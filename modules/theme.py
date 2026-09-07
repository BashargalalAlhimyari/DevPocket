import os

THEME_FILE = os.path.expanduser("~/.developer-notes/.config/theme.txt")

def get_theme():
    if os.path.exists(THEME_FILE):
        try:
            with open(THEME_FILE, 'r', encoding='utf-8') as f:
                t = f.read().strip().lower()
                if t in ['dark', 'light']:
                    return t
        except Exception:
            pass
    return 'dark'


def set_theme(theme_name):
    try:
        os.makedirs(os.path.dirname(THEME_FILE), exist_ok=True)
        with open(THEME_FILE, 'w', encoding='utf-8') as f:
            f.write(theme_name.lower())
    except Exception as e:
        print(f"Error saving theme setting: {e}")


def get_theme_colors(theme_name=None):
    if theme_name is None:
        theme_name = get_theme()

    if theme_name == 'light':
        return {
            'BG_MAIN': '#F8FAFC',
            'BG_SIDEBAR': '#F1F5F9',
            'BG_CARD': '#FFFFFF',
            'CLR_MAIN_BG': '#F8FAFC',
            'CLR_SIDEBAR_BG': '#F1F5F9',
            'CLR_CARD_BG': '#FFFFFF',
            'CLR_HEADER_BG': '#F1F5F9',
            'CLR_ROW_BG': '#FFFFFF',
            'CLR_ROW_HOVER': '#E2E8F0',
            'CLR_BORDER': '#CBD5E1',
            'CLR_PURPLE': '#7C3AED',
            'CLR_BLUE': '#2563EB',
            'CLR_GREEN': '#059669',
            'CLR_YELLOW': '#D97706',
            'CLR_RED': '#DC2626',
            'CLR_TEXT_MUTED': '#475569',
            'FG_TEXT': '#0F172A',
            'FG_MUTED': '#475569',
            'FG_GREEN': '#059669',
            'BTN_BG': '#E2E8F0',
            'BTN_HOVER': '#CBD5E1',
            'IS_DARK': False
        }
    else:
        return {
            'BG_MAIN': '#0D0F17',
            'BG_SIDEBAR': '#131622',
            'BG_CARD': '#171A29',
            'CLR_MAIN_BG': '#0D0F17',
            'CLR_SIDEBAR_BG': '#131622',
            'CLR_CARD_BG': '#171A29',
            'CLR_HEADER_BG': '#161926',
            'CLR_ROW_BG': '#181B2B',
            'CLR_ROW_HOVER': '#202438',
            'CLR_BORDER': '#232738',
            'CLR_PURPLE': '#7C3AED',
            'CLR_BLUE': '#2563EB',
            'CLR_GREEN': '#10B981',
            'CLR_YELLOW': '#F59E0B',
            'CLR_RED': '#EF4444',
            'CLR_TEXT_MUTED': '#94A3B8',
            'FG_TEXT': '#FFFFFF',
            'FG_MUTED': '#94A3B8',
            'FG_GREEN': '#10B981',
            'BTN_BG': '#1F2436',
            'BTN_HOVER': '#2A3048',
            'IS_DARK': True
        }


def get_theme_qss(theme_name=None):
    c = get_theme_colors(theme_name)
    bg_main = c['BG_MAIN']
    bg_card = c['BG_CARD']
    bg_sidebar = c['BG_SIDEBAR']
    border = c['CLR_BORDER']
    fg_text = c['FG_TEXT']
    fg_muted = c['FG_MUTED']

    return f"""
    QWidget {{
        background-color: {bg_main};
        color: {fg_text};
        font-family: 'Segoe UI', 'DejaVu Sans', sans-serif;
    }}
    QDialog {{
        background-color: {bg_main};
        color: {fg_text};
    }}
    QPushButton {{
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: bold;
    }}
    QTreeWidget {{
        background-color: {bg_card};
        color: {fg_text};
        alternate-background-color: {bg_sidebar};
        border: 1px solid {border};
        border-radius: 8px;
    }}
    QTreeWidget::item {{
        padding: 6px;
        border-bottom: 1px solid {border};
    }}
    QTreeWidget::item:selected {{
        background-color: #2563EB;
        color: #FFFFFF;
    }}
    QHeaderView::section {{
        background-color: {bg_sidebar};
        color: {fg_text};
        padding: 8px;
        border: 1px solid {border};
        font-weight: bold;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
        background-color: {bg_card};
        color: {fg_text};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 8px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {bg_card};
        color: {fg_text};
        selection-background-color: #2563EB;
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: {bg_sidebar};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {border};
        border-radius: 4px;
    }}
    """
