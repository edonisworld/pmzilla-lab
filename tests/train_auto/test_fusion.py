"""
Tranche 3 d'autonomous-trains-merge, tâche 9.2 (design D9) : le mode de fusion du passage, avec un faux finish_train.sh dans le dépôt jetable. Le train réel part
après un essai final à 0 seulement, avec trois branches au plus, sans nouveau lancement, dans un environnement sans FINISH_TRAIN_* ni jeton de verrou, dans son
propre groupe de processus, avec un délai de trois heures ; `latest_start` et son repli 20:30 ; le contrôle doctor du crochet bloque en fusion (D17).

    bash tests/run_all.sh train_auto
"""
import contextlib
import datetime as dt
import io
import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from aide_fusion import AvecFusion, epoch

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402


def enregistrement(duree, **surcharge):
    base = {"format": 1, "heure": "2026-11-06T10:00:00Z", "code": 0, "sens": "fusionne", "mode": "manuel", "n": 1, "runner": "conteneur", "duree_s": duree}
    base.update(surcharge)
    return base


class DepartLimite(unittest.TestCase):
    """D9 : `latest_start(records, day)`, 22:00 heure de Paris moins la durée la plus longue des dix derniers trains verts du conteneur, moins 10 minutes."""

    JOUR = dt.date(2026, 11, 6)

    def heure(self, records):
        d = train_auto.latest_start(records, self.JOUR)
        return d.strftime("%H:%M:%S")

    def test_moins_de_dix_trains_le_repli_de_20_h_30(self):
        self.assertEqual(train_auto.DEPART_LIMITE_REPLI, "20:30")
        self.assertEqual(self.heure([]), "20:30:00")
        self.assertEqual(self.heure([enregistrement(7200)] * 9), "20:30:00")

    def test_dix_trains_la_plus_longue_duree_moins_dix_minutes(self):
        records = [enregistrement(600)] * 9 + [enregistrement(7200)]
        self.assertEqual(self.heure(records), "19:50:00")   # 22:00 - 2 h - 10 min

    def test_arrondi_a_la_minute_inferieure(self):
        records = [enregistrement(600)] * 9 + [enregistrement(7230)]   # 22:00 - 2 h 0 min 30 s - 10 min = 19:49:30
        self.assertEqual(self.heure(records), "19:49:00")

    def test_seuls_les_dix_derniers_trains_verts_du_conteneur_comptent(self):
        vieux = [enregistrement(9000)]   # sorti de la fenêtre des dix derniers
        dix = [enregistrement(1200)] * 10
        self.assertEqual(self.heure(vieux + dix), "21:30:00")
        autres = [enregistrement(9999, code=70, sens="refuse"), enregistrement(9999, sens="essai"), enregistrement(9999, runner="remplace")]
        self.assertEqual(self.heure(dix + autres), "21:30:00", "un train rouge, un essai ou un runner remplacé ne compte pas")
        self.assertEqual(self.heure([enregistrement(1200, mode="auto")] * 10), "21:30:00", "le mode, auto ou manuel, ne filtre pas")

    def test_le_jour_donne_l_heure_de_paris(self):
        d = train_auto.latest_start([], dt.date(2026, 7, 1))   # heure d'été
        self.assertEqual((d.hour, d.minute), (20, 30))
        self.assertEqual(d.utcoffset(), dt.timedelta(hours=2))


