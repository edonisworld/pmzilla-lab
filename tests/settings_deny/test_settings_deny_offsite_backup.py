"""Règles `deny` de .claude/settings.json pour la copie hors du Mac (change offsite-backup, design D10, tâche 2.4).

La session ne lit ni ne liste le dossier de copies `pmzilla-offsite` (racine du volume externe), ne lance pas `tools/offsite_backup.sh`
(sauf son aide) et ne pilote pas ses deux tâches launchd. Les rapports et le fichier d'état du dossier de données (`~/.pmzilla-lab/offsite/`,
comptes seulement), le code du script, ses modèles launchd et sa suite de tests restent lisibles et lançables.

Ces cas restent ROUGES tant que l'auteur n'a pas ajouté à .claude/settings.json les règles de REGLES_A_AJOUTER (tâche 4.1) : attendu.
Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.
"""
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import motif_en_regex  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"

LECTEURS = ("cat", "head", "tail", "less", "more", "grep", "awk", "sed", "cp", "mv", "ls", "find", "du", "tree", "strings", "rsync",
            "tar", "base64", "open", "qlmanage", "shasum")
SOUS_COMMANDES = ("setup /Volumes/Disque", "setup", "copy", "copy --include-protected", "restore-test", "restore-test --force", "status")
LANCEURS = ("bash", "sh", "zsh", "uv run", "python3", "")
CHEMINS = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
           "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "{s}")
CHEMINS_DISQUE = ("pmzilla-offsite", "pmzilla-offsite/db/db-2026-10-11/knowledge.dump", "./pmzilla-offsite/sanctum",
                  "/Volumes/Disque/pmzilla-offsite/db", "/Volumes/Disque dur 2/pmzilla-offsite/sanctum/bmad-memory-2026-10-10",
                  "~/mnt/pmzilla-offsite/db", "$HOME/mnt/pmzilla-offsite", "/Users/quelquun/mnt/pmzilla-offsite/db/x")
# L'outil Read reçoit des chemins de fichiers, sans variable d'environnement : relatif, ./, absolu, ~/.
CHEMINS_READ = ("pmzilla-offsite/db/db-2026-10-11/knowledge.dump", "./pmzilla-offsite/sanctum/x/MANIFESTE.sha256",
                "/Volumes/Disque/pmzilla-offsite/db/db-2026-10-11/MANIFESTE.sha256",
                "/Volumes/Disque dur 2/pmzilla-offsite/sanctum/bmad-memory-2026-10-10/a.md", "~/mnt/pmzilla-offsite/db/x",
                "/Users/quelquun/mnt/pmzilla-offsite/db/x")
ETIQUETTES = ("com.pmzilla.offsite-copy", "com.pmzilla.offsite-restore-test")

# Les règles que l'auteur ajoute à permissions.deny (tâche 4.1) : une chaîne JSON par ligne.
REGLES_A_AJOUTER = (
    [f"Bash({lecteur} *pmzilla-offsite*)" for lecteur in LECTEURS]
    + ["Read(**/pmzilla-offsite/**)", "Read(//**/pmzilla-offsite/**)", "Read(~/**/pmzilla-offsite/**)"]
    + [f"Bash(*offsite_backup.sh {sous}*)" for sous in ("setup", "copy", "restore-test", "status")]
    + [f"Bash({lanceur}launchctl *com.pmzilla.offsite-*)" for lanceur in ("", "/bin/", "sudo ")]
)


def glob_en_regex(motif: str) -> re.Pattern:
    """Glob de type gitignore, suffisant pour les motifs Read ci-dessus : `**/` = zéro dossier ou plus, `/**` final = tout ce qui suit,
    `*` = une suite de caractères sans barre."""
    sortie, i = "", 0
    while i < len(motif):
        if motif.startswith("**/", i):
            sortie += "(?:.*/)?"; i += 3
        elif motif.startswith("/**", i) and i + 3 == len(motif):
            sortie += "/.*"; i += 3
        elif motif[i] == "*":
            sortie += "[^/]*"; i += 1
        else:
            sortie += re.escape(motif[i]); i += 1
    return re.compile(sortie, re.DOTALL)


