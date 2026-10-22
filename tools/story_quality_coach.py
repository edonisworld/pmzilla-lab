"""PMZilla Lab : sous-commande `coach` de tools/story_quality.py (change story-quality-audit, design D5, D7, D14).

    uv run tools/story_quality.py coach (--team <équipe> | --keys <clé>...) [--show | --dry-run] [--language fr|en]

Le moteur tourne en mode coaching sur les éléments choisis par l'équipe ou par les clés que l'utilisateur tape (jamais par un champ de
personne : il n'y en a aucun). Il écrit les verdicts et le retour borné dans `quality.coaching_feedback`, table que ni vue, ni rapport, ni
tableau de bord, ni synthèse mensuelle ne lit, et affiche le retour par élément dans le Terminal seulement, sous l'en-tête de D14. Aucun
fichier n'est écrit. `--show` réaffiche le retour enregistré sans appeler le moteur (ni clé, ni confirmation) ; `--dry-run` compte et
estime sans rien envoyer ni écrire. Les garde-fous de Q4 (relecture d'équipe, plafond, estimation, confirmation) s'appliquent à tout lot
envoyé. Une exécution de coaching ne change aucun effectif des vues : elle n'écrit pas dans `quality.assessments`.
Codes : 0 fait, non confirmé, essai ou rien à faire ; 1 base ou moteur en erreur ; 3 prérequis refusé (voir tools/story_quality_engine.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_quality_engine as engine  # noqa: E402
import story_quality_review as review  # noqa: E402


def selectionner(args, elements: list[dict]) -> tuple[list[dict] | None, int]:
    """(éléments choisis par clé croissante, nombre de clés inconnues). None à la place des éléments : équipe sans élément collecté."""
    if args.team is not None:
        equipe = args.team.strip()
        choisis = [e for e in elements if equipe in e["teams"]]
        return (choisis or None), 0
    voulues = {k.strip() for k in args.keys if k.strip()}
    par_cle = {e["key"]: e for e in elements}
    connus = [par_cle[k] for k in sorted(voulues) if k in par_cle]
    return connus, len(voulues) - len(connus)


def afficher_retour(cle: str, lignes, t) -> None:
    print(t("coach_item", item=review.propre(cle)))
    for code, verdict, retour in lignes:
        print(t("coach_line", code=code, verdict=verdict, feedback=review.propre(retour)))


def lancer(args, environ, t) -> int:
    try:
        return montrer(args, t) if args.show else executer(args, environ, t)
    except engine.Arret as arret:
        return arret.afficher(t)


def montrer(args, t) -> int:
    """`--show` : le retour enregistré, sans moteur, sans clé, sans confirmation."""
    magasin = engine.ouvrir_magasin()
    try:
        choisis, inconnus = selectionner(args, engine.base(magasin.elements))
        print(t("coaching_header"))
        if choisis is None:
            print(t("no_item_for_team"))
            return 0
        if inconnus:
            print(t("unknown_items", n=inconnus))
        retours = engine.base(magasin.lire_coaching, [e["key"] for e in choisis]) if choisis else {}
        if not retours:
            print(t("coach_nothing_stored"))
        for e in choisis:
            if e["key"] in retours:
                afficher_retour(e["key"], retours[e["key"]], t)
        return 0
    finally:
        magasin.fermer()


def executer(args, environ, t) -> int:
    essai = bool(args.dry_run)
    contexte = engine.preparer(environ, reel=not essai)
    magasin = engine.ouvrir_magasin()
    try:
        engine.verifier_surcouche(contexte, magasin)
        if not essai:
            print(t("coaching_header"))
        for cle in contexte.infos:
            print(t(cle))
        choisis, inconnus = selectionner(args, engine.base(magasin.elements))
        if choisis is None:
            print(t("no_item_for_team"))
            return 0
        if inconnus:
            print(t("unknown_items", n=inconnus))
        lot = engine.appliquer_garde_fous(contexte, magasin, choisis, not essai, t)
        if not lot and not essai:
            return 0
        textes = engine.base(magasin.textes, [e["key"] for e in lot]) if lot else {}
        lot = [e for e in lot if e["key"] in textes]      # texte disparu entre la sélection et la lecture : rien n'est envoyé
        if not engine.annoncer_et_confirmer(contexte, lot, textes, True, essai, t):
            return 0
        engine.enregistrer_surcouche(contexte, magasin)
        refus = 0
        for e in lot:
            try:
                resultat, refusee = engine.analyser(contexte, e["kind"], textes[e["key"]], True)
            except engine.ErreurMoteur as erreur:
                print(t("engine_error", kind=str(erreur)), file=sys.stderr)
                return 1
            refus += int(refusee)
            lignes = [(c["code"], *resultat[c["code"]]) for c in engine.criteres_du_genre(contexte, e["kind"])]
            engine.base(magasin.enregistrer_coaching, e["key"], contexte.paire, lignes)
            afficher_retour(e["key"], lignes, t)
        if refus:
            print(t("engine_refused", n=refus))
        return 0
    finally:
        magasin.fermer()
