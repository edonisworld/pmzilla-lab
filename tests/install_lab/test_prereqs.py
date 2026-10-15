"""
Tests de l'étape prereqs du script d'installation (tools/install_lab_prereqs.py) : formules Homebrew, Claude Code, moteur de conteneurs,
Ollama et ses modèles. Aucun effet réel : simulacres en tête du PATH, HOME et racine factices.

    python3 -W ignore -m unittest discover -s tests/install_lab -p "test_prereqs.py" -q -f
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_install import CasDeBase  # noqa: E402

ARGUMENTS_ETAPE = ("--mode", "fresh", "--step", "prereqs")
MODELES = ("bge-test", "gemma-test:1b")


class Base(CasDeBase):
    def decor(self, formules=("git", "uv", "node"), claude=True, runtime=True, ollama=True, modeles=MODELES, hors_homebrew=()):
        """formules : outils présents ET installés par Homebrew ; hors_homebrew : outils qui répondent sur le PATH sans être
        des formules Homebrew (Git des outils Xcode, Node installé autrement). Les autres sont absents."""
        fx = self.fx
        for f in formules:
            fx.drapeau(f"brew-{f}")
            fx.drapeau(f"outil-{f}")
        for f in hors_homebrew:
            fx.drapeau(f"outil-{f}")
        for f in ("git", "uv", "node"):
            fx.simulacre(f, f'[ "$1" = "--version" ] && [ -e "$INSTALL_LAB_ETAT/outil-{f}" ] && exit 0; exit 1')
        if claude:
            fx.drapeau("claude-ok")
        if runtime:
            fx.drapeau("runtime-up")
        for m in modeles:
            fx.drapeau(f"model-{m}")
        fx.simulacre("claude", '[ "$1" = "--version" ] && [ -e "$INSTALL_LAB_ETAT/claude-ok" ] && exit 0; exit 1')
        # l'installateur officiel simulé : le texte « téléchargé » est exécuté par bash et pose l'état
        fx.simulacre("curl", 'echo \': > "$INSTALL_LAB_ETAT/claude-ok"\'')
        fx.simulacre("docker", '[ "$1" = "info" ] && [ -e "$INSTALL_LAB_ETAT/runtime-up" ] && exit 0; exit 1')
        fx.simulacre("colima", '[ "$1" = "start" ] && { [ -e "$INSTALL_LAB_ETAT/colima-echec" ] && exit 1; : > "$INSTALL_LAB_ETAT/runtime-up"; }; exit 0')
        fx.simulacre("ollama", (
            'E="$INSTALL_LAB_ETAT"\ncase "$1" in\n'
            '  list) echo "NAME ID SIZE MODIFIED"; [ -e "$E/model-bge-test" ] && echo "bge-test:latest abc 1GB now"; '
            '[ -e "$E/model-gemma-test:1b" ] && echo "gemma-test:1b def 8GB now"; exit 0 ;;\n'
            '  pull) : > "$E/model-$2" ;;\nesac'))
        if not ollama:
            (fx.simulacres / "ollama").rename(fx.tmp / "ollama-stash")
        fx.simulacre("brew", (
            'E="$INSTALL_LAB_ETAT"\n[ -e "$E/brew-echec" ] && [ "$1" = "install" ] && exit 1\ncase "$1" in\n'
            '  list) [ -e "$E/brew-$3" ] ; exit $? ;;\n'
            '  install) shift; if [ "$1" = "--cask" ]; then cp "$(dirname "$0")/../ollama-stash" "$(dirname "$0")/ollama"; '
            'else for f in "$@"; do : > "$E/brew-$f"; : > "$E/outil-$f"; done; fi ;;\nesac'))

    def lancer(self, *extra, reponses=""):
        return self.fx.lancer(*ARGUMENTS_ETAPE, *extra, reponses=reponses)

    def changements(self, p):
        return self.fx.appels_qui_changent(p.appels)


class TousPresents(Base):
    def test_deja_fait_rien_ne_change(self):
        self.decor()
        p = self.lancer()
        self.assertEqual(p.code, 0, p.texte)
        self.assertIn("step prereqs: already done, skipped", p.texte)
        self.assertEqual(self.changements(p), [])

    def test_modeles_lus_dans_la_configuration_et_jamais_docker_desktop(self):
        self.decor(modeles=(), ollama=True)
        p = self.lancer(reponses="y\ny\n")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual([a for a in p.appels if a.startswith("ollama pull")],
                         ["ollama pull bge-test", "ollama pull gemma-test:1b"])
        self.assertEqual([a for a in p.appels if a.split()[0] in ("open", "osascript")], [])


class Homebrew(Base):
    def test_brew_absent_et_un_outil_manque_est_une_action_manuelle(self):
        self.decor(formules=("uv",))
        self.fx.retirer("brew")
        p = self.lancer()
        self.assertEqual(p.code, 4, p.texte)
        self.assertIn("https://brew.sh", p.texte)
        self.assertEqual(self.changements(p), [])

    def test_brew_absent_mais_tout_present_n_est_pas_un_probleme(self):
        """Homebrew n'est réclamé que si quelque chose manque : une machine complète sans Homebrew est déjà prête."""
        self.decor()
        self.fx.retirer("brew")
        p = self.lancer()
        self.assertEqual(p.code, 0, p.texte)
        self.assertIn("step prereqs: already done, skipped", p.texte)

    def test_outils_manquants_une_confirmation_puis_second_passage(self):
        self.decor(formules=("uv",))
        p = self.lancer(reponses="y\n")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.changements(p), ["brew install git node"])
        q = self.lancer()
        self.assertIn("already done, skipped", q.texte)
        self.assertEqual((q.code, self.changements(q)), (0, []))

    def test_outil_present_hors_homebrew_n_est_pas_propose(self):
        """Git des outils Xcode, Node installé autrement : ils répondent sur le PATH, Homebrew n'est pas sollicité pour eux."""
        self.decor(formules=("uv",), hors_homebrew=("git", "node"))
        p = self.lancer()
        self.assertEqual(p.code, 0, p.texte)
        self.assertIn("step prereqs: already done, skipped", p.texte)
        self.assertEqual(self.changements(p), [])
        self.assertEqual([a for a in p.appels if a.startswith("brew list")], [], "la présence se juge sur le PATH, pas sur brew list")

    def test_outil_present_par_homebrew_n_est_pas_propose(self):
        self.decor(formules=("git", "uv", "node"))
        p = self.lancer()
        self.assertIn("already done, skipped", p.texte)
        self.assertEqual(self.changements(p), [])

    def test_seul_l_outil_absent_est_propose(self):
        self.decor(formules=("uv",), hors_homebrew=("git",))
        p = self.lancer(reponses="y\n")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.changements(p), ["brew install node"])

    def test_outil_absent_en_passage_a_blanc(self):
        self.decor(formules=("uv",), hors_homebrew=("git",))
        p = self.lancer("--dry-run")
        self.assertIn("dry run: would run brew install node", p.texte)
        self.assertEqual(self.changements(p), [])

    def test_refus_par_defaut(self):
        self.decor(formules=())
        p = self.lancer(reponses="")
        self.assertEqual(p.code, 4, p.texte)
        self.assertEqual(self.changements(p), [])

    def test_echec_de_brew_arrete_avec_le_code_1(self):
        self.decor(formules=())
        self.fx.drapeau("brew-echec")
        p = self.lancer(reponses="y\n")
        self.assertEqual(p.code, 1, p.texte)
        self.assertIn("prereqs", p.texte)
        self.assertIn("brew install", p.texte)


