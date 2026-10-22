"""Couverture de la liste déclarée des suites qui lisent le dossier OpenSpec (change light-spec-finish, question Q10, design D6).

    python3 -m unittest discover -s tests/select_suites -v

La liste `tests/openspec_readers.txt` dit au chemin allégé quelles suites lancer ; ce test est la garde : il parcourt chaque suite de
tests/ et signale celle qui lit le dossier `openspec/` de l'arbre réel sans être listée ni exemptée. Il échoue aussi pour une suite
listée ou exemptée qui n'existe pas, et pour une ligne mal formée ou en double. Le balayage lit les commentaires et les docstrings
pour les ignorer, et ne suit pas les dépôts factices : un nom lié à tempfile, mkdtemp, TemporaryDirectory, mktemp ou TMPDIR n'est
jamais la racine réelle.
"""
import importlib.util
import io
import re
import shutil
import subprocess
import tempfile
import tokenize
import unittest
from pathlib import Path

RACINE_REELLE = Path(__file__).resolve().parents[2]
# tools/build_edition.py et tests/build_edition/ sont exclus de l'édition : sans le générateur, l'arbre est celui de l'édition, où la
# suite déclarée build_edition manque par construction.
OUTIL_DE_DEVELOPPEMENT = (RACINE_REELLE / "tools" / "build_edition.py").is_file()
HORS_EDITION = frozenset() if OUTIL_DE_DEVELOPPEMENT else frozenset({"build_edition"})
SPEC = importlib.util.spec_from_file_location("select_suites", RACINE_REELLE / "tools" / "select_suites.py")
SELECTEUR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTEUR)

SEGMENT_OPENSPEC = re.compile(r"(?<![\w.-])openspec(?![\w-])")
MOTS_TEMPORAIRES = ("tempfile", "mkdtemp", "TemporaryDirectory", "mktemp", "TMPDIR")


def _lignes_logiques_python(texte: str) -> list[list[tokenize.TokenInfo]]:
    """Les lignes logiques d'un fichier Python, sans commentaires ni docstrings (instruction réduite à des chaînes)."""
    lignes, courante = [], []
    try:
        for jeton in tokenize.generate_tokens(io.StringIO(texte).readline):
            if jeton.type == tokenize.COMMENT:
                continue
            if jeton.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
                if courante and not all(j.type == tokenize.STRING for j in courante):
                    lignes.append(courante)
                courante = []
            elif jeton.type not in (tokenize.NL, tokenize.INDENT, tokenize.DEDENT):
                courante.append(jeton)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return lignes


def _chaines(ligne: list[tokenize.TokenInfo]) -> list[str]:
    return [j.string for j in ligne if j.type == tokenize.STRING]


def _noms(ligne: list[tokenize.TokenInfo]) -> set[str]:
    return {j.string for j in ligne if j.type == tokenize.NAME}


def _temporaire(ligne: list[tokenize.TokenInfo]) -> bool:
    texte = " ".join(j.string for j in ligne)
    return any(mot in texte for mot in MOTS_TEMPORAIRES)


def _lit_openspec_python(texte: str) -> bool:
    lignes = _lignes_logiques_python(texte)
    racines = {"__file__"}
    for ligne in lignes:   # noms de racine réelle : `NOM = ... __file__ ...` ou `NOM = ... git rev-parse --show-toplevel ...` sans dossier temporaire
        if len(ligne) > 2 and ligne[0].type == tokenize.NAME and ligne[1].string == "=" and not _temporaire(ligne):
            texte_ligne = " ".join(j.string for j in ligne[2:])
            if "__file__" in texte_ligne or ("rev-parse" in texte_ligne and "--show-toplevel" in texte_ligne and "cwd" not in texte_ligne):
                racines.add(ligne[0].string)
    for ligne in lignes:
        if _temporaire(ligne):
            continue
        noms, chaines = _noms(ligne), _chaines(ligne)
        if not noms & racines:
            continue
        if any(SEGMENT_OPENSPEC.search(c) for c in chaines):
            return True
        if _ls_files_sans_pathspec_hors_openspec(ligne) is False:
            return True
    return False


