"""Keep captions stable during repeated cached frames, using real Qt widgets."""
import pytest

from cloudhime_ui import OverlayWindow


@pytest.fixture
def overlay(qtbot):
    window = OverlayWindow()
    qtbot.addWidget(window)
    yield window
    window.timer.stop()


@pytest.mark.parametrize("mode", ["bubble", "relief", "screenshot"])
def test_identical_frame_keeps_caption_widgets(overlay, mode):
    overlay.set_render_context("region", mode, scan_region=(100, 100, 240, 100))
    result = [("Stay on this page", 100, 100, 180, 40)]
    overlay.update_bubbles(result)
    caption = overlay.bubbles[0]
    geometry = caption.geometry()
    overlay.update_bubbles([list(row) for row in result])
    assert overlay.bubbles[0] is caption
    assert caption.geometry() == geometry
    assert caption.text() == result[0][0]


def test_changed_text_or_position_replaces_caption(overlay):
    overlay.update_bubbles([("First sentence", 100, 100, 180, 40)])
    first = overlay.bubbles[0]
    overlay.update_bubbles([("Next sentence", 100, 100, 180, 40)])
    second = overlay.bubbles[0]
    assert second is not first
    assert second.text() == "Next sentence"
    overlay.update_bubbles([("Next sentence", 200, 100, 180, 40)])
    assert overlay.bubbles[0] is not second
    assert overlay.bubbles[0].source_rect.x() == 200


def test_changed_render_context_relayouts_identical_caption(overlay):
    result = [("Same text, different placement", 100, 100, 180, 40)]
    overlay.update_bubbles(result)
    first = overlay.bubbles[0]
    overlay.set_render_context("region", "relief", scan_region=(100, 100, 240, 100))
    overlay.update_bubbles(result)
    assert overlay.bubbles[0] is not first
    assert overlay.bubbles[0].render_mode == "relief"


@pytest.mark.parametrize("stream_api", ["chunk", "batch"])
def test_final_result_replaces_stream_text_even_when_it_matches_previous_frame(overlay, stream_api):
    result = [("Previous final result", 100, 100, 180, 40)]
    overlay.update_bubbles(result)
    if stream_api == "chunk":
        overlay.update_translation_stream(0, "New partial text", "google", 100, 100, 180, 40)
    else:
        overlay.update_bubble_text_only([("New partial text", 100, 100, 180, 40)])
    assert overlay.bubbles[0].text() == "New partial text"
    overlay.update_bubbles(result)
    assert overlay.bubbles[0].text() == "Previous final result"


def test_clear_invalidates_cached_caption(overlay):
    result = [("Show it again after clearing", 100, 100, 180, 40)]
    overlay.update_bubbles(result)
    first = overlay.bubbles[0]
    overlay.clear_all()
    assert not overlay.bubbles
    assert not first.isVisible()
    overlay.update_bubbles(result)
    assert overlay.bubbles[0] is not first
    assert overlay.bubbles[0].text() == result[0][0]


@pytest.mark.parametrize("change", ["theme", "font"])
def test_display_style_changes_refresh_identical_caption(overlay, change):
    result = [("Read in the new display style", 100, 100, 180, 40)]
    overlay.update_bubbles(result)
    first = overlay.bubbles[0]
    if change == "theme":
        overlay.set_theme_mode("dark")
    else:
        font = overlay.font()
        font.setPointSizeF(font.pointSizeF() + 2)
        overlay.setFont(font)
    overlay.update_bubbles(result)
    assert overlay.bubbles[0] is not first


@pytest.mark.parametrize("mode", ["bubble", "relief"])
def test_adjacent_long_captions_avoid_overlap_and_keep_capture_geometry(overlay, mode):
    overlay.setGeometry(0, 0, 3000, 800)
    overlay.set_render_context(
        "region", mode, relief_offset_x=18, relief_offset_y=-12,
        relief_font_pt=32, scan_region=(400, 260, 200, 120),
    )
    results = [
        ("第一行 / First line / 一行目", 60, 140, 180, 32),
        ("第二行 / Second line / 二行目", 60, 180, 190, 32),
    ]

    overlay.update_bubbles(results)
    first, second = overlay.bubbles
    assert not first.geometry().intersects(second.geometry())
    assert overlay.snapshot_results() == results
    assert [bubble.font().pointSizeF() for bubble in overlay.bubbles] == [32, 32]
    assert [bubble.source_rect.getRect() for bubble in overlay.bubbles] == [
        row[1:] for row in results
    ]

    stable_widgets = tuple(overlay.bubbles)
    stable_geometry = tuple(bubble.geometry() for bubble in overlay.bubbles)
    overlay.update_bubbles([list(row) for row in results])
    assert tuple(overlay.bubbles) == stable_widgets
    assert tuple(bubble.geometry() for bubble in overlay.bubbles) == stable_geometry

    streamed_results = [
        ("Updated first caption with a longer translation", *results[0][1:]),
        ("Updated second caption with a longer translation", *results[1][1:]),
    ]
    overlay.update_translation_stream(0, streamed_results[0][0], "test", *results[0][1:])
    assert not overlay.bubbles[0].geometry().intersects(overlay.bubbles[1].geometry())
    stream_geometry = tuple(bubble.geometry() for bubble in overlay.bubbles)
    for _ in range(3):
        overlay.update_translation_stream(0, streamed_results[0][0], "test", *results[0][1:])
    assert tuple(bubble.geometry() for bubble in overlay.bubbles) == stream_geometry

    overlay.update_bubble_text_only(streamed_results)
    assert not overlay.bubbles[0].geometry().intersects(overlay.bubbles[1].geometry())
    text_only_geometry = tuple(bubble.geometry() for bubble in overlay.bubbles)
    overlay.update_bubbles(streamed_results)
    assert tuple(bubble.geometry() for bubble in overlay.bubbles) == text_only_geometry
    assert overlay.snapshot_results() == streamed_results
