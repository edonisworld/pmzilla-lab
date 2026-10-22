"""
Tests des garde-fous de Q4 sur `analyse` et `coach` (change story-quality-audit, tâche 3.8 ; design D5, D7 ; spec story-quality-analysis :
estimation et confirmation, plafond, essai à blanc, porte de relecture d'équipe de la tâche 3.14, échantillon, session au terminal). Faux
serveur d'analyse, fausse clé, faux magasin (aide_analyse.py). Données inventées.
"""
from __future__ import annotations

import ast
import unittest

from aide_analyse import EspaceAnalyse
from aide_story_quality import EQUIPE_A, EQUIPE_B, TOOLS

EQUIPE_C = "Equipe Zzgamma"


class Confirmation(EspaceAnalyse):
    def test_estimation_imprimee_avant_la_premiere_requete(self):
        self.remplir(3)
        code, sortie, _ = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.invites), 1)
        question, deja_ecrit, requetes_avant = self.invites[0]
        self.assertEqual(question.strip(), "Send this batch? Type yes to confirm:")
        self.assertIn("batch: 3 items, about ", deja_ecrit)
        self.assertIn(" tokens, estimated cost ", deja_ecrit)
        self.assertTrue(deja_ecrit.rstrip().splitlines()[-1].endswith(" USD"))
        self.assertEqual(requetes_avant, 0)
        self.assertEqual(len(self.moteur.requetes), 3)

    def test_mot_de_confirmation_francais(self):
        self.remplir(1)
        code, _, _ = self.lancer("analyse", reponse="OUI ")
        self.assertEqual((code, len(self.moteur.requetes)), (0, 1))
        self.assertEqual(self.invites[0][0].strip(), "Envoyer ce lot ? Taper oui pour confirmer :")

    def test_autre_reponse_n_envoie_rien_et_n_ecrit_rien(self):
        self.remplir(2)
        self.surcouche()
        for reponse in ("non", "", "y", "oui", None):          # « oui » n'est pas le mot de confirmation en anglais ; None : fin de l'entrée
            with self.subTest(reponse):
                code, sortie, _ = self.lancer("analyse", "--language", "en", reponse=reponse)
                self.assertEqual(code, 0)
                self.assertIn("not confirmed: nothing sent", sortie)
                self.assertEqual(self.moteur.requetes, [])
                self.assertEqual((self.analyse.ecritures, self.analyse.empreintes), (0, {}))
                self.assertEqual(self.nouveaux, set())

    def test_sans_terminal_rien_n_est_envoye_code_3(self):
        self.remplir(2)
        for argv in (("analyse",), ("analyse", "--sample", "1"), ("coach", "--team", EQUIPE_A)):
            with self.subTest(argv):
                code, _, erreur = self.lancer(*argv, "--language", "en", terminal=False)
                self.assertEqual(code, 3)
                self.assertIn("confirmation needs a terminal: nothing sent", erreur)
                self.assertEqual(self.invites, [])
        self.assertEqual((self.moteur.requetes, self.analyse.ecritures), ([], 0))

    def test_aucune_option_ne_saute_la_confirmation(self):
        self.remplir(1)
        for option in ("--yes", "--force", "--no-confirm"):
            with self.subTest(option):
                code, _, _ = self.lancer("analyse", option)
                self.assertEqual(code, 2)
        self.assertEqual(self.moteur.requetes, [])


