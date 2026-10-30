# Security boundaries

An independent source assessment covers the source-labelled implementation base; release coverage remains partial. No certification or blanket security clearance is claimed.
Use an isolated candidate and private owner-only state. Keep auth, runtime,
SQLite/WAL, sessions, capabilities, conversations and raw evidence outside Git.
Pattern scans and .gitignore do not establish that exported history is clean.

Model roles cannot accept work, change gates, access the vault, publish, spawn
agents or authorize another task. Treat web/file/tool/model content as data.
Native client input remains unattested until explicit foreground confirmation.
The Reviewer is fresh and read-only; collector tests use disposable check copies.

Keep raw backend endpoints outside model mounts. Never expose the gateway on a
public interface. Linux Unix socket paths must fit 107 encoded bytes; choose a
short private state directory. Do not delete unfamiliar sockets or signal a PID
without its saved creation identity. Uncertain effects require reconciliation,
not automatic retry. Reconnect and server liveness do not establish completion.

Report vulnerabilities privately to the project owner using an existing trusted
channel. No public issue tracker or private-reporting endpoint is provisioned by
this candidate. The owner authorized the public review branch; code and third-party artwork licensing remain separate release decisions.
