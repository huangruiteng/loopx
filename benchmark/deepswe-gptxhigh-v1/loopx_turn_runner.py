#!/usr/bin/env python3
"""Drive one DeepSWE task through LoopX's governed Turn loop, inside the container.

Run by LoopxCodex after the LoopX package, the Codex profile and the goal state
have been staged.  Kept as a standalone script for the same reason
native_codex_goal.py is: it must execute where the repository is, and the
repository is inside the task container.

Why this calls ``handle_turn_command`` instead of the ``loopx turn run-once``
CLI: the CLI restricts ``--codex-sandbox`` to read-only and workspace-write,
and neither can be set up inside these task images — the Linux sandbox needs
kernel features the container does not grant, and Codex responds by narrating
instead of executing (measured once: 431 assistant messages, zero command
executions, an empty patch scored 0/24).  The other two arms run Codex with
approvals and sandbox bypassed, so the LoopX arm has to as well or the three
differ in permissions as well as in looping.  Editing LoopX's argparse choices
would also have made the source tree dirty, and install_native_codex_profile
refuses an unclean source because mixing revisions invalidates a benchmark
treatment.  Building the Namespace directly avoids both problems and touches
no file in the LoopX checkout.

The loop is the point of the arm.  LoopX runs exactly one governed Turn per
call: it selects a Todo, has the host adapter invoke Codex, requires an
independent validator to prove the postcondition, and only then commits the
result and spends quota.  Multi-turn behaviour comes from calling it again --
which is precisely what the other two arms never do, since `codex exec` and the
app-server both stop as soon as the model says it is finished.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

REMOTE_DIR = Path(__file__).resolve().parent
DEFAULT_QUOTA = int(os.environ.get("MR_LOOPX_QUOTA", "4"))
DEFAULT_TURN_TIMEOUT = float(os.environ.get("MR_LOOPX_TURN_TIMEOUT", "1200"))

GOAL_ID = "deepswe-task"
AGENT_ID = "deepswe-codex"
TODO_ID = "deepswe-todo-1"


def hide_loopx_state_from_git(project: Path) -> None:
    """Keep LoopX's own files out of git's view.

    The goal document and registry have to live at paths inside the project —
    LoopX resolves ``state_file`` relative to the repo — but they are control-
    plane state, not the agent's work.  Left visible they break the run twice:
    ``git status`` never comes back clean, so the validator rejects every Turn,
    and they land in ``git diff base..HEAD``, which is exactly the patch the
    benchmark grades.

    Written to ``.git/info/exclude`` rather than ``.gitignore`` because that
    file is local to the clone and never becomes part of the diff itself.
    """
    exclude = project / ".git" / "info" / "exclude"
    if not exclude.parent.is_dir():
        return
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    additions = [p for p in (".codex/", ".loopx/") if p not in existing]
    if additions:
        with exclude.open("a", encoding="utf-8") as fh:
            fh.write("\n# LoopX control-plane state (benchmark harness)\n")
            fh.write("\n".join(additions) + "\n")


def stage_goal_state(project: Path, instruction: str) -> Path:
    """Write the goal document LoopX reads Todos from.

    The Todo, not the objective, is what LoopX plans against: it selects one per
    Turn and asks the host to advance it.  Phrasing it as staged work is what
    gives the loop somewhere to go on turn two — a Todo that one turn satisfies
    ends the goal exactly the way the Goal-API arm already ends, and the arm
    would measure nothing.
    """
    state = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        "\n".join(
            [
                "---",
                "status: active",
                "updated_at: 2026-01-01T00:00:00+00:00",
                "---",
                "",
                "# DeepSWE task",
                "",
                "## Agent Todo",
                "",
                "- [ ] [P0] Advance the task below by exactly one stage per Turn, "
                "and report which stage you completed and what remains. "
                "Stage 1: implement the target behaviour and commit. "
                "Stage 2: re-check the implementation against every requirement "
                "in the task text, fix gaps, commit. "
                "Stage 3: run the wider test suite and repair any regression. "
                "Stage 4: handle edge cases the tests do not cover.",
                f"  <!-- loopx:todo todo_id={TODO_ID} status=open "
                f"task_class=advancement_task action_kind=deepswe_task "
                f"claimed_by={AGENT_ID} priority=P0 -->",
                "",
                "## How to report each Turn",
                "",
                # gpt-5.5 reached for path_delta_mode=material_replan on a plain
                # first implementation Turn, which LoopX rejects four ways at
                # once: that mode is reserved for Turns that overturn a prior
                # assumption, and it then demands result_kind=replan_required
                # plus a goal_path_delta_v0 vision packet the model had not
                # produced.  Every Turn failed validation, so nothing committed
                # and the quota bought nothing.  Advancing a stage is routine
                # continuation, so say so explicitly rather than leaving the
                # model to pick.
                "This Todo is routine staged continuation, never a replan. In the",
                "typed result set `path_delta_mode=unchanged`, leave",
                "`agent_vision_json` empty, and give a one-line",
                "`vision_unchanged_reason` such as \"routine stage advance\".",
                "Set `delivery_batch_scale` to `implementation` when you changed",
                "source, or `test_only` when you only touched tests.",
                "Use `result_kind=validated_progress` when the stage advanced and",
                "`repair_required` when it did not.",
                "",
                "## Task",
                "",
                instruction,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return state


def stage_registry(project: Path, runtime: Path, state: Path) -> Path:
    """Write the registry LoopX plans against.

    Shape follows LoopX's own e2e fixture rather than a guess: a goal needs
    ``state_file`` to find its Todos, ``quota`` for the scheduler to spend
    against, and a ``coordination`` block with ``registered_agents`` — without
    the last one every Turn fails at planning with "quota should-run
    --agent-id requires coordination.registered_agents", before the host is
    ever invoked.

    ``write_scope`` is the repository rather than the fixture's ``docs/**``:
    the agent's whole job here is to change source.
    """
    registry = project / ".loopx" / "registry.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "deepswe-benchmark",
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state.relative_to(project)),
                        "adapter": {
                            "kind": "fixture_v0",
                            "status": "connected-delivery",
                        },
                        "quota": {"compute": 1.0, "window_hours": 24},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [AGENT_ID],
                            "agent_profiles": {
                                AGENT_ID: {
                                    "schema_version": "agent_profile_v1",
                                    "profile_role": "benchmark",
                                    "scope": "deepswe task",
                                }
                            },
                            "write_scope": ["**"],
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry


def validator_command(project: Path, base_sha: str) -> list[str]:
    """Postcondition: the Turn committed something new and left a clean tree.

    Comparing against the base commit is the whole point.  An earlier version
    only asked for a clean tree and a non-empty history, which any run
    satisfies without doing anything at all — four Turns passed validation
    while producing an empty patch.  A Turn that has not moved HEAD has not
    advanced the Todo, whatever the model reports.

    Deliberately structural, never the hidden tests: the benchmark's rules put
    verifier invocation after the run and outside the controller, so that a
    loop cannot steer on the grade.  What this proves is that the agent really
    committed work rather than declaring success over an unchanged tree.
    """
    program = (
        "import json,subprocess,sys;"
        "json.load(sys.stdin);"
        f"p={str(project)!r};b={base_sha!r};"
        "st=subprocess.run(['git','-C',p,'status','--porcelain'],"
        "capture_output=True,text=True);"
        "hd=subprocess.run(['git','-C',p,'rev-parse','HEAD'],"
        "capture_output=True,text=True);"
        "head=hd.stdout.strip();"
        "clean=st.returncode==0 and not st.stdout.strip();"
        "raise SystemExit(0 if clean and head and head!=b else 9)"
    )
    return [sys.executable, "-c", program]


def head_sha(project: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    return out.stdout.strip()


def run_turn(*, project: Path, registry: Path, runtime: Path, codex_bin: str,
             model: str, sandbox: str, turn_index: int, base_sha: str,
             ) -> dict:
    from loopx.cli_commands.turn import handle_turn_command, register_turn_commands

    # Build the Namespace from LoopX's own parser rather than by hand.  Hand-
    # writing it meant discovering missing attributes one failed Turn at a time
    # (`resume_turn_key` was the third), and every LoopX upgrade would restart
    # that game.  Parsing real argv fills every default the handler expects and
    # fails loudly here if an option is ever renamed.
    #
    # Host is generic-cli, not codex-cli.  LoopX's built-in Codex host launches
    # `codex exec --sandbox <mode>`, and both modes it permits need bubblewrap,
    # which needs unprivileged user namespaces that these containers do not
    # grant — every Turn came back with "bwrap: No permissions to create a new
    # namespace" and an empty patch.  The generic-cli seam lets the adapter
    # launch Codex with the same approvals-and-sandbox bypass the other two
    # arms use, so the loop stays LoopX's and the permissions stay identical.
    #
    # Which adapter is the only thing that differs between the Codex arm and the
    # Claude Code arm: both go through this same generic-cli seam, the same
    # validator and the same quota, and only the CLI that executes a Turn
    # changes.  Defaulting to the Codex one keeps that arm byte-identical to the
    # runs already recorded against it.
    wrapper = str(Path(__file__).resolve().parent / "codex_nosandbox_wrapper.py")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_turn_commands(sub, lambda p: p.add_argument("--format", default="json"))
    args = parser.parse_args([
        "turn", "run-once",
        "--goal-id", GOAL_ID,
        "--agent-id", AGENT_ID,
        "--turn-instance-id", f"{GOAL_ID}-turn-{turn_index}",
        # codex-cli, not generic-cli.  The generic host was an attempt to get
        # around the sandbox flag, and it cost more than it saved: it carries
        # its own scheduler contract, and eleven of sixteen turns died at
        # "LoopX Turn route is not host executable" before any model work, with
        # no route recorded to say why.  The codex host is the one that
        # demonstrably works — four turns, a 22 KB patch, f2p 31/35 — so keep it
        # and neutralise the sandbox at the binary instead, via a wrapper that
        # strips --sandbox and substitutes the approvals-and-sandbox bypass.
        "--host", "codex-cli",
        "--execution-mode", "isolated-headless",
        "--project", str(project),
        "--codex-bin", wrapper,
        # An accepted value that the wrapper then removes; LoopX only permits
        # read-only and workspace-write, and this argument has to satisfy its
        # parser rather than the container.
        "--codex-sandbox", "workspace-write",
        "--codex-model", model,
        "--validation-command-json", json.dumps(validator_command(project, base_sha)),
        "--validation-timeout-seconds", "60",
        # Without --execute LoopX plans the Turn and stops: every receipt comes
        # back ok=True with dry_run=True, the host is never invoked, and four
        # turns of nothing look exactly like four turns of success.
        "--execute",
        # Deliberately no --scan-root.  It is not "where the work is"; LoopX
        # documents it as "public files to scan for obvious private material",
        # and pointing it at the task repository made LoopX run its public
        # boundary scanner over the repository's own history.  On the OPA task
        # that produced
        #     public_boundary_violation  CHANGELOG.md:3588: private_ip
        #     public_boundary_violation  CHANGELOG.md:4859: credential
        # which sets contract health to not-ok, which makes the quota decision
        # `should_run=false / quota_skip`, which makes the route `wait`, which
        # is what "LoopX Turn route is not host executable" finally reports —
        # four layers away from the file it actually objected to.
        #
        # It also explains the shape of the failure: any repository whose text
        # happens to contain something resembling an IP or a credential is
        # rejected before a model runs, which is most of them, while the odd
        # clean repository sails through and looks like proof the setup works.
        # `turn plan` kept answering ready_for_host because the plan probe never
        # passed --scan-root and so scanned LoopX's own directory instead.
        #
        # The default is LoopX's own public root, which is what the scanner is
        # for.  The task repository reaches the Turn through --project.
        "--no-global-sync",
        "--timeout-seconds", str(DEFAULT_TURN_TIMEOUT),
        "--format", "json",
    ])

    # PrintPayload is (payload, fmt, renderer) -> None and FormatSelector is
    # (...) -> str; passing single-argument lambdas made every Turn die with a
    # TypeError before any model work, which the loop then dutifully repeated
    # four times.  Capture the payload instead of printing it, so the receipt
    # survives whatever the CLI would have rendered.
    captured: list[dict] = []

    def _print_payload(payload, fmt=None, renderer=None):  # noqa: ANN001
        if isinstance(payload, dict):
            captured.append(payload)

    # `run-once` decided `route: wait`, which `_typed_route` returns only when
    # the envelope says should_run is false.  The decision behind it blamed
    # "status or contract health is not ok" while reporting the quota itself as
    # eligible with zero slots spent — so the gate is `goal_status_health_ok`,
    # which reads `contract` and `global_registry` straight off the status
    # payload.  `turn plan`, run first in this same process, said
    # ready_for_host, so the two calls are seeing different status.  Spy on
    # collect_status for both and record what differs; the two subcommands do
    # not take the same options (`--scan-root` differs, `--no-global-sync` is
    # run-once only), and that is the remaining candidate.
    from loopx.cli_commands import turn as _turn_mod
    _statuses: list[dict] = []
    _original_collect = _turn_mod.collect_status

    def _spy_collect(*a, **kw):  # noqa: ANN002, ANN003
        result = _original_collect(*a, **kw)
        if isinstance(result, dict):
            contract = (result.get("contract")
                        if isinstance(result.get("contract"), dict) else {})
            registry = (result.get("global_registry")
                        if isinstance(result.get("global_registry"), dict) else {})
            _statuses.append({
                "scan_roots": [str(x) for x in (kw.get("scan_roots") or [])],
                "status_ok": result.get("ok"),
                "contract_ok": contract.get("ok"),
                "has_error_diagnostics": "error_diagnostics" in contract,
                "contract_errors": json.dumps(
                    contract.get("error_diagnostics"), ensure_ascii=False
                )[:600],
                "global_registry_ok": registry.get("ok"),
                "global_registry_error": json.dumps(
                    {k: v for k, v in registry.items() if k != "goals"},
                    ensure_ascii=False,
                )[:400],
            })
        return result

    _turn_mod.collect_status = _spy_collect

    # Plan first, and keep the result whatever happens next.  When the planner
    # declines to call the host, `run-once` raises "LoopX Turn route is not
    # host executable" and the receipt it leaves carries only ok and effects —
    # the route, the selected Todo and the scheduler context all vanish.  Eleven
    # turns failed exactly that way, and reproducing the call on the host proved
    # only that the *arguments* were fine, so every explanation stayed a guess.
    # `turn plan` runs the same decision without invoking a host or spending
    # quota, so recording it costs nothing and makes the next failure legible.
    plan_payload: dict = {}
    try:
        # Parse `turn plan` argv rather than copying the run-once Namespace and
        # renaming the subcommand.  The two subparsers do not define the same
        # options, so the copy was missing `include_transaction_detail` and the
        # probe failed on its own AttributeError — producing five nulls that
        # said nothing about the route it was meant to explain.
        plan_parser = argparse.ArgumentParser()
        plan_sub = plan_parser.add_subparsers(dest="command")
        register_turn_commands(
            plan_sub, lambda p: p.add_argument("--format", default="json")
        )
        plan_args = plan_parser.parse_args([
            "turn", "plan",
            "--goal-id", GOAL_ID,
            "--agent-id", AGENT_ID,
            "--host", "codex-cli",
            "--execution-mode", "isolated-headless",
            "--format", "json",
        ])
        with redirect_stdout(io.StringIO()):
            handle_turn_command(
                plan_args,
                registry_path=registry,
                runtime_root_arg=str(runtime),
                output_format=lambda *_a, **_k: "json",
                print_payload=_print_payload,
            )
        if captured:
            p = captured.pop()
            route = p.get("route") or {}
            ctx = p.get("scheduler_execution_context") or {}
            plan_payload = {
                "route_kind": route.get("kind"),
                "would_invoke_host": route.get("would_invoke_host"),
                "selected_todo": (route.get("selected_todo") or {}).get("todo_id"),
                "context_valid": ctx.get("valid"),
                "context_errors": ctx.get("errors"),
            }
            # Keep the raw shape when the expected keys are absent.  Reusing the
            # run-once Namespace for `plan` produced a payload without `route`
            # at all, and five nulls said only "not what I expected" — which is
            # the same dead end as having no diagnostics.
            if route or ctx:
                pass
            else:
                plan_payload["raw_keys"] = sorted(p)
                plan_payload["raw"] = json.dumps(p, ensure_ascii=False)[:1200]
    except Exception as exc:
        plan_payload = {"plan_error": f"{type(exc).__name__}: {exc}"}

    # Record the plan `run-once` builds and then rejects.  "LoopX Turn route is
    # not host executable" is raised by build_loopx_turn_host_request after
    # reading route.would_invoke_host off a payload run-once assembled moments
    # earlier and never prints, so the one run whose route matters is the one
    # nobody can see — and `turn plan`, which does print it, keeps answering
    # ready_for_host.  Both go through build_loopx_turn_plan, so wrapping it
    # captures run-once's own payload, including the `session` block that only
    # run-once populates.  Reproducing this on the host was not possible: there
    # both subcommands succeed, so the difference lives in the container.
    from loopx.cli_commands import turn as _turn_mod
    _built: list[dict] = []
    _original_build = _turn_mod.build_loopx_turn_plan

    def _spy_build(*a, **kw):  # noqa: ANN002, ANN003
        result = _original_build(*a, **kw)
        _built.append({"session_binding": kw.get("session_binding"),
                       "payload": result})
        return result

    _turn_mod.build_loopx_turn_plan = _spy_build

    # The route came back `wait`, which `_typed_route` only returns when the
    # envelope says should_run is false and a quiet no-op is allowed — a
    # scheduling verdict, not a contract error.  `turn plan`, run moments
    # earlier in this same process against this same registry, said
    # ready_for_host.  So capture the decision the envelope is projected from:
    # should_run is set by build_live_quota_should_run_decision, and its
    # rationale is the only thing that can say why the two disagree.
    _decisions: list[dict] = []
    _original_decision = _turn_mod.build_live_quota_should_run_decision

    def _spy_decision(*a, **kw):  # noqa: ANN002, ANN003
        result = _original_decision(*a, **kw)
        if isinstance(result, dict):
            _decisions.append(result)
        return result

    _turn_mod.build_live_quota_should_run_decision = _spy_decision

    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            code = handle_turn_command(
                args,
                registry_path=registry,
                runtime_root_arg=str(runtime),
                output_format=lambda *_a, **_k: "json",
                print_payload=_print_payload,
            )
    finally:
        _turn_mod.build_loopx_turn_plan = _original_build
        _turn_mod.build_live_quota_should_run_decision = _original_decision
        _turn_mod.collect_status = _original_collect
    built_payload: dict = {}
    if _built:
        record = _built[-1]
        built = record["payload"]
        route = built.get("route") if isinstance(built.get("route"), dict) else {}
        session = built.get("session") if isinstance(built.get("session"), dict) else {}
        ctx = built.get("scheduler_execution_context")
        ctx = ctx if isinstance(ctx, dict) else {}
        transaction = (built.get("transaction")
                       if isinstance(built.get("transaction"), dict) else {})
        built_payload = {
            "route_kind": route.get("kind"),
            "would_invoke_host": route.get("would_invoke_host"),
            "route_reasons": route.get("reasons") or route.get("errors"),
            "session_action": session.get("action"),
            "session_binding_status": session.get("binding_status"),
            "session_binding_arg": record["session_binding"],
            "context_valid": ctx.get("valid"),
            "context_errors": ctx.get("errors"),
            "turn_key": transaction.get("turn_key"),
            "builds": len(_built),
        }
        envelope = (built.get("turn_envelope")
                    if isinstance(built.get("turn_envelope"), dict) else {})
        action = (envelope.get("action")
                  if isinstance(envelope.get("action"), dict) else {})
        built_payload["envelope"] = {
            "should_run": envelope.get("should_run"),
            "effective_action": envelope.get("effective_action"),
            "delivery_allowed": action.get("delivery_allowed"),
            "must_attempt": action.get("must_attempt"),
            "quiet_noop_allowed": action.get("quiet_noop_allowed"),
        }
    if _decisions:
        decision = _decisions[-1]
        built_payload["decision"] = {
            key: decision.get(key)
            for key in ("should_run", "effective_action", "reason", "reasons",
                        "blocked_reason", "quota", "quota_state", "cadence",
                        "schedule", "gates")
            if key in decision
        }
        built_payload["decision_keys"] = sorted(decision)[:40]
        built_payload["decisions"] = len(_decisions)
    # Two entries: the `plan` probe's status, then run-once's.  Whatever differs
    # between them is what flipped goal_status_health_ok.
    built_payload["statuses"] = _statuses[:4]
    if captured:
        payload = captured[-1]
    else:
        raw = buffer.getvalue().strip()
        try:
            payload = json.loads(raw.splitlines()[-1]) if raw else {}
        except Exception:
            payload = {"unparsed": raw[-2000:]}
    payload["_exit_code"] = code
    payload["_plan"] = plan_payload
    payload["_built"] = built_payload
    # Carry the wrapper's log into the receipt.  LoopX reports a failed host as
    # `codex_cli_exit_nonzero` and keeps nothing else, and the container that
    # holds the log is deleted as soon as the task ends, so the receipt is the
    # only artifact that outlives the evidence.
    codex_log = Path(
        os.environ.get("MR_LOOPX_CODEX_LOG", "/tmp/loopx-goal/codex-wrapper.log")
    )
    try:
        payload["_codex_log"] = codex_log.read_text(encoding="utf-8")[-4000:]
        codex_log.unlink()
    except OSError:
        payload["_codex_log"] = None
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--adapter", default="loopx_codex_adapter.py",
                        help="generic-cli host adapter that executes one Turn "
                             "(loopx_codex_adapter.py | loopx_claude_adapter.py)")
    parser.add_argument("--model", required=True)
    parser.add_argument("--sandbox", default="danger-full-access")
    parser.add_argument("--quota", type=int, default=DEFAULT_QUOTA)
    args = parser.parse_args()

    project = Path(args.project).resolve()
    runtime = Path(args.runtime_root)
    runtime.mkdir(parents=True, exist_ok=True)
    instruction = Path(args.task_file).read_text(encoding="utf-8").strip()

    # The host adapter needs the task text too, and cannot get it from the Turn
    # envelope: the envelope carries only the selected Todo, and LoopX compacts
    # that to an 8 KB budget, so the staged Todo's wording survives truncated
    # ("Advance the task below by exactly one stage per Turn, and report which
    # s...") while the `## Task` section of the goal document is never included
    # at all.  An adapter working from the envelope alone therefore sees a
    # staging meta-instruction with no target behaviour attached, and a
    # well-behaved model correctly refuses to invent one — four Turns of
    # `validation_failed` with an empty patch, which reads like a model that
    # could not do the work rather than a prompt that never described it.
    # Handing the adapter the same file the goal document was built from keeps
    # one source of truth for the task text.
    os.environ["MR_LOOPX_TASK_FILE"] = str(Path(args.task_file).resolve())

    hide_loopx_state_from_git(project)
    state = stage_goal_state(project, instruction)
    registry = stage_registry(project, runtime, state)
    base_sha = head_sha(project)

    receipts = []
    for turn_index in range(1, args.quota + 1):
        try:
            payload = run_turn(
                project=project, registry=registry, runtime=runtime,
                codex_bin=args.codex_bin, model=args.model,
                sandbox=args.sandbox, turn_index=turn_index, base_sha=base_sha,

            )
        except Exception as exc:  # keep the receipt; a dead turn is evidence too
            payload = {"error": f"{type(exc).__name__}: {exc}"}
        receipts.append(payload)
        # A Turn that never reached the host is a defect in this runner, not a
        # result: repeating it burns the whole quota on the same traceback, as
        # four identical TypeErrors once did.  Stop and let the receipt show why.
        if "error" in payload:
            break
        if payload.get("dry_run"):
            payload["_fatal"] = "dry_run: --execute was not honoured"
            break
        status = str(payload.get("status") or payload.get("result_kind") or "")
        # Stop early only when LoopX says the work is settled; a failed or
        # repair-required Turn is exactly the case the next Turn exists for.
        if status in {"completed", "goal_complete", "done"}:
            break

    print(json.dumps({
        "schema": "deepswe_loopx_turn_log_v0",
        "quota": args.quota,
        "turns_run": len(receipts),
        "receipts": receipts,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
