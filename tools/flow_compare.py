# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PMZilla Lab : comparaison de deux rapports de flux (change database-only, D9 : la voie CSV n'existe plus).

    uv run tools/flow_compare.py reports <rapport-a.md> <rapport-b.md>      deux rapports écrits par le même outil

`reports` compare deux rapports déjà écrits (par exemple avant et après un changement de code, avec deux valeurs différentes de --name, pour
vérifier que le changement laisse les rapports identiques) : les lignes sont alignées comme diff, hors le titre, la ligne de fusion des
exports et les noms de fichiers de la ligne « Export » ; les écarts restants sont comptés par numéro de section (0 = avant le premier
titre), jamais avec leur contenu.

`data` est retirée (code 2, « data est retirée : la voie CSV n'existe plus ») : il n'y a plus de voie CSV à comparer à la base. Aucune
connexion à la base, aucune lecture de fichier.

Ce que l'outil affiche : des COMPTES seulement. Aucune clé de ticket, aucune valeur de champ, aucun nom d'équipe. Code de sortie 0 si tout
est identique, 1 sinon, 2 en cas d'erreur ou d'usage retiré. À lancer par l'utilisateur seul sur les vraies données (règles deny de
.claude/settings.json).

Exemple :
    uv run tools/flow_compare.py reports flux-avant-2026-10-04.md flux-apres-2026-10-04.md
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from messages import Messages, add_language_option  # noqa: E402
from flow_compare_messages import CATALOGS  # noqa: E402


class Ecarts:
    """Les écarts d'une comparaison, en comptes."""

    def __init__(self) -> None:
        self.lignes: list[str] = []
        self.total = 0

    def noter(self, texte: str, n: int = 1) -> None:
        self.lignes.append(texte)
        self.total += n


FUSION = re.compile(r"^(Fusion de \d+ exports|Merge of \d+ exports)\b")      # n'existe que du côté CSV avec plusieurs fichiers
NOM_EXPORT = re.compile(r"^(Export ?: ).*? · ")                              # le nom du fichier (CSV) ou « base »


def normaliser_rapport(texte: str) -> list[str]:
    """Lignes d'un rapport sans ce qui dépend de la source : le titre (première ligne : il porte le nom), la ligne de fusion
    des exports, les noms de fichiers de la ligne « Export » ; les suites de lignes vides sont réduites à une."""
    lignes: list[str] = []
    for ligne in texte.splitlines()[1:]:
        if FUSION.match(ligne):
            continue
        ligne = NOM_EXPORT.sub(r"\1· ", ligne, count=1)
        if not ligne.strip() and (not lignes or not lignes[-1].strip()):
            continue
        lignes.append(ligne)
    while lignes and not lignes[-1].strip():
        lignes.pop()
    return lignes


def comparer_rapports(a: Path, b: Path, t: Messages) -> Ecarts:
    """Aligne les lignes comme diff (une ligne en plus ou en moins ne décale pas les suivantes) ; les écarts restants sont
    comptés par numéro de section (0 = avant le premier titre « # »), jamais avec leur contenu."""
    ecarts = Ecarts()
    lignes_a = normaliser_rapport(a.read_text(encoding="utf-8"))
    lignes_b = normaliser_rapport(b.read_text(encoding="utf-8"))
    ecarts.lignes.append(t("reports_section", a=len(lignes_a), b=len(lignes_b)))
    par_section: Counter = Counter()
    for etiquette, i1, i2, j1, j2 in difflib.SequenceMatcher(None, lignes_a, lignes_b, autojunk=False).get_opcodes():
        if etiquette != "equal":
            section = sum(1 for ligne in lignes_a[:i1] if ligne.startswith("#"))
            par_section[section] += max(i2 - i1, j2 - j1)
    for section in sorted(par_section):
        ecarts.noter(t("reports_section_differs", section=section, n=par_section[section]), par_section[section])
    return ecarts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare deux rapports de flux (comptes seulement).")
    add_language_option(parser)
    sous = parser.add_subparsers(dest="commande", required=True, metavar="{reports}")
    d = sous.add_parser("data")                       # retirée : refusée avec la voie à suivre, absente de l'aide
    d.add_argument("ignores", nargs="*")
    d.add_argument("--history", nargs="?", const="", default=None)
    r = sous.add_parser("reports", help="deux rapports écrits par le même outil")
    r.add_argument("rapport_a")
    r.add_argument("rapport_b")
    args = parser.parse_args(argv)
    t = Messages(CATALOGS, args.language)
    if args.commande == "data":                       # avant toute lecture et toute connexion (design D9)
        print(t("error", message=t("data_retired")), file=sys.stderr)
        return 2
    try:
        ecarts = comparer_rapports(Path(args.rapport_a).expanduser(), Path(args.rapport_b).expanduser(), t)
    except SystemExit:
        raise
    except FileNotFoundError:
        print(t("error", message=t("file_missing")), file=sys.stderr)
        return 2
    except Exception as erreur:          # le message d'une exception peut citer une clé ou une valeur : seul le type est affiché
        print(t("error", message=type(erreur).__name__), file=sys.stderr)
        return 2
    print("\n".join(ecarts.lignes))
    print(t("identical") if ecarts.total == 0 else t("differences", n=ecarts.total))
    return 0 if ecarts.total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
