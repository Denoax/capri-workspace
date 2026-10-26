# Capri workspace

Private backup of the desktop companion and presentation work. Source histories
retain their original commit IDs and branches. Archiving does not approve a
candidate, install a release, or change the existing public repository.

- [Desktop companion V4 candidate](https://github.com/Denoax/capri-workspace/tree/testing/capri-desktop-v4-20261025-01a16d59): `0bd4a5c47e36a80b3635ccea13426f6d189c2662`
- [Published presentation source](https://github.com/Denoax/capri-workspace/tree/testing/capri-publication-20261025-01a1688d)
- [All source branches](https://github.com/Denoax/capri-workspace/branches)
- [Project artifact backup](https://github.com/Denoax/capri-workspace/releases/tag/workspace-backup-20261026)

The main branch is the recovery index. Source is on the preserved branches.
33 source refs were uploaded and verified. GitHub Actions are disabled for this
backup repository so restoring archived branches cannot start old jobs.

## Artifact snapshot

The manifest covers 92,541 retained project file paths: handoffs, previews,
review bundles, raw non-private evidence and workspace records. It deduplicates
identical content and reuses existing Git blobs. Non-Git content is in seventeen
SHA-256-verified `tar.zst` release assets, about 14.8 GB total. The exact counts,
paths, source commits, provider mappings and exclusions are under `snapshot/`.

Account state, credentials, runtime databases, browser profiles and reproducible
caches are excluded. Those local files have not been deleted. This is a project
backup, not a backup of the installed application's personal data.

## Recover source

```sh
git clone https://github.com/Denoax/capri-workspace.git
cd capri-workspace
git fetch --tags
git switch --track origin/testing/capri-desktop-v4-20261025-01a16d59
```

Switch back to `main` to use the recovery index. Use `git clone --mirror` if all
branches and historical tags are needed in a standalone archive.

## Recover project artifacts

Requires Python 3, Git, zstd and an authenticated GitHub CLI. Downloaded parts and
recovered files need additional local space. The tool rejects existing output
directories, verifies compressed and expanded content, and writes relative paths.

```sh
git switch main
git fetch --tags
gh release download workspace-backup-20261026 --repo Denoax/capri-workspace --pattern 'objects-*.tar.zst' --dir downloads
python3 restore.py --assets downloads --verify-only
python3 restore.py --assets downloads --destination recovered --prefix reviews/desktop-v4-01a16d59/
```

Omit `--prefix` to recover all retained paths. Source objects are read from this
clone's `.git`; pass `--source-git PATH` when using a separate mirror. External
symlinks are recorded in the manifest and never followed during recovery.

Verification receipts on this branch distinguish source/ref checks, uploaded
asset checks and an actual download/recovery check. No local cleanup is implied.
