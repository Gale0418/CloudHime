from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping


@dataclass(frozen=True)
class ThemeDefinition:
    key: str
    label: str
    is_dark: bool
    colors: Mapping[str, str]
    # Windows own-world display face for headings/brand.  Qt will fall through
    # to the CJK family for glyphs that Bahnschrift does not contain.
    display_font: str = "Bahnschrift SemiBold"
    display_cjk_font: str = "Microsoft JhengHei UI"

    def __getitem__(self, item: str) -> str:
        return self.colors[item]

    def get(self, item: str, default: str = "") -> str:
        return str(self.colors.get(item, default))

    def __getattr__(self, item: str) -> str:
        aliases = {
            "bg": "shell_bg",
            "card_bg": "panel_bg",
            "window_bg": "shell_bg",
            "window_border": "shell_border",
            "highlight": "accent",
        }
        key = aliases.get(item, item)
        if key in self.colors:
            return str(self.colors[key])
        raise AttributeError(item)

    def base_qss(self) -> str:
        return f"QWidget {{ color: {self.text}; }} QFrame {{ border: none; }}"

    def window_qss(self, radius: int = 16, border_width: int = 1) -> str:
        return (
            f"QFrame {{ background-color: {self.shell_bg}; border: {border_width}px solid {self.shell_border}; "
            f"border-radius: {int(radius)}px; }}"
        )

    def header_qss(self, radius: int = 22) -> str:
        return (
            f"QFrame {{ background-color: {self.header_bg}; border: 1px solid {self.header_border}; "
            f"border-radius: {int(radius)}px; }}"
        )

    def panel_qss(self, variant: str = "subtle", radius: int = 12) -> str:
        variant = str(variant or "subtle").strip().lower()
        if variant == "primary":
            return (
                f"QFrame {{ background-color: {self.panel_bg}; border: 1px solid {self.accent}; "
                f"border-radius: {int(radius)}px; }}"
            )
        if variant == "transparent":
            return "QFrame { background: transparent; border: none; }"
        return (
            f"QFrame {{ background-color: {self.panel_bg}; border: 1px solid {self.panel_border}; "
            f"border-radius: {int(radius)}px; }}"
        )

    def pill_qss(self, kind: str = "accent", size: int = 11) -> str:
        kind = str(kind or "accent").strip().lower()
        if kind == "danger":
            bg = self.danger_bg
            fg = self.danger_fg
            border = self.border
        elif kind == "ghost":
            bg = "transparent"
            fg = self.subtext
            border = "transparent"
        else:
            bg = self.accent_soft
            fg = self.accent
            border = self.border
        return (
            f"color: {fg}; font-size: {int(size)}px; font-weight: 700; background-color: {bg}; "
            f"border: 1px solid {border}; border-radius: 999px; padding: 4px 10px;"
        )

    def button_qss(self, variant: str = "default", radius: int = 10) -> str:
        variant = str(variant or "default").strip().lower()
        if variant == "danger":
            return (
                f"QPushButton {{ background-color: {self.danger_bg}; color: {self.danger_fg}; "
                f"border-radius: {int(radius)}px; padding: 5px; border: none; }}"
                f" QPushButton:hover {{ background-color: {self.danger_hover}; }}"
            )
        if variant == "ghost":
            return (
                f"QPushButton {{ background-color: transparent; color: {self.subtext}; border: none; "
                f"font-size: 14px; font-weight: bold; }}"
                f" QPushButton:hover {{ background-color: {self.accent_soft}; color: {self.text}; "
                f"border-radius: {int(radius)}px; }}"
            )
        return (
            f"QPushButton {{ background-color: {self.control_bg}; color: {self.control_fg}; "
            f"border-radius: {int(radius)}px; padding: 8px; font-weight: bold; border: none; }}"
            f" QPushButton:hover {{ background-color: {self.control_hover}; }}"
            f" QPushButton:checked {{ background-color: {self.control_checked}; color: white; }}"
            f" QPushButton:disabled {{ background-color: {self.control_disabled_bg}; color: {self.control_disabled_fg}; }}"
        )

    def raised_button_qss(
        self,
        variant: str = "secondary",
        radius: int = 8,
        text_align: str = "center",
    ) -> str:
        """Theme-aware raised control with restrained, native Qt relief."""
        variant = str(variant or "secondary").strip().lower()
        palette = {
            "primary": (
                self.accent,
                self.get("button_primary_top", self.accent),
                self.get("button_primary_edge", self.control_checked),
                self.checked_fg,
                self.control_checked,
            ),
            "segmented": (
                self.control_bg,
                self.get("button_segmented_top", self.accent),
                self.get("button_segmented_edge", self.control_checked),
                self.control_fg,
                self.control_hover,
            ),
            "secondary": (
                self.control_bg,
                self.get("button_secondary_top", self.border),
                self.get("button_secondary_edge", self.border),
                self.control_fg,
                self.control_hover,
            ),
        }
        background, highlight, lower_edge, foreground, hover_background = palette.get(
            variant, palette["secondary"]
        )
        return (
            f"QPushButton {{ background-color: {background}; color: {foreground}; "
            f"border: 1px solid {lower_edge}; border-top-color: {highlight}; "
            f"border-bottom: 2px solid {lower_edge}; border-radius: {int(radius)}px; "
            f"padding: 6px 12px 4px; min-height: 32px; font-weight: 700; "
            f"text-align: {text_align}; }}"
            f" QPushButton:hover {{ background-color: {hover_background}; "
            f"border-top-color: {highlight}; border-bottom-color: {self.accent}; }}"
            f" QPushButton:pressed {{ background-color: {hover_background}; "
            f"border-top: 2px solid {lower_edge}; border-bottom: 1px solid {highlight}; "
            "padding-top: 7px; padding-bottom: 3px; }}"
            f" QPushButton:focus {{ background-color: {background}; border: 2px solid {self.focus}; "
            "padding: 5px 11px 3px; }}"
            f" QPushButton:checked {{ background-color: {self.control_checked}; color: {self.checked_fg}; "
            f"border-top-color: {highlight}; border-bottom-color: {lower_edge}; }}"
            f" QPushButton:disabled {{ background-color: {self.control_disabled_bg}; "
            f"color: {self.control_disabled_fg}; border: 1px solid {self.control_disabled_bg}; "
            f"border-bottom: 1px solid {self.control_disabled_bg}; padding: 6px 12px 4px; }}"
        )

    def combo_qss(self, radius: int = 8) -> str:
        return (
            f"QComboBox {{ background-color: {self.input_bg}; color: {self.text}; "
            f"border: 1px solid {self.border}; border-radius: {int(radius)}px; padding: 6px 10px; }}"
            f" QComboBox:hover {{ border-color: {self.accent}; }}"
            f" QComboBox:focus {{ border: 2px solid {self.accent}; }}"
            " QComboBox::drop-down { border: none; width: 22px; }"
            " QComboBox::down-arrow { image: none; }"
            f" QComboBox QAbstractItemView {{ background-color: {self.panel_bg}; color: {self.text}; "
            f"selection-background-color: {self.accent_soft}; selection-color: {self.text}; "
            f"border: 1px solid {self.border}; outline: 0px; }}"
            f" QComboBox QAbstractItemView::item {{ min-height: 24px; padding: 4px 8px; }}"
            f" QComboBox QAbstractItemView::item:selected {{ background-color: {self.accent_soft}; color: {self.text}; }}"
        )

    def bubble_qss(self, relief: bool = False) -> str:
        if relief:
            return f"QLabel {{ background: transparent; color: {self.bubble_relief_fg}; font-weight: 400; border: none; padding: 0px; }}"
        return (
            f"QLabel {{ background-color: {self.bubble_bg}; color: {self.bubble_fg}; font-weight: bold; "
            f"border-radius: 12px; border: 1px solid {self.bubble_border}; padding: 2px; }}"
        )


