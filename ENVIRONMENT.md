> Historical detail below retains its original source/cutoff. For the30 October 2026 candidate, repository identity, qualification results and open gates, use [current status](docs/STATUS.md). Earlier counts and pending labels do not supersede that source-bound record.

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
uploads diagnostics even when the probe fails. Earlier `RTM_NEWADDR` failures
did not run the suite. Run 39973611264 subsequently captured exact AppArmor
`unprivileged_userns` capability denials for `setpcap` and `net_admin`.

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

## Disposable CI prerequisites

The workflow loads `examples/ci/bwrap.apparmor` only on this repository's
ephemeral GitHub-hosted Ubuntu runner and removes it after the job. The two
named profiles allow bwrap to construct its namespaces, then stack a capability
denial onto executed children. No unconfined profile, sysctl change, disabled
AppArmor service, setuid executable or collector-flag change is used. This is
an environment prerequisite, not a runtime permission for roles or the desktop.

The policy uses AppArmor 4.0 ABI and documented profile stacking, following
[Canonical's purpose-built bwrap guidance](https://discourse.ubuntu.com/t/understanding-apparmor-user-namespace-restriction/58007)
and the [AppArmor 4.0.1 example](https://gitlab.com/apparmor/apparmor/-/blob/v4.0.1/profiles/apparmor/profiles/extras/bwrap-userns-restrict).
The probe checks namespace separation and the actual child's profile and
zero effective capabilities before the required full suite. Failed policy
installation, missing child policy, failed probe or skipped suite stays a
failure with diagnostic artifacts. Do not install this policy on Mani's daily
workstation or treat CI as native model qualification.

The first policy-qualified run (39974469228) cleared the kernel denials but
reached a second prerequisite: `execvp python3: No such file or directory`.
The collector's existing `/lib64 -> usr/lib` mapping expects the ELF loader at
`/usr/lib/ld-linux-x86-64.so.2`; Ubuntu keeps it in `x86_64-linux-gnu` instead.
CI verifies Python's actual ELF interpreter and resolved loader, creates only
that missing alias on the disposable runner, records it, and removes its own
exact alias at cleanup. Conflicting paths reject. The collector and its
mount/namespace arguments remain unchanged. Ubuntu support includes this
declared prerequisite. Run 39974943718 verified the actual interpreter/alias,
child policy, all310 tests and cleanup; exact source/commit receipts belong
in the parent evidence record. No VM runner is provisioned by this guide.
# CI suite topology

The Ubuntu CI profile allows the collector launcher to build its sandbox and retains an additional child profile denying capabilities. Four integration tests themselves launch collectors and cannot be repeated inside that child. CI runs the full runtime suite on the host, then repeats the compatible 339 cases inside the unchanged collector. `tests/collector_runtime.py` lists the four host-only cases explicitly and rejects discovery drift; they remain required and executed in the host suite. No unittest skip, profile relaxation or global user-namespace change is used. The 12 benchmark-accounting tests also run at both levels.

The archived V3 full 343 collector pass on a different supported host remains separate evidence. `tools/run_offline_collector.py --suite runtime` retains the full-suite route for hosts supporting nested collectors; `--suite runtime-unit` names the Ubuntu CI repeat and must not be presented as a full-suite result.