def _ls_files_sans_pathspec_hors_openspec(ligne: list[tokenize.TokenInfo]) -> bool | None:
    """None : pas d'appel `git ls-files` dans la ligne. Sinon True si l'appel a un pathspec qui n'est pas sous openspec (variable comprise,
    inconnue donc supposée étrangère), False s'il n'a aucun pathspec ou un pathspec sous openspec (l'appel liste alors openspec/)."""
    for i, jeton in enumerate(ligne):
        if jeton.type == tokenize.STRING and jeton.string.strip("'\"") == "ls-files":
            elements, courant, profondeur = [], [], 0
            for suivant in ligne[i + 1:]:
                if suivant.string in "([{" and suivant.type == tokenize.OP:
                    profondeur += 1
                elif suivant.string in ")]}" and suivant.type == tokenize.OP:
                    if profondeur == 0:
                        break
                    profondeur -= 1
                if profondeur == 0 and suivant.string == "," and suivant.type == tokenize.OP:
                    elements.append(courant)
                    courant = []
                else:
                    courant.append(suivant)
            if courant:
                elements.append(courant)
            pathspecs = [e for e in elements if e and not (e[0].type == tokenize.STRING and e[0].string.strip("'\"").startswith("-"))]
            if not pathspecs:
                return False
            return not any(SEGMENT_OPENSPEC.search(j.string) for e in pathspecs for j in e if j.type == tokenize.STRING)
    return None


def _lit_openspec_shell(texte: str) -> bool:
    lignes = [re.sub(r"\s#(\s.*)?$", "", ligne) for ligne in texte.splitlines() if not ligne.lstrip().startswith("#")]   # sans commentaires, de ligne ou de fin de ligne
    racines = set()
    for ligne in lignes:
        trouve = re.match(r"\s*(?:export\s+)?(\w+)=(.*)", ligne)
        if trouve and not any(mot in ligne for mot in MOTS_TEMPORAIRES) \
                and re.search(r"\$0\b|BASH_SOURCE|rev-parse --show-toplevel", trouve.group(2)):
            racines.add(trouve.group(1))
    for ligne in lignes:
        if any(mot in ligne for mot in MOTS_TEMPORAIRES):
            continue
        utilisees = [v for v in racines if re.search(r"\$" + v + r"\b|\$\{" + v + r"\b", ligne)]
        if not utilisees:
            continue
        if SEGMENT_OPENSPEC.search(ligne):
            return True
        suite = re.search(r"ls-files(.*)", ligne)
        if suite:
            reste = [m for m in re.findall(r"[^\s|;&)]+", suite.group(1)) if not m.startswith("-") and "$" not in m]
            if not reste or any(SEGMENT_OPENSPEC.search(m) for m in reste):
                return True
    return False


def suites_qui_lisent_openspec(racine: Path) -> set[str]:
    """Les dossiers de tests/ dont un fichier lit `openspec/` dans l'arbre réel (balayage de garde, jamais le sélecteur)."""
    trouvees = set()
    dossier = racine / "tests"
    for suite in sorted(p for p in dossier.iterdir() if p.is_dir()):
        for fichier in sorted(suite.rglob("*")):
            if not fichier.is_file() or "__pycache__" in fichier.parts:
                continue
            texte = fichier.read_text(encoding="utf-8", errors="replace")
            if fichier.suffix == ".py" and _lit_openspec_python(texte):
                trouvees.add(suite.name)
            elif fichier.suffix in (".sh", ".bash") and _lit_openspec_shell(texte):
                trouvees.add(suite.name)
    return trouvees


def problemes(racine: Path, hors_edition: frozenset = frozenset()) -> list[str]:
    """Les écarts entre le balayage et la liste déclarée de `racine` (liste vide : couverture complète) ; une suite de `hors_edition`
    absente de l'arbre n'est pas signalée."""
    try:
        lecteurs, exemptees = SELECTEUR.lire_liste_lecteurs(racine)
    except SELECTEUR.ListeInvalide as erreur:
        return [str(erreur)]
    trouves = []
    for suite in sorted(suites_qui_lisent_openspec(racine) - set(lecteurs) - set(exemptees)):
        trouves.append(f"suite non déclarée qui lit openspec/ : {suite}")
    for suite in sorted(set(lecteurs) | set(exemptees)):
        dossier = racine / "tests" / suite
        if suite in hors_edition and not dossier.exists():
            continue
        if not dossier.is_dir() or not any(f.is_file() and f.name.startswith("test") for f in dossier.rglob("*")):
            trouves.append(f"suite déclarée introuvable : {suite}")
    return trouves


