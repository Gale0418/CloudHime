import os
path = r"d:\MyGame\CloudHime\CloudHime.py"
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

# 1
c = c.replace(
"""        self.frame_opacity = 40
        self.hide()""",
"""        self.frame_opacity = 40
        self.region_pass_through = False
        self.hide()

    def set_region_pass_through(self, pass_through):
        self.region_pass_through = bool(pass_through)
        flags = self.windowFlags()
        if self.region_pass_through:
            flags |= Qt.WindowTransparentForInput
        else:
            flags &= ~Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        if self.isVisible():
            self.show()"""
)

# 2
c = c.replace(
"""        self.lbl_ocr.setStyleSheet("background: transparent; border: none;")
        ocr.addWidget(self.lbl_ocr)
        ocr.addWidget(self.lbl_ocr_hint)""",
"""        self.lbl_ocr.setStyleSheet("background: transparent; border: none;")
        ocr.addWidget(self.lbl_ocr)
        ocr.addWidget(self.lbl_ocr_hint)
        
        self.chk_region_pass_through = QCheckBox("允許滑鼠穿透框選區 (點擊背景遊戲)")
        self.chk_region_pass_through.setChecked(getattr(self.controller, "region_pass_through", False))
        self.chk_region_pass_through.toggled.connect(self.controller.on_region_pass_through_changed)
        ocr.addWidget(self.chk_region_pass_through)"""
)

# 3
c = c.replace(
"""        self.region_relief_gap_px = 8
        self.region_frame_opacity = 40
        self.gemma_prompt = \"\"""",
"""        self.region_relief_gap_px = 8
        self.region_frame_opacity = 40
        self.region_pass_through = False
        self.gemma_prompt = \"\""""
)

# 4
c = c.replace(
"""            "random_scan_center_seconds": int(self.random_scan_center_seconds),
            "random_scan_jitter_percent": int(self.random_scan_jitter_percent),
            "region_render_mode": self.region_render_mode,""",
"""            "random_scan_center_seconds": int(self.random_scan_center_seconds),
            "random_scan_jitter_percent": int(self.random_scan_jitter_percent),
            "region_pass_through": getattr(self, "region_pass_through", False),
            "region_render_mode": self.region_render_mode,"""
)

# 5
c = c.replace(
"""            self.set_theme_mode(saved_theme_mode)
            self.region_frame.set_theme_mode(saved_theme_mode)
            self.region_frame.set_frame_opacity(self.region_frame_opacity)

            saved_region = settings.get("selected_region")""",
"""            self.set_theme_mode(saved_theme_mode)
            self.region_frame.set_theme_mode(saved_theme_mode)
            self.region_frame.set_frame_opacity(self.region_frame_opacity)
            self.region_pass_through = bool(settings.get("region_pass_through", False))
            self.region_frame.set_region_pass_through(self.region_pass_through)
            if self.settings_window is not None:
                self.settings_window.chk_region_pass_through.blockSignals(True)
                self.settings_window.chk_region_pass_through.setChecked(self.region_pass_through)
                self.settings_window.chk_region_pass_through.blockSignals(False)

            saved_region = settings.get("selected_region")"""
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)
print("Done!")
