# /// script
# requires-python = ">=3.11"
# dependencies = ["feedparser", "trafilatura", "httpx", "pyyaml", "beautifulsoup4", "markdownify"]
# ///
"""
PMZilla Lab — veille automatisée à partir de sources choisies.

Trois commandes :

    uv run watch_lab.py sources [--claude-export conversations-000.zip ...] [--bluesky HANDLE]
                                 [--linkedin Shares.csv] [--urls liens.txt]
        Lit les liens déjà traités (conversations SignalPM de l'export Claude, posts Bluesky,
        export LinkedIn, ou une simple liste),
        en déduit les sources (auteur Medium, publication, blog, newsletter) et cherche leur flux
        RSS. Ajoute les nouvelles sources à sources.yaml avec active: false : c'est vous qui
        choisissez lesquelles suivre. Les sources déjà présentes gardent vos réglages.

    uv run watch_lab.py collect [--since-days 30]
        Lit les sources active: true de sources.yaml et écrit un Markdown par nouvel article
        dans Watch-Lab/watch/ (la collection « watch » de la bibliothèque). Idempotent :
        un article déjà collecté n'est jamais repris.

    uv run watch_lab.py import-medium medium-export.zip --source medium.com/@<utilisateur> --author <nom>
        Importe vos propres articles depuis l'export Medium (brouillons et réponses exclus)
        dans Watch-Lab/own-articles/. Une source avec « collection: own-articles » dans sources.local.yaml
        (à côté de sources.yaml, non suivi par Git) y range ensuite ses nouveaux articles chaque matin.

    uv run watch_lab.py links
        Relève une fois les liens cités par les articles collectés avant que la collecte les
        garde (ils servent aux sources suggérées de watch_triage.py suggestions).

    uv run watch_lab.py digest [--days 7]
        Écrit Watch-Lab/_to-read.md : les articles collectés sur la période, par source,
        pour choisir ceux à passer dans SignalPM.

Variables d'environnement (toutes facultatives) :
    VEILLE_LAB_DIR       dossier des articles      (défaut ~/PMZilla-Lab/workspace/Watch-Lab)
    VEILLE_LAB_SOURCES   fichier des sources       (défaut ~/PMZilla-Lab/workspace/watch/sources.yaml)
    PMZILLA_LAB_DATA     dossier de l'état         (défaut ~/.pmzilla-lab)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import sqlite3
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
import yaml
from yaml_strict import ErreurConfig, charger

import watch_paths

# Les dossiers de contenu vivent dans le dépôt, mais leur contenu est exclu par .gitignore
# Noms de dossiers : watch_paths donne le nom actuel et refuse un dossier resté à l'ancien nom
WORKSPACE = Path(os.environ.get("PMZILLA_LAB_WORKSPACE", "~/PMZilla-Lab/workspace")).expanduser()
WATCH_DIR = Path(os.environ.get("VEILLE_LAB_DIR") or watch_paths.lab_dir(WORKSPACE)).expanduser()
ARTICLES_DIR = WATCH_DIR / watch_paths.collection_name(WATCH_DIR)   # le nom du dossier devient le nom de la collection


def collection_dir(source: dict) -> Path:
    """Dossier d'une source : la collection de la veille par défaut, ou la collection indiquée (own-articles pour
    vos propres articles : Watch-Lab/own-articles/, source déclarée dans sources.local.yaml)."""
    return WATCH_DIR / (source.get("collection") or ARTICLES_DIR.name)


def to_read_file() -> Path:
    """Liste à lire : _to-read.md."""
    return WATCH_DIR / watch_paths.to_read_name(WATCH_DIR)


SOURCES_FILE = Path(os.environ.get("VEILLE_LAB_SOURCES") or watch_paths.config_dir(WORKSPACE) / "sources.yaml").expanduser()
STATE_DB = Path(os.environ.get("PMZILLA_LAB_DATA", "~/.pmzilla-lab")).expanduser() / "veille.sqlite"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15"
TIMEOUT = 30
MIN_FULL_TEXT = 1500      # en dessous, le flux ne donne qu'un extrait : on va chercher la page
MIN_KEPT_TEXT = 300       # en dessous, article marqué « extrait seulement » (paywall probable)
BLUESKY_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"

URL_RE = re.compile(r"https?://[^\s<>\"'\])]+")
TRACKING_PARAM = re.compile(r"^(utm_\w+|fbclid|gclid|mc_cid|mc_eid|ref|ref_src|source|sk|si|trk|lipi)$", re.I)
SHORTENERS = {"lnkd.in", "bit.ly", "buff.ly", "t.co", "link.medium.com", "ow.ly", "tinyurl.com", "dlvr.it", "shorturl.at"}
NOT_SOURCES = {  # réseaux sociaux et vidéos : pas des sources d'articles
    "linkedin.com", "bsky.app", "bsky.social", "x.com", "twitter.com", "youtube.com", "youtu.be",
    "facebook.com", "instagram.com", "threads.net", "github.com", "docs.google.com", "drive.google.com",
}
MEDIUM_RESERVED = {"", "p", "m", "feed", "tag", "tags", "search", "me", "plans", "membership", "topics", "about"}
FEED_PATHS = ("/feed", "/rss", "/feed.xml", "/rss.xml", "/index.xml", "/atom.xml", "/blog/feed", "/blog/rss.xml")

SOURCES_HEADER = """\
# Sources de veille de PMZilla Lab.
# - active: true   -> la source est collectée chaque jour ; false -> ignorée.
# - feed           -> flux RSS ou Atom. feed_ok: false = flux introuvable, à compléter à la main.
# - include / exclude (facultatifs) -> mots-clés cherchés dans le titre et les catégories ;
#   utiles pour une publication large (ne garder que « product », « discovery »...).
# - shared         -> nombre de liens de cette source déjà partagés dans SignalPM.
# - note           -> texte libre (par exemple la raison d'une désactivation). Il est conservé quand ce fichier est
#   réécrit par un script ; les commentaires YAML, eux, sont perdus à chaque réécriture : écrire la raison dans note.
# Relancer « watch_lab.py sources » ajoute les nouvelles sources sans toucher à vos réglages.
# - Sources personnelles (vos propres articles) : dans sources.local.yaml, à côté de ce fichier, non suivi par Git ; jamais réécrit par un script.
"""


# ---------------------------------------------------------------------------
# URL et sources
# ---------------------------------------------------------------------------

def clean_url(url: str) -> str:
    """Retire la ponctuation finale, les paramètres de suivi, le fragment et le www."""
    url = url.strip().rstrip(".,;:!?…»”’")
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not TRACKING_PARAM.match(k)])
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower() or "https", host, path, query, ""))


def host_of(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def is_social(host: str) -> bool:
    return any(host == h or host.endswith("." + h) for h in NOT_SOURCES)


def source_of(url: str) -> dict:
    """Déduit la source d'un article : clé stable, nom, site et flux RSS probable."""
    host = host_of(url)
    scheme = urlsplit(url).scheme or "https"
    segments = [s for s in urlsplit(url).path.split("/") if s]
    first = segments[0] if segments else ""
    if host == "medium.com":
        if first.startswith("@"):
            return {"key": f"medium.com/{first}", "name": f"{first} (Medium)",
                    "site": f"https://medium.com/{first}", "feed": f"https://medium.com/feed/{first}"}
        if first.lower() not in MEDIUM_RESERVED:
            return {"key": f"medium.com/{first}", "name": f"{first} (Medium)",
                    "site": f"https://medium.com/{first}", "feed": f"https://medium.com/feed/{first}"}
        return {"key": "medium.com", "name": "Medium (auteur inconnu)", "site": "https://medium.com", "feed": None}
    if host.endswith(".medium.com") or host.endswith(".substack.com"):
        return {"key": host, "name": host.split(".")[0], "site": f"https://{host}", "feed": f"https://{host}/feed"}
    return {"key": host, "name": host, "site": f"{scheme}://{host}", "feed": None}