class ClaudeCode(Base):
    def test_installateur_officiel_confirme_puis_second_passage(self):
        self.decor(claude=False)
        p = self.lancer(reponses="y\n")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.changements(p), ["curl -fsSL https://claude.ai/install.sh"])
        self.assertIn("sh -c", p.texte)
        q = self.lancer()
        self.assertEqual((q.code, self.changements(q)), (0, []))

    def test_refus(self):
        self.decor(claude=False)
        p = self.lancer(reponses="n\n")
        self.assertEqual(p.code, 4, p.texte)
        self.assertEqual(self.changements(p), [])


class MoteurDeConteneurs(Base):
    def test_trois_confirmations_dans_l_ordre(self):
        self.decor(runtime=False)
        p = self.lancer(reponses="y\ny\ny\n")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.changements(p), [
            "brew install colima docker docker-compose", "brew services start colima", "colima start --cpu 4 --memory 6"])
        q = self.lancer()
        self.assertEqual((q.code, self.changements(q)), (0, []))

    def test_refus_reporte_la_base_le_serveur_et_la_sauvegarde(self):
        self.decor(runtime=False)
        p = self.lancer(reponses="")
        self.assertEqual(p.code, 4, p.texte)
        self.assertEqual(self.changements(p), [])
        for ligne in ("database step deferred", "library server step deferred", "backup job not installed"):
            self.assertIn(ligne, p.texte)

    def test_refus_apres_une_acceptation_arrete_la_proposition(self):
        self.decor(runtime=False)
        p = self.lancer(reponses="y\nn\n")
        self.assertEqual(p.code, 4, p.texte)
        self.assertEqual(self.changements(p), ["brew install colima docker docker-compose"])
        self.assertIn("backup job not installed", p.texte)

    def test_echec_du_demarrage(self):
        self.decor(runtime=False)
        self.fx.drapeau("colima-echec")
        p = self.lancer(reponses="y\ny\ny\n")
        self.assertEqual(p.code, 1, p.texte)
        self.assertIn("colima start", p.texte)

    def test_moteur_present_ne_propose_rien(self):
        self.decor(runtime=True, modeles=())
        p = self.lancer(reponses="n\nn\n")
        self.assertNotIn("colima", " ".join(self.changements(p)))
        self.assertNotIn("database step deferred", p.texte)


