"""
Tests de l'enchaînement de tools/watch.sh avec de fausses commandes.

    python3 -m unittest discover -s tests/watch_sh -v

Le script est lancé avec un faux HOME. Il place `$HOME/.local/bin` en tête du PATH : on y met un faux `uv`, un
faux `curl` et un faux `osascript` (la notification macOS), qui notent leurs appels dans un fichier et échouent à la demande (variable ECHEC : liste de
« script.py commande » séparés par des virgules ; ECHEC_CODE :
leur code de sortie ; CURL_CODE : code de sortie du faux curl). La vraie veille,
les vrais scripts, Ollama et launchd ne sont jamais touchés.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "watch.sh"

FAUX_UV = """#!/bin/sh
# uv run <script> [commande...] : note « script commande » et échoue si ECHEC le demande
# uv --version et uv python find --show-version : versions de FAUX_UV_VERSION et FAUX_PYTHON_VERSION (sans note)
[ "$1" = "--version" ] && { echo "uv ${FAUX_UV_VERSION:-0.13.0}"; exit 0; }
# uv python find lit .python-version du dossier courant s'il existe (le dossier de code), sinon FAUX_PYTHON_VERSION
[ "$1" = "python" ] && { [ -n "${FAUX_PYTHON_ABSENT:-}" ] && exit 2; [ -f .python-version ] && { cat .python-version; exit 0; }; echo "${FAUX_PYTHON_VERSION:-3.14.8}"; exit 0; }
echo "$* (args complets)" >> "$APPELS_COMPLETS"
echo "$* WS=${PMZILLA_LAB_WORKSPACE:-}" >> "$HOME/espaces.txt"
[ "$2" = "--python" ] && set -- "$1" "$4"   # uv run --python <version> <script> : le script redevient le 2e argument
[ "$2" = "--offline" ] && { premier="$1"; shift 2; set -- "$premier" "$@"; }   # uv run --offline <script> <commande> (tests de mutation)
script=$(basename "$2")
appel="$script${3:+ $3}"
# le résumé du matin (R-50) : appel noté à part (APPELS_RESUME) avec le repère tel qu'il est à cet instant ; rend RESUME_CODE (0 par défaut),
# et, s'il rend 0, une notification de résumé (le vrai script en envoie une) notée comme celles de osascript
if [ "$script" = "morning_summary.py" ]; then
  echo "$2 $3 $4 $5 | NOTIFY=${PMZILLA_SUMMARY_NOTIFY:-}" >> "$APPELS_RESUME"
  cp "${PMZILLA_LAB_DATA:-$HOME/.pmzilla-lab}/veille-du-jour.json" "$HOME/repere-a-l-appel.json" 2>/dev/null
  [ "${RESUME_CODE:-0}" = 0 ] && echo "osascript résumé du matin $*" >> "$APPELS"
  exit "${RESUME_CODE:-0}"
fi
# le script jetable du contrôle : « controle_cache.py » avec le réseau, « controle_cache.py hors-ligne » avec UV_OFFLINE
if [ "$script" = "controle_cache.py" ]; then
  [ -n "${UV_OFFLINE:-}" ] && appel="controle_cache.py hors-ligne"
  cp "$2" "$HOME/jetable-${UV_OFFLINE:+hors-ligne}.py"
fi
echo "$appel" >> "$APPELS"
case ",${ECHEC:-}," in *",$appel,"*) echo "faux échec de $appel" >&2; exit "${ECHEC_CODE:-1}";; esac
echo "faux uv : $appel"
exit 0
"""
FAUX_OSASCRIPT = """#!/bin/sh
echo "osascript $*" >> "$APPELS"
exit "${OSASCRIPT_CODE:-0}"
"""
FAUX_CURL = """#!/bin/sh
echo "curl $*" >> "$APPELS"
exit "${CURL_CODE:-0}"
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()   # chemin résolu : le dossier de code l'est aussi
        self.addCleanup(shutil.rmtree, self.home, True)
        bin_ = self.home / ".local" / "bin"
        bin_.mkdir(parents=True)
        for nom, texte in (("uv", FAUX_UV), ("curl", FAUX_CURL), ("osascript", FAUX_OSASCRIPT)):
            (bin_ / nom).write_text(texte)
            (bin_ / nom).chmod(0o755)
        outils = self.home / "PMZilla-Lab" / "workspace" / "tools"      # watch.sh y appelle watch_paths.py (le vrai)
        outils.mkdir(parents=True)
        shutil.copy(SCRIPT.parent / "watch_paths.py", outils / "watch_paths.py")
        shutil.copy(SCRIPT.parent / "lab_paths.sh", outils / "lab_paths.sh")
        shutil.copy(SCRIPT.parent / "lab_paths.py", outils / "lab_paths.py")
        shutil.copy(SCRIPT, outils / "watch.sh")      # dépôt de développement factice : dossier de code et dossier de contenu à la fois
        self.script = outils / "watch.sh"
        self.appels = self.home / "appels.txt"
        self.complets = self.home / "complets.txt"
        self.appels_resume = self.home / "appels-resume.txt"
        reveil = self.home / "PMZilla-Lab" / "workspace" / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts"
        reveil.mkdir(parents=True)
        (reveil / "wake.py").write_text("# /// script\n# dependencies = [\"pyyaml\"]\n# ///\nraise SystemExit('jamais exécuté')\n")
        self.versions()   # par défaut, les versions enregistrées sont celles du faux uv : pas de contrôle du cache

    def versions(self, uv: str = "uv 0.13.0", python: str = "3.14.8"):
        """Versions de uv et de Python enregistrées par la veille (fichiers de ~/.pmzilla-lab)."""
        donnees = self.home / ".pmzilla-lab"
        donnees.mkdir(parents=True, exist_ok=True)
        (donnees / "uv-version").write_text(uv + "\n")
        (donnees / "uv-python-version").write_text(python + "\n")

    def repere(self, jours: float | None = None, contenu: str | None = None) -> Path:
        """Date de la dernière indexation réussie, il y a `jours` jours (fichier repère de watch.sh)."""
        fichier = self.home / ".pmzilla-lab" / "derniere-indexation"
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(contenu if contenu is not None else str(int(time.time() - jours * 86400)))
        return fichier

    def lancer(self, echec: str = "", curl: int = 0, osascript: int = 0, args=(), script=None, **environnement):
        env = {k: v for k, v in os.environ.items()
               if k not in ("PMZILLA_LAB_DATA", "PMZILLA_INDEXATION_MAX_JOURS", "PMZILLA_LAB_WORKSPACE", "PMZILLA_LAB_RUN", "PMZILLA_LAB_OLLAMA")
               and not k.startswith("PMZILLA_WATCH_")}
        env = {**env, "PMZILLA_LAB_WORKSPACE": str(self.home / "PMZilla-Lab" / "workspace"), **environnement, "HOME": str(self.home), "APPELS": str(self.appels),
               "APPELS_COMPLETS": str(self.complets), "APPELS_RESUME": str(self.appels_resume), "ECHEC": echec, "CURL_CODE": str(curl),
               "OSASCRIPT_CODE": str(osascript)}
        resultat = subprocess.run(["zsh", str(script or self.script), *args], env=env, capture_output=True, text=True, timeout=60)
        appels = self.appels.read_text().splitlines() if self.appels.exists() else []
        self.notifications = [a for a in appels if a.startswith("osascript")]
        return resultat, [a for a in appels if not a.startswith(("curl", "osascript"))]


