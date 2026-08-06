"""Audit a YOLO detection dataset without modifying its predefined splits."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import imagehash
from PIL import Image


IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _duplicate_groups(
    hashes: dict[str, str], split_by_path: dict[str, str]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for relative_path, digest in hashes.items():
        grouped[digest].append(relative_path)

    duplicates = []
    for digest, paths in sorted(grouped.items()):
        if len(paths) < 2:
            continue
        paths.sort()
        splits = sorted({split_by_path[path] for path in paths})
        duplicates.append(
            {
                "hash": digest,
                "paths": paths,
                "splits": splits,
                "cross_split": len(splits) > 1,
            }
        )
    return duplicates


def audit_dataset(
    dataset_root: Path, source_manifest: Path, archive: Path | None = None
) -> dict[str, Any]:
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    class_names = source["class_names"]
    expected_splits = source["expected_image_counts"]
    errors: list[str] = []
    split_reports: dict[str, Any] = {}
    exact_hashes: dict[str, str] = {}
    perceptual_hashes: dict[str, str] = {}
    split_by_path: dict[str, str] = {}
    fingerprint_entries: list[tuple[str, str]] = []

    for split, expected_count in expected_splits.items():
        image_dir = dataset_root / "images" / split
        label_dir = dataset_root / "labels" / split
        images = sorted(
            path
            for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ) if image_dir.is_dir() else []
        if not image_dir.is_dir():
            errors.append(f"missing image directory: images/{split}")
        if not label_dir.is_dir():
            errors.append(f"missing label directory: labels/{split}")

        class_counts: Counter[str] = Counter()
        missing_labels: list[str] = []
        invalid_labels: list[dict[str, Any]] = []
        label_count = 0

        for image_path in images:
            relative_image = image_path.relative_to(dataset_root).as_posix()
            split_by_path[relative_image] = split
            exact_digest = sha256_file(image_path)
            exact_hashes[relative_image] = exact_digest
            fingerprint_entries.append((relative_image, exact_digest))
            try:
                with Image.open(image_path) as image:
                    perceptual_hashes[relative_image] = str(imagehash.phash(image))
            except (OSError, ValueError) as exc:
                errors.append(f"unreadable image {relative_image}: {exc}")

            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.is_file():
                missing_labels.append(relative_image)
                continue
            label_count += 1
            relative_label = label_path.relative_to(dataset_root).as_posix()
            fingerprint_entries.append((relative_label, sha256_file(label_path)))
            for line_number, raw_line in enumerate(
                label_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                fields = raw_line.split()
                try:
                    class_id = int(fields[0])
                    coordinates = [float(value) for value in fields[1:]]
                    if len(fields) != 5 or not 0 <= class_id < len(class_names):
                        raise ValueError("expected class id and four coordinates")
                    if any(
                        not math.isfinite(value) or value < 0 or value > 1
                        for value in coordinates
                    ):
                        raise ValueError("coordinates must be within [0, 1]")
                except (IndexError, ValueError) as exc:
                    invalid_labels.append(
                        {
                            "path": relative_label,
                            "line": line_number,
                            "reason": str(exc),
                        }
                    )
                    continue
                class_counts[class_names[class_id]] += 1

        observed_count = len(images)
        if observed_count != expected_count:
            errors.append(
                f"{split} image count is {observed_count}, expected {expected_count}"
            )
        if missing_labels:
            errors.append(f"{split} has {len(missing_labels)} images without labels")
        if invalid_labels:
            errors.append(f"{split} has {len(invalid_labels)} invalid label rows")

        split_reports[split] = {
            "expected_images": expected_count,
            "observed_images": observed_count,
            "label_files": label_count,
            "instances": sum(class_counts.values()),
            "class_instances": {
                name: class_counts[name] for name in class_names
            },
            "missing_labels": missing_labels,
            "invalid_labels": invalid_labels,
        }

    exact_duplicates = _duplicate_groups(exact_hashes, split_by_path)
    perceptual_duplicates = _duplicate_groups(perceptual_hashes, split_by_path)
    total_class_counts = {
        name: sum(
            split_report["class_instances"][name]
            for split_report in split_reports.values()
        )
        for name in class_names
    }
    dataset_digest = hashlib.sha256()
    for relative_path, digest in sorted(fingerprint_entries):
        dataset_digest.update(relative_path.encode("utf-8"))
        dataset_digest.update(b"\0")
        dataset_digest.update(digest.encode("ascii"))
        dataset_digest.update(b"\n")

    archive_report = None
    if archive is not None:
        actual_archive_hash = sha256_file(archive)
        expected_archive_hash = source.get("archive_sha256")
        archive_report = {
            "path": str(archive),
            "sha256": actual_archive_hash,
            "matches_manifest": actual_archive_hash == expected_archive_hash,
        }
        if expected_archive_hash and actual_archive_hash != expected_archive_hash:
            errors.append("archive SHA-256 does not match the source manifest")

    return {
        "valid": not errors,
        "dataset_root": str(dataset_root),
        "source": source,
        "archive": archive_report,
        "dataset_fingerprint_sha256": dataset_digest.hexdigest(),
        "summary": {
            "images": sum(
                split_report["observed_images"]
                for split_report in split_reports.values()
            ),
            "instances": sum(total_class_counts.values()),
            "class_instances": total_class_counts,
        },
        "splits": split_reports,
        "duplicates": {
            "exact_groups": exact_duplicates,
            "perceptual_groups": perceptual_duplicates,
            "cross_split_exact_groups": sum(
                group["cross_split"] for group in exact_duplicates
            ),
            "cross_split_perceptual_groups": sum(
                group["cross_split"] for group in perceptual_duplicates
            ),
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = audit_dataset(args.dataset_root, args.source_manifest, args.archive)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
