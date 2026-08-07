import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from video_inference import (  # noqa: E402
    FrameRateSampler,
    VideoInferenceRunner,
    extract_detections,
)


class FakeTensor:
    def __init__(self, values):
        self.values = values

    def cpu(self):
        return self

    def tolist(self):
        return self.values


class FakeBoxes:
    def __init__(self, track_id=17):
        self.xyxy = FakeTensor([[10.0, 20.0, 110.0, 220.0]])
        self.conf = FakeTensor([0.91])
        self.cls = FakeTensor([6])
        self.id = FakeTensor([track_id])


class FakeResult:
    names = {6: "Person"}

    def __init__(self, track_id=17):
        self.boxes = FakeBoxes(track_id)

    def plot(self):
        return "annotated"


class FakeFrame:
    shape = (360, 640, 3)


class FakeCapture:
    def __init__(self, frames, fps=10.0, opened=True):
        self.frames = iter(frames)
        self.fps = fps
        self.opened = opened
        self.released = False

    def isOpened(self):
        return self.opened

    def get(self, _property):
        return self.fps

    def read(self):
        try:
            return True, next(self.frames)
        except StopIteration:
            return False, None

    def release(self):
        self.released = True


class FakeCv2:
    CAP_PROP_FPS = 5

    def __init__(self, capture):
        self.capture = capture

    def VideoCapture(self, _path):
        return self.capture


class FakeModel:
    def __init__(self):
        self.calls = []

    def track(self, **kwargs):
        self.calls.append(kwargs)
        return [FakeResult()]


class FrameRateSamplerTest(unittest.TestCase):
    def test_selects_five_frames_per_second_without_drift(self):
        sampler = FrameRateSampler(5.0)

        selected = [
            index
            for index in range(31)
            if sampler.accepts(index * 1000.0 / 30.0)
        ]

        self.assertEqual(selected, [0, 6, 12, 18, 24, 30])

    def test_rejects_non_positive_rate(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            FrameRateSampler(0)


class ExtractDetectionsTest(unittest.TestCase):
    def test_preserves_original_box_and_anonymous_track_id(self):
        detections = extract_detections(FakeResult(track_id=23))

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].class_name, "Person")
        self.assertEqual(detections[0].track_id, 23)
        self.assertEqual(detections[0].box, (10.0, 20.0, 110.0, 220.0))


class VideoInferenceRunnerTest(unittest.TestCase):
    def test_limits_inference_rate_and_keeps_tracker_persistent(self):
        capture = FakeCapture([FakeFrame() for _ in range(10)], fps=10.0)
        model = FakeModel()
        runner = VideoInferenceRunner(
            model,
            cv2_module=FakeCv2(capture),
            target_fps=5.0,
            device=0,
        )

        frames = list(runner.iter_video(Path("fixture.mp4")))

        self.assertEqual([frame.frame_index for frame in frames], [0, 2, 4, 6, 8])
        self.assertEqual([frame.timestamp_ms for frame in frames], [0, 200, 400, 600, 800])
        self.assertTrue(all(frame.person_track_ids == (17,) for frame in frames))
        self.assertTrue(all(call["persist"] for call in model.calls))
        self.assertTrue(all(call["tracker"] == "bytetrack.yaml" for call in model.calls))
        self.assertTrue(capture.released)

    def test_releases_invalid_capture(self):
        capture = FakeCapture([], opened=False)
        runner = VideoInferenceRunner(
            FakeModel(), cv2_module=FakeCv2(capture)
        )

        with self.assertRaisesRegex(ValueError, "unable to open video"):
            list(runner.iter_video(Path("missing.mp4")))

        self.assertTrue(capture.released)


if __name__ == "__main__":
    unittest.main()
