"""
Tâche 3.6 (change finish-train-v1) : paquets npm de Mothra dans le worktree d'intégration (conception D10, décision A du 2026-10-27, codes 76, 80 et
81). Quand l'arbre du train porte mothra/package-lock.json, le script lance « npm ci --offline --ignore-scripts --no-audit --no-fund
--no-update-notifier » dans le dossier mothra/ du worktree d'intégration, avant la CI locale et le runner. Refus : 76 (npm introuvable, verrou ou
package.json inutilisable), 80 (version de Node différente de mothra/.node-version), 81 (npm ci hors ligne en échec). Un faux `npm` et un faux
`node`, écrits par le test, sont placés en tête du PATH.
"""
import os
import re
import signal
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain, PREFIXE, E2  # noqa: E402

VERROU = {"mothra/package-lock.json": "{}\n", "mothra/package.json": "{}\n", "mothra/contract/index.js": "c\n"}
VERROU_NODE = {**VERROU, "mothra/.node-version": "22.11.0\n"}
BASE_DB = {"db/001.sql": "SELECT 2;\n", **VERROU}
FAUX_NPM = """#!/bin/bash
echo "npm pwd=$(pwd -P) args=[$*] stdin=[$(cat)]" >> "@ETAT@/appels.log"
[ ! -e /dev/fd/3 ] || echo "descripteur 3 ouvert" >> "@ETAT@/fd-ouverts.log"
[ ! -e /dev/fd/4 ] || echo "descripteur 4 ouvert" >> "@ETAT@/fd-ouverts.log"
case "${FAKE_NPM_MODE:-vert}" in
  vert) mkdir -p node_modules/p node_modules/@mothra && echo "module.exports = 1;" > node_modules/p/index.js && ln -s ../../contract node_modules/@mothra/contract
    echo "npm info bruit"; exit 0 ;;
  cache) echo "npm warn bruit d'avertissement"; echo "npm error code ENOTCACHED"; echo "npm error request to registry failed: cache mode is only-if-cached"
    echo "npm error A complete log of this run can be found in: ${HOME:-/home/x}/.npm/_logs/2026-10-27-debug-0.log"
    echo "npm notice bruit d'information"; exit 1 ;;
  autre) echo "npm warn bruit d'avertissement"; echo "npm ERR! code E404"; echo "npm error 404 Not Found"; exit 3 ;;
  chemin) echo "npm error code EACCES"; echo "npm error path ${HOME:-/home/x}/x"; exit 4 ;;
  sans_ligne_erreur) for i in 1 2 3 4 5 6 7; do echo "sortie $i de npm ${HOME:-/home/x}/p"; done; exit 5 ;;
  sans_sortie) exit 6 ;;
  partiel) mkdir -p node_modules/p; echo "npm error code E404"; exit 1 ;;
  sans_node) echo "env: node: No such file or directory"; exit 127 ;;
  dort) : > "@ETAT@/npm-demarre"; i=0; while [ ! -f "@ETAT@/reveil" ]; do [ "$i" -lt 2400 ] || { echo "faux npm : borne de sécurité de 120 secondes atteinte, reveil jamais écrit par le test"; exit 97; }; i=$((i+1)); sleep 0.05; done; exit 0 ;;
  pipe_ferme) : > "@ETAT@/npm-demarre"; while [ ! -f "@ETAT@/pipe-ferme" ]; do sleep 0.05; done; echo "npm error code ENOTCACHED"; exit 1 ;;
esac
"""
FAUX_NODE = """#!/bin/bash
[ ! -e /dev/fd/3 ] || echo "node : descripteur 3 ouvert" >> "@ETAT@/fd-ouverts.log"
[ ! -e /dev/fd/4 ] || echo "node : descripteur 4 ouvert" >> "@ETAT@/fd-ouverts.log"
echo "node appelé" >> "@ETAT@/appels.log"
[ -z "${FAKE_NODE_MUET:-}" ] || exit 0
echo "v${FAKE_NODE_VERSION:-22.11.0}"
"""


