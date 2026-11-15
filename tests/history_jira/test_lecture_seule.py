"""Client Jira en lecture seule et garde du périmètre (change jira-read-only-client) : liste des lectures permises, phrases et codes 5 et 6,
sondes réelles contre un faux serveur local, garde des projets déclarés et refusés, filtre des réponses, test statique d'accès unique.

    bash tests/run_all.sh history_jira

Faux restants (design D6), déclarés ici : le jeton et le lecteur du Trousseau (JETON, `lire_jeton` remplacé), les magasins en mémoire
(MagasinMemoire), l'attente remplacée (aucune pause réelle), la passerelle (`API_ATLASSIAN`) qui pointe sur la machine locale en HTTP
simple. Le réseau, lui, est réel : un faux serveur local journalise chaque requête reçue, avant tout contrôle. Clés fictives seulement
(PRJA, PRJB, OTHER, SUPX, ABC) ; aucune clé ni aucun nom de projet réel.
"""
import ast
import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_history_jira as base  # noqa: E402

hj = base.hj
TOOLS = Path(__file__).resolve().parents[2] / "tools"
CHANGELOG = "/rest/api/3/issue/PRJA-1/changelog"
RECHERCHE = "/rest/api/3/search/jql"
GARDE_PRJ = ["scope_projects: [PRJA, PRJB]", "forbidden_projects: [SUPX]"]
DECLAREES = "declared_labels:\n  cycle:\n    prefix: cyc-\n    labels: [cyc-a, cyc-b]\n"
CHEMINS_PIEGES = ["/rest/api/3/issue/PRJA-1/../changelog", "/rest/api/3/search/jql?jql=project%20=%20PRJA",
                  "/rest/api/3/issue/PRJA%2F1/changelog", "/rest/api/3/issue/prja-1/changelog", "//rest/api/3/field",
                  "/rest/api/3/field/", "", "/rest/api/3/issue/PRJA-1/changelog#x", "/rest/api/3/issue/PRJA-1\\changelog",
                  "rest/api/3/field"]
# Paires vues par les sondes des deux autres suites. La SOURCE est la constante PAIRES_ATTENDUES de chacune de ces suites
# (tests/export_jira_api/test_lecture_seule.py, tests/story_quality/test_lecture_seule.py), vérifiée contre ses propres sondes ; les
# constantes ci-dessous en sont la copie, et le test `test_copies_alignees_sur_les_constantes_des_autres_suites` détecte tout écart.
# Le test de couverture en fait l'union avec les paires de cette suite.
PAIRES_EXPORT = {("GET", "/rest/api/3/field"), ("POST", RECHERCHE)}
PAIRES_QUALITE = {("GET", "/rest/api/3/field"), ("POST", RECHERCHE)}


def ticket(cle, ident="1", **champs):
    return {"id": ident, "key": cle, "fields": champs}


def lie(cle, **champs):
    return {"key": cle, "id": "999", "self": "https://exemple.invalid/x", "fields": {"summary": "Titre secret", "status": {"name": "Open"},
                                                                                "priority": {"name": "High"},
                                                                                "issuetype": {"name": "Bug"}, **champs}}


class Fond(base.Base):
    def setUp(self):
        super().setUp()
        hj.set_language("fr")
        self.addCleanup(hj.set_language, "fr")
        self.passerelle = f"{self.url}/ex/jira/{base.CLOUD_ID}"

    def client(self, projets=("PRJA", "PRJB"), interdits=("SUPX",), authentifie=True):
        if authentifie:
            return hj.Client(self.passerelle, (base.EMAIL, base.JETON), sleep=self.attentes.append, projets=projets, interdits=interdits)
        return hj.Client(self.url, sleep=self.attentes.append)

    def recherche(self, client, jql, methode="GET"):
        if methode == "GET":
            return client.requete("GET", RECHERCHE, params={"jql": jql})
        return client.requete("POST", RECHERCHE, json={"jql": jql, "fields": ["key"]})

    def chemin_sans_passerelle(self, chemin: str) -> str:
        p = urlparse(chemin).path
        return p[len(self.faux.prefixe):] if p.startswith(self.faux.prefixe) else p

    def paires_vues(self) -> set:
        return {(m, self.chemin_sans_passerelle(c)) for m, c, _ in self.faux.brut}

    def verifier_sonde(self):
        """Chaque requête reçue est une paire de la liste, aucune requête authentifiée ne sort de la passerelle, au moins une est reçue."""
        self.assertTrue(self.faux.brut, "aucune requête reçue")
        liste = hj.lectures_autorisees()
        for methode, chemin, auth in self.faux.brut:
            chemin_api = self.chemin_sans_passerelle(chemin)
            self.assertTrue(any(m == methode and re.fullmatch(p, chemin_api) for m, p, _ in liste), (methode, chemin_api))
            if auth:
                self.assertTrue(chemin.startswith(self.faux.prefixe + "/"), chemin)
            if methode != "GET":
                self.assertIn((methode, chemin_api), {("POST", RECHERCHE), ("POST", "/rest/api/3/changelog/bulkfetch")})

    def entrees_vues(self) -> set:
        """Entrées de la liste vues par les requêtes reçues (méthode, motif)."""
        vues = set()
        for m, chemin in self.paires_vues():
            for methode, motif, _ in hj.lectures_autorisees():
                if methode == m and re.fullmatch(motif, chemin):
                    vues.add((methode, motif))
        return vues


