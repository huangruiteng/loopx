import { existsSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";

const dashboardPublicDir = resolve(import.meta.dirname, "public");
const chatOutDir = resolve(import.meta.dirname, "../../../loopx/web/chat");
const retainedAssetsPath = resolve(chatOutDir, "asset-retention.json");
const sharedPwaAssets = ["manifest.webmanifest", "pwa/icon-192.png", "pwa/icon-512.png"] as const;

function retainedChatAssets(): Plugin {
  const previousIndex = resolve(chatOutDir, "index.html");
  const previousEntryAssets = existsSync(previousIndex)
    ? [...readFileSync(previousIndex, "utf8").matchAll(/(?:src|href)="\/chat\/(assets\/[^"]+)"/g)].map((match) => match[1])
    : [];
  const previousManifest = existsSync(retainedAssetsPath)
    ? JSON.parse(readFileSync(retainedAssetsPath, "utf8"))
    : { schema_version: "loopx_chat_asset_retention_v1", generations: [] };
  const previousGenerations = previousManifest.generations;
  if (previousManifest.schema_version !== "loopx_chat_asset_retention_v1"
    || !Array.isArray(previousGenerations) || previousGenerations.some(
    (generation) => !Array.isArray(generation) || generation.some(
      (asset) => typeof asset !== "string" || !/^assets\/[A-Za-z0-9._-]+$/.test(asset),
    ),
  )) {
    throw new Error("Invalid chat asset retention manifest");
  }
  const previousGeneration = previousGenerations.find((generation) =>
    previousEntryAssets.every((asset) => generation.includes(asset)),
  ) ?? previousEntryAssets;

  return {
    name: "loopx-bounded-chat-asset-retention",
    writeBundle(_options, bundle) {
      const generations: string[][] = [];
      const retained = new Set<string>();
      for (const generation of [
        Object.keys(bundle).filter((path) => path.startsWith("assets/")).sort(),
        previousGeneration,
        ...previousGenerations,
      ]) {
        const normalized = [...new Set(generation)].sort();
        if (normalized.some((asset) => !existsSync(resolve(chatOutDir, asset)))) continue;
        if (normalized.every((asset) => retained.has(asset))) continue;
        if (normalized.length && !generations.some((item) => item.join("\0") === normalized.join("\0"))) {
          generations.push(normalized);
          normalized.forEach((asset) => retained.add(asset));
        }
        // ponytail: one prior bundle protects rolling upgrades; add a larger
        // retention window only if multi-release stale tabs become a real need.
        if (generations.length === 2) break;
      }
      for (const name of readdirSync(resolve(chatOutDir, "assets"))) {
        if (!retained.has(`assets/${name}`)) rmSync(resolve(chatOutDir, "assets", name));
      }
      writeFileSync(retainedAssetsPath, `${JSON.stringify({
        schema_version: "loopx_chat_asset_retention_v1",
        generations,
      }, null, 2)}\n`);
    },
  };
}

function emitSharedPwaAssets(): Plugin {
  return {
    name: "loopx-shared-dashboard-pwa-assets",
    generateBundle() {
      for (const relativePath of sharedPwaAssets) {
        this.emitFile({
          type: "asset",
          fileName: relativePath,
          source: readFileSync(resolve(dashboardPublicDir, relativePath)),
        });
      }
    },
  };
}

export default defineConfig({
  root: resolve(import.meta.dirname, "chat"),
  base: "/chat/",
  // The chat bundle shares the root dashboard's manifest and icons without
  // copying unrelated showcase assets into the packaged chat directory.
  publicDir: false,
  plugins: [react(), tailwindcss(), emitSharedPwaAssets(), retainedChatAssets()],
  build: {
    outDir: chatOutDir,
    // Retention is bounded by retainedChatAssets instead of growing forever.
    emptyOutDir: false,
  },
});
