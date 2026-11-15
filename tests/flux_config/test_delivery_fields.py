"""tools/flux_config.py : réglage delivery_fields (table des champs de livraison de Jira, R-20261114-108, même logique que A-92).

Les identifiants réels des champs de livraison ne sont plus dans le code publié : ils viennent du bloc `delivery_fields` de
Flux-Lab/flux.yaml (hors Git). Bloc facultatif, SANS identifiant par défaut : un réglage absent donne un dictionnaire vide (les champs de
livraison ne sont alors ni demandés, ni lus, ni stockés ; l'export et la collecte le disent). Refus avec chemin de clé et ligne, sans
la valeur. Données inventées (table_factice) ; aucun accès à Flux-Lab/.
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "flow_delivery"))
import flux_config  # noqa: E402
import table_factice  # noqa: E402
from yaml_strict import ErreurConfig, charger  # noqa: E402


def lire(texte: str) -> dict:
    return flux_config.to_internal(charger(texte))


class TestDeliveryFields(unittest.TestCase):
    def test_clef_connue_et_inchangee(self):
        self.assertIn("delivery_fields", flux_config.INCHANGEES)

    def test_absent_donne_un_dictionnaire_vide_sans_identifiant_par_defaut(self):
        self.assertEqual(flux_config.delivery_fields(lire("jira_site: x\n")), {})

    def test_table_complete_lue_telle_quelle(self):
        lu = flux_config.delivery_fields(lire(table_factice.yaml()))
        self.assertEqual(lu, table_factice.TABLE)

    def test_la_table_factice_couvre_tout_le_schema(self):
        """Détecte un écart entre la table des tests et le schéma du validateur (source unique : flux_config)."""
        self.assertEqual(set(table_factice.TABLE), set(flux_config.DELIVERY_FIELDS_SCALAIRES) | set(flux_config.DELIVERY_FIELDS_GROUPES))
        for groupe, noms in flux_config.DELIVERY_FIELDS_GROUPES.items():
            self.assertEqual(set(table_factice.TABLE[groupe]), set(noms), groupe)

    def test_table_partielle_admise(self):
        lu = flux_config.delivery_fields(lire("delivery_fields:\n  sprint: customfield_99001\n  assets:\n    target: customfield_99002\n"))
        self.assertEqual(lu, {"sprint": "customfield_99001", "assets": {"target": "customfield_99002"}})

    def test_bloc_vide_admis_et_neutre(self):
        self.assertEqual(flux_config.delivery_fields(lire("delivery_fields: {}\n")), {})

    def test_pas_un_bloc_refuse_avec_chemin_et_ligne(self):
        for texte in ("delivery_fields: customfield_99001\n", "delivery_fields: [customfield_99001]\n"):
            with self.assertRaises(ErreurConfig) as c:
                lire("jira_site: x\n" + texte)
            self.assertIn("delivery_fields", str(c.exception))
            self.assertIn("L2", str(c.exception))

    def test_cle_inconnue_refusee_et_valeur_jamais_citee(self):
        for texte in ("delivery_fields:\n  inconnue: customfield_99777\n",
                      "delivery_fields:\n  assets:\n    inconnue: customfield_99777\n"):
            with self.assertRaises(ErreurConfig) as c:
                lire(texte)
            self.assertIn("delivery_fields", str(c.exception))
            self.assertNotIn("99777", str(c.exception))

    def test_valeur_qui_n_est_pas_un_identifiant_refusee_sans_la_valeur(self):
        for valeur in ("''", "7", "[customfield_99777]", "champ-zz-777", "Zz Champ 777", "customfield_", "99001"):
            for texte in (f"delivery_fields:\n  sprint: {valeur}\n", f"delivery_fields:\n  flags:\n    customer_commitment: {valeur}\n"):
                with self.subTest(texte=texte):
                    with self.assertRaises(ErreurConfig) as c:
                        lire(texte)
                    self.assertIn("delivery_fields", str(c.exception))
                    self.assertIn("identifiant de champ Jira", str(c.exception))
                    self.assertNotIn("777", str(c.exception))

    def test_groupe_qui_n_est_pas_un_bloc_refuse(self):
        with self.assertRaises(ErreurConfig) as c:
            lire("delivery_fields:\n  assets: customfield_99002\n")
        self.assertIn("delivery_fields.assets", str(c.exception))

    def test_meme_identifiant_deux_fois_refuse_sans_la_valeur(self):
        texte = "delivery_fields:\n  sprint: customfield_99555\n  assets:\n    target: customfield_99555\n"
        with self.assertRaises(ErreurConfig) as c:
            lire(texte)
        self.assertIn("delivery_fields.assets.target", str(c.exception))
        self.assertNotIn("99555", str(c.exception))


if __name__ == "__main__":
    unittest.main()
