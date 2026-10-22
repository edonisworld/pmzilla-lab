"""PMZilla Lab : sous-commande `analyse` de tools/story_quality.py (change story-quality-audit, design D5, D7, D14, D17).

    uv run tools/story_quality.py analyse [--sample <n> [--team <équipe>]] [--dry-run] [--language fr|en]

Audit : les éléments dont le texte, la version du socle ou la version de la surcouche a changé depuis leur dernier audit (un élément est
à jour quand l'empreinte de son texte actuel est celle de son dernier verdict d'audit à la paire courante ; une mise à jour Jira sans
changement de texte ne le renvoie pas), par clé croissante, dans la limite du plafond. Un code de verdict par critère effectif est écrit
dans `quality.assessments`, avec l'empreinte du texte envoyé (lue avec ce texte) ; aucun texte du moteur n'est gardé.

Échantillon (`--sample <n>`, avec `--team` facultatif) : tirage au hasard de <n> éléments collectés, audités ou non, de l'équipe ou de
toutes ; <n> est un entier positif au plus égal au plafond. Les verdicts portent la marque d'échantillon, remplacent les précédents
verdicts d'échantillon de l'élément et ne sont comptés par aucune vue ni aucun rapport. La sortie, dans le Terminal seulement, donne une
ligne par code de critère avec les quatre effectifs ; aucune clé, équipe ni texte.

Tous les garde-fous de Q4 (relecture d'équipe, plafond, estimation et confirmation, essai) s'appliquent à l'audit comme à l'échantillon.
Codes : 0 fait, non confirmé, essai ou rien à faire ; 1 base ou moteur en erreur ; 2 usage (--team sans --sample, taille d'échantillon) ;
3 prérequis refusé (voir tools/story_quality_engine.py).
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_quality_engine as engine  # noqa: E402


def a_auditer(elements: list[dict], audits: dict) -> list[dict]:
    """Éléments jamais audités à la paire courante, ou dont l'empreinte du texte diffère de celle du dernier audit (empreinte absente du
    verdict : à réauditer). `audits` : {clé: empreinte du dernier audit}."""
    return [e for e in elements if audits.get(e["key"]) is None or audits[e["key"]] != e["content_hash"]]


def lancer(args, environ, t) -> int:
    echantillon = args.sample is not None
    if args.team is not None and not echantillon:
        print(t("usage", what="--team"), file=sys.stderr)
        return 2
    taille = engine.taille_echantillon(args.sample) if echantillon else None
    if echantillon and taille is None:
        print(t("sample_size_invalid"), file=sys.stderr)
        return 2
    try:
        return executer(args, environ, t, taille)
    except engine.Arret as arret:
        return arret.afficher(t)


def executer(args, environ, t, taille) -> int:
    essai = bool(args.dry_run)
    contexte = engine.preparer(environ, reel=not essai, taille=taille)
    magasin = engine.ouvrir_magasin()
    try:
        engine.verifier_surcouche(contexte, magasin)
        for cle in contexte.infos:
            print(t(cle))
        elements = engine.base(magasin.elements)
        if taille is None:
            candidats = a_auditer(elements, engine.base(magasin.derniers_audits, contexte.paire))
        else:
            equipe = (args.team or "").strip()
            pool = [e for e in elements if not equipe or equipe in e["teams"]]
            if not pool and equipe:
                print(t("no_item_for_team"))
                return 0
            tirees = set(engine.nouvel_alea().sample([e["key"] for e in pool], min(taille, len(pool))))
            candidats = [e for e in pool if e["key"] in tirees]
        lot = engine.appliquer_garde_fous(contexte, magasin, candidats, not essai, t)
        if not lot and not essai:
            print(t("sample_done" if taille else "analysis_done", n=0, u=0))
            return 0
        textes = engine.base(magasin.textes, [e["key"] for e in lot]) if lot else {}
        lot = [e for e in lot if e["key"] in textes]      # texte disparu entre la sélection et la lecture : rien n'est envoyé
        if not engine.annoncer_et_confirmer(contexte, lot, textes, False, essai, t):
            return 0
        engine.enregistrer_surcouche(contexte, magasin)
        refus = indetermines = 0
        comptes: dict[str, Counter] = {}
        for e in lot:
            texte = textes[e["key"]]
            try:
                resultat, refusee = engine.analyser(contexte, e["kind"], texte, False)
            except engine.ErreurMoteur as erreur:
                print(t("engine_error", kind=str(erreur)), file=sys.stderr)
                return 1
            refus += int(refusee)
            criteres = engine.criteres_du_genre(contexte, e["kind"])
            verdicts = [(c["code"], c["origin"], c["link"], resultat[c["code"]][0]) for c in criteres]
            engine.base(magasin.enregistrer_audit, e["key"], contexte.paire, verdicts, taille is not None, texte[3])
            for code, _, _, verdict in verdicts:
                comptes.setdefault(code, Counter())[verdict] += 1
                indetermines += int(verdict == "undetermined")
        if refus:
            print(t("engine_refused", n=refus))
        if taille is None:
            print(t("analysis_done", n=len(lot), u=indetermines))
            return 0
        print(t("sample_done", n=len(lot), u=indetermines))
        genres = {e["kind"] for e in lot}
        for genre in ("story", "epic"):
            if genre in genres:
                for c in engine.criteres_du_genre(contexte, genre):
                    n = comptes.get(c["code"], Counter())
                    print(t("sample_line", code=c["code"], m=n["met"], x=n["not_met"], a=n["not_applicable"], u=n["undetermined"]))
        return 0
    finally:
        magasin.fermer()
