"""Self-check: python test_plugin.py (no network, no Hermes needed)."""
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest import mock

here = Path(__file__).parent
spec = importlib.util.spec_from_file_location("invezgo", here / "__init__.py", submodule_search_locations=[str(here)])
plugin = importlib.util.module_from_spec(spec)
sys.modules["invezgo"] = plugin
spec.loader.exec_module(plugin)


class Ctx:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, toolset, schema, handler, **_):
        assert name not in self.tools, f"duplicate tool {name}"
        assert len(name) <= 64 and name == schema["name"]
        json.dumps(schema)  # must be serialisable
        self.tools[name] = handler


ctx = Ctx()
plugin.register(ctx)
assert "invezgo_analysis_summary_stock" in ctx.tools
assert "invezgo_screener_screen" in ctx.tools
assert "invezgo_journals_delete_watchlists" not in ctx.tools, "writes must be off by default"

with mock.patch.dict(os.environ, {"INVEZGO_ALLOW_WRITE": "1"}):
    full = Ctx()
    plugin.register(full)
total = sum(1 for p in plugin.SPEC["paths"].values() for m in plugin.METHODS if m in p)
assert len(full.tools) == total, (len(full.tools), total)

# plugin.yaml provides_tools must list every tool (Hermes validate fails otherwise); --sync rewrites it.
manifest = here / "plugin.yaml"
head = manifest.read_text(encoding="utf-8").split("provides_tools:")[0].rstrip() + "\n"
expected = head + "provides_tools:\n" + "".join(f"  - {n}\n" for n in sorted(full.tools))
entry = here / "catalog" / "invezgo.yaml"  # draft for the hermes-agent plugin-catalog PR
entry_head = entry.read_text(encoding="utf-8").split("  provides_tools:")[0]
entry_expected = (entry_head + "  provides_tools:\n" + "".join(f"    - {n}\n" for n in sorted(full.tools))
                  + "  provides_hooks: []\n  provides_middleware: []\n  requires_env:\n    - INVEZGO_API_KEY\n")
if "--sync" in sys.argv:
    manifest.write_text(expected, encoding="utf-8")
    entry.write_text(entry_expected, encoding="utf-8")
assert entry.read_text(encoding="utf-8") == entry_expected, "catalog/invezgo.yaml out of date: --sync"
assert manifest.read_text(encoding="utf-8") == expected, "plugin.yaml out of date: python test_plugin.py --sync"

# URL/query/auth building without network
captured = {}


class FakeResp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read(self):
        return b'{"ok":1}'


def fake_open(req, timeout):
    captured.update(url=req.full_url, method=req.get_method(), auth=req.get_header("Authorization"))
    return FakeResp()


with mock.patch.dict(os.environ, {"INVEZGO_API_KEY": "k"}), mock.patch("urllib.request.urlopen", fake_open):
    out = ctx.tools["invezgo_analysis_summary_stock"](
        {"code": "BBCA", "from": "2026-11-01", "to": "2026-11-10", "investor": "all", "market": "RG"})
assert out == '{"ok":1}'
assert captured["url"].startswith("https://api.invezgo.com/analysis/summary/stock/BBCA?"), captured
assert "from=2026-11-01" in captured["url"] and captured["auth"] == "Bearer k"
assert "error" in json.loads(ctx.tools["invezgo_analysis_information"]({}))

print(f"OK: {len(ctx.tools)} read tools, {len(full.tools)} with INVEZGO_ALLOW_WRITE=1")
