"""
Aide des tests de `analyse` et `coach` (change story-quality-audit, tâches 3.7 à 3.9) : faux serveur d'analyse local, fausse clé, faux
magasin du schéma quality (relectures d'équipe, éléments, verdicts, retours de coaching, empreintes de surcouche). Aucune vraie base,
aucun vrai Trousseau, aucun appel réseau réel : l'adresse du moteur est celle du faux serveur. Les chaînes « zz » sont distinctives.

Le socle fictif et la surcouche d'essai sont ceux de aide_story_quality.py.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import random
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from aide_story_quality import (EQUIPE_A, EQUIPE_B, IDENTIFIANT_FICTIF, SOCLE, SURCOUCHE, EspaceCollecte, sq, so)
import story_quality_audit_store as audit_store    # noqa: E402
import story_quality_engine as engine              # noqa: E402

CLE_ANALYSE = "fausse-cle-analyse-zz-777"
SERVICE_CLE = "service-fictif"
ANCIEN = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
TEXTE_NOTE = "zznote distinctive du dossier de contexte"
PAIRE_SANS_SURCOUCHE = ("socle-fictif", "3", "", "")

BLOC = """story_quality:
  queries:
    alpha: "project = ZZA"
  issue_types:
    story: [Story]
    epic: [Epic]
  engine:
    model: modele-fictif
    keychain_service: {service}
    input_price_per_token: 0.000003
    output_price_per_token: 0.000015
    feedback_max_chars: 80
{plafond}"""


class FauxMoteur:
    """État du faux serveur d'analyse : requêtes reçues (corps, en-têtes), réponse choisie par le test."""

    def __init__(self):
        self.requetes: list[dict] = []
        self.entetes: list[dict] = []
        self.chemins: list[str] = []
        self.statut = 200
        self.echec_a: int | None = None          # à partir de la requête n° (1, 2, …), réponse 500
        self.redirection = False                 # 307 vers un autre chemin du même serveur
        self.fabriquer = self.valide

    @staticmethod
    def criteres(requete: dict) -> list[str]:
        return [c["code"] for c in json.loads(requete["messages"][0]["content"])["criteria"]]

    def valide(self, requete: dict) -> str:
        """Réponse correcte : « met » partout (avec un retour court en mode coaching)."""
        coaching = "feedback" in requete["system"]
        lignes = [{"criterion": c, "verdict": "met", **({"feedback": f"Conseil sur {c}"} if coaching else {})}
                  for c in self.criteres(requete)]
        return json.dumps({"verdicts": lignes})

    def textes(self) -> list[str]:
        return [r["messages"][0]["content"] for r in self.requetes]


def fabriquer_moteur(faux: FauxMoteur) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            corps = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            faux.requetes.append(corps)
            faux.entetes.append({k.lower(): v for k, v in self.headers.items()})
            faux.chemins.append(self.path)
            statut = faux.statut
            if faux.echec_a is not None and len(faux.requetes) >= faux.echec_a:
                statut = 500
            if faux.redirection and self.path == "/v1/messages":
                statut = 307
            if statut != 200:
                donnees = json.dumps({"error": "zzcorps-d-erreur-distinctif"}).encode()
            else:
                donnees = json.dumps({"content": [{"type": "text", "text": faux.fabriquer(corps)}]}).encode()
            self.send_response(statut)
            if statut == 307:
                self.send_header("Location", "/ailleurs")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(donnees)))
            self.end_headers()
            self.wfile.write(donnees)

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


