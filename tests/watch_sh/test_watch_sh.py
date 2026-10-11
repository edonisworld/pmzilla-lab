"""
Tests de l'enchaînement de tools/watch.sh avec de fausses commandes.

    python3 -m unittest discover -s tests/watch_sh -v

Le script est lancé avec un faux HOME. Il place `$HOME/.local/bin` en tête du PATH : on y met un faux `uv`, un
faux `curl` et un faux `osascript` (la notification macOS), qui notent leurs appels dans un fichier et échouent à la demande (variable ECHEC : liste de
« script.py commande » séparés par des virgules ; CURL_CODE : code de sortie du faux curl). La vraie veille,
les vrais scripts, Ollama et launchd ne sont jamais touchés.
"""
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "watch.sh"

FAUX_UV = """#!/bin/sh
# uv run <script> [commande...] : note « script commande » et échoue si ECHEC le demande
# uv --version et uv python find --show-version : versions de FAUX_UV_VERSION et FAUX_PYTHON_VERSION (sans note)
[ "$1" = "--version" ] && { echo "uv ${FAUX_UV_VERSION:-0.13.0}"; exit 0; }
[ "$1" = "python" ] && { [ -n "${FAUX_PYTHON_ABSENT:-}" ] && exit 2; echo "${FAUX_PYTHON_VERSION:-3.14.8}"; exit 0; }
echo "$* (args complets)" >> "$APPELS_COMPLETS"
[ "$2" = "--python" ] && set -- "$1" "$4"   # uv run --python <version> <script> : le script redevient le 2e argument
script=$(basename "$2")
appel="$script${3:+ $3}"
# le script jetable du contrôle : « controle_cache.py » avec le réseau, « controle_cache.py hors-ligne » avec UV_OFFLINE
if [ "$script" = "controle_cache.py" ]; then
  [ -n "${UV_OFFLINE:-}" ] && appel="controle_cache.py hors-ligne"
  cp "$2" "$HOME/jetable-${UV_OFFLINE:+hors-ligne}.py"
fi
echo "$appel" >> "$APPELS"
case ",${ECHEC:-}," in *",$appel,"*) echo "faux échec de $appel" >&2; exit "${ECHEC_CODE:-1}";; esac
echo "faux uv : $appel"
exit 0
"""
FAUX_OSASCRIPT = """#!/bin/sh
echo "osascript $*" >> "$APPELS"
exit "${OSASCRIPT_CODE:-0}"
"""
FAUX_CURL = """#!/bin/sh
echo "curl $*" >> "$APPELS"
exit "${CURL_CODE:-0}"
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, True)
        bin_ = self.home / ".local" / "bin"
        bin_.mkdir(parents=True)
        for nom, texte in (("uv", FAUX_UV), ("curl", FAUX_CURL), ("osascript", FAUX_OSASCRIPT)):
            (bin_ / nom).write_text(texte)
            (bin_ / nom).chmod(0o755)
        outils = self.home / "PMZilla-Lab" / "workspace" / "tools"      # watch.sh y appelle watch_paths.py (le vrai)
        outils.mkdir(parents=True)
        shutil.copy(SCRIPT.parent / "watch_paths.py", outils / "watch_paths.py")
        self.appels = self.home / "appels.txt"
        self.complets = self.home / "complets.txt"
        reveil = self.home / "PMZilla-Lab" / "workspace" / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts"
        reveil.mkdir(parents=True)
        (reveil / "wake.py").write_text("# /// script\n# dependencies = [\"pyyaml\"]\n# ///\nraise SystemExit('jamais exécuté')\n")
        self.versions()   # par défaut, les versions enregistrées sont celles du faux uv : pas de contrôle du cache

    def versions(self, uv: str = "uv 0.13.0", python: str = "3.14.8"):
        """Versions de uv et de Python enregistrées par la veille (fichiers de ~/.pmzilla-lab)."""
        donnees = self.home / ".pmzilla-lab"
        donnees.mkdir(parents=True, exist_ok=True)
        (donnees / "uv-version").write_text(uv + "\n")
        (donnees / "uv-python-version").write_text(python + "\n")

    def repere(self, jours: float | None = None, contenu: str | None = None) -> Path:
        """Date de la dernière indexation réussie, il y a `jours` jours (fichier repère de watch.sh)."""
        fichier = self.home / ".pmzilla-lab" / "derniere-indexation"
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(contenu if contenu is not None else str(int(time.time() - jours * 86400)))
        return fichier

    def lancer(self, echec: str = "", curl: int = 0, osascript: int = 0, **environnement):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_LAB_DATA", "PMZILLA_INDEXATION_MAX_JOURS")}
        env = {**env, **environnement, "HOME": str(self.home), "APPELS": str(self.appels),
               "APPELS_COMPLETS": str(self.complets), "ECHEC": echec, "CURL_CODE": str(curl),
               "OSASCRIPT_CODE": str(osascript)}
        resultat = subprocess.run(["zsh", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60)
        appels = self.appels.read_text().splitlines() if self.appels.exists() else []
        self.notifications = [a for a in appels if a.startswith("osascript")]
        return resultat, [a for a in appels if not a.startswith(("curl", "osascript"))]


class WatchSh(Base):
    def test_chemin_nominal_enchaine_toutes_les_etapes_dans_l_ordre(self):
        resultat, appels = self.lancer()
        self.assertEqual(appels, [
            "watch_lab.py collect", "watch_triage.py score", "watch_triage.py apply", "watch_triage.py shares",
            "watch_triage.py digest", "pmzilla_lab_library.py index", "dashboard.py"])
        self.assertEqual(resultat.returncode, 0)
        self.assertNotIn("erreur", resultat.stdout.lower().replace("sans erreur", ""))
        self.assertTrue(resultat.stdout.rstrip().endswith("=== Veille terminée sans erreur ==="))
        self.assertEqual(self.notifications, [])   # aucune notification quand tout va bien

    def activer_synchro(self):
        marqueur = self.home / ".pmzilla-lab" / "knowledge-sync"
        marqueur.parent.mkdir(parents=True, exist_ok=True)
        marqueur.write_text("")

    def test_synchro_postgres_absente_tant_que_le_marqueur_n_existe_pas(self):
        _, appels = self.lancer()
        self.assertFalse(any("knowledge_import" in a for a in appels))

    def test_synchro_postgres_apres_l_indexation_quand_activee(self):
        self.activer_synchro()
        resultat, appels = self.lancer()
        self.assertEqual(appels[-4:], ["pmzilla_lab_library.py index", "knowledge_import.py import", "knowledge_import.py verify", "dashboard.py"])
        self.assertEqual(resultat.returncode, 0)
        self.assertEqual(self.notifications, [])
        complet = next(l for l in self.complets.read_text().splitlines() if "knowledge_import.py" in l)
        self.assertIn(f"{self.home}/PMZilla-Lab/workspace/tools/knowledge_import.py import", complet)

    def test_synchro_postgres_en_echec_notifie_sans_bloquer_la_veille(self):
        self.activer_synchro()
        resultat, appels = self.lancer(echec="knowledge_import.py import")
        self.assertEqual(resultat.returncode, 0)                                  # la veille réussit
        self.assertIn("dashboard.py", appels)                                     # la suite continue
        self.assertIn("Synchronisation PostgreSQL en erreur", resultat.stdout)
        self.assertTrue(resultat.stdout.rstrip().endswith("=== Veille terminée sans erreur ==="))
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("PostgreSQL", self.notifications[0])

    def test_synchro_postgres_en_echec_ne_lance_pas_le_controle(self):
        self.activer_synchro()
        _, appels = self.lancer(echec="knowledge_import.py import")
        self.assertNotIn("knowledge_import.py verify", appels)

    def test_controle_index_bm25_illisible_journalise_et_notifie_sans_bloquer(self):
        self.activer_synchro()
        resultat, appels = self.lancer(echec="knowledge_import.py verify", ECHEC_CODE="3")
        self.assertEqual(resultat.returncode, 0)                                  # la veille réussit, même code de sortie qu'avant
        self.assertIn("dashboard.py", appels)                                     # la suite continue
        self.assertIn("Index BM25 illisible", resultat.stdout)
        self.assertIn("Damaged BM25 index", resultat.stdout)
        self.assertTrue(resultat.stdout.rstrip().endswith("=== Veille terminée sans erreur ==="))
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("BM25", self.notifications[0])
        self.assertIn("installation.md", self.notifications[0])

    def test_controle_ecart_de_copie_journalise_et_notifie_sans_bloquer(self):
        self.activer_synchro()
        resultat, appels = self.lancer(echec="knowledge_import.py verify", ECHEC_CODE="1")
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("dashboard.py", appels)
        self.assertIn("Vérification de la copie PostgreSQL en échec (code 1)", resultat.stdout)
        self.assertNotIn("Index BM25 illisible", resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("installation.md", self.notifications[0])

    def test_controle_reussi_ne_notifie_rien(self):
        self.activer_synchro()
        resultat, appels = self.lancer()
        self.assertIn("knowledge_import.py verify", appels)
        self.assertEqual(self.notifications, [])
        self.assertNotIn("BM25", resultat.stdout)

    def test_synchro_postgres_pas_lancee_si_l_indexation_echoue(self):
        self.activer_synchro()
        _, appels = self.lancer(echec="pmzilla_lab_library.py index")
        self.assertFalse(any("knowledge_import" in a for a in appels))

    def test_synchro_postgres_pas_lancee_sans_ollama(self):
        self.activer_synchro()
        _, appels = self.lancer(curl=7)
        self.assertFalse(any("knowledge_import" in a for a in appels))

    def test_journal_horodate_et_les_deux_dossiers_indexes(self):
        resultat, _ = self.lancer()
        self.assertRegex(resultat.stdout.splitlines()[0], r"^=== \d{4}-\d{2}-\d{2} \d{2}:\d{2} ===$")
        index = next(l for l in self.complets.read_text().splitlines() if "pmzilla_lab_library.py index" in l)
        self.assertIn(f"{self.home}/PMZilla-Lab/workspace/Bibliotheque-Lab", index)   # toujours les deux dossiers
        self.assertIn(f"{self.home}/PMZilla-Lab/workspace/Watch-Lab", index)           # aucun dossier : le nouveau nom
        for appel in self.complets.read_text().splitlines()[:6]:
            self.assertIn(f"{self.home}/PMZilla-Lab/", appel)   # les scripts sont appelés par leur chemin lié

    def test_dossier_de_la_veille_a_l_ancien_nom_refuse_sans_rien_lancer(self):
        ws = self.home / "PMZilla-Lab" / "workspace"
        (ws / "Veille-Lab").mkdir()
        resultat, appels = self.lancer()
        self.assertNotEqual(resultat.returncode, 0)
        self.assertEqual(appels, [])                                  # aucune étape n'a tourné
        self.assertIn("Veille-Lab", resultat.stderr)
        self.assertIn("Watch-Lab", resultat.stderr)
        self.assertIn("migrate_watch.py", resultat.stderr)
        (ws / "Watch-Lab").mkdir()                                   # les deux : le nouveau est pris, sans message
        resultat, _ = self.lancer()
        index = next(l for l in self.complets.read_text().splitlines() if "pmzilla_lab_library.py index" in l)
        self.assertIn(f"{ws}/Watch-Lab ", index)
        self.assertNotIn("Veille-Lab", index)
        self.assertNotIn("Veille-Lab", resultat.stderr)

    def test_ollama_absent_liste_simple_sans_pre_tri_ni_index(self):
        self.repere(jours=1)
        resultat, appels = self.lancer(curl=7)
        self.assertEqual(appels, ["watch_lab.py collect", "watch_lab.py digest", "dashboard.py"])
        self.assertIn("Ollama ne répond pas : pré-tri et indexation reportés au prochain passage", resultat.stdout)
        self.assertEqual(resultat.returncode, 0)   # report prévu, pas un échec
        self.assertEqual(self.notifications, [])

    def test_indexation_reussie_ecrit_le_repere_et_echouee_le_laisse(self):
        self.lancer()
        avant = int(time.time())
        repere = self.home / ".pmzilla-lab" / "derniere-indexation"
        self.assertLessEqual(avant - int(repere.read_text()), 60)
        repere.write_text("1000")
        self.lancer(echec="pmzilla_lab_library.py index")
        self.assertEqual(repere.read_text().strip(), "1000")       # un échec ne rafraîchit pas le repère
        self.lancer(curl=7)
        self.assertEqual(repere.read_text().strip(), "1000")       # Ollama absent : pas d'indexation, pas de repère

    def test_ollama_absent_index_recent_pas_de_notification(self):
        self.repere(jours=2.5)
        resultat, _ = self.lancer(curl=7)
        self.assertEqual(self.notifications, [])
        self.assertNotIn("obsolète", resultat.stdout)
        self.assertEqual(resultat.returncode, 0)

    def test_ollama_absent_index_trop_ancien_notifie_sans_code_de_sortie(self):
        self.repere(jours=4)
        resultat, appels = self.lancer(curl=7)
        self.assertEqual(resultat.returncode, 0)                    # jamais un échec
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("display notification", self.notifications[0])
        self.assertIn("depuis 4 jours", self.notifications[0])
        self.assertIn('with title "PMZilla watch"', self.notifications[0])
        self.assertIn("Index obsolète : dernière indexation réussie il y a 4 jour(s) (seuil : 3)", resultat.stdout)
        self.assertNotIn("pmzilla_lab_library.py index", appels)

    def test_seuil_reglable(self):
        self.repere(jours=2)
        resultat, _ = self.lancer(curl=7, PMZILLA_INDEXATION_MAX_JOURS="1")
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("(seuil : 1)", resultat.stdout)
        self.appels.unlink()
        self.repere(jours=10)
        self.lancer(curl=7, PMZILLA_INDEXATION_MAX_JOURS="30")
        self.assertEqual(self.notifications, [])                    # seuil large : pas de notification
        self.appels.unlink()
        self.lancer(curl=7, PMZILLA_INDEXATION_MAX_JOURS="beaucoup")  # valeur invalide : retour à 3 jours
        self.assertEqual(len(self.notifications), 1)

    def test_seuil_exact_pas_de_notification(self):
        self.repere(jours=2.99)
        self.lancer(curl=7)
        self.assertEqual(self.notifications, [])

    def test_ollama_absent_sans_repere_ni_index_connu(self):
        resultat, _ = self.lancer(curl=7)
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("Aucune indexation réussie connue", resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("aucune indexation réussie connue", self.notifications[0])

    def test_repere_illisible_traite_comme_inconnu(self):
        self.repere(contenu="pas une date")
        self.lancer(curl=7)
        self.assertEqual(len(self.notifications), 1)

    def test_avant_le_premier_repere_on_se_fie_a_l_index_lui_meme(self):
        index = self.home / ".pmzilla-lab" / "library.sqlite"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text("")
        ancien = time.time() - 6 * 86400
        os.utime(index, (ancien, ancien))
        resultat, _ = self.lancer(curl=7)
        self.assertIn("il y a 6 jour(s)", resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.appels.unlink()
        index.touch()
        self.lancer(curl=7)
        self.assertEqual(self.notifications, [])                    # index récent : rien

    def test_notification_ollama_impossible_ne_change_rien(self):
        self.repere(jours=5)
        resultat, _ = self.lancer(curl=7, osascript=1)
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("Notification macOS impossible", resultat.stdout)

    def test_collecte_en_erreur_est_journalisee_et_la_suite_continue(self):
        resultat, appels = self.lancer(echec="watch_lab.py collect")
        self.assertIn("Collecte en erreur", resultat.stdout)
        self.assertIn("_rapport_collecte.txt", resultat.stdout)
        self.assertIn("pmzilla_lab_library.py index", appels)   # l'index se met à jour malgré tout
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("=== Veille terminée avec 1 étape(s) en échec : collecte ===", resultat.stdout)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("display notification", self.notifications[0])
        self.assertIn("collecte", self.notifications[0])

    def test_echec_du_pre_tri_bascule_sur_la_liste_non_triee_et_arrete_la_chaine(self):
        for etape in ("score", "apply", "shares", "digest"):
            with self.subTest(etape=etape):
                self.appels.unlink(missing_ok=True)
                self.complets.unlink(missing_ok=True)
                resultat, appels = self.lancer(echec=f"watch_triage.py {etape}")
                ordre = ["score", "apply", "shares", "digest"]
                attendu_tri = [f"watch_triage.py {e}" for e in ordre[:ordre.index(etape) + 1]]
                self.assertEqual([a for a in appels if a.startswith("watch_triage.py")], attendu_tri)  # arrêt au premier échec
                self.assertIn("Pré-tri en erreur : liste à lire non triée", resultat.stdout)
                self.assertIn("watch_lab.py digest", appels)
                self.assertIn("pmzilla_lab_library.py index", appels)
                self.assertEqual(resultat.returncode, 1)
                self.assertIn("en échec : pré-tri ===", resultat.stdout)
                self.assertEqual(len(self.notifications), 1)
                self.assertIn("pré-tri", self.notifications[0])

    def test_echec_du_dashboard_ne_fait_pas_echouer_la_veille(self):
        resultat, appels = self.lancer(echec="dashboard.py")
        self.assertIn("Tableau de bord non généré", resultat.stdout)
        self.assertEqual(resultat.returncode, 0)   # choix documenté dans le script : jamais bloquant
        self.assertEqual(self.notifications, [])

    def test_echec_de_l_indexation_est_dit_et_notifie(self):
        resultat, appels = self.lancer(echec="pmzilla_lab_library.py index")
        self.assertIn("pmzilla_lab_library.py index", appels)
        self.assertIn("Indexation en erreur : la bibliothèque n'est pas à jour", resultat.stdout)
        self.assertIn("en échec : indexation ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("indexation", self.notifications[0])

    def test_plusieurs_echecs_nommes_dans_l_ordre(self):
        resultat, _ = self.lancer(echec="watch_lab.py collect,watch_triage.py score,pmzilla_lab_library.py index")
        self.assertIn("=== Veille terminée avec 3 étape(s) en échec : collecte, pré-tri, indexation ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)
        self.assertEqual(len(self.notifications), 1)   # une seule notification pour le passage
        self.assertIn("collecte, pré-tri, indexation", self.notifications[0])

    def test_liste_a_lire_en_erreur(self):
        resultat, _ = self.lancer(echec="watch_lab.py digest", curl=7)
        self.assertIn("Liste à lire en erreur", resultat.stdout)
        self.assertIn("en échec : liste à lire ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)
        resultat, _ = self.lancer(echec="watch_triage.py digest,watch_lab.py digest")
        self.assertIn("en échec : pré-tri, liste à lire ===", resultat.stdout)

    def test_notification_impossible_ne_change_pas_le_code_de_sortie(self):
        resultat, _ = self.lancer(echec="pmzilla_lab_library.py index", osascript=1)
        self.assertIn("Notification macOS impossible", resultat.stdout)
        self.assertEqual(resultat.returncode, 1)

    def test_aucune_commande_reelle_et_rien_hors_du_faux_home(self):
        resultat, _ = self.lancer()
        chemins = re.findall(r"(/\S*PMZilla-Lab\S*)", resultat.stdout + self.complets.read_text())
        self.assertTrue(chemins)
        self.assertTrue(all(c.startswith(str(self.home)) for c in chemins))
        self.assertTrue(all(not l.startswith("launchctl") for l in self.appels.read_text().splitlines()))
        self.assertEqual(self.notifications, [])   # la vraie notification n'est jamais déclenchée par les tests


class CacheUv(Base):
    """Contrôle du cache de uv (R-13) : seulement quand uv ou son Python a changé, jamais bloquant."""
    def appels_reveil(self, appels):
        return [a for a in appels if a.startswith("controle_cache.py")]

    def test_versions_inchangees_aucun_controle(self):
        resultat, appels = self.lancer()
        self.assertEqual(self.appels_reveil(appels), [])
        self.assertNotIn("cache", resultat.stdout.lower())

    def test_uv_change_relance_le_reveil_avec_reseau_puis_hors_ligne_et_enregistre(self):
        resultat, appels = self.lancer(FAUX_UV_VERSION="0.14.0")
        self.assertEqual(self.appels_reveil(appels), ["controle_cache.py", "controle_cache.py hors-ligne"])
        self.assertIn("Cache de uv rempli et vérifié hors ligne", resultat.stdout)
        self.assertEqual((self.home / ".pmzilla-lab" / "uv-version").read_text().strip(), "uv 0.14.0")
        self.assertEqual(self.notifications, [])
        self.assertEqual(resultat.returncode, 0)

    def test_python_change_relance_le_reveil(self):
        resultat, appels = self.lancer(FAUX_PYTHON_VERSION="3.15.0")
        self.assertEqual(self.appels_reveil(appels), ["controle_cache.py", "controle_cache.py hors-ligne"])
        self.assertEqual((self.home / ".pmzilla-lab" / "uv-python-version").read_text().strip(), "3.15.0")

    def test_versions_jamais_enregistrees_declenchent_le_controle(self):
        (self.home / ".pmzilla-lab" / "uv-version").unlink()
        _, appels = self.lancer()
        self.assertEqual(self.appels_reveil(appels), ["controle_cache.py", "controle_cache.py hors-ligne"])

    def test_deuxieme_passage_ne_controle_plus(self):
        self.lancer(FAUX_UV_VERSION="0.14.0")
        self.appels.unlink()
        _, appels = self.lancer(FAUX_UV_VERSION="0.14.0")
        self.assertEqual(self.appels_reveil(appels), [])

    def test_le_controle_du_cache_precede_la_collecte(self):
        _, appels = self.lancer(FAUX_UV_VERSION="0.14.0")
        self.assertEqual(appels[:3], ["controle_cache.py", "controle_cache.py hors-ligne", "watch_lab.py collect"])

    def test_versions_inchangees_la_collecte_est_le_premier_appel(self):
        _, appels = self.lancer()
        self.assertEqual(appels[0], "watch_lab.py collect")

    def test_le_reveil_se_lance_depuis_deux_dossiers_temporaires_distincts_nettoyes(self):
        resultat, _ = self.lancer(FAUX_UV_VERSION="0.14.0")
        lignes = [l for l in self.complets.read_text().splitlines() if "controle_cache.py" in l]
        self.assertEqual(len(lignes), 2)
        self.assertTrue(all(l.startswith("run --python 3.14.8 controle_cache.py") for l in lignes))   # chemin relatif : lancé depuis le dossier copie

    def test_les_deux_lancements_fixent_le_python_lu_dans_le_workspace(self):
        self.lancer(FAUX_UV_VERSION="0.14.0", FAUX_PYTHON_VERSION="3.15.0")
        lignes = [l for l in self.complets.read_text().splitlines() if "controle_cache.py" in l]
        self.assertEqual(len(lignes), 2)
        self.assertTrue(all(l.startswith("run --python 3.15.0 controle_cache.py") for l in lignes))

    def test_echec_hors_ligne_notifie_n_enregistre_pas_et_ne_bloque_pas(self):
        resultat, appels = self.lancer(echec="controle_cache.py hors-ligne", FAUX_UV_VERSION="0.14.0")
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("After an update of uv", self.notifications[0])
        self.assertIn("After an update of uv", resultat.stdout)
        self.assertEqual((self.home / ".pmzilla-lab" / "uv-version").read_text().strip(), "uv 0.13.0")
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("watch_lab.py collect", appels)
        self.assertIn("dashboard.py", appels)

    def test_echec_avec_reseau_n_essaie_pas_le_hors_ligne(self):
        resultat, appels = self.lancer(echec="controle_cache.py", FAUX_UV_VERSION="0.14.0")
        self.assertEqual(self.appels_reveil(appels), ["controle_cache.py"])   # l'appel échoué est noté, pas de hors-ligne ensuite
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(resultat.returncode, 0)

    def test_script_de_reveil_absent_notifie_sans_bloquer(self):
        (self.home / "PMZilla-Lab" / "workspace" / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts" / "wake.py").unlink()
        resultat, appels = self.lancer(FAUX_UV_VERSION="0.14.0")
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("watch_lab.py collect", appels)

    def test_version_illisible_journalise_sans_notifier_ni_bloquer(self):
        resultat, appels = self.lancer(FAUX_PYTHON_ABSENT="1")
        self.assertIn("Contrôle du cache de uv impossible", resultat.stdout)
        self.assertEqual(self.notifications, [])
        self.assertEqual(self.appels_reveil(appels), [])
        self.assertEqual(resultat.returncode, 0)

    def test_notification_impossible_ne_change_pas_le_code_de_sortie_du_controle(self):
        resultat, _ = self.lancer(echec="controle_cache.py hors-ligne", osascript=1, FAUX_UV_VERSION="0.14.0")
        self.assertEqual(resultat.returncode, 0)

    @staticmethod
    def entete(texte: str) -> list[str]:
        lignes = texte.splitlines()
        debut = lignes.index("# /// script")
        return lignes[debut:lignes.index("# ///", debut + 1) + 1]

    def test_script_jetable_porte_l_entete_du_vrai_wake_py_et_rien_d_autre_que_l_import(self):
        vrai = SCRIPT.parents[1] / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts" / "wake.py"
        (self.home / "PMZilla-Lab" / "workspace" / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts" / "wake.py"
         ).write_text(vrai.read_text())
        self.lancer(FAUX_UV_VERSION="0.14.0")
        for nom in ("jetable-.py", "jetable-hors-ligne.py"):
            jetable = (self.home / nom).read_text()
            entete = self.entete(jetable)
            self.assertEqual(entete, self.entete(vrai.read_text()))
            reste = [l for l in jetable.splitlines()[len(entete):] if l.strip()]
            self.assertEqual(reste, ["import yaml"])

    def test_wake_py_absent_ou_sans_entete_est_un_echec_notifie(self):
        (self.home / "PMZilla-Lab" / "workspace" / ".claude" / "skills" / "pmzilla-discovery-bmad" / "scripts" / "wake.py"
         ).write_text("print('pas d en-tete')\n")
        resultat, appels = self.lancer(FAUX_UV_VERSION="0.14.0")
        self.assertEqual(self.appels_reveil(appels), [])
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(resultat.returncode, 0)

    def test_python_version_a_la_racine_du_projet(self):
        racine = SCRIPT.parents[1]
        self.assertEqual((racine / ".python-version").read_text().strip(), "3.14")


class Plist(unittest.TestCase):
    """Le fichier de tools/ est un modèle : aucun chemin réel, __HOME__ à remplacer à l'installation."""

    def setUp(self):
        self.texte = (SCRIPT.parent / "com.pmzilla.watch.plist").read_text(encoding="utf-8")

    def test_etiquette_et_chemins_du_modele(self):
        self.assertIn("<string>com.pmzilla.watch</string>", self.texte)
        self.assertIn("<string>__HOME__/PMZilla-Lab/watch.sh</string>", self.texte)
        self.assertEqual(self.texte.count("<string>__HOME__/Library/Logs/pmzilla-watch.log</string>"), 2)

    def test_aucun_chemin_reel(self):
        self.assertNotIn("/Users/", self.texte)
        self.assertNotIn("veille", self.texte.lower())

    def test_le_rendu_par_sed_donne_un_plist_valide(self):
        rendu = subprocess.run(["sed", "s|__HOME__|/home/essai|g"], input=self.texte, text=True, capture_output=True).stdout
        self.assertNotIn("__HOME__", rendu)
        import plistlib
        donnees = plistlib.loads(rendu.encode())
        self.assertEqual(donnees["ProgramArguments"][1], "/home/essai/PMZilla-Lab/watch.sh")

    def test_le_chemin_du_plist_est_le_dossier_des_outils_de_watch_sh(self):
        """Le modèle lance __HOME__/PMZilla-Lab/watch.sh ; watch.sh en déduit ses dossiers (TOOLS, WORKSPACE) : les deux
        doivent désigner la même racine, sinon le script lancé ne retrouve pas ses outils."""
        import re
        import plistlib
        script = SCRIPT.read_text(encoding="utf-8")
        outils = re.search(r'^TOOLS="([^"]+)"', script, re.M).group(1)
        espace = re.search(r'^WORKSPACE="([^"]+)"', script, re.M).group(1)
        self.assertEqual(espace, "$TOOLS/workspace")
        rendu = self.texte.replace("__HOME__", "/home/essai")
        programme = plistlib.loads(rendu.encode())["ProgramArguments"][1]
        self.assertEqual(str(Path(programme).parent), outils.replace("$HOME", "/home/essai"))
        self.assertEqual(Path(programme).name, "watch.sh")


if __name__ == "__main__":
    unittest.main()
