"""Tests de history_jira.py : un faux serveur HTTP local, la base en mémoire, des données inventées, un faux jeton (change database-only).

    uv run --with pyyaml --with requests --with "psycopg[binary]" python -m unittest discover -s tests/history_jira -v

Aucun appel au vrai Jira, aucune base réelle. Le jeton factice (test-token-000) ne doit apparaître ni dans la sortie, ni dans la base
fictive, ni dans aucun fichier écrit ; l'auteur et les champs autres que status ne doivent jamais être gardés. La collecte lit les
tickets dans la base et y écrit en une transaction (jira-flow-history « History written in one transaction, no cache file ») ; `check`
lit la base en lecture seule. L'aide (faux serveur, faux magasin) est dans aide_historique.py ; ce module la ré-exporte pour les autres
tests de la suite.
"""
import datetime as dt
import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_historique import (AUTEUR, CLOUD_ID, EMAIL, JETON, PARIS, SCRIPT, SENTINELLE, Base, FauxJira,  # noqa: E402,F401
                             MagasinMemoire, hj, transitions_inventees)


class Connexion(Base):
    def test_connexion_ok_sans_rien_afficher_d_autre(self):
        code, sortie = self.lancer("test")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.splitlines(), ["connexion OK", "accès search : OK", "accès history : OK", "accès fields : OK"])

    def test_code_http_seulement(self):
        self.faux.attendu = "Basic autre"
        code, sortie = self.lancer("test")
        self.assertEqual((code, sortie.strip()), (1, "HTTP 401"))
        for interdit in ("Nom Fictif", self.url, EMAIL, JETON):
            self.assertNotIn(interdit, sortie)

    def test_mode_scopes_passe_par_le_cloud_id(self):
        code, sortie = self.lancer("test")
        self.assertEqual(code, 0)
        self.assertIn(("GET", "/_edge/tenant_info"), self.faux.appels)
        self.assertNotIn(CLOUD_ID, sortie)
        self.assertEqual(self.faux.hors_passerelle, [])

    def test_reglages_manquants_ne_montrent_aucune_valeur(self):
        (self.ws / "Flux-Lab" / "flux.yaml").write_text("jira_email: a@example.org\n", encoding="utf-8")
        code, sortie = self.lancer("test")
        self.assertEqual(code, 1)
        self.assertIn("jira_site", sortie)
        self.assertNotIn("a@example.org", sortie)

    def test_http_distant_refuse(self):
        (self.ws / "Flux-Lab" / "flux.yaml").write_text(
            f"jira_site: http://exemple.atlassian.net\njira_email: {EMAIL}\njira_token_type: scoped\n"
            f"jira_cloud_id: {CLOUD_ID}\n", encoding="utf-8")
        code, sortie = self.lancer("test")
        self.assertEqual(code, 1)
        self.assertIn("https://", sortie)
        self.assertEqual(self.faux.appels, [])

    def test_jeton_lu_dans_le_trousseau_avec_la_bonne_commande(self):
        with tempfile.TemporaryDirectory() as tmp:
            faux_security = Path(tmp) / "security"
            faux_security.write_text(f'#!/bin/sh\necho "$@" > "{tmp}/arguments.txt"\necho {JETON}\n', encoding="utf-8")
            faux_security.chmod(faux_security.stat().st_mode | stat.S_IEXEC)
            # lire_jeton a été remplacée dans setUp : on rappelle l'originale depuis le fichier
            spec2 = importlib.util.spec_from_file_location("history_jira_orig", SCRIPT)
            orig = importlib.util.module_from_spec(spec2)
            spec2.loader.exec_module(orig)
            with mock.patch.dict(os.environ, {"PATH": f"{tmp}:{os.environ['PATH']}"}):
                self.assertEqual(orig.lire_jeton(), JETON)
            self.assertEqual((Path(tmp) / "arguments.txt").read_text().strip(), "find-generic-password -s pmzilla-jira -w")

    def test_jeton_introuvable_message_sans_trace(self):
        def sans_jeton():
            raise hj.ErreurSimple("jeton introuvable dans le Trousseau (service pmzilla-jira).")
        with mock.patch.object(hj, "lire_jeton", sans_jeton):
            code, sortie = self.lancer("test")
        self.assertEqual(code, 1)
        self.assertIn("jeton introuvable", sortie)
        self.assertNotIn("Traceback", sortie)


