# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PMZilla Lab : lecteur de la file de travail (docs/pmzilla/feuille-de-route.md).

Le document contient de la prose libre et exactement un bloc YAML clôturé dont la clé `jobs` est la file ordonnée
(l'ordre est la priorité). Format et règles : openspec/changes/workflow-tooling/design.md, D7.

    uv run tools/roadmap.py check [--file CHEMIN]
        Code 0 : file valide. Code 1 : une ligne par problème (identifiant du job, champ). Code 2 : usage ou fichier absent.

    uv run tools/roadmap.py next --budget 2h [--file CHEMIN]
        Propose, dans l'ordre de la file, les jobs prêts qui tiennent dans le temps donné. Code 1 : file invalide. Code 2 : durée mal formée.

    uv run tools/roadmap.py done R-3 [--file CHEMIN]
        Passe le job à `done` (seule sa ligne d'état change) et liste les jobs débloqués. Code 1 : file invalide ou identifiant inconnu.
        Un identifiant déjà archivé répond qu'il est archivé (code 0).

    uv run tools/roadmap.py archive [--dry-run] [--file CHEMIN]
        Déplace vers l'archive (feuille-de-route-archive.md, à côté de la file) chaque job `done` dont aucun job non `done` ne
        dépend : son entrée YAML et son paragraphe de « Travaux décrits », mot pour mot, en tête de l'archive (créée au besoin).
        Idempotente. --dry-run liste seulement. Code 1 : file invalide avant ou après le déplacement (rien n'est écrit après).

L'archive a le même format que la file (un bloc YAML `jobs` et des descriptions) et ne contient que des jobs `done`. `check`, `next`
et `done` la lisent pour résoudre les dépendances : un identifiant archivé compte comme `done`, et les identifiants sont uniques
sur les deux fichiers.

Interdit à l'outil : écrire autre chose que l'état du job donné à `done` et les déplacements de `archive`, réordonner la file,
calculer une date autre que la comparaison avec aujourd'hui. La date du jour peut être imposée avec --today AAAA-MM-JJ ou ROADMAP_TODAY (tests).
"""
import argparse
import datetime
import os
import re
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[1]
DOCUMENT = RACINE / "docs" / "pmzilla" / "feuille-de-route.md"
PREFIXE = "roadmap : "

ETATS = ("ready", "blocked", "in-progress", "done")
METHODES = ("openspec", "direct-prompt")
MODELES = ("opus", "sonnet", "haiku", "tbd")      # décision R-16 du 2026-10-10 : alias de /model, ou tbd
REQUIS = ("id", "title", "depends_on", "conditions", "state", "estimate", "method", "model")
OPTIONNELS = ("not_before", "due", "change")
RE_ID = re.compile(r"^R-\d+$")
RE_BLOC = re.compile(r"^```[ \t]*(?:ya?ml)[ \t]*$", re.I)
RE_FIN = re.compile(r"^```[ \t]*$")
RE_DESCRIPTION = re.compile(r"^\*\*(R-\d+)\b")


class ChargeurTexte(yaml.SafeLoader):
    """Les dates restent du texte : une date impossible est signalée par job et par champ, pas par une erreur de lecture."""


ChargeurTexte.add_constructor("tag:yaml.org,2002:timestamp", lambda c, n: c.construct_scalar(n))


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


def blocs_yaml(lignes: list[str]) -> list[tuple[int, int]]:
    """(première, dernière) lignes de contenu de chaque bloc YAML clôturé (indices de ligne, 0 pour la première)."""
    blocs, debut, autre = [], None, False
    for i, l in enumerate(lignes):
        if debut is None and not autre:
            if RE_BLOC.match(l):
                debut = i + 1
            elif l.startswith("```"):
                autre = True
        elif debut is not None and RE_FIN.match(l):
            blocs.append((debut, i - 1))
            debut = None
        elif autre and RE_FIN.match(l):
            autre = False
    return blocs


def analyse(texte: str):
    """(jobs, problèmes, lignes, bloc) d'un texte, sans la vérification de cohérence."""
    lignes = texte.split("\n")
    blocs = blocs_yaml(lignes)
    if len(blocs) != 1:
        return None, [f"document : {len(blocs)} bloc(s) YAML, un seul attendu"], lignes, None
    d, f = blocs[0]
    try:
        donnees = yaml.load("\n".join(lignes[d:f + 1]), Loader=ChargeurTexte)
    except yaml.YAMLError:
        return None, ["document : bloc YAML illisible"], lignes, blocs[0]
    if not isinstance(donnees, dict) or not isinstance(donnees.get("jobs"), list):
        return None, ["document : la clé jobs doit contenir une liste"], lignes, blocs[0]
    return donnees["jobs"], [], lignes, blocs[0]


def chemin_archive(chemin: Path) -> Path:
    return chemin.with_name(chemin.stem + "-archive" + chemin.suffix)


def charge_textes(texte: str, texte_archive: str | None):
    """(jobs, problèmes, lignes, bloc, archives). La cohérence est vérifiée sur la file et l'archive réunies."""
    jobs, pb, lignes, bloc = analyse(texte)
    if jobs is None:
        return None, pb, lignes, bloc, []
    archives: list = []
    if texte_archive is not None:
        a, pba, _, _ = analyse(texte_archive)
        if a is None:
            return None, ["archive : " + p for p in pba], lignes, bloc, []
        archives = a
    return jobs, verifie(jobs, archives), lignes, bloc, archives


def charge(chemin: Path):
    """(jobs, problèmes, lignes, bloc, archives). Les problèmes sont des chaînes déjà formatées sans préfixe."""
    arch = chemin_archive(chemin)
    return charge_textes(chemin.read_text(encoding="utf-8"), arch.read_text(encoding="utf-8") if arch.is_file() else None)


def est_date(v) -> bool:
    if isinstance(v, datetime.date):
        return True
    try:
        return isinstance(v, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)) and bool(datetime.date.fromisoformat(v))
    except ValueError:
        return False


def en_date(v) -> datetime.date:
    return v if isinstance(v, datetime.date) else datetime.date.fromisoformat(v)


def verifie(file: list, archives: list = ()) -> list[str]:
    """Problèmes de la file et de l'archive réunies : l'archive ne tient que des jobs `done`, les identifiants sont uniques sur les deux."""
    jobs = list(file) + list(archives)
    pb: list[str] = []
    ids: dict[str, dict] = {}
    for a in archives:
        if isinstance(a, dict) and a.get("state") != "done":
            pb.append(f"{a.get('id', '?')} : state : l'archive ne contient que des jobs done")
    for rang, j in enumerate(jobs, 1):
        if not isinstance(j, dict):
            pb.append(f"job n°{rang} : format : un job doit être une table")
            continue
        jid = j.get("id") if isinstance(j.get("id"), str) else f"n°{rang}"
        for c in REQUIS:
            if c not in j or j[c] is None and c not in ("conditions",):
                pb.append(f"{jid} : {c} : champ obligatoire absent")
        for c in j:
            if c not in REQUIS and c not in OPTIONNELS:
                pb.append(f"{jid} : {c} : champ inconnu")
        if "id" in j:
            if not isinstance(j["id"], str) or not RE_ID.match(j["id"]):
                pb.append(f"{jid} : id : attendu R- suivi de chiffres")
            elif j["id"] in ids:
                pb.append(f"{jid} : id : identifiant en double")
            else:
                ids[j["id"]] = j
        if "title" in j and not (isinstance(j["title"], str) and j["title"].strip()):
            pb.append(f"{jid} : title : texte non vide attendu")
        if "conditions" in j and j["conditions"] is not None and not isinstance(j["conditions"], str):
            pb.append(f"{jid} : conditions : texte attendu")
        if "depends_on" in j and not (isinstance(j["depends_on"], list) and all(isinstance(x, str) for x in j["depends_on"])):
            pb.append(f"{jid} : depends_on : liste d'identifiants attendue")
        if "state" in j and j["state"] not in ETATS:
            pb.append(f"{jid} : state : valeur hors de {', '.join(ETATS)}")
        if "method" in j and j["method"] not in METHODES:
            pb.append(f"{jid} : method : valeur hors de {', '.join(METHODES)}")
        if "estimate" in j and j["estimate"] != "tbd" and duree(j["estimate"]) is None:
            pb.append(f"{jid} : estimate : durée (45min, 2h, 1h30) ou tbd attendue")
        if "model" in j and j["model"] not in MODELES:
            pb.append(f"{jid} : model : valeur hors de {', '.join(MODELES)}")
        for c in ("not_before", "due"):
            if c in j and not est_date(j[c]):
                pb.append(f"{jid} : {c} : date AAAA-MM-JJ attendue")
        if "change" in j and not (isinstance(j["change"], str) and j["change"].strip()):
            pb.append(f"{jid} : change : nom de change attendu")
    # dépendances, cycles, cohérence des états
    graphe: dict[str, list[str]] = {}
    for jid, j in ids.items():
        deps = j.get("depends_on") if isinstance(j.get("depends_on"), list) else []
        graphe[jid] = [d for d in deps if isinstance(d, str)]
        for d in graphe[jid]:
            if d not in ids:
                pb.append(f"{jid} : depends_on : dépendance inconnue {d}")
            elif d == jid:
                pb.append(f"{jid} : depends_on : dépend de lui-même")
    for jid, j in ids.items():
        for d in graphe[jid]:
            if d in ids and d != jid:
                if j.get("state") == "ready" and ids[d].get("state") != "done":
                    pb.append(f"{jid} : state : prêt (ready) alors que {d} n'est pas done")
                if j.get("state") == "done" and ids[d].get("state") != "done":
                    pb.append(f"{jid} : state : done alors que {d} n'est pas done")
    for cycle in cycles(graphe, set(ids)):
        pb.append(f"{cycle[0]} : depends_on : cycle de dépendances {' -> '.join(cycle + [cycle[0]])}")
    return pb


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


def lit(chemin: Path):
    if not chemin.is_file():
        raise Usage(f"fichier absent : {chemin}")
    return charge(chemin)


def sortie_invalide(pb: list[str]) -> int:
    for p in pb:
        print(PREFIXE + p)
    return 1


def cmd_check(args) -> int:
    _, pb, _, _, _ = lit(Path(args.file))
    if pb:
        return sortie_invalide(pb)
    print(PREFIXE + "file valide")
    return 0


def aujourdhui(args) -> datetime.date:
    brut = args.today or os.environ.get("ROADMAP_TODAY")
    if not brut:
        return datetime.date.today()
    if not est_date(brut):
        raise Usage(f"date du jour mal formée : {brut}")
    return en_date(brut)


def cmd_next(args) -> int:
    budget = duree(args.budget)
    if budget is None:
        raise Usage(f"durée mal formée : {args.budget} (attendu 45min, 2h ou 1h30)")
    jour = aujourdhui(args)
    jobs, pb, _, _, archives = lit(Path(args.file))
    if pb:
        return sortie_invalide(pb)
    etat = {j["id"]: j["state"] for j in jobs + archives}
    reste, total = budget, 0
    retenus, longs, inconnus = [], [], []
    for j in jobs:
        if j["state"] != "ready" or any(etat[d] != "done" for d in j["depends_on"]):
            continue
        if "not_before" in j and en_date(j["not_before"]) > jour:
            continue
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
    return 0


def cmd_done(args) -> int:
    chemin = Path(args.file)
    jobs, pb, lignes, bloc, archives = lit(chemin)
    if pb:
        return sortie_invalide(pb)
    if args.id in {j["id"] for j in archives}:
        print(f"{PREFIXE}{args.id} : déjà archivé")
        return 0
    if args.id not in {j["id"] for j in jobs}:
        print(f"{PREFIXE}{args.id} : id : identifiant inconnu")
        return 1
    d, f = bloc
    racine = yaml.compose("\n".join(lignes[d:f + 1]))
    ligne_etat = None
    liste = next(v for k, v in racine.value if k.value == "jobs")
    for item in liste.value:
        champs = {k.value: v for k, v in item.value}
        if champs["id"].value == args.id:
            ligne_etat = d + champs["state"].start_mark.line
    if ligne_etat is None:
        print(f"{PREFIXE}{args.id} : state : ligne d'état introuvable")
        return 1
    nouvelle, nb = re.subn(r"^(\s*(?:-\s+)?state\s*:\s*)(\"[^\"]*\"|'[^']*'|[^\s#]+)", r"\g<1>done", lignes[ligne_etat], count=1)
    if nb != 1:
        print(f"{PREFIXE}{args.id} : state : ligne d'état non modifiable (forme inattendue)")
        return 1
    lignes[ligne_etat] = nouvelle
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    etat = {j["id"]: j["state"] for j in jobs + archives}
    etat[args.id] = "done"
    debloques = [j["id"] for j in jobs if etat[j["id"]] != "done" and j["depends_on"] and args.id in j["depends_on"]
                 and all(etat[x] == "done" for x in j["depends_on"])]
    print(f"{PREFIXE}{args.id} : state : done")
    if debloques:
        print(PREFIXE + "jobs dont toutes les dépendances sont done (à passer ready si tu le décides) : " + ", ".join(debloques))
    return 0


def paragraphes_decrits(lignes: list[str], limite: int) -> list[tuple[int, int]]:
    """(début, fin exclue) de chaque paragraphe `**R-n …` avant la ligne `limite` : il court jusqu'au suivant, à un titre ou à la limite."""
    debuts = [i for i in range(limite) if RE_DESCRIPTION.match(lignes[i])]
    plages = []
    for i in debuts:
        fin = next((k for k in range(i + 1, limite) if RE_DESCRIPTION.match(lignes[k]) or lignes[k].startswith("#")), limite)
        plages.append((i, fin))
    return plages


def insere_archive(texte: str | None, nom: str, items: list[str], descriptions: list[str]) -> str:
    """Texte de l'archive avec les entrées YAML et les descriptions en tête ; l'archive est créée si `texte` est None."""
    if texte is None:
        return ("# Feuille de route : archive\n\n"
                f"Travaux terminés dont aucun travail ouvert ne dépend, déplacés tels quels de {nom} par `tools/roadmap.py archive`.\n\n"
                "## Travaux décrits\n\n" + "\n".join(descriptions) + "\n```yaml\njobs:\n" + "\n".join(items) + "\n```\n")
    lignes = texte.split("\n")
    d, f = blocs_yaml(lignes)[0]
    liste = next(v for k, v in yaml.compose("\n".join(lignes[d:f + 1])).value if k.value == "jobs")
    if liste.value:
        lignes[d + liste.value[0].start_mark.line:d + liste.value[0].start_mark.line] = items
    else:
        lignes[d:f + 1] = ["jobs:"] + items
    existants = paragraphes_decrits(lignes, d - 1)
    point = existants[0][0] if existants else d - 1
    lignes[point:point] = descriptions
    return "\n".join(lignes)


def cmd_archive(args) -> int:
    chemin = Path(args.file)
    arch = chemin_archive(chemin)
    jobs, pb, lignes, bloc, archives = lit(chemin)
    if pb:
        return sortie_invalide(pb)
    attendus = {d for j in jobs if j["state"] != "done" for d in j["depends_on"]}
    partants = [j for j in jobs if j["state"] == "done" and j["id"] not in attendus]
    if not partants:
        print(PREFIXE + "rien à archiver")
        return 0
    if args.dry_run:
        print(PREFIXE + "partirait vers l'archive :")
        for j in partants:
            print(f"  {j['id']} | {j['title']}")
        return 0
    ids = {j["id"] for j in partants}
    d, f = bloc
    liste = next(v for k, v in yaml.compose("\n".join(lignes[d:f + 1])).value if k.value == "jobs")
    debuts = [d + item.start_mark.line for item in liste.value] + [f + 1]
    morceaux, retire = [], set()
    for n, item in enumerate(liste.value):
        if {k.value: v for k, v in item.value}["id"].value in ids:
            morceaux.append(lignes[debuts[n]:debuts[n + 1]])
            retire.update(range(debuts[n], debuts[n + 1]))
    textes = []
    for debut, fin in paragraphes_decrits(lignes, d - 1):
        if RE_DESCRIPTION.match(lignes[debut]).group(1) in ids:
            textes.append(lignes[debut:fin])
            retire.update(range(debut, fin))
    restantes = [l for i, l in enumerate(lignes) if i not in retire]
    if len(morceaux) == len(liste.value):
        k = d - sum(1 for i in retire if i < d)
        restantes[k] = re.sub(r"^(\s*jobs\s*:).*$", r"\g<1> []", restantes[k])
    nouveau_texte = "\n".join(restantes)
    texte_archive = insere_archive(arch.read_text(encoding="utf-8") if arch.is_file() else None, chemin.name,
                                   [l for m in morceaux for l in m], [l for t in textes for l in (t if t[-1] == "" else t + [""])])
    apres = charge_textes(nouveau_texte, texte_archive)[1]
    if apres:
        print(PREFIXE + "la file serait invalide après le déplacement, rien n'est écrit :")
        return sortie_invalide(apres)
    arch.write_text(texte_archive, encoding="utf-8")
    chemin.write_text(nouveau_texte, encoding="utf-8")
    print(f"{PREFIXE}{len(partants)} travaux archivés vers {arch.name} :")
    for j in partants:
        print(f"  {j['id']} | {j['title']}")
    print(f"{PREFIXE}{len(jobs) - len(partants)} travaux restent dans la file")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="roadmap.py", description="Lecteur de la file de travail.")
    sub = p.add_subparsers(dest="cmd", required=True)
    for nom in ("check", "next", "done", "archive"):
        s = sub.add_parser(nom)
        s.add_argument("--file", default=str(DOCUMENT))
        if nom == "archive":
            s.add_argument("--dry-run", action="store_true")
        if nom == "next":
            s.add_argument("--budget", required=True)
            s.add_argument("--today", default=None)
        if nom == "done":
            s.add_argument("id")
    try:
        args = p.parse_args(argv)
        return {"check": cmd_check, "next": cmd_next, "done": cmd_done, "archive": cmd_archive}[args.cmd](args)
    except Usage as e:
        print(PREFIXE + str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
