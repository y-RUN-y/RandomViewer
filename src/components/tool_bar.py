from PySide6.QtWidgets import QToolBar, QWidget, QLabel, QFileDialog, QMessageBox, QPushButton
from PySide6.QtGui import QAction
from PySide6.QtCore import QThread, Signal, Qt
import sqlite3
import os
import subprocess
from send2trash import send2trash

from utils.data_manager import database_empty, clear_images, get_random_unviewed_image, delete_image
from utils.conf_manager import configer

class ToolBar(QToolBar):
    def __init__(self, parent):
        super().__init__(parent)
        self.setMovable(False)
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
        self.scan_label.setAlignment(Qt.AlignCenter)
        self.scan_process = QLabel("0", self)
        self.scan_process.setAlignment(Qt.AlignCenter)

        scale_label = QLabel("缩放：", self)
        scale_label.setAlignment(Qt.AlignCenter)
        self.scale_percent = QLabel(self)
        self.scale_percent.setAlignment(Qt.AlignCenter)
        reset_img = QAction("重置图片", self)
        reset_img.triggered.connect(parent.init_image)

        change_img = QPushButton("切换图片", self)
        change_img.setObjectName("changeImgBtn")
        change_img.clicked.connect(self.parent().show_random_img)
        delete_btn = QPushButton("删除当前图片", self)
        delete_btn.setObjectName("deleteBtn")
        delete_btn.clicked.connect(self.delete_current_image)
        open_dir = QAction("打开图片所在文件夹", self)
        open_dir.triggered.connect(self.open_image_directory)

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
        self.addAction(open_dir)

        for item in self.children():
            if isinstance(item, QWidget):
                item.setFixedHeight(40)
                item.setStyleSheet("margin: 5 0px;")
        change_img.setStyleSheet(
            """
            #changeImgBtn {
                background-color: #32be32;
                color: white;
                border-radius: 8px;
                padding: 0 10px;
                margin: 5 0px;
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
        delete_btn.setStyleSheet(
            """
            #deleteBtn {
                background-color: #ff0000;
                color: white;
                border-radius: 8px;
                padding: 0 10px;
                margin: 5 0px;
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
    
    def open_image_directory(self):
        if self.parent().qimage is None:
            return
        if not os.path.exists(os.path.dirname(self.parent().img[1])):
            QMessageBox.warning(self, "警告", "图片所在文件夹不存在。")
            return
        if not os.path.exists(self.parent().img[1]):
            QMessageBox.warning(self, "警告", "目标图片文件不存在。")
            return
        subprocess.run(['explorer.exe', '/select,', self.parent().img[1]])


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