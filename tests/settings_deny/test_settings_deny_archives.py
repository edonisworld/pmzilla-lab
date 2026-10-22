"""Règles `deny` du dossier `archives/` du lab (lab-folder-layout, design D6, tâche 4.1, spec tooling-permission-guards).

Après les déplacements de l'auteur (D5), l'ancienne table d'équipes vit sous `archives/archives-equipes` et la copie publique sous
`archives/edition-en`. La session ne lit toujours pas la table, ni avec l'outil Read ni avec un lecteur du terminal, et ne parcourt pas le
dossier `archives/` entier avec `find`, `tree`, `rsync`, `tar`, `ditto`, `zip`, `cp`. Les règles `archives-equipes` d'avant restent (aucune
n'est retirée) et la copie publique reste gardée par les règles `edition-en` d'avant, sans règle de plus.

Conception (même motif que test_settings_deny_contexte.py) : l'auteur ajoute les 24 règles de REGLES_D6 à .claude/settings.json (tâche 6.1).
La suite reste VERTE avant et après :
 - la matrice des formes s'applique au bloc REGLES_D6, pas au fichier de réglages ;
 - les tests « dans le fichier de réglages » sont SAUTÉS tant qu'aucune règle de D6 n'y est, ÉCHOUENT si l'état est partiel (ils nomment les
   règles absentes) et passent si tout y est, avec la matrice rejouée contre les règles RÉELLES ;
 - les cas « ancien emplacement toujours refusé », « copie publique sous archives/ refusée » et « cas permis » sont vérifiés contre les règles
   réelles, avant comme après : aucune règle de D6 n'est nécessaire à leur résultat (les cas permis le sont aussi privés des règles de D6).

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny_story_quality import Moteur  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"

# Bloc A : lecture de la table sous archives/ (nouvel emplacement) et partout ailleurs.
REGLES_A = (
    "Read(~/PMZilla-Lab/archives/archives-equipes/**)",
    "Read(~/**/archives-equipes/**)",
    "Read(//**/archives-equipes/**)",
)
# Bloc B : parcours récursif du dossier archives/ entier, trois formes par commande (nommé en dernier, chemin dessous, suivi d'options).
COMMANDES_B = ("find", "tree", "rsync", "tar", "ditto", "zip", "cp")
REGLES_B = tuple(f"Bash({c} *archives{fin})" for c in COMMANDES_B for fin in ("", "/*", " *"))
REGLES_D6 = REGLES_A + REGLES_B

ARCHIVE = "archives-equipes"
LECTEURS = ("cat", "head", "tail", "less", "more", "grep", "awk", "sed", "cp", "rg", "bat", "nl", "tac", "rev", "strings", "xxd", "od",
            "hexdump", "cut")
LISTAGES = ("ls", "find", "tree")        # ceux que les règles `archives-equipes` d'avant refusent déjà (test_settings_deny_r84_flux_lab.py)
DOSSIERS_ARCHIVES = ("archives", "./archives", "/Users/quelquun/PMZilla-Lab/archives", "~/PMZilla-Lab/archives",
                     "$HOME/PMZilla-Lab/archives", "../archives")
SOUS_CHEMINS = ("", "/", "/archives-equipes", "/archives-equipes/2026-10-18/table.yaml", "/edition-en", "/corbeille")
OPTIONS = ("", " -type f", " -name '*.yaml'", " -a . /tmp/copie")

CHEMINS_READ_TABLE = (
    "~/PMZilla-Lab/archives/archives-equipes/2026-10-18/table.yaml", "~/PMZilla-Lab/archives/archives-equipes/x",
    "/Users/quelquun/PMZilla-Lab/archives/archives-equipes/2026-10-18/table.yaml", "/Users/quelquun/ailleurs/archives-equipes/x",
    "~/ailleurs/archives-equipes/x", "~/PMZilla-Lab/autre/niveau/archives-equipes/y.csv",
)
CHEMINS_READ_ANCIEN = (
    "~/PMZilla-Lab/archives-equipes/2026-10-18/table.yaml", "/Users/quelquun/PMZilla-Lab/archives-equipes/x", "archives-equipes/x",
    "../archives-equipes/x",
)

# La copie publique sous archives/ : les règles `edition-en` d'avant, qui cherchent le nom n'importe où dans la commande, la gardent.
COPIE = "~/PMZilla-Lab/archives/edition-en"
COPIES = (COPIE, "$HOME/PMZilla-Lab/archives/edition-en", "/Users/quelquun/PMZilla-Lab/archives/edition-en")
COMMANDES_COPIE = tuple(c for d in COPIES for c in (
    f"git -C {d} commit -m x", f"git -C {d} push", f"git -C {d} push origin main",
    f"cd {d} && git commit -m x", f"cd {d} && git push", f"cd {d}; git commit -m x", f"cd {d}; git push",
    f"git --git-dir={d}/.git commit -m x", f"git --git-dir={d}/.git push",
))

# Permis (la preuve de chaque cas de D6) : aucune règle réelle, avec ou sans celles de D6, ne doit les refuser.
COMMANDES_PERMISES = (
    "git worktree list", "git -C ~/PMZilla-Lab/workspace worktree list", "git -C /Users/quelquun/PMZilla-Lab/workspace worktree list --porcelain",
    "git worktree move ~/PMZilla-Lab/wt-feat-x ~/PMZilla-Lab/worktrees/wt-feat-x",
    "git -C ~/PMZilla-Lab/workspace worktree move /Users/quelquun/PMZilla-Lab/wt-feat-x /Users/quelquun/PMZilla-Lab/worktrees/wt-feat-x",
    "git -C ~/PMZilla-Lab/worktrees/wt-feat-x status", "git -C /Users/quelquun/PMZilla-Lab/worktrees/wt-feat-x status --short",
    "ls ~/PMZilla-Lab/worktrees", "ls -la /Users/quelquun/PMZilla-Lab/worktrees", "ls $HOME/PMZilla-Lab/worktrees",
    "cat tools/worktree.sh", "head -40 tools/worktree.sh", "grep -n worktrees tools/worktree.sh", "cat tools/lab_paths.sh",
    "cat tools/lab_paths.py", "sed -n 1,40p tools/lab_paths.py", "ls tests/worktree", "ls tests/lab_paths", "cat tests/worktree/test_worktree.sh",
    "bash tests/worktree/test_worktree.sh", "bash tests/run_all.sh worktree", "bash tests/run_all.sh lab_paths",
    "bash tests/run_all.sh finish_worktree", "bash tests/run_all.sh settings_deny", "bash tests/run_all.sh --staged", "bash tests/run_all.sh",
    "cat openspec/changes/archive/2026-10-18-organisation-context/tasks.md", "ls openspec/changes/archive",
    "find openspec/changes/archive -name tasks.md", "grep -rn contexte openspec/changes/archive", "git log --oneline -3 -- openspec/changes/archive",
    "git commit -m x", "git -C ~/PMZilla-Lab/workspace commit -m x", "git -C /Users/quelquun/PMZilla-Lab/workspace status",
    "bash tools/worktree.sh feat/x", "python3 tools/lab_paths.py", "bash tools/lab_paths.sh",
)
CHEMINS_READ_PERMIS = (
    "tools/worktree.sh", "tools/lab_paths.sh", "tools/lab_paths.py", "tests/worktree/test_worktree.sh", "tests/lab_paths/test_worktrees_folder.py",
    "openspec/changes/archive/2026-10-18-organisation-context/tasks.md", "openspec/changes/lab-folder-layout/design.md",
    "~/PMZilla-Lab/workspace/tools/worktree.sh", "/Users/quelquun/PMZilla-Lab/workspace/tools/lab_paths.py",
    "docs/pmzilla/installation.md", "~/PMZilla-Lab/worktrees/wt-feat-x/tools/worktree.sh",
)


def deny_reel() -> list:
    return json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]


class Compte(unittest.TestCase):
    def test_24_regles_sans_doublon(self):
        self.assertEqual((len(REGLES_A), len(REGLES_B)), (3, 21))
        self.assertEqual(len(REGLES_D6), 24)
        self.assertEqual(len(set(REGLES_D6)), 24)

    def test_sept_commandes_trois_formes(self):
        self.assertEqual(COMMANDES_B, ("find", "tree", "rsync", "tar", "ditto", "zip", "cp"))
        self.assertIn("Bash(find *archives)", REGLES_B)
        self.assertIn("Bash(find *archives/*)", REGLES_B)
        self.assertIn("Bash(find *archives *)", REGLES_B)
        self.assertIn("Bash(cp *archives *)", REGLES_B)

    def test_aucune_regle_write_ni_notebookedit(self):
        """Claude Code ignore Write(chemin) : seules des règles Read/Bash sont posées ici (garde R-84)."""
        self.assertEqual([r for r in REGLES_D6 if r.startswith(("Write(", "NotebookEdit("))], [])
        self.assertTrue(all(r.startswith(("Bash(", "Read(")) and r.endswith(")") and r not in ("Bash()", "Read()") for r in REGLES_D6))

    def test_le_bloc_ne_touche_pas_le_nom_edition_en(self):
        """Aucune règle de plus pour la copie publique : les règles d'avant la gardent sous archives/."""
        self.assertEqual([r for r in REGLES_D6 if "edition-en" in r], [])


