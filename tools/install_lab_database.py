"""
PMZilla Lab : Étape database : démarrage de la base et migrations (design D10, D14, D15).
Module du script d'installation (orchestrateur du même nom sans suffixe) ; ne se lance pas seul.

Le script ne lit jamais le Trousseau et n'en demande aucune valeur. L'entrée absente se reconnaît au CODE DE SORTIE 3 de db_up.sh
(décision du 2026-10-11), pas à sa phrase française : une traduction future du script n'y change rien.
"""
from __future__ import annotations

import shlex
import subprocess

from install_lab_context import (A_BLANC, ECHEC, FAIT, MANUEL, REFUSE, REPORTE, Contexte, Etape, Resultat, runtime_conteneur_repond,
                                 service_trousseau_de_la_base)

ETAPE = "database"
CODE_MOT_DE_PASSE_ABSENT = 3          # code de sortie de db_up.sh quand l'entrée du Trousseau manque
# Seule dépendance au texte d'un script appelé : la phrase que db.py migrate affiche quand il n'y a rien à appliquer.
PHRASE_A_JOUR = "Rien à appliquer."


def base_prete(ctx: Contexte) -> bool:
    """Sonde partagée : le conteneur de la base est sain (docker compose ps), sans mot de passe."""
    termine = ctx.sonde(["docker", "compose", "ps"])
    sortie = termine.stdout.lower()
    return termine.returncode == 0 and "(healthy)" in sortie and "(unhealthy)" not in sortie


def _commande_migration(ctx: Contexte, *options: str) -> list[str]:
    return ["uv", "run", str(ctx.racine / "tools" / "db.py"), "migrate", *options]


def migrations_a_jour(ctx: Contexte) -> bool:
    termine = ctx.sonde(_commande_migration(ctx, "--dry-run"))
    return termine.returncode == 0 and PHRASE_A_JOUR in termine.stdout


def sonde(ctx: Contexte) -> bool:
    if base_prete(ctx) and migrations_a_jour(ctx):
        ctx.etat["base_ok"] = True
        return True
    return False


def _agir_avec_code(ctx: Contexte, description: str, commande: list[str]) -> tuple[Resultat, int | None]:
    """Comme ctx.act (passage à blanc, confirmation, sortie affichée), mais rend aussi le code de sortie de la commande, que
    ctx.act ne rend pas. Code None : pas lancée (passage à blanc, refus) ou commande introuvable."""
    texte = shlex.join(commande)
    if ctx.a_blanc:
        ctx.dire(f"dry run: would run {texte}")
        return Resultat(A_BLANC, texte), None
    if not ctx.confirmer(ETAPE, f"{description} (run {texte})"):
        ctx.dire_etape(ETAPE, "declined")
        return Resultat(REFUSE, texte), None
    try:
        termine = subprocess.run(commande, cwd=ctx.racine, text=True, check=False)
    except FileNotFoundError:
        ctx.dire_etape(ETAPE, f"failed: {texte}")
        return Resultat(ECHEC, texte), None
    if termine.returncode != 0:
        return Resultat(ECHEC, texte), termine.returncode
    return Resultat(FAIT, texte), 0


def _entree_du_trousseau_absente(ctx: Contexte) -> Resultat:
    """Affiche la commande de création (service lu dans tools/db.py, aucune valeur de mot de passe) ; ne la lance jamais."""
    service = service_trousseau_de_la_base(ctx.racine)
    if service:
        commande = "security add-generic-password -s " + shlex.quote(service) + ' -a "$USER" -w'
    else:
        commande = "see the Keychain section of docs/pmzilla/installation.md (service name not found in tools/db.py)"
    ctx.action_manuelle(commande, "create the Keychain entry of the database")
    ctx.etat["base_ok"] = False
    ctx.reportes.append("database-dependent steps deferred")
    return Resultat(MANUEL, commande)


def executer(ctx: Contexte) -> Resultat:
    marche = ctx.etat.get("runtime_ok")
    if marche is None:
        marche = runtime_conteneur_repond(ctx)
    if not marche:
        ctx.etat["base_ok"] = False
        return Resultat(REPORTE, "container runtime not available")

    resultat = Resultat(FAIT)
    if not base_prete(ctx):
        resultat, code = _agir_avec_code(ctx, "start the database", ["bash", str(ctx.racine / "tools" / "db_up.sh")])
        if resultat.etat == ECHEC:
            if code == CODE_MOT_DE_PASSE_ABSENT:
                return _entree_du_trousseau_absente(ctx)
            ctx.dire_etape(ETAPE, f"failed: {resultat.detail}")
            ctx.etat["base_ok"] = False
            return resultat
        if resultat.etat == REFUSE:
            ctx.etat["base_ok"] = False
            return resultat

    if not migrations_a_jour(ctx):
        # jamais « role-password » : ces commandes sont dans la liste manuelle finale
        resultat = ctx.act(ETAPE, "apply the database migrations", _commande_migration(ctx))
        if resultat.etat != FAIT and resultat.etat != A_BLANC:
            ctx.etat["base_ok"] = False
            return resultat
    if ctx.a_blanc:
        return Resultat(A_BLANC, resultat.detail)
    ctx.etat["base_ok"] = True
    return Resultat(FAIT)


ETAPES: list[Etape] = [
    Etape(ETAPE, ("fresh",), ("repo",), sonde, executer),
]
