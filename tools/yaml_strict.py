"""PMZilla Lab : lecture des fichiers YAML de configuration qui refuse une clé écrite deux fois.

PyYAML garde la dernière valeur d'une clé répétée, sans rien dire : une ligne oubliée en haut du fichier passe alors
pour une ligne lue. `charger` lève `ErreurConfig` avec les numéros des deux lignes et le chemin de la clé (jamais une
valeur : le message peut être affiché tel quel).

    from yaml_strict import charger
    reglages = charger(chemin.read_text(encoding="utf-8"), chemin.name)

`ErreurConfig` hérite de `SystemExit` : comme `sys.exit("message")`, elle s'arrête avec le message et le code 1, et elle
traverse les `except Exception` des scripts (qui ne montrent que le nom de l'exception). Les dictionnaires rendus gardent
le numéro de ligne de chaque clé dans l'attribut `lignes` (utilisé par flux_config pour ses messages).

Rien dans ce module ne lit de fichier de lui-même : il reçoit un texte.
"""
from __future__ import annotations

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

MERGE = "tag:yaml.org,2002:merge"


class ErreurConfig(SystemExit):
    """Réglage refusé : le message dit quoi corriger, avec les numéros de ligne, sans aucune valeur."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class DictLignes(dict):
    """Un dictionnaire lu dans un YAML ; `lignes` : clé -> numéro de ligne (à partir de 1) où elle est écrite."""
    lignes: dict


class _Chargeur(yaml.SafeLoader):
    def construire_dict(self, node):
        donnees = DictLignes()
        donnees.lignes = {}
        yield donnees
        donnees.update(self.construct_mapping(node))
        donnees.lignes.update(_lignes_du_bloc(node))


_Chargeur.add_constructor("tag:yaml.org,2002:map", _Chargeur.construire_dict)
# un dictionnaire lu par charger() peut être réécrit tel quel (safe_dump) comme un dict ordinaire
yaml.SafeDumper.add_representer(DictLignes, yaml.SafeDumper.represent_dict)


def _lignes_du_bloc(node: MappingNode) -> dict:
    return {cle.value: cle.start_mark.line + 1 for cle, _ in node.value
            if isinstance(cle, ScalarNode) and cle.tag != MERGE}


def _doublons(node, chemin: list[str], source: str, vus_ids: set[int]) -> None:
    """Parcourt l'arbre du document et lève `ErreurConfig` à la première clé écrite deux fois dans un même bloc."""
    if id(node) in vus_ids:
        return
    vus_ids.add(id(node))
    if isinstance(node, SequenceNode):
        for element in node.value:
            _doublons(element, chemin, source, vus_ids)
    elif isinstance(node, MappingNode):
        vues: dict[str, int] = {}
        for cle, valeur in node.value:
            if isinstance(cle, ScalarNode) and cle.tag != MERGE:
                numero = cle.start_mark.line + 1
                if cle.value in vues:
                    nom = ".".join(chemin + [cle.value])
                    raise ErreurConfig(f"{source} : « {nom} » est écrite deux fois (L{vues[cle.value]} et L{numero}) ; "
                                       "supprimer l'une des deux lignes.")
                vues[cle.value] = numero
            suite = chemin + [cle.value] if isinstance(cle, ScalarNode) else chemin
            _doublons(valeur, suite, source, vus_ids)


def charger(texte: str, source: str = "flux.yaml"):
    """Document YAML d'un texte (comme `yaml.safe_load`), mais une clé écrite deux fois dans un même bloc lève `ErreurConfig`.
    Un texte vide rend None. Une erreur de syntaxe reste une `yaml.YAMLError`."""
    chargeur = _Chargeur(texte)
    try:
        node = chargeur.get_single_node()
        if node is None:
            return None
        _doublons(node, [], source, set())
        return chargeur.construct_document(node)
    finally:
        chargeur.dispose()
