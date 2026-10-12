import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import "./ops.css";
import { StoreProvider } from "@/lib/store";
import { AuthProvider } from "@/lib/auth";
import { THEME_BOOT_SCRIPT } from "@/lib/theme";
import Shell from "@/components/Shell";

const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], display: "swap", variable: "--font-mono" });

export const metadata: Metadata = {
  title: "ColdChain Rescue — AI Cold-Chain Command Center",
  description: "Simulate. Detect. Investigate. Recover. (SIMULATION ENVIRONMENT)",
};

export const viewport: Viewport = {
  // The browser's own chrome (address bar, notch area) follows color-scheme.
  // A fixed dark value here paints a black bar above a white page on mobile.
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f4f6f8" },
    { media: "(prefers-color-scheme: dark)", color: "#080A0F" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
              {/* Must be the first thing in <body>: it writes data-theme before the
                  body paints, so a light-mode user never sees a dark flash. React
                  renders inline <script> in place (only src= scripts get hoisted). */}
              <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
              <AuthProvider>
          <StoreProvider>
            <Shell>{children}</Shell>
          </StoreProvider>
              </AuthProvider>
      </body>
    </html>
  );
}
