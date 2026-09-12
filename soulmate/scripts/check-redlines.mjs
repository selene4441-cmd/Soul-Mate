#!/usr/bin/env node
/**
 * 红线自查：扫描前端源码里有没有产品禁止出现的词，以及把 entropy 当分数用的低级形式。
 *
 * 用法：
 *   node check-redlines.mjs src            # 扫 src 目录
 *   node check-redlines.mjs src app        # 扫多个目录
 *   node check-redlines.mjs                # 默认扫当前目录（自动跳过 node_modules/.next/dist）
 *
 * 退出码：0 = 干净，1 = 命中红线。
 * 建议接进 CI 或 pre-commit。
 *
 * 注意：这是**兜底检查**，不是全部。它扫不出"把熵换算成百分比后起个别的名字"这种需要人判断的问题。
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, extname } from "node:path";

const FORBIDDEN_WORDS = [
  "匹配度",
  "契合度",
  "相似度",
  "人格报告",
  "MBTI",
  "用户标签",
  "用户画像",
  "匹配分",
  "亲密度",
];

/** 这些词单独出现不算命中（例如注释里解释"我们不做匹配度"），需要连着数字/百分比才算 */
const SUSPECT_WITH_NUMBER = ["匹配度", "契合度", "相似度", "得分", "评分", "排名", "等级"];

const SKIP_DIRS = new Set(["node_modules", ".next", "dist", "build", ".git", "out", "coverage"]);
const SKIP_FILES = new Set(["check-redlines.mjs"]); // 别把自己词表里的红线词算成命中
const CODE_EXT = new Set([".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".html", ".css"]);

/**
 * 文件级豁免：前 8 行内出现这个标记就整文件跳过。
 * 用于**定义**红线词表的文件（例如 lib/api/types.ts 里的 PRODUCT_FORBIDDEN_WORDS），
 * 它们写这些词是"立法"，不是"违规"。
 */
const SKIP_MARKER = "redlines:ignore-file";
const MARKER_SCAN_LINES = 8;

const args = process.argv.slice(2);
const roots = args.length > 0 ? args : ["."];

/** @type {{file: string, line: number, text: string, reason: string}[]} */
const hits = [];
let scanned = 0;

function walk(dir) {
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      walk(full);
      continue;
    }
    if (!CODE_EXT.has(extname(entry.name))) continue;
    if (SKIP_FILES.has(entry.name)) continue;
    scanFile(full);
  }
}

function scanFile(file) {
  let content;
  try {
    content = readFileSync(file, "utf8");
  } catch {
    return;
  }
  scanned += 1;
  const head = content.split("\n", MARKER_SCAN_LINES).join("\n");
  if (head.includes(SKIP_MARKER)) return; // 文件级豁免（立法文件）

  content.split("\n").forEach((raw, idx) => {
    // 去掉行尾注释后再判断，避免"我们不做匹配度"这类说明被误判
    const withoutInlineComment = raw.split("//")[0];
    const line = withoutInlineComment.trim();
    if (!line) return;
    if (line.startsWith("//") || line.startsWith("/*") || line.startsWith("*")) return; // 整行注释

    for (const word of FORBIDDEN_WORDS) {
      if (line.includes(word)) {
        hits.push({ file, line: idx + 1, text: line.slice(0, 120), reason: `禁止词「${word}」` });
      }
    }
    for (const word of SUSPECT_WITH_NUMBER) {
      if (!line.includes(word)) continue;
      // 出现了数值或百分号，基本就是在展示分数
      if (/\d/.test(line) || line.includes("%")) {
        hits.push({ file, line: idx + 1, text: line.slice(0, 120), reason: `「${word}」与数字同现，疑似展示分数` });
      }
    }
    // entropy / belief 被当百分比用的常见写法
    if (/(entropy|belief)/i.test(line) && /(\*\s*100|toFixed\(2\)\s*\)?\s*%|%\s*`)/.test(line)) {
      hits.push({ file, line: idx + 1, text: line.slice(0, 120), reason: "疑似把 entropy 换算成百分比展示" });
    }
  });
}

for (const root of roots) {
  let stat;
  try {
    stat = statSync(root);
  } catch {
    console.error(`跳过不存在的路径：${root}`);
    continue;
  }
  if (stat.isDirectory()) walk(root);
  else scanFile(root);
}

if (hits.length === 0) {
  console.log(`OK：扫描 ${scanned} 个文件，未发现红线。`);
  process.exit(0);
}

console.error(`发现 ${hits.length} 处红线（扫描 ${scanned} 个文件）：\n`);
for (const hit of hits) {
  console.error(`  ${relative(process.cwd(), hit.file)}:${hit.line}  ${hit.reason}`);
  console.error(`      ${hit.text}`);
}
console.error(
  "\n正确表达请参考契约第 6 节：用「共同点 / 差异 / 罕见共同点 / 世界观差异」，" +
    "不要展示匹配度、百分比、排名、等级。"
);
process.exit(1);
