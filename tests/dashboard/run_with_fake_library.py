"""
Lance tools/dashboard.py avec un faux lecteur de la bibliothèque (les tests ne joignent jamais une vraie base).

    python tests/dashboard/run_with_fake_library.py [options de dashboard.py]

Le faux lecteur est décrit par le fichier JSON nommé dans PMZILLA_TEST_FAKE_LIBRARY :
    {"books": [{"title": ..., "author": ..., "collections": [...], "passages": n}, ...]}  -> ces livres
    {"watch_counts": {"articles": n, "passages": m}}                                      -> comptes de la veille (base)
    {"shares": {"total": n, "recent": r, "first_pick": "AAAA-MM-JJ" ou null, "evaluable": e, "hits": h}}
                                                                                          -> partages et sélections (base)
    {"raise": "ConnectionError"}                                                          -> chaque lecteur lève cette erreur
Variable absente ou fichier absent : bibliothèque vide, et « pas encore de données » pour la veille et les partages.
PMZILLA_TEST_CODE_ROOT : voir code_root_for_tests. Aucun fichier d'état local n'est lu : seul le faux lecteur fournit des données.
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


def fake_spec():
    path = Path(os.environ.get("PMZILLA_TEST_FAKE_LIBRARY", "/nonexistent-fake-library.json"))
    spec = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if "raise" in spec:
        error = getattr(builtins, spec["raise"])
        raise error("message secret du faux lecteur")
    return spec


def fake_watch_counts(*args, **kwargs):
    counts = fake_spec().get("watch_counts")
    if counts is None:
        raise dashboard.PasDeDonnees
    return dict(counts)


def fake_shares(*args, **kwargs):
    shares = fake_spec().get("shares")
    if shares is None:
        raise dashboard.PasDeDonnees
    return dict(shares)


def refuse_real_reader(*args, **kwargs):
    raise AssertionError("le lecteur réel ne doit pas être appelé dans les tests")


dashboard.fetch_library_books = refuse_real_reader
dashboard.fetch_watch_counts = fake_watch_counts
dashboard.fetch_shares = fake_shares
dashboard.library_books = lambda read=None: (read or fake_reader)()

def code_root_for_tests():
    """PMZILLA_TEST_CODE_ROOT : dossier de code des réglages suivis (tri.yaml) et des scripts (mapping_lab.py). Absente : le dossier de
    contenu (dépôt de développement, les deux dossiers n'en font qu'un). « derived » : celui que dashboard.py déduit de son propre fichier
    (dossier d'exécution factice, voir test_run_tree.py)."""
    choice = os.environ.get("PMZILLA_TEST_CODE_ROOT")
    if choice == "derived":
        return
    dashboard.CODE_ROOT = Path(choice) if choice else dashboard.WORKSPACE


if __name__ == "__main__":
    code_root_for_tests()
    sys.exit(dashboard.main(sys.argv[1:]))
