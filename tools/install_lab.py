# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PMZilla Lab : script d'installation, orchestrateur (change install-script, job R-15). Bibliothèque standard seulement.

    zsh tools/install_lab.sh --mode fresh [--dry-run] [--step NOM | --start-at NOM]     (amorce : Homebrew, Git, uv, clone, puis ici)
    uv run tools/install_lab.py --mode fresh [--dry-run] [--step NOM | --start-at NOM]
    uv run tools/install_lab.py --list

Mode fresh : édition publiée, sans données personnelles. Chaque action qui change la machine demande une confirmation (défaut : non),
chaque étape commence par une sonde « déjà fait » en lecture seule, --dry-run n'exécute que les sondes. Aucune option « tout accepter ».
Aucun secret n'est manipulé : le script n'appelle jamais la commande du Trousseau ; quand une entrée manque, il affiche la commande à lancer.

Codes de sortie : 0 tout fait ou déjà fait ; 1 une étape a échoué ; 2 usage ; 3 environnement refusé ; 4 incomplet (refusé, reporté
ou action manuelle en attente). Messages en anglais, préfixés « install_lab: ».
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import install_lab_check
import install_lab_database
import install_lab_launchd
import install_lab_mcp
import install_lab_prereqs
import install_lab_repo
from install_lab_context import (A_BLANC, DEJA, ECHEC, FAIT, MANUEL, NON_LANCE, PREFIXE, REFUSE, REPORTE, Contexte, Etape, Resultat,
                                 VARIABLE_SANS_TERMINAL, entree_est_un_terminal, racine_du_depot, roles_de_la_base)

MODES = ("fresh",)
PAGE_GUIDE = 'see the "Install script" section of docs/pmzilla/installation.md'

# Tableau des étapes, dans l'ordre. Un mode futur ajoute des lignes (et des modes à des lignes existantes) sans toucher à l'exécuteur.
ETAPES: list[Etape] = [
    *install_lab_prereqs.ETAPES, *install_lab_repo.ETAPES, *install_lab_database.ETAPES,
    *install_lab_launchd.ETAPES, *install_lab_mcp.ETAPES, *install_lab_check.ETAPES,
]

# Ce qui reste manuel (design D5), affiché à la fin de chaque passage, réel ou à blanc.
A_FAIRE_A_LA_MAIN = (
    "install Homebrew (https://brew.sh)",
    "sign in to Claude Code in the browser: run claude once",
    "GitHub authentication, when the clone is private",
    "every Keychain entry (the database password, then one per application role), typed by you at the prompt",
    "the BMAD installer, only for updates",
    "the first session of each posture, in Claude Code (creates its sanctum)",
    "edit the local context (.pmzilla/contexte.md) and the triage themes and language (watch/tri.yaml)",
    "book conversion, sorting and indexing",
    "choose the watch sources and run the first collection",
    "the posture evaluation baseline (paid: the cost is announced first)",
    "the sensitive-names list (Flux-Lab/noms-sensibles.txt, outside Git)",
    "the Jira steps",
)

TEXTE_ETAT = {FAIT: "done", DEJA: "already done", REFUSE: "declined", REPORTE: "deferred", MANUEL: "manual action", ECHEC: "failed",
              NON_LANCE: "not run", A_BLANC: "would act (dry run)"}


def lire_arguments(argv: list[str]) -> argparse.Namespace:
    analyseur = argparse.ArgumentParser(prog="install_lab", allow_abbrev=False, description="Install PMZilla Lab (fresh mode).")
    analyseur.add_argument("--mode", help="fresh (the only mode in this version)")
    analyseur.add_argument("--dry-run", action="store_true", help="run only the read-only probes and print what would be done")
    analyseur.add_argument("--step", help="run one step only")
    analyseur.add_argument("--start-at", help="run this step and the following ones")
    analyseur.add_argument("--list", action="store_true", help="list the steps of the mode in order")
    analyseur.add_argument("--repo", help="clone URL (used by the bootstrap when it has to clone; ignored here)")
    return analyseur.parse_args(argv)


def erreur_d_usage(message: str) -> int:
    print(PREFIXE + message)
    return 2


def etapes_du_mode(mode: str) -> list[Etape]:
    return [e for e in ETAPES if mode in e.modes]


def dependance_satisfaite(ctx: Contexte, nom: str, resultats: dict, etapes: list[Etape]) -> bool:
    if nom in resultats:
        return resultats[nom].etat in (FAIT, DEJA, A_BLANC)
    etape = next((e for e in etapes if e.nom == nom), None)
    return bool(etape and etape.sonde(ctx))


