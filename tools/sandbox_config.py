"""Lecture partagée de la source du fichier géré du bac à sable (change bash-sandbox-n2, design D1, D7, D8, tâche 4.2).

Un seul lecteur de la source pour les tests statiques (tests/sandbox_config, S1 à S8) et pour le contrôle `sandbox` du doctor : ils lisent la
source de la même façon et en calculent la même empreinte. Bibliothèque seule (bibliothèque standard), aucun point d'entrée, aucune écriture,
aucune commande lancée.

 - SOURCE : config/gere/50-pmzilla-bac-a-sable.json, chemins relatifs au dossier personnel écrits « ~/ » ;
 - INSTALLE : le fichier géré posé par l'auteur, copie dont les « ~/ » sont développés (jamais un lien vers le dépôt) ;
 - l'empreinte compare le CONTENU (JSON canonique : clés triées, sans espace), jamais la mise en forme ni l'ordre des clés : l'empreinte
   des octets du fichier installé est celle que le fichier d'étape de l'auteur enregistre, un autre relevé ;
 - le relevé des outils figés (design D5) : un fichier `empreintes.sha256` du dossier `outils-figes`, une ligne « <sha256 en hexadécimal>
   deux espaces <nom relatif> » par fichier figé (la forme de `shasum -a 256`). Le fichier du relevé n'y est pas listé.

Remplace : rien. Condition de retrait : tombe avec le fichier géré (design D1).
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
from pathlib import Path

SOURCE_RELATIVE = "config/gere/50-pmzilla-bac-a-sable.json"
INSTALLE = "/Library/Application Support/ClaudeCode/managed-settings.d/50-pmzilla-bac-a-sable.json"
VERSION_MINIMALE = "2.1.319"
DOSSIER_FIGES = "outils-figes"
RELEVE_FIGES = "empreintes.sha256"
LIGNE_RELEVE = re.compile(r"^([0-9a-f]{64})  (\S.*)$")
TILDE = re.compile(r"(^|\s)~/")


def lire_source(racine) -> dict:
    """La source du fichier géré, telle quelle (chemins « ~/ »)."""
    return json.loads((Path(racine) / SOURCE_RELATIVE).read_text(encoding="utf-8"))


def dossier_personnel() -> str:
    """Le dossier personnel de l'utilisateur courant, lu dans la base des comptes (pwd.getpwuid), jamais par HOME ni os.path.expanduser (R-20261111-49).

    Même calcul que `dossier_personnel` de tools/garde_session.py, volontairement DUPLIQUÉ et non partagé : la garde est lancée par `python3 -I` depuis sa copie (D2), où
    `tools/` n'est pas importable, et un test de ses imports (suite garde_session) n'admet que la bibliothèque standard et deux modules frères ; l'importer ici
    tirerait un module de 1700 lignes dans le doctor. Une seule forme, brute (pw_dir sans realpath), dans la garde, ici, la sonde et le lanceur de tests ; le test
    `test_accord_des_valeurs_effectives_sur_le_dossier_personnel` (suite sandbox_config) compare leurs valeurs effectives : un écart se détecte là.
    Remplace : le développement de « ~ » par $HOME (ou par le dossier que l'appelant passe) dans `etendre`. Retrait : avec le bac à sable."""
    return pwd.getpwuid(os.getuid()).pw_dir


def etendre(valeur, maison=None):
    """Développe « ~/ » (en tête d'une chaîne ou après une espace, comme dans « bash ~/… ») en `<maison>/` dans toute la structure.

    Sans `maison` (R-20261111-49) : le dossier personnel de la base des comptes (`dossier_personnel`), jamais HOME : un HOME falsifié dans l'environnement ne change pas les
    motifs développés. Un `maison` explicite reste admis (tests ; appelants qui le calculent eux-mêmes). Remplace : le développement par $HOME. Retrait : avec le bac à sable."""
    return _developper(valeur, str(maison if maison is not None else dossier_personnel()).rstrip("/"))


def _developper(valeur, dossier):
    if isinstance(valeur, str):
        return TILDE.sub(lambda m: f"{m.group(1)}{dossier}/", valeur)
    if isinstance(valeur, list):
        return [_developper(v, dossier) for v in valeur]
    if isinstance(valeur, dict):
        return {cle: _developper(v, dossier) for cle, v in valeur.items()}
    return valeur


def canonique(objet) -> str:
    return json.dumps(objet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def empreinte(objet) -> str:
    """SHA-256 (hexadécimal) du JSON canonique d'une structure."""
    return hashlib.sha256(canonique(objet).encode("utf-8")).hexdigest()


def empreinte_source(racine) -> str:
    """Empreinte de la source développée pour le dossier personnel de la base des comptes : celle que doit avoir le fichier installé, lu de la même façon.
    Plus de paramètre `maison` (R-20261111-51, -52) : aucun appelant de production ne choisit le dossier."""
    return empreinte(etendre(lire_source(racine)))


def empreinte_installe(chemin) -> str | None:
    """Empreinte du contenu du fichier installé ; None si illisible ou si ce n'est pas du JSON."""
    try:
        return empreinte(json.loads(Path(chemin).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def lire_releve(dossier) -> dict | None:
    """{nom relatif: sha256} du relevé du dossier des outils figés ; None si le relevé manque, est illisible ou mal formé."""
    try:
        lignes = (Path(dossier) / RELEVE_FIGES).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    releve = {}
    for ligne in lignes:
        if not ligne.strip():
            continue
        trouve = LIGNE_RELEVE.match(ligne)
        if not trouve:
            return None
        releve[trouve.group(2)] = trouve.group(1)
    return releve or None


def empreinte_fichier(chemin) -> str | None:
    try:
        return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()
    except OSError:
        return None


# R-20261111-19, -22, -29 (design D13) : la forme unique `/bin/bash --noprofile --norc -p <chemin>`. Remplace : le lecteur de la forme `bash <chemin>`.
# Retrait : avec le fichier géré. Un test fait échouer un motif de la source que ce lecteur ne lit pas, et un ensemble de noms vide.
EXCLUE_FIGE = re.compile(rf"^/bin/bash --noprofile --norc -p \S*/{re.escape(DOSSIER_FIGES)}/(\S+)")


def noms_figes_attendus(racine) -> set[str]:
    """Les enveloppes que la source exclut du bac à sable (`excludedCommands`) : chacune doit figurer au relevé (une seule source des noms)."""
    noms = set()
    for motif in lire_source(racine)["sandbox"]["excludedCommands"]:
        trouve = EXCLUE_FIGE.match(motif)
        if trouve:
            noms.add(trouve.group(1))
    return noms


def ecarts_releve(dossier, racine=None) -> list[str]:
    """Noms des outils figés dont la copie diffère du relevé (absente comprise) ou qui manquent au relevé alors que la source les exclut du bac
    à sable ; le nom du relevé lui-même quand il manque ou est illisible. `racine` : le dépôt dont lire la source (par défaut celui de ce module)."""
    releve = lire_releve(dossier)
    if releve is None:
        return [RELEVE_FIGES]
    attendus = noms_figes_attendus(racine if racine is not None else Path(__file__).resolve().parents[1])
    differents = {nom for nom, attendue in releve.items() if empreinte_fichier(Path(dossier) / nom) != attendue}
    return sorted(differents | (attendus - set(releve)))


def sous_chaines(valeur):
    """Toutes les chaînes d'une structure JSON (les clés des dictionnaires aussi)."""
    if isinstance(valeur, str):
        yield valeur
    elif isinstance(valeur, list):
        for v in valeur:
            yield from sous_chaines(v)
    elif isinstance(valeur, dict):
        for cle, v in valeur.items():
            yield cle
            yield from sous_chaines(v)


# Voie A (design D11, D12, D14 ; R-20261112-41, -45, -49) : les huit règles `Edit` globales du fragment 27 que la voie A remplace par des règles sur les chemins
# sensibles de l'espace. Liste de référence UNIQUE de ces huit règles pour `controle_voie_a` ; le test de `tests/settings_deny` (voie A) la compare à la sienne : un écart
# se détecte là. Remplace : rien. Retrait : avec le fichier géré.
REGLES_EDIT_GLOBALES_27 = (
    "Edit(./.git/**)", "Edit(//**/.git/**)", "Edit(~/**/.git/**)", "Edit(**/.git/**)",
    "Edit(./.git)", "Edit(//**/.git)", "Edit(~/**/.git)", "Edit(**/.git)",
)
LIGNE_VOIE_A_NON_POSEE = "repetition : refusé : voie A non posée dans les réglages assemblés (fragment 27)"


def _regles_deny(reglages) -> list[str]:
    """permissions.deny d'un objet de réglages ; liste vide sans `permissions` ou sans `deny` ; ValueError si la forme est mauvaise (jamais un faux « rien à convertir »)."""
    if not isinstance(reglages, dict):
        raise ValueError("réglages : objet JSON attendu")
    permissions = reglages.get("permissions", {})
    if not isinstance(permissions, dict):
        raise ValueError("réglages : `permissions` doit être un objet")
    deny = permissions.get("deny", [])
    if not isinstance(deny, list) or not all(isinstance(regle, str) for regle in deny):
        raise ValueError("réglages : `permissions.deny` doit être une liste de chaînes")
    return list(deny)


def regles_converties(reglages) -> list[str]:
    """Les règles `Edit(…)` et `Read(…)` de permissions.deny des réglages assemblés, dans l'ordre : les entrées que Claude Code convertit en denyWrite et en denyRead sous le
    bac à sable (design D11, journal de la répétition). Jamais une règle `Bash(…)`, `Write(…)` ni `NotebookEdit(…)`. Lecture seule, rien lancé.
    Remplace : rien. Retrait : avec le fichier géré."""
    return [regle for regle in _regles_deny(reglages) if regle.startswith(("Edit(", "Read("))]


def controle_voie_a(reglages, declarees) -> list[str]:
    """Les refus de `repetition` pour la voie A (design D11, D12, D14) : une liste vide si les règles `Edit` rétrécies `declarees` (la liste `--json` du fragment 27) sont TOUTES dans
    les réglages assemblés et qu'aucune des huit règles `Edit` globales (REGLES_EDIT_GLOBALES_27) n'y reste ; sinon la seule ligne de D12 qui nomme « voie A », qui ne nomme ni règle
    ni chemin. Absente, partielle ou avec une règle globale restante : le même refus (code 3 du fichier d'étape, qui n'imprime que ce résultat).
    `declarees` vide ou qui n'est pas une liste de chaînes lève ValueError : « tout est posé » serait vrai à vide.
    Remplace : rien. Retrait : avec la sonde (D11)."""
    if not isinstance(declarees, (list, tuple)) or not declarees or not all(isinstance(r, str) for r in declarees):
        raise ValueError("règles Edit déclarées : liste de chaînes non vide attendue")
    deny = set(_regles_deny(reglages))
    if any(regle not in deny for regle in declarees) or any(regle in deny for regle in REGLES_EDIT_GLOBALES_27):
        return [LIGNE_VOIE_A_NON_POSEE]
    return []


def environnement_gere(racine) -> dict[str, str]:
    """Les variables de la clé `env` de la source du fichier géré (design D16 (2), tâche 28.4), noms et valeurs : lues dans la source à chaque appel, jamais une liste copiée
    dans le fichier d'étape ni dans un test. Sans clé `env`, un dictionnaire vide. ValueError si `env` n'est pas un objet de chaînes. Le dictionnaire rendu est une copie.
    Remplace : rien. Retrait : avec le fichier géré."""
    env = lire_source(racine).get("env", {})
    if not isinstance(env, dict) or not all(isinstance(nom, str) and isinstance(valeur, str) for nom, valeur in env.items()):
        raise ValueError("source du fichier géré : `env` doit être un objet de chaînes")
    return dict(env)


def version_en_tuple(texte: str) -> tuple | None:
    """« 2.1.319 » -> (2, 1, 319) ; un préfixe `v` est toléré ; None si illisible."""
    trouve = re.fullmatch(r"v?(\d+(?:\.\d+)*)", texte.strip())
    return tuple(int(p) for p in trouve.group(1).split(".")) if trouve else None
