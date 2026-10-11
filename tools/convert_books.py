# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf4llm", "pymupdf", "ebooklib", "markdownify", "beautifulsoup4", "pyyaml"]
# ///
"""
Convertit une bibliothèque de PDF et d'EPUB en Markdown (pour PMZilla Lab et Open WebUI).

Usage :
    uv run convert_books.py <dossier_livres> <dossier_markdown> [--dry-run]
    ex : uv run convert_books.py "~/Downloads/Livres - Ressources" "~/Bibliotheque-MD/Livres - Ressources"
        Conversion normale : le Markdown existant de chaque livre est retrouvé par la même recherche que
        --redo-figures (correspondance explicite SOURCES, nom de fichier, MAPPING) et réécrit sur place ;
        l'ancien est gardé en « .md.avant-figures » (une seule fois). Un livre sans Markdown existant n'est pas
        converti : il est listé (sortie et rapport), à traiter avec --convert-book. Arrêt avant toute
        conversion, avec toutes les erreurs listées, s'il y a plusieurs correspondances, une clé vers un
        fichier absent ou deux livres vers le même Markdown. Les dossiers de la source n'ont aucune influence
        sur le chemin du Markdown. --dry-run : résout et affiche (source -> Markdown, voie, livres sans
        Markdown, erreurs) sans rien écrire. Les sources de la table EXCLUSIONS (mapping_lab.py, avec leur raison)
        sont ignorées : ni converties, ni listées « sans Markdown » ; --redo-figures refuse un livre exclu.

    uv run convert_books.py --figure-statistics <dossier_livres> [<dossier_sortie>]
        Analyse seule : compte, livre par livre, les figures (images, schémas vectoriels), leurs légendes
        (« Figure 1.2 », figcaption, texte alternatif) et dit combien de livres ont des légendes exploitables.
        Ne convertit rien, n'écrit rien dans la bibliothèque ni dans l'index, ne modifie aucun livre. Écrit
        seulement _statistiques_figures.txt dans <dossier_sortie> (par défaut Bibliotheque-MD du workspace) ;
        le fichier n'est pas lisible par Claude Code. L'agrégat, sans aucun titre de livre, est la dernière
        partie de la sortie : c'est elle qu'on peut copier. Voir la piste « Illustrations et schémas ».
        Écrit aussi ~/PMZilla-Lab/figures-a-refaire.txt (variable PMZILLA_LAB_FIGURES_A_REFAIRE) : un livre
        source par ligne qui a au moins une figure retenue, chemin relatif au dossier des livres, et en
        commentaire le nombre de figures retenues ; la liste se donne telle quelle à --redo-figures (@liste).

    uv run convert_books.py <dossier_livres> <dossier_markdown> --redo-figures <livre> [<livre> ...]
        Reconvertit seulement les livres nommés (chemin relatif au dossier des livres, avec ou sans
        extension, ou nom du fichier ; « @liste.txt » pour une liste, un livre par ligne) pour y mettre
        les blocs de figures. Le Markdown existant de chaque livre est cherché par son nom de fichier dans
        tout le dossier de sortie (les dossiers de la source ont pu être renommés) et réécrit à cet endroit ;
        zéro ou plusieurs Markdown du même nom : arrêt avant toute conversion, chemins listés. L'ancien
        Markdown est gardé à côté en « .md.avant-figures » (une seule fois).
        Quand aucun Markdown ne porte le nom du livre (EPUB à titre d'ISBN, Markdown renommé à la main), la
        table MAPPING (mapping_lab.py, la même que sort_by_domain.py) est consultée : une clé dont le nom de
        fichier, sans casse ni accents, est celui du livre, ou dont le Markdown déclare le livre dans son
        en-tête (« source: »). Avant les deux, la table SOURCES de mapping_lab.py (correspondance explicite
        source -> Markdown) l'emporte : un Markdown absent est une erreur. Arrêt avant toute conversion, avec
        toutes les erreurs listées : aucune
        correspondance, plusieurs correspondances, clé vers un fichier absent, deux livres vers le même
        Markdown. Le rapport dit, pour chaque livre, la voie suivie (correspondance explicite, nom ou MAPPING).
        Une ligne de la liste peut finir par un commentaire (« livre.epub  # 12 figures ») : il est ignoré.
        Rapport : _rapport_figures.txt (le rapport de conversion complet n'est pas touché).

    uv run convert_books.py <dossier_livres> <dossier_markdown> --redo-figures <livre> [...] --dry-run
        Simulation : résout chaque livre (source -> Markdown, voie nom ou MAPPING) et affiche toutes les
        erreurs de correspondance ; ne convertit rien, n'écrit rien (ni Markdown, ni sauvegarde, ni rapport,
        ni image), n'ouvre aucun livre. Code de sortie 1 s'il y a une erreur.

    uv run convert_books.py <dossier_livres> <dossier_markdown> --convert-book <livre> --to <Markdown>
        Convertit ce seul livre (jamais converti) et écrit son Markdown au chemin donné, relatif au dossier de
        sortie (ex. « Books/Titre.md »), pour le ranger dans un ancien dossier cohérent avec MAPPING. Arrêt
        avant toute conversion si le livre est introuvable ou ambigu, si le Markdown existe déjà (rien n'est
        jamais écrasé), si un autre Markdown porte le même nom de fichier, ou si le chemin n'est pas une clé de
        MAPPING. Aucun autre livre n'est touché ; rapport : _rapport_livre.txt.

- Parcourt les sous-dossiers de la source ; le Markdown garde l'emplacement qu'il a déjà (pas de nouvelle arborescence).
- PDF : extraction par PyMuPDF4LLM. EPUB : HTML du livre converti en Markdown, chapitres et
  titres conservés (meilleure structure que le PDF).
- Si un livre existe dans les deux formats (même nom), l'EPUB est préféré et le PDF ignoré, sauf si
  l'EPUB échoue à la conversion (fichier corrompu) : le PDF du même livre est alors converti à sa place
  et le rapport le signale (« Repli sur le PDF »).
- Ne reprend pas là où il s'est arrêté : chaque passage réécrit tous les livres qui ont un Markdown.
- Signale les PDF qui contiennent très peu de texte (probablement scannés -> OCR nécessaire)
  et les EPUB vides (probablement protégés par DRM).
- Écrit un rapport _rapport_conversion.txt dans le dossier de sortie.
- Figures : une figure devient un bloc de texte (`<!-- figure id=… source=… page=… image="…" -->`, puis
  « Légende : … » et « Texte alternatif : … ») quand elle a une légende ou, pour un EPUB, un texte alternatif
  utile (ni vide, ni nom de fichier, ni mot générique comme « image » ou « logo », ni moins de
  MIN_ALT_WORDS mots sans légende). Pour un PDF, seuls les visuels à légende numérotée (« Figure 1.2 »)
  deviennent des blocs ; les images et zones vectorielles sans légende ne sont ni extraites ni indexées.
  Les images des figures retenues vont dans Bibliotheque-Images/<livre>/fig-NNNN.<ext> (dossier hors Git,
  illisible par Claude Code ; PDF : la zone de la page est rendue en PNG).
"""
import base64
import os
import posixpath
import re
import shutil
import statistics
import sys
import time
import unicodedata
import warnings
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

from mapping_lab import EXCLUSIONS, MAPPING, SOURCES, fold

MIN_CHARS_PER_PAGE = 200    # PDF : en dessous, probablement scanné
MIN_CHARS_EPUB = 2000       # EPUB : en dessous, probablement protégé par DRM ou vide

WORKSPACE = Path(os.environ.get("PMZILLA_LAB_WORKSPACE", "~/PMZilla-Lab/workspace")).expanduser()
IMAGES_DIR = Path(os.environ.get("PMZILLA_LAB_IMAGES", str(WORKSPACE / "Bibliotheque-Images"))).expanduser()
LISTE_A_REFAIRE = Path(os.environ.get("PMZILLA_LAB_FIGURES_A_REFAIRE",
                                      str(WORKSPACE.parent / "figures-a-refaire.txt"))).expanduser()
IMAGES_NAME = "Bibliotheque-Images"   # préfixe des chemins écrits dans le Markdown (relatifs au workspace)
PDF_RENDER_DPI = 150


def header(title: str, source: str, pages: int | None = None, figures: int | None = None) -> str:
    title = title.replace('"', "'")
    lines = ["---", f'title: "{title}"', f'source: "{source}"']
    if pages is not None:
        lines.append(f"pages: {pages}")
    if figures is not None:   # présent = livre converti avec les blocs de figures (0 = aucune figure retenue)
        lines.append(f"figures: {figures}")
    return "\n".join(lines + ["---", "", ""])


