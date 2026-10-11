# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx", "numpy", "pyyaml", "feedparser", "trafilatura", "beautifulsoup4", "markdownify", "mcp>=1.2,<2", "psycopg[binary]"]
# ///
"""
PMZilla Lab — pré-tri de la veille par le modèle local.

Pour chaque article de la collection « watch » (« veille » avant la migration) :
- pertinence : proximité (bge-m3) avec les articles que vous avez passés dans SignalPM, en rang
  sur 100. Elle sert au classement de _to-read.md, jamais au filtre ;
- jugement du modèle local (Ollama), chaque réponse justifiée par le texte : l'article relève-t-il
  de vos thèmes, est-ce une compilation, est-ce un contenu promotionnel, et une grille de
  substance de 5 critères oui/non ;
  plus un résumé de deux phrases et ce que l'article apporte à vos thèmes.
Entrent dans la bibliothèque les articles dans vos thèmes, ni compilations ni contenus
promotionnels, dont la substance atteint le seuil.

Commandes :

    uv run watch_triage.py references --claude-export conversations-000.zip [projects-000.zip]
        Construit la référence de votre goût : les réponses de SignalPM (une par lien partagé)
        et vos propres articles (collection personnelle). À relancer de temps en temps.

    uv run watch_triage.py score [--limit N] [--rescore]
        Note les articles de Watch-Lab/watch/ pas encore notés.

    uv run watch_triage.py shares [--pages 3]
        Lit vos posts Bluesky récents (identifiant « bluesky » dans tri.yaml) : un article de la
        veille que vous avez partagé est marqué « partagé », sort des « à lire » et rejoint la
        référence de pertinence.

    uv run watch_triage.py week [--days 7] [--max 40]
        Écrit Watch-Lab/_semaine.md : les articles retenus de la période (titre, source, lien,
        résumé), point de départ de la synthèse hebdomadaire (/watch-digest dans Claude Code).

    uv run watch_triage.py digest
        Écrit Watch-Lab/_to-read.md : les N articles à lire, le reste classé, et ce que
        le filtre écarterait (ou a écarté) de la bibliothèque.

    uv run watch_triage.py calibration
        Écrit Watch-Lab/_calibration.csv : remplissez la colonne « avis » (g = garder,
        e = écarter) sur une vingtaine d'articles variés.

    uv run watch_triage.py thresholds
        Compare vos avis aux seuils possibles et propose les meilleurs.

    uv run watch_triage.py shadow-report [--limit 20]
        Notation « en ombre » (lot 5b anglais) : avec `shadow: {enabled: true, language: en}` dans tri.yaml, chaque
        article noté par `score` l'est une seconde fois avec les prompts et thèmes anglais (tools/watch_prompts_en.py),
        même modèle ; les notes vont dans la table shadow_scores de tri.sqlite et ne servent à AUCUNE décision (filtre,
        seuils, _to-read.md, écartés). Ce rapport, dans le Terminal seulement, compare les deux langues : articles
        notés dans les deux, accord garder/écarter au seuil actuel, écart des notes, accord avec vos avis de calibration,
        repêchages et rejets, liste des désaccords. Il n'écrit aucun fichier.

    uv run watch_triage.py shadow-backfill [--limit N]
        Rattrape l'ombre : note en anglais (mêmes prompts, thèmes et modèle que l'ombre quotidienne) les articles DÉJÀ notés en
        français, bibliothèque et écartés, qui n'ont pas de note en ombre ou une note faite avec d'autres prompts. N'écrit que dans
        shadow_scores : aucune note française, aucun seuil, ni _to-read.md ni écartés ne changent. Les articles qui ont un avis g ou e
        dans _calibration.csv passent d'abord. Reprise après interruption : un article déjà noté n'est pas renoté. Lancement par
        l'utilisateur seul, pas pendant la veille du matin (aucun verrou) ; compter de l'ordre d'une heure pour environ 190 articles.

    uv run watch_triage.py apply
        En mode « filtre » seulement : sort de la bibliothèque les articles écartés
        (déplacés dans Watch-Excluded/, à côté de Watch-Lab, jamais supprimés).

    uv run watch_triage.py restore <fichier.md>
        Remet un article écarté dans la bibliothèque et le protège des tris suivants.

    uv run watch_triage.py exclude <fichier.md>
        Écarte à la main un article que le modèle garde à tort.

    uv run watch_triage.py suggestions [--min 2] [--max 30] [--reset]
        Propose dans sources.yaml (active: false) les sources citées par au moins 2 articles
        retenus, venant d'au moins 2 sources différentes (ou d'une compilation). Pages d'accueil,
        images, outils et boutiques sont ignorés. Les liens viennent de la collecte (watch_lab.py links pour
        les articles déjà collectés).

Réglages : ~/PMZilla-Lab/workspace/watch/tri.yaml (veille/ tant que le dossier n'est pas migré ; créé au premier lancement).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib
import json
import re
import shutil
import sqlite3
import sys
import time
import types
from pathlib import Path

import httpx
import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pmzilla_lab_library as library  # noqa: E402  (embed, OLLAMA_URL, DATA_DIR)
import watch_paths  # noqa: E402
import watch_config  # noqa: E402  (noms des clés de tri.yaml)
import flux_config  # noqa: E402
import watch_lab as veille  # noqa: E402  (dossiers, lecture de l'export Claude)
from yaml_strict import charger  # noqa: E402

CONFIG_FILE = veille.SOURCES_FILE.parent / "tri.yaml"
TRI_DB = library.DATA_DIR / "tri.sqlite"
ARCHIVE_DIR = watch_paths.excluded_dir(veille.WATCH_DIR.parent) / veille.ARTICLES_DIR.name   # à côté de Watch-Lab, dans le workspace, hors de l'index
OWN_DIR = veille.WATCH_DIR / watch_paths.OWN_COLLECTION

# Anciens noms d'options, refusés avec le nom actuel (plan 7.5)
OLD_OPTIONS = {"--enregistrer": "--save", "--jours": "--days", "--par-collecte": "--per-run",
               "--promotionnels": "--promotional", "--sans-modele": "--no-model",
               "--substance-max": "--max-substance"}

EMBED_CHARS = 4000      # début de l'article utilisé pour la pertinence
JUDGE_CHARS = 12000     # texte donné au modèle local (environ 3 000 tokens)
NEIGHBOURS = 3          # pertinence = moyenne des 3 références les plus proches
JUDGE_TIMEOUT = 180     # secondes ; au-delà, l'article est repris au passage suivant

DEFAULT_CONFIG = """\
# Pré-tri de la veille (watch_triage.py)
mode: observation        # observation : rien ne sort de la bibliothèque ; filtre : les articles écartés en sortent
model: gemma4:26b        # modèle Ollama qui remplit la grille de substance
to_read: 5               # articles mis en avant chaque jour
language: fr             # langue des prompts qui notent les articles : fr ou en
# Votre identifiant Bluesky (vos partages affinent la pertinence) va dans tri.local.yaml, à côté, non suivi par Git :
# une seule ligne « bluesky: prenom.bsky.social ».
days: 7                  # période couverte par _to-read.md
substance_threshold: 3   # nombre minimal de critères remplis sur 5
themes:
  - discovery produit et expérimentation
  - flux, métriques de flux et prédictibilité
  - Product Operating Model et transformation produit
  - organisation multi-équipes, Team Topologies, dépendances
  - OKR, priorisation, stratégie produit
  - plateformes internes et developer experience
  - coaching agile, facilitation, posture de Scrum Master
  - IA dans le travail produit
shadow:                  # notation « en ombre » avec les prompts anglais (lot 5b) : mesure seulement, ne décide rien
  enabled: false         # true : chaque article noté l'est une seconde fois en anglais (voir shadow-report)
  language: en
"""

CRITERIA = {  # clé : (question posée au modèle, raison affichée quand le critère manque)
    "these": ("L'article défend une idée centrale ou une position claire (une FAQ ou un entretien peut en avoir une).",
              "pas de position claire"),
    "etaye": ("Les affirmations sont étayées par des données, des cas concrets ou des retours d'expérience.",
              "affirmations non étayées"),
    "original": ("L'article apporte un point de vue propre, pas une reformulation de notions connues.",
                 "reformulation de notions connues"),
    "sources": ("L'article cite des sources, des auteurs ou des études identifiables.", "aucune source citée"),
    "non_promo": ("L'article n'est ni promotionnel, ni une liste générique de conseils.",
                  "promotionnel ou liste générique"),
}

SYSTEM_PROMPT = """Tu évalues des articles pour la bibliothèque d'un Agile Lead qui accompagne une \
organisation dans sa transformation produit. Ses thèmes : {themes}.
Évalue chaque critère séparément, à partir du texte seulement : un article peut en remplir certains et pas \
d'autres. Un critère n'est vrai que si l'article le remplit nettement.
Écris en français, mais garde les termes anglais du métier tels quels (product manager, discovery, delivery, \
outcome, roadmap, build to learn…). Réponds uniquement en JSON."""

USER_PROMPT = """Titre : {title}
Source : {source}

Texte :
{text}

Dans cet ordre :
1. resume : deux phrases sur ce que dit l'article.
2. pourquoi : une phrase sur ce que l'article apporte à ces thèmes (pas un jugement sur sa qualité), \
ou « hors sujet ».
3. compilation : « justification », puis « ok ». Sois strict : true seulement si l'essentiel du texte est une \
liste de contenus d'AUTRES auteurs (articles, vidéos, livres), chacun présenté en quelques lignes, sans \
argumentation suivie de l'auteur : revue de liens, « what I've been reading », newsletter de liens, programme \
d'un événement. false dans tous les autres cas, en particulier : un essai qui cite plusieurs sources, un \
épisode de podcast ou un entretien, un guide de lecture écrit par l'auteur du livre, un article qui commente \
longuement une seule source.
4. dans_themes : « justification », puis « ok » à true si le sujet principal de l'article relève d'au moins un \
des thèmes listés, même indirectement (par exemple le leadership ou la conduite du changement pour le coaching, \
la gestion de portefeuille pour la stratégie produit) ; false s'il relève d'un autre domaine (technique pure, \
santé, finance, vie personnelle…).
5. promotionnel : « justification », puis « ok ». Fais ce test : si on retire du texte tous les passages qui \
présentent une offre (livre, workshop, webinaire, club, newsletter, outil, service, appel à acheter ou à \
s'inscrire), reste-t-il un article argumenté complet ? Si oui, réponds false, même si l'offre est mise en avant \
au début ou à la fin. Réponds true seulement s'il ne reste presque rien : annonce de webinaire ou de \
formation, page de présentation d'un livre ou d'un outil, invitation à télécharger ou à s'inscrire.
6. Pour chaque critère ci-dessous : « justification », une phrase qui cite ou décrit l'élément précis du \
texte sur lequel tu t'appuies, puis « ok » (true ou false) cohérent avec cette justification.
{criteria}"""


# ---------------------------------------------------------------------------
# Réglages et stockage
# ---------------------------------------------------------------------------

def local_config_file() -> Path:
    """Couche locale des réglages, à côté de tri.yaml, ignorée par Git et jamais écrite par un script."""
    return CONFIG_FILE.with_name(watch_config.LOCAL_FILE)


def config(create: bool = True) -> dict:
    """Réglages de tri.yaml (créé au premier lancement si `create`, sinon réglages par défaut sans rien écrire), puis la
    couche locale tri.local.yaml par-dessus. `shadow`, `language` et `relevance_threshold` sont validés strictement."""
    if CONFIG_FILE.exists():
        text = CONFIG_FILE.read_text(encoding="utf-8")
    elif create:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"Réglages créés : {CONFIG_FILE}")
        text = DEFAULT_CONFIG
    else:  # lecture seule : les réglages par défaut, sans rien écrire
        text = DEFAULT_CONFIG
    raw = charger(text, CONFIG_FILE.name)
    watch_config.refuse_tracked_handle(raw, CONFIG_FILE.name)
    settings = watch_config.normalize(raw, CONFIG_FILE.name)
    settings["shadow"] = watch_config.shadow_settings(settings.get("shadow"), CONFIG_FILE.name)
    settings["language"] = watch_config.language(raw, settings.get("language"), CONFIG_FILE.name)
    settings["relevance_threshold"] = watch_config.relevance_threshold(raw, settings.get("relevance_threshold"),
                                                                       CONFIG_FILE.name)
    local = local_config_file()
    if local.exists():
        settings.update(watch_config.local_settings(charger(local.read_text(encoding="utf-8"), local.name), local.name))
    return settings


def set_config(key: str, value) -> None:
    """Modifie une ligne de tri.yaml (jamais tri.local.yaml) sans toucher aux commentaires ; l'ajoute si elle manque."""
    text = CONFIG_FILE.read_text(encoding="utf-8")
    pattern = re.compile(rf"^{re.escape(key)}:[^\n#]*", re.M)
    if pattern.search(text):
        text = pattern.sub(f"{key}: {value} ", text, count=1)
    else:
        text = text.rstrip("\n") + f"\n{key}: {value}\n"
    CONFIG_FILE.write_text(text, encoding="utf-8")


SCHEMA = """
CREATE TABLE IF NOT EXISTS refs (
    url TEXT PRIMARY KEY, title TEXT, origin TEXT, vector BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS scores (
    file TEXT PRIMARY KEY, url TEXT, title TEXT, source TEXT, published TEXT, collected TEXT,
    complete INTEGER, vector BLOB NOT NULL, criteria TEXT, substance INTEGER,
    resume TEXT, pourquoi TEXT, model TEXT, scored_at TEXT, location TEXT DEFAULT 'watch',
    justifications TEXT, compilation INTEGER, in_themes INTEGER, promo INTEGER
);
CREATE TABLE IF NOT EXISTS forced (file TEXT PRIMARY KEY, since TEXT);
CREATE TABLE IF NOT EXISTS excluded (file TEXT PRIMARY KEY, since TEXT);
CREATE TABLE IF NOT EXISTS shared (file TEXT PRIMARY KEY, url TEXT, post_date TEXT, found TEXT);
CREATE TABLE IF NOT EXISTS picks (day TEXT NOT NULL, file TEXT NOT NULL, PRIMARY KEY (day, file));
CREATE TABLE IF NOT EXISTS shadow_scores (
    url TEXT NOT NULL, language TEXT NOT NULL, model TEXT, prompts_hash TEXT, criteria TEXT, substance INTEGER,
    compilation INTEGER, in_themes INTEGER, promo INTEGER, scored_at TEXT, PRIMARY KEY (url, language)
);
"""


def db() -> sqlite3.Connection:
    TRI_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(TRI_DB)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(scores)")}
    if "justifications" not in columns:  # base créée par la première version
        connection.execute("ALTER TABLE scores ADD COLUMN justifications TEXT")
    if "compilation" not in columns:
        connection.execute("ALTER TABLE scores ADD COLUMN compilation INTEGER")
    if "in_themes" not in columns:
        connection.execute("ALTER TABLE scores ADD COLUMN in_themes INTEGER")
    if "promo" not in columns:
        connection.execute("ALTER TABLE scores ADD COLUMN promo INTEGER")
    return connection


def to_blob(vector: np.ndarray) -> bytes:
    return vector.astype(np.float16).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float16).astype(np.float32)


def read_article(path: Path) -> dict:
    """Front matter et texte d'un article écrit par watch_lab.py."""
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = {}, text
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip().strip('"')
        body = text[match.end():]
    title = meta.get("title", path.stem).rsplit(" · ", 1)[0]  # le nom de la source suit le « · »
    return {
        "file": path.name, "title": title, "url": meta.get("url", ""), "source": meta.get("source", ""),
        "published": meta.get("published", ""), "collected": meta.get("collected", ""),
        "complete": meta.get("complete", "true") == "true", "body": body.strip(),
    }


# ---------------------------------------------------------------------------
# Référence : ce que vous avez choisi de partager
# ---------------------------------------------------------------------------

def signalpm_references(paths: list[Path]) -> list[dict]:
    """Une référence par conversation SignalPM : le lien, et la réponse de SignalPM (résumé, posts)."""
    seen, refs = set(), []
    for path in paths:
        for document in veille.json_documents(path):
            for conversation in veille.conversations_in(document):
                key = conversation.get("uuid") or str(id(conversation))
                if key in seen:
                    continue
                seen.add(key)
                messages = [m for m in conversation["chat_messages"] if isinstance(m, dict)]
                messages.sort(key=lambda m: m.get("created_at") or "")
                human = [m for m in messages if (m.get("sender") or m.get("role")) in ("human", "user")]
                answers = [m for m in messages if (m.get("sender") or m.get("role")) == "assistant"]
                if not human or not answers:
                    continue
                first = veille.message_text(human[0]).strip()
                urls = {veille.clean_url(u) for u in veille.URL_RE.findall(first)}
                if len(urls) != 1 or len(veille.URL_RE.sub("", first).strip()) > 40:
                    continue
                answer = veille.message_text(answers[0]).strip()
                if len(answer) >= 200:
                    refs.append({"url": urls.pop(), "title": conversation.get("name") or "",
                                 "origin": "signalpm", "text": answer[:EMBED_CHARS]})
    return refs


def own_references() -> list[dict]:
    refs = []
    for path in sorted(OWN_DIR.glob("*.md")):
        article = read_article(path)
        refs.append({"url": article["url"] or path.name, "title": article["title"], "origin": watch_paths.OWN_COLLECTION,
                     "text": f"{article['title']}\n\n{article['body'][:EMBED_CHARS]}"})
    return refs


def cmd_references(args: argparse.Namespace) -> None:
    refs = signalpm_references([Path(p).expanduser() for p in args.claude_export])
    print(f"{len(refs)} conversations SignalPM avec une réponse exploitable")
    if not args.without_own:
        own = own_references()
        print(f"{len(own)} articles de la collection {watch_paths.OWN_COLLECTION}")
        refs += own
    if not refs:
        sys.exit("Aucune référence : vérifiez le chemin de l'export Claude.")
    connection = db()
    connection.execute("DELETE FROM refs WHERE origin != 'partage'")  # les partages restent
    for start in range(0, len(refs), 16):
        batch = refs[start:start + 16]
        vectors = library.embed([r["text"] for r in batch])
        connection.executemany(
            "INSERT OR REPLACE INTO refs VALUES (?, ?, ?, ?)",
            [(r["url"], r["title"], r["origin"], to_blob(v)) for r, v in zip(batch, vectors)],
        )
        print(f"  {min(start + 16, len(refs))}/{len(refs)}")
    connection.commit()
    print(f"Référence enregistrée : {len(refs)} textes · {TRI_DB}")


