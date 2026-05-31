"""
Модуль с регулярными выражениями для трёх заданий (вариант Васильев А.Р.)
"""


class RegexPatterns:
    """Класс, содержащий регулярные выражения для поиска"""

    # Задание 1: Числа, начинающиеся на 9
    TASK1_PATTERN = r'\b9\d*\b'
    TASK1_DESCRIPTION = "Числа, начинающиеся на 9"

    # Задание 2: Номера карт Maestro Card
    TASK2_PATTERN = (
        r'\b(?:'
        r'(?:5(?:0(?:0\d{2}|[1-9]\d{2})|[6-8]\d{2})|6\d{3})\d{10,13}'
        r'|'
        r'(?:501\d|502\d|503\d|504\d|505\d|506\d|507\d|508\d|509\d|'
        r'56\d{2}|57\d{2}|58\d{2}|6\d{3})(?:[\s-]\d{4}){3}'
        r')\b'
    )
    TASK2_DESCRIPTION = "Номера карт Maestro Card (12–19 цифр, BIN 50xxxx, 56–58xxxx, 60–69xxxx)"

    # Задание 3: HTML-тег с атрибутами
    TASK3_PATTERN = (
        r'<\s*[a-zA-Z][\w:-]*\s+'
        r'(?:[a-zA-Z][\w:-]*\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s/>]+)\s*)+'
        r'/?>'
    )
    TASK3_DESCRIPTION = "HTML-тег с одним или несколькими атрибутами"

    @staticmethod
    def get_patterns_dict():
        return {
            "Числа на 9": RegexPatterns.TASK1_PATTERN,
            "Maestro Card": RegexPatterns.TASK2_PATTERN,
            "HTML-тег с атрибутами": RegexPatterns.TASK3_PATTERN,
        }

    @staticmethod
    def get_task_info(task_name):
        info = {
            "Числа на 9": {
                "pattern": RegexPatterns.TASK1_PATTERN,
                "description": RegexPatterns.TASK1_DESCRIPTION,
                "examples_correct": [
                    "9", "90", "905", "9123456789", "999", "9001"
                ],
                "examples_incorrect": [
                    "89", "19", "809", "908abc", "x905"
                ],
            },
            "Maestro Card": {
                "pattern": RegexPatterns.TASK2_PATTERN,
                "description": RegexPatterns.TASK2_DESCRIPTION,
                "examples_correct": [
                    "5018021374808902",
                    "6759649826498443",
                    "5018 0213 7480 8902",
                    "6304-0000-0000-0000",
                ],
                "examples_incorrect": [
                    "4012881171304827",
                    "5555555555554444",
                    "50180213748089",
                    "4111111111111111",
                ],
            },
            "HTML-тег с атрибутами": {
                "pattern": RegexPatterns.TASK3_PATTERN,
                "description": RegexPatterns.TASK3_DESCRIPTION,
                "examples_correct": [
                    '<div class="container">',
                    '<img src="photo.jpg" alt="desc" />',
                    '<input type="text" name="user" value="admin">',
                    "<a href='index.html' target='_blank'>",
                ],
                "examples_incorrect": [
                    "<div>",
                    "<br />",
                    'div class="x"',
                    "<p>text</p>",
                ],
            },
        }
        return info.get(task_name, {})
