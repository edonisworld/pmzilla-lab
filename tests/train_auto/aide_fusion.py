"""
Aide des suites de la tranche 3 d'autonomous-trains-merge (tâches 9.2 à 9.4, design D9 à D15) : le mode de fusion du passage, avec un FAUX finish_train.sh dans
le dépôt jetable (jamais le vrai script de fin lancé pour de bon).

Les faux, chacun avec sa raison et le risque qu'il ne couvre pas (R-20261028-26) :
  - FAUX_FIN remplace tools/finish_train.sh : l'essai (`--essai`) rend FAUX_CODE_ESSAI (0 par défaut) ; le train réel (`--auto`) consigne ses arguments, son
    environnement, son groupe de processus et son entrée standard, écrit l'enregistrement du journal des trains par le vrai tools/train_record.py, puis rend
    FAUX_CODE_AUTO ; risque non couvert : le vrai script (tests/finish_train, qui lance le vrai train sur des dépôts jetables).
  - FAUX_DOCTOR remplace tools/doctor.py du dossier d'exécution : le vrai contrôle du crochet reference-transaction lit l'installation de l'auteur ; risque non
    couvert : la lecture réelle (tests/doctor).
  - TRAIN_AUTO_NOTIFIER remplace la commande de notification (tests seulement) : le vrai osascript n'est jamais lancé.
Le journal des trains et le fichier d'activation sont ceux du dossier de données jetable.
"""
import json
import os
import plistlib
import sys
from pathlib import Path

from aide_auto import AvecAuto, RACINE, epoch  # noqa: F401

sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402


def chemin_faux_modele(maison):
    """Le PATH du faux modèle launchd de `maison` : celui que train_auto calcule pour le faux `python3` de ce dossier personnel."""
    return train_auto.job_path(Path(maison) / "faux-python", maison)


def run_calcule():
    """Le dossier d'exécution que installed_plist_check() calcule quand on ne le lui donne pas (un lancement sans PMZILLA_LAB_RUN voit le même)."""
    try:
        return str(train_auto.lab_paths.run_tree(train_auto.lab_paths.content_root()))
    except train_auto.lab_paths.LabPathsError:
        return "/r"   # le contrôle retombe alors sur le WorkingDirectory du modèle installé : n'importe quelle valeur est conforme


def poser_modele_launchd(maison, run=None, date=None, surcharge=None):
    """R-20261110-33 (Q23) et R-20261110-39 (Q27) : pose le faux modèle launchd installé dans le faux dossier personnel `maison` (daté de 10:00Z, ou `date`) ; source commune de l'aide
    activer() et des suites d'activation. Le modèle est CONFORME : c'est celui que train_auto calcule (plist_model) pour un faux `python3` 3.14 de `maison`, avec le dossier d'exécution
    `run` (celui du lancement ; sans lui, le calculé), pour que le contrôle F6 rende `ok` ; `surcharge` change des clés de premier niveau (un modèle installé différent). Risque non
    couvert : le vrai chargement par launchd."""
    maison = Path(maison)
    python = maison / "faux-python" / "python3"
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text('#!/bin/sh\necho "Python 3.14.0"\n', encoding="utf-8")
    python.chmod(0o755)
    agents = maison / "Library" / "LaunchAgents"
    agents.mkdir(parents=True, exist_ok=True)
    modele = agents / f"{train_auto.LABEL}.plist"
    contenu = train_auto.plist_model(python, run or run_calcule(), maison)
    contenu.update(surcharge or {})
    modele.write_bytes(plistlib.dumps(contenu))
    date = train_auto.epoch_of("2026-11-10T10:00:00Z") if date is None else date
    os.utime(modele, (date, date))


def ligne_passage_launchd(maison):
    """La ligne de journal d'un faux passage launchd à 0 (11:00Z), postérieur au faux modèle, avec l'empreinte du PATH du faux modèle de `maison`."""
    # `marqueur_test` : champ réservé aux tests (R-20261110-34, Q25), que le code ne pose jamais ; l'aide journal() de test_activation_commandes ne masque que ce faux passage
    return json.dumps({"type": "passage", "utc": "2026-11-10T11:00:00Z", "caller": "launchd", "env_job": train_auto.path_fingerprint(chemin_faux_modele(maison)),
                       "marqueur_test": "faux-passage-launchd",
                       "essai": {"code": 0, "relance": False, "code2": None, "retirees": []}}) + "\n"

