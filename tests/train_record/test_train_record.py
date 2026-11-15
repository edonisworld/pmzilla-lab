"""tools/train_record.py : le journal des trains, seul écrivain (change autonomous-trains-merge, tâche 3.1, design D4).

    bash tests/run_all.sh train_record

Dossier de données jeté pour chaque test (PMZILLA_LAB_DATA) ; aucun dépôt, aucun réseau, aucune base, aucun nom.
"""
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
sys.path.insert(0, str(OUTILS))
import train_record  # noqa: E402
import train_record_messages  # noqa: E402
import messages  # noqa: E402

SOMMET_A = "a" * 40
SOMMET_B = "b" * 40
SOMMET_C = "c" * 40
MAIN_AVANT = "1" * 40
MAIN_APRES = "2" * 40


def champs(**surcharge):
    base = {"heure": "2026-11-06T10:00:00Z", "code": 0, "sens": "fusionne", "mode": "manuel", "n": 2,
            "sommets": [SOMMET_A, SOMMET_B], "sommet_train": SOMMET_C, "main_avant": MAIN_AVANT, "main_apres": MAIN_APRES,
            "runner": "conteneur", "base": False, "front": True, "politique": [], "duree_s": 600, "etape": ""}
    base.update(surcharge)
    return base


def arguments(**surcharge):
    """La ligne de commande de `append` pour des champs."""
    c = champs(**surcharge)
    ligne = ["append", "--heure", c["heure"], "--code", str(c["code"]), "--sens", c["sens"], "--mode", c["mode"], "--n", str(c["n"]),
             "--sommets", ",".join(c["sommets"]), "--sommet-train", c["sommet_train"], "--main-avant", c["main_avant"],
             "--main-apres", c["main_apres"], "--runner", c["runner"], "--duree-s", str(c["duree_s"]), "--etape", c["etape"],
             "--politique", ",".join(c["politique"])]
    if c["base"]:
        ligne.append("--base")
    if c["front"]:
        ligne.append("--front")
    return ligne


class AvecDonnees(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data = Path(self._tmp.name) / "data"
        self.data.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("PMZILLA_", "TRAIN_"))}
        self.env["PMZILLA_LAB_DATA"] = str(self.data)
        self._ancien = os.environ.get("PMZILLA_LAB_DATA")
        os.environ["PMZILLA_LAB_DATA"] = str(self.data)
        self.addCleanup(self._restaurer)
        self.journal = self.data / "trains" / "journal.jsonl"

    def _restaurer(self):
        if self._ancien is None:
            os.environ.pop("PMZILLA_LAB_DATA", None)
        else:
            os.environ["PMZILLA_LAB_DATA"] = self._ancien

    def lancer(self, *args, entree=None):
        r = subprocess.run([sys.executable, "-B", "-I", str(OUTILS / "train_record.py"), *args], capture_output=True, text=True, env=self.env,
                           input=entree if entree is not None else "", timeout=60)
        return r.returncode, r.stdout, r.stderr

    def lignes(self):
        return [json.loads(ligne) for ligne in self.journal.read_text(encoding="utf-8").splitlines()]