class ListeDesLectures(Fond):
    def test_garde_de_la_liste(self):
        liste = hj.lectures_autorisees()
        self.assertEqual(len(liste), 7)
        self.assertTrue(all(m in ("GET", "POST") for m, _, _ in liste))
        self.assertEqual({p for m, p, _ in liste if m == "POST"}, {RECHERCHE, "/rest/api/3/changelog/bulkfetch"})
        for m, motif, auth in liste:
            re.compile(motif)
            for interdit in (".*", ".+", "|"):
                self.assertNotIn(interdit, motif)
            for piege in CHEMINS_PIEGES:
                self.assertIsNone(re.fullmatch(motif, piege), (motif, piege))
        self.assertEqual([p for m, p, a in liste if not a], ["/_edge/tenant_info"])

    def test_ecritures_refusees_sans_appel(self):
        client = self.client()
        for methode in ("PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
            with self.assertRaises(hj.RequeteRefusee) as contexte:
                client.requete(methode, CHANGELOG)
            self.assertEqual(contexte.exception.genre, "write")
            self.assertNotIsInstance(contexte.exception, hj.ErreurHTTP)
            self.assertIsInstance(contexte.exception, hj.ErreurSimple)
        self.assertEqual((self.faux.brut, self.attentes), ([], []))

    def test_post_hors_des_deux_lectures(self):
        client = self.client()
        for chemin in ("/rest/api/3/issue", "/rest/api/3/field", CHANGELOG, "/_edge/tenant_info"):
            with self.assertRaises(hj.RequeteRefusee) as contexte:
                client.requete("POST", chemin, json={})
            self.assertEqual(contexte.exception.genre, "write")
        self.assertEqual(self.faux.brut, [])

    def test_chemins_pieges_refuses_avec_la_phrase_de_lecture(self):
        client = self.client()
        for piege in CHEMINS_PIEGES:
            with self.assertRaises(hj.RequeteRefusee) as contexte:
                client.requete("GET", piege)
            self.assertEqual(contexte.exception.genre, "read", piege)
        self.assertEqual(self.faux.brut, [])

    def test_methode_en_minuscules_acceptee_et_envoyee_en_majuscules(self):
        self.client().requete("get", "/rest/api/3/field")
        self.assertEqual([m for m, _, _ in self.faux.brut], ["GET"])

    def test_methode_hors_des_verbes_http_imprimee_en_point_d_interrogation(self):
        for methode in ("FOO", "get\n", "PUT-X", "x" * 40):
            with self.assertRaises(hj.RequeteRefusee) as contexte:
                self.client().requete(methode, CHANGELOG)
            self.assertEqual(contexte.exception.methode, "?")
            self.assertTrue(str(contexte.exception).endswith("(?)"), str(contexte.exception))
            self.assertNotIn("FOO", str(contexte.exception))
        with self.assertRaises(hj.RequeteRefusee) as contexte:
            self.client().requete("trace", CHANGELOG)
        self.assertEqual(contexte.exception.methode, "TRACE")

    def test_methode_qui_n_est_pas_un_texte(self):
        with self.assertRaises(hj.RequeteRefusee) as contexte:
            self.client().requete(None, "/rest/api/3/field")
        self.assertEqual(str(contexte.exception), "requête Jira refusée : écriture interdite (?)")

    def test_authentification_non_conforme(self):
        with self.assertRaises(hj.RequeteRefusee) as sans:
            self.client(authentifie=False).requete("GET", "/rest/api/3/field")
        with self.assertRaises(hj.RequeteRefusee) as avec:
            self.client().requete("GET", "/_edge/tenant_info")
        self.assertEqual((sans.exception.genre, avec.exception.genre), ("read", "read"))
        self.assertEqual(self.faux.brut, [])

    def test_options_limitees_aux_parametres_et_au_corps(self):
        client = self.client()
        for option in ({"data": "x=1"}, {"files": {"f": "x"}}, {"auth": ("a", "b")}, {"headers": {"X": "1"}}, {"cookies": {}}):
            with self.assertRaises(hj.RequeteRefusee) as contexte:
                client.requete("POST", RECHERCHE, json={"jql": "project = PRJA"}, **option)
            self.assertEqual(contexte.exception.genre, "option")
            self.assertEqual(str(contexte.exception), "requête Jira refusée : option non permise")
        self.assertEqual(self.faux.brut, [])

    def test_phrases_d_ecriture_dans_les_deux_langues(self):
        for langue, attendu in (("fr", "requête Jira refusée : écriture interdite (DELETE)"),
                                ("en", "Jira request refused: write forbidden (DELETE)")):
            hj.set_language(langue)
            with self.assertRaises(hj.RequeteRefusee) as contexte:
                self.client().requete("delete", CHANGELOG)
            self.assertEqual(str(contexte.exception), attendu)
            for interdit in ("PRJA", "changelog", base.JETON):
                self.assertNotIn(interdit, str(contexte.exception))

    def test_phrases_de_lecture_hors_liste_dans_les_deux_langues(self):
        for langue, attendu in (("fr", "requête Jira refusée : hors de la liste des lectures permises (GET)"),
                                ("en", "Jira request refused: outside the list of allowed reads (GET)")):
            hj.set_language(langue)
            for chemin, client in (("/rest/api/3/dashboard", self.client()), ("/_edge/tenant_info", self.client()),
                                   ("/rest/api/3/issue/PRJA-1/changelog/../x", self.client())):
                with self.assertRaises(hj.RequeteRefusee) as contexte:
                    client.requete("GET", chemin)
                self.assertEqual(str(contexte.exception), attendu)
                for interdit in ("PRJA", "dashboard", base.JETON):
                    self.assertNotIn(interdit, str(contexte.exception))

    def test_un_appelant_qui_demande_un_chemin_d_ecriture_est_refuse(self):
        def appelant(client, cles):
            return client.json("PUT", f"/rest/api/3/issue/{cles[0]}", json={"fields": {}})
        with self.assertRaises(hj.RequeteRefusee):
            appelant(self.client(), ["PRJA-1"])
        self.assertEqual(self.faux.brut, [])


class CodesDeSortie(Fond):
    def charger(self, n=2):
        self.ecrire_reglages("scopes", garde=GARDE_PRJ)
        lignes = []
        for i in range(1, n + 1):
            self.faux.ajouter(f"PRJA-{i}")
            lignes.append((f"PRJA-{i}", "Story", "Equipe Test", False))
        self.ecrire_export(lignes)

    def test_refus_pendant_test_code_5_et_phrase_en_entier(self):
        self.ecrire_reglages("scopes", garde=GARDE_PRJ)
        with mock.patch.object(hj, "sonder", lambda client, methode, chemin, **kw: client.requete("PUT", chemin)):
            code, sortie = self.lancer("test", "--language", "en")
        self.assertEqual(code, 5)
        self.assertIn("Jira request refused: write forbidden (PUT)", sortie)
        self.assertNotIn("Unexpected error", sortie)

    def test_refus_pendant_collect_code_5_rien_d_ecrit_meme_en_mode_strict(self):
        self.charger()
        for options in ((), ("--strict",)):
            self.faux.brut.clear()
            with mock.patch.object(hj, "valeurs_courantes",
                                   lambda client, cles, etiquettes: client.requete("DELETE", CHANGELOG)):
                code, sortie = self.lancer("collect", *options)
            self.assertEqual(code, 5, sortie)
            self.assertIn("requête Jira refusée : écriture interdite (DELETE)", sortie)
            self.assertNotIn("erreurs", sortie)
            self.assertEqual((self.magasin.ecritures, self.magasin.passages, self.cache()), (0, [], {}))
            self.assertEqual([m for m, _, _ in self.faux.brut if m not in ("GET", "POST")], [])
            self.assertEqual(self.attentes, [])

    def test_refus_de_lecture_code_5_en_francais_et_en_anglais(self):
        self.charger()
        with mock.patch.object(hj, "valeurs_courantes", lambda client, cles, etiquettes: client.requete("GET", "/rest/api/3/dashboard")):
            code, sortie = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 5)
        self.assertIn("Jira request refused: outside the list of allowed reads (GET)", sortie)


