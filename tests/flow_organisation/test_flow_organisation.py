"""tools/flow_organisation.py : lecture stricte du référentiel d'organisation, refus sans valeur, groupes.

Données inventées, chaînes distinctives (noms d'équipes, de sites, identifiants) vérifiées absentes des messages ;
aucun accès à Flux-Lab/ : les fichiers sont des fichiers temporaires."""
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_organisation as org  # noqa: E402
from yaml_strict import ErreurConfig  # noqa: E402

BASE = """source_date: 2026-10-01
sites: [Zorblax-Site, Quimbo-Site]
departments:
  - name: Dept-Wumpa
    site: Zorblax-Site
    headcount: 12
    mission_teams:
      - name: MT-Frobnic
        discovery_workflow_pilot: true
        teams: [Eq-Glimmer, Eq-Snarf]
      - name: MT-Plinth
        teams: [Eq-Vexor]
  - name: Dept-Direct
    site: Quimbo-Site
    headcount: 4
    teams: [Eq-Direct]
teams:
  - name: Eq-Glimmer
    headcount: 5
    jira_team_ids: ["id-g1", "id-g2"]
  - name: Eq-Snarf
    headcount: 3
    site: Quimbo-Site
    jira_team_ids: [id-s1]
  - name: Eq-Vexor
    headcount: 7
  - name: Eq-Direct
    headcount: 2
    jira_team_ids: []
  - name: Eq-Transverse
    headcount: 1
cross_cutting_teams: [Eq-Transverse]
"""

DISTINCTIFS = ["Zorblax", "Quimbo", "Wumpa", "Frobnic", "Plinth", "Glimmer", "Snarf", "Vexor", "Eq-Direct", "Transverse",
               "id-g1", "id-g2", "id-s1", "Dept-Direct"]


def refus(texte: str) -> str:
    with unittest.TestCase().assertRaises(ErreurConfig) as r:
        org.charger(texte)
    assert r.exception.code == 1 or str(r.exception.code) == str(r.exception), r.exception.code
    return str(r.exception)


class Lecture(unittest.TestCase):
    def setUp(self):
        self.ref = org.charger(BASE)

    def test_structure_lue(self):
        self.assertEqual(str(self.ref.source_date), "2026-10-01")
        self.assertEqual(self.ref.sites, ("Zorblax-Site", "Quimbo-Site"))
        self.assertEqual(self.ref.teams["Eq-Glimmer"].effectif, 5)
        self.assertEqual(self.ref.teams["Eq-Snarf"].site, "Quimbo-Site")
        self.assertEqual(self.ref.departments[0].mission_teams[0].equipes, ("Eq-Glimmer", "Eq-Snarf"))
        self.assertTrue(self.ref.departments[0].mission_teams[0].pilote_discovery_workflow)
        self.assertFalse(self.ref.departments[0].mission_teams[1].pilote_discovery_workflow)
        self.assertEqual(self.ref.departments[1].equipes_directes, ("Eq-Direct",))
        self.assertEqual(self.ref.cross_cutting_teams, ("Eq-Transverse",))

    def test_identifiants_jira(self):
        self.assertEqual(self.ref.team_for_jira_id("id-g2"), "Eq-Glimmer")
        self.assertEqual(self.ref.team_for_jira_id("id-s1"), "Eq-Snarf")
        self.assertIsNone(self.ref.team_for_jira_id("inconnu"))
        self.assertEqual(self.ref.jira_ids_count, 3)
        self.assertTrue(self.ref.has_jira_ids)

    def test_identifiant_entier_non_guillemete(self):
        ref = org.charger(BASE.replace("[id-s1]", "[1234]"))
        self.assertEqual(ref.team_for_jira_id(1234), "Eq-Snarf")
        self.assertEqual(ref.team_for_jira_id("1234"), "Eq-Snarf")

    def test_sans_identifiant(self):
        texte = "\n".join(l for l in BASE.splitlines() if "jira_team_ids" not in l)
        ref = org.charger(texte)
        self.assertFalse(ref.has_jira_ids)
        self.assertEqual(ref.jira_ids_count, 0)

    def test_rattachements(self):
        self.assertEqual(self.ref.mission_team_of("Eq-Snarf"), "MT-Frobnic")
        self.assertIsNone(self.ref.mission_team_of("Eq-Direct"))
        self.assertIsNone(self.ref.mission_team_of("Eq-Inconnue"))
        self.assertEqual(self.ref.department_of("Eq-Vexor"), "Dept-Wumpa")
        self.assertEqual(self.ref.department_of("Eq-Direct"), "Dept-Direct")
        self.assertIsNone(self.ref.department_of("Eq-Transverse"))

    def test_site_de_l_equipe_sinon_du_departement(self):
        self.assertEqual(self.ref.site_of("Eq-Snarf"), "Quimbo-Site")      # le sien
        self.assertEqual(self.ref.site_of("Eq-Glimmer"), "Zorblax-Site")   # celui du département
        self.assertEqual(self.ref.site_of("Eq-Direct"), "Quimbo-Site")
        self.assertIsNone(self.ref.site_of("Eq-Transverse"))
        self.assertIsNone(self.ref.site_of("Eq-Inconnue"))


