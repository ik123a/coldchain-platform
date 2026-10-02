export type Theme = "dark" | "light" | "system";

export const THEME_KEY = "cc.theme";

/**
 * Resolve a stored preference down to the two the CSS actually understands.
 *
 * "system" has no CSS equivalent — [data-theme="system"] would match no
 * token block, so the page would render with :root defaults (dark) while the
 * OS asked for light. That mismatch is exactly the bug this function exists
 * to prevent: the attribute must always be dark|light, never "system".
 *
 * MUST be safe to call during server prerender. /settings is statically
 * generated, and Layout (which calls this on every render) runs there with no
 * `window`. Reading matchMedia unconditionally threw
 * `ReferenceError: window is not defined` and failed `next build`. The
 * `typeof window` guard keeps the server on the dark default — which is also
 * what the boot script corrects before first paint on the client.
 */
export function resolveTheme(pref: Theme): "dark" | "light" {
  if (pref === "light") return "light";
  if (pref === "dark") return "dark";
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

/**
 * Runs before first paint from an inline script in <head>.
 *
 * Without this the document paints the dark :root palette once and only
 * flips after hydration reads localStorage — a white flash on every reload
 * for anyone who chose light. Writing the attribute here means the correct
 * palette is already on <html> when the first style resolves.
 */
export const THEME_BOOT_SCRIPT = `(function(){try{
var p=localStorage.getItem("${THEME_KEY}")||"system";
var l=p==="light"||(p==="system"&&window.matchMedia("(prefers-color-scheme: light)").matches);
document.documentElement.setAttribute("data-theme",l?"light":"dark");
}catch(e){document.documentElement.setAttribute("data-theme","dark");}})();`;