class Bloc(unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à copier : vert avant comme après la tâche 6.1."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_D6)

    def test_bloc_a_lecture_de_la_table(self):
        for chemin in CHEMINS_READ_TABLE:
            self.assertTrue(self.moteur.lecture_interdite(chemin), f"Read({chemin})")

    def test_bloc_a_ne_lit_pas_le_reste_de_archives(self):
        for chemin in ("~/PMZilla-Lab/archives/edition-en/README.md", "~/PMZilla-Lab/archives/corbeille/x", "docs/pmzilla/archives/x.md"):
            self.assertFalse(self.moteur.lecture_interdite(chemin), f"Read({chemin})")

    def test_bloc_b_chaque_commande_sous_ses_trois_formes(self):
        for commande, dossier in itertools.product(COMMANDES_B, DOSSIERS_ARCHIVES):
            for texte in (f"{commande} {dossier}",                        # nommé en dernier
                          f"{commande} {dossier}/archives-equipes",       # un chemin dessous
                          f"{commande} {dossier}/edition-en/x",
                          f"{commande} {dossier} -type f",                # suivi d'options
                          f"{commande} -a {dossier} /tmp/copie",
                          f"{commande} -r {dossier}/ ."):
                self.assertTrue(self.moteur.interdite(texte), texte)

    def test_bloc_b_chaque_forme_est_necessaire(self):
        """Retirer l'une des trois formes d'une commande laisse passer un des trois appels : la liste est minimale."""
        for commande in COMMANDES_B:
            formes = {f: f"Bash({commande} *archives{f})" for f in ("", "/*", " *")}
            appels = {"": f"{commande} ~/PMZilla-Lab/archives", "/*": f"{commande} ~/PMZilla-Lab/archives/x", " *": f"{commande} archives -v"}
            for forme, regle in formes.items():
                reste = Moteur([r for r in REGLES_D6 if r != regle])
                self.assertFalse(reste.interdite(appels[forme]), f"{commande} : la forme {forme!r} est redondante")

    def test_commandes_et_lectures_permises(self):
        moteur = self.moteur
        self.assertEqual([c for c in COMMANDES_PERMISES if moteur.interdite(c)], [])
        self.assertEqual([c for c in CHEMINS_READ_PERMIS if moteur.lecture_interdite(c)], [])


class ReglesReelles(unittest.TestCase):
    """Les règles réelles, avant comme après la tâche 6.1 : l'ancien emplacement, la copie publique et les cas permis."""

    @classmethod
    def setUpClass(cls):
        cls.deny = deny_reel()
        cls.reelles = Moteur(cls.deny)
        cls.sans_d6 = Moteur([r for r in cls.deny if r not in REGLES_D6])

    def test_l_ancien_emplacement_reste_refuse(self):
        for chemin in CHEMINS_READ_ANCIEN:
            self.assertTrue(self.reelles.lecture_interdite(chemin), f"Read({chemin})")
        for lecteur, dossier in itertools.product(LECTEURS + LISTAGES, ("~/PMZilla-Lab", "$HOME/PMZilla-Lab", "/Users/quelquun/PMZilla-Lab", ".", "..")):
            commande = f"{lecteur} {dossier}/{ARCHIVE}/2026-10-18/table.yaml"
            self.assertTrue(self.reelles.interdite(commande), commande)

    def test_aucune_regle_d_avant_n_est_retiree(self):
        existantes = [r for r in self.deny if ARCHIVE in r]
        self.assertGreaterEqual(len(existantes), 42, "les règles qui nomment archives-equipes (3 Read, 39 commandes) doivent toutes rester")
        for r in ("Read(~/PMZilla-Lab/archives-equipes/**)", "Read(//**/PMZilla-Lab/archives-equipes/**)", "Read(**/archives-equipes/**)",
                  "Bash(cat *archives-equipes*)", "Bash(cp *archives-equipes*)"):
            self.assertIn(r, self.deny)

    def test_la_table_sous_archives_est_refusee_par_les_lecteurs(self):
        for lecteur, dossier in itertools.product(LECTEURS, DOSSIERS_ARCHIVES):
            commande = f"{lecteur} {dossier}/{ARCHIVE}/2026-10-18/table.yaml"
            self.assertTrue(self.reelles.interdite(commande), commande)

    def test_la_copie_publique_sous_archives_reste_gardee(self):
        for commande in COMMANDES_COPIE:
            self.assertTrue(self.sans_d6.interdite(commande), commande)       # sans aucune règle de D6 : celles d'avant suffisent
            self.assertTrue(self.reelles.interdite(commande), commande)

    def test_commandes_et_lectures_permises(self):
        for moteur, nom in ((self.reelles, "règles réelles"), (self.sans_d6, "règles réelles privées de D6")):
            self.assertEqual([c for c in COMMANDES_PERMISES if moteur.interdite(c)], [], nom)
            self.assertEqual([c for c in CHEMINS_READ_PERMIS if moteur.lecture_interdite(c)], [], nom)


class DansLeFichierDeReglages(unittest.TestCase):
    """Tâche 6.1 : l'auteur ajoute les 24 règles. Sauté avant, échoue si l'état est partiel, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = deny_reel()
        cls.presentes = [r for r in REGLES_D6 if r in cls.deny]
        cls.manquantes = [r for r in REGLES_D6 if r not in cls.deny]

    def avant(self):
        if not self.presentes:
            self.fail("tâche 6.1 : l'auteur n'a pas encore ajouté les règles de D6 (utilisateur)")

    def test_les_24_regles_sont_dans_settings_json(self):
        self.avant()
        self.assertEqual(self.manquantes, [], f"{len(self.manquantes)} règle(s) de D6 absente(s) de .claude/settings.json")

    def test_aucune_regle_en_double(self):
        self.avant()
        self.assertEqual(len(self.deny), len(set(self.deny)), "doublon dans permissions.deny")

    def test_aucune_regle_write_ni_vide(self):
        self.avant()
        self.assertEqual([r for r in self.deny if r.startswith(("Write(", "NotebookEdit("))], [])
        self.assertEqual([r for r in self.deny if not r.strip() or r in ("Bash()", "Read()", "Edit()")], [])

    def test_la_matrice_contre_les_regles_reelles(self):
        self.avant()
        if self.manquantes:
            self.skipTest("règles partielles : voir test_les_24_regles_sont_dans_settings_json")
        moteur = Moteur(self.deny)
        for chemin in CHEMINS_READ_TABLE:
            self.assertTrue(moteur.lecture_interdite(chemin), f"Read({chemin})")
        for commande, dossier in itertools.product(COMMANDES_B, DOSSIERS_ARCHIVES):
            for texte in (f"{commande} {dossier}", f"{commande} {dossier}/x", f"{commande} {dossier} -type f"):
                self.assertTrue(moteur.interdite(texte), texte)


if __name__ == "__main__":
    unittest.main()
