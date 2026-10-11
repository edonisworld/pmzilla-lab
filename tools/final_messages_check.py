# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]", "httpx", "numpy", "mcp>=1.2,<2"]
# ///
"""PMZilla Lab : mesure, sans aucun appel au modèle, de l'indicateur « un seul message final » sur les traces conservées.

    uv run tools/final_messages_check.py [--data DOSSIER] [--case ID] [--list]

Relit les séances de ~/.pmzilla-lab/essais/<passage>/<cas>.jsonl avec la lecture de tools/posture_evals.py (messages du
dernier échange) et compte, par cas, les séances à un seul message final et celles qui en ont plusieurs (Critic restitué
dans un second message, par exemple). `--list` nomme les passages concernés. N'affiche que des identifiants de cas, des
horodatages de passage et des comptes.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import posture_evals as essai  # noqa: E402


def measure(data: Path, case: str | None = None) -> tuple[dict[str, list[int]], dict[str, list[str]]]:
    """({cas: [séances à un message, séances à plusieurs]}, {cas: [passages à plusieurs messages]})."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    several: dict[str, list[str]] = defaultdict(list)
    for trace_file in sorted(data.glob("*/*.jsonl")):
        name = trace_file.stem
        if ".rejeu" in name or (case and name != case):
            continue
        events, _ = essai.saved_session(trace_file.parent, name)
        if not events:
            continue
        ok = essai.check_single_final(essai.read_trace(events))["ok"]
        counts[name][0 if ok else 1] += 1
        if not ok:
            several[name].append(trace_file.parent.name)
    return counts, several


def main() -> None:
    parser = argparse.ArgumentParser(description="Séances à plusieurs messages finaux, sur les traces conservées")
    parser.add_argument("--data", default=str(essai.DATA), help="dossier des passages (défaut : ~/.pmzilla-lab/essais)")
    parser.add_argument("--case", help="un seul cas")
    parser.add_argument("--list", action="store_true", help="nomme les passages à plusieurs messages")
    args = parser.parse_args()
    counts, several = measure(Path(args.data).expanduser(), args.case)
    if not counts:
        print("Aucune trace trouvée.")
        return
    print(f"{'cas':32} {'un message':>10} {'plusieurs':>10}")
    for name in sorted(counts):
        one, many = counts[name]
        print(f"{name:32} {one:>10} {many:>10}")
    one = sum(c[0] for c in counts.values())
    many = sum(c[1] for c in counts.values())
    print(f"{'TOTAL':32} {one:>10} {many:>10}   ({100 * many / (one + many):.1f} % de séances à plusieurs messages)")
    if args.list:
        for name in sorted(several):
            print(f"{name} : {', '.join(several[name])}")


if __name__ == "__main__":
    main()
