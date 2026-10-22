"""Export : équipes par le référentiel d'organisation, étiquettes déclarées, versions, conservation (change jira-gdpr-alignment,
groupe 5 ; design D3, D4, D5, D11, D17, D19).

    bash tests/run_all.sh export_jira_api </dev/null

Specs : jira-flow-export (« Team table for asset-object team fields », « Diagnose subcommand », « Strict option for unknown
team identifiers », « Declared label and fix version columns », « Rows past the retention rule are not written »),
jira-flow-labels (« Only declared labels are stored », « Look-alike labels counted, never listed », « Jira labels only »,
« Exactly one up-merge label »), jira-flow-organisation (« Jira teams and referential teams controlled », « Names stay in the
flow folder »). Faux serveur et données inventées de test_export_jira_api.py ; la date du jour de la conservation est fixée
(AUJOURDHUI du fichier de base).
"""
import unittest

from test_export_jira_api import CHAMP, JETON, TICKETS, Base, champs, objet

# Référentiel : trois équipes décrites avec leurs identifiants, deux équipes sans identifiant ni ticket.
REFERENTIEL = """source_date: 2026-10-01
sites: [Site 1]
departments:
  - name: Departement 1
    site: Site 1
    headcount: 20
    teams: [Equipe A, Equipe B, Equipe C, Equipe D, Equipe E]
teams:
  - name: Equipe A
    headcount: 4
    jira_team_ids: ['1']
  - name: Equipe B
    headcount: 4
    jira_team_ids: ['2']
  - name: Equipe C
    headcount: 4
    jira_team_ids: ['3']
  - name: Equipe D
    headcount: 4
  - name: Equipe E
    headcount: 4
"""
SANS_IDENTIFIANT = REFERENTIEL.replace("    jira_team_ids: ['1']\n", "").replace("    jira_team_ids: ['2']\n", "") \
    .replace("    jira_team_ids: ['3']\n", "")
TABLE = "equipes: {'1': Table A, '2': Table B, '3': Table C, '4': Table D, '5': Table E, '6': Table F}\n"

# (objets Assets du ticket) : trois identifiants inconnus du référentiel (4, 5, 6) sur deux tickets.
ASSETS = {"ABC-1": [objet(1)], "ABC-2": [objet(2), objet(3)], "ABC-3": [objet(4)], "ABC-4": [objet(6), objet(5)]}
INCONNUE = "(équipe inconnue)"
ETAT_NEUF = ("Story", "Open", "To Do", "2026-09-01T16:45:00.000+0200")


class BaseAssets(Base):
    def setUp(self):
        super().setUp()
        self.faux.tickets = {}
        for cle, objets in ASSETS.items():
            t = champs(*ETAT_NEUF)
            t[CHAMP] = objets
            self.faux.tickets[cle] = t

    def ecrire(self, nom: str, contenu: str):
        chemin = self.ws / "Flux-Lab" / nom
        chemin.write_text(contenu, encoding="utf-8")
        return chemin

    def exporter_code(self, *extra: str):
        """(code, sortie, magasin) : l'export n'écrit aucun fichier, ses effets sont dans le faux magasin de la couche brute."""
        code, sortie = self.lancer("export", *extra)
        return code, sortie, self.magasin

    def equipes_par_cle(self) -> dict[str, list[str]]:
        return {i["issue_key"]: self.equipes(i) for i in self.magasin.instantanes}


