# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PMZilla Lab : lecteur de la file de travail.

La file est dans les issues du dépôt privé (remote origin), lue par `gh` en lecture seule (change github-roadmap, design D14 à D16) :
`check`, `next --budget 2h [--milestone M]`, `batch --milestone M`, `status`, `board [--open]`, `show R-<n>` et `reminder --session-hook`. Un instantané de la
dernière lecture réussie est écrit dans le dossier de données (hors dépôt, $PMZILLA_LAB_DATA, défaut ~/.pmzilla-lab) et sert quand
GitHub est injoignable (code 5 sans instantané) ; `reminder` ne lit que lui. L'exécutable `gh` peut être remplacé par la variable
d'environnement PMZILLA_GH (tests). Code 0 : valide. Code 1 : une ligne par problème. Code 2 : usage.

`batch --milestone M [--today AAAA-MM-JJ]` (change batch-milestone, design D2, D3 et D5) propose les features prêtes d'un jalon qui sont
indépendantes : celles que `next` proposerait, retenues par rang sauf si leurs fichiers connus (chemins cités par le tasks.md et le
design.md de leur change non archivé) recoupent ceux d'une feature retenue mieux classée ou d'une feature `In progress`. Il donne pour
chacune la branche, le modèle de lancement et le genre de session (cadrage ou exécution), liste les écartées avec leur raison et les
fichiers partagés. Lecture seule, en direct seulement. Codes : 0 (liste éventuellement vide), 1 file invalide (une ligne par problème),
2 usage (jalon absent, inconnu ou fermé), 5 GitHub injoignable (`GitHub unreachable; a batch needs a live read`, instantané ou non).

Interdit à l'outil : écrire dans GitHub, réordonner la file, calculer une date autre que la comparaison avec aujourd'hui.
La date du jour peut être imposée avec --today AAAA-MM-JJ ou ROADMAP_TODAY (tests).

Exemple :
    uv run tools/roadmap.py check
"""
import argparse
import collections
import datetime
import html
import json
import os
import subprocess
import re
import sys
from pathlib import Path

import roadmap_model as rm
import identifiants_personnels

RACINE = Path(__file__).resolve().parents[1]
PREFIXE = "roadmap : "

ETATS = ("ready", "blocked", "in-progress", "done")
THEMES = ("fiabilite", "veille", "bibliotheque", "base", "cas", "postures", "edition", "outillage")   # R-57
INCONNUE = "inconnue"   # done_on d'un job fait dont la date n'a pas été retrouvée
NB_PRETS = 5


class Usage(Exception):
    pass


def duree(texte) -> int | None:
    """Minutes d'une durée `45min`, `2h` ou `1h30` ; None si mal formée ou nulle."""
    m = re.fullmatch(r"(\d+)min|(\d+)h(?:(\d{1,2}))?", str(texte).strip())
    if not m:
        return None
    total = int(m.group(1)) if m.group(1) is not None else int(m.group(2)) * 60 + int(m.group(3) or 0)
    return total if total > 0 else None


def affiche_duree(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h{m:02d}"
    return f"{h}h" if h else f"{m}min"


def est_date(v) -> bool:
    if isinstance(v, datetime.date):
        return True
    try:
        return isinstance(v, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)) and bool(datetime.date.fromisoformat(v))
    except ValueError:
        return False


def en_date(v) -> datetime.date:
    return v if isinstance(v, datetime.date) else datetime.date.fromisoformat(v)


def cycles(graphe: dict[str, list[str]], ids: set[str]) -> list[list[str]]:
    """Un cycle par composante fortement connexe de plus d'un job (algorithme de Tarjan)."""
    index, bas, pile, sur, comps, n = {}, {}, [], set(), [], [0]

    def visite(v):
        index[v] = bas[v] = n[0]
        n[0] += 1
        pile.append(v)
        sur.add(v)
        for w in graphe.get(v, []):
            if w not in ids or w == v:
                continue
            if w not in index:
                visite(w)
                bas[v] = min(bas[v], bas[w])
            elif w in sur:
                bas[v] = min(bas[v], index[w])
        if bas[v] == index[v]:
            comp = []
            while True:
                w = pile.pop()
                sur.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                comps.append(sorted(comp, key=lambda x: list(graphe).index(x)))

    for v in graphe:
        if v not in index:
            visite(v)
    return comps


def sortie_invalide(pb: list[str]) -> int:
    for p in pb:
        print(PREFIXE + p)
    return 1


def cmd_check(args) -> int:
    return cmd_check_github(args)


def aujourdhui(args) -> datetime.date:
    brut = args.today or os.environ.get("ROADMAP_TODAY")
    if not brut:
        return datetime.date.today()
    if not est_date(brut):
        raise Usage(f"date du jour mal formée : {brut}")
    return en_date(brut)


def selection(candidats: list, budget: int):
    """(retenus, longs, inconnus, total) : parcours dans l'ordre donné des jobs proposables, dans le budget en minutes."""
    reste, total = budget, 0
    retenus, longs, inconnus = [], [], []
    for j in candidats:
        if j["estimate"] == "tbd":
            inconnus.append(j)
            continue
        minutes = duree(j["estimate"])
        if minutes <= reste:
            reste -= minutes
            total += minutes
            retenus.append(j)
        else:
            longs.append(j)
    return retenus, longs, inconnus, total


def imprime_next(budget: int, retenus: list, longs: list, inconnus: list, total: int) -> None:
    def ligne(j):
        s = f"{j['id']} | {j['title']} | estimation {j['estimate']} | méthode {j['method']} | modèle {j['model']}"
        if j["conditions"]:
            s += f" | à confirmer : {j['conditions']}"
        if "due" in j:
            s += f" | échéance {en_date(j['due']).isoformat()}"
        return s

    print(f"{PREFIXE}budget {affiche_duree(budget)}")
    print(PREFIXE + "jobs proposés :" + ("" if retenus else " aucun"))
    for j in retenus:
        print(f"  {ligne(j)}")
    if longs:
        print(PREFIXE + "trop long pour le temps restant :")
        for j in longs:
            print(f"  {ligne(j)}")
    if inconnus:
        print(PREFIXE + "sans estimation (non comptés) :")
        for j in inconnus:
            print(f"  {ligne(j)}")
    print(f"{PREFIXE}total {affiche_duree(total) if total else '0min'}")