# ---------------------------------------------------------------------------
# Notation
# ---------------------------------------------------------------------------

def decision_prompts(language: str) -> types.SimpleNamespace | None:
    """Prompts qui décident : None pour le français (charge utile de `judge` inchangée), le module de la langue sinon.
    Un module inutilisable arrête la notation : jamais de repli sur le français, que l'utilisateur n'a pas choisi."""
    if language == "fr":
        return None
    try:
        return load_shadow_prompts(language)
    except (ImportError, ValueError) as error:
        sys.exit(f"Prompts de la langue {language} inutilisables ({SHADOW_MODULES[language]}) : {error}")


def french_prompts() -> types.SimpleNamespace:
    """Les prompts et critères français, ceux qui décident de tout."""
    return types.SimpleNamespace(SYSTEM_PROMPT=SYSTEM_PROMPT, USER_PROMPT=USER_PROMPT, CRITERIA=CRITERIA)


def judge(model: str, themes: list[str], article: dict, prompts: types.SimpleNamespace | None = None) -> dict:
    """Grille de substance remplie par le modèle local, en sortie JSON contrainte. `prompts` : jeu de prompts et de
    critères de la notation en ombre ; par défaut le français (charge utile inchangée)."""
    prompts = prompts or french_prompts()
    item = {"type": "object", "properties": {"justification": {"type": "string"}, "ok": {"type": "boolean"}},
            "required": ["justification", "ok"]}
    schema = {  # l'ordre compte : le modèle résume et justifie avant de trancher
        "type": "object",
        "properties": {"resume": {"type": "string"}, "pourquoi": {"type": "string"}, "compilation": item,
                       "dans_themes": item, "promotionnel": item, **{k: item for k in CRITERIA}},
        "required": ["resume", "pourquoi", "compilation", "dans_themes", "promotionnel", *CRITERIA],
    }
    criteria = "\n".join(f"- {key} : {question}" for key, (question, _) in prompts.CRITERIA.items())
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompts.SYSTEM_PROMPT.format(themes="; ".join(themes))},
            {"role": "user", "content": prompts.USER_PROMPT.format(
                title=article["title"], source=article["source"],
                text=article["body"][:JUDGE_CHARS], criteria=criteria)},
        ],
        "format": schema, "stream": False, "think": False,
        # num_predict plafonne la réponse : certains modèles bouclent sur des espaces en sortie JSON
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1500},
    }
    url = f"{library.OLLAMA_URL}/api/chat"
    try:
        response = httpx.post(url, json=payload, timeout=JUDGE_TIMEOUT)
        if response.status_code == 400 and "think" in response.text:  # modèle sans mode de réflexion
            payload.pop("think")
            response = httpx.post(url, json=payload, timeout=JUDGE_TIMEOUT)
    except httpx.TimeoutException as error:
        raise ValueError(f"pas de réponse du modèle en {JUDGE_TIMEOUT} s") from error
    if response.status_code == 404:
        raise SystemExit(f"Ollama ne connaît pas le modèle « {model} ». Lancez : ollama pull {model}")
    response.raise_for_status()
    try:
        answer = json.loads(response.json()["message"]["content"])
    except json.JSONDecodeError as error:
        raise ValueError(f"réponse illisible du modèle : {error}") from error
    except (KeyError, TypeError) as error:   # enveloppe sans « message » (erreur du serveur, par exemple)
        raise ValueError("réponse du modèle sans message") from error
    if not isinstance(answer, dict):   # « [] », « null » : du JSON valide, mais pas la grille attendue
        raise ValueError(f"réponse illisible du modèle : objet attendu, reçu {type(answer).__name__}")
    missing = [k for k in ("compilation", "dans_themes", "promotionnel", *CRITERIA)
               if not isinstance(answer.get(k), dict) or not isinstance(answer[k].get("ok"), bool)]
    if missing:  # une réponse incomplète n'est pas un « non » : on ne note pas
        raise ValueError(f"réponse incomplète du modèle (manque : {', '.join(missing)})")
    return {
        "criteria": {k: answer[k]["ok"] for k in CRITERIA},
        "justifications": {k: str(answer[k].get("justification", "")).strip() for k in ("compilation", "dans_themes", "promotionnel", *CRITERIA)},
        "compilation": answer["compilation"]["ok"],
        "in_themes": answer["dans_themes"]["ok"],
        "promo": answer["promotionnel"]["ok"],
        "resume": str(answer.get("resume", "")).strip(),
        "pourquoi": str(answer.get("pourquoi", "")).strip(),
    }


# ---------------------------------------------------------------------------
# Notation en ombre (lot 5b anglais) : une seconde note, en anglais, qui ne décide de rien
# ---------------------------------------------------------------------------

SHADOW_MODULES = {"en": "watch_prompts_en"}   # langue -> module de tools/ qui porte prompts, critères et thèmes
SHADOW_PLACEHOLDERS = {"SYSTEM_PROMPT": ("{themes}",), "USER_PROMPT": ("{title}", "{source}", "{text}", "{criteria}")}


def check_prompts(module, name: str = "watch_prompts_en") -> types.SimpleNamespace:
    """Vérifie le contrat d'un module de prompts de l'ombre et rend un jeu utilisable par `judge`.

    Il doit porter SYSTEM_PROMPT (avec {themes}), USER_PROMPT (avec {title}, {source}, {text}, {criteria}), CRITERIA
    (mêmes clés que le français, valeurs (question, raison)) et THEMES (liste de textes). Lève ValueError sinon."""
    for attribute in ("SYSTEM_PROMPT", "USER_PROMPT", "CRITERIA", "THEMES"):
        if not hasattr(module, attribute):
            raise ValueError(f"{name} : « {attribute} » manque")
    for attribute, markers in SHADOW_PLACEHOLDERS.items():
        missing = [m for m in markers if m not in getattr(module, attribute)]
        if missing:
            raise ValueError(f"{name} : {attribute} sans {', '.join(missing)}")
    if list(module.CRITERIA) != list(CRITERIA):
        raise ValueError(f"{name} : les critères doivent avoir les clés {', '.join(CRITERIA)}, dans cet ordre")
    if not all(isinstance(v, (tuple, list)) and len(v) == 2 and all(isinstance(t, str) and t for t in v)
               for v in module.CRITERIA.values()):
        raise ValueError(f"{name} : chaque critère doit être un couple (question, raison)")
    if not module.THEMES or not all(isinstance(t, str) and t for t in module.THEMES):
        raise ValueError(f"{name} : THEMES doit être une liste non vide de textes")
    return types.SimpleNamespace(SYSTEM_PROMPT=module.SYSTEM_PROMPT, USER_PROMPT=module.USER_PROMPT,
                                 CRITERIA=dict(module.CRITERIA), THEMES=list(module.THEMES))


def load_shadow_prompts(language: str) -> types.SimpleNamespace:
    """Prompts et thèmes de la langue de l'ombre (import à la demande : rien n'est chargé quand l'ombre est inactive)."""
    return check_prompts(importlib.import_module(SHADOW_MODULES[language]), SHADOW_MODULES[language])


def prompts_hash(prompts: types.SimpleNamespace) -> str:
    """Empreinte (12 hex) des prompts, des questions des critères et des thèmes : elle change si l'un d'eux change."""
    parts = [prompts.SYSTEM_PROMPT, prompts.USER_PROMPT, *(f"{k}\x1f{q}\x1f{r}" for k, (q, r) in prompts.CRITERIA.items()),
             *prompts.THEMES]
    return hashlib.sha256("\x1e".join(parts).encode("utf-8")).hexdigest()[:12]


def shadow_key(article: dict) -> str:
    """Clé de l'article dans shadow_scores : son lien, à défaut son nom de fichier."""
    return article["url"] or article["file"]


def shadow_score(connection: sqlite3.Connection, model: str, language: str, prompts: types.SimpleNamespace,
                 article: dict) -> bool:
    """Seconde note de l'article avec les prompts de l'ombre. Rend False en cas d'échec ; ne lève jamais d'erreur de
    notation et ne touche pas à la table scores."""
    verdict = None
    for attempt in (1, 2):  # une seconde chance sur réponse incomplète, comme pour le français
        try:
            verdict = judge(model, prompts.THEMES, article, prompts)
            break
        except ValueError:
            continue
        except httpx.HTTPError:
            return False
    if verdict is None:
        return False
    flag = lambda value: None if value is None else int(value)  # noqa: E731
    connection.execute(
        "INSERT OR REPLACE INTO shadow_scores (url, language, model, prompts_hash, criteria, substance, compilation, "
        "in_themes, promo, scored_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (shadow_key(article), language, model, prompts_hash(prompts), json.dumps(verdict["criteria"]),
         sum(verdict["criteria"].values()), flag(verdict["compilation"]), flag(verdict["in_themes"]),
         flag(verdict["promo"]), dt.datetime.now().isoformat(timespec="seconds")))
    connection.commit()
    return True


