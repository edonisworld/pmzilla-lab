"""Règles `deny` de la liste Assets complète des équipes (change team-mapping, design D9, complément C4 (a), tâche 2.3).

La session ne lit ni Flux-Lab/equipes-assets-complet-<date>.csv ni une copie sous ce nom, avec l'outil Read comme avec les lecteurs
du terminal, en forme relative, absolue ou depuis le dossier personnel. Les rapports du dossier des flux restent lisibles. Les règles
sont celles du pas de l'auteur (tâche 1.5), ajoutées avant le code : ce change n'édite pas .claude/settings.json pour elles. Aucune
commande n'est lancée ; le test ne lit que le fichier de réglages. Données d'essai : noms de fichiers fictifs.

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
LISTE_ASSETS = "equipes-assets-complet-2026-10-16.csv"


def motif_en_regex(motif: str) -> re.Pattern:
    """« Bash(motif) » : le joker * vaut n'importe quelle suite (y compris vide), tout le reste est littéral."""
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)


class ListeAssetsComplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reglages = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        cls.deny = reglages["permissions"]["deny"]
        cls.motifs = [motif_en_regex(d[len("Bash("):-1]) for d in cls.deny if d.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)

    def test_lecture_par_l_outil_read(self):
        for forme in ("./Flux-Lab/equipes-assets-complet-*.csv", "//**/Flux-Lab/equipes-assets-complet-*.csv",
                      "~/**/Flux-Lab/equipes-assets-complet-*.csv"):
            self.assertIn(f"Read({forme})", self.deny)

    def test_lecture_par_les_lecteurs_du_terminal_sous_chaque_forme_de_chemin(self):
        for lecteur, forme in itertools.product(LECTEURS, FORMES):
            commande = f"{lecteur} {forme.format(f=LISTE_ASSETS)}"
            self.assertTrue(self.interdite(commande), commande)

    def test_une_copie_de_la_liste_dans_un_autre_dossier_est_interdite(self):
        for lecteur, dossier in itertools.product(LECTEURS, ("/tmp/copie", "~/Downloads", "./autre", "Contexte-Lab/notes")):
            commande = f"{lecteur} {dossier}/{LISTE_ASSETS}"
            self.assertTrue(self.interdite(commande), commande)

    def test_un_rapport_du_dossier_des_flux_reste_lisible(self):
        for commande in ("cat Flux-Lab/rapports/flux-serie-2026-10-06.md", "head Flux-Lab/flux.yaml",
                         "grep -n Débit Flux-Lab/rapports/flux-serie-2026-10-06.md",
                         "cat ~/PMZilla-Lab/workspace/Flux-Lab/rapports/equipes-2026-10-16.md", "ls Flux-Lab"):
            self.assertFalse(self.interdite(commande), commande)
        self.assertEqual([d for d in self.deny if d.startswith("Read(") and "rapports" in d], [])


if __name__ == "__main__":
    unittest.main()
