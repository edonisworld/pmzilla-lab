"""
Tests de l'étape launchd du script d'installation (change install-script, design D4, D14) : vrais gabarits, simulacre launchctl à état.

    python3 -W ignore -m unittest discover -s tests/install_lab -p "test_launchd.py" -q -f
"""
import os
import plistlib
import sys
import unittest
from unittest import mock

from aide_install import TOOLS_REELS, CasDeBase

sys.path.insert(0, str(TOOLS_REELS))
import install_lab_context as c        # noqa: E402
import install_lab_launchd as ll       # noqa: E402

ETIQUETTES = ("com.pmzilla.watch", "com.pmzilla.watch-catchup", "com.pmzilla.db-backup", "com.pmzilla.doctor")

# launchctl à état : un fichier « charge-<label> » par tâche chargée. Drapeaux : bootstrap-erreur-5 (charge puis rend 5),
# bootstrap-echec (rend 5 sans charger).
LAUNCHCTL = r'''
cmd="$1"
case "$cmd" in
  print) label="${2##*/}"; [ -e "$INSTALL_LAB_ETAT/charge-$label" ] && exit 0; exit 113 ;;
  bootout) label="${2##*/}"; rm -f "$INSTALL_LAB_ETAT/charge-$label"; exit 0 ;;
  bootstrap)
    label="$(basename "$3" .plist)"
    [ -e "$INSTALL_LAB_ETAT/bootstrap-echec" ] && { echo "Bootstrap failed: 5"; exit 5; }
    : > "$INSTALL_LAB_ETAT/charge-$label"
    [ -e "$INSTALL_LAB_ETAT/bootstrap-erreur-5" ] && { echo "Bootstrap failed: 5"; exit 5; }
    exit 0 ;;
  kickstart) exit 0 ;;
esac
exit 0
'''


class CasLaunchd(CasDeBase):
    def setUp(self):
        super().setUp()
        self.fx.simulacre("launchctl", LAUNCHCTL)
        self.agents = self.fx.maison / "Library" / "LaunchAgents"

    def lancer(self, *args, reponses="", etat=None, a_blanc=False):
        """Lance l'étape dans le processus, avec les simulacres en tête du PATH et les réponses sur l'entrée."""
        ctx = c.Contexte(racine=self.fx.racine, maison=self.fx.maison, a_blanc=a_blanc,
                         etat={"ollama_ok": True, "base_ok": True} if etat is None else etat)
        lignes = iter(reponses.splitlines())

        def entree(_invite=""):
            try:
                return next(lignes)
            except StopIteration:
                raise EOFError
        avant = len(self.fx.lire_appels())
        with mock.patch.dict(os.environ, self.fx.environnement()), mock.patch("builtins.input", entree), \
                mock.patch("sys.stdout", new=__import__("io").StringIO()) as sortie:
            resultat = ll.executer(ctx)
        self.sortie = sortie.getvalue()
        self.appels = self.fx.lire_appels()[avant:]
        self.ctx = ctx
        return resultat

    def sonde(self, etat=None):
        ctx = c.Contexte(racine=self.fx.racine, maison=self.fx.maison, etat=etat or {})
        with mock.patch.dict(os.environ, self.fx.environnement()):
            return ll.sonde(ctx)

    def installer_tout(self):
        r = self.lancer(reponses="y\n" * 20)
        self.assertEqual(r.etat, c.FAIT, self.sortie)

    def fichier(self, etiquette):
        return self.agents / f"{etiquette}.plist"