def convert_pdf(path: Path, images: "ImageSink | None" = None) -> tuple[str, str | None]:
    import pymupdf
    import pymupdf4llm

    sink = images if images is not None else ImageSink(None, path.stem)
    blocks: dict[int, list[str]] = {}
    with pymupdf.open(path) as doc:
        pages = doc.page_count
        for page in doc:
            retained = sorted((v for v in pdf_visuals(page)[0] if v["caption"]), key=lambda v: (v["rect"].y0, v["rect"].x0))
            for visual in retained:   # seuls les visuels à légende numérotée deviennent des blocs
                fig_id = sink.next_id()
                reference = sink.save_pixmap(fig_id, page, visual["rect"])
                blocks.setdefault(page.number, []).append(
                    figure_block(fig_id, "pdf", visual["caption"], None, reference, page=page.number + 1))
    if blocks:
        chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True)   # même texte, page par page
        md = "".join(chunk["text"] + "".join(f"\n{block}\n\n" for block in blocks.get(number, []))
                     for number, chunk in enumerate(chunks))
        base = "".join(chunk["text"] for chunk in chunks)
    else:
        md = base = pymupdf4llm.to_markdown(str(path))
    warning = None
    if pages and len(base) / pages < MIN_CHARS_PER_PAGE:
        warning = f"PDF probablement scanné ({len(base)} caractères pour {pages} pages)"
    return header(path.stem, path.name, pages, sink.count) + md, warning


def convert_epub(path: Path, images: "ImageSink | None" = None) -> tuple[str, str | None]:
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub
    from markdownify import markdownify

    warnings.filterwarnings("ignore")  # ebooklib prévient sur des options futures, sans conséquence
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    titles = book.get_metadata("DC", "title")
    title = titles[0][0].strip() if titles and titles[0][0].strip() else path.stem

    # Titres de chapitres pris dans la table des matières : beaucoup d'EPUB d'éditeurs marquent
    # leurs chapitres par des paragraphes mis en forme plutôt que par des balises <h1>-<h6>.
    toc_titles: dict[str, str] = {}

    def walk(entries) -> None:
        for entry in entries:
            if isinstance(entry, tuple):  # (Section, [sous-entrées])
                section, children = entry
                walk(children)  # d'abord les chapitres : le titre le plus précis l'emporte sur la partie
                href = getattr(section, "href", None)
                if href and getattr(section, "title", None):
                    toc_titles.setdefault(href.split("#")[0], section.title.strip())
            elif getattr(entry, "href", None) and getattr(entry, "title", None):
                toc_titles.setdefault(entry.href.split("#")[0], entry.title.strip())

    walk(book.toc)

    sink = images if images is not None else ImageSink(None, path.stem)
    parts = []
    spine_ids = [item_id for item_id, _ in book.spine]
    items = [book.get_item_with_id(i) for i in spine_ids] or list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    for item in items:
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        blocks: dict[str, str] = {}
        if not EPUB_COVER.search(item.get_name()):
            for unit in epub_units(soup)[0]:
                if not unit_retained(unit):   # ni légende ni texte alternatif utile : supprimé comme avant
                    continue
                fig_id = sink.next_id()
                data = epub_image(book, item, unit["visuals"][0])
                reference = sink.save_bytes(fig_id, *data) if data else None
                token = f"@@FIG:{fig_id}@@"
                blocks[token] = figure_block(fig_id, "epub", unit["caption"],
                                             unit["alt"] if unit["alt_etat"] == "utile" else None, reference,
                                             visuals=len(unit["visuals"]))
                placeholder = soup.new_tag("p")
                placeholder.string = token
                unit["anchor"].insert_after(placeholder)
                for element in [*unit["remove"], unit["caption_el"]]:
                    if element is not None and not element.decomposed:
                        element.decompose()
        for tag in soup(["script", "style", "img", "svg", "figure", "nav"]):
            if not tag.decomposed:
                tag.decompose()
        body = soup.body or soup
        md = markdownify(str(body), heading_style="ATX", strip=["a", "span"])
        for token, block in blocks.items():
            md = md.replace(token, block)
        md = re.sub(r"\n{3,}", "\n\n", md).strip()
        if not md:
            continue
        has_heading = re.search(r"^#{1,6} ", md, flags=re.M) is not None
        toc_title = toc_titles.get(item.get_name()) or toc_titles.get(Path(item.get_name()).name)
        if not has_heading and toc_title:
            md = f"# {toc_title}\n\n{md}"
        parts.append(md)

    text = "\n\n".join(parts)
    warning = None
    if len(text) < MIN_CHARS_EPUB:
        warning = f"EPUB presque vide ({len(text)} caractères) : protégé par DRM ?"
    return header(title, path.name, figures=sink.count) + text + "\n", warning


# ---------------------------------------------------------------------------
# Figures : détection, filtre des textes alternatifs, blocs de texte, images extraites, statistiques
# ---------------------------------------------------------------------------

# « Figure 1.2 », « Fig. 3-4 », « Exhibit 5 », « Schéma 2 », « Figure A.3 », « Figure 1.2a »
LABEL = re.compile(r"^\s*(?:figure|fig\.?|exhibit|illustration|sch[ée]ma|diagramme|diagram|graphique|chart)\s*"
                   r"(?:[A-Z](?=[.\-]?\d)[.\-]?)?\s*\d+(?:\s*[.\-–]\s*\d+)*[a-z]?\b", re.IGNORECASE)
CAPTION_CLASS = re.compile(r"caption|l[ée]gende|legend|figure-?title|fig-?title|figtitle", re.IGNORECASE)
BLOCK_TAGS = ("p", "div", "li", "td", "th", "section", "article", "blockquote", "center", "aside")
CAPTION_MAX = 400           # au-delà, ce n'est pas une légende mais un paragraphe qui parle de la figure
ORNAMENT_PX = 40            # EPUB : image dont la largeur ou la hauteur déclarée est inférieure = ornement
PDF_MIN_VISUAL_PT = 50      # PDF : image intégrée plus petite (largeur ou hauteur, en points) = ornement
PDF_MIN_VECTOR = (60, 40)   # PDF : zone de dessin vectoriel plus petite = filet, cadre ou puce, ignorée
PDF_CAPTION_GAP_PT = 60     # PDF : écart vertical maximal entre un visuel et sa légende
EPUB_COVER = re.compile(r"cover|couverture", re.IGNORECASE)

# Texte alternatif : utile seulement s'il décrit l'image. Seuil proposé : au moins MIN_ALT_WORDS mots quand aucune
# légende n'accompagne l'image (une légende rend utile un alt plus court, mais jamais un alt vide, un nom de fichier
# ou un mot générique).
MIN_ALT_WORDS = 4
ALT_EXTENSION = re.compile(r"\.(?:png|jpe?g|gif|svg|webp|bmp|tiff?|eps|pdf)\s*$", re.IGNORECASE)
ALT_FILENAME = re.compile(r"^[\w.\-]*[_\-]\d|^[\w.\-]*\d[_\-]|^[A-Za-z]*\d{2,}[A-Za-z]*$|^[0-9a-f]{12,}$", re.IGNORECASE)
ALT_GENERIC = frozenset({
    "image", "images", "img", "figure", "fig", "photo", "photos", "picture", "pic", "pics", "logo", "logos", "icon",
    "icons", "icone", "icones", "icône", "icônes", "illustration", "illustrations", "graphic", "graphics",
    "graphique", "graphiques", "graph", "chart", "diagram", "diagramme", "schéma", "schema", "dessin", "drawing",
    "screenshot", "capture", "cover", "couverture", "visuel", "placeholder", "thumbnail", "vignette", "banner",
    "bannière", "ornament", "separator", "spacer", "bullet"})
ALT_STOPWORDS = frozenset({"a", "an", "the", "of", "de", "la", "le", "les", "un", "une", "des", "du", "d", "l", "et",
                           "and", "or", "ou", "pour", "for", "to", "in", "en", "sur", "on"})
ALT_REASONS = ("fichier", "générique", "court")   # raisons d'un texte alternatif inutile, dans l'ordre des tests


