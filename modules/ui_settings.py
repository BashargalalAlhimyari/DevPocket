import os
import sys
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QLineEdit, QFileDialog, 
                             QMessageBox, QWidget, QGroupBox, QRadioButton, 
                             QButtonGroup, QFrame)
from PyQt5.QtCore import Qt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import NOTES_DIR, update_notes_dir
from utils import center_window
from i18n import get_lang, set_lang, tr
from theme import get_theme, set_theme, get_theme_colors, get_theme_qss
from git_sync import get_git_remote_url, setup_git_repo_gui
from ui_common import create_horizontal_button


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_changed = False
        
        c = get_theme_colors()
        self.setWindowTitle("⚙️ " + ("إعدادات التطبيق" if get_lang() == 'ar' else "Application Settings"))
        self.resize(620, 500)
        self.setMinimumSize(540, 420)
        self.setStyleSheet(get_theme_qss())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        is_ar = (get_lang() == 'ar')
        lbl_head = QLabel("⚙️ " + ("إعدادات التطبيق وتخصيص الواجهة" if is_ar else "Application Settings & Customization"))
        lbl_head.setStyleSheet(f"color: {c['FG_GREEN']}; font-weight: bold; font-size: 16px;")
        layout.addWidget(lbl_head)

        gb_style = f"""
            QGroupBox {{
                color: {c['FG_TEXT']};
                font-weight: bold;
                font-size: 13px;
                border: 1px solid {c['CLR_BORDER']};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 14px;
                background-color: {c['BG_CARD']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
            }}
        """

        # Section 1: Language Selection
        g_lang = QGroupBox("🌐 " + ("لغة الواجهة (Interface Language)" if is_ar else "Interface Language"))
        g_lang.setStyleSheet(gb_style)
        l_lang = QHBoxLayout(g_lang)
        
        self.bg_lang = QButtonGroup(self)
        self.rb_ar = QRadioButton("العربية (Arabic)")
        self.rb_en = QRadioButton("English")
        self.bg_lang.addButton(self.rb_ar)
        self.bg_lang.addButton(self.rb_en)
        
        if get_lang() == 'ar':
            self.rb_ar.setChecked(True)
        else:
            self.rb_en.setChecked(True)
            
        l_lang.addWidget(self.rb_ar)
        l_lang.addWidget(self.rb_en)
        l_lang.addStretch()
        layout.addWidget(g_lang)

        # Section 2: Theme Selection (Dark / Light Mode)
        g_theme = QGroupBox("🎨 " + ("مظهر التطبيق والثيم (Theme & Appearance)" if is_ar else "Theme & Appearance"))
        g_theme.setStyleSheet(gb_style)
        l_theme = QHBoxLayout(g_theme)
        
        self.bg_theme = QButtonGroup(self)
        self.rb_dark = QRadioButton("🌙 " + ("الوضع الليلي (Dark Mode)" if is_ar else "Dark Mode"))
        self.rb_light = QRadioButton("☀️ " + ("الوضع النهاري (Light Mode)" if is_ar else "Light Mode"))
        self.bg_theme.addButton(self.rb_dark)
        self.bg_theme.addButton(self.rb_light)
        
        if get_theme() == 'light':
            self.rb_light.setChecked(True)
        else:
            self.rb_dark.setChecked(True)
            
        l_theme.addWidget(self.rb_dark)
        l_theme.addWidget(self.rb_light)
        l_theme.addStretch()
        layout.addWidget(g_theme)

        layout.addStretch()

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_save = create_horizontal_button(
            "💾 " + ("حفظ وتطبيق الإعدادات" if is_ar else "Save & Apply Settings"),
            "#2563EB",
            self.on_save,
            is_primary=True
        )
        btn_cancel = create_horizontal_button(
            "❌ " + ("إلغاء" if is_ar else "Cancel"),
            c['BTN_BG'],
            self.reject
        )

        btn_layout.addWidget(btn_save)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        center_window(self, 620, 500)

    def on_change_dir(self):
        new_d = QFileDialog.getExistingDirectory(self, "اختر مجلد حفظ الملاحظات الجديد", NOTES_DIR)
        if new_d:
            update_notes_dir(new_d)
            self.path_ent.setText(new_d)
            self.settings_changed = True

    def on_setup_git(self):
        setup_git_repo_gui()
        remote_url = get_git_remote_url()
        if remote_url:
            self.git_lbl.setText(f"🔗 {remote_url}")

    def on_save(self):
        new_lang = 'ar' if self.rb_ar.isChecked() else 'en'
        set_lang(new_lang)

        new_theme = 'light' if self.rb_light.isChecked() else 'dark'
        set_theme(new_theme)

        self.settings_changed = True
        self.accept()


def show_settings_dialog(parent=None):
    dlg = SettingsDialog(parent)
    res = dlg.exec_()
    return dlg.settings_changed
