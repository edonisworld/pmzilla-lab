"""Aide des tests de history_jira.py (change database-only, D5 et D6) : un faux serveur Jira local, un faux jeton, un faux magasin de la
collecte (la base en mémoire) et un faux flow_store pour `check`. Aucune base, aucun appel réseau, aucune donnée réelle.

Le faux magasin suit le protocole de history_store.MagasinHistorique (`tickets`, `derniere_collecte`, `enregistrer`, `fermer`) et la
même règle d'écriture : transitions sans doublon, indicateur « avec historique », périodes remplacées pour un ticket dont les valeurs
courantes sont connues, passage « history » seulement pour une collecte réussie ; une erreur injectée (`echec`) ne laisse rien.
`ecrire_export(lignes)` charge ces lignes (clé, type, équipe, terminé[, mise à jour]) comme tickets de la base fictive et rend
SENTINELLE, que `Base.lancer` retire de la ligne de commande : les appels des tests gardent leur forme d'avant, sans fichier.
"""
import base64
import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
import threading
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "flow_delivery"))          # table FACTICE des champs de livraison (R-20261114-108)
import table_factice          # noqa: E402
import flow_delivery          # noqa: E402
import history_jira as hj          # noqa: E402
import history_common as commun    # noqa: E402

SCRIPT = TOOLS / "history_jira.py"
JETON = "test-token-000"
EMAIL = "utilisateur@example.org"
CLOUD_ID = "cloud-123"
AUTEUR = "Personne Fictive"
PARIS = ZoneInfo("Europe/Paris")
GARDE_DE_TEST = ["scope_projects: [PROJ, ABC, EPI, INI, BUG, ZZZ, ZZKEYSEPT]", "forbidden_projects: [SUPX]"]   # R-20261028-96 : clés fictives
SENTINELLE = "<<tickets de la base fictive>>"         # remplace le chemin d'un export dans les appels des tests : retiré par lancer


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
        self.courantes = {}          # clé -> {"fixVersions": [noms], "labels": [étiquettes]} : valeurs courantes rendues par la recherche
        self.groupe = True           # False : l'API groupée répond 404
        self.pages_groupees = 1      # 2 : la réponse groupée est paginée
        self.entrees_par_page = 0    # > 0 : la réponse groupée est coupée toutes les n entrées d'historique
        self.taille_recherche = 0    # > 0 : la recherche des clés rend n tickets par page, avec nextPageToken
        self.dates_epoch = False     # l'API groupée donne « created » en millisecondes depuis 1970 (format supposé réel)
        self.sans_islast = False     # l'historique ticket par ticket ne renvoie ni isLast ni total
        self.taille_page = 100       # taille des pages de l'historique ticket par ticket
        self.limite_429 = 0          # nombre d'appels API qui répondent 429 (Retry-After: 1) avant de répondre
        self.toujours_429 = False
        self.introuvables = set()    # clés dont l'historique ticket par ticket répond 404
        self.absents_groupe = set()  # clés rendues par la recherche mais absentes de la réponse groupée (réponse tronquée)
        self.erreurs_ticket = {}     # clé -> code HTTP (5xx) de l'historique ticket par ticket
        self.jeton_repete = False    # la réponse groupée renvoie toujours le même jeton de page
        self.jeton_repete_recherche = False   # la recherche des clés (avant la lecture groupée) renvoie toujours le même jeton de page
        self.appels = []
        self.recherche_imposee = None   # corps JSON rendu à toute recherche de tickets (tests de la garde du périmètre)
        self.brut = []               # (méthode, chemin complet, en-tête d'authentification présent) de chaque requête reçue, avant tout contrôle
        self.corps = []              # (chemin, corps JSON) des appels POST
        self.prefixe = f"/ex/jira/{CLOUD_ID}"     # la passerelle : le seul chemin des appels authentifiés
        self.cloud_site = CLOUD_ID   # le cloudId que le site donne sans authentification
        self.refus = {}              # famille de ressource (search, history, fields) -> code HTTP à répondre
        self.params = []             # (famille, paramètres de la requête) des appels de sonde
        self.hors_passerelle = []    # chemins appelés avec authentification en dehors de la passerelle
        self.auth_sur_tenant = False # la lecture du cloudId a reçu un en-tête d'authentification
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

        def noter_brut(self, methode):
            """Journal brut (design D6) : première ligne de chaque gestionnaire, avant tout contrôle."""
            faux.brut.append((methode, self.path, "Authorization" in self.headers))

        def traiter(self, methode):
            self.noter_brut(methode)
            chemin = urlparse(self.path)
            corps = {}
            if methode == "POST":
                taille = int(self.headers.get("Content-Length") or 0)
                corps = json.loads(self.rfile.read(taille) or b"{}")
            if chemin.path == "/_edge/tenant_info":
                faux.appels.append((methode, chemin.path))
                faux.auth_sur_tenant = faux.auth_sur_tenant or "Authorization" in self.headers
                return self.repondre(200, {"cloudId": faux.cloud_site, "site": "Nom Fictif"})
            if "Authorization" in self.headers and not chemin.path.startswith(faux.prefixe + "/"):
                faux.hors_passerelle.append(chemin.path)
                return self.repondre(404)
            if self.headers.get("Authorization") != faux.attendu:
                return self.repondre(401, {"message": "Nom Fictif"})
            api = chemin.path[len(faux.prefixe):] if chemin.path.startswith(faux.prefixe) else chemin.path
            faux.appels.append((methode, api))
            if methode == "POST":
                faux.corps.append((api, corps))
            famille = ("search" if api == "/rest/api/3/search/jql" and methode == "GET" else
                       "history" if api.endswith("/changelog") or api.endswith("/changelog/bulkfetch") else
                       "fields" if api == "/rest/api/3/field/search" else None)
            if famille:
                faux.params.append((famille, {k: v[0] for k, v in parse_qs(chemin.query).items()}))
            if famille in faux.refus:
                return self.repondre(faux.refus[famille], {"message": "Nom Fictif"})
            if api == "/rest/api/3/field/search":
                return self.repondre(200, {"values": [{"id": "customfield_99999", "name": "Champ Secret"}], "total": 1})
            if faux.toujours_429 or faux.limite_429 > 0:
                faux.limite_429 -= 1
                return self.repondre(429, {}, {"Retry-After": "1"})
            if api == "/rest/api/3/search/jql" and faux.recherche_imposee is not None:
                # réponse plantée par un test (garde du périmètre) : un corps, ou une fonction du corps de la requête (None : réponse usuelle)
                imposee = faux.recherche_imposee(corps) if callable(faux.recherche_imposee) else faux.recherche_imposee
                if imposee is not None:
                    return self.repondre(200, imposee)
            if api == "/rest/api/3/search/jql" and methode == "GET":
                premiers = [{"id": ident, "key": cle} for cle, (ident, _) in list(faux.tickets.items())[:1]]
                return self.repondre(200, {"issues": premiers, "owner": "Nom Fictif"})
            if api == "/rest/api/3/search/jql" and methode == "POST":
                cles = corps["jql"][len("key in ("):-1].split(",")
                demandes = corps.get("fields") or []

                def champs_de(cle):
                    valeurs = faux.courantes.get(cle, {})
                    sortie = {"summary": "Titre secret"}
                    for identifiant, valeur in valeurs.get("champs", {}).items():       # champs de livraison (jira-delivery-fields) : rendus s'ils sont demandés
                        if identifiant in demandes:
                            sortie[identifiant] = valeur
                    if "fixVersions" in demandes:
                        sortie["fixVersions"] = [{"name": n} for n in valeurs.get("fixVersions", [])]
                    if "labels" in demandes:
                        sortie["labels"] = list(valeurs.get("labels", []))
                    return sortie

                trouves = [{"id": faux.tickets[c][0], "key": c, "fields": champs_de(c)} for c in cles if c in faux.tickets]
                if faux.jeton_repete_recherche and demandes == ["key"]:       # la recherche des clés boucle sur le même jeton
                    return self.repondre(200, {"issues": trouves, "nextPageToken": "toujours-le-meme"})
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
                    return [{**h, "created": int(dt.datetime.strptime(h["created"], "%Y-%m-%dT%H:%M:%S.%f%z")
                                                 .timestamp() * 1000)} for h in histo]
                # R-20261028-105 : le corps porte des clés (ou, comme avant, des identifiants numériques)
                fiches = [{"issueId": ident, "changeHistories": format_groupe(histo)}
                          for cle, (ident, histo) in faux.tickets.items()
                          if (ident in ids or cle in ids) and cle not in faux.absents_groupe]
                if faux.jeton_repete:
                    return self.repondre(200, {"issueChangeLogs": fiches, "nextPageToken": "toujours-le-meme"})
                if faux.entrees_par_page:
                    plat = [(ident, h) for cle, (ident, histo) in faux.tickets.items() if ident in ids or cle in ids for h in histo]
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
                if cle in faux.erreurs_ticket:
                    return self.repondre(faux.erreurs_ticket[cle], {"message": "Nom Fictif"})
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

        def ecriture(self):
            """PUT, PATCH, DELETE, HEAD, OPTIONS : journal brut, puis 405 (le client ne doit jamais en émettre)."""
            self.noter_brut(self.command)
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            return self.repondre(405)

        do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = ecriture

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


