#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PMZilla Lab : le journal des trains, seul écrivain (change autonomous-trains-merge, design D4 et D19).

    python3 -I tools/train_record.py append --heure <AAAA-MM-JJTHH:MM:SSZ> --code <c> --sens <s> --mode <m> --n <n> --sommets <sha,sha> ...
    python3 -I tools/train_record.py list [--json]
    (--language fr|en avant la commande)

Le journal est le fichier `trains/journal.jsonl` du dossier de données du lab (hors Git, propriétaire seul, un objet JSON par ligne),
lu par le passage et par les contrôles de fin, écrit par ce module seulement. Le seul appelant d'`append` est le piège de sortie de
tools/finish_train.sh, une fois le code et le sens de la bannière calculés et avant la libération du verrou de fin : un enregistrement pour chaque
lancement qui a pris le verrou et qui n'est pas un essai rapide. `append` retire d'abord, sous le verrou du journal, les enregistrements de plus d'un
an, puis ajoute la ligne (remplacement atomique du fichier). `list` est en lecture seule et permis en session.

Champs (clés ASCII) : `format` 1, `heure` (UTC), `code`, `sens` (fusionne, essai, refuse ou interrompu), `mode` (auto ou manuel), `n`, `sommets`
(40 hexadécimaux, dans l'ordre du train), `sommet_train`, `main_avant`, `main_apres`, `runner` (remplace ou conteneur), `base` et `front` (booléens :
contrôle 14 ou contrôle 16 applicable à l'arbre du train), `politique` (les raisons de la politique automatique sur le code 84, vide sinon), `duree_s`,
`etape` (l'étape de la bannière, vide pour le code 0). Jamais un nom de branche, de personne ni une clé de ticket : le CLI prend ses champs en
arguments, n'accepte aucun nom, et chaque champ a une forme fermée (un champ hors forme sort en 2 sans rien écrire).

Codes de sortie : 0 fait ; 2 usage ou champ refusé ; 4 journal illisible ou non inscriptible, dossiers du lab introuvables (le type seulement pour une
erreur inattendue, jamais de trace de pile).

Phrases clés : `train_record : journal des trains illisible : ligne <n>` (jamais le contenu de la ligne) ;
`train_record : <n> enregistrement(s) retiré(s) (plus d'un an)`.

Remplace : rien (nouvelle preuve). Retrait : permanent tant que l'activation de la fusion automatique lit ce journal.
"""
from __future__ import annotations

import argparse
import calendar
import contextlib
import fcntl
import json
import os
import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths  # noqa: E402
from messages import Messages, add_language_option  # noqa: E402
from train_record_messages import CATALOGS  # noqa: E402

FORMAT = 1
FOLDER = "trains"              # sous le dossier de données du lab (D4), pas sous train-auto/ (la liste prête, l'arrêt et l'activation de tools/train_ready.py et tools/train_auto.py)
FILE_NAME = "journal.jsonl"
LOCK_NAME = "journal.lock"
KEEP_DAYS = 365
SENSES = ("fusionne", "essai", "refuse", "interrompu")
MODES = ("auto", "manuel")
RUNNERS = ("remplace", "conteneur")
MAX_BRANCHES = 6
TIME_FIELD = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", re.ASCII)
HEX40 = re.compile(r"[0-9a-f]{40}")
REASON = re.compile(r"[a-z]+(-[a-z]+)*")
STEP = re.compile(r"[A-Za-zà-ÿœ0-9 '’()-]{0,60}")   # une étape de la bannière (« passe Mac », « contrôle 14 »…) : lettres, chiffres, espaces ; jamais « / », « : », « . » ni « _ »
TICKET = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")     # une clé de ticket ne passe pas par l'étape


class Unreadable(Exception):
    """Le journal est illisible : `line` est le numéro de la ligne fautive (jamais son contenu), None quand c'est le fichier."""

    def __init__(self, line=None):
        super().__init__(str(line))
        self.line = line


class Invalid(Exception):
    """Un champ hors forme : `field` est son nom."""

    def __init__(self, field):
        super().__init__(field)
        self.field = field


# --- chemins ------------------------------------------------------------------------------------------------------------------------

def folder():
    return lab_paths.data_folder() / FOLDER


def record_path():
    return folder() / FILE_NAME


def ensure_folder():
    dossier = folder()
    dossier.mkdir(parents=True, exist_ok=True)
    os.chmod(dossier, 0o700)
    return dossier


def parse_time(texte):
    """Les secondes depuis l'époque d'une heure UTC `AAAA-MM-JJTHH:MM:SSZ` ; ValueError sinon."""
    if not TIME_FIELD.fullmatch(texte):
        raise ValueError(texte)
    return calendar.timegm(time.strptime(texte, "%Y-%m-%dT%H:%M:%SZ"))


def now_iso(ts=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if ts is None else ts))


# --- validation : chaque champ a une forme fermée, aucun nom ne passe ---------------------------------------------------------------

def _hex_or_empty(nom, valeur):
    if not isinstance(valeur, str) or not (valeur == "" or HEX40.fullmatch(valeur)):
        raise Invalid(nom)
    return valeur


def _integer(nom, valeur, bas, haut):
    if isinstance(valeur, bool) or not isinstance(valeur, int) or not bas <= valeur <= haut:
        raise Invalid(nom)
    return valeur


def build_record(fields):
    """L'enregistrement validé (format 1) pour des champs ; Invalid(champ) pour le premier champ hors forme. Les clés attendues sont exactement celles
    de D4 : une clé en trop ou en moins est refusée."""
    attendus = {"heure", "code", "sens", "mode", "n", "sommets", "sommet_train", "main_avant", "main_apres", "runner", "base", "front",
                "politique", "duree_s", "etape"}
    if not isinstance(fields, dict) or set(fields) != attendus:
        raise Invalid("champs")
    heure = fields["heure"]
    if not isinstance(heure, str) or not TIME_FIELD.fullmatch(heure):
        raise Invalid("heure")
    sommets = fields["sommets"]
    if not isinstance(sommets, list) or len(sommets) > MAX_BRANCHES or not all(isinstance(s, str) and HEX40.fullmatch(s) for s in sommets):
        raise Invalid("sommets")
    politique = fields["politique"]
    if not isinstance(politique, list) or not all(isinstance(r, str) and REASON.fullmatch(r) for r in politique):
        raise Invalid("politique")
    etape = fields["etape"]
    if not isinstance(etape, str) or not STEP.fullmatch(etape) or TICKET.search(etape):
        raise Invalid("etape")
    for nom, permis in (("sens", SENSES), ("mode", MODES), ("runner", RUNNERS)):
        if fields[nom] not in permis:
            raise Invalid(nom)
    for nom in ("base", "front"):
        if not isinstance(fields[nom], bool):
            raise Invalid(nom)
    return {"format": FORMAT, "heure": heure, "code": _integer("code", fields["code"], 0, 255), "sens": fields["sens"], "mode": fields["mode"],
            "n": _integer("n", fields["n"], 1, MAX_BRANCHES), "sommets": list(sommets),
            "sommet_train": _hex_or_empty("sommet_train", fields["sommet_train"]), "main_avant": _hex_or_empty("main_avant", fields["main_avant"]),
            "main_apres": _hex_or_empty("main_apres", fields["main_apres"]), "runner": fields["runner"], "base": fields["base"],
            "front": fields["front"], "politique": list(politique), "duree_s": _integer("duree_s", fields["duree_s"], 0, 10**7), "etape": etape}


# --- lecture et écriture ------------------------------------------------------------------------------------------------------------

def read_records(path=None):
    """Les enregistrements dans l'ordre du fichier ; un journal absent est vide ; Unreadable (numéro de ligne, jamais le contenu) quand le fichier ou
    une ligne ne se lit pas. Seul lecteur : le passage et les contrôles de fin lisent par cette fonction."""
    chemin = Path(path) if path is not None else record_path()
    try:
        texte = chemin.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError):
        raise Unreadable(None) from None
    resultat = []
    for n, ligne in enumerate(texte.splitlines(), start=1):
        try:
            r = json.loads(ligne)
            if not isinstance(r, dict) or r.get("format") != FORMAT or not TIME_FIELD.fullmatch(r.get("heure", "")):
                raise ValueError
        except (ValueError, TypeError):
            raise Unreadable(n) from None
        resultat.append(r)
    return resultat


