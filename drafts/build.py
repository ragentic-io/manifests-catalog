#!/usr/bin/env python3
"""Build the unsigned draft bundle payloads in drafts/<app>/payload.json.

    python3 -I drafts/build.py [--x-spec PATH]

Every input is pinned under drafts/<app>/ (lexicons, hand-built definitions,
source/origin records). The X definition is not committed separately: it is
downloaded from its pinned URL (or read from --x-spec) and must match the
pinned SHA-256 exactly, otherwise the build stops. No clock is read
(timestamps are constants below), so re-running reproduces identical files.

This script never signs anything and never touches index.json or bundles/.
"""
import hashlib
import json
import pathlib
import sys
import urllib.request

DRAFTS = pathlib.Path(__file__).resolve().parent

# Validity window written into every draft payload. not_before is the build
# date (2026-10-31T00:00:00Z); expires matches the sequence-9 index expiry
# (2027-01-28T01:47:04Z). DJ may change both when signing; see PUBLISHING.md.
NOT_BEFORE = 1793404800
EXPIRES = 1801100824

THEME = "#475569"  # neutral slate, the colour GOV.UK Pay's bundle uses; no brand colours
CATALOG = "https://a2ui.org/specification/v1_0/catalogs/basic/catalog.json"
CALLBACK = "https://graphx.ragentic.io/registry/oauth/callback"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(obj) -> bytes:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode()


