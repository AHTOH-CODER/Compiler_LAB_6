import sys
import os
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from translator import Translator
from regex_search_tab import RegexSearchTab
from result_tabs import SyntaxErrorResultTab
from lab6_expression_analyzer import (
    Lexer as ExprLexer,
    RecursiveDescentParser,
    to_postfix,
    eval_postfix,
)

def suppress_console_output():
    try:
        devnull = open(os.devnull, 'w', encoding='utf-8')
        sys.stdout = devnull
        sys.stderr = devnull
    except Exception:
        pass

class SyntaxErrorHighlight(QSyntaxHighlighter):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.error_positions = []
        self.active_error_index = -1
        self.error_format = QTextCharFormat()
        self.error_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        self.error_format.setUnderlineColor(QColor('#FF4444'))
        self.error_format.setBackground(QColor('#44FF4444'))
        self.active_error_format = QTextCharFormat()
        self.active_error_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        self.active_error_format.setUnderlineColor(QColor('#FF0000'))
        self.active_error_format.setBackground(QColor('#88FF6666'))
        self.active_error_format.setFontWeight(QFont.Weight.Bold)

    def set_errors(self, errors, active_index=-1):
        self.error_positions = []
        for e in errors:
            if isinstance(e, dict):
                line = e.get('line', 1)
                col = e.get('col', 1)
                fragment = e.get('fragment', '')
            else:
                line = getattr(e, 'line', 1)
                col = getattr(e, 'col', 1)
                fragment = getattr(e, 'fragment', '')
            self.error_positions.append((line, col, len(str(fragment))))
        self.active_error_index = active_index
        self.rehighlight()
        if self.parent() and hasattr(self.parent(), 'parent'):
            view = self.parent().parent()
            if view and hasattr(view, 'viewport'):
                view.viewport().update()

    def clear_errors(self):
        self.error_positions = []
        self.active_error_index = -1
        self.rehighlight()

    def highlightBlock(self, text):
        block_number = self.currentBlock().blockNumber() + 1
        for i, (line, col, length) in enumerate(self.error_positions):
            if line == block_number:
                fmt = self.active_error_format if i == self.active_error_index else self.error_format
                self.setFormat(col - 1, max(length, 1), fmt)

class LineNumberArea(QWidget):

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_width(), 0)

    def paintEvent(self, event):
        self.code_editor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):

    def __init__(self):
        super().__init__()
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width()
        self.highlight_current_line()
        self.setAcceptDrops(True)

    def line_number_width(self):
        digits = len(str(self.blockCount()))
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_width(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(40, 44, 52))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor(220, 220, 220))
                painter.drawText(0, int(top), self.line_number_area.width() - 2, self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor(50, 55, 65)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.endswith('.txt'):
                main_window = None
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, TextEditor):
                        main_window = widget
                        break
                if main_window:
                    main_window.open_file_with_path(file_path)
                    break

class SyntaxHighlighter(QSyntaxHighlighter):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        keywords = ['val', 'Complex']
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor('#FFA500'))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        for keyword in keywords:
            pattern = QRegularExpression('\\b' + keyword + '\\b')
            rule = (pattern, keyword_format)
            self.highlighting_rules.append(rule)
        string_format = QTextCharFormat()
        string_format.setForeground(QColor('#98FB98'))
        pattern = QRegularExpression('"[^"\\\\]*(\\\\.[^"\\\\]*)*"|\\\'[^\\\'\\\\]*(\\\\.[^\\\'\\\\]*)*\\\'')
        rule = (pattern, string_format)
        self.highlighting_rules.append(rule)
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor('#BC8F8F'))
        pattern = QRegularExpression('//.*')
        rule = (pattern, comment_format)
        self.highlighting_rules.append(rule)
        number_format = QTextCharFormat()
        number_format.setForeground(QColor('#B5CEA8'))
        pattern = QRegularExpression('\\b[0-9]+(\\.[0-9]+)?i?\\b')
        rule = (pattern, number_format)
        self.highlighting_rules.append(rule)

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

class EditorTab(QWidget):

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.code_editor = CodeEditor()
        self.code_editor.setStyleSheet('\n            QPlainTextEdit {\n                border: 2px solid #FFA500;\n                border-radius: 5px;\n                background-color: #1e1e1e;\n                selection-background-color: #FFA500;\n            }\n        ')
        self.highlighter = SyntaxHighlighter(self.code_editor.document())
        self.error_highlighter = SyntaxErrorHighlight(self.code_editor.document())
        self.code_editor.textChanged.connect(self.text_changed)
        layout.addWidget(self.code_editor)
        self.current_file = None
        self.text_modified = False

    def text_changed(self):
        self.text_modified = True

    def get_text(self):
        return self.code_editor.toPlainText()

    def set_text(self, text):
        self.code_editor.setPlainText(text)
        self.text_modified = False

class TokenResultTab(QWidget):

    def __init__(self, tr):
        super().__init__()
        self.tr = tr
        self.current_lang = 'ru'
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.update_headers()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet('\n            QTableWidget {\n                background-color: #2b2b2b;\n                color: #ffffff;\n                gridline-color: #FFA500;\n                border: 2px solid #FFA500;\n                border-radius: 5px;\n            }\n            QTableWidget::item {\n                padding: 5px;\n            }\n            QTableWidget::item:selected {\n                background-color: #FFA500;\n                color: #000000;\n            }\n            QHeaderView::section {\n                background-color: #404040;\n                color: #FFA500;\n                padding: 8px;\n                border: 1px solid #FFA500;\n                font-weight: bold;\n            }\n        ')
        layout.addWidget(self.table)

    def set_language(self, lang):
        self.current_lang = lang
        self.update_headers()

    def update_headers(self):
        self.table.setHorizontalHeaderLabels([self.tr('Тип'), self.tr('Фрагмент'), self.tr('Местоположение'), self.tr('Описание')])

    def clear_results(self):
        self.table.setRowCount(0)

    def add_result(self, code, token_type, lexeme, location):
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)
        self.table.setItem(row_count, 0, QTableWidgetItem(str(code)))
        self.table.setItem(row_count, 1, QTableWidgetItem(token_type))
        self.table.setItem(row_count, 2, QTableWidgetItem(lexeme))
        self.table.setItem(row_count, 3, QTableWidgetItem(location))

