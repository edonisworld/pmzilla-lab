"""Inventaire des composants : format, résolution des versions sans réseau, reconstruction depuis les sources (design.md D1, D2, D9, D15).

    uv run --with pyyaml python -m unittest discover -s tests/composants -v
"""
import socket
import sys
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_composants import (RACINE, AvecDepot, ConnexionInterdite, SansReseau, composants, entete, lancer,  # noqa: E402
                             verrou)


class Garde(SansReseau):
    def test_une_connexion_hors_boucle_locale_echoue_sans_nommer_l_adresse(self):
        with self.assertRaises(ConnexionInterdite) as ctx:
            socket.create_connection(("192.0.2.10", 443), timeout=1)
        self.assertNotIn("192.0.2.10", str(ctx.exception))
        self.assertIn("create_connection", str(ctx.exception))

    def test_une_requete_http_hors_boucle_locale_echoue(self):
        with self.assertRaises(Exception) as ctx:
            urllib.request.urlopen("http://exemple.invalid/", timeout=1)
        self.assertIn("connexion réseau interdite", repr(ctx.exception))
        self.assertNotIn("exemple.invalid", str(ctx.exception).replace("http://exemple.invalid/", ""))


class Format(AvecDepot):
    def test_inventaire_coherent(self):
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Inventaire à jour : 21 composant(s)", sortie)

    def test_champ_manquant(self):
        self.depot.modifier_inventaire(lambda e: e[0].pop("upstream"))
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 1)
        self.assertIn("Champ manquant : numpy, upstream", sortie)

    def test_procedure_manquante(self):
        self.depot.modifier_inventaire(lambda e: e[0].pop("procedure"))
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 1)
        self.assertIn("Champ manquant : numpy, procedure", sortie)

    def test_procedure_absente_du_guide(self):
        self.depot.modifier_inventaire(lambda e: e[1].update(procedure="Titre inventé"))
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 1)
        self.assertIn("Procédure introuvable dans le guide d'installation : psycopg", sortie)

    def test_champ_inconnu(self):
        self.depot.modifier_inventaire(lambda e: e[2].update(url="x"))
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 1)
        self.assertIn("Champ inconnu : pyyaml, url", sortie)

    def test_version_recopiee_refusee_comme_champ_inconnu(self):
        self.depot.modifier_inventaire(lambda e: e[2].update(version="6.0.3"))
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 1)
        self.assertIn("Champ inconnu : pyyaml, version", sortie)

    def test_genre_inconnu(self):
        self.depot.modifier_inventaire(lambda e: e[0].update(kind="gadget"))
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 1)
        self.assertIn("Genre inconnu : numpy, gadget", sortie)

    def test_nom_en_double(self):
        self.depot.modifier_inventaire(lambda e: e.append(dict(e[0])))
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 1)
        self.assertIn("Composant en double : numpy", sortie)

    def test_canal_obligatoire_pour_un_outil_non_epingle_et_interdit_sinon(self):
        def changer(e):
            e[-1].pop("channel")
            e[0]["channel"] = "npm registry"
        self.depot.modifier_inventaire(changer)
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 1)
        self.assertIn("Champ manquant : openspec, channel", sortie)
        self.assertIn("Champ inconnu : numpy, channel", sortie)

    def test_valeurs_hors_listes(self):
        def changer(e):
            e[0]["pinned_in"] = "ailleurs"
            e[1]["upstream"] = "un site"
            e[2]["flags"] = ["inconnu"]
        self.depot.modifier_inventaire(changer)
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 1)
        self.assertIn("Valeur inconnue : numpy, pinned_in", sortie)
        self.assertIn("Valeur inconnue : psycopg, upstream", sortie)
        self.assertIn("Valeur inconnue : pyyaml, flags", sortie)

    def test_inventaire_absent(self):
        (self.depot.racine / "docs/pmzilla/composants.yaml").unlink()
        code, _, erreurs = self.inventaire()
        self.assertEqual(code, 2)
        self.assertIn("Inventaire illisible", erreurs)

    def test_inventaire_illisible(self):
        self.depot.ecrire("docs/pmzilla/composants.yaml", "components: [\n")
        code, _, erreurs = self.inventaire()
        self.assertEqual(code, 2)
        self.assertIn("Inventaire illisible", erreurs)

    def test_usage(self):
        code, _, _ = lancer(["inconnue"])
        self.assertEqual(code, 2)


