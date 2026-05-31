from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from scanner import Token


INT_MIN = -2147483648
INT_MAX = 2147483647
FLOAT_ABS_MAX = 1.0e100


@dataclass
class SemanticErrorRecord:
    fragment: str
    line: int
    col: int
    message: str

    def location_ru(self) -> str:
        return f"строка {self.line}, позиция {self.col}"

    def location_en(self) -> str:
        return f"line {self.line}, position {self.col}"


@dataclass
class SemanticAnalysisResult:
    ast_text: str
    ast_root: Optional["AstNode"] = None
    errors: List[SemanticErrorRecord] = field(default_factory=list)


@dataclass
class AstNode:
    def label(self) -> str:
        return self.__class__.__name__

    def children(self) -> List["AstNode"]:
        return []

    def attributes(self) -> List[str]:
        return []


@dataclass
class IdentifierNode(AstNode):
    name: str
    line: int
    col: int

    def attributes(self) -> List[str]:
        return [f'name: "{self.name}"']


@dataclass
class IntLiteralNode(AstNode):
    value: int
    line: int
    col: int

    def attributes(self) -> List[str]:
        return [f"value: {self.value}"]


@dataclass
class FloatLiteralNode(AstNode):
    value: float
    line: int
    col: int

    def attributes(self) -> List[str]:
        return [f"value: {self.value}"]


@dataclass
class ComplexTypeNode(AstNode):
    name: str = "Complex"

    def label(self) -> str:
        return "ComplexNode"

    def attributes(self) -> List[str]:
        return [f'name: "{self.name}"']


@dataclass
class ComplexDeclNode(AstNode):
    name: str
    modifiers: List[str]
    type_node: ComplexTypeNode
    re: AstNode
    im: AstNode
    line: int
    col: int

    def attributes(self) -> List[str]:
        return [f'name: "{self.name}"', f"modifiers: {self.modifiers}"]

    def children(self) -> List[AstNode]:
        return [self.type_node, self.re, self.im]


@dataclass
class ProgramNode(AstNode):
    declarations: List[AstNode]

    def children(self) -> List[AstNode]:
        return self.declarations


@dataclass
class SymbolInfo:
    name: str
    type_name: str
    line: int
    col: int


class SymbolTable:
    def __init__(self):
        self.scopes: List[Dict[str, SymbolInfo]] = [dict()]

    def declare(self, symbol: SymbolInfo) -> bool:
        current = self.scopes[-1]
        if symbol.name in current:
            return False
        current[symbol.name] = symbol
        return True

    def lookup(self, name: str) -> Optional[SymbolInfo]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def lookup_current(self, name: str) -> Optional[SymbolInfo]:
        return self.scopes[-1].get(name)


