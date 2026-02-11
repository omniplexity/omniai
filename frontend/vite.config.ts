import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  // GitHub Pages-safe relative asset paths.
  base: "./",
  plugins: [preact()],
  build: {
    target: "es2022",
    sourcemap: true
  },
  server: {
    port: 5173
  },
  test: {
    include: ["src/**/*.test.ts", "src/**/__tests__/**/*.ts"],
    exclude: ["tests/e2e/**"]
  }
});