class Resolution(AvecDepot):
    def lignes(self) -> dict[str, str]:
        code, sortie, _ = self.inventaire()
        self.assertEqual(code, 0, sortie)
        return {l.split(" · ")[0]: l for l in sortie.splitlines() if " · " in l}

    def test_versions_lues_la_ou_elles_sont_fixees(self):
        lignes = self.lignes()
        self.assertIn("numpy · python-package · 2.1.0 · lock files", lignes["numpy"])
        self.assertIn("python · python-runtime · 3.14 · .python-version", lignes["python"])
        self.assertIn("exemple/base · docker-image · 1.2.0-pg18 · docker-compose.yml", lignes["exemple/base"])
        self.assertIn("bmad-method · bmad-module · 6.1.0 · BMAD manifest", lignes["bmad-method"])
        self.assertIn("ext · bmad-module · v2.0.0 · BMAD manifest", lignes["ext"])
        self.assertIn("core · bmad-module · 6.1.0", lignes["core"])
        self.assertIn("graphes · vendored · 5.6.0 · vendor version file", lignes["graphes"])
        self.assertIn("modele-a · ollama-model · latest · library tool constant", lignes["modele-a"])
        self.assertIn("modele-b · ollama-model · 7b · sorting configuration", lignes["modele-b"])
        self.assertIn("uv · tool · non épinglé · not pinned (Homebrew formula)", lignes["uv"])
        self.assertIn("git · tool · non épinglé · not pinned (Xcode Command Line Tools)", lignes["git"])
        self.assertIn("node · tool · non épinglé · not pinned (fnm)", lignes["node"])

    def test_verrous_en_desaccord(self):
        self.assertIn("6.0.2 (b), 6.0.3 (a, watch_triage)", self.lignes()["pyyaml"])

    def test_aucun_fichier_ecrit(self):
        self.lignes()
        self.inventaire("--verify")
        self.assertEqual(self.depot.inchange(), [])

    def test_sans_reseau_le_code_reussit(self):
        # la garde de SansReseau est active : une tentative de connexion ferait échouer le test
        code, _, _ = self.inventaire("--verify")
        self.assertEqual(code, 0)


