# Co-located Packages

This directory contains independently installable distributions developed next
to LoopX. Each child owns its packaging metadata, dependencies, and release
lifecycle; it is not included in the LoopX wheel merely because it is tracked
in this repository.

LoopX-owned source remains under `loopx/`:

- `loopx/capabilities/` owns caller-facing capability contracts and built-in
  implementations;
- `loopx/extensions/` owns extension lifecycle machinery and providers bundled
  in the LoopX wheel.

Create a standalone extension package with:

```bash
loopx extension init <extension-id> --execute
```

The default destination is `packages/<extension-id>/`.