class Ollama(Base):
    def test_absent_cask_puis_modeles_avec_tailles(self):
        self.decor(ollama=False, modeles=())
        p = self.lancer(reponses="y\ny\ny\n")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.changements(p), ["brew install --cask ollama-app", "ollama pull bge-test", "ollama pull gemma-test:1b"])
        self.assertIn("about 1.2 GB", p.texte)
        self.assertIn("about 18 GB", p.texte)
        q = self.lancer()
        self.assertEqual((q.code, self.changements(q)), (0, []))

    def test_application_sans_ligne_de_commande_etape_manuelle_sans_brew(self):
        self.decor(ollama=False, modeles=())
        (self.fx.tmp / "Applications" / "Ollama.app").mkdir(parents=True)
        p = self.lancer(reponses="y\ny\ny\n")
        self.assertEqual(p.code, 4, p.texte)
        self.assertEqual(self.changements(p), [])
        self.assertEqual(p.appels_de("brew"), [])
        self.assertIn("Ollama.app", p.texte)
        self.assertIn("watch job not installed", p.texte)
        self.assertIn("indexing deferred", p.texte)

    def test_ollama_refuse_reporte_la_veille_et_l_indexation(self):
        self.decor(ollama=False, modeles=())
        p = self.lancer(reponses="")
        self.assertEqual(p.code, 4, p.texte)
        self.assertEqual(self.changements(p), [])
        self.assertIn("watch job not installed", p.texte)
        self.assertIn("indexing deferred", p.texte)

    def test_un_modele_refuse(self):
        self.decor(modeles=())
        p = self.lancer(reponses="y\nn\n")
        self.assertEqual(p.code, 4, p.texte)
        self.assertEqual(self.changements(p), ["ollama pull bge-test"])
        self.assertIn("watch job not installed", p.texte)

    def test_configuration_illisible_echoue(self):
        self.decor(modeles=())
        (self.fx.racine / "watch" / "tri.yaml").write_text("mode: filtre\n", encoding="utf-8")
        p = self.lancer(reponses="y\ny\n")
        self.assertEqual(p.code, 1, p.texte)
        self.assertIn("prereqs", p.texte)
        self.assertEqual(self.changements(p), [])


class PassageABlanc(Base):
    def test_rien_ne_change(self):
        self.decor(formules=(), claude=False, runtime=False, ollama=False, modeles=())
        avant = self.fx.empreinte()
        p = self.lancer("--dry-run")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.fx.empreinte(), avant)
        self.assertEqual(self.changements(p), [])
        for texte in ("dry run: would run brew install git uv node", "colima start", "brew install --cask ollama-app"):
            self.assertIn(texte, p.texte)


if __name__ == "__main__":
    unittest.main()
