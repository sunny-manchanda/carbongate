---
name: Streamlit tabs single-pass gotcha
description: Why content gated on session state set inside an st.tabs panel stays locked until an unrelated rerun, and the ordering fix.
---

# Streamlit st.tabs render in ONE script pass

**Rule:** When tab A produces state (e.g. a file upload stored in
`st.session_state`) that gates tabs B–E, compute the gate/pipeline *after*
tab A's render call in script order — never at the top of the script.

**Why:** `st.tabs` renders every panel in the same script run; clicking a tab is
purely client-side and does NOT rerun the script. If the gate is evaluated
before tab A processes the upload, the other tabs render locked in that pass,
and the user who clicks over to them sees stale locked panels until some other
widget interaction forces a rerun.

**How to apply:** Script order = render order. Put `st.session_state` reads and
derived computation between the producing tab's `with tabs[0]:` block and the
consuming tabs' blocks. Alternative (`st.rerun()` after storing the upload)
works but wastes a full rerun and needs loop guards.