class TestAjout(AvecDonnees):
    def test_ajoute_une_ligne_json_avec_les_champs_de_d4(self):
        code, sortie, erreur = self.lancer(*arguments())
        self.assertEqual((code, erreur), (0, ""))
        (r,) = self.lignes()
        self.assertEqual(r["format"], 1)
        for cle, valeur in champs().items():
            self.assertEqual(r[cle], valeur, cle)
        self.assertEqual(set(r), {"format", *champs()})

    def test_les_cles_sont_ascii(self):
        self.lancer(*arguments())
        (r,) = self.lignes()
        self.assertTrue(all(cle.isascii() for cle in r))

    def test_un_enregistrement_de_plus_garde_les_precedents_dans_l_ordre(self):
        self.lancer(*arguments(heure="2026-11-06T10:00:00Z", code=70, sens="refuse", etape="porte du conteneur"))
        self.lancer(*arguments(heure="2026-11-06T11:00:00Z"))
        a, b = self.lignes()
        self.assertEqual((a["code"], b["code"]), (70, 0))
        self.assertEqual(a["etape"], "porte du conteneur")

    def test_fichier_et_dossier_reserves_au_proprietaire(self):
        self.lancer(*arguments())
        self.assertEqual(stat.S_IMODE(self.journal.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.journal.parent.stat().st_mode) & 0o077, 0)

    def test_politique_est_la_liste_des_raisons_sur_84(self):
        self.lancer(*arguments(code=84, sens="refuse", mode="auto", politique=["revue-absente", "plafond"], etape="politique automatique"))
        (r,) = self.lignes()
        self.assertEqual(r["politique"], ["revue-absente", "plafond"])
        self.assertEqual(r["mode"], "auto")

    def test_runner_remplace(self):
        self.lancer(*arguments(runner="remplace"))
        (r,) = self.lignes()
        self.assertEqual(r["runner"], "remplace")

    def test_sommets_et_main_vides_acceptes_pour_un_refus_precoce(self):
        code, _, _ = self.lancer(*arguments(code=61, sens="refuse", n=1, sommets=[], sommet_train="", main_avant="", main_apres="",
                                            etape="lancement"))
        self.assertEqual(code, 0)
        (r,) = self.lignes()
        self.assertEqual((r["sommets"], r["sommet_train"], r["main_avant"]), ([], "", ""))


class TestRefusDeChamps(AvecDonnees):
    """Aucun nom accepté : chaque champ a une forme fermée ; un refus sort en 2 et n'écrit rien."""

    def refuse(self, **surcharge):
        code, _, erreur = self.lancer(*arguments(**surcharge))
        self.assertEqual(code, 2, erreur)
        self.assertFalse(self.journal.exists())

    def test_un_nom_de_branche_dans_les_sommets_est_refuse(self):
        self.refuse(sommets=["feat/ma-branche"])

    def test_un_nom_dans_le_sommet_du_train_est_refuse(self):
        self.refuse(sommet_train="feat/x")

    def test_une_etape_avec_un_nom_de_chemin_est_refusee(self):
        self.refuse(etape="feat/ma-branche")

    def test_une_etape_avec_une_cle_de_ticket_est_refusee(self):
        self.refuse(etape="PROJ-1234")

    def test_toutes_les_etapes_de_la_banniere_sont_acceptees(self):
        """Les étapes que tools/finish_train.sh pose dans STEP (une majuscule dans « passe Mac », une apostrophe dans « mise à jour du dossier d'exécution »)."""
        etapes = ("usage", "dossiers du lab", "lancement", "verrou", "garde du matin", "base", "état des références", "admission", "construction",
                  "contrôle des noms", "contrôle 14", "contrôle 6", "paquets npm", "worktree d'intégration", "porte du conteneur", "passe Mac", "question",
                  "relecture des références", "avance rapide", "push", "nettoyage", "vérification finale", "mise à jour du dossier d'exécution",
                  "notes de relais", "politique automatique", "journal des trains", "outils figés", "version de python3")
        # revue Opus 4.1, constat 6 : la liste est celle des STEP="..." de tools/finish_train.sh, jamais une copie qui s'écarte
        texte = (Path(__file__).resolve().parents[2] / "tools" / "finish_train.sh").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r'STEP="([^"]+)"', texte)), set(etapes))
        for etape in etapes:
            with self.subTest(etape=etape):
                code, _, erreur = self.lancer(*arguments(etape=etape))
                self.assertEqual((code, erreur), (0, ""))

    def test_une_raison_de_politique_hors_forme_est_refusee(self):
        self.refuse(politique=["feat/x"])

    def test_sens_inconnu(self):
        self.refuse(sens="gagne")

    def test_mode_inconnu(self):
        self.refuse(mode="semi")

    def test_runner_inconnu(self):
        self.refuse(runner="mac")

    def test_code_hors_plage(self):
        self.refuse(code=256)

    def test_heure_hors_forme(self):
        self.refuse(heure="hier")

    def test_option_inconnue_comme_un_nom_de_branche(self):
        code, _, _ = self.lancer(*arguments(), "--branche", "feat/x")
        self.assertEqual(code, 2)
        self.assertFalse(self.journal.exists())

    def test_argument_positionnel_refuse(self):
        code, _, _ = self.lancer(*arguments(), "feat/x")
        self.assertEqual(code, 2)

    def test_aucune_commande(self):
        self.assertEqual(self.lancer()[0], 2)


