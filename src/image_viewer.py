from PySide6.QtWidgets import QMainWindow, QWidget, QToolBar, QLabel, QFileDialog, QMessageBox
from PySide6.QtGui import QImage, QAction, QPainter
from PySide6.QtCore import Qt, QThread, Signal
import os
import sqlite3
from send2trash import send2trash

from conf_manager import configer
from data_manager import *

class ImageViewer(QMainWindow):
    def __init__(self, width, height):
        super().__init__()
        self.setWindowTitle('RandomViewer')
        self.resize(width, height)

        self.toolbar = ToolBar(self)
        self.addToolBar(self.toolbar)

        self.view = ImageDisplayWidget(self)  # 自定义绘制控件
        self.view.resize(self.width(), self.height() - self.toolbar.height())
        self.setCentralWidget(self.view)
        self.qimage = None  # 原始图片数据
        self.scale = 1.0
        self.offset = (0, 0)  # 拖动偏移量

        if configer.config['Path'].get('dir', ''):
            self.img = get_random_unviewed_image()
            if self.img:
                self.load_image(self.img[1])
                mark_viewed(self.img[0])

    def init_image(self):
        self.offset = (0, 0)  # 重置偏移
        # 缩放图片以适应窗口
        view_width = self.view.width()
        view_height = self.view.height()
        if self.qimage:
            img_w = self.qimage.width()
            img_h = self.qimage.height()
            scale_w = view_width / img_w
            scale_h = view_height / img_h
            self.scale = min(scale_w, scale_h, 1.0)  # 初始缩放比例不超过1.0
        self.view.update()    # 触发重绘

    def load_image(self, img_path):
        self.qimage = QImage(img_path)
        if self.qimage.isNull():
            QMessageBox.critical(self, "错误", f"无法加载图片: {img_path}")
            self.qimage = None
        else:
            self.init_image()
            self.toolbar.scale_percent.setText(f"{self.scale:.2f}x")

    def set_scale(self, factor):
        # 缩放逻辑不变，但直接触发重绘
        self.scale *= factor
        self.scale = max(0.1, min(self.scale, 10))  # 限制缩放范围
        self.toolbar.scale_percent.setText(f"{self.scale:.2f}x")
        self.view.update()

    # 新增：处理拖动偏移
    def set_offset(self, delta):
        self.offset = (
            self.offset[0] + delta.x(),
            self.offset[1] + delta.y()
        )
        self.view.update()
    
    def closeEvent(self, event):
        self.save_config()
        close_database()  # 关闭数据库连接
        return super().closeEvent(event)
    
    def save_config(self):
        configer.config['Window']['width'] = str(self.width())
        configer.config['Window']['height'] = str(self.height())
        configer.save_config()

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
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        # 获取原始图片尺寸
        orig_w = self.parent.qimage.width()
        orig_h = self.parent.qimage.height()

        # 计算缩放后的尺寸
        scaled_w = int(orig_w * self.parent.scale)
        scaled_h = int(orig_h * self.parent.scale)

        # 限制拖拽范围
        max_offset_x = max(0, (scaled_w - self.width()) // 2)
        max_offset_y = max(0, (scaled_h - self.height()) // 2)
        self.parent.offset = (
            max(-max_offset_x, min(self.parent.offset[0], max_offset_x)),
            max(-max_offset_y, min(self.parent.offset[1], max_offset_y))
        )

        # 计算绘制位置（基于偏移量居中）
        center_x = (self.width() - scaled_w) // 2 + self.parent.offset[0]
        center_y = (self.height() - scaled_h) // 2 + self.parent.offset[1]

        # 绘制缩放后的图片
        painter.drawImage(
            center_x, center_y,
            self.parent.qimage.scaled(
                scaled_w, scaled_h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation  # 平滑缩放
            )
        )

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
        self.parent.set_scale(factor)
        super().wheelEvent(event)

    # 窗口大小变化时重绘
    def resizeEvent(self, event):
        self.update()
        super().resizeEvent(event)

class ToolBar(QToolBar):
    def __init__(self, parent):
        super().__init__(parent)

        load_img = QAction('选择文件夹', self)
        load_img.triggered.connect(lambda: self.scan(0))
        rescan_img = QAction('重新扫描', self)
        rescan_img.triggered.connect(lambda: self.scan(1))
        self.scan_label = QLabel("扫描进度：", self)
        self.scan_process = QLabel("0", self)

        change_img = QAction('切换图片', self)
        change_img.triggered.connect(self.load_img)
        delete_action = QAction('删除当前图片', self)
        delete_action.triggered.connect(self.delete_current_image)
        scale_label = QLabel("缩放：", self)
        self.scale_percent = QLabel(self)

        self.addAction(load_img)
        self.addAction(rescan_img)
        self.addWidget(self.scan_label)
        self.addWidget(self.scan_process)
        self.addAction(change_img)
        self.addAction(delete_action)
        self.addWidget(scale_label)
        self.addWidget(self.scale_percent)

    def load_img(self):
        img = get_random_unviewed_image()
        if img:
            self.parent().img = img
            self.parent().load_image(img[1])
            mark_viewed(img[0])
            return
        if database_empty():
            QMessageBox.information(self.parent(), "通知", "当前文件夹没有图片，请重新选择文件夹。")
            # 清除当前显示的图片
            self.parent().qimage = None
            self.parent().view.update()
        else:
            QMessageBox.information(self.parent(), "通知", "所有图片已浏览完毕，正在重置浏览状态。")
            reset_viewed()
            img = get_random_unviewed_image()
            self.parent().img = img
            self.parent().load_image(img[1])
            mark_viewed(img[0])
    
    def scan(self, mode):
        if mode == 0:
            dir_path = QFileDialog.getExistingDirectory(self, "选择图片文件夹", configer.config['Path'].get('dir', ''))
            if not database_empty():
                img = get_random_unviewed_image()
                if img and dir_path in img[1]:
                    pass
                else:
                    clear_images()
        elif mode == 1:
            dir_path = configer.config['Path'].get('dir', '')
            if not dir_path or not os.path.exists(dir_path):
                QMessageBox.warning(self, "警告", "当前没有有效的图片文件夹，请先选择文件夹。")
                return
        if dir_path:
            configer.config['Path']['dir'] = dir_path
            exts = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp', '.jfif')
            self.scan_thread = ScanThread(dir_path, exts)
            self.scan_thread.progress.connect(
                lambda idx, total: self.scan_process.setText(f"{idx}/{total}")
                                                             )
            self.scan_thread.finished.connect(self.on_scan_finished)
            self.scan_thread.start()

    def on_scan_finished(self):
        QMessageBox.information(self, "通知", "扫描完成！")
        self.load_img()

    def delete_current_image(self):
        if self.parent().qimage is None:
            return
        send2trash(self.parent().img[1])
        delete_image(self.parent().img[0])
        self.load_img()

class ScanThread(QThread):
    progress = Signal(int, int)  # 当前进度，总数

    def __init__(self, dir_path, exts):
        super().__init__()
        self.dir_path = dir_path
        self.exts = exts
    
    def add_image(self, path):
        self.cursor.execute('INSERT INTO images (path, viewed) VALUES (?, ?)', (path, False))
        self.conn.commit()
    
    def check_image_exists(self, path):
        self.cursor.execute('SELECT id FROM images WHERE path = ?', (path,))
        return self.cursor.fetchone() is not None

    def run(self):
        self.conn = sqlite3.connect('data.db')
        self.cursor = self.conn.cursor()
        image_files = []
        for root, dirs, files in os.walk(self.dir_path):
            for file in files:
                if file.lower().endswith(self.exts):
                    image_files.append(os.path.normpath(os.path.join(root, file)))
        total = len(image_files)
        for idx, img_path in enumerate(image_files, 1):
            if not self.check_image_exists(img_path):
                self.add_image(img_path)
            self.progress.emit(idx, total)
        self.conn.close()