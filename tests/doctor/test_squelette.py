"""Squelette de tools/doctor.py (tâche 3.1) : options, niveaux, codes de sortie, phrases clés, langue, catalogues de messages.

    uv run --with pyyaml python -m unittest discover -s tests/doctor -v
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aide_doctor  # noqa: E402
from aide_doctor import DOCTOR, RACINE, TOOLS, Labo  # noqa: E402

import doctor  # noqa: E402
import doctor_messages  # noqa: E402
import messages  # noqa: E402


def r(identifiant, niveau, cle="ok", **compteurs):
    return doctor.Resultat(identifiant, niveau, cle, compteurs)


class Phrases(unittest.TestCase):
    def test_catalogues_coherents(self):
        self.assertEqual(messages.check_catalogs(doctor_messages.CATALOGS), [])

    def test_aucun_tiret_cadratin(self):
        for langue, catalogue in doctor_messages.CATALOGS.items():
            for cle, texte in catalogue.items():
                self.assertNotIn("—", texte, f"{langue}/{cle}")

    def test_niveaux_en_francais_et_en_anglais(self):
        fr, en = messages.Messages(doctor_messages.CATALOGS, "fr"), messages.Messages(doctor_messages.CATALOGS, "en")
        self.assertEqual([fr(f"niveau_{n}") for n in ("ok", "warning", "problem", "skipped")], ["ok", "avertissement", "problème", "ignoré"])
        self.assertEqual([en(f"niveau_{n}") for n in ("ok", "warning", "problem", "skipped")], ["ok", "warning", "problem", "skipped"])

    def test_resumes(self):
        for langue, attendu in (("fr", ["doctor : tout va bien", "doctor : 1 avertissement(s)", "doctor : 2 problème(s), 1 avertissement(s)"]),
                                ("en", ["doctor: all good", "doctor: 1 warning(s)", "doctor: 2 problem(s), 1 warning(s)"])):
            t = messages.Messages(doctor_messages.CATALOGS, langue)
            self.assertEqual(doctor.resume([r("db", "ok"), r("disk", "skipped", "not_due")], t), attendu[0])
            self.assertEqual(doctor.resume([r("db", "ok"), r("disk", "warning", "low")], t), attendu[1])
            self.assertEqual(doctor.resume([r("db", "problem", "port_closed"), r("ollama", "problem", "down"), r("disk", "warning", "low")], t), attendu[2])

    def test_ligne_par_controle(self):
        fr, en = messages.Messages(doctor_messages.CATALOGS, "fr"), messages.Messages(doctor_messages.CATALOGS, "en")
        self.assertEqual(doctor.ligne(r("watch", "skipped", "not_due"), fr), "watch : ignoré : pas encore dû")
        self.assertEqual(doctor.ligne(r("watch", "skipped", "not_due"), en), "watch: skipped: not due yet")
        self.assertEqual(doctor.ligne(r("backup", "skipped", "not_set_up"), en), "backup: skipped: not set up")
        self.assertEqual(doctor.ligne(doctor.Resultat("models", "skipped", "depends", {}, ["ollama"]), en), "models: skipped: depends on ollama")
        self.assertEqual(doctor.ligne(r("jira", "skipped", "unknown"), en), "jira: skipped: expiry date unknown")
        self.assertEqual(doctor.ligne(r("jira", "skipped", "unknown"), fr), "jira : ignoré : date d'expiration inconnue")

    def test_phrase_impossible_de_lancer(self):
        self.assertEqual(messages.Messages(doctor_messages.CATALOGS, "en")("impossible", cause="x"), "doctor: cannot run: x")
        self.assertEqual(messages.Messages(doctor_messages.CATALOGS, "fr")("impossible", cause="x"), "doctor : impossible de lancer : x")

    def test_chaque_raison_a_un_texte_dans_les_deux_langues(self):
        for cle in doctor.TOUTES_LES_RAISONS:
            for langue in ("fr", "en"):
                t = messages.Messages(doctor_messages.CATALOGS, langue)
                self.assertTrue(doctor.raison(doctor.Resultat(cle[0], "ok", cle[1], {}, ["x"]), t), cle)


class Codes(unittest.TestCase):
    def test_codes_de_sortie_par_niveau(self):
        self.assertEqual(doctor.code_sortie([r("a", "ok"), r("b", "skipped", "not_due")]), 0)
        self.assertEqual(doctor.code_sortie([r("a", "warning", "low")]), 0)
        self.assertEqual(doctor.code_sortie([r("a", "problem", "down"), r("b", "warning", "low")]), 1)


class Ligne(Labo):
    def test_le_lancement_courant_appelle_main_dans_le_processus(self):
        with mock.patch.object(doctor, "main", wraps=doctor.main) as main, \
                mock.patch.object(subprocess, "run", wraps=subprocess.run) as run:
            p = self.lancer("--quiet")
        main.assert_called_once_with(["--quiet"])
        self.assertEqual(p.returncode, 0)
        self.assertTrue(p.stdout.strip().endswith("doctor : tout va bien"))
        self.assertFalse([c for c in run.call_args_list if str(DOCTOR) in map(str, c.args[0])])

    def test_le_depot_du_laboratoire_est_copie_d_un_modele(self):
        shutil.rmtree(self.run.parent)
        with mock.patch.object(aide_doctor, "git", wraps=aide_doctor.git) as git:
            self._depot_principal()
        verbes = {c.args[1] for c in git.call_args_list}
        self.assertFalse(verbes & {"init", "add", "commit"}, verbes)
        self.assertEqual(aide_doctor.git(self.principal, "rev-parse", "main").stdout.strip(),
                         aide_doctor.git(self.run, "rev-parse", "HEAD").stdout.strip())
        self.assertIn(str(self.run), aide_doctor.git(self.principal, "worktree", "list", "--porcelain").stdout)
        commun = aide_doctor.git(self.run, "rev-parse", "--git-common-dir").stdout.strip()
        self.assertEqual(Path(commun).resolve(), (self.principal / ".git").resolve())
        self.assertEqual(aide_doctor.git(self.run, "status", "--porcelain").stdout, "")

    def test_l_etat_sain_installe_une_seule_tache(self):
        self.assertEqual(len(list(self.agents.glob("*.plist"))), 1)
        niveau, entree, _ = self.niveau("launchd")
        self.assertEqual(niveau, "ok")
        self.assertEqual(entree["reason"]["counts"]["loaded"], 1)

    def test_le_lancement_reel_reste_un_processus(self):
        with mock.patch.object(doctor, "main", wraps=doctor.main) as main:
            p = self.lancer("--quiet", reel=True)
        main.assert_not_called()
        self.assertEqual(p.returncode, 0)
        self.assertTrue(p.stdout.strip().endswith("doctor : tout va bien"))

    def test_un_probleme_dans_le_vrai_processus_donne_le_code_1(self):
        self.fermer_base()
        p = self.lancer("--quiet", reel=True)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertNotIn("doctor : tout va bien", p.stdout)

    def test_option_inconnue_code_2_et_aucun_controle(self):
        p = self.lancer("--inconnue", reel=True)
        self.assertEqual(p.returncode, 2)
        self.assertEqual([a for a in self.appels() if not a.startswith("git ")], [])
        self.assertEqual(self.ollama.requetes, [])

    def test_langue_inconnue_code_2(self):
        self.assertEqual(self.lancer("--language", "de", reel=True).returncode, 2)

    def test_aide_en_francais_avec_les_codes(self):
        p = self.lancer("--help", reel=True)
        self.assertEqual(p.returncode, 0)
        for option in ("--json", "--language", "--quiet", "--record"):
            self.assertIn(option, p.stdout)
        texte = DOCTOR.read_text(encoding="utf-8")
        self.assertIn("Code de sortie", texte)

    def test_tete_pep_723_et_fichier_de_verrou(self):
        texte = DOCTOR.read_text(encoding="utf-8")
        self.assertIn("# /// script", texte)
        self.assertTrue((TOOLS / "doctor.py.lock").exists())

    def test_francais_par_defaut_et_anglais_sur_demande(self):
        self.assertTrue(self.lancer("--quiet").stdout.strip().endswith("doctor : tout va bien"))
        self.assertTrue(self.lancer("--quiet", "--language", "en").stdout.strip().endswith("doctor: all good"))

    def test_json_au_format_de_l_etat(self):
        p, donnees = self.resultat_json()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(set(donnees), {"version", "checked_at", "counts", "checks", "last_notification"})
        self.assertEqual(donnees["version"], 1)
        self.assertEqual(donnees["checked_at"], "2026-10-14T10:00")
        self.assertEqual(set(donnees["counts"]), {"ok", "warning", "problem", "skipped"})
        for controle in donnees["checks"]:
            self.assertEqual(set(controle), {"id", "level", "reason"})
            self.assertEqual(set(controle["reason"]), {"key", "counts"})

    def test_execution_simple_n_ecrit_rien(self):
        avant = self.fichiers()
        self.lancer()
        self.lancer("--json")
        self.assertEqual(self.fichiers(), avant)
        self.assertFalse((self.donnees / "doctor-etat.json").exists())

    def test_code_2_quand_la_racine_est_introuvable_n_est_pas_un_plantage(self):
        p = self.lancer(env={"PMZILLA_LAB_TODAY": "pas-une-date"}, reel=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("doctor : impossible de lancer", p.stdout + p.stderr)
        self.assertNotIn("Traceback", p.stderr)


class ParitePasDeControle(Labo):
    """Change doctor-parity-removal (design D4) : le doctor n'a plus de contrôle de parité. Un fichier du nom de l'ancien marqueur et un
    journal de verdicts qui finit sur un écart n'ajoutent ni ligne, ni contrôle JSON, ni entrée du fichier d'état, et ne changent pas le code de sortie."""

    def poser_anciens_fichiers(self):
        (self.donnees / "parite-sqlite").write_text("2026-10-10\n", encoding="utf-8")
        (self.donnees / "parite-sqlite.log").write_text("2026-10-13 identique livres 10\n2026-10-14 écart livres 10\n", encoding="utf-8")

    def sorties(self):
        sortie = {}
        for langue in ("fr", "en"):
            sortie[langue] = self.lancer("--language", langue)
        p_json, donnees = self.resultat_json()
        p_etat = self.lancer("--record")
        etat = json.loads((self.donnees / "doctor-etat.json").read_text(encoding="utf-8"))
        return sortie, (p_json, donnees), (p_etat, etat)

    def test_aucune_trace_de_parite_ni_changement_du_code_de_sortie(self):
        sans_fichiers = self.sorties()
        self.poser_anciens_fichiers()
        avec_fichiers = self.sorties()
        for langue in ("fr", "en"):
            self.assertNotIn("parity", avec_fichiers[0][langue].stdout)
            self.assertEqual(avec_fichiers[0][langue].returncode, sans_fichiers[0][langue].returncode)
            self.assertEqual(avec_fichiers[0][langue].stdout, sans_fichiers[0][langue].stdout)
        self.assertNotIn("parity", [c["id"] for c in avec_fichiers[1][1]["checks"]])
        self.assertEqual(avec_fichiers[1][0].returncode, sans_fichiers[1][0].returncode)
        self.assertNotIn("parity", [c["id"] for c in avec_fichiers[2][1]["checks"]])
        self.assertEqual(avec_fichiers[2][0].returncode, sans_fichiers[2][0].returncode)
        self.assertEqual(avec_fichiers[2][0].returncode, 0, avec_fichiers[2][0].stdout)

    def test_aucune_raison_de_parite_dans_les_catalogues_ni_dans_le_squelette(self):
        for langue, catalogue in doctor_messages.CATALOGS.items():
            self.assertEqual([cle for cle in catalogue if cle.startswith("raison_parity_")], [], langue)
        self.assertNotIn("parity", [cle[0] for cle in doctor.TOUTES_LES_RAISONS])
        self.assertNotIn("parity", doctor.ORDRE)


if __name__ == "__main__":
    unittest.main()
