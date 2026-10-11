"""
PMZilla Lab : Étape mcp : enregistrement du serveur de la bibliothèque (design D14, D15).
Module du script d'installation (orchestrateur du même nom sans suffixe) ; ne se lance pas seul.

Le serveur est enregistré pour l'utilisateur, lancé par le lien du dossier du laboratoire (<maison>/PMZilla-Lab/pmzilla_lab_library.py)
avec `uv` trouvé par le PATH. Quand la base n'est pas prête (conteneur absent ou report), il est enregistré avec le secours fichier
(`serve --backend sqlite`, guide d'installation 14.3).
"""
from __future__ import annotations

from pathlib import Path

from install_lab_context import A_BLANC, ECHEC, FAIT, REFUSE, Contexte, Etape, Resultat

NOM_SERVEUR = "pmzilla-library"


def lien_du_serveur(ctx: Contexte) -> Path:
    return ctx.maison / "PMZilla-Lab" / "pmzilla_lab_library.py"


def enregistrement_actuel(ctx: Contexte) -> str | None:
    """Sortie de `claude mcp get` si le serveur est enregistré, sinon None (lecture seule)."""
    sonde = ctx.sonde(["claude", "mcp", "get", NOM_SERVEUR])
    return sonde.stdout + sonde.stderr if sonde.returncode == 0 else None


def deja_enregistre(ctx: Contexte) -> bool:
    """Sonde : le serveur est enregistré et la sortie nomme le lien du dossier du laboratoire."""
    sortie = enregistrement_actuel(ctx)
    return sortie is not None and str(lien_du_serveur(ctx)) in sortie


def base_est_prete(ctx: Contexte) -> bool:
    if "base_ok" in ctx.etat:
        return bool(ctx.etat["base_ok"])
    from install_lab_database import base_prete
    return bool(base_prete(ctx))


def executer_mcp(ctx: Contexte) -> Resultat:
    uv = ctx.trouver("uv")
    if uv is None and not ctx.a_blanc:
        ctx.dire_etape("mcp", "failed: uv not found on the search path (needed to launch the library server)")
        return Resultat(ECHEC, "uv not found")
    lancement = ["uv", "run", str(lien_du_serveur(ctx)), "serve"]      # uv résolu par le PATH à l'exécution
    if not base_est_prete(ctx):
        lancement += ["--backend", "sqlite"]
        ctx.dire_etape("mcp", "database not ready, the server will use the file backend")
    ajout = ["claude", "mcp", "add", "--scope", "user", "--transport", "stdio", NOM_SERVEUR, "--", *lancement]

    if enregistrement_actuel(ctx) is not None:                          # enregistré autrement : remplacement confirmé
        ctx.dire_etape("mcp", "the library server is registered differently")
        retrait = ctx.act("mcp", "remove the existing registration of the library server",
                          ["claude", "mcp", "remove", NOM_SERVEUR, "--scope", "user"])
        if retrait.etat not in (FAIT, A_BLANC):
            return retrait
    resultat = ctx.act("mcp", "register the library server for the user", ajout)
    return resultat if resultat.etat != FAIT else Resultat(FAIT, resultat.detail)


ETAPES: list[Etape] = [
    Etape("mcp", ("fresh",), ("links",), deja_enregistre, executer_mcp),
]
