// Build of the front (vite). The bundle goes to dist/, never tracked by Git (.gitignore). The dev server listens on the loopback address
// only (invariant 6); no proxy is declared: the server route is reached by a relative path.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1" },
  build: { outDir: "dist", sourcemap: false },
});
