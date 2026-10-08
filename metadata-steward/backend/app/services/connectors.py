"""Metadata source connectors.

Two families:

* **Upload parsers** — turn a file (CSV, Excel, JSON, Slack export ZIP/JSON,
  Teams export JSON/CSV) into a list of :class:`DocInput`. These run offline.
* **Live API connectors** — pull messages from Slack / Microsoft Teams via
  their HTTP APIs using a caller-supplied token. These share the same
  :class:`DocInput` contract so ingestion is identical downstream.

Connectors only *read*; they never write to the catalog.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class DocInput:
    """A normalized raw item to persist as a ``SourceDocument``."""

    external_id: str | None = None
    kind: str = "message"  # message | row | file
    author: str | None = None
    channel: str | None = None
    ts: datetime | None = None
    content: str = ""
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "external_id": self.external_id,
            "kind": self.kind,
            "author": self.author,
            "channel": self.channel,
            "ts": self.ts,
            "content": self.content,
            "meta": self.meta,
        }


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _slack_ts(value) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError):
        return None


def _iso(value) -> datetime | None:
    """Parse an ISO-8601 timestamp string (Teams Graph) into naive UTC."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (TypeError, ValueError):
        return None


_AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".oga", ".opus", ".aac", ".mpga", ".mpeg")
_VIDEO_EXTS = (".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v", ".mpg")


def kind_from_filename(filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".zip"):
        return "slack"
    if name.endswith(".csv"):
        return "csv"
    if name.endswith((".xlsx", ".xls")):
        return "excel"
    if name.endswith(_VIDEO_EXTS):
        return "video"
    if name.endswith(_AUDIO_EXTS):
        return "audio"
    return "json"


def detect_kind(filename: str, file_bytes: bytes | None = None) -> str:
    """Detect the channel for a JSON file by sniffing its content (Slack vs
    Teams vs generic)."""
    kind = kind_from_filename(filename)
    if kind == "json" and file_bytes is not None:
        try:
            text = file_bytes.decode("utf-8-sig", errors="replace")[:8000].lower()
        except Exception:  # noqa: BLE001
            text = ""
        if '"createddatetime"' in text or '"body"' in text or '"messagetype"' in text:
            return "teams"
        if '"thread_ts"' in text or '"ts"' in text or '"messages"' in text:
            return "slack"
    return kind


# --------------------------------------------------------------------------- #
# Upload parsers
# --------------------------------------------------------------------------- #
def parse_upload(filename: str, file_bytes: bytes) -> list[DocInput]:
    """Dispatch an uploaded file to the right parser by extension."""
    name = (filename or "").lower()
    if name.endswith(".zip"):
        return _parse_zip(file_bytes)
    if name.endswith(".csv"):
        return _parse_csv(file_bytes)
    if name.endswith((".xlsx", ".xls")):
        return _parse_excel(file_bytes)
    return _parse_json(file_bytes)


def _rows_to_docs(rows: list[dict], *, sheet: str | None = None) -> list[DocInput]:
    docs: list[DocInput] = []
    for i, row in enumerate(rows):
        if not row:
            continue
        # Skip a header-only row (all values equal their keys or empty).
        vals = [str(v).strip() for v in row.values() if v is not None]
        if not vals:
            continue
        content_lines = [f"{k}: {v}" for k, v in row.items() if v is not None and str(v).strip() != ""]
        content = "; ".join(content_lines)
        docs.append(
            DocInput(
                external_id=f"row-{i}",
                kind="row",
                author=None,
                channel=sheet,
                ts=None,
                content=content,
                meta={"row": row, "index": i, "sheet": sheet},
            )
        )
    return docs


def _parse_csv(file_bytes: bytes) -> list[DocInput]:
    text = file_bytes.decode("utf-8-sig", errors="replace")
    sample = text[:2048]
    delimiter = ","
    for cand in ("\t", ";", "|"):
        if sample.count(cand) > sample.count(","):
            delimiter = cand
            break
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = [dict(r) for r in reader]
    return _rows_to_docs(rows)


def _parse_excel(file_bytes: bytes) -> list[DocInput]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    docs: list[DocInput] = []
    for ws in wb.worksheets:
        rows_iter = ws.iter_rows(values_only=True)
        header = next(rows_iter, None)
        if not header:
            continue
        headers = [str(h).strip() if h is not None else "" for h in header]
        for i, values in enumerate(rows_iter):
            if values is None or all(v is None for v in values):
                continue
            row = {headers[j]: values[j] for j in range(min(len(headers), len(values)))}
            docs.extend(_rows_to_docs([row], sheet=ws.title))
    return docs


