"""
La politique automatique et le train de l'auteur (autonomous-trains-merge, tâches 3.4 et 3.5, design D2 et D7).

    bash tests/run_all.sh finish_checks

  - train_de_l_auteur : la fonction unique (D2), sur des enregistrements fabriqués ;
  - auto_policy / « policy --json » : une raison par test, l'ordre, le doute qui refuse, la lecture seule, l'absence d'exemption par l'environnement.

Dépôt jetable (aide_depot) ; dossier de données jeté ; la liste prête, l'arrêt, l'activation et le journal des trains sont écrits par les modules qui les lisent.
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
sys.path.insert(0, str(OUTILS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import finish_checks  # noqa: E402
import train_auto  # noqa: E402
import train_ready  # noqa: E402
import train_record  # noqa: E402
import subprocess  # noqa: E402
from aide_depot import AvecDepot  # noqa: E402

LIBELLES = {
    "inactif": "fusion automatique non activée",
    "activation-invalide": "fichier d'activation invalide",
    "arret": "arrêt d'urgence actif",
    "liste-illisible": "liste prête illisible",
    "absente-de-la-liste": "branche absente de la liste prête",
    "sommet-non-atteste": "sommet différent de la liste prête",
    "revue-absente": "revue Opus absente pour ce sommet",
    "train-de-l-auteur": "outillage de fin, runner, preuve, .claude/, CLAUDE.md ou postures : train de l'auteur",
    "plafond": "plus de 3 branches : train de l'auteur",
    "calcul-impossible": "contrôles de fin impossibles",
}
ORDRE = list(LIBELLES)


def enregistrement(juges=(), sensibles=(), touches=None, verdict6="exempt", **plus):
    """Un enregistrement de « branch » réduit à ce que train_de_l_auteur lit."""
    touches = list(juges) + list(sensibles) if touches is None else list(touches)
    r = {"format": 1, "branch": "feat/x", "tip": "a" * 40, "controls": [{"id": "6", "verdict": verdict6, "phrase": "p", "details": []}],
         "runner_proof_touched": [], "protected_touched": touches, "protected_judges": list(juges), "protected_sensitive": list(sensibles), "exit": 0}
    r.update(plus)
    return r


class TrainDeLAuteur(unittest.TestCase):
    def test_une_branche_ordinaire_n_est_pas_un_train_de_l_auteur(self):
        self.assertFalse(finish_checks.train_de_l_auteur(enregistrement()))

    def test_un_fichier_juge(self):
        self.assertTrue(finish_checks.train_de_l_auteur(enregistrement(juges=["tools/finish_checks.py"])))

    def test_le_runner_et_la_preuve_sont_des_fichiers_juges(self):
        protege = (OUTILS / "finish_protected.txt").read_text(encoding="utf-8")
        juges = [m for m, c in finish_checks.classes_proteges(protege).items() if c == "juge"]
        entrees = finish_checks.motifs_proteges((OUTILS / "finish_runner_paths.txt").read_text(encoding="utf-8"))
        for chemin in entrees:
            self.assertTrue(finish_checks.couvert(chemin, juges), chemin)
            self.assertTrue(finish_checks.train_de_l_auteur(enregistrement(juges=[chemin])), chemin)

    def test_un_fichier_sensible_seul_n_est_pas_un_train_de_l_auteur(self):
        self.assertFalse(finish_checks.train_de_l_auteur(enregistrement(sensibles=["tools/flow_views.py"])))

    def test_un_chemin_de_claude(self):
        self.assertTrue(finish_checks.train_de_l_auteur(enregistrement(touches=[".claude/skills/x/SKILL.md"])))
        self.assertTrue(finish_checks.train_de_l_auteur(enregistrement(claude_paths=[".claude/settings.json"])))

    def test_un_fichier_claude_md_a_toute_profondeur(self):
        self.assertTrue(finish_checks.train_de_l_auteur(enregistrement(touches=["CLAUDE.md"])))
        self.assertTrue(finish_checks.train_de_l_auteur(enregistrement(touches=["mothra/CLAUDE.md"])))
        self.assertTrue(finish_checks.train_de_l_auteur(enregistrement(claude_paths=["a/b/c/CLAUDE.md"])))

    def test_un_nom_qui_ressemble_a_claude_md_n_en_est_pas_un(self):
        self.assertFalse(finish_checks.train_de_l_auteur(enregistrement(touches=["docs/CLAUDE.md.bak", "notes/MY-CLAUDE.md"])))

    def test_les_postures_controle_6_applicable(self):
        self.assertTrue(finish_checks.train_de_l_auteur(enregistrement(verdict6="pass")))
        self.assertTrue(finish_checks.train_de_l_auteur(enregistrement(verdict6="refused")))
        self.assertFalse(finish_checks.train_de_l_auteur(enregistrement(verdict6="exempt")))

    def test_le_champ_du_runner_et_de_la_preuve(self):
        """Revue Opus 4.1, constat 5 : un chemin du runner ou de la preuve touché, ou la clé absente (le doute), est un train de l'auteur."""
        self.assertTrue(finish_checks.train_de_l_auteur(enregistrement(runner_proof_touched=["tests/run_all.sh"])))
        sans_cle = enregistrement()
        del sans_cle["runner_proof_touched"]
        self.assertTrue(finish_checks.train_de_l_auteur(sans_cle))
        self.assertFalse(finish_checks.train_de_l_auteur(enregistrement(runner_proof_touched=[])))

    def test_un_enregistrement_incomplet_est_un_train_de_l_auteur(self):
        for r in ({}, {"protected_judges": []}, {"protected_judges": [], "protected_touched": []},
                  enregistrement(controls=[]), enregistrement(protected_judges="x"), None, "texte"):
            self.assertTrue(finish_checks.train_de_l_auteur(r), r)

    def test_une_seule_definition_dans_les_outils(self):
        """Aucun appelant ne garde sa copie : la fonction n'est définie qu'à un endroit de tools/."""
        definitions = [p.name for p in OUTILS.glob("*.py") if "def train_de_l_auteur(" in p.read_text(encoding="utf-8")]
        self.assertEqual(definitions, ["finish_checks.py"])


