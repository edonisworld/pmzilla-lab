"""
Tests de sensitive_names.extract_names (change team-names-readable, design D8, tâche 5.1).

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/sensitive_names -q

Extrait inventé dans un dossier temporaire, au format de tools/export_jira_api_equipes.py (extrait_des_noms) ; le vrai extrait et la
vraie liste ne sont jamais lus. Sans chemin, l'extrait est celui qui voisine la liste (PMZILLA_LAB_SENSITIVE_NAMES).
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import sensitive_names as sn  # noqa: E402

EXTRAIT = """extracted_on: '2026-10-19'
referential_teams:
- name: Zorglubian Squad
  jira_team_ids:
  - '111'
  without_identifier: false
  type: stream-aligned
- name: Platform Team
  jira_team_ids: []
  without_identifier: true
  type: null
- name: Quarkonaute
  jira_team_ids: []
  without_identifier: true
  type: null
catalogue_teams:
- name: Vexilloïde Nord
  jira_team_ids:
  - '222'
  type: null
  obsolete: false
  outside_referential: true
- name: "Support Platform"
  jira_team_ids: []
  type: null
  obsolete: true
  outside_referential: true
- name: Abc
  jira_team_ids: []
  type: null
  obsolete: false
  outside_referential: true
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dossier = Path(self.temp.name)
        self.extrait = self.dossier / "equipes-lisibles.yaml"

    def ecrire(self, texte=EXTRAIT):
        self.extrait.write_text(texte, encoding="utf-8")
        return self.extrait


class ExtractNames(Base):
    def test_seuls_les_noms_distinctifs_sont_rendus(self):
        noms = sn.extract_names(self.ecrire())
        self.assertEqual(noms, ["Zorglubian Squad", "Quarkonaute", "Vexilloïde Nord"])

    def test_nom_de_mots_courants_ecarte(self):
        noms = sn.extract_names(self.ecrire())
        for commun in ("Platform Team", "Abc", "Support Platform"):
            self.assertNotIn(commun, noms)

    def test_extrait_absent_donne_une_liste_vide(self):
        self.assertEqual(sn.extract_names(self.extrait), [])

    def test_extrait_illisible_donne_une_liste_vide(self):
        self.extrait.mkdir()
        self.assertEqual(sn.extract_names(self.extrait), [])

    def test_extrait_invalide_donne_une_liste_vide(self):
        for texte in ("", "::: pas du yaml [", "- juste\n- une liste\n", "referential_teams: 3\n", "catalogue_teams:\n- 5\n- name: [x]\n"):
            with self.subTest(texte=texte[:12]):
                self.assertEqual(sn.extract_names(self.ecrire(texte)), [])

    def test_octets_invalides_donnent_une_liste_vide(self):
        self.extrait.write_bytes(b"\xff\xfe\x00name: Quarkonaute\n")
        self.assertEqual(sn.extract_names(self.extrait), [])

    def test_sans_doublon_et_sans_blanc(self):
        texte = "referential_teams:\n- name: Quarkonaute\n- name: ' Quarkonaute '\ncatalogue_teams:\n- name: Quarkonaute\n"
        self.assertEqual(sn.extract_names(self.ecrire(texte)), ["Quarkonaute"])

    def test_chemin_par_defaut_voisin_de_la_liste(self):
        liste = self.dossier / "noms.txt"
        self.ecrire()
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(liste)}):
            self.assertIn("Quarkonaute", sn.extract_names())

    def test_sans_extrait_voisin_comportement_inchange(self):
        liste = self.dossier / "noms.txt"
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(liste)}):
            self.assertEqual(sn.extract_names(), [])

    def test_la_liste_n_est_jamais_ouverte(self):
        liste = self.dossier / "noms.txt"
        liste.write_text("SecretListe\n", encoding="utf-8")
        self.ecrire()
        ouverts = []
        vrai = Path.read_text

        def espion(chemin, *a, **k):
            ouverts.append(Path(chemin).name)
            return vrai(chemin, *a, **k)

        with mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(liste)}), mock.patch.object(Path, "read_text", espion):
            sn.extract_names()
        self.assertNotIn("noms.txt", ouverts)

    def test_lecteur_sans_yaml_donne_les_memes_noms(self):
        self.ecrire()
        with mock.patch.dict(sys.modules, {"yaml": None}):
            self.assertEqual(sn.extract_names(self.extrait), ["Zorglubian Squad", "Quarkonaute", "Vexilloïde Nord"])

    def test_motifs_utilisables_avec_la_liste(self):
        motifs = sn.patterns(["Autre"] + sn.extract_names(self.ecrire()))
        self.assertTrue(sn.line_matches(motifs, "voir quarkonaute demain"))
        self.assertFalse(sn.line_matches(motifs, "voir platform team demain"))


