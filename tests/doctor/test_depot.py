"""Contrôles jira, branches et run-worktree (tâche 3.4) : date d'expiration seulement, dernier commit pour l'inactivité, aucune commande Git qui change quelque chose."""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import DOCTOR, Labo, git  # noqa: E402

MODIFIANT = ("branch -d", "branch -D", "worktree remove", "worktree prune", "worktree add", "checkout", "switch", "reset", "merge", "pull", "fetch",
             "push", "gc", "clean", "stash", "commit", "rebase")


def appels_git_modifiants(appels):
    return [a for a in appels if a.startswith("git ") and any(f" {m}" in a.replace("merge-base", "lecture") for m in MODIFIANT)]


class Jira(Labo):
    def test_date_lointaine(self):
        niveau, entree, _ = self.niveau("jira")
        self.assertEqual(niveau, "ok")

    def test_date_absente_ignoree_et_code_inchange(self):
        self.ecrire_flux(None)
        niveau, entree, p = self.niveau("jira")
        self.assertEqual((niveau, entree["reason"]["key"]), ("skipped", "unknown"))
        self.assertEqual(p.returncode, 0)
        self.assertIn("jira: skipped: expiry date unknown", self.lancer("--language", "en").stdout)

    def test_fichier_de_reglages_absent_ignore(self):
        self.flux.unlink()
        self.assertEqual(self.niveau("jira")[1]["reason"]["key"], "unknown")

    def test_date_depassee_hier(self):
        self.ecrire_flux("2026-10-13")
        niveau, entree, p = self.niveau("jira")
        self.assertEqual((niveau, entree["reason"]["key"]), ("problem", "expired"))
        self.assertEqual(p.returncode, 1)
        self.assertEqual([a for a in self.appels() if a.split(" ")[0] in ("security", "INTERDIT")], [])

    def test_date_du_jour_n_est_pas_depassee(self):
        self.ecrire_flux("2026-10-14")
        self.assertEqual(self.niveau("jira")[0], "warning")

    def test_dans_la_periode_d_avertissement(self):
        self.ecrire_flux("2026-10-20")
        niveau, entree, p = self.niveau("jira")
        self.assertEqual((niveau, entree["reason"]["key"], entree["reason"]["counts"]), ("warning", "expiring", {"days": 6}))
        self.assertEqual(p.returncode, 0)

    def test_repli_de_30_jours_quand_la_periode_est_absente(self):
        self.ecrire_flux("2026-11-08")   # dans 25 jours : sous 30, au-dessus de l'ancien repli de 14
        niveau, entree, _ = self.niveau("jira")
        self.assertEqual((niveau, entree["reason"]["key"], entree["reason"]["counts"]), ("warning", "expiring", {"days": 25}))
        self.ecrire_flux("2026-11-20")   # dans 37 jours
        self.assertEqual(self.niveau("jira")[0], "ok")

    def test_periode_de_la_cle_du_fichier_prioritaire_sur_le_repli(self):
        self.ecrire_flux("2026-11-08", extra="jira_token_warning_days: 10\n")
        self.assertEqual(self.niveau("jira")[0], "ok")

    def test_periode_reglable(self):
        self.ecrire_flux("2026-10-20")
        self.assertEqual(self.niveau("jira", env={"DOCTOR_JIRA_WARN_DAYS": "3"})[0], "ok")

    def test_date_mal_formee(self):
        self.ecrire_flux("pas-une-date")
        niveau, entree, _ = self.niveau("jira")
        self.assertEqual((niveau, entree["reason"]["key"]), ("warning", "unreadable"))

    def test_fichier_illisible(self):
        self.flux.write_text("jira_token_expires: [\n", encoding="utf-8")
        self.assertEqual(self.niveau("jira")[0], "warning")

    def test_aucune_valeur_du_fichier_ne_sort(self):
        self.ecrire_flux("2027-06-01", extra="jira_cloud_id: identifiant-secret-xyz\n")
        for args in ((), ("--json",)):
            p = self.lancer(*args)
            self.assertNotIn("identifiant-secret-xyz", p.stdout)
            self.assertNotIn("2027-06-01", p.stdout)

    def test_ni_trousseau_ni_jeton(self):
        self.lancer()
        self.assertEqual([a for a in self.appels() if a.split(" ")[0] in ("security", "INTERDIT")], [])


