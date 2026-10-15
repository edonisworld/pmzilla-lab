"""Faux dépôt du manuel (design D13) : scripts de démonstration piégés, commandes, réglages, modèle planifié.

Chaque script écrit une sentinelle s'il est importé ou exécuté : la suite vérifie qu'elle n'existe jamais. Aucun
script du faux dépôt n'est lancé. Ce module n'est pas un test (nom sans préfixe test_).
"""
from pathlib import Path

PIEGE_PY = 'open({sentinelle!r}, "w").write("importé ou exécuté")\n'
PIEGE_SH = 'touch "{sentinelle}"\n'

OUTIL_SIMPLE = '''"""Outil simple de démonstration.

    uv run tools/outil_simple.py --mode json

Codes : 0 succès ; 1 échec ; 2 erreur d'usage
"""
import argparse
{piege}

def main():
    parser = argparse.ArgumentParser(description="Description du parseur simple")
    parser.add_argument("--mode", choices=["json", "text"], default="text", help="Format de sortie")
    parser.add_argument("--verbose", action="store_true", help="Bavard")
    parser.add_argument("--secret", help=argparse.SUPPRESS)
    parser.add_argument("--cache-aussi", help=argparse.SUPPRESS)
    parser.add_argument("fichier", nargs="?", help="Fichier à lire")
    parser.parse_args()

if __name__ == "__main__":
    main()
'''

OUTIL_SOUS = '''"""Outil à sous-commandes.

    uv run tools/outil_sous.py local

Codes de sortie
    0  tout va bien
    3  autre cas

Texte suivant la section.
"""
import argparse
{piege}
SOURCES = ("db", "fichier")

def main():
    parser = argparse.ArgumentParser()
    sous = parser.add_subparsers(dest="commande", required=True)
    test = sous.add_parser("test", help="Contacte le service distant")
    test.add_argument("--cle", help="Clé du ticket")
    local = sous.add_parser("local", help="Calcul local")
    local.add_argument("--delai", type=int, default=5, help="Délai en secondes")
    calcul = sous.add_parser("calcul", help="Calcul avec source")
    calcul.add_argument("--source", choices=["fichier", "db"], default="fichier", help="Source des données")
    calcul.add_argument("--calculee", choices=SOURCES, help="Choix calculés")
    calcul.add_argument("--aide-calculee", default=SOURCES[0], help="Défaut " + SOURCES[1])
    exclusif = calcul.add_mutually_exclusive_group(required=True)
    exclusif.add_argument("--json", action="store_true", help="Sortie JSON")
    exclusif.add_argument("--csv", action="store_true", help="Sortie CSV")
    groupe = calcul.add_argument_group("Filtres")
    groupe.add_argument("--depuis", help="Date de départ")
    origine = sous.add_parser("origine", help="Source écrite en metavar")
    origine.add_argument("--source", default="csv", metavar="{{csv,db}}", help="Origine des données")
    profond = sous.add_parser("profond", help="Sous-commandes imbriquées")
    niveau = profond.add_subparsers(dest="niveau")
    niveau.add_parser("un", help="Premier niveau")
    niveau.add_parser("deux", help="Deuxième niveau")
    parser.parse_args()

if __name__ == "__main__":
    main()
'''

OUTIL_AIDE = '''"""Outil avec options partagées.

    uv run tools/outil_aide.py
"""
import argparse
from ailleurs import ajouter_ailleurs
{piege}

def ajouter_langue(parser):
    parser.add_argument("--language", choices=["fr", "en"], default="fr", help="Langue des messages")

def main():
    parser = argparse.ArgumentParser()
    ajouter_langue(parser)
    ajouter_ailleurs(parser)
    parser.parse_args()

if __name__ == "__main__":
    main()
'''

OUTIL_SANS_PARSEUR = '''"""Outil sans argparse, lu dans sys.argv.

    uv run tools/outil_sans_parseur.py a.csv
    uv run tools/outil_sans_parseur.py a.csv b.csv

Détails ignorés.
"""
import sys
{piege}

if __name__ == "__main__":
    print(sys.argv)
'''

OUTIL_PLACEHOLDER = '''"""Outil dont le seul usage porte un marqueur.

    uv run tools/outil_placeholder.py <cle>

Codes : 0 ok
"""
import argparse
{piege}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cle", help="Clé obligatoire sans valeur par défaut")
    parser.parse_args()

if __name__ == "__main__":
    main()
'''

OUTIL_GENERE = '''# Pas de docstring : l'exemple est construit depuis le parseur.
import argparse
{piege}

def main():
    parser = argparse.ArgumentParser()
    sous = parser.add_subparsers(dest="commande", required=True)
    voir = sous.add_parser("voir", help="Voir")
    voir.add_argument("--genre", required=True, choices=["court", "long"], help="Genre")
    voir.add_argument("--niveau", required=True, default="3", help="Niveau")
    parser.parse_args()

if __name__ == "__main__":
    main()
'''

OUTIL_PLANIFIE_PY = '''"""Outil lancé par l'enveloppeur planifié."""
{piege}

if __name__ == "__main__":
    pass
'''

