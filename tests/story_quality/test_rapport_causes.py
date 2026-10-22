"""
Tests des lignes de grille, des causes probables de chaque équipe et de la chaîne du produit du rapport Markdown (change
story-quality-audit, tâches 3.18 et 3.21, design D8, D14, D15, D18, O7, O8, O9, O13 ; spec story-quality-report).

Le rapport met en forme le résultat de `report_data` (récurrence, ordre, parts) et ne calcule rien ; le masquage (sous 5, complémentaire,
secondaire de D18) vient des vues : une ligne de vue masquée est donnée ici comme la vue la rendrait (cellules None). Données inventées :
les équipes « Equipe Zzalpha », « Equipe Zzbeta » et « Equipe Zzgamma » sont des noms distinctifs.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_rapport import ALPHA, BETA, VUE_COUVERTURE, VUE_EQUIPE, VUE_PRODUIT, EspaceRapport  # noqa: E402
from aide_story_quality import DISTINCTIFS, NOM_FICTIF, SURCOUCHE  # noqa: E402
from test_donnees_rapport import GAMMA, ligne_equipe, ligne_produit  # noqa: E402

PRODUIT_EN, PRODUIT_FR = "Product chain", "Chaîne du produit"
CAUSES_EN, CAUSES_FR = "### Probable causes in the chain", "### Causes probables dans la chaîne"
NOTICE_CAUSES = "Where the chain usually produces this defect: a lead to check with the team, never a person's fault"
NOTICE_PRODUIT = ("All teams taken together, as for the product's monthly follow-up: no figure and no name per team, never a comparison "
                  "between teams")
AUCUN_EN, AUCUN_FR = "No recurrent defect at the current grid", "Aucun défaut récurrent pour la grille actuelle"


def sections(texte):
    """{titre de niveau 2: texte de la section}."""
    return {m.splitlines()[0]: m for m in re.split(r"^## ", texte, flags=re.M)[1:]}


def sous_section_causes(section, titre=CAUSES_EN):
    return section[section.index(titre):]


class LignesDeGrille(EspaceRapport):
    def test_sans_surcouche_la_forme_sans_surcouche_et_aucun_code_desactive(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        texte = self.rapport()
        self.assertIn("Grid: core 3, no organisation overlay", texte.splitlines())
        self.assertLess(texte.index("Grid: core 3"), texte.index(f"## {ALPHA}"))
        self.assertGreater(texte.index("Grid: core 3"), texte.index("Reading: a share"))
        self.assertNotIn("disabled", texte)

    def test_avec_surcouche_sa_version_et_les_codes_desactives_sans_raison_ni_identifiant(self):
        self.ecrire()
        code, sortie, erreur = self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual((code, erreur), (0, ""))
        self.assertNotIn("no organisation overlay", sortie)
        lignes = self.rapport().splitlines()
        self.assertIn("Grid: core 3, organisation overlay 2", lignes)
        self.assertIn("Core criteria disabled by the organisation rule: story-deux", lignes)
        for distinctif in DISTINCTIFS:                                          # raison, identifiant de la surcouche, résumé du produit
            self.assertNotIn(distinctif, self.rapport())

    def test_en_francais(self):
        self.ecrire()
        self.lancer("report", "--name", "serie", "--language", "fr")
        lignes = self.rapport().splitlines()
        self.assertIn("Grille : socle 3, surcouche de l'organisation 2", lignes)
        self.assertIn("Critères du socle désactivés par règle de l'organisation : story-deux", lignes)
        self.fichier.unlink()
        self.lancer("report", "--name", "serie", "--language", "fr")
        self.assertIn("Grille : socle 3, sans surcouche de l'organisation", self.rapport().splitlines())

    def test_un_critere_de_la_surcouche_porte_la_marque_regle_de_l_organisation(self):
        self.ecrire()
        self.vues["quality_by_team"] = VUE_EQUIPE + [ligne_equipe(ALPHA, "story", "orga-role", "ticket_template", 20, 5, 10, 5, None,
                                                                  "organisation_rule")]
        self.lancer("report", "--name", "serie", "--language", "en")
        alpha = sections(self.rapport())[ALPHA]
        self.assertIn("- orga-role | Named role (organisation rule) | share met: 5/20", alpha)
        self.assertIn("- orga-role | Named role (organisation rule) | share not met: 10/20 | link: ticket template", alpha)
        self.assertIn("- story-un | Label story-un | share met: 6/20", alpha)               # un critère du socle sans marque
        self.lancer("report", "--name", "serie", "--language", "fr")
        alpha = sections(self.rapport())[ALPHA]
        self.assertIn("- orga-role | Rôle nommé (règle de l'organisation) | part satisfaite : 5/20", alpha)

    def test_une_surcouche_refusee_arrete_en_code_3_sans_fichier_ni_lecture_des_vues(self):
        self.ecrire(SURCOUCHE.replace("Rôle nommé\n", f"{NOM_FICTIF}\n", 1))
        code, sortie, erreur = self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual((code, sortie), (3, ""))
        self.assertIn("organisation overlay refused", erreur)
        self.assertNotIn(NOM_FICTIF, erreur)
        self.assertEqual((self.fichiers(), self.vues_lues), ([], []))

    def test_une_surcouche_invalide_arrete_en_code_3(self):
        self.ecrire("version: deux\n")
        code, _, erreur = self.lancer("report", "--name", "serie", "--json", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("organisation overlay invalid", erreur)
        self.assertEqual(self.vues_lues, [])


class CausesProbablesParEquipe(EspaceRapport):
    def test_la_sous_section_ferme_la_section_de_chaque_equipe_avec_sa_notice(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        s = sections(self.rapport())
        for equipe in (ALPHA, BETA):
            lignes = sous_section_causes(s[equipe]).splitlines()
            self.assertEqual(lignes[:3], [CAUSES_EN, "", NOTICE_CAUSES])
            self.assertNotIn("### ", "\n".join(lignes[1:]))                    # dernière sous-section de l'équipe

    def test_une_ligne_par_critere_au_seuil_avec_part_non_satisfaite_denominateur_et_maillon(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        s = sections(self.rapport())
        self.assertIn("- story-un | Label story-un | share not met: 9/20 | link: ticket template", sous_section_causes(s[ALPHA]))
        self.assertIn("- story-un | Label story-un | share not met: 17/30 | link: ticket template", sous_section_causes(s[BETA]))

    def test_ordre_par_maillon_puis_code_jamais_par_resultat(self):
        self.vues["quality_by_team"] = [
            ligne_equipe(ALPHA, "story", "story-zz", "ticket_template", 20, 5, 10, 5, None),
            ligne_equipe(ALPHA, "story", "story-aa", "refinement", 20, 1, 14, 5, None),
            ligne_equipe(ALPHA, "story", "story-bb", "definition_of_ready", 20, 6, 9, 5, None),
            ligne_equipe(ALPHA, "epic", "epic-cc", "discovery_workflow_step", 20, 6, 9, 5, None),
            ligne_equipe(ALPHA, "story", "story-ab", "ticket_template", 20, 6, 9, 5, None)]
        self.lancer("report", "--name", "serie", "--language", "en")
        causes = sous_section_causes(sections(self.rapport())[ALPHA])
        codes = re.findall(r"^- (\S+) \|", causes, flags=re.M)
        self.assertEqual(codes, ["story-ab", "story-zz", "epic-cc", "story-bb", "story-aa"])
        self.assertIn("link: Discovery Workflow step", causes)
        self.assertIn("link: Definition of Ready", causes)
        self.assertIn("link: Refinement", causes)

    def test_aucun_defaut_recurrent_le_dit(self):
        self.reglages = (0.95, 5)
        self.lancer("report", "--name", "serie", "--language", "en")
        s = sections(self.rapport())
        for equipe in (ALPHA, BETA):
            causes = sous_section_causes(s[equipe])
            self.assertIn(AUCUN_EN, causes)
            self.assertNotIn("share not met", causes)

    def test_une_cellule_masquee_n_est_jamais_recurrente(self):
        self.reglages = (0.0, 5)                 # tout compte lisible serait récurrent : seules les cellules masquées restent dehors
        self.lancer("report", "--name", "serie", "--language", "en")
        s = sections(self.rapport())
        self.assertNotIn("story-trois", sous_section_causes(s[ALPHA]))         # not_met masqué par la vue
        self.assertNotIn("epic-un", sous_section_causes(s[ALPHA]))
        self.assertNotIn("story-trois", sous_section_causes(s[BETA]))          # ligne entière masquée
        self.assertNotIn("masked", sous_section_causes(s[ALPHA]) + sous_section_causes(s[BETA]))

    def test_en_francais(self):
        self.lancer("report", "--name", "serie", "--language", "fr")
        causes = sous_section_causes(sections(self.rapport())[ALPHA], CAUSES_FR)
        self.assertIn("Là où la chaîne produit d'ordinaire ce défaut : une piste à vérifier avec l'équipe, jamais la faute d'une personne",
                      causes)
        self.assertIn("- story-un | Libellé story-un | part non satisfaite : 9/20 | maillon : modèle de ticket", causes)
        self.reglages = (0.95, 5)
        self.lancer("report", "--name", "serie", "--language", "fr")
        self.assertIn(AUCUN_FR, sous_section_causes(sections(self.rapport())[ALPHA], CAUSES_FR))


class GardeAntiComparaisonDesCauses(EspaceRapport):
    def test_une_sous_section_ne_porte_que_les_chiffres_de_son_equipe(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        s = sections(self.rapport())
        alpha, beta = sous_section_causes(s[ALPHA]), sous_section_causes(s[BETA])
        self.assertNotIn("17/30", alpha)
        self.assertNotIn("9/20", beta)
        for texte in (alpha, beta):
            self.assertNotIn(BETA if texte is alpha else ALPHA, texte)

    def test_aucune_ligne_entre_equipes_ni_compte_d_equipes(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        texte = self.rapport()
        for ligne in texte.splitlines():
            self.assertFalse(ALPHA in ligne and BETA in ligne, ligne)
        bas = texte.lower()
        for mot in ("2 teams", "two teams", "teams share", "total", "score", "rank:", "ranking:"):
            self.assertNotIn(mot, bas)

    def test_une_seule_part_par_ligne_de_cause(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        for ligne in self.rapport().splitlines():
            if "share not met" in ligne:
                self.assertEqual(len(re.findall(r"\d+/\d+|<\d+", ligne)), 1, ligne)

    def test_le_rapport_est_identique_quel_que_soit_l_ordre_des_lignes(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        premier = self.rapport()
        self.vues = {vue: lignes[::-1] for vue, lignes in self.vues.items()}
        self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual(self.rapport(), premier)

    def test_des_resultats_echanges_echangent_les_sous_sections_sans_changer_l_ordre(self):
        echange = lambda lignes: [dict(l, team=BETA if l["team"] == ALPHA else ALPHA) for l in lignes]
        self.vues["quality_by_team"] = echange(VUE_EQUIPE)
        self.vues["quality_coverage_by_team"] = echange(VUE_COUVERTURE)
        self.lancer("report", "--name", "serie", "--language", "en")
        s = sections(self.rapport())
        self.assertEqual(list(s), [ALPHA, BETA, PRODUIT_EN])
        self.assertIn("share not met: 17/30", sous_section_causes(s[ALPHA]))
        self.assertIn("share not met: 9/20", sous_section_causes(s[BETA]))


class ChaineDuProduit(EspaceRapport):
    def test_la_section_suit_la_derniere_equipe_avec_sa_notice_et_ses_lignes(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        texte = self.rapport()
        self.assertEqual(re.findall(r"^## (.*)$", texte, flags=re.M), [ALPHA, BETA, PRODUIT_EN])
        lignes = sections(texte)[PRODUIT_EN].splitlines()
        self.assertEqual(lignes[:3], [PRODUIT_EN, "", NOTICE_PRODUIT])
        self.assertIn("- story-un | Label story-un | share not met: 26/50 | link: ticket template", lignes)

    def test_en_francais(self):
        self.lancer("report", "--name", "serie", "--language", "fr")
        produit = sections(self.rapport())[PRODUIT_FR]
        self.assertIn("Toutes équipes réunies, comme le suivi mensuel du produit : aucun chiffre ni nom par équipe, jamais une comparaison "
                      "entre équipes", produit)
        self.assertIn("- story-un | Libellé story-un | part non satisfaite : 26/50 | maillon : modèle de ticket", produit)

    def test_aucun_defaut_recurrent_du_produit_le_dit(self):
        self.vues["quality_by_product"] = [ligne_produit("story", "story-un", "ticket_template", 50, 40, 5, 5, None)]
        self.lancer("report", "--name", "serie", "--language", "en")
        produit = sections(self.rapport())[PRODUIT_EN]
        self.assertIn(AUCUN_EN, produit)
        self.assertNotIn("share not met", produit)

    def test_lue_de_la_vue_produit_jamais_de_la_somme_des_equipes(self):
        # vue produit vide : aucune ligne, bien que les deux équipes aient story-un récurrent
        self.vues["quality_by_product"] = []
        self.lancer("report", "--name", "serie", "--language", "en")
        self.assertIn(AUCUN_EN, sections(self.rapport())[PRODUIT_EN])
        # un élément de deux équipes compte une fois : 21 au produit, pas 9 + 17
        self.vues["quality_by_product"] = [ligne_produit("story", "story-un", "ticket_template", 45, 15, 21, 9, None)]
        self.lancer("report", "--name", "serie", "--language", "en")
        produit = sections(self.rapport())[PRODUIT_EN]
        self.assertIn("share not met: 21/45", produit)
        self.assertNotIn("26/", produit)

    def test_une_cellule_de_produit_masquee_n_est_jamais_recurrente_ni_estimee(self):
        self.reglages = (0.0, 5)
        self.vues["quality_by_product"] = [ligne_produit("story", "story-un", "ticket_template", 50, 14, None, None, None)]
        self.lancer("report", "--name", "serie", "--language", "en")
        produit = sections(self.rapport())[PRODUIT_EN]
        self.assertNotIn("story-un", produit)
        self.assertNotIn("masked", produit)
        self.assertIn(AUCUN_EN, produit)

    def test_masquage_secondaire_une_seule_cellule_d_equipe_masquee_masque_la_ligne(self):
        # Une seule cellule d'équipe masquée pour story-trois (Beta) : la vue produit masque la ligne entière (D18) ; le rapport la lit.
        self.reglages = (0.0, 5)
        self.vues["quality_by_product"] = [ligne_produit("story", "story-trois", "definition_of_ready", None, None, None, None, None)]
        self.lancer("report", "--name", "serie", "--language", "en")
        self.assertNotIn("story-trois", sections(self.rapport())[PRODUIT_EN])

    def test_masquage_secondaire_deux_cellules_d_equipe_masquees_laissent_la_ligne(self):
        self.vues["quality_by_team"] = VUE_EQUIPE + [ligne_equipe(GAMMA, "story", "story-trois", "definition_of_ready", 12, 7, None, None, None)]
        self.vues["quality_by_product"] = [ligne_produit("story", "story-trois", "definition_of_ready", 57, 20, 27, 10, None)]
        self.lancer("report", "--name", "serie", "--language", "en")
        self.assertIn("- story-trois | Label story-trois | share not met: 27/57 | link: Definition of Ready",
                      sections(self.rapport())[PRODUIT_EN])

    def test_ordre_par_maillon_puis_code(self):
        self.vues["quality_by_product"] = [ligne_produit("story", "story-b", "refinement", 20, 5, 15, 5, None),
                                           ligne_produit("story", "story-a", "refinement", 20, 5, 15, 5, None),
                                           ligne_produit("epic", "epic-a", "ticket_template", 20, 5, 15, 5, None)]
        self.lancer("report", "--name", "serie", "--language", "en")
        self.assertEqual(re.findall(r"^- (\S+) \|", sections(self.rapport())[PRODUIT_EN], flags=re.M), ["epic-a", "story-a", "story-b"])

    def test_aucun_nom_d_equipe_aucune_part_par_equipe_aucun_compte_d_equipes(self):
        self.lancer("report", "--name", "serie", "--language", "en")
        produit = sections(self.rapport())[PRODUIT_EN]
        for interdit in (ALPHA, BETA, "Zzalpha", "Zzbeta", "9/20", "17/30"):
            self.assertNotIn(interdit, produit)
        self.assertEqual(re.findall(r"\d+/\d+", produit), ["26/50"])
        self.assertNotRegex(produit.lower(), r"\d+ teams?\b")

    def test_un_critere_de_la_surcouche_porte_sa_marque_dans_la_chaine(self):
        self.ecrire()
        self.vues["quality_by_product"] = [ligne_produit("epic", "orga-objectif", "discovery_workflow_step", 30, 10, 15, 5, None,
                                                         "organisation_rule")]
        self.lancer("report", "--name", "serie", "--language", "en")
        self.assertIn("- orga-objectif | Linked objective (organisation rule) | share not met: 15/30 | link: Discovery Workflow step",
                      sections(self.rapport())[PRODUIT_EN])

    def test_un_rapport_sans_ligne_garde_la_section_du_produit_vide(self):
        self.vues = {vue: [] for vue in self.vues}
        self.lancer("report", "--name", "serie", "--language", "en")
        texte = self.rapport()
        self.assertIn("No results in the story quality views", texte)
        self.assertIn(AUCUN_EN, sections(texte)[PRODUIT_EN])


if __name__ == "__main__":
    unittest.main()