class AvecPolitique(AvecDepot):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.depot.data)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tip_train = self.depot.git("rev-parse", "HEAD")
        self.dossier = self.depot.data / "train-auto"

    # --- état de la tâche
    def activer(self):
        for n in "12345":
            train_record.append({"heure": "2026-11-06T10:00:00Z", "code": 0, "sens": "fusionne", "mode": "manuel", "n": 2, "sommets": ["a" * 40],
                                 "sommet_train": n * 40, "main_avant": "9" * 40, "main_apres": n * 40, "runner": "conteneur", "base": False,
                                 "front": True, "politique": [], "duree_s": 600, "etape": ""})
        self.dossier.mkdir(parents=True, exist_ok=True)
        fichier = self.dossier / "fusion-active"
        fichier.write_text(json.dumps({"format": 1, "heure": "2026-11-06T12:00:00Z", "serie": [n * 40 for n in "12345"]}), encoding="utf-8")
        os.chmod(fichier, 0o600)

    def lister(self, *lignes):
        """lignes : (branche, sommet, revue)."""
        self.dossier.mkdir(parents=True, exist_ok=True)
        train_ready.write_list([{"branche": b, "sommet": s, "empreinte": "e" * 40, "revue": r, "ajout": "2026-11-06T09:00:00Z"} for b, s, r in lignes])

    def branche(self, nom, fichiers=None):
        return self.depot.branche(nom, fichiers or {f"tools/{nom.split('/')[-1]}.sh": "x\n"})

    def politique(self, branches, tips, env=None):
        return finish_checks.auto_policy(self.depot.travail, self.tip_train, list(branches), list(tips), env)

    def codes(self, resultat):
        return [r["code"] for r in resultat["reasons"]]

    def pret(self, *noms, revue="faite"):
        """Des branches de code prêtes, avec activation valide ; rend (noms, sommets)."""
        tips = [self.branche(n) for n in noms]
        self.activer()
        self.lister(*[(n, t, revue) for n, t in zip(noms, tips)])
        return list(noms), tips


