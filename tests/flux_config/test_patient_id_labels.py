"""tools/flux_config.py : réglage facultatif patient_id_labels (étiquettes d'identifiant de patient propres à l'organisation, change
patient-data-detection, design D10).

Liste de chaînes non vide ; un réglage absent donne None (jamais une erreur). Refus avec chemin de clé et ligne, sans la valeur. Données
inventées ; aucun accès à Flux-Lab/."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flux_config  # noqa: E402
from yaml_strict import ErreurConfig, charger  # noqa: E402


def lire(texte: str) -> dict:
    return flux_config.to_internal(charger(texte))


class TestPatientIdLabels(unittest.TestCase):
    def test_clef_connue_et_inchangee(self):
        self.assertIn("patient_id_labels", flux_config.INCHANGEES)

    def test_absent_donne_none(self):
        self.assertIsNone(flux_config.patient_id_labels(lire("jira_site: x\n")))

    def test_liste_lue(self):
        self.assertEqual(flux_config.patient_id_labels(lire("patient_id_labels: [zzun, ' zzdeux ']\n")), ["zzun", "zzdeux"])

    def test_pas_une_liste_refuse_avec_chemin_et_ligne_sans_la_valeur(self):
        with self.assertRaises(ErreurConfig) as c:
            lire("jira_site: x\npatient_id_labels: ZzValeurDistinctive\n")
        m = str(c.exception)
        self.assertIn("patient_id_labels", m)
        self.assertIn("L2", m)
        self.assertNotIn("ZzValeurDistinctive", m)

    def test_element_non_chaine_ou_vide_refuse_sans_valeur(self):
        for texte in ("patient_id_labels: [zzun, 4242]\n", "patient_id_labels: []\n", "patient_id_labels: ['  ']\n"):
            with self.subTest(texte=texte):
                with self.assertRaises(ErreurConfig) as c:
                    lire(texte)
                self.assertNotIn("4242", str(c.exception))


if __name__ == "__main__":
    unittest.main()
