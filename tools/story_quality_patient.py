"""PMZilla Lab : sous-commandes `patient-scan` et `patient-lift` de tools/story_quality.py (change patient-data-detection, design D3 à D6, D9, D10).

    uv run tools/story_quality.py patient-scan [--json] [--language fr|en]
    uv run tools/story_quality.py patient-lift [--accept <code>]... [--language fr|en]

`patient-scan` lit les textes nettoyés de tous les éléments stockés (sortis de la collecte compris), lance le détecteur local
tools/patient_data.py et n'écrit que des effectifs agrégés : par catégorie et genre d'élément, par catégorie et champ, éléments que le
contrôle avant envoi retiendrait par genre, et P5 à part (marqué « bruit attendu »). Jamais un texte, un extrait, une clé, une équipe, une
personne, une valeur de champ ni une étiquette de la liste facultative `patient_id_labels`. Aucune ligne de total. Rien n'est envoyé : aucun
accès réseau. Chaque passage est enregistré dans le schéma `quality` (instant, version du détecteur, empreinte de la liste, éléments lus par
genre, un drapeau trouvé par catégorie) ; une erreur de la base n'enregistre rien et se termine par le code 1, le type de l'erreur seul affiché.

Écart assumé avec les vues de flux (design D4) : dans les vues, toute cellule de moins de 5 est masquée, zéro compris. Ici une cellule de 0
s'affiche 0, une cellule de 1 à 4 est masquée (« masqué » / « masked », cellule JSON `value: null, masked: true, reason: "under_threshold"`)
et une cellule de 5 ou plus s'affiche. Raison : un zéro ne décrit aucun élément, et c'est la réponse que cette mesure sert à obtenir. L'écart
est limité à cet outil ; le seuil est celui des vues de flux (tools/flow_views.py : plancher 5, relevé par `flow_views_min_cell`), lu à la même
source, jamais une seconde valeur. Le total de la ligne d'en-tête est masqué dès qu'un genre l'est, pour qu'une cellule masquée ne se retrouve
pas par différence.

`patient-lift` ne se lance que dans un terminal. Elle affiche les drapeaux du dernier passage (« trouvée » / « aucune » par catégorie) et
n'enregistre la levée de la suspension de l'analyse que si le dernier passage est à la version actuelle du détecteur et de la liste, si chaque
catégorie trouvée est nommée par `--accept` (acceptation écrite de l'auteur après vérification dans Jira, inscrite à son registre) et si
l'auteur tape le mot de confirmation. Une catégorie acceptée n'ouvre pas le contrôle avant envoi (voir tools/story_quality_engine.py).

Fonction de service : `patient_scan_result(magasin, settings, threshold)` porte toutes les décisions de D3, D4 et D10 (lecture, comptes, masquage,
enregistrement du passage) et rend le document du contrat `patient_data_scan` ; le Terminal et `--json` ne font que le mettre en forme. Avec
`--json`, la sortie standard ne porte que ce document, et les phrases d'accompagnement vont sur la sortie d'erreur.

Codes de `patient-scan` : 0 fait (quoi qu'on ait trouvé) ; 1 base ou réglages illisibles, aucun passage enregistré ; 2 usage ; 3 refusé dans une
session Claude Code (par le répartiteur, avant toute lecture). Codes de `patient-lift` : 0 enregistrée ou non enregistrée (réponse autre que le
mot de confirmation) ; 1 base ou réglages illisibles ; 2 usage, ou un code inconnu donné à `--accept` ; 3 session, pas de terminal, ou levée refusée.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flux_config  # noqa: E402
import history_jira as hj  # noqa: E402
import patient_data  # noqa: E402
import story_quality_review as review  # noqa: E402
import story_quality_store as store  # noqa: E402
from yaml_strict import ErreurConfig  # noqa: E402

CONTRACT = "patient_data_scan"
CONTRACT_VERSION = 1
KINDS = ("story", "epic", "defect")
FIELDS = ("title", "description", "acceptance_criteria")
UNDER_THRESHOLD = "under_threshold"


# ---------------------------------------------------------------------------------------------------------------------------------
# Cellules masquées et état de la suspension
# ---------------------------------------------------------------------------------------------------------------------------------

def cell(value: int, threshold: int) -> dict:
    """0 s'affiche, 1 jusqu'au seuil exclu est masqué, le seuil et au-delà s'affichent (D4)."""
    if 0 < value < threshold:
        return {"value": None, "masked": True, "reason": UNDER_THRESHOLD}
    return {"value": value, "masked": False, "reason": None}


def lift_is_current(lift: dict | None, labels) -> bool:
    """Vrai quand une levée est enregistrée à la version actuelle du détecteur et de la liste, et qu'aucun passage enregistré depuis n'a trouvé
    une catégorie qu'elle n'a pas acceptée (D6). Source unique de la porte de `analyse` et `coach` et de l'état du scan."""
    if lift is None:
        return False
    if lift["detector_version"] != patient_data.DETECTOR_VERSION or lift["labels_fingerprint"] != patient_data.labels_fingerprint(labels):
        return False
    return not (set(lift["found_after"]) - set(lift["accepted"]))


