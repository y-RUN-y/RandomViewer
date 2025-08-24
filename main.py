from PySide6.QtWidgets import QApplication
import sys
from image_viewer import ImageViewer
from conf_manager import configer

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ImageViewer(configer.config['Window'].getint('width', 1080), configer.config['Window'].getint('height', 720))
    viewer.show()
    sys.exit(app.exec())