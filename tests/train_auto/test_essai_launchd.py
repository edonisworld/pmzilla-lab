"""
Faux 65 du train automatique, branche 4 (change train-auto-launchd-env, design D10 et D9) : un essai lancé par launchd avant l'activation. Le passage enregistre `env_job`
(l'empreinte du PATH reçu, jamais le chemin) quand l'appelant est launchd, nul sinon ; `launchd_trial_status(journal, installed)` ; le code manquant `essai-launchd` de
l'activation en lecture réelle. Tout est jeté : dossier de données, dossier personnel et modèle installé temporaires, aucun launchctl, aucun fichier réel.

    bash tests/run_all.sh train_auto
"""
import hashlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from test_activation_commandes import AvecDonnees, TIPS, serie_verte  # noqa: E402  (aide commune de la suite)
from aide_fusion import chemin_faux_modele, poser_modele_launchd  # noqa: E402  (source commune du faux modèle installé)

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402
import train_auto_messages  # noqa: E402

PATH_JOB = "/x/py/bin:/h/.local/share/fnm/aliases/default/bin:/usr/bin:/bin"
EMPREINTE = hashlib.sha256(("PATH=" + PATH_JOB).encode("utf-8")).hexdigest()[:16]
MTIME = train_auto.epoch_of("2026-11-10T10:00:00Z")
AVANT = "2026-11-10T09:00:00Z"
APRES = "2026-11-10T11:00:00Z"
LIBELLE_FR = "un essai à 0 lancé par launchd depuis le dernier chargement du modèle"
LIBELLE_EN = "a trial at 0 launched by launchd since the template was last loaded"


def installe(**surcharge):
    base = {"state": "ok", "env_job": EMPREINTE, "mtime": MTIME, "differences": []}
    base.update(surcharge)
    return base


def passage(utc=APRES, caller="launchd", env_job=EMPREINTE, code=0, relance=False, code2=None, essai=True, **surcharge):
    rec = {"type": "passage", "utc": utc, "caller": caller, "env_job": env_job,
           "essai": {"code": code, "relance": relance, "code2": code2, "retirees": []} if essai else None}
    rec.update(surcharge)
    return rec


class EnvJobDuPassage(unittest.TestCase):
    """D10 : `env_job` est écrit pour un appelant launchd, nul pour un appelant terminal, et ne porte aucun chemin."""

    def enregistrement(self, caller, env):
        ctx = types.SimpleNamespace(clock=types.SimpleNamespace(now=lambda: 1_700_000_000), caller=caller, env=env)
        return train_auto.new_record(ctx)

    def test_launchd_ecrit_l_empreinte_du_chemin_recu(self):
        rec = self.enregistrement("launchd", {"PATH": PATH_JOB})
        self.assertEqual(rec["env_job"], EMPREINTE)
        self.assertRegex(rec["env_job"], r"^[0-9a-f]{16}$")

    def test_terminal_n_ecrit_rien(self):
        rec = self.enregistrement("terminal", {"PATH": PATH_JOB})
        self.assertIn("env_job", rec)
        self.assertIsNone(rec["env_job"])

    def test_aucun_chemin_dans_l_enregistrement(self):
        rec = self.enregistrement("launchd", {"PATH": PATH_JOB})
        texte = json.dumps(rec)
        self.assertNotIn("/x/py/bin", texte)
        self.assertNotIn("fnm", texte)

    def test_l_empreinte_est_celle_du_modele_installe(self):
        self.assertEqual(train_auto.path_fingerprint(PATH_JOB), EMPREINTE)


