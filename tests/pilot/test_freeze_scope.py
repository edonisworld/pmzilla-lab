"""Le gel ciblé du verrou de fin (change autonomous-trains-merge, design D18, tâches 6.1 à 6.3) : la liste que le train écrit dans le verrou
(finish_lock.sh), la règle unique `freeze_scope()` / `freezes()` de tools/finish_lock.py, son appel en ligne de commande par les lecteurs shell
(`refuse`) et le contrôle `pilot.py freeze --check`. Écrits avant le code ; le verrou n'est jamais modifié par un lecteur.

    python3 -W ignore -m unittest discover -s tests/pilot -p test_freeze_scope.py -q
"""
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aide_pilot as A  # noqa: E402
import finish_lock  # noqa: E402  (tools/ est dans sys.path par aide_pilot)

FINISH_LOCK_SH = A.RACINE / "tools" / "finish_lock.sh"
FINISH_LOCK_PY = A.RACINE / "tools" / "finish_lock.py"


def ecrire_liste(labo, branches=(), worktrees=(), fin=True, brut=None):
    """Pose la liste du train dans le verrou du faux laboratoire (même format que finish_lock.sh)."""
    lignes = brut if brut is not None else [f"B {b}" for b in branches] + [f"W {w}" for w in worktrees] + (["fin"] if fin else [])
    (labo.commun / A.NOM_LOCK / "gel").write_text("\n".join(lignes) + "\n", encoding="utf-8")


def contenu_verrou(labo):
    d = labo.commun / A.NOM_LOCK
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(d.iterdir())} if d.is_dir() else None


