"""
La table des formules fixes de CLAUDE.md (section « Response language and fixed formulas ») reprend, sans écart, les valeurs
de tests/postures/vocabulaire.yaml : c'est ce fichier que lisent le jeu d'essai et le miroir de Critic, et ce que lit le modèle.

    uv run --with pyyaml python -m unittest discover -s tests/posture_evals -q
"""
import re
import unittest
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
VOCABULAIRE = yaml.safe_load((RACINE / "tests" / "postures" / "vocabulaire.yaml").read_text(encoding="utf-8"))
COLONNES = {"fr": 1, "en": 2}


def table_des_formules() -> dict[str, list[str]]:
    """Lignes de la table de CLAUDE.md : formule -> [cellule française, cellule anglaise], sans les accents graves."""
    texte = (RACINE / "CLAUDE.md").read_text(encoding="utf-8")
    debut = texte.index("## Response language and fixed formulas")
    corps = texte[debut:]
    lignes = []
    for ligne in corps.splitlines()[1:]:
        if ligne.startswith("## "):
            break
        if ligne.startswith("|") and not ligne.startswith("|---"):
            lignes.append([c.strip() for c in ligne.strip().strip("|").split("|")])
    return {ligne[0]: [c.replace("`", "") for c in ligne[1:]] for ligne in lignes[1:]}


class TableDesFormules(unittest.TestCase):
    def test_la_table_reprend_le_vocabulaire(self):
        table = table_des_formules()
        self.assertEqual(len(table), 7, list(table))
        lignes = list(table.values())
        for langue, colonne in ((l, c - 1) for l, c in COLONNES.items()):
            vocabulaire = VOCABULAIRE[langue]
            attendu = [
                vocabulaire["posture_tag"],
                vocabulaire["out_of_library"],
                " / ".join(vocabulaire["source_separation"][:2]),
                vocabulaire["hypothesis"],
                vocabulaire["critic_final_title"],
                vocabulaire["source_separation"][2],
                vocabulaire["case_citation"],
            ]
            obtenu = [ligne[colonne] for ligne in lignes]
            self.assertEqual(obtenu, attendu, langue)

    def test_la_formule_de_citation_de_cas_dans_les_deux_langues(self):
        self.assertEqual(VOCABULAIRE["fr"]["case_citation"], "Cas n°{number}, soumis par {author}, {date}, résultat : {outcome}")
        self.assertEqual(VOCABULAIRE["en"]["case_citation"], "Case no. {number}, submitted by {author}, {date}, outcome: {outcome}")

    def test_la_table_des_postures_nomme_les_postures_du_vocabulaire(self):
        texte = (RACINE / "CLAUDE.md").read_text(encoding="utf-8")
        corps = texte[texte.index("## The five postures"):]
        corps = corps[:corps.index("\n## ", 1)]
        noms = [l.strip("|").split("|")[0].strip() for l in corps.splitlines()
                if l.startswith("|") and not l.startswith("|---")][1:]
        self.assertEqual(noms, VOCABULAIRE["posture_names"])

    def test_aucune_expression_reguliere_dans_la_table(self):
        for cellules in table_des_formules().values():
            for cellule in cellules:
                self.assertNotRegex(cellule, r"\\|\[\^|\(\?|\.\*|\\s", cellule)


if __name__ == "__main__":
    unittest.main()