class Sondes(Fond):
    def charger(self, n=3, extra=""):
        self.ecrire_reglages("scopes", extra=extra, garde=GARDE_PRJ)
        lignes = []
        for i in range(1, n + 1):
            self.faux.ajouter(f"PRJA-{i}")
            lignes.append((f"PRJA-{i}", "Story", "Equipe Test", False))
        self.ecrire_export(lignes)

    def test_sonde_de_test(self):
        self.ecrire_reglages("scopes", garde=GARDE_PRJ)
        code, sortie = self.lancer("test")
        self.assertEqual(code, 0, sortie)
        self.verifier_sonde()

    def test_sonde_de_test_envoie_le_premier_projet_declare(self):
        """R-20261028-111 : `project = <premier projet de scope_projects> ORDER BY created DESC`, un résultat."""
        self.ecrire_reglages("scopes", garde=["scope_projects: [PRJB, PRJA]", "forbidden_projects: [SUPX]"])
        recues = []
        original = hj.Client.requete

        def espion(client, methode, chemin, **kwargs):
            recues.append((chemin, kwargs.get("params")))
            return original(client, methode, chemin, **kwargs)
        with mock.patch.object(hj.Client, "requete", espion):
            code, _ = self.lancer("test")
        self.assertEqual(code, 0)
        recherche = next(p for c, p in recues if c == RECHERCHE)
        self.assertEqual((recherche["jql"], recherche["maxResults"]), ("project = PRJB ORDER BY created DESC", 1))

    def test_sonde_de_collect_mode_groupe_et_historique_groupe_par_cles(self):
        self.charger()
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.verifier_sonde()
        groupes = [c for api, c in self.faux.corps if api == "/rest/api/3/changelog/bulkfetch"]
        self.assertTrue(groupes)
        for corps in groupes:                      # R-20261028-105 : des clés déclarées, jamais un identifiant numérique
            self.assertTrue(corps["issueIdsOrKeys"])
            for cle in corps["issueIdsOrKeys"]:
                self.assertRegex(cle, r"^PRJA-[0-9]+$")

    def test_sonde_de_collect_ticket_par_ticket(self):
        self.charger()
        self.faux.groupe = False
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.verifier_sonde()
        self.assertTrue(any(p.endswith("/changelog") for _, p in self.paires_vues()))

    def test_sonde_de_collect_avec_pagination(self):
        self.charger(5)
        self.faux.pages_groupees = 2
        self.faux.taille_recherche = 2
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.verifier_sonde()

    def test_sonde_de_collect_apres_une_reponse_limitee(self):
        self.charger()
        self.faux.limite_429 = 2
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.verifier_sonde()
        self.assertTrue(self.attentes)

    def test_sonde_de_collect_avec_etiquettes_declarees(self):
        self.charger(extra=DECLAREES)
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.verifier_sonde()

    def test_copies_alignees_sur_les_constantes_des_autres_suites(self):
        """PAIRES_EXPORT et PAIRES_QUALITE sont égales aux PAIRES_ATTENDUES des deux autres suites (la source), lues dans leur code."""
        racine = Path(__file__).resolve().parents[1]
        for copie, fichier in ((PAIRES_EXPORT, racine / "export_jira_api" / "test_lecture_seule.py"),
                               (PAIRES_QUALITE, racine / "story_quality" / "test_lecture_seule.py")):
            arbre = ast.parse(fichier.read_text(encoding="utf-8"))
            texte = {}
            attendues = None
            for noeud in arbre.body:
                if isinstance(noeud, ast.Assign) and len(noeud.targets) == 1 and isinstance(noeud.targets[0], ast.Name):
                    nom = noeud.targets[0].id
                    if nom == "PAIRES_ATTENDUES":
                        attendues = eval(compile(ast.Expression(noeud.value), str(fichier), "eval"), {}, dict(texte))   # noqa: S307
                    elif isinstance(noeud.value, ast.Constant) and isinstance(noeud.value.value, str):
                        texte[nom] = noeud.value.value
            self.assertIsNotNone(attendues, f"PAIRES_ATTENDUES introuvable dans {fichier.name}")
            self.assertEqual(copie, attendues, f"écart avec la source {fichier.parent.name}")

    def test_couverture_de_la_liste_par_les_sondes_des_trois_suites(self):
        """L'union des paires vues par les sondes de cette suite et des deux autres (PAIRES_EXPORT, PAIRES_QUALITE) est la liste ; une
        entrée vue nulle part échoue et est nommée."""
        self.ecrire_reglages("scopes", garde=GARDE_PRJ)
        self.lancer("test")
        vues = self.entrees_vues()
        for groupe in (True, False):
            self.charger(2)
            self.faux.groupe = groupe
            self.faux.brut.clear()
            self.lancer("collect", "--refresh")
            vues |= self.entrees_vues()
        autres = set()
        for m, chemin in PAIRES_EXPORT | PAIRES_QUALITE:
            autres |= {(methode, motif) for methode, motif, _ in hj.lectures_autorisees()
                       if methode == m and re.fullmatch(motif, chemin)}
        tout = {(m, p) for m, p, _ in hj.lectures_autorisees()}
        manquantes = tout - vues - autres
        self.assertEqual(manquantes, set(), f"entrée de la liste vue par aucune sonde : {sorted(manquantes)}")


