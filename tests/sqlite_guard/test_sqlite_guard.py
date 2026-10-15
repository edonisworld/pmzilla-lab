"""
Garde-fou SQLite (change remove-sqlite, spec tooling-sqlite-guard) : plus aucun outil ni aucun test ne passe par SQLite.

    uv run --with numpy --with httpx --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/sqlite_guard -v

Deux parcours, sans base de données, qui ne lisent que des fichiers du dépôt :
  1. tools/ (scripts Python et shell, récursif, hors __pycache__) : échoue sur un `import sqlite3` / `from sqlite3`, sur un nom de
     fichier à extension .sqlite (aussi .sqlite-wal, .sqlite-shm, .sqlite.<suffixe> des points de restauration) et sur un appel de
     la commande `sqlite3`. Le message nomme le fichier et la ligne.
  2. tests/ : échoue sur un import du module SQLite ou sur un appel de `build_sqlite` (constructeur de la bibliothèque de démonstration
     fichier SQLite pour vérifier qu'un outil l'ignore. Ce garde-fou ne se parcourt pas lui-même.
     fichier SQLite pour vérifier qu'un outil l'ignore. Les fichiers de ce garde-fou sont exclus du parcours.

Listes d'autorisation (AUTORISES_OUTILS, AUTORISES_TESTS) : vides ; toute entrée exige l'accord de l'auteur.

"""
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
ICI = Path(__file__).resolve().parent

# Toute entrée de ces deux listes exige l'accord de l'auteur. Elles restent vides.
AUTORISES_OUTILS: set[str] = set()
AUTORISES_TESTS: set[str] = set()


MOTIFS_OUTILS = {
    "import du module SQLite": re.compile(r"^\s*(?:from\s+sqlite3\b|import\s+(?:[\w.]+\s*,\s*)*sqlite3\b)"),
    "nom de fichier .sqlite": re.compile(r"\.sqlite(?![A-Za-z_])"),
    "appel de la commande sqlite3": re.compile(r"""(?:^|[;&|(`]|\$\(|["'])\s*sqlite3(?=\s|["'])(?<!import sqlite3)"""),
}
MOTIFS_TESTS = {
    "import du module SQLite": MOTIFS_OUTILS["import du module SQLite"],
    "appel de build_sqlite": re.compile(r"\bbuild_sqlite\b"),
}


def fichiers(dossier: str, suffixes: tuple[str, ...]) -> list[Path]:
    return sorted(p for p in (RACINE / dossier).rglob("*")
                  if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts)


def occurrences(chemin: Path, motifs: dict) -> list[tuple[int, str]]:
    """[(numéro de ligne, nature)] des lignes du fichier qui portent un motif."""
    trouvees = []
    for numero, ligne in enumerate(chemin.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for nature, motif in motifs.items():
            if motif.search(ligne):
                trouvees.append((numero, nature))
    return trouvees


def relatif(chemin: Path) -> str:
    return chemin.relative_to(RACINE).as_posix()


def parcours(dossier: str, suffixes: tuple[str, ...], motifs: dict, ecartes: set, exclus: tuple[Path, ...] = ()) -> list[str]:
    messages = []
    for chemin in fichiers(dossier, suffixes):
        if chemin in exclus or relatif(chemin) in ecartes:
            continue
        for numero, nature in occurrences(chemin, motifs):
            messages.append(f"{relatif(chemin)}:{numero} : {nature}")
    return messages


class OutilsSansSqlite(unittest.TestCase):
    def test_aucun_outil_n_utilise_sqlite(self):
        ecartes = AUTORISES_OUTILS
        messages = parcours("tools", (".py", ".sh"), MOTIFS_OUTILS, ecartes)
        self.assertEqual([], messages, "SQLite dans tools/ :\n" + "\n".join(messages))

    def test_les_listes_d_autorisation_sont_vides(self):
        self.assertEqual(set(), AUTORISES_OUTILS)
        self.assertEqual(set(), AUTORISES_TESTS)

    def test_le_parcours_detecte_les_trois_formes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as dossier:
            cas = {"a.py": "import sqlite3\n", "b.py": "x = 1\nfrom sqlite3 import connect\n", "c.sh": "echo ok\nsqlite3 base.db 'select 1'\n",
                   "d.sh": 'F="$HOME/.pmzilla-lab/library.sqlite-wal"\n', "e.py": 'f = "veille.sqlite.2026-10-01"\n',
                   "f.py": 'subprocess.run(["sqlite3", "x"])\n', "propre.py": "import sqlite\nprint('rien')\n"}
            for nom, texte in cas.items():
                (Path(dossier) / nom).write_text(texte, encoding="utf-8")
            trouves = {nom for nom in cas if occurrences(Path(dossier) / nom, MOTIFS_OUTILS)}
            self.assertEqual({"a.py", "b.py", "c.sh", "d.sh", "e.py", "f.py"}, trouves)
            self.assertEqual([(2, "import du module SQLite")], occurrences(Path(dossier) / "b.py", MOTIFS_OUTILS))


class TestsSansSqlite(unittest.TestCase):
    def test_aucun_test_ne_construit_de_fixture_sqlite(self):
        ecartes = AUTORISES_TESTS
        exclus = tuple(p for p in ICI.glob("*.py"))
        messages = parcours("tests", (".py",), MOTIFS_TESTS, ecartes, exclus)
        self.assertEqual([], messages, "SQLite dans tests/ :\n" + "\n".join(messages))

    def test_un_fichier_marqueur_sqlite_ne_fait_pas_echouer(self):
        texte = 'chemin.with_name("library.sqlite").write_bytes(b"x")\n'
        import tempfile
        with tempfile.TemporaryDirectory() as dossier:
            f = Path(dossier) / "t.py"
            f.write_text(texte, encoding="utf-8")
            self.assertEqual([], occurrences(f, MOTIFS_TESTS))
            f.write_text("import sqlite3\nx = build_sqlite(d)\n", encoding="utf-8")
            self.assertEqual([(1, "import du module SQLite"), (2, "appel de build_sqlite")], occurrences(f, MOTIFS_TESTS))


if __name__ == "__main__":
    unittest.main()