def alt_status(alt: str, has_caption: bool) -> str | None:
    """None si le texte alternatif est vide ; « utile » ; ou la raison pour laquelle il est inutile :
    « fichier » (nom de fichier ou chemin), « générique » (seulement image, figure, photo, logo, icône… et des
    chiffres) ou « court » (moins de MIN_ALT_WORDS mots, sans légende à côté)."""
    text = " ".join(alt.split())
    if not text:
        return None
    single = " " not in text
    if ALT_EXTENSION.search(text) or (single and ("/" in text or ALT_FILENAME.match(text))):
        return "fichier"
    tokens = re.findall(r"[^\W_]+", text.lower())
    if not [t for t in tokens if not t.isdigit() and t not in ALT_STOPWORDS and t not in ALT_GENERIC]:
        return "générique"
    if not has_caption and len(text.split()) < MIN_ALT_WORDS:
        return "court"
    return "utile"


def unit_retained(unit: dict) -> bool:
    """Un visuel d'EPUB devient un bloc s'il a une légende (de toute forme) ou un texte alternatif utile."""
    return unit["legende"] is not None or unit["alt_etat"] == "utile"


def _text_of(element) -> str:
    return " ".join(element.get_text(" ", strip=True).split())


def _is_caption(element) -> bool:
    """Un élément voisin d'une image est une légende s'il commence par « Figure X.Y » ou porte une classe de légende."""
    text = _text_of(element)
    if not text or len(text) > CAPTION_MAX:
        return False
    classes = " ".join(element.get("class") or []) + " " + (element.get("id") or "")
    return bool(LABEL.match(text) or CAPTION_CLASS.search(classes))


def _declared_size(tag) -> int | None:
    sizes = []
    for attribute in ("width", "height"):
        match = re.match(r"\s*(\d+)", str(tag.get(attribute) or ""))
        if match:
            sizes.append(int(match.group(1)))
    return min(sizes) if sizes else None


def _alt_text(visual) -> str:
    if visual.name == "img":
        return " ".join((visual.get("alt") or "").split())
    title = visual.find("title")
    return _text_of(title) if title else " ".join((visual.get("aria-label") or "").split())


def epub_units(soup) -> tuple[list[dict], int]:
    """Visuels d'une page d'EPUB : une <figure> qui contient une image ou un svg, ou une image ou un svg isolé.
    Pour chacun : légende (figcaption, élément de classe « légende », paragraphe voisin « Figure X.Y »), texte
    alternatif et son état (voir alt_status), et les éléments à remplacer par le bloc. Renvoie aussi le nombre
    d'ornements ignorés (images déclarées très petites). Ne modifie pas la page."""
    body = soup.body or soup
    units, ornaments = [], 0
    used: set[int] = set()   # une légende ne sert qu'à un visuel (celle d'au-dessus n'est pas celle de l'image suivante)

    def neighbour_caption(block):
        for sibling in (block.find_next_sibling(), block.find_previous_sibling()):
            if sibling is not None and id(sibling) not in used and sibling.name not in ("img", "svg") \
                    and not sibling.find(["img", "svg"]) and _is_caption(sibling):
                used.add(id(sibling))
                return sibling
        return None

    def finish(unit: dict) -> None:
        unit["numerotee"] = bool(unit["caption"] and LABEL.match(unit["caption"]))
        alts = [a for a in (_alt_text(v) for v in unit["visuals"]) if a]
        unit["alt"] = alts[0] if alts else ""
        unit["alt_etat"] = alt_status(unit["alt"], unit["legende"] is not None)
        unit["vecteur"] = all(v.name == "svg" for v in unit["visuals"])
        units.append(unit)

    for figure in body.find_all("figure"):
        visuals = [v for v in figure.find_all(["img", "svg"]) if not v.find_parent("svg")]
        if not visuals:
            continue   # une <figure> qui n'est pas une image (code, citation, tableau)
        sizes = [_declared_size(v) for v in visuals if v.name == "img"]
        if sizes and all(s is not None and s <= ORNAMENT_PX for s in sizes) and len(sizes) == len(visuals):
            ornaments += 1
            continue
        unit = {"forme": "figure", "visuals": visuals, "legende": None, "caption": None, "caption_el": None,
                "anchor": figure, "remove": [figure]}
        figcaption = figure.find("figcaption")
        if figcaption is not None and _text_of(figcaption):
            unit.update(legende="figcaption", caption=_text_of(figcaption))
        else:
            inner = next((e for e in figure.find_all(True) if e.name not in ("img", "svg") and not e.find_parent("svg")
                          and _is_caption(e)), None)
            if inner is not None:
                unit.update(legende="classe", caption=_text_of(inner))
            else:
                neighbour = neighbour_caption(figure)
                if neighbour is not None:
                    unit.update(legende="voisin", caption=_text_of(neighbour), caption_el=neighbour)
        finish(unit)
    for visual in body.find_all(["img", "svg"]):
        if visual.find_parent("figure") or visual.find_parent("svg"):
            continue   # déjà compté avec sa <figure>, ou partie d'un svg
        size = _declared_size(visual) if visual.name == "img" else None
        if size is not None and size <= ORNAMENT_PX:
            ornaments += 1
            continue
        block = visual.find_parent(BLOCK_TAGS)
        if block is None or block is body:
            block = visual
        unit = {"forme": visual.name, "visuals": [visual], "legende": None, "caption": None, "caption_el": None,
                "anchor": block, "remove": [visual]}
        own = _text_of(block) if block is not visual else ""
        if own and LABEL.match(own) and len(own) <= CAPTION_MAX:   # légende dans le même bloc que l'image
            unit.update(legende="voisin", caption=own, remove=[block])
        elif block is not visual:
            neighbour = neighbour_caption(block)
            if neighbour is not None:
                unit.update(legende="voisin", caption=_text_of(neighbour), caption_el=neighbour)
        finish(unit)
    return units, ornaments


def epub_image(book, item, visual) -> tuple[bytes, str] | None:
    """Octets et extension de l'image d'un visuel d'EPUB : fichier du livre, image « data: », ou svg en ligne."""
    if visual.name == "svg":
        svg = re.sub(r"\bviewbox=", "viewBox=", str(visual), flags=re.IGNORECASE)   # html.parser met les noms en minuscules
        if "xmlns=" not in svg.split(">", 1)[0]:
            svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        return svg.encode("utf-8"), ".svg"
    source = (visual.get("src") or "").strip()
    if source.startswith("data:"):
        header_part, _, payload = source.partition(",")
        if ";base64" not in header_part:
            return None
        kind = header_part[5:].split(";")[0].split("/")[-1]
        extension = {"png": ".png", "jpeg": ".jpg", "jpg": ".jpg", "gif": ".gif", "svg+xml": ".svg",
                     "webp": ".webp"}.get(kind, ".png")
        try:
            return base64.b64decode(payload), extension
        except ValueError:
            return None
    if not source:
        return None
    href = posixpath.normpath(posixpath.join(posixpath.dirname(item.get_name()),
                                             unquote(source.split("#")[0].split("?")[0])))
    image = book.get_item_with_href(href)
    if image is None:
        return None
    return image.get_content(), (Path(href).suffix.lower() or ".png")


class ImageSink:
    """Numérote les figures d'un livre (fig-0001, fig-0002…) et range leurs images dans
    <dossier>/<livre>/. Le dossier du livre est vidé au départ : ce sont des fichiers générés, une
    reconversion ne laisse pas d'images d'une version précédente. dossier=None : numérote sans rien écrire."""

    def __init__(self, folder: Path | None, stem: str):
        self.folder, self.stem, self.count, self.saved, self.missing = folder, stem, 0, 0, 0
        if folder is not None:
            shutil.rmtree(folder / stem, ignore_errors=True)

    def next_id(self) -> str:
        self.count += 1
        return f"fig-{self.count:04d}"

    def _target(self, fig_id: str, extension: str) -> Path | None:
        if self.folder is None:
            return None
        target = self.folder / self.stem / f"{fig_id}{extension}"
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def reference(self, target: Path) -> str:
        return f"{IMAGES_NAME}/{self.stem}/{target.name}"

    def save_bytes(self, fig_id: str, data: bytes, extension: str) -> str | None:
        target = self._target(fig_id, extension)
        if target is None:
            return None
        target.write_bytes(data)
        self.saved += 1
        return self.reference(target)

    def save_pixmap(self, fig_id: str, page, rect) -> str | None:
        """Rend la zone de la page en PNG (figure vectorielle ou image d'un PDF)."""
        target = self._target(fig_id, ".png")
        if target is None:
            return None
        clip = (rect + (-4, -4, 4, 4)) & page.rect
        page.get_pixmap(clip=clip, dpi=PDF_RENDER_DPI).save(str(target))
        self.saved += 1
        return self.reference(target)

    def discard(self) -> None:
        if self.folder is not None:
            shutil.rmtree(self.folder / self.stem, ignore_errors=True)


