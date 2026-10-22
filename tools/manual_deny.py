"""Classement « qui lance » d'un script par les règles `deny` de .claude/settings.json.

Même sémantique que tests/settings_deny : une règle `Bash(motif)` interdit une commande complète quand le motif
(le joker `*` vaut n'importe quelle suite, tout le reste est littéral) correspond à toute la commande. Le module
ne lit que la liste `permissions.deny` du fichier de réglages et ne l'écrit jamais ; il ne lance aucun script.
"""
from __future__ import annotations

import functools
import json
import re
from pathlib import Path

PREFIXE = "Bash("

# Lanceurs par langage : les formes synthétiques essayées contre les règles.
LANCEURS_PYTHON = ("uv run", "python", "python3")
LANCEURS_SHELL = ("bash", "zsh")

# Façons d'écrire le chemin d'un script (même liste que tests/settings_deny), avec un faux dossier personnel et un faux dossier de lab :
# les règles `deny` s'écrivent avec des jokers sur le dossier, jamais avec un nom de dossier réel (R-77 : aucun chemin du lab en dur).
CHEMINS = ("tools/{s}", "./tools/{s}", "/home/essai/labo/workspace/tools/{s}",
           "~/labo/workspace/tools/{s}", "~/labo/{s}", "$HOME/labo/{s}",
           "/home/essai/labo/{s}", "{s}")

TERMINAL_SEUL = "Terminal seulement"
TERMINAL_OU_CLAUDE = "Terminal ou Claude Code"


@functools.lru_cache(maxsize=None)   # plus de règles que le cache de re : sans lui, chaque appel recompile tout
def motif_en_regex(motif: str) -> re.Pattern:
    """« Bash(motif) » : le joker * vaut n'importe quelle suite (y compris vide), tout le reste est littéral."""
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)


def lire_regles(chemin_reglages: Path) -> list[str]:
    """Motifs des règles `Bash(...)` de permissions.deny, sans le préfixe ni la parenthèse finale, dans l'ordre du fichier."""
    if not chemin_reglages.exists():
        return []
    reglages = json.loads(chemin_reglages.read_text(encoding="utf-8"))
    deny = (reglages.get("permissions") or {}).get("deny") or []
    return [d[len(PREFIXE):-1] if d.endswith(")") else d[len(PREFIXE):]
            for d in deny if isinstance(d, str) and d.startswith(PREFIXE)]


def interdite(regles: list[str], commande: str) -> bool:
    """Vrai quand un motif de `regles` correspond à la commande entière."""
    return any(motif_en_regex(regle).fullmatch(commande) for regle in regles)


def formes_de_lancement(script: str, langage: str, sous_commande: str | None,
                        option: str | None = None) -> list[str]:
    """Commandes synthétiques de lancement : lanceur x chemin, puis sous-commande et option quand fournies."""
    lanceurs = LANCEURS_PYTHON if langage == "python" else LANCEURS_SHELL
    suite = "".join(f" {morceau}" for morceau in (sous_commande, option) if morceau)
    return [f"{lanceur} {chemin.format(s=script)}{suite}" for lanceur in lanceurs for chemin in CHEMINS]


def classer(regles: list[str], script: str, langage: str, sous_commande: str | None = None,
            options=()) -> str:
    """« Terminal seulement », « Terminal seulement avec `<option>` » ou « Terminal ou Claude Code »."""
    if any(interdite(regles, forme) for forme in formes_de_lancement(script, langage, sous_commande)):
        return TERMINAL_SEUL
    for option in options:
        if any(interdite(regles, forme) for forme in formes_de_lancement(script, langage, sous_commande, option)):
            return f"{TERMINAL_SEUL} avec `{option}`"
    return TERMINAL_OU_CLAUDE