class AnciensNoms(Base):
    """Anciens noms d'options, de réglages et de valeurs refusés avec le nom actuel ; anciens noms de sous-commandes refusés."""

    def test_anciennes_options_refusees_avec_le_nom_actuel(self):
        export = self.ecrire_export(self.inventer(3))
        for args, ancien, nouveau in ((("collect", export, "--equipe", "Equipe Test"), "--equipe", "--team"),
                                      (("collect", export, "--rafraichir"), "--rafraichir", "--refresh"),
                                      (("check", "--cle", "ZZZ-9"), "--cle", "--key")):
            code, sortie = self.lancer(*args)
            self.assertEqual(code, 2, sortie)
            self.assertIn(f"« {ancien} » n'existe plus ; utiliser « {nouveau} »", sortie)
        self.assertEqual(self.faux.appels, [])

    def test_anciens_noms_de_reglages_refuses_avec_le_nom_actuel(self):
        for texte, attendu in ((f"jira_site: {self.url}\njira_email: {EMAIL}\njira_jeton: classic\n",
                                "« jira_jeton » n'existe plus ; utiliser « jira_token_type »"),
                               (f"jira_site: {self.url}\njira_email: {EMAIL}\njira_token_type: classique\n",
                                "valeur « classique » du réglage jira_token_type n'existe plus ; utiliser « classic »")):
            (self.ws / "Flux-Lab" / "flux.yaml").write_text(texte, encoding="utf-8")
            code, sortie = self.lancer("test")
            self.assertIn(attendu, str(code) + sortie)
            self.assertNotEqual(code, 0)
        self.assertEqual(self.faux.appels, [])

    def test_nouveaux_noms_sans_avertissement(self):
        code, sortie = self.lancer("test")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.splitlines()[0], "connexion OK")
        self.assertNotIn("n'existe plus", sortie)

    def test_anciens_noms_de_sous_commandes_refuses(self):
        for ancien in ("collecte", "controle"):
            code, sortie = self.lancer(ancien)
            self.assertEqual(code, 2, ancien)
            self.assertEqual(self.faux.appels, [])

    def test_message_du_reglage_manquant_donne_le_nouveau_nom(self):
        (self.ws / "Flux-Lab" / "flux.yaml").write_text(f"jira_email: {EMAIL}\n", encoding="utf-8")
        code, sortie = self.lancer("test")
        self.assertEqual(code, 1)
        self.assertIn("jira_site", sortie)
        self.assertNotIn("jira_jeton", sortie)


