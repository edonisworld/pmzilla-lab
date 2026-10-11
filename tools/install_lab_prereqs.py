"""
PMZilla Lab : Étape prereqs : outils (Git, uv, Node, installés par Homebrew s'ils manquent), Claude Code, moteur de conteneurs et Ollama (design D4, D14).
Module du script d'installation (orchestrateur du même nom sans suffixe) ; ne se lance pas seul.

Homebrew n'est jamais installé par le script (page officielle donnée). Le moteur de conteneurs et Ollama sont proposés, jamais forcés :
un refus pose ctx.etat["runtime_ok"] ou ctx.etat["ollama_ok"] à False et ajoute les raisons de report que les autres étapes lisent.
"""
from __future__ import annotations

from install_lab_context import (A_BLANC, ECHEC, FAIT, MANUEL, REFUSE, Contexte, Etape, Resultat, modeles_ollama,
                                 runtime_conteneur_repond)

NOM = "prereqs"
OUTILS = ("git", "uv", "node")      # présents s'ils répondent sur le PATH, qu'ils viennent de Homebrew ou non (Git des outils Xcode, Node installé autrement)
PAGE_HOMEBREW = "https://brew.sh"
INSTALLATEUR_CLAUDE = "curl -fsSL https://claude.ai/install.sh | bash"
RAISONS_RUNTIME = ("database step deferred", "library server registered with the file backend", "backup job not installed")
RAISONS_OLLAMA = ("watch job not installed", "indexing deferred")


# --- sondes (lecture seule) ----------------------------------------------------------------------------------------------------
def outils_manquants(ctx: Contexte) -> list[str]:
    """Outils qui ne répondent pas sur le PATH (`<outil> --version`) : seuls ceux-là sont proposés à Homebrew."""
    return [o for o in OUTILS if not ctx.sonde_ok([o, "--version"])]


def claude_present(ctx: Contexte) -> bool:
    return ctx.sonde_ok(["claude", "--version"])


def modeles_presents(ctx: Contexte) -> list[str]:
    """Noms de la première colonne de `ollama list` (la balise :latest est implicite)."""
    termine = ctx.sonde(["ollama", "list"])
    if termine.returncode != 0:
        return []
    noms = []
    for ligne in termine.stdout.splitlines()[1:]:
        mots = ligne.split()
        if mots:
            noms.append(mots[0])
    return noms


def _modele_present(nom: str, presents: list[str]) -> bool:
    return nom in presents or (":" not in nom and f"{nom}:latest" in presents)


def ollama_pret(ctx: Contexte) -> bool:
    """Sonde partagée : Ollama répond et tous les modèles de modeles_ollama() sont présents."""
    modeles = modeles_ollama(ctx.racine)
    if len(modeles) < 2:
        return False
    presents = modeles_presents(ctx)
    return bool(presents) and all(_modele_present(nom, presents) for _, nom, _ in modeles)


def poser_drapeaux(ctx: Contexte) -> None:
    ctx.etat["runtime_ok"] = runtime_conteneur_repond(ctx)
    ctx.etat["ollama_ok"] = ollama_pret(ctx)


def sonde(ctx: Contexte) -> bool:
    poser_drapeaux(ctx)
    return (not outils_manquants(ctx) and claude_present(ctx) and ctx.etat["runtime_ok"] and ctx.etat["ollama_ok"])


# --- exécution -----------------------------------------------------------------------------------------------------------------
def _reporter(ctx: Contexte, raisons: tuple) -> None:
    for raison in raisons:
        if raison not in ctx.reportes:
            ctx.reportes.append(raison)


def _moteur(ctx: Contexte) -> list[Resultat]:
    """Une confirmation par commande ; le premier refus arrête la proposition."""
    if runtime_conteneur_repond(ctx):
        return []
    resultats = []
    commandes = (
        ("install Colima, Docker and Compose through Homebrew", ["brew", "install", "colima", "docker", "docker-compose"]),
        ("start Colima as a Homebrew service", ["brew", "services", "start", "colima"]),
        ("start Colima with the guide's resources", ["colima", "start", "--cpu", "4", "--memory", "6"]),
    )
    for description, commande in commandes:
        r = ctx.act(NOM, description, commande)
        resultats.append(r)
        if r.etat in (REFUSE, ECHEC):
            break
    if any(r.etat == REFUSE for r in resultats):
        ctx.etat["runtime_ok"] = False
        _reporter(ctx, RAISONS_RUNTIME)
    return resultats


def _ollama(ctx: Contexte, modeles: list[tuple[str, str, str]]) -> list[Resultat]:
    resultats = []
    if not ctx.trouver("ollama"):
        r = ctx.act(NOM, "install Ollama through Homebrew", ["brew", "install", "--cask", "ollama"])
        resultats.append(r)
        if r.etat in (REFUSE, ECHEC):
            if r.etat == REFUSE:
                ctx.etat["ollama_ok"] = False
                _reporter(ctx, RAISONS_OLLAMA)
            return resultats
    presents = modeles_presents(ctx)
    for role, nom, taille in modeles:
        if _modele_present(nom, presents):
            continue
        r = ctx.act(NOM, f"pull the {role} model {nom} ({taille})", ["ollama", "pull", nom])
        resultats.append(r)
        if r.etat == ECHEC:
            return resultats
        if r.etat == REFUSE:
            ctx.etat["ollama_ok"] = False
            _reporter(ctx, RAISONS_OLLAMA)
    return resultats


def executer(ctx: Contexte) -> Resultat:
    poser_drapeaux(ctx)
    if not ctx.trouver("brew"):
        ctx.action_manuelle(PAGE_HOMEBREW, "Homebrew is missing; install it from the official page (this script never installs it)")
        return Resultat(MANUEL, f"Homebrew is missing, see {PAGE_HOMEBREW}")
    modeles = modeles_ollama(ctx.racine)
    if len(modeles) < 2:
        message = "cannot read the Ollama model names from the repository configuration (tools/pmzilla_lab_library.py, watch/tri.yaml)"
        ctx.dire_etape(NOM, "failed: " + message)
        return Resultat(ECHEC, message)

    resultats: list[Resultat] = []

    manquantes = outils_manquants(ctx)
    if manquantes:
        resultats.append(ctx.act(NOM, "install the missing tools through Homebrew", ["brew", "install", *manquantes]))
    if not any(r.etat == ECHEC for r in resultats) and not claude_present(ctx):
        resultats.append(ctx.act(NOM, "install Claude Code with the official installer", ["sh", "-c", INSTALLATEUR_CLAUDE]))
    if not any(r.etat == ECHEC for r in resultats):
        resultats.extend(_moteur(ctx))
    if not any(r.etat == ECHEC for r in resultats):
        resultats.extend(_ollama(ctx, modeles))

    echec = next((r for r in resultats if r.etat == ECHEC), None)
    if echec:
        return echec
    if any(r.etat == REFUSE for r in resultats):
        return next(r for r in resultats if r.etat == REFUSE)
    if any(r.etat == A_BLANC for r in resultats):
        return Resultat(A_BLANC)

    # tout a été accepté : relire l'état réel
    poser_drapeaux(ctx)
    if outils_manquants(ctx) or not claude_present(ctx) or not ctx.etat["runtime_ok"] or not ctx.etat["ollama_ok"]:
        message = "a prerequisite is still missing after the actions"
        ctx.dire_etape(NOM, "failed: " + message)
        return Resultat(ECHEC, message)
    return Resultat(FAIT)


ETAPES: list[Etape] = [
    Etape(NOM, ("fresh",), (), sonde, executer),
]
