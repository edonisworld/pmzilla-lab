"""PMZilla Lab : lecture des transcriptions de séance Claude Code pour tools/book_usage.py (R-52).

Ce module est le SEUL endroit qui connaît la structure des transcriptions. Elle est lue d'après le format JSON Lines documenté
de Claude Code et confirmée le 2026-10-17 par un relevé des noms de clés sur de vraies transcriptions (tâche 1.2 du change
posture-book-usage, design.md, question ouverte 1) ; si Claude Code change de format, seul ce fichier change. Hypothèses prises :

  - un enregistrement par ligne, objet JSON ; `type` vaut `user` ou `assistant`, les autres types sont ignorés ;
  - `message.content` est une chaîne, ou une liste de blocs : `text` (champ `text`), `tool_use` (`id`, `name`, `input`),
    `tool_result` (`tool_use_id`, `content` : chaîne ou liste de blocs `text`) ;
  - un message de l'utilisateur est un enregistrement `user` sans bloc `tool_result`, avec du texte, hors sous-agent
    (`isSidechain` faux) et hors méta (`isMeta` faux) ; un résultat d'outil est un enregistrement `user` de blocs `tool_result` ;
  - les enregistrements d'un sous-agent portent `isSidechain` vrai (dans le fichier de la séance ou dans un autre fichier du
    dossier du projet, avec le même `sessionId`) ; ils sont rattachés au tour dont ils suivent le message de l'utilisateur,
    dans l'ordre des `timestamp` (ordre du fichier à égalité) ;
  - le sous-agent Critic est lancé par un bloc `tool_use` de nom `Agent` ou `Task` dont `input.subagent_type` vaut
    `pmzilla-critic` ; faute de pouvoir relier un enregistrement de sous-agent à son lancement, les enregistrements de
    sous-agent d'un tour comptent pour Critic quand le tour n'a lancé que Critic, et ne comptent nulle part sinon ; la
    réponse de Critic est le texte du `tool_result` de cet appel de lancement (dans le fil principal, relié par `tool_use_id`),
    car le dernier texte des enregistrements du sous-agent est presque toujours vide ; faute de `tool_result`, repli sur le
    dernier texte non vide du sous-agent ;
  - le serveur de la bibliothèque s'appelle `mcp__pmzilla-library__<outil>` ; le résultat de `search_library` (forme relevée le 2026-10-17) est un
    texte JSON, en chaîne ou en liste d'un bloc `text`, dont l'objet de tête n'a que la clé `result`, valeur : la liste des
    passages ; `_objects` déballe cette enveloppe (et lit encore une liste d'objets, un bloc `text` JSON par objet, ou un seul
    bloc portant la liste) ; celui de `read_passage` est un objet portant directement `book`, `file` et `passages`.

Rien n'est conservé : le module renvoie des structures en mémoire que book_usage.py réduit à des comptes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

LIBRARY_SERVER = "mcp__pmzilla-library__"
SEARCH_TOOL = LIBRARY_SERVER + "search_library"
READ_TOOL = LIBRARY_SERVER + "read_passage"
LAUNCH_TOOLS = ("Agent", "Task")
CRITIC_AGENT = "pmzilla-critic"


@dataclass
class Call:
    id: str
    name: str
    results: list = field(default_factory=list)      # objets JSON renvoyés par l'outil (hits d'une recherche, ou la lecture)


@dataclass
class Record:
    role: str                       # "user" ou "assistant"
    sidechain: bool
    session: str
    timestamp: str
    prompt: bool = False            # message de l'utilisateur (début de tour)
    texts: list = field(default_factory=list)
    calls: list = field(default_factory=list)        # (id, name, input) des blocs tool_use
    results: dict = field(default_factory=dict)      # tool_use_id -> objets JSON du bloc tool_result
    result_texts: dict = field(default_factory=dict)  # tool_use_id -> texte du bloc tool_result (blocs text joints)


@dataclass
class Turn:
    session: str
    index: int
    day: str
    main_texts: list = field(default_factory=list)
    main_calls: list = field(default_factory=list)
    side_calls: list = field(default_factory=list)
    side_texts: list = field(default_factory=list)
    critic_results: list = field(default_factory=list)   # textes des tool_result des appels de lancement de Critic (fil principal)
    critic_launched: bool = False
    other_launched: bool = False

    @property
    def complete(self) -> bool:
        return any(t.strip() for t in self.main_texts)

    @property
    def critic_active(self) -> bool:
        """Les enregistrements de sous-agent du tour sont ceux de Critic (voir l'hypothèse dans l'en-tête)."""
        return self.critic_launched and not self.other_launched


def _blocks(content) -> list:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _objects(content) -> list:
    """Objets JSON portés par le contenu d'un tool_result (chaîne ou blocs texte, un objet ou une liste par bloc)."""
    found: list = []
    for block in _blocks(content):
        text = block.get("text")
        if not isinstance(text, str):
            continue
        try:
            value = json.loads(text)
        except ValueError:
            continue
        if isinstance(value, dict) and list(value) == ["result"] and isinstance(value["result"], list):
            value = value["result"]         # enveloppe de search_library : seule clé `result`, valeur = liste des passages
        found.extend(value if isinstance(value, list) else [value])
    return [o for o in found if isinstance(o, dict)]


