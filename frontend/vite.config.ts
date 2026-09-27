import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Single-file IIFE bundle served by HA at /halo_static/halo-panel.js.
// HA renders <halo-panel> and sets `.hass` on it (see src/main.tsx).
export default defineConfig({
  plugins: [react()],
  // React (and friends) reference process.env.NODE_ENV, which does not
  // exist in browsers. Without this, the panel dies with
  // "ReferenceError: process is not defined" and HA shows a blank page.
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    outDir: "../custom_components/halo/frontend",
    emptyOutDir: false,
    lib: {
      entry: "src/main.tsx",
      name: "HaloPanel",
      formats: ["iife"],
      fileName: () => "halo-panel.js",
    },
    minify: "esbuild",
  },
  test: {
    environment: "node",
  },
});
