# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]", "httpx", "numpy", "mcp>=1.2,<2"]
# ///
"""
PMZilla Lab : tableau de bord.

Une seule page HTML autonome (CSS et courbes SVG en ligne, aucun JavaScript, aucun appel réseau),
écrite dans <dossier du lab>/tableau-de-bord.html. Elle ne reprend que des comptes, des dates, des
noms de sources, des titres de livres et des textes écrits par l'utilisateur (journal, miroir) : jamais
le contenu d'un article ou d'un livre, jamais un titre d'article.

    uv run tools/dashboard.py [--open] [--output CHEMIN] [--language fr|en]

--language fr|en : langue de la page (français par défaut) : titres, libellés, phrases, dates et `<html lang>`. Les formats
lus dans d'autres fichiers (logs de la veille, rapports d'essai et du flux, journal) ne changent pas avec la langue.

Sources lues (chacune peut manquer : la section affiche « pas encore de données ») :
    ~/Library/Logs/pmzilla-watch.log et pmzilla-essai.log
    _bmad-output/essais/essai-*.md, _bmad-output/pmzilla/{veille,miroir}/
    base de la veille (schéma knowledge, rôle pmzilla_knowledge_ro, délai de connexion de 2 s) : articles et passages de la collection
    watch (tables de la bibliothèque, nom exact de la collection), partages et sélections du jour (tables triage_*) ; base qui ne répond
    pas : « source illisible » avec le seul type de l'erreur. Aucun ancien fichier d'état n'est ouvert.
    base de la bibliothèque (schéma knowledge : livres, collections, passages ; rôle pmzilla_knowledge_ro, délai de connexion
    de 2 s, base nommée par PMZILLA_LAB_KNOWLEDGE_DBNAME si elle est posée) : section bibliothèque.
    Base qui ne répond pas : « source illisible » avec le seul type de l'erreur ; aucun livre : « pas encore de données »
    tools/book_catalog.yaml (pas lu directement : l'index porte déjà les auteurs),
    tools/mapping_lab.py (commentaire des livres absents), watch/tri.yaml
    Journal-Lab/journal.yaml, Flux-Lab/rapports/evolution-*.md
    base des cas (schéma cases, rôle pmzilla_cases_ro, délai de connexion de 2 s) : les expérimentations en cours de l'auteur configuré
    uv run tools/critic_mirror.py (nombre d'objections du mois)

Variables d'environnement (pour les tests) : PMZILLA_LAB_WORKSPACE, PMZILLA_LAB_DATA,
PMZILLA_LAB_LOGS, PMZILLA_LAB_TODAY (AAAA-MM-JJ), PMZILLA_LAB_OUTPUT (fichier de sortie).
Une section en échec n'empêche jamais la page de s'écrire, et le script sort toujours avec le code 0.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flux_config
import lab_paths
import watch_paths
from dashboard_messages import CATALOGS
from messages import Messages, add_language_option

LAB = lab_paths.resolve_or_exit()   # module partagé : variable, sinon dépôt Git du code, sinon code 78
WORKSPACE = LAB["content_root"]   # dossier de contenu
CODE_ROOT = Path(__file__).resolve().parent.parent   # dossier de code : réglages suivis et scripts, liens suivis
DATA = Path(os.environ.get("PMZILLA_LAB_DATA", "~/.pmzilla-lab")).expanduser()
LOGS = Path(os.environ.get("PMZILLA_LAB_LOGS", "~/Library/Logs")).expanduser()
OUT = Path(os.environ.get("PMZILLA_LAB_OUTPUT") or LAB["lab_folder"] / "tableau-de-bord.html").expanduser()
DOMAINES = ["produit", "flow", "organisation", "facilitation", "tech"]
PASSAGES_VEILLE = 14
PREMIER_MIROIR = dt.date(2026, 11, 1)   # tant qu'aucun miroir n'existe, le premier est prévu début novembre
SEUIL_ANCIENNETE_JOURS = 31


t = Messages(CATALOGS, "fr")   # langue de la page : fixée par main() / build() avant tout rendu


def set_language(language: str) -> None:
    global t
    t = Messages(CATALOGS, language)


class PasDeDonnees(Exception):
    pass


def today() -> dt.date:
    raw = os.environ.get("PMZILLA_LAB_TODAY")
    return dt.date.fromisoformat(raw) if raw else dt.date.today()


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def nd(message: str | None = None) -> str:
    return f'<p class="nd">{esc(t("no_data_yet") if message is None else message)}</p>'


def pl(n: int, key: str) -> str:
    """« 0 passage », « 1 passage », « 2 passages » : le pluriel à partir de deux (clés `<key>_one` et `<key>_other`)."""
    return t(f"{key}_one" if n < 2 else f"{key}_other", n=n)


def pb(n: int, key: str) -> str:
    return t(f"{key}_one" if n < 2 else f"{key}_other", n=f"<b>{n}</b>")


def fr_date(d: dt.date) -> str:
    """Date complète dans la langue de la page (JJ/MM/AAAA en français, AAAA-MM-JJ en anglais)."""
    return d.strftime(t("full_date_format"))


def short_date(d: dt.date) -> str:
    return d.strftime(t("short_date_format"))


def read_text(path: Path) -> str:
    if not path.is_file():
        raise PasDeDonnees
    return path.read_text(encoding="utf-8", errors="replace")


# --- petits éléments graphiques -------------------------------------------------------------

def sparkline(values: list[float], width: int = 900, height: int = 80, ymax: float | None = None) -> str:
    if not values:
        return ""
    top = ymax if ymax else (max(values) or 1)
    top = top or 1
    step = (width - 20) / max(len(values) - 1, 1)
    points = [(round(10 + i * step, 1), round(height - 10 - (v / top) * (height - 20), 1)) for i, v in enumerate(values)]
    line = " ".join(f"{x},{y}" for x, y in points)
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="2.6"/>' for x, y in points)
    return (f'<svg class="spark" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(t("aria_curve"))}">'
            f'<polyline points="{line}" fill="none"/>{dots}</svg>')


def bars(values: list[float], labels: list[str], width: int = 900, height: int = 150) -> str:
    """Histogramme pleine largeur : la valeur au-dessus de chaque barre, la date (JJ/MM) dessous."""
    if not values:
        return ""
    top = max(values) or 1
    slot = width / len(values)
    base = height - 26
    out = []
    for i, (value, label) in enumerate(zip(values, labels)):
        h = round((value / top) * (base - 26), 1)
        x = round(i * slot + 4, 1)
        cx = round(i * slot + slot / 2, 1)
        y = round(base - h, 1)
        out.append(f'<rect x="{x}" y="{y}" width="{round(slot - 8, 1)}" height="{h}" rx="3"><title>{esc(t("bar_title", label=label, value=format(value, "g")))}</title></rect>'
                   f'<text x="{cx}" y="{round(y - 6, 1)}" text-anchor="middle">{value:g}</text>'
                   f'<text x="{cx}" y="{height - 6}" text-anchor="middle">{esc(label)}</text>')
    return f'<svg class="bars" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(t("aria_bars"))}">{"".join(out)}</svg>'


def courbe_scores(points: list[tuple[int, int]], width: int = 900, height: int = 150) -> str:
    """Courbe pleine largeur de 80 à 100 % : le score (ex. 30/32) sous chaque point."""
    if not points:
        return ""
    low, high = 80.0, 100.0
    left = 48
    step = (width - left - 36) / max(len(points) - 1, 1)
    coords = []
    for i, (ok, total) in enumerate(points):
        pct = min(max(ok / total * 100, low), high)
        coords.append((round(left + i * step, 1), round(18 + (high - pct) / (high - low) * (height - 66), 1), ok, total))
    line = " ".join(f"{x},{y}" for x, y, _, _ in coords)
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="3.5"/><text x="{x}" y="{round(y + 18, 1)}" text-anchor="middle">{ok}/{total}</text>'
                   for x, y, ok, total in coords)
    axes = (f'<text class="axe" x="0" y="22">{esc(t("axis_top"))}</text><text class="axe" x="0" y="{height - 46}">{esc(t("axis_bottom"))}</text>')
    return (f'<svg class="spark score" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(t("aria_scores"))}">{axes}'
            f'<polyline points="{line}" fill="none"/>{dots}</svg>')


def table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def badge(text: str, kind: str = "") -> str:
    return f'<span class="badge {kind}">{esc(text)}</span>'


# --- 0. Santé --------------------------------------------------------------------------------

def health_reason(check: dict) -> str:
    """Raison d'une ligne du fichier d'état dans la langue de la page, avec les catalogues du doctor (clé inconnue : la clé)."""
    from doctor_messages import CATALOGS as DOCTOR_CATALOGS
    from messages import fields
    dt_ = Messages(DOCTOR_CATALOGS, t.language)
    reason = check.get("reason") or {}
    key, counts = str(reason.get("key", "")), reason.get("counts") or {}
    full = DOCTOR_CATALOGS["fr"]
    name = f"raison_{str(check.get('id', '')).replace('-', '_')}_{key}"
    if name not in full:
        name = f"raison_{key}"
    if name not in full:
        return key
    values = {f: (counts.get(f, 0) if f != "noms" else "") for f in fields(full[name])}
    return dt_(name, **values)


def section_sante() -> str:
    """Le fichier d'état écrit par `doctor.py --record` (version 1) : jamais de lancement du doctor, aucun autre fichier."""
    from doctor_messages import CATALOGS as DOCTOR_CATALOGS
    state = json.loads(read_text(DATA / "doctor-etat.json"))
    checked = dt.datetime.fromisoformat(state["checked_at"])
    head = f'<p class="legend">{esc(t("health_checked", date=checked.strftime(t("stamp_format"))))}</p>'
    lines = [c for c in state["checks"] if c["level"] in ("problem", "warning")]
    if not lines:
        return head + f'<p>{badge(t("health_all_good"), "ok")}</p>'
    level_texts = Messages(DOCTOR_CATALOGS, t.language)
    rows = [[esc(c["id"]), badge(level_texts(f"niveau_{c['level']}"), "warn" if c["level"] == "warning" else "ko"),
             esc(health_reason(c))] for c in lines]
    return head + table([t("health_check"), t("health_level"), t("health_reason")], rows)


