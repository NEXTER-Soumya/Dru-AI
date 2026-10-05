import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const output = path.join(root, "frontend");
const runtimeSource = path.join(
  root,
  "node_modules",
  "onnxruntime-web",
  "dist",
);
const runtimeDestination = path.join(
  root,
  "static",
  "vendor",
  "onnxruntime-web",
);

await rm(runtimeDestination, { recursive: true, force: true });
await mkdir(path.dirname(runtimeDestination), { recursive: true });
await mkdir(runtimeDestination, { recursive: true });
for (const asset of [
  "ort.wasm.min.js",
  "ort-wasm-simd-threaded.mjs",
  "ort-wasm-simd-threaded.wasm",
]) {
  await cp(path.join(runtimeSource, asset), path.join(runtimeDestination, asset));
}

function makeStatic(html) {
  return html
    .replace(
      /\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}/g,
      "/static/$1",
    )
    .replace(/\{\{\s*url_for\('logout'\)\s*\}\}/g, "/logout")
    .replace(/\{\{\s*user_avatar\s*\}\}/g, "initial")
    .replace(/\{\{\s*user_initial\s*\}\}/g, "?")
    .replace(/\{\{\s*user_name\s*\}\}/g, "")
    .replace(
      /<div class="main" id="dashboardApp" \{% if requires_name %\}inert\{% endif %\}>/,
      '<div class="main" id="dashboardApp" inert style="visibility: hidden">',
    )
    .replace(
      /\{%\s*if\s*not\s+requires_name\s*%}hidden\{%\s*endif\s*%}/s,
      "hidden",
    )
    .replace(
      /<script src="\/static\/vendor\/onnxruntime-web\/ort\.wasm\.min\.js"><\/script>\s*<script>ort\.env\.wasm\.numThreads = 1; ort\.env\.wasm\.wasmPaths = '\/static\/vendor\/onnxruntime-web\/';<\/script>\s*<script src="\/static\/scripts\/users\/breed-inference\.js"><\/script>\s*<script src="\/static\/scripts\/users\/dashboard\.js"><\/script>\s*<script src="\/static\/scripts\/users\/informations\.js"><\/script>/,
      '<script type="module" src="/static/scripts/users/bootstrap.js"></script>',
    );
}

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(path.join(root, "static"), path.join(output, "static"), {
  recursive: true,
});
await cp(path.join(root, "vercel.json"), path.join(output, "vercel.json"));

const pages = [
  ["templates/pages/index.html", "index.html"],
  ["templates/pages/users.html", "dashboard.html"],
];

for (const [source, destination] of pages) {
  const html = await readFile(path.join(root, source), "utf8");
  const built = makeStatic(html);
  if (/\{\{|\{%/.test(built)) {
    throw new Error(`Unprocessed template syntax remains in ${source}.`);
  }
  await writeFile(path.join(output, destination), built);
}

console.log("Built static Vercel frontend in frontend/.");
