"""
Test statique de l'usage de la base par les tests (test-speed-2, D9) : aucune base, aucun réseau, aucun lancement de script.

    uv run python -m unittest discover -s tests/db -v

Un fichier de test « avec base » est un fichier Python suivi de tests/ qui renvoie à la garde des tests avec base (base_jetable_disponible,
BASE_DISPONIBLE, ThrowawayDatabase) ou à la classe de base de tests/flow_store/aide_base.py (AvecBase, aide_base). Le test échoue, en
nommant la suite ou le fichier, quand :
  - une suite qui contient un tel fichier manque à la liste par défaut de tools/dbtest.sh ;
  - un tel fichier n'est couvert par aucun motif de CHEMINS_BASE (tools/finish_branch.sh) ;
  - un outil de tools/ touche la base (R-85) et n'est couvert par aucun motif de CHEMINS_BASE : un module Python qui importe psycopg ou
    la couche base (db, flow_store, flow_raw, cases_store, watch_store, knowledge_library, hybrid_search), un module Python qui lance
    tools/db*.py ou tools/db*.sh par un chemin construit, un script shell ou un plist qui lance docker compose, pg_dump, pg_isready ou un script db_*.sh ;
  - un nom de la liste par défaut n'est pas un dossier de suite ;
  - un motif de CHEMINS_BASE ne correspond à aucun fichier suivi.
La liste de CHEMINS_BASE exige un passage vert de tools/dbtest.sh avant la fin d'une branche qui change le code de la base (code 14) :
sans ce test, un fichier avec base ajouté plus tard échapperait à l'exigence.
"""
import fnmatch
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MARQUES = ("base_jetable_disponible", "BASE_DISPONIBLE", "ThrowawayDatabase", "AvecBase", "aide_base", "db.connect(", "psycopg.connect(")

# Outils qui touchent la base (R-85) : trois formes, lues sur le texte, sans l'importer ni le lancer.
IMPORT_BASE = re.compile(r"^\s*(?:import|from)\s+(?:psycopg|db|flow_store|flow_raw|cases_store|watch_store|knowledge_library|hybrid_search)\b", re.M)
APPEL_PYTHON = re.compile(r'/ "db(?:_\w+)?\.(?:py|sh)"')   # tools/db.py, tools/db_up.sh… par un chemin construit
APPEL_SCRIPT = re.compile(r"docker compose|pg_dump|pg_isready|\bdb_(?:up|backup|rehearsal|restore_test)\.sh")
# Outils qui nomment un script de la base sans le lancer : install_links.sh ne fait que lier les scripts dans ~/bin.
EXEMPTES_OUTILS = ("tools/install_links.sh",)


def _bloc(texte: str, ouverture: str) -> list[str]:
    """Les mots entre guillemets ou nus du tableau Bash « ouverture(...) »."""
    m = re.search(r"^" + re.escape(ouverture) + r"=\((.*?)\)\s*$", texte, re.S | re.M)
    if not m:
        return []
    corps = "\n".join(ligne for ligne in m.group(1).splitlines() if not ligne.lstrip().startswith("#"))
    return [entre_guillemets or nu for entre_guillemets, nu in re.findall(r'"([^"]+)"|(\S+)', corps)]


def chemins_base(texte_finish: str) -> list[str]:
    return _bloc(texte_finish, "CHEMINS_BASE")


def suites_defaut(texte_dbtest: str) -> list[str]:
    return _bloc(texte_dbtest, "SUITES_PAR_DEFAUT")


def couvert(chemin: str, motifs: list[str]) -> bool:
    for motif in motifs:
        if motif.endswith("/"):
            if chemin.startswith(motif):
                return True
        elif fnmatch.fnmatchcase(chemin, motif):
            return True
    return False


def suivis_git(racine: Path) -> list[str]:
    sortie = subprocess.run(["git", "-C", str(racine), "ls-files"], capture_output=True, text=True, check=True).stdout
    return sortie.splitlines()


def outil_touche_la_base(chemin: str, texte: str) -> bool:
    """Vrai si l'outil tools/<nom>.py, .sh ou .plist importe ou lance la base ; les commentaires et les echo ne comptent pas."""
    if chemin in EXEMPTES_OUTILS or not re.fullmatch(r"tools/[^/]+\.(py|sh|plist)", chemin):
        return False
    if chemin.endswith(".py"):
        return bool(IMPORT_BASE.search(texte) or APPEL_PYTHON.search(texte))
    lignes = [ligne.strip() for ligne in texte.splitlines()]
    return any(APPEL_SCRIPT.search(ligne) for ligne in lignes if not ligne.startswith(("#", "echo")))