def _slack_message_to_doc(msg: dict, users: dict, channel: str) -> DocInput:
    text = str(msg.get("text") or "").strip()
    files = msg.get("files") or []
    if files:
        titles = [str(f.get("title") or f.get("name") or "") for f in files]
        titles = [t for t in titles if t]
        if titles and not text:
            text = "Shared file(s): " + ", ".join(titles)
        elif titles:
            text += "\n[files: " + ", ".join(titles) + "]"
    author_id = str(msg.get("user") or msg.get("username") or "") or None
    author = users.get(author_id, author_id) if author_id else None
    return DocInput(
        external_id=str(msg.get("ts") or msg.get("client_msg_id") or ""),
        kind="message",
        author=author,
        channel=channel,
        ts=_slack_ts(msg.get("ts")),
        content=text,
        meta={
            "subtype": msg.get("subtype"),
            "thread_ts": msg.get("thread_ts"),
            "reactions": [r.get("name") for r in (msg.get("reactions") or [])],
        },
    )


def _parse_slack_json(payload) -> list[DocInput]:
    """Parse a Slack export (single channel, workspace object, or message list)."""
    docs: list[DocInput] = []
    users: dict = {}

    if isinstance(payload, dict):
        users_map = payload.get("users") or payload.get("user_profiles")
        if isinstance(users_map, list):
            for u in users_map:
                if isinstance(u, dict) and u.get("id"):
                    users[str(u["id"])] = u.get("name") or u.get("real_name") or u.get("id")
        for key in ("channels", "groups", "dms"):
            group = payload.get(key)
            if isinstance(group, list):
                for ch in group:
                    if isinstance(ch, dict):
                        ch_name = str(ch.get("name") or ch.get("id") or key)
                        for msg in (ch.get("messages") or []):
                            if isinstance(msg, dict):
                                docs.append(_slack_message_to_doc(msg, users, ch_name))
            elif isinstance(group, dict):
                # {"channel_name": [messages...]}
                for ch_name, msgs in group.items():
                    if isinstance(msgs, list):
                        for msg in msgs:
                            if isinstance(msg, dict):
                                docs.append(_slack_message_to_doc(msg, users, str(ch_name)))
        # Single channel object: {"messages": [...]}
        for msg in (payload.get("messages") or []):
            if isinstance(msg, dict):
                docs.append(_slack_message_to_doc(msg, users, str(payload.get("name") or "channel")))
    elif isinstance(payload, list):
        for msg in payload:
            if isinstance(msg, dict):
                docs.append(_slack_message_to_doc(msg, users, "channel"))

    if docs:
        return docs
    # Fall back to treating a list of dicts as generic rows.
    if isinstance(payload, list):
        return _rows_to_docs([p for p in payload if isinstance(p, dict)])
    if isinstance(payload, dict):
        return _rows_to_docs([payload])
    return []


def _teams_message_to_doc(msg: dict, channel: str | None = None) -> DocInput:
    body = (msg.get("body") or {}).get("content") if isinstance(msg.get("body"), dict) else msg.get("body")
    author = None
    sender = msg.get("from")
    if isinstance(sender, dict):
        u = sender.get("user") or {}
        if isinstance(u, dict):
            author = u.get("displayName")
        elif isinstance(u, str):
            author = u
    return DocInput(
        external_id=str(msg.get("id") or ""),
        kind="message",
        author=author,
        channel=channel or msg.get("channelIdentity", {}).get("channelId") if isinstance(msg.get("channelIdentity"), dict) else channel,
        ts=_iso(msg.get("createdDateTime")),
        content=str(body or "").strip(),
        meta={"messageType": msg.get("messageType"), "reply_count": msg.get("replyCount")},
    )


def _parse_json(file_bytes: bytes) -> list[DocInput]:
    text = file_bytes.decode("utf-8-sig", errors="replace")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Single line of text / raw content.
        return [DocInput(kind="file", content=text.strip(), channel=None)]

    if isinstance(payload, list) and payload and all(
        isinstance(m, dict) and ("body" in m or "from" in m or "createdDateTime" in m) for m in payload
    ):
        return [_teams_message_to_doc(m) for m in payload]

    docs = _parse_slack_json(payload)
    if docs:
        return docs

    # Generic list/dict fallback.
    if isinstance(payload, list):
        return _rows_to_docs([p for p in payload if isinstance(p, dict)])
    if isinstance(payload, dict):
        return _rows_to_docs([payload])
    return []