def _theme_colors(**kwargs) -> Dict[str, str]:
    # Compatibility tokens used by the provider status panel.  Their defaults
    # deliberately follow the legacy palette instead of introducing a second
    # visual language for settings.
    kwargs.setdefault("shell_text", kwargs.get("text", ""))
    kwargs.setdefault("checked_fg", "#FFFFFF")
    kwargs.setdefault("focus", kwargs.get("accent", ""))
    kwargs.setdefault("operational", kwargs.get("charge_normal_fill", kwargs.get("accent", "")))
    kwargs.setdefault("operational_soft", kwargs.get("charge_normal_bg", kwargs.get("accent_soft", "")))
    kwargs.setdefault("readiness", kwargs["operational"])
    kwargs.setdefault("readiness_soft", kwargs["operational_soft"])
    kwargs.setdefault("loading", kwargs.get("charge_warning_fill", kwargs.get("accent", "")))
    kwargs.setdefault("loading_soft", kwargs.get("charge_warning_bg", kwargs.get("accent_soft", "")))
    kwargs.setdefault("quota", kwargs.get("charge_warning_fill", kwargs.get("accent", "")))
    kwargs.setdefault("quota_soft", kwargs.get("charge_warning_bg", kwargs.get("accent_soft", "")))
    kwargs.setdefault("error", kwargs.get("charge_danger_fill", kwargs.get("accent", "")))
    kwargs.setdefault("error_soft", kwargs.get("charge_danger_bg", kwargs.get("accent_soft", "")))
    for name in ("button_primary_top", "button_primary_edge", "button_secondary_top", "button_secondary_edge", "button_segmented_top", "button_segmented_edge"):
        kwargs.setdefault(name, kwargs.get("border", kwargs.get("accent", "")))
    kwargs.setdefault("provider_surface", kwargs.get("input_bg", ""))
    kwargs.setdefault("provider_border", kwargs.get("border", ""))
    kwargs.setdefault("provider_top_highlight", kwargs.get("border", ""))
    kwargs.setdefault("provider_bottom_edge", kwargs.get("border", ""))
    kwargs.setdefault("nested_model_surface", kwargs.get("input_bg", ""))
    kwargs.setdefault("nested_model_border", kwargs.get("border", ""))
    kwargs.setdefault("provider_metadata", kwargs.get("subtext", ""))
    return dict(kwargs)


