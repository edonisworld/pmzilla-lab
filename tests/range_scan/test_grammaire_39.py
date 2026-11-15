"""
Faux 65 du train automatique (design D4) : tools/range_scan.py s'importe sous Python 3.9, l'interpréteur du système du job launchd. Ses annotations ne
sont jamais évaluées à l'import (`from __future__ import annotations`, première instruction d'import) et il ne garde aucune forme de 3.10 évaluée à
l'exécution (ni `X | Y` hors annotation, ni `match`).
"""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "tools" / "range_scan.py"
TYPES_NUS = {"str", "int", "float", "bool", "bytes", "list", "dict", "tuple", "set", "frozenset", "object", "type"}


def annotations(arbre):
    """Les nœuds d'annotation de l'arbre (arguments, retours, variables annotées) : jamais évalués avec l'import futur."""
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.arg) and noeud.annotation is not None:
            yield noeud.annotation
        elif isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) and noeud.returns is not None:
            yield noeud.returns
        elif isinstance(noeud, ast.AnnAssign):
            yield noeud.annotation


class Grammaire39(unittest.TestCase):
    def setUp(self):
        self.texte = SOURCE.read_text(encoding="utf-8")
        self.arbre = ast.parse(self.texte, filename=str(SOURCE), feature_version=(3, 9))

    def test_l_import_futur_est_le_premier_import(self):
        imports = [n for n in self.arbre.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertTrue(imports, "aucun import")
        premier = imports[0]
        self.assertIsInstance(premier, ast.ImportFrom)
        self.assertEqual(premier.module, "__future__")
        self.assertEqual([a.name for a in premier.names], ["annotations"])

    def test_la_source_s_analyse_avec_la_grammaire_3_9(self):
        self.assertIsInstance(self.arbre, ast.Module)

    def test_aucun_match(self):
        self.assertEqual([n.lineno for n in ast.walk(self.arbre) if type(n).__name__ == "Match"], [])

    def test_aucune_union_de_types_evaluee_a_l_execution(self):
        dans_annotations = set()
        for annotation in annotations(self.arbre):
            dans_annotations.update(id(n) for n in ast.walk(annotation))
        fautes = []
        for n in ast.walk(self.arbre):
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr) and id(n) not in dans_annotations:
                for cote in (n.left, n.right):
                    if (isinstance(cote, ast.Constant) and cote.value is None) or (isinstance(cote, ast.Name) and cote.id in TYPES_NUS):
                        fautes.append(n.lineno)
        self.assertEqual(fautes, [], f"union de types évaluée à l'exécution, lignes {fautes}")


if __name__ == "__main__":
    unittest.main()
