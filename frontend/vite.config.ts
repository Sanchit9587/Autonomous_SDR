import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies the API routes to the FastAPI backend so there are no CORS
// issues locally. Every backend route prefix must be listed here.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/campaigns": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
      "/rep": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});