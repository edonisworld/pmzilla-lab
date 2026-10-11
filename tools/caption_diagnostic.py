# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "httpx", "pyyaml", "mcp>=1.2,<2", "psycopg[binary]"]
# ///
"""
PMZilla Lab — diagnostic des légendes PDF que l'indexation ne retire pas du texte de page.

    uv run tools/caption_diagnostic.py <livre.md>

Pour un livre converti depuis un PDF, l'indexation retire du texte courant la copie de chaque légende que la page
répète juste avant le bloc figure (pmzilla_lab_library._remove_caption_copy). Ce script prend le Markdown d'un livre,
rejoue ce retrait et classe par cause chaque légende qui n'a pas été retirée :

    trop loin du bloc        la copie existe, ligne entière, mais hors de la fenêtre du retrait (au-delà des
                             CAPTION_LOOKBACK paragraphes, avant la figure précédente, ou après le bloc)
    collée à d'autres mots   la légende est contenue dans une ligne qui contient aussi d'autres mots
    coupée                   la légende est répartie sur plus de CAPTION_MAX_LINES lignes ou sur plusieurs paragraphes
    forme différente         texte très proche (tiret de coupure, ligature, ponctuation, numéro) sans être identique
    introuvable              aucune ressemblance dans la fenêtre

Il n'affiche que des comptes : jamais le texte du livre, ni une légende, ni le titre ni le chemin du livre. Il ne
modifie rien, n'écrit aucun fichier et n'ouvre pas l'index.
"""
import copy
import difflib
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pmzilla_lab_library as library  # noqa: E402

SIMILAR = 0.85   # rapport de ressemblance à partir duquel une autre forme est dite « forme différente »
FAR_BEFORE = 200  # paragraphes examinés avant la figure précédente

CAUSES = ("trop loin du bloc", "collée à d'autres mots", "coupée sur plusieurs lignes ou paragraphes",
          "forme différente", "introuvable")


def _lines(item: list) -> list[str]:
    return [library._plain(line) for line in item[1].split("\n")]


def _whole_line_runs(lines: list[str], wanted: str) -> bool:
    """Vrai si `wanted` est exactement une ligne, ou 2 à CAPTION_MAX_LINES lignes consécutives (comme le retrait)."""
    for start in range(len(lines)):
        for stop in range(start + 1, min(len(lines), start + library.CAPTION_MAX_LINES) + 1):
            if " ".join(p for p in lines[start:stop] if p) == wanted:
                return True
    return False


def _paragraphs(items: list[list], start: int, step: int, limit: int, stop_at_figure: bool) -> list[list]:
    """Paragraphes à partir de `start`, dans le sens `step`, jusqu'à `limit` paragraphes (ou la figure voisine)."""
    found: list[list] = []
    index = start
    while 0 <= index < len(items) and len(found) < limit:
        item = items[index]
        if item[0] == "figure" and stop_at_figure:
            break
        if item[0] == "para":
            found.append(item)
        index += step
    return found


def classify(items: list[list], figure_index: int, caption: str) -> str:
    """Cause pour laquelle la légende `caption` du bloc `figure_index` n'a pas été retirée."""
    wanted = library._plain(caption)
    near = _paragraphs(items, figure_index - 1, -1, library.CAPTION_LOOKBACK, True)
    far_same_page = _paragraphs(items, figure_index - 1, -1, 10 ** 6, True)[library.CAPTION_LOOKBACK:]
    previous = next((i for i in range(figure_index - 1, -1, -1) if items[i][0] == "figure"), -1)
    before_previous = _paragraphs(items, previous - 1, -1, FAR_BEFORE, False) if previous >= 0 else []
    after = _paragraphs(items, figure_index + 1, 1, library.CAPTION_LOOKBACK, True)
    for paragraphs in (far_same_page, before_previous, after):   # exacte, mais hors de la fenêtre du retrait
        if any(_whole_line_runs(_lines(p), wanted) for p in paragraphs):
            return "trop loin du bloc"
    near_lines = [line for p in near for line in _lines(p)]
    if any(wanted in line and line != wanted for line in near_lines):
        return "collée à d'autres mots"
    chronological = [line for p in reversed(near) for line in _lines(p)]
    if wanted in " ".join(line for line in chronological if line):
        return "coupée sur plusieurs lignes ou paragraphes"
    for p in near:
        lines = _lines(p)
        for start in range(len(lines)):
            for stop in range(start + 1, min(len(lines), start + library.CAPTION_MAX_LINES) + 1):
                candidate = " ".join(x for x in lines[start:stop] if x)
                if difflib.SequenceMatcher(None, wanted, candidate).ratio() >= SIMILAR:
                    return "forme différente"
    return "introuvable"


def diagnose(body: str) -> dict:
    """Comptes pour le corps d'un Markdown : figures PDF à légende, retirées, non retirées par cause."""
    items = library.parse_items(body)
    working = copy.deepcopy(items)
    counts: Counter = Counter()
    captioned = removed = 0
    for index, item in enumerate(items):
        if item[0] != "figure" or item[1].get("source") != "pdf" or not item[2]:
            continue
        captioned += 1
        if library._remove_caption_copy(working, index, item[2]):
            removed += 1
        else:   # classée sur les paragraphes d'origine : un retrait voisin ne doit pas changer la cause
            counts[classify(items, index, item[2])] += 1
    return {"figures_pdf_avec_legende": captioned, "retirees": removed, "causes": counts}


def report(result: dict) -> str:
    left = result["figures_pdf_avec_legende"] - result["retirees"]
    lines = [f"Figures PDF avec légende : {result['figures_pdf_avec_legende']}",
             f"Légendes retirées du texte de page : {result['retirees']}",
             f"Non retirées : {left}"]
    lines += [f"  {cause} : {result['causes'].get(cause, 0)}" for cause in CAUSES]
    return "\n".join(lines) + "\n"


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    path = Path(sys.argv[1]).expanduser()
    if not path.is_file():
        sys.exit("Fichier introuvable.")   # le chemin n'est pas répété : il contient le titre du livre
    _, body = library.read_title(path.read_text(encoding="utf-8", errors="replace"), "")
    print(report(diagnose(body)), end="")


if __name__ == "__main__":
    main()
