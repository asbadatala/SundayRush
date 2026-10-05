// Server-safe (no "use client") so the root layout can inline it.

export const THEME_KEY = "sundayrush:theme";

/** Runs in <head> before first paint so the saved theme never flashes. Mirrors `apply` in lib/theme.ts. */
export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("${THEME_KEY}");var d=t==="dark"||(t!=="light"&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",d)}catch(e){}})()`;