class CouvertureReelle(unittest.TestCase):
    """La liste du dépôt couvre toutes les suites qui lisent openspec/ de l'arbre réel."""

    def test_aucun_ecart_sur_l_arbre_reel(self):
        self.assertEqual(problemes(RACINE_REELLE, HORS_EDITION), [])

    def test_les_quatre_lecteurs_sont_declares(self):
        lecteurs, _ = SELECTEUR.lire_liste_lecteurs(RACINE_REELLE)
        self.assertEqual({"workflow_commands", "roadmap_model", "build_edition", "correspondance_suites"} - set(lecteurs), set())

    def test_le_balayage_signale_les_lecteurs_connus_et_ignore_db(self):
        # `db` liste les fichiers suivis (git ls-files) depuis un paramètre de fonction et n'en garde que tools/ : le balayage ne le signale pas,
        # donc aucune exemption n'est nécessaire (décision de la tâche 10.1, le design D6 la donnait comme candidate).
        trouvees = suites_qui_lisent_openspec(RACINE_REELLE)
        for suite in sorted({"workflow_commands", "roadmap_model", "build_edition", "correspondance_suites"} - HORS_EDITION):
            self.assertIn(suite, trouvees)
        self.assertNotIn("db", trouvees)
        for suite in ("finish_branch", "finish_worktree", "hooks", "select_suites"):
            self.assertNotIn(suite, trouvees)


