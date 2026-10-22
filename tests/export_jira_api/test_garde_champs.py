"""Garde des champs de l'export (jira-flow-export, « No sensitive field requested or printed » ; design D3, D19).

    bash tests/run_all.sh export_jira_api </dev/null

Faux serveur et données inventées de test_export_jira_api.py, réutilisés tels quels. Ces tests épinglent ce que l'export
demande à Jira et ce qu'il enregistre : aucun champ de personne, jamais d'étiquette ni de version (database-only, D5), jamais de
valeur PO, aucun fichier écrit.
"""
import re
import unittest

from test_export_jira_api import Base, CHAMP

POINTS = "customfield_10003"
VERIFICATION = "customfield_10004"

# Champs de personne ou de texte libre : jamais demandés, quel que soit le réglage.
INTERDITS = ("summary", "description", "creator", "reporter", "assignee", "comment", "comments", "worklog", "watches",
             "votes", "lastViewed", "displayName", "emailAddress")
# Tous les réglages optionnels pris en charge par l'export, actifs ensemble.
TOUS_LES_REGLAGES = (f"jql_export: project = ABC\nexport_team_field: {CHAMP}\nexport_team_header: Team\n"
                     f"export_verification_field: {VERIFICATION}\nexport_verification_header: Verification Required\n"
                     f"export_points_field: {POINTS}\nexport_timezone: Europe/Paris\n")


class GardeChamps(Base):
    def champs_demandes(self) -> set[str]:
        return {f for r in self.faux.requetes for f in r["fields"]}

    def verifier_aucun_champ_interdit(self):
        demandes = self.champs_demandes()
        self.assertTrue(demandes)                         # des champs sont bien demandés : la garde ne passe pas à vide
        for interdit in INTERDITS:
            self.assertNotIn(interdit, demandes)
        for champ in demandes:                            # aucun champ d'utilisateur, même sous un autre nom
            self.assertIsNone(re.search(r"user|people|person|owner|\bpo\b", champ, re.I), champ)

    def test_reglages_par_defaut_aucun_champ_interdit(self):
        self.exporter()
        self.verifier_aucun_champ_interdit()

    def test_sans_champ_optionnel_aucun_champ_interdit(self):
        self.ecrire_reglages("jql_export: project = ABC\n")
        self.exporter()
        self.verifier_aucun_champ_interdit()

    def test_avec_chaque_reglage_optionnel_aucun_champ_interdit(self):
        for reglage in (f"export_team_field: {CHAMP}\n", f"export_verification_field: {VERIFICATION}\n",
                        f"export_points_field: {POINTS}\n", "export_timezone: Europe/Paris\n"):
            with self.subTest(reglage=reglage.split(":")[0]):
                self.faux.requetes.clear()
                self.ecrire_reglages(f"jql_export: project = ABC\n{reglage}")
                self.exporter()
                self.verifier_aucun_champ_interdit()

    def test_avec_tous_les_reglages_optionnels_aucun_champ_interdit(self):
        self.ecrire_reglages(TOUS_LES_REGLAGES)
        instantanes = self.exporter()
        self.verifier_aucun_champ_interdit()
        demandes = self.champs_demandes()                 # les réglages sont bien lus : leurs champs sont demandés
        for voulu in (CHAMP, POINTS):
            self.assertIn(voulu, demandes)
        self.assertNotIn(VERIFICATION, demandes)          # la colonne de vérification n'est plus demandée (Q7 (b))
        self.assertNotIn("PO", repr(instantanes))

    def test_liste_de_champs_de_points_aucun_champ_interdit(self):
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_points_field: [{POINTS}, customfield_10005]\n")
        self.exporter()
        self.verifier_aucun_champ_interdit()

    def test_labels_et_versions_jamais_demandes_avec_ou_sans_bloc_d_etiquettes_declarees(self):
        declarees = "declared_labels:\n  cycle:\n    prefix: label-\n    labels: [label-a, label-b]\n"
        for reglages in (None, TOUS_LES_REGLAGES, TOUS_LES_REGLAGES + declarees):
            with self.subTest(reglages=("defaut" if reglages is None else "tous")):
                self.faux.requetes.clear()
                self.ecrire_reglages(reglages)
                self.exporter()
                self.assertNotIn("labels", self.champs_demandes())
                self.assertNotIn("fixVersions", self.champs_demandes())
                self.verifier_aucun_champ_interdit()

    def test_aucune_valeur_po_ni_etiquette_dans_les_instantanes(self):
        for reglages in (None, TOUS_LES_REGLAGES):
            with self.subTest(reglages="defaut" if reglages is None else "tous"):
                self.ecrire_reglages(reglages)
                for instantane in self.exporter().values():
                    for cle in instantane:
                        self.assertIsNone(re.search(r"\b(po|product_owner|labels?|versions?|owner|person)\b", cle, re.I), cle)

    def test_aucune_valeur_po_meme_avec_un_reglage_de_champ_po(self):
        # Le réglage export_po_field est refusé par le groupe 3 ; ici, quel que soit le résultat, aucune valeur PO n'est enregistrée.
        self.ecrire_reglages(f"jql_export: project = ABC\nexport_po_field: {CHAMP}\n")
        self.lancer("export")
        self.assertNotIn("PO", repr(self.magasin.instantanes))

    def test_aucun_fichier_n_est_ecrit(self):
        for reglages in (None, TOUS_LES_REGLAGES):
            with self.subTest(reglages="defaut" if reglages is None else "tous"):
                self.ecrire_reglages(reglages)
                self.exporter()
                self.assertEqual([p.name for p in self.ws.rglob("*") if p.is_file()], ["flux.yaml"])


if __name__ == "__main__":
    unittest.main()