class ErrorResultTab(QWidget):

    def __init__(self, tr):
        super().__init__()
        self.tr = tr
        self.current_lang = 'ru'
        self.main_window = None
        self.errors_data = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.update_headers()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet('\n            QTableWidget {\n                background-color: #2b2b2b;\n                color: #ffffff;\n                gridline-color: #FFA500;\n                border: 2px solid #FFA500;\n                border-radius: 5px;\n            }\n            QTableWidget::item {\n                padding: 5px;\n            }\n            QTableWidget::item:selected {\n                background-color: #FFA500;\n                color: #000000;\n            }\n            QHeaderView::section {\n                background-color: #404040;\n                color: #FFA500;\n                padding: 8px;\n                border: 1px solid #FFA500;\n                font-weight: bold;\n            }\n        ')
        self.footer = QLabel()
        self.footer.setStyleSheet('color: #FFA500; padding: 6px 4px; font-weight: bold;')
        layout.addWidget(self.table)
        layout.addWidget(self.footer)
        self.table.itemSelectionChanged.connect(self.on_row_selected)

    def set_main_window(self, window):
        self.main_window = window

    def set_language(self, lang):
        self.current_lang = lang
        self.update_headers()

    def update_headers(self):
        self.table.setHorizontalHeaderLabels([self.tr('Тип'), self.tr('Фрагмент'), self.tr('Местоположение'), self.tr('Описание'), self.tr('Строка')])

    def clear_results(self):
        self.table.setRowCount(0)
        self.errors_data = []
        self.footer.setText('')

    def add_error(self, error_type, fragment, location, description):
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)
        items = [QTableWidgetItem(error_type), QTableWidgetItem(fragment), QTableWidgetItem(location), QTableWidgetItem(description)]
        for col, item in enumerate(items):
            item.setForeground(QColor('#F48771'))
            self.table.setItem(row_count, col, item)
        self.errors_data.append({'type': error_type, 'fragment': fragment, 'location': location, 'description': description, 'row': row_count})
        self.footer.setText(f"{self.tr('Всего ошибок:')} {row_count + 1}")

    def on_row_selected(self):
        if not self.main_window:
            return
        row = self.table.currentRow()
        if row < 0 or row >= len(self.errors_data):
            return
        err = self.errors_data[row]
        location = err['location']
        import re
        if self.current_lang == 'ru':
            match = re.search('строка (\\d+), позиция (\\d+)', location)
        else:
            match = re.search('line (\\d+), position (\\d+)', location)
        if match:
            line = int(match.group(1))
            col = int(match.group(2))
            self.main_window.go_to_position(line, col, row)

