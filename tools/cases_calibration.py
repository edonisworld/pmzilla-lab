# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.2,<2", "pyyaml", "httpx", "numpy", "psycopg[binary]"]
# ///
"""
PMZilla Lab : calibration provisoire du seuil de similarité du module des cas (db-lot2, design.md 3.7).

    uv run tools/cases_calibration.py [--language fr|en|both]

Lit tests/postures/cas.yaml, garde les cas qui nomment un `cases_fixture`, et calcule, pour chaque langue, la similarité entre la
question de chaque cas et chaque entrée des jeux d'essai de cette langue (texte stocké : problem, chosen_path, tested). La paire
« question de X, première entrée du jeu de X » est liée ; toute autre paire de la même langue est non liée. Règle : low = max des
non liées, high = min des liées, valeur proposée = milieu arrondi à deux décimales vers le bas, si elle reste strictement au-dessus
de low ; sinon « no separation » et aucune valeur.

Sort des identifiants, des natures, des rangs et des nombres, jamais une question ni un texte de jeu. Ne lit aucune base ; la
fonction d'embedding est celle de la bibliothèque (Ollama doit répondre).
"""
from __future__ import annotations

import argparse
import math
import sys
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path

import cases_store

WORKSPACE = Path(__file__).resolve().parents[1]
CASES_FILE = WORKSPACE / "tests" / "postures" / "cas.yaml"
LANGUAGES = ("fr", "en")


def propose_threshold(related: list[float], unrelated: list[float]) -> float | None:
    """Milieu entre le plus haut non lié et le plus bas lié, arrondi à deux décimales vers le bas ; None sans séparation."""
    if not related or not unrelated:
        return None
    low, high = max(unrelated), min(related)
    if not high > low:
        return None
    value = float(Decimal(repr(float((low + high) / 2))).quantize(Decimal("0.01"), rounding=ROUND_FLOOR))
    return value if value > low else None


def _entries(fixture: Path) -> list[dict]:
    """Entrées du jeu dans l'ordre de chargement : expériences puis cas (rang à partir de 1 dans chaque nature)."""
    import yaml
    data = yaml.safe_load(fixture.read_text(encoding="utf-8")) or {}
    entries = []
    for kind, key in (("experiment", "experiments"), ("case", "cases")):
        for index, raw in enumerate(data.get(key) or [], start=1):
            entries.append({"kind": kind, "index": index, "text": cases_store.embedding_text(
                raw["problem"], raw.get("chosen_path"), raw["tested"])})
    return entries


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def load_cases(language: str, cases_file: Path = CASES_FILE, workspace: Path = WORKSPACE) -> list[dict]:
    """Cas qui nomment un `cases_fixture` dans la langue demandée : id, question, entrées."""
    import yaml
    result = []
    for case in yaml.safe_load(cases_file.read_text(encoding="utf-8")) or []:
        block = {**case, **(case.get("en") or {})} if language == "en" else case
        if not block.get("cases_fixture"):
            continue
        result.append({"id": case["id"], "question": block["question"],
                       "entries": _entries(workspace / block["cases_fixture"])})
    return result


def build_pairs(language: str, embed, cases_file: Path = CASES_FILE, workspace: Path = WORKSPACE) -> list[dict]:
    """Paires (question de X, entrée e) d'une langue ; liée seulement pour la première entrée du jeu de X."""
    cases = load_cases(language, cases_file, workspace)
    pairs = []
    for case in cases:
        question = embed(case["question"])
        for other in cases:
            for position, entry in enumerate(other["entries"]):
                pairs.append({
                    "case_id": case["id"], "language": language, "entry_case_id": other["id"],
                    "kind": entry["kind"], "index": entry["index"],
                    "related": other["id"] == case["id"] and position == 0,
                    "similarity": _cosine(question, embed(entry["text"]))})
    return pairs


def main(argv=None, embed=None, out=None) -> int:
    parser = argparse.ArgumentParser(description="Propose un seuil de similarité provisoire (design.md 3.7).")
    parser.add_argument("--language", choices=("fr", "en", "both"), default="both")
    args = parser.parse_args(argv)
    out = out or sys.stdout
    languages = LANGUAGES if args.language == "both" else (args.language,)
    try:
        pairs = [p for lang in languages for p in build_pairs(
            lang, lambda text: cases_store._embed(embed, text))]
    except cases_store.CasesError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for p in pairs:
        label = "related" if p["related"] else "unrelated"
        print(f"{p['case_id']} {p['language']} {p['entry_case_id']} {p['kind']} {p['index']} {label} {p['similarity']:.3f}", file=out)
    related = [p["similarity"] for p in pairs if p["related"]]
    unrelated = [p["similarity"] for p in pairs if not p["related"]]
    if not related or not unrelated:
        print("no separation (no pair)", file=out)
        return 0
    print(f"low {max(unrelated):.3f}", file=out)
    print(f"high {min(related):.3f}", file=out)
    value = propose_threshold(related, unrelated)
    print("no separation" if value is None else f"proposed value {value:.2f}", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