class TestPurge(AvecDonnees):
    def ecrire_brut(self, *records):
        self.journal.parent.mkdir(parents=True)
        self.journal.write_text("".join(json.dumps(dict(r, format=1)) + "\n" for r in records), encoding="utf-8")

    def test_l_ajout_retire_d_abord_les_enregistrements_de_plus_d_un_an(self):
        self.ecrire_brut(champs(heure="2025-10-01T10:00:00Z", code=1), champs(heure="2026-01-01T10:00:00Z", code=2))
        code, sortie, _ = self.lancer(*arguments(heure="2026-11-06T10:00:00Z"))
        self.assertEqual(code, 0)
        self.assertEqual([r["code"] for r in self.lignes()], [2, 0])
        self.assertIn("1 enregistrement(s) retiré(s) (plus d'un an)", sortie)

    def test_purge_fonction_rend_le_nombre_retire(self):
        self.ecrire_brut(champs(heure="2025-01-01T00:00:00Z"), champs(heure="2025-02-01T00:00:00Z"), champs(heure="2026-11-01T00:00:00Z"))
        retires = train_record.purge(train_record.parse_time("2026-11-06T00:00:00Z"))
        self.assertEqual(retires, 2)
        self.assertEqual(len(self.lignes()), 1)

    def test_purge_sans_rien_a_retirer_ne_reecrit_pas_le_fichier(self):
        self.ecrire_brut(champs(heure="2026-11-01T00:00:00Z"))
        avant = self.journal.stat().st_mtime_ns
        self.assertEqual(train_record.purge(train_record.parse_time("2026-11-06T00:00:00Z")), 0)
        self.assertEqual(self.journal.stat().st_mtime_ns, avant)

    def test_purge_sans_fichier(self):
        self.assertEqual(train_record.purge(train_record.parse_time("2026-11-06T00:00:00Z")), 0)
        self.assertFalse(self.journal.exists())

    def test_la_limite_est_de_365_jours(self):
        self.ecrire_brut(champs(heure="2025-11-06T00:00:00Z"), champs(heure="2025-11-05T23:59:59Z"))
        retires = train_record.purge(train_record.parse_time("2026-11-06T00:00:00Z"))
        self.assertEqual(retires, 1)


class TestLecture(AvecDonnees):
    def test_read_records_sans_fichier(self):
        self.assertEqual(train_record.read_records(), [])

    def test_read_records_rend_les_enregistrements(self):
        self.lancer(*arguments())
        (r,) = train_record.read_records()
        self.assertEqual(r["sommet_train"], SOMMET_C)

    def test_une_ligne_illisible_nomme_son_numero_jamais_son_contenu(self):
        self.lancer(*arguments())
        with self.journal.open("a", encoding="utf-8") as f:
            f.write("ceci n'est pas du json secret-contenu\n")
        with self.assertRaises(train_record.Unreadable) as c:
            train_record.read_records()
        self.assertEqual(c.exception.line, 2)
        code, sortie, erreur = self.lancer("list")
        self.assertEqual(code, 4)
        self.assertIn("train_record : journal des trains illisible : ligne 2", erreur)
        self.assertNotIn("secret-contenu", sortie + erreur)

    def test_un_ajout_sur_un_journal_illisible_ne_l_ecrase_pas(self):
        self.journal.parent.mkdir(parents=True)
        self.journal.write_text("pas du json\n", encoding="utf-8")
        code, _, erreur = self.lancer(*arguments())
        self.assertEqual(code, 4)
        self.assertEqual(self.journal.read_text(encoding="utf-8"), "pas du json\n")

    def test_un_format_inconnu_est_illisible(self):
        self.journal.parent.mkdir(parents=True)
        self.journal.write_text(json.dumps({"format": 2, "heure": "2026-11-06T10:00:00Z"}) + "\n", encoding="utf-8")
        with self.assertRaises(train_record.Unreadable):
            train_record.read_records()


