"""Règles `deny` du garde-fou du matin des fins de branche (change morning-guard, design D11, tâche 9.1).

La session ne déclare pas le report de la copie hors du Mac du jour : seul l'auteur le décide, car il relâche un garde-fou (fiche Q11). Deux
familles de règles, quinze règles au total :
  - le lancement : `offsite_backup.sh postpone`, quelle que soit la forme (direct, `bash`, `sh`, `zsh`, `uv run`, lien du dossier du lab, chemin
    absolu, préfixé d'une variable ou d'un `cd`, espaces en trop), par un motif générique de la famille des sous-commandes déjà protégées (setup,
    copy, restore-test, status), élargi à `*offsite_backup.sh*postpone*` pour couvrir une option avant le mot ou plusieurs espaces ; il refuse
    aussi, par effet de bord assumé, une commande qui nomme le script puis le mot (`cat tools/offsite_backup.sh | grep postpone`) ;
  - les autres routes qui reviendraient au même, l'écriture de la ligne de report dans le journal de la copie (`pmzilla-offsite-copy.log`) : une
    redirection (`>`, `>>`), dix écrivains de fichier qui nomment le journal (tee, cp, mv, ln, dd, sed, truncate, rsync, install, perl), et trois
    règles `Edit(chemin)` (le journal sous ~/Library/Logs, tout chemin absolu, tout chemin sous le dossier personnel). Aucune règle `Write(chemin)` ni `NotebookEdit(chemin)`
    (idée #372) et aucune clé vide. Lire le journal reste permis aux outils de lecture déjà en place.
`bash tools/morning_state.sh check` reste permis (il remplace le mode « fenêtre seulement » des fichiers d'étape), comme les tests, la lecture
du script et les autres sous-commandes (aucune de ces règles ne les nomme ; la sous-commande `status` reste soumise aux règles de la copie hors du
Mac déjà posées, qui sont d'une autre famille).

Les règles sont ajoutées à .claude/settings.json par l'auteur seul (tâche 9.1). Tant qu'aucune règle de cette liste n'y est, les cas contre les
vrais réglages sont sautés (la suite reste verte et ce fichier se commite avec le change) ; dès qu'une règle y est, toutes sont exigées. La classe
`ReglesProposees` évalue les mêmes cas sur les règles de la liste seules : elle est toujours verte.
`python3 tests/settings_deny/test_settings_deny_garde_matin.py --json` imprime la liste exacte à copier dans permissions.deny.
Limites : une règle ne voit pas `bash -c '…'` construit par morceaux ni un écrivain d'une autre famille que ceux listés ; la session n'en écrit jamais.
Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.

    uv run python -W ignore -m unittest discover -s tests/settings_deny -q
"""
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = "offsite_backup.sh"
JOURNAL = "pmzilla-offsite-copy.log"
ECRIVAINS = ("tee", "cp", "mv", "ln", "dd", "sed", "truncate", "rsync", "install", "perl")


def regles_attendues() -> list:
    """Les 15 règles que l'auteur ajoute : 1 de lancement de postpone, 1 contre les redirections vers le journal de la copie,
    10 écrivains qui nomment le journal, 3 Edit sur le journal."""
    lancement = [f"Bash(*{SCRIPT}*postpone*)"]
    redirections = [f"Bash(*>*{JOURNAL}*)"]
    ecrivains = [f"Bash(*{e} *{JOURNAL}*)" for e in ECRIVAINS]
    edition = [f"Edit(~/Library/Logs/{JOURNAL})", f"Edit(//**/{JOURNAL})", f"Edit(~/**/{JOURNAL})"]
    return lancement + redirections + ecrivains + edition


def motif_en_regex(motif: str) -> re.Pattern:
    """« Bash(motif) » : le joker * vaut n'importe quelle suite (y compris vide), tout le reste est littéral."""
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)


LANCEURS = ("", "bash ", "sh ", "zsh ", "uv run ", "/bin/bash ", "env OFFSITE_NOW='2026-10-18 08:00:00' bash ", "cd workspace && bash ")
CHEMINS = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
           "~/PMZilla-Lab/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "{s}")
SUITES = (' postpone --reason "disque chez un tiers"', " postpone", " postpone --reason x --date 2026-10-19", "  postpone --reason x")
CIBLES_JOURNAL = (f"~/Library/Logs/{JOURNAL}", f"$HOME/Library/Logs/{JOURNAL}", f"/Users/quelquun/Library/Logs/{JOURNAL}",
                  f'"$HOME/Library/Logs/{JOURNAL}"', f"./{JOURNAL}", JOURNAL)
