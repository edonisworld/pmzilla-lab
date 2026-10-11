"""
Lance tools/dashboard.py avec un faux lecteur de la bibliothèque (les tests ne joignent jamais une vraie base).

    python tests/dashboard/run_with_fake_library.py [options de dashboard.py]

Le faux lecteur est décrit par le fichier JSON nommé dans PMZILLA_TEST_FAKE_LIBRARY :
    {"books": [{"title": ..., "author": ..., "collections": [...], "passages": n}, ...]}  -> ces livres
    {"raise": "ConnectionError"}                                                          -> le lecteur lève cette erreur
Variable absente ou fichier absent : bibliothèque vide.
"""
import builtins
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import dashboard  # noqa: E402


def fake_reader():
    path = Path(os.environ.get("PMZILLA_TEST_FAKE_LIBRARY", "/nonexistent-fake-library.json"))
    spec = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"books": []}
    if "raise" in spec:
        error = getattr(builtins, spec["raise"])
        raise error("message secret du faux lecteur")
    return [dict(book) for book in spec["books"]]


def refuse_real_reader(*args, **kwargs):
    raise AssertionError("le lecteur réel ne doit pas être appelé dans les tests")


dashboard.fetch_library_books = refuse_real_reader
dashboard.library_books = lambda read=None: (read or fake_reader)()

if __name__ == "__main__":
    sys.exit(dashboard.main(sys.argv[1:]))
