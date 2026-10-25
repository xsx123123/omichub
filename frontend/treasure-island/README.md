# Platform presentation overlays

The child repository archives the platform adapter under `archive/island` and
maintains shared React UI under `src`. `scripts/build-treasure-island.mjs` stages
the current `src`, `shared`, and archived adapter in a temporary directory, then
overlays this directory's `index.tsx` and `FullPresentation.tsx` into `src/island`.
Their relative imports resolve in that staging tree. The archive is not edited.

These files only present Vue-owned state and emit the existing typed callbacks.
Authentication, projects, sessions, streaming, permissions, and model selection
remain owned by `TreasureResearchWorkbench.vue`. Child SPA task queues, local
accounts and history are not automatically integrated into the platform.

Shared styles and components must be changed in the child repository. Run
`bash scripts/poc/check-treasure-island.sh` from the repository root to build the
actual artifact and test the Vue/React boundary. Set the optional browser paths
documented in that script for Chromium screenshots and interaction checks.
