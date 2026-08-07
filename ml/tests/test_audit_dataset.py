import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_dataset import audit_dataset  # noqa: E402


class AuditDatasetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.dataset_root = self.root / "dataset"
        self.manifest_path = self.root / "source.json"
        for split in ("train", "val", "test"):
            (self.dataset_root / "images" / split).mkdir(parents=True)
            (self.dataset_root / "labels" / split).mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_manifest(self, counts: dict[str, int]) -> None:
        self.manifest_path.write_text(
            json.dumps(
                {
                    "name": "fixture",
                    "class_names": ["helmet", "Person"],
                    "expected_image_counts": counts,
                }
            ),
            encoding="utf-8",
        )

    def add_sample(self, split: str, name: str, color: str, class_id: int) -> None:
        image_path = self.dataset_root / "images" / split / f"{name}.png"
        Image.new("RGB", (16, 16), color=color).save(image_path)
        label_path = self.dataset_root / "labels" / split / f"{name}.txt"
        label_path.write_text(
            f"{class_id} 0.5 0.5 0.5 0.5\n", encoding="utf-8"
        )

    def test_reports_counts_and_valid_split(self) -> None:
        self.write_manifest({"train": 1, "val": 1, "test": 1})
        self.add_sample("train", "a", "red", 0)
        self.add_sample("val", "b", "green", 1)
        self.add_sample("test", "c", "blue", 1)

        report = audit_dataset(self.dataset_root, self.manifest_path)

        self.assertTrue(report["valid"])
        self.assertEqual(report["summary"]["images"], 3)
        self.assertEqual(report["summary"]["instances"], 3)
        self.assertEqual(report["splits"]["train"]["class_instances"]["helmet"], 1)
        self.assertEqual(report["splits"]["val"]["class_instances"]["Person"], 1)
        self.assertEqual(report["duplicates"]["cross_split_exact_groups"], 0)

    def test_flags_cross_split_exact_duplicate(self) -> None:
        self.write_manifest({"train": 1, "val": 1, "test": 0})
        self.add_sample("train", "a", "red", 0)
        self.add_sample("val", "b", "red", 0)

        report = audit_dataset(self.dataset_root, self.manifest_path)

        self.assertTrue(report["valid"])
        self.assertEqual(report["duplicates"]["cross_split_exact_groups"], 1)

    def test_rejects_modified_split_count(self) -> None:
        self.write_manifest({"train": 1, "val": 0, "test": 0})

        report = audit_dataset(self.dataset_root, self.manifest_path)

        self.assertFalse(report["valid"])
        self.assertIn("train image count is 0, expected 1", report["errors"])


if __name__ == "__main__":
    unittest.main()
