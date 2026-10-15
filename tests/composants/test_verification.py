"""`composants.py check` : sémantique des versions, sources amont sur faux serveur, délai, essai à blanc de Python, versions locales,
fichier d'état, échéance hebdomadaire et notification (design.md D3, D5 à D8, D10, D11). Tout hors réseau.

    uv run --with pyyaml python -m unittest discover -s tests/components -v
"""
import ast
import json
import re
import stat
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_composants import SCRIPT, composants  # noqa: E402
from aide_verification import (DIGEST_IMAGE, MANIFESTE_MODELE_A, AvecSources, npm, pypi, sha)  # noqa: E402

c = composants


class Semantique(unittest.TestCase):
    """Natures des versions par écosystème (design.md D8), fonctions pures."""

    def natures(self, ecosysteme, utilisee, candidates):
        return {n.nature: n.disponible for n in c.classer(ecosysteme, utilisee, candidates)}

    def test_pep440_mise_a_jour_majeure_et_preversion_separees(self):
        r = self.natures("pep440", "2.1.0", [("2.2.0", False), ("3.0.0", False), ("3.1.0rc1", False), ("2.1.0", False)])
        self.assertEqual(r, {"update": "2.2.0", "major": "3.0.0", "pre-release": "3.1.0rc1"})

    def test_pep440_post_comptee_comme_publication(self):
        self.assertEqual(self.natures("pep440", "2.1.0", [("2.1.0.post1", False)]), {"update": "2.1.0.post1"})

    def test_pep440_dev_et_alpha_sont_des_preversions(self):
        for v in ("2.2.0a1", "2.2.0b2", "2.2.0.dev3", "2.2.0rc1"):
            with self.subTest(v=v):
                self.assertEqual(self.natures("pep440", "2.1.0", [(v, False)]), {"pre-release": v})

    def test_preversion_plus_ancienne_que_la_stable_ignoree(self):
        self.assertEqual(self.natures("pep440", "2.1.0", [("2.2.0rc1", False), ("2.2.0", False)]), {"update": "2.2.0"})

    def test_zero_majeure(self):
        self.assertEqual(self.natures("pep440", "0.4.2", [("0.5.0", False), ("0.4.3", False)]), {"major": "0.5.0", "update": "0.4.3"})
        self.assertEqual(self.natures("semver", "0.9.0", [("0.10.0", False)]), {"major": "0.10.0"})

    def test_runtime_python(self):
        self.assertEqual(self.natures("python", "3.14", [("3.14.2", False), ("3.15.0", False), ("3.16.0a1", False)]),
                         {"major": "3.15.0", "pre-release": "3.16.0a1"})
        self.assertEqual(self.natures("python", "3.14.0", [("3.14.2", False)]), {"update": "3.14.2"})

    def test_semver_v_initial(self):
        self.assertEqual(self.natures("semver", "v2.2.2", [("2.2.2", False)]), {})
        self.assertEqual(self.natures("semver", "v2.2.2", [("2.3.0", False), ("3.0.0-beta.1", False)]),
                         {"update": "2.3.0", "pre-release": "3.0.0-beta.1"})

    def test_semver_drapeau_preversion(self):
        self.assertEqual(self.natures("semver", "4.5.0", [("4.6.0", True)]), {"pre-release": "4.6.0"})

    def test_etiquettes_de_l_image(self):
        r = self.natures("docker", "0.26.0-pg18", [("0.26.1-pg18", False), ("0.27.0-pg18", False), ("0.26.0-pg19", False),
                                                    ("latest", False), ("main", False), ("0.28.0-rc.1-pg18", False)])
        self.assertEqual(r, {"update": "0.27.0-pg18", "major": "0.26.0-pg19", "pre-release": "0.28.0-rc.1-pg18"})
        self.assertEqual(self.natures("docker", "1.2.0-pg18", [("2.0.0-pg18", False)]), {"major": "2.0.0-pg18"})

    def test_homebrew_revision_ignoree(self):
        self.assertEqual(self.natures("homebrew", "2.50.0", [("2.50.0_1", False)]), {})
        self.assertEqual(self.natures("homebrew", "2.50.0", [("2.51.0", False), ("3.0.0", False)]), {"update": "2.51.0", "major": "3.0.0"})

    def test_version_illisible_ignoree(self):
        self.assertEqual(self.natures("pep440", "1.0.0", [("n'importe quoi", False)]), {})