THEME_DEFINITIONS: Dict[str, ThemeDefinition] = {
    "light": ThemeDefinition(
        key="light",
        label="淺色模式",
        is_dark=False,
        colors=_theme_colors(
            shell_bg="rgba(242, 242, 247, 235)",
            shell_border="rgba(0, 0, 0, 10)",
            panel_bg="rgba(255, 255, 255, 240)",
            panel_border="rgba(0, 0, 0, 10)",
            text="#1C1C1E",
            subtext="#8E8E93",
            border="rgba(0, 0, 0, 15)",
            accent="#007AFF",
            accent_soft="rgba(0, 122, 255, 30)",
            input_bg="rgba(255, 255, 255, 200)",
            control_bg="rgba(118, 118, 128, 20)",
            control_fg="#1C1C1E",
            control_hover="rgba(118, 118, 128, 40)",
            control_checked="#007AFF",
            control_disabled_fg="#8E8E93",
            control_disabled_bg="rgba(118, 118, 128, 10)",
            checked_fg="#FFFFFF",
            focus="#007AFF",
            operational="#4FC3F7",
            operational_soft="#E8F8FB",
            quota="#F4C542",
            quota_soft="#FFF4D6",
            error="#E53935",
            error_soft="#FDE8E8",
            readiness="#007AFF",
            readiness_soft="rgba(0, 122, 255, 30)",
            loading="#F4C542",
            loading_soft="#FFF4D6",
            danger_bg="#FF3B30",
            danger_hover="#FF453A",
            danger_fg="#FFFFFF",
            danger_checked="#D70015",
            header_bg="rgba(255, 255, 255, 120)",
            header_border="rgba(0, 0, 0, 10)",
            settings_shell_bg="rgba(242, 242, 247, 235)",
            settings_top_bg="#F2F2F7",
            settings_nav_bg="rgba(255, 255, 255, 200)",
            settings_card_bg="rgba(255, 255, 255, 240)",
            settings_card_highlight="rgba(255, 255, 255, 255)",
            settings_card_edge="rgba(0, 0, 0, 15)",
            provider_surface="rgba(255, 255, 255, 220)",
            provider_border="rgba(0, 0, 0, 26)",
            provider_top_highlight="rgba(255, 255, 255, 245)",
            provider_bottom_edge="rgba(0, 0, 0, 34)",
            nested_model_surface="rgba(248, 248, 250, 220)",
            nested_model_border="rgba(0, 0, 0, 18)",
            provider_metadata="#6B6B72",
            settings_fallback_bg="rgba(242, 242, 247, 235)",
            status_bg="rgba(255, 255, 255, 180)",
            status_border="rgba(0, 0, 0, 10)",
            status_text="#1C1C1E",
            bubble_bg="rgba(255, 255, 255, 245)",
            bubble_fg="#39566B",
            bubble_border="#DDDDDD",
            bubble_relief_fg="#39566B",
            bubble_relief_outline="rgba(255, 255, 255, 220)",
            selection_fill="rgba(79, 195, 247, 0.18)",
            selection_border="#4FC3F7",
            selection_handle="#4FC3F7",
            charge_normal_bg="#E8F8FB",
            charge_normal_border="#7FC8E8",
            charge_normal_fill="#4FC3F7",
            charge_normal_text="#3A5C72",
            charge_warning_bg="#FFF4D6",
            charge_warning_border="#E6B800",
            charge_warning_fill="#F4C542",
            charge_warning_text="#7A5A00",
            charge_danger_bg="#FDE8E8",
            charge_danger_border="#E57373",
            charge_danger_fill="#E53935",
            charge_danger_text="#8B1E1E",
            charge_off_bg="#F2F5F7",
            charge_off_border="#D7E0E8",
            charge_off_fill="#B7C7D8",
            charge_off_text="#6B7C8A",
        ),
    ),
    "dark": ThemeDefinition(
        key="dark",
        label="深色模式",
        is_dark=True,
        colors=_theme_colors(
            shell_bg="rgba(28, 28, 30, 242)",
            shell_text="#FFFFFF",
            shell_border="rgba(255, 255, 255, 15)",
            panel_bg="rgba(44, 44, 46, 230)",
            panel_border="rgba(255, 255, 255, 10)",
            text="rgba(255, 255, 255, 220)",
            subtext="rgba(235, 235, 245, 150)",
            border="rgba(255, 255, 255, 20)",
            accent="#0A84FF",
            accent_soft="rgba(10, 132, 255, 46)",
            input_bg="rgba(118, 118, 128, 60)",
            control_bg="rgba(118, 118, 128, 60)",
            control_fg="rgba(255, 255, 255, 220)",
            control_hover="rgba(118, 118, 128, 80)",
            control_checked="#0A84FF",
            control_disabled_fg="rgba(235, 235, 245, 100)",
            control_disabled_bg="rgba(118, 118, 128, 30)",
            checked_fg="#FFFFFF",
            button_primary_top="#7DE1EC",
            button_primary_edge="#0E6677",
            button_secondary_top="#2B5A70",
            button_secondary_edge="#0E2B3B",
            button_segmented_top="#7DE1EC",
            button_segmented_edge="#0E6677",
            focus="#7DE1EC",
            operational="#4FC3F7",
            operational_soft="#E8F8FB",
            quota="#F4C542",
            quota_soft="#FFF4D6",
            error="#E53935",
            error_soft="#FDE8E8",
            readiness="#43C5D7",
            readiness_soft="rgba(67, 197, 215, 34)",
            loading="#F4C542",
            loading_soft="#FFF4D6",
            danger_bg="#FF453A",
            danger_hover="#FF5E55",
            danger_fg="#FFFFFF",
            danger_checked="#D70015",
            header_bg="rgba(44, 44, 46, 120)",
            header_border="rgba(255, 255, 255, 15)",
            settings_shell_bg="rgba(28, 28, 30, 242)",
            settings_top_bg="#1C1C1E",
            settings_nav_bg="rgba(118, 118, 128, 60)",
            settings_card_bg="rgba(44, 44, 46, 230)",
            settings_card_highlight="rgba(255, 255, 255, 255)",
            settings_card_edge="rgba(255, 255, 255, 20)",
            provider_surface="rgba(44, 44, 46, 210)",
            provider_border="rgba(255, 255, 255, 34)",
            provider_top_highlight="rgba(255, 255, 255, 58)",
            provider_bottom_edge="rgba(0, 0, 0, 90)",
            nested_model_surface="rgba(58, 58, 60, 160)",
            nested_model_border="rgba(255, 255, 255, 24)",
            provider_metadata="rgba(235, 235, 245, 185)",
            settings_fallback_bg="rgba(28, 28, 30, 242)",
            status_bg="rgba(44, 44, 46, 180)",
            status_border="rgba(255, 255, 255, 15)",
            status_text="rgba(255, 255, 255, 220)",
            bubble_bg="rgba(35, 35, 35, 245)",
            bubble_fg="#EAF7FF",
            bubble_border="#555555",
            bubble_relief_fg="#EAF7FF",
            bubble_relief_outline="rgba(0, 0, 0, 220)",
            selection_fill="rgba(85, 199, 243, 0.22)",
            selection_border="#55C7F3",
            selection_handle="#55C7F3",
            charge_normal_bg="#E8F8FB",
            charge_normal_border="#7FC8E8",
            charge_normal_fill="#4FC3F7",
            charge_normal_text="#3A5C72",
            charge_warning_bg="#FFF4D6",
            charge_warning_border="#E6B800",
            charge_warning_fill="#F4C542",
            charge_warning_text="#7A5A00",
            charge_danger_bg="#FDE8E8",
            charge_danger_border="#E57373",
            charge_danger_fill="#E53935",
            charge_danger_text="#8B1E1E",
            charge_off_bg="#F2F5F7",
            charge_off_border="#D7E0E8",
            charge_off_fill="#B7C7D8",
            charge_off_text="#6B7C8A",
        ),
    ),
    "high_contrast": ThemeDefinition(
        key="high_contrast",
        label="高對比模式",
        is_dark=True,
        colors=_theme_colors(
            shell_bg="rgba(18, 18, 18, 248)",
            shell_text="#FFFFFF",
            shell_border="#FFFFFF",
            panel_bg="rgba(32, 32, 32, 240)",
            panel_border="#FFFFFF",
            text="#FFFFFF",
            subtext="#E5E5E5",
            border="#FFFFFF",
            accent="#FFD400",
            accent_soft="rgba(255, 212, 0, 56)",
            input_bg="#000000",
            control_bg="#000000",
            control_fg="#FFFFFF",
            control_hover="#2B2B2B",
            control_checked="#FFD400",
            control_disabled_fg="#B0B0B0",
            control_disabled_bg="#3A3A3A",
            checked_fg="#FFFFFF",
            button_primary_top="#FFFFFF",
            button_primary_edge="#003B46",
            button_secondary_top="#FFFFFF",
            button_secondary_edge="#000000",
            button_segmented_top="#FFFFFF",
            button_segmented_edge="#003B46",
            focus="#FFFFFF",
            operational="#FFD400",
            operational_soft="rgba(255, 212, 0, 56)",
            quota="#FFD400",
            quota_soft="#241B00",
            error="#FF4D4D",
            error_soft="#2B0008",
            readiness="#FFD400",
            readiness_soft="rgba(255, 212, 0, 45)",
            loading="#FFD400",
            loading_soft="#241B00",
            danger_bg="#C74F4A",
            danger_hover="#D9655F",
            danger_fg="#FFFFFF",
            danger_checked="#9E3434",
            header_bg="rgba(255, 212, 0, 0.16)",
            header_border="#FFFFFF",
            # High contrast deliberately stays fully opaque and has no image.
            settings_shell_bg="rgba(18, 18, 18, 248)",
            settings_top_bg="#121212",
            settings_nav_bg="#000000",
            settings_card_bg="rgba(32, 32, 32, 240)",
            settings_card_highlight="#FFFFFF",
            settings_card_edge="#000000",
            provider_surface="#202020",
            provider_border="#FFFFFF",
            provider_top_highlight="#FFFFFF",
            provider_bottom_edge="#000000",
            nested_model_surface="#000000",
            nested_model_border="#FFFFFF",
            provider_metadata="#E5E5E5",
            settings_fallback_bg="rgba(18, 18, 18, 248)",
            status_bg="#000000",
            status_border="#FFFFFF",
            status_text="#FFFFFF",
            bubble_bg="rgba(0, 0, 0, 248)",
            bubble_fg="#FFFFFF",
            bubble_border="#FFFFFF",
            bubble_relief_fg="#FFFFFF",
            bubble_relief_outline="rgba(0, 0, 0, 245)",
            selection_fill="rgba(255, 212, 0, 0.18)",
            selection_border="#FFD400",
            selection_handle="#FFFFFF",
            charge_normal_bg="#000000",
            charge_normal_border="#FFFFFF",
            charge_normal_fill="#FFD400",
            charge_normal_text="#FFFFFF",
            charge_warning_bg="#241B00",
            charge_warning_border="#FFD400",
            charge_warning_fill="#FFD400",
            charge_warning_text="#FFFFFF",
            charge_danger_bg="#2B0008",
            charge_danger_border="#FF4D4D",
            charge_danger_fill="#FF4D4D",
            charge_danger_text="#FFFFFF",
            charge_off_bg="#111111",
            charge_off_border="#FFFFFF",
            charge_off_fill="#777777",
            charge_off_text="#FFFFFF",
        ),
    ),
}