# --- 1. À faire ------------------------------------------------------------------------------

def journal_block() -> str:
    import yaml
    raw = read_text(WORKSPACE / "Journal-Lab" / "journal.yaml")
    entries = yaml.safe_load(raw) or []
    now = today()
    late, soon, experiences = [], [], []
    for entry in entries:
        perimetre = entry.get("perimetre", "")
        for suite in entry.get("suites") or []:
            if suite.get("statut") != "ouverte":
                continue
            due = dt.date.fromisoformat(str(suite["echeance"]))
            row = [esc(fr_date(due)), esc(suite.get("pour", "")), esc(suite.get("quoi", "")), esc(perimetre)]
            if due < now:
                late.append((due, row))
            elif due <= now + dt.timedelta(days=7):
                soon.append((due, row))
        exp = entry.get("experience")
        if exp and exp.get("statut") == "en cours":
            due = dt.date.fromisoformat(str(exp["bilan_le"]))
            if due <= now:
                experiences.append((due, [esc(fr_date(due)), esc(exp.get("hypothese", "")), esc(perimetre)]))
    parts = []
    heads = [t("head_due"), t("head_role"), t("head_follow_up"), t("head_scope")]
    parts.append(f"<h3>{t('late_follow_ups', n=len(late))}</h3>" +
                 (table(heads, [r for _, r in sorted(late, key=lambda x: x[0])], "late") if late else nd(t("none_f"))))
    parts.append(f"<h3>{t('upcoming_follow_ups', n=len(soon))}</h3>" +
                 (table(heads, [r for _, r in sorted(soon, key=lambda x: x[0])]) if soon else nd(t("none_f"))))
    parts.append(f"<h3>{t('due_experiments', n=len(experiences))}</h3>" +
                 (table([t("head_review_planned"), t("head_hypothesis"), t("head_scope")],
                        [r for _, r in sorted(experiences, key=lambda x: x[0])])
                  if experiences else nd(t("none_f"))))
    return "".join(parts)


