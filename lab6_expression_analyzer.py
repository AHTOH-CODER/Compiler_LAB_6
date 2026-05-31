from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Token:
    kind: str
    value: str
    pos: int


@dataclass
class LexError:
    pos: int
    message: str


@dataclass
class ParseError:
    pos: int
    message: str


class Lexer:
    """Лексер для варианта: id = letter {letter | digit}, num = digit {digit}."""

    def tokenize(self, text: str) -> Tuple[List[Token], List[LexError]]:
        tokens: List[Token] = []
        errors: List[LexError] = []
        i = 0
        n = len(text)

        while i < n:
            ch = text[i]
            if ch.isspace():
                i += 1
                continue

            if ch.isdigit():
                start = i
                while i < n and text[i].isdigit():
                    i += 1
                if i < n and text[i].isalpha():
                    while i < n and (text[i].isalnum()):
                        i += 1
                    bad = text[start:i]
                    errors.append(
                        LexError(start, f"Недопустимый идентификатор, начинающийся с цифры: '{bad}'")
                    )
                    tokens.append(Token("ERROR", bad, start))
                else:
                    tokens.append(Token("NUM", text[start:i], start))
                continue

            if ch.isalpha():
                start = i
                i += 1
                while i < n and (text[i].isalpha() or text[i].isdigit()):
                    i += 1
                tokens.append(Token("ID", text[start:i], start))
                continue

            if ch in "+-*/%":
                tokens.append(Token("OP", ch, i))
                i += 1
                continue
            if ch == "(":
                tokens.append(Token("LPAREN", ch, i))
                i += 1
                continue
            if ch == ")":
                tokens.append(Token("RPAREN", ch, i))
                i += 1
                continue

            errors.append(LexError(i, f"Недопустимый символ: '{ch}'"))
            tokens.append(Token("ERROR", ch, i))
            i += 1

        tokens.append(Token("EOF", "", n))
        return tokens, errors


class RecursiveDescentParser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.i = 0
        self.errors: List[ParseError] = []
        self.quads: List[Tuple[str, str, str, str]] = []
        self.temp_counter = 0

    def current(self) -> Token:
        return self.tokens[self.i]

    def advance(self) -> None:
        if self.i < len(self.tokens) - 1:
            self.i += 1

    def new_temp(self) -> str:
        self.temp_counter += 1
        return f"t{self.temp_counter}"

    def error(self, message: str) -> None:
        self.errors.append(ParseError(self.current().pos, message))

    def parse(self) -> Optional[str]:
        result = self.E()
        if result is None:
            return None
        if self.current().kind != "EOF":
            self.error(f"Лишний фрагмент после конца выражения: '{self.current().value}'")
            return None
        return result

    # E -> T A
    def E(self) -> Optional[str]:
        left = self.T()
        if left is None:
            return None
        return self.A(left)

    # A -> eps | + T A | - T A
    def A(self, inherited: str) -> Optional[str]:
        while self.current().kind == "OP" and self.current().value in {"+", "-"}:
            op = self.current().value
            self.advance()
            right = self.T()
            if right is None:
                self.error("Пропущен операнд после '+' или '-'")
                return None
            tmp = self.new_temp()
            self.quads.append((op, inherited, right, tmp))
            inherited = tmp
        return inherited

    # T -> F B
    def T(self) -> Optional[str]:
        left = self.F()
        if left is None:
            return None
        return self.B(left)

    # B -> eps | * F B | / F B | % F B
    def B(self, inherited: str) -> Optional[str]:
        while self.current().kind == "OP" and self.current().value in {"*", "/", "%"}:
            op = self.current().value
            self.advance()
            right = self.F()
            if right is None:
                self.error(f"Пропущен операнд после '{op}'")
                return None
            tmp = self.new_temp()
            self.quads.append((op, inherited, right, tmp))
            inherited = tmp
        return inherited

    # F -> num | id | (E)
    def F(self) -> Optional[str]:
        tok = self.current()
        if tok.kind == "NUM":
            self.advance()
            return tok.value
        if tok.kind == "ID":
            self.advance()
            return tok.value
        if tok.kind == "LPAREN":
            self.advance()
            inner = self.E()
            if inner is None:
                return None
            if self.current().kind != "RPAREN":
                self.error("Пропущена закрывающая скобка ')'")
                return None
            self.advance()
            return inner
        if tok.kind == "RPAREN":
            self.error("Лишняя закрывающая скобка ')'")
            return None
        if tok.kind == "EOF":
            self.error("Неожиданный конец выражения")
            return None
        self.error(f"Ожидались num, id или '(E)', получено: '{tok.value}'")
        return None


def to_postfix(tokens: List[Token]) -> List[str]:
    """ПОЛИЗ алгоритмом Дейкстры; * / % выше + -."""
    precedence = {
        "*": 3,
        "/": 3,
        "%": 3,
        "+": 2,
        "-": 2,
    }
    output: List[str] = []
    stack: List[str] = []

    for t in tokens:
        if t.kind == "NUM":
            output.append(t.value)
        elif t.kind == "OP":
            op = t.value
            p1 = precedence[op]
            while stack and stack[-1] in precedence and precedence[stack[-1]] >= p1:
                output.append(stack.pop())
            stack.append(op)
        elif t.kind == "LPAREN":
            stack.append("(")
        elif t.kind == "RPAREN":
            while stack and stack[-1] != "(":
                output.append(stack.pop())
            if stack and stack[-1] == "(":
                stack.pop()
            else:
                raise ValueError("Несбалансированные скобки при построении ПОЛИЗ")

    while stack:
        top = stack.pop()
        if top == "(":
            raise ValueError("Несбалансированные скобки при построении ПОЛИЗ")
        output.append(top)
    return output


def eval_postfix(postfix: List[str]) -> int:
    stack: List[int] = []
    for item in postfix:
        if item.isdigit():
            stack.append(int(item))
            continue
        if len(stack) < 2:
            raise ValueError("Недостаточно операндов в ПОЛИЗ")
        b = stack.pop()
        a = stack.pop()
        if item == "+":
            stack.append(a + b)
        elif item == "-":
            stack.append(a - b)
        elif item == "*":
            stack.append(a * b)
        elif item == "/":
            if b == 0:
                raise ZeroDivisionError("Деление на ноль")
            stack.append(a // b)
        elif item == "%":
            if b == 0:
                raise ZeroDivisionError("Деление на ноль")
            stack.append(a % b)
        else:
            raise ValueError(f"Неизвестная операция: {item}")
    if len(stack) != 1:
        raise ValueError("Некорректная ПОЛИЗ")
    return stack[0]
