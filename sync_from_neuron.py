#!/usr/bin/env python3
"""One-shot: download rashmi-ranjan Neuron assets and prepare git tree."""
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional, Set

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR
NEURON_SCRIPTS = Path.home() / ".cursor/skills/i-dont-like-databricks/scripts"
sys.path.insert(0, str(NEURON_SCRIPTS))

from neuron import jupyter_get, load_config, ensure_server  # noqa: E402

BASE = "default/rashmi-ranjan"
NOTEBOOKS = f"{BASE}/notebooks"
LIB = f"{BASE}/lib"
PIPELINE = f"{BASE}/pipeline"

SECRET_PATTERNS = [
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    re.compile(r'"type"\s*:\s*"service_account"'),
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\."),  # JWT-like
]


def list_dir(cfg, path: str) -> list[dict]:
    resp = jupyter_get(cfg, f"contents/{path}")
    resp.raise_for_status()
    data = resp.json()
    if data.get("type") == "directory":
        return data.get("content", [])
    return []


def download_file(cfg, remote_path: str, local_path: Path) -> None:
    resp = jupyter_get(cfg, f"contents/{remote_path}", params={"content": "1"})
    resp.raise_for_status()
    body = resp.json()
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if body["type"] == "notebook":
        content = body["content"]
        clear_notebook_outputs(content)
        local_path.write_text(json.dumps(content, indent=1) + "\n", encoding="utf-8")
    elif body["type"] == "file":
        local_path.write_text(body["content"], encoding="utf-8")
    else:
        raise ValueError(f"Unsupported type {body['type']} at {remote_path}")


def clear_notebook_outputs(nb: dict) -> None:
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None


def scan_text(path: Path, text: str) -> list[str]:
    hits = []
    for pat in SECRET_PATTERNS:
        if pat.search(text):
            hits.append(pat.pattern[:40])
    return hits


def download_tree(cfg, remote_dir: str, local_dir: Path, extensions: Optional[Set[str]]) -> int:
    count = 0
    for item in list_dir(cfg, remote_dir):
        name = item["name"]
        if name.startswith("."):
            continue
        remote = f"{remote_dir}/{name}" if remote_dir else name
        local = local_dir / name
        if item["type"] == "directory":
            if name == "data" and "notebooks" in remote_dir:
                continue
            count += download_tree(cfg, remote, local, extensions)
        elif item["type"] in ("notebook", "file"):
            if extensions and not any(name.endswith(ext) for ext in extensions):
                continue
            download_file(cfg, remote, local)
            text = local.read_text(encoding="utf-8", errors="replace")
            bad = scan_text(local, text)
            if bad:
                print(f"WARNING possible secret in {local}: {bad}")
            count += 1
            print(f"  {remote}")
    return count


def write_meta_files() -> None:
    gitignore = """secrets/
**/data/
*.env
.env.*
__pycache__/
.ipynb_checkpoints/
.DS_Store
sync_from_neuron.py
"""
    (REPO_ROOT / ".gitignore").write_text(gitignore, encoding="utf-8")
    readme = """# neuron-notebooks-rashmi

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

## Sync

Re-download from Neuron with the bundled script (requires `~/.cursor/mcp.json` neuron env):

```bash
python3 sync_from_neuron.py
```
"""
    (REPO_ROOT / "README.md").write_text(readme, encoding="utf-8")


def main() -> int:
    cfg = load_config()
    ensure_server(cfg)
    os.chdir(REPO_ROOT)
    total = 0
    print("Downloading notebooks...")
    total += download_tree(cfg, NOTEBOOKS, REPO_ROOT / NOTEBOOKS, {".ipynb"})
    print("Downloading lib...")
    total += download_tree(cfg, LIB, REPO_ROOT / LIB, {".py"})
    print("Downloading pipeline...")
    total += download_tree(
        cfg, PIPELINE, REPO_ROOT / PIPELINE, {".pipeline", ".py"}
    )
    write_meta_files()
    print(f"Done. {total} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
