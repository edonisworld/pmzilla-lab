"""
Tests de la section « Santé » / « Health » du tableau de bord (change doctor-command, R-45, tâche 5.1).

    uv run --with pyyaml python -m unittest discover -s tests/dashboard -v

La section lit seulement doctor-etat.json du dossier des données (fichier inventé ici) : elle ne lance jamais le doctor.
"""
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "dashboard.py"


def etat(checks, checked_at="2026-10-14T10:00") -> dict:
    counts = {"ok": 0, "warning": 0, "problem": 0, "skipped": 0}
    for check in checks:
        counts[check["level"]] += 1
    return {"version": 1, "checked_at": checked_at, "counts": counts, "checks": checks, "last_notification": None}


def check(id, level, key, counts=None) -> dict:
    return {"id": id, "level": level, "reason": {"key": key, "counts": counts or {}}}


class Sante(unittest.TestCase):
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
        patcher = unittest.mock.patch.object(self.dashboard, "DATA", self.data)
        patcher.start()
        self.addCleanup(patcher.stop)

    def ecrire(self, contenu) -> None:
        texte = contenu if isinstance(contenu, str) else json.dumps(contenu)
        (self.data / "doctor-etat.json").write_text(texte, encoding="utf-8")

    def section(self) -> str:
        return self.dashboard.safe(self.dashboard.section_sante)

    def test_premiere_section_de_la_page(self):
        self.assertEqual(self.dashboard.SECTIONS[0][0], "sante")
        self.assertEqual(len(self.dashboard.SECTIONS), 9)
        self.ecrire(etat([check("db", "ok", "db_ok")]))
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch.multiple(self.dashboard, WORKSPACE=Path(tmp) / "ws", LOGS=Path(tmp) / "logs"):
                page = self.dashboard.build("fr")
        self.assertIn('<section id="sante"><h2>Santé</h2>', page)
        self.assertLess(page.index('id="sante"'), page.index('id="a-faire"'))

    def test_fichier_absent(self):
        self.assertIn("pas encore de données", self.section())

    def test_fichier_illisible(self):
        self.ecrire("{pas du json /Users/quelquun/secret")
        html = self.section()
        self.assertIn("source illisible (JSONDecodeError)", html)
        self.assertNotIn("secret", html)

    def test_tout_va_bien(self):
        self.ecrire(etat([check("db", "ok", "ok"), check("jira", "skipped", "unknown"), check("ollama", "ok", "ok")]))
        html = self.section()
        self.assertIn("tout va bien", html)
        self.assertIn("14/10/2026 10:00", html)
        self.assertNotIn("<tr>", html)

    def test_un_probleme_et_un_avertissement(self):
        self.ecrire(etat([
            check("db", "problem", "port_closed"),
            check("ollama", "ok", "ok"),
            check("disk", "warning", "low", {"free_gb": 12}),
            check("jira", "skipped", "unknown")]))
        html = self.section()
        self.assertNotIn("tout va bien", html)
        self.assertIn("14/10/2026 10:00", html)
        self.assertEqual(html.count("<tr>"), 3)       # l'en-tête et deux lignes
        self.assertIn("db", html)
        self.assertIn("problème", html)
        self.assertIn("le port de la base refuse la connexion", html)
        self.assertIn("avertissement", html)
        self.assertIn("12 Go libres, sous le seuil d&#x27;avertissement", html)
        self.assertNotIn("Ollama", html)
        self.assertNotIn("jeton", html)
        self.assertLess(html.index("db"), html.index("disk"))

    def test_langue_anglaise(self):
        self.dashboard.set_language("en")
        self.ecrire(etat([check("db", "problem", "port_closed"), check("disk", "warning", "low", {"free_gb": 12})]))
        html = self.section()
        self.assertIn("2026-10-14 10:00", html)
        self.assertIn("problem", html)
        self.assertIn("warning", html)
        self.assertIn("the database port refuses connections", html)
        self.assertIn("12 GB free, under the warning threshold", html)
        self.assertEqual(self.dashboard.t("section_health"), "Health")
        self.ecrire(etat([check("db", "ok", "ok")]))
        self.assertIn("all good", self.section())

    def test_champ_noms_et_compteur_absents_sans_erreur(self):
        self.ecrire(etat([check("models", "warning", "missing"), check("disk", "warning", "low")]))
        html = self.section()
        self.assertIn("modèle absent", html)
        self.assertIn("0 Go libres", html)

    def test_cle_inconnue_ne_casse_pas_la_page(self):
        self.ecrire(etat([check("db", "problem", "cle_future")]))
        self.assertIn("cle_future", self.section())

    def test_ne_lance_aucun_processus(self):
        self.ecrire(etat([check("db", "problem", "port_closed")]))
        with unittest.mock.patch("subprocess.run", side_effect=AssertionError("lancement interdit")), \
                unittest.mock.patch("subprocess.Popen", side_effect=AssertionError("lancement interdit")):
            self.assertIn("problème", self.section())


if __name__ == "__main__":
    unittest.main()