TRAIN_RECORD = RACINE / "tools" / "train_record.py"
SOMMET_FAUX = "c" * 40

FAUX_FIN = """#!/bin/bash
echo "$*" >> "@ETAT@/appels-fin.txt"
mode=essai; names=()
for a in "$@"; do if [ "$a" = "--auto" ]; then mode=auto; elif [ "$a" != "--essai" ]; then names+=("$a"); fi; done
[ "$mode" = auto ] || { [ -z "${FAUX_RM:-}" ] || rm -f "$FAUX_RM"; exit "${FAUX_CODE_ESSAI:-0}"; }
env | sort > "@ETAT@/env-train.txt"
echo "pgid=$(ps -o pgid= -p $$ | tr -d ' ') pid=$$" > "@ETAT@/groupe-train.txt"
if [ -t 0 ]; then echo terminal > "@ETAT@/stdin-train.txt"; elif read -r -t 1 _x; then echo lu > "@ETAT@/stdin-train.txt"; else echo ferme > "@ETAT@/stdin-train.txt"; fi
if [ -n "${FAUX_IGNORE_TERM:-}" ]; then trap '' TERM; sleep "$FAUX_IGNORE_TERM" & wait; fi
if [ -n "${FAUX_DORS:-}" ]; then
  ( trap 'echo recu > "@ETAT@/enfant-term.txt"; exit 0' TERM; sleep "$FAUX_DORS" & wait ) &
  trap 'exit 143' TERM; sleep "$FAUX_DORS" & wait
fi
code=${FAUX_CODE_AUTO:-0}
if [ "${FAUX_SANS_ENREGISTREMENT:-}" != 1 ]; then
  sommets=""
  for n in "${names[@]}"; do s=$(@GIT@ -C @CONTENU@ rev-parse "refs/heads/$n"); sommets="${sommets:+$sommets,}$s"; done
  "@PYTHON@" -I "$(dirname "$0")/train_record.py" append --code "$code" --sens "${FAUX_SENS:-fusionne}" --mode auto --n "${#names[@]}" --sommets "$sommets" \\
    --sommet-train "@SOMMET@" --main-avant "@AVANT@" --main-apres "@APRES@" --runner conteneur --duree-s "${FAUX_DUREE:-120}" \\
    ${FAUX_POLITIQUE:+--politique "$FAUX_POLITIQUE"} > /dev/null || exit 99
fi
exit "$code"
"""

FAUX_DOCTOR = """#!/usr/bin/env python3
import json, sys
# faux doctor : le contrôle du crochet reference-transaction, avec l'état voulu par DOCTOR_FAUX (vert par défaut)
import os
statut = os.environ.get("DOCTOR_FAUX", "ok")
print(json.dumps({"checks": [{"name": "crochet reference-transaction", "status": statut}]}))
"""

NOTIFIER = """#!/bin/bash
printf '%s\\n' "$1" >> "@ETAT@/notifications.txt"
exit "${NOTIFIER_CODE:-0}"
"""


