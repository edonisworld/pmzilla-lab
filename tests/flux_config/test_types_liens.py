"""tools/flux_config.py : lecteur partagé des types de liens (change flow-definitions-loader, tâche 2.3, conception D2 ; spec jira-flow-config,
exigence « The link type defaults are read through one shared reader »).

Les défauts sont les deux constantes TYPES_BLOQUANTS_PAR_DEFAUT et TYPES_ATTENTE_PAR_DEFAUT ; le lecteur rend les bloquants d'abord, puis les
types d'attente qui ne sont pas déjà bloquants, chaque liste sans doublon de casse (première occurrence gardée). Le rapport des dépendances
tient les mêmes constantes (identité, pas égalité de copies). Noms de types inventés.

    bash tests/run_all.sh flux_config
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import dependencies_jira  # noqa: E402
import flux_config  # noqa: E402


class TypesLiens(unittest.TestCase):
    def test_sans_cle_les_deux_defauts(self):
        self.assertEqual(flux_config.types_liens({}),
                         (list(flux_config.TYPES_BLOQUANTS_PAR_DEFAUT), list(flux_config.TYPES_ATTENTE_PAR_DEFAUT)))
        self.assertIsInstance(flux_config.TYPES_BLOQUANTS_PAR_DEFAUT, tuple)
        self.assertIsInstance(flux_config.TYPES_ATTENTE_PAR_DEFAUT, tuple)

    def test_listes_des_reglages(self):
        self.assertEqual(flux_config.types_liens({"types_bloquants": ["T-B1", " T-B2 "], "types_attente": ["T-A1"]}),
                         (["T-B1", "T-B2"], ["T-A1"]))

    def test_une_cle_donnee_et_l_autre_absente(self):
        self.assertEqual(flux_config.types_liens({"types_bloquants": ["T-B1"]}),
                         (["T-B1"], list(flux_config.TYPES_ATTENTE_PAR_DEFAUT)))
        self.assertEqual(flux_config.types_liens({"types_attente": ["T-A1"]}),
                         (list(flux_config.TYPES_BLOQUANTS_PAR_DEFAUT), ["T-A1"]))

    def test_liste_vide_donnee_remplace_le_defaut_comme_le_rapport(self):
        self.assertEqual(flux_config.types_liens({"types_bloquants": [], "types_attente": []}), ([], []))

    def test_type_dans_les_deux_listes_gardé_une_fois_comme_bloquant(self):
        self.assertEqual(flux_config.types_liens({"types_bloquants": ["T-Les-Deux", "T-B"], "types_attente": ["t-LES-deux", "T-A"]}),
                         (["T-Les-Deux", "T-B"], ["T-A"]))

    def test_doublons_de_casse_une_fois_premiere_occurrence_gardee(self):
        self.assertEqual(flux_config.types_liens({"types_bloquants": ["T-B", "t-b", "T-C"], "types_attente": ["T-A", "T-a"]}),
                         (["T-B", "T-C"], ["T-A"]))

    def test_les_defauts_ne_sont_pas_modifies_par_le_lecteur(self):
        avant = (tuple(flux_config.TYPES_BLOQUANTS_PAR_DEFAUT), tuple(flux_config.TYPES_ATTENTE_PAR_DEFAUT))
        flux_config.types_liens({"types_bloquants": ["T-Les-Deux"], "types_attente": ["T-Les-Deux"]})
        self.assertEqual((flux_config.TYPES_BLOQUANTS_PAR_DEFAUT, flux_config.TYPES_ATTENTE_PAR_DEFAUT), avant)

    def test_le_rapport_des_dependances_tient_les_memes_constantes(self):
        self.assertIs(dependencies_jira.DEFAULTS["types_bloquants"], flux_config.TYPES_BLOQUANTS_PAR_DEFAUT)
        self.assertIs(dependencies_jira.DEFAULTS["types_attente"], flux_config.TYPES_ATTENTE_PAR_DEFAUT)

    def test_le_rapport_classe_comme_le_lecteur(self):
        reglages = {"types_bloquants": ["T-Les-Deux", "T-B"], "types_attente": ["t-les-deux", "T-A"]}
        bloquants, attente = flux_config.types_liens(reglages)
        for nom in bloquants:
            self.assertEqual(dependencies_jira.role(nom, reglages), "bloque")
        for nom in attente:
            self.assertEqual(dependencies_jira.role(nom, reglages), "attend")


if __name__ == "__main__":
    unittest.main()
