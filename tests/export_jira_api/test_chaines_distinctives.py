"""Chaînes distinctives de export_jira_api.py (change jira-gdpr-alignment, tâche 2.4).

    uv run --with pyyaml --with requests python -m unittest discover -s tests/export_jira_api -v

Spécifications : jira-flow-labels (« Only declared labels are stored », « Jira labels only »), jira-flow-organisation
(« Names stay in the flow folder »), jira-flow-export (rien de sensible imprimé).
Le faux serveur porte, sur chaque ticket, une étiquette et une version corrective distinctives (champs API labels et
fixVersions) ; une équipe et une clé distinctives complètent le jeu. L'export (database-only) ne demande ni les étiquettes ni les
versions, n'en enregistre aucune et n'en imprime aucune ; clés et équipes ont leur place dans les instantanés de la base, jamais dans
la console des contrôles.
"""
import unittest

from test_export_jira_api import Base, CHAMP, EMAIL, JETON, champs

ETIQUETTE = "ZZDISTINCT-ETIQUETTE"
VERSION = "ZZDISTINCT-VERSION"
CLE = "ZZKEY-77"
EQUIPE = "ZZDISTINCT-EQUIPE"


class ChainesDistinctives(Base):
    def setUp(self):
        super().setUp()
        self.faux.tickets = {}
        for i in (1, 2):
            ticket = champs("Story", "Open", "To Do", "2026-09-01T16:45:00.000+0200", equipes=[EQUIPE])
            ticket["labels"] = [ETIQUETTE, "ZZDISTINCT-AUTRE-ETIQUETTE"]
            ticket["fixVersions"] = [{"name": VERSION}]
            self.faux.tickets[f"{CLE}-{i}"] = ticket

    def test_aucune_etiquette_ni_version_ni_demandee_ni_imprimee_ni_enregistree(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        demandes = {f for r in self.faux.requetes for f in r["fields"]}
        self.assertNotIn("labels", demandes)
        self.assertNotIn("fixVersions", demandes)
        enregistre = repr(self.magasin.instantanes)
        for nom, texte in (("console", sortie), ("couche brute", enregistre)):
            for chaine in (ETIQUETTE, "ZZDISTINCT-AUTRE-ETIQUETTE", VERSION):
                self.assertNotIn(chaine, texte, f"{chaine} dans {nom}")

    def test_etiquette_declaree_non_demandee_non_plus(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n"
                             f"declared_labels:\n  cycle:\n    prefix: ZZDISTINCT-\n    labels: [{ETIQUETTE}]\n")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("labels", {f for r in self.faux.requetes for f in r["fields"]})
        for chaine in (ETIQUETTE, "ZZDISTINCT-AUTRE-ETIQUETTE", VERSION):
            self.assertNotIn(chaine, sortie)
            self.assertNotIn(chaine, repr(self.magasin.instantanes))

    def test_console_sans_cle_equipe_ni_secret(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        for chaine in (CLE, EQUIPE, JETON, EMAIL, self.url, CHAMP):
            self.assertNotIn(chaine, sortie)
        # Dans la couche brute de la base, clés et équipes sont permises.
        enregistre = repr(self.magasin.instantanes)
        self.assertIn(CLE, enregistre)
        self.assertIn(EQUIPE, enregistre)

    def test_controle_des_equipes_inconnues_ne_montre_ni_cle_ni_equipe_ni_etiquette(self):
        """Champ d'équipe en objets Assets sans référentiel : la console reste muette sur clés, étiquettes, versions."""
        for ticket in self.faux.tickets.values():
            ticket[CHAMP] = [{"workspaceId": "ws-secret", "id": "ws-secret:9", "objectId": "9"}]
        code, sortie = self.lancer("export")
        for chaine in (CLE, EQUIPE, ETIQUETTE, VERSION, JETON):
            self.assertNotIn(chaine, sortie)
        self.assertEqual(self.faux.appels_get, [])                           # aucun appel à l'API Assets ni autre lecture

    def test_diagnose_et_fields_sans_etiquette_ni_version_ni_cle(self):
        for argv in (("diagnose",), ("fields", "--search", "team")):
            code, sortie = self.lancer(*argv)
            for chaine in (CLE, EQUIPE, ETIQUETTE, VERSION, JETON):
                self.assertNotIn(chaine, sortie, argv)

if __name__ == "__main__":
    unittest.main()
