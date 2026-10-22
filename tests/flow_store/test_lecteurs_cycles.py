"""Lecteurs de flow_store pour `flux_jira.py cycles` (R-58, tâche 9.3) : périodes d'étiquettes et de versions, transitions des épics.

    bash tools/dbtest.sh flow_store          (instance jetable : installation.md, 14.5 ; sautés sans elle)

Deux familles. Sans base (toujours exécutée) : une fausse connexion rend des lignes préparées ; on vérifie l'assemblage des
éléments, les paramètres des requêtes et que chaque requête passe par flow.issues avec le filtre des tickets marqués hors export.
Avec base (sautée sans Docker) : les lignes insérées sous le rôle d'import sont relues sous le rôle de lecture seule, un ticket
marqué n'apparaît dans aucune lecture, les fuseaux sont ceux de export_timezone, et la sous-commande tourne de bout en bout.
Données inventées (PROJ-n, versions et étiquettes fictives).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import aide_base as base          # noqa: E402
import jeu                        # noqa: E402
import aide_scripts as sc         # noqa: E402

import flow_store                 # noqa: E402

UTC = dt.timezone.utc
MARQUE = "out_of_export_at IS NULL"
REGLAGES = {"export_fuseau": "Europe/Paris"}


class ConnexionCannee:
    """Rend des lignes préparées selon la table interrogée ; enregistre requêtes et paramètres."""

    def __init__(self, elements=(), etiquettes=(), versions=(), transitions=()):
        self.requetes = []
        self.lignes = [("flow.transitions", list(transitions)), ("issue_label_periods", list(etiquettes)),
                       ("issue_version_periods", list(versions)), ("FROM flow.issues i", list(elements))]

    def execute(self, requete, params=None):
        self.requetes.append((requete, params))
        return next(lignes for motif, lignes in self.lignes if motif in requete)

    def close(self):
        pass


def lire_avec(connexion, etiquettes_revue):
    with unittest.mock.patch.object(flow_store, "ouvrir", return_value=connexion):
        return flow_store.lire_donnees_cycles(REGLAGES, etiquettes_revue)


class SansBase(unittest.TestCase):
    def setUp(self):
        self.ajout = dt.datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        self.retrait = dt.datetime(2026, 2, 5, 18, 0, tzinfo=UTC)
        self.connexion = ConnexionCannee(
            elements=[("PROJ-1", "PROJ", "Story", "Done", dt.datetime(2026, 2, 10, 23, 30), "Done"),
                      ("PROJ-2", None, "Epic", "In Review", None, None)],
            etiquettes=[("PROJ-1", "UM-legal", self.ajout, None), ("PROJ-2", "ER-revue", self.ajout, self.retrait)],
            versions=[("PROJ-1", "patch-alpha", self.ajout, self.retrait), ("PROJ-1", "ver-alpha", self.retrait, None)],
            transitions=[("PROJ-2", self.ajout, "Draft", "In Review")])

    def test_assemblage_des_elements(self):
        elements = {e["cle"]: e for e in lire_avec(self.connexion, ["ER-revue"])}
        e1, e2 = elements["PROJ-1"], elements["PROJ-2"]
        self.assertEqual((e1["projet"], e1["type"], e1["etat"], e1["motif"]), ("PROJ", "Story", "Done", "Done"))
        self.assertEqual(e1["resolu"], dt.date(2026, 2, 10))          # jour local (la requête rend la date naïve du fuseau d'export)
        self.assertEqual(e1["labels"], [("UM-legal", self.ajout, None)])
        self.assertEqual(e1["versions"], [("patch-alpha", self.ajout, self.retrait), ("ver-alpha", self.retrait, None)])
        self.assertEqual(e1["transitions"], [])
        self.assertEqual((e2["projet"], e2["resolu"], e2["motif"]), ("PROJ", None, ""))        # projet déduit de la clé
        self.assertEqual(e2["labels"], [("ER-revue", self.ajout, self.retrait)])
        self.assertEqual(e2["transitions"], [(self.ajout, "Draft", "In Review")])

    def test_les_etiquettes_epic_review_sont_un_parametre_de_la_requete_des_transitions(self):
        lire_avec(self.connexion, ["ER-revue", "ER-autre"])
        transitions = [(r, p) for r, p in self.connexion.requetes if "flow.transitions" in r]
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0][1]["etiquettes_revue"], ["ER-revue", "ER-autre"])
        self.assertEqual(transitions[0][1]["tz"], "Europe/Paris")
        self.assertIn("%(etiquettes_revue)s", transitions[0][0])

    def test_sans_etiquette_epic_review_aucune_transition_n_est_lue(self):
        lire_avec(self.connexion, [])
        self.assertFalse([r for r, _ in self.connexion.requetes if "flow.transitions" in r])

    def test_chaque_requete_ecarte_les_tickets_marques_hors_export(self):
        lire_avec(self.connexion, ["ER-revue"])
        self.assertEqual(len(self.connexion.requetes), 4)
        for requete, _ in self.connexion.requetes:
            self.assertIn("flow.issues", requete)
            self.assertIn(MARQUE, requete, requete)
            self.assertNotRegex(requete.split("FROM", 1)[0], "out_of_export_at")        # filtrée, jamais rendue

    def test_une_periode_d_un_ticket_absent_des_elements_est_ignoree(self):
        self.connexion.lignes[1] = ("issue_label_periods", [("PROJ-9", "UM-legal", self.ajout, None)])
        for e in lire_avec(self.connexion, []):
            self.assertEqual(e["labels"], [])

    def test_la_lecture_passe_par_le_role_de_lecture_seule(self):
        source = (Path(flow_store.__file__)).read_text(encoding="utf-8")
        self.assertIn("SET ROLE {ROLE_LECTURE}", source)
        self.assertEqual(flow_store.ROLE_LECTURE, "pmzilla_flow_ro")


def ecrire_periodes(conn, etiquettes=(), versions=()):
    """Périodes sous le rôle d'import. etiquettes : (clé, étiquette, ajoutée, retirée) ; versions : de même."""
    conn.execute("SET ROLE pmzilla_flow")
    for cle, nom, ajout, retrait in etiquettes:
        conn.execute("INSERT INTO flow.issue_label_periods (issue_key, label, added_at, removed_at) VALUES (%s, %s, %s, %s)",
                     (cle, nom, ajout, retrait))
    for cle, nom, ajout, retrait in versions:
        conn.execute("INSERT INTO flow.issue_version_periods (issue_key, version, added_at, removed_at) VALUES (%s, %s, %s, %s)",
                     (cle, nom, ajout, retrait))
    conn.execute("RESET ROLE")
    conn.commit()


