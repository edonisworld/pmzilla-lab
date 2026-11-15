"""Règles `deny` des CLAUDE.md du lab : mothra/CLAUDE.md et le CLAUDE.md racine (ADR 0004, branche docs/mothra-adr-0004 ; spec tooling-permission-guards).

Les CLAUDE.md sont écrits par l'auteur seul, par un fichier d'étape. Les huit règles `Edit` ci-dessous les enferment pour les sessions :
une règle `Edit(chemin)` couvre tous les outils d'édition (Edit, Write, NotebookEdit) ; aucune règle `Write(chemin)` ni `NotebookEdit(chemin)`,
que Claude Code ignore et que tools/settings_assemble.py refuse (garde R-84).
Formes ancrées pour la racine : jamais `//**/CLAUDE.md` ni `~/**/CLAUDE.md`, qui viseraient aussi ~/.claude/CLAUDE.md et le CLAUDE.md des
autres projets. La racine est visée sous PMZilla-Lab/<dossier>/ (workspace, run) et PMZilla-Lab/worktrees/<dossier>/, en forme absolue (« // »)
et sous le dossier personnel (« ~/ »), et en forme relative pour la session ouverte dans le dossier.
`REGLES_CLAUDE_MD` (8, dans cet ordre) est imprimée par `python3 tests/settings_deny/test_settings_deny_claude_md.py --json` et contrôlée
par la garde partagée (test_settings_deny_listes_declarees.py).

Le fragment est .claude/deny/34-consignes-claude-md.txt, ajouté en fin de .claude/deny/ORDRE par le fichier d'étape de l'auteur
(mothra-claude-md-adr0004), qui reconstruit aussi .claude/settings.json (tools/settings_assemble.py --write). Tant que ce n'est pas fait,
les cas contre les vrais fichiers ÉCHOUENT.

Ce que les règles n'interdisent pas : la lecture de tout CLAUDE.md, ~/.claude/CLAUDE.md, le CLAUDE.md d'un autre projet.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json, .claude/deny/ORDRE et le fragment.

    python3 tests/settings_deny/test_settings_deny_claude_md.py --json
"""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import garde_regles  # noqa: E402
from test_settings_deny_story_quality import Moteur  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
ORDRE = RACINE / ".claude" / "deny" / "ORDRE"
NOM_FRAGMENT = "34-consignes-claude-md.txt"
FRAGMENT = RACINE / ".claude" / "deny" / NOM_FRAGMENT

REGLES_CLAUDE_MD = [
    "Edit(./mothra/CLAUDE.md)",
    "Edit(//**/mothra/CLAUDE.md)",
    "Edit(~/**/mothra/CLAUDE.md)",
    "Edit(./CLAUDE.md)",
    "Edit(//**/PMZilla-Lab/*/CLAUDE.md)",
    "Edit(//**/PMZilla-Lab/worktrees/*/CLAUDE.md)",
    "Edit(~/PMZilla-Lab/*/CLAUDE.md)",
    "Edit(~/PMZilla-Lab/worktrees/*/CLAUDE.md)",
]

CHEMINS_REFUSES = (
    # mothra/CLAUDE.md
    "mothra/CLAUDE.md", "./mothra/CLAUDE.md",
    "/Users/quelquun/PMZilla-Lab/workspace/mothra/CLAUDE.md",
    "/Users/quelquun/PMZilla-Lab/worktrees/wt-docs-mothra-adr-0004/mothra/CLAUDE.md",
    "~/PMZilla-Lab/workspace/mothra/CLAUDE.md",
    "~/PMZilla-Lab/worktrees/wt-docs-mothra-adr-0004/mothra/CLAUDE.md",
    # CLAUDE.md racine : relatif, espace de travail, un worktree, le dossier d'exécution, en absolu et sous ~/
    "CLAUDE.md", "./CLAUDE.md",
    "/Users/quelquun/PMZilla-Lab/workspace/CLAUDE.md",
    "~/PMZilla-Lab/workspace/CLAUDE.md",
    "/Users/quelquun/PMZilla-Lab/worktrees/wt-docs-mothra-adr-0004/CLAUDE.md",
    "~/PMZilla-Lab/worktrees/wt-docs-mothra-adr-0004/CLAUDE.md",
    "/Users/quelquun/PMZilla-Lab/run/CLAUDE.md",
    "~/PMZilla-Lab/run/CLAUDE.md",
)
OUTILS = ("Edit", "Write")  # le moteur applique une règle Edit à Write, comme Claude Code (R-84)
CHEMINS_PERMIS = (
    "~/.claude/CLAUDE.md", "/Users/quelquun/.claude/CLAUDE.md",
    "/Users/quelquun/autre-projet/CLAUDE.md", "~/Projets/autre-projet/CLAUDE.md", "~/PMZilla-Lab-autre/CLAUDE.md",
    "mothra/README.md", "mothra/src/CLAUDE.md.bak", "docs/CLAUDE.md.bak", "docs/adr/0004-amendements-adr-0002-accueil-et-donnees.md",
    "tools/settings_assemble.py", "tests/mothra_consignes/test_consignes_mothra.py",
)


