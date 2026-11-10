import sys, csv, sqlite3, datetime
from collections import Counter
from PyQt6.QtCore import Qt, QDate, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtWidgets import *
db = sqlite3.connect("gamevault.db")
db.create_function("LOW", 1, lambda s: (s or "").lower())  # поиск без учёта регистра (и для кириллицы)
db.executescript("""
CREATE TABLE IF NOT EXISTS games(id INTEGER PRIMARY KEY, title TEXT, genre TEXT, year INTEGER, cover TEXT, fav INTEGER, notes TEXT, platform TEXT);
CREATE TABLE IF NOT EXISTS champs(id INTEGER PRIMARY KEY, name TEXT, game_id INTEGER, date TEXT, descr TEXT);
CREATE TABLE IF NOT EXISTS participants(id INTEGER PRIMARY KEY, name TEXT, nick TEXT);""")

def columns(table):
    return [c[1] for c in db.execute(f"PRAGMA table_info({table})")]

for table, col in (("games", "platform"), ("champs", "descr")):
    if col not in columns(table):
        db.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
old = []
if "player" in columns("results"):  # раньше результат хранил имя игрока текстом
    old = db.execute("SELECT champ_id, player, score FROM results ORDER BY champ_id, score DESC").fetchall()
    db.execute("DROP TABLE results")
db.execute("CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY, champ_id INTEGER, participant_id INTEGER, place INTEGER, score INTEGER)")
for cid, player, score in old:
    row = db.execute("SELECT id FROM participants WHERE name=?", (player,)).fetchone()
    pid = row[0] if row else db.execute("INSERT INTO participants(name, nick) VALUES (?, '')", (player,)).lastrowid
    place = 1 + sum(1 for r in old if r[0] == cid and r[2] > score)
    db.execute("INSERT INTO results(champ_id, participant_id, place, score) VALUES (?,?,?,?)", (cid, pid, place, score))
db.commit()
ID = Qt.ItemDataRole.UserRole
GAME_SQL = "SELECT title, genre, year, cover, fav, notes, platform FROM games WHERE id=?"
BTN = QDialogButtonBox.StandardButton
DATE_FMT = "yyyy-MM-dd"

def run(sql, args=()):
    db.execute(sql, args)
    db.commit()

def add_buttons(layout, pairs):
    for text, func in pairs:
        btn = QPushButton(text)
        btn.clicked.connect(func)
        layout.addWidget(btn)

def label(name, nick):
    return f"{name} ({nick})" if nick else name

def make_table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    return table

def fill(table, rows):
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row[1:]):
            item = QTableWidgetItem("" if value is None else str(value))
            item.setData(ID, row[0])
            table.setItem(r, c, item)

def selected_id(table, parent):
    row = table.currentRow()
    if row < 0:
        QMessageBox.information(parent, "Выбор", "Сначала выберите строку в таблице")
        return None
    return table.item(row, 0).data(ID)

def winners(mode, date_from, date_to, game_id, n):
    p = {"a": date_from, "b": date_to, "g": game_id, "n": n}
    base = ("FROM results r JOIN champs c ON c.id = r.champ_id JOIN participants p ON p.id = r.participant_id "
            "WHERE c.date BETWEEN :a AND :b AND (:g IS NULL OR c.game_id = :g)")
    if mode == 0:
        data = db.execute("SELECT c.name, c.date, r.place, p.name, p.nick, r.score " + base +
                          " AND r.place <= :n ORDER BY c.date DESC, c.id, r.place", p).fetchall()
        rows = [(0, c, d, pl, label(nm, nk), sc) for c, d, pl, nm, nk, sc in data]
        bars = Counter(label(r[3], r[4]) for r in data).most_common(10)
        return ["Чемпионат", "Дата", "Место", "Участник", "Очки"], rows, bars
    if mode == 1:
        sql, head = "SELECT p.name, p.nick, COUNT(*) " + base + " AND r.place <= :n GROUP BY p.id ORDER BY 3 DESC, p.name", "Призовых мест"
    else:
        sql, head = "SELECT p.name, p.nick, SUM(r.score) " + base + " GROUP BY p.id ORDER BY 3 DESC, p.name", "Сумма очков"
    data = db.execute(sql, p).fetchall()
    return ["Участник", head], [(0, label(nm, nk), v) for nm, nk, v in data], [(label(nm, nk), v) for nm, nk, v in data[:10]]