def marquer(conn, *cles):
    conn.execute("SET ROLE pmzilla_flow")
    conn.execute("UPDATE flow.issues SET out_of_export_at = now() WHERE key = ANY(%s)", (list(cles),))
    conn.execute("RESET ROLE")
    conn.commit()


class AvecBase(base.AvecBase):
    def setUp(self):
        super().setUp()
        self.liste = jeu.tickets()
        self.inserer(self.liste, [], [])
        self.ajout = dt.datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        self.retrait = dt.datetime(2026, 2, 5, 18, 0, tzinfo=UTC)

    def elements(self, revue=()):
        return {e["cle"]: e for e in flow_store.lire_donnees_cycles(REGLAGES, list(revue))}

    def test_periodes_d_etiquettes_et_de_versions_relues_avec_leurs_instants(self):
        ecrire_periodes(self.conn, etiquettes=[("PROJ-5", "UM-legal", self.ajout, None), ("PROJ-5", "UM-hotfix", self.ajout, self.retrait)],
                        versions=[("PROJ-5", "patch-alpha", self.ajout, self.retrait), ("PROJ-5", "ver-alpha", self.retrait, None)])
        e = self.elements()["PROJ-5"]
        self.assertEqual(sorted(e["labels"]), sorted([("UM-legal", self.ajout, None), ("UM-hotfix", self.ajout, self.retrait)]))
        self.assertEqual(e["versions"], [("patch-alpha", self.ajout, self.retrait), ("ver-alpha", self.retrait, None)])
        self.assertTrue(all(i.tzinfo is not None for _, a, _ in e["labels"] for i in (a,)))       # instants avec fuseau

    def test_ticket_marque_hors_export_absent_de_la_lecture_et_de_ses_periodes(self):
        """Exigence « Tickets out of the export left out » : élément, périodes et transitions des marqués ne sont pas lus."""
        ecrire_periodes(self.conn, etiquettes=[("PROJ-5", "ER-revue", self.ajout, None), ("PROJ-6", "ER-revue", self.ajout, None)])
        marquer(self.conn, "PROJ-5")
        elements = self.elements(["ER-revue"])
        self.assertNotIn("PROJ-5", elements)
        self.assertEqual(elements["PROJ-6"]["labels"], [("ER-revue", self.ajout, None)])
        self.assertEqual(len(elements), len(self.liste) - 1)

    def test_transitions_lues_pour_les_seuls_tickets_a_etiquette_epic_review(self):
        conn = self.conn
        conn.execute("SET ROLE pmzilla_flow")
        for cle in ("PROJ-1", "PROJ-2"):
            conn.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, from_status, to_status) VALUES (%s, %s, %s, %s)",
                         (cle, self.ajout, "Draft", "In Review"))
        conn.execute("RESET ROLE")
        conn.commit()
        ecrire_periodes(conn, etiquettes=[("PROJ-1", "ER-revue", self.ajout, None)])
        elements = self.elements(["ER-revue"])
        self.assertEqual(elements["PROJ-1"]["transitions"], [(self.ajout, "Draft", "In Review")])
        self.assertEqual(elements["PROJ-2"]["transitions"], [])
        self.assertEqual(self.elements()["PROJ-1"]["transitions"], [])             # sans étiquette demandée, aucune transition lue

    def test_resolution_lue_en_jour_du_fuseau_d_export(self):
        """Résolu à 23:30 UTC le 10 février : le 11 à Paris (+01:00), le 10 en UTC."""
        self.conn.execute("SET ROLE pmzilla_flow")
        self.conn.execute("UPDATE flow.issues SET resolved_at = %s, resolution = 'Done' WHERE key = 'PROJ-7'",
                          (dt.datetime(2026, 2, 10, 23, 30, tzinfo=UTC),))
        self.conn.execute("RESET ROLE")
        self.conn.commit()
        self.assertEqual(self.elements()["PROJ-7"]["resolu"], dt.date(2026, 2, 11))
        en_utc = {e["cle"]: e for e in flow_store.lire_donnees_cycles({"export_fuseau": "UTC"}, [])}
        self.assertEqual(en_utc["PROJ-7"]["resolu"], dt.date(2026, 2, 10))

    def test_la_lecture_est_en_lecture_seule(self):
        """Le rôle de lecture seule ne peut pas écrire les périodes (privilège SELECT seulement)."""
        conn = flow_store.ouvrir()
        try:
            with self.assertRaises(Exception):
                conn.execute("INSERT INTO flow.issue_label_periods (issue_key, label, added_at) VALUES ('PROJ-1', 'x', now())")
        finally:
            conn.close()


