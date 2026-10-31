# Bluesky (AT Protocol): setup guide

Unsigned draft. Independent connector for Bluesky; not affiliated with or endorsed by
Bluesky Social PBC. No logo or brand mark is used.

## Definition

`definition.openapi.json` is an OpenAPI 3.0 conversion, made by Ragentic, of ten
official lexicons from `bluesky-social/atproto` pinned at commit
`d3080834ac43dbb94e97e82fdd85b1a0f12558ad` (`sources/lexicons/`, hashes in
`sources/lexicons.json`). Licence: MIT OR Apache-2.0 (`sources/LICENSE*.txt`). It is
not an official Bluesky definition.

| Operation | XRPC | Notes |
|---|---|---|
| getProfile, getAuthorFeed, getPostThread, searchActors, searchPosts | `app.bsky.*` (GET) | read |
| getSession | `com.atproto.server.getSession` | the connection test (read-only) |
| createRecord (`app.bsky.feed.post`), deleteRecord, uploadBlob | `com.atproto.repo.*` (POST) | write |

## Credential: `atproto_session` (app password)

1. In Bluesky, Settings → Privacy and security → App passwords → add one. Do not use
   the account password.
2. In Ragentic's setup form enter the handle or DID and the app password.
3. Test calls `com.atproto.server.createSession` on `https://bsky.social`, then the
   probe `GET /xrpc/com.atproto.server.getSession` with the `accessJwt` (identity:
   `did`). Nothing is posted. The secret is stored encrypted; the session is
   refreshed by creating a new one when the `accessJwt` (about two hours) nears expiry.

Requires the `atproto_session` credential type in Ragentic (ragentic-io/ragentic,
branch `feat/social-connectors-catalog`); older servers reject this bundle's setup.
atproto OAuth is **not** used: Ragentic has no DPoP/PAR support.

Accounts on another PDS: this draft pins `https://bsky.social` as the service.

## Unauthenticated reads

The `app.bsky.*` reads also work without any credential at
`https://public.api.bsky.app/xrpc/...` (public AppView). This bundle sends them through
the user's PDS, which proxies them to the AppView.

## Limits

Bluesky's PDS rate limits apply (e.g. createSession is limited per account per day,
record writes per account per hour): https://docs.bsky.app/docs/advanced-guides/rate-limits
