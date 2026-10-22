"""
Aide commune des tests de tools/story_quality.py (change story-quality-audit, groupe 2). Aucun effet réel :

  - un dossier de contexte temporaire (variable PMZILLA_LAB_CONTEXT) dont le sous-dossier regles/ porte la surcouche de l'essai ;
  - un socle FICTIF (jumeau JSON temporaire, variable PMZILLA_LAB_STORY_GRID) : le vrai socle de la tâche 2.3 n'est jamais lu ;
  - une liste de noms sensibles FICTIVE (variable PMZILLA_LAB_SENSITIVE_NAMES) et une liste d'identifiants personnels fournie à l'outil ;
  - l'outil RÉEL est appelé dans le processus (main(argv, environ, identifiers)) ; aucune base, aucun Jira, aucune clé.

Les chaînes qui portent la marque « zz » sont distinctives : un test qui les retrouve dans une sortie prouve que l'outil écrit une valeur
qu'il ne doit pas écrire (raison de désactivation, identifiant, résumé de contexte). Données inventées.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import story_quality as sq                 # noqa: E402
import story_quality_overlay as so         # noqa: E402

RACINE = TOOLS.parent
EXEMPLE = RACINE / "docs" / "pmzilla" / "surcouche-qualite-exemple.yaml"
SCHEMA = TOOLS / "story_quality_overlay.schema.json"

NOM_FICTIF = "Zorglub Quarante"            # nom sensible fictif
IDENTIFIANT_FICTIF = "zzidentifiant-perso"  # identifiant personnel fictif
RAISON = "zzraison de desactivation distinctive"
IDENTIFIANT_SURCOUCHE = "zzidentifiant-surcouche"
RESUME = "zzresume du contexte produit distinctif"
DISTINCTIFS = (RAISON, IDENTIFIANT_SURCOUCHE, RESUME)


def critere_socle(code, lien="refinement", na=None):
    return {"code": code, "label_fr": f"Libellé {code}", "label_en": f"Label {code}", "definition": f"Définition du critère {code}",
            "engine_question": f"Question du critère {code} ?", "not_applicable_condition": na, "link": lien,
            "source": "hors bibliothèque"}


SOCLE = {
    "identifier": "socle-fictif",
    "version": 3,
    "story": [critere_socle("story-un", "ticket_template", "Sans objet pour une story technique"), critere_socle("story-deux"),
              critere_socle("story-trois", "definition_of_ready")],
    "epic": [critere_socle("epic-un", "discovery_workflow_step"), critere_socle("epic-deux")],
}

SURCOUCHE = f"""identifier: {IDENTIFIANT_SURCOUCHE}
version: 2
product_context_summary: "{RESUME}"
structure:
  story:
    sections: [Contexte, Besoin]
    definition_of_ready: [Rôle nommé]
    vocabulary: [Étape de découverte]
  epic:
    sections: [Problème, Mesure]
criteria:
  story:
    - code: orga-role
      label_fr: Rôle nommé
      label_en: Named role
      definition: La story nomme un rôle.
      engine_question: La story nomme-t-elle un rôle ?
      not_applicable_condition: Story technique.
      link: ticket_template
  epic:
    - code: orga-objectif
      label_fr: Objectif lié
      label_en: Linked objective
      definition: L'epic nomme un objectif.
      engine_question: L'epic nomme-t-elle un objectif ?
      link: discovery_workflow_step
disabled:
  - code: story-deux
    reason: "{RAISON}"
"""


class Espace(unittest.TestCase):
    """Dossier de contexte, socle et liste de noms temporaires ; `lancer` appelle l'outil réel dans le processus."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.contexte = base / "contexte"
        (self.contexte / "regles").mkdir(parents=True)
        self.socle = base / "socle.json"
        self.socle.write_text(json.dumps(SOCLE), encoding="utf-8")
        self.noms = base / "noms.txt"
        self.noms.write_text(f"# liste fictive\n{NOM_FICTIF}\nzorglub\n", encoding="utf-8")
        self.environ = {so.CONTEXT_VARIABLE: str(self.contexte), sq.GRID_VARIABLE: str(self.socle), sq.NAMES_VARIABLE: str(self.noms)}

    @property
    def fichier(self):
        return self.contexte / "regles" / so.OVERLAY_FILE

    def ecrire(self, texte=SURCOUCHE):
        self.fichier.write_text(texte, encoding="utf-8")

    def lancer(self, *argv, environ=None):
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = sq.main(list(argv), self.environ if environ is None else environ, identifiers=[IDENTIFIANT_FICTIF])
        return code, sortie.getvalue(), erreur.getvalue()