def dated_files(directory: Path, pattern: str, regex: str) -> list[tuple[dt.date, Path]]:
    found = []
    if directory.is_dir():
        for path in directory.glob(pattern):
            match = re.search(regex, path.name)
            if match:
                found.append((dt.date.fromisoformat(match.group(1)), path))
    return sorted(found)


def cadence_block() -> str:
    now = today()
    rows = []
    # synthèse de veille : le lundi
    synth = dated_files(WORKSPACE / "_bmad-output" / "pmzilla" / "veille", "synthese-*.md", r"synthese-(\d{4}-\d{2}-\d{2})")
    last = synth[-1][0] if synth else None
    due = (last is None) or (now.weekday() == 0 and last < now) or (now - last).days > 7
    rows.append([t("reminder_veille"), t("cadence_veille"), esc(fr_date(last)) if last else t("none_f"),
                 badge(t("badge_todo"), "warn") if due else badge(t("badge_up_to_date"), "ok")])
    # flux : à faire seulement si le dernier rapport de calcul a plus de 31 jours
    rapports = WORKSPACE / "Flux-Lab" / "rapports"
    flux = dated_files(rapports, "evolution-*.md", r"(\d{4}-\d{2}-\d{2})\.md$") + dated_files(rapports, "flux-*.md", r"(\d{4}-\d{2}-\d{2})\.md$")
    last = max(d for d, _ in flux) if flux else None
    due = last is not None and (now - last).days > SEUIL_ANCIENNETE_JOURS
    etat = (badge(t("badge_todo"), "warn") if due else
            (badge(t("badge_up_to_date"), "ok") if last else badge(t("badge_no_report_yet"), "")))
    rows.append([t("reminder_flux"), t("cadence_flux"), esc(fr_date(last)) if last else t("none_m"), etat])
    # miroir de Critic : premier prévu début novembre, puis à faire au début d'un mois si le dernier a plus de 31 jours
    dossier = WORKSPACE / "_bmad-output" / "pmzilla" / "miroir"
    miroirs = sorted(dossier.glob("miroir-*.md")) if dossier.is_dir() else []
    last = dt.date.fromtimestamp(max(p.stat().st_mtime for p in miroirs)) if miroirs else None
    if last is None:
        if now < PREMIER_MIROIR:
            etat = badge(t("badge_first_mirror"), "")
        else:
            etat = badge(t("badge_todo"), "warn")
    else:
        due = now.day <= 7 and (now - last).days > SEUIL_ANCIENNETE_JOURS
        etat = badge(t("badge_todo"), "warn") if due else badge(t("badge_up_to_date"), "ok")
    rows.append([t("reminder_mirror"), t("cadence_mirror"), esc(fr_date(last)) if last else t("none_m"), etat])
    return table([t("head_reminder"), t("head_cadence"), t("head_last_file"), t("head_state")], rows)


def mode_block() -> str:
    import yaml
    raw = read_text(watch_paths.config_dir(CODE_ROOT) / "tri.yaml")
    mode = (yaml.safe_load(raw) or {}).get("mode", t("mode_unknown"))
    kind = "warn" if mode == "observation" else "ok"
    detail = t("mode_detail_observation") if mode == "observation" else t("mode_detail_filter")
    return t("mode_line", badge=badge(mode, kind), detail=esc(detail))


def section_a_faire() -> str:
    return "".join(safe(block) for block in (journal_block, cadence_block, mode_block))


# --- 1b. Expérimentations en attente de résultat (design.md 8 du change db-lot2) ------------------

CASES_TIMEOUT_SECONDS = 2


def fetch_running_experiments(author: str, day: dt.date) -> list[dict]:
    """Lecteur réel : rôle de lecture seule de la base des cas, connexion courte. Lève si la base ne répond pas."""
    import cases_store
    conn = cases_store.connect_cases(cases_store.ROLE_READ, timeout=CASES_TIMEOUT_SECONDS)
    try:
        return cases_store.running_experiments(conn, author, day)
    finally:
        conn.close()


def section_experiences(fetch=None) -> str:
    """`fetch(author, today)` est injectable (tests) ; par défaut, fetch_running_experiments (cherché à l'appel)."""
    import cases_store
    author = cases_store.resolve_author(WORKSPACE)
    if not author:
        raise PasDeDonnees
    day = today()
    rows = (fetch or fetch_running_experiments)(author, day)
    if not rows:
        raise PasDeDonnees
    due = sum(1 for row in rows if row["due"])
    body = [[esc(row["number"]), esc(row["problem"]), esc(fr_date(dt.date.fromisoformat(row["started_on"]))),
             esc(fr_date(dt.date.fromisoformat(row["review_due"]))), esc(row["postponements"]),
             badge(t("experiment_due"), "warn") if row["due"] else ""] for row in rows]
    headers = [t("experiment_number"), t("experiment_problem"), t("experiment_started"), t("experiment_review"),
               t("experiment_postponements"), t("experiment_status")]
    return f"<h3>{esc(t('experiments_heading', running=len(rows), due=due))}</h3>" + table(headers, body)


# --- 2. Veille -------------------------------------------------------------------------------

