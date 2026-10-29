"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [light, setLight] = useState(false);
  useEffect(() => setLight(document.documentElement.dataset.theme === "light"), []);

  const flip = () => {
    const next = light ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("pingie-docs-theme", next);
    setLight(!light);
  };

  const label = light ? "Switch to dark mode" : "Switch to light mode";
  return (
    <button type="button" className="icon-btn" onClick={flip} aria-label={label} title={label}>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true">
        <path
          d={
            light
              ? "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"
              : "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
          }
        />
      </svg>
    </button>
  );
}