class BalayageSurRacineFactice(unittest.TestCase):
    """Le balayage sur une racine factice : lecture de la racine réelle signalée, dépôt factice, docstring et commentaire non."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        (self.racine / "tests").mkdir()

    def suite(self, nom: str, fichier: str, texte: str):
        chemin = self.racine / "tests" / nom / fichier
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")

    def trouvees(self) -> set[str]:
        return suites_qui_lisent_openspec(self.racine)

    def test_lecture_de_la_racine_reelle_est_signalee(self):
        self.suite("lit", "test_lit.py", "from pathlib import Path\nRACINE = Path(__file__).resolve().parents[2]\nX = RACINE / 'openspec' / 'config.yaml'\n")
        self.assertEqual(self.trouvees(), {"lit"})

    def test_depot_factice_n_est_pas_signale(self):
        self.suite("factice", "test_factice.py",
                   "import tempfile\nfrom pathlib import Path\nracine = Path(tempfile.mkdtemp())\n(racine / 'openspec').mkdir()\n")
        self.assertEqual(self.trouvees(), set())

    def test_docstring_et_commentaire_ne_sont_pas_signales(self):
        self.suite("texte", "test_texte.py",
                   '"""Lit openspec/test-gaps.md."""\nfrom pathlib import Path\nRACINE = Path(__file__).resolve().parents[2]\n# RACINE / "openspec"\nX = RACINE\n')
        self.assertEqual(self.trouvees(), set())

    def test_git_ls_files_sans_pathspec_est_signale(self):
        self.suite("liste", "test_liste.py",
                   'import subprocess\nfrom pathlib import Path\nRACINE = Path(__file__).resolve().parents[2]\n'
                   'S = subprocess.run(["git", "-C", str(RACINE), "ls-files"], capture_output=True)\n')
        self.assertEqual(self.trouvees(), {"liste"})

    def test_git_ls_files_avec_pathspec_tools_n_est_pas_signale(self):
        self.suite("outils", "test_outils.py",
                   'import subprocess\nfrom pathlib import Path\nRACINE = Path(__file__).resolve().parents[2]\n'
                   'S = subprocess.run(["git", "-C", str(RACINE), "ls-files", "tools"], capture_output=True)\n')
        self.assertEqual(self.trouvees(), set())

    def test_git_ls_files_avec_pathspec_openspec_est_signale(self):
        self.suite("specs", "test_specs.py",
                   'import subprocess\nfrom pathlib import Path\nRACINE = Path(__file__).resolve().parents[2]\n'
                   'S = subprocess.run(["git", "-C", str(RACINE), "ls-files", "openspec"], capture_output=True)\n')
        self.assertEqual(self.trouvees(), {"specs"})

    def test_shell_lecture_de_la_racine_reelle_signalee(self):
        self.suite("sh_lit", "test_lit.sh", 'racine="$(cd "$(dirname "$0")/../.." && pwd)"\ncat "$racine/openspec/config.yaml"\n')
        self.assertEqual(self.trouvees(), {"sh_lit"})

    def test_shell_depot_factice_et_commentaire_ne_sont_pas_signales(self):
        self.suite("sh_factice", "test_factice.sh",
                   'racine="$(cd "$(dirname "$0")/../.." && pwd)"\n# cat "$racine/openspec/x"\ntmp=$(mktemp -d)\nmkdir -p "$tmp/openspec"\n')
        self.assertEqual(self.trouvees(), set())

    def test_shell_git_ls_files_sans_pathspec_signale_avec_pathspec_non(self):
        self.suite("sh_liste", "test_liste.sh", 'racine="$(cd "$(dirname "$0")/../.." && pwd)"\ngit -C "$racine" ls-files\n')
        self.suite("sh_outils", "test_outils.sh", 'racine="$(cd "$(dirname "$0")/../.." && pwd)"\ngit -C "$racine" ls-files tools\n')
        self.assertEqual(self.trouvees(), {"sh_liste"})


class EcartsDeLaListe(unittest.TestCase):
    """Les échecs de la garde : suite non déclarée, suite déclarée introuvable, ligne mal formée ou en double."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.suite("lit", "test_lit.py", "from pathlib import Path\nRACINE = Path(__file__).resolve().parents[2]\nX = RACINE / 'openspec'\n")
        self.suite("autre", "test_autre.py", "X = 1\n")

    def suite(self, nom: str, fichier: str, texte: str):
        chemin = self.racine / "tests" / nom / fichier
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")

    def liste(self, texte: str):
        (self.racine / "tests" / "openspec_readers.txt").write_text(texte, encoding="utf-8")

    def test_lecteur_non_declare_echoue_en_nommant_la_suite(self):
        self.liste("# vide\n")
        self.assertEqual(problemes(self.racine), ["suite non déclarée qui lit openspec/ : lit"])

    def test_lecteur_declare_ou_exempte_passe(self):
        self.liste("lit  # lit la configuration\n")
        self.assertEqual(problemes(self.racine), [])
        self.liste("!lit : liste les fichiers suivis mais ne garde que tools/\n")
        self.assertEqual(problemes(self.racine), [])

    def test_suite_declaree_que_le_balayage_ne_signale_pas_est_permise(self):
        self.liste("lit\nautre  # lit openspec/ par un outil\n")
        self.assertEqual(problemes(self.racine), [])

    def test_suite_declaree_ou_exemptee_inexistante_echoue(self):
        self.liste("lit\nfantome\n!absente : raison\n")
        self.assertEqual(problemes(self.racine), ["suite déclarée introuvable : absente", "suite déclarée introuvable : fantome"])

    def test_suite_sans_fichier_de_test_echoue(self):
        (self.racine / "tests" / "vide").mkdir()
        self.liste("lit\nvide\n")
        self.assertEqual(problemes(self.racine), ["suite déclarée introuvable : vide"])

    def test_ligne_mal_formee_echoue(self):
        for texte in ("lit\nmal formee !\n", "!lit\n", "!lit :   \n", "lit extra\n"):
            self.liste(texte)
            resultat = problemes(self.racine)
            self.assertEqual(len(resultat), 1, texte)
            self.assertIn("ligne", resultat[0])

    def test_suite_en_double_echoue(self):
        self.liste("lit\nlit  # encore\n")
        resultat = problemes(self.racine)
        self.assertEqual(len(resultat), 1)
        self.assertIn("deux fois", resultat[0])
        self.liste("lit\n!lit : raison\n")
        self.assertIn("deux fois", problemes(self.racine)[0])

    def test_fichier_absent_echoue(self):
        resultat = problemes(self.racine)
        self.assertEqual(len(resultat), 1)
        self.assertIn("openspec_readers.txt", resultat[0])


if __name__ == "__main__":
    unittest.main()
