"""Règles `deny` de la liste Assets complète : les 25 autres lecteurs courants (change team-mapping, tâche 2.3, extension de la
section F de etapes/r81-regles-deny.md).

Complète test_settings_deny_liste_assets.py (les neuf lecteurs de départ, déjà vert et commité). Ces cas restent rouges tant que
l'auteur n'a pas posé les 25 règles dans .claude/settings.json : ce fichier n'est donc pas commité par le change, l'auteur le
commite avec les règles. Aucune commande n'est lancée ; le test ne lit que le fichier de réglages. Noms de fichiers fictifs.
"""
import itertools
import json
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

LECTEURS_ETENDUS = ("rg ';'", "bat", "nl", "tac", "rev", "strings", "xxd", "od", "hexdump", "cut -d';' -f1", "sort -u", "uniq -c",
                    "diff README.md", "cmp README.md", "base64", "view", "vi", "vim", "nano", "rsync -a", "ditto",
                    "tar -cf /tmp/archive.tar", "zip /tmp/archive.zip", "ln -s", "mv")
AUTRES_FICHIERS = ("cut -d: -f1 /etc/hosts", "rg --files Flux-Lab/rapports", "rg migrate-teams openspec/", "sort tests/run_all.sh",
                   "diff README.md README.md", "mv /tmp/a.txt /tmp/b.txt")
FORMES = ("Flux-Lab/{f}", "./Flux-Lab/{f}", "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/{f}",
          "~/PMZilla-Lab/workspace/Flux-Lab/{f}", "$HOME/PMZilla-Lab/workspace/Flux-Lab/{f}", "{f}")
LISTE_ASSETS = "equipes-assets-complet-2026-10-16.csv"


def motif_en_regex(motif: str) -> re.Pattern:
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)


class ListeAssetsAutresLecteurs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reglages = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        cls.deny = reglages["permissions"]["deny"]
        cls.motifs = [motif_en_regex(d[len("Bash("):-1]) for d in cls.deny if d.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)

    def test_25_autres_lecteurs_sous_chaque_forme_de_chemin(self):
        for lecteur, forme in itertools.product(LECTEURS_ETENDUS, FORMES):
            commande = f"{lecteur} {forme.format(f=LISTE_ASSETS)}"
            self.assertTrue(self.interdite(commande), commande)

    def test_25_autres_lecteurs_sur_une_copie_dans_un_autre_dossier(self):
        for lecteur, dossier in itertools.product(LECTEURS_ETENDUS, ("/tmp/copie", "~/Downloads", "./autre")):
            commande = f"{lecteur} {dossier}/{LISTE_ASSETS}"
            self.assertTrue(self.interdite(commande), commande)

    def test_les_memes_lecteurs_sur_d_autres_fichiers_restent_permis(self):
        for commande in AUTRES_FICHIERS:
            self.assertFalse(self.interdite(commande), commande)


if __name__ == "__main__":
    unittest.main()
