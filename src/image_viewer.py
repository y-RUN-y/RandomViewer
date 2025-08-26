from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtGui import QImage
from PySide6.QtCore import Qt, QEvent
import sys

from utils.conf_manager import configer
from utils.data_manager import *
from components.image_display_widget import ImageDisplayWidget
from components.tool_bar import ToolBar


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RandomViewer")
        
        # 设置窗口初始位置和大小
        screen = QApplication.primaryScreen()
        screen_width = screen.availableGeometry().width()
        screen_height = screen.availableGeometry().height()
        self.default_x = int(screen_width * 0.125)
        self.default_y = int(screen_height * 0.125)
        self.default_width = int(screen_width * 0.75)
        self.default_height = int(screen_height * 0.75)

        if configer.config["Window"].getboolean("max", False):
            x = self.default_x
            y = self.default_y
            width = self.default_width
            height = self.default_height
        else:
            x = configer.config["Window"].getint("x", self.default_x)
            y = configer.config["Window"].getint("y", self.default_y)
            width = configer.config["Window"].getint("width", self.default_width)
            height = configer.config["Window"].getint("height", self.default_height)
        self.move(x, y)
        self.resize(width, height)
        if configer.config["Window"].getboolean("max", False):
            self.showMaximized()
        
        # 工具栏
        self.toolbar = ToolBar(self)
        self.addToolBar(self.toolbar)

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

        # 检查缩放权限
        if factor > 1.0 and not self.scale_up:
            return
        if factor < 1.0 and not self.scale_down:
            return

        # 计算初始新缩放比例
        new_scale = self.scale * factor

        # 原始图片尺寸
        orig_width = self.qimage.width()
        orig_height = self.qimage.height()
        min_allowed_scale = min(50 / orig_width, 50 / orig_height)
        max_allowed_scale = min(15000 / orig_width, 15000 / orig_height)

        # 应用缩放限制（先检查最小限制，再检查最大限制）
        if new_scale < min_allowed_scale:
            new_scale = min_allowed_scale  # 限制为最小允许比例
            self.scale_down = False  # 禁止继续缩小
        else:
            self.scale_down = True  # 允许缩小

        if new_scale > max_allowed_scale:
            new_scale = max_allowed_scale  # 限制为最大允许比例
            self.scale_up = False  # 禁止继续放大
        else:
            self.scale_up = True  # 允许放大

        self.scale = new_scale
        final_width = int(orig_width * self.scale)
        final_height = int(orig_height * self.scale)

        # 选择缩放模式
        transform_mode = (
            Qt.FastTransformation
            if (final_width > 10000 or final_height > 10000)
            else Qt.SmoothTransformation
        )
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

    def load_image(self):
        self.qimage = QImage(self.img[1])
        if self.qimage.isNull():
            QMessageBox.critical(self, "错误", f"无法加载图片: {self.img[1]}")
            delete_image(self.img[0])
            self.qimage = None
        else:
            self.init_image()
            self.toolbar.scale_percent.setText(f"{self.scale:.2f}x")
            if not self.img[2]:
                mark_viewed(self.img[0])

    def show_random_img(self):
        img = get_random_unviewed_image()
        if img:
            self.img = img
            self.load_image()
            return
        if database_empty():
            QMessageBox.information(
                self, "通知", "当前文件夹没有图片或数据库已被清空，请重新选择文件夹扫描。"
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
            if img:
                self.img = img
            self.load_image()

    # 新增：处理拖动偏移
    def set_offset(self, delta):
        self.offset = (self.offset[0] + delta.x(), self.offset[1] + delta.y())
        self.view.update()

    def closeEvent(self, event):
        configer.config["Window"]["max"] = str(self.isMaximized())
        configer.config["Window"]["x"] = str(self.x())
        configer.config["Window"]["y"] = str(self.y())
        configer.config["Window"]["width"] = str(self.width())
        configer.config["Window"]["height"] = str(self.height())
        configer.save_config()
        close_database()  # 关闭数据库连接
        return super().closeEvent(event)
    
    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if not self.isMaximized() and not self.isMinimized():
                self.move(self.default_x, self.default_y)
                self.resize(self.default_width, self.default_height)
        return super().changeEvent(event)
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec())