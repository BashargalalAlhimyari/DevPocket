import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import shutil
import subprocess
from PyQt5.QtWidgets import QDesktopWidget

def center_window(win, width=None, height=None, parent_geom=None):
    if width and height:
        win.resize(width, height)
    if parent_geom:
        win.setGeometry(parent_geom)
        return
    qr = win.frameGeometry()
    cp = QDesktopWidget().availableGeometry().center()
    qr.moveCenter(cp)
    win.move(qr.topLeft())

def open_file_cross_platform(path):
    if not path or not os.path.exists(path):
        return
    try:
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        print(f"Error opening file {path}: {e}")

def fix_arabic_display(text):
    if not text or not isinstance(text, str):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except ImportError:
        return text

def parse_note_file(filepath):
    title = os.path.basename(filepath)
    cat = "general"
    created = ""
    access = 0
    attachment = "none"
    reminder = ""
    scheduled_exec = ""
    schedule_type = "once"
    interval_mins = 0
    require_internet = "false"
    catch_up_on_boot = "true"
    play_sound = "true"
    last_run = ""
    run_on_boot = "false"
    boot_delay = "0"
    event_category = "None"
    event_trigger = ""
    event_value = ""
    script_enabled = "true"
    type_ = "Note"
    status = "todo"
    priority = "medium"
    tags = ""
    due_date = ""
    effort = ""
    body_lines = []

    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as fp:
                in_meta = False
                meta_count = 0
                for line in fp:
                    if line.strip() == '---':
                        meta_count += 1
                        in_meta = (meta_count < 2)
                        continue
                    if in_meta:
                        if line.startswith('title:'):
                            title = line.replace('title:', '').strip().strip('"').strip("'")
                        elif line.startswith('category:'):
                            cat = line.replace('category:', '').strip().strip('"').strip("'")
                        elif line.startswith('created:'):
                            created = line.replace('created:', '').strip().strip('"').strip("'")
                        elif line.startswith('access_count:'):
                            try: access = int(line.replace('access_count:', '').strip().strip('"').strip("'"))
                            except Exception: pass
                        elif line.startswith('attachment:'):
                            attachment = line.replace('attachment:', '').strip().strip('"').strip("'")
                        elif line.startswith('reminder:'):
                            reminder = line.replace('reminder:', '').strip().strip('"').strip("'")
                        elif line.startswith('scheduled_exec:'):
                            scheduled_exec = line.replace('scheduled_exec:', '').strip().strip('"').strip("'")
                        elif line.startswith('run_on_boot:'):
                            run_on_boot = line.replace('run_on_boot:', '').strip().strip('"').strip("'")
                        elif line.startswith('boot_delay:'):
                            boot_delay = line.replace('boot_delay:', '').strip().strip('"').strip("'")
                        elif line.startswith('type:'):
                            type_ = line.replace('type:', '').strip().strip('"').strip("'")
                        elif line.startswith('schedule_type:'):
                            schedule_type = line.replace('schedule_type:', '').strip().strip('"').strip("'")
                        elif line.startswith('interval_mins:'):
                            try: interval_mins = int(line.replace('interval_mins:', '').strip().strip('"').strip("'"))
                            except Exception: pass
                        elif line.startswith('require_internet:'):
                            require_internet = line.replace('require_internet:', '').strip().strip('"').strip("'")
                        elif line.startswith('catch_up_on_boot:'):
                            catch_up_on_boot = line.replace('catch_up_on_boot:', '').strip().strip('"').strip("'")
                        elif line.startswith('play_sound:'):
                            play_sound = line.replace('play_sound:', '').strip().strip('"').strip("'")
                        elif line.startswith('last_run:'):
                            last_run = line.replace('last_run:', '').strip().strip('"').strip("'")
                        elif line.startswith('event_category:'):
                            event_category = line.replace('event_category:', '').strip().strip('"').strip("'")
                        elif line.startswith('event_trigger:'):
                            event_trigger = line.replace('event_trigger:', '').strip().strip('"').strip("'")
                        elif line.startswith('event_value:'):
                            event_value = line.replace('event_value:', '').strip().strip('"').strip("'")
                        elif line.startswith('script_enabled:'):
                            script_enabled = line.replace('script_enabled:', '').strip().strip('"').strip("'")
                        elif line.startswith('status:'):
                            status = line.replace('status:', '').strip().strip('"').strip("'")
                        elif line.startswith('priority:'):
                            priority = line.replace('priority:', '').strip().strip('"').strip("'")
                        elif line.startswith('tags:'):
                            tags = line.replace('tags:', '').strip().strip('"').strip("'")
                        elif line.startswith('due_date:'):
                            due_date = line.replace('due_date:', '').strip().strip('"').strip("'")
                        elif line.startswith('effort:'):
                            effort = line.replace('effort:', '').strip().strip('"').strip("'")
                    else:
                        body_lines.append(line)
        except Exception:
            pass

    # Calculate subtasks
    subtasks_total = 0
    subtasks_done = 0
    for bline in body_lines:
        bstr = bline.strip().lower()
        if bstr.startswith("- [ ]") or bstr.startswith("* [ ]"):
            subtasks_total += 1
        elif bstr.startswith("- [x]") or bstr.startswith("* [x]"):
            subtasks_total += 1
            subtasks_done += 1

    return {
        'file': filepath,
        'title': title,
        'category': cat,
        'created': created,
        'access': access,
        'attachment': attachment,
        'reminder': reminder,
        'scheduled_exec': scheduled_exec,
        'run_on_boot': run_on_boot,
        'boot_delay': boot_delay,
        'schedule_type': schedule_type,
        'interval_mins': interval_mins,
        'require_internet': require_internet,
        'catch_up_on_boot': catch_up_on_boot,
        'play_sound': play_sound,
        'event_category': event_category,
        'event_trigger': event_trigger,
        'event_value': event_value,
        'script_enabled': script_enabled,
        'last_run': last_run,
        'type': type_,
        'status': status,
        'priority': priority,
        'tags': tags,
        'due_date': due_date,
        'effort': effort,
        'subtasks_total': subtasks_total,
        'subtasks_done': subtasks_done,
        'body': "".join(body_lines)
    }