THEME_ORDER = ("light", "dark", "high_contrast")
THEME_ALIASES = {
    "system": "light",
    "default": "light",
    "light_mode": "light",
    "dark_mode": "dark",
    "hc": "high_contrast",
    "contrast": "high_contrast",
}


class ThemeRegistry:
    @classmethod
    def normalize_mode(cls, theme_mode) -> str:
        if isinstance(theme_mode, bool):
            return "dark" if theme_mode else "light"
        mode = str(theme_mode or "light").strip().lower()
        mode = THEME_ALIASES.get(mode, mode)
        if mode not in THEME_DEFINITIONS:
            return "light"
        return mode

    @classmethod
    def normalize_key(cls, theme_mode) -> str:
        return cls.normalize_mode(theme_mode)

    @classmethod
    def get(cls, theme_mode) -> ThemeDefinition:
        return THEME_DEFINITIONS[cls.normalize_mode(theme_mode)]

    @classmethod
    def available_modes(cls):
        return [mode for mode in THEME_ORDER if mode in THEME_DEFINITIONS]

    @classmethod
    def available_themes(cls):
        return [THEME_DEFINITIONS[mode] for mode in cls.available_modes()]

    @classmethod
    def available(cls):
        return cls.available_themes()

    @classmethod
    def label_for(cls, theme_mode) -> str:
        return cls.get(theme_mode).label


