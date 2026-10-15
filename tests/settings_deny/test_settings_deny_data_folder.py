"""Règles `deny` du dossier de données `.pmzilla-lab` (change remove-sqlite, design D15, tâche 2.3).

La session n'a le droit ni de supprimer ni de déplacer un fichier du dossier de données : `rm`, `rmdir`, `mv` et `rsync` sont refusés
sur tout chemin qui contient `.pmzilla-lab`, quelle que soit sa forme (relatif au home, `$HOME`, absolu, relatif au dépôt, avec options,
glob), que le dossier soit la source ou la destination. Cela couvre les fichiers SQLite avant leur suppression et le dossier de copie
étiqueté `sauvegardes/db-2026-10-14-sortiesqlite` après. Lister ou lire ce dossier n'est pas l'affaire de ces règles (la lecture des
sauvegardes est refusée par ailleurs) ; les commandes sur un dossier temporaire, le lanceur de tests et `mv` dans le dépôt restent permis.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json. Limite : une règle `deny` n'arrête pas un `cd … && rm *`, ni
`bash -c '…'`, ni une ligne de Python ; la session n'en écrit jamais.

Les règles à ajouter à `permissions.deny` de .claude/settings.json (REGLES_ATTENDUES) sont ajoutées par l'auteur, jamais par la session.
"""
import json
import unittest

from test_settings_deny import Base, RACINE

DOSSIER = ".pmzilla-lab"
REGLES_ATTENDUES = [
    "Bash(rm *.pmzilla-lab*)",
    "Bash(rmdir *.pmzilla-lab*)",
    "Bash(mv *.pmzilla-lab*)",
    "Bash(rsync *.pmzilla-lab*)",
]
RACINES = ("~/.pmzilla-lab", "$HOME/.pmzilla-lab", "/Users/quelquun/.pmzilla-lab", ".pmzilla-lab", "./.pmzilla-lab",
           "../.pmzilla-lab", "../../.pmzilla-lab", '"$HOME/.pmzilla-lab"', "'/Users/quelquun/.pmzilla-lab'")
FICHIERS_SQLITE = ("library.sqlite", "library.sqlite-wal", "library.sqlite-shm", "library.sqlite*", "*.sqlite", "watch.sqlite",
                   "triage.sqlite", "cases.sqlite", "x.db", "")
SAUVEGARDE = "sauvegardes/db-2026-10-14-sortiesqlite"


class DossierDeDonnees(Base):
    def test_les_regles_attendues_sont_dans_settings_json(self):
        deny = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["deny"]
        for regle in REGLES_ATTENDUES:
            self.assertEqual(deny.count(regle), 1, regle)

    def test_suppression_d_un_fichier_sqlite(self):
        for racine in RACINES:
            for fichier in FICHIERS_SQLITE:
                for commande in ("rm", "rm -f", "rm -rf", "rm -fv", "rm --force"):
                    ligne = f"{commande} {racine}/{fichier}"
                    self.assertTrue(self.interdite(ligne), ligne)

    def test_glob_et_plusieurs_fichiers(self):
        for ligne in ("rm ~/.pmzilla-lab/library.sqlite*", "rm -f ~/.pmzilla-lab/*.sqlite*", "rm a.txt ~/.pmzilla-lab/library.sqlite",
                      "rm ~/.pmzilla-lab/library.sqlite ~/.pmzilla-lab/library.sqlite-wal", "rm -- ~/.pmzilla-lab/library.sqlite"):
            self.assertTrue(self.interdite(ligne), ligne)

    def test_suppression_ou_deplacement_de_la_copie_etiquetee(self):
        for racine in RACINES:
            for commande in ("rm -rf", "rm -r", "rmdir", "rm -f", "mv", "mv -f", "mv -n", "rsync -a", "rsync -a --remove-source-files"):
                ligne = f"{commande} {racine}/{SAUVEGARDE}"
                self.assertTrue(self.interdite(ligne), ligne)
                self.assertTrue(self.interdite(ligne + "/"), ligne + "/")
        for ligne in ("rmdir ~/.pmzilla-lab/sauvegardes", "rm -rf ~/.pmzilla-lab/sauvegardes",
                      "mv ~/.pmzilla-lab/sauvegardes/db-2026-10-14-sortiesqlite /tmp/x",
                      "mv /tmp/x ~/.pmzilla-lab/sauvegardes/db-2026-10-14-sortiesqlite"):
            self.assertTrue(self.interdite(ligne), ligne)

    def test_mv_et_rsync_avec_le_dossier_en_source_ou_en_destination(self):
        for racine in RACINES:
            for ligne in (f"mv {racine}/library.sqlite /tmp/library.sqlite", f"mv /tmp/a {racine}/library.sqlite",
                          f"mv -f {racine}/x y", f"mv x {racine}/", f"mv {racine} /tmp/autre",
                          f"rsync -a {racine}/ /tmp/copie/", f"rsync -a /tmp/copie/ {racine}/",
                          f"rsync -a --delete {racine}/ /tmp/vide/", f"rsync -a --delete /tmp/vide/ {racine}/",
                          f"rsync -av --delete-after {racine}/sauvegardes/ /tmp/s/"):
                self.assertTrue(self.interdite(ligne), ligne)

    def test_rsync_avec_delete(self):
        for ligne in ("rsync -a --delete /tmp/vide/ ~/.pmzilla-lab/", "rsync --delete -a /tmp/vide/ $HOME/.pmzilla-lab/",
                      "rsync -a --delete-excluded /tmp/vide/ /Users/quelquun/.pmzilla-lab/sauvegardes/",
                      "rsync -a --delete .pmzilla-lab/ /tmp/x/"):
            self.assertTrue(self.interdite(ligne), ligne)

    def test_ce_que_la_session_garde(self):
        for commande in ("rm -rf /tmp/x", "rm -f /tmp/x/abc.sqlite", 'rm "$TMPDIR/abc"', 'rm -rf "$TMPDIR/abc"', "rmdir /tmp/x",
                         "rm tests/fixtures/a.txt", "rm -rf tests/__pycache__",
                         "mv a.txt b.txt", "mv tools/a.py tools/b.py", "mv /tmp/a /tmp/b", "rsync -a src/ /tmp/copie/",
                         "bash tests/run_all.sh", "bash tests/run_all.sh --staged", "bash tests/run_all.sh watch_sh",
                         "uv run --quiet --with pyyaml python -W ignore -m unittest discover -s tests/watch_sh",
                         "uv run --with numpy --with httpx python -W ignore -m unittest discover -s tests/settings_deny -p test_settings_deny_data_folder.py",
                         "ls ~/.pmzilla-lab", "ls -la $HOME/.pmzilla-lab", "ls /Users/quelquun/.pmzilla-lab/sauvegardes",
                         "du -sh ~/.pmzilla-lab", "git status", "git mv a.txt b.txt"):
            self.assertFalse(self.interdite(commande), commande)


if __name__ == "__main__":
    unittest.main()
