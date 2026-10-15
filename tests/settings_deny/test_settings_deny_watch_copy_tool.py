"""Règles `deny` de tools/watch_copy.py (change db-lot5-watch-triage, design D12, tâche 9.1).

L'outil copie les anciens fichiers d'état de la veille dans la base, écrit dans la base et compare les deux côtés : seul l'utilisateur
le lance, dans le Terminal. Chaque façon de le lancer est refusée à la session, `--help` et `--dry-run` compris (une règle ne
distingue pas les options), avec chaque lanceur et chaque façon d'écrire le chemin, y compris le lancement direct du fichier. Lire le
script, lancer sa suite (anciens fichiers inventés, cible en mémoire) et lancer `watch_triage.py week` restent permis.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json. Limite : une règle `deny` n'arrête pas une ligne de Python
qui ouvrirait la base, ni un lancement précédé de `cd … &&`, ni `bash -c '…'` ; la session n'en écrit jamais.

Les règles à ajouter à `permissions.deny` de .claude/settings.json (REGLES_ATTENDUES) sont ajoutées par l'utilisateur, jamais par la session.
"""
import itertools
import json
import unittest

from test_settings_deny import Base, CHEMINS, LANCEURS, RACINE

OPTIONS = ("", " copy", " copy --dry-run", " copy --replace", " copy --replace --dry-run", " verify", " compare", " parity",
           " parity --day 2026-10-13", " --help", " copy --help", " -h", " copy --calibration Watch-Lab/_calibration.csv",
           " copy --watch-sqlite a.sqlite --triage-sqlite b.sqlite --dbname pmzilla_test_x")
SCRIPT = "watch_copy.py"
LANCEMENTS_DIRECTS = ("tools/watch_copy.py", "./tools/watch_copy.py", "~/PMZilla-Lab/workspace/tools/watch_copy.py",
                      "$HOME/PMZilla-Lab/workspace/tools/watch_copy.py", "/Users/quelquun/PMZilla-Lab/workspace/tools/watch_copy.py")

REGLES_ATTENDUES = [
    "Bash(uv run *watch_copy.py*)",
    "Bash(python *watch_copy.py*)",
    "Bash(python3 *watch_copy.py*)",
    "Bash(tools/watch_copy.py*)",
    "Bash(./tools/watch_copy.py*)",
    "Bash(~/*tools/watch_copy.py*)",
    "Bash($HOME/*tools/watch_copy.py*)",
    "Bash(/*tools/watch_copy.py*)",
]


class OutilDeCopieDeLaVeille(Base):
    def test_les_regles_attendues_sont_dans_settings_json(self):
        deny = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["deny"]
        for regle in REGLES_ATTENDUES:
            self.assertEqual(deny.count(regle), 1, regle)

    def test_chaque_lancement_est_refuse(self):
        for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS, OPTIONS):
            commande = f"{lanceur} {chemin.format(s=SCRIPT)}{option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_lancement_direct_du_fichier(self):
        for chemin, option in itertools.product(LANCEMENTS_DIRECTS, OPTIONS):
            commande = f"{chemin}{option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_lanceurs_avec_options_de_l_interpreteur(self):
        for commande in ("uv run --isolated tools/watch_copy.py copy", "uv run --with pyyaml python tools/watch_copy.py verify",
                         "uv run --directory tools watch_copy.py compare", "python3 -W ignore tools/watch_copy.py parity",
                         "python -I ~/PMZilla-Lab/workspace/tools/watch_copy.py copy --dry-run",
                         "uv run -q $HOME/PMZilla-Lab/workspace/tools/watch_copy.py copy --replace",
                         "uv run --with 'psycopg[binary]' --with numpy python3 tools/watch_copy.py parity --day 2026-10-13"):
            self.assertTrue(self.interdite(commande), commande)

    def test_ce_que_la_session_garde(self):
        for commande in ("cat tools/watch_copy.py", "head -60 tools/watch_copy.py", "grep -n 'def cmd_' tools/watch_copy.py",
                         "sed -n 1,40p tools/watch_copy.py", "wc -l tools/watch_copy.py", "cat tools/watch_copy.py.lock",
                         "git log --oneline -3 -- tools/watch_copy.py", "git diff --stat -- tools/watch_copy.py",
                         "uv lock --script tools/watch_copy.py",
                         "bash tests/run_all.sh watch_copy", "bash tests/run_all.sh --staged",
                         "python3 -W ignore -m unittest discover -s tests/watch_copy -q -f",
                         'uv run --with pyyaml --with "psycopg[binary]" --with numpy python -W ignore -m unittest discover -s tests/watch_copy -q -f 2>&1 | tail -4',
                         "python3 -W ignore -m unittest discover -s tests/watch_copy -p test_copie_sans_base.py -q",
                         "python3 -W ignore -m unittest discover -s tests/settings_deny -p test_settings_deny_watch_copy_tool.py -q",
                         "ls tests/watch_copy", "cat tests/fixtures_watch/old_files.py"):
            self.assertFalse(self.interdite(commande), commande)

    def test_les_autres_outils_de_la_veille_restent_permis(self):
        """D12 : seul l'outil de copie est refusé ; watch_lab.py et watch_triage.py servent à /watch-digest (`week`, lecture seule)."""
        for commande in ("uv run tools/watch_triage.py week", "uv run ~/PMZilla-Lab/watch_triage.py week --days 7 --max 40",
                         "uv run tools/watch_triage.py thresholds", "uv run tools/watch_triage.py shadow-report --limit 20",
                         "uv run tools/watch_lab.py check-db", "uv run tools/watch_lab.py check-db --wait 120",
                         "uv run tools/watch_lab.py digest --days 7"):
            self.assertFalse(self.interdite(commande), commande)


if __name__ == "__main__":
    unittest.main()