class Branches(Labo):
    def test_depot_propre(self):
        self.assertEqual(self.niveau("branches")[0], "ok")

    def test_worktree_fusionne(self):
        self.ajouter_branche("feat/fusionnee", fusionnee=True, worktree=True)
        niveau, entree, p = self.niveau("branches")
        self.assertEqual(niveau, "warning")
        self.assertEqual(entree["reason"]["counts"]["merged_worktrees"], 1)
        self.assertEqual(p.returncode, 0)
        self.assertIn("feat/fusionnee", self.lancer().stdout)

    def test_worktree_inactif_depuis_le_dernier_commit(self):
        self.ajouter_branche("feat/ancienne", jour="2026-09-20", worktree=True)
        niveau, entree, _ = self.niveau("branches")
        self.assertEqual((niveau, entree["reason"]["counts"]["stale_worktrees"]), ("warning", 1))
        self.assertEqual(entree["reason"]["counts"]["merged_worktrees"], 0)

    def test_worktree_recent_non_fusionne_est_sain(self):
        self.ajouter_branche("feat/en-cours", jour="2026-10-13", worktree=True)
        self.assertEqual(self.niveau("branches")[0], "ok")

    def test_seuil_d_inactivite_reglable(self):
        self.ajouter_branche("feat/ancienne", jour="2026-09-20", worktree=True)
        self.assertEqual(self.niveau("branches", env={"DOCTOR_STALE_DAYS": "30"})[0], "ok")

    def test_branche_locale_fusionnee_non_supprimee(self):
        self.ajouter_branche("fix/finie", fusionnee=True)
        niveau, entree, _ = self.niveau("branches")
        self.assertEqual((niveau, entree["reason"]["counts"]["merged_branches"]), ("warning", 1))
        self.assertIn("fix/finie", self.lancer("--language", "en").stdout)
        self.assertNotIn("fix/finie", json.dumps(entree))
        self.assertNotIn("fix/finie", self.lancer("--json").stdout)

    def test_worktree_a_elaguer(self):
        dossier = self.ajouter_branche("feat/disparue", jour="2026-10-13", worktree=True)
        shutil.rmtree(dossier)
        niveau, entree, _ = self.niveau("branches")
        self.assertEqual((niveau, entree["reason"]["counts"]["prunable"]), ("warning", 1))
        self.assertEqual(appels_git_modifiants(self.appels()), [])

    def test_jamais_un_probleme(self):
        for i in range(4):
            self.ajouter_branche(f"feat/vieille-{i}", fusionnee=True, worktree=True)
        niveau, _, p = self.niveau("branches")
        self.assertEqual(niveau, "warning")
        self.assertEqual(p.returncode, 0)

    def test_rien_n_est_supprime(self):
        self.ajouter_branche("feat/fusionnee", fusionnee=True, worktree=True)
        self.ajouter_branche("fix/finie", fusionnee=True)
        avant = git(self.principal, "branch", "--list").stdout
        self.lancer()
        self.lancer("--record")
        self.assertEqual(appels_git_modifiants(self.appels()), [])
        self.assertEqual(git(self.principal, "branch", "--list").stdout, avant)
        self.assertTrue((self.base / "wt-feat-fusionnee").is_dir())