class MagasinAnalyseMemoire:
    """Faux magasin (protocole de story_quality_audit_store.MagasinAnalyse) : mêmes règles de remplacement des verdicts."""

    def __init__(self):
        self.items: dict[str, dict] = {}
        self.contenus: dict[str, tuple] = {}
        self.relues: set[str] = set()
        self.audits: dict[tuple, str | None] = {}         # (paire, clé) -> empreinte du texte du dernier verdict d'audit
        self.verdicts: list[dict] = []                    # tous les verdicts écrits (audit et échantillon)
        self.coaching: dict[str, list] = {}               # clé -> lignes du retour
        self.coaching_ecritures: list[tuple] = []
        self.empreintes: dict[tuple, str] = {}
        self.empreinte_concurrente: str | None = None     # empreinte posée par un « autre lancement » juste avant la nôtre
        self.ecritures = 0
        self.ouvert = True
        self.versions = 0

    def _empreinte(self, cle):
        self.versions += 1
        return f"h-{cle}-{self.versions}"

    def ajouter(self, cle, equipes=(EQUIPE_A,), genre="story", titre=None, description="", criteres=""):
        self.items[cle] = {"key": cle, "kind": genre, "updated_at": ANCIEN, "teams": list(equipes)}
        titre = titre if titre is not None else f"Titre numéro {len(self.contenus) + 1}"
        self.contenus[cle] = (titre, description, criteres, self._empreinte(cle))

    def mettre_a_jour(self, cle, description=None):
        """Texte changé dans Jira puis recollecté : nouvelle empreinte, mise à jour Jira postérieure."""
        self.recollecter(cle, description)
        self.items[cle]["updated_at"] = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)

    def recollecter(self, cle, description=None):
        """Nouveau texte (nouvelle empreinte) sans toucher à updated_at."""
        titre, ancienne, criteres, _ = self.contenus[cle]
        self.contenus[cle] = (titre, description if description is not None else ancienne + " modifié", criteres, self._empreinte(cle))

    def changer_statut(self, cle):
        """Mise à jour Jira sans changement de texte : même empreinte."""
        self.items[cle]["updated_at"] = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)

    def elements(self):
        return [dict(self.items[k], teams=list(self.items[k]["teams"]), content_hash=self.contenus[k][3]) for k in sorted(self.items)]

    def textes(self, cles):
        return {k: self.contenus[k] for k in cles if k in self.contenus}

    def derniers_audits(self, paire):
        return {cle: empreinte for (p, cle), empreinte in self.audits.items() if p == tuple(paire)}

    def equipes_relues(self):
        return set(self.relues)

    def enregistrer_audit(self, cle, paire, verdicts, echantillon, empreinte=None):
        self.ecritures += 1
        paire = tuple(paire)
        if echantillon:
            self.verdicts = [v for v in self.verdicts if not (v["key"] == cle and v["sample"])]
        else:
            self.verdicts = [v for v in self.verdicts if not (v["key"] == cle and not v["sample"] and v["pair"] == paire)]
            self.audits[(paire, cle)] = empreinte
        for code, origine, lien, verdict in verdicts:
            self.verdicts.append({"key": cle, "pair": paire, "code": code, "origin": origine, "link": lien, "verdict": verdict,
                                  "sample": bool(echantillon), "hash": empreinte})

    def enregistrer_coaching(self, cle, paire, lignes):
        self.ecritures += 1
        self.coaching[cle] = list(lignes)
        self.coaching_ecritures.append((cle, tuple(paire)))

    def lire_coaching(self, cles):
        return {k: list(self.coaching[k]) for k in cles if k in self.coaching}

    def empreinte_surcouche(self, identifiant, version):
        return self.empreintes.get((identifiant, version))

    def enregistrer_empreinte(self, identifiant, version, empreinte):
        if self.empreinte_concurrente is not None:
            self.empreintes.setdefault((identifiant, version), self.empreinte_concurrente)
        self.empreintes.setdefault((identifiant, version), empreinte)
        return self.empreintes[(identifiant, version)]

    def fermer(self):
        self.ouvert = False

    def audites(self, paire=None):
        """Clés ayant un verdict d'audit (hors échantillon), à la paire donnée ou à toutes."""
        return {v["key"] for v in self.verdicts if not v["sample"] and (paire is None or v["pair"] == tuple(paire))}


