"""
Tests de `flow_retention.py` : refus de session, langues, durée de conservation au-delà d'un an, catalogue de messages
(spec jira-flow-retention : « Retention tool output and session refusal », scénario « Period above one year »). Suite : tests/flow_retention.
"""
import os
import subprocess
import sys
import unittest
import unittest.mock

from aide_flow_retention import ETIQUETTE, TOOLS, Espace, FausseBase, fr
from flow_retention_messages import CATALOGS
from messages import check_catalogs


class Session(Espace):
    def test_refus_dans_une_session_claude_code(self):
        self.sauvegarde = None
        for commande in (("check",), ("purge",), ("purge", "--apply")):
            for langue, phrase in (("en", "Refused inside a Claude Code session"), ("fr", "Refusé dans une session Claude Code")):
                with self.subTest(commande=commande, langue=langue):
                    base = FausseBase()
                    environ = {**self.environ, "CLAUDECODE": "1"}
                    with unittest.mock.patch.object(fr, "lire_reglages", side_effect=AssertionError("réglage lu")):
                        code, sortie, erreur, _ = self.lancer(*commande, "--language", langue, base=base, environ=environ)
                    self.assertEqual(code, 3)
                    self.assertIn(phrase, sortie)
                    self.assertEqual(base.requetes, [])

    def test_variable_presente_meme_vide(self):
        code, sortie, _, _ = self.lancer("check", "--language", "en", environ={**self.environ, "CLAUDECODE": ""})
        self.assertEqual(code, 3)
        self.assertIn("Refused inside a Claude Code session", sortie)

    def test_aucune_option_ne_contourne_le_refus(self):
        for option in ("--force", "--yes", "--allow-session"):
            code, _, _, _ = self.lancer("check", option, environ={**self.environ, "CLAUDECODE": "1"})
            self.assertEqual(code, 2, option)           # option inconnue : refus d'usage, jamais un contournement

    def test_rien_n_est_lu_ni_supprime_en_session(self):
        self.fichier(self.exports, "vieux.csv", 800)
        self.sauvegarde_du_jour = None
        avant = self.instantane()
        self.lancer("purge", "--apply", environ={**self.environ, "CLAUDECODE": "1"})
        self.assertEqual(self.instantane(), avant)

    def test_lancement_reel_en_sous_processus(self):
        environ = {k: v for k, v in self.environ.items()}
        environ["CLAUDECODE"] = "1"
        resultat = subprocess.run([sys.executable, "-B", str(TOOLS / "flow_retention.py"), "check", "--language", "en"], env=environ,
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(resultat.returncode, 3, resultat.stderr)
        self.assertIn("Refused inside a Claude Code session", resultat.stdout)


class Langues(Espace):
    def test_francais_par_defaut(self):
        code, sortie, _, _ = self.lancer("check")
        self.assertEqual(code, 0)
        self.assertIn("contrôle de conservation : rien hors règle", sortie)

    def test_anglais(self):
        _, sortie, _, _ = self.lancer("check", "--language", "en")
        self.assertIn("retention check: nothing out of rule", sortie)
        self.assertNotIn("contrôle", sortie)

    def test_option_avant_la_sous_commande(self):
        _, sortie, _, _ = self.lancer("--language", "en", "check")
        self.assertIn("retention check: nothing out of rule", sortie)

    def test_autre_langue_code_2(self):
        for langue in ("de", "FR", "", "es"):
            with self.subTest(langue=langue):
                base = FausseBase()
                code, sortie, erreur, _ = self.lancer("check", "--language", langue, base=base)
                self.assertEqual(code, 2)
                if langue:
                    self.assertNotIn(f"« {langue} »", sortie + erreur)
                self.assertEqual(base.requetes, [])

    def test_sous_commande_inconnue_ou_absente(self):
        self.assertEqual(self.lancer()[0], 2)
        self.assertEqual(self.lancer("zzcommande")[0], 2)
        code, sortie, erreur, _ = self.lancer("zzcommande")
        self.assertNotIn("zzcommande", sortie + erreur)

    def test_apply_seulement_avec_purge(self):
        self.assertEqual(self.lancer("check", "--apply")[0], 2)

    def test_catalogues_coherents(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_phrases_cles_de_la_conception(self):
        fr_, en = CATALOGS["fr"], CATALOGS["en"]
        self.assertEqual(en["check_clean"], "retention check: nothing out of rule")
        self.assertEqual(en["check_found"], "retention check: {n} items out of rule")
        self.assertEqual(fr_["check_clean"], "contrôle de conservation : rien hors règle")
        self.assertEqual(fr_["check_found"], "contrôle de conservation : {n} éléments hors règle")
        self.assertEqual(en["dry_run"], "dry run: nothing deleted")
        self.assertEqual(fr_["dry_run"], "essai : rien n'est supprimé")
        self.assertEqual((en["purge_done"], fr_["purge_done"]), ("purge done", "purge faite"))
        self.assertEqual(en["backup_missing"], "pre-purge backup missing: run the labelled backup first")
        self.assertEqual(fr_["backup_missing"], "sauvegarde avant purge absente : lancer d'abord la sauvegarde étiquetée")
        self.assertEqual(en["store_csv_route"], "files left from the CSV route: {n}")
        self.assertEqual(fr_["store_csv_route"], "fichiers laissés par la voie CSV : {n}")
        for retire in ("forbidden", "store_cache", "store_csv"):                 # magasins retirés avec la voie CSV (database-only, D10)
            self.assertNotIn(retire, en)
            self.assertNotIn(retire, fr_)


class DureeAuDelaDUnAn(Espace):
    def lancer_avec_duree(self, duree, extra=""):
        self.ecrire_reglages(f"retention:\n  period_days: {duree}\n  backup_label: {ETIQUETTE}\n{extra}")
        self.fichier(self.exports, "api-zzfichier.csv", 900)
        self.sauvegarde(fr_aujourdhui())
        base = FausseBase(5)
        avant = self.instantane()
        sorties = {c: self.lancer(*c, "--language", "en", base=base) for c in (("check",), ("purge",), ("purge", "--apply"))}
        return sorties, base, avant

    def test_refus_code_3_nomme_le_reglage_sans_sa_valeur_et_ne_lit_rien(self):
        sorties, base, avant = self.lancer_avec_duree(400)
        for commande, (code, sortie, erreur, _) in sorties.items():
            with self.subTest(commande=commande):
                self.assertEqual(code, 3)
                self.assertIn("retention.period_days", sortie)
                self.assertIn("above one year", sortie)
                self.assertNotIn("400", sortie + erreur)
        self.assertEqual(base.requetes, [])                         # la base n'est jamais ouverte
        self.assertEqual(self.instantane(), avant)                  # le fichier de 900 jours est toujours là
        self.assertFalse(base.fermee)

    def test_controle_avant_la_validation_du_reste_du_fichier(self):
        sorties, base, _ = self.lancer_avec_duree(9999, "cycles:\n  zzinvalide: {}\n")
        for commande, (code, sortie, _, _) in sorties.items():
            self.assertEqual(code, 3)
            self.assertIn("above one year", sortie)
            self.assertNotIn("zzinvalide", sortie)

    def test_un_an_exactement_est_accepte(self):
        sorties, base, _ = self.lancer_avec_duree(365)
        self.assertEqual(sorties[("check",)][0], 4)

    def test_age_maximal_au_dessus_de_la_duree_refuse(self):
        self.ecrire_reglages("retention:\n  period_days: 30\n  max_file_age_days: 31\n")
        base = FausseBase()
        code, sortie, _, _ = self.lancer("check", base=base)
        self.assertEqual(code, 3)
        self.assertEqual(base.requetes, [])

    def test_reglage_invalide_refuse_code_3(self):
        self.ecrire_reglages("retention:\n  zzinconnu: 3\n")
        code, sortie, _, base = self.lancer("check")
        self.assertEqual(code, 3)
        self.assertIn("retention.zzinconnu", sortie)                # le nom du réglage, jamais sa valeur
        self.assertEqual(base.requetes, [])

    def test_fichier_de_reglages_absent_defauts(self):
        self.reglages.unlink()
        self.assertEqual(self.lancer("check")[0], 0)

    def test_fichier_de_reglages_illisible(self):
        self.ecrire_reglages("retention: [\n")
        self.assertEqual(self.lancer("check")[0], 3)


def fr_aujourdhui():
    from aide_flow_retention import AUJOURDHUI
    return AUJOURDHUI


if __name__ == "__main__":
    unittest.main()