def resolve_theme(theme_mode) -> ThemeDefinition:
    return ThemeRegistry.get(theme_mode)


def build_bubble_style(theme: ThemeDefinition, relief: bool = False) -> dict:
    if relief:
        return {
            "stylesheet": (
                f"QLabel {{ background: transparent; color: {theme['bubble_relief_fg']}; "
                "font-weight: 400; border: none; padding: 0px; }}"
            ),
            "fill": theme["bubble_relief_fg"],
            "outline": theme["bubble_relief_outline"],
        }
    return {
        "stylesheet": (
            f"QLabel {{ background-color: {theme['bubble_bg']}; color: {theme['bubble_fg']}; "
            f"font-weight: bold; border-radius: 12px; border: 1px solid {theme['bubble_border']}; "
            "padding: 2px; }}"
        ),
        "fill": theme["bubble_fg"],
        "outline": theme["bubble_relief_outline"] if theme.is_dark else "rgba(255, 255, 255, 220)",
    }


def build_selection_colors(theme: ThemeDefinition) -> dict:
    return {
        "border": theme["selection_border"],
        "fill": theme["selection_fill"],
    }


def build_charge_bar_colors(theme: ThemeDefinition, state: str = "normal") -> dict:
    state = str(state or "normal").strip().lower()
    prefix = "charge_normal"
    if state in {"warning", "warn"}:
        prefix = "charge_warning"
    elif state in {"danger", "error"}:
        prefix = "charge_danger"
    elif state in {"off", "idle", "disabled"}:
        prefix = "charge_off"
    return {
        "base_bg": theme[f"{prefix}_bg"],
        "border_color": theme[f"{prefix}_border"],
        "fill_color": theme[f"{prefix}_fill"],
        "text_color": theme[f"{prefix}_text"],
    }


