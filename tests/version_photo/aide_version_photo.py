"""
Aide commune des tests de tools/version_photo.py (change version-quality-photo). Aucun effet réel :

  - un dossier temporaire pour le fichier de réglages (variable VERSION_PHOTO_SETTINGS), jamais Flux-Lab/ ;
  - l'instant du lancement est fixé (VERSION_PHOTO_NOW) ;
  - le magasin est un magasin EN MÉMOIRE qui rejoue l'interface de MagasinBase (aucun PostgreSQL) ; une fausse connexion sert à lire
    les requêtes de MagasinBase ; les essais avec une vraie base sont dans tests/db/test_flow_version_photo_outil.py (sautés sans base) ;
  - l'outil RÉEL est appelé dans le processus (main(argv, environ, ouvrir_magasin)) sans la variable de session Claude Code.

Les équipes, versions et types portent la marque « zz » : un test qui la retrouve dans une sortie prouve que l'outil écrit une valeur qu'il
ne doit pas écrire. Données inventées.
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import version_photo as vp          # noqa: E402

UTC = dt.timezone.utc
AUJOURDHUI = dt.datetime(2026, 10, 23, 14, 0, tzinfo=UTC)          # un vendredi ; la semaine en cours commence le lundi 2026-10-19
MARQUES = ("zzequipe", "zzversion", "zzdefaut", "zzcle", "ZZ")
REGLAGES = "defect_types: [zzdefaut]\nportfolio_types: [zzepic]\n"


def jour(texte: str, heure: int = 12) -> dt.datetime:
    """Un instant UTC à une heure du jour donné (AAAA-MM-JJ)."""
    return dt.datetime.combine(dt.date.fromisoformat(texte), dt.time(heure), tzinfo=UTC)


def regles(**remplacements) -> vp.Regles:
    base = dict(defauts=frozenset({"bug"}), portefeuille=frozenset({"epic"}), termine=frozenset({"closed", "resolved"}), periode_jours=365)
    base.update(remplacements)
    return vp.Regles(**base)


def defaut(cree="2026-01-05", resolu=None, fix=(), affects=(), periodes=(), transitions=(), equipe="Alpha", type_="Bug", hors_export=False):
    return vp.Ticket(type=type_, equipe=equipe, cree=jour(cree), resolu=jour(resolu) if resolu else None, hors_export=hors_export,
                     fix=frozenset(fix), affects=frozenset(affects), periodes=tuple(periodes), transitions=tuple(transitions))


class MagasinMemoire:
    """Le magasin de version_photo.py en mémoire : mêmes méthodes que MagasinBase, mêmes effets visibles (une validation termine la
    transaction, une fermeture sans validation l'annule)."""

    def __init__(self, tickets=(), marqueur=vp.VERSION_MASQUAGE_ATTENDUE, sorties=()):
        self.tickets = list(tickets)
        self.sorties = list(sorties)          # (nom, date de sortie, drapeau[, ticket sorti de l'export]) de chaque ligne de versions courantes stockée
        self.marqueur = marqueur          # version de flow.masking_version() (masquage des croisements de R-144) ; None : fonction absente
        self.etat = {"passages": [], "semaines": {}, "lignes": [], "versions": {}, "adoptions": []}
        self._photo = copy.deepcopy(self.etat)
        self.ouvertures = 0

    # --- interface --------------------------------------------------------------------------------------------------
    def lire_tickets(self, types_defaut):
        return list(self.tickets)

    def semaines(self):
        return {lundi: self.etat["passages"][s["passage"]]["source"] for lundi, s in self.etat["semaines"].items()}

    def reconstruction_existe(self):
        return any(p["source"] == "reconstructed" and not p.get("supprime") for p in self.etat["passages"])

    def _supprimer_passages(self, numeros):
        lundis = {l for l, s in self.etat["semaines"].items() if s["passage"] in numeros}
        self.etat["semaines"] = {l: s for l, s in self.etat["semaines"].items() if l not in lundis}
        self.etat["lignes"] = [r for r in self.etat["lignes"] if r["week"] not in lundis]
        for numero in numeros:
            self.etat["passages"][numero]["supprime"] = True

    def supprimer_semaines_reconstruites(self, lundis):
        """Retire ces semaines si elles sont reconstruites (jamais une semaine vivante), puis le passage reconstruit s'il n'a plus de semaine."""
        cibles = {l for l in lundis if l in self.etat["semaines"]
                  and self.etat["passages"][self.etat["semaines"][l]["passage"]]["source"] == "reconstructed"}
        self.etat["semaines"] = {l: s for l, s in self.etat["semaines"].items() if l not in cibles}
        self.etat["lignes"] = [r for r in self.etat["lignes"] if r["week"] not in cibles]
        utilises = {s["passage"] for s in self.etat["semaines"].values()}
        for numero, passage in enumerate(self.etat["passages"]):
            if passage["source"] == "reconstructed" and numero not in utilises:
                passage["supprime"] = True

    def supprimer_photo_vivante(self, lundi):
        semaine = self.etat["semaines"].get(lundi)
        if semaine and self.etat["passages"][semaine["passage"]]["source"] == "live":
            self._supprimer_passages({semaine["passage"]})

    def ecrire_passage(self, source, instant, semaines):
        numero = len(self.etat["passages"])                              # toujours un nouveau passage (décision 2 du 2026-10-23)
        self.etat["passages"].append({"source": source, "instant": instant})
        total = 0
        for lundi, couverture, lignes in semaines:
            if lundi in self.etat["semaines"]:
                raise RuntimeError("semaine déjà photographiée")            # la règle d'unicité du magasin
            self.etat["semaines"][lundi] = {"passage": numero, "coverage": couverture}
            for ligne in lignes:
                version = ligne["version"]
                if version is not None and version not in self.etat["versions"]:
                    self.etat["versions"][version] = {"no": len(self.etat["versions"]) + 1, "release_date": None, "released": None}
                self.etat["lignes"].append({**{k: v for k, v in ligne.items() if k != "version"}, "week": lundi,
                                            "version_no": None if version is None else self.etat["versions"][version]["no"]})
                total += 1
        return total

    def lire_sorties_stockees(self):
        return list(self.sorties)

    def ecrire_registre(self, attributs):
        """Écrit date et drapeau de chaque nom dans le registre (le crée au besoin) ; ne touche aucun autre nom."""
        for nom, (date_sortie, sortie) in attributs.items():
            version = self.etat["versions"].setdefault(nom, {"no": len(self.etat["versions"]) + 1, "release_date": None, "released": None})
            version["release_date"], version["released"] = date_sortie, sortie

    def compter_versions_sans_date(self):
        return sum(1 for v in self.etat["versions"].values() if v["release_date"] is None)

    def version_masquage(self):
        return self.marqueur

    def nombre_adoptions(self):
        return len(self.etat["adoptions"])

    def ajouter_adoption(self, semaines, jour_, raison):
        self.etat["adoptions"].append({"weeks": semaines, "adopted_on": jour_, "reason": raison})

    def valider(self):
        self._photo = copy.deepcopy(self.etat)

    def fermer(self):
        self.etat = copy.deepcopy(self._photo)

    # --- lecture pour les tests -------------------------------------------------------------------------------------
    def vivantes(self):
        return {l: s for l, s in self.etat["semaines"].items() if self.etat["passages"][s["passage"]]["source"] == "live"}

    def reconstruites(self):
        return {l: s for l, s in self.etat["semaines"].items() if self.etat["passages"][s["passage"]]["source"] == "reconstructed"}

    def lignes_de(self, lundi):
        return [r for r in self.etat["lignes"] if r["week"] == lundi]


class Espace(unittest.TestCase):
    """Fichier de réglages temporaire et lanceur de main()."""

    reglages_texte = REGLAGES

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.racine = Path(self.temp.name)
        self.reglages = self.racine / "flux.yaml"
        self.ecrire_reglages(self.reglages_texte)
        self.environ = {"VERSION_PHOTO_SETTINGS": str(self.reglages), "VERSION_PHOTO_NOW": AUJOURDHUI.isoformat(),
                        "PATH": os.environ.get("PATH", "")}

    def ecrire_reglages(self, texte: str) -> None:
        self.reglages.write_text(texte, encoding="utf-8")

    def lancer(self, *argv, magasin: MagasinMemoire | None = None, maintenant: dt.datetime | None = None, environ: dict | None = None):
        """Rend (code, sortie standard, sortie d'erreur, le magasin, nombre d'ouvertures du magasin)."""
        magasin = magasin if magasin is not None else MagasinMemoire()
        env = dict(environ if environ is not None else self.environ)
        if maintenant is not None:
            env["VERSION_PHOTO_NOW"] = maintenant.isoformat()
        ouvertures = []

        def ouvrir():
            ouvertures.append(1)
            return magasin

        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = vp.main(list(argv), env, ouvrir_magasin=ouvrir)
        return code, sortie.getvalue(), erreur.getvalue(), magasin, len(ouvertures)
