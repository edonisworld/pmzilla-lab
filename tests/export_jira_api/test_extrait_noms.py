"""Sous-commande extract-teams et service function extrait_des_noms (change team-names-readable, groupe 3, tâche 3.1).

    bash tests/run_all.sh export_jira_api </dev/null

Spécifications : jira-flow-organisation (« Team-names extract written by the author », « Team-names extract runs outside sessions and
prints counts only »). Aucun appel à Jira, aucune base, sources INVENTÉES avec des marqueurs : aucun nom de site, de département, de
Mission Team, aucun effectif ni commentaire ne doit atteindre le résultat ni le fichier (décision a) ; aucun nom d'équipe dans la
console. La variable CLAUDECODE est retirée de l'environnement du test ; le test de refus la pose.
"""
import os
import stat
import unittest
from unittest import mock

import yaml

from test_equipes_commandes import Socle
from test_catalogue_export import catalogue, entree

import export_jira_api_equipes as eq          # noqa: E402  (le chemin de tools/ est posé par les imports ci-dessus)
import flow_organisation as org               # noqa: E402

SITE, DEPARTEMENT, MISSION, COMMENTAIRE = "ZZSITE", "ZZDEPT", "ZZMISSION", "ZZCOMMENTAIRE"
EFFECTIF = "7731"
MARQUEURS = (SITE, DEPARTEMENT, MISSION, COMMENTAIRE, EFFECTIF, "source_date", "headcount", "pilot")

REF = f"""# {COMMENTAIRE} referentiel
source_date: 2026-10-01
sites: [{SITE}]
departments:
  - name: {DEPARTEMENT}
    site: {SITE}
    headcount: {EFFECTIF}
    mission_teams:
      - name: {MISSION}
        discovery_workflow_pilot: true
        teams: [Eq-Alpha, Eq-Beta, Eq-Gamma]
teams:
  - name: Eq-Alpha          # {COMMENTAIRE}
    headcount: {EFFECTIF}
    jira_team_ids: ['1', '11']
    type: Development Team
  - name: Eq-Beta
    headcount: {EFFECTIF}
    jira_team_ids: ['2']
  - name: Eq-Gamma
    headcount: {EFFECTIF}
cross_cutting_teams: [Eq-Gamma]
"""
CAT = "# " + COMMENTAIRE + "\n" + catalogue(
    entree("Lib-Alpha", "'1', '11'", "    type: Development Team\n"),
    entree("Lib-Beta", "'2'", "    type: Verification Team\n"),
    entree("Lib-Dehors", "'50', '51'", "    type: Other Team\n    obsolete: true\n"),
    entree("Lib-Libre", "'60'"),
)


class Extrait(Socle):
    def lire_extrait(self):
        return yaml.safe_load((self.flux / "equipes-lisibles.yaml").read_text(encoding="utf-8"))

    def sources(self, ref=REF, cat=CAT):
        if ref is not None:
            self.ecrire("organisation.yaml", ref)
        if cat is not None:
            self.ecrire("equipes-jira.yaml", cat)


