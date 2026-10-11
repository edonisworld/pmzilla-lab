"""PMZilla Lab : noms des réglages de Flux-Lab/flux.yaml (plan de la version anglaise, 7.6).

Les clés de flux.yaml ont un nom anglais. Les anciens noms français sont refusés (arrêt avec un message qui donne le nom
actuel). Les scripts travaillent encore avec les noms français internes : `to_internal` lit les noms anglais et rend les
noms internes, `to_public` fait l'inverse (pour écrire les réglages par défaut), `migrate_text` réécrit un flux.yaml
d'avant le lot 8 dans les nouveaux noms en gardant ses commentaires et sa mise en page (les tables ci-dessous servent à
la migration et au message de refus).

    uv run tools/flux_jira.py config migrate [--dry-run]    réécrit Flux-Lab/flux.yaml (à lancer par l'utilisateur)

Rien dans ce module ne lit Flux-Lab/ de lui-même : il reçoit un dictionnaire ou un texte.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from yaml_strict import ErreurConfig

# ancien nom (interne, français) -> nouveau nom
TOP = {
    "colonnes": "columns",
    "etats_en_cours": "in_progress_states",
    "etats_a_faire": "todo_states",
    "etats_attente": "waiting_states",
    "motifs_exclus": "excluded_resolutions",
    "types_portefeuille": "portfolio_types",
    "projets_exclus": "excluded_projects",
    "projets_perimetre": "scope_projects",
    "segments": "segments",
    "segments_hors_calcul": "uncounted_segments",
    "point_engagement": "commitment_point",
    "separateur_equipes": "team_separator",
    "seuil_fermetures_groupees": "batch_closure_threshold",
    "motifs_fermetures_groupees": "batch_closure_resolutions",
    "serie_par_defaut": "default_series",
    "noms_projets": "project_names",
    "tableaux": "boards",
    "jira_jeton": "jira_token_type",
    "export_champ_equipe": "export_team_field",
    "export_entete_equipe": "export_team_header",
    "export_champ_verification": "export_verification_field",
    "export_entete_verification": "export_verification_header",
    "export_fuseau": "export_timezone",
    "types_bloquants": "blocking_link_types",
    "types_attente": "waiting_link_types",
}
# réglages supprimés : l'export de l'API a un format de date fixe (history_common.FORMAT_DATE). Les deux noms sont refusés.
REGLAGES_IGNORES = {"format_date", "date_format"}
# noms français de colonnes qui étaient dans les listes par défaut (export manuel de Jira), supprimés avec l'export
# manuel : refusés, comparés sans casse, quand flux.yaml les redonne dans `columns`. Tout autre nom de colonne donné dans
# `columns` est un ajout légitime et reste.
ALIAS_COLONNES_SUPPRIMES = {n.casefold() for n in (
    "Type de ticket", "État", "Etat", "Statut", "Catégorie d'état", "Catégorie de statut", "Clé", "Clé de ticket",
    "Clé du ticket", "Créé", "Création", "Résolu", "Résolution (date)", "Résolution", "Catégorie d'état modifiée",
    "Équipe", "Equipe", "Composants", "Mis à jour", "Mise à jour", "Modifié", "Points d'histoire", "Clé parente")}
# anciens noms d'avant 7.6, refusés (et migrés par `config migrate`) : ils vont vers le même réglage interne
ANCIENS_ALIAS = {"types_exclus": "types_portefeuille"}
# clés qui ne changent pas
INCHANGEES = {"jira_site", "jira_email", "jql_export", "jql_exports", "export_points_field",
              "flow_views_min_cell"}

COLUMNS = {"type": "type", "etat": "status", "categorie": "category", "cle": "key", "cree": "created",
           "resolu": "resolved", "motif": "resolution", "debut": "category_changed", "equipe": "team",
           "parent": "parent", "modifie": "updated", "story_points": "story_points"}
SEGMENTS = {"definition": "definition", "pret": "ready", "implementation": "implementation",
            "revue_verification": "review_verification", "acceptation": "acceptance"}
UNCOUNTED = {"a_faire": "todo", "termine": "done"}
BOARDS = {"series": "series"}
BOARD = {"nom": "name", "dependances": "dependencies", "dependances_projets": "project_dependencies", "base": "baseline"}
# valeurs renommées : réglage interne -> {ancienne valeur: nouvelle valeur}
VALEURS = {"point_engagement": SEGMENTS, "jira_jeton": {"scopes": "scoped", "classique": "classic"}}

# sous-clés d'un réglage : (réglage interne, niveau) -> table
SOUS_TABLES = {"colonnes": COLUMNS, "segments": SEGMENTS, "segments_hors_calcul": UNCOUNTED, "tableaux": BOARDS}

# Options renommées communes à plusieurs scripts (plan 7.5) : ancien nom -> nouveau nom
OPTIONS_COMMUNES = {"--nom": "--name", "--perimetre": "--scope", "--semaines": "--weeks", "--historique": "--history",
                    "--aujourdhui": "--today", "--sortie": "--output", "--ouvrir": "--open",
                    "--anonyme": "--anonymous", "--langue": "--language", "--equipe": "--team"}

def refuse_old_options(argv: list[str], table: dict[str, str]) -> list[str]:
    """Refuse les anciens noms d'options (`--cle`, aussi sous la forme `--cle=valeur`) : arrêt avec le code 2 et un message
    qui donne le nom actuel. Les noms actuels passent sans message ; tout ce qui suit `--` est laissé tel quel."""
    for i, argument in enumerate(argv):
        if argument == "--":
            break
        nom = argument.partition("=")[0]
        if nom in table:
            print(f"PMZilla Lab, erreur : l'option « {nom} » n'existe plus ; utiliser « {table[nom]} ».", file=sys.stderr)
            raise SystemExit(2)
    return list(argv)


def _inverse(table: dict[str, str]) -> dict[str, str]:
    return {nouveau: ancien for ancien, nouveau in table.items()}




def _refus(source: str, lignes: dict, cle: str, chemin: str, message: str) -> ErreurConfig:
    """Refus d'un ancien nom : la ligne (quand le fichier vient de `charger`), puis ce qu'il faut écrire. Jamais une valeur."""
    ligne = lignes.get(cle)
    return ErreurConfig(f"{source} : {f'L{ligne} : ' if ligne else ''}{message} "
                        "(`uv run tools/flux_jira.py config migrate` réécrit le fichier).")


def _cle_interne(cle: str, table_publique: dict[str, str], chemin: str, source: str, lignes: dict) -> str:
    """Nom interne (français) d'une clé donnée sous le nom actuel ; l'ancien nom est refusé."""
    inverse = _inverse(table_publique)
    if cle in inverse and inverse[cle] != cle:             # nom actuel
        return inverse[cle]
    if cle in table_publique and table_publique[cle] != cle:   # ancien nom
        raise _refus(source, lignes, cle, chemin,
                     f"« {chemin}{cle} » n'existe plus ; utiliser « {chemin}{table_publique[cle]} »")
    return cle


def _valeur_interne(reglage: str, valeur, source: str, lignes: dict, cle: str):
    table = VALEURS.get(reglage)
    if not table or not isinstance(valeur, str):
        return valeur
    if valeur in _inverse(table) and _inverse(table)[valeur] != valeur:
        return _inverse(table)[valeur]
    if valeur in table and table[valeur] != valeur:
        raise _refus(source, lignes, cle, "", f"valeur « {valeur} » du réglage {TOP.get(reglage, reglage)} n'existe plus ; utiliser « {table[valeur]} »")
    return valeur


def to_internal(raw: dict | None, source: str = "flux.yaml", warn: bool = True) -> dict:
    """Réglages lus dans un fichier, sous les noms actuels, rendus avec les noms internes.

    Un ancien nom (réglage, sous-clé, valeur, colonne française), à n'importe quel niveau, lève `ErreurConfig` avec le nom
    actuel. Si `raw` vient de `yaml_strict.charger`, le message donne le numéro de ligne. `warn` est gardé pour les appelants
    existants et ne sert plus."""
    return _vers_interne(raw, source)


def _vers_interne(raw: dict | None, source: str) -> dict:
    sortie: dict = {}
    lignes = getattr(raw, "lignes", {})
    for cle, valeur in (raw or {}).items():
        if cle in REGLAGES_IGNORES:
            raise _refus(source, lignes, cle, "", f"« {cle} » n'existe plus : l'export de l'API a un format de date fixe ; "
                         "supprimer la ligne")
        if cle in ANCIENS_ALIAS:
            raise _refus(source, lignes, cle, "", f"« {cle} » n'existe plus ; utiliser « {TOP[ANCIENS_ALIAS[cle]]} »")
        interne = _cle_interne(cle, TOP, "", source, lignes)
        if interne in SOUS_TABLES and isinstance(valeur, dict):
            table = SOUS_TABLES[interne]
            convertie = {}
            sous_lignes = getattr(valeur, "lignes", {})
            for sous, contenu in valeur.items():
                nom = _cle_interne(sous, table, f"{cle}.", source, sous_lignes)
                if interne == "tableaux" and nom == "series" and isinstance(contenu, list):
                    contenu = [_serie_interne(s, source, f"{cle}.{sous}.") for s in contenu]
                convertie[nom] = contenu
            valeur = _sans_alias_francais(convertie, source, sous_lignes) if interne == "colonnes" else convertie
        else:
            valeur = _valeur_interne(interne, valeur, source, lignes, cle)
        sortie[interne] = valeur
    return sortie


def _sans_alias_francais(colonnes: dict, source: str, lignes: dict) -> dict:
    """Refuse dans `columns` les anciens noms français de colonnes (liste ALIAS_COLONNES_SUPPRIMES). Les autres noms (nom
    de la colonne d'équipe, par exemple) sont gardés."""
    for champ, noms in colonnes.items():
        if isinstance(noms, list):
            for n in noms:
                if isinstance(n, str) and n.strip().casefold() in ALIAS_COLONNES_SUPPRIMES:
                    raise ErreurConfig(f"{source} : « {n.strip()} » n'existe plus dans `columns` : l'export de l'API a des "
                                       "en-têtes fixes en anglais ; `columns` ne sert qu'à ajouter d'autres noms.")
    return colonnes


def _serie_interne(serie, source: str, chemin: str):
    if not isinstance(serie, dict):
        return serie
    lignes = getattr(serie, "lignes", {})
    return {_cle_interne(k, BOARD, chemin, source, lignes): v for k, v in serie.items()}


def to_public(interne: dict) -> dict:
    """Réglages internes -> noms anglais (écriture du fichier de réglages par défaut)."""
    sortie: dict = {}
    for cle, valeur in interne.items():
        nouveau = TOP.get(cle, cle)
        if cle in SOUS_TABLES and isinstance(valeur, dict):
            table = SOUS_TABLES[cle]
            valeur = {table.get(k, k): (([{BOARD.get(a, a): b for a, b in s.items()} if isinstance(s, dict) else s
                                          for s in v] if cle == "tableaux" and isinstance(v, list) else v))
                      for k, v in valeur.items()}
        elif cle in VALEURS and isinstance(valeur, str):
            valeur = VALEURS[cle].get(valeur, valeur)
        sortie[nouveau] = valeur
    return sortie


# ---------------------------------------------------------------------------
# Migration d'un flux.yaml existant (texte, commentaires conservés)
# ---------------------------------------------------------------------------

LIGNE_CLE = re.compile(r"^(?P<indent>\s*)(?P<tiret>- )?(?P<cle>[A-Za-z_][A-Za-z0-9_]*)(?P<reste>\s*:.*)$")


class MigrationConflict(Exception):
    """Deux clés du même bloc donneraient la même clé après migration (ou une clé est écrite deux fois) : rien n'est
    écrit. `conflits` : phrases sans valeurs (numéros de ligne et noms de clés) ; `changements` : ce qui aurait été fait."""

    def __init__(self, conflits: list[str], changements: list[str]):
        super().__init__("; ".join(conflits))
        self.conflits = conflits
        self.changements = changements


def migrate_analysis(texte: str) -> tuple[str, list[str], list[str]]:
    """Réécrit les clés (et les valeurs de `commitment_point` et `jira_token_type`) en nouveaux noms.

    Rend le texte, les changements (« LN : chemin.de.la.clé -> nouveau », le chemin tel qu'il est écrit dans le
    fichier, sans valeurs) et les conflits (deux clés d'un même bloc qui donnent le même nom, ou une clé en double). Idempotent :
    un fichier déjà migré ne change pas. Les commentaires, l'ordre et la mise en page sont conservés."""
    sortie: list[str] = []
    changements: list[str] = []
    conflits: list[str] = []
    pile: list[tuple[int, str, str, int]] = []        # (colonne de la clé, nom interne, nom écrit, numéro de ligne)
    vus: dict[tuple, dict[str, tuple[int, str]]] = {}   # bloc -> {nom après migration: (ligne, nom écrit)}
    item = 0                                           # ligne du dernier « - » (entrée d'une liste de séries)
    interne_de = {**{v: k for k, v in TOP.items()}, **{k: k for k in TOP}}
    for numero, ligne in enumerate(texte.split("\n"), start=1):
        m = None if ligne.lstrip().startswith("#") else LIGNE_CLE.match(ligne)
        if not m:
            sortie.append(ligne)
            continue
        colonne = len(m["indent"]) + (2 if m["tiret"] else 0)
        while pile and pile[-1][0] >= colonne:
            pile.pop()
        chemin = tuple(nom for _, nom, _, _ in pile)
        ecrit = ".".join(nom for _, _, nom, _ in pile)
        cle = m["cle"]
        if m["tiret"]:
            item = numero
        nouveau, interne, connue = cle, cle, False
        if not chemin:
            interne = ANCIENS_ALIAS.get(interne_de.get(cle, cle), interne_de.get(cle, cle))
            connue = cle in TOP or cle in TOP.values() or cle in ANCIENS_ALIAS or cle in INCHANGEES
            nouveau = TOP.get(interne, cle) if cle in TOP or cle in ANCIENS_ALIAS else cle
        elif len(chemin) == 1 and chemin[0] in SOUS_TABLES:
            table = SOUS_TABLES[chemin[0]]
            interne = {**_inverse(table), **{k: k for k in table}}.get(cle, cle)
            connue = cle in table or cle in table.values()
            nouveau = table.get(interne, cle)
        elif chemin == ("tableaux", "series"):
            interne = {**_inverse(BOARD), **{k: k for k in BOARD}}.get(cle, cle)
            connue = cle in BOARD or cle in BOARD.values()
            nouveau = BOARD.get(interne, cle)
        if connue:
            bloc = (pile[-1][3] if pile else 0, item if chemin == ("tableaux", "series") else 0)
            deja = vus.setdefault(bloc, {}).get(nouveau)
            if deja:
                memes = deja[1] == cle
                conflits.append(f"L{deja[0]} et L{numero} : "
                                + (f"« {(ecrit + '.' if ecrit else '') + cle} » est écrite deux fois" if memes else
                                   f"« {(ecrit + '.' if ecrit else '') + deja[1]} » et « {(ecrit + '.' if ecrit else '') + cle} » "
                                   f"donnent la même clé « {nouveau} »"))
            else:
                vus[bloc][nouveau] = (numero, cle)
        reste = m["reste"]
        if not chemin and interne in VALEURS:
            reste = _migrer_valeur(interne, reste, changements, numero)
        if nouveau != cle:
            changements.append(f"L{numero} : {(ecrit + '.' if ecrit else '') + cle} -> {nouveau}")
        sortie.append(f"{m['indent']}{m['tiret'] or ''}{nouveau}{reste}")
        pile.append((colonne, interne, cle, numero))
    return "\n".join(sortie), changements, conflits


def migrate_text(texte: str) -> tuple[str, list[str]]:
    """`migrate_analysis` sans les conflits : s'il y en a, lève `MigrationConflict` (rien ne doit être écrit)."""
    nouveau, changements, conflits = migrate_analysis(texte)
    if conflits:
        raise MigrationConflict(conflits, changements)
    return nouveau, changements


def _migrer_valeur(interne: str, reste: str, changements: list[str], numero: int) -> str:
    m = re.match(r"^(\s*:\s*)(['\"]?)([A-Za-z_]+)(['\"]?)(\s*(?:#.*)?)$", reste)
    if not m:
        return reste
    ancienne = m[3]
    nouvelle = VALEURS[interne].get(ancienne)
    if nouvelle is None or nouvelle == ancienne:
        return reste
    changements.append(f"L{numero} : valeur de {interne} : {ancienne} -> {nouvelle}")
    return f"{m[1]}{m[2]}{nouvelle}{m[4]}{m[5]}"


def migrate_file(chemin: Path, dry_run: bool = False) -> list[str]:
    """Réécrit un flux.yaml en nouveaux noms ; garde l'ancien à côté (`flux.yaml.avant-migration`). Aucune valeur
    n'est affichée : seulement les noms de clés changés."""
    texte = chemin.read_text(encoding="utf-8")
    nouveau, changements = migrate_text(texte)          # MigrationConflict : rien n'est écrit
    if changements and not dry_run:
        sauvegarde = chemin.with_name(chemin.name + ".avant-migration")
        if not sauvegarde.exists():
            shutil.copy2(chemin, sauvegarde)
        chemin.write_text(nouveau, encoding="utf-8")
    return changements