class Sources(AvecSources):
    """Lecteurs amont sur le faux serveur ; aucune authentification, aucun secret lu."""

    def test_tout_a_jour(self):
        code, sortie, erreurs = self.verifier()
        self.assertEqual(code, 0, sortie + erreurs)
        self.assertIn("Veille des composants : rien de nouveau", sortie)

    def test_mise_a_jour_pypi(self):
        self.serveur.routes["/pypi/numpy/json"] = pypi({"2.1.0": False, "2.1.1": False})
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("Veille des composants : 1 nouveauté(s)", sortie)
        self.assertIn("numpy 2.1.0 → 2.1.1 (mise à jour)", sortie)
        self.assertIn("Job proposé : Mettre à jour numpy 2.1.0 → 2.1.1", sortie)

    def test_version_retiree_ignoree(self):
        self.serveur.routes["/pypi/numpy/json"] = pypi({"2.1.0": False, "2.2.0": True})
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 0)
        self.assertIn("rien de nouveau", sortie)

    def test_majeure_et_preversion_a_part(self):
        self.serveur.routes["/pypi/numpy/json"] = pypi({"2.1.0": False, "3.0.0": False, "3.1.0rc1": False})
        code, sortie, _ = self.verifier()
        self.assertIn("numpy 2.1.0 → 3.0.0 (version majeure)", sortie)
        self.assertIn("numpy 2.1.0 → 3.1.0rc1 (préversion)", sortie)
        self.assertNotIn("(mise à jour)", sortie)

    def test_verrous_en_desaccord_la_plus_recente_compte(self):
        # une version publiée au-delà de tous les verrous est une nouveauté ; le verrou en retard se voit à l'essai à blanc
        code, sortie, _ = self.verifier()
        self.assertEqual(self.etat()["components"]["pyyaml"]["used"], "6.0.3")
        self.serveur.routes["/pypi/pyyaml/json"] = pypi({"6.0.3": False, "6.0.4": False})
        code, sortie, _ = self.verifier("--only", "pyyaml")
        self.assertIn("pyyaml 6.0.3 → 6.0.4 (mise à jour)", sortie)

    def test_module_bmad_avec_v_initial_a_jour_et_job_propose(self):
        self.serveur.routes["/npm/ext-paquet"] = npm("2.1.0", ["2.0.0", "2.1.0"])
        code, sortie, _ = self.verifier()
        self.assertIn("ext v2.0.0 → 2.1.0 (mise à jour)", sortie)
        self.assertIn("Job proposé : Mettre à jour ext v2.0.0 → 2.1.0 (procédure : Update BMAD)", sortie)

    def test_module_bmad_integre_suit_l_installation(self):
        self.serveur.routes["/npm/bmad-method"] = npm("6.2.0", ["6.1.0", "6.2.0"])
        code, sortie, _ = self.verifier()
        self.assertIn("bmad-method 6.1.0 → 6.2.0 (mise à jour)", sortie)
        self.assertNotIn("core 6.1.0 →", sortie)
        self.assertEqual(self.etat()["components"]["core"]["follows"], "bmad-method")

    def test_homebrew_formule_et_cask(self):
        self.serveur.routes["/brew/formula/uv.json"] = {"versions": {"stable": "0.13.1"}, "revision": 1}
        self.serveur.routes["/brew/cask/ollama-app.json"] = {"version": "0.13.0,build"}
        code, sortie, _ = self.verifier()
        self.assertIn("uv 0.13.0 → 0.13.1 (mise à jour)", sortie)
        self.assertIn("ollama 0.12.0 → 0.13.0 (mise à jour)", sortie)

    def test_git_des_outils_xcode_suivi_informatif(self):
        # git vient des Command Line Tools d'Apple : version locale relevée, aucune source amont, jamais de nouveauté
        self.serveur.routes["/brew/formula/git.json"] = {"versions": {"stable": "9.0.0"}, "revision": 0}
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 0, sortie)
        etat = self.etat()["components"]["git"]
        self.assertEqual((etat["used"], etat["novelties"], etat["incomplete"]), ("2.50.0", [], None))
        self.assertNotIn("/brew/formula/git.json", [c for c, _ in self.serveur.requetes])

    def test_node_par_fnm_compare_aux_publications_de_node(self):
        self.serveur.routes["/node/index.json"] = [{"version": "v25.0.0", "lts": False}, {"version": "v24.2.0", "lts": "Krypton"},
                                                   {"version": "v24.1.0", "lts": "Krypton"}]
        code, sortie, _ = self.verifier()
        self.assertIn("node 24.1.0 → 24.2.0 (mise à jour)", sortie)
        self.assertIn("node 24.1.0 → 25.0.0 (version majeure)", sortie)
        self.assertIn("Job proposé : Mettre à jour node 24.1.0 → 24.2.0 (procédure : Update Node.js (fnm))", sortie)
        self.assertNotIn("/brew/formula/node.json", [c for c, _ in self.serveur.requetes])

    def test_publications_de_node_illisibles(self):
        self.serveur.routes["/node/index.json"] = {"pas": "une liste"}
        code, sortie, _ = self.verifier()
        self.assertEqual(self.etat()["components"]["node"]["incomplete"], "UnexpectedBody")

    def test_cask_d_ollama_lue_sous_son_nom_amont(self):
        # Homebrew a renommé la cask « ollama » en « ollama-app » : l'ancienne adresse rend 404, le composant garde son nom local
        self.serveur.routes["/brew/cask/ollama.json"] = {"version": "9.9.9"}
        self.serveur.statuts["/brew/cask/ollama.json"] = 404
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 0, sortie)
        self.assertIn("rien de nouveau", sortie)
        self.assertIsNone(self.etat()["components"]["ollama"]["incomplete"])
        self.assertIn("/brew/cask/ollama-app.json", [c for c, _ in self.serveur.requetes])
        self.assertNotIn("/brew/cask/ollama.json", [c for c, _ in self.serveur.requetes])

    def test_github_brouillons_ignores_et_preversion(self):
        self.serveur.routes["/github/repos/Homebrew/brew/releases"] = [
            {"tag_name": "4.7.0", "draft": True, "prerelease": False},
            {"tag_name": "4.6.1", "draft": False, "prerelease": True}, {"tag_name": "4.6.0", "draft": False, "prerelease": False}]
        code, sortie, _ = self.verifier()
        self.assertIn("homebrew 4.6.0 → 4.6.1 (préversion)", sortie)
        self.assertNotIn("4.7.0", sortie)

    def test_image_ligne_postgresql_et_etiquette_republiee(self):
        self.serveur.routes["/hub/repositories/exemple/base/tags"] = {
            "results": [{"name": "1.2.0-pg18"}, {"name": "1.2.1-pg18"}, {"name": "1.2.0-pg19"}], "next": None}
        self.serveur.routes["/hub/repositories/exemple/base/tags/1.2.0-pg18"] = {"digest": "sha256:" + "b" * 64}
        code, sortie, _ = self.verifier()
        self.assertIn("exemple/base 1.2.0-pg18 → 1.2.1-pg18 (mise à jour)", sortie)
        self.assertIn("exemple/base 1.2.0-pg18 → 1.2.0-pg19 (version majeure)", sortie)
        self.assertIn("(étiquette republiée)", sortie)
        self.assertIn("major-watch-only", self.etat()["components"]["exemple/base"]["flags"])

    def test_pages_de_docker_hub_suivies(self):
        b = self.serveur.base
        self.serveur.routes["/hub/repositories/exemple/base/tags"] = {"results": [{"name": "1.2.0-pg18"}],
                                                                       "next": f"{b}/hub/repositories/exemple/base/tags2"}
        self.serveur.routes["/hub/repositories/exemple/base/tags2"] = {"results": [{"name": "1.3.0-pg18"}], "next": None}
        code, sortie, _ = self.verifier()
        self.assertIn("exemple/base 1.2.0-pg18 → 1.3.0-pg18 (mise à jour)", sortie)

    def test_page_suivante_hors_de_la_base_refusee(self):
        self.serveur.routes["/hub/repositories/exemple/base/tags"] = {"results": [{"name": "1.2.0-pg18"}],
                                                                       "next": "http://192.0.2.1/ailleurs"}
        code, sortie, _ = self.verifier()
        self.assertIn("Veille des composants incomplète : 1 source(s) injoignable(s)", sortie)

    def test_aucune_authentification_envoyee(self):
        self.verifier()
        self.assertTrue(self.serveur.requetes)
        for _, entetes in self.serveur.requetes:
            self.assertFalse({k.lower() for k in entetes} & {"authorization", "cookie", "x-api-key", "private-token"})

    def test_aucun_secret_lu(self):
        (self.maison / ".netrc").write_text("machine x login y password jeton-invente\n")
        self.verifier(GITHUB_TOKEN="jeton-invente", GH_TOKEN="jeton-invente")
        for _, entetes in self.serveur.requetes:
            self.assertNotIn("jeton-invente", json.dumps(entetes))
        self.assertFalse([a for a in self.appels() if a.startswith(("security", "gh "))])
        texte = SCRIPT.read_text()
        for interdit in ("security", "netrc", "TOKEN", "Keychain", "Trousseau", "hosts.yml", "Authorization"):
            self.assertNotIn(interdit, texte)

    def test_only_inconnu(self):
        code, _, erreurs = self.verifier("--only", "inconnu")
        self.assertEqual(code, 2)


