import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
  server: { proxy: { "/api": { target: "http://127.0.0.1:8765", changeOrigin: true,
    configure: proxy => proxy.on("proxyReq", request => request.setHeader("Origin", "http://127.0.0.1:8765")) } } },
});
