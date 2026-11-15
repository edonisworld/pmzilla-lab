#!/usr/bin/env python3
"""PMZilla Lab : pilotage de plusieurs sessions en parallèle (change multi-session-piloting, job R-75, design D1 à D4 et D6).

    uv run tools/pilot.py [--language fr|en] status
    uv run tools/pilot.py [--language fr|en] freeze --check
    uv run tools/pilot.py [--language fr|en] freeze --wait <minutes>
    uv run tools/pilot.py [--language fr|en] note <branche> "<texte>"
    uv run tools/pilot.py [--language fr|en] note <branche> --clear

`status` liste, depuis Git à chaque appel (jamais un registre), le dépôt et chaque worktree lié autre que le dossier d'exécution :
dossier (relatif au dossier du lab), branche, lien (R-<n> d'après le nom de la branche, `change <nom>` suivi de la feature que
l'instantané du lecteur de la file nomme pour ce change), état (propre ou nombre de fichiers modifiés), avance et retard sur main, âge
du dernier commit, processus qui ont leur dossier courant dans le worktree (occupé, libre, inconnu), « fusionnée, à retirer » et la note
de passage de relais ; puis le verrou de fin de branche et le dossier d'exécution. Aucun chemin absolu, aucun nom de fichier, aucun
numéro de processus n'est affiché. Hors ligne : ni réseau, ni `gh`. Change autonomous-trains-observe (D9) : sur la ligne d'un worktree dont la
branche est dans la liste prête, `prête (valide)` ou `prête (écartée : <raison>)` ; après la ligne du verrou de fin, une ligne « train
automatique » (dernier passage, arrêt actif ou absent). Les deux viennent des fonctions de service de tools/train_ready.py et
tools/train_auto.py ; sans fichier de train dans le dossier de données, la sortie est inchangée.

`freeze --check` rend 0 quand aucune fin de branche ne tient le verrou, quand l'appelant porte son jeton (FINISH_LOCK_TOKEN) ou quand la liste du
verrou (gel ciblé, autonomous-trains-merge D18, finish_lock.freeze_scope() par finish_lock.freezes(), règle unique des quatre lecteurs) ne nomme pas
le worktree du dossier courant (ligne « pilot : fin en cours : <n> worktree(s) gelé(s), main, dossier d'exécution et liste prête ») ; 4 quand un verrou
vivant sans le jeton de l'appelant nomme son worktree ou n'a pas de liste lisible (échec fermé), et, pendant un train, dans l'espace de travail sur main
ou en tête détachée (dossier d'exécution), même hors de la liste, avec la même règle stricte que le crochet et le lanceur (finish_lock.writes_protected,
R-20261107-3). Remplace : le gel général (4 pour tout appelant sans jeton). Retrait : permanent.
`freeze --wait <minutes>` (1 à 120) répète le contrôle jusqu'à ce que ce soit libre ou que les minutes soient écoulées. Un verrou périmé
(processus mort, ou plus vieux que PMZILLA_FINISH_LOCK_MAX_AGE secondes, 21600 par défaut) compte comme libre et est signalé.
`gestes` (R-160, P4) liste en lecture seule les gestes du tableau « En attente » de la file des gestes de l'auteur (`etapes/gestes.md` du
dossier du lab, hors dépôt, ou le fichier de PILOT_GESTES) : identifiant, geste, commande, ce qu'il débloque, décision ; `status` ajoute
la ligne « gestes en attente : <n> » quand la file est lisible, rien sinon. Cette lecture remplace la relecture à la main du fichier par la
session ; condition de retrait : permanente tant que la file des gestes existe (elle tombe avec la décision P4 si la file est abandonnée).
`note` pose ou retire une ligne par worktree (200 caractères au plus), contrôlée par la garde de l'outil d'écriture GitHub (noms sensibles,
identifiants personnels, clés de ticket) et rangée dans le dossier `pmzilla-notes` du dossier Git commun (propriétaire seul).

L'outil n'écrit que ces notes : jamais dans Git, jamais le verrou de fin (créé et retiré par les scripts de fin), aucun lancement de
script de fin ni de test.

Codes de sortie : 0 fait ; 2 usage ; 3 hors d'un dépôt du projet ; 4 gel : une fin de branche est en cours ; 5 note refusée par la garde ;
6 garde impossible (liste des noms absente, vide ou illisible, ou scanneur en échec) ; 7 aucun worktree pour la branche de la note ;
8 écriture de la note impossible ; 9 file des gestes introuvable, illisible ou sans section « En attente » (`gestes` seulement).

Variables : PILOT_NOW (secondes, horloge imposée, tests), PILOT_LSOF (commande qui liste les dossiers courants au format `lsof -F pn`,
défaut `lsof -w -n -P -d cwd -F pn`), PILOT_POLL_SECONDS (intervalle de `--wait`, 30 par défaut), PILOT_WAIT_UNIT_SECONDS (secondes par
« minute » de `--wait`, 60 par défaut ; tests), PMZILLA_FINISH_LOCK_MAX_AGE, FINISH_LOCK_TOKEN, PMZILLA_LAB_DATA (instantané),
PMZILLA_LAB_RUN (dossier d'exécution), PILOT_GESTES (fichier de la file des gestes ; tests).
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import finish_lock  # noqa: E402
import identifiants_personnels  # noqa: E402
import lab_paths  # noqa: E402
import sensitive_names  # noqa: E402
from messages import Messages, add_language_option  # noqa: E402
from pilot_messages import CATALOGS  # noqa: E402

NOTES_NAME = "pmzilla-notes"
SNAPSHOT_NAME = "roadmap-cache.json"
NOTE_MAX = 200
GESTES_DIR = "etapes"
GESTES_NAME = "gestes.md"
GIT_TIMEOUT = 30
# Même motif que tools/gh_issue.py (TICKET_KEY) : copié ici pour garder l'outil sans dépendance tierce.
TICKET_KEY = re.compile(r"(?<![A-Za-z0-9_])[A-Z]{2,}-\d+")


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def now():
    voulu = os.environ.get("PILOT_NOW", "")
    return int(voulu) if voulu.isdigit() else int(time.time())


def git(dossier, *args):
    """(code, sortie). Lecture seule : les verrous optionnels de Git sont coupés pour ne jamais réécrire l'index."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    try:
        r = subprocess.run(["git", "-C", str(dossier), *args], capture_output=True, text=True, env=env, timeout=GIT_TIMEOUT,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return r.returncode, r.stdout


# --- le dépôt et ses worktrees ------------------------------------------------------------------------------------------------

def find_common(t):
    code, sortie = git(Path.cwd(), "rev-parse", "--path-format=absolute", "--git-common-dir")
    lignes = sortie.splitlines()
    if code != 0 or len(lignes) != 1 or not os.path.isabs(lignes[0]):
        raise Stop(3, t("no_repo"))
    return Path(lignes[0])


def list_worktrees(main):
    """Les entrées de `git worktree list --porcelain` : dossier (chemin réel), sommet et branche courte (None si détachée)."""
    code, sortie = git(main, "worktree", "list", "--porcelain")
    entrees, courante = [], None
    for ligne in sortie.splitlines() + [""]:
        if ligne.startswith("worktree "):
            courante = {"path": os.path.realpath(ligne[9:]), "head": "", "branch": None}
        elif courante is not None and ligne.startswith("HEAD "):
            courante["head"] = ligne[5:]
        elif courante is not None and ligne.startswith("branch "):
            courante["branch"] = ligne[7:].removeprefix("refs/heads/")
        elif ligne == "" and courante is not None:
            entrees.append(courante)
            courante = None
    return entrees


# --- le verrou de fin de branche (lecture seule, tools/finish_lock.py) --------------------------------------------------------

def read_file(chemin):
    try:
        return Path(chemin).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_lock(common):
    return finish_lock.read_lock(common, now())


def clock_text(debut):
    return finish_lock.clock_text(debut if debut is not None else now())


# --- status ---------------------------------------------------------------------------------------------------------------------

def load_changes():
    """change -> R-<n> d'après l'instantané du lecteur de la file (lecture du fichier seulement) ; vide si absent ou illisible."""
    try:
        donnees = json.loads((lab_paths.data_folder() / SNAPSHOT_NAME).read_text(encoding="utf-8"))
        liens = {}
        for issue in donnees["issues"]:
            titre = re.match(r"R-(\d+)\b", issue.get("title") or "")
            change = re.search(r"^change:[ \t]*(\S+)[ \t]*$", issue.get("body") or "", re.M)
            if titre and change:
                liens.setdefault(change.group(1).strip("'\""), f"R-{titre.group(1)}")
        return liens
    except Exception:   # instantané absent, illisible ou d'une forme inconnue : pas de lien, jamais d'erreur
        return {}


def link_of(branche, liens, t):
    if branche is None:
        return t("link_none")
    m = re.fullmatch(r"chore/spec-r(\d+)", branche) or re.fullmatch(r"chore/r(\d+)-[a-z0-9][a-z0-9-]*", branche)
    if m:
        return f"R-{m.group(1)}"
    m = re.fullmatch(r"feat/(.+)", branche)
    if m:
        texte = t("link_change", change=m.group(1))
        return f"{texte} ({liens[m.group(1)]})" if m.group(1) in liens else texte
    return t("link_none")


def dirty_count(dossier):
    code, sortie = git(dossier, "status", "--porcelain", "--untracked-files=all")
    return len([l for l in sortie.splitlines() if l.strip()]) if code == 0 else 0


def age_text(sommet, dossier, t):
    code, sortie = git(dossier, "log", "-1", "--format=%ct", sommet)
    if code != 0 or not sortie.strip().isdigit():
        return None
    ecart = max(0, now() - int(sortie.strip()))
    if ecart < 3600:
        return t("age_min", n=ecart // 60)
    if ecart < 86400:
        return t("age_hour", n=ecart // 3600)
    return t("age_day", n=ecart // 86400)


def ahead_behind(dossier, sommet):
    code, sortie = git(dossier, "rev-list", "--left-right", "--count", f"main...{sommet}")
    morceaux = sortie.split()
    return (int(morceaux[1]), int(morceaux[0])) if code == 0 and len(morceaux) == 2 else None


def merged_tips(dossier):
    """Sommets de branche entrés dans main par une fusion sans avance rapide (seconds parents de l'historique de premier parent)."""
    code, sortie = git(dossier, "log", "--first-parent", "--merges", "--format=%P", "-n", "2000", "main")
    pris = set()
    if code == 0:
        for ligne in sortie.splitlines():
            pris.update(ligne.split()[1:])
    return pris


def busy_map(worktrees):
    """chemin -> True/False, ou None pour tous si le listage est impossible."""
    commande = os.environ.get("PILOT_LSOF") or "lsof -w -n -P -d cwd -F pn"
    try:
        r = subprocess.run(shlex.split(commande), capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if r.returncode != 0:
        return None
    occupes, pid = set(), ""
    for ligne in r.stdout.splitlines():
        if ligne.startswith("p"):
            pid = ligne[1:]
        elif ligne.startswith("n") and pid != str(os.getpid()):
            chemin = ligne[1:]
            for wt in worktrees:
                if (chemin + "/").startswith(wt + "/"):
                    occupes.add(wt)
    return occupes


def note_file(common, branche):
    return common / NOTES_NAME / branche.replace("%", "%25").replace("/", "%2F")


TRAIN_FOLDER = "train-auto"


def ready_flags(contenu):
    """branche -> ligne de la liste prête avec sa validité (change autonomous-trains-observe, D9), par la fonction de service de
    tools/train_ready.py ; vide sans fichier de liste, ou quand elle est illisible (le status ne s'arrête jamais pour cela). Hors réseau."""
    try:
        if not (lab_paths.data_folder() / TRAIN_FOLDER / "pretes.tsv").exists():
            return {}
        import train_ready
        return {e["branche"]: e for e in train_ready.list_validity(contenu, lab_paths.run_tree(contenu))}
    except Exception:
        return {}


def train_line(t):
    """La ligne « train automatique » (autonomous-trains-merge D20, qui remplace celle d'autonomous-trains-observe D9), ou None quand ni l'état, ni le fichier d'arrêt, ni le
    fichier d'activation n'existent. Le mode vient de train_auto.activation_state() (observation, fusion automatique ou activation invalide) et la série de
    train_auto.activation_status() : jamais du formatage. Formatage seulement."""
    try:
        dossier = lab_paths.data_folder() / TRAIN_FOLDER
        if not ((dossier / "etat.json").exists() or (dossier / "arret").exists() or (dossier / "fusion-active").exists()):
            return None
        import train_auto
        from train_auto_messages import decision_label, label
        etat = train_auto.last_state()
        arret = t("train_stop_active") if etat["arret"] else t("train_stop_absent")
        mode = t({"valide": "train_mode_fusion", "invalide": "train_mode_invalid"}.get(train_auto.activation_state(), "train_mode_observation"))
        try:
            serie = min(train_auto.activation_status()["series"], train_auto.SERIES_REQUIRED)
        except Exception:   # journal des trains illisible : la ligne reste, la série est 0
            serie = 0
        if etat["illisible"]:   # revue de contrôle 10.2, point A : dit, jamais pris pour « aucun passage »
            return t("train_line_unreadable", mode=mode, stop=arret, k=serie)
        r = etat["dernier"]
        if not r:
            return t("train_line_none", mode=mode, stop=arret, k=serie)
        return t("train_line", mode=mode, date=r["paris"], decision=decision_label(r["decision"], t.language), reason=label(r["raison"], t.language),
                 stop=arret, k=serie)
    except Exception:
        return None


def cmd_status(args, t):
    common = find_common(t)
    principal = common.parent
    contenu = principal
    labo = lab_paths.lab_folder(contenu)
    dossier_exec = os.path.realpath(lab_paths.run_tree(contenu))
    entrees = list_worktrees(principal)
    pretes = ready_flags(contenu)
    liens = load_changes()
    fusionnes = merged_tips(principal)
    liees = [e for e in entrees[1:] if e["path"] != dossier_exec]
    occupes = busy_map([e["path"] for e in liees])
    lignes = [t("header", n=len(liees))]
    for e in liees:
        nom = os.path.relpath(e["path"], labo)
        if nom.startswith(".."):
            nom = os.path.basename(e["path"])
        branche = e["branch"]
        k = dirty_count(e["path"])
        champs = [nom, branche or t("detached"), link_of(branche, liens, t), t("dirty", k=k) if k else t("clean")]
        ab = ahead_behind(e["path"], e["head"] or "HEAD")
        if ab:
            champs.append(t("ahead_behind", a=ab[0], b=ab[1]))
        age = age_text(e["head"] or "HEAD", e["path"], t)
        if age:
            champs.append(t("last_commit", d=age))
        champs.append(t("unknown") if occupes is None else (t("busy") if e["path"] in occupes else t("free")))
        if branche and branche in pretes:
            pret = pretes[branche]
            if pret["valide"]:
                champs.append(t("ready_valid"))
            else:
                from train_auto_messages import label as reason_label
                champs.append(t("ready_excluded", label=reason_label(pret["raison"], t.language)))
        if branche and e["head"] in fusionnes:
            champs.append(t("merged"))
        if branche:
            texte = read_file(note_file(common, branche))
            if texte:
                champs.append(t("note_field", text=texte))
        lignes.append(" | ".join(champs))
    if entrees:
        principal_branche = entrees[0]["branch"] or t("detached")
        k = dirty_count(entrees[0]["path"])
        lignes.append(t("workspace", branch=principal_branche, state=t("dirty", k=k) if k else t("clean")))
    verrou = read_lock(common)
    if verrou is None:
        lignes.append(t("lock_none"))
    elif verrou["stale"]:
        lignes.append(t("lock_stale", branch=verrou["branch"]))
    else:
        lignes.append(t("lock_held", branch=verrou["branch"], time=clock_text(verrou["start"])))
    ligne_train = train_line(t)
    if ligne_train:
        lignes.append(ligne_train)
    lignes.append(t("run_present") if any(e["path"] == dossier_exec for e in entrees) else t("run_absent"))
    try:
        lignes.append(t("gestes_count", n=len(read_gestes(t))))
    except Stop:   # file absente ou sans section : aucune ligne, jamais d'erreur dans status
        pass
    print("\n".join(lignes))
    return 0


# --- freeze -----------------------------------------------------------------------------------------------------------------------

def freeze_state(common):
    """('libre', None) ; ('perime', verrou) ; ('tenu', verrou) ; ('autre', verrou). L'appelant qui porte le jeton du verrou est libre.
    Gel ciblé (autonomous-trains-merge, D18) : une seule règle, finish_lock.freezes() ; « tenu » quand elle couvre le worktree du dossier courant
    (il est dans la liste du verrou, ou le verrou n'a pas de liste lisible), « autre » quand un verrou vivant ne le couvre pas.
    Remplace : le gel général (tout appelant sans jeton était « tenu »). Retrait : permanent."""
    scope = finish_lock.freeze_scope(common, now())
    verrou = {"branch": scope["branch"], "start": scope["start"], "token": scope["token"], "worktrees": scope["worktrees"]}
    if scope["stale"]:
        return "perime", verrou
    if not scope["held"]:
        return "libre", None
    jeton = os.environ.get("FINISH_LOCK_TOKEN", "")
    if jeton and jeton == scope["token"]:
        return "libre", verrou
    code, sortie = git(Path.cwd(), "rev-parse", "--show-toplevel")
    sommet = sortie.strip() if code == 0 and sortie.strip() else str(Path.cwd())
    # R-20261108-11 : le scope déjà lu est passé à freezes() (une seule lecture du verrou, décision et message cohérents).
    if finish_lock.freezes(common, sommet, jeton, protected=True, now=now(), scope=scope) is not None:   # R-20261107-3 : main et tête détachée gelés, règle stricte du crochet
        return "tenu", verrou
    return "autre", verrou


def freeze_report(etat, verrou, t):
    """Écrit la ligne du contrôle et rend le code de sortie."""
    if etat == "tenu":
        print(t("freeze_running", branch=verrou["branch"], time=clock_text(verrou["start"])), file=sys.stderr)
        return 4
    if etat == "autre":
        print(t("freeze_other", n=len(verrou["worktrees"])))
        return 0
    print(t("freeze_stale") if etat == "perime" else t("freeze_free"))
    return 0


def cmd_freeze(args, t):
    common = find_common(t)
    if args.check:
        return freeze_report(*freeze_state(common), t)
    texte = args.wait
    if not re.fullmatch(r"[1-9][0-9]{0,2}", texte) or not 1 <= int(texte) <= 120:
        raise Stop(2, t("wait_range"))
    minutes = int(texte)
    try:
        unite = float(os.environ.get("PILOT_WAIT_UNIT_SECONDS", "60"))
        intervalle = float(os.environ.get("PILOT_POLL_SECONDS", "30"))
    except ValueError:
        unite, intervalle = 60.0, 30.0
    fin = time.monotonic() + minutes * unite
    while True:
        etat, verrou = freeze_state(common)
        if etat != "tenu":
            return freeze_report(etat, verrou, t)
        reste = fin - time.monotonic()
        if reste <= 0:
            print(t("freeze_wait_spent", minutes=minutes), file=sys.stderr)
            return 4
        time.sleep(max(0.0, min(intervalle, reste)))


# --- note -------------------------------------------------------------------------------------------------------------------------

def guard_finds(texte):
    """True si la garde trouve un nom sensible, un identifiant personnel ou une clé de ticket ; Stop(6) si elle ne peut pas tourner."""
    try:
        noms = sensitive_names.load_judged_names()   # liste puis extrait : source unique (A-75, R-20261112-20)
    except sensitive_names.SensitiveNamesUnavailable:
        raise Stop(6, "") from None
    try:
        identifiants = [i.lower() for i in identifiants_personnels.identifiants(CODE_ROOT) if i]
    except BaseException as e:   # SystemExit(2) du scanneur compris
        if isinstance(e, KeyboardInterrupt):
            raise
        raise Stop(6, "") from None
    motifs = sensitive_names.patterns(noms)
    for ligne in texte.split("\n"):
        if sensitive_names.line_matches(motifs, ligne) or any(i in ligne.lower() for i in identifiants) or TICKET_KEY.search(ligne):
            return True
    return False


def cmd_note(args, t):
    if args.clear == (args.text is not None):
        raise Stop(2, t("note_usage"))
    if not args.clear and (len(args.text) > NOTE_MAX or "\n" in args.text or "\r" in args.text or not args.text.strip()):
        raise Stop(2, t("note_usage"))
    common = find_common(t)
    principal = common.parent
    dossier_exec = os.path.realpath(lab_paths.run_tree(principal))
    if not any(e["branch"] == args.branch and e["path"] != dossier_exec for e in list_worktrees(principal)[1:]):
        raise Stop(7, t("note_no_worktree", branch=args.branch))
    fichier = note_file(common, args.branch)
    if args.clear:
        try:
            fichier.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            raise Stop(8, t("note_write_failed")) from None
        print(t("note_cleared"))
        return 0
    try:
        trouve = guard_finds(args.text)
    except Stop as e:
        raise Stop(6, t("note_guard_impossible")) from e
    if trouve:
        raise Stop(5, t("note_refused"))
    try:
        dossier = fichier.parent
        dossier.mkdir(mode=0o700, exist_ok=True)
        os.chmod(dossier, 0o700)
        temporaire = dossier / f".tmp-{os.getpid()}"
        fd = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(args.text.strip() + "\n")
        os.replace(temporaire, fichier)
    except OSError:
        raise Stop(8, t("note_write_failed")) from None
    print(t("note_saved"))
    return 0


# --- gestes de l'auteur (R-160, P4) ---------------------------------------------------------------------------------------------

def gestes_file():
    voulu = os.environ.get("PILOT_GESTES", "")
    if voulu:
        return Path(voulu).expanduser()
    return lab_paths.lab_folder(lab_paths.content_root()) / GESTES_DIR / GESTES_NAME


def read_gestes(t):
    """Gestes du tableau « En attente » : liste de dicts (id, geste, commande, debloque, decision), ceux dont l'identifiant est barré exclus.
    Stop(9) si le fichier est absent, illisible ou sans section « En attente »."""
    try:
        lignes = gestes_file().read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError, lab_paths.LabPathsError):
        raise Stop(9, t("gestes_missing")) from None
    dedans, trouve, gestes = False, False, []
    for ligne in lignes:
        if re.match(r"##\s+En attente\s*$", ligne):
            dedans, trouve = True, True
        elif ligne.startswith("## "):
            dedans = False
        elif dedans and ligne.startswith("|") and not re.fullmatch(r"\|[-|: ]+\|?\s*", ligne):
            cellules = [c.strip() for c in ligne.strip().strip("|").split("|")]
            if len(cellules) < 5 or cellules[0] == "#" or "~~" in cellules[0]:
                continue
            gestes.append({"id": cellules[0], "geste": cellules[1], "commande": " | ".join(cellules[2:-2]).replace("`", ""),
                           "debloque": cellules[-2], "decision": cellules[-1]})
    if not trouve:
        raise Stop(9, t("gestes_format"))
    return gestes


def cmd_gestes(args, t):
    gestes = read_gestes(t)
    if not gestes:
        print(t("gestes_none"))
        return 0
    lignes = [t("gestes_header", n=len(gestes))]
    for g in gestes:
        lignes += [f"{g['id']} | {g['geste']}", t("gestes_command", text=g["commande"]), t("gestes_unblocks", text=g["debloque"]),
                   t("gestes_decision", text=g["decision"])]
    print("\n".join(lignes))
    return 0


# --- ligne de commande ------------------------------------------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="pilot.py", description="Pilotage de plusieurs sessions : état des worktrees, gel des tests, notes.")
    add_language_option(p)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="liste les worktrees, le verrou de fin et le dossier d'exécution")
    f = sub.add_parser("freeze", help="contrôle ou attend la fin d'une fin de branche")
    g = f.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--wait", metavar="MINUTES")
    sub.add_parser("gestes", help="liste les gestes en attente de l'auteur (file hors dépôt, lecture seule)")
    n = sub.add_parser("note", help="pose ou retire la note d'un worktree")
    n.add_argument("branch")
    n.add_argument("text", nargs="?")
    n.add_argument("--clear", action="store_true")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    t = Messages(CATALOGS, args.language)
    try:
        return {"status": cmd_status, "freeze": cmd_freeze, "note": cmd_note, "gestes": cmd_gestes}[args.cmd](args, t)
    except Stop as e:
        if e.message:
            print(e.message, file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
