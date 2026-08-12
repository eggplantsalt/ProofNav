"""Safely extract the official DUET archive into an empty staging directory."""

import argparse
import os
import pathlib
import shutil
import stat
import zipfile


ALLOWED_PREFIXES = ("R2R/connectivity/",)
ALLOWED_EXACT = {
    "R2R/features/pth_vit_base_patch16_224_imagenet.hdf5",
    "REVERIE/features/obj.avg.top3.min80_vit_base_patch16_224_imagenet.hdf5",
    "REVERIE/annotations/BBoxes.json",
    "REVERIE/annotations/REVERIE_train_enc.json",
    "REVERIE/annotations/REVERIE_val_train_seen_enc.json",
    "REVERIE/annotations/REVERIE_val_seen_enc.json",
    "REVERIE/annotations/REVERIE_val_unseen_enc.json",
    "REVERIE/annotations/REVERIE_test_enc.json",
    "REVERIE/trained_models/best_val_unseen",
}


def is_selected(name):
    if name in ALLOWED_EXACT or any(name.startswith(x) for x in ALLOWED_PREFIXES):
        return True
    if name.endswith("/"):
        prefix = name.rstrip("/") + "/"
        return any(
            x.startswith(prefix) for x in tuple(ALLOWED_EXACT) + ALLOWED_PREFIXES
        )
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()

    destination = os.path.abspath(args.destination)
    os.makedirs(destination, exist_ok=True)
    if os.listdir(destination):
        raise ValueError("destination must be empty: %s" % destination)

    extracted = 0
    skipped_inert_root = 0
    skipped_unselected = 0
    with zipfile.ZipFile(args.archive) as archive:
        for info in archive.infolist():
            name = info.filename
            if (name == "/" and info.is_dir() and info.file_size == 0
                    and info.compress_size == 0 and info.CRC == 0):
                skipped_inert_root += 1
                continue
            path = pathlib.PurePosixPath(name)
            mode = info.external_attr >> 16
            if (not name or "\x00" in name or path.is_absolute()
                    or name.startswith(("/", "\\")) or ".." in path.parts
                    or (path.parts and ":" in path.parts[0]) or stat.S_ISLNK(mode)):
                raise ValueError("unsafe archive member: %r" % name)
            if not is_selected(name):
                skipped_unselected += 1
                continue
            target = os.path.abspath(os.path.join(destination, *path.parts))
            if os.path.commonpath([destination, target]) != destination:
                raise ValueError("archive member escapes destination: %r" % name)
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with archive.open(info) as source, open(target, "xb") as sink:
                    shutil.copyfileobj(source, sink, length=16 * 1024 * 1024)
            extracted += 1
    print("extracted_members=%d skipped_inert_root=%d skipped_unselected=%d" % (
        extracted, skipped_inert_root, skipped_unselected
    ))
    if skipped_inert_root != 1:
        raise ValueError("expected exactly one inert root member")


if __name__ == "__main__":
    main()