class ServiceFunction(unittest.TestCase):
    def donnees(self, ref=REF, cat=CAT, date=None):
        referentiel = org.charger(ref) if ref is not None else None
        catalogue_ = org.charger_catalogue(cat) if cat is not None else org.Catalogue()
        return eq.extrait_des_noms(referentiel, catalogue_)

    def test_equipes_du_referentiel(self):
        extrait = self.donnees()
        par_nom = {e["name"]: e for e in extrait.referential_teams}
        self.assertEqual(list(par_nom), ["Eq-Alpha", "Eq-Beta", "Eq-Gamma"])
        self.assertEqual(par_nom["Eq-Alpha"]["jira_team_ids"], ["1", "11"])
        self.assertFalse(par_nom["Eq-Alpha"]["without_identifier"])
        self.assertEqual(par_nom["Eq-Alpha"]["type"], "Development Team")            # forcé
        self.assertEqual(par_nom["Eq-Beta"]["type"], "Verification Team")            # déduit du catalogue
        self.assertEqual(par_nom["Eq-Gamma"]["jira_team_ids"], [])
        self.assertTrue(par_nom["Eq-Gamma"]["without_identifier"])
        self.assertIsNone(par_nom["Eq-Gamma"]["type"])

    def test_entrees_du_catalogue(self):
        par_nom = {e["name"]: e for e in self.donnees().catalogue_teams}
        self.assertEqual(list(par_nom), ["Lib-Alpha", "Lib-Beta", "Lib-Dehors", "Lib-Libre"])
        self.assertFalse(par_nom["Lib-Alpha"]["outside_referential"])
        self.assertFalse(par_nom["Lib-Alpha"]["obsolete"])
        self.assertTrue(par_nom["Lib-Dehors"]["outside_referential"])
        self.assertTrue(par_nom["Lib-Dehors"]["obsolete"])
        self.assertEqual(par_nom["Lib-Dehors"]["jira_team_ids"], ["50", "51"])
        self.assertEqual(par_nom["Lib-Dehors"]["type"], "Other Team")
        self.assertIsNone(par_nom["Lib-Libre"]["type"])
        self.assertTrue(par_nom["Lib-Libre"]["outside_referential"])

    def test_aucun_champ_hors_conception(self):
        extrait = self.donnees()
        self.assertEqual({k for e in extrait.referential_teams for k in e}, {"name", "jira_team_ids", "without_identifier", "type"})
        self.assertEqual({k for e in extrait.catalogue_teams for k in e},
                         {"name", "jira_team_ids", "type", "obsolete", "outside_referential"})
        texte = repr(extrait)
        for marqueur in MARQUEURS[:5]:
            self.assertNotIn(marqueur, texte)

    def test_une_source_absente_donne_une_liste_vide(self):
        self.assertEqual(self.donnees(ref=None).referential_teams, [])
        self.assertEqual(len(self.donnees(ref=None).catalogue_teams), 4)
        self.assertTrue(all(e["outside_referential"] for e in self.donnees(ref=None).catalogue_teams))
        self.assertEqual(self.donnees(cat=None).catalogue_teams, [])
        self.assertEqual(len(self.donnees(cat=None).referential_teams), 3)


