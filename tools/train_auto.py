#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PMZilla Lab : le passage du train automatique (change autonomous-trains-observe, R-166, design D1 à D11, puis change autonomous-trains-merge, tranche 3, design D5, D6, D9 à D17 :
le mode de fusion, activé par l'auteur seul).

    python3 -I tools/train_auto.py pass
    python3 -I tools/train_auto.py status [--json]
    python3 -I tools/train_auto.py observation [--days N] [--json]
    python3 -I tools/train_auto.py arret [--raison <code>]
    python3 -I tools/train_auto.py reprendre
    python3 -I tools/train_auto.py plist
    python3 -I tools/train_auto.py activation [--json]
    python3 -I tools/train_auto.py activer
    python3 -I tools/train_auto.py desactiver
    (--language fr|en avant la commande)

Deux modes. L'OBSERVATION (pas de fichier d'activation, ou activation invalide) : le passage décide et observe, il ne fusionne jamais ; sa seule fin est l'essai
`finish_train.sh --essai <branches retenues>` du dossier d'exécution (jamais de réponse à la question o/n, jamais d'avance rapide, de push, d'écriture de référence, de
fetch, de gh, de Jira, de base, de dbtest ni de runner). La FUSION (fichier d'activation valide, D6) : après un essai final à 0 le passage lance le train réel
`finish_train.sh --auto <branches de l'essai>` (trois au plus, jamais relancé, jamais une branche ajoutée après l'essai) dans un environnement sans FINISH_TRAIN_* ni jeton de
verrou, entrée standard fermée, dans son propre groupe de processus, avec un délai de trois heures (TERM au groupe, puis l'arrêt est armé). Il lit son code et son enregistrement
du journal des trains, applique la table des codes (D10), l'exclusion `echec-au-sommet` (D11), écrit une ligne dans `etapes/fusions-auto.md` (D14, ajout seul, noms masqués par la
garde) et envoie une notification (D15, sans nom de branche). Un essai final non nul en fusion est rapporté de même (D12). Il est lancé par la tâche launchd de l'auteur ou par
l'auteur dans le Terminal, jamais dans une session Claude Code. Les contrôles se suivent dans l'ordre du design D2 ; le premier qui échoue arrête le passage, qui ne lance
rien et ne change rien (sauf le fichier d'arrêt de la reprise sur arrêt disparu, et le journal) :
  1 arrêt d'urgence ; 2 hors session ; la version de l'interpréteur (sous 3.10 : attente `python-ancien`, sans arrêt) ; 3 fenêtre (quatorze passages, un par heure de 8 h à 21 h, D13), puis en fusion l'heure de départ la plus tardive (`latest_start`, D9), puis l'état
  de l'étape précédente : présent mais illisible, il donne `attente` `etat-illisible` (les trains refusés ne sont pas connus ; l'état n'est alors pas réécrit ; absent, il n'y a
  rien à lire) ;
  4 état du matin (code de morning_state.sh) ; 5 verrou de fin (le verrou du runner de session est retiré avec
  T2 de tooling-proof-in-container : plus d'attente `runner-session`) (nouvel essai toutes les cinq minutes jusqu'à la fin de la tolérance) ; 6 espace de travail sur main et propre, `git ls-remote` sans
  invite égal au main local, dossier d'exécution à jour ; 7 crochets (install_hooks.sh --verify) et identité Git, état du contrôle doctor
  du crochet reference-transaction : noté en observation, bloquant en fusion quand il est rouge ou absent (D17, `crochets-doctor`) ; 8 liste prête ; 9 contrôle de chaque ligne ;
  10 plafond de trois branches (PLAFOND_TRAIN, D9) ; 11 essai ; 12 en fusion, le train réel, précédé de trois relectures juste avant son lancement (l'essai peut durer) :
  l'arrêt (`arret`), l'activation (retirée par `desactiver` : décision `observe` `essai`, aucun train) et l'heure de départ la plus tardive (`depart-limite`), puis l'état,
  avec les ensembles refusés, est écrit tout de suite après le train, avant le compte rendu et le journal (l'écriture finale reste).
Il lit les codes de sortie des outils qu'il appelle, jamais leurs phrases (sauf l'analyseur des refus 62 et 64 de l'essai, épinglé par des
tests qui lancent le vrai finish_train.sh).

pass : un passage ; il journalise un enregistrement (train-auto/journal.jsonl, purgé après un an) et écrit l'état (train-auto/etat.json).
status : le dernier état (`last_state`), permis en session. observation : le bilan des jours observés (`observation_summary`), permis en
    session : par jour et au total, les décisions et raisons, les branches retenues par un essai à 0 que l'auteur a ensuite fusionnées
    (avec le délai), celles qu'il a fusionnées alors que le passage les avait écartées ou sans qu'elles aient été listées.
arret : crée le fichier d'arrêt `train-auto/arret` et journalise ; permis en session (il ne fait que renforcer). reprendre : le retire
    et journalise ; refusé en session (code 3). Un arrêt armé par le passage après le code 65 ou 79 de l'essai ; un fichier d'arrêt
    disparu sans « reprendre » est recréé et le passage décide « arrêté » (arret-disparu).
activation : la série de trains verts sur le conteneur que demande l'activation (D5), calculée à chaque appel depuis le journal des trains ; permis en session ; `--json`
    donne le même dictionnaire que le texte. activer : le geste unique de l'auteur (D6), refusé en session (3) et quand la condition n'est pas remplie (7) ; écrit
    `train-auto/fusion-active` par un fichier temporaire renommé. desactiver : permis à tous (il ne fait que renforcer), retire ce fichier, ne touche ni l'arrêt ni la liste.
plist : écrit le modèle launchd (un StartCalendarInterval par heure de passage, quatorze de 8 h à 21 h, ni RunAtLoad, ni KeepAlive, ni StartInterval, et le PATH du job
    dans EnvironmentVariables) depuis les constantes de l'outil, sous un interpréteur de 3.10 ou plus (code 8 sinon) ; l'auteur seul l'installe et le charge.

Les heures de passage (WINDOWS, D13), la tolérance, l'heure de départ la plus tardive (`latest_start`, repli DEPART_LIMITE_REPLI 20 h 30), le plafond du passage (PLAFOND_TRAIN, 3) et
le délai du train (TRAIN_TIMEOUT, 3 heures) sont des constantes du code ; le plafond de la liste est CAP de tools/train_ready.py. Les noms de branche passent la garde des noms
sensibles avant toute écriture : un nom trouvé devient `branche masquée` et sa ligne est écartée (`nom`) ; une garde impossible donne `garde-noms`.

Variables (tests) : TRAIN_AUTO_NOW (secondes, horloge imposée ; les attentes avancent alors une horloge virtuelle), TRAIN_AUTO_REAL_SLEEP
(secondes réellement dormies par attente en horloge imposée, 0 par défaut), TRAIN_AUTO_TRAIN_TIMEOUT et TRAIN_AUTO_TERM_GRACE (secondes, délai du train réel et
délai de grâce après TERM), TRAIN_AUTO_NOTIFIER (commande qui remplace osascript, le texte en dernier argument), PMZILLA_LAB_WORKSPACE, PMZILLA_LAB_RUN, PMZILLA_LAB_DATA,
PMZILLA_LAB_SENSITIVE_NAMES, PILOT_LSOF (liste des processus, comme tools/pilot.py), XPC_SERVICE_NAME (l'étiquette launchd, pour l'appelant).

Le KILL (R-20261107-8 Q1) : un train qui ignore TERM reçoit KILL, tout son groupe de processus, TERM_GRACE (300 s) après TERM. Il ne remplace rien ; permanent, parce que sans lui
un train qui ignore TERM garde le verrou de fin. Après tout KILL le passage arme l'arrêt (comme pour une interruption, D10) : aucun train automatique ne repart avant
que l'auteur lance `reprendre`. TRAIN_AUTO_TRAIN_TIMEOUT et TRAIN_AUTO_TERM_GRACE sont des réglages de test (le délai et la grâce réels sont les constantes TRAIN_TIMEOUT
et TERM_GRACE) ; remplacent : rien ; condition de retrait : elles tombent avec le passage automatique (R-166).

Codes de sortie : 0 fait (un passage rend 0 quelle que soit sa décision, qui est au journal) ; 2 usage ;
  3 refusé dans une session Claude Code (`pass`, `reprendre`, `activer`) ;
  4 dossiers du lab ou dossier de données inutilisables, journal ou état non inscriptible (rien n'est décidé), journal des trains illisible (`activation`, `activer`) ;
  5 un autre passage est en cours (le verrou propre du passage) ; 6 erreur inattendue (le type seulement, jamais de trace) ;
  7 `activer` : la condition de la série de cinq trains verts n'est pas remplie, ou l'arrêt d'urgence est actif, ou aucun essai à 0 lancé par launchd depuis le dernier chargement du modèle (une ligne `manque <libellé>` par condition, rien d'écrit) ;
  8 modèle launchd refusé : interpréteur de la génération (`plist` : interpréteur de moins de 3.10, ou dossier de l'interpréteur sans `python3` identique, rien sur la sortie standard).

Faux 65 du 7 novembre (décisions R-20261110-12 à -14 ; le job n'avait que le PATH par défaut de launchd, donc le python3 3.9 du système) : le modèle porte un `EnvironmentVariables`
avec le seul `PATH` du job, calculé à chaque appel par `job_path` (le dossier de l'interpréteur de la génération, le dossier fnm par défaut du compte, puis `JOB_PATH_SYSTEME`, sans doublon ;
`FNM_DIR` est ignorée, aucun chemin du compte n'est écrit dans un fichier suivi). Remplace : le PATH par défaut de launchd pour le job. Retrait : permanent tant que le job existe.
L'interpréteur du job (R-20261110-34 et -36) : `ProgramArguments` commence par l'interpréteur de la génération (`sys.executable`, celui dont le dossier ouvre le PATH), pour que les scripts enfants
(`doctor.py`, `finish_checks.py`) héritent du bon `python3` ; remplace : le `/usr/bin/python3` du système ; retrait : permanent tant que le job existe. Au début d'un passage, l'outil vérifie sa version :
sous 3.10, décision `attente` sous la raison `python-ancien`, sans armer l'arrêt (le module reste importable sous 3.9) ; ne remplace rien ; retrait : permanent tant que le job existe.
`installed_plist_check()` et le contrôle doctor `train-auto-plist` vérifient aussi que l'interpréteur de `ProgramArguments` est le `python3` du premier dossier du PATH (même chemin réel) : sinon la clé
`ProgramArguments` est un écart ; ne remplace rien ; retrait : avec le job.
Le refus 8 de `plist` ne remplace rien ; retrait : permanent tant que le job existe. `stop_info()` est la source unique de l'arrêt pour les autres outils (lecture seule, jamais d'exception) ;
ne remplace rien ; retrait : avec le passage automatique (R-166). Le code `arret-actif` de l'activation (pas d'activation pendant l'arrêt) ne remplace rien ; retrait : permanent tant que
l'activation existe. Le code `essai-launchd` de l'activation (D10 : un essai final à 0 lancé par launchd, avec l'empreinte `env_job` du modèle installé, depuis sa dernière modification ; le code manque aussi tant que le modèle installé n'est pas à l'état ok du contrôle F6, R-20261110-39 ;
`env_job` est l'empreinte du PATH reçu, écrite au passage d'un appelant launchd, nulle sinon, jamais le chemin) ne remplace rien ; retrait : permanent tant que l'activation existe.
`installed_plist_check()` (lecture seule) est partagé avec le doctor ; ne remplace rien ; retrait : avec le job (R-20261110-14). Les essais en 68 et en 76 n'arment aucun arrêt
(seuls 65 et 79 l'arment, inchangé).

Phrases clés : `train_auto : observation : <n> branche(s) retenue(s), <k> écartée(s) ; essai code <c>` ; `train_auto : attente : <libellé>` ;
`train_auto : rien à faire` ; `train_auto : arrêté (arrêt d'urgence actif)` ; `train_auto : écartée : <branche> : <libellé>` ;
`train_auto : session Claude Code, lancement refusé` ; `train_auto : un autre passage est en cours` ; `train_auto : arrêt posé` ;
`train_auto : arrêt levé` ; `train_auto : arrêt armé après le code <c>` ; `train_auto : arrêt disparu sans « reprendre » : recréé` ;
`train_auto : fusion automatique : <n> branche(s) ; train code <c> (<sens>), <m> min` ; `train_auto : pour l'auteur : <suite>` ; `train_auto : activation : <k> train(s) de suite sur 5 requis` ;
`train_auto : activation : manque <libellé>` ; `train_auto : activation refusée : condition non remplie` ; `train_auto : fusion automatique activée` ;
`train_auto : fusion automatique désactivée` (ou `déjà désactivée`) ; `train_auto : compte rendu non écrit (écriture impossible)` ; `train_auto : notification non envoyée`.

Lecture de l'activation (change autonomous-trains-merge, tranche 1, D5 et D6) : `activation_path()` (`train-auto/fusion-active` du dossier de données),
`activation_state()` (« absent » : mode observation ; « valide » ; « invalide » au moindre doute) et `activation_valid()`, seul lecteur, en lecture seule ; la politique de
fin (tools/finish_checks.py, `auto_policy`) les appelle. Un fichier d'activation n'est valide que s'il est un fichier ordinaire lisible par le propriétaire seul, de format 1,
d'une série de cinq sommets de trains distincts dont chacun est un enregistrement compté du journal des trains (tools/train_record.py : train de l'auteur, fusionné, sur le
conteneur). Depuis la tranche 3, `activer` écrit ce fichier (le geste unique de l'auteur, quand `activation_status()` dit la série de cinq trains verts remplie), `desactiver`
le retire, et le mode de fusion du passage s'en sert ; le lecteur reste `activation_valid()`, en lecture seule.

Les codes ci-dessus sont déclarés ici, source du manuel, et non dans tools/finish_codes.yaml (registre des scripts de fin). La table des codes du train réel (CODE_TABLE, D10) est
rangée par les codes de ce registre, qui en est la source : un test échoue quand un code `utilise` ou `reserve` n'a pas de ligne.
Remplace : rien sur le chemin de l'auteur (train à la main, fin unitaire, question o/n restent entiers). La restriction d'observation d'autonomous-trains-observe (« Retrait de la
restriction d'observation : tombe avec R-167 (T5), qui ajoute le lancement réel ») est tombée avec la tranche 3 d'autonomous-trains-merge (R-167) : le passage lance le train réel
après activation, jamais sans. L'outil : permanent tant que le travail du train peut être lancé par la tâche.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import plistlib
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths  # noqa: E402
import pilot  # noqa: E402
import sensitive_names  # noqa: E402
import train_ready  # noqa: E402
import train_record  # noqa: E402
from messages import Messages, add_language_option  # noqa: E402
from train_auto_messages import CATALOGS, decision_label, label as reason_label  # noqa: E402

LABEL = "com.pmzilla.train-auto"
# (heure du passage, heure de départ la plus tardive du passage), heure de Paris : quatorze passages, un par heure de 8 h à 21 h (autonomous-trains-merge, D13,
# R-20261101-83). Remplace les deux passages de 12 h et de 17 h 30 d'autonomous-trains-observe (D10). Retrait : permanent ; cette constante est la seule copie de l'horaire.
WINDOWS = tuple((f"{heure:02d}:00", f"{heure:02d}:25") for heure in range(8, 22))
TOLERANCE_MINUTES = 30
RETRY_SECONDS = 300
REMOTE_TIMEOUT = 30
CHECK_TIMEOUT = 120
TRIAL_TIMEOUT = 1800
# Mode de fusion (autonomous-trains-merge, tranche 3, D9 à D15).
PLAFOND_TRAIN = 3   # au plus trois branches retenues par passage, dans les deux modes (D9 point 1, Q183) ; la liste garde son plafond de cinq
TRAIN_TIMEOUT = 10800   # trois heures (D9 point 4) ; TERM au groupe de processus du train au-delà, puis l'arrêt est armé
TERM_GRACE = 300   # secondes laissées au train pour sortir après TERM avant KILL
DEPART_LIMITE_REPLI = "20:30"   # heure de départ la plus tardive tant que moins de dix trains verts du conteneur sont connus (D9), revue après la mesure
DEPART_FIN_MINUTES = 22 * 60
DEPART_MARGE_MINUTES = 10
NOTIFY_TIMEOUT = 10   # secondes (D15)
REPORT_NAME = "fusions-auto.md"
REFUS_CODES = (62, 64, 69, 70, 71, 82, 83, 84)   # D11 : un train refusé pour son contenu n'est pas rejoué sur les mêmes sommets
# Le PATH du job (faux 65, D1) : les dossiers du système sont la seule constante ; celui de l'interpréteur et celui de fnm sont calculés (jamais un chemin du compte ici).
JOB_PATH_SYSTEME = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin")
FNM_DEFAULT_RELATIVE = ".local/share/fnm/aliases/default/bin"   # sous le dossier personnel ; FNM_DIR est ignorée, pour que le doctor et la génération calculent la même valeur
PYTHON_MINIMUM = (3, 10)
INSTALLED_PLIST_RELATIVE = "Library/LaunchAgents"
VERSION_TIMEOUT = 5   # secondes, `python3 --version` du contrôle du modèle installé (D11)
LOG_RELATIVE = "Library/Logs/pmzilla-train-auto.log"
KEEP_DAYS = 365
TZ_NAME = "Europe/Paris"
SESSION_VARIABLE = "CLAUDECODE"
TRIAL_PREFIX = "FINISH_TRAIN_"
STOP_NAME = "arret"
JOURNAL_NAME = "journal.jsonl"
STATE_NAME = "etat.json"
PASS_LOCK_NAME = "passage.lock"
JOURNAL_LOCK_NAME = "journal.lock"
FRONT_LIST = "tools/finish_e2e_paths.txt"   # source unique des chemins d'interface (B2), lue comme la fin la lit ; permanent tant que la fin l'exige
EXPECTED_FORMAT = 1


class Stop(Exception):
    def __init__(self, code, message=""):
        super().__init__(message)
        self.code = code
        self.message = message


# --- horloge, environnement, sous-processus ----------------------------------------------------------------------------------------

class Clock:
    """L'heure du passage. TRAIN_AUTO_NOW l'impose (tests) : attendre avance alors une horloge virtuelle (et dort réellement
    TRAIN_AUTO_REAL_SLEEP secondes, 0 par défaut) pour qu'un essai de verrou ne dure pas cinq minutes."""

    def __init__(self, env):
        voulu = env.get("TRAIN_AUTO_NOW", "")
        self.base = int(voulu) if voulu.isdigit() else None
        self.offset = 0.0
        try:
            self.real = float(env.get("TRAIN_AUTO_REAL_SLEEP", "0"))
        except ValueError:
            self.real = 0.0

    def now(self):
        return self.base + self.offset if self.base is not None else time.time()

    def sleep(self, secondes):
        if self.base is None:
            time.sleep(secondes)
            return
        self.offset += secondes
        if self.real > 0:
            time.sleep(min(secondes, self.real))


def paris(ts):
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(ts, ZoneInfo(TZ_NAME))
    except Exception:   # base de fuseaux absente : UTC, déclaré
        return dt.datetime.fromtimestamp(ts, dt.timezone.utc)


def iso_utc(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch_of(texte):
    return dt.datetime.strptime(texte, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()


def seconds_of_day(ts):
    p = paris(ts)
    return p.hour * 3600 + p.minute * 60 + p.second


def minutes_of(texte):
    h, m = texte.split(":")
    return int(h) * 60 + int(m)


def window_at(ts):
    """(heure d'observation, fin en secondes du jour) de la fenêtre qui contient l'instant, ou None."""
    sec = seconds_of_day(ts)
    for debut, tard in WINDOWS:
        d = minutes_of(debut) * 60
        fin = min(d + TOLERANCE_MINUTES * 60, minutes_of(tard) * 60)
        if d <= sec <= fin:
            return debut, fin
    return None


def paris_zone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(TZ_NAME)
    except Exception:   # base de fuseaux absente : UTC, déclaré
        return dt.timezone.utc


def latest_start(records, day):
    """L'heure de départ la plus tardive du train réel un jour donné (D9, R-20261101-122 Q245) : 22 h, heure de Paris, moins la plus longue `duree_s` des dix derniers
    enregistrements du journal des trains de code 0, de sens `fusionne` et de runner `conteneur`, moins dix minutes, arrondie à la minute inférieure. Avec moins de dix
    tels enregistrements : DEPART_LIMITE_REPLI (20 h 30), revu après la mesure. Rend un datetime de Paris ; `day` est une date. Remplace : rien. Retrait : permanent."""
    durees = [r["duree_s"] for r in records if isinstance(r, dict) and r.get("code") == 0 and r.get("sens") == "fusionne" and r.get("runner") == "conteneur"
              and isinstance(r.get("duree_s"), int) and not isinstance(r.get("duree_s"), bool)]
    zone = paris_zone()
    if len(durees) < 10:
        minutes = minutes_of(DEPART_LIMITE_REPLI)
        return dt.datetime(day.year, day.month, day.day, minutes // 60, minutes % 60, tzinfo=zone)
    fin = dt.datetime(day.year, day.month, day.day, DEPART_FIN_MINUTES // 60, DEPART_FIN_MINUTES % 60, tzinfo=zone)
    return (fin - dt.timedelta(seconds=max(durees[-10:]), minutes=DEPART_MARGE_MINUTES)).replace(second=0, microsecond=0)


def in_session(env):
    return SESSION_VARIABLE in env


def caller_of(env):
    return "launchd" if env.get("XPC_SERVICE_NAME") == LABEL else "terminal"


def clean_env(env):
    """L'environnement des outils appelés : sans jeton de verrou, sans variable FINISH_TRAIN_*. Le marqueur de session reste (R-20261030-01) :
    un outil appelé ne doit jamais perdre la preuve qu'il tourne sous une session."""
    return {k: v for k, v in env.items() if k != "FINISH_LOCK_TOKEN" and not k.startswith(TRIAL_PREFIX)}


def run_command(cmd, cwd, env, timeout, stdout_seul=False):
    """(code, sortie réunie) ; 127 quand la commande ne peut pas tourner, 124 au dépassement du délai (tout le groupe de processus est tué).
    `stdout_seul` (R-20261110-43) : la sortie rendue est celle de stdout seul, stderr est lu puis écarté. Remplace : rien. Retrait : permanent."""
    try:
        proc = subprocess.Popen(cmd, cwd=str(cwd), env=clean_env(env), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, errors="replace", start_new_session=True)
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    try:
        sortie, erreur = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.communicate(timeout=10)
        except (subprocess.SubprocessError, OSError):
            pass
        return 124, ""
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return proc.returncode, (sortie or "") if stdout_seul else (sortie or "") + (erreur or "")


def _signal_group(proc, signum):
    try:
        os.killpg(proc.pid, signum)
    except (ProcessLookupError, PermissionError):
        pass


def _float_of(env, name, default):
    try:
        return float(env[name]) if name in env else float(default)
    except ValueError:
        return float(default)


def run_train_process(cmd, cwd, env, timeout, grace):
    """(code, délai dépassé) du train réel (D9 points 3 et 4) : environnement sans FINISH_TRAIN_* ni jeton de verrou (clean_env), entrée standard fermée, sorties jetées
    (le train écrit son propre journal), dans son propre groupe de processus. Au-delà de `timeout` secondes le groupe reçoit TERM (le train sort en 143 et dit ce qu'il a
    laissé), puis KILL après `grace` secondes. Un signal reçu donne 128 + le signal ; 127 quand le train ne peut pas être lancé. Jamais relancé ici."""
    try:
        proc = subprocess.Popen(cmd, cwd=str(cwd), env=clean_env(env), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    except (OSError, subprocess.SubprocessError):
        return 127, False
    delai = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        delai = True
        _signal_group(proc, signal.SIGTERM)
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            _signal_group(proc, signal.SIGKILL)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
    code = proc.returncode
    if code is None:
        code = 124
    elif code < 0:
        code = 128 - code
    return code, delai


# --- dossier de données : arrêt, journal, état -------------------------------------------------------------------------------------

def data():
    return train_ready.data_dir()


def stop_path():
    return data() / STOP_NAME


STOP_DATE_FORM = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


def stop_info():
    """L'arrêt d'urgence pour les autres outils (faux 65, D7), source unique : lecture seule, jamais d'exception. Rend
    {"format": 1, "state": "absent" | "arrete" | "illisible" | "inconnu", "date": "AAAA-MM-JJ HH:MM" (Paris) | None, "raison": <code> | None}.
    `arrete` : le fichier d'arrêt existe et le dernier enregistrement `arret` du journal porte un champ `paris` de cette forme (`raison` : celle de l'enregistrement, éventuellement None) ;
    `illisible` : le fichier existe mais pas d'enregistrement `arret`, un journal illisible ou un champ `paris` d'une autre forme ; `inconnu` : le dossier de données n'est pas résolu.
    Remplace : rien. Retrait : avec le passage automatique (R-166)."""
    info = {"format": EXPECTED_FORMAT, "state": "inconnu", "date": None, "raison": None}
    try:
        fichier = stop_path()
        dossier = fichier.parent
    except Exception:   # noqa: BLE001 : jamais d'exception ; le dossier de données n'est pas résolu
        return info
    try:
        if not (fichier.exists() or fichier.is_symlink()):
            info["state"] = "absent"
            return info
    except OSError:
        info["state"] = "illisible"
        return info
    info["state"] = "illisible"
    try:
        texte = (dossier / JOURNAL_NAME).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return info
    dernier = None
    for ligne in texte.splitlines():
        try:
            r = json.loads(ligne)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("type") == "arret":
            dernier = r
    if dernier is None:
        return info
    date = dernier.get("paris")
    if not isinstance(date, str) or not STOP_DATE_FORM.match(date):
        return info
    raison = dernier.get("raison")
    info.update(state="arrete", date=date, raison=raison if isinstance(raison, str) else None)
    return info


# --- activation de la fusion automatique : lecture seule (change autonomous-trains-merge, design D5 et D6 ; tranche 1) --------------------
# Cette tranche ne pose que les fonctions de lecture dont la politique de fin a besoin (tools/finish_checks.py, auto_policy) : `activer`, `desactiver`,
# `activation_status` et le mode de fusion du passage viennent avec la tranche 3. Remplace : rien (nouvelle garde de P1). Retrait : permanent tant que le
# mode de fusion existe. Une fausse activation (fichier forgé) est la limite déclarée de D6 : le contrôle ci-dessous relit le journal des trains.
ACTIVATION_NAME = "fusion-active"
SERIES_REQUIRED = 5   # N = 5 trains verts de suite (R-20261101-122 Q242), D5


def activation_path():
    return data() / ACTIVATION_NAME


def record_counted(rec):
    """Un enregistrement du journal des trains compte dans la série quand c'est un train de l'auteur, fusionné, sur le conteneur (D5)."""
    return (isinstance(rec, dict) and rec.get("mode") == "manuel" and rec.get("code") == 0 and rec.get("sens") == "fusionne"
            and rec.get("runner") == "conteneur")


def activation_state():
    """« absent » (aucun fichier : mode observation), « valide » ou « invalide » (fichier présent mais illisible, hors forme, lisible par d'autres que le
    propriétaire, ou dont un sommet de la série n'est pas un enregistrement compté du journal des trains). Lecture seule ; tout doute est « invalide »,
    jamais « valide »."""
    chemin = activation_path()
    if not chemin.exists() and not chemin.is_symlink():
        return "absent"
    try:
        if not chemin.is_file() or chemin.is_symlink() or chemin.stat().st_mode & 0o077:
            return "invalide"
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        serie = donnees["serie"]
        if (not isinstance(donnees, dict) or donnees.get("format") != EXPECTED_FORMAT or not isinstance(donnees.get("heure"), str)
                or not train_record.TIME_FIELD.fullmatch(donnees["heure"]) or not isinstance(serie, list) or len(serie) != SERIES_REQUIRED
                or len(set(serie)) != len(serie) or not all(isinstance(s, str) and train_record.HEX40.fullmatch(s) for s in serie)):
            return "invalide"
        comptes = {r.get("sommet_train") for r in train_record.read_records() if record_counted(r)}
    except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError, train_record.Unreadable, lab_paths.LabPathsError):
        return "invalide"
    return "valide" if all(s in comptes for s in serie) else "invalide"


def activation_valid():
    """Seul lecteur de l'activation (D6) : vrai quand le fichier d'activation est présent et valide. Lecture seule."""
    return activation_state() == "valide"


RESET_CODES = (69, 70, 71, 82)   # D5 : un train de l'auteur rouge sur le conteneur remet la série à zéro (R-20261101-82)
MISSING_CODES = ("serie", "deux-branches", "base-ou-front", "arret-actif", "essai-launchd")


def activation_status(records=None):
    """La série de trains verts de D5, calculée à chaque appel depuis le journal des trains (jamais stockée, aucun compteur : une seule source), du plus récent
    au plus ancien. Compté : un train de l'auteur (`manuel`), code 0, sens `fusionne`, sur le conteneur (`record_counted`). Remise à zéro : un enregistrement `manuel` sur le
    conteneur de code 69, 70, 71 ou 82. Ni l'un ni l'autre : tout autre code, le sens `essai`, le mode `auto` et le runner `remplace`. Remplie quand la série compte
    au moins 5 enregistrements comptés et que, parmi les 5 plus récents, l'un a n >= 2 et l'un touche la base ou l'interface (`base` ou `front`). Rend
    {"format", "met", "series", "required", "missing", "serie"} ; `serie` : les sommets de train des 5 plus récents, du plus ancien au plus récent. Lecture seule.
    Remplace : rien. Retrait : permanent, tant que l'activation existe. `records` : liste donnée (tests) ; sinon le journal des trains (Unreadable si illisible).
    Faux 65 (D9) : en lecture réelle (sans `records`), le code manquant `arret-actif` s'ajoute tant que stop_info() n'est pas `absent` (arrêt d'urgence actif : reprendre d'abord) ;
    avec des `records` donnés, le calcul reste pur (il ne lit pas l'état du disque). Remplace : rien. Retrait : permanent, tant que l'activation existe.
    Faux 65 (D10) : de même en lecture réelle, le code manquant `essai-launchd` s'ajoute (après `arret-actif`) tant que launchd_trial_status(journal des passages, modèle installé) n'est pas
    vrai, et en particulier tant que le modèle installé n'est pas à l'état ok du contrôle F6 (R-20261110-39). Remplace : rien. Retrait : permanent, tant que l'activation existe."""
    lecture_reelle = records is None
    if records is None:
        records = train_record.read_records()
    comptes = []
    for rec in reversed(records):
        if record_counted(rec):
            comptes.append(rec)
        elif (isinstance(rec, dict) and rec.get("mode") == "manuel" and rec.get("runner") == "conteneur" and rec.get("code") in RESET_CODES):
            break
    cinq = list(reversed(comptes[:SERIES_REQUIRED]))
    manque = []
    if len(comptes) < SERIES_REQUIRED:
        manque.append("serie")
    if not any(isinstance(r.get("n"), int) and r["n"] >= 2 for r in cinq):
        manque.append("deux-branches")
    if not any(r.get("base") is True or r.get("front") is True for r in cinq):
        manque.append("base-ou-front")
    if lecture_reelle and stop_info()["state"] != "absent":
        manque.append("arret-actif")
    if lecture_reelle and not launchd_trial_status(read_journal(), installed_plist_check()):
        manque.append("essai-launchd")
    return {"format": EXPECTED_FORMAT, "met": not manque, "series": len(comptes), "required": SERIES_REQUIRED, "missing": manque,
            "serie": [r.get("sommet_train") for r in cinq]}


def read_journal():
    """Les enregistrements du journal, dans l'ordre ; une ligne illisible est ignorée."""
    try:
        texte = (data() / JOURNAL_NAME).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    resultat = []
    for ligne in texte.splitlines():
        try:
            r = json.loads(ligne)
        except ValueError:
            continue
        if isinstance(r, dict):
            resultat.append(r)
    return resultat


def _atomic_write(chemin, texte):
    temporaire = chemin.parent / f".{chemin.name}.tmp-{os.getpid()}"
    fd = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(texte)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporaire, chemin)
    except BaseException:
        try:
            os.unlink(temporaire)
        except OSError:
            pass
        raise


def append_journal(rec, now_ts):
    """Ajoute l'enregistrement et retire ceux de plus d'un an, sous verrou, par remplacement atomique."""
    with train_ready.exclusive(data() / JOURNAL_LOCK_NAME):
        limite = now_ts - KEEP_DAYS * 86400
        gardees = []
        for r in read_journal():
            try:
                if epoch_of(r["utc"]) >= limite:
                    gardees.append(r)
            except (KeyError, ValueError, TypeError):
                continue
        gardees.append(rec)
        _atomic_write(data() / JOURNAL_NAME, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in gardees))


def write_state(rec, refuses=None):
    """L'état : le dernier enregistrement, le résumé de la liste et, depuis la tranche 3 (D11), les ensembles de sommets des trains refusés (`refuses`)."""
    etat = {"format": EXPECTED_FORMAT, "dernier": rec, "liste": rec.get("liste")}
    if refuses is not None:
        etat["refuses"] = refuses
    _atomic_write(data() / STATE_NAME, json.dumps(etat, ensure_ascii=False) + "\n")


class EtatIllisible(Exception):
    """L'état est présent mais illisible : les ensembles refusés (D11) ne sont pas connus (revue 10.1, constat 2)."""


def read_refuses():
    """Les ensembles de sommets des trains refusés pour leur contenu (D11) lus dans l'état : [{"code", "sommet_train", "sommets", "notifies"}] ; une entrée mal
    formée est ignorée, l'état absent rend []. Un état présent mais illisible (ou qui n'est pas un objet) lève EtatIllisible : en fusion le passage attend
    (`etat-illisible`) au lieu de rejouer un train refusé. Lecture seule."""
    try:
        etat = json.loads((data() / STATE_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError, UnicodeDecodeError):
        raise EtatIllisible() from None
    if not isinstance(etat, dict):
        raise EtatIllisible()
    liste = etat.get("refuses")
    resultat = []
    for e in liste if isinstance(liste, list) else []:
        if (isinstance(e, dict) and isinstance(e.get("code"), int) and isinstance(e.get("sommets"), list) and all(isinstance(s, str) for s in e["sommets"])
                and isinstance(e.get("notifies", []), list)):
            resultat.append({"code": e["code"], "sommet_train": e.get("sommet_train", ""), "sommets": list(e["sommets"]), "notifies": list(e.get("notifies", []))})
    return resultat


def last_state():
    """Service : le dernier état écrit par le passage (jamais écrit ici), la présence du fichier d'arrêt et `illisible` (revue de contrôle 10.2, point A : vrai quand
    etat.json est présent mais illisible ou n'est pas un objet ; faux quand il est absent). Aucune écriture."""
    etat, illisible = None, False
    try:
        etat = json.loads((data() / STATE_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        pass
    except (OSError, ValueError):   # UnicodeDecodeError est une ValueError
        illisible = True
    if etat is not None and not isinstance(etat, dict):
        illisible = True
    etat = etat if isinstance(etat, dict) else {}
    return {"format": EXPECTED_FORMAT, "dernier": etat.get("dernier"), "liste": etat.get("liste"), "arret": stop_path().exists(), "illisible": illisible}


def stop_vanished():
    """Le dernier enregistrement d'arrêt est plus récent que le dernier « reprendre » (ordre du journal)."""
    dernier_arret = dernier_reprendre = -1
    for i, r in enumerate(read_journal()):
        if r.get("type") == "arret":
            dernier_arret = i
        elif r.get("type") == "reprendre":
            dernier_reprendre = i
    return dernier_arret > dernier_reprendre


def create_stop_file():
    train_ready.ensure_data_dir()
    fd = os.open(stop_path(), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.close(fd)


def event_record(kind, ctx_env, clock, reason=None):
    ts = clock.now()
    return {"format": EXPECTED_FORMAT, "type": kind, "utc": iso_utc(ts), "paris": paris(ts).strftime("%Y-%m-%d %H:%M"),
            "caller": "session" if in_session(ctx_env) else caller_of(ctx_env), "raison": reason}


# --- garde des noms ------------------------------------------------------------------------------------------------------------------

class Guard:
    """La garde des noms sensibles (les règles du crochet pre-commit, par tools/sensitive_names.py). Lève
    sensitive_names.SensitiveNamesUnavailable quand la liste est absente, illisible ou vide."""

    def __init__(self):
        self.motifs = sensitive_names.patterns(sensitive_names.load_judged_names())   # liste puis extrait : source unique (A-75, R-20261112-20)

    def matches(self, texte):
        return sensitive_names.line_matches(self.motifs, texte)


# --- exclusions et contrôle d'une ligne (une seule définition, appelée par les deux outils) -------------------------------------------

def checks_script(run):
    chemin = Path(run) / "tools" / "finish_checks.py"
    return chemin if chemin.is_file() else Path(__file__).resolve().parent / "finish_checks.py"


def front_touched(ws, branch):
    """True, False ou None (lecture impossible) : la branche change-t-elle un chemin de la liste du front, lue comme la fin la lit
    (union d'origin/main, de main local et du sommet) ? Liste absente partout ou sans aucune entrée : None (refus par défaut, jamais
    une admission)."""
    entrees, lue = [], False
    for revision in ("refs/remotes/origin/main", "refs/heads/main", f"refs/heads/{branch}"):
        code, sortie = train_ready.git(ws, "cat-file", "blob", f"{revision}:{FRONT_LIST}")
        if code != 0:
            continue
        lue = True
        for ligne in sortie.splitlines():
            ligne = ligne.split("#", 1)[0].strip()
            if ligne and ligne not in entrees:
                entrees.append(ligne)
    if not lue or not entrees:
        return None
    for entree in entrees:
        code, _ = train_ready.git(ws, "diff", "--quiet", "--no-renames", f"refs/remotes/origin/main...refs/heads/{branch}", "--", entree)
        if code == 1:
            return True
        if code != 0:
            return None
    return False


def exclusions(ws, run, branch, revue=None):
    """(raisons d'exclusion, code de finish_checks.py). Lues depuis la sortie JSON de `finish_checks.py branch <b> --json` : fichiers
    protégés touchés, contrôle 6 et contrôle 14 applicables ; plus la liste du front. Aucune liste de chemins n'est copiée ici.
    Code 3 ou 4 : « controle-impossible » (le code est rendu, 4 distingue un calcul impossible)."""
    code, sortie = run_command([sys.executable, "-I", str(checks_script(run)), "branch", branch, "--repo", str(ws), "--json"], ws,
                               os.environ, CHECK_TIMEOUT)
    if code in (3, 4):
        return ["controle-impossible"], code
    if code not in (0, 1):
        return ["controle-impossible"], 4
    try:
        donnees = json.loads(sortie)
        controles = {c["id"]: c["verdict"] for c in donnees["controls"]}
        touches = donnees["protected_touched"]
        if donnees["format"] != EXPECTED_FORMAT or not {"6", "14"} <= set(controles) or not isinstance(touches, list):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return ["controle-impossible"], 4
    # D16 (autonomous-trains-merge, tranche 3, R-20261101-61) : l'outillage (fichier `juge`, runner, preuve, .claude/, CLAUDE.md) et les postures restent exclus, par la
    # fonction UNIQUE train_de_l_auteur (D2) ; la base et l'interface ne le sont plus quand la ligne est `faite` ; un fichier sensible seul non plus. Sans revue `faite`
    # (revue None ou `non-requise` : le refus de `add --revue non-requise`), les quatre motifs de chemin restent des raisons.
    # Remplace : l'exclusion de tout fichier protégé, de la base et du front (observe D4). Retrait : permanent.
    faite = revue == "faite"
    raisons = []
    try:
        import finish_checks
        sans_postures = dict(donnees, controls=[dict(c, verdict="exempt") if c.get("id") == "6" else c for c in donnees["controls"]])
        outillage = finish_checks.train_de_l_auteur_de_la_branche(ws, sans_postures)
    except Exception:   # le doute refuse
        outillage = True
    if outillage or (touches and not faite):
        raisons.append("outillage-protege")
    if controles["6"] != "exempt":
        raisons.append("postures")
    if controles["14"] != "exempt" and not faite:
        raisons.append("base")
    front = front_touched(ws, branch)
    if front is None:
        return raisons + ["controle-impossible"], 4
    if front and not faite:
        raisons.append("front")
    return raisons, 0


def check_line(ws, run, entry):
    """Les raisons pour lesquelles une ligne de la liste ne tient plus (liste vide : valide). Même fonction pour le passage, `list` et /pilot.
    Le sommet noté, l'empreinte et la revue sont revérifiés ; la confiance dans l'empreinte ne remplace pas les contrôles de la fin."""
    ws, branche = Path(ws), entry["branche"]
    tip = train_ready.tip_of(ws, branche)
    if tip is None:
        return ["branche-absente"]
    deja = train_ready.in_origin_main(ws, tip)
    if deja is True:
        return ["deja-fusionnee"]
    if deja is None:
        return ["controle-impossible"]
    if tip != entry["sommet"]:
        return ["sommet-change"]
    raisons = []
    arbre = train_ready.tree_of(ws, tip)
    wt = train_ready.worktree_of(ws, branche)
    sans_wt = wt is None or not Path(wt).is_dir()
    # La preuve du sommet : UNE définition (train_ready.proof_of, qui délègue à tools/preuve_arbre.py : runner complet, conteneur et passe Mac, ou empreinte de branche), la même que pour `add` et `list`.
    manque = train_ready.proof_reason(wt, arbre) if not sans_wt and arbre == entry["empreinte"] else None
    if arbre != entry["empreinte"]:
        raisons.append("empreinte")
    elif manque:
        raisons.append(manque)
    if sans_wt:
        raisons.append("sans-worktree")
    if entry["revue"] == "non-requise":
        chemins = train_ready.changed_paths(ws, branche)
        if chemins is None:
            raisons.append("controle-impossible")
        elif not train_ready.review_free(chemins):
            raisons.append("revue")
    autres, _ = exclusions(ws, run, branche, entry["revue"])
    for r in autres:
        if r not in raisons:
            raisons.append(r)
    return raisons


# --- contrôles du passage ----------------------------------------------------------------------------------------------------------

# Retiré (tooling-proof-in-container, T2, design D3, R-20261104-7 P2) : session_runner_held et le contrôle « runner-session ». Le verrou « un seul runner
# complet de session » n'existe plus (plus aucun runner complet ne tourne sur le Mac en session) : la passe n'attend que le verrou de fin.
# Remplace : l'attente du verrou du runner de session. Condition de retrait de ce commentaire : la prochaine réécriture de cette section.


class Context:
    def __init__(self, env, ws, run):
        self.env = dict(env)
        self.clock = Clock(self.env)
        self.ws = Path(ws)
        self.run = Path(run)
        self.caller = caller_of(self.env)
        self.refuses = []      # les ensembles de sommets des trains refusés (D11), lus de l'état au début du passage et réécrits à la fin
        self.etat_illisible = False   # l'état présent mais illisible au début du passage : en fusion le passage attend (`etat-illisible`) et ne le réécrit pas (en observation non plus : revue 10.2, point D)
        self.train_row = None  # l'enregistrement du journal des trains écrit par le train réel de ce passage (D4), s'il y en a un
        self.a_notifier = []   # (sommet, code) des lignes exclues pour la première fois par `echec-au-sommet` (D11, D15)
        code, sortie = train_ready.git(self.ws, "rev-parse", "--path-format=absolute", "--git-common-dir")
        self.common = Path(sortie.strip()) if code == 0 and sortie.strip() else self.ws / ".git"

    def script(self, root, name, *args):
        return ["bash", str(Path(root) / "tools" / name), *args]


def lock_reason(ctx):
    etat, _ = pilot.freeze_state(ctx.common)
    if etat == "tenu":
        return "verrou-fin"
    return None


def wait_for_locks(ctx, window_end):
    """None quand les verrous sont libres ; sinon la raison, après les nouveaux essais toutes les cinq minutes jusqu'à la fin de la tolérance."""
    while True:
        raison = lock_reason(ctx)
        if raison is None:
            return None
        if seconds_of_day(ctx.clock.now()) + RETRY_SECONDS > window_end:
            return raison
        ctx.clock.sleep(RETRY_SECONDS)


def remote_main(ctx):
    env = {"GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o ConnectTimeout=20", "GCM_INTERACTIVE": "never"}
    code, sortie = train_ready.git(ctx.ws, "ls-remote", "--exit-code", "origin", "refs/heads/main", timeout=REMOTE_TIMEOUT, extra_env=env)
    champs = sortie.split()
    return champs[0] if code == 0 and champs else None


def environment_reason(ctx):
    """Contrôle 6 : espace de travail, distant, dossier d'exécution."""
    code, branche = train_ready.git(ctx.ws, "symbolic-ref", "-q", "--short", "HEAD")
    code2, statut = train_ready.git(ctx.ws, "status", "--porcelain")
    if code != 0 or branche.strip() != "main" or code2 != 0 or statut.strip():
        return "espace-de-travail"
    distant = remote_main(ctx)
    if distant is None:
        return "distant"
    if distant != train_ready.rev(ctx.ws, "refs/heads/main"):
        return "main-different"
    code, _ = run_command(ctx.script(ctx.run, "run_worktree.sh", "status"), ctx.run, ctx.env, CHECK_TIMEOUT)
    return None if code == 0 else "dossier-execution"


def hooks_reason(ctx):
    """Contrôle 7 : crochets vérifiés (l'installeur de l'espace de travail, qui sait où sont ses liens) et identité Git."""
    code, _ = run_command(ctx.script(ctx.ws, "install_hooks.sh", "--verify"), ctx.ws, ctx.env, CHECK_TIMEOUT)
    if code != 0:
        return "crochets"
    for cle in ("user.name", "user.email"):
        code, sortie = train_ready.git(ctx.ws, "config", "--get", cle)
        if code != 0 or not sortie.strip():
            return "identite"
    return None


def doctor_state(ctx):
    """L'état du contrôle doctor du crochet reference-transaction : vert, rouge ou absent. Noté, jamais bloquant dans ce change.
    R-20261110-43 : le doctor tourne sans DOCTOR_CROCHETS_DEPOT ni GIT_* (un dépôt hérité de l'environnement fausserait le contrôle : faux vert) et
    le JSON est lu sur stdout seul (un avertissement sur stderr ne rend plus « absent »). Remplace : rien. Retrait : permanent."""
    script = ctx.run / "tools" / "doctor.py"
    try:
        if "reference-transaction" not in script.read_text(encoding="utf-8"):
            return "absent"
    except OSError:
        return "absent"
    env = {k: v for k, v in ctx.env.items() if k != "DOCTOR_CROCHETS_DEPOT" and not k.startswith("GIT_")}
    code, sortie = run_command([sys.executable, "-I", str(script), "--json"], ctx.run, env, CHECK_TIMEOUT, stdout_seul=True)
    try:
        for c in json.loads(sortie).get("checks", []):
            if "reference-transaction" in json.dumps(c):
                # R-20261110-42 : le doctor écrit le niveau sous « level » ; « status » reste lu (le faux doctor des tests de la fusion).
                return "vert" if (c.get("level") or c.get("status")) in ("ok", "vert") else "rouge"
    except (ValueError, AttributeError):
        pass
    return "absent"


def busy_branches(ctx, entrees):
    """branche -> True quand un processus a son dossier courant dans son worktree (la carte de pilot.py, les seuls worktrees listés)."""
    chemins = {}
    for e in entrees:
        wt = train_ready.worktree_of(ctx.ws, e["branche"])
        if wt and Path(wt).is_dir():
            chemins[e["branche"]] = os.path.realpath(wt)
    occupes = pilot.busy_map(list(chemins.values())) if chemins else set()
    if occupes is None:
        return {}   # listage impossible : la fin décide (62 relancé une fois)
    return {b: True for b, p in chemins.items() if p in occupes}


# --- l'essai --------------------------------------------------------------------------------------------------------------------------

def trial_command(run, names):
    """La seule commande de fin que l'outil construit : toujours avec --essai, avant les noms."""
    return ["bash", str(Path(run) / "tools" / "finish_train.sh"), "--essai", *names]


def parse_refused(code, texte, names):
    """Les branches que la fin a nommées dans ses lignes de refus : code 62, lignes « - <branche> : <motif> » ; code 64, la ligne
    « conflit à la construction du train : <branche> avec … ». Seules les branches données comptent. Épinglé par des tests sur la vraie fin."""
    donnees = set(names)
    trouvees = []
    for ligne in texte.splitlines():
        if code == 62:
            m = re.match(r"^  - (\S+) : ", ligne)
        else:
            m = re.match(r"^finish_train : conflit à la construction du train : (\S+) avec ", ligne)
        if m and m.group(1) in donnees and m.group(1) not in trouvees:
            trouvees.append(m.group(1))
    return trouvees


def run_trial(ctx, names):
    """L'essai, puis au plus un nouvel essai sans les branches nommées par le refus 62 ou 64. Rend l'enregistrement `essai`."""
    code, sortie = run_command(trial_command(ctx.run, names), ctx.run, ctx.env, TRIAL_TIMEOUT)
    essai = {"code": code, "relance": False, "code2": None, "retirees": []}
    if code in (62, 64):
        refusees = parse_refused(code, sortie, names)
        reste = [n for n in names if n not in refusees]
        if refusees and reste:
            code2, _ = run_command(trial_command(ctx.run, reste), ctx.run, ctx.env, TRIAL_TIMEOUT)
            essai.update(relance=True, code2=code2, retirees=refusees)
    return essai


def final_code(essai):
    return essai["code2"] if essai["relance"] else essai["code"]


# --- le train réel (autonomous-trains-merge, tranche 3, D9 à D11) ---------------------------------------------------------------------

def train_command(run, names):
    """La commande du train réel : toujours avec --auto (la politique remplace la question), jamais sans. Le seul autre endroit qui nomme le script de fin est trial_command."""
    return ["bash", str(Path(run) / "tools" / "finish_train.sh"), "--auto", *names]


# D10 : une ligne par code de `finish_train` du registre tools/finish_codes.yaml (le registre est la source ; un test échoue quand un code d'origine `utilise` ou `reserve`
# n'a pas de ligne, ou qu'une ligne nomme un code absent). Valeur : la clé de la suite « pour l'auteur » (libellé `reason:suite-<clé>`). Les codes d'origine `jamais_rendu`
# (72, 77) tombent dans « tout autre » : arrêt armé. Remplace : rien (les codes de l'essai d'autonomous-trains-observe D6 sont inchangés). Retrait : permanent, avec le mode de fusion.
CODE_TABLE = {
    0: "rien", 62: "refusee", 64: "conflit", 66: "garde-matin", 67: "verrou-fin", 69: "base-rouge", 70: "train-rouge", 71: "runner", 82: "e2e-rouge",
    83: "jeu-essai", 84: "politique", 75: "incomplete",
    **{code: "environnement" for code in (60, 61, 63, 68, 76, 78, 80, 81)},
    **{code: "arret-arme" for code in (65, 73, 74, 79, 129, 130, 141, 143)},
}


def code_handling(code, sens):
    """Le traitement d'un code du train réel (D10) : {"suite": clé, "stop": l'arrêt est armé, "refuse": refus de contenu, D11}. Le code 0 n'est un succès que
    avec le sens `fusionne` ; tout code absent de la table arme l'arrêt : le passage ne prend jamais un code inconnu pour un succès."""
    if code == 0:
        suite = CODE_TABLE[0] if sens == "fusionne" else "anomalie"
        return {"suite": suite, "stop": suite == "anomalie", "refuse": False}
    suite = CODE_TABLE.get(code, "arret-arme")
    return {"suite": suite, "stop": suite == "arret-arme", "refuse": code in REFUS_CODES}


def policy_label(code):
    try:
        import finish_checks
        return finish_checks.POLITIQUE_LIBELLES.get(code, code)
    except Exception:   # le libellé n'est qu'un confort : le code reste lisible
        return code


def suite_text(cle, language="fr", politique=None):
    """Le texte « pour l'auteur » d'une clé de la table (D10). La suite `politique` cite les libellés de la politique (finish_checks.POLITIQUE_LIBELLES, seule source)."""
    texte = reason_label("suite-" + cle, language)
    if cle == "politique":
        texte = texte.replace("{labels}", ", ".join(str(policy_label(c)) for c in (politique or [])))
    return texte


def last_new_row(avant):
    """Le dernier enregistrement `auto` ajouté au journal des trains depuis la liste `avant` (D4), ou None (journal illisible compris)."""
    try:
        apres = train_record.read_records()
    except (train_record.Unreadable, lab_paths.LabPathsError, OSError):
        return None
    vus = [json.dumps(r, sort_keys=True) for r in avant]
    nouveaux = [r for r in apres if json.dumps(r, sort_keys=True) not in vus and r.get("mode") == "auto"]
    return nouveaux[-1] if nouveaux else None


def records_before():
    try:
        return train_record.read_records()
    except (train_record.Unreadable, lab_paths.LabPathsError, OSError):
        return []


def run_real_train(ctx, names, tips):
    """Lance le train réel sur `names` (D9) et rend l'enregistrement `train` du passage : code, sens, durée (secondes), sommets, délai, suite et arrêt. Lit l'enregistrement
    que le train a écrit au journal des trains (D4). Jamais relancé, aucune branche ajoutée après l'essai."""
    avant = records_before()
    debut = time.monotonic()
    code, delai = run_train_process(train_command(ctx.run, names), ctx.run, ctx.env, _float_of(ctx.env, "TRAIN_AUTO_TRAIN_TIMEOUT", TRAIN_TIMEOUT),
                                    _float_of(ctx.env, "TRAIN_AUTO_TERM_GRACE", TERM_GRACE))
    mesure = int(time.monotonic() - debut)
    ligne = last_new_row(avant)
    if ligne is not None and ligne.get("code") != code:
        ligne = None   # un enregistrement qui ne dit pas le code rendu n'est pas celui de ce train
    ctx.train_row = ligne
    sens = ligne.get("sens") if ligne else None
    traitement = code_handling(code, sens or "")
    arret = traitement["stop"] or delai   # le délai, TERM puis l'éventuel KILL compris, arme toujours l'arrêt (R-20261107-8 Q1)
    return {"code": code, "sens": sens, "duree": ligne["duree_s"] if ligne else mesure, "sommets": list(tips), "delai": delai, "suite": traitement["suite"],
            "refuse": traitement["refuse"], "arret": arret, "sommet_train": (ligne or {}).get("sommet_train", ""), "politique": list((ligne or {}).get("politique", []))}


def forget_unused_refuses(refuses, tips):
    """Un ensemble n'est gardé que tant qu'une ligne de la liste porte un de ses sommets (D11) : la ligne retirée ou dont le sommet a changé libère l'exclusion."""
    return [r for r in refuses if any(s in tips for s in r["sommets"])]


def refused_set_of(refuses, tip):
    for r in refuses:
        if tip in r["sommets"]:
            return r
    return None


# --- le compte rendu et la notification (D12, D14, D15) -----------------------------------------------------------------------------------

REPORT_HEADER = ("# Fusions automatiques\n\nÉcrit par train_auto seul, en ajout seul ; jamais modifié par une session.\n\n"
                 "| Heure (Paris) | Code (sens) | main | Branches (sommet, revue) | Écartées à l'essai | Durée | Pour l'auteur |\n|---|---|---|---|---|---|---|\n")
SENS_MOTS = {"fusionne": "fusionné", "refuse": "refusé", "interrompu": "interrompu", "essai": "essai"}


def merge_report(pass_record, train_rec):
    """Le compte rendu d'un passage en fusion (D14), en UN endroit : la ligne du rapport et la notification ne font que le formater. `pass_record` : l'enregistrement du
    passage ; `train_rec` : la ligne du journal des trains écrite par le train réel (ou None, ou pour un essai refusé). Rend un dictionnaire : heure, code, sens, main_avant,
    main_apres, branches [{nom, sommet, revue}], ecartees [{nom, motif}], duree_min, suite, politique, essai (vrai pour un essai refusé), arret, n. Aucun nom n'est
    masqué ici : report_line le fait avec la garde."""
    train = pass_record.get("train")
    essai = pass_record.get("essai") or {}
    retirees = set(essai.get("retirees") or [])
    retenues = [b for b in pass_record.get("retenues", []) if b["branche"] not in retirees]
    main = pass_record.get("main") or ""
    if train:
        code = train["code"]
        sens = (train_rec or {}).get("sens") or "inconnu"   # sans enregistrement du train, le sens n'est pas connu : le code 0 est alors une anomalie (D10)
        avant = (train_rec or {}).get("main_avant") or main
        apres = (train_rec or {}).get("main_apres") or avant
        secondes = (train_rec or {}).get("duree_s", train.get("duree", 0))
        traitement = code_handling(code, (train_rec or {}).get("sens") or "")
        politique = list((train_rec or {}).get("politique") or train.get("politique") or [])
    else:
        code = final_code(essai) if essai else 0
        sens, avant, apres = "essai", main, main
        secondes = pass_record.get("duree", 0)
        traitement = code_handling(code, "refuse")
        politique = []
    return {"heure": pass_record.get("paris", ""), "code": code, "sens": sens, "main_avant": avant, "main_apres": apres,
            "branches": [{"nom": b["branche"], "sommet": b["sommet"], "revue": b.get("revue", "faite")} for b in retenues],
            "ecartees": [{"nom": e["branche"], "motif": "conflit" if e["code"] == 64 else "refusée"} for e in pass_record.get("ecartees_essai", [])],
            "duree_min": (int(secondes) + 30) // 60, "suite": traitement["suite"], "politique": politique, "essai": not train,
            "arret": pass_record.get("arret_arme") is not None, "n": len(retenues)}


FIGEES_EN_RETARD = "outils-figes-en-retard"


def frozen_late_command(train_rec):
    """R-20261110-03 : la commande de rafraîchissement des copies figées que le train a notée (fichier `outils-figes-en-retard` du dossier de données : le sommet du train,
    un espace, la commande), ou None. Rien quand le passage n'a pas d'enregistrement de train (`train_rec` absent : la note n'est reprise que pour le train du
    passage), quand le fichier est absent ou illisible (octets invalides compris : la lecture n'arrête jamais le rapport), ou quand il note un autre train que celui du
    passage (sommet différent). Remplace : rien. Retrait : avec le bac à sable (R-20261110-03, -04)."""
    if not train_rec:
        return None
    try:
        texte = (lab_paths.data_folder() / FIGEES_EN_RETARD).read_text(encoding="utf-8").strip()
    except (OSError, ValueError, lab_paths.LabPathsError):
        return None
    sommet, _, commande = texte.partition(" ")
    if not commande or (train_rec.get("sommet_train") and train_rec["sommet_train"] != sommet):
        return None
    return commande


def report_line(rapport, garde, hide=False, retard=None):
    """La ligne du rapport (D14). Les noms de branche passent la garde des noms sensibles d'abord : un nom trouvé devient `branche masquée` ; `hide` (garde impossible)
    n'écrit que les comptes. Un `|` dans un nom est écrit `\\|`. `retard` (R-20261110-03) : la commande de rafraîchissement des copies figées, ajoutée à la dernière colonne."""
    def nom(n):
        return CATALOGS["fr"]["masked_branch"] if garde is not None and garde.matches(n) else n.replace("|", "\\|")

    def sha(texte):
        return (texte or "")[:12] or "—"
    if hide:
        branches = f"{len(rapport['branches'])} branche(s)"
        ecartees = f"{len(rapport['ecartees'])} branche(s)" if rapport["ecartees"] else "—"
    else:
        branches = " ; ".join(f"{nom(b['nom'])} (sommet {sha(b['sommet'])}, "
                              + (f"revue Opus du sommet {sha(b['sommet'])}" if b["revue"] == "faite" else "revue non requise") + ")" for b in rapport["branches"]) or "—"
        ecartees = " ; ".join(f"{nom(e['nom'])} ({e['motif']})" for e in rapport["ecartees"]) or "—"
    suite = suite_text(rapport["suite"], "fr", rapport["politique"]).replace("|", "\\|")
    if retard:
        suite += " ; copies figées en retard sur main, à rafraîchir par l'auteur : " + retard.replace("|", "\\|")
    return (f"| {rapport['heure']} | {rapport['code']} ({rapport['sens']}) | {sha(rapport['main_avant'])} -> {sha(rapport['main_apres'])} | {branches} | {ecartees} "
            f"| {rapport['duree_min']} min | {suite} |")


def notification_text(rapport):
    """Le texte de la notification (D15), sans nom de branche : train réel `<sens> : <n> branche(s), main <sha12>, revue <k>/<n>, <m> min, code <c>` ; essai refusé
    `essai refusé : <n> branche(s), code <c>, pour l'auteur : <suite>` ; suivi de `, arrêt armé` quand l'arrêt est armé."""
    n = rapport["n"]
    if rapport["essai"]:
        texte = f"essai refusé : {n} branche(s), code {rapport['code']}, pour l'auteur : {suite_text(rapport['suite'], 'fr', rapport['politique'])}"
    else:
        k = sum(1 for b in rapport["branches"] if b["revue"] == "faite")
        texte = (f"{SENS_MOTS.get(rapport['sens'], rapport['sens'])} : {n} branche(s), main {(rapport['main_apres'] or rapport['main_avant'] or '')[:12] or '—'}, "
                 f"revue {k}/{n}, {rapport['duree_min']} min, code {rapport['code']}")
    return texte + ", arrêt armé" if rapport["arret"] else texte


def notifier_command(texte):
    """La commande de notification de D15 (le texte est passé en argument, jamais interprété)."""
    return ["/usr/bin/osascript", "-e", "on run argv", "-e", 'display notification (item 1 of argv) with title "Train automatique"', "-e", "end run", texte]


def send_notification(texte, env):
    """Envoie la notification : entrée standard fermée, délai de NOTIFY_TIMEOUT secondes. Vrai quand elle est partie ; un échec est ignoré par l'appelant. TRAIN_AUTO_NOTIFIER
    remplace la commande dans les tests seulement (le texte s'ajoute en dernier argument)."""
    voulu = env.get("TRAIN_AUTO_NOTIFIER")
    commande = shlex.split(voulu) + [texte] if voulu else notifier_command(texte)
    try:
        fait = subprocess.run(commande, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=NOTIFY_TIMEOUT, env=dict(env))
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    return fait.returncode == 0


def report_path():
    return lab_paths.lab_folder(lab_paths.content_root()) / "etapes" / REPORT_NAME


def append_report(ligne):
    """Ajoute la ligne à etapes/fusions-auto.md (ajout seul ; l'en-tête est écrit à la création). OSError quand l'écriture est impossible. Rien d'autre n'est écrit dans etapes/."""
    chemin = report_path()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    nouveau = not chemin.exists()
    with open(chemin, "a", encoding="utf-8") as f:
        if nouveau:
            f.write(REPORT_HEADER)
        f.write(ligne + "\n")


def publish(ctx, rec):
    """D12, D14, D15, D11 : le compte rendu et les notifications d'un passage en fusion. Un train réel ; un essai final non nul (une ligne, une notification) ; les
    lignes exclues pour la première fois par `echec-au-sommet` (une notification par sommet). Jamais d'effet sur la décision : un échec d'écriture ou d'envoi est noté
    (`rapport_non_ecrit`, `notification_non_envoyee`) et le passage continue. Rien en observation, rien pour une attente, un « rien à faire » ou une exclusion journalisée."""
    if rec.get("mode") != "fusion":
        return
    essai = rec.get("essai")
    train = rec.get("train")
    if train is None and not (essai and final_code(essai) != 0):
        envoyes = []
    else:
        rapport = merge_report(rec, ctx.train_row)
        try:
            garde, cache = Guard(), False
        except sensitive_names.SensitiveNamesUnavailable:
            garde, cache = None, True
        try:
            retard = None if rapport["essai"] else frozen_late_command(ctx.train_row)
            append_report(report_line(rapport, garde, hide=cache, retard=retard))
        except OSError:
            rec["notices"].append("rapport_non_ecrit")
        envoyes = [notification_text(rapport)]
    for sommet, code in ctx.a_notifier:
        envoyes.append(f"train refusé sur ce sommet (code {code})")
        ensemble = refused_set_of(ctx.refuses, sommet)
        if ensemble is not None and sommet not in ensemble["notifies"]:
            ensemble["notifies"].append(sommet)
    for texte in envoyes:
        if not send_notification(texte, ctx.env):
            rec["notices"].append("notification_non_envoyee")


# --- la décision -----------------------------------------------------------------------------------------------------------------------

def new_record(ctx):
    ts = ctx.clock.now()
    return {"format": EXPECTED_FORMAT, "type": "passage", "utc": iso_utc(ts), "paris": paris(ts).strftime("%Y-%m-%d %H:%M"),
            "caller": ctx.caller, "fenetre": None, "decision": None, "raison": None, "retenues": [], "ecartees": [], "essai": None,
            "doctor": "absent", "liste": None, "duree": 0, "notices": [], "arret_arme": None,
            # tranche 3 (D9) : le mode du passage, la décision `train`, le train réel, les branches retirées par la relance ; `main` : le main local du passage (D14)
            "mode": "observation", "main": None, "ecartees_essai": [], "train": None,
            # branche 4 (D10) : l'empreinte du PATH reçu par un passage lancé par launchd, nulle sinon ; jamais le chemin
            "env_job": path_fingerprint(ctx.env.get("PATH", "")) if ctx.caller == "launchd" else None}


def halt(rec, decision, raison):
    rec["decision"], rec["raison"] = decision, raison
    return rec


def past_latest_start(ctx):
    """D9 : vrai quand l'heure de Paris du passage dépasse l'heure de départ la plus tardive du jour. Un seul calcul pour le contrôle 3 et pour la nouvelle vérification
    juste avant le train réel (D9 point 3, revue 10.1) : l'essai peut durer jusqu'à TRIAL_TIMEOUT. Remplace : rien. Retrait : permanent, avec le mode de fusion."""
    maintenant = paris(ctx.clock.now())
    return maintenant > latest_start(records_before(), maintenant.date())


def decide(ctx):
    """Le passage : les contrôles dans l'ordre de D2, puis l'essai. Rend l'enregistrement du passage ; ne lance rien d'autre que l'essai."""
    rec = new_record(ctx)
    debut = ctx.clock.now()
    try:
        return _decide(ctx, rec)
    finally:
        rec["duree"] = int(ctx.clock.now() - debut)


def _decide(ctx, rec):
    # 1 arrêt d'urgence
    if stop_path().exists():
        return halt(rec, "arrete", "arret")
    if stop_vanished():
        create_stop_file()
        rec["notices"].append("stop_vanished")
        return halt(rec, "arrete", "arret-disparu")
    # 2 hors session
    if in_session(ctx.env):
        return halt(rec, "refuse", "session")
    # 2 bis version de l'interpréteur (R-20261110-34) : sous 3.10, attente sous sa raison, sans armer l'arrêt
    if tuple(sys.version_info[:2]) < PYTHON_MINIMUM:
        return halt(rec, "attente", "python-ancien")
    # le mode (D6) : fusion seulement quand le fichier d'activation est valide ; absent : observation ; invalide : observation et le dit
    etat_activation = activation_state()
    rec["mode"] = "fusion" if etat_activation == "valide" else "observation"
    if etat_activation == "invalide":
        rec["notices"].append("activation_invalide")
    # 3 fenêtre
    fenetre = window_at(ctx.clock.now())
    if fenetre is None:
        return halt(rec, "attente", "hors-fenetre")
    rec["fenetre"], fin = fenetre
    if rec["mode"] == "fusion":   # l'heure de départ la plus tardive (D9) : aucun essai en mode de fusion au-delà
        if past_latest_start(ctx):
            return halt(rec, "attente", "depart-limite")
        if ctx.etat_illisible:   # revue 10.1 : les trains refusés ne sont pas connus, aucun essai ni train ne risque de les rejouer
            return halt(rec, "attente", "etat-illisible")
    # 4 état du matin (le code, jamais la phrase)
    code, _ = run_command(ctx.script(ctx.run, "morning_state.sh", "check"), ctx.run, ctx.env, CHECK_TIMEOUT)
    if code != 0:
        return halt(rec, "attente", "matin")
    # 5 verrous
    raison = wait_for_locks(ctx, fin)
    if raison:
        return halt(rec, "attente", raison)
    # 6 espace de travail et distant
    raison = environment_reason(ctx)
    if raison:
        return halt(rec, "attente", raison)
    rec["main"] = train_ready.rev(ctx.ws, "refs/heads/main")
    # 7 crochets et identité ; état du contrôle doctor : noté en observation, bloquant en fusion (D17 : rouge ou absent)
    rec["doctor"] = doctor_state(ctx)
    if rec["mode"] == "fusion" and rec["doctor"] != "vert":
        return halt(rec, "attente", "crochets-doctor")
    raison = hooks_reason(ctx)
    if raison:
        return halt(rec, "attente", raison)
    # 8 liste prête
    try:
        entrees = train_ready.read_list()
    except train_ready.ListeIllisible:
        return halt(rec, "attente", "liste-illisible")
    rec["liste"] = {"lignes": len(entrees), "valides": 0}
    ctx.refuses = forget_unused_refuses(ctx.refuses, {e["sommet"] for e in entrees})   # D11 : la ligne retirée ou dont le sommet a changé libère l'exclusion
    if not entrees:
        return halt(rec, "rien", "liste-vide")
    try:
        garde = Guard()
    except sensitive_names.SensitiveNamesUnavailable:
        return halt(rec, "attente", "garde-noms")
    # 9 contrôle de chaque ligne
    occupes = busy_branches(ctx, [e for e in entrees if not garde.matches(e["branche"])])
    valides = []
    for e in entrees:
        if garde.matches(e["branche"]):
            rec["ecartees"].append({"branche": CATALOGS["fr"]["masked_branch"], "raison": "nom", "sommet": None})
            continue
        raisons = check_line(ctx.ws, ctx.run, e)
        if not raisons and occupes.get(e["branche"]):
            raisons = ["session-active"]
        refus = refused_set_of(ctx.refuses, e["sommet"]) if not raisons else None
        if refus is not None:   # D11 : un train refusé pour son contenu n'est pas rejoué sur les mêmes sommets ; la ligne reste dans la liste
            raisons = ["echec-au-sommet"]
            if e["sommet"] not in refus["notifies"]:
                ctx.a_notifier.append((e["sommet"], refus["code"]))
        if raisons:
            rec["ecartees"].append({"branche": e["branche"], "raison": raisons[0], "sommet": train_ready.tip_of(ctx.ws, e["branche"])})
        else:
            valides.append(e)
    rec["liste"]["valides"] = len(valides)
    if not valides:
        return halt(rec, "rien", "toutes-ecartees")
    # 10 plafond : trois branches au plus dans les deux modes (D9 point 1) ; la liste garde son plafond de cinq
    retenues = valides[:PLAFOND_TRAIN]
    for e in valides[PLAFOND_TRAIN:]:
        rec["ecartees"].append({"branche": e["branche"], "raison": "plafond", "sommet": e["sommet"]})
    rec["retenues"] = [{"branche": e["branche"], "sommet": e["sommet"], "revue": e["revue"]} for e in retenues]
    # 11 essai
    rec["essai"] = run_trial(ctx, [e["branche"] for e in retenues])
    rec["ecartees_essai"] = [{"branche": b, "code": rec["essai"]["code"]} for b in rec["essai"]["retirees"]]
    # l'essai a reçu des noms : une branche dont le sommet a bougé depuis le contrôle n'est pas celle qui a été essayée
    for e in list(retenues):
        tip = train_ready.tip_of(ctx.ws, e["branche"])
        if tip != e["sommet"]:
            rec["ecartees"].append({"branche": e["branche"], "raison": "sommet-change", "sommet": tip})
            rec["retenues"] = [b for b in rec["retenues"] if b["branche"] != e["branche"]]
    codes = [rec["essai"]["code"]] + ([rec["essai"]["code2"]] if rec["essai"]["relance"] else [])
    for c in codes:
        if c in (65, 79):
            rec["arret_arme"] = c
            break
    if rec["mode"] == "fusion" and final_code(rec["essai"]) == 0 and rec["arret_arme"] is None:
        # 12 le train réel (D9 point 3) : sur les branches du dernier essai, jamais relancé, jamais une branche ajoutée
        a_fusionner = [b for b in rec["retenues"] if b["branche"] not in rec["essai"]["retirees"]]
        if a_fusionner and stop_path().exists():
            return halt(rec, "arrete", "arret")
        if a_fusionner and not activation_valid():   # revue 10.1 : un `desactiver` pendant l'essai (qui peut durer) retire le droit de lancer le train réel
            return halt(rec, "observe", "essai")
        if a_fusionner and past_latest_start(ctx):   # D9 point 3 : l'heure de départ la plus tardive est revérifiée juste avant le train réel
            return halt(rec, "attente", "depart-limite")
        if a_fusionner:
            rec["train"] = run_real_train(ctx, [b["branche"] for b in a_fusionner], [b["sommet"] for b in a_fusionner])
            if rec["train"]["arret"]:
                rec["arret_arme"] = rec["train"]["code"]
            if rec["train"]["refuse"]:
                ctx.refuses.append({"code": rec["train"]["code"], "sommet_train": rec["train"]["sommet_train"], "sommets": list(rec["train"]["sommets"]), "notifies": []})
            halt(rec, "train", "fusion-auto")
            try:   # revue 10.1 : l'état, avec les ensembles refusés, est écrit tout de suite après le train, avant le rapport et le journal ; l'écriture finale reste
                write_state(dict(rec), ctx.refuses)
            except OSError:
                pass   # l'écriture finale le dit (code 4)
            return rec
    return halt(rec, "observe", "essai")


def arm_stop(ctx, code):
    create_stop_file()
    append_journal(event_record("arret", ctx.env, ctx.clock, str(code)), ctx.clock.now())


def render(rec, t):
    """Les lignes imprimées : seulement le formatage de l'enregistrement."""
    lignes = []
    for e in rec["ecartees"]:
        lignes.append(t("discarded", branch=e["branche"], label=reason_label(e["raison"], t.language)))
    if "stop_vanished" in rec["notices"]:
        lignes.append(t("stop_vanished"))
    if "activation_invalide" in rec["notices"]:
        lignes.append(t("activation_invalid"))
    decision = rec["decision"]
    if decision == "observe":
        lignes.append(t("observation", n=len(rec["retenues"]), k=len(rec["ecartees"]), c=final_code(rec["essai"])))
        if rec["mode"] == "fusion" and final_code(rec["essai"]) != 0:   # D12 : un essai refusé en fusion dit ce qu'il reste à l'auteur
            lignes.append(t("for_author", suite=suite_text(code_handling(final_code(rec["essai"]), "refuse")["suite"], t.language)))
    elif decision == "train":
        tr = rec["train"]
        lignes.append(t("merge_line", n=len(tr["sommets"]), c=tr["code"], sens=tr["sens"] or "?", m=(int(tr["duree"]) + 30) // 60))
        lignes.append(t("for_author", suite=suite_text(tr["suite"], t.language, tr.get("politique"))))
    elif decision == "attente":
        lignes.append(t("waiting", label=reason_label(rec["raison"], t.language)))
    elif decision == "rien":
        lignes.append(t("nothing"))
    elif decision == "arrete":
        lignes.append(t("stopped"))
    if rec["arret_arme"] is not None:
        lignes.append(t("stop_armed", c=rec["arret_arme"]))
    if "rapport_non_ecrit" in rec["notices"]:
        lignes.append(t("report_not_written"))
    if "notification_non_envoyee" in rec["notices"]:
        lignes.append(t("notification_failed"))
    return lignes


# --- commandes -----------------------------------------------------------------------------------------------------------------------

def _context(t):
    try:
        ws = lab_paths.content_root()
        return Context(os.environ, ws, lab_paths.run_tree(ws))
    except lab_paths.LabPathsError:
        raise Stop(4, t("folders")) from None


def cmd_pass(args, t):
    if in_session(os.environ):
        raise Stop(3, t("session_refused"))
    os.environ.pop("FINISH_LOCK_TOKEN", None)
    ctx = _context(t)
    try:
        train_ready.ensure_data_dir()
        verrou = train_ready.exclusive(data() / PASS_LOCK_NAME, blocking=False)
        verrou.__enter__()
    except BlockingIOError:
        raise Stop(5, t("already_running")) from None
    except OSError:
        raise Stop(4, t("not_writable")) from None
    try:
        try:
            ctx.refuses = read_refuses()
        except EtatIllisible:
            ctx.etat_illisible = True
        rec = decide(ctx)
        try:
            if rec["arret_arme"] is not None:
                arm_stop(ctx, rec["arret_arme"])
            publish(ctx, rec)   # compte rendu et notifications (mode de fusion seulement) : jamais d'effet sur la décision
            publie = dict(rec)
            append_journal(publie, ctx.clock.now())
            if not ctx.etat_illisible:   # revue de contrôle 10.2, point D : quel que soit le mode, un état illisible reste tel quel (l'auteur le répare ou le retire ; les ensembles refusés ne sont pas perdus) ; `status` et /pilot le disent
                write_state(publie, ctx.refuses)
        except OSError:
            raise Stop(4, t("not_writable")) from None
    finally:
        verrou.__exit__(None, None, None)
    for ligne in render(rec, t):
        print(ligne)
    return 0


def cmd_status(args, t):
    etat = last_state()
    if args.json:
        print(json.dumps(etat, ensure_ascii=False))
        return 0
    arret = t("stop_active") if etat["arret"] else t("stop_absent")
    if etat["illisible"]:   # revue de contrôle 10.2, point A : un état illisible est dit, jamais pris pour « aucun passage » ; aucune notification (D15 inchangé)
        print(t("status_unreadable", stop=arret))
        return 0
    r = etat["dernier"]
    if not r:
        print(t("status_none", stop=arret))
        return 0
    liste = etat["liste"] or {"lignes": 0, "valides": 0}
    print(t("status_line", date=r["paris"], decision=decision_label(r["decision"], t.language), reason=reason_label(r["raison"], t.language),
            stop=arret, n=liste["lignes"], k=liste["valides"]))
    return 0


def _count(compteur, cle):
    compteur[cle] = compteur.get(cle, 0) + 1


def _merge_time(ws, tip):
    """Heure (secondes) de la première validation qui contient le sommet dans origin/main ; à défaut, l'heure du commit du sommet."""
    code, sortie = train_ready.git(ws, "log", "--ancestry-path", "--format=%ct", f"{tip}..refs/remotes/origin/main")
    nombres = [int(x) for x in sortie.split() if x.isdigit()] if code == 0 else []
    if nombres:
        return min(nombres)
    code, sortie = train_ready.git(ws, "log", "-1", "--format=%ct", tip)
    return int(sortie.strip()) if code == 0 and sortie.strip().isdigit() else None


def observation_summary(days=7, ws=None, now_ts=None):
    """Service : le bilan des passages des `days` derniers jours, comparé à ce que l'auteur a fusionné (origin/main), lecture seule."""
    ws = Path(ws) if ws else lab_paths.content_root()
    now_ts = time.time() if now_ts is None else now_ts
    depuis = now_ts - days * 86400
    passages = []
    for r in read_journal():
        try:
            if r.get("type") == "passage" and epoch_of(r["utc"]) >= depuis:
                passages.append(r)
        except (KeyError, ValueError, TypeError):
            continue
    par_decision, par_raison, par_jour, jours = {}, {}, {}, set()
    for r in passages:
        _count(par_decision, r["decision"])
        _count(par_raison, r["raison"] or "-")
        jour = r["paris"][:10]
        jours.add(jour)
        j = par_jour.setdefault(jour, {"passages": 0, "par_decision": {}})
        j["passages"] += 1
        _count(j["par_decision"], r["decision"])
    apres, deja_vues = [], set()
    for r in passages:   # ordre du journal : la première retenue d'une branche compte
        essai = r.get("essai")
        if r["decision"] != "observe" or not essai or final_code(essai) != 0:
            continue
        for b in r["retenues"]:
            if b["branche"] in essai["retirees"] or b["branche"] in deja_vues:
                continue
            if train_ready.in_origin_main(ws, b["sommet"]) is True:
                deja_vues.add(b["branche"])
                fusion = _merge_time(ws, b["sommet"])
                delai = max(0, int((fusion - epoch_of(r["utc"])) // 60)) if fusion is not None else None
                apres.append({"branche": b["branche"], "retenue": r["paris"], "delai_min": delai})
    ecartees, vues_ecartees = [], set()
    for r in reversed(passages):   # la raison la plus récente d'abord
        for e in r["ecartees"]:
            if e["branche"] in deja_vues or e["branche"] in vues_ecartees or not e.get("sommet") or e["raison"] in ("deja-fusionnee", "branche-absente"):
                continue
            if train_ready.in_origin_main(ws, e["sommet"]) is True:
                vues_ecartees.add(e["branche"])
                ecartees.append({"branche": e["branche"], "raison": e["raison"]})
    connues = {b["branche"] for r in read_journal() if r.get("type") == "passage" for b in r.get("retenues", []) + r.get("ecartees", [])}
    code, sortie = train_ready.git(ws, "log", "--first-parent", "--merges", f"--since={int(depuis)}", "--format=%s", "refs/remotes/origin/main")
    noms = []
    for ligne in sortie.splitlines() if code == 0 else []:
        m = re.match(r"^Merge branch '(.+?)'", ligne)
        if m and m.group(1) not in connues and m.group(1) not in noms:
            noms.append(m.group(1))
    try:
        garde = Guard()
        affichables = [CATALOGS["fr"]["masked_branch"] if garde.matches(n) else n for n in noms]
    except sensitive_names.SensitiveNamesUnavailable:
        affichables = []   # comptes seulement : sans la garde, aucun nom n'est montré
    return {"format": EXPECTED_FORMAT, "jours": days, "passages": len(passages), "jours_observes": len(jours), "par_decision": par_decision,
            "par_raison": par_raison, "par_jour": par_jour, "fusionnees_apres_observation": apres, "fusionnees_ecartees": ecartees,
            "fusionnees_non_listees": affichables, "non_listees": len(noms)}


def cmd_observation(args, t):
    if args.days < 1 or args.days > 366:
        raise Stop(2, "train_auto : --days attend un nombre entier de 1 à 366")
    try:
        bilan = observation_summary(args.days)
    except lab_paths.LabPathsError:
        raise Stop(4, t("folders")) from None
    if args.json:
        print(json.dumps(bilan, ensure_ascii=False))
        return 0
    print(t("obs_header", days=bilan["jours"], passes=bilan["passages"], observed=bilan["jours_observes"]))
    for jour in sorted(bilan["par_jour"]):
        print(t("obs_day", date=jour, n=bilan["par_jour"][jour]["passages"]))
    for nom in sorted(bilan["par_decision"]):
        print(t("obs_decision", name=decision_label(nom, t.language), n=bilan["par_decision"][nom]))
    for nom in sorted(bilan["par_raison"]):
        print(t("obs_reason", name=reason_label(nom, t.language), n=bilan["par_raison"][nom]))
    for b in bilan["fusionnees_apres_observation"]:
        print(t("obs_merged", branch=b["branche"], date=b["retenue"], delay="?" if b["delai_min"] is None else b["delai_min"]))
    for b in bilan["fusionnees_ecartees"]:
        print(t("obs_excluded", branch=b["branche"], label=reason_label(b["raison"], t.language)))
    for nom in bilan["fusionnees_non_listees"]:
        print(t("obs_unlisted", branch=nom))
    print(t("obs_counts", merged=len(bilan["fusionnees_apres_observation"]), excluded=len(bilan["fusionnees_ecartees"]), unlisted=bilan["non_listees"]))
    return 0


def cmd_arret(args, t):
    clock = Clock(os.environ)
    try:
        create_stop_file()
        append_journal(event_record("arret", os.environ, clock, args.raison), clock.now())
    except OSError:
        raise Stop(4, t("not_writable")) from None
    print(t("stop_set"))
    return 0


def cmd_reprendre(args, t):
    if in_session(os.environ):
        raise Stop(3, t("session_refused"))
    clock = Clock(os.environ)
    try:
        train_ready.ensure_data_dir()
        try:
            stop_path().unlink()
        except FileNotFoundError:
            pass
        append_journal(event_record("reprendre", os.environ, clock), clock.now())
    except OSError:
        raise Stop(4, t("not_writable")) from None
    print(t("stop_lifted"))
    return 0


def _status_or_stop(t):
    try:
        return activation_status()
    except train_record.Unreadable:
        raise Stop(4, t("record_unreadable")) from None
    except lab_paths.LabPathsError:
        raise Stop(4, t("folders")) from None


def _missing_lines(statut, t):
    return [t("activation_missing", label=reason_label(code, t.language)) for code in statut["missing"]]


def cmd_activation(args, t):
    """La série de trains verts (D5) : permis en session, lecture seule. Le texte et le JSON viennent du même dictionnaire."""
    statut = _status_or_stop(t)
    if args.json:
        print(json.dumps(statut, ensure_ascii=False))
        return 0
    print(t("activation_head", k=statut["series"], n=statut["required"]))
    for ligne in _missing_lines(statut, t):
        print(ligne)
    return 0


def cmd_activer(args, t):
    """Le geste unique de l'auteur (D6) : refusé en session (3) et quand la condition n'est pas remplie (7, rien d'écrit) ; sinon écrit le fichier d'activation
    par un fichier temporaire renommé (propriétaire seul), journalise `activer`."""
    if in_session(os.environ):
        raise Stop(3, t("session_refused"))
    statut = _status_or_stop(t)
    if not statut["met"]:
        for ligne in _missing_lines(statut, t):
            print(ligne, file=sys.stderr)
        raise Stop(7, t("activation_refused"))
    clock = Clock(os.environ)
    try:
        train_ready.ensure_data_dir()
        _atomic_write(activation_path(), json.dumps({"format": EXPECTED_FORMAT, "heure": iso_utc(clock.now()), "serie": statut["serie"]}) + "\n")
        if activation_state() != "valide":   # un fichier que le seul lecteur ne trouve pas valide ne reste jamais
            activation_path().unlink()
            raise OSError("activation invalide")
        append_journal(event_record("activer", os.environ, clock), clock.now())
    except OSError:
        raise Stop(4, t("not_writable")) from None
    print(t("activated"))
    return 0


def cmd_desactiver(args, t):
    """Permis à tous, parce qu'il ne fait que renforcer (D6) : retire le fichier d'activation, journalise `desactiver`, ne touche ni l'arrêt ni la liste."""
    clock = Clock(os.environ)
    try:
        train_ready.ensure_data_dir()
        deja = not activation_path().exists() and not activation_path().is_symlink()
        if not deja:
            activation_path().unlink()
        append_journal(event_record("desactiver", os.environ, clock), clock.now())
    except OSError:
        raise Stop(4, t("not_writable")) from None
    print(t("already_deactivated") if deja else t("deactivated"))
    return 0


def job_path(dossier, home):
    """Le PATH du job launchd (faux 65, D1), calculé par cette seule fonction : le dossier de l'interpréteur, le dossier fnm par défaut du compte (sous `home`, `FNM_DIR` ignorée),
    puis les dossiers du système (JOB_PATH_SYSTEME), joints par « : » ; un dossier en double garde sa première place. Remplace : le PATH par défaut de launchd pour le job. Retrait :
    permanent tant que le job existe (R-20261110-14)."""
    vus = []
    for d in (str(dossier), str(Path(home) / FNM_DEFAULT_RELATIVE), *JOB_PATH_SYSTEME):
        if d not in vus:
            vus.append(d)
    return ":".join(vus)


def path_fingerprint(path):
    """Les 16 premiers chiffres hexadécimaux du SHA-256 de `PATH=<path>` : l'empreinte du PATH d'un job, jamais le PATH lui-même."""
    return hashlib.sha256(("PATH=" + path).encode("utf-8")).hexdigest()[:16]


def plist_model(interpreter, run, home):
    """Le modèle launchd sous forme de dictionnaire, depuis les constantes de l'outil (seule source de l'horaire) ; `plist` l'imprime. `interpreter` : l'interpréteur de la génération
    (`sys.executable`) : il lance le passage dans ProgramArguments (R-20261110-34 ; remplace : /usr/bin/python3 du système ; retrait : permanent tant que le job existe) et son dossier ouvre
    le PATH du job. L'auteur seul installe et charge le modèle."""
    home = Path(home)
    journal = str(home / LOG_RELATIVE)
    return {
        "Label": LABEL,
        "ProgramArguments": [str(interpreter), "-I", str(Path(run) / "tools" / "train_auto.py"), "pass"],
        "WorkingDirectory": str(run),
        "EnvironmentVariables": {"PATH": job_path(Path(interpreter).parent, home)},
        "StartCalendarInterval": [{"Hour": minutes_of(debut) // 60, "Minute": minutes_of(debut) % 60} for debut, _ in WINDOWS],
        "StandardOutPath": journal,
        "StandardErrorPath": journal,
    }


def plist_bytes(run=None, home=None, interpreter=None):
    """Le modèle launchd en octets (liste de propriétés). Sans `run`, le dossier d'exécution des dossiers du lab ; sans `home`, le dossier personnel ; sans `interpreter`, celui qui tourne."""
    if run is None:
        run = lab_paths.run_tree(lab_paths.content_root())
    home = Path(home) if home else Path.home()
    return plistlib.dumps(plist_model(interpreter or sys.executable, run, home))


def generation_refusal(version, executable):
    """Le refus de générer (D2) : (clé du message, champs) quand l'interpréteur est plus ancien que 3.10, ou quand son dossier ne porte pas de `python3` qui est le même fichier (sans lui,
    `python3` dans le PATH du job résoudrait ailleurs) ; None sinon. Remplace : rien. Retrait : permanent tant que le job existe."""
    if tuple(version[:2]) < PYTHON_MINIMUM:
        return "plist_old_python", {"version": f"{version[0]}.{version[1]}"}
    candidat = Path(executable).parent / "python3"
    try:
        identique = candidat.exists() and os.path.realpath(candidat) == os.path.realpath(executable)
    except OSError:
        identique = False
    if not identique:
        return "plist_no_python3", {}
    return None


def _python_version(python):
    """La version (majeure, mineure) d'un `python3` par `--version`, délai de 5 secondes, entrée standard fermée ; None quand elle n'est pas lisible."""
    try:
        fait = subprocess.run([str(python), "--version"], capture_output=True, text=True, timeout=VERSION_TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"Python (\d+)\.(\d+)", fait.stdout + fait.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else None


def installed_plist_check(home=None, run=None):
    """Le modèle installé de `~/Library/LaunchAgents/<LABEL>.plist`, en lecture seule (D10, D11), partagé avec le doctor. Rend {"state", "env_job", "mtime", "differences"} :
    `absent` (non installé) ; `illisible` (pas une liste de propriétés ou pas un dictionnaire) ; `python-absent` (pas de `python3` dans le premier dossier de son PATH) ;
    `python-ancien` (son `python3` répond une version de moins de 3.10, ou aucune version lisible) ; `different` (le modèle installé diffère de plist_model(<ce python3>, run, home) ;
    `differences` : les clés de premier niveau qui diffèrent) ; `ok`. `env_job` : l'empreinte de son PATH (None sans PATH) ; `mtime` : sa date de modification. L'interpréteur de
    l'appelant (le doctor) n'entre jamais dans la comparaison : le modèle est reconstruit avec le dossier du `python3` du modèle installé. Ne charge, n'écrit ni ne régénère rien. Remplace : rien. Retrait : avec le job
    (R-20261110-14)."""
    home = Path(home) if home else Path.home()
    verdict = {"state": "absent", "env_job": None, "mtime": None, "differences": []}
    chemin = home / INSTALLED_PLIST_RELATIVE / f"{LABEL}.plist"
    try:
        info = chemin.stat()
    except FileNotFoundError:
        return verdict
    except OSError:
        verdict["state"] = "illisible"
        return verdict
    verdict["mtime"] = info.st_mtime
    try:
        installe = plistlib.loads(chemin.read_bytes())
    except Exception:   # noqa: BLE001 : toute lecture ratée est « illisible », sans texte
        installe = None
    if not isinstance(installe, dict):
        verdict["state"] = "illisible"
        return verdict
    env = installe.get("EnvironmentVariables")
    path = env.get("PATH") if isinstance(env, dict) else None
    if isinstance(path, str) and path:
        verdict["env_job"] = path_fingerprint(path)
        python = Path(path.split(":")[0]) / "python3"
        if not (python.is_file() and os.access(python, os.X_OK)):
            verdict["state"] = "python-absent"
            return verdict
        version = _python_version(python)
        if version is None or version < PYTHON_MINIMUM:
            verdict["state"] = "python-ancien"
            return verdict
        interprete = python
    else:
        # sans PATH, l'écart est celui de EnvironmentVariables : l'interpréteur du modèle installé sert de référence, pour que seules les autres clés comptent
        lancement = installe.get("ProgramArguments")
        interprete = Path(lancement[0]) if isinstance(lancement, list) and lancement and isinstance(lancement[0], str) else Path(sys.executable)
        python = None
    if run is None:
        try:
            run = lab_paths.run_tree(lab_paths.content_root())
        except lab_paths.LabPathsError:
            run = installe.get("WorkingDirectory", "")
    modele = plist_model(interprete, run, home)
    lancement = installe.get("ProgramArguments")
    if python is not None and isinstance(lancement, list) and lancement and isinstance(lancement[0], str):
        # R-20261110-34 : l'interpréteur de ProgramArguments doit être le python3 du premier dossier du PATH (même chemin réel, un autre nom du même fichier est permis) ;
        # sinon l'écart reste, sous la clé ProgramArguments
        try:
            meme = os.path.realpath(lancement[0]) == os.path.realpath(python)
        except OSError:
            meme = False
        if meme:
            installe = dict(installe, ProgramArguments=[str(interprete), *lancement[1:]])
    verdict["differences"] = sorted(k for k in set(modele) | set(installe) if modele.get(k) != installe.get(k))
    verdict["state"] = "different" if verdict["differences"] else "ok"
    return verdict


def launchd_trial_status(journal, installed):
    """D10 : vrai quand un enregistrement de passage du `journal` a l'appelant `launchd`, un essai dont le code final (celui de la relance, s'il y en a une) est 0, un `env_job` égal à celui
    du modèle `installed` (rendu par installed_plist_check) et une heure `utc` postérieure à sa date de modification. Le modèle installé doit être à l'état `ok` du contrôle F6 (conforme au
    modèle calculé), pas seulement présent et lisible (R-20261110-39) ; absent, illisible, différent, `python-absent`, `python-ancien`, sans empreinte ou sans date de
    modification : faux (la condition manque). Un appelant terminal ne compte jamais ; une empreinte nulle n'est égale à rien. Lecture seule. Remplace : rien. Retrait : permanent, tant que l'activation existe."""
    if installed.get("state") != "ok":
        return False
    attendu, mtime = installed.get("env_job"), installed.get("mtime")
    if not isinstance(attendu, str) or not attendu or not isinstance(mtime, (int, float)):
        return False
    for rec in journal:
        if not isinstance(rec, dict) or rec.get("type") != "passage" or rec.get("caller") != "launchd" or rec.get("env_job") != attendu:
            continue
        essai = rec.get("essai")
        if not isinstance(essai, dict) or final_code(essai) != 0:
            continue
        try:
            if epoch_of(rec["utc"]) > mtime:
                return True
        except (KeyError, ValueError, TypeError):
            continue
    return False


def cmd_plist(args, t):
    refus = generation_refusal(sys.version_info, sys.executable)
    if refus is not None:   # code 8 : rien sur la sortie standard, jamais un modèle partiel
        raise Stop(8, t(refus[0], **refus[1]))
    try:
        texte = plist_bytes().decode("utf-8")
    except lab_paths.LabPathsError:
        raise Stop(4, t("folders")) from None
    print(texte, end="")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="train_auto.py", description="Passage du train automatique (observation, ou fusion après l'activation de l'auteur).")
    add_language_option(p)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pass", help="un passage : décide, observe par l'essai, journalise")
    s = sub.add_parser("status", help="le dernier état")
    s.add_argument("--json", action="store_true")
    o = sub.add_parser("observation", help="le bilan des jours observés")
    o.add_argument("--days", type=int, default=7)
    o.add_argument("--json", action="store_true")
    a = sub.add_parser("arret", help="pose l'arrêt d'urgence")
    a.add_argument("--raison", default="manuel")
    sub.add_parser("reprendre", help="lève l'arrêt d'urgence (refusé en session)")
    sub.add_parser("plist", help="écrit le modèle launchd")
    c = sub.add_parser("activation", help="la série de trains verts requise pour activer la fusion automatique")
    c.add_argument("--json", action="store_true")
    sub.add_parser("activer", help="active la fusion automatique (le geste de l'auteur ; refusé en session)")
    sub.add_parser("desactiver", help="désactive la fusion automatique")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)   # une erreur d'usage sort avec le code 2
    t = Messages(CATALOGS, args.language)
    try:
        return {"pass": cmd_pass, "status": cmd_status, "observation": cmd_observation, "arret": cmd_arret, "reprendre": cmd_reprendre,
                "plist": cmd_plist, "activation": cmd_activation, "activer": cmd_activer, "desactiver": cmd_desactiver}[args.cmd](args, t)
    except Stop as e:
        if e.message:
            print(e.message, file=sys.stderr)
        return e.code
    except Exception as e:   # jamais de trace de pile : le type seulement
        print(t("unexpected", kind=type(e).__name__), file=sys.stderr)
        return 6


if __name__ == "__main__":
    sys.exit(main())
