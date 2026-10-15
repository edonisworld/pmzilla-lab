"""
PMZilla Lab : Étapes repo, hooks, runtree et links (design D14, D15 ; change run-worktree).
Module du script d'installation (orchestrateur du même nom sans suffixe) ; ne se lance pas seul.

Les scripts du dépôt sont appelés par leur chemin dans le clone (construit à l'exécution depuis la racine), l'interpréteur par son nom.
Leur sortie est montrée telle quelle. Le script d'installation n'est jamais lancé sans --verify quand tout est déjà en place.
"""
from __future__ import annotations

import os

from install_lab_context import A_BLANC, ECHEC, FAIT, MANUEL, Contexte, Etape, Resultat

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


# --- runtree : le dossier d'exécution (change run-worktree, D3) ------------------------------------------------------------------------
# Codes de `run_worktree.sh status` : 0 propre au sommet de main, 8 en retard sur main. Le script d'installation n'appelle jamais update.
CODE_EN_RETARD = 8
COMMANDE_MISE_A_JOUR = "bash tools/run_worktree.sh update"


def _run_worktree(ctx: Contexte, *options: str) -> list[str]:
    return _commande(ctx, "bash", "run_worktree.sh", *options)


def runtree_sonde(ctx: Contexte) -> bool:
    return ctx.sonde(_run_worktree(ctx, "status")).returncode == 0


def _runtree_en_retard(ctx: Contexte) -> Resultat:
    ctx.action_manuelle(COMMANDE_MISE_A_JOUR, "the run tree is behind main")
    return Resultat(MANUEL, COMMANDE_MISE_A_JOUR)


def runtree_executer(ctx: Contexte) -> Resultat:
    if ctx.sonde(_run_worktree(ctx, "status")).returncode == CODE_EN_RETARD:
        return _runtree_en_retard(ctx)
    resultat = ctx.act("runtree", "create the run tree", _run_worktree(ctx, "create"))
    if resultat.etat != FAIT:
        return resultat
    code = ctx.sonde(_run_worktree(ctx, "status")).returncode
    if code == CODE_EN_RETARD:
        return _runtree_en_retard(ctx)
    if code != 0:
        texte = " ".join(_run_worktree(ctx, "status"))
        ctx.dire_etape("runtree", f"failed: {texte}")
        return Resultat(ECHEC, texte)
    ctx.dire_etape("runtree", "done")
    return resultat


def _liens_ok(ctx: Contexte) -> None:
    ctx.etat["liens_ok"] = True


_sonde_hooks, _executer_hooks = _etape_script("hooks", "sh", "install_hooks.sh")
_sonde_links, _executer_links = _etape_script("links", "zsh", "install_links.sh", _liens_ok)

ETAPES: list[Etape] = [
    Etape("repo", ("fresh",), (), repo_sonde, repo_executer),
    Etape("hooks", ("fresh",), ("repo",), _sonde_hooks, _executer_hooks),
    Etape("runtree", ("fresh",), ("repo", "hooks"), runtree_sonde, runtree_executer),
    Etape("links", ("fresh",), ("repo", "runtree"), _sonde_links, _executer_links),
]
