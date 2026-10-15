"""
Tests de la section « Composants » / « Components » du tableau de bord (change components-watch, tâche 5.1).

    uv run --with pyyaml python -m unittest discover -s tests/dashboard -v

La section lit seulement composants-etat.json du dossier des données (fichier inventé ici) : jamais de réseau,
jamais de lancement de composants.py ni d'une autre commande, jamais d'écriture de l'état.
"""
import copy
import datetime as dt
import json
import re
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_dashboard as base  # noqa: E402

SCRIPT = base.SCRIPT


def etat(**surcharges) -> dict:
    composants = {
        "numpy": {"kind": "python-package", "used": "2.1.0", "pinned": True, "flags": [],
                  "procedure": "Update a Python package of the scripts", "incomplete": None, "follows": None,
                  "novelties": [{"nature": "update", "used": "2.1.0", "available": "2.1.1",
                                 "job": "Mettre à jour numpy 2.1.0 → 2.1.1"}]},
        "modele-a": {"kind": "ollama-model", "used": "v1", "pinned": True, "flags": ["requires-reindex"],
                     "procedure": "Update an Ollama model", "incomplete": None, "follows": None,
                     "novelties": [{"nature": "major", "used": "v1", "available": "v2",
                                    "job": "Mettre à jour modele-a v1 → v2"}]},
        "git": {"kind": "tool", "used": "2.50.0", "pinned": False, "flags": [],
                "procedure": "Update a Homebrew tool", "incomplete": None, "follows": None, "novelties": []},
        "outil-b": {"kind": "tool", "used": "1.0", "pinned": True, "flags": [],
                    "procedure": "Update a Homebrew tool", "incomplete": None, "follows": None, "novelties": []},
    }
    contenu = {"version": 1, "first_attempt": "2026-10-05", "last_attempt": "2026-10-12", "last_complete": "2026-10-12",
               "complete": True, "unreachable": 0, "stale_weeks": 3, "stale_alert": None, "components": composants,
               "scripts": {"a": {"to_update": 2}}, "notified": [["numpy", "2.1.1"]]}
    contenu.update(surcharges)
    return contenu