def figure_block(fig_id: str, source: str, caption: str | None, alt: str | None, reference: str | None,
                 page: int | None = None, visuals: int = 1) -> str:
    """Bloc de texte d'une figure retenue : une ligne de commentaire Markdown qui porte l'identifiant, la
    source, la page et le chemin de l'image (texte seulement), puis la légende de l'auteur et le texte alternatif."""
    fields = [f"id={fig_id}", f"source={source}"]
    if page:
        fields.append(f"page={page}")
    if visuals > 1:
        fields.append(f"visuels={visuals}")
    if reference:
        fields.append(f'image="{reference.replace(chr(34), chr(39))}"')
    lines = [f"<!-- figure {' '.join(fields)} -->"]
    if caption:
        lines.append(f"Légende : {caption}")
    if alt and alt != caption:
        lines.append(f"Texte alternatif : {alt}")
    return "\n".join(lines)


def figure_stats_epub(path: Path) -> dict:
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub

    warnings.filterwarnings("ignore")
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    spine_ids = [item_id for item_id, _ in book.spine]
    items = [book.get_item_with_id(i) for i in spine_ids] or list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    units, ornaments = [], 0
    for item in items:
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT or EPUB_COVER.search(item.get_name()):
            continue
        found, small = epub_units(BeautifulSoup(item.get_content(), "html.parser"))
        units += found
        ornaments += small
    reasons = Counter(u["alt_etat"] for u in units if u["alt_etat"] in ALT_REASONS)
    repeated = Counter(u["alt"].casefold() for u in units if u["alt"] and u["legende"] is None)
    return {"format": "EPUB", "visuels": len(units), "vecteurs": sum(u["vecteur"] for u in units),
            "legendes_num": sum(u["numerotee"] for u in units),
            "legendes": sum(u["legende"] is not None for u in units),
            "alt": sum(bool(u["alt"]) for u in units), "alt_utiles": sum(u["alt_etat"] == "utile" for u in units),
            "alt_inutiles": sum(reasons.values()), "raisons": dict(reasons),
            "alt_repetes": sum(1 for u in units
                               if u["alt"] and u["legende"] is None and repeated[u["alt"].casefold()] >= 3),
            "exploitables": sum(unit_retained(u) for u in units),
            "ornements": ornaments, "pages": None, "scannees": 0}


def _merge(rects: list) -> list:
    """Fusionne les rectangles qui se touchent (une image et son cadre, plusieurs tracés d'un même schéma)."""
    import pymupdf
    merged = [(pymupdf.Rect(r), kind) for r, kind in rects]
    changed = True
    while changed:
        changed = False
        for i in range(len(merged)):
            for j in range(i + 1, len(merged)):
                if (merged[i][0] + (-5, -5, 5, 5)).intersects(merged[j][0]):
                    kind = "image" if "image" in (merged[i][1], merged[j][1]) else "vecteur"
                    merged[i] = (merged[i][0] | merged[j][0], kind)
                    del merged[j]
                    changed = True
                    break
            if changed:
                break
    return merged


def pdf_visuals(page) -> tuple[list[dict], dict]:
    """Visuels d'une page de PDF (images d'au moins PDF_MIN_VISUAL_PT, zones vectorielles d'au moins PDF_MIN_VECTOR)
    avec, pour chacun, la légende numérotée la plus proche (bloc de texte court qui commence par « Figure X.Y », à
    moins de PDF_CAPTION_GAP_PT) : {rect, kind, caption}. Une page scannée (image pleine page sans texte) n'a pas de
    visuel. Renvoie aussi les compteurs {ornements, scannee, blocs_label}."""
    import pymupdf
    counters = {"ornements": 0, "scannee": False, "blocs_label": 0}
    area = page.rect.get_area()
    infos = page.get_image_info()
    if len(page.get_text("text").strip()) < 50 and any(pymupdf.Rect(i["bbox"]).get_area() >= 0.8 * area
                                                        for i in infos):
        counters["scannee"] = True   # une image pleine page sans texte n'est pas une figure
        return [], counters
    found = []
    for info in infos:
        rect = pymupdf.Rect(info["bbox"])
        if rect.get_area() >= 0.9 * area:
            continue   # fond de page
        if rect.width < PDF_MIN_VISUAL_PT or rect.height < PDF_MIN_VISUAL_PT:
            counters["ornements"] += 1
            continue
        found.append((rect, "image"))
    try:
        clusters = page.cluster_drawings()
    except Exception:  # un tracé que PyMuPDF ne sait pas regrouper ne doit pas arrêter le livre
        clusters = []
    found += [(r, "vecteur") for r in clusters
              if r.width >= PDF_MIN_VECTOR[0] and r.height >= PDF_MIN_VECTOR[1] and r.get_area() < 0.9 * area]
    candidates = []
    for block in page.get_text("blocks"):
        text = " ".join(str(block[4]).split())
        if block[6] == 0 and text and len(text) <= CAPTION_MAX and LABEL.match(text):
            candidates.append((pymupdf.Rect(block[:4]), text))
    counters["blocs_label"] = len(candidates)
    visuals = []
    for rect, kind in _merge(found):
        best, best_gap = None, None
        for index, (caption, _) in enumerate(candidates):
            gap = caption.y0 - rect.y1 if caption.y0 >= rect.y1 else (
                rect.y0 - caption.y1 if caption.y1 <= rect.y0 else 0)
            overlap = min(rect.x1, caption.x1) - max(rect.x0, caption.x0)
            if gap <= PDF_CAPTION_GAP_PT and overlap >= 0.2 * min(rect.width, caption.width) \
                    and (best_gap is None or gap < best_gap):
                best, best_gap = index, gap
        visuals.append({"rect": rect, "kind": kind,
                        "caption": candidates.pop(best)[1] if best is not None else None})
    return visuals, counters


def figure_stats_pdf(path: Path) -> dict:
    import pymupdf

    visuals_total = vectors = captioned = label_blocks = ornaments = scanned = 0
    with pymupdf.open(path) as doc:
        pages = doc.page_count
        for page in doc:
            visuals, counters = pdf_visuals(page)
            scanned += counters["scannee"]
            ornaments += counters["ornements"]
            label_blocks += counters["blocs_label"]
            visuals_total += len(visuals)
            vectors += sum(v["kind"] == "vecteur" for v in visuals)
            captioned += sum(v["caption"] is not None for v in visuals)
    return {"format": "PDF", "visuels": visuals_total, "vecteurs": vectors, "legendes_num": captioned,
            "legendes": captioned, "alt": 0, "alt_utiles": 0, "alt_inutiles": 0, "raisons": {}, "alt_repetes": 0,
            "exploitables": captioned, "ornements": ornaments, "pages": pages, "scannees": scanned,
            "blocs_label": label_blocks}


def _percent(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f} %" if whole else "—"


