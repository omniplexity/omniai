import { defineConfig } from "vite";

export default defineConfig({
  base: process.env.GITHUB_PAGES_BASE ?? "/",
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/v1": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path,
      },
    },
  },
});
