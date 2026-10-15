"""
Chaînes distinctives de flow_retention.py (change jira-gdpr-alignment, tâche 2.4, part « retention »).

Spécification : jira-flow-retention (« Retention tool output and session refusal », scénario « Distinctive names absent »). Les
fixtures portent une chaîne distinctive dans chaque clé, équipe, étiquette (déclarée et de sauvegarde), version et nom de fichier ;
aucune ne paraît dans la sortie de `check` ni de `purge` (essai, application, refus, erreur), dans les deux langues.
"""
import json
import unittest

from aide_flow_retention import AUJOURDHUI, Espace, FausseBase, jours_avant

CLE = "ZZDISTINCT-KEY-77"
EQUIPE = "ZZDISTINCT-EQUIPE"
ETIQUETTE = "zzdistinctetiquette"
VERSION = "ZZDISTINCT-VERSION-9"
FICHIER = "zzdistinct-fichier"
TOUTES = (CLE, EQUIPE, ETIQUETTE, VERSION, FICHIER, "ZZDISTINCT", "zzdistinct")


class ChainesDistinctives(Espace):
    def setUp(self):
        super().setUp()
        self.ecrire_reglages(f"retention:\n  backup_label: {ETIQUETTE}\n")
        corps = f"Issue key,Status,Declared Label,Fix Version\n{CLE}-1,Done,{ETIQUETTE},{VERSION}\n"
        self.fichier(self.exports, f"api-{FICHIER}-vieux.csv", 500, corps)
        self.fichier(self.exports, f"api-{FICHIER}-recent.csv", 2, corps)
        self.fichier(self.exports, f"{FICHIER}-manuel.csv", 3, f"Issue key,Summary\n{CLE}-2,{EQUIPE}\n")
        self.fichier(self.tableaux, f"points-{FICHIER}-2024-01-01.json", 500, json.dumps([{"equipe": EQUIPE}]))
        self.fichier(self.tableaux, f"tableau-flux-{FICHIER}-2024-01-01.html", 500, "<html></html>")
        self.fichier(self.rapports, f"flux-{FICHIER}-2024-01-01.md", 500, f"# {EQUIPE}\n")
        self.cache({f"{CLE}-3": {"termine": True, "resolu": "2024-03-01T10:00:00.000+0000", "transitions": [],
                                 "versions": [["2024-03-01T10:00:00.000+0000", "add", VERSION]],
                                 "etiquettes": [["2024-03-01T10:00:00.000+0000", "add", ETIQUETTE]]}})
        self.sauvegarde(AUJOURDHUI, ETIQUETTE)
        self.sauvegarde(jours_avant(60), ETIQUETTE)
        self.sauvegarde(jours_avant(60), "zzdistinctautre")
        self.etat_hors_site(2)

    def verifier(self, *morceaux):
        tout = "\n".join(morceaux)
        for chaine in TOUTES:
            self.assertNotIn(chaine, tout)

    def test_check_essai_et_application_dans_les_deux_langues(self):
        for langue in ("fr", "en"):
            for commande in (("check",), ("purge",), ("purge", "--apply")):
                with self.subTest(langue=langue, commande=commande):
                    code, sortie, erreur, _ = self.lancer(*commande, "--language", langue, base=FausseBase(4, jours_avant(500)))
                    self.assertIn(code, (0, 4), erreur)
                    self.assertTrue(sortie.strip())
                    self.verifier(sortie, erreur)
                    self.reconstituer()

    def reconstituer(self):
        """L'application supprime des éléments : on les remet pour la passe suivante."""
        if not (self.exports / f"api-{FICHIER}-vieux.csv").exists():
            self.fichier(self.exports, f"api-{FICHIER}-vieux.csv", 500, "Issue key,Status\n")
            self.fichier(self.exports, f"{FICHIER}-manuel.csv", 3, "Issue key,Summary\n")
            self.fichier(self.tableaux, f"points-{FICHIER}-2024-01-01.json", 500, "[]")
            self.cache({f"{CLE}-3": {"termine": True, "resolu": "2024-03-01T10:00:00.000+0000", "transitions": []}})
            dossier = self.sauvegardes / f"db-{jours_avant(60).isoformat()}-{ETIQUETTE}"
            dossier.mkdir(exist_ok=True)
            (dossier / "flow.dump").write_bytes(b"x")

    def test_refus_sans_sauvegarde_du_jour(self):
        import shutil
        shutil.rmtree(self.sauvegardes / f"db-{AUJOURDHUI.isoformat()}-{ETIQUETTE}")
        for langue in ("fr", "en"):
            code, sortie, erreur, _ = self.lancer("purge", "--apply", "--language", langue)
            self.assertEqual(code, 3)
            self.verifier(sortie, erreur)

    def test_refus_de_session(self):
        for langue in ("fr", "en"):
            code, sortie, erreur, _ = self.lancer("check", "--language", langue, environ={**self.environ, "CLAUDECODE": "1"})
            self.assertEqual(code, 3)
            self.verifier(sortie, erreur)

    def test_erreurs_de_fichier_et_de_base(self):
        class Panne(FausseBase):
            def execute(self, sql, params=()):
                raise RuntimeError(f"{CLE} {EQUIPE} {ETIQUETTE} {VERSION} {FICHIER}")

        for commande in (("check",), ("purge", "--apply")):
            code, sortie, erreur, _ = self.lancer(*commande, base=Panne())
            self.assertEqual(code, 1)
            self.verifier(sortie, erreur)
        self.historique.write_text(f"{CLE} pas du json", encoding="utf-8")
        code, sortie, erreur, _ = self.lancer("check")
        self.assertEqual(code, 1)
        self.verifier(sortie, erreur)

    def test_reglage_invalide_ne_repete_pas_les_valeurs(self):
        self.ecrire_reglages(f"retention:\n  backup_label: {ETIQUETTE.upper()}\n  period_days: {EQUIPE}\n")
        code, sortie, erreur, _ = self.lancer("check")
        self.assertEqual(code, 3)
        self.verifier(sortie, erreur)
        self.assertNotIn(ETIQUETTE.upper(), sortie + erreur)


if __name__ == "__main__":
    unittest.main()