class GenericNames(Base):
    """Liste des noms génériques (change extract-name-exclusions, design D1 à D4), noms inventés."""

    def generiques(self, contenu, dossier=None):
        chemin = (dossier or self.dossier) / sn.NOM_GENERIQUES
        if isinstance(contenu, bytes):
            chemin.write_bytes(contenu)
        else:
            chemin.write_text(contenu, encoding="utf-8")
        return chemin

    def test_constante_du_fichier(self):
        self.assertEqual(sn.NOM_GENERIQUES, "noms-generiques.txt")

    def test_sans_liste_nom_rendu(self):
        self.assertIn("Quarkonaute", sn.extract_names(self.ecrire()))

    def test_nom_liste_dans_une_autre_casse_non_rendu(self):
        self.ecrire()
        self.generiques("QUARKONAUTE\n")
        self.assertEqual(sn.extract_names(self.extrait), ["Zorglubian Squad", "Vexilloïde Nord"])

    def test_entree_partielle_ne_retire_rien(self):
        self.ecrire()
        self.generiques("Zorglubian\nSquad\n")
        self.assertIn("Zorglubian Squad", sn.extract_names(self.extrait))

    def test_pas_de_pliage_des_accents(self):
        self.ecrire()
        self.generiques("Vexilloide Nord\n")
        self.assertIn("Vexilloïde Nord", sn.extract_names(self.extrait))

    def test_commentaire_ligne_vide_et_espaces(self):
        self.ecrire()
        self.generiques("# un commentaire\n\n   \n   # indenté\n   quarkonaute   \n")
        noms = sn.extract_names(self.extrait)
        self.assertNotIn("Quarkonaute", noms)
        self.assertEqual(len(noms), 2)

    def test_commentaire_n_exclut_rien(self):
        self.ecrire()
        self.generiques("# Quarkonaute\n")
        self.assertIn("Quarkonaute", sn.extract_names(self.extrait))

    def test_marque_d_ordre_des_octets(self):
        self.ecrire()
        self.generiques(b"\xef\xbb\xbfQuarkonaute\n")
        self.assertNotIn("Quarkonaute", sn.extract_names(self.extrait))

    def test_liste_illisible_dossier_a_sa_place(self):
        self.ecrire()
        (self.dossier / sn.NOM_GENERIQUES).mkdir()
        self.assertIn("Quarkonaute", sn.extract_names(self.extrait))

    def test_liste_en_octets_invalides(self):
        self.ecrire()
        self.generiques(b"\xff\xfe\x00Quarkonaute\n")
        self.assertIn("Quarkonaute", sn.extract_names(self.extrait))

    def test_entree_qui_n_est_pas_un_nom_de_l_extrait_ignoree(self):
        self.ecrire()
        self.generiques("Inconnu Total\n")
        self.assertEqual(sn.extract_names(self.extrait), ["Zorglubian Squad", "Quarkonaute", "Vexilloïde Nord"])

    def test_liste_lue_dans_le_dossier_de_l_extrait_donne(self):
        autre = self.dossier / "autre"
        autre.mkdir()
        extrait = autre / "equipes-lisibles.yaml"
        extrait.write_text(EXTRAIT, encoding="utf-8")
        self.generiques("Quarkonaute\n")          # dossier voisin : sans effet sur l'extrait de « autre »
        self.assertIn("Quarkonaute", sn.extract_names(extrait))
        self.generiques("Quarkonaute\n", dossier=autre)
        self.assertNotIn("Quarkonaute", sn.extract_names(extrait))

    def test_chemin_par_defaut_voisin_de_la_liste(self):
        self.ecrire()
        self.generiques("Quarkonaute\n")
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.dossier / "noms.txt")}):
            self.assertNotIn("Quarkonaute", sn.extract_names())

    def test_nom_des_deux_listes_reste_reconnu_par_les_motifs(self):
        self.ecrire()
        self.generiques("Quarkonaute\n")
        sensibles = sn.parse_names("Quarkonaute\n")
        motifs = sn.patterns(sensibles + sn.extract_names(self.extrait))
        self.assertTrue(sn.line_matches(motifs, "voir quarkonaute demain"))

    def test_liste_sensible_jamais_filtree(self):
        self.generiques("Quarkonaute\n")
        self.assertEqual(sn.parse_names("Quarkonaute\n"), ["Quarkonaute"])

    def test_rien_n_est_imprime(self):
        self.ecrire()
        (self.dossier / sn.NOM_GENERIQUES).mkdir()
        with mock.patch("sys.stdout") as out, mock.patch("sys.stderr") as err:
            sn.extract_names(self.extrait)
        self.assertFalse(out.write.called or err.write.called)


if __name__ == "__main__":
    unittest.main()