def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def write_json(path, obj):
    pathlib.Path(path).write_text(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Graph of operations, same node/edge shape as the published bundles.

METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")


def pointer(path, method):
    return "#/paths/" + path.replace("~", "~0").replace("/", "~1") + "/" + method


def graph(app, document):
    nodes = [{"id": app, "kind": "application"}]
    edges = []
    for path in sorted(document["paths"]):
        item = document["paths"][path]
        for method in METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            node_id = f"operation:{method}:{path}"
            nodes.append(
                {
                    "deprecated": bool(op.get("deprecated", False)),
                    "id": node_id,
                    "kind": "operation",
                    "method": method,
                    "name": op.get("summary") or op.get("operationId") or f"{method.upper()} {path}",
                    "path": path,
                    "pointer": pointer(path, method),
                    "security": op.get("security", document.get("security", [])),
                    "summary": op.get("summary") or op.get("description", "")[:200],
                }
            )
            edges.append({"from": app, "kind": "EXPOSES", "to": node_id})
    return {"edges": edges, "nodes": nodes}


# --------------------------------------------------------------------------
# A2UI setup form, same component vocabulary as the published bundles.


def text(cid, value):
    return {"component": "Text", "id": cid, "text": value}


def button(cid, label_id, action, variant=None):
    b = {"action": action, "child": label_id, "component": "Button", "id": cid}
    if variant:
        b["variant"] = variant
    return b


def event(name, context):
    return {"event": {"context": context, "name": name}}


def a2ui(app, provider, steps, mode, token_label=None, username_label=None):
    """mode: "oauth" (one Connect button) or "atproto" (handle + app password, Test then Save)."""
    surface = f"setup-{app}"
    attribution = attribution_text(provider)
    status = (
        "Authorize the application to verify and save your connection."
        if mode == "oauth"
        else "Test the connection before saving."
    )
    components = []
    children = ["independent-label", "title", "independent-attribution", "steps", "connection-name", "workspace"]
    components.append(text("independent-label", "Independent integration"))
    components.append(text("title", f"## Connect {provider}"))
    components.append(
        {
            "component": "Tabs",
            "id": "steps",
            "tabs": [{"child": f"step-{i}", "title": f"{i + 1}. {s['title']}"} for i, s in enumerate(steps)],
        }
    )
    components.append({"component": "TextField", "id": "connection-name", "label": "Connection name", "value": {"@path": "/name"}})
    components.append({"component": "TextField", "id": "workspace", "label": "Workspace", "value": {"@path": "/workspace"}})

    base_context = {"app": app, "name": {"@path": "/name"}, "workspace": {"@path": "/workspace"}}
    if mode == "oauth":
        children += ["save", "status", "credentials"]
        components.append(text("save-label", "Connect and save"))
        components.append(button("save", "save-label", event("registry_oauth", base_context), "primary"))
    else:
        children += ["username", "token", "test", "save", "status", "credentials"]
        components.append({"component": "TextField", "id": "username", "label": username_label, "value": {"@path": "/username"}})
        components.append(
            {"component": "TextField", "id": "token", "label": token_label, "value": {"@path": "/token"}, "variant": "obscured"}
        )
        context = dict(base_context, token={"@path": "/token"}, username={"@path": "/username"})
        components.append(text("test-label", "Test connection"))
        components.append(button("test", "test-label", event("registry_test", context)))
        components.append(text("save-label", "Save connection"))
        components.append(button("save", "save-label", event("registry_save", context), "primary"))
    components.append({"component": "Text", "id": "status", "text": {"@path": "/status"}})
    components.append(text("credentials-label", "Manage credentials"))
    components.append(button("credentials", "credentials-label", event("registry_credentials", {})))

    for i, step in enumerate(steps):
        links = [f"step-{i}-link-{j}" for j in range(len(step["links"]))]
        components.append({"children": [f"step-{i}-text", *links], "component": "Column", "id": f"step-{i}"})
        components.append(text(f"step-{i}-text", step["text"]))
        for j, (label, url) in enumerate(step["links"]):
            components.append(text(f"step-{i}-link-{j}-label", label))
            components.append(
                button(
                    f"step-{i}-link-{j}",
                    f"step-{i}-link-{j}-label",
                    {"functionCall": {"@call": "openUrl", "args": {"url": url}}},
                )
            )
    components.append(text("independent-attribution", attribution))
    components.insert(0, {"children": children, "component": "Column", "id": "root"})

    return {
        "messages": [
            {
                "createSurface": {
                    "catalogId": CATALOG,
                    "dataModel": {"name": app, "status": status, "workspace": ""},
                    "metadata": {"extensions": {"io_ragentic_theme": {"primaryColor": THEME}}},
                    "sendDataModel": False,
                    "surfaceId": surface,
                },
                "version": "v1.0",
            },
            {"updateComponents": {"components": components, "surfaceId": surface}, "version": "v1.0"},
        ],
        "version": "v1.0",
    }


# --------------------------------------------------------------------------
# Rights: plain-text provider name only, independent attribution, no logo.


def attribution_text(provider):
    return f"Independent connector for {provider}. Not affiliated with or endorsed by {provider}."


MARK_POLICY = (
    "Provider name in plain text only for identification; no provider logo, favicon, "
    "or brand color; independent attribution shown in setup."
)


def rights(provider, brand_policy_url, source):
    attribution = attribution_text(provider)
    r = {
        "brand": {"attribution": attribution, "independent_integration": True, "logo": None},
        "independent_attribution": attribution,
        "mark_policy": MARK_POLICY,
        "source": source,
    }
    if brand_policy_url:
        r["brand_policy_url"] = brand_policy_url
    # Flat licence fields only where the source has a stated licence (as the
    # published bundles do); hand-built and terms-only sources carry their
    # notes in rights.source instead of null licence fields.
    if source.get("spdx") and source.get("license_text"):
        r |= {
            "source_attribution": source["attribution"],
            "source_license": source["spdx"],
            "source_license_sha256": source["license_sha256"],
            "source_license_text": source["license_text"],
            "source_license_url": source["license_url"],
        }
    return r


def manifest(app, title, endpoint, document, description, headers=None):
    return {
        "apiVersion": "ragentic.dev/v1",
        "kind": "ConnectorTemplate",
        "metadata": {"name": app},
        "spec": {
            "base": {
                "endpoint": endpoint,
                "headers": headers or {},
                "protocol": "openapi",
                "specification": {"document": document},
                "type": "app",
            },
            "category": "app",
            "connector": {},
            "description": description,
            "status": "published",
            "title": title,
        },
    }


def payload(app, title, version, provider, endpoint, document, description, setup, steps, mode, prov, rights_, readiness, review, headers=None, **form):
    return {
        "a2ui": a2ui(app, provider, steps, mode, **form),
        "app": app,
        "expires": EXPIRES,
        "graph": graph(app, document),
        "kind": "bundle",
        "manifest": manifest(app, title, endpoint, document, description, headers),
        "not_before": NOT_BEFORE,
        "protocol": "openapi",
        "provenance": prov,
        "readiness": readiness,
        "review_required": review,
        "rights": rights_,
        "setup": setup,
        "version": version,
    }


def oauth(authorize, token, scopes, client_authentication):
    return {
        "type": "oauth2_authorization_code",
        "provider": {
            "authorizationEndpoint": authorize,
            "clientAuthentication": client_authentication,
            "scopes": scopes,
            "tokenEndpoint": token,
        },
    }


def probe(endpoint, identity_path):
    return {"endpoint": endpoint, "identityPath": identity_path, "method": "GET", "protocol": "openapi"}


def callback_step(provider_app_console):
    return (
        f"Register the redirect URI {CALLBACK} in {provider_app_console}. Your Ragentic operator "
        "installs the app's client ID (and secret) in Ragentic's OAuth registrations file; "
        "they never go in this form or in the catalog."
    )


# --------------------------------------------------------------------------
# Bluesky: AT Protocol lexicons converted to an OpenAPI 3.0 document.


def lex_schema(defn, nsid):
    """Convert one lexicon schema node to OpenAPI. Cross-document refs become
    documented opaque objects: the referenced lexicon is named, not inlined."""
    t = defn.get("type")
    out = {}
    if "description" in defn:
        out["description"] = defn["description"]
    if t == "string":
        out["type"] = "string"
        for k in ("maxLength", "minLength", "default"):
            if k in defn:
                out[k] = defn[k]
        if "enum" in defn:
            out["enum"] = defn["enum"]
        if "knownValues" in defn:
            out["x-lexicon-knownValues"] = defn["knownValues"]
        if "format" in defn:
            fmt = defn["format"]
            out["format"] = {"datetime": "date-time", "uri": "uri"}.get(fmt, fmt)
    elif t in ("integer", "boolean"):
        out["type"] = t
        for k in ("minimum", "maximum", "default"):
            if k in defn:
                out[k] = defn[k]
    elif t == "array":
        out["type"] = "array"
        out["items"] = lex_schema(defn["items"], nsid)
        if "maxLength" in defn:
            out["maxItems"] = defn["maxLength"]
    elif t in ("object", "params"):
        out["type"] = "object"
        props = defn.get("properties", {})
        out["properties"] = {k: lex_schema(v, nsid) for k, v in props.items()}
        if defn.get("required"):
            out["required"] = defn["required"]
    elif t == "ref":
        ref = defn["ref"]
        target = ref if not ref.startswith("#") else nsid + ref
        out.setdefault("description", "")
        out["type"] = "object"
        out["x-lexicon-ref"] = target
        out["description"] = (out["description"] + f" Lexicon object {target}.").strip()
    elif t == "union":
        refs = [r if not r.startswith("#") else nsid + r for r in defn["refs"]]
        out["type"] = "object"
        out["x-lexicon-union"] = refs
        out["description"] = (out.get("description", "") + " One of: " + ", ".join(refs) + " (identified by $type).").strip()
    elif t == "blob":
        out["type"] = "object"
        out["x-lexicon-type"] = "blob"
        out["description"] = (out.get("description", "") + " Blob reference: {$type: blob, ref: {$link: CID}, mimeType, size}.").strip()
    elif t == "unknown":
        out["type"] = "object"
        out["additionalProperties"] = True
    else:
        raise SystemExit(f"unhandled lexicon type {t} in {nsid}")
    return out


BLUESKY_SUMMARIES = {
    "app.bsky.actor.getProfile": ("getProfile", "Get an actor's profile"),
    "app.bsky.actor.searchActors": ("searchActors", "Search for actors (profiles)"),
    "app.bsky.feed.getAuthorFeed": ("getAuthorFeed", "Get an actor's author feed"),
    "app.bsky.feed.getPostThread": ("getPostThread", "Get a post thread"),
    "app.bsky.feed.searchPosts": ("searchPosts", "Search posts"),
    "com.atproto.repo.createRecord": ("createRecord", "Create a record (for example a post)"),
    "com.atproto.repo.deleteRecord": ("deleteRecord", "Delete a record"),
    "com.atproto.repo.uploadBlob": ("uploadBlob", "Upload a blob (image or video) for a record"),
    "com.atproto.server.getSession": ("getSession", "Get the current session's account"),
}


def bluesky_document(lexdir: pathlib.Path):
    lexicons = {}
    for f in sorted(lexdir.glob("*.json")):
        d = load(f)
        lexicons[d["id"]] = d
    post = lexicons["app.bsky.feed.post"]["defs"]["main"]
    paths = {}
    for nsid, (op_id, summary) in BLUESKY_SUMMARIES.items():
        main = lexicons[nsid]["defs"]["main"]
        op = {
            "operationId": op_id,
            "summary": summary,
            "description": main.get("description", ""),
            "security": [{"atprotoSession": []}],
            "x-lexicon": nsid,
        }
        if main["type"] == "query":
            method = "get"
            params = main.get("parameters", {"properties": {}})
            required = set(params.get("required", []))
            op["parameters"] = [
                {
                    "name": name,
                    "in": "query",
                    "required": name in required,
                    "schema": lex_schema(schema, nsid),
                    **({"description": schema["description"]} if "description" in schema else {}),
                }
                for name, schema in params["properties"].items()
            ]
        else:
            method = "post"
            body = main["input"]
            if body["encoding"] == "application/json":
                schema = lex_schema(body["schema"], nsid)
                if nsid == "com.atproto.repo.createRecord":
                    # Document the one record type this connector is for, from app.bsky.feed.post.
                    record = lex_schema(post["record"], "app.bsky.feed.post")
                    record["properties"] = {"$type": {"type": "string", "enum": ["app.bsky.feed.post"]}, **record["properties"]}
                    record["required"] = ["$type", *record.get("required", [])]
                    record["description"] = (
                        "The record itself; must contain $type. For a post use collection "
                        "app.bsky.feed.post and this shape (lexicon app.bsky.feed.post)."
                    )
                    schema["properties"]["record"] = record
                op["requestBody"] = {"required": True, "content": {"application/json": {"schema": schema}}}
            else:
                op["requestBody"] = {
                    "required": True,
                    "description": "Raw blob bytes; set Content-Type to the blob's MIME type. Size limits are set by the PDS.",
                    "content": {"*/*": {"schema": {"type": "string", "format": "binary"}}},
                }
        output = main.get("output")
        if output and "schema" in output:
            op["responses"] = {
                "200": {"description": "OK", "content": {"application/json": {"schema": lex_schema(output["schema"], nsid)}}}
            }
        else:
            op["responses"] = {"200": {"description": "OK"}}
        op["responses"]["400"] = {"description": "XRPC error {error, message}"}
        op["responses"]["401"] = {"description": "Missing or expired session"}
        paths[f"/xrpc/{nsid}"] = {method: op}
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Bluesky (AT Protocol) profiles, feeds, search and posting (independent conversion)",
            "version": "atproto-lexicons@" + load(DRAFTS / "bluesky/sources/lexicons.json")["commit"][:12],
            "description": (
                "Selected AT Protocol XRPC methods converted by Ragentic to OpenAPI 3.0 from the official "
                "lexicons of bluesky-social/atproto (pinned commit, MIT OR Apache-2.0). This is NOT an "
                "official Bluesky definition and is not endorsed by Bluesky Social PBC. Requests go to the "
                "account's PDS at https://bsky.social, which serves com.atproto.* itself and proxies "
                "app.bsky.* reads to the Bluesky AppView. The same app.bsky.* reads also work without "
                "authentication at https://public.api.bsky.app. Cross-lexicon object references are named "
                "(x-lexicon-ref / x-lexicon-union), not inlined."
            ),
            "x-ragentic-not-official": True,
        },
        "servers": [{"url": "https://bsky.social"}],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "atprotoSession": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": (
                        "accessJwt from com.atproto.server.createSession with the account handle (or DID) and "
                        "an app password. Ragentic's atproto_session credential creates and renews it."
                    ),
                }
            }
        },
    }


