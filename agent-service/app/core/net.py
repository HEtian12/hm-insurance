"""Proxy environment helpers.

Windows proxy tools (Clash etc.) often put bracketed IPv6 entries such as
``[::1]`` into ``NO_PROXY``. httpx cannot parse those entries and fails with
``InvalidURL: Invalid port: ':1]'`` the first time a client is created.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse


def _rewrite(entries: list[str]) -> None:
    value = ",".join(dict.fromkeys(entries))
    os.environ["NO_PROXY"] = value
    os.environ["no_proxy"] = value


def bypass_proxy_for_hosts(*urls: str | None) -> None:
    """Drop unparsable proxy-bypass entries and add internal service hosts."""

    raw = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    entries = [item.strip() for item in raw.split(",") if item.strip() and not item.strip().startswith("[")]
    for url in urls:
        if not url:
            continue
        host = urlparse(url).hostname
        if host and host not in entries:
            entries.append(host)
    for host in ("localhost", "127.0.0.1", "::1"):
        if host not in entries:
            entries.append(host)
    _rewrite(entries)


def disable_proxy() -> None:
    """Send every request directly (used by the offline knowledge ingest)."""

    _rewrite(["*"])
