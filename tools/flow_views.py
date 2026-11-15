# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : lecture des vues agrégées du schéma flow (lot 6 de la base de données, docs/pmzilla/application.md, 5.3).

    uv run tools/flow_views.py list                       les vues disponibles
    uv run tools/flow_views.py show <vue> [--min-cell N]  le contenu d'une vue
    uv run tools/flow_views.py version-share [--floor N]  homogénéité de la part de fix version (vue v_team_fix_version_share, plancher 80 %)
    uv run tools/flow_views.py masked-cells [--min-cell N]  nombre de cellules masquées par vue et par colonne, sans aucune valeur
    uv run tools/flow_views.py team-ids-check             noms d'équipe à plusieurs identifiants Jira (nombre seulement)

C'est la seule porte de Claude Code vers les données Jira de la base : le script se connecte avec le rôle pmzilla_flow_views, qui n'a
de droit que sur les quatre vues de flow et les deux vues des noms d'équipe v_teams et v_team_jira_ids (aucun sur les tables qui portent les clés de tickets). Les trois vues de qualité des stories
(quality_by_team, quality_coverage_by_team, quality_by_product, change story-quality-audit) se lisent de la même façon sous leur propre rôle,
pmzilla_quality_views (service Trousseau pmzilla-lab-db-pmzilla_quality_views), qui ne lit aucune table du schéma quality. Une cellule de moins de 5 tickets est déjà
masquée dans la vue même. Ici, le seuil peut être relevé (réglage flow_views_min_cell de Flux-Lab/flux.yaml, ou --min-cell), jamais abaissé
sous 5 : une cellule sous le seuil s'affiche « masqué » (« masked » en anglais, idée #417) ; un seuil relevé au-dessus de 5 est
rappelé sur la sortie d'erreur de show, le titre de list donne le seuil configuré. Le mot de passe du rôle est dans le Trousseau (service pmzilla-lab-db-pmzilla_flow_views) :
`uv run tools/db.py role-password pmzilla_flow_views` le pose.

Le masquage de toutes les vues est une seule fonction de service pure, masquer_vue (change masking-sums, R-144) : elle applique les règles de la
conception (D2 ligne à compléter, D3 ligne du produit, D5 règles entre vues) aux seules données publiées ; rendre() ne fait que mettre en forme.
masked-cells et team-ids-check lisent les vues et n'impriment que des nombres : ni nom d'équipe, ni identifiant, ni valeur de compte.

Le nom d'une vue est comparé à une liste fermée avant toute requête. Le script n'écrit rien.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
from messages import Messages, add_language_option  # noqa: E402
from flow_views_messages import CATALOGS  # noqa: E402

ROLE = "pmzilla_flow_views"
ROLE_QUALITE = "pmzilla_quality_views"          # change story-quality-audit : les trois vues du schéma quality, sous leur propre rôle
PLANCHER = 5
VUES_FLOW = ("v_team_status", "v_team_weekly_resolved", "v_team_open_age", "v_team_dependencies")
VUES_QUALITE = ("quality_by_team", "quality_coverage_by_team", "quality_by_product")
VUES_EQUIPES = ("v_teams", "v_team_jira_ids")  # change team-names-readable (D2, D3) : noms d'équipe, type et identifiants Jira, migration 0014
VUE_PART = "v_team_fix_version_share"           # change flow-version-share : part des items terminés avec une fix version, migration 0018
VUE_PHOTO = "v_version_quality_photo"           # change version-quality-photo : photo de qualité par version, migration 0020
VUE_RETARD = "v_team_fix_version_lag"           # change version-quality-photo : délai de la première fix version, migration 0020
VUES_TRANCHE_1 = ("v_team_lead_time_throughput", "v_task_without_team_share", "v_team_ready_queue", "v_team_blocked_share",
                  "v_unplanned_share")           # change mothra-slices, tâche 15.2 : les cinq vues agrégées de la tranche 1, migration 0026
VUE_FLUX = "v_team_flow_inout"                   # change mothra-slices, tâche 36.1 (exception F12, D35) : créés et finis par équipe et trimestre clos, migration 0031
VUE_COUVERTURE = "v_team_delivery_fields_coverage"   # change jira-delivery-fields, D9 : couverture des champs de livraison, migration 0033
# colonnes de couverture (une par champ de livraison : items où le champ est rempli) ; la vue les nomme with_<champ>
COLONNES_COUVERTURE = ("with_sprint", "with_target_version", "with_resolution_version", "with_epic_version_a", "with_epic_version_b",
                       "with_category_nature", "with_workflow_option", "with_release_target", "with_verification_required",
                       "with_product_safety", "with_isp", "with_code_review_status", "with_portfolio_rank",
                       "with_customer_commitment", "with_source_commitment", "with_strategic_objective")
VUES = VUES_FLOW + VUES_EQUIPES + (VUE_PART, VUE_PHOTO, VUE_RETARD) + VUES_QUALITE + VUES_TRANCHE_1 + (VUE_FLUX, VUE_COUVERTURE)  # liste fermée : dix-neuf vues, aucune table
# Les neuf vues qui lisent une fenêtre de trois trimestres clos (flow.closed_quarter_starts) : `list` leur ajoute la limite déclarée de D3 (R-20261114-51).
# Remplace : rien. Retrait : quand la recherche d'export et la durée de conservation couvrent 366 jours (la limite tombe, voir la conception D3).
VUES_TRIMESTRIELLES = (VUE_PART, VUE_RETARD, "v_team_lead_time_throughput", "v_task_without_team_share", "v_team_ready_queue", "v_team_blocked_share", "v_unplanned_share",
                       VUE_FLUX, VUE_COUVERTURE)
# comptes de la vue de la photo (D6) et paires dont la partie est masquée avec le tout (D11) ; parts calculées dans la vue (D14)
COMPTES_PHOTO = ("found", "found_open", "corrected_at_week", "corrected_now", "reopened", "defects_created", "defects_without_affects",
                 "resolved_week", "resolved_week_defects")
PAIRES_PHOTO = {"found_open": "found", "reopened": "corrected_now", "corrected_at_week": "corrected_now",
                "defects_without_affects": "defects_created", "resolved_week_defects": "resolved_week"}
PARTS_PHOTO = {"correction_share_percent": ("resolved_week_defects", "resolved_week"),
               "without_affects_share_percent": ("defects_without_affects", "defects_created")}
SEAUX_RETARD = ("before_or_at_resolution", "within_7_days", "within_30_days", "later", "no_history")   # les cinq cellules font les items
PRODUIT = "(produit)"
def passes_max(semaines: int) -> int:
    """Limite de passes de la boucle de la ligne sans version de la photo (D5-d puis D2, repassés jusqu'à un point fixe ; décision du 2026-10-27) :
    2 x W + 1, W étant le nombre de semaines de la série. Chaque passe qui change quelque chose masque au moins une des 2 x W cellules de la série
    (la visibilité ne passe que de vrai à faux) : au plus 2 x W passes qui changent, une dernière stable. Même formule dans la migration (ligne
    `-- PASSES-MAX 2 x W + 1`, `limite := 2 * n + 1` de flow.photo_serie ; un test la compare). Limite atteinte : MasquageInstable, rien n'est publié."""
    return 2 * semaines + 1


class MasquageInstable(RuntimeError):
    """Le masquage complémentaire n'atteint pas son point fixe dans la limite de passes de la série : la vue n'est pas publiée."""


class ReglagesIllisibles(RuntimeError):
    """flux.yaml existe mais ne se lit pas (YAML cassé, flow_views_min_cell non entier) : refus, jamais un repli sur le plancher (audit #629, H-13).
    Remplace : le repli silencieux sur PLANCHER avec un avertissement. Retrait : permanent (un seuil que l'on ne sait pas lire n'est pas un seuil de 5)."""


CODE_REGLAGES_ILLISIBLES = 78                              # EX_CONFIG, comme le refus de la racine de contenu (lab_paths)
CODE_MASQUAGE_INSTABLE = 4                                 # les codes déjà pris sont 0, 1, 3 et 78


# colonnes de comptage : seules soumises au masquage (le drapeau single_po d'une équipe n'en est pas une)
COLONNES_COMPTE = ("tickets", "links", "collected", "audited", "empty_acceptance_criteria", "met", "not_met", "not_applicable",
                   "undetermined", "items", "with_fix_version") + COMPTES_PHOTO + SEAUX_RETARD + (
                   "throughput", "items_lt", "items_ct", "items_old", "items_without_commitment",      # tranche 1 (0026) : colonnes passées par mask_*
                   "tasks_done", "ready", "blocked_n", "unplanned_n",
                   "tasks_without_team", "blocked", "unplanned",      # comptes en CASE WHEN >= 5 dans 0026 : masqués aussi au seuil relevé
                   "created", "done") + COLONNES_COUVERTURE          # v_team_flow_inout (0031) : créés et finis du trimestre ; couverture (0033)
# Statistiques de la tranche 1 masquées avec leur colonne d'effectif (une médiane ou un P85 d'un effectif masqué ne se montre jamais), et parts
# masquées avec leur partie, leur tout et le reste (tout - partie) : (partie, tout), à la manière de PARTS_PHOTO. Change mothra-slices, tâche 15.2.
STATS_TRANCHE_1 = {
    "v_team_lead_time_throughput": {"lead_median_days": "items_lt", "lead_p85_days": "items_lt",
                                    "cycle_median_days": "items_ct", "cycle_p85_days": "items_ct",
                                    # D16, « Grouped year without the old items » (22.1, R-20261105-30) : quatre colonnes ajoutées en fin de vue (migration 0038),
                                    # lues par le seul rapport de H1 ; masquées avec leur effectif, et par STATS_SANS_ANCIENS ci-dessous
                                    "lead_median_days_excl_old": "items_lt", "lead_p85_days_excl_old": "items_lt",
                                    "cycle_median_days_excl_old": "items_ct", "cycle_p85_days_excl_old": "items_ct"},
}
# Les statistiques « sans les anciens » : masquées aussi sauf si items_old de la ligne est montré et que leur effectif moins items_old atteint le seuil (le lecteur
# ne lit pas m - o autrement : il se ferme). Au plancher comme au seuil relevé. Même règle dans mothra/contract/src/masquage.ts.
# Remplace : rien (colonnes nouvelles ; la règle de la première 0038, sans condition sur items_old, fuyait : R-20261106-59). Retrait : permanent tant que la vue
# publie ces colonnes (elles tombent avec la bascule de H1 sur d'autres colonnes ou avec la fin du rapport de H1).
STATS_SANS_ANCIENS = ("lead_median_days_excl_old", "lead_p85_days_excl_old", "cycle_median_days_excl_old", "cycle_p85_days_excl_old")
PARTS_TRANCHE_1 = {
    "v_task_without_team_share": {"share_percent": ("tasks_without_team", "tasks_done")},
    "v_team_blocked_share": {"share_percent": ("blocked", "blocked_n")},
    "v_unplanned_share": {"share_percent": ("unplanned", "unplanned_n")},
}
SANS_EQUIPE = "(sans équipe)"                    # libellé de la vue pour les items sans équipe : hors du verdict, montré à part
PLANCHER_PART = 80                               # part minimale (en %) du verdict d'homogénéité, option --floor
# Ordre des lignes des trois vues de qualité (change story-quality-audit, D15, M3 (a)) : équipe, genre d'élément, code du critère ; la vue
# du produit n'a pas d'équipe, la couverture n'a pas de code. Jamais l'ordre d'un compte ; Mothra garde cet ordre.
CLES_DE_TRI_QUALITE = ("team", "item_kind", "criterion_code")
# Vues lues avec la vue demandée pour les règles entre vues (D5-a, D5-b, D5-c)
VUE_HEBDO = "v_team_weekly_resolved"
VUE_DEBIT = "v_team_lead_time_throughput"
VUES_LIEES = {"v_teams": ("v_team_status", "v_team_jira_ids"), "v_team_jira_ids": ("v_teams", "v_team_status"), VUE_RETARD: (VUE_PART,),
              VUE_HEBDO: (VUE_DEBIT,), VUE_DEBIT: (VUE_HEBDO,)}      # les deux dernières : relation T3 de masking-sums D17 (tâche 13.3)

LO_ANCIENS_SI_CT_MONTRE = 1      # borne basse d'un items_old masqué dont items_ct est montré (R-20261106-39, conception D2 et D16)