def build_bluesky():
    app, provider = "bluesky", "Bluesky"
    src = load(DRAFTS / "bluesky/sources/lexicons.json")
    document = bluesky_document(DRAFTS / "bluesky/sources/lexicons")
    definition = DRAFTS / "bluesky/definition.openapi.json"
    definition.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    commit = src["commit"]
    mit = (DRAFTS / "bluesky/sources/LICENSE-MIT.txt").read_text(encoding="utf-8")
    notice = (DRAFTS / "bluesky/sources/LICENSE.txt").read_text(encoding="utf-8")
    manifest_bytes = (DRAFTS / "bluesky/sources/lexicons.json").read_bytes()
    prov = {
        "commit": commit,
        "fetched_at": src["fetched_at"],
        "license": {
            "name": "MIT OR Apache-2.0",
            "sha256": src["license"]["sha256"],
            "url": src["license"]["url"],
        },
        "normalization": (
            "Ragentic conversion of the pinned lexicons listed in origins to OpenAPI 3.0 "
            "(drafts/bluesky/build via drafts/build.py); queries become GET /xrpc/<nsid>, procedures POST; "
            "cross-lexicon refs named, not inlined. Not an official definition."
        ),
        "origins": [v["url"] for v in src["lexicons"].values()],
        "repository": "bluesky-social/atproto",
        "sha256": sha256(definition.read_bytes()),
        "source_id": "bluesky-social/atproto:lexicons",
        "source_updated": None,
        "upstream_sha256": sha256(manifest_bytes),
        "url": "https://github.com/ragentic-io/manifests-catalog/blob/main/drafts/bluesky/definition.openapi.json",
    }
    source = {
        "attribution": "AT Protocol lexicons, Copyright (c) 2022-2026 Bluesky Social PBC, and Contributors",
        "copyright_notice": "Copyright (c) 2022-2026 Bluesky Social PBC, and Contributors",
        "definition_url": f"https://github.com/bluesky-social/atproto/tree/{commit}/lexicons",
        "license_sha256": src["license"]["mit_text_sha256"],
        "license_text": notice + "\n---\n\n" + mit,
        "license_url": f"https://github.com/bluesky-social/atproto/blob/{commit}/LICENSE-MIT.txt",
        "spdx": "MIT OR Apache-2.0",
    }
    steps = [
        {
            "title": "Sign in",
            "text": (
                "Sign in to the Bluesky account this connection should act as. This guide is for accounts "
                "hosted on bsky.social; accounts on another PDS are not supported by this bundle."
            ),
            "links": [("Bluesky", "https://bsky.app/")],
        },
        {
            "title": "Create an app password",
            "text": (
                "Open Settings → Privacy and security → App passwords and add a new app password for Ragentic. "
                "Do not use your main account password. Leave direct-message access off. You can revoke the app "
                "password at any time, which disconnects Ragentic."
            ),
            "links": [("App passwords", "https://bsky.app/settings/app-passwords")],
        },
        {
            "title": "Test and save",
            "text": (
                "Enter your handle (for example alice.bsky.social) or DID and the app password. Test creates a "
                "session at bsky.social and reads com.atproto.server.getSession; it posts nothing. Save encrypts "
                "the handle and app password after a successful Test; Ragentic renews the short-lived session "
                "token from them. Reading profiles, feeds and threads also works without an account at "
                "public.api.bsky.app."
            ),
            "links": [
                ("Bluesky HTTP API reference", "https://docs.bsky.app/docs/category/http-reference"),
                ("Rate limits", "https://docs.bsky.app/docs/advanced-guides/rate-limits"),
            ],
        },
    ]
    return payload(
        app,
        "Bluesky",
        "1.0.0-draft",
        provider,
        "https://bsky.social",
        document,
        f"Connect to Bluesky (AT Protocol) with an independent Ragentic integration: read profiles, feeds, threads and search, and post with an app password. {attribution_text(provider).split('. ', 1)[1]}",
        {
            "credential": {"service": "https://bsky.social", "type": "atproto_session"},
            "probe": probe("https://bsky.social/xrpc/com.atproto.server.getSession", ["did"]),
        },
        steps,
        "atproto",
        prov,
        rights(provider, None, source),
        "draft_unsigned_requires_ragentic_atproto_session",
        {
            "authentication": True,
            "branding": True,
            "connection_test": True,
            "external_references": [
                "Requires Ragentic's atproto_session credential type (ragentic-io/ragentic PR on branch feat/social-connectors-catalog); older Ragentic servers reject this bundle's setup."
            ],
            "rights": True,
            "setup_guide": True,
            "source_currency": True,
        },
        username_label="Bluesky handle or DID",
        token_label="Bluesky app password",
    )