def lancer_etapes(ctx: Contexte, etapes: list[Etape], seule: str | None = None, depuis: str | None = None) -> dict:
    """Exécute les étapes choisies dans l'ordre : sonde « déjà fait », dépendances, exécution. Rend {nom: Resultat}.
    Un échec arrête la suite (les étapes restantes sont « not run »)."""
    noms = [e.nom for e in etapes]
    choisies = [e for e in etapes if e.nom == seule] if seule else (etapes[noms.index(depuis):] if depuis else list(etapes))
    resultats: dict[str, Resultat] = {}
    arret = False
    for etape in choisies:
        if arret:
            resultats[etape.nom] = Resultat(NON_LANCE)
            continue
        if etape.sonde(ctx):
            ctx.dire_etape(etape.nom, "already done, skipped")
            resultats[etape.nom] = Resultat(DEJA)
            continue
        manquantes = [d for d in etape.depend if not dependance_satisfaite(ctx, d, resultats, etapes)]
        if etape.apres_tout and not seule:
            manquantes += [n for n, r in resultats.items() if r.etat not in (FAIT, DEJA, A_BLANC) and n not in manquantes]
        if manquantes:
            raison = "waiting for step " + ", ".join(manquantes)
            ctx.dire_etape(etape.nom, f"deferred ({raison})")
            resultats[etape.nom] = Resultat(REPORTE, raison)
            continue
        resultat = etape.executer(ctx)
        resultats[etape.nom] = resultat
        if resultat.etat == ECHEC:
            arret = True
    return resultats


def code_de_sortie(resultats: dict) -> int:
    etats = [r.etat for r in resultats.values()]
    if ECHEC in etats:
        return 1
    if any(e in (REFUSE, REPORTE, MANUEL, NON_LANCE) for e in etats):
        return 4
    return 0


def afficher_rapport(ctx: Contexte, resultats: dict) -> None:
    ctx.dire("report:")
    for nom, r in resultats.items():
        suite = f" ({r.detail})" if r.detail and r.etat in (REPORTE, ECHEC) else ""
        ctx.dire(f"  {nom}: {TEXTE_ETAT[r.etat]}{suite}")
    for raison in ctx.reportes:
        ctx.dire(f"  deferred: {raison}")
    ctx.dire("remaining manual steps:")
    for ligne in A_FAIRE_A_LA_MAIN:
        ctx.dire(f"  - {ligne}")
    for role in roles_de_la_base(ctx.racine):
        ctx.dire(f"  - Keychain entry of role {role}: uv run tools/db.py role-password {role} (generates the password, stores it in the Keychain and tests it)")
    for commande in ctx.manuel:
        ctx.dire(f"  - {commande}")


def main(argv: list[str] | None = None) -> int:
    args = lire_arguments(sys.argv[1:] if argv is None else argv)

    if args.mode is not None and args.mode not in MODES:
        return erreur_d_usage(f"mode {args.mode} is not available in this version, {PAGE_GUIDE}")
    if args.mode is None and not args.list:
        return erreur_d_usage(f"--mode is required (fresh), {PAGE_GUIDE}")
    mode = args.mode or MODES[0]
    etapes = etapes_du_mode(mode)
    noms = [e.nom for e in etapes]
    if args.step and args.start_at:
        return erreur_d_usage("--step and --start-at cannot be used together")
    for nom in (args.step, args.start_at):
        if nom is not None and nom not in noms:
            return erreur_d_usage(f"unknown step {nom} for mode {mode}; steps: {', '.join(noms)}")

    if args.list:
        for e in etapes:
            print(f"{PREFIXE}{e.nom}" + (f"  (needs: {', '.join(e.depend)})" if e.depend else ""))
        return 0
    if not args.dry_run and not entree_est_un_terminal():
        return erreur_d_usage(f"a real run needs a terminal for its confirmations (use --dry-run to look; {VARIABLE_SANS_TERMINAL} is for tests only)")

    ctx = Contexte(racine=racine_du_depot(__file__), maison=Path.home(), mode=mode, a_blanc=args.dry_run)
    resultats = lancer_etapes(ctx, etapes, seule=args.step, depuis=args.start_at)
    afficher_rapport(ctx, resultats)
    code = code_de_sortie(resultats)
    if args.dry_run:
        ctx.dire("dry run: nothing was changed")
        return 0 if code != 1 else 1       # un passage à blanc ne « refuse » ni ne « reporte » rien : il décrit (design D16)
    else:
        ctx.dire("installation complete" if code == 0 else "installation incomplete" if code == 4 else "installation failed")
    return code


if __name__ == "__main__":
    sys.exit(main())
