import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QDialog, QTableWidget, QTextBrowser, QTextEdit, QComboBox, QDateEdit, QMessageBox
import sqlite3


class GameLibrary(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui()

    def ui(self):
        self.setGeometry(300, 300, 300, 300)
        self.setWindowTitle("Game Library")






if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = GameLibrary()
    ex.show()
    sys.exit(app.exec())
