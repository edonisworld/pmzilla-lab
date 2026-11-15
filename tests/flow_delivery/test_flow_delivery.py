"""Règles pures des champs de livraison, tools/flow_delivery.py (change jira-delivery-fields, design D1, D2, D5, D7, D11, D13 ; spec
jira-flow-delivery-fields).

    bash tests/run_all.sh flow_delivery

Aucune base, aucun réseau. Les valeurs sont inventées ; les chaînes « zz » sont distinctives : un test qui les retrouve dans une forme
stockée prouve que la réduction garde ce qu'elle ne doit pas garder.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_delivery as fd  # noqa: E402
import table_factice  # noqa: E402


def setUpModule():
    """Les tests lisent la table FACTICE (R-20261114-108) : aucun identifiant réel dans le dépôt ; sans table, l'état est neutre."""
    fd.configurer(table_factice.TABLE)


def tearDownModule():
    fd.configurer(None)


UUID = "0123456789abcdef-0123456789abcdef-012"[:36]
UUID_B = "fedcba9876543210-fedcba9876543210-012"[:36]


def filtre(noms=("ZzNomSensible",)):
    return fd.FiltreOptions(lambda: list(noms))


class Glissement(unittest.TestCase):
    """Spec « Slip rule » (D7)."""

    def test_premier_remplissage(self):
        self.assertEqual(fd.slips([set(), {"S1"}])[0], 0)

    def test_identifiant_ajoute(self):
        self.assertEqual(fd.slips([{"S1"}, {"S1", "S2"}])[0], 1)

    def test_vide_puis_rempli(self):
        self.assertEqual(fd.slips([{"V1"}, set(), {"V2"}])[0], 1)

    def test_identifiant_retire_seul(self):
        self.assertEqual(fd.slips([{"S1", "S2"}, {"S1"}])[0], 0)

    def test_instants_des_glissements(self):
        nombre, instants = fd.slips([("t1", {"A"}), ("t2", {"B"}), ("t3", set()), ("t4", {"B"}), ("t5", {"C"})])
        self.assertEqual((nombre, instants), (2, ["t2", "t5"]))

    def test_meme_valeur_deux_fois_n_est_pas_un_glissement(self):
        self.assertEqual(fd.slips([{"A"}, {"A"}, {"A"}])[0], 0)

    def test_aucune_valeur(self):
        self.assertEqual(fd.slips([]), (0, []))


class FluxDUneEpic(unittest.TestCase):
    """Spec « Flow of an epic read on its own statuses » (D11)."""

    def test_epic_sans_story_trois_transitions_propres(self):
        propres = [["2026-01-01", "A", "B"], ["2026-01-02", "B", "C"], ["2026-01-03", "C", "D"]]
        self.assertEqual(fd.epic_flow_source({"transitions": propres, "stories": []}), propres)

    def test_les_transitions_des_stories_ne_sont_pas_lues(self):
        propres = [["2026-01-01", "A", "B"]]
        epic = {"transitions": propres, "stories": [{"transitions": [["2026-02-01", "X", "Y"]]}]}
        self.assertEqual(fd.epic_flow_source(epic), propres)

    def test_epic_sans_transition(self):
        self.assertEqual(fd.epic_flow_source({"stories": [{"transitions": [["t", "a", "b"]]}]}), [])


