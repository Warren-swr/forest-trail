"""Collect public reference images and CC0 prototype packs; no game extraction."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now(timezone.utc).isoformat()
STORE = "https://store.steampowered.com/app/2929250/over_the_hill/"
API = "https://store.steampowered.com/api/appdetails?appids=2929250&l=english&cc=us"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "ResearchReferenceCollector/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read(), response.url


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def download(item):
    path = ROOT / item["local_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        data = path.read_bytes()
    else:
        data, final = fetch(item["download_url"])
        path.write_bytes(data)
        item["resolved_download_url"] = final
    item.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), accessed_at=STAMP)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            item["archive_entries"] = len(archive.namelist())
            item["license_files"] = []
            inventory = ROOT / "assets/reusable" / (path.stem + "-inventory.txt")
            inventory.write_text("\n".join(archive.namelist()) + "\n")
            for name in archive.namelist():
                if "license" in name.lower() and not name.endswith("/"):
                    target = ROOT / "assets/reusable/licenses" / (path.stem + "-" + Path(name).name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
                    item["license_files"].append(str(target.relative_to(ROOT)))
    return item


def main():
    existing = ROOT / "assets/manifest.json"
    if existing.exists():
        frozen = json.loads(existing.read_text())
        for item in frozen["items"]:
            path = ROOT / item["local_path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise RuntimeError(f"Frozen material changed: {path}")
        print("Existing snapshot verified; use a new research directory for a fresh collection.")
        return
    payload = json.loads(fetch(API)[0])
    data = next(entry["data"] for entry in payload.values()
                if entry.get("success") and entry.get("data", {}).get("steam_appid") == 2929250)
    save_json(ROOT / "sources/steam-media-metadata.json", {
        "source_url": API, "accessed_at": STAMP, "steam_appid": data["steam_appid"],
        "name": data["name"], "release_date": data["release_date"],
        "screenshots": data.get("screenshots", []), "movies": data.get("movies", []),
        "note": "Metadata only. Trailers indexed, not downloaded or viewed in this research.",
    })
    items = []
    for number, shot in enumerate(data.get("screenshots", []), 1):
        items.append({
            "id": f"REF-{number:02d}", "kind": "official_screenshot", "source_page": STORE,
            "download_url": shot["path_full"],
            "local_path": f"assets/reference/steam-{number:02d}.jpg",
            "rights": "Copyright Funselektor / Strelka Games; research reference only, not a game asset license.",
        })
    for slug in ("nature-kit", "car-kit", "survival-kit"):
        page = "https://kenney.nl/assets/" + slug
        body = fetch(page)[0].decode()
        links = re.findall(r'href=[\"\']([^\"\']+\.zip)[\"\']', body)
        if not links:
            raise RuntimeError(f"No public ZIP download found: {page}")
        items.append({
            "id": "PACK-" + slug.upper(), "kind": "prototype_asset_pack",
            "source_page": page, "download_url": html.unescape(links[0]),
            "local_path": f"assets/reusable/kenney_{slug}.zip",
            "creator": "Kenney", "rights": "CC0 1.0; see bundled license",
        })
    with ThreadPoolExecutor(max_workers=3) as pool:
        manifest = list(pool.map(download, items))
    save_json(ROOT / "assets/manifest.json", {"accessed_at": STAMP, "items": manifest})
    print(json.dumps({"files": len(manifest), "bytes": sum(i["bytes"] for i in manifest)}, indent=2))


if __name__ == "__main__":
    main()
