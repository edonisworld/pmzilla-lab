"""
Tests complémentaires du jeu d'essai (tools/posture_evals.py) : openspec/test-gaps.md, section posture-evals.
Avertissement de changement du workspace, voie de la bibliothèque, fichier de cas de commandes, passage « complet ».

    uv run --with pyyaml python -m unittest discover -s tests/posture_evals -v

Mêmes faux que test_posture_evals.py : aucun appel à Claude, aucune base, aucun git réel. Données inventées.
"""
import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

import yaml

import test_posture_evals as socle
import posture_evals as essai

CAS = [{"id": f"c{i}", "question": f"Question {i} ?", "posture": "Delivery"} for i in (1, 2)]


class PassageFictif(socle.Base):
    """main() sur de vrais passages, séances remplacées par une réponse fixe ; `self.statuts` : réponses successives de git status."""

    def setUp(self):
        super().setUp()
        self.statuts: list[str] = []
        self.sessions: list[str] = []

        def faux_git(*arguments, **options):
            if arguments and arguments[0] == "status" and "cwd" not in options:   # état du workspace, pas celui des copies
                return self.statuts.pop(0) if self.statuts else ""
            return ""

        def fausse_seance(question, copie, mcp, model, trace, *a, **k):
            self.sessions.append(question)
            return [socle.assistant(socle.texte("[Posture : Delivery] réponse")), socle.fin("[Posture : Delivery] réponse")]

        for patch in (mock.patch.object(essai, "git", faux_git),
                      mock.patch.object(essai, "make_copy", lambda *a, **k: None),
                      mock.patch.object(essai, "prepare_memory", lambda *a, **k: {}),
                      mock.patch.object(essai, "drop_copy"),
                      mock.patch.object(essai, "run_session", fausse_seance),
                      mock.patch.dict(os.environ)):
            patch.start()
            self.addCleanup(patch.stop)
        os.environ.pop("PMZILLA_LAB_BACKEND", None)
        essai.CASES_FILE.write_text(yaml.safe_dump(CAS, allow_unicode=True), encoding="utf-8")

    def lancer(self, *arguments) -> str:
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["posture_evals.py", "--retries", "0", *arguments]), \
             contextlib.redirect_stdout(sortie):
            essai.main()
        return sortie.getvalue()

    def dernier_resultat(self) -> dict:
        return json.loads(max(essai.DATA.glob("*/resultats.json")).read_text(encoding="utf-8"))


class ChangementDuWorkspace(PassageFictif):
    AVERTISSEMENT = "Attention : le workspace a changé pendant l'essai"

    def test_un_fichier_modifie_pendant_le_passage_declenche_l_avertissement(self):
        self.statuts = ["", " M tools/exemple.py"]          # avant, puis après le passage
        self.assertIn(self.AVERTISSEMENT, self.lancer())

    def test_un_workspace_inchange_ne_declenche_pas_l_avertissement(self):
        self.statuts = [" M tools/exemple.py", " M tools/exemple.py"]
        self.assertNotIn(self.AVERTISSEMENT, self.lancer())

    def test_le_dossier_des_rapports_est_exclu_de_la_comparaison(self):
        self.statuts = ["", "?? _bmad-output/essais/essai-2026-10-10-100000.md"]
        self.assertNotIn(self.AVERTISSEMENT, self.lancer())


