"""
Tests complémentaires du jeu d'essai (tools/posture_evals.py), partie A : openspec/test-gaps.md, section posture-evals.
Ligne de rapport du fichier de cas de commandes, rejugement sans verrou.

    bash tests/run_all.sh posture_evals

Aucun appel à Claude, aucun réseau, aucune vraie base : les séances sont remplacées par une réponse fixe. La voie unique de la bibliothèque est
vérifiée contre les valeurs figées dans tests/library_backend (demo_expected).
"""
import contextlib
import io
import json
import sys
import unittest
from unittest import mock

import yaml

import test_posture_evals as socle
import test_gaps_posture_evals as gaps
import posture_evals as essai


class LigneDuFichierDeCasDeCommandes(gaps.PassageFictif):
    """Question ouverte de la spec (posture-evals-report) : le rapport pourrait porter une ligne dédiée au fichier de cas de
    commandes ; ce n'est pas tranché. Seul l'état établi est testé : aucune ligne dédiée, compte des vérifications inchangé.
    L'entrée du jeu de lacunes reste ouverte : l'assertion d'une ligne dédiée attend la décision."""

    def test_le_rapport_ne_nomme_pas_le_fichier_de_cas_et_le_compte_est_celui_du_fichier(self):
        autre = self.tmp / "cas-commandes-inventes.yaml"
        autre.write_text(yaml.safe_dump([{"id": "cmd1", "question": "/commande un", "posture": "Delivery"}]), encoding="utf-8")
        self.lancer("--cases-file", str(autre))
        rapport = next(essai.REPORT_DIR.glob("essai-*.md")).read_text(encoding="utf-8")
        self.assertNotIn("cas-commandes-inventes", rapport)
        self.assertNotIn("commandes slash", rapport)
        self.assertIn("1/1 vérifications réussies sur 1 cas", rapport)       # le décompte n'est que celui de ses cas


class RejugementSansVerrou(socle.Base):
    def preparer(self):
        passage = essai.DATA / "2026-10-01-090000"
        passage.mkdir(parents=True)
        (passage / "avec.jsonl").write_text("\n".join(json.dumps(e) for e in socle.SEANCE), encoding="utf-8")
        (passage / "resultats.json").write_text(json.dumps({"base": "b", "memoire": "figée", "cas": []}), encoding="utf-8")
        essai.CASES_FILE.write_text(yaml.safe_dump([{"id": "avec", "question": "Q ?", "posture": "Delivery"}]), encoding="utf-8")
        patch = mock.patch.object(essai, "git", lambda *a, **k: "")
        patch.start()
        self.addCleanup(patch.stop)
        return passage

    def lancer(self, *arguments) -> str:
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["posture_evals.py", *arguments]), contextlib.redirect_stdout(sortie):
            essai.main()
        return sortie.getvalue()

    def test_un_rejugement_se_termine_pendant_qu_un_autre_passage_tient_le_verrou(self):
        passage = self.preparer()
        verrou = essai.lock_pass(essai.DATA)             # un passage en cours
        self.addCleanup(verrou.close)
        sortie = self.lancer("--rejudge", passage.name, "--cases", "avec")      # ne lève pas « Un autre passage ... »
        self.assertIn("BILAN", sortie)
        self.assertTrue(list(essai.REPORT_DIR.glob("essai-*.md")))

    def test_un_passage_normal_est_refuse_quand_le_verrou_est_pris(self):
        self.preparer()
        verrou = essai.lock_pass(essai.DATA)
        self.addCleanup(verrou.close)
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("--cases", "avec")
        self.assertIn("Un autre passage", str(erreur.exception))


if __name__ == "__main__":
    unittest.main()
