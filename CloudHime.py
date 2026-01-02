import os
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

import sys
import ctypes 
import numpy as np
import cv2
import mss
import paddle 
from deep_translator import GoogleTranslator
from paddleocr import PaddleOCR
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                               QPushButton, QFrame, QHBoxLayout, QButtonGroup)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
from PySide6.QtGui import QCursor, QFontMetrics

# ==========================================
# 🧠 OCR + 翻譯 Worker (邏輯保持不變)
# ==========================================
class OCRWorker(QObject):
    finished = Signal(list)
    status_msg = Signal(str)
    screenshot_taken = Signal() 
    hide_ui = Signal()
    show_ui = Signal()

    def __init__(self, lang='japan'):
        super().__init__()
        print("🚀 初始化 OCR 引擎中... (2026 Cloud Edition)")
        self.ocr = None
        
        try:
            paddle.device.set_device("gpu")
            self.ocr = PaddleOCR(use_textline_orientation=False, lang=lang, use_gpu=True, show_log=False)
            dummy = np.zeros((32, 32, 3), dtype=np.uint8)
            _ = self.ocr.ocr(dummy)
            print("✅ GPU 模式火力全開！")
        except Exception as e:
            print(f"⚠️ GPU 受阻，切換 CPU: {e}")
            try:
                paddle.device.set_device("cpu")
                self.ocr = PaddleOCR(use_textline_orientation=False, lang=lang, use_gpu=False, enable_mkldnn=True, show_log=False)
            except Exception:
                self.ocr = PaddleOCR(use_textline_orientation=False, lang=lang, use_gpu=False, show_log=False)

        self.translator = GoogleTranslator(source='auto', target='zh-TW')
        self.last_combined_text = ""
        self.last_results = []

    def run_scan_once(self):
        self.hide_ui.emit()  # 隱藏UI避免掃描到自己
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
            self.last_combined_text = ""
            self.last_results = []
            self.show_ui.emit()  # 顯示UI
            return

        self.status_msg.emit("🔍 辨識中...")
        try:
            result = self.ocr.ocr(img)
        except Exception:
            self.status_msg.emit("❌ OCR 運算錯誤")
            self.finished.emit([])
            self.last_combined_text = ""
            self.last_results = []
            self.show_ui.emit()  # 顯示UI
            return

        if not result or not result[0]:
            if self.last_combined_text != "":
                self.status_msg.emit("💤 畫面無文字")
                self.finished.emit([]) 
                self.last_combined_text = ""
                self.last_results = []
            else:
                self.finished.emit([]) 
            self.show_ui.emit()  # 顯示UI
            return

        raw_items = []
        for line in result[0]:
            text, confidence = line[1]
            if confidence < 0.5 or not text.strip():
                continue
            box = line[0]
            x, y = int(box[0][0]), int(box[0][1])
            w, h = int(box[2][0]-box[0][0]), int(box[2][1]-box[0][1])
            raw_items.append({'text': text, 'x': x, 'y': y, 'w': w, 'h': h})

        self.show_ui.emit()  # 辨識完成後立即恢復UI

        if not raw_items:
            self.finished.emit([])
            return

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
            self.last_combined_text = current_combined_text
            self.status_msg.emit("✅ 完成")
            self.finished.emit(fallback)

# ==========================================
# 📐 合併算法
# ==========================================
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
        y_overlap = abs(prev_cy - curr_cy) < (min(prev['h'], curr['h']) * 0.5)
        
        if y_overlap:
            current_line.append(curr)
        else:
            lines.append(current_line)
            current_line = [curr]
    lines.append(current_line)

    merged_results = []
    for line in lines:
        line.sort(key=lambda k: k['x'])
        idx = 0
        while idx < len(line):
            base = line[idx]
            text_acc = base['text']
            x_min, y_min = base['x'], base['y']
            x_max, y_max = base['x'] + base['w'], base['y'] + base['h']
            
            next_idx = idx + 1
            while next_idx < len(line):
                candidate = line[next_idx]
                dist_x = candidate['x'] - x_max
                if dist_x < (base['h'] * 2.0): 
                    text_acc += " " + candidate['text']
                    x_max = candidate['x'] + candidate['w']
                    y_max = max(y_max, candidate['y'] + candidate['h'])
                    y_min = min(y_min, candidate['y'])
                    next_idx += 1
                else:
                    break
            
            merged_results.append({
                'text': text_acc,
                'x': x_min, 'y': y_min, 'w': x_max - x_min, 'h': y_max - y_min
            })
            idx = next_idx
    return merged_results