class Delai(AvecSources):
    def test_delai_depasse_rend_le_composant_incomplet(self):
        self.serveur.delais["/pypi/numpy/json"] = 2
        self.serveur.routes["/pypi/psycopg/json"] = pypi({"3.2.1": False, "3.2.2": False})
        code, sortie, _ = self.verifier("--timeout", "0.5")
        self.assertEqual(code, 1)                                   # la nouveauté de psycopg décide, pas l'incomplétude
        self.assertIn("Veille des composants incomplète : 1 source(s) injoignable(s)", sortie)
        self.assertIn("numpy : source injoignable (", sortie)
        self.assertIn("psycopg 3.2.1 → 3.2.2 (mise à jour)", sortie)
        self.assertEqual(self.etat()["components"]["numpy"]["incomplete"], "TimeoutError")

    def test_delai_par_variable_et_valeur_invalide(self):
        self.assertEqual(c.delai(None, {"PMZILLA_COMPOSANTS_TIMEOUT": "3"}), 3.0)
        self.assertEqual(c.delai(None, {"PMZILLA_COMPOSANTS_TIMEOUT": "abc"}), c.DELAI_DEFAUT)
        self.assertEqual(c.delai("abc", {}), c.DELAI_DEFAUT)
        self.assertEqual(c.delai("-1", {}), c.DELAI_DEFAUT)
        self.assertEqual(c.delai("1.5", {"PMZILLA_COMPOSANTS_TIMEOUT": "3"}), 1.5)

    def test_aucune_nouvelle_tentative(self):
        self.serveur.statuts["/pypi/numpy/json"] = 503
        self.verifier()
        self.assertEqual(sum(1 for chemin, _ in self.serveur.requetes if chemin == "/pypi/numpy/json"), 1)

    def test_statut_inattendu_et_corps_illisible(self):
        self.serveur.statuts["/pypi/numpy/json"] = 429
        self.serveur.routes["/npm/graphes"] = b"<html>pas du json"
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 0)
        self.assertIn("Veille des composants incomplète : 2 source(s) injoignable(s)", sortie)
        etat = self.etat()
        self.assertEqual(etat["components"]["numpy"]["incomplete"], "HTTPError")
        self.assertEqual(etat["components"]["graphes"]["incomplete"], "JSONDecodeError")
        texte = json.dumps(etat)
        self.assertNotIn("127.0.0.1", texte)
        self.assertNotIn("http", texte)

    def test_serveur_arrete_jamais_code_2(self):
        self.serveur.arreter()
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 0)
        self.assertIn("Veille des composants incomplète", sortie)


