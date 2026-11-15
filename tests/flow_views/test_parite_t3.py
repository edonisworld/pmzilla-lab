"""
Parité statique de la relation T3 (change masking-sums, D17, tâche 13.1) : la migration de flow.v_t3_withheld, tools/flow_views.py et
mothra/contract/src/masquage.ts écrivent chacun, en commentaire, les lectures des semaines à cheval et les quatre conditions de la règle (b)
(lignes « T3-READINGS » et « T3-CONDITIONS ») ; les trois textes sont identiques. Le test lit les trois fichiers, aucune base, aucun lancement.
Source unique : le texte de ces deux lignes est écrit trois fois (SQL, Python, TypeScript) parce que la règle l'est ; l'écart entre elles se
détecte ici. Tombe avec la propagation de D15 (tâche 7.6), qui retire le code séparé de D17.
"""
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

MARQUES = ("T3-READINGS", "T3-CONDITIONS")
FICHIERS = {
    "sql": next(iter(sorted((RACINE / "db" / "migrations").glob("*_flow_t3_withheld.sql"))), None),
    "python": RACINE / "tools" / "flow_views.py",
    "typescript": RACINE / "mothra" / "contract" / "src" / "masquage.ts",
}


def marques(texte: str) -> dict:
    """{marque : texte de la ligne après « MARQUE: »} pour les lignes de commentaire (--, # ou //) qui portent une marque."""
    trouvees = {}
    for ligne in texte.splitlines():
        m = re.match(r"^\s*(?:--|#|//)\s*(T3-READINGS|T3-CONDITIONS):\s*(.*?)\s*$", ligne)
        if m:
            trouvees.setdefault(m.group(1), []).append(re.sub(r"\s+", " ", m.group(2)))
    return trouvees