class TestAutorise(AvecPolitique):
    def test_deux_branches_de_code_revue_faite_et_activation_valide(self):
        noms, tips = self.pret("feat/a", "feat/b")
        r = self.politique(noms, tips)
        self.assertEqual(r, {"format": 1, "allowed": True, "reasons": []})

    def test_une_branche_de_documentation_n_exige_pas_la_revue(self):
        tip = self.branche("feat/doc", {"docs/pmzilla/x.md": "x\n"})
        self.activer()
        self.lister(("feat/doc", tip, "non-requise"))
        self.assertTrue(self.politique(["feat/doc"], [tip])["allowed"])

    def test_trois_branches_au_plus(self):
        noms, tips = self.pret("feat/a", "feat/b", "feat/c")
        self.assertTrue(self.politique(noms, tips)["allowed"])


class TestUneRaisonParTest(AvecPolitique):
    def test_inactif(self):
        noms, tips = self.pret("feat/a")
        (self.dossier / "fusion-active").unlink()
        r = self.politique(noms, tips)
        self.assertFalse(r["allowed"])
        self.assertEqual(r["reasons"], [{"code": "inactif"}])

    def test_activation_invalide(self):
        noms, tips = self.pret("feat/a")
        (self.dossier / "fusion-active").write_text("pas du json", encoding="utf-8")
        self.assertEqual(self.politique(noms, tips)["reasons"], [{"code": "activation-invalide"}])

    def test_arret(self):
        noms, tips = self.pret("feat/a")
        (self.dossier / "arret").write_text("", encoding="utf-8")
        r = self.politique(noms, tips)
        self.assertEqual((r["allowed"], r["reasons"]), (False, [{"code": "arret"}]))

    def test_liste_illisible(self):
        noms, tips = self.pret("feat/a")
        (self.dossier / "pretes.tsv").write_text("pas une liste\n", encoding="utf-8")
        self.assertEqual(self.codes(self.politique(noms, tips)), ["liste-illisible"])

    def test_absente_de_la_liste(self):
        noms, tips = self.pret("feat/a")
        self.lister()
        r = self.politique(noms, tips)
        self.assertEqual(r["reasons"], [{"code": "absente-de-la-liste", "branch": "feat/a"}, {"code": "revue-absente", "branch": "feat/a"}])

    def test_sommet_non_atteste(self):
        noms, tips = self.pret("feat/a")
        self.lister(("feat/a", "0" * 40, "faite"))
        r = self.politique(noms, tips)
        self.assertEqual(r["reasons"], [{"code": "sommet-non-atteste", "branch": "feat/a"}, {"code": "revue-absente", "branch": "feat/a"}])

    def test_revue_absente_ligne_non_requise_pour_une_branche_de_code(self):
        noms, tips = self.pret("feat/a", revue="non-requise")
        self.assertEqual(self.politique(noms, tips)["reasons"], [{"code": "revue-absente", "branch": "feat/a"}])

    def test_train_de_l_auteur_le_runner_meme_seul(self):
        tip = self.branche("feat/run", {"tests/run_all.sh": "autre\n"})
        self.activer()
        self.lister(("feat/run", tip, "faite"))
        self.assertEqual(self.politique(["feat/run"], [tip])["reasons"], [{"code": "train-de-l-auteur", "branch": "feat/run"}])

    def test_train_de_l_auteur_un_fichier_juge(self):
        tip = self.branche("feat/juge", {"tools/finish_protected.txt": "tools/hooks/\ntools/finish_branch.sh\ntools/finish_protected.txt\ntests/run_all.sh\ntools/autre.sh\n"})
        self.activer()
        self.lister(("feat/juge", tip, "faite"))
        self.assertEqual(self.codes(self.politique(["feat/juge"], [tip])), ["train-de-l-auteur"])

    def test_train_de_l_auteur_un_chemin_de_claude_meme_hors_liste_protegee(self):
        tip = self.branche("feat/claude", {".claude/commands/x.md": "x\n"})
        self.activer()
        self.lister(("feat/claude", tip, "faite"))
        self.assertEqual(self.codes(self.politique(["feat/claude"], [tip])), ["train-de-l-auteur"])

    def test_train_de_l_auteur_un_claude_md(self):
        tip = self.branche("feat/cmd", {"mothra/CLAUDE.md": "x\n"})
        self.activer()
        self.lister(("feat/cmd", tip, "faite"))
        self.assertEqual(self.codes(self.politique(["feat/cmd"], [tip])), ["train-de-l-auteur"])

    def test_train_de_l_auteur_les_postures(self):
        tip = self.branche("feat/post", {"tests/postures/vocabulaire.yaml": "autre\n"})
        self.activer()
        self.lister(("feat/post", tip, "faite"))
        self.assertEqual(self.politique(["feat/post"], [tip])["reasons"], [{"code": "train-de-l-auteur", "branch": "feat/post"}])

    def test_plafond_quatre_branches(self):
        noms, tips = self.pret("feat/a", "feat/b", "feat/c", "feat/d")
        self.assertEqual(self.politique(noms, tips)["reasons"], [{"code": "plafond"}])

    def test_calcul_impossible_branche_inconnue(self):
        noms, tips = self.pret("feat/a")
        r = self.politique(noms + ["feat/inconnue"], tips + ["1" * 40])
        self.assertFalse(r["allowed"])
        self.assertIn({"code": "calcul-impossible", "branch": "feat/inconnue"}, r["reasons"])

    def test_calcul_impossible_branche_main(self):
        r = self.politique(["main"], [self.tip_train])
        self.assertIn({"code": "calcul-impossible", "branch": "main"}, r["reasons"])

    def test_calcul_impossible_le_sommet_donne_n_est_plus_celui_de_la_branche(self):
        noms, tips = self.pret("feat/a")
        r = self.politique(noms, ["0" * 40])
        self.assertIn({"code": "calcul-impossible", "branch": "feat/a"}, r["reasons"])
        self.assertFalse(r["allowed"])

    def test_calcul_impossible_origin_main_introuvable(self):
        noms, tips = self.pret("feat/a")
        self.depot.git("update-ref", "-d", "refs/remotes/origin/main")
        r = self.politique(noms, tips)
        self.assertFalse(r["allowed"])
        self.assertIn("calcul-impossible", self.codes(r))


