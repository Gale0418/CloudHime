# ==========================================
# 🌟 雲朵翻譯姬 - 螢幕 OCR 即時翻譯工具 (｀・ω・´)ゞ
# ==========================================
# 核心引擎: Windows Media OCR (WinRT)
# 版本特性: 
# 1. Windows 原生 OCR (速度快、免依賴)
# 2. 防 Ban 機制：隨機掃描間隔 (Survival Mode)
# 3. 立即掃描冷卻機制
# ==========================================

import os
import sys
import asyncio
import ctypes
import random  # 引入隨機模組，生存率 UP!
import numpy as np
import cv2
import mss

# Windows Runtime API
from winsdk.windows.media.ocr import OcrEngine
from winsdk.windows.globalization import Language
from winsdk.windows.graphics.imaging import BitmapDecoder
from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter

from deep_translator import GoogleTranslator
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout,
                               QPushButton, QFrame, QHBoxLayout, QButtonGroup)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
from PySide6.QtGui import QCursor, QFontMetrics

# 設定 Qt 高解析度縮放
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

# ==========================================
# 🤖 OCR 與翻譯工作執行緒 (WinRT 版)
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
        
        self.init_windows_ocr()

    def init_windows_ocr(self):
        try:
            lang = Language("ja-JP")
            if not OcrEngine.is_language_supported(lang):
                print("⚠️ 警告: 系統未偵測到日文 OCR 支援。請在 Windows 設定中安裝日文語言包。")
                self.engine = OcrEngine.try_create_from_user_profile_languages()
            else:
                self.engine = OcrEngine.try_create_from_language(lang)
            
            if self.engine:
                print("✅ Windows OCR 引擎啟動成功")
            else:
                print("❌ 無法建立 OCR 引擎")

        except Exception as e:
            print(f"❌ 初始化失敗: {e}")

    async def _run_ocr_async(self, img_np):
        """
        執行 OCR (包含您的修正)
        """
        try:
            # 1. OpenCV (Numpy) -> Bytes
            success, encoded_image = cv2.imencode('.png', img_np)
            if not success:
                return None
            
            bytes_data = encoded_image.tobytes()

            # 2. Bytes -> IRandomAccessStream
            stream = InMemoryRandomAccessStream()
            writer = DataWriter(stream.get_output_stream_at(0))
            
            # [您的修正] 直接寫入 bytes，無需轉 list
            writer.write_bytes(bytes_data)
            
            await writer.store_async()
            await writer.flush_async()
            
            # 3. Decode & Recognize
            decoder = await BitmapDecoder.create_async(stream)
            software_bitmap = await decoder.get_software_bitmap_async()
            result = await self.engine.recognize_async(software_bitmap)
            return result
        except Exception as e:
            print(f"OCR Async Error: {e}")
            return None

    def run_scan_once(self):
        if not self.engine:
            self.status_msg.emit("❌ 缺少日文套件")
            self.finished.emit([])
            self.show_ui.emit()
            return

        self.hide_ui.emit()
        self.status_msg.emit("⚡ 截圖中...")
        
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            self.status_msg.emit(f"❌ 截圖錯誤: {e}")
            self.finished.emit([])
            self.show_ui.emit()
            return

        self.status_msg.emit("🔍 辨識中...")
        
        try:
            ocr_result = asyncio.run(self._run_ocr_async(img))
        except Exception as e:
            print(f"Windows OCR Error: {e}")
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

            # 計算該行的包圍框
            x_min = min([w.bounding_rect.x for w in words])
            y_min = min([w.bounding_rect.y for w in words])
            x_max = max([w.bounding_rect.x + w.bounding_rect.width for w in words])
            y_max = max([w.bounding_rect.y + w.bounding_rect.height for w in words])
            
            w = x_max - x_min
            h = y_max - y_min

            raw_items.append({'text': line_text, 'x': int(x_min), 'y': int(y_min), 'w': int(w), 'h': int(h)})

        self.show_ui.emit()

        if not raw_items:
            self.finished.emit([])
            return

        # 合併與翻譯邏輯
        merged_items = merge_horizontal_lines(raw_items)
        current_combined_text = "".join([item['text'] for item in merged_items])

        if current_combined_text == self.last_combined_text:
            self.status_msg.emit("♻️ 畫面靜止")
            self.finished.emit(self.last_results) 
            return

        self.last_combined_text = current_combined_text
        self.status_msg.emit("🌏 翻譯中...")

        final_results = []
        try:
            source_texts = [item['text'] for item in merged_items]
            combined_source = "\n".join(source_texts)
            translated_combined = self.translator.translate(combined_source)
            translated_list = translated_combined.split("\n")

            if len(translated_list) != len(merged_items):
                for item in merged_items:
                    final_results.append((item['text'], item['x'], item['y'], item['w'], item['h']))
            else:
                for i, t_text in enumerate(translated_list):
                    item = merged_items[i]
                    final_results.append((t_text.strip(), item['x'], item['y'], item['w'], item['h']))

            self.last_results = final_results
            self.status_msg.emit("✅ 完成")
            self.finished.emit(final_results)

        except Exception as e:
            print(f"翻譯失敗: {e}")
            self.status_msg.emit("⚠️ 翻譯失敗")
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

