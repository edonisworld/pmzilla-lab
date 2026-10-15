# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.2,<2", "pyyaml", "httpx", "numpy", "psycopg[binary]"]
# ///
"""
PMZilla Lab : journal d'accompagnement.

Après chaque séance (atelier, rétro, coaching individuel, CoP…), quelques lignes : ce qui a été tenté,
ce qui a marché ou non, les suites promises, et éventuellement une expérience à évaluer plus tard.
Les postures relisent les suites ouvertes avant la séance suivante ; le bilan montre, au fil des
mois, ce qui marche selon le contexte.

Le journal ne contient que des rôles et des périmètres (équipe, domaine), jamais de noms de
personnes. Il vit dans Journal-Lab/, exclu de Git.

    uv run journal_lab.py add <entree.yaml> [--language fr|en]
        Valide une entrée rédigée dans un fichier (voir FORMAT ci-dessous), l'ajoute au journal,
        puis supprime le fichier. Affiche les identifiants attribués.

    uv run journal_lab.py follow-ups [--scope "équipe X"] [--all] [--language fr|en]
        Suites ouvertes (les plus urgentes d'abord, en retard signalées) et expériences dont le
        bilan est dû. --all ajoute les suites faites ou abandonnées.

    uv run journal_lab.py update <identifiant> <faite|abandonnee|ouverte|conclue> [--note "…"] [--language fr|en]
        Met à jour une suite (J-20261005-1.s1) ou conclut une expérience (J-20261005-1.x) ; pour
        une expérience, --note porte le résultat observé.

    uv run journal_lab.py review [--since AAAA-MM-JJ] [--scope "…"] [--language fr|en]
        Les séances de la période sous une forme compacte, avec le décompte des suites tenues, en
        retard ou abandonnées et des expériences conclues : la matière du bilan.

    uv run journal_lab.py experiment start <brouillon.yaml> [--language fr|en]
    uv run journal_lab.py experiment note <n> <brouillon.yaml>
    uv run journal_lab.py experiment show <n>
    uv run journal_lab.py experiment postpone <n> <durée>        (10d ou 2w)
    uv run journal_lab.py experiment drop <n>
    uv run journal_lab.py experiment close <n> <brouillon.yaml>
    uv run journal_lab.py experiment due [--session-hook]
        Module des cas (schéma cases de la base, design.md 5 de db-lot2) : une expérience se lance, se note,
        se reporte (deux fois au plus), s'abandonne ou se clôt en un cas. Les brouillons sont des fichiers YAML
        (clés en anglais, supprimés après succès, conservés après un refus). Codes de sortie : 0 succès ; 1 brouillon
        ou règle refusés ; 2 base injoignable, auteur non configuré, liste des noms sensibles absente ou vide, ou
        service d'embedding indisponible. --session-hook (crochet de début de séance) sort toujours 0 et
        n'imprime rien sans auteur ni bilan dû. L'auteur vient de PMZILLA_LAB_CASES_AUTHOR ou de la clé « author » de
        .pmzilla/cases.yaml ; follow-ups ajoute les bilans dus de la base quand un auteur est configuré.

--language fr|en : langue des messages et des sorties (français par défaut). Les clés YAML des entrées et les valeurs de
statut (ouverte, faite, abandonnee, en cours, conclue) sont un format de données : elles s'écrivent toujours en français,
seul leur affichage est traduit en anglais.

FORMAT d'une entrée (YAML) :
    date: 2026-10-05              # facultatif, aujourd'hui par défaut
    type: rétro                   # atelier, rétro, coaching (1:1), CoP, formation, diagnostic, autre
    perimetre: équipe Alpha       # une équipe, un domaine ou un rôle, jamais une personne
    posture: facilitation         # discovery, delivery, scaling, facilitation, aucune
    tente: …                      # ce qui a été tenté
    constat: …                    # ce qui a marché, ou non, et à quoi on le voit
    suites:                       # facultatif
      - quoi: …
        pour: Scrum Master        # un rôle
        echeance: 2026-10-19
    experience:                   # facultatif, OBSOLÈTE : utiliser « experiment start » (module des cas)
      hypothese: …
      signal: …                   # ce qu'on observera si l'hypothèse tient
      bilan_le: 2026-11-02

Exemple :
    uv run tools/journal_lab.py add entree.yaml
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cases_store
import flux_config
import sensitive_names
from cases_store import CasesError, connect_cases
from journal_lab_messages import CATALOGS
from messages import Messages, add_language_option

WORKSPACE = Path(os.environ.get("PMZILLA_LAB_WORKSPACE", "~/PMZilla-Lab/workspace")).expanduser()
JOURNAL_DIR = WORKSPACE / "Journal-Lab"
JOURNAL_FILE = JOURNAL_DIR / "journal.yaml"

# « coaching » plutôt que « 1:1 » : YAML lit 1:1 comme un nombre (61)
TYPES = ["atelier", "rétro", "coaching", "CoP", "formation", "diagnostic", "autre"]
POSTURES = ["discovery", "delivery", "scaling", "facilitation", "aucune"]
STATUTS_SUITE = ["ouverte", "faite", "abandonnee"]
from cases_store import MAX_TEXT_LENGTH as LONGUEUR_MAX   # au-delà, ce n'est plus une note de journal : résumer (constante déplacée dans cases_store)


class EntreeInvalide(Exception):
    pass


FR = Messages(CATALOGS, "fr")


def status_label(t: Messages, status: str) -> str:
    """Affichage d'une valeur de statut (la valeur écrite dans le journal reste en français)."""
    return t("status_" + status.replace(" ", "_"))


