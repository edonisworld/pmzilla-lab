"""
Les scripts du lot 6 se lancent avec « uv run tools/<script>.py », sans aucun --with : toutes leurs dépendances, imports indirects et
imports tardifs compris, sont déclarées dans leur bloc `# /// script`.

    uv run --with pyyaml python -m unittest discover -s tests/script_dependencies -v

Deux contrôles :
  - statique (toujours) : les imports de chaque script et de chaque module de tools/ qu'il importe (transitivement, y compris dans les
    fonctions) sont comparés aux dépendances déclarées ;
  - réel (si uv est là) : `uv run --isolated tools/<script>.py --help` dans un environnement propre, sans --with. Sauté, avec la raison,
    si uv ne peut pas résoudre les paquets (pas de réseau ni de cache).
"""
import ast
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
TOOLS = RACINE / "tools"

# scripts exécutables du lot 6 (et ceux qu'il a modifiés)
SCRIPTS = ("flow_import", "flow_compare", "flow_views", "db", "flux_jira", "dependencies_jira", "export_jira_api", "journal_lab", "cases_calibration", "posture_evals", "build_edition", "publish_edition", "install_lab", "flow_monthly", "book_usage", "epic_statuses", "flow_retention", "doctor", "manual", "composants", "morning_summary", "story_quality", "context_lab")
# nom du module importé -> nom du paquet à déclarer
PAQUETS = {"yaml": "pyyaml", "numpy": "numpy", "psycopg": "psycopg", "requests": "requests", "httpx": "httpx", "mcp": "mcp", "jsonschema": "jsonschema",
           "feedparser": "feedparser", "bs4": "beautifulsoup4", "markdownify": "markdownify", "trafilatura": "trafilatura",
           "ebooklib": "ebooklib", "pymupdf": "pymupdf", "pymupdf4llm": "pymupdf4llm"}
ERREURS_RESEAU = ("failed to fetch", "network", "offline", "dns", "connection", "no solution found", "timed out", "tls")


# Outils du dépôt privé seulement : le manifeste de l'édition les exclut, les contrôles ne les exigent donc pas dans l'arbre généré.
PRIVES = {"build_edition", "publish_edition", "migrate_watch"}


def presents(noms):
    return [n for n in noms if n not in PRIVES or (TOOLS / f"{n}.py").exists()]


def dependances_declarees(script: Path) -> set[str]:
    texte = script.read_text(encoding="utf-8")
    bloc = re.search(r"^# /// script\n((?:#.*\n)+?)# ///", texte, re.M)
    if not bloc:
        return set()
    corps = "\n".join(l[1:].strip() for l in bloc.group(1).splitlines())
    dep = re.search(r"dependencies\s*=\s*\[(.*)\]", corps)   # gourmand sur la ligne : « psycopg[binary] » ne coupe pas la liste
    if not dep:
        return set()
    return {re.split(r"[\[<>=! ;]", m.strip().strip("\"'"))[0].lower() for m in dep.group(1).split(",") if m.strip()}


