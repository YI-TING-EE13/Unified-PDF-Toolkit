import os
import unittest
from unittest import mock

from src.app import TOOL_PRESENTATIONS, build_tools_list, presentation_for
from src.ui.motion import MotionController, ease_out_cubic, motion_enabled


class FakeAfterHost:
    def __init__(self) -> None:
        self.callbacks = {}
        self.cancelled = []
        self._next_id = 0

    def after(self, _delay_ms, callback):
        self._next_id += 1
        job = f"after-{self._next_id}"
        self.callbacks[job] = callback
        return job

    def after_cancel(self, job) -> None:
        self.cancelled.append(job)
        self.callbacks.pop(job, None)

    def run(self, job) -> None:
        callback = self.callbacks.pop(job)
        callback()


class MotionControllerTests(unittest.TestCase):
    def test_ease_out_cubic_is_bounded_and_monotonic(self):
        values = [ease_out_cubic(index / 20) for index in range(21)]

        self.assertEqual(values[0], 0.0)
        self.assertEqual(values[-1], 1.0)
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(0.0 <= value <= 1.0 for value in values))

    def test_disabled_motion_immediately_applies_final_state(self):
        host = FakeAfterHost()
        updates = []
        completed = []
        controller = MotionController(host, enabled=False)

        controller.animate(
            "panel",
            200,
            updates.append,
            on_complete=lambda: completed.append(True),
        )

        self.assertEqual(updates, [1.0])
        self.assertEqual(completed, [True])
        self.assertEqual(controller.active_keys, ())
        self.assertEqual(host.callbacks, {})

    def test_tween_reaches_final_state_and_clears_its_key(self):
        host = FakeAfterHost()
        now = [10.0]
        updates = []
        completed = []
        controller = MotionController(host, enabled=True, clock=lambda: now[0])

        controller.animate(
            "panel",
            100,
            updates.append,
            on_complete=lambda: completed.append(True),
        )
        first_job = next(iter(host.callbacks))
        now[0] += 0.05
        host.run(first_job)
        second_job = next(iter(host.callbacks))
        now[0] += 0.05
        host.run(second_job)

        self.assertEqual(updates[0], 0.0)
        self.assertGreater(updates[1], 0.0)
        self.assertLess(updates[1], 1.0)
        self.assertEqual(updates[-1], 1.0)
        self.assertEqual(completed, [True])
        self.assertEqual(controller.active_keys, ())

    def test_new_tween_cancels_the_previous_tween_with_the_same_key(self):
        host = FakeAfterHost()
        now = [20.0]
        first_updates = []
        second_updates = []
        controller = MotionController(host, enabled=True, clock=lambda: now[0])

        controller.animate("view", 200, first_updates.append)
        first_job = next(iter(host.callbacks))
        controller.animate("view", 200, second_updates.append)

        self.assertIn(first_job, host.cancelled)
        self.assertEqual(first_updates, [0.0])
        self.assertEqual(second_updates, [0.0])
        self.assertEqual(controller.active_keys, ("view",))

    def test_reduce_motion_environment_override_wins(self):
        with mock.patch.dict(os.environ, {"PDF_TOOLKIT_REDUCE_MOTION": "1"}):
            self.assertFalse(motion_enabled())
        with mock.patch.dict(os.environ, {"PDF_TOOLKIT_REDUCE_MOTION": "0"}):
            self.assertTrue(motion_enabled())


class ToolPresentationTests(unittest.TestCase):
    def test_every_registered_tool_has_group_and_description(self):
        with mock.patch.dict(os.environ, {"PDF_TOOLKIT_ENABLE_DEV_TOOLS": "1"}):
            tools = build_tools_list()

        self.assertEqual({tool.name for tool in tools}, set(TOOL_PRESENTATIONS))
        for tool in tools:
            presentation = presentation_for(tool.name)
            self.assertTrue(presentation.group)
            self.assertGreater(len(presentation.description), 24)

    def test_unknown_tool_metadata_fails_closed(self):
        with self.assertRaisesRegex(KeyError, "Missing UI presentation metadata"):
            presentation_for("Unregistered Tool")


if __name__ == "__main__":
    unittest.main()
