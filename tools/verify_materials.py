"""Check the research delivery, not game behavior or performance."""

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(value for key, value in attrs if key in ("src", "href") and value)


def main():
    errors = []
    files_verified = 0
    for item in json.loads((ROOT / "assets/manifest.json").read_text())["items"]:
        path = ROOT / item["local_path"]
        data = path.read_bytes()
        if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            errors.append(f"Manifest mismatch: {path}")
        files_verified += 1
    packs = []
    for path in sorted((ROOT / "assets/reusable").glob("*.zip")):
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                errors.append(f"ZIP CRC failure: {path}: {bad}")
            licenses = [n for n in archive.namelist() if "license" in n.lower() and not n.endswith("/")]
            if not licenses or not all("CC0" in archive.read(n).decode() for n in licenses):
                errors.append(f"Missing expected CC0 license: {path}")
            packs.append({"path": str(path.relative_to(ROOT)), "crc_ok": bad is None,
                          "license_files": licenses})
    local_links = 0
    def check_link(source, raw):
        nonlocal local_links
        parsed = urlsplit(raw)
        if parsed.scheme or not parsed.path:
            return
        target = source.parent / unquote(parsed.path)
        local_links += 1
        if not target.exists() and target != ROOT / "checks/verification.json":
            errors.append(f"Broken link: {source.name}: {raw}")
    for path in ROOT.glob("*.md"):
        for raw in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", path.read_text()):
            check_link(path, raw)
    board = ROOT / "reference-board.html"
    parser = Links()
    parser.feed(board.read_text())
    for raw in parser.links:
        check_link(board, raw)
    ET.parse(ROOT / "design/forest-loop.svg")
    browser = json.loads((ROOT / "checks/browser-check.json").read_text())
    if browser["script_errors"] or browser["desktop"]["overflow"] or browser["mobile"]["overflow"]:
        errors.append("Browser rendering check failed")
    if any(image["width"] <= 0 for image in browser["desktop"]["images"]):
        errors.append("An image failed to decode")
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not errors else "fail", "errors": errors,
        "manifest_files_sha256_verified": files_verified,
        "official_screenshots": len(list((ROOT / "assets/reference").glob("*.jpg"))),
        "packs": packs, "local_document_links_checked": local_links,
        "svg_xml_valid": True, "board_images_decoded": len(browser["desktop"]["images"]),
        "desktop_and_mobile_no_horizontal_overflow": True,
        "scope": "Research file integrity, licenses, document links and offline board rendering only.",
        "not_tested": ["Original game", "Referenced videos or audio", "Playable web game", "Game physics or performance"],
    }
    target = ROOT / "checks/verification.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
