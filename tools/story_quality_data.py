"""PMZilla Lab : données et fonctions de service de la qualité des stories (change story-quality-audit, design D6, D15, D17).

Ce module ne lit ni base, ni Jira, ni clé. Il porte :
  - `load_core_grid` : lecture et contrôle du jumeau machine du socle de la grille (deux listes de critères, un identifiant, une version) ;
  - `effective_criteria` : les critères effectifs d'un genre (socle non désactivé, puis critères de la surcouche avec la marque
    « règle de l'organisation »).
  - `report_data` : la fonction de service du rapport (D15, M1 (a)) ; elle reçoit des lignes de vues, jamais une connexion.

Format du jumeau du socle (JSON) : {"identifier": str, "version": int, "story": [critère…], "epic": [critère…]} ; un critère : code,
label_fr, label_en, definition, engine_question, not_applicable_condition (texte ou null), link, source (non vide).
"""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from messages import Messages
from story_quality_messages import CATALOGS

KINDS = ("story", "epic")
LINKS = ("ticket_template", "discovery_workflow_step", "definition_of_ready", "refinement")
GRID_CONTRACT = "story_quality_grid"
GRID_CONTRACT_VERSION = 1
STRUCTURE_KEYS = ("sections", "definition_of_ready", "vocabulary")
CORE_ORIGIN = "core"
OVERLAY_ORIGIN = "organisation_rule"
ORGANISATION_RULE_MARK = {"en": "organisation rule", "fr": "règle de l'organisation"}
CRITERION_TEXT_FIELDS = ("code", "label_fr", "label_en", "definition", "engine_question", "link")


class GridError(Exception):
    """Socle absent ou invalide. Le message ne cite jamais le texte d'un critère."""


def load_core_grid(path: Path) -> dict:
    """Socle lu depuis son jumeau JSON ; lève GridError s'il manque, est illisible ou invalide (critère sans ligne de source compris)."""
    try:
        grid = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise GridError("grid_missing") from None
    except (OSError, UnicodeDecodeError, ValueError):
        raise GridError("grid_invalid") from None
    if not isinstance(grid, dict) or not isinstance(grid.get("identifier"), str) or not grid["identifier"] \
            or not isinstance(grid.get("version"), int) or isinstance(grid["version"], bool):
        raise GridError("grid_invalid")
    codes = set()
    for kind in KINDS:
        criteria = grid.get(kind)
        if not isinstance(criteria, list) or not criteria:
            raise GridError("grid_invalid")
        for criterion in criteria:
            if not isinstance(criterion, dict) or any(not isinstance(criterion.get(f), str) or not criterion[f].strip()
                                                      for f in CRITERION_TEXT_FIELDS + ("source",)):
                raise GridError("grid_invalid")
            if criterion["link"] not in LINKS or criterion["code"] in codes:
                raise GridError("grid_invalid")
            na = criterion.get("not_applicable_condition")
            if na is not None and not isinstance(na, str):
                raise GridError("grid_invalid")
            codes.add(criterion["code"])
    return grid


def core_codes(grid: dict) -> set[str]:
    return {c["code"] for kind in KINDS for c in grid[kind]}


def disabled_codes(overlay: dict | None) -> list[str]:
    """Codes du socle désactivés par la surcouche, dans l'ordre du fichier (jamais les raisons)."""
    return [d["code"] for d in (overlay or {}).get("disabled", [])]


def _criterion(raw: dict, origin: str, source: str) -> dict:
    return {
        "code": raw["code"],
        "labels": {"fr": raw["label_fr"], "en": raw["label_en"]},
        "definition": raw["definition"],
        "engine_question": raw["engine_question"],
        "not_applicable_condition": raw.get("not_applicable_condition"),
        "link": raw["link"],
        "origin": origin,
        "source": source,
    }


def effective_criteria(core: dict, overlay: dict | None, kind: str, language: str = "en") -> list[dict]:
    """Critères effectifs d'un genre : ceux du socle que la surcouche ne désactive pas, dans l'ordre du socle, puis ceux de la surcouche,
    dans l'ordre du fichier, avec la marque de la langue en place de la ligne de source."""
    off = set(disabled_codes(overlay))
    result = [_criterion(c, CORE_ORIGIN, c["source"]) for c in core[kind] if c["code"] not in off]
    mark = ORGANISATION_RULE_MARK[language]
    result += [_criterion(c, OVERLAY_ORIGIN, mark) for c in (overlay or {}).get("criteria", {}).get(kind, [])]
    return result


