"""
Tests du contexte commun du script d'installation (tools/install_lab_context.py) : confirmations, passage à blanc, lecture des
constantes de configuration. Sans aucun effet réel : seuls des fichiers d'un dossier temporaire sont touchés.

    uv run python -W ignore -m unittest discover -s tests/install_lab -q -f
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import install_lab_context as c   # noqa: E402


def contexte(tmp: Path, a_blanc=False) -> c.Contexte:
    return c.Contexte(racine=tmp, maison=tmp / "home", a_blanc=a_blanc)


class Confirmation(unittest.TestCase):
    def repondre(self, reponse):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            with mock.patch("builtins.input", return_value=reponse):
                return contexte(Path(d)).confirmer("x", "faire")

    def test_seuls_y_et_yes_acceptent(self):
        for r in ("y", "Y", "yes", "YES", " Yes "):
            self.assertTrue(self.repondre(r), r)
        for r in ("", "n", "no", "o", "oui", "yes please", "yy", " "):
            self.assertFalse(self.repondre(r), r)

    def test_fin_d_entree_refuse(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            with mock.patch("builtins.input", side_effect=EOFError):
                self.assertFalse(contexte(Path(d)).confirmer("x", "faire"))


class Actions(unittest.TestCase):
    def test_passage_a_blanc_ne_lance_rien_et_ne_demande_rien(self):
        with tempfile.TemporaryDirectory() as d:
            cible = Path(d) / "cree"
            sortie = io.StringIO()
            with redirect_stdout(sortie), mock.patch("builtins.input", side_effect=AssertionError("question posée")):
                r = contexte(Path(d), a_blanc=True).act("x", "créer", ["touch", str(cible)])
            self.assertEqual(r.etat, c.A_BLANC)
            self.assertFalse(cible.exists())
            self.assertIn("install_lab: dry run: would run touch", sortie.getvalue())

    def test_refus_ne_lance_rien(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            cible = Path(d) / "cree"
            with mock.patch("builtins.input", return_value=""):
                r = contexte(Path(d)).act("x", "créer", ["touch", str(cible)])
            self.assertEqual(r.etat, c.REFUSE)
            self.assertFalse(cible.exists())

    def test_accord_lance_la_commande(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            cible = Path(d) / "cree"
            with mock.patch("builtins.input", return_value="y"):
                r = contexte(Path(d)).act("x", "créer", ["touch", str(cible)])
            self.assertEqual(r.etat, c.FAIT)
            self.assertTrue(cible.exists())

    def test_commande_en_echec_est_nommee(self):
        with tempfile.TemporaryDirectory() as d:
            sortie = io.StringIO()
            with redirect_stdout(sortie), mock.patch("builtins.input", return_value="y"):
                r = contexte(Path(d)).act("etape", "échouer", ["false"])
            self.assertEqual(r.etat, c.ECHEC)
            self.assertIn("step etape: failed: false", sortie.getvalue())

    def test_commande_introuvable_est_un_echec(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            with mock.patch("builtins.input", return_value="y"):
                r = contexte(Path(d)).act("x", "inexistant", ["commande-qui-n-existe-pas"])
            self.assertEqual(r.etat, c.ECHEC)

    def test_ecriture_confirmee_seulement(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            cible = Path(d) / "sous" / "f.txt"
            with mock.patch("builtins.input", return_value=""):
                self.assertEqual(contexte(Path(d)).ecrire("x", "écrire", cible, "a").etat, c.REFUSE)
            self.assertFalse(cible.exists())
            self.assertEqual(contexte(Path(d), a_blanc=True).ecrire("x", "écrire", cible, "a").etat, c.A_BLANC)
            self.assertFalse(cible.exists())
            with mock.patch("builtins.input", return_value="y"):
                self.assertEqual(contexte(Path(d)).ecrire("x", "écrire", cible, "a").etat, c.FAIT)
            self.assertEqual(cible.read_text(), "a")

    def test_action_manuelle_est_affichee_et_gardee(self):
        with tempfile.TemporaryDirectory() as d:
            ctx, sortie = contexte(Path(d)), io.StringIO()
            with redirect_stdout(sortie):
                ctx.action_manuelle("security add-generic-password -s x -a \"$USER\" -w", "create the entry")
            self.assertIn("install_lab: manual action needed: create the entry", sortie.getvalue())
            self.assertEqual(len(ctx.manuel), 1)


class Configuration(unittest.TestCase):
    def depot(self, d: Path) -> Path:
        (d / "tools").mkdir()
        (d / "watch").mkdir()
        (d / "tools" / "db.py").write_text('SERVICE_TROUSSEAU = "svc-x"\nROLES_AVEC_MOT_DE_PASSE = ("r1", "r2")  # commentaire\nimport psycopg\n')
        (d / "tools" / "pmzilla_lab_library.py").write_text('import os\nEMBED_MODEL = os.environ.get("PMZILLA_LAB_MODEL", "emb-x")\n')
        (d / "watch" / "tri.yaml").write_text("mode: filtre\nmodel: veille-x:7b   # commentaire\n")
        return d

    def test_lecture_sans_importer(self):
        with tempfile.TemporaryDirectory() as t:
            d = self.depot(Path(t))
            self.assertEqual(c.roles_de_la_base(d), ["r1", "r2"])
            self.assertEqual(c.service_trousseau_de_la_base(d), "svc-x")
            self.assertEqual(c.modele_de_veille(d), "veille-x:7b")
            self.assertEqual([(r, n) for r, n, _ in c.modeles_ollama(d)], [("embedding", "emb-x"), ("watch triage", "veille-x:7b")])

    def test_valeur_introuvable_n_est_pas_inventee(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.assertEqual(c.roles_de_la_base(d), [])
            self.assertIsNone(c.service_trousseau_de_la_base(d))
            self.assertIsNone(c.modele_de_veille(d))
            self.assertEqual(c.modeles_ollama(d), [])


if __name__ == "__main__":
    unittest.main()
