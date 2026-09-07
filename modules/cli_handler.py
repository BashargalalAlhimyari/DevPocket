import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import subprocess
from config import NOTES_PATH
from PyQt5.QtWidgets import QApplication

_qapp = None
def get_qapp():
    global _qapp
    if _qapp is None:
        _qapp = QApplication(sys.argv)
    return _qapp

from utils import execute_script_in_terminal
from note_manager import get_all_notes, archive_note, archive_category
from git_sync import sync_notes_gui, sync_notes_cli
from daemon import check_reminders_and_schedules, run_daemon_loop
from ui_categories import show_categories_window
from ui_list_notes import show_notes_list_window
from ui_view_note import show_note_view_window
from ui_create_note import show_create_note_window
from ui_reminders import show_todays_reminders_window, show_reminder_alert_popup
from ui_setup import show_setup_wizard

def handle_exec(filepath=None):
    if not filepath or not os.path.exists(filepath):
        act, filepath = show_notes_list_window()
        if act == "DELETE" and filepath:
            archive_note(filepath)
            sync_notes_gui()
            return
    if filepath and os.path.exists(filepath):
        execute_script_in_terminal(filepath)

def handle_exec_silent(filepath=None, reason="Boot Script"):
    if not filepath or not os.path.exists(filepath):
        return
    import subprocess, shutil
    from utils import parse_note_file, get_gui_env
    from daemon import play_sound

    n_data = parse_note_file(filepath)
    body = n_data['body'].strip()
    if not body:
        return

    if body.startswith("#!"):
        body = "\n".join(body.splitlines()[1:]).strip()

    play_snd = n_data.get('play_sound', 'true').lower() in ['true', 'yes', '1']
    title = n_data['title']

    gui_env = get_gui_env()

    if play_snd:
        play_sound(is_reminder=False)
        notify_bin = shutil.which("notify-send")
        if notify_bin:
            subprocess.Popen([notify_bin, "-u", "normal", "-i", "utilities-terminal", f"🚀 Executing {reason}: {title}", "Running in background..."], env=gui_env)

    subprocess.Popen(["bash", "-c", body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def handle_show(filepath=None):
    if not filepath or not os.path.exists(filepath):
        act, filepath = show_notes_list_window()
        if act == "DELETE" and filepath:
            archive_note(filepath)
            sync_notes_gui()
            return
    if filepath and os.path.exists(filepath):
        action = show_note_view_window(filepath)
        if action == "EXEC":
            handle_exec(filepath)
        elif action == "SAVE_SYNC":
            sync_notes_gui()
        elif action == "DELETE":
            archive_note(filepath)
            sync_notes_gui()

def handle_new(default_cat="general"):
    filepath = show_create_note_window(default_cat=default_cat)
    if filepath:
        sync_notes_gui()

def handle_notes_list(filter_cat=None, search_query="", only_scheduled_scripts=False):
    while True:
        action, filepath = show_notes_list_window(filter_cat=filter_cat, search_query=search_query, only_scheduled_scripts=only_scheduled_scripts)
        if action == "OPEN" and filepath and os.path.exists(filepath):
            handle_show(filepath)
        elif action == "NEW":
            handle_new(default_cat=filter_cat)
        elif action == "EDIT" and filepath and os.path.exists(filepath):
            handle_show(filepath)
        elif action == "DELETE" and filepath:
            archive_note(filepath)
            sync_notes_gui()
        else:
            break

def handle_categories():
    while True:
        action, val = show_categories_window()
        if action == "OPEN" and val:
            handle_notes_list(filter_cat=val)
        elif action == "OPEN_FILE" and val:
            handle_show(val)
        elif action == "OPEN_SCRIPTS_LIST":
            handle_notes_list(only_scheduled_scripts=True)
        elif action == "DELETE" and val:
            archive_category(val)
            sync_notes_gui()
        else:
            break

def run_cli_router(args):
    cmd = args[1] if len(args) > 1 else ""
    target = args[2] if len(args) > 2 else ""

    if cmd in ["new", "n"]:
        handle_new()
    elif cmd in ["list", "ls"]:
        handle_notes_list()
    elif cmd in ["categories", "cat", "c"]:
        handle_categories()
    elif cmd in ["search", "s"]:
        handle_notes_list(search_query=target)
    elif cmd in ["show", "v"]:
        handle_show(target)
    elif cmd in ["exec", "run", "x"]:
        handle_exec(target)
    elif cmd in ["exec-silent", "run-silent"]:
        handle_exec_silent(target)
    elif cmd in ["today", "t"]:
        show_todays_reminders_window()
    elif cmd in ["remind-popup"]:
        show_reminder_alert_popup(target)
    elif cmd in ["sync"]:
        sync_notes_gui()
    elif cmd in ["check-reminders"]:
        check_reminders_and_schedules()
    elif cmd in ["daemon", "loop"]:
        run_daemon_loop()
    elif cmd in ["setup"]:
        show_setup_wizard()
    else:
        # Default launcher: Open categories navigation loop
        handle_categories()

if __name__ == "__main__":
    get_qapp()
    run_cli_router(sys.argv)