def regles_attendues() -> list:
    """Les 8 règles du fragment 34, ajoutées par le fichier d'étape mothra-claude-md-adr0004."""
    return list(REGLES_CLAUDE_MD)


class Bloc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_CLAUDE_MD)

    def test_huit_regles_sans_doublon(self):
        self.assertEqual(len(REGLES_CLAUDE_MD), 8)
        self.assertEqual(len(set(REGLES_CLAUDE_MD)), 8)
        self.assertEqual(regles_attendues(), REGLES_CLAUDE_MD)

    def test_la_garde_partagee_passe_sur_le_bloc(self):
        self.assertEqual(garde_regles.constats(regles_attendues()), [])
        self.assertTrue(garde_regles.imprime_json(Path(__file__).read_text(encoding="utf-8")))

    def test_uniquement_des_regles_edit_et_aucune_forme_non_ancree(self):
        self.assertEqual([r for r in REGLES_CLAUDE_MD if not r.startswith("Edit(")], [])
        self.assertEqual([r for r in REGLES_CLAUDE_MD if r in ("Edit(//**/CLAUDE.md)", "Edit(~/**/CLAUDE.md)", "Edit(**/CLAUDE.md)")], [])

    def test_chaque_chemin_est_refuse_en_edition_et_en_ecriture(self):
        manquants = [(o, c) for o in OUTILS for c in CHEMINS_REFUSES if not self.moteur.acces_interdit(o, c)]
        self.assertEqual(manquants, [])

    def test_les_autres_chemins_restent_permis(self):
        self.assertEqual([(o, c) for o in OUTILS for c in CHEMINS_PERMIS if self.moteur.acces_interdit(o, c)], [])

    def test_la_lecture_reste_permise(self):
        self.assertEqual([c for c in CHEMINS_REFUSES + CHEMINS_PERMIS if self.moteur.lecture_interdite(c)], [])


class DansLesFichiers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.moteur = Moteur(cls.deny)

    def test_les_huit_regles_sont_dans_les_reglages(self):
        manquantes = [r for r in REGLES_CLAUDE_MD if r not in self.deny]
        self.assertEqual(manquantes, [], f"{len(manquantes)} règle(s) absente(s) de .claude/settings.json")

    def test_le_fragment_34_est_dans_ordre_apres_le_33(self):
        # Le fragment 34 est posé après le 33 ; des fragments plus récents (35…) peuvent le suivre.
        noms = ORDRE.read_text(encoding="utf-8").split("\n")
        noms = [n for n in noms if n]
        self.assertEqual(noms.count(NOM_FRAGMENT), 1)
        self.assertEqual(noms[noms.index(NOM_FRAGMENT) - 1], "33-lectures-absolues.txt")

    def test_le_fragment_34_contient_les_huit_regles_dans_l_ordre(self):
        lignes = [n for n in FRAGMENT.read_text(encoding="utf-8").split("\n") if n]
        self.assertEqual(lignes, REGLES_CLAUDE_MD)

    def test_les_vrais_reglages_refusent_l_edition_et_l_ecriture(self):
        manquants = [(o, c) for o in OUTILS for c in CHEMINS_REFUSES if not self.moteur.acces_interdit(o, c)]
        self.assertEqual(manquants, [])

    def test_les_vrais_reglages_laissent_les_autres_chemins(self):
        refuses = [(o, c) for o in OUTILS for c in CHEMINS_PERMIS if self.moteur.acces_interdit(o, c)]
        self.assertEqual(refuses, [])

    def test_aucune_regle_write_ni_notebookedit_ne_vise_un_claude_md(self):
        self.assertEqual([d for d in self.deny if "CLAUDE.md" in d and d.startswith(("Write(", "NotebookEdit("))], [])


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
