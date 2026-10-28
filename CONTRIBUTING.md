# Contributing

Use Python 3.11+ and the exact hashed dependency lock. Run the README offline
command from a fresh temporary checkout as well as the supported Linux host.
Retain baseline regressions and all failures; do not weaken assertions, fabricate
credentials or skip required namespace checks to obtain a green result.

Live tests are explicit parent-owned qualification. They require the pinned CLI,
existing authentication, namespaces and bounded disposable fixtures. They must
not run as paid model jobs in pull-request CI. Capture actual role/thread/turn,
model/settings, source, command exits and evidence identities; exclude secrets
and private reasoning. Follow the shipped reference-led source policy.

Keep patches narrow. Native JSON-RPC and exec JSONL are separate protocols.
Changes to human decisions, question recovery or legacy lifecycle boundaries
need demonstrated scope and independent review. Fresh final review uses frozen
source and collector evidence, then stops at AWAITING_HUMAN.