def update_frontmatter_keys(filepath, key_values):
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as fp:
            content = fp.read()

        lines = content.splitlines()
        if not lines or lines[0].strip() != '---':
            front = ['---']
            for k, v in key_values.items():
                front.append(f'{k}: "{v}"')
            front.append('---')
            new_content = "\n".join(front) + "\n" + content
        else:
            c = 0
            front_lines = []
            body_lines = []
            found_keys = set()
            for l in lines:
                if c < 2:
                    if l.strip() == '---':
                        c += 1
                        front_lines.append(l)
                        continue
                    k_matched = False
                    for k, v in key_values.items():
                        if l.startswith(f"{k}:"):
                            front_lines.append(f'{k}: "{v}"')
                            found_keys.add(k)
                            k_matched = True
                            break
                    if not k_matched:
                        front_lines.append(l)
                else:
                    body_lines.append(l)

            insert_pos = len(front_lines) - 1
            for k, v in key_values.items():
                if k not in found_keys:
                    front_lines.insert(insert_pos, f'{k}: "{v}"')
                    insert_pos += 1

            new_content = "\n".join(front_lines) + "\n" + "\n".join(body_lines) + "\n"

        with open(filepath, 'w', encoding='utf-8') as fp:
            fp.write(new_content)
    except Exception as e:
        print(f"Error updating frontmatter in {filepath}: {e}")

def get_gui_env():
    gui_env = os.environ.copy()
    user_id = os.getuid()
    user_name = os.environ.get('USER') or os.environ.get('LOGNAME') or 'bashar'
    home_dir = os.path.expanduser(f'~{user_name}')

    gui_env['HOME'] = home_dir
    gui_env['USER'] = user_name
    gui_env['LOGNAME'] = user_name
    gui_env['SHELL'] = '/bin/bash'

    try:
        if os.path.exists('/proc'):
            for pid_str in os.listdir('/proc'):
                if not pid_str.isdigit():
                    continue
                try:
                    cmdline_path = f'/proc/{pid_str}/cmdline'
                    if not os.path.exists(cmdline_path):
                        continue
                    with open(cmdline_path, 'rb') as f:
                        cmdline = f.read().decode('utf-8', errors='ignore')
                    if any(proc in cmdline for proc in ['gnome-shell', 'mutter', 'ptyxis', 'gnome-terminal', 'wayland', 'systemd']):
                        environ_path = f'/proc/{pid_str}/environ'
                        if os.path.exists(environ_path):
                            with open(environ_path, 'rb') as f:
                                env_data = f.read().split(b'\x00')
                            for item in env_data:
                                if b'=' in item:
                                    k, v = item.split(b'=', 1)
                                    key_str = k.decode('utf-8', errors='ignore')
                                    val_str = v.decode('utf-8', errors='ignore')
                                    if key_str in ['DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS', 'XDG_RUNTIME_DIR', 'XDG_CURRENT_DESKTOP', 'XDG_SESSION_TYPE', 'PATH', 'DESKTOP_SESSION']:
                                        if val_str and key_str not in gui_env:
                                            gui_env[key_str] = val_str
                except Exception:
                    pass
    except Exception:
        pass

    if "DISPLAY" not in gui_env or not gui_env["DISPLAY"]:
        gui_env["DISPLAY"] = ":0"
    if "XDG_RUNTIME_DIR" not in gui_env or not gui_env["XDG_RUNTIME_DIR"]:
        gui_env["XDG_RUNTIME_DIR"] = f"/run/user/{user_id}"

    if "DBUS_SESSION_BUS_ADDRESS" not in gui_env or not gui_env["DBUS_SESSION_BUS_ADDRESS"]:
        bus_path = f"/run/user/{user_id}/bus"
        if os.path.exists(bus_path):
            gui_env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus_path}"

    if "WAYLAND_DISPLAY" not in gui_env or not gui_env["WAYLAND_DISPLAY"]:
        for w in ["wayland-0", "wayland-1"]:
            if os.path.exists(f"/run/user/{user_id}/{w}"):
                gui_env["WAYLAND_DISPLAY"] = w
                break

    if "XAUTHORITY" not in gui_env or not gui_env["XAUTHORITY"]:
        home_xauth = os.path.join(home_dir, ".Xauthority")
        if os.path.exists(home_xauth):
            gui_env["XAUTHORITY"] = home_xauth
        else:
            run_user = f"/run/user/{user_id}"
            if os.path.exists(run_user):
                for f in os.listdir(run_user):
                    if "xauth" in f.lower():
                        gui_env["XAUTHORITY"] = os.path.join(run_user, f)
                        break

    if "XDG_CURRENT_DESKTOP" not in gui_env:
        gui_env["XDG_CURRENT_DESKTOP"] = "ubuntu:GNOME"
    if "XDG_SESSION_TYPE" not in gui_env:
        gui_env["XDG_SESSION_TYPE"] = "wayland" if gui_env.get("WAYLAND_DISPLAY") else "x11"

    default_path = f"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin:/snap/bin:{home_dir}/.local/bin"
    if "PATH" not in gui_env or not gui_env["PATH"]:
        gui_env["PATH"] = default_path
    else:
        gui_env["PATH"] = f"{gui_env['PATH']}:{default_path}"

    return gui_env

