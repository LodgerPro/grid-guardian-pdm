import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base = "./" so the static build works equally well on GitHub Pages
// (under /grid-guardian-pdm/) and on Vercel/Netlify (under root).
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "dist",
    sourcemap: false,
  },
  server: {
    port: 5173,
  },
});
