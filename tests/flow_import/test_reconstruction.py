"""Reconstruction depuis la couche brute : flow_import.py --rebuild, --apply, --seed (change jira-data-architecture, D5, D11 ; spec
jira-flow-raw-layer « Rebuild is a comparison by default », « Rebuild applied in one transaction », « Rebuild refusals and usage
errors », « Seeding from the live tables », « Raw layer is append-only »). Tâche 4.6 (rouge d'abord), partie sans base.

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_import -v

Sans base : une fausse connexion répond aux requêtes de lecture avec des lignes inventées (tickets PROJ-n, équipes Alpha et Beta) et
note les écritures. Les scénarios sur la base jetable sont dans test_reconstruction_base.py (sautés sans elle).
"""
import contextlib
import datetime as dt
import io
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import db
import flow_import
import flow_raw

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
T1 = dt.datetime(2026, 10, 1, 10, 0, tzinfo=UTC)


def instantane(cle="PROJ-1", **valeurs):
    base = {"issue_key": cle, "project": "PROJ", "type": "Story", "status": "Open", "status_category": "To Do",
            "created_at": T0, "resolved_at": None, "resolution": None, "status_category_changed_at": None,
            "story_points": None, "updated_at": T1, "parent_key": None,
            "teams": [{"name": "Alpha", "jira_team_id": "1"}, {"name": "Beta", "jira_team_id": None}], "links": None}
    base.update(valeurs)
    return base


def vivant(cle="PROJ-1", **valeurs):
    base = {"key": cle, "project": "PROJ", "type": "Story", "status": "Open", "status_category": "To Do", "created_at": T0,
            "resolved_at": None, "resolution": None, "status_category_changed_at": None, "story_points": None,
            "updated_at": T1, "parent_key": None, "team": "Alpha", "teams": ["Alpha", "Beta"], "links": set()}
    base.update(valeurs)
    return base


class Champs(unittest.TestCase):
    def test_aucune_difference(self):
        self.assertEqual(flow_raw.champs_differents(instantane(), vivant()), [])

    def test_un_champ_a_la_fois(self):
        cas = [("status", {"status": "Done"}), ("status category", {"status_category": "Done"}), ("type", {"type": "Bug"}),
               ("resolution", {"resolution": "Done"}), ("parent", {"parent_key": "PROJ-9"}),
               ("dates", {"resolved_at": T1}), ("dates", {"updated_at": T0}), ("dates", {"created_at": T1}),
               ("dates", {"status_category_changed_at": T1}), ("story points", {"story_points": Decimal("3")})]
        for nom, change in cas:
            self.assertEqual(flow_raw.champs_differents(instantane(), vivant(**change)), [nom], change)

    def test_points_egaux_sous_deux_ecritures(self):
        self.assertEqual(flow_raw.champs_differents(instantane(story_points=Decimal("3.0")), vivant(story_points=Decimal("3"))), [])
        self.assertEqual(flow_raw.champs_differents(instantane(story_points=3), vivant(story_points=Decimal("3"))), [])

    def test_equipes_ordre_premiere_equipe(self):
        self.assertEqual(flow_raw.champs_differents(instantane(), vivant(teams=["Beta", "Alpha"], team="Beta")), ["team", "teams"])
        self.assertEqual(flow_raw.champs_differents(instantane(), vivant(teams=["Alpha"])), ["teams"])
        self.assertEqual(flow_raw.champs_differents(instantane(teams=[]), vivant(teams=[], team=None)), [])

    def test_un_nom_repete_compte_une_fois(self):
        doublon = [{"name": "Alpha", "jira_team_id": "1"}, {"name": "Alpha", "jira_team_id": "2"}]
        self.assertEqual(flow_raw.champs_differents(instantane(teams=doublon), vivant(teams=["Alpha"])), [])

    def test_liens_compares_seulement_quand_ils_sont_suivis(self):
        suivis = [{"target": "PROJ-2", "type": "Blocks", "direction": "outward"}]
        self.assertEqual(flow_raw.champs_differents(instantane(links=suivis), vivant(links={("PROJ-2", "Blocks", "outward")})), [])
        self.assertEqual(flow_raw.champs_differents(instantane(links=suivis), vivant(links=set())), ["links"])
        self.assertEqual(flow_raw.champs_differents(instantane(links=None), vivant(links=None)), [])

    def test_ligne_vivante_absente(self):
        self.assertEqual(flow_raw.champs_differents(instantane(), None), ["ticket"])


