# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "numpy", "requests", "psycopg[binary]"]
# ///
"""Lanceur de test des outils de rapport sur des fixtures CSV (change database-only, D11, tâche 4.1).

    uv run tests/flux_jira/lanceur_csv.py <outil> <arguments de l'outil, fichiers CSV compris>

Les outils lisent la base seule. Ce lanceur, réservé aux tests, retire de la ligne les fichiers CSV et le chemin donné à --history,
remplace le module flow_store par un faux qui rend les structures de ces fixtures (chargeur_csv.py), puis lance le `main` de l'outil
dans le même processus : même code de sortie, même sortie, aucune base. Aucun module du produit ne l'importe.
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parents[1] / "tools"))
sys.path.insert(0, str(ICI))
import chargeur_csv as chargeur  # noqa: E402

def separer(arguments: list[str]) -> tuple[list[str], list[str], str | None, bool]:
    """(arguments restants, chemins CSV, chemin du cache d'historique ou None, --history donné)."""
    restants, csv, cache, historique = [], [], None, False
    i = 0
    while i < len(arguments):
        a = arguments[i]
        if a.endswith(".csv"):
            csv.append(a)
        elif a in ("--history", "--historique"):
            historique = True
            restants.append("--history")
            suivant = arguments[i + 1] if i + 1 < len(arguments) else None
            if suivant is not None and not suivant.startswith("-") and not suivant.endswith(".csv"):
                cache = suivant
                i += 1
        else:
            restants.append(a)
        i += 1
    return restants, csv, cache, historique


def main() -> None:
    executer(sys.argv[1], sys.argv[2:])


def executer(outil: str, arguments: list[str]) -> None:
    """Lance `main` de l'outil (flux_jira, dependencies_jira, segment_sample ou epic_statuses). Le lanceur retire de la ligne les
    fichiers .csv et la valeur de --history ; avec LANCEUR_BRUT=1, la ligne est donnée telle quelle (tests de refus). Il retire aussi
    CLAUDECODE de l'environnement, sauf avec LANCEUR_GARDE_CLAUDECODE=1 (tests du refus en session)."""
    if os.environ.get("LANCEUR_GARDE_CLAUDECODE") != "1":
        os.environ.pop("CLAUDECODE", None)
    if os.environ.get("LANCEUR_BRUT") == "1":
        restants, csv, cache, historique = arguments, [], None, False
    else:
        restants, csv, cache, historique = separer(arguments)
    faux = types.ModuleType("flow_store")
    faux.lire_tickets_flux = lambda settings: chargeur.lire_tickets_flux(settings, csv)
    faux.lire_dependances = lambda settings: chargeur.lire_dependances(settings, csv)
    faux.lire_historique = lambda settings: chargeur.lire_historique(settings, cache)
    sys.modules["flow_store"] = faux
    sys.argv = [str(ICI.parents[1] / "tools" / f"{outil}.py")] + restants
    module = __import__(outil)
    module.main()


if __name__ == "__main__":
    main()