def imports_de(chemin: Path) -> set[str]:
    """Noms de modules importés (premier niveau), à n'importe quelle profondeur du fichier."""
    noms: set[str] = set()
    for noeud in ast.walk(ast.parse(chemin.read_text(encoding="utf-8"))):
        if isinstance(noeud, ast.Import):
            noms.update(a.name.split(".")[0] for a in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0 and noeud.module:
            noms.add(noeud.module.split(".")[0])
    return noms


def tiers_necessaires(script: str) -> tuple[set[str], set[str]]:
    """(modules tiers, modules inconnus) nécessaires au script : ses imports et ceux des modules locaux de tools/ qu'il importe."""
    vus, a_voir, tiers, inconnus = set(), [script], set(), set()
    while a_voir:
        nom = a_voir.pop()
        if nom in vus:
            continue
        vus.add(nom)
        for module in imports_de(TOOLS / f"{nom}.py"):
            if (TOOLS / f"{module}.py").exists():
                a_voir.append(module)
            elif module in sys.stdlib_module_names or module == "__future__":
                continue
            elif module in PAQUETS:
                tiers.add(PAQUETS[module])
            else:
                inconnus.add(module)
    return tiers, inconnus


class Declaration(unittest.TestCase):
    def test_chaque_script_declare_ses_dependances(self):
        for script in presents(SCRIPTS):
            declarees = dependances_declarees(TOOLS / f"{script}.py")
            texte = (TOOLS / f"{script}.py").read_text(encoding="utf-8")
            # un script de bibliothèque standard seulement (install_lab) déclare « dependencies = [] » : le bloc doit exister quand même
            self.assertTrue(declarees or re.search(r"^# dependencies\s*=\s*\[\s*\]", texte, re.M),
                            f"{script}.py : pas de bloc « # /// script » avec dependencies")
            tiers, inconnus = tiers_necessaires(script)
            self.assertEqual(inconnus, set(), f"{script}.py importe des modules inconnus : à ajouter à PAQUETS")
            self.assertEqual(sorted(tiers - declarees), [], f"{script}.py : dépendances non déclarées (imports indirects compris)")

    def test_psycopg_declare_pour_la_lecture_de_la_base(self):
        for script in ("flux_jira", "dependencies_jira", "flow_import", "flow_views", "db"):
            self.assertIn("psycopg", dependances_declarees(TOOLS / f"{script}.py"), script)

    def test_une_extra_entre_crochets_ne_coupe_pas_la_liste(self):
        texte = '# /// script\n# dependencies = ["psycopg[binary]", "numpy", "httpx"]\n# ///\n'
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "essai.py"
            chemin.write_text(texte, encoding="utf-8")
            self.assertEqual(dependances_declarees(chemin), {"psycopg", "numpy", "httpx"})

    def test_le_releve_statique_voit_les_imports_tardifs(self):
        self.assertIn("psycopg", tiers_necessaires("flux_jira")[0])        # import tardif de flow_store, puis de db

    def test_requires_python(self):
        for script in presents(SCRIPTS):
            self.assertRegex((TOOLS / f"{script}.py").read_text(encoding="utf-8")[:200], r"requires-python = \">=3\.1\d\"", script)


# Scripts d'entrée de tools/ (avec « if __name__ == "__main__" ») qui ne sont pas dans SCRIPTS : ils ne sont pas contrôlés par les tests
# ci-dessus. La liste est un cliquet : un nouveau script d'entrée doit être classé (ajouté à SCRIPTS ou ici) pour que le test passe.
EXEMPTES = {"caption_diagnostic", "convert_books", "critic_mirror", "dashboard", "final_messages_check", "flow_board", "history_jira",
            "outside_library", "library_parity", "migrate_watch", "pmzilla_lab_library", "roadmap", "gh_issue",
            "segment_sample", "watch_lab", "watch_triage", "identifiants_personnels", "journal_lab_messages", "sanctum_refresh",
            "select_suites", "sensitive_names", "sort_by_domain", "mapping_lab", "bmad_remplacements", "sorting_exclusions", "watch_paths", "lab_paths",
            "pilot", "pipe_guard", "light_validate"}   # R-75, deny-rules-review : bibliothèque standard seulement, aucun paquet tiers à déclarer ni à verrouiller


EXEMPTES = EXEMPTES | {"posture_eval_fingerprint"}   # posture-evals-on-branch-tip : bibliothèque standard seulement (ligne à part pour ne pas heurter la ligne commune à la fusion)
EXEMPTES = EXEMPTES | {"secret_scan"}   # pre-commit-secret-scan (D1) : bibliothèque standard seulement, importé par le crochet pre-commit sous python3 nu


def scripts_d_entree() -> set[str]:
    return {p.stem for p in TOOLS.glob("*.py") if re.search(r'^if __name__ == ["\']__main__["\']', p.read_text(encoding="utf-8"), re.M)}


# masking-mutation-tests (D1) : mutateur maison, bibliothèque standard seulement (ligne à part, loin des autres ajouts, pour la fusion)
EXEMPTES = EXEMPTES | {"mutation_masking"}
# fix/sorties-et-masquage (point 3) : bibliothèque standard seulement, lancé par les crochets commit-msg et pre-push sous python3 nu
EXEMPTES = EXEMPTES | {"commit_names_scan"}


class Decouverte(unittest.TestCase):
    def test_chaque_script_d_entree_est_controle_ou_explicitement_exempte(self):
        non_classes = sorted(scripts_d_entree() - set(SCRIPTS) - EXEMPTES)
        self.assertEqual(non_classes, [], f"script(s) de tools/ ni contrôlé(s) (SCRIPTS) ni exempté(s) (EXEMPTES) : {non_classes}")

    def test_les_exemptions_et_les_controles_existent(self):
        for nom in (set(SCRIPTS) | EXEMPTES) - PRIVES:
            self.assertTrue((TOOLS / f"{nom}.py").exists(), f"{nom}.py n'existe plus : à retirer de la liste")

    def test_les_scripts_d_entree_exemptes_declarent_aussi_leurs_dependances(self):
        incomplets = []
        for nom in sorted(EXEMPTES & scripts_d_entree()):
            tiers, _ = tiers_necessaires(nom)
            if tiers - dependances_declarees(TOOLS / f"{nom}.py"):
                incomplets.append(nom)
        self.assertEqual(incomplets, [], f"dépendances non déclarées : {incomplets}")


# Règle « pas de version épinglée » (décision du 2026-10-10) : noms de paquets nus, sauf la borne documentée du SDK MCP ; ni manifeste de
# projet ni fichier de verrou à la racine. Un changement de cette règle est une nouvelle décision : il passe par ces constantes.
BORNE_MCP = "mcp>=1.2,<2"
MANIFESTES_INTERDITS = ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile", "uv.lock", "poetry.lock", "Pipfile.lock",
                        "pdm.lock", "package.json", "package-lock.json")


