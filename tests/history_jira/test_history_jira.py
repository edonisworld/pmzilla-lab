"""Tests de history_jira.py : un faux serveur HTTP local, des données inventées, un faux jeton.

    uv run --with pyyaml --with requests python -m unittest discover -s tests/history_jira -v

Aucun appel au vrai Jira. Le jeton factice (test-token-000) ne doit apparaître ni dans la sortie, ni dans le
cache, ni dans aucun fichier écrit ; l'auteur et les champs autres que status ne doivent jamais être gardés.
"""
import base64
import contextlib
import importlib.util
import io
import json
import os
import stat
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "history_jira.py"
spec = importlib.util.spec_from_file_location("history_jira", SCRIPT)
hj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hj)

JETON = "test-token-000"
EMAIL = "utilisateur@example.org"
CLOUD_ID = "cloud-123"
AUTEUR = "Personne Fictive"


def transitions_inventees(i: int) -> list[dict]:
    """Historique inventé d'un ticket : deux transitions de statut et un changement qui n'en est pas un."""
    base = f"2026-0{1 + i % 8}-10T09:00:00.000+0200"
    return [
        {"id": f"{i}1", "created": base, "author": {"displayName": AUTEUR, "emailAddress": "p@example.org"},
         "items": [{"field": "status", "fieldId": "status", "fromString": "Open", "toString": "In Progress"},
                   {"field": "assignee", "fieldId": "assignee", "fromString": None, "toString": AUTEUR}]},
        {"id": f"{i}2", "created": base.replace("T09", "T15"), "author": {"displayName": AUTEUR},
         "items": [{"field": "status", "fieldId": "status", "fromString": "In Progress", "toString": "Done"}]},
    ]


class FauxJira:
    """État partagé du faux serveur : tickets, comportements simulés et journal des appels."""

    def __init__(self):
        self.tickets = {}            # clé -> (identifiant, historiques)
        self.groupe = True           # False : l'API groupée répond 404
        self.pages_groupees = 1      # 2 : la réponse groupée est paginée
        self.entrees_par_page = 0    # > 0 : la réponse groupée est coupée toutes les n entrées d'historique (un ticket peut
                                     # être coupé entre deux pages)
        self.taille_recherche = 0    # > 0 : la recherche des clés rend n tickets par page, avec nextPageToken
        self.dates_epoch = False     # l'API groupée donne « created » en millisecondes depuis 1970 (format supposé réel)
        self.sans_islast = False     # l'historique ticket par ticket ne renvoie ni isLast ni total
        self.taille_page = 100       # taille des pages de l'historique ticket par ticket
        self.limite_429 = 0          # nombre d'appels API qui répondent 429 (Retry-After: 1) avant de répondre
        self.toujours_429 = False
        self.introuvables = set()    # clés dont l'historique ticket par ticket répond 404
        self.appels = []
        self.prefixe = ""
        self.attendu = "Basic " + base64.b64encode(f"{EMAIL}:{JETON}".encode()).decode()

    def ajouter(self, cle: str):
        i = len(self.tickets) + 1
        self.tickets[cle] = (str(10000 + i), transitions_inventees(i))