def build_x(x_spec):
    app, provider = "x", "X"
    src = load(DRAFTS / "x/sources/source.json")["definition"]
    raw = pathlib.Path(x_spec).read_bytes() if x_spec else urllib.request.urlopen(src["url"], timeout=60).read()
    if sha256(raw) != src["sha256"]:
        raise SystemExit(
            f"X definition changed upstream: got {sha256(raw)}, pinned {src['sha256']}. "
            "Review the new document and update drafts/x/sources/source.json deliberately."
        )
    document = json.loads(raw)
    assert sha256(canonical(document)) == src["document_sha256"]
    prov = {
        "commit": None,
        "fetched_at": src["fetched_at"],
        "license": {
            "name": src["license_as_stated"]["name"],
            "sha256": None,
            "url": src["license_as_stated"]["url"],
        },
        "normalization": "JSON parsed and embedded unchanged; document_sha256 in drafts/x/sources/source.json is the sorted-key compact JSON hash",
        "origins": [src["url"]],
        "repository": None,
        "sha256": src["sha256"],
        "source_id": "api.x.com:/2/openapi.json",
        "source_updated": None,
        "upstream_sha256": src["sha256"],
        "url": src["url"],
    }
    source = {
        "attribution": "X API v2 OpenAPI definition published by X at https://api.x.com/2/openapi.json",
        "definition_url": src["url"],
        "license_sha256": None,
        "license_text": None,
        "license_url": "https://docs.x.com/developer-terms/policy",
        "license_url_as_stated": src["license_as_stated"]["url"],
        "spdx": "LicenseRef-X-Developer-Agreement",
        "terms_note": (
            "No open-source licence is stated. The definition's info.license names the X Developer Agreement "
            "and Policy at a URL that now answers 404 (the terms moved to license_url); their text is not reproduced here. Redistribution of the definition inside a signed "
            "bundle is not expressly granted by those terms and needs DJ's review before publication."
        ),
    }
    steps = [
        {
            "title": "Create an X app",
            "text": (
                "In the X Developer Console create a Project and App, enable OAuth 2.0 user authentication as a "
                "confidential Web App, and buy pay-per-use credits. X charges per request (for example about "
                "$0.015 per post created and $0.010 per user read at the time of writing) and caps pay-per-use "
                "at 3 million post reads per month. "
                + callback_step("the app's User authentication settings")
            ),
            "links": [
                ("X Developer Console", "https://console.x.com/"),
                ("Pricing", "https://docs.x.com/x-api/getting-started/pricing"),
            ],
        },
        {
            "title": "Authorize",
            "text": (
                "Connect opens X to authorize the scopes tweet.read, tweet.write, users.read and offline.access "
                "with PKCE (S256). That lets Ragentic read your timeline and posts, publish and delete posts as "
                "you, and refresh the two-hour access token. App-only bearer tokens (read-only) are not used by "
                "this connection."
            ),
            "links": [
                ("OAuth 2.0 with PKCE", "https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code"),
            ],
        },
        {
            "title": "Verify and save",
            "text": (
                "After you approve, Ragentic reads GET /2/users/me to confirm the account (one user read, which X "
                "bills) and posts nothing, then saves the encrypted tokens. Rate limits apply per user per "
                "15 minutes."
            ),
            "links": [("Rate limits", "https://docs.x.com/x-api/fundamentals/rate-limits")],
        },
    ]
    return payload(
        app,
        "X",
        src["info_version"],
        provider,
        "https://api.x.com",
        document,
        f"Connect to the X API v2 with an independent Ragentic integration using X's official OpenAPI definition. {attribution_text(provider).split('. ', 1)[1]}",
        {
            "credential": oauth(
                "https://x.com/i/oauth2/authorize",
                "https://api.x.com/2/oauth2/token",
                ["tweet.read", "tweet.write", "users.read", "offline.access"],
                "client_secret_basic",
            ),
            "probe": probe("https://api.x.com/2/users/me", ["data", "id"]),
        },
        steps,
        "oauth",
        prov,
        rights(provider, "https://docs.x.com/developer-terms/display-requirements", source),
        "definition_imported_unsigned_draft",
        {
            "authentication": True,
            "branding": True,
            "connection_test": True,
            "external_references": [
                "The definition's securitySchemes list https://api.x.com/2/oauth2/authorize; X's OAuth guide documents https://x.com/i/oauth2/authorize, which this setup uses. Confirm in a live authorization.",
                "Paid: every call consumes pay-per-use credits, including the connection test.",
            ],
            "rights": True,
            "setup_guide": True,
            "source_currency": True,
        },
    )