def build_window_styles(
    theme: ThemeDefinition,
    *,
    frame_radius: int,
    header_radius: int,
    card_radius: int,
    title_size: int,
    subtitle_size: int,
    label_size: int,
    status_radius: int,
    control_radius: int,
    title_line_height: int | None = None,
    scroll_area: bool = False,
) -> dict:
    c = theme.colors
    base_qss = [
        f"QWidget {{ color: {c['text']}; }}",
        "QFrame { border: none; }",
    ]
    if scroll_area:
        base_qss.append("QScrollArea { border: none; background: transparent; }")
    base_qss.extend(
        [
            (
                "QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit { "
                f"background-color: {c['input_bg']}; color: {c['text']}; "
                f"border: 1px solid {c['border']}; border-radius: 10px; padding: 5px 10px; min-height: 32px; "
                f"selection-background-color: {c['accent']}; }}"
            ),
            f"QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{ border: 2px solid {c['focus']}; }}",
            (
                f"QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QPlainTextEdit:disabled {{ "
                f"background-color: {c['control_disabled_bg']}; color: {c['control_disabled_fg']}; border-color: {c['control_disabled_bg']}; }}"
            ),
            "QComboBox::drop-down { border: none; width: 22px; }",
            "QComboBox::down-arrow { image: none; }",
            "QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }",
            f"QCheckBox {{ color: {c['text']}; spacing: 8px; }}",
            (
                "QCheckBox::indicator { width: 18px; height: 18px; border-radius: 9px; "
                f"border: 1px solid {c['border']}; background: {c['input_bg']}; }}"
            ),
            (
                "QCheckBox::indicator:checked { "
                f"background: {c['accent']}; border: 1px solid {c['accent']}; }}"
            ),
            (
                "QSlider::groove:horizontal { "
                f"height: 8px; border-radius: 4px; background: {c['accent_soft']}; }}"
            ),
            (
                "QSlider::handle:horizontal { "
                f"width: 18px; margin: -5px 0; border-radius: 9px; background: {c['accent']}; "
                "border: 2px solid white; }"
            ),
            (
                "QPushButton { "
                f"padding: 5px 12px; min-height: 32px; border-radius: {control_radius}px; border: 1px solid {c['border']}; "
                f"background: {c['panel_bg']}; color: {c['text']}; }}"
            ),
            f"QPushButton:hover {{ border-color: {c['accent']}; }}",
            f"QPushButton:focus {{ border: 2px solid {c['focus']}; }}",
            f"QPushButton:checked {{ background: {c['accent_soft']}; border-color: {c['accent']}; }}",
            f"QPushButton:disabled {{ background: {c['control_disabled_bg']}; color: {c['control_disabled_fg']}; border-color: {c['control_disabled_bg']}; }}",
            f"QWidget[status=\"ready\"], QWidget[state=\"ready\"], QWidget[readiness=\"ready\"], QWidget[status=\"readiness\"], QWidget[state=\"readiness\"], QWidget[readiness=\"readiness\"] {{ color: {c['readiness']}; background-color: {c['readiness_soft']}; border: 1px solid {c['readiness']}; border-radius: 6px; }}",
            f"QWidget[status=\"loading\"], QWidget[state=\"loading\"], QWidget[readiness=\"loading\"] {{ color: {c['loading']}; background-color: {c['loading_soft']}; border: 1px solid {c['loading']}; border-radius: 6px; }}",
            f"QWidget[status=\"error\"], QWidget[state=\"error\"], QWidget[readiness=\"error\"], QWidget[status=\"failed\"], QWidget[state=\"failed\"], QWidget[readiness=\"failed\"] {{ color: {c['error']}; background-color: {c['error_soft']}; border: 1px solid {c['error']}; border-radius: 6px; }}",
            f"QWidget[status=\"quota\"], QWidget[state=\"quota\"], QWidget[readiness=\"quota\"], QWidget[status=\"cooldown\"], QWidget[state=\"cooldown\"], QWidget[readiness=\"cooldown\"] {{ color: {c['quota']}; background-color: {c['quota_soft']}; border: 1px solid {c['quota']}; border-radius: 6px; }}",
        ]
    )
    if title_line_height is None:
        title_line_height = title_size
    styles = {
        "root": " ".join(base_qss),
        "frame": f"QFrame {{ background-color: {c['shell_bg']}; border: 2px solid {c['shell_border']}; border-radius: {frame_radius}px; }}",
        "header": f"QFrame {{ background-color: {c['header_bg']}; border: 1px solid {c['header_border']}; border-radius: {header_radius}px; }}",
        "subtle_card": f"QFrame {{ background-color: {c['panel_bg']}; border: 1px solid {c['panel_border']}; border-radius: {card_radius}px; }}",
        "primary_card": f"QFrame {{ background-color: {c['panel_bg']}; border: 1px solid {c['accent']}; border-radius: {card_radius}px; }}",
        "title": f"font-size: {title_size}px; font-weight: 800; color: {c['text']}; background: transparent; border: none;",
        "subtitle": f"font-size: {subtitle_size}px; color: {c['subtext']}; background: transparent; border: none;",
        "label": f"font-size: {label_size}px; font-weight: 700; color: {c['text']};",
        "hint": f"color: {c['subtext']};",
        "summary": f"color: {c['accent']}; font-size: 11px; font-weight: 700; background: transparent; border: none; padding: 0;",
        "status_badge": f"color: {c['status_text']}; background-color: {c['status_bg']}; border: 1px solid {c['status_border']}; border-radius: {status_radius}px; padding: 4px 10px;",
        "close_button": f"QPushButton {{ background-color: transparent; color: {c['subtext']}; border: none; font-size: 14px; font-weight: bold; }} QPushButton:hover {{ background-color: {c['accent_soft']}; color: {c['text']}; border-radius: {status_radius}px; }}",
        "button_bg": c["control_bg"],
        "button_fg": c["control_fg"],
        "button_hover": c["control_hover"],
        "button_checked": c["control_checked"],
        "button_focus": c["focus"],
        "checked_fg": c["checked_fg"],
        "button_disabled_fg": c["control_disabled_fg"],
        "button_disabled_bg": c["control_disabled_bg"],
        "danger_bg": c["danger_bg"],
        "danger_hover": c["danger_hover"],
        "danger_fg": c["danger_fg"],
        "danger_checked": c["danger_checked"],
        "combo_bg": c["input_bg"],
        "combo_fg": c["text"],
        "combo_border": c["border"],
        "accent": c["accent"],
        "accent_soft": c["accent_soft"],
        "input_bg": c["input_bg"],
        "text": c["text"],
        "subtext": c["subtext"],
        "border": c["border"],
        "focus": c["focus"],
        "operational": c["operational"],
        "quota": c["quota"],
        "error": c["error"],
        "readiness": c["readiness"],
        "loading": c["loading"],
    }
    styles["button_qss"] = (
        f"QPushButton {{ background-color: {styles['button_bg']}; color: {styles['button_fg']}; "
        f"border-radius: {control_radius}px; padding: 5px 12px; min-height: 32px; font-weight: bold; border: 1px solid {styles['border']}; }}"
        f" QPushButton:hover {{ background-color: {styles['button_hover']}; }}"
        f" QPushButton:focus {{ border: 2px solid {styles['button_focus']}; }}"
        f" QPushButton:checked {{ background-color: {styles['button_checked']}; color: {styles['checked_fg']}; border-color: {styles['button_checked']}; }}"
        f" QPushButton:disabled {{ background-color: {styles['button_disabled_bg']}; color: {styles['button_disabled_fg']}; border-color: {styles['button_disabled_bg']}; }}"
    )
    styles["auto_button_qss"] = styles["button_qss"]
    styles["danger_button_qss"] = (
        f"QPushButton {{ background-color: {styles['danger_bg']}; color: {styles['danger_fg']}; "
        f"border-radius: {control_radius}px; padding: 5px 12px; min-height: 32px; border: 1px solid {styles['danger_bg']}; }}"
        f" QPushButton:hover {{ background-color: {styles['danger_hover']}; }}"
        f" QPushButton:focus {{ border: 2px solid {styles['focus']}; }}"
        f" QPushButton:disabled {{ background-color: {styles['button_disabled_bg']}; color: {styles['button_disabled_fg']}; border-color: {styles['button_disabled_bg']}; }}"
    )
    styles["theme_button_qss"] = (
        f"QPushButton {{ background-color: transparent; color: {c['accent']}; border: none; font-size: 18px; }}"
        f" QPushButton:hover {{ background-color: {c['accent_soft']}; border-radius: {status_radius}px; }}"
    )
    return styles


def build_controller_styles(theme: ThemeDefinition) -> dict:
    return build_window_styles(
        theme,
        frame_radius=18,
        header_radius=18,
        card_radius=12,
        title_size=18,
        subtitle_size=12,
        label_size=14,
        status_radius=8,
        control_radius=10,
        scroll_area=False,
    )


def build_settings_styles(theme: ThemeDefinition) -> dict:
    styles = build_window_styles(
        theme,
        frame_radius=20,
        header_radius=18,
        card_radius=14,
        title_size=20,
        subtitle_size=13,
        label_size=15,
        status_radius=10,
        control_radius=10,
        scroll_area=True,
    )
    styles.update(
        {
            "settings_shell_bg": theme.get("settings_shell_bg", theme.shell_bg),
            "settings_top_bg": theme.get("settings_top_bg", theme.shell_bg),
            "settings_nav_bg": theme.get("settings_nav_bg", theme.input_bg),
            "settings_card_bg": theme.get("settings_card_bg", theme.panel_bg),
            "settings_fallback_bg": theme.get("settings_fallback_bg", theme.shell_bg),
            "settings_background_enabled": theme.key != "high_contrast",
        }
    )
    return styles
