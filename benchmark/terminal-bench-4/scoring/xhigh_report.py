import json, os, sys, pathlib, importlib.util, re, tempfile
# 结果树根目录走 $TB4_OUT（同 verdict.py），verdict.py 从本 scoring/ 目录旁加载。
OUT = pathlib.Path(os.environ.get("TB4_OUT", "tb4-full")).resolve()
spec = importlib.util.spec_from_file_location("verdict", str(pathlib.Path(__file__).with_name("verdict.py")))
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)
ARMS = ["plain","goal","ssh-goal","codex-cli","heartbeat"]

def stamp_effort(stamp, arm):
    cfg = stamp/arm/"config.json"
    if cfg.exists():
        try:
            d=json.loads(cfg.read_text()); ags=d.get("agents") or []
            return (ags[0].get("kwargs") or {}).get("reasoning_effort") if ags else None
        except: return None
    return None

def scan_stream(stamp):
    """memory-safe: stream files line by line, cap per-file bytes."""
    recon=disc=errev=0; cap=False; acct=False
    files = list(stamp.glob("**/*raw_stdout*.jsonl")) + list(stamp.glob("**/trajectory.json")) \
            + list(stamp.glob("**/*.stderr"))
    CAPB=200_000_000
    for f in files:
        try:
            read=0
            with open(f,'r',errors='ignore') as fh:
                for line in fh:
                    read+=len(line)
                    if read>CAPB: break
                    recon += len(V.RECONNECT.findall(line))
                    for m in V.DISCONNECT.findall(line):
                        disc+=1
                        if any(s in m.lower() for s in V.ACCOUNT): acct=True
                    if not cap and V.CAPACITY.search(line): cap=True
                    errev += len(V.ERROR_EVENT.findall(line))
        except Exception: continue
    return recon, disc, cap, acct, errev

def verdict_stamp(task, arm, stamp):
    comp, err, rw = V.read_result(stamp)
    rc = V.read_receipt(stamp)
    recon, disc, cap, acct, errev = scan_stream(stamp)
    sec, txt = V.runtime_sec(stamp)
    eec = rc.get("error_event_count");  eec = errev if eec is None else eec
    iec = rc.get("item_event_count") or 0
    if not (stamp/"run.log").exists(): return "PENDING","无 run.log", rw
    if "Total runtime" not in txt: return "PENDING","未收尾", rw
    if comp is None: return "PENDING","result 未出", rw
    timeout_ok = any(s in txt for s in V.TIMEOUT_OK)
    if cap: return "RETRY", f"serverOverloaded (sec={sec},eec={eec})", rw
    if disc>0 and acct: return "RESOURCE", f"no credits/access terminated (disc={disc})", rw
    if err and err>0:
        he=[h for h in V.HARNESS_ERR if h in txt]
        return "RESOURCE", f"harbor errored>0 ({','.join(he) or '未知'})", rw
    if arm=="plain":
        if disc>0 or eec>=V.PLAIN_STORM or recon>=V.PLAIN_STORM:
            return "RETRY", f"plain 断流 disc={disc} eec={eec} recon={recon}", rw
        return "OK", f"reward={rw} sec={sec}", rw
    if timeout_ok or (rw is not None and rw>0):
        if disc>=3 or eec>=15 or recon>=25:
            return "RETRY", f"断流偏重 disc={disc} eec={eec} recon={recon}", rw
        return "OK", f"reward={rw} sec={sec} eec={eec}{' timeout' if timeout_ok else ''}", rw
    if disc>0 or eec>=V.EEC_STORM or recon>=V.RECON_STORM:
        return "RETRY", f"断流/未收尾 disc={disc} eec={eec} recon={recon}", rw
    if iec<50 and (rw is None or rw<=0) and not timeout_ok:
        return "RETRY", f"疑空跑 sec={sec} iec={iec}", rw
    return "OK", f"reward={rw} sec={sec} eec={eec}{' timeout' if timeout_ok else ''}", rw

tasks = sorted([p.name for p in OUT.iterdir() if p.is_dir() and not p.name.startswith('.') and p.name not in ("report","rerun")])
rows={}
for task in tasks:
    for arm in ARMS:
        base = OUT/task/arm
        if not base.is_dir(): continue
        xs=[st for st in base.iterdir() if st.is_dir() and stamp_effort(st,arm)=="xhigh"]
        if not xs: continue
        xs.sort(key=lambda p:p.stat().st_mtime)
        evals=[(st,)+verdict_stamp(task,arm,st) for st in xs]
        oks=[e for e in evals if e[1]=="OK"]
        if oks:
            solved=[e for e in oks if (e[3] or 0)>0]
            chosen=(solved or oks)[-1]
        else:
            chosen=evals[-1]
        rows.setdefault(task,{})[arm]=(chosen[1],chosen[3],chosen[2])
    print(f"done {task}", file=sys.stderr)

_ROWS = os.environ.get("TB4_ROWS", os.path.join(tempfile.gettempdir(), "tb4_xhigh_rows.json"))
json.dump(rows, open(_ROWS, "w"), ensure_ascii=False, indent=1)
import collections
summary=collections.defaultdict(collections.Counter)
for t,d in rows.items():
    for arm,(v,rw,why) in d.items(): summary[arm][v]+=1
print("=== per-arm xhigh verdict counts ===")
for arm in ARMS:
    c=summary[arm]
    print(f"{arm:12s} OK={c['OK']:3d} RESOURCE={c['RESOURCE']:3d} RETRY={c['RETRY']:3d} PENDING={c['PENDING']:3d}")
print("\n=== solved (reward>0) among clean OK xhigh ===")
for arm in ARMS:
    solved=[t for t,d in rows.items() if arm in d and d[arm][0]=="OK" and (d[arm][1] or 0)>0]
    okn=sum(1 for t,d in rows.items() if arm in d and d[arm][0]=="OK")
    print(f"{arm:12s} solved={len(solved)}/{okn} OK  -> {sorted(solved)}")
print("\ntasks with any xhigh:", len(rows))