class SemanticAnalyzer:
    NUMERIC_TYPES = {"Int", "Float"}

    def __init__(self, tokens: List["Token"], lang: str = "ru"):
        self.tokens = self._filter_tokens(tokens)
        self.lang = lang if lang in ("ru", "en") else "ru"
        self.i = 0
        self.errors: List[SemanticErrorRecord] = []
        self.symbols = SymbolTable()

    @staticmethod
    def _filter_tokens(tokens: List["Token"]) -> List["Token"]:
        out = []
        for tok in tokens:
            if tok.token_type in ("DELIMITER", "COMMENT"):
                continue
            out.append(tok)
        return out

    def _m(self, ru: str, en: str) -> str:
        return en if self.lang == "en" else ru

    def _current(self) -> Optional["Token"]:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _advance(self):
        self.i += 1

    def _add_error(self, t: Optional["Token"], message: str):
        self.errors.append(
            SemanticErrorRecord(
                fragment=t.value if t is not None else "EOF",
                line=t.line if t is not None else 1,
                col=t.start if t is not None else 1,
                message=message,
            )
        )

    def _is_keyword(self, word: str) -> bool:
        t = self._current()
        return t is not None and t.token_type == "KEYWORD" and t.value == word

    def _is_identifier(self) -> bool:
        t = self._current()
        return t is not None and t.token_type == "IDENTIFIER"

    def _is_number(self) -> bool:
        t = self._current()
        return t is not None and t.token_type in ("INTEGER", "FLOAT")

    def _match_keyword(self, word: str) -> bool:
        if self._is_keyword(word):
            self._advance()
            return True
        return False

    def _match_value(self, value: str) -> bool:
        t = self._current()
        if t is not None and t.value == value:
            self._advance()
            return True
        return False

    def _expect_keyword(self, word: str) -> bool:
        if self._match_keyword(word):
            return True
        self._add_error(
            self._current(),
            self._m(f"Ожидалось ключевое слово '{word}'", f"Expected keyword '{word}'"),
        )
        return False

    def _expect_value(self, value: str) -> bool:
        if self._match_value(value):
            return True
        self._add_error(
            self._current(),
            self._m(f"Ожидался символ '{value}'", f"Expected '{value}'"),
        )
        return False

    def _parse_number_literal(self) -> Optional[AstNode]:
        t = self._current()
        if t is None:
            return None
        if t.token_type == "INTEGER":
            self._advance()
            return IntLiteralNode(value=int(t.value), line=t.line, col=t.start)
        if t.token_type == "FLOAT":
            self._advance()
            return FloatLiteralNode(value=float(t.value), line=t.line, col=t.start)
        if t.token_type == "IDENTIFIER":
            self._advance()
            return IdentifierNode(name=t.value, line=t.line, col=t.start)
        self._add_error(
            t,
            self._m(
                "Ожидалось число или идентификатор",
                "Expected number or identifier",
            ),
        )
        self._advance()
        return None

    def _parse_complex_decl(self) -> Optional[ComplexDeclNode]:
        if not self._expect_keyword("val"):
            self._sync_to_next_decl()
            return None

        name_tok = self._current()
        if not self._is_identifier():
            self._add_error(
                name_tok,
                self._m("Ожидался идентификатор", "Expected identifier"),
            )
            self._sync_to_next_decl()
            return None
        self._advance()

        if not self._expect_value("="):
            self._sync_to_next_decl()
            return None

        if not self._expect_keyword("Complex"):
            self._sync_to_next_decl()
            return None

        if not self._expect_value("("):
            self._sync_to_next_decl()
            return None

        re_node = self._parse_number_literal()
        if not self._expect_value(","):
            self._sync_to_next_decl()
            return None

        im_node = self._parse_number_literal()
        if not self._expect_value(")"):
            self._sync_to_next_decl()
            return None

        if not self._expect_value(";"):
            self._sync_to_next_decl()

        if re_node is None or im_node is None:
            return None

        return ComplexDeclNode(
            name=name_tok.value,
            modifiers=["val"],
            type_node=ComplexTypeNode(),
            re=re_node,
            im=im_node,
            line=name_tok.line,
            col=name_tok.start,
        )

    def _sync_to_next_decl(self):
        while self._current() is not None:
            if self._is_keyword("val"):
                return
            if self._match_value(";"):
                return
            self._advance()

    def _parse_program(self) -> ProgramNode:
        declarations: List[AstNode] = []
        while self._current() is not None:
            if not self._is_keyword("val"):
                self._advance()
                continue
            decl = self._parse_complex_decl()
            if decl is None:
                continue
            if self._check_decl_semantics(decl):
                declarations.append(decl)
        return ProgramNode(declarations=declarations)

    def _check_decl_semantics(self, decl: ComplexDeclNode) -> bool:
        existing = self.symbols.lookup_current(decl.name)
        if existing is not None:
            self.errors.append(
                SemanticErrorRecord(
                    fragment=decl.name,
                    line=decl.line,
                    col=decl.col,
                    message=self._m(
                        f'Идентификатор "{decl.name}" уже объявлен ранее (строка {existing.line})',
                        f'Identifier "{decl.name}" is already declared earlier (line {existing.line})',
                    ),
                )
            )
            return False

        re_type = self._infer_expr_type(decl.re)
        im_type = self._infer_expr_type(decl.im)

        if re_type == "Unknown" or im_type == "Unknown":
            pass
        elif re_type not in self.NUMERIC_TYPES or im_type not in self.NUMERIC_TYPES:
            self.errors.append(
                SemanticErrorRecord(
                    fragment=decl.name,
                    line=decl.line,
                    col=decl.col,
                    message=self._m(
                        f'Несовместимость типов: аргументы Complex должны быть числовыми, получено ({re_type}, {im_type})',
                        f'Type mismatch: Complex arguments must be numeric, got ({re_type}, {im_type})',
                    ),
                )
            )

        self.symbols.declare(
            SymbolInfo(
                name=decl.name,
                type_name="Complex",
                line=decl.line,
                col=decl.col,
            )
        )
        return True

    def _infer_expr_type(self, node: AstNode) -> str:
        if isinstance(node, IntLiteralNode):
            if node.value < INT_MIN or node.value > INT_MAX:
                self.errors.append(
                    SemanticErrorRecord(
                        fragment=str(node.value),
                        line=node.line,
                        col=node.col,
                        message=self._m(
                            f"Значение {node.value} выходит за диапазон Int [{INT_MIN}; {INT_MAX}]",
                            f"Value {node.value} is out of Int range [{INT_MIN}; {INT_MAX}]",
                        ),
                    )
                )
            return "Int"
        if isinstance(node, FloatLiteralNode):
            if abs(node.value) > FLOAT_ABS_MAX:
                self.errors.append(
                    SemanticErrorRecord(
                        fragment=str(node.value),
                        line=node.line,
                        col=node.col,
                        message=self._m(
                            f"Значение {node.value} выходит за допустимые пределы",
                            f"Value {node.value} is out of allowed range",
                        ),
                    )
                )
            return "Float"
        if isinstance(node, IdentifierNode):
            symbol = self.symbols.lookup(node.name)
            if symbol is None:
                self.errors.append(
                    SemanticErrorRecord(
                        fragment=node.name,
                        line=node.line,
                        col=node.col,
                        message=self._m(
                            f'Идентификатор "{node.name}" используется до объявления',
                            f'Identifier "{node.name}" is used before declaration',
                        ),
                    )
                )
                return "Unknown"
            return symbol.type_name
        return "Unknown"

    def analyze(self) -> SemanticAnalysisResult:
        self.i = 0
        self.errors = []
        self.symbols = SymbolTable()
        ast = self._parse_program()
        ast_text = render_tree(ast) if ast.declarations else render_tree(ast)
        if not ast.declarations and not self.errors:
            ast_text = "AST: <empty>"
        return SemanticAnalysisResult(ast_text=ast_text, ast_root=ast, errors=self.errors)


def render_tree(node: Optional[AstNode]) -> str:
    if node is None:
        return "AST: <empty>"

    lines: List[str] = [node.label()]

    def _walk(current: AstNode, prefix: str):
        entries: List[Union[str, AstNode]] = current.attributes() + current.children()
        for idx, item in enumerate(entries):
            is_last = idx == len(entries) - 1
            branch = "└── " if is_last else "├── "
            next_prefix = f"{prefix}{'    ' if is_last else '│   '}"
            if isinstance(item, str):
                lines.append(f"{prefix}{branch}{item}")
            else:
                lines.append(f"{prefix}{branch}{item.label()}")
                _walk(item, next_prefix)

    _walk(node, "")
    return "\n".join(lines)
