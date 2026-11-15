"""
`adopt-n` de tools/version_photo.py (change version-quality-photo, tâches 3.2 et 3.3 ; spec jira-flow-version-photo : N adopté avec une trace,
une adoption ultérieure exige une raison). Magasin en mémoire : aucune base.
"""
import copy
import unittest

from aide_version_photo import Espace, MagasinMemoire, vp

PREMIERE = ("adopt-n", "--weeks", "6", "--adopted-on", "2026-11-20")
SECONDE = ("adopt-n", "--weeks", "8", "--adopted-on", "2026-12-01")


class PremiereAdoption(Espace):
    def test_ajoute_une_adoption_et_le_dit(self):
        magasin = MagasinMemoire()
        code, sortie, erreur, _, _ = self.lancer(*PREMIERE, "--language", "en", magasin=magasin)
        self.assertEqual((code, erreur), (0, ""))
        self.assertEqual(sortie.splitlines(), ["N adopted: 6 weeks, on 2026-11-20"])
        self.assertEqual(len(magasin.etat["adoptions"]), 1)
        self.assertEqual(magasin.etat["adoptions"][0]["weeks"], 6)
        self.assertEqual(str(magasin.etat["adoptions"][0]["adopted_on"]), "2026-11-20")

    def test_francais_par_defaut(self):
        _, sortie, _, _, _ = self.lancer(*PREMIERE)
        self.assertEqual(sortie.splitlines(), ["N adopté : 6 semaines, le 2026-11-20"])

    def test_ne_lit_aucun_reglage(self):
        self.reglages.unlink()
        environ = {k: v for k, v in self.environ.items() if k != "VERSION_PHOTO_SETTINGS"}
        environ["PMZILLA_LAB_WORKSPACE"] = "/inexistant"                         # une lecture de réglage échouerait
        code, _, _, _, ouvertures = self.lancer(*PREMIERE, environ=environ)
        self.assertEqual((code, ouvertures), (0, 1))

    def test_une_premiere_adoption_accepte_une_raison_et_ne_la_dit_pas(self):
        magasin = MagasinMemoire()
        _, sortie, _, _, _ = self.lancer(*PREMIERE, "--reason", "zzraison", "--language", "en", magasin=magasin)
        self.assertNotIn("warning", sortie)
        self.assertNotIn("zzraison", sortie)
        self.assertEqual(magasin.etat["adoptions"][0]["reason"], "zzraison")

    def test_n_positif_entier_seulement(self):
        for valeur in ("0", "-3", "abc", "2.5", ""):
            code, sortie, _, magasin, ouvertures = self.lancer("adopt-n", "--weeks", valeur, "--adopted-on", "2026-11-20")
            self.assertEqual((code, sortie, ouvertures), (2, "", 0), valeur)
            self.assertEqual(magasin.etat["adoptions"], [])

    def test_date_illisible_ou_absente(self):
        for argv in (("adopt-n", "--weeks", "6", "--adopted-on", "20-11-2026"), ("adopt-n", "--weeks", "6", "--adopted-on", "2026-13-40"),
                     ("adopt-n", "--weeks", "6"), ("adopt-n", "--adopted-on", "2026-11-20")):
            code, _, _, magasin, ouvertures = self.lancer(*argv)
            self.assertEqual((code, ouvertures), (2, 0), argv)
            self.assertEqual(magasin.etat["adoptions"], [])


