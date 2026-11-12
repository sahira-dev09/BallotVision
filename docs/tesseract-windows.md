# Tesseract OCR on Windows

BallotVision uses the `pytesseract` Python package to call Tesseract. Installing that package does **not** install the Tesseract program, and it does **not** install the English or Malay language files.

BallotVision does not read images with Pillow. `pytesseract` still requires Pillow to be installed because the package imports it.

## 1. Install Tesseract

Use a source you already trust, such as the Windows Package Manager entry published as `UB-Mannheim.TesseractOCR`, or the installer linked from the official Tesseract documentation at [https://github.com/tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract).

In an elevated PowerShell window:

```powershell
winget install -e --id UB-Mannheim.TesseractOCR
```

The usual program path is:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

## 2. Install English and Malay language data

The OCR service requests both `eng` and `msa`. If either file is missing, BallotVision returns an error and does not invent text.

The UB Mannheim installer can add additional languages during setup. The files must be named:

```text
eng.traineddata
msa.traineddata
```

They belong in the `tessdata` folder next to `tesseract.exe`, normally:

```text
C:\Program Files\Tesseract-OCR\tessdata
```

Official language files are published with the Tesseract project at [https://github.com/tesseract-ocr/tessdata](https://github.com/tesseract-ocr/tessdata). Copy only those two files into `tessdata`. Do not use a random download site.

Check what is installed:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --list-langs
```

The list must include `eng` and `msa`.

## 3. Tell BallotVision where Tesseract is

If `tesseract.exe` is on your PATH, BallotVision finds it. Otherwise set the full path before starting the app:

```powershell
$env:BALLOTVISION_TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

To keep that for new PowerShell windows, set it as a user environment variable with the same name.

## 4. Python package

From the project folder, with the virtual environment active:

```powershell
pip install -r requirements.txt
```

That installs `pytesseract`. It does not install `tesseract.exe`, `eng.traineddata`, or `msa.traineddata`.
