import os

CONFIG_PATH_FILE = os.path.expanduser("~/.devnotes_path.txt")

def load_notes_dir():
    if os.path.exists(CONFIG_PATH_FILE):
        try:
            with open(CONFIG_PATH_FILE, "r", encoding="utf-8") as f:
                p = f.read().strip()
                if p and os.path.isabs(p):
                    return p
        except Exception:
            pass
    return os.path.expanduser("~/.developer-notes")

NOTES_DIR = load_notes_dir()
NOTES_PATH = os.path.join(NOTES_DIR, "notes")
CONFIG_DIR = os.path.join(NOTES_DIR, ".config")
ARCHIVE_PATH = os.path.join(NOTES_DIR, "archive")

PINNED_FILE = os.path.join(CONFIG_DIR, "pinned_categories.txt")
CAT_VISITS_FILE = os.path.join(CONFIG_DIR, "category_visits.txt")

def update_notes_dir(new_dir):
    global NOTES_DIR, NOTES_PATH, CONFIG_DIR, ARCHIVE_PATH, PINNED_FILE, CAT_VISITS_FILE
    new_dir = os.path.abspath(new_dir)
    os.makedirs(new_dir, exist_ok=True)
    try:
        with open(CONFIG_PATH_FILE, "w", encoding="utf-8") as f:
            f.write(new_dir)
    except Exception:
        pass
    
    NOTES_DIR = new_dir
    NOTES_PATH = os.path.join(NOTES_DIR, "notes")
    CONFIG_DIR = os.path.join(NOTES_DIR, ".config")
    ARCHIVE_PATH = os.path.join(NOTES_DIR, "archive")
    PINNED_FILE = os.path.join(CONFIG_DIR, "pinned_categories.txt")
    CAT_VISITS_FILE = os.path.join(CONFIG_DIR, "category_visits.txt")
    
    os.makedirs(NOTES_PATH, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_PATH, exist_ok=True)
    return new_dir

BG_MAIN = "#1E1E1E"
BG_CARD = "#252526"
BG_HEADER = "#333333"

FG_TEXT = "#FFFFFF"
FG_MUTED = "#CCCCCC"
FG_GREEN = "#00FF00"
FG_SUB = "#888888"

BTN_BLUE = "#0E639C"
BTN_AMBER = "#D97706"
BTN_RED = "#C9302C"
BTN_GREEN = "#28A745"
BTN_PURPLE = "#6F42C1"
BTN_TEAL = "#17A2B8"
BTN_GRAY = "#3C3C3C"

TASKS_PATH = os.path.join(NOTES_DIR, "tasks")

os.makedirs(NOTES_PATH, exist_ok=True)
os.makedirs(TASKS_PATH, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(ARCHIVE_PATH, exist_ok=True)

def get_category_dir(category):
    cat_name = (category or "general").strip()
    d = os.path.join(NOTES_PATH, cat_name)
    os.makedirs(d, exist_ok=True)
    return d

def get_category_media_dir(category):
    cat_dir = get_category_dir(category)
    m_dir = os.path.join(cat_dir, "media")
    os.makedirs(m_dir, exist_ok=True)
    gitkeep = os.path.join(m_dir, ".gitkeep")
    if not os.path.exists(gitkeep):
        try:
            with open(gitkeep, "w", encoding="utf-8") as f:
                f.write("# keep category media directory\n")
        except Exception:
            pass
    return m_dir

def get_tasks_dir():
    d = os.path.join(NOTES_DIR, "tasks")
    os.makedirs(d, exist_ok=True)
    return d

def get_tasks_media_dir():
    t_dir = get_tasks_dir()
    m_dir = os.path.join(t_dir, "media")
    os.makedirs(m_dir, exist_ok=True)
    gitkeep = os.path.join(m_dir, ".gitkeep")
    if not os.path.exists(gitkeep):
        try:
            with open(gitkeep, "w", encoding="utf-8") as f:
                f.write("# keep tasks media directory\n")
        except Exception:
            pass
    return m_dir

