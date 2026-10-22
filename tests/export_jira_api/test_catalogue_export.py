"""Export : traduction par le référentiel et le catalogue ensemble (change team-mapping, groupe 4, tâches 4.1 à 4.7).

    bash tests/run_all.sh export_jira_api </dev/null

Spécifications : jira-flow-export (« Team translation through the referential and the catalogue », « Conflicting or missing team
sources stop the export », « Teams outside the organisation and obsolete teams counted apart », « Strict option for unknown team
identifiers », « Diagnose subcommand »). Faux serveur et données inventées de test_export_jira_api.py ; aucun libellé réel.
"""
import unittest

from test_referentiel_et_etiquettes import BaseAssets, REFERENTIEL, INCONNUE

# Référentiel : Equipe A (1), Equipe B (2), Equipe C (3). Tickets : ABC-1 [1], ABC-2 [2, 3], ABC-3 [4], ABC-4 [6, 5].


def catalogue(*entrees: str) -> str:
    return "teams:\n" + "".join(entrees)


def entree(nom: str, ids: str, extra: str = "") -> str:
    return f"  - name: {nom}\n    jira_team_ids: [{ids}]\n{extra}"


class Base(BaseAssets):
    def exporter_csv(self, *extra: str):
        code, sortie, chemin = self.exporter_code(*extra)
        return code, sortie, chemin

    def cellules(self, magasin):
        """Noms d'équipe de chaque ticket, dans l'ordre de l'API (les instantanés du faux magasin remplacent les colonnes du CSV)."""
        return self.equipes_par_cle()

    def ecrire_sources(self, cat: str, referentiel: str = REFERENTIEL):
        self.ecrire("organisation.yaml", referentiel)
        self.ecrire("equipes-jira.yaml", cat)