class ComptesDEchecDeChangement(unittest.TestCase):
    """Spec « Change failure counts by detection version » (D13)."""

    def test_piloting_jamais_additionne(self):
        defauts = [{"phase": "production", "versions": ["V1"]}] * 2 + [{"phase": "piloting", "versions": ["V1"]}] * 3
        r = fd.change_failure_counts(defauts)
        self.assertEqual(r["versions"]["V1"], {"production": 2, "piloting": 3})
        self.assertNotIn(5, r["versions"]["V1"].values())

    def test_defaut_sans_version_de_detection(self):
        r = fd.change_failure_counts([{"phase": "production", "versions": []}, {"phase": "piloting"}])
        self.assertEqual((r["unattached_production"], r["unattached_piloting"], r["versions"]), (1, 1, {}))

    def test_plusieurs_versions_compte_dans_chacune(self):
        r = fd.change_failure_counts([{"phase": "production", "versions": ["V1", "V2"]}])
        self.assertEqual((r["versions"]["V1"]["production"], r["versions"]["V2"]["production"]), (1, 1))

    def test_total_sur_plusieurs_versions_compte_le_defaut_une_fois(self):
        r = fd.change_failure_counts([{"phase": "production", "versions": ["V1", "V2"]}], totaux={"annee": {"V1", "V2"}})
        self.assertEqual(r["totals"]["annee"], {"production": 1, "piloting": 0})
        self.assertEqual(r["total"]["production"], 1)

    def test_deux_defauts_sans_identifiant_sur_deux_versions_comptent_deux(self):
        r = fd.change_failure_counts([{"id": None, "phase": "production", "versions": ["V1"]},
                                      {"id": None, "phase": "production", "versions": ["V2"]}])
        self.assertEqual(r["total"]["production"], 2)

    def test_total_limite_a_une_version_exclut_le_defaut_qui_ne_cite_que_l_autre(self):
        r = fd.change_failure_counts([{"id": None, "phase": "production", "versions": ["V1"]},
                                      {"id": None, "phase": "production", "versions": ["V2"]}], totaux={"seul": {"V1"}})
        self.assertEqual(r["totals"]["seul"], {"production": 1, "piloting": 0})

    def test_autre_phase_et_phase_vide(self):
        r = fd.change_failure_counts([{"phase": None, "versions": ["V1"]}, {"phase": "Autre", "versions": ["V1"]}])
        self.assertEqual((r["other_phase"], r["versions"]), (2, {}))

    def test_le_libelle_brut_n_est_plus_accepte(self):
        r = fd.change_failure_counts([{"phase": "Production", "versions": ["V1"]}])
        self.assertEqual((r["other_phase"], r["versions"]), (1, {}))

    def test_les_champs_de_contexte_ne_sont_pas_lus(self):
        a = {"phase": "production", "versions": ["V1"], "detected_by": "zzA", "installed_base": "zzX", "affected": ["V9"]}
        b = {"phase": "production", "versions": ["V1"], "detected_by": "zzB", "installed_base": "zzY"}
        self.assertEqual(fd.change_failure_counts([a]), fd.change_failure_counts([b]))

    def test_un_defaut_deux_fois_la_meme_version_compte_une_fois(self):
        r = fd.change_failure_counts([{"phase": "production", "versions": ["V1", "V1"]}])
        self.assertEqual(r["versions"]["V1"]["production"], 1)