# ---------------------------------------------------------------------------
# Lecture et écriture
# ---------------------------------------------------------------------------

def load() -> list[dict]:
    if not JOURNAL_FILE.exists():
        return []
    return yaml.safe_load(JOURNAL_FILE.read_text(encoding="utf-8")) or []


def save(entries: list[dict]) -> None:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = JOURNAL_FILE.with_suffix(".tmp")
    tmp.write_text(yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
    tmp.replace(JOURNAL_FILE)   # écriture atomique : jamais de journal à moitié écrit


def as_date(value, field: str, t: Messages = FR) -> dt.date:
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise EntreeInvalide(t("date_invalid", field=field, value=value)) from None


def text(raw: dict, field: str, required: bool = True, t: Messages = FR) -> str:
    value = str(raw.get(field) or "").strip()
    if required and not value:
        raise EntreeInvalide(t("field_missing", field=field))
    if len(value) > LONGUEUR_MAX:
        raise EntreeInvalide(t("field_too_long", field=field, limit=LONGUEUR_MAX))
    return value


def today(args: argparse.Namespace) -> dt.date:
    return dt.date.fromisoformat(args.aujourdhui) if getattr(args, "aujourdhui", None) else dt.date.today()


# ---------------------------------------------------------------------------
# Validation d'une entrée
# ---------------------------------------------------------------------------

def validate(raw: dict, entries: list[dict], now: dt.date, t: Messages = FR) -> dict:
    if not isinstance(raw, dict):
        raise EntreeInvalide(t("entry_not_dict"))
    unknown = set(raw) - {"date", "type", "perimetre", "posture", "tente", "constat", "suites", "experience"}
    if unknown:
        raise EntreeInvalide(t("unknown_fields", fields=", ".join(sorted(unknown))))
    day = as_date(raw.get("date") or now, "date", t)
    if day > now:
        raise EntreeInvalide(t("date_in_future", date=day))
    kind = text(raw, "type", t=t)
    if kind not in TYPES:
        raise EntreeInvalide(t("unknown_type", value=kind, allowed=", ".join(TYPES)))
    posture = text(raw, "posture", required=False, t=t) or "aucune"
    if posture not in POSTURES:
        raise EntreeInvalide(t("unknown_posture", value=posture, allowed=", ".join(POSTURES)))
    same_day = sum(1 for e in entries if e["date"] == day.isoformat())
    entry_id = f"J-{day:%Y%m%d}-{same_day + 1}"
    entry = {"id": entry_id, "date": day.isoformat(), "type": kind, "perimetre": text(raw, "perimetre", t=t),
             "posture": posture, "tente": text(raw, "tente", t=t), "constat": text(raw, "constat", t=t), "suites": []}
    for n, suite in enumerate(raw.get("suites") or [], start=1):
        if not isinstance(suite, dict):
            raise EntreeInvalide(t("follow_up_malformed", n=n))
        due = as_date(suite.get("echeance"), f"suites[{n}].echeance", t)
        entry["suites"].append({"id": f"{entry_id}.s{n}", "quoi": text(suite, "quoi", t=t), "pour": text(suite, "pour", t=t),
                                "echeance": due.isoformat(), "statut": "ouverte", "note": ""})
    exp = raw.get("experience")
    if exp:
        if not isinstance(exp, dict):
            raise EntreeInvalide(t("experiment_malformed"))
        entry["experience"] = {"id": f"{entry_id}.x", "hypothese": text(exp, "hypothese", t=t),
                               "signal": text(exp, "signal", t=t),
                               "bilan_le": as_date(exp.get("bilan_le"), "experience.bilan_le", t).isoformat(),
                               "statut": "en cours", "resultat": ""}
    return entry


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

def cmd_ajouter(args: argparse.Namespace) -> None:
    t = Messages(CATALOGS, args.language)
    path = Path(args.fichier).expanduser()
    if not path.exists():
        sys.exit(t("file_not_found", path=path))
    entries = load()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        entry = validate(raw, entries, today(args), t)
    except (EntreeInvalide, yaml.YAMLError) as error:
        sys.exit(t("entry_refused", error=error))
    entries.append(entry)
    save(entries)
    path.unlink()
    print(t("session_noted", id=entry["id"], type=entry["type"], scope=entry["perimetre"]))
    for suite in entry["suites"]:
        print(t("added_follow_up", id=suite["id"], what=suite["quoi"], role=suite["pour"], due=suite["echeance"]))
    if "experience" in entry:
        print(t("added_experiment", id=entry["experience"]["id"], date=entry["experience"]["bilan_le"]))
        print(t("experience_deprecated"), file=sys.stderr)


def matches(entry: dict, perimetre: str | None) -> bool:
    return not perimetre or perimetre.casefold() in entry["perimetre"].casefold()


def cmd_suites(args: argparse.Namespace) -> None:
    t = Messages(CATALOGS, args.language)
    now = today(args)
    entries = [e for e in load() if matches(e, args.perimetre)]
    rows = [(s, e) for e in entries for s in e["suites"] if args.toutes or s["statut"] == "ouverte"]
    rows.sort(key=lambda r: (r[0]["statut"] != "ouverte", r[0]["echeance"]))
    label = f" · {args.perimetre}" if args.perimetre else ""
    print(t("followups_header", label=label, which=t("followups_which_all" if args.toutes else "followups_which_open"),
            date=now))
    if not rows:
        print(t("followups_none"))
    for suite, entry in rows:
        late = suite["statut"] == "ouverte" and dt.date.fromisoformat(suite["echeance"]) < now
        flag = t("late_flag") if late else ""
        status = "" if suite["statut"] == "ouverte" else f" [{status_label(t, suite['statut'])}]"
        print(t("followup_row", flag=flag, id=suite["id"], status=status, due=suite["echeance"], role=suite["pour"],
                what=suite["quoi"], date=entry["date"], type=entry["type"], scope=entry["perimetre"]))
    due = [e for e in entries if e.get("experience") and e["experience"]["statut"] == "en cours"
           and dt.date.fromisoformat(e["experience"]["bilan_le"]) <= now]
    if due:
        print(t("experiments_due_header"))
        for entry in due:
            x = entry["experience"]
            print(t("experiment_due_row", id=x["id"], date=x["bilan_le"], scope=entry["perimetre"],
                    hypothesis=x["hypothese"], signal=x["signal"]))
        print(t("experience_deprecated"), file=sys.stderr)
    cases_block(t, now)


def cmd_maj(args: argparse.Namespace) -> None:
    t = Messages(CATALOGS, args.language)
    entries = load()
    for entry in entries:
        if entry.get("experience", {}).get("id") == args.identifiant:
            if args.statut != "conclue":
                sys.exit(t("experiment_must_conclude"))
            if not (args.note or "").strip():
                sys.exit(t("experiment_note_required"))
            entry["experience"].update(statut="conclue", resultat=args.note.strip())
            save(entries)
            print(t("experiment_concluded", id=args.identifiant))
            return
        for suite in entry["suites"]:
            if suite["id"] == args.identifiant:
                if args.statut not in STATUTS_SUITE:
                    sys.exit(t("follow_up_status_invalid", allowed=", ".join(STATUTS_SUITE)))
                suite["statut"] = args.statut
                if args.note:
                    suite["note"] = args.note.strip()
                save(entries)
                print(t("follow_up_updated", id=args.identifiant, status=status_label(t, args.statut)))
                return
    sys.exit(t("unknown_id", id=args.identifiant))


def cmd_bilan(args: argparse.Namespace) -> None:
    t = Messages(CATALOGS, args.language)
    now = today(args)
    since = dt.date.fromisoformat(args.depuis) if args.depuis else now - dt.timedelta(days=30)
    entries = [e for e in load() if matches(e, args.perimetre) and dt.date.fromisoformat(e["date"]) >= since]
    print(t("review_header", since=since, now=now, scope=" · " + args.perimetre if args.perimetre else "",
            count=len(entries)))
    suites = [s for e in entries for s in e["suites"]]
    late = [s for s in suites if s["statut"] == "ouverte" and dt.date.fromisoformat(s["echeance"]) < now]
    counts = {status: sum(1 for s in suites if s["statut"] == status) for status in STATUTS_SUITE}
    experiences = [e["experience"] for e in entries if e.get("experience")]
    print(t("review_follow_ups", total=len(suites), done=counts["faite"], abandoned=counts["abandonnee"],
            open=counts["ouverte"], late=len(late)))
    print(t("review_experiments", total=len(experiences),
            concluded=sum(1 for x in experiences if x["statut"] == "conclue")))
    for entry in entries:
        print(t("review_entry", id=entry["id"], date=entry["date"], type=entry["type"], scope=entry["perimetre"],
                posture=entry["posture"]))
        print(t("review_tried", tried=entry["tente"], finding=entry["constat"]))
        for s in entry["suites"]:
            note = f" ({s['note']})" if s["note"] else ""
            print(t("review_follow_up", status=status_label(t, s["statut"]), what=s["quoi"], role=s["pour"],
                    due=s["echeance"], note=note))
        if entry.get("experience"):
            x = entry["experience"]
            print(t("review_experiment", status=status_label(t, x["statut"]), hypothesis=x["hypothese"], signal=x["signal"])
                  + (t("review_experiment_result", result=x["resultat"]) if x["resultat"] else ""))
        print()

# ---------------------------------------------------------------------------
# Module des cas : sous-commandes experiment (db-lot2, design.md 5)
# ---------------------------------------------------------------------------

AUTHOR_FILE_LABEL = ".pmzilla/cases.yaml"
EXIT_2_CODES = {"author_missing", "embedding_unavailable", "database_unreachable"}
SHOW_FIELDS = ("posture", "problem", "context", "hypotheses", "chosen_path", "references_used", "tested", "expected_signal",
               "success_criterion")


def fail(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    sys.exit(code)


def explain(t: Messages, error: CasesError) -> str:
    """Message du catalogue pour un refus connu (par son code) ; sinon le texte de la couche d'accès. Jamais un nom sensible."""
    key = "err_" + str(error.code)
    if error.code and key in CATALOGS["fr"]:
        return t(key, field=error.field or "", limit=LONGUEUR_MAX)
    return t("cases_refused", message=error)


def refuse(t: Messages, error: CasesError, draft: bool) -> None:
    detail = explain(t, error)
    if error.code == "author_missing":
        fail(t("author_missing", file=AUTHOR_FILE_LABEL), 2)
    if error.code in EXIT_2_CODES:
        fail(detail, 2)
    fail(t("draft_refused", error=detail) if draft else t("cases_refused", message=detail), 1)


def unreachable(t: Messages, error: Exception) -> str:
    return t("database_unreachable", error=type(error).__name__)   # le nom du type seulement : jamais le texte de l'erreur


def require_author(t: Messages) -> str:
    author = cases_store.resolve_author(WORKSPACE)
    if not author:
        fail(t("author_missing", file=AUTHOR_FILE_LABEL), 2)
    return author


def load_names(t: Messages) -> list[str]:
    """Liste des noms sensibles ; absente, illisible ou vide : refus avant toute connexion (design.md 3.5)."""
    try:
        return sensitive_names.load_names()
    except sensitive_names.SensitiveNamesUnavailable as error:
        fail(t("sensitive_names_empty" if error.reason == "empty" else "sensitive_names_missing", path=error.path), 2)


def read_draft(t: Messages, name: str):
    path = Path(name).expanduser()
    if not path.exists():
        fail(t("file_not_found", path=path), 1)
    try:
        return path, yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        fail(t("draft_not_yaml", error=type(error).__name__), 1)


def write_connection():
    return connect_cases("pmzilla_cases")


def run_write(t: Messages, action, draft: bool = False):
    """Exécute une écriture ; refus de la couche d'accès -> code 1 ou 2, base injoignable -> 2."""
    try:
        return action()
    except CasesError as error:
        refuse(t, error, draft)
    except Exception as error:   # connexion refusée (la couche d'accès a déjà converti les refus de la base)
        fail(unreachable(t, error), 2)


def cmd_experiment(args: argparse.Namespace) -> None:
    t = Messages(CATALOGS, args.language)
    now = today(args)
    action = args.action
    if action == "due" and args.session_hook:
        return session_hook(t, now)
    if action in ("start", "note", "close"):
        author = require_author(t)
        names = load_names(t)
        path, raw = read_draft(t, args.fichier)
        if action == "start":
            def start():
                clean = cases_store.validate_start_draft(raw, now, names)
                number = cases_store.start_experiment(write_connection, cases_store.default_embed, raw, author, now, names=names)
                return number, clean["review_due"]
            number, review = run_write(t, start, draft=True)
            print(t("experiment_started", number=number, date=review))
        elif action == "note":
            def note():
                clean = cases_store.validate_note_draft(raw, now, names)
                cases_store.add_note(write_connection, args.number, clean["note"], clean["noted_on"], author, now, names=names)
            run_write(t, note, draft=True)
            print(t("note_added", number=args.number))
        else:
            case = run_write(t, lambda: cases_store.close_experiment(write_connection, args.number, raw, author, now, names=names),
                             draft=True)
            print(t("experiment_closed", number=args.number, case=case))
        path.unlink()
    elif action == "postpone":
        author = require_author(t)
        result = run_write(t, lambda: cases_store.postpone(write_connection, args.number, args.duration, author, now))
        print(t("experiment_postponed", number=args.number, date=result["review_due"], count=result["postponements"]))
    elif action == "drop":
        author = require_author(t)
        run_write(t, lambda: cases_store.drop(write_connection, args.number, author))
        print(t("experiment_dropped", number=args.number))
    elif action == "show":
        print_experiment(t, read_cases(t, lambda conn: cases_store.show_experiment(conn, args.number)))
    else:   # due
        author = require_author(t)
        print_due(t, read_cases(t, lambda conn: cases_store.due_reviews(conn, author, now)), none=True)


def read_cases(t: Messages, query, timeout: int | None = None):
    """Une lecture sous pmzilla_cases_ro ; refus -> code 1, base injoignable -> code 2."""
    try:
        conn = connect_cases("pmzilla_cases_ro") if timeout is None else connect_cases("pmzilla_cases_ro", timeout=timeout)
    except Exception as error:
        fail(unreachable(t, error), 2)
    try:
        return query(conn)
    except CasesError as error:
        refuse(t, error, draft=False)
    except Exception as error:
        fail(unreachable(t, error), 2)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def print_experiment(t: Messages, e: dict) -> None:
    print(t("show_header", number=e["number"], status=e["status"], started=e["started_on"], due=e["review_due"],
            postponements=e["postponements"]))
    for key in SHOW_FIELDS:
        value = e.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, dict):
            value = ", ".join(f"{k}: {v}" for k, v in value.items())
        elif isinstance(value, list):
            value = " ; ".join(str(v) for v in value)
        print(t("show_field", label=t("show_label_" + key), value=value))
    if e["notes"]:
        print(t("show_notes_header"))
        for n in e["notes"]:
            print(t("show_note", date=n["noted_on"], note=n["note"]))
    else:
        print(t("show_notes_none"))


def print_due(t: Messages, reviews: list, none: bool = False) -> None:
    if not reviews:
        if none:
            print(t("due_none"))
        return
    print(t("due_reviews_header", count=len(reviews)))
    for r in reviews:
        print(t("due_review_row", number=r["number"], date=r["review_due"], problem=r["problem"],
                flag=t("due_review_flag") if r.get("decision_required") else ""))
    print(t("due_review_settle"))


def session_hook(t: Messages, now: dt.date) -> None:
    """Crochet de début de séance : sort toujours 0 (SystemExit compris) ; rien sans auteur (et aucune connexion), rien sans bilan dû."""
    try:
        author = cases_store.resolve_author(WORKSPACE)
        if not author:
            return
        try:
            conn = connect_cases("pmzilla_cases_ro", timeout=2)
        except (Exception, SystemExit):
            print(t("cases_unreachable_line"))
            return
        try:
            print_due(t, cases_store.due_reviews(conn, author, now))
        finally:
            try:
                conn.close()
            except (Exception, SystemExit):
                pass
    except (Exception, SystemExit):
        print(t("cases_unreachable_line"))


def cases_block(t: Messages, now: dt.date) -> None:
    """Bilans dus du module des cas, à la suite des expériences YAML, seulement si un auteur est configuré ; sans effet sur le code de sortie."""
    author = cases_store.resolve_author(WORKSPACE)
    if not author:
        return
    try:
        conn = connect_cases("pmzilla_cases_ro")
        try:
            reviews = cases_store.due_reviews(conn, author, now)
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception:
        print(t("cases_unreachable_line"))
        return
    print_due(t, reviews)


OPTIONS_RENOMMEES = {**flux_config.OPTIONS_COMMUNES, "--toutes": "--all", "--depuis": "--since"}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Journal d'accompagnement de PMZilla Lab")
    parser.add_argument("--today", dest="aujourdhui", help=argparse.SUPPRESS)   # pour les tests
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="ajouter une séance rédigée dans un fichier YAML")
    add.add_argument("fichier")
    add_language_option(add)
    sui = commands.add_parser("follow-ups", help="suites ouvertes et expériences dont le bilan est dû")
    sui.add_argument("--scope", dest="perimetre", help="filtrer sur un périmètre (recherche dans le nom)")
    sui.add_argument("--all", dest="toutes", action="store_true", help="inclure les suites faites ou abandonnées")
    add_language_option(sui)
    upd = commands.add_parser("update", help="mettre à jour une suite ou conclure une expérience")
    upd.add_argument("identifiant")
    upd.add_argument("statut", choices=STATUTS_SUITE + ["conclue"])
    upd.add_argument("--note", help="précision, ou résultat d'une expérience")
    add_language_option(upd)
    bil = commands.add_parser("review", help="la matière d'un bilan sur une période")
    bil.add_argument("--since", dest="depuis", help="date de début (AAAA-MM-JJ), 30 jours par défaut")
    bil.add_argument("--scope", dest="perimetre")
    add_language_option(bil)
    exp = commands.add_parser("experiment", help="expériences du module des cas (start, note, show, postpone, drop, close, due)")
    actions = exp.add_subparsers(dest="action", required=True)
    for name, helptext in (("start", "lancer une expérience depuis un brouillon YAML"), ("note", "ajouter une note datée"),
                           ("close", "clore une expérience en un cas")):
        one = actions.add_parser(name, help=helptext)
        if name != "start":
            one.add_argument("number", type=int)
        one.add_argument("fichier", help="brouillon YAML (supprimé après succès)")
        add_language_option(one)
    one = actions.add_parser("show", help="afficher une expérience et ses notes")
    one.add_argument("number", type=int)
    add_language_option(one)
    one = actions.add_parser("postpone", help="reporter le bilan (10d ou 2w, deux fois au plus)")
    one.add_argument("number", type=int)
    one.add_argument("duration")
    add_language_option(one)
    one = actions.add_parser("drop", help="abandonner sans leçon")
    one.add_argument("number", type=int)
    add_language_option(one)
    one = actions.add_parser("due", help="bilans dus de l'auteur")
    one.add_argument("--session-hook", action="store_true", help="sortie du crochet de début de séance : toujours 0")
    add_language_option(one)
    args = parser.parse_args(flux_config.refuse_old_options(sys.argv[1:] if argv is None else argv, OPTIONS_RENOMMEES))
    {"add": cmd_ajouter, "follow-ups": cmd_suites, "update": cmd_maj, "review": cmd_bilan, "experiment": cmd_experiment}[args.command](args)


if __name__ == "__main__":
    main()