class Collecte(Base):
    def recherches_de_cles(self) -> int:
        """Nombre de pages de la recherche qui fait correspondre les clés aux identifiants (l'autre recherche lit les valeurs courantes)."""
        return sum(1 for api, corps in self.faux.corps if api == "/rest/api/3/search/jql" and corps.get("fields") == ["key"])

    def test_groupee_ne_garde_que_date_et_etats(self):
        self.ecrire_export(self.inventer(5))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        cache = self.cache()
        self.assertEqual(len(cache), 5)
        for entree in cache.values():
            self.assertEqual(set(entree), {"transitions"})
            self.assertEqual(len(entree["transitions"]), 2)           # le changement d'assigné est écarté
            for transition in entree["transitions"]:
                self.assertEqual(len(transition), 3)
        self.assertEqual(cache["ABC-1"]["transitions"][0][1:], ["Open", "In Progress"])
        self.assertEqual(cache["ABC-1"]["transitions"][1][1:], ["In Progress", "Done"])
        self.assertIn("Mode : groupé", sortie)
        self.assertIn("Tickets traités : 5 ; transitions de statut : 10 ; erreurs : 0", sortie)
        self.assertIn("historique écrit : 10 transitions ajoutées, 0 périodes écrites", sortie)

    def test_rien_de_sensible_dans_la_sortie_la_base_ni_les_fichiers(self):
        self.ecrire_export(self.inventer(6))
        code, sortie = self.lancer("collect", "--team", "Equipe Test")
        self.assertEqual(code, 0, sortie)
        ecrit = self.tous_les_fichiers() + repr(self.magasin.transitions) + repr(self.magasin.periodes)
        for texte in (sortie, ecrit):
            for interdit in (JETON, AUTEUR, "p@example.org", "Titre secret", "Nom Fictif", "assignee", EMAIL):
                self.assertNotIn(interdit, texte)
        self.assertNotIn("ABC-", sortie)                              # aucune clé dans le Terminal
        self.assertNotIn("Equipe Test", sortie)                       # ni le nom de l'équipe
        self.assertNotIn(self.url, sortie)

    def test_aucun_fichier_n_est_ecrit(self):
        self.ecrire_export(self.inventer(3))
        self.assertEqual(self.lancer("collect")[0], 0)
        self.assertEqual([p.name for p in self.ws.rglob("*") if p.is_file()], ["flux.yaml"])        # ni cache, ni dossier d'historique

    def test_pagination_groupee(self):
        self.faux.pages_groupees = 2
        self.ecrire_export(self.inventer(6))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.cache()), 6)
        self.assertTrue(all(len(v["transitions"]) == 2 for v in self.cache().values()))

    def test_repli_ticket_par_ticket_avec_pagination(self):
        self.faux.groupe = False
        self.faux.taille_page = 1                                         # une page par transition
        self.ecrire_export(self.inventer(4))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Mode : ticket par ticket", sortie)
        self.assertTrue(all(len(v["transitions"]) == 2 for v in self.cache().values()))
        self.assertEqual(sum(1 for m, p in self.faux.appels if p.endswith("/changelog")), 8)   # 4 tickets, 2 pages

    def test_pagination_groupee_ticket_coupe_entre_deux_pages_et_recherche_paginee(self):
        self.faux.entrees_par_page = 3                                    # 2 entrées par ticket : un ticket sur deux est coupé
        self.faux.taille_recherche = 2
        self.ecrire_export(self.inventer(7))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.cache()), 7)
        self.assertTrue(all(len(v["transitions"]) == 2 for v in self.cache().values()))
        self.assertEqual(sum(1 for m, p in self.faux.appels if p == "/rest/api/3/changelog/bulkfetch"), 5)   # 14 entrées / 3
        self.assertEqual(self.recherches_de_cles(), 4)

    def test_ticket_par_ticket_sans_islast_va_jusqu_a_la_page_vide(self):
        self.faux.groupe = False
        self.faux.taille_page = 1
        self.faux.sans_islast = True
        self.ecrire_export(self.inventer(2))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertTrue(all(len(v["transitions"]) == 2 for v in self.cache().values()))

    def test_une_collecte_sans_changement_n_ajoute_ni_doublon_ni_transition(self):
        self.ecrire_export(self.inventer(3, termines={"ABC-1", "ABC-2", "ABC-3"}))
        self.lancer("collect")
        avant = self.cache()
        code, sortie = self.lancer("collect", "--refresh")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.cache(), avant)                              # jamais en double, jamais supprimées
        self.assertIn("historique écrit : 0 transitions ajoutées, 0 périodes écrites", sortie)

    def test_rafraichir_interroge_tout(self):
        self.ecrire_export(self.inventer(3, termines={"ABC-1", "ABC-2", "ABC-3"}))
        self.lancer("collect")
        self.faux.appels.clear()
        code, sortie = self.lancer("collect")
        self.assertEqual(self.faux.appels, [])                            # tout est collecté et terminé : aucun appel
        code, sortie = self.lancer("collect", "--refresh")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Tout est réinterrogé (--refresh)", sortie)
        self.assertIn("Tickets traités : 3", sortie)

    def test_seuls_les_tickets_sans_historique_ou_ouverts_sont_interroges(self):
        lignes = self.inventer(4, termines={"ABC-1", "ABC-2"})
        self.ecrire_export(lignes[:3])
        self.lancer("collect")
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-2", "ABC-3"})
        self.faux.appels.clear()
        self.faux.corps.clear()
        self.ecrire_export(lignes)                                         # ABC-4 arrive dans la base
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Déjà collectés et terminés (non réinterrogés) : 2 ; à interroger : 2", sortie)
        self.assertEqual(self.recherches_de_cles(), 1)                    # un seul lot : ABC-3 (non terminé) et ABC-4 (sans historique)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-2", "ABC-3", "ABC-4"})

    def test_tout_collecte_et_termine_aucun_appel(self):
        self.ecrire_export(self.inventer(3, termines={"ABC-1", "ABC-2", "ABC-3"}))
        self.lancer("collect")
        self.faux.appels.clear()
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0)
        self.assertEqual(self.faux.appels, [])
        self.assertIn("historique écrit : 0 transitions ajoutées, 0 périodes écrites", sortie)

    def test_ticket_devenu_termine_n_est_pas_reinterroge_sans_mise_a_jour(self):
        lignes = self.inventer(2)
        self.ecrire_export(lignes)
        self.lancer("collect")
        self.ecrire_export([(c, t, e, c == "ABC-1") for c, t, e, _ in lignes])          # ABC-1 se termine, sans mise à jour
        self.faux.appels.clear()
        self.faux.corps.clear()
        self.lancer("collect")
        self.assertEqual(self.recherches_de_cles(), 1)                    # ABC-2 (ouvert) seul est réinterrogé

    def test_equipe_filtre_et_ne_montre_pas_le_nom(self):
        self.ecrire_export(self.inventer(6))
        code, sortie = self.lancer("collect", "--team", "equipe test")     # casse sans importance
        self.assertEqual(code, 0, sortie)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-3", "ABC-5"})
        self.assertIn("hors équipe demandée : 3", sortie)
        self.assertNotIn("quipe test", sortie.lower().replace("équipe demandée", ""))

    def test_equipe_retient_un_ticket_des_qu_une_de_ses_equipes_correspond(self):
        for i in range(1, 6):
            self.faux.ajouter(f"ABC-{i}")
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", False), ("ABC-2", "Story", "Autre Equipe;Equipe Test", False),
                            ("ABC-3", "Story", "Autre Equipe;Equipe Test;Troisieme", False), ("ABC-4", "Story", "Autre Equipe", False),
                            ("ABC-5", "Story", "", False)])
        code, sortie = self.lancer("collect", "--team", "equipe test")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sorted(self.cache()), ["ABC-1", "ABC-2", "ABC-3"])
        self.assertIn("hors équipe demandée : 2", sortie)

    def test_equipe_inconnue(self):
        self.ecrire_export(self.inventer(3))
        code, sortie = self.lancer("collect", "--team", "Inconnue")
        self.assertEqual(code, 1)
        self.assertIn("aucun ticket", sortie)
        self.assertNotIn("Inconnue", sortie)
        self.assertEqual(self.faux.appels, [])

    def test_portefeuille_et_projets_exclus_ne_sont_pas_interroges(self):
        # epic_types : les types d'épic des réglages (« Epic » par défaut) sont interrogés même de niveau portefeuille ; ce test garde
        # le cas général (un type de portefeuille qui n'est pas un type d'épic reste écarté), l'exception est dans test_epics.py
        self.ecrire_reglages("scopes", "portfolio_types: [Epic]\nepic_types: [Feature]\nexcluded_projects: [BUG]\n")
        lignes = self.inventer(3)
        for cle in ("EPI-1", "BUG-1"):
            self.faux.ajouter(cle)
        lignes += [("EPI-1", "Epic", "Equipe Test", False), ("BUG-1", "Bug", "Equipe Test", False)]
        code, sortie = self.lancer("collect", self.ecrire_export(lignes))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-2", "ABC-3"})
        self.assertIn("écartés (types de portefeuille, projets exclus) : 2", sortie)

    def test_429_respecte_retry_after_puis_reussit(self):
        self.faux.limite_429 = 2
        self.ecrire_export(self.inventer(2))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.attentes[:2], [1.0, 1.0])                   # Retry-After: 1 respecté
        self.assertEqual(len(self.cache()), 2)

    def test_429_persistant_compte_les_erreurs_et_n_ecrit_pas_de_passage(self):
        self.faux.toujours_429 = True
        self.ecrire_export(self.inventer(2))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0)                                         # erreurs comptées, rien de fatal
        self.assertIn("erreurs : 2 (HTTP 429 : 2)", sortie)
        self.assertEqual(self.cache(), {})
        self.assertEqual(self.magasin.passages, [])                       # pas de collecte réussie : les tickets seront retentés
        self.assertTrue(self.attentes)

    def test_strict_429_persistant_sort_avec_3(self):
        self.faux.toujours_429 = True
        self.ecrire_export(self.inventer(2))
        code, sortie = self.lancer("collect", "--strict")
        self.assertEqual(code, 3, sortie)
        self.assertIn("erreurs : 2 (HTTP 429 : 2)", sortie)
        self.assertTrue(sortie.rstrip().endswith("erreurs de collecte : historique incomplet"), sortie)

    def test_strict_429_persistant_en_anglais(self):
        self.faux.toujours_429 = True
        self.ecrire_export(self.inventer(2))
        code, sortie = self.lancer("collect", "--strict", "--language", "en")
        self.assertEqual(code, 3, sortie)
        self.assertTrue(sortie.rstrip().endswith("collection errors: history incomplete"), sortie)

    def test_strict_sans_erreur_sort_avec_0(self):
        self.ecrire_export(self.inventer(2))
        code, sortie = self.lancer("collect", "--strict")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("historique incomplet", sortie)

    def test_sans_strict_429_persistant_reste_0(self):
        self.faux.toujours_429 = True
        self.ecrire_export(self.inventer(2))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("historique incomplet", sortie)

    def test_strict_garde_le_code_1_d_une_erreur_d_acces(self):
        self.faux.attendu = "Basic autre"
        self.ecrire_export(self.inventer(3))
        code, sortie = self.lancer("collect", "--strict")
        self.assertEqual(code, 1, sortie)
        self.assertNotIn("historique incomplet", sortie)

    def test_attente_croissante_sans_retry_after(self):
        faux_attentes = []
        r_sans = mock.Mock(status_code=503, headers={})
        client = hj.Client(self.url, (EMAIL, JETON), sleep=faux_attentes.append)
        with mock.patch.object(client.session, "request", return_value=r_sans):
            with self.assertRaises(hj.ErreurHTTP) as contexte:
                client.requete("GET", "/x")
        self.assertEqual(contexte.exception.code, 503)
        self.assertEqual(faux_attentes, [2.0, 4.0, 8.0, 16.0, 32.0])

    def test_erreur_d_acces_arrete_et_n_ecrit_rien(self):
        self.faux.attendu = "Basic autre"
        self.ecrire_export(self.inventer(3))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 1)
        self.assertIn("Arrêt : HTTP 401", sortie)
        self.assertEqual((self.cache(), self.magasin.passages, self.magasin.ecritures), ({}, [], 0))

    def test_acces_refuse_apres_un_premier_lot_annule_tout(self):
        """Une seule transaction : un 403 sur le deuxième lot ne laisse pas les transitions du premier."""
        self.ecrire_export(self.inventer(3))
        original = hj.Client.json
        appels = []

        def json_refuse_au_deuxieme_lot(client, methode, chemin, **kwargs):
            appels.append(chemin)
            if chemin == "/rest/api/3/search/jql" and sum(1 for c in appels if c == chemin) > 2:
                raise hj.ErreurHTTP(403)
            return original(client, methode, chemin, **kwargs)

        with mock.patch.object(hj, "LOT_GROUPE", 2), mock.patch.object(hj.Client, "json", json_refuse_au_deuxieme_lot):
            code, sortie = self.lancer("collect")
        self.assertEqual(code, 1, sortie)
        self.assertIn("Arrêt : HTTP 403", sortie)
        self.assertEqual((self.cache(), self.magasin.passages, self.magasin.ecritures), ({}, [], 0))

    def test_ticket_introuvable_compte_une_erreur_et_n_ecrit_pas_de_passage(self):
        self.faux.groupe = False
        self.faux.introuvables = {"ABC-2"}
        self.ecrire_export(self.inventer(3))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        # D15 (bug du 404 permanent) : un 404 n'est plus une erreur ; il est compté à part et n'empêche pas le passage d'être enregistré
        self.assertIn("erreurs : 0.", sortie)
        self.assertIn("tickets introuvables dans Jira : 1", sortie)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-3"})           # le ticket introuvable sera retenté
        self.assertEqual(len(self.magasin.passages), 1)                   # collecte réussie : le 404 ne bloque pas la fenêtre
        self.faux.introuvables = set()
        self.lancer("collect")
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-2", "ABC-3"})
        self.assertEqual(len(self.magasin.passages), 2)

    def test_une_collecte_reussie_ecrit_un_passage_history(self):
        self.ecrire_export(self.inventer(2))
        self.lancer("collect")
        self.assertEqual(len(self.magasin.passages), 1)
        self.lancer("collect")
        self.assertEqual(len(self.magasin.passages), 2)                   # même sans rien à interroger

    def test_erreur_de_base_a_l_ecriture_ne_laisse_rien_et_n_affiche_que_le_type(self):
        self.ecrire_export(self.inventer(3))
        self.magasin.echec = RuntimeError("ZZSECRET-ABC-1-mot-de-passe")
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 1, sortie)
        self.assertIn("Erreur inattendue (RuntimeError)", sortie)
        self.assertNotIn("ZZSECRET", sortie)
        self.assertNotIn("ABC-1", sortie)
        self.assertEqual((self.cache(), self.magasin.passages), ({}, []))
        self.assertTrue(self.magasin.ferme)                                # la connexion est fermée dans tous les cas

    def test_base_vide_arrete_avant_tout_appel(self):
        for langue, phrase in (("fr", "aucun ticket dans la base : lancez d'abord l'export et l'import"),
                               ("en", "no ticket in the database: run the export and the import first")):
            code, sortie = self.lancer("collect", "--language", langue)
            self.assertEqual(code, 1, sortie)
            self.assertIn(phrase, sortie)
        self.assertEqual(self.faux.appels, [])

    def test_fichier_d_export_refuse_avant_tout_appel_et_toute_connexion(self):
        connexions = []
        with mock.patch.object(hj, "ouvrir_magasin", lambda: connexions.append(1)):
            for langue, phrase in (("fr", "les fichiers d'export ne sont plus lus : la base est la seule source"),
                                   ("en", "export files are no longer read: the database is the only source")):
                code, sortie = self.lancer("collect", str(self.ws / "export.csv"), "--language", langue)
                self.assertEqual(code, 2, sortie)
                self.assertIn(phrase, sortie)
                self.assertNotIn("export.csv", sortie)
        self.assertEqual((connexions, self.faux.appels), ([], []))

    def test_mot_de_passe_du_role_d_import_absent_ou_base_injoignable_arrete_avant_jira(self):
        for cle in ("db_password_missing", "db_unreachable"):
            def refuse(cle=cle):
                raise hj.ErreurSimple(hj.t(cle))
            with mock.patch.object(hj, "ouvrir_magasin", refuse):
                code, sortie = self.lancer("collect")
            self.assertEqual(code, 1, sortie)
            self.assertIn("Erreur : ", sortie)
            self.assertEqual(self.faux.appels, [])

    def test_option_dormants_et_cle_inchangees(self):
        self.ecrire_export(self.inventer(1))
        self.lancer("collect")
        code, sortie = self.lancer("check", "--key", "ABC-1")
        self.assertEqual(code, 0, sortie)

    def test_cache_hors_git_plus_de_dossier_d_historique(self):
        self.ecrire_export(self.inventer(2))
        self.lancer("collect")
        self.assertFalse((self.ws / "Flux-Lab" / "historique").exists())


