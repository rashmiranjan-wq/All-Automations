# All-Automations

Private backup of Neuron notebooks for `default/rashmi-ranjan` on
[Neuron](https://neuron.dp.navi-tech.in).

## Layout

- `default/rashmi-ranjan/notebooks/` — Jupyter automation notebooks
- `default/rashmi-ranjan/lib/` — shared `neuron_runtime` helpers
- `default/rashmi-ranjan/pipeline/` — Elyra pipeline definitions and exported DAGs

## Running on Neuron

1. Sync this tree into your Neuron workspace under the same paths.
2. Keep credentials in Neuron `secrets/` (not in git): Google service account JSON, Slack token, Trino env.
3. Notebooks prepend `../lib` (or `/home/jovyan/work/default/rashmi-ranjan/lib`) for imports.

## Sync from Neuron

Re-download from Neuron (requires `~/.cursor/mcp.json` neuron env):

```bash
python3 sync_from_neuron.py
```

## Publish to GitHub

The Cursor GitHub MCP token cannot create new repositories. One-time setup:

Remote: `https://github.com/rashmiranjan-wq/All-Automations`

```bash
python3 push_to_github.py
```