class Plafond(EspaceAnalyse):
    def test_au_dessus_du_plafond_exactement_le_plafond_puis_la_suite(self):
        self.remplir(12)
        code, sortie, _ = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.moteur.requetes), 10)
        self.assertIn("cap reached: 2 items left for the next launch", sortie)
        self.assertIn("batch: 10 items, about", sortie)
        self.assertEqual(self.analyse.audites(), {f"ZZA-{i:03d}" for i in range(1, 11)})     # par clé croissante
        code, sortie, _ = self.lancer("analyse", "--language", "en")
        self.assertEqual(len(self.moteur.requetes), 12)
        self.assertNotIn("cap reached", sortie)
        self.assertEqual(self.analyse.audites(), {f"ZZA-{i:03d}" for i in range(1, 13)})

    def test_plafond_de_coach(self):
        self.remplir(4)
        self.ecrire_moteur("    cap_per_launch: 3\n")
        code, sortie, _ = self.lancer("coach", "--team", EQUIPE_A, "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.moteur.requetes), 3)
        self.assertIn("cap reached: 1 items left for the next launch", sortie)

    def test_plafond_absent_ou_invalide_pour_coach_et_l_essai(self):
        self.remplir(1)
        for argv in (("coach", "--team", EQUIPE_A), ("analyse", "--dry-run"), ("coach", "--keys", "ZZA-001", "--dry-run")):
            for plafond in ("", "    cap_per_launch: -1\n", "    cap_per_launch: 2.5\n"):
                with self.subTest(argv=argv, plafond=plafond):
                    self.ecrire_moteur(plafond)
                    code, _, erreur = self.lancer(*argv, "--language", "en")
                    self.assertEqual(code, 3)
                    self.assertIn("cap per launch missing or invalid", erreur)
        self.assertEqual((self.moteur.requetes, self.ouvertures_analyse), ([], 0))


class EssaiABlanc(EspaceAnalyse):
    def test_essai_sans_cle_sans_envoi_sans_ecriture(self):
        self.remplir(5)
        self.surcouche()
        code, sortie, erreur = self.lancer("analyse", "--dry-run", "--language", "en", cle=None)
        self.assertEqual(code, 0, erreur)
        self.assertIn("batch: 5 items, about", sortie)
        self.assertEqual(sortie.rstrip().splitlines()[-1], "dry run: nothing sent")
        self.assertEqual(self.invites, [])                       # aucune confirmation demandée
        self.assertFalse(hasattr(self, "service_demande"))       # la clé n'est même pas cherchée
        self.assertEqual((self.moteur.requetes, self.analyse.ecritures, self.analyse.empreintes), ([], 0, {}))
        self.assertEqual(self.nouveaux, set())

    def test_essai_applique_le_plafond(self):
        self.remplir(12)
        _, sortie, _ = self.lancer("analyse", "--dry-run", "--language", "en")
        self.assertIn("cap reached: 2 items left for the next launch", sortie)
        self.assertIn("batch: 10 items, about", sortie)

    def test_essai_sans_terminal(self):
        self.remplir(1)
        code, sortie, _ = self.lancer("analyse", "--dry-run", "--language", "en", terminal=False)
        self.assertEqual(code, 0)
        self.assertIn("dry run: nothing sent", sortie)

    def test_essai_de_coach(self):
        self.remplir(2)
        code, sortie, _ = self.lancer("coach", "--team", EQUIPE_A, "--dry-run", "--language", "en", cle=None)
        self.assertEqual(code, 0)
        self.assertIn("batch: 2 items, about", sortie)
        self.assertEqual(sortie.rstrip().splitlines()[-1], "dry run: nothing sent")
        self.assertNotIn("Coaching results", sortie)
        self.assertEqual((self.moteur.requetes, self.analyse.ecritures, self.invites), ([], 0, []))

    def test_rien_a_faire_en_essai(self):
        code, sortie, _ = self.lancer("analyse", "--dry-run", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("batch: 0 items", sortie)
        self.assertIn("dry run: nothing sent", sortie)


class PorteDeRelecture(EspaceAnalyse):
    """Tâche 3.14 : aucun élément d'une équipe jamais relue n'est envoyé (design D5, « Per-team review gate »)."""

    def test_equipe_nouvelle_bloquee_puis_envoyee_apres_relecture(self):
        self.remplir(4)
        self.remplir(3, equipes=(EQUIPE_C,), debut=10)
        code, sortie, _ = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.moteur.requetes), 4)
        self.assertIn("blocked until their team is reviewed: 3 items, 1 teams", sortie)
        self.assertNotIn(EQUIPE_C, sortie)
        self.assertEqual(self.analyse.audites(), {"ZZA-001", "ZZA-002", "ZZA-003", "ZZA-004"})
        self.relues(EQUIPE_C)
        code, sortie, _ = self.lancer("analyse", "--language", "en")
        self.assertEqual(len(self.moteur.requetes), 7)
        self.assertNotIn("blocked", sortie)

    def test_element_a_deux_equipes_envoye_seulement_si_les_deux_sont_relues(self):
        self.analyse.relues = {EQUIPE_A}
        self.analyse.ajouter("ZZA-001", (EQUIPE_A, EQUIPE_B))
        self.analyse.ajouter("ZZA-002", (EQUIPE_A,))
        _, sortie, _ = self.lancer("analyse", "--language", "en")
        self.assertEqual(self.analyse.audites(), {"ZZA-002"})
        self.assertIn("blocked until their team is reviewed: 1 items, 1 teams", sortie)
        self.relues(EQUIPE_B)
        self.lancer("analyse")
        self.assertEqual(self.analyse.audites(), {"ZZA-001", "ZZA-002"})

    def test_element_sans_equipe_bloque(self):
        self.analyse.ajouter("ZZA-001", ())
        self.analyse.ajouter("ZZA-002", (EQUIPE_A,))
        _, sortie, _ = self.lancer("analyse", "--language", "en")
        self.assertEqual(self.analyse.audites(), {"ZZA-002"})
        self.assertIn("blocked until their team is reviewed: 1 items, 0 teams", sortie)

    def test_tout_bloque_rien_n_est_envoye_code_3(self):
        self.analyse.relues = set()
        self.remplir(3)
        for argv in (("analyse",), ("coach", "--team", EQUIPE_A), ("coach", "--keys", "ZZA-001")):
            with self.subTest(argv):
                code, sortie, erreur = self.lancer(*argv, "--language", "en")
                self.assertEqual(code, 3)
                self.assertIn("nothing to send: run review for each new team first", erreur)
                self.assertEqual(self.invites, [])
        self.assertEqual((self.moteur.requetes, self.analyse.ecritures), ([], 0))

    def test_bloques_ecartes_avant_le_plafond_et_l_estimation(self):
        self.ecrire_moteur("    cap_per_launch: 3\n")
        self.remplir(5, equipes=(EQUIPE_C,))                     # ZZA-001 à ZZA-005 : équipe jamais relue, avant les autres par clé
        self.remplir(3, debut=10)
        _, sortie, _ = self.lancer("analyse", "--language", "en")
        self.assertIn("blocked until their team is reviewed: 5 items, 1 teams", sortie)
        self.assertIn("batch: 3 items, about", sortie)
        self.assertNotIn("cap reached", sortie)
        self.assertEqual(self.analyse.audites(), {"ZZA-010", "ZZA-011", "ZZA-012"})

    def test_l_essai_compte_les_bloques_sans_jamais_etre_bloque(self):
        self.remplir(5)
        self.remplir(2, equipes=(EQUIPE_C,), debut=10)
        code, sortie, _ = self.lancer("analyse", "--dry-run", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("blocked until their team is reviewed: 2 items, 1 teams", sortie)
        self.assertIn("batch: 5 items, about", sortie)
        _, avec_bloques, _ = self.lancer("analyse", "--dry-run", "--language", "en")
        self.analyse.items = {k: v for k, v in self.analyse.items.items() if EQUIPE_C not in v["teams"]}
        _, sans_bloques, _ = self.lancer("analyse", "--dry-run", "--language", "en")
        ligne = [l for l in avec_bloques.splitlines() if l.startswith("batch:")]
        self.assertEqual(ligne, [l for l in sans_bloques.splitlines() if l.startswith("batch:")])   # estimation sans les bloqués
        self.analyse.relues = set()
        code, sortie, _ = self.lancer("analyse", "--dry-run", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("blocked until their team is reviewed: 5 items, 1 teams", sortie)
        self.assertEqual(self.moteur.requetes, [])


class Echantillon(EspaceAnalyse):
    """`analyse --sample <n> [--team <équipe>]` (design D7, O4), graine fixe."""

    def test_echantillon_global_sur_des_elements_deja_audites(self):
        self.remplir(10)
        self.remplir(10, equipes=(EQUIPE_B,), debut=50)
        self.ecrire_moteur("    cap_per_launch: 20\n")
        self.lancer("analyse")
        audits = [dict(v) for v in self.analyse.verdicts]
        self.assertEqual(len(self.moteur.requetes), 20)
        self.ecrire_moteur()
        code, sortie, _ = self.lancer("analyse", "--sample", "3", "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.moteur.requetes), 23)
        self.assertIn("sample analysis done: 3 items, 0 undetermined verdicts; counted in no view and no report", sortie)
        echantillon = [v for v in self.analyse.verdicts if v["sample"]]
        self.assertEqual(len({v["key"] for v in echantillon}), 3)
        self.assertEqual([v for v in self.analyse.verdicts if not v["sample"]], audits)     # aucun verdict d'audit touché

    def test_echantillon_d_une_equipe(self):
        self.remplir(5)
        self.remplir(5, equipes=(EQUIPE_B,), debut=50)
        self.lancer("analyse", "--sample", "2", "--team", EQUIPE_B)
        self.assertEqual(len(self.moteur.requetes), 2)
        self.assertEqual({v["key"] for v in self.analyse.verdicts}, {v["key"] for v in self.analyse.verdicts if v["key"] >= "ZZA-050"})
        self.assertEqual(len({v["key"] for v in self.analyse.verdicts}), 2)

    def test_graine_fixe_tirage_reproductible(self):
        self.remplir(10)
        self.lancer("analyse", "--sample", "3", graine=11)
        premier = {v["key"] for v in self.analyse.verdicts}
        self.analyse.verdicts.clear()
        self.lancer("analyse", "--sample", "3", graine=11)
        self.assertEqual({v["key"] for v in self.analyse.verdicts}, premier)

    def test_taille_invalide_code_2_avant_toute_requete(self):
        self.remplir(3)
        for taille in ("0", "-1", "trois", "2.5", "11"):
            with self.subTest(taille):
                code, _, erreur = self.lancer("analyse", "--sample", taille, "--language", "en")
                self.assertEqual(code, 2)
                self.assertIn("sample size must be a positive integer not above the cap", erreur)
        self.assertEqual((self.moteur.requetes, self.invites), ([], []))

    def test_team_sans_sample_erreur_d_usage(self):
        self.remplir(1)
        code, _, erreur = self.lancer("analyse", "--team", EQUIPE_A, "--language", "en")
        self.assertEqual(code, 2)
        self.assertIn("Usage error: --team", erreur)
        self.assertEqual(self.ouvertures_analyse, 0)

    def test_equipe_sans_element_collecte(self):
        self.remplir(2)
        code, sortie, _ = self.lancer("analyse", "--sample", "2", "--team", EQUIPE_C, "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("no collected item for this team", sortie)
        self.assertEqual((self.moteur.requetes, self.invites), ([], []))

    def test_echantillon_d_une_equipe_jamais_relue(self):
        self.remplir(3, equipes=(EQUIPE_C,))
        code, _, erreur = self.lancer("analyse", "--sample", "2", "--team", EQUIPE_C, "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("nothing to send: run review for each new team first", erreur)
        self.assertEqual(self.moteur.requetes, [])

    def test_essai_d_echantillon_sans_cle(self):
        self.remplir(6)
        code, sortie, _ = self.lancer("analyse", "--sample", "3", "--dry-run", "--language", "en", cle=None)
        self.assertEqual(code, 0)
        self.assertIn("batch: 3 items, about", sortie)
        self.assertEqual(sortie.rstrip().splitlines()[-1], "dry run: nothing sent")
        self.assertEqual((self.moteur.requetes, self.analyse.ecritures), ([], 0))

    def test_echantillon_non_confirme(self):
        self.remplir(3)
        code, sortie, _ = self.lancer("analyse", "--sample", "2", "--language", "en", reponse="no")
        self.assertEqual(code, 0)
        self.assertIn("not confirmed: nothing sent", sortie)
        self.assertEqual((self.moteur.requetes, self.analyse.ecritures), ([], 0))

    def test_lignes_d_echantillon_sans_cle_ni_equipe_ni_texte(self):
        self.remplir(2)
        self.remplir(1, genre="epic", debut=10)
        self.moteur.fabriquer = lambda requete: '{"verdicts": [{"criterion": "story-un", "verdict": "not_met"}]}'
        code, sortie, _ = self.lancer("analyse", "--sample", "3", "--language", "en")
        self.assertEqual(code, 0)
        lignes = [l for l in sortie.splitlines() if l.startswith("sample ") and not l.startswith("sample analysis done")]
        self.assertEqual(lignes, [
            "sample story-un: 0 met, 2 not met, 0 not applicable, 0 undetermined",
            "sample story-deux: 0 met, 0 not met, 0 not applicable, 2 undetermined",
            "sample story-trois: 0 met, 0 not met, 0 not applicable, 2 undetermined",
            "sample epic-un: 0 met, 0 not met, 0 not applicable, 1 undetermined",
            "sample epic-deux: 0 met, 0 not met, 0 not applicable, 1 undetermined",
        ])
        for interdit in ("ZZA-", EQUIPE_A, "Texte distinctif", "Titre"):
            self.assertNotIn(interdit, sortie)

    def test_un_nouvel_echantillon_remplace_le_precedent_et_l_audit_suit(self):
        self.remplir(2)
        self.lancer("analyse", "--sample", "2")
        self.lancer("analyse", "--sample", "2")
        self.assertEqual(len([v for v in self.analyse.verdicts if v["sample"]]), 6)          # 2 éléments x 3 critères, remplacés
        self.assertEqual(self.analyse.audites(), set())
        self.lancer("analyse")                                   # l'élément échantillonné reste à auditer
        self.assertEqual(len(self.moteur.requetes), 6)
        self.assertEqual(self.analyse.audites(), {"ZZA-001", "ZZA-002"})


class Session(EspaceAnalyse):
    def test_refus_en_session_pour_toutes_les_formes_avant_toute_lecture(self):
        self.remplir(1)
        environ = {**self.environ, "CLAUDECODE": "1"}
        for argv in (("analyse",), ("analyse", "--dry-run"), ("analyse", "--sample", "1", "--team", EQUIPE_A),
                     ("coach", "--team", EQUIPE_A), ("coach", "--keys", "ZZA-001", "--dry-run"), ("coach", "--keys", "ZZA-001", "--show")):
            with self.subTest(argv):
                code, sortie, erreur = self.lancer(*argv, "--language", "en", environ=environ)
                self.assertEqual(code, 3)
                self.assertIn("Refused inside a Claude Code session", erreur)
                self.assertEqual(sortie, "")
        self.assertEqual((self.ouvertures_analyse, self.moteur.requetes, self.invites), (0, [], []))
        self.assertFalse(hasattr(self, "service_demande"))


class SousProcessus(unittest.TestCase):
    """Revue 4.1, E3 (test statique) : aucun module tools/story_quality*.py n'importe ni n'appelle un sous-processus, ni `gh`, sauf
    la lecture de la clé d'analyse dans le Trousseau (`security find-generic-password`, `lire_cle` de story_quality_engine.py)."""

    INTERDITS_OS = ("system", "popen", "execv", "execve", "execl", "execlp", "execvp", "spawnv", "spawnl", "posix_spawn", "fork")
    MODULES_INTERDITS = ("subprocess", "pty", "commands")
    AUTORISE = ("story_quality_engine.py", "lire_cle", ["security", "find-generic-password", "-s", None, "-w"])

    def modules(self):
        fichiers = sorted(TOOLS.glob("story_quality*.py"))
        self.assertGreaterEqual(len(fichiers), 10)
        return [(f.name, ast.parse(f.read_text(encoding="utf-8"))) for f in fichiers]

    def test_aucun_import_de_sous_processus_hors_du_trousseau(self):
        for nom, arbre in self.modules():
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Import):
                    racines = [a.name.split(".")[0] for a in noeud.names]
                elif isinstance(noeud, ast.ImportFrom):
                    racines = [(noeud.module or "").split(".")[0]]
                    if racines == ["os"]:
                        self.assertFalse({a.name for a in noeud.names} & set(self.INTERDITS_OS), nom)
                else:
                    continue
                for racine in racines:
                    if racine == "subprocess" and nom == self.AUTORISE[0]:
                        continue
                    self.assertNotIn(racine, self.MODULES_INTERDITS, f"{nom}:{noeud.lineno}")

    def test_aucun_appel_de_sous_processus_sauf_security_ni_gh(self):
        appels = []
        for nom, arbre in self.modules():
            parents = {}
            for noeud in ast.walk(arbre):
                for enfant in ast.iter_child_nodes(noeud):
                    parents[enfant] = noeud
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Attribute) and isinstance(noeud.value, ast.Name):
                    self.assertFalse(noeud.value.id == "os" and noeud.attr in self.INTERDITS_OS, f"{nom}:{noeud.lineno}")
                if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
                    self.assertFalse(noeud.value == "gh" or noeud.value.startswith("gh "), f"{nom}:{noeud.lineno}")
                if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute) and isinstance(noeud.func.value, ast.Name)
                        and noeud.func.value.id == "subprocess"):
                    fonction = parents.get(noeud)
                    while fonction is not None and not isinstance(fonction, ast.FunctionDef):
                        fonction = parents.get(fonction)
                    commande = noeud.args[0] if noeud.args else None
                    elements = ([e.value if isinstance(e, ast.Constant) else None for e in commande.elts]
                                if isinstance(commande, ast.List) else None)
                    appels.append((nom, fonction.name if fonction else None, noeud.func.attr, elements))
        self.assertEqual(appels, [(self.AUTORISE[0], self.AUTORISE[1], "run", self.AUTORISE[2])])


if __name__ == "__main__":
    unittest.main()