PARCOURS_REEL = [          # (de, vers, jour d'août ou septembre) : un ticket qui passe par tous les segments
    ("Open", "Definition", "2026-08-03"), ("Definition", "Ready for Implementation", "2026-08-10"),
    ("Ready for Implementation", "Implementation - Ongoing", "2026-08-17"),
    ("Implementation - Ongoing", "Ready for Review (Implementation)", "2026-08-31"),
    ("Ready for Review (Implementation)", "Ready for Acceptance", "2026-09-07"),
    ("Ready for Acceptance", "Closed", "2026-09-14")]


class DatesDeLaCollecte(Base):
    """Les dates de l'API (ISO avec décalage, ou millisecondes depuis 1970 en mode groupé) deviennent des instants triés."""

    def inventer_reels(self, n: int = 3):
        for i in range(1, n + 1):
            cle = f"ABC-{i}"
            self.faux.tickets[cle] = (str(20000 + i), [
                {"id": f"{i}{k}", "created": f"{jour}T09:00:00.000+0200", "author": {"displayName": AUTEUR},
                 "items": [{"field": "status", "fieldId": "status", "fromString": de, "toString": vers}]}
                for k, (de, vers, jour) in enumerate(PARCOURS_REEL)])
        return [(f"ABC-{i}", "Story", "Equipe Test", True) for i in range(1, n + 1)]

    def test_dates_iso_en_mode_groupe(self):
        self.ecrire_export(self.inventer_reels())
        self.assertEqual(self.lancer("collect")[0], 0)
        instants = [t[0] for t in self.cache()["ABC-1"]["transitions"]]
        self.assertEqual(len(instants), 6)
        self.assertEqual(instants[0], "2026-08-03T09:00:00+02:00")
        self.assertEqual(instants, sorted(instants))

    def test_dates_en_millisecondes_du_mode_groupe_lues_comme_des_instants(self):
        self.faux.dates_epoch = True
        self.ecrire_export(self.inventer_reels())
        self.assertEqual(self.lancer("collect")[0], 0)
        magasin = self.magasin.transitions["ABC-1"]
        self.assertEqual(len(magasin), 6)
        self.assertTrue(all(instant.utcoffset() == dt.timedelta(0) for instant, _, _ in magasin))      # millisecondes : UTC
        self.assertEqual(min(instant for instant, _, _ in magasin).isoformat(), "2026-08-03T07:00:00+00:00")

    def test_instant_sans_decalage_lu_dans_le_fuseau_d_export(self):
        histo = [{"created": "2026-03-01T09:00:00", "items": [{"fieldId": "status", "fromString": "A", "toString": "B"}]}]
        self.faux.tickets["ABC-1"] = ("30001", histo)
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", False)])
        self.lancer("collect")
        instant = self.magasin.transitions["ABC-1"][0][0]
        self.assertEqual(instant.isoformat(), "2026-03-01T09:00:00+01:00")       # fuseau d'export par défaut : Europe/Paris


