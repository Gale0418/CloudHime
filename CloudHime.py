# ==========================================
# 🌟 雲朵翻譯姬 - 螢幕 OCR 即時翻譯工具 (｀・ω・´)ゞ
# ==========================================
# 核心引擎: Windows Media OCR (WinRT) (3x放大 + 二值化 + 靈魂滑桿)
# 翻譯引擎: Google (主) + Argos (備援)
# 特性: 全域快捷鍵 + 動態閥值調整 + 垃圾過濾
# ==========================================

import os
import sys
import asyncio
import ctypes
import random
import threading
import re
import numpy as np
import cv2
import mss
import keyboard

# Windows Runtime API
from winsdk.windows.media.ocr import OcrEngine
from winsdk.windows.globalization import Language
from winsdk.windows.graphics.imaging import BitmapDecoder
from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter

# 翻譯套件
from deep_translator import GoogleTranslator

# 繁簡轉換
try:
    from opencc import OpenCC
    OPENCC_AVAILABLE = True
except ImportError:
    OPENCC_AVAILABLE = False
    print("⚠️ 未安裝 opencc，Argos 翻譯將維持簡體。")

# Argos Translate
try:
    import argostranslate.package
    import argostranslate.translate
    ARGOS_AVAILABLE = True
except ImportError:
    ARGOS_AVAILABLE = False
    print("⚠️ 未安裝 argostranslate，將無離線功能。")

from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout,
                               QPushButton, QFrame, QHBoxLayout, QButtonGroup, 
                               QSlider) # ✨ 新增 QSlider
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
from PySide6.QtGui import QCursor, QFontMetrics

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

# ==========================================
# 🧹 垃圾過濾工具函式
# ==========================================
def is_valid_content(text):
    if not text:
        return False
    text = text.strip()
    if len(text) == 0: 
        return False
    if re.match(r'^[-_=.,|/\\:;~^]+$', text):
        return False
    has_cjk = re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', text)
    if len(text) < 2 and not has_cjk and not text.isdigit():
        return False
    if text.lower() in ['ii', 'll', 'rr', '...']:
        return False
    return True

