"""
Tests de tools/outside_library.py : la liste « hors bibliothèque » est calculée depuis un catalogue.

    uv run --with pyyaml python -m unittest discover -s tests/outside_library -v

Catalogues et références fictifs dans un dossier temporaire ; seul tools/references_postures.yaml est lu pour
vérifier sa forme.
"""
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import outside_library as hb  # noqa: E402


def ecrire(dossier: Path, nom: str, donnees: dict) -> Path:
    chemin = dossier / nom
    chemin.write_text(yaml.safe_dump(donnees, allow_unicode=True), encoding="utf-8")
    return chemin


class TestCalcul(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dossier = Path(self.temp.name)
        self.refs = ecrire(self.dossier, "refs.yaml", {"delivery": [
            {"titre": "Livre Fictif A", "auteurs": ["Auteur Fictif A"]},
            {"titre": "Livre Fictif B", "auteurs": ["Auteur Fictif B"]},
            {"titre": "Scrum Guide", "document": True},
            {"titre": "Étrange livre fictif", "auteurs": ["Auteur Fictif C"]},
        ]})

    def tearDown(self):
        self.temp.cleanup()

    def catalogue(self, entrees: dict) -> Path:
        return ecrire(self.dossier, "catalogue.yaml", entrees)

    def test_livre_present_est_exclu_de_la_liste(self):
        cat = self.catalogue({"a.pdf": {"titre": "Livre Fictif A: Sous-titre fictif", "auteurs": ["Prénom Auteur Fictif A"]},
                              "b.pdf": {"titre": "Livre Fictif B", "auteurs": ["Prénom Auteur Fictif B"]}})
        titres = [o["titre"] for o in hb.hors_bibliotheque("delivery", cat, self.refs)]
        self.assertNotIn("Livre Fictif A", titres)
        self.assertNotIn("Livre Fictif B", titres)

    def test_document_hors_bibliotheque_tant_qu_il_n_est_pas_indexe(self):
        titres = [o["titre"] for o in hb.hors_bibliotheque("delivery", self.catalogue({}), self.refs)]
        self.assertIn("Scrum Guide", titres)

    def test_document_indexe_n_est_plus_hors_bibliotheque(self):
        cat = self.catalogue({"a.md": {"titre": "The Scrum Guide", "auteurs": ["Schwaber", "Sutherland"]}})
        titres = [o["titre"] for o in hb.hors_bibliotheque("delivery", cat, self.refs)]
        self.assertNotIn("Scrum Guide", titres)

    def test_relations_imprimees_pour_la_posture(self):
        refs = ecrire(self.dossier, "refs2.yaml", {"scaling": [
            {"titre": "Architecture for Flow", "auteurs": ["Kaiser"], "relations": [{"type": "commente", "avec": "Team Topologies"}]},
            {"titre": "Handbook", "auteurs": ["Quick"], "relations": [{"type": "ne_pas_confondre", "avec": "Doc SAFe", "note": "guide de coachs"}]},
            {"titre": "Sans lien", "auteurs": ["X"]}]})
        lignes = hb.rendre_relations("scaling", refs)
        self.assertEqual(len(lignes), 2)
        self.assertIn("commente Team Topologies", lignes[0])
        self.assertIn("ne pas confondre avec Doc SAFe", lignes[1])
        self.assertIn("guide de coachs", lignes[1])
        self.assertEqual(hb.rendre_relations("inconnue", refs), [])

    def test_meme_titre_autre_auteur_ne_compte_pas(self):
        cat = self.catalogue({"a.pdf": {"titre": "Livre Fictif B", "auteurs": ["Quelqu'un d'autre"]}})
        titres = [o["titre"] for o in hb.hors_bibliotheque("delivery", cat, self.refs)]
        self.assertIn("Livre Fictif B", titres)

    def test_accents_et_casse_ignores(self):
        cat = self.catalogue({"a.pdf": {"titre": "ETRANGE LIVRE FICTIF", "auteurs": ["Prénom Auteur Fictif C"]}})
        titres = [o["titre"] for o in hb.hors_bibliotheque("delivery", cat, self.refs)]
        self.assertNotIn("Étrange livre fictif", titres)

    def test_catalogue_vide_tout_est_hors_bibliotheque(self):
        cat = self.catalogue({})
        self.assertEqual(len(hb.hors_bibliotheque("delivery", cat, self.refs)), 4)

    def test_catalogue_illisible_ne_classe_rien(self):
        absent = self.dossier / "absent.yaml"
        self.assertIsNone(hb.hors_bibliotheque("delivery", absent, self.refs))
        texte = " ".join(hb.rendre("delivery", absent, self.refs))
        self.assertIn("pas calculée", texte)

    def test_posture_inconnue(self):
        self.assertIn("posture inconnue", hb.rendre("inconnue", self.catalogue({}), self.refs)[0])

    def test_catalogue_par_variable_d_environnement(self):
        import os
        cat = self.catalogue({"a.pdf": {"titre": "Livre Fictif A", "auteurs": ["Auteur Fictif A"]}})
        os.environ["PMZILLA_LAB_CATALOGUE"] = str(cat)
        try:
            self.assertEqual(hb.catalogue_par_defaut(), cat)
        finally:
            del os.environ["PMZILLA_LAB_CATALOGUE"]


class TestReferencesDuDepot(unittest.TestCase):
    def test_forme_du_fichier_de_references(self):
        donnees = yaml.safe_load((RACINE / "tools" / "references_postures.yaml").read_text(encoding="utf-8"))
        self.assertEqual(sorted(donnees), sorted(hb.POSTURES))
        for posture, ouvrages in donnees.items():
            for o in ouvrages:
                with self.subTest(posture=posture, titre=o.get("titre")):
                    self.assertTrue(o.get("titre"))
                    self.assertTrue(o.get("document") or o.get("auteurs"), "un livre a au moins un auteur")

    def test_les_relations_du_depot_visent_des_types_connus(self):
        donnees = yaml.safe_load((RACINE / "tools" / "references_postures.yaml").read_text(encoding="utf-8"))
        for posture, ouvrages in donnees.items():
            for o in ouvrages:
                for lien in o.get("relations") or []:
                    self.assertIn(lien["type"], hb.RELATIONS, (posture, o["titre"]))
                    self.assertTrue(lien.get("avec"), (posture, o["titre"]))

    def test_un_catalogue_vide_donne_une_liste_non_vide_pour_chaque_posture(self):
        with tempfile.TemporaryDirectory() as temp:
            cat = ecrire(Path(temp), "c.yaml", {})
            for posture in hb.POSTURES:
                self.assertTrue(hb.hors_bibliotheque(posture, cat))


if __name__ == "__main__":
    unittest.main()
