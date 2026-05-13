"""
Premier Tracker – PyQt6 GUI
Run from the project root:  python -m ui.app
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QScrollArea, QFrame, QGridLayout,
    QSizePolicy, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QPixmap, QPainter, QBrush, QPen

import db

# ── Palette ───────────────────────────────────────────────────────────────────
BG_DARK    = "#0f1923"
BG_PANEL   = "#1a2535"
BG_CARD    = "#1e2d3d"
BG_CARD2   = "#243447"
ACCENT     = "#ff4655"
ACCENT2    = "#ff6b77"
TEXT_WHITE = "#e8eaf0"
TEXT_DIM   = "#7a8a9a"
TEXT_FAINT = "#3d5166"
WIN_GREEN  = "#4caf7d"
LOSS_RED   = "#ff4655"
BORDER     = "#2a3f55"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_WHITE};
    font-family: Rajdhani;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {BG_DARK};
}}
QTabBar::tab {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    padding: 10px 28px;
    border: none;
    font-family: Rajdhani;
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 1px;
}}
QTabBar::tab:selected {{
    background: {BG_DARK};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT_WHITE};
    background: {BG_CARD};
}}
QComboBox {{
    background: {BG_PANEL};
    color: {TEXT_WHITE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 12px;
    font-family: Rajdhani;
    font-size: 12px;
    min-width: 160px;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {BG_PANEL};
    color: {TEXT_WHITE};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {BG_PANEL};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {TEXT_FAINT};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QTableWidget {{
    background: {BG_CARD};
    color: {TEXT_WHITE};
    border: none;
    gridline-color: {BORDER};
    font-family: Rajdhani;
    font-size: 12px;
}}
QTableWidget::item {{
    padding: 5px 8px;
    border: none;
}}
QTableWidget::item:selected {{
    background: {BG_CARD2};
    color: {TEXT_WHITE};
}}
QHeaderView::section {{
    background: {BG_DARK};
    color: {TEXT_FAINT};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px 8px;
    font-family: Rajdhani;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
}}
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_font(family: str, size: int, weight=QFont.Weight.Normal) -> QFont:
    f = QFont(family, size)
    f.setWeight(weight)
    return f


def lbl(text: str, size=12, weight=QFont.Weight.Normal,
        color=TEXT_WHITE, align=Qt.AlignmentFlag.AlignLeft) -> QLabel:
    w = QLabel(text)
    w.setFont(make_font("Rajdhani", size, weight))
    w.setStyleSheet(f"color: {color}; background: transparent;")
    w.setAlignment(align)
    return w


def divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {BORDER}; background: {BORDER}; max-height: 1px;")
    return line


def agent_icon(agent_name: str, size: int = 38) -> QLabel:
    agent_name = agent_name.replace("/", "")
    img_path = Path(__file__).parent.parent / "images" / f"{agent_name}.webp"

    w = QLabel()
    w.setFixedSize(size, size)
    w.setStyleSheet("background: transparent;")

    if img_path.exists():
        pix = QPixmap(str(img_path)).scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        w.setPixmap(pix)
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
    else:
        COLORS = {
            "Jett": "#89CFF0", "Reyna": "#9B59B6", "Phoenix": "#E74C3C",
            "Neon": "#3498DB", "Yoru": "#1A1AFF", "Iso": "#2ECC71",
            "Sage": "#1ABC9C", "Skye": "#27AE60", "Breach": "#F39C12",
            "Sova": "#2980B9", "KAYO": "#95A5A6", "Fade": "#8E44AD",
            "Gekko": "#2ECC71", "Harbor": "#16A085", "Deadlock": "#7F8C8D",
            "Brimstone": "#E67E22", "Viper": "#27AE60", "Astra": "#9B59B6",
            "Omen": "#6C3483", "Clove": "#D35400", "Cypher": "#BDC3C7",
            "Killjoy": "#F1C40F", "Chamber": "#B7950B", "Vyse": "#884EA0",
        }
        color = COLORS.get(agent_name, ACCENT)
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(color)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, size - 4, size - 4)
        p.setFont(make_font("Rajdhani", max(8, size // 3), QFont.Weight.Bold))
        p.setPen(QPen(QColor(TEXT_WHITE)))
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, agent_name[:2].upper())
        p.end()
        w = QLabel()
        w.setPixmap(pix)
        w.setFixedSize(size, size)
        w.setStyleSheet("background: transparent;")

    return w


def win_badge(result: str) -> QLabel:
    w = QLabel(result)
    w.setFont(make_font("Rajdhani", 12, QFont.Weight.Bold))
    w.setFixedSize(34, 34)
    w.setAlignment(Qt.AlignmentFlag.AlignCenter)
    color = WIN_GREEN if result == "W" else LOSS_RED
    w.setStyleSheet(f"color: white; background: {color}; border-radius: 4px;")
    return w


def season_combo(include_all: bool = True) -> QComboBox:
    db.init_db()
    combo = QComboBox()
    if include_all:
        combo.addItem("All Seasons", None)
    seasons = db.get_known_seasons()
    ignored = db.get_ignored_seasons()
    for s in seasons:
        if s not in ignored:
            short = s.split("-")[0] if "-" in s else s
            display = f"Current  ({short})" if s == seasons[0] else short
            combo.addItem(display, s)
    return combo


def _table(cols: list[tuple[str, int]], stretch_col: int = 0) -> QTableWidget:
    t = QTableWidget()
    t.setColumnCount(len(cols))
    t.setHorizontalHeaderLabels([c[0] for c in cols])
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.setShowGrid(False)
    t.horizontalHeader().setHighlightSections(False)
    t.setAlternatingRowColors(False)
    t.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    t.setStyleSheet(f"""
        QTableWidget {{ background: {BG_CARD}; alternate-background-color: {BG_CARD2}; }}
    """)

    for i, (_, width) in enumerate(cols):
        if i == stretch_col:
            t.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        else:
            t.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            t.setColumnWidth(i, width)

    t.verticalHeader().setDefaultSectionSize(34)
    return t


def _cell(text: str, color: str = TEXT_WHITE, align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
          bold: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setForeground(QColor(color))
    item.setTextAlignment(align)
    if bold:
        item.setFont(make_font("Rajdhani", 12, QFont.Weight.Bold))
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return item


CENTER = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter


# ── Tab: Match History ────────────────────────────────────────────────────────

class MatchCard(QFrame):
    def __init__(self, match: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 6px;
            }}
        """)
        self.setFixedHeight(280)
        self._build(match)

    def _build(self, m: dict):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(f"background: {BG_CARD2}; border-radius: 6px 6px 0 0;")
        header.setFixedHeight(50)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(10)
        hl.addWidget(win_badge(m["result"]))
        hl.addWidget(lbl(m["map_name"], size=14, weight=QFont.Weight.Bold))
        score_lbl = lbl(m["score"], size=13, color=ACCENT)
        hl.addWidget(score_lbl)
        hl.addStretch()
        hl.addWidget(lbl(f"{m['rounds']} rds", size=10, color=TEXT_DIM))
        hl.addSpacing(16)
        hl.addWidget(lbl(m["date"], size=10, color=TEXT_DIM))
        root.addWidget(header)

        cols = [("PLAYER", 0), ("AGENT", 100), ("KDA", 90), ("K/D", 64), ("HS%", 64), ("SCORE", 70)]
        t = _table(cols, stretch_col=0)
        t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        players = sorted(m["players"], key=lambda x: x["score"], reverse=True)
        t.setRowCount(len(players))
        for row, p in enumerate(players):
            kd_color = WIN_GREEN if p["kd"] >= 1.0 else LOSS_RED
            t.setItem(row, 0, _cell(p["name"]))
            t.setItem(row, 1, _cell(p["agent"], color=TEXT_DIM))
            t.setItem(row, 2, _cell(p["kda"], align=CENTER))
            t.setItem(row, 3, _cell(f"{p['kd']:.2f}", color=kd_color, align=CENTER))
            t.setItem(row, 4, _cell(f"{p['hs_percent']:.1f}%", color=TEXT_DIM, align=CENTER))
            t.setItem(row, 5, _cell(str(p["score"]), color=ACCENT, align=CENTER))

        t.setFixedHeight(t.verticalHeader().defaultSectionSize() * len(players)
                         + t.horizontalHeader().height() + 10)
        root.addWidget(t)


class HistoryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        bar = QHBoxLayout()
        bar.addWidget(lbl("MATCH HISTORY", size=18, weight=QFont.Weight.Bold, color=ACCENT))
        bar.addStretch()
        bar.addWidget(lbl("Season:", size=11, color=TEXT_DIM))
        self.season_cb = season_combo(include_all=True)
        self.season_cb.currentIndexChanged.connect(self.refresh)
        bar.addWidget(self.season_cb)
        root.addLayout(bar)
        root.addWidget(divider())

        # Plain widget – no scroll container at all
        self.inner = QWidget()
        self.vbox  = QVBoxLayout(self.inner)
        self.vbox.setSpacing(14)
        self.vbox.setContentsMargins(0, 6, 6, 6)
        self.vbox.addStretch()
        root.addWidget(self.inner)

        self.refresh()

    def refresh(self):
        season  = self.season_cb.currentData()
        matches = db.get_match_history(season_id=season, limit=30)

        while self.vbox.count() > 1:
            item = self.vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not matches:
            self.vbox.insertWidget(0, lbl("No matches found.", size=13, color=TEXT_DIM))
            return

        for m in matches:
            self.vbox.insertWidget(self.vbox.count() - 1, MatchCard(m))


# ── Tab: Player Overview ──────────────────────────────────────────────────────

class PlayersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        bar = QHBoxLayout()
        bar.addWidget(lbl("PLAYER OVERVIEW", size=18, weight=QFont.Weight.Bold, color=ACCENT))
        bar.addStretch()
        bar.addWidget(lbl("Season:", size=11, color=TEXT_DIM))
        self.season_cb = season_combo(include_all=False)
        self.season_cb.currentIndexChanged.connect(self.refresh)
        bar.addWidget(self.season_cb)
        root.addLayout(bar)
        root.addWidget(divider())

        cols = [("", 44), ("PLAYER", 0), ("GP", 52), ("W%", 64),
                ("K/D", 64), ("HS%", 64), ("AVG K", 64), ("TOP AGENT", 120)]
        self.table = _table(cols, stretch_col=1)
        root.addWidget(self.table)

        self.refresh()

    def refresh(self):
        season  = self.season_cb.currentData()
        players = db.get_tracked_players()
        self.table.setRowCount(0)

        for p in players:
            row = self.table.rowCount()
            self.table.insertRow(row)

            agent_rows = db.get_agent_stats(p["puuid"], season_id=season)
            top_agent  = agent_rows[0]["agent"] if agent_rows else None

            icon_lbl = agent_icon(top_agent or "??", 30)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row, 0, icon_lbl)

            name = f"{p['name']}#{p['tag']}"
            self.table.setItem(row, 1, _cell(name, bold=True))

            stats = db.get_player_stats_aggregated(p["puuid"], season_id=season)
            if stats:
                kd_color = WIN_GREEN if stats["kd"] >= 1.0 else LOSS_RED
                self.table.setItem(row, 2, _cell(str(stats["matches_played"]), align=CENTER))
                self.table.setItem(row, 3, _cell(f"{stats['win_rate']:.0f}%", align=CENTER))
                self.table.setItem(row, 4, _cell(f"{stats['kd']:.2f}", color=kd_color, align=CENTER))
                self.table.setItem(row, 5, _cell(f"{stats['hs_percent']:.1f}%", align=CENTER))
                self.table.setItem(row, 6, _cell(f"{stats['avg_kills']:.1f}", align=CENTER))
            else:
                for col in range(2, 7):
                    self.table.setItem(row, col, _cell("–", color=TEXT_FAINT, align=CENTER))

            agent_txt = top_agent if top_agent else "–"
            self.table.setItem(row, 7, _cell(agent_txt, color=TEXT_DIM, align=CENTER))

        self.table.verticalHeader().setDefaultSectionSize(42)


# ── Tab: Map Stats ────────────────────────────────────────────────────────────

class MapsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        bar = QHBoxLayout()
        bar.addWidget(lbl("MAP STATS", size=18, weight=QFont.Weight.Bold, color=ACCENT))
        bar.addStretch()
        bar.addWidget(lbl("Season:", size=11, color=TEXT_DIM))
        self.season_cb = season_combo(include_all=True)
        self.season_cb.currentIndexChanged.connect(self.refresh)
        bar.addWidget(self.season_cb)
        root.addLayout(bar)
        root.addWidget(divider())

        cols = [("MAP", 0), ("PLAYED", 80), ("WINS", 80), ("LOSSES", 80), ("WIN %", 90), ("", 180)]
        self.table = _table(cols, stretch_col=0)
        root.addWidget(self.table)

        self.refresh()

    def _make_bar_widget(self, pct: float) -> QWidget:
        outer = QWidget()
        outer.setFixedHeight(8)
        outer.setStyleSheet(f"background: {BG_DARK}; border-radius: 4px;")
        inner = QWidget(outer)
        inner.setFixedHeight(8)
        fill  = max(4, int(pct / 100 * 160))
        inner.setFixedWidth(fill)
        color = WIN_GREEN if pct >= 50 else LOSS_RED
        inner.setStyleSheet(f"background: {color}; border-radius: 4px;")
        container = QWidget()
        cl = QHBoxLayout(container)
        cl.setContentsMargins(8, 0, 8, 0)
        cl.addWidget(outer)
        cl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        container.setStyleSheet("background: transparent;")
        return container

    def refresh(self):
        season = self.season_cb.currentData()
        rows   = db.get_map_stats(season_id=season)
        self.table.setRowCount(0)

        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            pct       = r["win_rate"]
            pct_color = WIN_GREEN if pct >= 50 else LOSS_RED

            self.table.setItem(row, 0, _cell(r["map_name"], bold=True))
            self.table.setItem(row, 1, _cell(str(r["total"]),   align=CENTER))
            self.table.setItem(row, 2, _cell(str(r["wins"]),    color=WIN_GREEN, align=CENTER))
            self.table.setItem(row, 3, _cell(str(r["losses"]),  color=LOSS_RED,  align=CENTER))
            self.table.setItem(row, 4, _cell(f"{pct:.1f}%", color=pct_color, align=CENTER, bold=True))
            self.table.setCellWidget(row, 5, self._make_bar_widget(pct))

        self.table.verticalHeader().setDefaultSectionSize(40)


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        db.init_db()
        self.setWindowTitle("Premier Tracker")
        self.resize(1100, 760)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(STYLESHEET)
        self._build()

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        topbar = QWidget()
        topbar.setFixedHeight(50)
        topbar.setStyleSheet(f"background: {BG_PANEL}; border-bottom: 1px solid {BORDER};")
        tl = QHBoxLayout(topbar)
        tl.setContentsMargins(20, 0, 20, 0)
        tl.addWidget(lbl("PREMIER", size=15, weight=QFont.Weight.Bold, color=ACCENT))
        tl.addWidget(lbl(" TRACKER", size=15, weight=QFont.Weight.Bold, color=TEXT_WHITE))
        tl.addStretch()

        self.status_lbl = lbl("", size=10, color=TEXT_DIM)
        tl.addWidget(self.status_lbl)
        tl.addSpacing(12)

        sync_btn = QPushButton("↻  Sync")
        sync_btn.setFixedSize(88, 30)
        sync_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: white;
                border: none;
                border-radius: 4px;
                font-family: Rajdhani;
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QPushButton:hover   {{ background: {ACCENT2}; }}
            QPushButton:pressed {{ background: #cc2233; }}
        """)
        sync_btn.clicked.connect(self._on_sync)
        tl.addWidget(sync_btn)
        root.addWidget(topbar)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self.history_tab = HistoryTab()
        self.players_tab = PlayersTab()
        self.maps_tab    = MapsTab()
        tabs.addTab(self.history_tab, "History")
        tabs.addTab(self.players_tab, "Players")
        tabs.addTab(self.maps_tab,    "Maps")
        root.addWidget(tabs)

    def _on_sync(self):
        self.status_lbl.setText("Syncing…")
        QTimer.singleShot(100, self._do_sync)

    def _do_sync(self):
        from api import sync_all_tracked
        players = db.get_tracked_players()
        if not players:
            self.status_lbl.setText("No tracked players.")
            return
        summary = sync_all_tracked(players)
        total   = sum(v["saved"] for v in summary.values())
        self.status_lbl.setText(f"{total} new match(es) saved.")
        self.history_tab.refresh()
        self.players_tab.refresh()
        self.maps_tab.refresh()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.showMaximized()
    win.show()
    exit_code = app.exec()
    db.close_pool()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()