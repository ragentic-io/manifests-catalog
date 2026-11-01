# Publishing the social connector drafts

`drafts/<app>/payload.json` are **unsigned** bundle payloads for Bluesky, X, LinkedIn
and Facebook Pages. Builders never hold the registry key: nothing here is signed, and
`index.json` and `bundles/` are untouched. Only DJ signs, on a trusted machine.

## Sequence: 17, not 10

The brief said "sequence 10" because this Git snapshot was at sequence 9 when it was
written; main has since mirrored sequence 16. Production
`https://manifests.ragentic.io/v1/index.json` was at **sequence 16** (16 entries,
expires 2026-11-29 15:10:50 UTC) when these drafts were built on 2026-10-31. A new index
must extend production's newest index. A lower sequence is a rollback, and a second
index numbered 10 conflicts with the one production already signed; Ragentic rejects
both. `publish.exs` takes the base index as `BASE_INDEX`, checks it against the pinned
root, and signs `base + 1`.

## Before signing (review)

1. `python3 -I drafts/validate --fetch` must print `all passed`. It re-downloads every
   pinned upstream source and compares hashes.
2. From a ragentic checkout that has `atproto_session` (ragentic-io/ragentic PR on branch
   `feat/social-connectors-catalog`, merged and deployed first: older servers reject the
   Bluesky setup):
   `MIX_ENV=test mix run --no-start ../manifests-catalog/drafts/ragentic_check.exs ../manifests-catalog/drafts`
   must print `4 drafts checked by Ragentic: all passed`.
3. Decide the open points listed in each payload's `readiness.external_references` and
   `drafts/<app>/README.md`:
   - **X:** redistribution of X's OpenAPI document is not expressly granted by the X
     Developer Agreement. Approve it, or drop `x`.
   - **Facebook:** Page-token derivation is missing in Ragentic, so `getPageFeed` and
     `publishPagePost` fail until it exists.
   - **LinkedIn and Facebook:** confirm the PKCE and token-exchange behaviour in a live
     authorization.
   - **All four:** `review_required` is a draft marker. If Ragentic should treat a bundle
     as reviewed, set it to `false`, then rerun steps 1 and 2.
4. To publish only some apps, set `APPS=bluesky,linkedin` (comma-separated `app` ids).

## Sign, bundle, index

From the ragentic checkout, with the root private key in a file that never leaves the
trusted machine (base64url, no padding, 32 bytes; the script refuses any key whose
public half is not the pinned root `wFvL-3yCuZX52nrDbSxvTgeb5s4KFp6aS2W8JikogGs`):

```sh
CATALOG=../manifests-catalog                      # this repository, on the reviewed commit
curl -sf -o /tmp/prod-index.json https://manifests.ragentic.io/v1/index.json

# Rehearse with a throwaway key first (writes to /tmp, trusted by nobody):
mkdir -p /tmp/seq-dry && BASE_INDEX=/tmp/prod-index.json REGISTRY_KEY_FILE=ephemeral \
  mix run --no-start $CATALOG/drafts/publish.exs $CATALOG /tmp/seq-dry

# Real signing into a fresh directory:
mkdir -p /tmp/seq-out && BASE_INDEX=/tmp/prod-index.json REGISTRY_KEY_FILE=/secure/root.key \
  mix run --no-start $CATALOG/drafts/publish.exs $CATALOG /tmp/seq-out
```

Expected output: one `bundle <app> <version> <digest>` line per draft, then
`index manifests.ragentic.io sequence 17: 20 entries, ...`. The script verifies every
bundle and the new index with `RagenticManifests.Trust` before writing anything. With
unchanged payloads and `NOT_BEFORE`/`EXPIRES` unset, the digests are:

| app | version | digest |
|---|---|---|
| bluesky | 1.0.0-draft | `e065f1d096edfb00e9a7ec445972c33234b01c402186be7a4f9812f717435504` |
| facebook | v26.0 | `f611a796d5ab7a6c6e6654114df8b520f7f46276c337ea48fab403ac8cfb0154` |
| linkedin | 202610 | `db716a36cccd190f0f6795a426938972783ca905fd590baa37af4f410155ccad` |
| x | 2.173 | `447904d5fbad959e426fc6c11e352f1e8da4952adebb4f7d2cabb0f66ce305df` |

The bundles last until 2027-01-28 01:47:04 UTC (`expires` in each payload). The index
keeps the base index's expiry unless `EXPIRES` is set. Override either with
`NOT_BEFORE=<unix> EXPIRES=<unix>`; changing them changes the digests.

## Publish to manifests.ragentic.io

Upload `/tmp/seq-out/bundles/*.json` (served as `/v1/bundles/<digest>`, no suffix) and then `/tmp/seq-out/index.json` to the registry
server (the sibling ragentic-manifests project, using the same procedure as sequences
10–16; this repository has no access to it). Upload the bundles first, so the new index
never names a missing bundle. Then check:

```sh
curl -sf https://manifests.ragentic.io/v1/index.json | cmp - /tmp/seq-out/index.json
for f in /tmp/seq-out/bundles/*.json; do
  d=$(basename "$f" .json)
  curl -sf "https://manifests.ragentic.io/v1/bundles/$d" | cmp - "$f" && echo "ok $d"
done
```

## Mirror into this repository

The snapshot must hold every bundle the new index names (main already mirrors sequence
16; the loop fetches any bundle still missing):

```sh
cd $CATALOG && git switch main && git pull && git switch -c mirror-sequence-17
cp /tmp/seq-out/index.json index.json
cp /tmp/seq-out/bundles/*.json bundles/
python3 -I - <<'PY' | while read d; do
import base64, json
p = json.loads(base64.urlsafe_b64decode(json.load(open("index.json"))["payload"] + "=="))
print("\n".join(e["digest"] for e in p["entries"]))
PY
  [ -f "bundles/$d.json" ] || curl -sf -o "bundles/$d.json" "https://manifests.ragentic.io/v1/bundles/$d"
  python3 -I -c "import base64,hashlib,json,sys; p=json.load(open(sys.argv[1]))['envelope']['payload']; \
assert hashlib.sha256(base64.urlsafe_b64decode(p+'='*(-len(p)%4))).hexdigest()==sys.argv[2]" \
    "bundles/$d.json" "$d" || echo "DIGEST MISMATCH $d"
done
```

Update README.md (sequence 17, bundle count, index expiry, minimum sequence), commit
("Mirror signed manifest catalog sequence 17") and push. Do not commit the key or
`/tmp/seq-out` anywhere else. Once the snapshot is mirrored, the drafts can stay here
for reference or be removed.

## After publishing (shipper)

- `https://manifests.ragentic.io/v1/index.json` and this repository's `index.json` list
  `bluesky`, `x`, `linkedin` and `facebook` with the digests above.
- In Ragentic, `/catalog/registries` verifies and previews each one, with the setup
  form rendered and the independent-integration attribution shown.
