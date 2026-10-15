"""
Aide commune des tests de tools/flow_retention.py (change jira-gdpr-alignment, groupe 11). Aucun effet réel :

  - un espace de travail temporaire qui remplace tous les emplacements (variables FLOW_RETENTION_*), jamais Flux-Lab/ ;
  - la date du jour est fixée (FLOW_RETENTION_TODAY) ; l'âge d'un fichier se règle par sa date de modification ;
  - la base est une FAUSSE connexion (comptes choisis, journal des requêtes, échec réglable) : aucun PostgreSQL ;
  - l'outil RÉEL est appelé dans le processus (main(argv, environ, ouvrir_base)) sans la variable de session Claude Code.

Les clés, équipes, étiquettes, versions et noms de fichiers portent la marque « zz » : un test qui la retrouve dans une sortie prouve
que l'outil écrit une valeur qu'il ne doit pas écrire. Données inventées.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import flow_retention as fr          # noqa: E402

AUJOURDHUI = dt.date(2026, 10, 13)
ETIQUETTE = "zzetiquette"            # étiquette de sauvegarde du réglage
MARQUES = ("zzcle", "zzequipe", "zzfichier", "zzlabel", "zzversion", "ZZKEY", "ZZEQUIPE")


def jours_avant(n: int) -> dt.date:
    return AUJOURDHUI - dt.timedelta(days=n)


class FausseBase:
    """Connexion factice : `comptes` = (nombre, date de l'horloge la plus ancienne) rendu par la requête de comptage."""

    def __init__(self, compte: int = 0, plus_ancien: dt.date | None = None, echec_suppression: Exception | None = None):
        self.compte, self.plus_ancien, self.echec_suppression = compte, plus_ancien, echec_suppression
        self.requetes: list[tuple[str, tuple]] = []
        self.commits = self.rollbacks = 0
        self.fermee = False
        self.supprime = False
        self.rowcount = 0

    def cursor(self):
        return self

    def execute(self, sql, params=()):
        self.requetes.append((" ".join(sql.split()), tuple(params)))
        if sql.lstrip().upper().startswith("DELETE"):
            if self.echec_suppression is not None:
                raise self.echec_suppression
            self.supprime = True
            self.rowcount = self.compte
        return self

    def fetchone(self):
        return (self.compte, self.plus_ancien)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.fermee = True

    def suppressions(self):
        return [r for r in self.requetes if r[0].upper().startswith("DELETE")]


class Espace(unittest.TestCase):
    """Dossiers temporaires aux emplacements de l'outil et lanceur de main()."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.racine = Path(self.temp.name)
        self.exports = self.racine / "exports"
        self.tableaux = self.racine / "tableaux"
        self.rapports = self.racine / "rapports"
        self.historique = self.racine / "historique" / "transitions.json"
        self.sauvegardes = self.racine / "sauvegardes"
        self.statut = self.racine / "offsite" / "statut"
        self.reglages = self.racine / "flux.yaml"
        for dossier in (self.exports, self.tableaux, self.rapports, self.historique.parent, self.sauvegardes, self.statut.parent):
            dossier.mkdir()
        self.environ = {
            "FLOW_RETENTION_SETTINGS": str(self.reglages), "FLOW_RETENTION_EXPORTS": str(self.exports),
            "FLOW_RETENTION_TABLEAUX": str(self.tableaux), "FLOW_RETENTION_RAPPORTS": str(self.rapports),
            "FLOW_RETENTION_HISTORIQUE": str(self.historique), "FLOW_RETENTION_SAUVEGARDES": str(self.sauvegardes),
            "FLOW_RETENTION_STATUT": str(self.statut), "FLOW_RETENTION_TODAY": AUJOURDHUI.isoformat(),
            "PMZILLA_LAB_WORKSPACE": str(self.racine / "absent"), "PATH": os.environ.get("PATH", "")}
        self.ecrire_reglages(f"retention:\n  backup_label: {ETIQUETTE}\n")

    # --- fabrication -------------------------------------------------------------------------------------------------
    def ecrire_reglages(self, texte: str) -> None:
        self.reglages.write_text(texte, encoding="utf-8")

    def fichier(self, dossier: Path, nom: str, age: int, contenu: str = "Issue key,Status\nZZKEY-1,Done\n") -> Path:
        chemin = dossier / nom
        chemin.write_text(contenu, encoding="utf-8")
        instant = dt.datetime.combine(jours_avant(age), dt.time(12)).timestamp()
        os.utime(chemin, (instant, instant))
        return chemin

    def cache(self, entrees: dict) -> None:
        self.historique.write_text(json.dumps(entrees), encoding="utf-8")

    def sauvegarde(self, jour: dt.date, etiquette: str | None = ETIQUETTE, schemas=("knowledge", "cases", "flow")) -> Path:
        dossier = self.sauvegardes / (f"db-{jour.isoformat()}" + (f"-{etiquette}" if etiquette else ""))
        dossier.mkdir()
        for schema in schemas:
            (dossier / f"{schema}.dump").write_bytes(b"x")
        return dossier

    def etat_hors_site(self, anciennes: int, age: int = 35) -> None:
        self.statut.write_text(f"derniere serie-db derniere_copie=db-2026-10-10\nflux copies_flux_anciennes={anciennes} "
                               f"age_jours={age} date=2026-10-12\n", encoding="utf-8")

    # --- lancement ---------------------------------------------------------------------------------------------------
    def lancer(self, *argv, base: FausseBase | None = None, environ: dict | None = None):
        """Rend (code, sortie standard, sortie d'erreur, la fausse base). La base par défaut est vide."""
        base = base if base is not None else FausseBase()
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = fr.main(list(argv), environ if environ is not None else self.environ, ouvrir_base=lambda: base)
        return code, sortie.getvalue(), erreur.getvalue(), base

    def instantane(self) -> dict[str, bytes]:
        """Contenu de tous les fichiers de l'espace, pour prouver que rien n'a changé."""
        return {str(p.relative_to(self.racine)): p.read_bytes() for p in sorted(self.racine.rglob("*")) if p.is_file()}

    def existe(self, chemin: Path) -> bool:
        return chemin.exists()
