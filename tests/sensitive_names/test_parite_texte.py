"""
Parité de la règle des noms avec Mothra (mothra-slices D20, tâche 18.3) : les cas partagés de
mothra/contract/test-data/cas-texte.json, noms inventés, sont joués contre `parse_names`, `patterns` et `line_matches`
de tools/sensitive_names.py ; le même fichier est joué contre contract/src/texte.ts par la suite npm `mothra`.

    uv run python -m unittest discover -s tests/sensitive_names -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import sensitive_names as sn  # noqa: E402

CAS = RACINE / "mothra" / "contract" / "test-data" / "cas-texte.json"
CAS_NOMS = RACINE / "mothra" / "contract" / "test-data" / "cas-noms.json"


class PariteTexteMothra(unittest.TestCase):
    def test_les_cas_partages_donnent_le_meme_resultat_qu_en_typescript(self):
        donnees = json.loads(CAS.read_text(encoding="utf-8"))
        motifs = sn.patterns(sn.parse_names("\n".join(donnees["names"])))
        self.assertTrue(donnees["cases"])
        for cas in donnees["cases"]:
            with self.subTest(cas["name"]):
                self.assertEqual(sn.line_matches(motifs, cas["text"]), cas["matches"])

    def test_le_filtre_des_noms_distinctifs_et_l_extrait_donnent_les_memes_resultats_qu_en_typescript(self):
        donnees = json.loads(CAS_NOMS.read_text(encoding="utf-8"))
        for cas in donnees["distinctive"]:
            with self.subTest(cas["label"]):
                self.assertEqual(sn.is_distinctive(cas["label"]), cas["expected"])
        for cas in [{"name": "extract", **donnees["extract"]}, *donnees["extracts"]]:
            with self.subTest(cas["name"]), tempfile.TemporaryDirectory() as dossier:
                extrait = Path(dossier) / "equipes-lisibles.yaml"
                # En octets : les retours chariot du cas (CRLF, \r seul) et la marque d'ordre des octets sont écrits tels quels.
                extrait.write_bytes(cas["text"].encode("utf-8"))
                (Path(dossier) / "noms-generiques.txt").write_bytes(cas["generic"].encode("utf-8"))
                self.assertEqual(sn.extract_names(extrait), cas["expected"])

    def test_la_lecture_d_une_liste_donne_les_memes_noms_qu_en_typescript(self):
        donnees = json.loads(CAS_NOMS.read_text(encoding="utf-8"))
        self.assertTrue(donnees["parse"])
        for cas in donnees["parse"]:
            with self.subTest(cas["name"]):
                self.assertEqual(sn.parse_names(cas["text"]), cas["expected"])


if __name__ == "__main__":
    unittest.main()