def client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True)


def resolve_short(http: httpx.Client, url: str) -> str | None:
    """Suit un lien raccourci. lnkd.in renvoie une page intermédiaire : on y lit le vrai lien."""
    try:
        response = http.get(url)
    except httpx.HTTPError:
        return None
    final = str(response.url)
    if host_of(final) in ("lnkd.in", "linkedin.com"):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("http") and not is_social(host_of(a["href"])) \
                    and host_of(a["href"]) not in SHORTENERS:
                return a["href"]
        return None
    return final


def looks_like_feed(http: httpx.Client, url: str) -> bool:
    import feedparser
    try:
        response = http.get(url)
    except httpx.HTTPError:
        return False
    if response.status_code != 200:
        return False
    parsed = feedparser.parse(response.content)
    return bool(parsed.entries)


def discover_feed(http: httpx.Client, source: dict, examples: list[str]) -> str | None:
    """Cherche le flux : balise <link rel="alternate"> d'un article ou de l'accueil, puis chemins usuels."""
    from bs4 import BeautifulSoup
    if source["feed"] and looks_like_feed(http, source["feed"]):
        return source["feed"]
    for page in [*examples[:2], source["site"]]:
        try:
            response = http.get(page)
        except httpx.HTTPError:
            continue
        if response.status_code != 200 or "html" not in response.headers.get("content-type", ""):
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.find_all("link", rel="alternate"):
            kind = (link.get("type") or "").lower()
            if ("rss" in kind or "atom" in kind) and link.get("href"):
                candidate = urljoin(str(response.url), link["href"])
                if "comments" not in candidate and looks_like_feed(http, candidate):
                    return candidate
    for path in FEED_PATHS:
        candidate = source["site"].rstrip("/") + path
        if looks_like_feed(http, candidate):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Lecture des liens partagés