class Reconstruction(AvecDepot):
    def verifier(self) -> tuple[int, str]:
        code, sortie, _ = self.inventaire("--verify")
        return code, sortie

    def test_nouvelle_dependance_dans_un_en_tete(self):
        self.depot.ecrire("tools/c.py", entete(["requests"]) + "print('c')\n")
        code, sortie = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("Composant à ajouter à l'inventaire : requests (déclaré dans tools/c.py)", sortie)

    def test_module_de_bibliotheque_avec_en_tete_sans_verrou(self):
        self.depot.ecrire("tools/module.py", entete(["httpx"]) + "X = 1\n")
        code, sortie = self.verifier()
        self.assertIn("Composant à ajouter à l'inventaire : httpx (déclaré dans tools/module.py)", sortie)

    def test_paquet_d_un_verrou_seulement_n_est_pas_un_composant(self):
        # psycopg-binary est une dépendance transitive (verrou seulement) : ni demandée ni signalée
        code, sortie = self.verifier()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("psycopg-binary", sortie)

    def test_composant_plus_utilise(self):
        self.depot.modifier_inventaire(lambda e: e.insert(0, {**e[0], "name": "vieux-paquet"}))
        code, sortie = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("Composant à retirer de l'inventaire : vieux-paquet", sortie)

    def test_outil_prive_present_compte(self):
        self.depot.ecrire("tools/build_edition.py", entete(["paquet-prive"]) + "print('p')\n")
        code, sortie = self.verifier()
        self.assertIn("Composant à ajouter à l'inventaire : paquet-prive (déclaré dans tools/build_edition.py)", sortie)

    def test_outil_prive_absent_ni_demande_ni_signale(self):
        (self.depot.racine / "tools/build_edition.py").unlink()
        self.depot.modifier_inventaire(lambda e: e.insert(0, {**e[0], "name": "paquet-prive"}))
        code, sortie = self.verifier()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("inventaire : paquet-prive", sortie)

    def test_image_du_fichier_compose(self):
        self.depot.ecrire("docker-compose.yml", (self.depot.racine / "docker-compose.yml").read_text()
                          + "  autre:\n    image: exemple/cache:7.0\n")
        code, sortie = self.verifier()
        self.assertIn("Composant à ajouter à l'inventaire : exemple/cache (déclaré dans docker-compose.yml)", sortie)

    def test_modele_de_la_bibliotheque_et_du_tri(self):
        self.depot.ecrire("tools/pmzilla_lab_library.py",
                          entete(["numpy"]) + 'import os\nEMBED_MODEL = os.environ.get("PMZILLA_LAB_MODEL", "modele-c")\n')
        texte = (self.depot.racine / "tools/watch_triage.py").read_text().replace("modele-b:7b", "modele-d:1b")
        self.depot.ecrire("tools/watch_triage.py", texte)
        code, sortie = self.verifier()
        self.assertIn("Composant à ajouter à l'inventaire : modele-c (déclaré dans tools/pmzilla_lab_library.py)", sortie)
        self.assertIn("Composant à ajouter à l'inventaire : modele-d (déclaré dans tools/watch_triage.py)", sortie)
        self.assertIn("Composant à retirer de l'inventaire : modele-a", sortie)
        self.assertIn("Composant à retirer de l'inventaire : modele-b", sortie)

    def test_prerequis_des_deux_fichiers_d_installation(self):
        self.depot.ecrire("tools/install_lab.sh", "for outil in git uv jq; do\n  :\ndone\n")
        texte = (self.depot.racine / "tools/install_lab_prereqs.py").read_text().replace('"docker-compose"]', '"docker-compose", "pv"]')
        self.depot.ecrire("tools/install_lab_prereqs.py", texte)
        code, sortie = self.verifier()
        self.assertIn("Composant à ajouter à l'inventaire : jq (déclaré dans tools/install_lab.sh)", sortie)
        self.assertIn("Composant à ajouter à l'inventaire : pv (déclaré dans tools/install_lab_prereqs.py)", sortie)

    def test_claude_vient_de_l_installateur_officiel(self):
        texte = (self.depot.racine / "tools/install_lab_prereqs.py").read_text().replace("INSTALLATEUR_CLAUDE", "AUTRE")
        self.depot.ecrire("tools/install_lab_prereqs.py", texte)
        code, sortie = self.verifier()
        self.assertIn("Composant à retirer de l'inventaire : claude", sortie)

    def test_modules_et_installation_bmad(self):
        texte = (self.depot.racine / "_bmad/_config/manifest.yaml").read_text() + "  - name: neuf\n    version: 1.0.0\n    source: built-in\n"
        self.depot.ecrire("_bmad/_config/manifest.yaml", texte)
        code, sortie = self.verifier()
        self.assertIn("Composant à ajouter à l'inventaire : neuf (déclaré dans _bmad/_config/manifest.yaml)", sortie)

    def test_configuration_openspec(self):
        (self.depot.racine / "openspec/config.yaml").unlink()
        code, sortie = self.verifier()
        self.assertIn("Composant à retirer de l'inventaire : openspec", sortie)

    def test_fichier_de_version_du_dossier_vendor(self):
        self.depot.ecrire("tools/vendor/autre.version", "1.0.0\n")
        code, sortie = self.verifier()
        self.assertIn("Composant à ajouter à l'inventaire : autre (déclaré dans tools/vendor/autre.version)", sortie)

    def test_dependances_du_lanceur_de_tests(self):
        self.depot.ecrire("tests/run_all.sh", '#!/bin/bash\nDEPS="${RUN_ALL_DEPS---with numpy --with pyyaml --with "psycopg[binary]" --with lxml}"\n')
        code, sortie = self.verifier()
        self.assertIn("Composant à ajouter à l'inventaire : lxml (déclaré dans tests/run_all.sh)", sortie)

    def test_python_version(self):
        (self.depot.racine / ".python-version").unlink()
        code, sortie = self.verifier()
        self.assertIn("Composant à retirer de l'inventaire : python", sortie)

    def test_lecture_de_structure_seulement(self):
        # une valeur de configuration voisine (mot de passe de compose, mode du tri) n'apparaît jamais dans la sortie
        texte = (self.depot.racine / "docker-compose.yml").read_text() + "    environment:\n      POSTGRES_PASSWORD: secret-invente\n"
        self.depot.ecrire("docker-compose.yml", texte)
        self.depot.ecrire("tools/c.py", entete(["requests"]))
        code, sortie, erreurs = self.inventaire("--verify")
        self.assertNotIn("secret-invente", sortie + erreurs)
        self.assertNotIn("observation", sortie + erreurs)


