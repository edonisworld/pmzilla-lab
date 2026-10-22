"""Règles `deny` des sources d'équipes (change team-mapping, design D9 et complément C4 (a)).

La session ne lit ni le catalogue des équipes Jira (Flux-Lab/equipes-jira.yaml), ni le référentiel, ni l'ancienne table, avec l'outil
Read comme avec les lecteurs du terminal. Elle ne lance pas `check-teams` ni `migrate-teams`, sous aucun lanceur ni forme de chemin.
Les règles du catalogue et des deux sous-commandes sont ajoutées à .claude/settings.json par l'auteur (tâche 2.2) : les cas qui les
touchent restent rouges tant qu'elles n'y sont pas (ce fichier n'est donc pas commité par le change : l'auteur le commite avec les
règles). La liste Assets complète est dans test_settings_deny_liste_assets.py. Aucune commande n'est lancée ; le test ne lit que le
fichier de réglages. Données d'essai : noms de fichiers fictifs, aucune équipe réelle.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
"""
import itertools
import json
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

LECTEURS = ("cat", "head -n 5", "tail -f", "less", "more", "grep -r secret", "awk '{print $1}'", "sed -n 1,5p", "cp")
FORMES = ("Flux-Lab/{f}", "./Flux-Lab/{f}", "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/{f}",
          "~/PMZilla-Lab/workspace/Flux-Lab/{f}", "$HOME/PMZilla-Lab/workspace/Flux-Lab/{f}", "{f}")
CATALOGUE = "equipes-jira.yaml"
# Les 25 autres lecteurs courants (section B bis de etapes/r81-regles-deny.md), chacun avec un argument réaliste avant le chemin.
LECTEURS_ETENDUS = ("rg team", "bat", "nl", "tac", "rev", "strings", "xxd", "od", "hexdump", "cut -d: -f1", "sort -u", "uniq -c",
                    "diff README.md", "cmp README.md", "base64", "view", "vi", "vim", "nano", "rsync -a", "ditto",
                    "tar -cf /tmp/archive.tar", "zip /tmp/archive.zip", "ln -s", "mv")
LECTEURS_ETENDUS_AUTRES_FICHIERS = ("rg migrate-teams openspec/", "diff README.md README.md", "sort tests/run_all.sh",
                                    "cut -d: -f1 /etc/hosts", "rg --files Flux-Lab/rapports", "bat README.md", "tar -tf /tmp/a.tar",
                                    "mv /tmp/a.txt /tmp/b.txt", "ln -s /tmp/a /tmp/b", "rsync -a docs/ /tmp/docs/")

LANCEURS = ("uv run", "uv run --isolated", "uv run python", "uv run python3", "uv run --with pyyaml", "uv run -q",
            "python", "python3", "python3 -I", "python3 -W ignore")
CHEMINS = ("tools/{s}", "./tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
           "$HOME/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/{s}", "{s}")
SCRIPT = "export_jira_api.py"
OPTIONS = ("", " --language en", " --language fr", " --help", " --from-assets Flux-Lab/equipes-assets-complet-2026-10-16.csv",
           " --from-assets=Flux-Lab/equipes-assets-complet-2026-10-16.csv --language en")
SOUS_COMMANDES = ("check-teams", "migrate-teams")
EXECUTION_DIRECTE = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                     "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}")


def motif_en_regex(motif: str) -> re.Pattern:
    """« Bash(motif) » : le joker * vaut n'importe quelle suite (y compris vide), tout le reste est littéral."""
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reglages = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        cls.deny = reglages["permissions"]["deny"]
        cls.motifs = [motif_en_regex(d[len("Bash("):-1]) for d in cls.deny if d.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)


