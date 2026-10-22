"""Règles `deny` de la liste de revue des équipes extérieures (change names-and-team-review, design D4, tâche 4.1).

La session ne lit pas `Flux-Lab/equipes-revues.yaml` (identifiants seulement, mais le dossier de flux reste fermé), avec l'outil Read
comme avec les lecteurs du terminal : la famille de règles du catalogue des équipes (3 règles Read, 34 lecteurs). Son fichier
temporaire `equipes-revues.yaml.tmp` (écrit par `review-teams` avant son renommage) a les 3 règles Read. La session ne lance pas
`review-teams` : les 8 règles de lancement de `check-teams` et `migrate-teams`, pour la nouvelle sous-commande. Une commande qui ne fait que
nommer le fichier (`git grep`, `rg` dans la documentation) reste permise. La liste a aussi 3 règles `Edit(chemin)` (la session ne crée
ni ne modifie la liste, donc ne peut pas masquer d'entrée à revoir). Aucune règle `Write(chemin)` ni `NotebookEdit(chemin)` (idée #372).

Les règles sont ajoutées à .claude/settings.json par l'auteur seul (tâche 1.3). Tant qu'aucune règle de la liste n'y est, les cas
de lecture sont sautés (la suite reste verte et ce fichier se commite avec le change) ; dès qu'une règle y est, toutes sont exigées.
`python3 tests/settings_deny/test_settings_deny_revue_equipes.py --json` imprime la liste exacte à copier dans permissions.deny.
Aucune commande n'est lancée ; le test ne lit que le fichier de réglages.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
"""
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
REVUE = "equipes-revues.yaml"
TEMPORAIRE = "equipes-revues.yaml.tmp"
LECTEURS_DU_CATALOGUE = ("cat", "head", "tail", "less", "more", "grep", "awk", "sed", "cp", "rg", "bat", "nl", "tac", "rev", "strings",
                         "xxd", "od", "hexdump", "cut", "sort", "uniq", "diff", "cmp", "base64", "view", "vi", "vim", "nano", "rsync",
                         "ditto", "tar", "zip", "ln", "mv")
LECTEURS_COURANTS = ("cat", "head -n 5", "tail -f", "less", "more", "grep -r secret", "awk '{print $1}'", "sed -n 1,5p", "cp",
                     "rg team", "bat", "nl", "tac", "rev", "strings", "xxd", "od", "hexdump", "cut -d: -f1", "sort -u", "uniq -c",
                     "diff README.md", "cmp README.md", "base64", "view", "vi", "vim", "nano", "rsync -a", "ditto",
                     "tar -cf /tmp/archive.tar", "zip /tmp/archive.zip", "ln -s", "mv")
FORMES = ("Flux-Lab/{f}", "./Flux-Lab/{f}", "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/{f}",
          "~/PMZilla-Lab/workspace/Flux-Lab/{f}", "$HOME/PMZilla-Lab/workspace/Flux-Lab/{f}", "{f}")
AUTRES_FICHIERS = ("rg review-teams openspec/", "git grep equipes-revues.yaml -- docs/", "git grep -n equipes-revues.yaml -- tools/",
                   "grep -rn review-teams docs/", "cat tools/export_jira_api_equipes.py", "bat README.md",
                   "bash tests/run_all.sh settings_deny")


LANCEURS = ("uv run", "uv run --isolated", "uv run python", "uv run --with pyyaml", "python", "python3", "python3 -W ignore")
CHEMINS = ("tools/{s}", "./tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
           "$HOME/PMZilla-Lab/workspace/tools/{s}", "{s}")
SCRIPT = "export_jira_api.py"
OPTIONS = ("", " --add 50", " --add 50 51 52 --language en", " --help", " --add-seen")


