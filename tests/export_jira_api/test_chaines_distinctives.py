"""Chaînes distinctives de export_jira_api.py (change jira-gdpr-alignment, tâche 2.4).

    uv run --with pyyaml --with requests python -m unittest discover -s tests/export_jira_api -v

Spécifications : jira-flow-labels (« Only declared labels are stored », « Jira labels only »), jira-flow-organisation
(« Names stay in the flow folder »), jira-flow-export (rien de sensible imprimé).
Le faux serveur porte, sur chaque ticket, une étiquette et une version corrective distinctives (champs API labels et
fixVersions) ; une équipe, une clé et un nom de fichier distinctifs complètent le jeu. Aucune étiquette ni version ne doit
paraître dans la console. L'export ne demande les étiquettes que si des étiquettes déclarées sont réglées et n'écrit que
celles-là ; les versions correctives sont lues à chaque export et écrites dans le fichier. Le CSV est un
fichier du dossier de flux : clés et équipes y ont leur place ; la console des contrôles ne montre ni clé, ni équipe (le nom du
fichier écrit est annoncé par l'outil, c'est le fichier demandé par l'utilisateur).
"""
import unittest

from test_export_jira_api import Base, CHAMP, EMAIL, JETON, champs

ETIQUETTE = "ZZDISTINCT-ETIQUETTE"
VERSION = "ZZDISTINCT-VERSION"
CLE = "ZZKEY-77"
EQUIPE = "ZZDISTINCT-EQUIPE"
FICHIER = "zzdistinct-fichier.csv"


class ChainesDistinctives(Base):
    def setUp(self):
        super().setUp()
        self.faux.tickets = {}
        for i in (1, 2):
            ticket = champs("Story", "Open", "To Do", "2026-09-01T16:45:00.000+0200", equipes=[EQUIPE])
            ticket["labels"] = [ETIQUETTE, "ZZDISTINCT-AUTRE-ETIQUETTE"]
            ticket["fixVersions"] = [{"name": VERSION}]
            self.faux.tickets[f"{CLE}-{i}"] = ticket

    def test_sans_etiquette_declaree_aucune_etiquette_ni_demandee_ni_imprimee_ni_ecrite(self):
        chemin = self.ws / FICHIER
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 0, sortie)
        demandes = {f for r in self.faux.requetes for f in r["fields"]}
        self.assertNotIn("labels", demandes)                       # sans bloc declared_labels : aucune étiquette demandée
        csv_ecrit = chemin.read_text(encoding="utf-8-sig")
        for nom, texte in (("console", sortie), ("CSV", csv_ecrit)):
            for chaine in (ETIQUETTE, "ZZDISTINCT-AUTRE-ETIQUETTE"):
                self.assertNotIn(chaine, texte, f"{chaine} dans {nom}")
        for entete in ("Labels", "Declared Label"):
            self.assertNotIn(entete, csv_ecrit.splitlines()[0])          # jamais l'en-tête Jira des étiquettes en clair

    def test_version_ecrite_dans_le_fichier_jamais_dans_la_console(self):
        chemin = self.ws / FICHIER
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 0, sortie)
        self.assertIn("fixVersions", {f for r in self.faux.requetes for f in r["fields"]})
        csv_ecrit = chemin.read_text(encoding="utf-8-sig")
        self.assertIn("Fix Version", csv_ecrit.splitlines()[0])
        self.assertIn(VERSION, csv_ecrit)                          # fichier du dossier de flux : la version y a sa place
        self.assertNotIn(VERSION, sortie)

    def test_etiquette_declaree_dans_le_fichier_les_autres_nulle_part(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n"
                             f"declared_labels:\n  cycle:\n    prefix: ZZDISTINCT-\n    labels: [{ETIQUETTE}]\n")
        chemin = self.ws / FICHIER
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 0, sortie)
        csv_ecrit = chemin.read_text(encoding="utf-8-sig")
        self.assertIn(ETIQUETTE, csv_ecrit)
        self.assertNotIn("ZZDISTINCT-AUTRE-ETIQUETTE", csv_ecrit)
        for chaine in (ETIQUETTE, "ZZDISTINCT-AUTRE-ETIQUETTE", VERSION):
            self.assertNotIn(chaine, sortie)

    def test_console_sans_cle_equipe_nom_de_fichier_ni_secret(self):
        chemin = self.ws / FICHIER
        code, sortie = self.lancer("export", "--output", str(chemin))
        self.assertEqual(code, 0, sortie)
        for chaine in (CLE, EQUIPE, JETON, EMAIL, self.url, CHAMP):     # le nom du fichier écrit, lui, est annoncé
            self.assertNotIn(chaine, sortie)
        # Dans le fichier du dossier de flux, clés et équipes sont permises.
        csv_ecrit = chemin.read_text(encoding="utf-8-sig")
        self.assertIn(CLE, csv_ecrit)
        self.assertIn(EQUIPE, csv_ecrit)

    def test_controle_des_equipes_inconnues_ne_montre_ni_cle_ni_equipe_ni_etiquette(self):
        """Champ d'équipe en objets Assets sans référentiel : la console reste muette sur clés, étiquettes, versions."""
        for ticket in self.faux.tickets.values():
            ticket[CHAMP] = [{"workspaceId": "ws-secret", "id": "ws-secret:9", "objectId": "9"}]
        code, sortie = self.lancer("export", "--output", str(self.ws / FICHIER))
        for chaine in (CLE, EQUIPE, ETIQUETTE, VERSION, JETON):
            self.assertNotIn(chaine, sortie)
        self.assertEqual(self.faux.appels_get, [])                           # aucun appel à l'API Assets ni autre lecture

    def test_diagnose_et_fields_sans_etiquette_ni_version_ni_cle(self):
        for argv in (("diagnose",), ("fields", "--search", "team")):
            code, sortie = self.lancer(*argv)
            for chaine in (CLE, EQUIPE, ETIQUETTE, VERSION, JETON):
                self.assertNotIn(chaine, sortie, argv)

    def test_rapport_d_usage_des_etiquettes_sans_texte_d_etiquette(self):
        """Étiquette déclarée du rôle cycle + étiquette proche non déclarée : la console ne donne que des nombres."""
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_team_field: {CHAMP}\n"
                             f"declared_labels:\n  cycle:\n    prefix: ZZDISTINCT-\n    labels: [{ETIQUETTE}]\n")
        code, sortie = self.lancer("export", "--output", str(self.ws / FICHIER))
        self.assertEqual(code, 0, sortie)
        self.assertIn("étiquettes non déclarées au préfixe déclaré : 1", sortie)
        for chaine in (ETIQUETTE, "ZZDISTINCT-AUTRE-ETIQUETTE", VERSION):
            self.assertNotIn(chaine, sortie)


if __name__ == "__main__":
    unittest.main()
