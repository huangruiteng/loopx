import react from "@vitejs/plugin-react";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  base: process.env.LOOPX_SITE_BASE ?? "/",
  plugins: [react(), {
    name: "public-directory-index",
    configureServer(server) {
      // Match static-host directory URLs before Vite's SPA fallback.
      server.middlewares.use((request, _response, next) => {
        const url = new URL(request.url ?? "/", "http://localhost");
        if ((url.pathname.startsWith("/blog/") || url.pathname.startsWith("/benchmarks/")) && url.pathname.endsWith("/")) {
          const index = new URL(`./public${url.pathname}index.html`, import.meta.url);
          if (existsSync(fileURLToPath(index))) request.url = `${url.pathname}index.html${url.search}`;
        }
        next();
      });
    },
  }],
  server: {
    fs: {
      allow: [fileURLToPath(new URL("../../..", import.meta.url))],
    },
  },
  build: {
    assetsDir: "site-assets",
    emptyOutDir: true,
  },
});