# ==========================================
# 🤖 OCR 與翻譯工作執行緒
# ==========================================
class OCRWorker(QObject):
    finished = Signal(list)
    status_msg = Signal(str)
    screenshot_taken = Signal()
    hide_ui = Signal()
    show_ui = Signal()

    def __init__(self):
        super().__init__()
        print("🚀 初始化 Windows 原生 OCR 引擎...")
        self.engine = None
        self.translator = GoogleTranslator(source='auto', target='zh-TW')
        self.last_combined_text = ""
        self.last_results = []
        
        self.translation_cache = {}
        self.force_argos_mode = False
        self.temp_bypass_argos = False
        
        self.binary_threshold = 100 
        
        self.cc = None
        if OPENCC_AVAILABLE:
            self.cc = OpenCC('s2t')
        
        self.init_windows_ocr()
        
        if ARGOS_AVAILABLE:
            threading.Thread(target=self.init_argos_models, daemon=True).start()

    def init_windows_ocr(self):
        try:
            lang = Language("ja-JP")
            if not OcrEngine.is_language_supported(lang):
                self.engine = OcrEngine.try_create_from_user_profile_languages()
            else:
                self.engine = OcrEngine.try_create_from_language(lang)
            if self.engine:
                print("✅ Windows OCR 引擎啟動成功")
        except Exception as e:
            print(f"❌ 初始化失敗: {e}")

    def init_argos_models(self):
        try:
            argostranslate.package.update_package_index()
            available_packages = argostranslate.package.get_available_packages()
            installed_packages = argostranslate.package.get_installed_packages()
            needed_pairs = [('ja', 'en'), ('en', 'zh')]
            for from_code, to_code in needed_pairs:
                is_installed = any(p.from_code == from_code and p.to_code == to_code for p in installed_packages)
                if not is_installed:
                    pkg = next(filter(lambda x: x.from_code == from_code and x.to_code == to_code, available_packages), None)
                    if pkg:
                        pkg.install()
            print("✅ [Argos] 離線翻譯系統準備就緒")
        except Exception:
            pass

    async def _run_ocr_async(self, img_np):
        try:
            success, encoded_image = cv2.imencode('.png', img_np)
            if not success:
                return None
            stream = InMemoryRandomAccessStream()
            writer = DataWriter(stream.get_output_stream_at(0))
            writer.write_bytes(encoded_image.tobytes())
            await writer.store_async()
            await writer.flush_async()
            decoder = await BitmapDecoder.create_async(stream)
            software_bitmap = await decoder.get_software_bitmap_async()
            return await self.engine.recognize_async(software_bitmap)
        except Exception:
            return None

    def convert_to_trad(self, text):
        if self.cc:
            return self.cc.convert(text)
        return text

    def run_scan_once(self):
        if not self.engine:
            self.status_msg.emit("❌ 缺少日文套件")
            self.finished.emit([])
            self.show_ui.emit()
            return

        self.hide_ui.emit()
        
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception:
            self.finished.emit([])
            self.show_ui.emit()
            return

        self.status_msg.emit(f"🔍 辨識中 (閥值:{self.binary_threshold})...")
        
        # === ✨ 影像增強魔法 ✨ ===
        SCALE_FACTOR = 3.0
        h, w = img.shape[:2]
        img_scaled = cv2.resize(img, (int(w * SCALE_FACTOR), int(h * SCALE_FACTOR)), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img_scaled, cv2.COLOR_BGR2GRAY)
        
        _, binary = cv2.threshold(gray, self.binary_threshold, 255, cv2.THRESH_BINARY)
        img_final = cv2.bitwise_not(binary)
        
        img_for_ocr = cv2.cvtColor(img_final, cv2.COLOR_GRAY2BGR)
        # ==========================

        try:
            ocr_result = asyncio.run(self._run_ocr_async(img_for_ocr))
        except Exception:
            self.status_msg.emit("❌ 辨識錯誤")
            self.finished.emit([])
            self.show_ui.emit()
            return

        if not ocr_result or len(ocr_result.lines) == 0:
            self.handle_empty()
            return

        raw_items = []
        for line in ocr_result.lines:
            line_text = line.text
            words = line.words
            if not words or not line_text.strip():
                continue

            x_min = min([w.bounding_rect.x for w in words])
            y_min = min([w.bounding_rect.y for w in words])
            x_max = max([w.bounding_rect.x + w.bounding_rect.width for w in words])
            y_max = max([w.bounding_rect.y + w.bounding_rect.height for w in words])
            
            real_x = int(x_min / SCALE_FACTOR)
            real_y = int(y_min / SCALE_FACTOR)
            real_w = int((x_max - x_min) / SCALE_FACTOR)
            real_h = int((y_max - y_min) / SCALE_FACTOR)
            
            raw_items.append({'text': line_text, 'x': real_x, 'y': real_y, 'w': real_w, 'h': real_h})

        self.show_ui.emit()

        if not raw_items:
            self.finished.emit([])
            return

        merged_items = merge_horizontal_lines(raw_items)
        filtered_items = [item for item in merged_items if is_valid_content(item['text'])]
        
        if not filtered_items:
            self.handle_empty()
            return
            
        merged_items = filtered_items 
        current_combined_text = "".join([item['text'] for item in merged_items])

        if current_combined_text == self.last_combined_text:
            self.status_msg.emit("♻️ 畫面靜止")
            self.finished.emit(self.last_results) 
            return

        self.last_combined_text = current_combined_text
        
        final_results = []
        if len(self.translation_cache) > 1000:
            self.translation_cache.clear()

        try:
            use_argos = self.force_argos_mode and not self.temp_bypass_argos and ARGOS_AVAILABLE

            if use_argos:
                total_items = len(merged_items)
                for i, item in enumerate(merged_items):
                    src_text = item['text']
                    if src_text in self.translation_cache:
                        trans_text = self.translation_cache[src_text]
                    else:
                        self.status_msg.emit(f"🚀 Argos {i+1}/{total_items}")
                        try:
                            simplified_text = argostranslate.translate.translate(src_text, 'ja', 'zh')
                            trans_text = self.convert_to_trad(simplified_text)
                            self.translation_cache[src_text] = trans_text
                        except Exception:
                            trans_text = src_text
                    final_results.append((trans_text.strip(), item['x'], item['y'], item['w'], item['h']))
            else:
                self.status_msg.emit("🌏 Google...")
                source_texts = [item['text'] for item in merged_items]
                combined_source = "\n".join(source_texts)
                
                try:
                    translated_combined = self.translator.translate(combined_source)
                except Exception:
                    if ARGOS_AVAILABLE:
                        try:
                            simplified = argostranslate.translate.translate(combined_source, 'ja', 'zh')
                            translated_combined = self.convert_to_trad(simplified)
                        except Exception:
                            translated_combined = combined_source
                    else:
                        translated_combined = combined_source
                
                translated_list = translated_combined.split("\n")
                if len(translated_list) != len(merged_items):
                    for item in merged_items:
                        final_results.append((item['text'], item['x'], item['y'], item['w'], item['h']))
                else:
                    for i, t_text in enumerate(translated_list):
                        item = merged_items[i]
                        trans_text = t_text.strip()
                        self.translation_cache[item['text']] = trans_text
                        final_results.append((trans_text, item['x'], item['y'], item['w'], item['h']))

            self.temp_bypass_argos = False
            self.last_results = final_results
            self.status_msg.emit("✅ 完成")
            self.finished.emit(final_results)

        except Exception as e:
            print(f"Error: {e}")
            self.status_msg.emit("⚠️ 翻譯失敗")
            self.temp_bypass_argos = False 
            fallback = [(item['text'], item['x'], item['y'], item['w'], item['h']) for item in merged_items]
            self.last_results = fallback
            self.finished.emit(fallback)

    def handle_empty(self):
        if self.last_combined_text != "":
            self.status_msg.emit("💤 畫面無文字")
            self.last_combined_text = ""
            self.last_results = []
        self.finished.emit([])
        self.show_ui.emit()

