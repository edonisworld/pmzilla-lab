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
(suite transversale, exception d'outil ou dossier de données) dont tous les fichiers sont exclus par le manifeste n'y est pas
signalée comme périmée (extension aux dossiers de données : R-20261109-18. Remplace : rien. Retrait : avec le manifeste de l'édition).
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
    "fixtures_library": "bibliothèque inventée importée par les suites du lot 4 (hybrid_search, library_backend, parity)",
    "fixtures_watch": "faux magasin en mémoire de la veille et du pré-tri (fake_store.py), importé par les suites watch_store, watch_lab, watch_triage, watch_sh et dashboard",
    "e2e": "spec Playwright du passage de bout en bout de Mothra, lancée par tests/run_e2e.sh sous dbtest --e2e, pas une suite du runner",
    "postures": "jeu d'essai des postures (cas, contextes neutres, vocabulaire), lu par posture_evals",
    "sandbox_sonde": "table des cas et verdict de la sonde du bac à sable, lus par la suite sandbox_config et par sonde.sh (K4), pas une suite du runner",   # R-20261109-16 (1)
}

SUITES_TRANSVERSALES = {
    CETTE_SUITE: "contrôle la correspondance entre tools/ et tests/ (R-42)",
    "db_backup_plist": "modèle launchd tools/com.pmzilla.db-backup.plist, pas un script",
    "db_scripts": "scripts shell de la base (db_up.sh, db_backup.sh, db_restore_test.sh, dbtest.sh)",
    "fin_piege": "gabarit du piège de sortie des fichiers de fin tools/etapes/modele-piege-fin.sh, pas un outil (R-148/u14)",
    "finish_codes": "registre des codes de sortie des scripts de fin, tools/finish_codes.yaml (R-148/u17), pas un outil",
    "hooks": "hooks Git de tools/hooks/ (pre-commit, post-commit, commit-msg, pre-push)",
    "installation": "liens et hooks de l'installation (install_links.sh, install_hooks.sh)",
    "forme_p_mac": "mode privilégié -p du vrai /bin/bash 3.2 du Mac sur la forme des enveloppes figées (bash-sandbox-n2, D13, tâche 19.1), pas un tools/<nom>.py ni .sh",
    "finish_train_fin": "tests des codes, des messages et de la question d'arrivée de tools/finish_train.sh, séparés de finish_train pour la durée (R-20261029-38)",
    "finish_train_reprise": "tests de la reprise et du nettoyage de tools/finish_train.sh, séparés de finish_train pour la durée (R-20261029-38)",
    "finish_train_npm": "tests npm de Mothra et du verrou du matin de tools/finish_train.sh, séparés de finish_train pour la durée (R-20261029-38)",
    "finish_train_base": "tests de la base, de la construction, du contenu, du lanceur dbtest et de ls_norm de tools/finish_train.sh, séparés de finish_train pour la durée (R-20261029-38)",
    "library_backend":"choix de la voie de la bibliothèque et tools/knowledge_library.py",
    "mothra_donnees": "jeu synthétique du schéma flow et son chargeur (tests/mothra_donnees/jeu_synthetique.py), pas un outil de tools/ (#240)",
    "mothra_consignes":"consignes de session mothra/CLAUDE.md écrites par l'auteur, pas un outil (mothra-session-guards, D7)",
    "oracle_masquage": "oracle de masquage sans base (tests/oracle_masquage/oracle_masquage.py) contre tools/flow_views.py, pas un outil de tools/ (R-20261104-20)",
    "outils_figes": "enveloppes figées du dossier tools/outils_figes/ (bac à sable N2, K3), pas un tools/<nom>.py ni .sh",
    "parity": "tools/library_parity.py (nom court) et le jeu figé de requêtes",
    "postures_skills": "skills de posture traduits en anglais, pas un outil",
    "private_guards": "réglages réels de la veille suivis (watch/sources.yaml, watch/tri.yaml)",
    "references_postures": "références des postures et sanctum (tools/references_postures.yaml)",
    "sqlite_guard": "garde-fou : plus de SQLite dans tools/ ni dans les fixtures de tests/ (change remove-sqlite)",
    "run_all": "lanceur tests/run_all.sh",
    "script_dependencies": "en-têtes PEP 723 de tous les scripts lancés par uv run",
    "settings_deny": "règles de .claude/settings.json",
    "spec_sources": "lignes « Source: » des specs principales openspec/specs/, pas un outil (R-136)",
    "wake_postures": "scripts/wake.py des quatre postures, hors tools/",
    "watch_sh": "enchaînement de tools/watch.sh (nom court)",
    "workflow_commands": "commandes de travail de .claude/commands/",
}

EXCEPTIONS_OUTILS = {
    "db_rehearsal": "testé par tests/db_scripts/test_db_rehearsal.sh, suite transversale db_scripts (R-86)",
    "db_container_common": "fonctions communes de db_restore_test.sh et db_rehearsal.sh, testées par la suite transversale db_scripts (R-86)",
}

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


def declarations_hors_edition(suivis: list[str], regles: list, transversales: dict, exceptions: dict,
                              donnees: dict | None = None) -> set[str]:
    """Déclarations dont tous les fichiers suivis (tests/<suite>/, tools/<nom>.py ou .sh, tests/<dossier>/ pour un dossier de
    données) sont exclus par le manifeste. `donnees` (R-20261109-18) : DOSSIERS_DE_DONNEES, facultatif."""
    def exclue(fichiers):
        return bool(fichiers) and all(exclu_de_l_edition(p, regles) for p in fichiers)
    noms = {s for s in transversales if exclue([p for p in suivis if p.startswith(f"tests/{s}/")])}
    noms |= {d for d in (donnees or {}) if exclue([p for p in suivis if p.startswith(f"tests/{d}/")])}   # R-20261109-18
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
    for dossier in sorted(set(donnees) - (dossiers - suites) - set(hors_edition)):   # R-20261109-18
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

    @unittest.skipUnless(OUTIL_DE_DEVELOPPEMENT, "outil de développement absent : arbre de l'édition")
    def test_dossier_de_donnees_exclu_non_signale_dans_l_edition(self):   # R-20261109-18
        self.ecrire("tests/privee/cas.yaml")
        donnees = {"privee": "table des cas privée"}
        regles = self.manifeste()
        # Dépôt de développement : le dossier de données est vérifié normalement, rien à signaler.
        self.assertEqual(self.ecarts(donnees=donnees), [])
        edition = arbre_de_l_edition(self.suivis, regles)
        self.assertNotIn("tests/privee/cas.yaml", edition)
        hors = declarations_hors_edition(self.suivis, regles, {}, {}, donnees)
        self.assertEqual(hors, {"privee"})
        # Arbre de l'édition : le dossier a disparu, la déclaration exclue par le manifeste n'est pas signalée.
        self.assertEqual(self.ecarts(donnees=donnees, hors_edition=hors, suivis=edition), [])
        self.assertEqual(len(self.ecarts(donnees=donnees, suivis=edition)), 1)

    @unittest.skipUnless(OUTIL_DE_DEVELOPPEMENT, "outil de développement absent : arbre de l'édition")
    def test_dossier_de_donnees_absent_non_exclu_reste_signale(self):   # R-20261109-18
        regles = self.manifeste()
        donnees = {"fantome": "dossier absent du dépôt"}
        self.assertEqual(declarations_hors_edition(self.suivis, regles, {}, {}, donnees), set())
        [message] = self.ecarts(donnees=donnees)
        self.assertIn("DOSSIERS_DE_DONNEES déclare fantome", message)

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
        hors = set() if regles is not None else set(SUITES_TRANSVERSALES) | set(EXCEPTIONS_OUTILS) | set(DOSSIERS_DE_DONNEES)   # R-20261109-18
        messages = ecarts(RACINE, suivis, DOSSIERS_DE_DONNEES, SUITES_TRANSVERSALES, EXCEPTIONS_OUTILS, hors)
        self.assertEqual(messages, [], "\n" + "\n".join(messages))

    @unittest.skipUnless(OUTIL_DE_DEVELOPPEMENT, "outil de développement absent : arbre de l'édition")
    def test_correspondance_de_l_edition_simulee(self):
        regles = regles_du_manifeste(RACINE)
        if regles is None:
            self.skipTest("arbre de l'édition : pas de manifeste à simuler")
        suivis = self.suivis()
        hors = declarations_hors_edition(suivis, regles, SUITES_TRANSVERSALES, EXCEPTIONS_OUTILS,
                                         DOSSIERS_DE_DONNEES)   # R-20261109-18
        messages = ecarts(RACINE, arbre_de_l_edition(suivis, regles), DOSSIERS_DE_DONNEES, SUITES_TRANSVERSALES,
                          EXCEPTIONS_OUTILS, hors)
        self.assertEqual(messages, [], "\n" + "\n".join(messages))

    def test_chaque_declaration_a_sa_raison(self):
        for liste in (DOSSIERS_DE_DONNEES, SUITES_TRANSVERSALES, EXCEPTIONS_OUTILS):
            for nom, raison in liste.items():
                self.assertTrue(raison.strip(), nom)


if __name__ == "__main__":
    unittest.main()