def dependances_brutes(texte: str) -> list[str]:
    """Chaînes de dependencies du bloc `# /// script`, telles qu'écrites (extras et bornes compris), liste sur une ou plusieurs lignes."""
    bloc = re.search(r"^# /// script\n((?:#.*\n)+?)# ///", texte, re.M)
    if not bloc:
        return []
    corps = "\n".join(l[1:].strip() for l in bloc.group(1).splitlines())
    dep = re.search(r"dependencies\s*=\s*\[(.*?)\]\s*(?:\n|$)", corps, re.S)
    return re.findall(r"[\"']([^\"']+)[\"']", dep.group(1)) if dep else []


def versions_non_conformes(dependances: list[str]) -> list[str]:
    """Dépendances qui portent une version ou une borne, hors la borne MCP documentée."""
    return [d for d in dependances if d != BORNE_MCP and re.search(r"[<>=!~@]|==", d)]


def manifestes_presents(racine: Path) -> list[str]:
    return sorted(n for n in MANIFESTES_INTERDITS if (racine / n).exists()) + sorted(p.name for p in racine.glob("requirements*.txt")
                                                                                       if p.name not in MANIFESTES_INTERDITS)


class SansVersionEpinglee(unittest.TestCase):
    def test_les_en_tetes_du_depot_n_epinglent_aucune_version(self):
        fautifs = {}
        for script in sorted(TOOLS.glob("*.py")):
            mauvais = versions_non_conformes(dependances_brutes(script.read_text(encoding="utf-8")))
            if mauvais:
                fautifs[script.name] = mauvais
        self.assertEqual(fautifs, {}, "versions épinglées ou bornes inattendues (nouvelle décision requise)")

    def test_la_borne_mcp_documentee_est_la_seule_admise(self):
        vues = {d for s in TOOLS.glob("*.py") for d in dependances_brutes(s.read_text(encoding="utf-8")) if "mcp" in d}
        self.assertEqual(vues, {BORNE_MCP})

    def test_aucun_manifeste_de_projet_ni_verrou_a_la_racine(self):
        self.assertEqual(manifestes_presents(RACINE), [])

    def test_une_version_exacte_est_detectee(self):
        self.assertEqual(versions_non_conformes(["pyyaml==6.0", "numpy"]), ["pyyaml==6.0"])

    def test_une_borne_inattendue_est_detectee(self):
        self.assertEqual(versions_non_conformes(["httpx>=0.27", "mcp>=1.3,<2", "numpy<2", "x~=1.0", "psycopg[binary]>=3"]),
                         ["httpx>=0.27", "mcp>=1.3,<2", "numpy<2", "x~=1.0", "psycopg[binary]>=3"])

    def test_noms_nus_extras_et_borne_mcp_documentee_sont_acceptes(self):
        self.assertEqual(versions_non_conformes(["pyyaml", "psycopg[binary]", BORNE_MCP]), [])

    def test_le_releve_lit_un_bloc_sur_plusieurs_lignes(self):
        texte = '# /// script\n# dependencies = [\n#   "pyyaml",\n#   "numpy==1.0",\n# ]\n# ///\n'
        self.assertEqual(versions_non_conformes(dependances_brutes(texte)), ["numpy==1.0"])

    def test_un_manifeste_ou_un_verrou_est_detecte(self):
        for nom in ("pyproject.toml", "uv.lock", "requirements.txt", "requirements-dev.txt", "poetry.lock"):
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / nom).write_text("x", encoding="utf-8")
                self.assertEqual(manifestes_presents(Path(d)), [nom], nom)
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(manifestes_presents(Path(d)), [])


