import sys
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from video_inference import (  # noqa: E402
    FrameRateSampler,
    RealtimePacer,
    TrackedDetection,
    VideoInferenceRunner,
    _LatestInferenceWorker,
    extract_detections,
    write_annotated_video,
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
    FONT_HERSHEY_SIMPLEX = 0
    LINE_AA = 16

    def __init__(self, capture):
        self.capture = capture
        self.writers = []

    def VideoCapture(self, _path):
        return self.capture

    def rectangle(self, frame, point1, point2, color, thickness):
        x1, y1 = point1
        x2, y2 = point2
        frame[y1 : y1 + thickness, x1 : x2 + 1] = color
        frame[y2 - thickness + 1 : y2 + 1, x1 : x2 + 1] = color
        frame[y1 : y2 + 1, x1 : x1 + thickness] = color
        frame[y1 : y2 + 1, x2 - thickness + 1 : x2 + 1] = color

    def putText(self, frame, _label, origin, _font, _scale, color, _thickness, _line):
        x, y = origin
        frame[y, x] = color

    def VideoWriter_fourcc(self, *codec):
        return "".join(codec)

    def VideoWriter(self, path, codec, fps, size):
        writer = FakeWriter(path, codec, fps, size)
        self.writers.append(writer)
        return writer


class FakeWriter:
    def __init__(self, path, codec, fps, size, opened=True):
        self.path = path
        self.codec = codec
        self.fps = fps
        self.size = size
        self.opened = opened
        self.frames = []
        self.released = False

    def isOpened(self):
        return self.opened

    def write(self, frame):
        self.frames.append(frame.copy())

    def release(self):
        self.released = True


class FakeModel:
    def __init__(self):
        self.calls = []

    def track(self, **kwargs):
        self.calls.append(kwargs)
        return [FakeResult()]


class SlowAfterWarmupModel(FakeModel):
    def __init__(self):
        super().__init__()
        self.entered = Event()
        self.release = Event()
        self.source_values = []

    def track(self, **kwargs):
        self.calls.append(kwargs)
        self.source_values.append(int(kwargs["source"][0, 0, 0]))
        if len(self.calls) > 1:
            self.entered.set()
            self.release.wait(timeout=2)
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
    def test_rebases_after_late_frame_then_resumes_sleep(self):
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
            worker.close(1.0)

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
            worker.close(1.0)

    def test_close_times_out_when_inference_does_not_return(self):
        entered = Event()
        release = Event()

        def hang(_frame):
            entered.set()
            release.wait(timeout=2)
            return ()

        worker = _LatestInferenceWorker(hang)
        worker.start()
        worker.submit_latest(np.zeros((2, 2, 3), dtype=np.uint8), 0)
        self.assertTrue(entered.wait(timeout=1))

        try:
            with self.assertRaisesRegex(RuntimeError, "did not stop within"):
                worker.close(0.01)
        finally:
            release.set()
            worker.thread.join(timeout=1)

        self.assertFalse(worker.thread.is_alive())


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

    def test_realtime_frames_arrive_at_wall_clock_cadence(self):
        capture = FakeCapture(
            [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(5)],
            fps=20.0,
        )
        runner = VideoInferenceRunner(
            FakeModel(),
            cv2_module=FakeCv2(capture),
            target_fps=5.0,
            renderer=lambda frame, _detections: frame.copy(),
        )

        arrival_times = []
        for _frame in runner.iter_video(Path("fixture.mp4"), realtime=True):
            arrival_times.append(time.monotonic())

        elapsed = arrival_times[-1] - arrival_times[0]
        self.assertGreaterEqual(elapsed, 0.16)
        self.assertLess(elapsed, 0.8)

    def test_renderer_changes_pixels_without_mutating_original_frame(self):
        capture = FakeCapture([])
        runner = VideoInferenceRunner(
            FakeModel(), cv2_module=FakeCv2(capture)
        )
        original = np.zeros((240, 160, 3), dtype=np.uint8)
        detection = TrackedDetection(
            class_id=6,
            class_name="Person",
            confidence=0.91,
            box=(10.0, 20.0, 110.0, 220.0),
            track_id=17,
        )

        annotated = runner._render_detections(original, (detection,))

        self.assertFalse(np.shares_memory(original, annotated))
        self.assertEqual(int(original.sum()), 0)
        self.assertGreater(int(annotated.sum()), 0)
        np.testing.assert_array_equal(annotated[20, 10], [0, 200, 0])

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

    def test_slow_realtime_ai_does_not_block_complete_frame_output(self):
        source_frames = [
            np.full((2, 2, 3), index, dtype=np.uint8) for index in range(8)
        ]
        capture = FakeCapture(source_frames, fps=10.0)
        model = SlowAfterWarmupModel()
        clock = FakeClock()
        runner = VideoInferenceRunner(
            model,
            cv2_module=FakeCv2(capture),
            target_fps=5.0,
            renderer=lambda frame, _detections: frame.copy(),
            worker_shutdown_timeout_seconds=1.0,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        stream = runner.iter_video(Path("fixture.mp4"), realtime=True)

        output = [next(stream) for _ in range(3)]
        self.assertTrue(model.entered.wait(timeout=1))
        output.extend(next(stream) for _ in range(5))
        model.release.set()
        deadline = time.monotonic() + 1
        while len(model.source_values) < 3 and time.monotonic() < deadline:
            time.sleep(0.01)
        with self.assertRaises(StopIteration):
            next(stream)

        self.assertEqual([frame.frame_index for frame in output], list(range(8)))
        self.assertEqual(
            [frame.timestamp_ms for frame in output],
            [0, 100, 200, 300, 400, 500, 600, 700],
        )
        self.assertEqual(model.source_values, [0, 2, 6])
        self.assertTrue(
            all(frame.annotated_frame.shape == (2, 2, 3) for frame in output)
        )
        self.assertTrue(capture.released)

    def test_writes_every_annotated_frame_with_source_video_boundaries(self):
        source_frames = [
            np.full((36, 64, 3), index, dtype=np.uint8) for index in range(4)
        ]
        capture = FakeCapture(source_frames, fps=10.0)
        cv2_module = FakeCv2(capture)
        runner = VideoInferenceRunner(
            FakeModel(),
            cv2_module=cv2_module,
            target_fps=5.0,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "annotated.mp4"
            summary = write_annotated_video(
                runner,
                Path("fixture.mp4"),
                output_path,
            )

        writer = cv2_module.writers[0]
        self.assertEqual(writer.codec, "mp4v")
        self.assertEqual(writer.fps, 10.0)
        self.assertEqual(writer.size, (64, 36))
        self.assertEqual(len(writer.frames), 4)
        self.assertTrue(
            all(
                np.array_equal(frame[20, 10], [0, 200, 0])
                for frame in writer.frames
            )
        )
        self.assertTrue(writer.released)
        self.assertEqual(summary.frame_count, 4)
        self.assertEqual((summary.image_width, summary.image_height), (64, 36))
        self.assertEqual(summary.fps, 10.0)

    def test_worker_timeout_still_releases_video_capture(self):
        capture = FakeCapture(
            [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(3)],
            fps=10.0,
        )
        model = SlowAfterWarmupModel()
        clock = FakeClock()
        runner = VideoInferenceRunner(
            model,
            cv2_module=FakeCv2(capture),
            target_fps=5.0,
            renderer=lambda frame, _detections: frame.copy(),
            worker_shutdown_timeout_seconds=0.01,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        stream = runner.iter_video(Path("fixture.mp4"), realtime=True)

        try:
            next(stream)
            next(stream)
            next(stream)
            self.assertTrue(model.entered.wait(timeout=1))
            with self.assertRaisesRegex(RuntimeError, "did not stop within"):
                next(stream)
        finally:
            model.release.set()

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
