import sys
import time
import unittest
from pathlib import Path
from threading import Event

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from video_inference import (  # noqa: E402
    FrameRateSampler,
    RealtimePacer,
    VideoInferenceRunner,
    _LatestInferenceWorker,
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


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


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


class RealtimePacerTest(unittest.TestCase):
    def test_rebases_after_late_frame_instead_of_chasing(self):
        clock = FakeClock()
        pacer = RealtimePacer(
            10.0,
            1.0,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )

        pacer.wait()
        clock.now = 0.35
        pacer.wait()
        pacer.wait()

        self.assertEqual(len(clock.sleeps), 1)
        self.assertAlmostEqual(clock.sleeps[0], 0.1)


class ExtractDetectionsTest(unittest.TestCase):
    def test_preserves_original_box_and_anonymous_track_id(self):
        detections = extract_detections(FakeResult(track_id=23))

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].class_name, "Person")
        self.assertEqual(detections[0].track_id, 23)
        self.assertEqual(detections[0].box, (10.0, 20.0, 110.0, 220.0))


class LatestInferenceWorkerTest(unittest.TestCase):
    def test_discards_stale_pending_sample_when_inference_is_slow(self):
        entered = Event()
        release = Event()
        calls = []

        def infer(frame):
            value = int(frame[0, 0, 0])
            calls.append(value)
            if value == 0:
                entered.set()
                release.wait(timeout=2)
            return ()

        worker = _LatestInferenceWorker(infer)
        worker.start()
        try:
            worker.submit_latest(np.full((2, 2, 3), 0, dtype=np.uint8), 0)
            self.assertTrue(entered.wait(timeout=1))
            worker.submit_latest(np.full((2, 2, 3), 1, dtype=np.uint8), 100)
            worker.submit_latest(np.full((2, 2, 3), 2, dtype=np.uint8), 200)
            release.set()

            deadline = time.monotonic() + 1
            snapshot = None
            while time.monotonic() < deadline:
                snapshot = worker.latest_after(1)
                if snapshot is not None:
                    break
                time.sleep(0.01)

            self.assertIsNotNone(snapshot)
            self.assertEqual(calls, [0, 2])
            self.assertEqual(snapshot.timestamp_ms, 200)
        finally:
            release.set()
            worker.close()

    def test_propagates_background_inference_failure(self):
        def fail(_frame):
            raise ValueError("broken model")

        worker = _LatestInferenceWorker(fail)
        worker.start()
        worker.submit_latest(np.zeros((2, 2, 3), dtype=np.uint8), 0)

        deadline = time.monotonic() + 1
        while worker.thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)

        with self.assertRaisesRegex(RuntimeError, "background video inference failed"):
            worker.close()


class VideoInferenceRunnerTest(unittest.TestCase):
    def test_outputs_every_playback_frame_and_reuses_latest_overlay(self):
        frames = [np.full((36, 64, 3), index, dtype=np.uint8) for index in range(10)]
        capture = FakeCapture(frames, fps=10.0)
        model = FakeModel()
        render_calls = []

        def render(frame, detections):
            render_calls.append((int(frame[0, 0, 0]), len(detections)))
            return frame.copy()

        runner = VideoInferenceRunner(
            model,
            cv2_module=FakeCv2(capture),
            target_fps=5.0,
            device=0,
            renderer=render,
        )

        output = list(runner.iter_video(Path("fixture.mp4")))

        self.assertEqual([frame.frame_index for frame in output], list(range(10)))
        self.assertEqual(len(model.calls), 5)
        self.assertEqual(
            [frame.frame_index for frame in output if frame.analysis_updated],
            [0, 2, 4, 6, 8],
        )
        self.assertEqual(
            [frame.analysis_timestamp_ms for frame in output[:4]],
            [0, 0, 200, 200],
        )
        self.assertTrue(all(frame.person_track_ids == (17,) for frame in output))
        self.assertTrue(all(call["persist"] for call in model.calls))
        self.assertEqual(len(render_calls), 10)
        self.assertTrue(all(count == 1 for _, count in render_calls))
        self.assertTrue(capture.released)

    def test_max_frames_limits_playback_frames_not_ai_samples(self):
        capture = FakeCapture(
            [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(10)],
            fps=10.0,
        )
        model = FakeModel()
        runner = VideoInferenceRunner(
            model,
            cv2_module=FakeCv2(capture),
            target_fps=5.0,
            renderer=lambda frame, _detections: frame.copy(),
        )

        output = list(
            runner.iter_video(Path("fixture.mp4"), max_playback_frames=3)
        )

        self.assertEqual(len(output), 3)
        self.assertEqual(len(model.calls), 2)
        self.assertTrue(capture.released)

    def test_realtime_warms_first_analysis_before_playback(self):
        capture = FakeCapture(
            [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(2)],
            fps=10.0,
        )
        model = FakeModel()
        clock = FakeClock()
        runner = VideoInferenceRunner(
            model,
            cv2_module=FakeCv2(capture),
            target_fps=5.0,
            renderer=lambda frame, _detections: frame.copy(),
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )

        output = list(
            runner.iter_video(
                Path("fixture.mp4"),
                realtime=True,
                max_playback_frames=1,
            )
        )

        self.assertEqual(len(model.calls), 1)
        self.assertTrue(output[0].analysis_updated)
        self.assertEqual(output[0].analysis_timestamp_ms, 0)
        self.assertEqual(output[0].person_track_ids, (17,))

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
