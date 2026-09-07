import os
import sys
import time
import signal
import shutil
import threading
import subprocess
try:
    import speech_recognition as sr
except ImportError:
    sr = None

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QComboBox, QPushButton, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import NOTES_DIR, get_category_media_dir, BG_MAIN, BG_CARD, FG_GREEN, FG_TEXT, FG_MUTED, BTN_RED, BTN_BLUE, BTN_AMBER, BTN_GRAY
from utils import center_window
from ui_common import apply_rtl_to_widget, get_common_qss, create_horizontal_button, FONT_ARABIC
from i18n import tr


class VoiceRecorderDialog(QDialog):
    transcription_updated = pyqtSignal(str)
    transcription_finished = pyqtSignal()

    def __init__(self, parent=None, target_text_widget=None, category="general"):
        super().__init__(parent)
        self.target_text_widget = target_text_widget
        self.category = category
        self.result_file = ""
        self.result_text = ""

        self.is_recording = False
        self.is_paused = False
        self.rec_proc = None
        self.elapsed_sec = 0
        self.rec_filepath = ""
        self.accumulated_transcription = ""
        self.recognizer = sr.Recognizer() if sr else None


        self.setWindowTitle(tr('voice_win_title'))
        self.resize(640, 480)
        self.setMinimumSize(580, 420)
        self.setStyleSheet(get_common_qss())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header
        lbl = QLabel(tr('voice_header'))
        lbl.setStyleSheet(f"color: {FG_GREEN}; font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl)

        # Language selection
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("🌐 لغة التعرف على الكلام:"))
        self.lang_cb = QComboBox()
        self.lang_cb.addItems(["ar-YE (العربية)", "ar-SA (العربية)", "en-US (English)"])
        self.lang_cb.setCurrentText("ar-YE (العربية)")
        lang_layout.addWidget(self.lang_cb)
        lang_layout.addStretch()
        layout.addLayout(lang_layout)

        # Timer
        self.timer_lbl = QLabel("⏱️ 00:00")
        self.timer_lbl.setAlignment(Qt.AlignCenter)
        self.timer_lbl.setStyleSheet(f"background-color: {BG_CARD}; color: #00FF00; font-family: Monospace; font-size: 28px; font-weight: bold; padding: 10px 24px; border-radius: 4px;")
        layout.addWidget(self.timer_lbl)

        # Status
        self.status_lbl = QLabel("اضغط '🔴 بدء التسجيل' لتسجيل ملاحظة صوتية عبر الميكروفون:")
        self.status_lbl.setStyleSheet(f"color: {FG_MUTED};")
        layout.addWidget(self.status_lbl)

        # Live transcription
        self.live_box = QTextEdit()
        self.live_box.setReadOnly(True)
        apply_rtl_to_widget(self.live_box)
        layout.addWidget(self.live_box, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_start = create_horizontal_button(tr('btn_start_rec'), BTN_RED, self.start_rec, is_primary=True)
        self.btn_pause = create_horizontal_button(tr('btn_pause_rec'), BTN_GRAY, self.toggle_pause)
        self.btn_pause.setEnabled(False)
        self.btn_stop = create_horizontal_button(tr('btn_stop_save'), BTN_GRAY, self.stop_rec)
        self.btn_stop.setEnabled(False)
        btn_cancel = create_horizontal_button(tr('btn_cancel'), BTN_GRAY, self.reject)

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_pause)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        # QTimer for updating the clock
        self.qtimer = QTimer(self)
        self.qtimer.timeout.connect(self._tick_timer)

        self.transcription_updated.connect(self._update_live_box)
        self.transcription_finished.connect(self._finalize_save)

        center_window(self, 640, 480)

    def _update_live_box(self, text):
        self.live_box.setPlainText(text)
        apply_rtl_to_widget(self.live_box, text)

    def _tick_timer(self):
        if self.is_recording and not self.is_paused:
            self.elapsed_sec += 1
            m = self.elapsed_sec // 60
            s = self.elapsed_sec % 60
            self.timer_lbl.setText(f"🔴 {m:02d}:{s:02d}")

    def live_transcribe_worker(self, wav_path, target_lang):
        if not (sr and self.recognizer):
            return
        try:
            with sr.AudioFile(wav_path) as source:
                audio = self.recognizer.record(source)
            text = self.recognizer.recognize_google(audio, language=target_lang)
            if text:
                self.accumulated_transcription = text
                # Only update the live preview box inside this dialog, never overwrite the note's text widget
                self.transcription_updated.emit(text)
        except Exception:
            pass

    def real_time_transcription_loop(self, out_wav, target_lang):
        while self.is_recording:
            time.sleep(2.5)
            if not self.is_recording: break
            if not self.is_paused and os.path.exists(out_wav) and os.path.getsize(out_wav) > 8000:
                threading.Thread(target=self.live_transcribe_worker, args=(out_wav, target_lang), daemon=True).start()


    def start_rec(self):
        if self.is_recording: return
        arecord_bin = shutil.which("arecord")
        if not arecord_bin:
            QMessageBox.critical(self, "خطأ", "أداة التسجيل الصوتي arecord غير مثبتة في النظام!")
            return

        ts = int(time.time())
        media_dir = get_category_media_dir(self.category)
        out_wav = os.path.join(media_dir, f"voice_{ts}.wav")
        self.rec_filepath = out_wav
        sel_lang = self.lang_cb.currentText().split()[0]

        try:
            self.rec_proc = subprocess.Popen(
                [arecord_bin, "-f", "S16_LE", "-r", "16000", "-c", "1", out_wav],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self.is_recording = True
            self.is_paused = False
            self.elapsed_sec = 0

            self.btn_start.setEnabled(False)
            self.btn_start.setStyleSheet(f"background-color: {BTN_GRAY}; color: white;")
            self.btn_pause.setEnabled(True)
            self.btn_pause.setStyleSheet(f"background-color: {BTN_AMBER}; color: white; font-weight: bold;")
            self.btn_stop.setEnabled(True)
            self.btn_stop.setStyleSheet(f"background-color: {BTN_RED}; color: white; font-weight: bold;")
            self.status_lbl.setText("🎙️ جاري التسجيل الصوتي المباشر... تحدث في الميكروفون:")
            self.status_lbl.setStyleSheet(f"color: {FG_GREEN};")

            self.qtimer.start(1000)
            threading.Thread(target=self.real_time_transcription_loop, args=(out_wav, sel_lang), daemon=True).start()
        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"تعذر بدء التسجيل الصوتي: {e}")

    def toggle_pause(self):
        if not self.is_recording or not self.rec_proc: return
        pid = self.rec_proc.pid

        if not self.is_paused:
            self.is_paused = True
            try: os.kill(pid, signal.SIGSTOP)
            except: pass
            m = self.elapsed_sec // 60
            s = self.elapsed_sec % 60
            self.timer_lbl.setText(f"⏸️ {m:02d}:{s:02d}")
            self.timer_lbl.setStyleSheet(self.timer_lbl.styleSheet().replace("#00FF00", BTN_AMBER))
            self.btn_pause.setText("▶️ استئناف")
            self.status_lbl.setText("⏸️ التسجيل متوقف مؤقتاً. اضغط '▶️ استئناف' للمتابعة.")
        else:
            self.is_paused = False
            try: os.kill(pid, signal.SIGCONT)
            except: pass
            m = self.elapsed_sec // 60
            s = self.elapsed_sec % 60
            self.timer_lbl.setText(f"🔴 {m:02d}:{s:02d}")
            self.timer_lbl.setStyleSheet(self.timer_lbl.styleSheet().replace(BTN_AMBER, "#00FF00"))
            self.btn_pause.setText("⏸️ إيقاف مؤقت")
            self.status_lbl.setText("🎙️ تم استئناف التسجيل وجاري تحويل الصوت لنص...")

    def stop_rec(self):
        if not self.is_recording: return

        if self.is_paused and self.rec_proc:
            try: os.kill(self.rec_proc.pid, signal.SIGCONT)
            except: pass

        self.is_recording = False
        self.is_paused = False
        self.qtimer.stop()

        if self.rec_proc:
            self.rec_proc.terminate()
            try: self.rec_proc.wait(timeout=2)
            except: pass

        out_wav = self.rec_filepath
        sel_lang = self.lang_cb.currentText().split()[0]

        self.status_lbl.setText("⏳ جاري إنهاء تحويل الصوت وحفظ التسجيل...")

        from PyQt5.QtWidgets import QProgressDialog
        self.progress_dlg = QProgressDialog("⏳ جاري معالجة الصوت واستخراج النص...", None, 0, 0, self)
        self.progress_dlg.setWindowModality(Qt.WindowModal)
        self.progress_dlg.setWindowTitle("جاري المعالجة...")
        self.progress_dlg.setCancelButton(None)
        self.progress_dlg.show()

        def final_worker():
            if sr and self.recognizer and os.path.exists(out_wav) and os.path.getsize(out_wav) > 4000:
                try:
                    with sr.AudioFile(out_wav) as source:
                        audio = self.recognizer.record(source)
                    final_text = self.recognizer.recognize_google(audio, language=sel_lang)
                    if final_text:
                        self.accumulated_transcription = final_text
                except Exception:
                    pass
            self.transcription_finished.emit()
            
        threading.Thread(target=final_worker, daemon=True).start()

    def _finalize_save(self):
        if hasattr(self, 'progress_dlg') and self.progress_dlg:
            self.progress_dlg.close()
            
        out_wav = self.rec_filepath
        if os.path.exists(out_wav) and os.path.getsize(out_wav) > 4000:
            rel_path = os.path.relpath(out_wav, NOTES_DIR)
            self.result_file = rel_path
            transcribed = self.accumulated_transcription.strip()

            if transcribed:
                self.result_text = f"\n{transcribed}\n\n[ 🎙️ Voice Audio Attachment: {os.path.basename(out_wav)} ]\n"
            else:
                self.result_text = f"\n[ 🎙️ Voice Audio Attachment: {os.path.basename(out_wav)} ]\n"

            QMessageBox.information(self, "تم الحفظ وتحويل النص",
                f"✅ تم حفظ التسجيل الصوتي في '{self.category}/media/'!\nالمرفق: {rel_path}")
            self.accept()
        else:
            QMessageBox.warning(self, "تحذير", "التسجيل الصوتي فارغ أو قصير جداً!")
            self.reject()


def record_voice_dialog(parent=None, target_text_widget=None, category="general"):
    dlg = VoiceRecorderDialog(parent, target_text_widget, category)
    dlg.exec_()
    return dlg.result_file, dlg.result_text
