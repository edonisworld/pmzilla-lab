"""Lecture des scripts shell, des commandes slash et des modèles planifiés pour le manuel (change user-manual, tâche 4.1).

Module de bibliothèque : tout est lu comme TEXTE (read_text, regex). Aucun script n'est importé, exécuté ni lancé, aucun
modèle launchd n'est chargé. Une source illisible (UnicodeDecodeError, OSError) n'est pas avalée : elle remonte à l'appelant.
"""
from __future__ import annotations

import re
from pathlib import Path

DOSSIER_HOOKS = "tools/hooks"
MODELE_PLANIFIE = "tools/com.pmzilla.*.plist"

_DEBUTS_USAGE = ("bash tools/", "zsh tools/", "bash tests/", "uv run tools/")
_MARQUEURS_CODES = ("Codes de sortie", "Code de sortie", "Codes", "Code")
_SCRIPT_PLANIFIE = re.compile(r"tools/[\w.-]+\.(?:sh|py)")
_MARQUEURS_EXEMPLE = ("<", ">", "...", "XXX", "chemin/vers")


def _entete(chemin: Path) -> list[str]:
    """Lignes du bloc de commentaires qui suit le shebang, sans le `#` ni l'espace qui le suit (indentation conservée).

    Le bloc s'arrête à la première ligne qui n'est pas un commentaire (une ligne vide l'arrête) : rien n'est lu au-delà.
    """
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    debut = 1 if lignes and lignes[0].startswith("#!") else 0
    bloc: list[str] = []
    for ligne in lignes[debut:]:
        if not ligne.lstrip().startswith("#"):
            break
        texte = ligne.lstrip()[1:]
        bloc.append(texte[1:] if texte.startswith(" ") else texte)
    return bloc


def _role(bloc: list[str]) -> str | None:
    """Lignes jusqu'au premier commentaire vide, jointes par un espace ; None si le bloc est absent ou commence par du vide."""
    morceaux: list[str] = []
    for ligne in bloc:
        if not ligne.strip():
            break
        morceaux.append(ligne.strip())
    return " ".join(morceaux) if morceaux else None


def _usages(bloc: list[str]) -> list[dict]:
    resultat = []
    for ligne in bloc:
        texte = ligne.strip()
        if not texte.startswith(_DEBUTS_USAGE):
            continue
        morceaux = re.split(r"\s{2,}", texte, maxsplit=1)
        explication = morceaux[1].strip() if len(morceaux) > 1 and morceaux[1].strip() else None
        resultat.append({"commande": morceaux[0].rstrip(), "explication": explication})
    return resultat


def _marqueur_codes(ligne: str) -> str | None:
    """Reste du texte après un marqueur de codes placé en TÊTE de ligne (`Codes :`, `Code de sortie :`, `Codes de sortie`).

    Retourne None si la ligne ne commence pas par un marqueur ; "" si le marqueur est seul (forme section).
    """
    texte = ligne.strip()
    for marqueur in _MARQUEURS_CODES:
        if texte.startswith(marqueur):
            reste = texte[len(marqueur):]
            if reste and not reste[0].isspace() and reste[0] != ":":
                continue
            reste = reste.strip()
            if reste.startswith(":"):
                reste = reste[1:].strip()
            return reste
    return None


def _decouper(texte: str) -> list[str]:
    return [" ".join(p.split()) for p in texte.split(";") if p.strip()]


def _codes(bloc: list[str]) -> list[str] | None:
    for i, ligne in enumerate(bloc):
        reste = _marqueur_codes(ligne)
        if reste is None:
            continue
        suite = bloc[i + 1:]
        if reste:
            # Forme en ligne : une continuation est indentée ; une ligne non indentée continue aussi tant que la phrase n'est
            # pas finie (cas réel : code reporté sur la ligne suivante), et la lecture s'arrête à la première fin de phrase.
            morceaux = [reste]
            for suivante in suite:
                if not suivante.strip() or morceaux[-1].endswith("."):
                    break
                if not suivante[:1].isspace():
                    fin = suivante.find(". ")
                    if fin != -1:
                        morceaux.append(suivante[:fin + 1].strip())
                        break
                morceaux.append(suivante.strip())
            codes = _decouper(" ".join(morceaux))
        else:
            # Forme section : une ligne par code, jusqu'à la première ligne vide du commentaire.
            lignes = []
            for suivante in suite:
                if not suivante.strip():
                    break
                lignes.append(suivante.rstrip())
            marge = min((len(x) - len(x.lstrip()) for x in lignes), default=0)
            codes = [x[marge:] for x in lignes]
        return codes or None
    return None


def lire_shell(chemin: Path) -> dict:
    """Rôle, lignes d'usage et codes de sortie d'un script shell, lus dans son bloc d'en-tête."""
    bloc = _entete(Path(chemin))
    return {"role": _role(bloc), "usages": _usages(bloc), "codes": _codes(bloc)}


def _valeur_yaml(texte: str) -> str:
    texte = texte.strip()
    if len(texte) >= 2 and texte[0] == texte[-1] and texte[0] in "\"'":
        texte = texte[1:-1]
    return texte


def lire_commande(chemin: Path) -> dict:
    """Description, indication d'argument et modèle d'une commande slash, lus dans le front-matter (le corps n'est pas lu)."""
    chemin = Path(chemin)
    valeurs: dict[str, str] = {}
    with chemin.open(encoding="utf-8") as flux:
        premiere = flux.readline()
        if premiere.strip() == "---":
            for ligne in flux:
                if ligne.strip() == "---":
                    break
                cle, separateur, valeur = ligne.partition(":")
                if separateur and cle.strip() in ("description", "argument-hint", "model"):
                    valeurs[cle.strip()] = _valeur_yaml(valeur)
    return {"nom": chemin.stem, "description": valeurs.get("description"),
            "indice_argument": valeurs.get("argument-hint"), "modele": valeurs.get("model")}


def exemple_commande(nom: str, indice_argument: str | None) -> str:
    """`/nom`, suivi de l'indice d'argument seulement quand il ne porte aucun marqueur de substitution."""
    if indice_argument is None or any(m in indice_argument for m in _MARQUEURS_EXEMPLE):
        return f"/{nom}"
    return f"/{nom} {indice_argument}"


def scripts_planifies(dossier_tools: Path) -> set[str]:
    """Chemins `tools/<nom>.sh|.py` nommés par les modèles launchd `*.plist` du dossier (lus comme texte)."""
    noms: set[str] = set()
    for modele in sorted(Path(dossier_tools).glob("*.plist")):
        noms.update(_SCRIPT_PLANIFIE.findall(modele.read_text(encoding="utf-8")))
    return noms


def commandes_slash(racine: Path) -> list[Path]:
    """Les `.claude/commands/*.md`, triés par nom."""
    return sorted((Path(racine) / ".claude" / "commands").glob("*.md"), key=lambda p: p.name)


def scripts_shell(racine: Path) -> list[Path]:
    """Les `tools/*.sh`, triés, sans `tools/hooks/` ni aucun sous-dossier."""
    return sorted((p for p in (Path(racine) / "tools").glob("*.sh") if p.is_file()), key=lambda p: p.name)
