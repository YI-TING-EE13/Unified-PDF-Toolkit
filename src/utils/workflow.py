"""Shared helpers for long-running tool workflows."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Event
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional

from .file_ops import format_size, get_file_size
from .settings import add_recent_path, get_setting


class CancellationToken:
    """Small thread-safe cancellation flag shared by GUI and worker code."""

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


@dataclass
class WorkflowRecord:
    source: str
    output: str = ""
    status: str = "success"
    message: str = ""
    input_size: Optional[int] = None
    output_size: Optional[int] = None


@dataclass
class WorkflowReport:
    tool_name: str
    output_dir: str
    started_at: datetime = field(default_factory=datetime.now)
    options: Dict[str, Any] = field(default_factory=dict)
    records: List[WorkflowRecord] = field(default_factory=list)
    _started_timer: float = field(default_factory=perf_counter)

    def add(
        self,
        source: str,
        output: str = "",
        status: str = "success",
        message: str = "",
    ) -> None:
        self.records.append(
            WorkflowRecord(
                source=source,
                output=output,
                status=status,
                message=message,
                input_size=get_file_size(source) if source else None,
                output_size=get_file_size(output) if output else None,
            )
        )

    @property
    def elapsed_seconds(self) -> float:
        return perf_counter() - self._started_timer

    def write(self) -> str:
        output_root = Path(self.output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        timestamp = self.started_at.strftime("%Y%m%d_%H%M%S")
        slug = "".join(
            ch.lower() if ch.isalnum() else "_" for ch in self.tool_name
        ).strip("_")
        report_base = output_root / f"{slug}_report_{timestamp}"
        txt_path = report_base.with_suffix(".txt")
        csv_path = report_base.with_suffix(".csv")
        json_path = report_base.with_suffix(".json")

        summary = self._summary()

        lines = [
            f"Tool: {self.tool_name}",
            f"Started: {self.started_at.isoformat(timespec='seconds')}",
            f"Elapsed seconds: {self.elapsed_seconds:.2f}",
            f"Output folder: {output_root}",
            (
                "Summary: "
                f"success={summary['success']}, failed={summary['failed']}, "
                f"skipped={summary['skipped']}, cancelled={summary['cancelled']}"
            ),
        ]
        if self.options:
            lines.append("")
            lines.append("Options:")
            for key, value in sorted(self.options.items()):
                lines.append(f"- {key}: {value}")

        lines.append("")
        lines.append("Files:")
        for record in self.records:
            lines.append(f"- [{record.status}] {record.source}")
            if record.output:
                lines.append(f"  output: {record.output}")
            if record.input_size is not None:
                lines.append(f"  input_size: {format_size(record.input_size)}")
            if record.output_size is not None:
                lines.append(f"  output_size: {format_size(record.output_size)}")
            if (
                record.input_size is not None
                and record.output_size is not None
                and record.input_size
            ):
                saved = record.input_size - record.output_size
                pct = (saved / record.input_size) * 100
                lines.append(f"  saved: {format_size(saved)} ({pct:.1f}%)")
            if record.message:
                lines.append(f"  message: {record.message}")

        txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._write_csv(csv_path)
        self._write_json(json_path, summary)

        for path in (txt_path, csv_path, json_path):
            add_recent_path("recent.reports", str(path))
        return str(txt_path)

    def _summary(self) -> Dict[str, int]:
        return {
            "success": len([r for r in self.records if r.status == "success"]),
            "failed": len([r for r in self.records if r.status == "failed"]),
            "skipped": len([r for r in self.records if r.status == "skipped"]),
            "cancelled": len([r for r in self.records if r.status == "cancelled"]),
        }

    def _record_rows(self) -> List[Dict[str, Any]]:
        rows = []
        for record in self.records:
            saved_bytes = None
            saved_percent = None
            if (
                record.input_size is not None
                and record.output_size is not None
                and record.input_size
            ):
                saved_bytes = record.input_size - record.output_size
                saved_percent = (saved_bytes / record.input_size) * 100
            rows.append(
                {
                    "status": record.status,
                    "source": record.source,
                    "output": record.output,
                    "message": record.message,
                    "input_size": record.input_size,
                    "output_size": record.output_size,
                    "saved_bytes": saved_bytes,
                    "saved_percent": saved_percent,
                }
            )
        return rows

    def _write_csv(self, path: Path) -> None:
        rows = self._record_rows()
        fieldnames = [
            "status",
            "source",
            "output",
            "message",
            "input_size",
            "output_size",
            "saved_bytes",
            "saved_percent",
        ]
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _write_json(self, path: Path, summary: Dict[str, int]) -> None:
        payload = {
            "tool": self.tool_name,
            "started": self.started_at.isoformat(timespec="seconds"),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "output_dir": str(Path(self.output_dir)),
            "summary": summary,
            "options": self.options,
            "records": self._record_rows(),
        }
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def get_conflict_policy() -> str:
    value = get_setting("output.conflict_policy", "rename")
    return value if value in {"rename", "overwrite", "skip"} else "rename"


def remember_inputs(paths: Iterable[str]) -> None:
    for path in paths:
        add_recent_path("recent.inputs", path)


def remember_output(path: str) -> None:
    add_recent_path("recent.outputs", path)
