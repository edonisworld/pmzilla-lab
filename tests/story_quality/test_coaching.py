"""
Tests de `story_quality.py coach` (change story-quality-audit, tâche 3.9 ; design D5, D7, D14 ; spec story-quality-analysis : sélection
par équipe ou par clés tapées, retour borné dans sa propre table, affichage dans le Terminal seulement, `--show`, `--dry-run`, aucun
fichier, aucun compte des vues changé). Faux serveur d'analyse, fausse clé, faux magasin (aide_analyse.py). Données inventées.
"""
from __future__ import annotations

import json
import unittest

from aide_analyse import CLE_ANALYSE, EspaceAnalyse
from aide_story_quality import DISTINCTIFS, EQUIPE_A, EQUIPE_B
import story_quality_coach  # noqa: E402  (tools/story_quality_coach.py, chemin posé par aide_story_quality)

ENTETE = "Coaching results: shown here only, kept out of every report"


class Selection(unittest.TestCase):
    def test_par_cles_tapees_et_par_equipe(self):
        from types import SimpleNamespace
        elements = [{"key": "ZZ-2", "teams": ["A"]}, {"key": "ZZ-1", "teams": ["A", "B"]}]
        choisis, inconnus = story_quality_coach.selectionner(SimpleNamespace(team=None, keys=[" ZZ-2", "ZZ-1", "ZZ-9", ""]), elements)
        self.assertEqual(([e["key"] for e in choisis], inconnus), (["ZZ-1", "ZZ-2"], 1))
        self.assertEqual(story_quality_coach.selectionner(SimpleNamespace(team="B", keys=None), elements), ([elements[1]], 0))
        self.assertEqual(story_quality_coach.selectionner(SimpleNamespace(team="C", keys=None), elements), (None, 0))


