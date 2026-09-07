import os
import subprocess
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox)
from PyQt5.QtCore import Qt

from config import NOTES_DIR, BG_MAIN, BG_CARD, FG_GREEN, FG_TEXT, FG_MUTED, BTN_BLUE, BTN_GRAY
from utils import center_window
from ui_common import get_common_qss, create_horizontal_button


def show_setup_wizard():
    dlg = QDialog()
    dlg.setWindowTitle("⚙️ إعداد مزامنة GitHub")
    dlg.setFixedSize(550, 240)
    dlg.setStyleSheet(get_common_qss())

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(15, 15, 15, 15)

    lbl_title = QLabel("⚙️ إعداد مستودع GitHub")
    lbl_title.setStyleSheet(f"color: {FG_GREEN}; font-weight: bold; font-size: 14px;")
    layout.addWidget(lbl_title)

    lbl_sub = QLabel("أدخل رابط مستودع GitHub الخاص بك:")
    lbl_sub.setStyleSheet(f"color: {FG_MUTED};")
    layout.addWidget(lbl_sub)

    repo_ent = QLineEdit()
    layout.addWidget(repo_ent)

    layout.addStretch()

    def on_setup():
        repo = repo_ent.text().strip()
        if not repo:
            QMessageBox.warning(dlg, "تحذير", "رابط المستودع مطلوب!")
            return

        os.chdir(NOTES_DIR)
        subprocess.run(["git", "init"])
        subprocess.run(["git", "branch", "-M", "main"])
        subprocess.run(["git", "remote", "add", "origin", repo])

        readme_path = os.path.join(NOTES_DIR, "README.md")
        if not os.path.exists(readme_path):
            with open(readme_path, "w") as f:
                f.write("# Developer Notes\nPersonal notes repository.\n")

        subprocess.run(["git", "add", "."])
        subprocess.run(["git", "commit", "-m", "Initialize developer notes"])
        subprocess.run(["git", "push", "-u", "origin", "main"])
        QMessageBox.information(dlg, "نجاح", "✅ تم إعداد مستودع GitHub بنجاح!")
        dlg.accept()

    btn_layout = QHBoxLayout()
    btn_init = create_horizontal_button("🚀 تهيئة ورفع", BTN_BLUE, on_setup, is_primary=True)
    btn_cancel = create_horizontal_button("❌ إلغاء", BTN_GRAY, dlg.reject)
    btn_layout.addWidget(btn_init)
    btn_layout.addStretch()
    btn_layout.addWidget(btn_cancel)
    layout.addLayout(btn_layout)

    center_window(dlg, 550, 240)
    dlg.exec_()