class EspaceAnalyse(EspaceCollecte):
    """Espace de travail temporaire (réglages, socle fictif, dossier de contexte), faux moteur, fausse clé, faux magasin. `lancer` appelle
    l'outil réel dans le processus."""

    PLAFOND = "    cap_per_launch: 10\n"

    def setUp(self):
        super().setUp()
        self.moteur = FauxMoteur()
        self.serveur_moteur = fabriquer_moteur(self.moteur)
        threading.Thread(target=self.serveur_moteur.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.addCleanup(self.serveur_moteur.server_close)
        self.addCleanup(self.serveur_moteur.shutdown)
        self.url_moteur = f"http://127.0.0.1:{self.serveur_moteur.server_address[1]}/v1/messages"
        self.analyse = MagasinAnalyseMemoire()
        self.cle = CLE_ANALYSE
        self.ouvertures_analyse = 0
        self.contexte = self.maison / "contexte"
        (self.contexte / "regles").mkdir(parents=True)
        (self.contexte / "notes").mkdir()
        (self.contexte / "notes" / "note.md").write_text(TEXTE_NOTE, encoding="utf-8")
        self.socle = self.maison / "socle.json"
        self.socle.write_text(json.dumps(SOCLE), encoding="utf-8")
        self.environ.update({so.CONTEXT_VARIABLE: str(self.contexte), sq.GRID_VARIABLE: str(self.socle)})
        self.ecrire_moteur()
        self.relues(EQUIPE_A, EQUIPE_B)

    def ecrire_moteur(self, plafond: str | None = None):
        bloc = BLOC.format(service=SERVICE_CLE, plafond=self.PLAFOND if plafond is None else plafond)
        self.ecrire_reglages(bloc=bloc)

    def relues(self, *equipes):
        self.analyse.relues.update(equipes)

    def surcouche(self, texte=SURCOUCHE):
        (self.contexte / "regles" / so.OVERLAY_FILE).write_text(texte, encoding="utf-8")

    def remplir(self, n, equipes=(EQUIPE_A,), genre="story", debut=1):
        for i in range(debut, debut + n):
            self.analyse.ajouter(f"ZZA-{i:03d}", equipes, genre, description=f"Texte distinctif {i}")

    def lancer(self, *argv, environ=None, reponse: str | None = "confirmer", graine: int = 7, terminal: bool = True, cle="defaut"):
        """(code, sortie, erreur). `reponse` : ce que l'utilisateur tape à la confirmation (None : fin de l'entrée ; « confirmer » : le
        mot de confirmation de la langue demandée, « yes » avec --language en, « oui » sinon)."""
        if reponse == "confirmer":
            reponse = "yes" if "--language" in argv and argv[argv.index("--language") + 1:][:1] == ("en",) else "oui"
        self.invites: list[tuple[str, str, int]] = []       # (question, sortie déjà écrite, requêtes déjà reçues)
        sortie, erreur = io.StringIO(), io.StringIO()

        def ouvrir():
            self.ouvertures_analyse += 1
            return self.analyse

        def demander(question):
            self.invites.append((question, sortie.getvalue(), len(self.moteur.requetes)))
            if reponse is None:
                raise EOFError
            return reponse

        def lire_cle(service):
            self.service_demande = service
            return self.cle if cle == "defaut" else cle

        avant = self.fichiers_temporaires()
        with mock.patch.object(audit_store, "ouvrir", ouvrir), mock.patch.object(engine, "demander", demander), \
                mock.patch.object(engine, "lire_cle", lire_cle), mock.patch.object(engine, "est_terminal", lambda: terminal), \
                mock.patch.object(engine, "nouvel_alea", lambda: random.Random(graine)), \
                mock.patch.object(engine, "identifiants", lambda: [IDENTIFIANT_FICTIF]), \
                mock.patch.object(engine, "ENGINE_URL", self.url_moteur), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = sq.main(list(argv), self.environ if environ is None else environ, identifiers=[IDENTIFIANT_FICTIF])
        self.nouveaux = self.fichiers_temporaires() - avant            # fichiers que l'outil aurait écrits
        return code, sortie.getvalue(), erreur.getvalue()

    def fichiers_temporaires(self):
        from pathlib import Path
        return {p for p in Path(self.temp.name).rglob("*") if p.is_file()}

    def tout(self, resultat):
        return resultat[1] + resultat[2]
