"""tools/mutation_masking.py : tests de mutation du masquage et des rôles (change masking-mutation-tests, design D1 à D8 ;
spec tooling-mutation-tests).

Chaque test écrit son propre module factice et ses propres suites factices dans un dépôt Git temporaire (tempfile) : l'outil RÉEL est
appelé dans le processus (main(argv, racine=…, perimetre=…, lanceur=…)) avec l'interpréteur de ce test. Aucune base, aucun réseau,
aucune écriture dans le dépôt. Un seul test lit le dépôt réel : il copie ses fichiers suivis dans un dossier temporaire et y vérifie que
le mutant du plancher (5 devient 4) fait échouer tests/flow_views.

    uv run python -m unittest discover -s tests/mutation_masking
"""
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import mutation_masking as mm  # noqa: E402

LANCEUR = (sys.executable, "-W", "ignore")
SEUIL_FICHIER = "tools/mutation_masking_seuil.txt"

OPERATEURS = textwrap.dedent('''\
    SEUIL = 5
    ACTIF = True


    def masquer(n):
        if n < SEUIL:
            return None
        return n


    def plus_grand(a, b):
        return max(a, b)


    def membre(x, liste):
        return x in liste


    def inverse(drapeau):
        return not drapeau


    def hors_perimetre(n):
        return n < 3 and max(n, 1) and not n
    ''')

# Module factice des passages complets : SEUIL et masquer sont dans le périmètre, hors_perimetre jamais.
FACTICE = textwrap.dedent('''\
    SEUIL = 5


    def masquer(n):
        if n < SEUIL:
            return None
        return n


    def hors_perimetre(n):
        return n < 3
    ''')

# Les tests factices tuent les trois mutants de masquer ; les deux mutants de SEUIL (6 et 4) survivent : score 60 %.
TEST_FACTICE = textwrap.dedent('''\
    import json
    import os
    import sys
    import unittest
    from pathlib import Path

    RACINE = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(RACINE / "tools"))
    import factice  # noqa: E402


    class Factice(unittest.TestCase):
        def test_masquer(self):
            sortie = os.environ.get("MUTATION_TEST_SORTIE")
            if sortie:
                Path(sortie).write_text(json.dumps({"env": dict(os.environ), "fichiers": sorted(
                    str(p.relative_to(RACINE)) for p in RACINE.rglob("*") if p.is_file())}), encoding="utf-8")
            self.assertIsNone(factice.masquer(3))
            self.assertEqual(factice.masquer(7), 7)
    ''')


def git(dossier, *args):
    subprocess.run(["git", "-c", "user.name=essai", "-c", "user.email=essai@example.invalid", "-c", "core.hooksPath=/dev/null",
                    "-c", "commit.gpgsign=false", *args], cwd=dossier, check=True, capture_output=True)


