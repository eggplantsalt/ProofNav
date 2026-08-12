"""Hash and path-safety audit for the retained official DUET dataset archive."""

import argparse
import hashlib
import json
import os
import pathlib
import stat
import zipfile


REQUIRED_SUFFIXES = (
    "R2R/connectivity/scans.txt",
    "R2R/features/pth_vit_base_patch16_224_imagenet.hdf5",
    "REVERIE/features/obj.avg.top3.min80_vit_base_patch16_224_imagenet.hdf5",
    "REVERIE/annotations/BBoxes.json",
    "REVERIE/annotations/REVERIE_train_enc.json",
    "REVERIE/annotations/REVERIE_val_train_seen_enc.json",
    "REVERIE/annotations/REVERIE_val_seen_enc.json",
    "REVERIE/annotations/REVERIE_val_unseen_enc.json",
    "REVERIE/annotations/REVERIE_test_enc.json",
    "REVERIE/trained_models/best_val_unseen",
)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as infile:
        for block in iter(lambda: infile.read(16 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected_bytes", type=int)
    args = parser.parse_args()

    archive_bytes = os.path.getsize(args.archive)
    unsafe = []
    duplicate_names = []
    inert_root_members = []
    seen = set()
    top_levels = set()
    found_required = {suffix: [] for suffix in REQUIRED_SUFFIXES}
    compressed_bytes = 0
    uncompressed_bytes = 0
    with zipfile.ZipFile(args.archive) as archive:
        members = archive.infolist()
        member_name_digest = hashlib.sha256()
        for info in members:
            name = info.filename
            member_name_digest.update(name.encode("utf-8"))
            member_name_digest.update(b"\n")
            path = pathlib.PurePosixPath(name)
            mode = info.external_attr >> 16
            reasons = []
            if not name or "\x00" in name:
                reasons.append("empty_or_nul")
            if path.is_absolute() or name.startswith(("/", "\\")):
                reasons.append("absolute")
            if ".." in path.parts:
                reasons.append("parent_traversal")
            if path.parts and ":" in path.parts[0]:
                reasons.append("drive_prefix")
            if stat.S_ISLNK(mode):
                reasons.append("symlink")
            if reasons:
                if (name == "/" and reasons == ["absolute"] and info.is_dir()
                        and info.file_size == 0 and info.compress_size == 0
                        and info.CRC == 0):
                    inert_root_members.append(name)
                else:
                    unsafe.append({"name": name, "reasons": reasons})
            if name in seen:
                duplicate_names.append(name)
            seen.add(name)
            if path.parts:
                top_levels.add(path.parts[0])
            for suffix in REQUIRED_SUFFIXES:
                if name.endswith(suffix):
                    found_required[suffix].append(name)
            compressed_bytes += int(info.compress_size)
            uncompressed_bytes += int(info.file_size)
        bad_crc_member = None
        if not unsafe and not duplicate_names:
            bad_crc_member = archive.testzip()

    missing_required = sorted(
        suffix for suffix, matches in found_required.items() if len(matches) != 1
    )
    size_matches = (
        args.expected_bytes is None or archive_bytes == args.expected_bytes
    )
    report = {
        "audit_type": "m0.archive.v1",
        "archive": os.path.abspath(args.archive),
        "archive_bytes": archive_bytes,
        "expected_bytes": args.expected_bytes,
        "size_matches": size_matches,
        "sha256": sha256(args.archive),
        "member_count": len(members),
        "member_name_manifest_sha256": member_name_digest.hexdigest(),
        "compressed_member_bytes": compressed_bytes,
        "uncompressed_member_bytes": uncompressed_bytes,
        "top_level_entries": sorted(top_levels),
        "required_member_matches": found_required,
        "missing_or_ambiguous_required_members": missing_required,
        "unsafe_members": unsafe,
        "inert_root_members_requiring_controlled_skip": inert_root_members,
        "duplicate_names": duplicate_names,
        "zip_crc_failure_member": bad_crc_member,
    }
    report["passed"] = bool(
        size_matches and not missing_required and not unsafe
        and inert_root_members == ["/"]
        and not duplicate_names and bad_crc_member is None
    )
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as outfile:
        json.dump(report, outfile, sort_keys=True, indent=2)
    print(json.dumps(report, sort_keys=True, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
