"""Ventilation des incohérents de `check` (R-20261113-50 à -52 ; option renommée --since, R-20261114-01).

    bash tests/run_all.sh history_jira

Un incohérent est un ticket dont le dernier état de l'historique diffère de l'état stocké. `check` les ventile :
  - livré (date de résolution) ou non livré ;
  - avec --since AAAA-MM-JJ (jour du fuseau d'export) : dernière transition de l'historique avant cette date ou depuis (le jour même
    compte « depuis »). Sans --since, seule la première ventilation est faite ;
  - une date mal formée est refusée (code 2) avec un message, avant toute lecture ; l'ancien nom --depuis est refusé (code 2) avec
    le nom actuel ; --since avec --key est refusé (code 2), avant toute lecture ; une date future donne un avertissement d'une ligne ;
  - aucune clé, aucun nom de personne, aucune équipe ; seuls des noms d'état dans les paires.
Base fictive, données inventées.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_history_jira as base  # noqa: E402
from aide_historique import hj  # noqa: E402


class Ventilation(base.Controle):
    # `Controle` fournit `poser` et `parcours` ; ses propres tests ne sont pas rejoués ici (voir ci-dessous).
    def preparer(self):
        """Quatre incohérents : deux livrés (dernière transition le 2026-03-01 et le 2026-03-05), deux non livrés (2026-03-04 et
        2026-03-05) ; un cohérent livré ; un cohérent non livré. L'état stocké est « Done » (livré) ou « Open » (non livré)."""
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", True), ("ABC-2", "Story", "Equipe Test", True),
                            ("ABC-3", "Story", "Equipe Test", True), ("ABC-4", "Story", "Equipe Test", False),
                            ("ABC-5", "Story", "Equipe Test", False), ("ABC-6", "Story", "Equipe Test", False),
                            ("ABC-7", "Story", "Equipe Test", False)])
        self.poser("ABC-1", [("2026-03-01", "Open", "Doing")])         # livré, incohérent, avant
        self.poser("ABC-2", [("2026-03-05", "Open", "Doing")])         # livré, incohérent, le jour de la borne
        self.poser("ABC-3", [("2026-03-05", "Open", "Done")])          # livré, cohérent
        self.poser("ABC-4", [("2026-03-04", "Open", "Doing")])         # non livré, incohérent, avant
        self.poser("ABC-5", [("2026-03-05", "Open", "Doing")])         # non livré, incohérent, le jour de la borne
        self.poser("ABC-6", [("2026-03-05", "Doing", "Open")])         # non livré, cohérent
        self.poser("ABC-7", [("2026-03-01", "Open", "Doing"), ("2026-03-09", "Doing", "Review")])   # non livré, incohérent, depuis

    def test_sans_since_seule_la_ventilation_livre_ou_non(self):
        self.preparer()
        code, sortie = self.lancer("check")
        self.assertEqual(code, 0, sortie)
        self.assertIn("incohérents 5", sortie)
        self.assertIn("Incohérents : livrés 2 ; non livrés 3.", sortie)
        self.assertNotIn("dernière transition", sortie)
        self.assertNotIn("avant :", sortie)

    def test_avec_since_le_jour_meme_compte_depuis(self):
        self.preparer()
        code, sortie = self.lancer("check", "--since", "2026-03-05")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Incohérents : livrés 2 (dernière transition avant 2026-03-05 : 1, depuis : 1) ; "
                      "non livrés 3 (avant : 1, depuis : 2).", sortie)

    def test_avec_since_en_anglais(self):
        self.preparer()
        code, sortie = self.lancer("check", "--since", "2026-03-05", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Inconsistent: delivered 2 (last transition before 2026-03-05: 1, since: 1); "
                      "not delivered 3 (before: 1, since: 2).", sortie)
        _, sortie = self.lancer("check", "--language", "en")
        self.assertIn("Inconsistent: delivered 2; not delivered 3.", sortie)

    def test_ancien_nom_depuis_refuse_avec_le_nom_actuel(self):
        self.preparer()
        for argv in (("check", "--depuis", "2026-03-05"), ("check", "--depuis=2026-03-05")):
            code, sortie = self.lancer(*argv)
            self.assertEqual(code, 2, sortie)
            self.assertIn("« --depuis »", sortie)
            self.assertIn("« --since »", sortie)
            self.assertNotIn("Incohérents", sortie)

    def test_aucun_incoherent_lignes_a_zero(self):
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", True)])
        self.poser("ABC-1", self.parcours("Open", "Done"))
        _, sortie = self.lancer("check")
        self.assertIn("Incohérents : livrés 0 ; non livrés 0.", sortie)
        _, sortie = self.lancer("check", "--since", "2026-03-01")
        self.assertIn("Incohérents : livrés 0 (dernière transition avant 2026-03-01 : 0, depuis : 0) ; "
                      "non livrés 0 (avant : 0, depuis : 0).", sortie)

    def test_date_mal_formee_refusee_code_2(self):
        self.preparer()
        for mauvaise in ("2026-13-01", "05/03/2026", "hier", "20260305", ""):
            for langue in ("fr", "en"):
                code, sortie = self.lancer("check", "--since", mauvaise, "--language", langue)
                self.assertEqual(code, 2, (mauvaise, sortie))
                self.assertIn("--since", sortie)
                self.assertNotIn("--depuis", sortie)
                self.assertIn("AAAA-MM-JJ" if langue == "fr" else "YYYY-MM-DD", sortie)
                self.assertNotIn("Incohérents", sortie)
                self.assertNotIn("Inconsistent", sortie)

    def test_aucune_cle_ni_etat_ni_equipe_dans_la_sortie(self):
        self.preparer()
        for argv in (("check",), ("check", "--since", "2026-03-05")):
            _, sortie = self.lancer(*argv)
            ventilation = [ligne for ligne in sortie.splitlines() if ligne.startswith("Incohérents")]
            self.assertEqual(len(ventilation), 1)
            for interdit in ("ABC-", "Equipe Test", "Doing", "Review", "Done", "Open"):
                self.assertNotIn(interdit, ventilation[0])
            self.assertNotIn("ABC-", sortie)
            self.assertNotIn("Equipe Test", sortie)

    # ---- paires (dernier état de l'historique -> état stocké) et état stocké déjà traversé ou jamais vu
    def test_paires_triees_par_effectif_decroissant(self):
        self.preparer()
        _, sortie = self.lancer("check")
        self.assertIn("Paires d'incohérents (dernier état de l'historique -> état stocké) : "
                      "Doing -> Done 2 ; Doing -> Open 2 ; Review -> Open 1.", sortie)
        _, sortie = self.lancer("check", "--language", "en")
        self.assertIn("Inconsistent pairs (last state in the history -> stored state): "
                      "Doing -> Done 2; Doing -> Open 2; Review -> Open 1.", sortie)

    def test_paires_dix_premieres_puis_autres(self):
        self.ecrire_export([(f"ABC-{i}", "Story", "Equipe Test", False) for i in range(1, 14)])
        derniers = [f"E{i}" for i in range(1, 13)] + ["E9"]
        for i, dernier in enumerate(derniers, start=1):
            self.poser(f"ABC-{i}", [("2026-03-01", "Open", dernier)])
        _, sortie = self.lancer("check")
        self.assertIn("E9 -> Open 2 ; E1 -> Open 1 ; E10 -> Open 1 ; E11 -> Open 1 ; E12 -> Open 1 ; E2 -> Open 1 ; "
                      "E3 -> Open 1 ; E4 -> Open 1 ; E5 -> Open 1 ; E6 -> Open 1 ; autres : 2.", sortie)

    def test_etat_stocke_deja_traverse_ou_jamais_vu(self):
        self.preparer()
        _, sortie = self.lancer("check")
        self.assertIn("Parmi les incohérents : état stocké déjà traversé : 3 ; état stocké jamais vu dans l'historique : 2.", sortie)
        _, sortie = self.lancer("check", "--language", "en")
        self.assertIn("Among the inconsistent: stored state already crossed: 3; stored state never seen in the history: 2.", sortie)

    def test_aucun_incoherent_paires_et_traverses_a_zero(self):
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", True)])
        self.poser("ABC-1", self.parcours("Open", "Done"))
        _, sortie = self.lancer("check")
        self.assertIn("Paires d'incohérents (dernier état de l'historique -> état stocké) : aucune.", sortie)
        self.assertIn("état stocké déjà traversé : 0 ; état stocké jamais vu dans l'historique : 0.", sortie)

    def test_ligne_des_paires_seulement_des_noms_d_etat_et_des_nombres(self):
        self.preparer()
        _, sortie = self.lancer("check")
        ligne = next(l for l in sortie.splitlines() if l.startswith("Paires d'incohérents"))
        corps = ligne.split(" : ", 1)[1].rstrip(".")
        for morceau in corps.split(" ; "):
            self.assertRegex(morceau, r"^(Doing|Review|Done|Open) -> (Doing|Review|Done|Open) \d+$")
        self.assertNotIn("ABC-", ligne)
        self.assertNotIn("Equipe Test", ligne)

    # ---- revue Opus : fuseau paresseux, date illisible, borne dans le fuseau d'export, casse, lecture après le refus
    def test_sans_since_le_fuseau_des_reglages_n_est_pas_calcule(self):
        # la lecture de la base (faux ou réel) lit déjà le fuseau ; `check` seul ne doit pas le calculer une seconde fois pour rien
        self.preparer()
        with mock.patch.object(hj, "fuseau_des_reglages", side_effect=AssertionError("fuseau calculé sans --since")):
            code, sortie = self.lancer("check")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Incohérents : livrés 2 ; non livrés 3.", sortie)
        with mock.patch.object(hj, "fuseau_des_reglages", wraps=hj.fuseau_des_reglages) as appel:
            code, sortie = self.lancer("check", "--since", "2026-03-05")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(appel.call_count, 1)

    def test_date_de_derniere_transition_illisible_comptee_a_part(self):
        self.preparer()
        vraie = hj.lire_donnees_de_la_base

        def avec_une_date_illisible(settings):
            tickets, historique = vraie(settings)
            historique["ABC-4"][-1][0] = "pas une date"          # non livré, incohérent : ni « avant » ni « depuis »
            return tickets, historique
        with mock.patch.object(hj, "lire_donnees_de_la_base", avec_une_date_illisible):
            code, sortie = self.lancer("check", "--since", "2026-03-05")
            self.assertEqual(code, 0, sortie)
            self.assertIn("Incohérents : livrés 2 (dernière transition avant 2026-03-05 : 1, depuis : 1) ; "
                          "non livrés 3 (avant : 0, depuis : 2).", sortie)
            self.assertIn("Incohérents dont la date de dernière transition est illisible : 1.", sortie)
            _, sortie = self.lancer("check", "--since", "2026-03-05", "--language", "en")
            self.assertIn("Inconsistent with an unreadable last-transition date: 1.", sortie)
            _, sortie = self.lancer("check")
            self.assertNotIn("illisible", sortie)          # sans --since, la date n'est pas lue
        _, sortie = self.lancer("check", "--since", "2026-03-05")
        self.assertNotIn("illisible", sortie)              # aucune date illisible : aucune ligne

    def test_borne_lue_dans_le_fuseau_d_export(self):
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", False)])
        self.poser("ABC-1", [("2026-03-01", "Open", "Doing")])
        # 23 h 30 UTC le 4 mars est 0 h 30 le 5 mars à Paris : « depuis 2026-03-05 »
        self.magasin.transitions["ABC-1"] = [(dt.datetime.fromisoformat("2026-03-04T23:30:00+00:00"), "Open", "Doing")]
        _, sortie = self.lancer("check", "--since", "2026-03-05")
        self.assertIn("non livrés 1 (avant : 0, depuis : 1)", sortie)

    def test_etat_stocke_traverse_malgre_la_casse_et_les_espaces(self):
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", False)])
        self.poser("ABC-1", [("2026-03-01", "open ", "Doing")])          # état stocké « Open »
        _, sortie = self.lancer("check")
        self.assertIn("état stocké déjà traversé : 1 ; état stocké jamais vu dans l'historique : 0.", sortie)

    def test_date_mal_formee_refusee_avant_toute_lecture_de_la_base(self):
        self.preparer()
        with mock.patch.object(hj, "lire_donnees_de_la_base", side_effect=AssertionError("la base ne doit pas être lue")):
            code, sortie = self.lancer("check", "--since", "2026-13-01")
        self.assertEqual(code, 2, sortie)
        self.assertIn("AAAA-MM-JJ", sortie)

    # ---- R-20261114-01 : --since avec --key refusé, date future signalée
    def test_since_avec_key_refuse_code_2_avant_toute_lecture(self):
        self.preparer()
        for langue, attendu in (("fr", "--since ne s'utilise pas avec --key"), ("en", "--since cannot be used with --key")):
            with mock.patch.object(hj, "reglages", side_effect=AssertionError("réglages lus")), \
                    mock.patch.object(hj, "lire_donnees_de_la_base", side_effect=AssertionError("la base ne doit pas être lue")):
                code, sortie = self.lancer("check", "--key", "ABC-1", "--since", "2026-03-05", "--language", langue)
            self.assertEqual(code, 2, sortie)
            self.assertIn(attendu, sortie)
            self.assertNotIn("ABC-1 :", sortie)           # rien n'est affiché du ticket

    def test_key_seul_reste_permis(self):
        self.preparer()
        code, sortie = self.lancer("check", "--key", "ABC-1")
        self.assertEqual(code, 0, sortie)

    def test_date_future_avertissement_d_une_ligne_sans_erreur(self):
        self.preparer()
        code, sortie = self.lancer("check", "--since", "2999-01-01")
        self.assertEqual(code, 0, sortie)
        lignes = [l for l in sortie.splitlines() if l.startswith("Avertissement")]
        self.assertEqual(len(lignes), 1, sortie)
        self.assertIn("--since 2999-01-01", lignes[0])
        self.assertIn("postérieure à aujourd'hui", lignes[0])
        self.assertIn("Incohérents : livrés 2 (dernière transition avant 2999-01-01 : 2, depuis : 0)", sortie)
        _, sortie = self.lancer("check", "--since", "2999-01-01", "--language", "en")
        lignes = [l for l in sortie.splitlines() if l.startswith("Warning")]
        self.assertEqual(len(lignes), 1, sortie)
        self.assertIn("--since 2999-01-01", lignes[0])
        self.assertIn("is later than today", lignes[0])

    def test_pas_d_avertissement_pour_une_date_passee_ni_sans_since(self):
        self.preparer()
        for argv in (("check", "--since", "2026-03-05"), ("check",)):
            _, sortie = self.lancer(*argv)
            self.assertNotIn("Avertissement", sortie)
            self.assertNotIn("Warning", sortie)

    # ---- R-20261114-25 à -27 : deux dernières transitions au même horodatage, mise à jour postérieure à la dernière transition
    def preparer_horodatages(self):
        """Cinq incohérents (état stocké « Open », dernier état autre) et un cohérent. 1 : deux transitions au même instant, mise à
        jour (maj) postérieure ; 2 : une seule transition, maj postérieure ; 3 : deux instants différents, maj égale à la dernière
        transition (pas postérieure) ; 4 : même instant, sans maj ; 6 : même instant écrit avec deux décalages, maj antérieure ;
        5 (cohérent) : même instant, maj postérieure, hors compteurs."""
        apres = dt.datetime.fromisoformat("2026-03-10T10:00:00+02:00")
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", False, apres), ("ABC-2", "Story", "Equipe Test", False, apres),
                            ("ABC-3", "Story", "Equipe Test", False, dt.datetime.fromisoformat("2026-03-02T10:00:00+02:00")),
                            ("ABC-4", "Story", "Equipe Test", False), ("ABC-5", "Story", "Equipe Test", False, apres),
                            ("ABC-6", "Story", "Equipe Test", False)])
        self.poser("ABC-1", [("2026-03-01", "Open", "Doing"), ("2026-03-01", "Doing", "Review")])
        self.poser("ABC-2", [("2026-03-01", "Open", "Doing")])
        self.poser("ABC-3", [("2026-03-01", "Open", "Doing"), ("2026-03-02", "Doing", "Review")])
        self.poser("ABC-4", [("2026-03-01", "Open", "Doing"), ("2026-03-01", "Doing", "Review")])
        self.magasin.stock["ABC-4"]["maj"] = None
        self.poser("ABC-5", [("2026-03-01", "Open", "Doing"), ("2026-03-01", "Doing", "Open")])
        self.poser("ABC-6", [("2026-03-01", "Open", "Doing")])
        self.magasin.transitions["ABC-6"] = [(dt.datetime.fromisoformat("2026-03-01T08:00:00+00:00"), "Open", "Doing"),
                                             (dt.datetime.fromisoformat("2026-03-01T10:00:00+02:00"), "Doing", "Review")]

    def test_compteurs_meme_horodatage_et_mise_a_jour_posterieure(self):
        self.preparer_horodatages()
        code, sortie = self.lancer("check")
        self.assertEqual(code, 0, sortie)
        self.assertIn("incohérents 5", sortie)
        self.assertIn("Parmi les incohérents : deux dernières transitions au même horodatage : 3 ; "
                      "mise à jour du ticket postérieure à la fin de l'historique : 2.", sortie)
        _, sortie = self.lancer("check", "--language", "en")
        self.assertIn("Among the inconsistent: last two transitions at the same timestamp: 3; "
                      "ticket update later than the end of the history: 2.", sortie)

    def test_compteurs_apres_la_ligne_etat_stocke_et_sans_donnee_nominative(self):
        self.preparer_horodatages()
        _, sortie = self.lancer("check")
        lignes = sortie.splitlines()
        i = next(n for n, l in enumerate(lignes) if l.startswith("Parmi les incohérents : état stocké"))
        self.assertTrue(lignes[i + 1].startswith("Parmi les incohérents : deux dernières transitions"), lignes[i + 1])
        for interdit in ("ABC-", "Equipe Test", "2026-03"):
            self.assertNotIn(interdit, lignes[i + 1])

    def test_compteurs_a_zero_sans_incoherent(self):
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", True)])
        self.poser("ABC-1", self.parcours("Open", "Done"))
        _, sortie = self.lancer("check")
        self.assertIn("deux dernières transitions au même horodatage : 0 ; "
                      "mise à jour du ticket postérieure à la fin de l'historique : 0.", sortie)

    def test_date_illisible_jamais_comptee_comme_egale_ni_comme_anterieure(self):
        self.preparer_horodatages()
        vraie = hj.lire_donnees_de_la_base

        def avec_dates_illisibles(settings):
            tickets, historique = vraie(settings)
            for transition in historique["ABC-1"]:
                transition[0] = "pas une date"           # deux dates illisibles identiques : pas « égales »
            return tickets, historique
        with mock.patch.object(hj, "lire_donnees_de_la_base", avec_dates_illisibles):
            code, sortie = self.lancer("check")
        self.assertEqual(code, 0, sortie)
        self.assertIn("au même horodatage : 2 ; mise à jour du ticket postérieure à la fin de l'historique : 1.", sortie)

    def test_avec_key_les_mises_a_jour_ne_sont_pas_lues(self):
        self.preparer_horodatages()
        with mock.patch.object(hj, "lire_maj_de_la_base", side_effect=AssertionError("mises à jour lues")):
            code, sortie = self.lancer("check", "--key", "ABC-1")
        self.assertEqual(code, 0, sortie)


# les tests hérités de Controle ne sont pas rejoués dans cette classe : ils sont déjà lancés par test_history_jira
for _nom in [n for n in dir(base.Controle) if n.startswith("test_")]:
    setattr(Ventilation, _nom, None)

if __name__ == "__main__":
    unittest.main()
