import os
import sys

# Ensure directories are in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.join(BASE_DIR, "modules")
SITE_PACKAGES = os.path.join(BASE_DIR, "site-packages")

if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)
if SITE_PACKAGES not in sys.path:
    sys.path.insert(0, SITE_PACKAGES)

# Fix DLL path resolution on Windows for PyQt5 in Python 3.8+
if sys.platform == "win32":
    qt5_bin_dirs = [
        os.path.join(SITE_PACKAGES, "PyQt5", "Qt5", "bin"),
        os.path.join(SITE_PACKAGES, "PyQt5", "Qt", "bin"),
        os.path.join(SITE_PACKAGES, "PyQt5"),
        BASE_DIR
    ]
    for bin_dir in qt5_bin_dirs:
        if os.path.exists(bin_dir):
            try:
                os.add_dll_directory(bin_dir)
            except Exception:
                pass
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

def main():
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QIcon
        from ui_categories import show_categories_window

        app = QApplication(sys.argv)
        app.setApplicationName("DevPocket")
        
        icon_path = os.path.join(BASE_DIR, "app_icon.png")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
            
        show_categories_window()
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print("Error starting DevPocket:\n", err_msg)
        log_file = os.path.join(BASE_DIR, "error_log.txt")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(err_msg + "\n")
        raise e

if __name__ == "__main__":
    main()