class EssaiABlanc(AvecSources):
    def verrous(self) -> dict:
        return {p: p.read_bytes() for p in (self.depot.racine / "tools").glob("*.lock")}

    def test_essai_sur_copies_temporaires(self):
        (self.bin / "uv-sortie-a").write_text("Resolved 3 packages\nUpdate psycopg v3.2.1 -> v3.2.2\nUpdate psycopg-binary v3.2.1 -> v3.2.2\n")
        avant = self.verrous()
        code, sortie, _ = self.verifier()
        self.assertIn("Dépendances Python : a, 2 paquet(s) à mettre à jour", sortie)
        self.assertEqual(self.verrous(), avant)
        appels = [a for a in self.appels() if a.startswith("uv lock --script")]
        self.assertEqual(len(appels), 4)                           # a, b, pmzilla_lab_library, watch_triage
        for appel in appels:
            self.assertIn("--upgrade", appel)
            self.assertIn("--dry-run", appel)
            self.assertNotIn(str(self.depot.racine), appel)
            copie = Path(appel.split("--script ")[1].split()[0])
            self.assertFalse(copie.parent.exists(), "dossier temporaire non supprimé")
        self.assertEqual(self.etat()["scripts"]["a"], {"to_update": 2})

    def test_uv_sans_essai_a_blanc_compare_le_verrou_temporaire(self):
        (self.bin / "uv-lock-help.txt").write_text("Options:\n      --script <SCRIPT>\n")
        (self.bin / "uv-ecrase").touch()                       # le faux uv réécrit le verrou qu'il reçoit
        avant = self.verrous()
        self.verifier()
        self.assertEqual(self.verrous(), avant)
        appels = [a for a in self.appels() if a.startswith("uv lock --script")]
        self.assertTrue(appels)
        self.assertTrue(all("--dry-run" not in a for a in appels))

    def test_uv_qui_reecrit_le_verrou_meme_en_essai_a_blanc(self):
        (self.bin / "uv-ecrase").touch()
        avant = self.verrous()
        self.verifier()
        self.assertEqual(self.verrous(), avant)

    def test_un_script_en_echec(self):
        (self.bin / "uv-echec-b").touch()
        code, sortie, _ = self.verifier()
        etat = self.etat()
        self.assertEqual(etat["scripts"]["b"], {"incomplete": "DryRunFailed"})
        self.assertEqual(etat["components"]["pyyaml"]["incomplete"], "DryRunFailed")
        self.assertIsNone(etat["components"]["numpy"]["incomplete"])
        self.assertIn("a", etat["scripts"])
        self.assertIn("Veille des composants incomplète", sortie)

    def test_jamais_de_synchronisation_ni_de_nettoyage_du_cache(self):
        self.verifier()
        for appel in self.appels():
            self.assertNotRegex(appel, r"^uv (sync|cache|self|tool|pip)\b")

    def test_le_texte_du_script_ne_nettoie_pas_le_cache(self):
        texte = SCRIPT.read_text()
        self.assertNotRegex(texte, r"cache\W+(clean|prune)")
        self.assertNotRegex(texte, r"\"cache\"")