def cmd_next(args) -> int:
    budget = duree(args.budget)
    if budget is None:
        raise Usage(f"durée mal formée : {args.budget} (attendu 45min, 2h ou 1h30)")
    jour = aujourdhui(args)
    return cmd_next_github(args, budget, jour)


def vue(jobs: list, archives: list) -> dict:
    """Ce que montrent `status` et `board` : comptes, en cours, prochains prêts, bloqués, faits par semaine."""
    tous = jobs + archives
    etat = {j["id"]: j["state"] for j in tous}
    par_theme = {th: [0, 0] for th in THEMES}        # [faits, total]
    for j in tous:
        par_theme[j["theme"]][1] += 1
        par_theme[j["theme"]][0] += j["state"] == "done"
    prets = [j for j in jobs if j["state"] == "ready" and all(etat[d] == "done" for d in j["depends_on"])]
    semaines: dict = collections.Counter()
    for j in tous:
        if j["state"] == "done":
            fin = j.get("done_on", INCONNUE)
            if fin == INCONNUE:
                semaines[INCONNUE] += 1
            else:
                fin = en_date(fin)
                semaines[(fin - datetime.timedelta(days=fin.weekday())).isoformat()] += 1
    return {
        "etats": collections.Counter(j["state"] for j in tous),
        "themes": {th: v for th, v in par_theme.items() if v[1]},
        "en_cours": [j for j in jobs if j["state"] == "in-progress"],
        "prets": prets[:NB_PRETS],
        "bloques": [(j, [d for d in j["depends_on"] if etat[d] != "done"]) for j in jobs if j["state"] == "blocked"],
        "semaines": sorted(((s, n) for s, n in semaines.items() if s != INCONNUE), reverse=True),
        "inconnues": semaines[INCONNUE],
    }


def debut(j) -> str:
    return f"depuis {en_date(j['started_on']).isoformat()}" if "started_on" in j else "début inconnu"


def estimation(j) -> str:
    return f"estimation {j['estimate']}" + (f", pas avant {en_date(j['not_before']).isoformat()}" if "not_before" in j else "")


def attente(deps: list) -> str:
    return "attend " + ", ".join(deps) if deps else "dépendances faites, à passer ready si tu le décides"


def imprime_status(v: dict) -> None:
    print(PREFIXE + "par état : " + ", ".join(f"{e} {v['etats'][e]}" for e in ETATS))
    print(PREFIXE + "par thème (faits/total) :")
    for th, (faits, total) in v["themes"].items():
        print(f"  {th:<13}{faits}/{total}")
    for titre, liste, detail in (("en cours", v["en_cours"], debut),
                                 (f"{NB_PRETS} prochains prêts", v["prets"], estimation),
                                 ("bloqués", v["bloques"], None)):
        print(PREFIXE + titre + " :" + ("" if liste else " aucun"))
        for x in liste:
            j, info = (x[0], attente(x[1])) if detail is None else (x, detail(x))
            print(f"  {j['id']} | {j['title']} | {info}")


def cmd_status(args) -> int:
    return cmd_status_github(args)


STYLE = """:root{--fond:#fbfaf7;--texte:#1d1d1b;--doux:#6b6a65;--trait:#e3e1da;--plein:#2f6f5e;--vide:#e8e6df}
@media (prefers-color-scheme:dark){:root{--fond:#1b1b1a;--texte:#ecebe6;--doux:#a3a29c;--trait:#33322f;--plein:#5fb39b;--vide:#2c2b29}}
body{margin:0;background:var(--fond);color:var(--texte);font:15px/1.5 -apple-system,system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px}
p.doux,span.doux{color:var(--doux)}ul{list-style:none;padding:0;margin:0}li{padding:6px 0;border-bottom:1px solid var(--trait)}
.ligne{display:grid;grid-template-columns:110px 1fr 56px;gap:10px;align-items:center;padding:3px 0}
.barre{height:12px;background:var(--vide);border-radius:6px;overflow:hidden}.barre i{display:block;height:100%;background:var(--plein)}
code{font-size:13px}"""


def ligne_html(j, info: str) -> str:
    e = html.escape
    return f"<li><code>{e(j['id'])}</code> {e(j['title'])} <span class=\"doux\">{e(info)}</span></li>"


def page_board(v: dict, jour: datetime.date) -> str:
    e = html.escape
    bloc = [f"<!doctype html>\n<html lang=\"fr\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Feuille de route</title>"
            f"<style>{STYLE}</style></head><body><main>",
            "<h1>Feuille de route</h1>",
            f"<p class=\"doux\">Généré le {jour.isoformat()} par roadmap.py board · "
            + " · ".join(f"{e(s)} {v['etats'][s]}" for s in ETATS) + "</p>",
            "<h2>Avancement par thème</h2>"]
    for th, (faits, total) in v["themes"].items():
        bloc.append(f"<div class=\"ligne\"><span>{e(th)}</span><div class=\"barre\"><i style=\"width:{round(100 * faits / total)}%\">"
                    f"</i></div><span class=\"doux\">{faits}/{total}</span></div>")
    sections = (("En cours", [(j, debut(j)) for j in v["en_cours"]]),
                (f"{NB_PRETS} prochains prêts", [(j, estimation(j)) for j in v["prets"]]),
                ("Bloqués, et par quoi", [(j, attente(d)) for j, d in v["bloques"]]))
    for titre, liste in sections:
        bloc.append(f"<h2>{e(titre)}</h2>")
        bloc.append("<ul>" + "".join(ligne_html(j, info) for j, info in liste) + "</ul>" if liste else "<p class=\"doux\">aucun</p>")
    bloc.append("<h2>Fait par semaine</h2>")
    plus = max([n for _, n in v["semaines"]] + [1])
    for s, n in v["semaines"]:
        bloc.append(f"<div class=\"ligne\"><span>{e(s)}</span><div class=\"barre\"><i style=\"width:{round(100 * n / plus)}%\"></i>"
                    f"</div><span class=\"doux\">{n}</span></div>")
    if v["inconnues"]:
        bloc.append(f"<p class=\"doux\">{v['inconnues']} travaux faits à date inconnue.</p>")
    bloc.append("</main></body></html>\n")
    return "\n".join(bloc)


