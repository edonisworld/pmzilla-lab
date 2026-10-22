"""Tests de tools/secret_scan.py (change pre-commit-secret-scan, design D1, D6, D8, D9).

Toutes les fausses valeurs sont construites à l'exécution (valeurs.py) : aucun fichier suivi ne contient une valeur d'une famille. Aucun test
n'imprime une valeur ni une empreinte ; « declare » n'est lancé que dans un dossier temporaire créé par le test.

    uv run python -W ignore -m unittest discover -s tests/secret_scan -q -f
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import secret_scan as ss  # noqa: E402
import valeurs as v  # noqa: E402

MODULE = RACINE / "tools" / "secret_scan.py"


def en_ligne(valeur, numero=3):
    """Un texte dont la ligne `numero` contient la valeur, entourée de lignes neutres."""
    lignes = [f"ligne neutre {i}" for i in range(1, 6)]
    lignes[numero - 1] = "avant " + valeur + " après"
    return "\n".join(lignes) + "\n"


class Familles(unittest.TestCase):
    def assertTrouve(self, valeur, famille, numero=3):
        self.assertEqual(ss.findings(en_ligne(valeur, numero)), [ss.Finding(numero, famille)])

    def test_chaque_famille_avec_son_numero_de_ligne(self):
        cas = (
            (v.cle_privee(), ss.CLE_PRIVEE), (v.cle_privee("OPENSSH "), ss.CLE_PRIVEE), (v.cle_privee(""), ss.CLE_PRIVEE),
            (v.cle_privee("EC "), ss.CLE_PRIVEE),
            (v.cle_cloud(), ss.CLE_CLOUD), (v.jeton_github(), ss.JETON_GITHUB), (v.jeton_github_fin(), ss.JETON_GITHUB),
            (v.cle_anthropic(), ss.CLE_ANTHROPIC), (v.jeton_atlassian(), ss.JETON_ATLASSIAN), (v.jeton_slack(), ss.JETON_SLACK),
            (v.adresse(), ss.ADRESSE_MOT_DE_PASSE), (v.mot_de_passe_labo(), ss.MOT_DE_PASSE_LABO),
            (v.mot_de_passe_labo(suffixe=""), ss.MOT_DE_PASSE_LABO),
        )
        for numero, (valeur, famille) in enumerate(cas):
            with self.subTest(famille=famille, cas=numero):
                self.assertTrouve(valeur, famille, numero=1 + numero % 5)

    def test_cle_privee_pgp(self):
        self.assertTrouve("-----" + "BEGIN PGP " + "PRIVATE KEY BLOCK" + "-----", ss.CLE_PRIVEE)

    def test_mot_de_passe_du_labo_entre_guillemets_et_dans_un_dict(self):
        nom = "PMZILLA_LAB_DB" + "_PASSWORD"
        for ligne in (f'{nom}="Zx9Qw2Er7"', f"{nom}='Zx9Qw2Er7'", f'{{"{nom}": "Zx9Qw2Er7"}}', f"export {nom}=Zx9Qw2Er7",
                      "PMZILLA_JIRA" + "_TOKEN=Zx9Qw2Er7", "PMZILLA_STORY" + "_ANALYSIS_KEY: Zx9Qw2Er7"):
            with self.subTest(forme=ligne.split("=")[0][:12]):
                self.assertEqual([t.family for t in ss.findings(ligne)], [ss.MOT_DE_PASSE_LABO])

    def test_aucune_valeur_dans_les_trouvailles(self):
        jeton = v.jeton_github()
        for trouvaille in ss.findings(en_ligne(jeton)):
            self.assertEqual(trouvaille._fields, ("line", "family"))
            self.assertNotIn(jeton, repr(trouvaille))

    def test_etiquettes_de_d8(self):
        self.assertEqual(sorted(ss.ETIQUETTES.values()), sorted([
            "clé privée", "clé d'accès cloud", "jeton GitHub", "clé d'API Anthropic", "jeton Atlassian", "jeton Slack",
            "adresse avec mot de passe", "mot de passe du labo"]))

    def test_tres_longue_ligne_en_temps_lineaire(self):
        # D3 : fichiers de toute taille ; un motif quadratique bloquerait le crochet sur un fichier de plus de 1 Mo d'une seule ligne
        import time
        debut = time.monotonic()
        for remplissage in ("x" * 2_000_000, "a1" * 1_000_000, "a:" * 1_000_000):
            self.assertEqual(ss.findings(remplissage + " " + v.jeton_slack()), [ss.Finding(1, ss.JETON_SLACK)])
        self.assertLess(time.monotonic() - debut, 10)

    def test_plusieurs_trouvailles_dans_l_ordre_des_lignes(self):
        texte = "propre\n" + v.jeton_slack() + "\npropre\n" + v.cle_cloud() + "\n"
        self.assertEqual(ss.findings(texte), [ss.Finding(2, ss.JETON_SLACK), ss.Finding(4, ss.CLE_CLOUD)])


class EspacesReserves(unittest.TestCase):
    def assertRien(self, texte):
        self.assertEqual(ss.findings(texte), [], texte[:20])

    def test_adresses_a_espace_reserve(self):
        for mot_de_passe in ("<password>", "<mot-de-passe>", "xxxxxxxx", "********", "$PGPASSWORD", "${PGPASSWORD}", "{{ mdp }}",
                             "%(mdp)s", "{X}", "{MOT_DE_PASSE}"):
            with self.subTest(espace=mot_de_passe):
                self.assertRien(v.adresse(mot_de_passe))

    def test_adresse_sans_mot_de_passe_ou_a_chevrons(self):
        self.assertRien("postgresql://postgres@127.0.0.1:1/pmzilla")
        self.assertRien("<scheme>://<user>:<password>@<host>")

    def test_reference_accolades_en_majuscules_seulement(self):
        self.assertTrue(ss.is_placeholder("{X}"))
        self.assertTrue(ss.is_placeholder("{NOM_2}"))
        self.assertFalse(ss.is_placeholder("{Zx9Qw2Er7}"))

    def test_mot_de_passe_du_labo_reference_ou_constante(self):
        for valeur in ('"$PW"', "${PW}", '"${PW}"', "$(security find)", "<mot-de-passe>", "{X}", "FAUX_MOT_DE_PASSE",
                       "FAUX_MOT_DE_PASSE,", "FAUX_MOT_DE_PASSE}", "FAUX_MOT_DE_PASSE)", '""', "%(mdp)s"):
            with self.subTest(valeur=valeur[:6]):
                self.assertRien(v.mot_de_passe_labo(valeur))

    def test_lecture_de_variable_et_comparaison_non_trouvees(self):
        nom = "PMZILLA_LAB_DB" + "_PASSWORD"
        for ligne in (f'unset {nom}', f'echo "${{#{nom}}}"', f'[ -z "${{{nom}:-}}" ]', f'os.environ.get("{nom}")',
                      f'k != "{nom}"'):
            with self.subTest(ligne=ligne[:8]):
                self.assertRien(ligne)

    def test_hachages_condensats_et_empreintes_non_trouves(self):
        hexa = "0123456789abcdef" * 4
        self.assertRien(f'hash = "sha256:{hexa}"\n')
        self.assertRien(f"image: postgres@sha256:{hexa}\n")
        self.assertRien(f"commit {hexa[:40]}\nempreinte SHA-256 : {hexa}\n")
        self.assertRien("integrity sha512-" + "A" * 20 + "b" * 60 + "==\n")

    def test_corps_d_un_seul_caractere_repete(self):
        self.assertRien("gh" + "p_" + "x" * 36)
        self.assertRien("AK" + "IA" + "X" * 16)


class ExemplesDeclares(unittest.TestCase):
    def test_exemple_declare_accepte_meme_valeur_ailleurs_refusee(self):
        jeton = v.jeton_github()
        texte = en_ligne(jeton)
        declares = {("docs/exemple.md", ss.fingerprint("gh" + "p_" + v.CORPS + "AbCd"))}
        self.assertEqual(ss.check("docs/exemple.md", texte, declares), ([], [ss.Finding(3, ss.JETON_GITHUB)]))
        self.assertEqual(ss.check("docs/autre.md", texte, declares), ([ss.Finding(3, ss.JETON_GITHUB)], []))

    def test_autre_valeur_dans_le_meme_fichier_refusee(self):
        declares = {("docs/exemple.md", ss.fingerprint(v.jeton_github()))}
        refusees, acceptees = ss.check("docs/exemple.md", en_ligne(v.jeton_slack()), declares)
        self.assertEqual((refusees, acceptees), ([ss.Finding(3, ss.JETON_SLACK)], []))

    def test_liste_lue(self):
        empreinte = "a" * 64
        texte = f"# en-tête\n\ndocs/exemple.md {empreinte}  # exemple de format\n"
        self.assertEqual(ss.parse_declared(texte), {("docs/exemple.md", empreinte)})

    def test_liste_mal_formee_echoue_ferme(self):
        for ligne in ("docs/exemple.md", "docs/exemple.md abc", "docs/exemple.md " + "A" * 64, "un deux " + "a" * 64):
            with self.subTest(ligne=ligne[:18]):
                with self.assertRaises(ss.ListeInvalide) as ctx:
                    ss.parse_declared("# en-tête\n" + ligne + "\n")
                self.assertNotIn(ligne, str(ctx.exception))

    def test_liste_absente_vide_et_liste_illisible(self):
        dossier = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, dossier, True)
        self.assertEqual(ss.load_declared(str(dossier / "absente.txt")), set())
        illisible = dossier / "illisible.txt"
        illisible.write_bytes(b"\xff\xfe\x00")
        with self.assertRaises(ss.ListeInvalide):
            ss.load_declared(str(illisible))

    def test_liste_suivie_ne_contient_que_des_commentaires_ou_des_entrees(self):
        ss.load_declared(str(RACINE / ss.LISTE_EXEMPLES))


class Declare(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        (self.racine / "docs").mkdir()
        self.jeton = v.jeton_github()
        (self.racine / "docs" / "exemple.md").write_text(en_ligne(self.jeton), encoding="utf-8")
        self.liste = self.racine / ss.LISTE_EXEMPLES

    def lancer(self, *args, session=False):
        env = {k: val for k, val in os.environ.items() if k != ss.VARIABLE_CLAUDE_CODE}
        if session:
            env[ss.VARIABLE_CLAUDE_CODE] = "1"
        fait = subprocess.run([sys.executable, "-I", str(MODULE), "declare", *args], capture_output=True, text=True, env=env,
                              cwd=str(self.racine), timeout=60)
        sortie = fait.stdout + fait.stderr
        self.assertNotIn(self.jeton, sortie)
        self.assertNotIn(ss.fingerprint(self.jeton), sortie)
        return fait.returncode, sortie

    def test_refuse_en_session_code_3_avant_toute_lecture(self):
        code, sortie = self.lancer("docs/exemple.md:3", "--raison", "format", "--racine", str(self.racine), session=True)
        self.assertEqual(code, 3, sortie)
        self.assertIn("refusé dans une session Claude Code", sortie)
        self.assertFalse(self.liste.exists())
        code, _ = self.lancer("--bidon", session=True)
        self.assertEqual(code, 3)

    def test_ecrit_une_entree_sans_la_valeur(self):
        code, sortie = self.lancer("docs/exemple.md:3", "--raison", "exemple de format", "--racine", str(self.racine))
        self.assertEqual(code, 0, sortie)
        self.assertIn("docs/exemple.md, ligne 3 (jeton GitHub) : exemple déclaré", sortie)
        contenu = self.liste.read_text(encoding="utf-8")
        self.assertNotIn(self.jeton, contenu)
        self.assertIn(ss.fingerprint(self.jeton), contenu)
        declares = ss.load_declared(str(self.liste))
        self.assertEqual(ss.check("docs/exemple.md", en_ligne(self.jeton), declares), ([], [ss.Finding(3, ss.JETON_GITHUB)]))
        code, _ = self.lancer("docs/exemple.md:3", "--raison", "exemple de format", "--racine", str(self.racine))
        self.assertEqual(code, 0)
        self.assertEqual(self.liste.read_text(encoding="utf-8"), contenu)   # pas de doublon

    def test_aucune_trouvaille_code_1(self):
        code, sortie = self.lancer("docs/exemple.md:2", "--raison", "rien", "--racine", str(self.racine))
        self.assertEqual(code, 1, sortie)
        self.assertFalse(self.liste.exists())

    def test_usage_et_fichier_illisible_code_2(self):
        for args in ((), ("docs/exemple.md",), ("docs/exemple.md:0", "--raison", "x"), ("docs/exemple.md:3",),
                     ("docs/exemple.md:3", "--raison", " "), ("docs/exemple.md:3", "--raison", "x", "--bidon")):
            with self.subTest(args=len(args)):
                code, _ = self.lancer(*args)
                self.assertEqual(code, 2)
        code, sortie = self.lancer("docs/absent.md:3", "--raison", "x", "--racine", str(self.racine))
        self.assertEqual(code, 2, sortie)
        self.assertFalse(self.liste.exists())

    def test_liste_mal_formee_code_2_rien_ecrit(self):
        self.liste.parent.mkdir(parents=True)
        self.liste.write_text("ligne mal formée\n", encoding="utf-8")
        code, sortie = self.lancer("docs/exemple.md:3", "--raison", "x", "--racine", str(self.racine))
        self.assertEqual(code, 2, sortie)
        self.assertEqual(self.liste.read_text(encoding="utf-8"), "ligne mal formée\n")

    def test_raison_contenant_la_valeur_refusee(self):
        code, _ = self.lancer("docs/exemple.md:3", "--raison", "voir " + self.jeton, "--racine", str(self.racine))
        self.assertEqual(code, 2)
        self.assertFalse(self.liste.exists())

    def test_chemin_hors_du_depot_refuse(self):
        dehors = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, dehors, True)
        (dehors / "f.md").write_text(en_ligne(self.jeton), encoding="utf-8")
        code, _ = self.lancer(f"{dehors / 'f.md'}:3", "--raison", "x", "--racine", str(self.racine))
        self.assertEqual(code, 2)


class BibliothequeStandard(unittest.TestCase):
    def test_imports_de_la_bibliotheque_standard_seulement(self):
        import ast
        arbre = ast.parse(MODULE.read_text(encoding="utf-8"))
        modules = {a.name.split(".")[0] for n in ast.walk(arbre) if isinstance(n, ast.Import) for a in n.names}
        modules |= {n.module.split(".")[0] for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertLessEqual(modules, set(sys.stdlib_module_names))


if __name__ == "__main__":
    unittest.main()
