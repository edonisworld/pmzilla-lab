"""Dérivation des tables courantes depuis la couche brute : flow_import.py sans fichier (change database-only, D4, D6 ; spec jira-flow-import
« Import derives from the raw layer without files », « Out-of-export mark », « Mark only with a complete export set », « Mark refused on an
empty export or too many absent tickets »). Tâche 4.4, partie sans base.

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_import -v

Une fausse connexion répond aux requêtes de flow_raw.deriver avec des lignes inventées (tickets PROJ-n, équipes Alpha et Beta) et note les
écritures. Les scénarios sur la base jetable sont dans test_derivation_base.py (sautés sans elle).
"""
import contextlib
import datetime as dt
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
import flow_import  # noqa: E402
import flow_raw  # noqa: E402
from test_reconstruction import FausseConnexion, instantane, vivant  # noqa: E402

UTC = dt.timezone.utc
MAINTENANT = dt.datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


class FausseConnexionDerivation(FausseConnexion):
    """Ajoute à FausseConnexion le dernier passage d'export, ses visites et les comptes des marques."""

    def __init__(self, *args, passage=None, visites=(), revenus=0, candidats=0, total=0, marques=0, disparus_revus=0, **kw):
        super().__init__(*args, **kw)
        self.passage = passage                    # (identifiant, all_queries) ou None : aucun passage d'export
        self.visites = list(visites)
        self.revenus, self.candidats, self.total, self.marques = revenus, candidats, total, marques
        self.disparus_revus = disparus_revus      # tickets marqués disparus que le dernier passage revoit (D15 complété)

    def execute(self, sql, params=None):
        if sql.startswith("SELECT id, all_queries FROM flow.raw_runs"):
            self.derniere = [self.passage] if self.passage else []
        elif sql.startswith("SELECT issue_key FROM flow.raw_run_sightings"):
            self.derniere = [(cle,) for cle in self.visites]
        elif sql.startswith("UPDATE flow.issues SET out_of_export_at = NULL"):
            self.rowcount = self.revenus
            self.ecritures.append((sql, params))
        elif sql.startswith("UPDATE flow.issues SET history_not_found = 0, history_gone_at = NULL"):
            self.rowcount = self.disparus_revus
            self.ecritures.append((sql, params))
        elif sql.startswith("SELECT count(*) FROM flow.issues WHERE out_of_export_at IS NULL AND NOT"):
            self.derniere = [(self.candidats,)]
        elif sql.startswith("SELECT count(*) FROM flow.issues WHERE out_of_export_at IS NULL"):
            self.derniere = [(self.total,)]
        elif sql.startswith("UPDATE flow.issues SET out_of_export_at = %s"):
            self.rowcount = self.marques
            self.ecritures.append((sql, params))
        else:
            return super().execute(sql, params)
        return self

    def fetchone(self):
        return self.derniere[0] if self.derniere else None


def lancer(*argv, connexion=None):
    """flow_import.main avec une fausse connexion et des réglages inventés : (code, stdout, stderr)."""
    sortie, erreur = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur), \
            mock.patch.object(db, "connect", side_effect=(lambda *a, **k: connexion) if connexion is not None
                              else AssertionError("aucune connexion attendue")), \
            mock.patch.object(flow_import, "lire_reglages", return_value={}):
        try:
            flow_import.main(list(argv))
        except SystemExit as arret:
            code = arret.code if isinstance(arret.code, int) else (0 if arret.code is None else 1)
    return code, sortie.getvalue(), erreur.getvalue()


