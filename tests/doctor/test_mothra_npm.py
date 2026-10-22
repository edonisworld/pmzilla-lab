"""Contrôle mothra-npm (change mothra-npm-ready, design D3, D5) : Node de mothra/.node-version, node_modules présent et à jour du
verrou, comparés sans réseau ; avertissement seulement, jamais problème ; ignoré sans verrou. Le `node` est une doublure en tête du
PATH (la couture des commandes de la suite, tâche 2.1) ; `npm` et `npx` sont des doublures interdites."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import Labo  # noqa: E402

# Le verrou de Mothra au format de npm (lockfileVersion 3) : entrée racine "", un espace de travail et son lien, une dépendance, une
# dépendance optionnelle d'une autre plateforme.
PAQUETS = {
    "": {"name": "mothra", "version": "0.0.0", "workspaces": ["app"], "devDependencies": {"vitest": "^2.1.0"}},
    "app": {"name": "mothra-app", "version": "0.1.0"},
    "node_modules/mothra-app": {"resolved": "app", "link": True},
    "node_modules/vitest": {"version": "2.1.4", "resolved": "https://registry.npmjs.org/vitest/-/vitest-2.1.4.tgz",
                            "integrity": "sha512-AAAA", "dev": True, "license": "MIT"},
    "node_modules/@esbuild/linux-x64": {"version": "0.21.5", "resolved": "https://registry.npmjs.org/@esbuild/linux-x64/-/linux-x64-0.21.5.tgz",
                                        "integrity": "sha512-BBBB", "cpu": ["x64"], "os": ["linux"], "optional": True, "dev": True},
}
VERROU_JSON = {"name": "mothra", "version": "0.0.0", "lockfileVersion": 3, "requires": True, "packages": PAQUETS}
VERROU = json.dumps(VERROU_JSON, indent=2) + "\n"


def verrou_cache(modifier=None) -> str:
    """Le verrou caché que npm écrit dans node_modules/.package-lock.json : sans entrée racine "", sans le paquet optionnel d'une autre
    plateforme non installé, sérialisé autrement ; jamais une copie octet par octet du verrou."""
    paquets = {k: copy.deepcopy(v) for k, v in PAQUETS.items() if k not in ("", "node_modules/@esbuild/linux-x64")}
    if modifier:
        modifier(paquets)
    return json.dumps({"name": "mothra", "version": "0.0.0", "lockfileVersion": 3, "requires": True, "packages": paquets})


CACHE = verrou_cache()
FIXEE = "22.11.0"


class MothraNpm(Labo):
    def setUp(self):
        super().setUp()
        self.mothra = self.principal / "mothra"
        doublures = {
            "node": 'echo "node $*" >> "$STUB_LOG"\n[ -n "${FAUX_NODE_ABSENT:-}" ] && exit 127\necho "${FAUX_NODE_VERSION:-v22.11.0}"\n',
            "npm": 'echo "INTERDIT npm $*" >> "$STUB_LOG"\nexit 1\n',
            "npx": 'echo "INTERDIT npx $*" >> "$STUB_LOG"\nexit 1\n',
        }
        for nom, corps in doublures.items():
            chemin = self.bin / nom
            chemin.write_text("#!/bin/sh\n" + corps, encoding="utf-8")
            chemin.chmod(0o755)

    def mothra_pret(self, installe=True, recopie=CACHE, verrou=VERROU, fixee=FIXEE):
        self.mothra.mkdir(exist_ok=True)
        (self.mothra / "package-lock.json").write_text(verrou, encoding="utf-8")
        if fixee is not None:
            (self.mothra / ".node-version").write_text(fixee + "\n", encoding="utf-8")
        if installe:
            (self.mothra / "node_modules").mkdir(exist_ok=True)
            (self.mothra / "node_modules" / ".package-lock.json").write_text(recopie, encoding="utf-8")

    def lignes(self, langue="fr", env=None):
        sortie = self.lancer("--language", langue, env=env).stdout
        return [ligne for ligne in sortie.splitlines() if ligne.startswith("mothra-npm")]

    def sans_reseau(self):
        self.assertEqual([a for a in self.appels() if a.startswith("INTERDIT")], [])

    def test_sans_verrou_ignore_avec_sa_raison(self):
        niveau, entree, p = self.niveau("mothra-npm")
        self.assertEqual((niveau, entree["reason"]["key"]), ("skipped", "no_lock"))
        self.assertEqual(p.returncode, 0)
        self.assertEqual(self.lignes(), ["mothra-npm : ignoré : pas de verrou npm de Mothra"])
        self.assertEqual(self.lignes("en"), ["mothra-npm: skipped: no Mothra npm lock"])
        self.assertEqual([a for a in self.appels() if a.startswith("node")], [])
        self.sans_reseau()

    def test_pret_et_bon_node_ok(self):
        self.mothra_pret()
        niveau, _, p = self.niveau("mothra-npm")
        self.assertEqual(niveau, "ok", p.stdout)
        self.assertTrue(self.lancer("--quiet").stdout.strip().endswith("doctor : tout va bien"))
        self.sans_reseau()

    def test_node_d_une_autre_version_avertit_et_nomme_les_deux(self):
        self.mothra_pret()
        env = {"FAUX_NODE_VERSION": "v20.5.1"}
        niveau, entree, p = self.niveau("mothra-npm", env=env)
        self.assertEqual((niveau, entree["reason"]["key"]), ("warning", "node_version"))
        self.assertEqual(p.returncode, 0)
        self.assertEqual(self.lignes(env=env), ["mothra-npm : avertissement : Node v20.5.1 différent de mothra/.node-version (22.11.0)"])
        self.assertEqual(self.lignes("en", env=env), ["mothra-npm: warning: Node v20.5.1 differs from mothra/.node-version (22.11.0)"])
        self.assertIn("node --version", self.appels())
        self.sans_reseau()

    def test_node_absent_avertit(self):
        self.mothra_pret()
        niveau, entree, p = self.niveau("mothra-npm", env={"FAUX_NODE_ABSENT": "1"})
        self.assertEqual((niveau, entree["reason"]["key"]), ("warning", "node_missing"))
        self.assertEqual(p.returncode, 0)
        self.assertIn("22.11.0", self.lignes(env={"FAUX_NODE_ABSENT": "1"})[0])

    def test_verrou_sans_node_modules(self):
        self.mothra_pret(installe=False)
        niveau, entree, p = self.niveau("mothra-npm")
        self.assertEqual((niveau, entree["reason"]["key"]), ("warning", "modules_missing"))
        self.assertEqual(p.returncode, 0)
        self.assertEqual(self.lignes(), ["mothra-npm : avertissement : node_modules absent dans mothra/"])
        self.assertEqual(self.lignes("en"), ["mothra-npm: warning: node_modules missing in mothra/"])

    def test_node_modules_perime(self):
        self.mothra_pret(recopie='{"name": "mothra", "lockfileVersion": 3, "packages": {"ancien": {}}}\n')
        niveau, entree, p = self.niveau("mothra-npm")
        self.assertEqual((niveau, entree["reason"]["key"]), ("warning", "modules_stale"))
        self.assertEqual(p.returncode, 0)
        self.assertEqual(self.lignes(), ["mothra-npm : avertissement : node_modules périmé : verrou plus récent ou différent"])
        self.assertEqual(self.lignes("en"), ["mothra-npm: warning: stale node_modules: lock newer or different"])

    def test_node_modules_sans_verrou_recopie_perime(self):
        self.mothra_pret()
        (self.mothra / "node_modules" / ".package-lock.json").unlink()
        self.assertEqual(self.niveau("mothra-npm")[1]["reason"]["key"], "modules_stale")

    # --- E1 (revue 6.1) : comparaison des entrées du verrou caché, pas des octets --------------------------------------------
    def cle_mothra(self):
        return self.niveau("mothra-npm")[1]["reason"]["key"]

    def test_verrou_cache_au_format_reel_ok(self):
        self.assertNotEqual(CACHE, VERROU)
        self.mothra_pret()
        niveau, _, p = self.niveau("mothra-npm")
        self.assertEqual(niveau, "ok", p.stdout)

    def test_version_differente_dans_le_verrou_cache_perime(self):
        self.mothra_pret(recopie=verrou_cache(lambda p: p["node_modules/vitest"].update(version="2.1.3")))
        self.assertEqual(self.cle_mothra(), "modules_stale")

    def test_integrite_differente_dans_le_verrou_cache_perime(self):
        self.mothra_pret(recopie=verrou_cache(lambda p: p["node_modules/vitest"].update(integrity="sha512-ZZZZ")))
        self.assertEqual(self.cle_mothra(), "modules_stale")

    def test_paquet_ajoute_au_verrou_non_installe_perime(self):
        plus = copy.deepcopy(VERROU_JSON)
        plus["packages"]["node_modules/zod"] = {"version": "3.23.8", "resolved": "https://registry.npmjs.org/zod/-/zod-3.23.8.tgz",
                                                "integrity": "sha512-CCCC"}
        self.mothra_pret(verrou=json.dumps(plus, indent=2))
        self.assertEqual(self.cle_mothra(), "modules_stale")

    def test_paquet_installe_retire_du_verrou_perime(self):
        self.mothra_pret(recopie=verrou_cache(lambda p: p.update({"node_modules/ancien": {"version": "1.0.0", "integrity": "sha512-DDDD"}})))
        self.assertEqual(self.cle_mothra(), "modules_stale")

    def test_verrou_cache_illisible_perime(self):
        self.mothra_pret(recopie="{pas du json")
        self.assertEqual(self.cle_mothra(), "modules_stale")

    def test_entree_racine_du_verrou_ignoree(self):
        autre = copy.deepcopy(VERROU_JSON)
        autre["packages"][""]["version"] = "0.0.1"
        self.mothra_pret(verrou=json.dumps(autre))
        self.assertEqual(self.niveau("mothra-npm")[0], "ok")

    # --- E4 (revue 6.1) : .node-version absent, version comparée exactement -----------------------------------------------
    def test_sans_node_version_avertit_sans_appeler_node(self):
        self.mothra_pret(fixee=None)
        niveau, entree, p = self.niveau("mothra-npm")
        self.assertEqual((niveau, entree["reason"]["key"]), ("warning", "node_unpinned"))
        self.assertEqual(p.returncode, 0)
        self.assertEqual(self.lignes(), ["mothra-npm : avertissement : mothra/.node-version absent : version de Node non vérifiée"])
        self.assertEqual(self.lignes("en"), ["mothra-npm: warning: mothra/.node-version missing: Node version not checked"])
        self.assertEqual([a for a in self.appels() if a.startswith("node")], [])

    def test_version_fixee_comparee_exactement_pas_par_prefixe(self):
        self.mothra_pret(fixee="22")
        niveau, entree, _ = self.niveau("mothra-npm")
        self.assertEqual((niveau, entree["reason"]["key"]), ("warning", "node_version"))

    def test_prefixe_v_de_la_version_fixee_accepte(self):
        self.mothra_pret(fixee="v22.11.0")
        self.assertEqual(self.niveau("mothra-npm")[0], "ok")

    # --- E5 (revue 6.1) : racine de contenu introuvable, raison distincte -------------------------------------------------
    def test_contenu_introuvable_ignore_avec_sa_propre_raison(self):
        import datetime as dt
        from unittest import mock
        import doctor
        import doctor_messages
        hors_git = self.base / "copie"
        hors_git.mkdir()
        env = {k: v for k, v in self.environnement().items() if k not in ("PMZILLA_LAB_WORKSPACE", "PMZILLA_LAB_RUN", "DOCTOR_FLUX")}
        ctx = doctor.Contexte(dt.date(2026, 10, 14), dt.time(9, 0), self.donnees, self.journaux, self.maison, env)
        with mock.patch.object(doctor, "RACINE", hors_git):
            r = doctor.controle_mothra_npm(ctx, [])
        self.assertEqual((r.niveau, r.cle), ("skipped", "content_unknown"))
        for catalogue in doctor_messages.CATALOGS.values():
            self.assertNotEqual(catalogue["raison_content_unknown"], catalogue["raison_mothra_npm_no_lock"])

    def test_une_ligne_par_constat_et_une_seule_entree_json(self):
        self.mothra_pret(installe=False)
        env = {"FAUX_NODE_VERSION": "v20.5.1"}
        niveau, entree, p = self.niveau("mothra-npm", env=env)
        self.assertEqual(niveau, "warning")
        self.assertEqual(entree["reason"]["counts"], {"findings": 2})
        self.assertEqual(self.lignes(env=env), ["mothra-npm : avertissement : Node v20.5.1 différent de mothra/.node-version (22.11.0)",
                                                "mothra-npm : avertissement : node_modules absent dans mothra/"])
        self.assertTrue(self.lancer(env=env).stdout.strip().endswith("doctor : 1 avertissement(s)"))

    def test_jamais_probleme_ni_ecriture(self):
        self.mothra_pret(installe=False)
        avant = self.fichiers()
        p = self.lancer(env={"FAUX_NODE_ABSENT": "1"})
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertNotIn("mothra-npm : problème", p.stdout)
        self.assertEqual(self.fichiers(), avant)
        self.sans_reseau()


if __name__ == "__main__":
    unittest.main()
