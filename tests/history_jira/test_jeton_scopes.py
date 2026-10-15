"""Jeton à droits limités (« scoped ») de history_jira.py, sur le faux serveur de test_history_jira.py.

    uv run --with requests --with pyyaml python -m unittest discover -s tests/history_jira -v

- la séquence complète des appels de `test` : cloudId lu sur le site (sans authentification), puis les appels authentifiés par
  la passerelle api.atlassian.com, bâtie avec le cloudId des réglages (jira_cloud_id) ;
- hors `test`, aucun appel ne lit le cloudId sur le site ; un cloudId différent de celui du site arrête `test` ;
- un jeton refusé donne le code HTTP seul, sans cloudId, site, compte ni jeton ;
- un cloudId absent ou inexploitable arrête le script avec un message, avant tout appel authentifié ;
- le mode à droits limités est le seul : jira_token_type absent donne la passerelle, « classic » est refusé avant le Trousseau ;
- la sonde de `test` (une requête par ressource, limitée à un résultat) et les lignes d'expiration du jeton.
Aucun appel réseau réel : le serveur est local et le jeton inventé.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import test_history_jira as base  # noqa: E402

AUJOURD_HUI = dt.date(2026, 10, 13)       # date figée : les lignes d'expiration ne dépendent pas de l'horloge


class SequenceScopes(base.Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(base.hj, "aujourd_hui", lambda: AUJOURD_HUI)
        p.start()
        self.addCleanup(p.stop)

    def test_sequence_complete_des_appels(self):
        code, sortie = self.lancer("test")
        self.assertEqual((code, sortie.splitlines()[0]), (0, "connexion OK"))
        # d'abord le cloudId lu sur le site, puis une requête par ressource (le préfixe /ex/jira/<cloudId> est retiré par le faux) ;
        # le ticket de l'historique est une clé de sonde : la recherche n'a rien rendu
        self.assertEqual(self.faux.appels, [("GET", "/_edge/tenant_info"), ("GET", "/rest/api/3/search/jql"),
                                            ("GET", "/rest/api/3/issue/PROJ-1/changelog"),
                                            ("GET", "/rest/api/3/field/search")])

    def test_cloud_id_lu_sans_authentification(self):
        vus = []
        original = base.hj.Client.requete

        def espion(client, methode, chemin, **kwargs):
            vus.append((client.base, chemin, client.auth is not None))
            return original(client, methode, chemin, **kwargs)

        with mock.patch.object(base.hj.Client, "requete", espion):
            code, _ = self.lancer("test")
        self.assertEqual(code, 0)
        self.assertEqual(vus[0], (self.url, "/_edge/tenant_info", False))               # sur le site, sans authentification
        self.assertFalse(self.faux.auth_sur_tenant)
        for vu in vus[1:]:                                                              # puis api.atlassian.com/ex/jira/<cloudId>
            self.assertEqual(vu[0], f"{self.url}/ex/jira/{base.CLOUD_ID}")
            self.assertTrue(vu[2])
        self.assertEqual(self.faux.hors_passerelle, [])

    def test_jeton_refuse_donne_le_code_seul(self):
        self.faux.attendu = "Basic autre"
        code, sortie = self.lancer("test")
        self.assertEqual((code, sortie.strip()), (1, "HTTP 401"))
        for interdit in ("Nom Fictif", self.url, base.EMAIL, base.JETON, base.CLOUD_ID, "Traceback", "accès", "expire"):
            self.assertNotIn(interdit, sortie)
        # le cloudId a été lu, l'appel authentifié a échoué, et rien n'a été réessayé ni sondé ensuite
        self.assertEqual(self.faux.appels, [("GET", "/_edge/tenant_info")])

    def test_collecte_sans_appel_au_site(self):
        export = self.ecrire_export(self.inventer(3))
        code, sortie = self.lancer("collect", export)
        self.assertEqual(code, 0, sortie)
        self.assertGreater(len(self.faux.appels), 0)
        self.assertNotIn(("GET", "/_edge/tenant_info"), self.faux.appels)               # aucun appel ne lit le cloudId du site
        self.assertEqual(self.faux.hors_passerelle, [])                                 # tout passe par la passerelle

    def test_check_ne_contacte_pas_jira(self):
        export = self.ecrire_export(self.inventer(2))
        self.lancer("check", export)
        self.assertEqual(self.faux.appels, [])

    def test_cloud_id_different_de_celui_du_site(self):
        self.faux.cloud_site = "autre-identifiant"
        for argv, attendu in ((("test",), "cloudId différent de celui du site"),
                              (("test", "--language", "en"), "cloudId differs from the site's")):
            with self.subTest(argv=argv):
                self.faux.appels.clear()
                code, sortie = self.lancer(*argv)
                self.assertEqual(code, 1)
                self.assertIn(attendu, sortie)
                for interdit in (base.CLOUD_ID, "autre-identifiant", "Traceback", "connexion OK", "connection OK"):
                    self.assertNotIn(interdit, sortie)
                self.assertEqual(self.faux.appels, [("GET", "/_edge/tenant_info")])     # aucun appel authentifié
                self.assertEqual(self.faux.hors_passerelle, [])

    def test_cloud_id_absent_ou_avec_des_caracteres_de_chemin(self):
        jeton = mock.Mock(return_value=base.JETON)
        for nom, cloud in (("absent", None), ("chemin", "a/../b"), ("espace", "a b"), ("question", "a?x=1")):
            with self.subTest(cloud=nom):
                self.ecrire_reglages("scopes", cloud=cloud)
                self.faux.appels.clear()
                jeton.reset_mock()
                with mock.patch.object(base.hj, "lire_jeton", jeton):
                    code, sortie = self.lancer("test")
                self.assertEqual(code, 1)
                self.assertIn("cloudId introuvable", sortie)
                self.assertNotIn("Traceback", sortie)
                if cloud:
                    self.assertNotIn(cloud, sortie)
                self.assertEqual(self.faux.appels, [])                                  # aucun appel, pas même au site
                jeton.assert_not_called()                                               # et le Trousseau n'est pas lu

    def test_cloud_id_vide_dans_les_reglages(self):
        # un cloudId vide est refusé par flux_config (le message nomme le réglage, jamais une valeur)...
        self.ecrire_reglages("scopes", cloud='""')
        code, sortie = self.lancer("test")
        self.assertNotEqual(code, 0)
        self.assertIn("jira_cloud_id", str(code) + sortie)
        self.assertEqual(self.faux.appels, [])
        # ... et l'outil le refuse aussi quand les réglages lui arrivent déjà lus
        interne = {"jira_site": self.url, "jira_email": base.EMAIL, "jira_jeton": "scopes", "jira_cloud_id": ""}
        with mock.patch.object(base.hj, "reglages", return_value=interne):
            code, sortie = self.lancer("test")
        self.assertEqual(code, 1)
        self.assertIn("cloudId introuvable", sortie)
        self.assertEqual(self.faux.appels, [])

    def test_collecte_sans_cloud_id_s_arrete_avant_tout_appel(self):
        self.ecrire_reglages("scopes", cloud=None)
        export = self.ecrire_export(self.inventer(2))
        code, sortie = self.lancer("collect", export)
        self.assertEqual(code, 1)
        self.assertIn("cloudId introuvable", sortie)
        self.assertEqual(self.faux.appels, [])


class JetonAScopesSeul(base.Base):
    """Le mode à droits limités est le seul : réglage absent = passerelle ; « classic » refusé avant le Trousseau et tout appel."""

    def test_reglage_absent_utilise_la_passerelle(self):
        self.ecrire_reglages(None)
        code, sortie = self.lancer("test")
        self.assertEqual((code, sortie.splitlines()[0]), (0, "connexion OK"))
        self.assertIn(("GET", "/rest/api/3/search/jql"), self.faux.appels)
        self.assertEqual(self.faux.hors_passerelle, [])

    def test_classic_refuse_dans_test(self):
        self.ecrire_reglages("classique")
        jeton = mock.Mock(return_value=base.JETON)
        for argv, attendu in ((("test",), "jeton classique refusé : utiliser un jeton à scopes"),
                              (("test", "--language", "en"), "classic token refused: use a scoped token")):
            with self.subTest(argv=argv), mock.patch.object(base.hj, "lire_jeton", jeton):
                code, sortie = self.lancer(*argv)
                self.assertEqual(code, 1)
                self.assertIn(attendu, sortie)
                self.assertNotIn("Traceback", sortie)
        jeton.assert_not_called()                           # le Trousseau n'est pas lu
        self.assertEqual(self.faux.appels, [])              # aucun appel, pas même la lecture du cloudId
        self.assertEqual(self.faux.hors_passerelle, [])

    def test_classic_refuse_dans_collect(self):
        self.ecrire_reglages("classique")
        export = self.ecrire_export(self.inventer(3))
        jeton = mock.Mock(return_value=base.JETON)
        with mock.patch.object(base.hj, "lire_jeton", jeton):
            code, sortie = self.lancer("collect", export)
        self.assertEqual(code, 1)
        self.assertIn("jeton classique refusé : utiliser un jeton à scopes", sortie)
        jeton.assert_not_called()
        self.assertEqual(self.faux.appels, [])
        self.assertFalse((self.ws / "Flux-Lab" / "historique").exists())

    def test_aucun_appel_authentifie_vers_l_adresse_du_site(self):
        export = self.ecrire_export(self.inventer(3))
        self.lancer("test")
        self.lancer("collect", export)
        self.assertEqual(self.faux.hors_passerelle, [])
        self.assertFalse(self.faux.auth_sur_tenant)

    def test_anciennes_valeurs_francaises_refusees_par_flux_config(self):
        for valeur in ("classique", "scopes"):
            with self.subTest(valeur=valeur):
                (self.ws / "Flux-Lab" / "flux.yaml").write_text(
                    f"jira_site: {self.url}\njira_email: {base.EMAIL}\njira_token_type: {valeur}\n"
                    f"jira_cloud_id: {base.CLOUD_ID}\n", encoding="utf-8")
                code, sortie = self.lancer("test")
                self.assertNotEqual(code, 0)
                self.assertIn("n'existe plus", str(code) + sortie)
                self.assertEqual(self.faux.appels, [])


class SondeEtExpiration(base.Base):
    """`test` : une requête par ressource (limitée à un résultat), une ligne d'accès chacune, puis les lignes d'expiration."""

    def setUp(self):
        super().setUp()
        p = mock.patch.object(base.hj, "aujourd_hui", lambda: AUJOURD_HUI)
        p.start()
        self.addCleanup(p.stop)

    def test_une_ligne_ok_par_ressource(self):
        code, sortie = self.lancer("test")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.splitlines(), ["connexion OK", "accès search : OK", "accès history : OK", "accès fields : OK"])
        code, sortie = self.lancer("test", "--language", "en")
        self.assertEqual(sortie.splitlines(), ["connection OK", "access search: OK", "access history: OK", "access fields: OK"])

    def test_chaque_requete_est_limitee_a_un_resultat(self):
        self.lancer("test")
        self.assertEqual([f for f, _ in self.faux.params], ["search", "history", "fields"])
        for famille, params in self.faux.params:
            self.assertEqual(params.get("maxResults"), "1", famille)

    def test_historique_d_un_ticket_trouve_par_la_recherche_sans_l_afficher(self):
        self.faux.ajouter("ABC-1")
        code, sortie = self.lancer("test")
        self.assertEqual(code, 0)
        self.assertIn(("GET", "/rest/api/3/issue/ABC-1/changelog"), self.faux.appels)
        for interdit in ("ABC-1", "Nom Fictif", "Champ Secret", "customfield_99999", "Titre secret", "10001"):
            self.assertNotIn(interdit, sortie)

    def test_scope_manquant_sur_l_historique(self):
        self.faux.refus = {"history": 403}
        code, sortie = self.lancer("test")
        self.assertEqual(code, 1)
        lignes = sortie.splitlines()
        self.assertIn("accès history : 403", lignes)
        self.assertIn("accès search : OK", lignes)
        self.assertIn("accès fields : OK", lignes)
        self.assertNotIn("Nom Fictif", sortie)
        self.assertNotIn("Traceback", sortie)

    def test_scope_manquant_sur_la_recherche_et_les_champs(self):
        self.faux.refus = {"search": 403, "fields": 403}
        code, sortie = self.lancer("test")
        self.assertEqual(code, 1)
        self.assertIn("accès search : 403", sortie)
        self.assertIn("accès history : OK", sortie)
        self.assertIn("accès fields : 403", sortie)
        _, anglais = self.lancer("test", "--language", "en")
        self.assertIn("access search: 403", anglais)

    def test_expiration_proche(self):
        self.ecrire_reglages("scopes", expiration="2026-10-23", extra="jira_token_warning_days: 30\n")
        code, sortie = self.lancer("test")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.splitlines()[-1], "le jeton API expire dans 10 jours")
        _, anglais = self.lancer("test", "--language", "en")
        self.assertEqual(anglais.splitlines()[-1], "API token expires in 10 days")

    def test_delai_d_avertissement_par_defaut_et_reglable(self):
        self.ecrire_reglages("scopes", expiration="2026-11-12")                          # dans 30 jours, délai par défaut 30
        self.assertIn("le jeton API expire dans 30 jours", self.lancer("test")[1])
        self.ecrire_reglages("scopes", expiration="2026-11-13")                          # dans 31 jours
        self.assertNotIn("expire", self.lancer("test")[1])
        self.ecrire_reglages("scopes", expiration="2026-11-13", extra="jira_token_warning_days: 60\n")
        self.assertIn("le jeton API expire dans 31 jours", self.lancer("test")[1])

    def test_expiration_hors_delai_sans_ligne(self):
        code, sortie = self.lancer("test")                                               # 2099 : rien à dire
        self.assertEqual(code, 0)
        for fragment in ("expire", "dépassée", "renseignée"):
            self.assertNotIn(fragment, sortie)

    def test_expiration_depassee_sans_appel_refuse_garde_le_code_0(self):
        self.ecrire_reglages("scopes", expiration="2026-10-01")
        code, sortie = self.lancer("test")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.splitlines()[-1], "date d'expiration du jeton API dépassée")
        _, anglais = self.lancer("test", "--language", "en")
        self.assertEqual(anglais.splitlines()[-1], "API token expiry date passed")

    def test_expiration_depassee_avec_un_appel_refuse_donne_le_code_1(self):
        self.ecrire_reglages("scopes", expiration="2026-10-01")
        self.faux.refus = {"fields": 403}
        code, sortie = self.lancer("test")
        self.assertEqual(code, 1)
        self.assertIn("accès fields : 403", sortie)
        self.assertEqual(sortie.splitlines()[-1], "date d'expiration du jeton API dépassée")

    def test_expiration_non_renseignee(self):
        self.ecrire_reglages("scopes", expiration=None)
        code, sortie = self.lancer("test")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.splitlines()[-1], "date d'expiration du jeton non renseignée")
        _, anglais = self.lancer("test", "--language", "en")
        self.assertEqual(anglais.splitlines()[-1], "token expiry date not set")

    def test_date_illisible_refusee_avec_le_nom_du_reglage(self):
        self.ecrire_reglages("scopes", expiration="bientot-peut-etre")
        code, sortie = self.lancer("test")
        self.assertNotEqual(code, 0)
        self.assertIn("jira_token_expires", str(code) + sortie)
        self.assertNotIn("bientot-peut-etre", str(code) + sortie)
        self.assertEqual(self.faux.appels, [])

    def test_jeton_refuse_n_affiche_aucune_ligne_d_expiration(self):
        self.ecrire_reglages("scopes", expiration=None)
        self.faux.attendu = "Basic autre"
        code, sortie = self.lancer("test")
        self.assertEqual((code, sortie.strip()), (1, "HTTP 401"))


if __name__ == "__main__":
    unittest.main()
