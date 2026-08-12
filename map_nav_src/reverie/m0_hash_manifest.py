"""Create a complete SHA-256 manifest for retained M0 resource artifacts."""

import argparse
import hashlib
import json
import os


def digest(path):
    value = hashlib.sha256()
    with open(path, "rb") as infile:
        for block in iter(lambda: infile.read(16 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource_root", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = os.path.abspath(args.resource_root)
    files = {}
    for directory, _, names in os.walk(root):
        for name in sorted(names):
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, os.path.dirname(root))
            files[relative] = {
                "bytes": os.path.getsize(path),
                "sha256": digest(path),
            }
    archive = os.path.abspath(args.archive)
    report = {
        "manifest_type": "m0.resources.sha256.v1",
        "archive": {
            "path": archive,
            "bytes": os.path.getsize(archive),
            "sha256": digest(archive),
        },
        "resource_root": root,
        "resource_file_count": len(files),
        "resources": files,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as outfile:
        json.dump(report, outfile, sort_keys=True, indent=2)
    print(json.dumps({
        "archive_sha256": report["archive"]["sha256"],
        "resource_file_count": report["resource_file_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