def effective_grid(core: dict, overlay: dict | None, language: str = "en") -> dict:
    """Fonction de service de la grille effective (design D15) : le contrat `story_quality_grid`, version 1. Elle reçoit le socle et la
    surcouche déjà lus et contrôlés ; elle ne lit rien. `grid --show` et `grid --show --json` mettent son résultat en forme et ne
    construisent aucun critère. Jamais une raison de désactivation, l'identifiant de la surcouche ni le résumé de contexte du produit."""
    structure = (overlay or {}).get("structure", {})
    return {
        "contract": GRID_CONTRACT,
        "contract_version": GRID_CONTRACT_VERSION,
        "core_version": core["version"],
        "overlay_version": overlay["version"] if overlay else None,
        "kinds": {
            kind: {
                "criteria": effective_criteria(core, overlay, kind, language),
                "structure": {key: list(structure.get(kind, {}).get(key, [])) for key in STRUCTURE_KEYS},
            }
            for kind in KINDS
        },
    }


# --- Rapport (tâche 3.23, design D15, M1 (a), M4 révisé en (b) le 2026-10-20) ----------------------------------------------------------
# Masquage : les vues le portent au plancher de 5 (migration 0016) : cellule sous 5, masquage complémentaire dans une ligne, masquage
# secondaire du produit contre les équipes (D18). Le rapport relève le seuil (min_cell, seuil effectif) et refait à ce seuil le masquage
# complémentaire des lignes d'équipe et de la couverture (revue 4.1, E4) : sinon une cellule entre 5 et le seuil relevé se retrouverait
# par différence avec `audited`. Il refait aussi à ce seuil le masquage secondaire de la chaîne du produit contre les lignes d'équipe.

REPORT_CONTRACT = "story_quality_report"
REPORT_CONTRACT_VERSION = 1
COUNT_COLUMNS = ("met", "not_met", "not_applicable", "undetermined")      # les quatre comptes du contrat (D15) ; `audited` ne sert qu'au dénominateur
COVERAGE_COLUMNS = ("collected", "audited", "empty_acceptance_criteria")
MASK_FLOOR = 5


def masked_cell(threshold: int) -> dict:
    """Cellule masquée du schéma de mothra-slices D3 : jamais de propriété `value`."""
    return {"state": "masked", "threshold": threshold}


def count_cell(value, threshold: int) -> dict:
    """Cellule d'un compte : masquée si la vue l'a masquée (None) ou si elle passe sous le seuil effectif ; jamais estimée."""
    if value is None or value < threshold:
        return masked_cell(threshold)
    return {"state": "value", "value": int(value)}


def complement_masked(values, audited, threshold: int) -> list[bool]:
    """Cellules masquées des quatre comptes d'une ligne au seuil effectif, avec le masquage complémentaire de quality.mask_verdicts
    (migration 0016) refait à ce seuil : tant que la somme des cellules masquées (`audited` moins les cellules visibles) reste sous le
    seuil, la plus petite cellule visible est masquée aussi (égalité : l'ordre des colonnes). None : cellule que la vue a masquée. Au
    plancher, la vue a déjà fait ce complément : rien n'est recalculé."""
    masked = [v is None or v < threshold for v in values]
    if threshold <= MASK_FLOOR or not any(masked) or audited is None:    # audited masqué par la vue : toutes ses cellules sont sous 5
        return masked
    while True:
        visible = [i for i, m in enumerate(masked) if not m]
        if not visible or audited - sum(values[i] for i in visible) >= threshold:
            return masked
        masked[min(visible, key=lambda i: (values[i], i))] = True