def parse_veille_log() -> list[dict]:
    # journal de la tâche : pmzilla-watch.log (l'ancien pmzilla-veille.log n'est plus lu)
    text = read_text(LOGS / "pmzilla-watch.log")
    passes: list[dict] = []
    current = None
    for line in text.splitlines():
        header = re.match(r"^=== (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) ===", line)
        if header:
            current = {"jour": dt.date.fromisoformat(header.group(1)), "heure": header.group(2), "nouveaux": 0,
                       "erreurs": [], "pretri_s": 0, "pretries": 0, "a_lire": None, "ecartes": None, "partages": None}
            passes.append(current)
            continue
        if current is None:
            continue
        if match := re.match(r"^(\S+) : (\d+) nouveaux", line):
            current["nouveaux"] += int(match.group(2))
        elif match := re.match(r"^(\S+) : ERREUR", line):
            current["erreurs"].append(match.group(1))
        elif line.startswith("[") and (match := re.search(r"· (\d+) s\s*$", line)):
            current["pretri_s"] += int(match.group(1))
            current["pretries"] += 1
        elif match := re.search(r"(\d+) articles sur la période · (\d+) à lire · (\d+) seraient écartés", line):
            current["a_lire"], current["ecartes"] = int(match.group(2)), int(match.group(3))
        elif match := re.search(r"Partages : (\d+) liens lus sur Bluesky · (\d+) nouveaux articles de la veille partagés \((\d+) au total\)", line):
            current["partages"] = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return passes[-PASSAGES_VEILLE:]


