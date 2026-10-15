"""Règles `deny` de la migration de la feuille de route vers GitHub (change github-roadmap, R-62, design D18).

La session n'écrit jamais dans GitHub avec `gh` directement (écritures sur les tickets, `gh api` sous toute forme, étiquettes, Projects,
releases et dépôts hors lecture, jetons) et ne lance jamais l'outil d'import tools/roadmap_import.py, essai à blanc et aide compris.
Chaque motif existe sous quatre formes : `gh` nu, chemin absolu (`*/gh`), via `env`, via un chemin absolu d'`env`. Les règles sont
ajoutées à .claude/settings.json par l'utilisateur (groupe 8) : ces cas restent rouges tant qu'elles n'y sont pas. Le test ne lit que
le fichier de réglages et n'exécute rien.

    uv run python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_github.py --json   # imprime le bloc JSON à ajouter
"""
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

GH_REFUSE = (
    [f"issue {s}" for s in ("create", "edit", "close", "reopen", "comment", "delete", "transfer", "lock", "unlock", "pin", "unpin",
                            "develop")]
    + ["api"]
    + [f"label {s}" for s in ("create", "edit", "delete", "clone")]
    + [f"project {s}" for s in ("create", "copy", "close", "delete", "edit", "link", "unlink", "mark-template", "field-create",
                                "field-delete", "item-add", "item-archive", "item-create", "item-delete", "item-edit")]
    + [f"release {s}" for s in ("create", "delete", "delete-asset", "edit", "upload")]
    + [f"repo {s}" for s in ("create", "edit", "delete", "rename", "archive", "unarchive", "fork")]
    + [f"auth {s}" for s in ("token", "refresh", "login", "logout")]
)
FORMES_GH = ("gh {c}*", "*/gh {c}*", "env *gh {c}*", "*/env *gh {c}*")

IMPORT = "roadmap_import.py"
REGLES_IMPORT = [
    f"uv run *{IMPORT}*", f"python *{IMPORT}*", f"python3 *{IMPORT}*",
    f"tools/{IMPORT}*", f"./tools/{IMPORT}*", f"~/*tools/{IMPORT}*", f"$HOME/*tools/{IMPORT}*", f"/*tools/{IMPORT}*",
    f"{IMPORT}*", f"./{IMPORT}*",
]

REGLES = ["Bash(" + f.format(c=c) + ")" for c in GH_REFUSE for f in FORMES_GH] + [f"Bash({r})" for r in REGLES_IMPORT]

LANCEURS = ("uv run", "uv run --isolated", "uv run python", "uv run python3", "uv run --with pyyaml", "uv run -q",
            "python", "python3", "python3 -I", "python3 -W ignore")
CHEMINS = ("tools/{s}", "./tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
           "$HOME/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/{s}", "/Users/quelquun/PMZilla-Lab/{s}", "{s}")
CHEMINS_DIRECTS = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                   "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "{s}", "./{s}")
OPTIONS = ("", " --dry-run", " --help", " -h", " verify", " --verify", " --dry-run --verbose", " --from-file x.md")
PREFIXES_GH = ("gh", "/opt/homebrew/bin/gh", "/usr/local/bin/gh", "env gh", "env GH_TOKEN=x gh", "/usr/bin/env gh",
               "/usr/bin/env -i GH_REPO=o/r gh")


def motif_en_regex(motif: str) -> re.Pattern:
    """« Bash(motif) » : le joker * vaut n'importe quelle suite (y compris vide), tout le reste est littéral."""
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)


class GithubDeny(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reglages = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        cls.deny = reglages["permissions"]["deny"]
        cls.motifs = [motif_en_regex(d[len("Bash("):-1]) for d in cls.deny if d.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)

    def test_les_regles_du_design_sont_dans_le_fichier_de_reglages(self):
        self.assertEqual([r for r in REGLES if r not in self.deny], [])

    def test_chaque_forme_gh_refusee_nue_absolue_et_via_env(self):
        for prefixe, commande in itertools.product(PREFIXES_GH, GH_REFUSE):
            for suite in ("", " 12", " --repo o/r"):
                ligne = f"{prefixe} {commande}{suite}"
                self.assertTrue(self.interdite(ligne), ligne)

    def test_gh_api_sous_toute_forme(self):
        for ligne in ("gh api repos/o/r/issues", "gh api -X POST repos/o/r/issues -f title=x", "gh api graphql -f query='{ viewer }'",
                      "gh api --method DELETE repos/o/r/issues/1", "env GH_HOST=h gh api user", "/opt/homebrew/bin/gh api user"):
            self.assertTrue(self.interdite(ligne), ligne)

    def test_jeton_et_connexion(self):
        for ligne in ("gh auth token", "gh auth token --hostname github.com", "gh auth refresh -s project", "gh auth login",
                      "gh auth logout", "env gh auth token", "/opt/homebrew/bin/gh auth token"):
            self.assertTrue(self.interdite(ligne), ligne)

    def test_outil_d_import_chaque_lanceur_chaque_chemin_chaque_option(self):
        for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS, OPTIONS):
            ligne = f"{lanceur} {chemin.format(s=IMPORT)}{option}"
            self.assertTrue(self.interdite(ligne), ligne)

    def test_outil_d_import_execution_directe(self):
        for chemin, option in itertools.product(CHEMINS_DIRECTS, OPTIONS):
            ligne = f"{chemin.format(s=IMPORT)}{option}"
            self.assertTrue(self.interdite(ligne), ligne)

    def test_outil_d_import_essai_a_blanc_aide_et_recoupement(self):
        for ligne in ("uv run tools/roadmap_import.py --dry-run", "uv run tools/roadmap_import.py --help",
                      "uv run tools/roadmap_import.py verify", "python3 tools/roadmap_import.py --dry-run --verbose"):
            self.assertTrue(self.interdite(ligne), ligne)

    def test_ce_qui_reste_permis(self):
        for ligne in (
            "gh issue list", "gh issue list --label theme:x --state all --json number,title", "gh issue view 12",
            "gh issue view 12 --comments", "/opt/homebrew/bin/gh issue list", "env GH_REPO=o/r gh issue view 3",
            "gh label list", "gh auth status", "gh project list", "gh project view 1", "gh project field-list 1",
            "gh project item-list 1", "gh release list", "gh release view tarasque", "gh repo view",
            "uv run tools/roadmap.py check", "uv run tools/roadmap.py next --budget 2h", "uv run tools/roadmap.py show R-62",
            "uv run tools/roadmap.py board", "uv run tools/roadmap.py status", "uv run tools/roadmap.py reminder --session-hook",
            "uv run tools/gh_issue.py status R-62 \"In progress\"", "uv run tools/gh_issue.py close-feature R-62",
            "uv run tools/gh_issue.py sync-tasks", "python3 tools/gh_issue.py --help",
            "cat tools/roadmap.py", "head -40 tools/gh_issue.py", "grep -n def tools/gh_issue.py",
            "cat tools/roadmap_model.py", "cat tools/gh_issue.py", "cat tools/gh_issue.py.lock | head -5",
            "uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q",
            "uv run --with pyyaml python -W ignore -m unittest discover -s tests/roadmap -q",
            "uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q",
            "bash tests/run_all.sh gh_issue",
        ):
            self.assertFalse(self.interdite(ligne), ligne)


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(",\n".join("      " + json.dumps(r) for r in REGLES))
    else:
        unittest.main()