class GardeDesReglages(Fond):
    def refus_par_commande(self, garde, reglage):
        self.ecrire_reglages("scopes", garde=garde)
        self.ecrire_export([("PRJA-1", "Story", "Equipe Test", False)])
        self.faux.ajouter("PRJA-1")
        for commande in (("test",), ("collect",)):
            self.faux.brut.clear()
            code, sortie = self.lancer(*commande)
            self.assertEqual(code, 6, (commande, sortie))
            self.assertIn(f"requête Jira refusée : réglage absent, vide ou illisible ({reglage})", sortie)
            self.assertEqual(self.faux.brut, [], commande)           # aucune requête, pas même la lecture du cloudId
        code, sortie = self.lancer("test", "--language", "en")
        self.assertIn(f"Jira request refused: setting missing, empty or unreadable ({reglage})", sortie)
        return sortie

    def test_scope_projects_absent_vide_ou_illisible(self):
        for garde in (["forbidden_projects: [SUPX]"], ["scope_projects: []", "forbidden_projects: [SUPX]"],
                      ["scope_projects: PRJA", "forbidden_projects: [SUPX]"], ["scope_projects: [PRJA, '']", "forbidden_projects: [SUPX]"],
                      ["scope_projects: [PRJA, 7]", "forbidden_projects: [SUPX]"]):
            self.refus_par_commande(garde, "scope_projects")

    def test_forbidden_projects_absent_vide_ou_illisible(self):
        for garde in (["scope_projects: [PRJA]"], ["scope_projects: [PRJA]", "forbidden_projects: []"],
                      ["scope_projects: [PRJA]", "forbidden_projects: SUPX"], ["scope_projects: [PRJA]", "forbidden_projects: [SUPX, 3]"],
                      ["scope_projects: [PRJA]", "forbidden_projects: ['']"]):
            sortie = self.refus_par_commande(garde, "forbidden_projects")
            self.assertNotIn("SUPX", sortie)

    def test_cles_de_reglage_en_majuscules_seulement(self):
        """Revue 7.1 : une clé de projet d'un réglage est `[A-Z][A-Z0-9_]*` ; une clé en minuscules est un réglage illisible."""
        self.refus_par_commande(["scope_projects: [prja]", "forbidden_projects: [SUPX]"], "scope_projects")
        self.refus_par_commande(["scope_projects: [PRJA, Prjb]", "forbidden_projects: [SUPX]"], "scope_projects")
        self.refus_par_commande(["scope_projects: [PRJA]", "forbidden_projects: [supx]"], "forbidden_projects")

    def test_collect_verifie_les_deux_reglages_meme_sans_rien_a_interroger(self):
        """Revue 7.1 : `collecter` lit la garde en tête ; une base vide ou à jour ne la contourne pas."""
        for garde, reglage in ((["scope_projects: [PRJA]"], "forbidden_projects"), (["forbidden_projects: [SUPX]"], "scope_projects")):
            self.ecrire_reglages("scopes", garde=garde)
            code, sortie = self.lancer("collect", "--language", "en")          # aucun ticket dans la base fictive
            self.assertEqual(code, 6, sortie)
            self.assertIn(f"setting missing, empty or unreadable ({reglage})", sortie)
        self.ecrire_reglages("scopes", garde=GARDE_PRJ)
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 1, sortie)                                      # les réglages sont bons : la base vide reste l'erreur d'avant
        self.assertIn("aucun ticket dans la base", sortie)

    def test_forbidden_projects_lu_avant_scope_projects(self):
        sortie = self.refus_par_commande(["forbidden_projects: []"], "forbidden_projects")
        self.assertNotIn("scope_projects", sortie)

    def test_construire_client_ne_construit_aucun_client_et_lit_les_listes(self):
        self.ecrire_reglages("scopes", garde=GARDE_PRJ)
        client = hj.construire_client(hj.reglages())
        self.assertEqual((client.projets, client.interdits), (frozenset({"PRJA", "PRJB"}), frozenset({"SUPX"})))
        self.ecrire_reglages("scopes", garde=["scope_projects: [PRJA]"])
        with self.assertRaises(hj.RequeteHorsPerimetre) as contexte:
            hj.construire_client(hj.reglages())
        self.assertEqual(contexte.exception.genre, "setting")
        self.assertNotIsInstance(contexte.exception, hj.ErreurHTTP)
        self.assertEqual(self.faux.brut, [])

    def test_la_liste_n_a_aucun_repli_sur_la_base(self):
        """Les tickets de la base sont d'un autre projet (OTHER) : la liste du client reste celle du réglage."""
        self.ecrire_reglages("scopes", garde=GARDE_PRJ)
        self.ecrire_export([("OTHER-1", "Story", "Equipe Test", False)])
        self.assertEqual(hj.construire_client(hj.reglages()).projets, frozenset({"PRJA", "PRJB"}))


