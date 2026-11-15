"""
Tranche 3 d'autonomous-trains-merge, tâche 9.1 (design D5 et D6) : `activation_status`, `activation [--json]`, `activer` (3 en session, 7 quand la condition
n'est pas remplie, fichier écrit par renommage), `desactiver`. Tests sur un faux journal des trains dans un dossier de données jeté ; le texte et le JSON de
`activation` disent la même chose. Aucun dépôt, aucun réseau.

    bash tests/run_all.sh train_auto
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aide_fusion import ligne_passage_launchd, poser_modele_launchd  # noqa: E402  (source commune de l'aide activer())

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402
import train_record  # noqa: E402

AUTO = RACINE / "tools" / "train_auto.py"
TIPS = [f"{n}" * 40 for n in "12345"]
LIBELLES = {"serie": "trains verts de suite sur le conteneur", "deux-branches": "un train de deux branches ou plus",
            "base-ou-front": "un train qui touche la base ou l'interface de Mothra",
            "essai-launchd": "un essai à 0 lancé par launchd depuis le dernier chargement du modèle"}


def champs(sommet, **surcharge):
    base = {"heure": "2026-11-06T10:00:00Z", "code": 0, "sens": "fusionne", "mode": "manuel", "n": 1, "sommets": ["a" * 40],
            "sommet_train": sommet, "main_avant": "9" * 40, "main_apres": sommet, "runner": "conteneur", "base": False, "front": False,
            "politique": [], "duree_s": 600, "etape": ""}
    base.update(surcharge)
    return base


def serie_verte(tips=TIPS):
    """Cinq trains verts dont un de deux branches et un qui touche l'interface (la condition de D5 est remplie)."""
    return [champs(t, n=2 if i == 1 else 1, front=(i == 2)) for i, t in enumerate(tips)]


class AvecDonnees(unittest.TestCase):
    # R-20261110-33 (Q23) : à True, la mise en place pose le faux modèle launchd installé (dossier personnel jeté, HOME) et `lancer` pose, avant `activer` ou `activation`, un faux passage
    # launchd à 0 postérieur au modèle (comme l'aide activer() de aide_fusion) ; la condition `essai-launchd` est alors remplie. Les suites de la condition elle-même
    # (test_essai_launchd.py) gardent False et posent leur propre état. Le passage est posé à la demande, jamais avant : le dossier du journal n'existe pas tant qu'un test ne le crée pas.
    avec_essai_launchd = False

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data = Path(self._tmp.name) / "data"
        self.data.mkdir()
        self.fichier = self.data / "train-auto" / "fusion-active"
        if self.avec_essai_launchd:
            maison = self.maison_launchd = Path(self._tmp.name) / "maison-launchd"
            poser_modele_launchd(maison)
            patcher = mock.patch.dict(os.environ, {"HOME": str(maison)})
            patcher.start()
            self.addCleanup(patcher.stop)

    def poser_passage_launchd(self):
        """Ajoute le faux passage launchd à 0 au journal des passages jetable, une seule fois."""
        dossier = self.data / "train-auto"
        dossier.mkdir(parents=True, exist_ok=True)
        journal = dossier / "journal.jsonl"
        avant = journal.read_text(encoding="utf-8") if journal.exists() else ""
        ligne = ligne_passage_launchd(self.maison_launchd)
        if ligne not in avant:
            journal.write_text(avant + ligne, encoding="utf-8")

    def enregistrer(self, lignes):
        anciens = os.environ.get("PMZILLA_LAB_DATA")
        os.environ["PMZILLA_LAB_DATA"] = str(self.data)
        try:
            for champs_ in lignes:
                train_record.append(champs_)
        finally:
            if anciens is None:
                os.environ.pop("PMZILLA_LAB_DATA", None)
            else:
                os.environ["PMZILLA_LAB_DATA"] = anciens

    def lancer(self, *args, session=False, langue=None):
        if self.avec_essai_launchd and not session and args and args[0] in ("activer", "activation"):
            self.poser_passage_launchd()
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        env["PMZILLA_LAB_DATA"] = str(self.data)
        if session:
            env["CLAUDECODE"] = "1"
        commande = [sys.executable, "-I", str(AUTO)] + (["--language", langue] if langue else []) + list(args)
        r = subprocess.run(commande, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, timeout=120)
        return r

    def journal(self):
        f = self.data / "train-auto" / "journal.jsonl"
        lignes = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []
        # le faux passage launchd n'est qu'une préparation : il n'entre pas dans ce que les tests lisent du journal ; il est reconnu à son marqueur réservé aux tests
        # (R-20261110-34, Q25), jamais à son type : un passage launchd réel écrit par le code reste visible
        return [e for e in lignes if not (self.avec_essai_launchd and e.get("marqueur_test") == "faux-passage-launchd")]