def coverage_cells(row: dict, threshold: int) -> dict:
    """Cellules de couverture au seuil effectif, avec les compléments de quality_coverage_by_team (migration 0016) refaits à ce seuil :
    collectés moins audités sous le seuil masque `collected` ; audités moins sans critère (en valeur absolue), ou collectés visibles
    moins sans critère, sous le seuil masque `empty_acceptance_criteria`. `audited` n'est jamais masqué par le complément. Au plancher,
    la vue l'a déjà fait : rien n'est recalculé."""
    collected, audited, empty = (row.get(name) for name in COVERAGE_COLUMNS)

    def known(v):
        return v is not None and v >= threshold
    releve = threshold > MASK_FLOOR
    collected_masked = releve and known(collected) and known(audited) and collected - audited < threshold
    empty_masked = releve and known(empty) and ((known(audited) and abs(audited - empty) < threshold)
                                                or (known(collected) and not collected_masked and collected - empty < threshold))
    return {"collected": masked_cell(threshold) if collected_masked else count_cell(collected, threshold),
            "audited": count_cell(audited, threshold),
            "empty_acceptance_criteria": masked_cell(threshold) if empty_masked else count_cell(empty, threshold)}


def _share(numerator: dict, audited: dict, threshold: int) -> dict:
    """Part d'un compte sur TOUS les éléments audités, ceux « sans objet » compris (M4 révisé en (b)) : le dénominateur ne dépend plus
    du compte « sans objet ». Masquée dès que le numérateur ou le dénominateur l'est : aucun ratio n'est calculé, aucune valeur masquée
    n'est estimée."""
    if numerator["state"] != "value" or audited["state"] != "value":
        return masked_cell(threshold)
    return {"state": "value", "numerator": numerator, "denominator": audited}      # la paire de deux cellules D3, jamais un nombre nu


def _recurrent(share: dict, recurrence) -> bool:
    """Vrai si la part non satisfaite atteint le seuil de récurrence (D18). Comparaison exacte (fractions), cellule masquée jamais récurrente."""
    if recurrence is None or share["state"] != "value":
        return False
    return share["numerator"]["value"] >= Fraction(str(recurrence)) * share["denominator"]["value"]


def _line_order(row: dict) -> tuple:
    return LINKS.index(row["link"]) if row["link"] in LINKS else len(LINKS), row["code"]


def _cause_line(kind: str, code: str, label: str, row: dict, share: dict) -> dict:
    return {"kind": kind, "code": code, "label": label, "origin": row["origin"], "link": row["link"], "share_not_met": share}