class NormaliserDate(unittest.TestCase):
    def test_formats(self):
        n = hj.commun.normaliser_date
        self.assertEqual(n("2026-03-01T09:00:00.000+0200"), "2026-03-01T09:00:00.000+0200")
        self.assertEqual(n(1772352000123), "2026-03-01T08:00:00.123+0000")
        self.assertEqual(n("1772352000123"), "2026-03-01T08:00:00.123+0000")
        self.assertEqual(n(1772352000), "2026-03-01T08:00:00.000+0000")        # secondes
        self.assertIsNone(n(None))
        self.assertEqual(n("pas une date"), "pas une date")


class FormatsDeDate(unittest.TestCase):
    """Le calcul des dormants et la lecture des dates de transition ne dépendent d'aucun format de CSV."""

    def test_dormants_selon_l_historique_sans_format_de_csv(self):
        commun = hj.commun
        cache = {"ABC-1": [["2024-03-01T10:00:00.000+0200", "Open", "Doing"]], "ABC-2": []}
        dormants, sans = commun.dormants_selon_historique(
            [("ABC-1", dt.date(2024, 1, 1), False), ("ABC-2", dt.date(2026, 9, 1), False), ("ABC-3", dt.date(2024, 1, 1), False)],
            cache, dt.date(2026, 10, 4))
        self.assertEqual((dormants, sans), ({"ABC-1"}, 1))

    def test_date_calendaire_du_jour_du_decalage_d_origine(self):
        self.assertEqual(hj.commun.date_calendaire("2017-11-09T08:49:00.000+0100").isoformat(), "2017-11-09")


