"""
Tests de tools/flow_import.py sur une base jetable (même mécanisme que tests/db : base pmzilla_test_<hex> créée puis supprimée).

    bash tests/... (voir tests/db/test_db.py : PMZILLA_LAB_DB_URL et PMZILLA_LAB_DB_PASSWORD de la base jetable)

Données inventées (PROJ-n, équipes Alpha et Beta), jamais le vrai Jira. Sautés si la base manque.
"""
import contextlib
import datetime as dt
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

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "db"))
import csv_factices as cf  # noqa: E402
import test_db as base     # noqa: E402
from test_db import db     # noqa: E402
import flow_import         # noqa: E402
import flux_jira           # noqa: E402

UTC = dt.timezone.utc


class ImportBase(unittest.TestCase):
    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.temp = tempfile.TemporaryDirectory()
        self.dossier = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = base.url_vers(self.nom_base)
        self.conn = db.connect(self.url, password=base.MOT_DE_PASSE)
        db.migrer(self.conn, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        self.conn.commit()
        self.reglages = cf.reglages()

    def _supprimer(self):
        with contextlib.suppress(Exception):
            self.conn.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    # --- outils -----------------------------------------------------------------------------------------------------
    def csv(self, nom, lignes, entete=None):
        return str(cf.ecrire(self.dossier / nom, lignes, entete))

    def cache(self, contenu, nom="cache.json"):
        chemin = self.dossier / nom
        chemin.write_text(json.dumps(contenu), encoding="utf-8")
        return str(chemin)

    def lancer(self, *arguments, langue=None):
        """Lance main() sur la base jetable ; rend (code, sortie standard, sortie d'erreur)."""
        sortie, erreur = io.StringIO(), io.StringIO()
        code = 0
        argv = list(arguments) + (["--language", langue] if langue else [])
        with unittest.mock.patch.dict(os.environ, {db.VARIABLE_URL: self.url}), \
                unittest.mock.patch.object(flux_jira, "config", return_value=self.reglages), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            try:
                flow_import.main(argv)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
        return code, sortie.getvalue(), erreur.getvalue()

    def comptes(self, *arguments, **kw):
        """Importe et rend les nombres de la sortie, par ordre d'apparition."""
        code, sortie, erreur = self.lancer(*arguments, **kw)
        self.assertEqual(code, 0, erreur)
        return [int(n) for n in re.findall(r"\d+", sortie)]

    def un(self, sql, *params):
        return self.conn.execute(sql, params).fetchone()

    def tout(self, sql, *params):
        return self.conn.execute(sql, params).fetchall()

    def nombre(self, table):
        self.conn.rollback()
        return self.un(f"SELECT count(*) FROM flow.{table}")[0]


class Import(ImportBase):
    def test_premier_import_puis_reimport_identique(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1"), cf.ligne("PROJ-2", Team="Beta")])
        # lus, insérés, mis à jour, inchangés, illisibles, équipes, liens ajoutés, retirés
        self.assertEqual(self.comptes(f)[:8], [2, 2, 0, 0, 0, 2, 0, 0])
        self.assertEqual(self.nombre("issues"), 2)
        self.assertEqual(self.comptes(f)[:8], [2, 0, 0, 2, 0, 0, 0, 0])

    def test_champs_ecrits(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1", Resolved="10/Jul/2026 14:05", Resolution="Done", **{"Story Points": "3.5"},
                                        **{"Parent key": "PROJ-9"})])
        self.comptes(f)
        ligne = self.un("SELECT project, type, status, status_category, resolution, story_points, parent_key, "
                        "created_at, resolved_at, status_category_changed_at, updated_at FROM flow.issues")
        self.assertEqual(ligne[:7], ("PROJ", "Story", "In Progress", "In Progress", "Done", 3.5, "PROJ-9"))
        self.assertEqual(ligne[8], dt.datetime(2026, 7, 10, 12, 5, tzinfo=UTC))      # été : UTC+2
        self.assertEqual(ligne[7], dt.datetime(2026, 1, 2, 8, 30, tzinfo=UTC))       # hiver : UTC+1
        self.assertEqual(ligne[10], dt.datetime(2026, 1, 6, 10, 15, tzinfo=UTC))

    def test_ligne_modifiee_et_updated_plus_recent(self):
        self.comptes(self.csv("a.csv", [cf.ligne("PROJ-1"), cf.ligne("PROJ-2")]))
        f = self.csv("b.csv", [cf.ligne("PROJ-1", Status="Done", Updated="07/Jan/2026 08:00"), cf.ligne("PROJ-2")])
        self.assertEqual(self.comptes(f)[:5], [2, 0, 1, 1, 0])
        self.assertEqual(self.un("SELECT status, updated_at FROM flow.issues WHERE key = 'PROJ-1'"),
                         ("Done", dt.datetime(2026, 1, 7, 7, 0, tzinfo=UTC)))
        # seule la date Updated change : une mise à jour aussi
        g = self.csv("c.csv", [cf.ligne("PROJ-1", Status="Done", Updated="08/Jan/2026 08:00"), cf.ligne("PROJ-2")])
        self.assertEqual(self.comptes(g)[:5], [2, 0, 1, 1, 0])

    def test_un_export_plus_ancien_n_ecrase_pas(self):
        self.comptes(self.csv("a.csv", [cf.ligne("PROJ-1", Status="Done", Updated="08/Jan/2026 08:00")]))
        ancien = self.csv("b.csv", [cf.ligne("PROJ-1", Status="Open", Updated="07/Jan/2026 08:00")])
        self.assertEqual(self.comptes(ancien)[:5], [1, 0, 0, 1, 0])
        self.assertEqual(self.un("SELECT status FROM flow.issues WHERE key = 'PROJ-1'"), ("Done",))

    def test_ticket_absent_du_nouvel_export_conserve(self):
        self.comptes(self.csv("a.csv", [cf.ligne("PROJ-1"), cf.ligne("PROJ-2")]))
        self.comptes(self.csv("b.csv", [cf.ligne("PROJ-1")]))
        self.assertEqual(self.nombre("issues"), 2)

    def test_multi_equipes_sans_equipe(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1", Team="Alpha;Beta", Team2="Beta"), cf.ligne("PROJ-2", Team=""),
                               cf.ligne("PROJ-3", Team="Beta", Team2="Alpha")])
        self.comptes(f)
        self.assertEqual(self.tout("SELECT i.key, t.name FROM flow.issues i LEFT JOIN flow.teams t ON t.id = i.team_id "
                                   "ORDER BY 1"), [("PROJ-1", "Alpha"), ("PROJ-2", None), ("PROJ-3", "Beta")])
        self.assertEqual(self.tout("SELECT it.issue_key, t.name, it.position FROM flow.issue_teams it "
                                   "JOIN flow.teams t ON t.id = it.team_id ORDER BY 1, 3"),
                         [("PROJ-1", "Alpha", 1), ("PROJ-1", "Beta", 2), ("PROJ-3", "Beta", 1), ("PROJ-3", "Alpha", 2)])
        # une équipe change : la différence seulement est écrite, le reste est conservé
        g = self.csv("b.csv", [cf.ligne("PROJ-1", Team="Beta", Team2=""), cf.ligne("PROJ-2", Team=""),
                               cf.ligne("PROJ-3", Team="Beta", Team2="Alpha")])
        self.assertEqual(self.comptes(g)[:5], [3, 0, 1, 2, 0])
        self.assertEqual(self.tout("SELECT team_id, position FROM flow.issue_teams WHERE issue_key = 'PROJ-1'"), [(2, 1)])

    def test_liens_sans_doublon_au_reimport(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1", **{"Outward issue link (Blocks)": "PROJ-2",
                                                      "Inward issue link (Blocks)": "PROJ-3", "Linked Issues": "PROJ-4"}),
                               cf.ligne("PROJ-2")])
        self.assertEqual(self.comptes(f)[5:8], [1, 3, 0])
        self.assertEqual(self.tout("SELECT target_key, link_type, direction FROM flow.links ORDER BY 1"),
                         [("PROJ-2", "Blocks", "outward"), ("PROJ-3", "Blocks", "inward"), ("PROJ-4", "", None)])
        self.assertEqual(self.comptes(f)[5:8], [0, 0, 0])
        self.assertEqual(self.nombre("links"), 3)
        # un lien disparu de Jira est retiré, un lien nouveau ajouté
        g = self.csv("b.csv", [cf.ligne("PROJ-1", **{"Outward issue link (Blocks)": "PROJ-2", "Linked Issues": "PROJ-5"}),
                               cf.ligne("PROJ-2")])
        self.assertEqual(self.comptes(g)[5:8], [0, 1, 2])

    def test_export_sans_colonne_de_liens_garde_les_liens(self):
        self.comptes(self.csv("a.csv", [cf.ligne("PROJ-1", **{"Outward issue link (Blocks)": "PROJ-2"})]))
        entete = [c for c in cf.ENTETE if "link" not in c.lower() and "Linked" not in c]
        self.comptes(self.csv("b.csv", [cf.ligne("PROJ-1", Status="Done", Updated="09/Jan/2026 08:00")], entete))
        self.assertEqual(self.nombre("links"), 1)

    def test_story_points(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1", **{"Story Points": "5"}), cf.ligne("PROJ-2", **{"Story Points": "2,5"}),
                               cf.ligne("PROJ-3")])
        self.comptes(f)
        self.assertEqual([r[0] for r in self.tout("SELECT story_points FROM flow.issues ORDER BY key")],
                         [5, 2.5, None])

    def test_date_de_creation_illisible_comptee(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1", Created="pas une date"), cf.ligne("PROJ-2")])
        self.assertEqual(self.comptes(f)[:5], [1, 1, 0, 0, 1])

    def test_deux_fichiers_fusionnes(self):
        a = self.csv("a.csv", [cf.ligne("PROJ-1", Status="Open"), cf.ligne("PROJ-2")])
        b = self.csv("b.csv", [cf.ligne("PROJ-1", Status="Done"), cf.ligne("PROJ-3")])
        self.assertEqual(self.comptes(a, b)[:5], [3, 3, 0, 0, 0])
        self.assertEqual(self.un("SELECT status FROM flow.issues WHERE key = 'PROJ-1'")[0], "Done")

    def test_format_de_date_fixe_avec_heure(self):
        """Le réglage du format de date a été retiré (commit 2552d15) : l'export de l'API écrit toujours jour/mois/année
        et heure (history_common.FORMAT_DATE). Une date à minuit est lue ; une date sans heure ne l'est plus et sa ligne est écartée."""
        f = self.csv("a.csv", [cf.ligne("PROJ-1", Created="02/Jan/2026 00:00", Resolved="15/Jan/2026 00:00",
                                        Updated="16/Jan/2026 00:00"),
                               cf.ligne("PROJ-2", Created="02/Jan/2026", Resolved="15/Jan/2026", Updated="16/Jan/2026")])
        comptes = self.comptes(f)
        self.assertEqual(self.un("SELECT resolved_at, created_at FROM flow.issues WHERE key = 'PROJ-1'"),
                         (dt.datetime(2026, 1, 14, 23, 0, tzinfo=UTC), dt.datetime(2026, 1, 1, 23, 0, tzinfo=UTC)))
        # la ligne à date sans heure est écartée comme illisible (comme test_date_de_creation_illisible_comptee) : absente de la base
        self.assertIsNone(self.un("SELECT 1 FROM flow.issues WHERE key = 'PROJ-2'"))
        self.assertEqual((comptes[0], comptes[4]), (1, 1))     # une ligne importée, une écartée illisible

    def test_fuseau_ete_et_hiver(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1", Created="15/Jul/2026 10:00"), cf.ligne("PROJ-2", Created="15/Jan/2026 10:00")])
        self.comptes(f)
        self.assertEqual([r[0] for r in self.tout("SELECT created_at FROM flow.issues ORDER BY key")],
                         [dt.datetime(2026, 7, 15, 8, 0, tzinfo=UTC), dt.datetime(2026, 1, 15, 9, 0, tzinfo=UTC)])

    def test_fuseau_reglable(self):
        self.reglages = cf.reglages(export_fuseau="UTC")
        self.comptes(self.csv("a.csv", [cf.ligne("PROJ-1", Created="15/Jul/2026 10:00")]))
        self.assertEqual(self.un("SELECT created_at FROM flow.issues")[0], dt.datetime(2026, 7, 15, 10, 0, tzinfo=UTC))


class Transitions(ImportBase):
    def test_ajout_reimport_cle_inconnue_et_millisecondes(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1"), cf.ligne("PROJ-2")])
        cache = self.cache({
            "PROJ-1": {"termine": False, "transitions": [["2026-03-01T09:00:00.000+0200", "Open", "In Progress"],
                                                         ["2026-03-02T09:00:00.000+0100", "In Progress", "Done"]]},
            "proj-2": {"termine": False, "transitions": [[1767225600000, None, "Open"], ["pas une date", "Open", "Done"]]},
            "PROJ-77": {"termine": True, "transitions": [["2026-03-01T09:00:00.000+0200", "Open", "Done"]]},
        })
        # 8 compteurs de tickets puis : ajoutées, ignorées sans ticket, illisibles
        self.assertEqual(self.comptes(f, "--history", cache)[8:11], [3, 1, 1])
        self.assertEqual(self.tout("SELECT issue_key, transitioned_at, from_status, to_status FROM flow.transitions "
                                   "ORDER BY transitioned_at"),
                         [("PROJ-2", dt.datetime(2026, 1, 1, 0, 0, tzinfo=UTC), None, "Open"),
                          ("PROJ-1", dt.datetime(2026, 3, 1, 7, 0, tzinfo=UTC), "Open", "In Progress"),
                          ("PROJ-1", dt.datetime(2026, 3, 2, 8, 0, tzinfo=UTC), "In Progress", "Done")])
        self.assertEqual(self.comptes(f, "--history", cache)[8:11], [0, 1, 1])      # réimport : rien d'ajouté
        self.assertEqual(self.nombre("transitions"), 3)

    def test_une_entree_du_cache_sans_transition_marque_le_ticket_avec_historique(self):
        """Un ticket « avec historique » a une entrée dans le cache, même vide (un ticket qui n'a jamais changé d'état n'a aucune
        transition) : sinon la lecture de la base ne retrouverait pas la couverture ni les dormants du cache."""
        f = self.csv("a.csv", [cf.ligne("PROJ-1"), cf.ligne("PROJ-2"), cf.ligne("PROJ-3")])
        cache = self.cache({
            "PROJ-1": {"termine": False, "transitions": [["2026-03-01T09:00:00.000+0200", "Open", "In Progress"]]},
            "PROJ-2": {"termine": False, "transitions": []},                       # entrée sans transition
            "PROJ-77": {"termine": True, "transitions": []},                       # absent de l'export : ignoré
        })
        code, sortie, _ = self.lancer(f, "--history", cache)
        self.assertEqual(code, 0)
        self.assertIn("2 nouveau(x)", sortie)                                      # PROJ-1 et PROJ-2, pas PROJ-3
        self.assertEqual(self.tout("SELECT key FROM flow.issues WHERE has_history ORDER BY key"), [("PROJ-1",), ("PROJ-2",)])
        _, sortie, _ = self.lancer(f, "--history", cache)
        self.assertIn("0 nouveau(x)", sortie)                                      # réimport : rien de nouveau
        _, sortie, _ = self.lancer(f)                                              # sans --history : rien n'est marqué ni démarqué
        self.assertEqual(self.tout("SELECT count(*) FROM flow.issues WHERE has_history"), [(2,)])
        self.assertNotIn("PROJ-", sortie)

    def test_une_transition_nouvelle_s_ajoute_sans_rien_supprimer(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1")])
        self.comptes(f, "--history", self.cache({"PROJ-1": {"termine": False, "transitions": [
            ["2026-03-01T09:00:00.000+0200", "Open", "In Progress"]]}}))
        self.comptes(f, "--history", self.cache({"PROJ-1": {"termine": False, "transitions": [
            ["2026-03-05T09:00:00.000+0200", "In Progress", "Done"]]}}, "autre.json"))
        self.assertEqual(self.nombre("transitions"), 2)

    def test_sans_history_aucune_transition(self):
        code, sortie, _ = self.lancer(self.csv("a.csv", [cf.ligne("PROJ-1")]))
        self.assertEqual(code, 0)
        self.assertEqual(self.nombre("transitions"), 0)
        self.assertNotIn("Transitions", sortie)

    def test_cache_illisible_ou_absent(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1")])
        (self.dossier / "casse.json").write_text("{pas du json", encoding="utf-8")
        for cache in (str(self.dossier / "casse.json"), str(self.dossier / "absent.json")):
            code, sortie, erreur = self.lancer(f, "--history", cache)
            self.assertEqual(code, 1)
            self.assertIn("--history", erreur)
        self.assertEqual(self.nombre("issues"), 0)


class Refus(ImportBase):
    def test_sans_colonne_updated_rien_n_est_ecrit(self):
        entete = [c for c in cf.ENTETE if c != "Updated"]
        code, sortie, erreur = self.lancer(self.csv("export-x.csv", [cf.ligne("PROJ-1")], entete))
        self.assertEqual(code, 1)
        self.assertIn("export-x.csv", erreur)
        self.assertIn("Updated", erreur)
        self.assertNotIn("PROJ-1", sortie + erreur)
        self.assertEqual(self.nombre("issues"), 0)

    def test_updated_illisible_message_sans_valeur(self):
        code, sortie, erreur = self.lancer(self.csv("export-y.csv", [cf.ligne("PROJ-1", Updated="valeur-secrete-xyz")]))
        self.assertEqual(code, 1)
        self.assertIn("Updated", erreur)
        self.assertNotIn("valeur-secrete-xyz", sortie + erreur)
        self.assertNotIn("PROJ-1", sortie + erreur)
        self.assertEqual(self.nombre("issues"), 0)

    def test_base_injoignable_message_de_la_base(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1")])
        sortie, erreur = io.StringIO(), io.StringIO()
        with unittest.mock.patch.dict(os.environ, {db.VARIABLE_URL: "postgresql://postgres@127.0.0.1:9/inexistante"}), \
                unittest.mock.patch.object(flux_jira, "config", return_value=self.reglages), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            with self.assertRaises(SystemExit) as cm:
                flow_import.main([f])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Connexion à la base impossible", erreur.getvalue())

    def test_erreur_en_cours_d_import_annule_tout(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1"), cf.ligne("PROJ-2")])
        with unittest.mock.patch.object(flow_import, "_liens", side_effect=RuntimeError("PROJ-1 Alpha")):
            code, sortie, erreur = self.lancer(f)
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", erreur)
        self.assertNotIn("PROJ-1", sortie + erreur)
        self.assertNotIn("Alpha", sortie + erreur)
        self.assertEqual((self.nombre("issues"), self.nombre("teams")), (0, 0))


class EssaiEtSortie(ImportBase):
    def donnees(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1", Team="Alpha;Beta", **{"Outward issue link (Blocks)": "PROJ-2"}),
                               cf.ligne("PROJ-2", Team="Beta"), cf.ligne("PROJ-3", Created="illisible")])
        cache = self.cache({"PROJ-1": {"termine": False, "transitions": [["2026-03-01T09:00:00.000+0200", "Open", "Done"]]},
                            "PROJ-8": {"termine": False, "transitions": [["2026-03-01T09:00:00.000+0200", "Open", "Done"]]}})
        return f, cache

    def test_dry_run_n_ecrit_rien_et_donne_les_memes_comptes(self):
        f, cache = self.donnees()
        code, essai, _ = self.lancer(f, "--history", cache, "--dry-run")
        self.assertEqual(code, 0)
        for table in ("issues", "teams", "issue_teams", "links", "transitions"):
            self.assertEqual(self.nombre(table), 0, table)
        code, reel, _ = self.lancer(f, "--history", cache)
        self.assertEqual(code, 0)
        self.assertEqual(essai.splitlines()[1:], reel.splitlines())
        self.assertEqual(self.nombre("issues"), 2)

    def test_la_sortie_ne_contient_ni_cle_ni_equipe(self):
        f, cache = self.donnees()
        for arguments in ((f,), (f, "--history", cache), (f, "--history", cache, "--dry-run"),
                          (f, "--history", cache, "--language", "en")):
            code, sortie, erreur = self.lancer(*arguments)
            self.assertEqual(code, 0)
            tout = sortie + erreur
            self.assertIsNone(re.search(r"[A-Z][A-Z0-9_]*-\d+", tout), tout)
            self.assertNotIn("Alpha", tout)
            self.assertNotIn("Beta", tout)

    def test_langue_anglaise(self):
        f, cache = self.donnees()
        _, sortie, _ = self.lancer(f, "--history", cache, langue="en")
        self.assertIn("Tickets read: 2", sortie)
        self.assertIn("Transitions added: 1; ignored without ticket: 1", sortie)


if __name__ == "__main__":
    unittest.main()