def _instant(valeur) -> str | None:
    return None if valeur is None else (valeur.isoformat() if hasattr(valeur, "isoformat") else str(valeur))


def suspension_state(lift: dict | None, labels) -> dict:
    if lift_is_current(lift, labels):
        return {"state": "lifted", "lifted_at": _instant(lift["lifted_at"]), "lift_detector_version": lift["detector_version"],
                "accepted_categories": list(lift["accepted"])}
    return {"state": "suspended", "lifted_at": None, "lift_detector_version": None, "accepted_categories": []}


# ---------------------------------------------------------------------------------------------------------------------------------
# Fonction de service
# ---------------------------------------------------------------------------------------------------------------------------------

def masking_threshold(settings: dict) -> int:
    """Seuil de masquage des vues de flux : plancher 5, relevé par `flow_views_min_cell`, lus à la source des vues (tools/flow_views.py)."""
    import flow_views
    try:
        configured = int(settings.get("flow_views_min_cell", flow_views.PLANCHER))
    except (TypeError, ValueError):
        configured = flow_views.PLANCHER
    return flow_views.seuil_effectif(configured, None)


def patient_scan_result(magasin, settings: dict, threshold: int) -> dict:
    """Lit les textes, compte, masque, enregistre le passage (sans compte) et rend le document du contrat `patient_data_scan`. Lève toute
    erreur de la base, auquel cas rien n'est enregistré."""
    labels = flux_config.patient_id_labels(settings)
    read: Counter = Counter()
    by_kind = {code: Counter() for code in patient_data.CATEGORIES}
    by_field = {code: Counter() for code in patient_data.CATEGORIES}
    held, held_p5 = Counter(), Counter()
    for kind, *texts in magasin.textes_pour_detection():
        read[kind] += 1
        found = patient_data.found_in(texts, labels)
        for code, ranks in found.items():
            by_kind[code][kind] += 1
            for rank in ranks:
                by_field[code][FIELDS[rank]] += 1
        if found:
            held[kind] += 1
        if "P5" in found:
            held_p5[kind] += 1
    flags = {code: bool(by_kind[code]) for code in patient_data.CATEGORIES}
    lift = magasin.derniere_levee()               # lue AVANT l'enregistrement : une erreur ici n'enregistre aucun passage (D9)
    scanned_at = magasin.enregistrer_detection(patient_data.DETECTOR_VERSION, patient_data.labels_fingerprint(labels), dict(read), flags)
    kinds = [k for k in KINDS if k in read] + sorted(k for k in read if k not in KINDS)
    per_kind = [cell(read[k], threshold) for k in kinds]
    total = cell(sum(read.values()), threshold)
    if any(c["masked"] for c in per_kind):
        total = {"value": None, "masked": True, "reason": UNDER_THRESHOLD}      # un genre masqué : le total l'est aussi (pas de différence)
    return {
        "contract": CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "detector_version": patient_data.DETECTOR_VERSION,
        "labels_list_present": labels is not None,
        "scanned_at": _instant(scanned_at),
        "items_read": total,
        "kinds": [{"kind": k, "items_read": c} for k, c in zip(kinds, per_kind)],
        "categories": [{"code": code, "expected_noise": code == "P5",
                        "by_kind": [{"kind": k, **cell(by_kind[code][k], threshold)} for k in kinds],
                        "by_field": [{"field": f, **cell(by_field[code][f], threshold)} for f in FIELDS]}
                       for code in patient_data.CATEGORIES],
        "held_back": [{"kind": k, **cell(held[k], threshold)} for k in kinds],
        "held_back_p5": [{"kind": k, **cell(held_p5[k], threshold)} for k in kinds],
        "suspension": suspension_state(lift, labels),
    }


# ---------------------------------------------------------------------------------------------------------------------------------
# Mise en forme seule
# ---------------------------------------------------------------------------------------------------------------------------------

def _valeur(c: dict, t) -> str:
    return t("scan_masked") if c["masked"] else str(c["value"])


def _libelle(prefixe: str, cle: str, t) -> str:
    """Libellé d'un genre ou d'un champ ; un genre inconnu du catalogue s'écrit tel quel (jamais une erreur en cours d'écriture)."""
    try:
        return t(prefixe + cle)
    except KeyError:
        return cle


def _cells(items: list[dict], cle: str, prefixe: str, t) -> str:
    return ", ".join(f"{_libelle(prefixe, i[cle], t)} {_valeur(i, t)}" for i in items)