def regles_attendues() -> list:
    """Les 51 règles que l'auteur ajoute : 8 de lancement de la sous-commande (même famille que check-teams et migrate-teams),
    3 Read + 34 lecteurs + 3 Edit pour la liste, 3 Read pour son fichier temporaire."""
    lecture = lambda nom: [f"Read(./Flux-Lab/{nom})", f"Read(//**/Flux-Lab/{nom})", f"Read(~/**/Flux-Lab/{nom})"]
    edition = lambda nom: [f"Edit(./Flux-Lab/{nom})", f"Edit(//**/Flux-Lab/{nom})", f"Edit(~/**/Flux-Lab/{nom})"]
    lancement = [f"Bash(uv run *{SCRIPT} review-teams*)", f"Bash(python *{SCRIPT} review-teams*)", f"Bash(python3 *{SCRIPT} review-teams*)",
                 f"Bash(tools/{SCRIPT} review-teams*)", f"Bash(./tools/{SCRIPT} review-teams*)", f"Bash(~/*{SCRIPT} review-teams*)",
                 f"Bash($HOME/*{SCRIPT} review-teams*)", f"Bash(/*{SCRIPT} review-teams*)"]
    return lancement + lecture(REVUE) + [f"Bash({l} *{REVUE}*)" for l in LECTEURS_DU_CATALOGUE] + edition(REVUE) + lecture(TEMPORAIRE)


def motif_en_regex(motif: str) -> re.Pattern:
    """« Bash(motif) » : le joker * vaut n'importe quelle suite (y compris vide), tout le reste est littéral."""
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)


class RevueDesEquipes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reglages = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        cls.deny = reglages["permissions"]["deny"]
        cls.motifs = [motif_en_regex(d[len("Bash("):-1]) for d in cls.deny if d.startswith("Bash(")]
        cls.posees = any(REVUE in d for d in cls.deny)

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)

    def exiger_les_regles(self):
        if not self.posees:
            self.fail("règles de la liste de revue pas encore ajoutées par l'auteur (tâche 1.3)")

    def test_la_liste_des_regles_est_complete_et_sans_doublon(self):
        regles = regles_attendues()
        self.assertEqual(len(regles), 51)
        self.assertEqual(len(set(regles)), 51)
        self.assertFalse([r for r in regles if r.startswith(("Write(", "NotebookEdit("))])

    def test_lecture_par_l_outil_read(self):
        self.exiger_les_regles()
        for nom in (REVUE, TEMPORAIRE):
            for forme in (f"./Flux-Lab/{nom}", f"//**/Flux-Lab/{nom}", f"~/**/Flux-Lab/{nom}"):
                self.assertIn(f"Read({forme})", self.deny)

    def test_lecteurs_du_terminal_sous_chaque_forme_de_chemin(self):
        self.exiger_les_regles()
        for lecteur, forme in itertools.product(LECTEURS_COURANTS, FORMES):
            commande = f"{lecteur} {forme.format(f=REVUE)}"
            self.assertTrue(self.interdite(commande), commande)

    def test_une_copie_sous_le_meme_nom_reste_interdite(self):
        self.exiger_les_regles()
        for lecteur in LECTEURS_COURANTS:
            commande = f"{lecteur} /tmp/copie/{REVUE}"
            self.assertTrue(self.interdite(commande), commande)

    def test_les_toutes_les_regles_attendues_sont_dans_les_reglages(self):
        self.exiger_les_regles()
        self.assertEqual([r for r in regles_attendues() if r not in self.deny], [])

    def test_review_teams_jamais_lance_par_la_session(self):
        self.exiger_les_regles()
        for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS, OPTIONS):
            commande = f"{lanceur} {chemin.format(s=SCRIPT)} review-teams{option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_les_autres_lancements_restent_permis(self):
        for commande in ("uv run tools/export_jira_api.py --help", "grep -n review-teams tools/export_jira_api.py",
                         "git log --oneline -3 -- tools/export_jira_api.py"):
            self.assertFalse(self.interdite(commande), commande)

    def test_une_commande_qui_ne_fait_que_nommer_le_fichier_reste_permise(self):
        for commande in AUTRES_FICHIERS:
            self.assertFalse(self.interdite(commande), commande)

    def test_edition_par_l_outil_edit(self):
        self.exiger_les_regles()
        for forme in (f"./Flux-Lab/{REVUE}", f"//**/Flux-Lab/{REVUE}", f"~/**/Flux-Lab/{REVUE}"):
            self.assertIn(f"Edit({forme})", self.deny)

    def test_aucune_regle_write_ni_notebookedit_sur_la_liste(self):
        self.assertEqual([d for d in self.deny if REVUE in d and d.startswith(("Write(", "NotebookEdit("))], [])


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    else:
        unittest.main()