def dossier_donnees() -> Path:
    return Path(os.environ.get("PMZILLA_LAB_DATA", "~/.pmzilla-lab")).expanduser()


def ouvre(chemin: Path) -> None:
    subprocess.run(["open", str(chemin)], check=False)


def cmd_board(args) -> int:
    return cmd_board_github(args)


# --- Mode GitHub (change github-roadmap, design D14 à D16) ------------------------------------------------------------

REQUETE = (
    "query($owner:String!,$name:String!,$after:String){repository(owner:$owner,name:$name){"
    "milestones(first:100){nodes{title state}} "
    "issues(first:100,after:$after,orderBy:{field:CREATED_AT,direction:ASC}){pageInfo{hasNextPage endCursor}"
    "nodes{number title body state stateReason labels(first:30){nodes{name}} milestone{title state} parent{number} "
    "blockedBy(first:50){nodes{number}} projectItems(first:20){nodes{project{title} "
    "fieldValueByName(name:\"Status\"){... on ProjectV2ItemFieldSingleSelectValue{name}}}}}}}}"
)
PROJECT_TITLE = "PMZilla Lab roadmap"   # comme gh_issue.PROJECT_TITLE
TARASQUE = "Tarasque"
FICHIER_CACHE = "roadmap-cache.json"
CHEMIN_REGLAGES = RACINE / rm.SETTINGS_FILE
DELAI_GH = 60           # secondes par appel de gh (fiche W2), variable PMZILLA_GH_TIMEOUT
DELAI_GIT = 30
MESSAGE_ORIGIN = "usage: the origin remote is missing or is not a GitHub repository"


class Sortie(Exception):
    """Fin anticipée avec un code et un message sans préfixe (stderr)."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


class Injoignable(Exception):
    pass


def executable_gh() -> str:
    return os.environ.get("PMZILLA_GH") or "gh"


def message_refuse(texte: str) -> str:
    """Message d'erreur de GitHub, retenu s'il contient un identifiant personnel (propriétaire, dépôt, chemin)."""
    try:
        bas = texte.lower()
        trouve = any(i and i in bas for i in identifiants_personnels.identifiants(RACINE))
    except BaseException as e:
        if isinstance(e, KeyboardInterrupt):
            raise
        trouve = True
    if trouve:
        m = re.search(r"HTTP (\d{3})", texte)
        return f"GitHub refused: HTTP {m.group(1) if m else '?'} (message withheld)"
    return "GitHub refused: " + texte


def jour_reel() -> datetime.date:
    """Date réelle de la lecture (celle du cache), jamais --today ni ROADMAP_TODAY."""
    return datetime.date.today()


def delai_gh() -> float:
    """Délai par appel de gh : PMZILLA_GH_TIMEOUT (secondes, positif), sinon le défaut."""
    try:
        v = float(os.environ.get("PMZILLA_GH_TIMEOUT", ""))
    except ValueError:
        return DELAI_GH
    if not v > 0 or v == float("inf"):
        return DELAI_GH
    return int(v) if v == int(v) else v


def git_origin_url() -> str:
    """URL de `origin` (lecture seule, dans la racine du dépôt) ; chaîne vide si elle manque."""
    try:
        p = subprocess.run(["git", "-C", str(RACINE), "remote", "get-url", "origin"], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=DELAI_GIT, cwd=RACINE)
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def depot_origine() -> tuple[str, str]:
    """(propriétaire, dépôt) d'après `origin`, par la règle de l'outil d'écriture. Sortie 2 si absent ou hors GitHub."""
    repo = rm.repo_from_url(git_origin_url())
    if repo is None:
        raise Sortie(2, MESSAGE_ORIGIN)
    proprietaire, _, nom = repo.partition("/")
    return proprietaire, nom


def appelle_gh(args: list[str]) -> str:
    try:
        r = subprocess.run([executable_gh()] + args, capture_output=True, text=True, cwd=RACINE, timeout=delai_gh(),
                           stdin=subprocess.DEVNULL, env={**os.environ, "GH_PROMPT_DISABLED": "1"})
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Injoignable(str(e)) from None
    if r.returncode != 0:
        if "GraphQL:" in r.stderr:
            raise Sortie(1, message_refuse((r.stderr.strip().splitlines() or ["?"])[0][:200]))
        raise Injoignable(r.stderr.strip()[:200])
    return r.stdout


def normalise(noeud: dict) -> dict:
    statut = None
    for it in (noeud.get("projectItems") or {}).get("nodes") or []:
        if ((it or {}).get("project") or {}).get("title") != PROJECT_TITLE:
            continue
        v = (it or {}).get("fieldValueByName")
        if v and v.get("name"):
            statut = v["name"]
            break
    jalon = noeud.get("milestone")
    return {
        "number": noeud["number"], "title": noeud.get("title") or "", "body": noeud.get("body") or "",
        "state": (noeud.get("state") or "OPEN").lower(), "reason": (noeud.get("stateReason") or "").lower(),
        "labels": [l["name"] for l in (noeud.get("labels") or {}).get("nodes") or []],
        "milestone": {"title": jalon["title"], "state": (jalon.get("state") or "OPEN").lower()} if jalon else None,
        "parent": (noeud.get("parent") or {}).get("number"),
        "blocked_by": [b["number"] for b in (noeud.get("blockedBy") or {}).get("nodes") or []],
        "status": statut,
    }


