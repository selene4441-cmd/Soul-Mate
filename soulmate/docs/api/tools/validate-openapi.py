import sys

import yaml

REF = "$" + "ref"

d = yaml.safe_load(open("openapi.yaml", encoding="utf-8"))
print("openapi:", d["openapi"])
print("title:", d["info"]["title"], d["info"]["version"])
print("paths:", len(d["paths"]))
schemas = d["components"]["schemas"]
print("schemas:", len(schemas))
ops = [(m.upper(), p) for p, item in d["paths"].items() for m in item if m in ("get", "post", "put", "patch", "delete")]
print("operations:", len(ops))
for m, p in ops:
    st = d["paths"][p][m.lower()].get("x-contract-status", "implemented")
    print("   ", m.ljust(5), p.ljust(52), st)

bad = []


def walk(o, path=""):
    if isinstance(o, dict):
        if REF in o:
            target = o[REF]
            if target.startswith("#/components/schemas/"):
                name = target.split("/")[-1]
                if name not in schemas:
                    bad.append((path, name))
        for k, v in o.items():
            walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path + "/" + str(i))


walk(d)
print("broken schema refs:", bad if bad else "none")
# tag coverage
used_tags = {t for item in d["paths"].values() for op in item.values() if isinstance(op, dict) for t in op.get("tags", [])}
declared = {t["name"] for t in d["tags"]}
print("undeclared tags:", used_tags - declared or "none")
print("unused tags:", declared - used_tags or "none")
sys.exit(1 if bad else 0)