class VersionsLocales(AvecSources):
    INTERDITS = (r"^brew (install|upgrade|update|services)", r"^ollama (pull|serve|run|start)", r"^npm ", r"^docker (pull|run|start|compose)",
                 r"^colima (start|restart)", r"^uv (sync|self|tool|cache)", r"^docker-compose (up|pull|start)")

    def test_outil_absent_enregistre_comme_absent(self):
        self.retirer_commande("colima")
        code, sortie, _ = self.verifier()
        etat = self.etat()
        self.assertEqual(etat["components"]["colima"]["used"], "absent")
        self.assertIsNone(etat["components"]["colima"]["incomplete"])
        self.assertIn("rien de nouveau", sortie)

    def test_version_locale_lue(self):
        self.verifier()
        etat = self.etat()["components"]
        self.assertEqual(etat["uv"]["used"], "0.13.0")
        self.assertEqual(etat["claude"]["used"], "2.0.0")
        self.assertEqual(etat["docker-compose"]["used"], "2.39.0")
        self.assertEqual(etat["homebrew"]["used"], "4.6.0")

    def test_modele_d_embedding_republie(self):
        self.serveur.routes["/ollama-registry/library/modele-a/manifests/latest"] = b'{"autre":1}'
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("(étiquette republiée)", sortie)
        nouveaute = self.etat()["components"]["modele-a"]["novelties"][0]
        self.assertEqual(nouveaute["nature"], "republished")
        self.assertIn("requires-reindex", self.etat()["components"]["modele-a"]["flags"])
        self.assertIn("requires-reindex", sortie)

    def test_modele_a_jour(self):
        self.verifier()
        self.assertEqual(self.etat()["components"]["modele-a"]["novelties"], [])
        self.assertEqual(self.etat()["components"]["modele-a"]["used"], "latest")

    def test_service_de_modeles_arrete(self):
        del self.serveur.routes["/ollama-local/api/tags"]
        self.serveur.statuts["/ollama-local/api/tags"] = 404
        code, sortie, _ = self.verifier()
        etat = self.etat()["components"]
        self.assertEqual(etat["modele-a"]["incomplete"], "HTTPError")
        self.assertEqual(etat["modele-b"]["incomplete"], "HTTPError")
        self.assertIsNone(etat["numpy"]["incomplete"])
        self.assertFalse([a for a in self.appels() if a.startswith("ollama serve") or a.startswith("ollama run")])

    def test_aucune_commande_interdite(self):
        self.serveur.routes["/pypi/numpy/json"] = pypi({"2.1.0": False, "2.2.0": False})
        self.verifier()
        for appel in self.appels():
            for motif in self.INTERDITS:
                self.assertNotRegex(appel, motif)