class RechercheLimitee(Fond):
    PHRASE_FR = "requête Jira refusée : hors des projets déclarés du périmètre"
    PHRASE_EN = "Jira request refused: outside the declared scope projects"

    def refuse(self, jql, methode="GET", client=None, **champs):
        client = client or self.client()
        avant = len(self.faux.brut)
        with self.assertRaises(hj.RequeteHorsPerimetre) as contexte:
            if champs:
                client.requete("GET", RECHERCHE, params=champs)
            else:
                self.recherche(client, jql, methode)
        self.assertEqual(len(self.faux.brut), avant, jql)
        self.assertEqual(contexte.exception.genre, "scope")
        self.assertNotIsInstance(contexte.exception, (hj.ErreurHTTP, hj.RequeteRefusee))
        return contexte.exception

    def test_requete_restreinte_passe(self):
        for methode in ("GET", "POST"):
            self.recherche(self.client(), "project in (PRJA, PRJB) AND (status = Done) ORDER BY created", methode)
        self.recherche(self.client(), 'PROJECT = "PRJA"')
        self.recherche(self.client(), "key in (PRJA-1, PRJB-2)")
        self.recherche(self.client(), "project = PRJA ORDER BY created DESC")
        self.recherche(self.client(), 'project = PRJA AND (summary ~ "a)b" OR (x = 1))')
        self.recherche(self.client(), 'project = PRJA AND (summary ~ "a\\"b)" OR (x = 1))')     # un guillemet échappé reste dans la chaîne
        self.assertEqual(len(self.faux.brut), 7)

    def test_requetes_non_restreintes_ou_elargies_refusees(self):
        for jql in ("status = Done", "project = PRJA OR project = OTHER", "project in (PRJA, OTHER)",
                    "project = PRJA AND status = Done OR key = OTHER-1", "NOT project = OTHER", "project in ()",
                    "project = PRJA AND (status = Done) AND key = OTHER-1", "project = PRJA AND (status = Done) OR (key = OTHER-1)",
                    "key in (PRJA-1, OTHER-2)", "key = OTHER-1", "project = PRJAB", "project = PRJA ORDER BY created, (x)",
                    'project = PRJA AND (a ~ b\\") OR project = 10042 OR (c ~ "\\"")',      # revue 7.1, B1 : « \ » hors chaîne
                    'project = PRJA AND (a = 1) ORDER BY created\\', 'project = PRJA AND (text ~ "\\u0053UPX-1")',
                    'project = PRJA AND (text ~ "\\u0041")',                                   # échappement \u : refusé
                    "project = PRJA AND (status = Done", "", "  "):
            for methode in ("GET", "POST"):
                self.refuse(jql, methode)
        for options in ({"params": {"jql": 7}}, {"params": {"maxResults": 1}}, {"json": {"fields": ["key"]}}, {}):
            with self.assertRaises(hj.RequeteHorsPerimetre):
                self.client().requete("POST" if "json" in options else "GET", RECHERCHE, **options)
        self.assertEqual(self.faux.brut, [])

    def test_changelog_et_changelog_groupe(self):
        client = self.client()
        with self.assertRaises(hj.RequeteHorsPerimetre):
            client.requete("GET", "/rest/api/3/issue/OTHER-1/changelog")
        for cles in (["PRJA-1", "OTHER-1"], ["10001"], ["PRJA-1", 10002], [], "PRJA-1"):
            with self.assertRaises(hj.RequeteHorsPerimetre):
                client.requete("POST", "/rest/api/3/changelog/bulkfetch", json={"issueIdsOrKeys": cles})
        with self.assertRaises(hj.RequeteHorsPerimetre):
            client.requete("POST", "/rest/api/3/changelog/bulkfetch", json={})
        self.assertEqual(self.faux.brut, [])
        client.requete("POST", "/rest/api/3/changelog/bulkfetch", json={"issueIdsOrKeys": ["PRJA-1", "PRJB-2"], "fieldIds": ["status"]})
        client.requete("GET", CHANGELOG)
        self.assertEqual(len(self.faux.brut), 2)

    def test_phrases_dans_les_deux_langues_sans_requete_ni_cle(self):
        for langue, phrase in (("fr", self.PHRASE_FR), ("en", self.PHRASE_EN)):
            hj.set_language(langue)
            erreur = self.refuse("status = Done")
            self.assertEqual(str(erreur), phrase)
            for interdit in ("Done", "status", "PRJA", "OTHER"):
                self.assertNotIn(interdit, str(erreur))

    def test_le_refus_de_la_liste_l_emporte_avec_le_code_5(self):
        with self.assertRaises(hj.RequeteRefusee) as contexte:
            self.client().requete("PUT", "/rest/api/3/issue/OTHER-1/changelog")
        self.assertEqual(contexte.exception.genre, "write")
        self.assertEqual(self.faux.brut, [])
        self.ecrire_reglages("scopes", garde=GARDE_PRJ)
        with mock.patch.object(hj, "sonder", lambda client, m, c, **kw: client.requete("PUT", "/rest/api/3/issue/OTHER-1/changelog")):
            code, sortie = self.lancer("test")
        self.assertEqual(code, 5, sortie)

    def test_refus_pendant_test_code_6(self):
        self.ecrire_reglages("scopes", garde=GARDE_PRJ)
        with mock.patch.object(hj, "sonder", lambda client, m, c, **kw: self.recherche(client, "status = Done")):
            code, sortie = self.lancer("test")
            self.assertEqual(code, 6, sortie)
            self.assertIn(self.PHRASE_FR, sortie)
            code, sortie = self.lancer("test", "--language", "en")
            self.assertEqual(code, 6)
            self.assertIn(self.PHRASE_EN, sortie)

    def test_projet_refuse_cite_n_importe_ou(self):
        for jql in ("project = PRJA AND (issue in linkedIssues(SUPX-1))", 'project = PRJA AND (text ~ "supx")', "project = SUPX",
                    "project in (PRJA, supx)", 'project = PRJA AND (summary ~ "SUPX-12 est lié")'):
            erreur = self.refuse(jql)
            self.assertEqual(str(erreur), self.PHRASE_FR)
            self.assertNotIn("SUPX", str(erreur))

    def test_projet_refuse_meme_declare(self):
        client = self.client(projets=("PRJA", "SUPX"), interdits=("SUPX",))
        self.refuse("project = SUPX", client=client)
        with self.assertRaises(hj.RequeteHorsPerimetre):
            client.requete("GET", "/rest/api/3/issue/SUPX-1/changelog")
        with self.assertRaises(hj.RequeteHorsPerimetre):
            client.requete("POST", "/rest/api/3/changelog/bulkfetch", json={"issueIdsOrKeys": ["SUPX-1"]})
        self.assertEqual(self.faux.brut, [])