class Changelog(unittest.TestCase):
    """Spec « Delivery field events read from identifiers only » (D2, R-20261102-34)."""

    def test_liste_entre_crochets(self):
        ajoutes, retires, illisibles = fd.evenements_actifs(f"[{UUID}:101]", f"[{UUID}:101, {UUID_B}:102]")
        self.assertEqual((ajoutes, retires, illisibles), ({"102"}, set(), 0))

    def test_crochet_interieur_rend_l_element_illisible(self):
        ids, illisibles = fd.identifiants_d_actifs(f"[{UUID}:[5], {UUID_B}:6]")
        self.assertEqual(ids, {"6"})
        self.assertEqual(len(illisibles), 1)

    def test_chiffres_non_ascii_refuses(self):
        self.assertEqual(fd.identifiants_d_actifs(f"[{UUID}:٣]"), (set(), {f"{UUID}:٣"}))
        self.assertEqual(fd.identifiants_de_sprints("٣, 4"), {"4"})

    def test_colonne_vide_ou_absente(self):
        self.assertEqual(fd.evenements_actifs(None, f"[{UUID}:7]"), ({"7"}, set(), 0))
        self.assertEqual(fd.evenements_actifs(f"[{UUID}:7]", ""), (set(), {"7"}, 0))
        self.assertEqual(fd.evenements_actifs("[]", None), (set(), set(), 0))

    def test_element_hors_motif_compte_et_reste_ecarte(self):
        ajoutes, retires, illisibles = fd.evenements_actifs(f"[{UUID}:1]", f"[{UUID}:1, ZzLibelleVersion]")
        self.assertEqual((ajoutes, retires, illisibles), (set(), set(), 1))

    def test_pas_de_repli_sur_un_libelle_ou_un_nombre_nu(self):
        self.assertEqual(fd.identifiants_d_actifs("101"), (set(), {"101"}))
        self.assertEqual(fd.identifiants_d_actifs("ZzLibelle (ABC-1)"), (set(), {"ZzLibelle (ABC-1)"}))

    def test_evenements_de_livraison_ignore_les_chaines(self):
        historiques = [{"created": "2026-03-01T09:00:00.000+0100", "items": [
            {"fieldId": "customfield_99001", "from": "10, 11", "to": "11,12", "fromString": "ZzSprintA, ZzSprintB",
             "toString": "ZzSprintB, ZzSprintC"},
            {"fieldId": "customfield_99002", "from": f"[{UUID}:101]", "to": f"[{UUID}:101, {UUID_B}:102]",
             "fromString": "ZzVersionA", "toString": "ZzVersionA, ZzVersionB"},
            {"fieldId": "customfield_99006", "from": f"[{UUID}:1]", "to": f"[{UUID}:2]"},     # champ de défaut : jamais lu
            {"fieldId": "assignee", "from": "u1", "to": "u2"}]}]
        sprints_, actifs, illisibles = fd.evenements_de_livraison(historiques)
        self.assertEqual(sorted(sprints_), sorted([[historiques[0]["created"], "remove", "10"], [historiques[0]["created"], "add", "12"]]))
        self.assertEqual(actifs, [[historiques[0]["created"], "add", "target:102"]])
        self.assertEqual(illisibles, 0)
        self.assertNotIn("Zz", repr((sprints_, actifs)))

    def test_champs_historises_avec_les_versions_d_epic_sans_champ_de_defaut(self):
        # Remplace test_champs_historises_sans_champ_de_defaut_ni_epic_tant_que_1_1_n_a_pas_tranche : R-20261102-61 (1) (a), le relevé 1.1 v2
        # a tranché (forme, type et comptes), les deux versions d'épic sont historisées comme celles des stories ; remplace la suspension
        # de R-20261102-55 (2a). Les champs des seuls défauts restent absents (R-20261102-33).
        ids = fd.champs_historises()
        self.assertEqual(ids, ["customfield_99001", "customfield_99002", "customfield_99003", "customfield_99004", "customfield_99005"])
        self.assertTrue(set(fd.CHAMPS_ACTIFS_DEFAUT.values()).isdisjoint(ids))
        self.assertTrue(set(fd.CHAMPS_OPTIONS_DEFAUT.values()).isdisjoint(ids))

    def test_changelog_d_epic_lu_comme_celui_d_une_story(self):
        # R-20261102-61 : même motif, mêmes événements add/remove, par genre epic_a / epic_b.
        date = "2026-03-01T09:00:00.000+0100"
        historiques = [{"created": date, "items": [
            {"fieldId": "customfield_99004", "from": f"[{UUID}:301]", "to": f"[{UUID}:301, {UUID_B}:302]"},
            {"fieldId": "customfield_99005", "from": f"[{UUID}:401]", "to": f"[{UUID_B}:402]"}]}]
        sprints_, actifs, illisibles = fd.evenements_de_livraison(historiques)
        self.assertEqual(sprints_, [])
        self.assertEqual(sorted(actifs), sorted([[date, "add", "epic_a:302"], [date, "remove", "epic_b:401"], [date, "add", "epic_b:402"]]))
        self.assertEqual(illisibles, 0)

    def test_element_hors_motif_sur_une_version_d_epic_compte_et_ecarte_le_reste_est_garde(self):
        # R-20261102-36 (Q309) appliquée à la seconde version d'épic par R-20261102-61 : l'élément hors motif est compté et écarté, le reste du changement gardé.
        date = "2026-03-01T09:00:00.000+0100"
        historiques = [{"created": date, "items": [
            {"fieldId": "customfield_99005", "from": f"[{UUID}:401]", "to": f"[{UUID}:401, {UUID_B}:402, ZzLibelleSeul]"}]}]
        sprints_, actifs, illisibles = fd.evenements_de_livraison(historiques)
        self.assertEqual(actifs, [[date, "add", "epic_b:402"]])
        self.assertEqual(illisibles, 1)
        self.assertNotIn("ZzLibelleSeul", repr((sprints_, actifs)))

    def test_valeur_courante_d_une_epic_lue_par_courantes_de(self):
        champs = {"customfield_99004": [{"objectId": "301", "id": "ZzIdLong"}], "customfield_99005": [{"objectId": "401"}, {"objectId": "402"}]}
        self.assertEqual(fd.courantes_de(champs), {"actifs": {"epic_a": ["301"], "epic_b": ["401", "402"]}})
        self.assertEqual(fd.courantes_de({"customfield_99005": [{"objectId": "401"}]}), {"actifs": {"epic_b": ["401"]}})

    def test_valeurs_courantes_absentes_restent_absentes(self):
        self.assertEqual(fd.courantes_de({}), {})
        self.assertEqual(fd.courantes_de({"customfield_99001": None, "customfield_99002": [{"objectId": "5", "id": "9"}]}),
                         {"sprints": [], "actifs": {"target": ["5"]}})