class Derivation(unittest.TestCase):
    def test_un_nouveau_passage_est_applique_puis_un_second_import_ne_trouve_rien(self):
        connexion = FausseConnexionDerivation([instantane("PROJ-1"), instantane("PROJ-2")], [vivant("PROJ-1", status="Done")],
                                              passage=(1, True), visites=["PROJ-1", "PROJ-2"])
        code, sortie, erreur = lancer("--language", "en", connexion=connexion)
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.splitlines(), ["Tickets read: 2; inserted: 1; updated: 1; unchanged: 0.",
                                               "Teams created: 0; links added: 0; links removed: 0.",
                                               "tickets past retention, skipped: 0",
                                               "Tickets out of the export: 0 marked, 0 back",
                                               "tickets marked gone, sighted again by the export: 0"])
        self.assertEqual(connexion.valide, 1)
        propre = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1")], passage=(1, True), visites=["PROJ-1"])
        code, sortie, erreur = lancer("--language", "en", connexion=propre)
        self.assertEqual((code, sortie.splitlines()[0]), (0, "raw layer: no new run to apply"))
        self.assertEqual([s for s, _ in propre.ecritures if not s.startswith(("UPDATE flow.issues SET out_of_export_at = NULL",
                                                                              "UPDATE flow.issues SET history_not_found = 0"))], [])
        code, sortie, _ = lancer(connexion=FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1")], passage=(1, True),
                                                                        visites=["PROJ-1"]))
        self.assertEqual(sortie.splitlines()[0], "couche brute : aucun nouveau passage à appliquer")

    def test_couche_brute_vide_rien_a_appliquer(self):
        code, sortie, erreur = lancer("--language", "en", connexion=FausseConnexionDerivation())
        self.assertEqual((code, sortie.splitlines()[0]), (0, "raw layer: no new run to apply"))
        self.assertIn("tickets marked gone, sighted again by the export: 0", sortie)         # la phrase est écrite à chaque passage, 0 compris

    def test_ticket_disparu_revu_par_l_export_perd_sa_marque_avec_ou_sans_l_option(self):
        for options in ((), ("--mark-absent",)):
            connexion = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1")], passage=(1, True), visites=["PROJ-1"],
                                                  disparus_revus=1, candidats=0, total=5)
            code, sortie, erreur = lancer(*options, "--language", "en", connexion=connexion)
            self.assertEqual(code, 0, erreur)
            self.assertIn("tickets marked gone, sighted again by the export: 1", sortie)
            self.assertNotIn("no new run", sortie)                               # une marque effacée est un changement
            remises = [(s, p) for s, p in connexion.ecritures if s.startswith("UPDATE flow.issues SET history_not_found = 0")]
            self.assertEqual(len(remises), 1)
            self.assertIn("history_gone_at IS NOT NULL", remises[0][0])         # seuls les tickets marqués disparus : le compteur des autres reste
            self.assertEqual(remises[0][1], (["PROJ-1"],))
            self.assertEqual(connexion.valide, 1)

    def test_phrase_des_disparus_revus_en_francais_et_en_essai_a_blanc(self):
        connexion = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1")], passage=(1, True), visites=["PROJ-1"],
                                              disparus_revus=1)
        code, sortie, _ = lancer("--dry-run", "--language", "fr", connexion=connexion)
        self.assertEqual(code, 0)
        self.assertIn("tickets marqués disparus, revus par l'export : 1", sortie)
        self.assertEqual((connexion.valide, connexion.annule >= 1), (0, True))             # essai à blanc : annulé, même compte

    def test_aucun_ticket_disparu_revu_sans_passage_d_export(self):
        connexion = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1", status="Done")], passage=None)
        code, sortie, _ = lancer("--language", "en", connexion=connexion)
        self.assertEqual(code, 0)
        self.assertIn("tickets marked gone, sighted again by the export: 0", sortie)
        self.assertFalse(any(s.startswith("UPDATE flow.issues SET history_not_found") for s, _ in connexion.ecritures))

    def test_essai_a_blanc_annule_et_ne_dit_pas_rien_quand_il_y_a_une_difference(self):
        connexion = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1", status="Done")], passage=(1, True),
                                              visites=["PROJ-1"])
        code, sortie, erreur = lancer("--dry-run", "--language", "en", connexion=connexion)
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.splitlines()[0], "Dry run (--dry-run): counts computed in the database, nothing is written.")
        self.assertIn("updated: 1", sortie)
        self.assertEqual((connexion.valide, connexion.annule >= 1), (0, True))

    def test_ticket_vu_perd_sa_marque_meme_sans_l_option(self):
        connexion = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1")], passage=(1, True), visites=["PROJ-1"], revenus=1)
        code, sortie, _ = lancer("--language", "en", connexion=connexion)
        self.assertEqual(code, 0)
        self.assertIn("Tickets out of the export: 0 marked, 1 back", sortie)
        self.assertFalse(any(s.startswith("UPDATE flow.issues SET out_of_export_at = %s") for s, _ in connexion.ecritures))

    def test_avec_l_option_un_ticket_absent_du_jeu_complet_est_marque(self):
        connexion = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1")], passage=(1, True), visites=["PROJ-1"],
                                              candidats=1, total=10, marques=1)
        code, sortie, _ = lancer("--mark-absent", "--language", "en", connexion=connexion)
        self.assertEqual(code, 0)
        self.assertIn("Tickets out of the export: 1 marked, 0 back", sortie)
        self.assertEqual(connexion.valide, 1)

    def test_jeu_incomplet_refuse_avant_toute_ecriture(self):
        for langue, phrase in (("fr", "jeu d'exports incomplet : --mark-absent refusé"), ("en", "incomplete export set: --mark-absent refused")):
            connexion = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1")], passage=(1, False), visites=["PROJ-1"])
            code, sortie, erreur = lancer("--mark-absent", "--language", langue, connexion=connexion)
            self.assertEqual(code, 1)
            self.assertIn(phrase, sortie + erreur)
            self.assertEqual(connexion.valide, 0)
            self.assertGreaterEqual(connexion.annule, 1)

    def test_dernier_passage_par_requete_refuse_et_demande_un_passage_complet(self):
        """Confirmé par l'auteur (design D4, lecture sans état) : si le dernier passage enregistré est un passage `--query`, l'option est
        refusée (code 1, rien d'écrit) et le message ajoute qu'il faut lancer d'abord un passage complet."""
        for langue, phrase, suite in (
                ("fr", "jeu d'exports incomplet : --mark-absent refusé",
                 "dernier passage d'export limité à une requête (--query) : lancez d'abord un passage complet de l'export, sans --query"),
                ("en", "incomplete export set: --mark-absent refused",
                 "last export run limited to one query (--query): run a complete export first, without --query")):
            connexion = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1")], passage=(2, False), visites=["PROJ-1"])
            code, sortie, erreur = lancer("--mark-absent", "--language", langue, connexion=connexion)
            self.assertEqual(code, 1)
            texte = sortie + erreur
            self.assertIn(phrase, texte)
            self.assertIn(suite, texte)
            self.assertLess(texte.index(phrase), texte.index(suite))          # la phrase du passage partiel vient après
            self.assertNotIn("PROJ-1", sortie + erreur)
            self.assertEqual(connexion.valide, 0)
            self.assertFalse([e for e in connexion.ecritures if "out_of_export_at = %s" in e[0]])

    def test_aucun_passage_avec_l_option_refuse_comme_un_jeu_incomplet(self):
        code, sortie, erreur = lancer("--mark-absent", "--language", "en", connexion=FausseConnexionDerivation())
        self.assertEqual(code, 1)
        self.assertIn("incomplete export set: --mark-absent refused", sortie + erreur)
        self.assertNotIn("--query", sortie + erreur)                # sans aucun passage d'export : la phrase du jeu incomplet seule

    def test_export_vide_refuse(self):
        for langue, phrase in (("fr", "export vide : --mark-absent refusé"), ("en", "empty export: --mark-absent refused")):
            connexion = FausseConnexionDerivation([], [], passage=(1, True), visites=[])
            code, sortie, erreur = lancer("--mark-absent", "--language", langue, connexion=connexion)
            self.assertEqual(code, 1)
            self.assertIn(phrase, sortie + erreur)

    def test_trop_d_absents_refuse_sans_rien_marquer(self):
        connexion = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1")], passage=(1, True), visites=["PROJ-1"],
                                              candidats=2, total=4)
        code, sortie, erreur = lancer("--mark-absent", "--max-absent-percent", "20", "--language", "en", connexion=connexion)
        self.assertEqual(code, 1)
        self.assertIn("too many tickets absent from the last run (more than 20% of stored tickets)", sortie + erreur)
        self.assertIn("--max-absent-percent", sortie + erreur)
        self.assertFalse(any(s.startswith("UPDATE flow.issues SET out_of_export_at = %s") for s, _ in connexion.ecritures))
        code, sortie, _ = lancer("--mark-absent", "--max-absent-percent", "60", connexion=FausseConnexionDerivation(
            [instantane("PROJ-1")], [vivant("PROJ-1")], passage=(1, True), visites=["PROJ-1"], candidats=2, total=4, marques=2))
        self.assertEqual(code, 0)

    def test_pourcentage_invalide_refuse_avant_toute_connexion(self):
        code, _, erreur = lancer("--max-absent-percent", "120")                 # lancer() refuse toute connexion
        self.assertEqual(code, 2)
        self.assertIn("--max-absent-percent", erreur)

    def test_ticket_resolu_au_dela_de_la_conservation_ignore_et_compte(self):
        ancien = instantane("PROJ-2", resolved_at=dt.datetime(2020, 1, 1, tzinfo=UTC))
        connexion = FausseConnexionDerivation([instantane("PROJ-1"), ancien], [vivant("PROJ-1", status="Done")], passage=(1, True),
                                              visites=["PROJ-1"])
        with mock.patch.object(flow_import.cfg, "retention_days", return_value=365):
            code, sortie, erreur = lancer("--language", "en", connexion=connexion)
        self.assertEqual(code, 0, erreur)
        self.assertIn("Tickets read: 1;", sortie)
        self.assertIn("tickets past retention, skipped: 1", sortie)

    def test_fichier_d_export_refuse_avant_toute_connexion(self):
        for langue, phrase in (("fr", "les fichiers d'export ne sont plus lus : l'import part de la couche brute"),
                               ("en", "export files are no longer read: the import derives from the raw layer")):
            code, sortie, erreur = lancer("export.csv", "autre.csv", "--language", langue)          # lancer() refuse toute connexion
            self.assertEqual(code, 2, (sortie, erreur))
            self.assertIn(phrase, sortie + erreur)
            self.assertNotIn("export.csv", sortie + erreur)

    def test_option_historique_retiree_avant_toute_connexion(self):
        for langue, phrase in (("fr", "--history est retirée : la collecte de l'historique écrit les transitions"),
                               ("en", "--history is retired: the history collection writes the transitions")):
            code, sortie, erreur = lancer("--history", "--language", langue)
            self.assertEqual(code, 2, (sortie, erreur))
            self.assertIn(phrase, sortie + erreur)

    def test_erreur_de_base_n_affiche_que_le_type(self):
        connexion = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1", status="Done")], passage=(1, True), visites=["PROJ-1"])
        connexion.echec_ecriture = RuntimeError("ZZSECRET-PROJ-1")
        code, sortie, erreur = lancer(connexion=connexion)
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", erreur)
        self.assertNotIn("ZZSECRET", sortie + erreur)
        self.assertEqual(connexion.valide, 0)
        self.assertTrue(connexion.ferme)

    def test_la_connexion_se_fait_sous_le_role_d_import(self):
        appels = []

        def connecter(*a, **k):
            appels.append(k)
            return FausseConnexionDerivation()
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(db, "connect", side_effect=connecter), \
                mock.patch.object(flow_import, "lire_reglages", return_value={}), self.assertRaises(SystemExit) as arret:
            flow_import.main([])
        self.assertEqual(arret.exception.code, 0)
        self.assertEqual(appels, [{"role": "pmzilla_flow"}])           # son propre mot de passe, jamais celui du propriétaire

    def test_les_sorties_ne_portent_ni_cle_ni_equipe_ni_valeur(self):
        connexion = FausseConnexionDerivation([instantane("PROJ-1")], [vivant("PROJ-1", status="Done")], passage=(1, True),
                                              visites=["PROJ-1"], revenus=1, candidats=1, total=5, marques=1)
        code, sortie, erreur = lancer("--mark-absent", connexion=connexion)
        for interdit in ("PROJ-", "Alpha", "Beta", "Done", "Open"):
            self.assertNotIn(interdit, sortie + erreur)

    def test_part_absents_depassee_est_pure(self):
        self.assertTrue(flow_raw.part_absents_depassee(2, 4, 20))
        self.assertFalse(flow_raw.part_absents_depassee(1, 5, 20))
        self.assertFalse(flow_raw.part_absents_depassee(0, 0, 20))
        self.assertTrue(flow_raw.part_absents_depassee(1, 10, 0))


if __name__ == "__main__":
    unittest.main()