def cmd_score(args: argparse.Namespace) -> None:
    settings = config()
    connection = db()
    known = {row["file"] for row in connection.execute("SELECT file FROM scores")}
    files = sorted(veille.ARTICLES_DIR.glob("*.md"))
    todo = [f for f in files if args.rescore or f.name not in known]
    if args.compilations:  # pour revérifier les articles classés en compilation
        flagged = {row["file"] for row in connection.execute("SELECT file FROM scores WHERE compilation = 1")}
        todo = [f for f in todo if f.name in flagged]
    if args.promotional:  # pour revérifier les articles classés en contenu promotionnel
        flagged = {row["file"] for row in connection.execute("SELECT file FROM scores WHERE promo = 1")}
        todo = [f for f in todo if f.name in flagged]
    if args.max_substance is not None:  # pour comparer deux modèles sur les articles jugés faibles
        low = {row["file"] for row in connection.execute(
            "SELECT file FROM scores WHERE substance IS NOT NULL AND substance <= ?", (args.max_substance,))}
        todo = [f for f in todo if f.name in low]
    if args.limit:
        todo = todo[: args.limit]
    prompts = None if args.no_model else decision_prompts(settings["language"])
    print(f"{len(files)} articles dans la collection {veille.ARTICLES_DIR.name} · {len(todo)} à noter · modèle {settings['model']}")
    shadow = settings["shadow"]
    shadow_prompts = None
    if shadow["enabled"] and not args.no_model:
        try:
            shadow_prompts = load_shadow_prompts(shadow["language"])
        except (ImportError, ValueError) as error:  # l'ombre ne bloque jamais la notation
            print(f"Notation en ombre ({shadow['language']}) désactivée pour ce passage : {error}")
    shadow_done = shadow_failed = 0
    shadow_seconds = 0.0
    for number, path in enumerate(todo, 1):
        started = time.time()
        article = read_article(path)
        print(f"[{number}/{len(todo)}] {article['title'][:70]} …", end="\r", flush=True)
        vector = library.embed([f"{article['title']}\n\n{article['body'][:EMBED_CHARS]}"])[0]
        verdict = {"criteria": None, "justifications": None, "resume": "", "pourquoi": "", "compilation": None,
                   "in_themes": None, "promo": None}
        if article["complete"] and not args.no_model:
            try:
                verdict = judge(settings["model"], settings.get("themes") or [], article, prompts)
            except ValueError:
                try:  # une seconde chance : les réponses incomplètes sont souvent ponctuelles
                    verdict = judge(settings["model"], settings.get("themes") or [], article, prompts)
                except ValueError as error:
                    print(f"[{number}/{len(todo)}] {article['title'][:70]} · NON NOTÉ ({error}), repris au prochain passage")
                    continue
        substance = sum(verdict["criteria"].values()) if verdict["criteria"] else None
        connection.execute(
            "INSERT OR REPLACE INTO scores (file, url, title, source, published, collected, complete, vector, "
            "criteria, substance, resume, pourquoi, model, scored_at, location, justifications, compilation, in_themes, promo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'watch', ?, ?, ?, ?)",
            (path.name, article["url"], article["title"], article["source"], article["published"],
             article["collected"], int(article["complete"]), to_blob(vector),
             json.dumps(verdict["criteria"]) if verdict["criteria"] else None, substance,
             verdict["resume"], verdict["pourquoi"], settings["model"],
             dt.datetime.now().isoformat(timespec="seconds"),
             json.dumps(verdict["justifications"], ensure_ascii=False) if verdict["justifications"] else None,
             None if verdict["compilation"] is None else int(verdict["compilation"]),
             None if verdict["in_themes"] is None else int(verdict["in_themes"]),
             None if verdict["promo"] is None else int(verdict["promo"])),
        )
        connection.commit()  # un article à la fois : une notation interrompue reprend où elle s'est arrêtée
        shown = f"substance {substance}/5" if substance is not None else "extrait seulement"
        if verdict["compilation"]:
            shown += " · compilation"
        if verdict["in_themes"] is False:
            shown += " · hors thèmes"
        if verdict["promo"]:
            shown += " · promotionnel"
        print(f"[{number}/{len(todo)}] {article['title'][:70]} · {shown} · {time.time() - started:.0f} s")
        if shadow_prompts and article["complete"] and not args.no_model:  # après la note française, qu'elle ne change pas
            shadow_started = time.time()
            if shadow_score(connection, settings["model"], shadow["language"], shadow_prompts, article):
                shadow_done += 1
            else:
                shadow_failed += 1
            shadow_seconds += time.time() - shadow_started
    if shadow_prompts:
        print(f"Notation en ombre ({shadow['language']}) : {shadow_done} notés, {shadow_failed} échec(s), "
              f"+{shadow_seconds:.0f} s")


def ollama_reachable() -> bool:
    """Ollama répond-il ? (même sonde que la veille : la liste des modèles, en 5 s)"""
    try:
        return httpx.get(f"{library.OLLAMA_URL}/api/tags", timeout=5).status_code == 200
    except httpx.HTTPError:
        return False


def shadow_backfill_candidates(connection: sqlite3.Connection, language: str, current_hash: str) -> list[sqlite3.Row]:
    """Articles déjà notés en français (grille remplie, article complet) sans note en ombre pour `language`, ou avec une note faite avec
    une autre empreinte de prompts. Ceux qui ont un avis de calibration d'abord (g ou e), puis les autres, dans l'ordre des fichiers."""
    rows = connection.execute(
        "SELECT s.file, s.location, s.title FROM scores s LEFT JOIN shadow_scores h "
        "ON h.url = COALESCE(NULLIF(s.url, ''), s.file) AND h.language = ? "
        "WHERE s.criteria IS NOT NULL AND s.complete = 1 AND (h.url IS NULL OR h.prompts_hash IS NOT ?) ORDER BY s.file",
        (language, current_hash)).fetchall()
    opinions = calibration_opinions()
    return sorted(rows, key=lambda row: row["file"] not in opinions)    # tri stable : l'ordre des fichiers est gardé dans chaque groupe


def cmd_shadow_backfill(args: argparse.Namespace) -> None:
    """Rattrape la notation en ombre des articles déjà notés en français. N'écrit que dans shadow_scores : aucune note française,
    aucun seuil, ni _to-read.md ni article écarté ne change. Reprise naturelle : un article déjà noté avec l'empreinte courante
    n'est pas renoté. À ne pas lancer pendant la veille du matin (watch.sh ne pose pas de verrou)."""
    settings = config()
    shadow = settings["shadow"]
    if not shadow["enabled"]:
        sys.exit("Notation en ombre désactivée : mettre `enabled: true` dans le bloc `shadow` de tri.yaml avant de la rattraper.")
    try:
        prompts = load_shadow_prompts(shadow["language"])
    except (ImportError, ValueError) as error:
        sys.exit(f"Prompts de l'ombre ({shadow['language']}) inutilisables : {error}")
    if not ollama_reachable():
        sys.exit("Ollama ne répond pas : le lancer, puis relancer shadow-backfill (la reprise est automatique).")
    connection = db()
    todo = shadow_backfill_candidates(connection, shadow["language"], prompts_hash(prompts))
    if args.limit:
        todo = todo[: args.limit]
    opinions = calibration_opinions()
    print(f"{len(todo)} article(s) à noter en ombre ({shadow['language']}), dont {sum(r['file'] in opinions for r in todo)} avec un avis "
          f"de calibration · modèle {settings['model']}")
    done = failed = skipped = 0
    started = time.time()
    for number, row in enumerate(todo, 1):
        folders = (ARCHIVE_DIR, veille.ARTICLES_DIR) if row["location"] == "excluded" else (veille.ARTICLES_DIR, ARCHIVE_DIR)
        path = next((folder / row["file"] for folder in folders if (folder / row["file"]).exists()), None)
        if path is None:
            skipped += 1
            print(f"[{number}/{len(todo)}] {(row['title'] or row['file'])[:70]} · fichier introuvable, sauté")
            continue
        article = read_article(path)
        step = time.time()
        if shadow_score(connection, settings["model"], shadow["language"], prompts, article):
            done += 1
            outcome = "noté"
        else:
            failed += 1
            outcome = "ÉCHEC (repris au prochain lancement)"
        print(f"[{number}/{len(todo)}] {article['title'][:70]} · {outcome} · {time.time() - step:.0f} s", flush=True)
    print(f"Rattrapage de l'ombre ({shadow['language']}) : {done} notés, {failed} échec(s), {skipped} sauté(s), "
          f"{time.time() - started:.0f} s")


# ---------------------------------------------------------------------------
# Classement
# ---------------------------------------------------------------------------

def discard_reasons(row: dict, threshold: int, relevance: int = 0) -> list[str]:
    """Raisons pour lesquelles le filtre écarterait un article, d'après sa seule note (sans repêchage ni rejet à la main).

    `row` : substance, criteria (dict ou None), in_themes, promo, compilation et, si elle existe, why (justifications) ;
    avec `relevance` (seuil de pertinence, 0 : aucun), aussi pertinence. Vide : l'article est gardé. Commune à `ranked`
    (la décision, seule à passer `relevance`) et à `shadow-report` (la comparaison des langues, sans pertinence)."""
    why = row.get("why") or {}
    reasons = []
    if row.get("in_themes") == 0:  # jugement du modèle sur le sens, pas la ressemblance aux partages
        reasons.append("hors de vos thèmes" + (f" ({why['dans_themes']})" if why.get("dans_themes") else ""))
    if row.get("promo"):  # une annonce ou une publicité n'entre jamais, quelle que soit sa note
        reasons.append("contenu promotionnel" + (f" ({why['promotionnel']})" if why.get("promotionnel") else ""))
    if row.get("compilation"):  # une compilation ne remplace jamais l'article d'origine
        reasons.append("compilation de lectures")
    if row["substance"] is None:
        reasons.append("extrait seulement")
    elif row["substance"] < threshold:
        reasons += [CRITERIA[k][1] for k, ok in row["criteria"].items() if not ok]
    if relevance and row["pertinence"] < relevance:
        reasons.append(f"pertinence {row['pertinence']}/100 sous le seuil {relevance}")
    return reasons