class Reduction(unittest.TestCase):
    """Spec « Closed list of delivery fields in their stored form », « Asset version fields kept as object identifiers », « Option values
    filtered before storage » (D1)."""

    CHAMPS = {
        "customfield_99001": [{"id": 31, "name": "ZzSprintNom", "state": "closed", "goal": "ZzButDuSprint", "boardId": 4,
                               "startDate": "2026-09-01T08:00:00.000Z", "endDate": "2026-09-14T17:00:00.000Z",
                               "completeDate": "2026-09-15T09:00:00.000Z"}],
        "customfield_99002": [{"workspaceId": "ZzWorkspace", "id": "ZzIdLong", "objectId": "101", "label": "ZzLibelleActif"}],
        "customfield_99003": [{"objectId": "102"}],
        "customfield_99004": [{"objectId": "103"}],
        "customfield_99008": [{"id": "1", "value": "Nature A"}],
        "customfield_99009": [{"id": "7", "value": "Option courante"}, {"id": "8", "value": "Voie ZzNomSensible"}],
        "customfield_99010": {"id": "2", "value": "Cible 1"},
        "customfield_99015": 12.5,
        "customfield_99016": [{"value": "ZzClientNomme"}],
        "customfield_99017": None,
        "customfield_99018": "ZzObjectifTexteLibre",
        "customfield_99006": [{"objectId": "201"}],
        "customfield_99007": [{"objectId": "202"}],
        "customfield_99019": {"id": "11", "value": "Production"},
        "customfield_99020": {"id": "12", "value": "ZzNomSensible equipe"},
        "customfield_99021": {"id": "13", "value": "Base installee"},
    }

    def test_sprint_sans_nom_ni_but_ni_tableau(self):
        self.assertEqual(fd.sprints(self.CHAMPS["customfield_99001"]),
                         [{"id": "31", "state": "closed", "start": "2026-09-01T08:00:00.000Z", "end": "2026-09-14T17:00:00.000Z",
                           "complete": "2026-09-15T09:00:00.000Z"}])

    def test_actifs_identifiant_d_objet_seul(self):
        self.assertEqual(fd.objets_d_actifs(self.CHAMPS["customfield_99002"]), ["101"])

    def test_livraison_d_une_story(self):
        livraison = fd.livraison_de(self.CHAMPS, "Story", ["Bug"])
        self.assertEqual(livraison["assets"], {"target": ["101"], "resolution": ["102"], "epic_a": ["103"]})
        self.assertEqual(livraison["flags"], {"customer_commitment": True, "source_commitment": False, "strategic_objective": True})
        self.assertEqual(livraison["single"], {"release_target": "2"})          # R-20261102-51 : l'identifiant d'option, plus la valeur
        self.assertEqual(livraison["rank"], "12.5")
        self.assertNotIn("defect", livraison)                  # types hors défauts : champs de défaut écartés
        self.assertNotIn("detected", livraison["assets"])
        for secret in ("ZzSprintNom", "ZzButDuSprint", "ZzClientNomme", "ZzObjectifTexteLibre", "ZzLibelleActif", "ZzWorkspace", "ZzIdLong"):
            self.assertNotIn(secret, repr(livraison))

    def test_option_de_flux_en_identifiants_sans_valeur(self):
        # Remplace test_valeur_d_option_a_nom_sensible_remplacee_par_le_marqueur : mécanisme changé par R-20261102-51 (plus de valeur stockée,
        # donc plus de marqueur sur une valeur d'option).
        livraison = fd.livraison_de(self.CHAMPS, "Story", ["Bug"])
        self.assertEqual(livraison["options"]["workflow_option"], ["7", "8"])
        self.assertNotIn("ZzNomSensible", repr(livraison))

    def test_champs_de_defaut_pour_un_type_de_defaut_seulement(self):
        livraison = fd.livraison_de(self.CHAMPS, "bug", ["Bug"])
        self.assertEqual(livraison["assets"]["detected"], ["201"])
        self.assertEqual(livraison["assets"]["affected"], ["202"])
        self.assertEqual(livraison["defect"]["detection_phase"], {"id": "11", "code": "production"})          # R-20261102-51 : code fermé
        self.assertEqual(livraison["defect"]["detected_by"], {"id": "12"})
        self.assertEqual(livraison["defect"]["installed_base"], {"id": "13"})
        self.assertNotIn("ZzNomSensible", repr(livraison))
        self.assertNotIn("Base installee", repr(livraison))

    def test_aucun_champ_rempli_donne_none(self):
        self.assertIsNone(fd.livraison_de({}, "Story", []))

    def test_liste_fermee_des_champs_demandes(self):
        demandes = set(fd.champs_demandes())
        self.assertEqual(len(demandes), len(fd.champs_demandes()))
        for interdit in ("summary", "description", "assignee", "reporter", "creator", "comment", "timespent", "timeoriginalestimate"):
            self.assertNotIn(interdit, demandes)
        self.assertTrue(all(d.startswith("customfield_") for d in demandes))

    def test_le_filtre_ne_charge_la_liste_qu_a_la_premiere_valeur(self):
        appels = []
        f = fd.FiltreOptions(lambda: appels.append(1) or ["ZzNomSensible"])
        fd.version_de_ticket({"customfield_20000": 1}, f)          # R-20261102-51 : le filtre ne sert plus qu'au nom court d'une version
        self.assertEqual(appels, [])


