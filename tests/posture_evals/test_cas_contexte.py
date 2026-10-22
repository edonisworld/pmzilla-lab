"""
Les deux cas du jeu d'essai des notes de contexte (organisation-context, design D13, tâche 11.2) : tests/postures/cas-contexte.yaml,
joué avec `--cases-file`. Un cas cite une note déclarative avec sa formule, l'autre signale une note périmée. Notes inventées dans la
bibliothèque jetable du passage (champ `context_notes`).

    bash tests/run_all.sh posture_evals

Aucune base, aucun appel payant : les fichiers de cas et les notes sont vérifiés, l'indexation du cas est vue par un faux subprocess.
"""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import context_lab  # noqa: E402
import posture_evals as essai  # noqa: E402

FICHIER = RACINE / "tests" / "postures" / "cas-contexte.yaml"
DOSSIER = RACINE / "tests" / "postures" / "fixtures" / "organisation-context"
NOTE_A_JOUR = "2026-09-01-forums-de-decision.md"
NOTE_PERIMEE = "2025-03-01-dependances-de-donnees.md"


def cas():
    return {c["id"]: c for c in yaml.safe_load(FICHIER.read_text(encoding="utf-8"))}


class FichierDeCas(unittest.TestCase):
    def test_deux_cas_avec_leur_variante_anglaise(self):
        tous = cas()
        self.assertEqual(sorted(tous), ["contexte-note-declarative", "contexte-note-perimee"])
        for ident, c in tous.items():
            with self.subTest(ident):
                self.assertTrue(c["question"].strip())
                self.assertEqual(c["posture"], "Scaling")
                self.assertEqual(len(c["en"]["judgements"]), len(c["judgements"]))
                self.assertTrue(c["en"]["question"].strip())
                self.assertEqual(c["verifications"], [{"tool": "search_library", "collections": ["contexte"]}])

    def test_un_critere_bloquant_par_point_et_des_indicateurs_non_bloquants(self):
        for ident, c in cas().items():
            with self.subTest(ident):
                bloquants = [j for j in c["judgements"] if not isinstance(j, dict)]
                indicateurs = [j for j in c["judgements"] if isinstance(j, dict) and j.get("non_blocking")]
                self.assertEqual((len(bloquants), len(indicateurs)), (1, 1))

    def test_chaque_cas_nomme_sa_note_et_la_formule_attendue(self):
        a_jour, perimee = cas()["contexte-note-declarative"], cas()["contexte-note-perimee"]
        self.assertIn("Forums de décision de la ligne de produits", a_jour["judgements"][0])
        self.assertIn("2026-09-01", a_jour["judgements"][0])
        self.assertIn("Dépendances de données entre équipes produit", perimee["judgements"][0])
        self.assertIn("possiblement périmée (à revoir depuis le 2025-06-01)", perimee["judgements"][0])
        self.assertIn("possibly out of date (review due since 2025-06-01)", perimee["en"]["judgements"][0])

    def test_les_dossiers_designes_existent(self):
        for c in cas().values():
            self.assertTrue((RACINE / c["library"]).is_dir())
            self.assertTrue((RACINE / c["context_notes"] / "notes").is_dir())

    def test_aucun_nom_de_personne_ni_d_equipe_reelle(self):
        texte = FICHIER.read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in DOSSIER.rglob("*.md"))
        self.assertIsNone(re.search(r"/Users/|PMZilla-Lab/", texte))


class NotesInventees(unittest.TestCase):
    def champs(self, nom):
        champs, _ = context_lab.parse_header((DOSSIER / "notes" / nom).read_text(encoding="utf-8"))
        return champs

    def test_les_en_tetes_suivent_la_regle_des_notes(self):
        for nom in (NOTE_A_JOUR, NOTE_PERIMEE):
            with self.subTest(nom):
                self.assertIsNone(context_lab.header_problem(self.champs(nom)))

    def test_une_note_a_jour_longtemps_et_une_note_deja_perimee(self):
        self.assertGreater(self.champs(NOTE_A_JOUR)["review"], "2029-12-31")
        self.assertLess(self.champs(NOTE_PERIMEE)["review"], "2026-01-01")
        self.assertEqual(self.champs(NOTE_A_JOUR)["nature"], "declarative")

    def test_chaque_corps_depasse_le_seuil_d_un_passage(self):
        for nom in (NOTE_A_JOUR, NOTE_PERIMEE):
            _, corps = context_lab.parse_header((DOSSIER / "notes" / nom).read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(corps.strip()), 200)


class IndexationDuCas(unittest.TestCase):
    """case_library passe l'option --context quand le cas désigne un dossier de notes, et seulement alors."""

    def lancer(self, cas_):
        appels = []

        def faux(commande, **options):
            appels.append(commande)
            return mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(essai.subprocess, "run", faux), mock.patch.object(essai, "reset_case_library"), \
                mock.patch.object(essai, "mcp_config", return_value=Path("mcp.json")):
            essai.case_library(cas_, Path("."), None, "base_jetable")
        return appels[0]

    def test_l_option_context_est_passee_au_dossier_du_cas(self):
        commande = self.lancer(cas()["contexte-note-declarative"])
        position = commande.index("--context")
        self.assertEqual(Path(commande[position + 1]), essai.WORKSPACE / "tests/postures/fixtures/organisation-context")
        self.assertEqual(Path(commande[position - 1]), essai.WORKSPACE / "tests/postures/fixtures/organisation-context/collections")

    def test_sans_notes_pas_d_option(self):
        commande = self.lancer({"id": "x", "library": "tests/postures/fixtures/watch-digest/collections"})
        self.assertNotIn("--context", commande)


if __name__ == "__main__":
    unittest.main()
