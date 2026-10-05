"""Download the public OpenGovSG Careers@Gov extract."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from scripts.common import sha256_bytes
from scripts.validate_source import ValidationError


def download_jobs(url: str, dest: Path, timeout: int = 120) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_suffix(dest.suffix + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": "procurement-hiring-dashboard"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            payload = response.read()
            last_modified = response.headers.get("Last-Modified", "")
    except Exception as exc:  # noqa: BLE001 - surface any transport failure as a validation stop
        raise ValidationError(f"Download failed: {exc}") from exc
    if status != 200:
        raise ValidationError(f"Download returned HTTP {status}.")
    if not payload:
        raise ValidationError("Download was empty.")
    temporary.write_bytes(payload)
    temporary.replace(dest)
    return {
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "lastModified": last_modified,
        "url": url,
    }