def verifier(racine: Path, suivis: list[str], texte_dbtest: str, texte_finish: str) -> list[str]:
    """Les écarts, un message par écart (liste vide : tout concorde)."""
    motifs = chemins_base(texte_finish)
    defaut = suites_defaut(texte_dbtest)
    suites = {c.split("/")[1] for c in suivis if c.startswith("tests/") and c.count("/") >= 2
              and re.fullmatch(r"test_.*\.(py|sh)", c.rsplit("/", 1)[1])}
    ecarts = []
    avec_base = []
    for chemin in suivis:
        if not chemin.startswith("tests/") or not chemin.endswith(".py"):
            continue   # les gardes et les aides sont du Python ; un test shell qui cite leur nom dans une chaîne n'utilise pas de base
        fichier = racine / chemin
        if not fichier.is_file():
            continue
        texte = fichier.read_text(encoding="utf-8", errors="ignore")
        if any(marque in texte for marque in MARQUES):
            avec_base.append(chemin)
    for chemin in avec_base:
        if not couvert(chemin, motifs):
            ecarts.append(f"fichier avec base non couvert par CHEMINS_BASE : {chemin}")
        suite = chemin.split("/")[1]
        if suite in suites and suite not in defaut:
            message = f"suite avec base absente de la liste par défaut de tools/dbtest.sh : {suite}"
            if message not in ecarts:
                ecarts.append(message)
    for chemin in suivis:
        fichier = racine / chemin
        if not chemin.startswith("tools/") or not fichier.is_file() or couvert(chemin, motifs):
            continue
        if outil_touche_la_base(chemin, fichier.read_text(encoding="utf-8", errors="ignore")):
            ecarts.append(f"outil qui touche la base non couvert par CHEMINS_BASE : {chemin}")
    for nom in defaut:
        if nom not in suites:
            ecarts.append(f"nom de la liste par défaut qui n'est pas une suite : {nom}")
    for motif in motifs:
        if not any(couvert(c, [motif]) for c in suivis):
            ecarts.append(f"motif de CHEMINS_BASE sans fichier suivi : {motif}")
    return ecarts


class TestArbreReel(unittest.TestCase):
    def test_liste_et_chemins_concordent(self):
        ecarts = verifier(RACINE, suivis_git(RACINE), (RACINE / "tools" / "dbtest.sh").read_text(encoding="utf-8"),
                          (RACINE / "tools" / "finish_branch.sh").read_text(encoding="utf-8"))
        self.assertEqual(ecarts, [], "\n".join(ecarts))

    def test_les_deux_listes_sont_lues(self):
        # sans cette lecture, le test ci-dessus serait vide
        defaut = suites_defaut((RACINE / "tools" / "dbtest.sh").read_text(encoding="utf-8"))
        motifs = chemins_base((RACINE / "tools" / "finish_branch.sh").read_text(encoding="utf-8"))
        self.assertIn("db", defaut)
        self.assertIn("db/", motifs)
        self.assertIn("tools/db*", motifs)


