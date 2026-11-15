"""Paquets npm de Mothra : genres `npm-package` et `npm-runtime`, lecture de mothra/package.json et du verrou npm, contrôles de
l'épinglage (change mothra-slices, tâche 2.4 ; spec mothra-tooling, « Mothra's npm packages are inventoried »). Faux dépôt, aucun réseau.

    uv run --with pyyaml python -m unittest discover -s tests/composants -v
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_composants import AvecDepot  # noqa: E402
from aide_npm import NODE, NPM, PAQUET_JSON, VERROU, avec_npm, entree_npm, entree_paquet, package_json, racine_json, verrou_npm  # noqa: E402


class Inventaire(AvecDepot):
    def test_genres_acceptes_et_versions_lues(self):
        avec_npm(self.depot)
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertIn(f"npm · npm-runtime · {NPM} · mothra/package.json", sortie)
        self.assertIn("alpha · npm-package · 1.0.0 · mothra/package-lock.json", sortie)
        self.assertIn("beta · npm-package · 2.0.0 · mothra/package-lock.json", sortie)
        self.assertIn("Inventaire à jour : 24 composant(s)", sortie)   # 21 du faux dépôt (sans echarts depuis R-146) + npm, alpha, beta

    def test_dependance_de_developpement_et_du_serveur_comptent(self):
        avec_npm(self.depot, dependances={}, dev={"gamma": "3.0.0"})
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertIn("gamma · npm-package · 3.0.0", sortie)

    def test_paquets_du_depot_ne_comptent_pas(self):
        avec_npm(self.depot)
        _, sortie, _ = self.inventaire("--verify")
        self.assertNotIn("@mothra/", sortie)

    def test_sans_verrou_toleree(self):
        avec_npm(self.depot, lock=None)
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertIn("alpha · npm-package · introuvable · mothra/package-lock.json", sortie)

    def test_dependance_sans_entree(self):
        avec_npm(self.depot, entrees=[entree_npm(), entree_paquet("alpha")])
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn("Composant à ajouter à l'inventaire : beta (déclaré dans mothra/server/package.json)", sortie)

    def test_entree_sans_dependance(self):
        avec_npm(self.depot, entrees=[entree_npm(), entree_paquet("alpha"), entree_paquet("beta"), entree_paquet("delta")])
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn("Composant à retirer de l'inventaire : delta", sortie)

    def test_package_json_sans_entree_npm(self):
        avec_npm(self.depot, entrees=[entree_paquet("alpha"), entree_paquet("beta")])
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn("Composant à ajouter à l'inventaire : npm (déclaré dans mothra/package.json)", sortie)

    def test_procedure_absente_du_guide(self):
        avec_npm(self.depot, guide=False)
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 1)
        self.assertIn("Procédure introuvable dans le guide d'installation : npm", sortie)
        self.assertIn("Procédure introuvable dans le guide d'installation : alpha", sortie)

    def test_lieu_inconnu_refuse(self):
        avec_npm(self.depot, entrees=[{**entree_paquet("alpha"), "pinned_in": "mothra/autre.json"}])
        _, sortie, _ = self.inventaire()
        self.assertIn("Valeur inconnue : alpha, pinned_in", sortie)

    def test_aucun_fichier_ecrit(self):
        avec_npm(self.depot)
        self.depot.fichiers_initiaux = {p: p.read_bytes() for p in self.depot.racine.rglob("*") if p.is_file()}
        self.inventaire("--verify")
        self.assertEqual(self.depot.inchange(), [])


class Epinglage(AvecDepot):
    def test_dependance_non_epinglee(self):
        for plage in ("^1.0.0", "~1.0.0", "1.x", "*", "latest", ">=1.0.0", "1.0", "", "git+https://example.invalid/x.git"):
            with self.subTest(plage=plage):
                avec_npm(self.depot, dependances={"alpha": plage})
                code, sortie, _ = self.inventaire("--verify")
                self.assertEqual(code, 1, sortie)
                self.assertIn("Dépendance npm non épinglée : alpha (mothra/contract/package.json)", sortie)

    def test_dependance_epinglee_avec_suffixe_de_prepublication_acceptee(self):
        avec_npm(self.depot, dependances={"alpha": "1.0.0-rc.1"})
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)

    def test_dependance_de_developpement_non_epinglee(self):
        avec_npm(self.depot, dev={"beta": "^2.0.0"})
        _, sortie, _ = self.inventaire("--verify")
        self.assertIn("Dépendance npm non épinglée : beta (mothra/server/package.json)", sortie)

    def test_la_version_n_est_jamais_recopiee_dans_le_message(self):
        avec_npm(self.depot, dependances={"alpha": "^1.0.0"}, lock={"alpha": "1.0.0", "beta": "2.0.0"})
        _, sortie, _ = self.inventaire("--verify")
        self.assertIn("Dépendance npm non épinglée : alpha", sortie)
        self.assertNotIn("^1.0.0", sortie)

    def test_engines_node_different(self):
        avec_npm(self.depot, racine=racine_json(node="90.2.0"))
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn(f"engines.node de mothra/package.json différent de mothra/.node-version : 90.2.0 contre {NODE}", sortie)

    def test_engines_node_absent(self):
        avec_npm(self.depot, racine=racine_json(node=None))
        _, sortie, _ = self.inventaire("--verify")
        self.assertIn("engines.node de mothra/package.json absent", sortie)

    def test_engines_npm_non_exact(self):
        for valeur in ("^91.2.3", "91", "91.2", ">=91.2.3", "latest", "*"):
            with self.subTest(valeur=valeur):
                avec_npm(self.depot, racine=racine_json(npm=valeur))
                code, sortie, _ = self.inventaire("--verify")
                self.assertEqual(code, 1, sortie)
                self.assertIn(f"engines.npm de mothra/package.json non exact : {valeur}", sortie)

    def test_engines_npm_absent(self):
        avec_npm(self.depot, racine=racine_json(npm=None))
        _, sortie, _ = self.inventaire("--verify")
        self.assertIn("engines.npm de mothra/package.json absent", sortie)

    def test_engines_absents(self):
        avec_npm(self.depot, racine=racine_json(engines=False))
        _, sortie, _ = self.inventaire("--verify")
        self.assertIn("engines.node de mothra/package.json absent", sortie)
        self.assertIn("engines.npm de mothra/package.json absent", sortie)

    def test_package_json_illisible(self):
        avec_npm(self.depot, racine="{ pas du json")
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn("mothra/package.json illisible", sortie)

    def test_package_json_d_un_paquet_illisible(self):
        avec_npm(self.depot)
        self.depot.ecrire("mothra/front/package.json", "[]")
        _, sortie, _ = self.inventaire("--verify")
        self.assertIn("mothra/front/package.json illisible", sortie)

    def test_verrou_different_du_package_json(self):
        avec_npm(self.depot, lock={"alpha": "1.0.1", "beta": "2.0.0"})
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn("Verrou npm différent de package.json : alpha (1.0.1 contre 1.0.0)", sortie)

    def test_dependance_absente_du_verrou(self):
        avec_npm(self.depot, lock={"alpha": "1.0.0"})
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn("Dépendance absente du verrou npm : beta", sortie)

    def test_verrou_illisible(self):
        avec_npm(self.depot)
        self.depot.ecrire(VERROU, "pas du json")
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn("mothra/package-lock.json illisible", sortie)

    def test_sans_verrou_aucun_ecart(self):
        avec_npm(self.depot, lock=None)
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("verrou", sortie.lower().replace("package-lock.json", ""))

    def verrou_brut(self, paquets: dict) -> None:
        self.depot.ecrire(VERROU, json.dumps({"name": "mothra", "lockfileVersion": 3, "packages": {"": {"name": "mothra"}, **paquets}}))

    def test_lien_hors_espace_refuse(self):
        avec_npm(self.depot, lock=None)
        self.verrou_brut({
            "node_modules/alpha": {"version": "1.0.0"}, "node_modules/beta": {"version": "2.0.0"},
            "node_modules/intrus": {"resolved": "file:../x", "link": True},
        })
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn("registre non public : intrus", sortie)

    def test_liens_d_espace_acceptes(self):
        avec_npm(self.depot, lock=None)
        self.verrou_brut({
            "node_modules/alpha": {"version": "1.0.0"}, "node_modules/beta": {"version": "2.0.0"},
            "node_modules/@mothra/contract": {"resolved": "contract", "link": True},
            "node_modules/@mothra/server": {"resolved": "server", "link": True},
            "node_modules/@mothra/front": {"resolved": "front", "link": True},
        })
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("registre non public", sortie)

    def test_paquet_imbrique_sous_un_espace_trouve(self):
        avec_npm(self.depot, lock=None)
        self.verrou_brut({"contract/node_modules/alpha": {"version": "1.0.0"}, "node_modules/beta": {"version": "2.0.0"}})
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("absente du verrou", sortie)

    def test_deux_espaces_deux_versions_chacun_compare_a_la_sienne(self):
        avec_npm(self.depot, dependances={"alpha": "1.0.0"}, dev={"alpha": "2.0.0"}, lock=None, entrees=[entree_npm()])
        self.verrou_brut({"contract/node_modules/alpha": {"version": "1.0.0"}, "server/node_modules/alpha": {"version": "2.0.0"}})
        _, sortie, _ = self.inventaire("--verify")
        self.assertNotIn("Verrou npm différent", sortie)
        self.assertNotIn("absente du verrou", sortie)
        self.verrou_brut({"contract/node_modules/alpha": {"version": "1.0.1"}, "server/node_modules/alpha": {"version": "2.0.0"}})
        _, sortie, _ = self.inventaire("--verify")
        self.assertIn("Verrou npm différent de package.json : alpha (1.0.1 contre 1.0.0)", sortie)
        self.assertNotIn("(2.0.0 contre", sortie)

    def test_sans_package_json_rien_ne_change(self):
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("npm", sortie.replace("npm registry", ""))


if __name__ == "__main__":
    unittest.main()
