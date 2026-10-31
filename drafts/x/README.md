# X (API v2): setup guide

Unsigned draft. Independent connector for X; not affiliated with or endorsed by X.
No logo or brand mark is used.

## Definition

X's official OpenAPI document, `https://api.x.com/2/openapi.json` (info.version 2.173,
1,314,742 bytes, sha256 `a0d947e306520b653e252a965f6e28008e53d634f398231e8a767a720295ad02`),
embedded unchanged in `payload.json` (257 operations). It is not committed separately;
`sources/source.json` pins URL, hashes and fetch time, and `drafts/validate --fetch`
re-downloads and compares it.

**Licence / terms:** no open-source licence is stated. The document's `info.license`
names the "X Developer Agreement and Policy" at a URL that now answers 404 (terms moved
to https://docs.x.com/developer-terms/policy). Those terms do not expressly grant
redistribution of the definition in a signed bundle: **DJ must review before publishing.**

## Credential: `oauth2_authorization_code` with PKCE (S256)

1. X Developer Console → Project + App → User authentication: OAuth 2.0, type
   Web App (confidential client).
2. Redirect URI: `https://graphx.ragentic.io/registry/oauth/callback`.
3. The Ragentic operator installs the client ID and secret in Ragentic's OAuth
   registrations file. They never go into the catalog or the form.
4. Connect authorizes at `https://x.com/i/oauth2/authorize`, token endpoint
   `https://api.x.com/2/oauth2/token` (client_secret_basic), scopes
   `tweet.read tweet.write users.read offline.access`. That covers posting, deleting,
   reading the user's own timeline and refreshing the two-hour token.
5. Probe: `GET /2/users/me` (identity `data.id`). Nothing is posted.

App-only bearer (read-only, `static_bearer`) is **not** offered by this bundle: a
bundle declares one credential, and the user-context token covers the same reads.
A separate app-only bundle can be added later if it is needed.

## Paid tier and limits

X API access is paid: pay-per-use credits are charged per request, including the
connection test (e.g. about $0.015 per post created, $0.010 per user read at the time
of writing; pay-per-use capped at 3 million post reads/month). Per-endpoint rate limits
apply per user and per app per 15-minute window. See https://docs.x.com/x-api/fundamentals/rate-limits
and the pricing page in the Developer Console.