class FormDialog(QDialog):
    def __init__(self, title, rows):
        super().__init__()
        self.setWindowTitle(title)
        form = QFormLayout(self)
        for text, widget in rows:
            form.addRow(text, widget)
        buttons = QDialogButtonBox(BTN.Ok | BTN.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow("", buttons)

class GameDialog(QDialog):
    def __init__(self, data=("", "", 2020, "", 0, "", "")):
        super().__init__()
        self.setWindowTitle("Игра")
        form = QFormLayout(self)
        self.title, self.genre, self.cover = QLineEdit(data[0]), QLineEdit(data[1]), QLineEdit(data[3])
        self.platform = QLineEdit(data[6] or "")
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
        for label_, w in (("Название:", self.title), ("Жанр:", self.genre), ("Платформа:", self.platform),
                          ("Год:", self.year), ("Обложка:", self.cover), ("", browse), ("", self.fav),
                          ("Заметки:", self.notes), ("", buttons)):
            form.addRow(label_, w)
    def values(self):
        return (self.title.text().strip(), self.genre.text().strip(), self.year.value(), self.cover.text(),
                int(self.fav.isChecked()), self.notes.toPlainText(), self.platform.text().strip())

class ChampDialog(FormDialog):
    def __init__(self, data=("", None, "", "")):
        name, game, descr = QLineEdit(data[0]), QComboBox(), QTextEdit(data[3] or "")
        game.addItem("— без игры —", None)
        for gid, title in db.execute("SELECT id, title FROM games ORDER BY title"):
            game.addItem(title, gid)
        game.setCurrentIndex(max(0, game.findData(data[1])))
        date = QDateEdit(QDate.fromString(data[2], DATE_FMT) if data[2] else QDate.currentDate())
        date.setCalendarPopup(True)
        super().__init__("Чемпионат", (("Название:", name), ("Игра:", game), ("Дата:", date), ("Описание:", descr)))
        self.name, self.game, self.date, self.descr = name, game, date, descr
    def values(self):
        return (self.name.text().strip(), self.game.currentData(), self.date.date().toString(DATE_FMT),
                self.descr.toPlainText())

class PartDialog(FormDialog):
    def __init__(self, data=("", "")):
        name, nick = QLineEdit(data[0]), QLineEdit(data[1] or "")
        super().__init__("Участник", (("Имя:", name), ("Никнейм:", nick)))
        self.name, self.nick = name, nick
    def values(self):
        return self.name.text().strip(), self.nick.text().strip()

class ResultDialog(FormDialog):
    def __init__(self, data=(None, 1, 0)):
        who, place, score = QComboBox(), QSpinBox(), QSpinBox()
        for pid, name, nick in db.execute("SELECT id, name, nick FROM participants ORDER BY name"):
            who.addItem(label(name, nick), pid)
        who.setCurrentIndex(max(0, who.findData(data[0])))
        place.setRange(1, 999)
        place.setValue(data[1])
        score.setRange(0, 100000)
        score.setValue(data[2])
        super().__init__("Результат", (("Участник:", who), ("Место:", place), ("Очки:", score)))
        self.who, self.place, self.score = who, place, score
    def values(self):
        return self.who.currentData(), self.place.value(), self.score.value()

class ResultsDialog(QDialog):
    def __init__(self, cid, name):
        super().__init__()
        self.cid = cid
        self.setWindowTitle("Результаты: " + name)
        self.resize(560, 380)
        layout, row = QVBoxLayout(self), QHBoxLayout()
        self.table = make_table(["Место", "Участник", "Никнейм", "Очки"])
        layout.addWidget(self.table)
        add_buttons(row, (("Добавить результат", self.add), ("Изменить", self.edit), ("Удалить", self.delete)))
        layout.addLayout(row)
        self.load()
    def load(self):
        fill(self.table, db.execute(
            "SELECT r.id, r.place, p.name, p.nick, r.score FROM results r JOIN participants p "
            "ON p.id = r.participant_id WHERE r.champ_id=? ORDER BY r.place, r.score DESC", (self.cid,)).fetchall())
    def save(self, rid=None):
        if not db.execute("SELECT 1 FROM participants").fetchone():
            return QMessageBox.warning(self, "Нет участников", "Сначала добавьте участников на вкладке «Участники».")
        dlg = ResultDialog(db.execute("SELECT participant_id, place, score FROM results WHERE id=?", (rid,)).fetchone() or (None, 1, 0))
        if not dlg.exec():
            return
        pid, place, score = dlg.values()
        if db.execute("SELECT 1 FROM results WHERE champ_id=? AND participant_id=? AND id IS NOT ?",
                      (self.cid, pid, rid)).fetchone():
            return QMessageBox.warning(self, "Дубликат", "Этот участник уже есть в чемпионате.")
        if rid:
            run("UPDATE results SET participant_id=?, place=?, score=? WHERE id=?", (pid, place, score, rid))
        else:
            run("INSERT INTO results(champ_id, participant_id, place, score) VALUES (?,?,?,?)", (self.cid, pid, place, score))
        self.load()
    def add(self):
        self.save()
    def edit(self):
        rid = selected_id(self.table, self)
        if rid:
            self.save(rid)
    def delete(self):
        rid = selected_id(self.table, self)
        if rid:
            run("DELETE FROM results WHERE id=?", (rid,))
            self.load()

class BarChart(QWidget):
    def __init__(self):
        super().__init__()
        self.bars = []
        self.setMinimumHeight(230)
    def set_bars(self, bars):
        self.bars = bars
        self.update()
    def paintEvent(self, event):
        p, w, h = QPainter(self), self.width(), self.height()
        if not self.bars:
            return p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет данных для диаграммы")
        top, slot = max(v for _, v in self.bars) or 1, w / len(self.bars)
        for i, (text, v) in enumerate(self.bars):
            bh, x = (h - 60) * v / top, i * slot + slot * 0.15
            p.fillRect(QRectF(x, h - 30 - bh, slot * 0.7, bh), QColor("#3d5afe"))
            p.drawText(QRectF(x, h - 48 - bh, slot * 0.7, 16), Qt.AlignmentFlag.AlignCenter, f"{v:g}")
            p.drawText(QRectF(i * slot, h - 28, slot, 24), Qt.AlignmentFlag.AlignCenter,
                       p.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(slot) - 4))

class WinnersDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Победители и рейтинги")
        self.resize(740, 620)
        layout, top = QVBoxLayout(self), QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(["Победители и призёры чемпионатов", "Рейтинг по числу призовых мест", "Рейтинг по сумме очков"])
        self.n = QSpinBox()
        self.n.setRange(1, 50)
        self.n.setValue(3)
        self.game = QComboBox()
        self.game.addItem("Все игры", None)
        for gid, title in db.execute("SELECT id, title FROM games ORDER BY title"):
            self.game.addItem(title, gid)
        self.d1, self.d2 = QDateEdit(QDate(2000, 1, 1)), QDateEdit(QDate.currentDate().addYears(1))
        for text, w in (("Места до:", self.n), ("Игра:", self.game), ("С:", self.d1), ("По:", self.d2)):
            top.addWidget(QLabel(text))
            top.addWidget(w)
        for d in (self.d1, self.d2):
            d.setCalendarPopup(True)
        self.table, self.chart, self.caption = make_table([]), BarChart(), QLabel()
        for w in (self.mode, ):
            layout.addWidget(w)
        layout.addLayout(top)
        layout.addWidget(self.table)
        layout.addWidget(self.caption)
        layout.addWidget(self.chart)
        for signal in (self.mode.currentIndexChanged, self.n.valueChanged, self.game.currentIndexChanged,
                       self.d1.dateChanged, self.d2.dateChanged):
            signal.connect(self.refresh)
        self.refresh()
    def refresh(self, *args):
        mode = self.mode.currentIndex()
        heads, rows, bars = winners(mode, self.d1.date().toString(DATE_FMT), self.d2.date().toString(DATE_FMT),
                                    self.game.currentData(), self.n.value())
        self.table.setColumnCount(len(heads))
        self.table.setHorizontalHeaderLabels(heads)
        fill(self.table, rows)
        self.caption.setText("Диаграмма: " + ("сумма очков" if mode == 2 else "число призовых мест"))
        self.chart.set_bars(bars)

