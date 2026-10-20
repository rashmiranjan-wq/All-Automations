#!/usr/bin/env python3
"""Push local main branch to github.com/rashmiranjan-wq/neuron-notebooks-rashmi."""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = "neuron-notebooks-rashmi"
OWNER = "rashmiranjan-wq"
ROOT = Path(__file__).resolve().parent


def load_token() -> str:
    secrets = Path.home() / ".cursor/mcp.secrets.env"
    if not secrets.exists():
        raise SystemExit(f"Missing {secrets}")
    for line in secrets.read_text().splitlines():
        if line.startswith("GITHUB_MCP_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("GITHUB_MCP_TOKEN not found in mcp.secrets.env")


def repo_exists(token: str) -> bool:
    url = f"https://api.github.com/repos/{OWNER}/{REPO}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def create_repo(token: str) -> bool:
    url = "https://api.github.com/user/repos"
    body = json.dumps(
        {
            "name": REPO,
            "private": True,
            "description": "Neuron notebooks (rashmi-ranjan)",
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status in (200, 201)
    except urllib.error.HTTPError as e:
        print(e.read().decode(), file=sys.stderr)
        return False


def git_push(token: str) -> None:
    remote = f"https://github.com/{OWNER}/{REPO}.git"
    subprocess.run(["git", "remote", "remove", "origin"], cwd=ROOT, check=False)
    subprocess.run(["git", "remote", "add", "origin", remote], cwd=ROOT, check=True)
    header = f"AUTHORIZATION: bearer {token}"
    subprocess.run(
        [
            "git",
            "-c",
            f"http.extraHeader={header}",
            "push",
            "-u",
            "origin",
            "main",
        ],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    token = load_token()
    if not repo_exists(token):
        print("Repository not found; attempting create...")
        if not create_repo(token):
            print(
                f"\nCreate the repo manually: https://github.com/new?name={REPO}&visibility=private\n"
                "Then re-run: python3 push_to_github.py\n",
                file=sys.stderr,
            )
            return 1
    git_push(token)
    print(f"https://github.com/{OWNER}/{REPO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
