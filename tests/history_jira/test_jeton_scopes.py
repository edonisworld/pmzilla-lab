"""Séquence d'authentification du jeton à droits limités (« scoped ») de history_jira.py, sur le faux serveur de test_history_jira.py.

    uv run --with requests --with pyyaml python -m unittest discover -s tests/history_jira -v

- la séquence complète des appels : cloudId lu sur le site (sans authentification), puis appel authentifié par api.atlassian.com ;
- un jeton refusé donne le code HTTP seul, sans cloudId, site, compte ni jeton ;
- un cloudId inexploitable arrête le script avec un message, avant tout appel authentifié.
Aucun appel réseau réel : le serveur est local et le jeton inventé.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import test_history_jira as base  # noqa: E402


class SequenceScopes(base.Base):
    def setUp(self):
        super().setUp()
        self.ecrire_reglages("scopes")

    def test_sequence_complete_des_appels(self):
        code, sortie = self.lancer("test")
        self.assertEqual((code, sortie.strip()), (0, "connexion OK"))
        # d'abord le cloudId lu sur le site, puis un seul appel de recherche (le préfixe /ex/jira/<cloudId> est retiré par le faux)
        self.assertEqual(self.faux.appels, [("GET", "/_edge/tenant_info"), ("GET", "/rest/api/3/search/jql")])

    def test_cloud_id_lu_sans_authentification(self):
        vus = []
        original = base.hj.Client.requete

        def espion(client, methode, chemin, **kwargs):
            vus.append((client.base, chemin, client.auth is not None))
            return original(client, methode, chemin, **kwargs)

        with mock.patch.object(base.hj.Client, "requete", espion):
            code, _ = self.lancer("test")
        self.assertEqual(code, 0)
        self.assertEqual(len(vus), 2, vus)
        self.assertEqual(vus[0], (self.url, "/_edge/tenant_info", False))               # sur le site, sans authentification
        self.assertEqual(vus[1][0], f"{self.url}/ex/jira/{base.CLOUD_ID}")             # puis api.atlassian.com/ex/jira/<cloudId>
        self.assertTrue(vus[1][2])

    def test_jeton_refuse_donne_le_code_seul(self):
        self.faux.attendu = "Basic autre"
        code, sortie = self.lancer("test")
        self.assertEqual((code, sortie.strip()), (1, "HTTP 401"))
        for interdit in ("Nom Fictif", self.url, base.EMAIL, base.JETON, base.CLOUD_ID, "Traceback"):
            self.assertNotIn(interdit, sortie)
        # le cloudId a été lu, l'appel authentifié a échoué, et rien n'a été réessayé
        self.assertEqual(self.faux.appels, [("GET", "/_edge/tenant_info")])

    def test_cloud_id_inexploitable(self):
        for infos in ({}, {"cloudId": ""}, {"cloudId": "a/../b"}):
            with self.subTest(infos=infos), mock.patch.object(base.hj.Client, "json", return_value=infos):
                self.faux.appels.clear()
                code, sortie = self.lancer("test")
                self.assertEqual(code, 1)
                self.assertIn("cloudId introuvable", sortie)
                self.assertNotIn("Traceback", sortie)
                self.assertEqual(self.faux.appels, [])          # aucun appel authentifié


if __name__ == "__main__":
    unittest.main()