class Etat(AvecSources):
    def test_ecriture_atomique_et_droits_du_proprietaire(self):
        self.verifier()
        chemin = self.donnees / "composants-etat.json"
        self.assertEqual(stat.S_IMODE(chemin.stat().st_mode), 0o600)
        self.assertEqual([p.name for p in self.donnees.iterdir()], ["composants-etat.json"])
        etat = self.etat()
        self.assertEqual(etat["last_attempt"], "2026-10-12")
        self.assertEqual(etat["last_complete"], "2026-10-12")
        self.assertTrue(etat["complete"])
        self.assertEqual(etat["unreachable"], 0)

    def test_tentative_incomplete_garde_la_derniere_complete(self):
        self.ecrire_etat({"last_attempt": "2026-10-05", "last_complete": "2026-10-05", "notified": []})
        self.serveur.statuts["/pypi/numpy/json"] = 500
        self.verifier()
        etat = self.etat()
        self.assertEqual(etat["last_attempt"], "2026-10-12")
        self.assertEqual(etat["last_complete"], "2026-10-05")
        self.assertFalse(etat["complete"])
        self.assertEqual(etat["unreachable"], 1)

    def test_etat_illisible(self):
        self.donnees.mkdir()
        (self.donnees / "composants-etat.json").write_text("{pas du json")
        code, sortie, erreurs = self.verifier()
        self.assertEqual(code, 2)
        self.assertIn("Veille des composants impossible : état illisible (JSONDecodeError)", sortie + erreurs)
        self.assertEqual(self.serveur.requetes, [])

    def test_etat_non_inscriptible(self):
        self.donnees.mkdir()
        self.donnees.chmod(0o500)
        self.addCleanup(self.donnees.chmod, 0o700)
        code, sortie, erreurs = self.verifier()
        self.assertEqual(code, 2)
        self.assertIn("Veille des composants impossible : état non inscriptible (PermissionError)", sortie + erreurs)

    def test_inventaire_invalide(self):
        self.depot.modifier_inventaire(lambda e: e[0].pop("upstream"))
        code, sortie, erreurs = self.verifier()
        self.assertEqual(code, 2)
        self.assertIn("Veille des composants impossible : inventaire invalide", sortie + erreurs)

    def test_job_propose_dans_l_etat_et_rien_d_ecrit_dans_le_depot(self):
        self.serveur.routes["/npm/ext-paquet"] = npm("2.1.0", ["2.0.0", "2.1.0"])
        self.verifier()
        nouveaute = self.etat()["components"]["ext"]["novelties"][0]
        self.assertEqual(nouveaute, {"nature": "update", "used": "v2.0.0", "available": "2.1.0",
                                     "job": "Mettre à jour ext v2.0.0 → 2.1.0"})
        self.assertEqual(self.etat()["components"]["ext"]["procedure"], "Update BMAD")
        self.assertEqual(self.depot.inchange(), [])

    def test_contenu_sans_adresse_ni_message(self):
        self.serveur.statuts["/npm/graphes"] = 500
        self.verifier()
        texte = (self.donnees / "composants-etat.json").read_text()
        self.assertNotRegex(texte, r"https?://|127\.0\.0\.1|Internal Server Error")

    def test_only_ne_touche_pas_l_etat(self):
        self.verifier("--only", "numpy")
        self.assertFalse((self.donnees / "composants-etat.json").exists())


