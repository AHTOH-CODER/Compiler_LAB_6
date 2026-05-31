"""
Модуль с вкладкой для поиска по регулярным выражениям
"""

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

from regex_patterns import RegexPatterns
from search_module import RegexSearchEngine


class RegexSearchTab(QWidget):
    """Вкладка для поиска по регулярным выражениям"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.search_engine = RegexSearchEngine()
        self.current_results = []
        self.current_font_size = 10
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout(self)

        control_group = QGroupBox(self.tr("Управление поиском"))
        control_group.setStyleSheet(
            "QGroupBox { color: #FFA500; font-weight: bold; border: 2px solid #FFA500; "
            "border-radius: 5px; margin-top: 8px; padding-top: 8px; }"
        )
        control_layout = QHBoxLayout(control_group)

        control_layout.addWidget(QLabel(self.tr("Тип поиска:")))
        self.search_combo = QComboBox()
        self.search_combo.addItems(list(RegexPatterns.get_patterns_dict().keys()))
        self.search_combo.setStyleSheet(
            "QComboBox { background-color: #2b2b2b; color: #ffffff; border: 1px solid #FFA500; padding: 4px; }"
        )
        control_layout.addWidget(self.search_combo)

        self.ignore_case_check = QCheckBox(self.tr("Игнорировать регистр"))
        self.ignore_case_check.setStyleSheet("color: #ffffff;")
        control_layout.addWidget(self.ignore_case_check)

        self.search_button = QPushButton(self.tr("Найти"))
        self.search_button.setShortcut("F6")
        self.search_button.setStyleSheet(
            "QPushButton { background-color: #FFA500; color: #000000; font-weight: bold; "
            "padding: 6px 12px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #FFB52E; }"
        )
        self.search_button.clicked.connect(self.perform_search)
        control_layout.addWidget(self.search_button)

        self.clear_button = QPushButton(self.tr("Очистить"))
        self.clear_button.setStyleSheet(
            "QPushButton { background-color: #505050; color: #ffffff; padding: 6px 12px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #606060; }"
        )
        self.clear_button.clicked.connect(self.clear_results)
        control_layout.addWidget(self.clear_button)

        self.example_button = QPushButton(self.tr("Загрузить пример"))
        self.example_button.setStyleSheet(
            "QPushButton { background-color: #505050; color: #ffffff; padding: 6px 12px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #606060; }"
        )
        self.example_button.clicked.connect(self.load_examples)
        control_layout.addWidget(self.example_button)

        control_layout.addStretch()
        main_layout.addWidget(control_group)

        splitter = QSplitter(Qt.Orientation.Vertical)

        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)

        count_layout = QHBoxLayout()
        count_label = QLabel(self.tr("Найдено совпадений:"))
        count_label.setStyleSheet("color: #ffffff;")
        count_layout.addWidget(count_label)
        self.count_label = QLabel("0")
        self.count_label.setStyleSheet("font-weight: bold; color: #FFA500;")
        count_layout.addWidget(self.count_label)
        count_layout.addStretch()
        results_layout.addLayout(count_layout)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            self.tr("Найденная подстрока"),
            self.tr("Строка"),
            self.tr("Позиция"),
            self.tr("Длина"),
        ])
        self.results_table.setStyleSheet(
            "QTableWidget { background-color: #2b2b2b; color: #ffffff; "
            "gridline-color: #FFA500; border: 2px solid #FFA500; border-radius: 5px; }"
            "QTableWidget::item:selected { background-color: #FFA500; color: #000000; }"
            "QHeaderView::section { background-color: #404040; color: #FFA500; "
            "padding: 5px; border: 1px solid #FFA500; font-weight: bold; }"
        )

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.itemSelectionChanged.connect(self.on_result_select)
        results_layout.addWidget(self.results_table)

        self.info_tabs = QTabWidget()
        self.info_tabs.setStyleSheet(
            "QTabWidget::pane { border: 2px solid #FFA500; border-radius: 5px; }"
            "QTabBar::tab { background-color: #404040; color: #ffffff; padding: 6px 12px; }"
            "QTabBar::tab:selected { background-color: #FFA500; color: #000000; font-weight: bold; }"
        )

        task_info_widget = QWidget()
        task_info_layout = QVBoxLayout(task_info_widget)
        self.task_info_browser = QTextBrowser()
        self.task_info_browser.setStyleSheet(
            "QTextBrowser { background-color: #1e1e1e; color: #ffffff; border: none; }"
        )
        task_info_layout.addWidget(self.task_info_browser)
        self.info_tabs.addTab(task_info_widget, self.tr("Информация о задании"))

        examples_widget = QWidget()
        examples_layout = QVBoxLayout(examples_widget)
        self.examples_browser = QTextBrowser()
        self.examples_browser.setStyleSheet(
            "QTextBrowser { background-color: #1e1e1e; color: #ffffff; border: none; }"
        )
        examples_layout.addWidget(self.examples_browser)
        self.info_tabs.addTab(examples_widget, self.tr("Примеры"))

        regex_widget = QWidget()
        regex_layout = QVBoxLayout(regex_widget)
        self.regex_browser = QTextBrowser()
        self.regex_browser.setStyleSheet(
            "QTextBrowser { background-color: #1e1e1e; color: #ffffff; "
            "font-family: monospace; border: none; }"
        )
        regex_layout.addWidget(self.regex_browser)
        self.info_tabs.addTab(regex_widget, self.tr("Регулярное выражение"))

        splitter.addWidget(results_widget)
        splitter.addWidget(self.info_tabs)
        splitter.setSizes([400, 300])
        main_layout.addWidget(splitter)

        self.search_combo.currentTextChanged.connect(self.on_task_change)
        self.on_task_change()

    def load_examples(self):
        example_text = """Пример текста для поиска различных элементов:

1. ЧИСЛА, НАЧИНАЮЩИЕСЯ НА 9:
   Код 905 совпадает с условием, а 89 — нет.
   Номера: 9, 90, 912, 9999, 9001
   Некорректные: 89, 19, 809abc

2. НОМЕРА КАРТ MAESTRO CARD:
   Maestro: 5018021374808902
   Maestro: 6759 6498 2649 8443
   Maestro: 6304-0000-0000-0000
   Visa (не Maestro): 4012881171304827
   Mastercard (не Maestro): 5555555555554444

3. HTML-ТЕГИ С АТРИБУТАМИ:
   <div class="container">
   <img src="photo.jpg" alt="Описание" />
   <input type="text" name="login" value="admin">
   <a href='index.html' target='_blank'>
   Без атрибутов (не находится): <div>, <br />, <p>text</p>

Смешанный текст:
   Пользователь 905 оплатил картой 5018 0213 7480 8902
   <form action="/pay" method="post" id="payment">
   Сумма 912 рублей, карта 4111111111111111 (Visa)
"""
        editor = self.parent.get_current_editor()
        if editor:
            editor.set_text(example_text)
            self.parent.status_bar.showMessage(self.tr("Пример текста загружен"), 3000)
        else:
            QMessageBox.warning(
                self,
                self.tr("Предупреждение"),
                self.tr("Нет активного редактора для загрузки примера"),
            )

    def on_task_change(self):
        task_name = self.search_combo.currentText()
        task_info = RegexPatterns.get_task_info(task_name)

        if not task_info:
            return

        info_text = f"""<h3 style="color: #FFA500;">{self.tr("Описание задания")}</h3>
<p><b>{task_info['description']}</b></p>
<p>{self.tr("Данное регулярное выражение предназначено для поиска всех вхождений указанного паттерна в тексте.")}</p>
<p>{self.tr("Поиск может выполняться с игнорированием регистра символов (для HTML-тегов).")}</p>"""
        self.task_info_browser.setHtml(info_text)

        examples_text = f"""<h3 style="color: #81c784;">{self.tr("Примеры, которые ДОЛЖНЫ находиться:")}</h3>
{''.join(f'<p style="color: #81c784;">✓ {ex}</p>' for ex in task_info['examples_correct'][:6])}
<h3 style="color: #f44336;">{self.tr("Примеры, которые НЕ ДОЛЖНЫ находиться:")}</h3>
{''.join(f'<p style="color: #e57373;">✗ {ex}</p>' for ex in task_info['examples_incorrect'][:6])}"""
        self.examples_browser.setHtml(examples_text)

        regex_explanations = {
            "Числа на 9": """<p><b>\\b</b> — граница слова<br>
<b>9</b> — цифра 9 в начале числа<br>
<b>\\d*</b> — ноль или более цифр<br>
<b>\\b</b> — граница слова</p>""",
            "Maestro Card": """<p><b>\\b</b> — граница слова<br>
<b>(?:5(?:0(?:0\\d{{2}}|[1-9]\\d{{2}})|[6-8]\\d{{2}})|6\\d{{3}})\\d{{10,13}}</b> — номер из 12–19 цифр подряд<br>
<b>|</b> — альтернатива для формата с разделителями<br>
<b>(?:501\\d|...|6\\d{{3}})(?:[\\s-]\\d{{4}}){{3}}</b> — BIN Maestro и три группы по 4 цифры<br>
<b>\\b</b> — граница слова</p>""",
            "HTML-тег с атрибутами": """<p><b>&lt;</b> — открывающая угловая скобка<br>