# ==========================================
# ☁️ 雲朵氣泡 (支援深色模式)
# ==========================================
class TransBubble(QLabel):
    def __init__(self, parent, text, x, y, w, h, is_dark_mode=False):
        super().__init__(parent)
        self.setText(text)
        final_x = x - 1
        final_y = y - 1
        final_w = w + 2
        final_h = h + 2

        self.set_theme(is_dark_mode) # 設定初始顏色

        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)

        best_font_size = self.fit_text_strictly(text, final_w, final_h)
        
        font = self.font()
        font.setFamily("Microsoft JhengHei")
        font.setPixelSize(best_font_size)
        font.setBold(True)
        self.setFont(font)

        self.setGeometry(final_x, final_y, final_w, final_h)
        self.show()

    def set_theme(self, is_dark):
        """根據模式設定氣泡顏色"""
        if is_dark:
            # 深色模式：深灰底、白字、深灰邊框
            self.setStyleSheet("""
                background-color: rgba(35, 35, 35, 255);
                color: #FFFFFF;
                font-weight: bold; 
                border-radius: 2px;
                padding: 0px;
                border: 1px solid #555555;
            """)
        else:
            # 淺色模式：白底、黑字、淺灰邊框
            self.setStyleSheet("""
                background-color: rgba(255, 255, 255, 255);
                color: #000000;
                font-weight: bold; 
                border-radius: 2px;
                padding: 0px;
                border: 1px solid #DDDDDD;
            """)

    def fit_text_strictly(self, text, w, h):
        font = self.font()
        font.setFamily("Microsoft JhengHei")
        font.setBold(True)
        
        for size in range(40, 7, -1):
            font.setPixelSize(size)
            fm = QFontMetrics(font)
            rect = fm.boundingRect(0, 0, w, 0, Qt.TextWordWrap, text)
            if rect.height() <= h:
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
        self.is_dark_mode = False # 記錄當前狀態

        try:
            hwnd = self.winId()
            ctypes.windll.user32.SetWindowDisplayAffinity(int(hwnd), 0x00000011)
        except Exception:
            pass
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.ghost_mode_check)
        self.timer.start(50)

    def set_theme_mode(self, is_dark):
        self.is_dark_mode = is_dark
        # 更新所有現存氣泡
        for b in self.bubbles:
            b.set_theme(is_dark)

    def update_bubbles(self, results):
        self.clear_all()
        for text, x, y, w, h in results:
            # 傳入當前的顏色設定
            bubble = TransBubble(self, text, x, y, w, h, self.is_dark_mode)
            self.bubbles.append(bubble)
        
        self.setVisible(True)

    def clear_all(self):
        for b in self.bubbles:
            b.deleteLater()
        self.bubbles = []

    def ghost_mode_check(self):
        if not self.isVisible():
            return

        cursor_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(cursor_pos)
        for bubble in self.bubbles:
            rect = bubble.geometry().adjusted(-20, -20, 20, 20)
            bubble.setVisible(not rect.contains(local_pos))