# ---------------------------------------------------------------------------

def links_from_bluesky(http: httpx.Client, handle: str, max_pages: int = 50) -> list[tuple[str, str]]:
    """Liens de tous les posts publics d'un compte Bluesky (API publique, sans connexion)."""
    found: list[tuple[str, str]] = []
    cursor = None
    for _ in range(max_pages):
        params = {"actor": handle, "limit": 100, "filter": "posts_no_replies"}
        if cursor:
            params["cursor"] = cursor
        response = http.get(BLUESKY_API, params=params)
        if response.status_code == 400:
            raise SystemExit(f"Bluesky ne connaît pas le compte « {handle} » (ex. : prenom.bsky.social).")
        response.raise_for_status()
        data = response.json()
        for item in data.get("feed", []):
            found.extend(links_in_bluesky_post(item.get("post", {})))
        cursor = data.get("cursor")
        if not cursor:
            break
    return found


def links_in_bluesky_post(post: dict) -> list[tuple[str, str]]:
    record = post.get("record", {})
    date = record.get("createdAt", "")[:10]
    urls: set[str] = set()
    embed = record.get("embed") or {}
    for block in (embed, embed.get("media") or {}):
        external = block.get("external") or {}
        if external.get("uri"):
            urls.add(external["uri"])
    for facet in record.get("facets", []):
        for feature in facet.get("features", []):
            if feature.get("$type") == "app.bsky.richtext.facet#link" and feature.get("uri"):
                urls.add(feature["uri"])
    urls.update(URL_RE.findall(record.get("text", "")))
    return [(u, date) for u in {clean_url(u) for u in urls}]  # un même lien compté une fois par post


def links_from_linkedin(path: Path) -> list[tuple[str, str]]:
    """Export LinkedIn (Paramètres > Confidentialité > Obtenir une copie de vos données) : Shares.csv."""
    found = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            date = (row.get("Date") or "")[:10]
            for column, value in row.items():
                if column in ("ShareLink", "MediaUrl") or not value:
                    continue
                found.extend((u, date) for u in URL_RE.findall(value))
    return found


def message_text(message: dict) -> str:
    """Texte d'un message. L'export répète souvent le texte dans « text » et dans « content » :
    on prend les blocs de « content » s'il y en a, sinon « text », jamais les deux."""
    blocks = [b.get("text") or "" for b in message.get("content") or []
              if isinstance(b, dict) and b.get("type", "text") == "text"]
    text = "\n".join(b for b in blocks if b)
    return text or message.get("text") or ""


def json_documents(path: Path):
    """Documents JSON d'un export : fichier .json ou .jsonl, dossier décompressé, ou .zip tel quel."""
    import json
    import zipfile

    def parse(name: str, raw: bytes):
        text = raw.decode("utf-8", errors="replace")
        if name.endswith(".jsonl"):
            for line in text.splitlines():
                if line.strip():
                    yield json.loads(line)
        elif name.endswith(".json"):
            yield json.loads(text)

    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file():
                yield from json_documents(child)
    elif path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for name in sorted(archive.namelist()):
                if name.endswith((".json", ".jsonl")):
                    yield from parse(name, archive.read(name))
                elif name.endswith(".zip"):  # archive dans l'archive
                    import io
                    nested = Path(path.parent / "_tmp_nested.zip")
                    nested.write_bytes(io.BytesIO(archive.read(name)).getvalue())
                    try:
                        yield from json_documents(nested)
                    finally:
                        nested.unlink()
    else:
        yield from parse(path.name.lower(), path.read_bytes())


def conversations_in(document) -> list[dict]:
    """Trouve les conversations (objets qui ont des chat_messages) où qu'elles soient dans le JSON."""
    found, stack = [], [document]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if isinstance(node.get("chat_messages"), list):
                found.append(node)
            else:
                stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return found


def links_from_claude_export(paths: list[Path]) -> list[tuple[str, str]]:
    """Export Claude (Paramètres > Confidentialité > Exporter les données) : conversations-000.zip
    (et projects-000.zip), décompressés ou non. Ne garde que les conversations SignalPM,
    reconnues à leur premier message : un lien seul."""
    seen: set[str] = set()
    conversations = []
    for path in paths:
        for document in json_documents(path):
            for conversation in conversations_in(document):
                key = conversation.get("uuid") or str(id(conversation))
                if key not in seen:
                    seen.add(key)
                    conversations.append(conversation)
    print(f"{len(conversations)} conversations lues dans l'export Claude")
    found, senders, with_links = [], Counter(), []
    for conversation in conversations:
        messages = [m for m in conversation["chat_messages"] if isinstance(m, dict)]
        senders.update(str(m.get("sender") or m.get("role")) for m in messages)
        messages = [m for m in messages if (m.get("sender") or m.get("role")) in ("human", "user")]
        messages.sort(key=lambda m: m.get("created_at") or "")
        if not messages:
            continue
        first = message_text(messages[0]).strip()
        urls = {clean_url(u) for u in URL_RE.findall(first)}
        if urls:
            with_links.append(first)
        if len(urls) == 1 and len(URL_RE.sub("", first).strip()) <= 40:  # un lien, à peine commenté
            found.append((urls.pop(), (messages[0].get("created_at") or conversation.get("created_at") or "")[:10]))
    print(f"{len(found)} conversations commencent par un lien seul")
    if not found:  # diagnostic : à quoi ressemblent les messages de cet export ?
        print(f"  Auteurs des messages : {dict(senders)}")
        print(f"  Premiers messages contenant au moins un lien : {len(with_links)}")
        for sample in with_links[:5]:
            print("   -", sample.replace("\n", " ")[:150])
    return found


