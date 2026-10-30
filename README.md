# Ragentic signed manifest catalog snapshot

This repository is a Git transport snapshot of the six bundles published at
`https://manifests.ragentic.io` in signed catalog sequence 7. The signed
`index.json` and content-addressed `bundles/*.json` are copied byte-for-byte
from the production registry. Each bundle carries its own source and brand
rights notices. This snapshot is not the unfinished 500-application draft set.

Configure Ragentic's **Git repository** registry source with this repository URL,
the full 40-character commit SHA containing this snapshot, and an empty catalog
prefix. A branch or tag name is intentionally unsupported. Pin the registry
identity `manifests.ragentic.io`, minimum sequence `7`, and the independently
obtained Ed25519 public root:

```text
base64url: 52AAWwWestgMkDxcvhiaXmMqKKFypiBRMToJAIcPzwg
SHA-256 fingerprint: 0720afdf52cda1589ddf11e24724fa6490598ad87b3db6e645ad5257b257dec2
```

Do not establish trust from this repository alone; compare the public root
through a separate trusted channel. The index expires on 2027-01-28 01:47 UTC.
After that, use a newer signed snapshot and commit. Private signing keys are
never stored here.