# ==========================================
# 🎮 UI 控制器 (新增深色模式開關)
# ==========================================
class Controller(QWidget):
    request_scan = Signal()

    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.is_dark_mode = False  # 預設淺色
        self.setWindowTitle("雲朵翻譯姬")
        self.resize(320, 150)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10) # 讓陰影或邊緣有一點空間
        
        # 主框架
        self.frame = QFrame()
        # self.update_frame_style() # 初始化樣式 移除，因為widgets還沒創建

        inner_layout = QVBoxLayout(self.frame)
        
        # 1. 標題列
        title_bar = QHBoxLayout()
        self.lbl_title = QLabel("☁️雲朵翻譯姬")
        self.lbl_title.setStyleSheet("font-weight: bold; border: none; background: transparent;")
        title_bar.addWidget(self.lbl_title)
        
        title_bar.addStretch() # 把按鈕推到右邊

        self.btn_close_x = QPushButton("✕")
        self.btn_close_x.setFixedSize(24,24)
        self.btn_close_x.setCursor(Qt.PointingHandCursor)
        self.btn_close_x.setStyleSheet("background:transparent; color:#888; border:none; font-weight:900;")
        self.btn_close_x.clicked.connect(self.close_app)
        title_bar.addWidget(self.btn_close_x)
        
        inner_layout.addLayout(title_bar)

        # 2. 狀態列與燈泡按鈕 (修改這裡)
        status_row = QHBoxLayout()
        
        # 狀態文字框
        self.lbl_status = QLabel("等待指令 (｀・ω・´)")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        # 樣式會由 update_frame_style 統一管理，這裡先設定基本的
        self.lbl_status.setFixedHeight(30) 
        
        # 燈泡按鈕 (放在狀態列右邊，即 X 下方)
        self.btn_theme = QPushButton("💡")
        self.btn_theme.setFixedSize(30, 30)
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        
        status_row.addWidget(self.lbl_status) # 左邊佔大部分
        status_row.addWidget(self.btn_theme)  # 右邊一小顆
        
        inner_layout.addLayout(status_row)

        # 3. 時間按鈕
        btn_layout = QHBoxLayout()
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        self.btn_10 = self.create_time_btn("10秒", 10000)
        self.btn_30 = self.create_time_btn("30秒", 30000)
        self.btn_60 = self.create_time_btn("60秒", 60000)
        
        btn_layout.addWidget(self.btn_10)
        btn_layout.addWidget(self.btn_30)
        btn_layout.addWidget(self.btn_60)
        inner_layout.addLayout(btn_layout)

        # 4. 停止按鈕
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_scan)
        inner_layout.addWidget(self.btn_stop)

        layout.addWidget(self.frame)
        self.setLayout(layout)

        # 應用一次完整的樣式
        self.update_frame_style()

        self.ocr_thread = QThread()
        self.worker = OCRWorker(lang='japan')
        self.worker.moveToThread(self.ocr_thread)
        
        self.request_scan.connect(self.worker.run_scan_once)
        self.worker.finished.connect(self.overlay.update_bubbles)
        self.worker.status_msg.connect(self.update_status)
        self.worker.hide_ui.connect(self.hide_ui_for_scan)
        self.worker.show_ui.connect(self.show_ui_after_scan)
        
        self.ocr_thread.start()

        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.trigger_scan_sequence)
        self.old_pos = None

    def create_time_btn(self, text, interval):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self.start_timer(interval, btn))
        self.btn_group.addButton(btn)
        return btn

    def toggle_theme(self):
        """切換深色/淺色模式"""
        self.is_dark_mode = not self.is_dark_mode
        self.update_frame_style() # 更新 Controller UI
        self.overlay.set_theme_mode(self.is_dark_mode) # 更新 Overlay UI

    def update_frame_style(self):
        """根據 is_dark_mode 更新所有 CSS"""
        if self.is_dark_mode:
            # === 深色模式 ===
            bg_color = "rgba(45, 45, 45, 240)"
            border_color = "#555555"
            text_color = "#E0E0E0"
            status_bg = "#3A3A3A"
            status_border = "#555"
            btn_bg = "#424242"
            btn_hover = "#505050"
            btn_checked = "#00ACC1" # 深青色
            stop_bg = "#D32F2F"     # 深紅色
            stop_hover = "#E57373"
            bulb_bg = "transparent"
            bulb_color = "#FFEB3B"  # 燈泡亮黃色
        else:
            # === 淺色模式 ===
            bg_color = "rgba(240, 248, 255, 230)"
            border_color = "#87CEEB"
            text_color = "#444444"
            status_bg = "white"
            status_border = "#87CEEB"
            btn_bg = "#E0F7FA"
            btn_hover = "#B2EBF2"
            btn_checked = "#4FC3F7"
            stop_bg = "#FFB6C1"
            stop_hover = "#FF69B4"
            bulb_bg = "transparent"
            bulb_color = "#555"     # 燈泡灰色

        # 1. 主框架
        self.frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 15px;
                border: 2px solid {border_color};
            }}
        """)
        
        # 2. 標題與文字
        self.lbl_title.setStyleSheet(f"color: {text_color}; font-weight: bold; background: transparent; border: none;")
        
        # 3. 狀態列 (有邊框的那個)
        self.lbl_status.setStyleSheet(f"""
            color: {text_color}; 
            background-color: {status_bg}; 
            border: 1px solid {status_border}; 
            border-radius: 4px;
        """)

        # 4. 燈泡按鈕
        self.btn_theme.setStyleSheet(f"""
            QPushButton {{
                background-color: {bulb_bg}; 
                color: {bulb_color}; 
                border: none; 
                font-size: 18px;
            }}
            QPushButton:hover {{
                background-color: rgba(128,128,128,0.2);
                border-radius: 15px;
            }}
        """)

        # 5. 時間按鈕 (一般樣式)
        common_btn_style = f"""
            QPushButton {{
                background-color: {btn_bg}; 
                color: {text_color}; 
                border-radius: 8px; 
                padding: 8px; 
                font-weight: bold; 
                border: none;
            }}
            QPushButton:hover:!checked {{
                background-color: {btn_hover};
            }}
            QPushButton:checked {{
                background-color: {btn_checked}; 
                color: white;
            }}
        """
        self.btn_10.setStyleSheet(common_btn_style)
        self.btn_30.setStyleSheet(common_btn_style)
        self.btn_60.setStyleSheet(common_btn_style)

        # 6. 停止按鈕
        self.btn_stop.setStyleSheet(f"""
            QPushButton {{
                background-color: {stop_bg}; 
                color: white; 
                border-radius: 10px; 
                padding: 5px; 
                border: none;
            }}
            QPushButton:hover {{ background-color: {stop_hover}; }}
        """)

    def start_timer(self, interval, btn):
        if self.auto_timer.isActive() and self.auto_timer.interval() == interval:
            return

        self.lbl_status.setText(f"🔥 自動掃描: {interval//1000}s")
        self.auto_timer.stop()
        self.auto_timer.setInterval(interval)
        self.auto_timer.start()
        
        self.trigger_scan_sequence()

    def stop_scan(self):
        self.auto_timer.stop()
        self.btn_group.setExclusive(False)
        for btn in self.btn_group.buttons():
            btn.setChecked(False)
        self.btn_group.setExclusive(True)
        self.lbl_status.setText("⏸ 已暫停")
        self.overlay.clear_all() 

    def update_status(self, msg):
        self.lbl_status.setText(msg)

    def hide_ui_for_scan(self):
        self.overlay.setVisible(False)
        self.setVisible(False)

    def show_ui_after_scan(self):
        self.overlay.setVisible(True)
        self.setVisible(True)

    def trigger_scan_sequence(self):
        self.overlay.setVisible(False)
        QTimer.singleShot(50, self._emit_scan_signal)

    def _emit_scan_signal(self):
        self.request_scan.emit()

    def close_app(self):
        self.auto_timer.stop()
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
    def mouseReleaseEvent(self, event):
        self.old_pos = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = OverlayWindow()
    overlay.show()
    ctrl = Controller(overlay)
    ctrl.show()
    sys.exit(app.exec())