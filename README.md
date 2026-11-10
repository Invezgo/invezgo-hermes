# Invezgo for Hermes

Indonesia Stock Exchange (IDX / BEI) data for [Hermes Agent](https://hermes-agent.nousresearch.com), powered by the [Invezgo API](https://invezgo.com).

Ask your agent things like *"Which brokers accumulated BBCA this week?"*, *"Show foreign net buy leaders today"* or *"Screen for stocks closing above yesterday with volume over 1M"*. Hermes picks the right Invezgo tool and answers from live data.

## What you get

91 read-only tools, one per endpoint of the Invezgo OpenAPI spec, grouped into toolsets:

| Toolset | Covers |
|---|---|
| `invezgo_indonesia_stock_data_api` | Company profile, price charts and indicators, intraday, order book and queue, running trade, broker summary and inventory, broker/sector stalker, sector rotation, shareholders (KSEI, >1%, >5%, insiders, relations), financial statements, key stats, calendar, news, disclosures, top movers / foreign / accumulation |
| `invezgo_batch` | Full-day intraday and order-book history |
| `invezgo_search` | Stock and user search |
| `invezgo_screener` | Run formula screens, list saved screeners |
| `invezgo_personal` | Your portfolio, watchlists, journal and trades (read) |
| `invezgo_post` | Community posts and comments |
| `invezgo_live_alert` | Your price alerts (read) |
| `invezgo_usage` | Your API quota and request logs |

Tool names follow `invezgo_<area>_<operation>`, for example `invezgo_analysis_summary_stock`.

## Requirements

- Hermes Agent `>= 0.23.1`
- An Invezgo account with API access. Create a key at <https://invezgo.com/setting/api>.

## Install

```bash
hermes plugins install invezgo
hermes plugins enable invezgo
```

Hermes asks for `INVEZGO_API_KEY` during install. Or install from source:

```bash
git clone https://github.com/Invezgo/invezgo-hermes ~/.hermes/plugins/invezgo
hermes plugins enable invezgo
```

### Recommended: Tool Search

91 tool schemas take a noticeable share of the context window. Turn on Hermes [Tool Search](https://hermes-agent.nousresearch.com/docs/user-guide/features/tool-search) so the model loads Invezgo tools on demand, or disable the toolsets you don't need with `hermes tools`.

## Write access (opt-in)

By default the plugin cannot change anything in your Invezgo account. Set `INVEZGO_ALLOW_WRITE=1` to also register the 18 tools that create, update or delete watchlists, journal entries, trades, alerts and saved screeners. Hermes's normal approval flow still applies to every call.

## Disclosure

- **Network:** every tool call is an HTTPS request to `https://api.invezgo.com`, authenticated with your API key. No other hosts are contacted.
- **Quota:** calls count against your Invezgo plan's API quota (`invezgo_usage_usage_api` shows what's left).
- **Data flow:** results enter the session context and are sent to your model provider. This includes your portfolio, watchlists, journal and trades if the model calls those tools.
- **Credentials:** the API key is read only through Hermes's secret route (`agent.secret_scope.get_secret`). The plugin stores nothing, runs no background processes or shell commands, and has no telemetry.
- **Size limit:** responses over 60,000 characters are cut off and marked `"truncated": true`. Use narrower date ranges or `page`/`limit` when that happens.

## Development

```bash
python test_plugin.py --sync              # regenerate provides_tools in plugin.yaml + offline self-check
INVEZGO_API_KEY=... python smoke_live.py  # 5 read-only calls against the live API
hermes plugins validate . --install-deps
```

Tools are generated at load time from `spec.json`. To follow a new API version, replace `spec.json`, run `python test_plugin.py --sync` and bump `version` in `plugin.yaml`.

## License

MIT
