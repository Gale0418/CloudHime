from PySide6.QtCore import QPoint
from PySide6.QtGui import QFont

from marquee_label import MarqueeLabel


def test_short_text_stays_still_and_accessibility_tracks_text(qtbot):
    label = MarqueeLabel("short")
    qtbot.addWidget(label)
    label.resize(240, 28)
    label.show()
    qtbot.wait(80)

    assert label.text() == "short"
    assert label.toolTip() == label.text()
    assert label.statusTip() == label.text()
    assert label.accessibleName() == label.text()
    assert not label._timer.isActive()


def test_overflow_scrolls_and_hovers_pause_with_full_tooltip(qtbot):
    label = MarqueeLabel("A long translated privacy and region hint that cannot fit")
    qtbot.addWidget(label)
    label.resize(90, 28)
    label.move(300, 300)
    label.show()
    qtbot.mouseMove(label, QPoint(140, 50))
    qtbot.waitUntil(label._timer.isActive)
    qtbot.wait(120)
    assert label._offset > 0
    previous_offset = label._offset
    label.setText(label.text())
    qtbot.waitUntil(lambda: label._offset > previous_offset)

    qtbot.mouseMove(label, label.rect().center())
    qtbot.waitUntil(lambda: label._hovered)
    paused_offset = label._offset
    qtbot.wait(100)
    assert not label._timer.isActive()
    assert label._offset == paused_offset
    assert label.toolTip() == label.text()


def test_hidden_timer_stops_and_show_resumes_overflow(qtbot):
    label = MarqueeLabel("A sufficiently long region hint to overflow")
    qtbot.addWidget(label)
    label.resize(80, 28)
    label.show()
    qtbot.waitUntil(label._timer.isActive)
    label.hide()
    assert not label._timer.isActive()

    label.show()
    qtbot.waitUntil(label._timer.isActive)


def test_text_and_resize_recalculate_overflow_and_deleted_label_timer(qtbot):
    label = MarqueeLabel("short")
    qtbot.addWidget(label)
    label.resize(80, 28)
    label.show()
    label.setText("A long LocalGemma privacy explanation")
    qtbot.waitUntil(label._timer.isActive)
    label.resize(500, 28)
    qtbot.waitUntil(lambda: not label._timer.isActive())
    assert label.text() == "A long LocalGemma privacy explanation"

    label.resize(60, 28)
    qtbot.waitUntil(label._timer.isActive)
    label.deleteLater()
    qtbot.wait(50)


def test_font_change_recalculates_overflow_without_resize(qtbot):
    label = MarqueeLabel("A short privacy hint")
    qtbot.addWidget(label)
    label.resize(300, 28)
    small_font = QFont(label.font())
    small_font.setPointSize(7)
    label.setFont(small_font)
    assert label.fontMetrics().horizontalAdvance(label.text()) <= label.contentsRect().width()
    label.show()
    assert not label._timer.isActive()

    large_font = QFont(label.font())
    large_font.setPointSize(36)
    label.setFont(large_font)
    assert label.fontMetrics().horizontalAdvance(label.text()) > label.contentsRect().width()
    qtbot.waitUntil(label._timer.isActive)