# ---------------------------------------------------------------------------------------------------------------------------------
# Groupe 3 (collect, review, puis analyse et coach) : faux serveur Jira, faux jeton, faux magasin du schéma quality, fausse connexion.
# Aucune vraie base, aucun vrai Jira, aucun vrai Trousseau. Les chaînes « zz » / « ZZ » sont distinctives.
# ---------------------------------------------------------------------------------------------------------------------------------

import base64                                   # noqa: E402
import datetime as dt                           # noqa: E402
import os                                       # noqa: E402
import random                                   # noqa: E402
import threading                                # noqa: E402
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer   # noqa: E402
from unittest import mock                       # noqa: E402
from urllib.parse import urlparse               # noqa: E402

import history_jira as hj                        # noqa: E402
import story_quality_store as store              # noqa: E402

JETON = "faux-jeton-zz-000"
EMAIL = "utilisateur@exemple.org"
CLOUD_ID = "cloud-fictif"
CHAMP_CRITERES = "customfield_10500"
CHAMP_EQUIPE = "customfield_10001"
CHAMP_PERSONNE = "customfield_20000"            # champ de type utilisateur
CHAMP_PERSONNES = "customfield_20001"           # champ de type liste d'utilisateurs
EQUIPE_A = "Equipe Zzalpha"
EQUIPE_B = "Equipe Zzbeta"
REQUETE_A = "project = ZZA"
REQUETE_B = "project = ZZB"
NOMS_COLLECTE = ["Zorglub Quarante", "Zorglub"]

