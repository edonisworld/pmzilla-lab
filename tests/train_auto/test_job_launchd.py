"""
Faux 65 du train automatique : le modèle launchd et ses garde-fous (design D1, D2, D7, D9, D11), le code 8, `stop_info()`, le refus de l'activation
pendant l'arrêt, `installed_plist_check()`. Tout est jeté : dossier personnel temporaire, faux interpréteurs (scripts), dossier de données temporaire. Aucun
chemin du compte, aucun launchctl, aucun fichier réel.

    bash tests/run_all.sh train_auto
"""
import ast
import contextlib
import hashlib
import io
import json
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aide_auto import AvecAuto, epoch  # noqa: E402
from test_activation_commandes import AvecDonnees, serie_verte  # noqa: E402  (aide commune de la suite)

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import lab_paths  # noqa: E402
import train_auto  # noqa: E402
import train_auto_messages  # noqa: E402

SYSTEME = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
FNM = ".local/share/fnm/aliases/default/bin"


class Temporaire(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.maison = self.base / "maison"
        self.maison.mkdir()

    def faux_python(self, nom, sortie):
        """Un dossier avec un `python3` factice qui répond `sortie` à --version (le dossier est rendu)."""
        dossier = self.base / nom
        dossier.mkdir()
        faux = dossier / "python3"
        faux.write_text(f'#!/bin/sh\necho "{sortie}"\n', encoding="utf-8")
        faux.chmod(0o755)
        return dossier


class CheminDuJob(Temporaire):
    """D1 : le PATH du job est calculé par une seule fonction, dans l'ordre : dossier de l'interpréteur, fnm du compte, dossiers du système."""

    def test_l_ordre_des_dossiers(self):
        self.assertEqual(train_auto.job_path("/x/py/bin", "/h"), f"/x/py/bin:/h/{FNM}:{SYSTEME}")

    def test_un_dossier_en_double_garde_sa_premiere_place(self):
        self.assertEqual(train_auto.job_path("/opt/homebrew/bin", "/h"), f"/opt/homebrew/bin:/h/{FNM}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
        self.assertEqual(train_auto.job_path(f"/h/{FNM}", "/h"), f"/h/{FNM}:{SYSTEME}")

    def test_le_dossier_du_compte_suit_le_dossier_personnel_donne(self):
        self.assertIn(f"/autre/maison/{FNM}", train_auto.job_path("/x", "/autre/maison").split(":"))

    def test_fnm_dir_est_ignore(self):
        with mock.patch.dict(os.environ, {"FNM_DIR": "/ailleurs/fnm"}):
            self.assertNotIn("/ailleurs", train_auto.job_path("/x", "/h"))

    def test_aucun_chemin_du_compte_dans_la_source(self):
        source = (RACINE / "tools" / "train_auto.py").read_text(encoding="utf-8")
        self.assertNotIn("/Users/", source)
        self.assertNotRegex(source, r"/home/\w+")


class ModeleDuJob(Temporaire):
    def modele(self, interpreteur="/x/py/bin/python3", run="/r", maison="/h"):
        return train_auto.plist_model(interpreteur, run, maison)

    def test_le_chemin_du_job_est_la_seule_variable_d_environnement(self):
        m = self.modele()
        self.assertEqual(m["EnvironmentVariables"], {"PATH": f"/x/py/bin:/h/{FNM}:{SYSTEME}"})

    def test_le_reste_du_modele_ne_change_pas(self):
        m = self.modele()
        self.assertEqual(m["ProgramArguments"], ["/x/py/bin/python3", "-I", "/r/tools/train_auto.py", "pass"])   # R-20261110-36 : l'interpréteur de la génération, plus /usr/bin/python3
        self.assertEqual(m["WorkingDirectory"], "/r")
        self.assertEqual(m["StartCalendarInterval"], [{"Hour": h, "Minute": 0} for h in range(8, 22)])
        self.assertEqual(m["StandardOutPath"], "/h/Library/Logs/pmzilla-train-auto.log")
        self.assertEqual(m["StandardErrorPath"], m["StandardOutPath"])
        for cle in ("RunAtLoad", "KeepAlive", "StartInterval"):
            self.assertNotIn(cle, m)

    def test_plist_bytes_imprime_le_meme_modele(self):
        octets = train_auto.plist_bytes(run="/r", home="/h", interpreter="/x/py/bin/python3")
        self.assertEqual(plistlib.loads(octets), self.modele())


class ModeleRefuse(Temporaire):
    """D2 : `plist` sort en 8, sans rien sur la sortie standard, pour un interpréteur de moins de 3.10 ou sans `python3` identique dans son dossier."""

    def lancer(self, version, executable, *options):
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "version_info", version), mock.patch.object(sys, "executable", str(executable)), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = train_auto.main([*options, "plist"])
        return code, sortie.getvalue(), erreur.getvalue()

    def interpreteur_avec_python3(self, nom="bon"):
        dossier = self.base / nom
        dossier.mkdir()
        (dossier / "python3.14").write_text("#!/bin/sh\n", encoding="utf-8")
        (dossier / "python3.14").chmod(0o755)
        (dossier / "python3").symlink_to("python3.14")
        return dossier / "python3.14"

    def test_un_interpreteur_3_9_est_refuse(self):
        code, sortie, erreur = self.lancer((3, 9, 6, "final", 0), self.interpreteur_avec_python3())
        self.assertEqual(code, 8)
        self.assertEqual(sortie, "")
        self.assertEqual(erreur.strip(), "train_auto : modèle refusé : python3 3.10 ou plus requis pour le générer (version 3.9)")

    def test_la_phrase_en_anglais(self):
        code, sortie, erreur = self.lancer((3, 9, 6, "final", 0), self.interpreteur_avec_python3(), "--language", "en")
        self.assertEqual((code, sortie), (8, ""))
        self.assertEqual(erreur.strip(), "train_auto: template refused: python3 3.10 or newer required to generate it (version 3.9)")

    def test_un_dossier_sans_python3_est_refuse(self):
        dossier = self.base / "sans"
        dossier.mkdir()
        (dossier / "python3.14").write_text("#!/bin/sh\n", encoding="utf-8")
        code, sortie, erreur = self.lancer((3, 14, 0, "final", 0), dossier / "python3.14")
        self.assertEqual((code, sortie), (8, ""))
        self.assertEqual(erreur.strip(), "train_auto : modèle refusé : le dossier de l'interpréteur n'a pas de python3 identique")

    def test_un_python3_qui_est_un_autre_fichier_est_refuse(self):
        dossier = self.base / "autre"
        dossier.mkdir()
        (dossier / "python3.14").write_text("#!/bin/sh\n", encoding="utf-8")
        (dossier / "python3").write_text("#!/bin/sh\necho autre\n", encoding="utf-8")
        code, sortie, erreur = self.lancer((3, 14, 0, "final", 0), dossier / "python3.14")
        self.assertEqual((code, sortie), (8, ""))
        self.assertIn("pas de python3 identique", erreur)

    def test_la_phrase_en_anglais_du_dossier(self):
        dossier = self.base / "sans"
        dossier.mkdir()
        (dossier / "python3.14").write_text("#!/bin/sh\n", encoding="utf-8")
        code, _, erreur = self.lancer((3, 14, 0, "final", 0), dossier / "python3.14", "--language", "en")
        self.assertEqual(code, 8)
        self.assertEqual(erreur.strip(), "train_auto: template refused: the interpreter's folder has no identical python3")

    def test_un_interpreteur_conforme_n_est_pas_refuse(self):
        self.assertIsNone(train_auto.generation_refusal((3, 14, 0, "final", 0), str(self.interpreteur_avec_python3())))
        self.assertIsNone(train_auto.generation_refusal((3, 10, 0, "final", 0), str(self.interpreteur_avec_python3("autre-bon"))))

    def test_un_faux_python_3_9_ne_donne_aucun_modele(self):
        """R-20261110-36 : la génération sous un faux python 3.9 est refusée (8), sans modèle partiel, donc sans interpréteur dans ProgramArguments."""
        faux = self.interpreteur_avec_python3("faux39")
        code, sortie, erreur = self.lancer((3, 9, 18, "final", 0), faux)
        self.assertEqual((code, sortie), (8, ""))
        self.assertNotIn("ProgramArguments", sortie + erreur)
        self.assertNotIn(str(faux), sortie + erreur)

    def test_le_code_8_est_declare_dans_l_en_tete(self):
        self.assertIn("8 modèle launchd refusé : interpréteur de la génération", train_auto.__doc__)


class ArretInfo(unittest.TestCase):
    """D7 : `stop_info()` est la source unique de l'arrêt ; lecture seule, jamais d'exception."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data = Path(self._tmp.name) / "data"
        self.dossier = self.data / "train-auto"
        self.dossier.mkdir(parents=True)
        patcher = mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.data)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def poser_arret(self):
        (self.dossier / "arret").write_text("", encoding="utf-8")

    def journal(self, *enregistrements):
        (self.dossier / "journal.jsonl").write_text("".join(json.dumps(e) + "\n" for e in enregistrements), encoding="utf-8")

    def test_aucun_arret(self):
        self.assertEqual(train_auto.stop_info(), {"format": 1, "state": "absent", "date": None, "raison": None})

    def test_arret_arme_par_un_essai(self):
        self.poser_arret()
        self.journal({"type": "passage", "paris": "2026-11-07 20:00"}, {"type": "arret", "paris": "2026-11-07 21:04", "raison": "65"})
        self.assertEqual(train_auto.stop_info(), {"format": 1, "state": "arrete", "date": "2026-11-07 21:04", "raison": "65"})

    def test_le_dernier_enregistrement_d_arret_compte(self):
        self.poser_arret()
        self.journal({"type": "arret", "paris": "2026-11-06 10:00", "raison": "manuel"}, {"type": "reprendre", "paris": "2026-11-06 11:00"},
                     {"type": "arret", "paris": "2026-11-07 21:04", "raison": "65"})
        self.assertEqual(train_auto.stop_info()["date"], "2026-11-07 21:04")

    def test_raison_nulle(self):
        self.poser_arret()
        self.journal({"type": "arret", "paris": "2026-11-07 21:04", "raison": None})
        self.assertEqual(train_auto.stop_info(), {"format": 1, "state": "arrete", "date": "2026-11-07 21:04", "raison": None})

    def test_fichier_sans_enregistrement_est_illisible(self):
        self.poser_arret()
        self.assertEqual(train_auto.stop_info(), {"format": 1, "state": "illisible", "date": None, "raison": None})
        self.journal({"type": "passage", "paris": "2026-11-07 20:00"})
        self.assertEqual(train_auto.stop_info()["state"], "illisible")

    def test_journal_illisible(self):
        self.poser_arret()
        (self.dossier / "journal.jsonl").mkdir()   # un dossier à la place du fichier : la lecture échoue
        self.assertEqual(train_auto.stop_info(), {"format": 1, "state": "illisible", "date": None, "raison": None})

    def test_date_d_une_autre_forme(self):
        self.poser_arret()
        self.journal({"type": "arret", "paris": "7 novembre 21h04", "raison": "65"})
        self.assertEqual(train_auto.stop_info(), {"format": 1, "state": "illisible", "date": None, "raison": None})

    def test_dossier_de_donnees_non_resolu(self):
        with mock.patch.object(train_auto, "data", side_effect=lab_paths.LabPathsError("not_found")):
            self.assertEqual(train_auto.stop_info(), {"format": 1, "state": "inconnu", "date": None, "raison": None})

    def test_lecture_seule(self):
        self.poser_arret()
        self.journal({"type": "arret", "paris": "2026-11-07 21:04", "raison": "65"})
        avant = sorted((str(f), f.read_bytes()) for f in self.data.rglob("*") if f.is_file())
        train_auto.stop_info()
        self.assertEqual(sorted((str(f), f.read_bytes()) for f in self.data.rglob("*") if f.is_file()), avant)


class ActivationPendantArret(AvecDonnees):
    """D9 : pas d'activation tant que l'arrêt d'urgence existe."""
    avec_essai_launchd = True   # R-20261110-33 (Q23) : modèle installé et passage launchd à 0 posés, la condition essai-launchd est remplie

    def poser_arret(self):
        (self.data / "train-auto").mkdir(parents=True, exist_ok=True)
        (self.data / "train-auto" / "arret").write_text("", encoding="utf-8")

    def test_activer_est_refuse_en_7_et_n_ecrit_rien(self):
        self.enregistrer(serie_verte())
        self.poser_arret()
        r = self.lancer("activer")
        self.assertEqual(r.returncode, 7, r.stderr)
        self.assertIn("train_auto : activation : manque arrêt d'urgence actif (reprendre d'abord)", r.stderr)
        self.assertIn("train_auto : activation refusée : condition non remplie", r.stderr)
        self.assertFalse(self.fichier.exists())
        self.assertEqual(self.journal(), [])

    def test_activer_en_anglais(self):
        self.enregistrer(serie_verte())
        self.poser_arret()
        r = self.lancer("activer", langue="en")
        self.assertEqual(r.returncode, 7)
        self.assertIn("train_auto: activation: missing emergency stop active (resume first)", r.stderr)

    def test_le_statut_json_liste_arret_actif(self):
        self.enregistrer(serie_verte())
        self.poser_arret()
        r = self.lancer("activation", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        statut = json.loads(r.stdout)
        self.assertIn("arret-actif", statut["missing"])
        self.assertFalse(statut["met"])
        self.assertEqual(statut["series"], 5)

    def test_sans_arret_la_serie_verte_active(self):
        self.enregistrer(serie_verte())
        statut = json.loads(self.lancer("activation", "--json").stdout)
        self.assertEqual(statut["missing"], [])
        self.assertTrue(statut["met"])

    def test_un_fichier_d_activation_existant_reste_valide_pendant_l_arret(self):
        self.enregistrer(serie_verte())
        self.assertEqual(self.lancer("activer").returncode, 0)
        self.poser_arret()
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.data)}):
            self.assertEqual(train_auto.activation_state(), "valide")

    def test_les_libelles(self):
        self.assertEqual(train_auto_messages.label("arret-actif", "fr"), "arrêt d'urgence actif (reprendre d'abord)")
        self.assertEqual(train_auto_messages.label("arret-actif", "en"), "emergency stop active (resume first)")


