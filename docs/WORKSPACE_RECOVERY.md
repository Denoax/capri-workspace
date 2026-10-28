# Preserved workspace backup index

The root of this repository contains the Agentic Loop Prompting project. Its restored source comes from `7c5957b9e01cf4d2e07e58545a000aef03571983`, the last workflow README revision before the desktop-app documentation edits.

The earlier backup/recovery index is preserved intact at commit `b9af025c26107bf5476e0e2bb5f6c568f30f2475`. It remains part of this repository’s history:

- [Original backup README and recovery commands](https://github.com/Denoax/capri-workspace/blob/b9af025c26107bf5476e0e2bb5f6c568f30f2475/README.md)
- [Original restoration tool](https://github.com/Denoax/capri-workspace/blob/b9af025c26107bf5476e0e2bb5f6c568f30f2475/restore.py)
- [Original snapshot manifests](https://github.com/Denoax/capri-workspace/tree/b9af025c26107bf5476e0e2bb5f6c568f30f2475/snapshot)

From a clone with the history available, inspect the original guide with:

```sh
git show b9af025c26107bf5476e0e2bb5f6c568f30f2475:README.md
```

The existing `workspace-backup-20261026` artifact release is a separate draft; its publication status has not changed. Restoring the project on `main` does not publish those packs, discard their manifests, delete source branches/tags, install the app or launch native work. Both project-source and backup-index histories are parents of the restoration commit.
