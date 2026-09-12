"""找出 YAML 里「纯量（plain scalar）非法」的行：
1) 值以保留字符 ` 或 @ 开头；
2) 值里含 ": "（会被解析成嵌套映射）。
跳过块标量（| / >）内部的正文行。
"""

import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "openapi.yaml"
with open(path, encoding="utf-8") as fh:
    lines = fh.read().split("\n")

block_indent = None  # 块标量正文的缩进基准
problems = []

for i, line in enumerate(lines, 1):
    stripped = line.strip()
    indent = len(line) - len(line.lstrip(" "))

    if block_indent is not None:
        if stripped == "" or indent >= block_indent:
            continue
        block_indent = None

    if stripped == "" or stripped.startswith("#"):
        continue

    # 序列项 / 映射项
    m = re.match(r"^(\s*)(-\s+)?([A-Za-z0-9_.$#/-]+):\s*(.*)$", line)
    if not m:
        # 纯序列项：- xxx
        m2 = re.match(r"^(\s*)-\s+(.*)$", line)
        if m2:
            val = m2.group(2)
            if val[:1] in ("`", "@"):
                problems.append((i, "seq-start", val))
        continue

    lead, _dash, key, val = m.group(1), m.group(2), m.group(3), m.group(4)
    if val in ("|", ">", "|-", ">-", "|+", ">+"):
        block_indent = len(lead) + 1
        continue
    if val == "":
        continue

    q = val[:1]
    if q in ("`", "@"):
        problems.append((i, "starts-with-reserved", val))
        continue
    if q in ('"', "'", "{", "[", "&", "*", "!"):
        continue
    if ": " in val or val.endswith(":"):
        problems.append((i, "contains-colon-space", val))

if not problems:
    print("OK: 未发现非法纯量行")
    sys.exit(0)

print(f"发现 {len(problems)} 处可疑行：")
for i, kind, val in problems:
    print(f"  {i}\t{kind}\t{val[:90]}")
sys.exit(1)
