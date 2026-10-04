"""Single-line QLabel that scrolls only when its text does not fit."""

from PySide6.QtCore import QEvent, QPointF, QSize, Qt, QTimer, Slot
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel, QSizePolicy


class MarqueeLabel(QLabel):
    """A plain-text label with a lifecycle-safe, hover-pausable marquee."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.PlainText)
        self.setWordWrap(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._offset = 0.0
        self._hovered = False
        self._gap = 36
        self._pixels_per_tick = 1.0
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._advance)
        self.setText(text)

    def setText(self, text):
        previous_text = super().text()
        super().setText(text)
        full_text = super().text()
        if full_text != previous_text:
            self._offset = 0.0
        self.setToolTip(full_text)
        self.setStatusTip(full_text)
        self.setAccessibleName(full_text)
        self._refresh_marquee()
        self.update()

    def minimumSizeHint(self):
        return QSize(0, self.fontMetrics().height())

    def sizeHint(self):
        return QSize(1, self.fontMetrics().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_marquee(reset=True)

    def changeEvent(self, event):
        super().changeEvent(event)
        timer = getattr(self, "_timer", None)
        if timer is not None and event.type() in {
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
            QEvent.Type.ApplicationFontChange,
        }:
            self._refresh_marquee()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_marquee()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self._timer.stop()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._refresh_marquee()
        super().leaveEvent(event)

    def _text_width(self):
        return self.fontMetrics().horizontalAdvance(super().text())

    def _refresh_marquee(self, reset=False):
        if reset:
            self._offset = 0.0
        overflow = self._text_width() > max(0, self.contentsRect().width())
        if overflow and self.isVisible() and not self._hovered:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            if not overflow:
                self._offset = 0.0
        self.update()

    @Slot()
    def _advance(self):
        # Bound Qt's callback to this QObject and avoid queued lambdas that can
        # outlive the native widget during window teardown.
        if not self.isVisible() or self._hovered or self._text_width() <= self.contentsRect().width():
            self._timer.stop()
            return
        cycle = self._text_width() + self._gap
        if cycle > 0:
            self._offset = (self._offset + self._pixels_per_tick) % cycle
        self.update()

    def paintEvent(self, event):
        if self._text_width() <= self.contentsRect().width():
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setClipRect(self.contentsRect())
        painter.setPen(self.palette().color(self.foregroundRole()))
        metrics = self.fontMetrics()
        rect = self.contentsRect()
        baseline = rect.top() + (rect.height() - metrics.height()) / 2 + metrics.ascent()
        text = super().text()
        width = self._text_width()
        start = rect.left() - self._offset
        while start < rect.right():
            painter.drawText(QPointF(start, baseline), text)
            start += width + self._gap
        painter.end()