def _atomic_write(chemin, records):
    temporaire = chemin.parent / f".{chemin.name}.tmp-{os.getpid()}"
    fd = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporaire, chemin)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporaire)
        raise


@contextlib.contextmanager
def _locked():
    fd = os.open(ensure_folder() / LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _purged(records, now):
    limite = now - KEEP_DAYS * 86400
    return [r for r in records if parse_time(r["heure"]) >= limite]


def purge(now=None):
    """Retire les enregistrements de plus d'un an (`now` : secondes UTC) et rend leur nombre ; le fichier n'est réécrit que s'il y en a. Unreadable
    quand le journal ne se lit pas (rien n'est alors réécrit)."""
    now = time.time() if now is None else now
    with _locked():
        records = read_records()
        gardes = _purged(records, now)
        if len(gardes) != len(records):
            _atomic_write(record_path(), gardes)
        return len(records) - len(gardes)


def append(fields, now=None):
    """Valide, retire d'abord les enregistrements de plus d'un an, puis ajoute la ligne, sous le verrou du journal. Rend (enregistrement, nombre retiré).
    Invalid(champ) avant toute écriture ; Unreadable quand le journal existant ne se lit pas (il n'est jamais écrasé)."""
    record = build_record(fields)
    now = time.time() if now is None else now
    with _locked():
        records = read_records()
        gardes = _purged(records, now)
        _atomic_write(record_path(), gardes + [record])
        return record, len(records) - len(gardes)


# --- commandes ----------------------------------------------------------------------------------------------------------------------

def _csv(texte):
    return [x for x in texte.split(",") if x != ""]


def fields_of(args):
    return {"heure": args.heure or now_iso(), "code": args.code, "sens": args.sens, "mode": args.mode, "n": args.n, "sommets": _csv(args.sommets),
            "sommet_train": args.sommet_train, "main_avant": args.main_avant, "main_apres": args.main_apres, "runner": args.runner,
            "base": args.base, "front": args.front, "politique": _csv(args.politique), "duree_s": args.duree_s, "etape": args.etape}


def cmd_append(args, t):
    try:
        record, retires = append(fields_of(args))
    except Invalid as e:
        print(t("invalid", field=e.field), file=sys.stderr)
        return 2
    if retires:
        print(t("purged", n=retires))
    print(t("appended", code=record["code"], sens=record["sens"]))
    return 0


def cmd_list(args, t):
    records = read_records()
    if args.json:
        print(json.dumps({"format": FORMAT, "records": records}, ensure_ascii=False))
        return 0
    if not records:
        print(t("list_empty"))
    for r in records:
        print(t("list_line", heure=r["heure"], code=r["code"], sens=r["sens"], mode=r["mode"], n=r["n"], runner=r["runner"], duree=r["duree_s"]))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="train_record.py", description="Journal des trains (seul écrivain).")
    add_language_option(p)
    sub = p.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="écrit les enregistrements (lecture seule)")   # d'abord : le manuel construit son exemple depuis la première sous-commande
    ls.add_argument("--json", action="store_true")
    a = sub.add_parser("append", help="ajoute un enregistrement (appelé par le piège de sortie de tools/finish_train.sh)")
    a.add_argument("--heure", default="", help="heure UTC, AAAA-MM-JJTHH:MM:SSZ (défaut : maintenant)")
    a.add_argument("--code", type=int, required=True)
    a.add_argument("--sens", required=True)
    a.add_argument("--mode", required=True)
    a.add_argument("--n", type=int, required=True)
    a.add_argument("--sommets", default="", help="sommets des branches, séparés par des virgules, dans l'ordre du train")
    a.add_argument("--sommet-train", default="")
    a.add_argument("--main-avant", default="")
    a.add_argument("--main-apres", default="")
    a.add_argument("--runner", required=True)
    a.add_argument("--base", action="store_true")
    a.add_argument("--front", action="store_true")
    a.add_argument("--politique", default="", help="raisons de la politique automatique, séparées par des virgules")
    a.add_argument("--duree-s", type=int, required=True)
    a.add_argument("--etape", default="")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)   # une erreur d'usage sort avec le code 2
    t = Messages(CATALOGS, args.language)
    try:
        return {"append": cmd_append, "list": cmd_list}[args.cmd](args, t)
    except Unreadable as e:
        print(t("unreadable", n=e.line) if e.line else t("unreadable_file"), file=sys.stderr)
        return 4
    except lab_paths.LabPathsError:
        print(t("folders"), file=sys.stderr)
        return 4
    except OSError:
        print(t("not_writable"), file=sys.stderr)
        return 4
    except Exception as e:   # jamais de trace de pile : le type seulement
        print(t("unexpected", kind=type(e).__name__), file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
