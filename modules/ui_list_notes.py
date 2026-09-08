import os
import sys
import threading

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QWidget,
    QProgressBar, QFrame, QStackedWidget, QScrollArea, QGridLayout, QShortcut
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QIcon, QKeySequence

from config import (
    NOTES_PATH, BG_MAIN, BG_CARD, FG_GREEN, FG_TEXT, FG_MUTED,
    BTN_BLUE, BTN_AMBER, BTN_RED, BTN_PURPLE, BTN_TEAL, BTN_GRAY
)
from utils import center_window, parse_note_file, update_frontmatter_keys
from ui_common import apply_rtl_to_widget
from note_manager import get_all_notes, archive_note
from git_sync import sync_notes_cli, sync_notes_gui, get_git_unsynced_rel_paths, is_file_synced
from i18n import tr, get_lang, set_lang

# Palette Colors matching mockup
CLR_MAIN_BG = "#0D0F17"
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

class NotesListDialog(QDialog):
    def __init__(self, filter_cat=None, search_query="", only_scheduled_scripts=False):
        super().__init__()
        from theme import get_theme_colors
        c = get_theme_colors()
        is_ar = (get_lang() == 'ar')

        self.result_action = ""
        self.result_file = ""
        self.filter_cat = filter_cat
        self.only_scheduled_scripts = only_scheduled_scripts
        
        if only_scheduled_scripts:
            self.win_title = "السكربتات والمهام المجدولة 👨‍💻" if is_ar else "Scheduled Scripts & Tasks 👨‍💻"
            self.sub_title = "عرض وإدارة جميع السكربتات والمهام التلقائية" if is_ar else "View and manage all automated scripts and tasks"
        elif filter_cat:
            self.win_title = f"📁 الملاحظات | فئة: {filter_cat}" if is_ar else f"📁 Notes | Category: {filter_cat}"
            self.sub_title = f"عرض جميع الملاحظات والملفات المرفقة التابعة لفئة '{filter_cat}'" if is_ar else f"Viewing all notes and attached files in '{filter_cat}'"
        else:
            self.win_title = "📝 جميع الملاحظات والملفات" if is_ar else "📝 All Notes & Files"
            self.sub_title = "عرض وتصفح جميع الملاحظات المحفوظة" if is_ar else "Browse all saved notes"
            
        if is_ar:
            self.setLayoutDirection(Qt.RightToLeft)
        else:
            self.setLayoutDirection(Qt.LeftToRight)

        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )

        self.setWindowTitle(self.win_title)
        self.resize(980, 640)
        self.setMinimumSize(880, 560)
        
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
                height: 52px;
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
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 1. Header Bar (Clean, no sidebar, no duplicated sync/git buttons)
        top_bar = QHBoxLayout()
        
        title_box = QVBoxLayout()
        h_title = QLabel(self.win_title)
        h_title.setStyleSheet("color: #FFFFFF; font-size: 20px; font-weight: bold;")
        h_sub = QLabel(self.sub_title)
        h_sub.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 12px;")
        title_box.addWidget(h_title)
        title_box.addWidget(h_sub)
        
        top_bar.addLayout(title_box)
        top_bar.addStretch()
        
        btn_new_note = QPushButton("+ إنشاء ملاحظة جديدة")
        btn_new_note.setCursor(Qt.PointingHandCursor)
        btn_new_note.setStyleSheet(f"""
            QPushButton {{
                background-color: {CLR_PURPLE};
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
        btn_new_note.clicked.connect(self.on_new)
        top_bar.addWidget(btn_new_note)
        
        user_chip = QLabel("👤 Bashar ▾")
        user_chip.setStyleSheet(f"color: #94A3B8; font-weight: bold; font-size: 13px; padding: 6px 12px; background: #161926; border: 1px solid {CLR_BORDER}; border-radius: 20px;")
        top_bar.addWidget(user_chip)
        
        layout.addLayout(top_bar)
        
        # 2. Search & Filter Sub-Bar
        sub_bar = QHBoxLayout()
        
        self.search_ent = QLineEdit(search_query)
        self.search_ent.setPlaceholderText("بحث في ملاحظات هذه الفئة... 🔍")
        self.search_ent.textChanged.connect(lambda: self.populate_tree())
        apply_rtl_to_widget(self.search_ent)

        self.sort_cb = QComboBox()
        self.sort_cb.addItems(["ترتيب حسب: الزيارات 👁", "ترتيب حسب: العنوان 📝", "ترتيب حسب: التاريخ 📅"])
        self.sort_cb.currentTextChanged.connect(lambda: self.populate_tree())
        
        self.view_mode = "list"  # "list" or "grid"
        self.btn_view_mode = QPushButton("⊞")
        self.btn_view_mode.setFixedSize(38, 38)
        self.btn_view_mode.setCursor(Qt.PointingHandCursor)
        self.btn_view_mode.setToolTip("عرض على شكل مربعات / بطاقات (Grid View)")
        self.btn_view_mode.setStyleSheet(f"""
            QPushButton {{
                background-color: #161926;
                color: #FFFFFF;
                border: 1px solid {CLR_BORDER};
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {CLR_PURPLE};
                border: 1px solid {CLR_PURPLE};
            }}
        """)
        self.btn_view_mode.clicked.connect(self.toggle_view_mode)
        
        sub_bar.addWidget(self.search_ent, 1)
        sub_bar.addWidget(self.sort_cb)
        sub_bar.addWidget(self.btn_view_mode)
        
        layout.addLayout(sub_bar)

        # 3. Stacked View Container (List vs Grid)
        self.stack = QStackedWidget()

        # List View (Tree Table - واحد تحت واحد)
        self.tree = QTreeWidget()
        if is_ar:
            self.tree.setLayoutDirection(Qt.RightToLeft)
        else:
            self.tree.setLayoutDirection(Qt.LeftToRight)
        headers = ["File", "اسم الفئة 📁", "نوع الملاحظة 🏷️", "عنوان الملاحظة 📝", "الزيارات 👁", "المجدولة ⏰", "الحالة ⚡", "الإجراءات 🛠️"]
        if self.only_scheduled_scripts:
            headers[3] = "اسم السكربت 🚀"
        self.tree.setHeaderLabels(headers)
        self.tree.hideColumn(0)

        from PyQt5.QtWidgets import QHeaderView
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignCenter)

        self.tree.setColumnWidth(1, 110)  # اسم الفئة
        self.tree.setColumnWidth(2, 110)  # نوع الملاحظة (ملاحظة / سكريبت / مهمة)
        self.tree.setColumnWidth(3, 240)  # عنوان الملاحظة / السكربت
        self.tree.setColumnWidth(4, 80)   # الزيارات
        self.tree.setColumnWidth(5, 140)  # المجدولة
        self.tree.setColumnWidth(6, 110)  # الحالة
        self.tree.setColumnWidth(7, 130)  # الإجراءات

        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        header.setSectionResizeMode(6, QHeaderView.Interactive)
        header.setSectionResizeMode(7, QHeaderView.Fixed)

        def on_note_click(item, col):
            if col != 7:
                self.on_open(item)

        self.tree.itemClicked.connect(on_note_click)
        self.tree.itemDoubleClicked.connect(on_note_click)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.stack.addWidget(self.tree)

        # Grid View (Cards Scroll Area - مربعات)
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setStyleSheet(f"background-color: {CLR_MAIN_BG}; border: none;")

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet(f"background-color: {CLR_MAIN_BG};")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(12)
        self.grid_scroll.setWidget(self.grid_container)
        self.stack.addWidget(self.grid_scroll)

        layout.addWidget(self.stack, 1)

        # 4. Footer Pagination Bar
        footer = QHBoxLayout()
        self.footer_count = QLabel("عرض الملاحظات")
        self.footer_count.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 12px;")
        
        page_btn = QPushButton("1")
        page_btn.setFixedSize(30, 30)
        page_btn.setStyleSheet(f"background-color: {CLR_PURPLE}; color: white; border-radius: 6px; font-weight: bold;")
        
        footer.addWidget(page_btn)
        footer.addStretch()
        footer.addWidget(self.footer_count)
        footer.addStretch()
        
        page_size_lbl = QLabel("عرض 10 ▾")
        page_size_lbl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 12px; background: #161926; padding: 4px 10px; border: 1px solid {CLR_BORDER}; border-radius: 6px;")
        footer.addWidget(page_size_lbl)
        
        layout.addLayout(footer)
        
        # Keyboard Shortcuts for Sorting & View Mode
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
        self.sc_view.activated.connect(self.toggle_view_mode)

        self.populate_tree()
        center_window(self, 980, 640)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_B:
            if (event.modifiers() & Qt.ControlModifier) or (event.modifiers() & Qt.AltModifier):
                self.on_shortcut_sort()
                event.accept()
                return
        elif event.key() == Qt.Key_V:
            if (event.modifiers() & Qt.ControlModifier) or (event.modifiers() & Qt.AltModifier):
                self.toggle_view_mode()
                event.accept()
                return
        super().keyPressEvent(event)

    def on_shortcut_sort(self):
        curr_idx = self.sort_cb.currentIndex()
        next_idx = (curr_idx + 1) % self.sort_cb.count()
        self.sort_cb.setCurrentIndex(next_idx)
        self.populate_tree()
        self.sort_cb.setFocus()
        self.sort_cb.showPopup()
        from PyQt5.QtWidgets import QToolTip
        from PyQt5.QtGui import QCursor
        QToolTip.showText(QCursor.pos(), f"↕️ {self.sort_cb.currentText()}", self)

    def toggle_view_mode(self):
        if self.view_mode == "list":
            self.view_mode = "grid"
            self.btn_view_mode.setText("☰")
            self.btn_view_mode.setToolTip("عرض على شكل قائمة / واحد تحت واحد (List View)")
            self.stack.setCurrentIndex(1)
        else:
            self.view_mode = "list"
            self.btn_view_mode.setText("⊞")
            self.btn_view_mode.setToolTip("عرض على شكل مربعات / بطاقات (Grid View)")
            self.stack.setCurrentIndex(0)
        self.populate_tree()

    def create_note_grid_card(self, item_data, unsynced_set):
        filepath = item_data['file']
        title_str = item_data['title']
        is_synced = is_file_synced(filepath, unsynced_set)

        is_script = item_data.get('type') == 'Script' or bool(item_data.get('scheduled_exec') or str(item_data.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1'])
        is_task = item_data.get('type') == 'Task'

        if is_script:
            icon_prefix = "🚀"
            type_txt = "Script"
            type_bg, type_fg = "#281A45", "#C084FC"
        elif is_task:
            icon_prefix = "📋"
            type_txt = "Task"
            type_bg, type_fg = "#453517", "#FBBF24"
        else:
            icon_prefix = "📝"
            type_txt = "Note"
            type_bg, type_fg = "#0F2942", "#38BDF8"

        card = QFrame()
        card.setCursor(Qt.PointingHandCursor)
        card.mousePressEvent = lambda event, fp=filepath: self.on_open_direct(fp)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CLR_CARD_BG};
                border: 1px solid {CLR_BORDER};
                border-radius: 10px;
                padding: 6px;
            }}
            QFrame:hover {{
                border: 1px solid {CLR_PURPLE};
                background-color: #1B1E2F;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(8)

        # Top Bar: Type + Sync Badge
        top_h = QHBoxLayout()
        top_h.setSpacing(6)

        tp_badge = QLabel(f"{icon_prefix} {type_txt}")
        tp_badge.setStyleSheet(f"background-color: {type_bg}; color: {type_fg}; border-radius: 4px; padding: 2px 6px; font-weight: bold; font-size: 10px;")
        top_h.addWidget(tp_badge)

        sync_badge = QLabel("🟢 متزامنة" if is_synced else "🔴 غير متزامنة")
        sync_badge.setToolTip("مزامنة بالكامل مع GitHub" if is_synced else "غير متزامنة بعد مع GitHub")
        if is_synced:
            sync_badge.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
        else:
            sync_badge.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 11px;")
        
        top_h.addWidget(sync_badge)
        top_h.addStretch()

        c_layout.addLayout(top_h)

        # Title
        lbl_t = QLabel(title_str)
        lbl_t.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 14px;")
        lbl_t.setWordWrap(True)
        c_layout.addWidget(lbl_t)

        # Body Preview Snippet
        body_txt = item_data.get('body', '').strip()
        snippet = (body_txt[:90] + "...") if len(body_txt) > 90 else (body_txt or "لا يوجد محتوى معاينة")
        lbl_b = QLabel(snippet)
        lbl_b.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 11px;")
        lbl_b.setWordWrap(True)
        c_layout.addWidget(lbl_b, 1)

        # Footer Info (Category & Visits)
        info_h = QHBoxLayout()
        cat_lbl = QLabel(f"📁 {item_data.get('category', 'عام')}")
        cat_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")
        vis_lbl = QLabel(f"👁 {item_data.get('access', 0)}")
        vis_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")

        info_h.addWidget(cat_lbl)
        info_h.addStretch()
        info_h.addWidget(vis_lbl)
        c_layout.addLayout(info_h)

        # Action Buttons
        act_h = QHBoxLayout()
        act_h.setSpacing(6)

        btn_v = QPushButton("📖 فتح")
        btn_v.setCursor(Qt.PointingHandCursor)
        btn_v.setStyleSheet("background: #0F2942; color: #38BDF8; border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 11px;")
        btn_v.clicked.connect(lambda checked, fp=filepath: self.on_open_direct(fp))

        btn_e = QPushButton("✏️ تعديل")
        btn_e.setCursor(Qt.PointingHandCursor)
        btn_e.setStyleSheet("background: #1E3F35; color: #98C379; border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 11px;")
        btn_e.clicked.connect(lambda checked, fp=filepath: self.on_edit_direct(fp))

        btn_d = QPushButton("🗑️")
        btn_d.setCursor(Qt.PointingHandCursor)
        btn_d.setStyleSheet("background: #381212; color: #F87171; border-radius: 4px; padding: 4px 8px; font-weight: bold; font-size: 11px;")
        btn_d.clicked.connect(lambda checked, fp=filepath: self.on_delete_direct(fp))

        act_h.addWidget(btn_v)
        act_h.addWidget(btn_e)
        act_h.addStretch()
        act_h.addWidget(btn_d)
        c_layout.addLayout(act_h)

        return card

    def populate_tree(self, *args):
        is_ar = (get_lang() == 'ar')
        self.tree.clear()
        
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        query = self.search_ent.text().strip().lower()
        sort_txt = self.sort_cb.currentText()
        if "العنوان" in sort_txt or "الاسم" in sort_txt or "Name" in sort_txt or "Title" in sort_txt:
            sort_key_type = "name"
        elif "التاريخ" in sort_txt or "Date" in sort_txt:
            sort_key_type = "date"
        else:
            sort_key_type = "access"

        current_notes = get_all_notes(
            filter_cat=self.filter_cat,
            search_query=query,
            only_scheduled_scripts=self.only_scheduled_scripts,
            sort_by=sort_key_type
        )
        unsynced_set = get_git_unsynced_rel_paths()
        
        self.footer_count.setText(f"عرض 1 - {len(current_notes)} من {len(current_notes)} عناصر")

        cols = 2
        for idx, item_data in enumerate(current_notes):
            row = idx // cols
            col = idx % cols
            card = self.create_note_grid_card(item_data, unsynced_set)
            self.grid_layout.addWidget(card, row, col)

        for item_data in current_notes:
            filepath = item_data['file']
            title_str = item_data['title']
            is_synced = is_file_synced(filepath, unsynced_set)
            
            item = QTreeWidgetItem(["", "", "", "", "", "", "", ""])
            item.setText(0, filepath)
            self.tree.addTopLevelItem(item)

            # Col 1: اسم الفئة 📁
            cat_lbl = QLabel(f"📁 {item_data.get('category', 'عام')}")
            cat_lbl.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 12px;")
            self.tree.setItemWidget(item, 1, cat_lbl)

            # Col 2: نوع الملاحظة 🏷️ (ملاحظة / سكريبت / مهمة)
            raw_type = item_data.get('type', 'Note')
            is_script = raw_type == 'Script' or bool(item_data.get('scheduled_exec') or str(item_data.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1'])
            is_task = raw_type == 'Task'

            if is_script:
                type_str = "🚀 سكريبت"
                type_clr = "#C084FC"
                type_bg = "#281A45"
            elif is_task:
                type_str = "📋 مهمة"
                type_clr = "#FBBF24"
                type_bg = "#453517"
            else:
                type_str = "📝 ملاحظة"
                type_clr = "#38BDF8"
                type_bg = "#0F2942"

            tp_lbl = QLabel(type_str)
            tp_lbl.setAlignment(Qt.AlignCenter)
            tp_lbl.setStyleSheet(f"background-color: {type_bg}; color: {type_clr}; border-radius: 6px; padding: 3px 8px; font-weight: bold; font-size: 11px;")
            
            tp_wrap = QWidget()
            tp_layout = QHBoxLayout(tp_wrap)
            tp_layout.setContentsMargins(0, 0, 0, 0)
            tp_layout.addWidget(tp_lbl, 0, Qt.AlignCenter)
            self.tree.setItemWidget(item, 2, tp_wrap)

            # Col 3: عنوان الملاحظة 📝 / اسم السكربت 🚀
            if is_script:
                icon_prefix = "🚀"
            elif is_task:
                icon_prefix = "📋"
            else:
                icon_prefix = "📝"

            t_lbl = QLabel(f"{icon_prefix}  {title_str}")
            t_lbl.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 13px;")
            self.tree.setItemWidget(item, 3, t_lbl)

            # Col 4: الزيارات 👁
            v_lbl = QLabel(f"👁 {item_data.get('access', 0)}")
            v_lbl.setAlignment(Qt.AlignCenter)
            v_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: bold;")
            self.tree.setItemWidget(item, 4, v_lbl)

            # Col 5: المجدولة ⏰
            r = item_data.get('reminder')
            s = item_data.get('scheduled_exec')
            b = str(item_data.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1']
            evt_c = item_data.get('event_category')
            evt_t = item_data.get('event_trigger')

            t_arr = []
            if s: t_arr.append(f"⏰ {s}")
            if b: t_arr.append("🚀 إقلاع")
            if evt_t and evt_c != 'None': t_arr.append(f"⚡ {evt_t}")
            if r: t_arr.append(f"🔔 {r}")

            t_val = " | ".join(t_arr) if t_arr else "غير مجدولة"
            tm_lbl = QLabel(t_val)
            if t_arr:
                tm_lbl.setStyleSheet("color: #FBBF24; font-size: 12px; font-weight: bold;")
            else:
                tm_lbl.setStyleSheet("color: #64748B; font-size: 12px;")
            self.tree.setItemWidget(item, 5, tm_lbl)

            # Col 6: الحالة ⚡ (متزامنة / غير متزامنة)
            if is_synced:
                st_txt = "🟢 متزامنة" if is_ar else "🟢 Synced"
                st_clr = "#10B981"
                st_tip = "الملاحظة متزامنة بالكامل مع GitHub" if is_ar else "Note is fully synced with GitHub"
            else:
                st_txt = "🔴 غير متزامنة" if is_ar else "🔴 Unsynced"
                st_clr = "#EF4444"
                st_tip = "الملاحظة غير متزامنة بعد مع GitHub" if is_ar else "Note is not synced yet with GitHub"

            sync_lbl = QLabel(st_txt)
            sync_lbl.setAlignment(Qt.AlignCenter)
            sync_lbl.setToolTip(st_tip)
            sync_lbl.setStyleSheet(f"color: {st_clr}; font-weight: bold; font-size: 12px;")

            sync_wrap = QWidget()
            sync_layout = QHBoxLayout(sync_wrap)
            sync_layout.setContentsMargins(0, 0, 0, 0)
            sync_layout.addWidget(sync_lbl, 0, Qt.AlignCenter)

            cat_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            tp_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            t_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            v_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            tm_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            sync_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)

            self.tree.setItemWidget(item, 1, cat_lbl)
            self.tree.setItemWidget(item, 2, tp_wrap)
            self.tree.setItemWidget(item, 3, t_lbl)
            self.tree.setItemWidget(item, 4, v_lbl)
            self.tree.setItemWidget(item, 5, tm_lbl)
            self.tree.setItemWidget(item, 6, sync_wrap)

            # Col 7: الإجراءات 🛠️
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(6)
            action_layout.setAlignment(Qt.AlignCenter)

            def create_action_btn(icon_str, bg, border, fg, command, tooltip):
                b = QPushButton(icon_str)
                b.setToolTip(tooltip)
                b.setFixedSize(30, 30)
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg};
                        border: 1px solid {border};
                        color: {fg};
                        border-radius: 6px;
                        font-size: 13px;
                    }}
                    QPushButton:hover {{
                        background-color: {border};
                        color: #FFFFFF;
                    }}
                """)
                if command:
                    b.clicked.connect(command)
                return b

            btn_view = create_action_btn("📖", "#0F2942", "#0E639C", "#38BDF8", lambda checked, fp=filepath: self.on_open_direct(fp), "عرض الملاحظة")
            btn_edit = create_action_btn("✏️", "#1E3F35", "#2B5B4C", "#98C379", lambda checked, fp=filepath: self.on_edit_direct(fp), "تعديل الملاحظة")
            btn_del = create_action_btn("🗑️", "#381212", "#C9302C", "#F87171", lambda checked, fp=filepath: self.on_delete_direct(fp), "حذف/أرشفة")

            action_layout.addWidget(btn_view)
            action_layout.addWidget(btn_edit)
            action_layout.addWidget(btn_del)

            self.tree.setItemWidget(item, 7, action_widget)

    def get_selection(self, quiet=False):
        items = self.tree.selectedItems()
        if not items:
            if not quiet:
                QMessageBox.warning(self, "تحذير", "يُرجى تحديد ملاحظة من القائمة أولاً!")
            return None
        return items[0].text(0)

    def on_open(self, item=None):
        if isinstance(item, QTreeWidgetItem):
            f = item.text(0)
        else:
            f = self.get_selection(quiet=True)
        if f:
            self.on_open_direct(f)

    def on_open_direct(self, filepath):
        self.result_action = "OPEN"
        self.result_file = filepath
        self.accept()

    def on_edit_direct(self, filepath):
        self.result_action = "EDIT"
        self.result_file = filepath
        self.accept()

    def on_delete_direct(self, filepath):
        reply = QMessageBox.question(self, "تأكيد الحذف", "هل أنت تأكد من أنك تريد أرشفة/حذف هذه الملاحظة؟",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.result_action = "DELETE"
            self.result_file = filepath
            self.accept()

    def on_new(self):
        self.result_action = "NEW"
        self.result_file = ""
        self.accept()

    def on_edit(self):
        f = self.get_selection()
        if f:
            self.on_edit_direct(f)

    def on_delete(self):
        f = self.get_selection()
        if f:
            self.on_delete_direct(f)
                
    def on_toggle_script(self):
        f = self.get_selection()
        if f:
            n_data = parse_note_file(f)
            curr = str(n_data.get('script_enabled', 'true')).lower() in ['true', 'yes', '1']
            new_val = 'false' if curr else 'true'
            update_frontmatter_keys(f, {'script_enabled': new_val})
            self.populate_tree(self.search_ent.text())
            if new_val == 'true':
                QMessageBox.information(self, "مفعل", "✅ تم تفعيل السكربت التلقائي!")
            else:
                QMessageBox.information(self, "معطل", "⏸️ تم تعطيل السكربت التلقائي!")

    def show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        self.tree.setCurrentItem(item)
        
        f = self.get_selection(quiet=True)
        if not f: return
        
        n_data = parse_note_file(f)
        is_script = n_data.get('type') == 'Script' or bool(n_data.get('scheduled_exec') or str(n_data.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1'])
        is_enabled = str(n_data.get('script_enabled', 'true')).lower() in ['true', 'yes', '1']
        
        menu = QMenu(self)
        
        menu.addAction("📖 عرض / فتح", lambda: self.on_open_direct(f))
        menu.addAction("✏️ تعديل", lambda: self.on_edit_direct(f))
        
        if is_script:
            menu.addSeparator()
            if is_enabled:
                menu.addAction("⏸️ تعطيل السكربت", self.on_toggle_script)
            else:
                menu.addAction("▶️ تفعيل السكربت", self.on_toggle_script)
        
        menu.addSeparator()
        menu.addAction("🗑️ حذف", lambda: self.on_delete_direct(f))
        
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

def show_notes_list_window(filter_cat=None, search_query="", only_scheduled_scripts=False, parent=None):
    if parent:
        parent.hide()
    try:
        dlg = NotesListDialog(filter_cat, search_query, only_scheduled_scripts)
        dlg.exec_()
        return dlg.result_action, dlg.result_file
    finally:
        if parent:
            parent.show()
            parent.raise_()
            parent.activateWindow()
