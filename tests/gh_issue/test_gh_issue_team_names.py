"""
Tests de tools/gh_issue.py : le garde-fou refuse aussi les noms distinctifs de l'extrait des noms d'équipes
(change team-names-readable, design D8, tâche 5.1). Même faux gh que test_gh_issue.py ; extrait inventé voisin de la liste factice.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import unittest

from test_gh_issue import Base, NAME

DISTINCTIF = "Quarkonaute"     # nom fictif de l'extrait
COURANT = "Platform Team"      # nom de mots courants : jamais gardé
EXTRAIT = (f"extracted_on: '2026-10-19'\nreferential_teams:\n- name: {DISTINCTIF}\n  jira_team_ids: []\n  without_identifier: true\n  type: null\n"
           f"catalogue_teams:\n- name: {COURANT}\n  jira_team_ids: []\n  type: null\n  obsolete: false\n  outside_referential: true\n")


class GardeDeLExtrait(Base):
    def poser_extrait(self, texte=EXTRAIT):
        (self.names.parent / "equipes-lisibles.yaml").write_text(texte, encoding="utf-8")

    def new(self, **sets):
        argv = ["new-feature", "--title", "Titre", "--theme", "outillage", "--milestone", "Hydra"]
        for k, v in sets.items():
            argv += ["--set", f"{k}={v}"]
        return self.run_cli(*argv)

    def test_nom_distinctif_de_l_extrait_refuse_sans_etre_imprime(self):
        self.poser_extrait()
        code, out, err = self.new(conditions=f"voir avec {DISTINCTIF} demain")
        self.assertEqual(code, 3)
        self.assertRegex(err, r"gh_issue: refused: sensitive name in body, line \d+; nothing was sent")
        self.no_leak(out, err, words=(DISTINCTIF,))
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(self.load()["issues"], [])

    def test_nom_de_l_extrait_dans_le_titre_casse_ignoree(self):
        self.poser_extrait()
        code, out, err = self.run_cli("new-feature", "--title", DISTINCTIF.upper() + " plan", "--theme", "outillage", "--milestone", "Hydra")
        self.assertEqual(code, 3)
        self.assertIn("sensitive name in title, line 1", err)
        self.no_leak(out, err, words=(DISTINCTIF,))
        self.assertEqual(self.calls(writes_only=True), [])

    def test_nom_de_l_extrait_dans_le_corps_d_une_idee(self):
        self.poser_extrait()
        code, out, err = self.run_cli("new-idea", "--title", "Idée", "--body", f"voir {DISTINCTIF}")
        self.assertEqual(code, 3)
        self.assertRegex(err, r"sensitive name in body, line \d+")
        self.no_leak(out, err, words=(DISTINCTIF,))
        self.assertEqual(self.calls(writes_only=True), [])

    def test_nom_de_mots_courants_non_refuse(self):
        self.poser_extrait()
        code, _, err = self.new(conditions=f"voir {COURANT} demain")
        self.assertEqual(code, 0, err)

    def test_nom_colle_a_une_lettre_ne_correspond_pas(self):
        self.poser_extrait()
        code, _, err = self.new(conditions=f"x{DISTINCTIF}y")
        self.assertEqual(code, 0, err)

    def test_la_liste_garde_ses_noms_avec_un_extrait(self):
        self.poser_extrait()
        code, _, err = self.new(conditions=f"voir {NAME}")
        self.assertEqual(code, 3)
        self.assertIn("sensitive name in body", err)

    def poser_generiques(self, texte):
        (self.names.parent / "noms-generiques.txt").write_text(texte, encoding="utf-8")

    def test_nom_de_la_liste_des_generiques_non_refuse(self):
        self.poser_extrait()
        self.poser_generiques(f"# générique\n  {DISTINCTIF.upper()}  \n")
        code, _, err = self.new(conditions=f"voir {DISTINCTIF} demain")
        self.assertEqual(code, 0, err)

    def test_nom_des_deux_listes_reste_refuse(self):
        self.poser_extrait()
        self.poser_generiques(f"{NAME}\n")
        (self.names.parent / "equipes-lisibles.yaml").write_text(EXTRAIT.replace(DISTINCTIF, NAME), encoding="utf-8")
        code, out, err = self.new(conditions=f"voir {NAME} demain")
        self.assertEqual(code, 3)
        self.assertIn("sensitive name in body", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_sans_extrait_comportement_inchange(self):
        code, _, err = self.new(conditions=f"voir {DISTINCTIF}")
        self.assertEqual(code, 0, err)

    def test_extrait_illisible_comportement_inchange(self):
        self.poser_extrait("cette ligne: [pas du yaml\n")
        code, _, err = self.new(conditions=f"voir {DISTINCTIF}")
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