class ContenuDuModele(Temporaire):
    """D11 : `installed_plist_check()` lit le modèle installé ; lecture seule, jamais launchctl. Les interpréteurs sont de faux scripts."""

    def installer(self, modele=None, octets=None):
        dossier = self.maison / "Library" / "LaunchAgents"
        dossier.mkdir(parents=True, exist_ok=True)
        fichier = dossier / f"{train_auto.LABEL}.plist"
        fichier.write_bytes(octets if octets is not None else plistlib.dumps(modele))
        return fichier

    def modele_pour(self, dossier_python):
        return train_auto.plist_model(dossier_python / "python3", "/r", str(self.maison))

    def verifier(self):
        return train_auto.installed_plist_check(home=str(self.maison), run="/r")

    def test_aucun_modele_installe(self):
        self.assertEqual(self.verifier()["state"], "absent")

    def test_modele_illisible(self):
        self.installer(octets=b"ce n'est pas une liste de proprietes")
        self.assertEqual(self.verifier()["state"], "illisible")

    def test_modele_qui_n_est_pas_un_dictionnaire(self):
        self.installer(octets=plistlib.dumps(["a", "b"]))
        self.assertEqual(self.verifier()["state"], "illisible")

    def test_modele_sans_chemin_d_environnement(self):
        bon = self.faux_python("py314", "Python 3.14.0")
        modele = self.modele_pour(bon)
        del modele["EnvironmentVariables"]
        self.installer(modele)
        verdict = self.verifier()
        self.assertEqual(verdict["state"], "different")
        self.assertEqual(verdict["differences"], ["EnvironmentVariables"])

    def test_python3_absent_du_premier_dossier(self):
        vide = self.base / "vide"
        vide.mkdir()
        self.installer(self.modele_pour(vide))
        self.assertEqual(self.verifier()["state"], "python-absent")

    def test_python3_trop_ancien(self):
        ancien = self.faux_python("py39", "Python 3.9.6")
        self.installer(self.modele_pour(ancien))
        self.assertEqual(self.verifier()["state"], "python-ancien")

    def test_version_illisible(self):
        flou = self.faux_python("flou", "quelque chose")
        self.installer(self.modele_pour(flou))
        self.assertEqual(self.verifier()["state"], "python-ancien")

    def test_modele_different_ailleurs(self):
        bon = self.faux_python("py314", "Python 3.14.0")
        modele = self.modele_pour(bon)
        modele["WorkingDirectory"] = "/ailleurs"
        self.installer(modele)
        verdict = self.verifier()
        self.assertEqual((verdict["state"], verdict["differences"]), ("different", ["WorkingDirectory"]))

    def test_modele_conforme(self):
        bon = self.faux_python("py314", "Python 3.14.0")
        modele = self.modele_pour(bon)
        fichier = self.installer(modele)
        verdict = self.verifier()
        self.assertEqual(verdict["state"], "ok")
        self.assertEqual(verdict["differences"], [])
        self.assertEqual(verdict["mtime"], fichier.stat().st_mtime)
        attendu = hashlib.sha256(("PATH=" + modele["EnvironmentVariables"]["PATH"]).encode("utf-8")).hexdigest()[:16]
        self.assertEqual(verdict["env_job"], attendu)
        self.assertRegex(verdict["env_job"], r"^[0-9a-f]{16}$")

    def test_l_interpreteur_de_programarguments_n_est_pas_celui_du_premier_dossier_du_path(self):
        """R-20261110-34 : un modèle dont ProgramArguments garde /usr/bin/python3 (ancien modèle) diffère, par la clé ProgramArguments."""
        bon = self.faux_python("py314", "Python 3.14.0")
        modele = self.modele_pour(bon)
        modele["ProgramArguments"][0] = "/usr/bin/python3"
        self.installer(modele)
        verdict = self.verifier()
        self.assertEqual((verdict["state"], verdict["differences"]), ("different", ["ProgramArguments"]))

    def test_un_autre_nom_du_meme_fichier_que_le_python3_du_path_est_conforme(self):
        """ProgramArguments porte sys.executable (par exemple python3.14) : même chemin réel que le python3 du premier dossier, donc conforme."""
        bon = self.faux_python("py314", "Python 3.14.0")
        (bon / "python3.14").symlink_to(bon / "python3")
        modele = self.modele_pour(bon)
        modele["ProgramArguments"][0] = str(bon / "python3.14")
        self.installer(modele)
        self.assertEqual(self.verifier()["state"], "ok")

    def test_la_version_3_10_suffit(self):
        dix = self.faux_python("py310", "Python 3.10.0")
        self.installer(self.modele_pour(dix))
        self.assertEqual(self.verifier()["state"], "ok")

    def test_le_verdict_ne_porte_aucun_chemin(self):
        bon = self.faux_python("py314", "Python 3.14.0")
        self.installer(self.modele_pour(bon))
        self.assertNotIn(str(self.base), json.dumps(self.verifier(), default=str))

    def test_lecture_seule(self):
        bon = self.faux_python("py314", "Python 3.14.0")
        self.installer(self.modele_pour(bon))
        avant = sorted(str(f) for f in self.base.rglob("*"))
        self.verifier()
        self.assertEqual(sorted(str(f) for f in self.base.rglob("*")), avant)


