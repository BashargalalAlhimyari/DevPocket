import os
import sys
import time
import datetime
import shutil
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QComboBox, QTextEdit, 
                             QFileDialog, QMessageBox, QWidget, QGridLayout)
from PyQt5.QtCore import Qt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import NOTES_DIR, NOTES_PATH, get_category_dir, get_category_media_dir, get_tasks_dir, get_tasks_media_dir, BG_MAIN, BG_CARD, FG_GREEN, FG_TEXT, FG_MUTED, BTN_BLUE, BTN_RED, BTN_GRAY
from utils import center_window
from note_manager import get_categories_data
from voice_recorder import record_voice_dialog
from ui_common import get_common_qss, apply_rtl_to_widget, FONT_ARABIC, create_horizontal_button
from i18n import tr

class CreateNoteDialog(QDialog):
    def __init__(self, default_cat="general", default_type="Note"):
        super().__init__()
        self.saved_data = None
        self.attached_path = ""
        
        self.setWindowTitle(tr('create_dlg_title'))
        self.resize(720, 620)
        self.setMinimumSize(640, 520)
        self.setStyleSheet(get_common_qss())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        lbl = QLabel(tr('create_header'))
        lbl.setStyleSheet(f"color: {FG_GREEN}; font-weight: bold; font-size: 16px;")
        layout.addWidget(lbl)
        
        form_layout = QGridLayout()
        form_layout.setContentsMargins(0, 5, 0, 5)
        
        # Title
        lbl_title = QLabel(tr('lbl_title_input'))
        lbl_title.setStyleSheet(f"color: {FG_MUTED}; font-weight: bold;")
        self.title_ent = QLineEdit()
        apply_rtl_to_widget(self.title_ent)
        form_layout.addWidget(lbl_title, 0, 0)
        form_layout.addWidget(self.title_ent, 0, 1)
        
        # Category
        categories, _ = get_categories_data()
        existing_cats = set(categories.keys()) if categories else set()
        if not existing_cats:
            existing_cats.add("general")
        if default_cat and default_cat.lower() != "tasks":
            existing_cats.add(default_cat)
        
        self.lbl_cat = QLabel(tr('lbl_cat_input'))
        self.lbl_cat.setStyleSheet(f"color: {FG_MUTED}; font-weight: bold;")
        self.cat_cb = QComboBox()
        self.cat_cb.addItems(sorted(list(existing_cats)))
        target_cat = default_cat if (default_cat and default_cat in existing_cats) else (sorted(list(existing_cats))[0] if existing_cats else "general")
        self.cat_cb.setCurrentText(target_cat)
        
        form_layout.addWidget(self.lbl_cat, 1, 0)
        form_layout.addWidget(self.cat_cb, 1, 1)
        
        # Type
        lbl_type = QLabel(tr('lbl_type_input'))
        lbl_type.setStyleSheet(f"color: {FG_MUTED}; font-weight: bold;")
        self.type_cb = QComboBox()
        self.type_cb.addItems(["Note", "Script", "Task"])
        self.type_cb.setCurrentText(default_type)
        self.type_cb.currentTextChanged.connect(self.on_type_change)
        form_layout.addWidget(lbl_type, 2, 0)
        form_layout.addWidget(self.type_cb, 2, 1)
        
        # Attachment
        self.lbl_att = QLabel(tr('btn_attach_file') + ":")
        self.lbl_att.setStyleSheet(f"color: {FG_MUTED}; font-weight: bold;")
        
        self.att_sub_widget = QWidget()
        att_layout = QHBoxLayout(self.att_sub_widget)
        att_layout.setContentsMargins(0, 0, 0, 0)
        
        btn_select_file = create_horizontal_button(tr('btn_attach_file'), BTN_GRAY, self.select_file)
        btn_voice = create_horizontal_button(tr('btn_voice_rec'), BTN_RED, self.on_voice_record, is_primary=True)
        att_layout.addWidget(btn_select_file)
        att_layout.addWidget(btn_voice)
        att_layout.addStretch()
        
        form_layout.addWidget(self.lbl_att, 3, 0)
        form_layout.addWidget(self.att_sub_widget, 3, 1)
        
        self.att_display_lbl = QLabel("")
        self.att_display_lbl.setStyleSheet(f"color: {FG_GREEN};")
        form_layout.addWidget(self.att_display_lbl, 4, 1)
        
        # Task extensions
        self.task_ext_widget = QWidget()
        task_layout = QGridLayout(self.task_ext_widget)
        task_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_tags = QLabel(tr('lbl_tags_input'))
        lbl_tags.setStyleSheet(f"color: {FG_MUTED}; font-weight: bold;")
        self.tags_ent = QLineEdit()
        task_layout.addWidget(lbl_tags, 0, 0)
        task_layout.addWidget(self.tags_ent, 0, 1)
        
        lbl_date = QLabel(tr('lbl_due_date'))
        lbl_date.setStyleSheet(f"color: {FG_MUTED}; font-weight: bold;")
        self.due_date_ent = QLineEdit(datetime.date.today().strftime("%Y-%m-%d"))
        task_layout.addWidget(lbl_date, 1, 0)
        task_layout.addWidget(self.due_date_ent, 1, 1)
        
        lbl_effort = QLabel(tr('lbl_priority_input'))
        lbl_effort.setStyleSheet(f"color: {FG_MUTED}; font-weight: bold;")
        self.effort_cb = QComboBox()
        self.effort_cb.addItems(["XS", "S", "M", "L", "XL", "1h", "2h", "1d"])
        self.effort_cb.setCurrentText("M")
        task_layout.addWidget(lbl_effort, 2, 0)
        task_layout.addWidget(self.effort_cb, 2, 1)
        
        form_layout.addWidget(self.task_ext_widget, 5, 0, 1, 2)
        
        layout.addLayout(form_layout)
        
        lbl_content = QLabel(tr('lbl_content_input'))
        lbl_content.setStyleSheet(f"color: {FG_MUTED}; font-weight: bold;")
        layout.addWidget(lbl_content)
        
        # Scrolled Text
        self.txt_box = QTextEdit()
        apply_rtl_to_widget(self.txt_box)
        layout.addWidget(self.txt_box, 1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = create_horizontal_button(tr('btn_create_submit'), BTN_BLUE, self.on_save, is_primary=True)
        btn_cancel = create_horizontal_button(tr('btn_cancel'), BTN_GRAY, self.reject)
        
        btn_layout.addWidget(btn_save)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        self.on_type_change(default_type)
        center_window(self, 720, 620)

    def select_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "اختر ملف المرفق / الصورة", os.path.expanduser("~"))
        if f:
            self.attached_path = f
            self.att_display_lbl.setText(f"📎 {os.path.basename(f)}")

    def on_voice_record(self):
        sel_cat = self.cat_cb.currentText().strip() or "general"
        voice_rel, voice_txt = record_voice_dialog(self, target_text_widget=self.txt_box, category=sel_cat)
        if voice_rel:
            full_voice_path = os.path.join(NOTES_DIR, voice_rel)
            self.attached_path = full_voice_path
            self.att_display_lbl.setText(f"🎙️ {os.path.basename(voice_rel)}")
            self.txt_box.insertPlainText(voice_txt)

    def on_type_change(self, sel_type):
        if sel_type == "Script":
            self.lbl_att.hide()
            self.att_sub_widget.hide()
            self.att_display_lbl.hide()
            self.attached_path = ""
            self.att_display_lbl.setText("")
            
            self.lbl_cat.show()
            self.cat_cb.show()
            self.task_ext_widget.hide()
        elif sel_type == "Task":
            self.lbl_cat.hide()
            self.cat_cb.hide()
            
            self.lbl_att.show()
            self.att_sub_widget.show()
            self.att_display_lbl.show()
            
            self.task_ext_widget.show()
        else:
            self.lbl_att.show()
            self.att_sub_widget.show()
            self.att_display_lbl.show()
            
            self.lbl_cat.show()
            self.cat_cb.show()
            self.task_ext_widget.hide()

    def on_save(self):
        t = self.title_ent.text().strip()
        sel_type = self.type_cb.currentText()
        c = "tasks" if sel_type == "Task" else self.cat_cb.currentText().strip()
        if not t or (sel_type != "Task" and not c):
            QMessageBox.warning(self, "تحذير", "العنوان والفئة مطلوبان!")
            return
            
        self.saved_data = {
            'title': t,
            'category': c,
            'type': sel_type,
            'content': self.txt_box.toPlainText().strip(),
            'attached': self.attached_path,
            'tags': self.tags_ent.text().strip() if sel_type == "Task" else "",
            'due_date': self.due_date_ent.text().strip() if sel_type == "Task" else "",
            'effort': self.effort_cb.currentText().strip() if sel_type == "Task" else ""
        }
        self.accept()