class TestDoutEtOrdre(AvecPolitique):
    def test_toutes_les_raisons_sont_listees_dans_l_ordre_de_d7(self):
        tips = [self.branche(f"feat/{n}") for n in "abcd"]
        tip_run = self.branche("feat/run", {"tests/run_all.sh": "autre\n"})
        noms = ["feat/a", "feat/b", "feat/c", "feat/run"]
        tips = tips[:3] + [tip_run]
        (self.dossier).mkdir(parents=True, exist_ok=True)
        (self.dossier / "arret").write_text("", encoding="utf-8")
        self.lister(("feat/a", tips[0], "non-requise"), ("feat/b", "0" * 40, "faite"))
        r = self.politique(noms + ["feat/d"], tips + [tips[0]])
        codes = self.codes(r)
        self.assertEqual(codes, sorted(codes, key=ORDRE.index))
        for attendu in ("inactif", "arret", "absente-de-la-liste", "sommet-non-atteste", "revue-absente", "train-de-l-auteur", "plafond"):
            self.assertIn(attendu, codes)
        self.assertFalse(r["allowed"])

    def test_chaque_doute_donne_allowed_faux(self):
        noms, tips = self.pret("feat/a")
        cas = {
            "aucune branche": ([], []),
            "paires inegales": (noms, tips + tips),
            "sommet hors forme": (noms, ["feat/a"]),
            "doublon": (noms + noms, tips + tips),
        }
        for nom, (b, t) in cas.items():
            with self.subTest(nom):
                r = self.politique(b, t)
                self.assertFalse(r["allowed"])
                self.assertEqual(self.codes(r), ["calcul-impossible"])

    def test_sommet_du_train_inconnu(self):
        noms, tips = self.pret("feat/a")
        r = finish_checks.auto_policy(self.depot.travail, "f" * 40, noms, tips)
        self.assertEqual((r["allowed"], self.codes(r)), (False, ["calcul-impossible"]))

    def test_une_exception_inattendue_refuse(self):
        noms, tips = self.pret("feat/a")
        with mock.patch.object(train_ready, "read_list", side_effect=RuntimeError("boum")):
            r = self.politique(noms, tips)
        self.assertEqual((r["allowed"], self.codes(r)), (False, ["calcul-impossible"]))

    def test_une_exception_dans_l_activation_refuse(self):
        noms, tips = self.pret("feat/a")
        with mock.patch.object(train_auto, "activation_state", side_effect=RuntimeError("boum")):
            r = self.politique(noms, tips)
        self.assertFalse(r["allowed"])

    def test_un_depot_illisible_refuse(self):
        r = finish_checks.auto_policy(self.depot.dossier / "inexistant", "a" * 40, ["feat/a"], ["b" * 40])
        self.assertEqual((r["allowed"], self.codes(r)), (False, ["calcul-impossible"]))