class FausseConnexion:
    """Répond aux lectures de flow_raw avec des lignes données ; note les écritures. Aucune base."""

    rowcount = 1               # « lignes touchées » de la dernière écriture : la dérivation compte les équipes créées

    def __init__(self, instantanes=(), vivants=(), liens_instantanes=None, equipes_connues=("Alpha", "Beta")):
        self.instantanes = list(instantanes)
        self.vivants = list(vivants)
        self.liens_instantanes = liens_instantanes if liens_instantanes is not None else {}
        self.equipes_connues = list(equipes_connues)
        self.ecritures: list[tuple[str, tuple]] = []
        self.valide = self.annule = 0
        self.ferme = False
        self.echec_ecriture: Exception | None = None
        self.derniere: list = []

    def cursor(self):
        return self

    def execute(self, sql, params=None):
        if sql == flow_raw.SQL_DERNIERS_COMPLETS:
            colonnes = ("issue_key",) + flow_raw.COLONNES_COMPARAISON + ("teams",)
            self.derniere = [tuple(i[c] for c in colonnes) for i in self.instantanes]
        elif sql == flow_raw.SQL_DERNIERS_LIENS:
            self.derniere = list(self.liens_instantanes.items())
        elif sql == flow_raw.SQL_VIVANT:
            self.derniere = [tuple(v[c] for c in ("key",) + flow_raw.COLONNES_COMPARAISON + ("team",)) for v in self.vivants]
        elif sql == flow_raw.SQL_EQUIPES_VIVANTES:
            self.derniere = [(v["key"], nom) for v in self.vivants for nom in v["teams"]]
        elif sql == flow_raw.SQL_LIENS_VIVANTS:
            self.derniere = [(v["key"], *lien) for v in self.vivants for lien in sorted(v["links"], key=str)]
        elif sql.startswith("SELECT name, id FROM flow.teams"):
            self.derniere = [(nom, i) for i, nom in enumerate(self.equipes_connues, 1)]
        elif sql.startswith("SELECT DISTINCT issue_key FROM flow.raw_issue_snapshots"):
            self.derniere = [(i["issue_key"],) for i in self.instantanes]
        elif sql.startswith("SET ROLE"):
            self.derniere = []
        else:
            if self.echec_ecriture is not None:
                raise self.echec_ecriture
            self.ecritures.append((sql, params))
            self.derniere = [(len(self.ecritures),)]
        return self

    def executemany(self, sql, lots):
        self.ecritures.append((sql, tuple(lots)))

    def fetchall(self):
        return self.derniere

    def fetchone(self):
        return self.derniere[0]

    def commit(self):
        self.valide += 1

    def rollback(self):
        self.annule += 1

    def close(self):
        self.ferme = True


def lancer(*argv, connexion=None):
    """flow_import.main avec une fausse connexion : (code, stdout, stderr)."""
    sortie, erreur = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur), \
            mock.patch.object(db, "connect", side_effect=(lambda *a, **k: connexion) if connexion is not None
                              else AssertionError("aucune connexion attendue")):
        try:
            flow_import.main(list(argv))
        except SystemExit as arret:
            code = arret.code if isinstance(arret.code, int) else (0 if arret.code is None else 1)
    return code, sortie.getvalue(), erreur.getvalue()


