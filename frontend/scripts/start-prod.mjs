/** Serve the production build from .next-build (must match build-prod.mjs). */
import { spawn } from "node:child_process";

const distDir = process.env.NEXT_DIST_DIR || ".next-build";
const nextBin = process.platform === "win32" ? "next.cmd" : "next";

const child = spawn(nextBin, ["start", "-p", "3000"], {
  stdio: "inherit",
  shell: process.platform === "win32",
  env: { ...process.env, NEXT_DIST_DIR: distDir },
});
child.on("exit", (c) => process.exit(c ?? 0));
