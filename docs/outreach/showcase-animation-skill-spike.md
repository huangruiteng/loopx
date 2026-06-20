# Showcase Animation Skill Spike

This note records the first public-safe tool choice for turning the showcase
catalog into animated outreach assets. It is intentionally a spike, not a
runtime dependency.

## Goal

Create a 20-30 second animated demo that explains Goal Harness through public
showcases:

- the 0617 user-gate case;
- the sanitized 0619 multi-agent workflow;
- the repo-scale self-iteration efficiency case;
- the creator-operator synthetic case.

The input must be `docs/showcases/showcase-catalog.json` plus public assets.
The animation path must not read live registry state, local status exports,
private chats, raw benchmark traces, internal project names, or user-specific
active state.

## Recommended Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Video generation | Remotion Agent Skills | Remotion is React-based, works naturally with data-driven storyboards, and maintains Agent Skills for Codex, Claude Code, Cursor, and similar coding agents. |
| HTML-to-video fallback | HyperFrames | HyperFrames turns HTML/CSS/JS compositions into deterministic MP4, so it is a good fallback if the existing frontstage page becomes the source composition. |
| In-page motion | Motion for React | Motion is better for the dashboard/frontstage itself: subtle case-card motion, timeline transitions, and interactive state changes. |
| Micro loops | Lottie | Lottie is useful later for small reusable icons or loading loops, not for the first full showcase video. |

## First Experiment

Install or read the Remotion skill in an isolated worktree, then generate a
minimal video project under an ignored scratch directory or a future
`examples/showcase-video/` path only after the output shape is clear.

The first video should have four scenes:

1. **Gate appears**: a user decision blocks one lane, but stays visible.
2. **Safe side path moves**: a claimed side-agent todo advances with evidence.
3. **Run history accumulates**: validated writes make the next turn recoverable.
4. **Async agent team**: primary and side agents keep working across turns while
   the human keeps judgment.

Success means:

- an MP4 or storyboard preview can be produced from public catalog data;
- the README/Pages/frontstage can link to the artifact without private context;
- the implementation adds a boundary smoke or scripted scan proving the public
  video path does not consume local live status.

## Storyboard Artifact

The first public-safe storyboard artifact is
[`docs/showcases/showcase-animation-storyboard.json`](../showcases/showcase-animation-storyboard.json).
It is not the final MP4; it is the compact contract a Remotion or HyperFrames
experiment can render without reading live registry state.

The storyboard keeps the video deliberately short:

- one opening control-plane frame;
- one beat for the 0617 user gate and safe side lane;
- one beat for the sanitized 0619 multi-agent workflow;
- one beat for the repo-scale self-iteration efficiency case;
- one beat for the creator-operator synthetic case;
- one closing frame that says the public demo reads the showcase catalog, not
  private control-plane state.

## Validation

Run `python3 examples/showcase-animation-source-boundary-smoke.py` before
publishing any animation artifact. The smoke keeps the input contract narrow:
`docs/showcases/showcase-catalog.json` plus public assets are allowed; live
registry state, local status exports, user-specific active state, private
chats, internal project names, and raw benchmark traces are not animation
sources.

## Decision Boundary

Do not install animation tooling into the core package or dashboard dependency
tree until the spike proves a repeatable output. For now, this belongs to the
outreach/showcase lane.

Avoid claims like "AI made this overnight" unless the showcase evidence model
already supports the time comparison. The video should explain the operating
model shift:

> From AI assist to async agent work.
>
> Humans set gates, scope, and evidence; agent teams keep safe lanes moving
> across turns and off-hours.

## References

- [Remotion Agent Skills](https://www.remotion.dev/docs/ai/skills)
- [HyperFrames](https://github.com/heygen-com/hyperframes)
- [Motion for React](https://motion.dev/docs/react)
- [Text-to-lottie](https://github.com/diffusionstudio/lottie)