class AdoptionUlterieure(Espace):
    def test_sans_raison_refusee_sans_rien_ecrire(self):
        magasin = MagasinMemoire()
        self.lancer(*PREMIERE, magasin=magasin)
        avant = copy.deepcopy(magasin.etat)
        code, sortie, _, _, _ = self.lancer(*SECONDE, "--language", "en", magasin=magasin)
        self.assertEqual(code, 3)
        self.assertEqual(sortie.splitlines(), ["N already adopted: give --reason"])
        self.assertEqual(magasin.etat, avant)
        self.assertEqual(len(magasin.etat["adoptions"]), 1)

    def test_sans_raison_ou_raison_vide_en_francais(self):
        magasin = MagasinMemoire()
        self.lancer(*PREMIERE, magasin=magasin)
        for options in ((), ("--reason", ""), ("--reason", "   ")):
            code, sortie, _, _, _ = self.lancer(*SECONDE, *options, magasin=magasin)
            self.assertEqual(code, 3, options)
            self.assertEqual(sortie.splitlines(), ["N déjà adopté : donner --reason"])
        self.assertEqual(len(magasin.etat["adoptions"]), 1)

    def test_avec_raison_avertit_puis_adopte_et_ne_dit_pas_la_raison(self):
        magasin = MagasinMemoire()
        self.lancer(*PREMIERE, magasin=magasin)
        code, sortie, erreur, _, _ = self.lancer(*SECONDE, "--reason", "zzraison de la seconde adoption", "--language", "en", magasin=magasin)
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.splitlines(), ["warning: N modified after a first adoption, shown in the view",
                                               "N adopted: 8 weeks, on 2026-12-01"])
        self.assertNotIn("zz", sortie + erreur)
        self.assertEqual(magasin.etat["adoptions"][1]["reason"], "zzraison de la seconde adoption")

    def test_avertissement_en_francais(self):
        magasin = MagasinMemoire()
        self.lancer(*PREMIERE, magasin=magasin)
        _, sortie, _, _, _ = self.lancer(*SECONDE, "--reason", "r", magasin=magasin)
        self.assertEqual(sortie.splitlines(), ["avertissement : N modifié après une première adoption, signalé dans la vue",
                                               "N adopté : 8 semaines, le 2026-12-01"])

    def test_le_registre_garde_les_deux_lignes_et_le_dernier_n_est_effectif(self):
        magasin = MagasinMemoire()
        self.lancer(*PREMIERE, magasin=magasin)
        self.lancer(*SECONDE, "--reason", "r", magasin=magasin)
        self.assertEqual([a["weeks"] for a in magasin.etat["adoptions"]], [6, 8])
        self.assertEqual([str(a["adopted_on"]) for a in magasin.etat["adoptions"]], ["2026-11-20", "2026-12-01"])
        self.assertEqual(magasin.etat["adoptions"][-1]["weeks"], 8)                                  # la dernière adoption est la valeur effective

    def test_une_troisieme_adoption_exige_encore_une_raison(self):
        magasin = MagasinMemoire()
        self.lancer(*PREMIERE, magasin=magasin)
        self.lancer(*SECONDE, "--reason", "r", magasin=magasin)
        code, _, _, _, _ = self.lancer("adopt-n", "--weeks", "7", "--adopted-on", "2026-12-15", magasin=magasin)
        self.assertEqual(code, 3)
        self.assertEqual(len(magasin.etat["adoptions"]), 2)


