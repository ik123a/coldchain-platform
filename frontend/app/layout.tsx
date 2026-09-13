import type { Metadata } from "next";
import "./globals.css";
import { StoreProvider } from "@/lib/store";
import Layout from "@/components/Layout";

export const metadata: Metadata = {
  title: "ColdChain Rescue — AI Cold-Chain Command Center",
  description: "Simulate. Detect. Investigate. Recover. (SIMULATION ENVIRONMENT)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <StoreProvider>
          <Layout>{children}</Layout>
        </StoreProvider>
      </body>
    </html>
  );
}