def execute_script_in_terminal(filepath, custom_body=None):
    body = custom_body
    if body is None:
        if not os.path.exists(filepath):
            return False
        n_data = parse_note_file(filepath)
        body = n_data['body']

    body = body.strip()
    if not body:
        return False

    clean_body = body
    if clean_body.startswith("#!"):
        clean_body = "\n".join(clean_body.splitlines()[1:]).strip()

    if clean_body.startswith("bash -c '") and clean_body.endswith("'"):
        clean_body = clean_body[9:-1].strip()
    elif clean_body.startswith('bash -c "') and clean_body.endswith('"'):
        clean_body = clean_body[9:-1].strip()

    inline_cmd = f"source ~/.profile 2>/dev/null; source ~/.bashrc 2>/dev/null; {clean_body}\n\necho ''\necho '=================================================='\necho '✅ Note command execution completed.'\nexec bash"

    term = shutil.which("ptyxis") or shutil.which("gnome-terminal") or shutil.which("kgx") or shutil.which("x-terminal-emulator") or shutil.which("konsole") or shutil.which("xfce4-terminal") or shutil.which("alacritty") or shutil.which("kitty") or shutil.which("xterm")
    gui_env = get_gui_env()

    try:
        if term:
            real_term = os.path.realpath(term).lower()
            if "ptyxis" in real_term or "gnome-terminal" in real_term or "kgx" in real_term:
                subprocess.Popen([term, "--", "bash", "-c", inline_cmd], env=gui_env)
            elif "konsole" in real_term or "xfce4-terminal" in real_term or "alacritty" in real_term or "kitty" in real_term:
                subprocess.Popen([term, "-e", "bash", "-c", inline_cmd], env=gui_env)
            else:
                try:
                    subprocess.Popen([term, "--", "bash", "-c", inline_cmd], env=gui_env)
                except Exception:
                    subprocess.Popen([term, "-e", "bash", "-c", inline_cmd], env=gui_env)
        else:
            subprocess.Popen(["bash", "-c", inline_cmd], env=gui_env)
        return True
    except Exception as e:
        print(f"Terminal launch error: {e}")
        return False

def load_any_image(path, max_w=500, max_h=280):
    if not os.path.exists(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    try:
        from PIL import Image, ImageTk
        pil_img = Image.open(path)
        pil_img.thumbnail((max_w, max_h))
        return ImageTk.PhotoImage(pil_img)
    except Exception:
        pass

    tmp_png = path
    if ext not in ['.png', '.gif', '.ppm', '.pgm']:
        tmp_png = f'/tmp/note_img_thumb_{os.getpid()}.png'
        subprocess.run(['convert', path, '-resize', f'{max_w}x{max_h}', tmp_png], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not os.path.exists(tmp_png):
            return None

    try:
        raw_img = tk.PhotoImage(file=tmp_png)
        sub = max(1, max(raw_img.width() // max_w, raw_img.height() // max_h))
        return raw_img.subsample(sub, sub) if sub > 1 else raw_img
    except Exception:
        return None
