"""
PMZilla Lab : Étape launchd : tâches de la veille et de la sauvegarde de la base (design D4, D14).
Module du script d'installation (orchestrateur du même nom sans suffixe) ; ne se lance pas seul.

Chaque tâche : rendu du gabarit (le marqueur du dossier personnel est remplacé), fichier sous Library/LaunchAgents, `xattr -c`,
`launchctl bootstrap`. Une tâche dont les prérequis manquent (Ollama et ses modèles pour la veille, la base pour la sauvegarde)
n'est pas installée : elle est reportée. Ce module ne lance jamais `kickstart`.
"""
from __future__ import annotations

import os
import plistlib
from dataclasses import dataclass
from pathlib import Path

from install_lab_context import A_BLANC, ECHEC, FAIT, REFUSE, REPORTE, Contexte, Etape, Resultat

NOM = "launchd"
MARQUEUR = "__HOME__"


@dataclass
class Tache:
    gabarit: str          # nom du fichier modèle dans tools/
    drapeau: str          # clé de ctx.etat qui dit si le prérequis est prêt
    report: str           # ligne de ctx.reportes quand le prérequis manque
    prerequis: str        # texte affiché quand la tâche est reportée


TACHES = (
    Tache("com.pmzilla.watch.plist", "ollama_ok", "watch job not installed", "Ollama and its models are not ready"),
    Tache("com.pmzilla.db-backup.plist", "base_ok", "backup job not installed", "the database is not ready"),
)


def _rendu(ctx: Contexte, tache: Tache) -> str | None:
    try:
        modele = (ctx.racine / "tools" / tache.gabarit).read_text(encoding="utf-8")
    except OSError:
        return None
    return modele.replace(MARQUEUR, str(ctx.maison))


def _etiquette(rendu: str) -> str:
    return plistlib.loads(rendu.encode("utf-8"))["Label"]


def _chemin(ctx: Contexte, etiquette: str) -> Path:
    return ctx.maison / "Library" / "LaunchAgents" / f"{etiquette}.plist"


def _domaine() -> str:
    return f"gui/{os.getuid()}"


def _chargee(ctx: Contexte, etiquette: str) -> bool:
    return ctx.sonde_ok(["launchctl", "print", f"{_domaine()}/{etiquette}"])


def _identique(ctx: Contexte, chemin: Path, rendu: str) -> bool:
    try:
        return chemin.read_text(encoding="utf-8") == rendu
    except OSError:
        return False


def _tache_en_place(ctx: Contexte, tache: Tache) -> bool:
    rendu = _rendu(ctx, tache)
    if rendu is None:
        return False
    etiquette = _etiquette(rendu)
    return _identique(ctx, _chemin(ctx, etiquette), rendu) and _chargee(ctx, etiquette)


def _prerequis_pret(ctx: Contexte, tache: Tache) -> bool:
    if tache.drapeau in ctx.etat:
        return bool(ctx.etat[tache.drapeau])
    if tache.drapeau == "ollama_ok":
        import install_lab_prereqs
        return bool(install_lab_prereqs.ollama_pret(ctx))
    import install_lab_database
    return bool(install_lab_database.base_prete(ctx))


def _installer(ctx: Contexte, tache: Tache) -> Resultat:
    """Installe ou remplace une tâche prête à l'être. Rend FAIT, REFUSE, ECHEC ou A_BLANC."""
    rendu = _rendu(ctx, tache)
    if rendu is None:
        ctx.dire_etape(NOM, f"failed: template {tache.gabarit} not found")
        return Resultat(ECHEC, f"read tools/{tache.gabarit}")
    etiquette = _etiquette(rendu)
    chemin = _chemin(ctx, etiquette)
    cible = f"{_domaine()}/{etiquette}"
    resultats = []

    installe = chemin.exists()
    differe = installe and not _identique(ctx, chemin, rendu)
    if differe and _chargee(ctx, etiquette):
        resultats.append(ctx.act(NOM, f"unload job {etiquette} before replacing its file", ["launchctl", "bootout", cible]))
        if resultats[-1].etat in (REFUSE, ECHEC):
            return resultats[-1]
    if not installe or differe:
        verbe = "replace" if differe else "install"
        resultats.append(ctx.ecrire(NOM, f"{verbe} job file for {etiquette}", chemin, rendu))
        if resultats[-1].etat == REFUSE:
            return resultats[-1]
    resultats.append(ctx.act(NOM, f"clear extended attributes of {etiquette}", ["xattr", "-c", str(chemin)]))
    if resultats[-1].etat in (REFUSE, ECHEC):
        return resultats[-1]
    chargement = ctx.act(NOM, f"load job {etiquette}", ["launchctl", "bootstrap", _domaine(), str(chemin)], echec_tolere=True)
    if chargement.etat == ECHEC:
        # erreur inoffensive (« Bootstrap failed: 5 ») : si l'état de la tâche répond ensuite, elle est chargée
        if _chargee(ctx, etiquette):
            return Resultat(FAIT, chargement.detail)
        ctx.dire_etape(NOM, f"failed: {chargement.detail}")
        return chargement
    if chargement.etat == REFUSE:
        return chargement
    return Resultat(A_BLANC if ctx.a_blanc else FAIT, chargement.detail)


def sonde(ctx: Contexte) -> bool:
    return all(_tache_en_place(ctx, t) for t in TACHES)


def executer(ctx: Contexte) -> Resultat:
    refus = None
    reporte = False
    blanc = False
    for tache in TACHES:
        if _tache_en_place(ctx, tache):
            ctx.dire_etape(NOM, f"job {tache.gabarit} already done, skipped")
            continue
        if not _prerequis_pret(ctx, tache):
            ctx.dire_etape(NOM, f"deferred: {tache.prerequis}")
            if tache.report not in ctx.reportes:
                ctx.reportes.append(tache.report)
            reporte = True
            continue
        resultat = _installer(ctx, tache)
        if resultat.etat == ECHEC:
            return resultat
        if resultat.etat == REFUSE:
            refus = refus or resultat
        elif resultat.etat == A_BLANC:
            blanc = True
    if refus:
        return refus
    if ctx.a_blanc and (blanc or reporte):
        return Resultat(A_BLANC)
    if reporte:
        return Resultat(REPORTE, "; ".join(t.report for t in TACHES if t.report in ctx.reportes))
    return Resultat(FAIT)


ETAPES: list[Etape] = [Etape(NOM, ("fresh",), ("links",), sonde, executer)]
