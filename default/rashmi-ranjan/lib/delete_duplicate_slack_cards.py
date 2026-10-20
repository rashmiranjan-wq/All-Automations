#!/usr/bin/env python3
"""Delete duplicate audit-card Slack posts from tonight's batch (keep oldest)."""

import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "_shared"))
from neuron_runtime import load_slack_token

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Channels used by run_slack_prod_once.py (22-card batch)
CHANNELS = [
    "C07K5MBQVDW",  # procex-daily-updates
    "C08CXD3QVLH",  # procex-internal-metrics / playground
    "C0B77EWGSRE",  # motor sales (mentions)
]

# Titles from the 22-card prod list only
ALLOWED_TITLES = {
    "Claims Audit Summary Snapshot",
    "Apex Audit Summary Snapshot",
    "VKYC Audit Summary Snapshot",
    "GI Sales Audit Summary Snapshot",
    "GI Renewal Audit Summary Snapshot",
    "GI Sales & Renewal Audit Summary Snapshot",
    "GI Welcome Calling Audit Summary Snapshot",
    "Motor Sales Audit Summary Snapshot",
    "GI Sales Audit of Audits Summary Snapshot",
    "VKYC Audit of Audits Summary Snapshot",
    "Claims Audit of Audits Summary Snapshot",
    "Motor Insurance Sales Audit of Audits Summary Snapshot",
    "GI Renewal Audit of Audits Summary Snapshot",
    "CX S2 audit summary",
    "Google Sheet Snapshot",
    "CX AOA Audit of Audits Summary Snapshot",
    "CL Apex Audit of Audit Summary Snapshot",
}

# Only posts in the last 4 hours (tonight's duplicate batches)
OLDEST_TS = time.time() - 4 * 3600


def message_title(msg):
    files = msg.get("files") or []
    if files:
        return (files[0].get("title") or files[0].get("name") or "").strip()
    return ""


def is_our_card(msg, bot_user_id):
    if float(msg.get("ts", 0)) < OLDEST_TS:
        return False
    poster = msg.get("user") or msg.get("bot_id")
    if poster != bot_user_id and msg.get("user") != bot_user_id:
        return False
    title = message_title(msg)
    return title in ALLOWED_TITLES


def main():
    token = load_slack_token()
    if not token:
        print("No Slack token in environment", file=sys.stderr)
        return 1
    client = WebClient(token=token, timeout=60)
    auth = client.auth_test()
    bot_user_id = auth["user_id"]
    print(f"bot_user_id={bot_user_id} window_since_ts={OLDEST_TS:.0f}")
    deleted = 0
    errors = 0

    for channel in CHANNELS:
        try:
            resp = client.conversations_history(channel=channel, limit=120)
        except SlackApiError as e:
            print(f"history failed {channel}: {e.response.get('error')}")
            errors += 1
            continue

        buckets = defaultdict(list)
        for msg in resp.get("messages", []):
            if not is_our_card(msg, bot_user_id):
                continue
            key = message_title(msg)
            buckets[key].append(msg)

        for title, msgs in buckets.items():
            if len(msgs) < 2:
                continue
            msgs.sort(key=lambda m: float(m["ts"]))
            # Keep earliest from tonight; delete only extra copies (2nd batch)
            for dup in msgs[1:]:
                ts = dup["ts"]
                try:
                    client.chat_delete(channel=channel, ts=ts)
                    print(f"deleted {channel} ts={ts} title={title[:50]}")
                    deleted += 1
                except SlackApiError as e:
                    print(f"delete failed {channel} ts={ts}: {e.response.get('error')}")
                    errors += 1

    print(f"Done: deleted={deleted} errors={errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
