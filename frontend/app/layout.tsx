import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AppProvider } from "@/components/AppState";
import Header from "@/components/Header";
import Charts from "@/components/charts-setup";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Prometheus PromoForge",
  description: "Plan festival promotions that make money, don't run out of stock, and target customers an offer actually persuades.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body>
        <AppProvider>
          <Charts />
          <Header />
          {children}
        </AppProvider>
      </body>
    </html>
  );
}
