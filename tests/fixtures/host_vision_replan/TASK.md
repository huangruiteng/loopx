# Verified local artifact manifest

The first stage inventoried the files under `assets/`; `manifest.json` currently
contains only their names. The finished deliverable must also prove integrity.

Replace the inventory with a JSON object mapping each project-relative file path to an
object containing `size` (bytes) and `sha256` (lowercase hexadecimal). Include
every regular file recursively under `assets/`, no others. Add
`verify_manifest.py`, using only the Python standard library, which validates
the current assets against that manifest. It must exit zero for an exact match
and nonzero for a changed, missing, or additional file. Verification is read-only:
never regenerate the manifest or change assets to conceal a mismatch. Include
tests and a concise README explaining generation and verification.

Do not alter this acceptance specification. Work is local to this disposable
project; no network delivery, deployment, package installation or publication
is requested.