class EssaiLaunchd(unittest.TestCase):
    """D10 : la condition tient quand un passage launchd a un essai final à 0, l'empreinte du modèle installé et une heure postérieure à sa date de modification."""

    def statut(self, journal, inst=None):
        return train_auto.launchd_trial_status(journal, installe() if inst is None else inst)

    def test_la_condition_tient(self):
        self.assertTrue(self.statut([passage()]))

    def test_aucun_essai_launchd(self):
        self.assertFalse(self.statut([]))

    def test_un_essai_du_terminal_ne_compte_jamais(self):
        self.assertFalse(self.statut([passage(caller="terminal", env_job=None)]))
        self.assertFalse(self.statut([passage(caller="terminal")]), "même avec la bonne empreinte")

    def test_un_essai_final_non_nul(self):
        self.assertFalse(self.statut([passage(code=65)]))

    def test_le_code_final_est_celui_de_la_relance(self):
        self.assertTrue(self.statut([passage(code=62, relance=True, code2=0)]))
        self.assertFalse(self.statut([passage(code=0, relance=True, code2=65)]))

    def test_un_passage_sans_essai_ne_compte_pas(self):
        self.assertFalse(self.statut([passage(essai=False)]))

    def test_une_autre_empreinte(self):
        self.assertFalse(self.statut([passage(env_job="0" * 16)]))

    def test_un_essai_plus_ancien_que_le_modele(self):
        self.assertFalse(self.statut([passage(utc=AVANT)]))

    def test_un_essai_a_la_seconde_de_la_modification_ne_suffit_pas(self):
        self.assertFalse(self.statut([passage(utc="2026-11-10T10:00:00Z")]))

    def test_un_seul_bon_enregistrement_suffit_parmi_d_autres(self):
        self.assertTrue(self.statut([passage(utc=AVANT), passage(code=65), passage(caller="terminal"), passage()]))

    def test_les_enregistrements_qui_ne_sont_pas_des_passages_sont_ignores(self):
        self.assertFalse(self.statut([{"type": "arret", "utc": APRES, "caller": "launchd", "env_job": EMPREINTE, "essai": {"code": 0, "relance": False, "code2": None}}]))

    def test_un_enregistrement_sans_empreinte_ne_compte_pas(self):
        """Les passages d'avant la branche 4 n'ont pas `env_job` : ils ne comptent pas."""
        ancien = passage()
        del ancien["env_job"]
        self.assertFalse(self.statut([ancien]))

    def test_modele_absent(self):
        self.assertFalse(self.statut([passage()], installe(state="absent", env_job=None, mtime=None)))

    def test_modele_illisible(self):
        self.assertFalse(self.statut([passage()], installe(state="illisible", env_job=None)))
        self.assertFalse(self.statut([passage()], installe(state="illisible")), "illisible : la condition manque même avec une empreinte")

    def test_un_modele_qui_n_est_pas_conforme_ne_compte_pas(self):
        """R-20261110-39 (Q27) : seul l'état `ok` du contrôle F6 compte ; `different`, `python-absent` et `python-ancien` font manquer la condition."""
        for etat in ("different", "python-absent", "python-ancien"):
            self.assertFalse(self.statut([passage()], installe(state=etat)), etat)

    def test_aucune_empreinte_nulle_n_est_egale_a_une_autre(self):
        self.assertFalse(self.statut([passage(env_job=None)], installe(env_job=None)))

    def test_une_date_de_modification_inconnue_fait_manquer_la_condition(self):
        self.assertFalse(self.statut([passage()], installe(mtime=None)))

    def test_une_heure_illisible_est_ignoree(self):
        self.assertFalse(self.statut([passage(utc="hier")]))
        self.assertFalse(self.statut([passage(utc=None)]))

    def test_lecture_seule(self):
        journal = [passage()]
        avant = json.dumps(journal)
        self.statut(journal)
        self.assertEqual(json.dumps(journal), avant)


