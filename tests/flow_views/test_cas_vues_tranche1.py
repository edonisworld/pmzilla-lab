"""
Joueur Python des cas de masquage des vues servies par Mothra (contrats/cas-vues-tranche1.json, mothra-slices tâche 15.3).

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Le même fichier de cas synthétiques est joué par la suite npm du paquet de contrat (mothra/contract/test/masquage.test.ts) contre masquerVue, la
copie TypeScript des règles, et par ce joueur contre flow_views.masquer_vue, la règle de référence (R-20261030-28). Un écart entre les deux copies
se voit ici ou là : le cas qui diffère est nommé. Permanent : deux langages, une règle.
Un cas du fichier sans test fixe ici est un échec, jamais un saut ; `players` doit lister `npm` et `python`.
"""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

FICHIER = RACINE / "contrats" / "cas-vues-tranche1.json"
CONTRAT = RACINE / "contrats" / "vues.json"


def charger() -> dict:
    return json.loads(FICHIER.read_text(encoding="utf-8"))


def colonnes_de(vue: str) -> list[str]:
    for v in json.loads(CONTRAT.read_text(encoding="utf-8"))["views"]:
        if v["name"] == vue:
            return v["plainColumns"] + v.get("maskableColumns", []) + v["countColumns"]
    raise KeyError(vue)


def masquees(cas: dict) -> list[list]:
    """Paires [rang, colonne] des colonnes jugées dont la cellule du lecteur est masquée (une colonne absente d'une ligne vaut NULL)."""
    noms = colonnes_de(cas["view"])
    lignes = [tuple(ligne.get(n) for n in noms) for ligne in cas["rows"]]
    sorties = fv.masquer_vue(cas["view"], noms, lignes, cas["threshold"])
    return [[rang, col] for rang, cellules in enumerate(sorties) for col in cas["cells"] if "masked" in cellules[col]]


def ordonnees(paires) -> list[list]:
    return sorted([list(p) for p in paires], key=lambda p: (p[0], p[1]))


class JoueurPython(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cas = {c["id"]: c for c in charger()["cases"]}

    def jouer(self, identifiant: str):
        cas = self.cas[identifiant]
        self.assertEqual(ordonnees(masquees(cas)), ordonnees(cas["masked"]), f"{identifiant} : {cas['title']}")

    def test_cas_V1(self):
        self.jouer("V1")

    def test_cas_V2(self):
        self.jouer("V2")

    def test_cas_V3(self):
        self.jouer("V3")

    def test_cas_V4(self):
        self.jouer("V4")

    def test_cas_V5(self):
        self.jouer("V5")

    def test_cas_V6(self):
        self.jouer("V6")

    def test_cas_V7(self):
        self.jouer("V7")

    def test_cas_V8(self):
        self.jouer("V8")

    def test_cas_V9(self):
        self.jouer("V9")

    def test_cas_V10(self):
        self.jouer("V10")

    def test_cas_V11(self):
        self.jouer("V11")

    def test_cas_V12(self):
        self.jouer("V12")

    def test_cas_V13(self):
        self.jouer("V13")

    def test_cas_V14(self):
        self.jouer("V14")

    def test_cas_V15(self):
        # H-05 (audit 629, R-20261107-30) : la ligne du produit seule de son groupe est masquée par Python et par TypeScript (même cas, deux joueurs).
        self.jouer("V15")


class Consommation(unittest.TestCase):
    def test_chaque_cas_du_fichier_a_son_test_fixe_et_les_deux_joueurs_sont_listes(self):
        donnees = charger()
        self.assertEqual(sorted(donnees["players"]), ["npm", "python"])
        for cas in donnees["cases"]:
            test = getattr(JoueurPython, f"test_cas_{cas['id']}", None)
            self.assertIsNotNone(test, cas["id"])
            self.assertFalse(getattr(test, "__unittest_skip__", False), cas["id"])

    def test_chaque_vue_des_cas_est_dans_le_contrat_et_chaque_colonne_jugee_est_une_colonne_de_la_vue(self):
        for cas in charger()["cases"]:
            noms = colonnes_de(cas["view"])
            for col in cas["cells"]:
                self.assertIn(col, noms, cas["id"])
            for ligne in cas["rows"]:
                self.assertTrue(set(ligne) <= set(noms), cas["id"])


if __name__ == "__main__":
    unittest.main()
