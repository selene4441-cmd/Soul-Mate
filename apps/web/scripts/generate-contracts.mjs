import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const workspace = path.resolve(scriptDir, "../../..");
const specPath = path.join(workspace, "packages/contracts/openapi.json");
const outputPath = path.join(workspace, "packages/contracts/client.ts");
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));

const operations = [];
for (const [route, methods] of Object.entries(spec.paths ?? {})) {
  for (const [method, definition] of Object.entries(methods)) {
    if (!["get", "post", "put", "patch", "delete"].includes(method)) continue;
    const operationId = definition.operationId ?? `${method}_${route}`.replace(/[^a-zA-Z0-9]+/g, "_");
    operations.push({
      method: method.toUpperCase(),
      path: route,
      operationId,
      tags: definition.tags ?? [],
    });
  }
}

const lines = [
  "// Generated from packages/contracts/openapi.json. Do not edit by hand.",
  'export type ApiMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";',
  "export type ApiOperation = {",
  "  method: ApiMethod;",
  "  path: string;",
  "  operationId: string;",
  "  tags: string[];",
  "};",
  "",
  "export const apiOperations = " + JSON.stringify(operations, null, 2) + " as const satisfies readonly ApiOperation[];",
  "",
];
fs.writeFileSync(outputPath, lines.join("\n"), "utf8");
console.log(`generated ${path.relative(workspace, outputPath)} (${operations.length} operations)`);