class Tri(unittest.TestCase):
    def test_tri_chronologique_malgre_des_decalages_differents(self):
        # 09:00 à +0200 = 07:00 UTC, avant 08:00 à +0000, alors que le texte les range dans l'autre ordre
        histo = [{"created": "2026-03-01T08:00:00.000+0000", "items": [{"fieldId": "status", "fromString": "B", "toString": "C"}]},
                 {"created": "2026-03-01T09:00:00.000+0200", "items": [{"fieldId": "status", "fromString": "A", "toString": "B"}]}]
        self.assertEqual([t[1:] for t in hj.evenements_de(histo)[0]], [["A", "B"], ["B", "C"]])

    def test_ordre_de_l_api_inverse_ou_non_donne_le_meme_resultat(self):
        histo = transitions_inventees(1)
        self.assertEqual(hj.evenements_de(histo)[0], hj.evenements_de(list(reversed(histo)))[0])

    def test_date_illisible_ne_fait_pas_planter(self):
        histo = [{"created": None, "items": [{"fieldId": "status", "fromString": "A", "toString": "B"}]},
                 {"created": "2026-03-01T09:00:00.000+0200", "items": [{"fieldId": "status", "fromString": "B", "toString": "C"}]}]
        self.assertEqual(len(hj.evenements_de(histo)[0]), 2)