def figure_report(rows: list[dict], skipped_pdf: int, src: Path) -> str:
    """Tableau par livre, puis agrégat par format et total. L'agrégat ne contient aucun titre de livre.
    « Exploit. » = les blocs figure qu'une conversion créerait (EPUB : légende ou texte alternatif utile ;
    PDF : légende numérotée)."""
    detail = [f"Statistiques sur les figures · {time.strftime('%Y-%m-%d')} · {src}", "",
              "==== DÉTAIL PAR LIVRE ====", "",
              f"{'Livre':<46} {'Fmt':<4} {'Visuels':>7} {'dont vect.':>10} {'Légende n°':>10} {'Légende':>8} "
              f"{'Alt':>5} {'Alt inut.':>9} {'Exploit.':>8} {'Part':>6}  Notes"]
    for row in rows:
        name = row["livre"] if len(row["livre"]) <= 46 else row["livre"][:43] + "..."
        if row.get("erreur"):
            detail.append(f"{name:<46} {row['format']:<4} ERREUR : {row['erreur']}")
            continue
        notes = []
        if row["scannees"]:
            notes.append(f"{row['scannees']} page(s) scannée(s)")
        if row.get("repli"):
            notes.append("repli sur le PDF (EPUB en échec)")
        if row["ornements"]:
            notes.append(f"{row['ornements']} ornement(s) ignoré(s)")
        if row["alt_inutiles"] >= 10:
            notes.append("alt inutiles : " + ", ".join(
                f"{n} {r}" for r, n in sorted(row["raisons"].items(), key=lambda x: -x[1])))
        if row["alt_repetes"] >= 10:
            notes.append(f"{row['alt_repetes']} alt identiques répétés ≥ 3 fois")
        detail.append(f"{name:<46} {row['format']:<4} {row['visuels']:>7} {row['vecteurs']:>10} "
                      f"{row['legendes_num']:>10} {row['legendes']:>8} {row['alt']:>5} {row['alt_inutiles']:>9} "
                      f"{row['exploitables']:>8} {_percent(row['exploitables'], row['visuels']):>6}  "
                      f"{'; '.join(notes)}")
    aggregate = ["", "==== AGRÉGAT (cette partie seule peut être copiée : aucun titre de livre) ====", ""]
    ok_rows = [r for r in rows if not r.get("erreur")]
    for fmt in ("EPUB", "PDF"):
        part = [r for r in ok_rows if r["format"] == fmt]
        failed = sum(1 for r in rows if r.get("erreur") and r["format"] == fmt)
        if not part and not failed:
            continue
        with_visuals = [r for r in part if r["visuels"]]
        shares = [100 * r["exploitables"] / r["visuels"] for r in with_visuals]
        bands = [("0 %", lambda x: x == 0), ("1 à 24 %", lambda x: 0 < x < 25), ("25 à 49 %", lambda x: 25 <= x < 50),
                 ("50 à 74 %", lambda x: 50 <= x < 75), ("75 % et plus", lambda x: x >= 75)]
        total = lambda key: sum(r[key] for r in part)  # noqa: E731
        reasons = Counter()
        for r in part:
            reasons.update(r["raisons"])
        aggregate += [
            f"-- {fmt} --",
            f"Livres analysés : {len(part)} (en erreur : {failed})",
            f"Livres sans aucun visuel : {len(part) - len(with_visuals)}",
            f"Livres avec au moins 1 légende numérotée : {sum(1 for r in part if r['legendes_num'] >= 1)}",
            f"Livres avec au moins 10 légendes numérotées : {sum(1 for r in part if r['legendes_num'] >= 10)}",
            f"Visuels : {total('visuels')} (dont vectoriels : {total('vecteurs')}) · ornements ignorés : "
            f"{total('ornements')}",
            f"Légendes numérotées : {total('legendes_num')} · légendes de toute forme : {total('legendes')}",
        ]
        if fmt == "EPUB":
            detail_reasons = " · ".join(f"{r} : {reasons[r]}" for r in ALT_REASONS)
            aggregate += [
                f"Textes alternatifs non vides : {total('alt')} · utiles : {total('alt_utiles')} · inutiles : "
                f"{total('alt_inutiles')} ({detail_reasons}) · seuil : {MIN_ALT_WORDS} mots sans légende",
                f"Textes alternatifs identiques répétés au moins 3 fois, sans légende (information, non filtrés) : "
                f"{total('alt_repetes')} visuels dans {sum(1 for r in part if r['alt_repetes'])} livre(s)",
            ]
        aggregate += [
            f"Blocs figure qui seraient créés (légende ou texte alternatif utile ; PDF : légende numérotée) : "
            f"{total('exploitables')} ({_percent(total('exploitables'), total('visuels'))} des visuels)",
            f"Visuels écartés (ni légende ni texte alternatif utile) : {total('visuels') - total('exploitables')}",
            f"Part retenue par livre (livres avec visuels) : médiane {statistics.median(shares):.0f} %" if shares
            else "Part retenue par livre : aucun livre avec visuels",
        ]
        if shares:
            aggregate.append("Répartition des livres par part retenue : "
                             + " · ".join(f"{label} : {sum(1 for x in shares if test(x))}" for label, test in bands))
        if fmt == "PDF":
            aggregate.append(f"Pages scannées (image pleine page sans texte, non comptées) : {total('scannees')} "
                             f"dans {sum(1 for r in part if r['scannees'])} livre(s)")
        aggregate.append("")
    visuals = sum(r["visuels"] for r in ok_rows)
    usable = sum(r["exploitables"] for r in ok_rows)
    aggregate += [
        "-- TOTAL (EPUB + PDF) --",
        f"Livres analysés : {len(ok_rows)} · avec au moins 1 légende numérotée : "
        f"{sum(1 for r in ok_rows if r['legendes_num'] >= 1)} · sans aucun visuel : "
        f"{sum(1 for r in ok_rows if not r['visuels'])}",
        f"Visuels : {visuals} · blocs figure qui seraient créés : {usable} ({_percent(usable, visuals)})",
        f"Visuels écartés (candidats d'un éventuel niveau 2) : {visuals - usable}",
        f"PDF ignorés car l'EPUB existe : {skipped_pdf}",
        "",
        "Lecture : EPUB, un visuel est une <figure> ou une image ou un svg isolé (ornements déclarés de moins de "
        f"{ORNAMENT_PX} px et pages de couverture exclus) ; il est retenu s'il a une légende de toute forme ou un "
        "texte alternatif utile (ni vide, ni nom de fichier, ni mot générique, ni moins de "
        f"{MIN_ALT_WORDS} mots sans légende). PDF, un visuel est une image d'au moins {PDF_MIN_VISUAL_PT} pt ou une "
        f"zone vectorielle d'au moins {PDF_MIN_VECTOR[0]} × {PDF_MIN_VECTOR[1]} pt (peut inclure des tableaux "
        "encadrés) ; il n'est retenu que s'il a une légende numérotée (bloc court qui commence par « Figure X.Y ») "
        f"à moins de {PDF_CAPTION_GAP_PT} pt.",
    ]
    return "\n".join(detail + aggregate) + "\n"


def figures_a_refaire(rows: list[dict]) -> str:
    """Liste pour --redo-figures : un livre source par ligne s'il a au moins une figure retenue (celles que la
    conversion créerait), chemin relatif au dossier des livres, nombre de figures en commentaire de fin de ligne."""
    kept = [r for r in rows if not r.get("erreur") and r.get("exploitables", 0) >= 1]
    lines = [f"# Livres ayant au moins une figure retenue · {time.strftime('%Y-%m-%d')} · écrit par "
             "convert_books.py --figure-statistics",
             "# Un livre par ligne ; tout ce qui suit un « # » précédé d'un espace est ignoré par --redo-figures."]
    lines += [f"{r['chemin']}  # {r['exploitables']} figure{'s' if r['exploitables'] > 1 else ''}" for r in kept]
    return "\n".join(lines) + "\n"


def figure_statistics(argv: list[str]) -> None:
    if len(argv) not in (1, 2):
        print(__doc__)
        sys.exit(1)
    src = Path(argv[0]).expanduser().resolve()
    dst = (Path(argv[1]).expanduser() if len(argv) == 2 else WORKSPACE / "Bibliotheque-MD").resolve()
    if not src.is_dir():
        sys.exit(f"Not a folder: {src}")
    books = sorted(p for p in src.rglob("*") if p.suffix.lower() in (".pdf", ".epub"))
    pdf_by_stem = {p.with_suffix("").as_posix().lower(): p for p in books if p.suffix.lower() == ".pdf"}
    epub_stems = {p.with_suffix("").as_posix().lower() for p in books if p.suffix.lower() == ".epub"}
    rows = []
    for number, book in enumerate(books, 1):
        key = book.with_suffix("").as_posix().lower()
        is_pdf = book.suffix.lower() == ".pdf"
        if is_pdf and key in epub_stems:
            continue   # l'EPUB est préféré, comme à la conversion
        print(f"[{number}/{len(books)}] {book.name}", file=sys.stderr, flush=True)
        name = book.relative_to(src).with_suffix("").as_posix()
        try:
            row = figure_stats_pdf(book) if is_pdf else figure_stats_epub(book)
            rows.append({"livre": name, "chemin": book.relative_to(src).as_posix(), **row})
        except Exception as error:
            twin = pdf_by_stem.get(key) if not is_pdf else None
            if twin is None:
                rows.append({"livre": name, "format": "PDF" if is_pdf else "EPUB", "erreur": str(error)[:80]})
                continue
            try:   # même repli que la conversion : le PDF du même livre remplace l'EPUB en échec
                rows.append({"livre": name, "chemin": book.relative_to(src).as_posix(),
                             **figure_stats_pdf(twin), "repli": True})
            except Exception as pdf_error:
                rows.append({"livre": name, "format": "EPUB",
                             "erreur": f"{str(error)[:40]} ; PDF : {str(pdf_error)[:30]}"})
    skipped_pdf = sum(1 for b in books if b.suffix.lower() == ".pdf"
                      and b.with_suffix("").as_posix().lower() in epub_stems) \
        - sum(1 for r in rows if r.get("repli"))   # un PDF qui remplace un EPUB en échec n'est pas « ignoré »
    report = figure_report(rows, skipped_pdf, src)
    print(report, end="")
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "_statistiques_figures.txt").write_text(report, encoding="utf-8")
    print(f"\nRapport écrit : {dst / '_statistiques_figures.txt'}", file=sys.stderr)
    LISTE_A_REFAIRE.parent.mkdir(parents=True, exist_ok=True)
    LISTE_A_REFAIRE.write_text(figures_a_refaire(rows), encoding="utf-8")
    print(f"Liste des livres à refaire : {LISTE_A_REFAIRE}", file=sys.stderr)