class ActivationSansEssaiLaunchd(AvecDonnees):
    """D10 : en lecture réelle, l'activation manque `essai-launchd` tant que la condition ne tient pas ; `activer` sort en 7 sans rien écrire."""

    def setUp(self):
        super().setUp()
        self.maison = Path(self._tmp.name) / "maison"
        self.agents = self.maison / "Library" / "LaunchAgents"
        self.agents.mkdir(parents=True)
        self.plist = self.agents / f"{train_auto.LABEL}.plist"
        for cle, valeur in (("PMZILLA_LAB_DATA", str(self.data)), ("HOME", str(self.maison))):
            patcher = mock.patch.dict(os.environ, {cle: valeur})
            patcher.start()
            self.addCleanup(patcher.stop)
        (self.data / "train-auto").mkdir()
        self.empreinte = train_auto.path_fingerprint(chemin_faux_modele(self.maison))   # R-20261110-39 : le modèle installé est conforme, son PATH est celui du faux python3

    def installer(self, date=MTIME, surcharge=None):
        """Le modèle CONFORME (état `ok` du contrôle F6), éventuellement avec des clés changées (`surcharge`)."""
        poser_modele_launchd(self.maison, date=date, surcharge=surcharge)

    def ecrire_journal(self, *enregistrements):
        """Les passages posés avec l'empreinte du PATH d'exemple prennent celle du modèle conforme de ce dossier personnel."""
        lignes = [dict(e, env_job=self.empreinte) if e.get("env_job") == EMPREINTE else e for e in enregistrements]
        (self.data / "train-auto" / "journal.jsonl").write_text("".join(json.dumps(e) + "\n" for e in lignes), encoding="utf-8")

    def test_un_modele_installe_different_du_modele_calcule_ne_compte_pas(self):
        """R-20261110-39 (Q27) : une autre clé que le PATH diffère (état `different`) : l'essai launchd, même à 0 et à la bonne empreinte, ne compte pas ; `activer` rend 7."""
        self.enregistrer(serie_verte())
        self.installer(surcharge={"WorkingDirectory": "/ailleurs"})
        self.ecrire_journal(passage())
        self.assertEqual(train_auto.installed_plist_check()["state"], "different")
        self.assertEqual(train_auto.activation_status()["missing"], ["essai-launchd"])
        r = self.lancer("activer")
        self.assertEqual(r.returncode, 7, r.stderr)
        self.assertIn(f"manque {LIBELLE_FR}", r.stderr)
        self.assertFalse(self.fichier.exists())

    def test_un_modele_conforme_et_un_passage_posterieur_remplissent_la_condition(self):
        """R-20261110-39 (Q27) : état `ok`, passage launchd à 0 postérieur à la date du modèle : la condition est remplie."""
        self.enregistrer(serie_verte())
        self.installer()
        self.ecrire_journal(passage())
        self.assertEqual(train_auto.installed_plist_check()["state"], "ok")
        s = train_auto.activation_status()
        self.assertEqual(s["missing"], [])
        self.assertTrue(s["met"])
        self.assertEqual(self.lancer("activer").returncode, 0)

    def test_aucun_modele_installe(self):
        self.enregistrer(serie_verte())
        s = train_auto.activation_status()
        self.assertEqual(s["missing"], ["essai-launchd"])
        self.assertFalse(s["met"])

    def test_modele_installe_sans_essai_launchd(self):
        self.enregistrer(serie_verte())
        self.installer()
        self.assertEqual(train_auto.activation_status()["missing"], ["essai-launchd"])

    def test_avec_l_essai_launchd_la_condition_est_remplie(self):
        self.enregistrer(serie_verte())
        self.installer()
        self.ecrire_journal(passage())
        s = train_auto.activation_status()
        self.assertEqual(s["missing"], [])
        self.assertTrue(s["met"])

    def test_un_essai_du_terminal_ne_remplit_pas_la_condition(self):
        self.enregistrer(serie_verte())
        self.installer()
        self.ecrire_journal(passage(caller="terminal", env_job=None))
        self.assertEqual(train_auto.activation_status()["missing"], ["essai-launchd"])

    def test_un_modele_recharge_apres_l_essai_demande_un_nouvel_essai(self):
        self.enregistrer(serie_verte())
        self.installer(date=train_auto.epoch_of("2026-11-10T12:00:00Z"))
        self.ecrire_journal(passage())
        self.assertEqual(train_auto.activation_status()["missing"], ["essai-launchd"])

    def test_un_modele_avec_un_autre_chemin_demande_un_nouvel_essai(self):
        self.enregistrer(serie_verte())
        self.installer()
        self.ecrire_journal(passage(env_job=train_auto.path_fingerprint("/autre:/usr/bin")))
        self.assertEqual(train_auto.installed_plist_check()["state"], "ok")
        self.assertEqual(train_auto.activation_status()["missing"], ["essai-launchd"])

    def test_le_code_vient_apres_arret_actif(self):
        self.enregistrer(serie_verte())
        (self.data / "train-auto" / "arret").write_text("", encoding="utf-8")
        self.assertEqual(train_auto.activation_status()["missing"], ["arret-actif", "essai-launchd"])

    def test_les_enregistrements_donnes_gardent_le_calcul_pur(self):
        """Comme `arret-actif` : avec des `records` donnés, le calcul ne lit ni le journal des passages ni le modèle installé."""
        self.assertEqual(train_auto.activation_status(serie_verte())["missing"], [])

    def test_activer_est_refuse_en_7_et_n_ecrit_rien(self):
        self.enregistrer(serie_verte())
        self.installer()
        r = self.lancer("activer")
        self.assertEqual(r.returncode, 7, r.stderr)
        self.assertIn(f"train_auto : activation : manque {LIBELLE_FR}", r.stderr)
        self.assertIn("train_auto : activation refusée : condition non remplie", r.stderr)
        self.assertFalse(self.fichier.exists())
        self.assertEqual(self.journal(), [])

    def test_activer_sans_passage_launchd_rend_7(self):
        """R-20261110-32 (Q21) : un modèle installé, aucun passage launchd dans le journal : 7 avec `essai-launchd` manquant."""
        self.enregistrer(serie_verte())
        self.installer()
        r = self.lancer("activer")
        self.assertEqual(r.returncode, 7, r.stderr)
        self.assertIn(f"manque {LIBELLE_FR}", r.stderr)
        self.assertFalse(self.fichier.exists())

    def test_activer_avec_passage_anterieur_au_rechargement_rend_7(self):
        """R-20261110-32 (Q21) : un passage launchd à 0 antérieur à la date de modification du modèle : 7."""
        self.enregistrer(serie_verte())
        self.installer(date=train_auto.epoch_of("2026-11-10T12:00:00Z"))
        self.ecrire_journal(passage())
        r = self.lancer("activer")
        self.assertEqual(r.returncode, 7, r.stderr)
        self.assertIn(f"manque {LIBELLE_FR}", r.stderr)
        self.assertFalse(self.fichier.exists())

    def test_activer_en_anglais(self):
        self.enregistrer(serie_verte())
        self.installer()
        r = self.lancer("activer", langue="en")
        self.assertEqual(r.returncode, 7)
        self.assertIn(f"train_auto: activation: missing {LIBELLE_EN}", r.stderr)

    def test_le_statut_json_liste_essai_launchd(self):
        self.enregistrer(serie_verte())
        self.installer()
        r = self.lancer("activation", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        statut = json.loads(r.stdout)
        self.assertEqual(statut["missing"], ["essai-launchd"])
        self.assertFalse(statut["met"])
        self.assertEqual(statut["series"], 5)
        self.assertEqual(statut["serie"], TIPS)

    def test_activer_reussit_avec_l_essai_launchd(self):
        self.enregistrer(serie_verte())
        self.installer()
        self.ecrire_journal(passage())
        r = self.lancer("activer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.fichier.exists())

    def test_la_validite_d_une_activation_existante_ne_change_pas(self):
        """D9 et D10 : `activation_valid()` ne lit pas la condition ; un fichier valide reste valide sans essai launchd."""
        self.enregistrer(serie_verte())
        self.installer()
        self.ecrire_journal(passage())
        self.assertEqual(self.lancer("activer").returncode, 0)
        self.plist.unlink()
        self.assertEqual(train_auto.activation_state(), "valide")


class LibellesEtEntete(unittest.TestCase):
    def test_les_libelles(self):
        self.assertEqual(train_auto_messages.label("essai-launchd", "fr"), LIBELLE_FR)
        self.assertEqual(train_auto_messages.label("essai-launchd", "en"), LIBELLE_EN)

    def test_le_code_est_declare(self):
        self.assertIn("essai-launchd", train_auto.MISSING_CODES)

    def test_l_en_tete_dit_ce_que_la_regle_remplace_et_son_retrait(self):
        doc = train_auto.__doc__
        self.assertIn("essai-launchd", doc)
        debut = doc.index("essai-launchd")
        extrait = doc[debut:debut + 600]
        self.assertIn("ne remplace rien", extrait)
        self.assertIn("retrait : permanent tant que l'activation existe", extrait)


if __name__ == "__main__":
    unittest.main()