class PassageSousPythonAncien(AvecAuto):
    """R-20261110-34 : au début d'un passage, train_auto.py vérifie sa propre version ; sous 3.10, attente `python-ancien`, sans arrêt armé."""

    def passer_sous(self, version, *options):
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.environnement(epoch()), clear=True), mock.patch.object(sys, "version_info", version), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = train_auto.main([*options, "pass"])
        return code, sortie.getvalue(), erreur.getvalue()

    def test_un_passage_sous_3_9_attend_sans_armer_l_arret(self):
        code, sortie, erreur = self.passer_sous((3, 9, 6, "final", 0))
        self.assertEqual(code, 0, erreur)
        self.assertIn("train_auto : attente : python3 3.10 ou plus requis", sortie)
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"]), ("attente", "python-ancien"))
        self.assertIsNone(d["arret_arme"])
        self.assertFalse((self.dossier_train() / "arret").exists())
        self.assertNotIn("arret", [x["type"] for x in self.journal()])

    def test_la_phrase_en_anglais(self):
        code, sortie, _ = self.passer_sous((3, 9, 6, "final", 0), "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("train_auto: waiting: python3 3.10 or newer required", sortie)

    def test_sous_3_10_le_passage_decide_normalement(self):
        code, _, erreur = self.passer_sous((3, 10, 0, "final", 0))
        self.assertEqual(code, 0, erreur)
        self.assertNotEqual(self.dernier()["raison"], "python-ancien")

    def test_le_module_se_charge_sous_3_9(self):
        source = (RACINE / "tools" / "train_auto.py").read_text(encoding="utf-8")
        self.assertIn("from __future__ import annotations", source)


def fermeture_des_imports_locaux(depart="train_auto"):
    """Les modules de tools/ importés par `depart`, récursivement (imports de n'importe quel niveau, `depart` compris), dans l'ordre de découverte."""
    outils = RACINE / "tools"
    vus, pile = [], [depart]
    while pile:
        nom = pile.pop(0)
        if nom in vus:
            continue
        vus.append(nom)
        arbre = ast.parse((outils / f"{nom}.py").read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                candidats = [a.name.split(".")[0] for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0 and noeud.module:
                candidats = [noeud.module.split(".")[0]]
            else:
                continue
            pile.extend(c for c in candidats if (outils / f"{c}.py").is_file() and c not in vus)
    return vus


class ImportSous39(unittest.TestCase):
    """R-20261110-37 : train_auto.py, lancé par le python3 du système (3.9), doit s'importer avec toute sa fermeture d'imports locaux, avant sa propre garde de version."""

    def test_la_fermeture_contient_les_modules_attendus(self):
        fermeture = fermeture_des_imports_locaux()
        self.assertEqual(fermeture[0], "train_auto")
        self.assertIn("lab_paths", fermeture)
        self.assertIn("train_auto_messages", fermeture)

    def test_toute_la_fermeture_s_analyse_en_3_9(self):
        for nom in fermeture_des_imports_locaux():
            source = (RACINE / "tools" / f"{nom}.py").read_text(encoding="utf-8")
            try:
                ast.parse(source, filename=f"{nom}.py", feature_version=(3, 9))
            except SyntaxError as e:
                self.fail(f"{nom}.py ne s'analyse pas en 3.9 : {e}")

    def test_l_import_reel_par_le_python3_du_systeme(self):
        systeme = Path("/usr/bin/python3")
        if not systeme.exists():
            self.skipTest("pas de /usr/bin/python3 sur cette machine")
        version = subprocess.run([str(systeme), "-I", "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], capture_output=True, text=True,
                                 stdin=subprocess.DEVNULL, timeout=60).stdout.strip()
        if not re.fullmatch(r"\d+\.\d+", version) or tuple(int(x) for x in version.split(".")) >= (3, 10):
            self.skipTest(f"/usr/bin/python3 est en {version or 'version illisible'} : l'import sous une version de moins de 3.10 n'a pas lieu d'être sur cette machine")
        code = f"import sys; sys.path.insert(0, {str(RACINE / 'tools')!r}); import train_auto"
        r = subprocess.run([str(systeme), "-I", "-c", code], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
