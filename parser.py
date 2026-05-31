from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from scanner import Token

@dataclass
class SyntaxErrorRecord:
    fragment: str
    line: int
    col: int
    message: str

    def location_ru(self) -> str:
        return f'строка {self.line}, позиция {self.col}'

    def location_en(self) -> str:
        return f'line {self.line}, position {self.col}'

@dataclass
class ParseResult:
    ok: bool
    errors: List[SyntaxErrorRecord] = field(default_factory=list)

class Parser:

    def __init__(self, tokens: List['Token'], lang: str='ru'):
        self.tokens = self._filter_tokens(tokens)
        self.pos = 0
        self.errors: List[SyntaxErrorRecord] = []
        self.lang = lang if lang in ('ru', 'en') else 'ru'
        self.current_line = 1

    def _m(self, ru: str, en: str) -> str:
        return en if self.lang == 'en' else ru

    @staticmethod
    def _filter_tokens(tokens: List['Token']) -> List['Token']:
        out = []
        for t in tokens:
            if t.token_type in ('DELIMITER', 'COMMENT'):
                continue
            out.append(t)
        return out

    def _current(self) -> Optional['Token']:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _advance(self):
        if self._current():
            self.current_line = self._current().line
        self.pos += 1

    def _fragment(self, t: Optional['Token']) -> str:
        if not t:
            return 'EOF'
        raw = getattr(t, 'raw_lexeme', t.value)
        return raw if len(raw) <= 32 else raw[:29] + '...'

    def _add_error(self, fragment: str, line: int, col: int, message: str):
        self.errors.append(SyntaxErrorRecord(fragment=fragment, line=line, col=col, message=message))

    def _check_value(self, value: str) -> bool:
        t = self._current()
        return t is not None and t.value == value

    def _is_keyword(self, word: str) -> bool:
        t = self._current()
        return t is not None and t.token_type == 'KEYWORD' and (t.value == word)

    def _is_identifier(self) -> bool:
        t = self._current()
        return t is not None and t.token_type == 'IDENTIFIER'

    def _is_number(self) -> bool:
        t = self._current()
        return t is not None and t.token_type in ('INTEGER', 'FLOAT')

    def _report_current_error(self, message: str):
        t = self._current()
        if t is None:
            self._add_error('EOF', self.current_line, 1, message)
            return
        self._add_error(self._fragment(t), t.line, t.start, message)

    def _error_symbol(self, token) -> str:
        text = self._fragment(token)
        if "'" in text:
            parts = text.split("'")
            if len(parts) >= 2 and parts[1]:
                return parts[1]
        return text

    def _constructor_fragment(self, token) -> str:
        text = self._fragment(token)
        if token is not None and token.token_type == 'IDENTIFIER':
            prefix = ''
            for ch in text:
                if ch.isalpha() or ch == '_':
                    prefix += ch
                else:
                    break
            if prefix and prefix != text:
                return prefix
        return text

    def _constructor_has_glued_argument(self, token) -> bool:
        if token is None:
            return False
        text = self._fragment(token)
        if token.token_type == 'IDENTIFIER' and any((ch.isdigit() for ch in text)):
            return True
        return self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].token_type == 'ERROR' and self._fragment(self.tokens[self.pos + 1]).startswith('.')

    def _has_closing_paren_before_semicolon(self) -> bool:
        idx = self.pos
        while idx < len(self.tokens) and self.tokens[idx].value != ';':
            if self.tokens[idx].value == ')':
                return True
            idx += 1
        return False

    def _glued_argument_info(self, token) -> tuple[str, int]:
        if token is None:
            return ('EOF', 1)
        text = self._fragment(token)
        if token.token_type == 'IDENTIFIER':
            prefix_len = 0
            for ch in text:
                if ch.isalpha() or ch == '_':
                    prefix_len += 1
                else:
                    break
            suffix = text[prefix_len:]
            if suffix:
                if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].token_type == 'ERROR' and self._fragment(self.tokens[self.pos + 1]).startswith('.'):
                    suffix += self._fragment(self.tokens[self.pos + 1])
                return (suffix, token.start + prefix_len)
        return (self._fragment(token), token.start)

    def _is_number_text(self, text: str) -> bool:
        return re.fullmatch(r'-?\d+(\.\d+)?', text) is not None

    def _missing_comma_after_glued_argument(self) -> Optional['Token']:
        idx = self.pos + 1
        if idx < len(self.tokens) and self.tokens[idx].token_type == 'ERROR' and self._fragment(self.tokens[idx]).startswith('.'):
            idx += 1
        if idx < len(self.tokens) and self.tokens[idx].token_type in ('INTEGER', 'FLOAT', 'ERROR'):
            if self.tokens[idx].value not in (')', ';'):
                return self.tokens[idx]
        return None

    def parse(self) -> ParseResult:
        self.errors = []
        self.pos = 0
        self.current_line = 1
        if not self.tokens:
            self._add_error('EOF', 1, 1, self._m('Пустой ввод', 'Empty input'))
            return ParseResult(ok=False, errors=list(self.errors))
        while self._current() is not None:
            if self.pos > 0 and self.tokens[self.pos - 1].value == ';' and (self._current().token_type != 'KEYWORD' or self._current().value != 'val'):
                self._report_current_error(self._m('Некорректный фрагмент после завершенного объявления', 'Invalid fragment after completed declaration'))
                self._advance()
                continue
            self._parse_complex_declaration()
        return ParseResult(ok=len(self.errors) == 0, errors=list(self.errors))

    def _sync_to_semicolon_or_eof(self, expect_semicolon: bool=False):
        found_semicolon = False
        while self._current() is not None and (not self._check_value(';')):
            self._advance()
        if self._check_value(';'):
            found_semicolon = True
            self._advance()
        if expect_semicolon and (not found_semicolon):
            last = self.tokens[-1] if self.tokens else None
            if last is None:
                self._add_error('EOF', self.current_line, 1, self._m("Ожидалась ';' в конце объявления", "Expected ';' at end of declaration"))
            else:
                self._add_error('EOF', last.line, last.end + 1, self._m("Ожидалась ';' в конце объявления", "Expected ';' at end of declaration"))

    def _sync_after_declaration_error(self, expect_semicolon: bool=False):
        self._sync_to_semicolon_or_eof(expect_semicolon=expect_semicolon)
        while self._current() is not None and (not self._is_keyword('val')):
            self._advance()

    def _recover_to_identifier_before_assign(self):
        pass
        idx = self.pos + 1
        while idx < len(self.tokens):
            tok = self.tokens[idx]
            if tok.value == ';':
                return
            if tok.value == '=':
                self.pos = idx
                return
            if tok.token_type == 'IDENTIFIER':
                self.pos = idx
                return
            idx += 1

    def _recover_to_lparen_or_semicolon(self):
        while self._current() is not None and (not (self._check_value('(') or self._check_value(';'))):
            self._advance()

    def _recover_to_any(self, values: set[str]):
        while self._current() is not None and self._current().value not in values:
            self._advance()

    def _recover_to_assign_or_semicolon(self):
        self._recover_to_any({'=', ';'})

    def _recover_to_complex_or_lparen_or_semicolon(self) -> int:
        skipped = 0
        while self._current() is not None:
            if self._check_value(';') or self._check_value('('):
                return skipped
            if self._is_keyword('Complex'):
                return skipped
            if self._looks_like_constructor_candidate():
                return skipped
            self._advance()
            skipped += 1
        return skipped

    def _looks_like_constructor_candidate(self) -> bool:
        t = self._current()
        if t is None or t.token_type not in ('IDENTIFIER', 'ERROR'):
            return False
        if t.value.startswith('Недопустимый') or t.value.startswith('Invalid'):
            return False
        if not any((ch.isalpha() for ch in self._fragment(t))):
            return False
        idx = self.pos + 1
        while idx < len(self.tokens) and self.tokens[idx].value != ';':
            if self.tokens[idx].value == '(':
                return True
            idx += 1
        return False

    def _expect_keyword(self, word: str, message_ru: str, message_en: str) -> bool:
        if self._is_keyword(word):
            self._advance()
            return True
        self._report_current_error(self._m(message_ru, message_en))
        return False

    def _expect_identifier(self) -> bool:
        if self._is_identifier():
            self._advance()
            return True
        self._report_current_error(self._m('Ожидался идентификатор', 'Expected identifier'))
        return False

    def _expect_value(self, value: str, message_ru: str, message_en: str) -> bool:
        if self._check_value(value):
            self._advance()
            return True
        self._report_current_error(self._m(message_ru, message_en))
        return False

    def _is_number_or_identifier(self) -> bool:
        t = self._current()
        return t is not None and t.token_type in ('INTEGER', 'FLOAT', 'IDENTIFIER')

    def _expect_number(self, which_ru: str, which_en: str) -> bool:
        if self._is_number():
            self._advance()
            return True
        self._report_current_error(self._m(f'Ожидалось число ({which_ru})', f'Expected number ({which_en})'))
        return False

    def _expect_number_or_identifier(self, which_ru: str, which_en: str) -> bool:
        if self._is_number_or_identifier():
            self._advance()
            return True
        self._report_current_error(
            self._m(
                f'Ожидалось число или идентификатор ({which_ru})',
                f'Expected number or identifier ({which_en})',
            )
        )
        return False

    def _parse_complex_declaration(self):
        pass
        start_errors = len(self.errors)
        if not self._expect_keyword('val', "Ожидалось ключевое слово 'val'", "Expected keyword 'val'"):
            self._recover_to_identifier_before_assign()
        if not self._expect_identifier():
            self._recover_to_assign_or_semicolon()
            if self._check_value(';') or self._current() is None:
                self._sync_after_declaration_error(expect_semicolon=True)
                return
        if self._expect_value('=', "Ожидался оператор '='", "Expected '=' operator"):
            current = self._current()
            previous = self.tokens[self.pos - 1] if self.pos > 0 else None
            if current is not None and previous is not None and current.token_type == 'ERROR' and current.start == previous.end + 1:
                symbol = self._error_symbol(current)
                self._add_error(previous.value + symbol, previous.line, previous.start, self._m('Некорректная запись оператора присваивания', 'Invalid assignment operator'))
                self._advance()
        else:
            current = self._current()
            op_fragment = None
            op_line = None
            op_col = None
            if current is not None and current.token_type == 'ERROR' and (self.pos + 2 < len(self.tokens)) and (self.tokens[self.pos + 1].token_type == 'OPERATOR') and (self.tokens[self.pos + 2].token_type == 'OPERATOR'):
                op_fragment = self.tokens[self.pos + 1].value + self.tokens[self.pos + 2].value
                op_line = self.tokens[self.pos + 1].line
                op_col = self.tokens[self.pos + 1].start
            skipped = self._recover_to_complex_or_lparen_or_semicolon()
            if op_fragment is not None:
                self._add_error(op_fragment, op_line, op_col, self._m('Некорректная запись оператора присваивания', 'Invalid assignment operator'))
            elif current is not None and current.token_type == 'ERROR' and (skipped >= 2) and (self.pos > 0) and (self.tokens[self.pos - 1].token_type == 'OPERATOR') and (self.tokens[self.pos - 1].value != '='):
                self._add_error(self._fragment(current), current.line, current.start, self._m('Некорректная запись оператора присваивания', 'Invalid assignment operator'))
            if self._check_value(';') or self._current() is None:
                self._sync_after_declaration_error(expect_semicolon=True)
                return
        if not self._is_keyword('Complex'):
            current = self._current()
            constructor_fragment = self._constructor_fragment(current)
            if self._constructor_has_glued_argument(current):
                if constructor_fragment != 'Complex':
                    self._add_error(constructor_fragment, current.line if current else self.current_line, current.start if current else 1, self._m("Ожидалось ключевое слово 'Complex'", "Expected keyword 'Complex'"))
                arg_fragment, arg_col = self._glued_argument_info(current)
                if not self._is_number_text(arg_fragment):
                    self._add_error(arg_fragment, current.line if current else self.current_line, arg_col, self._m('Ожидалось число (первый аргумент)', 'Expected number (first argument)'))
                self._add_error(arg_fragment, current.line if current else self.current_line, arg_col, self._m("Ожидалась '(' после 'Complex'", "Expected '(' after 'Complex'"))
                comma_token = self._missing_comma_after_glued_argument()
                if comma_token is not None:
                    self._add_error(self._fragment(comma_token), comma_token.line, comma_token.start, self._m("Ожидалась ',' между аргументами", "Expected ',' between arguments"))
                    if comma_token.token_type == 'ERROR':
                        self._add_error(self._fragment(comma_token), comma_token.line, comma_token.start, self._m('Ожидалось число (второй аргумент)', 'Expected number (second argument)'))
                if not self._has_closing_paren_before_semicolon():
                    last = self.tokens[-1] if self.tokens else current
                    self._add_error('EOF', last.line if last else self.current_line, (last.end + 1) if last else 1, self._m("Ожидалась ')' после аргументов", "Expected ')' after arguments"))
                self._sync_after_declaration_error(expect_semicolon=True)
                return
            self._add_error(constructor_fragment, current.line if current else self.current_line, current.start if current else 1, self._m("Ожидалось ключевое слово 'Complex'", "Expected keyword 'Complex'"))
            self._recover_to_lparen_or_semicolon()
            if self._check_value('('):
                self._advance()
            else:
                self._sync_after_declaration_error(expect_semicolon=True)
                return
        else:
            self._advance()
        if self.pos > 0 and self.tokens[self.pos - 1].value != '(':
            if not self._expect_value('(', "Ожидалась '(' после 'Complex'", "Expected '(' after 'Complex'"):
                self._sync_after_declaration_error(expect_semicolon=True)
                return
        first_ok = self._expect_number_or_identifier('первый аргумент', 'first argument')
        if not first_ok:
            failed = self._current()
            if failed is not None and failed.value == '(':
                self._advance()
                first_ok = self._expect_number_or_identifier('первый аргумент', 'first argument')
                if not first_ok:
                    failed_after_lparen = self._current()
                    if failed_after_lparen is not None and failed_after_lparen.token_type == 'ERROR':
                        self._advance()
                        if self._is_number() or (self._current() is not None and self._current().token_type == 'ERROR'):
                            first_ok = True
                        else:
                            self._recover_to_any({',', ')'})
                    else:
                        self._recover_to_any({',', ')'})
            elif failed is not None and failed.token_type == 'ERROR':
                self._advance()
                if self._is_number() or (self._current() is not None and self._current().token_type == 'ERROR'):
                    first_ok = True
                else:
                    self._recover_to_any({',', ')'})
            else:
                self._recover_to_any({',', ')'})
            if not first_ok and self._check_value(')'):
                self._advance()
                if self._check_value('('):
                    self._advance()
                    first_ok = self._expect_number_or_identifier('первый аргумент', 'first argument')
                    if not first_ok:
                        self._sync_after_declaration_error(expect_semicolon=True)
                        return
                else:
                    self._sync_after_declaration_error(expect_semicolon=True)
                    return
        comma_ok = self._expect_value(',', "Ожидалась ',' между аргументами", "Expected ',' between arguments")
        if not comma_ok:
            if self._check_value(';'):
                self._sync_after_declaration_error(expect_semicolon=True)
                return
            comma_token = self._current()
            comma_fragment = self._fragment(comma_token)
            comma_line = comma_token.line if comma_token else self.current_line
            comma_col = comma_token.start if comma_token else 1
            self._recover_to_any({')', ';'})
            if not self._check_value(')'):
                last = self.tokens[-1] if self.tokens else None
                self._add_error('EOF', last.line if last else self.current_line, (last.end + 1) if last else 1, self._m("Ожидалась ')' после аргументов", "Expected ')' after arguments"))
                self._sync_after_declaration_error(expect_semicolon=True)
                return
            if comma_token is not None and comma_token.token_type == 'ERROR':
                self._add_error(comma_fragment, comma_line, comma_col, self._m('Ожидалось число (второй аргумент)', 'Expected number (second argument)'))
            self._advance()
            if not self._expect_value(';', "Ожидалась ';' в конце объявления", "Expected ';' at end of declaration"):
                if self._current() is not None:
                    self._sync_after_declaration_error(expect_semicolon=True)
                return
            if len(self.errors) != start_errors:
                self._sync_after_declaration_error()
            return
        second_ok = self._expect_number_or_identifier('второй аргумент', 'second argument')
        if not second_ok:
            self._recover_to_any({')'})
            if not self._check_value(')'):
                self._sync_after_declaration_error(expect_semicolon=True)
                return
        if not self._expect_value(')', "Ожидалась ')' после аргументов", "Expected ')' after arguments"):
            self._recover_to_any({')', ';'})
            if self._check_value(')'):
                self._advance()
            else:
                self._sync_after_declaration_error(expect_semicolon=True)
                return
        if not self._expect_value(';', "Ожидалась ';' в конце объявления", "Expected ';' at end of declaration"):
            if self._current() is not None:
                self._sync_after_declaration_error(expect_semicolon=True)
            return
        if len(self.errors) != start_errors:
            self._sync_after_declaration_error()
