from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt
class ImageDisplayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setMouseTracking(True)
        self._drag_pos = None

    def paintEvent(self, event):
        if not self.parent.qimage or self.parent.qimage.isNull():
            return

        painter = QPainter(self)
        # 关键：启用最高质量的缩放和抗锯齿
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        scaled_img = self.parent.cached_scaled_image
        if not scaled_img or scaled_img.isNull():
            return
        scaled_w = scaled_img.width()
        scaled_h = scaled_img.height()

        # 限制拖拽范围
        max_offset_x = max(0, (scaled_w - self.width()) // 2)
        max_offset_y = max(0, (scaled_h - self.height()) // 2)
        self.parent.offset = (
            max(-max_offset_x, min(self.parent.offset[0], max_offset_x)),
            max(-max_offset_y, min(self.parent.offset[1], max_offset_y)),
        )

        # 计算绘制位置（基于偏移量居中）
        center_x = (self.width() - scaled_w) // 2 + self.parent.offset[0]
        center_y = (self.height() - scaled_h) // 2 + self.parent.offset[1]

        # 绘制缩放后的图片
        painter.drawImage(center_x, center_y, scaled_img)

    # 处理鼠标拖动（与原逻辑类似）
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos:
            delta = event.pos() - self._drag_pos
            self._drag_pos = event.pos()
            self.parent.set_offset(delta)  # 更新偏移量
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    # 处理滚轮缩放（与原逻辑类似）
    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        factor = 1.1 if angle > 0 else 0.9
        self.parent.update_cached_image(factor)
        self.update()
        super().wheelEvent(event)