class EcritureDeLaListe(unittest.TestCase):
    """6.1 : le train enregistre ses branches et ses worktrees sous son jeton (finish_lock_record)."""

    def setUp(self):
        self.labo = A.Labo()

    def shell(self, script, entree=""):
        env = self.labo.env()
        env.pop("FINISH_LOCK_TOKEN", None)
        return subprocess.run(["bash", "-c", script], input=entree, capture_output=True, text=True, env=env, cwd=str(self.labo.ws))

    def test_la_liste_est_ecrite_sous_le_jeton_du_train(self):
        r = self.shell(f'. "{FINISH_LOCK_SH}"; finish_lock_acquire "{self.labo.commun}" train || exit 9; finish_lock_record; code=$?; '
                       'printf "%s\\n" "$code"; finish_lock_release',
                       "B feat/un\nW /tmp/wt-un\nB feat/deux\nW /tmp/wt-train-x\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "0")

    def test_la_liste_est_lue_par_freeze_scope(self):
        r = self.shell(f'. "{FINISH_LOCK_SH}"; finish_lock_acquire "{self.labo.commun}" train || exit 9; '
                       f'finish_lock_record; python3 -I -c "import sys; sys.path.insert(0, \'{A.RACINE / "tools"}\'); import finish_lock, json; '
                       f'print(json.dumps(finish_lock.freeze_scope(\'{self.labo.commun}\')))"',
                       "B feat/un\nW /tmp/wt-un\nB feat/deux\nW /tmp/wt-train-x\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        scope = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertTrue(scope["held"])
        self.assertTrue(scope["readable"])
        self.assertEqual(scope["branches"], ["feat/un", "feat/deux"])
        self.assertEqual(scope["worktrees"], ["/tmp/wt-un", "/tmp/wt-train-x"])

    def test_un_verrou_herite_n_est_pas_modifie(self):
        """Le script qui n'a pas pris le verrou (hérité par le jeton) n'y écrit aucune liste : lecteurs en échec fermé."""
        self.labo.poser_verrou()
        avant = contenu_verrou(self.labo)
        env = self.labo.env(FINISH_LOCK_TOKEN=A.JETON)
        r = subprocess.run(["bash", "-c", f'. "{FINISH_LOCK_SH}"; finish_lock_acquire "{self.labo.commun}" train || exit 9; finish_lock_record'],
                           input="B feat/un\n", capture_output=True, text=True, env=env, cwd=str(self.labo.ws))
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(contenu_verrou(self.labo), avant)

    def test_un_verrou_d_un_autre_jeton_n_est_pas_modifie(self):
        self.labo.poser_verrou()
        avant = contenu_verrou(self.labo)
        r = self.shell(f'. "{FINISH_LOCK_SH}"; finish_lock_record', "B feat/un\n")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(contenu_verrou(self.labo), avant)

    def test_le_train_ecrit_sa_liste_avant_toute_construction(self):
        """Lecture du script : record_freeze précède la garde du matin, l'état des références et la construction du train."""
        texte = (A.RACINE / "tools" / "finish_train.sh").read_text(encoding="utf-8")
        principal = texte[texte.index("\nmain() {"):]
        self.assertLess(principal.index("take_lock\n"), principal.index("record_freeze\n"))
        self.assertLess(principal.index("record_freeze\n"), principal.index("establish_base\n"))
        self.assertLess(principal.index("record_freeze\n"), principal.index("build_train\n"))
        self.assertIn("INTEG_NAME", texte[texte.index("integration_checks() {"):])


class RegleUnique(unittest.TestCase):
    """6.2 : freeze_scope() et freezes(), échec fermé sur un verrou sans liste lisible."""

    def setUp(self):
        self.labo = A.Labo()

    def test_sans_verrou(self):
        scope = finish_lock.freeze_scope(self.labo.commun)
        self.assertEqual((scope["held"], scope["branches"], scope["worktrees"]), (False, [], []))
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, ""))

    def test_verrou_perime_n_est_pas_tenu(self):
        self.labo.poser_verrou(pid=A.processus_mort())
        scope = finish_lock.freeze_scope(self.labo.commun)
        self.assertFalse(scope["held"])
        self.assertTrue(scope["stale"])
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, ""))

    def test_verrou_sans_liste_gele_tout(self):
        self.labo.poser_verrou()
        scope = finish_lock.freeze_scope(self.labo.commun)
        self.assertTrue(scope["held"])
        self.assertFalse(scope["readable"])
        for w in (self.labo.wt_propre, self.labo.ws, self.labo.run):
            self.assertIsNotNone(finish_lock.freezes(self.labo.commun, w, ""), str(w))

    def test_listes_mal_formees_gelent_tout(self):
        self.labo.poser_verrou()
        cas = {"sans la ligne fin": dict(branches=["feat/un"], worktrees=[str(self.labo.wt_sale)], fin=False),
               "ligne inconnue": dict(brut=["X feat/un", "fin"]),
               "vide": dict(brut=[]),
               "étiquette sans valeur": dict(brut=["W ", "fin"])}
        for nom, kw in cas.items():
            ecrire_liste(self.labo, **kw)
            scope = finish_lock.freeze_scope(self.labo.commun)
            self.assertFalse(scope["readable"], nom)
            self.assertIsNotNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, ""), nom)

    def test_un_worktree_liste_est_gele_les_autres_non(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, ["feat/demo-change"], [str(self.labo.wt_sale)])
        self.assertIsNotNone(finish_lock.freezes(self.labo.commun, self.labo.wt_sale, ""))
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, ""))
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_fusionne, ""))

    def test_branche_listee_sans_ligne_w_est_gelee(self):
        """Un worktree créé après coup sur une branche du train est gelé par sa branche courante, sans ligne W."""
        self.labo.poser_verrou()
        ecrire_liste(self.labo, [A.BRANCHE_PROPRE], [])
        self.assertIsNotNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, ""))
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_sale, ""), "branche non listée")
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, A.JETON), "jeton du train")

    def test_writes_ready_list_gele_tout_worktree_sauf_jeton_ou_verrou_perime(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, ["feat/demo-change"], [str(self.labo.wt_sale)])
        for w in (self.labo.wt_propre, self.labo.wt_sale, self.labo.wt_fusionne, self.labo.ws):
            self.assertIsNotNone(finish_lock.freezes(self.labo.commun, w, "", writes_ready_list=True), str(w))
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, ""), "sans le paramètre, hors liste : libre")
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, A.JETON, writes_ready_list=True), "jeton du train")

    def test_writes_ready_list_verrou_perime_ou_absent_libre(self):
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, "", writes_ready_list=True), "sans verrou")
        self.labo.poser_verrou(pid=A.processus_mort())
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, "", writes_ready_list=True), "verrou périmé")

    def test_liste_aux_octets_invalides_gele_tout(self):
        self.labo.poser_verrou()
        (self.labo.commun / A.NOM_LOCK / "gel").write_bytes(b"B feat/\xff\xfe\nfin\n")
        self.assertFalse(finish_lock.freeze_scope(self.labo.commun)["readable"])
        self.assertIsNotNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, ""))

    def test_le_jeton_du_train_n_est_jamais_gele(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, ["feat/demo-change"], [str(self.labo.wt_sale)])
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_sale, A.JETON, protected=True))
        self.assertIsNotNone(finish_lock.freezes(self.labo.commun, self.labo.wt_sale, "autre-jeton"))

    def test_main_et_dossier_d_execution_gelent_seulement_si_l_action_les_ecrit(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, [], [str(self.labo.wt_sale)])
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.ws, ""), "lecture ou passage qui n'écrit rien")
        self.assertIsNotNone(finish_lock.freezes(self.labo.commun, self.labo.ws, "", protected=True), "main")
        self.assertIsNotNone(finish_lock.freezes(self.labo.commun, self.labo.run, "", protected=True), "dossier d'exécution (tête détachée)")
        self.assertIsNone(finish_lock.freezes(self.labo.commun, self.labo.wt_propre, "", protected=True), "branche de travail hors liste")

    def test_chemin_non_canonique_dans_la_liste(self):
        self.labo.poser_verrou()
        lien = self.labo.tmp / "lien-vers-sale"
        lien.symlink_to(self.labo.wt_sale)
        ecrire_liste(self.labo, [], [str(lien)])
        self.assertIsNotNone(finish_lock.freezes(self.labo.commun, self.labo.wt_sale, ""))

    def test_le_verrou_n_est_jamais_modifie(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, ["feat/demo-change"], [str(self.labo.wt_sale)])
        avant = contenu_verrou(self.labo)
        finish_lock.freeze_scope(self.labo.commun)
        finish_lock.freezes(self.labo.commun, self.labo.wt_sale, "", protected=True)
        self.assertEqual(contenu_verrou(self.labo), avant)

    def test_le_gel_general_de_blocking_est_inchange(self):
        """pre-merge-commit et reference-transaction lisent toujours blocking() : un verrou vivant d'un autre jeton, quelle que soit la liste."""
        self.labo.poser_verrou()
        ecrire_liste(self.labo, [], [str(self.labo.wt_sale)])
        self.assertIsNotNone(finish_lock.blocking(self.labo.commun, ""))
        self.assertIsNone(finish_lock.blocking(self.labo.commun, A.JETON))


