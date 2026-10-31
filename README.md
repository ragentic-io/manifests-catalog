# Ragentic manifest catalog

The source of truth for the applications served at `https://manifests.ragentic.io`.
Anyone can propose a new service or an improvement with a pull request. CI
validates every change, and after a maintainer merges it, the Sign workflow signs it
with the registry's Ed25519 root key. Every file here, plain text and transport
alike, is covered by that one key.

See [CATALOG.md](CATALOG.md) for every application and its status.

## Layout

| Path | What it is | Who writes it |
| --- | --- | --- |
| `apps/<id>/manifest.json` | The application's bundle payload, pretty-printed: the connector template, the embedded API definition, its operation graph, provenance, rights and setup | Contributors |
| `apps/<id>/MANIFEST.md` | Front matter with the catalog listing (`title`, `catalog`, optional `logo`), then a generated human-readable summary: endpoint, credential, source, license, review checklist and every operation | Contributors (front matter); `tools/catalog.py docs` (body) |
| `CATALOG.md` | Generated table of every application | `tools/catalog.py docs` |
| `index.json`, `bundles/` | Signed catalog of **published** applications, which people can connect | Sign workflow |
| `browse-index.json`, `browse-bundles/` | Signed catalog of **draft** applications, which can be browsed but not connected | Sign workflow |
| `sources.json` | Signed SHA-256 list of every plain-text file under `apps/` plus `CATALOG.md` | Sign workflow |
| `registry.json` | Registry identity, pinned public root and signature lifetimes | Maintainers |
| `tools/catalog.py` | Scaffolding, validation, docs and signing | Maintainers |

Signed objects are canonical JSON wrapped in `{"payload", "signature"}` envelopes. The
signature is Ed25519 over `ragentic.manifests/v1\n` followed by the payload bytes. A
bundle's file name is the SHA-256 of its payload bytes.

## The operation graph

Each OpenAPI application's `graph` is generated from its embedded definition by
`python tools/catalog.py graph <id>`, and `validate` checks that it is current.

| Node | Fields |
| --- | --- |
| `application` | `id` |
| `operation` | `name` (operationId), `method`, `path`, `summary`, `description` (first sentence), `tags`, `security`, `deprecated`, `pointer` into the definition, `parameters` (`name`, `in`, `required`, `type`, `description`, `enum`, `default`), `request` (`content_types`, `required`, `type`), `responses` (`status`, `type`), and `safe` |
| `schema` | `name`, `type`, `description` |

| Edge | Meaning |
| --- | --- |
| `EXPOSES` | application → operation |
| `ACCEPTS` | operation → schema of its request body |
| `RETURNS` | operation → schema of a 2xx response |
| `REFERENCES` | schema → schema it refers to |

Types are compact: `Pet`, `Pet[]`, `string:date-time`, `A|B`. `safe` is true for
`GET`, `HEAD` and `OPTIONS`, the operations that only read. These fields are what a
tool-calling model such as Ragentic's Needle needs to pick an operation and fill its
arguments. `safe` marks the operations a future Needle-powered preview call can run
against a connection without side effects.

## Register a new service

You need Python 3.10+ and a public OpenAPI 3 or Swagger 2 definition published by the
provider.

1. **Fork and clone** this repository, then install the tools:

   ```sh
   pip install cryptography pyyaml
   ```

2. **Pick an id.** Use lowercase letters, digits, `.`, `_` and `-`, starting with a
   letter or digit, for example `acme-openapi`. Check that `apps/<id>` doesn't exist
   and the service isn't already listed in [CATALOG.md](CATALOG.md) under another id.

3. **Scaffold the draft** from the provider's definition:

   ```sh
   python tools/catalog.py new acme-openapi \
     --openapi https://developer.acme.com/openapi.json \
     --title "Acme" \
     --credential api_key_header --header Authorization --prefix Bearer
   ```

   This fetches the definition and embeds it. It records its URL and SHA-256 under
   `provenance`, generates the operation graph and writes
   `apps/acme-openapi/manifest.json` and `MANIFEST.md`. Leave out `--credential` if
   you don't know the authentication yet. `--endpoint` overrides the base URL, which
   otherwise comes from the definition's first `https` server.

4. **Review and complete `manifest.json`:**
   - `manifest.spec.title` and `description`: the provider's own name and a one-line summary.
   - `manifest.spec.base.endpoint`: the production `https` base URL.
   - `provenance.license`: the definition's license. Only submit definitions whose
     license allows redistribution.
   - `setup.credential`: `none`, `static_bearer`, or `api_key_header` with `header`
     and `prefix`. Never put a real key, token or password anywhere in the file.
   - If you edit the embedded definition, run `python tools/catalog.py graph <id>`
     to regenerate the graph.

