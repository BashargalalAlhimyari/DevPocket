import os
import time
import subprocess
import threading
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QInputDialog,
                             QMessageBox, QLabel, QFrame, QPushButton)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from config import NOTES_DIR, BG_MAIN, FG_GREEN
from utils import center_window
from ui_common import get_common_qss


def clean_stale_git_locks():
    git_dir = os.path.join(NOTES_DIR, ".git")
    if not os.path.exists(git_dir):
        return
    lock_files = [
        os.path.join(git_dir, "index.lock"),
        os.path.join(git_dir, "refs", "heads", "main.lock"),
        os.path.join(git_dir, "refs", "heads", "master.lock"),
    ]
    for lf in lock_files:
        if os.path.exists(lf):
            try:
                os.remove(lf)
            except Exception:
                pass


def sanitize_git_url(url):
    if not url:
        return ""
    url = url.strip()
    if url.startswith("https://github.com/") and not url.endswith(".git") and not url.endswith("/"):
        url += ".git"
    return url


def detect_remote_default_branch(remote_target="origin"):
    try:
        clean_stale_git_locks()
        res = subprocess.run(
            ["git", "ls-remote", "--symref", remote_target, "HEAD"],
            cwd=NOTES_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=8
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "ref: refs/heads/" in line:
                    b = line.split("ref: refs/heads/")[1].split()[0].strip()
                    if b:
                        return b
    except Exception:
        pass
    return "main"


def check_large_files():
    large_files = []
    if os.path.exists(NOTES_DIR):
        for root, dirs, files in os.walk(NOTES_DIR):
            if ".git" in root:
                continue
            for f in files:
                fp = os.path.join(root, f)
                try:
                    if os.path.getsize(fp) > 95 * 1024 * 1024:
                        large_files.append(os.path.basename(fp))
                except Exception:
                    pass
    return large_files


def diagnose_git_error(error_text, url=""):
    err_lower = str(error_text).lower()
    
    if "could not resolve host" in err_lower or "failed to connect" in err_lower or "network is unreachable" in err_lower:
        return (
            "🌐 <b>تعذر الاتصال بالشبكة (Network Offline)</b><br>"
            "تأكد من اتصال جهازك بالإنترنت وأن خوادم GitHub متاحة حالياً."
        )
    elif "authentication failed" in err_lower or "403" in err_lower or "401" in err_lower:
        return (
            "🔐 <b>خطأ المصادقة والتصاريح (Authentication Failed)</b><br>"
            "قام GitHub بإلغاء كلمة المرور العادية واشترط <b>Personal Access Token (PAT)</b>.<br><br>"
            "💡 <b>كيفية الحل:</b><br>"
            "1. اذهب لـ GitHub ➔ Settings ➔ Developer Settings ➔ Personal Access Tokens.<br>"
            "2. قم بأنشئ Token جديد مع اختيار صلاحية <b>repo</b>.<br>"
            "3. أدخل الرابط بالشكل التالي:<br>"
            "<code>https://&lt;YOUR_TOKEN&gt;@github.com/username/repository.git</code>"
        )
    elif "permission denied (publickey)" in err_lower:
        return (
            "🔑 <b>خطأ مفتاح SSH (SSH Key Error)</b><br>"
            "جهازك لا يملك مفتاح SSH معرّف على حساب GitHub.<br><br>"
            "💡 <b>الحل السريع:</b> يُفضّل تغيير الرابط إلى صيغة <b>HTTPS</b> (مثال: <code>https://github.com/user/repo.git</code>)."
        )
    elif "repository not found" in err_lower or "404" in err_lower:
        return (
            "🔍 <b>المستودع غير موجود (Repository Not Found)</b><br>"
            "يرجى التأكد من اسم المستودع، أو التأكد من توفر تصريح للمستودعات الخاصة (Private)."
        )
    elif "exceeds github's file size limit" in err_lower or "large files detected" in err_lower:
        return (
            "📦 <b>تجاوز حد حجم الملفات (File Size Limit > 100MB)</b><br>"
            "يحتوي المجلد على ملف ضخم يتجاوز 100MB لا يقبله GitHub بدون LFS."
        )
    else:
        return f"⚠️ <b>تفاصيل الخطأ:</b><br>{error_text}"


def sync_notes_cli():
    if not os.path.exists(os.path.join(NOTES_DIR, ".git")):
        print("⚠️ Sync skipped: Git repository not initialized.")
        return
    clean_stale_git_locks()
    branch = get_git_branch_name() or "main"
    print("🔄 Staging local changes...")
    os.chdir(NOTES_DIR)

    subprocess.run(["git", "add", "-A"])
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        print("📌 Committing local changes...")
        subprocess.run(["git", "commit", "-m", f"Update notes {time.strftime('%Y-%m-%d %H:%M')}"])

    subprocess.run(["git", "add", "-A"])
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        subprocess.run(["git", "commit", "-m", f"Auto-save before sync {time.strftime('%Y-%m-%d %H:%M')}"])

    print("🔄 Pulling remote changes with autostash protection...")
    pull_res = subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", branch]).returncode

    if pull_res != 0:
        print("⚠️ Rebase pull lock detected, attempting fail-safe merge...")
        subprocess.run(["git", "rebase", "--abort"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "add", "-A"])
        subprocess.run(["git", "pull", "origin", branch, "--no-rebase", "-Xours"])

    print("🚀 Pushing to GitHub...")
    push_res = subprocess.run(["git", "push", "origin", branch]).returncode
    if push_res == 0:
        print("✅ Notes synchronized successfully.")
    else:
        print("⚠️ Standard push rejected, using force-with-lease fallback...")
        subprocess.run(["git", "push", "origin", branch, "--force-with-lease"])


class SyncDialog(QDialog):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("مزامنة GitHub - نافذة الأوامر")
        self.resize(680, 430)
        self.setMinimumSize(580, 360)
        self.setStyleSheet("""
            QDialog {
                background-color: #090C10;
                color: #F1F5F9;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # Terminal Header Bar (Mac/Linux Window Style)
        term_header = QFrame()
        term_header.setStyleSheet("background-color: #161B22; border-radius: 8px 8px 0 0; padding: 8px 14px; border: 1px solid #30363D;")
        header_layout = QHBoxLayout(term_header)
        header_layout.setContentsMargins(4, 2, 4, 2)

        # Window Dots
        dots_layout = QHBoxLayout()
        dots_layout.setSpacing(6)
        lbl_red = QLabel("🔴")
        lbl_yellow = QLabel("🟡")
        lbl_green = QLabel("🟢")
        for dot in [lbl_red, lbl_yellow, lbl_green]:
            dot.setStyleSheet("font-size: 11px; background: transparent;")
            dots_layout.addWidget(dot)

        header_layout.addLayout(dots_layout)

        # Title Label
        title_lbl = QLabel("💻 التيرمينال - رفع التغييرات إلى GitHub")
        title_lbl.setStyleSheet("color: #8B949E; font-size: 12px; font-weight: bold; background: transparent; font-family: monospace;")
        header_layout.addStretch()
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        layout.addWidget(term_header)

        # Terminal Log Screen (QTextEdit)
        self.text_box = QTextEdit()
        self.text_box.setReadOnly(True)
        self.text_box.setStyleSheet("""
            QTextEdit {
                background-color: #0D1117;
                color: #34D399;
                font-family: 'Monaco', 'DejaVu Sans Mono', 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                line-height: 1.5;
                border: 1px solid #30363D;
                border-top: none;
                border-radius: 0 0 8px 8px;
                padding: 14px;
            }
            QScrollBar:vertical {
                background: #161B22;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #30363D;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.text_box, 1)

        # Bottom Action Bar
        btn_layout = QHBoxLayout()
        self.btn_close = QPushButton("⏳ جاري المزامنة مع GitHub...")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setEnabled(False)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #21262D;
                color: #8B949E;
                font-weight: bold;
                font-size: 12px;
                padding: 7px 18px;
                border-radius: 6px;
                border: 1px solid #30363D;
            }
            QPushButton:enabled {
                background-color: #238636;
                color: #FFFFFF;
                border: none;
            }
            QPushButton:enabled:hover {
                background-color: #2EA043;
            }
        """)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        # Signals
        self.log_signal.connect(self.append_log)
        self.finished_signal.connect(self.on_finished)

        center_window(self, 680, 430)

    def append_log(self, text):
        self.text_box.append(text)
        self.text_box.verticalScrollBar().setValue(self.text_box.verticalScrollBar().maximum())

    def on_finished(self):
        self.btn_close.setEnabled(True)
        self.btn_close.setText("✅ إغلاق التيرمينال")

    def run_cmd(self, cmd):
        self.log_signal.emit(f"<span style='color: #38BDF8; font-weight: bold;'>$ {' '.join(cmd)}</span>")
        try:
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            for line in p.stdout:
                clean_line = line.rstrip('\n').replace('<', '&lt;').replace('>', '&gt;')
                self.log_signal.emit(f"<span style='color: #C9D1D9;'>{clean_line}</span>")
            p.wait()
            return p.returncode
        except Exception as e:
            self.log_signal.emit(f"<span style='color: #F87171;'>Error executing {cmd[0]}: {e}</span>")
            return 1

    def start_sync(self):
        self.log_signal.emit("<span style='color: #A78BFA; font-weight: bold;'>================================================</span>")
        self.log_signal.emit("<span style='color: #34D399; font-weight: bold;'> 💻 التيرمينال: جاري بدء مزامنة GitHub...</span>")
        self.log_signal.emit("<span style='color: #A78BFA; font-weight: bold;'>================================================</span><br>")

        os.chdir(NOTES_DIR)
        try:
            self.run_cmd(["git", "add", "-A"])
            if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
                self.log_signal.emit("<br><span style='color: #FBBF24;'>📌 جاري حفظ التغييرات المحلية...</span>")
                self.run_cmd(["git", "commit", "-m", f"تحديث الملاحظات {time.strftime('%Y-%m-%d %H:%M')}"])

            self.run_cmd(["git", "add", "-A"])
            if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
                self.run_cmd(["git", "commit", "-m", f"حفظ تلقائي قبل المزامنة {time.strftime('%Y-%m-%d %H:%M')}"])

            self.log_signal.emit("<br><span style='color: #38BDF8;'>🔄 جاري سحب التغييرات من الخادم (Pull)...</span>")
            pull_res = self.run_cmd(["git", "pull", "--rebase", "--autostash", "origin", "main"])
            if pull_res != 0:
                self.log_signal.emit("<br><span style='color: #FBBF24;'>⚠️ تم كشف تعارض، جاري إجراء دمج آمن...</span>")
                self.run_cmd(["git", "rebase", "--abort"])
                self.run_cmd(["git", "add", "-A"])
                pull_res = self.run_cmd(["git", "pull", "origin", "main", "--no-rebase", "-Xours"])

            self.log_signal.emit("<br><span style='color: #38BDF8;'>🚀 جاري الرفع إلى GitHub (Push)...</span>")
            push_res = self.run_cmd(["git", "push", "origin", "main"])
            if push_res != 0:
                self.log_signal.emit("<br><span style='color: #FBBF24;'>⚠️ تم رفض الرفع العادي، جاري الرفع القسري الآمن...</span>")
                push_res = self.run_cmd(["git", "push", "origin", "main", "--force-with-lease"])

            if push_res == 0:
                self.log_signal.emit("<br><span style='color: #34D399; font-weight: bold;'>✅ تم المزامنة والرفع إلى GitHub بنجاح!</span>")
            else:
                self.log_signal.emit("<br><span style='color: #F87171; font-weight: bold;'>❌ فشلت عملية الرفع! يرجى التحقق من اتصال الإنترنت أو رابط المستودع.</span>")

        except Exception as e:
            self.log_signal.emit(f"<br><span style='color: #F87171;'>❌ خطأ: {str(e)}</span>")

        self.finished_signal.emit()


def sync_notes_gui(parent=None):
    if not os.path.exists(os.path.join(NOTES_DIR, ".git")):
        print("⚠️ Sync skipped: Git repository not initialized.")
        return

    try:
        dlg = SyncDialog(parent)
        def do_sync():
            dlg.start_sync()
        threading.Thread(target=do_sync, daemon=True).start()
        dlg.exec_()
    except Exception as e:
        print(f"Error executing GUI sync: {e}")
        sync_notes_cli()


def setup_git_repo_gui():
    from ui_common import get_common_qss
    
    # Use simple PyQt5 input dialog
    parent_dlg = QDialog()
    parent_dlg.setStyleSheet(get_common_qss())
    
    url, ok = QInputDialog.getText(
        parent_dlg,
        "إعداد مستودع GitHub",
        "أدخل رابط مستودع GitHub البعيد:\n(مثال: https://github.com/user/repo.git)"
    )
    if not ok or not url.strip():
        return

    url = url.strip()
    os.chdir(NOTES_DIR)

    try:
        if not os.path.exists(os.path.join(NOTES_DIR, ".git")):
            subprocess.run(["git", "init"], check=True)

        subprocess.run(["git", "branch", "-M", "main"], check=False)
        subprocess.run(["git", "remote", "remove", "origin"], stderr=subprocess.DEVNULL)
        subprocess.run(["git", "remote", "add", "origin", url], check=True)

        subprocess.run(["git", "add", "-A"])
        if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
            subprocess.run(["git", "commit", "-m", "Initial sync setup from Antigravity Notes"])

        subprocess.run(["git", "pull", "origin", "main", "--allow-unrelated-histories", "--no-rebase", "-Xours"],
                       stderr=subprocess.DEVNULL)

        res = subprocess.run(["git", "push", "-u", "origin", "main", "--force-with-lease"])

        if res.returncode == 0:
            QMessageBox.information(parent_dlg, "نجاح",
                f"✅ تم ربط المستودع بنجاح بـ:\n{url}\n\nملاحظاتك جاهزة للمزامنة الآن!")
        else:
            QMessageBox.warning(parent_dlg, "تحذير",
                "تم ربط المستودع، ولكن فشلت عملية الرفع الأولية.\n"
                "قد تحتاج إلى إعداد مفاتيح SSH أو الرمز الشخصي (PAT) لـ GitHub.")

    except Exception as e:
        QMessageBox.critical(parent_dlg, "خطأ", f"فشل في إعداد المستودع:\n{str(e)}")


def get_git_remote_url():
    git_dir = os.path.join(NOTES_DIR, ".git")
    if not os.path.exists(git_dir):
        return ""
    try:
        res = subprocess.run(["git", "remote", "get-url", "origin"], cwd=NOTES_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def get_git_branch_name():
    git_dir = os.path.join(NOTES_DIR, ".git")
    if not os.path.exists(git_dir):
        return ""
    try:
        res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=NOTES_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "main"


def get_git_last_commit_info():
    git_dir = os.path.join(NOTES_DIR, ".git")
    if not os.path.exists(git_dir):
        return "لم يتم تهيئة Git بعد"
    try:
        res = subprocess.run(["git", "log", "-1", "--format=%cd - %s", "--date=short"], cwd=NOTES_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "لا توجد التزامات سابقة (No commits yet)"


def unlink_git_remote():
    git_dir = os.path.join(NOTES_DIR, ".git")
    if not os.path.exists(git_dir):
        return False
    try:
        subprocess.run(["git", "remote", "remove", "origin"], cwd=NOTES_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        return False


def get_git_unsynced_rel_paths():
    from config import NOTES_DIR
    git_dir = os.path.join(NOTES_DIR, ".git")
    if not os.path.exists(git_dir):
        return None  # Git not initialized

    remote_url = get_git_remote_url()
    if not remote_url:
        return None  # No GitHub repository linked

    try:
        unsynced = set()

        # 1. Uncommitted working tree & untracked files
        res_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=NOTES_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3
        )
        if res_status.returncode == 0:
            for line in res_status.stdout.splitlines():
                line_str = line.strip()
                if len(line_str) > 3:
                    rel_p = line_str[2:].strip().strip('"')
                    unsynced.add(rel_p.replace('\\', '/'))

        # 2. Unpushed commits compared to remote origin
        branch = get_git_branch_name() or "main"
        res_unpushed = subprocess.run(
            ["git", "log", f"origin/{branch}..HEAD", "--name-only", "--format="],
            cwd=NOTES_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3
        )
        if res_unpushed.returncode == 0:
            for line in res_unpushed.stdout.splitlines():
                fp = line.strip().strip('"')
                if fp:
                    unsynced.add(fp.replace('\\', '/'))
        elif "no upstream" in res_unpushed.stderr.lower() or "unknown revision" in res_unpushed.stderr.lower():
            # If origin/branch is not fetched or unpushed, mark local files as unsynced
            res_all_local = subprocess.run(
                ["git", "ls-files"],
                cwd=NOTES_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3
            )
            if res_all_local.returncode == 0:
                for line in res_all_local.stdout.splitlines():
                    fp = line.strip().strip('"')
                    if fp:
                        unsynced.add(fp.replace('\\', '/'))

        return unsynced
    except Exception:
        return None


def is_file_synced(filepath, unsynced_set=None):
    from config import NOTES_DIR
    git_dir = os.path.join(NOTES_DIR, ".git")
    if not os.path.exists(git_dir):
        return False

    if unsynced_set is None:
        unsynced_set = get_git_unsynced_rel_paths()

    if unsynced_set is None:
        return False

    try:
        rel_p = os.path.relpath(filepath, NOTES_DIR).replace('\\', '/')
        return rel_p not in unsynced_set
    except Exception:
        return False


def is_category_synced(cat_name, unsynced_set=None):
    from config import NOTES_DIR
    git_dir = os.path.join(NOTES_DIR, ".git")
    if not os.path.exists(git_dir):
        return False

    if unsynced_set is None:
        unsynced_set = get_git_unsynced_rel_paths()

    if unsynced_set is None:
        return False

    cat_lower = cat_name.lower()
    prefix1 = f"{cat_lower}/"
    prefix2 = f"notes/{cat_lower}/"

    for unsynced_file in unsynced_set:
        uf_lower = unsynced_file.lower()
        if uf_lower.startswith(prefix1) or uf_lower.startswith(prefix2) or uf_lower == cat_lower:
            return False

    return True