def empreinte(dossier: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(dossier.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(dossier)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


class Depot:
    """Dépôt Git temporaire : un module factice, une suite factice, le fichier de seuil, un dossier ignoré avec une sentinelle."""

    def __init__(self, module=FACTICE, test=TEST_FACTICE, seuil="# seuil\n60\n80\n"):
        self._tmp = tempfile.TemporaryDirectory(prefix="essai-mutation-")
        self.racine = Path(self._tmp.name) / "depot"
        (self.racine / "tools").mkdir(parents=True)
        (self.racine / "tests" / "factice").mkdir(parents=True)
        (self.racine / "ignore").mkdir()
        (self.racine / "tools" / "factice.py").write_text(module, encoding="utf-8")
        (self.racine / "tests" / "factice" / "test_factice.py").write_text(test, encoding="utf-8")
        if seuil is not None:
            (self.racine / SEUIL_FICHIER).write_text(seuil, encoding="utf-8")
        (self.racine / ".gitignore").write_text("ignore/\n", encoding="utf-8")
        (self.racine / "ignore" / "sentinelle.txt").write_text("ne jamais copier", encoding="utf-8")
        git(self.racine, "init", "-q")
        git(self.racine, "add", "-A")
        git(self.racine, "commit", "-qm", "essai")
        self.donnees = Path(self._tmp.name) / "donnees"
        self.sortie = Path(self._tmp.name) / "sortie.json"

    def fermer(self):
        self._tmp.cleanup()


PERIMETRE = (mm.Cible("tools/factice.py", ("SEUIL", "masquer"), (("tests/factice", None),)),)


class Base(unittest.TestCase):
    def setUp(self):
        self.depots = []

    def tearDown(self):
        for d in self.depots:
            d.fermer()

    def depot(self, **kw) -> Depot:
        d = Depot(**kw)
        self.depots.append(d)
        return d

    def lancer(self, depot, argv=("run",), perimetre=PERIMETRE, env=None, today="2026-10-20"):
        variables = {"PMZILLA_LAB_DATA": str(depot.donnees), "PMZILLA_LAB_TODAY": today, **(env or {})}
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, variables), contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = mm.main(list(argv), racine=depot.racine, perimetre=perimetre, lanceur=LANCEUR)
        return code, sortie.getvalue() + erreur.getvalue()


class Operateurs(unittest.TestCase):
    """Chaque opérateur produit le mutant attendu (D1), sur les seuls noms déclarés."""

    NOMS = ("SEUIL", "ACTIF", "masquer", "plus_grand", "membre", "inverse")

    def mutants(self):
        lignes = []
        for m in mm.points(OPERATEURS, self.NOMS, "tools/factice.py"):
            mute = mm.appliquer(OPERATEURS, m)
            compile(mute, "factice.py", "exec")
            lignes.append((m.operateur, m.ligne, mute.splitlines()[m.ligne - 1], m.fonction))
        return lignes

    def test_chaque_operateur_produit_le_mutant_attendu(self):
        attendus = {
            ("constante", 1, "SEUIL = 6", "SEUIL"),
            ("constante", 1, "SEUIL = 4", "SEUIL"),
            ("negation", 2, "ACTIF = False", "ACTIF"),
            ("comparaison", 6, "    if n >= SEUIL:", "masquer"),
            ("negation", 6, "    if not (n < SEUIL):", "masquer"),
            ("retour_none", 8, "    return None", "masquer"),
            ("max_min", 12, "    return min(a, b)", "plus_grand"),
            ("retour_none", 12, "    return None", "plus_grand"),
            ("appartenance", 16, "    return x not in liste", "membre"),
            ("retour_none", 16, "    return None", "membre"),
            ("negation", 20, "    return (drapeau)", "inverse"),
            ("retour_none", 20, "    return None", "inverse"),
        }
        self.assertEqual(set(self.mutants()), attendus)

    def test_une_fonction_hors_perimetre_n_est_jamais_mutee(self):
        for operateur, ligne, _, fonction in self.mutants():
            self.assertNotEqual(fonction, "hors_perimetre")
            self.assertLess(ligne, 23, operateur)

    def test_le_mutant_ne_change_que_sa_ligne(self):
        for m in mm.points(OPERATEURS, self.NOMS, "tools/factice.py"):
            avant, apres = OPERATEURS.splitlines(), mm.appliquer(OPERATEURS, m).splitlines()
            self.assertEqual(len(avant), len(apres))
            self.assertEqual([i + 1 for i, (a, b) in enumerate(zip(avant, apres)) if a != b], [m.ligne])

    def test_inversions_des_comparaisons(self):
        source = "def f(a, b):\n    return (a <= b, a > b, a >= b, a == b, a != b, a is b, a is not b)\n"
        textes = sorted(mm.appliquer(source, m).splitlines()[1] for m in mm.points(source, ("f",), "x.py")
                        if m.operateur == "comparaison")
        self.assertEqual(textes, sorted([
            "    return (a > b, a > b, a >= b, a == b, a != b, a is b, a is not b)",
            "    return (a <= b, a <= b, a >= b, a == b, a != b, a is b, a is not b)",
            "    return (a <= b, a > b, a < b, a == b, a != b, a is b, a is not b)",
            "    return (a <= b, a > b, a >= b, a != b, a != b, a is b, a is not b)",
            "    return (a <= b, a > b, a >= b, a == b, a == b, a is b, a is not b)",
            "    return (a <= b, a > b, a >= b, a == b, a != b, a is not b, a is not b)",
            "    return (a <= b, a > b, a >= b, a == b, a != b, a is b, a is b)",
        ]))

    def test_min_devient_max_et_condition_ternaire_niee(self):
        source = "def f(a):\n    return min(a, 1) if a else 0\n"
        textes = {(m.operateur, mm.appliquer(source, m).splitlines()[1]) for m in mm.points(source, ("f",), "x.py")}
        self.assertIn(("max_min", "    return max(a, 1) if a else 0"), textes)
        self.assertIn(("negation", "    return min(a, 1) if not (a) else 0"), textes)

    def test_aucune_mutation_dans_une_chaine_formatee(self):
        source = 'def f(n):\n    return f"<{n + 5}"\n'
        self.assertEqual([m.operateur for m in mm.points(source, ("f",), "x.py")], ["retour_none"])


class PassageComplet(Base):
    def test_mutants_tues_et_survivants_comptes_seuil_atteint(self):
        d = self.depot()
        code, sortie = self.lancer(d)
        self.assertEqual(code, 0, sortie)
        self.assertIn("mutation : cible tools/factice.py : 3 tués sur 5, score 60 %", sortie)
        self.assertIn("mutation : 3 mutants tués sur 5 (dont 0 en délai), score 60 %, seuil 60 %, cible 80 %", sortie)
        survivants = [l for l in sortie.splitlines() if l.startswith("mutation : survivant ")]
        self.assertEqual(survivants, ["mutation : survivant tools/factice.py:SEUIL ligne 1 (constante)"] * 2)
        self.assertNotIn("hors_perimetre", sortie)

    def test_sous_le_seuil_code_3_et_survivants_listes(self):
        d = self.depot(seuil="70\n80\n")
        code, sortie = self.lancer(d)
        self.assertEqual(code, 3, sortie)
        self.assertIn("mutation : score 60 % sous le seuil 70 %", sortie)
        self.assertEqual(sortie.count("mutation : survivant "), 2)

    def test_l_arbre_source_reste_inchange(self):
        d = self.depot()
        avant = empreinte(d.racine)
        self.lancer(d)
        self.assertEqual(empreinte(d.racine), avant)

    def test_la_copie_ne_tient_que_les_fichiers_suivis_et_aucune_valeur_de_base(self):
        d = self.depot()
        FAUX_1, FAUX_2 = "secret-" + "qq-1", "secret-" + "qq-2"   # fabriqués à l'exécution : aucun littéral pour la garde des secrets
        exportees = {"PMZILLA_LAB_DB_PASSWORD": FAUX_1, "PMZILLA_LAB_DB_URL": "postgresql://u@hote-qq:9/x",
                     "PMZILLA_LAB_DB_PORT": "55999", "DBTEST_PORT": "55998", "PGPASSWORD": FAUX_2,
                     "MUTATION_TEST_SORTIE": str(d.sortie)}
        code, sortie = self.lancer(d, env=exportees)
        self.assertEqual(code, 0, sortie)
        vu = json.loads(d.sortie.read_text(encoding="utf-8"))
        self.assertNotIn("ignore/sentinelle.txt", vu["fichiers"])
        self.assertIn("tools/factice.py", vu["fichiers"])
        env = vu["env"]
        for nom in ("PMZILLA_LAB_DB_PASSWORD", "PMZILLA_LAB_DB_PORT", "DBTEST_PORT", "PGPASSWORD"):
            self.assertNotIn(nom, env)
        valeurs = json.dumps(env)
        for valeur in (FAUX_1, FAUX_2, "hote-qq", "55999", "55998"):
            self.assertNotIn(valeur, valeurs)
        self.assertIn("127.0.0.1:1/", env["PMZILLA_LAB_DB_URL"])
        self.assertFalse(Path(env["PMZILLA_LAB_DB_SECURITY_BIN"]).exists())
        self.assertEqual(env["PGPORT"], "1")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")

    def test_le_dossier_temporaire_est_retire(self):
        d = self.depot()
        crees = []
        vrai = tempfile.mkdtemp

        def espion(*a, **kw):
            chemin = vrai(*a, **kw)
            crees.append(chemin)
            return chemin
        with mock.patch.object(mm.tempfile, "mkdtemp", side_effect=espion):
            self.lancer(d)
        self.assertTrue(crees)
        for chemin in crees:
            self.assertFalse(Path(chemin).exists(), chemin)

    def test_un_delai_depasse_compte_comme_tue(self):
        module = "ATTENTE = 0\n"
        test = textwrap.dedent('''\
            import sys
            import time
            import unittest
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
            import factice


            class Attente(unittest.TestCase):
                def test_attente(self):
                    if factice.ATTENTE != 0:
                        time.sleep(60)
            ''')
        d = self.depot(module=module, test=test)
        perimetre = (mm.Cible("tools/factice.py", ("ATTENTE",), (("tests/factice", None),)),)
        code, sortie = self.lancer(d, argv=("run", "--timeout", "2"), perimetre=perimetre)
        self.assertEqual(code, 0, sortie)
        self.assertIn("mutation : 2 mutants tués sur 2 (dont 2 en délai), score 100 %", sortie)
        self.assertEqual(sortie.count("mutation : délai tools/factice.py:ATTENTE ligne 1 (constante)"), 2)

    def test_suite_de_reference_en_echec(self):
        d = self.depot(test=TEST_FACTICE.replace("factice.masquer(7), 7", "factice.masquer(7), 8"))
        code, sortie = self.lancer(d)
        self.assertEqual(code, 2)
        self.assertIn("mutation : lancement impossible (suite de référence en échec)", sortie)
        self.assertNotIn("survivant", sortie)

    def test_copie_impossible_hors_depot_git(self):
        d = self.depot()
        with tempfile.TemporaryDirectory() as vide:
            (Path(vide) / "tools").mkdir()
            (Path(vide) / SEUIL_FICHIER).write_text("70\n", encoding="utf-8")
            sortie, erreur = io.StringIO(), io.StringIO()
            with mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(d.donnees)}), \
                    contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
                code = mm.main(["run"], racine=Path(vide), perimetre=PERIMETRE, lanceur=LANCEUR)
        self.assertEqual(code, 2)
        self.assertIn("mutation : lancement impossible (copie impossible)", sortie.getvalue() + erreur.getvalue())