class Coaching(EspaceAnalyse):
    def test_keys_entete_retour_par_element_et_aucun_fichier(self):
        self.remplir(3)
        code, sortie, erreur = self.lancer("coach", "--keys", "ZZA-002", "ZZA-001", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.splitlines()[0], ENTETE)
        self.assertIn("--- ZZA-001 ---\nstory-un [met] Conseil sur story-un\n", sortie)
        self.assertIn("--- ZZA-002 ---", sortie)
        self.assertLess(sortie.index("--- ZZA-001 ---"), sortie.index("--- ZZA-002 ---"))      # clé croissante
        self.assertNotIn("ZZA-003", sortie)
        self.assertEqual(self.nouveaux, set())
        self.assertEqual(sorted(self.analyse.coaching), ["ZZA-001", "ZZA-002"])
        self.assertEqual(self.analyse.coaching["ZZA-001"][0], ("story-un", "met", "Conseil sur story-un"))

    def test_la_requete_de_coaching(self):
        self.remplir(1)
        self.surcouche()
        self.lancer("coach", "--keys", "ZZA-001")
        requete = self.moteur.requetes[0]
        self.assertIn("feedback", requete["system"])
        self.assertIn("at most 80 characters", requete["system"])
        brut = json.dumps(requete, ensure_ascii=False)
        for interdit in ("ZZA-", EQUIPE_A, CLE_ANALYSE, "story-deux"):
            self.assertNotIn(interdit, brut)
        self.assertNotIn("tools", requete)
        self.assertEqual([c["code"] for c in json.loads(requete["messages"][0]["content"])["criteria"]],
                         ["story-un", "story-trois", "orga-role"])                    # même grille effective que l'audit
        self.assertEqual(self.moteur.entetes[0]["x-api-key"], CLE_ANALYSE)

    def test_cle_inconnue(self):
        self.remplir(1)
        code, sortie, _ = self.lancer("coach", "--keys", "ZZA-001", "ZZA-999", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("unknown items: 1", sortie)
        self.assertEqual(len(self.moteur.requetes), 1)
        self.assertNotIn("ZZA-999", sortie)

    def test_toutes_les_cles_inconnues(self):
        self.remplir(1)
        code, sortie, _ = self.lancer("coach", "--keys", "ZZA-998", "ZZA-999", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("unknown items: 2", sortie)
        self.assertEqual((self.moteur.requetes, self.invites), ([], []))

    def test_team(self):
        self.remplir(2)
        self.remplir(2, equipes=(EQUIPE_B,), debut=10)
        code, sortie, _ = self.lancer("coach", "--team", EQUIPE_B, "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(self.analyse.coaching), ["ZZA-010", "ZZA-011"])
        self.assertEqual(len(self.moteur.requetes), 2)
        self.assertNotIn(EQUIPE_B, sortie)

    def test_equipe_sans_element(self):
        self.remplir(1)
        code, sortie, _ = self.lancer("coach", "--team", "Equipe Zzabsente", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("no collected item for this team", sortie)
        self.assertEqual(self.moteur.requetes, [])

    def test_un_coaching_ne_change_aucun_verdict_d_audit(self):
        self.remplir(6)
        self.lancer("analyse")
        avant = [dict(v) for v in self.analyse.verdicts]
        audits = dict(self.analyse.audits)
        self.moteur.fabriquer = lambda requete: json.dumps({"verdicts": [
            {"criterion": c, "verdict": "not_met", "feedback": "zz"} for c in self.moteur.criteres(requete)]})
        code, _, _ = self.lancer("coach", "--team", EQUIPE_A)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.analyse.coaching), 6)
        self.assertEqual(self.analyse.verdicts, avant)             # les vues ne lisent que les verdicts d'audit : comptes inchangés
        self.assertEqual(self.analyse.audits, audits)
        self.lancer("analyse")
        self.assertEqual(len(self.moteur.requetes), 12)             # le coaching ne rend pas un élément « à jour » ni « à refaire »

    def test_un_nouveau_coaching_remplace_le_retour(self):
        self.remplir(1)
        self.lancer("coach", "--keys", "ZZA-001")
        self.moteur.fabriquer = lambda requete: json.dumps({"verdicts": [
            {"criterion": c, "verdict": "not_met", "feedback": "Nouveau"} for c in self.moteur.criteres(requete)]})
        self.lancer("coach", "--keys", "ZZA-001")
        self.assertEqual([l[1] for l in self.analyse.coaching["ZZA-001"]], ["not_met"] * 3)

    def test_retour_trop_long_refuse(self):
        self.remplir(1)
        self.moteur.fabriquer = lambda requete: json.dumps({"verdicts": [
            {"criterion": c, "verdict": "met", "feedback": "x" * 81} for c in self.moteur.criteres(requete)]})
        code, sortie, _ = self.lancer("coach", "--keys", "ZZA-001", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("engine answers refused: 1", sortie)
        self.assertEqual(self.analyse.coaching["ZZA-001"], [(c, "undetermined", "") for c in ("story-un", "story-deux", "story-trois")])
        self.assertNotIn("x" * 81, sortie)

    def test_retour_qui_n_est_pas_du_texte_refuse(self):
        self.remplir(1)
        self.moteur.fabriquer = lambda requete: json.dumps({"verdicts": [{"criterion": "story-un", "verdict": "met", "feedback": 3}]})
        _, sortie, _ = self.lancer("coach", "--keys", "ZZA-001", "--language", "en")
        self.assertIn("engine answers refused: 1", sortie)

    def test_sequences_de_terminal_retirees_du_retour(self):
        self.remplir(1)
        self.moteur.fabriquer = lambda requete: json.dumps({"verdicts": [
            {"criterion": c, "verdict": "met", "feedback": "\x1b[31mrouge\x1b]0;titre\x07"} for c in self.moteur.criteres(requete)]})
        _, sortie, _ = self.lancer("coach", "--keys", "ZZA-001", "--language", "en")
        self.assertNotIn("\x1b", sortie)
        self.assertIn("story-un [met] rouge", sortie)

    def test_erreur_du_moteur(self):
        self.remplir(2)
        self.moteur.statut = 503
        code, sortie, erreur = self.lancer("coach", "--team", EQUIPE_A, "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("analysis engine unreachable or in error, batch interrupted: HTTP 503", erreur)
        self.assertNotIn("zzcorps", sortie + erreur)
        self.assertEqual(self.analyse.coaching, {})

    def test_non_confirme(self):
        self.remplir(1)
        code, sortie, _ = self.lancer("coach", "--keys", "ZZA-001", "--language", "en", reponse="no")
        self.assertEqual(code, 0)
        self.assertIn("not confirmed: nothing sent", sortie)
        self.assertEqual((self.moteur.requetes, self.analyse.ecritures), ([], 0))

    def test_cle_absente(self):
        self.remplir(1)
        code, _, erreur = self.lancer("coach", "--keys", "ZZA-001", "--language", "en", cle=None)
        self.assertEqual(code, 3)
        self.assertIn("analysis key missing: create it in the Keychain", erreur)
        self.assertEqual((self.moteur.requetes, self.ouvertures_analyse), ([], 0))

    def test_rien_de_distinctif_de_la_surcouche(self):
        self.remplir(1)
        self.surcouche()
        resultat = self.lancer("coach", "--keys", "ZZA-001", "--language", "en")
        for chaine in DISTINCTIFS:
            self.assertNotIn(chaine, self.tout(resultat))


class Reaffichage(EspaceAnalyse):
    def test_show_sans_moteur_sans_cle_sans_confirmation(self):
        self.remplir(2)
        self.lancer("coach", "--keys", "ZZA-001", "ZZA-002")
        envoyees = len(self.moteur.requetes)
        ecritures = self.analyse.ecritures
        del self.service_demande
        code, sortie, _ = self.lancer("coach", "--keys", "ZZA-002", "--show", "--language", "en", cle=None, terminal=False)
        self.assertEqual(code, 0)
        self.assertEqual(sortie.splitlines()[0], ENTETE)
        self.assertIn("--- ZZA-002 ---\nstory-un [met] Conseil sur story-un", sortie)
        self.assertNotIn("ZZA-001", sortie)
        self.assertEqual((len(self.moteur.requetes), self.analyse.ecritures, self.invites), (envoyees, ecritures, []))
        self.assertFalse(hasattr(self, "service_demande"))           # la clé n'est même pas cherchée
        self.assertEqual(self.nouveaux, set())

    def test_show_par_equipe_et_rien_d_enregistre(self):
        self.remplir(1)
        code, sortie, _ = self.lancer("coach", "--team", EQUIPE_A, "--show", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("no coaching feedback stored for these items", sortie)
        code, sortie, _ = self.lancer("coach", "--team", "Equipe Zzabsente", "--show", "--language", "en")
        self.assertIn("no collected item for this team", sortie)
        code, sortie, _ = self.lancer("coach", "--keys", "ZZA-404", "--show", "--language", "en")
        self.assertIn("unknown items: 1", sortie)

    def test_show_et_dry_run_exclusifs(self):
        self.remplir(1)
        code, _, _ = self.lancer("coach", "--keys", "ZZA-001", "--show", "--dry-run")
        self.assertEqual(code, 2)
        code, _, _ = self.lancer("coach", "--team", EQUIPE_A, "--keys", "ZZA-001")
        self.assertEqual(code, 2)
        code, _, _ = self.lancer("coach")
        self.assertEqual(code, 2)
        self.assertEqual(self.ouvertures_analyse, 0)


if __name__ == "__main__":
    unittest.main()