def ranked(connection: sqlite3.Connection) -> list[dict]:
    """Tous les articles notés, avec leur pertinence en rang sur 100 et leur verdict de filtre."""
    refs = [from_blob(r["vector"]) for r in connection.execute("SELECT vector FROM refs")]
    if not refs:
        sys.exit("Pas de référence : lancez d'abord la commande references.")
    reference = np.vstack(refs)
    rows = [dict(r) for r in connection.execute("SELECT * FROM scores")]
    if not rows:
        sys.exit("Aucun article noté : lancez d'abord la commande score.")
    k = min(NEIGHBOURS, len(reference))
    for row in rows:
        similarities = reference @ from_blob(row["vector"])
        row["cosine"] = float(np.sort(similarities)[-k:].mean())
    order = sorted(rows, key=lambda r: r["cosine"])
    for position, row in enumerate(order):
        row["pertinence"] = round(100 * position / max(1, len(order) - 1))
    forced = {r["file"] for r in connection.execute("SELECT file FROM forced")}
    excluded = {r["file"] for r in connection.execute("SELECT file FROM excluded")}
    settings = config()
    # la pertinence est un rang qui bouge avec le corpus : elle ne décide que pour les articles de la période, pour ne
    # jamais faire sortir plus tard un article gardé à son arrivée
    since = (dt.date.today() - dt.timedelta(days=settings["days"])).isoformat()
    for row in rows:
        row["criteria"] = json.loads(row["criteria"]) if row["criteria"] else None
        why = json.loads(row["justifications"]) if row.get("justifications") else {}
        row["why"] = why
        recent = (row["collected"] or "") >= since
        reasons = discard_reasons(row, settings["substance_threshold"],
                                  settings["relevance_threshold"] if recent else 0)
        row["forced"] = row["file"] in forced
        row["reasons"] = [] if row["forced"] else reasons
        if row["file"] in excluded:  # votre décision l'emporte sur celle du modèle
            row["reasons"] = ["écarté à la main"]
    return sorted(rows, key=lambda r: -r["cosine"])


MEDIUM_ID = re.compile(r"-([0-9a-f]{10,12})$")


def match_keys(url: str) -> set[str]:
    """Clés de rapprochement d'un lien : l'adresse nettoyée et, pour Medium, l'identifiant de l'article
    (le même article circule sous plusieurs adresses : medium.com/@auteur/..., auteur.medium.com/...)."""
    from urllib.parse import urlsplit
    keys = {veille.clean_url(url)}
    last = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    found = MEDIUM_ID.search(last)
    if found:
        keys.add(f"medium:{found.group(1)}")
    return keys


def cmd_shares(args: argparse.Namespace) -> None:
    """Relève vos posts Bluesky récents : un article de la veille que vous avez partagé est marqué
    « partagé » et rejoint la référence de pertinence."""
    settings = config()
    handle = (settings.get("bluesky") or "").strip().removeprefix("@")
    if not handle:
        print(f"Partages : pas d'identifiant Bluesky dans {watch_config.LOCAL_FILE} (ligne « bluesky: »), étape sautée.")
        return
    connection = db()
    index: dict[str, sqlite3.Row] = {}
    for row in connection.execute("SELECT file, url, vector FROM scores WHERE url != ''"):
        for key in match_keys(row["url"]):
            index[key] = row
    try:
        with veille.client() as http:
            posts = veille.links_from_bluesky(http, handle, max_pages=args.pages)
            new = 0
            for url, date in posts:
                if veille.host_of(url) in veille.SHORTENERS:
                    url = veille.resolve_short(http, url) or url
                row = next((index[k] for k in match_keys(url) if k in index), None)
                if row is None:
                    continue
                if connection.execute("SELECT 1 FROM shared WHERE file = ?", (row["file"],)).fetchone():
                    continue
                connection.execute("INSERT INTO shared VALUES (?, ?, ?, ?)",
                                   (row["file"], row["url"], date, dt.date.today().isoformat()))
                connection.execute("INSERT OR REPLACE INTO refs VALUES (?, ?, ?, ?)",
                                   (row["url"], row["file"], "partage", row["vector"]))
                new += 1
    except (httpx.HTTPError, SystemExit) as error:  # Bluesky indisponible : le reste du passage continue
        print(f"Partages : Bluesky n'a pas répondu ({error}), reprise au prochain passage.")
        return
    connection.commit()
    total = connection.execute("SELECT COUNT(*) FROM shared").fetchone()[0]
    print(f"Partages : {len(posts)} liens lus sur Bluesky · {new} nouveaux articles de la veille partagés "
          f"({total} au total), ajoutés à la référence de pertinence")


def share_stats(connection: sqlite3.Connection, days: int = 30) -> str:
    """Combien des articles partagés récemment avaient été proposés dans les « à lire »."""
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    shared = connection.execute("SELECT file, found FROM shared WHERE found >= ?", (since,)).fetchall()
    if not shared:
        return ""
    picked = sum(
        1 for row in shared
        if connection.execute("SELECT 1 FROM picks WHERE file = ? AND day <= ?", (row["file"], row["found"])).fetchone()
    )
    return (f"{days} derniers jours : {len(shared)} article(s) de la veille partagé(s), "
            f"dont {picked} proposé(s) avant dans les « à lire ».")


WEEK_FILE = veille.WATCH_DIR / "_semaine.md"


def cmd_week(args: argparse.Namespace) -> None:
    """Inventaire des articles retenus sur la période, point de départ de la synthèse hebdomadaire :
    titres, sources, liens et résumés, sans le texte des articles (Claude lit le détail via la
    bibliothèque, passage par passage)."""
    connection = db()
    rows = ranked(connection)
    since = (dt.date.today() - dt.timedelta(days=args.days)).isoformat()
    shared = {r["file"] for r in connection.execute("SELECT file FROM shared")}
    # Par défaut, la période porte sur la date de publication : une source ajoutée récemment livre
    # aussi ses anciens articles, qui n'ont pas leur place dans la synthèse de la période.
    def day(row: dict) -> str:
        if args.per_run:
            return (row["collected"] or "")[:10]
        return (row["published"] or row["collected"] or "")[:10]
    kept = [r for r in rows if not r["reasons"] and day(r) >= since][: args.max]
    basis = "collectés" if args.per_run else "publiés"
    lines = [
        f"# Veille : articles retenus, {basis} du {since} au {dt.date.today().isoformat()}",
        "",
        f"{len(kept)} articles, classés par pertinence. Fichier produit par watch_triage.py semaine, "
        "pour la commande /watch-digest. Le texte complet de chaque article est dans la collection "
        "watch de la bibliothèque (search_library, collections [\"watch\"]).",
        "",
    ]
    for row in kept:
        mark = " · partagé" if row["file"] in shared else ""
        lines += [
            f"## {row['title']}",
            f"- Source : {row['source']} · publié le {row['published']} · pertinence {row['pertinence']} · "
            f"substance {row['substance']}/5{mark}",
            f"- Lien : {row['url']}",
            f"- Fichier : {row['file']}",
        ]
        if row["resume"]:
            lines.append(f"- Résumé : {row['resume']}")
        if row["pourquoi"]:
            lines.append(f"- Apport : {row['pourquoi']}")
        lines.append("")
    WEEK_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(kept)} articles retenus, {basis} depuis le {since} · {WEEK_FILE}")