class Echeance(AvecSources):
    """Échéance hebdomadaire avec rattrapage (fiche C1, design.md D3) ; date injectée."""

    def pas_due(self, code, sortie):
        self.assertEqual(code, 0)
        self.assertIn("Veille des composants : pas due", sortie)
        self.assertEqual(self.serveur.requetes, [])
        self.assertEqual(self.appels(), [])

    def test_jour_hebdomadaire(self):
        code, sortie, _ = self.verifier("--if-due")
        self.assertIn("rien de nouveau", sortie)

    def test_rattrapage_sans_verification_complete(self):
        self.aujourdhui = "2026-10-14"                                   # un mercredi
        code, sortie, _ = self.verifier("--if-due")
        self.assertIn("rien de nouveau", sortie)

    def test_rattrapage_derniere_complete_trop_ancienne(self):
        self.aujourdhui = "2026-10-14"
        self.ecrire_etat({"last_attempt": "2026-10-13", "last_complete": "2026-10-06", "notified": []})
        code, sortie, _ = self.verifier("--if-due")
        self.assertIn("rien de nouveau", sortie)

    def test_pas_due_apres_une_verification_complete(self):
        self.aujourdhui = "2026-10-14"
        self.ecrire_etat({"last_attempt": "2026-10-12", "last_complete": "2026-10-12", "notified": []})
        self.pas_due(*self.verifier("--if-due")[:2])

    def test_pas_due_deja_tentee_aujourd_hui(self):
        self.ecrire_etat({"last_attempt": "2026-10-12", "last_complete": "2026-10-05", "notified": []})
        self.pas_due(*self.verifier("--if-due")[:2])

    def test_jour_reglable(self):
        self.aujourdhui = "2026-10-14"
        self.ecrire_etat({"last_attempt": "2026-10-12", "last_complete": "2026-10-12", "notified": []})
        code, sortie, _ = self.verifier("--if-due", PMZILLA_COMPOSANTS_DAY="wednesday")
        self.assertIn("rien de nouveau", sortie)
        self.assertEqual(c.jour_hebdomadaire({"PMZILLA_COMPOSANTS_DAY": "mardi"}), 1)
        self.assertEqual(c.jour_hebdomadaire({"PMZILLA_COMPOSANTS_DAY": "n'importe"}), 0)

    def test_sans_if_due_toujours_lancee(self):
        self.ecrire_etat({"last_attempt": "2026-10-12", "last_complete": "2026-10-12", "notified": []})
        code, sortie, _ = self.verifier()
        self.assertIn("rien de nouveau", sortie)


