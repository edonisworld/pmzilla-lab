"""Fixture commune des tests du résumé du matin (change morning-summary, R-50, design D13).

Tout se passe dans un dossier temporaire : dossier de données, racine du contenu, jour du jour, faux `osascript` en tête du PATH
(avec un journal d'appels), faux `security`, base des cas remplacée par une fonction. Aucun réseau, aucun vrai dossier, aucune notification.
Une chaîne sentinelle est posée dans chaque titre et chaque texte de problème : aucune sortie ne doit la contenir.
"""
import contextlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import morning_summary as ms  # noqa: E402
import roadmap  # noqa: E402
import roadmap_model as rm  # noqa: E402

JOUR = "2026-10-14"
HIER = "2026-10-13"
SENTINELLE = "SENTINELLE-TEXTE-7431"
MOT_DE_PASSE = "SENTINELLE-MOT-DE-PASSE-12345"
AUTEUR = "auteur-de-test"


def noeud_feature(n, status="Ready", state="OPEN"):
    """Instantané normalisé d'une feature (format de roadmap.normalise), titre et corps sentinelles."""
    bloc = {"id": f"R-{n}", "theme": "outillage", "estimate": "1h", "method": "direct-prompt", "model": "sonnet", "conditions": "",
            "rank": n * 10}
    return {"number": 100 + n, "title": rm.feature_title(n, SENTINELLE), "state": state.lower(), "reason": "",
            "body": rm.marker(f"R-{n}") + "\n" + rm.render_block(bloc) + "\n\n" + SENTINELLE,
            "labels": [rm.LABEL_FEATURE, rm.label_theme("outillage")], "milestone": {"title": "Jalon-A", "state": "open"},
            "parent": None, "blocked_by": [], "status": status}


def bilan(numero, decision=False):
    return {"number": numero, "problem": SENTINELLE, "review_due": JOUR, "postponements": 3 if decision else 0,
            "decision_required": decision}


class Labo(unittest.TestCase):
    """Un dossier de données, une racine de contenu, un PATH avec faux osascript, et des aides d'écriture."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.donnees = self.tmp / "donnees"
        self.donnees.mkdir()
        self.racine = self.tmp / "contenu"
        (self.racine / ".pmzilla").mkdir(parents=True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.appels = self.tmp / "osascript.log"
        self.stub("osascript", f'#!/bin/sh\necho CALL >> "{self.appels}"\nfor a in "$@"; do printf "%s\\n" "$a" >> "{self.appels}"; done\nexit "${{STUB_EXIT:-0}}"\n')
        env = {"PMZILLA_LAB_DATA": str(self.donnees), "PMZILLA_LAB_WORKSPACE": str(self.racine), "PMZILLA_LAB_TODAY": JOUR,
               "PATH": f"{self.bin}:/usr/bin:/bin", "PMZILLA_LAB_CASES_AUTHOR": AUTEUR}
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        for nom in ("PMZILLA_SUMMARY_NOTIFY", "STUB_EXIT", "PMZILLA_LAB_DB_PASSWORD_PMZILLA_CASES_RO", "PMZILLA_LAB_DB_PASSWORD"):
            os.environ.pop(nom, None)
        self.reviews_demandes = []

    # -- écriture des fichiers lus ---------------------------------------------------------------------------------
    def stub(self, nom, texte):
        chemin = self.bin / nom
        chemin.write_text(texte, encoding="utf-8")
        chemin.chmod(0o755)

    def json(self, nom, contenu):
        (self.donnees / nom).write_text(json.dumps(contenu), encoding="utf-8")

    def repere(self, etat="termine", declencheur="calendrier", date=JOUR):
        self.json("veille-du-jour.json", {"date": date, "declencheur": declencheur, "debut": "07:10", "fin": "07:40", "etat": etat,
                                          "code": 0 if etat == "termine" else 1, "notifie": False, "essais": 0, "reprises": 0})

    def retenus(self, n=7, date=JOUR):
        self.json("veille-retenus.json", {"date": date, "retained": n})

    def cache(self, prets=4, en_cours=1, jour=JOUR):
        issues = [noeud_feature(i + 1) for i in range(prets)] + [noeud_feature(50 + i, "In progress") for i in range(en_cours)]
        roadmap.ecrit_cache(issues, __import__("datetime").date.fromisoformat(jour))

    def doctor(self, problemes=0, date=HIER):
        self.json("doctor-etat.json", {"version": 1, "checked_at": f"{date}T20:30", "counts": {"ok": 9, "warning": 1, "problem": problemes, "skipped": 0},
                                       "checks": [{"id": "db", "level": "problem", "reason": {"key": SENTINELLE, "counts": {}}}],
                                       "last_notification": None})

    def tout_connu(self):
        self.repere()
        self.retenus()
        self.cache()
        self.doctor(2)

    def auteur_dans_le_fichier(self):
        os.environ.pop("PMZILLA_LAB_CASES_AUTHOR", None)
        (self.racine / ".pmzilla" / "cases.yaml").write_text(f"author: {AUTEUR}\n", encoding="utf-8")

    # -- lancement ------------------------------------------------------------------------------------------------
    def lancer(self, *argv, bilans=None, **env):
        """(code, sortie standard, erreur standard). `bilans` : liste rendue par la règle des bilans dus, ou exception levée."""
        def faux(auteur, jour):
            self.reviews_demandes.append((auteur, jour))
            if isinstance(bilans, BaseException) or (isinstance(bilans, type) and issubclass(bilans, BaseException)):
                raise bilans
            return list(bilans or [])
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            try:
                code = ms.main(list(argv), reviews=faux)
            except SystemExit as sortie_argparse:
                code = sortie_argparse.code
        return code, sortie.getvalue(), erreur.getvalue()

    def lancer_planifie(self, *argv, **options):
        return self.lancer("--notify", *argv, PMZILLA_SUMMARY_NOTIFY="1", **options)

    def notifications(self):
        """Appels du faux osascript : liste d'appels, chacun la liste de ses arguments."""
        if not self.appels.exists():
            return []
        appels, courant = [], None
        for ligne in self.appels.read_text(encoding="utf-8").splitlines():
            if ligne == "CALL":
                courant = []
                appels.append(courant)
            else:
                courant.append(ligne)
        return appels

    def memoire(self):
        return self.donnees / "resume-du-matin.json"

    def verrouiller_donnees(self):
        self.donnees.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(self.donnees.chmod, 0o700)
        if os.access(self.donnees, os.W_OK):
            self.skipTest("l'utilisateur du test écrit malgré les droits (administrateur)")
