# Disposable CI namespace prerequisite

The Ubuntu 24.04 hosted runner for run 39973611264 entered AppArmor's
`unprivileged_userns` profile and denied bwrap `setpcap` and `net_admin`.
The unchanged collector failed to configure loopback; the suite did not run.
Installing bubblewrap alone did not resolve that prerequisite.

The workflow loads `examples/ci/bwrap.apparmor` only on this repository's
ephemeral GitHub-hosted Ubuntu runner and removes it after the job. The two
named profiles allow bwrap to construct its namespaces, then stack a capability
denial onto executed children. No unconfined profile, sysctl change, disabled
AppArmor service, setuid executable or collector-flag change is used. This is
an environment prerequisite, not a runtime permission for roles or the desktop.

The policy uses AppArmor 4.0 ABI and documented profile stacking. Its design
follows the purpose-built bwrap policy described by
[Canonical](https://discourse.ubuntu.com/t/understanding-apparmor-user-namespace-restriction/58007)
and the [AppArmor 4.0.1 example](https://gitlab.com/apparmor/apparmor/-/blob/v4.0.1/profiles/apparmor/profiles/extras/bwrap-userns-restrict).
The CI probe checks namespace separation and the actual child's profile and
capabilities before the required full suite. Failed installation, missing child
policy, failed probe or skipped suite remains a failure with diagnostic artifacts.
Do not install this policy on Mani's daily workstation or treat CI as native
model qualification.

The first policy-qualified run (39974469228) cleared the kernel denials but
reached a second prerequisite: `execvp python3: No such file or directory`.
The collector's existing `/lib64 -> usr/lib` mapping expects the ELF loader at
`/usr/lib/ld-linux-x86-64.so.2`; Ubuntu keeps it in `x86_64-linux-gnu` instead.
The CI setup verifies Python's actual ELF interpreter and resolved loader,
creates only that missing alias on the disposable runner, records it, and
removes its own exact alias at cleanup. It refuses conflicting paths. The
collector and its mount/namespace arguments remain unchanged. Ubuntu support
therefore includes this declared environment prerequisite.