def fabriquer_serveur(faux: FauxJira):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def repondre(self, code, corps=None, entetes=None):
            donnees = json.dumps(corps if corps is not None else {}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(donnees)))
            for k, v in (entetes or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(donnees)

        def traiter(self, methode):
            chemin = urlparse(self.path)
            corps = {}
            if methode == "POST":
                taille = int(self.headers.get("Content-Length") or 0)
                corps = json.loads(self.rfile.read(taille) or b"{}")
            if chemin.path == "/_edge/tenant_info":
                faux.appels.append((methode, chemin.path))
                return self.repondre(200, {"cloudId": CLOUD_ID, "site": "Nom Fictif"})
            if self.headers.get("Authorization") != faux.attendu:
                return self.repondre(401, {"message": "Nom Fictif"})
            api = chemin.path[len(faux.prefixe):] if chemin.path.startswith(faux.prefixe) else chemin.path
            faux.appels.append((methode, api))
            if faux.toujours_429 or faux.limite_429 > 0:
                faux.limite_429 -= 1
                return self.repondre(429, {}, {"Retry-After": "1"})
            if api == "/rest/api/3/search/jql" and methode == "GET":
                return self.repondre(200, {"issues": [], "owner": "Nom Fictif"})
            if api == "/rest/api/3/search/jql" and methode == "POST":
                cles = corps["jql"][len("key in ("):-1].split(",")
                trouves = [{"id": faux.tickets[c][0], "key": c, "fields": {"summary": "Titre secret"}}
                           for c in cles if c in faux.tickets]
                if faux.taille_recherche:
                    debut = int(corps.get("nextPageToken") or 0)
                    fin = debut + faux.taille_recherche
                    suite = {"nextPageToken": str(fin)} if fin < len(trouves) else {}
                    return self.repondre(200, {"issues": trouves[debut:fin], **suite})
                return self.repondre(200, {"issues": trouves})
            if api == "/rest/api/3/changelog/bulkfetch":
                if not faux.groupe:
                    return self.repondre(404)
                ids = corps["issueIdsOrKeys"]
                def format_groupe(histo):
                    if not faux.dates_epoch:
                        return histo
                    import datetime as _dt
                    return [{**h, "created": int(_dt.datetime.strptime(h["created"], "%Y-%m-%dT%H:%M:%S.%f%z")
                                                 .timestamp() * 1000)} for h in histo]
                fiches = [{"issueId": ident, "changeHistories": format_groupe(histo)}
                          for _, (ident, histo) in faux.tickets.items() if ident in ids]
                if faux.entrees_par_page:
                    plat = [(ident, h) for _, (ident, histo) in faux.tickets.items() if ident in ids for h in histo]
                    debut = int(corps.get("nextPageToken") or 0)
                    fin = debut + faux.entrees_par_page
                    parties = {}
                    for ident, h in plat[debut:fin]:
                        parties.setdefault(ident, []).append(h)
                    suite = {"nextPageToken": str(fin)} if fin < len(plat) else {}
                    return self.repondre(200, {"issueChangeLogs": [
                        {"issueId": i, "changeHistories": hs} for i, hs in parties.items()], **suite})
                if faux.pages_groupees == 2:
                    moitie = max(1, len(fiches) // 2)
                    if not corps.get("nextPageToken"):
                        return self.repondre(200, {"issueChangeLogs": fiches[:moitie], "nextPageToken": "page2"})
                    return self.repondre(200, {"issueChangeLogs": fiches[moitie:]})
                return self.repondre(200, {"issueChangeLogs": fiches})
            if api.startswith("/rest/api/3/issue/") and api.endswith("/changelog"):
                cle = api.split("/")[5]
                if cle in faux.introuvables or cle not in faux.tickets:
                    return self.repondre(404)
                histo = faux.tickets[cle][1]
                debut = int(parse_qs(chemin.query).get("startAt", ["0"])[0])
                page = histo[debut:debut + faux.taille_page]
                if faux.sans_islast:
                    return self.repondre(200, {"values": page})
                return self.repondre(200, {"values": page, "isLast": debut + len(page) >= len(histo)})
            return self.repondre(404)

        def do_GET(self):
            self.traiter("GET")

        def do_POST(self):
            self.traiter("POST")

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


class Base(unittest.TestCase):
    def setUp(self):
        self.faux = FauxJira()
        self.serveur = fabriquer_serveur(self.faux)
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        self.addCleanup(self.serveur.server_close)
        self.addCleanup(self.serveur.shutdown)
        self.url = f"http://127.0.0.1:{self.serveur.server_address[1]}"
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        flux = self.ws / "Flux-Lab"
        flux.mkdir()
        patches = [mock.patch.object(hj, "WORKSPACE", self.ws), mock.patch.object(hj, "FLUX_DIR", flux),
                   mock.patch.object(hj, "CONFIG_FILE", flux / "flux.yaml"),
                   mock.patch.object(hj, "CACHE_DIR", flux / "historique"),
                   mock.patch.object(hj, "CACHE_FILE", flux / "historique" / "transitions.json"),
                   mock.patch.object(hj, "lire_jeton", lambda: JETON),
                   mock.patch.object(hj, "API_ATLASSIAN", self.url), mock.patch.object(hj, "PAUSE", 0),
                   mock.patch.object(hj, "_JETON", None)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.attentes = []
        p = mock.patch.object(hj.time, "sleep", lambda s: self.attentes.append(s))
        p.start()
        self.addCleanup(p.stop)
        self.ecrire_reglages("classique")

    def ecrire_reglages(self, mode: str, extra: str = ""):
        nouveau = {"scopes": "scoped", "classique": "classic"}.get(mode, mode)
        (self.ws / "Flux-Lab" / "flux.yaml").write_text(
            f"jira_site: {self.url}\njira_email: {EMAIL}\njira_token_type: {nouveau}\n{extra}", encoding="utf-8")
        self.faux.prefixe = f"/ex/jira/{CLOUD_ID}" if mode == "scopes" else ""

    def ecrire_export(self, lignes, nom="export.csv") -> str:
        """lignes : (clé, type, équipe, terminé). Les titres ne sont jamais écrits."""
        chemin = self.ws / nom
        chemin.write_text("Issue key,Issue Type,Status,Resolved,Team\n" + "".join(
            f"{c},{t},{'Done' if f else 'Open'},{'10/Sep/2026 10:00' if f else ''},{e}\n" for c, t, e, f in lignes),
            encoding="utf-8")
        return str(chemin)

    def lancer(self, *argv):
        sortie = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(sortie):
            try:
                hj.main(list(argv))
            except SystemExit as sortie_code:
                code = sortie_code.code or 0
        return code, sortie.getvalue()

    def cache(self) -> dict:
        return json.loads((self.ws / "Flux-Lab" / "historique" / "transitions.json").read_text(encoding="utf-8"))

    def tous_les_fichiers(self) -> str:
        return "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in self.ws.rglob("*")
                         if p.is_file() and p.name != "flux.yaml" and p.suffix != ".csv")

    def inventer(self, n: int, termines=()):
        lignes = []
        for i in range(1, n + 1):
            cle = f"ABC-{i}"
            self.faux.ajouter(cle)
            lignes.append((cle, "Story", "Equipe Test" if i % 2 else "Autre Equipe", cle in termines))
        return lignes


class Connexion(Base):
    def test_connexion_ok_sans_rien_afficher_d_autre(self):
        code, sortie = self.lancer("test")
        self.assertEqual((code, sortie.strip()), (0, "connexion OK"))

    def test_code_http_seulement(self):
        self.faux.attendu = "Basic autre"
        code, sortie = self.lancer("test")
        self.assertEqual((code, sortie.strip()), (1, "HTTP 401"))
        for interdit in ("Nom Fictif", self.url, EMAIL, JETON):
            self.assertNotIn(interdit, sortie)

    def test_mode_scopes_passe_par_le_cloud_id(self):
        self.ecrire_reglages("scopes")
        code, sortie = self.lancer("test")
        self.assertEqual((code, sortie.strip()), (0, "connexion OK"))
        self.assertIn(("GET", "/_edge/tenant_info"), self.faux.appels)
        self.assertNotIn(CLOUD_ID, sortie)

    def test_reglages_manquants_ne_montrent_aucune_valeur(self):
        (self.ws / "Flux-Lab" / "flux.yaml").write_text("jira_email: a@example.org\n", encoding="utf-8")
        code, sortie = self.lancer("test")
        self.assertEqual(code, 1)
        self.assertIn("jira_site", sortie)
        self.assertNotIn("a@example.org", sortie)

    def test_http_distant_refuse(self):
        (self.ws / "Flux-Lab" / "flux.yaml").write_text(
            f"jira_site: http://exemple.atlassian.net\njira_email: {EMAIL}\njira_token_type: classic\n", encoding="utf-8")
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
        self.assertEqual((code, sortie.strip()), (0, "connexion OK"))

    def test_anciens_noms_de_sous_commandes_refuses(self):
        for ancien in ("collecte", "controle"):
            code, sortie = self.lancer(ancien)
            self.assertEqual(code, 2, ancien)
            self.assertEqual(self.faux.appels, [])

    def test_message_du_reglage_manquant_donne_le_nouveau_nom(self):
        (self.ws / "Flux-Lab" / "flux.yaml").write_text(f"jira_site: {self.url}\njira_email: {EMAIL}\n", encoding="utf-8")
        code, sortie = self.lancer("test")
        self.assertEqual(code, 1)
        self.assertIn("jira_token_type", sortie)
        self.assertNotIn("jira_jeton", sortie)


class Collecte(Base):
    def test_groupee_ne_garde_que_date_et_etats(self):
        export = self.ecrire_export(self.inventer(5))
        code, sortie = self.lancer("collect", export)
        self.assertEqual(code, 0, sortie)
        cache = self.cache()
        self.assertEqual(len(cache), 5)
        for entree in cache.values():
            self.assertEqual(set(entree), {"termine", "transitions"})
            self.assertEqual(len(entree["transitions"]), 2)           # le changement d'assigné est écarté
            for transition in entree["transitions"]:
                self.assertEqual(len(transition), 3)
        self.assertEqual(cache["ABC-1"]["transitions"][0][1:], ["Open", "In Progress"])
        self.assertEqual(cache["ABC-1"]["transitions"][1][1:], ["In Progress", "Done"])
        self.assertIn("Mode : groupé", sortie)
        self.assertIn("Tickets traités : 5 ; transitions de statut : 10 ; erreurs : 0", sortie)

    def test_rien_de_sensible_dans_la_sortie_le_cache_ni_les_fichiers(self):
        export = self.ecrire_export(self.inventer(6))
        code, sortie = self.lancer("collect", export, "--team", "Equipe Test")
        self.assertEqual(code, 0, sortie)
        ecrit = self.tous_les_fichiers()
        for texte in (sortie, ecrit):
            for interdit in (JETON, AUTEUR, "p@example.org", "Titre secret", "Nom Fictif", "assignee", EMAIL):
                self.assertNotIn(interdit, texte)
        for texte in (sortie,):
            self.assertNotIn("ABC-", texte)                              # aucune clé dans le Terminal
            self.assertNotIn("Equipe Test", texte)                       # ni le nom de l'équipe
        self.assertNotIn(self.url, sortie)

    def test_pagination_groupee(self):
        self.faux.pages_groupees = 2
        export = self.ecrire_export(self.inventer(6))
        code, sortie = self.lancer("collect", export)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.cache()), 6)
        self.assertTrue(all(len(v["transitions"]) == 2 for v in self.cache().values()))

    def test_repli_ticket_par_ticket_avec_pagination(self):
        self.faux.groupe = False
        self.faux.taille_page = 1                                         # une page par transition
        export = self.ecrire_export(self.inventer(4))
        code, sortie = self.lancer("collect", export)
        self.assertEqual(code, 0, sortie)
        self.assertIn("Mode : ticket par ticket", sortie)
        self.assertTrue(all(len(v["transitions"]) == 2 for v in self.cache().values()))
        self.assertEqual(sum(1 for m, p in self.faux.appels if p.endswith("/changelog")), 8)   # 4 tickets, 2 pages

    def test_pagination_groupee_ticket_coupe_entre_deux_pages_et_recherche_paginee(self):
        self.faux.entrees_par_page = 3                                    # 2 entrées par ticket : un ticket sur deux est coupé
        self.faux.taille_recherche = 2
        export = self.ecrire_export(self.inventer(7))
        code, sortie = self.lancer("collect", export)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(len(self.cache()), 7)
        self.assertTrue(all(len(v["transitions"]) == 2 for v in self.cache().values()))
        self.assertEqual(sum(1 for m, p in self.faux.appels if p == "/rest/api/3/changelog/bulkfetch"), 5)   # 14 entrées / 3
        self.assertEqual(sum(1 for m, p in self.faux.appels if p == "/rest/api/3/search/jql" and m == "POST"), 4)

    def test_ticket_par_ticket_sans_islast_va_jusqu_a_la_page_vide(self):
        self.faux.groupe = False
        self.faux.taille_page = 1
        self.faux.sans_islast = True
        export = self.ecrire_export(self.inventer(2))
        code, sortie = self.lancer("collect", export)
        self.assertEqual(code, 0, sortie)
        self.assertTrue(all(len(v["transitions"]) == 2 for v in self.cache().values()))

    def test_rafraichir_ignore_le_cache(self):
        lignes = self.inventer(3, termines={"ABC-1", "ABC-2", "ABC-3"})
        export = self.ecrire_export(lignes)
        self.lancer("collect", export)
        self.faux.appels.clear()
        code, sortie = self.lancer("collect", export)
        self.assertEqual(self.faux.appels, [])                            # tout en cache et terminé
        code, sortie = self.lancer("collect", export, "--refresh")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Cache ignoré", sortie)
        self.assertIn("Tickets traités : 3", sortie)

    def test_incremental_ne_reinterroge_que_les_non_termines_ou_absents(self):
        lignes = self.inventer(4, termines={"ABC-1", "ABC-2"})
        export = self.ecrire_export(lignes[:3])
        self.lancer("collect", export)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-2", "ABC-3"})
        self.faux.appels.clear()
        code, sortie = self.lancer("collect", self.ecrire_export(lignes, "export2.csv"))
        self.assertEqual(code, 0, sortie)
        self.assertIn("Déjà en cache et terminés (non réinterrogés) : 2 ; à interroger : 2", sortie)
        recherche = [p for m, p in self.faux.appels if p == "/rest/api/3/search/jql"]
        self.assertEqual(len(recherche), 1)                               # un seul lot : ABC-3 (non terminé) et ABC-4 (absent)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-2", "ABC-3", "ABC-4"})

    def test_tout_en_cache_et_termine_aucun_appel(self):
        export = self.ecrire_export(self.inventer(3, termines={"ABC-1", "ABC-2", "ABC-3"}))
        self.lancer("collect", export)
        self.faux.appels.clear()
        code, sortie = self.lancer("collect", export)
        self.assertEqual(code, 0)
        self.assertEqual(self.faux.appels, [])

    def test_ticket_devenu_termine_est_reinterroge_une_fois(self):
        lignes = self.inventer(2)
        self.lancer("collect", self.ecrire_export(lignes))
        self.assertFalse(self.cache()["ABC-1"]["termine"])
        termine = [(c, t, e, c == "ABC-1") for c, t, e, _ in lignes]
        self.lancer("collect", self.ecrire_export(termine, "export2.csv"))
        self.assertTrue(self.cache()["ABC-1"]["termine"])

    def test_equipe_filtre_et_ne_montre_pas_le_nom(self):
        export = self.ecrire_export(self.inventer(6))
        code, sortie = self.lancer("collect", export, "--team", "equipe test")     # casse sans importance
        self.assertEqual(code, 0, sortie)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-3", "ABC-5"})
        self.assertIn("hors équipe demandée : 3", sortie)
        self.assertNotIn("quipe test", sortie.lower().replace("équipe demandée", ""))

    def test_equipe_retient_un_ticket_des_qu_une_de_ses_equipes_correspond(self):
        for i in range(1, 6):
            self.faux.ajouter(f"ABC-{i}")
        chemin = self.ws / "multi.csv"
        chemin.write_text(
            "Issue key,Issue Type,Status,Resolved,Team,Team\n"
            "ABC-1,Story,Open,,Equipe Test,\n"                  # première colonne
            "ABC-2,Story,Open,,Autre Equipe,Equipe Test\n"      # seconde colonne
            "ABC-3,Story,Open,,Autre Equipe;Equipe Test,\n"     # plusieurs valeurs dans la cellule
            "ABC-4,Story,Open,,Autre Equipe,\n"
            "ABC-5,Story,Open,,,\n", encoding="utf-8")
        code, sortie = self.lancer("collect", str(chemin), "--team", "equipe test")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sorted(self.cache()), ["ABC-1", "ABC-2", "ABC-3"])
        self.assertIn("hors équipe demandée : 2", sortie)

    def test_equipe_inconnue(self):
        export = self.ecrire_export(self.inventer(3))
        code, sortie = self.lancer("collect", export, "--team", "Inconnue")
        self.assertEqual(code, 1)
        self.assertIn("aucun ticket", sortie)
        self.assertNotIn("Inconnue", sortie)
        self.assertEqual(self.faux.appels, [])

    def test_portefeuille_et_projets_exclus_ne_sont_pas_interroges(self):
        self.ecrire_reglages("classique", "portfolio_types: [Epic]\nexcluded_projects: [BUG]\n")
        lignes = self.inventer(3)
        for cle in ("EPI-1", "BUG-1"):
            self.faux.ajouter(cle)
        lignes += [("EPI-1", "Epic", "Equipe Test", False), ("BUG-1", "Bug", "Equipe Test", False)]
        code, sortie = self.lancer("collect", self.ecrire_export(lignes))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-2", "ABC-3"})
        self.assertIn("écartés (types de portefeuille, projets exclus) : 2", sortie)

    def test_lots_multiples_fusionnes_par_cle(self):
        lignes = self.inventer(4)
        e1 = self.ecrire_export(lignes[:3], "a.csv")
        e2 = self.ecrire_export(lignes[2:], "b.csv")
        code, sortie = self.lancer("collect", e1, e2)
        self.assertEqual(code, 0, sortie)
        self.assertIn("Tickets lus : 4", sortie)

    def test_429_respecte_retry_after_puis_reussit(self):
        self.faux.limite_429 = 2
        code, sortie = self.lancer("collect", self.ecrire_export(self.inventer(2)))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.attentes[:2], [1.0, 1.0])                   # Retry-After: 1 respecté
        self.assertEqual(len(self.cache()), 2)

    def test_429_persistant_arrete_proprement_sans_cacher(self):
        self.faux.toujours_429 = True
        code, sortie = self.lancer("collect", self.ecrire_export(self.inventer(2)))
        self.assertEqual(code, 0)                                         # erreurs comptées, rien de fatal
        self.assertIn("erreurs : 2 (HTTP 429 : 2)", sortie)
        self.assertFalse((self.ws / "Flux-Lab" / "historique" / "transitions.json").exists())
        self.assertTrue(self.attentes)

    def test_strict_429_persistant_sort_avec_3_sans_cache(self):
        self.faux.toujours_429 = True
        code, sortie = self.lancer("collect", self.ecrire_export(self.inventer(2)), "--strict")
        self.assertEqual(code, 3, sortie)
        self.assertIn("erreurs : 2 (HTTP 429 : 2)", sortie)
        self.assertFalse((self.ws / "Flux-Lab" / "historique" / "transitions.json").exists())
        self.assertTrue(sortie.rstrip().endswith("erreurs de collecte : historique incomplet"), sortie)

    def test_strict_429_persistant_en_anglais(self):
        self.faux.toujours_429 = True
        code, sortie = self.lancer("collect", self.ecrire_export(self.inventer(2)), "--strict", "--language", "en")
        self.assertEqual(code, 3, sortie)
        self.assertTrue(sortie.rstrip().endswith("collection errors: history incomplete"), sortie)

    def test_strict_sans_erreur_sort_avec_0(self):
        code, sortie = self.lancer("collect", self.ecrire_export(self.inventer(2)), "--strict")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("historique incomplet", sortie)

    def test_sans_strict_429_persistant_reste_0(self):
        self.faux.toujours_429 = True
        code, sortie = self.lancer("collect", self.ecrire_export(self.inventer(2)))
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("historique incomplet", sortie)

    def test_strict_garde_le_code_1_d_une_erreur_d_acces(self):
        self.faux.attendu = "Basic autre"
        code, sortie = self.lancer("collect", self.ecrire_export(self.inventer(3)), "--strict")
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

    def test_erreur_d_acces_arrete_et_garde_le_cache(self):
        self.faux.attendu = "Basic autre"
        code, sortie = self.lancer("collect", self.ecrire_export(self.inventer(3)))
        self.assertEqual(code, 1)
        self.assertIn("Arrêt : HTTP 401", sortie)

    def test_ticket_introuvable_compte_une_erreur(self):
        self.faux.groupe = False
        self.faux.introuvables = {"ABC-2"}
        code, sortie = self.lancer("collect", self.ecrire_export(self.inventer(3)))
        self.assertEqual(code, 0, sortie)
        self.assertIn("erreurs : 1 (HTTP 404 : 1)", sortie)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-3"})           # le ticket en erreur sera retenté

    def test_cache_hors_git_permissions_restreintes(self):
        self.lancer("collect", self.ecrire_export(self.inventer(2)))
        dossier = self.ws / "Flux-Lab" / "historique"
        self.assertEqual(stat.S_IMODE(dossier.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((dossier / "transitions.json").stat().st_mode), 0o600)

    def test_export_sans_colonne_de_cle(self):
        chemin = self.ws / "sans_cle.csv"
        chemin.write_text("Summary,Status\nx,Open\n", encoding="utf-8")
        code, sortie = self.lancer("collect", str(chemin))
        self.assertEqual(code, 1)
        self.assertIn("colonne de clé", sortie)


PARCOURS_REEL = [          # (de, vers, jour d'août ou septembre) : un ticket qui passe par tous les segments
    ("Open", "Definition", "2026-08-03"), ("Definition", "Ready for Implementation", "2026-08-10"),
    ("Ready for Implementation", "Implementation - Ongoing", "2026-08-17"),
    ("Implementation - Ongoing", "Ready for Review (Implementation)", "2026-08-31"),
    ("Ready for Review (Implementation)", "Ready for Acceptance", "2026-09-07"),
    ("Ready for Acceptance", "Closed", "2026-09-14")]


class FluxSurCacheReel(Base):
    """Non-régression : le cache produit par history_jira.py, lu par flux_jira.py compute --history, doit
    donner les sorties de segment et le point d'engagement. Données inventées."""

    def inventer_reels(self, n: int = 3):
        for i in range(1, n + 1):
            cle = f"ABC-{i}"
            self.faux.tickets[cle] = (str(20000 + i), [
                {"id": f"{i}{k}", "created": f"{jour}T09:00:00.000+0200", "author": {"displayName": AUTEUR},
                 "items": [{"field": "status", "fieldId": "status", "fromString": de, "toString": vers}]}
                for k, (de, vers, jour) in enumerate(PARCOURS_REEL)])
        return [(f"ABC-{i}", "Story", "Equipe Test", True) for i in range(1, n + 1)]

    def exporter_flux(self, n: int) -> str:
        chemin = self.ws / "export-flux.csv"
        chemin.write_text("Issue key,Issue Type,Status,Status Category,Created,Resolved,Resolution,"
                          "Status Category Changed,Team\n" + "".join(
            f"ABC-{i},Story,Closed,Done,01/Aug/2026 08:00,14/Sep/2026 10:00,Done,14/Sep/2026 10:00,Equipe Test\n"
            for i in range(1, n + 1)) + "ABC-9,Story,Closed,Done,01/May/2026 08:00,01/Jun/2026 10:00,Done,"
                          "01/Jun/2026 10:00,Equipe Test\n", encoding="utf-8")       # sans historique : ouvre la période
        return str(chemin)

    def calcul_flux(self, cache_chemin=None):
        import subprocess
        env = {**os.environ, "PMZILLA_LAB_WORKSPACE": str(self.ws)}
        r = subprocess.run(["uv", "run", str(SCRIPT.parent / "flux_jira.py"), "compute", self.exporter_flux(3),
                            "--name", "reel", "--today", "2026-10-04", "--no-comparison", "--history",
                            *([str(cache_chemin)] if cache_chemin else [])], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rap = self.ws / "Flux-Lab" / "rapports" / "flux-reel-2026-10-04.json"
        return json.loads(rap.read_text(encoding="utf-8"))["temps_par_segment"], r.stdout

    def verifier(self, ts):
        lt = ts["global"]["lead_time_livraison"]
        self.assertEqual((lt["n"], lt["sans_engagement"]), (3, 0))
        for segment in ("pret", "implementation", "revue_verification", "acceptation"):
            self.assertEqual(ts["global"]["sortis"][segment]["n"], 3, segment)
        self.assertEqual(ts["global"]["sortis"]["pret"]["p50"], 7)             # 10 au 17 août
        self.assertEqual(ts["etats_hors_segment"], {})
        self.assertNotIn("dates_illisibles", ts)

    def test_cache_collecte_en_mode_groupe_avec_dates_iso(self):
        export = self.ecrire_export(self.inventer_reels())
        self.assertEqual(self.lancer("collect", export)[0], 0)
        ts, _ = self.calcul_flux()
        self.verifier(ts)

    def test_cache_collecte_en_mode_groupe_avec_dates_en_millisecondes(self):
        self.faux.dates_epoch = True
        export = self.ecrire_export(self.inventer_reels())
        self.assertEqual(self.lancer("collect", export)[0], 0)
        cache = self.cache()
        self.assertTrue(all(isinstance(t[0], str) and t[0].endswith("+0000")
                            for v in cache.values() for t in v["transitions"]))
        ts, _ = self.calcul_flux()
        self.assertEqual(ts["global"]["lead_time_livraison"]["n"], 3)
        self.assertEqual(ts["global"]["sortis"]["pret"]["n"], 3)

    def test_ancien_cache_avec_dates_en_nombres_est_lu_correctement(self):
        """Un cache écrit avant la correction (dates en millisecondes, nombres) donne les mêmes chiffres."""
        import datetime as _dt
        export = self.ecrire_export(self.inventer_reels())
        self.assertEqual(self.lancer("collect", export)[0], 0)
        cache = self.cache()
        for fiche in cache.values():
            for t in fiche["transitions"]:
                t[0] = int(_dt.datetime.strptime(t[0], "%Y-%m-%dT%H:%M:%S.%f%z").timestamp() * 1000)
        ancien = self.ws / "ancien.json"
        ancien.write_text(json.dumps(cache), encoding="utf-8")
        ts, _ = self.calcul_flux(ancien)
        self.assertEqual(ts["global"]["lead_time_livraison"]["n"], 3)
        self.assertEqual(ts["global"]["sortis"]["implementation"]["n"], 3)
        (self.ws / "Flux-Lab" / "historique" / "transitions.json").write_text(json.dumps(cache), encoding="utf-8")
        code, sortie = self.lancer("check", "--key", "ABC-1")
        self.assertEqual(code, 0, sortie)                                        # plus d'AttributeError
        self.assertIn("2026-08-03 07:00:00+0000", sortie)
        self.assertIn("Ready for Implementation  ->  Implementation - Ongoing", sortie)
        code, sortie = self.lancer("check", self.ecrire_export_etat_reel())
        self.assertIn("Dates de transition illisibles : 0.", sortie)

    def ecrire_export_etat_reel(self) -> str:
        chemin = self.ws / "etat.csv"
        chemin.write_text("Issue key,Issue Type,Status,Resolved,Team\n" + "".join(
            f"ABC-{i},Story,Closed,14/Sep/2026 10:00,Equipe Test\n" for i in range(1, 4)), encoding="utf-8")
        return str(chemin)

    def test_date_illisible_signalee_au_lieu_d_un_zero_silencieux(self):
        export = self.ecrire_export(self.inventer_reels())
        self.lancer("collect", export)
        cache = self.cache()
        for fiche in cache.values():
            for t in fiche["transitions"]:
                t[0] = "pas une date"
        (self.ws / "Flux-Lab" / "historique" / "transitions.json").write_text(json.dumps(cache), encoding="utf-8")
        code, sortie = self.lancer("check", self.ecrire_export_etat_reel())
        self.assertIn("Dates de transition illisibles : 18 (", sortie)
        ts, stdout = self.calcul_flux()
        self.assertEqual(ts["dates_illisibles"], 3)
        self.assertIn("date de transition illisible", stdout)


class NormaliserDate(unittest.TestCase):
    def test_formats(self):
        n = hj.commun.normaliser_date
        self.assertEqual(n("2026-03-01T09:00:00.000+0200"), "2026-03-01T09:00:00.000+0200")
        self.assertEqual(n(1772352000123), "2026-03-01T08:00:00.123+0000")
        self.assertEqual(n("1772352000123"), "2026-03-01T08:00:00.123+0000")
        self.assertEqual(n(1772352000), "2026-03-01T08:00:00.000+0000")        # secondes
        self.assertIsNone(n(None))
        self.assertEqual(n("pas une date"), "pas une date")


class FormatsDeDateReduits(unittest.TestCase):
    """Seul le format de l'export de l'API (09/Nov/2017 08:49) lit un CSV ; la lecture du cache d'historique (dates ISO
    8601 avec décalage, millisecondes depuis 1970) et le calcul des dormants n'en dépendent pas."""

    def test_un_seul_format_de_csv(self):
        commun = hj.commun
        self.assertFalse(hasattr(commun, "FORMATS_DATE"))
        self.assertEqual(commun.FORMAT_DATE, "%d/%b/%Y %H:%M")
        self.assertEqual(commun.parse_jour("09/Nov/2017 08:49").isoformat(), "2017-11-09")
        for refuse in ("2017-11-09", "2017-11-09 08:49", "09/11/2017", "09/Nov/17 08:49 AM", "09/Nov/2017 08:49 AM", "", None):
            self.assertIsNone(commun.parse_jour(refuse), refuse)

    def test_lecture_du_cache_avec_des_dates_iso_de_l_api(self):
        commun = hj.commun
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "transitions.json"
            chemin.write_text(json.dumps({"ABC-1": {"termine": False, "transitions": [
                ["2017-11-09T08:49:00.000+0100", "Open", "Doing"],
                ["2017-11-08T10:00:00.000+0100", None, "Open"],
                [1510212540000, "Doing", "Done"]]}}), encoding="utf-8")
            cache = commun.lire_cache(chemin)
        dates = [t[0] for t in cache["ABC-1"]["transitions"]]
        self.assertEqual(dates, ["2017-11-08T10:00:00.000+0100", "2017-11-09T07:29:00.000+0000",
                                 "2017-11-09T08:49:00.000+0100"])         # triées par instant, pas par texte
        self.assertEqual(commun.date_calendaire("2017-11-09T08:49:00.000+0100").isoformat(), "2017-11-09")
        self.assertEqual(len(dates), 3)

    def test_dormants_selon_l_historique_sans_format_de_csv(self):
        commun = hj.commun
        import datetime as dt
        cache = {"ABC-1": [["2024-03-01T10:00:00.000+0200", "Open", "Doing"]], "ABC-2": []}
        dormants, sans = commun.dormants_selon_historique(
            [("ABC-1", dt.date(2024, 1, 1), False), ("ABC-2", dt.date(2026, 9, 1), False), ("ABC-3", dt.date(2024, 1, 1), False)],
            cache, dt.date(2026, 10, 4))
        self.assertEqual((dormants, sans), ({"ABC-1"}, 1))


class Tri(unittest.TestCase):
    def test_tri_chronologique_malgre_des_decalages_differents(self):
        # 09:00 à +0200 = 07:00 UTC, avant 08:00 à +0000, alors que le texte les range dans l'autre ordre
        histo = [{"created": "2026-03-01T08:00:00.000+0000", "items": [{"fieldId": "status", "fromString": "B", "toString": "C"}]},
                 {"created": "2026-03-01T09:00:00.000+0200", "items": [{"fieldId": "status", "fromString": "A", "toString": "B"}]}]
        self.assertEqual([t[1:] for t in hj.transitions_de(histo)], [["A", "B"], ["B", "C"]])

    def test_ordre_de_l_api_inverse_ou_non_donne_le_meme_resultat(self):
        histo = transitions_inventees(1)
        self.assertEqual(hj.transitions_de(histo), hj.transitions_de(list(reversed(histo))))

    def test_date_illisible_ne_fait_pas_planter(self):
        histo = [{"created": None, "items": [{"fieldId": "status", "fromString": "A", "toString": "B"}]},
                 {"created": "2026-03-01T09:00:00.000+0200", "items": [{"fieldId": "status", "fromString": "B", "toString": "C"}]}]
        self.assertEqual(len(hj.transitions_de(histo)), 2)


class Controle(Base):
    def ecrire_export_etat(self, lignes, nom="export.csv") -> str:
        """lignes : (clé, état, terminé)."""
        chemin = self.ws / nom
        chemin.write_text("Issue key,Issue Type,Status,Resolved,Team\n" + "".join(
            f"{c},Story,{e},{'10/Sep/2026 10:00' if f else ''},Equipe Test\n" for c, e, f in lignes), encoding="utf-8")
        return str(chemin)

    def test_effectifs_sans_identifiant_et_sans_appel_reseau(self):
        for i in range(1, 6):
            self.faux.ajouter(f"ABC-{i}")
        collecte = self.ecrire_export_etat([(f"ABC-{i}", "Done", True) for i in range(1, 6)])
        self.lancer("collect", collecte)
        cache = self.cache()
        cache["ABC-5"]["transitions"] = []                                # livré sans transition
        cache["ABC-4"]["transitions"] = cache["ABC-4"]["transitions"][:1]  # dernier état : In Progress, pas Done
        (self.ws / "Flux-Lab" / "historique" / "transitions.json").write_text(json.dumps(cache), encoding="utf-8")
        self.faux.appels.clear()
        export = self.ecrire_export_etat([(f"ABC-{i}", "Done", True) for i in range(1, 6)] + [("ABC-9", "Open", False)])
        code, sortie = self.lancer("check", export)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.faux.appels, [])
        self.assertIn("absents du cache : 1", sortie)
        self.assertIn("cohérents 3 ; incohérents 1 ; non comparables (aucune transition) 1", sortie)
        self.assertIn("0 : 1 ; 1 : 1 ; 2-4 : 3 ; 5-9 : 0 ; 10 et plus : 0", sortie)
        self.assertIn("(date de résolution) : 5 ; livrés sans aucune transition : 1", sortie)
        self.assertNotIn("ABC-", sortie)
        self.assertNotIn("Equipe Test", sortie)

    def test_livres_etat_de_depart_transitions_et_segments(self):
        for i in range(1, 5):
            self.faux.ajouter(f"ABC-{i}")
        export = self.ecrire_export_etat([(f"ABC-{i}", "Done", True) for i in range(1, 5)])
        self.lancer("collect", export)
        def t(*etats):
            return [[f"2026-03-0{n + 1}T10:00:00.000+0200", a, b] for n, (a, b) in enumerate(zip(etats, etats[1:]))]
        cache = self.cache()
        cache["ABC-1"]["transitions"] = t("Open", "Definition", "Ready for Implementation", "Implementation", "Done")
        cache["ABC-2"]["transitions"] = t("Open", "Implementation", "Done")
        cache["ABC-3"]["transitions"] = t("Implementation", "Verification", "Done")     # début tronqué
        cache["ABC-4"]["transitions"] = t("Open", "Closed")
        (self.ws / "Flux-Lab" / "historique" / "transitions.json").write_text(json.dumps(cache), encoding="utf-8")
        code, sortie = self.lancer("check", export)
        self.assertEqual(code, 0, sortie)
        self.assertIn("Tickets livrés (4) : lecture de l'historique.", sortie)
        self.assertIn("État de départ de la première transition connue : Open 3 ; Implementation 1.", sortie)
        self.assertIn("Transitions par ticket livré : 0 : 0 ; 1 : 1 ; 2-4 : 3 ; 5-9 : 0 ; 10 et plus : 0.", sortie)
        self.assertIn("definition 1 ; pret 1 ; implementation 3 ; revue_verification 1 ; (aucun segment) 1", sortie)
        self.assertNotIn("ABC-", sortie)

    def test_segments_reglables_dans_flux_yaml(self):
        self.faux.ajouter("ABC-1")
        export = self.ecrire_export_etat([("ABC-1", "Done", True)])
        self.lancer("collect", export)
        self.ecrire_reglages("classique", "segments:\n  fin: [In Progress]\n")
        code, sortie = self.lancer("check", export)
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
        export = self.ecrire_export_etat([("ABC-1", "Done", True)])
        self.lancer("collect", export)
        code, sortie = self.lancer("check", "--key", "abc-1", export)
        self.assertEqual(code, 0, sortie)
        self.assertIn("ABC-1 : 2 transition(s)", sortie.replace("abc-1", "ABC-1"))
        self.assertIn("Open  ->  In Progress", sortie)
        self.assertIn("In Progress  ->  Done", sortie)
        self.assertIn("état de l'export : Done", sortie)
        self.assertNotIn(AUTEUR, sortie)
        self.assertNotIn("2026-01-10T", sortie)                     # date lisible, sans « T » ni millisecondes
        code, sortie = self.lancer("check", "--key", "ZZZ-9")
        self.assertEqual(code, 1)
        self.assertIn("absent du cache", sortie)

    def test_controle_sans_export_ni_cle(self):
        code, sortie = self.lancer("check")
        self.assertEqual(code, 1)

    def test_option_dormants_refusee_avec_la_voie_de_remplacement(self):
        export = self.ecrire_export_etat([("ABC-1", "Done", True)])
        (self.ws / "dormants.csv").write_text("Issue key\nABC-1\n", encoding="utf-8")
        for langue, extrait in (("fr", "n'existe plus"), ("en", "no longer exists")):
            code, sortie = self.lancer("check", export, "--dormants", str(self.ws / "dormants.csv"), "--language", langue)
            self.assertEqual(code, 1, sortie)
            self.assertIn("--dormant-from-history", sortie)
            self.assertIn(extrait, sortie)
            self.assertNotIn("Traceback", sortie)

    def test_controle_sans_dormants_inchange(self):
        for i in range(1, 3):
            self.faux.ajouter(f"ABC-{i}")
        export = self.ecrire_export_etat([("ABC-1", "Done", True), ("ABC-2", "Done", True)])
        self.lancer("collect", export)
        code, sortie = self.lancer("check", export)
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("Dormants", sortie)

    def test_export_a_en_tetes_francais_refuse_avec_la_voie_api(self):
        chemin = self.ws / "manuel.csv"
        chemin.write_text("Clé de ticket,Type de ticket,Statut,Créé,Résolu,Équipe\n"
                          "ABC-1,Story,Fait,01/Jan/2024 09:00,02/Jan/2024 09:00,Equipe Test\n", encoding="utf-8")
        for langue in ("fr", "en"):
            code, sortie = self.lancer("check", str(chemin), "--language", langue)
            self.assertEqual(code, 1, sortie)
            self.assertIn("export_jira_api.py export", sortie)
            self.assertNotIn("Traceback", sortie)

    def test_tranches(self):
        self.assertEqual([hj.tranche(n) for n in (0, 1, 2, 4, 5, 9, 10, 40)],
                         ["0", "1", "2-4", "2-4", "5-9", "5-9", "10 et plus", "10 et plus"])

    def test_export_sans_colonne_d_etat(self):
        chemin = self.ws / "sans.csv"
        chemin.write_text("Issue key,Issue Type\nABC-1,Story\n", encoding="utf-8")
        code, sortie = self.lancer("check", str(chemin))
        self.assertEqual(code, 1)
        self.assertIn("colonne d'état", sortie)


if __name__ == "__main__":
    unittest.main()
