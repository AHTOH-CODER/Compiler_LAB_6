"""
Модуль для поиска подстрок с использованием регулярных выражений
"""

import re
from typing import Dict, List, Tuple


class SearchResult:
    """Класс для хранения результата поиска"""

    def __init__(self, text: str, start_line: int, start_char: int, length: int):
        self.text = text
        self.start_line = start_line
        self.start_char = start_char
        self.length = length

    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "line": self.start_line,
            "char": self.start_char,
            "length": self.length,
        }


class RegexSearchEngine:
    """Движок поиска с использованием регулярных выражений"""

    def __init__(self):
        self.results: List[SearchResult] = []
        self.full_text = ""

    def search(
        self,
        text: str,
        pattern: str,
        task_name: str = "",
        ignore_case: bool = False,
    ) -> List[Dict]:
        self.full_text = text
        self.results = []

        if not text or not pattern:
            return []

        flags = re.MULTILINE
        if ignore_case:
            flags |= re.IGNORECASE

        try:
            regex = re.compile(pattern, flags)
            lines = text.split("\n")

            for line_num, line in enumerate(lines, 1):
                for match in regex.finditer(line):
                    result = SearchResult(
                        text=match.group(),
                        start_line=line_num,
                        start_char=match.start() + 1,
                        length=len(match.group()),
                    )
                    self.results.append(result)

            return [r.to_dict() for r in self.results]

        except re.error as e:
            print(f"Ошибка в регулярном выражении: {e}")
            return []

    def get_global_position(self, result_index: int) -> Tuple[int, int]:
        if result_index >= len(self.results):
            return (0, 0)

        result = self.results[result_index]
        lines = self.full_text.split("\n")
        global_start = 0

        for i in range(result.start_line - 1):
            global_start += len(lines[i]) + 1

        global_start += result.start_char - 1
        global_end = global_start + result.length

        return (global_start, global_end)

    def get_count(self) -> int:
        return len(self.results)
