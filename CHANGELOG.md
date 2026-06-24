# Changelog

## Unreleased

- Added architecture-only scaffolding for optional future advanced local AI OCR, including an ADR, OCR backend abstractions, consent validation structures, a fake Unlimited-OCR test backend, and safe optional-readiness diagnostics.
- Added Settings / Recent consent management for future optional advanced local AI OCR without enabling real model inference.

## 0.5.0 - 2026-06-19

- Added a tag-driven GitHub Release workflow for Python packages, Windows ZIP bundles, and optional installer artifacts.
- Added an Inno Setup installer script and release checklist.
- Added Batch Queue for mixed sequential jobs across compression, PDF-to-image, and PDF-to-Word workflows.
- Added Diagnostics view for dependency, Tkinter, Tesseract, settings, and output-folder checks.
- Added OCR cleanup options: None, Grayscale, Auto Contrast, and Threshold.
- Added user-facing error suggestions for common OCR, permission, page-range, encrypted-PDF, and missing-file failures.
- Expanded unit tests for batch queue, diagnostics, OCR cleanup, and error suggestions.

## 0.4.0 - 2026-06-18

- Added drag-and-drop support for shared file lists when native Tk drag-and-drop is available.
- Added Cancel buttons and cancellation handling for long-running workflows.
- Added completion reports for long workflows, now emitted as TXT, CSV, and JSON.
- Added shared output conflict behavior: rename, overwrite, or skip.
- Added Settings / Recent view for output behavior and recent inputs, outputs, and reports.
- Added PDF to Word OCR Text mode with configurable Tesseract language and render DPI.
- Added GitHub Actions CI and Windows PyInstaller smoke packaging.
- Added MIT LICENSE and aligned package metadata with Python 3.10+.
- Expanded workflow tests, including Page Manager edit operations and mocked OCR conversion.

## 0.3.0

- Added PDF to Word conversion with Preserve Layout, Text Only, and Page Images modes.
- Added PDF to Word preview and preflight checks.
- Added merged PDF preview and optional post-merge compression.
- Enlarged the application workspace for preview-heavy workflows.
- Added progress feedback for long-running tools.
