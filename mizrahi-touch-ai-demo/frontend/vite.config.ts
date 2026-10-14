import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Mizrahi #1 (the mortgage demo) owns :8790 / :5190 on this machine; this app's backend is :8791, Vite :5192.
const API = process.env.MZ_API || "http://127.0.0.1:8791";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": API,
      "/mcp": API,
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
