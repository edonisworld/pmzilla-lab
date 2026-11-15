"""Contrôle crochet-reference-transaction et import tiers absent (R-20261110-42). Tout se joue dans des dépôts jetables créés par les tests ; le vrai
dépôt et ses crochets ne sont jamais lus (le contrôle lit DOCTOR_CROCHETS_DEPOT)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import Labo, depot_avec_crochet, git  # noqa: E402

import doctor  # noqa: E402
from doctor_messages import CATALOGS  # noqa: E402
from messages import Messages  # noqa: E402

ID = "crochet-reference-transaction"


class Verification(unittest.TestCase):
    def depot(self, **options):
        base = tempfile.TemporaryDirectory(prefix="doctor-crochet.")
        self.addCleanup(base.cleanup)
        return depot_avec_crochet(Path(base.name) / "depot", **options)

    def test_crochet_conforme_ok(self):
        self.assertEqual(doctor.verifier_crochet(self.depot()), "ok")

    def test_sans_crochet_installe(self):
        self.assertEqual(doctor.verifier_crochet(self.depot(conforme=False)), "missing")

    def test_crochet_different_du_lien_attendu(self):
        depot = self.depot(conforme=False)
        crochet = depot / ".git" / "hooks" / "reference-transaction"
        crochet.parent.mkdir(exist_ok=True)
        crochet.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")   # un fichier ordinaire, pas le lien
        crochet.chmod(0o755)
        self.assertEqual(doctor.verifier_crochet(depot), "differs")
        crochet.unlink()
        crochet.symlink_to("../../tools/hooks/pre-commit")   # un lien vers un autre crochet
        self.assertEqual(doctor.verifier_crochet(depot), "differs")

    def test_source_non_executable_ou_absente(self):
        depot = self.depot()
        source = depot / "tools" / "hooks" / "reference-transaction"
        source.chmod(0o644)
        self.assertEqual(doctor.verifier_crochet(depot), "differs")
        source.unlink()
        self.assertEqual(doctor.verifier_crochet(depot), "source_absent")

    def test_hors_d_un_depot_git(self):
        base = tempfile.TemporaryDirectory(prefix="doctor-crochet.")
        self.addCleanup(base.cleanup)
        with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(Path(base.name).parent)}):
            self.assertEqual(doctor.verifier_crochet(Path(base.name)), "no_repo")

    def worktree_lie(self, depot):
        """R-20261110-43 : un worktree lié du dépôt jetable (le cas de production : .git y est un fichier, les crochets sont dans le dépôt commun)."""
        git(depot, "add", "-A", "-f")
        git(depot, "commit", "-q", "-m", "initial")
        lie = depot.parent / "lie"
        git(depot, "worktree", "add", "-q", "--detach", str(lie), "main")
        self.assertTrue((lie / ".git").is_file())
        return lie

    def test_worktree_lie_crochet_du_depot_commun(self):
        self.assertEqual(doctor.verifier_crochet(self.worktree_lie(self.depot())), "ok")

    def test_worktree_lie_sans_crochet_dans_le_depot_commun(self):
        self.assertEqual(doctor.verifier_crochet(self.worktree_lie(self.depot(conforme=False))), "missing")

    def test_import_d_un_module_du_depot_n_est_pas_ignore(self):
        """R-20261110-43 : seul un module tiers absent rend le contrôle « ignoré » ; un module du dépôt en défaut relève l'erreur."""
        def controle_jira(ctx, precedents):
            raise ImportError("boom", name="messages")
        with mock.patch.object(doctor, "CONTROLES", [controle_jira]):
            with self.assertRaises(ImportError):
                doctor.lancer_controles(mock.Mock(env={}))

    def test_import_d_un_module_tiers_est_ignore(self):
        def controle_jira(ctx, precedents):
            raise ImportError("boom", name="yaml")
        with mock.patch.object(doctor, "CONTROLES", [controle_jira]):
            resultats = doctor.lancer_controles(mock.Mock(env={}))
        self.assertEqual([(r.id, r.niveau, r.cle) for r in resultats], [("jira", "skipped", "module_missing")])

    def test_niveaux_et_lignes_avec_la_commande_de_reparation(self):
        ctx = mock.Mock(env={})
        for conforme, niveau, cle in ((True, "ok", "ok"), (False, "problem", "missing")):
            with self.subTest(conforme=conforme):
                ctx.env = {"DOCTOR_CROCHETS_DEPOT": str(self.depot(conforme=conforme))}
                r = doctor.controle_crochet_reference_transaction(ctx, [])
                self.assertEqual((r.id, r.niveau, r.cle), (ID, niveau, cle))
        for langue in ("fr", "en"):
            texte = doctor.raison(doctor.Resultat(ID, "problem", "missing"), Messages(CATALOGS, langue))
            self.assertIn("bash tools/install_hooks.sh", texte)
        self.assertIn(ID, doctor.ORDRE)
        self.assertIn(doctor.controle_crochet_reference_transaction, doctor.CONTROLES)


class DansLeDoctor(Labo):
    def test_ok_dans_l_etat_sain(self):
        niveau, entree, _ = self.niveau(ID)
        self.assertEqual((niveau, entree["reason"]["key"]), ("ok", "ok"))

    def test_probleme_sans_crochet_et_exit_1(self):
        depot = depot_avec_crochet(self.base / "sans-crochet", conforme=False)
        niveau, entree, p = self.niveau(ID, env={"DOCTOR_CROCHETS_DEPOT": str(depot)})
        self.assertEqual((niveau, entree["reason"]["key"], p.returncode), ("problem", "missing", 1))
        self.assertIn("bash tools/install_hooks.sh", self.lancer(env={"DOCTOR_CROCHETS_DEPOT": str(depot)}).stdout)

    def test_sans_pyyaml_le_doctor_rend_un_json_valide_avec_jira_ignore(self):
        with mock.patch.dict(sys.modules, {"yaml": None}):
            p, donnees = self.resultat_json()
            texte = self.lancer().stdout
        self.assertIsNotNone(donnees, p.stdout + p.stderr)
        json.dumps(donnees)
        jira = [c for c in donnees["checks"] if c["id"] == "jira"]
        self.assertEqual([(c["level"], c["reason"]["key"]) for c in jira], [("skipped", "module_missing")])
        self.assertIn("jira : ignoré : module yaml absent", texte)
        self.assertEqual(p.returncode, 0)
        self.assertIn(ID, [c["id"] for c in donnees["checks"]])


if __name__ == "__main__":
    unittest.main()
