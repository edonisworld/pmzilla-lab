# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PMZilla Lab : matière du miroir de Critic.

Relit les livrables de _bmad-output/pmzilla/ (diagnostics, cadrages, synthèses de veille, messages…)
et en extrait, telles quelles, les sections où Critic conteste. Le script ne classe rien : il donne
à /critic-mirror un corpus fiable (fichier, date, posture, objections numérotées) et le nombre
exact d'objections, que le classement doit retrouver.

    uv run critic_mirror.py [--since AAAA-MM-JJ] [--until AAAA-MM-JJ] [--language fr|en]
        Par défaut, le mois précédent si l'on est en début de mois (avant le 8), sinon le mois en cours.

    uv run critic_mirror.py --categories [--language fr|en]
        Affiche la grille de classement des objections (11 catégories, tableau Markdown) et s'arrête : c'est la seule
        source de la grille, la commande /critic-mirror ne la recopie pas.

--language fr|en : langue de la sortie (français par défaut). La reconnaissance des sections de Critic ne dépend pas
de cette option : toutes les langues du vocabulaire sont reconnues.

Les rapports du jeu d'essai (_bmad-output/essais/) et les miroirs eux-mêmes sont ignorés.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flux_config
from critic_mirror_messages import CATALOGS
from messages import Messages, add_language_option

OPTIONS_RENOMMEES = {**flux_config.OPTIONS_COMMUNES, "--depuis": "--since", "--jusqu": "--until"}

WORKSPACE = Path(os.environ.get("PMZILLA_LAB_WORKSPACE", "~/PMZilla-Lab/workspace")).expanduser()
OUTPUT_DIR = WORKSPACE / "_bmad-output" / "pmzilla"
IGNORED = ("miroir",)

# début d'une section Critic : tout titre Markdown qui nomme Critic (« ## 8. Revue de Critic »,
# « ## Ce que Critic conteste »), ou une ligne courte seule qui l'annonce (format des messages)
START_HEADING = re.compile(r"^#{1,6}\s.*\bCritic\b", re.IGNORECASE)
# Les formules viennent du vocabulaire des postures (tests/postures/vocabulaire.yaml), le même que celui du jeu d'essai :
# toutes les langues sont reconnues, un livrable pouvant être écrit dans l'une ou l'autre.
VOCABULARY_FILE = Path(__file__).resolve().parents[1] / "tests" / "postures" / "vocabulaire.yaml"


def load_vocabulary(path: Path | None = None) -> dict[str, dict]:
    """Les langues du vocabulaire (les clés communes aux langues, comme `posture_names`, ne sont pas des langues)."""
    data = yaml.safe_load((path or VOCABULARY_FILE).read_text(encoding="utf-8")) or {}
    return {lang: values for lang, values in data.items() if isinstance(values, dict)}


def build_patterns(vocabulary: dict[str, dict]) -> tuple[re.Pattern, re.Pattern, re.Pattern]:
    """(début d'une section de Critic en ligne simple, fin d'une telle section, balise de posture) pour toutes les
    langues du vocabulaire (le français d'abord)."""
    languages = sorted(vocabulary, key=lambda lang: (lang != "fr", lang))
    starts = [alt for lang in languages for alt in vocabulary[lang]["critic_plain_start"]]
    ends = [alt for lang in languages for alt in vocabulary[lang]["critic_plain_end"]]
    prefixes = []
    for lang in languages:
        prefix = vocabulary[lang]["posture_tag"].split("{posture}")[0]
        # les espaces du format deviennent \s* : la balise est reconnue avec ou sans espace avant les deux-points
        pattern = re.sub(r"(\\ )+", r"\\s*", re.escape(prefix))
        if pattern not in prefixes:
            prefixes.append(pattern)
    return (re.compile(r"^(" + "|".join(starts) + r")\b.{0,40}$", re.IGNORECASE),
            re.compile(r"^(" + "|".join(ends) + r")\b", re.IGNORECASE),
            re.compile("(?:" + "|".join(prefixes) + r")([A-Za-zÀ-ÿ]+)"))


