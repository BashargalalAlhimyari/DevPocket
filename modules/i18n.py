import os

LANG_FILE = os.path.expanduser("~/.developer-notes/.config/language.txt")

def get_lang():
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, 'r', encoding='utf-8') as f:
                lang = f.read().strip().lower()
                if lang in ['ar', 'en']:
                    return lang
        except Exception:
            pass
    return 'ar'  # Default to Arabic

def set_lang(lang_code):
    try:
        os.makedirs(os.path.dirname(LANG_FILE), exist_ok=True)
        with open(LANG_FILE, 'w', encoding='utf-8') as f:
            f.write(lang_code.lower())
    except Exception as e:
        print(f"Error saving language setting: {e}")

TRANSLATIONS = {
    'ar': {
        # Sidebar Navigation & Tools
        'nav_cats': 'الفئات',
        'nav_kanban': 'لوحة كانبان',
        'nav_scripts': 'السكربتات',
        'nav_rems': 'التذكيرات',
        'nav_git': 'إعداد Git',
        'nav_settings': 'الإعدادات',
        'nav_sync': 'مزامنة',
        'nav_export': 'التصدير الكلي',
        'tools_header': 'الأدوات',
        'settings_title': '⚙️ إعدادات التطبيق',
        'settings_sub': 'تخصيص لغة الواجهة ومظهر التطبيق',
        'settings_gb_lang': '🌐 لغة الواجهة (Interface Language)',
        'settings_gb_theme': '🎨 مظهر التطبيق والثيم (Theme & Appearance)',
        'settings_save': '💾 حفظ وتطبيق الإعدادات',

        # Categories Window
        'cat_win_title': '📁 تصفح وإدارة الفئات',
        'cat_header_lbl': '📁 الفئات (المثبتة 📌 أولاً):',
        'btn_reminders': '⏰ التذكيرات',
        'btn_scripts': '🚀 السكربتات',
        'btn_kanban': '📋 لوحة كانبان',
        'btn_setup_git': '⚙️ إعداد Git',
        'btn_sync': '🔄 مزامنة',
        'btn_new_task': '➕ مهمة جديدة',
        'btn_lang_toggle': '🌐 English',
        'search_lbl': '🔍 بحث:',
        'sort_lbl': '↕️ ترتيب حسب:',
        'sort_visits': 'الزيارات',
        'sort_name': 'الاسم',
        'sort_date': 'تاريخ الإنشاء',
        'col_cat_name': '📁 اسم الفئة',
        'col_visits': '📊 الزيارات',
        'col_notes': '📝 الملاحظات',
        'col_scheduled': '⏰ المجدولة',
        'col_status': '📌 الحالة',
        'col_actions': '⚡ الإجراءات',
        'btn_open': '📂 فتح (Enter)',
        'btn_new_cat': '📁 فئة جديدة',
        'btn_cancel': '❌ إلغاء (Esc)',
        'btn_pin': '📌 تثبيت',
        'btn_rename': '✏️ تعديل',
        'btn_delete': '🗑️ حذف',
        'status_pinned': '📌 مثبتة',
        'status_normal': 'عادي',
        'visit_count': '{count} زيارة',
        'note_count': '{count} ملاحظة',
        'sched_count': '⏰ {count} نشط',

        # Notes List Window
        'notes_win_title': '📝 قائمة الملاحظات',
        'notes_win_scripts_title': '🚀 السكربتات المجدولة',
        'notes_header_filter': '📁 الفئة: {cat}',
        'notes_header_all': '📝 جميع الملاحظات',
        'btn_new_note': '➕ ملاحظة جديدة',
        'col_title': '📄 العنوان',
        'col_type': '📝 النوع',
        'col_tags': '🏷️ الوسوم',
        'col_created': '📅 تـاريخ الإنشاء',
        'col_reminder': '🔔 التذكير / الجدولة',
        'view_note_opt': '📖 عرض / فتح',
        'edit_note_opt': '✏️ تعديل',
        'disable_script_opt': '⏸️ تعطيل السكربت',
        'enable_script_opt': '▶️ تفعيل السكربت',
        'delete_note_opt': '🗑️ حذف',

        # View Note Window
        'view_note_title': '📄 ملاحظة: {title}',
        'btn_edit': '✏️ تعديل الملاحظة',
        'btn_save_changes': '💾 حفظ التغييرات',
        'btn_voice_rec': '🎙️ تسجيل صوتي',
        'btn_exec_now': '🚀 تشغيل الآن',
        'btn_sched_boot': '🚀 جدولة وإقلاع',
        'btn_disable': '⏸️ تعطيل',
        'btn_enable': '▶️ تفعيل',
        'btn_set_rem': '⏰ ضبط تذكير',
        'btn_mark_done': '✅ تحديد كمكتمل',
        'btn_close': '❌ إغلاق',

        # Schedule Dialog
        'sched_dlg_title': '🚀 إعدادات الجدولة المتقدمة',
        'sched_main_header': '🚀 إعدادات جدولة التشغيل الأوتوماتيكي',
        'sec_boot': '1. مشغل إقلاع النظام (System Boot)',
        'cb_run_boot': '🚀 التشغيل أوتوماتيكياً مع كل إقلاع للنظام (@reboot)',
        'lbl_boot_delay': 'تأخير التشغيل بعد الإقلاع (بالدقائق):',
        'sec_time': '2. الجدولة الزمانية (Time-based)',
        'rb_none': '🚫 بدون جدولة (معطل)',
        'rb_once': '🕒 تشغيل مرة واحدة في وقت محدد',
        'rb_recurring': '🔁 تشغيل متكرر (دوري)',
        'lbl_target_dt': 'تاريخ ووقت التشغيل المستهدف:',
        'lbl_interval': 'فترة التكرار (للجدولة الدورية):',
        'sec_event': '3. الأتمتة القائمة على الأحداث (Event-Based)',
        'lbl_evt_cat': 'فئة الحدث:',
        'lbl_evt_trig': 'شرط الحدث:',
        'lbl_evt_val': 'القيمة المستهدفة:',
        'sec_adv': '4. الشروط المتقدمة',
        'cb_req_net': '🌐 يتطلب اتصال إنترنت للتشغيل',
        'cb_catch_up': '🔄 التدارك (التشغيل فوراً إذا فات الوقت أثناء إيقاف الجهاز)',
        'cb_play_sound': '🔊 تشغيل تنبيه صوتي عند التنفيذ',
        'btn_save_cfg': '💾 حفظ الإعدادات',

        # Create Note Dialog
        'create_dlg_title': '➕ إنشاء عنصر جديد (ملاحظة / مهمة / سكربت)',
        'create_header': '➕ إنشاء عنصر جديد',
        'lbl_title_input': '📄 العنوان:',
        'lbl_cat_input': '📁 الفئة:',
        'lbl_type_input': '📝 النوع:',
        'lbl_tags_input': '🏷️ الوسوم (تفصل بينها الفواصل):',
        'lbl_priority_input': '🎯 الأولوية (للمهمات):',
        'lbl_due_date': '📅 تاريخ الاستحقاق:',
        'lbl_content_input': '📜 المحتوى / الكود:',
        'btn_attach_file': '📎 إرفاق ملف',
        'btn_create_submit': '✨ إنشاء وحفظ',

        # Kanban Board
        'kanban_win_title': '📋 لوحة كانبان للمهمات (Kanban Board)',
        'kanban_header': '📋 لوحة متابعة المهمات',
        'col_todo': '📌 قيد الانتظار (To Do)',
        'col_in_progress': '⏳ قيد التنفيذ (In Progress)',
        'col_done': '✅ مكتملة (Done)',

        # Reminders Window
        'rem_win_title': '⏰ التذكيرات والمهام المجدولة اليوم',
        'rem_header': '⏰ جميع التذكيرات والمهام المجدولة النشطة',
        'col_rem_title': '📄 عنوان الملاحظة',
        'col_rem_time': '⏰ الوقت / المشغّل المجدول',
        'col_rem_type': '📌 نوع المهمة',

        # Git Setup
        'git_dlg_title': '⚙️ إعداد المزامنة مع GitHub',
        'git_header': '⚙️ إعداد مستودع GitHub الخاس',
        'lbl_repo_url': 'أدخل رابط مستودع GitHub الخاص بك (Repository URL):',
        'btn_init_push': '🚀 تهيئة ورفع للمستودع',

        # Voice Recorder
        'voice_win_title': '🎙️ مسجل الصوت وتحويل الكلام إلى نص حي',
        'voice_header': '🎙️ تسجيل نوتة صوتية',
        'lbl_speech_lang': '🌐 لغة الكلام:',
        'btn_start_rec': '🔴 بدء التسجيل',
        'btn_pause_rec': '⏸️ إيقاف مؤقت',
        'btn_stop_save': '⏹️ إيقاف وحفظ النوتة',

        # Common
        'success': 'نجاح',
        'error': 'خطأ',
        'warning': 'تحذير',
        'confirm': 'تأكيد'
    },
    'en': {
        # Sidebar Navigation & Tools
        'nav_cats': 'Categories',
        'nav_kanban': 'Kanban Board',
        'nav_scripts': 'Scripts',
        'nav_rems': 'Reminders',
        'nav_git': 'Git Setup',
        'nav_settings': 'Settings',
        'nav_sync': 'Sync',
        'nav_export': 'Global Export',
        'tools_header': 'Tools',
        'settings_title': '⚙️ Application Settings',
        'settings_sub': 'Customize interface language and appearance theme',
        'settings_gb_lang': '🌐 Interface Language',
        'settings_gb_theme': '🎨 Theme & Appearance',
        'settings_save': '💾 Save & Apply Settings',

        # Categories Window
        'cat_win_title': '📁 Browse & Manage Categories',
        'cat_header_lbl': '📁 Categories (Pinned 📌 first):',
        'btn_reminders': '⏰ Reminders',
        'btn_scripts': '🚀 Scripts',
        'btn_kanban': '📋 Kanban',
        'btn_setup_git': '⚙️ Setup Git',
        'btn_sync': '🔄 Sync',
        'btn_new_task': '➕ New Task',
        'btn_lang_toggle': '🌐 العربية',
        'search_lbl': '🔍 Search:',
        'sort_lbl': '↕️ Sort By:',
        'sort_visits': 'Visits',
        'sort_name': 'Name',
        'sort_date': 'Date Created',
        'col_cat_name': '📁 Category Name',
        'col_visits': '📊 Visits',
        'col_notes': '📝 Notes',
        'col_scheduled': '⏰ Scheduled',
        'col_status': '📌 Status',
        'col_actions': '⚡ Actions',
        'btn_open': '📂 Open (Enter)',
        'btn_new_cat': '📁 New Category',
        'btn_cancel': '❌ Cancel (Esc)',
        'btn_pin': '📌 Pin',
        'btn_rename': '✏️ Edit',
        'btn_delete': '🗑️ Delete',
        'status_pinned': '📌 Pinned',
        'status_normal': 'Normal',
        'visit_count': '{count} visit(s)',
        'note_count': '{count} note(s)',
        'sched_count': '⏰ {count} active',

        # Notes List Window
        'notes_win_title': '📝 Notes List',
        'notes_win_scripts_title': '🚀 Scheduled Scripts',
        'notes_header_filter': '📁 Category: {cat}',
        'notes_header_all': '📝 All Notes',
        'btn_new_note': '➕ New Note',
        'col_title': '📄 Title',
        'col_type': '📝 Type',
        'col_tags': '🏷️ Tags',
        'col_created': '📅 Date Created',
        'col_reminder': '🔔 Reminder / Schedule',
        'view_note_opt': '📖 View/Open',
        'edit_note_opt': '✏️ Edit',
        'disable_script_opt': '⏸️ Disable Script',
        'enable_script_opt': '▶️ Enable Script',
        'delete_note_opt': '🗑️ Delete',

        # View Note Window
        'view_note_title': '📄 Note: {title}',
        'btn_edit': '✏️ Edit Note',
        'btn_save_changes': '💾 Save Changes',
        'btn_voice_rec': '🎙️ Voice Record',
        'btn_exec_now': '🚀 Execute Now',
        'btn_sched_boot': '🚀 Schedule & Boot',
        'btn_disable': '⏸️ Disable',
        'btn_enable': '▶️ Enable',
        'btn_set_rem': '⏰ Set Reminder',
        'btn_mark_done': '✅ Mark as Done',
        'btn_close': '❌ Close',

        # Schedule Dialog
        'sched_dlg_title': '🚀 Advanced Schedule Setup',
        'sched_main_header': '🚀 Schedule Execution Configuration',
        'sec_boot': '1. System Boot Trigger',
        'cb_run_boot': '🚀 Run automatically every time the system boots up (@reboot)',
        'lbl_boot_delay': 'Delay execution after boot (Minutes):',
        'sec_time': '2. Time-based Schedule',
        'rb_none': '🚫 Do not schedule (Off)',
        'rb_once': '🕒 Run Once at Specific Time',
        'rb_recurring': '🔁 Run Repeatedly (Recurring)',
        'lbl_target_dt': 'Target/Start Date & Time:',
        'lbl_interval': 'Repeat Interval (if recurring):',
        'sec_event': '3. Event-Based Automation (Triggers)',
        'lbl_evt_cat': 'Event Category:',
        'lbl_evt_trig': 'Trigger Condition:',
        'lbl_evt_val': 'Target Value:',
        'sec_adv': '4. Advanced Conditions',
        'cb_req_net': '🌐 Requires Internet Connection to run',
        'cb_catch_up': '🔄 Catch-up (Run immediately if missed while PC was off)',
        'cb_play_sound': '🔊 Play Audio Alarm on Execution',
        'btn_save_cfg': '💾 Save Configuration',

        # Create Note Dialog
        'create_dlg_title': '➕ Create New Item (Note / Task / Script)',
        'create_header': '➕ Create New Item',
        'lbl_title_input': '📄 Title:',
        'lbl_cat_input': '📁 Category:',
        'lbl_type_input': '📝 Type:',
        'lbl_tags_input': '🏷️ Tags (comma separated):',
        'lbl_priority_input': '🎯 Priority (for tasks):',
        'lbl_due_date': '📅 Due Date:',
        'lbl_content_input': '📜 Content / Script Code:',
        'btn_attach_file': '📎 Attach File',
        'btn_create_submit': '✨ Create & Save',

        # Kanban Board
        'kanban_win_title': '📋 Task Kanban Board',
        'kanban_header': '📋 Task Tracking Kanban Board',
        'col_todo': '📌 To Do',
        'col_in_progress': '⏳ In Progress',
        'col_done': '✅ Done',

        # Reminders Window
        'rem_win_title': '⏰ Scheduled Reminders & Tasks Today',
        'rem_header': '⏰ All Active Scheduled Reminders & Tasks',
        'col_rem_title': '📄 Note Title',
        'col_rem_time': '⏰ Scheduled Time / Trigger',
        'col_rem_type': '📌 Task Type',

        # Git Setup
        'git_dlg_title': '⚙️ GitHub Sync Setup',
        'git_header': '⚙️ GitHub Repository Setup',
        'lbl_repo_url': 'Enter your private GitHub Repository URL:',
        'btn_init_push': '🚀 Initialize & Push',

        # Voice Recorder
        'voice_win_title': '🎙️ Voice Recording & Live Speech Transcriber',
        'voice_header': '🎙️ Voice Recorder',
        'lbl_speech_lang': '🌐 Speech Language:',
        'btn_start_rec': '🔴 Start Recording',
        'btn_pause_rec': '⏸️ Pause',
        'btn_stop_save': '⏹️ Stop & Save Note',

        # Common
        'success': 'Success',
        'error': 'Error',
        'warning': 'Warning',
        'confirm': 'Confirm'
    }
}

def tr(key, **kwargs):
    lang = get_lang()
    txt = TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS.get('en', {}).get(key, key)
    if kwargs:
        try:
            return txt.format(**kwargs)
        except Exception:
            return txt
    return txt