def hand_built_prov(app, origins_file, repository_note):
    definition = DRAFTS / app / "definition.openapi.json"
    origins = load(origins_file)
    return {
        "commit": None,
        "fetched_at": origins["documentation"][0]["fetched_at"],
        "license": None,
        "normalization": repository_note,
        "origins": [o["url"] for o in origins["documentation"]],
        "repository": "ragentic-io/manifests-catalog",
        "sha256": sha256(definition.read_bytes()),
        "source_id": f"ragentic-io/manifests-catalog:drafts/{app}/definition.openapi.json",
        "source_updated": None,
        "upstream_sha256": sha256(pathlib.Path(origins_file).read_bytes()),
        "url": f"https://github.com/ragentic-io/manifests-catalog/blob/main/drafts/{app}/definition.openapi.json",
    }


def build_linkedin():
    app, provider = "linkedin", "LinkedIn"
    document = load(DRAFTS / "linkedin/definition.openapi.json")
    prov = hand_built_prov(
        app,
        DRAFTS / "linkedin/sources/origins.json",
        "Hand-built OpenAPI 3.0 from LinkedIn's public documentation (origins); not an official LinkedIn definition. upstream_sha256 is the hash of drafts/linkedin/sources/origins.json.",
    )
    source = {
        "attribution": "Operation definition written by Ragentic from LinkedIn's public documentation",
        "definition_url": prov["url"],
        "license_sha256": None,
        "license_text": None,
        "license_url": None,
        "spdx": None,
        "terms_note": (
            "Not an official LinkedIn definition; no LinkedIn documentation text is reproduced. Use of the "
            "LinkedIn APIs is governed by the LinkedIn API Terms of Use."
        ),
        "terms_url": "https://www.linkedin.com/legal/l/api-terms-of-use",
    }
    steps = [
        {
            "title": "Create a LinkedIn app",
            "text": (
                "In the LinkedIn Developer Portal create an app associated with a LinkedIn Page you administer, "
                "then on the Products tab add the self-serve products Sign In with LinkedIn using OpenID Connect "
                "and Share on LinkedIn. "
                + callback_step("the app's Auth tab (Authorized redirect URLs)")
                + " Posting as an organization (Community Management API) needs LinkedIn's product approval and "
                "is not part of this connection."
            ),
            "links": [
                ("LinkedIn Developer Portal", "https://www.linkedin.com/developers/apps"),
                (
                    "Share on LinkedIn",
                    "https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin",
                ),
            ],
        },
        {
            "title": "Authorize",
            "text": (
                "Connect opens LinkedIn to authorize openid, profile, email and w_member_social. Ragentic can then "
                "read your sign-in profile and create or delete posts as you. Self-serve tokens last 60 days "
                "and LinkedIn does not issue refresh tokens to self-serve apps, so reconnect when it expires."
            ),
            "links": [
                (
                    "Authorization code flow",
                    "https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow",
                ),
            ],
        },
        {
            "title": "Verify and save",
            "text": (
                "After you approve, Ragentic reads GET /v2/userinfo to confirm the member (it posts nothing), then "
                "saves the encrypted token. Requests send LinkedIn-Version 202610; daily rate limits are shown "
                "on your app's Analytics tab."
            ),
            "links": [
                (
                    "Sign In with LinkedIn using OpenID Connect",
                    "https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2",
                ),
            ],
        },
    ]
    return payload(
        app,
        "LinkedIn",
        "202610",
        provider,
        "https://api.linkedin.com",
        document,
        f"Connect a LinkedIn member account with an independent Ragentic integration: sign-in profile and member posts (self-serve products only). {attribution_text(provider).split('. ', 1)[1]}",
        {
            "credential": oauth(
                "https://www.linkedin.com/oauth/v2/authorization",
                "https://www.linkedin.com/oauth/v2/accessToken",
                ["openid", "profile", "email", "w_member_social"],
                "client_secret_post",
            ),
            "probe": probe("https://api.linkedin.com/v2/userinfo", ["sub"]),
        },
        steps,
        "oauth",
        prov,
        rights(provider, "https://brand.linkedin.com/policies", source),
        "hand_built_definition_unsigned_draft",
        {
            "authentication": True,
            "branding": True,
            "connection_test": True,
            "external_references": [
                "Hand-built definition, not official: compare each operation against the cited documentation before signing.",
                "Requires Ragentic to accept the reviewed headers LinkedIn-Version and X-Restli-Protocol-Version (ragentic-io/ragentic PR on branch feat/social-connectors-catalog).",
                "Ragentic always sends PKCE parameters; LinkedIn documents PKCE only for approved native clients. Confirm in a live authorization that the standard web flow ignores them.",
                "Community Management API (organization posting, reading posts) requires LinkedIn product approval and is excluded.",
            ],
            "rights": True,
            "setup_guide": True,
            "source_currency": True,
        },
        headers={"LinkedIn-Version": "202610", "X-Restli-Protocol-Version": "2.0.0"},
    )


