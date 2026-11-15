"""Champs de livraison et tickets de version dans l'export (change jira-delivery-fields ; spec jira-flow-delivery-fields et jira-flow-export,
design D1, D3, D4, D5, D12).

    bash tests/run_all.sh export_jira_api

Faux serveur et faux magasin en mémoire de test_export_jira_api.py, plus une recherche de versions de forme fixe sur un projet de référence
fictif (VREF), hors du périmètre déclaré. Valeurs distinctives « Zz » : aucune ne doit sortir, ni dans la sortie ni dans l'instantané.
"""
import io
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from test_export_jira_api import Base, champs, ex, hj  # noqa: E402

import flow_delivery  # noqa: E402
import flow_raw  # noqa: E402

UUID = "0123456789abcdef-0123456789abcdef-01"
SECRETS = ("ZzSprintNom", "ZzButDuSprint", "ZzClientNomme", "ZzLibelleActif", "ZzNomCourtVersion", "ZzResumeVersion", "ZzOptionValeur",
           "ZzNomSensible", "ZzDetectePar", "ZzBaseInstallee", "VREF-1", "VREF-2")
NON_STOCKES = ("ZzSprintNom", "ZzButDuSprint", "ZzClientNomme", "ZzLibelleActif", "ZzNomCourtVersion", "ZzResumeVersion", "ZzNomSensible",
               "ZzIdLong", "VREF-1", "VREF-2")          # ce que la forme stockée d'une story ne tient jamais
VERSION_NORMALE = {"key": "VREF-1", "fields": {
    "issuetype": {"name": "Version"}, "status": {"name": "Released", "statusCategory": {"name": "Done"}},
    "customfield_99022": [{"objectId": "101", "id": "ZzIdLong", "workspaceId": "ZzW", "label": "ZzLibelleActif"}],
    "customfield_99023": "2026-03-10", "customfield_99024": "2026-01-05", "customfield_99025": "ZzNomCourtVersion",
    "summary": "ZzResumeVersion"}}


def version(cle, objets, type_="Version", **plus):
    fields = {"issuetype": {"name": type_}, "status": {"name": "Open", "statusCategory": {"name": "To Do"}},
              "customfield_99022": [{"objectId": o} for o in objets], "customfield_99023": None, "customfield_99024": None,
              "customfield_99025": "ZzNomCourtVersion", "summary": "ZzResumeVersion"}
    fields.update(plus)
    return {"key": cle, "fields": fields}


