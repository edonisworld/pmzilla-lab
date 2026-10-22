"""PMZilla Lab : sous-commande `review` de tools/story_quality.py (change story-quality-audit, design D5 « Per-team review gate »,
section « Residual risk », D14).

    uv run tools/story_quality.py review --team <équipe> --sample <n> [--language fr|en]

Lancée par l'utilisateur seul, dans le Terminal : le répartiteur la refuse dans une session Claude Code (code 3) avant toute lecture.
Elle tire au hasard au plus <n> éléments de l'équipe encore dans la collecte et écrit leurs textes NETTOYÉS dans le Terminal, sans les
clés. L'utilisateur les lit, puis tape le mot de confirmation (« oui », ou « yes » en anglais) seulement si aucun nom ne reste : la
relecture de l'équipe est alors enregistrée (équipe, instant, taille de l'échantillon ; ni texte, ni clé, ni personne). Toute autre
réponse n'enregistre rien et rappelle de compléter la liste des noms sensibles puis de recollecter. Aucun fichier n'est écrit.

Elle charge et valide flux.yaml (flux_config) : `story_quality.review_sample_size` est la taille MINIMALE de --sample (une valeur plus petite
est refusée avec le code 3) ; sans bloc ni réglage, aucun minimum. Une équipe qui a moins d'éléments que la taille demandée est relue
en entier, et la relecture enregistrée le dit.

Codes : 0 fait (enregistrée, non enregistrée, ou équipe sans élément collecté) ; 1 base injoignable ou erreur de la base ; 2 usage (taille
d'échantillon qui n'est pas un entier positif) ; 3 pas de terminal (entrée ou sortie redirigée), refusé avant toute lecture. Les textes
affichés n'ont ni séquence ANSI ou OSC ni caractère de contrôle (saut de ligne et tabulation exceptés).
"""
from __future__ import annotations

import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flux_config  # noqa: E402
import history_jira as hj  # noqa: E402
import story_quality_store as store  # noqa: E402
from yaml_strict import ErreurConfig  # noqa: E402

demander = input                 # remplacé par les tests ; la réponse n'est jamais écrite ailleurs que dans la comparaison
nouvel_alea = random.Random      # remplacé par les tests (graine fixe)


SEQUENCE_OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?")
SEQUENCE_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SEQUENCE_AUTRE = re.compile(r"\x1b[@-Z\\-_]?")
CONTROLES = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")      # tout sauf la tabulation et le saut de ligne


def est_terminal() -> bool:
    """Vrai si l'entrée et la sortie standard sont des terminaux (remplacé par les tests)."""
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def propre(texte) -> str:
    """Texte sans séquence ANSI ni OSC ni caractère de contrôle (sauf saut de ligne et tabulation) : un texte de Jira ne pilote pas le terminal."""
    texte = SEQUENCE_OSC.sub("", str(texte or ""))
    texte = SEQUENCE_CSI.sub("", texte)
    texte = SEQUENCE_AUTRE.sub("", texte)
    return CONTROLES.sub("", texte)


def taille_valide(texte) -> int | None:
    """Entier positif écrit en chiffres, ou None."""
    texte = str(texte or "").strip()
    return int(texte) if texte.isdigit() and int(texte) > 0 else None


def lancer(args, environ, t) -> int:
    taille = taille_valide(args.sample)
    if taille is None or not str(args.team or "").strip():
        print(t("usage", what="--sample" if taille is None else "--team"), file=sys.stderr)
        return 2
    equipe = args.team.strip()
    if not est_terminal():                   # D14 : dans le Terminal seulement ; avant toute lecture de la base
        print(t("no_terminal"), file=sys.stderr)
        return 3
    try:
        reglages = flux_config.story_quality(hj.reglages())
    except flux_config.ErreurPlafond:
        print(t("cap_invalid"), file=sys.stderr)
        return 3
    except ErreurConfig as erreur:
        print(t("settings_unreadable", detail=str(erreur)), file=sys.stderr)
        return 1
    minimum = (reglages or {}).get("review_sample_size")       # sans bloc ni réglage : aucun minimum
    if minimum is not None and taille < minimum:
        print(t("sample_below_minimum", n=minimum), file=sys.stderr)
        return 3
    try:
        magasin = store.ouvrir()
    except store.ErreurMagasin:
        print(t("db_unreachable"), file=sys.stderr)
        return 1
    try:
        try:
            textes = magasin.echantillon(equipe, taille, nouvel_alea())
        except Exception as erreur:
            print(t("db_error", kind=type(erreur).__name__), file=sys.stderr)
            return 1
        if not textes:
            print(t("no_item_for_team"))
            return 0
        for i, (titre, description, criteres) in enumerate(textes, start=1):
            print(t("review_item", i=i, n=len(textes)))
            print(t("review_title", text=propre(titre)))
            print(t("review_description"))
            print(propre(description))
            print(t("review_criteria"))
            print(propre(criteres))
        print()
        try:
            reponse = demander(t("review_prompt") + " ")
        except EOFError:
            reponse = ""
        if str(reponse).strip().casefold() != t("confirm_word").casefold():
            print(t("review_not_recorded"))
            return 0
        try:
            magasin.enregistrer_relecture(equipe, len(textes))
        except Exception as erreur:
            print(t("db_error", kind=type(erreur).__name__), file=sys.stderr)
            return 1
        print(t("review_recorded"))
        if len(textes) < taille:              # l'équipe a moins d'éléments que la taille demandée : tous relus, et la relecture le dit
            print(t("review_complete", n=len(textes)))
        return 0
    finally:
        magasin.fermer()
