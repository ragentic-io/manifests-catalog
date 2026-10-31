# LinkedIn: setup guide

Unsigned draft. Independent connector for LinkedIn; not affiliated with or endorsed by
LinkedIn. No logo or brand mark is used.

## Definition

LinkedIn publishes no OpenAPI document. `definition.openapi.json` is a **hand-built,
non-official** minimal operation set for the self-serve products only, written from
LinkedIn's public docs (URLs + sha256 in `sources/origins.json`, also listed in
`provenance.origins`):

| Operation | Endpoint | Product / scope |
|---|---|---|
| getUserInfo | `GET https://api.linkedin.com/v2/userinfo` | Sign In with LinkedIn using OpenID Connect: `openid profile email` |
| createPost | `POST https://api.linkedin.com/rest/posts` | Share on LinkedIn: `w_member_social` (author `urn:li:person:<sub>`) |
| deletePost | `DELETE https://api.linkedin.com/rest/posts/{postUrn}` | Share on LinkedIn: `w_member_social` |

`/rest` calls carry `LinkedIn-Version: 202610` and `X-Restli-Protocol-Version: 2.0.0`
(reviewed headers; requires the ragentic PR on branch `feat/social-connectors-catalog`).

## Credential: `oauth2_authorization_code`

1. LinkedIn Developer Portal → create an app → Products: add **Sign In with LinkedIn
   using OpenID Connect** and **Share on LinkedIn** (both self-serve).
2. Auth → Authorized redirect URL: `https://graphx.ragentic.io/registry/oauth/callback`.
3. The Ragentic operator installs the client ID and secret in Ragentic's OAuth
   registrations file.
4. Authorization `https://www.linkedin.com/oauth/v2/authorization`, token
   `https://www.linkedin.com/oauth/v2/accessToken` (client_secret_post), scopes
   `openid profile email w_member_social`. Ragentic always sends S256 PKCE
   parameters; LinkedIn documents PKCE for native clients only, so confirm in a live
   authorization that the web flow accepts them.
5. Probe: `GET /v2/userinfo` (identity `sub`). Nothing is posted.

Access tokens last 60 days; refresh tokens are only issued to approved partners, so
users reconnect when the token expires.

## Approval-gated (not included)

Organization / company-page posting, reading posts and everything else in the
**Community Management API** require LinkedIn product approval. They are deliberately
excluded and `review_required` says so; they do not work out of the box.

## Limits

Daily per-member and per-application limits apply; see
https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/rate-limits
(the Developer Portal Analytics tab shows an app's limits).
