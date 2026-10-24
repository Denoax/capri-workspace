# Path to a usable alpha

CAPRI is an experimental three-role native Codex controller. Updating `main` publishes the source revision inside the repository; it does not accept the preserved candidate, start the stopped runtime or qualify a release.

| Gate | Current evidence | Remaining work |
| --- | --- | --- |
| Deterministic controller correctness | V3 records 343 host and 343 isolated-collector tests, no skips. New commit CI must independently verify the exported tree. | Keep required tests and isolation checks green on the exact shipped commit. |
| Stopped compaction accounting | Pure inspection, typed fence/preparation support and synthetic atomicity/identity tests exist. Actual fence has not executed. | Use the supported source-bound route on the user's installation after integration is concrete. |
| Fresh native launch | V3 intentionally has no launch handler for the new prepared condition. | Connect the checked preparation to existing startup admission without old-intent replay or weaker guards. |
| Context and recovery | Prior run produced a task and sealed source; compaction started but lacked its completion lifecycle before timeout. | Actual completion, reread, replacement, controller restart and negative controls on the final profile. |
| Measured value | A versioned benchmark protocol and receipt analyzer exist. | Native comparison, full usage coverage and representative task outcomes. Savings and superiority remain unknown. |
| First-run usability | Offline setup is documented; qualified native CLI is pinned to 0.163.0. | Test a clean supported Linux setup with an owned disposable repository and make one supported start/check/status/stop route clear. |
| Final review | The sole fresh qualification Reviewer and same-Thinker report remain unused. | Run them on the final frozen candidate/evidence after qualification and evaluation. |
| Release packaging | Repository remains private; code and character-art licensing are unresolved. | Choose an explicit code license and resolve redistribution of shipped assets before a public release. |

For the first alpha, retain exactly three visible native sessions, the same requested model, one writer and the explicit human acceptance boundary. Keep optional model routing, broader client support and production automation on the roadmap. Do not restore a legacy background-exec route to bypass native qualification.

The next implementation priority is the fresh disposable native launch route, followed by useful measurement. Avoid adding additional recovery wrappers without a demonstrated case, or optimizing byte counts while original requirements become unavailable. A smaller packet is useful only if behavior and trace-backed coverage remain sound.
