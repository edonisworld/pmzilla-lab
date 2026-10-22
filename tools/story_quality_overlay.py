"""PMZilla Lab : lecture et contrôle de la surcouche de l'organisation de la grille de qualité des stories (change story-quality-audit,
design D17, tâches 2.9 et 2.10).

Une seule surcouche, pour toute l'organisation : le fichier `surcouche-qualite-stories.yaml` du sous-dossier `regles/` du dossier de
contexte résolu par `lab_paths.context_folder` (variable PMZILLA_LAB_CONTEXT, sinon `contexte` du dossier du lab), jamais un chemin lu dans un réglage. Ce module ne lit que le fichier qu'on lui
donne ; il n'ouvre ni base, ni Jira, ni clé.

Contrôles, dans l'ordre :
  1. le YAML se lit (clé répétée refusée) ;
  2. le texte entier (identifiant et résumé de contexte compris) ne contient ni nom sensible ni identifiant personnel : ligne par ligne
     dans le texte brut, puis dans chaque chaîne lue, clés comprises, espaces normalisés (bloc multiligne, échappement `\\u…`) ;
  3. le schéma tools/story_quality_overlay.schema.json, par la bibliothèque `jsonschema` : jeu de clés fermé, bornes de longueur ;
  4. le rapport avec le socle : un critère désactivé nomme un code du socle ; un critère ajouté ne reprend pas un code du socle (ce serait
     renommer, reformuler ou relier autrement un critère du socle) et ne répète pas un code de la surcouche.

`OverlayError` porte une clé de message et ses champs : le chemin d'une clé (`criteria.story[0].code`) ou un numéro de ligne, jamais une
valeur de la surcouche.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths  # noqa: E402
import sensitive_names  # noqa: E402
import yaml_strict  # noqa: E402

CONTEXT_VARIABLE = "PMZILLA_LAB_CONTEXT"
OVERLAY_FOLDER = "regles"
OVERLAY_FILE = "surcouche-qualite-stories.yaml"
SCHEMA_PATH = Path(__file__).resolve().parent / "story_quality_overlay.schema.json"
KINDS = ("story", "epic")

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
MENTION = re.compile(r"(?<![\w])@\w{2,}")


class OverlayError(Exception):
    """Surcouche refusée. `key` : clé du catalogue de messages ; `values` : ses champs (chemin ou numéro de ligne, jamais une valeur)."""

    def __init__(self, key: str, **values):
        super().__init__(key)
        self.key = key
        self.values = values


def overlay_path(environ) -> Path | None:
    """Chemin de la surcouche sous le dossier de contexte du résolveur partagé (`lab_paths.context_folder`, design D16 de
    organisation-context) : la variable quand elle est posée, sinon `contexte` du dossier du lab. None quand le dossier de contenu est
    introuvable. Rien n'est ouvert ici."""
    if environ.get(CONTEXT_VARIABLE):
        dossier = lab_paths.context_folder(Path(), environ)
    else:
        try:
            dossier = lab_paths.context_folder(lab_paths.content_root(environ), environ)
        except lab_paths.LabPathsError:
            return None
    return dossier / OVERLAY_FOLDER / OVERLAY_FILE


def _path_text(path) -> str:
    texte = ""
    for part in path:
        texte += f"[{part}]" if isinstance(part, int) else (f".{part}" if texte else str(part))
    return texte or "(root)"


def _first_error(document, schema) -> str | None:
    """Chemin de la première erreur de schéma, dans un ordre stable ; jamais le message de jsonschema (il cite la valeur)."""
    import jsonschema
    erreurs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(document), key=lambda e: [str(p) for p in e.absolute_path])
    if not erreurs:
        return None
    erreur = erreurs[0]
    base = list(erreur.absolute_path)
    if erreur.validator == "additionalProperties":
        connues = erreur.schema.get("properties", {})
        inconnues = sorted(k for k in erreur.instance if k not in connues)
        return _path_text(base + inconnues[:1])
    if erreur.validator == "required":
        manquantes = [k for k in erreur.validator_value if k not in erreur.instance]
        return _path_text(base + manquantes[:1])
    return _path_text(base)


