"""Shared names, colours, and page titles used across BallotVision."""

APP_NAME = "BallotVision"
APP_VERSION = "1.0"
APP_BRAND_TAG = "SPR Ballot Prototype"
APP_SUBTITLE = "AI-Powered Automated Recognition and Vote Counting System"
APP_USER_MODEL_ID = "BallotVision.Desktop.SPRBallotPrototype"
USER_ROLE = "Election Officer"
USER_NAME = "Sahira"
USER_INITIALS = "SA"
DEMO_ELECTION_NAME = "BallotVision Demo Election"
DEMO_BATCH_ID = "BATCH-001"
DEMO_CONTACT_EMAIL = "support@ballotvision.demo"
DEMO_CONTACT_NOTE = "Demonstration contact only — not an official SPR channel."

WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900
MIN_WIDTH = 1180
MIN_HEIGHT = 760

CANDIDATES = (
    "Amalia Suria",
    "Rizal Purnama",
    "Nora Bentara",
    "Faizal Ombak",
)

PAGES = (
    {
        "id": "dashboard",
        "nav": "Dashboard",
        "title": "Dashboard",
        "subtitle": "Check this constituency, then review flagged ballots or import the next image.",
    },
    {
        "id": "scan",
        "nav": "Scan Ballots",
        "title": "Scan Ballots",
        "subtitle": "Import a ballot image for this constituency. Camera capture is not connected yet.",
    },
    {
        "id": "review",
        "nav": "Review Queue",
        "title": "Review Queue",
        "subtitle": "Open a flagged ballot, choose a decision, and submit. Then the next pending ballot opens.",
    },
    {
        "id": "results",
        "nav": "Vote Results",
        "title": "Vote Results",
        "subtitle": "Unofficial demonstration totals for the selected Negeri and DUN.",
    },
    {
        "id": "audit",
        "nav": "Audit Trail",
        "title": "Audit Trail",
        "subtitle": "See what happened in this session, and when. Demonstration log — not official SPR records.",
    },
    {
        "id": "settings",
        "nav": "Settings",
        "title": "Settings",
        "subtitle": "Preferences for this prototype on this computer.",
    },
)

DEFAULT_SETTINGS = {
    "app_name": APP_NAME,
    "theme_name": "Dark Navy",
    "time_format": "24-hour",
    "demo_processing_mode": True,
    "confidence_threshold": 85,
    "require_reviewer_confirmation": True,
    "default_review_filter": "Pending Review",
    "export_format": "CSV",
    "demo_negeri": "Johor",
    "demo_dun_code": "N.01",
    "demo_dun_name": "Buloh Kasap",
}
