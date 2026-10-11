"""
PMZilla Lab : Étapes repo, hooks et links (design D14, D15).
Module du script d'installation (orchestrateur du même nom sans suffixe) ; ne se lance pas seul.

Les scripts du dépôt sont appelés par leur chemin dans le clone (construit à l'exécution depuis la racine), l'interpréteur par son nom.
Leur sortie est montrée telle quelle. Le script d'installation n'est jamais lancé sans --verify quand tout est déjà en place.
"""
from __future__ import annotations

import os

from install_lab_context import A_BLANC, ECHEC, FAIT, Contexte, Etape, Resultat

QUARANTAINE = "com.apple.quarantine"


# --- repo -----------------------------------------------------------------------------------------------------------------------------
def fichiers_a_rendre_executables(ctx: Contexte) -> list[str]:
    """Scripts shell des outils et hooks du clone (chemins construits depuis la racine)."""
    tools = ctx.racine / "tools"
    fichiers = sorted(tools.glob("*.sh")) + sorted(p for p in (tools / "hooks").glob("*") if p.is_file())
    return [str(f) for f in fichiers]


def repo_sonde(ctx: Contexte) -> bool:
    if not (ctx.racine / ".git").exists():
        return False
    for fichier in fichiers_a_rendre_executables(ctx):
        if not os.access(fichier, os.X_OK):
            return False
        if QUARANTAINE in ctx.sonde(["xattr", "-l", fichier]).stdout:
            return False
    return True


def repo_executer(ctx: Contexte) -> Resultat:
    fichiers = fichiers_a_rendre_executables(ctx)
    commande = ["sh", "-c", 'xattr -c "$@" && chmod +x "$@"', "sh", *fichiers]
    resultat = ctx.act("repo", "clear the quarantine attribute and make the tool scripts and hooks executable", commande)
    if resultat.etat != FAIT:
        return resultat
    if not repo_sonde(ctx):
        ctx.dire_etape("repo", "failed: scripts are still not executable or still quarantined")
        return Resultat(ECHEC, resultat.detail)
    ctx.dire_etape("repo", "done")
    return resultat


# --- hooks et links : même schéma ----------------------------------------------------------------------------------------------------
def _commande(ctx: Contexte, interpreteur: str, script: str, *options: str) -> list[str]:
    return [interpreteur, str(ctx.racine / "tools" / script), *options]


def _etape_script(nom: str, interpreteur: str, script: str, apres=None) -> tuple:
    def sonde(ctx: Contexte) -> bool:
        fait = ctx.sonde_ok(_commande(ctx, interpreteur, script, "--verify"))
        if fait and apres:
            apres(ctx)
        return fait

    def executer(ctx: Contexte) -> Resultat:
        resultat = ctx.act(nom, f"run {script}", _commande(ctx, interpreteur, script))
        if resultat.etat != FAIT:
            return resultat
        verification = _commande(ctx, interpreteur, script, "--verify")
        if not ctx.sonde_ok(verification):
            texte = " ".join(verification)
            ctx.dire_etape(nom, f"failed: {texte}")
            return Resultat(ECHEC, texte)
        if apres:
            apres(ctx)
        ctx.dire_etape(nom, "done")
        return resultat

    return sonde, executer


def _liens_ok(ctx: Contexte) -> None:
    ctx.etat["liens_ok"] = True


_sonde_hooks, _executer_hooks = _etape_script("hooks", "sh", "install_hooks.sh")
_sonde_links, _executer_links = _etape_script("links", "zsh", "install_links.sh", _liens_ok)

ETAPES: list[Etape] = [
    Etape("repo", ("fresh",), (), repo_sonde, repo_executer),
    Etape("hooks", ("fresh",), ("repo",), _sonde_hooks, _executer_hooks),
    Etape("links", ("fresh",), ("repo",), _sonde_links, _executer_links),
]
