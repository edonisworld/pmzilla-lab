"""
Aide des suites tests/train_auto et tests/train_ready (change autonomous-trains-observe, tâche 2).

Elle réutilise, sans les modifier, les dépôts jetables de tests/finish_train/aide_train.py : un dépôt distant nu pour « origin », un espace de
travail sur main, un dossier d'exécution détaché au sommet de main qui porte les copies du vrai finish_train.sh et de ses modules, un dossier de
données jetable, de faux dossiers du lab. Aucun réseau, aucune base, aucun vrai dossier du lab, jamais le vrai finish_train.sh du dépôt de travail.

Les faux, chacun avec sa raison et le risque qu'il ne couvre pas (R-20261028-26) :
  - FAUX_MATIN_AUTO remplace tools/morning_state.sh dans main du dépôt jetable (le passage et la fin le lancent depuis le dossier d'exécution) : le vrai
    garde du matin lit des repères de veille et de sauvegarde du dossier de données ; risque non couvert : la lecture réelle de ces repères
    (tests/morning_state). Il refuse quand le fichier matin-refuse existe.
  - FAUX_CROCHETS remplace tools/install_hooks.sh : le vrai installeur vérifie des liens de .git/hooks que le dépôt jetable n'a pas ; risque non
    couvert : la vérification réelle des liens (tests/installation). Il refuse quand le fichier crochets-ko existe.
  - le faux run_worktree.sh et le faux git espion sont ceux de aide_train.py (le faux git consigne ses appels et passe au vrai git).
  - le faux lsof de la carte des processus est un script posé par le test (PILOT_LSOF) ; risque non couvert : le vrai lsof (tests/pilot, tests/finish_train).
Les lancements de tools/train_auto.py et de tools/train_ready.py passent par un environnement en LISTE BLANCHE (aide_train.Train.env) : le marqueur
de session d'une session Claude Code n'y arrive jamais, sauf quand un test le pose.
"""
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tests" / "finish_train"))
sys.path.insert(0, str(RACINE / "tools"))
from aide_train import AvecTrain, NOM_FICTIF, OUTILS, Resultat, Train  # noqa: E402,F401

AUTO = RACINE / "tools" / "train_auto.py"
READY = RACINE / "tools" / "train_ready.py"
MARQUEUR_SESSION = "CLAUDECODE"

FAUX_MATIN_AUTO = """#!/bin/bash
echo "matin appelé : $*" >> "@ETAT@/appels.log"
[ ! -f "@ETAT@/matin-refuse" ] || { echo "morning_state : refusé (faux)"; exit 1; }
exit 0
"""

FAUX_CROCHETS = """#!/bin/sh
echo "crochets appelé : $*" >> "@ETAT@/appels.log"
[ ! -f "@ETAT@/crochets-ko" ] || exit 1
exit 0
"""

LISTE_PROTEGEE_COMPLETE = ("# liste fictive de l'outillage protégé, avec les graines du dépôt réel\ntools/hooks/\ntools/finish_branch.sh\n"
                           "tools/finish_train.sh\ntools/finish_protected.txt\ntests/run_all.sh\n.claude/\nCLAUDE.md\n*/CLAUDE.md\n")


def epoch(heure=12, minute=5, jour=(2026, 10, 29)):
    """Les secondes d'un instant à Paris."""
    return int(dt.datetime(*jour, heure, minute, tzinfo=ZoneInfo("Europe/Paris")).timestamp())