class TestActivationStatus(AvecDonnees):
    """D5 : la série est calculée à chaque appel depuis le journal des trains, jamais stockée."""
    avec_essai_launchd = True

    def enregistrer(self, lignes):
        super().enregistrer(lignes)
        self.poser_passage_launchd()   # ici le calcul est appelé directement (sans `lancer`) : le passage se pose avec l'enregistrement

    def test_aucun_enregistrement(self):
        s = train_auto.activation_status([])
        self.assertEqual(s, {"format": 1, "met": False, "series": 0, "required": 5, "missing": ["serie", "deux-branches", "base-ou-front"], "serie": []})

    def test_cinq_trains_verts_avec_deux_branches_et_interface_remplissent_la_condition(self):
        s = train_auto.activation_status(serie_verte())
        self.assertTrue(s["met"])
        self.assertEqual((s["series"], s["missing"]), (5, []))
        self.assertEqual(s["serie"], TIPS, "les sommets de train, du plus ancien au plus récent")

    def test_il_manque_un_train_de_deux_branches(self):
        s = train_auto.activation_status([champs(t, front=True) for t in TIPS])
        self.assertFalse(s["met"])
        self.assertEqual(s["missing"], ["deux-branches"])

    def test_il_manque_un_train_qui_touche_la_base_ou_l_interface(self):
        s = train_auto.activation_status([champs(t, n=2) for t in TIPS])
        self.assertEqual(s["missing"], ["base-ou-front"])
        s = train_auto.activation_status([champs(t, n=2, base=(t == TIPS[0])) for t in TIPS])
        self.assertEqual(s["missing"], [], "la base compte comme l'interface")

    def test_quatre_trains_ne_suffisent_pas(self):
        s = train_auto.activation_status(serie_verte()[1:])
        self.assertFalse(s["met"])
        self.assertEqual(s["series"], 4)
        self.assertIn("serie", s["missing"])

    def test_un_train_rouge_du_conteneur_remet_la_serie_a_zero(self):
        for code in (69, 70, 71, 82):
            with self.subTest(code=code):
                rouge = champs("f" * 40, code=code, sens="refuse")
                s = train_auto.activation_status(serie_verte() + [rouge] + serie_verte(["6" * 40, "7" * 40]))
                self.assertEqual(s["series"], 2)
                self.assertEqual(s["serie"], ["6" * 40, "7" * 40])

    def test_ce_qui_ne_compte_ni_ne_remet_a_zero(self):
        neutres = [champs("a1" * 20, code=65, sens="refuse"), champs("a2" * 20, sens="essai"), champs("a3" * 20, mode="auto"),
                   champs("a4" * 20, runner="remplace"), champs("a5" * 20, code=70, sens="refuse", runner="remplace"),
                   champs("a6" * 20, code=70, sens="refuse", mode="auto"), champs("a7" * 20, code=143, sens="interrompu")]
        for n in neutres:
            with self.subTest(code=n["code"], sens=n["sens"], mode=n["mode"], runner=n["runner"]):
                s = train_auto.activation_status(serie_verte() + [n])
                self.assertEqual(s["series"], 5, "le train neutre ne remet pas la série à zéro")
                s = train_auto.activation_status(serie_verte()[:2] + [n] + serie_verte()[2:])
                self.assertEqual(s["series"], 5, "et ne la compte pas")

    def test_la_serie_garde_les_cinq_plus_recents(self):
        tips = [f"{n}" * 40 for n in "123456"]
        s = train_auto.activation_status([champs(t, n=2, front=True) for t in tips])
        self.assertEqual(s["serie"], tips[1:])
        self.assertTrue(s["met"])

    def test_lit_le_journal_quand_aucun_enregistrement_n_est_donne(self):
        self.enregistrer(serie_verte())
        os.environ["PMZILLA_LAB_DATA"] = str(self.data)
        self.addCleanup(os.environ.pop, "PMZILLA_LAB_DATA", None)
        self.assertTrue(train_auto.activation_status()["met"])

    def test_ne_lit_aucun_fichier_et_n_en_ecrit_aucun(self):
        train_auto.activation_status([])
        self.assertEqual(list(self.data.rglob("*")), [])