class Controle(Base):
    """`check` lit la base en lecture seule (faux flow_store) : aucun appel à Jira, effectifs seulement (jira-flow-history « Cache check »)."""

    def poser(self, cle, transitions):
        """Pose l'historique d'un ticket de la base fictive : [(jour, départ, arrivée)] ; le ticket est « avec historique »."""
        self.magasin.stock[cle]["a_historique"] = True
        self.magasin.transitions[cle] = [(dt.datetime.fromisoformat(f"{jour}T10:00:00+02:00"), de, vers) for jour, de, vers in transitions]

    def parcours(self, *etats):
        return [(f"2026-03-0{n + 1}", a, b) for n, (a, b) in enumerate(zip(etats, etats[1:]))]

    def test_effectifs_sans_identifiant_et_sans_appel_reseau(self):
        for i in range(1, 6):
            self.faux.ajouter(f"ABC-{i}")
        self.ecrire_export([(f"ABC-{i}", "Story", "Equipe Test", True) for i in range(1, 6)] + [("ABC-9", "Story", "Equipe Test", False)])
        self.lancer("collect")
        self.magasin.transitions["ABC-5"] = []                                           # livré sans transition
        self.magasin.transitions["ABC-4"] = self.magasin.transitions["ABC-4"][:1]        # dernier état : In Progress, pas Done
        self.faux.appels.clear()
        code, sortie = self.lancer("check")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.faux.appels, [])
        self.assertIn("sans historique : 1", sortie)                                     # ABC-9 n'a pas d'historique
        self.assertIn("cohérents 3 ; incohérents 1 ; non comparables (aucune transition) 1", sortie)
        self.assertIn("0 : 1 ; 1 : 1 ; 2-4 : 3 ; 5-9 : 0 ; 10 et plus : 0", sortie)
        self.assertIn("(date de résolution) : 5 ; livrés sans aucune transition : 1", sortie)
        self.assertNotIn("ABC-", sortie)
        self.assertNotIn("Equipe Test", sortie)
        self.assertNotIn("illisibles", sortie)                                           # aucune ligne de dates illisibles

    def test_livres_etat_de_depart_transitions_et_segments(self):
        self.ecrire_export([(f"ABC-{i}", "Story", "Equipe Test", True) for i in range(1, 5)])
        self.poser("ABC-1", self.parcours("Open", "Definition", "Ready for Implementation", "Implementation", "Done"))
        self.poser("ABC-2", self.parcours("Open", "Implementation", "Done"))
        self.poser("ABC-3", self.parcours("Implementation", "Verification", "Done"))      # début tronqué
        self.poser("ABC-4", self.parcours("Open", "Closed"))
        code, sortie = self.lancer("check")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Tickets livrés (4) : lecture de l'historique.", sortie)
        self.assertIn("État de départ de la première transition connue : Open 3 ; Implementation 1.", sortie)
        self.assertIn("Transitions par ticket livré : 0 : 0 ; 1 : 1 ; 2-4 : 3 ; 5-9 : 0 ; 10 et plus : 0.", sortie)
        self.assertIn("definition 1 ; pret 1 ; implementation 3 ; revue_verification 1 ; (aucun segment) 1", sortie)
        self.assertNotIn("ABC-", sortie)

    def test_segments_reglables_dans_flux_yaml(self):
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", True)])
        self.poser("ABC-1", self.parcours("Open", "In Progress", "Done"))
        self.ecrire_reglages("scopes", "segments:\n  fin: [In Progress]\n")
        code, sortie = self.lancer("check")
        self.assertIn("Segments traversés (tickets livrés passés par le segment) : fin 1.", sortie)

    def test_flux_jira_et_controle_partagent_la_table_des_segments(self):
        import ast
        source = (SCRIPT.parent / "flux_jira.py").read_text(encoding="utf-8")
        noeud = next(n for n in ast.parse(source).body if isinstance(n, ast.Assign)
                     and any(getattr(c, "id", None) == "DEFAULT_CONFIG" for c in n.targets))
        valeurs = {k.value: ast.unparse(v) for k, v in zip(noeud.value.keys, noeud.value.values)}
        self.assertEqual(valeurs["segments"], "commun.SEGMENTS_PAR_DEFAUT")
        self.assertEqual(valeurs["segments_hors_calcul"], "commun.SEGMENTS_HORS_CALCUL_PAR_DEFAUT")

    def test_etats_par_defaut_ranges(self):
        segment_de, calcules = hj.commun.table_segments({})
        self.assertEqual(segment_de["ready for enhancement check"], "definition")
        self.assertEqual(segment_de["draft"], "a_faire")
        self.assertEqual(segment_de["open"], "a_faire")
        for etat in ("Closed", "Resolved", "Accepted & Released", "Rejected"):
            self.assertEqual(segment_de[etat.casefold()], "termine")
        self.assertNotIn("a_faire", calcules)                       # hors calcul : aucun temps calculé
        self.assertNotIn("termine", calcules)

    def test_cle_affiche_la_suite_des_etats_sans_auteur(self):
        self.faux.ajouter("ABC-1")
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", True)])
        self.lancer("collect")
        code, sortie = self.lancer("check", "--key", "abc-1")
        self.assertEqual(code, 0, sortie)
        self.assertIn("ABC-1 : 2 transition(s)", sortie.replace("abc-1", "ABC-1"))
        self.assertIn("Open  ->  In Progress", sortie)
        self.assertIn("In Progress  ->  Done", sortie)
        self.assertIn("état stocké : Done", sortie)
        self.assertNotIn(AUTEUR, sortie)
        self.assertNotIn("2026-01-10T", sortie)                     # date lisible, sans « T » ni millisecondes
        code, sortie = self.lancer("check", "--key", "ZZZ-9")
        self.assertEqual(code, 1)
        self.assertIn("absent de la base", sortie)

    def test_controle_sans_aucun_historique_stocke(self):
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", True)])
        for langue, phrase in (("fr", "aucun historique dans la base : lancez d'abord la collecte de l'historique"),
                               ("en", "no history in the database: run the history collection first")):
            code, sortie = self.lancer("check", "--language", langue)
            self.assertEqual(code, 1, sortie)
            self.assertIn(phrase, sortie)

    def test_option_dormants_refusee_avec_la_voie_de_remplacement(self):
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", True)])
        for langue, extrait in (("fr", "n'existe plus"), ("en", "no longer exists")):
            code, sortie = self.lancer("check", "--dormants", "dormants.csv", "--language", langue)
            self.assertEqual(code, 1, sortie)
            self.assertIn("--dormant-from-history", sortie)
            self.assertIn(extrait, sortie)
            self.assertNotIn("Traceback", sortie)

    def test_fichier_d_export_refuse_avec_la_phrase_de_la_conception(self):
        for langue, phrase in (("fr", "les fichiers d'export ne sont plus lus : la base est la seule source"),
                               ("en", "export files are no longer read: the database is the only source")):
            code, sortie = self.lancer("check", str(self.ws / "export.csv"), "--language", langue)
            self.assertEqual(code, 2, sortie)
            self.assertIn(phrase, sortie)

    def test_refus_dans_une_session_claude_code_avant_toute_lecture_de_reglage(self):
        (self.ws / "Flux-Lab" / "flux.yaml").unlink()
        for langue, phrase in (("fr", "Refusé dans une session Claude Code"), ("en", "Refused inside a Claude Code session")):
            with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
                code, sortie = self.lancer("check", "--language", langue)
            self.assertEqual(code, 3, sortie)
            self.assertEqual(sortie.strip(), phrase)

    def test_la_collecte_n_est_pas_un_lecteur_de_session(self):
        """La session est refusée par les règles deny pour la collecte ; seul `check` (lecteur de la base) la refuse lui-même."""
        self.ecrire_export(self.inventer(1))
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)

    def test_tranches(self):
        self.assertEqual([hj.tranche(n) for n in (0, 1, 2, 4, 5, 9, 10, 40)],
                         ["0", "1", "2-4", "2-4", "5-9", "5-9", "10 et plus", "10 et plus"])


if __name__ == "__main__":
    unittest.main()
