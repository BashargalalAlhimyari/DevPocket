import os
import time
import datetime
import subprocess
import threading
import shutil
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QLineEdit, QComboBox, QTextEdit,
                             QTextBrowser, QMessageBox, QWidget, QGridLayout, 
                             QGroupBox, QCheckBox, QRadioButton, QButtonGroup, 
                             QScrollArea, QFrame)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage

from config import NOTES_DIR, BG_MAIN, BG_CARD, FG_GREEN, FG_TEXT, FG_MUTED, BTN_BLUE, BTN_AMBER, BTN_RED, BTN_GREEN, BTN_PURPLE, BTN_TEAL, BTN_GRAY
from utils import center_window, parse_note_file, update_frontmatter_keys, open_file_cross_platform
from note_manager import increase_note_access, archive_note
from boot_manager import update_boot_autostart_entries
from git_sync import sync_notes_cli
from voice_recorder import record_voice_dialog
from ui_common import apply_rtl_to_widget, get_common_qss, create_horizontal_button, create_horizontal_scrollable_frame, is_arabic
from daemon import play_sound
from i18n import tr

import re
try:
    import markdown
except ImportError:
    markdown = None

try:
    import emoji
except ImportError:
    emoji = None

def convert_markdown_to_styled_html(text):
    if not text:
        return ""
    
    # 1. Pre-process GitHub Alert Callouts: > [!NOTE], > [!TIP], > [!IMPORTANT], > [!WARNING], > [!CAUTION]
    alert_styles = {
        'NOTE': ('ℹ️', 'Note', '#1F6FEB', '#0D1117', '#38BDF8'),
        'TIP': ('💡', 'Tip', '#238636', '#0D1117', '#34D399'),
        'IMPORTANT': ('📌', 'Important', '#8957E5', '#0D1117', '#A78BFA'),
        'WARNING': ('⚠️', 'Warning', '#9E6A03', '#0D1117', '#FBBF24'),
        'CAUTION': ('🚫', 'Caution', '#DA3633', '#0D1117', '#F87171'),
    }

    pattern = r'^>\s*\[\!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*\n((?:^>.*(?:\n|$))+)'

    def process_alert_match(m):
        kind = m.group(1).upper()
        lines = m.group(2).splitlines()
        clean_lines = [re.sub(r'^>\s*', '', l) for l in lines]
        body_content = "<br>".join(clean_lines)
        icon, title, border_clr, bg_clr, text_clr = alert_styles.get(kind, ('ℹ️', kind, '#1F6FEB', '#0D1117', '#38BDF8'))
        return (
            f'<div style="background-color: {bg_clr}; border-left: 4px solid {border_clr}; '
            f'border-radius: 6px; padding: 10px 14px; margin: 12px 0; border: 1px solid #30363D; '
            f'border-left: 4px solid {border_clr};">'
            f'<div style="color: {text_clr}; font-weight: bold; font-size: 13px; margin-bottom: 4px;">{icon}  {title}</div>'
            f'<div style="color: #C9D1D9; font-size: 13px;">{body_content}</div></div>\n'
        )

    processed_text = re.sub(pattern, process_alert_match, text, flags=re.MULTILINE | re.IGNORECASE)

    # 2. Markdown Extensions Config (GFM support via pymdownx & standard markdown)
    ext_configs = {
        'codehilite': {
            'noclasses': True,
            'pygments_style': 'monokai',
            'guess_lang': True,
            'use_pygments': True
        }
    }

    extensions = ['extra', 'codehilite', 'toc', 'nl2br', 'sane_lists', 'tables', 'fenced_code']
    try:
        import pymdownx
        extensions.extend(['pymdownx.tasklist', 'pymdownx.tilde', 'pymdownx.magiclink'])
    except ImportError:
        pass

    if markdown:
        try:
            html_content = markdown.markdown(
                processed_text,
                extensions=extensions,
                extension_configs=ext_configs
            )
        except Exception:
            html_content = processed_text.replace('\n', '<br>')
    else:
        html_content = processed_text.replace('\n', '<br>')

    # 3. Convert Emojis to Twemoji HTML image tags for PyQt5
    if emoji:
        try:
            def replace_emoji_with_img(emoji_char, match_dict):
                hex_code = "-".join(f"{ord(c):x}" for c in emoji_char)
                url = f"https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72/{hex_code}.png"
                return f'<img src="{url}" width="18" height="18" style="vertical-align: middle; margin: 0 2px;" alt="{emoji_char}">'

            html_content = emoji.replace_emoji(html_content, replace_emoji_with_img)
        except Exception:
            pass

    # 4. Wrap codehilite divs inside robust HTML tables for PyQt5 QTextEdit
    def wrap_codehilite_in_table(match):
        code_inner = match.group(1)
        return (
            '<table style="background-color: #1E222A; border: 1px solid #3E4451; '
            'width: 100%; border-radius: 6px; margin: 10px 0; border-collapse: collapse;">'
            '<tr><td style="padding: 10px 14px; font-family: monospace; font-size: 13px; color: #ABB2BF; border: none;">'
            f'{code_inner}'
            '</td></tr></table>'
        )

    html_content = re.sub(
        r'<div class="codehilite"[^>]*>(.*?)</div>',
        wrap_codehilite_in_table,
        html_content,
        flags=re.DOTALL
    )

    # 5. Full GitHub Dark Theme CSS
    styled_html = f"""
    <html>
    <head>
    <style>
        body {{
            color: #C9D1D9;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'DejaVu Sans', sans-serif;
            font-size: 14px;
            line-height: 1.6;
            background-color: transparent;
            margin: 0;
            padding: 16px 22px;
        }}
        p, div, li, td, th {{
            color: #C9D1D9;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'DejaVu Sans', sans-serif;
            font-size: 14px;
            line-height: 1.6;
            background-color: transparent;
        }}
        h1 {{
            color: #58A6FF;
            border-bottom: 1px solid #30363D;
            padding-bottom: 6px;
            font-size: 22px;
            font-weight: bold;
            margin-top: 20px;
            margin-bottom: 12px;
        }}
        h2 {{
            color: #79C0FF;
            border-bottom: 1px solid #30363D;
            padding-bottom: 4px;
            font-size: 18px;
            font-weight: bold;
            margin-top: 16px;
            margin-bottom: 10px;
        }}
        h3 {{
            color: #D2A8FF;
            font-size: 16px;
            font-weight: bold;
            margin-top: 14px;
            margin-bottom: 8px;
        }}
        h4, h5, h6 {{
            color: #FFA657;
            font-size: 14px;
            font-weight: bold;
        }}
        code {{
            background-color: #262C36;
            color: #E6EDF3;
            font-family: monospace;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 13px;
        }}
        pre {{
            font-family: monospace;
            color: #ABB2BF;
            margin: 0;
            padding: 0;
            background-color: transparent;
        }}
        kbd {{
            background-color: #21262D;
            border: 1px solid #30363D;
            border-radius: 4px;
            color: #C9D1D9;
            font-size: 11px;
            font-family: monospace;
            padding: 2px 5px;
        }}
        blockquote {{
            border-left: 4px solid #30363D;
            margin: 12px 0;
            padding: 8px 16px;
            color: #8B949E;
            background-color: #0D1117;
            border-radius: 0 6px 6px 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 14px 0;
            border: 1px solid #30363D;
        }}
        th, td {{
            border: 1px solid #30363D;
            padding: 8px 12px;
            text-align: left;
        }}
        th {{
            background-color: #161B22;
            color: #F0F6FC;
            font-weight: bold;
        }}
        tr:nth-child(even) {{
            background-color: #161B22;
        }}
        a {{
            color: #58A6FF;
            text-decoration: underline;
        }}
        hr {{
            border: none;
            border-top: 1px solid #30363D;
            margin: 18px 0;
        }}
        ul, ol {{
            padding-left: 24px;
            margin: 8px 0;
        }}
        li {{
            margin-bottom: 4px;
        }}
        del {{
            color: #8B949E;
            text-decoration: line-through;
        }}
        img {{
            max-width: 100%;
            height: auto;
            border-radius: 6px;
        }}
    </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    return styled_html


def create_datetime_picker(parent_layout, initial_date="", initial_time=""):
    now = datetime.datetime.now()
    cur_year = initial_date.split('-')[0] if '-' in initial_date else str(now.year)
    cur_month = initial_date.split('-')[1] if '-' in initial_date and len(initial_date.split('-')) > 1 else f"{now.month:02d}"
    cur_day = initial_date.split('-')[2] if '-' in initial_date and len(initial_date.split('-')) > 2 else f"{now.day:02d}"
    cur_hour = initial_time.split(':')[0] if ':' in initial_time else f"{now.hour:02d}"
    cur_min = initial_time.split(':')[1] if ':' in initial_time else f"{now.minute:02d}"

    # Date
    date_layout = QHBoxLayout()
    date_layout.addWidget(QLabel("📅 Date:"))
    
    cb_year = QComboBox()
    cb_year.addItems([str(y) for y in range(now.year, now.year + 6)])
    cb_year.setCurrentText(cur_year)
    date_layout.addWidget(cb_year)
    date_layout.addWidget(QLabel("-"))
    
    cb_month = QComboBox()
    cb_month.addItems([f"{m:02d}" for m in range(1, 13)])
    cb_month.setCurrentText(cur_month)
    date_layout.addWidget(cb_month)
    date_layout.addWidget(QLabel("-"))
    
    cb_day = QComboBox()
    cb_day.addItems([f"{d:02d}" for d in range(1, 32)])
    cb_day.setCurrentText(cur_day)
    date_layout.addWidget(cb_day)
    date_layout.addStretch()
    
    # Time
    time_layout = QHBoxLayout()
    time_layout.addWidget(QLabel("⏰ Time:"))
    
    cb_hour = QComboBox()
    cb_hour.addItems([f"{h:02d}" for h in range(0, 24)])
    cb_hour.setCurrentText(cur_hour)
    time_layout.addWidget(cb_hour)
    time_layout.addWidget(QLabel(":"))
    
    cb_min = QComboBox()
    cb_min.addItems([f"{m:02d}" for m in range(0, 60)])
    cb_min.setCurrentText(cur_min)
    time_layout.addWidget(cb_min)
    time_layout.addStretch()

    parent_layout.addLayout(date_layout)
    parent_layout.addLayout(time_layout)

    def get_formatted_date_time():
        d_str = f"{cb_year.currentText()}-{cb_month.currentText()}-{cb_day.currentText()}"
        t_str = f"{cb_hour.currentText()}:{cb_min.currentText()}"
        return d_str, t_str

    return get_formatted_date_time

CATEGORIES_TRIGGERS = {
    "💻 النظام والطاقة (System & Power)": [
        "إقلاع النظام (System Booted)",
        "تسجيل دخول مستخدم (User Logged In)",
        "إيقاف تشغيل النظام (System Shutting Down)",
        "دخول وضع السكون (System Sleep/Suspend)",
        "استيقاظ الجهاز (System Resume/Wakeup)",
        "انخفاض البطارية عن % (Battery Drops Below)",
        "ارتفاع البطارية أو اكتمالها % (Battery Rises/Full)",
        "توصيل الشاحن (Charger Connected)",
        "فصل الشاحن (Charger Disconnected)",
        "تفعيل وضع توفير الطاقة (Power Save Mode)",
        "ارتفاع درجة الحرارة عن °C (Temp Exceeds)",
        "انخفاض الذاكرة المتاحة عن MB (RAM Available)",
        "ارتفاع استهلاك القرص عن % (Disk Usage Exceeds)"
    ],
    "🌐 الشبكات والاتصال (Network & Connectivity)": [
        "الاتصال بـ Wi-Fi محددة (Wi-Fi Connected)",
        "الاتصال بـ Wi-Fi عامة/مفتوحة (Wi-Fi Public/Open)",
        "انقطاع اتصال Wi-Fi (Wi-Fi Disconnected)",
        "تغير عنوان الـ IP (IP Address Changed)",
        "تغير حالة كابل شبكة Ethernet (Ethernet State)",
        "توفر اتصال الإنترنت (Internet Connected)",
        "انقطاع اتصال الإنترنت (Internet Disconnected)",
        "عُودة اتصال الإنترنت (Internet Reconnected)",
        "فشل الاتصال بخادم (Ping Host Failed)",
        "ارتفاع بطء الشبكة عن ms (Latency Exceeds)",
        "الاتصال بشبكة غير موثوقة (Untrusted Network)",
        "الاتصال بشبكة الشركة (Company Network)",
        "تفعيل اتصال VPN (VPN Connected)",
        "توقف أو انقطاع VPN (VPN Disconnected)"
    ],
    "🐳 Docker والخدمات (Docker & Services)": [
        "بدء تشغيل Docker (Docker Daemon Started)",
        "توقف Docker (Docker Daemon Stopped)",
        "بدء تشغيل حاوية Docker (Container Started)",
        "جاهزية قاعدة البيانات (Database Service Ready)",
        "توقف أو فشل حاوية Docker (Container Failed)",
        "تكرار فشل حاوية Docker (Container Failed Repeatedly)",
        "ملاءمة/فتح منفذ معين (Port Open/Available)",
        "إغلاق/عدم إتاحة منفذ (Port Closed/Unavailable)",
        "بدء تشغيل خادم التطوير (Dev Server Started)",
        "توقف خدمة الـ Backend (Backend Service Stopped)",
        "تعديل ملف البيئة (.env File Changed)",
        "تحديث صورة Docker (Docker Image Updated)",
        "فشل فحص الصحة (Health Check Failed)",
        "بدء تسلسل خدمات مشروع (Project Sequence Start)"
    ],
    "💻 التطوير والبرمجة (Development & Programming)": [
        "فتح مجلد مشروع (Project Directory Opened)",
        "تعديل ملف Python (Python File Modified)",
        "حفظ ملف كود (Code File Saved)",
        "فشل مجموعة الاختبارات (Test Suite Failed)",
        "نجاح بناء المشروع (Build Succeeded)",
        "إنشاء Commit جديد بـ Git (Git Commit Created)",
        "إنشاء Tag جديد بـ Git (Git Tag Created)",
        "وصول تغييرات Git جديدة (Git Pull/Changes)",
        "تعديل ملف requirements.txt Changed",
        "تعديل ملف package.json Changed",
        "بدء تشغيل مشروع Flutter (Flutter Started)",
        "توصيل هاتف Android بـ USB (Android Connected)",
        "فصل هاتف Android (Android Disconnected)",
        "فشل بناء تطبيق Android (Android Build Failed)",
        "إضافة ملف جديد لمجلد مراقب (New File Added)"
    ],
    "📁 الملفات والملاحظات (Files & Notes)": [
        "إنشاء ملف جديد بمجلد (File Created In Dir)",
        "تعديل ملف إعدادات (Config File Modified)",
        "حذف ملف مهم (Important File Deleted)",
        "وصول ملف لمجلد التنزيلات (Downloads File Arrived)",
        "تحميل ملف مضغوط Zip Arrived",
        "تعديل محتوى ملاحظة (Note Modified)",
        "ملاحظة تحتوي وسم (#urgent Tag)",
        "ملاحظة تحتوي كود أتمتة (WHEN... Code)",
        "فشل تنفيذ أتمتة (Automation Failed)",
        "تجاوز فترة عدم نشاط بالتحفيز (Inactivity Timeout)"
    ],
    "🛡️ الأمان والمراقبة (Security & Monitoring)": [
        "تغير ملف نظام حساس (Sensitive File Changed)",
        "رصد تسجيل دخول غير معتاد (Unusual Login)",
        "برنامج غير معروف (Unknown Process)",
        "تجاوز استهلاك بيانات الشبكة MB (Data Exceeds)",
        "تكرار فشل تسجيل SSH (SSH Failed Attempts)",
        "توقف خدمة الجدار الناري (Firewall Stopped)",
        "توصيل جهاز USB غير معروف (Unknown USB)",
        "تغير قواعد الجدار الناري (Firewall Rules Changed)",
        "رصد خدمة غير آمنة (Insecure Service Detected)",
        "تكرار الحدث بشكل سريع جداً (Rapid Event Triggered)"
    ],
    "⚙️ مخصص وأوامر (Custom & Advanced)": [
        "نجاح أمر Bash (Exit 0) (Bash Command Succeeds)",
        "برنامج قيد التشغيل (Process Running/Found)",
        "برنامج متوقف عن العمل (Process Terminated)"
    ]
}

TRIGGER_HINTS = {
    # System & Power
    "إقلاع النظام (System Booted)": "لا يتطلب قيمة (اتركه فارغاً)",
    "تسجيل دخول مستخدم (User Logged In)": "اسم المستخدم (مثال: bashar أو اتركه فارغاً لأي مستخدم)",
    "إيقاف تشغيل النظام (System Shutting Down)": "لا يتطلب قيمة (اتركه فارغاً)",
    "دخول وضع السكون (System Sleep/Suspend)": "لا يتطلب قيمة (اتركه فارغاً)",
    "استيقاظ الجهاز (System Resume/Wakeup)": "لا يتطلب قيمة (اتركه فارغاً)",
    "انخفاض البطارية عن % (Battery Drops Below)": "رقم: نسبة مئوية (مثال: 20)",
    "ارتفاع البطارية أو اكتمالها % (Battery Rises/Full)": "رقم: نسبة مئوية (مثال: 85 أو 100)",
    "توصيل الشاحن (Charger Connected)": "لا يتطلب قيمة (اتركه فارغاً)",
    "فصل الشاحن (Charger Disconnected)": "لا يتطلب قيمة (اتركه فارغاً)",
    "تفعيل وضع توفير الطاقة (Power Save Mode)": "لا يتطلب قيمة (اتركه فارغاً)",
    "ارتفاع درجة الحرارة عن °C (Temp Exceeds)": "رقم: درجة حرارة مئوية (مثال: 75)",
    "انخفاض الذاكرة المتاحة عن MB (RAM Available)": "رقم: حجم بالميجابايت (مثال: 1024)",
    "ارتفاع استهلاك القرص عن % (Disk Usage Exceeds)": "رقم: نسبة مئوية لامتلاء القرص (مثال: 90)",

    # Network
    "الاتصال بـ Wi-Fi محددة (Wi-Fi Connected)": "نص: اسم الشبكة SSID (مثال: Home_5G أو فارغ لأي شبكة)",
    "الاتصال بـ Wi-Fi عامة/مفتوحة (Wi-Fi Public/Open)": "لا يتطلب قيمة (اتركه فارغاً)",
    "انقطاع اتصال Wi-Fi (Wi-Fi Disconnected)": "نص: اسم الشبكة المقطوعة SSID",
    "تغير عنوان الـ IP (IP Address Changed)": "لا يتطلب قيمة (اتركه فارغاً)",
    "تغير حالة كابل شبكة Ethernet (Ethernet State)": "لا يتطلب قيمة (اتركه فارغاً)",
    "توفر اتصال الإنترنت (Internet Connected)": "لا يتطلب قيمة (اتركه فارغاً)",
    "انقطاع اتصال الإنترنت (Internet Disconnected)": "لا يتطلب قيمة (اتركه فارغاً)",
    "عُودة اتصال الإنترنت (Internet Reconnected)": "لا يتطلب قيمة (اتركه فارغاً)",
    "فشل الاتصال بخادم (Ping Host Failed)": "نص: عنوان الخادم أو IP (مثال: 8.8.8.8 أو google.com)",
    "ارتفاع بطء الشبكة عن ms (Latency Exceeds)": "رقم: الزمن بالمللي ثانية (مثال: 250)",
    "الاتصال بشبكة غير موثوقة (Untrusted Network)": "نص: اسم شبكة المكاتب الموثوقة أو اتركه فارغاً",
    "الاتصال بشبكة الشركة (Company Network)": "نص: اسم شبكة الشركة أو النطاق",
    "تفعيل اتصال VPN (VPN Connected)": "نص: اسم واجهة الـ VPN (مثال: tun0 أو اتركه فارغاً)",
    "توقف أو انقطاع VPN (VPN Disconnected)": "نص: اسم واجهة الـ VPN (مثال: tun0)",

    # Docker & Services
    "بدء تشغيل Docker (Docker Daemon Started)": "لا يتطلب قيمة (اتركه فارغاً)",
    "توقف Docker (Docker Daemon Stopped)": "لا يتطلب قيمة (اتركه فارغاً)",
    "بدء تشغيل حاوية Docker (Container Started)": "نص: اسم الحاوية (مثال: my-web-app)",
    "جاهزية قاعدة البيانات (Database Service Ready)": "رقم/نص: المنفذ أو اسم الخدمة (مثال: 5432 أو postgres)",
    "توقف أو فشل حاوية Docker (Container Failed)": "نص: اسم الحاوية المتوقفة",
    "تكرار فشل حاوية Docker (Container Failed Repeatedly)": "نص: اسم الحاوية",
    "ملاءمة/فتح منفذ معين (Port Open/Available)": "رقم: رقم المنفذ (مثال: 8080)",
    "إغلاق/عدم إتاحة منفذ (Port Closed/Unavailable)": "رقم: رقم المنفذ (مثال: 3000)",
    "بدء تشغيل خادم التطوير (Dev Server Started)": "رقم/نص: رقم المنفذ أو الرابط (مثال: 3000)",
    "توقف خدمة الـ Backend (Backend Service Stopped)": "نص: اسم العملية أو المنفذ",
    "تعديل ملف البيئة (.env File Changed)": "مسار: مسار ملف البيئة (مثال: /path/to/.env)",
    "تحديث صورة Docker (Docker Image Updated)": "نص: اسم الصورة (مثال: ubuntu:latest)",
    "فشل فحص الصحة (Health Check Failed)": "نص: رابط فحص الصحة (مثال: http://localhost:8000/health)",
    "بدء تسلسل خدمات مشروع (Project Sequence Start)": "مسار: مسار مجلد المشروع",

    # Development
    "فتح مجلد مشروع (Project Directory Opened)": "مسار: مسار مجلد المشروع",
    "تعديل ملف Python (Python File Modified)": "مسار: مسار الملف أو المجلد",
    "حفظ ملف كود (Code File Saved)": "نص/مسار: الامتداد أو المسار (مثال: .py)",
    "فشل مجموعة الاختبارات (Test Suite Failed)": "أمر/نص: أمر تشغيل الاختبارات (مثال: pytest)",
    "نجاح بناء المشروع (Build Succeeded)": "مسار: مسار المشروع",
    "إنشاء Commit جديد بـ Git (Git Commit Created)": "مسار: مسار مستودع Git",
    "إنشاء Tag جديد بـ Git (Git Tag Created)": "مسار: مسار مستودع Git",
    "وصول تغييرات Git جديدة (Git Pull/Changes)": "مسار: مسار مستودع Git",
    "تعديل ملف requirements.txt Changed": "مسار: مسار ملف requirements.txt",
    "تعديل ملف package.json Changed": "مسار: مسار ملف package.json",
    "بدء تشغيل مشروع Flutter (Flutter Started)": "نص/مسار: اسم أو مسار مشروع Flutter",
    "توصيل هاتف Android بـ USB (Android Connected)": "لا يتطلب قيمة (اتركه فارغاً)",
    "فصل هاتف Android (Android Disconnected)": "لا يتطلب قيمة (اتركه فارغاً)",
    "فشل بناء تطبيق Android (Android Build Failed)": "مسار: مسار المشروع",
    "إضافة ملف جديد لمجلد مراقب (New File Added)": "مسار: مسار المجلد المراد مراقبته",

    # Files & Notes
    "إنشاء ملف جديد بمجلد (File Created In Dir)": "مسار: مسار المجلد (مثال: ~/Downloads)",
    "تعديل ملف إعدادات (Config File Modified)": "مسار: مسار ملف الإعدادات (مثال: ~/.bashrc)",
    "حذف ملف مهم (Important File Deleted)": "مسار: مسار الملف المراقَب",
    "وصول ملف لمجلد التنزيلات (Downloads File Arrived)": "نص: امتداد الملف المطلوب (مثال: .pdf أو اتركه فارغاً)",
    "تحميل ملف مضغوط Zip Arrived": "مسار: مسار مجلد التنزيلات أو فارغ لـ ~/Downloads",
    "تعديل محتوى ملاحظة (Note Modified)": "نص: عنوان الملاحظة أو مسارها",
    "ملاحظة تحتوي وسم (#urgent Tag)": "نص: اسم الوسم (مثال: #urgent)",
    "ملاحظة تحتوي كود أتمتة (WHEN... Code)": "نص: البادئة البحثية (مثل WHEN)",
    "فشل تنفيذ أتمتة (Automation Failed)": "لا يتطلب قيمة (اتركه فارغاً)",
    "تجاوز فترة عدم نشاط بالتحفيز (Inactivity Timeout)": "رقم: عدد الساعات (مثال: 24)",

    # Security
    "تغير ملف نظام حساس (Sensitive File Changed)": "مسار: مسار الملف الحساس (مثال: /etc/passwd)",
    "رصد تسجيل دخول غير معتاد (Unusual Login)": "لا يتطلب قيمة (اتركه فارغاً)",
    "برنامج غير معروف (Unknown Process)": "نص: اسم العملية أو النمط",
    "تجاوز استهلاك بيانات الشبكة MB (Data Exceeds)": "رقم: الاستهلاك بالميجابايت (مثال: 500)",
    "تكرار فشل تسجيل SSH (SSH Failed Attempts)": "رقم: عدد محاولات الفشل (مثال: 3)",
    "توقف خدمة الجدار الناري (Firewall Stopped)": "لا يتطلب قيمة (اتركه فارغاً)",
    "توصيل جهاز USB غير معروف (Unknown USB)": "لا يتطلب قيمة (اتركه فارغاً)",
    "تغير قواعد الجدار الناري (Firewall Rules Changed)": "لا يتطلب قيمة (اتركه فارغاً)",
    "رصد خدمة غير آمنة (Insecure Service Detected)": "رقم/نص: رقم المنفذ غير الآمن (مثال: 23 لـ Telnet)",
    "تكرار الحدث بشكل سريع جداً (Rapid Event Triggered)": "رقم: نافذة التكرار بالثواني (مثال: 5)",

    # Custom
    "نجاح أمر Bash (Exit 0) (Bash Command Succeeds)": "أمر Bash: ادخل الأمر المراد تشغيله واختبار نجاحه",
    "برنامج قيد التشغيل (Process Running/Found)": "نص: اسم العملية (مثال: firefox)",
    "برنامج متوقف عن العمل (Process Terminated)": "نص: اسم العملية (مثال: chrome)"
}

class ScheduleExecDialog(QDialog):
    def __init__(self, parent, filepath, cur_n, refresh_callback):
        super().__init__(parent)
        self.filepath = filepath
        self.refresh_callback = refresh_callback
        
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        self.setWindowTitle(tr('sched_dlg_title'))
        self.setMinimumSize(640, 500)
        self.setStyleSheet(get_common_qss())
        
        main_layout = QVBoxLayout(self)
        
        lbl = QLabel(tr('sched_main_header'))
        lbl.setStyleSheet(f"color: {FG_GREEN}; font-weight: bold; font-size: 14px;")
        main_layout.addWidget(lbl)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        
        ACCENT_COLOR = "#E5C07B"
        gb_style = f"""
            QGroupBox {{
                color: {ACCENT_COLOR};
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #3E3E42;
                border-radius: 6px;
                margin-top: 14px;
                padding-top: 14px;
                background-color: {BG_CARD};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
            }}
        """
        
        # Section 0: Enable Script Switch (Positioned at the TOP)
        g0 = QGroupBox("⚡ حالة تفعيل السكربت والأتمتة")
        g0.setStyleSheet(gb_style)
        l0 = QVBoxLayout(g0)
        self.script_enabled_cb = QCheckBox("⚡ تفعيل تشغيل السكربت التلقائي والأتمتة")
        self.script_enabled_cb.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 13px;")
        self.script_enabled_cb.setChecked(str(cur_n.get('script_enabled', 'true')).lower() in ['true', 'yes', '1'])
        l0.addWidget(self.script_enabled_cb)
        layout.addWidget(g0)
        
        # Section 1: Boot
        g1 = QGroupBox(tr('sec_boot'))
        g1.setStyleSheet(gb_style)
        l1 = QGridLayout(g1)
        
        self.boot_cb = QCheckBox(tr('cb_run_boot'))
        self.boot_cb.setChecked(cur_n.get('run_on_boot', 'false').lower() in ['true', 'yes', '1'])
        l1.addWidget(self.boot_cb, 0, 0, 1, 2)
        
        l1.addWidget(QLabel(tr('lbl_boot_delay')), 1, 0)
        self.delay_ent = QLineEdit(str(cur_n.get('boot_delay', '0')))
        l1.addWidget(self.delay_ent, 1, 1)
        layout.addWidget(g1)
        
        # Section 2: Time
        g2 = QGroupBox(tr('sec_time'))
        g2.setStyleSheet(gb_style)
        l2 = QVBoxLayout(g2)
        
        is_scheduled = bool(cur_n.get('scheduled_exec', '').strip())
        initial_sched_type = cur_n.get('schedule_type', 'once') if is_scheduled else 'none'
        
        self.bg_sched = QButtonGroup(self)
        self.rb_none = QRadioButton(tr('rb_none'))
        self.rb_once = QRadioButton(tr('rb_once'))
        self.rb_recurring = QRadioButton(tr('rb_recurring'))
        self.bg_sched.addButton(self.rb_none)
        self.bg_sched.addButton(self.rb_once)
        self.bg_sched.addButton(self.rb_recurring)
        
        l2.addWidget(self.rb_none)
        l2.addWidget(self.rb_once)
        l2.addWidget(self.rb_recurring)
        
        if initial_sched_type == 'none': self.rb_none.setChecked(True)
        elif initial_sched_type == 'once': self.rb_once.setChecked(True)
        else: self.rb_recurring.setChecked(True)
        
        self.dt_widget = QWidget()
        dt_layout = QVBoxLayout(self.dt_widget)
        self.dt_title = QLabel("Target/Start Date & Time:")
        self.dt_title.setStyleSheet(f"color: {FG_GREEN}; font-weight: bold;")
        dt_layout.addWidget(self.dt_title)
        
        cur_dt, cur_tm = "", ""
        if cur_n.get('scheduled_exec', ''):
            parts = cur_n['scheduled_exec'].split()
            cur_dt = parts[0] if len(parts) > 0 else ""
            cur_tm = parts[1] if len(parts) > 1 else ""
            
        self.get_dt_func = create_datetime_picker(dt_layout, cur_dt, cur_tm)
        l2.addWidget(self.dt_widget)
        
        self.interval_widget = QWidget()
        int_layout = QHBoxLayout(self.interval_widget)
        int_layout.addWidget(QLabel("Repeat Interval (if recurring):"))
        self.interval_opts = {
            "1 Minute": "1", "2 Minutes": "2", "5 Minutes": "5", "10 Minutes": "10",
            "15 Minutes": "15", "30 Minutes": "30", "1 Hour": "60", "2 Hours": "120",
            "6 Hours": "360", "12 Hours": "720", "1 Day": "1440"
        }
        self.interval_cb = QComboBox()
        self.interval_cb.addItems(list(self.interval_opts.keys()))
        int_layout.addWidget(self.interval_cb)
        int_layout.addStretch()
        l2.addWidget(self.interval_widget)
        
        layout.addWidget(g2)
        
        # Connect signals for toggling
        self.rb_none.toggled.connect(self.update_ui_state)
        self.rb_once.toggled.connect(self.update_ui_state)
        self.rb_recurring.toggled.connect(self.update_ui_state)
        self.update_ui_state()


        # Section 3: Event
        g3 = QGroupBox(tr('sec_event'))
        g3.setStyleSheet(gb_style)
        l3 = QGridLayout(g3)
        
        l3.addWidget(QLabel(tr('lbl_evt_cat')), 0, 0)
        self.evt_cat_cb = QComboBox()
        self.evt_cat_cb.addItems(["None"] + list(CATEGORIES_TRIGGERS.keys()))
        l3.addWidget(self.evt_cat_cb, 0, 1)
        
        l3.addWidget(QLabel(tr('lbl_evt_trig')), 1, 0)
        self.evt_trig_cb = QComboBox()
        l3.addWidget(self.evt_trig_cb, 1, 1)
        
        l3.addWidget(QLabel(tr('lbl_evt_val')), 2, 0)
        self.evt_val_ent = QLineEdit()
        l3.addWidget(self.evt_val_ent, 2, 1)

        self.evt_hint_lbl = QLabel("")
        self.evt_hint_lbl.setStyleSheet("color: #888888; font-size: 11px; font-style: italic;")
        l3.addWidget(self.evt_hint_lbl, 3, 1)
        
        self.evt_cat_cb.currentTextChanged.connect(self.update_triggers)
        self.evt_trig_cb.currentTextChanged.connect(self.update_trigger_hint)

        saved_cat = cur_n.get('event_category', 'None')
        cat_map = {
            "Battery": "System & Power", "Hardware": "System & Power", "System": "System & Power",
            "Network": "Network & Connectivity", "Files": "Files, Folders & Notes", "Custom": "Custom & Advanced"
        }
        saved_cat = cat_map.get(saved_cat, saved_cat)
        if saved_cat in list(CATEGORIES_TRIGGERS.keys()) + ["None"]:
            self.evt_cat_cb.setCurrentText(saved_cat)
        self.update_triggers()
        
        saved_trig = cur_n.get('event_trigger', '')
        if saved_trig:
            self.evt_trig_cb.setCurrentText(saved_trig)
            
        self.evt_val_ent.setText(cur_n.get('event_value', ''))
        self.update_trigger_hint()
        
        layout.addWidget(g3)
        
        # Section 4: Advanced
        g4 = QGroupBox(tr('sec_adv'))
        g4.setStyleSheet(gb_style)
        l4 = QVBoxLayout(g4)
        
        self.req_net_cb = QCheckBox(tr('cb_req_net'))
        self.req_net_cb.setChecked(cur_n.get('require_internet', 'false').lower() in ['true', 'yes', '1'])
        l4.addWidget(self.req_net_cb)
        
        self.catch_up_cb = QCheckBox(tr('cb_catch_up'))
        self.catch_up_cb.setChecked(cur_n.get('catch_up_on_boot', 'true').lower() in ['true', 'yes', '1'])
        l4.addWidget(self.catch_up_cb)
        
        self.play_sound_cb = QCheckBox(tr('cb_play_sound'))
        self.play_sound_cb.setChecked(cur_n.get('play_sound', 'true').lower() in ['true', 'yes', '1'])
        l4.addWidget(self.play_sound_cb)
        
        layout.addWidget(g4)
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = create_horizontal_button(tr('btn_save_cfg'), BTN_GREEN, self.save_sched, is_primary=True)
        btn_cancel = create_horizontal_button(tr('btn_cancel'), BTN_GRAY, self.reject)
        btn_layout.addWidget(btn_save)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        main_layout.addLayout(btn_layout)

    def update_ui_state(self):
        if self.rb_none.isChecked():
            self.dt_widget.hide()
            self.interval_widget.hide()
        elif self.rb_once.isChecked():
            self.dt_title.setText("Exact Execution Date & Time:")
            self.dt_widget.show()
            self.interval_widget.hide()
        else:
            self.dt_title.setText("Starting Date & Time (First Run):")
            self.dt_widget.show()
            self.interval_widget.show()

    def update_triggers(self):
        cat = self.evt_cat_cb.currentText()
        self.evt_trig_cb.clear()
        if cat in CATEGORIES_TRIGGERS:
            self.evt_trig_cb.addItems(CATEGORIES_TRIGGERS[cat])
        self.update_trigger_hint()

    def update_trigger_hint(self):
        trig = self.evt_trig_cb.currentText()
        hint = TRIGGER_HINTS.get(trig, "")
        if hint:
            self.evt_hint_lbl.setText(f"💡 Expected Value Type: {hint}")
            self.evt_val_ent.setPlaceholderText(hint)
        else:
            self.evt_hint_lbl.setText("")
            self.evt_val_ent.setPlaceholderText("Enter target value or condition parameter...")

    def save_sched(self):
        b_val = "true" if self.boot_cb.isChecked() else "false"
        b_delay = self.delay_ent.text().strip() or "0"
        
        if self.rb_none.isChecked():
            s_type = "none"
            sched_str = ""
            save_s_type = "once"
            i_mins = "0"
        else:
            d_val, t_val = self.get_dt_func()
            sched_str = f"{d_val} {t_val}"
            save_s_type = "once" if self.rb_once.isChecked() else "recurring"
            
            val = self.interval_cb.currentText().strip()
            if val in self.interval_opts:
                i_mins = self.interval_opts[val]
            else:
                nums = ''.join(c for c in val if c.isdigit())
                i_mins = nums if nums else "0"
                
        r_net = "true" if self.req_net_cb.isChecked() else "false"
        c_up = "true" if self.catch_up_cb.isChecked() else "false"
        p_snd = "true" if self.play_sound_cb.isChecked() else "false"
        
        e_cat = self.evt_cat_cb.currentText()
        e_trig = self.evt_trig_cb.currentText() if e_cat != "None" else ""
        e_val = self.evt_val_ent.text().strip() if e_cat != "None" else ""

        s_enabled = "true" if self.script_enabled_cb.isChecked() else "false"
        try:
            update_frontmatter_keys(self.filepath, {
                'run_on_boot': b_val,
                'boot_delay': b_delay,
                'scheduled_exec': sched_str,
                'schedule_type': save_s_type,
                'interval_mins': i_mins,
                'require_internet': r_net,
                'catch_up_on_boot': c_up,
                'play_sound': p_snd,
                'event_category': e_cat,
                'event_trigger': e_trig,
                'event_value': e_val,
                'script_enabled': s_enabled,
                'last_run': ''
            })
            update_boot_autostart_entries()
            self.refresh_callback()
            def run_sync():
                try: sync_notes_cli()
                except: pass
            threading.Thread(target=run_sync, daemon=True).start()
            self.accept()
            QMessageBox.information(self, "تم الحفظ والمزامنة", "✅ تم حفظ إعدادات الجدولة بنجاح!")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", str(e))


class ReminderDialog(QDialog):
    def __init__(self, parent, filepath, cur_n, refresh_callback):
        super().__init__(parent)
        self.filepath = filepath
        self.refresh_callback = refresh_callback
        
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        self.setWindowTitle("⏰ تخصيص وتحديد إعدادات التذكير")
        self.setMinimumSize(540, 520)
        self.setStyleSheet(get_common_qss())
        
        main_layout = QVBoxLayout(self)
        
        lbl = QLabel("⏰ إعداد وتخصيص التذكير للملاحظة")
        lbl.setStyleSheet(f"color: {FG_GREEN}; font-weight: bold; font-size: 15px;")
        main_layout.addWidget(lbl)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        
        ACCENT_COLOR = "#E5C07B"
        gb_style = f"""
            QGroupBox {{
                color: {ACCENT_COLOR};
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #3E3E42;
                border-radius: 6px;
                margin-top: 14px;
                padding-top: 14px;
                background-color: {BG_CARD};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
            }}
        """
        
        # Section 0: Enable Sound Alert (Positioned at the TOP)
        g0 = QGroupBox("🔊 خيارات التنبيه والصوت")
        g0.setStyleSheet(gb_style)
        l0 = QVBoxLayout(g0)
        self.play_sound_cb = QCheckBox("🔊 تفعيل تشغيل التنبيه والنغمة الصوتية عند التذكير")
        self.play_sound_cb.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 13px;")
        self.play_sound_cb.setChecked(cur_n.get('play_sound', 'true').lower() in ['true', 'yes', '1'])
        l0.addWidget(self.play_sound_cb)
        layout.addWidget(g0)

        # Section 1: Date & Time
        g1 = QGroupBox("📅 تاريخ ووقت التذكير (Date & Time)")
        g1.setStyleSheet(gb_style)
        l1 = QVBoxLayout(g1)
        
        cur_dt, cur_tm = "", ""
        if cur_n.get('reminder'):
            parts = cur_n['reminder'].split()
            cur_dt = parts[0] if len(parts) > 0 else ""
            cur_tm = parts[1] if len(parts) > 1 else ""

        self.get_dt_func = create_datetime_picker(l1, cur_dt, cur_tm)
        layout.addWidget(g1)
        
        # Section 2: Priority & Urgency
        g2 = QGroupBox("🎯 مستوى الأهمية ونغمة التنبيه (Priority & Tone)")
        g2.setStyleSheet(gb_style)
        l2 = QVBoxLayout(g2)
        
        self.bg_pri = QButtonGroup(self)
        self.rb_pri_quiet = QRadioButton("🟢 خفيف (Quiet): إشعار هادئ وبدون إلحاح")
        self.rb_pri_normal = QRadioButton("🟡 قياسي (Normal): إشعار قياسي وصوت تنبيه رنان")
        self.rb_pri_critical = QRadioButton("🔴 حرج جداً (Critical): تنبيه ملح بصوت إنذار وفتح النافذة بالمقدمة")
        
        self.bg_pri.addButton(self.rb_pri_quiet)
        self.bg_pri.addButton(self.rb_pri_normal)
        self.bg_pri.addButton(self.rb_pri_critical)
        
        l2.addWidget(self.rb_pri_quiet)
        l2.addWidget(self.rb_pri_normal)
        l2.addWidget(self.rb_pri_critical)
        
        cur_pri = cur_n.get('reminder_priority', 'normal').lower()
        if cur_pri == 'quiet':
            self.rb_pri_quiet.setChecked(True)
        elif cur_pri == 'critical':
            self.rb_pri_critical.setChecked(True)
        else:
            self.rb_pri_normal.setChecked(True)
            
        def preview_sound():
            if self.rb_pri_quiet.isChecked(): pri = "quiet"
            elif self.rb_pri_critical.isChecked(): pri = "critical"
            else: pri = "normal"
            try:
                play_sound(is_reminder=True, priority=pri)
            except Exception:
                pass

        btn_preview = create_horizontal_button("🔊 معاينة صوت النغمة المحددة", BTN_TEAL, preview_sound)
        l2.addWidget(btn_preview)
        
        layout.addWidget(g2)
        
        # Section 3: Repeat & Recurrence
        g3 = QGroupBox("🔄 التكرار والمرونة الزمنية (Repeat & Recurrence)")
        g3.setStyleSheet(gb_style)
        l3 = QVBoxLayout(g3)
        
        self.bg_repeat = QButtonGroup(self)
        self.rb_rep_none = QRadioButton("❌ بدون تكرار (مرة واحدة فقط)")
        self.rb_rep_daily = QRadioButton("🔄 تكرار يومياً (Daily)")
        self.rb_rep_weekly = QRadioButton("📅 تكرار أسبوعياً (Weekly)")
        self.rb_rep_custom = QRadioButton("⏱️ تكرار مخصص (كل فترة بالدقائق)")
        
        self.bg_repeat.addButton(self.rb_rep_none)
        self.bg_repeat.addButton(self.rb_rep_daily)
        self.bg_repeat.addButton(self.rb_rep_weekly)
        self.bg_repeat.addButton(self.rb_rep_custom)
        
        l3.addWidget(self.rb_rep_none)
        l3.addWidget(self.rb_rep_daily)
        l3.addWidget(self.rb_rep_weekly)
        l3.addWidget(self.rb_rep_custom)
        
        self.custom_interval_widget = QWidget()
        c_layout = QHBoxLayout(self.custom_interval_widget)
        c_layout.setContentsMargins(20, 0, 0, 0)
        c_layout.addWidget(QLabel("⏱️ فترة التكرار المخصص (بالدقائق):"))
        self.interval_ent = QLineEdit(str(cur_n.get('reminder_interval_mins', '30')))
        c_layout.addWidget(self.interval_ent)
        c_layout.addStretch()
        l3.addWidget(self.custom_interval_widget)
        
        cur_rep = cur_n.get('reminder_repeat', 'none').lower()
        if cur_rep == 'daily': self.rb_rep_daily.setChecked(True)
        elif cur_rep == 'weekly': self.rb_rep_weekly.setChecked(True)
        elif cur_rep == 'custom': self.rb_rep_custom.setChecked(True)
        else: self.rb_rep_none.setChecked(True)
        
        def update_rep_state():
            if self.rb_rep_custom.isChecked():
                self.custom_interval_widget.show()
            else:
                self.custom_interval_widget.hide()
                
        self.rb_rep_none.toggled.connect(update_rep_state)
        self.rb_rep_daily.toggled.connect(update_rep_state)
        self.rb_rep_weekly.toggled.connect(update_rep_state)
        self.rb_rep_custom.toggled.connect(update_rep_state)
        update_rep_state()
        
        layout.addWidget(g3)
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = create_horizontal_button("⏰ حفظ التذكير", BTN_BLUE, self.save_rem, is_primary=True)
        btn_clear = create_horizontal_button("🗑️ مسح التذكير", BTN_RED, self.clear_rem)
        btn_cancel = create_horizontal_button("❌ إلغاء", BTN_GRAY, self.reject)
        
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        main_layout.addLayout(btn_layout)

    def closeEvent(self, event):
        stop_current_sound()
        super().closeEvent(event)

    def reject(self):
        stop_current_sound()
        super().reject()

    def save_rem(self):
        dt, tm = self.get_dt_func()
        rem_str = f"{dt} {tm}"
        p_snd = "true" if self.play_sound_cb.isChecked() else "false"
        
        if self.rb_pri_quiet.isChecked(): pri = "quiet"
        elif self.rb_pri_critical.isChecked(): pri = "critical"
        else: pri = "normal"
        
        if self.rb_rep_daily.isChecked(): rep = "daily"
        elif self.rb_rep_weekly.isChecked(): rep = "weekly"
        elif self.rb_rep_custom.isChecked(): rep = "custom"
        else: rep = "none"
        
        mins = self.interval_ent.text().strip() or "30"
        
        try:
            update_frontmatter_keys(self.filepath, {
                'reminder': rem_str,
                'play_sound': p_snd,
                'reminder_priority': pri,
                'reminder_repeat': rep,
                'reminder_interval_mins': mins
            })
            self.refresh_callback()
            def run_sync():
                try: sync_notes_cli()
                except: pass
            threading.Thread(target=run_sync, daemon=True).start()
            self.accept()
            QMessageBox.information(self, "تم الحفظ والمزامنة", f"✅ تم حفظ التذكير المخصص بنجاح:\n📅 الموعد: {rem_str}\n🎯 الأهمية: {pri}\n🔄 التكرار: {rep}")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", str(e))

    def clear_rem(self):
        try:
            update_frontmatter_keys(self.filepath, {
                'reminder': "",
                'reminder_repeat': "none"
            })
            self.refresh_callback()
            def run_sync():
                try: sync_notes_cli()
                except: pass
            threading.Thread(target=run_sync, daemon=True).start()
            self.accept()
            QMessageBox.information(self, "تمت الإزالة", "🗑️ تم مسح/إلغاء التذكير الخاص بهذه الملاحظة!")
        except Exception as e:
            QMessageBox.critical(self, "خطأ", str(e))


class NoteViewDialog(QDialog):
    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.result_action = ""
        self.is_editing = False
        self.is_markdown_rendered = True
        
        increase_note_access(filepath)
        self.n_data = parse_note_file(filepath)
        
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        self.setWindowTitle(f"تفاصيل الملاحظة: {self.n_data['title']}")
        self.resize(1180, 740)
        self.setMinimumSize(1020, 640)
        
        CLR_MAIN_BG = "#0D0F17"
        CLR_SIDEBAR_BG = "#131622"
        CLR_CARD_BG = "#161928"
        CLR_HEADER_BG = "#161926"
        CLR_BORDER = "#232738"
        CLR_PURPLE = "#7C3AED"
        CLR_BLUE = "#2563EB"
        CLR_GREEN = "#10B981"
        CLR_RED = "#EF4444"
        CLR_TEXT_MUTED = "#64748B"
        
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
            QTextEdit, QTextBrowser {{
                background-color: {CLR_CARD_BG};
                color: #E2E8F0;
                border: 1px solid {CLR_BORDER};
                border-radius: 12px;
                padding: 26px 30px;
                font-size: 14px;
                line-height: 1.6;
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
        
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(32, 24, 32, 32)
        root_layout.setSpacing(20)
        
        # 1. Top Header Bar (Back button + Window Title)
        top_bar = QHBoxLayout()
        
        btn_back = QPushButton("← عودة")
        btn_back.setCursor(Qt.PointingHandCursor)
        btn_back.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #94A3B8;
                font-size: 14px;
                font-weight: bold;
                border: none;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
            }}
        """)
        btn_back.clicked.connect(self.reject)
        top_bar.addWidget(btn_back)
        
        top_bar.addStretch()
        
        title_box = QHBoxLayout()
        t_icon = QLabel("📓")
        t_icon.setStyleSheet("font-size: 20px; background: transparent;")
        t_lbl = QLabel("تفاصيل الملاحظة")
        t_lbl.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; background: transparent;")
        title_box.addWidget(t_lbl)
        title_box.addWidget(t_icon)
        top_bar.addLayout(title_box)
        
        root_layout.addLayout(top_bar)
        
        # 2. Main Two-Column Splitter Layout
        split_layout = QHBoxLayout()
        split_layout.setSpacing(24)
        
        # COLUMN 1: Main Content Column (Left / Center)
        col1 = QVBoxLayout()
        col1.setSpacing(16)
        
        # Toolbar Row inside Main Content Column
        toolbar = QHBoxLayout()
        
        n_type = self.n_data.get('type', 'Note')
        is_script = (n_type == 'Script')
        
        if is_script:
            # Left action: Run Now / Execute button
            self.btn_exec_now = QPushButton("▷  تشغيل الآن")
            self.btn_exec_now.setCursor(Qt.PointingHandCursor)
            self.btn_exec_now.setStyleSheet(f"""
                QPushButton {{
                    background-color: {CLR_PURPLE};
                    color: #FFFFFF;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 8px 18px;
                    border-radius: 8px;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: #6D28D9;
                }}
            """)
            self.btn_exec_now.clicked.connect(self.on_exec)
            toolbar.addWidget(self.btn_exec_now)
            
            is_enabled = str(self.n_data.get('script_enabled', 'true')).lower() in ['true', 'yes', '1']
            toggle_txt = "⏸️ تعطيل السكربت" if is_enabled else "▶️ تفعيل السكربت"
            toggle_bg = "#451A1A" if is_enabled else "#064E3B"
            toggle_border = "#991B1B" if is_enabled else "#059669"
            toggle_fg = "#F87171" if is_enabled else "#34D399"
            
            self.btn_toggle_script = QPushButton(toggle_txt)
            self.btn_toggle_script.setCursor(Qt.PointingHandCursor)
            self.btn_toggle_script.setStyleSheet(f"""
                QPushButton {{
                    background-color: {toggle_bg};
                    color: {toggle_fg};
                    font-weight: bold;
                    font-size: 13px;
                    padding: 8px 16px;
                    border-radius: 8px;
                    border: 1px solid {toggle_border};
                }}
            """)
            self.btn_toggle_script.clicked.connect(self.on_toggle_script_inside)
            toolbar.addWidget(self.btn_toggle_script)

        toolbar.addStretch()
        
        # Right Segmented Tab Buttons: Edit, Markdown View, Raw View
        self.btn_edit = QPushButton("✏️ تعديل")
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: #161926;
                color: #94A3B8;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                border-radius: 8px;
                border: 1px solid {CLR_BORDER};
            }}
            QPushButton:hover {{
                background-color: #202438;
                color: #FFFFFF;
            }}
        """)
        self.btn_edit.clicked.connect(self.toggle_edit)
        
        self.btn_md_view = QPushButton("Ⓜ️ عرض Markdown")
        self.btn_md_view.setCursor(Qt.PointingHandCursor)
        self.btn_md_view.setStyleSheet(f"""
            QPushButton {{
                background-color: {CLR_PURPLE};
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                border-radius: 8px;
                border: none;
            }}
        """)
        self.btn_md_view.clicked.connect(lambda: self.set_view_mode(True))
        
        self.btn_raw_view = QPushButton("</> عرض خام")
        self.btn_raw_view.setCursor(Qt.PointingHandCursor)
        self.btn_raw_view.setStyleSheet(f"""
            QPushButton {{
                background-color: #161926;
                color: #94A3B8;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                border-radius: 8px;
                border: 1px solid {CLR_BORDER};
            }}
        """)
        self.btn_raw_view.clicked.connect(lambda: self.set_view_mode(False))
        
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_md_view)
        toolbar.addWidget(self.btn_raw_view)
        
        col1.addLayout(toolbar)
        
        # Note Text Box (Qt Native Markdown & HTML Browser Widget)
        self.txt_box = QTextBrowser()
        self.txt_box.setReadOnly(True)
        self.txt_box.setOpenExternalLinks(True)
        self.update_text_display()
        col1.addWidget(self.txt_box, 1)
        
        # Attachment Preview Card (if any)
        att = self.n_data.get('attachment', '')
        if att and att != "none":
            abs_att = os.path.join(NOTES_DIR, att)
            if not os.path.exists(abs_att):
                abs_att = os.path.join(NOTES_DIR, "uploads", os.path.basename(att))
            if os.path.exists(abs_att):
                att_card = QFrame()
                att_card.setStyleSheet(f"background-color: {CLR_CARD_BG}; border: 1px solid {CLR_BORDER}; border-radius: 10px; padding: 12px;")
                att_layout = QVBoxLayout(att_card)
                
                ext = os.path.splitext(abs_att)[1].lower()
                is_image = ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff']
                is_audio = ext in ['.wav', '.mp3', '.ogg', '.oga', '.m4a', '.flac']
                
                sz = os.path.getsize(abs_att)
                size_str = f"{sz / (1024*1024):.2f} MB" if sz >= 1048576 else f"{int(sz/1024)} KB"
                
                if is_image:
                    img_lbl = QLabel()
                    pixmap = QPixmap(abs_att)
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(480, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        img_lbl.setPixmap(pixmap)
                        att_layout.addWidget(img_lbl)
                    msg = f"📷 صورة مرفقة: {os.path.basename(abs_att)} ({size_str})"
                elif is_audio:
                    msg = f"🎙️ تسجيل صوتي مرفق: {os.path.basename(abs_att)} ({size_str})"
                else:
                    msg = f"📎 ملف مرفق: {os.path.basename(abs_att)} ({size_str})"
                
                msg_lbl = QLabel(msg)
                msg_lbl.setStyleSheet(f"color: {CLR_GREEN}; font-weight: bold; border: none;")
                att_layout.addWidget(msg_lbl)
                
                att_btns = QHBoxLayout()
                open_text = "👁️ عرض الصورة" if is_image else ("▶️ تشغيل الصوت" if is_audio else "👁️ فتح الملف")
                btn_open_att = QPushButton(open_text)
                btn_open_att.setStyleSheet(f"background-color: {CLR_BLUE}; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
                btn_open_att.clicked.connect(lambda: open_file_cross_platform(abs_att))
                
                btn_open_dir = QPushButton("📁 فتح المجلد")
                btn_open_dir.setStyleSheet("background-color: #1F2436; color: white; padding: 6px 12px; border-radius: 6px;")
                btn_open_dir.clicked.connect(lambda: open_file_cross_platform(os.path.dirname(abs_att)))
                
                att_btns.addWidget(btn_open_att)
                att_btns.addWidget(btn_open_dir)
                att_btns.addStretch()
                att_layout.addLayout(att_btns)
                
                col1.addWidget(att_card)
                
        split_layout.addLayout(col1, 1)
        
        # COLUMN 2: Metadata Right Sidebar (Fixed width ~310px)
        self.side_col = QVBoxLayout()
        self.side_col.setSpacing(12)
        
        # CARD 1: Note Information (معلومات الملاحظة)
        card1 = QFrame()
        card1.setStyleSheet(f"background-color: {CLR_CARD_BG}; border: 1px solid {CLR_BORDER}; border-radius: 12px;")
        c1_layout = QVBoxLayout(card1)
        c1_layout.setContentsMargins(14, 14, 14, 14)
        c1_layout.setSpacing(10)
        
        c1_header = QLabel("معلومات الملاحظة")
        c1_header.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold; background: transparent;")
        c1_layout.addWidget(c1_header)
        
        self.info_table_widget = QWidget()
        self.info_table_layout = QVBoxLayout(self.info_table_widget)
        self.info_table_layout.setContentsMargins(0, 0, 0, 0)
        self.info_table_layout.setSpacing(8)
        c1_layout.addWidget(self.info_table_widget)
        
        self.side_col.addWidget(card1)
        
        # CARD 2: Boot Schedule / Reminder Card
        self.card2 = QFrame()
        self.card2.setStyleSheet(f"background-color: {CLR_CARD_BG}; border: 1px solid {CLR_BORDER}; border-radius: 12px;")
        c2_layout = QVBoxLayout(self.card2)
        c2_layout.setContentsMargins(14, 14, 14, 14)
        c2_layout.setSpacing(8)
        
        self.c2_head = QLabel("📅  جدول الإقلاع / التذكير")
        self.c2_head.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold; background: transparent;")
        self.c2_sub = QLabel("يتم تشغيل التنبيه أو التذكير تلقائياً حسب الجدول.")
        self.c2_sub.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 11px; background: transparent;")
        
        c2_layout.addWidget(self.c2_head)
        c2_layout.addWidget(self.c2_sub)
        
        self.sched_badge = QLabel("⚪ غير مجدول")
        self.sched_badge.setStyleSheet("color: #34D399; font-weight: bold; font-size: 12px; background: #064E3B; padding: 6px 10px; border-radius: 6px; border: 1px solid #059669;")
        c2_layout.addWidget(self.sched_badge)
        
        self.btn_edit_sched = QPushButton("📅 تعديل الجدول / التذكير")
        self.btn_edit_sched.setCursor(Qt.PointingHandCursor)
        self.btn_edit_sched.setStyleSheet(f"background-color: #1F2436; color: white; border: 1px solid {CLR_BORDER}; padding: 7px; border-radius: 8px; font-size: 12px; font-weight: bold;")
        self.btn_edit_sched.clicked.connect(self.on_schedule_exec)
        c2_layout.addWidget(self.btn_edit_sched)
        
        self.side_col.addWidget(self.card2)

        # CARD 3: Status Toggle Card (الحالة)
        card3 = QFrame()
        card3.setStyleSheet(f"background-color: {CLR_CARD_BG}; border: 1px solid {CLR_BORDER}; border-radius: 12px;")
        c3_layout = QVBoxLayout(card3)
        c3_layout.setContentsMargins(14, 14, 14, 14)
        c3_layout.setSpacing(6)
        
        c3_head_layout = QHBoxLayout()
        c3_title = QLabel("الحالة")
        c3_title.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold; background: transparent;")
        self.c3_toggle = QLabel("🟢 مفعلة")
        self.c3_toggle.setStyleSheet("color: #34D399; font-weight: bold; font-size: 12px; background: #064E3B; padding: 4px 8px; border-radius: 6px;")
        c3_head_layout.addWidget(c3_title)
        c3_head_layout.addStretch()
        c3_head_layout.addWidget(self.c3_toggle)
        c3_layout.addLayout(c3_head_layout)
        
        self.c3_sub = QLabel("الملاحظة والسكربت التلقائي مفعلان ويعملان بشكل طبيعي.")
        self.c3_sub.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 11px; background: transparent;")
        c3_layout.addWidget(self.c3_sub)
        
        self.side_col.addWidget(card3)

        # CARD 4: Delete Danger Zone (حذف الملاحظة)
        card4 = QFrame()
        card4.setStyleSheet("background-color: #1F141B; border: 1px solid #3D1B26; border-radius: 12px;")
        c4_layout = QVBoxLayout(card4)
        c4_layout.setContentsMargins(14, 14, 14, 14)
        c4_layout.setSpacing(8)
        
        c4_title = QLabel("🗑️  حذف الملاحظة")
        c4_title.setStyleSheet("color: #EF4444; font-size: 14px; font-weight: bold; background: transparent;")
        c4_sub = QLabel("سيتم أرشفة وحذف الملاحظة نهائياً ولا يمكن استعادتها.")
        c4_sub.setStyleSheet("color: #9CA3AF; font-size: 11px; background: transparent;")
        
        c4_layout.addWidget(c4_title)
        c4_layout.addWidget(c4_sub)
        
        btn_del_danger = QPushButton("حذف الملاحظة")
        btn_del_danger.setCursor(Qt.PointingHandCursor)
        btn_del_danger.setStyleSheet("""
            QPushButton {
                background-color: #421B27;
                color: #F87171;
                border: 1px solid #6B2337;
                border-radius: 8px;
                padding: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #6B2337;
                color: #FFFFFF;
            }
        """)
        btn_del_danger.clicked.connect(self.on_delete)
        c4_layout.addWidget(btn_del_danger)
        
        self.side_col.addWidget(card4)
        self.side_col.addStretch()
        
        # Wrap side column in a widget with fixed width
        side_widget = QWidget()
        side_widget.setFixedWidth(310)
        side_widget.setLayout(self.side_col)
        
        split_layout.addWidget(side_widget)
        root_layout.addLayout(split_layout, 1)

        self.refresh_sub_header()
        center_window(self, 1180, 740)

    def trigger_instant_bg_sync(self):
        def run_sync():
            try: sync_notes_cli()
            except: pass
        threading.Thread(target=run_sync, daemon=True).start()

    def set_view_mode(self, is_md):
        self.is_markdown_rendered = is_md
        CLR_PURPLE = "#7C3AED"
        CLR_BORDER = "#232738"
        if is_md:
            self.btn_md_view.setStyleSheet(f"background-color: {CLR_PURPLE}; color: #FFFFFF; font-weight: bold; font-size: 13px; padding: 8px 16px; border-radius: 8px; border: none;")
            self.btn_raw_view.setStyleSheet(f"background-color: #161926; color: #94A3B8; font-weight: bold; font-size: 13px; padding: 8px 16px; border-radius: 8px; border: 1px solid {CLR_BORDER};")
        else:
            self.btn_raw_view.setStyleSheet(f"background-color: {CLR_PURPLE}; color: #FFFFFF; font-weight: bold; font-size: 13px; padding: 8px 16px; border-radius: 8px; border: none;")
            self.btn_md_view.setStyleSheet(f"background-color: #161926; color: #94A3B8; font-weight: bold; font-size: 13px; padding: 8px 16px; border-radius: 8px; border: 1px solid {CLR_BORDER};")
        self.update_text_display()

    def refresh_sub_header(self):
        # Clear info table
        while self.info_table_layout.count():
            child = self.info_table_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.n_data = parse_note_file(self.filepath)
        data = self.n_data
        n_type = data.get('type', 'Note')

        def add_info_row(label_str, val_widget):
            row = QHBoxLayout()
            lbl = QLabel(label_str)
            lbl.setStyleSheet("color: #94A3B8; font-size: 12px; background: transparent;")
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val_widget)
            self.info_table_layout.addLayout(row)

        # 1. Type
        type_txt = "سكربت" if n_type == 'Script' else ("مهمة" if n_type == 'Task' else "ملاحظة")
        type_badge = QLabel(type_txt)
        type_badge.setStyleSheet("background-color: #281A45; color: #C084FC; font-weight: bold; font-size: 11px; padding: 3px 8px; border-radius: 5px;")
        add_info_row("🔮 النوع", type_badge)

        # 2. Category
        cat_lbl = QLabel(data.get('category', 'عام'))
        cat_lbl.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 12px; background: transparent;")
        add_info_row("📁 الفئة", cat_lbl)

        # 3. Visits
        v_lbl = QLabel(str(data.get('access', 0)))
        v_lbl.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 12px; background: transparent;")
        add_info_row("👁️ عدد الزيارات", v_lbl)

        # 4. Created
        c_lbl = QLabel(data.get('created', 'غير محدد'))
        c_lbl.setStyleSheet("color: #FFFFFF; font-size: 12px; background: transparent;")
        add_info_row("📅 تاريخ الإنشاء", c_lbl)

        # 5. Last updated
        mod_lbl = QLabel(data.get('last_updated', 'مؤخراً'))
        mod_lbl.setStyleSheet("color: #FFFFFF; font-size: 12px; background: transparent;")
        add_info_row("✏️ آخر تعديل", mod_lbl)

        # 6. Auto boot / Reminder
        is_boot = str(data.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1']
        is_script = (n_type == 'Script')
        if is_script:
            boot_badge = QLabel("● مفعل" if is_boot else "● معطل")
            if is_boot:
                boot_badge.setStyleSheet("background-color: #064E3B; color: #34D399; font-weight: bold; font-size: 11px; padding: 3px 8px; border-radius: 5px;")
            else:
                boot_badge.setStyleSheet("background-color: #1E293B; color: #94A3B8; font-weight: bold; font-size: 11px; padding: 3px 8px; border-radius: 5px;")
            add_info_row("⚡ الإقلاع التلقائي", boot_badge)
        else:
            rem = data.get('reminder', '')
            if rem:
                rem_lbl = QLabel(rem)
                rem_lbl.setStyleSheet("color: #FBBF24; font-weight: bold; font-size: 11px; background: #3D3812; padding: 3px 8px; border-radius: 5px;")
                add_info_row("⏰ التذكير", rem_lbl)

        # Update Card 2 Schedule / Reminder info
        s_exec = data.get('scheduled_exec', '')
        rem = data.get('reminder', '')
        
        if is_script:
            self.c2_head.setText("📅  جدول الإقلاع والسكربت")
            self.c2_sub.setText("تشغيل الأتمتة أو السكربت تلقائياً حسب الجدول المقتطع.")
            self.btn_edit_sched.setText("📅 تعديل جدول السكربت")
            if s_exec:
                self.sched_badge.setText(f"🟢 مجدول: {s_exec}")
            elif is_boot:
                self.sched_badge.setText("⚡ مفعل عند الإقلاع")
            else:
                self.sched_badge.setText("⚪ غير مجدول")
        else:
            self.c2_head.setText("⏰  التذكير والتوقيت")
            self.c2_sub.setText("تخصيص وقت لتذكيرك بهذه الملاحظة مع نغمة أو تنبيه.")
            self.btn_edit_sched.setText("⏰ ضبط التذكير والتوقيت")
            if rem:
                self.sched_badge.setText(f"🔔 تذكير: {rem}")
            else:
                self.sched_badge.setText("⚪ بدون تذكير")

        # Update Card 3 Status Card
        if is_script:
            is_script_enabled = str(data.get('script_enabled', 'true')).lower() in ['true', 'yes', '1']
            if is_script_enabled:
                self.c3_toggle.setText("🟢 مفعل")
                self.c3_toggle.setStyleSheet("color: #34D399; font-weight: bold; font-size: 12px; background: #064E3B; padding: 4px 8px; border-radius: 6px;")
                self.c3_sub.setText("الملاحظة والسكربت التلقائي مفعلان ويعملان بشكل طبيعي.")
            else:
                self.c3_toggle.setText("🔴 معطل")
                self.c3_toggle.setStyleSheet("color: #F87171; font-weight: bold; font-size: 12px; background: #451A1A; padding: 4px 8px; border-radius: 6px;")
                self.c3_sub.setText("السكربت معطل حالياً ولن يتم تشغيله تلقائياً.")
        else:
            if n_type == 'Task':
                st = data.get('status', 'todo').lower()
                st_map = {'done': ('✅ مكتملة', '#064E3B', '#34D399'), 'in_progress': ('⏳ قيد التنفيذ', '#3D3812', '#FBBF24')}
                txt, bg, fg = st_map.get(st, ('📌 قيد الانتظار', '#1E293B', '#94A3B8'))
                self.c3_toggle.setText(txt)
                self.c3_toggle.setStyleSheet(f"color: {fg}; font-weight: bold; font-size: 12px; background: {bg}; padding: 4px 8px; border-radius: 6px;")
                self.c3_sub.setText("حالة المهمة الحالية في لوحة كانبان.")
            else:
                self.c3_toggle.setText("📌 نشطة")
                self.c3_toggle.setStyleSheet("color: #34D399; font-weight: bold; font-size: 12px; background: #064E3B; padding: 4px 8px; border-radius: 6px;")
                self.c3_sub.setText("الملاحظة محفوظة ومتاحة للاستخدام.")

    def on_toggle_script_inside(self):
        curr_enabled = str(self.n_data.get('script_enabled', 'true')).lower() in ['true', 'yes', '1']
        new_val = 'false' if curr_enabled else 'true'
        
        if new_val == 'true':
            has_sched = bool(self.n_data.get('scheduled_exec', '').strip()) or \
                        (str(self.n_data.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1']) or \
                        (bool(self.n_data.get('event_trigger', '').strip()) and self.n_data.get('event_category', 'None') != 'None') or \
                        (bool(self.n_data.get('reminder', '').strip()))
            if not has_sched:
                QMessageBox.information(self, "تحديد الجدول", "ℹ️ هذا السكربت غير مجدول بعد.\nسأفتح لك نافذة الإعدادات الآن لتحديد الموعد أو الشروط المراد تفعيل السكربت بناءً عليها.")
                dlg = ScheduleExecDialog(self, self.filepath, self.n_data, self.refresh_sub_header)
                if dlg.exec_() == QDialog.Accepted:
                    update_frontmatter_keys(self.filepath, {'script_enabled': 'true'})
                    self.n_data['script_enabled'] = 'true'
                    self.refresh_sub_header()
                    self.trigger_instant_bg_sync()
                    if hasattr(self, 'btn_toggle_script'):
                        self.btn_toggle_script.setText("⏸️ تعطيل السكربت")
                        self.btn_toggle_script.setStyleSheet("""
                            QPushButton {
                                background-color: #451A1A;
                                color: #F87171;
                                font-weight: bold;
                                font-size: 13px;
                                padding: 8px 16px;
                                border-radius: 8px;
                                border: 1px solid #991B1B;
                            }
                        """)
                return

        update_frontmatter_keys(self.filepath, {'script_enabled': new_val})
        self.n_data['script_enabled'] = new_val
        self.refresh_sub_header()
        self.trigger_instant_bg_sync()
        if hasattr(self, 'btn_toggle_script'):
            if new_val == 'true':
                self.btn_toggle_script.setText("⏸️ تعطيل السكربت")
                self.btn_toggle_script.setStyleSheet("""
                    QPushButton {
                        background-color: #451A1A;
                        color: #F87171;
                        font-weight: bold;
                        font-size: 13px;
                        padding: 8px 16px;
                        border-radius: 8px;
                        border: 1px solid #991B1B;
                    }
                """)
                QMessageBox.information(self, "حالة السكربت", "✅ تم تفعيل السكربت بنجاح!")
            else:
                self.btn_toggle_script.setText("▶️ تفعيل السكربت")
                self.btn_toggle_script.setStyleSheet("""
                    QPushButton {
                        background-color: #064E3B;
                        color: #34D399;
                        font-weight: bold;
                        font-size: 13px;
                        padding: 8px 16px;
                        border-radius: 8px;
                        border: 1px solid #059669;
                    }
                """)
                QMessageBox.information(self, "حالة السكربت", "⏸️ تم تعطيل السكربت بنجاح!")


    def update_text_display(self):
        body = self.n_data.get('body', '')
        if self.is_markdown_rendered:
            html = convert_markdown_to_styled_html(body)
            self.txt_box.setHtml(html)
            self.txt_box.setLayoutDirection(Qt.RightToLeft if is_arabic(body) else Qt.LeftToRight)
        else:
            self.txt_box.setPlainText(body)
            apply_rtl_to_widget(self.txt_box, body)

    def toggle_edit(self):
        CLR_CARD_BG = "#161928"
        FG_TEXT = "#E2E8F0"
        if not self.is_editing:
            self.is_editing = True
            self.txt_box.setReadOnly(False)
            self.txt_box.setStyleSheet(f"background-color: {CLR_CARD_BG}; color: {FG_TEXT}; border: 1px solid #7C3AED;")
            self.n_data = parse_note_file(self.filepath)
            self.txt_box.setPlainText(self.n_data['body'])
            self.btn_edit.setText("💾 حفظ التعديلات")
            QMessageBox.information(self, "تحرير الملاحظة", "✏️ يمكنك الآن تحرير نص الملاحظة مباشرة في المربع فوق!\nانقر '💾 حفظ التعديلات' عند الانتهاء.")
        else:
            new_body = self.txt_box.toPlainText().strip()
            try:
                with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as fp: raw = fp.read()
                c = 0
                lines = raw.splitlines()
                front_lines = []
                for l in lines:
                    front_lines.append(l)
                    if l.strip() == '---':
                        c += 1
                        if c == 2: break
                new_file_content = "\n".join(front_lines) + "\n" + new_body + "\n"
                with open(self.filepath, 'w', encoding='utf-8') as fp: fp.write(new_file_content)

                self.is_editing = False
                self.txt_box.setPlainText(new_body)
                apply_rtl_to_widget(self.txt_box, new_body)
                self.txt_box.setReadOnly(True)
                self.txt_box.setStyleSheet(f"background-color: {CLR_CARD_BG}; color: {FG_TEXT}; border: 1px solid #232738;")
                self.btn_edit.setText("✏️ تعديل")
                self.refresh_sub_header()
                self.trigger_instant_bg_sync()
                QMessageBox.information(self, "تم الحفظ والمزامنة", "✅ تم حفظ التعديلات ومزامنتها بنجاح!")
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"تعذر حفظ التعديلات: {e}")

    def on_exec(self):
        self.result_action = "EXEC"
        self.accept()

    def on_schedule_exec(self):
        n_type = self.n_data.get('type', 'Note')
        if n_type == 'Script':
            dlg = ScheduleExecDialog(self, self.filepath, self.n_data, self.refresh_sub_header)
            dlg.exec_()
        else:
            dlg = ReminderDialog(self, self.filepath, self.n_data, self.refresh_sub_header)
            dlg.exec_()

    def on_delete(self):
        reply = QMessageBox.question(self, "تأكيد الحذف", "هل أنت تأكيد من أرشفة/حذف هذه الملاحظة نهائياً؟",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            archive_note(self.filepath)
            self.trigger_instant_bg_sync()
            self.result_action = "DELETE"
            self.accept()

def show_note_view_window(filepath, parent=None):
    if not os.path.exists(filepath):
        return None
    if parent:
        parent.hide()
    try:
        dlg = NoteViewDialog(filepath)
        dlg.exec_()
        return dlg.result_action
    finally:
        if parent:
            parent.show()
            parent.raise_()
            parent.activateWindow()