class Livraison(Base):
    def setUp(self):
        super().setUp()
        self.versions = [VERSION_NORMALE]
        self.recherches_versions = []
        base_handler, faux, test = self.serveur.RequestHandlerClass, self.faux, self

        class Handler(base_handler):
            def do_POST(self):
                taille = int(self.headers.get("Content-Length") or 0)
                brut = self.rfile.read(taille)
                corps = json.loads(brut or b"{}")
                if str(corps.get("jql", "")).startswith("project = VREF"):
                    self.noter_brut("POST")
                    if self.hors():
                        return self.repondre(404)
                    test.recherches_versions.append(corps)
                    return self.repondre(200, {"issues": test.versions})
                self.rfile = io.BytesIO(brut)
                return super().do_POST()

        self.serveur2 = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.serveur2.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        self.addCleanup(self.serveur2.server_close)
        self.addCleanup(self.serveur2.shutdown)
        self.url = f"http://127.0.0.1:{self.serveur2.server_address[1]}"
        patch = mock.patch.object(hj, "API_ATLASSIAN", self.url)
        patch.start()
        self.addCleanup(patch.stop)
        noms = self.ws / "noms-sensibles.txt"
        noms.write_text("ZzNomSensible\n", encoding="utf-8")
        patch_env = mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(noms)})
        patch_env.start()
        self.addCleanup(patch_env.stop)
        self.reglages_livraison()
        t = self.faux.tickets
        t["ABC-1"].update({
            "customfield_99001": [{"id": 31, "name": "ZzSprintNom", "goal": "ZzButDuSprint", "boardId": 4, "state": "closed",
                                   "startDate": "2026-09-01T08:00:00.000Z", "endDate": "2026-09-14T17:00:00.000Z"}],
            "customfield_99002": [{"objectId": "101", "id": "ZzIdLong", "workspaceId": "ZzW", "label": "ZzLibelleActif"}],
            "customfield_99003": [{"objectId": "102"}],
            "customfield_99009": [{"id": "7", "value": "ZzOptionValeur"}, {"id": "8", "value": "Voie ZzNomSensible"}],
            "customfield_99016": [{"value": "ZzClientNomme"}], "customfield_99015": 3,
            "customfield_99006": [{"objectId": "201"}], "customfield_99019": {"id": "11", "value": "Production"},
            "customfield_99020": {"id": "12", "value": "ZzDetectePar"}, "customfield_99021": {"id": "13", "value": "ZzBaseInstallee"}})
        t["ABC-4"] = champs("Bug", "Open", "To Do", "2026-09-02T09:00:00.000+0200", equipes=["Equipe A"])
        t["ABC-4"].update({"customfield_99006": [{"objectId": "201"}], "customfield_99007": [{"objectId": "202"}],
                           "customfield_99019": {"id": "11", "value": "Production"},
                           "customfield_99020": {"id": "12", "value": "ZzDetectePar"}, "customfield_99021": {"id": "13", "value": "ZzBaseInstallee"}})

    def reglages_livraison(self, reference: str | None = "VREF", table: str | None = None, livraison: bool = True):
        """`table` : texte du bloc `delivery_fields` à la place de la table factice ; `livraison=False` : aucune table."""
        extra = f"jql_export: project = ABC\nexport_team_field: customfield_10001\ndefect_types: [Bug]\n"
        extra += f"version_reference_project: {reference}\n" if reference is not None else ""
        extra += table or ""
        self.ecrire_reglages(extra, livraison=livraison and table is None)

    def en(self, *options):
        return self.lancer("export", "--language", "en", *options)

    # --- liste demandée, forme stockée ------------------------------------------------------------------------------

    def test_liste_fermee_des_champs_de_livraison_demandee(self):
        self.exporter()
        premiere = self.faux.requetes[0]["fields"]
        self.assertLessEqual(set(flow_delivery.champs_demandes()), set(premiere))
        self.assertFalse({"summary", "description", "assignee", "reporter", "creator", "comment", "labels", "timespent"} & set(premiere))

    def test_recherche_de_versions_de_forme_fixe_et_champs_reduits(self):
        self.exporter()
        self.assertEqual(len(self.recherches_versions), 1)
        corps = self.recherches_versions[0]
        self.assertEqual(corps["jql"], 'project = VREF AND issuetype = "Version"')
        self.assertEqual(set(corps["fields"]), set(flow_delivery.champs_versions()))
        self.assertNotIn("summary", corps["fields"])

    def test_forme_stockee_d_une_story(self):
        instantane = self.exporter()["ABC-1"]
        livraison = instantane["delivery"]
        self.assertEqual(livraison["sprints"], [{"id": "31", "state": "closed", "start": "2026-09-01T08:00:00.000Z",
                                                 "end": "2026-09-14T17:00:00.000Z", "complete": None}])
        self.assertEqual(livraison["assets"], {"target": ["101"], "resolution": ["102"]})        # détectée : défauts seulement
        self.assertEqual(livraison["flags"]["customer_commitment"], True)
        self.assertEqual(livraison["rank"], "3")
        self.assertNotIn("defect", livraison)
        for secret in NON_STOCKES:
            self.assertNotIn(secret, json.dumps(livraison, default=str))

    def test_champs_de_defaut_gardes_pour_un_defaut_seulement(self):
        instantanes = self.exporter()
        defaut = instantanes["ABC-4"]["delivery"]
        self.assertEqual(defaut["assets"], {"detected": ["201"], "affected": ["202"]})
        # R-20261102-51 : phase de détection en code fermé ; « détecté par » et base installée en identifiant d'option seul
        self.assertEqual(defaut["defect"]["detection_phase"], {"id": "11", "code": "production"})
        self.assertEqual(defaut["defect"]["installed_base"], {"id": "13"})
        self.assertNotIn("detected", instantanes["ABC-1"]["delivery"]["assets"])
        self.assertEqual(defaut["defect"]["detected_by"], {"id": "12"})
        for valeur in ("ZzDetectePar", "ZzBaseInstallee"):
            self.assertNotIn(valeur, json.dumps(defaut, default=str))

    def test_options_de_flux_en_identifiants_seuls_sans_remplacement(self):
        # Remplace test_valeur_d_option_a_nom_sensible_filtree_et_comptee : mécanisme changé par R-20261102-51 (plus de valeur d'option stockée).
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        # R-20261102-51 et R-20261102-55 : la ligne ne compte plus que les noms courts de version ; aucune valeur d'option, donc rien n'est compté
        self.assertNotIn("version short names replaced by the sensitive-name marker", sortie)
        options =self.magasin.dernier("ABC-1")["delivery"]["options"]["workflow_option"]
        self.assertEqual(options, ["7", "8"])
        self.assertNotIn("ZzNomSensible", sortie)
        self.assertNotIn("ZzOptionValeur", json.dumps(self.magasin.dernier("ABC-1")["delivery"], default=str))

    def test_engagements_presence_seulement_aucune_valeur_stockee_ni_affichee(self):
        # R-20261102-50 : toute option vaut oui (« No » comprise), vide vaut non ; aucune valeur d'option n'est lue.
        t = self.faux.tickets
        t["ABC-1"]["customfield_99016"] = {"id": "1", "value": "ZzClient1"}
        t["ABC-1"]["customfield_99017"] = {"id": "2", "value": "No"}
        t["ABC-1"]["customfield_99018"] = {"id": "3", "value": "Yes"}
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        livraison = self.magasin.dernier("ABC-1")["delivery"]
        self.assertEqual(livraison["flags"], {"customer_commitment": True, "source_commitment": True, "strategic_objective": True})
        for valeur in ("ZzClient1", "No", "Yes"):
            self.assertNotIn(valeur, json.dumps(livraison, default=str))
        self.assertNotIn("ZzClient1", sortie)
        t["ABC-1"]["customfield_99016"] = None
        t["ABC-1"]["customfield_99017"] = None
        t["ABC-1"]["customfield_99018"] = None
        self.en()
        self.assertNotIn("flags", self.magasin.dernier("ABC-1")["delivery"])          # tous vides : non

    def test_aucune_valeur_distinctive_dans_la_sortie(self):
        for langue in ("fr", "en"):
            code, sortie = self.lancer("export", "--language", langue)
            self.assertEqual(code, 0, sortie)
            for secret in SECRETS:
                self.assertNotIn(secret, sortie)

    def test_aucune_valeur_distinctive_dans_la_sortie_d_erreur(self):
        self.magasin.echec_ecriture = RuntimeError("ZzOptionValeur ZzNomSensible VREF-1")
        code, sortie = self.en()
        self.assertEqual(code, 1)
        for secret in SECRETS:
            self.assertNotIn(secret, sortie)

    def test_ticket_sans_champ_de_livraison_garde_son_empreinte(self):
        instantane = self.exporter()["ABC-2"]
        self.assertIsNone(instantane["delivery"])
        self.assertEqual(instantane["content_hash"], flow_raw.empreinte({k: v for k, v in instantane.items() if k != "delivery"}))

    def test_sprint_ajoute_ecrit_un_seul_instantane(self):
        self.exporter()
        avant = len(self.magasin.instantanes)
        self.faux.tickets["ABC-2"]["customfield_99001"] = [{"id": 77, "state": "active"}]
        self.exporter()
        self.assertEqual(len(self.magasin.instantanes), avant + 1)
        self.assertEqual(self.magasin.dernier("ABC-2")["issue_key"], "ABC-2")

    def test_liste_des_noms_sensibles_indisponible_arrete_sans_ecrire(self):
        os.environ["PMZILLA_LAB_SENSITIVE_NAMES"] = str(self.ws / "absente.txt")
        code, sortie = self.en()
        self.assertEqual(code, 1)
        self.assertIn("sensitive-names list unavailable: version short names cannot be filtered, export stopped.", sortie)
        code, sortie_fr = self.lancer("export", "--language", "fr")
        self.assertEqual(code, 1)
        self.assertIn("liste des noms sensibles indisponible : les noms courts de version ne peuvent pas être filtrés, export arrêté.", sortie_fr)
        self.assertEqual(self.magasin.passages, [])
        self.assertNotIn("absente", sortie)
        self.assertNotIn("absente", sortie_fr)
        self.assertEqual(self.faux.brut, [])          # R-20261102-41 (Q326) : arrêt AVANT le premier appel à Jira

    def test_valeur_unique_et_option_de_defaut_en_identifiant_seul(self):
        # Remplace test_valeur_unique_et_option_de_defaut_filtrees : mécanisme changé par R-20261102-51 (identifiant d'option seul, aucun filtre).
        self.faux.tickets["ABC-1"]["customfield_99010"] = {"id": "2", "value": "Cible ZzNomSensible"}
        self.faux.tickets["ABC-4"]["customfield_99020"] = {"id": "12", "value": "ZzNomSensible equipe"}
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        # R-20261102-51 et R-20261102-55 : ligne de sortie limitée aux noms courts de version ; aucune valeur d'option comptée
        self.assertNotIn("version short names replaced by the sensitive-name marker", sortie)
        self.assertEqual(self.magasin.dernier("ABC-1")["delivery"]["single"]["release_target"], "2")
        self.assertEqual(self.magasin.dernier("ABC-4")["delivery"]["defect"]["detected_by"], {"id": "12"})
        self.assertNotIn("ZzNomSensible", sortie)

    def test_phase_de_detection_libre_stockee_en_other(self):
        self.faux.tickets["ABC-4"]["customfield_99019"] = {"id": "19", "value": "ZzPhaseLibre"}
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        defaut = self.magasin.dernier("ABC-4")["delivery"]["defect"]
        self.assertEqual(defaut["detection_phase"], {"id": "19", "code": "other"})
        self.assertNotIn("ZzPhaseLibre", json.dumps(defaut, default=str) + sortie)

    def test_nom_court_de_version_sensible_filtre_et_compte(self):
        self.versions = [version("VREF-1", ["101"], customfield_99025="Produit ZzNomSensible 3")]
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.magasin.versions_recues[-1]["101"]["short_name"], flow_delivery.MARQUEUR)
        self.assertIn("version short names replaced by the sensitive-name marker: 1", sortie)          # R-20261102-51 et R-20261102-55 : seul le nom court est compté (exactement 1)
        self.assertNotIn("ZzNomSensible", sortie)

    # --- tickets de version ------------------------------------------------------------------------------------------

    def test_version_lue_et_jointe_par_objet(self):
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        self.assertIn("version tickets read: 1", sortie)
        contenu = self.magasin.versions_recues[-1]["101"]
        self.assertEqual(contenu, {"short_name": "ZzNomCourtVersion", "status": "Released", "status_category": "Done",
                                   "started": "2026-01-05", "released": "2026-03-10"})
        self.assertEqual(len(self.magasin.instantanes_de_version), 1)

    def test_les_tickets_de_version_n_entrent_pas_dans_les_instantanes(self):
        instantanes = self.exporter()
        self.assertFalse([cle for cle in instantanes if cle.startswith("VREF")])
        self.assertEqual(self.magasin.cles_vues(), set(instantanes))

    def test_autre_type_ecarte_et_compte_sans_cle(self):
        self.versions = [VERSION_NORMALE, version("VREF-2", ["103"], type_="Task")]
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        self.assertIn("tickets of another type set aside from the version reference project: 1", sortie)
        self.assertNotIn("103", self.magasin.versions_recues[-1])
        self.assertNotIn("VREF-2", sortie)

    def test_ticket_sans_actif_et_actifs_en_conflit(self):
        self.versions = [version("VREF-1", []), version("VREF-2", ["104"]), version("VREF-3", ["104"])]
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        self.assertIn("version tickets without asset: 1", sortie)
        self.assertIn("assets with conflicting version tickets: 1", sortie)
        self.assertEqual(self.magasin.versions_recues[-1]["104"], flow_delivery.CONTENU_VIDE)

    def test_ticket_de_version_a_plusieurs_actifs_a_sa_ligne(self):
        self.versions = [version("VREF-1", ["1", "2"])]
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        self.assertIn("version tickets with several assets: 1", sortie)
        self.assertNotIn("without asset", sortie)
        code, sortie = self.lancer("export")
        self.assertIn("tickets de version à plusieurs actifs : 1", sortie)

    def test_version_inchangee_n_ajoute_pas_d_instantane_de_version(self):
        self.exporter()
        self.exporter()
        self.assertEqual(len(self.magasin.instantanes_de_version), 1)
        self.versions = [version("VREF-1", ["101"], customfield_99023="2026-03-11")]
        self.exporter()
        self.assertEqual(len(self.magasin.instantanes_de_version), 2)

    def test_reglage_absent_aucune_recherche_ligne_fixe_code_zero(self):
        self.reglages_livraison(reference=None)
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.recherches_versions, [])
        self.assertIn("version reference project not configured: version attributes skipped", sortie)
        self.assertIsNone(self.magasin.versions_recues[-1])
        code, sortie = self.lancer("export")
        self.assertIn("projet de référence des versions non configuré : attributs des versions ignorés", sortie)

    # --- table absente de flux.yaml (R-20261114-108, même logique que A-92) -----------------------------------------

    def test_table_absente_rien_n_est_lu_message_explicite_code_zero(self):
        """Sans `delivery_fields`, le code ne porte aucun identifiant réel : aucun champ de livraison demandé, aucune recherche de versions,
        aucune partie `delivery` stockée ; la ligne le dit dans les deux langues ; le code de sortie reste 0."""
        self.reglages_livraison(livraison=False)
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        self.assertIn("delivery fields not configured (delivery_fields key missing from flux.yaml): "
                      "delivery fields and version attributes not read, delivery data already stored kept, export continued", sortie)
        demandes = set(self.faux.requetes[0]["fields"])
        self.assertEqual(sorted(demandes), sorted(ex.CHAMPS_DE_BASE + ["customfield_10001"]))          # champs de base et champ d'équipe, rien d'autre
        self.assertEqual(self.recherches_versions, [])
        self.assertNotIn("version tickets read", sortie)
        self.assertIsNone(self.magasin.dernier("ABC-1")["delivery"])
        self.assertIsNone(self.magasin.versions_recues[-1])
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertIn("champs de livraison non configurés (clé delivery_fields absente de flux.yaml)", sortie)

    def test_table_absente_conserve_les_donnees_de_livraison_deja_stockees(self):
        """C2 : sans `delivery_fields`, l'export ne change rien aux données de livraison déjà stockées : la partie `delivery` du dernier
        instantané est reprise, l'empreinte reste celle du dernier export avec table, aucun instantané parasite n'est écrit (donc rien
        à réconcilier : les lignes courantes de livraison ne sont pas effacées). Un ticket modifié par ailleurs garde sa livraison."""
        self.exporter()
        avant = {i["issue_key"]: i for i in self.magasin.instantanes}
        self.assertTrue(avant["ABC-1"]["delivery"])
        nombre = len(self.magasin.instantanes)
        self.reglages_livraison(livraison=False)
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.magasin.instantanes), nombre, "aucun instantané écrit pour cette seule raison")
        self.faux.tickets["ABC-1"]["updated"] = "2026-10-03T10:00:00.000+0200"
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        dernier = self.magasin.dernier("ABC-1")
        self.assertEqual(dernier["delivery"], avant["ABC-1"]["delivery"])
        self.assertEqual(dernier["content_hash"], flow_raw.empreinte(dernier))

    def test_table_presente_aucun_message_d_absence(self):
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("delivery fields not configured", sortie)
        self.assertNotIn("version ticket fields not configured", sortie)

    def test_table_sans_champs_de_version_aucune_recherche_et_ligne_dediee(self):
        self.reglages_livraison(table="delivery_fields:\n  sprint: customfield_99001\n")
        code, sortie = self.en()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.recherches_versions, [])
        self.assertIn("version ticket fields not configured (delivery_fields.version_tickets.asset missing from flux.yaml): "
                      "version attributes skipped", sortie)
        self.assertNotIn("delivery fields not configured", sortie)
        self.assertEqual(self.magasin.dernier("ABC-1")["delivery"]["sprints"][0]["id"], "31")

    def test_table_mal_formee_arret_avant_tout_appel_a_jira(self):
        self.reglages_livraison(table="delivery_fields:\n  sprint: champ-zz-777\n")
        code, sortie = self.en()
        self.assertEqual(code, 1, sortie)
        self.assertIn("delivery_fields.sprint", sortie)
        self.assertNotIn("champ-zz-777", sortie)
        self.assertEqual(self.faux.brut, [])

    def test_reglage_illisible_code_6_phrase_et_journal_brut_vide(self):
        for valeur in ("[VREF, OTHERP]", "VREF OTHERP", "vref", "ABC"):          # deux clés, espace, minuscules, clé aussi déclarée
            with self.subTest(valeur=valeur):
                self.reglages_livraison(reference=valeur)
                self.faux.brut.clear()
                code, sortie = self.en()
                self.assertEqual(code, 6, sortie)
                self.assertIn("Jira request refused: setting unreadable (version_reference_project)", sortie)
                self.assertNotIn("OTHERP", sortie)
                self.assertEqual(self.faux.brut, [])
        self.reglages_livraison(reference="[VREF, OTHERP]")
        code, sortie = self.lancer("export", "--language", "fr")
        self.assertIn("requête Jira refusée : réglage illisible (version_reference_project)", sortie)


if __name__ == "__main__":
    unittest.main()
