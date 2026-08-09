"""Small, cancellable motion primitives for Tk widgets and windows."""

from __future__ import annotations

import ctypes
import os
import sys
import time
from collections.abc import Callable
from typing import Any


ProgressCallback = Callable[[float], None]
CompletionCallback = Callable[[], None]
EasingFunction = Callable[[float], float]


def ease_out_cubic(progress: float) -> float:
    """Return a smooth decelerating curve for a normalized progress value."""

    bounded = min(1.0, max(0.0, progress))
    return 1.0 - (1.0 - bounded) ** 3


def motion_enabled() -> bool:
    """Honor an explicit override and the Windows client-animation setting."""

    override = os.environ.get("PDF_TOOLKIT_REDUCE_MOTION", "").strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return False
    if override in {"0", "false", "no", "off"}:
        return True

    if sys.platform == "win32":
        try:
            enabled = ctypes.c_int()
            succeeded = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
                0x1042, 0, ctypes.byref(enabled), 0
            )
            if succeeded:
                return bool(enabled.value)
        except (AttributeError, OSError):
            pass
    return True


class MotionController:
    """Run keyed tweens on a Tk event loop and cancel superseded work."""

    def __init__(
        self,
        host: Any,
        *,
        enabled: bool | None = None,
        frame_ms: int = 16,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.host = host
        self.enabled = motion_enabled() if enabled is None else enabled
        self.frame_ms = max(8, frame_ms)
        self._clock = clock
        self._jobs: dict[str, Any] = {}
        self._tokens: dict[str, object] = {}

    @property
    def active_keys(self) -> tuple[str, ...]:
        return tuple(self._jobs)

    def animate(
        self,
        key: str,
        duration_ms: int,
        update: ProgressCallback,
        *,
        on_complete: CompletionCallback | None = None,
        easing: EasingFunction = ease_out_cubic,
    ) -> None:
        """Animate one keyed value; a newer tween with the same key wins."""

        self.cancel(key)
        if not self.enabled or duration_ms <= 0:
            update(1.0)
            if on_complete:
                on_complete()
            return

        token = object()
        self._tokens[key] = token
        started = self._clock()
        duration_seconds = duration_ms / 1000.0
        update(0.0)

        def tick() -> None:
            if self._tokens.get(key) is not token:
                return
            raw = min(1.0, max(0.0, (self._clock() - started) / duration_seconds))
            update(easing(raw))
            if raw >= 1.0:
                self._jobs.pop(key, None)
                self._tokens.pop(key, None)
                if on_complete:
                    on_complete()
                return
            self._jobs[key] = self.host.after(self.frame_ms, tick)

        self._jobs[key] = self.host.after(self.frame_ms, tick)

    def cancel(self, key: str) -> None:
        job = self._jobs.pop(key, None)
        self._tokens.pop(key, None)
        if job is not None:
            try:
                self.host.after_cancel(job)
            except Exception:
                pass

    def cancel_all(self) -> None:
        for key in tuple(self._jobs):
            self.cancel(key)


class WindowMotion:
    """Animate a Tk/Toplevel window entering and leaving when alpha is supported."""

    def __init__(self, window: Any, *, enabled: bool | None = None) -> None:
        self.window = window
        self.controller = MotionController(window, enabled=enabled)
        self._alpha_supported = self._set_alpha(0.0) if self.controller.enabled else False

    def show(self, duration_ms: int = 180) -> None:
        if not self._alpha_supported:
            self._set_alpha(1.0)
            return
        self.controller.animate(
            "window-opacity",
            duration_ms,
            self._set_alpha,
            on_complete=lambda: self._set_alpha(1.0),
        )

    def close(
        self,
        *,
        duration_ms: int = 120,
        on_complete: CompletionCallback | None = None,
    ) -> None:
        finish = on_complete or self.window.destroy
        if not self._alpha_supported:
            finish()
            return
        try:
            start_alpha = float(self.window.attributes("-alpha"))
        except Exception:
            start_alpha = 1.0
        self.controller.animate(
            "window-opacity",
            duration_ms,
            lambda value: self._set_alpha(start_alpha * (1.0 - value)),
            on_complete=finish,
        )

    def _set_alpha(self, value: float) -> bool:
        try:
            self.window.attributes("-alpha", min(1.0, max(0.0, value)))
            return True
        except Exception:
            return False