class Composants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SCRIPT.parent))
        import dashboard
        cls.dashboard = dashboard

    def setUp(self):
        self.dashboard.set_language("fr")
        self.addCleanup(self.dashboard.set_language, "fr")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = Path(tmp.name)
        for patcher in (unittest.mock.patch.object(self.dashboard, "DATA", self.data),
                        unittest.mock.patch.object(self.dashboard, "today", lambda: dt.date(2026, 10, 14))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def ecrire(self, contenu) -> None:
        texte = contenu if isinstance(contenu, str) else json.dumps(contenu)
        (self.data / "composants-etat.json").write_text(texte, encoding="utf-8")

    def section(self) -> str:
        return self.dashboard.safe(self.dashboard.section_composants)

    def test_derniere_section_de_la_page(self):
        self.assertEqual(self.dashboard.SECTIONS[-1][0], "composants")
        self.assertEqual(len(self.dashboard.SECTIONS), 9)
        self.assertEqual(self.dashboard.SECTIONS[-2][0], "critic")
        self.ecrire(etat())
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch.multiple(self.dashboard, WORKSPACE=Path(tmp) / "ws", LOGS=Path(tmp) / "logs"):
                page = self.dashboard.build("fr")
        self.assertIn('<section id="composants"><h2>Composants</h2>', page)
        self.assertLess(page.index('id="critic"'), page.index('id="composants"'))

    def test_nouveautes(self):
        self.ecrire(etat())
        html = self.section()
        self.assertIn("Dernière vérification complète", html)
        self.assertIn("12/10/2026", html)
        self.assertNotIn("ancienne", html)
        self.assertNotIn("incomplète", html)
        self.assertEqual(html.count("<tr>"), 3)                       # l'en-tête et deux lignes
        self.assertIn("numpy", html)
        self.assertIn("mise à jour", html)
        self.assertIn("2.1.1", html)
        self.assertIn("version majeure", html)
        self.assertIn("réindexation nécessaire", html)
        self.assertIn("Mettre à jour numpy 2.1.0 → 2.1.1", html)
        self.assertIn("Mettre à jour modele-a v1 → v2", html)
        self.assertIn("Update a Python package of the scripts", html)
        self.assertIn("2 à jour", html)                               # outil-b et git (sans nouveauté)

    def test_non_epingle(self):
        contenu = etat()
        contenu["components"]["git"]["novelties"] = [{"nature": "update", "used": "2.50.0", "available": "2.50.1", "job": "z"}]
        self.ecrire(contenu)
        html = self.section()
        self.assertEqual(html.count("non épinglé"), 1)
        self.assertIn("1 à jour", html)

    def test_veille_seule_affichee_pour_la_seule_version_majeure(self):
        contenu = etat()
        contenu["components"]["exemple/base"] = {
            "kind": "docker-image", "used": "0.26.0-pg18", "pinned": True, "flags": ["major-watch-only"],
            "procedure": "Update the database image", "incomplete": None, "follows": None,
            "novelties": [{"nature": "update", "used": "0.26.0-pg18", "available": "0.26.1-pg18", "job": "x"},
                          {"nature": "major", "used": "0.26.0-pg18", "available": "0.26.0-pg19", "job": "y"}]}
        self.ecrire(contenu)
        lignes = [l for l in self.section().split("<tr>") if "exemple/base" in l]
        correctif = next(l for l in lignes if "0.26.1-pg18" in l)
        majeure = next(l for l in lignes if "0.26.0-pg19" in l)
        self.assertNotIn("veille seule", correctif)
        self.assertNotIn("version majeure", correctif)
        self.assertIn("veille seule : migration nécessaire", majeure)
        self.dashboard.set_language("en")
        html = self.section()
        self.assertEqual(html.count("watch only: migration needed"), 1)

    def test_etiquette_republiee_et_prerelease(self):
        contenu = etat()
        contenu["components"]["git"]["novelties"] = [
            {"nature": "pre-release", "used": "2.50.0", "available": "2.51.0rc1", "job": "x"}]
        contenu["components"]["outil-b"]["novelties"] = [
            {"nature": "republished", "used": "latest@aaaaaaaaaaaa", "available": "latest@bbbbbbbbbbbb", "job": "y"}]
        self.ecrire(contenu)
        html = self.section()
        self.assertIn("préversion", html)
        self.assertIn("étiquette republiée", html)
        self.assertIn("latest@bbbbbbbbbbbb", html)

    def test_incomplete_et_ancienne(self):
        self.ecrire(etat(complete=False, unreachable=2, last_attempt="2026-10-13", last_complete="2026-09-15"))
        html = self.section()
        self.assertIn("incomplète", html)
        self.assertRegex(html, r"incomplète[^<]*</span>[^<]*2|2[^<]*incomplète")
        self.assertIn("15/09/2026", html)
        self.assertIn("ancienne", html)
        self.assertIn("13/10/2026", html)

    def test_jamais_de_verification_complete(self):
        self.ecrire(etat(last_complete=None, complete=False, unreachable=1))
        html = self.section()
        self.assertIn("ancienne", html)
        self.assertIn("incomplète", html)

    def test_limite_par_defaut_et_explicite(self):
        # 14/10 moins 21 jours = 23/09 : pas encore ancienne ; un jour de plus, ancienne
        self.ecrire(etat(last_complete="2026-09-23"))
        self.assertNotIn("ancienne", self.section())
        self.ecrire(etat(last_complete="2026-09-22"))
        self.assertIn("ancienne", self.section())
        sans = etat(last_complete="2026-09-22")
        del sans["stale_weeks"]
        self.ecrire(sans)
        self.assertIn("ancienne", self.section())
        self.ecrire(etat(last_complete="2026-09-22", stale_weeks=4))
        self.assertNotIn("ancienne", self.section())

    def test_composant_incomplet_pas_a_jour(self):
        contenu = etat()
        contenu["components"]["outil-b"]["incomplete"] = "URLError"
        self.ecrire(contenu)
        self.assertIn("1 à jour", self.section())

    def test_fichier_absent(self):
        self.assertIn("pas encore de données", self.section())

    def test_fichier_illisible(self):
        self.ecrire("{pas du json /Users/quelquun/secret")
        html = self.section()
        self.assertIn("source illisible (JSONDecodeError)", html)
        self.assertNotIn("secret", html)

    def test_aucune_adresse_ni_lien(self):
        contenu = etat()
        contenu["components"]["numpy"]["novelties"][0]["available"] = "2.1.1"
        self.ecrire(contenu)
        html = self.section()
        for interdit in ("http", "<a ", "href", "://", "—"):
            self.assertNotIn(interdit, html)

    def test_echappement(self):
        contenu = etat()
        contenu["components"]["<b>x</b>"] = copy.deepcopy(contenu["components"]["numpy"])
        self.ecrire(contenu)
        html = self.section()
        self.assertNotIn("<b>x</b>", html)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)

    def test_langue_anglaise(self):
        self.dashboard.set_language("en")
        contenu = etat(complete=False, unreachable=1, last_complete="2026-09-01")
        contenu["components"]["git"]["novelties"] = [{"nature": "update", "used": "2.50.0", "available": "2.50.1", "job": "z"}]
        contenu["components"]["numpy"]["novelties"][0]["job"] = "Mettre à jour numpy 2.1.0 → 2.1.1"
        self.ecrire(contenu)
        html = self.section()
        self.assertEqual(self.dashboard.t("section_components"), "Components")
        self.assertIn("Last complete check", html)
        self.assertIn("2026-09-01", html)
        self.assertIn("stale", html)
        self.assertIn("incomplete", html)
        self.assertIn("update", html)
        self.assertIn("major version", html)
        self.assertIn("requires reindexing", html)
        self.assertIn("not pinned", html)
        self.assertIn("1 up to date", html)
        self.assertIn("Update numpy 2.1.0 → 2.1.1", html)
        self.assertIn("Update modele-a v1 → v2", html)
        self.assertNotIn("Mettre à jour", html)
        self.assertNotIn("mise à jour", html)

    def test_ne_lance_aucun_processus_ni_connexion_et_n_ecrit_pas(self):
        self.ecrire(etat())
        avant = (self.data / "composants-etat.json").read_bytes()
        with unittest.mock.patch("subprocess.run", side_effect=AssertionError("lancement interdit")), \
                unittest.mock.patch("subprocess.Popen", side_effect=AssertionError("lancement interdit")), \
                unittest.mock.patch("socket.socket", side_effect=AssertionError("réseau interdit")):
            self.assertIn("numpy", self.section())
        self.assertEqual((self.data / "composants-etat.json").read_bytes(), avant)
        self.assertEqual([p.name for p in self.data.iterdir()], ["composants-etat.json"])


