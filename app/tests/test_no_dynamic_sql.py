"""
Regression guard: SQL passed to execute()/executemany()/executescript() must be a plain
string with ? placeholders, never built with f-strings, + / % concatenation or .format().

If a dynamic fragment is ever genuinely needed (for example a column picked from a fixed
dict), mark the line with `# sql-safe: <reason>` so the exception is explicit in review.
"""
import ast
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
SQL_CALLS = {"execute", "executemany", "executescript"}
ALLOW_MARKER = "# sql-safe:"
EXCLUDED_DIRS = {"tests", "env", ".venv", "__pycache__"}


def _is_dynamic(node):
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return True
    return False


def offending_calls(source):
    """Yields line numbers of SQL calls whose query argument is built dynamically."""
    lines = source.splitlines()
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in SQL_CALLS or not node.args:
            continue
        if not _is_dynamic(node.args[0]):
            continue
        call_lines = lines[node.lineno - 1:(node.end_lineno or node.lineno)]
        if any(ALLOW_MARKER in line for line in call_lines):
            continue
        yield node.lineno


def app_python_files():
    for path in sorted(APP_DIR.rglob("*.py")):
        if EXCLUDED_DIRS.intersection(path.relative_to(APP_DIR).parts):
            continue
        yield path


def test_no_dynamic_sql_in_app():
    hits = []
    for path in app_python_files():
        for lineno in offending_calls(path.read_text(encoding="utf-8")):
            hits.append(f"{path.relative_to(APP_DIR)}:{lineno}")
    assert hits == [], "Dynamic SQL found, use ? placeholders instead:\n" + "\n".join(hits)


def test_scanner_covers_the_app():
    scanned = {str(p.relative_to(APP_DIR)) for p in app_python_files()}
    assert "modules/helper_functions.py" in scanned
    assert "cogs/SoundsUtils.py" in scanned


@pytest.mark.parametrize("snippet", [
    'db.cursor.execute(f"SELECT * FROM sounds WHERE sound_id=\\"{sound}\\"")',
    'db.cursor.execute("SELECT * FROM sounds WHERE sound_id=\\"" + sound + "\\"")',
    'db.cursor.execute("SELECT * FROM sounds WHERE sound_id=\'%s\'" % sound)',
    'db.cursor.execute("SELECT * FROM sounds WHERE sound_id=\'{}\'".format(sound))',
    'conn.executemany(f"INSERT INTO t VALUES ({x})", rows)',
    'conn.executescript("DROP TABLE " + name)',
])
def test_scanner_flags_dynamic_sql(snippet):
    assert list(offending_calls(snippet)) == [1]


@pytest.mark.parametrize("snippet", [
    'db.cursor.execute("SELECT * FROM sounds WHERE sound_id = ?", (sound,))',
    'db.cursor.execute(query, params)',
    'conn.executescript(schema)',
    'pipe.execute()',
    'db.cursor.execute("SELECT " + COLUMNS[choice] + " FROM sounds")  # sql-safe: fixed column map',
])
def test_scanner_allows_static_sql(snippet):
    assert list(offending_calls(snippet)) == []