class AvecFusion(AvecAuto):
    """Un dépôt jetable avec le faux finish_train.sh, le faux doctor et le notificateur factice, dans le dossier d'exécution."""

    def setUp(self):
        super().setUp()
        t = self.t
        avant = t.main()
        fin = (FAUX_FIN.replace("@PYTHON@", sys.executable).replace("@SOMMET@", SOMMET_FAUX).replace("@AVANT@", avant).replace("@APRES@", "d" * 40))
        t.commit_main({"tools/finish_train.sh": t.remplir(fin), "tools/doctor.py": FAUX_DOCTOR}, "faux finish_train.sh et faux doctor", pousser=True)
        t.mettre_a_jour_run()
        self.notificateur = t.poser(t.fakes / "notifier.sh", NOTIFIER)

    # --- l'activation (D5, D6) --------------------------------------------------------------------------------------------------------
    def enregistrer_serie(self, tips=None):
        """Cinq trains verts de l'auteur dans le journal des trains jetable, dont un de deux branches et un qui touche l'interface."""
        tips = tips or [f"{n}" * 40 for n in "12345"]
        for i, tip in enumerate(tips):
            r = self.lancer(TRAIN_RECORD, ["append", "--heure", "2026-11-06T10:00:00Z", "--code", "0", "--sens", "fusionne", "--mode", "manuel",
                                           "--n", "2" if i == 1 else "1", "--sommets", ",".join(["a" * 40] * (2 if i == 1 else 1)), "--sommet-train", tip,
                                           "--main-avant", "9" * 40, "--main-apres", tip, "--runner", "conteneur", "--duree-s", "600"]
                            + (["--front"] if i == 2 else []))
            self.assertEqual(r.code, 0, r.texte)
        return tips

    def poser_essai_launchd(self):
        """R-20261110-32 (Q21) : remplit la condition `essai-launchd` (D10) dans le dossier jetable : un faux modèle launchd installé dans un faux dossier personnel (daté de 10:00Z)
        et un faux passage launchd à 0 (11:00Z, `env_job` égal à l'empreinte du PATH du modèle). Rend (le faux dossier personnel, la ligne du faux passage) ; risque non couvert :
        le vrai lancement par launchd (tests/train_auto/test_essai_launchd.py lit la condition elle-même)."""
        maison = self.t.dossier / "maison-launchd"
        poser_modele_launchd(maison, run=str(self.t.run))
        ligne = ligne_passage_launchd(maison)
        self.dossier_train().mkdir(parents=True, exist_ok=True)
        journal = self.dossier_train() / "journal.jsonl"
        avant = journal.read_text(encoding="utf-8") if journal.exists() else ""
        journal.write_text(avant + ligne, encoding="utf-8")
        return maison, ligne

    def activer(self):
        self.enregistrer_serie()
        maison, ligne = self.poser_essai_launchd()
        r = self.auto("activer", extra={"HOME": str(maison)})
        self.assertEqual(r.code, 0, r.texte)
        self.assertTrue((self.dossier_train() / "fusion-active").exists())
        # le faux passage n'est qu'une préparation : il quitte le journal pour que les tests comptent seulement les passages qu'ils lancent
        journal = self.dossier_train() / "journal.jsonl"
        journal.write_text(journal.read_text(encoding="utf-8").replace(ligne, "", 1), encoding="utf-8")

    # --- les branches prêtes et la sonde ---------------------------------------------------------------------------------------------------
    def lister(self, *noms, revue="faite"):
        lignes = ["# pmzilla-train-pretes format 1"]
        for nom in noms:
            lignes.append("\t".join((nom, self.t.sommet(nom), self.t.arbre(nom), revue, "2026-10-29T10:00:00Z")))
        self.dossier_train().mkdir(parents=True, exist_ok=True)
        self.fichier_liste().write_text("\n".join(lignes) + "\n", encoding="utf-8")

    def assurer(self, nom):
        """La branche avec son worktree propre et l'empreinte d'un runner complet réussi, créée une seule fois."""
        if not self.t.dossier_worktree(nom).exists():
            self.preparer(nom)

    def passage_fusion(self, *noms, extra=None, now=None, entree=None):
        """Prépare les branches, les liste (revue faite) et lance un passage avec le notificateur factice."""
        for n in noms:
            self.assurer(n)
        self.lister(*noms)
        return self.passage(now=now, extra=self.avec_notificateur(extra), entree=entree)

    def appels_fin(self):
        f = self.t.etat / "appels-fin.txt"
        return f.read_text(encoding="utf-8").splitlines() if f.exists() else []

    def appels_train(self):
        return [a for a in self.appels_fin() if a.startswith("--auto")]

    def notifications(self):
        f = self.t.etat / "notifications.txt"
        return f.read_text(encoding="utf-8").splitlines() if f.exists() else []

    def avec_notificateur(self, extra=None):
        return dict({"TRAIN_AUTO_NOTIFIER": str(self.notificateur)}, **(extra or {}))

    def fichier_rapport(self) -> Path:
        return self.t.lab / "etapes" / "fusions-auto.md"

    def rapport(self):
        f = self.fichier_rapport()
        return f.read_text(encoding="utf-8") if f.exists() else None

    def etat_refuses(self):
        etat = self.etat()
        return (etat or {}).get("refuses", [])

    def journal_json(self):
        return json.dumps(self.journal())
