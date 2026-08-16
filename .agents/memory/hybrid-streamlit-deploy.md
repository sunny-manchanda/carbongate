---
name: Hybrid Streamlit deploy architecture
description: How publishing works for this repo's root Streamlit app inside a pnpm-workspace artifact project, and the deploy traps already hit
---

# Hybrid Streamlit deploy architecture

**Rule:** Production runs ONLY artifact `[services.production]` processes. The root Streamlit app is the "CarbonGate" service inside the api-server artifact (`paths = ["/"]`, localPort 5000, explicit `.pythonlibs/bin/streamlit` run command, startup health `/_stcore/health`). `.replit` `[deployment]` must contain NO `run` command — only router/target/postBuild.

**Why:** Platform docs say `.replit` `deployment.run` is ignored in artifact mode, but a leftover legacy `run = ["streamlit", ...]` plus a service on the same port is at best ambiguous — keep it out. REVISED after evidence: the silent promote stalls on this project were most likely NOT config-caused; a known-good immutable image later failed to re-initialize the same way, which exonerates the workspace (see recipe below).

**How to apply — silent "Waiting for deployment to be ready" stall recipe:**
1. Build log mentions "Nix layers … uncached" → cold image pull; just retry once.
2. Warm cache → check for port/process conflicts across config layers, and that each service's health path returns 200 locally.
3. Decisive test: after a failed promote the platform auto-rolls back by re-provisioning the PREVIOUS good build's VM (its status shows "resuming", its build log gains new "Creating virtual machine…" lines). If that re-init ALSO fails ("failed to initialize due to a configuration or code error"), the workspace is exonerated — that image is immutable and predates all changes. Escalate to Replit support with deployment + build IDs and timestamps; when rollback fails the old build flips to `failed` and the live domain 404s on every path.

**Other traps:**
- `fetchDeploymentLogs` takes NUMERIC epoch-ms timestamps (`afterTimestamp: Date.parse("…Z")`); a string throws a validation error. Even called correctly it returned "No deployment logs found" for these init failures — zero runtime lines means the VM died before the app started (an app-level crash leaves a trace). Probe the live domain for current state: `/_stcore/health` (Streamlit), `/api/healthz` (api-server).
- Never remove the "Start application" workflow: without it the platform flips the project to "not deployable" (kind=api artifacts count as reusable libraries, kind=design as mockups). Re-adding it restores publishability instantly.
- Artifact schema requires `development.run` on every service; CarbonGate's dev run is an `echo` no-op because "Start application" owns dev port 5000.
- `artifact.toml` edits only via temp-file + `verifyAndReplaceArtifactToml`; validation errors are unspecific — diff against a service that already validates.
- Before suggesting publish, dry-run each service's exact production command locally on a spare port and require 200 on its configured health path.
