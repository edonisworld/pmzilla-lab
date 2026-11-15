"""Champs de livraison dans le client et dans la collecte de history_jira.py (change jira-delivery-fields ; spec jira-flow-history, design D2, D4,
D12), sur le faux serveur et la base fictive.

    bash tests/run_all.sh history_jira

Valeurs distinctives « Zz » : noms de sprint, libellés d'actifs, clés de tickets de version. Aucune ne doit sortir ni être stockée.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_history_jira as base  # noqa: E402

AUJOURD_HUI = dt.date(2026, 10, 13)
UUID = "0123456789abcdef-0123456789abcdef-01"
UUID_B = "fedcba9876543210-fedcba9876543210-01"
REFERENCE = "version_reference_project: VREF\n"
RECHERCHE_VERSIONS = 'project = VREF AND issuetype = "Version"'
CREE = dt.datetime(2026, 1, 2, 9, 0, tzinfo=base.PARIS)


def historique(created: str, *items: dict) -> dict:
    return {"id": created, "created": created, "author": {"displayName": base.AUTEUR}, "items": list(items)}


def element(champ: str, de, vers, de_texte=None, vers_texte=None) -> dict:
    return {"field": "Zz libellé", "fieldId": champ, "from": de, "to": vers, "fromString": de_texte, "toString": vers_texte}


def instant(texte: str) -> dt.datetime:
    return dt.datetime.fromisoformat(texte)


class Livraison(base.Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(base.hj, "aujourd_hui", lambda: AUJOURD_HUI)
        p.start()
        self.addCleanup(p.stop)

    def collecter(self, historiques, courantes=None, *options, type_ticket="Story"):
        self.faux.tickets["ABC-1"] = ("30001", historiques)
        if courantes is not None:
            self.faux.courantes["ABC-1"] = courantes
        self.ecrire_export([("ABC-1", type_ticket, "Equipe Test", True)])
        return self.lancer("collect", "--language", "en", *options)

    def periodes(self, nature):
        return self.magasin.periodes.get(nature, {}).get("ABC-1", {})

    # --- liste groupée du changelog ----------------------------------------------------------------------------------

    def test_la_requete_groupee_ajoute_les_champs_de_livraison_et_aucun_champ_de_defaut(self):
        code, sortie = self.collecter([historique("2026-03-01T09:00:00.000+0200", element("status", None, None))])
        self.assertEqual(code, 0, sortie)
        corps = next(c for api, c in self.faux.corps if api == "/rest/api/3/changelog/bulkfetch")
        # R-20261102-61 : les deux versions d'épic (99004, 99005 de la table factice) rejoignent la liste, aucun champ de défaut.
        self.assertEqual(sorted(corps["fieldIds"]), sorted(["status", "labels", "fixVersions", "customfield_99001", "customfield_99002",
                                                            "customfield_99003", "customfield_99004", "customfield_99005"]))
        for defaut in ("customfield_99006", "customfield_99007", "customfield_99019", "customfield_99020", "customfield_99021"):
            self.assertNotIn(defaut, corps["fieldIds"])

    # --- sprint ----------------------------------------------------------------------------------------------------

    def test_noms_de_sprint_ecartes_identifiants_gardes(self):
        courantes = {"champs": {"customfield_99001": [{"id": 11, "name": "ZzSprintUn"}, {"id": 12, "name": "ZzSprintDeux"}]}}
        code, sortie = self.collecter([historique("2026-03-01T09:00:00.000+0200", element(
            "customfield_99001", "11", "11, 12", "ZzSprintUn", "ZzSprintUn, ZzSprintDeux"))], courantes)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.periodes("sprints"), {("11", CREE): None, ("12", instant("2026-03-01T09:00:00+02:00")): None})
        self.assertNotIn("ZzSprint", repr(self.magasin.periodes))
        self.assertNotIn("ZzSprint", sortie)
        self.assertIn("delivery field events kept: 1", sortie)

    def test_sprint_retire_ferme_la_periode(self):
        courantes = {"champs": {"customfield_99001": []}}
        self.collecter([historique("2026-03-01T09:00:00.000+0200", element("customfield_99001", "5", None)),
                        historique("2026-02-01T09:00:00.000+0200", element("customfield_99001", None, "5"))], courantes)
        self.assertEqual(self.periodes("sprints"), {("5", instant("2026-02-01T09:00:00+02:00")): instant("2026-03-01T09:00:00+02:00")})

    # --- versions visée et livrée ---------------------------------------------------------------------------------

    def test_liste_entre_crochets_lue_un_evenement_et_aucun_libelle(self):
        courantes = {"champs": {"customfield_99002": [{"objectId": "101"}, {"objectId": "102"}]}}
        code, sortie = self.collecter([historique("2026-03-01T09:00:00.000+0200", element(
            "customfield_99002", f"[{UUID}:101]", f"[{UUID}:101, {UUID_B}:102]", "ZzVersionA", "ZzVersionA, ZzVersionB"))], courantes)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.periodes("actifs"), {("target:101", CREE): None, ("target:102", instant("2026-03-01T09:00:00+02:00")): None})
        self.assertNotIn("ZzVersion", repr(self.magasin.periodes) + sortie)
        self.assertIn("delivery field events kept: 1", sortie)
        self.assertIn("unreadable changelog elements (target, resolution and epic versions): 0", sortie)

    def test_historique_de_version_d_un_defaut_collecte(self):
        self.ecrire_export([("ABC-1", "Bug", "Equipe Test", True)])
        self.faux.tickets["ABC-1"] = ("30001", [historique("2026-03-01T09:00:00.000+0200", element(
            "customfield_99003", f"[{UUID}:101]", f"[{UUID_B}:102]"), element("customfield_99006", f"[{UUID}:1]", f"[{UUID}:2]"),
            element("customfield_99019", "Test", "Production"))])
        self.faux.courantes["ABC-1"] = {"champs": {"customfield_99003": [{"objectId": "102"}]}}
        code, sortie = self.lancer("collect", "--language", "en", "--refresh")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.periodes("actifs"), {("resolution:101", CREE): instant("2026-03-01T09:00:00+02:00"),
                                                   ("resolution:102", instant("2026-03-01T09:00:00+02:00")): None})
        self.assertNotIn("detected", repr(self.magasin.periodes))
        self.assertIn("delivery field events kept: 2", sortie)

    def test_element_hors_motif_compte_et_ignore_le_reste_est_garde(self):
        code, sortie = self.collecter([historique("2026-03-01T09:00:00.000+0200", element(
            "customfield_99003", f"[{UUID}:101]", f"[{UUID}:101, {UUID_B}:102, ZzLibelleSeul]", "ZzA", "ZzA, ZzB, ZzLibelleSeul"))],
            {"champs": {"customfield_99003": [{"objectId": "101"}, {"objectId": "102"}]}})
        self.assertEqual(code, 0, sortie)
        self.assertIn("unreadable changelog elements (target, resolution and epic versions): 1", sortie)
        self.assertIn("delivery field events kept: 1", sortie)
        self.assertNotIn("ZzLibelleSeul", sortie + repr(self.magasin.periodes))

    def test_champ_d_epic_historise_evenement_garde_et_plus_de_ligne_non_collecte(self):
        # Remplace test_champ_d_epic_non_historise_ligne_et_aucun_evenement : R-20261102-61 (1) (a), les versions d'épic sont historisées.
        courantes = {"champs": {"customfield_99004": [{"objectId": "301"}, {"objectId": "302"}]}}
        code, sortie = self.collecter([historique("2026-03-01T09:00:00.000+0200", element(
            "customfield_99004", f"[{UUID}:301]", f"[{UUID}:301, {UUID_B}:302]", "ZzVersionEpic", "ZzVersionEpic, ZzAutre"))], courantes)
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("history not collected", sortie)
        self.assertIn("delivery field events kept: 1", sortie)
        self.assertEqual(self.periodes("actifs"), {("epic_a:301", CREE): None, ("epic_a:302", instant("2026-03-01T09:00:00+02:00")): None})
        self.assertNotIn("ZzVersionEpic", repr(self.magasin.periodes) + sortie)
        corps = next(c for api, c in self.faux.corps if api == "/rest/api/3/changelog/bulkfetch")
        self.assertIn("customfield_99004", corps["fieldIds"])
        self.assertIn("customfield_99005", corps["fieldIds"])

    def test_historique_de_version_d_epic_retrait_et_ajout_scenario_de_la_spec(self):
        # Scénario « Epic version history collected » (spec jira-flow-history) : [U:201] -> [U:202] sur le premier champ de version d'épic.
        courantes = {"champs": {"customfield_99004": [{"objectId": "202"}]}}
        code, sortie = self.collecter([historique("2026-03-01T09:00:00.000+0200", element(
            "customfield_99004", f"[{UUID}:201]", f"[{UUID}:202]", "ZzEpicAvant", "ZzEpicApres"))], courantes, type_ticket="Epic")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.periodes("actifs"), {("epic_a:201", CREE): instant("2026-03-01T09:00:00+02:00"),
                                                   ("epic_a:202", instant("2026-03-01T09:00:00+02:00")): None})
        self.assertIn("delivery field events kept: 2", sortie)
        self.assertNotIn("ZzEpic", repr(self.magasin.periodes) + sortie)
        self.assertNotIn("history not collected", sortie)

    def test_element_hors_motif_d_epic_compte_et_le_reste_est_garde_sous_epic_b(self):
        # Scénario « Epic version element out of the pattern » (spec jira-flow-history) : second champ de version d'épic.
        code, sortie = self.collecter([historique("2026-03-01T09:00:00.000+0200", element(
            "customfield_99005", f"[{UUID}:401]", f"[{UUID}:401, {UUID_B}:402, ZzLibelleSeul]", "ZzA", "ZzA, ZzB, ZzLibelleSeul"))],
            {"champs": {"customfield_99005": [{"objectId": "401"}, {"objectId": "402"}]}}, type_ticket="Epic")
        self.assertEqual(code, 0, sortie)
        self.assertIn("unreadable changelog elements (target, resolution and epic versions): 1", sortie)
        self.assertEqual(self.periodes("actifs"), {("epic_b:401", CREE): None, ("epic_b:402", instant("2026-03-01T09:00:00+02:00")): None})
        self.assertNotIn("ZzLibelleSeul", sortie + repr(self.magasin.periodes))

    # --- table absente de flux.yaml (R-20261114-108, même logique que A-92) -----------------------------------------

    def test_table_absente_aucun_champ_collecte_message_explicite_code_zero(self):
        """Sans `delivery_fields`, le code ne porte aucun identifiant réel : la liste groupée ne demande aucun champ de livraison, aucune
        période de sprint ni d'actif n'est écrite ; la ligne le dit ; le code de sortie reste 0."""
        self.ecrire_reglages("scopes", livraison=False)
        courantes = {"champs": {"customfield_99001": [{"id": 11}]}}
        code, sortie = self.collecter([historique("2026-03-01T09:00:00.000+0200", element("customfield_99001", "11", "11, 12"))], courantes)
        self.assertEqual(code, 0, sortie)
        self.assertIn("delivery fields not configured (delivery_fields key missing from flux.yaml): "
                      "sprints and asset versions not collected, collection continued", sortie)
        corps = next(c for api, c in self.faux.corps if api == "/rest/api/3/changelog/bulkfetch")
        self.assertEqual(sorted(corps["fieldIds"]), ["fixVersions", "labels", "status"])
        self.assertEqual(self.periodes("sprints"), {})
        self.assertEqual(self.periodes("actifs"), {})

    def test_table_presente_aucun_message_d_absence(self):
        code, sortie = self.collecter([historique("2026-03-01T09:00:00.000+0200", element("status", None, None))])
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("delivery fields not configured", sortie)

    def test_evenements_comptes_sans_identifiant_dans_la_sortie(self):
        code, sortie = self.collecter([historique("2026-03-01T09:00:00.000+0200", element("customfield_99001", None, "8"),
                                                  element("customfield_99001", "8", "8, 9"),
                                                  element("customfield_99002", None, f"[{UUID}:301]"))])
        self.assertEqual(code, 0, sortie)
        self.assertIn("delivery field events kept: 3", sortie)
        self.assertNotIn("301", sortie)

    def test_refresh_rejoue_les_evenements_d_un_ticket_deja_collecte(self):
        self.collecter([historique("2026-03-01T09:00:00.000+0200", element("customfield_99001", None, "8"))],
                       {"champs": {"customfield_99001": [{"id": 8}]}})
        self.assertEqual(self.periodes("sprints"), {("8", instant("2026-03-01T09:00:00+02:00")): None})
        self.faux.tickets["ABC-1"] = ("30001", [historique("2026-03-01T09:00:00.000+0200", element("customfield_99001", None, "8")),
                                                historique("2026-04-01T09:00:00.000+0200", element("customfield_99001", "8", "8, 9"))])
        self.faux.courantes["ABC-1"] = {"champs": {"customfield_99001": [{"id": 8}, {"id": 9}]}}
        code, sortie = self.lancer("collect", "--language", "en", "--refresh")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(set(self.periodes("sprints")), {("8", instant("2026-03-01T09:00:00+02:00")), ("9", instant("2026-04-01T09:00:00+02:00"))})

    def test_valeur_courante_absente_de_la_reponse_ne_touche_pas_aux_periodes(self):
        self.collecter([historique("2026-03-01T09:00:00.000+0200", element("customfield_99001", None, "8"))],
                       {"champs": {"customfield_99001": [{"id": 8}]}})
        self.faux.courantes["ABC-1"] = {}                 # Jira ne renvoie plus le champ : inconnu, non vide
        self.lancer("collect", "--refresh")
        self.assertEqual(set(self.periodes("sprints")), {("8", instant("2026-03-01T09:00:00+02:00"))})


class GardeDeLaRecherche(base.Base):
    """Le client admet la recherche de forme fixe des versions, comparée littéralement, et elle seule (design D4)."""

    def setUp(self):
        super().setUp()
        base.hj.set_language("fr")          # la langue est globale : un test précédent a pu la changer
        self.ecrire_reglages("scopes", extra=REFERENCE)

    def client(self, avec=True):
        return base.hj.construire_client(base.hj.reglages(), avec_reference=avec)

    def recherche(self, client, jql):
        return client.json("POST", "/rest/api/3/search/jql", json={"jql": jql, "fields": ["issuetype"]})

    def refuse(self, client, jql):
        with self.assertRaises(base.hj.RequeteHorsPerimetre) as contexte:
            self.recherche(client, jql)
        self.assertEqual(str(contexte.exception), "requête Jira refusée : hors des projets déclarés du périmètre")

    def test_forme_fixe_admise_les_autres_refusees_sans_rien_envoyer(self):
        client = self.client()
        self.recherche(client, RECHERCHE_VERSIONS)
        envoyes = len(self.faux.brut)
        self.assertEqual(envoyes, 1)
        for jql in ("project = VREF", 'project = VREF AND issuetype = "Version" OR project = OTHER', RECHERCHE_VERSIONS + " ORDER BY created",
                    'project = VREF AND issuetype = "Task"', 'project in (VREF, ABC)', 'project = "VREF" AND issuetype = "Version"',
                    'project = vref AND issuetype = "Version"'):
            with self.subTest(jql=jql):
                self.refuse(client, jql)
        self.assertEqual(len(self.faux.brut), envoyes)

    def test_sans_reglage_la_forme_fixe_est_refusee(self):
        self.ecrire_reglages("scopes")
        for avec in (True, False):
            client = self.client(avec)
            self.refuse(client, RECHERCHE_VERSIONS)
        self.assertEqual(self.faux.brut, [])

    def test_un_client_sans_reference_n_admet_pas_la_forme_fixe_meme_avec_le_reglage(self):
        self.refuse(self.client(avec=False), RECHERCHE_VERSIONS)
        self.assertEqual(self.faux.brut, [])

    def test_changelog_et_groupe_d_un_ticket_de_la_reference_refuses(self):
        client = self.client()
        with self.assertRaises(base.hj.RequeteHorsPerimetre):
            client.json("GET", "/rest/api/3/issue/VREF-1/changelog", params={"startAt": 0})
        with self.assertRaises(base.hj.RequeteHorsPerimetre):
            client.json("POST", "/rest/api/3/changelog/bulkfetch", json={"issueIdsOrKeys": ["VREF-1"], "fieldIds": ["status"]})
        self.assertEqual(self.faux.brut, [])

    def test_reponse_de_la_recherche_de_versions_filtree_par_type(self):
        self.faux.recherche_imposee = {"issues": [
            {"id": "1", "key": "VREF-1", "fields": {"issuetype": {"name": "Version"}}},
            {"id": "2", "key": "VREF-2", "fields": {"issuetype": {"name": "Task"}}},
            {"id": "3", "key": "OTHER-1", "fields": {"issuetype": {"name": "Version"}}},
            {"id": "4", "key": "ABC-1", "fields": {"issuetype": {"name": "Story"}}}]}
        client = self.client()
        reponse = self.recherche(client, RECHERCHE_VERSIONS)
        self.assertEqual([i["key"] for i in reponse["issues"]], ["VREF-1", "ABC-1"])          # le ticket d'un projet déclaré reste (filtre D9 inchangé)
        self.assertEqual((client.autres_types_reference, client.tickets_hors_perimetre), (1, 1))          # le Task de VREF, puis OTHER-1

    def test_ticket_de_la_reference_dans_une_recherche_ordinaire_est_retire(self):
        self.faux.recherche_imposee = {"issues": [
            {"id": "1", "key": "ABC-1", "fields": {}}, {"id": "2", "key": "VREF-1", "fields": {"issuetype": {"name": "Version"}}}]}
        client = self.client()
        reponse = self.recherche(client, "project = ABC")
        self.assertEqual([i["key"] for i in reponse["issues"]], ["ABC-1"])
        self.assertEqual((client.tickets_hors_perimetre, client.autres_types_reference), (1, 0))

    def test_reglage_illisible_ou_en_recouvrement_code_6_avant_le_trousseau(self):
        jeton = mock.Mock(return_value=base.JETON)
        for ecrit in ("version_reference_project: [VREF, OTHERP]\n", "version_reference_project: VREF OTHERP\n",
                      "version_reference_project: ABC\n"):
            self.ecrire_reglages("scopes", extra=ecrit)
            with self.subTest(ecrit=ecrit), mock.patch.object(base.hj, "lire_jeton", jeton):
                with self.assertRaises(base.hj.RequeteHorsPerimetre) as contexte:
                    self.client()
                self.assertEqual(str(contexte.exception), "requête Jira refusée : réglage illisible (version_reference_project)")
        jeton.assert_not_called()
        self.assertEqual(self.faux.brut, [])

    def test_cle_refusee_comme_reference_refusee_par_la_regle_des_projets_refuses(self):
        self.ecrire_reglages("scopes", extra="version_reference_project: SUPX\n")
        client = self.client()
        self.refuse(client, 'project = SUPX AND issuetype = "Version"')
        self.assertEqual(self.faux.brut, [])


if __name__ == "__main__":
    unittest.main()