class CatalogueDesEquipes(Base):
    """Exigence « Team sources denied to the session » (tâche 2.1) : rouge jusqu'à la tâche 2.2 (règles de l'auteur)."""

    def test_lecture_par_l_outil_read(self):
        for forme in (f"./Flux-Lab/{CATALOGUE}", f"//**/Flux-Lab/{CATALOGUE}", f"~/**/Flux-Lab/{CATALOGUE}"):
            self.assertIn(f"Read({forme})", self.deny)

    def test_lecture_par_les_lecteurs_du_terminal_sous_chaque_forme_de_chemin(self):
        for lecteur, forme in itertools.product(LECTEURS, FORMES):
            commande = f"{lecteur} {forme.format(f=CATALOGUE)}"
            self.assertTrue(self.interdite(commande), commande)

    def test_une_copie_du_catalogue_sous_le_meme_nom_reste_interdite(self):
        for lecteur in LECTEURS:
            commande = f"{lecteur} /tmp/copie/{CATALOGUE}"
            self.assertTrue(self.interdite(commande), commande)

    def test_25_autres_lecteurs_sous_chaque_forme_de_chemin(self):
        for lecteur, forme in itertools.product(LECTEURS_ETENDUS, FORMES):
            commande = f"{lecteur} {forme.format(f=CATALOGUE)}"
            self.assertTrue(self.interdite(commande), commande)

    def test_25_autres_lecteurs_sur_une_copie_du_catalogue(self):
        for lecteur in LECTEURS_ETENDUS:
            commande = f"{lecteur} /tmp/copie/{CATALOGUE}"
            self.assertTrue(self.interdite(commande), commande)

    def test_les_memes_lecteurs_sur_d_autres_fichiers_restent_permis(self):
        for commande in LECTEURS_ETENDUS_AUTRES_FICHIERS:
            self.assertFalse(self.interdite(commande), commande)

    def test_la_regle_couvrant_l_outil_grep_de_claude_code(self):
        """Aucune forme `Grep(...)` n'existe dans les réglages : la documentation de Claude Code applique les règles `Read(...)` aux
        outils qui lisent des fichiers, Grep compris. Ce test vérifie la règle qui doit le faire (les trois formes de chemin du
        catalogue, sans restriction de motif de contenu) ; le comportement réel de l'outil Grep ne se teste pas par unittest :
        vérification manuelle décrite dans le message final du change (faux dossier Flux-Lab dans /tmp, faux equipes-jira.yaml)."""
        for forme in (f"./Flux-Lab/{CATALOGUE}", f"//**/Flux-Lab/{CATALOGUE}", f"~/**/Flux-Lab/{CATALOGUE}"):
            regle = f"Read({forme})"
            self.assertIn(regle, self.deny)
            self.assertNotIn("*", regle.split("Flux-Lab/")[1])       # le nom exact : un faux fichier du même nom est couvert
        self.assertEqual([d for d in self.deny if d.startswith("Grep(") and CATALOGUE in d], [])

    def test_git_grep_du_nom_du_catalogue_dans_la_documentation_reste_permis(self):
        for commande in ("git grep equipes-jira.yaml -- docs/", "git grep -n equipes-jira.yaml -- docs/pmzilla/installation.md"):
            self.assertFalse(self.interdite(commande), commande)

    def test_ancienne_table_formes_read_manquantes_et_rg(self):
        for forme in ("//**/Flux-Lab/equipes-assets.yaml", "~/**/Flux-Lab/equipes-assets.yaml"):
            self.assertIn(f"Read({forme})", self.deny)
        for forme in FORMES:
            commande = f"rg team {forme.format(f='equipes-assets.yaml')}"
            self.assertTrue(self.interdite(commande), commande)
        self.assertFalse(self.interdite("rg migrate-teams openspec/"))

    def test_le_referentiel_et_l_ancienne_table_restent_interdits(self):
        for fichier in ("organisation.yaml", "equipes-assets.yaml"):
            for lecteur, forme in itertools.product(LECTEURS, FORMES):
                commande = f"{lecteur} {forme.format(f=fichier)}"
                self.assertTrue(self.interdite(commande), commande)
        self.assertIn("Read(./Flux-Lab/organisation.yaml)", self.deny)
        self.assertIn("Read(./Flux-Lab/equipes-assets.yaml)", self.deny)


class LancementDesSousCommandes(Base):
    """Même exigence : `check-teams` et `migrate-teams` ne sont jamais lancés par la session, forme ancrée."""

    def test_chaque_lanceur_chaque_chemin_chaque_option(self):
        for sous, lanceur, chemin, option in itertools.product(SOUS_COMMANDES, LANCEURS, CHEMINS, OPTIONS):
            commande = f"{lanceur} {chemin.format(s=SCRIPT)} {sous}{option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_execution_directe_sous_chaque_forme_de_chemin(self):
        for sous, chemin, option in itertools.product(SOUS_COMMANDES, EXECUTION_DIRECTE, OPTIONS):
            commande = f"{chemin.format(s=SCRIPT)} {sous}{option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_la_recherche_du_meme_texte_dans_la_documentation_reste_permise(self):
        for commande in ("grep -rn check-teams docs/", "grep -rn migrate-teams docs/pmzilla/installation.md",
                         "grep -n 'check-teams' tools/export_jira_api.py", "cat tools/export_jira_api_messages.py",
                         "head -40 tools/export_jira_api.py", "git log --oneline -3 -- tools/export_jira_api.py",
                         "rg migrate-teams openspec/", "sed -n 1,20p docs/pmzilla/installation.md",
                         "uv run --with pyyaml python -W ignore -m unittest discover -s tests/export_jira_api -q -f",
                         "bash tests/run_all.sh settings_deny"):
            self.assertFalse(self.interdite(commande), commande)


if __name__ == "__main__":
    unittest.main()
