path = r"d:\MyGame\CloudHime\CloudHime.py"
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

# Fix 1: remove duplicate except block
old1 = """            except Exception:
                _google_ocr_future = None
        except Exception as exc:
            self.status_msg.emit(f"\\u274c 擷取螢幕失敗：{type(exc).__name__}")
            self.finished.emit([])
            self.show_ui.emit()
            return"""
new1 = """            except Exception:
                _google_ocr_future = None"""
c = c.replace(old1, new1)

# Fix 2: replace old Google OCR block with prefetch-aware version
old2 = """            self.status_msg.emit("🧠 AI 大圖翻譯..." if self.has_multimodal_ai() else "🌐 Google...")
            if self.google_ocr_enabled and self.google_api_key:
                if ai_image_parts is None:
                    _log("④-pre 開始 build_ai_image_parts (Google OCR)")
                    ai_image_parts = self.build_ai_image_parts(img)
                    _log("④ build_ai_image_parts 完成 (Google OCR)")
                _log("⑤ 開始 refine_merged_items_with_google_ocr")
                merged_items = self.refine_merged_items_with_google_ocr(merged_items, ai_image_parts)
                _log("⑥ Google OCR 精煉完成")"""
new2 = """            self.status_msg.emit("🧠 AI 大圖翻譯..." if self.has_multimodal_ai() else "🌐 Google...")
            if self.google_ocr_enabled and self.google_api_key:
                if _google_ocr_future is not None:
                    _log("⑤ 等待 Google OCR 預取結果...")
                    try:
                        _google_result = _google_ocr_future.result()
                        _log("⑥ Google OCR 精煉完成 (已預取)")
                        if _google_result is not None:
                            _google_lines = [normalize_ocr_text(line) for line in str(_google_result.text or "").splitlines() if normalize_ocr_text(line)]
                            merged_items = self._merge_google_lines_into_items(merged_items, _google_lines)
                    except Exception:
                        pass
                else:
                    if ai_image_parts is None:
                        _log("④-pre 開始 build_ai_image_parts (Google OCR)")
                        ai_image_parts = self.build_ai_image_parts(img)
                        _log("④ build_ai_image_parts 完成 (Google OCR)")
                    _log("⑤ 開始 refine_merged_items_with_google_ocr")
                    merged_items = self.refine_merged_items_with_google_ocr(merged_items, ai_image_parts)
                    _log("⑥ Google OCR 精煉完成")"""
c = c.replace(old2, new2)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)
print(f"Fix1: {'OK' if old1 not in c else 'FAIL'}")
print(f"Fix2: {'OK' if old2 not in c else 'FAIL'}")
