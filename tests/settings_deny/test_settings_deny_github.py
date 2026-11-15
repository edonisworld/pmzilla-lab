"""Règles `deny` de la migration de la feuille de route vers GitHub (change github-roadmap, R-62, design D18).

La session n'écrit jamais dans GitHub avec `gh` directement (écritures sur les tickets, `gh api` sous toute forme, étiquettes, Projects,
releases et dépôts hors lecture, jetons). Désherbage du 2026-10-28 (D33) : l'outil d'import tools/roadmap_import.py n'existe plus, ses règles
et ses cas sont retirés d'ici. Chaque motif existe sous quatre formes : `gh` nu, chemin absolu (`*/gh`), via `env`, via un chemin absolu d'`env`. Les règles sont
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

REGLES = ["Bash(" + f.format(c=c) + ")" for c in GH_REFUSE for f in FORMES_GH]

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

    def test_ce_qui_reste_permis(self):
        for ligne in (
            "gh issue list", "gh issue list --label theme:x --state all --json number,title", "gh issue view 12",
            "gh issue view 12 --comments", "/opt/homebrew/bin/gh issue list", "env GH_REPO=o/r gh issue view 3",
            "gh label list", "gh auth status", "gh project list", "gh project view 1", "gh project field-list 1",
            "gh project item-list 1", "gh release list", "gh release view tarasque", "gh repo view",
            "uv run tools/roadmap.py check", "uv run tools/roadmap.py next --budget 2h", "uv run tools/roadmap.py show R-62",
            "uv run tools/roadmap.py status", "uv run tools/roadmap.py reminder --session-hook",
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
