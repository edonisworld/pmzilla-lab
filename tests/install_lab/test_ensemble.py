"""
Test d'ensemble du script d'installation (mode fresh) : toutes les étapes ensemble, avec des simulacres à état, dans un décor factice.

    uv run python -W ignore -m unittest discover -s tests/install_lab -p "test_ensemble.py" -q -f

Une machine « neuve » : les outils sont là (Homebrew, Claude Code, Docker, Ollama et ses modèles), mais ni les hooks, ni les liens, ni la
base, ni les tâches launchd, ni le serveur MCP ne sont installés. Un premier passage (toutes les confirmations acceptées) installe tout ;
un second ne change plus rien. Aucun effet réel : tout passe par les simulacres du décor.
"""
import unittest

from aide_install import CasDeBase


def machine_neuve(fx):
    etat = '"$INSTALL_LAB_ETAT"'
    fx.simulacre("brew", "exit 0")
    fx.simulacre("node", "echo v22")      # git et uv répondent déjà (décor et simulacre ci-dessous)
    fx.simulacre("claude", f'''case "$*" in
  "--version") echo 1.0 ;;
  "mcp get pmzilla-library") [ -e {etat}/mcp-ok ] && {{ echo "Status: Connected"; echo "Command: $HOME/PMZilla-Lab/pmzilla_lab_library.py"; exit 0; }}; exit 1 ;;
  "mcp add"*) : > {etat}/mcp-ok; exit 0 ;;
  *) exit 0 ;;
esac''')
    fx.simulacre("ollama", 'case "$1" in list) echo "NAME ID SIZE MODIFIED"; echo "bge-test:latest abc 1GB now"; echo "gemma-test:1b def 2GB now" ;; esac; exit 0')
    fx.simulacre("docker", f'''case "$*" in
  info) exit 0 ;;
  "compose ps"*) [ -e {etat}/db-up ] && echo "db   Up 2 minutes (healthy)"; exit 0 ;;
  *) exit 0 ;;
esac''')
    fx.simulacre("uv", f'''case "$*" in
  *"migrate --dry-run"*) [ -e {etat}/db-migre ] && echo "Rien à appliquer." || echo "1 migration à appliquer"; exit 0 ;;
  *"db.py migrate"*) : > {etat}/db-migre; exit 0 ;;
  *) exit 0 ;;
esac''')
    fx.simulacre("launchctl", f'''eti=$(basename "$3" .plist 2>/dev/null)
case "$1" in
  print) [ -e {etat}/launchctl-$(basename "$2") ] && exit 0; exit 113 ;;
  bootstrap) : > {etat}/launchctl-$(basename "$3" .plist); exit 0 ;;
  *) exit 0 ;;
esac''')


class Ensemble(CasDeBase):
    def setUp(self):
        super().setUp()
        machine_neuve(self.fx)

    def test_premier_passage_installe_tout_puis_le_second_ne_change_rien(self):
        premier = self.fx.lancer("--mode", "fresh", reponses="y\n" * 40)
        self.assertEqual(premier.code, 0, premier.texte)
        self.assertIn("installation complete", premier.texte)
        self.assertTrue(self.fx.a_drapeau("hooks-ok") and self.fx.a_drapeau("links-ok") and self.fx.a_drapeau("db-up"))
        self.assertTrue(self.fx.a_drapeau("mcp-ok"))
        self.assertEqual(len(list((self.fx.maison / "Library" / "LaunchAgents").glob("*.plist"))), 2)

        second = self.fx.lancer("--mode", "fresh")
        self.assertEqual(second.code, 0, second.texte)
        self.assertEqual(self.fx.appels_qui_changent(second.appels), [], second.appels)
        for etape in ("prereqs", "repo", "hooks", "links", "database", "launchd", "mcp"):
            self.assertIn(f"step {etape}: already done, skipped", second.texte, etape)

    def test_passage_a_blanc_complet_ne_change_rien_et_sort_en_zero(self):
        avant = self.fx.empreinte()
        p = self.fx.lancer("--mode", "fresh", "--dry-run")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.fx.empreinte(), avant)
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [], p.appels)
        self.assertIn("dry run: would run", p.texte)

    def test_tout_refuser_ne_change_rien_et_sort_en_quatre(self):
        avant = self.fx.empreinte()
        p = self.fx.lancer("--mode", "fresh", reponses="\n" * 40)
        self.assertEqual(p.code, 4, p.texte)
        self.assertIn("installation incomplete", p.texte)
        self.assertEqual(self.fx.empreinte(), avant)
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [], p.appels)

    def test_mot_de_passe_de_la_base_absent_laisse_une_action_manuelle(self):
        self.fx.drapeau("db-sans-mot-de-passe")
        p = self.fx.lancer("--mode", "fresh", reponses="y\n" * 40)
        self.assertEqual(p.code, 4, p.texte)
        self.assertIn("manual action needed", p.texte)
        self.assertIn("security add-generic-password -s pmzilla-test-db", p.texte)
        self.assertTrue(self.fx.a_drapeau("mcp-ok"), "le serveur est enregistré, avec le backend fichier")
        self.assertTrue(any("--backend sqlite" in a for a in p.appels_de("claude")), p.appels)


if __name__ == "__main__":
    unittest.main()
