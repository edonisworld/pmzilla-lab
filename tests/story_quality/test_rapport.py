"""
Tests de `story_quality.py report --name <série>` (change story-quality-audit, tâche 3.10, design D8, D14, D15, spec story-quality-report) :
le rapport Markdown met en forme le résultat de `report_data` et ne calcule ni part, ni masquage, ni ordre. Garde anti-comparaison :
aucune ligne ne porte les chiffres de deux équipes, aucune note composite, aucun total par équipe, aucun classement.

Les points d'extension des tâches 3.18 (ligne des grilles, causes probables) et 3.21 (chaîne du produit) sont éprouvés avec des fonctions
d'essai ; leur contenu réel est testé dans test_rapport_causes.py.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_rapport import ALPHA, BETA, VUE_COUVERTURE, VUE_EQUIPE, EspaceRapport, sr  # noqa: E402
from test_donnees_rapport import ligne_equipe  # noqa: E402


def sections(texte):
    """{équipe: texte de sa section} d'après les titres de niveau 2."""
    morceaux = re.split(r"^## ", texte, flags=re.M)[1:]
    return {m.splitlines()[0]: m for m in morceaux}


class DossierDesRapports(unittest.TestCase):
    """Décision du 2026-10-21, point 6 : sans PMZILLA_LAB_REPORTS, le dossier des rapports est Flux-Lab/rapports de la racine de contenu
    (tools/lab_paths.py), jamais celui de la racine du code (un worktree n'a pas de Flux-Lab)."""

    def test_sous_la_racine_de_contenu(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            contenu = Path(d) / "contenu"
            contenu.mkdir()
            dossier = sr.dossier_rapports({"PMZILLA_LAB_WORKSPACE": str(contenu)})
            self.assertEqual(dossier, contenu.resolve() / "Flux-Lab" / "rapports")
            self.assertNotEqual(dossier.parent.parent, Path(sr.__file__).resolve().parents[1])

    def test_la_variable_des_rapports_l_emporte(self):
        self.assertEqual(sr.dossier_rapports({sr.REPORTS_VARIABLE: "/x/rapports", "PMZILLA_LAB_WORKSPACE": "/absent"}),
                         Path("/x/rapports"))


class Ecriture(EspaceRapport):
    def test_le_rapport_est_ecrit_sous_le_nom_de_la_serie_et_du_jour(self):
        code, sortie, erreur = self.lancer("report", "--name", "pilote", "--language", "en")
        self.assertEqual((code, sortie.splitlines()[-1], erreur), (0, "story quality report written", ""))
        self.assertEqual(self.fichiers(), ["qualite-stories-pilote-2026-10-20.md"])

    def test_la_phrase_pas_de_surcouche_est_toujours_imprimee(self):
        code, sortie, erreur = self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual(sortie.splitlines(), ["no organisation overlay: core grid only", "story quality report written"])
        self.assertEqual(erreur, "")

    def test_la_phrase_d_ecriture_est_en_francais_par_defaut(self):
        code, sortie, _ = self.lancer("report", "--name", "serie")
        self.assertEqual((code, sortie.splitlines()[-1]), (0, "rapport de qualité des stories écrit"))

    def test_seules_les_trois_vues_sont_lues(self):
        self.lancer("report", "--name", "serie")
        self.assertCountEqual(self.vues_lues, ["quality_by_team", "quality_coverage_by_team", "quality_by_product"])

    def test_permis_dans_une_session_claude_code(self):
        self.environ["CLAUDECODE"] = "1"
        self.assertEqual(self.lancer("report", "--name", "serie")[0], 0)

    def test_titre_et_notice_en_tete(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        lignes = self.rapport().splitlines()
        self.assertEqual(lignes[0], "# Story quality: serie")
        self.assertEqual(lignes[2], "Team results: never a person's evaluation, never a ranking")

    def test_titre_et_notice_en_francais(self):
        self.lancer("report", "--name", "serie")
        lignes = self.rapport().splitlines()
        self.assertEqual(lignes[0], "# Qualité des stories : serie")
        self.assertEqual(lignes[2], "Résultats d'équipe : jamais l'évaluation d'une personne, jamais un classement")
        self.assertTrue(lignes[4].startswith("Lecture : une part se lit sur tous les éléments audités, y compris ceux pour qui le critère "
                                             "est sans objet."), lignes[4])

    def test_la_legende_dit_le_denominateur_et_le_masquage(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        lignes = self.rapport().splitlines()
        self.assertIn("a share is read over all audited items, including those for which the criterion does not apply", lignes[4])
        self.assertIn("masked so that a count under 5 cannot be recovered by difference; never estimated", lignes[4])
        self.assertIn("\"masked\": a cell under the threshold of 5 or masked", lignes[4])       # idée #417 : le seuil est dans la légende

    def test_une_section_par_equipe_dans_l_ordre_des_noms_avec_parts_et_denominateurs(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        texte = self.rapport()
        self.assertEqual(re.findall(r"^## (.*)$", texte, flags=re.M), [ALPHA, BETA, "Product chain"])     # chaîne du produit : 3.21
        alpha = sections(texte)[ALPHA]
        self.assertIn("- story-un | Label story-un | share met: 6/20", alpha)            # M4 (b) : sur tous les audités
        self.assertIn("- story-trois | Label story-trois | share met: 13/20", alpha)
        self.assertIn("Coverage: 25 collected, 20 audited, masked without acceptance criteria", alpha)

    def test_les_cellules_masquees_s_ecrivent_masque_sans_estimation(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        alpha = sections(self.rapport())[ALPHA]
        self.assertIn("- epic-un | Label epic-un | share met: 9/12", alpha)              # les sans objet masqués ne masquent plus la part
        self.assertIn("- story-trois | Label story-trois | share met: 13/20", alpha)
        self.assertIn("Coverage: masked collected, masked audited, masked without acceptance criteria", alpha)
        beta = sections(self.rapport())[BETA]
        self.assertIn("- story-trois | Label story-trois | share met: masked", beta)
        self.assertNotIn("<", self.rapport())

    def test_un_seuil_releve_s_ecrit_dans_la_legende(self):
        self.reglages = (0.5, 12)
        self.lancer("report", "--name", "serie", "--language", "en")
        self.assertIn("- story-un | Label story-un | share met: masked", sections(self.rapport())[ALPHA])
        self.assertIn("\"masked\": a cell under the threshold of 12 or masked", self.rapport().splitlines()[4])

    def test_libelles_en_francais(self):
        self.lancer("report", "--name", "serie", "--language", "fr")
        alpha = sections(self.rapport())[ALPHA]
        self.assertIn("- story-un | Libellé story-un | part satisfaite : 6/20", alpha)
        self.assertIn("Couverture : 25 collectés, 20 audités, masqué sans critère d'acceptation", alpha)
        self.assertIn("« masqué » : cellule sous le seuil de 5 ou masquée", self.rapport().splitlines()[4])

    def test_la_phrase_un_seul_po_ouvre_la_section_de_l_equipe_signalee_seulement(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        phrase = "Single-PO team: these results are those of one person's work; never use them to evaluate that person"
        s = sections(self.rapport())
        self.assertEqual(s[ALPHA].splitlines()[2], phrase)
        self.assertNotIn(phrase, s[BETA])

    def test_le_drapeau_un_seul_po_ne_change_aucun_chiffre(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        avec = self.rapport()
        self.vues["quality_coverage_by_team"] = [dict(c, single_po=False) for c in VUE_COUVERTURE]
        self.lancer("report", "--name", "serie", "--language", "en")
        sans = self.rapport()
        retire = lambda texte: [l for l in texte.splitlines() if l and not l.startswith("Single-PO")]
        self.assertEqual(retire(avec), retire(sans))

    def test_rien_d_identifiant_dans_le_rapport(self):
        self.vues["quality_by_team"] = [dict(l, key="ZZ-1234", title="zztitre distinctif", person="zzpersonne", feedback="zzretour")
                                        for l in VUE_EQUIPE]
        self.lancer("report", "--name", "serie")
        texte = self.rapport()
        for distinctif in ("ZZ-1234", "zztitre", "zzpersonne", "zzretour"):
            self.assertNotIn(distinctif, texte)


class GardeAntiComparaison(EspaceRapport):
    def test_une_section_ne_porte_que_les_chiffres_de_son_equipe(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        s = sections(self.rapport())
        self.assertIn("6/20", s[ALPHA])
        self.assertNotIn("6/20", s[BETA])
        self.assertIn("8/30", s[BETA])
        self.assertNotIn("8/30", s[ALPHA])
        self.assertNotIn("41 collected", s[ALPHA])

    def test_aucune_ligne_ne_nomme_deux_equipes_ni_ne_compte_les_equipes(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        for ligne in self.rapport().splitlines():
            self.assertFalse(ALPHA in ligne and BETA in ligne, ligne)
        for mot in ("total", "score", "rank", "2 teams", "teams share"):
            self.assertNotIn(mot, self.rapport().lower().replace("never a ranking", ""))

    def test_aucune_note_composite_une_seule_part_par_ligne_de_critere(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        for ligne in self.rapport().splitlines():
            if ligne.startswith("- story") or ligne.startswith("- epic"):
                self.assertEqual(len(re.findall(r"\d+/\d+|\bmasked\b", ligne)), 1, ligne)

    def test_le_rapport_est_identique_quel_que_soit_l_ordre_des_lignes_des_vues(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        premier = self.rapport()
        self.vues = {vue: lignes[::-1] for vue, lignes in self.vues.items()}
        self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual(self.rapport(), premier)

    def test_les_resultats_echanges_gardent_l_ordre_des_sections(self):
        echange = lambda lignes: [dict(l, team=BETA if l["team"] == ALPHA else ALPHA) for l in lignes]
        self.vues["quality_by_team"] = echange(VUE_EQUIPE)
        self.vues["quality_coverage_by_team"] = echange(VUE_COUVERTURE)
        self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual(re.findall(r"^## (.*)$", self.rapport(), flags=re.M), [ALPHA, BETA, "Product chain"])
        self.assertIn("8/30", sections(self.rapport())[ALPHA])

    def test_un_rapport_sans_ligne_le_dit(self):
        self.vues = {vue: [] for vue in self.vues}
        self.assertEqual(self.lancer("report", "--name", "serie", "--language", "en")[0], 0)
        self.assertIn("No results in the story quality views", self.rapport())


class LaMiseEnFormeNeCalculeRien(EspaceRapport):
    def resultat_fabrique(self):
        rien = {"state": "masked", "threshold": 5}
        zero = {"state": "value", "value": 99}
        equipe = lambda nom: {"team": nom, "single_po": False, "single_po_notice": None,
                              "coverage": {"story": {"collected": zero, "audited": zero, "empty_acceptance_criteria": rien}},
                              "criteria": {"story": [{"code": "c-z", "label": "Libellé Z", "origin": "core", "link": "refinement",
                                                      "counts": {}, "share_met": {"state": "value", "numerator": {"state": "value", "value": 98},
                                                                    "denominator": {"state": "value", "value": 99}},
                                                      "share_not_met": rien}], "epic": []},
                              "probable_causes": {"notice": {"code": "x", "text": "x"}, "lines": []}}
        return {"contract": "story_quality_report", "contract_version": 1,
                "grid": {"core_version": 1, "overlay_version": None, "disabled_codes": []},
                "notice": {"code": "team_results_notice", "text": "NOTICE FABRIQUÉE"},
                "teams": [equipe("Zz-dernière"), equipe("Aa-première")], "product_chain": {"notice": {"code": "x", "text": "x"}, "lines": []}}

    def test_le_markdown_reprend_tel_quel_le_resultat_du_service(self):
        with mock.patch.object(sr.data, "report_data", return_value=self.resultat_fabrique()):
            self.assertEqual(self.lancer("report", "--name", "serie", "--language", "en")[0], 0)
        texte = self.rapport()
        self.assertIn("NOTICE FABRIQUÉE", texte)
        self.assertIn("share met: 98/99", texte)
        self.assertIn("Coverage: 99 collected, 99 audited, masked without acceptance criteria", texte)
        # l'ordre est celui du service : le rapport n'ordonne rien lui-même
        self.assertEqual(re.findall(r"^## (.*)$", texte, flags=re.M), ["Zz-dernière", "Aa-première", "Product chain"])

    def test_le_service_recoit_les_lignes_des_vues_le_seuil_de_recurrence_et_le_seuil_de_masquage(self):
        self.reglages = (0.4, 9)
        with mock.patch.object(sr.data, "report_data", return_value=self.resultat_fabrique()) as service:
            self.lancer("report", "--name", "serie", "--language", "en")
        args, options = service.call_args
        self.assertEqual(args[0], VUE_EQUIPE)
        self.assertEqual(args[1], VUE_COUVERTURE)
        self.assertEqual((options["threshold"], options["min_cell"], options["language"]), (0.4, 9, "en"))

    def test_les_points_d_extension_des_taches_3_18_et_3_21(self):
        appels = []
        entete = lambda r, t: appels.append("entete") or ["LIGNE D'ENTETE", ""]
        equipe = lambda e, r, t: appels.append("equipe") or [f"SOUS-SECTION {e['team']}", ""]
        finale = lambda r, t: appels.append("finale") or ["SECTION FINALE", ""]
        with mock.patch.object(sr, "ENTETE_RAPPORT", [entete]), mock.patch.object(sr, "SOUS_SECTIONS_EQUIPE", [equipe]), \
                mock.patch.object(sr, "SECTIONS_FINALES", [finale]):
            self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual(appels, ["entete", "equipe", "equipe", "finale"])
        texte = self.rapport()
        self.assertLess(texte.index("LIGNE D'ENTETE"), texte.index(f"## {ALPHA}"))
        self.assertLess(texte.index(f"SOUS-SECTION {ALPHA}"), texte.index(f"## {BETA}"))
        self.assertGreater(texte.index("SECTION FINALE"), texte.index(f"SOUS-SECTION {BETA}"))


class Refus(EspaceRapport):
    def test_nom_de_serie_invalide_en_code_2_sans_fichier(self):
        for nom in ("../evasion", "a/b", "avec espace", "", ".cache", "x" * 80):
            with self.subTest(nom=nom):
                code, sortie, erreur = self.lancer("report", "--name", nom, "--language", "en")
                self.assertEqual((code, sortie), (2, ""))
                self.assertIn("Usage error", erreur)
        self.assertEqual(self.fichiers(), [])
        self.assertEqual(self.vues_lues, [])

    def test_sans_nom_de_serie_usage(self):
        self.assertEqual(self.lancer("report")[0], 2)

    def test_vues_illisibles_en_code_1_sans_fichier(self):
        with mock.patch.object(sr, "lire_vue", side_effect=RuntimeError("zz secret de la base")):
            code, sortie, erreur = self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual((code, sortie), (1, ""))
        self.assertIn("database error, nothing is written: RuntimeError", erreur)
        self.assertNotIn("zz secret", erreur)
        self.assertEqual(self.fichiers(), [])

    def test_base_injoignable_en_code_1(self):
        class ErreurBase(Exception):
            pass
        with mock.patch.object(sr, "lire_vue", side_effect=ErreurBase("mot de passe zz")):
            code, _, erreur = self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("database unreachable or password missing", erreur)
        self.assertNotIn("zz", erreur)

    def test_reglages_illisibles_en_code_1(self):
        from yaml_strict import ErreurConfig
        with mock.patch.object(sr, "reglages_rapport", side_effect=ErreurConfig("flux.yaml : trou")):
            code, _, erreur = self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("unreadable settings", erreur)

    def test_socle_absent_en_code_3(self):
        self.socle.unlink()
        code, _, erreur = self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual((code, erreur.strip()), (3, "core grid missing"))
        self.assertEqual(self.fichiers(), [])


if __name__ == "__main__":
    unittest.main()