class DeBoutEnBout(base.AvecBase, sc.AvecDossier):
    """`flux_jira.py cycles` lancé comme l'utilisateur le fait, sur la base jetable : mêmes chiffres que le calcul en mémoire."""

    REGLAGES = """export_timezone: Europe/Paris
cycles:
  2026-C1:
    fix_version: ver-alpha
    start: 2026-01-05
    end: 2026-02-27
patches:
  2026-Q1: [patch-alpha]
declared_labels:
  up_merge:
    prefix: UM-
    labels: [UM-legal, UM-hotfix]
"""

    def test_rapport_des_cycles_de_bout_en_bout(self):
        liste = [jeu.issue(f"PROJ-{i}", etat="Closed", categorie="Done", cree=jeu.moment(400), resolu=dt.datetime(2026, 2, 10, 12, 0),
                           motif="Done", equipes=["Alpha"]) for i in range(1, 8)]
        self.inserer(liste, [], [])
        ajout = dt.datetime(2026, 1, 6, tzinfo=UTC)
        ecrire_periodes(self.conn,
                        versions=[(f"PROJ-{i}", "ver-alpha", ajout, None) for i in range(1, 6)]
                        + [("PROJ-6", "patch-alpha", ajout, None)],
                        etiquettes=[("PROJ-6", "UM-legal", ajout, None), ("PROJ-7", "UM-hotfix", ajout, None)])
        ws = self.dossier()
        (ws / "Flux-Lab").mkdir()
        (ws / "Flux-Lab" / "flux.yaml").write_text(self.REGLAGES, encoding="utf-8")
        r = sc.lancer(sc.FLUX, ws, "cycles", "--name", "essai", "--today", "2026-05-04", env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rapport = json.loads((ws / "Flux-Lab" / "rapports" / "cycles-essai-2026-05-04.json").read_text(encoding="utf-8"))
        c1 = rapport["cycles"][0]
        self.assertEqual((c1["livres"], c1["up_merge"]["resolus"], c1["up_merge"]["par_patch"], c1["up_merge"]["sans_patch"]),
                         (5, 2, {"2026-Q1": 1}, 1))
        self.assertNotIn("PROJ-", r.stdout + r.stderr)


class SansConnexion(sc.AvecDossier):
    def test_un_fichier_csv_est_refuse_sans_connexion(self):
        export = self.dossier() / "export.csv"
        jeu.ecrire_csv(export, jeu.tickets())
        r = sc.lancer(sc.FLUX, self.dossier(), "cycles", str(export), "--language", "en", env={"PMZILLA_LAB_DB_PORT": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("no CSV file may be given", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