def line_with_sensitive_content(text: str, names, identifiers) -> int | None:
    """Numéro (à partir de 1) de la première ligne qui contient un nom sensible, un identifiant personnel, une adresse e-mail ou une
    mention ; None sinon. Ne rend jamais la valeur trouvée."""
    motifs = sensitive_names.patterns(names)
    cherches = [i.lower() for i in identifiers if i]
    for numero, ligne in enumerate(text.splitlines(), 1):
        minuscule = ligne.lower()
        if (sensitive_names.line_matches(motifs, ligne) or EMAIL.search(ligne) or MENTION.search(ligne)
                or any(c in minuscule for c in cherches)):
            return numero
    return None


def _sensitive_text(texte: str, motifs, cherches) -> bool:
    texte = " ".join(texte.split())              # espaces normalisés : un nom coupé par un bloc `>` ou `|` se retrouve entier
    minuscule = texte.lower()
    return bool(sensitive_names.line_matches(motifs, texte) or EMAIL.search(texte) or MENTION.search(texte)
                or any(c in minuscule for c in cherches))


def path_with_sensitive_content(document, names, identifiers) -> str | None:
    """Chemin (forme de `_path_text`) de la première chaîne lue (valeur ou clé, récursivement) qui contient un nom sensible, un
    identifiant personnel, une adresse e-mail ou une mention ; None sinon. Une clé fautive est rendue `(key)` sous le chemin de son
    parent. Rattrape ce que le contrôle par ligne ne voit pas (bloc multiligne, échappement `\\u…`) ; ne rend jamais la valeur."""
    motifs = sensitive_names.patterns(names)
    cherches = [i.lower() for i in identifiers if i]

    def parcourir(noeud, chemin):
        if isinstance(noeud, str):
            return _path_text(chemin) if _sensitive_text(noeud, motifs, cherches) else None
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                if isinstance(cle, str) and _sensitive_text(cle, motifs, cherches):
                    return _path_text(chemin + ["(key)"])
                trouve = parcourir(valeur, chemin + [cle if isinstance(cle, str) else str(cle)])
                if trouve:
                    return trouve
        elif isinstance(noeud, list):
            for i, valeur in enumerate(noeud):
                trouve = parcourir(valeur, chemin + [i])
                if trouve:
                    return trouve
        return None

    return parcourir(document, [])


def check_overlay(text: str, core_codes, names, identifiers, schema_path: Path = SCHEMA_PATH) -> dict:
    """Surcouche lue depuis son texte, contrôlée ; lève OverlayError. `core_codes` : tous les codes du socle (les deux listes)."""
    try:
        document = yaml_strict.charger(text, OVERLAY_FILE)
    except (yaml_strict.ErreurConfig, Exception):
        raise OverlayError("overlay_invalid", field="(yaml)") from None
    # Avant le schéma : son refus nomme une clé inconnue, qui ne doit jamais être un nom ou une adresse.
    ligne = line_with_sensitive_content(text, names, identifiers)
    if ligne is not None:
        raise OverlayError("overlay_refused", line=ligne)
    chemin = path_with_sensitive_content(document, names, identifiers)
    if chemin is not None:
        raise OverlayError("overlay_refused_path", field=chemin)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    chemin = _first_error(document, schema)
    if chemin is not None:
        raise OverlayError("overlay_invalid", field=chemin)
    core_codes = set(core_codes)
    for i, desactive in enumerate(document.get("disabled", [])):
        if desactive["code"] not in core_codes:
            raise OverlayError("overlay_invalid", field=f"disabled[{i}].code")
    vus = set()
    for kind in KINDS:
        for i, critere in enumerate(document.get("criteria", {}).get(kind, [])):
            if critere["code"] in core_codes or critere["code"] in vus:
                raise OverlayError("overlay_invalid", field=f"criteria.{kind}[{i}].code")
            vus.add(critere["code"])
    return dict(document)


def read_overlay_file(path: Path) -> str:
    """Texte de la surcouche ; fichier illisible : OverlayError (aucun détail)."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise OverlayError("overlay_invalid", field="(file)") from None
