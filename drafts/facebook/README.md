# Facebook Pages (Meta Graph API v26.0): setup guide

Unsigned draft. Independent connector for Facebook; not affiliated with or endorsed by
Meta. No logo or brand mark is used.

## Definition

Meta publishes no OpenAPI document. `definition.openapi.json` is a **hand-built,
non-official** minimal Pages operation set, pinned to Graph API **v26.0**, written from
Meta's public docs (URLs + sha256 in `sources/origins.json`, also in
`provenance.origins`):

| Operation | Endpoint | Token / permission |
|---|---|---|
| getMe | `GET /v26.0/me` | user token (connection test) |
| listPages | `GET /v26.0/me/accounts` | user token, `pages_show_list`; returns each Page's id and Page access token |
| getPageFeed | `GET /v26.0/{page-id}/feed` | **Page** token, `pages_read_engagement` |
| publishPagePost | `POST /v26.0/{page-id}/feed` | **Page** token, `pages_manage_posts` (+ `pages_read_engagement`, `pages_show_list`) |

## Credential: `oauth2_authorization_code` (user token → Page token)

1. Meta for Developers → create an app (type Business) → add Facebook Login.
2. Valid OAuth redirect URI: `https://graphx.ragentic.io/registry/oauth/callback`.
3. The Ragentic operator installs the app ID and secret in Ragentic's OAuth
   registrations file.
4. Authorization `https://www.facebook.com/v26.0/dialog/oauth`, token
   `https://graph.facebook.com/v26.0/oauth/access_token` (client_secret_post), scopes
   `pages_show_list pages_read_engagement pages_manage_posts`.
5. Probe: `GET /v26.0/me` (identity `id`). Nothing is posted.

**Known gap:** the feed operations need a *Page* access token, which Meta returns from
`/me/accounts` for a user token. Ragentic does not yet derive and store Page tokens
from the user token, so `getPageFeed` and `publishPagePost` fail with the user token
until it does (stated in `readiness` and `review_required`). `getMe` and `listPages` work.
Meta documents the code exchange as GET with query parameters; Ragentic POSTs a form
and always adds PKCE. Confirm both in a live authorization before signing.

## Approval

Without **Meta App Review** (and Business Verification) the permissions only work for
people with a role on the app and Pages they manage. Managing Pages of anyone else
needs App Review for all three permissions.

## Limits

Page calls are rate-limited by Business Use Case limits per Page (scaled by the Page's
engagement): https://developers.facebook.com/docs/graph-api/overview/rate-limiting
Graph API versions are supported for about two years; re-pin before v26.0 is retired.
