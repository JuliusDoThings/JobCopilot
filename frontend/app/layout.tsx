import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Job Copilot — Un regard clair sur votre candidature",
  description:
    "Comparez les compétences de votre CV aux exigences d’une offre d’emploi.",
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
