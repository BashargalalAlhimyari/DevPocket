from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QScrollArea, QFrame, QDesktopWidget
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt
from config import BG_MAIN, BG_CARD, BG_HEADER, FG_TEXT, FG_MUTED

FONT_ARABIC = QFont("Amiri", 12)
FONT_DEFAULT = QFont("Monospace", 10)

def apply_rtl_to_widget(widget, text=""):
    """
    In PyQt5, widgets handle RTL natively. 
    This function sets the font and direction if the text contains Arabic.
    """
    if is_arabic(text):
        widget.setFont(FONT_ARABIC)
        widget.setLayoutDirection(Qt.RightToLeft)

def is_arabic(text):
    if not text or not isinstance(text, str):
        return False
    return any(
        ('\u0600' <= char <= '\u06FF') or
        ('\u0750' <= char <= '\u077F') or
        ('\u08A0' <= char <= '\u08FF') or
        ('\uFB50' <= char <= '\uFDFF') or
        ('\uFE70' <= char <= '\uFEFF')
        for char in text
    )

def fix_arabic(text):
    """
    No longer needed in PyQt5. Returns the original text.
    """
    return text

def center_window(window, width, height):
    """
    Centers a PyQt5 window on the screen.
    """
    window.resize(width, height)
    qr = window.frameGeometry()
    cp = QDesktopWidget().availableGeometry().center()
    qr.moveCenter(cp)
    window.move(qr.topLeft())

def get_common_qss():
    """
    Returns the common Qt Style Sheet string based on the active theme.
    """
    from theme import get_theme_qss
    return get_theme_qss()

def create_horizontal_button(text, bg_color, command=None, is_primary=False):
    btn = QPushButton(text)
    font_weight = "bold" if is_primary else "normal"
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg_color};
            color: white;
            font-weight: {font_weight};
            font-size: 14px;
        }}
        QPushButton:hover {{
            background-color: #444;
        }}
    """)
    if command:
        btn.clicked.connect(command)
    btn.setCursor(Qt.PointingHandCursor)
    return btn

def create_horizontal_scrollable_frame(parent=None):
    """
    Creates a horizontal scroll area for buttons.
    Returns (QScrollArea, QWidget (content_frame), QHBoxLayout (for adding buttons)).
    """
    scroll_area = QScrollArea(parent)
    scroll_area.setWidgetResizable(True)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll_area.setStyleSheet("border: none; background: transparent;")
    
    content_widget = QWidget()
    content_widget.setStyleSheet("background: transparent;")
    
    layout = QHBoxLayout(content_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    
    scroll_area.setWidget(content_widget)
    return scroll_area, content_widget, layout
