"""
PMZilla Lab : Étape check : contrôles en lecture seule (design D14).
Module du script d'installation (orchestrateur du même nom sans suffixe) ; ne se lance pas seul.

Sous-ensemble en lecture seule des contrôles du guide d'installation (section 13). Les contrôles longs (lanceur de tests complet,
contrôle de réveil par posture, somme de contrôle de la bibliothèque de graphiques) sont affichés, jamais lancés.
En passage à blanc, aucun contrôle n'est lancé : la machine n'est pas encore installée.
"""
from __future__ import annotations

import plistlib
import re
import shlex

from install_lab_context import A_BLANC, ECHEC, FAIT, Contexte, Etape, Resultat, modeles_ollama

NOM_SERVEUR = "pmzilla-library"

# affichés, jamais lancés (guide d'installation, section 13)
A_LANCER_SOI_MEME = (
    "bash tests/run_all.sh",
    "for a in discovery delivery scaling facilitation; do uv run .claude/skills/pmzilla-$a-bmad/scripts/wake.py . | head -1; done",
    "(cd tools/vendor && shasum -a 256 -c echarts.sha256)",
)


def etiquettes_des_taches(ctx: Contexte) -> list[str]:
    """Étiquettes des tâches launchd, lues dans les gabarits du dépôt (jamais écrites en dur)."""
    etiquettes = []
    for gabarit in sorted((ctx.racine / "tools").glob("com.pmzilla.*.plist")):
        try:
            etiquettes.append(str(plistlib.loads(gabarit.read_bytes())["Label"]))
        except (OSError, KeyError, plistlib.InvalidFileException, ValueError):
            continue
    return etiquettes


def taches_installees(ctx: Contexte) -> list[str]:
    dossier = ctx.maison / "Library" / "LaunchAgents"
    return [e for e in etiquettes_des_taches(ctx) if (dossier / f"{e}.plist").exists()]


def identifiant_utilisateur() -> str:
    import os
    return str(os.getuid())


def controles(ctx: Contexte) -> list[tuple[list[str], object]]:
    """(commande, jugement(sortie_standard_et_erreur) -> message d'échec ou None). Les composants volontairement reportés sont omis."""
    racine = ctx.racine
    liste: list[tuple[list[str], object]] = []
    if ctx.etat.get("ollama_ok") is not False:
        noms = [nom for _, nom, _ in modeles_ollama(racine)]

        def modeles_presents(sortie: str, noms=noms):
            absents = [n for n in noms if n not in sortie]
            return "missing model " + ", ".join(absents) if absents else None
        liste.append((["ollama", "list"], modeles_presents))

    def connecte(sortie: str):
        bas = sortie.lower()
        return None if re.search(r"\bconnected\b", bas) and "failed" not in bas and "not connected" not in bas else "server not connected"
    liste.append((["claude", "mcp", "get", NOM_SERVEUR], connecte))
    liste.append((["sh", str(racine / "tools" / "install_hooks.sh"), "--verify"], None))
    liste.append((["zsh", str(racine / "tools" / "install_links.sh"), "--verify"], None))
    for etiquette in taches_installees(ctx):
        liste.append((["launchctl", "print", f"gui/{identifiant_utilisateur()}/{etiquette}"], None))
    if ctx.etat.get("base_ok") is not False:
        liste.append((["docker", "compose", "ps"], None))
        liste.append((["uv", "run", str(racine / "tools" / "db.py"), "status"], None))
    liste.append((["git", "status", "--short"], None))
    return liste


def afficher_commandes_a_lancer(ctx: Contexte) -> None:
    ctx.dire_etape("check", "not run here, to run yourself:")
    for commande in A_LANCER_SOI_MEME:
        ctx.dire("    " + commande)


def executer_check(ctx: Contexte) -> Resultat:
    liste = controles(ctx)
    if ctx.a_blanc:
        for commande, _ in liste:
            ctx.dire("dry run: would run " + shlex.join(commande))
        afficher_commandes_a_lancer(ctx)
        return Resultat(A_BLANC, "no check run")
    premier = None
    for commande, jugement in liste:
        texte = shlex.join(commande)
        sonde = ctx.sonde(commande)
        sortie = sonde.stdout + sonde.stderr
        raison = f"exit code {sonde.returncode}" if sonde.returncode != 0 else (jugement(sortie) if jugement else None)
        if raison is None:
            ctx.dire_etape("check", f"ok: {texte}")
            continue
        ctx.dire_etape("check", f"failed: {texte} ({raison})")
        premier = premier or texte
    afficher_commandes_a_lancer(ctx)
    return Resultat(ECHEC, premier) if premier else Resultat(FAIT)


ETAPES: list[Etape] = [
    Etape("check", ("fresh",), (), lambda ctx: False, executer_check, apres_tout=True),
]