class LigneDeCommande(unittest.TestCase):
    """`python3 -I tools/finish_lock.py refuse` : la même règle pour le lanceur de tests et ci_local.sh."""

    def setUp(self):
        self.labo = A.Labo()

    def refuse(self, worktree, protected=False, jeton=None):
        env = self.labo.env()
        if jeton:
            env["FINISH_LOCK_TOKEN"] = jeton
        args = [sys.executable, "-I", str(FINISH_LOCK_PY), "refuse", "--common", str(self.labo.commun), "--worktree", str(worktree)]
        if protected:
            args.append("--protected")
        return subprocess.run(args, capture_output=True, text=True, env=env)

    def test_libre_sans_verrou(self):
        r = self.refuse(self.labo.wt_propre)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))

    def test_gele_sans_liste_et_dit_la_branche(self):
        self.labo.poser_verrou()
        r = self.refuse(self.labo.wt_propre)
        self.assertEqual((r.returncode, r.stdout.strip()), (4, "feat/autre"))

    def test_libre_hors_liste_gele_dans_la_liste(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, [], [str(self.labo.wt_sale)])
        self.assertEqual(self.refuse(self.labo.wt_propre).returncode, 0)
        self.assertEqual(self.refuse(self.labo.wt_sale).returncode, 4)

    def test_protege_gele_main(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, [], [str(self.labo.wt_sale)])
        self.assertEqual(self.refuse(self.labo.ws).returncode, 0)
        self.assertEqual(self.refuse(self.labo.ws, protected=True).returncode, 4)

    def test_jeton_du_train_libre(self):
        self.labo.poser_verrou()
        self.assertEqual(self.refuse(self.labo.wt_sale, protected=True, jeton=A.JETON).returncode, 0)

    def test_perime_dit_et_libre(self):
        self.labo.poser_verrou(pid=A.processus_mort())
        r = self.refuse(self.labo.wt_sale, protected=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "perime"))

    def test_usage(self):
        for args in ([], ["autre"], ["refuse"], ["refuse", "--common", "x"]):
            r = subprocess.run([sys.executable, "-I", str(FINISH_LOCK_PY), *args], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, str(args))