def _parse_zip(file_bytes: bytes) -> list[DocInput]:
    """Slack export ZIP (channels/*.json + users.json) or a generic archive of
    CSV/JSON files."""
    docs: list[DocInput] = []
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        names = zf.namelist()
        users: dict = {}
        for n in names:
            if n.endswith("users.json"):
                try:
                    data = json.loads(zf.read(n).decode("utf-8", errors="replace"))
                    for u in data if isinstance(data, list) else []:
                        if isinstance(u, dict) and u.get("id"):
                            users[str(u["id"])] = u.get("name") or u.get("real_name") or u.get("id")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
        for n in names:
            if n.endswith("/") or n.startswith("__MACOSX"):
                continue
            if n.endswith(".json"):
                try:
                    payload = json.loads(zf.read(n).decode("utf-8", errors="replace"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                channel = n.split("/")[-1].removesuffix(".json")
                if isinstance(payload, list):
                    for msg in payload:
                        if isinstance(msg, dict):
                            docs.append(_slack_message_to_doc(msg, users, channel))
                elif isinstance(payload, dict):
                    for msg in (payload.get("messages") or []):
                        if isinstance(msg, dict):
                            docs.append(_slack_message_to_doc(msg, users, channel))
            elif n.endswith(".csv"):
                try:
                    docs.extend(_parse_csv(zf.read(n)))
                except Exception:  # noqa: BLE001
                    continue
    return docs


# --------------------------------------------------------------------------- #
# Live API connectors
# --------------------------------------------------------------------------- #
def _slack_get(path: str, token: str, params: dict | None = None) -> dict:
    import httpx

    resp = httpx.get(
        f"https://slack.com/api/{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
    return data


def list_slack_channels(token: str) -> list[dict]:
    """List public + private channels (groups) the token can see."""
    data = _slack_get(
        "conversations.list",
        token,
        {"types": "public_channel,private_channel", "limit": 200},
    )
    return [
        {"id": c.get("id"), "name": c.get("name")}
        for c in (data.get("channels") or [])
    ]


def pull_slack_messages(token: str, channel_id: str, limit: int = 200) -> list[DocInput]:
    data = _slack_get(
        "conversations.history", token, {"channel": channel_id, "limit": min(limit, 200)}
    )
    docs: list[DocInput] = []
    for msg in (data.get("messages") or []):
        docs.append(_slack_message_to_doc(msg, {}, channel_id))
    return docs


def _graph_get(path: str, token: str) -> dict:
    import httpx

    resp = httpx.get(
        f"https://graph.microsoft.com/v1/{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def list_teams_channels(token: str, team_id: str) -> list[dict]:
    data = _graph_get(f"teams/{team_id}/channels", token)
    return [
        {"id": c.get("id"), "name": c.get("displayName")}
        for c in (data.get("value") or [])
    ]


def pull_teams_messages(token: str, team_id: str, channel_id: str, limit: int = 200) -> list[DocInput]:
    data = _graph_get(
        f"teams/{team_id}/channels/{channel_id}/messages?$top={min(limit, 50)}", token
    )
    return [_teams_message_to_doc(m, channel_id) for m in (data.get("value") or [])]


# --------------------------------------------------------------------------- #
# Incremental (CDC) pulls — return (docs, newest_watermark)
# --------------------------------------------------------------------------- #
def pull_slack_messages_incremental(
    token: str, channel_id: str, since: str | None = None, limit: int = 200
) -> tuple[list[DocInput], str | None]:
    """Pull Slack messages newer than ``since`` (a message ``ts`` watermark),
    following pagination. Returns (docs, newest_ts_or_None)."""
    docs: list[DocInput] = []
    newest = since
    params: dict = {"channel": channel_id, "limit": min(limit, 200)}
    if since:
        params["oldest"] = since  # inclusive; we filter the boundary below

    while True:
        data = _slack_get("conversations.history", token, params)
        for msg in (data.get("messages") or []):
            ts = msg.get("ts")
            if since and ts and str(ts) <= str(since):
                continue  # skip the already-ingested boundary message
            docs.append(_slack_message_to_doc(msg, {}, channel_id))
            if ts and (newest is None or str(ts) > str(newest)):
                newest = str(ts)
        if not data.get("has_more"):
            break
        pagination = (data.get("response_metadata") or {}).get("next_cursor")
        if not pagination:
            break
        params = {**params, "cursor": pagination}
    return docs, newest


def _teams_watermark(msg: dict) -> str | None:
    return msg.get("lastModifiedDateTime") or msg.get("createdDateTime") or None


def pull_teams_messages_incremental(
    token: str, team_id: str, channel_id: str, since: str | None = None, limit: int = 200
) -> tuple[list[DocInput], str | None]:
    """Pull Teams messages newer than ``since`` (an ISO-8601 watermark),
    following Graph pagination. Returns (docs, newest_watermark_or_None)."""
    import httpx

    docs: list[DocInput] = []
    newest = since
    url = (
        f"https://graph.microsoft.com/v1/teams/{team_id}/channels/{channel_id}"
        f"/messages?$top={min(limit, 50)}"
    )
    while url:
        resp = httpx.get(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        for msg in (data.get("value") or []):
            wm = _teams_watermark(msg)
            if since and wm and str(wm) <= str(since):
                continue
            docs.append(_teams_message_to_doc(msg, channel_id))
            if wm and (newest is None or str(wm) > str(newest)):
                newest = str(wm)
        url = data.get("@odata.nextLink") or None
    return docs, newest
