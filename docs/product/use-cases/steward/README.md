# Steward: An Owner Sentence Becomes A Confirmed Team

Status: qualification case. It records what the local steward journey proves on
the workspace today, which beats are still unproven, and how to reproduce both.
It is product guidance, not a new capability, contract or scheduler.

The case is grounded in one deterministic browser scenario
(`examples/personal-workspace-browser/steward-journey.mjs`) that runs on synthetic
data. The fixture substitutes the agent turn; everything the case describes is a
fact the workspace surfaces render, not a claim about a live Goal.

## When This Case Applies

- an owner wants work to start from one sentence instead of a filled-in form;
- the work needs more than one Agent or more than one lane, so staffing is
  itself part of the answer;
- the owner wants to keep confirming, correcting and reading results in one
  place instead of relaying between Agent conversations.

## The Journey

| Beat | What the owner does | What the workspace shows | State |
| --- | --- | --- | --- |
| 1 | Looks at the first screen | Goal board lanes (needs you / running / observing / scheduled), each Goal card naming its Agent and its next sentence | Proven |
| 2 | Asks the steward in the Goal conversation | The ask becomes an accepted Turn and the admitted team plan card lands in the same conversation | Proven |
| 3 | Reads the card | Per lane: the Agent, the first bounded Todo with priority and action kind, the acceptance signal, and an explicitly unstaffed lane that keeps the work it did not staff; the quota envelope and stop condition; a statement that confirming is what creates the lanes | Proven |
| 4 | Confirms | Exactly one apply and one durable write; the card reports that LoopX state will refresh | Proven, but see gap 2 |
| 5 | Checks who can actually work | — | Gap 3 |
| 6 | Corrects or pauses one lane | — | Gap 4 |
| 7 | Waits for a lane to fail and asks who fixes it / judges completion | — | Gaps 5, 6 |

Beats 5–7 are recorded by the scenario as typed gaps with the probe that looked
for them. They are not "not implemented here" hand-waving: the scenario names
the selectors and phrases it searched for and what it found instead.

## Patterns

1. **Ask for an outcome, not an org chart.** One sentence with the outcome and
   the constraint produces a plan card; naming Agents before the outcome turns
   coordination into the owner's job.
2. **Read four facts before confirming.** Agent, first bounded Todo, acceptance
   signal and staffing gap. A card that cannot show a gap is not yet reviewable.
3. **Treat the gap lane as information, not failure.** An unstaffed lane keeps
   the work it could not staff and names the reason, so the owner can decide to
   drop it, staff it, or accept partial delivery.
4. **Confirmation is a durable write.** Confirming sends exactly one apply and
   performs one durable write; the surface must not claim a lane exists before
   that write, and must say what the write produced afterwards.
5. **Judge delivery by the returned result, not by the conversation.** A reply
   or a message is not a completed lane. Until gap 6 closes, treat the
   conversation as the request channel and the Goal's own state as the truth.
6. **Correct in the conversation the work came from.** Steering an active run is
   supported today; correcting a confirmed lane commitment is not yet, so avoid
   confirming a plan whose lanes may need to be withdrawn.

## Reproduce

```sh
# development surfaces
LOOPX_PERSONAL_WORKSPACE_SCENARIO=steward-journey \
  node examples/personal-workspace-browser-smoke.mjs

# packaged workspace bundle
LOOPX_PERSONAL_WORKSPACE_PACKAGED=1 \
LOOPX_PERSONAL_WORKSPACE_SCENARIO=steward-journey \
  node examples/personal-workspace-browser-smoke.mjs
```

The run writes `steward-journey-report.json` (beats, gaps, probe evidence) and
per-beat screenshots under `output/playwright/personal-workspace/`, which is
gitignored. No live Goal, Agent, credential or local path is read or captured.

## Recorded Gaps And Owners

| # | Gap | Evidence the scenario recorded | Owner surface |
| --- | --- | --- | --- |
| 1 | The steward's bounded prompt set (`找下一步` / `看阻塞` / `查证据`) is defined in the client model but not reachable from the conversation | probe: no steward-prompt element, no prompt phrases before the owner types | workspace composer |
| 2 | A confirmed plan does not distinguish committed / partial / all-gap / stale / rejected per lane | probe: the only outcome sentence is the generic applied notice | steward plan commit (roadmap R1 remainder) |
| 3 | No per-lane readiness ladder (registered → bound → launchable → executing) | probe: no lane-readiness element or phrase | steward readiness (roadmap R2 / audit F6) |
| 4 | No lane-level correction (pause or supersede a confirmed commitment) | probe: no lane-correction element; only run steering exists | shared alignment (roadmap R4) |
| 5 | A failed lane does not name its blocker owner and next step | probe: no lane-blocker element or phrase | recovery/continuation (roadmap R3) |
| 6 | Completion is not judged by the lane's returned result | probe: no lane-return element or phrase | return delivery (roadmap R3) |

## What This Case Does Not Claim

- It does not qualify a live steward conversation: the fixture substitutes the
  agent turn, so the model/runtime behind the intake stays untested here.
- It does not qualify Lark audiences or any cloud/remote worker.
- It does not turn a passing smoke into product acceptance for a Goal whose
  plan was confirmed with real consequences.