class Reconstruction(unittest.TestCase):
    def test_a_blanc_sans_difference(self):
        connexion = FausseConnexion([instantane("PROJ-1"), instantane("PROJ-2")], [vivant("PROJ-1"), vivant("PROJ-2")])
        code, sortie, erreur = lancer("--rebuild", connexion=connexion)
        self.assertEqual(code, 0, erreur)
        lignes = sortie.splitlines()
        self.assertEqual(lignes, ["reconstruction : 2 tickets comparés, 0 changeraient", "reconstruction à blanc : rien n'est écrit"])
        self.assertEqual(connexion.ecritures, [])
        self.assertTrue(connexion.ferme)

    def test_a_blanc_compte_une_difference_par_champ_sans_valeur_et_ne_change_rien(self):
        connexion = FausseConnexion([instantane("PROJ-1"), instantane("PROJ-2")], [vivant("PROJ-1", status="Done"), vivant("PROJ-2")])
        code, sortie, erreur = lancer("--rebuild", "--language", "en", connexion=connexion)
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.splitlines(), ["rebuild: 2 tickets compared, 1 would change", "rebuild: status differs: 1",
                                               "rebuild dry run: nothing written"])
        self.assertEqual(connexion.ecritures, [])
        for interdit in ("PROJ-", "Alpha", "Beta", "Done", "Open"):
            self.assertNotIn(interdit, sortie)

    def test_application_en_une_transaction(self):
        connexion = FausseConnexion([instantane("PROJ-1"), instantane("PROJ-2")], [vivant("PROJ-1", status="Done"), vivant("PROJ-2")])
        code, sortie, erreur = lancer("--rebuild", "--apply", "--language", "en", connexion=connexion)
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.splitlines()[-1], "rebuild done: 1 tickets changed")
        self.assertNotIn("dry run", sortie)
        self.assertTrue(any(s.startswith("INSERT INTO flow.issues") for s, _ in connexion.ecritures))
        self.assertEqual(sum(1 for s, _ in connexion.ecritures if s.startswith("INSERT INTO flow.issues")), 1)
        self.assertEqual(connexion.valide, 1)
        self.assertEqual(connexion.annule, 0)
        for s, _ in connexion.ecritures:                       # ni équipe supprimée, ni transition, ni période, ni couche brute
            self.assertNotRegex(s, r"(?i)DELETE FROM flow\.(teams|transitions|issue_label_periods|issue_version_periods|raw_)")
            self.assertNotRegex(s, r"(?i)(UPDATE|INSERT INTO|DELETE FROM) flow\.(transitions|raw_|issue_label|issue_version)")
            self.assertNotIn("out_of_export_at", s)
            self.assertNotIn("has_history", s)

    def test_equipes_manquantes_creees_jamais_supprimees(self):
        neuf = instantane("PROJ-1", teams=[{"name": "Gamma", "jira_team_id": None}])
        connexion = FausseConnexion([neuf], [vivant("PROJ-1")])
        lancer("--rebuild", "--apply", connexion=connexion)
        self.assertTrue(any(s.startswith("INSERT INTO flow.teams") for s, _ in connexion.ecritures))
        self.assertFalse(any("DELETE FROM flow.teams" in s for s, _ in connexion.ecritures))

    def test_erreur_pendant_l_ecriture_annule_tout_et_n_affiche_que_le_type(self):
        connexion = FausseConnexion([instantane()], [vivant(status="Done")])
        connexion.echec_ecriture = RuntimeError("ZZSECRET-PROJ-1")
        code, sortie, erreur = lancer("--rebuild", "--apply", connexion=connexion)
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", erreur)
        self.assertNotIn("ZZSECRET", sortie + erreur)
        self.assertGreaterEqual(connexion.annule, 1)
        self.assertEqual(connexion.valide, 0)

    def test_couche_brute_vide_refusee(self):
        for langue, phrase in (("fr", "couche brute vide : reconstruction refusée"), ("en", "raw layer empty: rebuild refused")):
            connexion = FausseConnexion([], [vivant()])
            code, sortie, erreur = lancer("--rebuild", "--language", langue, connexion=connexion)
            self.assertEqual(code, 1)
            self.assertIn(phrase, sortie + erreur)
            self.assertEqual(connexion.ecritures, [])

    def test_tickets_sans_instantane_refuses_avec_leur_nombre(self):
        connexion = FausseConnexion([instantane("PROJ-1")], [vivant("PROJ-1"), vivant("PROJ-2"), vivant("PROJ-3")])
        code, sortie, erreur = lancer("--rebuild", "--apply", connexion=connexion)
        self.assertEqual(code, 1)
        self.assertIn("tickets sans instantané : 2, reconstruction refusée", sortie + erreur)
        self.assertEqual(connexion.ecritures, [])
        code, sortie, erreur = lancer("--rebuild", "--language", "en", connexion=connexion)
        self.assertIn("tickets without snapshot: 2, rebuild refused", sortie + erreur)

    def test_marque_de_sortie_de_l_export_non_reconstruite(self):
        """La ligne vivante n'a pas de colonne de sortie dans la comparaison : une marque ne crée aucune différence."""
        connexion = FausseConnexion([instantane()], [vivant()])
        code, sortie, _ = lancer("--rebuild", "--apply", connexion=connexion)
        self.assertEqual(code, 0)
        self.assertEqual(connexion.ecritures, [])

    def test_liens_non_suivis_gardent_les_derniers_liens(self):
        connexion = FausseConnexion([instantane(links=None)], [vivant(links={("PROJ-2", "Blocks", "outward")})])
        code, sortie, _ = lancer("--rebuild", "--language", "en", connexion=connexion)
        self.assertIn("0 would change", sortie)

    def test_ticket_absent_des_tables_vivantes_est_cree(self):
        connexion = FausseConnexion([instantane("PROJ-1")], [])
        code, sortie, _ = lancer("--rebuild", "--apply", "--language", "en", connexion=connexion)
        self.assertEqual(code, 0)
        self.assertIn("rebuild: ticket differs: 1", sortie)
        self.assertTrue(any(s.startswith("INSERT INTO flow.issues") for s, _ in connexion.ecritures))