class TestAucuneExemption(AvecPolitique):
    VARIABLES = {"FINISH_TRAIN_CI": "true", "FINISH_TRAIN_RUNNER": "true", "FINISH_TRAIN_MORNING_CHECK": "true", "PMZILLA_SKIP_GREEN_CHECK": "1",
                 "TRAIN_AUTO_NOW": "1", "CLAUDECODE": "", "FINISH_LOCK_TOKEN": "x", "AUTO_POLICY_ALLOW": "1"}

    def test_aucune_variable_ne_rend_la_politique_permissive(self):
        noms, tips = self.pret("feat/a")
        (self.dossier / "fusion-active").unlink()   # inactif
        sans = self.politique(noms, tips)
        with mock.patch.dict(os.environ, self.VARIABLES):
            avec = self.politique(noms, tips)
            avec_env = self.politique(noms, tips, env=dict(self.VARIABLES))
        self.assertEqual(avec, sans)
        self.assertEqual(avec_env, sans)
        self.assertFalse(sans["allowed"])

    def test_le_module_ne_lit_aucune_variable_pour_la_politique(self):
        texte = Path(finish_checks.__file__).read_text(encoding="utf-8")
        debut = texte.index("def auto_policy(")
        fin = texte.index("def policy_exit(")
        corps = texte[debut:fin]
        for interdit in ("os.environ", "getenv", "environ.get"):
            self.assertNotIn(interdit, corps)


class TestLectureSeule(AvecPolitique):
    def instantane(self):
        refs = self.depot.git("for-each-ref", "--format=%(refname) %(objectname)")
        fichiers = {str(p.relative_to(self.depot.dossier)): (p.stat().st_mtime_ns, p.stat().st_size)
                    for p in self.depot.dossier.rglob("*") if p.is_file() and ".git/objects" not in str(p) and not str(p).endswith(".lock")}
        objets = self.depot.git("count-objects", "-v")
        return refs, fichiers, objets

    def test_rien_n_est_ecrit(self):
        noms, tips = self.pret("feat/a", "feat/b")
        (self.dossier / "arret").write_text("", encoding="utf-8")   # un refus complet passe par toutes les lectures
        avant = self.instantane()
        self.politique(noms, tips)
        self.assertEqual(self.instantane(), avant)

    def test_sans_aucun_fichier_de_donnees_rien_n_est_cree(self):
        tip = self.branche("feat/a")
        self.assertFalse(self.dossier.exists())
        self.politique(["feat/a"], [tip])
        self.assertFalse(self.dossier.exists())
        self.assertFalse((self.depot.data / "trains").exists())