def merge_horizontal_lines(items):
    if not items:
        return []
    items.sort(key=lambda k: k['y'])
    lines = []
    current_line = [items[0]]
    for i in range(1, len(items)):
        curr = items[i]
        prev = current_line[-1]
        prev_cy = prev['y'] + prev['h'] / 2
        curr_cy = curr['y'] + curr['h'] / 2
        if abs(prev_cy - curr_cy) < (min(prev['h'], curr['h']) * 0.5):
            current_line.append(curr)
        else:
            lines.append(current_line)
            current_line = [curr]
    lines.append(current_line)
    merged = []
    for line in lines:
        line.sort(key=lambda k: k['x'])
        idx = 0
        while idx < len(line):
            base = line[idx]
            text = base['text']
            x1, y1 = base['x'], base['y']
            x2, y2 = base['x']+base['w'], base['y']+base['h']
            next_idx = idx + 1
            while next_idx < len(line):
                cand = line[next_idx]
                if cand['x'] - x2 < (base['h'] * 2.0):
                    text += " " + cand['text']
                    x2 = cand['x'] + cand['w']
                    y2 = max(y2, cand['y'] + cand['h'])
                    y1 = min(y1, cand['y'])
                    next_idx += 1
                else:
                    break
            merged.append({'text': text, 'x': x1, 'y': y1, 'w': x2-x1, 'h': y2-y1})
            idx = next_idx
    return merged

class TransBubble(QLabel):
    def __init__(self, parent, text, x, y, w, h, is_dark_mode=False):
        super().__init__(parent)
        self.setText(text)
        self.set_theme(is_dark_mode)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        best_size = self.fit_text_strictly(text, w+2, h+2)
        font = self.font()
        font.setFamily("Microsoft JhengHei")
        font.setPixelSize(best_size)
        font.setBold(True)
        self.setFont(font)
        self.setGeometry(x-1, y-1, w+2, h+2)
        self.show()

    def set_theme(self, is_dark):
        if is_dark:
            self.setStyleSheet("background-color: rgba(35,35,35,255); color: #FFFFFF; font-weight: bold; border-radius: 2px; border: 1px solid #555;")
        else:
            self.setStyleSheet("background-color: rgba(255,255,255,255); color: #000; font-weight: bold; border-radius: 2px; border: 1px solid #DDD;")

    def fit_text_strictly(self, text, w, h):
        font = self.font()
        font.setFamily("Microsoft JhengHei")
        font.setBold(True)
        for size in range(40, 7, -1):
            font.setPixelSize(size)
            if QFontMetrics(font).boundingRect(0, 0, w, 0, Qt.TextWordWrap, text).height() <= h:
                return size
        return 8

