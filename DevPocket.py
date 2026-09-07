import os
import sys
import subprocess

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


def run_preflight_checks():
    """Runs a step-by-step diagnostic check for Python, Git, and dependencies."""
    print("=" * 70)
    print(" 🚀 DevPocket System & Dependency Diagnostic Check")
    print("=" * 70)

    # 1. Check Python Version
    py_ver = sys.version_info
    py_ver_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver < (3, 8):
        print(f" ❌ [1/4] Python Version: {py_ver_str} (Requires Python 3.8 or higher)")
        print("    -> Please upgrade Python to version 3.8+ to run DevPocket.")
        sys.exit(1)
    else:
        print(f" ✅ [1/4] Python Version: {py_ver_str} OK")

    # 2. Check Git Installation & GitHub Status
    try:
        git_res = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
        git_version = git_res.stdout.strip()
        print(f" ✅ [2/4] Git Environment: {git_version} OK")
    except Exception:
        print(" ⚠️  [2/4] Git Environment: Git command not found in PATH.")
        print("    -> Git is recommended for automatic project backups.")

    # 3. Check Required Python Dependencies
    required_packages = [
        ("PyQt5", "PyQt5.QtWidgets", "PyQt5"),
        ("PyYAML", "yaml", "pyyaml"),
        ("markdown", "markdown", "markdown"),
        ("pymdown-extensions", "pymdownx", "pymdown-extensions"),
        ("emoji", "emoji", "emoji"),
        ("requests", "requests", "requests"),
        ("GitPython", "git", "gitpython"),
        ("SpeechRecognition", "speech_recognition", "speechrecognition"),
    ]

    missing_pkgs = []
    print(" 🔍 [3/4] Verifying Required Python Libraries:")
    for display_name, import_name, pip_name in required_packages:
        try:
            __import__(import_name)
            print(f"    • {display_name:<20}: Installed ✅")
        except ImportError:
            print(f"    • {display_name:<20}: MISSING ❌")
            missing_pkgs.append((display_name, pip_name))

    # 4. Handle Missing Dependencies
    if missing_pkgs:
        print("\n" + "!" * 70)
        print(" ⚠️  ATTENTION: Missing Python Packages Detected!")
        print("!" * 70)
        print(" The following required packages are not installed in your Python environment:\n")
        for disp, pip_n in missing_pkgs:
            print(f"   - {disp} (pip package: {pip_n})")

        req_file = os.path.join(BASE_DIR, "requirements.txt")
        print("\n 💡 How to fix:")
        print(f"   Run the following command in your terminal:\n")
        print(f"       pip install -r {req_file}\n")

        print(" Attempting automatic installation via pip now...")
        pip_cmd = [sys.executable, "-m", "pip", "install"]
        is_venv = hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
        if not is_venv and sys.platform != "win32":
            pip_cmd.extend(["--break-system-packages"])

        try:
            cmd = pip_cmd + [pip_n for _, pip_n in missing_pkgs]
            subprocess.check_call(cmd)
            print("\n ✅ All missing packages installed successfully!")
        except Exception:
            try:
                cmd = [sys.executable, "-m", "pip", "install"] + [pip_n for _, pip_n in missing_pkgs]
                subprocess.check_call(cmd)
                print("\n ✅ All missing packages installed successfully!")
            except Exception as e:
                print(f"\n ❌ Automatic installation failed: {e}")
                print(f" Please run: pip install -r requirements.txt manually and restart DevPocket.")
                sys.exit(1)
    else:
        print(" ✅ [4/4] All Dependencies Verified Successfully!")

    print("=" * 70)
    print(" 🎉 All checks passed! Launching DevPocket GUI...\n")


def main():
    # Execute preflight system checks
    run_preflight_checks()

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