class PariteT3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.textes = {nom: chemin.read_text(encoding="utf-8") for nom, chemin in FICHIERS.items() if chemin is not None}

    def test_les_trois_fichiers_existent(self):
        for nom, chemin in FICHIERS.items():
            self.assertIsNotNone(chemin, f"{nom} : fichier absent")
            self.assertTrue(chemin.is_file(), f"{nom} : {chemin}")

    def test_chaque_fichier_porte_chaque_marque_une_seule_fois(self):
        for nom, texte in self.textes.items():
            trouvees = marques(texte)
            for marque in MARQUES:
                self.assertEqual(len(trouvees.get(marque, [])), 1, f"{nom} : {marque}")

    def test_les_textes_sont_identiques_dans_les_trois_fichiers(self):
        for marque in MARQUES:
            versions = {nom: marques(texte)[marque][0] for nom, texte in self.textes.items()}
            self.assertEqual(len(set(versions.values())), 1, f"{marque} diffère : {versions}")

    def test_les_quatre_conditions_sont_dites_une_fois_dans_chaque_langage(self):
        sql = re.sub(r"--[^\n]*", "", self.textes["sql"])
        self.assertRegex(sql, r"k\s*>=\s*2\s+AND\s+n\s*-\s*v\s*>=\s*5\s+AND\s+n\s*-\s*v\s*<>\s*k\s+AND\s+n\s*-\s*v\s*<>\s*4\s*\*\s*k")
        self.assertRegex(sql, r"n\s*-\s*v\s+BETWEEN\s+k\s+AND\s+4\s*\*\s*k")                           # lecture incohérente écartée
        self.assertEqual(len(re.findall(r"CROSS\s+JOIN\s*\(VALUES\s*\(false\),\s*\(true\)\)", sql)), 2)  # quatre lectures des deux semaines à cheval
        py = self.textes["python"]
        self.assertRegex(py, r"k >= 2 and s >= seuil and s != k \* lo and s != k \* hi")
        self.assertRegex(py, r"k \* lo <= s <= k \* hi")
        self.assertRegex(py, r"for avec_debut in \(False, True\):\s+for avec_fin in \(False, True\):")
        ts = self.textes["typescript"]
        self.assertRegex(ts, r"k >= 2 && s >= seuil && s !== k \* LO_HEBDO && s !== k \* hi")
        self.assertRegex(ts, r"k \* LO_HEBDO <= s && s <= k \* hi")
        self.assertRegex(ts, r"for \(const avecDebut of \[false, true\]\)[\s\S]*for \(const avecFin of \[false, true\]\)")

    def test_les_bornes_de_la_vue_hebdomadaire_sont_celles_du_sql_et_du_typescript(self):
        lo, complement = fv.BORNES[fv.VUE_HEBDO]["tickets"]
        self.assertEqual((lo, complement), (1, False))
        self.assertRegex(self.textes["typescript"], rf"const LO_HEBDO = {lo};")
        sql = re.sub(r"--[^\n]*", "", self.textes["sql"])
        self.assertRegex(sql, r"n\s*-\s*v\s+BETWEEN\s+k\s+AND\s+4\s*\*\s*k")      # lo = 1 : k * lo s'écrit k ; hi = seuil - 1 = 4 au plancher
        self.assertEqual(fv.PLANCHER - 1, 4)

    def test_types_et_lignes_liees(self):
        self.assertEqual(fv.TYPES_DEBIT, ("story", "task"))
        self.assertRegex(re.sub(r"--[^\n]*", "", self.textes["sql"]), r"lower\(i\.type\)\s+IN\s+\('story',\s*'task'\)")
        self.assertRegex(self.textes["typescript"], r'TYPES_DEBIT: readonly string\[\] = \["story", "task"\]')
        self.assertEqual(fv.VUES_LIEES[fv.VUE_HEBDO], (fv.VUE_DEBIT,))
        self.assertEqual(fv.VUES_LIEES[fv.VUE_DEBIT], (fv.VUE_HEBDO,))

    def test_la_vue_interne_n_a_aucun_droit_donne(self):
        sql = re.sub(r"--[^\n]*", "", self.textes["sql"])
        self.assertRegex(sql, r"(?is)CREATE\s+VIEW\s+flow\.v_t3_withheld\s+AS")
        self.assertNotRegex(sql, r"(?i)\bGRANT\b")
        revoke = re.search(r"(?is)REVOKE\s+ALL\s+ON\s+flow\.v_t3_withheld\s+FROM([^;]*);", sql)
        self.assertIsNotNone(revoke)
        for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_flow_views", "pmzilla_quality_views"):
            self.assertRegex(revoke.group(1), rf"\b{role}\b")
        self.assertNotRegex(sql, r"(?i)SECURITY\s+INVOKER|\bCREATE\s+(OR\s+REPLACE\s+)?FUNCTION\b")      # aucune fonction appelée avec les droits de l'appelant

    def test_la_migration_garde_les_colonnes_des_deux_vues(self):
        sql = re.sub(r"--[^\n]*", "", self.textes["sql"])
        hebdo = re.search(r"(?is)CREATE\s+OR\s+REPLACE\s+VIEW\s+flow\.v_team_weekly_resolved\s+AS\s+SELECT(.*?)FROM", sql).group(1)
        self.assertEqual(re.findall(r"\bAS\s+(\w+)", hebdo), ["team", "week_start", "tickets"])                 # `i.type` est la deuxième colonne, sans alias
        debit = re.search(r"(?is)CREATE\s+OR\s+REPLACE\s+VIEW\s+flow\.v_team_lead_time_throughput\s+AS", sql)
        self.assertIsNotNone(debit)
        for colonne in ("throughput", "items_lt", "lead_median_days", "lead_p85_days", "items_ct", "cycle_median_days", "cycle_p85_days",
                        "items_old", "items_without_commitment"):
            self.assertRegex(sql, rf"\bAS\s+{colonne}\b")


if __name__ == "__main__":
    unittest.main()
