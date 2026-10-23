# Environment and host qualification

The preserved October 21 exec setup and its private `runtime.lock.json` are
historical observations. Their `app_server: not used` field describes that cutoff,
not the selected native candidate. Authentication contents and personal runtime
locations stay outside the curated export.

Stabilization targets Linux x86_64, Python 3.11+, working unprivileged namespaces,
bubblewrap and tmux. Native transport alone depends on pinned websockets 17.1.
The local compatibility input is CLI 0.163.0 and its inspected schema; the binary
and companion hashes are checked before launch. See NATIVE_PROFILE.md. Existing
local authenticated access is reused without a new provider or billing route.

Run `python3 -B tools/collector_diagnostics.py --output /absolute/private/checks`
to capture platform/kernel/Python/bwrap, available policy and denial diagnostics,
and a probe through the unchanged production collector. Its user/mount/PID/network
namespaces must differ from the caller and its network must have only loopback.
A passing probe alone does not certify the suite. Unsupported namespaces are a
failed prerequisite; required tests must not be skipped or confinement weakened.

CI requests explicit `ubuntu-24.04`, installs distro Python/venv/bubblewrap and
uploads diagnostics even when the probe fails. The earlier run 39927083322 failed
`RTM_NEWADDR` after installing bubblewrap; the full suite did not run. The cause
was not established. New CI results belong in the parent source-bound receipt,
not inferences about AppArmor from an error string.

A dedicated Linux VM/self-hosted runner is the fallback if the hosted image
cannot satisfy isolation. Provision it without project credentials or model
authentication: install Python 3.11+, bubblewrap and Git; create a fresh unprivileged
runner account; install the pinned lock in a private venv outside checkout; run
this exact diagnostic and then the complete offline suite. Do not enable a runner
until both succeed. No runner is provisioned or registered by these instructions.
Do not disable host AppArmor/seccomp globally or remove namespace flags.

Only the trusted parent sees controller state, credentials, evidence and vault.
Role mounts exclude those surfaces and raw backend endpoints. Trusted collector
checks have no authentication or network. This boundary does not defend against
an unrestricted host administrator. Terminal qualification does not establish
VS Code sidebar or physical-device support.