class WorktreeDExecution(Labo):
    def cle(self, **env):
        niveau, entree, p = self.niveau("run-worktree", env=env)
        return niveau, entree["reason"]["key"], p

    def test_detache_au_sommet_de_main(self):
        self.assertEqual(self.cle()[:2], ("ok", "ok"))

    def test_en_retard_sur_main(self):
        self.avancer_main()
        avant = git(self.run, "rev-parse", "HEAD").stdout
        niveau, cle, p = self.cle()
        self.assertEqual((niveau, cle, p.returncode), ("warning", "behind", 0))
        self.assertEqual(git(self.run, "rev-parse", "HEAD").stdout, avant)
        self.assertEqual(appels_git_modifiants(self.appels()), [])

    def test_sur_une_branche(self):
        git(self.run, "checkout", "-q", "-b", "feat/x")
        niveau, cle, p = self.cle()
        self.assertEqual((niveau, cle, p.returncode), ("problem", "wrong_branch", 1))

    def test_appels_git_sans_changement(self):
        git(self.run, "checkout", "-q", "-b", "feat/x")
        self.appels_avant = len(self.appels())
        self.cle()
        self.assertEqual(appels_git_modifiants(self.appels()[self.appels_avant:]), [])

    def test_hors_de_l_historique_de_main(self):
        (self.run / "c.txt").write_text("c", encoding="utf-8")
        git(self.run, "add", "c.txt")
        git(self.run, "commit", "-q", "-m", "ailleurs")
        self.assertEqual(self.cle()[:2], ("problem", "off_history"))

    def test_changement_local(self):
        (self.run / "a.txt").write_text("modifié", encoding="utf-8")
        niveau, cle, p = self.cle()
        self.assertEqual((niveau, cle, p.returncode), ("problem", "dirty", 1))
        self.assertEqual(appels_git_modifiants(self.appels()), [])

    def test_changement_local_et_en_retard(self):
        self.avancer_main()
        (self.run / "a.txt").write_text("modifié", encoding="utf-8")
        self.assertEqual(self.cle()[:2], ("problem", "dirty"))

    def test_fichier_non_suivi_ne_compte_pas(self):
        (self.run / "cache.tmp").write_text("x", encoding="utf-8")
        self.assertEqual(self.cle()[:2], ("ok", "ok"))

    def test_dossier_introuvable(self):
        self.assertEqual(self.cle(DOCTOR_RUN_WORKTREE=self.base / "absent")[:2], ("problem", "missing"))

    def test_dossier_par_defaut_absent(self):
        shutil.rmtree(self.run)
        self.assertEqual(self.cle()[:2], ("problem", "missing"))

    def test_reglage_pmzilla_lab_run(self):
        autre = self.base / "autre-run"
        git(self.principal, "worktree", "add", "-q", "--detach", str(autre), "main")
        (autre / "a.txt").write_text("modifié", encoding="utf-8")
        self.assertEqual(self.cle(PMZILLA_LAB_RUN=autre)[:2], ("problem", "dirty"))
        self.assertEqual(self.cle(PMZILLA_LAB_RUN=autre, DOCTOR_RUN_WORKTREE=self.run)[:2], ("ok", "ok"))

    def test_dossier_qui_n_est_pas_un_depot(self):
        vide = self.base / "vide"
        vide.mkdir()
        self.assertEqual(self.cle(DOCTOR_RUN_WORKTREE=vide)[:2], ("problem", "missing"))

    def test_branches_ignore_le_dossier_d_execution(self):
        self.avancer_main(jour="2026-09-01")
        git(self.run, "checkout", "-q", "--detach", "main~1")
        niveau, entree, _ = self.niveau("branches")
        self.assertEqual(niveau, "ok")
        self.assertNotIn("run", self.lancer().stdout.split("branches")[1].splitlines()[0].split(":", 2)[-1])

    def test_branches_ignore_le_dossier_d_execution_meme_sur_une_branche(self):
        autre = self.base / "autre-run"
        git(self.principal, "worktree", "add", "-q", "-b", "run/ancienne", str(autre), "main")
        (autre / "z.txt").write_text("z", encoding="utf-8")
        git(autre, "add", "z.txt")
        git(autre, "commit", "-q", "-m", "z", env={"GIT_COMMITTER_DATE": "2026-09-01T08:00:00", "GIT_AUTHOR_DATE": "2026-09-01T08:00:00"})
        self.assertEqual(self.niveau("branches")[0], "warning")
        self.assertEqual(self.niveau("branches", env={"PMZILLA_LAB_RUN": autre})[0], "ok")


class ContenuDuDepotDeDeveloppement(Labo):
    def test_flux_cherche_dans_la_copie_principale(self):
        """Lancé depuis le dossier d'exécution, le doctor trouve Flux-Lab/flux.yaml du dépôt de développement (PMZILLA_LAB_WORKSPACE)."""
        (self.principal / "Flux-Lab").mkdir()
        (self.principal / "Flux-Lab" / "flux.yaml").write_text("jira_token_expires: 2020-01-01\n", encoding="utf-8")
        env = self.environnement()
        env.pop("DOCTOR_FLUX")
        sortie = subprocess.run([sys.executable, str(DOCTOR), "--json"], capture_output=True, text=True, env=env, cwd=str(self.base), timeout=60)
        jira = [c for c in json.loads(sortie.stdout)["checks"] if c["id"] == "jira"][0]
        self.assertEqual((jira["level"], jira["reason"]["key"]), ("problem", "expired"))


if __name__ == "__main__":
    unittest.main()
