import os
import sys
import subprocess
import threading
import datetime
import time
import zipfile

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QInputDialog,
    QWidget, QFileDialog, QProgressBar, QFrame, QStackedWidget, QScrollArea,
    QApplication, QTextEdit, QGridLayout, QShortcut, QRadioButton, QButtonGroup, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QIcon, QKeySequence

from config import (
    NOTES_DIR, NOTES_PATH, ARCHIVE_PATH, BG_MAIN, BG_CARD, FG_GREEN, FG_TEXT, FG_MUTED,
    BTN_BLUE, BTN_AMBER, BTN_RED, BTN_PURPLE, BTN_TEAL, BTN_GRAY,
    get_category_media_dir, update_notes_dir
)
from utils import center_window, update_frontmatter_keys, parse_note_file
from ui_common import apply_rtl_to_widget
from git_sync import (
    sync_notes_cli, sync_notes_gui, setup_git_repo_gui,
    get_git_remote_url, get_git_branch_name, get_git_last_commit_info, unlink_git_remote,
    clean_stale_git_locks, sanitize_git_url, detect_remote_default_branch, check_large_files, diagnose_git_error,
    get_git_unsynced_rel_paths, is_category_synced, is_file_synced
)
from note_manager import (
    get_categories_data,
    get_pinned_categories,
    save_pinned_categories,
    archive_category,
    rename_category,
    get_all_notes,
    get_all_tasks
)
from ui_create_note import show_create_note_window
from ui_view_note import show_note_view_window
from i18n import tr, get_lang, set_lang

# Palette Colors matching mockup
CLR_MAIN_BG = "#0D0F17"
CLR_SIDEBAR_BG = "#131622"
CLR_CARD_BG = "#171A29"
CLR_HEADER_BG = "#161926"
CLR_ROW_BG = "#181B2B"
CLR_ROW_HOVER = "#202438"
CLR_BORDER = "#232738"
CLR_PURPLE = "#7C3AED"
CLR_BLUE = "#2563EB"
CLR_GREEN = "#10B981"
CLR_YELLOW = "#F59E0B"
CLR_RED = "#EF4444"
CLR_TEXT_MUTED = "#64748B"

FOLDER_COLORS = ["#3B82F6", "#8B5CF6", "#F97316", "#14B8A6", "#EAB308", "#EC4899", "#6366F1"]

def get_real_notes_storage_info():
    total_bytes = 0
    if os.path.exists(NOTES_PATH):
        for root, dirs, files in os.walk(NOTES_PATH):
            for f in files:
                fp = os.path.join(root, f)
                if not os.path.islink(fp):
                    try:
                        total_bytes += os.path.getsize(fp)
                    except Exception:
                        pass
    
    if total_bytes < 1024 * 1024:
        size_str = f"{total_bytes / 1024:.1f} KB"
    elif total_bytes < 1024 * 1024 * 1024:
        size_str = f"{total_bytes / (1024*1024):.1f} MB"
    else:
        size_str = f"{total_bytes / (1024*1024*1024):.2f} GB"
        
    try:
        st = os.statvfs(NOTES_PATH)
        disk_total = st.f_blocks * st.f_frsize
        pct = max(1, min(100, int((total_bytes / disk_total) * 100))) if disk_total else 5
    except Exception:
        pct = 5
        
    return size_str, pct

