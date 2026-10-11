"""Les scripts qui lisent flux.yaml (et tri.yaml, sources.yaml, anonymes.yaml) refusent une clé écrite deux fois, ou un
ancien nom de réglage, au lieu de garder la dernière ligne en silence.

Données inventées, fichiers temporaires ; aucun accès à Flux-Lab/ ni à Jira."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import dependencies_jira  # noqa: E402
import flow_board  # noqa: E402
import flux_jira  # noqa: E402
import history_jira  # noqa: E402
import watch_lab  # noqa: E402
from yaml_strict import ErreurConfig  # noqa: E402

DOUBLON = "projets_exclus: [A]\netats_a_faire: [X]\nprojets_exclus: [B]\n"
ANCIEN_ET_NOUVEAU = "etats_a_faire: a\ntodo_states: b\n"


class Lecteurs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fichier = Path(self.tmp.name) / "flux.yaml"

    def ecrire(self, texte: str) -> None:
        self.fichier.write_text(texte, encoding="utf-8")

    def lecteurs(self):
        return {
            "flux_jira": (lambda: flux_jira.config(), mock.patch.object(flux_jira, "CONFIG_FILE", self.fichier)),
            "dependencies_jira": (lambda: dependencies_jira.config(), mock.patch.object(dependencies_jira, "CONFIG_FILE", self.fichier)),
            "history_jira": (lambda: history_jira.reglages(), mock.patch.object(history_jira, "CONFIG_FILE", self.fichier)),
            "flow_board": (lambda: flow_board.reglages(), mock.patch.object(flow_board, "CONFIG", self.fichier)),
        }

    def test_cle_ecrite_deux_fois_refusee_avec_les_deux_lignes(self):
        self.ecrire(DOUBLON)
        for nom, (lire, patch) in self.lecteurs().items():
            with self.subTest(nom), patch, self.assertRaises(ErreurConfig) as c:
                lire()
            self.assertIn("« projets_exclus » est écrite deux fois (L1 et L3)", str(c.exception))

    def test_ancien_nom_refuse_avec_la_ligne_et_le_nom_actuel(self):
        self.ecrire(ANCIEN_ET_NOUVEAU)
        for nom, (lire, patch) in self.lecteurs().items():
            with self.subTest(nom), patch, self.assertRaises(ErreurConfig) as c:
                lire()
            self.assertIn("L1 : « etats_a_faire » n'existe plus ; utiliser « todo_states »", str(c.exception))

    def test_fichier_correct_toujours_lu(self):
        self.ecrire("todo_states: '%Y-%m-%d'\nexcluded_projects: [A]\n")
        for nom, (lire, patch) in self.lecteurs().items():
            with self.subTest(nom), patch:
                lire()

    def test_sources_de_la_veille(self):
        fichier = Path(self.tmp.name) / "sources.yaml"
        fichier.write_text("sources: []\nsources: []\n", encoding="utf-8")
        with mock.patch.object(watch_lab, "SOURCES_FILE", fichier), self.assertRaises(ErreurConfig) as c:
            watch_lab.load_sources()
        self.assertIn("sources.yaml : « sources » est écrite deux fois (L1 et L2)", str(c.exception))


if __name__ == "__main__":
    unittest.main()