@unittest.skipUnless(shutil.which("uv"), "uv absent")
class AideSansWith(unittest.TestCase):
    def test_help_dans_un_environnement_propre(self):
        for script in presents(SCRIPTS):
            r = subprocess.run(["uv", "run", "--isolated", f"tools/{script}.py", "--help"], cwd=RACINE, capture_output=True,
                               text=True, timeout=300)
            sortie = (r.stdout + r.stderr)
            if r.returncode != 0 and any(m in sortie.lower() for m in ERREURS_RESEAU) and "ModuleNotFoundError" not in sortie:
                self.skipTest(f"uv ne peut pas résoudre les paquets ici ({script}) : {sortie.strip().splitlines()[-1][:120]}")
            self.assertEqual(r.returncode, 0, f"{script}.py --help : {sortie[-400:]}")
            self.assertNotIn("ModuleNotFoundError", sortie, script)
            self.assertIn("usage", r.stdout.lower() + r.stderr.lower(), script)


if __name__ == "__main__":
    unittest.main()


# Versions figées (D1 de build-edition, R-36, décision du 2026-10-11 qui remplace R-10) : chaque script d'entrée de tools/ qui déclare
# des dépendances a son fichier `tools/<script>.py.lock` (`uv lock --script`), suivi dans le dépôt et livré dans l'édition ; `uv run` le lit.
def scripts_avec_dependances() -> list[str]:
    return sorted(s for s in scripts_d_entree() if dependances_declarees(TOOLS / f"{s}.py"))


class VersionsFigees(unittest.TestCase):
    def test_chaque_script_d_entree_avec_dependances_a_son_lock(self):
        manquants = [s for s in scripts_avec_dependances() if not (TOOLS / f"{s}.py.lock").exists()]
        self.assertEqual(manquants, [], f"sans fichier .lock (lancer : uv lock --script tools/<script>.py) : {manquants}")

    def test_le_lock_reprend_les_dependances_de_l_en_tete(self):
        """Un lock périmé (dépendance ajoutée ou retirée dans l'en-tête sans relancer uv lock --script) est signalé."""
        import tomllib
        perimes = []
        for s in scripts_avec_dependances():
            verrou = TOOLS / f"{s}.py.lock"
            if not verrou.exists():
                continue
            manifeste = tomllib.loads(verrou.read_text(encoding="utf-8")).get("manifest", {})
            noms = {r["name"].lower() for r in manifeste.get("requirements", [])}
            if noms != {d for d in dependances_declarees(TOOLS / f"{s}.py") if d}:     # « mcp>=1.2,<2 » laisse un morceau vide
                perimes.append(s)
        self.assertEqual(perimes, [], f"lock à régénérer (uv lock --script tools/<script>.py) : {perimes}")

    def test_aucun_lock_orphelin(self):
        orphelins = [p.name for p in TOOLS.glob("*.py.lock") if p.name[:-len(".py.lock")] not in scripts_avec_dependances()]
        self.assertEqual(orphelins, [], f"lock sans script d'entrée avec dépendances : {orphelins}")
