"""
Tests de tools/range_scan.py (change finish-train-foundations, groupe 2, design D1 à D8).

    uv run python -W ignore -m unittest discover -s tests/range_scan -q -f

Dépôts jetables : un dépôt de travail et un dépôt nu qui tient lieu d'origine (le suivi distant `origin/main` vient d'un `git fetch`),
une fausse liste de noms sensibles, un faux extrait des équipes, un faux fichier d'identifiants et une fausse liste d'exemples
déclarés engagée dans `origin/main`. Les valeurs de secrets sont construites à l'exécution par concaténation : aucun fichier suivi ne
contient une valeur d'une famille de tools/secret_scan.py (tests/secret_scan/test_depot_reel.py le vérifie). Aucun nom réel.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
sys.path.insert(0, str(OUTILS))
import secret_scan  # noqa: E402
import range_scan  # noqa: E402

CORPS = "aB3dE5gH7jK9mN2pQ4rS6tU8vW1xY0zC"
NOM = "Quasarix"                  # nom sensible fictif (liste)
NOM_EXTRAIT = "Vortexia Labs"     # nom fictif de l'extrait des équipes
IDENT = "zorglub-test"            # identifiant personnel fictif


def jeton(suffixe="AbCd"):
    return "gh" + "p_" + CORPS + suffixe


def cle_privee():
    return "-----" + "BEGIN RSA PRIVATE" + " KEY" + "-----"


class Depot:
    """Dépôt de travail jetable, avec origine nue et listes fictives."""

    def __init__(self, racine, construire=True):
        """`construire` : crée le dépôt de zéro (une fois, pour le modèle) ; sinon la racine est une copie du modèle."""
        self.racine = Path(racine)
        self.dossier = self.racine / "depot"
        self.nu = self.racine / "origine.git"
        self.contenu = self.racine / "contenu"
        self.listes = self.racine / "listes"
        self.noms = self.listes / "noms-sensibles.txt"
        if not construire:
            self.git("remote", "set-url", "origin", str(self.nu))
            return
        self.listes.mkdir()
        (self.contenu / ".pmzilla").mkdir(parents=True)
        self.noms.write_text(f"# noms fictifs\n{NOM}\n", encoding="utf-8")
        (self.listes / "equipes-lisibles.yaml").write_text(f"referential_teams:\n  - name: {NOM_EXTRAIT}\n", encoding="utf-8")
        (self.contenu / ".pmzilla" / "identifiants.txt").write_text(IDENT + "\n", encoding="utf-8")
        self.dossier.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Essai")
        self.git("config", "user.email", "essai@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", os.devnull)
        exemples = f"docs/exemple.md {secret_scan.fingerprint(jeton('Decl'))}  # exemple de format\n"
        self.commit({"README.md": "depot d'essai\n", "tools/secret_scan_exemples.txt": exemples}, "initial")
        subprocess.run(["git", "clone", "-q", "--bare", str(self.dossier), str(self.nu)], check=True, env=self.env_git(),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.git("remote", "add", "origin", str(self.nu))
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "-b", "feat/x")

    @staticmethod
    def env_git():
        env = dict(os.environ)
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_MERGE_AUTOEDIT="no")
        return env

    def env_outil(self):
        env = self.env_git()
        env.pop("PMZILLA_NOMS", None)
        env.update(PMZILLA_LAB_SENSITIVE_NAMES=str(self.noms), PMZILLA_LAB_WORKSPACE=str(self.contenu), PYTHONIOENCODING="utf-8")
        return env

    def git(self, *args, env=None):
        fait = subprocess.run(["git", *args], cwd=self.dossier, capture_output=True, env=env or self.env_git())
        if fait.returncode != 0:
            raise AssertionError(f"git {args} : {fait.stderr.decode(errors='replace')}")
        return fait.stdout.decode("utf-8", errors="replace")

    def commit(self, fichiers, message="essai"):
        for chemin, contenu in fichiers.items():
            p = self.dossier / chemin
            if contenu is None:
                p.unlink()
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(contenu if isinstance(contenu, bytes) else contenu.encode("utf-8"))
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.sha()

    def sha(self, rev="HEAD"):
        return self.git("rev-parse", rev).strip()

    def avancer_origine(self, rev="main"):
        """Place origin/main sur la révision donnée (sans réseau)."""
        self.git("update-ref", "refs/remotes/origin/main", self.sha(rev))

    def instantane(self):
        return {"refs": self.git("for-each-ref"), "objets": self.git("count-objects", "-v"),
                "index": (self.dossier / ".git" / "index").read_bytes(), "etat": self.git("status", "--porcelain")}

    def lancer(self, tip, *options):
        commande = [sys.executable, "-B", "-I", str(OUTILS / "range_scan.py"), tip, "--repo", str(self.dossier), *options]
        fait = subprocess.run(commande, capture_output=True, env=self.env_outil(), stdin=subprocess.DEVNULL)
        return fait.returncode, fait.stdout.decode("utf-8"), fait.stderr.decode("utf-8")

    def lancer_json(self, tip, *options):
        code, sortie, erreur = self.lancer(tip, "--json", *options)
        return code, json.loads(sortie), erreur

    def rapport(self, tip="feat/x", branches=()):
        with mock.patch.dict(os.environ, self.env_outil(), clear=True):
            return range_scan.scan_range(self.dossier, tip, list(branches))


MODELE = {}


def setUpModule():
    """Le dépôt de départ est construit une fois ; chaque test en reçoit une copie (les appels à git coûtent le plus)."""
    MODELE["temp"] = tempfile.TemporaryDirectory()
    MODELE["racine"] = Path(MODELE["temp"].name).resolve() / "modele"
    MODELE["racine"].mkdir()
    Depot(MODELE["racine"])


def tearDownModule():
    MODELE["temp"].cleanup()


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        racine = Path(self.temp.name).resolve() / "t"
        shutil.copytree(MODELE["racine"], racine, symlinks=True)
        self.d = Depot(racine, construire=False)

    def trouvailles(self, rapport, kind=None, where=None):
        return [f for f in rapport.findings if (kind is None or f["kind"] == kind) and (where is None or f["where"] == where)]


class CommitParCommit(Base):
    def test_secret_ajoute_puis_retire(self):
        c1 = self.d.commit({"docs/a.txt": f"intro\ntoken = {jeton()}\n"})
        self.d.commit({"docs/a.txt": None}, "retrait")
        r = self.d.rapport()
        self.assertEqual(r.exit, 1)
        trouvees = self.trouvailles(r, "secret")
        self.assertEqual(len(trouvees), 1)
        self.assertEqual((trouvees[0]["file"], trouvees[0]["line"], trouvees[0]["commit"], trouvees[0]["family"]),
                         ("docs/a.txt", 2, c1, secret_scan.JETON_GITHUB))
        code, sortie, erreur = self.d.lancer("feat/x")
        self.assertEqual(code, 1)
        self.assertIn(f"range_scan : secret possible dans docs/a.txt, ligne 2 (jeton GitHub), commit {c1[:7]}", sortie)

    def test_cle_privee_dont_le_corps_est_sur_la_ligne_suivante(self):
        c = self.d.commit({"docs/k.txt": f"avant\n{cle_privee()}\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n"})
        r = self.d.rapport()
        self.assertEqual([(f["file"], f["line"], f["family"], f["commit"]) for f in r.findings], [("docs/k.txt", 2, secret_scan.CLE_PRIVEE, c)])

    def test_nom_ajoute_puis_retire(self):
        c1 = self.d.commit({"docs/b.txt": f"un\ndeux\nchez {NOM} ici\n"})
        self.d.commit({"docs/b.txt": "un\ndeux\n"}, "retrait")
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertEqual(code, 1)
        self.assertIn(f"range_scan : nom sensible dans docs/b.txt, ligne 3, commit {c1[:7]}", sortie)

    def test_nom_de_l_extrait_des_equipes(self):
        self.d.commit({"docs/b.txt": f"equipe {NOM_EXTRAIT}\n"})
        self.assertEqual(len(self.trouvailles(self.d.rapport(), "name")), 1)

    def test_identifiant_ajoute_puis_retire(self):
        c1 = self.d.commit({"docs/c.txt": f"x\ncd /Users/{IDENT.upper()}/travail\n"})
        self.d.commit({"docs/c.txt": None}, "retrait")
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertEqual(code, 1)
        self.assertIn(f"range_scan : identifiant personnel dans docs/c.txt, ligne 2, commit {c1[:7]}", sortie)

    def test_ligne_retiree_n_est_jamais_une_trouvaille(self):
        self.d.git("checkout", "-q", "main")
        self.d.commit({"docs/d.txt": f"{NOM}\nreste\n"}, "ancien")
        self.d.avancer_origine()
        self.d.git("checkout", "-q", "-b", "feat/y")
        self.d.commit({"docs/d.txt": "reste\n"}, "retrait")
        r = self.d.rapport("feat/y")
        self.assertEqual((r.exit, r.findings), (0, []))

    def test_le_numero_de_ligne_est_celui_du_fichier_apres_le_commit(self):
        self.d.commit({"docs/e.txt": "1\n2\n3\n4\n5\n"})
        self.d.commit({"docs/e.txt": f"1\n2\nnouvelle\n3\n4\n{NOM}\n5\n"}, "ajouts")
        trouvees = self.trouvailles(self.d.rapport(), "name")
        self.assertEqual([t["line"] for t in trouvees], [6])

    def test_main_local_en_avance_sur_origin(self):
        self.d.git("checkout", "-q", "main")
        c = self.d.commit({"docs/f.txt": f"{NOM}\n"}, "en avance")     # origin/main n'a pas ce commit
        self.d.git("checkout", "-q", "-b", "feat/z")
        r = self.d.rapport("feat/z")
        self.assertEqual([f["commit"] for f in r.findings], [c])

    def test_la_base_est_origin_main_et_aucune_option_ne_la_change(self):
        code, _, erreur = self.d.lancer("feat/x", "--base", "main")
        self.assertEqual(code, 3)
        self.assertIn("range_scan : usage", erreur)

    def test_plage_vide(self):
        code, sortie, _ = self.d.lancer("main")
        self.assertEqual(code, 0)
        self.assertIn("0 commit(s) lu(s) de origin/main", sortie)
        r = self.d.rapport("main")
        self.assertEqual((r.exit, r.commits), (0, 0))

    def test_origin_main_absent(self):
        self.d.git("update-ref", "-d", "refs/remotes/origin/main")
        code, sortie, erreur = self.d.lancer("feat/x")
        self.assertEqual(code, 3)
        self.assertIn("range_scan : origin/main introuvable", erreur)
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual((code, donnees["error"], donnees["exit"], donnees["format"]), (3, "base_missing", 3, 1))

    def test_revision_inconnue(self):
        code, _, erreur = self.d.lancer("branche-inexistante")
        self.assertEqual(code, 3)
        self.assertIn("range_scan : révision inconnue : branche-inexistante", erreur)
        code, donnees, _ = self.d.lancer_json("branche-inexistante")
        self.assertEqual((code, donnees["error"]), (3, "unknown_tip"))

    def test_revision_inconnue_dont_le_nom_est_sensible_n_est_pas_affichee(self):
        code, sortie, erreur = self.d.lancer(f"{NOM.lower()}-inconnue")
        self.assertEqual(code, 3)
        self.assertNotIn(NOM.lower(), sortie + erreur)

    def test_usage_sans_argument(self):
        fait = subprocess.run([sys.executable, "-B", "-I", str(OUTILS / "range_scan.py")], capture_output=True, env=self.d.env_outil())
        self.assertEqual(fait.returncode, 3)
        self.assertIn("range_scan : usage", fait.stderr.decode())

    def test_les_en_tetes_auteur_et_committer_ne_sont_pas_lus(self):
        env = self.d.env_git()
        env.update(GIT_AUTHOR_NAME=IDENT, GIT_COMMITTER_NAME=NOM)
        (self.d.dossier / "g.txt").write_text("propre\n", encoding="utf-8")
        self.d.git("add", "-A")
        self.d.git("commit", "-q", "-m", "propre", env=env)
        self.assertEqual(self.d.rapport().exit, 0)


class Fusions(Base):
    def test_ligne_injectee_dans_une_fusion(self):
        self.d.commit({"f.txt": "un\ndeux\ntrois\n"}, "base")
        self.d.git("checkout", "-q", "-b", "cote")
        self.d.commit({"g.txt": "g\n"}, "cote")
        self.d.git("checkout", "-q", "feat/x")
        self.d.commit({"f.txt": "un\ndeux modifie\ntrois\n"}, "modif")
        self.d.git("merge", "-q", "--no-ff", "--no-commit", "cote")
        (self.d.dossier / "f.txt").write_text(f"un\ndeux modifie\ntrois\najout {NOM}\n", encoding="utf-8")
        self.d.git("add", "-A")
        self.d.git("commit", "-q", "-m", "fusion avec ajout")
        fusion = self.d.sha()
        r = self.d.rapport()
        self.assertEqual(r.exit, 1)
        trouvees = self.trouvailles(r, "name")
        self.assertEqual([(t["commit"], t["file"], t["line"]) for t in trouvees], [(fusion, "f.txt", 4)])

    def test_fusion_qui_n_apporte_que_des_lignes_de_parent(self):
        self.d.commit({"f.txt": "un\n"}, "base")
        self.d.git("checkout", "-q", "-b", "cote")
        c_cote = self.d.commit({"n.txt": f"chez {NOM}\n"}, "cote")
        self.d.git("checkout", "-q", "feat/x")
        self.d.commit({"h.txt": "autre\n"}, "autre")
        self.d.git("merge", "-q", "--no-ff", "-m", "fusion", "cote")
        fusion = self.d.sha()
        r = self.d.rapport()
        self.assertEqual([f["commit"] for f in r.findings], [c_cote])
        self.assertNotIn(fusion, [f["commit"] for f in r.findings])
        self.assertEqual(r.commits, 4)


class CheminsMessagesBranches(Base):
    def test_nom_dans_le_message(self):
        c = self.d.commit({"docs/x.txt": "propre\n"}, f"chez {NOM} aujourd'hui")
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertEqual(code, 1)
        self.assertIn(f"range_scan : nom sensible dans le message du commit {c[:7]}", sortie)
        self.assertNotIn(NOM, sortie)

    def test_identifiant_dans_le_message(self):
        c = self.d.commit({"docs/x.txt": "propre\n"}, f"dossier de {IDENT}")
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertIn(f"range_scan : identifiant personnel dans le message du commit {c[:7]}", sortie)

    def test_secret_dans_le_message_jamais_accepte_comme_exemple(self):
        c = self.d.commit({"docs/x.txt": "propre\n"}, f"jeton {jeton('Decl')}")
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertEqual(code, 1)
        self.assertIn(f"range_scan : secret possible dans le message du commit {c[:7]} (jeton GitHub)", sortie)

    def test_nom_dans_le_chemin_est_masque(self):
        c = self.d.commit({f"docs/{NOM.lower()}-notes.md": "propre\n"})
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertEqual(code, 1)
        self.assertIn(f"range_scan : nom sensible dans le chemin du fichier n°1 du commit {c[:7]}", sortie)
        self.assertNotIn(NOM.lower(), sortie.lower())
        code, donnees, _ = self.d.lancer_json("feat/x")
        trouvee = donnees["findings"][0]
        self.assertEqual((trouvee["kind"], trouvee["where"]), ("name", "path"))
        self.assertEqual(trouvee["file"], {"masked": True, "reason": "name in path", "index": 1})

    def test_identifiant_et_secret_dans_le_chemin(self):
        self.d.commit({f"docs/{IDENT}.md": "propre\n", f"docs/{jeton()}.md": "propre\n"})
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertIn("identifiant personnel dans le chemin du fichier n°", sortie)
        self.assertIn("secret possible dans le chemin du fichier n°", sortie)
        self.assertNotIn(IDENT, sortie)
        self.assertNotIn(jeton(), sortie)

    def test_trouvaille_de_ligne_dans_un_fichier_au_chemin_sensible(self):
        self.d.commit({f"docs/{NOM.lower()}.md": f"{NOM}\n"})
        code, donnees, _ = self.d.lancer_json("feat/x")
        lignes = [f for f in donnees["findings"] if f["where"] == "line"]
        self.assertEqual(lignes[0]["file"], {"masked": True, "reason": "name in path", "index": 1})
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertIn("nom sensible dans fichier n°1, ligne 1, commit", sortie)

    def test_noms_de_branche_donnes_en_option(self):
        code, sortie, _ = self.d.lancer("feat/x", "--branch", "propre", "--branch", f"feat/{NOM.lower()}", "--branch", f"s/{jeton()}",
                                        "--branch", IDENT)
        self.assertEqual(code, 1)
        self.assertIn("range_scan : nom sensible dans le nom de branche n°2", sortie)
        self.assertIn("range_scan : secret possible dans le nom de branche n°3", sortie)
        self.assertIn("range_scan : identifiant personnel dans le nom de branche n°4", sortie)
        self.assertNotIn("branche n°1", sortie)
        for secret in (NOM.lower(), jeton(), IDENT):
            self.assertNotIn(secret, sortie)

    def test_le_nom_de_la_branche_du_sommet_est_lu(self):
        self.d.git("checkout", "-q", "-b", f"feat/{NOM.lower()}-suite")
        code, sortie, _ = self.d.lancer(f"feat/{NOM.lower()}-suite")
        self.assertEqual(code, 1)
        self.assertIn("nom sensible dans le nom de branche n°1", sortie)
        code, donnees, _ = self.d.lancer_json("HEAD")   # HEAD se lit comme la branche courante : même trouvaille, une seule fois
        self.assertEqual([f["branch_index"] for f in donnees["findings"] if f["where"] == "branch"], [1])

    def test_chemin_non_ascii_affiche_tel_quel(self):
        c = self.d.commit({"docs/été.md": f"{NOM}\n"})
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertIn(f"range_scan : nom sensible dans docs/été.md, ligne 1, commit {c[:7]}", sortie)


class ExemplesDeclares(Base):
    def test_exemple_declare_sur_origin_main_est_accepte(self):
        c = self.d.commit({"docs/exemple.md": f"jeton {jeton('Decl')}\n"})
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertEqual(code, 0)
        self.assertIn(f"range_scan : exemple déclaré accepté : docs/exemple.md, ligne 1 (jeton GitHub), commit {c[:7]}", sortie)
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual(donnees["findings"], [])
        self.assertEqual(donnees["accepted_examples"], [{"commit": c, "file": "docs/exemple.md", "line": 1, "family": secret_scan.JETON_GITHUB}])

    def test_meme_valeur_dans_un_autre_fichier_est_refusee(self):
        self.d.commit({"docs/autre.md": f"jeton {jeton('Decl')}\n"})
        self.assertEqual(self.d.rapport().exit, 1)

    def test_exemple_declare_sur_la_branche_seulement(self):
        valeur = jeton("Neuf")
        self.d.commit({"docs/neuf.md": f"jeton {valeur}\n"}, "ajoute")
        liste = (self.d.dossier / "tools" / "secret_scan_exemples.txt").read_text(encoding="utf-8")
        self.d.commit({"tools/secret_scan_exemples.txt": liste + f"docs/neuf.md {secret_scan.fingerprint(valeur)}  # declare ici\n"}, "declare")
        r = self.d.rapport()
        self.assertEqual(r.exit, 1)
        self.assertEqual(len(self.trouvailles(r, "secret")), 1)
        self.assertEqual(r.accepted_examples, [])

    def test_liste_mal_formee_sur_origin_main(self):
        self.d.git("checkout", "-q", "main")
        self.d.commit({"tools/secret_scan_exemples.txt": "ceci n'est pas une entree\n"}, "liste cassee")
        self.d.avancer_origine()
        self.d.git("checkout", "-q", "feat/x")
        self.d.commit({"docs/x.md": f"jeton {jeton()}\n"})
        code, sortie, erreur = self.d.lancer("feat/x")
        self.assertEqual(code, 2)
        self.assertIn("range_scan : liste des exemples déclarés d'origin/main mal formée : vérification impossible", erreur)
        self.assertEqual(sortie, "")
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual((code, donnees["error"]), (2, "examples_list_malformed"))

    def test_liste_absente_d_origin_main_vaut_ensemble_vide(self):
        self.d.git("checkout", "-q", "main")
        self.d.commit({"tools/secret_scan_exemples.txt": None}, "sans liste")
        self.d.avancer_origine()
        self.d.git("checkout", "-q", "feat/x")
        self.d.commit({"docs/exemple.md": f"jeton {jeton('Decl')}\n"})
        self.assertEqual(self.d.rapport().exit, 1)


class FichiersNonExamines(Base):
    def test_fichier_binaire(self):
        c = self.d.commit({"bin/x.dat": b"\x00\x01\x02 " + NOM.encode() + b"\x00"})
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertEqual(code, 0)
        self.assertIn(f"range_scan : non examiné (binaire) : bin/x.dat, commit {c[:7]}", sortie)
        self.assertIn("1 fichier(s) non examiné(s) (binaire : 1, taille : 0)", sortie)

    def test_gros_fichier_avec_un_secret_et_un_nom(self):
        lignes = ["x" * 99] * 10_100
        lignes[2] = f"jeton {jeton()}"
        lignes[3] = f"chez {NOM}"
        texte = "\n".join(lignes) + "\n"
        # R-20261107-33 point 1 (a) : plus de limite de taille, un fichier de plus de 1 Mo est examiné en entier
        self.assertGreater(len(texte), 1_000_000)
        self.d.commit({"docs/gros.txt": texte})
        r = self.d.rapport()
        self.assertEqual(r.exit, 1)
        self.assertEqual(sorted((f["kind"], f["line"]) for f in r.findings), [("name", 4), ("secret", 3)])
        self.assertEqual(r.not_examined["size"], 0)
        self.assertEqual(r.not_examined["files"], [])
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertNotIn("dépasse 1 Mo", sortie)
        self.assertIn("(binaire : 0, taille : 0)", sortie)

    def test_nom_et_secret_au_dela_de_1_mo_sont_trouves(self):
        lignes = ["x" * 99] * 10_100 + [f"jeton {jeton()}", f"chez {NOM}"]
        texte = "\n".join(lignes) + "\n"
        self.assertGreater(len(texte.encode()), 1_000_000)
        self.d.commit({"docs/gros2.txt": texte})
        r = self.d.rapport()
        self.assertEqual(r.exit, 1)
        self.assertEqual(sorted((f["kind"], f["line"]) for f in r.findings), [("name", 10_102), ("secret", 10_101)])

    def test_le_fichier_non_examine_au_chemin_sensible_est_masque(self):
        self.d.commit({f"bin/{NOM.lower()}.dat": b"\x00\x00"})
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertIn("non examiné (binaire) : fichier n°1, commit", sortie)
        self.assertNotIn(NOM.lower(), sortie.lower())


class ListesEtCodes(Base):
    def test_liste_des_noms_absente(self):
        self.d.noms.unlink()
        self.d.commit({"docs/x.md": f"jeton {jeton()}\n"})
        code, sortie, erreur = self.d.lancer("feat/x")
        self.assertEqual(code, 2)
        self.assertIn("range_scan : liste des noms sensibles absente : vérification impossible, refus par défaut", erreur)
        self.assertEqual(sortie, "")
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual((code, donnees["error"]), (2, "names_list_absent"))

    def test_liste_des_noms_illisible(self):
        self.d.noms.write_bytes(b"\xff\xfe\x00\xd8 pas de l'utf-8 \xff")
        code, _, erreur = self.d.lancer("feat/x")
        self.assertEqual(code, 2)
        self.assertIn("liste des noms sensibles illisible : vérification impossible, refus par défaut", erreur)
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual(donnees["error"], "names_list_unreadable")

    def test_identifiants_illisibles(self):
        (self.d.dossier / ".pmzilla").mkdir()
        (self.d.dossier / ".pmzilla" / "cases.yaml").write_bytes(b"author: \xff\xfe\n")
        code, sortie, erreur = self.d.lancer("feat/x")
        self.assertEqual(code, 2)
        self.assertIn("range_scan : identifiants personnels illisibles : vérification impossible", erreur)
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual(donnees["error"], "identifiers_unreadable")

    def test_liste_vide_avertit_et_cherche_encore_les_secrets(self):
        self.d.noms.write_text("# rien\n", encoding="utf-8")
        (self.d.listes / "equipes-lisibles.yaml").unlink()
        self.d.commit({"docs/x.md": f"jeton {jeton()}\nchez {NOM}\n"})
        code, sortie, erreur = self.d.lancer("feat/x")
        self.assertEqual(code, 1)
        self.assertIn("range_scan : garde-fou des noms inactif : liste vide", erreur)
        self.assertIn("secret possible dans docs/x.md, ligne 1", sortie)
        self.assertNotIn("nom sensible", sortie)
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual(donnees["warnings"], ["empty_names_list"])

    def test_code_zero_sur_une_plage_propre(self):
        self.d.commit({"docs/x.md": "rien a signaler\n"})
        code, sortie, erreur = self.d.lancer("feat/x")
        self.assertEqual((code, erreur), (0, ""))
        self.assertIn("1 commit(s) lu(s) de origin/main", sortie)
        self.assertIn("0 secret(s), 0 nom(s), 0 identifiant(s), 0 fichier(s) non examiné(s) (binaire : 0, taille : 0)", sortie)

    def test_resume_toujours_en_derniere_ligne(self):
        self.d.commit({"docs/x.md": f"chez {NOM}\n", "bin/y.dat": b"\x00"})
        _, sortie, _ = self.d.lancer("feat/x")
        lignes = sortie.strip().splitlines()
        self.assertRegex(lignes[-1], r"^range_scan : 1 commit\(s\) lu\(s\) de origin/main [0-9a-f]{7} à [0-9a-f]{7} : 0 secret\(s\), 1 nom\(s\)")
        self.assertTrue(all(l.startswith("range_scan : ") for l in lignes))

    def test_erreur_inattendue_dit_le_type_seulement(self):
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.object(range_scan, "scan_range", side_effect=RuntimeError(f"texte secret {NOM}")), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = range_scan.main(["feat/x", "--repo", str(self.d.dossier)])
        self.assertEqual(code, 3)
        self.assertIn("range_scan : erreur inattendue (RuntimeError)", erreur.getvalue())
        self.assertNotIn(NOM, sortie.getvalue() + erreur.getvalue())
        self.assertNotIn("Traceback", sortie.getvalue() + erreur.getvalue())

    def test_erreur_inattendue_en_json(self):
        sortie = io.StringIO()
        with mock.patch.object(range_scan, "scan_range", side_effect=KeyError("x")), contextlib.redirect_stdout(sortie), \
                contextlib.redirect_stderr(io.StringIO()):
            code = range_scan.main(["feat/x", "--repo", str(self.d.dossier), "--json"])
        donnees = json.loads(sortie.getvalue())
        self.assertEqual((code, donnees["error"], donnees["exit"], donnees["format"]), (3, "unexpected:KeyError", 3, 1))


class SortieEtFonction(Base):
    def plante(self):
        self.d.commit({f"docs/{NOM.lower()}-p.md": f"jeton {jeton()}\nchez {NOM}\ncd /{IDENT}/x\n"}, f"message {NOM} {IDENT} {jeton('Msg1')}")
        return [NOM, NOM.lower(), IDENT, jeton(), jeton("Msg1"), f"feat/{NOM.lower()}", f"s/{jeton('Br01')}"]

    def test_sentinelle_jamais_imprimee(self):
        sentinelles = self.plante()
        branches = ["--branch", f"feat/{NOM.lower()}", "--branch", f"s/{jeton('Br01')}"]
        sentinelles.append(jeton("Br01"))
        for option in ((), ("--json",)):
            code, sortie, erreur = self.d.lancer("feat/x", *branches, *option)
            self.assertEqual(code, 1)
            for s in sentinelles:
                self.assertNotIn(s, sortie, option)
                self.assertNotIn(s, erreur, option)
                self.assertNotIn(s.lower(), (sortie + erreur).lower(), option)

    def test_meme_resultat_en_texte_et_en_json(self):
        self.plante()
        self.d.commit({"bin/z.dat": b"\x00", "docs/v.md": f"chez {NOM}\n"}, "suite")
        code_t, sortie, _ = self.d.lancer("feat/x")
        code_j, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual(code_t, code_j)
        self.assertEqual(donnees["exit"], code_j)
        self.assertEqual(donnees["format"], 1)
        self.assertEqual(donnees["base"]["ref"], "origin/main")
        self.assertEqual(donnees["tip"], self.d.sha())
        self.assertEqual(donnees["commits"], 2)
        nombre = {k: sum(1 for f in donnees["findings"] if f["kind"] == k) for k in ("secret", "name", "identifier")}
        self.assertIn(f"{nombre['secret']} secret(s), {nombre['name']} nom(s), {nombre['identifier']} identifiant(s), "
                      f"{donnees['not_examined']['binary'] + donnees['not_examined']['size']} fichier(s) non examiné(s)", sortie)
        self.assertEqual(sortie.count("range_scan : nom sensible dans"), sum(1 for f in donnees["findings"] if f["kind"] == "name"))
        for cle in ("kind", "where", "commit", "file", "line", "family", "branch_index"):
            self.assertIn(cle, donnees["findings"][0])

    def test_appel_de_la_fonction_sans_rien_imprimer(self):
        c = self.d.commit({"docs/x.md": f"chez {NOM}\n"})
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            r = self.d.rapport()
        self.assertEqual((sortie.getvalue(), erreur.getvalue()), ("", ""))
        self.assertEqual([(f["kind"], f["commit"], f["file"], f["line"]) for f in r.findings], [("name", c, "docs/x.md", 1)])
        self.assertEqual(r.to_dict()["exit"], 1)

    def test_lecture_seule(self):
        self.plante()
        avant = self.d.instantane()
        self.d.lancer("feat/x", "--branch", "x")
        self.d.lancer("feat/x", "--json")
        self.assertEqual(self.d.instantane(), avant)

    def test_rien_n_est_ecrit_dans_le_dossier_de_travail(self):
        self.plante()
        def fichiers():
            return sorted(p.relative_to(self.d.racine).as_posix() for p in self.d.racine.rglob("*")
                          if p.is_file() and "origine.git" not in p.parts and ".git" not in p.parts)
        avant = fichiers()
        self.d.lancer("feat/x")
        self.assertEqual(fichiers(), avant)


class CorrectionsDeRevue(Base):
    """Revue Opus de la branche : objets de remplacement, attributs, sentinelle des listes, sous-modules, base résolue, message brut."""

    def test_objet_de_remplacement_n_aveugle_pas_le_scan(self):
        self.d.git("checkout", "-q", "-b", "alt")
        propre = self.d.commit({"docs/a.md": "propre\n"}, "propre")
        self.d.git("checkout", "-q", "feat/x")
        sale = self.d.commit({"docs/a.md": f"token = {jeton()}\n"}, "sale")
        self.d.git("replace", sale, propre)
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertEqual(code, 1)
        self.assertIn("secret possible dans docs/a.md, ligne 1", sortie)

    def test_replace_ref_base_de_l_environnement_est_ignore(self):
        self.d.git("checkout", "-q", "-b", "alt")
        propre = self.d.commit({"docs/a.md": "propre\n"}, "propre")
        self.d.git("checkout", "-q", "feat/x")
        sale = self.d.commit({"docs/a.md": f"token = {jeton()}\n"}, "sale")
        self.d.git("update-ref", "refs/autres/" + sale, propre)    # replace placé sous une autre base
        env = self.d.env_outil()
        env["GIT_REPLACE_REF_BASE"] = "refs/autres/"
        fait = subprocess.run([sys.executable, "-B", "-I", str(OUTILS / "range_scan.py"), "feat/x", "--repo", str(self.d.dossier)],
                              capture_output=True, env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(fait.returncode, 1)

    def test_attributs_n_aveuglent_pas_le_scan(self):
        (self.d.dossier / ".gitattributes").write_text("* -diff\n", encoding="utf-8")
        (self.d.dossier / ".git" / "info").mkdir(exist_ok=True)
        (self.d.dossier / ".git" / "info" / "attributes").write_text("*.md binary\n", encoding="utf-8")
        c = self.d.commit({".gitattributes": "* -diff\n*.txt binary\n", "docs/a.md": f"token = {jeton()}\n", "docs/b.txt": f"chez {NOM}\n"})
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertEqual(code, 1)
        self.assertIn(f"range_scan : secret possible dans docs/a.md, ligne 1 (jeton GitHub), commit {c[:7]}", sortie)
        self.assertIn(f"range_scan : nom sensible dans docs/b.txt, ligne 1, commit {c[:7]}", sortie)
        self.assertNotIn("non examiné (binaire)", sortie)

    def test_l_octet_nul_reste_le_seul_binaire(self):
        (self.d.dossier / ".gitattributes").write_text("* -diff\n", encoding="utf-8")
        self.d.commit({".gitattributes": "* -diff\n", "bin/y.dat": b"\x00\x01"})
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertIn("non examiné (binaire) : bin/y.dat", sortie)

    def test_sentinelle_du_dossier_de_travail_absent_jamais_sur_stderr(self):
        sentinelle = "sentinelle-zorg-9f3"
        self.d.commit({"docs/x.md": "propre\n"})
        env = self.d.env_outil()
        env["PMZILLA_LAB_WORKSPACE"] = str(self.d.racine / sentinelle / "absent")
        for option in ((), ("--json",)):
            fait = subprocess.run([sys.executable, "-B", "-I", str(OUTILS / "range_scan.py"), "feat/x", "--repo", str(self.d.dossier), *option],
                                  capture_output=True, env=env, stdin=subprocess.DEVNULL)
            self.assertNotIn(sentinelle, fait.stderr.decode("utf-8", errors="replace"), option)
            self.assertNotIn(sentinelle, fait.stdout.decode("utf-8", errors="replace"), option)

    def test_listes_sous_redirection_de_stderr(self):
        def bavarde(*_a, **_k):
            print("sentinelle-liste", file=sys.stderr)
            raise SystemExit(1)
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.d.env_outil(), clear=True), \
                mock.patch.object(range_scan.commit_names_scan, "motifs_des_listes", side_effect=bavarde), \
                contextlib.redirect_stderr(erreur), contextlib.redirect_stdout(sortie):
            with contextlib.suppress(SystemExit):
                range_scan._listes(str(self.d.dossier), str(self.d.dossier), self.d.sha("origin/main"))
        self.assertNotIn("sentinelle-liste", erreur.getvalue())

    def test_sous_module_au_chemin_sensible(self):
        self.d.git("update-index", "--add", "--cacheinfo", f"160000,{self.d.sha()},docs/{NOM.lower()}-sub")
        self.d.git("commit", "-q", "-m", "sous-module")
        c = self.d.sha()
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertEqual(code, 1)
        self.assertIn(f"range_scan : nom sensible dans le chemin du fichier n°1 du commit {c[:7]}", sortie)
        self.assertNotIn(NOM.lower(), sortie.lower())

    def test_liste_des_exemples_lue_par_le_sha_de_la_base(self):
        self.d.commit({"docs/x.md": "propre\n"})
        appels = []
        vrai = range_scan._git

        def espion(repo, *args, **kw):
            appels.append(args)
            return vrai(repo, *args, **kw)
        base = self.d.sha("origin/main")
        with mock.patch.dict(os.environ, self.d.env_outil(), clear=True), mock.patch.object(range_scan, "_git", espion):
            range_scan.scan_range(self.d.dossier, "feat/x", [])
        self.assertTrue(any(f"{base}:{secret_scan.LISTE_EXEMPLES}" in a for a in appels), appels)
        self.assertFalse(any(f"{range_scan.REF_BASE}:{secret_scan.LISTE_EXEMPLES}" in a for a in appels))

    def test_message_lu_en_brut_malgre_show_signature(self):
        self.d.git("config", "log.showSignature", "true")
        c = self.d.commit({"docs/x.md": "propre\n"}, f"chez {NOM} aujourd'hui")
        code, sortie, _ = self.d.lancer("feat/x")
        self.assertIn(f"range_scan : nom sensible dans le message du commit {c[:7]}", sortie)

    def test_en_tete_de_signature_n_est_pas_le_message(self):
        arbre = self.d.git("rev-parse", "HEAD^{tree}").strip()
        parent = self.d.sha()
        brut = (f"tree {arbre}\nparent {parent}\nauthor Essai <essai@example.invalid> 1700000000 +0000\n"
                f"committer Essai <essai@example.invalid> 1700000000 +0000\n"
                f"gpgsig -----BEGIN PGP SIGNATURE-----\n \n {NOM}\n -----END PGP SIGNATURE-----\n\nmessage propre\n")
        fichier = self.d.racine / "commit-brut.txt"
        fichier.write_text(brut, encoding="utf-8")
        sha = self.d.git("hash-object", "-t", "commit", "-w", "--literally", str(fichier)).strip()
        self.d.git("update-ref", "refs/heads/feat/x", sha)
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual([f for f in donnees["findings"] if f["where"] == "message"], [])

    def test_sommet_donne_sous_la_forme_refs_heads(self):
        nom = f"feat/{NOM.lower()}-suite"
        self.d.git("checkout", "-q", "-b", nom)
        code, sortie, _ = self.d.lancer(f"refs/heads/{nom}")
        self.assertEqual(code, 1)
        self.assertIn("nom sensible dans le nom de branche n°1", sortie)
        self.assertNotIn(NOM.lower(), sortie.lower())


class CorrectionsDeControle(Base):
    """Revue de contrôle Opus : environnement hérité, dossier de départ, fermé par défaut, encodage du message, nom court du sommet."""

    def lancer_avec(self, env_en_plus, tip="feat/x", repo=None):
        env = self.d.env_outil()
        env.update(env_en_plus)
        fait = subprocess.run([sys.executable, "-B", "-I", str(OUTILS / "range_scan.py"), tip, "--repo", str(repo or self.d.dossier)],
                              capture_output=True, env=env, stdin=subprocess.DEVNULL)
        return fait.returncode, fait.stdout.decode("utf-8", errors="replace")

    def test_git_literal_pathspecs_herite_n_aveugle_pas_le_scan(self):
        self.d.commit({"docs/a.md": f"token = {jeton()}\n"})
        for variable in ("GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS", "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS"):
            code, sortie = self.lancer_avec({variable: "1"})
            self.assertEqual(code, 1, variable)
            self.assertIn("secret possible dans docs/a.md, ligne 1", sortie, variable)

    def test_repo_pointe_sur_un_sous_dossier(self):
        self.d.commit({"docs/a.md": f"token = {jeton()}\n"})
        code, sortie = self.lancer_avec({}, repo=self.d.dossier / "docs")
        self.assertEqual(code, 1)
        self.assertIn("secret possible dans docs/a.md, ligne 1", sortie)

    def test_fichier_sans_en_tete_de_diff_est_un_echec_de_git(self):
        self.d.commit({"docs/a.md": f"token = {jeton()}\n"})
        vrai = range_scan._git

        def aveugle(repo, *args, **kw):
            if "-p" in args:
                return mock.Mock(stdout=b"", returncode=0)
            return vrai(repo, *args, **kw)
        with mock.patch.dict(os.environ, self.d.env_outil(), clear=True), mock.patch.object(range_scan, "_git", aveugle):
            rapport = range_scan.scan_range(self.d.dossier, "feat/x", [])
        self.assertEqual((rapport.exit, rapport.error), (3, "git_failure"))

    def test_variables_de_depot_heritees_sont_ignorees(self):
        self.d.commit({"docs/a.md": f"token = {jeton()}\n"})
        autre = self.d.racine / "autre"
        autre.mkdir()
        subprocess.run(["git", "init", "-q", str(autre)], check=True, env=self.d.env_git())
        env = {"GIT_DIR": str(autre / ".git"), "GIT_WORK_TREE": str(autre), "GIT_INDEX_FILE": str(autre / ".git" / "index"),
               "GIT_COMMON_DIR": str(autre / ".git"), "GIT_OBJECT_DIRECTORY": str(autre / ".git" / "objects")}
        code, sortie = self.lancer_avec(env)
        self.assertEqual(code, 1)
        self.assertIn("secret possible dans docs/a.md, ligne 1", sortie)

    def commit_brut(self, entetes, message):
        arbre = self.d.git("rev-parse", "HEAD^{tree}").strip()
        tete = (f"tree {arbre}\nparent {self.d.sha()}\nauthor Essai <essai@example.invalid> 1700000000 +0000\n"
                f"committer Essai <essai@example.invalid> 1700000000 +0000\n{entetes}\n").encode("ascii")
        fichier = self.d.racine / "commit-brut.bin"
        fichier.write_bytes(tete + message)
        sha = self.d.git("hash-object", "-t", "commit", "-w", "--literally", str(fichier)).strip()
        self.d.git("update-ref", "refs/heads/feat/x", sha)

    def test_message_lu_selon_son_encodage_declare(self):
        self.commit_brut("encoding UTF-16LE\n", f"chez {NOM}\n".encode("utf-16-le"))
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual(code, 1)
        self.assertEqual([f["kind"] for f in donnees["findings"] if f["where"] == "message"], ["name"])

    def test_encodage_inconnu_ou_message_indecodable_est_un_echec_de_git(self):
        self.commit_brut("encoding codec-inexistant\n", b"propre\n")
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual((code, donnees["error"]), (3, "git_failure"))
        self.commit_brut("encoding UTF-16LE\n", b"\xff\xfe\xfd")
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual((code, donnees["error"]), (3, "git_failure"))

    def fusion_de_deux_cotes(self, ligne_cote, ligne_ici):
        """Chaque côté modifie une ligne différente du même fichier ; la fusion est propre (aucun conflit)."""
        base = "un\ndeux\ntrois\nquatre\ncinq\nsix\n"
        self.d.commit({"f.txt": base}, "base")
        self.d.git("checkout", "-q", "-b", "cote")
        c_cote = self.d.commit({"f.txt": base.replace("un\n", ligne_cote + "\n", 1)}, "cote")
        self.d.git("checkout", "-q", "feat/x")
        self.d.commit({"f.txt": base.replace("six\n", ligne_ici + "\n")}, "ici")
        self.d.git("merge", "-q", "--no-ff", "-m", "fusion", "cote")
        return c_cote

    def test_fusion_propre_sur_deux_lignes_du_meme_fichier(self):
        self.fusion_de_deux_cotes("UN", "SIX")
        code, sortie, erreur = self.d.lancer("feat/x")
        self.assertEqual(code, 0, sortie + erreur)
        self.assertNotIn("secret", sortie.replace("0 secret(s)", ""))

    def test_fusion_propre_qui_reprend_une_ligne_d_un_parent_n_est_pas_comptee(self):
        c_cote = self.fusion_de_deux_cotes(f"chez {NOM}", "SIX")
        fusion = self.d.sha()
        r = self.d.rapport()
        self.assertEqual([(f["kind"], f["commit"]) for f in r.findings], [("name", c_cote)])
        self.assertNotIn(fusion, [f["commit"] for f in r.findings])

    def test_fusion_propre_dont_la_resolution_injecte_un_secret(self):
        self.fusion_de_deux_cotes("UN", "SIX")
        (self.d.dossier / "f.txt").write_text(f"UN\ndeux\ntrois\nquatre\ncinq\nSIX\ntoken = {jeton()}\n", encoding="utf-8")
        self.d.git("add", "-A")
        self.d.git("commit", "-q", "--amend", "--no-edit")
        fusion = self.d.sha()
        r = self.d.rapport()
        self.assertEqual(r.exit, 1)
        self.assertEqual([(f["kind"], f["commit"], f["file"], f["line"]) for f in r.findings], [("secret", fusion, "f.txt", 7)])

    def test_message_declare_utf16_mais_ecrit_en_utf8_est_lu_aussi_en_utf8(self):
        corps = f"chez {NOM}  \n".encode("ascii")
        self.assertEqual(len(corps) % 2, 0)   # longueur paire : le codec déclaré sait décoder, mais lit du bruit
        self.commit_brut("encoding UTF-16LE\n", corps)
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual(code, 1)
        self.assertEqual([f["kind"] for f in donnees["findings"] if f["where"] == "message"], ["name"])

    def test_message_utf16_declare_de_longueur_impaire_ecrit_en_utf8_est_lu_en_utf8_et_signale(self):
        corps = f"chez {NOM}\n".encode("ascii")
        if len(corps) % 2 == 0:
            corps = f"chez {NOM} \n".encode("ascii")
        self.assertEqual(len(corps) % 2, 1)   # longueur impaire : le décodage UTF-16 déclaré échoue, la lecture UTF-8 suffit
        self.commit_brut("encoding UTF-16LE\n", corps)
        code, donnees, sortie = self.d.lancer_json("feat/x")
        self.assertEqual(code, 1)
        self.assertEqual(sorted(f["kind"] for f in donnees["findings"] if f["where"] == "message"), ["encoding", "name"])
        texte = self.d.lancer("feat/x")[1]
        self.assertIn("message : encodage déclaré incohérent", texte)
        self.assertNotIn(NOM, texte)

    def test_message_utf16_declare_de_longueur_impaire_propre_donne_une_trouvaille_sans_texte(self):
        self.commit_brut("encoding UTF-16LE\n", b"propre\n")
        self.assertEqual(len(b"propre\n") % 2, 1)
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual(code, 1)
        self.assertEqual([f["kind"] for f in donnees["findings"]], ["encoding"])

    def test_git_shallow_file_herite_est_ignore(self):
        self.d.commit({"docs/a.md": f"token = {jeton()}\n"})
        self.d.commit({"docs/a.md": None})
        c3 = self.d.commit({"docs/b.md": "propre\n"})
        fichier = self.d.racine / "shallow"
        fichier.write_text(c3 + "\n", encoding="ascii")
        code, sortie = self.lancer_avec({"GIT_SHALLOW_FILE": str(fichier)})
        self.assertEqual(code, 1)
        self.assertIn("secret possible dans docs/a.md, ligne 1", sortie)

    def test_depot_shallow_est_refuse(self):
        self.d.commit({"docs/a.md": f"token = {jeton()}\n"})
        self.d.commit({"docs/a.md": None})
        c3 = self.d.commit({"docs/b.md": "propre\n"})
        (self.d.dossier / ".git" / "shallow").write_text(c3 + "\n", encoding="ascii")
        code, donnees, _ = self.d.lancer_json("feat/x")
        self.assertEqual((code, donnees["error"]), (3, "git_failure"))

    def test_sommet_head_lit_le_nom_de_la_branche_courante(self):
        nom = f"feat/{NOM.lower()}-suite"
        self.d.git("checkout", "-q", "-b", nom)
        for tip in ("HEAD", "@"):
            code, sortie, _ = self.d.lancer(tip)
            self.assertEqual(code, 1, tip)
            self.assertIn("nom sensible dans le nom de branche n°1", sortie, tip)
            self.assertNotIn(NOM.lower(), sortie.lower())

    def test_sommet_head_detache_ne_lit_aucun_nom_de_branche(self):
        self.d.commit({"docs/b.md": "propre\n"})
        self.d.git("checkout", "-q", "--detach")
        code, sortie, _ = self.d.lancer("HEAD")
        self.assertEqual(code, 0, sortie)

    def test_sommet_sous_les_formes_heads_et_tilde(self):
        nom = f"feat/{NOM.lower()}-suite"
        self.d.git("checkout", "-q", "-b", nom)
        code, sortie, _ = self.d.lancer(f"heads/{nom}")
        self.assertEqual(code, 1)
        self.assertIn("nom sensible dans le nom de branche n°1", sortie)
        code, sortie, _ = self.d.lancer(f"{nom}~0")
        self.assertNotIn("nom de branche", sortie)
        self.assertNotIn(NOM.lower(), sortie.lower())


if __name__ == "__main__":
    unittest.main()
