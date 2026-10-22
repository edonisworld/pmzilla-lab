"""`pilot.py status` (change multi-session-piloting, design D1, D2, D6, D11) : une ligne par worktree, depuis Git, hors ligne, sans
chemin, sans nom de fichier, sans numéro de processus, sans aucune écriture. Écrits avant le code.

    python3 -W ignore -m unittest discover -s tests/pilot -q
"""
import os
import re
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aide_pilot as A  # noqa: E402


def ligne_de(sortie, debut):
    lignes = [l for l in sortie.splitlines() if l.startswith(debut)]
    assert len(lignes) == 1, (debut, sortie)
    return lignes[0]


class Etat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.labo = A.Labo()

    def lancer(self, *args, **kw):
        return self.labo.pilot("status", *args, **kw)


class TroisWorktrees(Etat):
    def test_une_ligne_par_worktree(self):
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pilot : 3 worktree(s)", r.stdout.splitlines()[0])
        propre = ligne_de(r.stdout, "wt-propre")
        sale = ligne_de(r.stdout, "wt-sale")
        fusionne = ligne_de(r.stdout, "wt-fusionne")
        champs = propre.split(" | ")
        self.assertEqual(champs[0], "wt-propre")
        self.assertEqual(champs[1], A.BRANCHE_PROPRE)
        self.assertEqual(champs[2], "R-12")
        self.assertEqual(champs[3], "propre")
        retard = A.git(self.labo.ws, "rev-list", "--count", f"{A.BRANCHE_PROPRE}..main")
        self.assertEqual(champs[4], f"+1/-{retard} sur main")
        self.assertRegex(champs[5], r"^dernier commit il y a \d+ (min|h|j)$")
        self.assertIn("2 fichier(s) modifié(s)", sale)
        self.assertIn("fusionnée, à retirer", fusionne)
        self.assertNotIn("fusionnée", propre)
        self.assertNotIn("fusionnée", sale)

    def test_ligne_de_l_espace_de_travail(self):
        r = self.lancer()
        self.assertIn("espace de travail : main, propre", r.stdout)

    def test_dossier_d_execution_hors_de_la_liste(self):
        r = self.lancer()
        self.assertFalse([l for l in r.stdout.splitlines() if l.startswith("run ")], r.stdout)
        self.assertIn("dossier d'exécution : présent", r.stdout)

    def test_age_du_dernier_commit(self):
        maintenant = int(time.time())
        r = self.lancer(env=self.labo.env(PILOT_NOW=str(maintenant + 2 * 3600 + 30)))
        self.assertIn("dernier commit il y a 2 h", ligne_de(r.stdout, "wt-propre"))
        r = self.lancer(env=self.labo.env(PILOT_NOW=str(maintenant + 3 * 86400 + 60)))
        self.assertIn("dernier commit il y a 3 j", ligne_de(r.stdout, "wt-propre"))
        r = self.lancer(env=self.labo.env(PILOT_NOW=str(maintenant + 5 * 60 + 5)))
        self.assertIn("dernier commit il y a 5 min", ligne_de(r.stdout, "wt-propre"))

    def test_depuis_un_worktree_meme_liste(self):
        r1 = self.lancer()
        r2 = self.lancer(cwd=self.labo.wt_propre)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("pilot : 3 worktree(s)", r2.stdout)
        self.assertEqual(ligne_de(r1.stdout, "wt-sale"), ligne_de(r2.stdout, "wt-sale"))