class PageComplete(unittest.TestCase):
    def test_sans_etat_les_autres_sections_inchangees(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = base.donnees_completes(root)
            self.assertFalse((Path(env["PMZILLA_LAB_DATA"]) / "composants-etat.json").exists())
            result, page = base.generer(root, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        morceau = re.search(r'<section id="composants">.*?</section>', page, re.S).group(0)
        self.assertIn("pas encore de données", morceau)
        for cle in base.SECTIONS:
            self.assertIn(f'<section id="{cle}">', page)
        self.assertLess(page.index('id="critic"'), page.index('id="composants"'))

    def test_page_anglaise_avec_etat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = base.donnees_completes(root)
            (Path(env["PMZILLA_LAB_DATA"]) / "composants-etat.json").write_text(json.dumps(etat()), encoding="utf-8")
            sortie = root / "page.html"
            result = base.subprocess.run([sys.executable, str(base.RUNNER), "--output", str(sortie), "--language", "en"],
                                         capture_output=True, text=True, timeout=120,
                                         env={**base.without_cases_variables(base.os.environ), **env,
                                              "PMZILLA_LAB_TODAY": "2026-10-12"})
            page = sortie.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        morceau = re.search(r'<section id="composants">.*?</section>', page, re.S).group(0)
        self.assertIn("<h2>Components</h2>", morceau)
        self.assertIn("Update numpy 2.1.0 → 2.1.1", morceau)
        self.assertNotIn("http", morceau)


if __name__ == "__main__":
    unittest.main()
