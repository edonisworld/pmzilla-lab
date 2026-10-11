"""
Tests de la comparaison base contre CSV (tools/flow_compare.py) : des comptes, jamais une clé de ticket.

    uv run --with numpy --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_compare -v

Données inventées (PROJ-n, équipes Alpha et Beta). Les tests avec base utilisent la base jetable (bash tools/dbtest.sh flow_compare ; installation.md, 14.5) ; sans elle ils sont sautés.
"""
import contextlib
import copy
import io
import json
import os
import re
import secrets
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "flow_import"))
sys.path.insert(0, str(RACINE / "tests" / "flow_store"))
import db  # noqa: E402
import dependencies_jira  # noqa: E402
import flow_compare as fc  # noqa: E402
import flow_export_reader  # noqa: E402
import flow_import  # noqa: E402
import csv_factices as cf  # noqa: E402
import aide_base as base  # noqa: E402
from flow_compare_messages import CATALOGS  # noqa: E402
from messages import Messages, check_catalogs  # noqa: E402

T = Messages(CATALOGS, "fr")
CLE = re.compile(r"\b[A-Z][A-Z0-9_]*-\d+\b")


class SansBase(unittest.TestCase):
    def test_catalogues_coherents(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_comparer_dicts_ne_montre_que_des_comptes(self):
        a = {"PROJ-1": {"etat": "Open", "equipe": "Alpha"}, "PROJ-2": {"etat": "Done", "equipe": "Alpha"}, "XYZ-9": {"etat": "Open", "equipe": "Beta"}}
        b = {"PROJ-1": {"etat": "Open", "equipe": "Alpha"}, "PROJ-2": {"etat": "Closed", "equipe": "Beta"}, "PROJ-3": {"etat": "Open", "equipe": "Beta"}}
        e = fc.Ecarts()
        fc.comparer_dicts(a, b, ("etat", "equipe"), T, "Titre", e)
        texte = "\n".join(e.lignes)
        self.assertEqual(e.total, 1 + 1 + 1 + 1)               # un côté A, un côté B, 2 champs
        self.assertIn("CSV seulement : 1", texte)
        self.assertIn("base seulement : 1", texte)
        self.assertIn("« etat » différent : 1", texte)
        self.assertIn("« equipe » différent : 1", texte)
        self.assertIn("projet PROJ : 2", texte)
        self.assertIn("projet XYZ : 1", texte)
        self.assertIsNone(CLE.search(texte), texte)             # aucune clé de ticket
        self.assertNotIn("Alpha", texte)
        self.assertNotIn("Beta", texte)

    def test_donnees_identiques_ne_donnent_aucun_ecart(self):
        a = {"PROJ-1": {"etat": "Open"}}
        e = fc.Ecarts()
        fc.comparer_dicts(a, copy.deepcopy(a), ("etat",), T, "Titre", e)
        self.assertEqual(e.total, 0)

    def test_historique_compare_les_instants_pas_les_textes(self):
        csv = {"PROJ-1": [["2026-03-01T09:00:00.000+0200", "Open", "Done"]], "PROJ-2": [["2026-03-02T09:00:00.000+0100", None, "Open"]]}
        base_ = {"PROJ-1": [["2026-03-01T07:00:00+00:00", "Open", "Done"]], "PROJ-2": [["2026-03-02T09:30:00+01:00", None, "Open"]]}
        e = fc.Ecarts()
        fc.comparer_historiques(csv, base_, {"PROJ-1", "PROJ-2"}, T, e)
        self.assertEqual(e.total, 1)                           # PROJ-2 : 30 minutes d'écart
        self.assertIsNone(CLE.search("\n".join(e.lignes)))

    def test_historique_ignore_les_cles_hors_export(self):
        e = fc.Ecarts()
        fc.comparer_historiques({"PROJ-1": [], "AUTRE-1": [["2026-03-01T09:00:00+00:00", None, "Open"]]}, {"PROJ-1": []}, {"PROJ-1"}, T, e)
        self.assertEqual(e.total, 0)

    def test_rapports(self):
        with tempfile.TemporaryDirectory() as d:
            a, b, c = (Path(d) / n for n in ("a.md", "b.md", "c.md"))
            a.write_text("# Rapport série-csv\nligne 1\nligne 2\n", encoding="utf-8")
            b.write_text("# Rapport série-base\nligne 1\nligne 2\n", encoding="utf-8")
            c.write_text("# Rapport série-base\nligne 1\nligne X\nligne 3\n", encoding="utf-8")
            self.assertEqual(fc.comparer_rapports(a, b, T).total, 0)           # le titre (nom) est ignoré
            self.assertEqual(fc.comparer_rapports(a, c, T).total, 2)           # une ligne différente et une ligne en plus

    def rapport(self, dossier, nom, texte):
        chemin = Path(dossier) / nom
        chemin.write_text(texte, encoding="utf-8")
        return chemin

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


class AvecBase(unittest.TestCase):
    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dossier = Path(self.temp.name)
        self.nom = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._nettoyer)
        self.admin.execute(f'CREATE DATABASE "{self.nom}"')
        self.url = base.url_vers(self.nom)
        self.conn = db.connect(self.url, password=base.MOT_DE_PASSE)
        db.migrer(self.conn, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        self.conn.commit()
        self.flux = cf.reglages()
        self.dep = {**dependencies_jira.DEFAULTS, "colonnes": {k: list(v) for k, v in dependencies_jira.DEFAULTS["colonnes"].items()}}

    def _nettoyer(self):
        with contextlib.suppress(Exception):
            self.conn.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom}" WITH (FORCE)')
        self.admin.close()

    def env(self):
        """URL de la base jetable ; le vrai Trousseau n'est jamais interrogé (faux binaire security)."""
        return {db.VARIABLE_URL: self.url, db.VARIABLE_SECURITY: str(base.FAUX_SECURITY)}

    def csv(self, nom, lignes):
        return str(cf.ecrire(self.dossier / nom, lignes))

    def importer(self, chemins, cache=None):
        donnees = flow_export_reader.lire_exports(chemins, self.flux)
        flow_import.importer(self.conn, donnees, cache, flow_export_reader.fuseau(self.flux))
        self.conn.commit()

    def comparer(self, chemins, historique=None):
        with unittest.mock.patch.dict(os.environ, self.env()):
            return fc.comparer_donnees(chemins, historique, T, self.flux, self.dep)

    def jeu(self):
        return [cf.ligne("PROJ-1", Team="Alpha", Team2="Beta", **{"Outward issue link (Blocks)": "PROJ-2"}),
                cf.ligne("PROJ-2", Team="Beta", Status="Closed", Resolved="10/Jan/2026 12:30", Resolution="Done",
                         **{"Status Category": "Done"}),
                cf.ligne("PROJ-3", Team="", **{"Linked Issues": "PROJ-1"})]

    def test_meme_export_aucun_ecart(self):
        f = self.csv("a.csv", self.jeu())
        self.importer([f])
        e = self.comparer([f])
        self.assertEqual(e.total, 0, "\n".join(e.lignes))

    def test_un_ecart_est_compte_sans_cle_ni_valeur(self):
        f = self.csv("a.csv", self.jeu())
        self.importer([f])
        self.conn.execute("SET ROLE pmzilla_flow")
        self.conn.execute("UPDATE flow.issues SET status = 'Zorglub' WHERE key = 'PROJ-1'")
        self.conn.execute("DELETE FROM flow.issues WHERE key = 'PROJ-3'")
        self.conn.execute("RESET ROLE")
        self.conn.commit()
        e = self.comparer([f])
        texte = "\n".join(e.lignes)
        self.assertGreaterEqual(e.total, 2)
        self.assertIn("CSV seulement : 1", texte)
        self.assertIn("« etat » différent : 1", texte)
        self.assertIsNone(CLE.search(texte), texte)
        self.assertNotIn("Zorglub", texte)
        self.assertNotIn("Alpha", texte)

    def test_historique(self):
        f = self.csv("a.csv", self.jeu())
        cache = {"PROJ-1": {"termine": False, "transitions": [["2026-03-01T09:00:00.000+0200", "Open", "In Progress"]]}}
        self.importer([f], cache)
        chemin = self.dossier / "cache.json"
        chemin.write_text(json.dumps(cache), encoding="utf-8")
        self.assertEqual(self.comparer([f], chemin).total, 0)
        cache["PROJ-1"]["transitions"].append(["2026-03-05T09:00:00.000+0200", "In Progress", "Done"])
        chemin.write_text(json.dumps(cache), encoding="utf-8")
        e = self.comparer([f], chemin)
        self.assertEqual(e.total, 1)

    def test_main_de_bout_en_bout(self):
        f = self.csv("a.csv", self.jeu())
        self.importer([f])
        sortie = io.StringIO()
        import flux_jira
        with unittest.mock.patch.dict(os.environ, self.env()), \
                unittest.mock.patch.object(flux_jira, "config", return_value=self.flux), \
                unittest.mock.patch.object(dependencies_jira, "config", return_value=self.dep), \
                contextlib.redirect_stdout(sortie):
            code = fc.main(["data", f])
        self.assertEqual(code, 0, sortie.getvalue())
        self.assertIn("Aucun écart", sortie.getvalue())
        self.assertIsNone(CLE.search(sortie.getvalue()), sortie.getvalue())


if __name__ == "__main__":
    unittest.main()
