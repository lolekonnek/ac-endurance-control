#!/usr/bin/env python3
"""Build a token-free Windows client ZIP suitable for a GitHub Release."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / f"AC-Endurance-Control-Client-v{VERSION}.zip")
    args = parser.parse_args()
    source = ROOT / "client" / "csp" / "ac_endurance_client"
    windows = ROOT / "client" / "windows"
    files = {
        "manifest.ini": source / "manifest.ini",
        "ac_endurance_client.lua": source / "ac_endurance_client.lua",
        "Install-ACEndurance.ps1": windows / "Install-ACEndurance.ps1",
        "README.md": windows / "README.md",
    }
    missing = [str(path) for path in files.values() if not path.is_file()]
    if missing:
        parser.error("Missing client package files: " + ", ".join(missing))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in files.items():
            archive.write(path, arcname=name)
    print(f"Created {args.output}")


if __name__ == "__main__":
    main()
