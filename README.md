# Ragentic signed manifest catalog snapshot

This repository is a Git transport snapshot of everything served by
`https://manifests.ragentic.io/v1`:

| Object | Contents |
| --- | --- |
| `index.json` | signed catalog **sequence 16**: 16 reviewed, connectable application bundles |
| `bundles/*.json` | the 16 content-addressed bundles named by `index.json` |
| `browse-index.json` | signed browse catalog **sequence 8**: 519 discovered draft applications |
| `browse-bundles/*.json` | the 519 content-addressed draft bundles named by `browse-index.json` |

All files are copied byte-for-byte from the production registry. Every index and
bundle signature verifies against the root below, and every bundle's digest
matches its file name. Each bundle carries its own source and brand rights
notices. Draft (`discovered`) applications are browse-only: they are not live
verified and cannot be connected until reviewed and published in `index.json`.

Configure Ragentic's **Git repository** registry source with this repository URL,
the full 40-character commit SHA containing this snapshot, and an empty catalog
prefix. A branch or tag name is intentionally unsupported. Pin the registry
identity `manifests.ragentic.io`, minimum sequence `16`, and the independently
obtained Ed25519 public root:

```text
base64url: 52AAWwWestgMkDxcvhiaXmMqKKFypiBRMToJAIcPzwg
SHA-256 fingerprint: 0720afdf52cda1589ddf11e24724fa6490598ad87b3db6e645ad5257b257dec2
```

Do not establish trust from this repository alone; compare the public root
through a separate trusted channel. Both indexes expire on 2026-11-29 15:10 UTC.
After that, use a newer signed snapshot and commit. Private signing keys are
never stored here.