def report_data(team_rows, coverage_rows, product_rows, grid: dict, *, threshold, disabled=(), min_cell: int = MASK_FLOOR,
                language: str = "en") -> dict:
    """Fonction de service du rapport (design D15, M1 (a)) : le contrat `story_quality_report`, version 1. Elle reçoit les lignes (dicts
    colonne -> valeur, None pour une cellule masquée par la vue) des trois vues `quality_by_team`, `quality_coverage_by_team` et
    `quality_by_product`, la grille effective (`effective_grid`: versions et libellés), les codes du socle que la surcouche désactive, le
    seuil de récurrence `threshold` (une part ; None : aucun défaut n'est récurrent) et le seuil de masquage effectif `min_cell`. Elle ne
    lit ni base, ni fichier. Le Markdown et le JSON du rapport mettent en forme son résultat et ne calculent rien.

    Ordres : équipes par nom, critères par code, lignes de causes par maillon puis code ; jamais d'après un résultat. Le résultat ne dépend
    pas de l'ordre des lignes reçues. Pas de rang, de score, de total par équipe ni de nombre d'équipes ; la chaîne du produit n'a aucun
    champ d'équipe. Le masquage (complémentaire, et secondaire de D18) vient des vues au plancher, et il est refait au seuil
    relevé : une ligne de produit que la vue masque n'a aucune
    part lisible, elle n'est donc jamais récurrente et n'apparaît pas dans la chaîne."""
    t = Messages(CATALOGS, language)
    labels = {c["code"]: c["labels"][language] for kind in KINDS for c in grid["kinds"][kind]["criteria"]}

    def label(code: str) -> str:
        return labels.get(code, code)

    def notice(code: str) -> dict:
        return {"code": code, "text": t(code)}

    def counts(row: dict) -> dict:
        masked = complement_masked([row.get(name) for name in COUNT_COLUMNS], row.get("audited"), min_cell)
        return {name: masked_cell(min_cell) if m else count_cell(row.get(name), min_cell) for name, m in zip(COUNT_COLUMNS, masked)}

    by_team: dict[str, dict[str, list[dict]]] = {}
    for row in team_rows:
        by_team.setdefault(row["team"], {}).setdefault(row["item_kind"], []).append(row)
    coverage: dict[str, dict[str, dict]] = {}
    single_po: dict[str, bool] = {}
    for row in coverage_rows:
        coverage.setdefault(row["team"], {})[row["item_kind"]] = coverage_cells(row, min_cell)
        single_po[row["team"]] = single_po.get(row["team"], False) or bool(row.get("single_po"))

    # Cellules d'équipe masquées au seuil effectif, par ligne de produit et par colonne (audited puis les quatre comptes) : leur valeur
    # brute (None, celle que la vue a masquée, compte pour 0 : la somme n'en est que plus prudente). Sert au masquage secondaire relevé.
    team_masked: dict[tuple, list[list]] = {}

    teams = []
    for team in sorted(set(by_team) | set(coverage)):
        criteria, causes = {}, []
        for kind in KINDS:
            criteria[kind] = []
            for row in sorted(by_team.get(team, {}).get(kind, []), key=lambda r: r["criterion_code"]):
                cells = counts(row)
                audited = count_cell(row.get("audited"), min_cell)
                columns = team_masked.setdefault((kind, row["criterion_code"], row["origin"], row["link"]), [[] for _ in range(5)])
                for i, (name, cell) in enumerate(zip(("audited",) + COUNT_COLUMNS, [audited] + [cells[n] for n in COUNT_COLUMNS])):
                    if cell["state"] == "masked":
                        columns[i].append(row.get(name) or 0)
                share_not_met = _share(cells["not_met"], audited, min_cell)
                criteria[kind].append({
                    "code": row["criterion_code"], "label": label(row["criterion_code"]), "origin": row["origin"], "link": row["link"],
                    "counts": cells, "share_met": _share(cells["met"], audited, min_cell),
                    "share_not_met": share_not_met})
                if _recurrent(share_not_met, threshold):
                    causes.append(_cause_line(kind, row["criterion_code"], label(row["criterion_code"]),
                                              {"origin": row["origin"], "link": row["link"], "code": row["criterion_code"]}, share_not_met))
        causes.sort(key=_line_order)
        teams.append({
            "team": team,
            "single_po": single_po.get(team, False),
            "single_po_notice": t("single_po_notice") if single_po.get(team, False) else None,
            "coverage": {kind: coverage[team][kind] for kind in KINDS if kind in coverage.get(team, {})},
            "criteria": criteria,
            "probable_causes": {"notice": notice("probable_causes_notice"), "lines": causes},
        })

    def secondary_masked(row: dict) -> bool:
        """Règle secondaire de la vue produit (D18, migration 0016) refaite au seuil relevé : pour une colonne où la cellule du produit est
        visible, une seule cellule d'équipe masquée, ou des cellules masquées dont la somme est sous le seuil, masquent toute la ligne."""
        columns = team_masked.get((row["item_kind"], row["criterion_code"], row["origin"], row["link"]))
        if min_cell <= MASK_FLOOR or not columns:
            return False
        for name, masked in zip(("audited",) + COUNT_COLUMNS, columns):
            visible = row.get(name) is not None and row.get(name) >= min_cell
            if visible and masked and (len(masked) == 1 or sum(masked) < min_cell):
                return True
        return False

    # Chaîne du produit : au plancher, la vue porte déjà le masquage secondaire (D18) ; au seuil relevé, il est refait à ce seuil.
    chain = []
    for row in product_rows:
        if secondary_masked(row):
            continue
        share = _share(count_cell(row.get("not_met"), min_cell), count_cell(row.get("audited"), min_cell), min_cell)
        if not _recurrent(share, threshold):
            continue
        chain.append(_cause_line(row["item_kind"], row["criterion_code"], label(row["criterion_code"]),
                                 {"origin": row["origin"], "link": row["link"], "code": row["criterion_code"]}, share))
    chain.sort(key=_line_order)

    return {
        "contract": REPORT_CONTRACT,
        "contract_version": REPORT_CONTRACT_VERSION,
        "grid": {"core_version": grid["core_version"], "overlay_version": grid["overlay_version"], "disabled_codes": list(disabled)},
        "notice": notice("team_results_notice"),
        "teams": teams,
        "product_chain": {"notice": notice("product_chain_notice"), "lines": chain},
    }