class JointureDesVersions(unittest.TestCase):
    """Spec « Version attributes joined by asset object » (D5)."""

    @staticmethod
    def ticket(objets, **autres):
        return {"objets": objets, "short_name": "ZzNomCourt", "status": "Released", "status_category": "Done",
                "started": "2026-01-05", "released": "2026-03-10T00:00:00.000+0100", **autres}

    def test_un_objet_par_ticket(self):
        contenus, comptes = fd.joindre_versions([self.ticket(["101"])])
        self.assertEqual(contenus["101"], {"short_name": "ZzNomCourt", "status": "Released", "status_category": "Done",
                                           "started": "2026-01-05", "released": "2026-03-10"})
        self.assertEqual((comptes["lus"], comptes["sans_actif"], comptes["conflits"]), (1, 0, 0))

    def test_deux_tickets_sur_un_objet_attributs_nuls(self):
        contenus, comptes = fd.joindre_versions([self.ticket(["101"]), self.ticket(["101"])])
        self.assertEqual(contenus["101"], fd.CONTENU_VIDE)
        self.assertEqual(comptes["conflits"], 1)

    def test_ticket_sans_actif_ou_a_plusieurs_objets_compte_non_stocke(self):
        contenus, comptes = fd.joindre_versions([self.ticket([]), self.ticket(["1", "2"])])
        self.assertEqual((contenus, comptes["sans_actif"], comptes["plusieurs_actifs"]), ({}, 1, 1))          # lignes distinctes (Q327)

    def test_nom_court_sensible_passe_par_le_filtre(self):
        f = filtre()
        lu = fd.version_de_ticket({"customfield_99022": [{"objectId": "55"}], "customfield_99025": "Produit ZzNomSensible 2"}, f)
        self.assertEqual(lu["short_name"], fd.MARQUEUR)
        self.assertEqual(f.remplacees, 1)
        self.assertEqual(fd.version_de_ticket({"customfield_99025": "v1.2"}, f)["short_name"], "v1.2")

    def test_lecture_d_un_ticket_de_version(self):
        lu = fd.version_de_ticket({"customfield_99022": [{"objectId": "55", "id": "9"}], "customfield_99025": "v1.2",
                                   "customfield_99023": "2026-02-02", "customfield_99024": "2026-01-01",
                                   "status": {"name": "Released", "statusCategory": {"name": "Done"}}, "summary": "ZzResume"})
        self.assertEqual(lu["objets"], ["55"])
        self.assertNotIn("ZzResume", repr(lu))


