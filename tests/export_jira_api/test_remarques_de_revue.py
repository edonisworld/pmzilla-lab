"""Remarques de la revue du team-mapping (change names-and-team-review, groupe 5, tâches 5.2 et 5.3).

    bash tests/run_all.sh export_jira_api </dev/null

Spécifications : jira-flow-export (« Line of empty cells in the Assets list refused », « Catalogue refusals in the form of the export's
refusals »). La remarque 1 (entrée du catalogue sans `type`) est dans tests/flow_organisation. Aucun appel à Jira ; données inventées,
libellés sentinelles : aucun libellé, nom ni valeur ne doit paraître dans la sortie.
"""
import contextlib
import io
import unittest

from test_equipes_commandes import Socle, REF_COMPLET, ENTETE, DEV, objet, liste
from test_catalogue_export import catalogue, entree


class LigneDeCellulesVides(Socle):
    """D8 : une ligne dont toutes les cellules sont vides est refusée par la lecture stricte, par migrate-teams et check-teams."""

    def liste_avec_ligne_vide(self, ligne=",,,,"):
        return self.ecrire("equipes-assets-complet-2026-10-16.csv",
                           ENTETE + "\n" + ",".join(objet(1)) + "\n" + ligne + "\n" + ",".join(objet(2)) + "\n")

    def test_migrate_teams_refuse_et_n_ecrit_rien(self):
        chemin = self.liste_avec_ligne_vide()
        code, sortie = self.lancer("migrate-teams", "--from-assets", str(chemin))
        self.assertEqual(code, 1, sortie)
        self.assertIn("liste Assets refusée : ligne vide à la ligne 3", sortie)
        self.assertFalse((self.flux / "equipes-jira.yaml").exists())
        self.verifier_neutre(sortie)

    def test_migrate_teams_en_anglais(self):
        chemin = self.liste_avec_ligne_vide()
        code, sortie = self.lancer("migrate-teams", "--from-assets", str(chemin), "--language", "en")
        self.assertEqual(code, 1, sortie)
        self.assertIn("assets list refused: empty line at line 3", sortie)

    def test_check_teams_refuse_la_meme_liste(self):
        self.ecrire("organisation.yaml", REF_COMPLET)
        self.liste_avec_ligne_vide()
        code, sortie = self.lancer("check-teams")
        self.assertEqual(code, 1, sortie)
        self.assertIn("liste Assets refusée : ligne vide à la ligne 3", sortie)

    def test_cellules_blanches_seulement_refusees_aussi(self):
        chemin = self.liste_avec_ligne_vide(" , ,  ,,")
        code, sortie = self.lancer("migrate-teams", "--from-assets", str(chemin))
        self.assertEqual(code, 1, sortie)
        self.assertIn("ligne vide à la ligne 3", sortie)

    def test_une_ligne_sans_aucun_separateur_reste_ignoree(self):
        chemin = self.liste_avec_ligne_vide("")
        code, sortie = self.lancer("migrate-teams", "--from-assets", str(chemin))
        self.assertEqual(code, 0, sortie)

    def test_une_ligne_a_cellules_remplies_reste_acceptee(self):
        chemin = self.ecrire("equipes-assets-complet-2026-10-16.csv", liste(objet(1), objet(2)))
        code, sortie = self.lancer("migrate-teams", "--from-assets", str(chemin))
        self.assertEqual(code, 0, sortie)


class FormeDesRefusDuCatalogue(Socle):
    """D9 : sortie d'erreur, préfixe des autres refus de l'export, guillemets droits en anglais, phrases inchangées, code 1."""

    CATALOGUE_AVEC_EFFECTIF = catalogue(entree("Libelle-Sentinelle", "'50'", "    headcount: 3\n"))

    def lancer_separe(self, *argv):
        sortant, erreur = io.StringIO(), io.StringIO()
        code = 0
        from test_export_jira_api import ex
        with contextlib.redirect_stdout(sortant), contextlib.redirect_stderr(erreur):
            try:
                ex.main(list(argv))
            except SystemExit as s:
                code = s.code
        return code, sortant.getvalue(), erreur.getvalue()

    def test_cle_inconnue_en_anglais(self):
        self.ecrire("equipes-jira.yaml", self.CATALOGUE_AVEC_EFFECTIF)
        code, sortant, erreur = self.lancer_separe("check-teams", "--language", "en")
        self.assertEqual(code, 1)
        self.assertEqual(sortant, "")
        ligne = erreur.strip()
        self.assertTrue(ligne.startswith("Error: "), erreur)
        self.assertIn('"teams[0].headcount"', ligne)
        self.assertIn("(L4)", ligne)
        self.assertNotIn("«", erreur)
        self.assertNotIn("»", erreur)
        self.verifier_neutre(erreur)

    def test_cle_inconnue_en_francais_avec_le_prefixe_et_les_guillemets_de_l_original(self):
        self.ecrire("equipes-jira.yaml", self.CATALOGUE_AVEC_EFFECTIF)
        code, sortant, erreur = self.lancer_separe("check-teams")
        self.assertEqual(code, 1)
        self.assertEqual(sortant, "")
        self.assertTrue(erreur.startswith("Erreur : "), erreur)
        self.assertIn("clé inconnue « teams[0].headcount » (L4)", erreur)

    def test_la_phrase_n_est_pas_reformulee(self):
        self.ecrire("equipes-jira.yaml", self.CATALOGUE_AVEC_EFFECTIF)
        _, _, erreur = self.lancer_separe("check-teams")
        self.assertIn("le catalogue ne décrit aucune personne et n'accepte que les clés de sa structure.", erreur)

    def test_meme_forme_pour_migrate_teams_et_review_teams(self):
        # revue 7.1 : le nom annonçait migrate-teams sans le lancer ; migrate-teams lit le référentiel (sans catalogue présent)
        self.ecrire("organisation.yaml", "source_date: 2026-10-01\nsites: [Site 1]\nmauvaise_cle: 1\n")
        liste_assets = self.liste_assets(objet(1))
        code, sortant, erreur = self.lancer_separe("migrate-teams", "--from-assets", str(liste_assets), "--language", "en")
        self.assertEqual(code, 1, sortant + erreur)
        self.assertTrue(erreur.startswith("Error: "), erreur)
        self.assertNotIn("«", erreur)
        self.assertFalse((self.flux / "equipes-jira.yaml").exists())
        self.ecrire("equipes-jira.yaml", self.CATALOGUE_AVEC_EFFECTIF)
        code, _, erreur = self.lancer_separe("review-teams", "--add", "50", "--language", "en")
        self.assertEqual(code, 1)
        self.assertTrue(erreur.startswith("Error: "), erreur)
        self.assertFalse((self.flux / "equipes-revues.yaml").exists())

    def test_refus_du_referentiel_dans_la_meme_forme(self):
        self.ecrire("organisation.yaml", "source_date: 2026-10-01\nsites: [Site 1]\nmauvaise_cle: 1\n")
        code, sortant, erreur = self.lancer_separe("check-teams", "--language", "en")
        self.assertEqual(code, 1)
        self.assertTrue(erreur.startswith("Error: "), erreur)
        self.assertNotIn("«", erreur)

    def test_aucun_refus_de_ce_genre_sur_la_sortie_standard(self):
        self.ecrire("equipes-jira.yaml", self.CATALOGUE_AVEC_EFFECTIF)
        for argv in (("check-teams",), ("check-teams", "--language", "en")):
            _, sortant, _ = self.lancer_separe(*argv)
            self.assertEqual(sortant, "")


if __name__ == "__main__":
    unittest.main()