class TestListe(AvecDonnees):
    def test_list_vide(self):
        code, sortie, _ = self.lancer("list")
        self.assertEqual(code, 0)
        self.assertIn("journal des trains vide", sortie)

    def test_list_json(self):
        self.lancer(*arguments())
        code, sortie, _ = self.lancer("list", "--json")
        self.assertEqual(code, 0)
        donnees = json.loads(sortie)
        self.assertEqual(donnees["format"], 1)
        self.assertEqual(donnees["records"][0]["sommet_train"], SOMMET_C)

    def test_list_texte_une_ligne_par_enregistrement(self):
        self.lancer(*arguments())
        self.lancer(*arguments(heure="2026-11-06T11:00:00Z", code=70, sens="refuse"))
        code, sortie, _ = self.lancer("list")
        self.assertEqual(code, 0)
        self.assertEqual(len(sortie.strip().splitlines()), 2)
        self.assertIn("code 70 (refuse)", sortie)

    def test_list_est_en_lecture_seule(self):
        self.lancer(*arguments())
        avant = self.journal.stat().st_mtime_ns
        self.lancer("list")
        self.lancer("list", "--json")
        self.assertEqual(self.journal.stat().st_mtime_ns, avant)

    def test_langue_anglaise(self):
        code, sortie, _ = self.lancer("--language", "en", "list")
        self.assertEqual(code, 0)
        self.assertIn("train record empty", sortie)


class TestEcritureImpossible(AvecDonnees):
    def test_dossier_de_donnees_non_inscriptible(self):
        faux = Path(self._tmp.name) / "fichier"
        faux.write_text("x", encoding="utf-8")
        self.env["PMZILLA_LAB_DATA"] = str(faux / "data")   # un fichier à la place d'un dossier parent
        code, _, erreur = self.lancer(*arguments())
        self.assertEqual(code, 4)
        self.assertIn("non inscriptible", erreur)
        self.assertNotIn("Traceback", erreur)


class TestUnSeulEcrivain(unittest.TestCase):
    """Le module est le seul à écrire le journal : le CLI n'a que `append` et `list`, le reste est lecture."""

    def test_commandes_du_cli(self):
        parser = train_record.build_parser()
        sous = [a for a in parser._actions if a.dest == "cmd"][0]
        self.assertEqual(set(sous.choices), {"append", "list"})

    def test_le_journal_est_dans_le_dossier_de_donnees_du_lab_pas_dans_celui_de_la_liste_prete(self):
        """D4 : `trains/journal.jsonl` du dossier de données du lab ; la liste prête (train-auto/) reste le seul fichier de ce dossier-là que le train lit."""
        with tempfile.TemporaryDirectory() as d:
            ancien = os.environ.get("PMZILLA_LAB_DATA")
            os.environ["PMZILLA_LAB_DATA"] = d
            try:
                self.assertEqual(train_record.record_path(), Path(d) / "trains" / "journal.jsonl")
            finally:
                if ancien is None:
                    os.environ.pop("PMZILLA_LAB_DATA", None)
                else:
                    os.environ["PMZILLA_LAB_DATA"] = ancien

    def test_catalogues_coherents(self):
        self.assertEqual(messages.check_catalogs(train_record_messages.CATALOGS), [])

    def test_aucune_dependance_hors_du_dossier_des_outils(self):
        texte = (OUTILS / "train_record.py").read_text(encoding="utf-8")
        for module in ("train_auto", "train_ready", "finish_checks", "pilot"):
            self.assertNotIn(f"import {module}", texte)


if __name__ == "__main__":
    unittest.main()
