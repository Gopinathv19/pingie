"use client";

import { useCallback, useEffect, useState } from "react";
import { DEFAULT_THEME_PREF, THEME_KEY } from "./theme-script";

export type ThemePref = "dark" | "light" | "system";
export type Theme = "dark" | "light";

const KEY = THEME_KEY;
const DEFAULT_PREF: ThemePref = DEFAULT_THEME_PREF;

const systemTheme = (): Theme => (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");

function readPref(): ThemePref {
  const v = localStorage.getItem(KEY);
  return v === "light" || v === "dark" || v === "system" ? v : DEFAULT_PREF;
}

function apply(pref: ThemePref) {
  document.documentElement.dataset.theme = pref === "system" ? systemTheme() : pref;
}

export function useTheme() {
  const [pref, setPrefState] = useState<ThemePref>(DEFAULT_PREF);

  useEffect(() => {
    setPrefState(readPref());
  }, []);

  useEffect(() => {
    if (pref !== "system") return;
    const mq = matchMedia("(prefers-color-scheme: light)");
    const onChange = () => apply("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [pref]);

  const setPref = useCallback((next: ThemePref) => {
    localStorage.setItem(KEY, next);
    apply(next);
    setPrefState(next);
  }, []);

  return { pref, setPref };
}
