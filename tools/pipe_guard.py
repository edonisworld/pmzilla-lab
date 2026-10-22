#!/usr/bin/env python3
"""PMZilla Lab : garde des tubes (change deny-rules-review, design D6 à D8 et D10).

Hook Claude Code des appels Bash : signale, sans jamais bloquer, un tube dont le programme receveur est python3 (avec ou sans
version mineure), python, grep, egrep, fgrep ou tail. Un tail qui suit directement le lanceur de tests (un mot dont le nom de
base est run_all.sh, ou le mot unittest) n'est pas signalé (décision Q3, option B).

    python3 tools/pipe_guard.py --event post   signalé : message sur la sortie d'erreur, code 2 (la commande a déjà tourné)
    python3 tools/pipe_guard.py --event pre    signalé : JSON additionalContext sur la sortie standard, code 0

Entrée : le JSON du hook sur l'entrée standard. Rien signalé, entrée illisible ou autre outil que Bash : code 0, aucune sortie.
Erreur d'usage : code 1. Bibliothèque standard seulement ; ne lit que l'entrée standard, n'écrit aucun fichier, ne lance aucune
commande, n'imprime que les noms des programmes receveurs (jamais la commande).
"""
import json
import os
import re
import shlex
import sys

PROGRAMMES = re.compile(r"^(python3(\.\d+)?|python|grep|egrep|fgrep|tail)$")
AFFECTATION = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
TUBES = ("|", "|&")
CONTROLES = {"|", "|&", "||", "&&", ";", ";;", "&", "(", ")"}
USAGE = "pipe_guard : option --event attendue (pre ou post)"
MESSAGE = ("garde des tubes : sortie passée à « {noms} » ; utiliser l'outil Read ou Grep, ou lire la sortie telle quelle "
           "(préambule des agents). Signalement seulement : la commande n'a pas été bloquée.")


def _mots(commande: str):
    lexeur = shlex.shlex(commande, posix=True, punctuation_chars=True)
    lexeur.whitespace_split = True
    return list(lexeur)


def _est_lanceur(segment: list) -> bool:
    return any(mot == "unittest" or os.path.basename(mot) == "run_all.sh" for mot in segment)


def receveurs(commande: str) -> list:
    """Noms distincts, dans l'ordre d'apparition, des programmes qui reçoivent un tube et sont à signaler ; [] si illisible."""
    try:
        mots = _mots(commande)
    except ValueError:
        return []
    noms, debut = [], 0   # debut : index du premier mot du segment en cours
    for i, mot in enumerate(mots):
        if mot not in CONTROLES:
            continue
        if mot in TUBES:
            alimentation = mots[debut:i]
            suite = []
            for suivant in mots[i + 1:]:
                if suivant in CONTROLES:
                    break
                suite.append(suivant)
            while suite and AFFECTATION.match(suite[0]):
                suite = suite[1:]
            if suite:
                nom = os.path.basename(suite[0])
                if PROGRAMMES.match(nom) and not (nom == "tail" and _est_lanceur(alimentation)):
                    if nom not in noms:
                        noms.append(nom)
        debut = i + 1
    return noms


def _lire_commande(texte: str):
    try:
        donnees = json.loads(texte)
    except ValueError:
        return None
    if not isinstance(donnees, dict) or donnees.get("tool_name") != "Bash":
        return None
    entree = donnees.get("tool_input")
    commande = entree.get("command") if isinstance(entree, dict) else None
    return commande if isinstance(commande, str) else None


def main(argv: list, entree: str) -> int:
    evenement = argv[argv.index("--event") + 1] if "--event" in argv[:-1] else None
    if evenement not in ("pre", "post"):
        print(USAGE, file=sys.stderr)
        return 1
    commande = _lire_commande(entree)
    noms = receveurs(commande) if commande else []
    if not noms:
        return 0
    message = MESSAGE.format(noms=", ".join(noms))
    if evenement == "post":
        print(message, file=sys.stderr)
        return 2
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": message}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], sys.stdin.read()))