class AvecAuto(AvecTrain):
    """Un dépôt jetable avec les faux gardes posés dans main, et les lancements des deux outils."""

    def setUp(self):
        super().setUp()
        t = self.t
        t.commit_main({"tools/morning_state.sh": t.remplir(FAUX_MATIN_AUTO), "tools/install_hooks.sh": t.remplir(FAUX_CROCHETS)},
                      "faux gardes", pousser=True)
        t.mettre_a_jour_run()

    # --- lancements ------------------------------------------------------------------------------------------------------------------
    def environnement(self, now=None, extra=None):
        env = self.t.env()
        for cle in [c for c in env if c.startswith("FINISH_TRAIN_")]:
            env.pop(cle)   # les remplacements de la fin du dépôt jetable ne sont pas ceux d'un lancement de la tâche
        for cle, valeur in (extra or {}).items():
            if valeur is None:
                env.pop(cle, None)
            else:
                env[cle] = valeur
        if now is not None:
            env["TRAIN_AUTO_NOW"] = str(now)
        return env

    def lancer(self, script, args, now=None, extra=None, langue=None, delai=300, entree=None):
        """`entree` : un texte mis dans un tube ouvert sur l'entrée standard du lancement (revue 10.1, constat 5) ; sans lui, l'entrée est fermée (/dev/null)."""
        commande = [sys.executable, "-I", str(script)]
        if langue:
            commande += ["--language", langue]
        commande += list(args)
        # groupe de processus à part : au dépassement du délai, tout le groupe est tué, pas seulement le premier processus (R-20261030-01)
        proc = subprocess.Popen(commande, cwd=self.t.lab, env=self.environnement(now, extra), stdin=subprocess.DEVNULL if entree is None else subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            sortie, erreur = proc.communicate(input=entree, timeout=delai)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            proc.communicate()
            raise
        return Resultat(proc.returncode, sortie, erreur)

    def auto(self, *args, now=None, extra=None, langue=None, entree=None):
        return self.lancer(AUTO, args, now, extra, langue, entree=entree)

    def passage(self, now=None, extra=None, langue=None, entree=None):
        return self.auto("pass", now=epoch() if now is None else now, extra=extra, langue=langue, entree=entree)

    def pret(self, *args, extra=None, langue=None):
        return self.lancer(READY, args, None, extra, langue)

    # --- états ------------------------------------------------------------------------------------------------------------------------
    def dossier_train(self) -> Path:
        return self.t.data / "train-auto"

    def fichier_liste(self) -> Path:
        return self.dossier_train() / "pretes.tsv"

    def octets_liste(self):
        f = self.fichier_liste()
        return f.read_bytes() if f.exists() else None

    def journal(self):
        f = self.dossier_train() / "journal.jsonl"
        return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []

    def passages(self):
        return [r for r in self.journal() if r["type"] == "passage"]

    def dernier(self):
        return self.passages()[-1]

    def etat(self):
        f = self.dossier_train() / "etat.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

    def tout_le_texte_ecrit(self):
        """Ce que le passage écrit dans le dossier de train (journal, état, arrêt), pour chercher une chaîne qui n'a rien à y faire.
        La liste prête est celle de la session, pas du passage : elle n'en fait pas partie."""
        morceaux = []
        for f in sorted(self.dossier_train().glob("*")):
            if f.is_file() and f.name != "pretes.tsv":
                morceaux.append(f.read_text(encoding="utf-8", errors="replace"))
        return "\n".join(morceaux)

    # --- branches prêtes ----------------------------------------------------------------------------------------------------------------
    def ecrire_empreinte(self, nom, arbre=None):
        wt = self.t.dossier_worktree(nom)
        chemin = self.t.git("rev-parse", "--path-format=absolute", "--git-path", "pmzilla-run-all-ok", cwd=wt)
        Path(chemin).write_text((arbre or self.t.git("rev-parse", "HEAD^{tree}", cwd=wt)) + "\n", encoding="utf-8")

    def preparer(self, nom, fichiers=None, suite=()):
        """La branche avec son worktree propre et l'empreinte d'un runner complet réussi sur son sommet (sans l'inscrire)."""
        self.t.branche(nom, fichiers, suite=suite)
        self.ecrire_empreinte(nom)

    def inscrire(self, nom, fichiers=None, revue="faite"):
        self.preparer(nom, fichiers)
        r = self.pret("add", nom, "--revue", revue)
        self.assertEqual(r.code, 0, r.texte)
        return r

    def commit_dans(self, nom, fichiers, message="suite"):
        return self.t.valider(self.t.dossier_worktree(nom), fichiers, message)

    def poser_liste_protegee_complete(self):
        self.t.commit_main({"tools/finish_protected.txt": LISTE_PROTEGEE_COMPLETE}, "liste protégée complète", pousser=True)
        self.t.mettre_a_jour_run()

    def poser_liste_front(self, entrees="mothra/front/\n"):
        self.t.commit_main({"tools/finish_e2e_paths.txt": "# liste fictive\n" + entrees}, "liste du front", pousser=True)
        self.t.mettre_a_jour_run()


class AvecPret(AvecAuto):
    """Alias lisible pour les tests de la liste prête."""


if __name__ == "__main__":
    unittest.main()
