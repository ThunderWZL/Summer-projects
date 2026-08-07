import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_failures import box_iou, match_detections  # noqa: E402


class AnalyzeFailuresTest(unittest.TestCase):
    def test_box_iou(self) -> None:
        self.assertEqual(box_iou([0, 0, 10, 10], [20, 20, 30, 30]), 0.0)
        self.assertAlmostEqual(box_iou([0, 0, 10, 10], [5, 5, 15, 15]), 25 / 175)

    def test_matches_once_per_box_and_class(self) -> None:
        ground_truth = [
            {"class_id": 0, "box": [0, 0, 10, 10]},
            {"class_id": 1, "box": [20, 20, 30, 30]},
        ]
        predictions = [
            {"class_id": 0, "box": [0, 0, 10, 10]},
            {"class_id": 0, "box": [0, 0, 10, 10]},
            {"class_id": 1, "box": [40, 40, 50, 50]},
        ]

        report = match_detections(ground_truth, predictions, 0.5)

        self.assertEqual(report["true_positives"], 1)
        self.assertEqual(report["false_positives"], 2)
        self.assertEqual(report["false_negatives"], 1)


if __name__ == "__main__":
    unittest.main()