class TestLigneDeCommande(AvecPolitique):
    def lancer(self, *args, entree=""):
        r = subprocess.run([sys.executable, "-B", "-I", str(OUTILS / "finish_checks.py"), *args], cwd=self.depot.travail, env=self.depot.env,
                           capture_output=True, text=True, input=entree, timeout=120)
        return r.returncode, r.stdout, r.stderr

    def policy(self, noms, tips, *plus):
        args = ["policy", "--repo", str(self.depot.travail), "--train-tip", self.tip_train]
        for b, t in zip(noms, tips):
            args += ["--branch", b, "--tip", t]
        return self.lancer(*args, *plus)

    def test_autorise_sort_en_0_avec_le_json(self):
        noms, tips = self.pret("feat/a", "feat/b")
        code, sortie, erreur = self.policy(noms, tips, "--json")
        self.assertEqual((code, erreur), (0, ""))
        self.assertEqual(json.loads(sortie), {"format": 1, "allowed": True, "reasons": []})

    def test_refuse_sort_en_1_avec_les_raisons(self):
        noms, tips = self.pret("feat/a")
        (self.dossier / "arret").write_text("", encoding="utf-8")
        code, sortie, _ = self.policy(noms, tips, "--json")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(sortie), {"format": 1, "allowed": False, "reasons": [{"code": "arret"}]})

    def test_calcul_impossible_sort_en_4(self):
        noms, tips = self.pret("feat/a")
        code, sortie, _ = self.policy(noms + ["feat/inconnue"], tips + ["1" * 40], "--json")
        self.assertEqual(code, 4)
        self.assertFalse(json.loads(sortie)["allowed"])

    def test_usage_sort_en_2(self):
        self.assertEqual(self.lancer("policy")[0], 2)
        self.assertEqual(self.lancer("policy", "--train-tip", self.tip_train, "--branch", "feat/a")[0], 2)
        self.assertEqual(self.lancer("policy", "--train-tip", self.tip_train, "--branch", "a", "--branch", "b", "--tip", "1" * 40)[0], 2)

    def test_texte_sans_json(self):
        noms, tips = self.pret("feat/a")
        (self.dossier / "arret").write_text("", encoding="utf-8")
        code, sortie, _ = self.policy(noms, tips)
        self.assertEqual(code, 1)
        self.assertIn("finish_checks : politique : arrêt d'urgence actif", sortie)

    def test_policy_lines_une_ligne_par_raison(self):
        sortie = json.dumps({"format": 1, "allowed": False, "reasons": [{"code": "arret"}, {"code": "revue-absente", "branch": "feat/a"}]})
        code, lignes, erreur = self.lancer("policy-lines", entree=sortie)
        self.assertEqual(code, 0)
        self.assertEqual(lignes.splitlines(), ["arrêt d'urgence actif", "revue Opus absente pour ce sommet (feat/a)"])

    def test_policy_lines_illisible_sort_en_4(self):
        for entree in ("pas du json", json.dumps({"format": 2, "reasons": []}), json.dumps({"format": 1, "reasons": [{"code": "inconnu"}]}), ""):
            with self.subTest(entree=entree):
                self.assertEqual(self.lancer("policy-lines", entree=entree)[0], 4)

    def test_les_libelles_sont_ceux_de_d7(self):
        self.assertEqual(finish_checks.POLITIQUE_LIBELLES, LIBELLES)
        self.assertEqual(list(finish_checks.POLITIQUE_LIBELLES), ORDRE)


if __name__ == "__main__":
    unittest.main()
