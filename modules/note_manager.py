import os
import sys
import shutil
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from utils import parse_note_file, update_frontmatter_keys

def get_pinned_categories():
    if os.path.exists(config.PINNED_FILE):
        try:
            with open(config.PINNED_FILE, 'r', encoding='utf-8') as f:
                return set(line.strip() for line in f if line.strip())
        except Exception:
            pass
    return set()

def save_pinned_categories(pinned_set):
    try:
        os.makedirs(os.path.dirname(config.PINNED_FILE), exist_ok=True)
        with open(config.PINNED_FILE, 'w', encoding='utf-8') as f:
            for c in sorted(pinned_set):
                f.write(c + '\n')
    except Exception:
        pass

def get_category_visits():
    visits = {}
    if os.path.exists(config.CAT_VISITS_FILE):
        try:
            with open(config.CAT_VISITS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if ':' in line:
                        k, v = line.strip().split(':', 1)
                        visits[k.strip()] = int(v.strip())
        except Exception:
            pass
    return visits

def increase_category_access(cat_name):
    if not cat_name:
        return
    visits = get_category_visits()
    visits[cat_name] = visits.get(cat_name, 0) + 1
    try:
        os.makedirs(os.path.dirname(config.CAT_VISITS_FILE), exist_ok=True)
        with open(config.CAT_VISITS_FILE, 'w', encoding='utf-8') as f:
            for k, v in visits.items():
                f.write(f"{k}:{v}\n")
    except Exception:
        pass

def increase_note_access(filepath):
    if not os.path.exists(filepath):
        return
    data = parse_note_file(filepath)
    if data['category']:
        increase_category_access(data['category'])
    new_access = data.get('access', 0) + 1
    update_frontmatter_keys(filepath, {'access_count': str(new_access)})

    def run_sync():
        try:
            from git_sync import sync_notes_cli
            sync_notes_cli()
        except Exception:
            pass
    threading.Thread(target=run_sync, daemon=True).start()

def get_all_notes(filter_cat=None, search_query="", only_scheduled_scripts=False, sort_by="access"):
    notes = []
    scan_paths = []
    if os.path.exists(config.NOTES_PATH):
        scan_paths.append(config.NOTES_PATH)

    visited_files = set()

    for base_path in scan_paths:
        for root_dir, dirs, files in os.walk(base_path):
            rel_path = os.path.relpath(root_dir, base_path)
            parts = rel_path.split(os.sep)
            if any(p.startswith('.') or p in ['modules', 'bin', 'archive', '__pycache__', 'scratch', '.config', 'tasks'] for p in parts if p != '.'):
                continue
            for f in files:
                if f.endswith('.md') and not f.startswith('.'):
                    fp = os.path.realpath(os.path.join(root_dir, f))
                    if fp in visited_files:
                        continue
                    visited_files.add(fp)

                    n_data = parse_note_file(fp)
                    if filter_cat and n_data['category'].lower() != filter_cat.lower():
                        continue
                    if only_scheduled_scripts:
                        is_script = (n_data.get('type', '') == 'Script') or \
                                    bool(n_data.get('scheduled_exec')) or \
                                    (str(n_data.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1']) or \
                                    (bool(n_data.get('event_trigger')) and n_data.get('event_category', 'None') != 'None')
                        if not is_script:
                            continue
                    if search_query:
                        q = search_query.lower()
                        if q not in n_data['title'].lower() and q not in n_data['category'].lower() and q not in n_data['body'].lower():
                            continue
                    notes.append(n_data)

    if sort_by in ["name", "title"]:
        notes.sort(key=lambda x: x.get('title', '').lower())
    elif sort_by in ["date", "created"]:
        notes.sort(key=lambda x: str(x.get('created', '')), reverse=True)
    else:
        notes.sort(key=lambda x: (x.get('access', 0), str(x.get('created', ''))), reverse=True)

    return notes

def get_all_tasks():
    tasks = []
    scan_paths = []
    if os.path.exists(config.TASKS_PATH):
        scan_paths.append(config.TASKS_PATH)
    if os.path.exists(config.NOTES_PATH) and config.NOTES_PATH not in scan_paths:
        scan_paths.append(config.NOTES_PATH)

    visited_files = set()

    for base_path in scan_paths:
        for root_dir, dirs, files in os.walk(base_path):
            rel_path = os.path.relpath(root_dir, base_path)
            parts = rel_path.split(os.sep)
            if any(p.startswith('.') or p in ['modules', 'bin', 'archive', '__pycache__', 'scratch', '.config'] for p in parts if p != '.'):
                continue
            for f in files:
                if f.endswith('.md') and not f.startswith('.'):
                    fp = os.path.realpath(os.path.join(root_dir, f))
                    if fp in visited_files:
                        continue
                    visited_files.add(fp)

                    n_data = parse_note_file(fp)
                    if n_data.get('type', '') == 'Task':
                        tasks.append(n_data)

    return tasks

def get_categories_data():
    pinned_cats = get_pinned_categories()
    cat_visits = get_category_visits()
    categories = {}

    scan_paths = []
    if os.path.exists(config.NOTES_PATH):
        scan_paths.append(config.NOTES_PATH)

    IGNORE_DIRS = {'.git', '.config', 'modules', 'archive', 'bin', '__pycache__', 'scratch', 'notes', 'tasks', 'media'}

    for base_path in scan_paths:
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path) and not item.startswith('.') and item.lower() not in IGNORE_DIRS:
                if item not in categories:
                    categories[item] = {
                        'count': 0,
                        'scheduled': 0,
                        'access': cat_visits.get(item, 0),
                        'pinned': item in pinned_cats,
                        'created': os.path.getctime(item_path)
                    }

    notes = get_all_notes()
    for n_data in notes:
        cat = n_data.get('category')
        if not cat:
            parent_dir = os.path.basename(os.path.dirname(n_data['file']))
            if parent_dir and parent_dir.lower() not in IGNORE_DIRS and not parent_dir.startswith('.'):
                cat = parent_dir
            else:
                cat = "general"

        if cat.lower() == 'tasks':
            continue

        if cat not in categories:
            categories[cat] = {
                'count': 0,
                'scheduled': 0,
                'access': cat_visits.get(cat, 0),
                'pinned': cat in pinned_cats,
                'created': 0
            }

        categories[cat]['count'] += 1
        categories[cat]['access'] += n_data.get('access', 0)
        is_scheduled = bool(n_data.get('reminder') or n_data.get('scheduled_exec') or (str(n_data.get('run_on_boot', 'false')).lower() in ['true', 'yes', '1']))
        if is_scheduled:
            categories[cat]['scheduled'] += 1

    for p_cat in pinned_cats:
        if p_cat not in categories:
            categories[p_cat] = {'count': 0, 'scheduled': 0, 'access': cat_visits.get(p_cat, 0), 'pinned': True, 'created': 0}
        else:
            categories[p_cat]['pinned'] = True

    return categories, pinned_cats

def archive_note(filepath):
    if filepath and os.path.exists(filepath) and os.path.isfile(filepath):
        os.makedirs(config.ARCHIVE_PATH, exist_ok=True)
        shutil.move(filepath, os.path.join(config.ARCHIVE_PATH, os.path.basename(filepath)))

def archive_category(cat_name):
    if not cat_name or not cat_name.strip():
        return
    cat_name = cat_name.strip()
    if cat_name in [".", "..", "notes", "/", "\\"]:
        return
    os.makedirs(config.ARCHIVE_PATH, exist_ok=True)
    cat_dir = os.path.join(config.NOTES_PATH, cat_name)
    if not os.path.exists(cat_dir):
        cat_dir = os.path.join(config.NOTES_DIR, cat_name)
    if os.path.exists(cat_dir) and os.path.abspath(cat_dir) not in [os.path.abspath(config.NOTES_PATH), os.path.abspath(config.NOTES_DIR)]:
        shutil.move(cat_dir, os.path.join(config.ARCHIVE_PATH, cat_name))
    else:
        for n in get_all_notes(filter_cat=cat_name):
            archive_note(n['file'])

def rename_category(old_cat_name, new_cat_name):
    if not old_cat_name or not new_cat_name:
        return False
    old_cat = old_cat_name.strip()
    new_cat = new_cat_name.strip()
    if not old_cat or not new_cat or old_cat == new_cat:
        return False

    old_dir = os.path.join(config.NOTES_PATH, old_cat)
    if not os.path.exists(old_dir):
        old_dir = os.path.join(config.NOTES_DIR, old_cat)

    new_dir = os.path.join(config.NOTES_PATH, new_cat)

    os.makedirs(config.NOTES_PATH, exist_ok=True)
    if os.path.exists(old_dir) and os.path.isdir(old_dir):
        if os.path.exists(new_dir):
            for f in os.listdir(old_dir):
                shutil.move(os.path.join(old_dir, f), os.path.join(new_dir, f))
            shutil.rmtree(old_dir)
        else:
            shutil.move(old_dir, new_dir)

    notes = get_all_notes()
    for n in notes:
        f = n['file']
        if f.startswith(new_dir) or n.get('category') == old_cat:
            att = n.get('attachment')
            updates = {'category': new_cat}
            if att and att != "none" and old_cat in att:
                new_att = att.replace(f"{old_cat}/media/", f"{new_cat}/media/").replace(f"{old_cat}/", f"{new_cat}/")
                updates['attachment'] = new_att
            update_frontmatter_keys(f, updates)

    pinned = get_pinned_categories()
    if old_cat in pinned:
        pinned.remove(old_cat)
        pinned.add(new_cat)
        save_pinned_categories(pinned)

    visits = get_category_visits()
    if old_cat in visits:
        visits[new_cat] = visits.get(new_cat, 0) + visits.pop(old_cat)
        try:
            with open(config.CAT_VISITS_FILE, 'w', encoding='utf-8') as f:
                for k, v in visits.items():
                    f.write(f"{k}:{v}\n")
        except Exception:
            pass

    return True
