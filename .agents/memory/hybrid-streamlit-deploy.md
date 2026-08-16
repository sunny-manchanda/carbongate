---
name: Hybrid Streamlit deploy architecture
description: How publishing works for this repo's root Streamlit app inside a pnpm-workspace artifact project, and the traps hit while fixing it
---

# Hybrid Streamlit deploy architecture

**Rule:** Production publishing runs ONLY each artifact's `[services.production]` from `artifact.toml`. The root `.replit` `[deployment] run` never executes in artifact mode. The root Streamlit app is deployed as an extra service ("CarbonGate") inside the api-server artifact: `paths = ["/"]`, localPort 5000, run via explicit `.pythonlibs/bin/streamlit` path (avoids PATH assumptions), startup health check `/_stcore/health`.

**Why:** A publish once went "green" while the live site 404'd on `/` — only the api-server had a production service, so Streamlit never ran in prod. Its `/api/healthz` passing was the only readiness gate.

**How to apply:**
- Never remove the legacy "Start application" workflow: without it the platform flips the project to "not deployable" (kind=api artifacts count as reusable libraries, kind=design as mockups — neither is an app). Deployability restores the moment the workflow is re-added.
- Artifact schema requires `development.run` on every service. CarbonGate's dev run is an `echo` no-op; "Start application" owns dev on port 5000. Don't give the managed service a real dev command or the two will fight over the port.
- `artifact.toml` edits only via the temp-file + `verifyAndReplaceArtifactToml` flow; validation errors are unspecific — diff against a service that validates.
- A promote failure whose build log ends silently at "Waiting for deployment to be ready" with zero runtime logs is likely a readiness timeout during a cold image pull (check for "Nix layers ... uncached" in the build log) — retry once before code archaeology.
- `fetchDeploymentLogs` can return nothing for this project even while prod demonstrably serves; absence of prod logs proves nothing. Probe the live domain instead: `/_stcore/health` (Streamlit up?) and `/api/healthz` (api-server up?).
- If a future publish fails with a port-5000 collision signature, the fix is removing `run` from `.replit` `[deployment]` — but only then; it may be bound to the publish UI's run field.
