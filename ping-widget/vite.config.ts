import { readFileSync } from "node:fs";
import { defineConfig } from "vite";

const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));

// One self-executing file (dist/widget.js) that customers load with a plain
// <script> tag. CSS is inlined into the bundle and injected into a shadow root.
export default defineConfig({
  define: { __PINGIE_VERSION__: JSON.stringify(version) },
  build: {
    target: "es2019",
    outDir: "dist",
    emptyOutDir: true,
    lib: {
      entry: "src/index.ts",
      name: "PingieWidget",
      formats: ["iife"],
      fileName: () => "widget.js",
    },
  },
});