class TraductionParReferentiel(BaseAssets):
    def test_le_referentiel_traduit_les_equipes_de_chaque_ticket(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        equipes = self.equipes_par_cle()
        self.assertEqual(equipes["ABC-1"], ["Equipe A"])
        self.assertEqual(equipes["ABC-2"], ["Equipe B", "Equipe C"])
        self.assertEqual(equipes["ABC-3"], [INCONNUE])
        self.assertEqual(equipes["ABC-4"], [INCONNUE, INCONNUE])          # ordre de l'API conservé
        identifiants = {i["issue_key"]: [e["jira_team_id"] for e in i["teams"]] for i in self.magasin.instantanes}
        self.assertEqual(identifiants["ABC-4"], ["6", "5"])               # l'identifiant inconnu est gardé dans l'instantané

    def test_identifiants_inconnus_comptes_et_listes_sans_nom_ni_cle(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertIn("identifiants d'équipe ni dans le référentiel ni dans le catalogue : 3, sur 2 tickets", sortie)
        self.assertIn("identifiants à ajouter : 4 ; 5 ; 6", sortie)         # liste triée des identifiants
        for interdit in ("Equipe", "ABC-", "ws-secret", "Site 1", "Departement", self.url, JETON):
            self.assertNotIn(interdit, sortie)

    def test_identifiants_inconnus_en_anglais(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        code, sortie, _ = self.exporter_code("--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("team identifiers in neither the referential nor the catalogue: 3, on 2 tickets", sortie)
        self.assertIn("identifiers to add: 4; 5; 6", sortie)

    def test_referentiel_complet_aucun_message_de_completion(self):
        self.ecrire("organisation.yaml", REFERENTIEL.replace("jira_team_ids: ['3']", "jira_team_ids: ['3', '4', '5', '6']"))
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        for absent in ("ni dans le référentiel", "à ajouter", "dépréciée"):
            self.assertNotIn(absent, sortie)

    def test_le_referentiel_seul_sans_table_n_affiche_pas_l_avertissement(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        _, sortie, _ = self.exporter_code()
        self.assertNotIn("dépréciée", sortie)

    def test_aucun_appel_a_l_api_assets(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        self.exporter_code()
        self.assertEqual(self.faux.appels_get, [])
        self.assertEqual({chemin for _, chemin in self.faux.appels}, {"/rest/api/3/search/jql"})

    def test_marqueur_inconnu_independant_de_la_langue(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        for langue in ("fr", "en"):
            self.magasin.instantanes.clear()
            code, sortie, _ = self.exporter_code("--language", langue)
            self.assertEqual(code, 0, sortie)
            self.assertIn(INCONNUE, {nom for equipes in self.equipes_par_cle().values() for nom in equipes})

    def test_referentiel_illisible_arrete_l_export_sans_valeur(self):
        for contenu in ("sites: [pas, un", REFERENTIEL + "owner: Une Personne\n"):
            with self.subTest(contenu=contenu[:12]):
                self.ecrire("organisation.yaml", contenu)
                code, sortie, magasin = self.exporter_code()
                self.assertNotEqual(code, 0)
                self.assertEqual(magasin.passages, [])
                self.assertEqual(self.faux.requetes, [])                     # arrêt avant tout appel à Jira
                self.assertNotIn("Une Personne", str(code) + sortie)

    def test_referentiel_avec_identifiant_sous_deux_equipes_refuse(self):
        self.ecrire("organisation.yaml", REFERENTIEL.replace("jira_team_ids: ['2']", "jira_team_ids: ['1']"))
        code, sortie, magasin = self.exporter_code()
        self.assertNotEqual(code, 0)
        self.assertEqual(magasin.passages, [])

    def test_referentiel_absent_et_libelles_utilisables_comme_avant(self):
        self.faux.tickets = {cle: dict(t) for cle, t in TICKETS.items()}
        code, sortie, magasin = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(magasin.passages), 1)

    # --- 5.2 contrôles du référentiel
    def test_equipes_du_referentiel_sans_ticket_comptees_sans_nom(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertIn("équipes du référentiel sans ticket : 2", sortie)
        code, sortie, _ = self.exporter_code("--language", "en")
        self.assertIn("referential teams without ticket: 2", sortie)
        for nom in ("Equipe D", "Equipe E", "Equipe A"):
            self.assertNotIn(nom, sortie)

    def test_aucune_equipe_inactive_aucune_ligne(self):
        trois = REFERENTIEL.replace("  - name: Equipe D\n    headcount: 4\n", "").replace("  - name: Equipe E\n    headcount: 4\n", "") \
            .replace(", Equipe D, Equipe E]", "]").replace("jira_team_ids: ['3']", "jira_team_ids: ['3', '4', '5', '6']")
        self.ecrire("organisation.yaml", trois)
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("sans ticket", sortie)

    def test_equipes_par_libelles_comptees_aussi_avec_un_referentiel(self):
        self.ecrire("organisation.yaml", SANS_IDENTIFIANT)
        self.faux.tickets = {"ABC-1": {**champs(*ETAT_NEUF, equipes=["Equipe A", "Equipe B"])}}
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertIn("équipes du référentiel sans ticket : 3", sortie)
        self.assertNotIn("Equipe", sortie)

    def test_controle_une_seule_fois_pour_plusieurs_requetes(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.count("équipes du référentiel sans ticket"), 1)

    # --- option stricte
    def test_strict_teams_identifiant_inconnu_du_referentiel(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        code, sortie, magasin = self.exporter_code("--strict-teams")
        self.assertEqual(code, 3, sortie)
        self.assertEqual((magasin.passages, magasin.visites, magasin.instantanes), ([], [], []))        # rien d'enregistré sur le code 3
        self.assertTrue(sortie.rstrip().endswith("identifiants d'équipe inconnus : export incomplet"), sortie)
        code, sortie, _ = self.exporter_code("--strict-teams", "--language", "en")
        self.assertTrue(sortie.rstrip().endswith("unknown team identifiers: export incomplete"), sortie)

    def test_strict_teams_referentiel_complet_sort_avec_0(self):
        self.ecrire("organisation.yaml", REFERENTIEL.replace("jira_team_ids: ['3']", "jira_team_ids: ['3', '4', '5', '6']"))
        code, sortie, _ = self.exporter_code("--strict-teams")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("export incomplet", sortie)

    def test_sans_strict_teams_le_code_reste_0(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        self.assertEqual(self.exporter_code()[0], 0)

    # --- diagnose
    def test_diagnose_reference_le_referentiel_sans_identifiant_ni_nom(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 0, sortie)
        self.assertIn("sources d'équipes : référentiel 3 identifiants, catalogue 0 identifiants", sortie)
        for interdit in ("Equipe", "ws-secret", "equipes-assets"):
            self.assertNotIn(interdit, sortie)
        code, sortie = self.lancer("diagnose", "--language", "en")
        self.assertIn("team sources: referential 3 identifiers, catalogue 0 identifiers", sortie)

    def test_diagnose_referentiel_illisible_arrete(self):
        self.ecrire("organisation.yaml", "sites: [pas, un")
        code, sortie = self.lancer("diagnose")
        self.assertNotEqual(code, 0)


class AncienneTableNonLue(BaseAssets):
    """L'ancienne table n'est plus lue par l'export ni par diagnose (change team-mapping, tâches 4.1, 4.2, 4.7) : une phrase demande
    de la supprimer tant que le fichier existe."""

    PHRASE = "ancienne table des équipes plus lue : supprimer equipes-assets.yaml"

    def test_la_table_seule_ne_traduit_rien_et_l_export_s_arrete_sans_source(self):
        self.ecrire("equipes-assets.yaml", TABLE)
        code, sortie, magasin = self.exporter_code()
        self.assertEqual(code, 1, sortie)
        self.assertEqual(magasin.passages, [])
        self.assertIn("aucune source d'équipes", sortie)

    def test_la_phrase_est_imprimee_avec_le_referentiel_et_la_table_ne_change_pas_la_traduction(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        self.exporter_code()
        sans = self.equipes_par_cle()
        self.magasin.instantanes.clear()
        self.ecrire("equipes-assets.yaml", TABLE)
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertIn(self.PHRASE, sortie)
        self.assertEqual(self.equipes_par_cle(), sans)
        self.assertNotIn("Table", repr(self.magasin.instantanes))

    def test_phrase_en_anglais(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        self.ecrire("equipes-assets.yaml", TABLE)
        _, sortie, _ = self.exporter_code("--language", "en")
        self.assertIn("former team table no longer read: delete equipes-assets.yaml", sortie)
        self.assertNotIn("deprecated", sortie)

    def test_la_phrase_est_imprimee_une_seule_fois_sur_un_export_a_deux_requetes(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        self.ecrire("equipes-assets.yaml", TABLE)
        self.ecrire_reglages(f"export_team_field: {CHAMP}\njql_exports:\n  a: project = AAA\n  b: project = BBB\n")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sortie.count(self.PHRASE), 1)

    def test_l_ancienne_phrase_de_depreciation_n_existe_plus(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        self.ecrire("equipes-assets.yaml", TABLE)
        _, sortie, _ = self.exporter_code()
        self.assertNotIn("dépréciée", sortie)

    def test_pas_de_phrase_sans_table(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        _, sortie, _ = self.exporter_code()
        self.assertNotIn("plus lue", sortie)

    def test_la_table_illisible_n_est_pas_lue(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        self.ecrire("equipes-assets.yaml", "equipes: [pas, un")
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("illisible", sortie)

    def test_strict_teams_sort_avec_3_meme_quand_la_table_porte_les_identifiants(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        self.ecrire("equipes-assets.yaml", TABLE)               # les identifiants 4, 5, 6 y sont : ils restent inconnus
        code, sortie, magasin = self.exporter_code("--strict-teams")
        self.assertEqual(code, 3, sortie)
        self.assertEqual(magasin.passages, [])

    def test_pas_d_avertissement_quand_les_libelles_suffisent(self):
        self.ecrire("equipes-assets.yaml", TABLE)
        self.faux.tickets = {"ABC-1": champs(*ETAT_NEUF, equipes=["Equipe A"])}
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("plus lue", sortie)

    def test_diagnose_avec_la_table_seule_sort_avec_1_et_la_phrase(self):
        self.ecrire("equipes-assets.yaml", TABLE)
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 1, sortie)
        self.assertIn(self.PHRASE, sortie)

    def test_diagnose_ne_lit_pas_la_table(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        self.ecrire("equipes-assets.yaml", "equipes: [pas, un")
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 0, sortie)
        self.assertIn(self.PHRASE, sortie)


class AucuneSource(BaseAssets):
    def verifier_refus(self, sortie: str, magasin):
        self.assertEqual((magasin.passages, magasin.instantanes), ([], []))
        self.assertIn("organisation.yaml", sortie)
        for cle in ("jira_team_ids", "teams", "name", "headcount"):        # la structure : des clés
            self.assertIn(cle, sortie)
        for valeur in ("ws-secret", "Equipe", "ABC-", '"1"', "'1'"):       # jamais une valeur
            self.assertNotIn(valeur, sortie)
        self.assertNotIn("Créer à la main Flux-Lab/equipes-assets.yaml", sortie)

    def test_ni_referentiel_ni_table(self):
        code, sortie, chemin = self.exporter_code()
        self.assertEqual(code, 1, sortie)
        self.verifier_refus(sortie, chemin)
        self.assertIn("objet {id, objectId, workspaceId}", sortie)          # la forme du champ, jamais ses valeurs

    def test_ni_referentiel_ni_table_en_anglais(self):
        code, sortie, chemin = self.exporter_code("--language", "en")
        self.assertEqual(code, 1, sortie)
        self.verifier_refus(sortie, chemin)

    def test_referentiel_sans_identifiant_et_sans_table(self):
        self.ecrire("organisation.yaml", SANS_IDENTIFIANT)
        code, sortie, chemin = self.exporter_code()
        self.assertEqual(code, 1, sortie)
        self.verifier_refus(sortie, chemin)

    def test_diagnose_sort_avec_1_sans_aucune_source(self):
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 1, sortie)
        self.assertIn("Libellés exploitables : non", sortie)


# ---------------------------------------------------------------------------
# Étiquettes déclarées, versions correctives, conservation
# ---------------------------------------------------------------------------

DECLAREES = """declared_labels:
  up_merge:
    prefix: um-
    labels: [um-legal, um-hotfix]
  cycle:
    prefix: cy-
    labels: [cy-a, cy-b]
"""
VERIFICATION = "customfield_10004"
SECRET_ETIQUETTE = "ZZ-ETIQUETTE-LIBRE"
SECRET_VERSION = "ZZ-VERSION-SECRETE"


class BaseEtiquettes(Base):
    def reglages_avec(self, extra: str = DECLAREES) -> None:
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n" + extra)

    def ticket(self, cle: str, etiquettes=None, versions=None, **kw):
        t = champs(*ETAT_NEUF, equipes=["Equipe A"], **kw)
        if etiquettes is not None:
            t["labels"] = list(etiquettes)
        if versions is not None:
            t["fixVersions"] = [{"name": v} for v in versions]
        t[VERIFICATION] = True
        self.faux.tickets[cle] = t

    def champs_demandes(self) -> set[str]:
        return {f for r in self.faux.requetes for f in r["fields"]}


class AucuneEtiquetteNiVersion(BaseEtiquettes):
    """L'export ne demande ni étiquette ni version (la collecte de l'historique s'en charge, database-only D5), n'en enregistre aucune
    et n'en dit rien ; le bloc declared_labels des réglages ne le concerne plus."""

    def setUp(self):
        super().setUp()
        self.faux.tickets = {}

    def test_champs_labels_et_fixversions_jamais_demandes_avec_ou_sans_bloc(self):
        self.ticket("ABC-1", ["cy-a"], ["v1"])
        for extra in ("", DECLAREES):
            self.faux.requetes.clear()
            self.reglages_avec(extra=extra)
            self.exporter()
            demandes = self.champs_demandes()
            for interdit in ("labels", "fixVersions", "summary", "assignee", "reporter", "creator", "description", "comment", VERIFICATION):
                self.assertNotIn(interdit, demandes)

    def test_ni_etiquette_ni_version_dans_les_instantanes_ni_dans_la_console(self):
        self.reglages_avec()
        self.ticket("ABC-1", ["cy-a", "cy-extra", SECRET_ETIQUETTE, "um-legal", "um-hotfix"], [SECRET_VERSION])
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        enregistre = repr(self.magasin.instantanes)
        for chaine in ("cy-a", "cy-extra", "um-legal", "um-hotfix", SECRET_ETIQUETTE, SECRET_VERSION):
            self.assertNotIn(chaine, sortie)
            self.assertNotIn(chaine, enregistre)
        for chaine in ("ABC-", "Equipe", "étiquette", "label", "up-merge"):
            self.assertNotIn(chaine, sortie)

    def test_un_bloc_declared_labels_invalide_arrete_encore_l_export_avant_tout_appel(self):
        """Les réglages sont validés en bloc à la lecture (flux_config) : un bloc invalide arrête toujours l'export, sans rien enregistrer
        et sans nommer la valeur refusée."""
        self.reglages_avec(extra=DECLAREES.replace("cy-b", "xx-b"))
        self.ticket("ABC-1")
        code, sortie = self.lancer("export")
        self.assertNotEqual(code, 0)
        self.assertIn("declared_labels", str(code) + sortie)
        self.assertNotIn("xx-b", str(code) + sortie)
        self.assertEqual((self.faux.requetes, self.magasin.passages), ([], []))


class JiraSeulement(BaseEtiquettes):
    """Spec « Jira labels only » : lectures de l'API Jira seulement, aucune écriture, aucun appel Confluence."""

    def test_appels_enregistres_lectures_jira_seulement(self):
        self.reglages_avec()
        self.ticket("ABC-1", ["cy-a"], ["v1"])
        self.exporter()
        self.lancer("diagnose")
        self.lancer("fields", "--search", "team")
        self.assertTrue(self.faux.appels)
        for methode, chemin in self.faux.appels:
            self.assertIn(methode, ("GET", "POST"), (methode, chemin))                 # aucune méthode d'écriture
            self.assertTrue(chemin.startswith("/rest/api/3/"), chemin)
            for confluence in ("wiki", "confluence", "/rest/api/2/"):
                self.assertNotIn(confluence, chemin.lower())
        self.assertEqual(self.faux.hors_passerelle, [])

    def test_les_requetes_post_ne_sont_que_des_recherches(self):
        self.reglages_avec()
        self.ticket("ABC-1", ["cy-a"])
        self.exporter()
        self.assertEqual({chemin for methode, chemin in self.faux.appels if methode == "POST"}, {"/rest/api/3/search/jql"})


class Conservation(Base):
    """Les tickets résolus depuis plus que la durée de conservation ne sont pas écrits (aujourd'hui : AUJOURDHUI)."""

    def setUp(self):
        super().setUp()
        self.faux.tickets = {
            "ABC-1": champs("Story", "Closed", "Done", "2024-01-05T08:00:00.000+0100", "2024-02-10T10:30:00.000+0100", "Done",
                            equipes=["Equipe A"]),                                    # résolu il y a plus d'un an
            "ABC-2": champs("Story", "Closed", "Done", "2026-05-05T08:00:00.000+0200", "2026-07-10T10:30:00.000+0200", "Done",
                            equipes=["Equipe A"]),                                    # résolu récemment
            "ABC-3": champs("Story", "Open", "To Do", "2023-01-05T08:00:00.000+0100", equipes=["Equipe A"])}    # ouvert depuis longtemps

    def cles_ecrites(self) -> set[str]:
        """Clés vues par le dernier passage de la couche brute (un ticket au-delà de la conservation n'est ni vu ni écrit)."""
        return self.magasin.cles_vues(len(self.magasin.passages))

    def test_ticket_resolu_au_dela_de_la_conservation_non_ecrit(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.cles_ecrites(), {"ABC-2", "ABC-3"})                # l'ouvert ancien reste écrit
        self.assertEqual({i["issue_key"] for i in self.magasin.instantanes}, {"ABC-2", "ABC-3"})
        self.assertIn("tickets au-delà de la conservation, non écrits : 1", sortie)
        self.assertIn("Tickets : 2 ;", sortie)
        self.assertNotIn("ABC-", sortie)
        self.assertNotIn("2024", sortie)

    def test_en_anglais(self):
        code, sortie = self.lancer("export", "--language", "en")
        self.assertIn("tickets past retention, not written: 1", sortie)

    def test_aucun_ticket_au_dela_aucune_ligne(self):
        del self.faux.tickets["ABC-1"]
        code, sortie = self.lancer("export")
        self.assertNotIn("conservation", sortie)

    def test_duree_reglable(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nretention:\n  period_days: 30\n")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.cles_ecrites(), {"ABC-3"})
        self.assertIn("tickets au-delà de la conservation, non écrits : 2", sortie)

    def test_limite_de_la_duree_incluse(self):
        # résolu exactement 365 jours avant AUJOURDHUI (2026-10-04) : encore dans la règle
        self.faux.tickets["ABC-2"]["resolutiondate"] = "2025-10-04T10:30:00.000+0200"
        self.lancer("export")
        self.assertIn("ABC-2", self.cles_ecrites())
        self.faux.tickets["ABC-2"]["resolutiondate"] = "2025-10-03T10:30:00.000+0200"
        self.lancer("export")
        self.assertNotIn("ABC-2", self.cles_ecrites())

    def test_duree_au_dela_d_un_an_refusee_avant_tout_appel(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nretention:\n  period_days: 366\n")
        code, sortie = self.lancer("export")
        self.assertNotEqual(code, 0)
        self.assertIn("retention.period_days", str(code) + sortie)
        self.assertNotIn("366", str(code) + sortie)
        self.assertEqual((self.faux.requetes, self.faux.appels_get), ([], []))
        self.assertEqual(self.magasin.passages, [])

    def test_les_equipes_du_ticket_ecarte_ne_comptent_pas(self):
        """Un ticket non écrit n'entre dans aucun contrôle d'équipe de l'export."""
        (self.ws / "Flux-Lab" / "organisation.yaml").write_text(
            REFERENTIEL, encoding="utf-8")
        self.faux.tickets["ABC-1"][CHAMP] = [objet(9)]
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("inconnues", sortie)


if __name__ == "__main__":
    unittest.main()
