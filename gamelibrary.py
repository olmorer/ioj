import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWidgets import QTabWidget, QWidget, QLabel, QListWidget, QPushButton, QHBoxLayout, QVBoxLayout



class GameLibrary(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui()

    def ui(self):
        self.setGeometry(300, 300, 300, 300)
        self.setWindowTitle("Game Library")

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        games_tab = QWidget()
        games_layout = QHBoxLayout(games_tab)
        self.games_list = QListWidget()
        games_layout.addWidget(self.games_list)

        right_layout = QVBoxLayout()
        self.image_label = QLabel("Обложка")
        self.image_label.setFixedSize(150, 150)
        right_layout.addWidget(self.image_label)
        self.info_label = QLabel("Название:\nЖанр:\nГод:")
        right_layout.addWidget(self.info_label)
        self.add_btn = QPushButton("Добавить")
        self.edit_btn = QPushButton("Изменить")
        self.delete_btn = QPushButton("Удалить")
        right_layout.addWidget(self.add_btn)
        right_layout.addWidget(self.edit_btn)
        right_layout.addWidget(self.delete_btn)
        games_layout.addLayout(right_layout)

        self.tabs.addTab(games_tab, "Игры")
        self.tabs.addTab(QWidget(), "Чемпионаты")
        self.tabs.addTab(QWidget(), "Участники")

        file_menu = self.menuBar().addMenu("Файл")
        file_menu.addAction("Импортироват игр из csv...")
        file_menu.addAction("Экспорт игр в csv...")
        file_menu.addAction("Экспорт результатов в csv...")
        file_menu.addAction("Выход", self.close)

        stat_menu = self.menuBar().addMenu("Статистика")
        stat_menu.addAction("Посмотреть статистику...")

        self.statusBar().showMessage("Готово")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = GameLibrary()
    ex.show()
    sys.exit(app.exec())


