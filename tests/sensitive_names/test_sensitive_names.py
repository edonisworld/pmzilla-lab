"""
Tests de tools/sensitive_names.py : garde des noms sensibles (design.md 3.5).

    uv run python -m unittest discover -s tests/sensitive_names -v

Liste inventée dans un fichier temporaire ; la vraie liste n'est jamais lue.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import sensitive_names as sn  # noqa: E402

LISTE = "# commentaire\n\n  Zorglub Martin  \nA&B\nabc\nXYZW\n+plus\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.chemin = Path(self.temp.name) / "noms.txt"

    def ecrire(self, texte):
        self.chemin.write_text(texte, encoding="utf-8")
        return self.chemin


class Chargement(Base):
    def test_commentaires_et_lignes_vides_ignores_et_noms_nettoyes(self):
        self.assertEqual(sn.load_names(self.ecrire(LISTE)), ["Zorglub Martin", "A&B", "abc", "XYZW", "+plus"])

    def test_fichier_absent(self):
        with self.assertRaises(sn.SensitiveNamesUnavailable) as c:
            sn.load_names(self.chemin)
        self.assertEqual(c.exception.reason, "missing")
        self.assertIn(str(self.chemin), str(c.exception))

    def test_liste_sans_aucun_nom_est_traitee_comme_absente(self):
        for texte in ("# seulement\n\n   \n# des commentaires\n", ""):
            with self.subTest(octets=len(texte)):
                with self.assertRaises(sn.SensitiveNamesUnavailable) as c:
                    sn.load_names(self.ecrire(texte))
                self.assertEqual(c.exception.reason, "empty")
                self.assertIn(str(self.chemin), str(c.exception))

    def test_fichier_illisible(self):
        self.chemin.mkdir()  # un dossier : lecture impossible
        with self.assertRaises(sn.SensitiveNamesUnavailable) as c:
            sn.load_names(self.chemin)
        self.assertEqual(c.exception.reason, "unreadable")
        self.assertIn(str(self.chemin), str(c.exception))

    def test_message_sans_contenu(self):
        self.ecrire("# Zorglub\n")
        with self.assertRaises(sn.SensitiveNamesUnavailable) as c:
            sn.load_names(self.chemin)
        self.assertNotIn("Zorglub", str(c.exception))

    def test_sous_classe_d_exception(self):
        self.assertTrue(issubclass(sn.SensitiveNamesUnavailable, Exception))

    def test_variable_d_environnement_remplace_le_chemin(self):
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.chemin)}):
            self.assertEqual(sn.default_path(), self.chemin)
        env = {k: v for k, v in os.environ.items() if k != "PMZILLA_LAB_SENSITIVE_NAMES"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(sn.default_path().parts[-2:], ("Flux-Lab", "noms-sensibles.txt"))

    def test_chemin_par_defaut_utilise_par_load_names(self):
        self.ecrire("abc\n")
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.chemin)}):
            self.assertEqual(sn.load_names(), ["abc"])


class Correspondance(unittest.TestCase):
    NOMS = ["Zorglub Martin", "A&B", "abc", "XYZW", "+plus", "Durand"]

    def champ(self, texte):
        return sn.find_field({"f": texte}, self.NOMS)

    def test_mot_entier(self):
        self.assertEqual(self.champ("vu avec Zorglub Martin hier"), "f")

    def test_mot_colle_ne_correspond_pas(self):
        for t in ("xDurand", "Durandx", "Durand1", "_Durand", "Durand_"):
            with self.subTest(t=t):
                self.assertIsNone(self.champ(t))

    def test_ponctuation_voisine_correspond(self):
        self.assertEqual(self.champ("(Durand), puis"), "f")

    def test_symbole_en_bordure(self):
        self.assertEqual(self.champ("equipe A&B."), "f")
        self.assertEqual(self.champ("le +plus de"), "f")
        self.assertIsNone(self.champ("xA&Bx"))

    def test_nom_ordinaire_insensible_a_la_casse(self):
        self.assertEqual(self.champ("DURAND et durand"), "f")
        self.assertEqual(self.champ("zorglub martin"), "f")

    def test_nom_court_sensible_a_la_casse(self):
        self.assertEqual(self.champ("le abc ici"), "f")
        self.assertIsNone(self.champ("le ABC ici"))
        self.assertIsNone(self.champ("le Abc ici"))

    def test_sigle_sensible_a_la_casse(self):
        self.assertEqual(self.champ("le XYZW ici"), "f")
        self.assertIsNone(self.champ("le xyzw ici"))

    def test_nom_le_plus_long_l_emporte(self):
        self.assertEqual(sn.find_field({"f": "A&B Team"}, ["A&B", "A&B Team"]), "f")

    def test_find_field_retourne_le_champ_et_jamais_le_nom(self):
        r = sn.find_field({"problem": "rien", "tested": "avec Durand", "notes": "Zorglub Martin"}, self.NOMS)
        self.assertEqual(r, "tested")
        self.assertNotIn("Durand", r)

    def test_aucun_champ(self):
        self.assertIsNone(sn.find_field({"a": "rien", "b": ""}, self.NOMS))

    def test_liste_vide_ne_trouve_rien(self):
        self.assertIsNone(sn.find_field({"a": "Durand"}, []))


class FonctionsPartagees(unittest.TestCase):
    """Une seule lecture de la liste et une seule compilation, partagées avec le hook pre-commit."""

    def test_parse_names_ignore_vides_et_commentaires(self):
        self.assertEqual(sn.parse_names("\ufeffNomA\n\n  # commentaire\n#autre\n  NomB  \n"), ["NomA", "NomB"])
        self.assertEqual(sn.parse_names("# seulement\n\n"), [])

    def test_patterns_et_match_line(self):
        motifs = sn.patterns(["NomA", "ABC"])
        self.assertTrue(sn.line_matches(motifs, "voir NomA ici"))
        self.assertTrue(sn.line_matches(motifs, "le sigle ABC"))
        self.assertFalse(sn.line_matches(motifs, "le sigle abc"))
        self.assertFalse(sn.line_matches(motifs, "MonNomAbis"))

    def test_le_hook_n_a_plus_sa_propre_copie_des_regles(self):
        hook = (Path(__file__).resolve().parents[2] / "tools" / "hooks" / "pre-commit").read_text(encoding="utf-8")
        self.assertIn("import sensitive_names", hook)
        for copie in ("def compiler", "def sensible_a_la_casse", "re.compile", "import re"):
            self.assertNotIn(copie, hook)


if __name__ == "__main__":
    unittest.main()
