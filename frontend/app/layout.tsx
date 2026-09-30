import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import "./ops.css";
import { StoreProvider } from "@/lib/store";
import Layout from "@/components/Layout";

const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], display: "swap", variable: "--font-mono" });

export const metadata: Metadata = {
  title: "ColdChain Rescue — AI Cold-Chain Command Center",
  description: "Simulate. Detect. Investigate. Recover. (SIMULATION ENVIRONMENT)",
};

export const viewport: Viewport = {
  themeColor: "#080A0F",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <StoreProvider>
          <Layout>{children}</Layout>
        </StoreProvider>
      </body>
    </html>
  );
}