class MagasinMemoire:
    """La base fictive de la collecte : tickets, transitions, périodes et passages « history » (protocole de history_store)."""

    def __init__(self):
        self.stock: dict[str, dict] = {}                       # clé -> ticket (cle, projet, type, cree, resolu, maj, a_historique, equipes, etat)
        self.transitions: dict[str, list] = {}                 # clé -> [(instant, départ, arrivée)] sans doublon
        self.periodes = {"etiquettes": {}, "versions": {}}     # nature -> clé -> {(valeur, début): fin} ; « sprints » et « actifs » s'ajoutent à la première écriture
        self.passages: list[dt.datetime] = []                  # instants des passages « history » SANS erreur (collectes réussies)
        self.passages_en_erreur: list[tuple[dt.datetime, int]] = []   # (instant, nombre d'erreurs) des passages enregistrés avec erreurs
        self.nombres_introuvables: list[int] = []              # nombre de 404 de chaque passage « history » enregistré
        self.compteurs: dict[str, int] = {}                  # clé -> passages consécutifs en 404
        self.disparus: set[str] = set()                        # clés marquées disparues : plus réinterrogées
        self.echec: Exception | None = None                    # levée à l'écriture : rien n'est écrit
        self.ferme = False
        self.horloge = lambda: dt.datetime.now(dt.timezone.utc)
        self.ecritures = 0                                     # nombre d'appels à enregistrer qui ont abouti

    def tickets(self) -> list[dict]:
        return [{k: v for k, v in t.items() if k != "etat"} | {"equipes": list(t["equipes"])} for t in self.stock.values()]

    def derniere_collecte(self):
        """Instant du dernier passage sans erreur : un passage avec erreurs est enregistré mais n'avance pas la collecte réussie."""
        return self.passages[-1] if self.passages else None

    def introuvables(self):
        """(compteurs de 404 consécutifs non nuls, clés disparues) — protocole de history_store.MagasinHistorique.introuvables."""
        return {c: n for c, n in self.compteurs.items() if n}, set(self.disparus)

    def enregistrer(self, resultats: dict, erreurs: int = 0, suivi: dict | None = None, introuvables: int = 0):
        if self.echec is not None:
            raise self.echec
        for cle, (compteur, disparu) in (suivi or {}).items():
            self.compteurs[cle] = compteur
            (self.disparus.add if disparu else self.disparus.discard)(cle)
        majuscules = {cle.upper(): cle for cle in self.stock}
        ajoutees = periodes = 0
        for cle, resultat in resultats.items():
            vrai = majuscules.get(cle.upper())
            if vrai is None:
                continue
            existantes = self.transitions.setdefault(vrai, [])
            for transition in resultat["transitions"]:
                if transition not in existantes and transition[2]:
                    existantes.append(transition)
                    ajoutees += 1
            self.stock[vrai]["a_historique"] = True
            for nature in ("etiquettes", "versions", "sprints", "actifs"):
                voulu = resultat.get(nature)
                if voulu is None:
                    continue
                avant = self.periodes.setdefault(nature, {}).get(vrai, {})
                apres = {(valeur, debut): fin for valeur, debut, fin in voulu}
                periodes += sum(1 for k, fin in apres.items() if k not in avant or avant[k] != fin)
                self.periodes[nature][vrai] = apres
        self.nombres_introuvables.append(introuvables)       # un nombre de 404 par passage enregistré, dans l'ordre
        if erreurs:                       # l'horloge réglée par les tests ne cadence que les collectes réussies
            self.passages_en_erreur.append((dt.datetime.now(dt.timezone.utc), erreurs))
        else:
            self.passages.append(self.horloge())
        self.ecritures += 1
        return ajoutees, periodes

    def fermer(self):
        self.ferme = True

    # --- lecture des tests

    def cache(self) -> dict:
        """Vue de l'historique stocké, de la forme de l'ancien cache : clé -> {"transitions": [[ISO, départ, arrivée], ...]}."""
        return {cle: {"transitions": [[instant.isoformat(), de, vers] for instant, de, vers in sorted(self.transitions.get(cle, []), key=lambda t: t[0])]}
                for cle, t in self.stock.items() if t["a_historique"]}


