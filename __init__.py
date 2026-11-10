"""Invezgo Hermes plugin: one tool per operation in spec.json (Invezgo OpenAPI).

Update to a newer API: replace spec.json, restart Hermes.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from agent.secret_scope import get_secret  # Hermes route: honours the active profile
except ImportError:  # outside Hermes (test_plugin.py, smoke_live.py)
    def get_secret(name, default=None):
        return os.environ.get(name, default)

SPEC = json.loads((Path(__file__).parent / "spec.json").read_text(encoding="utf-8"))
BASE_URL = SPEC["servers"][0]["url"].rstrip("/")
METHODS = ("get", "post", "put", "patch", "delete")
# Non-GET ops change user data (watchlist, journal, alert, ...); off unless INVEZGO_ALLOW_WRITE=1.
READ_ONLY_POSTS = {"ScreenerController_screen"}
MAX_DESC = 800  # keeps all 91 schemas ~120k chars; the model sees real response fields anyway
MAX_RESULT = 60_000  # shortcut: hard cut of huge responses, upgrade to pagination hints if models need full data


def _deref(node, depth=0):
    """Inline #/components/... $refs so the model sees plain JSON Schema."""
    if depth > 8:
        return {}
    if isinstance(node, dict):
        if "$ref" in node:
            target = SPEC
            for part in node["$ref"].lstrip("#/").split("/"):
                target = target[part]
            return _deref(target, depth + 1)
        return {k: _deref(v, depth) for k, v in node.items() if k not in ("example", "examples")}
    if isinstance(node, list):
        return [_deref(v, depth) for v in node]
    return node


def _snake(s):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s).lower()  # shareholderKSEI -> shareholder_ksei


def _tool_name(op_id):
    ctrl, _, method = op_id.partition("_")
    return f"invezgo_{_snake(ctrl.removesuffix('Controller'))}_{_snake(method)}"


def _description(op):
    text = (op.get("description") or "").strip()
    if "[English]" in text:  # spec is bilingual ID/EN; English half is enough for the model
        text = text.split("[English]", 1)[1].strip()
    text = re.sub(r"\n\s+", "\n", text)
    full = f"{op.get('summary', '')}. {text}".strip(". ")
    return full[:MAX_DESC]


def _build(path, method, op):
    params = [_deref(p) for p in op.get("parameters", [])]
    props, required = {}, []
    for p in params:
        schema = dict(p.get("schema", {}))
        if p.get("description"):
            schema["description"] = p["description"].strip()[:500]
        props[p["name"]] = schema
        if p.get("required"):
            required.append(p["name"])
    body = op.get("requestBody")
    if body:
        schema = _deref(body["content"]["application/json"]["schema"])
        schema["description"] = (body.get("description") or "JSON request body").strip()
        props["body"] = schema
        if body.get("required"):
            required.append("body")

    schema = {
        "name": _tool_name(op["operationId"]),
        "description": _description(op),
        "parameters": {"type": "object", "properties": props, "required": required},
    }
    path_names = {p["name"] for p in params if p["in"] == "path"}
    query_names = {p["name"] for p in params if p["in"] == "query"}

    def handler(args: dict, **kwargs) -> str:
        try:
            url = BASE_URL + re.sub(
                r"\{(\w+)\}", lambda m: urllib.parse.quote(str(args.get(m.group(1), "")), safe=""), path
            )
            missing = [n for n in path_names if args.get(n) in (None, "")]
            if missing:
                return json.dumps({"error": f"Missing path parameter(s): {missing}"})
            query = {k: str(v).lower() if isinstance(v, bool) else v
                     for k, v in args.items() if k in query_names and v is not None}
            if query:
                url += "?" + urllib.parse.urlencode(query, doseq=True)
            data = json.dumps(args["body"]).encode() if "body" in args else None
            req = urllib.request.Request(url, data=data, method=method.upper(), headers={
                "Authorization": f"Bearer {get_secret('INVEZGO_API_KEY') or ''}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            })
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode("utf-8", "replace")
            if len(text) > MAX_RESULT:
                text = json.dumps({"truncated": True, "chars": len(text), "data": text[:MAX_RESULT]})
            return text or json.dumps({"ok": True})
        except urllib.error.HTTPError as e:
            return json.dumps({"error": f"HTTP {e.code}", "detail": e.read().decode("utf-8", "replace")[:2000]})
        except Exception as e:  # handlers must never raise
            return json.dumps({"error": str(e)})

    return schema, handler


def operations():
    try:
        allow_write = get_secret("INVEZGO_ALLOW_WRITE") == "1"
    except Exception:  # unscoped under multiplexing: fail closed to read-only
        allow_write = False
    for path, item in SPEC["paths"].items():
        for method in METHODS:
            op = item.get(method)
            if not op:
                continue
            if method != "get" and op["operationId"] not in READ_ONLY_POSTS and not allow_write:
                continue
            tag = (op.get("tags") or ["misc"])[0]
            yield "invezgo_" + re.sub(r"\W+", "_", tag.lower()).strip("_"), *_build(path, method, op)


def register(ctx):
    for toolset, schema, handler in operations():
        ctx.register_tool(name=schema["name"], toolset=toolset, schema=schema, handler=handler)
