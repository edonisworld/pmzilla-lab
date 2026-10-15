"""Garde-fous du source de tools/doctor.py : ni Trousseau, ni client de base, ni conteneur, ni adresse non locale, ni comparaison de versions ;
et, sur une exécution complète, aucun appel interdit ni contenu de sauvegarde."""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import DOCTOR, SENTINELLE, Labo  # noqa: E402


def chaines_du_code() -> list[str]:
    """Littéraux de chaîne du source, docstrings exclues."""
    arbre = ast.parse(DOCTOR.read_text(encoding="utf-8"))
    docstrings = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.FunctionDef, ast.ClassDef)) and noeud.body and isinstance(noeud.body[0], ast.Expr) \
                and isinstance(noeud.body[0].value, ast.Constant):
            docstrings.add(id(noeud.body[0].value))
    return [n.value for n in ast.walk(arbre) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]


class Source(unittest.TestCase):
    def test_aucune_commande_interdite(self):
        for chaine in chaines_du_code():
            for interdit in ("security", "psql", "docker", "pg_dump", "find-generic-password"):
                self.assertNotRegex(chaine, rf"\b{interdit}\b", f"{interdit} dans {chaine!r}")

    def test_aucune_adresse_non_locale(self):
        for chaine in chaines_du_code():
            for adresse in re.findall(r"https?://([^/:\s\"']+)", chaine):
                self.assertIn(adresse, ("127.0.0.1", "localhost"), chaine)

    def test_aucune_comparaison_de_versions(self):
        texte = DOCTOR.read_text(encoding="utf-8")
        for mot in ("packaging", "parse_version", "LooseVersion", "releases/latest", "pypi.org", "api.github.com"):
            self.assertNotIn(mot, texte)

    def test_aucune_commande_qui_change_quelque_chose(self):
        for chaine in chaines_du_code():
            for verbe in ("bootstrap", "bootout", "kickstart", "prune", "pull", "checkout", "rmtree", "unlink "):
                self.assertNotEqual(chaine, verbe)


class Execution(Labo):
    def test_suite_complete_sans_appel_interdit_ni_sentinelle(self):
        self.ajouter_branche("fix/finie", fusionnee=True)
        self.ouvrir_parite("identique")
        self.fermer_base()
        for args in ((), ("--json",), ("--quiet", "--language", "en"), ("--record",)):
            p = self.lancer(*args)
            self.assertNotIn(SENTINELLE, p.stdout + p.stderr)
        self.assertEqual([a for a in self.appels() if a.split(" ")[0] in ("INTERDIT", "security", "psql", "docker", "pg_dump", "curl")], [])
        self.assertEqual(set(self.ollama.requetes) - {("GET", "/api/tags")}, set())


if __name__ == "__main__":
    unittest.main()
