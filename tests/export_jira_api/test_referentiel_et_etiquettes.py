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

    def exporter_code(self, *extra: str, nom: str = "api.csv"):
        chemin = self.ws / nom
        code, sortie = self.lancer("export", "--output", str(chemin), *extra)
        return code, sortie, chemin


class TraductionParReferentiel(BaseAssets):
    def test_le_referentiel_traduit_une_colonne_par_equipe(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        code, sortie, chemin = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        lignes = self.lignes(chemin)
        i = lignes[0].index("Team")
        equipes = {l[0]: l[i:i + 2] for l in lignes[1:]}
        self.assertEqual(equipes["ABC-1"], ["Equipe A", ""])
        self.assertEqual(equipes["ABC-2"], ["Equipe B", "Equipe C"])
        self.assertEqual(equipes["ABC-3"], [INCONNUE, ""])
        self.assertEqual(equipes["ABC-4"], [INCONNUE, INCONNUE])          # ordre de l'API conservé

    def test_identifiants_inconnus_comptes_et_listes_sans_nom_ni_cle(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertIn("Équipes inconnues : 3 identifiant(s) distinct(s) absent(s) du référentiel, 2 ticket(s) concerné(s)", sortie)
        self.assertIn("4 ; 5 ; 6", sortie)                                 # liste triée des identifiants
        for interdit in ("Equipe", "ABC-", "ws-secret", "Site 1", "Departement", self.url, JETON):
            self.assertNotIn(interdit, sortie)

    def test_identifiants_inconnus_en_anglais(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        code, sortie, _ = self.exporter_code("--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Unknown teams: 3 distinct identifier(s) missing from the referential, 2 ticket(s) affected", sortie)
        self.assertIn("4; 5; 6", sortie)

    def test_referentiel_complet_aucun_message_de_completion(self):
        self.ecrire("organisation.yaml", REFERENTIEL.replace("jira_team_ids: ['3']", "jira_team_ids: ['3', '4', '5', '6']"))
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        for absent in ("inconnues", "Compléter", "dépréciée"):
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
            code, sortie, chemin = self.exporter_code("--language", langue, nom=f"{langue}.csv")
            self.assertEqual(code, 0, sortie)
            self.assertIn(INCONNUE, chemin.read_text(encoding="utf-8-sig"))

    def test_referentiel_illisible_arrete_l_export_sans_valeur(self):
        for contenu in ("sites: [pas, un", REFERENTIEL + "owner: Une Personne\n"):
            with self.subTest(contenu=contenu[:12]):
                self.ecrire("organisation.yaml", contenu)
                code, sortie, chemin = self.exporter_code()
                self.assertNotEqual(code, 0)
                self.assertFalse(chemin.exists())
                self.assertEqual(self.faux.requetes, [])                     # arrêt avant tout appel à Jira
                self.assertNotIn("Une Personne", str(code) + sortie)

    def test_referentiel_avec_identifiant_sous_deux_equipes_refuse(self):
        self.ecrire("organisation.yaml", REFERENTIEL.replace("jira_team_ids: ['2']", "jira_team_ids: ['1']"))
        code, sortie, chemin = self.exporter_code()
        self.assertNotEqual(code, 0)
        self.assertFalse(chemin.exists())

    def test_referentiel_absent_et_libelles_utilisables_comme_avant(self):
        self.faux.tickets = {cle: dict(t) for cle, t in TICKETS.items()}
        code, sortie, chemin = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertTrue(chemin.exists())

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
        code, sortie, chemin = self.exporter_code("--strict-teams")
        self.assertEqual(code, 3, sortie)
        self.assertTrue(chemin.exists())
        self.assertIn("Fichier écrit", sortie)
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
        self.assertIn("référentiel d'organisation (3 identifiant(s))", sortie)
        for interdit in ("Equipe", "ws-secret", "equipes-assets"):
            self.assertNotIn(interdit, sortie)
        code, sortie = self.lancer("diagnose", "--language", "en")
        self.assertIn("organisation referential (3 identifier(s))", sortie)

    def test_diagnose_referentiel_illisible_arrete(self):
        self.ecrire("organisation.yaml", "sites: [pas, un")
        code, sortie = self.lancer("diagnose")
        self.assertNotEqual(code, 0)


class RepliSurLaTable(BaseAssets):
    """Tant que le référentiel n'a aucun identifiant, l'ancienne table est lue, avec l'avertissement de dépréciation."""

    AVERTISSEMENT = "table des équipes dépréciée : compléter jira_team_ids du référentiel d'organisation"

    def test_repli_sur_la_table_sans_referentiel(self):
        self.ecrire("equipes-assets.yaml", TABLE)
        code, sortie, chemin = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertIn(self.AVERTISSEMENT, sortie)
        i = self.lignes(chemin)[0].index("Team")
        self.assertEqual(self.lignes(chemin)[1][i], "Table A")

    def test_repli_sur_la_table_avec_un_referentiel_sans_identifiant(self):
        self.ecrire("organisation.yaml", SANS_IDENTIFIANT)
        self.ecrire("equipes-assets.yaml", TABLE)
        code, sortie, chemin = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertIn(self.AVERTISSEMENT, sortie)
        self.assertEqual(self.lignes(chemin)[1][self.lignes(chemin)[0].index("Team")], "Table A")

    def test_avertissement_en_anglais(self):
        self.ecrire("equipes-assets.yaml", TABLE)
        code, sortie, _ = self.exporter_code("--language", "en")
        self.assertIn("team table deprecated: fill jira_team_ids in the organisation referential", sortie)

    def test_les_deux_presents_le_referentiel_seul_est_utilise(self):
        self.ecrire("organisation.yaml", REFERENTIEL)
        self.ecrire("equipes-assets.yaml", TABLE)
        code, sortie, chemin = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertIn(self.AVERTISSEMENT, sortie)                          # même avertissement : supprimer l'ancienne table
        lignes = self.lignes(chemin)
        self.assertEqual(lignes[1][lignes[0].index("Team")], "Equipe A")   # jamais « Table A »
        self.assertNotIn("Table", chemin.read_text(encoding="utf-8-sig"))
        self.assertIn("absent(s) du référentiel", sortie)                  # les inconnus se lisent contre le référentiel

    def test_table_partielle_les_inconnus_apres_l_avertissement(self):
        self.ecrire("equipes-assets.yaml", "equipes: {'1': Table A, '2': Table B, '3': Table C}\n")
        code, sortie, chemin = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertIn(INCONNUE, chemin.read_text(encoding="utf-8-sig"))
        self.assertIn("Équipes inconnues : 3 identifiant(s) distinct(s) absent(s) de la table", sortie)
        self.assertLess(sortie.index(self.AVERTISSEMENT), sortie.index("Équipes inconnues"))
        self.assertIn("4 ; 5 ; 6", sortie)

    def test_table_complete_avertissement_sans_completion(self):
        self.ecrire("equipes-assets.yaml", TABLE)
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertIn(self.AVERTISSEMENT, sortie)
        self.assertNotIn("Complétez", sortie)
        self.assertNotIn("inconnues", sortie)

    def test_strict_teams_table_partielle_et_complete(self):
        self.ecrire("equipes-assets.yaml", "equipes: {'1': A}\n")
        self.assertEqual(self.exporter_code("--strict-teams")[0], 3)
        self.ecrire("equipes-assets.yaml", TABLE)
        self.assertEqual(self.exporter_code("--strict-teams")[0], 0)

    def test_pas_d_avertissement_quand_les_libelles_suffisent(self):
        self.ecrire("equipes-assets.yaml", TABLE)
        self.faux.tickets = {"ABC-1": champs(*ETAT_NEUF, equipes=["Equipe A"])}
        code, sortie, _ = self.exporter_code()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("dépréciée", sortie)

    def test_diagnose_par_la_table_en_repli(self):
        self.ecrire("equipes-assets.yaml", TABLE)
        code, sortie = self.lancer("diagnose")
        self.assertEqual(code, 0, sortie)
        self.assertIn("par la table equipes-assets.yaml (6 identifiant(s))", sortie)


class AucuneSource(BaseAssets):
    def verifier_refus(self, sortie: str, chemin):
        self.assertFalse(chemin.exists())
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
    def reglages_avec(self, extra: str = DECLAREES, verification: bool = True) -> None:
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n"
                             + (f"export_verification_field: {VERIFICATION}\n" if verification else "") + extra)

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


class ColonnesEtiquettesEtVersions(BaseEtiquettes):
    def setUp(self):
        super().setUp()
        self.faux.tickets = {}

    def test_ordre_des_colonnes_verification_etiquettes_versions_puis_liens(self):
        self.reglages_avec()
        self.ticket("ABC-1", ["cy-a", "um-legal"], [SECRET_VERSION], liens=[
            {"type": {"name": "Blocks"}, "outwardIssue": {"key": "ABC-2"}}])
        self.ticket("ABC-2")
        entete = self.lignes(self.exporter())[0]
        iv = entete.index("Verification Required")
        self.assertEqual(entete[iv + 1:iv + 4], ["Declared Label", "Declared Label", "Fix Version"])
        self.assertEqual(entete[iv + 4], "Outward issue link (Blocks)")
        self.assertEqual(entete.count("Declared Label"), 2)
        self.assertEqual(entete.count("Fix Version"), 1)

    def test_entetes_anglais_dans_les_deux_langues_et_jamais_labels_ni_po(self):
        self.reglages_avec()
        self.ticket("ABC-1", ["cy-a"], ["v1"])
        for langue in ("fr", "en"):
            chemin = self.ws / f"{langue}.csv"
            code, sortie = self.lancer("export", "--output", str(chemin), "--language", langue)
            self.assertEqual(code, 0, sortie)
            entete = self.lignes(chemin)[0]
            self.assertIn("Declared Label", entete)
            self.assertIn("Fix Version", entete)
            for interdit in ("Labels", "labels", "Label", "PO", "Étiquette", "Version corrigée"):
                self.assertNotIn(interdit, entete)

    def test_cellules_repetees_selon_le_maximum_d_un_ticket(self):
        self.reglages_avec()
        self.ticket("ABC-1", ["cy-a", "cy-b", "um-hotfix"], ["v1", "v2"])
        self.ticket("ABC-2", ["cy-b"], ["v3"])
        self.ticket("ABC-3", [], [])
        lignes = self.lignes(self.exporter())
        entete = lignes[0]
        i, j = entete.index("Declared Label"), entete.index("Fix Version")
        self.assertEqual(entete.count("Declared Label"), 3)
        par_cle = {l[0]: l for l in lignes[1:]}
        self.assertEqual(par_cle["ABC-1"][i:i + 3], ["cy-a", "cy-b", "um-hotfix"])
        self.assertEqual(par_cle["ABC-2"][i:i + 3], ["cy-b", "", ""])
        self.assertEqual(par_cle["ABC-3"][i:i + 3], ["", "", ""])
        self.assertEqual(par_cle["ABC-1"][j:j + 2], ["v1", "v2"])
        self.assertEqual(par_cle["ABC-2"][j:j + 2], ["v3", ""])

    def test_seules_les_etiquettes_declarees_sont_ecrites(self):
        self.reglages_avec()
        self.ticket("ABC-1", [SECRET_ETIQUETTE, "cy-a", "ZZ-AUTRE-ETIQUETTE"])
        chemin = self.ws / "api.csv"
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 0, sortie)
        ligne = self.lignes(chemin)[1]
        self.assertIn("cy-a", ligne)
        for texte in (sortie, chemin.read_text(encoding="utf-8-sig")):
            self.assertNotIn(SECRET_ETIQUETTE, texte)
            self.assertNotIn("ZZ-AUTRE-ETIQUETTE", texte)

    def test_champ_labels_demande_seulement_avec_des_etiquettes_declarees(self):
        self.ticket("ABC-1", ["cy-a"])
        self.reglages_avec(extra="")
        self.exporter()
        self.assertNotIn("labels", self.champs_demandes())
        self.faux.requetes.clear()
        self.reglages_avec()
        self.exporter()
        self.assertIn("labels", self.champs_demandes())

    def test_fixversions_toujours_demande_et_aucun_champ_de_personne(self):
        self.ticket("ABC-1")
        for extra in ("", DECLAREES):
            self.faux.requetes.clear()
            self.reglages_avec(extra=extra)
            self.exporter()
            demandes = self.champs_demandes()
            self.assertIn("fixVersions", demandes)
            for interdit in ("summary", "assignee", "reporter", "creator", "description", "comment"):
                self.assertNotIn(interdit, demandes)

    def test_sans_bloc_aucune_colonne_d_etiquette_meme_si_le_ticket_en_porte(self):
        self.reglages_avec(extra="")
        self.ticket("ABC-1", ["cy-a", SECRET_ETIQUETTE], [SECRET_VERSION])
        chemin = self.exporter()
        entete = self.lignes(chemin)[0]
        self.assertNotIn("Declared Label", entete)
        self.assertNotIn(SECRET_ETIQUETTE, chemin.read_text(encoding="utf-8-sig"))
        self.assertNotIn("cy-a", chemin.read_text(encoding="utf-8-sig"))

    def test_sans_version_aucune_colonne_de_version(self):
        self.reglages_avec()
        self.ticket("ABC-1", ["cy-a"])
        self.assertNotIn("Fix Version", self.lignes(self.exporter())[0])

    def test_console_ni_etiquette_ni_version_ni_cle(self):
        self.reglages_avec()
        self.ticket("ABC-1", ["cy-a", "cy-extra", SECRET_ETIQUETTE, "um-legal", "um-hotfix"], [SECRET_VERSION])
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertEqual(code, 0, sortie)
        for chaine in ("cy-a", "cy-extra", "um-legal", "um-hotfix", SECRET_ETIQUETTE, SECRET_VERSION, "ABC-", "Equipe"):
            self.assertNotIn(chaine, sortie)

    def test_bloc_invalide_arrete_avant_tout_appel(self):
        self.reglages_avec(extra=DECLAREES.replace("cy-b", "xx-b"))
        self.ticket("ABC-1")
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertNotEqual(code, 0)
        self.assertIn("declared_labels", str(code) + sortie)
        self.assertNotIn("xx-b", str(code) + sortie)
        self.assertEqual(self.faux.requetes, [])
        self.assertFalse((self.ws / "api.csv").exists())


class EtiquettesProches(BaseEtiquettes):
    def setUp(self):
        super().setUp()
        self.faux.tickets = {}
        self.reglages_avec()

    def sortie(self, *extra: str) -> str:
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"), *extra)
        self.assertEqual(code, 0, sortie)
        return sortie

    def test_etiquette_renommee_comptee_sans_texte(self):
        self.ticket("ABC-1", ["cy-renommee"])
        sortie = self.sortie()
        self.assertIn("étiquettes non déclarées au préfixe déclaré : 1", sortie)
        self.assertNotIn("cy-renommee", sortie)

    def test_en_anglais(self):
        self.ticket("ABC-1", ["um-renomme"])
        sortie = self.sortie("--language", "en")
        self.assertIn("undeclared labels with a declared prefix: 1", sortie)
        self.assertNotIn("um-renomme", sortie)

    def test_distinctes_et_tickets(self):
        self.ticket("ABC-1", ["cy-x", "cy-y"])
        self.ticket("ABC-2", ["cy-x"])
        self.ticket("ABC-3", ["autre"])                                      # sans préfixe déclaré : non comptée
        sortie = self.sortie()
        self.assertIn("étiquettes non déclarées au préfixe déclaré : 2", sortie)         # distinctes
        self.assertIn("tickets qui les portent : 2", sortie)                                # tickets qui les portent

    def test_etiquette_declaree_non_comptee(self):
        self.ticket("ABC-1", ["cy-a", "um-legal"])
        self.assertNotIn("préfixe déclaré", self.sortie())

    def test_calcul_des_effectifs(self):
        from export_jira_api import construire_csv
        tickets = [{"key": "ABC-1", "fields": {"labels": ["cy-x", "cy-y", "cy-a"]}},
                   {"key": "ABC-2", "fields": {"labels": ["cy-x"]}}, {"key": "ABC-3", "fields": {"labels": ["z"]}}]
        _, effectifs = construire_csv(tickets, None, "Team", etiquettes={
            "cycle": {"prefix": "cy-", "labels": ["cy-a"]}})
        self.assertEqual((effectifs["proches_distinctes"], effectifs["proches_tickets"]), (2, 2))


class DeuxEtiquettesUpMerge(BaseEtiquettes):
    def setUp(self):
        super().setUp()
        self.faux.tickets = {}
        self.reglages_avec()

    def test_deux_etiquettes_comptees_sans_cle(self):
        self.ticket("ABC-1", ["um-legal", "um-hotfix"])
        self.ticket("ABC-2", ["um-legal"])
        self.ticket("ABC-3", ["um-hotfix", "cy-a"])
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertEqual(code, 0, sortie)
        self.assertIn("éléments d'up-merge à deux étiquettes : 1", sortie)
        self.assertNotIn("ABC-", sortie)
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"), "--language", "en")
        self.assertIn("up-merge items with two labels: 1", sortie)

    def test_aucun_ticket_a_deux_etiquettes_aucune_ligne(self):
        self.ticket("ABC-1", ["um-legal"])
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertNotIn("up-merge", sortie)

    def test_la_ligne_du_fichier_garde_les_deux_etiquettes(self):
        self.ticket("ABC-1", ["um-legal", "um-hotfix"])
        lignes = self.lignes(self.exporter())
        self.assertIn("um-legal", lignes[1])
        self.assertIn("um-hotfix", lignes[1])


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

    def cles_ecrites(self, chemin) -> set[str]:
        return {l[0] for l in self.lignes(chemin)[1:]}

    def test_ticket_resolu_au_dela_de_la_conservation_non_ecrit(self):
        chemin = self.ws / "api.csv"
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.cles_ecrites(chemin), {"ABC-2", "ABC-3"})                # l'ouvert ancien reste écrit
        self.assertIn("tickets au-delà de la conservation, non écrits : 1", sortie)
        self.assertIn("Tickets : 2 ;", sortie)
        self.assertNotIn("ABC-", sortie)
        self.assertNotIn("2024", sortie)

    def test_en_anglais(self):
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"), "--language", "en")
        self.assertIn("tickets past retention, not written: 1", sortie)

    def test_aucun_ticket_au_dela_aucune_ligne(self):
        del self.faux.tickets["ABC-1"]
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertNotIn("conservation", sortie)

    def test_duree_reglable(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nretention:\n  period_days: 30\n")
        chemin = self.ws / "api.csv"
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.cles_ecrites(chemin), {"ABC-3"})
        self.assertIn("tickets au-delà de la conservation, non écrits : 2", sortie)

    def test_limite_de_la_duree_incluse(self):
        # résolu exactement 365 jours avant AUJOURDHUI (2026-10-04) : encore dans la règle
        self.faux.tickets["ABC-2"]["resolutiondate"] = "2025-10-04T10:30:00.000+0200"
        chemin = self.ws / "api.csv"
        self.lancer("export", "--output", str(chemin))
        self.assertIn("ABC-2", self.cles_ecrites(chemin))
        self.faux.tickets["ABC-2"]["resolutiondate"] = "2025-10-03T10:30:00.000+0200"
        self.lancer("export", "--output", str(chemin))
        self.assertNotIn("ABC-2", self.cles_ecrites(chemin))

    def test_duree_au_dela_d_un_an_refusee_avant_tout_appel(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nretention:\n  period_days: 366\n")
        chemin = self.ws / "api.csv"
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertNotEqual(code, 0)
        self.assertIn("retention.period_days", str(code) + sortie)
        self.assertNotIn("366", str(code) + sortie)
        self.assertEqual((self.faux.requetes, self.faux.appels_get), ([], []))
        self.assertFalse(chemin.exists())

    def test_les_equipes_du_ticket_ecarte_ne_comptent_pas(self):
        """Un ticket non écrit n'entre dans aucun contrôle d'équipe de l'export."""
        (self.ws / "Flux-Lab" / "organisation.yaml").write_text(
            REFERENTIEL, encoding="utf-8")
        self.faux.tickets["ABC-1"][CHAMP] = [objet(9)]
        code, sortie = self.lancer("export", "--output", str(self.ws / "api.csv"))
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("inconnues", sortie)


if __name__ == "__main__":
    unittest.main()