class BaseDeDonnees(Base):
    """Étape « base de données » (R-22) : `watch_lab.py check-db --wait N` après le contrôle du cache de uv et avant la collecte.
    Un faux `check-db` rend 0, 4 ou 5 ; la veille ne démarre jamais la base."""

    SAUTEES = ("watch_lab.py collect", "watch_lab.py digest", "watch_triage.py score", "watch_triage.py apply",
               "watch_triage.py shares", "watch_triage.py digest", "pmzilla_lab_library.py index", "pmzilla_lab_library.py probe")

    def sans_base(self, code, **environnement):
        return self.lancer(echec="watch_lab.py check-db", ECHEC_CODE=str(code), **environnement)

    def verifier_jour_saute(self, resultat, appels):
        self.assertEqual(appels, ["watch_lab.py check-db", "composants.py check", "mutation_masking.py run", "dashboard.py"])   # composants, mutation, tableau de bord
        for sautee in self.SAUTEES:
            self.assertNotIn(sautee, appels)
        self.assertIn("=== Veille terminée avec 1 étape(s) en échec : base de données ===", resultat.stdout)
        self.assertTrue(resultat.stdout.rstrip().endswith("base de données ==="))
        self.assertEqual(len(self.notifications), 1)                                 # une seule notification
        self.assertIn("base de données", self.notifications[0])
        self.assertEqual(resultat.returncode, 1)
        self.assertFalse(any("db_up" in a for a in self.appels.read_text().splitlines()))   # elle ne démarre pas la base

    def test_base_prete_les_etapes_suivent_apres_la_verification(self):
        resultat, appels = self.lancer()
        self.assertEqual(appels[0], "watch_lab.py check-db")
        self.assertEqual(appels[1], "watch_lab.py collect")
        self.assertEqual(resultat.returncode, 0)
        self.assertEqual(self.notifications, [])

    def test_base_qui_ne_repond_pas_saute_le_jour(self):
        resultat, appels = self.sans_base(4)
        self.assertRegex(resultat.stdout, r"Base de données injoignable à \d\d:\d\d : collecte, pré-tri, listes à lire et indexation du jour "
                                          r"sautés, rien n'est écrit ailleurs\.")
        self.verifier_jour_saute(resultat, appels)

    def test_tables_absentes_sautent_le_jour(self):
        resultat, appels = self.sans_base(5)
        self.assertIn("Tables de la veille absentes : collecte, pré-tri, listes à lire et indexation du jour sautés.", resultat.stdout)
        self.assertNotIn("Base de données injoignable", resultat.stdout)
        self.verifier_jour_saute(resultat, appels)

    def test_attente_par_defaut_reglee_ou_invalide(self):
        cas = {None: "120", "45": "45", "0": "0", "abc": "120", "1.5": "120", "-5": "120", "": "120", "12 3": "120"}
        for valeur, attendue in cas.items():
            with self.subTest(valeur=valeur):
                self.complets.unlink(missing_ok=True)
                self.appels.unlink(missing_ok=True)
                self.lancer(**({} if valeur is None else {"PMZILLA_WATCH_DB_WAIT": valeur}))
                ligne = next(l for l in self.complets.read_text().splitlines() if "check-db" in l)
                self.assertRegex(ligne, rf"watch_lab\.py check-db --wait {attendue} ")

    def test_la_verification_precede_la_collecte_et_suit_le_controle_du_cache(self):
        self.versions(uv="uv 0.12.0")
        _, appels = self.lancer()
        self.assertEqual(appels[:4], ["controle_cache.py", "controle_cache.py hors-ligne", "watch_lab.py check-db", "watch_lab.py collect"])

    def test_le_jour_saute_ne_touche_pas_au_repere_d_indexation(self):
        repere = self.repere(contenu="1000")
        self.sans_base(4)
        self.assertEqual(repere.read_text(), "1000")

    def test_base_perdue_pendant_le_pre_tri_les_deux_echecs_sont_nommes_dans_l_ordre(self):
        resultat, appels = self.lancer(echec="watch_triage.py score,watch_lab.py digest", ECHEC_CODE="4")
        self.assertEqual(appels[:3], ["watch_lab.py check-db", "watch_lab.py collect", "watch_triage.py score"])
        self.assertIn("watch_lab.py digest", appels)                      # la liste simple a été tentée
        self.assertIn("Pré-tri en erreur : liste à lire non triée", resultat.stdout)
        self.assertIn("Liste à lire en erreur", resultat.stdout)
        self.assertIn("=== Veille terminée avec 2 étape(s) en échec : pré-tri, liste à lire ===", resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(resultat.returncode, 1)

    def test_le_texte_du_script_ne_nomme_aucun_ancien_fichier_d_etat(self):
        texte = SCRIPT.read_text(encoding="utf-8")
        for ancien in ("veille.sqlite", "tri.sqlite", "STATE_DB", "TRI_DB"):
            self.assertNotIn(ancien, texte)


class Rattrapage(Base):
    """Rattrapage (R-44) : repère du jour, heure due et limite, fuseau d'Europe/Paris, reprise, verrou, report, écriture du repère.
    L'instant est injecté (PMZILLA_WATCH_NOW) ; le processus tourne dans un fuseau éloigné de Paris."""

    ZONE = "Pacific/Auckland"
    CLE_ILLISIBLE = "Repère du passage du jour illisible : passage considéré comme dû"
    CLE_ECRITURE = "Repère du passage du jour impossible à écrire : veille non lancée"
    CLE_REPORT = "Veille du jour reportée : nouvel essai au prochain passage planifié"
    CLE_RATTRAPAGE = "Passage de rattrapage : la veille du jour n'avait pas eu lieu"
    CLE_REPRISE = "Passage du jour interrompu : nouvel essai, le seul de la journée"
    CLE_PERIME = "Verrou de la veille périmé, repris"
    CLE_EN_COURS = "=== Veille non lancée : un passage est déjà en cours ==="
    EN_TETE = r"^=== \d{4}-\d\d-\d\d \d\d:\d\d ===$"

    def setUp(self):
        super().setUp()
        self.donnees = self.home / ".pmzilla-lab"
        self.fichier_repere = self.donnees / "veille-du-jour.json"
        self.verrou = self.donnees / "veille.verrou"
        self.alerte = self.home / "Library" / "Logs" / "pmzilla-watch-alerte"

    # Aides
    @staticmethod
    def instant(jour: str, heure: str, fold: int = 0) -> str:
        a, m, j = (int(x) for x in jour.split("-"))
        h, mn = (int(x) for x in heure.split(":"))
        return str(int(datetime(a, m, j, h, mn, tzinfo=ZoneInfo("Europe/Paris"), fold=fold).timestamp()))

    def planifie(self, heure="08:00", jour="2026-10-14", option="--if-due", fold=0, **env):
        env.setdefault("TZ", self.ZONE)
        return self.lancer(args=[option], PMZILLA_WATCH_NOW=self.instant(jour, heure, fold), **env)

    def manuel(self, heure="08:00", jour="2026-10-14", **env):
        env.setdefault("TZ", self.ZONE)
        return self.lancer(PMZILLA_WATCH_NOW=self.instant(jour, heure), **env)

    def ecrire_repere(self, etat="termine", date="2026-10-14", **champs):
        contenu = {"date": date, "declencheur": "calendrier", "debut": "07:10", "fin": "07:40", "etat": etat,
                   "code": 0 if etat == "termine" else None, "notifie": False, "essais": 0, "reprises": 0, **champs}
        self.donnees.mkdir(parents=True, exist_ok=True)
        self.fichier_repere.write_text(json.dumps(contenu))
        return self.fichier_repere.read_bytes()

    def lire(self) -> dict:
        return json.loads(self.fichier_repere.read_text())

    def verifier_rien(self, resultat, appels, avant=None):
        """Lancement planifié sans rien à faire : code 0, ni journal, ni outil, ni notification, ni verrou, repère inchangé."""
        self.assertEqual(resultat.returncode, 0)
        self.assertEqual((resultat.stdout, resultat.stderr), ("", ""))
        self.assertEqual(appels, [])
        self.assertEqual(self.notifications, [])
        self.assertFalse(self.verrou.exists())
        if avant is None:
            self.assertFalse(self.fichier_repere.exists())
        else:
            self.assertEqual(self.fichier_repere.read_bytes(), avant)

    def verifier_jour_complet(self, appels):
        self.assertIn("watch_lab.py collect", appels)
        self.assertIn("dashboard.py", appels)

    def verrou_vivant(self, debut=None):
        """Verrou tenu par un processus vivant (un sleep lancé par le test)."""
        processus = subprocess.Popen(["sleep", "300"])
        self.addCleanup(lambda: (processus.kill(), processus.wait()))
        self.verrou.mkdir(parents=True)
        (self.verrou / "pid").write_text(str(processus.pid))
        if debut is not None:
            (self.verrou / "debut").write_text(str(debut))

    def verrou_mort(self):
        processus = subprocess.Popen(["true"])
        processus.wait()
        self.verrou.mkdir(parents=True)
        (self.verrou / "pid").write_text(str(processus.pid))

    def espionner_uv(self, appel: str, commande: str):
        """Le faux uv exécute `commande` (shell) quand il est appelé pour `appel`."""
        (self.home / ".local" / "bin" / "uv").write_text(FAUX_UV.replace(
            'echo "$appel" >> "$APPELS"', 'echo "$appel" >> "$APPELS"\n[ "$appel" = "%s" ] && { %s; }' % (appel, commande)))

    # 4.1 et 4.2 : options, constantes, repère
    def test_option_inconnue_code_2_avant_tout_outil_sans_repere_ni_verrou(self):
        (self.home / "PMZilla-Lab" / "workspace" / "Veille-Lab").mkdir()   # l'option est vérifiée avant le dossier de la veille
        for args in (["--bidon"], ["--if-due", "--catch-up"], ["--IF-DUE"]):
            with self.subTest(args=args):
                resultat, appels = self.lancer(args=args)
                self.assertEqual(resultat.returncode, 2)
                self.assertEqual(appels, [])
                self.assertNotEqual(resultat.stderr, "")
                self.assertEqual(resultat.stdout, "")
                self.assertFalse(self.fichier_repere.exists())
                self.assertFalse(self.verrou.exists())
                self.assertEqual(self.notifications, [])

    def test_constantes_sur_une_ligne_exacte(self):
        texte = SCRIPT.read_text(encoding="utf-8")
        self.assertRegex(texte, r'(?m)^HEURE_DUE="07:10"$')
        self.assertRegex(texte, r'(?m)^HEURE_LIMITE="22:00"$')

    def test_avant_l_heure_due_rien_n_est_fait_ni_ecrit(self):
        for option in ("--if-due", "--catch-up"):
            self.verifier_rien(*self.planifie(heure="07:09", option=option))

    def test_a_l_heure_due_exactement_le_passage_a_lieu(self):
        resultat, appels = self.planifie(heure="07:10")
        self.assertEqual(resultat.returncode, 0)
        self.verifier_jour_complet(appels)

    def test_sans_repere_apres_l_heure_due_le_passage_a_lieu_et_le_repere_est_ecrit(self):
        resultat, appels = self.planifie()
        self.assertEqual(resultat.returncode, 0)
        self.verifier_jour_complet(appels)
        repere = self.lire()
        self.assertEqual((repere["date"], repere["declencheur"], repere["debut"], repere["etat"], repere["code"]),
                         ("2026-10-14", "calendrier", "08:00", "termine", 0))
        self.assertRegex(repere["fin"], r"^\d\d:\d\d$")
        self.assertEqual((repere["notifie"], repere["essais"], repere["reprises"]), (False, 0, 0))
        self.assertEqual(self.fichier_repere.stat().st_mode & 0o777, 0o600)
        self.assertEqual([p.name for p in self.donnees.iterdir() if p.name.startswith(".veille")], [])   # aucun temporaire
        self.assertFalse(self.verrou.exists())

    def test_repere_pendant_le_passage_dit_commence(self):
        self.espionner_uv("watch_lab.py collect", 'cp "$HOME/.pmzilla-lab/veille-du-jour.json" "$HOME/pendant.json"')
        self.planifie()
        pendant = json.loads((self.home / "pendant.json").read_text())
        self.assertEqual((pendant["etat"], pendant["code"], pendant["fin"]), ("commence", None, ""))

    def test_declencheurs_enregistres(self):
        self.planifie(option="--catch-up")
        self.assertEqual(self.lire()["declencheur"], "rattrapage")
        self.manuel()
        self.assertEqual(self.lire()["declencheur"], "manuel")

    def test_repere_d_un_autre_jour_le_passage_a_lieu(self):
        self.ecrire_repere("termine", date="2026-10-13")
        resultat, appels = self.planifie()
        self.verifier_jour_complet(appels)
        self.assertEqual(self.lire()["date"], "2026-10-14")
        self.assertNotIn(self.CLE_ILLISIBLE, resultat.stdout)

    def test_repere_illisible_cle_et_passage(self):
        for contenu in ("pas du json", "", '{"date": "2026-10-14"}', '{"date": "hier", "etat": "termine"}'):
            with self.subTest(contenu=contenu):
                self.appels.unlink(missing_ok=True)
                self.donnees.mkdir(exist_ok=True)
                self.fichier_repere.write_text(contenu)
                resultat, appels = self.planifie()
                self.assertIn(self.CLE_ILLISIBLE, resultat.stdout)
                self.verifier_jour_complet(appels)
                self.assertEqual(self.lire()["etat"], "termine")

    def test_repere_reporte_le_passage_a_lieu_et_garde_le_compte_du_jour(self):
        self.ecrire_repere("reporte", essais=1, notifie=True)
        resultat, appels = self.planifie()
        self.verifier_jour_complet(appels)
        repere = self.lire()
        self.assertEqual((repere["etat"], repere["essais"], repere["notifie"]), ("termine", 1, True))

    def test_passage_deja_termine_echoue_ou_interrompu_rien_n_est_fait(self):
        for etat in ("termine", "echoue", "interrompu"):
            with self.subTest(etat=etat):
                avant = self.ecrire_repere(etat, code=1 if etat == "echoue" else None)
                for option in ("--if-due", "--catch-up"):
                    self.verifier_rien(*self.planifie(option=option), avant=avant)

    def test_passage_echoue_est_enregistre_echoue_avec_son_code(self):
        resultat, _ = self.planifie(echec="watch_lab.py collect")
        self.assertEqual(resultat.returncode, 1)
        repere = self.lire()
        self.assertEqual((repere["etat"], repere["code"]), ("echoue", 1))
        self.assertEqual(len(self.notifications), 1)

    def test_surcharge_de_l_heure_due(self):
        self.verifier_rien(*self.planifie(heure="08:00", PMZILLA_WATCH_DUE_TIME="09:00"))
        _, appels = self.planifie(heure="09:00", PMZILLA_WATCH_DUE_TIME="09:00")
        self.verifier_jour_complet(appels)

    def test_surcharge_invalide_de_l_heure_due_prend_la_constante(self):
        for valeur in ("9h", "24:00", "07:60", "7:10", "", "abc"):
            with self.subTest(valeur=valeur):
                self.appels.unlink(missing_ok=True)
                self.fichier_repere.unlink(missing_ok=True)
                self.verifier_rien(*self.planifie(heure="07:00", PMZILLA_WATCH_DUE_TIME=valeur))
                _, appels = self.planifie(heure="07:10", PMZILLA_WATCH_DUE_TIME=valeur)
                self.verifier_jour_complet(appels)

    def test_instant_non_entier_est_ignore_et_l_horloge_du_systeme_sert(self):
        _, appels = self.lancer(args=["--if-due"], PMZILLA_WATCH_NOW="pas un entier", PMZILLA_WATCH_DUE_TIME="00:00",
                                PMZILLA_WATCH_LATEST_TIME="23:59")
        self.verifier_jour_complet(appels)
        self.assertRegex(self.lire()["date"], r"^\d{4}-\d\d-\d\d$")

    # 4.3 : heure limite
    def test_apres_l_heure_limite_rien_n_est_fait(self):
        for etat in (None, "reporte", "commence"):
            with self.subTest(etat=etat):
                avant = None if etat is None else self.ecrire_repere(etat)
                self.verifier_rien(*self.planifie(heure="22:01"), avant=avant)

    def test_a_l_heure_limite_exactement_le_passage_a_lieu(self):
        _, appels = self.planifie(heure="22:00")
        self.verifier_jour_complet(appels)

    def test_jour_reporte_ou_interrompu_n_est_plus_repris_apres_l_heure_limite(self):
        avant = self.ecrire_repere("reporte", essais=1, notifie=True)
        self.verifier_rien(*self.planifie(heure="23:30"), avant=avant)
        avant = self.ecrire_repere("commence")
        self.verifier_rien(*self.planifie(heure="23:30", option="--catch-up"), avant=avant)

    def test_lancement_manuel_non_borne_par_l_heure_limite_ni_l_heure_due(self):
        for heure in ("23:59", "03:00"):
            self.appels.unlink(missing_ok=True)
            _, appels = self.manuel(heure=heure)
            self.verifier_jour_complet(appels)
            self.assertEqual(self.lire()["declencheur"], "manuel")

    def test_surcharge_de_l_heure_limite(self):
        self.verifier_rien(*self.planifie(heure="20:01", PMZILLA_WATCH_LATEST_TIME="20:00"))
        _, appels = self.planifie(heure="20:00", PMZILLA_WATCH_LATEST_TIME="20:00")
        self.verifier_jour_complet(appels)

    def test_surcharge_invalide_de_l_heure_limite_prend_la_constante(self):
        for valeur in ("abc", "25:00", "8h"):
            with self.subTest(valeur=valeur):
                self.appels.unlink(missing_ok=True)
                self.fichier_repere.unlink(missing_ok=True)
                self.verifier_rien(*self.planifie(heure="22:01", PMZILLA_WATCH_LATEST_TIME=valeur))
                _, appels = self.planifie(heure="22:00", PMZILLA_WATCH_LATEST_TIME=valeur)
                self.verifier_jour_complet(appels)

    # 4.4 : le jour d'Europe/Paris
    def test_apres_l_heure_due_a_paris_mais_avant_dans_le_fuseau_du_processus(self):
        # 07:30 à Paris (été, UTC+2) = 22:30 la veille à Los Angeles : le jour et l'heure du processus sont ceux d'hier soir
        _, appels = self.planifie(heure="07:30", TZ="America/Los_Angeles")
        self.verifier_jour_complet(appels)
        repere = self.lire()
        self.assertEqual((repere["date"], repere["debut"]), ("2026-10-14", "07:30"))

    def test_avant_l_heure_due_a_paris_quel_que_soit_le_fuseau_du_processus(self):
        for zone in ("Pacific/Auckland", "America/Los_Angeles", "Asia/Tokyo", "Europe/Paris"):
            self.verifier_rien(*self.planifie(heure="06:30", TZ=zone))

    def test_juste_apres_minuit_a_paris_la_veille_est_un_autre_jour_et_rien_n_est_du(self):
        avant = self.ecrire_repere("termine", date="2026-10-14")
        # 00:05 le 15 à Paris = 15:05 le 14 à Los Angeles : encore la veille pour le processus
        self.verifier_rien(*self.planifie(heure="00:05", jour="2026-10-15", TZ="America/Los_Angeles"), avant=avant)

    def test_jour_ou_les_pendules_avancent_un_seul_passage(self):
        jour = "2026-03-29"
        _, appels = self.planifie(heure="07:10", jour=jour)
        self.verifier_jour_complet(appels)
        self.assertEqual(self.lire()["date"], jour)
        self.appels.unlink()
        self.verifier_rien(*self.planifie(heure="09:00", jour=jour), avant=self.fichier_repere.read_bytes())

    def test_jour_ou_les_pendules_reculent_heure_repetee_puis_un_seul_passage(self):
        jour = "2026-10-25"   # 02:00-03:00 se répète
        self.assertNotEqual(self.instant(jour, "02:30", 0), self.instant(jour, "02:30", 1))
        for fold in (0, 1):
            self.verifier_rien(*self.planifie(heure="02:30", jour=jour, fold=fold))
        _, appels = self.planifie(heure="07:10", jour=jour)
        self.verifier_jour_complet(appels)
        self.assertEqual(self.lire()["date"], jour)
        self.appels.unlink()
        self.verifier_rien(*self.planifie(heure="12:00", jour=jour), avant=self.fichier_repere.read_bytes())

    def test_l_age_du_verrou_est_en_secondes_ecoulees_pas_en_heures_murales(self):
        # Verrou créé à 22:00 la veille du retour à l'heure d'hiver ; lancement à 08:00 : 10 h murales, mais 11 h écoulées.
        # Seuil de 10 h 30 : périmé en secondes écoulées (il ne le serait pas en heures murales).
        self.verrou_vivant(debut=int(self.instant("2026-10-24", "22:00")))
        resultat, appels = self.planifie(heure="08:00", jour="2026-10-25", PMZILLA_WATCH_LOCK_MAX_AGE=str(10 * 3600 + 1800))
        self.assertIn(self.CLE_PERIME, resultat.stdout)
        self.verifier_jour_complet(appels)

    # 4.5 : reprise unique d'un passage interrompu
    def test_passage_interrompu_est_repris_une_fois(self):
        self.ecrire_repere("commence", reprises=0, declencheur="calendrier")
        resultat, appels = self.planifie(option="--catch-up")
        self.assertIn(self.CLE_REPRISE, resultat.stdout)
        self.verifier_jour_complet(appels)
        repere = self.lire()
        self.assertEqual((repere["reprises"], repere["etat"], repere["declencheur"]), (1, "termine", "rattrapage"))

    def test_deuxieme_interruption_marque_interrompu_sans_outil_ni_journal(self):
        self.ecrire_repere("commence", reprises=1)
        resultat, appels = self.planifie()
        self.assertEqual(resultat.returncode, 0)
        self.assertEqual((resultat.stdout, resultat.stderr, appels, self.notifications), ("", "", [], []))
        self.assertEqual(self.lire()["etat"], "interrompu")
        self.assertFalse(self.verrou.exists())
        self.verifier_rien(*self.planifie(), avant=self.fichier_repere.read_bytes())   # et le lancement suivant ne fait rien

    def test_commence_avec_un_vivant_qui_tient_le_verrou_n_est_pas_une_interruption(self):
        avant = self.ecrire_repere("commence")
        self.verrou_vivant()
        resultat, appels = self.planifie()
        self.assertEqual((resultat.returncode, resultat.stdout, appels), (0, "", []))
        self.assertEqual(self.fichier_repere.read_bytes(), avant)

    def test_pas_de_cle_de_reprise_sur_un_passage_ordinaire(self):
        resultat, _ = self.planifie()
        self.assertNotIn(self.CLE_REPRISE, resultat.stdout)

    # 4.6 : verrou
    def test_verrou_tenu_par_un_vivant_planifie_sort_en_silence_et_ne_le_retire_pas(self):
        self.verrou_vivant()
        for option in ("--if-due", "--catch-up"):
            resultat, appels = self.planifie(option=option)
            self.assertEqual((resultat.returncode, resultat.stdout, resultat.stderr, appels, self.notifications), (0, "", "", [], []))
            self.assertFalse(self.fichier_repere.exists())
            self.assertTrue(self.verrou.exists())

    def test_verrou_tenu_lancement_manuel_refuse_code_3(self):
        avant = self.ecrire_repere("termine")
        self.verrou_vivant()
        resultat, appels = self.manuel()
        self.assertEqual(resultat.returncode, 3)
        self.assertIn(self.CLE_EN_COURS, resultat.stdout + resultat.stderr)
        self.assertEqual((appels, self.notifications), ([], []))
        self.assertTrue(self.verrou.exists())
        self.assertEqual(self.fichier_repere.read_bytes(), avant)

    def test_verrou_perime_par_processus_mort_est_repris_et_journalise(self):
        self.verrou_mort()
        resultat, appels = self.planifie()
        self.assertIn(self.CLE_PERIME, resultat.stdout)
        self.verifier_jour_complet(appels)
        self.assertFalse(self.verrou.exists())

    def test_verrou_perime_par_l_age_et_age_invalide_remplace_par_la_valeur_par_defaut(self):
        debut = int(self.instant("2026-10-14", "08:00")) - 7200
        self.verrou_vivant(debut=debut)
        resultat, appels = self.planifie(PMZILLA_WATCH_LOCK_MAX_AGE="3600")
        self.assertIn(self.CLE_PERIME, resultat.stdout)
        self.verifier_jour_complet(appels)
        self.fichier_repere.unlink()
        self.appels.unlink()
        self.verrou_vivant(debut=debut)   # deux heures : sous le seuil par défaut (six heures), le verrou tient
        resultat, appels = self.planifie(PMZILLA_WATCH_LOCK_MAX_AGE="abc")
        self.assertEqual((resultat.returncode, resultat.stdout, appels), (0, "", []))
        self.assertTrue(self.verrou.exists())

    def test_verrou_pris_pendant_le_passage_et_libere_apres_un_echec(self):
        self.espionner_uv("watch_lab.py collect", 'cp "$HOME/.pmzilla-lab/veille.verrou/pid" "$HOME/pid-pendant"')
        resultat, _ = self.planifie(echec="watch_lab.py collect")
        self.assertEqual(resultat.returncode, 1)
        self.assertTrue((self.home / "pid-pendant").read_text().strip().isdigit())
        self.assertFalse(self.verrou.exists())

    def test_verrou_libere_apres_un_lancement_manuel_et_apres_un_report(self):
        self.manuel()
        self.assertFalse(self.verrou.exists())
        self.manuel(echec="watch_lab.py check-db", ECHEC_CODE="4")
        self.assertFalse(self.verrou.exists())

    def test_repere_relu_sous_le_verrou(self):
        # Un autre passage se termine entre la première lecture et la prise du verrou : un faux mkdir écrit le repère
        # « termine » juste avant de créer le dossier du verrou.
        faux = self.home / ".local" / "bin" / "mkdir"
        faux.write_text("""#!/bin/sh
case "$1" in *veille.verrou) cat > "$HOME/.pmzilla-lab/veille-du-jour.json" <<EOF
{"date": "2026-10-14", "declencheur": "calendrier", "debut": "07:10", "fin": "07:40", "etat": "termine", "code": 0, "notifie": false, "essais": 0, "reprises": 0}
EOF
;; esac
exec /bin/mkdir "$@"
""")
        faux.chmod(0o755)
        resultat, appels = self.planifie()
        self.assertEqual((resultat.returncode, resultat.stdout, appels), (0, "", []))
        self.assertEqual(self.lire()["declencheur"], "calendrier")
        self.assertFalse(self.verrou.exists())

    # 4.7 : le repère doit pouvoir être écrit
    def donnees_en_lecture_seule(self):
        self.donnees.mkdir(exist_ok=True)
        self.donnees.chmod(0o500)
        self.addCleanup(self.donnees.chmod, 0o700)   # nettoyage avant la suppression du faux HOME

    def test_dossier_de_donnees_en_lecture_seule_exit_4_une_seule_alerte_par_jour(self):
        self.donnees_en_lecture_seule()
        resultat, appels = self.planifie()
        self.assertEqual(resultat.returncode, 4)
        self.assertEqual(appels, [])
        self.assertRegex(resultat.stdout.splitlines()[0], self.EN_TETE)
        self.assertIn(self.CLE_ECRITURE, resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn(self.CLE_ECRITURE, self.notifications[0])
        self.assertEqual(self.alerte.read_text().strip(), "2026-10-14")
        self.assertFalse(self.verrou.exists())
        self.appels.unlink()
        resultat, appels = self.planifie(heure="09:00", option="--catch-up")
        self.assertEqual((resultat.returncode, resultat.stdout, appels, self.notifications), (4, "", [], []))

    def test_le_lendemain_l_alerte_est_de_nouveau_notifiee(self):
        self.donnees_en_lecture_seule()
        self.planifie()
        self.appels.unlink()
        self.planifie(jour="2026-10-15")
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.alerte.read_text().strip(), "2026-10-15")

    def test_marqueur_d_alerte_a_la_date_de_paris(self):
        self.donnees_en_lecture_seule()
        # 08:00 le 15 à Paris = 23:00 le 14 à Los Angeles
        self.planifie(heure="08:00", jour="2026-10-15", TZ="America/Los_Angeles")
        self.assertEqual(self.alerte.read_text().strip(), "2026-10-15")

    def test_marqueur_non_inscriptible_notifie_quand_meme_a_chaque_lancement(self):
        self.donnees_en_lecture_seule()
        self.alerte.mkdir(parents=True)   # un dossier à la place du fichier : écriture impossible
        for _ in range(2):
            self.appels.unlink(missing_ok=True)
            resultat, _ = self.planifie()
            self.assertEqual(resultat.returncode, 4)
            self.assertEqual(len(self.notifications), 1)

    def test_lancement_manuel_dossier_en_lecture_seule_affiche_sans_notifier_ni_marqueur(self):
        self.donnees_en_lecture_seule()
        resultat, appels = self.manuel()
        self.assertEqual(resultat.returncode, 4)
        self.assertIn(self.CLE_ECRITURE, resultat.stdout + resultat.stderr)
        self.assertEqual((appels, self.notifications), ([], []))
        self.assertFalse(self.alerte.exists())
        self.assertFalse(self.verrou.exists())

    def test_rien_a_faire_et_dossier_en_lecture_seule_reste_silencieux(self):
        self.donnees_en_lecture_seule()
        resultat, appels = self.planifie(heure="06:00")
        self.assertEqual((resultat.returncode, resultat.stdout, appels, self.notifications), (0, "", [], []))
        self.assertFalse(self.alerte.exists())

    # 4.9 : report
    def test_base_qui_ne_repond_pas_premier_report_une_notification_et_repere_reporte(self):
        resultat, appels = self.planifie(echec="watch_lab.py check-db", ECHEC_CODE="4")
        self.assertEqual(resultat.returncode, 1)
        self.assertRegex(resultat.stdout, r"Base de données injoignable à \d\d:\d\d")
        self.assertIn(self.CLE_REPORT, resultat.stdout)
        self.assertLess(resultat.stdout.index("Base de données injoignable"), resultat.stdout.index(self.CLE_REPORT))
        self.assertIn("=== Veille terminée avec 1 étape(s) en échec : base de données ===", resultat.stdout)
        self.assertEqual(appels, ["watch_lab.py check-network", "watch_lab.py check-db", "composants.py check", "mutation_masking.py run", "dashboard.py"])
        self.assertEqual(len(self.notifications), 1)
        repere = self.lire()
        self.assertEqual((repere["etat"], repere["code"], repere["notifie"], repere["essais"]), ("reporte", 1, True, 1))
        self.assertFalse(self.verrou.exists())

    def test_deuxieme_report_du_jour_sans_notification_puis_passage_qui_aboutit(self):
        self.planifie(echec="watch_lab.py check-db", ECHEC_CODE="4")
        self.appels.unlink()
        resultat, _ = self.planifie(heure="09:00", option="--catch-up", echec="watch_lab.py check-db", ECHEC_CODE="4")
        self.assertEqual((resultat.returncode, self.notifications), (1, []))
        self.assertEqual((self.lire()["essais"], self.lire()["etat"]), (2, "reporte"))
        self.assertIn("=== Veille terminée avec 1 étape(s) en échec : base de données ===", resultat.stdout)
        self.appels.unlink()
        resultat, appels = self.planifie(heure="10:00", option="--catch-up")
        self.assertEqual(resultat.returncode, 0)
        self.verifier_jour_complet(appels)
        self.assertEqual(self.lire()["etat"], "termine")

    def test_report_en_manuel_declencheur_manuel_puis_un_planifie_reessaie(self):
        resultat, appels = self.manuel(echec="watch_lab.py check-db", ECHEC_CODE="4")
        self.assertEqual(resultat.returncode, 1)
        repere = self.lire()
        self.assertEqual((repere["etat"], repere["declencheur"], repere["notifie"]), ("reporte", "manuel", True))
        self.assertEqual(len(self.notifications), 1)
        self.appels.unlink()
        _, appels = self.planifie(heure="09:00")
        self.verifier_jour_complet(appels)
        self.assertEqual(self.lire()["etat"], "termine")

    def test_le_lendemain_le_report_notifie_de_nouveau(self):
        self.planifie(echec="watch_lab.py check-db", ECHEC_CODE="4")
        self.appels.unlink()
        self.planifie(jour="2026-10-15", echec="watch_lab.py check-db", ECHEC_CODE="4")
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.lire()["essais"], 1)

    def test_tables_absentes_echec_pas_un_report(self):
        resultat, _ = self.planifie(echec="watch_lab.py check-db", ECHEC_CODE="5")
        self.assertEqual(resultat.returncode, 1)
        self.assertNotIn(self.CLE_REPORT, resultat.stdout)
        repere = self.lire()
        self.assertEqual((repere["etat"], repere["essais"], repere["code"]), ("echoue", 0, 1))
        self.assertEqual(len(self.notifications), 1)
        self.appels.unlink()
        self.verifier_rien(*self.planifie(heure="09:00"), avant=self.fichier_repere.read_bytes())

    def test_autre_code_de_la_base_garde_la_ligne_injoignable_et_compte_comme_echec(self):
        for code in ("1", "2", "7"):
            with self.subTest(code=code):
                self.fichier_repere.unlink(missing_ok=True)
                self.appels.unlink(missing_ok=True)
                resultat, _ = self.planifie(echec="watch_lab.py check-db", ECHEC_CODE=code)
                self.assertRegex(resultat.stdout, r"Base de données injoignable à \d\d:\d\d")
                self.assertNotIn(self.CLE_REPORT, resultat.stdout)
                self.assertEqual(self.lire()["etat"], "echoue")
                self.appels.unlink()
                self.verifier_rien(*self.planifie(heure="09:00"), avant=self.fichier_repere.read_bytes())

    def test_reseau_absent_reporte_sans_collecte_et_avec_tableau_de_bord(self):
        resultat, appels = self.planifie(echec="watch_lab.py check-network", ECHEC_CODE="6")
        self.assertEqual(appels, ["watch_lab.py check-network", "composants.py check", "mutation_masking.py run", "dashboard.py"])
        self.assertRegex(resultat.stdout, r"Réseau absent à \d\d:\d\d : collecte, pré-tri, listes à lire et indexation du jour reportés\.")
        self.assertIn(self.CLE_REPORT, resultat.stdout)
        self.assertIn("=== Veille terminée avec 1 étape(s) en échec : réseau ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("réseau", self.notifications[0])
        repere = self.lire()
        self.assertEqual((repere["etat"], repere["essais"], repere["notifie"]), ("reporte", 1, True))
        self.appels.unlink()
        resultat, _ = self.planifie(heure="09:00", echec="watch_lab.py check-network", ECHEC_CODE="6")
        self.assertEqual((resultat.returncode, self.notifications), (1, []))   # deuxième report du jour : sans notification

    def test_tout_code_non_nul_du_reseau_reporte(self):
        _, appels = self.planifie(echec="watch_lab.py check-network", ECHEC_CODE="2")
        self.assertNotIn("watch_lab.py check-db", appels)
        self.assertEqual(self.lire()["etat"], "reporte")

    def test_attente_reseau_par_defaut_reglee_ou_invalide(self):
        cas = {None: "120", "30": "30", "abc": "120", "1.5": "120", "-1": "120"}
        for valeur, attendue in cas.items():
            with self.subTest(valeur=valeur):
                self.complets.unlink(missing_ok=True)
                self.fichier_repere.unlink(missing_ok=True)
                self.planifie(**({} if valeur is None else {"PMZILLA_WATCH_NET_WAIT": valeur}))
                ligne = next(l for l in self.complets.read_text().splitlines() if "check-network" in l)
                self.assertRegex(ligne, rf"watch_lab\.py check-network --wait {attendue} ")

    def test_reseau_controle_entre_le_cache_uv_et_la_base_jamais_en_manuel(self):
        self.versions(uv="uv 0.12.0")
        _, appels = self.planifie()
        self.assertEqual(appels[:4], ["controle_cache.py", "controle_cache.py hors-ligne", "watch_lab.py check-network", "watch_lab.py check-db"])
        self.appels.unlink()
        _, appels = self.manuel(echec="watch_lab.py check-network", ECHEC_CODE="6")
        self.assertNotIn("watch_lab.py check-network", appels)
        self.assertIn("watch_lab.py collect", appels)

    # 4.10 : ligne de rattrapage
    def test_ligne_de_rattrapage_juste_apres_l_en_tete_inchange(self):
        resultat, _ = self.planifie(option="--catch-up")
        lignes = resultat.stdout.splitlines()
        self.assertRegex(lignes[0], self.EN_TETE)
        self.assertEqual(lignes[1], self.CLE_RATTRAPAGE)
        self.assertEqual([n for n in self.notifications if not n.startswith("osascript résumé du matin")], [])   # aucune notification pour le rattrapage lui-même (le résumé du matin, R-50, est l'unique notification du passage)

    def test_pas_de_ligne_de_rattrapage_sur_un_passage_du_calendrier_ou_manuel(self):
        for lancer in (self.planifie, self.manuel):
            resultat, _ = lancer()
            self.assertNotIn(self.CLE_RATTRAPAGE, resultat.stdout)
            self.assertRegex(resultat.stdout.splitlines()[0], self.EN_TETE)

    def test_rattrapage_sans_rien_a_faire_n_ecrit_aucune_ligne(self):
        self.ecrire_repere("termine")
        resultat, appels = self.planifie(option="--catch-up")
        self.assertEqual((resultat.stdout, resultat.stderr, appels), ("", "", []))

    def test_rattrapage_en_echec_notifie_comme_n_importe_quel_passage(self):
        self.planifie(option="--catch-up", echec="watch_lab.py collect")
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("collecte", self.notifications[0])

    # Lancement manuel
    def test_lancement_manuel_apres_un_passage_termine_le_force(self):
        self.ecrire_repere("termine")
        resultat, appels = self.manuel()
        self.verifier_jour_complet(appels)
        self.assertEqual(self.lire()["declencheur"], "manuel")
        self.assertNotIn(self.CLE_RATTRAPAGE, resultat.stdout)


class WatchSh(Base):
    def test_chemin_nominal_enchaine_toutes_les_etapes_dans_l_ordre(self):
        resultat, appels = self.lancer()
        self.assertEqual(appels, [
            "watch_lab.py check-db", "watch_lab.py collect", "watch_triage.py score", "watch_triage.py apply", "watch_triage.py shares",
            "watch_triage.py digest", "pmzilla_lab_library.py index", "pmzilla_lab_library.py probe", "composants.py check", "mutation_masking.py run",
            "dashboard.py"])
        self.assertEqual(resultat.returncode, 0)
        self.assertNotIn("erreur", resultat.stdout.lower().replace("sans erreur", ""))
        self.assertTrue(resultat.stdout.rstrip().endswith("=== Veille terminée sans erreur ==="))
        self.assertEqual(self.notifications, [])   # aucune notification quand tout va bien

    def test_le_texte_du_script_ne_garde_aucune_trace_de_sqlite(self):
        texte = SCRIPT.read_text(encoding="utf-8")
        for trace in (".sqlite", "sqlite3", "parite-sqlite", "knowledge_import.py"):
            self.assertNotIn(trace, texte)

    def test_passage_complet_sans_fichier_sqlite_dans_le_dossier_de_donnees(self):
        resultat, appels = self.lancer()
        self.assertEqual(appels[-5:], ["pmzilla_lab_library.py index", "pmzilla_lab_library.py probe", "composants.py check", "mutation_masking.py run",
                                       "dashboard.py"])
        self.assertEqual(resultat.returncode, 0)
        self.assertTrue(resultat.stdout.rstrip().endswith("=== Veille terminée sans erreur ==="))
        self.assertEqual(self.notifications, [])
        self.assertEqual(list((self.home / ".pmzilla-lab").glob("*.sqlite*")), [])

    def test_un_ancien_marqueur_de_parite_ne_change_rien(self):
        (self.home / ".pmzilla-lab" / "parite-sqlite").write_text("2026-10-01\n")
        resultat, appels = self.lancer()
        self.assertEqual(appels, [
            "watch_lab.py check-db", "watch_lab.py collect", "watch_triage.py score", "watch_triage.py apply", "watch_triage.py shares",
            "watch_triage.py digest", "pmzilla_lab_library.py index", "pmzilla_lab_library.py probe", "composants.py check", "mutation_masking.py run",
            "dashboard.py"])
        self.assertFalse(any(a.startswith("ancien") or "knowledge_import" in a for a in appels))
        self.assertEqual(resultat.returncode, 0)
        self.assertEqual(self.notifications, [])

    # Base injoignable (code 2 de l'indexeur)
    def test_base_injoignable_nommee_dans_le_resume_et_la_notification(self):
        repere = self.repere(contenu="1000")
        resultat, appels = self.lancer(echec="pmzilla_lab_library.py index", ECHEC_CODE="2")
        self.assertIn("Indexation en erreur : base PostgreSQL injoignable, la bibliothèque n'est pas à jour "
                      "(bash tools/db_up.sh)", resultat.stdout)
        self.assertIn("=== Veille terminée avec 1 étape(s) en échec : indexation (base injoignable) ===", resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("indexation (base injoignable)", self.notifications[0])
        self.assertEqual(repere.read_text(), "1000")              # repère inchangé
        self.assertIn("watch_triage.py digest", appels)          # liste à lire construite avant
        self.assertIn("dashboard.py", appels)
        self.assertNotIn("pmzilla_lab_library.py probe", appels)
        self.assertEqual(resultat.returncode, 1)

    def test_autre_code_de_l_indexeur_garde_l_etiquette_indexation(self):
        resultat, _ = self.lancer(echec="pmzilla_lab_library.py index", ECHEC_CODE="5")
        self.assertIn("Indexation en erreur : la bibliothèque n'est pas à jour", resultat.stdout)
        self.assertNotIn("injoignable", resultat.stdout)
        self.assertIn("en échec : indexation ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)

    # Sonde de l'index BM25
    def test_sonde_reussie_ne_notifie_rien(self):
        resultat, appels = self.lancer()
        self.assertIn("pmzilla_lab_library.py probe", appels)
        self.assertEqual(self.notifications, [])
        self.assertNotIn("BM25", resultat.stdout)
        complet = next(l for l in self.complets.read_text().splitlines() if "pmzilla_lab_library.py probe" in l)
        self.assertIn(f"{self.home}/PMZilla-Lab/workspace/tools/pmzilla_lab_library.py probe", complet)

    def test_sonde_index_bm25_illisible_journalise_et_notifie_sans_bloquer(self):
        resultat, appels = self.lancer(echec="pmzilla_lab_library.py probe", ECHEC_CODE="3")
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("dashboard.py", appels)
        self.assertIn("Index BM25 illisible", resultat.stdout)
        self.assertIn("Damaged BM25 index", resultat.stdout)
        self.assertTrue(resultat.stdout.rstrip().endswith("=== Veille terminée sans erreur ==="))
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("BM25", self.notifications[0])
        self.assertIn("Damaged BM25 index", self.notifications[0])

    def test_sonde_en_echec_autre_code_journalise_et_notifie_sans_bloquer(self):
        resultat, appels = self.lancer(echec="pmzilla_lab_library.py probe", ECHEC_CODE="2")
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("dashboard.py", appels)
        self.assertIn("Sonde de l'index BM25 en échec (code 2) : voir ci-dessus", resultat.stdout)
        self.assertNotIn("Index BM25 illisible", resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("Sonde de l'index BM25 en échec. Voir le journal de la veille.", self.notifications[0])

    def test_sonde_pas_lancee_si_l_indexation_echoue_ou_sans_ollama(self):
        _, appels = self.lancer(echec="pmzilla_lab_library.py index")
        self.assertNotIn("pmzilla_lab_library.py probe", appels)
        self.appels.unlink()
        _, appels = self.lancer(curl=7)
        self.assertNotIn("pmzilla_lab_library.py probe", appels)

    def appels_curl(self):
        return [a for a in self.appels.read_text().splitlines() if a.startswith("curl")]

    def test_ollama_par_defaut_comme_l_indexeur(self):
        # Décision du 2026-10-21, point 8 (A12) : même adresse par défaut que tools/pmzilla_lab_library.py (OLLAMA_URL).
        self.lancer()
        self.assertTrue(any("http://localhost:11434/api/tags" in a for a in self.appels_curl()))

    def test_ollama_lu_dans_pmzilla_lab_ollama(self):
        # PMZILLA_LAB_OLLAMA, la variable de l'indexeur, barre oblique finale retirée comme lui ; jamais l'adresse codée en dur.
        self.lancer(PMZILLA_LAB_OLLAMA="http://ollama-ailleurs:9999/")
        appels = self.appels_curl()
        self.assertTrue(any("http://ollama-ailleurs:9999/api/tags" in a for a in appels))
        self.assertFalse(any("11434" in a for a in appels))

    def test_journal_horodate_et_les_deux_dossiers_indexes(self):
        resultat, _ = self.lancer()
        self.assertRegex(resultat.stdout.splitlines()[0], r"^=== \d{4}-\d{2}-\d{2} \d{2}:\d{2} ===$")
        index = next(l for l in self.complets.read_text().splitlines() if "pmzilla_lab_library.py index" in l)
        self.assertIn(f"{self.home}/PMZilla-Lab/workspace/Bibliotheque-Lab", index)   # toujours les deux dossiers
        self.assertIn(f"{self.home}/PMZilla-Lab/workspace/Watch-Lab", index)           # aucun dossier : le nouveau nom
        for appel in self.complets.read_text().splitlines()[:6]:
            self.assertIn(f"{self.home}/PMZilla-Lab/", appel)   # les scripts sont appelés par leur chemin lié

    def test_dossier_de_la_veille_a_l_ancien_nom_refuse_sans_rien_lancer(self):
        ws = self.home / "PMZilla-Lab" / "workspace"
        (ws / "Veille-Lab").mkdir()
        resultat, appels = self.lancer()
        self.assertNotEqual(resultat.returncode, 0)
        self.assertEqual(appels, [])                                  # aucune étape n'a tourné
        self.assertIn("Veille-Lab", resultat.stderr)
        self.assertIn("Watch-Lab", resultat.stderr)
        self.assertIn("migrate_watch.py", resultat.stderr)
        (ws / "Watch-Lab").mkdir()                                   # les deux : le nouveau est pris, sans message
        resultat, _ = self.lancer()
        index = next(l for l in self.complets.read_text().splitlines() if "pmzilla_lab_library.py index" in l)
        self.assertIn(f"{ws}/Watch-Lab ", index)
        self.assertNotIn("Veille-Lab", index)
        self.assertNotIn("Veille-Lab", resultat.stderr)

    def test_ollama_absent_liste_simple_sans_pre_tri_ni_index(self):
        self.repere(jours=1)
        resultat, appels = self.lancer(curl=7)
        self.assertEqual(appels, ["watch_lab.py check-db", "watch_lab.py collect", "watch_lab.py digest", "composants.py check", "mutation_masking.py run",
                                  "dashboard.py"])
        self.assertIn("Ollama ne répond pas : pré-tri et indexation reportés au prochain passage", resultat.stdout)
        self.assertEqual(resultat.returncode, 0)   # report prévu, pas un échec
        self.assertEqual(self.notifications, [])

    def test_indexation_reussie_ecrit_le_repere_et_echouee_le_laisse(self):
        self.lancer()
        avant = int(time.time())
        repere = self.home / ".pmzilla-lab" / "derniere-indexation"
        self.assertLessEqual(avant - int(repere.read_text()), 60)
        repere.write_text("1000")
        self.lancer(echec="pmzilla_lab_library.py index")
        self.assertEqual(repere.read_text().strip(), "1000")       # un échec ne rafraîchit pas le repère
        self.lancer(curl=7)
        self.assertEqual(repere.read_text().strip(), "1000")       # Ollama absent : pas d'indexation, pas de repère

    def test_ollama_absent_index_recent_pas_de_notification(self):
        self.repere(jours=2.5)
        resultat, _ = self.lancer(curl=7)
        self.assertEqual(self.notifications, [])
        self.assertNotIn("obsolète", resultat.stdout)
        self.assertEqual(resultat.returncode, 0)

    def test_ollama_absent_index_trop_ancien_notifie_sans_code_de_sortie(self):
        self.repere(jours=4)
        resultat, appels = self.lancer(curl=7)
        self.assertEqual(resultat.returncode, 0)                    # jamais un échec
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("display notification", self.notifications[0])
        self.assertIn("depuis 4 jours", self.notifications[0])
        self.assertIn('with title "PMZilla watch"', self.notifications[0])
        self.assertIn("Index obsolète : dernière indexation réussie il y a 4 jour(s) (seuil : 3)", resultat.stdout)
        self.assertNotIn("pmzilla_lab_library.py index", appels)

    def test_seuil_reglable(self):
        self.repere(jours=2)
        resultat, _ = self.lancer(curl=7, PMZILLA_INDEXATION_MAX_JOURS="1")
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("(seuil : 1)", resultat.stdout)
        self.appels.unlink()
        self.repere(jours=10)
        self.lancer(curl=7, PMZILLA_INDEXATION_MAX_JOURS="30")
        self.assertEqual(self.notifications, [])                    # seuil large : pas de notification
        self.appels.unlink()
        self.lancer(curl=7, PMZILLA_INDEXATION_MAX_JOURS="beaucoup")  # valeur invalide : retour à 3 jours
        self.assertEqual(len(self.notifications), 1)

    def test_seuil_exact_pas_de_notification(self):
        self.repere(jours=2.99)
        self.lancer(curl=7)
        self.assertEqual(self.notifications, [])

    def test_ollama_absent_sans_repere_ni_index_connu(self):
        resultat, _ = self.lancer(curl=7)
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("Aucune indexation réussie connue", resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("aucune indexation réussie connue", self.notifications[0])

    def test_repere_illisible_traite_comme_inconnu(self):
        self.repere(contenu="pas une date")
        self.lancer(curl=7)
        self.assertEqual(len(self.notifications), 1)

    def test_sans_repere_un_fichier_sqlite_errant_est_ignore(self):
        index = self.home / ".pmzilla-lab" / "library.sqlite"
        index.write_text("")                                         # récent : sa date n'est jamais lue
        resultat, _ = self.lancer(curl=7)
        self.assertIn("Aucune indexation réussie connue", resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("aucune indexation réussie connue", self.notifications[0])

    def test_notification_ollama_impossible_ne_change_rien(self):
        self.repere(jours=5)
        resultat, _ = self.lancer(curl=7, osascript=1)
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("Notification macOS impossible", resultat.stdout)

    def test_collecte_en_erreur_est_journalisee_et_la_suite_continue(self):
        resultat, appels = self.lancer(echec="watch_lab.py collect")
        self.assertIn("Collecte en erreur", resultat.stdout)
        self.assertIn("_rapport_collecte.txt", resultat.stdout)
        self.assertIn("pmzilla_lab_library.py index", appels)   # l'index se met à jour malgré tout
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("=== Veille terminée avec 1 étape(s) en échec : collecte ===", resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("display notification", self.notifications[0])
        self.assertIn("collecte", self.notifications[0])

    def test_echec_du_pre_tri_bascule_sur_la_liste_non_triee_et_arrete_la_chaine(self):
        for etape in ("score", "apply", "shares", "digest"):
            with self.subTest(etape=etape):
                self.appels.unlink(missing_ok=True)
                self.complets.unlink(missing_ok=True)
                resultat, appels = self.lancer(echec=f"watch_triage.py {etape}")
                ordre = ["score", "apply", "shares", "digest"]
                attendu_tri = [f"watch_triage.py {e}" for e in ordre[:ordre.index(etape) + 1]]
                self.assertEqual([a for a in appels if a.startswith("watch_triage.py")], attendu_tri)  # arrêt au premier échec
                self.assertIn("Pré-tri en erreur : liste à lire non triée", resultat.stdout)
                self.assertIn("watch_lab.py digest", appels)
                self.assertIn("pmzilla_lab_library.py index", appels)
                self.assertEqual(resultat.returncode, 1)
                self.assertIn("en échec : pré-tri ===", resultat.stdout)
                self.assertEqual(len(self.notifications), 1)
                self.assertIn("pré-tri", self.notifications[0])

    def test_echec_du_dashboard_ne_fait_pas_echouer_la_veille(self):
        resultat, appels = self.lancer(echec="dashboard.py")
        self.assertIn("Tableau de bord non généré", resultat.stdout)
        self.assertEqual(resultat.returncode, 0)   # choix documenté dans le script : jamais bloquant
        self.assertEqual(self.notifications, [])

    def test_echec_de_l_indexation_est_dit_et_notifie(self):
        resultat, appels = self.lancer(echec="pmzilla_lab_library.py index")
        self.assertIn("pmzilla_lab_library.py index", appels)
        self.assertIn("Indexation en erreur : la bibliothèque n'est pas à jour", resultat.stdout)
        self.assertIn("en échec : indexation ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("indexation", self.notifications[0])

    def test_plusieurs_echecs_nommes_dans_l_ordre(self):
        resultat, _ = self.lancer(echec="watch_lab.py collect,watch_triage.py score,pmzilla_lab_library.py index")
        self.assertIn("=== Veille terminée avec 3 étape(s) en échec : collecte, pré-tri, indexation ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)
        self.assertEqual(len(self.notifications), 1)   # une seule notification pour le passage
        self.assertIn("collecte, pré-tri, indexation", self.notifications[0])

    def test_liste_a_lire_en_erreur(self):
        resultat, _ = self.lancer(echec="watch_lab.py digest", curl=7)
        self.assertIn("Liste à lire en erreur", resultat.stdout)
        self.assertIn("en échec : liste à lire ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)
        resultat, _ = self.lancer(echec="watch_triage.py digest,watch_lab.py digest")
        self.assertIn("en échec : pré-tri, liste à lire ===", resultat.stdout)

    def test_notification_impossible_ne_change_pas_le_code_de_sortie(self):
        resultat, _ = self.lancer(echec="pmzilla_lab_library.py index", osascript=1)
        self.assertIn("Notification macOS impossible", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)

    def test_aucune_commande_reelle_et_rien_hors_du_faux_home(self):
        resultat, _ = self.lancer()
        chemins = re.findall(r"(/\S*PMZilla-Lab\S*)", resultat.stdout + self.complets.read_text())
        self.assertTrue(chemins)
        self.assertTrue(all(c.startswith(str(self.home)) for c in chemins))
        self.assertTrue(all(not l.startswith("launchctl") for l in self.appels.read_text().splitlines()))
        self.assertEqual(self.notifications, [])   # la vraie notification n'est jamais déclenchée par les tests


class CacheUv(Base):
    """Contrôle du cache de uv (R-13) : seulement quand uv ou son Python a changé, jamais bloquant."""
    def appels_reveil(self, appels):
        return [a for a in appels if a.startswith("controle_cache.py")]

    def test_versions_inchangees_aucun_controle(self):
        resultat, appels = self.lancer()
        self.assertEqual(self.appels_reveil(appels), [])
        self.assertNotIn("cache", resultat.stdout.lower())

    def test_uv_change_relance_le_reveil_avec_reseau_puis_hors_ligne_et_enregistre(self):
        resultat, appels = self.lancer(FAUX_UV_VERSION="0.14.0")
        self.assertEqual(self.appels_reveil(appels), ["controle_cache.py", "controle_cache.py hors-ligne"])
        self.assertIn("Cache de uv rempli et vérifié hors ligne", resultat.stdout)
        self.assertEqual((self.home / ".pmzilla-lab" / "uv-version").read_text().strip(), "uv 0.14.0")
        self.assertEqual(self.notifications, [])
        self.assertEqual(resultat.returncode, 0)

    def test_python_change_relance_le_reveil(self):
        resultat, appels = self.lancer(FAUX_PYTHON_VERSION="3.15.0")
        self.assertEqual(self.appels_reveil(appels), ["controle_cache.py", "controle_cache.py hors-ligne"])
        self.assertEqual((self.home / ".pmzilla-lab" / "uv-python-version").read_text().strip(), "3.15.0")

    def test_versions_jamais_enregistrees_declenchent_le_controle(self):
        (self.home / ".pmzilla-lab" / "uv-version").unlink()
        _, appels = self.lancer()
        self.assertEqual(self.appels_reveil(appels), ["controle_cache.py", "controle_cache.py hors-ligne"])

    def test_deuxieme_passage_ne_controle_plus(self):
        self.lancer(FAUX_UV_VERSION="0.14.0")
        self.appels.unlink()
        _, appels = self.lancer(FAUX_UV_VERSION="0.14.0")
        self.assertEqual(self.appels_reveil(appels), [])

    def test_le_controle_du_cache_precede_la_collecte(self):
        _, appels = self.lancer(FAUX_UV_VERSION="0.14.0")
        self.assertEqual(appels[:4], ["controle_cache.py", "controle_cache.py hors-ligne", "watch_lab.py check-db", "watch_lab.py collect"])

    def test_versions_inchangees_la_collecte_est_le_premier_appel(self):
        _, appels = self.lancer()
        self.assertEqual(appels[0], "watch_lab.py check-db")

    def test_le_reveil_se_lance_depuis_deux_dossiers_temporaires_distincts_nettoyes(self):
        resultat, _ = self.lancer(FAUX_UV_VERSION="0.14.0")
        lignes = [l for l in self.complets.read_text().splitlines() if "controle_cache.py" in l]
        self.assertEqual(len(lignes), 2)
        self.assertTrue(all(l.startswith("run --python 3.14.8 controle_cache.py") for l in lignes))   # chemin relatif : lancé depuis le dossier copie

    def test_les_deux_lancements_fixent_le_python_lu_dans_le_workspace(self):
        self.lancer(FAUX_UV_VERSION="0.14.0", FAUX_PYTHON_VERSION="3.15.0")
        lignes = [l for l in self.complets.read_text().splitlines() if "controle_cache.py" in l]
        self.assertEqual(len(lignes), 2)
        self.assertTrue(all(l.startswith("run --python 3.15.0 controle_cache.py") for l in lignes))

    def test_echec_hors_ligne_notifie_n_enregistre_pas_et_ne_bloque_pas(self):
        resultat, appels = self.lancer(echec="controle_cache.py hors-ligne", FAUX_UV_VERSION="0.14.0")
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("After an update of uv", self.notifications[0])
        self.assertIn("After an update of uv", resultat.stdout)
        self.assertEqual((self.home / ".pmzilla-lab" / "uv-version").read_text().strip(), "uv 0.13.0")
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("watch_lab.py collect", appels)
        self.assertIn("dashboard.py", appels)

    def test_echec_avec_reseau_n_essaie_pas_le_hors_ligne(self):
        resultat, appels = self.lancer(echec="controle_cache.py", FAUX_UV_VERSION="0.14.0")
        self.assertEqual(self.appels_reveil(appels), ["controle_cache.py"])   # l'appel échoué est noté, pas de hors-ligne ensuite
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(resultat.returncode, 0)

    def test_script_de_reveil_absent_notifie_sans_bloquer(self):
        (self.home / "PMZilla-Lab" / "workspace" / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts" / "wake.py").unlink()
        resultat, appels = self.lancer(FAUX_UV_VERSION="0.14.0")
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("watch_lab.py collect", appels)

    def test_version_illisible_journalise_sans_notifier_ni_bloquer(self):
        resultat, appels = self.lancer(FAUX_PYTHON_ABSENT="1")
        self.assertIn("Contrôle du cache de uv impossible", resultat.stdout)
        self.assertEqual(self.notifications, [])
        self.assertEqual(self.appels_reveil(appels), [])
        self.assertEqual(resultat.returncode, 0)

    def test_notification_impossible_ne_change_pas_le_code_de_sortie_du_controle(self):
        resultat, _ = self.lancer(echec="controle_cache.py hors-ligne", osascript=1, FAUX_UV_VERSION="0.14.0")
        self.assertEqual(resultat.returncode, 0)

    @staticmethod
    def entete(texte: str) -> list[str]:
        lignes = texte.splitlines()
        debut = lignes.index("# /// script")
        return lignes[debut:lignes.index("# ///", debut + 1) + 1]

    def test_script_jetable_porte_l_entete_du_vrai_wake_py_et_rien_d_autre_que_l_import(self):
        vrai = SCRIPT.parents[1] / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts" / "wake.py"
        (self.home / "PMZilla-Lab" / "workspace" / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts" / "wake.py"
         ).write_text(vrai.read_text())
        self.lancer(FAUX_UV_VERSION="0.14.0")
        for nom in ("jetable-.py", "jetable-hors-ligne.py"):
            jetable = (self.home / nom).read_text()
            entete = self.entete(jetable)
            self.assertEqual(entete, self.entete(vrai.read_text()))
            reste = [l for l in jetable.splitlines()[len(entete):] if l.strip()]
            self.assertEqual(reste, ["import yaml"])

    def test_wake_py_absent_ou_sans_entete_est_un_echec_notifie(self):
        (self.home / "PMZilla-Lab" / "workspace" / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts" / "wake.py"
         ).write_text("print('pas d en-tete')\n")
        resultat, appels = self.lancer(FAUX_UV_VERSION="0.14.0")
        self.assertEqual(self.appels_reveil(appels), [])
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(resultat.returncode, 0)

    def test_le_controle_lit_le_python_et_l_entete_du_dossier_de_code_pas_ceux_du_contenu(self):
        run = self.home / "PMZilla-Lab" / "run"
        (run / "tools").mkdir(parents=True)
        shutil.copy(SCRIPT, run / "tools" / "watch.sh")
        shutil.copy(SCRIPT.parent / "watch_paths.py", run / "tools" / "watch_paths.py")
        shutil.copy(SCRIPT.parent / "lab_paths.sh", run / "tools" / "lab_paths.sh")
        shutil.copy(SCRIPT.parent / "lab_paths.py", run / "tools" / "lab_paths.py")
        reveil = run / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts"
        reveil.mkdir(parents=True)
        (reveil / "wake.py").write_text("# /// script\n# dependencies = [\"entete-du-dossier-de-code\"]\n# ///\n")
        (run / ".python-version").write_text("3.99.1\n")
        contenu = self.home / "PMZilla-Lab" / "workspace"
        (contenu / ".python-version").write_text("3.11.0\n")
        lien = self.home / "PMZilla-Lab" / "watch.sh"
        lien.symlink_to(run / "tools" / "watch.sh")
        resultat, appels = self.lancer(script=lien, FAUX_UV_VERSION="0.14.0")
        self.assertEqual(self.appels_reveil(appels), ["controle_cache.py", "controle_cache.py hors-ligne"])
        self.assertEqual((self.home / ".pmzilla-lab" / "uv-python-version").read_text().strip(), "3.99.1")
        lignes = [l for l in self.complets.read_text().splitlines() if "controle_cache.py" in l]
        self.assertTrue(all(l.startswith("run --python 3.99.1 controle_cache.py") for l in lignes))
        for nom in ("jetable-.py", "jetable-hors-ligne.py"):
            jetable = (self.home / nom).read_text()
            self.assertIn("entete-du-dossier-de-code", jetable)
            self.assertNotIn("pyyaml", jetable)

    def test_python_version_a_la_racine_du_projet(self):
        racine = SCRIPT.parents[1]
        self.assertEqual((racine / ".python-version").read_text().strip(), "3.14")


class DossiersDeCodeEtDeContenu(Base):
    """Run-worktree D2 et D5 : dossier de code (là où le lien se résout) et dossier de contenu (PMZILLA_LAB_WORKSPACE).
    Le dossier d'exécution est un faux dossier ~/PMZilla-Lab/run, le dépôt de développement factice ~/PMZilla-Lab/workspace."""

    CLE_REFUS = "=== Veille arrêtée : le dossier de contenu est le dossier d'exécution ==="
    NOTIF_REFUS = "Veille arrêtée : le dossier de contenu est le dossier d'exécution. Voir installation.md, « Run worktree »."
    OUTILS = ("watch_lab.py check-db", "watch_lab.py collect", "composants.py check", "dashboard.py", "pmzilla_lab_library.py index")

    def setUp(self):
        super().setUp()
        self.lab = self.home / "PMZilla-Lab"
        self.run = self.lab / "run"
        (self.run / "tools").mkdir(parents=True)
        shutil.copy(SCRIPT, self.run / "tools" / "watch.sh")
        shutil.copy(SCRIPT.parent / "watch_paths.py", self.run / "tools" / "watch_paths.py")
        shutil.copy(SCRIPT.parent / "lab_paths.sh", self.run / "tools" / "lab_paths.sh")
        shutil.copy(SCRIPT.parent / "lab_paths.py", self.run / "tools" / "lab_paths.py")
        reveil = self.run / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts"
        reveil.mkdir(parents=True)
        (reveil / "wake.py").write_text("# /// script\n# dependencies = [\"dependance-du-dossier-de-code\"]\n# ///\nraise SystemExit('jamais')\n")
        (self.run / ".python-version").write_text("3.99.1\n")
        self.lien = self.lab / "watch.sh"
        self.lien.symlink_to(self.run / "tools" / "watch.sh")
        self.donnees = self.home / ".pmzilla-lab"
        self.contenu = self.lab / "workspace"

    def lancer_lien(self, **env):
        return self.lancer(script=self.lien, **env)

    def fichiers(self, racine: Path):
        return sorted(str(f.relative_to(racine)) for f in racine.rglob("*"))

    def test_les_outils_appeles_sont_ceux_du_dossier_d_execution_et_rien_n_y_est_ecrit(self):
        avant = self.fichiers(self.run)
        resultat, appels = self.lancer_lien()
        self.assertEqual(resultat.returncode, 0)
        complets = self.complets.read_text().splitlines()
        for outil in self.OUTILS:
            ligne = next(l for l in complets if outil.split()[0] in l and (outil.split()[1] if len(outil.split()) > 1 else "") in l)
            self.assertIn(f"{self.run}/tools/{outil.split()[0]}", ligne)
        self.assertFalse(any(f"{self.contenu}/tools/" in l for l in complets))
        self.assertEqual(self.fichiers(self.run), avant)

    def test_les_dossiers_indexes_sont_ceux_du_contenu(self):
        self.lancer_lien()
        index = next(l for l in self.complets.read_text().splitlines() if "pmzilla_lab_library.py index" in l)
        self.assertIn(f"{self.contenu}/Bibliotheque-Lab", index)
        self.assertIn(f"{self.contenu}/Watch-Lab", index)
        self.assertNotIn(str(self.run), index.split("index", 1)[1])

    def test_le_dossier_de_contenu_vient_de_la_variable_et_est_exporte_aux_outils(self):
        autre = self.home / "contenu-ailleurs"
        autre.mkdir()
        resultat, _ = self.lancer_lien(PMZILLA_LAB_WORKSPACE=str(autre))
        self.assertEqual(resultat.returncode, 0)
        index = next(l for l in self.complets.read_text().splitlines() if "pmzilla_lab_library.py index" in l)
        self.assertIn(f"{autre}/Bibliotheque-Lab", index)
        self.assertIn(f"{autre}/Watch-Lab", index)
        espaces = (self.home / "espaces.txt").read_text().splitlines()
        self.assertTrue(espaces)
        self.assertTrue(all(l.endswith(f"WS={autre}") for l in espaces))

    def test_le_resume_du_matin_part_par_le_lien_du_labo_avec_le_dossier_de_contenu_exporte(self):
        # R-50 tâche 1.3 recalée sur R-43 : le résumé est lancé par le lien du dossier du labo (il se résout dans le dossier d'exécution)
        # et reçoit le dossier de contenu (le fichier de l'auteur des cas y vit), jamais le dossier d'exécution.
        (self.lab / "morning_summary.py").symlink_to(self.run / "tools" / "morning_summary.py")
        resultat, _ = self.lancer(script=self.lien, args=["--if-due"], TZ="Europe/Paris",
                                  PMZILLA_WATCH_NOW=str(int(datetime(2026, 10, 14, 8, 0, tzinfo=ZoneInfo("Europe/Paris")).timestamp())))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        appel = self.appels_resume.read_text().splitlines()
        self.assertEqual(len(appel), 1)
        self.assertTrue(appel[0].startswith(f"{self.lab}/morning_summary.py "), appel[0])
        ligne = next(l for l in (self.home / "espaces.txt").read_text().splitlines() if "morning_summary.py" in l)
        self.assertTrue(ligne.endswith(f"WS={self.contenu}"), ligne)

    def test_variable_absente_le_contenu_est_le_depot_de_developpement_et_est_exporte(self):
        self.lancer_lien()
        self.assertTrue(all(l.endswith(f"WS={self.contenu}") for l in (self.home / "espaces.txt").read_text().splitlines()))

    def test_les_deux_lignes_des_dossiers_suivent_l_en_tete(self):
        resultat, _ = self.lancer_lien()
        lignes = resultat.stdout.splitlines()
        self.assertRegex(lignes[0], Rattrapage.EN_TETE)
        self.assertEqual(lignes[1], f"Dossier de code : {self.run}")
        self.assertEqual(lignes[2], f"Dossier de contenu : {self.contenu}")

    def test_lien_suivi_le_dossier_de_code_est_la_cible_pas_le_dossier_du_lien(self):
        resultat, _ = self.lancer_lien()
        self.assertNotIn(f"Dossier de code : {self.lab}\n", resultat.stdout + "\n")

    def test_en_rattrapage_la_ligne_de_rattrapage_reste_la_premiere_apres_l_en_tete(self):
        resultat, _ = self.lancer(script=self.lien, args=["--catch-up"], TZ=Rattrapage.ZONE,
                                  PMZILLA_WATCH_NOW=Rattrapage.instant("2026-10-14", "09:00"))
        lignes = resultat.stdout.splitlines()
        self.assertRegex(lignes[0], Rattrapage.EN_TETE)
        self.assertEqual(lignes[1], Rattrapage.CLE_RATTRAPAGE)
        self.assertEqual(lignes[2], f"Dossier de code : {self.run}")
        self.assertEqual(lignes[3], f"Dossier de contenu : {self.contenu}")

    def test_depot_de_developpement_pour_les_deux_dossiers_est_accepte(self):
        resultat, appels = self.lancer()
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("watch_lab.py collect", appels)
        self.assertIn(f"Dossier de code : {self.contenu}", resultat.stdout)
        self.assertNotIn(self.CLE_REFUS, resultat.stdout)

    # Refus de D2
    def planifie(self, heure="08:00", option="--if-due", **env):
        return self.lancer(script=self.lien, args=[option], TZ=Rattrapage.ZONE,
                           PMZILLA_WATCH_NOW=Rattrapage.instant("2026-10-14", heure), **env)

    def test_contenu_egal_au_dossier_d_execution_refus_apres_le_debut_du_repere(self):
        resultat, appels = self.planifie(PMZILLA_LAB_WORKSPACE=str(self.run))
        self.assertIn(self.CLE_REFUS, resultat.stdout)
        self.assertEqual(appels, [])                                       # aucun outil, contrôle du cache compris
        self.assertEqual(len(self.notifications), 1)
        self.assertIn(self.NOTIF_REFUS, self.notifications[0])
        repere = json.loads((self.donnees / "veille-du-jour.json").read_text())
        self.assertEqual((repere["etat"], repere["code"], repere["date"]), ("echoue", 1, "2026-10-14"))
        self.assertFalse((self.donnees / "veille.verrou").exists())        # verrou libéré
        self.assertEqual(resultat.returncode, 1)

    def test_refus_aussi_pour_un_sous_dossier_et_pour_un_lien_vers_le_dossier_d_execution(self):
        (self.run / "contenu").mkdir()
        resultat, appels = self.planifie(PMZILLA_LAB_WORKSPACE=str(self.run / "contenu"))
        self.assertEqual((resultat.returncode, appels), (1, []))
        (self.donnees / "veille-du-jour.json").unlink()
        raccourci = self.home / "raccourci"
        raccourci.symlink_to(self.run)
        resultat, appels = self.planifie(PMZILLA_LAB_WORKSPACE=str(raccourci))
        self.assertEqual((resultat.returncode, appels), (1, []))

    def test_refus_en_manuel_aussi(self):
        resultat, appels = self.lancer(script=self.lien, PMZILLA_LAB_WORKSPACE=str(self.run))
        self.assertEqual((resultat.returncode, appels), (1, []))
        self.assertIn(self.CLE_REFUS, resultat.stdout)

    def test_le_refus_vient_apres_le_garde_de_rattrapage_lancement_sans_objet_silencieux(self):
        resultat, appels = self.planifie(heure="06:00", PMZILLA_LAB_WORKSPACE=str(self.run))   # pas encore l'heure due
        self.assertEqual((resultat.returncode, resultat.stdout, resultat.stderr, appels), (0, "", "", []))
        self.assertEqual(self.notifications, [])
        self.assertFalse((self.donnees / "veille-du-jour.json").exists())

    def test_rattrapage_horaire_suivant_apres_le_refus_est_silencieux(self):
        self.planifie(PMZILLA_LAB_WORKSPACE=str(self.run))
        self.appels.unlink()
        avant = (self.donnees / "veille-du-jour.json").read_bytes()
        resultat, appels = self.planifie(heure="09:00", option="--catch-up", PMZILLA_LAB_WORKSPACE=str(self.run))
        self.assertEqual((resultat.returncode, resultat.stdout, resultat.stderr, appels), (0, "", "", []))
        self.assertFalse(self.appels.exists() and self.appels.read_text().strip())
        self.assertEqual((self.donnees / "veille-du-jour.json").read_bytes(), avant)

    # Le verrou est le seul repère
    def test_pendant_la_collecte_le_dossier_de_donnees_ne_tient_que_le_verrou_et_le_repere_du_jour(self):
        (self.home / ".local" / "bin" / "uv").write_text(FAUX_UV.replace(
            'echo "$appel" >> "$APPELS"',
            'echo "$appel" >> "$APPELS"\n[ "$appel" = "watch_lab.py collect" ] && ls -A "$HOME/.pmzilla-lab" > "$HOME/pendant.txt"'))
        resultat, _ = self.lancer_lien()
        self.assertEqual(resultat.returncode, 0)
        pendant = set((self.home / "pendant.txt").read_text().split())
        self.assertEqual(pendant, {"veille.verrou", "veille-du-jour.json", "uv-version", "uv-python-version"})

    def test_texte_du_script_aucun_autre_repere_de_passage(self):
        texte = SCRIPT.read_text(encoding="utf-8")
        for motif in (r"db-backup", r"offsite", r"db_backup", r"\.encours", r"en-cours\.", r"\.marqueur"):
            self.assertNotRegex(texte, motif)
        self.assertEqual(texte.count('mkdir "$VERROU"'), 1)   # le seul dossier-repère créé est le verrou


class Plist(unittest.TestCase):
    """Le fichier de tools/ est un modèle : aucun chemin réel, __HOME__ à remplacer à l'installation."""

    def setUp(self):
        self.texte = (SCRIPT.parent / "com.pmzilla.watch.plist").read_text(encoding="utf-8")

    def test_etiquette_et_chemins_du_modele(self):
        self.assertIn("<string>com.pmzilla.watch</string>", self.texte)
        self.assertIn("<string>__LAB__/watch.sh</string>", self.texte)
        self.assertEqual(self.texte.count("<string>__HOME__/Library/Logs/pmzilla-watch.log</string>"), 2)

    def test_aucun_chemin_reel(self):
        self.assertNotIn("/Users/", self.texte)
        self.assertNotIn("veille", self.texte.lower())

    def test_le_rendu_par_sed_donne_un_plist_valide(self):
        rendu = subprocess.run(["sed", "-e", "s|__HOME__|/home/essai|g", "-e", "s|__LAB__|/home/essai/PMZilla-Lab|g"], input=self.texte, text=True, capture_output=True).stdout
        self.assertNotIn("__HOME__", rendu)
        self.assertNotIn("__LAB__", rendu)
        import plistlib
        donnees = plistlib.loads(rendu.encode())
        self.assertEqual(donnees["ProgramArguments"][1], "/home/essai/PMZilla-Lab/watch.sh")

    def test_le_chemin_du_plist_est_le_dossier_des_outils_de_watch_sh(self):
        """Le modèle lance __LAB__/watch.sh ; watch.sh en déduit ses dossiers (TOOLS, WORKSPACE) : les deux
        doivent désigner la même racine, sinon le script lancé ne retrouve pas ses outils."""
        import re
        import plistlib
        script = SCRIPT.read_text(encoding="utf-8")
        outils = re.search(r'^TOOLS="([^"]+)"', script, re.M).group(1)
        espace = re.search(r'^WORKSPACE="([^"]+)"', script, re.M).group(1)
        self.assertEqual(espace, "$LAB_CONTENT_ROOT")   # contenu : le module partagé (la variable, sinon le dépôt Git du code)
        rendu = self.texte.replace("__HOME__", "/home/essai").replace("__LAB__", "/home/essai/PMZilla-Lab")
        programme = plistlib.loads(rendu.encode())["ProgramArguments"][1]
        self.assertEqual(outils, "$LAB_FOLDER")   # le dossier du lab, donné par le module partagé
        self.assertEqual(str(Path(programme).parent), "/home/essai/PMZilla-Lab")
        self.assertEqual(Path(programme).name, "watch.sh")


    def test_les_modeles_planifies_de_la_veille_lancent_le_lien_et_ne_nomment_aucun_dossier_de_code(self):
        for nom in ("com.pmzilla.watch.plist", "com.pmzilla.watch-catchup.plist"):
            texte = (SCRIPT.parent / nom).read_text(encoding="utf-8")
            self.assertIn("<string>__LAB__/watch.sh</string>", texte, nom)
            self.assertNotRegex(texte, r"PMZilla-Lab/(workspace|run)\b", nom)
            self.assertNotIn("/tools/", texte, nom)


class VeilleDesComposants(Base):
    """Étape « veille des composants » (R-41, design.md D4) : `composants.py check --if-due` juste avant le tableau de bord, jamais
    bloquante, jamais dans les étapes en échec. Le faux `composants.py check` rend le code que le test fixe (ECHEC, ECHEC_CODE)."""

    TEXTE_NOUVEAUTES = "Composants : nouveautés à examiner. Voir le tableau de bord."
    TEXTE_IMPOSSIBLE = "Veille des composants impossible. Voir le journal de la veille."

    def test_rien_de_nouveau_appel_avec_l_option_d_echeance_juste_avant_le_tableau_de_bord(self):
        resultat, appels = self.lancer()
        self.assertEqual(appels[-3:], ["composants.py check", "mutation_masking.py run", "dashboard.py"])
        self.assertIn("composants.py check --if-due", self.complets.read_text())
        self.assertEqual(self.notifications, [])
        self.assertTrue(resultat.stdout.rstrip().endswith("=== Veille terminée sans erreur ==="))
        self.assertEqual(resultat.returncode, 0)

    def test_nouveautes_une_notification_et_code_inchange(self):
        resultat, appels = self.lancer(echec="composants.py check", ECHEC_CODE="1")
        self.assertEqual(appels[-1], "dashboard.py")
        self.assertEqual(len(self.notifications), 1)
        self.assertIn(self.TEXTE_NOUVEAUTES, self.notifications[0])
        self.assertEqual(resultat.returncode, 0)
        self.assertTrue(resultat.stdout.rstrip().endswith("=== Veille terminée sans erreur ==="))

    def test_verification_impossible_journalisee_et_notifiee_sans_compter_comme_echec(self):
        resultat, appels = self.lancer(echec="composants.py check", ECHEC_CODE="2")
        self.assertIn("Veille des composants impossible (code 2)", resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn(self.TEXTE_IMPOSSIBLE, self.notifications[0])
        self.assertEqual(appels[-1], "dashboard.py")
        self.assertEqual(resultat.returncode, 0)
        self.assertNotIn("en échec", resultat.stdout)

    def test_base_injoignable_la_verification_tourne_quand_meme(self):
        resultat, appels = self.lancer(echec="watch_lab.py check-db", ECHEC_CODE="4")
        self.assertEqual(appels, ["watch_lab.py check-db", "composants.py check", "mutation_masking.py run", "dashboard.py"])
        self.assertIn("=== Veille terminée avec 1 étape(s) en échec : base de données ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)

    def test_impossible_et_echec_d_une_etape_le_resume_ne_nomme_que_l_etape(self):
        resultat, appels = self.lancer(echec="watch_lab.py check-db,composants.py check", ECHEC_CODE="4")
        self.assertIn("Veille des composants impossible (code 4)", resultat.stdout)
        self.assertIn("=== Veille terminée avec 1 étape(s) en échec : base de données ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)
        self.assertEqual(len(self.notifications), 2)              # la vérification impossible, puis le résumé

    def test_notification_impossible_seulement_journalisee(self):
        resultat, _ = self.lancer(echec="composants.py check", ECHEC_CODE="1", osascript=1)
        self.assertIn("Notification macOS impossible", resultat.stdout)
        self.assertEqual(resultat.returncode, 0)

    def test_ollama_absent_la_verification_tourne(self):
        resultat, appels = self.lancer(curl=7)
        self.assertIn("composants.py check", appels)
        self.assertEqual(appels[-1], "dashboard.py")


class TestsDeMutation(Base):
    """Étape « tests de mutation » (masking-mutation-tests, design.md D7) : `uv run --offline tools/mutation_masking.py run --due`
    juste après la veille des composants et avant le tableau de bord, jamais dans les étapes en échec, sans changer le code de sortie ;
    un code 2 ou 3 est nommé dans le journal. Le faux `mutation_masking.py run` rend le code que le test fixe (ECHEC, ECHEC_CODE)."""

    APPEL = "mutation_masking.py run"

    def test_appel_hors_ligne_avec_l_option_d_echeance_apres_les_composants_et_avant_le_tableau_de_bord(self):
        resultat, appels = self.lancer()
        self.assertEqual(appels[-3:], ["composants.py check", self.APPEL, "dashboard.py"])
        complets = self.complets.read_text()
        self.assertRegex(complets, r"run --offline \S*/tools/mutation_masking\.py run --due")
        self.assertEqual(self.notifications, [])
        self.assertNotIn("Tests de mutation", resultat.stdout)
        self.assertTrue(resultat.stdout.rstrip().endswith("=== Veille terminée sans erreur ==="))
        self.assertEqual(resultat.returncode, 0)

    def test_lancement_impossible_code_2_nomme_dans_le_journal_sans_compter_comme_echec(self):
        resultat, appels = self.lancer(echec=self.APPEL, ECHEC_CODE="2")
        self.assertIn("Tests de mutation en échec : lancement impossible (code 2)", resultat.stdout)
        self.assertEqual(appels[-1], "dashboard.py")
        self.assertNotIn("étape(s) en échec", resultat.stdout)
        self.assertTrue(resultat.stdout.rstrip().endswith("=== Veille terminée sans erreur ==="))
        self.assertEqual(resultat.returncode, 0)

    def test_score_sous_le_seuil_code_3_nomme_dans_le_journal_sans_compter_comme_echec(self):
        resultat, appels = self.lancer(echec=self.APPEL, ECHEC_CODE="3")
        self.assertIn("Tests de mutation en échec : score sous le seuil (code 3)", resultat.stdout)
        self.assertEqual(appels[-1], "dashboard.py")
        self.assertNotIn("étape(s) en échec", resultat.stdout)
        self.assertEqual(resultat.returncode, 0)

    def test_autre_code_journalise_sans_compter_comme_echec(self):
        resultat, _ = self.lancer(echec=self.APPEL, ECHEC_CODE="1")
        self.assertIn("Tests de mutation en échec (code 1)", resultat.stdout)
        self.assertEqual(resultat.returncode, 0)

    def test_base_injoignable_l_etape_tourne_et_le_resume_ne_nomme_que_la_base(self):
        resultat, appels = self.lancer(echec="watch_lab.py check-db," + self.APPEL, ECHEC_CODE="4")
        self.assertEqual(appels, ["watch_lab.py check-db", "composants.py check", self.APPEL, "dashboard.py"])
        self.assertIn("Tests de mutation en échec (code 4)", resultat.stdout)
        self.assertIn("=== Veille terminée avec 1 étape(s) en échec : base de données ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)

    def test_composants_en_echec_l_etape_tourne_quand_meme(self):
        resultat, appels = self.lancer(echec="composants.py check", ECHEC_CODE="2")
        self.assertEqual(appels[-3:], ["composants.py check", self.APPEL, "dashboard.py"])
        self.assertEqual(resultat.returncode, 0)

    def test_aucune_notification_pour_l_etape(self):
        for code in ("2", "3"):
            with self.subTest(code=code):
                self.appels.unlink(missing_ok=True)
                self.lancer(echec=self.APPEL, ECHEC_CODE=code)
                self.assertEqual(self.notifications, [])


class NiNettoyageNiInstallation(Base):
    """La veille ne nettoie jamais le cache de uv et n'installe aucun composant (spec watch-pipeline, R-41)."""

    INTERDITS = (r"\bcache\s+(clean|prune)\b", r"\bbrew\s+(install|upgrade|update)\b", r"\bollama\s+pull\b", r"\bnpm\s+install\b",
                 r"\bdocker\s+pull\b", r"\buv\s+sync\b")

    def test_texte_du_script(self):
        texte = SCRIPT.read_text(encoding="utf-8")
        for motif in self.INTERDITS:
            self.assertNotRegex(texte, motif)

    def test_appels_enregistres(self):
        self.versions(uv="uv 0.12.0")                      # le contrôle du cache tourne aussi
        resultat, _ = self.lancer(echec="composants.py check", ECHEC_CODE="1")
        complets = self.complets.read_text() + self.appels.read_text()
        for motif in self.INTERDITS:
            self.assertNotRegex(complets, motif)


if __name__ == "__main__":
    unittest.main()