class VoieDeLaBibliotheque(PassageFictif):
    def configuration(self, *arguments) -> list[str]:
        self.lancer("--cases", "c1", *arguments)
        config = json.loads(next(essai.DATA.glob("*/mcp.json")).read_text(encoding="utf-8"))
        return config["mcpServers"]["pmzilla-library"]["args"]

    def test_backend_postgres_est_transmis_au_serveur_de_la_bibliotheque(self):
        args = self.configuration("--backend", "postgres")
        self.assertEqual(args[-2:], ["--backend", "postgres"])

    def test_backend_sqlite_est_transmis_au_serveur_de_la_bibliotheque(self):
        args = self.configuration("--backend", "sqlite")
        self.assertEqual(args[-2:], ["--backend", "sqlite"])

    def test_sans_option_le_serveur_garde_sa_voie_par_defaut(self):
        self.assertNotIn("--backend", self.configuration())

    def test_la_bibliotheque_jetable_d_un_cas_est_lue_en_postgres_quelle_que_soit_la_voie(self):
        self.lancer("--cases", "c1", "--backend", "sqlite")
        dossier = next(essai.DATA.glob("*/mcp.json")).parent
        config = essai.mcp_config(dossier, knowledge_dbname="pmzilla_eval_inventee", backend="sqlite", label="bibliotheque-c1")
        serveur = json.loads(config.read_text(encoding="utf-8"))["mcpServers"]["pmzilla-library"]
        self.assertEqual(serveur["args"][-2:], ["--backend", "postgres"])
        self.assertEqual(serveur["env"], {"PMZILLA_LAB_KNOWLEDGE_DBNAME": "pmzilla_eval_inventee"})

    def test_voie_inconnue_refusee(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.lancer("--backend", "mysql")


class FichierDeCasDeCommandes(PassageFictif):
    COMMANDES = [{"id": "cmd1", "question": "/commande un", "posture": "Delivery"}]

    def setUp(self):
        super().setUp()
        self.autre = self.tmp / "cas-commandes.yaml"
        self.autre.write_text(yaml.safe_dump(self.COMMANDES, allow_unicode=True), encoding="utf-8")

    def test_le_passage_des_commandes_est_un_passage_a_part_et_le_decompte_standard_ne_change_pas(self):
        standard = self.lancer()
        self.assertIn("BILAN 2/2", standard)
        passage_standard = self.dernier_resultat()
        with mock.patch.object(essai.dt, "datetime", wraps=essai.dt.datetime) as faux_dt:      # un autre horodatage de passage
            faux_dt.now.return_value = essai.dt.datetime(2099, 1, 1, 0, 0, 0)
            sortie = self.lancer("--cases-file", str(self.autre))
        self.assertIn("BILAN 1/1", sortie)                       # ses vérifications ne s'ajoutent pas à celles de cas.yaml
        self.assertEqual(self.sessions[-1], "/commande un")
        rapports = list(essai.REPORT_DIR.glob("essai-*.md"))
        self.assertEqual(len(rapports), 2)                       # un rapport par passage
        self.assertEqual([c["id"] for c in passage_standard["cas"]], ["c1", "c2"])
        self.assertEqual([c["id"] for c in self.dernier_resultat()["cas"]], ["cmd1"])
        self.assertTrue(passage_standard["complet"])
        self.assertFalse(self.dernier_resultat()["complet"])

    def test_le_fichier_de_cas_standard_n_est_pas_modifie(self):
        avant = essai.CASES_FILE.read_text(encoding="utf-8")
        self.lancer("--cases-file", str(self.autre))
        self.assertEqual(essai.CASES_FILE.read_text(encoding="utf-8"), avant)


class PassageComplet(PassageFictif):
    def test_un_passage_sans_selection_ni_fichier_alternatif_est_complet(self):
        self.lancer()
        self.assertTrue(self.dernier_resultat()["complet"])

    def test_une_selection_de_cas_rend_le_passage_incomplet(self):
        self.lancer("--cases", "c1")
        self.assertFalse(self.dernier_resultat()["complet"])

    def test_un_fichier_de_cas_alternatif_rend_le_passage_incomplet(self):
        autre = self.tmp / "autre.yaml"
        autre.write_text(yaml.safe_dump(CAS, allow_unicode=True), encoding="utf-8")
        self.lancer("--cases-file", str(autre))
        self.assertFalse(self.dernier_resultat()["complet"])

    def test_selection_et_fichier_alternatif_ensemble_restent_incomplets(self):
        autre = self.tmp / "autre.yaml"
        autre.write_text(yaml.safe_dump(CAS, allow_unicode=True), encoding="utf-8")
        self.lancer("--cases-file", str(autre), "--cases", "c1")
        self.assertFalse(self.dernier_resultat()["complet"])


if __name__ == "__main__":
    unittest.main()