def veille_log_block() -> str:
    passes = parse_veille_log()
    if not passes:
        raise PasDeDonnees
    par_jour: dict[dt.date, int] = {}
    for p in passes:
        par_jour[p["jour"]] = par_jour.get(p["jour"], 0) + p["nouveaux"]
    jours = sorted(par_jour)
    out = [t("new_articles_per_day", runs=pl(len(passes), "latest_run")),
           bars([par_jour[j] for j in jours], [short_date(j) for j in jours]),
           t("new_articles_legend", first=esc(fr_date(jours[0])), last=esc(fr_date(jours[-1])),
             count=pl(sum(par_jour.values()), "new_article"))]
    # sources en erreur : jours consécutifs
    dernier_par_jour: dict[dt.date, list[str]] = {}
    for p in passes:
        dernier_par_jour[p["jour"]] = p["erreurs"]
    jours_desc = sorted(dernier_par_jour, reverse=True)
    erreurs = []
    for source in dernier_par_jour[jours_desc[0]]:
        n = 0
        for jour in jours_desc:
            if source in dernier_par_jour[jour]:
                n += 1
            else:
                break
        erreurs.append([esc(source), t("consecutive_days_other" if n > 1 else "consecutive_days_one", n=n)])
    out.append(t("sources_in_error") + (table([t("head_source"), t("head_since")], erreurs) if erreurs else nd(t("none_f"))))
    # durée du pré-tri : seulement les passages qui ont pré-trié au moins un article, courbe à partir de deux
    durees = [p["pretri_s"] for p in passes if p["pretries"] > 0]
    minutes = lambda sec: t("minutes_seconds", minutes=sec // 60, seconds=sec % 60)
    out.append(t("pretri_duration_heading"))
    if len(durees) >= 2:
        out.append(sparkline([float(d) for d in durees]) +
                   t("pretri_legend", duration=minutes(durees[-1]), runs=pl(len(durees), "run")))
    elif durees:
        out.append(t("pretri_single", duration=minutes(durees[0])))
    else:
        out.append(nd(t("pretri_none")))
    # à lire
    avec = [p for p in passes if p["a_lire"] is not None]
    if avec:
        a_lire, ecartes = avec[-1]["a_lire"], avec[-1]["ecartes"]
        out.append(t("last_list", n=a_lire, to_read=t("to_read_one" if a_lire < 2 else "to_read_other"), skipped_n=ecartes,
                     skipped=t("discarded_one" if ecartes < 2 else "discarded_other")))
    partages = [p["partages"] for p in passes if p["partages"]]
    if partages:
        lus, nouveaux, total = partages[-1]
        out.append(t("last_bluesky", links=pl(lus, "link_read"), shares=pl(nouveaux, "new_share"), total=total))
    return "".join(out)


WATCH_COUNTS_SQL = (
    "WITH watch_books AS (SELECT b.id FROM knowledge.books b WHERE EXISTS (SELECT 1 FROM knowledge.book_collections bc "
    "JOIN knowledge.collections co ON co.id = bc.collection_id WHERE bc.book_id = b.id AND co.name = ANY(%s))) "
    "SELECT (SELECT count(*) FROM watch_books), (SELECT count(*) FROM knowledge.chunks c WHERE c.book_id IN (SELECT id FROM watch_books))")
SHARES_SQL = (
    "SELECT (SELECT count(*) FROM knowledge.triage_shared), "
    "(SELECT count(*) FROM knowledge.triage_shared WHERE post_date >= %(recent)s), "
    "(SELECT min(day) FROM knowledge.triage_daily_picks)")
EVALUABLE_SQL = (
    "SELECT count(*), count(*) FILTER (WHERE EXISTS (SELECT 1 FROM knowledge.triage_daily_picks p WHERE p.file = s.file AND p.day <= s.post_date)) "
    "FROM knowledge.triage_shared s WHERE s.post_date >= %(first)s")


def fetch_watch_counts(connect=None) -> dict:
    """Lecteur réel : articles et passages indexés de la collection de la veille (nom actuel ou ancien, par nom exact), sous le
    rôle de lecture seule. Lève si la base ne répond pas. `connect` est injectable ; la connexion est toujours fermée."""
    conn = (connect or connect_knowledge)()
    try:
        articles, passages = conn.execute(WATCH_COUNTS_SQL, (sorted(WATCH_COLLECTIONS),)).fetchone()
    finally:
        conn.close()
    return {"articles": int(articles), "passages": int(passages)}


def fetch_shares(day: dt.date, connect=None) -> dict:
    """Lecteur réel : partages, partages des 14 derniers jours, premier jour des sélections, partages postérieurs à ce jour et
    ceux qui figuraient déjà dans les « à lire » avant d'être partagés. Lève si la base ne répond pas."""
    conn = (connect or connect_knowledge)()
    try:
        total, recent, first_pick = conn.execute(SHARES_SQL, {"recent": day - dt.timedelta(days=14)}).fetchone()
        evaluable = hits = 0
        if first_pick is not None:
            evaluable, hits = conn.execute(EVALUABLE_SQL, {"first": first_pick}).fetchone()
    finally:
        conn.close()
    return {"total": int(total), "recent": int(recent), "first_pick": first_pick.isoformat() if first_pick else None,
            "evaluable": int(evaluable), "hits": int(hits)}


def veille_base_block(fetch=None) -> str:
    """`fetch()` est injectable (tests) ; par défaut, fetch_watch_counts (cherché à l'appel)."""
    counts = (fetch or fetch_watch_counts)()
    return t("veille_collection", articles=pb(counts["articles"], "article"), passages=pl(counts["passages"], "indexed_passage"))


def partages_block(fetch=None) -> str:
    """`fetch(jour)` est injectable (tests) ; par défaut, fetch_shares (cherché à l'appel)."""
    shares = (fetch or fetch_shares)(today())
    out = [t("shares_total", total=shares["total"], recent=shares["recent"])]
    first_pick = shares["first_pick"]
    if shares["total"] == 0:
        out.append(nd(t("shares_none")))
    elif first_pick is None:
        out.append(nd(t("shares_no_picks")))
    elif not shares["evaluable"]:
        out.append(nd(t("shares_not_evaluable", date=first_pick)))
    else:
        out.append(t("shares_hits", hits=shares["hits"], total=shares["evaluable"],
                     percent=round(100 * shares["hits"] / shares["evaluable"]), date=esc(first_pick)))
    return "".join(out)


def section_veille() -> str:
    blocks = [veille_log_block, veille_base_block, partages_block]
    return "".join(safe(b) for b in blocks)


# --- 3. Bibliothèque -------------------------------------------------------------------------

KNOWLEDGE_ROLE = "pmzilla_knowledge_ro"
KNOWLEDGE_TIMEOUT_SECONDS = CASES_TIMEOUT_SECONDS   # même délai de connexion court que la section des expérimentations
LIBRARY_SQL = ("SELECT b.title, b.author, ARRAY(SELECT co.name FROM knowledge.book_collections bc "
               "JOIN knowledge.collections co ON co.id = bc.collection_id WHERE bc.book_id = b.id), "
               "(SELECT count(*) FROM knowledge.chunks c WHERE c.book_id = b.id) FROM knowledge.books b")


def connect_knowledge():
    """Connexion réelle : rôle de lecture seule, délai court ; base nommée par PMZILLA_LAB_KNOWLEDGE_DBNAME si elle est posée."""
    import db
    return db.connect(role=KNOWLEDGE_ROLE, timeout=KNOWLEDGE_TIMEOUT_SECONDS,
                      dbname=os.environ.get("PMZILLA_LAB_KNOWLEDGE_DBNAME") or None)


def fetch_library_books(connect=None) -> list[dict]:
    """Lecteur réel du schéma knowledge : un dict par livre (title, author dérivé, collections, passages). Lève si la base
    ne répond pas. `connect` est injectable (base jetable des tests) ; la connexion est toujours fermée."""
    conn = (connect or connect_knowledge)()
    try:
        rows = conn.execute(LIBRARY_SQL).fetchall()
    finally:
        conn.close()
    return [{"title": title, "author": author, "collections": list(names or []), "passages": int(passages)}
            for title, author, names, passages in rows]


def library_books(read=None) -> list[dict]:
    """`read()` est injectable (tests) ; par défaut, fetch_library_books (cherché à l'appel)."""
    return (read or fetch_library_books)()


WATCH_COLLECTIONS = {watch_paths.NEW["collection"], watch_paths.OLD["collection"]}


def livres_block(read=None) -> str:
    # exclusion par nom exact de collection (jamais par sous-chaîne) : veille (nom actuel et ancien) et collection personnelle
    exclues = WATCH_COLLECTIONS | {watch_paths.OWN_COLLECTION}
    rows = [row for row in library_books(read) if not exclues & set(row["collections"])]
    if not rows:
        raise PasDeDonnees
    passages = sum(row["passages"] for row in rows)
    domaines = {d: 0 for d in DOMAINES}
    sans_auteur = []
    for row in rows:
        for name in row["collections"]:
            if name in domaines:
                domaines[name] += 1
        author = row["author"]
        if not author or "auteur non indiqué" in author:
            sans_auteur.append(row["title"])
    out = [t("books_summary", books=pb(len(rows), "book"), passages=pl(passages, "passage")),
           table([t("head_domain"), t("head_books")], [[esc(d), str(n)] for d, n in domaines.items()]),
           f"<h3>{t('books_without_author', n=len(sans_auteur))}</h3>",
           ("<ul>" + "".join(f"<li>{esc(title)}</li>" for title in sorted(sans_auteur)) + "</ul>") if sans_auteur else nd(t("none_m"))]
    return "".join(out)


def titres_absents(lines: list[str]) -> list[str]:
    """Extrait « Titre (Auteurs) » des commentaires de MAPPING, sans codes de domaine ni explications."""
    blocs, bloc = [], []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            bloc.append(stripped.lstrip("# ").rstrip())
        else:
            if bloc:
                blocs.append(bloc)
            bloc = []
    if bloc:
        blocs.append(bloc)
    titres: list[str] = []
    for bloc in blocs:
        if not any("re-télécharger" in l for l in bloc):
            continue
        # on garde les lignes de liste (indentées dans le commentaire), pas les phrases d'introduction
        corps = " ; ".join(l for l in bloc if not re.search(r"re-télécharger|avec les domaines|^---", l))
        morceaux, profondeur, courant = [], 0, ""
        for ch in corps:
            profondeur += (ch == "(") - (ch == ")")
            if ch in ",;" and profondeur == 0:
                morceaux.append(courant)
                courant = ""
            else:
                courant += ch
        morceaux.append(courant)
        for morceau in morceaux:
            morceau = morceau.strip().rstrip(".").strip()
            if not morceau or re.match(r"(le |la |les )", morceau) or "le livre complet" in morceau or "le fichier actuel" in morceau:
                continue
            morceau = re.sub(r"\s+[A-Z]{1,5}$", "", morceau).strip()
            deux = re.match(r"^(The .+?) et (The .+?) \(([^)]*)\)$", morceau)   # « A et B (Auteur) » : un livre par ligne
            if deux:
                titres += [f"{deux.group(1)} ({deux.group(3)})", f"{deux.group(2)} ({deux.group(3)})"]
            elif morceau:
                titres.append(morceau)
    return titres


def absents_block() -> str:
    path = CODE_ROOT / "tools" / "mapping_lab.py"
    if not path.is_file():
        path = LAB["lab_folder"] / "mapping_lab.py"
    titres = titres_absents(read_text(path).splitlines())
    if not titres:
        raise PasDeDonnees
    return (f"<h3>{t('missing_books', n=len(titres))}</h3>" +
            "<ul>" + "".join(f"<li>{esc(title)}</li>" for title in titres) + "</ul>")


def articles_sans_auteur_block(read=None) -> str:
    rows = [row for row in library_books(read) if WATCH_COLLECTIONS & set(row["collections"])]
    if not rows:
        raise PasDeDonnees
    sans_rien = sans_nom = 0
    for row in rows:
        author = (row["author"] or "").strip()
        if not author:
            sans_rien += 1
        elif "auteur non indiqué" in author:
            sans_nom += 1
    return t("veille_without_author", total=len(rows), no_author=sans_rien, site_only=sans_nom)


def section_bibliotheque() -> str:
    return "".join(safe(b) for b in (livres_block, absents_block, articles_sans_auteur_block))


# --- 4. Qualité ------------------------------------------------------------------------------

def parse_rapports() -> list[dict]:
    directory = WORKSPACE / "_bmad-output" / "essais"
    if not directory.is_dir():
        raise PasDeDonnees
    rapports = []
    for path in sorted(directory.glob("essai-*.md")):
        name = re.match(r"essai-(\d{4}-\d{2}-\d{2})-(\d{6})\.md", path.name)
        if not name:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        score = re.search(r"(\d+)/(\d+) vérifications réussies.*?État testé : (\w+)", text, re.S)
        if not score:
            continue
        regressions = 0
        match = re.search(r"## Régressions[^\n]*\n(.*?)(?=\n## )", text, re.S)
        if match:
            regressions = len(re.findall(r"^- \*\*", match.group(1), re.M))
        cas = {}
        table_match = re.search(r"\| Cas \|.*?\n\|[-| ]+\n(.*?)(?=\n\n)", text, re.S)
        cost = 0.0
        if table_match:
            for row in table_match.group(1).splitlines():
                cells = [c.strip() for c in row.strip().strip("|").split("|")]
                if len(cells) >= 4:
                    ok = re.match(r"(\d+)/(\d+)", cells[1])
                    price = re.match(r"([\d.]+)", cells[3])
                    cas[cells[0]] = (int(ok.group(1)), int(ok.group(2))) if ok else (0, 0)
                    cost += float(price.group(1)) if price else 0.0
        models = re.search(r"^modèles : sessions (.+?) · juge (.+?)$", text, re.M)
        rapports.append({"date": dt.date.fromisoformat(name.group(1)), "heure": name.group(2), "ok": int(score.group(1)),
                         "modeles": (models.group(1), models.group(2)) if models else None,
                         "non_validant": "**Passage non validant**" in text,
                         "total": int(score.group(2)), "commit": score.group(3)[:7], "regressions": regressions,
                         "cas": cas, "cout": cost})
    if not rapports:
        raise PasDeDonnees
    return rapports


def model_name(label: str) -> str:
    return t("model_default") if label == "défaut" else label     # « défaut » : écrit tel quel par le rapport (français)


def qualite_block() -> str:
    tous = parse_rapports()
    total_complet = tous[-1]["total"]          # un passage complet a autant de vérifications que le dernier
    memes_verifs = [r for r in tous if r["total"] == total_complet]
    rapports = [r for r in memes_verifs if not r["non_validant"]]      # un passage non validant n'entre pas dans la courbe
    partiels = len(tous) - len(memes_verifs)
    rows = [[esc(fr_date(r["date"])), f"<code>{esc(r['commit'])}</code>", f"{r['ok']}/{r['total']}",
             badge(str(r["regressions"]), "warn" if r["regressions"] else "ok"), t("cost_amount", amount=f"{r['cout']:.2f}"),
             esc(t("models_cell", sessions=model_name(r["modeles"][0]), judge=model_name(r["modeles"][1])) if r["modeles"] else "-")
             + (" " + badge(t("not_validating"), "warn") if r["non_validant"] else "")]
            for r in reversed(memes_verifs[-10:])]
    nb = min(len(rapports), 12)
    out = [f"<h3>{t('history_heading')}</h3>",
           courbe_scores([(r["ok"], r["total"]) for r in rapports[-12:]]),
           '<p class="legend">' + t("history_legend", runs=pl(nb, "full_run"), total=total_complet)
           + (t("history_legend_partial", partial=pl(partiels, "partial_run")) if partiels else "") + '</p>',
           table([t("head_date"), t("head_commit"), t("head_score"), t("head_regressions"), t("head_cost"), t("head_models")], rows)]
    derniers = rapports[-5:]
    noms = []
    for r in derniers:
        for name in r["cas"]:
            if name not in noms:
                noms.append(name)
    matrix = []
    for name in noms:
        cells = [esc(name)]
        for r in derniers:
            if name in r["cas"]:
                ok, total = r["cas"][name]
                cells.append(f'<span class="cell {"ok" if ok == total else "ko"}">{ok}/{total}</span>')
            else:
                cells.append('<span class="cell nd">-</span>')
        matrix.append(cells)
    out.append(f"<h3>{t('cases_state', runs=pl(len(derniers), 'latest_run'))}</h3>" +
               table([t("head_case")] + [t("run_label", date=short_date(r["date"]), hour=r["heure"][:2], minute=r["heure"][2:4])
                                         for r in derniers], matrix, "matrix"))
    now = today()
    mois = [r for r in tous if (r["date"].year, r["date"].month) == (now.year, now.month)]
    out.append(t("month_cost", month=now.strftime(t("month_format")),
                 cost=t("cost_amount", amount=f"{sum(r['cout'] for r in mois):.2f}"), runs=pl(len(mois), "run")))
    return "".join(out)


def section_qualite() -> str:
    return safe(qualite_block)


# --- 5. Flux ---------------------------------------------------------------------------------

def section_flux() -> str:
    rapports = WORKSPACE / "Flux-Lab" / "rapports"
    if not rapports.is_dir():
        raise PasDeDonnees
    evolutions: dict[str, tuple[dt.date, Path]] = {}
    for path in rapports.glob("evolution-*.md"):
        match = re.match(r"evolution-(.+)-(\d{4}-\d{2}-\d{2})\.md$", path.name)
        if match:
            nom, date = match.group(1), dt.date.fromisoformat(match.group(2))
            if nom not in evolutions or date > evolutions[nom][0]:
                evolutions[nom] = (date, path)
    if not evolutions:
        calculs = {}
        for path in rapports.glob("flux-*.md"):
            match = re.match(r"flux-(.+)-(\d{4}-\d{2}-\d{2})\.md$", path.name)
            if match:
                calculs[match.group(1)] = max(calculs.get(match.group(1), dt.date.min), dt.date.fromisoformat(match.group(2)))
        if not calculs:
            raise PasDeDonnees
        rows = [[esc(nom), esc(fr_date(date))] for nom, date in sorted(calculs.items())]
        return (f"<p>{t('flux_no_evolution_report')}</p>" + table([t("head_scope_flux"), t("head_last_computation")], rows))
    out = []
    for nom, (date, path) in sorted(evolutions.items()):
        text = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"## (?:Ce qui a bougé|What changed)\n(.*?)(?=\n## |\Z)", text, re.S)
        signals = [l[2:].strip() for l in (match.group(1).splitlines() if match else []) if l.startswith("- ")]
        out.append(f"<h3>{esc(nom)} <span class='legend'>({esc(fr_date(date))})</span></h3>" +
                   ("<ul>" + "".join(f"<li>{esc(s)}</li>" for s in signals) + "</ul>" if signals else nd(t("flux_no_changed_section"))))
    return "".join(out)


