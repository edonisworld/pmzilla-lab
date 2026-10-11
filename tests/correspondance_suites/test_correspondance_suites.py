"""
Correspondance entre outils et suites de tests (R-42) : chaque suite de tests/ vise un outil existant, chaque outil a sa suite.

    bash tests/run_all.sh correspondance_suites

Sur les fichiers suivis par Git, le test échoue en nommant quoi ajouter ou retirer quand :
  - un dossier tests/<dossier>/ suivi ne contient aucun fichier de test suivi (test_*.py ou test_*.sh), sauf s'il est déclaré
    dossier de données (DOSSIERS_DE_DONNEES) ; les dossiers non suivis (qui ne contiennent que __pycache__) sont ignorés ;
  - une suite déclarée transversale porte le nom d'un outil, ou ne contient plus de test (déclaration périmée) ;
  - une suite sans outil homonyme (tools/<nom>.py ou .sh) n'est pas déclarée transversale (SUITES_TRANSVERSALES) ;
  - un tools/*.py ou tools/*.sh n'a de suite ni par son nom, ni par la correspondance de tools/select_suites.py (une suite dont les
    tests nomment le fichier), ni dans les exceptions justifiées (EXCEPTIONS_OUTILS) ; une exception devenue inutile est signalée.
Une seule source de vérité pour la correspondance : tools/select_suites.py (suites_python, suites_shell, textes_des_suites,
suites_du_chemin). Seules les suites non transversales comptent : une suite transversale (settings_deny, script_dependencies…)
nomme des outils sans les tester, et cette suite-ci nomme les outils dans ses listes.
Les sous-dossiers de tools/ (hooks/, vendor/) sont hors champ : seuls tools/*.py et tools/*.sh sont contrôlés.
Édition anglaise : une seule source, edition/manifest.yaml. Dans le dépôt de développement (manifeste présent), toute déclaration est
vérifiée normalement, et un test simule l'arbre de l'édition (fichiers suivis moins ceux que le manifeste exclut) : une déclaration
(suite transversale ou exception d'outil) dont tous les fichiers sont exclus par le manifeste n'y est pas signalée comme périmée.
Dans l'arbre généré (manifeste absent, exclu par lui-même), une déclaration absente de l'arbre n'est donc pas signalée : la
simulation du dépôt de développement garantit que seules les déclarations exclues par le manifeste y manquent.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import select_suites  # noqa: E402

CETTE_SUITE = "correspondance_suites"

DOSSIERS_DE_DONNEES = {
    "fixtures_library": "bibliothèque inventée importée par les suites du lot 4 (knowledge_import, hybrid_search, library_backend, parity)",
    "postures": "jeu d'essai des postures (cas, contextes neutres, vocabulaire), lu par posture_evals",
}

SUITES_TRANSVERSALES = {
    CETTE_SUITE: "contrôle la correspondance entre tools/ et tests/ (R-42)",
    "db_backup_plist": "modèle launchd tools/com.pmzilla.db-backup.plist, pas un script",
    "db_scripts": "scripts shell de la base (db_up.sh, db_backup.sh, db_restore_test.sh, dbtest.sh)",
    "hooks": "hooks Git de tools/hooks/ (pre-commit, post-commit, commit-msg, pre-push)",
    "installation": "liens et hooks de l'installation (install_links.sh, install_hooks.sh)",
    "library_backend": "choix de la voie de la bibliothèque et tools/knowledge_library.py",
    "parity": "tools/library_parity.py (nom court) et le jeu figé de requêtes",
    "postures_skills": "skills de posture traduits en anglais, pas un outil",
    "private_guards": "réglages réels de la veille suivis (watch/sources.yaml, watch/tri.yaml)",
    "references_postures": "références des postures et sanctum (tools/references_postures.yaml)",
    "run_all": "lanceur tests/run_all.sh",
    "script_dependencies": "en-têtes PEP 723 de tous les scripts lancés par uv run",
    "settings_deny": "règles de .claude/settings.json",
    "wake_postures": "scripts/wake.py des quatre postures, hors tools/",
    "watch_sh": "enchaînement de tools/watch.sh (nom court)",
    "workflow_commands": "commandes de travail de .claude/commands/",
}

EXCEPTIONS_OUTILS = {}

MOTIF_TEST = re.compile(r"^tests/([^/]+)/(?:.+/)?test_[^/]*\.(?:py|sh)$")
MOTIF_OUTIL = re.compile(r"^tools/([^/]+)\.(?:py|sh)$")
MANIFESTE = "edition/manifest.yaml"
# Lire le manifeste importe tools/build_edition.py, exclu de l'édition : sans lui, les tests qui le lisent sautent et
# le dépôt est traité comme l'arbre de l'édition.
OUTIL_DE_DEVELOPPEMENT = (RACINE / "tools/build_edition.py").is_file()


def regles_du_manifeste(racine: Path) -> list | None:
    """[(correspondance, action)] du manifeste de l'édition, dans l'ordre ; None sans manifeste (arbre de l'édition)."""
    chemin = racine / MANIFESTE
    if not chemin.is_file():
        return None
    import yaml  # noqa: E402
    import build_edition  # noqa: E402  (même règle de correspondance que le générateur)
    donnees = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    if isinstance(donnees, dict):
        donnees = donnees.get("rules") or []
    return [(build_edition.make_matcher(r["path"]), r["action"]) for r in donnees]


def exclu_de_l_edition(chemin: str, regles: list) -> bool:
    """La première règle qui correspond décide, comme dans tools/build_edition.py."""
    return next((action == "exclude" for correspond, action in regles if correspond(chemin)), False)


def arbre_de_l_edition(suivis: list[str], regles: list) -> list[str]:
    return [p for p in suivis if not exclu_de_l_edition(p, regles)]


def declarations_hors_edition(suivis: list[str], regles: list, transversales: dict, exceptions: dict) -> set[str]:
    """Déclarations dont tous les fichiers suivis (tests/<suite>/, tools/<nom>.py ou .sh) sont exclus par le manifeste."""
    def exclue(fichiers):
        return bool(fichiers) and all(exclu_de_l_edition(p, regles) for p in fichiers)
    noms = {s for s in transversales if exclue([p for p in suivis if p.startswith(f"tests/{s}/")])}
    return noms | {n for n in exceptions if exclue([p for p in suivis if p in (f"tools/{n}.py", f"tools/{n}.sh")])}


def ecarts(racine: Path, suivis: list[str], donnees: dict, transversales: dict, exceptions: dict,
           hors_edition: set = frozenset()) -> list[str]:
    """Messages d'écart (vide si tout correspond). `suivis` : chemins suivis par Git, relatifs à `racine`. `hors_edition` :
    déclarations exclues de l'édition, non signalées quand elles sont absentes de l'arbre."""
    dossiers = {p.split("/")[1] for p in suivis if p.startswith("tests/") and p.count("/") >= 2}
    suites = {m.group(1) for p in suivis if (m := MOTIF_TEST.match(p))}
    outils = {m.group(1): p for p in suivis if (m := MOTIF_OUTIL.match(p))}
    messages = []
    for dossier in sorted(dossiers - suites - set(donnees)):
        messages.append(f"tests/{dossier}/ suivi sans fichier de test suivi : ajouter un test_*.py ou test_*.sh, "
                        f"retirer le dossier, ou le déclarer dans DOSSIERS_DE_DONNEES avec sa raison")
    for dossier in sorted(set(donnees) - (dossiers - suites)):
        messages.append(f"DOSSIERS_DE_DONNEES déclare {dossier} : dossier absent ou devenu suite, retirer la déclaration")
    for suite in sorted(suites):
        if suite in outils and suite in transversales:
            messages.append(f"suite {suite} déclarée transversale alors que {outils[suite]} existe : retirer la déclaration")
        elif suite not in outils and suite not in transversales:
            messages.append(f"suite {suite} sans tools/{suite}.py ni .sh : la renommer d'après l'outil testé, la retirer, "
                            f"ou la déclarer dans SUITES_TRANSVERSALES avec sa raison")
    for suite in sorted(set(transversales) - suites - set(hors_edition)):
        messages.append(f"SUITES_TRANSVERSALES déclare {suite} : aucune suite de ce nom, retirer la déclaration")
    exclues = set(transversales) | {CETTE_SUITE}
    py = [s for s in select_suites.suites_python(racine) if s in suites and s not in exclues]
    shell = {c: n for c, n in select_suites.suites_shell(racine).items() if c in suivis and c.split("/")[1] not in exclues}
    textes = select_suites.textes_des_suites(racine, py, shell)
    for nom, chemin in sorted(outils.items()):
        couvert = nom in suites or bool(select_suites.suites_du_chemin(chemin, py, shell, textes))
        if not couvert and nom not in exceptions:
            messages.append(f"{chemin} sans suite : ajouter tests/{nom}/, le nommer dans les tests d'une suite, "
                            f"ou le déclarer dans EXCEPTIONS_OUTILS avec sa raison")
        elif couvert and nom in exceptions:
            messages.append(f"EXCEPTIONS_OUTILS déclare {nom} alors qu'une suite le couvre : retirer l'exception")
    for nom in sorted(set(exceptions) - set(outils) - set(hors_edition)):
        messages.append(f"EXCEPTIONS_OUTILS déclare {nom} : tools/{nom}.py ou .sh absent, retirer l'exception")
    return messages


class FauxDepot(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self._tmp.name)
        self.suivis = []

    def tearDown(self):
        self._tmp.cleanup()

    def ecrire(self, chemin: str, texte: str = "", suivi: bool = True):
        fichier = self.racine / chemin
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(texte, encoding="utf-8")
        if suivi:
            self.suivis.append(chemin)

    def ecarts(self, donnees=None, transversales=None, exceptions=None, hors_edition=frozenset(), suivis=None):
        return ecarts(self.racine, self.suivis if suivis is None else suivis, donnees or {}, transversales or {},
                      exceptions or {}, hors_edition)

    def test_tout_correspond(self):
        self.ecrire("tools/alpha.py")
        self.ecrire("tests/alpha/test_alpha.py")
        self.assertEqual(self.ecarts(), [])

    def test_dossier_suivi_sans_test(self):
        self.ecrire("tests/donnees/cas.yaml")
        [message] = self.ecarts()
        self.assertIn("tests/donnees/", message)
        self.assertEqual(self.ecarts(donnees={"donnees": "jeu d'essai"}), [])

    def test_dossier_non_suivi_ignore(self):
        self.ecrire("tests/vieux/__pycache__/test_vieux.cpython-312.pyc", suivi=False)
        self.assertEqual(self.ecarts(), [])

    def test_suite_sans_outil_homonyme(self):
        self.ecrire("tests/regles/test_regles.py")
        [message] = self.ecarts()
        self.assertIn("suite regles", message)
        self.assertEqual(self.ecarts(transversales={"regles": "réglages"}), [])

    def test_transversale_perimee_ou_homonyme(self):
        self.ecrire("tools/alpha.py")
        self.ecrire("tests/alpha/test_alpha.py")
        messages = self.ecarts(transversales={"alpha": "x", "disparue": "y"})
        self.assertTrue(any("alpha" in m and "retirer la déclaration" in m for m in messages))
        self.assertTrue(any("disparue" in m for m in messages))

    def test_outil_sans_suite(self):
        self.ecrire("tools/orphelin.sh")
        [message] = self.ecarts()
        self.assertIn("tools/orphelin.sh sans suite", message)
        self.assertEqual(self.ecarts(exceptions={"orphelin": "à traiter"}), [])

    def test_outil_couvert_par_la_correspondance_du_selecteur(self):
        self.ecrire("tools/alpha.py")
        self.ecrire("tools/alpha_messages.py")
        self.ecrire("tests/alpha/test_alpha.py", "import alpha_messages\n")
        self.assertEqual(self.ecarts(), [])
        [message] = self.ecarts(exceptions={"alpha_messages": "inutile"})
        self.assertIn("retirer l'exception", message)

    def test_cette_suite_ne_compte_pas_comme_correspondance(self):
        self.ecrire("tools/orphelin.py")
        self.ecrire(f"tests/{CETTE_SUITE}/test_{CETTE_SUITE}.py", "orphelin\n")
        messages = self.ecarts(transversales={CETTE_SUITE: "contrôle"})
        self.assertEqual(len(messages), 1)
        self.assertIn("tools/orphelin.py sans suite", messages[0])

    def test_une_suite_transversale_ne_couvre_pas_un_outil(self):
        self.ecrire("tools/orphelin.py")
        self.ecrire("tests/regles/test_regles.py", "import orphelin\n")
        [message] = self.ecarts(transversales={"regles": "réglages"})
        self.assertIn("tools/orphelin.py sans suite", message)
        self.ecrire("tools/alpha.py")
        self.ecrire("tests/alpha/test_alpha.py", "import orphelin\n")
        self.assertEqual(self.ecarts(transversales={"regles": "réglages"}), [])

    def test_exception_d_un_outil_absent(self):
        [message] = self.ecarts(exceptions={"fantome": "x"})
        self.assertIn("fantome", message)

    def test_sous_dossiers_de_tools_hors_champ(self):
        self.ecrire("tools/vendor/echarts.js")
        self.ecrire("tools/hooks/pre_commit.sh")
        self.assertEqual(self.ecarts(), [])


    def test_une_suite_non_suivie_ne_couvre_pas_un_outil(self):
        self.ecrire("tools/orphelin.py")
        self.ecrire("tests/fantome/test_fantome.py", "import orphelin\n", suivi=False)
        [message] = self.ecarts()
        self.assertIn("tools/orphelin.py sans suite", message)

    def test_declaration_hors_edition_absente_non_signalee(self):
        self.assertEqual(self.ecarts(transversales={"privee": "x"}, exceptions={"prive": "y"},
                                     hors_edition={"privee", "prive"}), [])
        messages = self.ecarts(transversales={"privee": "x"}, exceptions={"prive": "y"})
        self.assertEqual(len(messages), 2)

    def test_declaration_hors_edition_presente_reste_verifiee(self):
        self.ecrire("tools/alpha.py")
        self.ecrire("tests/alpha/test_alpha.py")
        [message] = self.ecarts(transversales={"alpha": "x"}, hors_edition={"alpha"})
        self.assertIn("suite alpha déclarée transversale alors que tools/alpha.py existe", message)

    def manifeste(self):
        self.ecrire(MANIFESTE, "rules:\n"
                               "  - path: tests/privee/\n    action: exclude\n    reason: privée\n"
                               "  - path: tools/prive.py\n    action: exclude\n    reason: privé\n"
                               "  - path: '**'\n    action: include\n")
        return regles_du_manifeste(self.racine)

    @unittest.skipUnless(OUTIL_DE_DEVELOPPEMENT, "outil de développement absent : arbre de l'édition")
    def test_arbre_de_l_edition_simule(self):
        self.ecrire("tools/alpha.py")
        self.ecrire("tests/alpha/test_alpha.py")
        self.ecrire("tests/privee/test_privee.py")
        self.ecrire("tools/prive.py")
        transversales, exceptions = {"privee": "réglages réels", "perimee": "z"}, {"prive": "à traiter"}
        regles = self.manifeste()
        # Dépôt de développement : vérification normale, seule la déclaration sans suite est signalée.
        [message] = self.ecarts(transversales=transversales, exceptions=exceptions)
        self.assertIn("SUITES_TRANSVERSALES déclare perimee", message)
        # Arbre de l'édition : les déclarations exclues par le manifeste ne sont pas signalées, les autres le restent.
        edition = arbre_de_l_edition(self.suivis, regles)
        self.assertNotIn("tests/privee/test_privee.py", edition)
        self.assertNotIn("tools/prive.py", edition)
        hors = declarations_hors_edition(self.suivis, regles, transversales, exceptions)
        self.assertEqual(hors, {"privee", "prive"})
        [message] = self.ecarts(transversales=transversales, exceptions=exceptions, hors_edition=hors, suivis=edition)
        self.assertIn("SUITES_TRANSVERSALES déclare perimee", message)
        self.assertEqual(len(self.ecarts(transversales=transversales, exceptions=exceptions, suivis=edition)), 3)

    @unittest.skipUnless(OUTIL_DE_DEVELOPPEMENT, "outil de développement absent : arbre de l'édition")
    def test_suite_en_partie_exclue_reste_declaree(self):
        self.ecrire("tests/privee/test_privee.py")
        self.ecrire("tests/privee/test_public.py")
        self.ecrire(MANIFESTE, "rules:\n  - path: tests/privee/test_privee.py\n    action: exclude\n    reason: x\n"
                               "  - path: '**'\n    action: include\n")
        regles = regles_du_manifeste(self.racine)
        self.assertEqual(declarations_hors_edition(self.suivis, regles, {"privee": "x"}, {}), set())

    def test_sans_manifeste(self):
        self.assertIsNone(regles_du_manifeste(self.racine))


class DepotReel(unittest.TestCase):
    def suivis(self) -> list[str]:
        fait = subprocess.run(["git", "ls-files", "-z"], cwd=RACINE, capture_output=True)
        if fait.returncode != 0:
            self.skipTest("hors dépôt Git")
        return [p for p in fait.stdout.decode("utf-8", errors="replace").split("\0") if p]

    def test_correspondance_du_depot(self):
        suivis = self.suivis()
        regles = regles_du_manifeste(RACINE) if OUTIL_DE_DEVELOPPEMENT else None
        # Manifeste présent (dépôt de développement) : tout est vérifié. Absent (arbre de l'édition) : voir l'en-tête.
        hors = set() if regles is not None else set(SUITES_TRANSVERSALES) | set(EXCEPTIONS_OUTILS)
        messages = ecarts(RACINE, suivis, DOSSIERS_DE_DONNEES, SUITES_TRANSVERSALES, EXCEPTIONS_OUTILS, hors)
        self.assertEqual(messages, [], "\n" + "\n".join(messages))

    @unittest.skipUnless(OUTIL_DE_DEVELOPPEMENT, "outil de développement absent : arbre de l'édition")
    def test_correspondance_de_l_edition_simulee(self):
        regles = regles_du_manifeste(RACINE)
        if regles is None:
            self.skipTest("arbre de l'édition : pas de manifeste à simuler")
        suivis = self.suivis()
        hors = declarations_hors_edition(suivis, regles, SUITES_TRANSVERSALES, EXCEPTIONS_OUTILS)
        messages = ecarts(RACINE, arbre_de_l_edition(suivis, regles), DOSSIERS_DE_DONNEES, SUITES_TRANSVERSALES,
                          EXCEPTIONS_OUTILS, hors)
        self.assertEqual(messages, [], "\n" + "\n".join(messages))

    def test_chaque_declaration_a_sa_raison(self):
        for liste in (DOSSIERS_DE_DONNEES, SUITES_TRANSVERSALES, EXCEPTIONS_OUTILS):
            for nom, raison in liste.items():
                self.assertTrue(raison.strip(), nom)


if __name__ == "__main__":
    unittest.main()
