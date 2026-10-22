"""Ticket introuvable (404) distingué des erreurs passagères (change database-only, D5 ; bug du 404 permanent).

    bash tests/run_all.sh history_jira

Un ticket supprimé ou sans accès répondait 404 à chaque collecte : le passage « history » n'était jamais enregistré. Désormais :
  - un 404 compte pour le ticket (compteur de passages consécutifs, remis à zéro dès que le ticket est trouvé) ;
  - après N passages consécutifs en 404 (réglage history_not_found_limit, 3 par défaut), le ticket est marqué disparu et n'est plus
    interrogé (sauf --refresh) ;
  - une erreur passagère (429, 5xx, réseau) ne marque jamais un ticket disparu et ne touche pas son compteur ;
  - le passage « history » est enregistré même avec des erreurs, avec leur nombre ; seul un passage sans erreur avance la dernière
    collecte réussie (les tickets mis à jour depuis sont réinterrogés) ;
  - aucune clé, aucun titre dans la sortie.
Faux serveur Jira, base fictive, données inventées, faux jeton.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_history_jira as base  # noqa: E402


class Introuvables(base.Base):
    def preparer(self, n=3, mode_groupe=False):
        """n tickets non résolus ; le deuxième (ABC-2) est introuvable. En mode ticket par ticket, l'API groupée est absente."""
        self.faux.groupe = mode_groupe
        self.ecrire_export(self.inventer(n))
        if mode_groupe:
            del self.faux.tickets["ABC-2"]          # absent de la réponse groupée : Jira ne le renvoie pas
        else:
            self.faux.introuvables = {"ABC-2"}

    def appels_de(self, cle):
        return [a for a in self.faux.appels if cle in a[1] and a[1].endswith("/changelog")]

    def test_un_404_puis_trouve_remet_le_compteur_a_zero(self):
        self.preparer()
        self.lancer("collect")
        self.lancer("collect")
        self.assertEqual(self.magasin.compteurs["ABC-2"], 2)
        self.faux.introuvables = set()
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.magasin.compteurs["ABC-2"], 0)
        self.assertNotIn("ABC-2", self.magasin.disparus)
        self.assertIn("ABC-2", self.cache())
        self.faux.introuvables = {"ABC-2"}
        self.lancer("collect")
        self.lancer("collect")
        self.assertEqual(self.magasin.compteurs["ABC-2"], 2)            # il faut de nouveau des passages consécutifs
        self.assertEqual(self.magasin.disparus, set())

    def test_n_fois_404_marque_disparu_et_ne_reinterroge_plus(self):
        self.preparer()
        for _ in range(3):
            self.lancer("collect")
        self.assertEqual(self.magasin.disparus, {"ABC-2"})
        avant = len(self.appels_de("ABC-2"))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.appels_de("ABC-2")), avant)            # plus aucun appel pour ce ticket
        self.assertIn("tickets marqués disparus, non interrogés : 1", sortie)
        self.assertNotIn("tickets introuvables dans Jira", sortie)

    def test_un_disparu_dont_l_import_a_efface_la_marque_est_reinterroge_a_la_collecte_suivante(self):
        """D15 complété : l'import remet à 0 le compteur et efface la marque d'un ticket que l'export revoit ; la collecte suivante
        l'interroge de nouveau, et une réponse 404 repart de 1."""
        self.preparer()
        for _ in range(3):
            self.lancer("collect")
        self.assertEqual(self.magasin.disparus, {"ABC-2"})
        avant = len(self.appels_de("ABC-2"))
        self.magasin.compteurs.pop("ABC-2", None)            # ce que fait l'import : compteur à 0 (aucune entrée) et marque effacée
        self.magasin.disparus.discard("ABC-2")
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertGreater(len(self.appels_de("ABC-2")), avant)                       # interrogé de nouveau
        self.assertEqual(self.magasin.compteurs["ABC-2"], 1)                          # le 404 repart de 1
        self.assertEqual(self.magasin.disparus, set())
        self.assertNotIn("ABC-2", sortie)

    def test_le_passage_ou_le_ticket_devient_disparu_le_dit_sans_la_cle(self):
        self.preparer()
        _, sortie = self.lancer("collect")
        self.assertIn("tickets introuvables dans Jira : 1", sortie)
        self.assertNotIn("désormais marqués disparus", sortie)
        self.lancer("collect")
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertIn("tickets introuvables dans Jira : 1", sortie)
        self.assertIn("tickets introuvables dans Jira, désormais marqués disparus : 1", sortie)
        self.assertNotIn("ABC-2", sortie)

    def test_les_404_ne_sont_pas_des_erreurs_et_n_empechent_pas_la_collecte_reussie_d_avancer(self):
        """D15 : seules les erreurs passagères empêchent un passage d'avancer la fenêtre des tickets modifiés."""
        self.preparer()
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertIn("erreurs : 0.", sortie)
        self.assertEqual((len(self.magasin.passages), self.magasin.passages_en_erreur), (1, []))
        self.assertEqual(self.magasin.nombres_introuvables, [1])
        for _ in range(3):
            self.lancer("collect")
        self.assertEqual(len(self.magasin.passages), 4)
        self.assertEqual(self.magasin.nombres_introuvables, [1, 1, 1, 0])          # disparu au troisième : plus de 404 ensuite

    def test_en_mode_groupe_un_ticket_que_jira_ne_renvoie_pas_compte_comme_404(self):
        self.preparer(mode_groupe=True)
        for _ in range(3):
            self.lancer("collect")
        self.assertEqual(self.magasin.disparus, {"ABC-2"})
        self.assertTrue(any(a[1] == "/rest/api/3/changelog/bulkfetch" for a in self.faux.appels))      # bien le mode groupé

    def test_le_reglage_fixe_le_nombre_de_passages(self):
        self.preparer()
        self.ecrire_reglages("scopes", extra="history_not_found_limit: 2\n")
        self.lancer("collect")
        self.assertEqual(self.magasin.disparus, set())
        _, sortie = self.lancer("collect")
        self.assertEqual(self.magasin.disparus, {"ABC-2"})
        self.assertIn("désormais marqués disparus : 1", sortie)

    def test_erreur_passagere_ne_marque_jamais_disparu(self):
        self.preparer()
        self.faux.introuvables = set()
        self.faux.refus = {"history": 503}
        for _ in range(6):                                               # plus que N, avec ticket par ticket puis groupé
            code, sortie = self.lancer("collect")
            self.assertEqual(code, 0, sortie)
        self.assertEqual(self.magasin.disparus, set())
        self.assertEqual(self.magasin.compteurs, {})
        self.faux.groupe = True
        for _ in range(4):
            self.lancer("collect")
        self.assertEqual((self.magasin.disparus, self.magasin.compteurs), (set(), {}))

    def test_une_erreur_passagere_ne_remet_pas_le_compteur_a_zero(self):
        self.preparer()
        self.lancer("collect")
        self.lancer("collect")
        self.assertEqual(self.magasin.compteurs["ABC-2"], 2)
        self.faux.introuvables = set()
        self.faux.refus = {"history": 503}
        self.lancer("collect")
        self.assertEqual(self.magasin.compteurs["ABC-2"], 2)             # ni remis à zéro, ni augmenté
        self.assertEqual(self.magasin.disparus, set())

    def test_passage_enregistre_avec_erreurs_et_leur_nombre(self):
        self.preparer()
        self.faux.introuvables = set()
        self.faux.refus = {"history": 503}
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertEqual([erreurs for _, erreurs in self.magasin.passages_en_erreur], [3])
        self.assertEqual(self.magasin.passages, [])                      # la dernière collecte réussie n'avance pas
        self.assertIsNone(self.magasin.derniere_collecte())
        self.assertEqual((self.magasin.ecritures, self.magasin.nombres_introuvables), (1, [0]))
        self.faux.refus = {}
        self.faux.introuvables = {"ABC-2"}
        self.lancer("collect")                                           # un 404 seul : passage réussi
        self.assertEqual((len(self.magasin.passages), self.magasin.nombres_introuvables), (1, [0, 1]))

    def test_un_passage_sans_erreur_n_a_pas_de_passage_en_erreur(self):
        self.ecrire_export(self.inventer(2))
        self.lancer("collect")
        self.assertEqual((len(self.magasin.passages), self.magasin.passages_en_erreur), (1, []))

    def test_strict_ne_sort_en_3_que_sur_des_erreurs_passageres(self):
        self.preparer()
        code, sortie = self.lancer("collect", "--strict")
        self.assertEqual(code, 0, sortie)                                # un 404 seul : code 0
        self.faux.introuvables = set()
        self.faux.refus = {"history": 503}
        code, sortie = self.lancer("collect", "--strict")
        self.assertEqual(code, 3, sortie)
        self.assertEqual(len(self.magasin.passages_en_erreur), 1)        # écrit comme sans l'option

    def test_refresh_reinterroge_un_disparu_et_le_remet_en_service_s_il_est_trouve(self):
        self.preparer()
        for _ in range(3):
            self.lancer("collect")
        self.assertEqual(self.magasin.disparus, {"ABC-2"})
        self.faux.introuvables = set()
        avant = len(self.appels_de("ABC-2"))
        self.lancer("collect")
        self.assertEqual(len(self.appels_de("ABC-2")), avant)            # sans --refresh : toujours ignoré
        code, sortie = self.lancer("collect", "--refresh")
        self.assertEqual(code, 0, sortie)
        self.assertGreater(len(self.appels_de("ABC-2")), avant)
        self.assertEqual(self.magasin.disparus, set())
        self.assertEqual(self.magasin.compteurs["ABC-2"], 0)
        self.assertIn("ABC-2", self.cache())
        self.assertIn("tickets marqués disparus retrouvés : 1", sortie)

    def test_refresh_et_404_garde_le_ticket_disparu(self):
        self.preparer()
        for _ in range(3):
            self.lancer("collect")
        self.lancer("collect", "--refresh")
        self.assertEqual(self.magasin.disparus, {"ABC-2"})

    def test_sortie_sans_cle_ni_titre_en_francais_et_en_anglais(self):
        self.preparer()
        for langue in ("fr", "en"):
            for _ in range(3):
                code, sortie = self.lancer("collect", "--language", langue)
                self.assertEqual(code, 0, sortie)
                for interdit in ("ABC-", "Titre secret", base.AUTEUR, "Nom Fictif"):
                    self.assertNotIn(interdit, sortie)
            self.magasin.disparus.clear()
            self.magasin.compteurs.clear()

    def test_ligne_anglaise(self):
        self.preparer()
        self.lancer("collect", "--language", "en")
        self.lancer("collect", "--language", "en")
        _, sortie = self.lancer("collect", "--language", "en")
        self.assertIn("tickets not found in Jira: 1", sortie)
        self.assertIn("tickets not found in Jira, now marked gone: 1", sortie)
        _, sortie = self.lancer("collect", "--language", "en")
        self.assertIn("tickets marked gone, not queried: 1", sortie)
        self.faux.introuvables = set()
        _, sortie = self.lancer("collect", "--language", "en", "--refresh")
        self.assertIn("tickets marked gone found again: 1", sortie)

    def test_un_ticket_disparu_n_entre_pas_dans_le_decompte_a_interroger(self):
        self.preparer()
        for _ in range(3):
            self.lancer("collect")
        _, sortie = self.lancer("collect")
        self.assertIn("à interroger : 2", sortie)


if __name__ == "__main__":
    unittest.main()