class Engagements(unittest.TestCase):
    """R-20261102-50 : présence seulement. Rempli = oui, vide = non ; aucune valeur d'option n'est lue, « No » comprise (le cas « No = non » de
    Q329, R-20261102-41, est retiré : l'ancien test test_no_yes_et_vide l'affirmait, retiré au titre de R-20261102-50)."""

    def test_toute_option_vaut_oui_le_vide_vaut_non(self):
        for option in ({"id": "1", "value": "ZzClient1"}, {"id": "2", "value": "No"}, {"id": "3", "value": "Yes"}, [{"value": "no"}]):
            self.assertTrue(fd.rempli(option), option)
        self.assertFalse(fd.rempli({"value": ""}))
        self.assertFalse(fd.rempli(None))
        self.assertFalse(fd.rempli([]))

    def test_indicateurs_dans_la_forme_stockee_sans_aucune_valeur(self):
        champs = {"customfield_99016": {"id": "1", "value": "No"}, "customfield_99017": {"id": "2", "value": "ZzClient1"},
                  "customfield_99018": {"id": "3", "value": "Yes"}}
        livraison = fd.livraison_de(champs, "Story", [])
        self.assertEqual(livraison["flags"], {"customer_commitment": True, "source_commitment": True, "strategic_objective": True})
        for valeur in ("ZzClient1", "No", "Yes"):
            self.assertNotIn(valeur, repr(livraison))
        vide = {"customfield_99016": None, "customfield_99017": [], "customfield_99018": {"value": ""}}
        self.assertIsNone(fd.livraison_de(vide, "Story", []))          # tous vides : aucun indicateur stocké