class NpmMothra(AvecTrain):
    def setUp(self):
        super().setUp()
        dossier = self.t.fakes / "bin-npm"
        self.t.poser(dossier / "npm", FAUX_NPM)
        self.t.poser(dossier / "node", FAUX_NODE)
        self.path = f"{dossier}:{self.t.env()['PATH']}"

    def extra(self, **extra):
        return {"PATH": self.path, **extra}

    def lance(self, entree="n\n", **extra):
        return self.t.lance("feat/x", extra=self.extra(**extra), entree=entree)

    def lignes_log(self):
        return self.t.journaux()[-1].read_text(encoding="utf-8").splitlines()

    # --- le chemin vert ----------------------------------------------------------------------------------------------------------------
    def test_npm_ci_hors_ligne_dans_mothra_du_worktree_d_integration(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance()
        self.assertEqual(r.code, 0, r.texte)
        (ligne,) = self.t.appels("npm")
        self.assertIn("/wt-train-", ligne)
        self.assertIn("/mothra args=[ci --offline --ignore-scripts --no-audit --no-fund --no-update-notifier] stdin=[]", ligne)
        self.contient(r, "paquets de Mothra installés dans le worktree d'intégration (npm ci --offline --ignore-scripts)")

    def test_descripteurs_3_et_4_fermes_pendant_npm(self):
        self.t.branche("feat/x", VERROU_NODE)   # avec .node-version : node est lancé lui aussi
        r = self.lance()
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(len(self.t.appels("npm")), 1)
        self.assertEqual(len(self.t.appels("node")), 1)
        self.assertFalse((self.t.etat / "fd-ouverts.log").exists(), "npm ou node hérite d'un descripteur 3 ou 4 ouvert")

    def test_npm_avant_la_ci_et_le_runner(self):
        # R-20261101-114 : le train ne lance plus dbtest, la porte du conteneur (FINISH_TRAIN_CI) le remplace. L'ordre est observable (revue Opus point 5) :
        # le faux ci_local écrit aussi « ci … » dans appels.log, l'ordre exigé est npm, puis le passage du conteneur, puis la passe Mac
        self.t.branche("feat/x", BASE_DB)
        r = self.lance()
        self.assertEqual(r.code, 0, r.texte)
        ordre = [l.split()[0] for l in self.t.appels("") if l.split()[0] in ("npm", "ci", "dbtest", "runner")]
        self.assertEqual(ordre, ["npm", "ci", "runner"])
        ci = (self.t.etat / "ci-appels").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(ci), 1, "la CI locale est appelée une fois")

    def test_arbre_sans_verrou_npm_aucun_appel(self):
        self.t.branche("feat/x")
        r = self.lance()
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.appels("npm"), [])
        self.absent(r, "paquets de Mothra")

    def test_essai_ne_lance_pas_npm(self):
        self.t.branche("feat/x", VERROU)
        r = self.t.lance("--essai", "feat/x", extra=self.extra())
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.appels("npm"), [])

    def test_reprise_s1_ne_lance_pas_npm(self):
        self.t.branche("feat/x", VERROU)
        self.t.etat_fusionne_localement("feat/x", extra=self.extra())
        self.assertEqual(len(self.t.appels("npm")), 1, "le premier passage installe les paquets")
        r = self.t.lance("feat/x", extra=self.extra())
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "reprise : main porte déjà le train")
        self.assertEqual(len(self.t.appels("npm")), 1, "la reprise au push n'installe rien")

    # --- un vrai node_modules dans le worktree d'intégration ----------------------------------------------------------------------------
    def test_node_modules_reel_reponse_n_le_worktree_est_retire(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.worktrees_train(), [])
        self.absent(r, "worktree gardé")

    def test_node_modules_reel_reponse_o_aucun_worktree_garde(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "worktree gardé")
        self.assertEqual(self.t.worktrees_train(), [])

    # --- les refus : 76, 80, 81 --------------------------------------------------------------------------------------------------------
    def test_81_cache_vide_enotcached_avant_tout_runner(self):
        self.t.branche("feat/x", BASE_DB)
        avant = self.t.instantane()
        r = self.lance(entree="o\n", FAKE_NPM_MODE="cache")
        self.code(r, 81, "paquets de Mothra absents du cache npm (npm ci --offline, code 1) ; rien n'est fusionné")
        self.assertEqual(len(self.t.appels("npm")), 1)
        self.assertEqual(self.t.appels("dbtest"), [])
        self.assertEqual(self.t.appels("runner"), [])
        self.assertFalse((self.t.etat / "ci-appels").exists(), "aucun passage de la CI locale avant npm")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.worktrees_train(), [])

    def test_la_sortie_de_npm_est_recopiee_seulement_en_lignes_npm_error(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="cache")
        self.assertEqual(r.code, 81, r.texte)
        self.contient(r, "npm error code ENOTCACHED", "npm error request to registry failed: cache mode is only-if-cached")
        self.absent(r, "bruit d'avertissement", "bruit d'information", "A complete log of this run can be found in", ".npm/_logs")
        journal = "\n".join(self.lignes_log())
        self.assertIn("npm error code ENOTCACHED", journal)
        self.assertNotIn("bruit d'avertissement", journal)
        self.assertNotIn(".npm/_logs", journal, "aucun chemin du dossier personnel dans le journal")
        home = os.environ.get("HOME", "")
        if home:
            self.assertNotIn(home, journal)
            self.assertNotIn(home, r.texte)

    def test_le_dossier_personnel_est_remplace_par_tilde_dans_les_lignes_npm_error(self):
        # les chemins absolus des lignes de CONSEIL (cd "…/mothra" && npm ci …) sont voulus : ce sont des lignes à coller dans le Terminal ; seule la
        # sortie recopiée de npm est réécrite, le dossier personnel y devient ~
        home = os.environ.get("HOME", "")
        self.assertTrue(home, "HOME doit être défini pour ce test")
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="chemin")
        self.assertEqual(r.code, 81, r.texte)
        self.contient(r, "npm error path ~/x")
        self.absent(r, f"npm error path {home}/x")

    def test_81_sans_ligne_npm_error_montre_les_5_dernieres_lignes(self):
        home = os.environ.get("HOME", "")
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="sans_ligne_erreur")
        self.code(r, 81, "npm ci hors ligne en échec (code 5) ; rien n'est fusionné")
        self.contient(r, "aucune ligne npm error ; les 5 dernières lignes de la sortie de npm :", "sortie 7 de npm ~/p", "sortie 3 de npm ~/p")
        refus = r.texte.index(PREFIXE + "npm ci hors ligne en échec (code 5)")
        self.assertLess(r.texte.index("aucune ligne npm error ; les 5 dernières lignes"), refus)
        self.assertLess(r.texte.index("sortie 7 de npm"), refus)
        self.absent(r, "sortie 2 de npm", "sortie 1 de npm")
        if home:
            self.absent(r, f"sortie 7 de npm {home}/p")

    def test_81_sans_aucune_sortie_dit_aucune_ligne_npm_error(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="sans_sortie")
        self.code(r, 81, "npm ci hors ligne en échec (code 6) ; rien n'est fusionné")
        self.contient(r, "aucune ligne npm error\n")

    def test_81_npm_dont_le_node_est_introuvable_exit_127(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="sans_node")
        self.code(r, 81, "npm ci hors ligne en échec (code 127) ; rien n'est fusionné")
        self.contient(r, "env: node: No such file or directory")

    def test_la_ligne_npm_err_ancienne_forme_est_acceptee(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="autre")
        self.contient(r, "npm ERR! code E404", "npm error 404 Not Found")

    def test_81_autre_echec_de_npm_ci_hors_ligne_avec_son_code(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="autre")
        self.code(r, 81, "npm ci hors ligne en échec (code 3) ; rien n'est fusionné")
        self.absent(r, "absents du cache npm", "remplir le cache npm", "branche(s) du train qui modifient")
        self.contient(r, "voir les lignes npm error ci-dessus, puis relancer la même ligne : " + self.t.ligne + " feat/x")

    def test_conseil_branche_qui_modifie_le_verrou_dans_son_worktree(self):
        self.t.branche("feat/x", VERROU)
        self.t.branche("feat/y")
        r = self.t.lance("feat/x", "feat/y", extra=self.extra(FAKE_NPM_MODE="cache"), entree="o\n")
        self.assertEqual(r.code, 81, r.texte)
        self.contient(r, "branche(s) du train qui modifient mothra/package-lock.json : feat/x ;")
        self.contient(r, f'cd {self.t.dossier_worktree("feat/x")}/mothra && npm ci --ignore-scripts && cd {self.t.contenu} && {self.t.ligne} feat/x feat/y')
        self.absent(r, f'cd {self.t.contenu}/mothra', f'cd {self.t.dossier_worktree("feat/y")}/mothra')

    def test_conseil_branche_sans_worktree_commence_par_en_creer_un(self):
        self.t.branche("feat/x", VERROU, worktree=False)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="cache")
        self.assertEqual(r.code, 81, r.texte)
        wt = self.t.dossier_worktree("feat/x")
        self.contient(r, f'git -C {self.t.contenu} worktree add {wt} feat/x && cd {wt}/mothra && npm ci --ignore-scripts && cd {self.t.contenu} && '
                         f'{self.t.ligne} feat/x')

    BASE_VERROU = {**VERROU, "mothra/package-lock.json": "".join(f"ligne {k}\n" for k in range(1, 21))}

    def deux_branches_qui_changent_le_verrou(self, worktree_y=True):
        # le verrou existe déjà sur main ; chaque branche en change une ligne, loin de l'autre : le train se construit sans conflit
        self.t.commit_main(self.BASE_VERROU, "verrou sur main", pousser=True)
        self.t.mettre_a_jour_run()
        verrou = self.BASE_VERROU["mothra/package-lock.json"]
        self.t.branche("feat/x", {"mothra/package-lock.json": verrou.replace("ligne 1\n", "ligne 1 modifiée\n")})
        self.t.branche("feat/y", {"mothra/package-lock.json": verrou.replace("ligne 20\n", "ligne 20 modifiée\n")}, worktree=worktree_y)

    def test_conseil_deux_branches_qui_changent_le_verrou_commandes_enchainees(self):
        self.deux_branches_qui_changent_le_verrou()
        r = self.t.lance("feat/x", "feat/y", extra=self.extra(FAKE_NPM_MODE="cache"), entree="o\n")
        self.assertEqual(r.code, 81, r.texte)
        wx, wy, ws = self.t.dossier_worktree("feat/x"), self.t.dossier_worktree("feat/y"), self.t.contenu
        self.contient(r, "branche(s) du train qui modifient mothra/package-lock.json : feat/x, feat/y ;")
        self.contient(r, f'cd {wx}/mothra && npm ci --ignore-scripts && cd {wy}/mothra && npm ci --ignore-scripts && cd {ws} && {self.t.ligne} feat/x feat/y')

    def test_conseil_une_branche_avec_worktree_mêlée_à_une_sans(self):
        self.deux_branches_qui_changent_le_verrou(worktree_y=False)
        r = self.t.lance("feat/x", "feat/y", extra=self.extra(FAKE_NPM_MODE="cache"), entree="o\n")
        self.assertEqual(r.code, 81, r.texte)
        wx, wy, ws = self.t.dossier_worktree("feat/x"), self.t.dossier_worktree("feat/y"), self.t.contenu
        self.contient(r, f'cd {wx}/mothra && npm ci --ignore-scripts && git -C {ws} worktree add {wy} feat/y && cd {wy}/mothra && npm ci --ignore-scripts && '
                         f'cd {ws} && {self.t.ligne} feat/x feat/y')

    def test_noms_de_branche_proteges_dans_les_lignes_a_coller(self):
        # un nom de branche permis par Git avec des caractères spéciaux du shell est protégé (printf %q) dans toutes les lignes à coller
        self.t.branche("feat/a&b(1)", VERROU, worktree=False)
        r = self.t.lance("feat/a&b(1)", extra=self.extra(FAKE_NPM_MODE="cache"), entree="o\n")
        self.assertEqual(r.code, 81, r.texte)
        protege = "feat/a\\&b\\(1\\)"
        wt = str(self.t.dossier_worktree("feat/a&b(1)")).replace("&", "\\&").replace("(", "\\(").replace(")", "\\)")
        self.contient(r, f'git -C {self.t.contenu} worktree add {wt} {protege} && cd {wt}/mothra && npm ci --ignore-scripts && cd {self.t.contenu} && '
                         f'{self.t.ligne} {protege}')

    def test_chemin_du_worktree_protege_quand_le_nom_de_branche_porte_un_dollar(self):
        # le chemin du worktree à créer est dérivé du nom de branche : le dollar y est protégé (printf %q), jamais entre guillemets doubles
        self.t.branche("feat/a$b", VERROU, worktree=False)
        r = self.t.lance("feat/a$b", extra=self.extra(FAKE_NPM_MODE="cache"), entree="o\n")
        self.assertEqual(r.code, 81, r.texte)
        wt = str(self.t.dossier_worktree("feat/a$b")).replace("$", "\\$")
        self.contient(r, f'git -C {self.t.contenu} worktree add {wt} feat/a\\$b && cd {wt}/mothra && npm ci --ignore-scripts && cd {self.t.contenu} && '
                         f'{self.t.ligne} feat/a\\$b')
        self.absent(r, 'worktree add "', 'cd "')

    def test_chemin_du_worktree_avec_une_espace_est_protege(self):
        self.t.branche("feat/x", VERROU, worktree=False)
        dossier = self.t.dossier / "avec espace"
        self.t.git("worktree", "add", "-q", str(dossier), "feat/x")
        r = self.t.lance("feat/x", extra=self.extra(FAKE_NPM_MODE="cache"), entree="o\n")
        self.assertEqual(r.code, 81, r.texte)
        protege = str(dossier).replace(" ", "\\ ")
        self.contient(r, f"cd {protege}/mothra && npm ci --ignore-scripts && cd {self.t.contenu} && {self.t.ligne} feat/x")

    def test_ordre_du_refus_puis_du_conseil_pour_81_enotcached(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="cache")
        self.assertEqual(r.code, 81, r.texte)
        t = r.texte
        refus = t.index(PREFIXE + "paquets de Mothra absents du cache npm (npm ci --offline, code 1) ; rien n'est fusionné")
        self.assertLess(t.index("npm error code ENOTCACHED"), refus)
        self.assertLess(refus, t.index("remplir le cache npm avec leur propre verrou :"))
        self.assertLess(refus, t.index("npm ci --ignore-scripts"))

    def test_ordre_du_refus_puis_du_conseil_pour_81_autre_echec(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="autre")
        self.assertEqual(r.code, 81, r.texte)
        t = r.texte
        refus = t.index(PREFIXE + "npm ci hors ligne en échec (code 3) ; rien n'est fusionné")
        self.assertLess(t.index("npm ERR! code E404"), refus)
        self.assertLess(refus, t.index("voir les lignes npm error ci-dessus, puis relancer la même ligne : "))

    def test_ordre_du_refus_puis_du_conseil_pour_80(self):
        self.t.branche("feat/x", VERROU_NODE)
        r = self.lance(entree="o\n", FAKE_NODE_VERSION="20.1.0")
        self.assertEqual(r.code, 80, r.texte)
        t = r.texte
        refus = t.index(PREFIXE + "version de Node trouvée 20.1.0, attendue 22.11.0 (mothra/.node-version de l'arbre du train) ; rien n'est fusionné")
        self.assertLess(refus, t.index("passer à la version attendue avec le gestionnaire de versions, puis relancer la même ligne :"))
        self.assertLess(refus, t.index("fnm use --install-if-missing 22.11.0 && "))

    def test_la_version_de_node_du_fichier_est_protegee_dans_la_ligne_fnm(self):
        self.t.branche("feat/x", {**VERROU, "mothra/.node-version": "2$2\n"})
        r = self.lance(entree="o\n", FAKE_NODE_VERSION="22.11.0")
        self.assertEqual(r.code, 80, r.texte)
        self.contient(r, f"fnm use --install-if-missing 2\\$2 && {self.t.ligne} feat/x")

    def test_nom_protege_aussi_dans_la_ligne_fnm_et_la_ligne_de_relance_simple(self):
        self.t.branche("feat/a&b", VERROU_NODE)
        r = self.t.lance("feat/a&b", extra=self.extra(FAKE_NODE_VERSION="20.1.0"), entree="o\n")
        self.code(r, 80)
        self.contient(r, f"fnm use --install-if-missing 22.11.0 && {self.t.ligne} feat/a\\&b")
        r = self.t.lance("feat/a&b", extra=self.extra(FAKE_NPM_MODE="autre"), entree="o\n")
        self.assertEqual(r.code, 81, r.texte)
        self.contient(r, f"relancer la même ligne : {self.t.ligne} feat/a\\&b")

    def test_conseil_sans_branche_qui_modifie_le_verrou_dans_l_espace_de_travail(self):
        self.t.commit_main(VERROU, "verrou npm sur main", pousser=True)
        self.t.mettre_a_jour_run()
        self.t.branche("feat/x")
        r = self.lance(entree="o\n", FAKE_NPM_MODE="cache")
        self.assertEqual(r.code, 81, r.texte)
        self.contient(r, f'cd {self.t.contenu}/mothra && npm ci --ignore-scripts && cd {self.t.contenu} && {self.t.ligne} feat/x')
        self.absent(r, "branche(s) du train qui modifient")

    def test_76_npm_introuvable(self):
        self.t.branche("feat/x", VERROU)
        avant = self.t.instantane()
        # le PATH du test sans aucun dossier qui porte un exécutable npm (le reste, Python compris, est gardé)
        sans_npm = ":".join(d for d in self.t.env()["PATH"].split(":") if not os.access(os.path.join(d, "npm"), os.X_OK))
        # le faux node reste en tête du PATH : node est contrôlé avant npm, la panne attendue est celle de npm
        dossier = self.t.fakes / "bin-node-seul"
        self.t.poser(dossier / "node", FAUX_NODE)
        r = self.t.lance("feat/x", extra={"PATH": f"{dossier}:{sans_npm}"}, entree="o\n")
        self.code(r, 76, "calcul impossible (outil introuvable : npm) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])
        self.rien_ne_change(avant)
        self.assertEqual(self.t.worktrees_train(), [])

    def test_76_ni_node_ni_npm_le_message_est_celui_de_node(self):
        self.t.branche("feat/x", VERROU)
        sans = ":".join(d for d in self.t.env()["PATH"].split(":")
                        if not os.access(os.path.join(d, "node"), os.X_OK) and not os.access(os.path.join(d, "npm"), os.X_OK))
        r = self.t.lance("feat/x", extra={"PATH": sans}, entree="o\n")
        self.code(r, 76, "calcul impossible (outil introuvable : node) ; rien n'est fusionné")
        self.absent(r, "outil introuvable : npm")

    def test_76_node_muet_meme_sans_node_version(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NODE_MUET="1")
        self.code(r, 76, "calcul impossible (version de node illisible) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_76_package_json_absent_du_worktree_d_integration(self):
        self.t.branche("feat/x", {"mothra/package-lock.json": "{}\n"})
        r = self.lance(entree="o\n")
        self.code(r, 76, "calcul impossible (mothra/package.json absent du worktree d'intégration, alors que mothra/package-lock.json est dans l'arbre) ; "
                         "rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_76_le_verrou_n_est_pas_un_fichier(self):
        self.t.branche("feat/x", {"mothra/package-lock.json/x": "{}\n", "mothra/package.json": "{}\n"})
        r = self.lance(entree="o\n")
        self.code(r, 76, "calcul impossible (mothra/package-lock.json de l'arbre du train n'est pas un fichier ordinaire : mode 040000) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_76_le_verrou_est_un_lien_symbolique(self):
        self.t.branche("feat/x", {"mothra/package.json": "{}\n", "mothra/autre.json": "{}\n"})
        wt = self.t.dossier_worktree("feat/x")
        os.symlink("autre.json", wt / "mothra" / "package-lock.json")
        self.t.git("add", "-A", cwd=wt)
        self.t.git("commit", "-q", "-m", "verrou en lien symbolique", cwd=wt)
        r = self.lance(entree="o\n")
        self.code(r, 76, "calcul impossible (mothra/package-lock.json de l'arbre du train n'est pas un fichier ordinaire : mode 120000) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_76_erreur_git_a_la_lecture_du_verrou_distincte_de_son_absence(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_LS_TREE_VERROU_CODE="128")
        self.code(r, 76, "calcul impossible (lecture de mothra/package-lock.json dans l'arbre du train en échec : erreur Git) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])
        # l'absence du verrou, sans erreur Git, n'est pas un refus : test_arbre_sans_verrou_npm_aucun_appel

    def test_76_node_introuvable_avec_npm_present(self):
        self.t.branche("feat/x", VERROU_NODE)
        dossier = self.t.fakes / "bin-npm-seul"
        self.t.poser(dossier / "npm", FAUX_NPM)
        sans_node = ":".join(d for d in self.t.env()["PATH"].split(":") if not os.access(os.path.join(d, "node"), os.X_OK))
        r = self.t.lance("feat/x", extra={"PATH": f"{dossier}:{sans_node}"}, entree="o\n")
        self.code(r, 76, "calcul impossible (outil introuvable : node) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_76_node_introuvable_meme_sans_node_version(self):
        self.t.branche("feat/x", VERROU)   # pas de .node-version : node doit quand même exister (npm l'exige)
        dossier = self.t.fakes / "bin-npm-seul"
        self.t.poser(dossier / "npm", FAUX_NPM)
        sans_node = ":".join(d for d in self.t.env()["PATH"].split(":") if not os.access(os.path.join(d, "node"), os.X_OK))
        r = self.t.lance("feat/x", extra={"PATH": f"{dossier}:{sans_node}"}, entree="o\n")
        self.code(r, 76, "calcul impossible (outil introuvable : node) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_76_node_version_dossier_ou_lien_symbolique(self):
        self.t.branche("feat/x", {**VERROU, "mothra/.node-version/x": "22\n"})
        r = self.lance(entree="o\n")
        self.code(r, 76, "calcul impossible (mothra/.node-version de l'arbre du train n'est pas un fichier ordinaire : mode 040000) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_76_node_version_lien_symbolique(self):
        self.t.branche("feat/x", {**VERROU, "mothra/version.txt": "22\n"})
        wt = self.t.dossier_worktree("feat/x")
        os.symlink("version.txt", wt / "mothra" / ".node-version")
        self.t.git("add", "-A", cwd=wt)
        self.t.git("commit", "-q", "-m", "version en lien symbolique", cwd=wt)
        r = self.lance(entree="o\n")
        self.code(r, 76, "calcul impossible (mothra/.node-version de l'arbre du train n'est pas un fichier ordinaire : mode 120000) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_76_erreur_git_a_la_lecture_de_node_version(self):
        self.t.branche("feat/x", VERROU_NODE)
        r = self.lance(entree="o\n", FAKE_LS_TREE_NODE_VERSION_CODE="128")
        self.code(r, 76, "calcul impossible (lecture de mothra/.node-version dans l'arbre du train en échec : erreur Git) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_76_echec_de_git_show_a_la_lecture_de_node_version(self):
        self.t.branche("feat/x", VERROU_NODE)
        r = self.lance(entree="o\n", FAKE_SHOW_NODE_VERSION_CODE="128")
        self.code(r, 76, "calcul impossible (lecture de mothra/.node-version en échec) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_81_node_modules_partiel_le_worktree_est_retire_sans_etre_garde(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="partiel")
        self.assertEqual(r.code, 81, r.texte)
        self.absent(r, "worktree gardé")
        self.assertEqual(self.t.worktrees_train(), [])

    def test_76_node_version_muet(self):
        self.t.branche("feat/x", VERROU_NODE)
        r = self.lance(entree="o\n", FAKE_NODE_MUET="1")
        self.code(r, 76, "calcul impossible (version de node illisible) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_76_node_version_fichier_vide(self):
        self.t.branche("feat/x", {**VERROU, "mothra/.node-version": " \t\n"})
        r = self.lance(entree="o\n")
        self.code(r, 76, "calcul impossible (mothra/.node-version vide) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_node_version_avec_espaces_tabulations_et_retours_passe(self):
        self.t.branche("feat/x", {**VERROU, "mothra/.node-version": " 22.11.0 \t\r\n\n"})
        r = self.lance(FAKE_NODE_VERSION="22.11.0")
        self.assertEqual(r.code, 0, r.texte)

    def test_80_une_version_majeure_qui_n_est_qu_un_prefixe_de_chiffres_est_refusee(self):
        self.t.branche("feat/x", {**VERROU, "mothra/.node-version": "2\n"})
        r = self.lance(entree="o\n", FAKE_NODE_VERSION="26.12.1")
        self.code(r, 80, "version de Node trouvée 26.12.1, attendue 2 (mothra/.node-version de l'arbre du train) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_80_un_prefixe_de_chiffres_dans_le_mineur_est_refuse(self):
        self.t.branche("feat/x", {**VERROU, "mothra/.node-version": "22.1\n"})
        r = self.lance(entree="o\n", FAKE_NODE_VERSION="22.11.0")
        self.code(r, 80, "version de Node trouvée 22.11.0, attendue 22.1 (mothra/.node-version de l'arbre du train) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("npm"), [])

    def test_node_de_la_version_du_fichier_passe(self):
        self.t.branche("feat/x", VERROU_NODE)
        r = self.lance(FAKE_NODE_VERSION="22.11.0")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(len(self.t.appels("npm")), 1)

    def test_node_version_majeure_seule_dans_le_fichier_passe(self):
        self.t.branche("feat/x", {**VERROU, "mothra/.node-version": "v22\n"})
        r = self.lance(FAKE_NODE_VERSION="22.4.1")
        self.assertEqual(r.code, 0, r.texte)

    def test_80_version_de_node_differente_avant_npm(self):
        self.t.branche("feat/x", VERROU_NODE)
        avant = self.t.instantane()
        r = self.lance(entree="o\n", FAKE_NODE_VERSION="20.1.0")
        self.code(r, 80, "version de Node trouvée 20.1.0, attendue 22.11.0 (mothra/.node-version de l'arbre du train) ; rien n'est fusionné")
        self.contient(r, f"fnm use --install-if-missing 22.11.0 && {self.t.ligne} feat/x")
        self.assertEqual(self.t.appels("npm"), [])
        self.rien_ne_change(avant)
        self.assertEqual(self.t.worktrees_train(), [])

    # --- la bannière et les signaux -------------------------------------------------------------------------------------------------
    def test_bandeau_arret_a_paquets_npm(self):
        self.t.branche("feat/x", VERROU)
        r = self.lance(entree="o\n", FAKE_NPM_MODE="cache")
        self.assertEqual(r.code, 81, r.texte)
        self.contient(r, f"===== arrêt à paquets npm : {E2} =====")

    def test_bandeau_arret_a_la_ci_verrou_present_et_phase_base_rouge(self):
        # R-20261101-114 : la phase base du conteneur remplace dbtest (code 69, D9). L'étape du bandeau est « porte du conteneur » (revue Opus point 4) :
        # la phrase exacte, avec l'état E2, est exigée ; l'ancienne étape « dbtest » reste absente
        self.t.branche("feat/x", BASE_DB)
        r = self.lance(entree="o\n", FAUX_CI_CODE="1",
                       FAUX_CI_LIGNES="ci_passage : phase portable : verte · 1 s\nci_passage : phase base : rouge · 1 s : suite_a\nci_passage : phase e2e : sautée (phase précédente rouge)")
        self.code(r, 69, "phase base du conteneur rouge sur l'arbre du train ; rien n'est fusionné")
        self.assertEqual(len(self.t.appels("npm")), 1)
        self.assertIn(f"===== arrêt à porte du conteneur : {E2} =====", r.texte)
        self.absent(r, "arrêt à dbtest")
        self.assertEqual(self.t.appels("runner"), [], "le runner du Mac n'est pas lancé après une phase base rouge")

    def test_130_pendant_npm(self):
        self.t.branche("feat/x", VERROU)
        avant_main = self.t.main()
        proc = self.t.demarre("feat/x", extra=self.extra(FAKE_NPM_MODE="dort"))
        self.t.attend_fichier("npm-demarre")
        os.killpg(proc.pid, signal.SIGINT)
        self.t.reveille()
        code, _ = self.t.termine(proc)
        self.assertEqual(code, 130)
        lignes = self.lignes_log()
        self.assertEqual(lignes[-1], f"===== arrêt à paquets npm : {E2} =====")
        self.assertEqual(lignes.count(PREFIXE + "interrompu (code 130) : rien n'est fusionné"), 1, "\n".join(lignes))
        self.assertEqual(self.t.main(), avant_main)
        self.assertEqual(self.t.distant_main(), avant_main)
        self.assertEqual(self.t.worktrees_train(), [], "le worktree d'intégration est retiré à la sortie")
        self.assertFalse((self.t.commun() / "pmzilla-fin-en-cours").exists(), "le verrou est libéré")

    def test_141_tube_ferme_pendant_npm(self):
        # Le faux npm (mode pipe_ferme) attend que le test ait fermé le tube de sortie, puis ÉCHOUE avec une ligne « npm error ». Pourquoi échouer : la
        # sortie de npm est capturée par le script, qui n'écrit sur le tube qu'à l'étape suivante. Avec un npm qui réussit, la première écriture sur le
        # tube fermé vient plus tard (étape runner) ; un échec fait écrire le script tout de suite (lignes npm error, conseil, refus), donc le 141 a bien
        # lieu pendant l'étape « paquets npm ».
        self.t.branche("feat/x", VERROU)
        avant_main = self.t.main()
        proc = self.t.demarre("feat/x", extra=self.extra(FAKE_NPM_MODE="pipe_ferme"))
        self.t.attend_fichier("npm-demarre")
        proc.stdout.close()
        (self.t.etat / "pipe-ferme").write_text("x", encoding="utf-8")
        try:
            code = proc.wait(timeout=60)
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        self.assertEqual(code, 141)
        lignes = self.lignes_log()
        self.assertEqual(lignes.count(PREFIXE + "interrompu (code 141) : rien n'est fusionné"), 1, "\n".join(lignes))
        self.assertEqual(lignes[-1], f"===== arrêt à paquets npm : {E2} =====")
        self.assertEqual(self.t.main(), avant_main)
        self.assertEqual(self.t.worktrees_train(), [], "le worktree d'intégration est retiré à la sortie")


if __name__ == "__main__":
    unittest.main()