class FiltreDesReponses(Fond):
    def lire(self, corps, **options):
        self.faux.recherche_imposee = corps
        client = self.client(**options)
        reponse = self.recherche(client, "project = PRJA")
        return client, reponse.json()

    def test_ticket_d_un_autre_projet_retire_et_compte(self):
        corps = {"issues": [ticket("PRJA-1", "1"), ticket("PRJA-2", "2"), ticket("OTHER-1", "3")], "nextPageToken": "t"}
        client, rendu = self.lire(corps)
        self.assertEqual([t["key"] for t in rendu["issues"]], ["PRJA-1", "PRJA-2"])
        self.assertEqual((client.tickets_hors_perimetre, rendu["nextPageToken"]), (1, "t"))
        self.assertNotIn("OTHER", json.dumps(rendu))

    def test_ticket_sans_cle_ou_a_cle_mal_formee_retire(self):
        client, rendu = self.lire({"issues": [{"id": "1", "fields": {}}, ticket("pas une cle"), ticket("PRJA-1"), "x", ticket("PRJA-1-2")]})
        self.assertEqual([t["key"] for t in rendu["issues"]], ["PRJA-1"])
        self.assertEqual(client.tickets_hors_perimetre, 4)

    def test_aucun_retrait_aucun_compte(self):
        client, rendu = self.lire({"issues": [ticket("PRJA-1"), ticket("PRJB-2")]})
        self.assertEqual((len(rendu["issues"]), client.tickets_hors_perimetre), (2, 0))

    def test_lien_reduit_a_la_cle_et_au_type(self):
        lien = {"id": "5", "type": {"name": "Blocks", "inward": "is blocked by"}, "outwardIssue": lie("OTHER-7")}
        _, rendu = self.lire({"issues": [ticket("PRJA-1", issuelinks=[lien])]})
        sortie = rendu["issues"][0]["fields"]["issuelinks"][0]
        self.assertEqual(sortie["type"], lien["type"])
        self.assertEqual(sortie["outwardIssue"], {"key": "OTHER-7", "fields": {"issuetype": {"name": "Bug"}}})
        texte = json.dumps(rendu)
        for interdit in ("Titre secret", "High", "Open", "exemple.invalid", "999"):
            self.assertNotIn(interdit, texte)

    def test_parent_et_sous_tache_reduits_a_la_cle_et_au_type(self):
        _, rendu = self.lire({"issues": [ticket("PRJA-1", parent=lie("OTHER-3"), subtasks=[lie("PRJA-9")])]})
        champs = rendu["issues"][0]["fields"]
        self.assertEqual(champs["parent"], {"key": "OTHER-3", "fields": {"issuetype": {"name": "Bug"}}})
        self.assertEqual(champs["subtasks"], [{"key": "PRJA-9", "fields": {"issuetype": {"name": "Bug"}}}])
        for interdit in ("Titre secret", "High", "Open"):
            self.assertNotIn(interdit, json.dumps(rendu))

    def test_projet_refuse_retire_des_reponses_avec_ses_liens_parent_et_sous_taches(self):
        corps = {"issues": [ticket("PRJA-1", issuelinks=[{"type": {"name": "Blocks"}, "inwardIssue": lie("SUPX-4")},
                                                          {"type": {"name": "Relates"}, "outwardIssue": lie("PRJA-2")}],
                            parent=lie("SUPX-2")),
                           ticket("SUPX-5")]}
        client, rendu = self.lire(corps)
        self.assertEqual(client.tickets_hors_perimetre, 3)
        champs = rendu["issues"][0]["fields"]
        self.assertEqual([lien["type"]["name"] for lien in champs["issuelinks"]], ["Relates"])
        self.assertNotIn("parent", champs)
        self.assertNotIn("SUPX", json.dumps(rendu))
        client, rendu = self.lire({"issues": [ticket("PRJA-1", subtasks=[lie("SUPX-8"), lie("PRJA-3")])]})
        self.assertEqual([t["key"] for t in rendu["issues"][0]["fields"]["subtasks"]], ["PRJA-3"])
        self.assertEqual(client.tickets_hors_perimetre, 1)

    def test_projet_refuse_meme_declare_retire_de_la_reponse(self):
        client, rendu = self.lire({"issues": [ticket("SUPX-1"), ticket("PRJA-1")]}, projets=("PRJA", "SUPX"))
        self.assertEqual([t["key"] for t in rendu["issues"]], ["PRJA-1"])
        self.assertEqual(client.tickets_hors_perimetre, 1)

    def test_reference_refusee_dans_un_champ_personnalise_imbriquee(self):
        corps = {"issues": [ticket("PRJA-1", customfield_10099={"liste": [{"texte": "voir SUPX-123 et plus"}]})]}
        client, rendu = self.lire(corps)
        self.assertEqual(rendu["issues"][0]["fields"]["customfield_10099"], {"liste": [{"texte": "voir [ticket-refusé] et plus"}]})
        self.assertEqual(client.references_remplacees, 1)
        self.assertNotIn("SUPX", json.dumps(rendu))

    def test_reference_refusee_dans_la_description(self):
        corps = {"issues": [ticket("PRJA-1", description={"type": "doc", "content": [{"text": "lié à SUPX-45"}]})]}
        client, rendu = self.lire(corps)
        self.assertIn("lié à [ticket-refusé]", json.dumps(rendu, ensure_ascii=False))
        self.assertEqual(client.references_remplacees, 1)
        self.assertNotIn("SUPX", json.dumps(rendu))

    def test_reference_refusee_dans_le_titre(self):
        client, rendu = self.lire({"issues": [ticket("PRJA-1", summary="Suite de SUPX-7")]})
        self.assertEqual(rendu["issues"][0]["fields"]["summary"], "Suite de [ticket-refusé]")
        self.assertEqual(client.references_remplacees, 1)
        self.assertNotIn("SUPX", json.dumps(rendu))

    def test_reference_refusee_en_minuscules_remplacee_et_borne_de_mot_respectee(self):
        corps = {"issues": [ticket("PRJA-1", summary="a supx-9 b", customfield_10099="XSUPX-12 et SUPX-12Y")]}
        client, rendu = self.lire(corps)
        champs = rendu["issues"][0]["fields"]
        self.assertEqual(champs["summary"], "a [ticket-refusé] b")
        # R-20261029-03 : borne avant seulement ; rien n'est exigé après les chiffres
        self.assertEqual(champs["customfield_10099"], "XSUPX-12 et [ticket-refusé]Y")
        self.assertEqual(client.references_remplacees, 2)

    def test_reference_refusee_suivie_d_une_lettre_ou_d_un_tiret_bas_remplacee(self):
        corps = {"issues": [ticket("PRJA-1", summary="SUPX-12Y puis SUPX-12_x")]}
        client, rendu = self.lire(corps)
        self.assertEqual(rendu["issues"][0]["fields"]["summary"], "[ticket-refusé]Y puis [ticket-refusé]_x")
        self.assertEqual(client.references_remplacees, 2)

    def test_deux_cles_refusees_distinctes_et_occurrences_multiples_dans_une_chaine(self):
        corps = {"issues": [ticket("PRJA-1", summary="SUPX-1, SUPY-2 et supx-3", customfield_10099=["SUPY-4 SUPY-5"])]}
        client, rendu = self.lire(corps, interdits=("SUPX", "SUPY"))
        champs = rendu["issues"][0]["fields"]
        self.assertEqual(champs["summary"], "[ticket-refusé], [ticket-refusé] et [ticket-refusé]")
        self.assertEqual(champs["customfield_10099"], ["[ticket-refusé] [ticket-refusé]"])
        self.assertEqual(client.references_remplacees, 5)
        self.assertNotIn("SUP", json.dumps(rendu))