def scan_lines(doc: dict, t, json_mode: bool = False) -> tuple[list[str], list[str]]:
    """(lignes de la sortie standard, lignes de la sortie d'erreur) du scan, dans l'ordre de D3."""
    lines = [t("scan_header", n=_valeur(doc["items_read"], t))]
    notes = []
    if not doc["labels_list_present"]:
        (notes if json_mode else lines).append(t("labels_absent"))
    for k in doc["kinds"]:
        lines.append(t("scan_kind", kind=_libelle("pdk_", k["kind"], t), n=_valeur(k["items_read"], t)))
    for c in doc["categories"]:
        ligne = t("scan_category", code=c["code"], label=t("cat_" + c["code"]), cells=_cells(c["by_kind"], "kind", "pdk_", t))
        lines.append(f"{ligne} {t('expected_noise')}" if c["expected_noise"] else ligne)
    for c in doc["categories"]:
        lines.append(t("scan_field", code=c["code"], cells=_cells(c["by_field"], "field", "pdf_", t)))
    lines.append(t("scan_held_back", cells=_cells(doc["held_back"], "kind", "pdk_", t)))
    lines.append(t("scan_held_back_p5", cells=_cells(doc["held_back_p5"], "kind", "pdk_", t)))
    notes_fin = [t("scan_recorded", v=doc["detector_version"])]
    s = doc["suspension"]
    if s["state"] == "lifted":
        codes = ", ".join(s["accepted_categories"]) or t("codes_none")
        notes_fin.append(t("suspension_state_off", date=s["lifted_at"][:10], v=s["lift_detector_version"], codes=codes))
    else:
        notes_fin.append(t("suspension_state_on"))
    (notes if json_mode else lines).extend(notes_fin)
    return lines, notes


# ---------------------------------------------------------------------------------------------------------------------------------
# Sous-commandes
# ---------------------------------------------------------------------------------------------------------------------------------

def _preparer(t):
    """(réglages, magasin) ou (code d'arrêt, None). Réglages illisibles : code 1 ; base injoignable : code 1."""
    try:
        settings = hj.reglages()
    except ErreurConfig as erreur:
        print(t("settings_unreadable", detail=str(erreur)), file=sys.stderr)
        return 1, None
    try:
        return settings, store.ouvrir()
    except store.ErreurMagasin:
        print(t("db_unreachable"), file=sys.stderr)
        return 1, None


def scan(args, environ, t) -> int:
    settings, magasin = _preparer(t)
    if magasin is None:
        return settings
    try:
        try:
            doc = patient_scan_result(magasin, settings, masking_threshold(settings))
        except Exception as erreur:
            print(t("db_error", kind=type(erreur).__name__), file=sys.stderr)
            return 1
    finally:
        magasin.fermer()
    if args.json:
        lines, notes = scan_lines(doc, t, json_mode=True)
        for note in notes:
            print(note, file=sys.stderr)
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        return 0
    for line in scan_lines(doc, t)[0]:
        print(line)
    return 0


def lift(args, environ, t) -> int:
    accepted = sorted(set(args.accept or []))
    if any(code not in patient_data.CATEGORIES for code in accepted):
        print(t("usage", what="--accept"), file=sys.stderr)
        return 2
    if not review.est_terminal():
        print(t("no_terminal"), file=sys.stderr)
        return 3
    settings, magasin = _preparer(t)
    if magasin is None:
        return settings
    labels = flux_config.patient_id_labels(settings)
    try:
        try:
            run = magasin.derniere_detection()
        except Exception as erreur:
            print(t("db_error", kind=type(erreur).__name__), file=sys.stderr)
            return 1
        if (run is None or run["detector_version"] != patient_data.DETECTOR_VERSION
                or run["labels_fingerprint"] != patient_data.labels_fingerprint(labels)):
            print(t("lift_refused_none"), file=sys.stderr)
            return 3
        found = sorted(code for code in patient_data.CATEGORIES if run["found"].get(code))
        for code in patient_data.CATEGORIES:
            print(t("scan_category", code=code, label=t("cat_" + code), cells=t("flag_found" if code in found else "flag_none")))
        missing = [code for code in found if code not in accepted]
        if missing:
            print(t("lift_refused_found", codes=", ".join(missing)), file=sys.stderr)
            return 3
        try:
            reponse = review.demander(t("lift_prompt") + " ")
        except EOFError:
            reponse = ""
        if str(reponse).strip().casefold() != t("confirm_word").casefold():
            print(t("lift_declined"))
            return 0
        try:
            magasin.enregistrer_levee(patient_data.DETECTOR_VERSION, patient_data.labels_fingerprint(labels), run["id"], accepted)
        except Exception as erreur:
            print(t("db_error", kind=type(erreur).__name__), file=sys.stderr)
            return 1
        print(t("lift_recorded"))
        return 0
    finally:
        magasin.fermer()


def lancer(args, environ, t) -> int:
    """Point d'entrée du répartiteur pour `patient-scan` et `patient-lift`."""
    return scan(args, environ, t) if args.command == "patient-scan" else lift(args, environ, t)