class Groupes(unittest.TestCase):
    def setUp(self):
        self.ref = org.charger(BASE)

    def test_par_mission_team(self):
        g = self.ref.groups("mission-team")
        self.assertEqual(g["MT-Frobnic"], {"teams": ["Eq-Glimmer", "Eq-Snarf"], "headcount": 8})
        self.assertEqual(g["MT-Plinth"], {"teams": ["Eq-Vexor"], "headcount": 7})
        self.assertEqual(g["sans Mission Team"], {"teams": ["Eq-Direct", "Eq-Transverse"], "headcount": 3})
        self.assertEqual(list(g), sorted(g))

    def test_par_site(self):
        g = self.ref.groups("site")
        self.assertEqual(g["Zorblax-Site"], {"teams": ["Eq-Glimmer", "Eq-Vexor"], "headcount": 12})
        self.assertEqual(g["Quimbo-Site"], {"teams": ["Eq-Direct", "Eq-Snarf"], "headcount": 5})
        self.assertEqual(g["sans site"], {"teams": ["Eq-Transverse"], "headcount": 1})

    def test_somme_des_groupes_egale_total(self):
        for by in org.GROUPEMENTS:
            self.assertEqual(sum(v["headcount"] for v in self.ref.groups(by).values()), 18)
            self.assertEqual(sum(len(v["teams"]) for v in self.ref.groups(by).values()), 5)

    def test_hors_referentiel(self):
        self.assertEqual(org.outside_label("fr"), "hors référentiel")
        self.assertEqual(org.outside_label("en"), "outside the referential")
        self.assertEqual(org.outside_label("de"), "hors référentiel")
        self.assertEqual(self.ref.group_of("Eq-Inconnue", "site", "en"), "outside the referential")
        self.assertEqual(self.ref.group_of("Eq-Inconnue", "mission-team"), "hors référentiel")
        self.assertEqual(self.ref.group_of("Eq-Snarf", "mission-team"), "MT-Frobnic")
        self.assertNotIn("hors référentiel", self.ref.groups("site"))

    def test_resume_de_structure_alphabetique_sans_ratio(self):
        resume = self.ref.structure_summary("mission-team")
        self.assertEqual([r["group"] for r in resume], sorted(r["group"] for r in resume))
        self.assertEqual(resume[0], {"group": "MT-Frobnic", "teams": 2, "headcount": 8})
        for ligne in resume:   # que des effectifs et des nombres d'équipes : aucune autre colonne
            self.assertEqual(set(ligne), {"group", "teams", "headcount"})

    def test_ordre_alphabetique_independant_des_effectifs(self):
        # le plus gros effectif n'est pas en tête : l'ordre ne suit aucun chiffre
        texte = BASE.replace("headcount: 7", "headcount: 700")
        noms = [r["group"] for r in org.charger(texte).structure_summary("mission-team")]
        self.assertEqual(noms, sorted(noms))

    def test_groupement_inconnu(self):
        with self.assertRaises(ValueError):
            self.ref.groups("team")


