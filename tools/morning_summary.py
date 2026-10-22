# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.2,<2", "pyyaml", "httpx", "numpy", "psycopg[binary]"]
# ///
"""
PMZilla Lab : résumé du matin (change morning-summary, R-50).

    uv run tools/morning_summary.py [--language fr|en] [--json] [--notify] [--failed-steps "<étapes>"]

Imprime un titre puis une ligne par partie, dans cet ordre : la veille du jour, les bilans dus, les travaux prêts de la file, le dernier
contrôle du doctor. Des nombres et des dates seulement : jamais un titre d'article, un texte de problème, un titre de travail, un chemin,
un nom ni un secret. Sans `--notify`, le script n'écrit rien : la session peut le lancer pour lire le résumé dans le Terminal.

Sources (chacune lue en lecture seule, jamais le réseau) :
  - la veille : le repère du passage du jour `veille-du-jour.json` (état « termine » ou « echoue », déclencheur « rattrapage ») et le
    décompte `veille-retenus.json` écrit par la liste à lire classée, retenu seulement s'il porte la date du repère ;
  - les bilans dus : la règle commune de tools/cases_store.py (`due_reviews`), sous le rôle de lecture seule, délai de connexion court ;
    sans auteur configuré, la ligne est omise et aucune connexion n'est ouverte ; si le mot de passe ne se lit pas (Trousseau fermé),
    la ligne dit « indisponible » ; si la base ne répond pas, « base injoignable » ;
  - la file : l'instantané du lecteur (tools/roadmap.py), compté comme le rappel de début de séance (Status Ready) ;
  - le doctor : `doctor-etat.json` (date du contrôle et nombre de problèmes).
Les dossiers viennent des réglages (PMZILLA_LAB_DATA, PMZILLA_LAB_WORKSPACE), jamais de l'emplacement du script ; PMZILLA_LAB_TODAY
(AAAA-MM-JJ) fixe le jour dans les tests, sinon c'est le jour d'Europe/Paris.

Notification : seulement avec `--notify` ET la variable PMZILLA_SUMMARY_NOTIFY=1 (posée par watch.sh), une fois par jour au plus
(`resume-du-matin.json`, écrit après une notification réussie), sauf si le marqueur `resume-du-matin-coupe` du dossier de données existe.
Le titre et le corps passent à osascript comme arguments, jamais dans le texte de son script.

Codes de sortie :
  0  résumé imprimé (notification envoyée si elle était demandée ; une partie inconnue ne change rien)
  1  notification demandée et permise, mais osascript a échoué
  2  erreur d'usage
  3  notification demandée et permise, mais déjà envoyée aujourd'hui
  4  notification demandée et permise, mais le résumé est coupé par le réglage local (le résumé est imprimé quand même)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths  # noqa: E402
from messages import Messages, add_language_option  # noqa: E402
from morning_summary_messages import CATALOGS  # noqa: E402

FUSEAU = "Europe/Paris"
DELAI_BASE = 2            # secondes : le délai court du crochet de début de séance
VARIABLE_PLANIFIE = "PMZILLA_SUMMARY_NOTIFY"
MEMOIRE = "resume-du-matin.json"
INTERRUPTEUR = "resume-du-matin-coupe"
SCRIPT_OSASCRIPT = ("on run argv", "display notification (item 2 of argv) with title (item 1 of argv)", "end run")


class Injoignable(Exception):
    """La base des cas ne répond pas (le texte de l'erreur d'origine n'est jamais gardé)."""


class Indisponible(Exception):
    """Le mot de passe du rôle de lecture ne se lit pas (Trousseau fermé, par exemple)."""


def aujourdhui() -> dt.date:
    force = os.environ.get("PMZILLA_LAB_TODAY", "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", force):
        try:
            return dt.date.fromisoformat(force)
        except ValueError:
            pass
    return dt.datetime.now(ZoneInfo(FUSEAU)).date()


def dossier_donnees() -> Path:
    return Path(os.environ.get("PMZILLA_LAB_DATA") or "~/.pmzilla-lab").expanduser()


def dossier_contenu(code: Path | None = None) -> Path | None:
    """Dossier de contenu par le module partagé tools/lab_paths.py (R-77, D1) : PMZILLA_LAB_WORKSPACE s'il est posé, sinon le parent du
    dossier Git commun du dossier du code. None quand il est introuvable (variable sur un dossier absent, pas un dépôt Git, Git absent,
    délai) : le résumé ne s'arrête jamais (D7), la partie qui en a besoin est inconnue ; jamais le dossier du code en repli."""
    try:
        return lab_paths.content_root(os.environ, code)
    except lab_paths.LabPathsError:
        return None


def lire_objet(chemin: Path):
    """Objet JSON du fichier, ou None s'il manque, est illisible ou n'est pas un objet."""
    try:
        valeur = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return valeur if isinstance(valeur, dict) else None


# --- les quatre parties : un dictionnaire d'état, des nombres et des dates ------------------------------------------------------

def partie_veille(jour: dt.date, etapes: list[str]) -> dict:
    donnees = dossier_donnees()
    repere = lire_objet(donnees / "veille-du-jour.json")
    if repere is None or repere.get("date") != jour.isoformat() or repere.get("etat") not in ("termine", "echoue"):
        return {"state": "unknown"}
    if repere["etat"] == "echoue":
        return {"state": "failed", "failed_steps": etapes}
    retenus = lire_objet(donnees / "veille-retenus.json")
    compte = None
    if retenus is not None and retenus.get("date") == repere["date"] and isinstance(retenus.get("retained"), int) \
            and not isinstance(retenus.get("retained"), bool):
        compte = retenus["retained"]
    return {"state": "done", "catch_up": repere.get("declencheur") == "rattrapage", "retained": compte}


def bilans_de_la_base(auteur: str, jour: dt.date) -> list:
    """La vraie lecture : mot de passe (module db), connexion courte sous le rôle de lecture, règle commune des bilans dus."""
    import cases_store
    import db
    role = cases_store.ROLE_READ
    try:
        secret = db.lire_mot_de_passe(role=role)
    except (Exception, SystemExit):
        raise Indisponible() from None
    if not secret:
        raise Indisponible()
    try:
        connexion = db.connect(role=role, password=secret, dbname=os.environ.get(cases_store.DBNAME_VARIABLE) or None, timeout=DELAI_BASE)
    except (Exception, SystemExit):
        raise Injoignable() from None
    try:
        return cases_store.due_reviews(connexion, auteur, jour)
    except (Exception, SystemExit):
        raise Injoignable() from None
    finally:
        try:
            connexion.close()
        except (Exception, SystemExit):
            pass


def partie_bilans(jour: dt.date, bilans) -> dict:
    import cases_store
    contenu = dossier_contenu()
    if contenu is None:      # dossier de contenu introuvable : la partie est inconnue, sans arrêt (R-77, D7)
        return {"state": "content_unknown"}
    auteur = cases_store.resolve_author(contenu)
    if not auteur:
        return {"state": "no_author"}
    try:
        dus = bilans(auteur, jour)
    except Indisponible:
        return {"state": "unavailable"}
    except (Exception, SystemExit):      # Injoignable et toute autre erreur : jamais son texte
        return {"state": "unreachable"}
    return {"state": "ok", "due": len(dus), "decision_required": sum(1 for b in dus if b.get("decision_required"))}


def partie_file(jour: dt.date) -> dict:
    try:
        import roadmap
        cache = roadmap.lit_cache()
        if cache is None:
            return {"state": "no_cache"}
        fonctionnalites = roadmap.analyse_github(cache[0])[0]
        pretes = sum(1 for f in fonctionnalites if f["open"] and f["status"] == "Ready")
        date = str(cache[1])
    except Exception:
        return {"state": "no_cache"}
    return {"state": "ok", "ready": pretes, "cache_date": date if date != jour.isoformat() else None}


def partie_doctor() -> dict:
    chemin = dossier_donnees() / "doctor-etat.json"
    if not chemin.exists():
        return {"state": "absent"}
    etat = lire_objet(chemin)
    try:
        date = dt.date.fromisoformat(str(etat["checked_at"])[:10]).isoformat()
        problemes = etat["counts"]["problem"]
        if not isinstance(problemes, int) or isinstance(problemes, bool):
            raise TypeError
    except (TypeError, KeyError, ValueError):
        return {"state": "unreadable"}
    return {"state": "problems" if problemes else "ok", "date": date, "problems": problemes}


def lignes(parties: dict, t: Messages) -> list[str]:
    sortie = []
    v = parties["watch"]
    if v["state"] == "done":
        base = t("watch_done", n=v["retained"]) if v["retained"] is not None else t("watch_done_no_triage")
        sortie.append(base + (t("catch_up") if v["catch_up"] else ""))
    elif v["state"] == "failed":
        etapes = v["failed_steps"]
        sortie.append(t("watch_failed", n=len(etapes), steps=", ".join(etapes)) if etapes else t("watch_failed_unknown"))
    else:
        sortie.append(t("watch_unknown"))
    b = parties["reviews"]
    if b["state"] == "ok":
        if not b["due"]:
            sortie.append(t("reviews_none"))
        elif b["decision_required"]:
            sortie.append(t("reviews_decision", n=b["due"], m=b["decision_required"]))
        else:
            sortie.append(t("reviews", n=b["due"]))
    elif b["state"] == "unreachable":
        sortie.append(t("reviews_unreachable"))
    elif b["state"] == "unavailable":
        sortie.append(t("reviews_unavailable"))
    elif b["state"] == "content_unknown":
        sortie.append(t("reviews_content_unknown"))
    f = parties["queue"]
    if f["state"] == "ok":
        sortie.append(t("queue_older", n=f["ready"], date=f["cache_date"]) if f["cache_date"] else t("queue", n=f["ready"]))
    else:
        sortie.append(t("queue_no_cache"))
    d = parties["doctor"]
    if d["state"] == "ok":
        sortie.append(t("doctor_ok", date=d["date"]))
    elif d["state"] == "problems":
        sortie.append(t("doctor_problems", date=d["date"], n=d["problems"]))
    elif d["state"] == "unreadable":
        sortie.append(t("doctor_unreadable"))
    else:
        sortie.append(t("doctor_absent"))
    return sortie


# --- notification : une fois par jour, sous le planificateur seulement -------------------------------------------------------------

def notifier(titre: str, corps: str) -> bool:
    commande = ["osascript"]
    for ligne in SCRIPT_OSASCRIPT:
        commande += ["-e", ligne]
    try:
        return subprocess.run(commande + [titre, corps], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ecrire_memoire(jour: dt.date) -> bool:
    cible = dossier_donnees() / MEMOIRE
    temporaire = cible.with_name(f".{MEMOIRE}.{os.getpid()}.tmp")
    try:
        descripteur = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descripteur, "w", encoding="utf-8") as fichier:
            json.dump({"date": jour.isoformat()}, fichier)
        os.replace(temporaire, cible)
        return True
    except OSError:
        try:
            temporaire.unlink()
        except OSError:
            pass
        return False


def main(argv=None, reviews=None) -> int:
    """`reviews(auteur, jour)` remplace la lecture de la base (tests)."""
    parser = argparse.ArgumentParser(prog="morning_summary.py", description="Résumé du matin de PMZilla Lab.")
    add_language_option(parser)
    parser.add_argument("--json", action="store_true", help="affiche les parties au format JSON")
    parser.add_argument("--notify", action="store_true", help="envoie le résumé en notification (avec PMZILLA_SUMMARY_NOTIFY=1)")
    parser.add_argument("--failed-steps", default="", help="étapes en échec de la veille, séparées par une virgule (watch.sh seulement)")
    args = parser.parse_args(argv)
    t = Messages(CATALOGS, args.language)
    jour = aujourdhui()
    etapes = [e.strip() for e in args.failed_steps.split(",") if e.strip()]
    parties = {"watch": partie_veille(jour, etapes), "reviews": partie_bilans(jour, reviews or bilans_de_la_base),
               "queue": partie_file(jour), "doctor": partie_doctor()}
    texte = lignes(parties, t)
    if args.json:
        print(json.dumps(parties, ensure_ascii=False, indent=2))
    else:
        print(t("title"))
        for ligne in texte:
            print(ligne)
    if not (args.notify and os.environ.get(VARIABLE_PLANIFIE) == "1"):
        return 0
    donnees = dossier_donnees()
    if (donnees / INTERRUPTEUR).exists():
        print(t("switched_off"))
        return 4
    memoire = lire_objet(donnees / MEMOIRE)
    if memoire is not None and memoire.get("date") == jour.isoformat():
        print(t("already_sent"))
        return 3
    if not notifier(t("title"), " ; ".join(texte)):
        print(t("notify_failed"))
        return 1
    if not ecrire_memoire(jour):
        print(t("memory_not_written"), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