# ==========================================
# 🎮 控制器介面 (已升級功能)
# ==========================================
class Controller(QWidget):
    request_scan = Signal()

    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.is_dark_mode = False
        self.current_auto_interval = 0 # 0 表示未開啟自動
        
        self.setWindowTitle("雲朵翻譯姬")
        self.resize(320, 150)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # UI Setup
        self.frame = QFrame()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.frame)
        
        inner_layout = QVBoxLayout(self.frame)
        
        # 標題列
        title_bar = QHBoxLayout()
        self.lbl_title = QLabel("☁️雲朵翻譯姬 (Survival Mode)")
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

        # 狀態列
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

        # 按鈕群組
        btn_layout = QHBoxLayout()
        
        # 1. 立即掃描按鈕 (單次，有冷卻)
        self.btn_now = QPushButton("⚡ 立即")
        self.btn_now.setCursor(Qt.PointingHandCursor)
        self.btn_now.clicked.connect(self.on_immediate_click)
        
        # 自動掃描按鈕群組 (互斥)
        self.auto_group = QButtonGroup(self)
        self.auto_group.setExclusive(True)
        
        # 2. 隨機 30s 按鈕
        self.btn_30 = QPushButton("🎲 30s~")
        self.btn_30.setCheckable(True)
        self.btn_30.setCursor(Qt.PointingHandCursor)
        self.btn_30.clicked.connect(lambda: self.start_auto_scan(30000))
        self.auto_group.addButton(self.btn_30)

        # 3. 隨機 60s 按鈕
        self.btn_60 = QPushButton("⭐ 60s~")
        self.btn_60.setCheckable(True)
        self.btn_60.setCursor(Qt.PointingHandCursor)
        self.btn_60.clicked.connect(lambda: self.start_auto_scan(60000))
        self.auto_group.addButton(self.btn_60)
        
        btn_layout.addWidget(self.btn_now)
        btn_layout.addWidget(self.btn_30)
        btn_layout.addWidget(self.btn_60)
        inner_layout.addLayout(btn_layout)

        # 停止按鈕
        self.btn_stop = QPushButton("⏹ 停止自動")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_scan)
        inner_layout.addWidget(self.btn_stop)

        self.update_frame_style()

        # 初始化執行緒
        self.ocr_thread = QThread()
        self.worker = OCRWorker()
        self.worker.moveToThread(self.ocr_thread)
        self.request_scan.connect(self.worker.run_scan_once)
        self.worker.finished.connect(self.overlay.update_bubbles)
        self.worker.status_msg.connect(self.update_status)
        self.worker.hide_ui.connect(self.hide_ui_for_scan)
        self.worker.show_ui.connect(self.show_ui_after_scan)
        self.ocr_thread.start()

        # 計時器 (不使用固定 interval，而是動態 singleShot)
        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(True)
        self.auto_timer.timeout.connect(self.on_auto_timeout)
        
        # 立即掃描冷卻計時器
        self.cooldown_timer = QTimer(self)
        self.cooldown_timer.setSingleShot(True)
        self.cooldown_timer.timeout.connect(self.reset_immediate_btn)

        self.old_pos = None

    # --- 功能邏輯 ---

    def on_immediate_click(self):
        """⚡ 處理立即掃描：單次執行 + 10秒冷卻"""
        if self.cooldown_timer.isActive():
            return
        
        self.lbl_status.setText("⚡ 立即掃描中...")
        self.trigger_scan_sequence()
        
        # 進入冷卻
        self.btn_now.setEnabled(False)
        self.btn_now.setText("⏳ 冷卻")
        self.cooldown_timer.start(10000) # 10秒

    def reset_immediate_btn(self):
        """冷卻結束，恢復按鈕"""
        self.btn_now.setEnabled(True)
        self.btn_now.setText("⚡ 立即")

    def start_auto_scan(self, base_interval):
        """🎲 啟動隨機自動掃描"""
        # 如果已經是同一個模式，不需重啟 (或可視為重置)
        self.current_auto_interval = base_interval
        self.schedule_next_scan()

    def schedule_next_scan(self):
        """計算下一次隨機時間並排程"""
        if self.current_auto_interval == 0:
            return

        # 隨機演算法：
        # 30s -> 25~40s
        # 60s -> 50~80s
        if self.current_auto_interval == 30000:
            random_delay = random.randint(25000, 40000)
        else: # 60000
            random_delay = random.randint(50000, 80000)
            
        seconds = random_delay // 1000
        self.lbl_status.setText(f"🎲 下次掃描: {seconds}秒後")
        
        self.auto_timer.start(random_delay)

    def on_auto_timeout(self):
        """時間到，執行掃描並排程下一次"""
        if self.current_auto_interval == 0:
            return
        
        self.trigger_scan_sequence()
        # 掃描發出後，立刻排程下一次 (保持循環)
        self.schedule_next_scan()

    def stop_scan(self):
        """🛑 停止所有自動任務"""
        self.current_auto_interval = 0
        self.auto_timer.stop()
        
        # 取消按鈕選取
        self.auto_group.setExclusive(False)
        self.btn_30.setChecked(False)
        self.btn_60.setChecked(False)
        self.auto_group.setExclusive(True)
        
        self.lbl_status.setText("⏸ 自動已停止")
        self.overlay.clear_all()

    def trigger_scan_sequence(self):
        self.overlay.setVisible(False)
        QTimer.singleShot(50, self._emit_scan_signal)

    def _emit_scan_signal(self):
        self.request_scan.emit()

    def update_status(self, msg):
        # 只有在不是倒數計時的時候才覆蓋訊息
        if "下次掃描" not in self.lbl_status.text() or msg in ["⚡ 截圖中...", "🔍 辨識中...", "🌏 翻譯中...", "✅ 完成"]:
             self.lbl_status.setText(msg)

    def hide_ui_for_scan(self):
        self.overlay.setVisible(False)
        self.setVisible(False)

    def show_ui_after_scan(self):
        self.overlay.setVisible(True)
        self.setVisible(True)

    # --- UI 外觀與操作 ---

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
        else:
            bg, border, text, btn_bg = "rgba(240,248,255,230)", "#87CEEB", "#444", "#E0F7FA"
            status_bg, status_bd = "white", "#87CEEB"
            btn_fg, btn_hover, btn_chk = "#444", "#B2EBF2", "#4FC3F7"
            bulb_bg, bulb_fg = "transparent", "#555"

        self.frame.setStyleSheet(f"QFrame {{ background-color: {bg}; border-radius: 15px; border: 2px solid {border}; }}")
        self.lbl_title.setStyleSheet(f"color: {text}; font-weight: bold; background: transparent; border: none;")
        self.lbl_status.setStyleSheet(f"color: {text}; background-color: {status_bg}; border: 1px solid {status_bd}; border-radius: 4px;")
        
        # 立即按鈕樣式 (特殊色)
        now_btn_style = f"""
            QPushButton {{ background-color: {btn_bg}; color: {btn_fg}; border-radius: 8px; padding: 8px; font-weight: bold; border: 2px solid {border}; }}
            QPushButton:hover {{ background-color: {btn_hover}; }}
            QPushButton:disabled {{ background-color: #888; color: #CCC; border: 2px solid #666; }}
        """
        self.btn_now.setStyleSheet(now_btn_style)

        # 自動按鈕樣式
        auto_btn_style = f"""
            QPushButton {{ background-color: {btn_bg}; color: {btn_fg}; border-radius: 8px; padding: 8px; font-weight: bold; border: none; }}
            QPushButton:hover:!checked {{ background-color: {btn_hover}; }}
            QPushButton:checked {{ background-color: {btn_chk}; color: white; }}
        """
        self.btn_30.setStyleSheet(auto_btn_style)
        self.btn_60.setStyleSheet(auto_btn_style)

        self.btn_stop.setStyleSheet("QPushButton {{ background-color: #D32F2F; color: white; border-radius: 10px; padding: 5px; border: none; }} QPushButton:hover {{ background-color: #E57373; }}")
        self.btn_theme.setStyleSheet(f"QPushButton {{ background-color: {bulb_bg}; color: {bulb_fg}; border: none; font-size: 18px; }} QPushButton:hover {{ background-color: rgba(128,128,128,0.2); border-radius: 15px; }}")

    def close_app(self):
        self.auto_timer.stop()
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