class GameLibrary(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui()
        self.load_games()
        self.load_champs()
        self.load_people()
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
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по названию, жанру, платформе")
        self.search.textChanged.connect(self.load_games)
        self.fav_only = QCheckBox("Только избранное")
        self.fav_only.stateChanged.connect(self.load_games)
        self.games_list = QListWidget()
        self.games_list.currentItemChanged.connect(self.show_game)
        left.addWidget(self.search)
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
        self.champs_list.currentItemChanged.connect(self.show_champ)
        self.champs_list.itemDoubleClicked.connect(self.open_results)
        self.champ_info = QLabel("Описание:")
        self.champ_info.setWordWrap(True)
        champ_layout.addWidget(self.champs_list)
        champ_layout.addWidget(self.champ_info)
        add_buttons(row, (("Создать чемпионат", self.add_champ), ("Изменить", self.edit_champ),
                          ("Удалить чемпионат", self.delete_champ), ("Результаты...", self.open_results)))
        champ_layout.addLayout(row)
        self.tab("Чемпионаты", champ_layout)

        part_layout, row = QVBoxLayout(), QHBoxLayout()
        self.table = make_table(["Имя", "Никнейм"])
        part_layout.addWidget(self.table)
        add_buttons(row, (("Добавить участника", self.add_person), ("Изменить", self.edit_person),
                          ("Удалить участника", self.delete_person)))
        part_layout.addLayout(row)
        self.tab("Участники", part_layout)
        file_menu = self.menuBar().addMenu("Файл")
        file_menu.addAction("Импорт игр из CSV...", self.import_games)
        file_menu.addAction("Экспорт игр в CSV...", lambda: self.export_csv(
            "games.csv", ["title", "genre", "year", "platform"],
            "SELECT title, genre, year, platform FROM games ORDER BY title"))
        file_menu.addAction("Экспорт результатов в CSV...", lambda: self.export_csv(
            "results.csv", ["champ", "game", "date", "participant", "nick", "place", "score"],
            "SELECT c.name, IFNULL(g.title, ''), c.date, p.name, p.nick, r.place, r.score FROM results r "
            "JOIN champs c ON c.id = r.champ_id JOIN participants p ON p.id = r.participant_id "
            "LEFT JOIN games g ON g.id = c.game_id ORDER BY c.id, r.place"))
        file_menu.addAction("Выход", self.close)
        self.menuBar().addMenu("Статистика").addAction("Посмотреть статистику...", self.show_stats)
        self.menuBar().addMenu("Справка").addAction("О программе", self.show_help)
        self.statusBar().showMessage("Готово")
    def current_id(self, widget):
        item = widget.currentItem()
        if item is None:
            self.statusBar().showMessage("Сначала выберите элемент в списке")
        return item.data(ID) if item else None

    def load_games(self, *args):
        where, params = [], []
        if self.fav_only.isChecked():
            where.append("fav = 1")
        text = self.search.text().strip().lower()
        if text:
            where.append("(instr(LOW(title), ?) OR instr(LOW(genre), ?) OR instr(LOW(platform), ?))")
            params = [text] * 3
        self.games_list.clear()
        sql = "SELECT id, title, fav FROM games" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY title"
        for gid, title, fav in db.execute(sql, params):
            item = QListWidgetItem(("★ " if fav else "") + title)
            item.setData(ID, gid)
            self.games_list.addItem(item)
        self.statusBar().showMessage(f"Игр в списке: {self.games_list.count()}")
    def show_game(self, *args):
        item = self.games_list.currentItem()
        self.image_label.setPixmap(QPixmap())
        if item is None:
            self.image_label.setText("Обложка")
            return self.info_label.setText("Название:\nЖанр:\nГод:")
        title, genre, year, cover, fav, notes, platform = db.execute(GAME_SQL, (item.data(ID),)).fetchone()
        self.info_label.setText(f"Название: {title}\nЖанр: {genre}\nПлатформа: {platform or '—'}\nГод: {year}\n"
                                f"Заметки: {notes or '—'}")
        pix = QPixmap(cover)
        if cover and not pix.isNull():
            self.image_label.setPixmap(pix.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.image_label.setText("Нет обложки")
    def add_game(self):
        dlg = GameDialog()
        if dlg.exec() and dlg.values()[0]:
            run("INSERT INTO games(title, genre, year, cover, fav, notes, platform) VALUES (?,?,?,?,?,?,?)", dlg.values())
            self.load_games()
    def edit_game(self):
        gid = self.current_id(self.games_list)
        if gid is None:
            return
        dlg = GameDialog(db.execute(GAME_SQL, (gid,)).fetchone())
        if dlg.exec() and dlg.values()[0]:
            run("UPDATE games SET title=?, genre=?, year=?, cover=?, fav=?, notes=?, platform=? WHERE id=?", dlg.values() + (gid,))
            self.load_games()
    def delete_game(self):
        gid = self.current_id(self.games_list)
        if gid is not None and QMessageBox.question(self, "Удаление", "Удалить игру?") == QMessageBox.StandardButton.Yes:
            run("DELETE FROM games WHERE id=?", (gid,))
            run("UPDATE champs SET game_id=NULL WHERE game_id=?", (gid,))
            self.load_games()
            self.load_champs()

    def load_champs(self):
        self.champs_list.clear()
        for cid, name, d, game in db.execute("SELECT champs.id, name, date, title FROM champs "
                                             "LEFT JOIN games ON games.id = game_id ORDER BY champs.id"):
            item = QListWidgetItem(f"{name} — {game or '?'} ({d})")
            item.setData(ID, cid)
            self.champs_list.addItem(item)
        self.show_champ()
    def show_champ(self, *args):
        item = self.champs_list.currentItem()
        row = db.execute("SELECT descr FROM champs WHERE id=?", (item.data(ID),)).fetchone() if item else None
        self.champ_info.setText("Описание: " + ((row[0] if row else "") or "—"))
    def add_champ(self):
        dlg = ChampDialog()
        if dlg.exec() and dlg.values()[0]:
            run("INSERT INTO champs(name, game_id, date, descr) VALUES (?,?,?,?)", dlg.values())
            self.load_champs()
    def edit_champ(self):
        cid = self.current_id(self.champs_list)
        if cid is None:
            return
        dlg = ChampDialog(db.execute("SELECT name, game_id, date, descr FROM champs WHERE id=?", (cid,)).fetchone())
        if dlg.exec() and dlg.values()[0]:
            run("UPDATE champs SET name=?, game_id=?, date=?, descr=? WHERE id=?", dlg.values() + (cid,))
            self.load_champs()
    def delete_champ(self):
        cid = self.current_id(self.champs_list)
        if cid is not None:
            run("DELETE FROM results WHERE champ_id=?", (cid,))
            run("DELETE FROM champs WHERE id=?", (cid,))
            self.load_champs()
    def open_results(self, *args):
        cid = self.current_id(self.champs_list)
        if cid is not None:
            ResultsDialog(cid, db.execute("SELECT name FROM champs WHERE id=?", (cid,)).fetchone()[0]).exec()
            self.statusBar().showMessage("Результаты обновлены")

    def load_people(self):
        fill(self.table, db.execute("SELECT id, name, nick FROM participants ORDER BY name").fetchall())
    def add_person(self):
        dlg = PartDialog()
        if dlg.exec() and dlg.values()[0]:
            run("INSERT INTO participants(name, nick) VALUES (?,?)", dlg.values())
            self.load_people()
    def edit_person(self):
        pid = selected_id(self.table, self)
        if pid is None:
            return
        dlg = PartDialog(db.execute("SELECT name, nick FROM participants WHERE id=?", (pid,)).fetchone())
        if dlg.exec() and dlg.values()[0]:
            run("UPDATE participants SET name=?, nick=? WHERE id=?", dlg.values() + (pid,))
            self.load_people()
    def delete_person(self):
        pid = selected_id(self.table, self)
        if pid is not None and QMessageBox.question(
                self, "Удаление", "Удалить участника вместе с его результатами?") == QMessageBox.StandardButton.Yes:
            run("DELETE FROM results WHERE participant_id=?", (pid,))
            run("DELETE FROM participants WHERE id=?", (pid,))
            self.load_people()

    def show_stats(self):
        WinnersDialog().exec()
    def show_help(self):
        QMessageBox.about(self, "О программе", "Game Library — библиотека игр и чемпионатов.\n\n"
                          "Игры: добавление, поиск, обложки. Чемпионаты: двойной клик открывает результаты.\n"
                          "Участники: список игроков. Статистика: победители, рейтинги и диаграмма.\n"
                          "Файл: импорт и экспорт CSV.")

    def import_games(self):
        path = QFileDialog.getOpenFileName(self, "Импорт игр", "", "CSV (*.csv)")[0]
        if not path:
            return
        with open(path, encoding="utf-8-sig", newline="") as f:
            delimiter = ";" if ";" in f.readline() else ","
            f.seek(0)
            rows = [(r["title"].strip(), r.get("genre") or "", int(r["year"]) if (r.get("year") or "").isdigit() else 0,
                     r.get("platform") or "") for r in csv.DictReader(f, delimiter=delimiter) if r.get("title")]
        db.executemany("INSERT INTO games(title, genre, year, cover, fav, notes, platform) VALUES (?,?,?,'',0,'',?)", rows)
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