# début d'une section écrite en ligne simple, fin d'une telle section (pas de titre Markdown), balise de posture
START_PLAIN, PLAIN_END, POSTURE = build_patterns(load_vocabulary())
ITEM = re.compile(r"^(\d+[.)]|[-*])\s+")
# posture écrite en métadonnée, en tête de livrable : « - **Posture :** Scaling » (typographie française, espace
# avant les deux-points) ou « - **Posture:** Scaling » (anglaise) ; puces, gras, italique et deux-points dans ou
# hors du gras acceptés. Seules les lignes avant le premier titre « ## » sont lues.
META_POSTURE = re.compile(r"^\s*(?:[-*+]\s+)?[*_]{0,2}Posture[*_]{0,2}\s*:\s*[*_]{0,2}\s*(.+)$", re.IGNORECASE)
KNOWN_POSTURES = ("Discovery", "Delivery", "Scaling", "Facilitation")   # Critic n'est jamais la posture d'un livrable
META_LIST = re.compile(r"^(" + "|".join(KNOWN_POSTURES) + r")\b\s*(?:\([^)]*\)\s*)?(?:,|\+|/|&|et\b|and\b)?\s*",
                       re.IGNORECASE)
TRAILING = re.compile(r"^(Amélioration|Piste|Suggestion|Pour améliorer)\b", re.IGNORECASE)
DATE_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


def heading_level(line: str) -> int:
    match = re.match(r"^(#{1,6})\s", line)
    return len(match.group(1)) if match else 0


def critic_sections(lines: list[str]) -> list[list[str]]:
    """Toutes les sections Critic d'un fichier, sans leur titre."""
    sections, i = [], 0
    while i < len(lines):
        line = lines[i].strip()
        if (START_HEADING.match(line) or START_PLAIN.match(line)) and not POSTURE.search(line):
            level = heading_level(line)
            body, i = [], i + 1
            while i < len(lines):
                current = lines[i].strip()
                lvl = heading_level(current)
                if level and lvl and lvl <= level:
                    break
                if not level and (lvl or PLAIN_END.match(current)):
                    break
                body.append(lines[i].rstrip())
                i += 1
            if any(b.strip() for b in body):
                sections.append(body)
            continue
        i += 1
    return sections


def unquote(raw: str) -> str:
    """Retire les marques de citation (> ou ▎) en gardant l'indentation qui suit."""
    return re.sub(r"^\s*(?:[>▎] ?)+", "", raw) if re.match(r"^\s*[>▎]", raw) else raw


def objections(body: list[str]) -> list[str]:
    """Une objection par point de premier niveau ; sans liste, la section entière en est une seule.
    Les sous-points restent rattachés à leur point. L'en-tête « [Posture : Critic] » est omis."""
    lines = [unquote(raw).rstrip() for raw in body]
    indents = [len(l) - len(l.lstrip()) for l in lines if ITEM.match(l.lstrip()) and l.strip()]
    top = min(indents) if indents else 0
    items: list[list[str]] = []
    preamble: list[str] = []
    for line in lines:
        text = line.strip()
        if not text or (POSTURE.search(text) and len(text) < 40):
            continue
        indent = len(line) - len(line.lstrip())
        if TRAILING.match(text):
            break   # la piste d'amélioration de Critic n'est pas une objection
        if ITEM.match(text) and indent <= top + 1:
            items.append([ITEM.sub("", text).strip()])
        elif items:
            items[-1].append(ITEM.sub("", text).strip())
        else:
            preamble.append(text)
    if not items:
        return [" ".join(preamble)] if preamble else []
    return [" ".join(parts) for parts in items]


def metadata_postures(lines: list[str]) -> list[str]:
    """Postures de la ligne « Posture : … » de l'en-tête (avant le premier titre « ## »). Seules celles qui
    ouvrent la valeur sont lues, séparées par une virgule, « et », « and », « + », « / » ou « & » : dans
    « Scaling (vue d'ensemble). Delivery ne commente aucune équipe », seule Scaling est la posture."""
    for line in lines:
        if re.match(r"^#{2,6}\s", line):
            break
        match = META_POSTURE.match(line)
        if not match:
            continue
        value, found = match.group(1).strip().lstrip("*_ "), []
        while (known := META_LIST.match(value)):
            found.append(known.group(1).capitalize())
            value = value[known.end():]
        if found:
            return list(dict.fromkeys(found))
    return []