class PasseEnFusion(AvecFusion):
    # --- le mode ---------------------------------------------------------------------------------------------------------------------
    def test_sans_activation_c_est_l_observation_et_aucun_train_reel(self):
        r = self.passage_fusion("feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.appels_fin(), ["--essai feat/x"])
        d = self.dernier()
        self.assertEqual((d["mode"], d["decision"], d["raison"], d["train"]), ("observation", "observe", "essai", None))
        self.assertIsNone(self.rapport(), "rien n'est écrit en observation")
        self.assertEqual(self.notifications(), [])

    def test_une_activation_invalide_est_l_observation(self):
        self.activer()
        f = self.dossier_train() / "fusion-active"
        f.write_text('{"format": 1, "heure": "2026-11-06T12:00:00Z", "serie": ["' + '9' * 40 + '"]}', encoding="utf-8")
        f.chmod(0o600)
        r = self.passage_fusion("feat/x")
        self.assertEqual(self.appels_fin(), ["--essai feat/x"])
        self.assertEqual(self.dernier()["mode"], "observation")
        self.assertIn("activation invalide", r.sortie)

    def test_un_fichier_d_activation_disparu_est_l_observation_et_n_est_jamais_recree(self):
        self.activer()
        (self.dossier_train() / "fusion-active").unlink()
        self.passage_fusion("feat/x")
        self.assertEqual(self.appels_train(), [])
        self.assertFalse((self.dossier_train() / "fusion-active").exists())

    # --- le train réel ---------------------------------------------------------------------------------------------------------------
    def test_train_reel_apres_un_essai_final_a_zero(self):
        self.activer()
        r = self.passage_fusion("feat/x", "feat/y")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.appels_fin(), ["--essai feat/x feat/y", "--auto feat/x feat/y"])
        d = self.dernier()
        self.assertEqual((d["mode"], d["decision"], d["raison"]), ("fusion", "train", "fusion-auto"))
        self.assertEqual((d["train"]["code"], d["train"]["sens"]), (0, "fusionne"))
        self.assertEqual(d["train"]["sommets"], [self.t.sommet("feat/x"), self.t.sommet("feat/y")])
        self.assertIsInstance(d["train"]["duree"], int)
        self.assertIn("train_auto : fusion automatique : 2 branche(s) ; train code 0 (fusionne), 2 min", r.sortie)
        self.assertFalse((self.dossier_train() / "arret").exists())

    def test_un_essai_final_non_nul_ne_lance_pas_le_train(self):
        self.activer()
        r = self.passage_fusion("feat/x", extra={"FAUX_CODE_ESSAI": "70"})
        self.assertEqual(self.appels_train(), [])
        self.assertEqual((self.dernier()["decision"], self.dernier()["mode"]), ("observe", "fusion"))
        self.assertIn("essai code 70", r.sortie)

    def test_un_arret_arme_par_l_essai_empeche_le_train(self):
        self.activer()
        self.passage_fusion("feat/x", extra={"FAUX_CODE_ESSAI": "65"})
        self.assertEqual(self.appels_train(), [])
        self.assertTrue((self.dossier_train() / "arret").exists())

    def test_pas_de_nouveau_lancement_du_train(self):
        self.activer()
        self.passage_fusion("feat/x", "feat/y", extra={"FAUX_CODE_AUTO": "70", "FAUX_SENS": "refuse"})
        self.assertEqual(len(self.appels_train()), 1, "le train réel n'est jamais relancé dans le passage")
        self.assertEqual(len([a for a in self.appels_fin() if a.startswith("--essai")]), 1)
        self.assertEqual(self.dernier()["train"]["code"], 70)

    def test_trois_branches_au_plus_dans_les_deux_modes(self):
        noms = [f"feat/p{k}" for k in range(4)]
        self.passage_fusion(*noms)   # observation
        self.assertEqual(self.appels_fin(), ["--essai " + " ".join(noms[:3])])
        self.assertIn({"branche": noms[3], "raison": "plafond"}, [{"branche": e["branche"], "raison": e["raison"]} for e in self.dernier()["ecartees"]])

    def test_trois_branches_au_plus_dans_le_train_reel(self):
        self.activer()
        noms = [f"feat/p{k}" for k in range(4)]
        self.passage_fusion(*noms)
        self.assertEqual(self.appels_fin(), ["--essai " + " ".join(noms[:3]), "--auto " + " ".join(noms[:3])])

    def test_les_branches_retirees_par_la_relance_ne_sont_pas_dans_le_train(self):
        self.activer()
        for n in ("feat/x", "feat/y"):
            self.preparer(n)
        self.lister("feat/x", "feat/y")
        # le faux finish rend 62 à l'essai avec le refus de feat/y, puis 0 à la relance : la forme exacte des lignes est celle que lit l'analyseur
        self.t.casser_le_module("finish_train.sh", self.t.remplir(self.faux_refus_62()))
        r = self.passage(extra=self.avec_notificateur())
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.appels_fin(), ["--essai feat/x feat/y", "--essai feat/x", "--auto feat/x"])
        d = self.dernier()
        self.assertEqual(d["ecartees_essai"], [{"branche": "feat/y", "code": 62}])
        self.assertEqual(d["train"]["sommets"], [self.t.sommet("feat/x")])

    def faux_refus_62(self):
        return (FAUX_REFUS_62.replace("@PYTHON@", sys.executable).replace("@GIT@", self.t.git_reel).replace("@CONTENU@", str(self.t.contenu)))

    def test_le_train_est_lance_sans_variable_de_fin_ni_jeton_dans_son_groupe_a_part_et_sans_entree(self):
        self.activer()
        extra = {"FINISH_TRAIN_RUNNER": "bash faux", "FINISH_TRAIN_CI": "faux", "FINISH_TRAIN_MORNING_CHECK": "faux", "FINISH_LOCK_TOKEN": "jeton-herite",
                 "FINISH_TRAIN_LOG_DIR": "/nulle/part"}
        self.passage_fusion("feat/x", extra=extra, entree="o\n ")   # revue 10.1 : un tube ouvert qui contient « o » ; un train qui hériterait de l'entrée du passage verrait « lu »
        env = (self.t.etat / "env-train.txt").read_text(encoding="utf-8")
        self.assertNotIn("FINISH_TRAIN_", env)
        self.assertNotIn("FINISH_LOCK_TOKEN", env)
        self.assertNotIn("CLAUDECODE", env)
        self.assertEqual((self.t.etat / "stdin-train.txt").read_text(encoding="utf-8").strip(), "ferme")
        groupe = dict(p.split("=") for p in (self.t.etat / "groupe-train.txt").read_text(encoding="utf-8").split())
        self.assertEqual(groupe["pgid"], groupe["pid"], "le train est le chef de son propre groupe de processus")

    def test_le_train_reel_n_est_lance_que_par_une_commande_avec_auto(self):
        self.assertEqual(train_auto.train_command("/run", ["feat/a", "feat/b"]), ["bash", "/run/tools/finish_train.sh", "--auto", "feat/a", "feat/b"])
        self.assertEqual(train_auto.TRAIN_TIMEOUT, 10800)
        self.assertEqual(train_auto.PLAFOND_TRAIN, 3)

    def test_un_enregistrement_du_train_manquant_arme_l_arret(self):
        self.activer()
        r = self.passage_fusion("feat/x", extra={"FAUX_SANS_ENREGISTREMENT": "1"})
        self.assertTrue((self.dossier_train() / "arret").exists(), "code 0 sans enregistrement : anomalie, arrêt armé (D10)")
        self.assertIn("train_auto : arrêt armé après le code 0", r.sortie)

    # --- le délai de trois heures ------------------------------------------------------------------------------------------------------
    def test_delai_le_groupe_recoit_term_et_l_arret_est_arme(self):
        self.activer()
        r = self.passage_fusion("feat/x", extra={"FAUX_DORS": "60", "TRAIN_AUTO_TRAIN_TIMEOUT": "2", "TRAIN_AUTO_TERM_GRACE": "20"})
        self.assertEqual(r.code, 0, r.texte)
        d = self.dernier()
        self.assertEqual(d["train"]["code"], 143, "le train sort en 143 sur TERM")
        self.assertTrue(d["train"]["delai"])
        self.assertEqual(d["arret_arme"], 143)
        self.assertTrue((self.dossier_train() / "arret").exists())
        # revue 10.1 : TERM va à tout le groupe de processus, pas au seul premier processus : l'enfant en arrière-plan du faux note sa réception
        enfant = self.t.etat / "enfant-term.txt"
        for _ in range(50):
            if enfant.exists():
                break
            time.sleep(0.1)
        self.assertTrue(enfant.exists(), "l'enfant du train n'a pas reçu TERM : seul le premier processus l'a reçu")

    def test_un_train_qui_ignore_term_est_tue_l_arret_est_arme_et_rien_ne_repart_avant_reprendre(self):
        # R-20261107-8 Q1 (a) : le KILL après le délai de grâce est gardé ; après tout KILL l'arrêt est armé, comme pour une interruption (D10)
        self.activer()
        r = self.passage_fusion("feat/x", extra={"FAUX_IGNORE_TERM": "60", "TRAIN_AUTO_TRAIN_TIMEOUT": "1", "TRAIN_AUTO_TERM_GRACE": "1"})
        self.assertEqual(r.code, 0, r.texte)
        d = self.dernier()
        self.assertEqual(d["train"]["code"], 137, "le train qui ignore TERM sort en 137 sur KILL")
        self.assertTrue(d["train"]["delai"])
        self.assertEqual(d["arret_arme"], 137)
        self.assertTrue((self.dossier_train() / "arret").exists())
        avant = self.appels_fin()
        self.passage_fusion("feat/x")
        self.assertEqual(self.appels_fin(), avant, "ni essai ni train tant que `reprendre` n'a pas été fait")
        self.assertEqual(self.dernier()["decision"], "arrete")
        self.assertEqual(self.auto("reprendre").code, 0)
        self.assertFalse((self.dossier_train() / "arret").exists())

    # --- l'heure de départ la plus tardive ---------------------------------------------------------------------------------------------
    def test_apres_l_heure_de_depart_limite_en_fusion_aucun_essai(self):
        self.activer()
        r = self.passage_fusion("feat/x", now=epoch(21, 0))   # repli 20:30 : moins de dix trains verts
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.appels_fin(), [])
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"], d["mode"]), ("attente", "depart-limite", "fusion"))
        self.assertIn("train_auto : attente : départ limite du train dépassé", r.sortie)

    def test_l_heure_limite_ne_s_applique_pas_en_observation(self):
        r = self.passage_fusion("feat/x", now=epoch(21, 0))
        self.assertEqual(self.appels_fin(), ["--essai feat/x"])
        self.assertEqual(self.dernier()["decision"], "observe")

    def test_avant_l_heure_limite_le_train_part(self):
        self.activer()
        self.passage_fusion("feat/x", now=epoch(20, 0))
        self.assertEqual(len(self.appels_train()), 1)

    def test_la_limite_atteinte_entre_l_essai_et_le_train_reel_arrete_le_passage(self):
        # revue 10.1, constat 1 (D9 point 3) : l'essai peut durer ; l'heure de départ la plus tardive est revérifiée juste avant le train réel.
        # Horloge fausse : elle avance d'une heure dès que l'essai est fini (le passage tourne dans ce processus, le faux finish est lancé pour de bon).
        self.activer()
        self.assurer("feat/x")
        self.lister("feat/x")
        essai_fini = []
        horloge_reelle, essai_reel = train_auto.Clock, train_auto.run_trial

        class HorlogeFausse(horloge_reelle):
            def now(self):
                return super().now() + (3600 if essai_fini else 0)

        def essai(ctx, noms):
            resultat = essai_reel(ctx, noms)
            essai_fini.append(True)
            return resultat

        env = self.environnement(epoch(20, 0), self.avec_notificateur())   # 20 h 00 : avant le repli de 20 h 30 ; après l'essai, 21 h 00
        courant = os.getcwd()
        os.chdir(self.t.lab)
        try:
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(train_auto, "Clock", HorlogeFausse), \
                    mock.patch.object(train_auto, "run_trial", essai), contextlib.redirect_stdout(io.StringIO()) as sortie:
                code = train_auto.main(["pass"])
        finally:
            os.chdir(courant)
        self.assertEqual(code, 0)
        self.assertEqual(self.appels_fin(), ["--essai feat/x"], "l'essai a eu lieu, aucun train réel")
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"], d["mode"], d["train"]), ("attente", "depart-limite", "fusion", None))
        self.assertIn("train_auto : attente : départ limite du train dépassé", sortie.getvalue())

    def test_un_desactiver_pendant_l_essai_empeche_le_train_reel(self):
        # revue 10.1, constat 3 : l'activation est relue juste avant le train réel. Le faux essai retire le fichier d'activation (ce que fait `desactiver`).
        self.activer()
        r = self.passage_fusion("feat/x", extra={"FAUX_RM": str(self.dossier_train() / "fusion-active")})
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.appels_fin(), ["--essai feat/x"], "aucun --auto réel")
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"], d["train"]), ("observe", "essai", None))

    def test_un_etat_illisible_apres_un_train_refuse_donne_une_attente_sans_essai_ni_train(self):
        # revue 10.1, constat 2 : l'état est écrit tout de suite après le train réel ; présent mais illisible, il donne `etat-illisible` en fusion
        self.activer()
        self.passage_fusion("feat/x", extra={"FAUX_CODE_AUTO": "70", "FAUX_SENS": "refuse"})
        self.assertEqual(len(self.etat_refuses()), 1)
        etat = self.dossier_train() / "etat.json"
        etat.write_text("{pas du json", encoding="utf-8")
        avant = self.appels_fin()
        r = self.passage_fusion("feat/x")
        self.assertEqual(self.appels_fin(), avant, "ni essai ni train")
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"], d["mode"]), ("attente", "etat-illisible", "fusion"))
        self.assertIn("train_auto : attente : état du train automatique illisible", r.sortie)
        self.assertEqual(etat.read_text(encoding="utf-8"), "{pas du json", "l'état illisible n'est pas réécrit : l'auteur le répare ou le retire")

    def test_un_journal_non_inscriptible_apres_un_train_refuse_laisse_l_etat_ecrit_apres_le_train(self):
        # revue de contrôle 10.2, point B (constat 2) : l'état avec l'ensemble refusé est écrit tout de suite après le train, avant le rapport et le journal. Le journal ne
        # s'écrit pas (OSError) : le passage rend 4, et l'ensemble refusé est quand même dans etat.json. Le passage tourne dans ce processus (comme le test du constat 1).
        self.activer()
        self.assurer("feat/x")
        self.lister("feat/x")
        env = self.environnement(epoch(), self.avec_notificateur({"FAUX_CODE_AUTO": "70", "FAUX_SENS": "refuse"}))
        courant = os.getcwd()
        os.chdir(self.t.lab)
        try:
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(train_auto, "append_journal", side_effect=OSError), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = train_auto.main(["pass"])
        finally:
            os.chdir(courant)
        self.assertEqual(code, 4)
        self.assertEqual(len(self.appels_train()), 1, "le train réel a eu lieu")
        refuses = self.etat_refuses()
        self.assertEqual(len(refuses), 1, "l'ensemble refusé est dans etat.json malgré le journal non écrit")
        self.assertEqual(refuses[0]["code"], 70)

    def test_en_observation_un_etat_illisible_reste_tel_quel(self):
        # revue de contrôle 10.2, point D (décision déléguée) : un état illisible n'est jamais réécrit, quel que soit le mode. En observation le passage observe quand même.
        self.dossier_train().mkdir(parents=True, exist_ok=True)
        etat = self.dossier_train() / "etat.json"
        etat.write_text("{pas du json", encoding="utf-8")
        r = self.passage_fusion("feat/x")
        self.assertEqual(r.code, 0, r.texte)
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"], d["mode"]), ("observe", "essai", "observation"))
        self.assertEqual(self.appels_train(), [])
        self.assertEqual(etat.read_text(encoding="utf-8"), "{pas du json", "l'état illisible n'est pas réécrit, même en observation")

    # --- D17 : le contrôle doctor du crochet bloque la fusion --------------------------------------------------------------------------
    def test_doctor_rouge_bloque_la_fusion_au_controle_7(self):
        self.activer()
        r = self.passage_fusion("feat/x", extra={"DOCTOR_FAUX": "ko"})
        self.assertEqual(self.appels_fin(), [])
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"], d["doctor"]), ("attente", "crochets-doctor", "rouge"))
        self.assertIn("train_auto : attente : contrôle doctor du crochet reference-transaction rouge ou absent", r.sortie)

    def test_doctor_absent_bloque_la_fusion(self):
        self.activer()
        self.t.casser_le_module("doctor.py", "print('{}')\n")   # le script ne parle pas du crochet : état absent
        self.passage_fusion("feat/x")
        self.assertEqual(self.dernier()["raison"], "crochets-doctor")
        self.assertEqual(self.appels_fin(), [])

    def test_doctor_rouge_est_seulement_note_en_observation(self):
        r = self.passage_fusion("feat/x", extra={"DOCTOR_FAUX": "ko"})
        d = self.dernier()
        self.assertEqual((d["decision"], d["doctor"], d["mode"]), ("observe", "rouge", "observation"))

    # --- l'arrêt ---------------------------------------------------------------------------------------------------------------------
    def test_l_arret_suspend_les_deux_modes(self):
        self.activer()
        self.assertEqual(self.auto("arret").code, 0)
        r = self.passage_fusion("feat/x")
        self.assertIn("train_auto : arrêté (arrêt d'urgence actif)", r.sortie)
        self.assertEqual(self.appels_fin(), [])


FAUX_REFUS_62 = """#!/bin/bash
echo "$*" >> "@ETAT@/appels-fin.txt"
mode=essai; names=()
for a in "$@"; do if [ "$a" = "--auto" ]; then mode=auto; elif [ "$a" != "--essai" ]; then names+=("$a"); fi; done
if [ "$mode" = essai ]; then
  for n in "${names[@]}"; do
    if [ "$n" = "feat/y" ]; then echo "finish_train : branche(s) refusée(s)"; echo "  - feat/y : worktree pas propre"; exit 62; fi
  done
  exit 0
fi
sommets=""
for n in "${names[@]}"; do s=$(@GIT@ -C @CONTENU@ rev-parse "refs/heads/$n"); sommets="${sommets:+$sommets,}$s"; done
"@PYTHON@" -I "$(dirname "$0")/train_record.py" append --code 0 --sens fusionne --mode auto --n "${#names[@]}" --sommets "$sommets" --sommet-train "cccccccccccccccccccccccccccccccccccccccc" \\
  --main-avant "1111111111111111111111111111111111111111" --main-apres "2222222222222222222222222222222222222222" --runner conteneur --duree-s 60 > /dev/null || exit 99
exit 0
"""


if __name__ == "__main__":
    unittest.main()
