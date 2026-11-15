"""
Tests de `story_quality.py patient-scan`, porté par tools/story_quality_patient.py et tools/patient_data.py (change patient-data-detection, tâches 3.3 à 3.6 et 5.1, spec story-quality-patient-data).

Faux magasin, faux moteur, réglages et textes inventés ; aucune base, aucun réseau, aucune clé. Les chaînes « zz » et les noms-sentinelles
sont distinctifs : un test qui les retrouve dans une sortie prouve que l'outil écrit ce qu'il ne doit pas écrire.
"""
from __future__ import annotations

import json
import unittest

from aide_analyse import BLOC, SERVICE_CLE
from aide_patient import (ETIQUETTE, NOM, NUMERO_DOSSIER, NUMERO_LOCAL, SENTINELLES, TEXTE_P5, EspacePatient, pd)

SESSION = {"CLAUDECODE": "1"}


class Scan(EspacePatient):
    def test_entete_avec_le_nombre_d_elements_lus(self):
        self.propre(12)
        code, sortie, erreur = self.lancer("patient-scan", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.splitlines()[0], "patient-data detection (local, nothing sent): 12 items read")

    def test_entete_en_francais_par_defaut(self):
        self.propre(12)
        code, sortie, _ = self.lancer("patient-scan")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.splitlines()[0], "détection de données de patient (locale, rien n'est envoyé) : 12 éléments lus")
        self.assertIn("P5 nom de patient : story", sortie)

    def test_la_ligne_de_champ(self):
        self.propre(2)
        self.avec(6, description=NUMERO_DOSSIER)
        code, sortie, _ = self.lancer("patient-scan", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("P3 by field: title 0, description 6, criteria 0", sortie.splitlines())
        self.assertIn("P3 stay or record number: story 6", sortie)

    def test_zero_affiche_et_aucun_total_de_ligne_ni_de_colonne(self):
        self.propre(8)
        _, sortie, _ = self.lancer("patient-scan", "--language", "en")
        self.assertIn("P1 social security number: story 0", sortie.splitlines())
        self.assertIn("P9 health fact tied to a patient: story 0", sortie.splitlines())
        self.assertIn("held back by the pre-send check: story 0", sortie.splitlines())
        self.assertNotIn("total", sortie.lower())
        self.assertNotIn("masked", sortie)

    def test_trois_stories_avec_un_nom_de_patient_et_aucune_epic(self):
        self.propre(6)
        self.avec(3, description=TEXTE_P5)
        self.analyse.ajouter("ZZA-900", genre="epic", titre="Titre d'epic", description="", criteres="")
        _, sortie, _ = self.lancer("patient-scan", "--language", "en")
        ligne = next(l for l in sortie.splitlines() if l.startswith("P5 "))
        self.assertEqual(ligne, "P5 patient name: story masked, epic 0 (expected noise)")

    def test_p5_marque_et_ligne_des_retenus_par_p5(self):
        self.propre(2)
        self.avec(7, description=TEXTE_P5)
        _, sortie, _ = self.lancer("patient-scan", "--language", "en")
        lignes = sortie.splitlines()
        self.assertIn("P5 patient name: story 7 (expected noise)", lignes)
        self.assertIn("held back by the pre-send check: story 7", lignes)
        self.assertIn("of which held back by P5: story 7", lignes)
        self.assertEqual([l for l in lignes if "(expected noise)" in l], ["P5 patient name: story 7 (expected noise)"])

    def test_ordre_des_lignes(self):
        self.propre(6)
        self.analyse.ajouter("ZZA-900", genre="epic", titre="Titre d'epic", description="", criteres="")
        lignes = self.lancer("patient-scan", "--language", "en")[1].splitlines()
        indices = [next(i for i, l in enumerate(lignes) if l.startswith(debut)) for debut in (
            "patient-data detection", "optional list absent", "story: ", "epic: ", "P1 ", "P9 ", "P1 by field", "P9 by field",
            "held back by", "of which held back", "detection recorded", "suspension lifted")]
        self.assertEqual(indices, sorted(indices))
        self.assertEqual(len(set(indices)), len(indices))

    def test_l_etat_de_la_suspension_est_la_derniere_ligne(self):
        self.propre(6)
        self.sans_levee()
        derniere = self.lancer("patient-scan", "--language", "en")[1].splitlines()[-1]
        self.assertEqual(derniere, "analysis suspended: lift with patient-lift after a detection")
        self.lever()
        derniere = self.lancer("patient-scan", "--language", "en")[1].splitlines()[-1]
        self.assertRegex(derniere, r"^suspension lifted on 2026-01-01, detector version 1, accepted categories: none$")

    def test_les_elements_sortis_de_la_collecte_sont_lus_aussi(self):
        self.propre(6)
        self.analyse.items["ZZA-001"]["out_of_collection_at"] = "sorti"
        _, sortie, _ = self.lancer("patient-scan", "--language", "en")
        self.assertIn("6 items read", sortie.splitlines()[0])

    def test_un_genre_masque_masque_aussi_le_total_de_l_entete(self):
        self.propre(12)
        self.analyse.ajouter("ZZA-900", genre="epic", titre="Titre d'epic", description="", criteres="")
        sortie = self.lancer("patient-scan", "--language", "en")[1]
        self.assertEqual(sortie.splitlines()[0], "patient-data detection (local, nothing sent): masked items read")
        self.assertIn("epic: masked items read", sortie)
        self.assertIn("story: 12 items read", sortie)
        self.assertNotIn("13", sortie)

    def test_liste_facultative_absente(self):
        self.propre(6)
        code, sortie, _ = self.lancer("patient-scan", "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.splitlines()[1], "optional list absent")

    def test_liste_facultative_presente_etend_p2_et_n_apparait_nulle_part(self):
        self.etiquettes(ETIQUETTE)
        self.propre(2)
        self.avec(5, description=NUMERO_LOCAL)
        code, sortie, erreur = self.lancer("patient-scan", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("P2 patient identifier: story 5", sortie.splitlines())
        self.assertNotIn("optional list absent", sortie)
        self.assertNotIn(ETIQUETTE, sortie + erreur)
        code, doc, erreur = self.document()
        self.assertEqual(code, 0)
        self.assertTrue(doc["labels_list_present"])
        self.assertNotIn(ETIQUETTE, json.dumps(doc) + erreur)

    def test_sans_la_liste_la_meme_etiquette_ne_compte_pas(self):
        self.propre(2)
        self.avec(5, description=NUMERO_LOCAL)
        _, sortie, _ = self.lancer("patient-scan", "--language", "en")
        self.assertIn("P2 patient identifier: story 0", sortie.splitlines())

    def test_une_liste_illisible_arrete_avec_le_code_1_sans_rien_enregistrer(self):
        self.ecrire_reglages(bloc=BLOC.format(service=SERVICE_CLE, plafond=self.PLAFOND) + "patient_id_labels: pas-une-liste\n")
        code, sortie, erreur = self.lancer("patient-scan", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("patient_id_labels", erreur)
        self.assertNotIn("pas-une-liste", sortie + erreur)
        self.assertEqual((self.analyse.passages, self.ouvertures_patient), ([], 0))

    def test_aucune_sentinelle_ni_cle_ni_equipe_dans_la_sortie(self):
        self.etiquettes(ETIQUETTE)
        for i in range(1, 9):
            self.analyse.ajouter(f"ZZA-{i:03d}", (f"Equipe Zzalpha",), "story",
                                 titre=f"Patient {NOM} titre {i}", description=f"{NUMERO_DOSSIER} {NUMERO_LOCAL}",
                                 criteres=f"Mme {NOM} critères")
        for argv in (("patient-scan", "--language", "en"), ("patient-scan", "--language", "fr"), ("patient-scan", "--json")):
            code, sortie, erreur = self.lancer(*argv)
            self.assertEqual(code, 0, erreur)
            for sentinelle in SENTINELLES + ("Equipe Zzalpha", "Zzalpha"):
                self.assertNotIn(sentinelle, sortie + erreur, f"{argv} : {sentinelle}")

    def test_aucune_ecriture_de_fichier(self):
        self.propre(6)
        self.lancer("patient-scan")
        self.assertEqual(self.nouveaux, set())


class ScanJson(EspacePatient):
    def test_cellule_masquee_structuree(self):
        self.propre(6)
        self.avec(2, description=NUMERO_DOSSIER, genre="epic")
        code, doc, erreur = self.document()
        self.assertEqual(code, 0, erreur)
        self.assertEqual(self.cellule(doc, "P3", "epic"), {"kind": "epic", "value": None, "masked": True, "reason": "under_threshold"})
        self.assertEqual(self.cellule(doc, "P3", "story"), {"kind": "story", "value": 0, "masked": False, "reason": None})

    def test_la_sortie_standard_ne_porte_que_le_document(self):
        self.propre(6)
        code, sortie, erreur = self.lancer("patient-scan", "--json", "--language", "en")
        self.assertEqual(code, 0)
        doc = json.loads(sortie)                          # tout le contenu de la sortie standard est le document
        self.assertEqual((doc["contract"], doc["contract_version"]), ("patient_data_scan", 1))
        self.assertIn("optional list absent", erreur)
        self.assertIn("detection recorded: detector version 1", erreur)

    def test_forme_du_contrat(self):
        self.propre(6)
        _, doc, _ = self.document()
        self.assertEqual(doc["detector_version"], pd.DETECTOR_VERSION)
        self.assertFalse(doc["labels_list_present"])
        self.assertTrue(doc["scanned_at"].startswith("2026-01-01"))
        self.assertEqual([k["kind"] for k in doc["kinds"]], ["story"])
        self.assertEqual([c["code"] for c in doc["categories"]], list(pd.CATEGORIES))
        self.assertEqual([c["expected_noise"] for c in doc["categories"]], [c == "P5" for c in pd.CATEGORIES])
        self.assertEqual([f["field"] for f in doc["categories"][0]["by_field"]], ["title", "description", "acceptance_criteria"])
        self.assertEqual(doc["held_back"], [{"kind": "story", "value": 0, "masked": False, "reason": None}])
        self.assertEqual(doc["held_back_p5"], doc["held_back"])
        self.assertEqual(doc["suspension"], {"state": "lifted", "lifted_at": doc["suspension"]["lifted_at"],
                                             "lift_detector_version": pd.DETECTOR_VERSION, "accepted_categories": []})

    def test_suspension_suspendue_sans_levee(self):
        self.propre(6)
        self.sans_levee()
        _, doc, _ = self.document()
        self.assertEqual(doc["suspension"], {"state": "suspended", "lifted_at": None, "lift_detector_version": None,
                                             "accepted_categories": []})

    def test_les_cellules_de_cinq_et_plus_sont_affichees(self):
        self.propre(2)
        self.avec(5, description=NUMERO_DOSSIER)
        _, doc, _ = self.document()
        self.assertEqual(self.cellule(doc, "P3", "story")["value"], 5)
        self.assertFalse(self.cellule(doc, "P3", "story")["masked"])

    def test_le_seuil_est_celui_des_vues_releve_par_le_reglage(self):
        self.ecrire_reglages(bloc=BLOC.format(service=SERVICE_CLE, plafond=self.PLAFOND))
        with open(self.flux / "flux.yaml", "a", encoding="utf-8") as f:
            f.write("flow_views_min_cell: 8\n")
        self.propre(2)
        self.avec(6, description=NUMERO_DOSSIER)
        _, doc, _ = self.document()
        self.assertTrue(self.cellule(doc, "P3", "story")["masked"])          # 6 < 8 : masqué au seuil relevé


class PassageEnregistre(EspacePatient):
    def test_un_passage_est_enregistre_sans_compte_ni_texte(self):
        self.propre(2)
        self.avec(5, description=f"{NUMERO_DOSSIER}. {TEXTE_P5}", titre="Titre propre")
        code, sortie, _ = self.lancer("patient-scan", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("detection recorded: detector version 1", sortie.splitlines())
        self.assertEqual(len(self.analyse.passages), 1)
        passage = self.analyse.passages[0]
        self.assertEqual(passage["detector_version"], pd.DETECTOR_VERSION)
        self.assertIsNone(passage["labels_fingerprint"])
        self.assertEqual(passage["items_read"], {"story": 7})
        self.assertEqual(passage["found"], {c: c in ("P3", "P5") for c in pd.CATEGORIES})
        self.assertTrue(all(isinstance(v, bool) for v in passage["found"].values()))
        for sentinelle in SENTINELLES:
            self.assertNotIn(sentinelle, repr(passage))

    def test_l_empreinte_de_la_liste_est_enregistree_pas_la_liste(self):
        self.etiquettes(ETIQUETTE)
        self.propre(3)
        self.lancer("patient-scan")
        passage = self.analyse.passages[0]
        self.assertEqual(passage["labels_fingerprint"], pd.labels_fingerprint([ETIQUETTE]))
        self.assertNotIn(ETIQUETTE, repr(passage))

    def test_une_erreur_de_la_base_n_enregistre_rien_et_ne_dit_que_le_type(self):
        self.propre(3)

        def echec(*a, **k):
            raise RuntimeError("zzdetail-de-la-base")
        self.analyse.enregistrer_detection = echec
        code, sortie, erreur = self.lancer("patient-scan", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("database error, nothing is written: RuntimeError", erreur)
        self.assertNotIn("zzdetail", sortie + erreur)
        self.assertEqual(self.analyse.passages, [])
        self.assertFalse(self.analyse.ouvert)                 # le magasin est fermé

    def test_une_erreur_a_la_lecture_de_la_levee_n_enregistre_aucun_passage(self):
        self.propre(3)

        def echec(*a, **k):
            raise RuntimeError("zzdetail-de-la-base")
        self.analyse.derniere_levee = echec
        code, sortie, erreur = self.lancer("patient-scan", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("database error, nothing is written: RuntimeError", erreur)
        self.assertNotIn("zzdetail", sortie + erreur)
        self.assertEqual(self.analyse.passages, [])           # la levée est lue avant l'enregistrement du passage (D9)
        self.assertFalse(self.analyse.ouvert)

    def test_une_base_injoignable_donne_le_code_1(self):
        self.propre(3)
        self.injoignable = True
        code, sortie, erreur = self.lancer("patient-scan", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("database unreachable or password missing: nothing is read or written", erreur)
        self.assertEqual((sortie, self.analyse.passages), ("", []))

    def test_sans_reseau_le_scan_se_termine_et_le_moteur_ne_recoit_rien(self):
        self.propre(6)
        code, sortie, erreur = self.lancer_sans_reseau("patient-scan", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("items read", sortie)
        self.assertEqual(self.moteur.requetes, [])
        self.assertIsNone(self.service_demande)              # la clé d'analyse n'est pas lue


class RefusEnSession(EspacePatient):
    def test_patient_scan_refuse_dans_une_session_avant_toute_lecture(self):
        self.propre(6)
        for argv in (("patient-scan",), ("patient-scan", "--json", "--language", "en")):
            code, sortie, erreur = self.lancer(*argv, environ={**self.environ, **SESSION})
            self.assertEqual(code, 3, argv)
            self.assertIn("Refused inside a Claude Code session" if "en" in argv else "Refusé dans une session Claude Code", erreur)
            self.assertEqual(sortie, "")
        self.assertEqual((self.ouvertures_patient, self.analyse.passages), (0, []))

    def test_patient_lift_refuse_dans_une_session_avant_toute_lecture(self):
        self.propre(6)
        self.lever()
        for argv in (("patient-lift",), ("patient-lift", "--accept", "P5", "--language", "en")):
            code, sortie, erreur = self.lancer(*argv, environ={**self.environ, **SESSION})
            self.assertEqual(code, 3, argv)
            self.assertIn("Refused inside a Claude Code session" if "en" in argv else "Refusé dans une session Claude Code", erreur)
            self.assertEqual(sortie, "")
        self.assertEqual(self.ouvertures_patient, 0)
        self.assertEqual(len(self.analyse.levees), 1)
        self.assertEqual(self.invites_levee, [])

    def test_aucune_option_ne_contourne_le_refus(self):
        for argv in (("patient-scan", "--force"), ("patient-lift", "--session"), ("patient-scan", "--language", "de")):
            code, _, erreur = self.lancer(*argv, environ={**self.environ, **SESSION})
            self.assertEqual(code, 2, argv)


if __name__ == "__main__":
    unittest.main()
