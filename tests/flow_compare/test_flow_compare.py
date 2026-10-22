"""
Tests de la comparaison de deux rapports (tools/flow_compare.py) : des comptes, jamais une clé de ticket (change database-only, D9).

    uv run python -m unittest discover -s tests/flow_compare -v

La sous-commande `data` (voie CSV contre base) est retirée : code 2, aucune connexion, aucune lecture de fichier. Seule `reports` reste.
Aucun accès à la base ni au disque hors dossier temporaire. Données inventées.
"""
import contextlib
import io
import re
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flow_compare as fc  # noqa: E402
from flow_compare_messages import CATALOGS  # noqa: E402
from messages import Messages, check_catalogs  # noqa: E402

T = Messages(CATALOGS, "fr")
CLE = re.compile(r"\b[A-Z][A-Z0-9_]*-\d+\b")


class Rapports(unittest.TestCase):
    def rapport(self, dossier, nom, texte):
        chemin = Path(dossier) / nom
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def test_catalogues_coherents(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_rapports(self):
        with tempfile.TemporaryDirectory() as d:
            a, b, c = (Path(d) / n for n in ("a.md", "b.md", "c.md"))
            a.write_text("# Rapport série-avant\nligne 1\nligne 2\n", encoding="utf-8")
            b.write_text("# Rapport série-apres\nligne 1\nligne 2\n", encoding="utf-8")
            c.write_text("# Rapport série-apres\nligne 1\nligne X\nligne 3\n", encoding="utf-8")
            self.assertEqual(fc.comparer_rapports(a, b, T).total, 0)           # le titre (nom) est ignoré
            self.assertEqual(fc.comparer_rapports(a, c, T).total, 2)           # une ligne différente et une ligne en plus

    def test_alignement_une_ligne_en_plus_ne_decale_pas_les_suivantes(self):
        corps = "\n".join(f"ligne {i}" for i in range(40))
        with tempfile.TemporaryDirectory() as d:
            a = self.rapport(d, "a.md", "# Rapport a\n\n## S1\n\n" + corps + "\n")
            b = self.rapport(d, "b.md", "# Rapport b\n\nFusion de 2 exports par clé (20 ticket(s) en double retiré(s)).\n\n## S1\n\nligne 0\n"
                             + "\n".join(f"ligne {i}" for i in range(1, 40)) + "\n")
            e = fc.comparer_rapports(a, b, T)
            self.assertEqual(e.total, 0, "\n".join(e.lignes))                  # titre et ligne de fusion ignorés, rien n'est décalé

    def test_ligne_export_sans_le_nom_du_fichier(self):
        with tempfile.TemporaryDirectory() as d:
            a = self.rapport(d, "a.md", "# t\nExport : e0.csv, e1.csv · 108 tickets · 4 dépendances\n")
            b = self.rapport(d, "b.md", "# t\nExport : base · 108 tickets · 4 dépendances\n")
            c = self.rapport(d, "c.md", "# t\nExport: database · 108 tickets · 4 dependencies\n")
            d_ = self.rapport(d, "d.md", "# t\nExport: e0.csv · 108 tickets · 4 dependencies\n")
            self.assertEqual(fc.comparer_rapports(a, b, T).total, 0)
            self.assertEqual(fc.comparer_rapports(c, d_, T).total, 0)
            e = self.rapport(d, "e.md", "# t\nExport : base · 109 tickets · 4 dépendances\n")
            self.assertEqual(fc.comparer_rapports(a, e, T).total, 1)           # un nombre différent reste un écart

    def test_ecarts_restants_par_numero_de_section_sans_contenu(self):
        with tempfile.TemporaryDirectory() as d:
            base_ = "# t\nintro\n## A\na1\na2\n## B\nb1\nb2\n## C\nc1\n"
            a = self.rapport(d, "a.md", base_)
            b = self.rapport(d, "b.md", base_.replace("b2", "SECRET-42").replace("c1", "c1\nc2"))
            e = fc.comparer_rapports(a, b, T)
            texte = "\n".join(e.lignes)
            self.assertEqual(e.total, 2)
            self.assertIn("section 2 : 1 ligne(s) en écart", texte)
            self.assertIn("section 3 : 1 ligne(s) en écart", texte)
            self.assertNotIn("SECRET", texte)
            self.assertNotIn("section 0", texte)
            self.assertIsNone(CLE.search(texte), texte)

    def test_listes_dans_un_autre_ordre_comptent_comme_un_ecart_localise(self):
        with tempfile.TemporaryDirectory() as d:
            a = self.rapport(d, "a.md", "# t\n## S\n- Types : Story 4, Bug 4\n")
            b = self.rapport(d, "b.md", "# t\n## S\n- Types : Bug 4, Story 4\n")
            self.assertEqual(fc.comparer_rapports(a, b, T).total, 1)           # l'ordre est désormais déterministe : c'est un vrai écart

    def test_main_rapports_codes_de_sortie(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.md", Path(d) / "b.md"
            a.write_text("# t\nx\n", encoding="utf-8")
            b.write_text("# u\nx\n", encoding="utf-8")
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                self.assertEqual(fc.main(["reports", str(a), str(b)]), 0)
            self.assertIn("Aucun écart", sortie.getvalue())
            b.write_text("# u\ny\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(fc.main(["reports", str(a), str(b)]), 1)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(fc.main(["reports", str(a), str(Path(d) / "absent.md")]), 2)


class DonneesRetiree(unittest.TestCase):
    """Design D9 : `data` est refusée (code 2) sans connexion à la base ni lecture de fichier."""

    def lancer(self, *argv):
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur), contextlib.redirect_stdout(io.StringIO()) as sortie:
            code = fc.main(list(argv))
        return code, sortie.getvalue() + erreur.getvalue()

    def test_data_refusee_avec_la_phrase_de_la_conception_dans_les_deux_langues(self):
        for langue, phrase in (("fr", "data est retirée : la voie CSV n'existe plus"), ("en", "data is retired: the CSV route no longer exists")):
            for argv in (["data"], ["data", "export.csv"], ["data", "a.csv", "b.csv", "--history"], ["data", "a.csv", "--history", "cache.json"]):
                code, sortie = self.lancer("--language", langue, *argv)
                self.assertEqual(code, 2, (argv, sortie))
                self.assertIn(phrase, sortie)

    def test_data_ne_lit_aucun_fichier_et_n_ouvre_aucune_connexion(self):
        import builtins
        ouvertures = []
        vrai = builtins.open

        def espion(chemin, *a, **k):
            ouvertures.append(str(chemin))
            return vrai(chemin, *a, **k)

        with unittest.mock.patch.object(builtins, "open", espion):
            code, sortie = self.lancer("data", "export.csv")
        self.assertEqual(code, 2)
        self.assertFalse(any("export.csv" in o for o in ouvertures))

    def test_data_ne_figure_plus_dans_l_aide(self):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), self.assertRaises(SystemExit):
            fc.main(["--help"])
        self.assertIn("{reports}", sortie.getvalue())
        self.assertNotIn("data", sortie.getvalue().replace("databases", ""))

    def test_le_module_ne_charge_ni_la_base_ni_les_lecteurs_de_csv(self):
        source = (Path(fc.__file__)).read_text(encoding="utf-8")
        for interdit in ("import db", "flux_jira", "dependencies_jira", "flow_store", "read_exports", "charger_historique"):
            self.assertNotIn(interdit, source.replace("flux_jira.py", ""))


if __name__ == "__main__":
    unittest.main()
