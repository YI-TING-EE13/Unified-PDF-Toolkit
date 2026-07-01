# Getting Started: Document OCR with Tesseract

This guide is for first-time users who want to turn a PDF or image into local
TXT or Markdown text files.

Document OCR runs on your computer. Files are not uploaded by Unified PDF
Toolkit. The default OCR backend is Tesseract.

## What Document OCR Does

Document OCR reads text from:

- scanned PDF files;
- image-only PDF pages;
- image files such as PNG, JPG, JPEG, TIF, TIFF, and BMP.

It writes the recognized text to local output files. It does not edit the
original PDF or image.

## Before You Start

Install Tesseract OCR and the language data you need. For English, use `eng`.
For Traditional Chinese, use `chi_tra`. You can combine languages with a plus
sign, for example `eng+chi_tra`.

If Tesseract is not installed or is not on PATH, the app can still open, but
Document OCR will not be able to run the default OCR backend.

## Open the App

Windows installer or portable bundle:

1. Start Unified PDF Toolkit from the Start Menu, desktop shortcut, or extracted
   app folder.
2. Select `Document OCR` from the sidebar.

Source checkout:

```powershell
.\.venv\Scripts\python.exe src\app.py
```

If the source app reports that Tk/Tcl is unavailable, use the packaged app or a
Python runtime with working Tk support.

## Choose a PDF or Image

1. In `Document OCR`, click the file picker for `PDF/Image Files`.
2. Choose one or more PDF or image files.
3. Keep the files in the order you want them processed.

Use small files for a first test. A one-page scan or a simple image is easiest
to verify.

## Choose TXT or Markdown

In `Output Options`:

- select `TXT` for a plain text file;
- select `Markdown` for a `.md` file with page headings;
- select both if you want both formats.

For `Tesseract language`, enter the installed language code, such as:

```text
eng
chi_tra
eng+chi_tra
```

## Choose the Output Folder

Set `Output Folder` to a folder you control, such as a folder under Documents.
Document OCR creates new local output files there.

Output names are based on the input file name and include `document_ocr`.
If a file already exists, the app follows the configured output conflict policy.

## Run OCR

1. Confirm the backend is `Tesseract OCR (default)`.
2. Click `Run Document OCR`.
3. Wait for the progress bar and status message.
4. When the run completes, open the output folder from the app or browse to it
   manually.

The app writes OCR text only to the selected output files. Default status and
diagnostic summaries should not print the full OCR text.

## Common Tesseract Limitations

Tesseract is useful, but it is not perfect:

- low-resolution scans may produce missing or incorrect words;
- skewed, rotated, blurry, or shadowed pages reduce accuracy;
- handwriting is usually unreliable;
- complex tables and multi-column layouts may not preserve structure;
- language data must be installed before you can use that language code;
- very large PDFs can take time because each page must be rendered before OCR.

For better results, try a clearer scan, a higher-resolution source image, or a
single-language setting that matches the document.

## Basic Troubleshooting

| Problem | What to check |
| --- | --- |
| OCR fails immediately | Confirm Tesseract is installed and available on PATH. |
| Text is in the wrong language | Confirm the language data is installed and the language code is correct. |
| No output files appear | Confirm the output folder is writable and TXT or Markdown is selected. |
| Output is low quality | Try a clearer scan, fewer languages, or a higher-resolution image. |
| App cannot open from source | Use the packaged app or a Python runtime with working Tk support. |

## What Not To Share In Beta Reports

When reporting a problem, do not paste private document text, screenshots of
private pages, generated OCR output, or source file paths unless you intentionally
approved a private debug case.