def faux_flow_store(magasin: MagasinMemoire) -> types.SimpleNamespace:
    """Faux flow_store (lecteurs de la base en lecture seule) bâti sur le faux magasin, pour `check`."""
    def lire_tickets_flux(settings):
        tickets = []
        for t in magasin.stock.values():
            tickets.append({"cle": t["cle"], "projet": t["projet"], "type": t["type"] or "?", "etat": t["etat"],
                            "cree": t["cree"].date(), "resolu": t["resolu"].date() if t["resolu"] else None,
                            "equipe": t["equipes"][0] if t["equipes"] else "(sans équipe)", "equipes": list(t["equipes"]),
                            "categorie": "", "debut": None, "motif": ""})
        return tickets, {}, 0, 0

    def lire_historique(settings):
        fuseau = commun.fuseau_export(settings)
        return {cle.upper(): [[commun.en_fuseau(instant.isoformat(), fuseau), de, vers]
                               for instant, de, vers in sorted(magasin.transitions.get(cle, []), key=lambda t: t[0])]
                for cle, t in magasin.stock.items() if t["a_historique"]}

    def lire_maj_tickets(settings):
        """Comme flow_store.lire_maj_tickets : {CLÉ_MAJUSCULES: date de dernière mise à jour du ticket (avec décalage) ou None}."""
        return {cle.upper(): t["maj"] for cle, t in magasin.stock.items()}

    return types.SimpleNamespace(lire_tickets_flux=lire_tickets_flux, lire_historique=lire_historique,
                                 lire_maj_tickets=lire_maj_tickets)


