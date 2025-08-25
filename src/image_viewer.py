from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QToolBar,
    QLabel,
    QFileDialog,
    QMessageBox,
    QPushButton,
)
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
        self.setWindowTitle("RandomViewer")
        self.resize(width, height)

        self.toolbar = ToolBar(self)
        self.addToolBar(self.toolbar)
        self.toolbar.setFixedHeight(40)

        self.view = ImageDisplayWidget(self)  # 自定义绘制控件
        self.view.resize(self.width(), self.height() - self.toolbar.height())
        self.setCentralWidget(self.view)
        self.img = None  # 当前图片记录
        self.qimage = None  # 原始图片数据
        self.cached_scaled_image = None  # 缓存缩放后的图像
        self.scale = 1.0
        self.scale_up = True  # 是否允许放大
        self.scale_down = True  # 是否允许缩小
        self.offset = (0, 0)  # 拖动偏移量

        if not configer.config["Path"].get("dir", ""):
            QMessageBox.information(self, "通知", "请选择图片文件夹。")
        else:
            self.show_random_img()

    def update_cached_image(self, factor=1.0):
        if not self.qimage:
            self.cached_scaled_image = None
            return
        # 2. 获取当前窗口（或显示区域）的尺寸
        window_width = self.view.width()  # 显示图片的部件宽度
        window_height = self.view.height()  # 显示图片的部件高度

        # 4. 检查缩放权限
        if factor > 1.0 and not self.scale_up:
            return
        if factor < 1.0 and not self.scale_down:
            return

        # 计算初始新缩放比例
        new_scale = self.scale * factor

        # 原始图片尺寸
        orig_width = self.qimage.width()
        orig_height = self.qimage.height()

        # 基于窗口大小计算最小允许缩放比例
        min_allowed_scale = min(
            window_width / orig_width,  # 保证宽度不小于窗口
            window_height / orig_height,  # 保证高度不小于窗口
        )

        # 基于最大尺寸（15000x15000）计算最大允许缩放比例
        max_allowed_scale = min(15000 / orig_width, 15000 / orig_height)

        # 应用缩放限制（先检查最小限制，再检查最大限制）
        # 处理缩小限制（基于窗口大小）
        if new_scale < min_allowed_scale:
            new_scale = min_allowed_scale  # 限制为最小允许比例
            self.scale_down = False  # 禁止继续缩小
        else:
            self.scale_down = True  # 允许缩小

        # 处理放大限制（基于最大尺寸）
        if new_scale > max_allowed_scale:
            new_scale = max_allowed_scale  # 限制为最大允许比例
            self.scale_up = False  # 禁止继续放大
        else:
            self.scale_up = True  # 允许放大

        # 最终确定缩放比例和尺寸
        self.scale = new_scale
        final_width = int(orig_width * self.scale)
        final_height = int(orig_height * self.scale)

        # 选择缩放模式
        transform_mode = (
            Qt.FastTransformation
            if (final_width > 10000 or final_height > 10000)
            else Qt.SmoothTransformation
        )

        # 更新缓存和显示
        self.cached_scaled_image = self.qimage.scaled(
            final_width, final_height, Qt.KeepAspectRatio, transform_mode
        )
        self.toolbar.scale_percent.setText(f"{self.scale:.2f}x")

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
            self.update_cached_image()
        self.view.update()  # 触发重绘

    def load_image(self, img_path):
        self.qimage = QImage(img_path)
        if self.qimage.isNull():
            QMessageBox.critical(self, "错误", f"无法加载图片: {img_path}")
            self.qimage = None
        else:
            self.init_image()
            self.toolbar.scale_percent.setText(f"{self.scale:.2f}x")

    def show_random_img(self):
        img = get_random_unviewed_image()
        if img:
            self.img = img
            self.load_image(img[1])
            mark_viewed(img[0])
            return
        if database_empty():
            QMessageBox.information(
                self, "通知", "当前文件夹没有图片，请重新选择文件夹。"
            )
            # 清除当前显示的图片
            self.qimage = None
            self.view.update()
        else:
            QMessageBox.information(
                self.parent(), "通知", "所有图片已浏览完毕，正在重置浏览状态。"
            )
            reset_viewed()
            img = get_random_unviewed_image()
            self.img = img
            self.load_image(img[1])
            mark_viewed(img[0])

    # 新增：处理拖动偏移
    def set_offset(self, delta):
        self.offset = (self.offset[0] + delta.x(), self.offset[1] + delta.y())
        self.view.update()

    def closeEvent(self, event):
        self.save_config()
        close_database()  # 关闭数据库连接
        return super().closeEvent(event)

    def save_config(self):
        configer.config["Window"]["width"] = str(self.width())
        configer.config["Window"]["height"] = str(self.height())
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