def lecture_github(proprietaire: str, depot: str) -> tuple[list[dict], dict]:
    """(issues ouvertes et fermées, jalons {titre: état}), par lecture GraphQL seule. Injoignable si gh échoue."""
    issues, jalons, curseur = [], {}, None
    while True:
        cmd = ["api", "graphql", "-H", "GraphQL-Features: sub_issues", "-f", "query=" + REQUETE,
               "-F", f"owner={proprietaire}", "-F", f"name={depot}"]
        if curseur:
            cmd += ["-F", "after=" + curseur]
        try:
            rep = json.loads(appelle_gh(cmd))
        except ValueError:
            raise Injoignable("réponse illisible") from None
        if rep.get("errors"):
            raise Sortie(1, message_refuse(str(rep["errors"][0].get("message", "?"))[:200]))
        page = (((rep.get("data") or {}).get("repository") or {}).get("issues"))
        if page is None:
            raise Injoignable("réponse sans issues")
        if curseur is None:
            jalons = {j["title"]: (j.get("state") or "OPEN").lower()
                      for j in (((rep["data"]["repository"].get("milestones")) or {}).get("nodes")) or [] if j}
        issues += [normalise(n) for n in page["nodes"] if n]
        if not page["pageInfo"]["hasNextPage"]:
            return issues, jalons
        curseur = page["pageInfo"]["endCursor"]


def chemin_cache() -> Path:
    return dossier_donnees() / FICHIER_CACHE