class IdentifiantsDOption(unittest.TestCase):
    """R-20261102-51 : pour les champs à options, l'identifiant d'option seul est stocké, jamais la valeur."""

    def test_options_multiples_et_uniques_en_identifiants(self):
        champs = {"customfield_99008": [{"id": "1", "value": "ZzNature"}], "customfield_99009": [{"id": "7", "value": "ZzFlux"}, {"value": "SansId"}],
                  "customfield_99010": {"id": "2", "value": "ZzCible"}, "customfield_99011": {"id": "3", "value": "ZzVerif"},
                  "customfield_99012": {"id": "4", "value": "ZzSecu"}, "customfield_99013": {"id": "5", "value": "ZzIsp"},
                  "customfield_99014": {"id": "6", "value": "ZzRevue"}}
        livraison = fd.livraison_de(champs, "Story", [])
        self.assertEqual(livraison["options"], {"category_nature": ["1"], "workflow_option": ["7"]})
        self.assertEqual(livraison["single"], {"release_target": "2", "verification_required": "3", "product_safety": "4", "isp": "5",
                                               "code_review_status": "6"})
        self.assertNotIn("Zz", repr(livraison))
        self.assertNotIn("SansId", repr(livraison))

    def test_phase_de_detection_code_ferme(self):
        self.assertEqual(fd.phase_de_detection({"id": "1", "value": "Production"}), {"id": "1", "code": "production"})
        self.assertEqual(fd.phase_de_detection({"id": "2", "value": " Piloting "}), {"id": "2", "code": "piloting"})
        self.assertEqual(fd.phase_de_detection({"id": "3", "value": "ZzLibelleLibre"}), {"id": "3", "code": "other"})
        self.assertEqual(fd.phase_de_detection({"id": "4", "value": "production"}), {"id": "4", "code": "other"})          # comparaison exacte (D13)
        self.assertIsNone(fd.phase_de_detection(None))
        self.assertNotIn("ZzLibelleLibre", repr(fd.phase_de_detection({"id": "3", "value": "ZzLibelleLibre"})))

    def test_code_stocke_comparable_dans_les_comptes_d_echec(self):
        r = fd.change_failure_counts([{"phase": "production", "versions": ["V1"]}, {"phase": "piloting", "versions": ["V1"]},
                                      {"phase": "other", "versions": ["V1"]}])
        self.assertEqual((r["versions"]["V1"], r["other_phase"]), ({"production": 1, "piloting": 1}, 1))

    def test_detecte_par_et_base_installee_identifiant_seul(self):
        champs = {"customfield_99019": {"id": "11", "value": "Production"}, "customfield_99020": {"id": "12", "value": "ZzDetectePar"},
                  "customfield_99021": {"id": "13", "value": "ZzBase"}}
        defaut = fd.livraison_de(champs, "Bug", ["Bug"])["defect"]
        self.assertEqual(defaut, {"detection_phase": {"id": "11", "code": "production"}, "detected_by": {"id": "12"},
                                  "installed_base": {"id": "13"}})


class LignesVoulues(unittest.TestCase):
    def test_lignes_d_un_ticket_sans_livraison(self):
        self.assertTrue(all(not v for v in fd.lignes_de("PROJ-1", None).values()))

    def test_lignes_d_une_livraison(self):
        livraison = {"sprints": [{"id": "5", "state": "active", "start": "2026-01-01T00:00:00Z", "end": None, "complete": None}],
                     "assets": {"target": ["1"], "detected": ["2"]}, "options": {"workflow_option": ["9"]},
                     "single": {"isp": "5"}, "flags": {"customer_commitment": True}, "rank": "3",
                     "defect": {"detection_phase": {"id": "1", "code": "production"}, "detected_by": {"id": "4"}}}          # R-20261102-51 : identifiants seuls
        lignes = fd.lignes_de("PROJ-1", livraison)
        self.assertEqual({(a[1], a[2]) for a in lignes["assets"]}, {("target", "1"), ("detected", "2")})
        self.assertEqual(len(lignes["fields"]), 1)
        self.assertEqual(next(iter(lignes["fields"]))[3:5], (None, "5"))
        self.assertEqual(next(iter(lignes["defect"])), ("PROJ-1", "1", "production", "4", None))
        self.assertEqual(next(iter(lignes["options"])), ("PROJ-1", "workflow_option", 1, "9"))
        self.assertEqual(next(iter(lignes["sprints"]))[:3], ("PROJ-1", "5", "active"))

    def test_canonique_ignore_l_ordre(self):
        a = {"sprints": [{"id": "2"}, {"id": "1"}], "assets": {"target": ["2", "1"]}}
        b = {"sprints": [{"id": "1"}, {"id": "2"}], "assets": {"target": ["1", "2"]}}
        self.assertEqual(fd.canonique(a), fd.canonique(b))