class Refus(unittest.TestCase):
    def verifier(self, message, attendus=(), absents=()):
        for a in attendus:
            self.assertIn(a, message)
        for d in list(absents) + DISTINCTIFS:
            self.assertNotIn(d, message)

    def test_cle_inconnue_a_chaque_niveau(self):
        cas = [
            ("sites: [", "extra_racine: 1\nsites: [", "extra_racine", "L2"),
            ("    headcount: 12\n", "    headcount: 12\n    extra_dept: 1\n", "departments[0].extra_dept", "L7"),
            ("        discovery_workflow_pilot: true\n", "        discovery_workflow_pilot: true\n        extra_mt: 1\n",
             "departments[0].mission_teams[0].extra_mt", "L10"),
            ("    headcount: 5\n", "    headcount: 5\n    extra_eq: 1\n", "teams[0].extra_eq", "L20"),
        ]
        for ancien, nouveau, chemin, ligne in cas:
            with self.subTest(chemin=chemin):
                self.verifier(refus(BASE.replace(ancien, nouveau, 1)), [chemin, ligne])

    def test_aucun_champ_de_personne(self):
        for cle in ("manager", "owner"):
            with self.subTest(cle=cle):
                texte = BASE.replace("    headcount: 5\n", f"    headcount: 5\n    {cle}: Quidam-Unique\n", 1)
                m = refus(texte)
                self.assertIn(f"teams[0].{cle}", m)
                self.assertNotIn("Quidam-Unique", m)
                texte = BASE.replace("    headcount: 12\n", f"    headcount: 12\n    {cle}: Quidam-Unique\n", 1)
                self.assertNotIn("Quidam-Unique", refus(texte))

    def test_equipe_non_decrite_dans_une_mission_team(self):
        m = refus(BASE.replace("teams: [Eq-Glimmer, Eq-Snarf]", "teams: [Eq-Glimmer, Eq-Fantome]"))
        self.verifier(m, ["departments[0].mission_teams[0].teams[1]", "non décrite"], ["Fantome"])

    def test_equipe_non_decrite_dans_un_departement(self):
        m = refus(BASE.replace("teams: [Eq-Direct]", "teams: [Eq-Fantome]"))
        self.verifier(m, ["departments[1].teams[0]", "non décrite"], ["Fantome"])

    def test_equipe_non_decrite_transverse(self):
        m = refus(BASE.replace("cross_cutting_teams: [Eq-Transverse]", "cross_cutting_teams: [Eq-Fantome]"))
        self.verifier(m, ["cross_cutting_teams[0]", "non décrite"], ["Fantome"])

    def test_equipe_dans_deux_mission_teams(self):
        m = refus(BASE.replace("teams: [Eq-Vexor]", "teams: [Eq-Vexor, Eq-Glimmer]"))
        self.verifier(m, ["departments[0].mission_teams[0].teams", "departments[0].mission_teams[1].teams", "L10", "L12",
                          "deux fois"])

    def test_identifiant_sous_deux_equipes(self):
        m = refus(BASE.replace("jira_team_ids: [id-s1]", 'jira_team_ids: ["id-g2"]'))
        self.verifier(m, ["teams[0].jira_team_ids", "teams[1].jira_team_ids", "L20", "L24", "deux équipes"])

    def test_identifiant_repete_dans_la_meme_equipe_n_est_pas_refuse(self):
        org.charger(BASE.replace('["id-g1", "id-g2"]', '["id-g1", "id-g1"]'))

    def test_site_non_declare(self):
        m = refus(BASE.replace("site: Zorblax-Site", "site: Ailleurs-Unique"))
        self.verifier(m, ["departments[0].site", "non déclaré"], ["Ailleurs"])
        m = refus(BASE.replace("site: Quimbo-Site\n    jira_team_ids: [id-s1]", "site: Ailleurs-Unique\n    jira_team_ids: [id-s1]"))
        self.verifier(m, ["teams[1].site", "non déclaré"], ["Ailleurs"])

    def test_effectif_invalide(self):
        for valeur in ("douze-unique", "-3", "2.5", "true", "null"):
            with self.subTest(valeur=valeur):
                m = refus(BASE.replace("headcount: 5", f"headcount: {valeur}"))
                self.verifier(m, ["teams[0].headcount", "L19", "entier"], ["douze-unique"])
        m = refus(BASE.replace("headcount: 12", "headcount: -1"))
        self.verifier(m, ["departments[0].headcount", "L6"])

    def test_departement_avec_les_deux(self):
        texte = BASE.replace("    teams: [Eq-Direct]\n", "    teams: [Eq-Direct]\n    mission_teams: []\n")
        self.verifier(refus(texte), ["departments[1]", "exactement l'une"])

    def test_departement_sans_aucun(self):
        texte = BASE.replace("    teams: [Eq-Direct]\n", "")
        self.verifier(refus(texte), ["departments[1]", "exactement l'une"])

    def test_cle_obligatoire_absente(self):
        texte = "\n".join(l for l in BASE.splitlines() if not l.startswith("source_date"))
        self.verifier(refus(texte), ["source_date", "obligatoire"])

    def test_equipe_decrite_deux_fois(self):
        m = refus(BASE.replace("name: Eq-Vexor", "name: Eq-Glimmer"))
        self.verifier(m, ["teams[0].name", "teams[2].name", "deux fois"])

    def test_equipe_rangee_dans_un_departement_et_une_mission_team(self):
        m = refus(BASE.replace("teams: [Eq-Direct]", "teams: [Eq-Direct, Eq-Vexor]"))
        self.verifier(m, ["departments[1].teams", "deux fois"])

    def test_cle_ecrite_deux_fois(self):
        m = refus(BASE.replace("    headcount: 5\n", "    headcount: 5\n    headcount: 6\n", 1))
        self.verifier(m, ["deux fois", "teams.headcount", "L19", "L20"])

    def test_yaml_illisible_sans_repeter_le_texte(self):
        m = refus("sites: [Zorblax-Site\nteams: {Vexor-Unique: [\n")
        self.verifier(m, ["illisible"], ["Vexor-Unique"])

    def test_pas_un_bloc(self):
        self.verifier(refus("- Zorblax-Site\n"), ["bloc de clés"])
        self.verifier(refus("source_date: 2026-10-01\nsites: Zorblax-Site\ndepartments: []\nteams: []\n"), ["sites", "liste"])

    def test_pilote_non_booleen(self):
        m = refus(BASE.replace("discovery_workflow_pilot: true", "discovery_workflow_pilot: oui-unique"))
        self.verifier(m, ["discovery_workflow_pilot", "true ou false"], ["oui-unique"])

    def test_date_invalide(self):
        self.verifier(refus(BASE.replace("2026-10-01", "hier-unique")), ["source_date"], ["hier-unique"])