class ControlePilot(unittest.TestCase):
    """`pilot.py freeze --check` suit la même règle (D18 point 3, phrase de D19)."""

    def setUp(self):
        self.labo = A.Labo()

    def test_worktree_hors_liste_libre_avec_la_phrase_de_d19(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, ["feat/demo-change"], [str(self.labo.wt_sale), "/tmp/wt-train-x"])
        r = self.labo.pilot("freeze", "--check", cwd=self.labo.wt_propre)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pilot : fin en cours : 2 worktree(s) gelé(s), main, dossier d'exécution et liste prête", r.stdout)

    def test_main_et_dossier_d_execution_gelent_hors_liste_meme_regle_stricte_que_le_crochet(self):
        """R-20261107-3 : `freeze --check` rend 4 dans l'espace de travail sur main et dans une tête détachée (dossier d'exécution) pendant un train,
        même hors de la liste, avec la règle stricte de writes_protected() (celle du crochet et du lanceur) ; `--wait` attend tant que c'est 4."""
        self.labo.poser_verrou()
        ecrire_liste(self.labo, ["feat/demo-change"], [str(self.labo.wt_sale)])
        for cwd in (self.labo.ws, self.labo.run):
            r = self.labo.pilot("freeze", "--check", cwd=cwd)
            self.assertEqual(r.returncode, 4, f"{cwd} : {r.stdout}{r.stderr}")
        r = self.labo.pilot("freeze", "--wait", "1", cwd=self.labo.ws,
                            env=self.labo.env(PILOT_POLL_SECONDS="0.05", PILOT_WAIT_UNIT_SECONDS="0.3"))
        self.assertEqual(r.returncode, 4, "l'attente de main dure tant que le contrôle rend 4, puis rend 4 au délai")
        self.assertEqual(self.labo.pilot("freeze", "--check", cwd=self.labo.wt_propre).returncode, 0, "une branche hors liste reste libre")

    def test_worktree_liste_gele(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, ["feat/demo-change"], [str(self.labo.wt_sale)])
        r = self.labo.pilot("freeze", "--check", cwd=self.labo.wt_sale)
        self.assertEqual(r.returncode, 4)
        self.assertIn("pilot : fin de branche en cours (feat/autre, depuis", r.stderr)

    def test_sans_liste_lisible_gele_tout_appelant(self):
        self.labo.poser_verrou()
        for cwd in (self.labo.wt_propre, self.labo.ws):
            self.assertEqual(self.labo.pilot("freeze", "--check", cwd=cwd).returncode, 4, str(cwd))

    def test_jeton_du_train_libre(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, [], [str(self.labo.wt_sale)])
        r = self.labo.pilot("freeze", "--check", cwd=self.labo.wt_sale, env=self.labo.env(FINISH_LOCK_TOKEN=A.JETON))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_attente_hors_liste_ne_boucle_pas(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, [], [str(self.labo.wt_sale)])
        r = self.labo.pilot("freeze", "--wait", "1", cwd=self.labo.wt_propre,
                            env=self.labo.env(PILOT_POLL_SECONDS="0.05", PILOT_WAIT_UNIT_SECONDS="0.3"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_anglais(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, [], [str(self.labo.wt_sale)])
        r = self.labo.pilot("--language", "en", "freeze", "--check", cwd=self.labo.wt_propre)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pilot: finish running: 1 worktree(s) frozen", r.stdout)

    def test_le_verrou_n_est_pas_modifie(self):
        self.labo.poser_verrou()
        ecrire_liste(self.labo, [], [str(self.labo.wt_sale)])
        avant = contenu_verrou(self.labo)
        self.labo.pilot("freeze", "--check", cwd=self.labo.wt_propre)
        self.assertEqual(contenu_verrou(self.labo), avant)


if __name__ == "__main__":
    unittest.main()