class TestCommandeActivation(AvecDonnees):
    avec_essai_launchd = True

    def test_json_et_texte_disent_la_meme_chose(self):
        self.enregistrer([champs(t, front=(t == TIPS[0])) for t in TIPS[:4]])
        j = json.loads(self.lancer("activation", "--json").stdout)
        t = self.lancer("activation")
        self.assertEqual(t.returncode, 0, t.stderr)
        lignes = t.stdout.splitlines()
        self.assertEqual(lignes[0], f"train_auto : activation : {j['series']} train(s) de suite sur 5 requis")
        self.assertEqual(lignes[1:], [f"train_auto : activation : manque {LIBELLES[code]}" for code in j["missing"]])
        self.assertEqual(j["missing"], ["serie", "deux-branches"])
        self.assertEqual((j["format"], j["met"], j["required"], j["series"]), (1, False, 5, 4))

    def test_condition_remplie_aucune_ligne_manque(self):
        self.enregistrer(serie_verte())
        j = json.loads(self.lancer("activation", "--json").stdout)
        self.assertTrue(j["met"])
        t = self.lancer("activation")
        self.assertEqual(t.stdout.splitlines(), ["train_auto : activation : 5 train(s) de suite sur 5 requis"])

    def test_permis_en_session_et_en_lecture_seule(self):
        self.enregistrer(serie_verte())
        avant = {p: p.read_bytes() for p in self.data.rglob("*") if p.is_file()}
        r = self.lancer("activation", session=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual({p: p.read_bytes() for p in self.data.rglob("*") if p.is_file()}, avant)

    def test_anglais(self):
        r = self.lancer("activation", langue="en")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("train_auto: activation: 0 train(s) in a row out of 5 required", r.stdout)
        self.assertIn("train_auto: activation: missing ", r.stdout)

    def test_journal_illisible_sort_en_4_sans_le_contenu(self):
        self.enregistrer([champs(TIPS[0])])
        with open(self.data / "trains" / "journal.jsonl", "a", encoding="utf-8") as f:
            f.write("pas du json SECRET\n")
        r = self.lancer("activation")
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertNotIn("SECRET", r.stdout + r.stderr)


class TestActiver(AvecDonnees):
    avec_essai_launchd = True

    def test_refuse_en_session(self):
        self.enregistrer(serie_verte())
        r = self.lancer("activer", session=True)
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertFalse(self.fichier.exists())
        self.assertEqual(self.journal(), [])

    def test_condition_non_remplie_sort_en_7_sans_rien_ecrire(self):
        self.enregistrer([champs(t) for t in TIPS[:4]])
        r = self.lancer("activer")
        self.assertEqual(r.returncode, 7, r.stderr)
        sortie = r.stdout + r.stderr
        for code in ("serie", "deux-branches", "base-ou-front"):
            self.assertIn(f"train_auto : activation : manque {LIBELLES[code]}", sortie)
        self.assertIn("train_auto : activation refusée : condition non remplie", sortie)
        self.assertFalse(self.fichier.exists())
        self.assertEqual(self.journal(), [])

    def test_ecrit_le_fichier_valide_par_renommage_et_journalise(self):
        self.enregistrer(serie_verte())
        r = self.lancer("activer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("train_auto : fusion automatique activée", r.stdout)
        donnees = json.loads(self.fichier.read_text(encoding="utf-8"))
        self.assertEqual((donnees["format"], donnees["serie"]), (1, TIPS))
        self.assertRegex(donnees["heure"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(stat.S_IMODE(self.fichier.stat().st_mode), 0o600)
        self.assertEqual([f.name for f in self.fichier.parent.iterdir() if f.name.startswith(".")], [], "aucun fichier temporaire ne reste")
        self.assertEqual([e["type"] for e in self.journal()], ["activer"])
        os.environ["PMZILLA_LAB_DATA"] = str(self.data)
        self.addCleanup(os.environ.pop, "PMZILLA_LAB_DATA", None)
        self.assertTrue(train_auto.activation_valid(), "le fichier écrit est celui que le seul lecteur trouve valide")

    def test_un_passage_launchd_reel_reste_visible_dans_journal(self):
        """R-20261110-34 (Q25) : l'aide journal() ne masque que le faux passage posé par l'aide de test (marqueur réservé aux tests), jamais un passage launchd écrit par le code."""
        self.poser_passage_launchd()
        reel = {"type": "passage", "utc": "2026-11-10T12:00:00Z", "caller": "launchd", "env_job": train_auto.path_fingerprint("/usr/bin:/bin"),
                "essai": {"code": 0, "relance": False, "code2": None, "retirees": []}}
        self.assertNotIn("marqueur_test", reel)
        with open(self.data / "train-auto" / "journal.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(reel) + "\n")
        self.assertEqual(self.journal(), [reel], "le faux passage est masqué, le passage réel reste")

    def test_le_fichier_est_ecrit_par_un_fichier_temporaire_renomme(self):
        source = AUTO.read_text(encoding="utf-8")
        corps = source[source.index("def cmd_activer("):source.index("def cmd_desactiver(")]
        self.assertIn("_atomic_write(", corps)
        self.assertIn("os.replace(temporaire, chemin)", source[source.index("def _atomic_write("):source.index("def append_journal(")])

    def test_ne_touche_ni_l_arret_ni_la_liste(self):
        self.enregistrer(serie_verte())
        dossier = self.data / "train-auto"
        dossier.mkdir()
        (dossier / "arret").write_text("", encoding="utf-8")
        (dossier / "pretes.tsv").write_text("# liste\n", encoding="utf-8")
        self.assertEqual(self.lancer("activer").returncode, 7)
        self.assertTrue((dossier / "arret").exists())
        self.assertEqual((dossier / "pretes.tsv").read_text(encoding="utf-8"), "# liste\n")

    def test_activer_reussi_laisse_la_liste_des_branches_pretes_intacte(self):
        self.enregistrer(serie_verte())
        dossier = self.data / "train-auto"
        dossier.mkdir()
        (dossier / "pretes.tsv").write_text("# liste\n", encoding="utf-8")
        self.assertEqual(self.lancer("activer").returncode, 0)
        self.assertFalse((dossier / "arret").exists())
        self.assertEqual((dossier / "pretes.tsv").read_text(encoding="utf-8"), "# liste\n")


class TestDesactiver(AvecDonnees):
    avec_essai_launchd = True

    def test_retire_le_fichier_journalise_et_ne_touche_ni_l_arret_ni_la_liste(self):
        self.enregistrer(serie_verte())
        self.assertEqual(self.lancer("activer").returncode, 0)
        dossier = self.data / "train-auto"
        (dossier / "arret").write_text("", encoding="utf-8")
        (dossier / "pretes.tsv").write_text("# liste\n", encoding="utf-8")
        r = self.lancer("desactiver")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("train_auto : fusion automatique désactivée", r.stdout)
        self.assertFalse(self.fichier.exists())
        self.assertTrue((dossier / "arret").exists())
        self.assertEqual((dossier / "pretes.tsv").read_text(encoding="utf-8"), "# liste\n")
        self.assertEqual([e["type"] for e in self.journal()], ["activer", "desactiver"])

    def test_deja_desactivee(self):
        r = self.lancer("desactiver")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("train_auto : fusion automatique déjà désactivée", r.stdout)

    def test_permis_en_session_parce_qu_il_ne_fait_que_renforcer(self):
        self.enregistrer(serie_verte())
        self.assertEqual(self.lancer("activer").returncode, 0)
        r = self.lancer("desactiver", session=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.fichier.exists())

    def test_reprendre_n_active_pas_et_desactiver_ne_leve_pas_l_arret(self):
        self.enregistrer(serie_verte())
        self.assertEqual(self.lancer("arret").returncode, 0)
        self.assertEqual(self.lancer("desactiver").returncode, 0)
        self.assertTrue((self.data / "train-auto" / "arret").exists())
        self.assertEqual(self.lancer("reprendre").returncode, 0)
        self.assertFalse(self.fichier.exists(), "reprendre n'active pas")


if __name__ == "__main__":
    unittest.main()
