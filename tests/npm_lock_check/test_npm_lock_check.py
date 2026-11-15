"""
Suite de tools/npm_lock_check.py (mothra-slices, groupe 3, design D9) : le contrôle de node_modules contre le verrou npm, sans npm, sans Node,
sans réseau. Faux espace de travail dans un dossier temporaire ; le script est lancé par python3 -I -B, comme le lanceur de tests le fait.

    uv run python -m unittest discover -s tests/npm_lock_check -v
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTIL = RACINE / "tools" / "npm_lock_check.py"

VERROU = {"lockfileVersion": 3, "packages": {
    "": {"name": "mothra"},
    "contract": {"name": "@mothra/contract"},
    "node_modules/@mothra/contract": {"resolved": "contract", "link": True},
    "node_modules/a": {"version": "1.0.0", "resolved": "https://registry.npmjs.org/a/-/a-1.0.0.tgz", "integrity": "sha512-aaa"},
    "node_modules/b": {"version": "2.0.0", "integrity": "sha512-bbb", "optional": True},
}}


class ControleDuVerrou(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.dossier = self.racine / "espace"
        self.installer()

    def installer(self, verrou=None, cache=None):
        """Écrit le verrou, le verrou caché et un dossier (avec package.json) par paquet installé. Par défaut : tout concorde, sans le facultatif."""
        verrou = json.loads(json.dumps(verrou or VERROU))
        shutil.rmtree(self.dossier, True)
        (self.dossier / "node_modules").mkdir(parents=True)
        (self.dossier / "package-lock.json").write_text(json.dumps(verrou), encoding="utf-8")
        if cache is None:
            cache = {"lockfileVersion": 3, "packages": {c: e for c, e in verrou["packages"].items()
                                                         if c and not any(e.get(k) for k in ("optional", "devOptional", "peerOptional"))}}
        (self.dossier / "node_modules" / ".package-lock.json").write_text(json.dumps(cache), encoding="utf-8")
        paquets = cache.get("packages") if isinstance(cache, dict) else None
        for chemin, entree in (paquets.items() if isinstance(paquets, dict) else ()):
            if chemin and not entree.get("link") and "node_modules/" in chemin:
                (self.dossier / chemin).mkdir(parents=True, exist_ok=True)
                (self.dossier / chemin / "package.json").write_text("{}", encoding="utf-8")

    def lancer(self, *arguments):
        return subprocess.run(["python3", "-I", "-B", str(OUTIL), *arguments], capture_output=True, text=True, timeout=60)

    def controler(self):
        resultat = self.lancer(str(self.dossier))
        return resultat.returncode, resultat.stdout

    def cache(self):
        return json.loads((self.dossier / "node_modules" / ".package-lock.json").read_text(encoding="utf-8"))

    def ecrire_cache(self, cache):
        (self.dossier / "node_modules" / ".package-lock.json").write_text(json.dumps(cache), encoding="utf-8")

    # --- ce qui concorde
    def test_tout_concorde_rien_et_code_0(self):
        self.assertEqual(self.controler(), (0, ""))

    def test_controle_du_verrou_seul_codes_et_message(self):
        # déplacé de tests/run_all (le test qui nomme l'outil est le sien)
        self.assertEqual(self.controler(), (0, ""))
        cache = self.cache()
        cache["packages"]["node_modules/a"]["version"] = "1.0.1"
        self.ecrire_cache(cache)
        self.assertEqual(self.controler(), (1, "écart : version différente : node_modules/a\n"))
        shutil.rmtree(self.dossier / "node_modules")
        (self.dossier / "node_modules").mkdir()
        self.assertEqual(self.controler(), (1, "écart : .package-lock.json absent\n"))
        self.assertEqual(self.lancer().returncode, 2)

    def test_paquet_facultatif_absent_n_est_pas_un_ecart(self):
        self.assertEqual(self.controler(), (0, ""))   # « b » est facultatif dans le verrou et absent de node_modules

    def test_lien_des_deux_cotes_est_ignore(self):
        verrou = json.loads(json.dumps(VERROU))
        cache = {"lockfileVersion": 3, "packages": {"node_modules/@mothra/contract": {"resolved": "contract", "link": True},
                                                     "node_modules/a": verrou["packages"]["node_modules/a"]}}
        self.installer(verrou, cache)
        self.assertEqual(self.controler(), (0, ""))
        cache["packages"]["node_modules/@mothra/contract"]["resolved"] = "autre"   # un lien qui change n'est jamais comparé
        self.ecrire_cache(cache)
        self.assertEqual(self.controler(), (0, ""))

    def test_chemin_imbrique(self):
        verrou = json.loads(json.dumps(VERROU))
        verrou["packages"]["node_modules/a/node_modules/c"] = {"version": "3.0.0", "integrity": "sha512-ccc"}
        self.installer(verrou)
        self.assertEqual(self.controler(), (0, ""))
        cache = self.cache()
        cache["packages"]["node_modules/a/node_modules/c"]["version"] = "3.0.1"
        self.ecrire_cache(cache)
        self.assertEqual(self.controler(), (1, "écart : version différente : node_modules/a/node_modules/c\n"))
        del cache["packages"]["node_modules/a/node_modules/c"]
        self.ecrire_cache(cache)
        self.assertEqual(self.controler(), (1, "écart : paquet absent : node_modules/a/node_modules/c\n"))

    def test_dev_optionnel_et_pair_optionnel_peuvent_manquer(self):
        verrou = json.loads(json.dumps(VERROU))
        verrou["packages"]["node_modules/d"] = {"version": "4.0.0", "integrity": "sha512-ddd", "devOptional": True}
        verrou["packages"]["node_modules/p"] = {"version": "5.0.0", "integrity": "sha512-ppp", "peerOptional": True}
        self.installer(verrou)
        self.assertEqual(self.controler(), (0, ""))

    # --- les écarts
    def test_version_ou_integrite_differente(self):
        for champ, valeur in (("version", "1.0.1"), ("integrity", "sha512-autre")):
            with self.subTest(champ=champ):
                self.installer()
                cache = self.cache()
                cache["packages"]["node_modules/a"][champ] = valeur
                self.ecrire_cache(cache)
                self.assertEqual(self.controler(), (1, f"écart : {champ} différente : node_modules/a\n"))

    def test_paquet_manquant_et_paquet_en_trop(self):
        cache = self.cache()
        del cache["packages"]["node_modules/a"]
        self.ecrire_cache(cache)
        self.assertEqual(self.controler(), (1, "écart : paquet absent : node_modules/a\n"))
        self.installer()
        cache = self.cache()
        cache["packages"]["node_modules/z"] = {"version": "9.0.0", "integrity": "sha512-zzz"}
        self.ecrire_cache(cache)
        self.assertEqual(self.controler(), (1, "écart : paquet installé inconnu du verrou : node_modules/z\n"))

    def test_paquet_facultatif_installe_a_une_autre_version_est_un_ecart(self):
        cache = self.cache()
        cache["packages"]["node_modules/b"] = {"version": "2.0.1", "integrity": "sha512-bbb", "optional": True}
        self.ecrire_cache(cache)
        (self.dossier / "node_modules" / "b").mkdir()
        (self.dossier / "node_modules" / "b" / "package.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.controler(), (1, "écart : version différente : node_modules/b\n"))

    def test_paquet_facultatif_installe_a_la_meme_version_concorde(self):
        cache = self.cache()
        cache["packages"]["node_modules/b"] = {"version": "2.0.0", "integrity": "sha512-bbb", "optional": True}
        self.ecrire_cache(cache)
        (self.dossier / "node_modules" / "b").mkdir()
        (self.dossier / "node_modules" / "b" / "package.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.controler(), (0, ""))

    def test_dossier_de_paquet_supprime_apres_l_installation(self):
        # le verrou caché dit « installé » mais le dossier a été retiré à la main : écart (le chemin seulement)
        shutil.rmtree(self.dossier / "node_modules" / "a")
        self.assertEqual(self.controler(), (1, "écart : dossier du paquet absent : node_modules/a\n"))

    def test_dossier_de_paquet_sans_package_json(self):
        (self.dossier / "node_modules" / "a" / "package.json").unlink()
        self.assertEqual(self.controler(), (1, "écart : dossier du paquet absent : node_modules/a\n"))

    def test_dossier_d_un_paquet_facultatif_non_installe_n_est_pas_cherche(self):
        self.assertFalse((self.dossier / "node_modules" / "b").exists())
        self.assertEqual(self.controler(), (0, ""))

    # --- fichiers absents, illisibles, mal formés
    def test_verrou_absent_illisible_ou_sans_table(self):
        verrou = self.dossier / "package-lock.json"
        verrou.unlink()
        self.assertEqual(self.controler(), (1, "écart : package-lock.json absent\n"))
        verrou.write_text("{ pas du json", encoding="utf-8")
        self.assertEqual(self.controler(), (1, "écart : package-lock.json illisible\n"))
        verrou.write_bytes(b"\xff\xfe\x00")
        self.assertEqual(self.controler(), (1, "écart : package-lock.json illisible\n"))
        verrou.write_text(json.dumps({"lockfileVersion": 3}), encoding="utf-8")
        self.assertEqual(self.controler(), (1, "écart : package-lock.json sans table packages\n"))

    def test_packages_qui_n_est_pas_un_objet(self):
        for valeur in ([], "texte", 3, None):
            with self.subTest(valeur=valeur):
                self.installer({"lockfileVersion": 3, "packages": valeur}, {"lockfileVersion": 3, "packages": {}})
                self.assertEqual(self.controler(), (1, "écart : package-lock.json sans table packages\n"))
                self.installer(cache={"lockfileVersion": 3, "packages": valeur})
                self.assertEqual(self.controler(), (1, "écart : .package-lock.json sans table packages\n"))

    def test_contenu_qui_n_est_pas_un_objet(self):
        (self.dossier / "package-lock.json").write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(self.controler(), (1, "écart : package-lock.json sans table packages\n"))

    def test_verrou_cache_absent_ou_illisible(self):
        (self.dossier / "node_modules" / ".package-lock.json").unlink()
        self.assertEqual(self.controler(), (1, "écart : .package-lock.json absent\n"))
        (self.dossier / "node_modules" / ".package-lock.json").write_text("nul", encoding="utf-8")
        self.assertEqual(self.controler(), (1, "écart : .package-lock.json illisible\n"))

    def test_node_modules_absent(self):
        shutil.rmtree(self.dossier / "node_modules")
        self.assertEqual(self.controler(), (1, "écart : .package-lock.json absent\n"))

    # --- usage
    def test_mauvais_usage_code_2(self):
        for arguments in ((), ("a", "b"), ("-h",), ("--help",)):
            with self.subTest(arguments=arguments):
                resultat = self.lancer(*arguments)
                self.assertEqual(resultat.returncode, 2, resultat.stderr)
                self.assertIn("npm_lock_check.py", resultat.stdout)

    def test_aucun_fichier_ecrit(self):
        avant = sorted(str(p.relative_to(self.racine)) for p in self.racine.rglob("*"))
        self.controler()
        self.assertEqual(sorted(str(p.relative_to(self.racine)) for p in self.racine.rglob("*")), avant)


if __name__ == "__main__":
    unittest.main()
