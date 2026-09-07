import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTreeWidget, QTreeWidgetItem, QTextEdit)
from PyQt5.QtCore import Qt

from config import NOTES_PATH, BG_MAIN, BG_CARD, FG_GREEN, FG_TEXT, FG_MUTED, BTN_BLUE, BTN_GRAY, BTN_AMBER, BTN_GREEN, BTN_PURPLE, BTN_RED
from utils import center_window, parse_note_file, update_frontmatter_keys
from ui_common import get_common_qss, create_horizontal_button, apply_rtl_to_widget
from note_manager import get_all_notes
from ui_view_note import show_note_view_window
from git_sync import sync_notes_cli
from i18n import tr
import datetime


def show_todays_reminders_window(filter_cat=None):
    all_notes = get_all_notes(filter_cat=filter_cat)

    reminders = []
    for n in all_notes:
        rem = n['reminder']
        n_type = n.get('type', 'Note')
        has_sched = bool(n.get('scheduled_exec') or str(n.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1'])
        is_script = (n_type == 'Script') or has_sched

        if rem and not is_script:
            type_str = "📋 Task" if n_type == 'Task' else "📝 Note"
            reminders.append({
                'file': n['file'],
                'title': n['title'],
                'time': rem,
                'type': type_str
            })

    dlg = QDialog()
    title_str = tr('rem_win_title')
    dlg.setWindowTitle(title_str)
    dlg.setFixedSize(740, 440)
    dlg.setStyleSheet(get_common_qss())

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(15, 15, 15, 15)

    header_str = tr('rem_header')
    lbl = QLabel(header_str)
    lbl.setStyleSheet(f"color: {FG_GREEN}; font-weight: bold; font-size: 14px;")
    layout.addWidget(lbl)

    tree = QTreeWidget()
    tree.setHeaderLabels(["File", tr('col_rem_title'), tr('col_rem_time'), tr('col_rem_type')])
    tree.hideColumn(0)
    tree.setColumnWidth(1, 280)
    tree.setColumnWidth(2, 220)
    tree.setColumnWidth(3, 200)
    layout.addWidget(tree)

    for r in reminders:
        item = QTreeWidgetItem([r['file'], r['title'], r['time'], r['type']])
        tree.addTopLevelItem(item)

    def on_open():
        items = tree.selectedItems()
        if items:
            f = items[0].text(0)
            if f and os.path.exists(f):
                dlg.accept()
                show_note_view_window(f)

    tree.itemDoubleClicked.connect(lambda item, col: on_open())

    btn_layout = QHBoxLayout()
    btn_view = create_horizontal_button("📄 " + tr('btn_open'), BTN_BLUE, on_open, is_primary=True)
    btn_close = create_horizontal_button(tr('btn_cancel'), BTN_GRAY, dlg.reject)
    btn_layout.addWidget(btn_view)
    btn_layout.addStretch()
    btn_layout.addWidget(btn_close)
    layout.addLayout(btn_layout)

    center_window(dlg, 740, 440)
    dlg.exec_()


def show_reminder_alert_popup(filepath):
    if not filepath or not os.path.exists(filepath):
        return
    
    n_data = parse_note_file(filepath)
    title = n_data['title']
    category = n_data.get('category', 'general')
    body = n_data.get('body', '')
    priority = n_data.get('reminder_priority', 'normal').lower()
    
    dlg = QDialog()
    dlg.setWindowTitle(f"🔔 تنبيه تذكير: {title}")
    dlg.setMinimumSize(580, 400)
    dlg.setStyleSheet(get_common_qss())
    
    if priority == 'critical':
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(15, 15, 15, 15)
    
    if priority == 'critical':
        pri_badge = "🔴 تنبيه حرج (Critical Urgency)"
        pri_color = "#E06C75"
    elif priority == 'quiet':
        pri_badge = "🟢 تنبيه هادئ (Quiet Notice)"
        pri_color = "#98C379"
    else:
        pri_badge = "🟡 تنبيه قياسي (Normal Alert)"
        pri_color = "#E5C07B"

    header_lbl = QLabel(f"🔔 إشعار تذكير: {title}")
    header_lbl.setStyleSheet(f"color: {pri_color}; font-weight: bold; font-size: 16px;")
    layout.addWidget(header_lbl)
    
    cat_lbl = QLabel(f"📁 الفئة: {category}  |  {pri_badge}")
    cat_lbl.setStyleSheet("color: #888888; font-size: 12px;")
    layout.addWidget(cat_lbl)
    
    preview_box = QTextEdit()
    preview_box.setReadOnly(True)
    preview_box.setStyleSheet(f"background-color: {BG_CARD}; color: {FG_TEXT}; border: 1px solid #444; border-radius: 6px;")
    preview_text = body[:600] + ("..." if len(body) > 600 else "")
    preview_box.setPlainText(preview_text)
    apply_rtl_to_widget(preview_box, preview_text)
    layout.addWidget(preview_box, 1)
    
    snooze_hdr = QLabel("⏰ اختر تأجيل التنبيه (Snooze Options):")
    snooze_hdr.setStyleSheet(f"color: {FG_GREEN}; font-weight: bold; font-size: 12px; margin-top: 5px;")
    layout.addWidget(snooze_hdr)
    
    snooze_layout = QHBoxLayout()
    
    def snooze(minutes):
        new_dt = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        rem_str = new_dt.strftime("%Y-%m-%d %H:%M")
        update_frontmatter_keys(filepath, {'reminder': rem_str})
        sync_notes_cli()
        dlg.accept()
        
    btn_s5 = create_horizontal_button("⏱️ +5 دقائق", BTN_AMBER, lambda: snooze(5))
    btn_s15 = create_horizontal_button("⏱️ +15 دقيقة", BTN_AMBER, lambda: snooze(15))
    btn_s60 = create_horizontal_button("⏱️ +ساعة", BTN_AMBER, lambda: snooze(60))
    btn_s24h = create_horizontal_button("📅 للغد (24س)", BTN_PURPLE, lambda: snooze(1440))
    
    snooze_layout.addWidget(btn_s5)
    snooze_layout.addWidget(btn_s15)
    snooze_layout.addWidget(btn_s60)
    snooze_layout.addWidget(btn_s24h)
    layout.addLayout(snooze_layout)
    
    bottom_layout = QHBoxLayout()
    
    def on_open_full():
        dlg.accept()
        show_note_view_window(filepath)

    def on_dismiss():
        rem_rep = n_data.get('reminder_repeat', 'none').lower()
        if rem_rep == 'none':
            update_frontmatter_keys(filepath, {'reminder': ""})
            sync_notes_cli()
        dlg.accept()

    btn_open = create_horizontal_button("📄 فتح الملاحظة", BTN_BLUE, on_open_full, is_primary=True)
    btn_dismiss = create_horizontal_button("✅ حسناً / إغلاق", BTN_GREEN, on_dismiss)
    
    bottom_layout.addWidget(btn_open)
    bottom_layout.addWidget(btn_dismiss)
    layout.addLayout(bottom_layout)
    
    center_window(dlg, 580, 400)
    dlg.exec_()

