"""
Chargement du jeu d'essai de l'évaluation (db-lot2, groupe 12.2) : `cases_store.load_fixture` sur une base jetable.

    bash tests/run_all.sh cases_store

Classes sautées sans PMZILLA_LAB_DB_PASSWORD (base jetable pmzilla_test_<hex>, comme tests/db et test_cases_store.py). Données inventées.
Le vidage `TRUNCATE ... RESTART IDENTITY` est celui de tools/posture_evals.py (reset_cases_database), rejoué ici tel quel.
"""
import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cases_store as cs        # noqa: E402
import test_cases_store as base  # noqa: E402

VIDER = "TRUNCATE cases.cases, cases.experiment_notes, cases.experiments RESTART IDENTITY"

JEU = """\
experiments:
  - author: agile-lead-test
    started_on: 2026-09-01
    status: running
    problem: "Les refinements de l'équipe A durent plus de deux heures [c90]"
    context: {team_type: "type A", team_size: "7", phase: "croissance"}
    chosen_path: "Un format court"
    tested: "Une boîte de temps"
    expected_signal: "Une décision par refinement"
    success_criterion: "Trois refinements de suite sous une heure"
    review_due: 2028-01-31
    notes: [{noted_on: 2026-09-15, note: "premier essai"}]
cases:
  - author: agile-lead-b
    launched_on: 2026-06-01
    reviewed_on: 2026-07-13
    problem: "Les parties prenantes ne viennent plus aux revues [c80]"
    context: {team_type: "type A", team_size: "7", phase: "croissance"}
    chosen_path: "Une revue autour de deux décisions"
    tested: "Deux décisions par revue"
    expected_signal: "Les parties prenantes reviennent"
    success_criterion: "Quatre revues de suite"
    outcome: worked
    confidence: medium
"""


class ChargementAvecBase(base.AvecBase):
    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dossier = Path(self.temp.name)

    def ecrire(self, contenu, nom="jeu.yaml"):
        chemin = self.dossier / nom
        chemin.write_text(contenu, encoding="utf-8")
        return chemin

    def vider(self):
        self.super.execute(VIDER)
        self.super.commit()

    def test_remplit_la_base_jetable(self):
        self.assertEqual(cs.load_fixture(self.super, base.embed_par_marqueur, self.ecrire(JEU)), {"experiments": 1, "cases": 1})
        self.assertEqual(self.lire("SELECT id, status, author, review_due FROM cases.experiments ORDER BY id"),
                         [(1, "running", "agile-lead-test", dt.date(2028, 1, 31)),
                          (2, "closed", "agile-lead-b", dt.date(2026, 7, 13))])
        self.assertEqual(self.lire("SELECT experiment_id, outcome, confidence FROM cases.cases"), [(2, "worked", "medium")])
        self.assertEqual(self.lire("SELECT experiment_id, note FROM cases.experiment_notes"), [(1, "premier essai")])

    def test_les_numeros_repartent_de_1_apres_le_vidage(self):
        jeu = self.ecrire(JEU)
        cs.load_fixture(self.super, base.embed_par_marqueur, jeu)
        self.vider()
        self.assertEqual(self.lire("SELECT count(*) FROM cases.experiments"), [(0,)])
        cs.load_fixture(self.super, base.embed_par_marqueur, jeu)
        self.assertEqual([n for (n,) in self.lire("SELECT id FROM cases.experiments ORDER BY id")], [1, 2])

    def test_fixtures_invalides_refusees_sans_rien_ecrire(self):
        invalides = {
            "cle inconnue": "autre: []\n",
            "statut inconnu": "experiments:\n  - {author: a, started_on: 2027-01-04, status: lancee, problem: 'p [c50]', tested: t, "
                              "context: {phase: x}, expected_signal: s, success_criterion: c}\n",
            "issue absente": "cases:\n  - {author: a, launched_on: 2026-06-01, reviewed_on: 2026-07-13, problem: 'p [c50]', tested: t, "
                             "context: {phase: x}, expected_signal: s, success_criterion: c}\n",
            "bilan avant le début": "experiments:\n  - {author: a, started_on: 2027-01-04, review_due: 2027-01-01, problem: 'p [c50]', "
                                    "tested: t, context: {phase: x}, expected_signal: s, success_criterion: c}\n",
        }
        for nom, contenu in invalides.items():
            with self.subTest(nom), self.assertRaises(cs.CasesError):
                cs.load_fixture(self.super, base.embed_par_marqueur, self.ecrire(contenu, "mauvais.yaml"))
            self.assertEqual(self.lire("SELECT count(*) FROM cases.experiments"), [(0,)])

    def test_la_liste_des_noms_sensibles_n_est_pas_appliquee(self):
        # une liste est configurée et contient un mot du jeu d'essai : le chargeur ne la lit pas (les brouillons, eux, la refuseraient)
        liste = self.ecrire("équipe\n", "noms.txt")
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(liste)}):
            self.assertEqual(cs.load_fixture(self.super, base.embed_par_marqueur, self.ecrire(JEU)), {"experiments": 1, "cases": 1})
            with self.assertRaises(cs.CasesError) as refus:
                cs.start_experiment(self.writer, base.embed_par_marqueur, base.draft(problem="L'équipe A [c50]"), base.ME, base.TODAY)
        self.assertEqual(refus.exception.code, "sensitive_name")


if __name__ == "__main__":
    unittest.main()
