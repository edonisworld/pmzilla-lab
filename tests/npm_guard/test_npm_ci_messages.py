"""La ligne de refus de `npm ci` (change npm-ci-session, design D7) : les phrases et la phrase de fin, caractère pour caractère, leur ordre, ce
que la ligne ne contient jamais, et « vérification impossible » sur une exception ou un dépassement de temps, sans trace d'erreur.
Les phrases ci-dessous sont recopiées de la conception, non lues des constantes du module : c'est ce que la comparaison vérifie.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/npm_guard -q -f
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_npm_ci import AvecDepot, npm_ci_conditions  # noqa: E402

PHRASES_DE_D7 = {
    "forme": "forme non admise (aucune option, aucun alias, rien avant ni après)",
    "worktree": "pas dans le dossier mothra d'un worktree (espace de travail, dossier d'exécution ou autre dossier)",
    "fin": "fin en cours (verrou de fin présent)",
    "origine": "état Git illisible ou origin/main introuvable",
    "non-commite": "modification non commitée dans le worktree",
    "verrou": "package-lock.json différent de origin/main : <chemin>",
    "paquet": "package.json différent de origin/main : <chemin>",
    "npmrc": ".npmrc absent de origin/main ou différent : <chemin>",
    "impossible": "vérification impossible",
}
LIGNE_DE_D7 = ("garde npm : npm ci refusé : <phrases>. Une session lance npm ci seulement sous la forme « npm ci » ou « cd <dossier> && npm ci », "
               "dans le dossier mothra d'un worktree propre, sans fin en cours, avec les package.json, package-lock.json et .npmrc de mothra/ "
               "identiques à origin/main. Un verrou modifié, avec son npm install et son audit, reste à l'auteur.")
ORDRE_DE_D7 = ("forme", "worktree", "fin", "origine", "non-commite", "verrou", "paquet", "npmrc", "impossible")
PREFIXE = "garde npm : npm ci refusé : "


class Constantes(unittest.TestCase):
    def test_les_phrases_sont_celles_de_la_conception(self):
        self.assertEqual(npm_ci_conditions.PHRASES, PHRASES_DE_D7)

    def test_le_prefixe_et_la_phrase_de_fin(self):
        self.assertEqual(npm_ci_conditions.PREFIXE, PREFIXE)
        self.assertEqual(npm_ci_conditions.PREFIXE + "<phrases>" + npm_ci_conditions.FIN_DE_MESSAGE, LIGNE_DE_D7)

    def test_l_ordre_des_phrases(self):
        self.assertEqual(npm_ci_conditions.ORDRE, ORDRE_DE_D7)
        self.assertEqual(tuple(npm_ci_conditions.PHRASES), ORDRE_DE_D7)

    def test_message_depuis_une_liste_de_conditions(self):
        liste = [("non-commite", None), ("verrou", "mothra/package-lock.json"), ("npmrc", "mothra/.npmrc")]
        attendu = (PREFIXE + "modification non commitée dans le worktree; package-lock.json différent de origin/main : mothra/package-lock.json; "
                   ".npmrc absent de origin/main ou différent : mothra/.npmrc" + LIGNE_DE_D7.split("<phrases>", 1)[1])
        self.assertEqual(npm_ci_conditions.message(liste), attendu)

    def test_les_phrases_sont_jointes_par_point_virgule_et_espace(self):
        texte = npm_ci_conditions.message([("fin", None), ("origine", None)])
        self.assertIn("fin en cours (verrou de fin présent); état Git illisible ou origin/main introuvable. Une session", texte)

    def test_le_chemin_est_nettoye_des_caracteres_de_controle(self):
        texte = npm_ci_conditions.message([("paquet", "mothra/a\nb/package.json")])
        self.assertNotIn("\nb", texte)
        self.assertEqual(texte.count("\n"), 0)

    def test_le_repli_de_la_garde_porte_la_phrase_de_fin_de_d7(self):
        """M1 : copie de repli dans la garde ; source : le module (un écart entre les deux échoue ici)."""
        import npm_guard
        self.assertEqual(npm_guard.MESSAGE_NPM_CI_ILLISIBLE, npm_ci_conditions.message([("impossible", None)]))

    def test_le_module_est_seul_a_dire_les_phrases(self):
        """Source des phrases : le module ; la garde ne les recopie pas (un écart se verrait ici)."""
        source = (Path(__file__).resolve().parents[2] / "tools" / "npm_guard.py").read_text(encoding="utf-8")
        for phrase in ("forme non admise", "verrou de fin présent", "modification non commitée", "différent de origin/main"):
            self.assertNotIn(phrase, source, phrase)


class DansLaSortie(AvecDepot):
    def test_l_ordre_des_phrases_dans_la_ligne(self):
        self.depot.verrou_de_fin()
        self.depot.ecrire(self.wt, "mothra/package-lock.json", '{"x": 1}\n')
        self.depot.ecrire(self.wt, "mothra/package.json", '{"x": 2}\n')
        self.depot.ecrire(self.wt, "mothra/.npmrc", "x=1\n")
        _, erreur = self.lancer("npm ci")
        positions = [erreur.index(p) for p in ("fin en cours (verrou de fin présent)", "modification non commitée dans le worktree",
                                              "package-lock.json différent de origin/main : mothra/package-lock.json",
                                              "package.json différent de origin/main : mothra/package.json",
                                              ".npmrc absent de origin/main ou différent : mothra/.npmrc")]
        self.assertEqual(positions, sorted(positions))

    def test_une_phrase_par_fichier_different(self):
        self.depot.ecrire(self.wt, "mothra/package-lock.json", '{"x": 1}\n')
        self.depot.ecrire(self.wt, "mothra/serveur/package-lock.json", '{"x": 2}\n')
        self.depot.valider(self.wt)
        _, erreur = self.lancer("npm ci")
        self.assertEqual(erreur.count("package-lock.json différent de origin/main"), 2)
        self.assertLess(erreur.index("mothra/package-lock.json"), erreur.index("mothra/serveur/package-lock.json"))

    def test_une_seule_ligne_qui_finit_par_la_phrase_de_fin(self):
        self.depot.ecrire(self.wt, "README.md", "modifié\n")
        _, erreur = self.lancer("npm ci")
        self.assertEqual(erreur.count("\n"), 1)
        self.assertTrue(erreur.endswith(LIGNE_DE_D7.split("<phrases>", 1)[1] + "\n"))

    def test_forme_arrete_seule(self):
        self.depot.ecrire(self.wt, "README.md", "modifié\n")
        self.depot.verrou_de_fin()
        _, erreur = self.lancer("npm ci --offline")
        self.assertEqual(erreur, PREFIXE + PHRASES_DE_D7["forme"] + LIGNE_DE_D7.split("<phrases>", 1)[1] + "\n")

    def test_worktree_arrete_seul(self):
        self.depot.ecrire(self.depot.repo, "README.md", "modifié\n")
        self.depot.verrou_de_fin()
        _, erreur = self.lancer("npm ci", cwd=self.depot.repo / "mothra")
        self.assertEqual(erreur, PREFIXE + PHRASES_DE_D7["worktree"] + LIGNE_DE_D7.split("<phrases>", 1)[1] + "\n")

    def test_le_chemin_est_relatif_a_la_racine_du_worktree_et_rien_d_absolu_n_est_imprime(self):
        self.depot.ecrire(self.wt, "mothra/serveur/package.json", '{"x": 1}\n')
        self.depot.valider(self.wt)
        _, erreur = self.lancer(f"cd {self.mothra} && npm ci", cwd=self.depot.repo)
        self.assertIn("package.json différent de origin/main : mothra/serveur/package.json", erreur)
        self.assertNotIn(str(self.wt), erreur)
        self.assertNotIn(self._tmp.name, erreur)
        self.assertNotIn(str(self.mothra), erreur)
        self.assertNotIn("cd ", erreur.split(". Une session", 1)[0])

    def test_la_ligne_ne_reprend_ni_la_commande_ni_le_contenu_d_un_fichier(self):
        self.depot.ecrire(self.wt, "mothra/package.json", '{"scripts": {"postinstall": "SECRET_CONTENU_12345"}}\n')
        self.depot.valider(self.wt)
        _, erreur = self.lancer("npm ci --token=SECRET_ARGUMENT_67890")
        self.assertNotIn("SECRET", erreur)
        _, erreur = self.lancer("npm ci")
        self.assertNotIn("SECRET", erreur)
        self.assertNotIn("postinstall", erreur)

    def test_aucun_code_nouveau_zero_ou_deux(self):
        self.assertEqual(self.lancer("npm ci")[0], 0)
        self.assertEqual(self.lancer("npm ci --offline")[0], 2)


class VerificationImpossible(AvecDepot):
    PHRASE = PREFIXE + "vérification impossible" + LIGNE_DE_D7.split("<phrases>", 1)[1] + "\n"

    def test_exception_pendant_une_lecture_de_git(self):
        with mock.patch.object(npm_ci_conditions.subprocess, "run", side_effect=RuntimeError("boum")):
            code, erreur = self.lancer("npm ci")
        self.assertEqual((code, erreur), (2, self.PHRASE))

    def test_depassement_de_temps_d_une_lecture(self):
        with mock.patch.object(npm_ci_conditions.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 1)):
            code, erreur = self.lancer("npm ci")
        self.assertEqual((code, erreur), (2, self.PHRASE))
        self.assertNotIn("Traceback", erreur)

    def test_temps_total_epuise(self):
        with mock.patch.object(npm_ci_conditions, "DELAI_TOTAL", 0.0):
            code, erreur = self.lancer("npm ci")
        self.assertEqual((code, erreur), (2, self.PHRASE))

    def test_exception_dans_le_module_des_conditions(self):
        with mock.patch.object(npm_ci_conditions, "echecs", side_effect=ZeroDivisionError):
            code, erreur = self.lancer("npm ci")
        self.assertEqual((code, erreur), (2, self.PHRASE))
        self.assertNotIn("Traceback", erreur)

    def test_exception_dans_la_forme(self):
        with mock.patch.object(npm_ci_conditions, "forme_admise", side_effect=MemoryError):
            code, erreur = self.lancer("npm ci")
        self.assertEqual((code, erreur), (2, self.PHRASE))

    def test_exception_dans_le_dossier_des_worktrees(self):
        with mock.patch.object(npm_ci_conditions, "_dossier_des_worktrees", side_effect=OSError):
            code, erreur = self.lancer("npm ci")
        self.assertEqual((code, erreur), (2, self.PHRASE))

    def test_verifier_ne_laisse_passer_aucune_exception(self):
        with mock.patch.object(npm_ci_conditions.os, "walk", side_effect=PermissionError):
            self.assertEqual(npm_ci_conditions.verifier(self.mothra, self.depot.worktrees), [("impossible", None)])


if __name__ == "__main__":
    unittest.main()
