"""PMZilla Lab : noms des réglages de watch/tri.yaml (plan de la version anglaise, 7.6).

Les clés de tri.yaml ont un nom anglais (`model`, `to_read`, `days`, `substance_threshold`). Les anciens noms français
(`modele`, `a_lire`, `jours`, `seuil_substance`) ne sont plus acceptés : le chargement les refuse avec un message qui
donne le nom actuel. Les clés `mode`, `bluesky` et `themes` ne changent pas (`bluesky` va dans tri.local.yaml, jamais
dans tri.yaml). `migrate_text` (utilisé par `tools/migrate_watch.py`, l'outil de migration unique) réécrit le texte d'un
fichier existant en gardant commentaires et mise en page.

Rien dans ce module ne lit de fichier de lui-même : il reçoit un dictionnaire ou un texte.
"""
from __future__ import annotations

import re

from yaml_strict import ErreurConfig

# ancien nom -> nouveau nom
KEYS = {"modele": "model", "a_lire": "to_read", "jours": "days", "seuil_substance": "substance_threshold"}


def normalize(raw: dict | None, source: str = "tri.yaml") -> dict:
    """Réglages lus dans tri.yaml, sous leurs noms actuels. Un ancien nom est refusé (`ErreurConfig`) avec le nom
    actuel dans le message ; la valeur écrite n'y figure jamais."""
    lines = getattr(raw, "lignes", {})
    for key in (raw or {}):
        if key in KEYS:
            where = f"L{lines[key]} : " if key in lines else ""
            raise ErreurConfig(f"{source} : {where}le réglage « {key} » n'existe plus ; utiliser « {KEYS[key]} » "
                               "(`uv run tools/migrate_watch.py` réécrit le fichier).")
    return dict(raw or {})


_LINE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)(?P<rest>\s*:.*)$")


def migrate_text(text: str) -> tuple[str, list[str]]:
    """Réécrit les clés de premier niveau en nouveaux noms ; commentaires, ordre et mise en page conservés.

    Rend le texte et les changements (« LN : ancien -> nouveau »). Idempotent. Lève `ErreurConfig` si l'ancien et le
    nouveau nom du même réglage sont déjà tous deux présents."""
    present = {m["key"] for m in (_LINE.match(l) for l in text.split("\n")) if m}
    for old, new in KEYS.items():
        if old in present and new in present:
            raise ErreurConfig(f"tri.yaml : « {old} » et « {new} » sont le même réglage ; garder une seule des deux lignes.")
    out, changes = [], []
    for number, line in enumerate(text.split("\n"), start=1):
        m = _LINE.match(line)
        if m and m["key"] in KEYS:
            changes.append(f"L{number} : {m['key']} -> {KEYS[m['key']]}")
            line = KEYS[m["key"]] + m["rest"]
        out.append(line)
    return "\n".join(out), changes


# ---------------------------------------------------------------------------
# Notation en ombre (lot 5b) : réglage `shadow` de tri.yaml
# ---------------------------------------------------------------------------

SHADOW_KEYS = ("enabled", "language")
SHADOW_LANGUAGES = ("en",)


def shadow_settings(value, source: str = "tri.yaml") -> dict:
    """Réglage `shadow` validé : {"enabled": bool, "language": str}. Absent : désactivé.

    Clé inconnue, type faux ou langue inconnue lèvent `ErreurConfig`. Les messages donnent le nom de la clé et, quand
    on la connaît, son numéro de ligne, jamais la valeur écrite."""
    if value is None:
        return {"enabled": False, "language": SHADOW_LANGUAGES[0]}
    if not isinstance(value, dict):
        raise ErreurConfig(f"{source} : « shadow » doit être un bloc avec les clés {', '.join(SHADOW_KEYS)}.")
    lines = getattr(value, "lignes", {})

    def where(key) -> str:
        return f"L{lines[key]} : " if key in lines else ""

    for key in value:
        if key not in SHADOW_KEYS:
            raise ErreurConfig(f"{source} : {where(key)}shadow : clé « {key} » inconnue (clés admises : {', '.join(SHADOW_KEYS)}).")
    enabled = value.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ErreurConfig(f"{source} : {where('enabled')}shadow.enabled doit valoir true ou false.")
    language = value.get("language", SHADOW_LANGUAGES[0])
    if not isinstance(language, str) or language not in SHADOW_LANGUAGES:
        raise ErreurConfig(f"{source} : {where('language')}shadow.language doit être l'une des langues admises : "
                           f"{', '.join(SHADOW_LANGUAGES)}.")
    return {"enabled": enabled, "language": language}


# ---------------------------------------------------------------------------
# Lot 5b : langue des prompts de décision, seuil de pertinence, couche locale tri.local.yaml
# ---------------------------------------------------------------------------

LANGUAGES = ("fr", "en")
LOCAL_FILE = "tri.local.yaml"
LOCAL_KEYS = ("bluesky",)


def refuse_tracked_handle(raw, source: str = "tri.yaml") -> None:
    """`bluesky` n'est plus admis dans tri.yaml (fichier suivi par Git) : à mettre dans tri.local.yaml. Jamais la valeur
    dans le message."""
    if isinstance(raw, dict) and "bluesky" in raw:
        raise ErreurConfig(f"{source} : {_where(raw, 'bluesky')}le réglage « bluesky » n'est plus admis ici ; "
                           f"le mettre dans {LOCAL_FILE} (non suivi par Git).")


def _where(raw, key) -> str:
    lines = getattr(raw, "lignes", {})
    return f"L{lines[key]} : " if key in lines else ""


def language(raw, value, source: str = "tri.yaml") -> str:
    """Langue des prompts qui décident (`language`). Absente : fr. Jamais la valeur écrite dans le message."""
    if value is None:
        return LANGUAGES[0]
    if not isinstance(value, str) or value not in LANGUAGES:
        raise ErreurConfig(f"{source} : {_where(raw, 'language')}language doit valoir fr ou en.")
    return value


def relevance_threshold(raw, value, source: str = "tri.yaml") -> int:
    """Seuil de pertinence (`relevance_threshold`), entier de 0 à 100. Absent : 0, aucun filtre de pertinence."""
    if value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 100:
        raise ErreurConfig(f"{source} : {_where(raw, 'relevance_threshold')}"
                           "relevance_threshold doit être un entier de 0 à 100.")
    return value


def local_settings(raw, source: str = LOCAL_FILE) -> dict:
    """Couche locale non suivie : seules les clés de LOCAL_KEYS. Fichier vide : rien. Jamais de valeur dans le message."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ErreurConfig(f"{source} : le fichier doit être un bloc de clés ({', '.join(LOCAL_KEYS)}).")
    for key in raw:
        if key not in LOCAL_KEYS:
            raise ErreurConfig(f"{source} : {_where(raw, key)}clé « {key} » inconnue "
                               f"(clés admises : {', '.join(LOCAL_KEYS)}).")
    return dict(raw)
