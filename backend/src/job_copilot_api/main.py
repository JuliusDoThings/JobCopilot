"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="AI Job Copilot")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
