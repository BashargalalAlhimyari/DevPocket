import os
import sys
import time
import subprocess

def read_file_safe(path):
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except Exception:
        return ""

def cmd_output(cmd_list):
    try:
        return subprocess.check_output(cmd_list, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore').strip()
    except Exception:
        return ""

def cmd_exit_code(cmd_str):
    try:
        return subprocess.call(['bash', '-c', cmd_str], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return 1

# Category 1: System & Power
def check_system_power(trigger, value):
    val_str = str(value).strip()
    
    if trigger == "System Booted":
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_sec = float(f.readline().split()[0])
                return uptime_sec < 120
        except Exception:
            return False

    elif trigger == "User Logged In":
        out = cmd_output(['who'])
        if val_str:
            return val_str in out
        return bool(out)

    elif trigger == "System Shutting Down":
        out = cmd_output(['systemctl', 'is-system-running'])
        return out in ['stopping', 'offline']

    elif trigger == "System Sleep/Suspend":
        out = cmd_output(['journalctl', '-n', '5', '-u', 'systemd-suspend.service'])
        return "Started" in out or "Reached target Sleep" in out

    elif trigger == "System Resume/Wakeup":
        out = cmd_output(['journalctl', '-n', '5', '-u', 'systemd-suspend.service'])
        return "Finished" in out or "Leaving sleep state" in out

    elif trigger in ["Battery Drops Below (%)", "Drops Below (%)"]:
        capacity_str = read_file_safe('/sys/class/power_supply/BAT0/capacity') or read_file_safe('/sys/class/power_supply/BAT1/capacity')
        status = read_file_safe('/sys/class/power_supply/BAT0/status') or read_file_safe('/sys/class/power_supply/BAT1/status')
        if not capacity_str: return False
        try:
            cap = int(capacity_str)
            target = int(val_str) if val_str else 20
            return cap < target and status != "Charging"
        except Exception: return False

    elif trigger in ["Battery Rises Above / Full (%)", "Rises Above (%)", "Fully Charged (100%)"]:
        capacity_str = read_file_safe('/sys/class/power_supply/BAT0/capacity') or read_file_safe('/sys/class/power_supply/BAT1/capacity')
        status = read_file_safe('/sys/class/power_supply/BAT0/status') or read_file_safe('/sys/class/power_supply/BAT1/status')
        if not capacity_str: return False
        try:
            cap = int(capacity_str)
            target = int(val_str) if val_str else 85
            return cap >= target or status == "Full"
        except Exception: return False

    elif trigger == "Charger Connected":
        status = read_file_safe('/sys/class/power_supply/BAT0/status') or read_file_safe('/sys/class/power_supply/BAT1/status')
        return status in ["Charging", "Full"]

    elif trigger == "Charger Disconnected":
        status = read_file_safe('/sys/class/power_supply/BAT0/status') or read_file_safe('/sys/class/power_supply/BAT1/status')
        return status == "Discharging"

    elif trigger == "Power Save Mode Enabled":
        return cmd_exit_code('powerprofilesctl get | grep power-saver') == 0

    elif trigger in ["Temperature Exceeds (C)", "Temperature Drops Below (C)"]:
        temp_str = read_file_safe('/sys/class/thermal/thermal_zone0/temp')
        if temp_str:
            try:
                temp_c = int(temp_str) / 1000.0
                target = float(val_str) if val_str else 75.0
                if "Exceeds" in trigger: return temp_c > target
                else: return temp_c < target
            except Exception: return False
        return False

    elif trigger == "RAM Available Below (MB)":
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        mb = int(line.split()[1]) / 1024
                        target = float(val_str) if val_str else 1024
                        return mb < target
        except Exception: return False

    elif trigger == "Disk Space Usage Exceeds (%)":
        out = cmd_output(['df', '/', '--output=pcent'])
        lines = out.splitlines()
        if len(lines) > 1:
            try:
                pct = int(lines[1].strip().replace('%', ''))
                target = int(val_str) if val_str else 90
                return pct >= target
            except Exception: return False

    return False

# Category 2: Network & Connectivity
def check_network_triggers(trigger, value):
    val_str = str(value).strip()
    
    if trigger in ["Wi-Fi Connected (SSID)", "Wi-Fi Disconnected (SSID)"]:
        out = cmd_output(['nmcli', '-t', '-f', 'active,ssid', 'dev', 'wifi'])
        active_ssid = ""
        for line in out.splitlines():
            if line.startswith("yes:"):
                active_ssid = line[4:]
                break
        if trigger == "Wi-Fi Connected (SSID)":
            return active_ssid == val_str if val_str else active_ssid != ""
        else:
            return active_ssid != val_str if val_str else active_ssid == ""

    elif trigger == "Wi-Fi Connected (Public/Open)":
        out = cmd_output(['nmcli', '-t', '-f', 'active,security', 'dev', 'wifi'])
        for line in out.splitlines():
            if line.startswith("yes:"):
                sec = line[4:].strip()
                return sec in ["", "--", "none"]
        return False

    elif trigger == "IP Address Changed":
        ip = cmd_output(['hostname', '-I']).split()[0] if cmd_output(['hostname', '-I']) else ""
        cache_file = "/tmp/.dev_notes_last_ip"
        old_ip = read_file_safe(cache_file)
        if ip and old_ip and ip != old_ip:
            with open(cache_file, "w") as f: f.write(ip)
            return True
        if ip and not old_ip:
            with open(cache_file, "w") as f: f.write(ip)
        return False

    elif trigger == "Ethernet State Changed":
        out = cmd_output(['ip', 'link', 'show'])
        return "eth" in out or "enp" in out

    elif trigger in ["Internet Connected", "Internet Reconnected"]:
        return cmd_exit_code('ping -c 1 -W 1 8.8.8.8') == 0

    elif trigger == "Internet Disconnected":
        return cmd_exit_code('ping -c 1 -W 1 8.8.8.8') != 0

    elif trigger == "Ping Host Failed":
        host = val_str if val_str else "8.8.8.8"
        return cmd_exit_code(f'ping -c 1 -W 1 {host}') != 0

    elif trigger == "Network Latency Exceeds (ms)":
        target = float(val_str) if val_str else 250.0
        out = cmd_output(['ping', '-c', '1', '-W', '1', '8.8.8.8'])
        if "time=" in out:
            try:
                ms = float(out.split("time=")[1].split()[0])
                return ms > target
            except Exception: return False

    elif trigger == "Untrusted Network Connected":
        out = cmd_output(['nmcli', '-t', '-f', 'active,ssid', 'dev', 'wifi'])
        active_ssid = ""
        for line in out.splitlines():
            if line.startswith("yes:"):
                active_ssid = line[4:]
                break
        return active_ssid != "" and val_str and val_str not in active_ssid

    elif trigger == "Company Network Connected":
        out = cmd_output(['nmcli', '-t', '-f', 'active,ssid', 'dev', 'wifi'])
        return val_str in out if val_str else "company" in out.lower() or "corp" in out.lower()

    elif trigger in ["VPN Connected", "VPN Disconnected / Stopped"]:
        out = cmd_output(['ip', 'a'])
        has_vpn = "tun" in out or "wg" in out or "proton" in out or "tap" in out
        if val_str: has_vpn = has_vpn and val_str in out
        if trigger == "VPN Connected": return has_vpn
        else: return not has_vpn

    return False

# Category 3: Docker & Services
def check_docker_services(trigger, value):
    val_str = str(value).strip()

    if trigger == "Docker Daemon Started":
        return cmd_exit_code('systemctl is-active docker') == 0 or cmd_exit_code('docker info') == 0

    elif trigger == "Docker Daemon Stopped":
        return cmd_exit_code('docker info') != 0

    elif trigger == "Docker Container Started":
        out = cmd_output(['docker', 'ps', '--format', '{{.Names}}'])
        return val_str in out if val_str else bool(out)

    elif trigger == "Database Service Ready":
        port = val_str if val_str else "5432"
        return cmd_exit_code(f'nc -z 127.0.0.1 {port}') == 0

    elif trigger == "Docker Container Stopped/Failed":
        out_running = cmd_output(['docker', 'ps', '--format', '{{.Names}}'])
        out_all = cmd_output(['docker', 'ps', '-a', '--format', '{{.Names}}'])
        if val_str:
            return val_str in out_all and val_str not in out_running
        return bool(out_all) and len(out_running.splitlines()) < len(out_all.splitlines())

    elif trigger == "Docker Container Failed Repeatedly":
        out = cmd_output(['docker', 'ps', '-a', '--filter', 'status=exited', '--format', '{{.Names}}'])
        return val_str in out if val_str else bool(out)

    elif trigger == "Port Becomes Open/Available":
        port = val_str if val_str else "8080"
        return cmd_exit_code(f'nc -z 127.0.0.1 {port}') == 0

    elif trigger == "Port Becomes Closed/Unavailable":
        port = val_str if val_str else "8080"
        return cmd_exit_code(f'nc -z 127.0.0.1 {port}') != 0

    elif trigger == "Dev Server Started":
        port = val_str if val_str else "3000"
        return cmd_exit_code(f'nc -z 127.0.0.1 {port}') == 0

    elif trigger == "Backend Service Stopped":
        port = val_str if val_str else "8000"
        return cmd_exit_code(f'nc -z 127.0.0.1 {port}') != 0

    elif trigger == "Environment File (.env) Changed":
        path = os.path.expanduser(val_str) if val_str else os.path.expanduser("./.env")
        if os.path.exists(path):
            return (time.time() - os.path.getmtime(path)) < 30
        return False

    elif trigger == "Docker Image Updated":
        out = cmd_output(['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}'])
        return val_str in out if val_str else bool(out)

    elif trigger == "Health Check Failed":
        url = val_str if val_str else "http://localhost:8000/health"
        return cmd_exit_code(f'curl -f -s {url}') != 0

    elif trigger == "Project Services Sequence Start":
        path = os.path.expanduser(val_str) if val_str else ""
        return os.path.exists(path)

    return False

# Category 4: Development & Programming
def check_development(trigger, value):
    val_str = str(value).strip()

    if trigger == "Project Directory Opened":
        path = os.path.expanduser(val_str) if val_str else ""
        return os.path.exists(path)

    elif trigger == "Python File Modified":
        path = os.path.expanduser(val_str) if val_str else "."
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for f in files:
                    if f.endswith(".py"):
                        fp = os.path.join(root, f)
                        try:
                            if (time.time() - os.path.getmtime(fp)) < 30: return True
                        except Exception: pass
        elif os.path.exists(path):
            return (time.time() - os.path.getmtime(path)) < 30
        return False

    elif trigger == "Code File Saved":
        path = os.path.expanduser(val_str) if val_str else "."
        if os.path.exists(path):
            return (time.time() - os.path.getmtime(path)) < 30
        return False

    elif trigger == "Test Suite Failed":
        cmd = val_str if val_str else "pytest"
        return cmd_exit_code(cmd) != 0

    elif trigger == "Build Succeeded":
        path = os.path.expanduser(val_str) if val_str else "."
        return os.path.exists(path)

    elif trigger in ["Git Commit Created", "Git Tag Created", "Git Pull / Changes Received"]:
        repo_path = os.path.expanduser(val_str) if val_str else "."
        git_head = os.path.join(repo_path, ".git", "HEAD")
        if os.path.exists(git_head):
            return (time.time() - os.path.getmtime(git_head)) < 30
        return False

    elif trigger == "requirements.txt Changed":
        path = os.path.expanduser(val_str) if val_str else "requirements.txt"
        if os.path.exists(path):
            return (time.time() - os.path.getmtime(path)) < 30
        return False

    elif trigger == "package.json Changed":
        path = os.path.expanduser(val_str) if val_str else "package.json"
        if os.path.exists(path):
            return (time.time() - os.path.getmtime(path)) < 30
        return False

    elif trigger == "Flutter Project Started":
        out = cmd_output(['pgrep', '-f', 'flutter'])
        return bool(out)

    elif trigger in ["Android Device USB Connected", "Android Device Disconnected"]:
        out = cmd_output(['adb', 'devices'])
        has_dev = any("device" in line for line in out.splitlines()[1:] if line.strip())
        if trigger == "Android Device USB Connected": return has_dev
        else: return not has_dev

    elif trigger == "Android Build Failed":
        path = os.path.expanduser(val_str) if val_str else "."
        return os.path.exists(path)

    elif trigger == "New File Added To Watch List":
        path = os.path.expanduser(val_str) if val_str else "."
        if os.path.exists(path):
            return (time.time() - os.path.getmtime(path)) < 30
        return False

    return False

# Category 5: Files, Folders & Notes
def check_files_notes(trigger, value):
    val_str = str(value).strip()

    if trigger == "File Created In Directory":
        path = os.path.expanduser(val_str) if val_str else "."
        if os.path.exists(path):
            return (time.time() - os.path.getmtime(path)) < 30
        return False

    elif trigger == "Config File Modified":
        path = os.path.expanduser(val_str) if val_str else os.path.expanduser("~/.bashrc")
        if os.path.exists(path):
            return (time.time() - os.path.getmtime(path)) < 30
        return False

    elif trigger == "Important File Deleted":
        path = os.path.expanduser(val_str)
        return not os.path.exists(path) if val_str else False

    elif trigger == "Downloads Folder File Arrived":
        dl_dir = os.path.expanduser("~/Downloads")
        if os.path.exists(dl_dir):
            ext = val_str.lower() if val_str else ""
            for f in os.listdir(dl_dir):
                if not ext or f.endswith(ext):
                    fp = os.path.join(dl_dir, f)
                    try:
                        if (time.time() - os.path.getmtime(fp)) < 30: return True
                    except Exception: pass
        return False

    elif trigger == "Zip File Downloaded/Arrived":
        dl_dir = os.path.expanduser(val_str) if val_str else os.path.expanduser("~/Downloads")
        if os.path.exists(dl_dir):
            for f in os.listdir(dl_dir):
                if f.endswith(".zip"):
                    fp = os.path.join(dl_dir, f)
                    try:
                        if (time.time() - os.path.getmtime(fp)) < 30: return True
                    except Exception: pass
        return False

    elif trigger == "Note Content Modified":
        path = os.path.expanduser(val_str) if val_str else ""
        if os.path.exists(path):
            return (time.time() - os.path.getmtime(path)) < 30
        return False

    elif trigger == "Note Contains Tag (#urgent)":
        tag = val_str if val_str else "#urgent"
        notes_dir = os.path.expanduser("~/.developer-notes/notes")
        return cmd_exit_code(f'grep -rn "{tag}" "{notes_dir}"') == 0

    elif trigger == "Note Contains Automation Code (WHEN...)":
        prefix = val_str if val_str else "WHEN"
        notes_dir = os.path.expanduser("~/.developer-notes/notes")
        return cmd_exit_code(f'grep -rn "{prefix}" "{notes_dir}"') == 0

    elif trigger == "Automation Execution Failed":
        log_file = os.path.expanduser("~/.developer-notes/daemon.log")
        return cmd_exit_code(f'grep -i "error" "{log_file}"') == 0 if os.path.exists(log_file) else False

    elif trigger == "Rule Inactivity Timeout Exceeded (Hours)":
        return False

    return False

# Category 6: Security & Monitoring
def check_security(trigger, value):
    val_str = str(value).strip()

    if trigger == "Sensitive System File Changed":
        path = os.path.expanduser(val_str) if val_str else "/etc/passwd"
        if os.path.exists(path):
            return (time.time() - os.path.getmtime(path)) < 60
        return False

    elif trigger == "Unusual Login Detected":
        out = cmd_output(['last', '-n', '5'])
        return bool(out)

    elif trigger == "Unknown Process Started":
        out = cmd_output(['ps', 'aux'])
        return val_str in out if val_str else False

    elif trigger == "Network Data Usage Exceeds (MB)":
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]
                total_bytes = 0
                for l in lines:
                    parts = l.split()
                    if len(parts) > 9:
                        total_bytes += int(parts[1]) + int(parts[9])
                mb = total_bytes / (1024 * 1024)
                target = float(val_str) if val_str else 500.0
                return mb > target
        except Exception: return False

    elif trigger == "SSH Failed Login Attempts Exceeds":
        out = cmd_output(['journalctl', '-u', 'ssh', '-n', '20'])
        count = out.count("Failed password")
        target = int(val_str) if val_str else 3
        return count >= target

    elif trigger == "Security / Firewall Service Stopped":
        return cmd_exit_code('systemctl is-active ufw') != 0 and cmd_exit_code('systemctl is-active firewalld') != 0

    elif trigger == "Unknown USB Device Connected":
        out = cmd_output(['lsusb'])
        return bool(out)

    elif trigger == "Firewall Rules Changed":
        path = "/etc/ufw/user.rules"
        if os.path.exists(path):
            return (time.time() - os.path.getmtime(path)) < 60
        return False

    elif trigger == "Insecure Service Detected":
        port = val_str if val_str else "23"
        return cmd_exit_code(f'nc -z 127.0.0.1 {port}') == 0

    elif trigger == "Rapid Repeated Event Triggered (Seconds)":
        return False

    return False

# Category 7: Custom & Advanced
def check_custom(trigger, value):
    val_str = str(value).strip()

    if trigger in ["Bash Command Succeeds (Exit 0)", "Custom"]:
        return cmd_exit_code(val_str) == 0 if val_str else False

    elif trigger == "Process Running / Found":
        return cmd_exit_code(f'pgrep -f "{val_str}"') == 0 if val_str else False

    elif trigger == "Process Terminated / Stopped":
        return cmd_exit_code(f'pgrep -f "{val_str}"') != 0 if val_str else False

    return False

def evaluate_trigger(category, trigger, value):
    if not category or category == "None" or not trigger:
        return False

    norm_trig = trigger
    if '(' in trigger and ')' in trigger:
        norm_trig = trigger.split('(')[-1].split(')')[0].strip()

    norm_cat = category
    if '(' in category and ')' in category:
        norm_cat = category.split('(')[-1].split(')')[0].strip()

    # Try matching with original or normalized
    return (check_system_power(trigger, value) or check_system_power(norm_trig, value) or
            check_network_triggers(trigger, value) or check_network_triggers(norm_trig, value) or
            check_docker_services(trigger, value) or check_docker_services(norm_trig, value) or
            check_development(trigger, value) or check_development(norm_trig, value) or
            check_files_notes(trigger, value) or check_files_notes(norm_trig, value) or
            check_security(trigger, value) or check_security(norm_trig, value) or
            check_custom(trigger, value) or check_custom(norm_trig, value))