class TextEditor(QMainWindow):

    def __init__(self):
        super().__init__()
        self.translator = Translator()
        self.tr = self.translator.tr
        self.current_font_size = 11
        self.result_font_size = 10
        self.expr_lexer = ExprLexer()
        self.initUI()
        self.retranslateUi()
        self.editor_tabs.currentChanged.connect(self.update_cursor_position)

    def initUI(self):
        self.setStyleSheet('\n            QMainWindow {\n                background-color: #2b2b2b;\n            }\n            QTabWidget::pane {\n                border: 2px solid #FFA500;\n                border-radius: 5px;\n                top: -1px;\n            }\n            QTabBar::tab {\n                background-color: #404040;\n                color: #ffffff;\n                padding: 8px 12px;\n                margin-right: 2px;\n                border-top-left-radius: 5px;\n                border-top-right-radius: 5px;\n            }\n            QTabBar::tab:selected {\n                background-color: #FFA500;\n                color: #000000;\n                font-weight: bold;\n            }\n            QTabBar::tab:hover {\n                background-color: #606060;\n            }\n        ')
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(self.close_editor_tab)
        self.result_tabs = QTabWidget()
        self.text_result_tab = QWidget()
        text_result_layout = QVBoxLayout(self.text_result_tab)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet('\n            QTextEdit {\n                background-color: #1e1e1e;\n                color: #ffffff;\n                border: 2px solid #FFA500;\n                border-radius: 5px;\n                padding: 5px;\n                selection-background-color: #FFA500;\n            }\n        ')
        text_result_layout.addWidget(self.result_text)
        self.tokens_tab = TokenResultTab(self.tr)
        self.error_table_tab = ErrorResultTab(self.tr)
        self.error_table_tab.set_main_window(self)
        self.syntax_error_tab = SyntaxErrorResultTab(self.tr)
        self.syntax_error_tab.set_main_window(self)
        self.quad_tab = QWidget()
        quad_layout = QVBoxLayout(self.quad_tab)
        self.quad_text = QTextEdit()
        self.quad_text.setReadOnly(True)
        self.quad_text.setStyleSheet('\n            QTextEdit {\n                background-color: #1e1e1e;\n                color: #ffffff;\n                border: 2px solid #FFA500;\n                border-radius: 5px;\n                padding: 5px;\n            }\n        ')
        quad_layout.addWidget(self.quad_text)
        self.poliz_tab = QWidget()
        poliz_layout = QVBoxLayout(self.poliz_tab)
        self.poliz_text = QTextEdit()
        self.poliz_text.setReadOnly(True)
        self.poliz_text.setStyleSheet('\n            QTextEdit {\n                background-color: #1e1e1e;\n                color: #ffffff;\n                border: 2px solid #FFA500;\n                border-radius: 5px;\n                padding: 5px;\n            }\n        ')
        poliz_layout.addWidget(self.poliz_text)
        self.regex_search_tab = RegexSearchTab(self)
        self.result_tabs.addTab(self.text_result_tab, self.tr('Текстовый вывод'))
        self.result_tabs.addTab(self.tokens_tab, self.tr('Лексемы'))
        self.result_tabs.addTab(self.error_table_tab, self.tr('Ошибки'))
        self.result_tabs.addTab(self.syntax_error_tab, self.tr('Синтаксис'))
        self.result_tabs.addTab(self.quad_tab, self.tr('Тетрады'))
        self.result_tabs.addTab(self.poliz_tab, self.tr('ПОЛИЗ'))
        self.result_tabs.addTab(self.regex_search_tab, self.tr('Regex Поиск'))
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.editor_tabs)
        splitter.addWidget(self.result_tabs)
        splitter.setSizes([400, 300])
        splitter.setStyleSheet('\n            QSplitter::handle {\n                background-color: #FFA500;\n                height: 3px;\n            }\n            QSplitter::handle:hover {\n                background-color: #FFB52E;\n            }\n        ')
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(splitter)
        self.setCentralWidget(central)
        self.add_new_editor_tab()
        self.create_menu()
        self.create_toolbar()
        self.create_status_bar()
        self.setWindowTitle(self.tr('Текстовый редактор с языковым процессором'))
        self.resize(1000, 700)
        self.setMinimumSize(600, 400)

    def create_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet('\n            QStatusBar {\n                background-color: #404040;\n                color: #FFA500;\n                border-top: 2px solid #FFA500;\n                font-weight: bold;\n            }\n        ')
        self.status_bar.showMessage(self.tr('Готов'))
        self.cursor_position_label = QLabel(self.tr('Строка: 1, Столбец: 1'))
        self.file_info_label = QLabel(self.tr('Новый файл'))
        self.encoding_label = QLabel(self.tr('UTF-8'))
        self.parser_type_label = QLabel('Lab 6: RD')
        self.parser_type_label.setStyleSheet('color: #FFA500; font-weight: bold; margin-right: 10px;')
        self.status_bar.addPermanentWidget(self.parser_type_label)
        self.status_bar.addPermanentWidget(self.cursor_position_label)
        self.status_bar.addPermanentWidget(self.file_info_label)
        self.status_bar.addPermanentWidget(self.encoding_label)

    def update_cursor_position(self):
        editor = self.get_current_editor()
        if not editor:
            self.cursor_position_label.setText(self.tr('Строка: -, Столбец: -'))
            return
        cursor = editor.code_editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self.cursor_position_label.setText(f"{self.tr('Строка:')} {line}, {self.tr('Столбец:')} {col}")

    def update_file_info(self, file_name):
        if file_name:
            self.file_info_label.setText(os.path.basename(file_name))
        else:
            self.file_info_label.setText(self.tr('Новый файл'))

    def get_current_editor(self):
        return self.editor_tabs.currentWidget()

    def add_new_editor_tab(self, file_name=None, content=''):
        new_tab = EditorTab()
        if content:
            new_tab.set_text(content)
        base_name = self.tr('Новый файл')
        tab_name = os.path.basename(file_name) if file_name else f'{base_name} {self.editor_tabs.count() + 1}'
        index = self.editor_tabs.addTab(new_tab, tab_name)
        self.editor_tabs.setCurrentIndex(index)
        if file_name:
            new_tab.current_file = file_name
        new_tab.code_editor.cursorPositionChanged.connect(self.update_cursor_position)
        new_tab.code_editor.textChanged.connect(self.on_tab_text_changed)
        return new_tab

    def on_tab_text_changed(self):
        index = self.editor_tabs.currentIndex()
        tab_text = self.editor_tabs.tabText(index)
        if not tab_text.endswith('*'):
            self.editor_tabs.setTabText(index, tab_text + '*')

    def close_editor_tab(self, index):
        if self.editor_tabs.count() <= 1:
            return
        tab = self.editor_tabs.widget(index)
        if tab.text_modified:
            reply = QMessageBox.question(self, self.tr('Сохранение'), self.tr('Сохранить изменения в документе?'), QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                self.save_current_file()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        self.editor_tabs.removeTab(index)

    def change_editor_font_size(self, delta):
        self.current_font_size = max(8, min(72, self.current_font_size + delta))
        editor = self.get_current_editor()
        if editor:
            font = editor.code_editor.font()
            font.setPointSize(self.current_font_size)
            editor.code_editor.setFont(font)
            editor.code_editor.update_line_number_area_width()
        self.status_bar.showMessage(f"{self.tr('Размер шрифта редактора:')} {self.current_font_size}")

    def change_result_font_size(self, delta):
        self.result_font_size = max(8, min(72, self.result_font_size + delta))
        font = self.result_text.font()
        font.setPointSize(self.result_font_size)
        self.result_text.setFont(font)
        self.regex_search_tab.change_font_size(delta)
        self.status_bar.showMessage(f"{self.tr('Размер шрифта результатов:')} {self.result_font_size}")

    def start_regex_search(self):
        self.result_tabs.setCurrentWidget(self.regex_search_tab)
        self.regex_search_tab.perform_search()

    def create_menu(self):
        menubar = self.menuBar()
        menubar.clear()
        menubar.setStyleSheet('\n            QMenuBar {\n                background-color: #404040;\n                color: #ffffff;\n                border-bottom: 2px solid #FFA500;\n            }\n            QMenuBar::item:selected {\n                background-color: #FFA500;\n                color: #000000;\n            }\n            QMenu {\n                background-color: #404040;\n                color: #ffffff;\n                border: 2px solid #FFA500;\n            }\n            QMenu::item:selected {\n                background-color: #FFA500;\n                color: #000000;\n            }\n        ')
        file_menu = menubar.addMenu(self.tr('Файл'))
        new_act = QAction(self.tr('Создать'), self)
        new_act.setShortcut('Ctrl+N')
        new_act.triggered.connect(lambda: self.add_new_editor_tab())
        file_menu.addAction(new_act)
        open_act = QAction(self.tr('Открыть'), self)
        open_act.setShortcut('Ctrl+O')
        open_act.triggered.connect(self.open_file)
        file_menu.addAction(open_act)
        save_act = QAction(self.tr('Сохранить'), self)
        save_act.setShortcut('Ctrl+S')
        save_act.triggered.connect(self.save_file)
        file_menu.addAction(save_act)
        save_as_act = QAction(self.tr('Сохранить как'), self)
        save_as_act.setShortcut('Ctrl+Shift+S')
        save_as_act.triggered.connect(self.save_as_file)
        file_menu.addAction(save_as_act)
        file_menu.addSeparator()
        exit_act = QAction(self.tr('Выход'), self)
        exit_act.setShortcut('Ctrl+Q')
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)
        edit_menu = menubar.addMenu(self.tr('Правка'))
        undo_act = QAction(self.tr('Отменить'), self)
        undo_act.setShortcut('Ctrl+Z')
        undo_act.triggered.connect(lambda: self.get_current_editor().code_editor.undo() if self.get_current_editor() else None)
        edit_menu.addAction(undo_act)
        redo_act = QAction(self.tr('Повторить'), self)
        redo_act.setShortcut('Ctrl+Y')
        redo_act.triggered.connect(lambda: self.get_current_editor().code_editor.redo() if self.get_current_editor() else None)
        edit_menu.addAction(redo_act)
        edit_menu.addSeparator()
        cut_act = QAction(self.tr('Вырезать'), self)
        cut_act.setShortcut('Ctrl+X')
        cut_act.triggered.connect(lambda: self.get_current_editor().code_editor.cut() if self.get_current_editor() else None)
        edit_menu.addAction(cut_act)
        copy_act = QAction(self.tr('Копировать'), self)
        copy_act.setShortcut('Ctrl+C')
        copy_act.triggered.connect(lambda: self.get_current_editor().code_editor.copy() if self.get_current_editor() else None)
        edit_menu.addAction(copy_act)
        paste_act = QAction(self.tr('Вставить'), self)
        paste_act.setShortcut('Ctrl+V')
        paste_act.triggered.connect(lambda: self.get_current_editor().code_editor.paste() if self.get_current_editor() else None)
        edit_menu.addAction(paste_act)
        del_act = QAction(self.tr('Удалить'), self)
        del_act.setShortcut('Del')
        del_act.triggered.connect(lambda: self.get_current_editor().code_editor.textCursor().removeSelectedText() if self.get_current_editor() else None)
        edit_menu.addAction(del_act)
        sel_all_act = QAction(self.tr('Выделить все'), self)
        sel_all_act.setShortcut('Ctrl+A')
        sel_all_act.triggered.connect(lambda: self.get_current_editor().code_editor.selectAll() if self.get_current_editor() else None)
        edit_menu.addAction(sel_all_act)
        view_menu = menubar.addMenu(self.tr('Вид'))
        inc_ed_font = QAction(self.tr('Увеличить шрифт редактора'), self)
        inc_ed_font.setShortcut('Ctrl+=')
        inc_ed_font.triggered.connect(lambda: self.change_editor_font_size(1))
        view_menu.addAction(inc_ed_font)
        dec_ed_font = QAction(self.tr('Уменьшить шрифт редактора'), self)
        dec_ed_font.setShortcut('Ctrl+-')
        dec_ed_font.triggered.connect(lambda: self.change_editor_font_size(-1))
        view_menu.addAction(dec_ed_font)
        view_menu.addSeparator()
        inc_res_font = QAction(self.tr('Увеличить шрифт результатов'), self)
        inc_res_font.setShortcut('Ctrl+Shift+=')
        inc_res_font.triggered.connect(lambda: self.change_result_font_size(1))
        view_menu.addAction(inc_res_font)
        dec_res_font = QAction(self.tr('Уменьшить шрифт результатов'), self)
        dec_res_font.setShortcut('Ctrl+Shift+-')
        dec_res_font.triggered.connect(lambda: self.change_result_font_size(-1))
        view_menu.addAction(dec_res_font)
        text_menu = menubar.addMenu(self.tr('Текст'))
        text_items = ['Постановка задачи', 'Грамматика', 'Классификация грамматики', 'Метод анализа', 'Тестовый пример', 'Список литературы', 'Исходный код программы']
        for item in text_items:
            act = QAction(self.tr(item), self)
            act.triggered.connect(lambda _, t=item: self.show_text_info(t))
            text_menu.addAction(act)
        parser_menu = menubar.addMenu('Parser')
        rd_act = QAction('Recursive Descent (Lab 6)', self)
        rd_act.setEnabled(False)
        parser_menu.addAction(rd_act)
        run_menu = menubar.addMenu(self.tr('Пуск'))
        run_act = QAction(self.tr('Запуск анализатора'), self)
        run_act.setShortcut('F5')
        run_act.triggered.connect(self.start_analyzer)
        run_menu.addAction(run_act)
        regex_run_act = QAction(self.tr('Поиск по Regex'), self)
        regex_run_act.setShortcut('Ctrl+F5')
        regex_run_act.triggered.connect(self.start_regex_search)
        run_menu.addAction(regex_run_act)
        show_ast_act = QAction(self.tr('Показать AST'), self)
        show_ast_act.setShortcut('F6')
        show_ast_act.triggered.connect(self.show_ast_graph)
        run_menu.addAction(show_ast_act)
        help_menu = menubar.addMenu(self.tr('Справка'))
        help_act = QAction(self.tr('Вызов справки'), self)
        help_act.setShortcut('F1')
        help_act.triggered.connect(self.show_help)
        help_menu.addAction(help_act)
        about_act = QAction(self.tr('О программе'), self)
        about_act.triggered.connect(self.show_about)
        help_menu.addAction(about_act)
        lang_menu = menubar.addMenu(self.tr('Язык'))
        ru_act = QAction(self.tr('Русский'), self)
        ru_act.triggered.connect(lambda: self.change_language('ru'))
        lang_menu.addAction(ru_act)
        en_act = QAction(self.tr('English'), self)
        en_act.triggered.connect(lambda: self.change_language('en'))
        lang_menu.addAction(en_act)

    def create_toolbar(self):
        self.toolbar = self.addToolBar(self.tr('Инструменты'))
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.toolbar.setStyleSheet('\n            QToolBar {\n                background-color: #404040;\n                border-bottom: 2px solid #FFA500;\n                spacing: 5px;\n            }\n            QToolButton {\n                background-color: #505050;\n                color: #ffffff;\n                border: 1px solid #FFA500;\n                border-radius: 3px;\n                padding: 5px;\n                min-width: 60px;\n            }\n            QToolButton:hover {\n                background-color: #FFA500;\n                color: #000000;\n            }\n            QToolButton:pressed {\n                background-color: #FFB52E;\n            }\n        ')
        self.update_toolbar()

    def update_toolbar(self):
        self.toolbar.clear()

        def create_icon(name):
            if name == 'system-run':
                pixmap = QPixmap(24, 24)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setBrush(QColor(255, 165, 0))
                painter.setPen(Qt.PenStyle.NoPen)
                points = [QPoint(6, 4), QPoint(20, 12), QPoint(6, 20)]
                painter.drawPolygon(*points)
                painter.end()
                return QIcon(pixmap)
            elif name == 'help-contents':
                pixmap = QPixmap(24, 24)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setBrush(QColor(255, 165, 0))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(4, 4, 16, 16)
                painter.setPen(QColor(255, 255, 255))
                painter.setFont(QFont('Arial', 12, QFont.Weight.Bold))
                painter.drawText(8, 18, '?')
                painter.end()
                return QIcon(pixmap)
            elif name == 'help-about':
                pixmap = QPixmap(24, 24)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setBrush(QColor(255, 165, 0))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(4, 4, 16, 16)
                painter.setPen(QColor(255, 255, 255))
                painter.setFont(QFont('Arial', 12, QFont.Weight.Bold))
                painter.drawText(11, 18, 'i')
                painter.end()
                return QIcon(pixmap)
            elif name == 'ast-tree':
                pixmap = QPixmap(24, 24)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setPen(QPen(QColor(255, 165, 0), 2))
                painter.drawLine(12, 4, 6, 12)
                painter.drawLine(12, 4, 18, 12)
                painter.drawLine(6, 12, 4, 20)
                painter.drawLine(6, 12, 10, 20)
                painter.drawLine(18, 12, 14, 20)
                painter.drawLine(18, 12, 20, 20)
                painter.end()
                return QIcon(pixmap)
            else:
                return QIcon.fromTheme(name)
        actions = [('document-new', self.tr('Создать'), lambda: self.add_new_editor_tab()), ('document-open', self.tr('Открыть'), self.open_file), ('document-save', self.tr('Сохранить'), self.save_file), None, ('edit-undo', self.tr('Отменить'), lambda: self.get_current_editor().code_editor.undo() if self.get_current_editor() else None), ('edit-redo', self.tr('Повторить'), lambda: self.get_current_editor().code_editor.redo() if self.get_current_editor() else None), None, ('edit-copy', self.tr('Копировать'), lambda: self.get_current_editor().code_editor.copy() if self.get_current_editor() else None), ('edit-cut', self.tr('Вырезать'), lambda: self.get_current_editor().code_editor.cut() if self.get_current_editor() else None), ('edit-paste', self.tr('Вставить'), lambda: self.get_current_editor().code_editor.paste() if self.get_current_editor() else None), None, ('system-run', self.tr('Запуск'), self.start_analyzer), ('system-run', self.tr('Regex'), self.start_regex_search), ('ast-tree', self.tr('Показать AST'), self.show_ast_graph), ('help-contents', self.tr('Справка'), self.show_help), ('help-about', self.tr('О программе'), self.show_about)]
        for item in actions:
            if item is None:
                self.toolbar.addSeparator()
                continue
            icon_name, text, func = item
            icon = create_icon(icon_name)
            act = QAction(icon, text, self)
            act.triggered.connect(func)
            self.toolbar.addAction(act)

    def retranslateUi(self):
        self.setWindowTitle(self.tr('Текстовый редактор с языковым процессором'))
        menubar = self.menuBar()
        menubar.clear()
        self.create_menu()
        self.result_tabs.setTabText(0, self.tr('Текстовый вывод'))
        self.result_tabs.setTabText(1, self.tr('Лексемы'))
        self.result_tabs.setTabText(2, self.tr('Ошибки'))
        self.result_tabs.setTabText(3, self.tr('Синтаксис'))
        self.result_tabs.setTabText(4, self.tr('Тетрады'))
        self.result_tabs.setTabText(5, self.tr('ПОЛИЗ'))
        self.result_tabs.setTabText(6, self.tr('Regex Поиск'))
        self.tokens_tab.update_headers()
        self.error_table_tab.update_headers()
        self.syntax_error_tab.set_language(self.translator.lang)
        self.regex_search_tab.retranslateUi()
        self.status_bar.showMessage(self.tr('Готов'))
        self.update_cursor_position()
        self.update_file_info(None)
        for i in range(self.editor_tabs.count()):
            tab = self.editor_tabs.widget(i)
            if tab and (not tab.current_file):
                current_text = self.editor_tabs.tabText(i).rstrip('*')
                if current_text.startswith('Новый файл') or current_text.startswith('Untitled'):
                    base_name = self.tr('Новый файл')
                    if current_text == 'Новый файл' or current_text == 'Untitled':
                        new_text = base_name
                    else:
                        try:
                            num = current_text.split()[-1]
                            new_text = f'{base_name} {num}'
                        except:
                            new_text = base_name
                    if self.editor_tabs.tabText(i).endswith('*'):
                        new_text += '*'
                    self.editor_tabs.setTabText(i, new_text)
        self.update_toolbar()

    def change_language(self, lang):
        self.translator.set_language(lang)
        self.retranslateUi()
        self.tokens_tab.set_language(lang)
        self.error_table_tab.set_language(lang)
        self.syntax_error_tab.set_language(lang)
        tab = self.get_current_editor()
        if tab and tab.get_text().strip():
            self.start_analyzer()
        QMessageBox.information(self, self.tr('Смена языка'), self.tr('Язык изменен на русский') if lang == 'ru' else self.tr('Язык изменен на английский'))

    def open_file_with_path(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            self.add_new_editor_tab(file_path, content)
            self.status_bar.showMessage(f"{self.tr('Открыт файл:')} {file_path}")
            self.update_file_info(file_path)
        except Exception as e:
            QMessageBox.critical(self, self.tr('Ошибка'), f"{self.tr('Не удалось открыть файл:')} {str(e)}")

    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, self.tr('Открыть файл'), '', 'Текстовые файлы (*.txt);;Все файлы (*)')
        if file_name:
            self.open_file_with_path(file_name)

    def save_current_file(self):
        tab = self.get_current_editor()
        if not tab:
            return
        if tab.current_file:
            try:
                with open(tab.current_file, 'w', encoding='utf-8') as file:
                    file.write(tab.get_text())
                tab.text_modified = False
                idx = self.editor_tabs.currentIndex()
                title = self.editor_tabs.tabText(idx)
                if title.endswith('*'):
                    self.editor_tabs.setTabText(idx, title[:-1])
                self.status_bar.showMessage(f"{self.tr('Файл сохранен:')} {tab.current_file}")
            except Exception as e:
                QMessageBox.critical(self, self.tr('Ошибка'), f"{self.tr('Не удалось сохранить файл:')} {str(e)}")
        else:
            self.save_as_file()

    def save_file(self):
        self.save_current_file()

    def save_as_file(self):
        file_name, _ = QFileDialog.getSaveFileName(self, self.tr('Сохранить как'), '', 'Текстовые файлы (*.txt);;Все файлы (*)')
        if file_name:
            tab = self.get_current_editor()
            if tab:
                tab.current_file = file_name
                self.save_current_file()
                self.editor_tabs.setTabText(self.editor_tabs.currentIndex(), os.path.basename(file_name))
                self.update_file_info(file_name)

    def show_text_info(self, text_type):
        info_texts = {
            'Постановка задачи': (
                'Реализовать лексер и синтаксический анализатор рекурсивного спуска '
                'для арифметических выражений, а также построение тетрад и ПОЛИЗ.'
            ),
            'Грамматика': (
                'E -> T A\n'
                'A -> eps | + T A | - T A\n'
                'T -> F B\n'
                'B -> eps | * F B | / F B | % F B\n'
                'F -> num | id | (E)\n'
                'id -> letter {letter | digit}\n'
                'num -> digit {digit}'
            ),
            'Классификация грамматики': 'Грамматика является КС-грамматикой с явной приоритетностью через уровни E/T/F.',
            'Метод анализа': 'Рекурсивный спуск для синтаксического анализа; алгоритм Дейкстры для ПОЛИЗ.',
            'Тестовый пример': '2 + 3 * (4 - 1)',
            'Список литературы': (
                '1. Ахо А., Сети Р., Ульман Дж. Компиляторы: принципы, технологии и инструменты.\n'
                '2. Можгинский А.Ю. Лексический анализ.'
            ),
            'Исходный код программы': 'main.py, lab6_expression_analyzer.py, translator.py, editor_tab.py, result_tabs.py',
        }
        QMessageBox.information(self, self.tr(text_type), info_texts[text_type])

    def go_to_position(self, line, col, error_index=-1):
        editor = self.get_current_editor()
        if not editor:
            return
        cursor = editor.code_editor.textCursor()
        block = editor.code_editor.document().findBlockByNumber(line - 1)
        if not block.isValid():
            return
        cursor.setPosition(block.position())
        target_pos = block.position() + col - 1
        if target_pos > len(editor.code_editor.toPlainText()):
            target_pos = block.position()
        cursor.setPosition(target_pos, QTextCursor.MoveMode.MoveAnchor)
        editor.code_editor.setTextCursor(cursor)
        editor.code_editor.setFocus()
        editor.code_editor.centerCursor()
        if error_index >= 0:
            editor.error_highlighter.active_error_index = error_index
            editor.error_highlighter.rehighlight()

    def start_analyzer(self):
        tab = self.get_current_editor()
        if not tab:
            return
        text = tab.get_text()
        self.tokens_tab.clear_results()
        self.error_table_tab.clear_results()
        self.syntax_error_tab.clear_results()
        self.quad_text.clear()
        self.poliz_text.clear()
        tab.error_highlighter.clear_errors()
        if not text.strip():
            self.result_text.setPlainText(self.tr('Текст для анализа отсутствует.'))
            return

        tokens, lex_errors = self.expr_lexer.tokenize(text)
        current_lang = self.translator.lang
        type_map = {
            'NUM': ('ЦЕЛОЕ_ЧИСЛО', 'INTEGER'),
            'ID': ('ИДЕНТИФИКАТОР', 'IDENTIFIER'),
            'OP': ('ОПЕРАТОР', 'OPERATOR'),
            'LPAREN': ('СКОБКА', 'PAREN'),
            'RPAREN': ('СКОБКА', 'PAREN'),
            'ERROR': ('ОШИБКА', 'ERROR'),
        }
        code_map = {'NUM': 1, 'ID': 2, 'OP': 10, 'LPAREN': 11, 'RPAREN': 11, 'ERROR': 99}

        token_count = len([t for t in tokens if t.kind != 'EOF'])
        if current_lang == 'ru':
            tokens_text = '=== РЕЗУЛЬТАТЫ ЛЕКСИЧЕСКОГО АНАЛИЗА ===\n\n'
        else:
            tokens_text = '=== LEXICAL ANALYSIS RESULTS ===\n\n'
        tokens_text += f"{self.tr('Найдено лексем:')} {token_count}\n"
        tokens_text += f"{self.tr('Найдено ошибок:')} {len(lex_errors)}\n\n"
        tokens_text += (
            'Грамматика: E->TA; A->eps|+TA|-TA; T->FB; B->eps|*FB|/FB|%FB; F->num|id|(E)\n'
        )

        all_errors = []
        for token in tokens:
            if token.kind == 'EOF':
                continue
            code = code_map.get(token.kind, 99)
            kind_ru, kind_en = type_map.get(token.kind, (token.kind, token.kind))
            kind_name = kind_ru if current_lang == 'ru' else kind_en
            start = token.pos + 1
            end = token.pos + len(token.value)
            if current_lang == 'ru':
                location = f'строка 1, {start}-{end}'
            else:
                location = f'line 1, {start}-{end}'
            self.tokens_tab.add_result(code, kind_name, token.value, location)

        for err in lex_errors:
            start = err.pos + 1
            if current_lang == 'ru':
                loc = f'строка 1, позиция {start}'
                syn_loc = f'строка 1, позиция {start}'
            else:
                loc = f'line 1, position {start}'
                syn_loc = f'line 1, position {start}'
            self.error_table_tab.add_error(
                'Lexical' if current_lang == 'en' else 'Лексическая',
                err.message,
                loc,
                err.message,
            )
            self.syntax_error_tab.add_row('LEX', syn_loc, err.message)
            all_errors.append({'type': 'Lexical', 'fragment': err.message, 'location': loc, 'description': err.message, 'line': 1, 'col': start})

        if lex_errors:
            self.syntax_error_tab.set_total(len(lex_errors))
            stop_msg = (
                '\n\nЕсть лексические ошибки. Построение тетрад и ПОЛИЗ остановлено.'
                if current_lang == 'ru'
                else '\n\nLexical errors found. Quad and RPN generation stopped.'
            )
            self.result_text.setPlainText(tokens_text + stop_msg)
            self.quad_text.setPlainText(
                'Тетрады не строятся при лексических ошибках.'
                if current_lang == 'ru'
                else 'Quads are not generated when lexical errors exist.'
            )
            self.poliz_text.setPlainText(
                'ПОЛИЗ не строится при лексических ошибках.'
                if current_lang == 'ru'
                else 'RPN is not generated when lexical errors exist.'
            )
            tab.error_highlighter.set_errors(all_errors)
            self.status_bar.showMessage(
                f"{self.tr('Анализ завершен')}. {self.tr('Лексем:')} {token_count}, "
                f"{self.tr('Ошибок:')} {len(lex_errors)}"
            )
            return

        parser = RecursiveDescentParser(tokens)
        parser.parse()
        parse_errors = parser.errors
        for err in parse_errors:
            pos = err.pos + 1
            if current_lang == 'ru':
                loc = f'строка 1, позиция {pos}'
            else:
                loc = f'line 1, position {pos}'
            self.syntax_error_tab.add_row('SYN', loc, err.message)
            self.error_table_tab.add_error(
                'Syntax' if current_lang == 'en' else 'Синтаксическая',
                err.message,
                loc,
                err.message,
            )
            all_errors.append({'type': 'Syntax', 'fragment': err.message, 'location': loc, 'description': err.message, 'line': 1, 'col': pos})
        self.syntax_error_tab.set_total(len(parse_errors))

        if current_lang == 'ru':
            syn_block = '\n\n=== СИНТАКСИЧЕСКИЙ АНАЛИЗ ===\n'
        else:
            syn_block = '\n\n=== SYNTAX ANALYSIS ===\n'
        if parse_errors:
            syn_block += f"{'Найдено синтаксических ошибок' if current_lang == 'ru' else 'Syntax errors found'}: {len(parse_errors)}"
            self.quad_text.setPlainText(
                'Тетрады не строятся при синтаксических ошибках.'
                if current_lang == 'ru'
                else 'Quads are not generated when syntax errors exist.'
            )
            self.poliz_text.setPlainText(
                'ПОЛИЗ не строится при синтаксических ошибках.'
                if current_lang == 'ru'
                else 'RPN is not generated when syntax errors exist.'
            )
            self.result_text.setPlainText(tokens_text + syn_block)
            tab.error_highlighter.set_errors(all_errors)
            self.status_bar.showMessage(
                f"{self.tr('Анализ завершен')}. {self.tr('Лексем:')} {token_count}, "
                f"{self.tr('Ошибок:')} {len(all_errors)}"
            )
            return

        syn_block += (
            'Синтаксических ошибок не обнаружено.'
            if current_lang == 'ru'
            else 'No syntax errors found.'
        )
        self.result_text.setPlainText(tokens_text + syn_block)

        quads_lines = ['N   op   arg1       arg2       result']
        for idx, (op, arg1, arg2, res) in enumerate(parser.quads, 1):
            quads_lines.append(f'{idx:<3} {op:<4} {arg1:<10} {arg2:<10} {res:<8}')
        if len(quads_lines) == 1:
            quads_lines.append(
                'Операций нет (одно значение без операторов).'
                if current_lang == 'ru'
                else 'No operations (single value without operators).'
            )
        self.quad_text.setPlainText('\n'.join(quads_lines))

        only_int_expr = all(t.kind in {'NUM', 'OP', 'LPAREN', 'RPAREN', 'EOF'} for t in tokens)
        if not only_int_expr:
            self.poliz_text.setPlainText(
                'ПОЛИЗ строится только для выражений из целых чисел (без идентификаторов).'
                if current_lang == 'ru'
                else 'RPN is built only for integer expressions (no identifiers).'
            )
        else:
            try:
                postfix = to_postfix(tokens)
                value = eval_postfix(postfix)
                self.poliz_text.setPlainText(f"ПОЛИЗ: {' '.join(postfix)}\nЗначение: {value}")
            except Exception as ex:
                self.poliz_text.setPlainText(
                    f'Ошибка построения/вычисления ПОЛИЗ: {ex}'
                    if current_lang == 'ru'
                    else f'RPN build/eval error: {ex}'
                )

        tab.error_highlighter.set_errors(all_errors)
        self.status_bar.showMessage(
            f"{self.tr('Анализ завершен')}. {self.tr('Лексем:')} {token_count}, "
            f"{self.tr('Ошибок:')} {len(all_errors)}"
        )

    def show_ast_graph(self):
        QMessageBox.information(
            self,
            self.tr('AST'),
            self.tr(
                'Для лабораторной 6 отображаются тетрады и ПОЛИЗ. '
                'Графическое AST относится к лабораторной работе 5.'
            ),
        )

    def show_help(self):
        help_text = self.tr('=== СПРАВКА ПО ТЕКСТОВОМУ РЕДАКТОРУ ===') + '\n\n' + self.tr('Функции меню "Файл":') + '\n' + '- ' + self.tr('Создать') + ': ' + self.tr('Создать новый документ (Ctrl+N)') + '\n' + '- ' + self.tr('Открыть') + ': ' + self.tr('Открыть существующий текстовый файл (Ctrl+O)') + '\n' + '- ' + self.tr('Сохранить') + ': ' + self.tr('Сохранить текущий документ (Ctrl+S)') + '\n' + '- ' + self.tr('Сохранить как') + ': ' + self.tr('Сохранить документ под новым именем (Ctrl+Shift+S)') + '\n' + '- ' + self.tr('Выход') + ': ' + self.tr('Закрыть программу (Ctrl+Q)') + '\n\n' + self.tr('Функции меню "Правка":') + '\n' + '- ' + self.tr('Отменить') + ': Ctrl+Z\n' + '- ' + self.tr('Повторить') + ': Ctrl+Y\n' + '- ' + self.tr('Вырезать') + ': Ctrl+X\n' + '- ' + self.tr('Копировать') + ': Ctrl+C\n' + '- ' + self.tr('Вставить') + ': Ctrl+V\n' + '- ' + self.tr('Удалить') + ': Del\n' + '- ' + self.tr('Выделить все') + ': Ctrl+A\n\n' + self.tr('Функции меню "Вид":') + '\n' + '- ' + self.tr('Увеличить/уменьшить шрифт редактора') + ' (Ctrl+= / Ctrl+-)\n' + '- ' + self.tr('Увеличить/уменьшить шрифт результатов') + ' (Ctrl+Shift+= / Ctrl+Shift+-)\n\n' + self.tr('Функции меню "Пуск":') + '\n' + '- ' + self.tr('Запуск анализатора') + ': F5 (лексика, синтаксис, тетрады, ПОЛИЗ)\n' + '- ' + self.tr('Поиск по Regex') + ': Ctrl+F5\n\n' + self.tr('Дополнительно:') + '\n' + '- ' + self.tr('Навигация по ошибкам: клик на ошибке в таблице') + '\n' + '- ' + self.tr('Выделение ошибок: красное подчеркивание в тексте') + '\n' + '- ' + self.tr('Поиск по Regex: вкладка "Regex Поиск"') + '\n' + '- ' + 'Вкладки «Тетрады» и «ПОЛИЗ» после успешного анализа (F5)\n'
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr('Справка'))
        dlg.resize(650, 550)
        dlg.setStyleSheet('\n            QDialog { background-color: #2b2b2b; }\n            QTextEdit {\n                background-color: #1e1e1e;\n                color: #ffffff;\n                border: 2px solid #FFA500;\n                border-radius: 5px;\n                padding: 10px;\n            }\n            QPushButton {\n                background-color: #FFA500;\n                color: #000000;\n                border: none;\n                padding: 8px;\n                border-radius: 3px;\n                font-weight: bold;\n            }\n            QPushButton:hover { background-color: #FFB52E; }\n        ')
        lay = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(help_text)
        btn = QPushButton(self.tr('Закрыть'))
        btn.clicked.connect(dlg.close)
        lay.addWidget(te)
        lay.addWidget(btn)
        dlg.exec()

    def show_about(self):
        QMessageBox.about(
            self,
            self.tr('О программе'),
            self.tr('Текстовый редактор с языковым процессором')
            + '\n\n'
            + self.tr('Версия: 6.0 (Internal Representation: Quads + RPN)')
            + '\n\n'
            + self.tr('Автор: Васильев Антон Романович')
            + '\n'
            + self.tr('ЛР6: Тетрады и ПОЛИЗ для арифметических выражений')
            + '\n\n'
            + self.tr('(c) 2026'),
        )

    def closeEvent(self, event):
        for i in range(self.editor_tabs.count()):
            tab = self.editor_tabs.widget(i)
            if tab.text_modified:
                reply = QMessageBox.question(self, self.tr('Сохранение'), self.tr('Есть несохраненные изменения. Закрыть программу?'), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    event.ignore()
                    return
        event.accept()

def main():
    suppress_console_output()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(43, 43, 43))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(64, 64, 64))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Highlight, QColor(255, 165, 0))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)
    window = TextEditor()
    window.show()
    sys.exit(app.exec())
if __name__ == '__main__':
    main()