def convert_with_fallback(book: Path, pdf_by_stem: dict[str, Path], images_root: Path | None) -> dict:
    """Convertit un livre ; si l'EPUB échoue, essaie le PDF du même livre. Renvoie un dictionnaire :
    md, warning, sink (blocs et images), fallback (le PDF utilisé), epub_error ; ou error (et pdf_error si le PDF
    a échoué à son tour). Les images d'une conversion en échec sont retirées."""
    is_epub = book.suffix.lower() == ".epub"
    sink = ImageSink(images_root, book.stem)
    try:
        md, warning = (convert_epub if is_epub else convert_pdf)(book, images=sink)
        return {"md": md, "warning": warning, "sink": sink, "fallback": None}
    except Exception as error:  # on continue même si un livre pose problème
        sink.discard()
        twin = pdf_by_stem.get(book.with_suffix("").as_posix().lower()) if is_epub else None
        if twin is None:
            return {"error": str(error), "fallback": None}
        sink = ImageSink(images_root, twin.stem)
        try:
            md, warning = convert_pdf(twin, images=sink)
        except Exception as pdf_error:  # les deux formats échouent : le livre n'est converti dans aucun
            sink.discard()
            return {"error": str(error), "pdf_error": str(pdf_error), "fallback": twin}
        return {"md": md, "warning": warning, "sink": sink, "fallback": twin, "epub_error": str(error)}


