"""
Tests de `story_quality.py patient-lift`, de la porte de suspension de `analyse` et `coach` et du contrôle avant envoi (change
patient-data-detection, tâches 4.1 à 4.5, spec story-quality-analysis et story-quality-patient-data). Faux magasin, faux moteur, fausse clé,
textes inventés ; aucune base, aucun réseau.
"""
from __future__ import annotations

import unittest

from aide_patient import (ETIQUETTE, NOM, NUMERO_DOSSIER, NUMERO_LOCAL, TEXTE_P5, TEXTE_PROPRE, EspacePatient, pd)

SUSPENDU = "analysis suspended: patient-data check not lifted"
RETENU = "held back, patient data detected: 1 items"


class Levee(EspacePatient):
    def passage(self, **options):
        """Un passage réel de `patient-scan` sur le magasin du test."""
        code, sortie, erreur = self.lancer("patient-scan", **options)
        self.assertEqual(code, 0, erreur)

    def test_categorie_trouvee_et_non_acceptee(self):
        self.avec(2, description="Patient ID: 4821973 saisi")
        self.passage()
        self.sans_levee()
        code, sortie, erreur = self.lancer("patient-lift", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("lift refused: categories found and not accepted: P2", erreur)
        self.assertEqual(self.analyse.levees, [])
        self.assertEqual(self.invites_levee, [])               # refusée avant toute question
        self.assertIn("P2 patient identifier: found", sortie)

    def test_categorie_acceptee_et_mot_de_confirmation(self):
        self.avec(2, description=TEXTE_P5)
        self.passage()
        self.sans_levee()
        code, sortie, erreur = self.lancer("patient-lift", "--accept", "P5", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("suspension lifted: analysis may resume", sortie.splitlines())
        self.assertEqual(len(self.analyse.levees), 1)
        levee = self.analyse.levees[0]
        self.assertEqual((levee["accepted"], levee["detector_version"], levee["labels_fingerprint"]), (["P5"], pd.DETECTOR_VERSION, None))
        self.assertEqual(levee["run_id"], self.analyse.passages[-1]["id"])
        self.assertEqual(self.invites_levee, ["Lift the analysis suspension? Type yes to confirm: "])

    def test_les_drapeaux_du_dernier_passage_sont_affiches(self):
        self.avec(2, description=TEXTE_P5)
        self.passage()
        _, sortie, _ = self.lancer("patient-lift", "--accept", "P5", "--language", "en")
        self.assertIn("P5 patient name: found", sortie.splitlines())
        self.assertIn("P1 social security number: none", sortie.splitlines())

    def test_aucune_detection_se_leve_sans_categorie(self):
        self.propre(3)
        self.passage()
        self.sans_levee()
        code, sortie, _ = self.lancer("patient-lift")
        self.assertEqual(code, 0)
        self.assertIn("suspension levée : l'analyse peut reprendre", sortie)
        self.assertEqual(self.analyse.levees[0]["accepted"], [])

    def test_reponse_autre_que_le_mot_de_confirmation(self):
        self.propre(3)
        self.passage()
        self.sans_levee()
        for reponse in ("non", "", "oui ", None):
            code, sortie, erreur = self.lancer("patient-lift", "--language", "en", reponse=reponse)
            if reponse == "oui ":
                continue
            self.assertEqual(code, 0, erreur)
            self.assertIn("lift not recorded", sortie, reponse)
        self.assertEqual(self.analyse.levees, [])

    def test_ancienne_version_du_detecteur(self):
        self.propre(3)
        self.analyse.enregistrer_detection(pd.DETECTOR_VERSION - 1, None, {"story": 3}, dict.fromkeys(pd.CATEGORIES, False))
        self.sans_levee()
        code, sortie, erreur = self.lancer("patient-lift", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("lift refused: no detection at the current detector and list version", erreur)
        self.assertEqual(self.analyse.levees, [])

    def test_autre_liste_facultative(self):
        self.propre(3)
        self.passage()                                          # passage sans liste
        self.sans_levee()
        self.etiquettes(ETIQUETTE)                              # la liste change : le passage n'est plus à jour
        code, _, erreur = self.lancer("patient-lift", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("lift refused: no detection at the current detector and list version", erreur)
        self.assertNotIn(ETIQUETTE, erreur)

    def test_aucun_passage_enregistre(self):
        self.sans_levee()
        code, _, erreur = self.lancer("patient-lift", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("lift refused: no detection at the current detector and list version", erreur)

    def test_code_inconnu_refuse_avec_le_code_2(self):
        self.propre(3)
        self.passage()
        for code_inconnu in ("P0", "P10", "p5", "ZZ"):
            code, sortie, erreur = self.lancer("patient-lift", "--accept", code_inconnu, "--language", "en")
            self.assertEqual(code, 2, code_inconnu)
            self.assertIn("Usage error: --accept", erreur)
        self.assertEqual(len(self.analyse.levees), 1)           # celle du montage : rien n'a été ajouté
        self.assertEqual(self.ouvertures_patient, 1)            # le scan seulement

    def test_pas_de_terminal(self):
        self.propre(3)
        self.passage()
        self.sans_levee()
        code, _, erreur = self.lancer("patient-lift", "--language", "en", terminal=False)
        self.assertEqual(code, 3)
        self.assertIn("confirmation needs a terminal", erreur)
        self.assertEqual(self.analyse.levees, [])

    def test_erreur_de_la_base_a_l_enregistrement(self):
        self.propre(3)
        self.passage()
        self.sans_levee()

        def echec(*a, **k):
            raise RuntimeError("zzdetail-de-la-base")
        self.analyse.enregistrer_levee = echec
        code, sortie, erreur = self.lancer("patient-lift", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("database error, nothing is written: RuntimeError", erreur)
        self.assertNotIn("zzdetail", sortie + erreur)
        self.assertEqual(self.analyse.levees, [])

    def test_accepter_plusieurs_categories(self):
        self.avec(2, description=f"{TEXTE_P5}. {NUMERO_DOSSIER}")
        self.passage()
        self.sans_levee()
        code, _, _ = self.lancer("patient-lift", "--accept", "P5", "--accept", "P3", "--accept", "P5")
        self.assertEqual(code, 0)
        self.assertEqual(self.analyse.levees[0]["accepted"], ["P3", "P5"])
        code, _, erreur = self.lancer("patient-lift", "--accept", "P5", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("categories found and not accepted: P3", erreur)


class Porte(EspacePatient):
    def setUp(self):
        super().setUp()
        self.remplir(3)

    def verifier_ferme(self, resultat, requetes=0):
        code, sortie, erreur = resultat
        self.assertEqual(code, 3, sortie + erreur)
        self.assertIn(SUSPENDU, erreur)
        self.assertEqual(len(self.moteur.requetes), requetes)
        self.assertIsNone(self.service_demande)                  # avant la lecture de la clé
        self.assertEqual(self.invites, [])
        self.assertEqual(self.analyse.ecritures, 0)

    def test_aucune_levee_enregistree(self):
        self.sans_levee()
        self.verifier_ferme(self.lancer("analyse", "--language", "en"))

    def test_donnees_trouvees_apres_la_levee(self):
        self.lever()
        self.trouver("P1")
        self.verifier_ferme(self.lancer("coach", "--team", "Equipe Zzalpha", "--language", "en"))

    def test_une_categorie_acceptee_ne_ferme_pas_la_porte(self):
        self.lever("P5")
        self.trouver("P5")
        code, sortie, erreur = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(len(self.moteur.requetes), 3)

    def test_une_categorie_non_acceptee_ferme_la_porte_meme_si_une_autre_l_est(self):
        self.lever("P5")
        self.trouver("P5", "P3")
        self.verifier_ferme(self.lancer("analyse", "--language", "en"))

    def test_levee(self):
        code, sortie, erreur = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("batch: 3 items", sortie)
        self.assertEqual(len(self.invites), 1)
        self.assertEqual(len(self.moteur.requetes), 3)
        self.assertEqual(self.service_demande, "service-fictif")

    def test_version_du_detecteur_changee(self):
        self.lever(version=pd.DETECTOR_VERSION - 1)
        self.verifier_ferme(self.lancer("analyse", "--language", "en"))

    def test_liste_facultative_changee(self):
        self.etiquettes(ETIQUETTE)                               # la levée du montage est celle d'une liste absente
        self.verifier_ferme(self.lancer("analyse", "--language", "en"))
        self.lever(empreinte=pd.labels_fingerprint([ETIQUETTE]))
        code, _, erreur = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 0, erreur)

    def test_l_echantillon_et_le_coaching_par_cles_sont_suspendus_aussi(self):
        self.sans_levee()
        self.verifier_ferme(self.lancer("analyse", "--sample", "2", "--language", "en"))
        self.verifier_ferme(self.lancer("coach", "--keys", "ZZA-001", "--language", "en"))
        self.verifier_ferme(self.lancer("coach", "--team", "Equipe Zzalpha", "--language", "en"))

    def test_la_session_est_refusee_avant_la_porte(self):
        self.sans_levee()
        code, _, erreur = self.lancer("analyse", environ={**self.environ, "CLAUDECODE": "1"})
        self.assertEqual(code, 3)
        self.assertIn("Refusé dans une session Claude Code", erreur)
        self.assertEqual(self.ouvertures_analyse, 0)

    def test_le_code_d_une_erreur_de_la_base_a_la_porte_est_1(self):
        def echec():
            raise RuntimeError("zzdetail")
        self.analyse.derniere_levee = echec
        code, sortie, erreur = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("database error, nothing is written: RuntimeError", erreur)
        self.assertNotIn("zzdetail", sortie + erreur)

    def test_aucune_option_ne_saute_la_porte(self):
        self.sans_levee()
        for argv in (("analyse", "--no-gate"), ("analyse", "--force"), ("coach", "--team", "x", "--skip-patient-check")):
            self.assertEqual(self.lancer(*argv)[0], 2, argv)


class EssaiEtAffichage(EspacePatient):
    def setUp(self):
        super().setUp()
        self.remplir(3)
        self.sans_levee()

    def test_essai_de_l_audit_pendant_la_suspension(self):
        code, sortie, erreur = self.lancer("analyse", "--dry-run", "--language", "en")
        self.assertEqual(code, 0, erreur)
        lignes = sortie.splitlines()
        self.assertTrue(any(l.startswith("batch: 3 items") for l in lignes))
        self.assertIn(SUSPENDU, lignes)
        self.assertLess(lignes.index("dry run: nothing sent"), lignes.index(SUSPENDU))
        self.assertEqual((self.moteur.requetes, self.service_demande, self.analyse.ecritures), ([], None, 0))

    def test_essai_du_coaching_pendant_la_suspension(self):
        code, sortie, erreur = self.lancer("coach", "--team", "Equipe Zzalpha", "--dry-run", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn(SUSPENDU, sortie.splitlines())
        self.assertEqual(self.moteur.requetes, [])

    def test_essai_de_l_echantillon_pendant_la_suspension(self):
        code, sortie, _ = self.lancer("analyse", "--sample", "2", "--dry-run", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn(SUSPENDU, sortie.splitlines())

    def test_pas_de_phrase_quand_la_porte_est_ouverte(self):
        self.lever()
        code, sortie, _ = self.lancer("analyse", "--dry-run", "--language", "en")
        self.assertEqual(code, 0)
        self.assertNotIn(SUSPENDU, sortie)

    def test_l_affichage_du_retour_enregistre_n_est_jamais_suspendu(self):
        self.analyse.coaching["ZZA-001"] = [("story-un", "met", "Conseil enregistré")]
        code, sortie, erreur = self.lancer("coach", "--keys", "ZZA-001", "--show", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("Conseil enregistré", sortie)
        self.assertNotIn(SUSPENDU, sortie + erreur)


class ControleAvantEnvoi(EspacePatient):
    def lever_p5(self):
        self.lever("P5")

    def test_numero_de_dossier_residuel_retenu_dans_l_audit(self):
        self.avec(2, description=TEXTE_PROPRE)
        self.analyse.ajouter("ZZA-500", (self.equipe_a,), "story", titre="Titre propre", description=NUMERO_DOSSIER, criteres="")
        code, sortie, erreur = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn(RETENU, sortie.splitlines())
        self.assertEqual(len(self.moteur.requetes), 2)
        for texte in self.moteur.textes():
            self.assertNotIn("556677", texte)
        self.assertNotIn("ZZA-500", self.analyse.audites())
        self.assertIn("batch: 2 items", sortie)
        self.assertIn("analysis done: 2 items", sortie)

    def test_p5_accepte_reste_retenu(self):
        self.lever_p5()
        self.avec(2, description=TEXTE_PROPRE)
        self.analyse.ajouter("ZZA-500", (self.equipe_a,), "story", titre="Titre propre", description=TEXTE_P5, criteres="")
        code, sortie, erreur = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn(RETENU, sortie.splitlines())
        self.assertEqual(len(self.moteur.requetes), 2)
        self.assertNotIn(NOM, "".join(self.moteur.textes()))
        self.assertNotIn("ZZA-500", self.analyse.audites())

    def test_chacun_des_trois_textes_est_controle(self):
        for champ in ("titre", "description", "criteres"):
            with self.subTest(champ=champ):
                self.analyse.items.clear()
                self.analyse.contenus.clear()
                self.analyse.ajouter("ZZA-500", (self.equipe_a,), "story", **{
                    "titre": "Titre propre", "description": "", "criteres": "", champ: NUMERO_DOSSIER})
                self.moteur.requetes.clear()
                code, sortie, erreur = self.lancer("analyse", "--language", "en")
                self.assertEqual(code, 0, erreur)
                self.assertEqual(self.moteur.requetes, [])
                self.assertIn(RETENU, sortie.splitlines())

    def test_le_coaching_retient_aussi(self):
        self.avec(1, description=TEXTE_PROPRE)
        self.analyse.ajouter("ZZA-500", (self.equipe_a,), "story", titre="Titre propre", description=NUMERO_DOSSIER, criteres="")
        code, sortie, erreur = self.lancer("coach", "--keys", "ZZA-100", "ZZA-500", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn(RETENU, sortie.splitlines())
        self.assertEqual(len(self.moteur.requetes), 1)
        self.assertNotIn("ZZA-500", self.analyse.coaching)
        self.assertNotIn("ZZA-500", sortie)

    def test_l_echantillon_retient_aussi(self):
        self.analyse.ajouter("ZZA-500", (self.equipe_a,), "story", titre="Titre propre", description=NUMERO_DOSSIER, criteres="")
        code, sortie, erreur = self.lancer("analyse", "--sample", "1", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(self.moteur.requetes, [])
        self.assertIn(RETENU, sortie.splitlines())
        self.assertEqual(self.analyse.verdicts, [])

    def test_tous_les_elements_retenus_pas_de_question(self):
        self.avec(3, description=NUMERO_DOSSIER)
        code, sortie, erreur = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("held back, patient data detected: 3 items", sortie.splitlines())
        self.assertEqual((self.invites, self.moteur.requetes), ([], []))
        self.assertIn("analysis done: 0 items", sortie)

    def test_la_phrase_ne_porte_ni_cle_ni_equipe_ni_texte(self):
        self.avec(1, description=f"{NUMERO_DOSSIER} {TEXTE_P5}")
        _, sortie, erreur = self.lancer("analyse", "--language", "en")
        for interdit in ("ZZA-", "Zzalpha", "556677", NOM):
            self.assertNotIn(interdit, sortie + erreur)

    def test_la_liste_facultative_vaut_pour_le_controle(self):
        self.etiquettes(ETIQUETTE)
        self.lever(empreinte=pd.labels_fingerprint([ETIQUETTE]))
        self.avec(1, description=TEXTE_PROPRE)
        self.analyse.ajouter("ZZA-500", (self.equipe_a,), "story", titre="Titre propre", description=NUMERO_LOCAL, criteres="")
        code, sortie, erreur = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn(RETENU, sortie.splitlines())
        self.assertEqual(len(self.moteur.requetes), 1)
        self.assertNotIn(ETIQUETTE, sortie + erreur)

    def test_un_element_propre_est_envoye_comme_avant(self):
        self.avec(2, description=TEXTE_PROPRE)
        code, sortie, erreur = self.lancer("analyse", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertNotIn("held back", sortie)
        self.assertEqual(len(self.moteur.requetes), 2)

    equipe_a = "Equipe Zzalpha"


if __name__ == "__main__":
    unittest.main()
