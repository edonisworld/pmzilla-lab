"""Tests de tools/flow_store.py sur la base jetable : les structures lues dans le schéma flow sont égales à celles des lecteurs
de CSV pour le même jeu inventé (tickets PROJ-n, équipes Alpha et Beta, aucune donnée réelle).

    bash tools/dbtest.sh flow_store          (instance jetable : installation.md, 14.5 ; sautés sans elle)

Le jeu (jeu.py) est écrit deux fois : en CSV (lu par flux_jira.read_exports et dependencies_jira.read_exports) et en lignes SQL
sous le rôle pmzilla_flow (lu par flow_store sous le rôle pmzilla_flow_ro).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import aide_base as base          # noqa: E402
import jeu                        # noqa: E402

import dependencies_jira as dj    # noqa: E402
import flux_jira as fj            # noqa: E402


def trier(tickets):
    return sorted(tickets, key=lambda t: t["cle"])


class LectureDeLaBase(base.AvecBase):
    def setUp(self):
        super().setUp()
        import flow_store
        self.store = flow_store
        self.dossier = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.dossier, ignore_errors=True))

    def reglages_flux(self, fuseau=None):
        reglages = {**fj.DEFAULT_CONFIG}
        if fuseau:
            reglages["export_fuseau"] = fuseau
        return reglages

    def reglages_dependances(self, fuseau=None):
        reglages = {**dj.DEFAULTS}
        if fuseau:
            reglages["export_fuseau"] = fuseau
        return reglages

    def csv(self, liste, **options):
        chemin = self.dossier / "export.csv"
        jeu.ecrire_csv(chemin, liste, **options)
        return str(chemin)

    # --- flux_jira ------------------------------------------------------------------------------------------------
    def test_tickets_de_flux_egaux_au_csv(self):
        liste = jeu.tickets()
        self.inserer(liste, jeu.liens(), [])
        reglages = self.reglages_flux()
        attendu = fj.read_exports([self.csv(liste)], reglages)
        lu = self.store.lire_tickets_flux(reglages)
        self.assertEqual(trier(lu[0]), trier(attendu[0]))
        self.assertEqual(lu[1:], attendu[1:])        # colonnes trouvées, illisibles, doublons
        multi = [t for t in lu[0] if len(t["equipes"]) > 1]
        sans = [t for t in lu[0] if t["equipe"] == "(sans équipe)"]
        self.assertTrue(multi and sans)
        self.assertTrue(all(t["equipe"] == t["equipes"][0] for t in multi))
        self.assertTrue(all(t["equipes"] == [] for t in sans))
        self.assertTrue(any(t["resolu_a"] and t["resolu_a"].minute for t in lu[0]))

    def test_dates_a_minuit(self):
        """Le format de date est fixe depuis le commit 2552d15 (jour, mois, année et heure) : des instants à minuit sont lus
        comme les autres, et la base rend les mêmes tickets que le CSV. (Un export sans heure n'est plus lu : voir
        tests/flow_import, test_format_de_date_fixe_avec_heure.)"""
        liste = jeu.a_minuit(jeu.tickets())
        self.inserer(liste, [], [])
        reglages = self.reglages_flux()
        attendu = fj.read_exports([self.csv(liste)], reglages)
        lu = self.store.lire_tickets_flux(reglages)
        self.assertEqual(trier(lu[0]), trier(attendu[0]))
        self.assertTrue(any(t["resolu"] for t in lu[0]))

    def test_autre_fuseau(self):
        liste = jeu.tickets()
        self.inserer(liste, [], [], fuseau="America/New_York")
        reglages = self.reglages_flux(fuseau="America/New_York")
        attendu = fj.read_exports([self.csv(liste)], reglages)
        self.assertEqual(trier(self.store.lire_tickets_flux(reglages)[0]), trier(attendu[0]))
        # lu dans le fuseau par défaut, le même instant tombe à une autre heure : la conversion n'est pas neutre
        paris = self.store.lire_tickets_flux(self.reglages_flux())[0]
        self.assertNotEqual([t["resolu_a"] for t in trier(paris)], [t["resolu_a"] for t in trier(attendu[0])])

    def test_fuseau_inconnu(self):
        with self.assertRaises(base.db.ErreurBase) as cm:
            self.store.lire_tickets_flux(self.reglages_flux(fuseau="Mars/Olympus"))
        self.assertIn("Mars/Olympus", str(cm.exception))

    # --- dependencies_jira ----------------------------------------------------------------------------------------
    def test_dependances_egales_au_csv(self):
        liste = jeu.tickets()
        self.inserer(liste, jeu.liens(), [])
        reglages = self.reglages_dependances()
        attendu = dj.read_exports([self.csv(liste)], reglages)
        lu = self.store.lire_dependances(reglages)
        self.assertEqual(lu["tickets"], attendu["tickets"])
        self.assertEqual(lu["liens"], attendu["liens"])
        self.assertEqual(lu["colonnes"], attendu["colonnes"])
        self.assertEqual(lu["liens_types"], attendu["liens_types"])
        self.assertEqual(lu["liens_simples"], attendu["liens_simples"])
        self.assertEqual(lu["tronques"], [])
        self.assertEqual(lu["fichiers"], ["base"])
        sens = {(typ, s) for _, _, typ, s in lu["liens"]}
        self.assertEqual(sens, {("Blocks", "entrant"), ("Blocks", "sortant"), ("Depends", "sortant"), (None, None)})
        self.assertTrue(any(t["parent"] for t in lu["tickets"].values()))

    def test_dependances_sans_liens_simples(self):
        liens = [lien for lien in jeu.liens() if lien[2]]
        liste = jeu.tickets()
        self.inserer(liste, liens, [])
        reglages = self.reglages_dependances()
        attendu = dj.read_exports([self.csv(liste, liens_base=liens)], reglages)
        lu = self.store.lire_dependances(reglages)
        self.assertEqual(lu["liens"], attendu["liens"])
        self.assertEqual(lu["liens_simples"], [])
        self.assertEqual(lu["liens_types"], attendu["liens_types"])

    # --- historique -----------------------------------------------------------------------------------------------
    def test_historique_avec_decalages_ete_hiver(self):
        liste = jeu.tickets()
        self.inserer(liste, [], jeu.transitions())
        lu = self.store.lire_historique(self.reglages_flux())
        attendu = {f"PROJ-{i}": [] for i in range(1, 49)}
        attendu["PROJ-1"] = [["2026-01-15T09:30:00.000+0100", None, "Open"],
                             ["2026-01-20T14:05:00.000+0100", "Open", "In Progress"],
                             ["2026-07-02T08:45:00.000+0200", "In Progress", "Closed"]]
        attendu["PROJ-2"] = [["2025-10-25T23:59:00.000+0200", None, "Backlog"],
                             ["2025-10-26T03:30:00.000+0100", None, "Open"],
                             ["2026-03-29T03:30:00.000+0200", "Open", "In Progress"]]
        attendu["PROJ-4"] = [["2026-03-28T12:00:00.000+0100", "Open", "Closed"]]
        self.assertEqual(lu, attendu)

    def test_historique_egal_au_cache_de_fichier(self):
        import json
        liste = jeu.tickets()
        self.inserer(liste, [], jeu.transitions())
        cache = {t["cle"]: {"termine": bool(t["resolu"]), "transitions": []} for t in liste}
        for cle, instant, depart, arrivee in jeu.transitions():
            iso = instant.strftime("%Y-%m-%dT%H:%M:%S.000%z")
            cache[cle]["transitions"].append([iso, depart, arrivee])
        chemin = self.dossier / "transitions.json"
        chemin.write_text(json.dumps(cache), encoding="utf-8")
        self.assertEqual(self.store.lire_historique(self.reglages_flux()), fj.charger_historique(chemin))

    # --- rôle -----------------------------------------------------------------------------------------------------
    def test_lecture_seule(self):
        self.inserer(jeu.tickets(), [], [])
        conn = self.store.ouvrir()
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("SELECT current_user").fetchone()[0], "pmzilla_flow_ro")
        self.assertGreater(conn.execute("SELECT count(*) FROM flow.issues").fetchone()[0], 0)
        with self.assertRaises(base.db.psycopg.Error):
            conn.execute("DELETE FROM flow.issues")

    def test_role_inutilisable(self):
        original = self.store.ROLE_LECTURE
        self.addCleanup(setattr, self.store, "ROLE_LECTURE", original)
        self.store.ROLE_LECTURE = "pmzilla_role_inexistant"
        with self.assertRaises(base.db.ErreurBase) as cm:
            self.store.ouvrir()
        self.assertIn("pmzilla_role_inexistant", str(cm.exception))
        self.assertNotIn(base.MOT_DE_PASSE, str(cm.exception))


if __name__ == "__main__":
    unittest.main()