class RemplacementToutesNatures(Fond):
    """R-20261029-03 : le remplacement D11 s'applique à toute réponse 2xx lisible, quelle que soit la nature."""

    def planter(self, histo):
        self.faux.tickets["PRJA-1"] = ("10001", histo)

    def test_changelog_ticket_par_ticket(self):
        self.planter([{"id": "11", "created": "2026-01-10T09:00:00.000+0200",
                       "items": [{"field": "Link", "fromString": None, "toString": "This issue relates to SUPX-12 et supx-13"}]}])
        client = self.client()
        rendu = client.requete("GET", CHANGELOG).json()
        texte = json.dumps(rendu, ensure_ascii=False)
        self.assertIn("relates to [ticket-refusé] et [ticket-refusé]", texte)
        self.assertEqual(client.references_remplacees, 2)
        self.assertNotIn("SUPX", texte.upper())

    def test_bulkfetch_etiquette_et_nom_de_version(self):
        self.planter([{"id": "11", "created": "2026-01-10T09:00:00.000+0200",
                       "items": [{"field": "labels", "fromString": "", "toString": "suite-de-SUPX-7"},
                                 {"field": "Fix Version", "fromString": "SUPX-8", "toString": "v1"}]}])
        client = self.client()
        rendu = client.requete("POST", "/rest/api/3/changelog/bulkfetch", json={"issueIdsOrKeys": ["PRJA-1"]}).json()
        texte = json.dumps(rendu, ensure_ascii=False)
        self.assertIn("suite-de-[ticket-refusé]", texte)
        self.assertIn('"fromString": "[ticket-refusé]"', texte)
        self.assertEqual(client.references_remplacees, 2)
        self.assertNotIn("SUPX", texte.upper())
        self.assertEqual(client.tickets_hors_perimetre, 0)      # le filtre D9 reste propre à la recherche

    def test_collect_ecarte_un_ticket_d_un_autre_projet_sans_trace_ni_ligne_a_zero(self):
        self.ecrire_reglages("scopes", garde=["scope_projects: [ABC]", "forbidden_projects: [SUPX]"])
        self.ecrire_export(self.inventer(1))
        sans = self.lancer("collect", "--refresh")
        self.assertNotIn("hors des projets déclarés", sans[1])
        planté = {"issues": [ticket("ABC-1", "10001", fixVersions=[], labels=[]), ticket("OTHER-9", "99")]}
        # planté dans la lecture des valeurs courantes seulement (la recherche des clés garde sa réponse usuelle) : un seul retrait
        self.faux.recherche_imposee = lambda corps: planté if corps.get("fields") != ["key"] else None
        for langue, ligne in (("fr", "tickets hors des projets déclarés écartés : 1"),
                              ("en", "tickets outside the declared projects set aside: 1")):
            code, sortie = self.lancer("collect", "--refresh", "--language", langue)
            self.assertEqual(code, 0, sortie)
            self.assertIn(ligne, sortie)
            for texte in (sortie, self.tous_les_fichiers(), repr(self.magasin.transitions), repr(self.magasin.periodes)):
                self.assertNotIn("OTHER", texte)

    def test_collect_hors_perimetre_n_ecrit_rien_code_6_meme_en_mode_strict(self):
        self.ecrire_reglages("scopes", garde=GARDE_PRJ)
        self.ecrire_export([("OTHER-1", "Story", "Equipe Test", False)])
        for options in ((), ("--strict",)):
            code, sortie = self.lancer("collect", *options)
            self.assertEqual(code, 6, sortie)
            self.assertIn("requête Jira refusée : hors des projets déclarés du périmètre", sortie)
            self.assertNotIn("erreurs", sortie)
            self.assertNotIn("OTHER", sortie)
            self.assertEqual((self.magasin.ecritures, self.cache(), self.attentes), (0, {}, []))
            self.assertEqual(self.faux.brut, [])

    def test_collect_ticket_et_lien_du_projet_refuse_plantes_aucune_cle_en_sortie(self):
        self.ecrire_reglages("scopes", garde=["scope_projects: [ABC]", "forbidden_projects: [SUPX]"])
        self.ecrire_export(self.inventer(1))
        planté = {"issues": [
            ticket("ABC-1", "10001", fixVersions=[], labels=[], parent=lie("SUPX-2"),
                   issuelinks=[{"type": {"name": "Blocks"}, "inwardIssue": lie("SUPX-4")}]), ticket("SUPX-5", "98")]}
        self.faux.recherche_imposee = lambda corps: planté if corps.get("fields") != ["key"] else None
        code, sortie = self.lancer("collect", "--refresh")
        self.assertEqual(code, 0, sortie)
        self.assertIn("tickets hors des projets déclarés écartés : 3", sortie)
        for texte in (sortie, self.tous_les_fichiers(), repr(self.magasin.transitions)):
            self.assertNotIn("SUPX", texte)