class GardeDuMasquageDesCroisements(Espace):
    """Change masking-sums, D9 : tant que le marqueur `flow.masking_version()` est absent ou inférieur à la version attendue, `adopt-n`
    refuse, code 3, sans rien écrire : les croisements équipes x versions de la photo ne sont pas encore masqués. Version égale ou supérieure :
    adoption écrite (les versions du marqueur sont croissantes)."""

    def test_refus_sans_le_marqueur_en_anglais_et_rien_n_est_ecrit(self):
        magasin = MagasinMemoire(marqueur=None)
        avant = copy.deepcopy(magasin.etat)
        code, sortie, erreur, _, ouvertures = self.lancer(*PREMIERE, "--language", "en", magasin=magasin)
        self.assertEqual((code, erreur, ouvertures), (3, "", 1))
        self.assertEqual(sortie.splitlines(), [vp.CATALOGS["en"]["crossing_masking_missing"]])
        self.assertIn("R-144", sortie)
        self.assertIn("masking of team x version crossings", sortie)
        self.assertEqual(magasin.etat, avant)
        self.assertEqual(magasin.etat["adoptions"], [])

    def test_refus_en_francais_avec_la_raison_nommee(self):
        magasin = MagasinMemoire(marqueur=None)
        code, sortie, _, _, _ = self.lancer(*PREMIERE, magasin=magasin)
        self.assertEqual(code, 3)
        self.assertEqual(sortie.splitlines(), [vp.CATALOGS["fr"]["crossing_masking_missing"]])
        self.assertIn("masquage des croisements", sortie)
        self.assertIn("R-144", sortie)

    def test_refus_meme_avec_une_raison_et_une_adoption_deja_faite(self):
        magasin = MagasinMemoire()
        self.lancer(*PREMIERE, magasin=magasin)
        magasin.marqueur = None
        code, sortie, _, _, _ = self.lancer(*SECONDE, "--reason", "r", "--language", "en", magasin=magasin)
        self.assertEqual((code, sortie.splitlines()), (3, [vp.CATALOGS["en"]["crossing_masking_missing"]]))
        self.assertEqual(len(magasin.etat["adoptions"]), 1)

    def test_refus_quand_le_marqueur_est_inferieur_a_la_version_attendue_et_rien_n_est_ecrit(self):
        magasin = MagasinMemoire(marqueur=vp.VERSION_MASQUAGE_ATTENDUE - 1)
        avant = copy.deepcopy(magasin.etat)
        code, sortie, erreur, _, _ = self.lancer(*PREMIERE, "--language", "en", magasin=magasin)
        self.assertEqual((code, erreur), (3, ""))
        # décision du 2026-10-28 : le refus d'une version installée trop basse nomme la version installée, la version attendue et la raison
        self.assertEqual(sortie.splitlines(), [vp.CATALOGS["en"]["crossing_masking_version"].format(
            installed=vp.VERSION_MASQUAGE_ATTENDUE - 1, expected=vp.VERSION_MASQUAGE_ATTENDUE)])
        self.assertEqual(magasin.etat, avant)

    def test_version_attendue_trois_la_version_deux_de_la_migration_0035_est_refusee_avec_le_message_explicite(self):
        """R-20261104-45 (1) : adopt-n attend la version 3 du marqueur dès le groupe 6 ; la migration 0035 pose 2 : refus, code 3, même code qu'avant,
        rien d'écrit, message en français et en anglais (N reste bloqué jusqu'aux groupes 7 et 8, échec fermé)."""
        self.assertEqual(vp.VERSION_MASQUAGE_ATTENDUE, 3)
        for langue, phrases in (("en", ("installed version 2", "expected version 3", "D15 bounds propagation not installed")),
                                ("fr", ("version installée 2", "version attendue 3", "propagation des bornes D15 non installée"))):
            with self.subTest(langue=langue):
                magasin = MagasinMemoire(marqueur=2)
                avant = copy.deepcopy(magasin.etat)
                code, sortie, erreur, _, _ = self.lancer(*PREMIERE, "--language", langue, magasin=magasin)
                self.assertEqual((code, erreur), (3, ""))
                for phrase in phrases:
                    self.assertIn(phrase, sortie)
                self.assertEqual(magasin.etat, avant)
                self.assertEqual(magasin.etat["adoptions"], [])

    def test_version_deux_refusee_avec_le_message_reel(self):
        """R-20261104-45 (1) : le marqueur 2 (migration 0035) est désormais refusé, code 3, rien d'écrit."""
        magasin = MagasinMemoire(marqueur=2)
        avant = copy.deepcopy(magasin.etat)
        code, sortie, _, _, _ = self.lancer(*PREMIERE, "--language", "en", magasin=magasin)
        self.assertEqual((code, sortie.splitlines()), (3, [vp.CATALOGS["en"]["crossing_masking_version"].format(installed=2, expected=3)]))
        self.assertEqual(magasin.etat, avant)
        self.assertEqual(magasin.etat["adoptions"], [])

    def test_version_trois_simulee_acceptee(self):
        magasin = MagasinMemoire(marqueur=3)
        code, sortie, _, _, _ = self.lancer(*PREMIERE, "--language", "en", magasin=magasin)
        self.assertEqual((code, sortie.splitlines()), (0, ["N adopted: 6 weeks, on 2026-11-20"]))
        self.assertEqual(len(magasin.etat["adoptions"]), 1)

    def test_acceptation_quand_le_marqueur_egale_la_version_attendue(self):
        magasin = MagasinMemoire(marqueur=vp.VERSION_MASQUAGE_ATTENDUE)
        code, sortie, _, _, _ = self.lancer(*PREMIERE, "--language", "en", magasin=magasin)
        self.assertEqual((code, sortie.splitlines()), (0, ["N adopted: 6 weeks, on 2026-11-20"]))
        self.assertEqual(len(magasin.etat["adoptions"]), 1)

    def test_acceptation_quand_le_marqueur_depasse_la_version_attendue(self):
        """Décision 3 du 2026-10-26 : un masquage ultérieur relève la version, il ne bloque pas de nouveau la photo."""
        magasin = MagasinMemoire(marqueur=vp.VERSION_MASQUAGE_ATTENDUE + 1)
        code, sortie, _, _, _ = self.lancer(*PREMIERE, "--language", "en", magasin=magasin)
        self.assertEqual((code, sortie.splitlines()), (0, ["N adopted: 6 weeks, on 2026-11-20"]))
        self.assertEqual(len(magasin.etat["adoptions"]), 1)

    def test_les_constantes_de_nom_de_migration_n_existent_plus(self):
        self.assertFalse(hasattr(vp, "MOTIF_MIGRATION_MASQUAGE"))
        self.assertFalse(hasattr(vp, "SQL_MASQUAGE_SOMME"))
        self.assertFalse(hasattr(vp.MagasinBase, "masquage_somme_applique"))

    def test_la_garde_ne_touche_ni_reconstruct_ni_take(self):
        magasin = MagasinMemoire(marqueur=None)
        code, _, _, _, _ = self.lancer("take", magasin=magasin)
        self.assertEqual(code, 0)


class RienNeModifieNiNeSupprime(unittest.TestCase):
    def test_aucune_requete_de_l_outil_ne_modifie_ni_ne_supprime_le_registre(self):
        requetes = {nom: valeur for nom, valeur in vars(vp).items() if nom.startswith("SQL_") and isinstance(valeur, str)}
        du_registre = {nom: v for nom, v in requetes.items() if "version_photo_n" in v}
        self.assertTrue(du_registre)
        for nom, requete in du_registre.items():
            self.assertTrue(requete.lstrip().upper().startswith(("INSERT", "SELECT")), nom)

    def test_la_raison_ne_figure_dans_aucun_message(self):
        for langue, catalogue in vp.CATALOGS.items():
            for cle, texte in catalogue.items():
                self.assertNotIn("{reason}", texte, f"{langue}/{cle}")


if __name__ == "__main__":
    unittest.main()