class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())
        self.bubbles = []
        self.is_dark = False
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), 0x00000011)
        except Exception:
            pass
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.ghost_mode)
        self.timer.start(50)

    def set_theme_mode(self, is_dark):
        self.is_dark = is_dark
        for b in self.bubbles:
            b.set_theme(is_dark)

    def update_bubbles(self, results):
        self.clear_all()
        for t, x, y, w, h in results:
            self.bubbles.append(TransBubble(self, t, x, y, w, h, self.is_dark))
        self.setVisible(True)

    def clear_all(self):
        for b in self.bubbles:
            b.deleteLater()
        self.bubbles = []

    def ghost_mode(self):
        if not self.isVisible():
            return
        pos = self.mapFromGlobal(QCursor.pos())
        for b in self.bubbles:
            b.setVisible(not b.geometry().adjusted(-20,-20,20,20).contains(pos))

class Controller(QWidget):
    request_scan = Signal()

    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.is_dark_mode = False
        self.current_auto_interval = 0 
        self.countdown_seconds = 0
        
        self.setWindowTitle("雲朵翻譯姬")
        self.resize(320, 180) 
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.frame = QFrame()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.frame)
        
        inner_layout = QVBoxLayout(self.frame)
        
        title_bar = QHBoxLayout()
        self.lbl_title = QLabel("☁️雲朵翻譯姬 (Slider)")
        self.lbl_title.setStyleSheet("font-weight: bold; border: none; background: transparent;")
        
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(24,24)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.close_app)
        self.btn_close.setStyleSheet("background:transparent; color:#888; border:none; font-weight:900;")
        
        title_bar.addWidget(self.lbl_title)
        title_bar.addStretch()
        title_bar.addWidget(self.btn_close)
        inner_layout.addLayout(title_bar)

        slider_layout = QHBoxLayout()
        self.lbl_thresh = QLabel("閥值: 100")
        self.lbl_thresh.setStyleSheet("font-size: 10px; color: #666;")
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(50, 240) 
        self.slider.setValue(100)     
        self.slider.valueChanged.connect(self.update_threshold)
        
        slider_layout.addWidget(QLabel("🌑"))
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(QLabel("🌕"))
        slider_layout.addWidget(self.lbl_thresh)
        inner_layout.addLayout(slider_layout)

        status_row = QHBoxLayout()
        self.lbl_status = QLabel("準備就緒 (｀・ω・´)")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setFixedHeight(30)
        
        self.btn_theme = QPushButton("💡")
        self.btn_theme.setFixedSize(30, 30)
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        
        status_row.addWidget(self.lbl_status)
        status_row.addWidget(self.btn_theme)
        inner_layout.addLayout(status_row)

        btn_layout = QHBoxLayout()
        self.btn_now = QPushButton("⚡ 立即 (~)")
        self.btn_now.setCursor(Qt.PointingHandCursor)
        self.btn_now.clicked.connect(self.on_immediate_click)
        
        self.auto_group = QButtonGroup(self)
        self.auto_group.setExclusive(True)
        
        self.btn_30 = QPushButton("🎲 30s~")
        self.btn_30.setCheckable(True)
        self.btn_30.setCursor(Qt.PointingHandCursor)
        self.btn_30.clicked.connect(lambda: self.start_auto_scan(30000))
        self.auto_group.addButton(self.btn_30)

        self.btn_60 = QPushButton("⭐ 60s~")
        self.btn_60.setCheckable(True)
        self.btn_60.setCursor(Qt.PointingHandCursor)
        self.btn_60.clicked.connect(lambda: self.start_auto_scan(60000))
        self.auto_group.addButton(self.btn_60)
        
        btn_layout.addWidget(self.btn_now)
        btn_layout.addWidget(self.btn_30)
        btn_layout.addWidget(self.btn_60)
        inner_layout.addLayout(btn_layout)

        stop_layout = QHBoxLayout()
        self.btn_rapid = QPushButton("🔥 急速 (Argos)")
        self.btn_rapid.setCheckable(True)
        self.btn_rapid.setCursor(Qt.PointingHandCursor)
        self.btn_rapid.clicked.connect(self.start_rapid_scan)
        self.auto_group.addButton(self.btn_rapid)
        
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_scan)
        
        stop_layout.addWidget(self.btn_rapid)
        stop_layout.addWidget(self.btn_stop)
        inner_layout.addLayout(stop_layout)

        self.update_frame_style()

        self.ocr_thread = QThread()
        self.worker = OCRWorker()
        self.worker.moveToThread(self.ocr_thread)
        self.request_scan.connect(self.worker.run_scan_once)
        self.worker.finished.connect(self.on_scan_complete)
        self.worker.status_msg.connect(self.update_status)
        self.worker.hide_ui.connect(self.hide_ui_for_scan)
        self.worker.show_ui.connect(self.show_ui_after_scan)
        self.ocr_thread.start()

        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(True)
        self.auto_timer.timeout.connect(self.trigger_scan_sequence)
        
        self.display_timer = QTimer(self)
        self.display_timer.setInterval(1000)
        self.display_timer.timeout.connect(self.update_countdown_label)
        
        self.cooldown_timer = QTimer(self)
        self.cooldown_timer.setSingleShot(True)
        self.cooldown_timer.timeout.connect(self.reset_immediate_btn)

        self.old_pos = None
        self.setup_global_hotkey()

    def update_threshold(self, val):
        self.lbl_thresh.setText(f"閥值: {val}")
        self.worker.binary_threshold = val

    def setup_global_hotkey(self):
        HOTKEY = '`'
        try:
            keyboard.add_hotkey(HOTKEY, self.on_hotkey_pressed)
            print(f"✅ 全域快捷鍵已啟動: 按下 [{HOTKEY}] 鍵觸發 (請務必以管理員身分執行！)")
        except Exception as e:
            print(f"❌ 快捷鍵註冊失敗: {e}")

    def on_hotkey_pressed(self):
        QTimer.singleShot(0, self.on_immediate_click)

    def on_immediate_click(self):
        if self.cooldown_timer.isActive():
            print("❄️ 冷卻中...請稍後")
            return
        
        self.worker.temp_bypass_argos = True
        self.display_timer.stop()
        self.lbl_status.setText("⚡ 立即掃描中...")
        self.trigger_scan_sequence()
        self.btn_now.setEnabled(False)
        self.btn_now.setText("⏳ 冷卻")
        self.cooldown_timer.start(10000)

    def reset_immediate_btn(self):
        self.btn_now.setEnabled(True)
        self.btn_now.setText("⚡ 立即 (~)")

    def start_auto_scan(self, base_interval):
        self.worker.force_argos_mode = False
        self.current_auto_interval = base_interval
        self.schedule_next_scan()

    def start_rapid_scan(self):
        if not ARGOS_AVAILABLE:
            self.lbl_status.setText("⚠️ 無 Argos 套件")
            self.btn_rapid.setChecked(False)
            return
        self.worker.force_argos_mode = True
        self.current_auto_interval = 5000
        self.schedule_next_scan()

    def schedule_next_scan(self):
        if self.current_auto_interval == 0:
            return
        if self.current_auto_interval == 5000:
            delay = 5000
        elif self.current_auto_interval == 30000:
            delay = random.randint(25000, 40000)
        else:
            delay = random.randint(50000, 80000)
        self.auto_timer.start(delay)
        self.countdown_seconds = delay // 1000
        self.update_countdown_label()
        self.display_timer.start()

    def update_countdown_label(self):
        if self.current_auto_interval == 0: 
            self.display_timer.stop()
            return
        prefix = "🚀 急速" if self.current_auto_interval == 5000 else "⏳ 隨機"
        self.lbl_status.setText(f"{prefix}倒數: {self.countdown_seconds}s")
        self.countdown_seconds -= 1
        if self.countdown_seconds < 0:
            self.display_timer.stop()

    def on_scan_complete(self, results):
        self.overlay.update_bubbles(results)
        if self.current_auto_interval > 0:
            self.schedule_next_scan()

    def stop_scan(self):
        self.worker.force_argos_mode = False
        self.current_auto_interval = 0
        self.auto_timer.stop()
        self.display_timer.stop()
        self.auto_group.setExclusive(False)
        self.btn_30.setChecked(False)
        self.btn_60.setChecked(False)
        self.btn_rapid.setChecked(False)
        self.auto_group.setExclusive(True)
        self.lbl_status.setText("⏸ 自動已停止")
        self.overlay.clear_all()

    def trigger_scan_sequence(self):
        self.display_timer.stop()
        self.overlay.setVisible(False)
        QTimer.singleShot(50, self._emit_scan_signal)

    def _emit_scan_signal(self):
        self.request_scan.emit()

    def update_status(self, msg):
        if "Argos" in msg:
            self.lbl_status.setText(msg)
            return
        if self.display_timer.isActive() and "完成" not in msg:
            return
        self.lbl_status.setText(msg)

    def hide_ui_for_scan(self):
        self.overlay.setVisible(False)
        self.setVisible(False)

    def show_ui_after_scan(self):
        self.overlay.setVisible(True)
        self.setVisible(True)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.update_frame_style()
        self.overlay.set_theme_mode(self.is_dark_mode)

    def update_frame_style(self):
        if self.is_dark_mode:
            bg, border, text, btn_bg = "rgba(45,45,45,240)", "#555", "#E0E0E0", "#424242"
            status_bg, status_bd = "#3A3A3A", "#555"
            btn_fg, btn_hover, btn_chk = "#E0E0E0", "#505050", "#00ACC1"
            bulb_bg, bulb_fg = "transparent", "#FFEB3B"
            rapid_bg, rapid_hover = "#E65100", "#EF6C00"
        else:
            bg, border, text, btn_bg = "rgba(240,248,255,230)", "#87CEEB", "#444", "#E0F7FA"
            status_bg, status_bd = "white", "#87CEEB"
            btn_fg, btn_hover, btn_chk = "#444", "#B2EBF2", "#4FC3F7"
            bulb_bg, bulb_fg = "transparent", "#555"
            rapid_bg, rapid_hover = "#FF9800", "#FFB74D"

        self.frame.setStyleSheet(f"QFrame {{ background-color: {bg}; border-radius: 15px; border: 2px solid {border}; }}")
        self.lbl_title.setStyleSheet(f"color: {text}; font-weight: bold; background: transparent; border: none;")
        self.lbl_status.setStyleSheet(f"color: {text}; background-color: {status_bg}; border: 1px solid {status_bd}; border-radius: 4px;")
        
        # 滑桿樣式
        self.lbl_thresh.setStyleSheet(f"color: {text}; font-size: 10px;")

        now_btn_style = f"""
            QPushButton {{ background-color: {btn_bg}; color: {btn_fg}; border-radius: 8px; padding: 8px; font-weight: bold; border: 2px solid {border}; }}
            QPushButton:hover {{ background-color: {btn_hover}; }}
            QPushButton:disabled {{ background-color: #888; color: #CCC; border: 2px solid #666; }}
        """
        self.btn_now.setStyleSheet(now_btn_style)

        auto_btn_style = f"""
            QPushButton {{ background-color: {btn_bg}; color: {btn_fg}; border-radius: 8px; padding: 8px; font-weight: bold; border: none; }}
            QPushButton:hover:!checked {{ background-color: {btn_hover}; }}
            QPushButton:checked {{ background-color: {btn_chk}; color: white; }}
        """
        self.btn_30.setStyleSheet(auto_btn_style)
        self.btn_60.setStyleSheet(auto_btn_style)
        
        rapid_btn_style = f"""
            QPushButton {{ background-color: {rapid_bg}; color: white; border-radius: 8px; padding: 8px; font-weight: bold; border: none; }}
            QPushButton:hover:!checked {{ background-color: {rapid_hover}; }}
            QPushButton:checked {{ background-color: {btn_chk}; border: 2px solid {rapid_bg}; }}
        """
        self.btn_rapid.setStyleSheet(rapid_btn_style)

        self.btn_stop.setStyleSheet("QPushButton {{ background-color: #D32F2F; color: white; border-radius: 10px; padding: 5px; border: none; }} QPushButton:hover {{ background-color: #E57373; }}")
        self.btn_theme.setStyleSheet(f"QPushButton {{ background-color: {bulb_bg}; color: {bulb_fg}; border: none; font-size: 18px; }} QPushButton:hover {{ background-color: rgba(128,128,128,0.2); border-radius: 15px; }}")

    def close_app(self):
        keyboard.unhook_all()
        self.auto_timer.stop()
        self.display_timer.stop()
        self.cooldown_timer.stop()
        self.ocr_thread.quit()
        self.ocr_thread.wait()
        self.overlay.close()
        self.close()
        QApplication.instance().quit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x()+delta.x(), self.y()+delta.y())
            self.old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event): self.old_pos = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = OverlayWindow()
    overlay.show()
    ctrl = Controller(overlay)
    ctrl.show()
    sys.exit(app.exec())