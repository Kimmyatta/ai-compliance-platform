import argparse
import hashlib
import json
from pathlib import Path

import fitz
import httpx


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="Import the three verified, manually downloaded judgment PDFs.")
    parser.add_argument("downloads", type=Path)
    parser.add_argument("--api", default="http://127.0.0.1:8011")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "samples/judgment_import_manifest.json").read_text(encoding="utf-8"))
    prepared = []
    for item in manifest["documents"]:
        matches = sorted(args.downloads.glob(item["pattern"]), key=lambda p: (len(p.name), p.name))
        if not matches:
            raise SystemExit(f"Missing PDF: {item['pattern']}")
        path = matches[0]
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise SystemExit(f"PDF differs from the verified original: {path.name}")
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if len(pdf) != item["pages"]:
                raise SystemExit(f"Unexpected page count: {path.name}")
        prepared.append((item, path, content))

    records = []
    with httpx.Client(base_url=args.api.rstrip("/") + "/api/", timeout=90) as client:
        client.get("health").raise_for_status()
        for item, path, content in prepared:
            data = {key: item[key] for key in ("title", "court", "citation", "decision_date", "source_url")}
            data.update({
                "kind": "judgment", "permission_confirmed": "true",
                "permission_note": "User manually downloaded and authorised import for local prototype testing. "
                "Source: GhaLII; general terms describe CC BY-NC 4.0 with attribution and additional conditions. "
                "No commercial reuse clearance is asserted. Terms: " + manifest["terms_url"],
            })
            response = client.post("documents", data=data,
                                   files={"file": (path.name, content, "application/pdf")})
            response.raise_for_status()
            document = response.json()
            original = client.get(f"documents/{document['id']}/download")
            original.raise_for_status()
            if hashlib.sha256(original.content).hexdigest() != item["sha256"]:
                raise SystemExit(f"Stored original differs: {path.name}")
            records.append({"id": document["id"], "title": document["title"],
                            "pages": item["pages"], "passages": document["chunk_count"]})
        print(json.dumps({"imported": records, "dashboard": client.get("dashboard").json()}, indent=2))


if __name__ == "__main__":
    main()