# --- 6. Critic -------------------------------------------------------------------------------

def miroir_block() -> str:
    directory = WORKSPACE / "_bmad-output" / "pmzilla" / "miroir"
    miroirs = sorted(directory.glob("miroir-*.md")) if directory.is_dir() else []
    if not miroirs:
        raise PasDeDonnees
    latest = max(miroirs, key=lambda p: p.stat().st_mtime)
    text = latest.read_text(encoding="utf-8", errors="replace")
    title = re.search(r"^# (.+)$", text, re.M)
    match = re.search(r"^## [^\n]*(?:angles morts|blind spots)[^\n]*\n(.*?)(?=\n## |\Z)", text, re.S | re.M | re.I)
    body = (match.group(1).strip() if match else "")[:900]
    return (f"<h3>{esc(t('last_mirror', name=latest.name))}</h3><p class='legend'>{esc(title.group(1) if title else '')}</p>" +
            (f"<pre>{esc(body)}</pre>" if body else nd(t("mirror_no_blind_spots"))))


def objections_block() -> str:
    script = Path(__file__).resolve().parent / "critic_mirror.py"
    if not script.is_file():
        raise PasDeDonnees
    now = today()
    debut = now.replace(day=1)
    result = subprocess.run([sys.executable, str(script), "--since", debut.isoformat(), "--today", now.isoformat(),
                             "--language", t.language],
                            capture_output=True, text=True, timeout=60, env={**os.environ, "PMZILLA_LAB_WORKSPACE": str(WORKSPACE)})
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    if result.returncode != 0 or len(lines) < 2:
        raise PasDeDonnees
    match = re.search(r"(\d+) objection", lines[1])
    if not match:
        raise PasDeDonnees
    return t("mirror_objections", first=esc(fr_date(debut)), last=esc(fr_date(now)), n=match.group(1))