class BaseOffsite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.motifs = [motif_en_regex(d[len("Bash("):-1]) for d in cls.deny if d.startswith("Bash(")]
        cls.lectures = [d[len("Read("):-1] for d in cls.deny if d.startswith("Read(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)

    def lecture_interdite(self, chemin: str) -> bool:
        """Outil Read : « // » = chemin absolu depuis la racine du disque, « ~/ » = depuis le dossier personnel, sinon relatif au dossier courant."""
        for motif in self.lectures:
            if motif.startswith("//"):
                if chemin.startswith("/") and glob_en_regex(motif[1:]).fullmatch(chemin):
                    return True
            elif motif.startswith("~/"):
                if chemin.startswith("~/") and glob_en_regex(motif).fullmatch(chemin):
                    return True
            elif not chemin.startswith(("/", "~")) and glob_en_regex(motif.removeprefix("./")).fullmatch(chemin.removeprefix("./")):
                return True
        return False


class CopiesDuDisque(BaseOffsite):
    def test_regles_presentes(self):
        self.assertEqual([r for r in REGLES_A_AJOUTER if r not in self.deny], [])

    def test_lecture_par_l_outil_read_dans_toutes_les_formes_de_chemin(self):
        for chemin in CHEMINS_READ:
            with self.subTest(chemin):
                self.assertTrue(self.lecture_interdite(chemin))

    def test_lecture_et_liste_par_les_commandes_du_terminal(self):
        for lecteur, chemin in itertools.product(LECTEURS, CHEMINS_DISQUE):
            for commande in (f"{lecteur} {chemin}", f"{lecteur} -r {chemin}", f"{lecteur} -la {chemin}/"):
                self.assertTrue(self.interdite(commande), commande)

    def test_lectures_voisines_autorisees(self):
        """Les rapports et l'état du dossier de données ne contiennent que des comptes ; le code et les modèles se lisent."""
        for chemin in ("~/.pmzilla-lab/offsite/rapports/restore-2026-10.txt", "~/.pmzilla-lab/offsite/statut",
                       "/Users/quelquun/.pmzilla-lab/offsite/rapports/restore-2026-10.txt", "tools/offsite_backup.sh",
                       "tools/com.pmzilla.offsite-copy.plist", "tests/offsite_backup/test_offsite_backup.sh"):
            with self.subTest(chemin):
                self.assertFalse(self.lecture_interdite(chemin))
        for commande in ("cat ~/.pmzilla-lab/offsite/rapports/restore-2026-10.txt", "cat ~/.pmzilla-lab/offsite/statut",
                         "ls ~/.pmzilla-lab/offsite/rapports", "head -20 /Users/quelquun/.pmzilla-lab/offsite/rapports/restore-2026-10.txt",
                         "cat tools/offsite_backup.sh", "cat tools/com.pmzilla.offsite-copy.plist",
                         "plutil -lint tools/com.pmzilla.offsite-restore-test.plist", "ls /Volumes"):
            self.assertFalse(self.interdite(commande), commande)


class ScriptEtTaches(BaseOffsite):
    def test_lancement_interdit_avec_chaque_lanceur_chemin_et_sous_commande(self):
        for lanceur, chemin, sous in itertools.product(LANCEURS, CHEMINS, SOUS_COMMANDES):
            commande = f"{lanceur} {chemin.format(s='offsite_backup.sh')} {sous}".strip()
            self.assertTrue(self.interdite(commande), commande)

    def test_lancement_avec_variables_d_environnement_interdit(self):
        for commande in ("OFFSITE_NOTIFIER=1 bash tools/offsite_backup.sh copy", "OFFSITE_DATE=2026-10-11 bash tools/offsite_backup.sh restore-test --force",
                         "OFFSITE_DONNEES=/tmp/x OFFSITE_DISKUTIL=/tmp/faux bash tools/offsite_backup.sh copy"):
            self.assertTrue(self.interdite(commande), commande)

    def test_aide_source_et_suite_de_tests_non_interdits(self):
        for lanceur, chemin in itertools.product(("bash", "sh", "zsh", ""), CHEMINS):
            for option in ("--help", "-h"):
                commande = f"{lanceur} {chemin.format(s='offsite_backup.sh')} {option}".strip()
                self.assertFalse(self.interdite(commande), commande)
        for commande in ("bash tests/offsite_backup/test_offsite_backup.sh", "bash tests/run_all.sh offsite_backup",
                         "bash tests/run_all.sh --staged", "grep -n restore tools/offsite_backup.sh", "sed -n 1,40p tools/offsite_backup.sh",
                         "python3 -W ignore -m unittest discover -s tests/offsite_backup -q -f", "git log --oneline -3 -- tools/offsite_backup.sh",
                         "uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q -f"):
            self.assertFalse(self.interdite(commande), commande)

    def test_pilotage_des_deux_taches_interdit(self):
        uid = "$(id -u)"
        for lanceur, action, etiquette in itertools.product(
                ("launchctl", "/bin/launchctl", "sudo launchctl"),
                ("bootstrap", "bootout", "kickstart", "kickstart -k", "print", "unload", "load", "enable", "disable"), ETIQUETTES):
            for cible in (f"gui/{uid}/{etiquette}", f"gui/501/{etiquette}", f"gui/{uid} ~/Library/LaunchAgents/{etiquette}.plist"):
                commande = f"{lanceur} {action} {cible}"
                self.assertTrue(self.interdite(commande), commande)

    def test_pilotage_de_la_tache_de_sauvegarde_de_la_base_inchange(self):
        """Les règles d'avant (com.pmzilla.db-backup) restent en place et ne sont pas élargies à toutes les tâches pmzilla."""
        self.assertTrue(self.interdite("launchctl kickstart gui/501/com.pmzilla.db-backup"))
        self.assertFalse(self.interdite("launchctl list"))


if __name__ == "__main__":
    unittest.main()
