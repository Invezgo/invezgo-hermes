"""Live check against api.invezgo.com. Read-only calls only.

    INVEZGO_API_KEY=... python smoke_live.py
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

if not os.environ.get("INVEZGO_API_KEY"):
    sys.exit("INVEZGO_API_KEY not set")

here = Path(__file__).parent
spec = importlib.util.spec_from_file_location("invezgo", here / "__init__.py", submodule_search_locations=[str(here)])
plugin = importlib.util.module_from_spec(spec)
sys.modules["invezgo"] = plugin
spec.loader.exec_module(plugin)
tools = {s["name"]: h for _, s, h in plugin.operations()}

calls = [
    ("invezgo_analysis_information", {"code": "BBCA"}),
    ("invezgo_search_search_stock", {"query": "bank"}),
    ("invezgo_analysis_summary_stock",
     {"code": "BBCA", "from": "2026-11-03", "to": "2026-11-10", "investor": "all", "market": "RG"}),
    ("invezgo_screener_screen", {"body": {"formula": "close > prev"}}),
    ("invezgo_usage_usage_api", {}),
]
failed = 0
for name, args in calls:
    out = tools[name](args)
    err = json.loads(out).get("error") if out.lstrip().startswith("{") else None
    failed += bool(err)
    print(f"{'FAIL' if err else 'OK  '} {name}: {out[:200]}")
sys.exit(failed)
