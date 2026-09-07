import os
import datetime
import threading
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QScrollArea, QWidget, QFrame)
from PyQt5.QtCore import Qt

from config import BG_MAIN, BG_CARD, FG_GREEN, FG_TEXT, FG_MUTED, BTN_BLUE, BTN_AMBER, BTN_RED, BTN_GRAY
from utils import center_window, update_frontmatter_keys
from ui_common import apply_rtl_to_widget, get_common_qss, create_horizontal_button
from note_manager import get_all_tasks
from ui_view_note import show_note_view_window
from ui_create_note import show_create_note_window
from git_sync import sync_notes_cli
from i18n import tr

def create_scrollable_column(title, bg_color):
    col = QFrame()
    col.setStyleSheet(f"background-color: {BG_MAIN}; border: 1px solid #333;")
    layout = QVBoxLayout(col)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    
    header = QLabel(title)
    header.setAlignment(Qt.AlignCenter)
    header.setStyleSheet(f"background-color: {bg_color}; color: white; font-weight: bold; font-size: 14px; padding: 10px; border: none;")
    layout.addWidget(header)
    
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("border: none;")
    
    content = QWidget()
    content.setStyleSheet(f"background-color: {BG_MAIN};")
    content_layout = QVBoxLayout(content)
    content_layout.setAlignment(Qt.AlignTop)
    content_layout.setSpacing(10)
    scroll.setWidget(content)
    
    layout.addWidget(scroll)
    return col, content_layout

class KanbanBoardDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr('kanban_win_title'))
        self.resize(1100, 700)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(get_common_qss())
        
        main_layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        lbl = QLabel(tr('kanban_header'))
        lbl.setStyleSheet(f"color: {FG_GREEN}; font-weight: bold; font-size: 16px;")
        header.addWidget(lbl)
        header.addStretch()
        
        btn_new = create_horizontal_button(tr('btn_new_task'), "#008080", self.on_new_task, is_primary=True)
        btn_close = create_horizontal_button(tr('btn_close'), BTN_GRAY, self.reject)
        
        header.addWidget(btn_new)
        header.addWidget(btn_close)
        main_layout.addLayout(header)
        
        # Board
        board = QHBoxLayout()
        board.setSpacing(10)
        
        col_todo, self.layout_todo = create_scrollable_column(tr('col_todo'), "#2c2c2c")
        col_prog, self.layout_prog = create_scrollable_column(tr('col_in_progress'), "#3d3d00")
        col_done, self.layout_done = create_scrollable_column(tr('col_done'), "#003d14")
        
        board.addWidget(col_todo)
        board.addWidget(col_prog)
        board.addWidget(col_done)
        
        main_layout.addLayout(board, 1)
        
        self.refresh_board()
        center_window(self, 1100, 700)

    def on_new_task(self):
        show_create_note_window(default_cat="tasks", default_type="Task")
        self.refresh_board()

    def trigger_instant_bg_sync(self):
        def run_sync():
            try: sync_notes_cli()
            except: pass
        threading.Thread(target=run_sync, daemon=True).start()

    def move_task(self, filepath, new_status):
        update_frontmatter_keys(filepath, {'status': new_status})
        self.refresh_board()
        self.trigger_instant_bg_sync()

    def open_task(self, filepath):
        show_note_view_window(filepath)
        self.refresh_board()

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def refresh_board(self):
        self.clear_layout(self.layout_todo)
        self.clear_layout(self.layout_prog)
        self.clear_layout(self.layout_done)
        
        tasks = get_all_tasks()
        
        for t in tasks:
            status = t.get('status', 'todo').lower()
            if status == 'todo': parent_layout = self.layout_todo
            elif status == 'in_progress': parent_layout = self.layout_prog
            elif status == 'done': parent_layout = self.layout_done
            else: parent_layout = self.layout_todo
            
            self.build_task_card(parent_layout, t)

    def build_task_card(self, parent_layout, t):
        card = QFrame()
        card.setStyleSheet(f"background-color: {BG_CARD}; border: 1px solid #444; border-radius: 4px;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        
        # Priority mapping
        pri = t.get('priority', 'medium').lower()
        if pri == 'high':
            p_color, p_text = BTN_RED, "⬆️ HIGH"
        elif pri == 'low':
            p_color, p_text = BTN_GRAY, "⬇️ LOW"
        else:
            p_color, p_text = BTN_BLUE, "➖ MED"
            
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        
        lbl_pri = QLabel(p_text)
        lbl_pri.setStyleSheet(f"background-color: {p_color}; color: white; font-weight: bold; font-size: 10px; padding: 2px 5px; border-radius: 2px; border: none;")
        top_bar.addWidget(lbl_pri)
        top_bar.addStretch()
        
        if t.get('reminder'):
            lbl_rem = QLabel(f"⏰ {t['reminder']}")
            lbl_rem.setStyleSheet(f"color: {FG_MUTED}; font-size: 11px; border: none;")
            top_bar.addWidget(lbl_rem)
            
        card_layout.addLayout(top_bar)
        
        # Tags (Pills)
        tags = t.get('tags', '').strip()
        if tags:
            tag_layout = QHBoxLayout()
            tag_layout.setContentsMargins(0, 5, 0, 0)
            tag_layout.setSpacing(5)
            for tag in tags.split(','):
                tag = tag.strip()
                if tag:
                    lbl_tag = QLabel(f"{tag}")
                    lbl_tag.setStyleSheet("background-color: #3b6978; color: white; font-weight: bold; font-size: 10px; padding: 2px 5px; border-radius: 2px; border: none;")
                    tag_layout.addWidget(lbl_tag)
            tag_layout.addStretch()
            card_layout.addLayout(tag_layout)
            
        lbl_title = QLabel(t['title'])
        lbl_title.setWordWrap(True)
        lbl_title.setStyleSheet(f"color: {FG_TEXT}; font-weight: bold; font-size: 14px; border: none; padding-top: 5px;")
        apply_rtl_to_widget(lbl_title, t['title'])
        card_layout.addWidget(lbl_title)
        
        # Subtasks
        sub_total = t.get('subtasks_total', 0)
        sub_done = t.get('subtasks_done', 0)
        if sub_total > 0:
            prog_color = FG_GREEN if sub_done == sub_total else FG_MUTED
            lbl_sub = QLabel(f"☑️ Subtasks: {sub_done}/{sub_total}")
            lbl_sub.setStyleSheet(f"color: {prog_color}; font-weight: bold; font-size: 11px; border: none;")
            card_layout.addWidget(lbl_sub)
            
        # Due Date & Effort
        if t.get('due_date') or t.get('effort'):
            info_layout = QHBoxLayout()
            info_layout.setContentsMargins(0, 5, 0, 0)
            if t.get('due_date'):
                d_color = FG_MUTED
                try:
                    due_d = datetime.datetime.strptime(t['due_date'], "%Y-%m-%d").date()
                    now_d = datetime.date.today()
                    if due_d < now_d: d_color = "#ff4444"
                    elif due_d == now_d: d_color = "#ffaa00"
                except:
                    pass
                lbl_due = QLabel(f"📅 {t['due_date']}")
                lbl_due.setStyleSheet(f"color: {d_color}; font-weight: bold; font-size: 11px; border: none;")
                info_layout.addWidget(lbl_due)
                
            if t.get('effort'):
                lbl_eff = QLabel(f"⏳ {t['effort']}")
                lbl_eff.setStyleSheet(f"color: {FG_MUTED}; font-weight: bold; font-size: 11px; border: none;")
                info_layout.addWidget(lbl_eff)
                
            info_layout.addStretch()
            card_layout.addLayout(info_layout)
            
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 10, 0, 0)
        btn_bar.setSpacing(5)
        
        btn_open = create_horizontal_button("👁️ Open", "#3a3a3a", lambda: self.open_task(t['file']))
        btn_bar.addWidget(btn_open)
        
        st = t.get('status', 'todo').lower()
        if st == 'todo':
            btn_next = create_horizontal_button("Move to Progress ▶", "#3a3a3a", lambda: self.move_task(t['file'], 'in_progress'))
            btn_bar.addWidget(btn_next)
        elif st == 'in_progress':
            btn_prev = create_horizontal_button("◀ Back to Todo", "#3a3a3a", lambda: self.move_task(t['file'], 'todo'))
            btn_next = create_horizontal_button("Move to Done ▶", "#003d14", lambda: self.move_task(t['file'], 'done'))
            btn_bar.addWidget(btn_prev)
            btn_bar.addWidget(btn_next)
        elif st == 'done':
            btn_prev = create_horizontal_button("◀ Back to Progress", "#3a3a3a", lambda: self.move_task(t['file'], 'in_progress'))
            btn_bar.addWidget(btn_prev)
            
        btn_bar.addStretch()
        card_layout.addLayout(btn_bar)
        
        parent_layout.addWidget(card)

def show_kanban_board():
    dlg = KanbanBoardDialog()
    dlg.exec_()