def cmd_digest(args: argparse.Namespace) -> None:
    settings = config()
    connection = db()
    rows = ranked(connection)
    since = (dt.date.today() - dt.timedelta(days=settings["days"])).isoformat()
    period = [r for r in rows if (r["collected"] or "") >= since]
    filtering = settings["mode"] == "filtre"
    shared = {r["file"] for r in connection.execute("SELECT file FROM shared")}
    kept = [r for r in period if not r["reasons"]]
    top = [r for r in kept if r["file"] not in shared][: settings["to_read"]]  # déjà partagé = déjà lu
    today = dt.date.today().isoformat()
    connection.executemany("INSERT OR IGNORE INTO picks VALUES (?, ?)", [(today, r["file"]) for r in top])
    connection.commit()
    others = [r for r in period if r not in top and not r["reasons"]]
    compilations = [r for r in period if r.get("compilation") and not r["forced"]]
    excluded = [r for r in period if r["reasons"] and r not in compilations]

    def line(row: dict) -> str:
        substance = f"substance {row['substance']}/5" if row["substance"] is not None else "extrait"
        mark = " · **partagé**" if row["file"] in shared else ""
        return (f"- [{row['title']}]({row['url']}) · {row['source']}, {row['published']} · "
                f"pertinence {row['pertinence']} · {substance}{mark}")

    out = [f"# À lire : articles collectés depuis le {since}", ""]
    out.append(
        "Mode filtre : les articles écartés ne sont plus dans la bibliothèque (repêchage : watch_triage.py restore)."
        if filtering else
        "Mode observation : rien n'est retiré de la bibliothèque. La dernière section montre ce que le filtre écarterait."
    )
    stats = share_stats(connection)
    if stats:
        out += ["", stats]
    out += ["", f"## Les {len(top)} à lire", ""]
    for row in top:
        substance = f"substance {row['substance']}/5" if row["substance"] is not None else "extrait seulement"
        out += [f"### [{row['title']}]({row['url']})",
                f"{row['source']} · {row['published']} · pertinence {row['pertinence']} · {substance}", ""]
        if row["resume"]:
            out += [row["resume"], ""]
        if row["pourquoi"]:
            out += [f"*Pour vous :* {row['pourquoi']}", ""]
    out += [f"## Les autres ({len(others)}), par pertinence", "", *[line(r) for r in others], ""]
    if compilations:
        out += [f"## Compilations de lectures ({len(compilations)})", "",
                "Pour découvrir des sources ; elles n'entrent pas dans la bibliothèque.", "",
                *[line(r) for r in compilations], ""]
    title = "Écartés de la bibliothèque" if filtering else "Ce que le filtre écarterait"
    out += [f"## {title} ({len(excluded)})", "",
            f"Règle : dans vos thèmes, ni compilation ni contenu promotionnel, substance d'au moins "
            f"{settings['substance_threshold']}/5"
            + (f", pertinence d'au moins {settings['relevance_threshold']}/100." if settings["relevance_threshold"]
               else "."),
            ""]
    out += [f"{line(r)} · *{', '.join(r['reasons'])}*" for r in excluded]
    target = veille.to_read_file()
    target.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(period)} articles sur la période · {len(top)} à lire · {len(excluded)} "
          f"{'écartés' if filtering else 'seraient écartés'} · {target}")


# ---------------------------------------------------------------------------
# Calibration des seuils
# ---------------------------------------------------------------------------

CALIBRATION_FILE = veille.WATCH_DIR / "_calibration.csv"


def cmd_calibration(args: argparse.Namespace) -> None:
    rows = ranked(db())
    with CALIBRATION_FILE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["fichier", "titre", "source", "pertinence", "dans_themes", "substance", "compilation",
                         "promotionnel", "manque", "filtre", "avis"])
        for row in rows:
            why = row["why"]
            missing = [f"{CRITERIA[k][1]} ({why[k]})" if why.get(k) else CRITERIA[k][1]
                       for k, ok in (row["criteria"] or {}).items() if not ok]
            themes = {None: "", 1: "oui", 0: "non"}[row.get("in_themes")]
            writer.writerow([row["file"], row["title"], row["source"], row["pertinence"], themes,
                             "" if row["substance"] is None else row["substance"],
                             "oui" if row.get("compilation") else "", "oui" if row.get("promo") else "",
                             ", ".join(missing),
                             "écarter" if row["reasons"] else "garder", ""])
    print(f"{len(rows)} articles · {CALIBRATION_FILE}\n"
          "Ouvrez-le dans Numbers ou Excel, remplissez la colonne « avis » (g = garder, e = écarter) "
          "pour une vingtaine d'articles pris en haut, au milieu et en bas, enregistrez en CSV, "
          "puis lancez : watch_triage.py thresholds")


def calibration_opinions() -> dict[str, bool]:
    """Vos avis de calibration : fichier -> True (g, garder) / False (e, écarter). Vide sans fichier de calibration."""
    opinions: dict[str, bool] = {}
    if CALIBRATION_FILE.exists():
        with CALIBRATION_FILE.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                avis = (row.get("avis") or "").strip().lower()[:1]
                if avis in ("g", "e"):
                    opinions[row.get("fichier", "")] = avis == "g"
    return opinions


RELEVANCE_STEPS = range(0, 100, 10)   # seuils de pertinence essayés par thresholds (0 : aucun filtre de pertinence)


def threshold_counts(sample: list[tuple], substance: int, relevance: int = 0) -> tuple[int, int]:
    """(bons articles perdus, articles faibles gardés) pour un couple de seuils, sur les avis exploitables."""
    lost = sum(keep and (sub is None or sub < substance or rel < relevance) for sub, rel, keep, _, _ in sample)
    noise = sum((not keep) and sub is not None and sub >= substance and rel >= relevance
                for sub, rel, keep, _, _ in sample)
    return lost, noise


def cmd_thresholds(args: argparse.Namespace) -> None:
    """Propose les seuils de substance et de pertinence à partir de vos avis, et signale les désaccords sur les règles
    fixes (hors thèmes, compilation, promotionnel), qui se corrigent article par article avec restore."""
    if not CALIBRATION_FILE.exists():
        sys.exit("Pas de fichier de calibration : lancez d'abord la commande calibration.")
    sample, disagreements = [], []
    with CALIBRATION_FILE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            avis = (row.get("avis") or "").strip().lower()[:1]
            if avis not in ("g", "e"):
                continue
            rule = []
            if (row.get("compilation") or "").strip():
                rule.append("compilation")
            if (row.get("dans_themes") or "").strip() == "non":
                rule.append("hors thèmes")
            if (row.get("promotionnel") or "").strip():
                rule.append("promotionnel")
            if rule:  # écarté par une règle fixe, pas par le seuil
                if avis == "g":
                    disagreements.append((row["fichier"], row["titre"], " et ".join(rule)))
                continue
            substance = int(row["substance"]) if row["substance"].strip() else None
            relevance = int(row["pertinence"]) if (row.get("pertinence") or "").strip() else 0
            sample.append((substance, relevance, avis == "g", row["fichier"], row["titre"]))
    if len(sample) < 10:
        sys.exit(f"{len(sample)} avis exploitables seulement : il en faut au moins 10, idéalement 20 à 30.")
    results = sorted((*threshold_counts(sample, threshold), threshold) for threshold in range(0, 6))
    settings = config()
    print(f"{len(sample)} avis · seuil actuel : substance {settings['substance_threshold']}/5\n")
    print("substance  bons articles perdus  articles faibles gardés")
    for lost, noise, threshold in sorted(results, key=lambda r: r[2]):
        print(f"{threshold:>9}  {lost:>20}  {noise:>23}")
    lost, noise, threshold = results[0]   # le moins de bons perdus, puis de faibles gardés, puis le moins strict
    print(f"\nProposition (substance seule) : substance_threshold: {threshold} "
          f"(perd {lost} bon(s) article(s), garde {noise} article(s) faible(s)).")
    # couples (substance, pertinence) : le plus d'accord avec vos avis, puis le moins de bons perdus, puis les seuils
    # les moins stricts (pertinence d'abord). « Le moins de bons perdus d'abord » ne proposerait jamais de seuil de
    # pertinence : le relever ne peut que perdre de bons articles.
    print("\npertinence \\ substance (bons perdus/faibles gardés)")
    print("          " + "".join(f"{s:>8}" for s in range(0, 6)))
    pairs = []
    for relevance in RELEVANCE_STEPS:
        cells = []
        for substance in range(0, 6):
            pair_lost, pair_noise = threshold_counts(sample, substance, relevance)
            cells.append(f"{pair_lost}/{pair_noise}")
            pairs.append((-(len(sample) - pair_lost - pair_noise), pair_lost, relevance, substance, pair_noise))
        print(f"{relevance:>10}" + "".join(f"{c:>8}" for c in cells))
    minus_agreement, lost, relevance, threshold, noise = min(pairs)
    print(f"\nProposition (substance et pertinence) : substance_threshold: {threshold}, relevance_threshold: {relevance} "
          f"(accord {-minus_agreement}/{len(sample)}, perd {lost} bon(s) article(s), garde {noise} article(s) faible(s)).")
    if disagreements:
        print(f"\n{len(disagreements)} article(s) que vous voulez garder sont écartés par une règle fixe. "
              "Repêchez-les avant de passer en mode filtre :")
        for name, title, rule in disagreements:
            print(f"  {title[:60]} ({rule})\n    uv run ~/PMZilla-Lab/watch_triage.py restore {name}")
    lost_by_pair = [(name, title) for sub, rel, keep, name, title in sample
                    if keep and (sub is None or sub < threshold or rel < relevance)]
    if lost_by_pair:
        print(f"\n{len(lost_by_pair)} article(s) que vous voulez garder sont écartés par ce couple de seuils. "
              "Repêchez-les :")
        for name, title in lost_by_pair:
            print(f"  {title[:60]}\n    uv run ~/PMZilla-Lab/watch_triage.py restore {name}")
    still_in = [(name, title) for sub, rel, keep, name, title in sample
                if not keep and sub is not None and sub >= threshold and rel >= relevance]
    if still_in:
        print(f"\n{len(still_in)} article(s) que vous voulez écarter restent gardés avec ces seuils. "
              "Écartez-les à la main :")
        for name, title in still_in:
            print(f"  {title[:60]}\n    uv run ~/PMZilla-Lab/watch_triage.py exclude {name}")
    if args.save:
        set_config("substance_threshold", threshold)
        set_config("relevance_threshold", relevance)
        print(f"Enregistré dans {CONFIG_FILE}. Le mode reste « {settings['mode']} » : "
              "passez « mode: filtre » quand vous êtes prêt.")
    else:
        print("Pour l'enregistrer : watch_triage.py thresholds --save")