class Seuil(Base):
    def test_seuil_absent(self):
        d = self.depot(seuil=None)
        code, sortie = self.lancer(d)
        self.assertEqual(code, 2)
        self.assertIn("mutation : lancement impossible (seuil illisible)", sortie)
        self.assertNotIn("mutation : cible", sortie)

    def test_seuil_hors_bornes_ou_illisible(self):
        for texte in ("40\n", "101\n", "soixante-dix\n", "# rien\n", "70\nquatre-vingts\n", "70\n120\n"):
            with self.subTest(texte=texte):
                d = self.depot(seuil=texte)
                code, sortie = self.lancer(d)
                self.assertEqual(code, 2, sortie)
                self.assertIn("mutation : lancement impossible (seuil illisible)", sortie)

    def test_lecture_du_seuil_reel(self):
        self.assertEqual(mm.lire_seuil(RACINE / SEUIL_FICHIER), (80, 80))   # plancher relevé à la cible le 2026-10-20 (6.3)

    def test_cible_absente_vaut_le_seuil(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "seuil.txt"
            chemin.write_text("# commentaire\n\n75\n", encoding="utf-8")
            self.assertEqual(mm.lire_seuil(chemin), (75, 75))

    def test_aucune_liste_de_survivants_acceptes(self):
        texte = (RACINE / "tools" / "mutation_masking.py").read_text(encoding="utf-8").lower()
        for mot in ("accepted", "acceptes", "acceptés", "exclusion", "excluded", "ignore_survivor", "allowlist"):
            self.assertNotIn(mot, texte, mot)
        voisins = [p.name for p in (RACINE / "tools").glob("mutation_masking*")]
        self.assertEqual(sorted(voisins), ["mutation_masking.py", "mutation_masking_seuil.txt"])


class Echeance(Base):
    def test_regle_due(self):
        lundi = dt.date(2026, 10, 19)
        mardi = dt.date(2026, 10, 20)
        self.assertTrue(mm.due({}, mardi, 0))
        self.assertTrue(mm.due({"last_complete": "2026-10-19"}, lundi, 0))
        self.assertFalse(mm.due({"last_attempt": "2026-10-19", "last_complete": "2026-10-12"}, lundi, 0))
        self.assertFalse(mm.due({"last_attempt": "2026-10-19", "last_complete": "2026-10-19"}, mardi, 0))
        self.assertTrue(mm.due({"last_attempt": "2026-10-19", "last_complete": "2026-10-12"}, mardi, 0))

    def test_pas_due_rien_ne_tourne(self):
        d = self.depot()
        d.donnees.mkdir(parents=True)
        etat = {"last_attempt": "2026-10-19", "last_complete": "2026-10-19"}
        (d.donnees / "mutation-etat.json").write_text(json.dumps(etat), encoding="utf-8")
        code, sortie = self.lancer(d, argv=("run", "--due"), today="2026-10-19", env={"PMZILLA_MUTATION_DAY": "lundi"})
        self.assertEqual(code, 0)
        self.assertEqual(sortie.strip(), "mutation : pas due")
        self.assertEqual(json.loads((d.donnees / "mutation-etat.json").read_text(encoding="utf-8")), etat)

    def test_rattrapage(self):
        d = self.depot()
        d.donnees.mkdir(parents=True)
        (d.donnees / "mutation-etat.json").write_text(json.dumps({"last_attempt": "2026-10-10", "last_complete": "2026-10-10"}),
                                                       encoding="utf-8")
        code, sortie = self.lancer(d, argv=("run", "--due"), today="2026-10-20", env={"PMZILLA_MUTATION_DAY": "lundi"})
        self.assertEqual(code, 0, sortie)
        self.assertIn("mutation : 3 mutants tués sur 5", sortie)

    def test_etat_proprietaire_seul_sans_code(self):
        d = self.depot()
        self.lancer(d)
        chemin = d.donnees / "mutation-etat.json"
        self.assertEqual(stat.S_IMODE(chemin.stat().st_mode), 0o600)
        texte = chemin.read_text(encoding="utf-8")
        for fragment in ("n < SEUIL", "def masquer", "return", "SEUIL = "):
            self.assertNotIn(fragment, texte)
        etat = json.loads(texte)
        self.assertEqual(etat["last_attempt"], "2026-10-20")
        self.assertEqual(etat["last_complete"], "2026-10-20")
        self.assertEqual((etat["tues"], etat["total"], etat["score"]), (3, 5, 60))
        self.assertEqual(etat["survivants"][0], {"fichier": "tools/factice.py", "fonction": "SEUIL", "ligne": 1,
                                                  "operateur": "constante"})

    def test_rapport_relit_le_dernier_passage(self):
        d = self.depot()
        self.lancer(d)
        code, sortie = self.lancer(d, argv=("report",))
        self.assertEqual(code, 0)
        self.assertIn("mutation : 3 mutants tués sur 5 (dont 0 en délai), score 60 %, seuil 60 %, cible 80 %", sortie)
        self.assertEqual(sortie.count("mutation : survivant "), 2)

    def test_rapport_sans_passage(self):
        d = self.depot()
        code, sortie = self.lancer(d, argv=("report",))
        self.assertEqual(code, 0)
        self.assertIn("mutation : aucun passage enregistré", sortie)


class DepotReel(unittest.TestCase):
    def test_le_perimetre_reel_nomme_des_noms_existants(self):
        import ast
        for cible in mm.PERIMETRE:
            arbre = ast.parse((RACINE / cible.fichier).read_text(encoding="utf-8"))
            definis = {n.name for n in arbre.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            definis |= {t.id for n in arbre.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
            self.assertEqual(sorted(set(cible.noms) - definis), [], cible.fichier)
            for dossier, _ in cible.suites:
                self.assertTrue((RACINE / dossier).is_dir(), dossier)
        self.assertNotIn("connect", next(c for c in mm.PERIMETRE if c.fichier == "tools/db.py").noms)

    def test_le_mutant_du_plancher_fait_echouer_tests_flow_views(self):
        cible = next(c for c in mm.PERIMETRE if c.fichier == "tools/flow_views.py")
        with tempfile.TemporaryDirectory(prefix="essai-plancher-") as dossier:
            copie = Path(dossier)
            mm.copier(RACINE, copie)
            env = mm.environnement(copie, os.environ)
            self.assertEqual(mm.juger(copie, cible, LANCEUR, env, delai=300), "survivant")    # référence : la suite passe intacte
            source = (copie / cible.fichier).read_text(encoding="utf-8")
            plancher =[m for m in mm.points(source, ("PLANCHER",), cible.fichier)
                        if m.operateur == "constante" and m.remplacement == "4"]
            self.assertEqual(len(plancher), 1)
            (copie / cible.fichier).write_text(mm.appliquer(source, plancher[0]), encoding="utf-8")
            verdict = mm.juger(copie, cible, LANCEUR, env, delai=300)
        self.assertEqual(verdict, "tue")

    def test_le_lanceur_de_tests_ne_nomme_pas_l_outil(self):
        self.assertNotIn("mutation_masking.py", (RACINE / "tests" / "run_all.sh").read_text(encoding="utf-8"))
        self.assertEqual([p for p in (RACINE / "tests").rglob("mutation_masking.py")], [])

    def test_bibliotheque_standard_seulement(self):
        texte = (RACINE / "tools" / "mutation_masking.py").read_text(encoding="utf-8")
        self.assertNotIn("mutmut", texte.split('"""', 2)[0] + texte.split('"""', 2)[2])
        self.assertFalse((RACINE / "tools" / "mutation_masking.py.lock").exists())
        self.assertNotIn("mutmut", (RACINE / "docs" / "pmzilla" / "composants.yaml").read_text(encoding="utf-8"))


class Durcissement(Base):
    """Relecture 5.1 du 2026-10-20 (tests écrits après le code) : aucune variable de dépôt Git héritée, uv hors ligne, dossier de contenu
    sur la copie, état partiel en code 2 sans trace."""

    def test_environnement_sans_variables_git_hors_ligne_contenu_sur_la_copie(self):
        base = {"GIT_DIR": "/ailleurs/.git", "GIT_INDEX_FILE": "/ailleurs/index", "GIT_WORK_TREE": "/ailleurs",
                "GIT_COMMON_DIR": "/ailleurs/.git", "PMZILLA_LAB_WORKSPACE": "/espace-reel", "HOME": "/maison"}
        env = mm.environnement(Path("/copie"), base)
        for nom in mm.VARIABLES_GIT:
            self.assertNotIn(nom, env)
        self.assertEqual(env["UV_OFFLINE"], "1")
        self.assertEqual(env["PMZILLA_LAB_WORKSPACE"], "/copie")
        self.assertEqual(env["HOME"], "/maison")

    def test_un_git_dir_herite_n_est_jamais_ecrit(self):
        # dans un crochet, GIT_DIR désigne le vrai dépôt : la copie (git init, add, commit) ne doit jamais y écrire
        d = self.depot()
        def etat_du_depot():
            env = mm.sans_variables_git(os.environ)
            return subprocess.run(["git", "-C", str(d.racine), "for-each-ref", "--format=%(refname) %(objectname)"],
                                  capture_output=True, text=True, env=env).stdout
        avant = etat_du_depot()
        code, sortie = self.lancer(d, env={"GIT_DIR": str(d.racine / ".git"), "GIT_WORK_TREE": str(d.racine)})
        self.assertEqual(code, 0, sortie)
        self.assertEqual(etat_du_depot(), avant)

    def test_report_sur_un_etat_partiel_code_2_sans_trace(self):
        d = self.depot()
        d.donnees.mkdir(parents=True)
        etat = {"last_complete": "2026-10-19", "cibles": [], "tues": 0, "total": 0, "survivants": [], "en_delai": []}
        (d.donnees / "mutation-etat.json").write_text(json.dumps(etat), encoding="utf-8")
        code, sortie = self.lancer(d, argv=("report",))
        self.assertEqual(code, 2, sortie)
        self.assertIn("état illisible", sortie)
        self.assertNotIn("Traceback", sortie)


if __name__ == "__main__":
    unittest.main()
