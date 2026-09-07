import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import shutil
import hashlib
import subprocess
from config import NOTES_DIR
from note_manager import get_all_notes

AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")

def get_note_boot_id(filepath):
    return hashlib.md5(filepath.encode('utf-8')).hexdigest()[:10]

def update_boot_autostart_entries():
    os.makedirs(AUTOSTART_DIR, exist_ok=True)
    notes = get_all_notes()

    for f in os.listdir(AUTOSTART_DIR):
        if f.startswith("note_boot_") and f.endswith(".desktop"):
            try:
                os.remove(os.path.join(AUTOSTART_DIR, f))
            except Exception:
                pass

    cron_boot_lines = []

    for n in notes:
        run_boot = n.get('run_on_boot', '').lower() in ['true', 'yes', '1']
        if run_boot:
            fp = n['file']
            title = n['title']
            try:
                delay_min = int(n.get('boot_delay', '0'))
            except ValueError:
                delay_min = 0

            delay_sec = delay_min * 60
            boot_id = get_note_boot_id(fp)
            desktop_path = os.path.join(AUTOSTART_DIR, f"note_boot_{boot_id}.desktop")

            desktop_content = f"""[Desktop Entry]
Type=Application
Name=Execute Note: {title}
Exec=bash -c "sleep {delay_sec} && /home/bashar/.local/bin/notes exec-silent '{fp}'"
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=Auto-execute script on system boot
"""
            with open(desktop_path, 'w', encoding='utf-8') as f:
                f.write(desktop_content)
            os.chmod(desktop_path, 0o755)

            cron_boot_lines.append(f"@reboot sleep {delay_sec} && /home/bashar/.local/bin/notes exec-silent '{fp}' >/dev/null 2>&1")

    if shutil.which("crontab"):
        try:
            res = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            existing_lines = res.stdout.splitlines() if res.returncode == 0 else []
            filtered_lines = [l for l in existing_lines if "@reboot" not in l or "notes exec" not in l]

            new_crontab = filtered_lines + cron_boot_lines
            crontab_input = "\n".join(new_crontab) + "\n"

            p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
            p.communicate(input=crontab_input)
        except Exception as e:
            print(f"Crontab update error: {e}")