<b>\\s*</b> — необязательные пробелы<br>
<b>[a-zA-Z][\\w:-]*</b> — имя тега<br>
<b>\\s+</b> — обязательный пробел перед атрибутами<br>
<b>[a-zA-Z][\\w:-]*\\s*=\\s*(?:"[^"]*"|'[^']*'|[^\\s/>]+)</b> — атрибут=значение<br>
<b>+</b> — один или более атрибутов<br>
<b>/?&gt;</b> — необязательный / и закрывающая скобка</p>""",
        }

        regex_text = f"""<h3 style="color: #FFA500;">{self.tr("Регулярное выражение:")}</h3>
<p><code style="font-size: 14px; background-color: #1e1e1e; padding: 5px; display: block;">{task_info['pattern']}</code></p>
<h3 style="color: #FFA500;">{self.tr("Пояснение:")}</h3>
{regex_explanations.get(task_name, '')}"""
        self.regex_browser.setHtml(regex_text)

    def perform_search(self):
        editor = self.parent.get_current_editor()
        if not editor:
            QMessageBox.warning(
                self,
                self.tr("Предупреждение"),
                self.tr("Нет активного редактора для поиска"),
            )
            return

        text = editor.get_text()
        if not text.strip():
            QMessageBox.warning(
                self,
                self.tr("Предупреждение"),
                self.tr("Нет данных для поиска"),
            )
            return

        task_name = self.search_combo.currentText()
        pattern = RegexPatterns.get_patterns_dict().get(task_name, "")
        if not pattern:
            QMessageBox.critical(self, self.tr("Ошибка"), self.tr("Не выбран тип поиска"))
            return

        self.clear_results(clear_editor_highlight=False)

        ignore_case = self.ignore_case_check.isChecked()
        results = self.search_engine.search(text, pattern, task_name, ignore_case)
        self.current_results = results

        self.results_table.setRowCount(len(results))
        for i, result in enumerate(results):
            self.results_table.setItem(i, 0, QTableWidgetItem(result["text"]))
            self.results_table.setItem(i, 1, QTableWidgetItem(str(result["line"])))
            self.results_table.setItem(i, 2, QTableWidgetItem(str(result["char"])))
            self.results_table.setItem(i, 3, QTableWidgetItem(str(result["length"])))

        count = self.search_engine.get_count()
        self.count_label.setText(str(count))

        if count > 0:
            self.parent.status_bar.showMessage(
                self.tr("Найдено совпадений: {}").format(count), 3000
            )
        else:
            self.parent.status_bar.showMessage(self.tr("Совпадений не найдено"), 3000)
            QMessageBox.information(
                self, self.tr("Результаты поиска"), self.tr("Совпадений не найдено")
            )

    def clear_results(self, clear_editor_highlight=True):
        self.results_table.setRowCount(0)
        self.count_label.setText("0")
        self.current_results = []

        if clear_editor_highlight:
            editor = self.parent.get_current_editor()
            if editor:
                cursor = editor.code_editor.textCursor()
                cursor.select(QTextCursor.SelectionType.Document)
                cursor.setCharFormat(QTextCharFormat())
                cursor.clearSelection()
                editor.code_editor.setTextCursor(cursor)
            self.parent.status_bar.showMessage(self.tr("Результаты очищены"), 2000)

    def on_result_select(self):
        selected_rows = self.results_table.selectedItems()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        if row >= len(self.current_results):
            return

        result = self.current_results[row]
        start_pos, end_pos = self.search_engine.get_global_position(row)

        if start_pos >= 0 and end_pos > start_pos:
            editor = self.parent.get_current_editor()
            if not editor:
                return

            cursor = editor.code_editor.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.setCharFormat(QTextCharFormat())

            cursor = editor.code_editor.textCursor()
            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)

            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#FFA500"))
            fmt.setForeground(QColor("#000000"))
            cursor.setCharFormat(fmt)

            editor.code_editor.setTextCursor(cursor)
            editor.code_editor.ensureCursorVisible()

            self.parent.status_bar.showMessage(
                self.tr("Выделен результат: {} (строка {}, позиция {})").format(
                    result["text"], result["line"], result["char"]
                ),
                3000,
            )

    def change_font_size(self, delta):
        self.current_font_size = max(8, min(72, self.current_font_size + delta))
        font = self.results_table.font()
        font.setPointSize(self.current_font_size)
        self.results_table.setFont(font)

    def retranslateUi(self):
        self.results_table.setHorizontalHeaderLabels([
            self.tr("Найденная подстрока"),
            self.tr("Строка"),
            self.tr("Позиция"),
            self.tr("Длина"),
        ])
        self.ignore_case_check.setText(self.tr("Игнорировать регистр"))
        self.search_button.setText(self.tr("Найти"))
        self.clear_button.setText(self.tr("Очистить"))
        self.example_button.setText(self.tr("Загрузить пример"))
        self.info_tabs.setTabText(0, self.tr("Информация о задании"))
        self.info_tabs.setTabText(1, self.tr("Примеры"))
        self.info_tabs.setTabText(2, self.tr("Регулярное выражение"))
        self.on_task_change()