# Bornes d'une cellule masquée (conception, « Attacker model ») : (lo, complément). lo vaut 1 quand la ligne n'existe que pour un compte d'au moins
# 1 (ligne de GROUP BY : lignes d'équipe, noms, items), 0 pour les tranches, les comptes filtrés, les verdicts et les paires. Le complément dit
# qu'un masquage complémentaire peut s'appliquer au groupe : la borne haute est alors le plus grand de seuil - 1 et de la plus petite cellule
# visible. La vue en SQL reprend la même table (un test les compare).
BORNES = {
    "v_team_status": {"tickets": (1, False)},
    "v_team_weekly_resolved": {"tickets": (1, False)},
    "v_team_open_age": {"tickets": (1, False)},
    "v_team_dependencies": {"links": (1, False)},
    "v_teams": {"tickets": (1, False)},
    "v_team_jira_ids": {"tickets": (1, True)},
    VUE_PART: {"items": (1, False), "with_fix_version": (0, False)},
    VUE_RETARD: {"items": (1, False), **{c: (0, True) for c in SEAUX_RETARD}},
    VUE_PHOTO: {c: (0, False) for c in COMPTES_PHOTO},
    "quality_by_team": {"audited": (0, False), "met": (0, True), "not_met": (0, True), "not_applicable": (0, True), "undetermined": (0, True)},
    "quality_coverage_by_team": {"collected": (1, False), "audited": (0, False), "empty_acceptance_criteria": (0, False)},
    "quality_by_product": {"audited": (0, False), "met": (0, True), "not_met": (0, True), "not_applicable": (0, True), "undetermined": (0, True)},
    # tranche 1 (migration 0026) : le débit, la file prête, les bloqués et les non planifiés sont des lignes de GROUP BY (au moins 1) ; les effectifs
    # liés au débit (lead time, cycle time, anciens, sans engagement) sont des comptes filtrés (0). Pas de drapeau de complément déclaré ici : les
    # paires (n, m), (n, c, g), (m, c), (c, o) et la règle de série entre l'année groupée et les trimestres sont appliquées par _masque_debit, au
    # seuil relevé comme au plancher (revue 15.2, constats 1 et 2) ; la relation T3 est portée par D17 (lignes_publiees, _t3_retires) ; les autres relations T1 à T13 de masking-sums D15 et D16 (groupe 7) restent à porter.
    # items_without_commitment : le zéro que la base montre (mask_count_zero) est masqué ici, plus strict que la base.
    "v_team_lead_time_throughput": {"throughput": (1, False), "items_lt": (0, False), "items_ct": (0, False), "items_old": (0, False),
                                    "items_without_commitment": (0, False)},
    # items_old : (0, False) quand items_ct est masqué ; LO_ANCIENS_SI_CT_MONTRE (1) quand items_ct est montré, puisque le zéro est alors montré
    # (R-20261106-39 ; remplace le masquage du zéro, retrait permanent tant que la vue publie items_old).
    "v_task_without_team_share": {"tasks_done": (1, False), "tasks_without_team": (0, True)},
    "v_team_ready_queue": {"ready": (1, False)},
    "v_team_blocked_share": {"blocked_n": (1, False), "blocked": (0, True)},
    "v_unplanned_share": {"unplanned_n": (1, False), "unplanned": (0, True)},
    # v_team_flow_inout (0031, tâche 36.1) : une ligne existe dès qu'un des deux comptes vaut au moins 1, l'autre peut valoir 0 ; aucun total publié à
    # compléter dans la vue (D2) : seule la règle D3 de la ligne du produit s'applique. Les relations avec d'autres vues (T13 et les trois de D35) sont
    # à déclarer dans masking-sums D16 (groupe 7), pas ici.
    "v_team_flow_inout": {"created": (0, False), "done": (0, False)},
    # v_team_delivery_fields_coverage (0033, jira-delivery-fields D9) : une ligne existe dès qu'un item terminé existe (au moins 1) ; un compte de
    # champs remplis peut valoir 0. Aucun total publié à compléter, aucune ligne du produit : le remplissage est masqué avec son reste.
    VUE_COUVERTURE: {"items": (1, False), **{c: (0, False) for c in COLONNES_COUVERTURE}},
}


def fichier_config() -> Path:
    """Flux-Lab/flux.yaml de la racine de contenu (tools/lab_paths.py), jamais de la racine du code : depuis un worktree, le Flux-Lab du
    code est absent et le seuil retomberait au plancher. Racine introuvable : message et code 78 du module partagé, jamais un repli."""
    import lab_paths
    return lab_paths.resolve_or_exit()["content_root"] / "Flux-Lab" / "flux.yaml"


def seuil_configure(t: Messages, fichier: Path | None = None) -> int:
    """Seuil de flux.yaml (flow_views_min_cell), jamais en dessous de PLANCHER. Fichier absent : PLANCHER. Fichier illisible : ReglagesIllisibles
    (H-13, R-20261107-30). Sans fichier donné : fichier_config(). `t` n'est plus utilisé ici : le message est celui de l'appelant."""
    import yaml
    fichier = fichier_config() if fichier is None else fichier
    try:
        if not fichier.exists():
            return PLANCHER
        donnees = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
        valeur = int(donnees.get("flow_views_min_cell", PLANCHER))
    except (OSError, ValueError, TypeError, yaml.YAMLError, AttributeError):
        raise ReglagesIllisibles("flux.yaml") from None
    return max(PLANCHER, valeur)


def seuil_effectif(configure: int, option: int | None) -> int:
    """Le seuil relevé par l'option l'emporte ; il ne descend jamais sous le réglage ni sous PLANCHER."""
    return max(PLANCHER, configure, option or 0)


def cellule(colonne: str, valeur, seuil: int) -> dict:
    """Cellule structurée (D7). Colonne de comptage : {"value": n} à partir du seuil, sinon (nul de la vue compris) une cellule masquée
    avec sa raison et son seuil. Toute autre colonne (identifiant Jira, type d'équipe, nom) : {"value": v}, jamais masquée."""
    if colonne in COLONNES_COMPTE and (valeur is None or valeur < seuil):
        return {"value": None, "masked": "under_threshold", "threshold": seuil}
    return {"value": valeur}


def part_visible(items, avec, seuil: int) -> bool:
    """Une part n'est montrée que si les items, ceux avec fix version et ceux sans (leur différence) atteignent tous le seuil : un nul de
    la vue (masquage de la base) compte comme masqué."""
    if items is None or avec is None:
        return False
    return min(items, avec, items - avec) >= seuil


def cellule_part(noms: list[str], ligne: tuple, cellules: dict, seuil: int) -> tuple[str, float | None]:
    """Lecture d'une ligne de la vue de part, d'après les cellules que masquer_vue en donne (revue R-144, m5) : ("share", part en %), ("bound",
    borne basse en % des items, d'après le chiffre publié par la vue, jamais une estimation faite ici) ou ("masked", None). La borne n'est lue que
    si la cellule des items est visible."""
    if "masked" not in cellules["with_fix_version"] and "masked" not in cellules["share_percent"] and cellules["share_percent"]["value"] is not None:
        return "share", cellules["share_percent"]["value"]
    borne = ligne[noms.index("with_fix_version_min")] if "with_fix_version_min" in noms else None
    items = cellules["items"]
    if borne is not None and "masked" not in items and items["value"] is not None:
        return "bound", 100.0 * borne / items["value"]
    return "masked", None


def detail_part(genre: str, valeur, t: Messages) -> str:
    """Une cellule de part pour la ligne à part : part, borne basse (« ≥ ») ou « masqué »."""
    if genre == "share":
        return f"{valeur} %"
    if genre == "bound":
        return f"≥ {valeur:.1f} %"
    return t("masked")


def aujourdhui() -> date:
    """Date du jour en UTC (comme la vue) ; une fonction à part pour que les tests fixent la date de référence."""
    return datetime.now(timezone.utc).date()