def normalise(raw, fallback_session: str = "") -> Record | None:
    """Enregistrement normalisé, ou None pour un type ignoré. Lève ValueError sur une structure inattendue."""
    if not isinstance(raw, dict):
        raise ValueError("record is not an object")
    role = raw.get("type")
    if role not in ("user", "assistant"):
        return None
    message = raw.get("message")
    if not isinstance(message, dict):
        raise ValueError("record without message")
    record = Record(role=role, sidechain=bool(raw.get("isSidechain")), session=str(raw.get("sessionId") or fallback_session),
                    timestamp=str(raw.get("timestamp") or ""))
    has_result = False
    for block in _blocks(message.get("content")):
        kind = block.get("type")
        if kind == "text" and isinstance(block.get("text"), str):
            record.texts.append(block["text"])
        elif kind == "tool_use" and role == "assistant":
            record.calls.append((str(block.get("id")), str(block.get("name")), block.get("input") if isinstance(block.get("input"), dict) else {}))
        elif kind == "tool_result":
            has_result = True
            record.results[str(block.get("tool_use_id"))] = _objects(block.get("content"))
            record.result_texts[str(block.get("tool_use_id"))] = "\n".join(
                b["text"] for b in _blocks(block.get("content")) if isinstance(b.get("text"), str))
    record.prompt = (role == "user" and not record.sidechain and not raw.get("isMeta") and not has_result
                     and any(t.strip() for t in record.texts))
    return record


def _launch_kind(name: str, tool_input: dict) -> str | None:
    if name not in LAUNCH_TOOLS:
        return None
    return "critic" if tool_input.get("subagent_type") == CRITIC_AGENT else "other"


def turns_of(records: list[Record]) -> list[Turn]:
    """Tours d'une séance : de chaque message de l'utilisateur au suivant. `records` : dans l'ordre de lecture des fichiers."""
    last, keyed = "", []
    for position, record in enumerate(records):
        if record.timestamp:
            last = record.timestamp
        keyed.append((last, position, record))
    ordered = [r for _, _, r in sorted(keyed, key=lambda k: (k[0], k[1]))]
    results: dict = {}
    result_texts: dict = {}
    for record in ordered:
        results.update(record.results)
        result_texts.update(record.result_texts)
    turns: list[Turn] = []
    for record in ordered:
        if record.prompt:
            turns.append(Turn(session=record.session, index=len(turns), day=record.timestamp[:10]))
            continue
        if not turns or record.role != "assistant":
            continue
        turn = turns[-1]
        library = [Call(i, n, results.get(i, [])) for i, n, _ in record.calls if n in (SEARCH_TOOL, READ_TOOL)]
        if record.sidechain:
            turn.side_texts.extend(record.texts)
            turn.side_calls.extend(library)
            continue
        turn.main_texts.extend(record.texts)
        turn.main_calls.extend(library)
        for identifier, name, tool_input in record.calls:
            kind = _launch_kind(name, tool_input)
            if kind == "critic":
                turn.critic_launched = True
                if result_texts.get(identifier, "").strip():
                    turn.critic_results.append(result_texts[identifier])
            elif kind == "other":
                turn.other_launched = True
    return turns