class CategoriesDialog(QDialog):
    git_log_signal = pyqtSignal(str)
    git_finished_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.result_action = ""
        self.result_val = ""
        
        self.git_log_signal.connect(self.append_git_log)
        self.git_finished_signal.connect(self.on_git_setup_finished)

        if get_lang() == 'ar':
            self.setLayoutDirection(Qt.RightToLeft)
        else:
            self.setLayoutDirection(Qt.LeftToRight)

        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )

        self.setWindowTitle("DevNotes - إدارة الفئات والملاحظات")
        self.resize(1240, 740)
        self.setMinimumSize(1100, 660)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {CLR_MAIN_BG};
                color: #FFFFFF;
                font-family: 'Segoe UI', 'DejaVu Sans', sans-serif;
            }}
            QWidget {{
                color: #FFFFFF;
                font-family: 'Segoe UI', 'DejaVu Sans', sans-serif;
            }}
            QTreeWidget {{
                background-color: {CLR_CARD_BG};
                border: 1px solid {CLR_BORDER};
                border-radius: 10px;
                outline: none;
            }}
            QTreeWidget::item {{
                height: 54px;
                border-bottom: 1px solid #1F2336;
            }}
            QTreeWidget::item:hover {{
                background-color: {CLR_ROW_HOVER};
            }}
            QTreeWidget::item:selected {{
                background-color: #272C44;
            }}
            QHeaderView::section {{
                background-color: {CLR_HEADER_BG};
                color: #94A3B8;
                padding: 10px;
                border: none;
                border-bottom: 1px solid {CLR_BORDER};
                font-weight: bold;
                font-size: 12px;
            }}
            QLineEdit {{
                background-color: #161926;
                color: #FFFFFF;
                border: 1px solid {CLR_BORDER};
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {CLR_PURPLE};
            }}
            QComboBox {{
                background-color: #161926;
                color: #FFFFFF;
                border: 1px solid {CLR_BORDER};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QScrollBar:vertical {{
                border: none;
                background: #141724;
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #2D334B;
                border-radius: 4px;
            }}
        """)
        
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Build Left Sidebar
        self.sidebar = self.build_sidebar()
        self.main_layout.addWidget(self.sidebar)
        
        # Stacked Widget for in-place views
        self.stack = QStackedWidget()
        
        # View 0: Categories Page
        self.view_cats = self.build_categories_view()
        self.stack.addWidget(self.view_cats)
        
        # View 1: Kanban Board Page
        self.view_kanban = self.build_kanban_view()
        self.stack.addWidget(self.view_kanban)
        
        # View 2: Scripts Page
        self.view_scripts = self.build_scripts_view()
        self.stack.addWidget(self.view_scripts)
        
        # View 3: Reminders Page
        self.view_rems = self.build_reminders_view()
        self.stack.addWidget(self.view_rems)

        # View 4: Git Setup Page
        self.view_git = self.build_git_view()
        self.stack.addWidget(self.view_git)
        
        self.main_layout.addWidget(self.stack, 1)
        
        self.populate_tree()
        center_window(self, 1240, 740)

    def build_sidebar(self):
        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        sidebar = QWidget()
        sidebar.setFixedWidth(230)
        sidebar.setStyleSheet(f"background-color: {c['CLR_SIDEBAR_BG']}; border-right: 1px solid {c['CLR_BORDER']};")
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(14)
        
        # App Logo & Title
        logo_layout = QHBoxLayout()
        logo_icon = QLabel("📓")
        logo_icon.setStyleSheet("font-size: 22px; background: transparent;")
        
        title_box = QVBoxLayout()
        title_lbl = QLabel("DevNotes")
        title_lbl.setStyleSheet(f"color: {c['FG_TEXT']}; font-weight: bold; font-size: 16px; background: transparent;")
        sub_lbl = QLabel("ملاحظاتك، منظمة." if is_ar else "Your notes, organized.")
        sub_lbl.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 11px; background: transparent;")
        
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        logo_layout.addWidget(logo_icon)
        logo_layout.addLayout(title_box)
        logo_layout.addStretch()
        layout.addLayout(logo_layout)
        
        layout.addSpacing(10)
        
        # Main Navigation Buttons
        self.nav_btns = []
        
        def create_nav_btn(text, icon_str, page_idx):
            btn = QPushButton(f"{icon_str}  {text}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda: self.switch_view(page_idx))
            self.nav_btns.append((btn, page_idx))
            return btn

        btn_cats = create_nav_btn(tr('nav_cats'), "📁", 0)
        btn_kanban = create_nav_btn(tr('nav_kanban'), "📊", 1)
        btn_scripts = create_nav_btn(tr('nav_scripts'), "👨‍💻", 2)
        btn_rems = create_nav_btn(tr('nav_rems'), "🔔", 3)
        btn_git = create_nav_btn(tr('nav_git'), "🐙", 4)
        
        btn_sync_side = QPushButton(f"🔄  {tr('btn_sync')}")
        btn_sync_side.setCursor(Qt.PointingHandCursor)
        btn_sync_side.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {c['FG_MUTED']};
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 10px 14px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {c['CLR_ROW_HOVER']};
                color: {c['FG_TEXT']};
            }}
        """)
        btn_sync_side.clicked.connect(self.on_sync)

        layout.addWidget(btn_cats)
        layout.addWidget(btn_kanban)
        layout.addWidget(btn_scripts)
        layout.addWidget(btn_rems)
        layout.addWidget(btn_git)
        layout.addWidget(btn_sync_side)

        # Separator Line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background-color: {c['CLR_BORDER']}; border: none; max-height: 1px;")
        layout.addWidget(line)

        # Tools Header
        self.tools_hdr_lbl = QLabel(tr('tools_header'))
        self.tools_hdr_lbl.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-weight: bold; font-size: 12px; background: transparent;")
        layout.addWidget(self.tools_hdr_lbl)

        def create_tool_btn(text, icon_str, command):
            b = QPushButton(f"{icon_str}  {text}")
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c['FG_MUTED']};
                    font-size: 14px;
                    font-weight: bold;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 14px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {c['CLR_ROW_HOVER']};
                    color: {c['FG_TEXT']};
                }}
            """)
            if command: b.clicked.connect(command)
            return b

        self.btn_export_tool = create_tool_btn(tr('nav_export'), "📦", self.on_global_export)
        layout.addWidget(self.btn_export_tool)

        layout.addStretch()

        # Storage Space Widget
        storage_card = QFrame()
        storage_card.setStyleSheet(f"background-color: {c['CLR_CARD_BG']}; border: 1px solid {c['CLR_BORDER']}; border-radius: 10px; padding: 10px;")
        s_layout = QVBoxLayout(storage_card)
        s_layout.setContentsMargins(8, 8, 8, 8)
        s_layout.setSpacing(6)
        
        s_lbl = QLabel("مساحة التخزين" if is_ar else "Storage Space")
        s_lbl.setStyleSheet(f"color: {c['FG_MUTED']}; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        
        size_str, size_pct = get_real_notes_storage_info()
        
        pbar = QProgressBar()
        pbar.setValue(size_pct)
        pbar.setFixedHeight(6)
        pbar.setTextVisible(False)
        pbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {c['CLR_BORDER']};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {c['CLR_PURPLE']};
                border-radius: 3px;
            }}
        """)
        
        sub_s = QLabel(f"{size_str} المستهلكة من القرص" if is_ar else f"{size_str} used of disk")
        sub_s.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 10px; border: none; background: transparent;")
        
        s_layout.addWidget(s_lbl)
        s_layout.addWidget(pbar)
        s_layout.addWidget(sub_s)
        layout.addWidget(storage_card)
        
        self.update_nav_styles(self.stack.currentIndex() if hasattr(self, 'stack') else 0)
        return sidebar

    def switch_view(self, page_idx):
        self.stack.setCurrentIndex(page_idx)
        self.update_nav_styles(page_idx)
        if page_idx == 0:
            self.populate_tree()
        elif page_idx == 1:
            self.refresh_kanban_board()
        elif page_idx == 2:
            self.refresh_scripts_view()
        elif page_idx == 3:
            self.refresh_reminders_view()
        elif page_idx == 4:
            self.refresh_git_view()
        elif page_idx == 5:
            self.refresh_settings_view()

    def update_nav_styles(self, active_idx):
        from theme import get_theme_colors
        c = get_theme_colors()
        for btn, idx in self.nav_btns:
            if idx == active_idx:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {c['CLR_PURPLE']};
                        color: #FFFFFF;
                        font-size: 14px;
                        font-weight: bold;
                        border: none;
                        border-radius: 8px;
                        padding: 10px 14px;
                        text-align: left;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {c['FG_MUTED']};
                        font-size: 14px;
                        font-weight: bold;
                        border: none;
                        border-radius: 8px;
                        padding: 10px 14px;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        background-color: {c['CLR_ROW_HOVER']};
                        color: {c['FG_TEXT']};
                    }}
                """)

    def build_categories_view(self):
        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        area = QWidget()
        area.setStyleSheet(f"background-color: {c['CLR_MAIN_BG']};")
        
        layout = QVBoxLayout(area)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        
        # Top Header Bar
        top_bar = QHBoxLayout()
        
        title_box = QVBoxLayout()
        h_title = QLabel("📁 " + ("الفئات والملاحظات" if is_ar else "Categories & Notes"))
        h_title.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 22px; font-weight: bold;")
        h_sub = QLabel("إدارة جميع الفئات وملاحظاتك بكل سهولة" if is_ar else "Manage all your categories and notes with ease")
        h_sub.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 12px;")
        title_box.addWidget(h_title)
        title_box.addWidget(h_sub)
        
        top_bar.addLayout(title_box)
        top_bar.addStretch()
        
        btn_new_task = QPushButton(f"+ {tr('btn_new_task')}")
        btn_new_task.setCursor(Qt.PointingHandCursor)
        btn_new_task.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['CLR_PURPLE']};
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 9px 18px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #6D28D9;
            }}
        """)
        btn_new_task.clicked.connect(self.on_new_task)
        top_bar.addWidget(btn_new_task)
        
        user_chip = QLabel("👤 Bashar ▾")
        user_chip.setStyleSheet(f"color: {c['FG_MUTED']}; font-weight: bold; font-size: 13px; padding: 6px 12px; background: {c['CLR_CARD_BG']}; border: 1px solid {c['CLR_BORDER']}; border-radius: 20px;")
        top_bar.addWidget(user_chip)
        
        layout.addLayout(top_bar)
        
        # Search & Filter Sub-Bar
        sub_bar = QHBoxLayout()
        
        btn_new_cat = QPushButton(f"+ {tr('btn_new_cat')}")
        btn_new_cat.setCursor(Qt.PointingHandCursor)
        btn_new_cat.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['CLR_PURPLE']};
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 9px 16px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #6D28D9;
            }}
        """)
        btn_new_cat.clicked.connect(self.on_create_category)
        
        self.search_ent = QLineEdit()
        self.search_ent.setPlaceholderText(f"{tr('search_lbl')} ... 🔍")
        self.search_ent.textChanged.connect(self.populate_tree)
        apply_rtl_to_widget(self.search_ent)

        self.sort_cb = QComboBox()
        self.sort_cb.addItems([
            f"{tr('sort_lbl')} {tr('sort_visits')} ⇅",
            f"{tr('sort_lbl')} {tr('sort_name')}",
            f"{tr('sort_lbl')} {tr('sort_date')}"
        ])
        self.sort_cb.currentIndexChanged.connect(lambda idx: self.populate_tree(self.search_ent.text() if hasattr(self, 'search_ent') and self.search_ent else ""))
        
        self.cat_view_mode = getattr(self, 'cat_view_mode', 'list')
        self.btn_view_mode = QPushButton("⊞" if self.cat_view_mode == "list" else "☰")
        self.btn_view_mode.setFixedSize(38, 38)
        self.btn_view_mode.setCursor(Qt.PointingHandCursor)
        self.btn_view_mode.setToolTip("عرض على شكل مربعات / بطاقات (Grid View)" if is_ar else "Grid View")
        self.btn_view_mode.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['CLR_CARD_BG']};
                color: {c['FG_TEXT']};
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {c['CLR_PURPLE']};
                color: #FFFFFF;
                border: 1px solid {c['CLR_PURPLE']};
            }}
        """)
        self.btn_view_mode.clicked.connect(self.toggle_cat_view_mode)
        
        sub_bar.addWidget(btn_new_cat)
        sub_bar.addWidget(self.search_ent, 1)
        sub_bar.addWidget(self.sort_cb)
        sub_bar.addWidget(self.btn_view_mode)
        
        layout.addLayout(sub_bar)

        # Categories Stacked Container (List vs Grid)
        self.cat_stack = QStackedWidget()

        # Categories List View (Table)
        self.tree = QTreeWidget()
        if is_ar:
            self.tree.setLayoutDirection(Qt.RightToLeft)
        else:
            self.tree.setLayoutDirection(Qt.LeftToRight)
        self.tree.setHeaderLabels(["File", tr('col_cat_name'), tr('col_visits'), tr('col_notes'), tr('col_scheduled'), tr('col_status'), tr('col_actions')])
        self.tree.hideColumn(0)

        from PyQt5.QtWidgets import QHeaderView
        cat_hdr = self.tree.header()
        cat_hdr.setStretchLastSection(False)
        cat_hdr.setDefaultAlignment(Qt.AlignCenter)

        self.tree.setColumnWidth(1, 260)
        self.tree.setColumnWidth(2, 90)
        self.tree.setColumnWidth(3, 100)
        self.tree.setColumnWidth(4, 100)
        self.tree.setColumnWidth(5, 110)
        self.tree.setColumnWidth(6, 170)

        cat_hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        cat_hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        cat_hdr.setSectionResizeMode(2, QHeaderView.Interactive)
        cat_hdr.setSectionResizeMode(3, QHeaderView.Interactive)
        cat_hdr.setSectionResizeMode(4, QHeaderView.Interactive)
        cat_hdr.setSectionResizeMode(5, QHeaderView.Interactive)
        cat_hdr.setSectionResizeMode(6, QHeaderView.Fixed)
        
        def on_cat_click(item, col):
            if col != 6: # Ignore action buttons column
                self.on_open(item)
                
        self.tree.itemClicked.connect(on_cat_click)
        self.tree.itemDoubleClicked.connect(on_cat_click)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.cat_stack.addWidget(self.tree)

        # Categories Grid View (Cards Scroll Area)
        self.cat_grid_scroll = QScrollArea()
        self.cat_grid_scroll.setWidgetResizable(True)
        self.cat_grid_scroll.setStyleSheet(f"background-color: {c['CLR_MAIN_BG']}; border: none;")

        self.cat_grid_container = QWidget()
        self.cat_grid_container.setStyleSheet(f"background-color: {c['CLR_MAIN_BG']};")
        self.cat_grid_layout = QGridLayout(self.cat_grid_container)
        self.cat_grid_layout.setContentsMargins(4, 4, 4, 4)
        self.cat_grid_layout.setSpacing(12)
        self.cat_grid_scroll.setWidget(self.cat_grid_container)
        self.cat_stack.addWidget(self.cat_grid_scroll)

        layout.addWidget(self.cat_stack, 1)

        if self.cat_view_mode == "grid":
            self.cat_stack.setCurrentIndex(1)
        else:
            self.cat_stack.setCurrentIndex(0)

        # Table Footer Pagination Bar
        footer = QHBoxLayout()
        footer_count = QLabel("عرض الفئات" if is_ar else "Viewing categories")
        footer_count.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 12px;")
        
        page_btn = QPushButton("1")
        page_btn.setFixedSize(30, 30)
        page_btn.setStyleSheet(f"background-color: {c['CLR_PURPLE']}; color: white; border-radius: 6px; font-weight: bold;")
        
        footer.addWidget(page_btn)
        footer.addStretch()
        footer.addWidget(footer_count)
        footer.addStretch()
        
        page_size_lbl = QLabel("عرض 10 ▾" if is_ar else "Show 10 ▾")
        page_size_lbl.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 12px; background: {c['CLR_CARD_BG']}; padding: 4px 10px; border: 1px solid {c['CLR_BORDER']}; border-radius: 6px;")
        footer.addWidget(page_size_lbl)
        
        # Shortcuts for Sorting & View Mode
        self.sc_sort1 = QShortcut(QKeySequence("Ctrl+Alt+B"), self)
        self.sc_sort1.setContext(Qt.ApplicationShortcut)
        self.sc_sort1.activated.connect(self.on_shortcut_sort)

        self.sc_sort2 = QShortcut(QKeySequence("Ctrl+B"), self)
        self.sc_sort2.setContext(Qt.ApplicationShortcut)
        self.sc_sort2.activated.connect(self.on_shortcut_sort)

        self.sc_sort3 = QShortcut(QKeySequence("Alt+B"), self)
        self.sc_sort3.setContext(Qt.ApplicationShortcut)
        self.sc_sort3.activated.connect(self.on_shortcut_sort)

        self.sc_view = QShortcut(QKeySequence("Ctrl+Alt+V"), self)
        self.sc_view.setContext(Qt.ApplicationShortcut)
        self.sc_view.activated.connect(self.toggle_cat_view_mode)

        return area

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_B:
            if (event.modifiers() & Qt.ControlModifier) or (event.modifiers() & Qt.AltModifier):
                self.on_shortcut_sort()
                event.accept()
                return
        elif event.key() == Qt.Key_V:
            if (event.modifiers() & Qt.ControlModifier) or (event.modifiers() & Qt.AltModifier):
                self.toggle_cat_view_mode()
                event.accept()
                return
        super().keyPressEvent(event)

    def on_shortcut_sort(self):
        if hasattr(self, 'sort_cb') and self.sort_cb:
            curr_idx = self.sort_cb.currentIndex()
            next_idx = (curr_idx + 1) % self.sort_cb.count()
            self.sort_cb.setCurrentIndex(next_idx)
            search_query = self.search_ent.text() if hasattr(self, 'search_ent') else ""
            self.populate_tree(search_query)
            self.sort_cb.setFocus()
            self.sort_cb.showPopup()
            from PyQt5.QtWidgets import QToolTip
            from PyQt5.QtGui import QCursor
            QToolTip.showText(QCursor.pos(), f"↕️ {self.sort_cb.currentText()}", self)

    def build_kanban_view(self):
        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        area = QWidget()
        area.setStyleSheet(f"background-color: {c['CLR_MAIN_BG']};")
        layout = QVBoxLayout(area)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        lbl = QLabel(tr('kanban_header'))
        lbl.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 22px; font-weight: bold;")
        sub = QLabel("متابعة حالة المهمات: قيد الانتظار، قيد التنفيذ، والمهام المكتملة" if is_ar else "Track task statuses: To Do, In Progress, and Completed Tasks")
        sub.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 12px;")
        title_box.addWidget(lbl)
        title_box.addWidget(sub)
        top.addLayout(title_box)
        top.addStretch()
        
        btn_new_t = QPushButton(f"+ {tr('btn_new_task')}")
        btn_new_t.setStyleSheet(f"background-color: {c['CLR_PURPLE']}; color: white; padding: 8px 16px; border-radius: 8px; font-weight: bold;")
        btn_new_t.clicked.connect(self.on_new_task)
        top.addWidget(btn_new_t)
        layout.addLayout(top)

        # 3 Board Columns
        board = QHBoxLayout()
        board.setSpacing(12)
        
        def create_col(title, header_bg, text_color="#FFFFFF"):
            frame = QFrame()
            frame.setStyleSheet(f"background-color: {c['CLR_CARD_BG']}; border: 1px solid {c['CLR_BORDER']}; border-radius: 10px;")
            cl = QVBoxLayout(frame)
            cl.setContentsMargins(0, 0, 0, 0)
            
            h = QLabel(title)
            h.setAlignment(Qt.AlignCenter)
            h.setStyleSheet(f"background-color: {header_bg}; color: {text_color}; font-weight: bold; font-size: 14px; padding: 12px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
            cl.addWidget(h)
            
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("border: none; background: transparent;")
            cw = QWidget()
            cw.setStyleSheet("background: transparent;")
            cwl = QVBoxLayout(cw)
            cwl.setAlignment(Qt.AlignTop)
            cwl.setSpacing(10)
            scroll.setWidget(cw)
            cl.addWidget(scroll)
            return frame, cwl

        hdr_todo = "#2C2C3A" if c['IS_DARK'] else "#CBD5E1"
        hdr_prog = "#3D3812" if c['IS_DARK'] else "#FEF3C7"
        hdr_done = "#0F3D24" if c['IS_DARK'] else "#D1FAE5"
        txt_col = "#FFFFFF" if c['IS_DARK'] else "#0F172A"

        col_todo, self.k_todo_layout = create_col(tr('col_todo'), hdr_todo, txt_col)
        col_prog, self.k_prog_layout = create_col(tr('col_in_progress'), hdr_prog, txt_col)
        col_done, self.k_done_layout = create_col(tr('col_done'), hdr_done, txt_col)
        
        board.addWidget(col_todo)
        board.addWidget(col_prog)
        board.addWidget(col_done)
        
        layout.addLayout(board, 1)
        self.refresh_kanban_board()
        return area

    def open_and_refresh_task(self, fp):
        show_note_view_window(fp, parent=self)
        self.refresh_kanban_board()
        self.populate_tree()

    def move_task_status(self, fp, new_status):
        update_frontmatter_keys(fp, {'status': new_status})
        self.refresh_kanban_board()
        self.trigger_instant_bg_sync()

    def refresh_kanban_board(self):
        if not hasattr(self, 'k_todo_layout'): return
        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        for l in [self.k_todo_layout, self.k_prog_layout, self.k_done_layout]:
            while l.count():
                child = l.takeAt(0)
                if child.widget(): child.widget().deleteLater()
                
        tasks = get_all_tasks()
        for t in tasks:
            st = t.get('status', 'todo').lower()
            if st == 'in_progress': parent_l = self.k_prog_layout
            elif st == 'done': parent_l = self.k_done_layout
            else: parent_l = self.k_todo_layout
            
            card = QFrame()
            card.setStyleSheet(f"background-color: {c['CLR_ROW_BG']}; border: 1px solid {c['CLR_BORDER']}; border-radius: 8px; padding: 10px;")
            cl = QVBoxLayout(card)
            cl.setSpacing(6)
            
            t_lbl = QLabel(t['title'])
            t_lbl.setStyleSheet(f"color: {c['FG_TEXT']}; font-weight: bold; font-size: 13px;")
            cl.addWidget(t_lbl)
            
            btns = QHBoxLayout()
            btns.setSpacing(6)
            b_view = QPushButton("📖 " + ("عرض" if is_ar else "View"))
            b_view.setStyleSheet(f"background: {c['CLR_CARD_BG']}; color: {c['FG_MUTED']}; padding: 4px 8px; border-radius: 4px; font-weight: bold;")
            b_view.clicked.connect(lambda checked, fp=t['file']: self.open_and_refresh_task(fp))
            btns.addWidget(b_view)
            
            if st == 'todo':
                b_move = QPushButton("▶ " + ("قيد التنفيذ" if is_ar else "In Progress"))
                b_move.setStyleSheet("background: #3D3812; color: #FBBF24; padding: 4px 8px; border-radius: 4px; font-weight: bold;")
                b_move.clicked.connect(lambda checked, fp=t['file']: self.move_task_status(fp, 'in_progress'))
                btns.addWidget(b_move)
            elif st == 'in_progress':
                b_back = QPushButton("◀ " + ("للانتظار" if is_ar else "To Do"))
                b_back.setStyleSheet("background: #2C2C3A; color: #94A3B8; padding: 4px 8px; border-radius: 4px;")
                b_back.clicked.connect(lambda checked, fp=t['file']: self.move_task_status(fp, 'todo'))
                btns.addWidget(b_back)
                
                b_done = QPushButton("✔ " + ("إكمال" if is_ar else "Complete"))
                b_done.setStyleSheet("background: #0F3D24; color: #34D399; padding: 4px 8px; border-radius: 4px; font-weight: bold;")
                b_done.clicked.connect(lambda checked, fp=t['file']: self.move_task_status(fp, 'done'))
                btns.addWidget(b_done)
            elif st == 'done':
                b_back = QPushButton("◀ " + ("قيد التنفيذ" if is_ar else "In Progress"))
                b_back.setStyleSheet("background: #3D3812; color: #FBBF24; padding: 4px 8px; border-radius: 4px;")
                b_back.clicked.connect(lambda checked, fp=t['file']: self.move_task_status(fp, 'in_progress'))
                btns.addWidget(b_back)

            btns.addStretch()
            cl.addLayout(btns)
            parent_l.addWidget(card)

    def build_scripts_view(self):
        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        area = QWidget()
        area.setStyleSheet(f"background-color: {c['CLR_MAIN_BG']};")
        layout = QVBoxLayout(area)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        
        h_lbl = QLabel("👨‍💻 " + ("السكربتات والأتمتة المجدولة" if is_ar else "Scripts & Scheduled Automation"))
        h_lbl.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 22px; font-weight: bold;")
        sub = QLabel("قائمة جميع السكربتات التلقائية ومواعيد تشغيلها وإقلاعها" if is_ar else "List of all automated scripts and their schedule/boot timing")
        sub.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 12px;")
        layout.addWidget(h_lbl)
        layout.addWidget(sub)

        self.s_tree = QTreeWidget()
        if is_ar:
            self.s_tree.setLayoutDirection(Qt.RightToLeft)
        else:
            self.s_tree.setLayoutDirection(Qt.LeftToRight)
        headers = ["File", "اسم الفئة 📁" if is_ar else "Category 📁", "نوع الملاحظة 🏷️" if is_ar else "Type 🏷️", "اسم السكربت 🚀" if is_ar else "Script Name 🚀", "الزيارات 👁" if is_ar else "Visits 👁", "المجدولة ⏰" if is_ar else "Schedule ⏰", "الحالة ⚡" if is_ar else "Status ⚡", "الإجراءات 🛠️" if is_ar else "Actions 🛠️"]
        self.s_tree.setHeaderLabels(headers)
        self.s_tree.hideColumn(0)

        from PyQt5.QtWidgets import QHeaderView
        s_hdr = self.s_tree.header()
        s_hdr.setStretchLastSection(False)
        s_hdr.setDefaultAlignment(Qt.AlignCenter)

        self.s_tree.setColumnWidth(1, 110)
        self.s_tree.setColumnWidth(2, 100)
        self.s_tree.setColumnWidth(3, 240)
        self.s_tree.setColumnWidth(4, 80)
        self.s_tree.setColumnWidth(5, 150)
        self.s_tree.setColumnWidth(6, 110)
        self.s_tree.setColumnWidth(7, 160)

        s_hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        s_hdr.setSectionResizeMode(1, QHeaderView.Interactive)
        s_hdr.setSectionResizeMode(2, QHeaderView.Interactive)
        s_hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        s_hdr.setSectionResizeMode(4, QHeaderView.Interactive)
        s_hdr.setSectionResizeMode(5, QHeaderView.Interactive)
        s_hdr.setSectionResizeMode(6, QHeaderView.Interactive)
        s_hdr.setSectionResizeMode(7, QHeaderView.Fixed)
        
        def on_script_click(item, col):
            if col != 7:
                fp = item.data(0, Qt.UserRole)
                if fp:
                    show_note_view_window(fp, parent=self)
                
        self.s_tree.itemClicked.connect(on_script_click)
        layout.addWidget(self.s_tree, 1)
        self.refresh_scripts_view()
        return area

    def toggle_script_direct(self, filepath, curr_enabled):
        new_val = 'false' if curr_enabled else 'true'
        if new_val == 'true':
            n_data = parse_note_file(filepath)
            has_sched = bool(n_data.get('scheduled_exec', '').strip()) or \
                        (str(n_data.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1']) or \
                        (bool(n_data.get('event_trigger', '').strip()) and n_data.get('event_category', 'None') != 'None') or \
                        (bool(n_data.get('reminder', '').strip()))
            if not has_sched:
                QMessageBox.information(self, "تحديد الجدول", "ℹ️ هذا السكربت غير مجدول بعد.\nسأفتح لك نافذة الإعدادات الآن لتحديد الموعد أو الشروط المراد تفعيل السكربت بناءً عليها.")
                from ui_view_note import ScheduleExecDialog
                dlg = ScheduleExecDialog(self, filepath, n_data, self.refresh_scripts_view)
                if dlg.exec_() == QDialog.Accepted:
                    update_frontmatter_keys(filepath, {'script_enabled': 'true'})
                    self.refresh_scripts_view()
                    self.trigger_instant_bg_sync()
                return

        update_frontmatter_keys(filepath, {'script_enabled': new_val})
        self.refresh_scripts_view()
        self.trigger_instant_bg_sync()
        status_msg = "⏸️ تم تعطيل السكربت بنجاح!" if new_val == 'false' else "✅ تم تفعيل السكربت بنجاح!"
        QMessageBox.information(self, "حالة السكربت", status_msg)

    def refresh_scripts_view(self):
        if not hasattr(self, 's_tree'): return
        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        self.s_tree.clear()
        scripts = get_all_notes(only_scheduled_scripts=True)
        unsynced_set = get_git_unsynced_rel_paths()

        for s in scripts:
            filepath = s['file']
            is_enabled = str(s.get('script_enabled', 'true')).lower() in ['true', 'yes', '1']
            is_synced = is_file_synced(filepath, unsynced_set)

            item = QTreeWidgetItem(["", "", "", "", "", "", "", ""])
            item.setData(0, Qt.UserRole, filepath)
            self.s_tree.addTopLevelItem(item)

            # Col 1: Category
            cat_lbl = QLabel(f"📁 {s.get('category', 'عام')}")
            cat_lbl.setStyleSheet(f"color: {c['FG_MUTED']}; font-weight: bold; font-size: 12px;")
            self.s_tree.setItemWidget(item, 1, cat_lbl)

            # Col 2: Note Type
            tp_lbl = QLabel("🚀 سكريبت" if is_ar else "🚀 Script")
            tp_lbl.setAlignment(Qt.AlignCenter)
            tp_lbl.setStyleSheet("background-color: #281A45; color: #C084FC; font-weight: bold; font-size: 11px; padding: 3px 8px; border-radius: 5px;")
            tp_wrap = QWidget()
            tp_layout = QHBoxLayout(tp_wrap)
            tp_layout.setContentsMargins(0, 0, 0, 0)
            tp_layout.addWidget(tp_lbl, 0, Qt.AlignCenter)
            self.s_tree.setItemWidget(item, 2, tp_wrap)

            # Col 3: Title
            t_lbl = QLabel(f"🚀  {s['title']}")
            t_lbl.setStyleSheet(f"color: {c['FG_TEXT']}; font-weight: bold; font-size: 13px;")
            self.s_tree.setItemWidget(item, 3, t_lbl)

            # Col 4: Visits
            v_lbl = QLabel(f"👁 {s.get('access', 0)}")
            v_lbl.setAlignment(Qt.AlignCenter)
            v_lbl.setStyleSheet(f"color: {c['FG_MUTED']}; font-size: 12px; font-weight: bold;")
            self.s_tree.setItemWidget(item, 4, v_lbl)

            # Col 5: Timing
            s_exec = s.get('scheduled_exec', '').strip()
            is_boot = str(s.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1']
            evt_trig = s.get('event_trigger', '').strip()
            evt_cat = s.get('event_category', 'None')
            rem = s.get('reminder', '').strip()
            
            t_arr = []
            if s_exec: t_arr.append(f"⏰ {s_exec}")
            if is_boot: t_arr.append("🚀 إقلاع")
            if evt_trig and evt_cat != 'None': t_arr.append(f"⚡ {evt_trig}")
            if rem: t_arr.append(f"🔔 {rem}")
            
            timing_txt = " | ".join(t_arr) if t_arr else ("⚪ غير مجدول" if is_ar else "⚪ Unscheduled")
            tm_lbl = QLabel(timing_txt)
            tm_lbl.setStyleSheet("color: #FBBF24; font-size: 12px; font-weight: bold;" if t_arr else f"color: {c['CLR_TEXT_MUTED']}; font-size: 12px;")
            self.s_tree.setItemWidget(item, 5, tm_lbl)

            # Col 6: Status
            if is_synced:
                st_text = "🟢 متزامنة" if is_ar else "🟢 Synced"
                st_style = "color: #10B981; font-weight: bold; font-size: 12px;"
            else:
                st_text = "🔴 غير متزامنة" if is_ar else "🔴 Unsynced"
                st_style = "color: #EF4444; font-weight: bold; font-size: 12px;"

            st_badge = QLabel(st_text)
            st_badge.setAlignment(Qt.AlignCenter)
            st_badge.setStyleSheet(st_style)
            
            st_wrap = QWidget()
            stw_l = QHBoxLayout(st_wrap)
            stw_l.setContentsMargins(0, 0, 0, 0)
            stw_l.addWidget(st_badge, 0, Qt.AlignCenter)

            cat_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            tp_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            t_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            v_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            tm_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            st_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            self.s_tree.setItemWidget(item, 1, cat_lbl)
            self.s_tree.setItemWidget(item, 2, tp_wrap)
            self.s_tree.setItemWidget(item, 3, t_lbl)
            self.s_tree.setItemWidget(item, 4, v_lbl)
            self.s_tree.setItemWidget(item, 5, tm_lbl)
            self.s_tree.setItemWidget(item, 6, st_wrap)

            # Col 7: Actions
            act_w = QWidget()
            act_l = QHBoxLayout(act_w)
            act_l.setContentsMargins(0, 0, 0, 0)
            act_l.setSpacing(6)
            act_l.setAlignment(Qt.AlignCenter)
            
            b_open = QPushButton("📖 " + ("فتح" if is_ar else "Open"))
            b_open.setStyleSheet(f"background: {c['CLR_CARD_BG']}; color: {c['FG_TEXT']}; border: 1px solid {c['CLR_BORDER']}; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
            b_open.clicked.connect(lambda checked, fp=filepath: show_note_view_window(fp, parent=self))
            act_l.addWidget(b_open)
            
            t_txt = "⏸️ تعطيل" if is_enabled else "▶️ تفعيل"
            if not is_ar: t_txt = "⏸️ Disable" if is_enabled else "▶️ Enable"

            t_bg = "#381A1A" if is_enabled else "#064E3B"
            t_fg = "#F87171" if is_enabled else "#34D399"
            t_border = "#991B1B" if is_enabled else "#059669"
            
            b_toggle = QPushButton(t_txt)
            b_toggle.setStyleSheet(f"background: {t_bg}; color: {t_fg}; border: 1px solid {t_border}; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
            b_toggle.clicked.connect(lambda checked, fp=filepath, en=is_enabled: self.toggle_script_direct(fp, en))
            act_l.addWidget(b_toggle)

            self.s_tree.setItemWidget(item, 7, act_w)

    def build_reminders_view(self):
        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        area = QWidget()
        area.setStyleSheet(f"background-color: {c['CLR_MAIN_BG']};")
        layout = QVBoxLayout(area)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        
        h_lbl = QLabel("🔔 " + ("التذكيرات والمنبهات اليومية" if is_ar else "Daily Reminders & Alarms"))
        h_lbl.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 22px; font-weight: bold;")
        sub = QLabel("جميع التذكيرات النشطة والقادمة للملاحظات والمهام" if is_ar else "All active and upcoming reminders for notes and tasks")
        sub.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 12px;")
        layout.addWidget(h_lbl)
        layout.addWidget(sub)

        self.r_tree = QTreeWidget()
        if is_ar:
            self.r_tree.setLayoutDirection(Qt.RightToLeft)
        else:
            self.r_tree.setLayoutDirection(Qt.LeftToRight)
        headers = ["File", "اسم الفئة 📁" if is_ar else "Category 📁", "نوع الملاحظة 🏷️" if is_ar else "Type 🏷️", "عنوان التذكير 🔔" if is_ar else "Reminder Title 🔔", "الزيارات 👁" if is_ar else "Visits 👁", "الموعد والتكرار ⏰" if is_ar else "Schedule ⏰", "الحالة ⚡" if is_ar else "Status ⚡", "الإجراءات 🛠️" if is_ar else "Actions 🛠️"]
        self.r_tree.setHeaderLabels(headers)
        self.r_tree.hideColumn(0)

        from PyQt5.QtWidgets import QHeaderView
        r_hdr = self.r_tree.header()
        r_hdr.setStretchLastSection(False)
        r_hdr.setDefaultAlignment(Qt.AlignCenter)

        self.r_tree.setColumnWidth(1, 110)
        self.r_tree.setColumnWidth(2, 100)
        self.r_tree.setColumnWidth(3, 240)
        self.r_tree.setColumnWidth(4, 80)
        self.r_tree.setColumnWidth(5, 160)
        self.r_tree.setColumnWidth(6, 110)
        self.r_tree.setColumnWidth(7, 140)

        r_hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        r_hdr.setSectionResizeMode(1, QHeaderView.Interactive)
        r_hdr.setSectionResizeMode(2, QHeaderView.Interactive)
        r_hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        r_hdr.setSectionResizeMode(4, QHeaderView.Interactive)
        r_hdr.setSectionResizeMode(5, QHeaderView.Interactive)
        r_hdr.setSectionResizeMode(6, QHeaderView.Interactive)
        r_hdr.setSectionResizeMode(7, QHeaderView.Fixed)

        def on_rem_click(item, col):
            if col != 7:
                fp = item.data(0, Qt.UserRole)
                if fp:
                    show_note_view_window(fp, parent=self)

        self.r_tree.itemClicked.connect(on_rem_click)
        layout.addWidget(self.r_tree, 1)
        self.refresh_reminders_view()
        return area

    def refresh_reminders_view(self):
        if not hasattr(self, 'r_tree'): return
        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        self.r_tree.clear()
        all_n = get_all_notes()
        unsynced_set = get_git_unsynced_rel_paths()

        for n in all_n:
            rem = n.get('reminder')
            if rem:
                filepath = n['file']
                is_synced = is_file_synced(filepath, unsynced_set)
                pri = n.get('reminder_priority', 'normal')
                rep = n.get('reminder_repeat', 'none')

                item = QTreeWidgetItem(["", "", "", "", "", "", "", ""])
                item.setData(0, Qt.UserRole, filepath)
                self.r_tree.addTopLevelItem(item)

                # Col 1: Category
                cat_lbl = QLabel(f"📁 {n.get('category', 'عام')}")
                cat_lbl.setStyleSheet(f"color: {c['FG_MUTED']}; font-weight: bold; font-size: 12px;")
                self.r_tree.setItemWidget(item, 1, cat_lbl)

                # Col 2: Note Type
                raw_type = n.get('type', 'Note')
                is_script = raw_type == 'Script' or bool(n.get('scheduled_exec') or str(n.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1'])
                is_task = raw_type == 'Task'

                if is_script:
                    type_str = "🚀 سكريبت" if is_ar else "🚀 Script"
                    type_clr = "#C084FC"
                    type_bg = "#281A45"
                elif is_task:
                    type_str = "📋 مهمة" if is_ar else "📋 Task"
                    type_clr = "#FBBF24"
                    type_bg = "#453517"
                else:
                    type_str = "📝 ملاحظة" if is_ar else "📝 Note"
                    type_clr = "#38BDF8"
                    type_bg = "#0F2942"

                tp_lbl = QLabel(type_str)
                tp_lbl.setAlignment(Qt.AlignCenter)
                tp_lbl.setStyleSheet(f"background-color: {type_bg}; color: {type_clr}; font-weight: bold; font-size: 11px; padding: 3px 8px; border-radius: 5px;")
                tp_wrap = QWidget()
                tp_layout = QHBoxLayout(tp_wrap)
                tp_layout.setContentsMargins(0, 0, 0, 0)
                tp_layout.addWidget(tp_lbl, 0, Qt.AlignCenter)
                self.r_tree.setItemWidget(item, 2, tp_wrap)

                # Col 3: Title
                t_lbl = QLabel(f"🔔  {n['title']}")
                t_lbl.setStyleSheet(f"color: {c['FG_TEXT']}; font-weight: bold; font-size: 13px;")
                self.r_tree.setItemWidget(item, 3, t_lbl)

                # Col 4: Visits
                v_lbl = QLabel(f"👁 {n.get('access', 0)}")
                v_lbl.setAlignment(Qt.AlignCenter)
                v_lbl.setStyleSheet(f"color: {c['FG_MUTED']}; font-size: 12px; font-weight: bold;")
                self.r_tree.setItemWidget(item, 4, v_lbl)

                # Col 5: Timing & Repeat
                tm_lbl = QLabel(f"⏰ {rem} ({rep})")
                tm_lbl.setStyleSheet("color: #FBBF24; font-size: 12px; font-weight: bold;")
                self.r_tree.setItemWidget(item, 5, tm_lbl)

                # Col 6: Status
                if is_synced:
                    st_text = "🟢 متزامنة" if is_ar else "🟢 Synced"
                    st_style = "color: #10B981; font-weight: bold; font-size: 12px;"
                else:
                    st_text = "🔴 غير متزامنة" if is_ar else "🔴 Unsynced"
                    st_style = "color: #EF4444; font-weight: bold; font-size: 12px;"
                st_badge = QLabel(st_text)
                st_badge.setAlignment(Qt.AlignCenter)
                st_badge.setStyleSheet(st_style)
                
                st_wrap = QWidget()
                stw_l = QHBoxLayout(st_wrap)
                stw_l.setContentsMargins(0, 0, 0, 0)
                stw_l.addWidget(st_badge, 0, Qt.AlignCenter)

                cat_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                tp_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                t_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                v_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                tm_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                st_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)

                self.r_tree.setItemWidget(item, 1, cat_lbl)
                self.r_tree.setItemWidget(item, 2, tp_wrap)
                self.r_tree.setItemWidget(item, 3, t_lbl)
                self.r_tree.setItemWidget(item, 4, v_lbl)
                self.r_tree.setItemWidget(item, 5, tm_lbl)
                self.r_tree.setItemWidget(item, 6, st_wrap)

                # Col 7: Actions
                act_w = QWidget()
                act_l = QHBoxLayout(act_w)
                act_l.setContentsMargins(0, 0, 0, 0)
                act_l.setAlignment(Qt.AlignCenter)

                b_open = QPushButton("📖 " + ("فتح" if is_ar else "Open"))
                b_open.setStyleSheet(f"background: {c['CLR_CARD_BG']}; color: {c['FG_TEXT']}; border: 1px solid {c['CLR_BORDER']}; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
                b_open.clicked.connect(lambda checked, fp=filepath: show_note_view_window(fp, parent=self))
                act_l.addWidget(b_open)

                self.r_tree.setItemWidget(item, 7, act_w)

    def build_git_view(self):
        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {c['CLR_MAIN_BG']};
                border: none;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {c['CLR_SIDEBAR_BG']};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {c['CLR_BORDER']};
                border-radius: 4px;
            }}
        """)

        area = QWidget()
        area.setStyleSheet(f"background-color: {c['CLR_MAIN_BG']};")
        main_layout = QVBoxLayout(area)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(20)

        # Top Header Bar
        top_bar = QHBoxLayout()
        header_icon = QLabel("🌿")
        header_icon.setStyleSheet("font-size: 26px; color: #38BDF8; background: transparent; padding-right: 4px;")
        
        title_box = QVBoxLayout()
        h_title = QLabel("🌿 " + tr('git_header'))
        h_title.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 24px; font-weight: bold; background: transparent;")
        h_sub = QLabel("مزامنة ملاحظاتك ومهامك بأمان تام مع مستودع GitHub" if is_ar else "Securely sync your notes and tasks with your GitHub repository")
        h_sub.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 13px; background: transparent;")
        title_box.addWidget(h_title)
        title_box.addWidget(h_sub)
        
        top_bar.addWidget(header_icon)
        top_bar.addLayout(title_box)
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        CARD_QSS = f"""
            QFrame {{
                background-color: {c['CLR_CARD_BG']};
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 12px;
                padding: 16px;
            }}
        """

        def make_card_header(icon_symbol, title_str, desc_str):
            header_w = QWidget()
            header_w.setStyleSheet("background: transparent;")
            h_lay = QHBoxLayout(header_w)
            h_lay.setContentsMargins(0, 0, 0, 0)
            h_lay.setSpacing(14)

            icon_circle = QLabel(icon_symbol)
            icon_circle.setAlignment(Qt.AlignCenter)
            icon_circle.setFixedSize(40, 40)
            icon_circle.setStyleSheet(f"""
                background-color: {c['CLR_MAIN_BG']};
                color: #38BDF8;
                border-radius: 20px;
                font-size: 18px;
                border: 1px solid {c['CLR_BORDER']};
            """)

            t_box = QVBoxLayout()
            t_box.setSpacing(2)
            lbl_t = QLabel(title_str)
            lbl_t.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 15px; font-weight: bold; background: transparent;")
            lbl_d = QLabel(desc_str)
            lbl_d.setWordWrap(True)
            lbl_d.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 12px; background: transparent;")
            t_box.addWidget(lbl_t)
            t_box.addWidget(lbl_d)

            h_lay.addWidget(icon_circle)
            h_lay.addLayout(t_box, 1)
            return header_w

        # --- Card 1: Local Storage & Sync Folder ---
        card2 = QFrame()
        card2.setStyleSheet(CARD_QSS)
        c2_lay = QVBoxLayout(card2)
        c2_lay.setSpacing(14)
        c2_head = make_card_header(
            "📁",
            "مجلد الحفظ والمزامنة المحلي" if is_ar else "Local Sync Folder",
            "حدد المجلد المحلي على جهازك الذي ترغب بتخزين بياناتك فيه ومزامنتها مع GitHub." if is_ar else "Specify the local folder on your device for storing and syncing notes."
        )
        c2_lay.addWidget(c2_head)

        c2_controls = QHBoxLayout()
        c2_controls.setSpacing(10)
        self.txt_local_dir = QLineEdit(NOTES_DIR)
        self.txt_local_dir.setReadOnly(True)
        self.txt_local_dir.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c['CLR_MAIN_BG']};
                color: #38BDF8;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)

        self.btn_browse_dir = QPushButton("تغيير المجلد" if is_ar else "Change Folder")
        self.btn_browse_dir.setCursor(Qt.PointingHandCursor)
        self.btn_browse_dir.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['CLR_CARD_BG']};
                color: #38BDF8;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 8px;
                padding: 10px 18px;
            }}
            QPushButton:hover {{
                background-color: {c['CLR_ROW_HOVER']};
                color: {c['FG_TEXT']};
            }}
        """)
        self.btn_browse_dir.clicked.connect(self.on_browse_local_dir)

        c2_controls.addWidget(self.txt_local_dir, 1)
        c2_controls.addWidget(self.btn_browse_dir)
        c2_lay.addLayout(c2_controls)
        left_col.addWidget(card2)

        # --- Card 2: Configure GitHub Repository ---
        card3 = QFrame()
        card3.setStyleSheet(CARD_QSS)
        c3_lay = QVBoxLayout(card3)
        c3_lay.setSpacing(12)
        c3_head = make_card_header(
            "🔀",
            "تكوين وإعداد مستودع GitHub" if is_ar else "Configure GitHub Repository",
            "قم بربط مستودع GitHub الخاص بك لمزامنة بياناتك وتغييراتك بأمان." if is_ar else "Connect your private GitHub repository to securely sync changes."
        )
        c3_lay.addWidget(c3_head)

        self.txt_git_url = QLineEdit()
        self.txt_git_url.setPlaceholderText("https://github.com/username/repository.git")
        self.txt_git_url.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c['CLR_MAIN_BG']};
                color: {c['FG_TEXT']};
                font-size: 13px;
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 8px;
                padding: 10px 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {c['CLR_PURPLE']};
            }}
        """)
        c3_lay.addWidget(self.txt_git_url)

        self.btn_save_git = QPushButton("🔗 " + tr('btn_init_push'))
        self.btn_save_git.setCursor(Qt.PointingHandCursor)
        self.btn_save_git.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['CLR_PURPLE']};
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background-color: #6D28D9;
            }}
        """)
        self.btn_save_git.clicked.connect(self.on_start_git_setup)
        c3_lay.addWidget(self.btn_save_git)

        btn_sub_row = QHBoxLayout()
        btn_sub_row.setSpacing(10)

        self.btn_sync_now = QPushButton("🔄 " + ("مزامنة فورية الآن" if is_ar else "Sync Now"))
        self.btn_sync_now.setCursor(Qt.PointingHandCursor)
        self.btn_sync_now.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['CLR_CARD_BG']};
                color: {c['FG_MUTED']};
                font-weight: bold;
                font-size: 12px;
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 8px;
                padding: 8px 14px;
            }}
            QPushButton:hover {{
                background-color: {c['CLR_ROW_HOVER']};
                color: {c['FG_TEXT']};
            }}
        """)
        self.btn_sync_now.clicked.connect(self.on_sync_git_page)

        self.btn_unlink = QPushButton("🗑️ " + ("إزالة الربط" if is_ar else "Unlink Repository"))
        self.btn_unlink.setCursor(Qt.PointingHandCursor)
        self.btn_unlink.setStyleSheet("""
            QPushButton {
                background-color: #271216;
                color: #F87171;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #7F1D1D;
                border-radius: 8px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #3F171D;
                color: #EF4444;
            }
        """)
        self.btn_unlink.clicked.connect(self.on_unlink_git)

        btn_sub_row.addWidget(self.btn_sync_now, 1)
        btn_sub_row.addWidget(self.btn_unlink, 1)
        c3_lay.addLayout(btn_sub_row)
        left_col.addWidget(card3)

        # --- Card 3: Repository Status ---
        card4 = QFrame()
        card4.setStyleSheet(CARD_QSS)
        c4_lay = QVBoxLayout(card4)
        c4_lay.setSpacing(12)
        c4_head = make_card_header(
            "🎯",
            "حالة المستودع الحالية" if is_ar else "Current Repository Status",
            "عرض الحالة الحالية والارتباط بمستودع GitHub الخاص بك." if is_ar else "View connection status to your GitHub repository."
        )
        c4_lay.addWidget(c4_head)

        c4_r1 = QHBoxLayout()
        c4_r1.setSpacing(10)

        self.lbl_git_status_badge = QLabel("● " + ("متصل ومُفعّل" if is_ar else "Connected & Active"))
        self.lbl_git_status_badge.setStyleSheet("color: #10B981; font-weight: bold; font-size: 13px; background: transparent;")
        c4_r1.addWidget(self.lbl_git_status_badge, 1)

        col_br_box = QVBoxLayout()
        lbl_br_title = QLabel("الفرع الحالي" if is_ar else "Current Branch")
        lbl_br_title.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 11px; background: transparent;")
        self.lbl_git_branch_val = QLabel("main")
        self.lbl_git_branch_val.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 12px; background: transparent;")
        col_br_box.addWidget(lbl_br_title)
        col_br_box.addWidget(self.lbl_git_branch_val)
        c4_r1.addLayout(col_br_box, 1)

        c4_lay.addLayout(c4_r1)

        c4_r2 = QHBoxLayout()
        c4_r2.setSpacing(10)

        col_url_box = QVBoxLayout()
        lbl_url_title = QLabel("رابط المستودع (URL)" if is_ar else "Repository URL")
        lbl_url_title.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 11px; background: transparent;")
        self.lbl_git_url_val = QLabel("-")
        self.lbl_git_url_val.setWordWrap(True)
        self.lbl_git_url_val.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 12px; background: transparent;")
        col_url_box.addWidget(lbl_url_title)
        col_url_box.addWidget(self.lbl_git_url_val)
        c4_r2.addLayout(col_url_box, 1)

        col_cm_box = QVBoxLayout()
        lbl_cm_title = QLabel("آخر التغييرات (Commit)" if is_ar else "Last Commit")
        lbl_cm_title.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 11px; background: transparent;")
        self.lbl_git_commit_val = QLabel("-")
        self.lbl_git_commit_val.setWordWrap(True)
        self.lbl_git_commit_val.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 12px; background: transparent;")
        col_cm_box.addWidget(lbl_cm_title)
        col_cm_box.addWidget(self.lbl_git_commit_val)
        c4_r2.addLayout(col_cm_box, 1)

        c4_lay.addLayout(c4_r2)
        left_col.addWidget(card4)

        # --- Card 4: General Info ---
        card1 = QFrame()
        card1.setStyleSheet(CARD_QSS)
        c1_lay = QVBoxLayout(card1)
        c1_lay.setSpacing(8)
        c1_head = make_card_header(
            "🛡️",
            "المعلومات العامة والأمان" if is_ar else "Security & Info",
            "بياناتك مخزنة محلياً وأميناً على جهازك، مع إمكانية المزامنة السحابية الاحتياطية على GitHub." if is_ar else "Your data is stored locally and securely, with cloud backup to GitHub."
        )
        c1_lay.addWidget(c1_head)
        left_col.addWidget(card1)

        content_layout.addLayout(left_col, 1)

        # RIGHT COLUMN (Live Terminal Logs)
        right_col = QVBoxLayout()
        
        term_card = QFrame()
        term_card.setStyleSheet(f"""
            QFrame {{
                background-color: {c['CLR_CARD_BG']};
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        term_lay = QVBoxLayout(term_card)
        term_lay.setSpacing(12)

        term_top = QHBoxLayout()
        lbl_term_title = QLabel(">_ " + ("سجلاّت التيرمينال الحية" if is_ar else "Live Terminal Logs"))
        lbl_term_title.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 14px; font-weight: bold; background: transparent;")
        
        lbl_live_badge = QLabel("● " + ("مباشر (Live)" if is_ar else "Live"))
        lbl_live_badge.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px; background: transparent;")
        
        term_top.addWidget(lbl_term_title)
        term_top.addStretch()
        term_top.addWidget(lbl_live_badge)
        term_lay.addLayout(term_top)

        self.txt_git_log = QTextEdit()
        self.txt_git_log.setReadOnly(True)
        self.txt_git_log.setLineWrapMode(QTextEdit.WidgetWidth)
        self.txt_git_log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {c['CLR_MAIN_BG']};
                color: #34D399;
                font-family: 'Monaco', 'DejaVu Sans Mono', 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.6;
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 8px;
                padding: 12px;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {c['CLR_SIDEBAR_BG']};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {c['CLR_BORDER']};
                border-radius: 3px;
            }}
        """)
        term_lay.addWidget(self.txt_git_log, 1)

        right_col.addWidget(term_card, 1)
        content_layout.addLayout(right_col, 1)

        main_layout.addLayout(content_layout)

        scroll.setWidget(area)
        return scroll

    def on_browse_local_dir(self):
        remote_url = get_git_remote_url()
        if remote_url or os.path.exists(os.path.join(NOTES_DIR, ".git")):
            reply = QMessageBox.warning(
                self,
                "⚠️ تنبيه مهم: تغيير مجلد الحفظ والمزامنة",
                "المستودع المحلي مربوط ومزامن حالياً مع GitHub.\n\n"
                "تنبيه: إن تغيير مجلد التخزين سيوقف المزامنة الحالية لهذا المجلد، وستضطر إلى إعادة إعداد ومزامنة مستودع GitHub للمسار الجديد.\n\n"
                "هل أنت تأكد من اختيار تغيير المجلد المربوط؟",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        new_dir = QFileDialog.getExistingDirectory(
            self,
            "اختر مجلد التخزين والمزامنة المحلي للملاحظات",
            self.txt_local_dir.text() or os.path.expanduser("~")
        )
        if new_dir:
            updated_path = update_notes_dir(new_dir)
            self.txt_local_dir.setText(updated_path)
            self.refresh_git_view()
            self.populate_tree()
            QMessageBox.information(
                self,
                "تم تحديث المجلد المحلي",
                f"✅ تم تفعيل وتعين المجلد المحلي بنجاح!\n\n📂 المسار الجديد:\n{updated_path}\n\nيمكنك الآن إعداد ومزامنة ملاحظاتك في هذا المسار."
            )

    def refresh_git_view(self):
        if hasattr(self, 'txt_local_dir'):
            from config import NOTES_DIR as ACTIVE_ND
            self.txt_local_dir.setText(ACTIVE_ND)

        remote_url = get_git_remote_url()
        branch = get_git_branch_name()
        last_commit = get_git_last_commit_info()

        if remote_url:
            self.lbl_git_status_badge.setText("🟢 المستودع مربوط ومُفعل بنجاح")
            self.lbl_git_status_badge.setStyleSheet("color: #10B981; font-weight: bold; font-size: 14px; border: none;")
            self.lbl_git_url_val.setText(remote_url)
            if not self.txt_git_url.text().strip():
                self.txt_git_url.setText(remote_url)
            if hasattr(self, 'btn_unlink'):
                self.btn_unlink.setVisible(True)
        else:
            self.lbl_git_status_badge.setText("🔴 لم يتم ربط مستودع GitHub بعد")
            self.lbl_git_status_badge.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 14px; border: none;")
            self.lbl_git_url_val.setText("غير مربوط")
            if hasattr(self, 'btn_unlink'):
                self.btn_unlink.setVisible(False)

        self.lbl_git_branch_val.setText(branch if branch else "main")
        self.lbl_git_commit_val.setText(last_commit)

    def append_git_log(self, text):
        self.txt_git_log.append(text)
        self.txt_git_log.verticalScrollBar().setValue(self.txt_git_log.verticalScrollBar().maximum())

    def on_git_setup_finished(self):
        self.btn_save_git.setEnabled(True)
        self.btn_save_git.setText("🔗 حفظ وربط المستودع")
        self.refresh_git_view()
        self.populate_tree()

    def on_start_git_setup(self):
        local_dir = self.txt_local_dir.text().strip() if hasattr(self, 'txt_local_dir') else ""
        if not local_dir or not os.path.exists(local_dir):
            QMessageBox.warning(
                self,
                "تنبيه: مجلد الحفظ غير محدد",
                "يُرجى تحديد واختيار مجلد الحفظ والمزامنة المحلي أولاً قبل إتمام عملية ربط المستودع!"
            )
            return

        raw_url = self.txt_git_url.text().strip()
        if not raw_url:
            QMessageBox.warning(self, "تحذير", "يُرجى إدخال رابط مستودع GitHub أولاً!")
            return

        clean_url = sanitize_git_url(raw_url)
        if clean_url != raw_url:
            self.txt_git_url.setText(clean_url)

        self.btn_save_git.setEnabled(False)
        self.btn_save_git.setText("⏳ جاري الفحص والربط...")
        self.txt_git_log.clear()

        def run_setup_thread():
            try:
                self.git_log_signal.emit("<span style='color: #38BDF8; font-weight: bold;'>🔍 جاري تنظيف الأقفال وتحليل المستودع...</span>")
                clean_stale_git_locks()
                os.chdir(NOTES_DIR)

                # Cleanup misplaced .git inside notes/ subdirectory if present
                misplaced_git = os.path.join(NOTES_PATH, ".git")
                if os.path.exists(misplaced_git):
                    try:
                        import shutil
                        shutil.rmtree(misplaced_git)
                    except Exception:
                        pass

                # Check for large files (>95MB)
                large_files = check_large_files()
                if large_files:
                    self.git_log_signal.emit(f"<span style='color: #FBBF24;'>⚠️ تنبيه: تم اكتشاف ملفات كبيرة الحجم قد يرفضها GitHub: {', '.join(large_files)}</span>")

                captured_output = []

                def exec_cmd(cmd):
                    self.git_log_signal.emit(f"<span style='color: #818CF8;'>$ {' '.join(cmd)}</span>")
                    try:
                        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=NOTES_DIR)
                        for line in p.stdout:
                            clean_line = line.rstrip('\n').replace('<', '&lt;').replace('>', '&gt;')
                            captured_output.append(clean_line)
                            self.git_log_signal.emit(f"<span style='color: #9CA3AF;'>{clean_line}</span>")
                        p.wait()
                        return p.returncode
                    except Exception as e:
                        self.git_log_signal.emit(f"<span style='color: #F87171;'>Error: {e}</span>")
                        return 1

                # 1. Initialize git if not present in NOTES_DIR
                if not os.path.exists(os.path.join(NOTES_DIR, ".git")):
                    exec_cmd(["git", "init"])

                # 2. Configure remote origin
                subprocess.run(["git", "remote", "remove", "origin"], cwd=NOTES_DIR, stderr=subprocess.DEVNULL)
                code_remote = exec_cmd(["git", "remote", "add", "origin", clean_url])

                if code_remote == 0:
                    # 3. Detect remote default branch (main vs master vs custom)
                    self.git_log_signal.emit("<span style='color: #38BDF8;'>🌿 فحص اسم الفرع الافتراضي للمستودع البعيد...</span>")
                    target_branch = detect_remote_default_branch("origin")
                    self.git_log_signal.emit(f"<span style='color: #34D399;'>✅ الفرع المستهدف: <b>{target_branch}</b></span>")
                    exec_cmd(["git", "branch", "-M", target_branch])

                    # 4. Stage and commit local notes
                    exec_cmd(["git", "add", "-A"])
                    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=NOTES_DIR).returncode != 0:
                        exec_cmd(["git", "commit", "-m", f"Initial setup from DevNotes {time.strftime('%Y-%m-%d %H:%M')}"])

                    # 5. Pull with unrelated histories & auto-merge protection
                    self.git_log_signal.emit("<br><span style='color: #FBBF24;'>🔄 جاري جلب ومزيج السجلات من المستودع البعيد...</span>")
                    exec_cmd(["git", "pull", "origin", target_branch, "--allow-unrelated-histories", "--no-rebase", "-Xours"])

                    # 6. Push to GitHub
                    self.git_log_signal.emit("<br><span style='color: #38BDF8;'>🚀 جاري رفع الملاحظات والبيانات إلى GitHub...</span>")
                    push_res = exec_cmd(["git", "push", "-u", "origin", target_branch, "--force-with-lease"])

                    if push_res == 0:
                        self.git_log_signal.emit("<br><span style='color: #34D399; font-weight: bold;'>🎉 تم ربط ومزامنة المستودع بنجاح تام!</span>")
                    else:
                        full_log = "\n".join(captured_output)
                        diag_msg = diagnose_git_error(full_log, clean_url)
                        self.git_log_signal.emit(f"<br><div style='background: #281616; padding: 12px; border: 1px solid #7F1D1D; border-radius: 8px; color: #FCA5A5;'>{diag_msg}</div>")
            finally:
                self.git_finished_signal.emit()

        threading.Thread(target=run_setup_thread, daemon=True).start()

    def on_sync_git_page(self):
        sync_notes_gui(self)
        self.refresh_git_view()
        self.populate_tree()

    def on_unlink_git(self):
        reply = QMessageBox.question(
            self,
            "تأكيد إزالة الربط",
            "هل أنت تأكد من إزالة ربط المستودع الحالي (origin)؟ لن يتم حذف ملفاتك المحلية.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            unlink_git_remote()
            self.txt_git_url.clear()
            self.refresh_git_view()
            QMessageBox.information(self, "تمت الإزالة", "تمت إزالة رابط المستودع بنجاح.")

    def trigger_instant_bg_sync(self):
        def run_sync():
            try: sync_notes_cli()
            except Exception: pass
        threading.Thread(target=run_sync, daemon=True).start()

    def build_settings_view(self):
        from theme import get_theme, get_theme_colors
        c = get_theme_colors()

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setStyleSheet(f"background-color: {c['CLR_MAIN_BG']}; border: none;")

        container = QWidget()
        container.setStyleSheet(f"background-color: {c['CLR_MAIN_BG']};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(20)

        # 1. Header
        head_layout = QHBoxLayout()
        icon_lbl = QLabel("⚙️")
        icon_lbl.setStyleSheet("font-size: 26px; background: transparent;")

        title_vbox = QVBoxLayout()
        self.settings_header_title = QLabel(tr('settings_title'))
        self.settings_header_title.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 20px; font-weight: bold; background: transparent;")

        self.settings_header_sub = QLabel(tr('settings_sub'))
        self.settings_header_sub.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 12px; background: transparent;")

        title_vbox.addWidget(self.settings_header_title)
        title_vbox.addWidget(self.settings_header_sub)
        head_layout.addWidget(icon_lbl)
        head_layout.addLayout(title_vbox)
        head_layout.addStretch()
        layout.addLayout(head_layout)

        gb_style = f"""
            QGroupBox {{
                color: {c['FG_TEXT']};
                font-weight: bold;
                font-size: 14px;
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 16px;
                background-color: {c['CLR_CARD_BG']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 8px;
            }}
        """

        # Card 1: Language
        self.gb_lang_page = QGroupBox(tr('settings_gb_lang'))
        self.gb_lang_page.setStyleSheet(gb_style)
        l_lang = QVBoxLayout(self.gb_lang_page)
        l_lang.setContentsMargins(16, 16, 16, 16)
        l_lang.setSpacing(12)

        self.rb_lang_ar = QRadioButton("العربية (Arabic)")
        self.rb_lang_ar.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 14px; font-weight: bold;")
        self.rb_lang_en = QRadioButton("English (الإنجليزي)")
        self.rb_lang_en.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 14px; font-weight: bold;")

        self.bg_lang_group = QButtonGroup(container)
        self.bg_lang_group.addButton(self.rb_lang_ar)
        self.bg_lang_group.addButton(self.rb_lang_en)

        if get_lang() == 'ar':
            self.rb_lang_ar.setChecked(True)
        else:
            self.rb_lang_en.setChecked(True)

        l_lang.addWidget(self.rb_lang_ar)
        l_lang.addWidget(self.rb_lang_en)
        layout.addWidget(self.gb_lang_page)

        # Card 2: Theme (Dark / Light Mode)
        self.gb_theme_page = QGroupBox(tr('settings_gb_theme'))
        self.gb_theme_page.setStyleSheet(gb_style)
        l_theme = QVBoxLayout(self.gb_theme_page)
        l_theme.setContentsMargins(16, 16, 16, 16)
        l_theme.setSpacing(12)

        self.rb_theme_dark = QRadioButton("🌙 " + ("الوضع الليلي (Dark Mode)" if get_lang() == 'ar' else "Dark Mode"))
        self.rb_theme_dark.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 14px; font-weight: bold;")
        self.rb_theme_light = QRadioButton("☀️ " + ("الوضع النهاري (Light Mode)" if get_lang() == 'ar' else "Light Mode"))
        self.rb_theme_light.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 14px; font-weight: bold;")

        self.bg_theme_group = QButtonGroup(container)
        self.bg_theme_group.addButton(self.rb_theme_dark)
        self.bg_theme_group.addButton(self.rb_theme_light)

        if get_theme() == 'light':
            self.rb_theme_light.setChecked(True)
        else:
            self.rb_theme_dark.setChecked(True)

        l_theme.addWidget(self.rb_theme_dark)
        l_theme.addWidget(self.rb_theme_light)
        layout.addWidget(self.gb_theme_page)

        # Save Button Row
        btn_row = QHBoxLayout()
        self.btn_save_settings = QPushButton(tr('settings_save'))
        self.btn_save_settings.setCursor(Qt.PointingHandCursor)
        self.btn_save_settings.setStyleSheet(f"""
            QPushButton {{
                background-color: {CLR_BLUE};
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 24px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #1D4ED8;
            }}
        """)
        self.btn_save_settings.clicked.connect(self.on_apply_settings_page)
        btn_row.addWidget(self.btn_save_settings)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        area.setWidget(container)
        return area

    def refresh_settings_view(self):
        is_ar = (get_lang() == 'ar')
        if hasattr(self, 'rb_lang_ar'):
            if is_ar: self.rb_lang_ar.setChecked(True)
            else: self.rb_lang_en.setChecked(True)
        if hasattr(self, 'rb_theme_dark'):
            from theme import get_theme
            if get_theme() == 'light': self.rb_theme_light.setChecked(True)
            else: self.rb_theme_dark.setChecked(True)

    def on_apply_settings_page(self):
        new_lang = 'ar' if self.rb_lang_ar.isChecked() else 'en'
        set_lang(new_lang)

        new_theme = 'light' if self.rb_theme_light.isChecked() else 'dark'
        set_theme(new_theme)

        self.apply_theme_and_language()
        QMessageBox.information(
            self,
            tr('success'),
            "✅ " + ("تم حفظ وتطبيق الإعدادات بنجاح!" if get_lang() == 'ar' else "Settings saved and applied successfully!")
        )

    def apply_theme_and_language(self):
        from theme import get_theme_qss, get_theme_colors
        c = get_theme_colors()

        global CLR_MAIN_BG, CLR_CARD_BG, CLR_SIDEBAR_BG, CLR_BORDER, CLR_TEXT_MUTED
        CLR_MAIN_BG = c['CLR_MAIN_BG']
        CLR_CARD_BG = c['CLR_CARD_BG']
        CLR_SIDEBAR_BG = c['CLR_SIDEBAR_BG']
        CLR_BORDER = c['CLR_BORDER']
        CLR_TEXT_MUTED = c['CLR_TEXT_MUTED']

        qss = get_theme_qss()
        QApplication.instance().setStyleSheet(qss)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['CLR_MAIN_BG']};
                color: {c['FG_TEXT']};
                font-family: 'Segoe UI', 'DejaVu Sans', sans-serif;
            }}
            QWidget {{
                color: {c['FG_TEXT']};
                font-family: 'Segoe UI', 'DejaVu Sans', sans-serif;
            }}
            QTreeWidget {{
                background-color: {c['CLR_CARD_BG']};
                color: {c['FG_TEXT']};
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 10px;
                outline: none;
            }}
            QTreeWidget::item {{
                height: 54px;
                border-bottom: 1px solid {c['CLR_BORDER']};
            }}
            QTreeWidget::item:hover {{
                background-color: {c['CLR_ROW_HOVER']};
            }}
            QTreeWidget::item:selected {{
                background-color: #2563EB;
                color: #FFFFFF;
            }}
            QHeaderView::section {{
                background-color: {c['CLR_HEADER_BG']};
                color: {c['FG_MUTED']};
                padding: 10px;
                border: none;
                border-bottom: 1px solid {c['CLR_BORDER']};
                font-weight: bold;
                font-size: 12px;
            }}
            QLineEdit {{
                background-color: {c['CLR_CARD_BG']};
                color: {c['FG_TEXT']};
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {c['CLR_PURPLE']};
            }}
            QComboBox {{
                background-color: {c['CLR_CARD_BG']};
                color: {c['FG_TEXT']};
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {c['CLR_SIDEBAR_BG']};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {c['CLR_BORDER']};
                border-radius: 4px;
            }}
        """)

        curr_idx = self.stack.currentIndex() if hasattr(self, 'stack') else 0
        search_txt = self.search_ent.text() if hasattr(self, 'search_ent') and self.search_ent else ""

        # Replace Sidebar Widget
        if hasattr(self, 'main_layout') and hasattr(self, 'sidebar'):
            old_sidebar = self.sidebar
            self.sidebar = self.build_sidebar()
            self.main_layout.replaceWidget(old_sidebar, self.sidebar)
            old_sidebar.deleteLater()

        # Rebuild Stacked Views
        if hasattr(self, 'stack'):
            while self.stack.count():
                w = self.stack.widget(0)
                self.stack.removeWidget(w)
                w.deleteLater()

            self.view_cats = self.build_categories_view()
            self.stack.addWidget(self.view_cats)

            self.view_kanban = self.build_kanban_view()
            self.stack.addWidget(self.view_kanban)

            self.view_scripts = self.build_scripts_view()
            self.stack.addWidget(self.view_scripts)

            self.view_rems = self.build_reminders_view()
            self.stack.addWidget(self.view_rems)

            self.view_git = self.build_git_view()
            self.stack.addWidget(self.view_git)

            self.view_settings = self.build_settings_view()
            self.stack.addWidget(self.view_settings)

            self.stack.setCurrentIndex(curr_idx)
            self.update_nav_styles(curr_idx)

        if hasattr(self, 'search_ent') and search_txt:
            self.search_ent.setText(search_txt)

        self.populate_tree()
        self.refresh_settings_view()

    def toggle_cat_view_mode(self):
        if self.cat_view_mode == "list":
            self.cat_view_mode = "grid"
            self.btn_view_mode.setText("☰")
            self.btn_view_mode.setToolTip("عرض على شكل قائمة / واحد تحت واحد (List View)")
            self.cat_stack.setCurrentIndex(1)
        else:
            self.cat_view_mode = "list"
            self.btn_view_mode.setText("⊞")
            self.btn_view_mode.setToolTip("عرض على شكل مربعات / بطاقات (Grid View)")
            self.cat_stack.setCurrentIndex(0)
        self.populate_tree()

    def create_cat_grid_card(self, cat_name, data, idx, is_synced):
        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        card = QFrame()
        card.setCursor(Qt.PointingHandCursor)
        card.mousePressEvent = lambda event, c=cat_name: self.open_notes_list_for_cat(c)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {c['CLR_CARD_BG']};
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 10px;
                padding: 8px;
            }}
            QFrame:hover {{
                border: 1px solid {c['CLR_PURPLE']};
                background-color: {c['CLR_ROW_HOVER']};
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(8)

        top_h = QHBoxLayout()
        folder_color = FOLDER_COLORS[idx % len(FOLDER_COLORS)]
        icon_lbl = QLabel("📁")
        icon_lbl.setStyleSheet(f"font-size: 24px; color: {folder_color}; background: transparent;")
        
        st_txt = ("🟢 متزامنة" if is_synced else "🔴 غير متزامنة") if is_ar else ("🟢 Synced" if is_synced else "🔴 Unsynced")
        sync_badge = QLabel(st_txt)
        sync_badge.setToolTip("الفئة متزامنة بالكامل" if is_synced else "تحتوي الفئة على ملفات محليّة غير متزامنة")
        if is_synced:
            sync_badge.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
        else:
            sync_badge.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 11px;")
        
        top_h.addWidget(icon_lbl)
        top_h.addStretch()
        top_h.addWidget(sync_badge)
        c_layout.addLayout(top_h)

        title_str = f"📌 {cat_name}" if data['pinned'] else cat_name
        lbl_t = QLabel(title_str)
        lbl_t.setStyleSheet(f"color: {c['FG_TEXT']}; font-weight: bold; font-size: 15px;")
        c_layout.addWidget(lbl_t)

        info_h = QHBoxLayout()
        notes_txt = f"📄 {data['count']} " + ("ملاحظة" if is_ar else "note(s)")
        notes_cnt_lbl = QLabel(notes_txt)
        notes_cnt_lbl.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 11px; font-weight: bold;")
        vis_lbl = QLabel(f"👁 {data['access']}")
        vis_lbl.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 11px;")

        info_h.addWidget(notes_cnt_lbl)
        info_h.addStretch()
        info_h.addWidget(vis_lbl)
        c_layout.addLayout(info_h)

        act_h = QHBoxLayout()
        act_h.setSpacing(6)

        open_txt = "📂 " + ("فتح الفئة" if is_ar else "Open Category")
        btn_v = QPushButton(open_txt)
        btn_v.setCursor(Qt.PointingHandCursor)
        btn_v.setStyleSheet(f"background: {c['CLR_CARD_BG']}; color: {c['FG_TEXT']}; border: 1px solid {c['CLR_BORDER']}; border-radius: 4px; padding: 5px 12px; font-weight: bold; font-size: 11px;")
        btn_v.clicked.connect(lambda checked, c=cat_name: self.open_notes_list_for_cat(c))

        if is_ar:
            pin_txt = "📌 إلغاء التثبيت" if data['pinned'] else "📌 تثبيت"
        else:
            pin_txt = "📌 Unpin" if data['pinned'] else "📌 Pin"

        btn_p = QPushButton(pin_txt)
        btn_p.setCursor(Qt.PointingHandCursor)
        btn_p.setStyleSheet("background: #281A45; color: #C084FC; border-radius: 4px; padding: 5px 8px; font-weight: bold; font-size: 11px;")
        btn_p.clicked.connect(lambda checked, c=cat_name: self.on_toggle_pin_cat(c))

        act_h.addWidget(btn_v)
        act_h.addStretch()
        act_h.addWidget(btn_p)
        c_layout.addLayout(act_h)

        return card

    def populate_tree(self):
        if not hasattr(self, 'tree') or not hasattr(self, 'cat_grid_layout'):
            return

        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        self.tree.clear()
        
        while self.cat_grid_layout.count():
            child = self.cat_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        q = self.search_ent.text().lower() if hasattr(self, 'search_ent') and self.search_ent else ""
        sort_txt = self.sort_cb.currentText() if hasattr(self, 'sort_cb') and self.sort_cb else ""
        
        cats, pinned = get_categories_data()
        unsynced_set = get_git_unsynced_rel_paths()
        
        def sort_key(item):
            cat_name, data = item
            pinned_val = -1 if data['pinned'] else 0
            if "الاسم" in sort_txt or "Name" in sort_txt:
                return (pinned_val, cat_name.lower())
            elif "التاريخ" in sort_txt or "Date" in sort_txt:
                return (pinned_val, -data.get('created', 0), cat_name.lower())
            else:
                return (pinned_val, -data['access'], -data['count'], cat_name.lower())

        sorted_cats = sorted(cats.items(), key=sort_key)
        
        cols = 2
        filtered_cats = [(c_name, c_data) for c_name, c_data in sorted_cats if not q or q in c_name.lower()]
        
        for idx, (cat_name, data) in enumerate(filtered_cats):
            is_synced = is_category_synced(cat_name, unsynced_set)
            card = self.create_cat_grid_card(cat_name, data, idx, is_synced)
            row = idx // cols
            col = idx % cols
            self.cat_grid_layout.addWidget(card, row, col)
        
        for idx, (cat_name, data) in enumerate(sorted_cats):
            if q and q not in cat_name.lower():
                continue
                
            item = QTreeWidgetItem(["", "", "", "", "", "", ""])
            item.setData(0, Qt.UserRole, cat_name)
            self.tree.addTopLevelItem(item)

            # Col 1: Custom Category Title + Icon + Subtitle
            col0_widget = QWidget()
            col0_layout = QHBoxLayout(col0_widget)
            col0_layout.setContentsMargins(8, 4, 8, 4)
            col0_layout.setSpacing(10)

            folder_color = FOLDER_COLORS[idx % len(FOLDER_COLORS)]
            icon_lbl = QLabel("📁")
            icon_lbl.setStyleSheet(f"font-size: 22px; color: {folder_color}; background: transparent;")

            text_box = QVBoxLayout()
            text_box.setSpacing(2)
            title_str = f"📌 {cat_name}" if data['pinned'] else cat_name
            t_lbl = QLabel(title_str)
            t_lbl.setStyleSheet(f"color: {c['FG_TEXT']}; font-weight: bold; font-size: 14px; background: transparent;")
            
            sub_str = f"آخر تحديث: {data.get('last_updated', 'مؤخراً')}" if is_ar else f"Last updated: {data.get('last_updated', 'Recently')}"
            sub_lbl = QLabel(sub_str)
            sub_lbl.setStyleSheet(f"color: {c['CLR_TEXT_MUTED']}; font-size: 11px; background: transparent;")
            
            text_box.addWidget(t_lbl)
            text_box.addWidget(sub_lbl)

            col0_layout.addWidget(icon_lbl)
            col0_layout.addLayout(text_box)
            col0_layout.addStretch()

            # Col 2: Visits
            v_lbl = QLabel(f"👁 {data['access']}")
            v_lbl.setAlignment(Qt.AlignCenter)
            v_lbl.setStyleSheet(f"color: {c['FG_MUTED']}; font-size: 13px; font-weight: bold;")

            # Col 3: Notes count
            n_lbl = QLabel(str(data['count']))
            n_lbl.setAlignment(Qt.AlignCenter)
            n_lbl.setStyleSheet(f"color: {c['FG_TEXT']}; font-size: 13px; font-weight: bold;")

            # Col 4: Scheduled Badge
            has_sched = data['scheduled'] > 0
            sched_str = ("✓ نعم" if has_sched else "✕ لا") if is_ar else ("✓ Yes" if has_sched else "✕ No")
            sched_badge = QLabel(sched_str)
            sched_badge.setAlignment(Qt.AlignCenter)
            sched_badge.setFixedSize(65, 26)
            if has_sched:
                sched_badge.setStyleSheet("background-color: #064E3B; color: #34D399; border: 1px solid #059669; border-radius: 6px; font-weight: bold; font-size: 11px;")
            else:
                sched_badge.setStyleSheet("background-color: #381A1A; color: #F87171; border: 1px solid #DC2626; border-radius: 6px; font-weight: bold; font-size: 11px;")
            
            sched_wrap = QWidget()
            sw_layout = QHBoxLayout(sched_wrap)
            sw_layout.setContentsMargins(0, 0, 0, 0)
            sw_layout.addWidget(sched_badge, 0, Qt.AlignCenter)

            # Col 5: Git Sync Status Badge
            cat_synced = is_category_synced(cat_name, unsynced_set)
            if cat_synced:
                st_text = "🟢 متزامنة" if is_ar else "🟢 Synced"
                st_style = "color: #10B981; font-weight: bold; font-size: 12px;"
                st_tip = "جميع ملاحظات وملفات هذه الفئة متزامنة ومرفوعة بالكامل على GitHub" if is_ar else "All notes and files in this category are fully synced with GitHub"
            else:
                st_text = "🔴 غير متزامنة" if is_ar else "🔴 Unsynced"
                st_style = "color: #EF4444; font-weight: bold; font-size: 12px;"
                st_tip = "توجد تعديلات محليّة أو ملاحظات جديدة لم يتم رفعها لـ GitHub بعد" if is_ar else "Local changes or new notes pending push to GitHub"

            st_badge = QLabel(st_text)
            st_badge.setAlignment(Qt.AlignCenter)
            st_badge.setStyleSheet(st_style)
            st_badge.setToolTip(st_tip)

            st_wrap = QWidget()
            stw_layout = QHBoxLayout(st_wrap)
            stw_layout.setContentsMargins(0, 0, 0, 0)
            stw_layout.addWidget(st_badge, 0, Qt.AlignCenter)

            col0_widget.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            v_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            n_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            sched_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            st_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            self.tree.setItemWidget(item, 1, col0_widget)
            self.tree.setItemWidget(item, 2, v_lbl)
            self.tree.setItemWidget(item, 3, n_lbl)
            self.tree.setItemWidget(item, 4, sched_wrap)
            self.tree.setItemWidget(item, 5, st_wrap)

            # Col 6: Actions Bar (4 Icon Buttons)
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(6)
            action_layout.setAlignment(Qt.AlignCenter)

            def create_action_btn(icon_str, bg, border, fg, command, tooltip):
                b = QPushButton(icon_str)
                b.setToolTip(tooltip)
                b.setFixedSize(32, 32)
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg};
                        border: 1px solid {border};
                        color: {fg};
                        border-radius: 6px;
                        font-size: 14px;
                    }}
                    QPushButton:hover {{
                        background-color: {border};
                        color: #FFFFFF;
                    }}
                """)
                if command:
                    b.clicked.connect(command)
                return b

            btn_pin = create_action_btn("📌", "#382F0D", "#D97706", "#F59E0B", lambda checked, c=cat_name: self.on_toggle_pin_direct(c), "تثبيت / إلغاء تثبيت")
            btn_ren = create_action_btn("✏️", "#0F2942", "#0E639C", "#38BDF8", lambda checked, c=cat_name: self.on_rename_direct(c), "إعادة تسمية")
            btn_exp = create_action_btn("📦", "#281A45", "#6D28D9", "#C084FC", lambda checked, c=cat_name: self.on_export_direct(c), "تصدير كـ ZIP")
            btn_del = create_action_btn("🗑️", "#381212", "#C9302C", "#F87171", lambda checked, c=cat_name: self.on_delete_direct(c), "حذف الفئة")

            action_layout.addWidget(btn_pin)
            action_layout.addWidget(btn_ren)
            action_layout.addWidget(btn_exp)
            action_layout.addWidget(btn_del)

            self.tree.setItemWidget(item, 6, action_widget)

    def get_selection(self, quiet=False):
        items = self.tree.selectedItems()
        if not items:
            if not quiet:
                QMessageBox.warning(self, "تحذير", "يُرجى تحديد فئة من القائمة أولاً!")
            return None
        return items[0].data(0, Qt.UserRole)

    def open_notes_list_for_cat(self, cat_name):
        if not cat_name:
            return
        from ui_list_notes import show_notes_list_window
        from ui_view_note import show_note_view_window
        while True:
            action, filepath = show_notes_list_window(filter_cat=cat_name)
            if action == "OPEN" and filepath and os.path.exists(filepath):
                show_note_view_window(filepath)
            elif action == "NEW":
                from ui_create_note import show_create_note_window
                fp = show_create_note_window(default_cat=cat_name)
                if fp:
                    self.trigger_instant_bg_sync()
            elif action == "EDIT" and filepath and os.path.exists(filepath):
                show_note_view_window(filepath)
            elif action == "DELETE" and filepath:
                from note_manager import archive_note
                archive_note(filepath)
                self.trigger_instant_bg_sync()
            else:
                break
        self.populate_tree()

    def on_open(self, item=None):
        if item and hasattr(item, 'data'):
            cat = item.data(0, Qt.UserRole)
        else:
            cat = self.get_selection(quiet=True)
        if cat:
            self.open_notes_list_for_cat(cat)

    def on_create_category(self):
        text, ok = QInputDialog.getText(self, "📁 إنشاء فئة جديدة", "أدخل اسم الفئة:")
        if ok and text.strip():
            new_n = text.strip()
            get_category_media_dir(new_n)
            self.populate_tree()
            QMessageBox.information(self, "تم إنشاء الفئة", f"✅ تم إنشاء الفئة '{new_n}' بنجاح!")
            self.trigger_instant_bg_sync()

    def on_export_direct(self, cat):
        cat_dir = os.path.join(NOTES_PATH, cat)
        if not os.path.exists(cat_dir):
            QMessageBox.warning(self, "خطأ", f"مجلد الفئة '{cat}' غير موجود.")
            return

        default_dir = os.path.expanduser("~/Downloads")
        if not os.path.exists(default_dir):
            default_dir = os.path.expanduser("~")
            
        default_file = os.path.join(default_dir, f"{cat}_export_{time.strftime('%Y%m%d_%H%M%S')}.zip")
        
        options = QFileDialog.Options()
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            f"📦 تصدير الفئة '{cat}' كـ ZIP",
            default_file,
            "ZIP Archives (*.zip);;All Files (*)",
            options=options
        )

        if not save_path:
            return

        try:
            if os.path.isdir(save_path):
                save_path = os.path.join(save_path, f"{cat}_export_{time.strftime('%Y%m%d_%H%M%S')}.zip")
            elif not save_path.endswith(".zip"):
                save_path += ".zip"

            out_dir = os.path.dirname(save_path)
            if not os.access(out_dir, os.W_OK):
                QMessageBox.critical(
                    self,
                    "خطأ تصريح الوصول (Permission Denied)",
                    f"⛔ تعذر التصدير! المجلد المستهدف للـ ZIP غير قابل للكتابة:\n{out_dir}\n\nيُرجى اختيار مجلد تملك تصريح الكتابة فيه (مثل مجلد التنزيلات ~/Downloads)."
                )
                return

            QApplication.setOverrideCursor(Qt.WaitCursor)

            notes_count = 0
            tasks_count = 0
            scripts_count = 0
            attachments_count = 0
            skipped_files = 0

            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(cat_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        try:
                            arcname = os.path.relpath(full_path, start=os.path.dirname(cat_dir))
                            zipf.write(full_path, arcname)

                            if file.endswith('.md'):
                                try:
                                    ndata = parse_note_file(full_path)
                                    ntype = ndata.get('type', 'Note')
                                    if ntype == 'Task': tasks_count += 1
                                    elif ntype == 'Script': scripts_count += 1
                                    else: notes_count += 1
                                except Exception:
                                    notes_count += 1
                            else:
                                attachments_count += 1
                        except (PermissionError, OSError):
                            skipped_files += 1

            QApplication.restoreOverrideCursor()

            msg = (
                f"✅ تم تصدير الفئة '{cat}' بنجاح!\n\n"
                f"📊 ملخص الفئة المصدّرة:\n"
                f"📄 الملاحظات: {notes_count}\n"
                f"📊 المهام: {tasks_count}\n"
                f"🚀 السكريبتات والأتمتة: {scripts_count}\n"
                f"📎 المرفقات والوسائط: {attachments_count}\n"
            )
            if skipped_files > 0:
                msg += f"⚠️ ملفات تم تخطيها بسبب التصاريح: {skipped_files}\n"
            msg += f"\n📦 موقع الملف: {save_path}"

            QMessageBox.information(self, "تم التصدير بنجاح", msg)
        except PermissionError:
            try: QApplication.restoreOverrideCursor()
            except: pass
            QMessageBox.critical(
                self,
                "خطأ تصريح (Permission Denied)",
                f"⛔ تعذر إنشاء ملف الـ ZIP في هذا المسار بسبب تصاريح النظام:\n{save_path}\n\nيُرجى اختيار مكان آخر مثل مجلد التنزيلات (Downloads) أو سطح المكتب."
            )
        except Exception as e:
            try: QApplication.restoreOverrideCursor()
            except: pass
            QMessageBox.critical(self, "خطأ في التصدير", f"تعذر تصدير الفئة: {e}")

    def on_global_export(self):
        try:
            default_dir = os.path.expanduser("~/Downloads")
            if not os.path.exists(default_dir):
                default_dir = os.path.expanduser("~")
                
            default_file = os.path.join(default_dir, f"devnotes_full_export_{time.strftime('%Y%m%d_%H%M%S')}.zip")
            
            options = QFileDialog.Options()
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "📦 التصدير الكلي الشامل (All Categories, Notes, Tasks & Scripts)",
                default_file,
                "ZIP Archives (*.zip);;All Files (*)",
                options=options
            )

            if not save_path:
                return

            if os.path.isdir(save_path):
                save_path = os.path.join(save_path, f"devnotes_full_export_{time.strftime('%Y%m%d_%H%M%S')}.zip")
            elif not save_path.endswith(".zip"):
                save_path += ".zip"

            out_dir = os.path.dirname(save_path)
            if not os.access(out_dir, os.W_OK):
                QMessageBox.critical(
                    self,
                    "خطأ تصريح الوصول (Permission Denied)",
                    f"⛔ تعذر التصدير! المجلد المستهدف للـ ZIP غير قابل للكتابة:\n{out_dir}\n\nيُرجى اختيار مجلد تملك تصريح الكتابة فيه (مثل مجلد التنزيلات ~/Downloads)."
                )
                return

            QApplication.setOverrideCursor(Qt.WaitCursor)

            notes_count = 0
            tasks_count = 0
            scripts_count = 0
            attachments_count = 0
            skipped_files = 0
            categories_set = set()

            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 1. Archive everything inside notes/ directory (categories, notes, tasks, scripts, media)
                if os.path.exists(NOTES_PATH):
                    for root, dirs, files in os.walk(NOTES_PATH):
                        for file in files:
                            full_path = os.path.join(root, file)
                            try:
                                rel_path = os.path.relpath(full_path, start=NOTES_PATH)
                                arcname = os.path.join("notes", rel_path)
                                zipf.write(full_path, arcname)

                                if file.endswith('.md'):
                                    try:
                                        ndata = parse_note_file(full_path)
                                        ntype = ndata.get('type', 'Note')
                                        if ntype == 'Task': tasks_count += 1
                                        elif ntype == 'Script': scripts_count += 1
                                        else: notes_count += 1
                                        categories_set.add(ndata.get('category', 'general'))
                                    except Exception:
                                        notes_count += 1
                                else:
                                    attachments_count += 1
                            except (PermissionError, OSError):
                                skipped_files += 1

                # 2. Archive everything inside archive/ directory
                if os.path.exists(ARCHIVE_PATH):
                    for root, dirs, files in os.walk(ARCHIVE_PATH):
                        for file in files:
                            full_path = os.path.join(root, file)
                            try:
                                rel_path = os.path.relpath(full_path, start=ARCHIVE_PATH)
                                arcname = os.path.join("archive", rel_path)
                                zipf.write(full_path, arcname)
                            except (PermissionError, OSError):
                                skipped_files += 1

            QApplication.restoreOverrideCursor()
            cats_count = len(categories_set)

            msg = (
                f"✅ تم التصدير الكلي الشامل بنجاح!\n\n"
                f"📊 ملخص البيانات المصدّرة بالكامل:\n"
                f"📁 الفئات: {cats_count}\n"
                f"📄 الملاحظات: {notes_count}\n"
                f"📊 المهام (Kanban): {tasks_count}\n"
                f"🚀 السكريبتات والأتمتة: {scripts_count}\n"
                f"📎 المرفقات والوسائط: {attachments_count}\n"
            )
            if skipped_files > 0:
                msg += f"⚠️ ملفات تم تخطيها بسبب التصاريح: {skipped_files}\n"
            msg += f"\n📦 مسار أرشيف ZIP الكامل:\n{save_path}"

            QMessageBox.information(self, "التصدير الكلي الشامل", msg)

        except PermissionError:
            try: QApplication.restoreOverrideCursor()
            except: pass
            QMessageBox.critical(
                self,
                "خطأ تصريح (Permission Denied)",
                f"⛔ تعذر إنشاء ملف الـ ZIP في هذا المسار بسبب تصاريح النظام:\n{save_path}\n\nيُرجى اختيار مكان آخر مثل مجلد التنزيلات (Downloads) أو سطح المكتب."
            )
        except Exception as e:
            try: QApplication.restoreOverrideCursor()
            except: pass
            QMessageBox.critical(self, "خطأ في التصدير", f"تعذر إكمال التصدير الكلي: {e}")

    def show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        self.tree.setCurrentItem(item)
        
        cat = item.data(0, Qt.UserRole)
        
        menu = QMenu(self)
        
        _, pinned_cats = get_categories_data()
        pin_label = "📌 Unpin" if cat in pinned_cats else "📌 Pin"
        
        menu.addAction(pin_label, lambda: self.on_toggle_pin_direct(cat))
        menu.addAction("✏️ Rename", lambda: self.on_rename_direct(cat))
        menu.addAction("📦 Export ZIP", lambda: self.on_export_direct(cat))
        menu.addSeparator()
        menu.addAction("🗑️ Delete", lambda: self.on_delete_direct(cat))
        
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def on_sync(self):
        sync_notes_gui()
        self.populate_tree()

    def on_new_task(self):
        fp = show_create_note_window(default_cat="tasks", default_type="Task", parent=self)
        if fp:
            self.refresh_kanban_board()
            self.populate_tree()
            self.trigger_instant_bg_sync()


def show_categories_window():
    dlg = CategoriesDialog()
    dlg.exec_()
    return dlg.result_action, dlg.result_val