def links_from_file(path: Path) -> list[tuple[str, str]]:
    return [(u, "") for u in URL_RE.findall(path.read_text(encoding="utf-8", errors="replace"))]


LOCAL_SOURCES_NAME = "sources.local.yaml"
_LOCAL_HINT = " ; corriger le fichier ou le retirer (les sources suivies seront alors lues seules)."


def local_sources_file() -> Path:
    """Sources personnelles : à côté du fichier suivi, non suivi par Git, jamais réécrit par un script."""
    return SOURCES_FILE.with_name(LOCAL_SOURCES_NAME)


def load_local_sources() -> list[dict]:
    path = local_sources_file()
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
        data = charger(text, LOCAL_SOURCES_NAME)
    except UnicodeDecodeError:
        raise ErreurConfig(f"{LOCAL_SOURCES_NAME} : fichier illisible{_LOCAL_HINT}") from None
    except yaml.YAMLError as err:
        mark = getattr(err, "problem_mark", None)
        where = f" (L{mark.line + 1})" if mark is not None else ""
        raise ErreurConfig(f"{LOCAL_SOURCES_NAME} : fichier illisible{where}{_LOCAL_HINT}") from None
    if data is None:
        return []
    entries = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ErreurConfig(f"{LOCAL_SOURCES_NAME} : « sources » doit être une liste d'entrées{_LOCAL_HINT}")
    seen: dict[str, int] = {}
    for rank, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or not entry.get("key"):
            raise ErreurConfig(f"{LOCAL_SOURCES_NAME} : entrée {rank} sans « key »{_LOCAL_HINT}")
        if entry["key"] in seen:
            raise ErreurConfig(f"{LOCAL_SOURCES_NAME} : entrées {seen[entry['key']]} et {rank} : "
                               "même « key » ; garder une seule des deux entrées.")
        seen[entry["key"]] = rank
    return entries


def _load_tracked_sources() -> list[dict]:
    if not SOURCES_FILE.exists():
        return []
    data = charger(SOURCES_FILE.read_text(encoding="utf-8"), SOURCES_FILE.name) or {}
    return data.get("sources", [])


def load_sources() -> list[dict]:
    """Sources suivies, puis sources locales : une clé locale déjà suivie la remplace à sa place, une nouvelle suit."""
    merged = list(_load_tracked_sources())
    position = {s["key"]: i for i, s in enumerate(merged)}
    for entry in load_local_sources():
        if entry["key"] in position:
            merged[position[entry["key"]]] = entry
        else:
            position[entry["key"]] = len(merged)
            merged.append(entry)
    return merged


def save_sources(sources: list[dict]) -> None:
    """Écrit le fichier suivi seulement : une entrée définie en local n'y est jamais copiée (la version suivie, s'il y en
    a une, est gardée telle quelle)."""
    local_keys = {s["key"] for s in load_local_sources()}
    if local_keys:
        tracked = {s["key"]: s for s in _load_tracked_sources()}
        sources = [tracked[s["key"]] if s["key"] in local_keys else s
                   for s in sources if s["key"] not in local_keys or s["key"] in tracked]
    SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump({"sources": sources}, allow_unicode=True, sort_keys=False, width=120)
    SOURCES_FILE.write_text(SOURCES_HEADER + "\n" + body, encoding="utf-8")


