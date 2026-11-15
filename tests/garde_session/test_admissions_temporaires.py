"""Garde de session, le chemin absolu de la forme des enveloppes et le refus de `; true` (bash-sandbox-n2, tâche 19.5 puis 21.2, design D13 ; R-20261111-26,
-30, -48).

 - le chemin absolu EXACT du dossier personnel (celui de la base des comptes), à la place de `~` : depuis R-20261111-48 (DN2-Q1 (a)) ce n'est plus une
   admission temporaire, c'est la forme unique ; admis pour ce chemin seul ; refusé pour un autre chemin absolu, un lien, `..`, `/./` et `//` (les tests de
   cette classe sont inchangés, seule leur portée est dite ici) ;
 - le suffixe exactement `; true` (R-20261111-30) : admis pendant la sonde pour que le cas X9 mesure la vraie comparaison de Claude Code ; la tâche 21.2 a
   retiré cette admission (le suffixe est refusé comme tout autre suffixe, opérateur ou mot ; ces tests sont devenus des tests de refus). Remplace : l'admission
   temporaire de `; true`. Retrait : permanent tant que la garde refuse tout suffixe. La forme `~` de ces tests est devenue la forme du chemin absolu (R-20261111-48).

    uv run tools/pilot.py freeze --check && bash tests/run_all.sh garde_session
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Arbre, g  # noqa: E402

CHEMIN = ".pmzilla-lab/outils-figes/gh_issue.sh"


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Arbre()
        os.symlink(cls.a.home, os.path.join(cls.a.tmp, "lien-vers-maison"))
        cls.lien = os.path.join(cls.a.tmp, "lien-vers-maison")

    @classmethod
    def tearDownClass(cls):
        cls.a.fermer()

    def forme_absolue(self, home=None, chemin=CHEMIN, suite=" view 742"):
        return f"/bin/bash --noprofile --norc -p {home or self.a.home}/{chemin}{suite}"

    def refuse(self, commandes):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertEqual(self.a.cle(commande, self.a.wt), "E-enveloppe")

    def passe(self, commandes):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertIsNone(self.a.cle(commande, self.a.wt))


class CheminAbsoluDuDossierPersonnel(Base):
    def test_le_chemin_absolu_exact_est_admis_pour_les_quatre_enveloppes(self):
        self.passe([self.forme_absolue(chemin=f".pmzilla-lab/outils-figes/{nom}.sh") for nom in ("ci_local", "gh_issue", "flow_views", "worktree")])

    def test_le_chemin_absolu_exact_est_admis_avec_des_arguments(self):
        self.passe((self.forme_absolue(suite=" run --travail --worktree ~/PMZilla-Lab/worktrees/wt-a une_suite"), self.forme_absolue(suite=" status R-1 'In progress'")))

    def test_un_autre_chemin_absolu_est_refuse(self):
        self.refuse((self.forme_absolue(home="/Users/quelquun"), self.forme_absolue(home=self.a.tmp), self.forme_absolue(home=os.path.dirname(self.a.home)),
                     self.forme_absolue(home=self.a.home + "x")))

    def test_un_lien_est_refuse(self):
        self.refuse((self.forme_absolue(home=self.lien),))

    def test_point_point_point_barre_point_et_double_barre_sont_refuses(self):
        h = self.a.home
        self.refuse((self.forme_absolue(home=h + "/.."), self.forme_absolue(home=h + "/../" + os.path.basename(h)),
                     f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab/outils-figes/../outils-figes/gh_issue.sh list",
                     f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab/outils-figes/./gh_issue.sh list",
                     f"/bin/bash --noprofile --norc -p {h}/./.pmzilla-lab/outils-figes/gh_issue.sh list",
                     f"/bin/bash --noprofile --norc -p {h}//.pmzilla-lab/outils-figes/gh_issue.sh list",
                     f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab//outils-figes/gh_issue.sh list",
                     f"/bin/bash --noprofile --norc -p {h}/.pmzilla-lab/outils-figes//gh_issue.sh list"))

    def test_le_chemin_absolu_reste_refuse_hors_de_la_forme(self):
        h = self.a.home
        self.refuse((f"bash {h}/{CHEMIN} list", f"/bin/bash -p --noprofile --norc {h}/{CHEMIN} list", f"{h}/{CHEMIN} list",
                     f"cd /x && {self.forme_absolue()}", self.forme_absolue(suite=" view 742 > f"), f"X=1 {self.forme_absolue()}"))

    def test_un_nom_autre_que_les_quatre_est_refuse_en_chemin_absolu(self):
        self.refuse((self.forme_absolue(chemin=".pmzilla-lab/outils-figes/autre.sh"), self.forme_absolue(chemin=".pmzilla-lab/outils-figes/enveloppe.sh")))


class SuffixePointVirguleTrue(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.FORME = f"/bin/bash --noprofile --norc -p {cls.a.home}/{CHEMIN} view 742"   # R-20261111-48 : la forme est le chemin absolu
        cls.FORME_TILDE = "/bin/bash --noprofile --norc -p ~/.pmzilla-lab/outils-figes/gh_issue.sh view 742"

    def test_le_suffixe_exact_est_refuse(self):
        """Tâche 21.2 : ancien attendu « admis » (R-20261111-30), nouvel attendu « refusé » ; changement permis par R-20261111-30 (fin de l'admission) et R-20261111-48."""
        self.refuse((self.FORME + "; true", self.forme_absolue() + "; true", self.FORME.replace("view 742", "list --label type:feature") + "; true"))

    def test_le_suffixe_ne_sauve_pas_la_forme_avec_tilde(self):
        self.refuse((self.FORME_TILDE + "; true", self.FORME_TILDE))

    def test_tout_autre_suffixe_est_refuse(self):
        suffixes = ("; false", ";true", " ; true", "; true ", "; true\n", "\n; true", "; true; ls", "; true && ls", "; true | cat", "; true &", "; true > f", "&& true",
                    "|| true", "; TRUE", ";  true", "; true;", "; ls", "; true #", "; true $x", "; true `id`", "; $(true)", ";", "; ", "; truex", "; tru")
        self.refuse([self.FORME + s for s in suffixes] + [self.forme_absolue() + s for s in suffixes[:6]])

    def test_le_suffixe_ne_sauve_pas_une_autre_forme(self):
        self.refuse(("bash ~/.pmzilla-lab/outils-figes/gh_issue.sh view 742; true", "/bin/bash -p ~/.pmzilla-lab/outils-figes/gh_issue.sh view 742; true",
                     "cd /x && " + self.FORME + "; true", "true; " + self.FORME + "; true", "echo $(" + self.FORME + "; true)"))

    def test_le_suffixe_apres_un_mot_non_litteral_reste_refuse(self):
        self.refuse((self.FORME + ' "$(id)"; true', self.FORME + " > f; true", self.FORME + " #; true"))

    def test_sans_suffixe_la_forme_seule_passe(self):
        self.passe((self.FORME,))


class ParametreHome(unittest.TestCase):
    def test_forme_admise_prend_le_dossier_personnel_en_parametre(self):
        self.assertTrue(g.forme_admise("/bin/bash --noprofile --norc -p /home/a/.pmzilla-lab/outils-figes/gh_issue.sh list", "/home/a"))
        self.assertFalse(g.forme_admise("/bin/bash --noprofile --norc -p /home/b/.pmzilla-lab/outils-figes/gh_issue.sh list", "/home/a"))
        self.assertFalse(g.forme_admise("/bin/bash --noprofile --norc -p /home/a/.pmzilla-lab/outils-figes/gh_issue.sh list"))


if __name__ == "__main__":
    unittest.main()