class Rendu(CasLaunchd):
    def test_installation_rend_et_charge_les_quatre_taches(self):
        self.installer_tout()
        for e in ETIQUETTES:
            texte = self.fichier(e).read_text(encoding="utf-8")
            self.assertNotIn("__HOME__", texte)
            self.assertNotIn("__LAB__", texte)
            self.assertIn(str(self.fx.maison), texte)
            self.assertEqual(plistlib.loads(texte.encode())["Label"], e)
            self.assertTrue(self.fx.a_drapeau(f"charge-{e}"))
        uid = os.getuid()
        for e in ETIQUETTES:
            self.assertIn(f"launchctl bootstrap gui/{uid} {self.fichier(e)}", self.appels)
            self.assertIn(f"xattr -c {self.fichier(e)}", self.appels)
        self.assertEqual([a for a in self.appels if a.startswith("launchctl kickstart")], [])

    def test_le_dossier_du_lab_vient_du_module_partage(self):
        self.installer_tout()
        programme = plistlib.loads(self.fichier("com.pmzilla.doctor").read_bytes())["ProgramArguments"][1]
        self.assertEqual(os.path.realpath(programme), os.path.realpath(f"{self.fx.maison}/PMZilla-Lab/doctor.sh"))

    def test_sans_dossier_de_contenu_l_installation_s_arrete_avec_le_code_78(self):
        ctx = c.Contexte(racine=self.fx.racine, maison=self.fx.maison, etat={"ollama_ok": True, "base_ok": True})
        env = {k: v for k, v in self.fx.environnement().items() if k != "PMZILLA_LAB_WORKSPACE"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch("sys.stderr", new=__import__("io").StringIO()) as erreur:
            with self.assertRaises(SystemExit) as arret:
                ll.executer(ctx)
        self.assertEqual(arret.exception.code, 78)
        self.assertIn("content folder not found", erreur.getvalue())
        self.assertNotIn(str(self.fx.maison), erreur.getvalue())

    def test_second_passage_saute_sans_appel_qui_change(self):
        self.installer_tout()
        self.assertTrue(self.sonde())
        r = self.lancer()
        self.assertEqual(r.etat, c.FAIT)
        self.assertEqual(self.fx.appels_qui_changent(self.appels), [])
        self.assertIn("already done, skipped", self.sortie)


class Confirmation(CasLaunchd):
    def test_reponse_vide_refuse_et_ne_change_rien(self):
        avant = self.fx.empreinte()
        r = self.lancer(reponses="\n\n\n\n")
        self.assertEqual(r.etat, c.REFUSE)
        self.assertEqual(self.fx.empreinte(), avant)
        self.assertEqual(self.fx.appels_qui_changent(self.appels), [])

    def test_fin_d_entree_refuse(self):
        r = self.lancer()
        self.assertEqual(r.etat, c.REFUSE)
        self.assertFalse(self.agents.exists())

    def test_passage_a_blanc(self):
        avant = self.fx.empreinte()
        r = self.lancer(a_blanc=True)
        self.assertEqual(r.etat, c.A_BLANC)
        self.assertEqual(self.fx.empreinte(), avant)
        self.assertEqual(self.fx.appels_qui_changent(self.appels), [])


class Prerequis(CasLaunchd):
    def test_sans_ollama_la_veille_est_reportee(self):
        r = self.lancer(reponses="y\n" * 10, etat={"ollama_ok": False, "base_ok": True})
        self.assertEqual(r.etat, c.REPORTE)
        self.assertIn("watch job not installed", self.ctx.reportes)
        self.assertIn("watch catch-up job not installed", self.ctx.reportes)
        self.assertFalse(self.fichier("com.pmzilla.watch").exists())
        self.assertFalse(self.fichier("com.pmzilla.watch-catchup").exists())
        self.assertTrue(self.fichier("com.pmzilla.db-backup").exists())
        self.assertTrue(self.fichier("com.pmzilla.doctor").exists())

    def test_sans_base_la_sauvegarde_est_reportee(self):
        r = self.lancer(reponses="y\n" * 10, etat={"ollama_ok": True, "base_ok": False})
        self.assertEqual(r.etat, c.REPORTE)
        self.assertIn("backup job not installed", self.ctx.reportes)
        self.assertFalse(self.fichier("com.pmzilla.db-backup").exists())
        self.assertTrue(self.fichier("com.pmzilla.watch").exists())

    def test_la_tache_du_doctor_est_installee_sans_ollama_ni_base(self):
        r = self.lancer(reponses="y\n" * 10, etat={"ollama_ok": False, "base_ok": False})
        self.assertEqual(r.etat, c.REPORTE)
        self.assertTrue(self.fichier("com.pmzilla.doctor").exists())
        self.assertTrue(self.fx.a_drapeau("charge-com.pmzilla.doctor"))
        self.assertFalse(self.fichier("com.pmzilla.watch").exists())
        self.assertFalse(self.fichier("com.pmzilla.watch-catchup").exists())
        self.assertFalse(self.fichier("com.pmzilla.db-backup").exists())
        self.assertEqual(len([x for x in self.ctx.reportes if "doctor" in x]), 0)

    def test_ligne_de_report_non_dupliquee(self):
        ctx = c.Contexte(racine=self.fx.racine, maison=self.fx.maison, etat={"ollama_ok": False, "base_ok": False},
                         reportes=["watch job not installed"])
        with mock.patch.dict(os.environ, self.fx.environnement()), mock.patch("sys.stdout", new=__import__("io").StringIO()):
            ll.executer(ctx)
        self.assertEqual(ctx.reportes.count("watch job not installed"), 1)
        self.assertEqual(ctx.reportes.count("watch catch-up job not installed"), 1)
        self.assertEqual(ctx.reportes.count("backup job not installed"), 1)

    def test_repli_sur_les_sondes_partagees(self):
        import install_lab_prereqs as pr
        import install_lab_database as db
        with mock.patch.object(pr, "ollama_pret", return_value=True), mock.patch.object(db, "base_prete", return_value=False):
            r = self.lancer(reponses="y\n" * 10, etat={})
        self.assertEqual(r.etat, c.REPORTE)
        self.assertTrue(self.fichier("com.pmzilla.watch").exists())
        self.assertTrue(self.fichier("com.pmzilla.watch-catchup").exists())
        self.assertFalse(self.fichier("com.pmzilla.db-backup").exists())


class Chargement(CasLaunchd):
    def test_erreur_de_chargement_suivie_d_un_print_reussi_compte_comme_fait(self):
        self.fx.drapeau("bootstrap-erreur-5")
        r = self.lancer(reponses="y\n" * 20)
        self.assertEqual(r.etat, c.FAIT, self.sortie)
        self.assertNotIn("failed", self.sortie)

    def test_chargement_en_echec_nomme_l_etape_et_la_commande(self):
        self.fx.drapeau("bootstrap-echec")
        r = self.lancer(reponses="y\n" * 20)
        self.assertEqual(r.etat, c.ECHEC)
        self.assertIn("launchctl bootstrap", r.detail)
        self.assertIn("step launchd: failed: launchctl bootstrap", self.sortie)

    def test_fichier_different_remplace_apres_confirmation_avec_bootout(self):
        self.installer_tout()
        chemin = self.fichier("com.pmzilla.watch")
        chemin.write_text("different", encoding="utf-8")
        self.assertFalse(self.sonde())
        r = self.lancer(reponses="y\n" * 10)
        self.assertEqual(r.etat, c.FAIT, self.sortie)
        uid = os.getuid()
        manip = [a for a in self.appels if a.startswith("launchctl")]
        self.assertLess(manip.index(f"launchctl bootout gui/{uid}/com.pmzilla.watch"),
                        next(i for i, a in enumerate(manip) if a.startswith("launchctl bootstrap")))
        self.assertNotEqual(chemin.read_text(encoding="utf-8"), "different")

    def test_remplacement_refuse_laisse_le_fichier(self):
        self.installer_tout()
        chemin = self.fichier("com.pmzilla.watch")
        chemin.write_text("different", encoding="utf-8")
        r = self.lancer(reponses="\n\n\n\n")
        self.assertEqual(r.etat, c.REFUSE)
        self.assertEqual(chemin.read_text(encoding="utf-8"), "different")
        self.assertTrue(self.fx.a_drapeau("charge-com.pmzilla.watch"))
        self.assertEqual(self.fx.appels_qui_changent(self.appels), [])


class ModelesSansDossierDeCode(unittest.TestCase):
    """Change run-worktree (D5) : aucun modèle rendu ne nomme un dossier de code ; chaque tâche lance un lien du dossier du labo."""
    MODELES = ("com.pmzilla.watch.plist", "com.pmzilla.watch-catchup.plist", "com.pmzilla.db-backup.plist",
               "com.pmzilla.offsite-copy.plist", "com.pmzilla.offsite-restore-test.plist", "com.pmzilla.doctor.plist")
    MAISON = "/home/essai"

    def rendu(self, nom):
        texte = (TOOLS_REELS / nom).read_text(encoding="utf-8").replace(ll.MARQUEUR, self.MAISON).replace(ll.MARQUEUR_LAB, self.MAISON + "/PMZilla-Lab")
        return plistlib.loads(texte.encode("utf-8"))

    def test_les_six_modeles_existent(self):
        for nom in self.MODELES:
            self.assertTrue((TOOLS_REELS / nom).is_file(), nom)

    def test_aucun_modele_rendu_ne_nomme_un_dossier_de_code(self):
        for nom in self.MODELES:
            donnees = self.rendu(nom)
            programme = donnees["ProgramArguments"][1]
            self.assertRegex(programme, rf"^{self.MAISON}/PMZilla-Lab/[A-Za-z0-9_]+\.(sh|py)$", f"{nom} : {programme}")
            for dossier in ("/workspace/", "/run/", "/tools/", "/wt-"):
                self.assertNotIn(dossier, repr(donnees), f"{nom} nomme {dossier}")

    def test_les_modeles_rendus_par_l_etape_ne_nomment_pas_non_plus_un_dossier_de_code(self):
        for tache in ll.TACHES:
            self.assertIn(tache.gabarit, self.MODELES)


class ViaOrchestrateur(CasDeBase):
    def test_passage_a_blanc_de_l_etape(self):
        self.fx.simulacre("launchctl", LAUNCHCTL)
        avant = self.fx.empreinte()
        p = self.fx.lancer("--mode", "fresh", "--dry-run", "--step", "launchd")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.fx.empreinte(), avant)
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])

    def test_etape_declaree(self):
        self.assertEqual([(e.nom, e.depend) for e in ll.ETAPES], [("launchd", ("links",))])


if __name__ == "__main__":
    unittest.main()