ROUTES_D_ECRITURE = (
    'echo "2026-10-18 08:00:00 copie reportée déclarée : db-2026-10-18 : x" >> {c}',
    'printf "%s\\n" "ligne" >> {c}', "echo ligne > {c}", "cat note.txt >> {c}", "tee -a {c}", "echo ligne | tee -a {c}",
    "cp /tmp/ligne {c}", "mv /tmp/ligne {c}", "ln -sf /tmp/ligne {c}", "dd if=/tmp/ligne of={c}", "sed -i '' 's/a/b/' {c}",
    "truncate -s 0 {c}", "rsync -a /tmp/ligne {c}", "install -m 600 /tmp/ligne {c}", "perl -pi -e 's/a/b/' {c}",
)
PERMISES = (
    "bash tools/morning_state.sh check", "bash tools/morning_state.sh check --language en", "bash ./tools/morning_state.sh check",
    "bash tests/run_all.sh morning_state", "bash tests/morning_state/test_morning_state.sh",
    "bash tests/offsite_backup/test_offsite_backup.sh", "cat tools/offsite_backup.sh", "git grep postpone -- tools/",
    "git grep -n offsite_backup.sh -- docs/", "git log --oneline -3 -- tools/offsite_backup.sh", "rg morning_state tools/",
    "bash tools/offsite_backup.sh --help", "bash tools/offsite_backup.sh status", "bash tools/finish_branch.sh --check feat/x",
    f"tail -n 5 ~/Library/Logs/{JOURNAL}", f"cat ~/Library/Logs/{JOURNAL}", f"grep copie ~/Library/Logs/{JOURNAL}",
    "echo morning_state >> notes.txt", "tee -a notes.txt", "cp tools/offsite_backup.sh /tmp/copie.sh",
)


class Cas:
    """Les cas, évalués contre une liste de motifs `Bash(...)` ; `interdite(commande)` dit si l'un d'eux la refuse."""

    motifs: list

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)

    def test_postpone_jamais_lance_par_la_session(self):
        for lanceur, chemin, suite in itertools.product(LANCEURS, CHEMINS, SUITES):
            commande = f"{lanceur}{chemin.format(s=SCRIPT)}{suite}"
            self.assertTrue(self.interdite(commande), commande)

    def test_aucune_ecriture_dans_le_journal_de_la_copie(self):
        for route, cible in itertools.product(ROUTES_D_ECRITURE, CIBLES_JOURNAL):
            commande = route.format(c=cible)
            self.assertTrue(self.interdite(commande), commande)

    def test_le_reste_reste_permis(self):
        for commande in PERMISES:
            self.assertFalse(self.interdite(commande), commande)


class ReglesProposees(Cas, unittest.TestCase):
    """Les cas sur les 15 règles de la liste seules : toujours verts."""

    @classmethod
    def setUpClass(cls):
        cls.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in regles_attendues() if r.startswith("Bash(")]

    def test_la_liste_est_complete_sans_doublon_ni_ecriture_ni_cle_vide(self):
        regles = regles_attendues()
        self.assertEqual(len(regles), 15)
        self.assertEqual(len(set(regles)), 15)
        self.assertTrue(all(r.strip() and r.endswith(")") for r in regles))
        self.assertFalse([r for r in regles if r.startswith(("Write(", "NotebookEdit("))])
        self.assertEqual(len([r for r in regles if r.startswith("Edit(")]), 3)
        self.assertEqual(len([r for r in regles if r.startswith("Bash(")]), 12)

    def test_les_edit_nomment_le_journal(self):
        for regle in (r for r in regles_attendues() if r.startswith("Edit(")):
            self.assertIn(JOURNAL, regle)


class ReglagesReels(Cas, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reglages = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        cls.deny = reglages["permissions"]["deny"]
        cls.motifs = [motif_en_regex(d[len("Bash("):-1]) for d in cls.deny if d.startswith("Bash(")]
        cls.posees = any(r in cls.deny for r in regles_attendues())

    # Les commandes permises sont évaluées sur la liste proposée (classe ci-dessus), pas sur les réglages entiers : d'autres familles de règles
    # (la copie hors du Mac, par exemple, refuse déjà `offsite_backup.sh status`) refusent légitimement certaines d'entre elles.
    test_le_reste_reste_permis = None

    def exiger_les_regles(self):
        if not self.posees:
            self.fail("règles du garde-fou du matin pas encore ajoutées par l'auteur (tâche 9.1)")

    def test_postpone_jamais_lance_par_la_session(self):
        self.exiger_les_regles()
        super().test_postpone_jamais_lance_par_la_session()

    def test_aucune_ecriture_dans_le_journal_de_la_copie(self):
        self.exiger_les_regles()
        super().test_aucune_ecriture_dans_le_journal_de_la_copie()

    def test_toutes_les_regles_attendues_sont_dans_les_reglages(self):
        self.exiger_les_regles()
        self.assertEqual([r for r in regles_attendues() if r not in self.deny], [])

    def test_aucune_regle_write_ni_notebookedit_sur_le_journal(self):
        self.assertEqual([d for d in self.deny if JOURNAL in d and d.startswith(("Write(", "NotebookEdit("))], [])

    def test_aucune_cle_vide_dans_les_reglages(self):
        self.assertEqual([d for d in self.deny if not d.strip()], [])

    def test_le_controle_du_matin_reste_permis_dans_les_reglages_reels(self):
        # `check` ne doit jamais être refusé : la session s'en sert à la place du mode « fenêtre seulement » des fichiers d'étape
        for commande in ("bash tools/morning_state.sh check", "bash tools/morning_state.sh check --language en"):
            self.assertFalse(self.interdite(commande), commande)


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
