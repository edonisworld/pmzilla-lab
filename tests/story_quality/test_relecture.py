"""
Tests de `story_quality.py review --team <équipe> --sample <n>` (change story-quality-audit, tâche 3.6 ; design D5 « Per-team review
gate », section « Residual risk », D14 ; spec story-quality-analysis, « A team sample review is recorded per team », « Only the user
launches the analysis tool »).

Faux magasin du schéma quality (aide_story_quality.py), graine fixe, réponse de l'utilisateur simulée. Données inventées.
"""
from __future__ import annotations

import unittest

from aide_story_quality import EQUIPE_A, EQUIPE_B, EspaceCollecte


class Relecture(EspaceCollecte):
    def setUp(self):
        super().setUp()
        for i in range(1, 6):
            self.magasin.ajouter(f"ZZKEY-{i}", (EQUIPE_A,), titre=f"Titre nettoyé {i}", description=f"Description [person] {i}",
                                 criteres=f"Critère {i}")
        self.magasin.ajouter("ZZKEY-9", (EQUIPE_B,), titre="Titre de l'autre équipe")
        self.magasin.ajouter("ZZKEY-8", (EQUIPE_A,), titre="Titre sorti de la collecte", sorti=True)

    def test_echantillon_sans_cle_puis_question(self):
        code, sortie, erreur = self.lancer("review", "--team", EQUIPE_A, "--sample", "2", "--language", "en", reponse="no")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.count("Title: Titre nettoyé"), 2)
        self.assertIn("--- item 1 of 2 (no key) ---", sortie)
        self.assertIn("Description [person]", sortie)
        self.assertNotIn("ZZKEY", sortie + erreur)
        self.assertNotIn("Titre de l'autre équipe", sortie)
        self.assertNotIn("sorti de la collecte", sortie)
        self.assertEqual(self.questions, ["Sample checked, no name left? Type yes to record: "])

    def test_tirage_au_hasard_borne_et_reproductible(self):
        self.lancer("review", "--team", EQUIPE_A, "--sample", "3", reponse="non", graine=3)
        self.lancer("review", "--team", EQUIPE_A, "--sample", "3", reponse="non", graine=3)
        self.lancer("review", "--team", EQUIPE_A, "--sample", "50", reponse="non")
        premier, second, tout = self.magasin.tirages
        self.assertEqual(premier, second)
        self.assertEqual(len(premier), 3)
        self.assertEqual(sorted(tout), [f"ZZKEY-{i}" for i in range(1, 6)])     # pas plus que les éléments collectés

    def test_enregistree_sur_le_mot_de_confirmation(self):
        code, sortie, _ = self.lancer("review", "--team", EQUIPE_A, "--sample", "2", "--language", "en", reponse=" Yes ")
        self.assertEqual(code, 0)
        self.assertIn("team sample review recorded", sortie)
        self.assertEqual(self.magasin.relectures, [(EQUIPE_A, 2)])
        self.assertEqual(self.fichiers_ecrits(), [])

    def test_en_francais_le_mot_est_oui(self):
        code, sortie, _ = self.lancer("review", "--team", EQUIPE_A, "--sample", "1", reponse="oui")
        self.assertEqual(code, 0)
        self.assertIn("relecture de l'échantillon de l'équipe enregistrée", sortie)
        self.assertIn("Échantillon relu, aucun nom restant ? Taper oui pour enregistrer :", self.questions[0])
        self.assertEqual(self.magasin.relectures, [(EQUIPE_A, 1)])

    def test_toute_autre_reponse_n_enregistre_rien(self):
        for reponse in ("no", "yes please", "oui", "", None):
            with self.subTest(reponse=reponse):
                code, sortie, _ = self.lancer("review", "--team", EQUIPE_A, "--sample", "2", "--language", "en", reponse=reponse)
                self.assertEqual(code, 0)
                self.assertIn("review not recorded: update the sensitive-names list and collect again", sortie)
        self.assertEqual(self.magasin.relectures, [])

    def test_equipe_sans_element_collecte(self):
        code, sortie, _ = self.lancer("review", "--team", "Equipe Zzinconnue", "--sample", "2", "--language", "en", reponse="yes")
        self.assertEqual(code, 0)
        self.assertIn("no collected item for this team", sortie)
        self.assertEqual(self.questions, [])
        self.assertEqual(self.magasin.relectures, [])
        self.assertNotIn("Zzinconnue", sortie)

    def test_la_relecture_ne_vaut_que_pour_son_equipe(self):
        self.lancer("review", "--team", EQUIPE_B, "--sample", "5", "--language", "en", reponse="yes")
        self.assertEqual(self.magasin.relectures, [(EQUIPE_B, 1)])

    def test_refus_en_session_avant_toute_lecture(self):
        code, sortie, erreur = self.lancer("review", "--team", EQUIPE_A, "--sample", "2", "--language", "en", reponse="yes",
                                           environ={**self.environ, "CLAUDECODE": "1"})
        self.assertEqual(code, 3)
        self.assertIn("Refused inside a Claude Code session", sortie + erreur)
        self.assertEqual(self.ouvertures, 0)
        self.assertEqual(self.questions, [])

    def test_refus_sans_terminal_avant_toute_lecture(self):
        code, sortie, erreur = self.lancer("review", "--team", EQUIPE_A, "--sample", "2", "--language", "en", reponse="yes",
                                           terminal=False)
        self.assertEqual(code, 3)
        self.assertIn("confirmation needs a terminal", erreur)
        self.assertEqual(sortie, "")
        self.assertEqual(self.ouvertures, 0)
        self.assertEqual(self.questions, [])
        self.assertEqual(self.magasin.tirages, [])

    def test_controles_et_sequences_ansi_retires_de_l_affichage(self):
        self.magasin.ajouter("ZZKEY-7", (EQUIPE_B,), titre="Ti\x1b[31mtre\x1b[0m\x07 zz",
                             description="de\x1b]0;zzfenetre\x07sc\x1b]8;;http://zz\x1b\\ri\x00ption\ttab\nligne",
                             criteres="cr\x1b[2Jit\x7f\x9bère")
        code, sortie, _ = self.lancer("review", "--team", EQUIPE_B, "--sample", "5", "--language", "en", reponse="no")
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", sortie)
        for interdit in ("\x07", "\x00", "\x7f", "\x9b", "zzfenetre", "http://zz"):
            self.assertNotIn(interdit, sortie)
        self.assertIn("Title: Titre zz", sortie)
        self.assertIn("description\ttab\nligne", sortie)
        self.assertIn("critère", sortie)

    def fixer_minimum(self, valeur=3):
        texte = (self.flux / "flux.yaml").read_text(encoding="utf-8")
        (self.flux / "flux.yaml").write_text(texte + f"  review_sample_size: {valeur}\n", encoding="utf-8")

    def test_sample_sous_le_minimum_refuse_en_code_3_avant_toute_lecture(self):
        self.fixer_minimum(3)
        code, sortie, erreur = self.lancer("review", "--team", EQUIPE_A, "--sample", "2", "--language", "en", reponse="yes")
        self.assertEqual(code, 3)
        self.assertIn("sample size below the minimum for review: 3", erreur)
        self.assertEqual(sortie, "")
        self.assertEqual(self.ouvertures, 0)
        self.assertEqual(self.questions, [])
        code, _, erreur = self.lancer("review", "--team", EQUIPE_A, "--sample", "2", reponse="oui")
        self.assertEqual(code, 3)
        self.assertIn("taille d'échantillon inférieure au minimum de la relecture : 3", erreur)

    def test_sample_egal_ou_superieur_au_minimum_accepte(self):
        self.fixer_minimum(3)
        for taille in ("3", "4"):
            with self.subTest(taille=taille):
                code, sortie, _ = self.lancer("review", "--team", EQUIPE_A, "--sample", taille, "--language", "en", reponse="yes")
                self.assertEqual(code, 0)
                self.assertIn("team sample review recorded", sortie)

    def test_sans_reglage_aucun_minimum(self):
        code, sortie, _ = self.lancer("review", "--team", EQUIPE_A, "--sample", "1", "--language", "en", reponse="yes")
        self.assertEqual(code, 0)
        self.assertIn("team sample review recorded", sortie)

    def test_sans_bloc_aucun_minimum(self):
        self.ecrire_reglages(bloc="")
        code, _, _ = self.lancer("review", "--team", EQUIPE_A, "--sample", "1", "--language", "en", reponse="yes")
        self.assertEqual(code, 0)

    def test_reglage_invalide_arrete_sans_valeur_ni_lecture(self):
        self.fixer_minimum("zzabc")
        code, sortie, erreur = self.lancer("review", "--team", EQUIPE_A, "--sample", "2", "--language", "en", reponse="yes")
        self.assertEqual(code, 1)
        self.assertIn("story_quality.review_sample_size", erreur)
        self.assertNotIn("zzabc", sortie + erreur)
        self.assertEqual(self.ouvertures, 0)

    def test_equipe_plus_petite_que_la_taille_demandee_relecture_complete(self):
        code, sortie, _ = self.lancer("review", "--team", EQUIPE_A, "--sample", "50", "--language", "en", reponse="yes")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.count("Title: Titre nettoyé"), 5)
        self.assertIn("team sample review recorded", sortie)
        self.assertIn("full review: 5 items", sortie)
        self.assertEqual(self.magasin.relectures, [(EQUIPE_A, 5)])

    def test_relecture_complete_en_francais_et_pas_quand_l_echantillon_est_plein(self):
        _, sortie, _ = self.lancer("review", "--team", EQUIPE_A, "--sample", "50", reponse="oui")
        self.assertIn("relecture complète : 5 éléments", sortie)
        _, sortie, _ = self.lancer("review", "--team", EQUIPE_A, "--sample", "5", "--language", "en", reponse="yes")
        self.assertNotIn("full review", sortie)
        _, sortie, _ = self.lancer("review", "--team", EQUIPE_A, "--sample", "50", "--language", "en", reponse="no")
        self.assertNotIn("full review", sortie)           # rien d'enregistré, rien à dire

    def test_taille_d_echantillon_invalide(self):
        for taille in ("0", "-2", "abc", "2.5"):
            with self.subTest(taille=taille):
                code, _, _ = self.lancer("review", "--team", EQUIPE_A, "--sample", taille, reponse="yes")
                self.assertEqual(code, 2)
        self.assertEqual(self.ouvertures, 0)
        self.assertEqual(self.lancer("review", "--team", EQUIPE_A, reponse="yes")[0], 2)      # --sample obligatoire
        self.assertEqual(self.lancer("review", "--sample", "2", reponse="yes")[0], 2)         # --team obligatoire

    def test_panne_a_l_enregistrement_type_seul(self):
        self.magasin.echec = RuntimeError("ZZKEY-1 zzsecret")
        code, sortie, erreur = self.lancer("review", "--team", EQUIPE_A, "--sample", "1", "--language", "en", reponse="yes")
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", erreur)
        self.assertNotIn("zzsecret", sortie + erreur)
        self.assertNotIn("team sample review recorded", sortie)


if __name__ == "__main__":
    unittest.main()