5. **Check the listing** in the front matter of `MANIFEST.md`. Values are JSON:

   ```yaml
   ---
   title: "Acme"
   catalog: "drafts"
   logo: "https://acme.com/favicon.svg"
   ---
   ```

   New services always start in `drafts`. `logo` is optional and must be `https`.

6. **Regenerate the docs and validate:**

   ```sh
   python tools/catalog.py docs
   python tools/catalog.py validate
   ```

   `validate` must end with `ok`. Your application is reported as
   `pending … not signed yet`, which is expected.

7. **Open a pull request** that changes only `apps/` and `CATALOG.md`, and fill in
   the checklist. The Validate workflow runs the same checks and prints the signing
   plan. Pull requests from forks may not touch signed objects, `registry.json`,
   `tools/` or `.github/`.

8. **After merge**, the Sign workflow signs the new bundle and adds it to
   `browse-index.json` with the next sequence number. It also commits the signed
   files, and the application shows as `signed` in [CATALOG.md](CATALOG.md).

### Updating or removing a service

Edit `apps/<id>/manifest.json` or the front matter, run `docs` and `validate`, and
open a pull request. The Sign workflow re-signs only what changed. Deleting
`apps/<id>` removes the application from its index and deletes its bundle when the
change is signed.

### Promoting a draft to published

Published applications can be connected in Ragentic, so they need a complete setup.
Change `catalog: "drafts"` to `catalog: "published"` only when `manifest.json` has:

- a `readiness` other than `discovered` or `preview_only`
- `setup.credential` and a `setup.probe` connection test
- `rights.source` (license and copyright) and `rights.brand` (attribution)
- an `a2ui` setup form

Use a published application with the same credential type as a template, for
example `apps/govuk-pay`. `validate` enforces these requirements. Say in the pull
request how you tested the connection.

## Validation rules

`python tools/catalog.py validate` checks the following:

- **Signatures:** both indexes, every bundle they name and `sources.json` verify
  against the root in `registry.json`. Digests match file names, and no bundle is
  left unreferenced.
- **Each application:**
  - Its id, protocol, version, `manifest` template and provenance are valid.
  - It embeds its definition (an OpenAPI document, or GraphQL SDL).
  - Its graph edges join known nodes.
  - OpenAPI graphs match the definition.
- **Listing:** the title, catalog and logo are valid, and published applications meet
  the promotion requirements.
- **Safety:** no credential-like strings in `setup`, `a2ui` or the base headers, and
  every payload is under 16 MiB.
- **Generated docs:** `MANIFEST.md` bodies and `CATALOG.md` are up to date.

`validate --require-signed` also fails if anything is waiting for signature. The Sign
workflow runs it after signing.

## Signing (maintainers)

The Sign workflow runs on every push to `main` that touches `apps/`, `registry.json`
or `tools/catalog.py`, daily on a schedule, and on demand. For each application whose
sources differ from its signed bundle, or whose signature expires within
`refresh_days`, it:

1. Sets `not_before` and `expires` (`validity_days` ahead) and signs the canonical
   payload into `bundles/` or `browse-bundles/`.
2. Writes the new times back into `manifest.json`, so the sources keep matching.
3. Rebuilds each index whose entries changed or that is close to expiry, keeping
   existing order. It increments the sequence and deletes bundles the index no
   longer names.
4. Regenerates the docs and signs `sources.json` over every plain-text file.
5. Commits the result to `main`.

Preview the plan without a key with `python tools/catalog.py sign --dry-run`.

One-time setup:

1. Create a GitHub environment named `registry-signing`, with deployment branches
   restricted to `main`.
2. Add the root private key to that environment as the secret
   `MANIFESTS_SIGNING_KEY`, as a 32-byte Ed25519 seed in hex or base64url. The tool
   refuses a key that doesn't match the pinned root.
3. Protect `main`: require pull requests, the Validate check and a code owner review.
   Allow GitHub Actions to push the signing commit, for example as a ruleset bypass
   actor.

The registry server at `manifests.ragentic.io` should publish from this repository,
so the repository and the server never sign competing sequence numbers.

## Using this catalog

Configure Ragentic's **Git repository** registry source with this repository URL,
the full 40-character commit SHA of a signed commit, and an empty catalog prefix. A
branch or tag name is intentionally unsupported. Pin the registry identity
`manifests.ragentic.io`, a minimum sequence no lower than the one you last trusted,
and the independently obtained Ed25519 public root:

```text
base64url: 52AAWwWestgMkDxcvhiaXmMqKKFypiBRMToJAIcPzwg
SHA-256 fingerprint: 0720afdf52cda1589ddf11e24724fa6490598ad87b3db6e645ad5257b257dec2
```

Do not establish trust from this repository alone; compare the public root through a
separate trusted channel. Signed objects expire, so use a recent signed commit.
Private signing keys are never stored here.
