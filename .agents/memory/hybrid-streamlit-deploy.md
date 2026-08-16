---
name: Hybrid Streamlit deploy architecture
description: How publishing works for this repo's root Streamlit app inside a pnpm-workspace artifact project, and the deploy traps already hit
---

# Hybrid Streamlit deploy architecture

**Rule:** Production runs ONLY artifact `[services.production]` processes. The root Streamlit app is the "CarbonGate" service inside the api-server artifact (`paths = ["/"]`, localPort 5000, explicit `.pythonlibs/bin/streamlit` run command, startup health `/_stcore/health`). `.replit` `[deployment]` must contain NO `run` command — only router/target/postBuild.

**Why:** On the vm target a legacy `.replit` run command executes ALONGSIDE artifact services. With both a legacy `run = ["streamlit", ...]` and the CarbonGate service binding port 5000, the loser exits and the VM hangs at "Waiting for deployment to be ready" — a silent promote timeout with zero runtime logs. An earlier belief that the legacy run is "completely ignored" was unsafe; treat it as a live collision hazard. A separate earlier failure with the same silent signature was a cold image pull (build log said nix layers uncached) — that one just warrants a retry.

**How to apply:**
- Debugging a silent promote timeout here: first check the build log for uncached nix layers (cold pull → retry once); if the cache was warm, hunt for port/process conflicts between `.replit` [deployment] and artifact services.
- Never remove the "Start application" workflow: without it the platform flips the project to "not deployable" (kind=api artifacts count as reusable libraries, kind=design as mockups). Re-adding it restores publishability instantly.
- Artifact schema requires `development.run` on every service; CarbonGate's dev run is an `echo` no-op because "Start application" owns dev port 5000. Don't give the managed service a real dev command.
- `artifact.toml` edits only via temp-file + `verifyAndReplaceArtifactToml`; validation errors are unspecific — diff against a service that already validates.
- `fetchDeploymentLogs` returns nothing for this project even while prod demonstrably serves; absence of logs proves nothing. Probe the live domain instead: `/_stcore/health` (Streamlit) and `/api/healthz` (api-server).
- Before suggesting publish, dry-run each service's exact production command locally on a spare port and require 200 on its configured health path.
