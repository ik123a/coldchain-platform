/**
 * Production build wrapper.
 *
 * Runs `next build` with NEXT_DIST_DIR pointed at .next-build so a build can
 * never overwrite the dev server's .next directory. Running a build while
 * `next dev` is live previously killed the dev server with
 * "Cannot find module './<chunk>.js'", because the two emit different chunk
 * layouts into the same folder.
 */
import { spawn } from "node:child_process";

const distDir = process.env.NEXT_DIST_DIR || ".next-build";
const nextBin = process.platform === "win32" ? "next.cmd" : "next";

const child = spawn(nextBin, ["build"], {
  stdio: "inherit",
  shell: process.platform === "win32",
  env: { ...process.env, NEXT_DIST_DIR: distDir },
});

child.on("exit", (code, signal) => {
  if (signal) {
    console.error(`\nbuild terminated by signal ${signal}`);
    process.exit(1);
  }
  if (code !== 0) process.exit(code ?? 1);
  console.log(`\nbuild output: ${distDir}/`);
  process.exit(0);
});
