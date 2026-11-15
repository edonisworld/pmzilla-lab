"""Fermeture des imports des gardes et des crochets (change session-guard-n1, design D7 « Closure test », tâche 4.2).

Le fragment 41 protège en écriture les gardes, les crochets et chaque module qu'ils importent. Ce test recalcule la fermeture : il part des commandes de la
section `hooks` de .claude/settings.base.json (les gardes PreToolUse) et des crochets de `tools/hooks/` ; il suit les imports Python, les `source` et `.` du shell
et les scripts lancés par leur chemin, jusqu'à ce qu'aucun fichier nouveau n'apparaisse. Il ÉCHOUE, en nommant le fichier, quand un fichier atteint n'est pas protégé
par la liste du fragment 41 (tools/garde_session.py : FICHIERS_PROTEGES et DOSSIERS_PROTEGES).

Lecture stricte, différente de la fermeture large de tools/finish_checks.py (qui suit aussi tout nom de fichier cité dans un texte) : en Python, les `import` et
`from … import` (l'arbre syntaxique, fonctions comprises) et les chaînes qui sont à elles seules un nom ou un chemin de script `.py` ou `.sh` ; en shell, les noms de script
des lignes qui ne sont pas des commentaires. Un nom cité dans une phrase n'est pas une référence.

Un fichier atteint hors de la liste ARRÊTE la tâche et revient à l'auteur avant que la liste grandisse (tâche 4.2) : ce test ne l'ajoute jamais lui-même.

Exemptions déclarées, chacune avec sa raison (Q12 de la décision de l'auteur, R-20261107-26) : les crochets SessionStart, `tests/run_all.sh` et `tools/evals_auto.sh`
restent hors de la liste protégée. Une exemption coupe l'arête (source, cible) seulement.

    bash tests/run_all.sh settings_deny
"""
import ast
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import garde_session  # noqa: E402

REGLAGES_BASE = RACINE / ".claude" / "settings.base.json"

# (source, cible) -> raison. Une arête exemptée n'est pas suivie.
EXEMPTIONS = {
    ("tools/hooks/post-commit", "tools/evals_auto.sh"): "Q12 : tools/evals_auto.sh reste hors de la liste protégée (évaluations des postures, payantes, lancées par l'auteur)",
}
# Événements de la section hooks dont les commandes restent hors de la liste protégée (Q12) : SessionStart n'exécute ni garde ni crochet.
EVENEMENTS_HORS_LISTE = {"SessionStart": "Q12 : les crochets SessionStart restent hors de la liste protégée"}

NOM_DE_SCRIPT = re.compile(r"^(?:[\w$.{}~/-]*/)?([\w-]+\.(?:py|sh))$")
NOM_DANS_UNE_LIGNE = re.compile(r"(?<![\w.-])(?:[\w$.{}~\"'/-]*/)?([\w-]+\.(?:py|sh))(?![\w.-])")


def suivis() -> list:
    # Fichiers suivis et fichiers neufs non ignorés : la branche n'est pas encore commitée quand ses premiers tests tournent. Le pathspec « tools »
    # suffit (la fermeture ne vise que des fichiers de tools/) ; sans pathspec, le balayage de tests/select_suites/test_openspec_readers.py prend
    # l'appel pour une lecture de openspec/ (revue Opus, constat 13) et la suite settings_deny devait être exemptée. Remplace : l'exemption de la liste.
    # Retrait : permanent tant que la fermeture ne lit que tools/.
    fait = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "tools"], cwd=RACINE, capture_output=True)
    if fait.returncode != 0:
        raise unittest.SkipTest("hors dépôt Git")
    return [p for p in fait.stdout.decode("utf-8", errors="replace").split("\0") if p]


def lire(chemin: str):
    try:
        return (RACINE / chemin).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def commandes_de_la_section_hooks() -> list:
    """Les commandes de la section `hooks` de settings.base.json, hors événements exemptés."""
    reglages = json.loads(REGLAGES_BASE.read_text(encoding="utf-8"))
    commandes = []
    for evenement, entrees in reglages.get("hooks", {}).items():
        if evenement in EVENEMENTS_HORS_LISTE:
            continue
        for entree in entrees:
            commandes += [h["command"] for h in entree.get("hooks", []) if h.get("type") == "command"]
    return commandes


LANCEMENTS = {"run", "Popen", "call", "check_call", "check_output", "system", "popen", "execv", "execvp", "execl", "execlp", "spawnv"}


def _lance_un_processus(appel) -> bool:
    f = appel.func
    return (isinstance(f, ast.Attribute) and f.attr in LANCEMENTS) or (isinstance(f, ast.Name) and f.id in LANCEMENTS)


def noms_cites(chemin: str, texte: str) -> set:
    """Les noms de fichier de tools/ que le fichier importe, source ou lance (lecture stricte, voir l'en-tête)."""
    noms = set()
    premiere = texte.splitlines()[0] if texte else ""
    if chemin.endswith(".py") or "python" in premiere:
        arbre = ast.parse(texte)
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                noms |= {f"{a.name.split('.')[0]}.py" for a in noeud.names}
            elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0 and noeud.module:
                noms.add(f"{noeud.module.split('.')[0]}.py")
            elif isinstance(noeud, ast.Call) and _lance_un_processus(noeud):
                for sous in ast.walk(noeud):   # les chaînes des arguments d'un lancement de processus
                    if isinstance(sous, ast.Constant) and isinstance(sous.value, str) and len(sous.value) < 200:
                        m = NOM_DE_SCRIPT.match(sous.value)
                        if m:
                            noms.add(m.group(1))
    else:
        for ligne in texte.splitlines():
            if not ligne.lstrip().startswith("#"):
                noms |= set(NOM_DANS_UNE_LIGNE.findall(ligne))
    return noms


