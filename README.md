# BallotVision

**AI-Powered Automated Recognition and Vote Counting System for SPR Election Ballots**

BallotVision is a Final Year Project. It will be a native Windows desktop application that helps recognise and count votes on SPR (Suruhanjaya Pilihan Raya) election ballots using computer vision.

This version is a **working Windows UI prototype**. Sample numbers, ballot marks, and review decisions are fictional. The AI recognition model is not built yet.

## What the app includes now

1. **Dashboard** — overview of scans, counts, and system status
2. **Scan Ballots** — capture or load ballot images
3. **Review Flagged Ballots** — check ballots the system is unsure about
4. **Vote Results** — show vote totals
5. **Audit Trail** — keep a record of what the system did
6. **Settings** — camera, folders, and other options

## Tech stack

| Tool | Why we use it |
|------|----------------|
| **Python** | Main programming language |
| **PySide6** | Builds the Windows desktop windows and buttons |
| **Qt Style Sheets (QSS)** | Styles the app (colours, rounded cards, fonts) — similar to CSS for websites |

The planned look is a **dark navy** background with **cyan** accents, modern text, rounded cards, and a clean professional layout.

## Project folder structure

```
BallotVision/
├── main.py                 # App starting point. Run this file to launch BallotVision.
├── requirements.txt        # List of Python packages the project needs
├── README.md               # This guide
├── .gitignore              # Tells Git which files not to save (venv, cache, etc.)
│
├── app/                    # All application code lives here
│   ├── __init__.py         # Marks this folder as a Python package
│   ├── main_window.py      # The main window with the 6 page areas (to be built)
│   ├── pages/              # One file per screen
│   │   ├── dashboard_page.py
│   │   ├── scan_page.py
│   │   ├── review_page.py
│   │   ├── results_page.py
│   │   ├── audit_page.py
│   │   └── settings_page.py
│   ├── styles/
│   │   └── theme.qss       # Colours, fonts, cards, and borders (QSS)
│   ├── assets/             # Images, icons, and fonts you add later
│   │   ├── icons/
│   │   ├── images/
│   │   └── fonts/
│   ├── core/               # Shared helpers (config, constants)
│   └── services/           # Later: scanning, counting, audit logging
│
├── data/                   # Later: local database and logs
└── resources/              # Later: sample ballot images for testing
    └── sample_ballots/
```

Empty folders include a `.gitkeep` file. That file only exists so Git can save an otherwise empty folder. You can ignore it.

## How to run on Windows

You need **Python 3.10 or newer**. Check in PowerShell or Command Prompt:

```powershell
python --version
```

If that fails, try:

```powershell
py --version
```

### Step 1 — Open the project folder

```powershell
cd C:\Users\ASUS\Documents\BallotVision
```

### Step 2 — Create a virtual environment

A virtual environment is a private Python folder for this project only. It keeps BallotVision packages separate from other Python projects.

```powershell
python -m venv .venv
```

### Step 3 — Turn the virtual environment on

```powershell
.venv\Scripts\activate
```

You should see `(.venv)` at the start of the line.

If Windows blocks the script, run this once in PowerShell, then try activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Step 4 — Install the listed packages

```powershell
pip install -r requirements.txt
```

### Step 5 — Start the app

```powershell
python main.py
```

The BallotVision window should open at about 1440 × 900. Use the left sidebar to move between the six pages.

### Step 6 — Stop the app

Close the window, or press `Ctrl+C` in the terminal.

To leave the virtual environment later:

```powershell
deactivate
```

## Current status

- [x] Project folders and starter files
- [x] Full six-page user interface prototype
- [x] Simulated ballot import and processing
- [ ] AI recognition model
- [x] Simulated vote results and CSV export
- [x] Prototype audit trail

## Notes for development

- Work inside `.venv` whenever you install packages or run `main.py`.
- Do not put camera, OpenCV, or AI packages in `requirements.txt` until those features are being built.
- Keep real ballot images in `resources/sample_ballots/` for testing. Do not commit private voter data if you use Git.