class Base(unittest.TestCase):
    def setUp(self):
        self.addCleanup(flow_delivery.configurer, None)          # l'état des champs de livraison est global : jamais d'un test à l'autre
        self.faux = FauxJira()
        self.serveur = fabriquer_serveur(self.faux)
        threading.Thread(target=self.serveur.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        self.addCleanup(self.serveur.server_close)
        self.addCleanup(self.serveur.shutdown)
        self.url = f"http://127.0.0.1:{self.serveur.server_address[1]}"
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name)
        flux = self.ws / "Flux-Lab"
        flux.mkdir()
        self.magasin = MagasinMemoire()
        patches = [mock.patch.object(hj, "WORKSPACE", self.ws), mock.patch.object(hj, "FLUX_DIR", flux),
                   mock.patch.object(hj, "CONFIG_FILE", flux / "flux.yaml"),
                   mock.patch.object(hj, "lire_jeton", lambda: JETON),
                   mock.patch.object(hj, "API_ATLASSIAN", self.url), mock.patch.object(hj, "PAUSE", 0),
                   mock.patch.object(hj, "_JETON", None),
                   mock.patch.object(hj, "ouvrir_magasin", lambda: self.magasin),
                   mock.patch.dict(sys.modules, {"flow_store": faux_flow_store(self.magasin)}),
                   mock.patch.dict(os.environ)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("CLAUDECODE", None)           # `check` refuse une session Claude Code : les tests y tournent comme dans le Terminal
        self.attentes = []
        p = mock.patch.object(hj.time, "sleep", lambda s: self.attentes.append(s))
        p.start()
        self.addCleanup(p.stop)
        self.ecrire_reglages("scopes")

    def ecrire_reglages(self, mode: str | None = "scopes", extra: str = "", cloud: str | None = CLOUD_ID,
                        expiration: str | None = "2099-12-31", garde: list[str] | None = None, livraison: bool = True):
        """Réglages de Jira. mode : « scopes », « classique » (refusé par l'outil) ou None (réglage absent) ; cloud et
        expiration : None retire le réglage ; garde : les lignes des réglages du périmètre (scope_projects, forbidden_projects), les
        clés fictives de R-20261028-96 par défaut, une liste vide pour n'en écrire aucune ; livraison : écrit en dernier le bloc
        `delivery_fields` de la table FACTICE (R-20261114-108), faux pour tester l'absence de la table."""
        nouveau = {"scopes": "scoped", "classique": "classic"}.get(mode, mode)
        lignes = [f"jira_site: {self.url}", f"jira_email: {EMAIL}"]
        lignes += GARDE_DE_TEST if garde is None else garde
        if nouveau is not None:
            lignes.append(f"jira_token_type: {nouveau}")
        if cloud is not None:
            lignes.append(f"jira_cloud_id: {cloud}")
        if expiration is not None:
            lignes.append(f"jira_token_expires: {expiration}")
        if livraison:
            extra += ("" if extra.endswith("\n") or not extra else "\n") + table_factice.yaml()
        (self.ws / "Flux-Lab" / "flux.yaml").write_text("\n".join(lignes) + "\n" + extra, encoding="utf-8")

    def ecrire_export(self, lignes, nom=None) -> str:
        """Charge les lignes (clé, type, équipe, terminé[, mise à jour]) comme tickets de la base fictive et rend SENTINELLE (retirée par
        `lancer`). Un ticket déjà présent garde son indicateur « avec historique ». Une résolution date de 30 jours : sous la durée de
        conservation, quelle que soit la date du jour. Les titres ne sont jamais écrits."""
        resolu = (dt.datetime.combine(hj.aujourd_hui() - dt.timedelta(days=30), dt.time(10, 0), tzinfo=PARIS))
        cree = dt.datetime(2026, 1, 2, 9, 0, tzinfo=PARIS)
        for ligne in lignes:
            cle, typ, equipe, termine = ligne[:4]
            maj = ligne[4] if len(ligne) > 4 and ligne[4] is not None else cree
            ancien = self.magasin.stock.get(cle)
            self.magasin.stock[cle] = {
                "cle": cle, "projet": cle.rsplit("-", 1)[0].upper() if "-" in cle else "", "type": typ, "cree": cree,
                "resolu": resolu if termine else None, "maj": maj, "a_historique": ancien["a_historique"] if ancien else False,
                "equipes": [e.strip() for e in equipe.split(";") if e.strip()], "etat": "Done" if termine else "Open"}
        return SENTINELLE

    def lancer(self, *argv):
        sortie = io.StringIO()
        code = 0
        argv = [a for a in argv if a != SENTINELLE]
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(sortie):
            try:
                hj.main(list(argv))
            except SystemExit as sortie_code:
                code = sortie_code.code or 0
        return code, sortie.getvalue()

    def cache(self) -> dict:
        return self.magasin.cache()

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
