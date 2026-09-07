import sys
from ui_view_note import show_schedule_dialog
from config import NOTES_PATH
# We can't easily script the Tkinter UI. Let's just call update_boot_autostart_entries directly.
from boot_manager import update_boot_autostart_entries
update_boot_autostart_entries()
print("Success")