class Image(AvecDepot):
    PHRASE = "Empreinte de l'image à mettre à jour avec l'étiquette"

    def compose(self, ancien: str, nouveau: str):
        self.depot.ecrire("docker-compose.yml", (self.depot.racine / "docker-compose.yml").read_text().replace(ancien, nouveau))

    def test_etiquette_changee_seule(self):
        self.compose("image: exemple/base:1.2.0-pg18", "image: exemple/base:1.3.0-pg18")
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn(f"{self.PHRASE} : exemple/base", sortie)

    def test_etiquette_latest_ou_absente(self):
        for image in ("exemple/base:latest", "exemple/base"):
            with self.subTest(image=image):
                self.depot.ecrire("docker-compose.yml", self.depot.fichiers_initiaux[self.depot.racine / "docker-compose.yml"].decode())
                self.compose("image: exemple/base:1.2.0-pg18", f"image: {image}")
                code, sortie, _ = self.inventaire("--verify")
                self.assertEqual(code, 1)
                self.assertIn(self.PHRASE, sortie)

    def test_empreinte_absente(self):
        self.compose("# Digest de l'index multi-architecture tiré : sha256:" + "a" * 64, "# Pas d'empreinte")
        code, sortie, _ = self.inventaire("--verify")
        self.assertEqual(code, 1)
        self.assertIn(self.PHRASE, sortie)


class DepotReel(SansReseau):
    """Le dépôt lui-même : l'inventaire suivi est cohérent avec ses sources, sans réseau (spec « Real repository »)."""

    def test_inventaire_du_depot_a_jour(self):
        code, sortie, erreurs = lancer(["inventory", "--verify", "--root", str(RACINE)])
        self.assertEqual(code, 0, sortie + erreurs)
        self.assertIn("Inventaire à jour", sortie)

    def test_l_etude_laya_est_retiree(self):
        self.assertFalse((RACINE / "tools/etude_laya.py").exists())
        self.assertFalse((RACINE / "tools/etude_laya.py.lock").exists())

    def test_aucune_adresse_dans_l_inventaire(self):
        texte = (RACINE / "docs/pmzilla/composants.yaml").read_text(encoding="utf-8")
        self.assertNotRegex(texte, r"https?://|www\.")


class Fonctions(unittest.TestCase):
    def test_noms_normalises(self):
        self.assertEqual(composants.normaliser("PyYAML"), "pyyaml")
        self.assertEqual(composants.normaliser("psycopg[binary]"), "psycopg")
        self.assertEqual(composants.normaliser("mcp>=1.2,<2"), "mcp")
        self.assertEqual(composants.normaliser("Foo_Bar.baz"), "foo-bar-baz")

    def test_en_tete_sur_plusieurs_lignes(self):
        texte = '# /// script\n# dependencies = [\n#   "pyyaml",\n#   "psycopg[binary]",\n# ]\n# ///\n'
        self.assertEqual(composants.dependances_en_tete(texte), ["pyyaml", "psycopg"])

    def test_paquets_d_un_verrou(self):
        self.assertEqual(composants.paquets_du_verrou(verrou({"PyYAML": "6.0", "numpy": "2.0"})), {"pyyaml": "6.0", "numpy": "2.0"})


if __name__ == "__main__":
    unittest.main()
