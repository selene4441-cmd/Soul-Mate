import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const root = path.resolve(__dirname, "..");

function sourceFiles(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    return /\.(ts|tsx)$/.test(entry.name) ? [full] : [];
  });
}

describe("UI 表达约束", () => {
  const sources = [
    ...sourceFiles(path.join(root, "app")),
    ...sourceFiles(path.join(root, "components")),
  ]
    .filter((file) => !file.endsWith(".test.ts"))
    .map((file) => ({ file, text: fs.readFileSync(file, "utf8") }));

  it("不展示确定性分值与固定人格标签", () => {
    const forbidden = [/匹配度/, /匹配百分比/, /星级/, /等级/, /最匹配/, /命中注定/, /人格标签/];
    for (const source of sources) {
      for (const pattern of forbidden) {
        expect(source.text, `${source.file} 不应包含 ${pattern}`).not.toMatch(pattern);
      }
    }
  });

  it("推荐解释同时包含共同点、差异与未知信息", () => {
    const allText = sources.map((source) => source.text).join("\n");
    expect(allText).toContain("目前看到的共同点");
    expect(allText).toContain("可能需要进一步确认的差异");
    expect(allText).toContain("现在仍然不知道的事情");
    expect(allText).toContain("可以怎样继续了解");
  });

  it("用户可以用更像、不太像和不确定修正信号", () => {
    const allText = sources.map((source) => source.text).join("\n");
    expect(allText).toContain("更像");
    expect(allText).toContain("不太像");
    expect(allText).toContain("不确定");
  });

  it("交流产品保留双向连接和安全退出入口", () => {
    const allText = sources.map((source) => source.text).join("\n");
    expect(allText).toContain("连接请求");
    expect(allText).toContain("愿意聊聊");
    expect(allText).toContain("交流提示");
    expect(allText).toContain("结束交流");
    expect(allText).toContain("拉黑");
  });

  it("交流页不展示在线和输入状态压力", () => {
    const forbidden = [/在线状态/, /正在输入/, /精确已读/];
    for (const source of sources) {
      for (const pattern of forbidden) {
        expect(source.text, `${source.file} 不应包含 ${pattern}`).not.toMatch(pattern);
      }
    }
  });
});

describe("浏览器 API 边界", () => {
  it("所有修改请求携带 CSRF 头", () => {
    const client = fs.readFileSync(path.join(root, "lib", "api.ts"), "utf8");
    expect(client).toContain("X-CSRF-Token");
    expect(client).toContain("credentials: \"include\"");
  });
});
