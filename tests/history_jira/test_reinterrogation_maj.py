"""Réinterrogation des tickets terminés mis à jour depuis la dernière collecte (R-90, GitHub #357 ; change database-only, D5).

    bash tests/run_all.sh history_jira

Un ticket terminé qui a déjà un historique n'est réinterrogé que si sa date de mise à jour (lue dans la base) est postérieure à celle de
la dernière collecte réussie moins un jour (le passage « history » de la couche brute). Un ticket sans historique ou non terminé est
toujours interrogé. Faux serveur, base fictive, données inventées, faux jeton ; aucune clé ni aucun nom dans la sortie.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_history_jira as base  # noqa: E402

UTC = dt.timezone.utc
PREMIERE = dt.datetime(2026, 9, 10, 12, 0, tzinfo=UTC)         # instant de la première collecte réussie
SECONDE = dt.datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
ANCIEN = dt.datetime(2026, 9, 1, 9, 0, tzinfo=UTC)             # bien avant la première collecte
TRES_RECENT = dt.datetime(2026, 9, 20, 9, 0, tzinfo=UTC)       # après la première collecte
LIGNE_FR = "Tickets terminés réinterrogés (mis à jour depuis la dernière collecte) : "
LIGNE_EN = "Finished tickets queried again (updated since the last collection): "


class ReinterrogationMaj(base.Base):
    def setUp(self):
        super().setUp()
        self.instants = iter([PREMIERE, SECONDE, SECONDE + dt.timedelta(days=5), SECONDE + dt.timedelta(days=10)])
        self.magasin.horloge = lambda: next(self.instants)

    def lignes(self, n, maj):
        """n tickets terminés, tous mis à jour à `maj`."""
        self.inventer(n)
        return [(f"ABC-{i}", "Story", "Equipe Test", True, maj) for i in range(1, n + 1)]

    def recherches_de_cles(self):
        return sum(1 for api, corps in self.faux.corps if api == "/rest/api/3/search/jql" and corps.get("fields") == ["key"])

    def ajouter_transition(self, cle):
        ident, histo = self.faux.tickets[cle]
        histo.append({"id": "9", "created": "2026-09-18T10:00:00.000+0200", "author": {"displayName": base.AUTEUR},
                      "items": [{"field": "status", "fieldId": "status", "fromString": "Done", "toString": "Reopened"}]})

    def mettre_a_jour(self, lignes, **par_cle):
        """Les mêmes lignes, avec une autre date de mise à jour pour les clés données."""
        self.ecrire_export([(c, t, e, f, par_cle.get(c, u)) for c, t, e, f, u in lignes])

    def test_ticket_termine_inchange_n_est_pas_reinterroge(self):
        self.ecrire_export(self.lignes(2, ANCIEN))
        self.lancer("collect")
        self.assertEqual(self.magasin.passages, [PREMIERE])
        self.faux.appels.clear()
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.faux.appels, [])
        self.assertIn("Déjà collectés et terminés (non réinterrogés) : 2 ; à interroger : 0", sortie)
        self.assertIn(LIGNE_FR + "0", sortie)

    def test_ticket_termine_mis_a_jour_est_reinterroge_et_ses_nouvelles_transitions_ajoutees(self):
        lignes = self.lignes(2, ANCIEN)
        self.ecrire_export(lignes)
        self.lancer("collect")
        self.assertEqual(len(self.cache()["ABC-1"]["transitions"]), 2)
        self.ajouter_transition("ABC-1")
        self.faux.appels.clear()
        self.faux.corps.clear()
        self.mettre_a_jour(lignes, **{"ABC-1": TRES_RECENT})
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.recherches_de_cles(), 1)                    # un seul lot : ABC-1
        self.assertEqual(len(self.cache()["ABC-1"]["transitions"]), 3)
        self.assertEqual(self.cache()["ABC-1"]["transitions"][-1][2], "Reopened")
        self.assertEqual(len(self.cache()["ABC-2"]["transitions"]), 2)
        self.assertIn("Déjà collectés et terminés (non réinterrogés) : 1 ; à interroger : 1", sortie)
        self.assertIn(LIGNE_FR + "1", sortie)
        self.assertIn("Tickets traités : 1", sortie)
        self.assertIn("historique écrit : 1 transitions ajoutées, 0 périodes écrites", sortie)

    def test_ticket_reinterroge_une_fois_puis_plus(self):
        lignes = self.lignes(1, ANCIEN)
        self.ecrire_export(lignes)
        self.lancer("collect")
        self.mettre_a_jour(lignes, **{"ABC-1": TRES_RECENT})
        self.lancer("collect")
        self.assertEqual(self.magasin.passages, [PREMIERE, SECONDE])
        self.faux.appels.clear()
        self.lancer("collect")
        self.assertEqual(self.faux.appels, [])

    def test_mise_a_jour_anterieure_a_la_derniere_collecte_ne_reinterroge_pas(self):
        lignes = self.lignes(1, ANCIEN)
        self.ecrire_export(lignes)
        self.lancer("collect")
        self.faux.appels.clear()
        self.mettre_a_jour(lignes, **{"ABC-1": ANCIEN + dt.timedelta(days=2)})
        self.lancer("collect")
        self.assertEqual(self.faux.appels, [])

    def test_le_recouvrement_d_un_jour_reinterroge_une_mise_a_jour_juste_avant_la_collecte(self):
        lignes = self.lignes(2, ANCIEN)
        self.ecrire_export(lignes)
        self.lancer("collect")
        self.faux.appels.clear()
        self.faux.corps.clear()
        self.mettre_a_jour(lignes, **{"ABC-1": PREMIERE - dt.timedelta(hours=12), "ABC-2": PREMIERE - dt.timedelta(hours=30)})
        code, sortie = self.lancer("collect")
        self.assertIn(LIGNE_FR + "1", sortie)                             # 12 heures avant : dans le jour de recouvrement ; 30 heures : non

    def test_un_ticket_sans_historique_ou_ouvert_est_toujours_interroge(self):
        lignes = self.lignes(2, ANCIEN)
        self.ecrire_export(lignes)
        self.lancer("collect")
        self.faux.ajouter("ABC-3")
        self.faux.ajouter("ABC-4")
        self.ecrire_export(lignes + [("ABC-3", "Story", "Equipe Test", True, ANCIEN), ("ABC-4", "Story", "Equipe Test", False, ANCIEN)])
        code, sortie = self.lancer("collect")
        self.assertIn("Déjà collectés et terminés (non réinterrogés) : 2 ; à interroger : 2", sortie)     # ABC-3 sans historique, ABC-4 ouvert

    def test_ticket_mis_a_jour_en_erreur_sera_retente(self):
        """Un ticket en erreur n'écrit pas de collecte réussie : la référence ne bouge pas et il est réinterrogé ensuite."""
        lignes = self.lignes(2, ANCIEN)
        self.ecrire_export(lignes)
        self.lancer("collect")
        self.ajouter_transition("ABC-1")
        self.faux.refus = {"history": 503}                                # erreur passagère (un 404 n'est plus une erreur : D15)
        self.mettre_a_jour(lignes, **{"ABC-1": TRES_RECENT})
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertIn("erreurs : 1 (HTTP 503 : 1)", sortie)
        self.assertEqual(len(self.cache()["ABC-1"]["transitions"]), 2)
        self.assertEqual(self.magasin.passages, [PREMIERE])               # pas de nouvelle collecte réussie
        self.faux.refus = {}
        code, sortie = self.lancer("collect")
        self.assertIn(LIGNE_FR + "1", sortie)
        self.assertEqual(len(self.cache()["ABC-1"]["transitions"]), 3)
        self.assertEqual(self.magasin.passages, [PREMIERE, SECONDE])

    def test_premiere_collecte_sans_passage_anterieur(self):
        self.ecrire_export(self.lignes(2, TRES_RECENT))
        code, sortie = self.lancer("collect")
        self.assertIn("Déjà collectés et terminés (non réinterrogés) : 0 ; à interroger : 2", sortie)       # sans historique : tous interrogés
        self.assertIn(LIGNE_FR + "0", sortie)

    def test_ligne_en_anglais(self):
        self.ecrire_export(self.lignes(1, ANCIEN))
        self.lancer("collect")
        code, sortie = self.lancer("collect", "--language", "en")
        self.assertIn(LIGNE_EN + "0", sortie)

    def test_refresh_inchange(self):
        self.ecrire_export(self.lignes(2, ANCIEN))
        self.lancer("collect")
        code, sortie = self.lancer("collect", "--refresh")
        self.assertIn("Tout est réinterrogé (--refresh)", sortie)
        self.assertIn("Tickets traités : 2", sortie)
        self.assertNotIn("mis à jour", sortie)

    def test_aucune_cle_ni_nom_dans_la_sortie_ni_les_fichiers(self):
        lignes = self.lignes(2, ANCIEN)
        self.ecrire_export(lignes)
        self.lancer("collect")
        self.ajouter_transition("ABC-1")
        self.mettre_a_jour(lignes, **{"ABC-1": TRES_RECENT, "ABC-2": TRES_RECENT})
        code, sortie = self.lancer("collect")
        for interdit in ("ABC-", "Equipe Test", base.AUTEUR, base.JETON, "Titre secret"):
            self.assertNotIn(interdit, sortie)
        for interdit in (base.AUTEUR, "Equipe Test", base.JETON, "Titre secret"):
            self.assertNotIn(interdit, self.tous_les_fichiers() + repr(self.magasin.transitions))


if __name__ == "__main__":
    unittest.main()