class Sous_commande(Extrait):
    def test_ecrit_les_noms_et_rien_d_autre(self):
        self.sources()
        code, sortie = self.lancer("extract-teams")
        self.assertEqual(code, 0, sortie)
        texte = (self.flux / "equipes-lisibles.yaml").read_text(encoding="utf-8")
        for marqueur in MARQUEURS[:5]:
            self.assertNotIn(marqueur, texte)
        donnees = self.lire_extrait()
        self.assertEqual([e["name"] for e in donnees["referential_teams"]], ["Eq-Alpha", "Eq-Beta", "Eq-Gamma"])
        self.assertEqual(len(donnees["catalogue_teams"]), 4)
        self.assertEqual(set(donnees), {"extracted_on", "referential_teams", "catalogue_teams"})

    def test_droits_600_et_remplacement_atomique(self):
        self.sources()
        destination = self.flux / "equipes-lisibles.yaml"
        destination.write_text("ancien: contenu\n", encoding="utf-8")
        code, sortie = self.lancer("extract-teams")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
        self.assertNotIn("ancien", destination.read_text(encoding="utf-8"))
        self.assertEqual([p for p in self.fichiers() if p.endswith(".tmp")], [])         # aucun temporaire ne reste

    def test_console_en_francais_sans_aucun_nom(self):
        self.sources()
        code, sortie = self.lancer("extract-teams")
        self.assertEqual(code, 0, sortie)
        self.assertIn("extrait des noms d'équipes écrit : 3 équipes du référentiel, dont 1 sans identifiant ; 4 entrées du catalogue",
                      sortie)
        for interdit in ("Eq-", "Lib-", *MARQUEURS):
            self.assertNotIn(interdit, sortie)

    def test_console_en_anglais_sans_aucun_nom(self):
        self.sources()
        code, sortie = self.lancer("extract-teams", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("team-names extract written: 3 referential teams, 1 without identifier; 4 catalogue entries", sortie)
        for interdit in ("Eq-", "Lib-", *MARQUEURS):
            self.assertNotIn(interdit, sortie)

    def test_aucun_appel_a_jira(self):
        self.sources()
        self.lancer("extract-teams")
        self.assertEqual(self.faux.requetes, [])
        self.assertEqual(self.faux.appels, [])

    def test_refus_en_session_avant_toute_lecture(self):
        self.sources()
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), mock.patch("pathlib.Path.read_text", side_effect=AssertionError("lu")), \
                mock.patch("pathlib.Path.is_file", side_effect=AssertionError("lu")), \
                mock.patch("pathlib.Path.exists", side_effect=AssertionError("lu")), \
                mock.patch("builtins.open", side_effect=AssertionError("ouvert")), \
                mock.patch("os.open", side_effect=AssertionError("ouvert")):
            code, sortie = self.lancer("extract-teams")
        self.assertEqual(code, 3, sortie)
        self.assertIn("Refusé dans une session Claude Code", sortie)
        self.assertFalse((self.flux / "equipes-lisibles.yaml").exists())

    def test_refus_en_session_en_anglais(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            code, sortie = self.lancer("extract-teams", "--language", "en")
        self.assertEqual(code, 3, sortie)
        self.assertIn("Refused inside a Claude Code session", sortie)

    def test_source_refusee_code_1_rien_n_est_ecrit(self):
        self.sources(cat="teams:\n  - name: Lib-X\n    jira_team_ids: ['1']\n    cle_inconnue: 1\n")
        destination = self.flux / "equipes-lisibles.yaml"
        destination.write_text("ancien: contenu\n", encoding="utf-8")
        code, sortie = self.lancer("extract-teams")
        self.assertEqual(code, 1, sortie)
        self.assertEqual(destination.read_text(encoding="utf-8"), "ancien: contenu\n")        # ni écrit ni remplacé
        self.assertNotIn("Lib-X", sortie)

    def test_referentiel_refuse_code_1_rien_n_est_ecrit(self):
        self.sources(ref="source_date: 2026-10-01\ncle_inconnue: 1\n")
        code, sortie = self.lancer("extract-teams")
        self.assertEqual(code, 1, sortie)
        self.assertFalse((self.flux / "equipes-lisibles.yaml").exists())

    def test_aucune_source_code_1_phrase_de_la_conception(self):
        code, sortie = self.lancer("extract-teams")
        self.assertEqual(code, 1, sortie)
        self.assertIn("aucune source d'équipes à extraire : ni référentiel ni catalogue ; rien n'est écrit", sortie)
        self.assertFalse((self.flux / "equipes-lisibles.yaml").exists())

    def test_aucune_source_en_anglais(self):
        code, sortie = self.lancer("extract-teams", "--language", "en")
        self.assertEqual(code, 1, sortie)
        self.assertIn("no team source to extract: neither referential nor catalogue; nothing written", sortie)

    def test_catalogue_absent_seul_le_referentiel_est_extrait(self):
        self.sources(cat=None)
        code, sortie = self.lancer("extract-teams")
        self.assertEqual(code, 0, sortie)
        donnees = self.lire_extrait()
        self.assertEqual(len(donnees["referential_teams"]), 3)
        self.assertEqual(donnees["catalogue_teams"], [])

    def test_referentiel_absent_seul_le_catalogue_est_extrait(self):
        self.sources(ref=None)
        code, sortie = self.lancer("extract-teams")
        self.assertEqual(code, 0, sortie)
        donnees = self.lire_extrait()
        self.assertEqual(donnees["referential_teams"], [])
        self.assertEqual(len(donnees["catalogue_teams"]), 4)

    def test_echec_d_ecriture_code_1_sans_detail(self):
        self.sources()
        with mock.patch("os.replace", side_effect=PermissionError("secret-Eq-Alpha")):
            code, sortie = self.lancer("extract-teams")
        self.assertEqual(code, 1, sortie)
        self.assertIn("extrait des noms d'équipes non écrit : PermissionError", sortie)
        self.assertNotIn("secret", sortie)
        self.assertFalse((self.flux / "equipes-lisibles.yaml").exists())
        self.assertEqual([p for p in self.fichiers() if p.endswith(".tmp")], [])

    def test_echec_d_ecriture_en_anglais(self):
        self.sources()
        with mock.patch("os.replace", side_effect=PermissionError("x")):
            code, sortie = self.lancer("extract-teams", "--language", "en")
        self.assertEqual(code, 1, sortie)
        self.assertIn("team-names extract not written: PermissionError", sortie)

    def test_option_inconnue_code_2(self):
        code, sortie = self.lancer("extract-teams", "--add", "1")
        self.assertEqual(code, 2, sortie)

    def test_la_sous_commande_figure_dans_l_aide(self):
        code, sortie = self.lancer("--help")
        self.assertEqual(code, 0, sortie)
        self.assertIn("extract-teams", sortie)


if __name__ == "__main__":
    unittest.main()
