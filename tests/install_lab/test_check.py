"""
Tests de l'étape check du script d'installation (tools/install_lab_check.py) : contrôles en lecture seule.

    uv run python -W ignore -m unittest discover -s tests/install_lab -p "test_check.py" -q -f
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from aide_install import TOOLS_REELS, CasDeBase

sys.path.insert(0, str(TOOLS_REELS))
import install_lab_check as check      # noqa: E402
import install_lab_context as c        # noqa: E402


class EtapeCheck(CasDeBase):
    def setUp(self):
        super().setUp()
        self.fx.simulacre("ollama", 'echo "NAME ID SIZE"; echo "bge-test:latest abc 1GB"; echo "gemma-test:1b def 18GB"')
        self.fx.simulacre("claude", 'echo "pmzilla-library:"; echo "  Status: Connected"')
        self.fx.simulacre("docker", 'echo "NAME STATUS"; echo "db Up (healthy)"')
        self.fx.simulacre("uv")
        self.fx.simulacre("launchctl")
        self.fx.simulacre("git")
        self.fx.drapeau("hooks-ok")
        self.fx.drapeau("links-ok")
        agents = self.fx.maison / "Library" / "LaunchAgents"
        agents.mkdir(parents=True)
        for label in ("com.pmzilla.watch", "com.pmzilla.db-backup"):
            (agents / f"{label}.plist").write_text("x", encoding="utf-8")

    def lancer(self, *extra):
        return self.fx.lancer("--mode", "fresh", "--step", "check", *extra)

    def test_tous_les_controles_passent(self):
        p = self.lancer()
        self.assertEqual(p.code, 0, p.texte)
        attendus = ["ollama list", "claude mcp get pmzilla-library", "install_hooks.sh --verify", "install_links.sh --verify",
                    "launchctl print gui/", "docker compose ps", "db.py status", "git status --short"]
        for a in attendus:
            self.assertTrue(any(a in x for x in p.appels), (a, p.appels))
        etiquettes = [x for x in p.appels if x.startswith("launchctl print")]
        self.assertEqual(len(etiquettes), 2)
        self.assertTrue(any(x.endswith("com.pmzilla.watch") for x in etiquettes))
        self.assertTrue(any(x.endswith("com.pmzilla.db-backup") for x in etiquettes))
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])

    def test_affiche_sans_lancer_les_commandes_longues(self):
        p = self.lancer()
        texte = p.texte
        for morceau in ("run_all.sh", "wake.py", "echarts.sha256"):
            self.assertIn(morceau, texte)
        self.assertFalse(any("run_all" in a or "wake.py" in a or "shasum" in a for a in p.appels), p.appels)

    def test_seconde_passe_rejoue_les_controles(self):
        self.lancer()
        p = self.lancer()
        self.assertNotIn("already done", p.texte)
        self.assertEqual(p.code, 0)
        self.assertTrue(p.appels_de("git status --short"))

    def test_passage_a_blanc_ne_lance_aucun_controle(self):
        avant = self.fx.empreinte()
        p = self.lancer("--dry-run")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(p.appels, [])
        self.assertEqual(self.fx.empreinte(), avant)
        self.assertIn("dry run: would run ollama list", p.lignes())
        self.assertIn("dry run: would run git status --short", p.lignes())

    def test_controle_en_echec_nomme_le_premier_et_arrete_en_code_1(self):
        self.fx.drapeau("links-ok", False)
        self.fx.regles("claude", [("get", 1, "")])
        p = self.lancer()
        self.assertEqual(p.code, 1, p.texte)
        self.assertIn("step check: failed", p.texte)
        self.assertIn("claude mcp get pmzilla-library", p.texte)       # premier en échec, avant links --verify
        self.assertNotIn("install_links.sh --verify failed", p.texte)

    def test_modele_absent_est_un_echec(self):
        self.fx.simulacre("ollama", 'echo "NAME"; echo "bge-test:latest abc 1GB"')
        p = self.lancer()
        self.assertEqual(p.code, 1, p.texte)
        self.assertIn("ollama list", p.texte)
        self.assertIn("gemma-test:1b", p.texte)

    def test_serveur_non_connecte_est_un_echec(self):
        self.fx.simulacre("claude", 'echo "pmzilla-library:"; echo "  Status: Failed to connect"')
        p = self.lancer()
        self.assertEqual(p.code, 1, p.texte)
        self.assertIn("claude mcp get", p.texte)

    def test_aucun_travail_sur_tache_non_installee(self):
        (self.fx.maison / "Library" / "LaunchAgents" / "com.pmzilla.db-backup.plist").unlink()
        p = self.lancer()
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(len([x for x in p.appels if x.startswith("launchctl print")]), 1)

    def test_tache_installee_non_chargee_echoue(self):
        self.fx.regles("launchctl", [("com.pmzilla.watch", 113, "")])
        p = self.lancer()
        self.assertEqual(p.code, 1, p.texte)
        self.assertIn("launchctl print", p.texte)

    def executer_direct(self, etat):
        ctx = c.Contexte(racine=self.fx.racine, maison=self.fx.maison, etat=etat)
        with mock.patch.dict(os.environ, self.fx.environnement()), redirect_stdout(io.StringIO()):
            return check.executer_check(ctx), self.fx.lire_appels()

    def test_base_reportee_saute_les_controles_de_la_base(self):
        self.fx.simulacre("docker", "exit 1")
        r, appels = self.executer_direct({"base_ok": False})
        self.assertEqual(r.etat, c.FAIT, r)
        self.assertFalse(any(a.startswith("docker compose") or "db.py" in a for a in appels), appels)

    def test_base_prete_controle_la_base(self):
        self.fx.simulacre("docker", "exit 1")
        r, appels = self.executer_direct({"base_ok": True})
        self.assertEqual(r.etat, c.ECHEC)
        self.assertIn("docker compose ps", r.detail)

    def test_ollama_reporte_saute_la_liste_des_modeles(self):
        self.fx.simulacre("ollama", "exit 1")
        r, appels = self.executer_direct({"ollama_ok": False})
        self.assertEqual(r.etat, c.FAIT, r)
        self.assertFalse(any(a.startswith("ollama") for a in appels))


if __name__ == "__main__":
    unittest.main()