def section_critic() -> str:
    return "".join(safe(b) for b in (objections_block, miroir_block))


# --- page ------------------------------------------------------------------------------------

def safe(block) -> str:
    try:
        return block()
    except PasDeDonnees:
        return nd()
    except Exception as exc:  # une source illisible ne fait jamais échouer la page
        return nd(t("unreadable_source", error=type(exc).__name__))


def section_composants() -> str:
    """Le fichier d'état écrit par `composants.py check` (version 1) : jamais de réseau, jamais de lancement, jamais d'écriture."""
    state = json.loads(read_text(DATA / "composants-etat.json"))
    now = today()
    complete = state.get("last_complete")
    limite = dt.timedelta(weeks=state.get("stale_weeks") or 3)
    if complete:
        day = dt.date.fromisoformat(complete)
        stale = now - day > limite
        last = esc(fr_date(day)) + (f" {badge(t('components_stale'), 'warn')}" if stale else "")
    else:
        last = esc(t("components_never")) + f" {badge(t('components_stale'), 'warn')}"
    attempt = state.get("last_attempt")
    parts = [f'<p>{esc(t("components_last_complete"))} : {last}</p>']
    if attempt:
        parts.append(f'<p class="legend">{esc(t("components_last_attempt"))} : {esc(fr_date(dt.date.fromisoformat(attempt)))}</p>')
    if not state.get("complete", True):
        parts.append(f'<p>{badge(t("components_incomplete"), "warn")} {esc(pl(int(state.get("unreachable") or 0), "components_unreachable"))}</p>')
    rows, up_to_date = [], 0
    for name, comp in sorted((state.get("components") or {}).items()):
        novelties = comp.get("novelties") or []
        if not novelties and not comp.get("incomplete"):
            up_to_date += 1
        raw = list(comp.get("flags") or [])
        flags = [t(f"components_flag_{f}") if f"components_flag_{f}" in t.catalogs["fr"] else f for f in raw]
        if comp.get("pinned") is False:
            flags.append(t("components_not_pinned"))
            raw.append("not-pinned")
        for nov in novelties:
            nature = nov.get("nature", "")
            label = t(f"components_nature_{nature}") if f"components_nature_{nature}" in t.catalogs["fr"] else nature
            # la veille seule ne vaut que pour une version majeure : un correctif de la même ligne reste une mise à jour simple
            shown = [f for f, k in zip(flags, raw) if k != "major-watch-only" or nature == "major"]
            job = t("components_job", name=name, used=nov.get("used", ""), available=nov.get("available", ""))
            if comp.get("procedure"):
                job += f" ({comp['procedure']})"
            rows.append([esc(name), esc(nov.get("used", "")), esc(nov.get("available", "")), esc(label),
                         esc(", ".join(shown)), esc(job)])
    parts.append(f'<p>{badge(t("components_up_to_date", n=up_to_date), "ok")}</p>')
    heads = [t(f"components_head_{k}") for k in ("name", "used", "available", "nature", "flags", "job")]
    parts.append(table(heads, rows) if rows else nd(t("components_none_new")))
    return "".join(parts)


