"""
Tests complémentaires du jeu d'essai (tools/posture_evals.py), partie A : openspec/test-gaps.md, section posture-evals.
Mêmes résultats sur les deux voies de la bibliothèque, ligne de rapport du fichier de cas de commandes, rejugement sans verrou.

    bash tests/run_all.sh posture_evals

Aucun appel à Claude, aucun réseau, aucune vraie base : les séances sont remplacées par une réponse fixe, la voie PostgreSQL
tourne sur la base jetable des tests de la bibliothèque (sautée sans base). Données inventées (bibliothèque de démonstration).
"""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tests" / "library_backend"))
import pg_demo                  # noqa: E402  (ajoute tools/, tests/db et tests/fixtures_library au chemin)
import demo_library as demo     # noqa: E402
import knowledge_library as kl  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402

import test_posture_evals as socle
import test_gaps_posture_evals as gaps
import posture_evals as essai

QUESTIONS = [("le flux de travail", None, None), ("hypothesis experiment", ["produit"], None), ("prévision", ["watch"], None)]
# « watch » : la bibliothèque inventée ne stocke plus « veille » depuis la fin des anciens noms (R-5) ; filtrer sur « veille » ne
# trouvait rien sur aucune des deux voies (le test, avec base seulement, ne tournait pas dans dbtest.sh).


class MemesResultatsSurLesDeuxVoies(gaps.PassageFictif):
    """La voie est transmise au serveur MCP par la configuration du passage (testé ailleurs) ; ici, la voie que cette configuration
    désigne est ouverte comme le fait `serve` (choose_backend, puis la bibliothèque de la voie) sur la même bibliothèque inventée.
    Les passages d'une séance sont ceux que rend `search_library` : on compare ces résultats, pas ceux d'une séance Claude."""

    def setUp(self):
        super().setUp()
        self.pg = pg_demo.ThrowawayDatabase(self)          # saute le test sans base jetable
        chemin = self.tmp / "library.sqlite"
        demo.build_sqlite(chemin)
        for patch in (mock.patch.object(library, "DATA_DIR", self.tmp), mock.patch.object(library, "DB_PATH", chemin),
                      mock.patch.object(library, "embed", demo.fake_embed)):
            patch.start()
            self.addCleanup(patch.stop)

    def voie_du_passage(self, option: str) -> str:
        """La voie lue par le serveur dans la configuration MCP écrite pour un passage lancé avec `--backend option`."""
        self.lancer("--cases", "c1", "--backend", option)
        config = json.loads(max(essai.DATA.glob("*/mcp.json"), key=lambda p: p.stat().st_mtime_ns).read_text(encoding="utf-8"))
        args = config["mcpServers"]["pmzilla-library"]["args"]
        return library.choose_backend(args[args.index("--backend") + 1])

    def ouvrir(self, voie: str):
        if voie == "postgres":
            return kl.PostgresLibrary(connect=self.pg.connect, embed=demo.fake_embed)
        return library.Library()

    def test_memes_passages_sur_la_voie_fichier_et_la_voie_base(self):
        fichier, base = (self.ouvrir(self.voie_du_passage(option)) for option in ("sqlite", "postgres"))
        self.assertIsInstance(fichier, library.Library)
        self.assertIsInstance(base, kl.PostgresLibrary)
        for question, collections, types in QUESTIONS:
            with self.subTest(question=question, collections=collections):
                a = fichier.search(question, collections, 14, None, types)
                b = base.search(question, collections, 14, None, types)
                self.assertTrue(a)                                       # la fixture répond : l'égalité n'est pas vide
                self.assertEqual({(r["file"], r["position"]) for r in a}, {(r["file"], r["position"]) for r in b})
                self.assertEqual((a[0]["file"], a[0]["position"]), (b[0]["file"], b[0]["position"]))


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