class TestArbreFactice(unittest.TestCase):
    """Un arbre minimal : une suite avec base (tests/s1), une suite sans base (tests/s2)."""

    DBTEST = 'SUITES_PAR_DEFAUT=(s1)\n'
    FINISH = 'CHEMINS_BASE=(\n  "tests/s1/test_a.py" "db/"\n)\n'

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        self.racine = Path(self.dossier.name)
        self.suivis = ["db/001.sql", "tests/s1/test_a.py", "tests/s2/test_b.py"]
        self.ecrire("db/001.sql", "SELECT 1;")
        self.ecrire("tests/s1/test_a.py", "BASE_DISPONIBLE = True\n")
        self.ecrire("tests/s2/test_b.py", "pass\n")

    def ecrire(self, chemin, contenu):
        fichier = self.racine / chemin
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(contenu, encoding="utf-8")

    def verifier(self, dbtest=None, finish=None):
        return verifier(self.racine, self.suivis, dbtest or self.DBTEST, finish or self.FINISH)

    def test_arbre_concordant(self):
        self.assertEqual(self.verifier(), [])

    def test_fichier_non_couvert(self):
        self.ecrire("tests/s1/test_c.py", "import aide_base\n")
        self.suivis.append("tests/s1/test_c.py")
        self.assertEqual(self.verifier(), ["fichier avec base non couvert par CHEMINS_BASE : tests/s1/test_c.py"])

    def test_suite_absente_de_la_liste(self):
        ecarts = self.verifier(dbtest="SUITES_PAR_DEFAUT=(s2)\n")
        self.assertIn("suite avec base absente de la liste par défaut de tools/dbtest.sh : s1", ecarts)

    def test_nom_inconnu_dans_la_liste(self):
        ecarts = self.verifier(dbtest="SUITES_PAR_DEFAUT=(s1 fantome)\n")
        self.assertEqual(ecarts, ["nom de la liste par défaut qui n'est pas une suite : fantome"])

    def test_motif_sans_fichier(self):
        ecarts = self.verifier(finish='CHEMINS_BASE=(\n  "tests/s1/test_a.py" "db/" "tools/db*"\n)\n')
        self.assertEqual(ecarts, ["motif de CHEMINS_BASE sans fichier suivi : tools/db*"])

    def test_aide_sans_suite_ne_demande_que_la_couverture(self):
        # un dossier d'aides (aucun test_*.py) n'est pas une suite : il n'a pas à figurer dans la liste par défaut
        self.ecrire("tests/aides/pg.py", "from x import ThrowawayDatabase\n")
        self.suivis.append("tests/aides/pg.py")
        self.assertEqual(self.verifier(), ["fichier avec base non couvert par CHEMINS_BASE : tests/aides/pg.py"])
        self.assertEqual(self.verifier(finish='CHEMINS_BASE=(\n  "tests/s1/test_a.py" "db/" "tests/aides/"\n)\n'), [])

    def outil(self, chemin, contenu):
        self.ecrire(chemin, contenu)
        self.suivis.append(chemin)

    def ecart_outil(self, chemin):
        return f"outil qui touche la base non couvert par CHEMINS_BASE : {chemin}"

    def test_outil_python_qui_importe_la_couche_base(self):
        for i, source in enumerate(("import psycopg\n", "import db\n", "from cases_store import X\n", "def f():\n    import flow_store\n")):
            self.outil(f"tools/o{i}.py", source)
        self.assertEqual(self.verifier(), [self.ecart_outil(f"tools/o{i}.py") for i in range(4)])

    def test_outil_python_qui_lance_un_script_de_la_base(self):
        self.outil("tools/a.py", 'cmd = ["uv", "run", str(racine / "tools" / "db.py"), "status"]\n')
        self.outil("tools/b.py", 'cmd = ["bash", str(racine / "tools" / "db_up.sh")]\n')
        self.assertEqual(self.verifier(), [self.ecart_outil("tools/a.py"), self.ecart_outil("tools/b.py")])

    def test_outil_shell_ou_plist_qui_lance_la_base(self):
        self.outil("tools/s.sh", "cd x && docker compose ps -q\n")
        self.outil("tools/t.sh", 'bash "$RACINE/tools/db_restore_test.sh"\n')
        self.outil("tools/p.plist", "<string>__LAB__/db_backup.sh</string>\n")
        self.assertEqual(self.verifier(), [self.ecart_outil(c) for c in ("tools/s.sh", "tools/t.sh", "tools/p.plist")])

    def test_outil_qui_ne_fait_que_nommer_la_base_est_ignore(self):
        self.outil("tools/c.sh", "# lance docker compose ps\n  echo 'bash tools/db_up.sh'\n")
        self.outil("tools/d.py", '"""Voir tools/db.py et import db."""\nx = 1\n')          # docstring : pas un import en tête de ligne de code
        self.outil("tools/install_links.sh", "  db_backup.sh offsite_backup.sh doctor.sh)\n")   # exempté
        self.outil("tools/dossier/e.py", "import db\n")                                       # hors tools/<nom> : hors du champ
        self.assertEqual(self.verifier(), [])

    def test_outil_couvert_par_un_motif_est_accepte(self):
        self.outil("tools/db_up.sh", "docker compose up\n")
        self.outil("tools/x.py", "import db\n")
        self.assertEqual(self.verifier(finish='CHEMINS_BASE=(\n  "tests/s1/test_a.py" "db/" "tools/db*" "tools/x.py"\n)\n'), [])

    def test_test_qui_se_connecte_sans_autre_marque(self):
        self.ecrire("tests/s1/test_d.py", "conn = db.connect(url)\n")
        self.suivis.append("tests/s1/test_d.py")
        self.assertEqual(self.verifier(), ["fichier avec base non couvert par CHEMINS_BASE : tests/s1/test_d.py"])


class TestTrousComblesDansLArbreReel(unittest.TestCase):
    """R-85 : les outils qui touchaient la base sans figurer dans CHEMINS_BASE y figurent désormais."""

    def test_outils_autrefois_non_couverts(self):
        motifs = chemins_base((RACINE / "tools" / "finish_branch.sh").read_text(encoding="utf-8"))
        for chemin in ("tools/cases_calibration.py", "tools/morning_summary.py", "tools/offsite_backup.sh",
                       "tools/com.pmzilla.db-backup.plist", "tools/install_lab_check.py", "tools/install_lab_database.py",
                       "tools/install_lab_context.py"):
            self.assertTrue(couvert(chemin, motifs), chemin)


if __name__ == "__main__":
    unittest.main()
