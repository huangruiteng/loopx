#!/usr/bin/env python3
"""重跑后看一眼轨迹：判断是否因 API 限流/断流/资源失败。

用法:
  check_rerun.py                      # 检查全部重跑对（最新 stamp）
  check_rerun.py <task> <arm>         # 单对

判据（每 (task,arm) 取最新 stamp 目录）:
  - result.json.stats -> n_completed_trials / n_errored_trials / reward
  - goal_receipt.json -> error_event_count / goal_status / continuation_turn_completed
  - raw stdout/trajectory -> 'Reconnecting... x/y' 次数、'stream disconnected' 内容
  - run.log 尾部 -> address pool / Docker compose failed / RuntimeError / CancelledError / TimeoutError

分类:
  OK           n_errored==0 且 无断流风暴/无致命资源信号（reward=0 只因任务难，可接受）
  NET_RERUN    断流/限流迹象明显（error_event_count 高 或 Reconnecting 多 或 turn.failed）-> 再重跑
  RESOURCE     账号/资源不可解（no credits / access terminated / 网段池 / compose failed / errored>0）-> 记录后跑后面的
  PENDING      还没有产物 / 正在跑
"""
import json, os, sys, re, pathlib, glob

OUT = pathlib.Path(os.environ.get("TB4_OUT", "tb4-full")).resolve()
RECONNECT = re.compile(r"Reconnecting\.\.\.\s*\d+/\d+")
DISCONNECT = re.compile(r"stream disconnected before completion:[^\"]{0,160}")
FATAL_ACCOUNT = ("no credits remaining", "access was terminated", "violation of our policies",
                 "insufficient_quota")
FATAL_RES = ("all predefined address pools have been fully subnetted",
             "Docker compose command failed", "Cannot connect to the Docker daemon")
HARNESS_ERR = ("RuntimeError", "CancelledError", "TimeoutError", "AgentTimeoutError",
               "VerifierTimeoutError")

PAIRS = {
 "goal": "ctr-optimization interleaved-vigenere layout-config-recreation sound-change-cascade uefi-bootkit wdm-design freecad-impeller freecad-platform-drawing freecad-spring-clip".split(),
 "ssh-goal": "coq-block-bound embedding-drift-monitor heat-pump-warranty interleaved-vigenere legacy-utility-triage medical-claims-processing nextjs-performance rs-archive-clone uefi-bootkit wdm-design freecad-impeller freecad-platform-drawing freecad-spring-clip".split(),
 "codex-cli": "bun-sourcemap-leak coq-block-bound ctr-optimization medical-claims-processing nextjs-performance payments-pipeline-fix wdm-design".split(),
 "heartbeat": "cumulative-layout-shift embedding-drift-monitor intrastat-meldung lake-temp-glm music-harmony retro-console-soc rs-archive-clone sglang-qwen-burst wdm-design freecad-impeller freecad-platform-drawing freecad-spring-clip".split(),
}

def latest_stamp(task, arm):
    base = OUT / task / arm
    if not base.is_dir():
        return None
    stamps = sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime)
    return stamps[-1] if stamps else None

def read_result(stamp):
    res = sorted(stamp.glob("**/result.json"), key=lambda p: p.stat().st_mtime)
    for p in reversed(res):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        st = d.get("stats") or {}
        if st.get("n_completed_trials") is not None:
            rw = None
            for ev, v in (st.get("evals") or {}).items():
                vals=[float(k) for k,t in ((v.get("reward_stats") or {}).get("reward") or {}).items() for _ in t]
                if vals: rw = sum(vals)/len(vals)
            return st.get("n_completed_trials"), st.get("n_errored_trials"), rw
    return None, None, None

def read_receipt(stamp):
    rc = list(stamp.glob("**/goal_receipt.json"))
    if not rc: return {}
    try: return json.loads(rc[0].read_text())
    except Exception: return {}

def scan_text(stamp):
    recon = 0; disc = []; fatal_acct=False
    for f in list(stamp.glob("**/*stdout*.jsonl")) + list(stamp.glob("**/trajectory.json")):
        try: t = f.read_text(errors="ignore")
        except Exception: continue
        recon += len(RECONNECT.findall(t))
        for m in DISCONNECT.findall(t):
            disc.append(m)
            if any(s in m.lower() for s in FATAL_ACCOUNT): fatal_acct=True
    tail = ""
    rl = stamp / "run.log"
    if rl.exists(): tail = rl.read_text(errors="ignore")[-8000:]
    return recon, disc, fatal_acct, tail

def classify(task, arm):
    stamp = latest_stamp(task, arm)
    if stamp is None:
        return "PENDING", "无目录", {}
    comp, err, rw = read_result(stamp)
    rc = read_receipt(stamp)
    recon, disc, fatal_acct, tail = scan_text(stamp)
    eec = rc.get("error_event_count")
    cont = rc.get("goal_continuation_turn_completed_count")
    gstat = rc.get("goal_status")
    info = dict(stamp=stamp.name, completed=comp, errored=err, reward=rw,
                error_event_count=eec, reconnecting=recon, disconnects=len(disc),
                continuation=cont, goal_status=gstat)
    # running? (no result.json yet)
    if comp is None and not (stamp/"run.log").exists():
        return "PENDING", "无 result 无 run.log", info
    # fatal resource / account
    if fatal_acct:
        return "RESOURCE", "上游账号: no credits/access terminated", info
    for s in FATAL_RES:
        if s in tail:
            return "RESOURCE", f"资源: {s}", info
    if err and err > 0:
        # harness error class in tail?
        he = [h for h in HARNESS_ERR if h in tail]
        return "RESOURCE", f"errored>0 ({','.join(he) or '未知'})", info
    if comp is None:
        return "PENDING", "run.log 有但 result 未出（在跑或异常退出）", info
    # net storm heuristics
    net_bad = (eec or 0) > 10 or recon > 20 or len(disc) > 0
    if net_bad:
        return "NET_RERUN", f"断流迹象 eec={eec} reconnect={recon} disc={len(disc)}", info
    return "OK", (f"reward={rw}" + (f" (goal={gstat},cont={cont})" if gstat else "")), info

def main():
    if len(sys.argv) == 3:
        pairs = [(sys.argv[1], sys.argv[2])]
    else:
        pairs = [(t, a) for a, ts in PAIRS.items() for t in ts]
    rows=[]
    for task, arm in pairs:
        cls, why, info = classify(task, arm)
        rows.append((cls, arm, task, why, info))
    order={"RESOURCE":0,"NET_RERUN":1,"PENDING":2,"OK":3}
    rows.sort(key=lambda r: (order.get(r[0],9), r[1], r[2]))
    from collections import Counter
    c=Counter(r[0] for r in rows)
    print("== 汇总:", dict(c), " 共", len(rows), "对 ==")
    for cls, arm, task, why, info in rows:
        print(f"[{cls:9}] {arm:9} {task:28} {why}")
    return rows

if __name__ == "__main__":
    main()