class Notification(AvecSources):
    def test_nouvelle_puis_connue(self):
        self.serveur.routes["/pypi/numpy/json"] = pypi({"2.1.0": False, "2.1.1": False})
        code, _, _ = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn(["numpy", "2.1.1"], self.etat()["notified"])
        self.aujourdhui = "2026-10-19"
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 0)
        self.assertIn("numpy 2.1.0 → 2.1.1 (mise à jour)", sortie)

    def test_echec_reseau_seul_ne_notifie_pas(self):
        self.serveur.arreter()
        code, _, _ = self.verifier()
        self.assertEqual(code, 0)

    def test_anciennete_une_fois_le_jour_hebdomadaire(self):
        self.serveur.arreter()
        self.ecrire_etat({"last_attempt": "2026-10-05", "last_complete": "2026-09-14", "notified": []})
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("Aucune vérification complète des composants depuis 4 semaine(s)", sortie)
        self.aujourdhui = "2026-10-13"
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 0)

    def test_anciennete_sous_le_seuil(self):
        self.serveur.arreter()
        self.ecrire_etat({"last_attempt": "2026-10-05", "last_complete": "2026-09-28", "notified": []})
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 0)

    def test_anciennete_seuil_reglable(self):
        self.serveur.arreter()
        self.ecrire_etat({"last_attempt": "2026-10-05", "last_complete": "2026-09-28", "notified": []})
        code, sortie, _ = self.verifier(PMZILLA_COMPOSANTS_STALE_WEEKS="1")
        self.assertEqual(code, 1)

    def test_jamais_complete_depuis_la_premiere_tentative(self):
        self.serveur.arreter()
        self.ecrire_etat({"first_attempt": "2026-09-01", "last_attempt": "2026-10-05", "last_complete": None, "notified": []})
        code, sortie, _ = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("Aucune vérification complète des composants depuis", sortie)


class Source(unittest.TestCase):
    def test_adresses_amont_constantes_remplacables(self):
        texte = SCRIPT.read_text()
        for variable in ("PMZILLA_COMPOSANTS_PYPI", "PMZILLA_COMPOSANTS_NPM", "PMZILLA_COMPOSANTS_HOMEBREW",
                         "PMZILLA_COMPOSANTS_GITHUB", "PMZILLA_COMPOSANTS_DOCKER_HUB", "PMZILLA_COMPOSANTS_NODE", "PMZILLA_COMPOSANTS_OLLAMA_REGISTRY",
                         "PMZILLA_COMPOSANTS_OLLAMA_LOCAL"):
            self.assertIn(variable, texte)

    def test_aucune_commande_d_installation_dans_le_texte(self):
        # seule la lecture des prérequis d'installation (prerequis) compare des mots « brew install » : elle ne lance rien
        for fonction in ast.walk(ast.parse(SCRIPT.read_text())):
            if not isinstance(fonction, ast.FunctionDef) or fonction.name == "prerequis":
                continue
            for n in ast.walk(fonction):
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    self.assertNotRegex(n.value, r"^(install|upgrade|pull|sync|serve|start)$", f"{fonction.name} : {n.value}")


if __name__ == "__main__":
    unittest.main()