def build_facebook():
    app, provider = "facebook", "Facebook"
    document = load(DRAFTS / "facebook/definition.openapi.json")
    prov = hand_built_prov(
        app,
        DRAFTS / "facebook/sources/origins.json",
        "Hand-built OpenAPI 3.0 for Graph API v26.0 from Meta's public documentation (origins); not an official Meta definition. upstream_sha256 is the hash of drafts/facebook/sources/origins.json.",
    )
    source = {
        "attribution": "Operation definition written by Ragentic from Meta's public Graph API documentation",
        "definition_url": prov["url"],
        "license_sha256": None,
        "license_text": None,
        "license_url": None,
        "spdx": None,
        "terms_note": (
            "Not an official Meta definition; no Meta documentation text is reproduced. Use of the Graph API is "
            "governed by the Meta Platform Terms and Developer Policies."
        ),
        "terms_url": "https://developers.facebook.com/terms/",
    }
    steps = [
        {
            "title": "Create a Meta app",
            "text": (
                "In Meta for Developers create a Business app with Facebook Login for Business and request "
                "pages_show_list, pages_read_engagement and pages_manage_posts. "
                + callback_step("Facebook Login settings (Valid OAuth Redirect URIs)")
                + " Without Meta App Review the app works only for people with a role on the app and Pages they "
                "manage; managing other people's Pages needs App Review and Business Verification."
            ),
            "links": [
                ("Meta for Developers apps", "https://developers.facebook.com/apps/"),
                ("Permissions reference", "https://developers.facebook.com/docs/permissions"),
            ],
        },
        {
            "title": "Authorize",
            "text": (
                "Connect opens Facebook to grant the three Page permissions and choose which Pages to share. "
                "Ragentic stores the resulting user access token. Reading a Page feed and publishing to a Page "
                "need that Page's own access token, which this connection does not obtain yet: listing your Pages "
                "works, Page feed and publishing calls are rejected by Meta until Ragentic adds Page-token support."
            ),
            "links": [("Pages API overview", "https://developers.facebook.com/docs/pages-api/overview")],
        },
        {
            "title": "Verify and save",
            "text": (
                "After you approve, Ragentic reads GET /v26.0/me to confirm the user (it posts nothing), then "
                "saves the encrypted token. Graph API v26.0 is pinned; Meta's Platform and Pages rate limits apply."
            ),
            "links": [("Rate limits", "https://developers.facebook.com/docs/graph-api/overview/rate-limiting")],
        },
    ]
    return payload(
        app,
        "Facebook Pages",
        "v26.0",
        provider,
        "https://graph.facebook.com",
        document,
        f"Connect Facebook Pages through the Meta Graph API v26.0 with an independent Ragentic integration: list your Pages; Page feed and publishing need Page tokens (see setup). {attribution_text(provider).split('. ', 1)[1]}",
        {
            "credential": oauth(
                "https://www.facebook.com/v26.0/dialog/oauth",
                "https://graph.facebook.com/v26.0/oauth/access_token",
                ["pages_show_list", "pages_read_engagement", "pages_manage_posts"],
                "client_secret_post",
            ),
            "probe": probe("https://graph.facebook.com/v26.0/me", ["id"]),
        },
        steps,
        "oauth",
        prov,
        rights(provider, "https://www.meta.com/brand/resources/", source),
        "hand_built_definition_unsigned_draft_page_token_missing",
        {
            "authentication": True,
            "branding": True,
            "connection_test": True,
            "external_references": [
                "Hand-built definition, not official: compare each operation against the cited documentation before signing.",
                "getPageFeed and publishPagePost need a Page access token; Ragentic does not yet derive one from the user token, so those two operations fail until it does.",
                "Meta documents the token exchange as GET with query parameters; Ragentic POSTs a form with client_secret_post and always adds PKCE. Confirm both in a live authorization.",
                "Meta App Review and Business Verification are needed for Pages the app's own role-holders do not manage.",
            ],
            "rights": True,
            "setup_guide": True,
            "source_currency": True,
        },
    )


def main(argv):
    x_spec = None
    if "--x-spec" in argv:
        x_spec = argv[argv.index("--x-spec") + 1]
    for app, build in (
        ("bluesky", build_bluesky),
        ("x", lambda: build_x(x_spec)),
        ("linkedin", build_linkedin),
        ("facebook", build_facebook),
    ):
        p = build()
        write_json(DRAFTS / app / "payload.json", p)
        print(f"{app}: {len(canonical(p))} bytes, {len(p['graph']['nodes']) - 1} operations")


if __name__ == "__main__":
    main(sys.argv[1:])
