"use client";

import { useSyncExternalStore } from "react";

import { THEME_KEY as KEY } from "@/lib/theme-script";

export type ThemePref = "light" | "dark" | "system";

const listeners = new Set<() => void>();

function read(): ThemePref {
  const raw = window.localStorage.getItem(KEY);
  return raw === "light" || raw === "dark" ? raw : "system";
}

function apply(pref: ThemePref) {
  const dark = pref === "dark" || (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function setThemePref(pref: ThemePref) {
  if (pref === "system") window.localStorage.removeItem(KEY);
  else window.localStorage.setItem(KEY, pref);
  apply(pref);
  listeners.forEach((l) => l());
}

/** Flips whatever is currently showing and saves it as an explicit choice. */
export function toggleTheme() {
  setThemePref(document.documentElement.classList.contains("dark") ? "light" : "dark");
}

function subscribe(listener: () => void) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const onSystem = () => {
    if (read() === "system") apply("system");
    listener();
  };
  const onStorage = () => {
    apply(read());
    listener();
  };
  listeners.add(listener);
  media.addEventListener("change", onSystem);
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    media.removeEventListener("change", onSystem);
    window.removeEventListener("storage", onStorage);
  };
}

export function useThemePref(): ThemePref {
  return useSyncExternalStore(subscribe, read, () => "system");
}
