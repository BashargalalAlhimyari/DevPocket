import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import shutil
import datetime
import subprocess
from config import NOTES_PATH
from utils import get_gui_env, execute_script_in_terminal, update_frontmatter_keys
from note_manager import get_all_notes
from git_sync import sync_notes_cli
from event_monitor import evaluate_trigger

def check_internet():
    try:
        res = subprocess.run(["ping", "-c", "1", "-W", "2", "8.8.8.8"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except Exception:
        return False

_current_sound_process = None

def stop_current_sound():
    global _current_sound_process
    if _current_sound_process is not None:
        try:
            if _current_sound_process.poll() is None:
                _current_sound_process.terminate()
        except Exception:
            pass
        _current_sound_process = None
    
    try:
        subprocess.run(["killall", "-q", "-9", "canberra-gtk-play", "pw-play", "paplay", "aplay"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def play_sound(is_reminder=False, priority="normal"):
    global _current_sound_process
    
    stop_current_sound()

    if is_reminder:
        if priority == "quiet":
            alarm_files = ["/usr/share/sounds/freedesktop/stereo/message.oga", "/usr/share/sounds/gnome/default/alerts/glass.ogg"]
            canberra_id = "message"
        elif priority == "critical":
            alarm_files = ["/usr/share/sounds/gnome/default/alarms/school-bell.oga", "/usr/share/sounds/gnome/default/alarms/crossing-bell.oga"]
            canberra_id = "alarm-clock-elapsed"
        else:
            alarm_files = ["/usr/share/sounds/freedesktop/stereo/message-new-instant.oga", "/usr/share/sounds/gnome/default/alerts/glass.ogg"]
            canberra_id = "message-new-instant"
    else:
        alarm_files = [
            "/usr/share/sounds/gnome/default/alarms/school-bell.oga",
            "/usr/share/sounds/gnome/default/alarms/crossing-bell.oga",
            "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
            "/usr/share/sounds/freedesktop/stereo/complete.oga"
        ]
        canberra_id = "alarm-clock-elapsed"

    sound_file = next((f for f in alarm_files if os.path.exists(f)), None)
    canberra = shutil.which("canberra-gtk-play")
    pw_play = shutil.which("pw-play")
    paplay = shutil.which("paplay")
    aplay = shutil.which("aplay")
    gui_env = get_gui_env()

    try:
        if canberra:
            _current_sound_process = subprocess.Popen([canberra, f"--id={canberra_id}"], env=gui_env)
        elif pw_play and sound_file:
            _current_sound_process = subprocess.Popen([pw_play, sound_file], env=gui_env)
        elif paplay and sound_file:
            _current_sound_process = subprocess.Popen([paplay, sound_file], env=gui_env)
        elif aplay and sound_file and sound_file.endswith(".wav"):
            _current_sound_process = subprocess.Popen([aplay, sound_file], env=gui_env)
    except Exception as e:
        print(f"Sound play error: {e}")

def check_reminders_and_schedules():
    now_dt = datetime.datetime.now()
    notes = get_all_notes()
    gui_env = get_gui_env()
    notify_bin = shutil.which("notify-send")

    for n in notes:
        filepath = n['file']
        title = n['title']
        body = n['body']
        rem = n['reminder']
        sched = n['scheduled_exec']
        s_type = n.get('schedule_type', 'once')
        i_mins = int(n.get('interval_mins', 0) or 0)
        req_net = n.get('require_internet', 'false').lower() in ['true', 'yes', '1']
        catch_up = n.get('catch_up_on_boot', 'true').lower() in ['true', 'yes', '1']
        play_snd = n.get('play_sound', 'true').lower() in ['true', 'yes', '1']
        last_run = n.get('last_run', '')
        e_cat = n.get('event_category', 'None')
        e_trig = n.get('event_trigger', '')
        e_val = n.get('event_value', '')
        enabled = str(n.get('script_enabled', 'true')).lower() in ['true', 'yes', '1']

        if not enabled:
            continue

        # Check reminder notification
        if rem:
            try:
                rem_dt = datetime.datetime.strptime(rem, "%Y-%m-%d %H:%M")
                if now_dt >= rem_dt:
                    rem_pri = n.get('reminder_priority', 'normal').lower()
                    rem_rep = n.get('reminder_repeat', 'none').lower()
                    rem_int = int(n.get('reminder_interval_mins', 30) or 30)

                    if play_snd:
                        play_sound(is_reminder=True, priority=rem_pri)

                    notify_urgency = "critical" if rem_pri == 'critical' else ("low" if rem_pri == 'quiet' else "normal")
                    if notify_bin:
                        subprocess.Popen([notify_bin, "-u", notify_urgency, "-i", "alarm-clock", f"⏰ Reminder ({rem_pri.upper()}): {title}", "Opening reminder popup..."], env=gui_env)

                    # Launch interactive popup dialog with Snooze buttons
                    subprocess.Popen(["/home/bashar/.local/bin/notes", "remind-popup", filepath], env=gui_env)

                    # Handle Recurrence / Repeat
                    if rem_rep == 'daily':
                        next_dt = rem_dt + datetime.timedelta(days=1)
                        if next_dt <= now_dt: next_dt = now_dt + datetime.timedelta(days=1)
                        update_frontmatter_keys(filepath, {'reminder': next_dt.strftime("%Y-%m-%d %H:%M")})
                    elif rem_rep == 'weekly':
                        next_dt = rem_dt + datetime.timedelta(days=7)
                        if next_dt <= now_dt: next_dt = now_dt + datetime.timedelta(days=7)
                        update_frontmatter_keys(filepath, {'reminder': next_dt.strftime("%Y-%m-%d %H:%M")})
                    elif rem_rep == 'custom' and rem_int > 0:
                        next_dt = rem_dt + datetime.timedelta(minutes=rem_int)
                        if next_dt <= now_dt: next_dt = now_dt + datetime.timedelta(minutes=rem_int)
                        update_frontmatter_keys(filepath, {'reminder': next_dt.strftime("%Y-%m-%d %H:%M")})
                    else:
                        update_frontmatter_keys(filepath, {'reminder': ""})

                    sync_notes_cli()
            except Exception as e:
                print(f"Reminder check error for {filepath}: {e}")

        # Check scheduled terminal execution
        should_run = False
        target_dt = None
        is_event_triggered = False

        if e_cat != "None" and e_trig:
            try:
                if evaluate_trigger(e_cat, e_trig, e_val):
                    if last_run != "event_active":
                        should_run = True
                        target_dt = now_dt
                        is_event_triggered = True
                        update_frontmatter_keys(filepath, {'last_run': "event_active"})
                        last_run = "event_active"
                else:
                    if last_run == "event_active":
                        update_frontmatter_keys(filepath, {'last_run': ""})
                        last_run = ""
            except Exception as e:
                print(f"Event check error for {filepath}: {e}")

        if not should_run and sched:
            try:
                base_dt = datetime.datetime.strptime(sched, "%Y-%m-%d %H:%M")
                if s_type == 'recurring' and i_mins > 0:
                    if not last_run:
                        if now_dt >= base_dt:
                            should_run = True
                            target_dt = base_dt
                    else:
                        last_dt = datetime.datetime.strptime(last_run, "%Y-%m-%d %H:%M")
                        next_dt = last_dt + datetime.timedelta(minutes=i_mins)
                        if now_dt >= next_dt:
                            should_run = True
                            target_dt = next_dt
                else:
                    if now_dt >= base_dt:
                        should_run = True
                        target_dt = base_dt
            except Exception as e:
                print(f"Schedule parse error for {filepath}: {e}")

        if should_run and target_dt:
            time_diff = (now_dt - target_dt).total_seconds() / 60.0
            
            if not catch_up and time_diff > 15:
                print(f"Skipping missed execution for {title}")
                if s_type == 'once':
                    update_frontmatter_keys(filepath, {'scheduled_exec': ""})
                else:
                    update_frontmatter_keys(filepath, {'last_run': now_dt.strftime("%Y-%m-%d %H:%M")})
                sync_notes_cli()
                continue
                
            if req_net:
                if not check_internet():
                    print(f"Skipping execution for {title} due to no internet")
                    continue
            
            try:
                if play_snd: play_sound(is_reminder=False)
                if notify_bin:
                    subprocess.Popen([notify_bin, "-u", "normal", "-i", "utilities-terminal", f"🚀 Executing Scheduled Script: {title}", "Running in background..."], env=gui_env)
                
                clean_body = body.strip()
                if clean_body.startswith("#!"):
                    clean_body = "\n".join(clean_body.splitlines()[1:]).strip()
                
                subprocess.Popen(["bash", "-c", clean_body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                if is_event_triggered:
                    pass # Debounce state already set to 'event_active'
                elif s_type == 'once':
                    update_frontmatter_keys(filepath, {'scheduled_exec': ""})
                else:
                    update_frontmatter_keys(filepath, {'last_run': now_dt.strftime("%Y-%m-%d %H:%M")})
                sync_notes_cli()
            except Exception as e:
                print(f"Schedule exec error for {filepath}: {e}")

def run_daemon_loop(interval_sec=20):
    print(f"🚀 Developer Notes Daemon started. Monitoring reminders every {interval_sec} seconds...")
    cycle = 0
    while True:
        try:
            check_reminders_and_schedules()
            cycle += 1
            if cycle % 3 == 0:
                sync_notes_cli()
        except Exception as e:
            print(f"Daemon error: {e}")
        time.sleep(interval_sec)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["loop", "daemon"]:
        run_daemon_loop()
    else:
        check_reminders_and_schedules()