def percent(part: int, total: int) -> str:
    return f"{part}/{total}" + (f" ({round(100 * part / total)} %)" if total else "")


def shadow_pairs(connection: sqlite3.Connection, language: str, threshold: int) -> list[dict]:
    """Articles notés dans les deux langues, avec la note et la décision de chacune (sans repêchage ni rejet)."""
    cursor = connection.execute(
        "SELECT s.file, s.title, s.source, s.criteria, s.substance, s.compilation, s.in_themes, s.promo, "
        "h.criteria AS e_criteria, h.substance AS e_substance, h.compilation AS e_compilation, "
        "h.in_themes AS e_in_themes, h.promo AS e_promo "
        "FROM scores s JOIN shadow_scores h ON h.url = COALESCE(NULLIF(s.url, ''), s.file) AND h.language = ? "
        "WHERE s.criteria IS NOT NULL AND h.criteria IS NOT NULL ORDER BY s.file", (language,))
    pairs = []
    for row in cursor:
        fr = {"substance": row["substance"], "criteria": json.loads(row["criteria"]), "compilation": row["compilation"],
              "in_themes": row["in_themes"], "promo": row["promo"]}
        en = {"substance": row["e_substance"], "criteria": json.loads(row["e_criteria"]),
              "compilation": row["e_compilation"], "in_themes": row["e_in_themes"], "promo": row["e_promo"]}
        pairs.append({"file": row["file"], "title": row["title"], "source": row["source"], "fr": fr, "en": en,
                      "keep_fr": not discard_reasons(fr, threshold), "keep_en": not discard_reasons(en, threshold)})
    return pairs


def cmd_shadow_report(args: argparse.Namespace) -> None:
    """Compare les notes françaises et anglaises des mêmes articles. Lecture seule, sortie dans le Terminal."""
    settings = config(create=False)
    language = settings["shadow"]["language"]
    threshold = settings["substance_threshold"]
    connection = db()
    pairs = shadow_pairs(connection, language, threshold)
    if not pairs:
        print(f"Aucun article noté dans les deux langues (fr et {language}). La notation en ombre est "
              f"{'active' if settings['shadow']['enabled'] else 'inactive'} : "
              "pour l'activer, mettre `enabled: true` dans le bloc `shadow` de tri.yaml, puis laisser tourner `score`.")
        return
    total = len(pairs)
    print(f"Notation en ombre : fr et {language} · seuil de substance actuel {threshold}/5 · modèle {settings['model']}\n")
    print(f"Articles notés dans les deux langues : {total}")
    agree = sum(p["keep_fr"] == p["keep_en"] for p in pairs)
    print(f"Accord sur la décision garder/écarter : {percent(agree, total)}")
    print(f"  gardés : fr {sum(p['keep_fr'] for p in pairs)}, {language} {sum(p['keep_en'] for p in pairs)}")
    differences = [p["en"]["substance"] - p["fr"]["substance"] for p in pairs]
    mean_fr = sum(p["fr"]["substance"] for p in pairs) / total
    mean_en = sum(p["en"]["substance"] for p in pairs) / total
    print(f"Substance moyenne : fr {mean_fr:.2f}, {language} {mean_en:.2f} · écart moyen {sum(differences) / total:+.2f} "
          f"· écart absolu moyen {sum(abs(d) for d in differences) / total:.2f}")
    print("Critères où les deux langues diffèrent :")
    for key in CRITERIA:
        differ = sum(p["fr"]["criteria"].get(key) != p["en"]["criteria"].get(key) for p in pairs)
        yes_fr = sum(bool(p["fr"]["criteria"].get(key)) for p in pairs)
        yes_en = sum(bool(p["en"]["criteria"].get(key)) for p in pairs)
        print(f"  {key:<10} désaccord {percent(differ, total):<12} remplis : fr {yes_fr}, {language} {yes_en}")
    for key, label in (("in_themes", "dans les thèmes"), ("promo", "promotionnel"), ("compilation", "compilation")):
        differ = sum(p["fr"][key] != p["en"][key] for p in pairs)
        print(f"  {label:<15} désaccord {percent(differ, total)}")

    forced = {r["file"] for r in connection.execute("SELECT file FROM forced")}
    excluded = {r["file"] for r in connection.execute("SELECT file FROM excluded")}
    opinions = calibration_opinions()   # fichier -> True (garder) / False (écarter), d'après vos avis de calibration
    by_file = {p["file"]: p for p in pairs}
    print("\nAccord avec vos décisions (sur les articles notés dans les deux langues) :")
    for label, wanted in (("avis de calibration", opinions),
                          ("repêchages (à garder)", {f: True for f in forced}),
                          ("rejets à la main (à écarter)", {f: False for f in excluded})):
        known = {f: keep for f, keep in wanted.items() if f in by_file}
        if not known:
            print(f"  {label} : aucun article en commun")
            continue
        ok_fr = sum(by_file[f]["keep_fr"] == keep for f, keep in known.items())
        ok_en = sum(by_file[f]["keep_en"] == keep for f, keep in known.items())
        print(f"  {label} : fr {percent(ok_fr, len(known))} · {language} {percent(ok_en, len(known))}")

    def note(side: dict, keep: bool) -> str:
        failed = [k for k, ok in side["criteria"].items() if not ok]
        rules = [name for name, on in (("hors thèmes", side["in_themes"] == 0), ("promotionnel", side["promo"]),
                                       ("compilation", side["compilation"])) if on]
        detail = ", ".join(rules + (["manque " + "/".join(failed)] if failed else []))
        return f"substance {side['substance']}/5 → {'garder' if keep else 'écarter'}" + (f" ({detail})" if detail else "")

    disagreements = [p for p in pairs if p["keep_fr"] != p["keep_en"]]
    shown = disagreements[: args.limit] if args.limit else disagreements
    print(f"\nDésaccords sur la décision : {len(disagreements)}" + (f" (les {len(shown)} premiers)" if len(shown) < len(disagreements) else ""))
    for p in shown:
        print(f"- {p['title'][:70]} · {p['source']}\n    fr : {note(p['fr'], p['keep_fr'])}\n    {language} : {note(p['en'], p['keep_en'])}")


# ---------------------------------------------------------------------------
# Sources suggérées
# ---------------------------------------------------------------------------

NOT_SUGGESTED = (  # plateformes, boutiques et références : citées souvent, sans flux d'articles utile
    "amazon.", "wikipedia.org", "goodreads.com", "doi.org", "arxiv.org", "scholar.google", "google.com",
    "apple.com", "spotify.com", "wordpress.com", "wordpress.org", "ghost.org", "beehiiv.com", "mailchimp.com",
    "eventbrite.", "meetup.com", "zoom.us", "notion.so", "figma.com", "miro.com", "creativecommons.org",
    "gumroad.com", "patreon.com", "buymeacoffee.com", "openai.com", "anthropic.com", "claude.ai",
    "claude.com", "chatgpt.com", "gemini.google", "amzn.to", "amzn.eu", "maven.com", "luma.com", "lu.ma",
    "udemy.com", "coursera.org", "calendly.com", "typeform.com", "forms.gle", "cdn", "images.",
    "podcasts.apple", "open.spotify", "music.", "store.", "shop.",
)
FILE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf", ".mp3", ".mp4", ".zip")


def is_citation(url: str) -> bool:
    """Un lien vers un article précis : ni page d'accueil, ni image ou fichier."""
    from urllib.parse import urlsplit
    path = urlsplit(url).path.rstrip("/")
    return bool(path) and not path.lower().endswith(FILE_EXTENSIONS)
GENERIC_KEYS = {"medium.com", "substack.com", "open.substack.com"}


def drop_old_suggestions(followed: dict[str, dict]) -> dict[str, dict]:
    """Retire de `followed` les suggestions jamais activées (--reset) ; les sources actives et celles que
    l'utilisateur a ajoutées lui-même (sans date de suggestion) restent."""
    return {k: v for k, v in followed.items() if v.get("active") or not v.get("suggested")}


def sorted_sources(followed: dict[str, dict]) -> list[dict]:
    return sorted(followed.values(), key=lambda x: (not x.get("active"), -x.get("shared", 0), x["key"]))


