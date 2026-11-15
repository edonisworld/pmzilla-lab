# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Lecteur des durées des suites pour l'ordre de départ de tests/run_all.sh (change run-all-faster-and-guarded, design D1). Bibliothèque
standard seulement, en lecture seule : il n'écrit rien.

    python3 tools/suite_order.py --durations <fichier>

Lit le fichier des durées du lanceur (mesures/run_all-durees.tsv, dix champs séparés par une tabulation : lancement, identifiant, genre,
poste, suite, type, secondes, secondes_unittest, verdict, raison). Pour chaque paire (suite, type), il garde les lignes de genre
« complet » et de verdict « ok », et prend la médiane des secondes des cinq dernières. (L'option --chunks, pour les suites shell découpées
en morceaux, est retirée avec ce découpage : B9, finish-single-b7-b9, décision de l'auteur R-20261105-33 ; argparse la refuse en code 2.)

Sortie : une ligne « <suite>:<type><TAB><secondes estimées> » par suite mesurée, dans l'ordre de première apparition (code 0).
Codes de sortie : 0 ; 2 usage ; 3 fichier absent, illisible ou sans aucune ligne utilisable.
Une ligne mal formée ou partielle (la dernière, qu'un autre lanceur est en train d'écrire) est ignorée.

Exemple :
    python3 tools/suite_order.py --durations mesures/run_all-durees.tsv
"""
import argparse
import statistics
import sys
from pathlib import Path

CHAMPS = 10
DERNIERES = 5


def lignes_utiles(lignes):
    """[(suite, type, secondes)] des lignes complètes, de genre « complet » et de verdict « ok », dans l'ordre du fichier."""
    utiles = []
    for brute in lignes:
        champs = brute.rstrip("\n").split("\t")
        if len(champs) != CHAMPS or champs[2] != "complet" or champs[8] != "ok":
            continue
        try:
            secondes = float(champs[6])
        except ValueError:
            continue
        if secondes < 0 or secondes != secondes:
            continue
        utiles.append((champs[4], champs[5], secondes))
    return utiles


def estimations(lignes):
    """{(suite, type) : secondes estimées} : médiane des cinq dernières durées vertes d'un passage complet. Une paire sans ligne utile
    n'y figure pas."""
    durees = {}
    for suite, genre, secondes in lignes_utiles(lignes):
        durees.setdefault((suite, genre), []).append(secondes)
    return {paire: statistics.median(valeurs[-DERNIERES:]) for paire, valeurs in durees.items()}


def principal(argv):
    analyseur = argparse.ArgumentParser(prog="suite_order.py", description="Estime la durée des suites d'après le fichier des durées.")
    analyseur.add_argument("--durations", required=True, help="fichier des durées du lanceur")
    try:
        arguments = analyseur.parse_args(argv)
    except SystemExit as sortie:
        return 2 if sortie.code not in (0, None) else 0
    try:
        lignes = Path(arguments.durations).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 3
    estimees = estimations(lignes)
    if not estimees:
        return 3
    for (suite, genre), secondes in estimees.items():
        print(f"{suite}:{genre}\t{secondes:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
