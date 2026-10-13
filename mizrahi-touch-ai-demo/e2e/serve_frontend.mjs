// Build the customer app into its own folder and serve it with /api and /mcp proxied to a chosen
// backend. Lets browser QA run against an isolated backend without touching frontend/dist.
//
//   node e2e/serve_frontend.mjs <outDir> <port> <backendUrl>
//   node e2e/serve_frontend.mjs e2e/artifacts/ai-card/web 5841 http://127.0.0.1:8791
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const frontend = fileURLToPath(new URL("../frontend/", import.meta.url));
const viteDir = dirname(createRequire(resolve(frontend, "package.json")).resolve("vite/package.json"));
const { build, preview } = await import(pathToFileURL(resolve(viteDir, "dist/node/index.js")).href);
const [outDir, port, backend] = process.argv.slice(2);
if (!outDir || !port || !backend) {
  console.error("usage: node e2e/serve_frontend.mjs <outDir> <port> <backendUrl>");
  process.exit(2);
}
const configFile = resolve(frontend, "vite.config.ts");
const out = resolve(outDir);
await build({ root: frontend, configFile, logLevel: "warn", build: { outDir: out, emptyOutDir: true } });
const server = await preview({ root: frontend, configFile, build: { outDir: out },
  preview: { host: "127.0.0.1", port: Number(port), strictPort: true, proxy: { "/api": backend, "/mcp": backend } } });
server.printUrls();