def cmd_sources(args: argparse.Namespace) -> None:
    raw: list[tuple[str, str]] = []
    with client() as http:
        if args.bluesky:
            raw += links_from_bluesky(http, args.bluesky.removeprefix("@"))
        if args.linkedin:
            raw += links_from_linkedin(Path(args.linkedin).expanduser())
        if args.claude_export:
            raw += links_from_claude_export([Path(p).expanduser() for p in args.claude_export])
        if args.urls:
            raw += links_from_file(Path(args.urls).expanduser())
        if not raw:
            sys.exit("Aucun lien : indiquez --claude-export, --bluesky, --linkedin ou --urls.")
        print(f"{len(raw)} liens lus")

        unresolved, ignored = [], 0
        by_source: dict[str, dict] = {}
        for url, date in raw:
            url = clean_url(url)
            if host_of(url) in SHORTENERS:
                target = resolve_short(http, url)
                if not target:
                    unresolved.append(url)
                    continue
                url = clean_url(target)
            if is_social(host_of(url)):
                ignored += 1
                continue
            if source_of(url)["key"] == "medium.com":  # medium.com/p/<id> redirige vers l'URL de l'auteur
                target = resolve_short(http, url)
                url = clean_url(target) if target else url
            source = source_of(url)
            entry = by_source.setdefault(source["key"], {**source, "shared": 0, "last_shared": "", "examples": set()})
            entry["shared"] += 1
            entry["last_shared"] = max(entry["last_shared"], date)
            entry["examples"].add(url)

        existing = {s["key"]: s for s in load_sources()}
        added = 0
        ranked = sorted(by_source.values(), key=lambda s: (-s["shared"], s["key"]))
        for number, found in enumerate(ranked, 1):
            examples = sorted(found["examples"])
            if found["key"] in existing:  # vos réglages restent ; seuls les compteurs bougent
                existing[found["key"]]["shared"] = found["shared"]
                existing[found["key"]]["last_shared"] = found["last_shared"] or existing[found["key"]].get("last_shared", "")
                continue
            print(f"[{number}/{len(ranked)}] {found['key']} : recherche du flux")
            feed = discover_feed(http, found, examples) if found["key"] != "medium.com" else None
            existing[found["key"]] = {
                "key": found["key"], "name": found["name"], "active": False,
                "feed": feed or found["feed"], "feed_ok": bool(feed),
                "shared": found["shared"], "last_shared": found["last_shared"], "examples": examples[:3],
            }
            added += 1

    sources = sorted(existing.values(), key=lambda s: (not s.get("active"), -s.get("shared", 0), s["key"]))
    save_sources(sources)
    print(f"\n{len(by_source)} sources trouvées, {added} nouvelles ajoutées à {SOURCES_FILE}")
    print(f"Liens de réseaux sociaux ignorés : {ignored}")
    if unresolved:
        print(f"Liens raccourcis non résolus : {len(unresolved)} (ex. : {unresolved[0]})")
    print("Passez active: true sur les sources à suivre, puis lancez la commande collect.")


# ---------------------------------------------------------------------------
# Collecte
# ---------------------------------------------------------------------------

STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    url        TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    title      TEXT NOT NULL,
    file       TEXT NOT NULL,
    published  TEXT NOT NULL,
    complete   INTEGER NOT NULL,
    collected  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    source     TEXT PRIMARY KEY,
    last_try   TEXT NOT NULL,
    last_ok    TEXT,
    error      TEXT
);
CREATE TABLE IF NOT EXISTS links (          -- liens cités dans le corps d'un article
    article_url TEXT NOT NULL,
    target_url  TEXT NOT NULL,
    PRIMARY KEY (article_url, target_url)
);
CREATE TABLE IF NOT EXISTS links_done (     -- articles dont les liens ont été relevés
    article_url TEXT PRIMARY KEY
);
"""


def state() -> sqlite3.Connection:
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(STATE_DB)
    db.executescript(STATE_SCHEMA)
    return db


def slugify(text: str, limit: int) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit].strip("-") or "article"


def html_to_markdown(html: str) -> str:
    from bs4 import BeautifulSoup
    from markdownify import markdownify
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "img", "svg", "figure", "iframe", "noscript"]):
        tag.decompose()
    text = markdownify(str(soup), heading_style="ATX", strip=["a", "span"])
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # Medium ajoute « Continue reading on ... » et un pixel de suivi en fin d'extrait
    return re.sub(r"\n*\[?Continue reading on .*$", "", text, flags=re.S).strip()


def fetch_html(http: httpx.Client, url: str) -> str:
    try:
        response = http.get(url)
    except httpx.HTTPError:
        return ""
    return response.text if response.status_code == 200 else ""


def page_text(http: httpx.Client, url: str, html: str | None = None) -> str:
    import trafilatura
    html = fetch_html(http, url) if html is None else html
    if not html:
        return ""
    return trafilatura.extract(html, output_format="markdown", include_links=False,
                               include_images=False, include_comments=False) or ""


MARKDOWN_LINK = re.compile(r"\]\((https?://[^)\s]+)\)")


def content_links(article_url: str, feed_html: str = "", page_html: str = "") -> set[str]:
    """Liens cités dans le corps de l'article (jamais le menu ni le pied de page), hors liens
    vers la source elle-même, réseaux sociaux et liens raccourcis."""
    import trafilatura
    from bs4 import BeautifulSoup
    found: set[str] = set()
    if feed_html:  # le contenu du flux est déjà le corps de l'article
        for a in BeautifulSoup(feed_html, "html.parser").find_all("a", href=True):
            found.add(urljoin(article_url, a["href"]))
    if page_html:  # la page complète : trafilatura n'en garde que le corps
        body = trafilatura.extract(page_html, output_format="markdown", include_links=True,
                                   include_images=False, include_comments=False, url=article_url) or ""
        found.update(MARKDOWN_LINK.findall(body))
    own = source_of(article_url)["key"]
    links = set()
    for link in found:
        if not link.startswith(("http://", "https://")):
            continue
        link = clean_url(link)
        host = host_of(link)
        if is_social(host) or host in SHORTENERS or source_of(link)["key"] == own:
            continue
        links.add(link)
    return links


def store_links(db: sqlite3.Connection, article_url: str, links: set[str]) -> None:
    db.executemany("INSERT OR IGNORE INTO links VALUES (?, ?)", [(article_url, link) for link in links])
    db.execute("INSERT OR IGNORE INTO links_done VALUES (?)", (article_url,))


def entry_date(entry) -> dt.date | None:
    stamp = entry.get("published_parsed") or entry.get("updated_parsed")
    return dt.date(*stamp[:3]) if stamp else None


def keep(entry, source: dict) -> bool:
    """Filtre facultatif par mots-clés (titre et catégories)."""
    haystack = " ".join([entry.get("title", ""), *[t.get("term", "") for t in entry.get("tags", [])]]).lower()
    include = [w.lower() for w in source.get("include") or []]
    exclude = [w.lower() for w in source.get("exclude") or []]
    if include and not any(w in haystack for w in include):
        return False
    return not any(w in haystack for w in exclude)


def article_markdown(title: str, url: str, source: dict, author: str, published: str,
                     text: str, complete: bool) -> str:
    safe = lambda s: s.replace('"', "'")  # noqa: E731
    header = [
        "---",
        f'title: "{safe(title)} · {safe(source["name"])}"',
        f'url: "{url}"',
        f'source: "{source["key"]}"',
        f'author: "{safe(author)}"',
        f"published: {published}",
        f"collected: {dt.date.today().isoformat()}",
        f"complete: {'true' if complete else 'false'}",
        "---",
        "",
    ]
    text = re.sub(rf"\A#+\s*{re.escape(title)}\s*\n+", "", text.lstrip())  # titre déjà en tête
    byline = ", ".join(p for p in (source["name"], author, f"publié le {published}") if p)
    note = "" if complete else "\n\n> Extrait seulement : le texte complet n'était pas accessible (paywall probable)."
    return "\n".join(header) + f"# {title}\n\nSource : {byline}. {url}{note}\n\n{text}\n"


def collect_source(http: httpx.Client, db: sqlite3.Connection, source: dict, since: dt.date) -> tuple[int, int]:
    import feedparser
    response = http.get(source["feed"])
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"flux illisible : {feed.bozo_exception}")
    if not feed.entries and not feed.version:  # page HTML, redirection vers l'accueil : pas un flux, pas un flux vide
        kind = response.headers.get("content-type", "type inconnu").split(";")[0].strip()
        raise ValueError(f"la réponse n'est pas un flux RSS ou Atom ({kind}, {response.url})")
    new = partial = 0
    for entry in feed.entries:
        if not entry.get("link"):
            continue
        url = clean_url(entry.link)
        if db.execute("SELECT 1 FROM articles WHERE url = ?", (url,)).fetchone():
            continue
        published = entry_date(entry)
        if published and published < since:
            continue
        if not keep(entry, source):
            continue
        title = (entry.get("title") or "Sans titre").strip()
        # Même source, même titre, même date de publication, collecté un jour précédent : c'est le même article revenu
        # sous une autre URL (hôte ou chemin changé), pas un second article. Sans cela, il serait gardé en « -2.md ».
        # Deux entrées identiques du même flux, collectées ensemble, restent deux articles (« -2.md » les distingue).
        if published and db.execute("SELECT 1 FROM articles WHERE source = ? AND title = ? AND published = ? "
                                    "AND substr(collected, 1, 10) < ?",
                                    (source["key"], title, published.isoformat(), dt.date.today().isoformat())).fetchone():
            continue
        bodies = [c.get("value", "") for c in entry.get("content", [])] + [entry.get("summary", "")]
        feed_html = max(bodies, key=len) if any(bodies) else ""
        text = html_to_markdown(feed_html) if feed_html else ""
        page_html = ""
        if len(text) < MIN_FULL_TEXT:
            page_html = fetch_html(http, url)
            fetched = page_text(http, url, page_html)
            if len(fetched) > len(text):
                text = fetched
        complete = len(text) >= MIN_KEPT_TEXT and "Continue reading" not in text[-200:]
        day = (published or dt.date.today()).isoformat()
        name = f"{day}-{slugify(source['key'], 30)}-{slugify(title, 60)}.md"
        folder = collection_dir(source)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
        counter = 2
        while target.exists():
            target = folder / name.replace(".md", f"-{counter}.md")
            counter += 1
        target.write_text(
            article_markdown(title, url, source, entry.get("author", ""), day, text, complete), encoding="utf-8"
        )
        db.execute(
            "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?)",
            (url, source["key"], title, target.name, day, int(complete), dt.datetime.now().isoformat(timespec="seconds")),
        )
        store_links(db, url, content_links(url, feed_html, page_html))  # pour les sources suggérées
        db.commit()  # un article à la fois : une collecte interrompue reprend sans doublon
        new += 1
        partial += not complete
        time.sleep(1)  # politesse envers les sites
    return new, partial


def cmd_collect(args: argparse.Namespace) -> None:
    sources = [s for s in load_sources() if s.get("active") and s.get("feed")]
    if not sources:
        sys.exit(f"Aucune source active avec un flux dans {SOURCES_FILE}.")
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    since = dt.date.today() - dt.timedelta(days=args.since_days)
    db = state()
    report, failures, total = [], [], 0
    now = lambda: dt.datetime.now().isoformat(timespec="seconds")  # noqa: E731
    with client() as http:
        for source in sources:
            try:
                new, partial = collect_source(http, db, source, since)
                db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?, ?, NULL)", (source["key"], now(), now()))
                total += new
                line = f"{source['key']} : {new} nouveaux" + (f" dont {partial} extraits seulement" if partial else "")
            except Exception as error:  # une source en panne ne bloque pas les autres
                db.execute(
                    "INSERT INTO runs VALUES (?, ?, NULL, ?) ON CONFLICT(source) DO UPDATE SET last_try = ?, error = ?",
                    (source["key"], now(), str(error)[:300], now(), str(error)[:300]),
                )
                failures.append(source["key"])
                line = f"{source['key']} : ERREUR {str(error)[:150]}"
            db.commit()
            report.append(line)
            print(line)
    summary = f"{now()} · {total} nouveaux articles · {len(failures)} sources en erreur"
    (WATCH_DIR / "_rapport_collecte.txt").write_text("\n".join([summary, "", *report]) + "\n", encoding="utf-8")
    print(f"\n{summary}\nArticles : {ARTICLES_DIR}")


# ---------------------------------------------------------------------------
# Sélection à lire
# ---------------------------------------------------------------------------

def cmd_links(args: argparse.Namespace) -> None:
    """Relève une fois les liens cités par les articles collectés avant que la collecte les garde."""
    db = state()
    todo = db.execute(
        "SELECT url, title FROM articles WHERE url NOT IN (SELECT article_url FROM links_done) "
        "AND url LIKE 'http%' ORDER BY collected"
    ).fetchall()
    print(f"{len(todo)} articles dont les liens n'ont pas encore été relevés")
    found = failed = 0
    with client() as http:
        for number, (url, title) in enumerate(todo, 1):
            html = fetch_html(http, url)
            if not html:
                failed += 1
                print(f"[{number}/{len(todo)}] {title[:60]} · page inaccessible, reprise au prochain lancement")
                continue
            links = content_links(url, page_html=html)
            store_links(db, url, links)
            db.commit()
            found += len(links)
            print(f"[{number}/{len(todo)}] {title[:60]} · {len(links)} liens")
            time.sleep(1)  # politesse envers les sites
    print(f"\n{found} liens relevés · {failed} pages inaccessibles (relancer plus tard pour les reprendre)")


def cmd_digest(args: argparse.Namespace) -> None:
    db = state()
    since = (dt.date.today() - dt.timedelta(days=args.days)).isoformat()
    rows = db.execute(
        "SELECT source, title, url, published, complete, file FROM articles "
        "WHERE collected >= ? ORDER BY source, published DESC",
        (since,),
    ).fetchall()
    sources = load_sources()
    names = {s["key"]: s.get("name", s["key"]) for s in sources}
    own = {s["key"] for s in sources if (s.get("collection") or ARTICLES_DIR.name) != ARTICLES_DIR.name}
    rows = [row for row in rows if row[0] not in own]  # vos propres articles ne sont pas « à lire »
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[0]].append(row)
    lines = [f"# À lire : articles collectés depuis le {since}", "",
             f"{len(rows)} articles. Pour un article retenu, coller son lien dans SignalPM.", ""]
    for key, items in grouped.items():
        lines += [f"## {names.get(key, key)}", ""]
        for _, title, url, published, complete, file in items:
            flag = "" if complete else " (extrait seulement)"
            lines.append(f"- {published} · [{title}]({url}){flag}")
        lines.append("")
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    target = to_read_file()
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(rows)} articles · {target}")


# ---------------------------------------------------------------------------
# Import de l'export Medium (vos propres articles)
# ---------------------------------------------------------------------------

def medium_post(html: str) -> dict | None:
    """Lit un article de l'export Medium (posts/*.html) : titre, date, lien, texte."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    body = soup.find(attrs={"data-field": "body"}) or soup.find(class_="e-content")
    if body is None:
        return None
    title_tag = soup.find(class_="p-name") or soup.find("title")
    title = title_tag.get_text(" ", strip=True) if title_tag else "Sans titre"
    for heading in body.find_all(["h1", "h2", "h3"], limit=1):  # Medium répète le titre en tête du corps
        if heading.get_text(" ", strip=True) == title:
            heading.decompose()
    time_tag = soup.find("time", class_="dt-published")
    canonical = soup.find("a", class_="p-canonical")
    subtitle = soup.find(attrs={"data-field": "subtitle"})
    return {
        "title": title,
        "date": (time_tag.get("datetime") or "")[:10] if time_tag else "",
        "url": canonical["href"] if canonical and canonical.get("href") else "",
        "subtitle": subtitle.get_text(" ", strip=True) if subtitle else "",
        "text": html_to_markdown(str(body)),
    }


