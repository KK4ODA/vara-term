"""
gui/sn_graph.py — Real-time S/N ratio chart widget.
"""

from collections import deque
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath
from PyQt6.QtCore import Qt, QRectF

from gui.theme import C, sn_graph_style


class SNGraph(QWidget):
    """Small real-time S/N ratio history chart with Y-axis labels."""

    def __init__(self, parent=None, max_points: int = 60):
        super().__init__(parent)
        self._data = deque(maxlen=max_points)
        self._max_points = max_points
        self.setMinimumHeight(70)
        self.setMaximumHeight(90)
        self.setStyleSheet(sn_graph_style())

    def add_value(self, sn_db: float):
        self._data.append(sn_db)
        self.update()

    def clear_data(self):
        self._data.clear()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Draw border
        painter.setPen(QPen(QColor(C["border"]), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        # Font for labels
        label_font = QFont("Consolas", 7)
        label_font.setStyleHint(QFont.StyleHint.Monospace)
        painter.setFont(label_font)

        # Layout: left margin for Y-axis labels, top for title
        left_margin = 32
        top_margin = 14
        right_margin = 6
        bottom_margin = 4

        plot_x = left_margin
        plot_y = top_margin
        plot_w = w - left_margin - right_margin
        plot_h = h - top_margin - bottom_margin

        # Title: "S/N (dB)"
        painter.setPen(QPen(QColor(C["text_dim"])))
        painter.drawText(QRectF(0, 1, w, top_margin),
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                         "S/N (dB)")

        if not self._data or len(self._data) < 2:
            if not self._data:
                painter.setPen(QPen(QColor(C["border_light"])))
                painter.drawText(QRectF(plot_x, plot_y, plot_w, plot_h),
                                 Qt.AlignmentFlag.AlignCenter,
                                 "No data")
            painter.end()
            return

        points = list(self._data)

        # Calculate nice Y-axis range
        raw_min = min(points)
        raw_max = max(points)

        tick_step = self._nice_step(raw_max - raw_min, 3)
        if tick_step < 1:
            tick_step = 1
        y_min = max(0, int(raw_min / tick_step) * tick_step - tick_step)
        y_max = int(raw_max / tick_step + 1) * tick_step + tick_step
        val_range = y_max - y_min
        if val_range == 0:
            val_range = 1

        # Generate tick values
        ticks = []
        v = y_min
        while v <= y_max:
            ticks.append(v)
            v += tick_step

        # Draw horizontal grid lines
        painter.setPen(QPen(QColor(C["bg_surface"]), 1, Qt.PenStyle.DotLine))
        for tick in ticks:
            frac = 1.0 - (tick - y_min) / val_range
            y = plot_y + plot_h * frac
            if plot_y <= y <= plot_y + plot_h:
                painter.drawLine(int(plot_x), int(y),
                                 int(plot_x + plot_w), int(y))

        # Y-axis tick labels
        painter.setPen(QPen(QColor(C["text_dim"])))
        painter.setFont(label_font)
        for tick in ticks:
            frac = 1.0 - (tick - y_min) / val_range
            y = plot_y + plot_h * frac
            if plot_y <= y <= plot_y + plot_h:
                label = f"{int(tick)}"
                label_rect = QRectF(0, y - 6, left_margin - 4, 12)
                painter.drawText(label_rect,
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                 label)

        # Draw S/N line
        path = QPainterPath()
        step = plot_w / (self._max_points - 1) if self._max_points > 1 else 1

        for i, val in enumerate(points):
            x = plot_x + i * step
            frac = 1.0 - (val - y_min) / val_range
            y = plot_y + plot_h * frac
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        painter.setPen(QPen(QColor(C["info"]), 2))
        painter.drawPath(path)

        # Current value (top-right of plot area, bold)
        painter.setPen(QPen(QColor(C["text"])))
        value_font = QFont("Consolas", 8)
        value_font.setStyleHint(QFont.StyleHint.Monospace)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.drawText(
            QRectF(plot_x + plot_w - 55, plot_y, 55, 14),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            f"{points[-1]:.0f} dB")

        painter.end()

    @staticmethod
    def _nice_step(data_range: float, target_ticks: int) -> int:
        """Pick a clean tick step (1, 2, 5, 10, 20, ...) for the axis."""
        if data_range <= 0:
            return 5
        rough = data_range / max(target_ticks, 1)
        magnitude = 1
        while magnitude * 10 <= rough:
            magnitude *= 10
        if rough <= magnitude:
            return magnitude
        elif rough <= magnitude * 2:
            return magnitude * 2
        elif rough <= magnitude * 5:
            return magnitude * 5
        else:
            return magnitude * 10