class DeuxSourcesEnsemble(Base):
    def test_referentiel_seul_et_catalogue_seul_ensemble_dans_l_ordre_de_l_api(self):
        self.faux.tickets["ABC-5"] = {**self.faux.tickets["ABC-1"], **{"customfield_10001": [
            {"workspaceId": "w", "id": "w:1", "objectId": "1"}, {"workspaceId": "w", "id": "w:4", "objectId": "4"}]}}
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'")))
        code, sortie, chemin = self.exporter_csv()
        self.assertEqual(code, 0, sortie)
        cellules = self.cellules(chemin)
        self.assertEqual(cellules["ABC-5"], ["Equipe A", "Libelle-Quimbo"])
        self.assertEqual(cellules["ABC-3"], ["Libelle-Quimbo"])
        self.assertNotIn(INCONNUE, cellules["ABC-5"] + cellules["ABC-3"])

    def test_identifiant_dans_les_deux_fichiers_le_nom_du_referentiel_l_emporte(self):
        self.ecrire_sources(catalogue(entree("Libelle-Plinth", "'1'", "    type: Development Team\n")))
        code, sortie, chemin = self.exporter_csv()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.cellules(chemin)["ABC-1"], ["Equipe A"])
        self.assertNotIn("hors organisation", sortie)             # un identifiant des deux fichiers n'est pas hors organisation
        self.assertNotIn("refus", sortie.lower())
        self.assertNotIn("Plinth", sortie)

    def test_meme_nom_dans_les_deux_fichiers_avec_tous_les_identifiants_listes_accepte(self):
        self.ecrire_sources(catalogue(entree("Equipe A", "'1'")))
        code, sortie, chemin = self.exporter_csv()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.cellules(chemin)["ABC-1"], ["Equipe A"])

    def test_la_table_n_est_jamais_lue_ni_combinee(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'")))
        self.ecrire("equipes-assets.yaml", "equipes: {'5': Table E, '6': Table F}\n")
        code, sortie, chemin = self.exporter_csv()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("Table", repr(chemin.instantanes))
        self.assertEqual(self.cellules(chemin)["ABC-4"], [INCONNUE, INCONNUE])

    def test_aucun_appel_a_l_api_assets(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'")))
        self.exporter_csv()
        self.assertEqual(self.faux.appels_get, [])


class RefusDesSources(Base):
    """4.3 : arrêt avec le code 1, sans rien enregistrer, avant tout appel à Jira."""

    def verifier(self, code, sortie, magasin):
        self.assertEqual(code, 1, sortie)
        self.assertEqual((magasin.passages, magasin.instantanes), ([], []))
        self.assertEqual(self.faux.requetes, [])

    def test_nom_du_referentiel_avec_un_identifiant_hors_referentiel(self):
        self.ecrire_sources(catalogue(entree("Equipe A", "'1', '987654'")))
        code, sortie, chemin = self.exporter_csv()
        self.verifier(code, sortie, chemin)
        self.assertIn("équipe du catalogue nommée comme une équipe du référentiel : ", sortie)
        self.assertIn("teams[0].name", sortie)
        for interdit in ("Equipe A", "987654", "ws-secret"):
            self.assertNotIn(interdit, sortie)

    def test_phrase_en_anglais(self):
        self.ecrire_sources(catalogue(entree("Equipe A", "'1', '9'")))
        code, sortie, chemin = self.exporter_csv("--language", "en")
        self.verifier(code, sortie, chemin)
        self.assertIn("catalogue team named like a referential team: ", sortie)

    def test_cle_a_confirmer_refusee_comme_cle_inconnue(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'", "    obsolete_to_confirm: true\n")))
        code, sortie, chemin = self.exporter_csv()
        self.verifier(code, sortie, chemin)
        self.assertIn("teams[0].obsolete_to_confirm", sortie)
        self.assertNotIn("Quimbo", sortie)

    def test_type_hors_des_quatre_noms(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'", "    type: Nope\n")))
        code, sortie, chemin = self.exporter_csv()
        self.verifier(code, sortie, chemin)
        self.assertIn("type d'équipe autre que les quatre sous-types de Team : ", sortie)
        self.assertNotIn("Nope", sortie)

    def test_type_du_referentiel_hors_des_quatre_noms(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'")),
                            REFERENTIEL.replace("jira_team_ids: ['1']", "jira_team_ids: ['1']\n    type: Nope"))
        code, sortie, chemin = self.exporter_csv("--language", "en")
        self.verifier(code, sortie, chemin)
        self.assertIn("team type other than the four Team sub-types: ", sortie)

    def test_diagnose_refuse_aussi(self):
        self.ecrire_sources(catalogue(entree("Equipe A", "'1', '9'")))
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 1, sortie)
        self.assertIn("équipe du catalogue nommée comme une équipe du référentiel", sortie)

    def test_ni_source_ni_identifiant_donne_les_deux_structures_sans_valeur(self):
        self.ecrire("equipes-assets.yaml", "equipes: {'1': Table A}\n")           # même quand l'ancienne table existe
        code, sortie, magasin = self.exporter_csv()
        self.assertEqual(code, 1, sortie)
        self.assertEqual(magasin.passages, [])
        self.assertIn("aucune source d'équipes : compléter jira_team_ids du référentiel et du catalogue", sortie)
        for cle in ("organisation.yaml", "equipes-jira.yaml", "jira_team_ids", "obsolete", "teams", "name", "headcount", "type"):
            self.assertIn(cle, sortie)
        for valeur in ("Table A", "ws-secret", "ABC-"):
            self.assertNotIn(valeur, sortie)
        code, sortie, _ = self.exporter_csv("--language", "en")
        self.assertIn("no team source: fill jira_team_ids in the referential and the catalogue", sortie)


class EquipesHorsOrganisationEtObsoletes(Base):
    """4.5 : lignes du design D11, identifiants et nombres seulement."""

    def test_equipes_hors_organisation(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'"), entree("Libelle-Plinth", "'5'")))
        code, sortie, chemin = self.exporter_csv()
        self.assertEqual(code, 0, sortie)
        self.assertIn("équipes hors organisation : 2 identifiants, 2 tickets", sortie)
        self.assertEqual(self.cellules(chemin)["ABC-4"], [INCONNUE, "Libelle-Plinth"])
        self.assertIn("identifiants d'équipe ni dans le référentiel ni dans le catalogue : 1, sur 1 tickets", sortie)
        self.assertIn("identifiants à ajouter : 6", sortie)
        for interdit in ("Quimbo", "Plinth", "ABC-", "obsolète", "confirmer"):
            self.assertNotIn(interdit, sortie)

    def test_lignes_en_anglais(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'")))
        code, sortie, _ = self.exporter_csv("--language", "en")
        self.assertIn("teams outside the organisation: 1 identifiers, 1 tickets", sortie)

    def test_pas_de_ligne_quand_rien_n_est_hors_organisation(self):
        self.ecrire_sources(catalogue(entree("Libelle-Z", "'1'")), REFERENTIEL.replace("jira_team_ids: ['3']", "jira_team_ids: ['3', '4', '5', '6']"))
        code, sortie, _ = self.exporter_csv()
        self.assertEqual(code, 0, sortie)
        for absent in ("hors organisation", "à ajouter", "obsolètes"):
            self.assertNotIn(absent, sortie)

    def test_equipe_obsolete_son_libelle_est_ecrit_et_elle_n_est_pas_inconnue(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4', '5', '6'", "    obsolete: true\n")))
        code, sortie, chemin = self.exporter_csv("--strict-teams")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.cellules(chemin)["ABC-3"], ["Libelle-Quimbo"])
        self.assertIn("tickets sur des équipes obsolètes : 2", sortie)
        self.assertNotIn("à ajouter", sortie)
        self.assertNotIn("incomplet", sortie)

    def test_obsolete_en_anglais(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4', '5', '6'", "    obsolete: true\n")))
        _, sortie, _ = self.exporter_csv("--language", "en")
        self.assertIn("tickets on obsolete teams: 2", sortie)

    def test_obsolete_dans_le_catalogue_nommee_par_le_referentiel(self):
        self.faux.tickets = {k: v for k, v in self.faux.tickets.items() if k == "ABC-1"}
        self.ecrire_sources(catalogue(entree("Libelle-Plinth", "'1'", "    obsolete: true\n")))
        code, sortie, chemin = self.exporter_csv()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.cellules(chemin)["ABC-1"], ["Equipe A"])
        self.assertIn("tickets sur des équipes obsolètes : 1", sortie)
        self.assertNotIn("hors organisation", sortie)
        self.assertNotIn("à ajouter", sortie)

    def test_identifiant_dans_aucune_source_marqueur_et_liste(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'")))
        code, sortie, chemin = self.exporter_csv()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.cellules(chemin)["ABC-4"], [INCONNUE, INCONNUE])
        self.assertIn("identifiants à ajouter : 5 ; 6", sortie)

    def test_les_equipes_du_referentiel_sans_ticket_ne_comptent_pas_le_catalogue(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'"), entree("Libelle-Sans-Ticket", "'77'")))
        _, avec, _ = self.exporter_csv()
        self.ecrire_sources(catalogue())
        _, sans, _ = self.exporter_csv()
        ligne = lambda s: [l for l in s.splitlines() if "sans ticket" in l]
        self.assertEqual(ligne(avec), ligne(sans))
        self.assertEqual(len(ligne(avec)), 1)

    def test_aucun_libelle_ni_cle_dans_la_console(self):
        self.ecrire_sources(catalogue(entree("ZZLIBELLE-DISTINCT", "'4'", "    obsolete: true\n")))
        _, sortie, _ = self.exporter_csv()
        self.assertNotIn("ZZLIBELLE", sortie)


class OptionStricte(Base):
    """4.6 : le code 3 seulement pour les identifiants dans aucune source."""

    def test_identifiant_dans_aucune_source_sort_avec_3_meme_si_la_table_le_porte(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'")))
        self.ecrire("equipes-assets.yaml", "equipes: {'5': E, '6': F}\n")
        code, sortie, magasin = self.exporter_csv("--strict-teams")
        self.assertEqual(code, 3, sortie)
        self.assertEqual(magasin.passages, [])          # rien d'enregistré sur le code 3 (database-only, D1)
        self.assertTrue(sortie.rstrip().endswith("identifiants d'équipe inconnus : export incomplet"), sortie)

    def test_entree_obsolete_a_la_main_ou_depuis_assets_ne_fait_jamais_sortir_avec_3(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'", "    obsolete: true\n"), entree("Libelle-Plinth", "'5', '6'")))
        code, sortie, _ = self.exporter_csv("--strict-teams")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("incomplet", sortie)

    def test_sans_l_option_le_code_reste_0(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4'")))
        self.assertEqual(self.exporter_csv()[0], 0)


class Diagnose(Base):
    """4.7 : ligne des sources, aucune table lue, codes de sortie."""

    def test_ligne_des_sources_avec_les_deux_fichiers(self):
        self.ecrire_sources(catalogue(entree("Libelle-Quimbo", "'4', '5'")))
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 0, sortie)
        self.assertIn("sources d'équipes : référentiel 3 identifiants, catalogue 2 identifiants", sortie)
        code, sortie = self.lancer("diagnose", "--language", "en")
        self.assertIn("team sources: referential 3 identifiers, catalogue 2 identifiers", sortie)
        for interdit in ("Quimbo", "Equipe", "ws-secret"):
            self.assertNotIn(interdit, sortie)

    def test_catalogue_seul(self):
        self.ecrire("equipes-jira.yaml", catalogue(entree("Libelle-Quimbo", "'4'")))
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 0, sortie)
        self.assertIn("référentiel 0 identifiants, catalogue 1 identifiants", sortie)


if __name__ == "__main__":
    unittest.main()
