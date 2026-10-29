"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

/** Adds a Copy button to every rendered code block. */
export function CopyButtons() {
  const pathname = usePathname();
  useEffect(() => {
    document.querySelectorAll<HTMLDivElement>(".code").forEach((block) => {
      if (block.querySelector(".copy-btn")) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "copy-btn";
      btn.textContent = "Copy";
      btn.addEventListener("click", () => {
        const text = block.querySelector("code")?.textContent ?? "";
        navigator.clipboard.writeText(text).then(() => {
          btn.textContent = "Copied";
          setTimeout(() => (btn.textContent = "Copy"), 1500);
        });
      });
      block.appendChild(btn);
    });
  }, [pathname]);
  return null;
}