class Fichiers(unittest.TestCase):
    def test_fichier_absent_donne_la_structure(self):
        with tempfile.TemporaryDirectory() as t:
            chemin = Path(t) / "organisation.yaml"
            with self.assertRaises(ErreurConfig) as r:
                org.charger_fichier(chemin)
            m = str(r.exception)
            self.assertEqual(r.exception.code, m)
            self.assertIn("absent", m)
            for cle in ("source_date", "sites", "departments", "mission_teams", "teams", "headcount", "jira_team_ids",
                        "cross_cutting_teams", "discovery_workflow_pilot"):
                self.assertIn(cle, m)
            self.assertNotIn(t, m)

    def test_si_present_rend_none_sans_fichier(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertIsNone(org.charger_si_present(Path(t) / "organisation.yaml"))

    def test_si_present_lit_le_fichier(self):
        with tempfile.TemporaryDirectory() as t:
            chemin = Path(t) / "organisation.yaml"
            chemin.write_text(BASE, encoding="utf-8")
            self.assertEqual(org.charger_si_present(chemin).team_for_jira_id("id-g1"), "Eq-Glimmer")
            self.assertEqual(org.charger_fichier(str(chemin)).jira_ids_count, 3)

    def test_si_present_refuse_un_fichier_invalide(self):
        with tempfile.TemporaryDirectory() as t:
            chemin = Path(t) / "organisation.yaml"
            chemin.write_text(BASE.replace("headcount: 5", "headcount: -5"), encoding="utf-8")
            with self.assertRaises(ErreurConfig):
                org.charger_si_present(chemin)

    def test_le_message_nomme_le_fichier_pas_le_dossier(self):
        with tempfile.TemporaryDirectory() as t:
            chemin = Path(t) / "organisation.yaml"
            chemin.write_text(BASE.replace("headcount: 5", "headcount: -5"), encoding="utf-8")
            with self.assertRaises(ErreurConfig) as r:
                org.charger_fichier(chemin)
            self.assertIn("organisation.yaml", str(r.exception))
            self.assertNotIn(t, str(r.exception))


if __name__ == "__main__":
    unittest.main()