def ecrit_cache(issues: list[dict], jour: datetime.date, jalons: dict | None = None) -> None:
    """Instantané de la dernière lecture réussie, hors dépôt. Une erreur d'écriture ne gêne pas la lecture."""
    try:
        chemin = chemin_cache()
        chemin.parent.mkdir(parents=True, exist_ok=True)
        tmp = chemin.with_name(chemin.name + ".tmp")
        tmp.write_text(json.dumps({"date": jour.isoformat(), "issues": issues, "milestones": jalons or {}},
                                            ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, chemin)
    except OSError:
        pass


def lit_cache():
    """(issues, date) de l'instantané, ou None s'il manque ou est illisible."""
    c = lit_cache_complet()
    return None if c is None else (c[0], c[1])


def lit_cache_complet():
    """(issues, date, jalons) de l'instantané, ou None. Un instantané ancien sans jalons les tire des issues."""
    try:
        d = json.loads(chemin_cache().read_text(encoding="utf-8"))
        issues = d["issues"]
        jalons = d.get("milestones")
        if not isinstance(jalons, dict) or not jalons:
            jalons = {i["milestone"]["title"]: i["milestone"]["state"] for i in issues if i.get("milestone")}
        return issues, d["date"], jalons
    except (OSError, ValueError, KeyError, TypeError):
        return None


def lecture_complete(args, banniere=print) -> tuple[list[dict], dict]:
    """(issues, jalons) en direct (instantané réécrit) ou, GitHub injoignable, depuis l'instantané avec sa ligne d'avertissement
    (`banniere`, sur la sortie standard par défaut). Le dépôt d'origine est résolu avant toute lecture, du réseau comme de l'instantané."""
    proprietaire, depot = depot_origine()
    jour = jour_reel()
    try:
        issues, jalons = lecture_github(proprietaire, depot)
    except Injoignable:
        cache = lit_cache_complet()
        if cache is None:
            raise Sortie(5, "GitHub unreachable and no cache") from None
        banniere(f"GitHub unreachable; read from the cache of {cache[1]}")
        return cache[0], cache[2]
    ecrit_cache(issues, jour, jalons)
    return issues, jalons


def lecture(args) -> list[dict]:
    return lecture_complete(args)[0]


def ident(i: dict) -> str:
    t = rm.parse_title(i["title"])
    return f"R-{t[0]}" if t else f"#{i['number']}"


def analyse_github(issues: list[dict]):
    """(features dans l'ordre du rang, sous-issues, problèmes). Un problème est « identifiant : champ : message »."""
    pb: list[str] = []
    issues = [i for i in issues if rm.LABEL_IDEA not in i["labels"]]     # une idée n'est pas dans la file (D7)
    par_num = {i["number"]: i for i in issues}
    feats: dict[str, dict] = {}
    sous: list[dict] = []
    for i in issues:
        labels, ouvert = i["labels"], i["state"] == "open"
        est_f, est_t = rm.LABEL_FEATURE in labels, rm.LABEL_TASK in labels
        nom = ident(i)
        if est_f and est_t:
            pb.append(f"{nom} : labels : {rm.LABEL_FEATURE} et {rm.LABEL_TASK} ensemble")
        if est_t or (not est_f and i["parent"] is not None):
            sous.append(i)
            continue
        if not est_f:
            pb.append(f"{nom} : labels : {rm.LABEL_FEATURE} ou {rm.LABEL_TASK} attendu")
            continue
        titre = rm.parse_title(i["title"])
        if titre is None:
            pb.append(f"{nom} : title : motif R-<n> {rm.SEP} <titre> attendu")
        cle = rm.parse_marker(i["body"])
        if cle is None:
            pb.append(f"{nom} : marker : marqueur d'identité absent ou mal formé")
        elif cle != nom:
            pb.append(f"{nom} : marker : {cle} différent de l'identifiant du titre")
        themes = [l for l in labels if l.startswith("theme:")]
        theme = themes[0].split(":", 1)[1] if len(themes) == 1 else None
        if len(themes) != 1:
            pb.append(f"{nom} : labels : exactement un label theme: attendu ({len(themes)} trouvés)")
        elif theme not in rm.THEMES:
            pb.append(f"{nom} : labels : thème inconnu {theme}")
        if i["milestone"] is None:
            pb.append(f"{nom} : milestone : jalon absent")
        bloc = None
        try:
            bloc = rm.parse_block(i["body"])
        except rm.BlockError as e:
            pb.append(f"{nom} : block : {e}")
        except ValueError:      # date impossible que YAML refuse de construire
            champs = [k for k, v in re.findall(r"^(\w+):[ \t]*(\S+)[ \t]*$", "\n".join(rm._FENCE.findall(i["body"])), re.M)
                      if k in rm.DATES and not est_date(v)]
            pb += [f"{nom} : {k} : date AAAA-MM-JJ attendue" for k in champs] or [f"{nom} : block : bloc roadmap illisible"]
        if bloc is not None:
            for p in rm.validate_block(bloc, is_open=ouvert, marker_key=nom if titre else None, theme_label=theme):
                pb.append(f"{nom} : {p}")
            e = bloc.get("estimate")
            if isinstance(e, str) and e != "tbd" and duree(e) is None and not any(p.startswith("estimate :") for p in pb[-8:]):
                pb.append(f"{nom} : estimate : durée non nulle attendue (45min, 2h, 1h30) ou tbd")
        if nom in feats:
            pb.append(f"{nom} : id : identifiant en double (#{feats[nom]['number']} et #{i['number']})")
            continue
        feats[nom] = {"id": nom, "number": i["number"], "title": titre[1] if titre else i["title"], "open": ouvert,
                      "status": i["status"], "milestone": (i["milestone"] or {}).get("title"), "block": bloc or {},
                      "blocker_numbers": i["blocked_by"], "issue": i}
    par_numero = {f["number"]: f for f in feats.values()}
    rangs: dict = collections.defaultdict(list)
    for f in feats.values():
        if f["open"] and isinstance(f["block"].get("rank"), int):
            rangs[f["block"]["rank"]].append(f["id"])
    for r, ids in rangs.items():
        if len(ids) > 1:
            for x in ids:
                pb.append(f"{x} : rank : rang {r} en double ({', '.join(ids)})")
    for f in feats.values():
        s = f["status"]
        if s is None:
            pb.append(f"{f['id']} : Status : absent du Project")
        elif s not in rm.STATUSES:
            pb.append(f"{f['id']} : Status : valeur inconnue {s}")
        elif f["open"] and s == "Done":
            pb.append(f"{f['id']} : Status : Done sur une feature ouverte")
        elif not f["open"] and s != "Done":
            pb.append(f"{f['id']} : Status : Done attendu sur une feature fermée, reçu {s}")
    graphe: dict[str, list[str]] = {}
    for f in feats.values():
        graphe[f["id"]] = []
        f["blockers"] = []
        for b in f["blocker_numbers"]:
            cible = par_numero.get(b)
            if cible is None:
                autre = par_num.get(b)
                pb.append(f"{f['id']} : blocked_by : dépendance inconnue ({ident(autre) if autre else '#' + str(b)} n'est pas une feature)")
            elif cible["id"] == f["id"]:
                pb.append(f"{f['id']} : blocked_by : bloquée par elle-même")
            else:
                graphe[f["id"]].append(cible["id"])
                f["blockers"].append(cible["id"])
    for f in feats.values():
        for b in f["blockers"]:
            bo = feats[b]["open"]
            if f["open"] and f["status"] in ("Ready", "In progress") and bo:
                pb.append(f"{f['id']} : Status : {f['status']} alors que {b} est ouverte")
            if not f["open"] and bo:
                pb.append(f"{f['id']} : state : fermée alors que {b} est ouverte")
    for cycle in cycles(graphe, set(graphe)):
        pb.append(f"{cycle[0]} : blocked_by : cycle {' -> '.join(cycle + [cycle[0]])}")
    for i in issues:
        j = i["milestone"]
        if j and j["state"] == "closed" and i["state"] == "open":
            pb.append(f"{ident(i)} : milestone : issue ouverte dans le jalon fermé {j['title']}")
    for f in feats.values():
        if f["open"] and f["milestone"] == TARASQUE:
            pb.append(f"{f['id']} : milestone : feature ouverte dans {TARASQUE}")
    for i in sous:
        cle = rm.parse_marker(i["body"]) or f"#{i['number']}"
        labels = i["labels"]
        if par_numero.get(i["parent"]) is None:
            pb.append(f"{cle} : parent : une feature est attendue")
        if rm.LABEL_TASK not in labels:
            pb.append(f"{cle} : labels : {rm.LABEL_TASK} attendu")
        modeles = [l for l in labels if l.startswith("model:")]
        for m in modeles:
            if m not in [rm.label_model(x) for x in rm.MODELS]:
                pb.append(f"{cle} : labels : modèle inconnu {m}")
        if len(modeles) + (rm.LABEL_USER in labels) != 1:
            pb.append(f"{cle} : labels : un seul label model: ou {rm.LABEL_USER}, pas les deux ni aucun")
    for f in feats.values():
        f["sous"] = [i for i in sous if i["parent"] == f["number"]]
    rang = lambda f: f["block"]["rank"] if isinstance(f["block"].get("rank"), int) else 10**9
    ordre = sorted(feats.values(), key=lambda f: (not f["open"], rang(f), f["number"]))
    return ordre, sous, pb


def etat_github(args):
    return analyse_github(lecture(args))


def probleme_release(jalons: dict) -> str | None:
    """Ligne `current_release : <raison>` si le réglage nomme un jalon absent, fermé ou Tarasque ; None sinon (D12)."""
    try:
        texte = CHEMIN_REGLAGES.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return "current_release : fichier de réglages illisible"
    try:
        nom = rm.parse_settings(texte)["current_release"]
    except ValueError as e:
        return f"current_release : {e}"
    if not nom:
        return None
    if nom == TARASQUE:
        return f"current_release : {TARASQUE} ne peut pas être la release courante"
    if nom not in jalons:
        return f"current_release : jalon inconnu {nom}"
    if jalons[nom] == "closed":
        return f"current_release : jalon fermé {nom}"
    return None


def en_job(f: dict) -> dict:
    """La feature sous la forme d'un job de la vue (`vue`, `page_board`) : l'état se déduit de l'ouverture et du Status (D2)."""
    b = f["block"]
    etat = "done" if not f["open"] else {"In progress": "in-progress", "Ready": "ready"}.get(f["status"], "blocked")
    j = {"id": f["id"], "title": f["title"], "theme": b.get("theme", "outillage"), "depends_on": list(f["blockers"]),
         "conditions": b.get("conditions") or "", "state": etat, "estimate": b.get("estimate", "tbd"),
         "method": b.get("method", "?"), "model": b.get("model", "tbd")}
    for k in ("not_before", "due", "started_on"):
        if k in b:
            j[k] = b[k]
    if b.get("done_on") not in (None, "unknown"):
        j["done_on"] = b["done_on"]
    return j


def vue_github(feats: list[dict]) -> dict:
    jobs = [en_job(f) for f in feats]
    return vue([j for j in jobs if j["state"] != "done"], [j for j in jobs if j["state"] == "done"])


def cmd_check_github(args) -> int:
    issues, jalons = lecture_complete(args)
    pb = analyse_github(issues)[2]
    release = probleme_release(jalons)
    if release:
        pb.append(release)
    if pb:
        return sortie_invalide(pb)
    print(PREFIXE + "file valide")
    return 0


# --- Lot d'un jalon (change batch-milestone, design D2, D3, D5) ----------------------------------------------------

ARBRE = RACINE      # arbre où lire les changes OpenSpec et vérifier les chemins connus (remplaçable par les tests)
COMMUNS = ("README.md", "docs/pmzilla/installation.md", "docs/pmzilla/application.md", "tests/run_all.sh", ".claude/settings.json")
INVITE_CADRAGE = ("Frame R-{n} as an OpenSpec change with the spec-writer agent: proposal, design, tasks, delta specs and "
                  "fiche-decisions.md with an empty decision column; run openspec validate --strict; commit on this branch; do not push.")


def change_existe(arbre: Path, nom) -> bool:
    return isinstance(nom, str) and bool(nom) and nom != "archive" and "/" not in nom and nom not in (".", "..") \
        and (arbre / "openspec" / "changes" / nom).is_dir()


def fichiers_connus(arbre: Path, nom: str) -> set[str]:
    """Chemins relatifs cités tels quels (entre apostrophes inverses) par le tasks.md et le design.md du change `nom` qui existent dans
    `arbre`, hors `openspec/` (D3). Un `/` final est ignoré ; un extrait avec espace, `..`, `/` ou `~` initial n'est pas un chemin."""
    trouves: set[str] = set()
    for fichier in ("tasks.md", "design.md"):
        try:
            texte = (arbre / "openspec" / "changes" / nom / fichier).read_text(encoding="utf-8")
        except OSError:
            continue
        for extrait in re.findall(r"`([^`\n]+)`", texte):
            chemin = extrait.rstrip("/") if extrait != "/" else extrait
            parts = chemin.split("/")
            if (not chemin or re.search(r"\s", chemin) or chemin.startswith(("/", "~")) or any(x in ("", ".", "..") for x in parts)
                    or parts[0] == "openspec"):
                continue
            if (arbre / chemin).exists():
                trouves.add(chemin)
    return trouves


def se_recoupent(a: str, b: str) -> bool:
    """Deux chemins se recoupent s'ils sont égaux ou si l'un est un dossier qui contient l'autre (D3)."""
    return a == b or b.startswith(a + "/") or a.startswith(b + "/")


def fichiers_en_commun(a: set[str], b: set[str]) -> bool:
    return any(se_recoupent(x, y) for x in a - set(COMMUNS) for y in b - set(COMMUNS))


def slug_branche(titre: str) -> str:
    return "-".join(rm.idea_slug(titre).split("-")[:4])


def lancement(f: dict) -> dict:
    """Branche, genre de session, modèle de lancement et invite d'une feature retenue, d'après la table de D5."""
    b, n = f["block"], f["id"].removeprefix("R-")
    if b.get("method") == "openspec" and not b.get("change"):
        return {"branche": f"chore/spec-r{n}", "genre": "cadrage", "modele": "opus", "invite": INVITE_CADRAGE.format(n=n)}
    if b.get("method") == "openspec":
        return {"branche": f"feat/{b['change']}", "genre": "exécution", "modele": "sonnet", "invite": f"/start {f['id']}"}
    modele = b.get("model")
    return {"branche": f"chore/r{n}-{slug_branche(f['title'])}", "genre": "exécution",
            "modele": modele if modele in ("opus", "sonnet", "haiku") else "sonnet", "invite": f"/start {f['id']}"}


def lot(feats: list[dict], jalon: str, jour: datetime.date, arbre: Path):
    """(retenues, écartées, partagés) : retenues = [(feature, lancement, fichiers connus ou None)], écartées = [(feature, raison)],
    partagés = {chemin: [identifiants]}."""
    ouvert = {f["id"]: f["open"] for f in feats}
    connus: dict[str, set[str] | None] = {}
    for f in feats:
        nom = f["block"].get("change")
        connus[f["id"]] = fichiers_connus(arbre, nom) if change_existe(arbre, nom) else None
    en_cours = [f for f in feats if f["open"] and f["status"] == "In progress" and connus[f["id"]] is not None]
    retenues, ecartees = [], []
    for f in feats:
        b = f["block"]
        if (not f["open"] or f["status"] != "Ready" or f["milestone"] != jalon or any(ouvert[x] for x in f["blockers"])
                or ("not_before" in b and en_date(b["not_before"]) > jour)):
            continue
        nom = b.get("change")
        if nom and connus[f["id"]] is None:
            ecartees.append((f, f"change {nom} introuvable"))
            continue
        if nom:
            contre = next((g for g in en_cours if fichiers_en_commun(connus[f["id"]], connus[g["id"]])), None)
            if contre:
                ecartees.append((f, f"fichiers communs avec {contre['id']} (en cours)"))
                continue
            contre = next((g for g, _, c in retenues if c is not None and fichiers_en_commun(connus[f["id"]], c)), None)
            if contre:
                ecartees.append((f, f"fichiers communs avec {contre['id']}"))
                continue
        retenues.append((f, lancement(f), connus[f["id"]]))
    partages = {}
    for chemin in COMMUNS:
        ids = [f["id"] for f, _, c in retenues if c is not None and chemin in c]
        if len(ids) > 1:
            partages[chemin] = ids
    return retenues, ecartees, partages


def release_courante() -> str:
    try:
        return rm.parse_settings(CHEMIN_REGLAGES.read_text(encoding="utf-8"))["current_release"]
    except (OSError, ValueError):
        return ""


def cmd_batch(args) -> int:
    jour = aujourdhui(args)
    proprietaire, depot = depot_origine()
    try:
        issues, jalons = lecture_github(proprietaire, depot)
    except Injoignable:
        raise Sortie(5, "GitHub unreachable; a batch needs a live read") from None
    ecrit_cache(issues, jour_reel(), jalons)
    if args.milestone not in jalons:
        raise Sortie(2, f"usage: unknown milestone {args.milestone}")
    if jalons[args.milestone] == "closed":
        raise Sortie(2, f"usage: closed milestone {args.milestone}")
    feats, _, pb = analyse_github(issues)
    release = probleme_release(jalons)
    if release:
        pb.append(release)
    if pb:
        return sortie_invalide(pb)
    retenues, ecartees, partages = lot(feats, args.milestone, jour, ARBRE)
    print(f"{PREFIXE}lot du jalon {args.milestone}")
    print(f"{PREFIXE}release courante : {release_courante() or 'aucune'}")
    if not retenues:
        print(f"{PREFIXE}retenues : aucune")
    else:
        print(f"{PREFIXE}retenues :")
    for f, l, c in retenues:
        b = f["block"]
        champs = [f["id"], f["title"], f"méthode {b.get('method', '?')}", f"modèle {b.get('model', 'tbd')}", f"branche {l['branche']}",
                  f"session {l['modele']}", l["genre"], "fichiers inconnus" if c is None else f"fichiers {len(c)}"]
        if b.get("conditions"):
            champs.append(f"à confirmer : {b['conditions']}")
        if b.get("due"):
            champs.append(f"échéance {b['due']}")
        print("  " + " | ".join(champs))
    if ecartees:
        print(f"{PREFIXE}écartées :")
        for f, raison in ecartees:
            print(f"  {f['id']} | {f['title']} | {raison}")
    if partages:
        print(f"{PREFIXE}fichiers partagés :")
        for chemin, ids in partages.items():
            print(f"  {chemin} | {', '.join(ids)}")
    return 0


def cmd_next_github(args, budget: int, jour: datetime.date) -> int:
    feats, _, pb = etat_github(args)
    if pb:
        return sortie_invalide(pb)
    ouvert = {f["id"]: f["open"] for f in feats}
    candidats = []
    for f in feats:
        b = f["block"]
        if not f["open"] or f["status"] != "Ready" or any(ouvert[x] for x in f["blockers"]):
            continue
        if args.milestone and f["milestone"] != args.milestone:
            continue
        if "not_before" in b and en_date(b["not_before"]) > jour:
            continue
        candidats.append(en_job(f))
    imprime_next(budget, *selection(candidats, budget))
    return 0


def cmd_status_github(args) -> int:
    feats, _, pb = etat_github(args)
    if pb:
        return sortie_invalide(pb)
    imprime_status(vue_github(feats))
    return 0


def cmd_board_github(args) -> int:
    feats, _, pb = etat_github(args)
    if pb:
        return sortie_invalide(pb)
    sortie = dossier_donnees() / "feuille-de-route.html"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(page_board(vue_github(feats), aujourdhui(args)), encoding="utf-8")
    print(f"{PREFIXE}tableau écrit : {sortie.name}")
    if args.open:
        ouvre(sortie)
    return 0


def cmd_show(args) -> int:
    feats, _, pb = etat_github(args)
    f = next((x for x in feats if x["id"] == args.id), None)
    if f is None:
        print(f"{PREFIXE}{args.id} : id : identifiant inconnu")
        return 1
    mal = [p for p in pb if p.startswith(f"{args.id} : ")]
    if mal:
        return sortie_invalide(mal)
    b = f["block"]
    print(f"{PREFIXE}{f['id']} {rm.SEP} {f['title']}")
    print(f"{PREFIXE}état : {'ouverte' if f['open'] else 'fermée'} | Status : {f['status']} | jalon : {f['milestone']}")
    print(f"{PREFIXE}estimation {b['estimate']} | méthode {b['method']} | modèle {b['model']}"
          + (f" | rang {b['rank']}" if "rank" in b else ""))
    print(f"{PREFIXE}conditions : {b['conditions'] or 'aucune'}")
    for k in ("not_before", "due", "started_on", "done_on", "change"):
        if k in b:
            print(f"{PREFIXE}{k} : {b[k]}")
    ouvert = {x["id"]: x["open"] for x in feats}
    bloqueurs = [f"{x} ({'ouverte' if ouvert[x] else 'fermée'})" for x in f["blockers"]]
    print(f"{PREFIXE}bloquée par : {', '.join(bloqueurs) if bloqueurs else 'aucune'}")
    print(f"{PREFIXE}sous-issues :" + ("" if f["sous"] else " aucune"))
    for s in sorted(f["sous"], key=lambda i: i["number"]):
        print(f"  {rm.parse_marker(s['body']) or '#' + str(s['number'])} | {s['title']} | {'ouverte' if s['state'] == 'open' else 'fermée'}")
    texte = rm._FENCE.sub("", re.sub(r"\A<!-- roadmap-id: \S+ -->", "", f["issue"]["body"])).strip()
    if texte:
        print(PREFIXE + "description :")
        print(texte)
    return 0


def lignes_notes(feats: list[dict]) -> list[str]:
    """Lignes Markdown des notes : un `## <thème>` par thème, ordre alphabétique ; sous lui, `- <titre>` par done_on puis identifiant."""
    par_theme: dict[str, list] = collections.defaultdict(list)
    for i in feats:
        themes = [l.split(":", 1)[1] for l in i["labels"] if l.startswith("theme:")]
        try:
            fait = rm.parse_block(i["body"]).get("done_on")
        except (rm.BlockError, ValueError):
            fait = None
        fait = fait.isoformat() if isinstance(fait, datetime.date) else (fait if est_date(fait) else "9999-99-99")
        t = rm.parse_title(i["title"])
        par_theme[themes[0] if themes else "none"].append((fait, t[0] if t else 10**9, i["number"], t[1] if t else i["title"]))
    lignes: list[str] = []
    for theme in sorted(par_theme):
        lignes += (["" ] if lignes else []) + [f"## {theme}", ""]
        lignes += [f"- {x[3]}" for x in sorted(par_theme[theme], key=lambda x: x[:3])]
    return lignes


def cmd_release_notes(args) -> int:
    """Notes de release d'un jalon (D5) : features fermées comme terminées, en Markdown sur la sortie standard, rien d'écrit."""
    def avertit(texte):
        print(PREFIXE + texte, file=sys.stderr)

    issues, jalons = lecture_complete(args, banniere=avertit)
    if args.milestone not in jalons:
        raise Sortie(2, f"usage: unknown milestone {args.milestone}")
    du_jalon = [i for i in issues if (i["milestone"] or {}).get("title") == args.milestone]
    types = (rm.LABEL_FEATURE, rm.LABEL_TASK, rm.LABEL_IDEA)
    feats = [i for i in du_jalon if rm.LABEL_FEATURE in i["labels"] and rm.LABEL_IDEA not in i["labels"]
             and rm.LABEL_TASK not in i["labels"]]
    faites = [i for i in feats if i["state"] == "closed" and i.get("reason", "completed") in ("completed", "")]
    ouvertes = [i for i in feats if i["state"] == "open"]
    privees = 0
    if getattr(args, "public", False):
        privees = sum(1 for i in faites if rm.LABEL_EDITION_PUBLIC not in i["labels"])
        faites = [i for i in faites if rm.LABEL_EDITION_PUBLIC in i["labels"]]
    sans_type = sorted(i["number"] for i in du_jalon if not any(l in types for l in i["labels"]))
    texte = "\n".join(lignes_notes(faites)) + "\n" if faites else ""
    if texte:
        import gh_issue     # le garde de l'outil d'écriture, réutilisé tel quel
        try:
            gh_issue.Guard.load().scan({"notes": texte})
        except gh_issue.Stop as e:
            raise Sortie(e.code, e.lines[0].replace("; nothing was sent", "; nothing was printed")) from None
    if ouvertes:
        avertit(f"not listed: {len(ouvertes)} open feature(s)")
    if sans_type:
        avertit("not listed: issues without a type label: " + ", ".join(f"#{n}" for n in sans_type))
    if privees:
        avertit(f"not listed: {privees} closed feature(s) without {rm.LABEL_EDITION_PUBLIC}")
    if not faites:
        avertit(f"no closed feature in {args.milestone}")
    sys.stdout.write(texte)
    return 0


def cmd_reminder(args) -> int:
    """Une ligne lue dans l'instantané, jamais le réseau ; rien sans instantané ; toujours le code 0."""
    cache = lit_cache()
    if cache is None:
        return 0
    try:
        feats = analyse_github(cache[0])[0]
        prets = sum(1 for f in feats if f["open"] and f["status"] == "Ready")
        en_cours = sum(1 for f in feats if f["open"] and f["status"] == "In progress")
        print(f"roadmap: {prets} ready, {en_cours} in progress (cache of {cache[1]})")
    except Exception:
        pass
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="roadmap.py", description="Lecteur de la file de travail.")
    sub = p.add_subparsers(dest="cmd", required=True)
    for nom in ("check", "next", "batch", "status", "board", "show", "reminder", "release-notes"):
        s = sub.add_parser(nom)
        if nom in ("release-notes", "batch"):
            s.add_argument("--milestone", required=True)
        if nom == "release-notes":
            s.add_argument("--public", action="store_true")
        if nom == "next":
            s.add_argument("--budget", required=True)
            s.add_argument("--milestone", default=None)
        if nom in ("next", "batch", "board", "check", "status", "show"):
            s.add_argument("--today", default=None)
        if nom == "show":
            s.add_argument("id")
        if nom == "board":
            s.add_argument("--open", action="store_true")
        if nom == "reminder":
            s.add_argument("--session-hook", action="store_true")
    try:
        args = p.parse_args(argv)
        return {"check": cmd_check, "next": cmd_next, "status": cmd_status,
                "board": cmd_board, "show": cmd_show, "reminder": cmd_reminder,
                "release-notes": cmd_release_notes, "batch": cmd_batch}[args.cmd](args)
    except Usage as e:
        print(PREFIXE + str(e), file=sys.stderr)
        return 2
    except Sortie as e:
        print(str(e), file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