def show_create_note_window(default_cat="general", default_type="Note", parent=None):
    if parent:
        parent.hide()
    try:
        dlg = CreateNoteDialog(default_cat, default_type)
        res = dlg.exec_()
    finally:
        if parent:
            parent.show()
            parent.raise_()
            parent.activateWindow()

    if res == QDialog.Accepted and dlg.saved_data:
        sd = dlg.saved_data
        cat_name = sd['category']
        if sd['type'] == 'Task':
            cat_dir = get_tasks_dir()
            media_dir = get_tasks_media_dir()
        else:
            cat_dir = get_category_dir(cat_name)
            media_dir = get_category_media_dir(cat_name)

        att_rel = "none"
        if sd['attached'] and os.path.exists(sd['attached']):
            if sd['attached'].startswith(cat_dir):
                att_rel = os.path.relpath(sd['attached'], NOTES_DIR)
            else:
                fname = os.path.basename(sd['attached'])
                sname = f"{int(time.time())}_{fname}"
                dest_file = os.path.join(media_dir, sname)
                shutil.copy(sd['attached'], dest_file)
                att_rel = os.path.relpath(dest_file, NOTES_DIR)

        safe_title = sd['title'].replace('/', '-').strip()
        file_path = os.path.join(cat_dir, f"{safe_title}.md")

        content_str = f"""---
title: "{sd['title']}"
category: "{sd['category']}"
icon: "📌"
attachment: "{att_rel}"
created: "{time.strftime('%Y-%m-%d %H:%M')}"
access_count: 0
reminder: ""
scheduled_exec: ""
type: "{sd['type']}"
status: "todo"
priority: "medium"
tags: "{sd.get('tags', '')}"
due_date: "{sd.get('due_date', '')}"
effort: "{sd.get('effort', '')}"
schedule_type: "once"
interval_mins: 0
require_internet: "false"
catch_up_on_boot: "true"
play_sound: "true"
last_run: ""
script_enabled: "true"
---
{sd['content']}
"""
        with open(file_path, 'w', encoding='utf-8') as fp:
            fp.write(content_str)
        return file_path
    return None
