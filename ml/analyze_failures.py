"""Rank YOLO test-set failures and render the most severe examples."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image


IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def box_iou(first: list[float], second: list[float]) -> float:
    intersection_width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    intersection_height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    intersection = intersection_width * intersection_height
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def match_detections(
    ground_truth: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    iou_threshold: float,
) -> dict[str, Any]:
    candidates: list[tuple[float, int, int]] = []
    for ground_index, ground in enumerate(ground_truth):
        for prediction_index, prediction in enumerate(predictions):
            if ground["class_id"] != prediction["class_id"]:
                continue
            overlap = box_iou(ground["box"], prediction["box"])
            if overlap >= iou_threshold:
                candidates.append((overlap, ground_index, prediction_index))

    matched_ground: set[int] = set()
    matched_predictions: set[int] = set()
    matches = []
    for overlap, ground_index, prediction_index in sorted(candidates, reverse=True):
        if ground_index in matched_ground or prediction_index in matched_predictions:
            continue
        matched_ground.add(ground_index)
        matched_predictions.add(prediction_index)
        matches.append(
            {
                "ground_truth_index": ground_index,
                "prediction_index": prediction_index,
                "iou": overlap,
            }
        )

    false_negatives = [
        ground for index, ground in enumerate(ground_truth) if index not in matched_ground
    ]
    false_positives = [
        prediction
        for index, prediction in enumerate(predictions)
        if index not in matched_predictions
    ]
    return {
        "true_positives": len(matches),
        "false_positives": len(false_positives),
        "false_negatives": len(false_negatives),
        "matches": matches,
        "false_positive_details": false_positives,
        "false_negative_details": false_negatives,
    }


def load_ground_truth(
    label_path: Path, width: int, height: int, class_names: dict[int, str]
) -> list[dict[str, Any]]:
    annotations = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        class_id_text, center_x, center_y, box_width, box_height = line.split()
        class_id = int(class_id_text)
        center_x_pixels = float(center_x) * width
        center_y_pixels = float(center_y) * height
        width_pixels = float(box_width) * width
        height_pixels = float(box_height) * height
        annotations.append(
            {
                "class_id": class_id,
                "class_name": class_names[class_id],
                "box": [
                    center_x_pixels - width_pixels / 2,
                    center_y_pixels - height_pixels / 2,
                    center_x_pixels + width_pixels / 2,
                    center_y_pixels + height_pixels / 2,
                ],
            }
        )
    return annotations


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device", default="0")
    parser.add_argument("--confidence", default=0.25, type=float)
    parser.add_argument("--iou", default=0.5, type=float)
    parser.add_argument("--top-k", default=12, type=int)
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.model)
    class_names = {int(index): name for index, name in model.names.items()}
    image_dir = args.dataset_root / "images" / "test"
    label_dir = args.dataset_root / "labels" / "test"
    images = sorted(
        path
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )

    image_reports = []
    for image_path in images:
        with Image.open(image_path) as image:
            width, height = image.size
        ground_truth = load_ground_truth(
            label_dir / f"{image_path.stem}.txt", width, height, class_names
        )
        result = model.predict(
            source=image_path,
            conf=args.confidence,
            device=args.device,
            verbose=False,
        )[0]
        predictions = [
            {
                "class_id": int(class_id),
                "class_name": class_names[int(class_id)],
                "confidence": confidence,
                "box": box,
            }
            for box, class_id, confidence in zip(
                result.boxes.xyxy.cpu().tolist(),
                result.boxes.cls.cpu().tolist(),
                result.boxes.conf.cpu().tolist(),
            )
        ]
        matching = match_detections(ground_truth, predictions, args.iou)
        image_reports.append(
            {
                "image": image_path.relative_to(args.dataset_root).as_posix(),
                **matching,
                "error_count": matching["false_positives"]
                + matching["false_negatives"],
            }
        )

    ranked = sorted(
        image_reports,
        key=lambda item: (
            -item["error_count"],
            -item["false_negatives"],
            -item["false_positives"],
            item["image"],
        ),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    rendered_dir = args.output / "rendered"
    rendered_dir.mkdir(exist_ok=True)
    for rank, report in enumerate(ranked[: args.top_k], start=1):
        image_path = args.dataset_root / report["image"]
        result = model.predict(
            source=image_path,
            conf=args.confidence,
            device=args.device,
            verbose=False,
        )[0]
        rendered_path = rendered_dir / f"{rank:02d}-{image_path.stem}.jpg"
        result.save(filename=str(rendered_path))
        report["rendered_path"] = rendered_path.relative_to(args.output).as_posix()

    report = {
        "model_sha256": sha256_file(args.model),
        "test_images": len(image_reports),
        "confidence_threshold": args.confidence,
        "iou_threshold": args.iou,
        "summary": {
            "true_positives": sum(item["true_positives"] for item in image_reports),
            "false_positives": sum(item["false_positives"] for item in image_reports),
            "false_negatives": sum(item["false_negatives"] for item in image_reports),
            "images_with_errors": sum(item["error_count"] > 0 for item in image_reports),
        },
        "top_failures": ranked[: args.top_k],
        "all_images": sorted(image_reports, key=lambda item: item["image"]),
    }
    (args.output / "failure-analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
