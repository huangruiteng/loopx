#!/usr/bin/env python3
"""单 (task,arm) 轨迹判定：OK / RETRY / RESOURCE / PENDING。

关键区分（吸取教训）：
  - `"status":"failed"` 在 raw 里多数是**shell 命令失败**（agent 自己跑的命令），不是 turn 失败，
    不能据此判 RETRY。
  - 跑满预算正常收尾 = run.log 有 `goal_timeout_before_terminal` → 属正常，判 OK
    （长程任务预算耗尽是正常，reward=0 是任务难/预算紧，不是 API 失败）。
真正的基础设施失败信号：
  - serverOverloaded / "at capacity"（codex 不重试，整 turn 废）→ RETRY
  - error_event_count(eec) 高（断流风暴）→ RETRY
  - stream disconnected before completion + 账单/封号文案 → RESOURCE
  - harbor n_errored_trials>0（环境/异常类故障）→ RESOURCE
  - 极短空跑（没到预算、事件极少、无收尾标记）→ RETRY

退出码 0=OK 10=RETRY 20=RESOURCE 30=PENDING
"""
import json, os, sys, re, pathlib

# 结果树根目录：默认 $TB4_OUT，或回退当前目录下的 tb4-full。不再内嵌任何绝对路径。
OUT = pathlib.Path(os.environ.get("TB4_OUT", "tb4-full")).resolve()
RECONNECT = re.compile(r"Reconnecting\.\.\.\s*\d+/\d+")
DISCONNECT = re.compile(r"stream disconnected before completion:[^\"]{0,200}")
CAPACITY = re.compile(r"at capacity|serverOverloaded|server_overloaded|overloaded_error", re.I)
ERROR_EVENT = re.compile(r'"method"\s*:\s*"error"')
ACCOUNT = ("no credits remaining", "access was terminated", "violation of our policies", "insufficient_quota")
HARNESS_ERR = ("RuntimeError", "CancelledError", "TimeoutError", "AgentTimeoutError", "VerifierTimeoutError")
RUNTIME_RE = re.compile(r"Total runtime:\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?")
TIMEOUT_OK = ("goal_timeout_before_terminal", "超时终止（预期行为）", "超时终止")

# 阈值
EEC_STORM = 30      # 断流事件数达此即判风暴
EEC_DESPITE = 60    # 即便跑满预算，eec 超此说明大半时间在断流重连 → 仍重跑
RECON_STORM = 40
SHORT_SEC = 1500    # 少于此且事件极少视为空跑
FULLBUDGET_SEC = 4800
PLAIN_STORM = 15    # plain 单长 turn：重连/错误事件达此即判 API 不稳需重跑

def latest_stamp(task, arm):
    base = OUT / task / arm
    if not base.is_dir(): return None
    ds = sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime)
    return ds[-1] if ds else None

def read_result(stamp):
    for p in reversed(sorted(stamp.glob("**/result.json"), key=lambda p: p.stat().st_mtime)):
        try: d = json.loads(p.read_text())
        except Exception: continue
        st = d.get("stats") or {}
        if st.get("n_completed_trials") is not None:
            rw=None
            for ev,v in (st.get("evals") or {}).items():
                vals=[float(k) for k,t in ((v.get("reward_stats") or {}).get("reward") or {}).items() for _ in t]
                if vals: rw=sum(vals)/len(vals)
            return st.get("n_completed_trials"), st.get("n_errored_trials"), rw
    return None, None, None

def read_receipt(stamp):
    for rc in stamp.glob("**/goal_receipt.json"):
        try: return json.loads(rc.read_text())
        except Exception: pass
    return {}

def scan(stamp):
    recon=0; disc=0; cap=False; acct=False; errev=0
    files = list(stamp.glob("**/*raw_stdout*.jsonl")) + list(stamp.glob("**/trajectory.json")) \
            + list(stamp.glob("**/*.stderr"))
    for f in files:
        try: t=f.read_text(errors="ignore")
        except Exception: continue
        recon += len(RECONNECT.findall(t))
        for m in DISCONNECT.findall(t):
            disc += 1
            if any(s in m.lower() for s in ACCOUNT): acct=True
        if CAPACITY.search(t): cap=True
        errev += len(ERROR_EVENT.findall(t))
    return recon, disc, cap, acct, errev

