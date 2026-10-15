"""
Tests de l'étape runtree du script d'installation (change run-worktree, tâche 8.5) : le dossier d'exécution est créé après les hooks et avant les
liens, le serveur de la bibliothèque et les tâches launchd. Écrits avant le code ; run_worktree.sh du décor est un simulacre à état.

    python3 -W ignore -m unittest discover -s tests/install_lab -p "test_runtree.py" -q -f
"""
import unittest

from aide_install import CasDeBase


class Base(CasDeBase):
    def setUp(self):
        super().setUp()
        self.fx.drapeau("runtree-ok", False)       # le décor part avec un dossier d'exécution propre : ici, on le retire
        self.fx.drapeau("hooks-ok")                # l'étape dépend des hooks et du dépôt : l'un et l'autre prêts
        tools = self.fx.racine / "tools"
        (tools / "hooks").mkdir(exist_ok=True)
        (tools / "hooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
        for fichier in list(tools.glob("*.sh")) + [tools / "hooks" / "pre-commit"]:
            fichier.chmod(0o755)
        self.fx.simulacre("xattr", 'case "$1" in -l) exit 0 ;; esac')

    def lancer(self, *args, **kw):
        return self.fx.lancer("--mode", "fresh", "--step", "runtree", *args, **kw)

    def appels_run_worktree(self, p):
        return [a for a in p.appels if a.startswith("run_worktree.sh")]


class EtapeRunTree(Base):
    def test_machine_neuve_cree_puis_verifie_l_etat(self):
        p = self.lancer(reponses="y\n")
        self.assertEqual(p.code, 0, p.texte)
        appels = self.appels_run_worktree(p)
        self.assertIn("run_worktree.sh create", appels)
        self.assertEqual(appels[-1], "run_worktree.sh status")
        self.assertLess(appels.index("run_worktree.sh create"), len(appels) - 1)
        self.assertTrue(self.fx.a_drapeau("runtree-ok"))
        self.assertNotIn("run_worktree.sh update", appels)

    def test_dossier_propre_au_sommet_de_main_est_ignore(self):
        self.fx.drapeau("runtree-ok")
        p = self.lancer()
        self.assertIn("step runtree: already done, skipped", p.lignes())
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.appels_run_worktree(p), ["run_worktree.sh status"])
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])

    def test_dossier_en_retard_sur_main_donne_une_action_manuelle_sans_mise_a_jour(self):
        self.fx.drapeau("runtree-ok")
        self.fx.drapeau("runtree-retard")
        p = self.lancer(reponses="y\n")
        self.assertEqual(p.code, 4, p.texte)
        self.assertIn("bash tools/run_worktree.sh update", p.texte)
        self.assertIn("manual action needed", p.texte)
        appels = self.appels_run_worktree(p)
        self.assertNotIn("run_worktree.sh update", appels)
        self.assertNotIn("run_worktree.sh create", appels)
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])

    def test_refus_par_defaut_ne_cree_rien(self):
        avant = self.fx.empreinte()
        p = self.lancer(reponses="\n")
        self.assertEqual(p.code, 4, p.texte)
        self.assertIn("step runtree: declined", p.texte)
        self.assertNotIn("run_worktree.sh create", self.appels_run_worktree(p))
        self.assertFalse(self.fx.a_drapeau("runtree-ok"))
        self.assertEqual(self.fx.empreinte(), avant)

    def test_passage_a_blanc_ne_cree_rien(self):
        avant = self.fx.empreinte()
        p = self.lancer("--dry-run")
        self.assertEqual(p.code, 0, p.texte)
        self.assertTrue(any(l.startswith("dry run: would run") and "run_worktree.sh create" in l for l in p.lignes()), p.texte)
        self.assertNotIn("run_worktree.sh create", self.appels_run_worktree(p))
        self.assertEqual(self.fx.empreinte(), avant)

    def test_echec_de_la_creation(self):
        self.fx.drapeau("runtree-create-echec")
        p = self.lancer(reponses="y\n")
        self.assertEqual(p.code, 1, p.texte)
        self.assertIn("step runtree: failed", p.texte)

    def test_ne_met_jamais_a_jour_ni_ne_remet_a_zero(self):
        for retard in (False, True):
            self.fx.drapeau("runtree-ok")
            self.fx.drapeau("runtree-retard", retard)
            p = self.lancer(reponses="y\n")
            self.assertNotIn("run_worktree.sh update", self.appels_run_worktree(p))


class Ordre(Base):
    def test_l_etape_vient_apres_les_hooks_et_avant_les_liens_le_serveur_et_les_taches(self):
        p = self.fx.lancer("--mode", "fresh", "--list")
        noms = [l.split()[0] for l in p.lignes() if l.strip()]
        self.assertEqual(p.code, 0, p.texte)
        i = noms.index("runtree")
        self.assertGreater(i, noms.index("hooks"))
        for suivante in ("links", "mcp", "launchd"):
            self.assertLess(i, noms.index(suivante), suivante)

    def test_les_liens_attendent_le_dossier_d_execution(self):
        self.fx.drapeau("hooks-ok")
        p = self.fx.lancer("--mode", "fresh", "--step", "links", reponses="y\n")
        self.assertIn("deferred (waiting for step runtree)", p.texte)
        self.assertEqual([a for a in p.appels if a.startswith("install_links.sh") and "--verify" not in a], [])
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])

    def test_passage_complet_cree_le_dossier_avant_les_liens(self):
        self.fx.drapeau("hooks-ok")
        p = self.fx.lancer("--mode", "fresh", "--start-at", "hooks", reponses="y\n" * 10)
        liens = [i for i, a in enumerate(p.appels) if a.startswith("install_links.sh") and "--verify" not in a]
        self.assertTrue(liens, p.appels)
        self.assertLess(p.appels.index("run_worktree.sh create"), liens[0])


if __name__ == "__main__":
    unittest.main()