def _normal(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold().strip().strip("/")


def norm_path(text: str) -> str:
    return unicodedata.normalize("NFC", text)


SOURCE_HEADER = re.compile(r'^source:\s*"(.*)"\s*$')


def markdown_source(markdown: Path) -> str | None:
    """Nom de la source déclaré dans l'en-tête d'un Markdown converti (`source: "livre.epub"`), sinon None.
    Seules les premières lignes sont lues."""
    try:
        with markdown.open(encoding="utf-8", errors="replace") as handle:
            for number, line in enumerate(handle):
                if number >= 12:
                    break
                found = SOURCE_HEADER.match(line.strip())
                if found:
                    return found.group(1)
    except OSError:
        pass
    return None


def resolve_markdown(targets: list[Path], src: Path, dst: Path, mapping: dict | None = None,
                     sources: dict | None = None) -> tuple[dict[Path, tuple[Path, str]], list[str], list[Path]]:
    """Markdown existant de chaque livre à convertir (--redo-figures ou conversion normale). Renvoie
    (livre -> (Markdown, voie), erreurs, livres sans aucun Markdown) ; toutes les erreurs sont rassemblées, rien n'est
    écrit. Un livre sans aucun Markdown n'est pas une erreur ici : l'appelant décide (--redo-figures s'arrête,
    la conversion normale le liste).

    0. Par la correspondance explicite SOURCES (mapping_lab.py) : le livre y est désigné par son chemin relatif ;
       son Markdown doit exister sous le dossier de sortie, sinon erreur. Pas de repli sur 1 et 2.
    1. Par le nom de fichier (livre.md), n'importe où dans le dossier de sortie, car les dossiers de la source ont
       pu être renommés. Les dossiers et fichiers dont le nom commence par « _ » sont ignorés. Plusieurs Markdown
       du même nom : erreur.
    2. Sinon par MAPPING (mapping_lab.py) : les clés dont le premier dossier est le dossier de sortie, leur chemin
       relatif à lui. Une clé correspond au livre si son nom de fichier, sans casse ni accents, est celui du livre,
       ou si le Markdown qu'elle désigne déclare le livre dans son en-tête (`source:`). Une clé qui correspond mais
       dont le fichier n'existe pas : erreur ; zéro ou plusieurs correspondances : erreur.
    Deux livres vers le même Markdown : erreur."""
    mapping = MAPPING if mapping is None else mapping
    explicit = {_normal(norm_path(k)): v for k, v in (SOURCES if sources is None else sources).items()}
    by_name: dict[str, list[Path]] = {}
    by_path: dict[str, Path] = {}
    for markdown in dst.rglob("*.md"):
        relative = markdown.relative_to(dst)
        if any(part.startswith("_") for part in relative.parts):
            continue
        by_name.setdefault(_normal(markdown.name), []).append(markdown)
        by_path[_normal(relative.as_posix())] = markdown
    entries: list[tuple[str, Path | None]] = []   # (clé de MAPPING, Markdown existant ou None)
    for key in mapping:
        parts = norm_path(key).split("/", 1)
        if len(parts) == 2 and _normal(parts[0]) == _normal(dst.name):
            entries.append((key, by_path.get(_normal(parts[1]))))
    declared: dict[Path, str | None] = {}

    def source_of(markdown: Path) -> str | None:
        if markdown not in declared:
            declared[markdown] = markdown_source(markdown)
        return declared[markdown]

    located: dict[Path, tuple[Path, str]] = {}
    problems: list[str] = []
    missing: list[Path] = []
    for book in targets:
        label = book.relative_to(src)
        target = explicit.get(_normal(norm_path(label.as_posix())))
        if target is not None:
            parts = norm_path(target).split("/", 1)
            existing = by_path.get(_normal(parts[1])) if len(parts) == 2 and _normal(parts[0]) == _normal(dst.name) else None
            if existing is None:
                problems.append(f"correspondance explicite vers un Markdown absent pour {label} : {target} "
                                f"(dans {dst})")
            else:
                located[book] = (existing, f"correspondance explicite, {target}")
            continue
        found = sorted(by_name.get(_normal(book.with_suffix(".md").name), []))
        if len(found) == 1:
            located[book] = (found[0], "nom")
            continue
        if len(found) > 1:
            problems.append(f"plusieurs Markdown pour {label} :\n      "
                            + "\n      ".join(str(f.relative_to(dst)) for f in found))
            continue
        stem = fold(book.stem)
        matches: dict[Path, str] = {}
        absent: list[str] = []
        for key, existing in entries:
            same_name = fold(Path(key).stem) == stem
            if existing is None:
                if same_name:
                    absent.append(key)
                continue
            declared_name = source_of(existing)
            if same_name or (declared_name is not None and fold(Path(declared_name).stem) == stem):
                matches.setdefault(existing, key)
        if absent:
            problems.append(f"clé de MAPPING vers un fichier absent pour {label} : " + " ; ".join(absent))
        elif len(matches) > 1:
            problems.append(f"plusieurs clés de MAPPING pour {label} :\n      "
                            + "\n      ".join(f"{key} -> {m.relative_to(dst)}" for m, key in sorted(matches.items())))
        elif matches:
            (markdown, key), = matches.items()
            located[book] = (markdown, f"MAPPING, clé « {key} »")
        else:
            missing.append(book)
    by_markdown: dict[Path, list[Path]] = {}
    for book, (markdown, _) in located.items():
        by_markdown.setdefault(markdown, []).append(book)
    for markdown, books in sorted(by_markdown.items()):
        if len(books) > 1:
            problems.append(f"deux livres vers le même Markdown {markdown.relative_to(dst)} : "
                            + " ; ".join(str(b.relative_to(src)) for b in books))
    return located, problems, missing


def split_excluded(books: list[Path], src: Path, exclusions: dict | None = None) -> tuple[list[Path], list[tuple[Path, str]]]:
    """(livres à convertir, [(livre exclu, raison)]) : EXCLUSIONS (mapping_lab.py), comparées sans casse, en NFC."""
    table = {_normal(norm_path(k)): v for k, v in (EXCLUSIONS if exclusions is None else exclusions).items()}
    kept: list[Path] = []
    excluded: list[tuple[Path, str]] = []
    for book in books:
        reason = table.get(_normal(norm_path(book.relative_to(src).as_posix())))
        if reason is None:
            kept.append(book)
        else:
            excluded.append((book, reason))
    return kept, excluded


def excluded_messages(chosen: list[Path], src: Path) -> list[str]:
    return [f"livre exclu de la conversion : {book.relative_to(src)} ({reason})"
            for book, reason in split_excluded(chosen, src)[1]]


def missing_message(book: Path, src: Path, dst: Path) -> str:
    return (f"Markdown introuvable : {book.relative_to(src)} (aucun « {book.stem}.md » dans {dst}, "
            "aucune clé de MAPPING ne correspond)")


def locate_markdown(targets: list[Path], src: Path, dst: Path) -> dict[Path, tuple[Path, str]]:
    """resolve_markdown, avec arrêt (avant toute conversion) à la moindre erreur : toutes sont listées."""
    located, problems, missing = resolve_markdown(targets, src, dst)
    problems = problems + [missing_message(book, src, dst) for book in missing]
    if problems:
        sys.exit("--redo-figures : rien n'a été converti.\n  " + "\n  ".join(problems)
                 + "\n  Corrige la correspondance (un seul Markdown et une seule clé de MAPPING par livre) puis relance.")
    return located


def choose_books(names: list[str], books: list[Path], src: Path) -> tuple[list[Path], list[str]]:
    """Livres désignés par --redo-figures : chemin relatif au dossier des livres, avec ou sans extension, ou
    simple nom de fichier ; « @liste.txt » pour une liste (un livre par ligne, ligne en # = commentaire, et tout ce
    qui suit un « # » précédé d'un espace est ignoré). Un livre qui existe en EPUB et en PDF est désigné par son
    EPUB. Renvoie (livres, erreurs) : un nom introuvable ou ambigu est une erreur."""
    def normal(text: str) -> str:
        return unicodedata.normalize("NFC", text).casefold().strip().strip("/")

    entries: list[str] = []
    for name in names:
        if name.startswith("@"):
            lines = Path(name[1:]).expanduser().read_text(encoding="utf-8").splitlines()
            entries += [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
        else:
            entries.append(name)
    entries = [entry for entry in (re.sub(r"\s+#.*$", "", entry).strip() for entry in entries) if entry]
    preferred: dict[str, Path] = {}
    for book in books:   # un EPUB l'emporte sur le PDF du même nom
        key = normal(book.relative_to(src).with_suffix("").as_posix())
        if key not in preferred or book.suffix.lower() == ".epub":
            preferred[key] = book
    chosen: list[Path] = []
    problems: list[str] = []
    for entry in entries:
        wanted = normal(re.sub(r"\.(?:epub|pdf|md)$", "", entry.strip(), flags=re.IGNORECASE))
        matches = [book for key, book in preferred.items() if key == wanted or key.endswith("/" + wanted)]
        if not matches:
            problems.append(f"introuvable : {entry}")
        elif len(matches) > 1:
            problems.append(f"ambigu : {entry} (" + ", ".join(str(m.relative_to(src)) for m in matches) + ")")
        elif matches[0] not in chosen:
            chosen.append(matches[0])
    return chosen, problems


def preferred_books(books: list[Path], src: Path) -> list[Path]:
    """Un livre par titre : l'EPUB l'emporte sur le PDF du même chemin (hors extension). Le PDF n'est converti que si
    l'EPUB échoue (repli de convert_with_fallback)."""
    best: dict[str, Path] = {}
    for book in books:
        key = _normal(book.relative_to(src).with_suffix("").as_posix())
        if key not in best or book.suffix.lower() == ".epub":
            best[key] = book
    return sorted(best.values())


def select_books(names: list[str], books: list[Path], src: Path) -> list[Path]:
    """choose_books, avec arrêt avant toute conversion à la moindre erreur."""
    chosen, problems = choose_books(names, books, src)
    if problems:
        sys.exit("--redo-figures : rien n'a été converti.\n  " + "\n  ".join(problems))
    return chosen


def simulate(names: list[str] | None, books: list[Path], src: Path, dst: Path) -> None:
    """--dry-run : résout chaque livre (source -> Markdown, voie) et affiche toutes les erreurs. Ne convertit rien,
    n'écrit rien, n'ouvre aucun livre. `names` : les livres de --redo-figures ; None : la conversion normale, où
    un livre sans Markdown existant est listé (non converti) et non une erreur. Sortie 1 s'il y a une erreur."""
    excluded: list[tuple[Path, str]] = []
    if names is None:
        chosen, excluded = split_excluded(preferred_books(books, src), src)
        problems: list[str] = []
    else:
        chosen, problems = choose_books(names, books, src)
        problems += excluded_messages(chosen, src)
    located, resolution, missing = resolve_markdown(chosen, src, dst)
    problems += resolution
    if names is not None:
        problems += [missing_message(book, src, dst) for book in missing]
    kind = "--redo-figures" if names is not None else "conversion normale"
    print(f"--dry-run ({kind}) : {len(chosen)} livre(s) ; rien n'est converti, rien n'est écrit, aucune image.\n")
    for book in chosen:
        if book in located:
            markdown, route = located[book]
            print(f"  {book.relative_to(src)} -> {markdown.relative_to(dst)}  (voie : {route})")
    if names is None and missing:
        print(f"\nSans Markdown existant, non convertis ({len(missing)}), à traiter avec --convert-book :")
        for book in missing:
            print(f"  {book.relative_to(src)}")
    if excluded:
        print(f"\nExclus de la conversion normale ({len(excluded)}) :")
        for book, reason in excluded:
            print(f"  {book.relative_to(src)} : {reason}")
    if problems:
        print(f"\nErreurs de correspondance ({len(problems)}) :")
        for problem in problems:
            print(f"  {problem}")
    by_route = Counter(route.split(",")[0] for _, route in located.values())
    print(f"\nRésolus : {len(located)} (par correspondance explicite : {by_route['correspondance explicite']}, "
          f"par nom : {by_route['nom']}, par MAPPING : {by_route['MAPPING']})"
          + (f" · sans Markdown : {len(missing)} · exclus : {len(excluded)}" if names is None else "")
          + f" · erreurs : {len(problems)}")
    if problems:
        sys.exit(1)


def convert_one(argv: list[str]) -> None:
    """--convert-book <livre> --to <Markdown> : convertit ce seul livre, jamais converti, et écrit son Markdown
    au chemin donné (relatif au dossier de sortie). Tout est vérifié avant la conversion ; rien n'est écrasé."""
    options: dict[str, str] = {}
    rest = list(argv)
    for flag in ("--convert-book", "--to"):
        if flag not in rest or rest.index(flag) + 1 >= len(rest):
            sys.exit("--convert-book demande un livre et --to un chemin de Markdown.")
        position = rest.index(flag)
        options[flag] = rest[position + 1]
        del rest[position:position + 2]
    if len(rest) != 2:
        print(__doc__)
        sys.exit(1)
    src, dst = Path(rest[0]).expanduser().resolve(), Path(rest[1]).expanduser().resolve()
    if not src.is_dir():
        sys.exit(f"Not a folder: {src}")
    if not dst.is_dir():
        sys.exit(f"--convert-book : dossier de sortie introuvable : {dst}")
    books = sorted(p for p in src.rglob("*") if p.suffix.lower() in (".pdf", ".epub"))
    chosen, problems = choose_books([options["--convert-book"]], books, src)
    vers = norm_path(options["--to"]).strip().strip("/")
    parts = vers.split("/")
    if not vers.lower().endswith(".md") or any(part in ("", ".", "..") for part in parts) or vers.startswith("_"):
        problems.append(f"--to : chemin de Markdown invalide : {options['--to']} (relatif au dossier de sortie, "
                        "se terminant par .md, sans « .. »)")
    else:
        out = dst / vers
        if out.exists():
            problems.append(f"le Markdown existe déjà : {vers} (rien n'est écrasé ; pour refaire un livre déjà "
                            "converti, utilise --redo-figures)")
        same_name = [m for m in dst.rglob("*.md") if _normal(m.name) == _normal(parts[-1])
                     and not any(part.startswith("_") for part in m.relative_to(dst).parts)]
        if same_name:
            problems.append(f"un autre Markdown porte déjà ce nom de fichier : {same_name[0].relative_to(dst)}")
        if _normal(f"{dst.name}/{vers}") not in {_normal(norm_path(k)) for k in MAPPING}:
            problems.append(f"{dst.name}/{vers} n'est pas une clé de MAPPING (mapping_lab.py) : ajoute-la d'abord, "
                            "pour que sort_by_domain.py copie le livre")
    if problems:
        sys.exit("--convert-book : rien n'a été converti.\n  " + "\n  ".join(problems))
    book = chosen[0]
    pdf_by_stem = {p.with_suffix("").as_posix().lower(): p for p in books if p.suffix.lower() == ".pdf"}
    print(f"{book.relative_to(src)} -> {vers}")
    result = convert_with_fallback(book, pdf_by_stem, IMAGES_DIR)
    if "error" in result:
        sys.exit(f"--convert-book : conversion en échec, rien n'a été écrit : {result['error']}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result["md"], encoding="utf-8")
    sink = result["sink"]
    report = [f"Livre converti : {book.relative_to(src)} -> {vers}",
              f"Blocs figure créés : {sink.count} (images extraites : {sink.saved}, dans {IMAGES_NAME}/)",
              *([f"Repli sur le PDF (EPUB en échec) : {result['fallback'].name}"] if result["fallback"] else []),
              *([f"À vérifier : {result['warning']}"] if result["warning"] else [])]
    (dst / "_rapport_livre.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print("\nÀ faire ensuite : sort_by_domain.py (copie dans Bibliotheque-Lab), l'entrée du catalogue puis l'indexation.")


OPTIONS_RENOMMEES = {"--convertir-livre": "--convert-book", "--refaire-figures": "--redo-figures", "--simuler": "--dry-run",
                     "--statistiques-figures": "--figure-statistics", "--vers": "--to"}


def main() -> None:
    import flux_config
    sys.argv[1:] = flux_config.refuse_old_options(sys.argv[1:], OPTIONS_RENOMMEES)
    if sys.argv[1:2] == ["--figure-statistics"]:
        figure_statistics(sys.argv[2:])
        return
    if "--convert-book" in sys.argv[1:]:
        convert_one(sys.argv[1:])
        return
    argv = sys.argv[1:]
    simuler = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]
    refaire: list[str] | None = None
    if "--redo-figures" in argv:
        position = argv.index("--redo-figures")
        refaire, argv = argv[position + 1:], argv[:position]
        if not refaire:
            sys.exit("--redo-figures demande au moins un livre (ou @liste.txt).")
    if len(argv) != 2:
        print(__doc__)
        sys.exit(1)
    src = Path(argv[0]).expanduser().resolve()
    dst = Path(argv[1]).expanduser().resolve()
    if not src.is_dir():
        sys.exit(f"Not a folder: {src}")
    if simuler:
        if not dst.is_dir():
            sys.exit(f"--dry-run : dossier de sortie introuvable : {dst}")
    else:
        dst.mkdir(parents=True, exist_ok=True)

    books = sorted(p for p in src.rglob("*") if p.suffix.lower() in (".pdf", ".epub"))
    epub_stems = {p.with_suffix("").as_posix().lower() for p in books if p.suffix.lower() == ".epub"}
    if simuler:
        simulate(refaire, books, src, dst)
        return
    excluded: list[tuple[Path, str]] = []
    if refaire is not None:
        targets = select_books(refaire, books, src)
        if excluded_messages(targets, src):
            sys.exit("--redo-figures : rien n'a été converti.\n  " + "\n  ".join(excluded_messages(targets, src)))
        located = locate_markdown(targets, src, dst)
        missing: list[Path] = []
    else:   # conversion normale : le Markdown existant de chaque livre, par la même recherche, réécrit sur place
        targets, excluded = split_excluded(preferred_books(books, src), src)
        located, problems, missing = resolve_markdown(targets, src, dst)
        if problems:
            sys.exit("conversion normale : rien n'a été converti.\n  " + "\n  ".join(problems)
                     + "\n  Corrige la correspondance (un seul Markdown et une seule clé de MAPPING par livre) puis relance.")
    print(f"{len(books)} livres trouvés dans {src} "
          f"({sum(p.suffix.lower() == '.pdf' for p in books)} PDF, {len(epub_stems)} EPUB)\n")
    print(f"{'--redo-figures' if refaire is not None else 'Conversion normale'} : {len(located)} livre(s) à "
          f"reconvertir sur place ; l'ancien Markdown est gardé en « .md.avant-figures » (une seule fois)")
    for book in targets:
        if book in located:
            print(f"  {book.relative_to(src)} -> {located[book][0].relative_to(dst)}  (voie : {located[book][1]})")
    if missing:
        print(f"\nSans Markdown existant, non convertis ({len(missing)}), à traiter avec --convert-book :")
        for book in missing:
            print(f"  {book.relative_to(src)}")
    if excluded:
        print(f"\nExclus de la conversion normale ({len(excluded)}) :")
        for book, reason in excluded:
            print(f"  {book.relative_to(src)} : {reason}")
    print()

    pdf_by_stem = {p.with_suffix("").as_posix().lower(): p for p in books if p.suffix.lower() == ".pdf"}
    converted = blocks = images = 0
    fallbacks, used_pdfs, suspects, errors, per_book, backups = [], set(), [], [], [], []
    kept_backups: list[str] = []
    start = time.time()

    todo = [book for book in targets if book in located]
    for i, book in enumerate(todo, 1):
        rel = book.relative_to(src)
        out = located[book][0]
        print(f"[{i}/{len(todo)}] {book.name}")
        result = convert_with_fallback(book, pdf_by_stem, IMAGES_DIR)
        if "error" in result:
            if result["fallback"] is None:
                errors.append(f"{rel} : {result['error']}")
                print(f"   ERREUR : {result['error']}")
            else:
                errors.append(f"{rel} : {result['error']}")
                errors.append(f"{result['fallback'].relative_to(src)} : {result['pdf_error']} "
                              f"(repli après l'échec de l'EPUB)")
                print(f"   ERREUR : {result['error']} ; repli sur {result['fallback'].name}")
                print(f"   ERREUR : {result['pdf_error']}")
            continue
        if result["fallback"] is not None:
            print(f"   ERREUR : {result['epub_error']} ; repli sur {result['fallback'].name}")
        backup = out.with_name(out.name + ".avant-figures")   # la copie d'avant n'est faite qu'une fois, avant d'écraser
        if backup.exists():
            kept_backups.append(str(out.relative_to(dst)))
        else:
            shutil.copy2(out, backup)
            backups.append(str(out.relative_to(dst)))
        out.write_text(result["md"], encoding="utf-8")
        converted += 1
        sink = result["sink"]
        blocks += sink.count
        images += sink.saved
        per_book.append(f"{rel} : {sink.count} bloc(s) figure, {sink.saved} image(s) -> {out.relative_to(dst)} "
                        f"(voie : {located[book][1]})")
        if result["fallback"] is not None:
            used_pdfs.add(result["fallback"])
            fallbacks.append(f"{rel} : EPUB en échec ({result['epub_error']}) ; converti depuis "
                             f"{result['fallback'].name}")
            if result["warning"]:
                suspects.append(f"{result['fallback'].relative_to(src)} : {result['warning']}")
        elif result["warning"]:
            suspects.append(f"{rel} : {result['warning']}")

    doubles = [str(p.relative_to(src)) for p in books if p.suffix.lower() == ".pdf"
               and p.with_suffix("").as_posix().lower() in epub_stems and p not in used_pdfs]
    report = [
        f"{'Refaits (figures)' if refaire is not None else 'Convertis'} : {converted}",
        f"Anciennes versions gardées (.md.avant-figures) : {len(backups) + len(kept_backups)} "
        f"(créées maintenant : {len(backups)}, déjà là d'un passage précédent : {len(kept_backups)})",
        *([] if refaire is not None else [f"Sans Markdown existant (non convertis) : {len(missing)}",
                                          f"Exclus (EXCLUSIONS) : {len(excluded)}",
                                          f"PDF ignorés car l'EPUB existe : {len(doubles)}"]),
        f"Repli sur le PDF (EPUB en échec) : {len(fallbacks)}",
        f"Erreurs : {len(errors)}",
        f"À vérifier : {len(suspects)}",
        f"Blocs figure créés : {blocks} (images extraites : {images}, dans {IMAGES_NAME}/)",
        f"Durée : {(time.time() - start) / 60:.1f} min",
        "",
        "== À vérifier (PDF scannés, EPUB vides) ==",
        *suspects,
        "",
        *([] if refaire is not None else ["== Sans Markdown existant (à traiter avec --convert-book) ==",
                                          *(str(b.relative_to(src)) for b in missing), "",
                                          "== Exclus (source : raison) ==",
                                          *(f"{b.relative_to(src)} : {r}" for b, r in excluded), "",
                                          "== PDF ignorés car l'EPUB existe ==", *doubles, ""]),
        "== Repli sur le PDF (l'EPUB n'a pas pu être converti) ==",
        *fallbacks,
        "",
        "== Figures par livre ==",
        *per_book,
        "",
        "== Erreurs ==",
        *errors,
    ]
    report_name = "_rapport_figures.txt" if refaire is not None else "_rapport_conversion.txt"
    (dst / report_name).write_text("\n".join(report), encoding="utf-8")
    print("\n" + "\n".join(report[:10 if refaire is None else 8]))
    if converted:
        print("\nÀ faire ensuite : relancer sort_by_domain.py (copie dans Bibliotheque-Lab) puis l'indexation.")
    print(f"\nRapport complet : {dst / report_name}")


if __name__ == "__main__":
    main()