def runtime_sec(stamp):
    rl = stamp/"run.log"
    if not rl.exists(): return None, ""
    txt = rl.read_text(errors="ignore")
    m = RUNTIME_RE.search(txt)
    sec=None
    if m:
        h,mi,s = (int(x) if x else 0 for x in m.groups())
        sec = h*3600+mi*60+s
    return sec, txt

def verdict(task, arm):
    stamp = latest_stamp(task, arm)
    if stamp is None: return "PENDING","无目录"
    comp, err, rw = read_result(stamp)
    rc = read_receipt(stamp)
    recon, disc, cap, acct, errev = scan(stamp)
    sec, txt = runtime_sec(stamp)
    eec = rc.get("error_event_count")
    if eec is None: eec = errev            # 无 receipt 时用 raw 的 error 事件数兜底
    cont = rc.get("goal_continuation_turn_completed_count")
    iec = rc.get("item_event_count") or 0
    if not (stamp/"run.log").exists():
        return "PENDING","无 run.log（在跑）"
    # harbor 只在收尾时打印 "Total runtime"；没有它就是还在跑（或中途崩）。
    # 无论 harbor 是否预写了 result.json，一律先当在跑，避免把半成品判成结果。
    if "Total runtime" not in txt:
        return "PENDING","harbor 未收尾（在跑/中途退出）"
    if comp is None:
        return "PENDING","result 未出（异常退出）"
    timeout_ok = any(s in txt for s in TIMEOUT_OK)
    # ---- 致命瞬时：容量（codex 不重试，整 turn 废）----
    if cap:
        return "RETRY", f"serverOverloaded/at-capacity (runtime={sec}s, eec={eec})"
    # ---- 账号/资源不可解 ----
    if disc>0 and acct:
        return "RESOURCE", f"stream disconnected: no credits/access terminated (disc={disc})"
    if err and err>0:
        he=[h for h in HARNESS_ERR if h in txt]
        return "RESOURCE", f"harbor errored>0 ({','.join(he) or '未知'})"
    # ---- plain 专用：CodexPlainAppServer 不做 goal 续跑，goal_receipt 的 iec≈2 / goal_status=none /
    #      无 goal_timeout 标记都不适用；跑到 Total runtime 即算跑完，只按 断流/容量/账号/harbor错 判 API 故障。
    if arm == "plain":
        if disc>0 or eec>=PLAIN_STORM or recon>=PLAIN_STORM:
            return "RETRY", f"plain 断流/API不稳 disc={disc} eec={eec} recon={recon} (runtime={sec}s)"
        return "OK", f"reward={rw} runtime={sec}s eec={eec} recon={recon} disc={disc}"
    # ---- 跑满预算 / 解出：单次或少量断流已恢复，不算失败；只有明显风暴才重跑 ----
    if timeout_ok or (rw is not None and rw>0):
        if disc>=3 or eec>=15 or recon>=25:
            return "RETRY", f"虽收尾但断流偏重 disc={disc} eec={eec} recon={recon} (runtime={sec}s)"
        return "OK", f"reward={rw} runtime={sec}s eec={eec} disc={disc} iec={iec} cont={cont}{' timeout' if timeout_ok else ''}"
    # ---- 未收尾：断流风暴/硬断流：API 不稳，重跑 ----
    if disc>0 or eec>=EEC_STORM or recon>=RECON_STORM:
        return "RETRY", f"断流/未收尾 disc={disc} eec={eec} recon={recon} (runtime={sec}s)"
    # 到这里：无容量错、无账号问题、harbor 无 errored、无断流风暴 —— 基础设施是干净的。
    # 判断 agent 是否真的跑起来了（防"容量错没被字符串捕获的秒退"这类空跑）。
    if iec < 50 and (rw is None or rw <= 0) and not timeout_ok:
        return "RETRY", f"疑空跑/秒退 runtime={sec}s iec={iec} cont={cont}"
    # 干净地跑到（harbor agent 超时 / 解出）—— 未因 API/资源失败。
    return "OK", f"reward={rw} runtime={sec}s eec={eec} disc={disc} iec={iec} cont={cont}{' timeout' if timeout_ok else ''}"

if __name__=="__main__":
    task, arm = sys.argv[1], sys.argv[2]
    v, why = verdict(task, arm)
    print(f"{v}\t{why}")
    sys.exit({"OK":0,"RETRY":10,"RESOURCE":20,"PENDING":30}.get(v,1))