def cmd_suggestions(args: argparse.Namespace) -> None:
    """Propose les sources citées par plusieurs bons articles ou compilations, avec active: false."""
    if not db().execute("SELECT 1 FROM scores LIMIT 1").fetchone():   # base vide : rien à proposer, ce n'est pas une erreur
        print("Aucun article noté : il n'y a aucune suggestion à calculer. Lancez d'abord « watch_triage.py score ».")
        if args.reset:   # --reset repart de zéro : il nettoie quand même les anciennes suggestions
            followed = {s["key"]: s for s in veille.load_sources()}
            kept = drop_old_suggestions(followed)
            if len(kept) < len(followed):
                veille.save_sources(sorted_sources(kept))
                print(f"Les anciennes suggestions inactives ont été retirées de sources.yaml "
                      f"({len(followed) - len(kept)}).")
            else:
                print("Aucune ancienne suggestion inactive à retirer de sources.yaml.")
        return
    rows = ranked(db())
    citing = {r["url"]: r for r in rows if r["url"] and (r.get("compilation") or not r["reasons"])}
    links = veille.state().execute("SELECT article_url, target_url FROM links").fetchall()
    followed = {s["key"]: s for s in veille.load_sources()}
    found: dict[str, dict] = {}
    for article_url, target in links:
        article = citing.get(article_url)
        if article is None or not is_citation(target):
            continue
        source = veille.source_of(target)
        key = source["key"]
        if key in GENERIC_KEYS or any(key.startswith(m) if m.endswith(".") else m in key for m in NOT_SUGGESTED):
            continue
        if key in followed and followed[key].get("active"):
            continue  # déjà suivie
        entry = found.setdefault(key, {**source, "articles": set(), "citing_sources": set(), "examples": set(),
                                       "from_compilation": False})
        entry["from_compilation"] |= bool(article.get("compilation"))
        entry["articles"].add(article_url)
        entry["citing_sources"].add(article["source"])
        entry["examples"].add(target)
    if args.reset:  # repartir de zéro pour les suggestions jamais activées
        followed = drop_old_suggestions(followed)
    # une source citée par un seul site (lien de sponsor, de bio) ne compte pas, sauf recommandation
    # explicite d'une compilation
    ranked_sources = sorted(
        (e for e in found.values() if len(e["articles"]) >= args.min
         and (len(e["citing_sources"]) >= 2 or e["from_compilation"])),
        key=lambda e: (-len(e["citing_sources"]), -len(e["articles"]), e["key"]),
    )[: args.max]
    if not ranked_sources:
        print(f"Aucune source citée par au moins {args.min} articles de deux sources différentes "
              "(ou par une compilation). Lancez d'abord « watch_lab.py links », ou attendez que la veille grossisse.")
        if args.reset:
            veille.save_sources(sorted_sources(followed))
            print("Les anciennes suggestions inactives ont été retirées de sources.yaml.")
        return
    print(f"{len(ranked_sources)} sources citées par au moins {args.min} articles retenus ou compilations\n")
    added = updated = 0
    with veille.client() as http:
        for number, entry in enumerate(ranked_sources, 1):
            examples = sorted(entry["examples"])[:3]
            cited = len(entry["articles"])
            by = len(entry["citing_sources"])
            if entry["key"] in followed:  # déjà proposée (inactive) : on met les compteurs à jour
                followed[entry["key"]].update(cited=cited, cited_by_sources=by)
                updated += 1
                state_label = "déjà dans sources.yaml"
            else:
                feed = veille.discover_feed(http, entry, examples)
                followed[entry["key"]] = {
                    "key": entry["key"], "name": entry["name"], "active": False,
                    "feed": feed or entry["feed"], "feed_ok": bool(feed),
                    "cited": cited, "cited_by_sources": by, "suggested": dt.date.today().isoformat(),
                    "examples": examples,
                }
                added += 1
                state_label = "flux trouvé" if feed else "pas de flux"
            print(f"[{number}/{len(ranked_sources)}] {entry['key']} · cité par {cited} articles "
                  f"de {by} source(s) · {state_label}")
    sources = sorted(followed.values(), key=lambda x: (not x.get("active"), -x.get("shared", 0),
                                                        -x.get("cited", 0), x["key"]))
    veille.save_sources(sources)
    print(f"\n{added} nouvelles sources proposées, {updated} mises à jour, dans {veille.SOURCES_FILE} "
          "(toutes en active: false). Passez active: true sur celles à suivre.")


# ---------------------------------------------------------------------------
# Filtre
# ---------------------------------------------------------------------------

def cmd_apply(args: argparse.Namespace) -> None:
    settings = config()
    if settings["mode"] != "filtre":
        print("Mode observation : aucun article ne sort de la bibliothèque.")
        return
    connection = db()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    moved = 0
    for row in ranked(connection):
        source = veille.ARTICLES_DIR / row["file"]
        if row["reasons"] and source.exists():
            shutil.move(str(source), ARCHIVE_DIR / row["file"])
            connection.execute("UPDATE scores SET location = 'excluded' WHERE file = ?", (row["file"],))
            moved += 1
    connection.commit()
    print(f"{moved} article(s) sorti(s) de la bibliothèque · {ARCHIVE_DIR}")


def cmd_exclude(args: argparse.Namespace) -> None:
    connection = db()
    name = Path(args.fichier).name
    if not (veille.ARTICLES_DIR / name).exists() and not (ARCHIVE_DIR / name).exists():
        sys.exit(f"Introuvable : {name}")
    connection.execute("DELETE FROM forced WHERE file = ?", (name,))
    connection.execute("INSERT OR REPLACE INTO excluded VALUES (?, ?)", (name, dt.date.today().isoformat()))
    connection.commit()
    print(f"{name} sera écarté de la bibliothèque (en mode filtre, au prochain passage).")


def cmd_restore(args: argparse.Namespace) -> None:
    connection = db()
    name = Path(args.fichier).name
    archived = ARCHIVE_DIR / name
    if archived.exists():
        shutil.move(str(archived), veille.ARTICLES_DIR / name)
    elif not (veille.ARTICLES_DIR / name).exists():
        sys.exit(f"Introuvable : {name}")
    connection.execute("DELETE FROM excluded WHERE file = ?", (name,))
    connection.execute("INSERT OR REPLACE INTO forced VALUES (?, ?)", (name, dt.date.today().isoformat()))
    connection.execute("UPDATE scores SET location = 'watch' WHERE file = ?", (name,))
    connection.commit()
    print(f"{name} est dans la bibliothèque et ne sera plus écarté. Il entre dans l'index au prochain passage.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Pré-tri de la veille de PMZilla Lab")
    commands = parser.add_subparsers(dest="command", required=True)
    refs = commands.add_parser("references", help="construire la référence à partir de SignalPM")
    refs.add_argument("--claude-export", nargs="+", required=True)
    refs.add_argument("--without-own", action="store_true", help="ne pas utiliser vos propres articles")
    score = commands.add_parser("score", help="noter les nouveaux articles")
    score.add_argument("--limit", type=int, default=0)
    score.add_argument("--rescore", action="store_true", help="tout renoter (après un changement de modèle)")
    score.add_argument("--no-model", action="store_true", help="pertinence seule, sans grille de substance")
    score.add_argument("--compilations", action="store_true",
                       help="avec --rescore : seulement les articles classés en compilation")
    score.add_argument("--promotional", action="store_true",
                       help="avec --rescore : seulement les articles classés en contenu promotionnel")
    score.add_argument("--max-substance", type=int, default=None,
                       help="avec --rescore : seulement les articles déjà notés à ce niveau ou moins")
    commands.add_parser("digest", help="écrire _to-read.md")
    week = commands.add_parser("week", help="préparer l'inventaire de la synthèse hebdomadaire")
    week.add_argument("--days", type=int, default=7)
    week.add_argument("--max", type=int, default=40, help="nombre maximal d'articles (les plus pertinents)")
    week.add_argument("--per-run", action="store_true",
                      help="filtrer sur la date de collecte au lieu de la date de publication")
    shares = commands.add_parser("shares", help="relever vos partages Bluesky et affiner la pertinence")
    shares.add_argument("--pages", type=int, default=3, help="pages de 100 posts lues (défaut 3)")
    commands.add_parser("calibration", help="exporter les notes pour donner votre avis")
    thresholds = commands.add_parser("thresholds", help="proposer des seuils à partir de vos avis")
    thresholds.add_argument("--save", action="store_true", help="écrire les seuils proposés dans tri.yaml")
    shadow_report = commands.add_parser("shadow-report", help="comparer les notes françaises et anglaises de l'ombre")
    shadow_report.add_argument("--limit", type=int, default=20,
                               help="nombre maximal de désaccords listés (0 : tous ; défaut 20)")
    backfill = commands.add_parser("shadow-backfill", help="noter en ombre les articles déjà notés en français")
    backfill.add_argument("--limit", type=int, default=0, help="nombre maximal d'articles notés ce passage (0 : tous)")
    commands.add_parser("apply", help="en mode filtre, sortir les articles écartés")
    rescue = commands.add_parser("restore", help="remettre un article écarté dans la bibliothèque")
    rescue.add_argument("fichier")
    exclude = commands.add_parser("exclude", help="écarter à la main un article que le modèle garde")
    exclude.add_argument("fichier")
    suggest = commands.add_parser("suggestions", help="proposer les sources citées par les bons articles")
    suggest.add_argument("--min", type=int, default=2, help="nombre minimal d'articles qui citent la source")
    suggest.add_argument("--max", type=int, default=30, help="nombre maximal de sources proposées")
    suggest.add_argument("--reset", action="store_true",
                         help="retirer d'abord les suggestions jamais activées, puis recalculer")
    args = parser.parse_args(flux_config.refuse_old_options(sys.argv[1:] if argv is None else argv, OLD_OPTIONS))
    {"references": cmd_references, "score": cmd_score, "digest": cmd_digest, "calibration": cmd_calibration,
     "thresholds": cmd_thresholds, "apply": cmd_apply, "restore": cmd_restore, "exclude": cmd_exclude,
     "suggestions": cmd_suggestions, "shares": cmd_shares, "shadow-report": cmd_shadow_report,
     "shadow-backfill": cmd_shadow_backfill,
     "week": cmd_week}[args.command](args)


if __name__ == "__main__":
    main()
