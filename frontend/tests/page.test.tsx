import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Home from "@/app/page";

const scored = {
  status: "scored",
  score: 50,
  matched_skills: ["python"],
  missing_skills: ["sql"],
  reason: null,
};
const unscored = {
  status: "not_scorable",
  score: null,
  matched_skills: [],
  missing_skills: [],
  reason: "no_explicit_required_skills",
};
function fill() {
  fireEvent.change(screen.getByRole("textbox", { name: "Votre CV" }), {
    target: { value: " CV fictif " },
  });
  fireEvent.change(screen.getByRole("textbox", { name: "L’offre d’emploi" }), {
    target: { value: " Annonce fictive " },
  });
}
function button() {
  return screen.getByRole("button", { name: /Analyser la compatibilité/ });
}

describe("analysis form", () => {
  it("shows accessible fields and the score limitation", () => {
    render(<Home />);
    expect(screen.getByRole("textbox", { name: "Votre CV" })).toBeRequired();
    expect(
      screen.getByRole("textbox", { name: "L’offre d’emploi" }),
    ).toBeRequired();
    expect(
      screen.getByText(
        "Le score mesure la couverture des compétences obligatoires identifiées, pas les chances de recrutement.",
      ),
    ).toBeVisible();
  });
  it("validates missing and blank fields without requests", async () => {
    render(<Home />);
    fireEvent.change(screen.getByRole("textbox", { name: "Votre CV" }), {
      target: { value: " \n " },
    });
    await userEvent.click(button());
    expect(screen.getAllByRole("alert")).toHaveLength(2);
    expect(screen.getByRole("textbox", { name: "Votre CV" })).toHaveFocus();
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each(["Votre CV", "L’offre d’emploi"])(
    "validates the maximum for %s",
    async (label) => {
      render(<Home />);
      fill();
      fireEvent.change(screen.getByRole("textbox", { name: label }), {
        target: { value: "x".repeat(20_001) },
      });
      await userEvent.click(button());
      expect(screen.getByRole("alert")).toHaveTextContent("20 000");
      expect(fetch).not.toHaveBeenCalled();
    },
  );
  it.each([50, 0])(
    "shows scored %i percent, skills and no technical payload",
    async (score) => {
      const fetcher = vi
        .fn()
        .mockResolvedValue(Response.json({ ...scored, score }));
      vi.stubGlobal("fetch", fetcher);
      render(<Home />);
      fill();
      await userEvent.click(button());
      expect(await screen.findByText(`${score} %`)).toBeVisible();
      expect(screen.getByText("python")).toBeVisible();
      expect(screen.getByText("sql")).toBeVisible();
      expect(fetcher).toHaveBeenCalledWith(
        "/api/analyze",
        expect.objectContaining({
          body: JSON.stringify({
            cv_text: "CV fictif",
            job_text: "Annonce fictive",
          }),
        }),
      );
      expect(
        screen.queryByText("Pas de score à calculer"),
      ).not.toBeInTheDocument();
    },
  );
  it("shows no percentage for not_scorable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(unscored)));
    render(<Home />);
    fill();
    await userEvent.click(button());
    expect(await screen.findByText("Pas de score à calculer")).toBeVisible();
    expect(screen.queryByText(/\d+\s?%/)).not.toBeInTheDocument();
  });
  it.each([422, 502, 503, 504])(
    "shows a controlled error for status %i",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(new Response("RAW-SECRET", { status })),
      );
      render(<Home />);
      fill();
      await userEvent.click(button());
      expect(await screen.findByRole("alert")).toBeVisible();
      expect(screen.queryByText("RAW-SECRET")).not.toBeInTheDocument();
      expect(screen.queryByText(/\d+\s?%/)).not.toBeInTheDocument();
    },
  );
  it("handles network failure without a score", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("RAW-SECRET")));
    render(<Home />);
    fill();
    await userEvent.click(button());
    expect(await screen.findByRole("alert")).toHaveTextContent("connexion");
    expect(screen.queryByText("RAW-SECRET")).not.toBeInTheDocument();
  });
  it("rejects inconsistent successful responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ ...scored, score: null })),
    );
    render(<Home />);
    fill();
    await userEvent.click(button());
    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.queryByText(/\d+\s?%/)).not.toBeInTheDocument();
  });
  it("locks submission and inputs until completion, then clears stale results on edit", async () => {
    let resolve!: (response: Response) => void;
    const fetcher = vi.fn(
      () =>
        new Promise<Response>((done) => {
          resolve = done;
        }),
    );
    vi.stubGlobal("fetch", fetcher);
    render(<Home />);
    fill();
    const form = button().closest("form")!;
    fireEvent.submit(form);
    fireEvent.submit(form);
    expect(fetcher).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("button", { name: /Analyse en cours/ }),
    ).toBeDisabled();
    expect(screen.getByRole("status")).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Votre CV" })).toBeDisabled();
    await act(async () => resolve(Response.json(scored)));
    expect(await screen.findByText("50 %")).toBeVisible();
    await waitFor(() => expect(button()).toBeEnabled());
    fireEvent.change(screen.getByRole("textbox", { name: "Votre CV" }), {
      target: { value: "Autre CV fictif" },
    });
    expect(screen.queryByText("50 %")).not.toBeInTheDocument();
  });
});