class TableNeutreSansReglage(unittest.TestCase):
    """R-20261114-108 (même logique que A-92) : sans table de flux.yaml, le code ne porte aucun identifiant réel et se comporte de façon
    neutre et explicite : aucun champ demandé, lu ni stocké ; `configurer` rend False pour que l'export et la collecte le disent."""

    def setUp(self):
        self.addCleanup(fd.configurer, table_factice.TABLE)          # les autres classes lisent la table factice
        self.assertFalse(fd.configurer(None))

    def test_aucun_champ_demande_ni_historise(self):
        self.assertEqual((fd.champs_demandes(), fd.champs_historises()), ([], []))
        self.assertEqual(fd.champs_versions(), ["issuetype", "status"])
        self.assertFalse(fd.table_configuree() or fd.versions_configurees())

    def test_aucun_champ_lu_ni_stocke(self):
        champs = {"customfield_99001": [{"id": 31}], "customfield_99002": [{"objectId": "1"}], "customfield_99016": {"value": "x"},
                  "customfield_99019": {"id": "1", "value": "Production"}}
        self.assertIsNone(fd.livraison_de(champs, "Bug", ["Bug"]))
        self.assertEqual(fd.courantes_de(champs), {})
        historiques = [{"created": "2026-03-01T09:00:00.000+0100", "items": [
            {"fieldId": "customfield_99001", "from": "1", "to": "2"}, {"fieldId": "customfield_99002", "from": None, "to": f"[{UUID}:1]"},
            {"fieldId": None, "from": "1", "to": "2"}]}]
        self.assertEqual(fd.evenements_de_livraison(historiques), ([], [], 0))

    def test_ticket_de_version_sans_champ_declare(self):
        lu = fd.version_de_ticket({"customfield_99022": [{"objectId": "55"}], "status": {"name": "Open"}})
        self.assertEqual((lu["objets"], lu["short_name"], lu["started"], lu["released"]), ([], None, None, None))

    def test_table_partielle(self):
        fd.configurer({"sprint": "customfield_99001", "assets": {"target": "customfield_99002"}})
        self.assertTrue(fd.table_configuree())
        self.assertFalse(fd.versions_configurees())
        self.assertEqual(fd.champs_demandes(), ["customfield_99001", "customfield_99002"])
        self.assertEqual(fd.champs_historises(), ["customfield_99001", "customfield_99002"])
        livraison = fd.livraison_de({"customfield_99001": [{"id": 31}], "customfield_99019": {"id": "1", "value": "Production"}},
                                    "Bug", ["Bug"])
        self.assertEqual(list(livraison), ["sprints"])          # un champ de défaut non déclaré n'est pas lu, sans erreur

    def test_aucun_identifiant_reel_dans_le_module(self):
        """Garde locale : le module ne tient aucun identifiant `customfield_<chiffres>` ; le test d'empreintes de l'édition couvre les réels.
        Source : tests/build_edition/test_champs_livraison_absents.py (empreintes des identifiants réels) ; cette garde ne vérifie que
        l'absence de toute forme `customfield_<chiffres>` dans ce module. Un écart se détecte ainsi : l'une échoue dès qu'un identifiant,
        réel ou non, entre dans le module ; l'autre échoue pour un identifiant réel dans n'importe quel fichier de l'édition."""
        import re
        texte = (Path(fd.__file__)).read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"customfield_[0-9]+", texte), [])


if __name__ == "__main__":
    unittest.main()
