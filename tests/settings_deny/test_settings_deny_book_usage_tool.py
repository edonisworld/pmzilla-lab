"""Règles `deny` de tools/book_usage.py (change posture-book-usage, design D8, tâche 4.0).

L'outil lit toutes les conversations du workspace (les transcriptions de Claude Code) : seul l'utilisateur le lance, dans le Terminal.
Chaque façon de le lancer est refusée à la session, `--help` compris (une règle ne distingue pas les options), avec chaque lanceur et
chaque façon d'écrire le chemin. Lire le script, lancer sa suite (transcriptions synthétiques) et lire le rapport restent permis.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json. Limite : une règle `deny` n'arrête pas une ligne de Python qui
lirait les transcriptions, ni un lancement précédé de `cd … &&` ; la session n'en écrit jamais.
"""
import itertools
import unittest

from test_settings_deny import Base, CHEMINS, LANCEURS

OPTIONS = ("", " collect", " report", " --help", " collect --help", " report --help", " collect --delay 1",
           " report --since 2026-10-01 --until 2026-10-09", " -h")
SCRIPT = "book_usage.py"


class OutilUsageDesLivres(Base):
    def test_chaque_lancement_est_refuse(self):
        for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS, OPTIONS):
            commande = f"{lanceur} {chemin.format(s=SCRIPT)}{option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_lanceurs_avec_options_de_l_interpreteur(self):
        for commande in ("uv run --isolated tools/book_usage.py collect", "uv run --with pyyaml python tools/book_usage.py report",
                         "python3 -W ignore tools/book_usage.py collect", "python -I ~/PMZilla-Lab/workspace/tools/book_usage.py report",
                         "uv run -q $HOME/PMZilla-Lab/workspace/tools/book_usage.py collect --delay 0"):
            self.assertTrue(self.interdite(commande), commande)

    def test_ce_que_la_session_garde(self):
        for commande in ("cat tools/book_usage.py", "head -60 tools/book_usage_transcripts.py", "grep -n DOMAINS tools/book_usage.py",
                         "sed -n 1,40p tools/book_usage.py", "bash tests/run_all.sh book_usage", "bash tests/run_all.sh --staged",
                         "python3 -W ignore -m unittest discover -s tests/book_usage -q -f",
                         'uv run --with pyyaml --with "psycopg[binary]" python -W ignore -m unittest discover -s tests/book_usage -q -f 2>&1 | tail -4',
                         "python3 -W ignore -m unittest discover -s tests/settings_deny -p test_settings_deny_book_usage_tool.py -q",
                         "ls _bmad-output/pmzilla/usage-livres", "cat _bmad-output/pmzilla/usage-livres/usage-livres-2026-10-11.md",
                         "git log --oneline -3 -- tools/book_usage.py"):
            self.assertFalse(self.interdite(commande), commande)


if __name__ == "__main__":
    unittest.main()
