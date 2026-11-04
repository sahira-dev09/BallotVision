"""Main application chrome: sidebar, header, and stacked pages."""

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from app.core.constants import (
    APP_BRAND_TAG,
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    DEMO_CONTACT_EMAIL,
    DEMO_CONTACT_NOTE,
    MIN_HEIGHT,
    MIN_WIDTH,
    PAGES,
    USER_NAME,
    USER_ROLE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from app.pages.audit_page import AuditPage
from app.pages.dashboard_page import DashboardPage
from app.pages.results_page import ResultsPage
from app.pages.review_page import ReviewPage
from app.pages.scan_page import ScanPage
from app.pages.settings_page import SettingsPage
from app.widgets.avatar import AvatarLabel
from app.widgets.icons import PaintedIcon
from app.widgets.logo import LogoMark, logo_icon
from app.widgets.sidebar import Sidebar


class ProfileButton(QFrame):
    def __init__(self, menu: QMenu, parent=None) -> None:
        super().__init__(parent)
        self._menu = menu
        self.setObjectName("profileButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setMinimumWidth(210)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
        super().mousePressEvent(event)


class InfoDialog(QDialog):
    def __init__(self, title: str, body: str, parent=None, show_photo: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        heading_row = QHBoxLayout()
        if show_photo:
            heading_row.addWidget(AvatarLabel(72), 0, Qt.AlignmentFlag.AlignTop)
        heading_col = QVBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        heading_col.addWidget(heading)
        heading_row.addLayout(heading_col, 1)
        layout.addLayout(heading_row)
        text = QLabel(body)
        text.setWordWrap(True)
        text.setObjectName("mutedLabel")
        close = QPushButton("Close")
        close.setObjectName("primaryButton")
        close.clicked.connect(self.accept)
        layout.addWidget(text)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)


class MainWindow(QMainWindow):
    def __init__(self, store) -> None:
        super().__init__()
        self.store = store
        self.setWindowTitle(f"{APP_NAME}  ·  {APP_BRAND_TAG}")
        self.setWindowIcon(logo_icon(256))
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.page_chosen.connect(self.show_page)
        root_layout.addWidget(self.sidebar)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._build_header())

        self.toast = QLabel("")
        self.toast.setObjectName("toast")
        self.toast.setVisible(False)
        self.toast.setWordWrap(True)
        toast_wrap = QWidget()
        toast_layout = QVBoxLayout(toast_wrap)
        toast_layout.setContentsMargins(24, 0, 24, 0)
        toast_layout.addWidget(self.toast)
        right_layout.addWidget(toast_wrap)

        self.stack = QStackedWidget()
        self.pages = {
            "dashboard": DashboardPage(store),
            "scan": ScanPage(store),
            "review": ReviewPage(store),
            "results": ResultsPage(store),
            "audit": AuditPage(store),
            "settings": SettingsPage(store),
        }
        self.page_index = {}
        for index, page_id in enumerate(self.pages):
            self.stack.addWidget(self.pages[page_id])
            self.page_index[page_id] = index
        right_layout.addWidget(self.stack, 1)

        root_layout.addWidget(right, 1)
        self.setCentralWidget(root)

        for page in self.pages.values():
            if hasattr(page, "navigate"):
                page.navigate.connect(self.show_page)

        self.store.message.connect(self.show_message)
        self.store.changed.connect(self._refresh_nav)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self.toast.setVisible(False))

        self._refresh_nav()
        self.show_page("dashboard")

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(76)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 10, 20, 10)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(LogoMark(28), 0, Qt.AlignmentFlag.AlignVCenter)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        titles.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel()
        self.title_label.setObjectName("headerTitle")
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("headerSubtitle")
        self.subtitle_label.setWordWrap(False)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        layout.addLayout(titles, 1)

        indicators = QWidget()
        indicators.setObjectName("headerIndicators")
        indicator_row = QHBoxLayout(indicators)
        indicator_row.setContentsMargins(0, 0, 0, 0)
        indicator_row.setSpacing(8)
        indicator_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.demo_chip = QLabel("DEMO MODE")
        self.demo_chip.setObjectName("demoChip")
        self.demo_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.demo_chip.setMinimumHeight(36)
        indicator_row.addWidget(self.demo_chip, 0, Qt.AlignmentFlag.AlignVCenter)

        self.info_button = QToolButton()
        self.info_button.setObjectName("infoButton")
        self.info_button.setFixedSize(36, 36)
        self.info_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.info_button.setIcon(self._menu_icon("info"))
        self.info_button.setIconSize(QSize(16, 16))
        self.info_button.setToolTip(
            "BallotVision is an SPR ballot prototype.\n"
            "Recognition, counts, and results are simulated and unofficial."
        )
        self.info_button.clicked.connect(self._show_demo_information)
        indicator_row.addWidget(self.info_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(indicators, 0, Qt.AlignmentFlag.AlignVCenter)

        self._profile_menu = self._build_profile_menu()
        self.profile_button = ProfileButton(self._profile_menu)

        avatar = AvatarLabel(36)
        names = QVBoxLayout()
        names.setSpacing(0)
        officer = QLabel(USER_NAME)
        officer.setObjectName("profileName")
        role = QLabel(USER_ROLE)
        role.setObjectName("mutedLabel")
        names.addWidget(officer)
        names.addWidget(role)
        chevron = QLabel("▾")
        chevron.setObjectName("mutedLabel")
        button_layout = QHBoxLayout(self.profile_button)
        button_layout.setContentsMargins(8, 4, 10, 4)
        button_layout.setSpacing(8)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        button_layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignVCenter)
        button_layout.addLayout(names, 1)
        button_layout.addWidget(chevron, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.profile_button, 0, Qt.AlignmentFlag.AlignVCenter)
        return header

    def _menu_icon(self, kind: str) -> QIcon:
        widget = PaintedIcon(kind, "#22D3EE", 16)
        widget.resize(16, 16)
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        widget.render(pixmap)
        return QIcon(pixmap)

    def _build_profile_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setObjectName("profileMenu")
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(8)
        header_layout.addWidget(AvatarLabel(36))
        names = QVBoxLayout()
        names.setSpacing(0)
        title = QLabel(USER_NAME)
        title.setObjectName("profileName")
        role = QLabel(USER_ROLE)
        role.setObjectName("mutedLabel")
        names.addWidget(title)
        names.addWidget(role)
        header_layout.addLayout(names)
        header_action = QWidgetAction(menu)
        header_action.setDefaultWidget(header)
        menu.addAction(header_action)
        menu.addSeparator()
        items = (
            ("Officer Profile", "user", self._show_officer_profile),
            ("Contact and Support", "mail", self._show_contact),
            ("About BallotVision", "about", self._show_about),
            ("Demo Information", "demo", self._show_demo_information),
            ("Application Settings", "gear", lambda: self.show_page("settings")),
        )
        for label, kind, handler in items:
            action = QAction(self._menu_icon(kind), label, self)
            action.triggered.connect(handler)
            menu.addAction(action)
        return menu

    def _refresh_nav(self) -> None:
        pending = int(self.store.data.get("stats", {}).get("pending_reviews", 0))
        self.sidebar.set_review_count(pending)

    def show_page(self, page_id: str) -> None:
        meta = next(page for page in PAGES if page["id"] == page_id)
        self.stack.setCurrentIndex(self.page_index[page_id])
        self.sidebar.set_active(page_id)
        self.title_label.setText(meta["title"])
        self.subtitle_label.setText(meta["subtitle"])
        page = self.pages[page_id]
        if hasattr(page, "on_page_shown"):
            page.on_page_shown()

    def show_message(self, text: str, level: str) -> None:
        colors = {
            "success": ("#34D399", "rgba(52, 211, 153, 0.12)"),
            "warning": ("#FBBF24", "rgba(251, 191, 36, 0.12)"),
            "error": ("#FB7185", "rgba(251, 113, 133, 0.12)"),
            "info": ("#22D3EE", "rgba(34, 211, 238, 0.12)"),
        }
        color, background = colors.get(level, colors["info"])
        self.toast.setText(text)
        self.toast.setStyleSheet(
            f"color: {color}; background: {background}; border: 1px solid {color};"
        )
        self.toast.setVisible(True)
        self._toast_timer.start(4200)

    def _show_officer_profile(self) -> None:
        InfoDialog(
            "Officer Profile",
            f"{USER_NAME}\n{USER_ROLE}\n\n"
            "This is a demonstration officer identity for the BallotVision prototype. "
            "It is not a live SPR staff account and does not provide authentication.",
            self,
            show_photo=True,
        ).exec()

    def _show_contact(self) -> None:
        InfoDialog(
            "Contact and Support",
            f"Prototype support mailbox: {DEMO_CONTACT_EMAIL}\n\n{DEMO_CONTACT_NOTE}\n\n"
            "Use this prototype to explore scan, review, results, and audit workflows. "
            "It is not connected to any official election helpdesk.",
            self,
        ).exec()

    def _show_about(self) -> None:
        InfoDialog(
            "About BallotVision",
            f"{APP_NAME}\n{APP_BRAND_TAG}  ·  Version {APP_VERSION}\n{APP_SUBTITLE}\n\n"
            "Desktop prototype built with Python and PySide6. "
            "The interface demonstrates election-officer workflows. "
            "It does not connect to live SPR systems and does not produce official results.",
            self,
        ).exec()

    def _show_demo_information(self) -> None:
        election = self.store.data.get("election", {})
        InfoDialog(
            "Demo Information",
            "BallotVision is running in demonstration mode.\n\n"
            f"Election: {election.get('name', 'BallotVision Demo Election')}\n"
            f"Negeri: {election.get('negeri', 'Johor')}\n"
            f"DUN: {election.get('dun', 'fictional demonstration constituency')}\n"
            f"Batch: {election.get('batch', 'BATCH-001')}\n\n"
            "Ballot recognition is simulated. Counts, flags, and vote totals are fictional "
            "and must not be treated as official election figures.",
            self,
        ).exec()

    def closeEvent(self, event) -> None:  # noqa: N802
        answer = QMessageBox.question(
            self,
            "Exit BallotVision",
            "Close the BallotVision prototype?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()