CHAMPS_JIRA = [
    {"id": "summary", "name": "Summary", "schema": {"type": "string", "system": "summary"}},
    {"id": "description", "name": "Description", "schema": {"type": "string", "system": "description"}},
    {"id": "assignee", "name": "Assignee", "schema": {"type": "user", "system": "assignee"}},
    {"id": CHAMP_CRITERES, "name": "Critères zz", "schema": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:textarea"}},
    {"id": CHAMP_EQUIPE, "name": "Equipe zz", "schema": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:textfield"}},
    {"id": CHAMP_PERSONNE, "name": "PO zz", "schema": {"type": "user", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:userpicker"}},
    {"id": CHAMP_PERSONNES, "name": "Relecteurs zz", "schema": {"type": "array", "items": "user",
                                                               "custom": "com.atlassian.jira.plugin.system.customfieldtypes:multiuserpicker"}},
]


def adf(*morceaux) -> dict:
    """Document riche inventé : chaque morceau est un texte, ou un tuple ("mention", identifiant)."""
    contenu = []
    for m in morceaux:
        if isinstance(m, tuple) and m[0] == "mention":
            contenu.append({"type": "mention", "attrs": {"id": m[1], "text": "@" + m[1]}})
        else:
            contenu.append({"type": "text", "text": m})
    return {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": contenu}]}


def date_api(jour: dt.date) -> str:
    return f"{jour.isoformat()}T10:00:00.000+0200"


def ticket(cle: str, type_: str = "Story", equipe: str | None = EQUIPE_A, resolu_il_y_a: int | None = None, titre: str | None = None,
           description=None, criteres=None, parent: str | None = None) -> dict:
    """Ticket inventé, sous la forme de l'API (champs complets : le faux serveur ne rend que ceux demandés). Il porte aussi des champs
    de personne et des à-côtés que la collecte ne doit jamais demander."""
    aujourdhui = dt.date.today()
    champs = {
        "summary": titre if titre is not None else f"Titre de {cle}",
        "description": description if description is not None else adf(f"Description de {cle}"),
        CHAMP_CRITERES: criteres if criteres is not None else f"Critères de {cle}",
        "issuetype": {"name": type_},
        "status": {"name": "En cours", "statusCategory": {"key": "indeterminate"}},
        CHAMP_EQUIPE: equipe,
        "parent": {"key": parent} if parent else None,
        "created": date_api(aujourdhui - dt.timedelta(days=60)),
        "updated": date_api(aujourdhui - dt.timedelta(days=2)),
        "resolutiondate": date_api(aujourdhui - dt.timedelta(days=resolu_il_y_a)) if resolu_il_y_a is not None else None,
        "assignee": {"accountId": "zzcompte-assignee", "displayName": "Personne Zzassignee"},
        "reporter": {"displayName": "Personne Zzreporter"},
        "comment": {"comments": [{"body": "zzcommentaire"}]},
        CHAMP_PERSONNE: {"displayName": "Personne Zzpo"},
    }
    return {"id": str(abs(hash(cle)) % 100000), "key": cle, "fields": champs}


class FauxJira:
    """État partagé du faux serveur Jira : tickets par requête JQL, liste des champs, journal des appels et des corps."""

    def __init__(self):
        self.par_requete: dict[str, list[dict]] = {}
        self.champs = list(CHAMPS_JIRA)
        self.appels: list[tuple[str, str]] = []
        self.corps: list[dict] = []              # corps des recherches (jql, fields, ...)
        self.refus: int | None = None            # code HTTP rendu à tout appel authentifié
        self.prefixe = f"/ex/jira/{CLOUD_ID}"
        self.attendu = "Basic " + base64.b64encode(f"{EMAIL}:{JETON}".encode()).decode()

    def ajouter(self, requete: str, *tickets_):
        self.par_requete.setdefault(requete, []).extend(tickets_)

    def recherches(self) -> list[dict]:
        return list(self.corps)


def fabriquer_serveur(faux: FauxJira) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def repondre(self, code, corps=None):
            donnees = json.dumps(corps if corps is not None else {}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(donnees)))
            self.end_headers()
            self.wfile.write(donnees)

        def traiter(self, methode):
            chemin = urlparse(self.path)
            corps = {}
            if methode == "POST":
                corps = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            if self.headers.get("Authorization") != faux.attendu or not chemin.path.startswith(faux.prefixe + "/"):
                return self.repondre(401, {"message": "Personne Zzrefus"})
            api = chemin.path[len(faux.prefixe):]
            faux.appels.append((methode, api))
            if faux.refus:
                return self.repondre(faux.refus, {"message": "Personne Zzrefus"})
            if api == "/rest/api/3/field" and methode == "GET":
                return self.repondre(200, faux.champs)
            if api == "/rest/api/3/search/jql" and methode == "POST":
                faux.corps.append(corps)
                demandes = corps.get("fields") or []
                tickets_ = faux.par_requete.get(corps.get("jql"), [])
                rendus = [{"id": tk["id"], "key": tk["key"], "fields": {c: v for c, v in tk["fields"].items() if c in demandes}}
                          for tk in tickets_]
                return self.repondre(200, {"issues": rendus})
            return self.repondre(404)

        def do_GET(self):
            self.traiter("GET")

        def do_POST(self):
            self.traiter("POST")

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


class MagasinMemoire:
    """Faux magasin du schéma quality (protocole de story_quality_store.MagasinQualite), avec la même règle d'écriture : une collecte
    s'écrit en une fois ou pas du tout (`echec` levée à l'écriture : rien n'est écrit). Sert aussi aux blocs suivants (relectures
    d'équipe pour la garde de D5, éléments et contenus)."""

    def __init__(self):
        self.elements: dict[str, dict] = {}      # clé -> {kind, parent_key, status_category, created_at, ..., out_of_collection}
        self.equipes: dict[str, list[str]] = {}  # clé -> équipes
        self.contenus: dict[str, tuple] = {}     # clé -> (titre, description, critères, empreinte, remplacements)
        self.attributs: dict[str, bool] = {}     # équipe -> drapeau « un seul PO »
        self.relectures: list[tuple[str, int]] = []
        self.ecritures = 0
        self.echec: Exception | None = None
        self.ouvert = True
        self.tirages: list[list[str]] = []      # clés tirées par echantillon (lecture des tests seulement)

    def enregistrer_collecte(self, elements, attributs, complet, vus=None):
        if self.echec is not None:
            raise self.echec
        cles = [e.key for e in elements]
        vus = cles if vus is None else list(vus)
        revenus = sum(1 for c in cles if c in self.elements and self.elements[c]["out_of_collection"])
        for e in elements:
            self.elements[e.key] = {"kind": e.kind, "parent_key": e.parent_key, "status_category": e.status_category,
                                    "created_at": e.created_at, "updated_at": e.updated_at, "resolved_at": e.resolved_at,
                                    "out_of_collection": False}
            self.equipes[e.key] = list(dict.fromkeys(e.teams))
            self.contenus[e.key] = (e.title, e.description, e.acceptance_criteria, e.content_hash, e.replacements)
        self.attributs.update({k: bool(v) for k, v in attributs.items()})
        marques = 0
        if complet:
            for cle, element in self.elements.items():
                if cle not in vus and not element["out_of_collection"]:
                    element["out_of_collection"] = True
                    marques += 1
        self.ecritures += 1
        return marques, revenus

    def echantillon(self, equipe, taille, alea):
        cles = sorted(c for c, eqs in self.equipes.items() if equipe in eqs and not self.elements[c]["out_of_collection"])
        if not cles:
            return []
        tirees = alea.sample(cles, min(taille, len(cles)))
        self.tirages.append(tirees)
        return [self.contenus[c][:3] for c in tirees]

    def enregistrer_relecture(self, equipe, taille):
        if self.echec is not None:
            raise self.echec
        self.relectures.append((equipe, taille))

    def fermer(self):
        self.ouvert = False

    def ajouter(self, cle, equipes=(EQUIPE_A,), titre=None, description="", criteres="", sorti=False, kind="story"):
        """Élément déjà collecté (pour review et les blocs suivants)."""
        self.elements[cle] = {"kind": kind, "parent_key": None, "status_category": "new", "created_at": None, "updated_at": None,
                              "resolved_at": None, "out_of_collection": sorti}
        self.equipes[cle] = list(equipes)
        self.contenus[cle] = (titre if titre is not None else f"Titre de {cle}", description, criteres, "h", 0)


class FauxCurseur:
    def __init__(self, conn):
        self.conn = conn
        self.resultat: list = []
        self.rowcount = -1

    def execute(self, sql, params=()):
        self.conn.requetes.append((sql, params))
        if self.conn.echec is not None and self.conn.echec[0] in sql:
            raise self.conn.echec[1]
        self.resultat, self.rowcount = [], -1
        for fragment, lignes in self.conn.reponses.items():
            if fragment in sql:
                self.resultat = list(lignes(params) if callable(lignes) else lignes)
                self.rowcount = len(self.resultat) if sql.lstrip().upper().startswith("SELECT") else self.conn.rowcount
                return
        self.rowcount = self.conn.rowcount

    def fetchone(self):
        return self.resultat[0] if self.resultat else None

    def fetchall(self):
        return list(self.resultat)


class FausseConnexion:
    """Fausse connexion psycopg : journal des requêtes, réponses choisies par fragment de SQL, validations et annulations comptées.
    `echec` : (fragment, exception) levée quand une requête contient le fragment."""

    def __init__(self, reponses: dict | None = None, rowcount: int = 0):
        self.reponses = reponses or {}
        self.rowcount = rowcount
        self.requetes: list[tuple[str, tuple]] = []
        self.commits = self.rollbacks = 0
        self.echec: tuple[str, Exception] | None = None
        self.fermee = False

    def cursor(self):
        return FauxCurseur(self)

    def commit(self):
        self.commits += 1
        self.requetes.append(("COMMIT", ()))

    def rollback(self):
        self.rollbacks += 1
        self.requetes.append(("ROLLBACK", ()))

    def close(self):
        self.fermee = True


REGLAGES_COLLECTE = """story_quality:
  queries:
    alpha: "{a}"
    beta: "{b}"
  issue_types:
    story: [Story]
    epic: [Epic]
  acceptance_criteria_field: {criteres}
  engine:
    model: modele-fictif
    keychain_service: service-fictif
    input_price_per_token: 0
    output_price_per_token: 0
    cap_per_launch: 10
"""

REFERENTIEL = f"""source_date: 2026-10-01
sites: [Site Zz]
departments:
  - name: Departement Zz
    site: Site Zz
    headcount: 9
    teams: [{EQUIPE_A}, {EQUIPE_B}]
teams:
  - name: {EQUIPE_A}
    headcount: 5
    site: Site Zz
    single_po: true
  - name: {EQUIPE_B}
    headcount: 4
"""


class EspaceCollecte(unittest.TestCase):
    """Faux Jira local, espace de travail et dossier personnel temporaires, faux magasin ; `lancer` appelle l'outil réel dans le processus
    avec un environnement sans la variable de session (sauf si le test la pose)."""

    def setUp(self):
        self.faux = FauxJira()
        self.serveur = fabriquer_serveur(self.faux)
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        self.addCleanup(self.serveur.server_close)
        self.addCleanup(self.serveur.shutdown)
        self.url = f"http://127.0.0.1:{self.serveur.server_address[1]}"
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ws = Path(self.temp.name) / "espace"
        self.flux = self.ws / "Flux-Lab"
        self.flux.mkdir(parents=True)
        self.maison = Path(self.temp.name) / "maison"
        self.maison.mkdir()
        self.noms = Path(self.temp.name) / "noms.txt"
        self.noms.write_text("# liste fictive\n" + "\n".join(NOMS_COLLECTE) + "\n", encoding="utf-8")
        self.magasin = MagasinMemoire()
        self.ouvertures = 0

        def ouvrir():
            self.ouvertures += 1
            return self.magasin

        for p in (mock.patch.object(hj, "WORKSPACE", self.ws), mock.patch.object(hj, "FLUX_DIR", self.flux),
                  mock.patch.object(hj, "CONFIG_FILE", self.flux / "flux.yaml"), mock.patch.object(hj, "lire_jeton", lambda: JETON),
                  mock.patch.object(hj, "API_ATLASSIAN", self.url), mock.patch.object(hj, "PAUSE", 0),
                  mock.patch.object(hj, "_JETON", None), mock.patch.object(store, "ouvrir", ouvrir),
                  mock.patch.dict(os.environ, {"HOME": str(self.maison)})):
            p.start()
            self.addCleanup(p.stop)
        self.environ = {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.noms), "HOME": str(self.maison)}
        self.ecrire_reglages()

    def ecrire_reglages(self, criteres: str = CHAMP_CRITERES, equipe: str | None = CHAMP_EQUIPE, bloc: str | None = None):
        lignes = [f"jira_site: {self.url}", f"jira_email: {EMAIL}", "jira_token_type: scoped", f"jira_cloud_id: {CLOUD_ID}",
                  "jira_token_expires: 2099-12-31"]
        if equipe:
            lignes.append(f"export_team_field: {equipe}")
        texte = "\n".join(lignes) + "\n"
        texte += REGLAGES_COLLECTE.format(a=REQUETE_A, b=REQUETE_B, criteres=criteres) if bloc is None else bloc
        (self.flux / "flux.yaml").write_text(texte, encoding="utf-8")

    def ecrire_referentiel(self, texte: str = REFERENTIEL):
        (self.flux / "organisation.yaml").write_text(texte, encoding="utf-8")

    def lancer(self, *argv, environ=None, reponse: str | None = None, graine: int = 7,
               terminal: bool = True):
        """(code, sortie, erreur). `reponse` : ce que l'utilisateur tape à la question de review (None : fin de l'entrée).
        `terminal` : ce que répond le contrôle « stdin et stdout sont des terminaux » de review."""
        import story_quality_review as review

        def demander(question):
            self.questions.append(question)
            if reponse is None:
                raise EOFError
            return reponse

        self.questions = []
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.object(review, "demander", demander), mock.patch.object(review, "nouvel_alea", lambda: random.Random(graine)), \
                mock.patch.object(review, "est_terminal", lambda: terminal), contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = sq.main(list(argv), self.environ if environ is None else environ, identifiers=[IDENTIFIANT_FICTIF])
        return code, sortie.getvalue(), erreur.getvalue()

    def fichiers_ecrits(self) -> list[Path]:
        """Fichiers du dossier temporaire (espace, dossier personnel), hors ceux que le test a écrits lui-même."""
        a_moi = {self.flux / "flux.yaml", self.flux / "organisation.yaml", self.noms}
        return [p for p in Path(self.temp.name).rglob("*") if p.is_file() and p not in a_moi]
