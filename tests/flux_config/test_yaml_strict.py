"""tools/yaml_strict.py : une clé écrite deux fois dans un fichier YAML de configuration est refusée, avec les deux lignes.

Données inventées ; aucun accès à Flux-Lab/."""
import sys
import unittest
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
from yaml_strict import ErreurConfig, charger  # noqa: E402


class CleEcriteDeuxFois(unittest.TestCase):
    def refus(self, texte: str, source: str = "flux.yaml") -> str:
        with self.assertRaises(ErreurConfig) as c:
            charger(texte, source)
        return str(c.exception)

    def test_premier_niveau_avec_les_deux_numeros_de_ligne(self):
        message = self.refus("projets_exclus: [A]\netats_a_faire: [X]\nprojets_exclus: [B]\n")
        self.assertEqual(message, "flux.yaml : « projets_exclus » est écrite deux fois (L1 et L3) ; supprimer l'une des deux lignes.")

    def test_le_nom_du_fichier_est_celui_qui_est_donne(self):
        self.assertTrue(self.refus("a: 1\na: 2\n", "tri.yaml").startswith("tri.yaml : "))

    def test_sous_cle_avec_son_chemin(self):
        message = self.refus("colonnes:\n  etat: [S]\n  cle: [K]\n  etat: [S2]\n")
        self.assertIn("« colonnes.etat » est écrite deux fois (L2 et L4)", message)

    def test_cle_dans_une_liste_de_series(self):
        message = self.refus("tableaux:\n  series:\n    - nom: a\n      base: b\n      nom: c\n")
        self.assertIn("« tableaux.series.nom » est écrite deux fois (L3 et L5)", message)

    def test_la_meme_cle_dans_deux_blocs_differents_est_permise(self):
        donnees = charger("a:\n  nom: 1\nb:\n  nom: 2\nliste:\n  - nom: x\n  - nom: y\n")
        self.assertEqual(donnees, {"a": {"nom": 1}, "b": {"nom": 2}, "liste": [{"nom": "x"}, {"nom": "y"}]})

    def test_le_message_ne_montre_aucune_valeur(self):
        self.assertNotIn("Secret", self.refus("jira_email: SecretA\njira_email: SecretB\n"))

    def test_la_cle_ecrite_entre_guillemets_compte_comme_la_meme(self):
        self.assertIn("(L1 et L2)", self.refus("'a': 1\na: 2\n"))

    def test_une_valeur_repetee_n_est_pas_une_cle(self):
        self.assertEqual(charger("a: [x, x]\nb: x\nc: x\n"), {"a": ["x", "x"], "b": "x", "c": "x"})

    def test_une_surcharge_par_merge_n_est_pas_un_doublon(self):
        donnees = charger("base: &b {x: 1, y: 2}\nautre:\n  <<: *b\n  x: 9\n")
        self.assertEqual(donnees["autre"], {"x": 9, "y": 2})


class MemeResultatQueSafeLoad(unittest.TestCase):
    TEXTE = "# commentaire\njira_site: https://exemple.atlassian.net\ncolonnes:\n  type: [Issue Type]\nliste: [1, 2]\nvide:\nnul: null\n"

    def test_meme_dictionnaire(self):
        self.assertEqual(charger(self.TEXTE), yaml.safe_load(self.TEXTE))

    def test_texte_vide_ou_commentaires_seuls(self):
        self.assertIsNone(charger(""))
        self.assertIsNone(charger("# rien\n"))

    def test_erreur_de_syntaxe_reste_une_erreur_yaml(self):
        with self.assertRaises(yaml.YAMLError):
            charger("a: [1, 2\n")

    def test_les_numeros_de_ligne_de_chaque_cle(self):
        donnees = charger("a: 1\n\nb:\n  c: 2\n  d: 3\n")
        self.assertEqual(donnees.lignes, {"a": 1, "b": 3})
        self.assertEqual(donnees["b"].lignes, {"c": 4, "d": 5})

    def test_safe_dump_ecrit_un_dictionnaire_lu_comme_un_dict_ordinaire(self):
        donnees = charger("a: 1\nb:\n  c: 2\n")
        self.assertEqual(yaml.safe_dump(donnees, sort_keys=False), yaml.safe_dump({"a": 1, "b": {"c": 2}}, sort_keys=False))

    def test_erreur_config_traverse_except_exception(self):
        """Elle hérite de SystemExit : les `except Exception` des scripts ne la masquent pas."""
        self.assertTrue(issubclass(ErreurConfig, SystemExit))
        self.assertFalse(issubclass(ErreurConfig, Exception))


if __name__ == "__main__":
    unittest.main()
