import os
import sys

from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "logo", "VISION CENTER LOGOLOGO ICON.ico")


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setWindowIcon(QIcon(LOGO_PATH))
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