def cmd_import_medium(args: argparse.Namespace) -> None:
    import zipfile
    source = next((s for s in load_sources() if s["key"] == args.source), None) or {
        "key": args.source, "name": args.source}
    source = {**source, "collection": args.collection}
    folder = collection_dir(source)
    folder.mkdir(parents=True, exist_ok=True)
    db = state()
    imported = skipped_short = skipped_known = drafts = 0
    with zipfile.ZipFile(Path(args.export).expanduser()) as archive:
        names = [n for n in archive.namelist() if "/posts/" in f"/{n}" and n.endswith(".html")]
        for name in sorted(names):
            if Path(name).name.startswith("draft_"):
                drafts += 1
                continue
            post = medium_post(archive.read(name).decode("utf-8", errors="replace"))
            if not post or len(post["text"]) < args.min_chars:  # réponses et commentaires : trop courts
                skipped_short += 1
                continue
            url = clean_url(post["url"]) if post["url"] else f"medium-export:{Path(name).stem}"
            if db.execute("SELECT 1 FROM articles WHERE url = ?", (url,)).fetchone():
                skipped_known += 1
                continue
            day = post["date"] or Path(name).name[:10]
            text = (f"*{post['subtitle']}*\n\n" if post["subtitle"] else "") + post["text"]
            target = folder / f"{day}-{slugify(source['key'], 30)}-{slugify(post['title'], 60)}.md"
            target.write_text(
                article_markdown(post["title"], post["url"], source, args.author, day, text, True),
                encoding="utf-8",
            )
            db.execute(
                "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?)",
                (url, source["key"], post["title"], target.name, day, 1,
                 dt.datetime.now().isoformat(timespec="seconds")),
            )
            db.commit()
            imported += 1
    print(f"{len(names)} fichiers d'articles dans l'export · importés : {imported} · "
          f"brouillons ignorés : {drafts} · trop courts (réponses) : {skipped_short} · "
          f"déjà présents : {skipped_known}\nDossier : {folder}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Veille automatisée de PMZilla Lab")
    commands = parser.add_subparsers(dest="command", required=True)
    sources = commands.add_parser("sources", help="déduire les sources des liens déjà partagés")
    sources.add_argument("--bluesky", help="compte Bluesky, ex. prenom.bsky.social")
    sources.add_argument("--linkedin", help="chemin de Shares.csv (export LinkedIn)")
    sources.add_argument("--claude-export", nargs="+",
                         help="export Claude : conversations-000.zip et projects-000.zip (ou dossiers décompressés)")
    sources.add_argument("--urls", help="fichier texte contenant des liens")
    collect = commands.add_parser("collect", help="collecter les nouveaux articles")
    collect.add_argument("--since-days", type=int, default=30, help="ignorer les articles plus anciens (défaut 30)")
    commands.add_parser("links", help="relever une fois les liens des articles déjà collectés")
    medium = commands.add_parser("import-medium", help="importer vos articles depuis l'export Medium")
    medium.add_argument("export", help="archive .zip de l'export Medium")
    medium.add_argument("--source", required=True, help="clé de la source dans sources.yaml (medium.com/@<utilisateur>)")
    medium.add_argument("--collection", default=watch_paths.OWN_COLLECTION)
    medium.add_argument("--author", required=True, help="nom d'auteur écrit dans l'en-tête des articles importés")
    medium.add_argument("--min-chars", type=int, default=800, help="en dessous : réponse, ignorée")
    digest = commands.add_parser("digest", help="écrire la liste des articles à lire")
    digest.add_argument("--days", type=int, default=7)
    args = parser.parse_args(argv)
    commands_map = {"sources": cmd_sources, "collect": cmd_collect, "digest": cmd_digest, "links": cmd_links,
                    "import-medium": cmd_import_medium}
    commands_map[args.command](args)


if __name__ == "__main__":
    main()
