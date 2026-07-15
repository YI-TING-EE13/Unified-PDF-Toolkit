# Command-Line and Headless Batch Guide

The `pdf-toolkit` command runs supported Batch Queue operations without opening
the desktop interface. It is intended for local scripts, scheduled jobs, CI, and
machines without a graphical display.

## Install and verify

From a source checkout:

```powershell
uv sync
uv run --no-sync pdf-toolkit --version
uv run --no-sync pdf-toolkit --help
```

The wheel also installs the same console command. The GUI remains available as
`pdf-toolkit-gui` or through the normal launchers and packaged application.

## Direct commands

```powershell
pdf-toolkit compress file1.pdf image.png -o output --level Medium
pdf-toolkit pdf-to-images scan.pdf -o output --dpi 200 --format png --pages "1-4,7"
pdf-toolkit pdf-to-word report.pdf -o output --mode text --pages "1-10"
pdf-toolkit pdf-to-word scan.pdf -o output --mode ocr --ocr-lang eng+chi_tra
```

PDF-to-Word modes are `text`, `page-images`, and `ocr`. OCR requires the
Tesseract executable and every language data file named by `--ocr-lang`.
OCR preprocessing supports `None`, `Grayscale`, `Auto Contrast`, and
`Threshold`; OCR DPI is limited to 100-600 to avoid accidental memory exhaustion.

All direct commands accept:

- `--conflict rename|overwrite|skip` (default: `rename`)
- `--stop-on-error`
- `--json` for a machine-readable final summary
- `--quiet` to suppress progress messages

## Managed Unlimited-OCR commands

The advanced local OCR deployment commands are separate from normal batch jobs.
Inspection, planning, and status are read-only:

```powershell
pdf-toolkit ocr inspect --json
pdf-toolkit ocr plan --json
pdf-toolkit ocr status --json
```

`ocr plan` prints the current compatibility decision, exact argv-only private
environment plan, pinned source/model revisions, estimated download and disk
cost, system-change boundary, and consent summary. A plan may be blocked or
marked experimental; detecting an NVIDIA GPU does not make it automatically
supported.

Setup requires the current plan ID and six separate acknowledgements. There is
no general `--yes` bypass:

```powershell
pdf-toolkit ocr setup `
  --plan-id <reviewed-plan-id> `
  --ack-large-download `
  --ack-private-environment `
  --ack-custom-code `
  --ack-resource-usage `
  --ack-local-processing-and-temporary-files `
  --ack-no-performance-guarantee
```

Ctrl+C requests safe cancellation of the current private subprocess. Running
the same reviewed plan again resumes its journal and reusable model cache.

Cleanup is restricted to APP-managed paths and requires the exact current plan
ID:

```powershell
pdf-toolkit ocr uninstall --confirm-plan-id <reviewed-plan-id>
pdf-toolkit ocr uninstall --confirm-plan-id <reviewed-plan-id> --remove-model --clear-download-cache
```

Full behavior, privacy boundaries, and recovery rules are documented in
[Managed Unlimited-OCR Setup](runtime/managed_unlimited_ocr.md).

## JSON manifest

Edit the included example so `source` points to an existing PDF, then run it:

```powershell
pdf-toolkit batch docs/examples/batch-manifest.json --json
```

A manifest can be either a jobs array or an object with `jobs`, `output_dir`,
and `conflict_policy` fields:

```json
{
  "output_dir": "output",
  "conflict_policy": "rename",
  "jobs": [
    {
      "source": "sample.pdf",
      "operation": "pdf-to-images",
      "options": {
        "dpi": 150,
        "format": "png",
        "page_range": "1-3"
      }
    },
    {
      "source": "sample.pdf",
      "operation": "pdf-to-word-text",
      "options": {
        "page_range": "1-3"
      }
    }
  ]
}
```

Supported manifest operation names are:

- `compress`
- `pdf-to-images`
- `pdf-to-word-text`
- `pdf-to-word-images`
- `pdf-to-word-ocr`

Relative source paths and an unqualified manifest `output_dir` are resolved from
the manifest's folder, not the caller's current directory. A command-line
`--output-dir` or `--conflict` overrides the manifest value.

## Reports and exit codes

Every run writes TXT, CSV, and JSON workflow reports to the output folder. The
final JSON summary contains `success`, `failed`, `skipped`, `cancelled`, and
`report_path`.

| Exit code | Meaning |
| --- | --- |
| `0` | Run completed without failed jobs. Skipped outputs are not failures. |
| `1` | One or more jobs failed. |
| `2` | Command or manifest validation failed. |
| `3` | Managed OCR compatibility is `UNSUPPORTED` or `UNKNOWN`. |
| `4` | Managed OCR setup failed with a structured deployment error. |
| `130` | Ctrl+C cancellation was requested. |

Cancellation is cooperative: the current file finishes or fails, then the
runner stops before the next queued job. A second Ctrl+C aborts immediately.

## Automation recommendations

- Use absolute source paths when manifests will move between machines.
- Use `--conflict skip` for resumable runs and `--conflict rename` when every
  result must be retained.
- Capture stdout when using `--json`; progress is written to stderr unless
  `--quiet` is set.
- Check the exit code and preserve the generated JSON report when a run fails.
- Run Diagnostics in the GUI before scheduling OCR to verify Tesseract language
  data, especially `chi_tra` or `chi_sim`.
