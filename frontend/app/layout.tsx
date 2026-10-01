import type { Metadata } from "next";
import { Anek_Latin, Mukta } from "next/font/google";
import "./globals.css";
import { AppProvider } from "@/components/AppState";
import Shell from "@/components/Shell";
import Charts from "@/components/charts-setup";

// Anek (headings and figures) and Mukta (text) both come from Ek Type, an Indian foundry; Mukta carries Devanagari for Hindi copy.
const anek = Anek_Latin({ subsets: ["latin"], axes: ["wdth"], variable: "--font-anek" });
const mukta = Mukta({ subsets: ["latin", "devanagari"], weight: ["400", "500", "600", "700"], variable: "--font-mukta" });

export const metadata: Metadata = {
  title: "PromoForge | Prometheus Retail",
  description: "Plan festival promotions that make money, don't run out of stock, and reach customers an offer actually persuades.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${anek.variable} ${mukta.variable}`} suppressHydrationWarning>
      <body>
        <AppProvider>
          <Charts />
          <Shell>{children}</Shell>
        </AppProvider>
      </body>
    </html>
  );
}