class ToolBar(QToolBar):
    def __init__(self, parent):
        super().__init__(parent)

        self.setStyleSheet(
            """
            QToolBar {
                spacing: 5px;
            }
            """
        )

        load_img = QAction("选择文件夹", self)
        load_img.triggered.connect(lambda: self.scan(0))
        rescan_img = QAction("重新扫描", self)
        rescan_img.triggered.connect(lambda: self.scan(1))
        self.scan_label = QLabel("扫描进度：", self)
        self.scan_process = QLabel("0", self)

        scale_label = QLabel("缩放：", self)
        self.scale_percent = QLabel(self)
        reset_img = QAction("重置图片", self)
        reset_img.triggered.connect(parent.init_image)

        change_img = QPushButton("切换图片", self)
        change_img.setObjectName("changeImgBtn")
        change_img.setStyleSheet(
            """
            #changeImgBtn {
                background-color: #32be32;
                color: white;
                border-radius: 8px;
                padding: 0 10px;
                border: none;
            }
            #changeImgBtn:hover {             /* 鼠标悬停状态 */
                background-color: #32a032;
            }
            #changeImgBtn:pressed {           /* 鼠标点击（按下）状态 */
                background-color: #328c32;
            }
            """
        )
        change_img.clicked.connect(self.parent().show_random_img)
        delete_btn = QPushButton("删除当前图片", self)
        delete_btn.setObjectName("deleteBtn")
        delete_btn.setStyleSheet(
            """
            #deleteBtn {
                background-color: #ff0000;
                color: white;
                border-radius: 8px;
                padding: 0 10px;
                border: none;
            }
            #deleteBtn:hover {             /* 鼠标悬停状态 */
                background-color: #cc0000;
            }
            #deleteBtn:pressed {           /* 鼠标点击（按下）状态 */
                background-color: #aa0000;
            }
            """
        )
        delete_btn.clicked.connect(self.delete_current_image)

        self.addAction(load_img)
        self.addAction(rescan_img)
        self.addWidget(self.scan_label)
        self.addWidget(self.scan_process)
        self.addSeparator()
        self.addAction(reset_img)
        self.addWidget(scale_label)
        self.addWidget(self.scale_percent)
        self.addSeparator()
        self.addWidget(change_img)
        self.addWidget(delete_btn)

        for item in self.children():
            if isinstance(item, QWidget):
                item.setFixedHeight(self.height())

    def scan(self, mode):
        if mode == 0:
            dir_path = QFileDialog.getExistingDirectory(
                self, "选择图片文件夹", configer.config["Path"].get("dir", "")
            )
            if not database_empty():
                img = get_random_unviewed_image()
                if img and dir_path in img[1]:
                    pass
                else:
                    clear_images()
        elif mode == 1:
            dir_path = configer.config["Path"].get("dir", "")
            if not dir_path or not os.path.exists(dir_path):
                QMessageBox.warning(
                    self, "警告", "当前没有有效的图片文件夹，请先选择文件夹。"
                )
                return
        if dir_path:
            configer.config["Path"]["dir"] = dir_path
            exts = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp", ".jfif")
            self.scan_thread = ScanThread(dir_path, exts)
            self.scan_thread.progress.connect(
                lambda idx, total: self.scan_process.setText(f"{idx}/{total}")
            )
            self.scan_thread.finished.connect(self.on_scan_finished)
            self.scan_thread.start()

    def on_scan_finished(self):
        QMessageBox.information(self, "通知", "扫描完成！")
        self.parent().show_random_img()

    def delete_current_image(self):
        if self.parent().qimage is None:
            return
        send2trash(self.parent().img[1])
        delete_image(self.parent().img[0])
        self.parent().show_random_img()


class ScanThread(QThread):
    progress = Signal(int, int)  # 当前进度，总数

    def __init__(self, dir_path, exts):
        super().__init__()
        self.dir_path = dir_path
        self.exts = exts

    def add_image(self, path):
        self.cursor.execute(
            "INSERT INTO images (path, viewed) VALUES (?, ?)", (path, False)
        )
        self.conn.commit()

    def check_image_exists(self, path):
        self.cursor.execute("SELECT id FROM images WHERE path = ?", (path,))
        return self.cursor.fetchone() is not None

    def run(self):
        self.conn = sqlite3.connect("data.db")
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
