import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.release_manifest import load_and_validate_release_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_dir")
    args = parser.parse_args()
    manifest = load_and_validate_release_manifest(Path(args.bundle_dir) / "release-manifest.json")
    print(f"Release bundle verified: {manifest['version']} ({len(manifest['artifacts'])} artifacts)")


if __name__ == "__main__":
    main()
