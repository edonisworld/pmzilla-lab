"""
Tests de `story_quality.py report --name <série> --json` (change story-quality-audit, tâche 3.24, design D15, M2 (a), spec story-quality-report
« The report data contract is printed as JSON » et « has a closed key set »). Le JSON est le contrat de `report_data` : un seul document
sur la sortie standard, aucun fichier, aucune autre ligne ; le Markdown et le JSON portent les mêmes chiffres, les mêmes cellules masquées
et le même ordre.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_rapport import ALPHA, BETA, VUE_EQUIPE, EspaceRapport, sr  # noqa: E402
from test_donnees_rapport import (  # noqa: E402
    verifier_cellule, verifier_cle, verifier_part,
)


class Document(EspaceRapport):
    def json(self, *options):
        code, sortie, erreur = self.lancer("report", "--name", "pilote", "--json", *options)
        self.assertEqual(code, 0, erreur)
        return json.loads(sortie), sortie, erreur

    def test_la_sortie_standard_est_un_seul_document_json(self):
        document, sortie, _ = self.json()
        self.assertEqual((document["contract"], document["contract_version"]), ("story_quality_report", 1))
        self.assertTrue(sortie.lstrip().startswith("{") and sortie.rstrip().endswith("}"))

    def test_les_equipes_viennent_dans_l_ordre_des_noms_et_aucun_fichier_n_est_ecrit(self):
        document, sortie, _ = self.json()
        self.assertEqual([e["team"] for e in document["teams"]], [ALPHA, BETA])
        self.assertEqual(self.fichiers(), [])
        self.assertFalse(self.rapports.exists())
        self.assertNotIn("story quality report written", sortie)
        self.assertNotIn("rapport de qualité des stories écrit", sortie)

    def test_la_phrase_pas_de_surcouche_va_sur_la_sortie_d_erreur(self):
        _, sortie, erreur = self.json("--language", "en")
        self.assertEqual(erreur.strip(), "no organisation overlay: core grid only")
        self.assertNotIn("overlay: core", sortie)

    def test_sans_seuil_de_recurrence_refus_en_code_1_sans_sortie(self):
        self.reglages = (None, 5)
        code, sortie, erreur = self.lancer("report", "--name", "pilote", "--json", "--language", "en")
        self.assertEqual((code, sortie), (1, ""))
        self.assertIn("story_quality.recurrence_threshold", erreur)
        self.assertEqual(self.vues_lues, [])                     # refusé avant toute lecture des vues
        code, _, erreur = self.lancer("report", "--name", "pilote", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("story_quality.recurrence_threshold", erreur)
        self.assertEqual(self.fichiers(), [])

    def test_les_parts_sont_deux_cellules(self):
        document, _, _ = self.json()
        part = document["teams"][0]["criteria"]["story"][1]["share_not_met"]          # story-un d'Alpha : 9 sur 20 audités (M4 (b))
        self.assertEqual(part, {"state": "value", "numerator": {"state": "value", "value": 9}, "denominator": {"state": "value", "value": 20}})

    def test_permis_dans_une_session_claude_code(self):
        self.environ["CLAUDECODE"] = "1"
        self.assertEqual(self.lancer("report", "--name", "pilote", "--json")[0], 0)

    def test_cellules_masquees_en_objets_avec_le_seuil_effectif_jamais_un_nombre_ni_le_texte(self):
        self.reglages = (0.5, 8)
        document, sortie, _ = self.json()
        comptes = document["teams"][0]["criteria"]["story"][0]["counts"]
        self.assertEqual(comptes["not_applicable"], {"state": "masked", "threshold": 8})          # 5 passe sous le seuil relevé
        self.assertEqual(set(comptes), {"met", "not_met", "not_applicable", "undetermined"})
        self.assertNotIn("<", sortie)
        self.assertNotIn('"value": null', sortie)

    def test_une_petite_equipe_n_a_que_des_cellules_masquees(self):
        petite = [dict(VUE_EQUIPE[0], team="Equipe Zzpetite", audited=3, met=0, not_met=None, not_applicable=None, undetermined=None)]
        self.vues["quality_by_team"] = VUE_EQUIPE + petite
        document, _, _ = self.json()
        equipe = next(e for e in document["teams"] if e["team"] == "Equipe Zzpetite")
        critere = equipe["criteria"]["story"][0]
        self.assertEqual(critere["share_met"], {"state": "masked", "threshold": 5})
        self.assertEqual(critere["share_not_met"], {"state": "masked", "threshold": 5})
        for cellule in critere["counts"].values():
            self.assertEqual(cellule, {"state": "masked", "threshold": 5})

    def test_aucune_cle_hors_du_contrat_et_la_chaine_du_produit_sans_equipe(self):
        document, sortie, _ = self.json()
        self.assertEqual(set(document), {"contract", "contract_version", "grid", "notice", "teams", "product_chain"})
        for equipe in document["teams"]:
            self.assertEqual(set(equipe), {"team", "single_po", "single_po_notice", "coverage", "criteria", "probable_causes"})
            for criteres in equipe["criteria"].values():
                for c in criteres:
                    verifier_cle(self, c["counts"], "counts")
                    verifier_part(self, c["share_not_met"])
                    for cellule in c["counts"].values():
                        verifier_cellule(self, cellule)
        verifier_cle(self, document["product_chain"], "chain")
        for ligne in document["product_chain"]["lines"]:
            verifier_cle(self, ligne, "line")
        chaine = json.dumps(document["product_chain"])
        for nom in (ALPHA, BETA):
            self.assertNotIn(nom, chaine)

    def test_rien_d_identifiant_dans_le_json(self):
        self.vues["quality_by_team"] = [dict(l, key="ZZ-1234", title="zztitre", person="zzpersonne", feedback="zzretour", sample="zzverdict")
                                        for l in VUE_EQUIPE]
        _, sortie, _ = self.json()
        for distinctif in ("ZZ-1234", "zztitre", "zzpersonne", "zzretour", "zzverdict"):
            self.assertNotIn(distinctif, sortie)

    def test_les_libelles_suivent_la_langue_et_les_codes_non(self):
        en, _, _ = self.json("--language", "en")
        fr, _, _ = self.json("--language", "fr")
        self.assertEqual(en["teams"][0]["criteria"]["story"][1]["label"], "Label story-un")
        self.assertEqual(fr["teams"][0]["criteria"]["story"][1]["label"], "Libellé story-un")
        self.assertEqual(en["notice"]["code"], fr["notice"]["code"])
        self.assertNotEqual(en["notice"]["text"], fr["notice"]["text"])
        self.assertEqual(en["teams"][0]["criteria"]["story"][1]["link"], fr["teams"][0]["criteria"]["story"][1]["link"])

    def test_le_json_est_celui_du_service(self):
        resultat = {"contract": "story_quality_report", "contract_version": 1, "teams": [{"team": "Zz"}, {"team": "Aa"}]}
        with mock.patch.object(sr.data, "report_data", return_value=resultat):
            code, sortie, _ = self.lancer("report", "--name", "pilote", "--json")
        self.assertEqual((code, json.loads(sortie)), (0, resultat))                 # même ordre que le service, rien d'ajouté ni de trié


class MemesChiffresQueLeMarkdown(EspaceRapport):
    def test_memes_chiffres_memes_cellules_masquees_meme_ordre(self):
        self.lancer("report", "--name", "pilote", "--language", "en")
        markdown = (self.rapports / "qualite-stories-pilote-2026-10-20.md").read_text(encoding="utf-8")
        code, sortie, _ = self.lancer("report", "--name", "pilote", "--json", "--language", "en")
        self.assertEqual(code, 0)
        document = json.loads(sortie)
        self.assertEqual(re.findall(r"^## (.*)$", markdown, flags=re.M), [e["team"] for e in document["teams"]] + ["Product chain"])
        lignes_causes = [l for e in document["teams"] for l in e["probable_causes"]["lines"]] + document["product_chain"]["lines"]
        self.assertGreater(len(lignes_causes), 0)
        for ligne in lignes_causes:                    # mêmes causes probables et même chaîne du produit, dans le même ordre
            part = ligne["share_not_met"]
            self.assertIn(f"- {ligne['code']} | {ligne['label']} | share not met: {part['numerator']['value']}/{part['denominator']['value']}",
                          markdown)
        positions = []
        for equipe in document["teams"]:
            for genre in ("story", "epic"):
                for critere in equipe["criteria"][genre]:
                    ligne = f"- {critere['code']} | {critere['label']} | share met: {sr.texte_part(critere['share_met'], lambda k, **v: 'masked')}"
                    self.assertIn(ligne, markdown)
                    positions.append(markdown.index(ligne, markdown.index(f"## {equipe['team']}")))
        self.assertEqual(positions, sorted(positions))
        masquees = sum(1 for e in document["teams"] for g in ("story", "epic") for c in e["criteria"][g] if c["share_met"]["state"] == "masked")
        self.assertGreater(masquees, 0)
        self.assertEqual(len(re.findall(r"share met: masked", markdown)), masquees)  # une part masquée du JSON est « masked » dans le Markdown


class Codes(EspaceRapport):
    def test_vues_illisibles_rien_sur_la_sortie_standard(self):
        with mock.patch.object(sr, "lire_vue", side_effect=RuntimeError("zz")):
            code, sortie, erreur = self.lancer("report", "--name", "pilote", "--json", "--language", "en")
        self.assertEqual((code, sortie), (1, ""))
        self.assertIn("database error", erreur)

    def test_nom_invalide_en_usage_sans_sortie(self):
        code, sortie, _ = self.lancer("report", "--name", "../x", "--json")
        self.assertEqual((code, sortie), (2, ""))

    def test_socle_absent_en_code_3_sans_sortie(self):
        self.socle.unlink()
        code, sortie, _ = self.lancer("report", "--name", "pilote", "--json")
        self.assertEqual((code, sortie), (3, ""))


if __name__ == "__main__":
    unittest.main()
