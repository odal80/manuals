#!/usr/bin/env python3
"""Poll a Google Drive folder and announce new/updated files to Slack.

Runs in GitHub Actions. Reads the folder with a Google service account,
diffs against a committed manifest, and posts changes to a Slack incoming
webhook. On the very first run it only records a baseline (no spam).

Environment:
  GDRIVE_SA_JSON   service account key JSON (string)  [required]
  SLACK_WEBHOOK_URL  Slack incoming webhook URL        [required]
  DRIVE_FOLDER_ID  Drive folder id (defaults to the configured one)
  MANIFEST_PATH    path to the state manifest file
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "1g_nxqHfG4V44AXEVoN5hvrhmC7Ho5FbY")
MANIFEST_PATH = Path(os.environ.get("MANIFEST_PATH", "state/drive-manifest.json"))
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_service():
    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["GDRIVE_SA_JSON"]), scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_files(service, folder_id):
    """Recursively list all non-folder files under folder_id."""
    files = {}
    stack = [folder_id]
    seen = set()
    while stack:
        fid = stack.pop()
        if fid in seen:
            continue
        seen.add(fid)
        page_token = None
        while True:
            resp = (
                service.files()
                .list(
                    q=f"'{fid}' in parents and trashed=false",
                    fields="nextPageToken, files(id,name,mimeType,modifiedTime,webViewLink)",
                    pageSize=1000,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    pageToken=page_token,
                )
                .execute()
            )
            for f in resp.get("files", []):
                if f["mimeType"] == "application/vnd.google-apps.folder":
                    stack.append(f["id"])
                else:
                    files[f["id"]] = f
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    return files


def load_manifest():
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def save_manifest(files):
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        fid: {
            "name": f["name"],
            "modifiedTime": f["modifiedTime"],
            "webViewLink": f.get("webViewLink", ""),
        }
        for fid, f in files.items()
    }
    MANIFEST_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def post_to_slack(webhook, text, blocks):
    payload = json.dumps({"text": text, "blocks": blocks}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()


def build_blocks(new_files, updated_files):
    folder_link = f"https://drive.google.com/drive/folders/{FOLDER_ID}"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📂 구글 드라이브 업데이트 알림"},
        }
    ]

    def section(title, items):
        lines = []
        for f in items:
            link = f.get("webViewLink") or folder_link
            lines.append(f"• <{link}|{f['name']}>")
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{title}*\n" + "\n".join(lines)},
            }
        )

    if new_files:
        section(f"🆕 새 파일 ({len(new_files)})", new_files)
    if updated_files:
        section(f"✏️ 변경된 파일 ({len(updated_files)})", updated_files)
    blocks.append(
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"<{folder_link}|드라이브 폴더 열기>"}
            ],
        }
    )
    return blocks


def main():
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not os.environ.get("GDRIVE_SA_JSON") or not webhook:
        print(
            "[skip] GDRIVE_SA_JSON and/or SLACK_WEBHOOK_URL not set. "
            "Configure repo secrets to enable notifications."
        )
        return 0

    service = get_service()
    current = list_files(service, FOLDER_ID)
    previous = load_manifest()

    if previous is None:
        save_manifest(current)
        print(f"[baseline] recorded {len(current)} files; no notification sent.")
        return 0

    new_files, updated_files = [], []
    for fid, f in current.items():
        if fid not in previous:
            new_files.append(f)
        elif previous[fid].get("modifiedTime") != f["modifiedTime"]:
            updated_files.append(f)

    if new_files or updated_files:
        new_files.sort(key=lambda x: x["name"].lower())
        updated_files.sort(key=lambda x: x["name"].lower())
        summary = f"드라이브 업데이트: 새 파일 {len(new_files)}개, 변경 {len(updated_files)}개"
        post_to_slack(webhook, summary, build_blocks(new_files, updated_files))
        print(f"[notified] {summary}")
    else:
        print("[ok] no changes.")

    save_manifest(current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
