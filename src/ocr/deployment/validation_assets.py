"""Generate deterministic, synthetic OCR validation documents and page images."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz


@dataclass(frozen=True)
class ValidationCase:
    case_id: str
    category: str
    image_path: Path
    pdf_path: Path
    expected_terms: tuple[str, ...]
    rotation_degrees: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "image_path": str(self.image_path),
            "pdf_path": str(self.pdf_path),
            "expected_terms": self.expected_terms,
            "rotation_degrees": self.rotation_degrees,
        }


def create_validation_suite(root: Path, *, dpi: int = 144) -> tuple[ValidationCase, ...]:
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    cases = (
        _pure_text(root, dpi),
        _table(root, dpi),
        _mixed_language(root, dpi),
        _complex_layout(root, dpi),
        _rotated(root, dpi),
    )
    (root / "suite.json").write_text(
        json.dumps(
            {"schema_version": "1.0", "synthetic": True, "cases": [case.to_dict() for case in cases]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return cases


def _pure_text(root: Path, dpi: int) -> ValidationCase:
    doc, page = _new_document()
    page.insert_text((72, 90), "Unified PDF Toolkit OCR Test", fontsize=24, fontname="helv")
    page.insert_text((72, 135), "Invoice ID: UPT-2026-0714", fontsize=15, fontname="helv")
    page.insert_text((72, 170), "Total: USD 1,234.56", fontsize=15, fontname="helv")
    page.insert_text((72, 205), "This file contains synthetic test data only.", fontsize=13, fontname="helv")
    return _save_case(
        doc,
        root,
        "pure-text",
        "pure_text",
        ("Unified PDF Toolkit", "UPT-2026-0714", "1,234.56"),
        dpi=dpi,
    )


def _table(root: Path, dpi: int) -> ValidationCase:
    doc, page = _new_document()
    page.insert_text((72, 72), "Quarterly Inventory Table", fontsize=22, fontname="helv")
    left, top, width, row_height = 72, 110, 450, 42
    columns = (0, 190, 310, 450)
    rows = (
        ("Item", "Quantity", "Status"),
        ("Scanner", "12", "Ready"),
        ("Printer", "7", "Review"),
        ("Archive Box", "105", "Ready"),
    )
    for row_index in range(len(rows) + 1):
        y = top + row_index * row_height
        page.draw_line((left, y), (left + width, y), color=(0, 0, 0), width=1)
    for offset in columns:
        page.draw_line(
            (left + offset, top),
            (left + offset, top + len(rows) * row_height),
            color=(0, 0, 0),
            width=1,
        )
    for row_index, row in enumerate(rows):
        y = top + row_index * row_height + 27
        for column_index, text in enumerate(row):
            page.insert_text(
                (left + columns[column_index] + 8, y),
                text,
                fontsize=12,
                fontname="helv",
            )
    return _save_case(
        doc,
        root,
        "table",
        "table",
        ("Quarterly Inventory Table", "Scanner", "Archive Box", "105"),
        dpi=dpi,
    )


def _mixed_language(root: Path, dpi: int) -> ValidationCase:
    doc, page = _new_document()
    page.insert_text((72, 85), "中英文混合 OCR 測試", fontsize=24, fontname="china-s")
    page.insert_text((72, 130), "文件編號 Document ID: TW-2026-0714", fontsize=16, fontname="china-s")
    page.insert_text((72, 170), "狀態 Status: 已完成 Complete", fontsize=16, fontname="china-s")
    page.insert_text((72, 210), "金額 Amount: NT$ 9,876", fontsize=16, fontname="china-s")
    return _save_case(
        doc,
        root,
        "mixed-zh-en",
        "mixed_language",
        ("中英文", "Document ID", "TW-2026-0714", "NT$ 9,876"),
        dpi=dpi,
    )


def _complex_layout(root: Path, dpi: int) -> ValidationCase:
    doc, page = _new_document()
    page.insert_text((72, 70), "Complex Layout Validation", fontsize=22, fontname="helv")
    page.draw_rect(fitz.Rect(72, 95, 270, 420), color=(0.2, 0.2, 0.2), width=1)
    page.draw_rect(fitz.Rect(300, 95, 522, 420), color=(0.2, 0.2, 0.2), width=1)
    left_text = (
        "LEFT COLUMN\n"
        "Project: Aurora\n"
        "Owner: LAB-606\n"
        "Priority: High\n\n"
        "Milestone A\nMilestone B\nMilestone C"
    )
    right_text = (
        "RIGHT COLUMN\n"
        "Build: 2026.07\n"
        "Result: PASS\n"
        "Pages: 128\n\n"
        "Notes\nNo external upload\nLocal processing"
    )
    page.insert_textbox(fitz.Rect(85, 110, 255, 405), left_text, fontsize=12, fontname="helv")
    page.insert_textbox(fitz.Rect(315, 110, 505, 405), right_text, fontsize=12, fontname="helv")
    page.insert_text((72, 470), "Footer Reference: COMPLEX-42", fontsize=13, fontname="helv")
    return _save_case(
        doc,
        root,
        "complex-layout",
        "complex_layout",
        ("LEFT COLUMN", "RIGHT COLUMN", "Aurora", "COMPLEX-42"),
        dpi=dpi,
    )


def _rotated(root: Path, dpi: int) -> ValidationCase:
    doc, page = _new_document()
    page.insert_text((72, 100), "ROTATED OCR VALIDATION", fontsize=25, fontname="helv")
    page.insert_text((72, 145), "Rotation angle: 90 degrees", fontsize=16, fontname="helv")
    page.insert_text((72, 185), "Reference: ROTATE-0090", fontsize=16, fontname="helv")
    page.set_rotation(90)
    return _save_case(
        doc,
        root,
        "rotated-90",
        "rotation",
        ("ROTATED OCR VALIDATION", "ROTATE-0090"),
        dpi=dpi,
        rotation_degrees=90,
    )


def _new_document() -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open()
    return doc, doc.new_page(width=595, height=842)


def _save_case(
    doc: fitz.Document,
    root: Path,
    case_id: str,
    category: str,
    expected_terms: tuple[str, ...],
    *,
    dpi: int,
    rotation_degrees: int = 0,
) -> ValidationCase:
    pdf_path = root / f"{case_id}.pdf"
    image_path = root / f"{case_id}.png"
    pdf_path.unlink(missing_ok=True)
    image_path.unlink(missing_ok=True)
    doc.save(pdf_path, garbage=4, deflate=True)
    page = doc[0]
    pixmap = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    pixmap.save(image_path)
    doc.close()
    return ValidationCase(
        case_id=case_id,
        category=category,
        image_path=image_path,
        pdf_path=pdf_path,
        expected_terms=expected_terms,
        rotation_degrees=rotation_degrees,
    )