def section_experimentations() -> str:
    return safe(section_experiences)


SECTIONS = [("sante", "section_health", section_sante), ("a-faire", "section_todo", section_a_faire),
            ("experimentations", "section_experiments", section_experimentations), ("veille", "section_veille", section_veille),
            ("bibliotheque", "section_library", section_bibliotheque), ("qualite", "section_quality", section_qualite),
            ("flux", "section_flux", section_flux), ("critic", "section_critic", section_critic),
            ("composants", "section_components", section_composants)]

CSS = """
:root{--bg:#f7f6f2;--fg:#1d1d1b;--mut:#6b6a63;--card:#fff;--line:#dedcd3;--acc:#1f6f6b;--ok:#2b7a3d;--warn:#a85b00;--ko:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ececea;--mut:#9a998f;--card:#1f1f1d;--line:#34332f;--acc:#6fc2bd;--ok:#7fcf8f;--warn:#e0a35a;--ko:#f08a82}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header,main{max-width:980px;margin:0 auto;padding:16px}h1{font-size:1.6rem;margin:.4rem 0}nav a{margin-right:12px;color:var(--acc);text-decoration:none}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 18px;margin:16px 0}h2{margin:.2rem 0 .6rem;font-size:1.2rem}h3{font-size:1rem;margin:1rem 0 .3rem}
table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--mut);font-weight:600}
.nd,.legend{color:var(--mut);font-size:.88rem}.badge{display:inline-block;padding:1px 9px;border-radius:99px;border:1px solid var(--line);font-size:.82rem}
.badge.ok,.cell.ok{color:var(--ok)}.badge.warn{color:var(--warn)}.badge.ko,.cell.ko,.late td:first-child{color:var(--ko)}.cell{font-variant-numeric:tabular-nums}
.spark polyline{stroke:var(--acc);stroke-width:2.2}svg text{fill:var(--mut);font-size:11.5px}svg .axe{font-size:11px}.spark circle{fill:var(--acc)}.spark,.bars{width:100%;max-width:none;height:auto;display:block}.bars rect{fill:var(--acc)}
code,pre{font-family:ui-monospace,Menlo,monospace;font-size:.85rem}pre{white-space:pre-wrap;background:var(--bg);padding:8px;border-radius:6px;border:1px solid var(--line)}
@media (max-width:560px){header,main{padding:10px}section{padding:10px 12px}}
"""


def build(language: str = "fr") -> str:
    set_language(language)
    parts = []
    for key, title_key, fn in SECTIONS:
        parts.append(f'<section id="{key}"><h2>{esc(t(title_key))}</h2>{safe(fn)}</section>')
    nav = "".join(f'<a href="#{k}">{esc(t(title_key))}</a>' for k, title_key, _ in SECTIONS)
    now = dt.datetime.now().strftime(t("stamp_format"))
    return (f'<!doctype html><html lang="{t("html_lang")}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{esc(t('page_title'))}</title><style>{CSS}</style></head><body>"
            f"<header><h1>{esc(t('page_title'))}</h1><p class='legend'>{esc(t('page_generated', stamp=now, date=fr_date(today())))}</p><nav>{nav}</nav></header>"
            f"<main>{''.join(parts)}</main></body></html>")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tableau de bord de PMZilla Lab (une page HTML autonome)")
    parser.add_argument("--open", dest="ouvrir", action="store_true", help="ouvrir la page dans le navigateur")
    parser.add_argument("--output", dest="sortie", help="fichier de sortie (défaut : <dossier du lab>/tableau-de-bord.html)")
    add_language_option(parser)
    args = parser.parse_args(flux_config.refuse_old_options(sys.argv[1:] if argv is None else argv, flux_config.OPTIONS_COMMUNES))
    set_language(args.language)
    out = Path(args.sortie).expanduser() if args.sortie else OUT
    try:
        page = build(args.language)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        print(t("written", path=out))
        if args.ouvrir:
            subprocess.run(["open", str(out)], check=False)
    except Exception as exc:  # jamais d'échec visible pour veille.sh ou evals_auto.sh
        print(t("not_generated", error=type(exc).__name__), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
