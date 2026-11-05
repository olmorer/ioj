import sys, csv, sqlite3, datetime
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import *
db = sqlite3.connect("gamevault.db")
db.executescript("""
CREATE TABLE IF NOT EXISTS games(id INTEGER PRIMARY KEY, title TEXT, genre TEXT, year INTEGER, cover TEXT, fav INTEGER, notes TEXT);
CREATE TABLE IF NOT EXISTS champs(id INTEGER PRIMARY KEY, name TEXT, game_id INTEGER, date TEXT);
CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY, champ_id INTEGER, player TEXT, score INTEGER);""")
ID = Qt.ItemDataRole.UserRole
GAME_SQL = "SELECT title, genre, year, cover, fav, notes FROM games WHERE id=?"
BTN = QDialogButtonBox.StandardButton

def run(sql, args=()):
    db.execute(sql, args)
    db.commit()

def add_buttons(layout, pairs):
    for text, func in pairs:
        btn = QPushButton(text)
        btn.clicked.connect(func)
        layout.addWidget(btn)

class GameDialog(QDialog): 
    def __init__(self, data=("", "", 2020, "", 0, "")):
        super().__init__()
        self.setWindowTitle("Игра")
        form = QFormLayout(self)
        self.title, self.genre, self.cover = QLineEdit(data[0]), QLineEdit(data[1]), QLineEdit(data[3])
        self.year = QSpinBox()
        self.year.setRange(1950, 2100)
        self.year.setValue(int(data[2] or 2020))
        self.fav = QCheckBox("Избранное")
        self.fav.setChecked(bool(data[4]))
        self.notes = QTextEdit(data[5] or "")
        browse = QPushButton("Выбрать обложку...")
        browse.clicked.connect(lambda: self.cover.setText(QFileDialog.getOpenFileName(
            self, "Обложка", "", "Изображения (*.png *.jpg *.jpeg)")[0] or self.cover.text()))
        buttons = QDialogButtonBox(BTN.Ok | BTN.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        for label, w in (("Название:", self.title), ("Жанр:", self.genre), ("Год:", self.year), ("Обложка:", self.cover),
                         ("", browse), ("", self.fav), ("Заметки:", self.notes), ("", buttons)):
            form.addRow(label, w)
    def values(self):
        return (self.title.text().strip(), self.genre.text().strip(), self.year.value(), self.cover.text(),
                int(self.fav.isChecked()), self.notes.toPlainText())

class GameLibrary(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui()
        self.load_games()
        self.load_champs()
    def tab(self, name, layout):
        widget = QWidget()
        widget.setLayout(layout)
        self.tabs.addTab(widget, name)
    def ui(self):
        self.setGeometry(300, 300, 720, 460)
        self.setWindowTitle("Game Library")
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        games_layout, left, right_layout = QHBoxLayout(), QVBoxLayout(), QVBoxLayout()
        self.fav_only = QCheckBox("Только избранное")
        self.fav_only.stateChanged.connect(self.load_games)
        self.games_list = QListWidget()
        self.games_list.currentItemChanged.connect(self.show_game)
        left.addWidget(self.fav_only)
        left.addWidget(self.games_list)
        self.image_label = QLabel("Обложка")
        self.image_label.setFixedSize(150, 150)
        self.info_label = QLabel("Название:\nЖанр:\nГод:")
        self.info_label.setWordWrap(True)
        self.info_label.setMaximumWidth(230)
        right_layout.addWidget(self.image_label)
        right_layout.addWidget(self.info_label)
        add_buttons(right_layout, (("Добавить", self.add_game), ("Изменить", self.edit_game),
                                   ("Удалить", self.delete_game)))
        right_layout.addStretch()
        games_layout.addLayout(left)
        games_layout.addLayout(right_layout)
        self.tab("Игры", games_layout)
        champ_layout, row = QVBoxLayout(), QHBoxLayout()
        self.champs_list = QListWidget()
        champ_layout.addWidget(self.champs_list)
        add_buttons(row, (("Создать чемпионат", self.add_champ), ("Удалить чемпионат", self.delete_champ)))
        champ_layout.addLayout(row)
        self.tab("Чемпионаты", champ_layout)
        part_layout, row = QVBoxLayout(), QHBoxLayout()
        self.champ_box = QComboBox()
        self.champ_box.currentIndexChanged.connect(self.load_results)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Участник", "Очки"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        part_layout.addWidget(self.champ_box)
        part_layout.addWidget(self.table)
        add_buttons(row, (("Добавить участника", self.add_result), ("Удалить участника", self.delete_result)))
        part_layout.addLayout(row)
        self.tab("Участники", part_layout)
        file_menu = self.menuBar().addMenu("Файл")
        file_menu.addAction("Импорт игр из CSV...", self.import_games)
        file_menu.addAction("Экспорт игр в CSV...", lambda: self.export_csv(
            "games.csv", ["title", "genre", "year"], "SELECT title, genre, year FROM games ORDER BY title"))
        file_menu.addAction("Экспорт результатов в CSV...", lambda: self.export_csv(
            "results.csv", ["champ", "player", "score"], "SELECT champs.name, results.player, results.score "
            "FROM results JOIN champs ON champs.id = results.champ_id ORDER BY champs.id, results.score DESC"))
        file_menu.addAction("Выход", self.close)
        self.menuBar().addMenu("Статистика").addAction("Посмотреть статистику...", self.show_stats)
        self.statusBar().showMessage("Готово")
    def current_id(self, widget):
        item = widget.currentItem()
        if item is None:
            self.statusBar().showMessage("Сначала выберите элемент в списке")
        return item.data(ID) if item else None
    def load_games(self):
        self.games_list.clear()
        where = " WHERE fav = 1" if self.fav_only.isChecked() else ""
        for gid, title, fav in db.execute("SELECT id, title, fav FROM games" + where + " ORDER BY title"):
            item = QListWidgetItem(("★ " if fav else "") + title)
            item.setData(ID, gid)
            self.games_list.addItem(item)
        self.statusBar().showMessage(f"Игр в списке: {self.games_list.count()}")
    def show_game(self):
        item = self.games_list.currentItem()
        self.image_label.setPixmap(QPixmap())
        if item is None:
            self.image_label.setText("Обложка")
            return self.info_label.setText("Название:\nЖанр:\nГод:")
        title, genre, year, cover, fav, notes = db.execute(GAME_SQL, (item.data(ID),)).fetchone()
        self.info_label.setText(f"Название: {title}\nЖанр: {genre}\nГод: {year}\nЗаметки: {notes or '—'}")
        pix = QPixmap(cover)
        if cover and not pix.isNull():
            self.image_label.setPixmap(pix.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.image_label.setText("Нет обложки")
    def add_game(self):
        dlg = GameDialog()
        if dlg.exec() and dlg.values()[0]:
            run("INSERT INTO games(title, genre, year, cover, fav, notes) VALUES (?,?,?,?,?,?)", dlg.values())
            self.load_games()
    def edit_game(self):
        gid = self.current_id(self.games_list)
        if gid is None:
            return
        dlg = GameDialog(db.execute(GAME_SQL, (gid,)).fetchone())
        if dlg.exec() and dlg.values()[0]:
            run("UPDATE games SET title=?, genre=?, year=?, cover=?, fav=?, notes=? WHERE id=?", dlg.values() + (gid,))
            self.load_games()
    def delete_game(self):
        gid = self.current_id(self.games_list)
        if gid is not None and QMessageBox.question(self, "Удаление", "Удалить игру?") == QMessageBox.StandardButton.Yes:
            run("DELETE FROM games WHERE id=?", (gid,))
            self.load_games()
            self.load_champs()
    def load_champs(self):
        self.champs_list.clear()
        self.champ_box.clear()
        for cid, name, d, game in db.execute("SELECT champs.id, name, date, title FROM champs "
                                             "LEFT JOIN games ON games.id = game_id ORDER BY champs.id"):
            text = f"{name} — {game or '?'} ({d})"
            item = QListWidgetItem(text)
            item.setData(ID, cid)
            self.champs_list.addItem(item)
            self.champ_box.addItem(text, cid)
    def add_champ(self):
        games = db.execute("SELECT id, title FROM games ORDER BY title").fetchall()
        if not games:
            return QMessageBox.warning(self, "Нет игр", "Сначала добавьте хотя бы одну игру.")
        name, ok = QInputDialog.getText(self, "Чемпионат", "Название чемпионата:")
        if not ok or not name.strip():
            return
        titles = [g[1] for g in games]
        title, ok = QInputDialog.getItem(self, "Чемпионат", "Игра:", titles, 0, False)
        if ok:
            run("INSERT INTO champs(name, game_id, date) VALUES (?,?,?)",
                (name.strip(), games[titles.index(title)][0], datetime.date.today().isoformat()))
            self.load_champs()
    def delete_champ(self):
        cid = self.current_id(self.champs_list)
        if cid is not None:
            run("DELETE FROM results WHERE champ_id=?", (cid,))
            run("DELETE FROM champs WHERE id=?", (cid,))
            self.load_champs()
    def load_results(self):
        rows = db.execute("SELECT id, player, score FROM results WHERE champ_id=? ORDER BY score DESC",
                          (self.champ_box.currentData(),)).fetchall()
        self.table.setRowCount(len(rows))
        for r, (rid, player, score) in enumerate(rows):
            first = QTableWidgetItem(player)
            first.setData(ID, rid)
            self.table.setItem(r, 0, first)
            self.table.setItem(r, 1, QTableWidgetItem(str(score)))
    def add_result(self):
        cid = self.champ_box.currentData()
        if cid is None:
            return self.statusBar().showMessage("Сначала создайте чемпионат")
        name, ok = QInputDialog.getText(self, "Участник", "Имя участника:")
        if not ok or not name.strip():
            return
        score, ok = QInputDialog.getInt(self, "Результат", "Очки:", 0, 0, 100000)
        if ok:
            run("INSERT INTO results(champ_id, player, score) VALUES (?,?,?)", (cid, name.strip(), score))
            self.load_results()
    def delete_result(self):
        row = self.table.currentRow()
        if row < 0:
            return self.statusBar().showMessage("Выберите участника в таблице")
        run("DELETE FROM results WHERE id=?", (self.table.item(row, 0).data(ID),))
        self.load_results()
    def show_stats(self):
        lines = []
        for cid, name in db.execute("SELECT id, name FROM champs"):
            win = db.execute("SELECT player, MAX(score) FROM results WHERE champ_id=?", (cid,)).fetchone()
            lines.append(f"{name}: победитель {win[0]} ({win[1]} очк.)" if win[0] else f"{name}: нет результатов")
        QMessageBox.information(self, "Статистика", "\n".join(lines) or "Чемпионатов пока нет")
    def import_games(self):
        path = QFileDialog.getOpenFileName(self, "Импорт игр", "", "CSV (*.csv)")[0]
        if not path:
            return
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = [(r["title"], r.get("genre", ""), int(r.get("year") or 0)) for r in csv.DictReader(f) if r.get("title")]
        db.executemany("INSERT INTO games(title, genre, year, cover, fav, notes) VALUES (?,?,?,'',0,'')", rows)
        db.commit()
        self.load_games()
        self.statusBar().showMessage(f"Импортировано игр: {len(rows)}")
    def export_csv(self, name, header, query):
        path = QFileDialog.getSaveFileName(self, "Экспорт", name, "CSV (*.csv)")[0]
        if path:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerows(db.execute(query))
            self.statusBar().showMessage("Экспорт выполнен")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = GameLibrary()
    ex.show()
    sys.exit(app.exec())