class Amorcage(unittest.TestCase):
    def test_amorcage_puis_reconstruction_a_blanc(self):
        connexion = FausseConnexion([], [vivant("PROJ-1"), vivant("PROJ-2")])
        with mock.patch.object(flow_raw, "reconstruire", return_value={"compares": 2, "changeraient": 0, "champs": {}, "modifies": 0}):
            code, sortie, erreur = lancer("--rebuild", "--seed", "--language", "en", connexion=connexion)
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.splitlines()[0], "seed: 2 snapshots built from the live tables")
        passage = [p for s, p in connexion.ecritures if s.startswith("INSERT INTO flow.raw_runs")]
        self.assertEqual(len(passage), 1)
        self.assertIn("'seed'", [s for s, _ in connexion.ecritures if s.startswith("INSERT INTO flow.raw_runs")][0])

    def test_instantane_d_amorcage_sans_identifiant_d_equipe_et_marque_amorce(self):
        connexion = FausseConnexion([], [vivant("PROJ-1", teams=["Alpha", "Beta"])])
        self.assertEqual(flow_raw.amorcer(connexion), 1)
        lots = [p for s, p in connexion.ecritures if s.startswith("INSERT INTO flow.raw_issue_snapshots")]
        self.assertEqual(len(lots), 1)
        parametres = lots[0][0]
        self.assertTrue(parametres[-1])                                  # seeded
        self.assertEqual([e["jira_team_id"] for e in parametres[13].obj], [None, None])
        self.assertEqual([e["name"] for e in parametres[13].obj], ["Alpha", "Beta"])

    def test_un_ticket_deja_dote_d_un_instantane_n_est_pas_double(self):
        connexion = FausseConnexion([instantane("PROJ-1")], [vivant("PROJ-1"), vivant("PROJ-2")])
        self.assertEqual(flow_raw.amorcer(connexion), 1)
        cles = [p[0][0] for s, p in connexion.ecritures if s.startswith("INSERT INTO flow.raw_issue_snapshots")]
        self.assertEqual(cles, ["PROJ-2"])

    def test_rien_a_amorcer_n_ecrit_aucun_passage(self):
        connexion = FausseConnexion([instantane("PROJ-1")], [vivant("PROJ-1")])
        self.assertEqual(flow_raw.amorcer(connexion), 0)
        self.assertEqual(connexion.ecritures, [])


class UsageEtRefus(unittest.TestCase):
    """Codes 2 avant toute connexion, avec les phrases de D11 dans les deux langues."""

    def verifier(self, argv, fr, en):
        for langue, phrase in (("fr", fr), ("en", en)):
            code, sortie, erreur = lancer(*argv, "--language", langue)            # lancer() refuse toute connexion
            self.assertEqual(code, 2, (argv, sortie, erreur))
            self.assertIn(phrase, sortie + erreur)

    def test_fichier_d_export_avec_rebuild(self):
        self.verifier(["--rebuild", "export.csv"], "les fichiers d'export ne sont plus lus : l'import part de la couche brute",
                      "export files are no longer read: the import derives from the raw layer")

    def test_apply_ou_seed_sans_rebuild(self):
        for option in ("--apply", "--seed"):
            self.verifier([option], "--apply et --seed demandent --rebuild", "--apply and --seed need --rebuild")

    def test_marque_absent_ou_essai_a_blanc_avec_rebuild(self):
        for option in ("--mark-absent", "--dry-run"):
            self.verifier(["--rebuild", option], "--mark-absent et --dry-run ne sont pas acceptés avec --rebuild",
                          "--mark-absent and --dry-run are not accepted with --rebuild")

    def test_historique_retire(self):
        for argv in (["--history"], ["--rebuild", "--history"], ["--history", "cache.json"]):
            self.verifier(argv, "--history est retirée : la collecte de l'historique écrit les transitions",
                          "--history is retired: the history collection writes the transitions")

    def test_apply_avec_dry_run_n_applique_rien(self):
        """`--rebuild --apply --dry-run` appliquait la reconstruction sans le dire : refus d'usage, aucune connexion (lancer() les refuse)."""
        self.verifier(["--rebuild", "--apply", "--dry-run"], "--mark-absent et --dry-run ne sont pas acceptés avec --rebuild",
                      "--mark-absent and --dry-run are not accepted with --rebuild")


if __name__ == "__main__":
    unittest.main()