def trois_trimestres_clos(instant: datetime | date) -> list[date]:
    """Débuts des trois trimestres civils clos avant le trimestre UTC de `instant` (le trimestre en cours n'y est jamais), du plus récent au plus
    ancien : l'ordre de flow.closed_quarter_starts (change de trois trimestres clos, D2 ; fonction pure). Même fenêtre en SQL et en TypeScript
    (fenetreTroisTrimestres) : un test compare les trois sur chaque jour de 2027 à 2030.
    Remplace : les quatre trimestres écrits dans chaque vue et dans trimestres_termines. Retrait : permanent, tant que les vues portent des trimestres."""
    if isinstance(instant, datetime):
        jour = instant.astimezone(timezone.utc).date() if instant.tzinfo is not None else instant.date()
    else:
        jour = instant
    indice = jour.year * 4 + (jour.month - 1) // 3               # numéro de trimestre depuis l'an 0
    return [date(i // 4, 3 * (i % 4) + 1, 1) for i in (indice - 1, indice - 2, indice - 3)]


def trimestres_termines(reference: date | None = None) -> list[date]:
    """Débuts des trois derniers trimestres civils terminés avant la date de référence (le trimestre en cours n'y est jamais), du plus
    ancien au plus récent."""
    return sorted(trois_trimestres_clos(reference or aujourdhui()))


def verdict_part(noms: list[str], lignes: list[tuple], plancher: int, seuil: int = PLANCHER, reference: date | None = None) -> dict:
    """Homogénéité de la part de fix version (fonction pure). Les lignes sont celles de la vue, sans la ligne « (produit) ». Une équipe dont
    toutes les parts sont masquées est « non établie » : laissée de côté, jamais comptée. Un trimestre masqué d'une équipe n'établit rien
    pour elle, sans casser l'homogénéité. Résultat : verdict « homogeneous » (trois trimestres), « since » (à partir du trimestre
    `since`), « not_homogeneous » (le dernier trimestre visible d'une équipe est sous le plancher) ou « not_established » (aucune équipe
    établie) ; `not_established` liste les équipes laissées de côté. Les trois trimestres attendus sont les trois derniers terminés
    avant `reference` (la date du jour par défaut) : une ligne d'un autre trimestre, le trimestre en cours compris, n'entre jamais dans
    le verdict."""
    i_equipe, i_trim = noms.index("team"), noms.index("quarter_start")
    ecartees = ("(produit)", SANS_EQUIPE)
    attendus = trimestres_termines(reference)
    lignes = [ligne for ligne in lignes if ligne[i_trim] in attendus]
    trimestres = sorted({ligne[i_trim] for ligne in lignes if ligne[i_equipe] not in ecartees})
    cellules = masquer_vue(VUE_PART, noms, lignes, seuil)       # une seule fonction de masquage (D4) ; la ligne du produit y entre (D3)
    series: dict[str, dict] = {}
    sans_equipe = []
    for ligne, cellules_ligne in zip(lignes, cellules):
        if ligne[i_equipe] == "(produit)":
            continue
        genre, valeur = cellule_part(noms, ligne, cellules_ligne, seuil)
        if ligne[i_equipe] == SANS_EQUIPE:                     # montrée à part, jamais comptée dans le verdict (décision du 2026-10-23)
            sans_equipe.append((ligne[i_trim], genre, valeur))
            continue
        if genre == "bound":                                   # borne publiée par la vue : au-dessus du plancher, ou rien d'établi
            valeur = valeur if valeur >= plancher else None
        series.setdefault(ligne[i_equipe], {})[ligne[i_trim]] = valeur
    non_etablies = sorted(e for e, parts in series.items() if all(p is None for p in parts.values()))
    etablies = {e: parts for e, parts in series.items() if e not in non_etablies}
    resultat = {"verdict": "not_established", "since": None, "not_established": non_etablies, "no_team": sorted(sans_equipe)}
    if not etablies:
        return resultat
    dernier_echec = None
    for parts in etablies.values():
        visibles = sorted(q for q, p in parts.items() if p is not None)
        if parts[visibles[-1]] < plancher:
            resultat["verdict"] = "not_homogeneous"
            return resultat
        for q in visibles:
            if parts[q] < plancher and (dernier_echec is None or q > dernier_echec):
                dernier_echec = q
    if dernier_echec is None:
        # « homogène sur les trois trimestres » exige trois trimestres présents et lisibles pour l'équipe : sinon elle est non établie
        incompletes = sorted(e for e, parts in etablies.items() if any(parts.get(q) is None for q in attendus))
        resultat["not_established"] = sorted(non_etablies + incompletes)
        if len(incompletes) < len(etablies):
            resultat["verdict"] = "homogeneous"
        return resultat
    resultat["verdict"] = "since"
    resultat["since"] = next(q for q in trimestres if q > dernier_echec)
    return resultat


def est_vue_photo(noms: list[str]) -> bool:
    return "week_start" in noms and "n_adopted" in noms


def est_vue_retard(noms: list[str]) -> bool:
    return "no_history" in noms and "quarter_start" in noms


def est_vue_part(noms: list[str]) -> bool:
    return all(n in noms for n in ("items", "with_fix_version", "share_percent"))


def est_vue_flux(noms: list[str]) -> bool:
    return all(n in noms for n in ("type_group", "created", "done"))


def est_vue_couverture(noms: list[str]) -> bool:
    return "item_kind" in noms and "items" in noms and "with_sprint" in noms


# ---------------------------------------------------------------------------------------------------------------------------------------
# Masquage : une seule fonction de service pure (change masking-sums, R-144 ; conception D2, D3, D4, D5, D11)
# ---------------------------------------------------------------------------------------------------------------------------------------

def _masquee(seuil: int) -> dict:
    return {"value": None, "masked": "under_threshold", "threshold": seuil}


def _visible(valeur, seuil: int) -> bool:
    """Un nul de la vue (masquage de la base) compte comme masqué."""
    return valeur is not None and valeur >= seuil


def _compte_photo_visible(ligne: dict, col: str, seuil: int) -> bool:
    """Un compte de la photo est visible au seuil quand il l'atteint et, pour la partie d'une paire, que le tout moins la partie l'atteint aussi
    (D11)."""
    valeur = ligne.get(col)
    if not _visible(valeur, seuil):
        return False
    tout = PAIRES_PHOTO.get(col)
    if tout is None:
        return True
    reste = ligne.get(tout)
    return reste is not None and reste - valeur >= seuil


def _borne(vue: str, colonne: str, items_ct_visible: bool = False) -> tuple[int, bool]:
    """(lo, complément) de BORNES pour une colonne d'une vue (revue R-144, M3) : aucune règle ne code seuil - 1 ni le drapeau en dur.
    `items_ct_visible` (R-20261106-39, revue 21.2, constat 8) : pour items_old de v_team_lead_time_throughput, la borne basse vaut LO_ANCIENS_SI_CT_MONTRE (1) quand
    items_ct de la même ligne est montré (le zéro est alors montré), BORNES (0) sinon. Même borne en SQL (0037, commentaire de tête) et en TypeScript
    (masquage.ts, LO_ANCIENS_SI_CT_MONTRE) : un test statique compare les trois."""
    lo, complement = BORNES[vue][colonne]
    if items_ct_visible and vue == VUE_DEBIT and colonne == "items_old":
        return LO_ANCIENS_SI_CT_MONTRE, complement
    return lo, complement


def _haut(vue: str, colonne: str, seuil: int, visibles) -> int:
    """Borne haute d'une cellule masquée : seuil - 1 ; avec le drapeau de complément de BORNES, le plus grand de seuil - 1 et de la plus petite
    cellule visible du groupe (`visibles` : leurs valeurs)."""
    visibles = list(visibles)
    return max(seuil - 1, min(visibles)) if _borne(vue, colonne)[1] and visibles else seuil - 1


def _regle_ligne(vue: str, total: int, termes: dict, visibles: dict, seuil: int) -> tuple[dict, bool]:
    """D2, ligne à compléter (un total visible et ses termes ; les termes sont des colonnes de `vue`). Les termes masqués doivent être au moins
    deux, de somme S d'au moins le seuil, et S différent de la somme des bornes basses et de la somme des bornes hautes, lues dans BORNES ; la borne
    haute d'un terme masqué est seuil - 1, ou le plus grand de seuil - 1 et de la plus petite cellule visible quand le drapeau de complément le
    dit. Sinon le plus petit terme visible (à égalité, le premier de la liste) est masqué à son tour et la vérification repart ; sans terme
    visible, c'est le total qui est masqué. Un zéro masqué compte comme une cellule masquée. Renvoie (visibilité des termes, total masqué).
    N'utilise que des cellules visibles."""
    visibles = dict(visibles)
    ordre = list(termes)
    while True:
        cachees = [c for c in ordre if not visibles[c]]
        if not cachees:
            return visibles, False
        vus = [c for c in ordre if visibles[c]]
        somme = total - sum(termes[c] for c in vus)
        valeurs = [termes[c] for c in vus]
        bas = sum(_borne(vue, c)[0] for c in cachees)
        haut = sum(_haut(vue, c, seuil, valeurs) for c in cachees)
        k = len(cachees)
        if k >= 2 and somme >= seuil and somme != bas and somme != haut:
            return visibles, False
        if not vus:
            return visibles, True
        visibles[min(vus, key=lambda c: (termes[c], ordre.index(c)))] = False


def _etat_plancher(items, avec, borne) -> tuple[bool, int | None]:
    """Image de la vue de la part au plancher : (détail masqué, borne basse publiée). La borne n'est publiée que lorsque le compte sans fix
    version est sous le plancher : sans borne et détail masqué, ce compte vaut au moins 5 (cas X10)."""
    if items is None or items < PLANCHER:
        return True, None
    if avec is None:
        return True, borne
    sans = items - avec
    if avec < PLANCHER or sans < PLANCHER:
        return True, (items - (PLANCHER - 1)) if sans < PLANCHER else None
    return False, None


def _masque_part(noms, rangees, seuil, applic, vis) -> None:
    """Vue de la part : primaire, relation « items = avec + sans » (D2, X10), ligne du produit (D3, X3 X4 X5)."""
    colonnes = ("items", "with_fix_version", "share_percent")
    produits, equipes = [], defaultdict(list)
    for i, r in enumerate(rangees):
        applic[i] = set(colonnes)
        items, avec = r.get("items"), r.get("with_fix_version")
        iv = _visible(items, seuil)
        if iv:
            cache, publiee = _etat_plancher(items, avec, r.get("with_fix_version_min"))
            if cache and publiee is None and min(PLANCHER - 1, items - PLANCHER) <= 0:
                iv = False                              # « avec » n'a qu'une valeur possible : les items de la ligne sont masqués
        dv = iv and part_visible(items, avec, seuil)
        vis[i] = {"items": iv, "with_fix_version": dv, "share_percent": dv and r.get("share_percent") is not None}
        if r.get("team") == PRODUIT:
            produits.append(i)
        else:
            equipes[r.get("quarter_start")].append(i)
    for p in produits:                                   # D3 : toutes les cellules d'équipe de la colonne, ou aucune
        for col in colonnes:
            if not all(vis[t][col] for t in equipes[rangees[p].get("quarter_start")]):
                vis[p][col] = False


def _masque_flux(rangees, seuil, applic, vis) -> None:
    """Vue des créés et des finis par équipe et trimestre clos (tâche 36.1) : primaire (un nul de la vue est une cellule cachée), puis D3 sur la ligne du
    produit : sa cellule d'une colonne n'est montrée que si toutes les cellules d'équipe de cette colonne (même trimestre, même groupe de types, ligne
    « sans équipe » comprise) sont visibles. Un produit sans aucune ligne d'équipe publiée est masqué (échec fermé). Aucune relation avec une autre
    vue ici (T13 et les trois de D35 : groupe 7 de masking-sums)."""
    colonnes = ("created", "done")
    produits, equipes = [], defaultdict(list)
    for i, r in enumerate(rangees):
        applic[i] = set(colonnes)
        vis[i] = {c: _visible(r.get(c), seuil) for c in colonnes}
        if r.get("team") == PRODUIT:
            produits.append(i)
        else:
            equipes[(r.get("quarter_start"), r.get("type_group"))].append(i)
    for p in produits:
        groupe = equipes.get((rangees[p].get("quarter_start"), rangees[p].get("type_group")), [])
        for col in colonnes:
            if not groupe or not all(vis[t][col] for t in groupe):
                vis[p][col] = False


def _masque_couverture(rangees, seuil, applic, vis) -> None:
    """Couverture des champs de livraison (jira-delivery-fields D9, migration 0033) : le nombre d'items est visible au seuil ; le nombre
    d'items où un champ est rempli l'est quand le nombre de remplis ET le nombre de non remplis (items - remplis) atteignent le seuil. La vue
    masque déjà ainsi au plancher ; ici, un seuil relevé masque davantage, jamais moins. Un nul de la vue est une cellule cachée. Aucune
    ligne du produit, aucune relation avec une autre vue."""
    colonnes = ("items",) + COLONNES_COUVERTURE
    for i, r in enumerate(rangees):
        applic[i] = set(colonnes)
        items = r.get("items")
        vis[i] = {"items": _visible(items, seuil)}
        for c in COLONNES_COUVERTURE:
            rempli = r.get(c)
            vis[i][c] = items is not None and _visible(rempli, seuil) and _visible(items - rempli, seuil)


def _ligne_retard(r: dict, seuil: int, permis: dict | None, cachee: bool) -> dict:
    colonnes = ("items",) + SEAUX_RETARD
    items = r.get("items")
    if cachee or not _visible(items, seuil) or (permis is not None and not permis["items"]):
        return {c: False for c in colonnes}
    v = {c: _visible(r.get(c), seuil) and (permis is None or permis[c]) for c in SEAUX_RETARD}
    v, total = _regle_ligne(VUE_RETARD, items, {c: r.get(c) for c in SEAUX_RETARD}, v, seuil)
    if total:
        return {c: False for c in colonnes}
    return {"items": True, **v}


def _masque_retard(noms, rangees, seuil, applic, vis, liees) -> None:
    """Vue du retard : primaire, D5-c (la ligne suit la part au seuil), D2 sur les cinq tranches, D3 sur le produit."""
    colonnes = ("items",) + SEAUX_RETARD
    cachees_part: set = set()
    if VUE_PART in liees:
        noms_p, lignes_p = liees[VUE_PART]
        visibles_p, connues = set(), set()
        for ligne, c in zip(lignes_p, masquer_vue(VUE_PART, noms_p, lignes_p, seuil)):
            r = dict(zip(noms_p, ligne))
            cle = (r.get("team"), r.get("quarter_start"))
            connues.add(cle)
            if "masked" not in c["items"] and "masked" not in c["with_fix_version"] and c["items"]["value"] - c["with_fix_version"]["value"] >= seuil:
                visibles_p.add(cle)
        cachees_part = connues - visibles_p
    produits, equipes = [], defaultdict(list)
    for i, r in enumerate(rangees):
        applic[i] = set(colonnes)
        if r.get("team") == PRODUIT:
            produits.append(i)
            continue
        vis[i] = _ligne_retard(r, seuil, None, (r.get("team"), r.get("quarter_start")) in cachees_part)
        equipes[r.get("quarter_start")].append(i)
    for p in produits:
        r = rangees[p]
        permis = {c: all(vis[t][c] for t in equipes[r.get("quarter_start")]) for c in colonnes}
        vis[p] = _ligne_retard(r, seuil, permis, (PRODUIT, r.get("quarter_start")) in cachees_part)


def _comptes_statut(liees: dict, seuil: int) -> dict:
    """D5-a : par nom, (somme des comptes de statut visibles, nombre de cellules de statut masquées), d'après la vue des statuts."""
    par_equipe: dict = {}
    if "v_team_status" in liees:
        noms_s, lignes_s = liees["v_team_status"]
        for ligne in lignes_s:
            s = dict(zip(noms_s, ligne))
            acc = par_equipe.setdefault(s.get("team"), [0, 0])
            if _visible(s.get("tickets"), seuil):
                acc[0] += s["tickets"]
            else:
                acc[1] += 1
    return par_equipe


def _identifiants(seuil: int, comptes: dict, ids: dict, par_statut: dict | None = None) -> tuple[set, set]:
    """D5-a, D5-b et leur famille, une seule règle pour la vue des noms et celle des identifiants (revue R-144, M2 (a), m1). `comptes` : nom ->
    compte de la vue des noms ; `ids` : nom -> [(rang, compte de l'identifiant)] ; `par_statut` : sortie de _comptes_statut. Renvoie les noms
    dont le compte est masqué et les rangs d'identifiants masqués. Modèle de l'attaquant au cas le plus défavorable, y compris des données Jira
    propres (compte = somme des identifiants) : quand le compte d'un nom est masqué (sous le seuil, par D5-a ou par la famille), son plus petit
    identifiant visible l'est aussi (option A de l'auteur). Compte visible, tous les identifiants visibles : écart D = somme des identifiants
    moins compte, masqué de 1 à seuil - 1 en valeur absolue (zéro non protégé), avec le plus petit identifiant. Identifiants masqués : la
    relation « compte = somme des identifiants » suit D2 avec les bornes de BORNES (lo, borne haute, la plus petite visible en complément),
    la vérification repartant après chaque complément, à condition d'être possible."""
    lo, _ = _borne("v_team_jira_ids", "tickets")
    caches_avant = set()                                    # noms masqués avant la famille : sous le seuil, absents de la vue, D5-a
    for nom in set(comptes) | set(ids):
        c = comptes.get(nom)
        if not _visible(c, seuil):
            caches_avant.add(nom)
        elif nom in (par_statut or {}):
            somme, k = par_statut[nom]
            if k >= 1 and c - somme <= k:
                caches_avant.add(nom)
    noms_caches, rangs = set(caches_avant), set()
    for nom, lignes in ids.items():
        c = comptes.get(nom)
        visibles = {rang: v for rang, v, _ in lignes if _visible(v, seuil)}
        identifiant = {rang: ident for rang, _, ident in lignes}

        def plus_petit() -> int:
            # égalité départagée par l'identifiant Jira, comme le SQL (ORDER BY n, jira_team_id), jamais par la position de ligne (revue 2, M2)
            return min(visibles, key=lambda x: (visibles[x], str(identifiant[x]), x))
        if nom in caches_avant:
            rangs.update(visibles)                          # 5.11, option A élargie : tous les identifiants visibles
            continue
        k = len(lignes) - len(visibles)
        if k == 0:
            if 1 <= abs(sum(visibles.values()) - c) <= seuil - 1:
                noms_caches.add(nom)
                rangs.update(visibles)                      # 5.11 : nom masqué, tous ses identifiants visibles le sont
            continue
        while True:
            somme = c - sum(visibles.values())
            haut = _haut("v_team_jira_ids", "tickets", seuil, visibles.values())
            if not k * lo <= somme <= k * haut:
                break
            if k >= 2 and somme >= seuil and somme != k * lo and somme != k * haut:
                break
            if not visibles:
                noms_caches.add(nom)
                break
            rang = plus_petit()
            rangs.add(rang)
            del visibles[rang]
            k += 1
    return noms_caches, rangs


def _masque_equipes(vue, noms, rangees, seuil, vis, liees) -> None:
    """v_teams (D5-a, D5-b) et v_team_jira_ids (complément des identifiants, m1) : une famille, calculée de la même façon des deux côtés."""
    par_statut = _comptes_statut(liees, seuil)
    if vue == "v_teams":
        if "v_team_jira_ids" not in liees and "v_team_status" not in liees:
            return
        ids: dict = defaultdict(list)
        if "v_team_jira_ids" in liees:
            noms_i, lignes_i = liees["v_team_jira_ids"]
            for rang, ligne in enumerate(lignes_i):
                s = dict(zip(noms_i, ligne))
                ids[s.get("team")].append((rang, s.get("tickets"), s.get("jira_team_id")))
        comptes = {r.get("team"): r.get("tickets") for r in rangees}
        caches, _ = _identifiants(seuil, comptes, ids, par_statut)
        for i, r in enumerate(rangees):
            if r.get("team") in caches:
                vis[i]["tickets"] = False
    elif vue == "v_team_jira_ids" and "v_teams" in liees:
        noms_t, lignes_t = liees["v_teams"]
        comptes = {dict(zip(noms_t, ligne)).get("team"): dict(zip(noms_t, ligne)).get("tickets") for ligne in lignes_t}
        ids = defaultdict(list)
        for i, r in enumerate(rangees):
            ids[r.get("team")].append((i, r.get("tickets"), r.get("jira_team_id")))
        _, rangs = _identifiants(seuil, comptes, ids, par_statut)
        for i in rangs:
            vis[i]["tickets"] = False


def propagation_max(variables: int, borne: int) -> int:
    """Limite de balayages de la propagation (D15, « Termination and limits ») : 1 + V x (2M + 3), V le nombre de variables de l'unité et M la
    borne finie maximale. Sous le contrôle d'exécution « aucune borne finie au-dessus de M », chaque balayage qui change quelque chose déplace une borne
    d'au moins 1 : une borne basse prend au plus M + 1 valeurs, une borne haute au plus M + 2 (l'infini compris), soit au plus V x (2M + 3) balayages
    qui changent, plus un balayage stable. Même formule dans la migration (ligne `-- PROPAGATION-MAX 1 + V x (2M + 3)` ; un test la compare)."""
    return 1 + variables * (2 * borne + 3)


def propagation_zero_max(variables: int, relations: int) -> int:
    """Limite de balayages de chaque lecture « m = 0 » (D15 ; M2 a de la fiche R-20261104-6) : 4 x (V + R) + 10, V variables et R relations. Un
    pari « m = 0 » que les cellules publiées contredisent ne se resserre jamais : les bornes montent d'une unité ou de quelques unités par balayage jusqu'à
    M, ce qui prend de l'ordre de M balayages (des dizaines de milliers pour des cellules de quelques dizaines). Une lecture cohérente converge en peu
    de balayages ; la limite atteinte est une erreur (MasquageInstable, rien n'est publié), jamais un écart de la lecture. Même formule dans la migration
    (ligne `-- PROPAGATION-ZERO-MAX 4 x (V + R) + 10`). Valable pour toutes les lectures de pari par ligne (« m = 0 », « U = 0 », « U = 0 et m = 0 », M7 a).
    Replaces: nothing in D15 (borne neuve des seules lectures par ligne, que PROPAGATION-MAX bornait avant). Condition de retrait (M9 a, R-20261104-12, amendée par
    R-20261104-50) : une exception due à cette limite, comptée par la mesure 17.1 au plancher et au seuil relevé 10, revient à l'auteur avant tout retrait ;
    la limite tombe avec la mesure 17.1, une fois ses exceptions tranchées par l'auteur (P6 seulement si des exceptions apparaissent) ; ces lectures
    reprennent alors PROPAGATION-MAX."""
    return 4 * (variables + relations) + 10


def boucle_max(cellules: int) -> int:
    """Limite de la boucle externe de la propagation (D15) : C + 1, C étant le nombre de cellules de comptage publiées de l'unité au début de la
    boucle. Chaque passe qui ne s'arrête pas masque exactement une cellule publiée : au plus C passes qui masquent, une dernière stable. Même formule
    dans la migration (ligne `-- LOOP-MAX C + 1`)."""
    return cellules + 1


def _propager(lo: list, hi: list, relations: list, borne_m: int, limite: int) -> tuple[list, list, bool]:
    """Propagation des bornes (D15, bounds consistency). `lo` et `hi` : intervalle de chaque variable (hi None : sans borne haute) ; `relations` :
    liste de (sorte, second membre, termes), sorte « eq » (somme des coef x variable = second membre) ou « le » (inférieure ou égale), termes de
    (variable, coefficient +1 ou -1). Un balayage prend les relations dans l'ordre de la liste, et dans chacune ses termes dans l'ordre ; chaque
    intervalle est resserré sur place. Les balayages se répètent jusqu'à un balayage stable. Renvoie (lo, hi, vide) : `vide` quand un intervalle
    devient vide (lecture incohérente avec les cellules publiées). Une borne finie au-dessus de `borne_m`, ou plus de `limite` balayages :
    MasquageInstable (rien n'est publié)."""
    lo, hi = list(lo), list(hi)
    for _ in range(limite):
        change = False
        for sorte, second, termes in relations:
            for k, (xk, ak) in enumerate(termes):
                somme_max = somme_min = 0
                max_infini = min_infini = False
                for j, (xj, aj) in enumerate(termes):
                    if j == k:
                        continue
                    haut_j, bas_j = (hi[xj], lo[xj]) if aj == 1 else (-lo[xj], None if hi[xj] is None else -hi[xj])
                    if haut_j is None:
                        max_infini = True
                    else:
                        somme_max += haut_j
                    if bas_j is None:
                        min_infini = True
                    else:
                        somme_min += bas_j
                haut_t = None if min_infini else second - somme_min                        # a_k x_k <= second - somme des plus petits des autres
                bas_t = None if (sorte != "eq" or max_infini) else second - somme_max      # égalité : a_k x_k >= second - somme des plus grands
                if ak == 1:
                    nouveau_lo, nouveau_hi = bas_t, haut_t
                else:
                    nouveau_lo = None if haut_t is None else -haut_t
                    nouveau_hi = None if bas_t is None else -bas_t
                if nouveau_lo is not None and nouveau_lo > lo[xk]:
                    lo[xk], change = nouveau_lo, True
                if nouveau_hi is not None and (hi[xk] is None or nouveau_hi < hi[xk]):
                    hi[xk], change = nouveau_hi, True
                if lo[xk] > borne_m or (hi[xk] is not None and hi[xk] > borne_m):
                    raise MasquageInstable(f"propagation : une borne finie dépasse M = {borne_m}")
                if hi[xk] is not None and lo[xk] > hi[xk]:
                    return lo, hi, True
        if not change:
            return lo, hi, False
    raise MasquageInstable(f"propagation : pas de balayage stable en {limite} balayages")


class _UnitePhoto:
    """Unité de propagation de la photo (D15) : toute la vue `v_version_quality_photo` (chaque semaine retenue, équipe, ligne sans équipe et produit).
    Variables : chaque cellule de comptage, plus les termes latents D_r, m_r et U_r de chaque ligne sans version qui a des lignes de version (P2), et
    le terme latent D_t des lignes sans version d'une semaine où P5 est construite qui n'ont pas de D_r.
    Relations : P1 (paires), P2 (ligne à compléter), P3 (chaîne de D5-d), P4 (ligne du produit, D3), P5 (défauts distincts du produit, redondante). Les relations de partage, de retard et de noms
    (S1 à S3, L1 à L3, N1) viennent avec le groupe 7 sur le même moteur."""

    def __init__(self, noms, rangees, seuil, vis, regle, versions, libres, groupes, produits, cacher):
        self.noms, self.rangees, self.seuil, self.vis, self.regle = noms, rangees, seuil, vis, regle
        self.versions, self.libres, self.groupes, self.produits, self.cacher = versions, libres, groupes, produits, cacher
        self.largeurs: dict = {}

    def _cle_ligne(self, i: int) -> tuple:
        r = self.rangees[i]
        return (1 if r["team"] == PRODUIT else 0, str(r.get("week_start")), r["team"], -1 if r.get("version_no") is None else r["version_no"])

    def _cellules(self) -> list:
        return [(i, col) for i, r in enumerate(self.rangees) if r.get("team") is not None for col in self.vis[i] if col in self.noms]

    def _construire(self) -> dict:
        t, vis, rangees = self.seuil, self.vis, self.rangees
        definitions = [((*self._cle_ligne(i), COMPTES_PHOTO.index(col)), ("c", i, col)) for i, col in self._cellules()]
        presentes = set(self._cellules())
        for i, r in enumerate(rangees):                    # termes latents des lignes sans version : D_r puis m_r, après les cellules de leur ligne
            if r.get("team") is not None and r.get("version_no") is None and self.versions.get((r.get("week_start"), r["team"])) \
                    and (i, "defects_created") in presentes:
                definitions += [((*self._cle_ligne(i), 100), ("D", i)), ((*self._cle_ligne(i), 101), ("m", i)),
                                ((*self._cle_ligne(i), 102), ("U", i))]       # U : terme latent des versions non retenues (D4 (d), M1 a), sans borne haute
        avec_d = {definition[1] for _, definition in definitions if definition[0] == "D"}
        # P5 (R-20261104-49, Q1 e) : par semaine, ligne sans version du produit dont chaque ligne d'équipe de P4 a ses deux cellules (créés, sans affects) ;
        # chaque ligne de la semaine sans D_r reçoit un D_t latent (rang de colonne 100, comme D_r), sans borne haute
        p5_semaines = []
        for p in self.produits:
            if rangees[p].get("version_no") is not None:
                continue
            equipes = self.groupes[(rangees[p].get("week_start"), None)]
            lignes = [*equipes, p]
            if equipes and all((i, "defects_created") in presentes and (i, "defects_without_affects") in presentes for i in lignes):
                p5_semaines.append((p, equipes))
                definitions += [((*self._cle_ligne(i), 100), ("Dt", i)) for i in lignes if i not in avec_d]
        definitions.sort(key=lambda d: d[0])
        indice = {d[1]: v for v, d in enumerate(definitions)}
        n = len(definitions)
        cles = [d[0] for d in definitions]
        cellule, publiee, valeur, lo, hi = [False] * n, [False] * n, [None] * n, [0] * n, [None] * n
        for v, (_, definition) in enumerate(definitions):
            if definition[0] != "c":
                continue
            _, i, col = definition
            cellule[v] = True
            if vis[i][col]:
                publiee[v], valeur[v] = True, rangees[i][col]
                lo[v] = hi[v] = valeur[v]
                continue
            raison = self.regle.get((i, col), ("inconnue",))
            if raison[0] == "primaire":
                hi[v] = t - 1
            elif raison[0] == "paire":                    # la partie ne dépasse pas le tout publié ; sinon P1 la borne
                tout = raison[1]
                hi[v] = max(t - 1, rangees[i][tout]) if vis[i].get(tout) else None
            elif raison[0] == "d15":                      # voisine seule candidate (B15, R-20261104-49 Q2 a) : borne enregistrée None, pas de borne haute
                hi[v] = None if raison[1] is None else max(t - 1, raison[1])
            # inconnue, D3, D5-d (P3), D2 et D5-e : pas de borne haute
        p1, p2, p3, p4, p5 = [], [], [], [], []
        avec_p2 = set()                                    # lignes dont D_r a la première équation de P2 (D_r = créés - sans affects)
        termes_de: dict = {}                             # variable m -> nombre de termes retenus de sa ligne (écart 3 de M5)
        for i, r in enumerate(rangees):
            if r.get("team") is None:
                continue
            for partie, tout in PAIRES_PHOTO.items():
                if (("c", i, partie) in indice) and (("c", i, tout) in indice):
                    p1.append(("le", 0, tuple(sorted(((indice[("c", i, partie)], 1), (indice[("c", i, tout)], -1))))))      # termes dans l'ordre des clés
            if ("D", i) in indice and ("c", i, "defects_without_affects") in indice:
                d, m, libre_u = indice[("D", i)], indice[("m", i)], indice[("U", i)]
                crees, sans = indice[("c", i, "defects_created")], indice[("c", i, "defects_without_affects")]
                trouves = [indice[("c", j, "found")] for j in sorted(self.versions[(r.get("week_start"), r["team"])], key=self._cle_ligne)
                           if ("c", j, "found") in indice]
                if trouves:
                    avec_p2.add(i)
                    p2.append(("eq", 0, tuple(sorted(((crees, 1), (sans, -1), (d, -1))))))
                    p2.append(("eq", 0, tuple(sorted(((d, 1), (m, 1), (libre_u, -1), *((f, -1) for f in trouves))))))      # D + m = trouvés retenus + U
                    termes_de[m] = len(trouves)
                    p2.extend(("le", 0, tuple(sorted(((f, 1), (d, -1))))) for f in trouves)
        for (i, col), raison in self.regle.items():
            if raison[0] == "d5d" and not vis[i][col] and raison[1] is not None and ("c", i, col) in indice and ("c", raison[1], col) in indice:
                p3.append(("le", t - 1, tuple(sorted(((indice[("c", i, col)], 1), (indice[("c", raison[1], col)], -1))))))
        for p in self.produits:
            r = rangees[p]
            equipes = self.groupes[(r.get("week_start"), r.get("version_no"))]
            for col in vis[p]:
                termes = [indice[("c", e, col)] for e in equipes if ("c", e, col) in indice]
                if ("c", p, col) in indice and termes:
                    p4.append(("eq", 0, tuple(sorted(((indice[("c", p, col)], 1), *((e, -1) for e in termes))))))
        for p, equipes in p5_semaines:                     # P5 : D_P = somme des D_t ; D_t = créés - sans affects pour une ligne sans la première équation de P2
            def d_de(i):
                return indice[("D", i)] if ("D", i) in indice else indice[("Dt", i)]
            for i in (*equipes, p):
                if i not in avec_p2:
                    crees, sans = indice[("c", i, "defects_created")], indice[("c", i, "defects_without_affects")]
                    p5.append((("eq", 0, tuple(sorted(((crees, 1), (sans, -1), (d_de(i), -1))))), False))
            p5.append((("eq", 0, tuple(sorted(((d_de(p), 1), *((d_de(e), -1) for e in equipes))))), True))
        relations = [sorted(groupe, key=lambda rel: (rel[2][0][0], rel[2], rel[1])) for groupe in (p1, p2, p3, p4)]
        p5 = sorted(p5, key=lambda e: (e[0][2][0][0], e[0][2], e[0][1]))
        toutes = [rel for groupe in relations for rel in groupe] + [e[0] for e in p5]
        hors_anneau = [False] * (len(toutes) - len(p5)) + [e[1] for e in p5]      # la relation P5 des sommes n'est pas traversée par la règle du voisin
        return {"n": n, "cle": cles, "definition": [d[1] for d in definitions], "cellule": cellule, "publiee": publiee, "valeur": valeur,
                "lo": lo, "hi": hi, "relations": toutes, "hors_anneau": hors_anneau,
                "latents_m": [v for v, d in enumerate(definitions) if d[1][0] == "m"], "termes_de": termes_de,
                "latent_u": {v: indice[("U", d[1][1])] for v, d in enumerate(definitions) if d[1][0] == "m"}}

    def _epingles(self, u: dict, balayages: int | None) -> tuple:
        """Propage les quatre lectures de l'excès (décision 14 : « m libre », « m = 0 », « U = 0 » et « U = 0 et m = 0 »), la plus stricte décide. Renvoie (première variable épinglée
        dans l'ordre des clés, ou None ; largeur de chaque cellule masquée dans la lecture la plus étroite non écartée)."""
        t = self.seuil
        n = u["n"]
        borne_m = (sum(v for v, p in zip(u["valeur"], u["publiee"]) if p) + t) * (n + 1)
        limite = balayages if balayages is not None else propagation_max(n, borne_m)
        lo, hi, vide = _propager(u["lo"], u["hi"], u["relations"], borne_m, limite)
        if vide:                                            # la lecture « m libre » n'est jamais écartée : un intervalle vide est une erreur
            raise MasquageInstable(f"{VUE_PHOTO} : la propagation donne un intervalle vide dans la lecture où m est libre")
        lectures = [(lo, hi)]
        exces = []                                          # excès m_r fixé sous T dans la lecture « U_r = 0 » de sa ligne (D15, étape 4 ; D5-e, X10)
        for m in u["latents_m"]:                            # par ligne (M2 a, M7 a) : « m_r = 0 », « U_r = 0 » et « U_r = 0 et m_r = 0 », les autres lignes libres
            libre_u = u["latent_u"][m]
            for fixes in ([m], [libre_u], [m, libre_u]):
                if any(lo[x] != 0 for x in fixes):          # le pari est déjà contredit par la lecture libre : lecture vide, écartée
                    continue
                lo0, hi0 = list(u["lo"]), list(u["hi"])
                for x in fixes:
                    lo0[x] = hi0[x] = 0
                # une limite atteinte (PROPAGATION-ZERO-MAX) ou une borne au-dessus de M : MasquageInstable, échec fermé, rien n'est publié (M2 a, M7 a) ;
                # seul un intervalle vide écarte la lecture de cette ligne (le pari est contredit par les cellules publiées)
                lo2, hi2, vide2 = _propager(lo0, hi0, u["relations"], borne_m, min(limite, propagation_zero_max(n, len(u["relations"]))))
                if not vide2:
                    lectures.append((lo2, hi2))
                    # l'excès n'est contrôlé que dans « U = 0 » (ni « m = 0 » ni « U = 0 et m = 0 », où m = 0 est le pari) ; exemption : un seul terme retenu
                    if fixes == [libre_u] and hi2[m] is not None and lo2[m] == hi2[m] and lo2[m] < t and u["termes_de"].get(m, 0) != 1:
                        exces.append(m)
        epingles = []
        largeurs = {}
        for v in range(n):
            if u["cellule"][v] and not u["publiee"][v]:
                if any(h[v] is not None and b[v] == h[v] for b, h in lectures):
                    epingles.append(v)
                finies = [h[v] - b[v] for b, h in lectures if h[v] is not None]
                _, i, col = u["definition"][v]
                largeurs[(i, col)] = min(finies) if finies else None
        epingles.extend(exces)
        return (min(epingles) if epingles else None), largeurs

    def _voisine(self, u: dict, x: int) -> tuple[int, int | None]:
        """Règle du voisin (« la cellule qui ferme le moins d'information ») : parmi les cellules publiées qui figurent dans une relation avec x,
        la plus petite valeur, à égalité la première de l'ordre des clés ; sans candidate, les cellules publiées des relations des cellules masquées
        qui partagent une relation avec x, anneau après anneau. Les termes latents sont transparents et la relation P5 des sommes n'est pas traversée
        (anneaux : P1 à P4 et créés - sans affects - D_t = 0 seulement ; R-20261104-49, revue 19.1 C2). Renvoie (voisine, borne haute de départ de la
        cellule masquée : le plus grand de seuil - 1 et de la plus petite valeur des autres candidates ; None, sans borne haute, quand la voisine était
        la seule candidate : B15, R-20261104-49 Q2 a)."""
        hors_anneau = u.get("hors_anneau") or [False] * len(u["relations"])
        ensembles = [{v for v, _ in termes} for (_, _, termes), hors in zip(u["relations"], hors_anneau) if not hors]
        vus, front = {x}, {x}
        while front:
            anneau, pile = set(), list(front)
            while pile:                                     # un terme latent (D_r, m_r) est transparent : ses relations comptent pour l'anneau de x
                v = pile.pop()
                for ensemble in ensembles:
                    if v in ensemble:
                        for w in ensemble:
                            if w not in vus and w not in front and w not in anneau:
                                anneau.add(w)
                                if not u["cellule"][w]:
                                    pile.append(w)
            candidates = {w for w in anneau if u["cellule"][w] and u["publiee"][w]}
            suivant = anneau - candidates
            if candidates:
                y = min(candidates, key=lambda w: (u["valeur"][w], w))
                autres = [u["valeur"][w] for w in candidates if w != y]
                return y, (max(self.seuil - 1, min(autres)) if autres else None)
            vus |= suivant
            front = suivant
        raise MasquageInstable(f"{VUE_PHOTO} : une cellule épinglée sans cellule publiée à masquer")

    def propager(self, regles, limites: dict) -> None:
        """Boucle de D15 : une cellule masquée qui n'a plus qu'une valeur possible masque sa voisine, et tout l'ordre repart (`regles`), jusqu'à ce
        qu'aucune cellule masquée ne soit épinglée. Limite de la boucle : LOOP-MAX = C + 1 ; atteinte : MasquageInstable, rien n'est publié."""
        publiees = sum(1 for i, col in self._cellules() if self.vis[i][col])
        limite = limites["boucle"] if limites.get("boucle") is not None else boucle_max(publiees)
        for _ in range(limite):
            u = self._construire()
            epingle, self.largeurs = self._epingles(u, limites.get("balayages"))
            if epingle is None:
                return
            y, haut = self._voisine(u, epingle)
            _, i, col = u["definition"][y]
            self.cacher(i, col, ("d15", haut))
            regles()
        raise MasquageInstable(f"{VUE_PHOTO} : la propagation des bornes ne se stabilise pas en {limite} passes")


def _masque_photo(noms, rangees, seuil, applic, vis, largeurs: dict | None = None, limites: dict | None = None) -> None:
    """Vue de la photo : primaire et paires (D11), semaines retenues (D5-d), ligne à compléter et défauts à plusieurs affects versions (D2, D5-e),
    ligne du produit (D3), propagation des bornes sur toute l'unité (D15), parts. `largeurs` (sortie, facultative) reçoit la largeur de chaque
    cellule masquée, (rang, colonne) -> largeur après propagation (None : sans borne haute) ; `limites` (entrée, facultative) abaisse les
    limites déclarées, pour les tests : clés « balayages » et « boucle »."""
    versions = defaultdict(list)          # (semaine, équipe) -> rangs des lignes par version
    libres = defaultdict(list)            # équipe -> rangs des lignes sans version
    groupes = defaultdict(list)           # (semaine, version) -> rangs des lignes d'équipe
    produits = []
    regle: dict = {}                      # (rang, colonne) -> première règle qui a masqué la cellule (D15, B15) ; jamais publiée
    for i, r in enumerate(rangees):
        if r.get("team") is None:                          # ligne de couverture : aucune cellule applicable
            ap: tuple = ()
        elif r.get("version_no") is not None:              # ligne d'équipe ou de produit pour une version : les cinq comptes de version
            ap = COMPTES_PHOTO[:5]
        else:                                              # ligne sans version : les quatre comptes libres et les deux parts
            ap = COMPTES_PHOTO[5:]
        applic[i] = set(ap) | (set(PARTS_PHOTO) if ap and r.get("version_no") is None else set())
        vis[i] = {c: _compte_photo_visible(r, c, seuil) for c in ap}
        for c in ap:                                       # règle enregistrée : primaire, paire ou inconnue (un nul de la vue)
            if not vis[i][c]:
                valeur = r.get(c)
                regle[(i, c)] = ("inconnue",) if valeur is None else (("primaire",) if valeur < seuil else ("paire", PAIRES_PHOTO[c]))
        if r.get("team") is None:
            continue
        if r.get("team") == PRODUIT:
            produits.append(i)
        else:
            groupes[(r.get("week_start"), r.get("version_no"))].append(i)
        if r.get("version_no") is None:
            libres[r["team"]].append(i)
        else:
            versions[(r.get("week_start"), r["team"])].append(i)

    def cacher(i: int, col: str, raison: tuple) -> None:
        """Masque une cellule encore publiée et enregistre la règle qui l'a masquée (la première, B15) ; sans effet sur une cellule déjà masquée."""
        if vis[i][col]:
            vis[i][col] = False
            regle[(i, col)] = raison

    def chainer(lignes: list) -> None:
        """D5-d : semaines retenues d'une ligne (équipe ou produit), du plus ancien au plus récent, sur les seules cellules encore publiées."""
        ordonnees = sorted(lignes, key=lambda i: str(rangees[i].get("week_start")))
        for col in ("defects_created", "defects_without_affects"):
            dernier = None
            ancre = None
            for i in ordonnees:
                if not vis[i][col]:
                    continue
                valeur = rangees[i][col]
                if dernier is not None and 1 <= abs(valeur - dernier) <= seuil - 1:
                    cacher(i, col, ("d5d", ancre))             # P3 : la cellule se compare à son ancre (la dernière cellule publiée d'une semaine antérieure)
                else:
                    dernier, ancre = valeur, i

    def completer(i: int) -> None:
        """Créés = sans affects + défauts distincts avec affects ; la somme des trouvés par version dépasse ces défauts de m (défauts à plusieurs
        affects versions), terme caché. Sans terme caché, m est lu par différence : il doit être d'au moins le seuil (D5-e, zéro compris). Termes
        cachés : au moins deux, de somme S d'au moins le seuil et différente de la somme des bornes basses et de la somme des bornes hautes de
        BORNES (B1 : S = Σhi pinglerait chaque terme). La somme S est celle que les valeurs publiées donnent. Écart D4 (d) rétabli (R-20261106-22, qui
        remplace R-20261105-6 Q4 (a)) : une ligne sans aucune ligne de version retenue cette semaine-là (équipe ou produit) est lue comme flow.photo_serie
        de 0022 la lisait, k = 0 terme caché et somme des visibles nulle, donc un excès créés - sans affects - 0 sous le seuil : sans affects est masqué,
        puis créés à la passe suivante. Même règle dans la migration qui remplace flow.photo_masque après 0035 (le garde-fou nterms de 0035 en moins)."""
        r = rangees[i]
        crees, sans = r.get("defects_created"), r.get("defects_without_affects")
        termes = versions.get((r.get("week_start"), r["team"]), [])
        if crees is None or not vis[i]["defects_created"]:
            return                                          # un nul de la vue est déjà tranché par la vue
        vus = [rangees[j]["found"] for j in termes if vis[j]["found"]]
        visibles, k = sum(vus), len(termes) - len(vus)
        bas_t, haut_t = _borne(VUE_PHOTO, "found")[0], _haut(VUE_PHOTO, "found", seuil, vus)
        if vis[i]["defects_without_affects"]:
            if k == 0:
                echec = visibles - (crees - sans) < seuil
            else:
                somme = max(0, crees - sans - visibles)
                echec = k < 2 or somme < seuil or somme == k * bas_t or somme == k * haut_t
            if echec:
                cacher(i, "defects_without_affects", ("d2",))
        else:
            n, somme = 1 + k, crees - visibles
            bas_s, haut_s = _borne(VUE_PHOTO, "defects_without_affects")[0], _haut(VUE_PHOTO, "defects_without_affects", seuil, [])
            if n < 2 or somme < seuil or somme == bas_s + k * bas_t or somme == haut_s + k * haut_t:
                cacher(i, "defects_created", ("d2",))

    def boucle(lignes: list) -> None:
        """Une série (une équipe, ou le produit après D3) : D5-d sur les seules cellules encore publiées, puis D2 sur chaque semaine, repassés jusqu'à
        ce qu'une passe ne masque plus rien (décision du 2026-10-27 : une cellule masquée par D5-e, D5-d ou une passe précédente change la relation
        ou la chaîne, une cellule restée seule cachée se lirait par différence). Les passes_max(W) = 2 x W + 1 passes qui masquent toutes encore
        une cellule : MasquageInstable, rien n'est publié (la même limite que la fonction flow.photo_serie)."""
        limite = passes_max(len(lignes))
        for _ in range(limite):
            avant = [(vis[i]["defects_created"], vis[i]["defects_without_affects"]) for i in lignes]
            chainer(lignes)
            for i in sorted(lignes, key=lambda j: str(rangees[j].get("week_start"))):
                completer(i)
            if [(vis[i]["defects_created"], vis[i]["defects_without_affects"]) for i in lignes] == avant:
                return
        raise MasquageInstable(f"{VUE_PHOTO} : le masquage de la ligne sans version ne se stabilise pas en {limite} passes")

    def regles() -> None:
        """Les règles existantes dans leur ordre (D13) : les séries d'équipe jusqu'à leur point fixe, D3, puis la série du produit."""
        for equipe, lignes in libres.items():              # les lignes d'équipe d'abord, chacune jusqu'à son point fixe
            if equipe != PRODUIT:
                boucle(lignes)
        for p in produits:                                  # D3 : toutes les cellules d'équipe de la colonne, ou aucune
            r = rangees[p]
            for col in list(vis[p]):
                if not all(vis[t][col] for t in groupes[(r.get("week_start"), r.get("version_no"))]):
                    cacher(p, col, ("d3",))
        if PRODUIT in libres:                               # puis la série du produit après D3 : seules les cellules encore publiées s'enchaînent (M2 c)
            boucle(libres[PRODUIT])

    regles()
    unite = _UnitePhoto(noms, rangees, seuil, vis, regle, versions, libres, groupes, produits, cacher)
    unite.propager(regles, limites or {})
    if largeurs is not None:
        largeurs.update(unite.largeurs)
    for i, r in enumerate(rangees):                         # parts : masquées avec leur partie ou leur tout
        if r.get("team") is not None and r.get("version_no") is None:
            for col, (partie, tout) in PARTS_PHOTO.items():
                vis[i][col] = r.get(col) is not None and vis[i].get(partie, False) and vis[i].get(tout, False)


def _genre(vue, noms) -> str:
    if vue == VUE_PHOTO or (vue is None and est_vue_photo(noms)):
        return "photo"
    if vue == VUE_RETARD or (vue is None and est_vue_retard(noms)):
        return "retard"
    if vue == VUE_PART or (vue is None and est_vue_part(noms)):
        return "part"
    if vue == VUE_FLUX or (vue is None and est_vue_flux(noms)):
        return "flux"
    if vue == VUE_COUVERTURE or (vue is None and est_vue_couverture(noms)):
        return "couverture"
    return "simple"


SERIE_DEBIT = ("throughput", "items_lt", "items_ct", "items_without_commitment", "items_old")      # n, m, c, g (= n - c), o


# ---------------------------------------------------------------------------------------------------------------------------------------
# Relation T3 (change masking-sums, D17, R-20261031-07) : débit trimestriel = somme des cellules hebdomadaires Story et Task des semaines du trimestre.
# Règle (a) : débit masqué, aucune ligne Story ni Task de l'équipe sur une semaine qui touche le trimestre. Règle (b) : débit visible, les lignes
# masquées ne sont publiées que si le reste ne fixe rien ; sinon le débit est masqué, puis la règle (a) s'applique.
# Même règle en SQL (migration de flow.v_t3_withheld) et en TypeScript (mothra/contract/src/masquage.ts) : les deux lignes T3 ci-dessous sont
# identiques dans les trois fichiers (un test les compare). Tombe avec la propagation de D15 quand le groupe 7 déclare T3 (tâche 7.6).
# ---------------------------------------------------------------------------------------------------------------------------------------
# T3-READINGS: the two weeks straddling a quarter limit are each counted in the quarter or not (four readings); a reading whose S is outside [k * lo, k * hi] is dropped as inconsistent; the rows are published only when every reading left passes.
# T3-CONDITIONS: publish only when k >= 2 and S >= T and S != k * lo and S != k * hi, with S = n - the visible weekly cells, k the masked rows, lo and hi from BORNES.
TYPES_DEBIT = ("story", "task")        # ST de D16 : les types dont les lignes hebdomadaires font le débit


def _jour(valeur) -> date:
    """Une date de vue (objet date) ou son texte ISO."""
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    return date.fromisoformat(str(valeur)[:10])


def _jour_ou_none(valeur) -> date | None:
    """_jour, ou None quand la date manque ou n'est pas lisible."""
    if valeur is None:
        return None
    try:
        return _jour(valeur)
    except (ValueError, TypeError):
        return None


def _debut_suivant(debut: date) -> date:
    """Début du trimestre civil qui suit celui qui commence à `debut`."""
    mois = debut.month + 3
    return date(debut.year + (mois - 1) // 12, (mois - 1) % 12 + 1, 1)


def _semaine_touche(semaine: date, debut: date) -> bool:
    """Vrai si la semaine (lundi `semaine`) touche le trimestre qui commence à `debut`."""
    return semaine + timedelta(days=7) > debut and semaine < _debut_suivant(debut)


def _t3_lectures_passent(n: int, rangs: list, seuil: int) -> bool:
    """Règle (b) pour un débit visible `n` : `rangs` = [(position, valeur publiée ou None)] des lignes Story et Task de l'équipe dont la semaine
    touche le trimestre, la position étant « in » (semaine dans le trimestre), « start » ou « end » (semaine qui chevauche une limite). Quatre
    lectures des deux semaines qui chevauchent ; une lecture sans ligne masquée n'a rien à cacher ; une lecture dont S sort de [k x lo, k x hi]
    est écartée. Vrai si toute lecture restante passe les quatre conditions."""
    lo, _ = _borne(VUE_HEBDO, "tickets")
    hi = _haut(VUE_HEBDO, "tickets", seuil, [])
    for avec_debut in (False, True):
        for avec_fin in (False, True):
            retenues = [v for position, v in rangs if position == "in" or (position == "start" and avec_debut) or (position == "end" and avec_fin)]
            visibles = [v for v in retenues if _visible(v, seuil)]
            k = len(retenues) - len(visibles)
            s = n - sum(visibles)
            if k == 0 or not k * lo <= s <= k * hi:
                continue
            if not (k >= 2 and s >= seuil and s != k * lo and s != k * hi):
                return False
    return True


def _t3_retires(debit: tuple, hebdo: tuple, seuil: int) -> set:
    """Les (équipe, début de trimestre) dont les lignes Story et Task sont retirées (règle (a)) : le débit du trimestre est masqué (nul de la vue,
    sous le seuil) ou la règle (b) échoue. `debit` et `hebdo` : (noms, lignes) de v_team_lead_time_throughput et de v_team_weekly_resolved,
    telles que la vue les publie (un nul est une cellule masquée). Sans colonne period, rien n'est lu (les cellules du débit sont alors toutes masquées)."""
    noms_d, lignes_d = debit
    noms_h, lignes_h = hebdo
    if "period" not in noms_d:
        return set()
    lisible = all(c in noms_h for c in ("team", "type", "week_start", "tickets"))      # revue de T3, 1 : sans la vue hebdomadaire lisible, le débit est masqué
    semaines = defaultdict(list)                       # équipe -> [(lundi de la semaine, valeur publiée)]
    illisibles = set()                                 # équipes dont une ligne Story ou Task n'a pas de date lisible : leurs débits sont masqués
    for ligne in lignes_h if lisible else []:
        r = dict(zip(noms_h, ligne))
        if str(r.get("type")).lower() in TYPES_DEBIT:
            semaine = _jour_ou_none(r.get("week_start"))
            if semaine is None:
                illisibles.add(r.get("team"))
            else:
                semaines[r.get("team")].append((semaine, r.get("tickets")))
    retires = set()
    for ligne in lignes_d:
        r = dict(zip(noms_d, ligne))
        if r.get("period") == "pooled_year":
            continue
        equipe, debut, n = r.get("team"), _jour_ou_none(r.get("quarter_start")), r.get("throughput")
        if debut is None or not _visible(n, seuil) or not lisible or equipe in illisibles:
            retires.add((equipe, debut))                # date du trimestre illisible : la clé (équipe, None) masque la ligne
            continue
        fin = _debut_suivant(debut)
        rangs = []
        for semaine, valeur in semaines.get(equipe, []):
            if not _semaine_touche(semaine, debut):
                continue
            position = "start" if semaine < debut else "end" if semaine + timedelta(days=7) > fin else "in"
            rangs.append((position, valeur))
        if not _t3_lectures_passent(n, rangs, seuil):
            retires.add((equipe, debut))
    return retires


def _t3_retires_monotone(debit: tuple, hebdo: tuple, seuil: int) -> set:
    """Monotonie de la relation T3 en le seuil (audit #629, A-78 / L3-07 ; R-20261107-29, point 8) : la règle (b) seule n'est pas monotone (au plancher
    le reste fixe un compte et le débit est retiré, à un seuil plus haut le même reste ne fixe rien). Un trimestre retiré à un seuil quelconque entre le
    plancher et le seuil effectif reste retiré au seuil effectif. Au-delà du plus grand débit aucun trimestre n'est jugé : la boucle s'y arrête.
    Copie de `retiresT3Monotone` du masquage du contrat de Mothra (masquage.ts). La vue flow.v_t3_withheld (0030) est la première évaluation de cette union, celle
    du plancher : les seuils plus hauts ne sont appliqués qu'ici et dans Mothra, jamais dans la base, donc aucune migration.
    Remplace : l'évaluation unique de `_t3_retires` au seuil effectif. Retrait : avec la règle (b) rendue monotone d'elle-même."""
    noms_d, lignes_d = debit
    plus_grand = PLANCHER
    if "throughput" in noms_d:
        for ligne in lignes_d:
            n = dict(zip(noms_d, ligne)).get("throughput")
            if isinstance(n, int) and not isinstance(n, bool) and n > plus_grand:
                plus_grand = n
    retires = set()
    for s in range(PLANCHER, min(seuil, plus_grand) + 1):
        retires |= _t3_retires(debit, hebdo, s)
    if seuil > plus_grand:
        retires |= _t3_retires(debit, hebdo, seuil)
    return retires


def _lignes_retirees(vue, noms, lignes, seuil, liees) -> set:
    """Rangs des lignes de v_team_weekly_resolved que la règle (a) retire. Sans la vue du débit parmi les vues liées, rien n'est retiré."""
    if vue != VUE_HEBDO or VUE_DEBIT not in (liees or {}) or any(c not in noms for c in ("team", "type", "week_start")):
        return set()
    retires = _t3_retires_monotone(liees[VUE_DEBIT], (noms, lignes), seuil)
    if not retires:
        return set()
    sortie = set()
    for i, ligne in enumerate(lignes):
        r = dict(zip(noms, ligne))
        if str(r.get("type")).lower() not in TYPES_DEBIT:
            continue
        semaine = _jour_ou_none(r.get("week_start"))
        if any(equipe == r.get("team") and (semaine is None or debut is None or _semaine_touche(semaine, debut)) for equipe, debut in retires):
            sortie.add(i)       # une date illisible, de la ligne ou du trimestre, ne permet pas de dire que la ligne est hors du trimestre : retirée
    return sortie


def lignes_publiees(vue, noms: list[str], lignes: list[tuple], seuil: int, liees: dict | None = None) -> list[tuple]:
    """Les lignes d'une vue que la relation T3 laisse publier (masking-sums D17, règle (a)), dans l'ordre : pour v_team_weekly_resolved, sans les
    lignes Story et Task d'une équipe et d'un trimestre dont le débit est masqué ; toute autre vue, ou sans la vue du débit parmi `liees`, est rendue
    telle quelle. À appeler avant masquer_vue (qui masque de toute façon les cellules de ces lignes si l'appelant l'oublie)."""
    retirees = _lignes_retirees(vue, noms, lignes, seuil, liees)
    return [ligne for i, ligne in enumerate(lignes) if i not in retirees]


def _masque_debit(noms, rangees, seuil, vis, retires=frozenset()) -> None:
    """Règle des paires et règle de série de v_team_lead_time_throughput appliquées au seuil (revue 15.2, constats 1 et 2) : la migration 0026 ne
    les tient qu'à 5. Valeurs publiées seulement : un nul de la vue est une valeur inconnue (cellule masquée). Jamais moins strict que le masquage
    de chaque compte seul.
      * m (items_lt) : visible si n l'est et que n - m vaut 0 ou au moins le seuil ;
      * c (items_ct) : visible si n l'est, que g = n - c vaut 0 ou au moins le seuil et que |m - c| vaut 0 ou au moins le seuil quand m est visible ;
      * g (items_without_commitment) : visible s'il atteint le seuil, que n l'est et que c l'est ; quand c est nul dans la vue (c valait 0, que la base
        masque), g n'est visible que s'il égale n. Son zéro reste masqué : plus strict que la base (mask_count_zero), qui le montre ;
      * o (items_old) : visible si c l'est et que o vaut 0 (R-20261106-39 : le zéro est montré) ou que c - o vaut 0 ou au moins le seuil et o atteint
        le seuil ; la borne basse d'un o masqué dont c est visible est 1 (LO_ANCIENS_SI_CT_MONTRE) ;
      * ligne « pooled_year » : les mêmes règles, et un compte de l'année n'est visible que si aucune cellule de sa série n'est masquée sur les
        trimestres de la même équipe (un trimestre masqué se lirait par différence ; fuite_serie de la migration, appliquée plus largement)."""
    def atteint(v):
        return v is not None and v >= seuil

    def ecart_ok(d):
        return d == 0 or d >= seuil

    def retiree(r) -> bool:             # relation T3 (D17) : le débit de ce trimestre est masqué par la règle (b), ou par la règle (a) qui le suit
        return bool(retires) and r.get("period") != "pooled_year" and (r.get("team"), _jour_ou_none(r.get("quarter_start"))) in retires

    def drapeaux(r, f):
        n, m, c, g, o = (r.get(k) for k in SERIE_DEBIT)
        dn = atteint(n) and not f["n"] and not retiree(r)
        dm = atteint(m) and dn and not f["m"] and ecart_ok(abs(n - m))
        dc = atteint(c) and dn and not f["c"] and not f["g"] and ecart_ok(abs(n - c)) and (not dm or ecart_ok(abs(m - c)))
        dg = atteint(g) and dn and not f["g"] and (dc or (c is None and g == n))
        # R-20261106-39 : un zéro d'items_old est montré quand items_ct l'est (l'année à 0 seulement si aucun trimestre de sa série n'est masqué : f["o"]) ;
        # le reste est la règle d'avant, série comprise. Remplace le masquage du zéro de items_old ; retrait permanent tant que la vue publie items_old.
        do = dc and not f["o"] and (o == 0 or (atteint(o) and ecart_ok(abs(c - o))))
        return {"n": dn, "m": dm, "c": dc, "g": dg, "o": do}

    aucun = {k: False for k in "nmcgo"}                          # sert de drapeaux de série vides ET de résultat « tout masqué »
    if "period" not in noms:          # fail-closed : sans colonne period, une année ne se distingue pas d'un trimestre
        for i in range(len(rangees)):
            for colonne in SERIE_DEBIT:
                if colonne in noms:
                    vis[i][colonne] = False
        return
    serie_masquee = defaultdict(lambda: dict(aucun))             # équipe -> série -> une cellule trimestrielle est masquée
    resultats = []
    equipes_avec_trimestres = {r.get("team") for r in rangees if r.get("period") != "pooled_year"}
    for r in rangees:
        if r.get("period") == "pooled_year":
            resultats.append(None)
            continue
        d = drapeaux(r, aucun)
        resultats.append(d)
        zero_deductible = r.get("items_without_commitment") == 0 and d["c"]          # g = 0 se lit sur n et c visibles : pas une fuite
        for k, visible in d.items():
            if not visible and not (k == "g" and zero_deductible):
                serie_masquee[r.get("team")][k] = True
    for i, r in enumerate(rangees):
        if resultats[i] is None and r.get("team") not in equipes_avec_trimestres:      # année sans les trimestres de sa série : tout masqué
            d = aucun
        else:
            d = resultats[i] or drapeaux(r, serie_masquee[r.get("team")])
        for k, colonne in zip("nmcgo", SERIE_DEBIT):
            if colonne in noms:
                vis[i][colonne] = d[k]


def masquer_vue(vue, noms: list[str], lignes: list[tuple], seuil: int, liees: dict | None = None) -> list[dict]:
    """Cellules structurées d'une vue au seuil (change masking-sums, D4 ; fonction pure des données publiées, jamais d'une cellule brute).
    Une cellule : {"value": v}, ou, pour un compte ou une part masqué, {"value": None, "masked": "under_threshold", "threshold": seuil} : une
    seule raison, jamais la règle (D11). Une cellule sans objet pour la sorte de ligne (photo) est {"value": None} sans masque. Un nul de la vue
    est une cellule cachée. Appliquée aux comptes bruts au plancher, elle redonne la vue (à une exception, plus stricte : le zéro de
    items_without_commitment, que la base montre par mask_count_zero, reste masqué ici) ; appliquée à une vue à un seuil relevé, elle ne montre
    jamais une cellule que la vue masque. `liees` : nom de vue -> (noms, lignes), les autres vues que lisent les règles entre vues D5-a et D5-b
    (v_teams : v_team_status et v_team_jira_ids ; v_team_jira_ids : v_teams) et D5-c (le retard : la part). `vue` peut être None : la sorte de
    vue est alors déduite des colonnes."""
    if vue is not None and vue not in VUES:
        raise ValueError(vue)
    liees = liees or {}
    rangees = [dict(zip(noms, ligne)) for ligne in lignes]
    genre = _genre(vue, noms)
    applic = [set() for _ in rangees]
    vis = [{} for _ in rangees]
    forcees = [set() for _ in rangees]                      # statistiques et parts de la tranche 1 masquées avec leur effectif
    if genre == "photo":
        _masque_photo(noms, rangees, seuil, applic, vis)
    elif genre == "retard":
        _masque_retard(noms, rangees, seuil, applic, vis, liees)
    elif genre == "part":
        _masque_part(noms, rangees, seuil, applic, vis)
    elif genre == "flux":
        _masque_flux(rangees, seuil, applic, vis)
    elif genre == "couverture":
        _masque_couverture(rangees, seuil, applic, vis)
    else:
        for i, r in enumerate(rangees):
            applic[i] = {c for c in noms if c in COLONNES_COMPTE}
            vis[i] = {c: _visible(r[c], seuil) for c in applic[i]}
        if vue in VUES_EQUIPES:
            _masque_equipes(vue, noms, rangees, seuil, vis, liees)
        if vue == VUE_HEBDO:                                # T3, règle (a) : les cellules des lignes retirées sont masquées (sans effet si l'appelant les a retirées)
            for i in _lignes_retirees(vue, noms, lignes, seuil, liees):
                vis[i] = {c: False for c in applic[i]}
        if vue == VUE_DEBIT:
            retires = _t3_retires_monotone((noms, lignes), liees[VUE_HEBDO], seuil) if VUE_HEBDO in liees else set()
            _masque_debit(noms, rangees, seuil, vis, retires)
        for i, r in enumerate(rangees):
            for stat, effectif in STATS_TRANCHE_1.get(vue, {}).items():
                if stat in noms and not vis[i].get(effectif, False):
                    forcees[i].add(stat)
                elif stat in noms and stat in STATS_SANS_ANCIENS:
                    reste = None if r.get(effectif) is None or r.get("items_old") is None else r[effectif] - r["items_old"]
                    if not vis[i].get("items_old", False) or reste is None or reste < seuil:
                        forcees[i].add(stat)
            for part, (partie, tout) in PARTS_TRANCHE_1.get(vue, {}).items():
                if part not in noms:
                    continue
                p, t = r.get(partie), r.get(tout)
                if p is None or t is None or p < seuil or t - p < seuil or t < seuil:    # partie, reste ou tout sous le seuil : la part se lirait
                    vis[i][partie] = False
                    forcees[i].add(part)
    sorties = []
    for i, r in enumerate(rangees):
        cellules = {}
        for col in noms:
            if genre == "simple":                           # vues sans structure propre : la cellule primaire, puis les règles entre vues
                primaire = cellule(col, r[col], seuil)
                if vue == VUE_DEBIT and col == "items_old" and r[col] == 0 and vis[i].get(col, False):
                    cellules[col] = {"value": 0}            # R-20261106-39 : le zéro d'items_old est montré, la cellule primaire le masquerait
                    continue
                cellules[col] = _masquee(seuil) if (col in applic[i] and not vis[i].get(col, False)) or col in forcees[i] else primaire
            elif col in applic[i]:
                cellules[col] = {"value": r[col]} if vis[i].get(col, False) else _masquee(seuil)
            elif col in COLONNES_COMPTE or col in PARTS_PHOTO or (genre == "part" and col == "share_percent"):
                cellules[col] = {"value": None}            # sans objet pour cette sorte de ligne : ni valeur, ni masque
            else:
                cellules[col] = {"value": r[col]}
        sorties.append(cellules)
    return sorties


def taille_echantillon_h1(cellules: dict, genre: str) -> int | None:
    """Taille d'échantillon de H1 d'une ligne de v_team_lead_time_throughput, calculée des seules cellules montrées (change masking-sums, D16, « Sample size of
    H1 », R-20261106-18) : items_lt moins items_old pour le lead time (`genre` « lead »), items_ct moins items_old pour le cycle time (« cycle »). Aucune taille (None,
    le verdict « échantillon insuffisant ») quand l'effectif ou items_old est masqué, quelle que soit la règle qui l'a masqué : aucune borne basse n'est prise. Jamais
    publiée, ni dans la fiche ni dans un tableau. `cellules` : la sortie de masquer_vue pour la ligne. Même fonction en TypeScript (tailleEchantillonH1).
    Remplace : la borne basse `items_lt` - (T - 1) de R-20261105-30 (fausse, R-20261106-18). Retrait : permanent tant qu'un items_old masqué peut cacher une valeur
    du seuil ou plus et qu'aucune vue ne publie l'échantillon sans les anciens."""
    colonne = {"lead": "items_lt", "cycle": "items_ct"}.get(genre)
    if colonne is None:
        raise ValueError(genre)
    effectif, anciens = cellules.get(colonne), cellules.get("items_old")
    if effectif is None or anciens is None or "masked" in effectif or "masked" in anciens or effectif.get("value") is None or anciens.get("value") is None:
        return None
    return effectif["value"] - anciens["value"]


def _largeurs_photo(noms, rangees, seuil) -> dict:
    """Largeur de chaque cellule de comptage masquée de la photo après la propagation de D15 (la lecture la plus étroite non écartée) :
    (rang, colonne) -> largeur, math.inf sans borne haute. Rejoue le masquage sur les lignes brutes données à masquer_vue."""
    largeurs: dict = {}
    _masque_photo(noms, rangees, seuil, [set() for _ in rangees], [{} for _ in rangees], largeurs)
    return {cle: (float("inf") if w is None else w) for cle, w in largeurs.items()}


def _intervalles_chaine(noms, rangees, cellules, seuil) -> dict:
    """Photo : rang de chaque ligne sans version dont les créés sont masqués seuls (par la chaîne des semaines, sans affects et tous les trouvés de la
    semaine publiés) -> largeur de l'intervalle où ils se placent, celle de la propagation de D15 (« créés = sans affects + défauts distincts »,
    la chaîne et le produit croisés ; elle remplace la différence somme - max de la première version)."""
    largeurs = _largeurs_photo(noms, rangees, seuil)
    termes = defaultdict(list)
    for r, c in zip(rangees, cellules):
        if r.get("team") is not None and r.get("version_no") is not None:      # équipes et produit : chaque ligne avec ses lignes de version
            termes[(r.get("week_start"), r["team"])].append(None if "masked" in c["found"] else r["found"])
    intervalles = {}
    for i, (r, c) in enumerate(zip(rangees, cellules)):
        if r.get("team") is None or r.get("version_no") is not None:
            continue
        trouves = termes.get((r.get("week_start"), r["team"]), [])
        if "masked" in c["defects_created"] and "masked" not in c["defects_without_affects"] and trouves and None not in trouves:
            intervalles[i] = largeurs.get((i, "defects_created"), float("inf"))
    return intervalles


def _largeurs(vue, noms, rangees, cellules, seuil) -> dict:
    """Largeur (en unités) de chaque cellule masquée, relation par relation (D6) : la formule min(hi - lo, S - Σlo, Σhi - S, Σ(hi - lo) des autres)
    de la conception, pour les tranches du retard et le détail de la part ; ailleurs hi - lo. Une combinaison de relations peut être plus étroite
    (limite acceptée, l'oracle la couvre sur de petites tables)."""
    largeurs = {}
    for i, (r, c) in enumerate(zip(rangees, cellules)):
        for col in noms:
            if col in COLONNES_COMPTE and "masked" in c[col]:
                lo = BORNES.get(vue, {}).get(col, (0, False))[0]
                if vue == VUE_DEBIT and col == "items_old":
                    lo = _borne(vue, col, "masked" not in c["items_ct"])[0]      # R-20261106-39 : un zéro d'items_old est montré, un o masqué avec items_ct visible vaut au moins 1
                largeurs[(i, col)] = max(0, seuil - 1 - lo)
        if vue == VUE_RETARD and "items" in noms and "masked" not in c["items"]:
            cachees = [col for col in SEAUX_RETARD if "masked" in c[col]]
            vus = [r[col] for col in SEAUX_RETARD if "masked" not in c[col]]
            if cachees:
                haut = _haut(vue, cachees[0], seuil, vus)
                k, somme = len(cachees), r["items"] - sum(vus)
                for col in cachees:
                    largeurs[(i, col)] = max(0, min(haut, somme, k * haut - somme, (k - 1) * haut))
        if vue == VUE_PART and "masked" not in c["items"] and "masked" in c["with_fix_version"]:
            _, publiee = _etat_plancher(r["items"], r.get("with_fix_version"), r.get("with_fix_version_min"))
            largeurs[(i, "with_fix_version")] = max(0, r["items"] - publiee if publiee is not None else min(PLANCHER - 1, r["items"] - PLANCHER))
    if vue == VUE_PHOTO:
        largeurs.update(_largeurs_photo(noms, rangees, seuil))      # D15 : la largeur après propagation remplace celle de chaque relation prise seule
    return largeurs


def masquer(valeur, seuil: int, t: Messages) -> str:
    cell = cellule("tickets", valeur, seuil)
    if "masked" in cell:
        return t("masked")
    return str(cell["value"])


def lire(vue: str, role: str | None = None, **connexion) -> tuple[list[str], list[tuple]]:
    if vue not in VUES:                                        # liste fermée : jamais de nom venu de l'extérieur dans le SQL
        raise ValueError(vue)
    schema, role_de_la_vue = ("quality", ROLE_QUALITE) if vue in VUES_QUALITE else ("flow", ROLE)
    conn = db.connect(role=role or role_de_la_vue, **connexion)
    try:
        curseur = conn.execute(f"SELECT * FROM {schema}.{vue}")      # noqa: S608  (schéma et nom vérifiés ci-dessus)
        noms = [c.name for c in curseur.description]
        lignes = curseur.fetchall()
    finally:
        conn.close()
    return noms, lignes


def rendre(noms: list[str], lignes: list[tuple], seuil: int, t: Messages, vue: str | None = None, liees: dict | None = None) -> str:
    """Mise en forme seule : toute règle de masquage est dans masquer_vue. `vue` absent : la sorte de vue est déduite des colonnes."""
    cles = []
    if est_vue_photo(noms):
        cles = [noms.index(c) for c in ("week_start", "team", "version_no") if c in noms]
    elif est_vue_retard(noms):
        cles = [noms.index(c) for c in ("team", "quarter_start")]
    if cles:                        # photo et retard : l'ordre des semaines, équipes et versions, jamais celui d'un compte
        def cle_de_tri(ligne):
            return tuple("" if ligne[i] is None else str(ligne[i]).zfill(8) if isinstance(ligne[i], int) else str(ligne[i]) for i in cles)
    else:
        qualite = [i for colonne in CLES_DE_TRI_QUALITE for i, nom in enumerate(noms) if nom == colonne] if "item_kind" in noms else []

        def cle_de_tri(ligne):
            texte = tuple("" if x is None else str(x) for x in ligne)
            return tuple(texte[i] for i in qualite) + texte    # vues de qualité : équipe, genre, code d'abord, jamais un compte (M3 (a))
    ordonnees = sorted(lignes, key=cle_de_tri)
    cellules = masquer_vue(vue, noms, ordonnees, seuil, liees)
    part = est_vue_part(noms)

    def formater(nom: str, c: dict, ligne: dict) -> str:
        if "masked" in c:
            return t("masked")
        if c["value"] is None:
            return ""
        if part and nom == "with_fix_version_min":
            # borne basse publiée par la vue (D10) : affichée « ≥ N » tant que les items sont visibles, jamais recalculée ici
            return "" if "masked" in ligne["items"] else f"≥ {c['value']}"
        return str(c["value"])

    corps = [[formater(n, ligne[n], ligne) for n in noms] for ligne in cellules]
    if not corps:
        return t("no_rows")
    largeurs = [max(len(n), *(len(l[i]) for l in corps)) for i, n in enumerate(noms)]
    sortie = ["  ".join(n.ljust(w) for n, w in zip(noms, largeurs)).rstrip(),
              "  ".join("-" * w for w in largeurs)]
    sortie += ["  ".join(c.ljust(w) for c, w in zip(l, largeurs)).rstrip() for l in corps]
    return "\n".join(sortie)


def lire_avec_liees(vue: str) -> tuple[list[str], list[tuple], dict]:
    """La vue et, pour les règles entre vues, celles qu'elle lit (D5), sous le même rôle."""
    noms, lignes = lire(vue)
    return noms, lignes, {autre: lire(autre) for autre in VUES_LIEES.get(vue, ())}


def cellules_masquees(seuil: int, t: Messages) -> list[str]:
    """Lignes de masked-cells (D6) : par vue et par colonne de comptage, le nombre de cellules masquées sur le nombre de cellules ; par vue, le
    total et le nombre de cellules d'au plus une unité de large. Chaque vue est lue une fois. Jamais un nom, un identifiant ni une valeur."""
    lues = {vue: lire(vue) for vue in VUES}
    sortie = []
    for vue in VUES:
        noms, lignes = lues[vue]
        liees = {autre: lues[autre] for autre in VUES_LIEES.get(vue, ())}
        # T3 (D17, Q31) : les lignes que la règle (a) retirerait ne sont pas filtrées ici ; masquer_vue masque leurs cellules, qui comptent donc comme masquées
        rangees = [dict(zip(noms, ligne)) for ligne in lignes]
        cellules = masquer_vue(vue, noms, lignes, seuil, liees)
        largeurs = _largeurs(vue, noms, rangees, cellules, seuil)
        total = masquees = etroites = 0
        for col in (c for c in noms if c in COLONNES_COMPTE):
            sur = [(i, c[col]) for i, c in enumerate(cellules) if "masked" in c[col] or c[col]["value"] is not None]
            cachees = [i for i, cell in sur if "masked" in cell]
            sortie.append(t("masked_cells_column", view=vue, column=col, masked=len(cachees), cells=len(sur)))
            total += len(sur)
            masquees += len(cachees)
            etroites += sum(1 for i in cachees if largeurs.get((i, col), seuil) <= 1)
        sortie.append(t("masked_cells_view", view=vue, masked=masquees, cells=total, narrow=etroites))
        if vue == VUE_PHOTO:                       # créés masqués seuls par la chaîne des semaines : un intervalle, jamais une valeur (décision du 2026-10-27)
            intervalles = _intervalles_chaine(noms, rangees, cellules, seuil)
            sortie.append(t("masked_cells_chain", view=vue, count=len(intervalles), narrow=sum(1 for w in intervalles.values() if w <= 1)))
    return sortie


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vues agrégées du schéma flow (lecture seule).",
                                     epilog=f"Vues trimestrielles : {CATALOGS['fr']['quarter_limit']}. / Quarter views: {CATALOGS['en']['quarter_limit']}.")
    add_language_option(parser)
    sous = parser.add_subparsers(dest="commande", required=True)
    sous.add_parser("list", help="les vues disponibles")
    montrer = sous.add_parser("show", help="le contenu d'une vue")
    montrer.add_argument("vue")
    montrer.add_argument("--min-cell", type=int, help=f"seuil de masquage (relève le réglage, jamais sous {PLANCHER})")
    part = sous.add_parser("version-share", help="homogénéité de la part de fix version (vue v_team_fix_version_share)")
    part.add_argument("--floor", type=int, default=PLANCHER_PART,
                      help=f"part minimale en pourcent, de 1 à 100 (défaut {PLANCHER_PART})")
    comptees = sous.add_parser("masked-cells", help="nombre de cellules masquées par vue et par colonne (aucune valeur, aucun nom)")
    comptees.add_argument("--min-cell", type=int, help=f"seuil de masquage (relève le réglage, jamais sous {PLANCHER})")
    sous.add_parser("team-ids-check", help="nombre de noms d'équipe à plusieurs identifiants Jira (aucun nom)")
    args = parser.parse_args(argv)
    t = Messages(CATALOGS, args.language)
    if args.commande == "version-share" and not 1 <= args.floor <= 100:
        print(t("share_floor_range", floor=args.floor), file=sys.stderr)
        return 1
    try:
        configure = seuil_configure(t)
    except ReglagesIllisibles:
        print(t("settings_unreadable"), file=sys.stderr)
        return CODE_REGLAGES_ILLISIBLES
    try:
        if args.commande == "list":
            print(t("views_title", min_cell=configure, masked=t("masked")))
            largeur = max(len(vue) for vue in VUES) + 2          # le nom le plus long, au moins deux espaces avant la description
            for vue in VUES:
                limite = f" ({t('quarter_limit')})" if vue in VUES_TRIMESTRIELLES else ""      # limite déclarée de D3 (R-20261114-51)
                print(f"  {vue:<{largeur}}{t('desc_' + vue)}{limite}")
            return 0
        if args.commande == "version-share":
            if configure > PLANCHER:                           # comme show : un seuil relevé est rappelé (D8)
                print(t("min_cell_raised", min_cell=configure, masked=t("masked")), file=sys.stderr)
            noms, lignes = lire(VUE_PART)
            resultat = verdict_part(noms, lignes, args.floor, configure)
            print(t("share_" + resultat["verdict"], floor=args.floor, since=resultat["since"]))
            if resultat["not_established"]:
                print(t("share_teams_not_established", teams=", ".join(resultat["not_established"])))
            if resultat["no_team"]:                            # signal de processus : montrée à part, jamais dans le verdict
                detail = ", ".join(f"{q} {detail_part(g, v, t)}" for q, g, v in resultat["no_team"])
                print(t("share_no_team", team=SANS_EQUIPE, detail=detail))
            return 0
        if args.commande == "masked-cells":
            seuil = seuil_effectif(configure, args.min_cell)
            lignes = cellules_masquees(seuil, t)               # toutes les lectures avant la première ligne imprimée
            print("\n".join(lignes))
            return 0
        if args.commande == "team-ids-check":
            noms, lignes = lire("v_team_jira_ids")
            i_equipe = noms.index("team")
            par_nom: dict = defaultdict(int)
            for ligne in lignes:
                par_nom[ligne[i_equipe]] += 1
            nombre = sum(1 for n in par_nom.values() if n > 1)
            print(t("team_ids_count", n=nombre))
            if nombre:
                print(t("team_ids_clean"))
                return 3
            return 0
        if args.vue not in VUES:
            print(t("unknown_view", name=args.vue, views=", ".join(VUES)), file=sys.stderr)
            return 1
        seuil = seuil_effectif(configure, args.min_cell)
        if args.min_cell is not None and args.min_cell < PLANCHER:
            print(t("min_cell_floor", min_cell=seuil, floor=PLANCHER), file=sys.stderr)
        if seuil > PLANCHER:                                   # la cellule ne dit plus son seuil (idée #417) : un seuil relevé est rappelé
            print(t("min_cell_raised", min_cell=seuil, masked=t("masked")), file=sys.stderr)
        noms, lignes, liees = lire_avec_liees(args.vue)
        lignes = lignes_publiees(args.vue, noms, lignes, seuil, liees)      # T3, règle (a) : les lignes retirées ne s'impriment pas (D17)
        print(rendre(noms, lignes, seuil, t, vue=args.vue, liees=liees))
        return 0
    except db.ErreurBase as erreur:
        print(t("error", message=erreur), file=sys.stderr)
        return 1
    except MasquageInstable:
        # Remplace : la trace Python. Retrait : permanent, tant que MasquageInstable existe (R-20261109-19).
        # Échec fermé : rien n'est publié, ni le texte de l'exception ni trace.
        print(t("masking_unstable"), file=sys.stderr)
        return CODE_MASQUAGE_INSTABLE


if __name__ == "__main__":
    sys.exit(main())