def default_period(today: dt.date) -> tuple[dt.date, dt.date]:
    if today.day < 8:   # début de mois : le miroir porte sur le mois écoulé
        end = today.replace(day=1) - dt.timedelta(days=1)
        return end.replace(day=1), end
    return today.replace(day=1), today


def file_date(path: Path) -> dt.date:
    match = DATE_IN_NAME.search(path.name)
    if match:
        try:
            return dt.date.fromisoformat(match.group(1))
        except ValueError:
            pass
    return dt.date.fromtimestamp(path.stat().st_mtime)


def kind_of(path: Path, t: Messages | None = None) -> str:
    t = t or Messages(CATALOGS)
    parts = path.relative_to(OUTPUT_DIR).parts
    if parts[0] == "veille":
        return t("kind_veille")
    if parts[0] == "messages":
        return t("kind_messages")
    return t("kind_posture")


CATEGORY_COUNT = 11      # catégories de la grille : clés category_<n>_name et category_<n>_cover du catalogue


def categories_grid(t) -> str:
    """Grille de classement des objections, en tableau Markdown, dans la langue de `t`."""
    rows = [f"| {t(f'category_{n}_name')} | {t(f'category_{n}_cover')} |" for n in range(1, CATEGORY_COUNT + 1)]
    return "\n".join([t("categories_heading"), t("categories_header"), *rows])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extrait les objections de Critic des livrables")
    parser.add_argument("--since", dest="depuis")
    parser.add_argument("--until", dest="jusqu")
    parser.add_argument("--today", dest="aujourdhui", help=argparse.SUPPRESS)
    parser.add_argument("--categories", action="store_true", help="affiche la grille de classement des objections et s'arrête")
    add_language_option(parser)
    args = parser.parse_args(flux_config.refuse_old_options(sys.argv[1:] if argv is None else argv, OPTIONS_RENOMMEES))
    t = Messages(CATALOGS, args.language)
    if args.categories:
        print(categories_grid(t))
        return
    today = dt.date.fromisoformat(args.aujourdhui) if args.aujourdhui else dt.date.today()
    start, end = default_period(today)
    start = dt.date.fromisoformat(args.depuis) if args.depuis else start
    # --since seul : jusqu'à aujourd'hui (et non jusqu'à la fin de la période par défaut)
    end = dt.date.fromisoformat(args.jusqu) if args.jusqu else (today if args.depuis else end)

    files = sorted(p for p in OUTPUT_DIR.rglob("*.md")
                   if not any(part in IGNORED for part in p.relative_to(OUTPUT_DIR).parts)) \
        if OUTPUT_DIR.exists() else []
    found, without, count = [], [], 0
    for path in files:
        day = file_date(path)
        if not start <= day <= end:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        sections = critic_sections(lines)
        if not sections:
            without.append(path)
            continue
        postures = list(dict.fromkeys(
            metadata_postures(lines)
            + [p.capitalize() for p in POSTURE.findall("\n".join(lines)) if p.lower() != "critic"]))
        items = [o for body in sections for o in objections(body)]
        count += len(items)
        found.append((path, day, ", ".join(postures) or t("posture_not_stated"), items))

    print(t("title", start=start, end=end))
    print(t("summary", found=len(found), count=count, without=len(without)))
    n = 0
    for path, day, posture, items in found:
        print(t("deliverable_heading", path=path.relative_to(OUTPUT_DIR), date=day, kind=kind_of(path, t), posture=posture))
        for item in items:
            n += 1
            print(t("objection_line", number=n, text=item))
        print()
    if without:
        print(t("without_heading"))
        for path in without:
            print(f"- {path.relative_to(OUTPUT_DIR)}")


if __name__ == "__main__":
    main()
