"""R-20261110-06 : à la main, tools/outils_figes/rafraichir.sh refuse la copie (code 5, message fixe sans chemin, note du retard gardée, aucune copie) si l'espace de
travail n'est pas sur la branche main, si `git fetch` échoue ou si HEAD diffère de origin/main après lui, ou si un fichier de liste.txt a une modification non commitée.
Dépôt factice et « origin » local (dépôt nu) dans un dossier temporaire, sans réseau. R-20261110-07 : le dossier de préparation de la fin d'un train (sans .git) se
distingue par le troisième argument `--extrait-du-train` (voir test_rafraichir_note_retard.py) ; sans lui, un dossier sans .git est refusé (code 5) ; avec lui, un dossier
avec .git est refusé ; tout autre troisième argument : code 2. R-20261110-08 : liste.txt et le script sont contrôlés comme les fichiers de la liste, chaque fichier doit être
suivi par Git (fichier ignoré refusé, status.showUntrackedFiles sans effet), l'environnement Git hérité est effacé, un .git qui n'est pas un dossier est refusé.
Remplace : rien. Retrait : avec le bac à sable (R-20261110-06, -07, -08).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SOURCE = RACINE / "tools" / "outils_figes"

MESSAGES = {
    "branche": "outils figés : refus : l'espace de travail n'est pas sur la branche main, rien n'est copié",
    "fetch": "outils figés : refus : git fetch en échec, rien n'est copié",
    "tete": "outils figés : refus : HEAD diffère de origin/main, rien n'est copié",
    "modifie": "outils figés : refus : un fichier de la liste a une modification non commitée, rien n'est copié",
    "non_suivi": "outils figés : refus : un fichier de la liste n'est pas suivi par Git, rien n'est copié",
    "git_pas_dossier": "outils figés : refus : le .git du dépôt n'est pas un dossier, rien n'est copié",
    "sans_git": "outils figés : refus : le dépôt n'a pas de .git, rien n'est copié",
    "avec_git": "outils figés : refus : le dossier extrait du train ne doit pas avoir de .git, rien n'est copié",
}


class ControlesGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.env_git = {"PATH": "/usr/bin:/bin", "HOME": str(self.base), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_NOSYSTEM": "1"}
        self.origin = self.base / "origin.git"
        self.depot = self.base / "depot"
        self.git("init", "-q", "--bare", "-b", "main", str(self.origin), cwd=self.base)
        self.git("init", "-q", "-b", "main", str(self.depot), cwd=self.base)
        self.git("remote", "add", "origin", str(self.origin))
        self.ecrire(self.depot, "tools/outils_figes/liste.txt", "E a.sh\nC tools/dep.py\n")
        self.ecrire(self.depot, "tools/outils_figes/a.sh", "enveloppe v1\n")
        self.ecrire(self.depot, "tools/outils_figes/rafraichir.sh", "# copie du script, suivie comme dans le dépôt réel\n")   # R-20261110-08 : contrôlé comme la liste
        self.ecrire(self.depot, "tools/dep.py", "dependance v1\n")
        self.ecrire(self.depot, "tools/hors_liste.py", "hors liste v1\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "depart")
        self.git("push", "-q", "origin", "main")
        self.dest = self.base / "outils-figes"
        self.dest.mkdir()
        (self.dest / "dossiers.conf").write_text("maison=/m\n", encoding="utf-8")
        self.note = self.base / "outils-figes-en-retard"
        self.note.write_text("a" * 40 + " cd /x && bash tools/outils_figes/rafraichir.sh /x /y\n", encoding="utf-8")

    def git(self, *args, cwd=None):
        r = subprocess.run(["git", *args], cwd=cwd or self.depot, env=self.env_git, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"git {args} : {r.stderr}")
        return r.stdout

    @staticmethod
    def ecrire(racine, chemin, texte):
        fichier = racine / chemin
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(texte, encoding="utf-8")

    def lancer(self):
        return subprocess.run(["/bin/bash", str(SOURCE / "rafraichir.sh"), str(self.depot), str(self.dest)], capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin", "HOME": str(self.base)})

    def lancer_avec(self, depot, *supplement):
        return subprocess.run(["/bin/bash", str(SOURCE / "rafraichir.sh"), str(depot), str(self.dest), *supplement], capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin", "HOME": str(self.base)})

    def image_sans_git(self):
        """Le dossier de préparation d'un train : les fichiers de la liste extraits du commit, sans .git."""
        image = self.base / "image"
        for chemin in ("tools/outils_figes/liste.txt", "tools/outils_figes/a.sh", "tools/dep.py"):
            self.ecrire(image, chemin, (self.depot / chemin).read_text(encoding="utf-8"))
        return image

    def test_sans_argument_un_dossier_sans_git_est_refuse(self):
        r = self.lancer_avec(self.image_sans_git())
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertEqual(r.stderr.strip(), MESSAGES["sans_git"])
        self.assertNotIn(str(self.base), r.stderr)
        self.assertTrue(self.note.exists())
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["dossiers.conf"])

    def test_extrait_du_train_sur_un_dossier_sans_git_copie_sans_controles_git(self):
        r = self.lancer_avec(self.image_sans_git(), "--extrait-du-train")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.dest / "a.sh").read_text(encoding="utf-8"), "enveloppe v1\n")
        self.assertEqual((self.dest / "copie" / "tools" / "dep.py").read_text(encoding="utf-8"), "dependance v1\n")
        self.assertFalse(self.note.exists())

    def test_extrait_du_train_sur_un_dossier_avec_git_est_refuse(self):
        r = self.lancer_avec(self.depot, "--extrait-du-train")
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertEqual(r.stderr.strip(), MESSAGES["avec_git"])
        self.assertNotIn(str(self.base), r.stderr)
        self.assertTrue(self.note.exists())
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["dossiers.conf"])

    def test_troisieme_argument_inconnu_code_2(self):
        for supplement in (("--autre",), ("--extrait-du-train ",), ("",), ("--extrait-du-train", "--extrait-du-train")):
            with self.subTest(supplement=supplement):
                r = self.lancer_avec(self.depot, *supplement)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertTrue(self.note.exists())
                self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["dossiers.conf"])

    def refus(self, cle):
        r = self.lancer()
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertEqual(r.stderr.strip(), MESSAGES[cle])            # message fixe
        self.assertNotIn(str(self.base), r.stderr)                   # sans chemin
        self.assertTrue(self.note.exists())                          # la note du retard est gardée
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["dossiers.conf"])   # aucune copie, aucun relevé

    def test_pas_sur_main(self):
        self.git("checkout", "-q", "-b", "autre")
        self.refus("branche")

    def test_tete_detachee(self):
        self.git("checkout", "-q", "--detach")
        self.refus("branche")

    def test_fetch_en_echec(self):
        self.git("remote", "set-url", "origin", str(self.base / "inexistant.git"))
        self.refus("fetch")

    def test_head_different_de_origin_main(self):
        autre = self.base / "autre-clone"
        self.git("clone", "-q", str(self.origin), str(autre), cwd=self.base)
        self.ecrire(autre, "tools/dep.py", "dependance v2\n")
        self.git("add", ".", cwd=autre)
        self.git("commit", "-q", "-m", "avance", cwd=autre)
        self.git("push", "-q", "origin", "main", cwd=autre)
        self.refus("tete")                                           # le fetch du script ramène origin/main en avance sur HEAD

    def test_commit_local_non_pousse(self):
        self.ecrire(self.depot, "tools/dep.py", "dependance v2\n")
        self.git("commit", "-q", "-a", "-m", "local")
        self.refus("tete")

    def test_fichier_de_la_liste_modifie_non_indexe(self):
        self.ecrire(self.depot, "tools/dep.py", "dependance modifiee\n")
        self.refus("modifie")

    def test_fichier_de_la_liste_modifie_indexe(self):
        self.ecrire(self.depot, "tools/outils_figes/a.sh", "enveloppe modifiee\n")
        self.git("add", "tools/outils_figes/a.sh")
        self.refus("modifie")

    def test_liste_modifiee_non_commitee_est_refusee(self):
        # R-20261110-08 : la liste elle-même est contrôlée comme les fichiers qu'elle nomme.
        self.ecrire(self.depot, "tools/outils_figes/liste.txt", "E a.sh\nC tools/dep.py\n# ajout non commité\n")
        self.refus("modifie")

    def test_script_modifie_non_commite_est_refuse(self):
        self.ecrire(self.depot, "tools/outils_figes/rafraichir.sh", "# modifié\n")
        self.refus("modifie")

    def test_modification_indexee_puis_annulee_dans_l_arbre_est_refusee(self):
        self.ecrire(self.depot, "tools/dep.py", "dependance indexee\n")
        self.git("add", "tools/dep.py")
        self.ecrire(self.depot, "tools/dep.py", "dependance v1\n")   # l'arbre est revenu à HEAD, l'index non
        self.refus("modifie")

    def ajouter_a_la_liste_un_fichier_non_suivi(self, ignore):
        """La liste (commitée et poussée) nomme tools/ignore.py, qui existe dans l'arbre sans être suivi : ignoré par .git/info/exclude, ou simplement non suivi."""
        self.ecrire(self.depot, "tools/outils_figes/liste.txt", "E a.sh\nC tools/dep.py\nC tools/ignore.py\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "liste")
        self.git("push", "-q", "origin", "main")
        self.ecrire(self.depot, "tools/ignore.py", "fichier non suivi\n")
        if ignore:
            self.ecrire(self.depot, ".git/info/exclude", "tools/ignore.py\n")

    def test_fichier_liste_ignore_et_non_suivi_est_refuse(self):
        self.ajouter_a_la_liste_un_fichier_non_suivi(ignore=True)
        self.assertEqual(self.git("status", "--porcelain").strip(), "")   # `git status` ne le montre pas : seul le contrôle de suivi l'arrête
        self.refus("non_suivi")

    def test_show_untracked_files_no_ne_change_rien(self):
        self.ajouter_a_la_liste_un_fichier_non_suivi(ignore=False)
        self.git("config", "status.showUntrackedFiles", "no")
        self.assertEqual(self.git("status", "--porcelain").strip(), "")
        self.refus("non_suivi")

    def test_git_dir_herite_vers_un_autre_depot_propre_ne_fait_pas_accepter_un_arbre_sale(self):
        autre = self.base / "autre-clone"
        self.git("clone", "-q", str(self.origin), str(autre), cwd=self.base)
        self.ecrire(self.depot, "tools/dep.py", "dependance modifiee\n")
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.base), "GIT_DIR": str(autre / ".git"), "GIT_WORK_TREE": str(autre)}
        r = subprocess.run(["/bin/bash", str(SOURCE / "rafraichir.sh"), str(self.depot), str(self.dest)], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertEqual(r.stderr.strip(), MESSAGES["modifie"])
        self.assertTrue(self.note.exists())
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["dossiers.conf"])

    def test_git_fichier_vers_un_autre_depot_est_refuse(self):
        autre = self.base / "autre-clone"
        self.git("clone", "-q", str(self.origin), str(autre), cwd=self.base)
        faux = self.base / "faux"
        for chemin in ("tools/outils_figes/liste.txt", "tools/outils_figes/a.sh", "tools/outils_figes/rafraichir.sh", "tools/dep.py"):
            self.ecrire(faux, chemin, (self.depot / chemin).read_text(encoding="utf-8"))
        (faux / ".git").write_text(f"gitdir: {autre / '.git'}\n", encoding="utf-8")   # propre aux yeux de Git, qui juge l'autre dépôt
        r = self.lancer_avec(faux)
        self.assertEqual(r.returncode, 5, r.stderr)
        self.assertEqual(r.stderr.strip(), MESSAGES["git_pas_dossier"])
        self.assertNotIn(str(self.base), r.stderr)
        self.assertTrue(self.note.exists())
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["dossiers.conf"])

    def test_fichier_hors_liste_modifie_ne_bloque_pas(self):
        self.ecrire(self.depot, "tools/hors_liste.py", "hors liste modifie\n")
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_cas_qui_passe_copie_et_retire_la_note(self):
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.dest / "a.sh").read_text(encoding="utf-8"), "enveloppe v1\n")
        self.assertEqual((self.dest / "copie" / "tools" / "dep.py").read_text(encoding="utf-8"), "dependance v1\n")
        self.assertTrue((self.dest / "empreintes.sha256").is_file())
        self.assertFalse(self.note.exists())


if __name__ == "__main__":
    unittest.main()