class LienHorsLigne(Etat):
    def test_branche_de_cadrage_et_de_correctif(self):
        labo = A.Labo()
        A.git(labo.ws, "worktree", "add", "-q", "-b", "chore/r44-petit-correctif", str(labo.lab / "wt-corr"))
        r = labo.pilot("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(ligne_de(r.stdout, "wt-propre").split(" | ")[2], "R-12")
        self.assertEqual(ligne_de(r.stdout, "wt-corr").split(" | ")[2], "R-44")
        self.assertEqual(ligne_de(r.stdout, "wt-fusionne").split(" | ")[2], "R-7")

    def test_branche_de_change_connue_de_l_instantane(self):
        r = self.lancer()
        self.assertEqual(ligne_de(r.stdout, "wt-sale").split(" | ")[2], "change demo-change (R-30)")

    def test_sans_instantane_et_sans_gh(self):
        labo = A.Labo()
        labo.retirer_instantane()
        r = labo.pilot("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(ligne_de(r.stdout, "wt-sale").split(" | ")[2], "change demo-change")
        self.assertEqual(ligne_de(r.stdout, "wt-propre").split(" | ")[2], "R-12")
        self.assertEqual(labo.appels_gh(), "")

    def test_instantane_illisible(self):
        labo = A.Labo()
        (labo.donnees / "roadmap-cache.json").write_text("{pas du json", encoding="utf-8")
        r = labo.pilot("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(ligne_de(r.stdout, "wt-sale").split(" | ")[2], "change demo-change")

    def test_autre_branche_sans_lien(self):
        labo = A.Labo()
        A.git(labo.ws, "worktree", "add", "-q", "-b", "autre/sujet", str(labo.lab / "wt-autre"))
        r = labo.pilot("status")
        self.assertEqual(ligne_de(r.stdout, "wt-autre").split(" | ")[2], "—")

    def test_aucun_appel_reseau(self):
        labo = A.Labo()
        labo.pilot("status")
        self.assertEqual(labo.appels_gh(), "")


class ProcessusEtVerrou(Etat):
    def test_worktree_occupe(self):
        labo = A.Labo()
        labo.ecrire_lsof(f"p424242\nn{labo.wt_propre}/sous-dossier\np1\nn/\n")
        r = labo.pilot("status")
        self.assertIn("occupé", ligne_de(r.stdout, "wt-propre"))
        self.assertIn("libre", ligne_de(r.stdout, "wt-sale"))
        self.assertNotIn("424242", r.stdout)
        self.assertNotIn("424242", r.stderr)

    def test_listage_impossible(self):
        labo = A.Labo()
        for commande in ("false", "/nonexistent-command-for-pilot"):
            r = labo.pilot("status", env=labo.env(PILOT_LSOF=commande))
            self.assertEqual(r.returncode, 0, r.stderr)
            for debut in ("wt-propre", "wt-sale", "wt-fusionne"):
                self.assertIn("inconnu", ligne_de(r.stdout, debut))

    def test_ligne_du_verrou(self):
        labo = A.Labo()
        self.assertIn("fin en cours : aucune", labo.pilot("status").stdout)
        debut = int(time.time()) - 600
        labo.poser_verrou(debut=debut)
        self.assertIn(f"fin en cours : feat/autre depuis {labo.heure(debut)}", labo.pilot("status").stdout)
        labo.retirer_verrou()
        labo.poser_verrou(pid=A.processus_mort())
        self.assertIn("fin en cours : verrou périmé (feat/autre)", labo.pilot("status").stdout)

    def test_dossier_d_execution_absent(self):
        labo = A.Labo()
        A.git(labo.ws, "worktree", "remove", "--force", str(labo.run))
        self.assertIn("dossier d'exécution : absent", labo.pilot("status").stdout)


class RienNEstAffiche(Etat):
    def test_aucun_chemin_nom_de_fichier_ni_numero(self):
        labo = A.Labo()
        labo.ecrire_lsof(f"p{os.getpid() + 1}\nn{labo.wt_sale}\n")
        labo.poser_verrou()
        sortie = labo.pilot("status")
        texte = sortie.stdout + sortie.stderr
        for interdit in (str(labo.tmp), str(labo.tmp.parent), str(Path.home()), os.path.expanduser("~"), "sale-un", "sale-deux", "base.txt",
                         "propre.txt", str(os.getpid() + 1), A.JETON):
            self.assertNotIn(interdit, texte, interdit)
        self.assertNotIn("/Users/", texte)

    def test_rien_n_est_ecrit(self):
        labo = A.Labo()
        avant = labo.etat_git()
        index_avant = (labo.commun / "index").read_bytes() if (labo.commun / "index").exists() else b""
        for _ in range(2):
            r = labo.pilot("status")
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(labo.etat_git(), avant)
        self.assertFalse((labo.commun / A.NOM_LOCK).exists())
        self.assertEqual(labo.fichiers_notes(), [])
        self.assertEqual(index_avant, (labo.commun / "index").read_bytes() if (labo.commun / "index").exists() else b"")


class Sorties(Etat):
    def test_hors_du_depot(self):
        labo = A.Labo()
        dehors = labo.tmp / "hors-depot"
        dehors.mkdir()
        r = labo.pilot("status", cwd=dehors, env=labo.env(GIT_CEILING_DIRECTORIES=str(labo.tmp)))
        self.assertEqual(r.returncode, 3)
        self.assertIn("pilot : dépôt introuvable", r.stderr)

    def test_usage(self):
        self.assertEqual(self.labo.pilot().returncode, 2)
        self.assertEqual(self.labo.pilot("status", "--inconnue").returncode, 2)
        self.assertEqual(self.labo.pilot("inconnue").returncode, 2)

    def test_anglais(self):
        r = self.labo.pilot("--language", "en", "status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pilot: 3 worktree(s)", r.stdout.splitlines()[0])
        self.assertNotIn("fichier(s)", r.stdout)
        self.assertRegex(r.stdout, r"no finish running|finish running|stale")


class NoteDansLaLigne(Etat):
    def test_note_affichee_sur_la_ligne(self):
        labo = A.Labo()
        r = labo.pilot("note", A.BRANCHE_PROPRE, "en attente de revue")
        self.assertEqual(r.returncode, 0, r.stderr)
        champs = ligne_de(labo.pilot("status").stdout, "wt-propre").split(" | ")
        self.assertEqual(champs[-1], "note : en attente de revue")

    def test_note_d_une_branche_sans_worktree_ignoree(self):
        labo = A.Labo()
        labo.pilot("note", A.BRANCHE_FUSIONNEE, "prête pour la fin")
        A.git(labo.ws, "worktree", "remove", "--force", str(labo.wt_fusionne))
        r = labo.pilot("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("prête pour la fin", r.stdout)
        self.assertIn("pilot : 2 worktree(s)", r.stdout)


class Texte(unittest.TestCase):
    def test_pas_d_ecriture_git_ni_reseau_ni_lancement_de_script(self):
        """Le texte de l'outil, hors commentaires et docstrings, ne contient aucune commande interdite (exigence « n'écrit que ses notes »)."""
        import io
        import tokenize
        interdits = [r"['\"]commit['\"]", r"['\"]merge['\"]", r"['\"]push['\"]", r"['\"]fetch['\"]", r"['\"]pull['\"]",
                     r"['\"]remove['\"]", r"['\"]prune['\"]", r"['\"]branch['\"]\s*,\s*['\"]-[dD]['\"]", r"['\"]update-ref['\"]",
                     r"['\"]config['\"]", r"['\"]add['\"]", r"['\"]checkout['\"]", r"['\"]switch['\"]", r"['\"]reset['\"]",
                     r"['\"]gh['\"]", r"finish_worktree", r"finish_branch", r"run_all", r"rmtree", r"rmdir", r"os\.mkdir\(.*LOCK",
                     r"requests|urllib\.request|socket|http\.client"]
        for source in A.SOURCES:
            self.assertTrue(source.exists(), source)
            texte = source.read_text(encoding="utf-8")
            sans = []
            precedent = None
            for jeton in tokenize.generate_tokens(io.StringIO(texte).readline):
                if jeton.type == tokenize.COMMENT:
                    continue
                if jeton.type == tokenize.STRING and (precedent in (None, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.NL)):
                    precedent = jeton.type
                    continue   # docstring
                precedent = jeton.type
                sans.append(jeton.string)
            code = " ".join(sans)
            for motif in interdits:
                self.assertIsNone(re.search(motif, code), f"{source.name} : {motif}")


if __name__ == "__main__":
    unittest.main()
