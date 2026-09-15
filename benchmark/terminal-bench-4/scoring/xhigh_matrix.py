import json, os, collections, tempfile
# 与 xhigh_report.py 共用的中间产物路径：优先 $TB4_ROWS，否则系统临时目录。
_ROWS = os.environ.get("TB4_ROWS", os.path.join(tempfile.gettempdir(), "tb4_xhigh_rows.json"))
rows=json.load(open(_ROWS))
ARMS=["plain","goal","ssh-goal","codex-cli","heartbeat"]
# matched = tasks where ALL arms have clean OK xhigh
matched=[t for t,d in rows.items() if all(a in d and d[a][0]=="OK" for a in ARMS)]
print("matched (all-5 clean OK xhigh):", len(matched))
sol=collections.Counter()
for t in matched:
    for a in ARMS:
        if (rows[t][a][1] or 0)>0: sol[a]+=1
print("\n=== matched Solve@1.0 (denom={}) ===".format(len(matched)))
for a in ARMS: print(f"  {a:12s} {sol[a]}/{len(matched)}  mean={sol[a]/len(matched):.3f}")

# tasks solved by >=1 arm on matched
anysolve=[t for t in matched if any((rows[t][a][1] or 0)>0 for a in ARMS)]
print("\nmatched tasks solved by >=1 arm:", len(anysolve))
print("\n=== matched matrix (solved tasks only) ===")
sym=lambda t,a: "✅" if (rows[t][a][1] or 0)>0 else "0"
print("task |", " | ".join(ARMS))
for t in sorted(anysolve):
    print(f"{t} | "+" | ".join(sym(t,a) for a in ARMS))

# excluded pairs (not clean OK) per arm
print("\n=== excluded (RESOURCE/RETRY/PENDING) per arm ===")
for a in ARMS:
    ex=[(t,rows[t][a][0],rows[t][a][2]) for t in rows if a in rows[t] and rows[t][a][0]!="OK"]
    print(f"\n{a} ({len(ex)}):")
    for t,v,why in sorted(ex): print(f"   {t:32s} {v:9s} {why}")
# arms missing any xhigh run per task
print("\n=== tasks lacking a clean-OK xhigh for some arm (breaks matched) ===")
for t in sorted(rows):
    miss=[a for a in ARMS if not (a in rows[t] and rows[t][a][0]=="OK")]
    if miss: print(f"   {t:32s} miss: {miss}")