def fermeture() -> dict:
    """{fichier de tools/ atteint : origine} depuis les gardes de la section hooks et les crochets de tools/hooks/."""
    liste = suivis()
    ensemble = set(liste)
    racines = [p for p in liste if p.startswith("tools/hooks/")]
    for commande in commandes_de_la_section_hooks():
        racines += [f"tools/{n}" for n in re.findall(r"tools/([\w-]+\.(?:py|sh))", commande) if f"tools/{n}" in ensemble]
    racines.append("tools/garde_session.py")   # racine même avant que le fichier d'étape P2 l'inscrive dans la section hooks
    atteints, a_voir = {r: "racine" for r in racines}, list(racines)
    while a_voir:
        source = a_voir.pop()
        texte = lire(source)
        if texte is None:
            continue
        for nom in sorted(noms_cites(source, texte)):
            cible = f"tools/{nom}"
            if cible not in ensemble or cible == source or (source, cible) in EXEMPTIONS or cible in atteints:
                continue
            atteints[cible] = f"cité par {source}"
            a_voir.append(cible)
    return atteints


def fichiers_non_proteges(atteints) -> list:
    """Les fichiers atteints que la liste du fragment 41 ne couvre pas."""
    return sorted(c for c in atteints if not garde_session.relatif_protege(c))


class FermetureDesGardes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atteints = fermeture()

    def test_les_racines_sont_les_gardes_et_les_crochets(self):
        for attendu in ("tools/hooks/pre-commit", "tools/hooks/commit-msg", "tools/pipe_guard.py", "tools/npm_guard.py", "tools/garde_session.py"):
            self.assertIn(attendu, self.atteints)
        self.assertNotIn("tools/journal_lab.py", self.atteints)   # SessionStart : hors liste (Q12)
        self.assertNotIn("tools/roadmap.py", self.atteints)

    def test_la_fermeture_atteint_les_modules_connus(self):
        for attendu in ("tools/npm_ci_conditions.py", "tools/lab_paths.py", "tools/finish_lock.py", "tools/secret_scan.py", "tools/commit_names_scan.py",
                        "tools/sensitive_names.py", "tools/identifiants_personnels.py", "tools/preuve_arbre.py"):
            self.assertIn(attendu, self.atteints, attendu)

    def test_chaque_fichier_atteint_est_protege_par_le_fragment_41(self):
        non_proteges = fichiers_non_proteges(self.atteints)
        self.assertEqual(non_proteges, [], "fichier(s) atteint(s) par les gardes ou les crochets, hors de la liste du fragment 41 : "
                         + ", ".join(f"{c} ({self.atteints[c]})" for c in non_proteges)
                         + " (tâche 4.2 : s'arrêter et revenir à l'auteur avant d'allonger la liste)")

    def test_chaque_exemption_a_une_raison_et_une_arete_reelle(self):
        liste = suivis()
        for (source, cible), raison in EXEMPTIONS.items():
            self.assertTrue(raison.strip())
            self.assertIn(source, liste)
            self.assertIn(cible, liste)
            self.assertIn(cible.rsplit("/", 1)[-1], noms_cites(source, lire(source)), "exemption sans arête réelle : la retirer")
        for evenement, raison in EVENEMENTS_HORS_LISTE.items():
            self.assertTrue(raison.strip())
            self.assertIn(evenement, json.loads(REGLAGES_BASE.read_text(encoding="utf-8"))["hooks"])

    def test_la_liste_de_la_garde_ne_contient_que_des_fichiers_existants(self):
        liste = set(suivis())
        for fichier in garde_session.FICHIERS_PROTEGES:
            self.assertIn(fichier, liste, fichier)
        self.assertIn("tools/hooks/commit-msg", liste)

    def test_la_lecture_stricte_ne_suit_pas_une_phrase(self):
        self.assertEqual(noms_cites("tools/x.py", 'import json\nimport lab_paths\nTEXTE = "voir tools/finish_train.sh pour la fin"\n'), {"json.py", "lab_paths.py"})
        self.assertEqual(noms_cites("tools/x.py", 'import subprocess\ndef f():\n    import secret_scan\n    NOMS = ["liste.py", "autre_liste.sh"]\n'
                                    '    subprocess.run(["python3", "identifiants_personnels.py", "dir/autre.sh"])\n'),
                         {"subprocess.py", "secret_scan.py", "identifiants_personnels.py", "autre.sh"})
        self.assertEqual(noms_cites("tools/hooks/h", '#!/bin/sh\n# voir finish_train.sh\npython3 "$OUTILS/commit_names_scan.py" "$@"\n. "$DIR/lab_paths.sh"\n'),
                         {"commit_names_scan.py", "lab_paths.sh"})


if __name__ == "__main__":
    unittest.main()