BIBLIOTHEQUE = '''"""Module de bibliothèque sans point d'entrée."""
{piege}

def utile():
    return 1
'''

LANCEUR_SH = '''#!/bin/bash
# PMZilla Lab : lanceur de démonstration.
# Deuxième ligne du rôle.
#
#     bash tools/lanceur.sh              lance tout
#     bash tools/lanceur.sh --seulement  seulement la moitié
#
# Codes : 0 succès ; 1 échec ;
#         2 erreur d'usage
set -u
{piege}'''

SANS_ENTETE_SH = '''#!/bin/bash
set -u
{piege}echo "rien à lire ici"
'''

PLANIFIE_SH = '''#!/bin/bash
# PMZilla Lab : enveloppeur planifié.
#
#     bash tools/planifie.sh
set -u
{piege}'''

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>__HOME__/PMZilla-Lab/workspace/tools/planifie.sh</string>
  </array>
</dict>
</plist>
"""

COMMANDE_DEMO = """---
description: Commande de démonstration pour le manuel
argument-hint: "[fr|en]"
model: sonnet
allowed-tools: Bash(ls:*)
---

Corps jamais lu : MARQUEUR-CORPS-SECRET
"""

COMMANDE_MARQUEUR = """---
description: Commande dont l'indication d'argument porte un marqueur
argument-hint: "<identifiant>"
model: opus
---

Corps.
"""

RUN_ALL = """#!/bin/bash
# Lance toutes les suites de démonstration.
#
#     bash tests/run_all.sh         toutes les suites
#     bash tests/run_all.sh -v      en plus, la sortie complète
#
# Codes : 0 vert ; 1 échec
set -u
"""

REGLES_DENY = [
    "Bash(uv run tools/outil_sous.py test*)",
    "Bash(python tools/outil_sous.py test*)",
    "Bash(python3 tools/outil_sous.py test*)",
    "Bash(uv run tools/outil_sous.py calcul*--source db*)",
    "Bash(python3 tools/outil_sous.py calcul*--source db*)",
    "Bash(uv run tools/outil_sous.py origine*--source db*)",
    "Bash(bash tools/lanceur.sh*)",
    "Bash(uv run tools/ancien_nom.py*)",
    "Read(./Flux-Lab/exports/**)",
]


def ecrire(racine, relatif, texte):
    chemin = Path(racine) / relatif
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")
    return chemin


def construire_depot(racine, sentinelle):
    """Écrit le faux dépôt sous `racine` ; `sentinelle` est le fichier que tout script exécuté créerait."""
    py, sh = PIEGE_PY.format(sentinelle=str(sentinelle)), PIEGE_SH.format(sentinelle=str(sentinelle))
    modeles = {
        "tools/outil_simple.py": OUTIL_SIMPLE, "tools/outil_sous.py": OUTIL_SOUS, "tools/outil_aide.py": OUTIL_AIDE,
        "tools/outil_sans_parseur.py": OUTIL_SANS_PARSEUR, "tools/outil_placeholder.py": OUTIL_PLACEHOLDER,
        "tools/outil_genere.py": OUTIL_GENERE, "tools/outil_planifie.py": OUTIL_PLANIFIE_PY,
        "tools/bibliotheque_lib.py": BIBLIOTHEQUE}
    for relatif, modele in modeles.items():
        ecrire(racine, relatif, modele.format(piege=py))
    ecrire(racine, "tools/lanceur.sh", LANCEUR_SH.format(piege=sh))
    ecrire(racine, "tools/sans_entete.sh", SANS_ENTETE_SH.format(piege=sh))
    ecrire(racine, "tools/planifie.sh", PLANIFIE_SH.format(piege=sh))
    ecrire(racine, "tools/com.exemple.planifie.plist", PLIST)
    ecrire(racine, "tools/hooks/pre-commit", "#!/bin/sh\n" + sh)
    ecrire(racine, ".claude/commands/demo.md", COMMANDE_DEMO)
    ecrire(racine, ".claude/commands/marqueur.md", COMMANDE_MARQUEUR)
    ecrire(racine, "tests/run_all.sh", RUN_ALL + sh)
    import json
    ecrire(racine, ".claude/settings.json", json.dumps({"permissions": {"deny": REGLES_DENY, "allow": ["Bash(ls:*)"]}}))
    ecrire(racine, "docs/pmzilla/.gitkeep", "")
    return racine


TABLE = {
    "tools/outil_simple.py": "Flux et Jira", "tools/outil_sous.py": "Flux et Jira", "tools/outil_aide.py": "Base",
    "tools/outil_sans_parseur.py": "Base", "tools/outil_placeholder.py": "Base", "tools/outil_genere.py": "Base",
    "tools/outil_planifie.py": "Sauvegardes", "tools/lanceur.sh": "Sauvegardes", "tools/sans_entete.sh": "Sauvegardes",
    "tools/planifie.sh": "Sauvegardes", "/demo": "Diagnostic (doctor)", "/marqueur": "Diagnostic (doctor)",
    "tests/run_all.sh": "Tests et contrôles"}