class AccesUnique(unittest.TestCase):
    """Test statique du client unique (design D5), sur `tools/` : ast pour les .py, texte sans commentaires pour les .sh."""

    PASSERELLE = ("api.atlassian.com", "atlassian.net", "/ex/jira", "_edge/tenant_info")
    CLIENT = ("history_jira.py", "history_jira_messages.py")
    BIBLIOTHEQUES = ("requests", "urllib.request", "urllib.error", "urllib3", "http.client", "httpx", "aiohttp", "socket")
    # Table des importeurs HTTP : fichier -> (bibliothèques, destination, raison). Elle est la source du test : un importeur absent
    # d'ici échoue, et une ligne dont le fichier n'importe plus rien échoue (ligne morte). Seul le client va à Jira.
    IMPORTEURS = {
        "history_jira.py": ({"requests"}, "Jira", "le client unique de Jira"),
        "composants.py": ({"http.client", "socket", "urllib.error", "urllib.request"}, "registres publics de paquets et machine locale",
                          "versions publiées des composants du laboratoire"),
        "cases_store.py": ({"httpx"}, "machine locale", "moteur d'empreintes local"),
        "pmzilla_lab_library.py": ({"httpx"}, "machine locale", "moteur d'empreintes local de la bibliothèque"),
        "story_quality_engine.py": ({"requests"}, "moteur d'analyse", "appel au moteur configuré de l'analyse"),
        "watch_lab.py": ({"httpx", "socket"}, "flux publics de la veille", "collecte de la veille"),
        "watch_triage.py": ({"httpx"}, "machine locale", "moteur local du tri de la veille"),
        "doctor.py": ({"socket", "urllib.error", "urllib.request"}, "machine locale", "sondes de santé du laboratoire"),
        "watch.sh": ({"curl"}, "machine locale", "présence du moteur local"),
        "evals_auto.sh": ({"curl"}, "machine locale", "présence du moteur local"),
    }

    @staticmethod
    def sources():
        return sorted(p for p in TOOLS.rglob("*") if p.suffix in (".py", ".sh") and p.is_file())

    @staticmethod
    def arbre(chemin):
        return ast.parse(chemin.read_text(encoding="utf-8"))

    @staticmethod
    def texte_shell(chemin):
        lignes = []
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            lignes.append(re.sub(r"(^|\s)#.*$", "", ligne))
        return "\n".join(lignes)

    @classmethod
    def litteraux(cls, arbre):
        """Chaînes littérales hors docstrings (les morceaux des f-strings compris)."""
        docstrings = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and noeud.body:
                premier = noeud.body[0]
                if isinstance(premier, ast.Expr) and isinstance(premier.value, ast.Constant) and isinstance(premier.value.value, str):
                    docstrings.add(id(premier.value))
        return [n.value for n in ast.walk(arbre)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]

    @classmethod
    def bibliotheques(cls, chemin):
        if chemin.suffix == ".sh":
            texte = cls.texte_shell(chemin)
            return {nom for nom in ("curl", "wget") if re.search(rf"\b{nom}\b", texte)}
        trouvees = set()
        for noeud in ast.walk(cls.arbre(chemin)):
            if isinstance(noeud, ast.Import):
                noms = [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                noms = [noeud.module] + [f"{noeud.module}.{a.name}" for a in noeud.names]
            else:
                continue
            trouvees |= {b for b in cls.bibliotheques_visees(noms)}
        return trouvees

    @classmethod
    def bibliotheques_visees(cls, noms):
        return {b for b in cls.BIBLIOTHEQUES for n in noms if n == b or n.startswith(b + ".")}

    def test_passerelle_nommee_par_le_client_seulement(self):
        fautifs = []
        for chemin in self.sources():
            if chemin.name in self.CLIENT:
                continue
            textes = self.litteraux(self.arbre(chemin)) if chemin.suffix == ".py" else [self.texte_shell(chemin)]
            if any(motif in texte for texte in textes for motif in self.PASSERELLE):
                fautifs.append(str(chemin.relative_to(TOOLS)))
        self.assertEqual(fautifs, [], "passerelle ou information du site nommée hors du client")

    def test_table_des_importeurs_est_la_source(self):
        trouves = {}
        for chemin in self.sources():
            libs = self.bibliotheques(chemin)
            if libs:
                trouves[chemin.name] = libs
        absents = sorted(set(trouves) - set(self.IMPORTEURS))
        self.assertEqual(absents, [], f"importeur HTTP absent de la table : {absents}")
        morts = sorted(f for f in self.IMPORTEURS if f not in trouves)
        self.assertEqual(morts, [], f"ligne morte de la table (le fichier n'importe plus rien) : {morts}")
        for fichier, (libs, _, _) in self.IMPORTEURS.items():
            self.assertEqual(trouves[fichier], libs, fichier)
        vers_jira = [f for f, (_, destination, _) in self.IMPORTEURS.items() if destination == "Jira"]
        self.assertEqual(vers_jira, ["history_jira.py"])

    def test_aucun_contournement_du_client(self):
        fautifs = []
        for chemin in self.sources():
            if chemin.suffix != ".py" or chemin.name == "history_jira.py":
                continue
            arbre = self.arbre(chemin)
            importe = any((isinstance(n, ast.Import) and any(a.name == "history_jira" for a in n.names))
                          or (isinstance(n, ast.ImportFrom) and n.module == "history_jira") for n in ast.walk(arbre))
            if importe and any(isinstance(n, ast.Attribute) and n.attr in ("requests", "session") for n in ast.walk(arbre)):
                fautifs.append(chemin.name)
        self.assertEqual(fautifs, [], "accès à .requests ou .session dans un fichier qui importe le client")

    def test_aucun_client_construit_hors_du_fichier_du_client(self):
        """Revue 7.1 : `Client(` n'est construit que dans tools/history_jira.py (les autres passent par `construire_client`)."""
        fautifs = []
        for chemin in self.sources():
            if chemin.suffix != ".py" or chemin.name == "history_jira.py":
                continue
            arbre = self.arbre(chemin)
            alias, direct = set(), False
            for n in ast.walk(arbre):
                if isinstance(n, ast.Import):
                    alias |= {a.asname or a.name for a in n.names if a.name == "history_jira"}
                elif isinstance(n, ast.ImportFrom) and n.module == "history_jira":
                    direct = direct or any(a.name == "Client" and a.asname is None for a in n.names)
            for n in ast.walk(arbre):
                if not isinstance(n, ast.Call):
                    continue
                f = n.func
                if (isinstance(f, ast.Attribute) and f.attr == "Client" and isinstance(f.value, ast.Name) and f.value.id in alias) \
                        or (direct and isinstance(f, ast.Name) and f.id == "Client"):
                    fautifs.append(chemin.name)
        self.assertEqual(fautifs, [], "Client( construit hors de tools/history_jira.py")

    def test_la_detection_nomme_un_importeur_et_une_ligne_morte(self):
        """Le test attrape ce qu'il doit attraper : un fichier fictif qui importe une bibliothèque, un autre qui n'en importe aucune."""
        import tempfile
        with tempfile.TemporaryDirectory() as dossier:
            neuf, vide = Path(dossier) / "neuf.py", Path(dossier) / "vide.py"
            neuf.write_text("import requests\nx = 'api.atlassian.com'\n", encoding="utf-8")
            vide.write_text("import json\n", encoding="utf-8")
            self.assertEqual(self.bibliotheques(neuf), {"requests"})
            self.assertEqual(self.bibliotheques(vide), set())
            self.assertTrue(any("atlassian" in t for t in self.litteraux(self.arbre(neuf))))


if __name__ == "__main__":
    unittest.main()
