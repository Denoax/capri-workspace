# Start with the existing project

Use `main` in the private [Denoax/capri](https://github.com/Denoax/capri) repository, ID 1429595311. It combines the current committed stabilization source and V3 presentation on the original implementation history. The previous public snapshot is preserved as [capri-presentation-v1-retired](https://github.com/Denoax/capri-presentation-v1-retired); see the [consolidation record](CONSOLIDATION.md).

## Offline inspection

Use Linux x86_64, Python 3.11+ with pip/venv, Git, bubblewrap and working user/mount/PID/network namespaces. From the project root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python3 -B tools/collector_diagnostics.py --output /absolute/private/checks
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s controller/tests -v
```

The diagnostic path is an operator-selected placeholder outside public Git. Tests use disposable fixtures and do not call models or need auth or a vault. A failed isolation prerequisite remains failed; do not skip assertions or weaken confinement. See [ENVIRONMENT.md](../ENVIRONMENT.md) for actual diagnostic semantics and the supported-host fallback.

## Native boundary

Read the preserved [implementation README](../IMPLEMENTATION_README.md), [native profile](../NATIVE_PROFILE.md), [example config](../examples/config.json) and [client support](../CLIENT_SUPPORT.md). The selected CLI is 0.163.0; the inherited source checks binary/schema identities. Later versions are not implicitly qualified. Ordinary native panes use tmux; existing authentication and all live state remain private.

Keep production automation disabled and use only explicitly registered disposable fixtures. Initial scope comes from a genuine foreground terminal. The presentation branch does not reset claims, launch sessions, perform maintenance or add another qualification phase. Existing qualification/evaluation and final human decisions stay as documented by the implementation owner.
