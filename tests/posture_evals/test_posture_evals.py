"""
Tests de la logique locale du jeu d'essai (tools/posture_evals.py) : lecture des cas, lecture de la trace,
vérifications automatiques, calcul du score, rapport, mémoire figée, rejugement.

    uv run --with pyyaml python -m unittest discover -s tests/posture_evals -v

Aucun appel payant : `subprocess.run` est remplacé dans le module par un faux (qui enregistre les commandes et
répond ce que le test décide) ; `claude` n'est jamais lancé, aucun modèle appelé, aucun worktree créé. Traces,
rapports et mémoire sont dans un dossier temporaire. Seul le fichier réel tests/postures/cas.yaml est lu, pour
vérifier qu'il ne contient que des règles que le script sait appliquer.
"""
import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import posture_evals as essai  # noqa: E402

RACINE_DEPOT = Path(__file__).resolve().parents[2]
CAS_REEL = Path(__file__).resolve().parents[2] / "tests" / "postures" / "cas.yaml"


# -- événements de la trace stream-json -------------------------------------------------------------------

def assistant(*blocs, parent=None) -> dict:
    return {"type": "assistant", "parent_tool_use_id": parent, "message": {"content": list(blocs)}}


def texte(t: str) -> dict:
    return {"type": "text", "text": t}


def appel(nom: str, entree: dict, ident: str) -> dict:
    return {"type": "tool_use", "name": nom, "input": entree, "id": ident}


def resultat_outil(ident: str, contenu) -> dict:
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": ident, "content": contenu}]}}


def fin(resultat="", cout=0.12, tours=4, erreur=False, refus=None) -> dict:
    return {"type": "result", "result": resultat, "total_cost_usd": cout, "num_turns": tours, "is_error": erreur,
            "permission_denials": refus or []}


SEANCE = [
    assistant(texte("[Posture : Delivery]\nJe cherche d'abord."),
              appel("mcp__pmzilla-library__search_library", {"query": "flux", "collections": ["flow"]}, "t1"),
              appel("Agent", {"subagent_type": "pmzilla-critic", "prompt": "..."}, "t2")),
    resultat_outil("t1", [{"type": "text", "text": '{"section": "Limiter le WIP", "text": "Voir chapter 3 pour le détail."}'}]),
    assistant(texte("Texte d'un sous-agent, hors fil principal."), parent="t2"),
    resultat_outil("t2", "ok"),
    fin("Réponse finale avec Auteur, Titre."),
]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.commandes: list[list[str]] = []
        self.reponses: list = []   # file de CompletedProcess ou d'exceptions renvoyés par le faux subprocess.run

        def faux_run(commande, **options):
            self.commandes.append(list(commande))
            reponse = self.reponses.pop(0) if self.reponses else subprocess.CompletedProcess(commande, 0, "", "")
            if isinstance(reponse, Exception):
                raise reponse
            return reponse

        for patch in (
            mock.patch.object(essai.subprocess, "run", faux_run),
            mock.patch.object(essai, "CLAUDE", "faux-claude"),
            mock.patch.object(essai, "DATA", self.tmp / "essais"),
            mock.patch.object(essai, "REPORT_DIR", self.tmp / "rapports"),
            mock.patch.object(essai, "WORKSPACE", self.tmp / "workspace"),
            mock.patch.object(essai, "CASES_FILE", self.tmp / "cas.yaml"),
            mock.patch.object(essai, "create_cases_database", lambda: None),     # jamais de base réelle (db-lot2, groupe 12)
            mock.patch.object(essai, "evaluated_paths", lambda: ["CLAUDE.md"]),    # liste partagée et empreinte : testées dans test_branche.py
            mock.patch.object(essai, "evaluated_fingerprint", lambda commit, paths: "v1:" + "0" * 64),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def termine(self, sortie: str, code=0, erreur=""):
        return subprocess.CompletedProcess([], code, sortie, erreur)


class Trace(Base):
    def test_lecture_de_la_trace(self):
        trace = essai.read_trace(SEANCE)
        self.assertEqual([c["name"] for c in trace["calls"]], ["mcp__pmzilla-library__search_library", "Agent"])
        self.assertEqual(trace["sections"], ["Limiter le WIP"])
        self.assertIn("chapter 3", trace["mentions"][0])
        self.assertEqual((trace["cost"], trace["turns"], trace["error"]), (0.12, 4, False))
        self.assertEqual(trace["answer"], "Réponse finale avec Auteur, Titre.")
        self.assertIn("[Posture : Delivery]", trace["all_text"])
        self.assertNotIn("sous-agent", trace["all_text"])   # le texte d'un sous-agent n'est pas dans le fil principal
        self.assertIn("Limiter le WIP", trace["calls"][0]["result"])

    def test_trace_vide_ou_sans_resultat_est_une_erreur(self):
        trace = essai.read_trace([])
        self.assertTrue(trace["error"])
        self.assertEqual((trace["answer"], trace["calls"]), ("", []))
        trace = essai.read_trace([assistant(texte("Réponse sans événement final."))])
        self.assertEqual(trace["answer"], "Réponse sans événement final.")   # repli sur le texte du fil principal
        self.assertTrue(trace["error"])

    def test_refus_d_outils(self):
        trace = essai.read_trace([fin("x", refus=[{"tool_name": "Bash", "tool_input": {"command": "rm -rf /" + "x" * 200}},
                                                  {"tool_name": "WebFetch"}])])
        self.assertEqual(len(trace["denied"]), 2)
        self.assertTrue(trace["denied"][0].startswith("Bash (rm -rf /"))
        self.assertLessEqual(len(trace["denied"][0]), 160)
        self.assertEqual(trace["denied"][1], "WebFetch")

    def test_critic_et_outils(self):
        trace = essai.read_trace(SEANCE)
        self.assertTrue(any(essai.is_critic(c) for c in trace["calls"]))
        self.assertEqual(len(essai.tool_calls(trace, "search_library")), 1)
        self.assertEqual(essai.tool_calls(trace, "Read"), [])
        self.assertFalse(essai.is_critic({"name": "Agent", "input": {"subagent_type": "Explore"}}))
        self.assertFalse(essai.is_critic({"name": "Skill", "input": {"skill": "pmzilla-critic"}}))

    def test_trace_sauvegardee_relue_sans_stderr_ni_lignes_cassees(self):
        dossier = self.tmp / "passage"
        dossier.mkdir()
        brut = "\n".join([json.dumps(e) for e in SEANCE[:2]] + ["ligne qui n'est pas du JSON", "{cassé"] +
                         [json.dumps(e) for e in SEANCE[2:]])
        (dossier / "cas1.jsonl").write_text(brut + "\n# stderr\n" + json.dumps({"type": "result", "result": "NON"}),
                                            encoding="utf-8")
        (dossier / "cas1.fichiers.json").write_text(json.dumps({"a.md": "contenu"}), encoding="utf-8")
        evenements, fichiers = essai.saved_session(dossier, "cas1")
        self.assertEqual(len(evenements), len(SEANCE))
        self.assertEqual(fichiers, {"a.md": "contenu"})
        self.assertEqual(essai.read_trace(evenements)["answer"], "Réponse finale avec Auteur, Titre.")
        self.assertEqual(essai.saved_session(dossier, "absent"), (None, {}))

    def test_outils_resume_d_un_passage(self):
        dossier = essai.DATA / "2026-10-01-100000"
        dossier.mkdir(parents=True)
        (dossier / "cas1.jsonl").write_text("\n".join(json.dumps(e) for e in SEANCE), encoding="utf-8")
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            essai.show_tools(dossier)
        self.assertIn("## cas1", sortie.getvalue())
        self.assertIn("search_library : flux · ['flow']", sortie.getvalue())
        self.assertIn("Agent : pmzilla-critic", sortie.getvalue())
        with self.assertRaises(SystemExit):
            essai.show_tools(self.tmp / "absent")


class Verifications(Base):
    def setUp(self):
        super().setUp()
        self.trace = essai.read_trace(SEANCE)

    def test_posture(self):
        self.assertIsNone(essai.check_posture(None, self.trace))
        self.assertTrue(essai.check_posture("delivery", self.trace)["ok"])   # insensible à la casse
        faux = essai.check_posture("Discovery", self.trace)
        self.assertFalse(faux["ok"])
        self.assertIn("balise : Delivery", faux["justification"])
        self.assertFalse(essai.check_posture("aucune", self.trace)["ok"])
        sans = essai.read_trace([assistant(texte("Une question de clarification ?")), fin("Une question ?")])
        self.assertTrue(essai.check_posture("aucune", sans)["ok"])
        self.assertIn("absente", essai.check_posture("Scaling", sans)["justification"])

    def test_tag_de_posture_avec_espaces(self):
        self.assertEqual(essai.POSTURE_TAG.findall("[ Posture :  Facilitation ] et [posture:Critic]"),
                         ["Facilitation", "Critic"])

    def test_outil_et_collections(self):
        self.assertTrue(essai.check_auto({"tool": "search_library"}, self.trace, {})["ok"])
        self.assertFalse(essai.check_auto({"tool": "read_passage"}, self.trace, {})["ok"])
        verdict = essai.check_auto({"tool": "search_library", "collections": ["flow", "tech"]}, self.trace, {})
        self.assertTrue(verdict["ok"])
        self.assertIn("collections : flow", verdict["justification"])
        self.assertFalse(essai.check_auto({"tool": "search_library", "collections": ["veille"]}, self.trace, {})["ok"])

    def test_critic(self):
        self.assertTrue(essai.check_auto({"critic": True}, self.trace, {})["ok"])
        self.assertFalse(essai.check_auto({"critic": False}, self.trace, {})["ok"])
        sans = essai.read_trace([fin("x")])
        self.assertTrue(essai.check_auto({"critic": False}, sans, {})["ok"])
        self.assertFalse(essai.check_auto({"critic": True}, sans, {})["ok"])

    def test_texte_et_sans_texte(self):
        self.assertTrue(essai.check_auto({"text": "auteur, titre"}, self.trace, {})["ok"])    # sans casse
        self.assertFalse(essai.check_auto({"text": "absent du tout"}, self.trace, {})["ok"])
        self.assertTrue(essai.check_auto({"without_text": "emoji"}, self.trace, {})["ok"])
        self.assertFalse(essai.check_auto({"without_text": "cherche"}, self.trace, {})["ok"])

    def test_memoire_sans(self):
        ok = essai.check_auto({"memory_without": "Paul"}, self.trace, {"a.md": "un rôle", "b.md": "autre"})
        self.assertTrue(ok["ok"])
        self.assertIn("2 fichier(s) écrit(s)", ok["justification"])
        ko = essai.check_auto({"memory_without": "Paul"}, self.trace, {"a.md": "avec Paul ici", "b.md": "x"})
        self.assertFalse(ko["ok"])
        self.assertIn("a.md", ko["justification"])
        self.assertTrue(essai.check_auto({"memory_without": "Paul"}, self.trace, {})["ok"])

    def test_regle_inconnue(self):
        with self.assertRaises(SystemExit):
            essai.check_auto({"inconnue": 1}, self.trace, {})

    def test_cas_reel_ne_contient_que_des_regles_connues(self):
        """cas.yaml (réel, sans donnée sensible) : ids uniques, postures valides, règles applicables."""
        cas = yaml.safe_load(CAS_REEL.read_text(encoding="utf-8"))
        self.assertTrue(cas)
        self.assertEqual(len({c["id"] for c in cas}), len(cas))
        trace = essai.read_trace(SEANCE)
        for c in cas:
            self.assertTrue(c["question"].strip(), c["id"])
            self.assertIn(c.get("posture"), {None, "Discovery", "Delivery", "Scaling", "Facilitation", "Critic", "aucune"},
                          c["id"])
            for regle in c.get("verifications") or []:
                essai.check_auto(regle, trace, {})   # lève SystemExit sur une règle que le script ne sait pas lire
            for critere in c.get("judgements") or []:
                self.assertIsInstance(critere if isinstance(critere, str) else critere["text"], str)


class Juge(Base):
    CAS = {"id": "c1", "question": "Question ?", "judgements": ["Critère un", "Critère deux", "Critère trois"]}

    def juger(self, sortie_claude: str, **options):
        self.reponses.append(self.termine(sortie_claude))
        return essai.judge(self.CAS, essai.read_trace(SEANCE), None, self.tmp, **options) if options else \
            essai.judge(self.CAS, essai.read_trace(SEANCE), None, self.tmp)

    def enveloppe(self, jugements) -> str:
        return json.dumps({"result": "Voici mon jugement :\n" + json.dumps({"jugements": jugements})})

    def test_verdicts_lus_et_commande_du_juge(self):
        verdicts = self.juger(self.enveloppe([{"critere": "x", "justification": "Cité.", "ok": True},
                                              {"critere": "y", "justification": "Absent.", "ok": False},
                                              {"critere": "z", "justification": "Oui.", "ok": True}]))
        self.assertEqual([(v["critere"], v["ok"]) for v in verdicts],
                         [("Critère un", True), ("Critère deux", False), ("Critère trois", True)])
        self.assertEqual(verdicts[0]["justification"], "Cité.")
        self.assertEqual(self.commandes[0][:2], ["faux-claude", "-p"])
        self.assertIn("Critère deux", self.commandes[0][2])
        self.assertIn("--output-format", self.commandes[0])
        self.assertTrue((self.tmp / "juge").is_dir())   # dossier neutre : pas de CLAUDE.md de PMZilla

    def test_juge_strict_sur_le_booleen(self):
        verdicts = self.juger(self.enveloppe([{"justification": "a", "ok": "true"}, {"justification": "b", "ok": 1},
                                              {"justification": "c"}]))
        self.assertEqual([v["ok"] for v in verdicts], [False, False, False])

    def test_verdicts_manquants_ou_illisibles(self):
        verdicts = self.juger(self.enveloppe([{"justification": "Seul.", "ok": True}]))
        self.assertEqual([v["ok"] for v in verdicts], [True, False, False])
        self.assertEqual(verdicts[2]["justification"], "pas de jugement exploitable")
        for sortie in ("pas de JSON du tout", "{ceci n'est pas du json}", json.dumps({"result": "rien"}),
                       json.dumps({"result": json.dumps({"autre": 1})})):
            self.assertEqual([v["ok"] for v in self.juger(sortie)], [False, False, False], sortie)

    def test_delai_depasse(self):
        self.reponses.append(subprocess.TimeoutExpired("claude", 300))
        verdicts = essai.judge(self.CAS, essai.read_trace(SEANCE), None, self.tmp)
        self.assertEqual([v["ok"] for v in verdicts], [False, False, False])

    def test_sans_critere_aucun_appel(self):
        self.assertEqual(essai.judge({"id": "c", "question": "q"}, essai.read_trace(SEANCE), None, self.tmp), [])
        self.assertEqual(self.commandes, [])

    def test_modele_du_juge_transmis(self):
        self.reponses.append(self.termine(self.enveloppe([])))
        essai.judge(self.CAS, essai.read_trace(SEANCE), "modele-x", self.tmp)
        self.assertEqual(self.commandes[0][-2:], ["--model", "modele-x"])


class Seance(Base):
    def test_commande_de_la_seance_et_evenements(self):
        brut = "\n".join(json.dumps(e) for e in SEANCE) + "\nbruit\n{cassé"
        self.reponses.append(self.termine(brut, erreur="avertissement"))
        trace = self.tmp / "t.jsonl"
        evenements = essai.run_session("Une question ?", self.tmp / "copie", self.tmp / "mcp.json", "modele-x", trace, False)
        self.assertEqual(len(evenements), len(SEANCE))
        commande = self.commandes[0]
        self.assertEqual(commande[:3], ["faux-claude", "-p", "Une question ?"])
        for option in ("--strict-mcp-config", "--allowedTools", "--append-system-prompt"):
            self.assertIn(option, commande)
        self.assertEqual(commande[commande.index("--permission-mode") + 1], "acceptEdits")
        self.assertEqual(commande[-2:], ["--model", "modele-x"])
        self.assertNotIn("Bash", commande)                  # aucun Bash libre par défaut
        self.assertIn("# stderr\navertissement", trace.read_text(encoding="utf-8"))

    def test_consigne_systeme_selon_la_langue(self):
        def consigne(**options):
            self.reponses.append(self.termine("{}"))
            essai.run_session("q", self.tmp / "copie", self.tmp / "mcp.json", None, self.tmp / "t.jsonl", False, **options)
            commande = self.commandes[-1]
            return commande[commande.index("--append-system-prompt") + 1]
        francais = consigne()
        self.assertEqual(francais, f"Le dossier de travail est {self.tmp / 'copie'}. Dans les commandes Bash, n'utilise "
                                   f"jamais $PWD ni $(pwd) : écris ce chemin en clair.")      # inchangée
        self.assertEqual(consigne(language="fr"), francais)
        anglais = consigne(language="en")
        self.assertIn("The working folder is", anglais)
        self.assertNotIn("dossier", anglais)

    def test_avec_bash_et_delai_depasse(self):
        self.reponses.append(subprocess.TimeoutExpired("claude", 900, output=b'{"type": "result", "result": "partiel"}'))
        trace = self.tmp / "t.jsonl"
        evenements = essai.run_session("q", self.tmp, self.tmp / "mcp.json", None, trace, True)
        self.assertIn("Bash", self.commandes[0])
        self.assertEqual(evenements[0]["result"], "partiel")      # ce qui était déjà écrit est gardé
        self.assertIn("délai dépassé (900 s)", trace.read_text(encoding="utf-8"))

    def test_configuration_mcp(self):
        config = json.loads(essai.mcp_config(self.tmp).read_text())
        serveur = config["mcpServers"]["pmzilla-library"]
        self.assertEqual(serveur["args"][0], "run")
        self.assertTrue(serveur["args"][-1] == "serve")


class MemoireFigee(Base):
    def test_vecu_remplace_par_la_version_neutre(self):
        copie = self.tmp / "copie"
        neutre = copie / "tests" / "postures" / "memoire" / "delivery"
        neutre.mkdir(parents=True)
        (neutre / "MEMORY.md").write_text("mémoire neutre", encoding="utf-8")
        cible = copie / "_bmad" / "memory" / "pmzilla-delivery-bmad"
        (cible / "sessions").mkdir(parents=True)
        (cible / "sessions" / "2026.md").write_text("vécu réel", encoding="utf-8")
        (cible / "MEMORY.md").write_text("mémoire réelle", encoding="utf-8")
        (cible / "BOND.md").write_text("lien réel", encoding="utf-8")   # pas de version neutre : retiré
        (cible / "CAPABILITIES.md").write_text("structure", encoding="utf-8")
        posees = essai.freeze_memory(copie)
        self.assertEqual((cible / "MEMORY.md").read_text(encoding="utf-8"), "mémoire neutre")
        self.assertFalse((cible / "BOND.md").exists())
        self.assertFalse((cible / "sessions").exists())
        self.assertTrue((cible / "CAPABILITIES.md").exists())              # la structure reste celle de l'état testé
        self.assertEqual(list(posees.values()), ["mémoire neutre"])

    def test_erreurs(self):
        with self.assertRaises(SystemExit):
            essai.freeze_memory(self.tmp)   # pas de mémoire figée dans l'état testé
        copie = self.tmp / "copie"
        (copie / "tests" / "postures" / "memoire" / "scaling").mkdir(parents=True)
        with self.assertRaises(SystemExit):
            essai.freeze_memory(copie)       # la posture n'existe pas dans _bmad/memory


def resultat(ident, verifications, **reste):
    return {"id": ident, "question": "Question ?", "verifications": verifications, "posture": "Delivery",
            "cost": 0.5, "turns": 3, "error": False, "refus": [], **reste}


class Rapport(Base):
    def test_score_regressions_et_corrections(self):
        avant = {("c1", "Posture Delivery"): True, ("c1", "Critic appelé"): False, ("c2", "Critère"): True}
        resultats = [resultat("c1", [{"critere": "Posture Delivery", "ok": False, "justification": "absente"},
                                     {"critere": "Critic appelé", "ok": True, "justification": "appelé"}]),
                     resultat("c2", [{"critere": "Critère", "ok": True, "justification": "ok"}], cost=None, turns=None,
                              error=True, refus=["Bash (ls)", "Bash (ls)"])]
        chemin = essai.write_report("2026-10-06-120000", resultats, avant, "abcdef1234567", "figée")
        texte = chemin.read_text(encoding="utf-8")
        self.assertEqual(chemin.name, "essai-2026-10-06-120000.md")
        self.assertIn("mémoire : figée", texte)
        self.assertIn("2/3 vérifications réussies sur 2 cas. État testé : abcdef1234.", texte)
        self.assertIn("## Régressions (réussies au passage précédent)\n\n- **c1** : Posture Delivery", texte)
        self.assertNotIn("- **c2**", texte)
        self.assertIn("| c1 | 1/2 | Delivery | 0.50 $ | 3 |", texte)
        self.assertIn("| c2 | 1/1 | Delivery | ? | ? |", texte)
        self.assertIn("❌ Posture Delivery (régression) : absente", texte)
        self.assertIn("✅ Critic appelé (corrigé) : appelé", texte)
        self.assertIn("La séance a échoué", texte)
        self.assertEqual(texte.count("- Bash (ls)"), 1)       # refus dédoublonnés

    def test_sans_regression_pas_de_section(self):
        chemin = essai.write_report("s", [resultat("c1", [{"critere": "X", "ok": True, "justification": "ok"}])], {}, "abc")
        self.assertNotIn("Régressions", chemin.read_text(encoding="utf-8"))
        self.assertIn("mémoire : réelle", chemin.read_text(encoding="utf-8"))   # valeur par défaut

    def test_resultats_precedents(self):
        self.assertEqual(essai.previous_results(self.tmp / "x"), {})
        for stamp, ok in (("2026-10-01-100000", False), ("2026-10-02-100000", True), ("2026-10-03-100000", False)):
            dossier = essai.DATA / stamp
            dossier.mkdir(parents=True)
            (dossier / "resultats.json").write_text(json.dumps(
                {"cas": [{"id": "c1", "verifications": [{"critere": "X", "ok": ok}]}]}), encoding="utf-8")
        # le plus récent, hors le passage en cours
        self.assertEqual(essai.previous_results(essai.DATA / "2026-10-03-100000"), {("c1", "X"): True})
        self.assertEqual(essai.previous_results(essai.DATA / "2026-10-09-000000"), {("c1", "X"): False})


class Principal(Base):
    """main() sur --rejudge : aucune séance, aucun git réel, aucun worktree ; seul le juge (faux) est appelé."""

    CAS = [{"id": "c1", "question": "Question un ?", "posture": "Delivery",
            "verifications": [{"tool": "search_library"}, {"critic": True}],
            "judgements": ["Critère un"]},
           {"id": "c2", "question": "Question deux ?", "posture": "aucune"}]

    def setUp(self):
        super().setUp()
        essai.CASES_FILE.write_text(yaml.safe_dump(self.CAS, allow_unicode=True), encoding="utf-8")
        self.passage = essai.DATA / "2026-10-01-090000"
        self.passage.mkdir(parents=True)
        (self.passage / "c1.jsonl").write_text("\n".join(json.dumps(e) for e in SEANCE), encoding="utf-8")
        (self.passage / "resultats.json").write_text(json.dumps(
            {"base": "basebase12", "memoire": "figée", "cas": [{"id": "c1", "verifications": [
                {"critere": "Posture Delivery", "ok": True}, {"critere": "Appel à search_library", "ok": True},
                {"critere": "Critère un", "ok": True}]}]}),
            encoding="utf-8")
        for patch in (mock.patch.object(essai, "git", lambda *a, **k: ""),):
            patch.start()
            self.addCleanup(patch.stop)

    def lancer(self, *arguments) -> str:
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["posture_evals.py", *arguments]), contextlib.redirect_stdout(sortie):
            essai.main()
        return sortie.getvalue()

    def test_rejuger_calcule_le_score_et_ecrit_le_rapport(self):
        self.reponses.append(self.termine(json.dumps({"result": json.dumps(
            {"jugements": [{"critere": "Critère un", "justification": "Oui.", "ok": True}]})})))
        sortie = self.lancer("--rejudge", "2026-10-01-090000")
        self.assertIn("pas de trace pour ce cas dans le passage indiqué, ignoré", sortie)   # c2 n'a pas de trace
        self.assertIn("BILAN 4/4 · 0 régression(s)", sortie)
        rapports = list(essai.REPORT_DIR.glob("essai-*.md"))
        self.assertEqual(len(rapports), 1)
        texte = rapports[0].read_text(encoding="utf-8")
        self.assertIn("mémoire : figée", texte)           # reprise du passage rejugé
        self.assertIn("État testé : basebase12", texte)
        self.assertEqual(len(self.commandes), 1)          # seulement le juge : aucune séance relancée
        self.assertNotIn("--permission-mode", self.commandes[0])
        nouveaux = [d for d in essai.DATA.iterdir() if d.name != "2026-10-01-090000"]
        self.assertEqual(len(nouveaux), 1)
        resultats = json.loads((nouveaux[0] / "resultats.json").read_text(encoding="utf-8"))
        self.assertEqual([c["id"] for c in resultats["cas"]], ["c1"])

    def test_regression_detectee_au_rejugement(self):
        self.reponses.append(self.termine(json.dumps({"result": "{}"})))   # le juge ne rend rien d'exploitable
        # le passage source disait « Critère un » réussi : le juge ne rend rien, c'est une régression
        sortie = self.lancer("--rejudge", "2026-10-01-090000", "--cases", "c1")
        self.assertIn("BILAN 3/4 · 1 régression(s)", sortie)
        rapport = next(essai.REPORT_DIR.glob("essai-*.md")).read_text(encoding="utf-8")
        self.assertIn("- **c1** : Critère un", rapport)

    def test_cases_file_remplace_cas_yaml_sans_toucher_au_decompte(self):
        autre = self.tmp / "cas-commandes.yaml"
        autre.write_text(yaml.safe_dump([{"id": "cmd1", "question": "/monthly-flow x"}], allow_unicode=True), encoding="utf-8")
        sortie = self.lancer("--rejudge", "2026-10-01-090000", "--cases-file", str(autre), "--cases", "cmd1")
        self.assertIn("pas de trace pour ce cas dans le passage indiqué, ignoré", sortie)
        with self.assertRaises(SystemExit) as erreur:         # c1 n'existe que dans cas.yaml
            self.lancer("--rejudge", "2026-10-01-090000", "--cases-file", str(autre), "--cases", "c1")
        self.assertIn("Cas inconnus : c1", str(erreur.exception))

    def test_cases_file_absent(self):
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("--cases-file", str(self.tmp / "nulle-part.yaml"))
        self.assertIn("Cas introuvables", str(erreur.exception))

    def test_cas_inconnu_et_fichier_de_cas_absent(self):
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("--cases", "inexistant", "--rejudge", "2026-10-01-090000")
        self.assertIn("Cas inconnus : inexistant", str(erreur.exception))
        essai.CASES_FILE.unlink()
        with self.assertRaises(SystemExit):
            self.lancer("--rejudge", "2026-10-01-090000")

    def test_passage_a_rejuger_introuvable(self):
        with self.assertRaises(SystemExit):
            self.lancer("--rejudge", "1999-01-01-000000")

    def test_main_refuse_l_ancien_nom_d_option(self):
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
            self.lancer("--rejuger", "2026-10-01-090000", "--cas", "c1")
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("« --rejuger »", erreur.getvalue())
        self.assertIn("« --rejudge »", erreur.getvalue())
        self.assertEqual(self.commandes, [])

    def test_main_refuse_les_anciennes_cles_du_fichier_de_cas(self):
        essai.CASES_FILE.write_text(yaml.safe_dump([{"id": "c1", "question": "Question un ?", "posture": "Delivery",
                                                     "verifications": [{"outil": "search_library"}],
                                                     "jugements": ["Critère un"]}], allow_unicode=True), encoding="utf-8")
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
            self.lancer("--rejudge", "2026-10-01-090000", "--cases", "c1")
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("cas c1 : la clé « jugements » n'existe plus ; utiliser « judgements »", erreur.getvalue())
        self.assertEqual(self.commandes, [])

    def test_language_en_liste_les_cas_sans_variante_et_ne_rejoue_rien(self):
        sortie = self.lancer("--language", "en")
        self.assertIn("Cas sans variante en : c1, c2", sortie)
        self.assertIn("Aucun cas n'a de variante en : rien à rejouer.", sortie)
        self.assertEqual(self.commandes, [])
        self.assertEqual(list(essai.REPORT_DIR.glob("essai-*.md")) if essai.REPORT_DIR.exists() else [], [])

    def test_langue_ancien_nom_refuse(self):
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
            self.lancer("--langue", "en")
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("« --langue »", erreur.getvalue())
        self.assertIn("« --language »", erreur.getvalue())

    def test_langue_en_ne_rejoue_que_les_cas_avec_variante(self):
        essai.CASES_FILE.write_text(yaml.safe_dump([
            {"id": "c1", "question": "Question un ?", "posture": "Delivery"},
            {"id": "c2", "question": "Question deux ?", "posture": "Delivery",
             "en": {"question": "Question two?"}}], allow_unicode=True), encoding="utf-8")
        questions = []
        with mock.patch.object(essai, "make_copy", lambda *a, **k: None), \
             mock.patch.object(essai, "prepare_memory", lambda *a, **k: {}), \
             mock.patch.object(essai, "drop_copy"), \
             mock.patch.object(essai, "run_session", lambda question, *a, **k: questions.append(question) or SEANCE):
            sortie = self.lancer("--language", "en", "--retries", "0")
        self.assertEqual(questions, ["Question two?"])
        self.assertIn("Cas sans variante en : c1", sortie)
        rapport = next(essai.REPORT_DIR.glob("essai-*.md")).read_text(encoding="utf-8")
        self.assertIn("langue : en", rapport)
        # le passage créé par ce lancement, pas le passage factice du setUp (l'ordre d'un glob n'est pas garanti)
        nouveaux = [d for d in essai.DATA.iterdir() if d.is_dir() and d.name != "2026-10-01-090000"]
        self.assertEqual(len(nouveaux), 1)
        resultats = json.loads((nouveaux[0] / "resultats.json").read_text(encoding="utf-8"))
        self.assertEqual(resultats["langue"], "en")

    def test_outils_n_appelle_rien(self):
        sortie = self.lancer("--tools", "2026-10-01-090000")
        self.assertIn("## c1", sortie)
        self.assertEqual(self.commandes, [])


class AnciensNomsDOptions(unittest.TestCase):
    """Les anciens noms français des options sont refusés (arrêt, code 2) avec le nom actuel (lot 8)."""

    def test_chaque_ancien_nom_a_son_nouveau(self):
        self.assertEqual(essai.OLD_OPTIONS, {
            "--cas": "--cases", "--modele": "--model", "--juge-modele": "--judge-model", "--garder": "--keep",
            "--memoire-reelle": "--real-memory", "--rejuger": "--rejudge", "--outils": "--tools",
            "--etat-commite": "--committed-state", "--avec-bash": "--with-bash", "--langue": "--language"})

    def test_chaque_ancien_nom_est_refuse_avec_le_nom_actuel(self):
        for ancien, actuel in essai.OLD_OPTIONS.items():
            for argv in ([ancien, "x"], [f"{ancien}=x"]):
                with self.subTest(argv=argv):
                    erreur = io.StringIO()
                    with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
                        essai.check_options(argv)
                    self.assertEqual(stop.exception.code, 2)
                    self.assertIn(f"« {ancien} »", erreur.getvalue())
                    self.assertIn(f"« {actuel} »", erreur.getvalue())

    def test_les_nouveaux_noms_passent_sans_message(self):
        erreur = io.StringIO()
        argv = ["--cases", "a", "--model", "m", "--real-memory"]
        with contextlib.redirect_stderr(erreur):
            self.assertEqual(essai.check_options(argv), argv)
        self.assertEqual(erreur.getvalue(), "")


class AnciennesClesDeCas(unittest.TestCase):
    """Les anciennes clés françaises de cas.yaml sont refusées (arrêt, code 2), cas et clé actuelle nommés (lot 8)."""

    def refuse(self, cas):
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
            essai.normalize_cases(cas)
        self.assertEqual(stop.exception.code, 2)
        return erreur.getvalue()

    ANCIEN = [{"id": "c1", "question": "Q ?", "posture": "Delivery",
               "verifications": [{"outil": "search_library", "collections": ["flow"]}, {"texte": "a"},
                                 {"sans_texte": "b"}, {"memoire_sans": "c"}, {"critic": True}],
               "prerequis": [{"livre": "L"}, {"collection": "veille", "minimum": 2}, {"sujet_absent": "x"}],
               "jugements": ["J"]}]

    def test_chaque_ancienne_cle_est_refusee_avec_la_cle_actuelle(self):
        cas_par_cle = {
            "jugements": ({"id": "c1", "jugements": ["J"]}, "judgements"),
            "prerequis": ({"id": "c1", "prerequis": [{"book": "L"}]}, "prerequisites"),
            "outil": ({"id": "c1", "verifications": [{"outil": "t"}]}, "tool"),
            "texte": ({"id": "c1", "verifications": [{"texte": "a"}]}, "text"),
            "sans_texte": ({"id": "c1", "verifications": [{"sans_texte": "b"}]}, "without_text"),
            "memoire_sans": ({"id": "c1", "verifications": [{"memoire_sans": "c"}]}, "memory_without"),
            "livre": ({"id": "c1", "prerequisites": [{"livre": "L"}]}, "book"),
            "sujet_absent": ({"id": "c1", "prerequisites": [{"sujet_absent": "x"}]}, "absent_topic"),
        }
        for ancienne, (cas, actuelle) in cas_par_cle.items():
            with self.subTest(cle=ancienne):
                message = self.refuse([cas])
                self.assertIn("c1", message)
                self.assertIn(f"« {ancienne} »", message)
                self.assertIn(f"« {actuelle} »", message)

    def test_nouvelles_cles_sans_message(self):
        nouveau = [{"id": "c1", "verifications": [{"tool": "t"}], "judgements": ["J"], "prerequisites": [{"book": "L"}]}]
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur):
            self.assertEqual(essai.normalize_cases(nouveau), nouveau)
        self.assertEqual(erreur.getvalue(), "")

    def test_ancienne_et_nouvelle_cle_ensemble_sont_refusees(self):
        message = self.refuse([{"id": "c1", "jugements": ["vieux"], "judgements": ["neuf"]}])
        self.assertIn("c1", message)
        self.assertIn("« jugements »", message)
        self.assertIn("« judgements »", message)

    def test_le_fichier_reel_n_utilise_que_les_nouvelles_cles(self):
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur):
            essai.normalize_cases(yaml.safe_load(CAS_REEL.read_text(encoding="utf-8")))
        self.assertEqual(erreur.getvalue(), "")


class Langue(Base):
    """Vocabulaire par langue, balise de posture, garde contre la dérive de formule, variantes `en:` des cas."""

    def trace(self, texte: str) -> dict:
        return {"all_text": texte}

    def test_vocabulaire_du_depot_a_le_mot_hypothese(self):
        vocabulaire = essai.load_vocabulary()
        self.assertEqual(vocabulaire["fr"]["hypothesis"], "Hypothèse")
        self.assertEqual(vocabulaire["en"]["hypothesis"], "Hypothesis")

    def test_vocabulaire_du_depot_a_les_deux_langues_et_les_memes_cles(self):
        vocabulaire = essai.load_vocabulary()
        self.assertEqual(sorted(vocabulaire), ["en", "fr", "posture_names"])
        self.assertEqual(sorted(vocabulaire["fr"]), sorted(vocabulaire["en"]))
        self.assertEqual(vocabulaire["posture_names"], ["Discovery", "Delivery", "Scaling", "Facilitation", "Critic"])
        for langue, valeurs in ((l, vocabulaire[l]) for l in essai.LANGUAGES):
            self.assertIn("{posture}", valeurs["posture_tag"], langue)
            self.assertTrue(valeurs["critic_plain_start"] and valeurs["critic_plain_end"], langue)
            re.compile(valeurs["posture_tag_pattern"])

    def test_le_format_de_la_balise_distingue_les_langues(self):
        vocabulaire = essai.load_vocabulary()
        self.assertEqual(vocabulaire["fr"]["posture_tag"], "[Posture : {posture}]")
        self.assertEqual(vocabulaire["en"]["posture_tag"], "[Posture: {posture}]")
        self.assertEqual(essai.posture_tags("[Posture : Delivery] puis [Posture : Critic]", "fr"), ["Delivery", "Critic"])
        self.assertEqual(essai.posture_tags("[Posture : Delivery]", "en"), [])
        self.assertEqual(essai.posture_tags("[Posture: Delivery]", "en"), ["Delivery"])
        self.assertEqual(essai.posture_tags("[Posture: Delivery]", "fr"), [])

    def test_balise_francaise_dans_une_reponse_francaise_reussit(self):
        verdict = essai.check_posture("Delivery", self.trace("[Posture : Delivery]\nTexte."), "fr")
        self.assertTrue(verdict["ok"])

    def test_balise_anglaise_dans_une_reponse_francaise_echoue(self):
        verdict = essai.check_posture("Delivery", self.trace("[Posture: Delivery]\nTexte."), "fr")
        self.assertFalse(verdict["ok"])
        self.assertIn("balise dans le format de l'autre langue : Delivery", verdict["justification"])
        self.assertIn("[Posture : {posture}]", verdict["justification"])

    def test_balise_francaise_dans_une_reponse_anglaise_echoue(self):
        self.assertFalse(essai.check_posture("Delivery", self.trace("[Posture : Delivery]"), "en")["ok"])
        self.assertTrue(essai.check_posture("Delivery", self.trace("[Posture: Delivery]"), "en")["ok"])

    def test_les_deux_formats_dans_la_meme_reponse_echouent(self):
        verdict = essai.check_posture("Delivery", self.trace("[Posture : Delivery] ... [Posture: Critic]"), "fr")
        self.assertFalse(verdict["ok"])

    def test_balise_mal_ecrite_echoue_meme_a_cote_d_une_balise_juste(self):
        for texte in ("[Posture : Délivery]\nTexte.", "[Posture : delivery]\nTexte.",
                      "[Posture : Delivery]\nTexte.\n[Posture : Livraison]"):
            with self.subTest(texte=texte):
                verdict = essai.check_posture("Delivery", self.trace(texte), "fr")
                self.assertFalse(verdict["ok"])
                self.assertIn("balise mal écrite : [Posture : ", verdict["justification"])
                self.assertIn("(attendu : [Posture : Delivery])", verdict["justification"])

    def test_balises_justes_de_plusieurs_postures_reussissent(self):
        self.assertTrue(essai.check_posture("Delivery", self.trace("[Posture : Delivery]\n…\n[Posture : Critic]"), "fr")["ok"])
        self.assertTrue(essai.check_posture("Delivery", self.trace("[Posture: Delivery]\n…\n[Posture: Critic]"), "en")["ok"])

    def test_indicateur_de_place_de_la_balise(self):
        tete = essai.check_tag_placement("Delivery", {"answer": "\n[Posture : Delivery]\nTexte."}, "fr")
        self.assertTrue(tete["ok"])
        self.assertTrue(tete["indicateur"])
        self.assertEqual(tete["critere"], "La balise de posture ouvre la réponse")
        self.assertTrue(essai.check_tag_placement("Delivery", {"answer": "**[Posture : Delivery]**\nTexte."}, "fr")["ok"])
        self.assertTrue(essai.check_tag_placement("Delivery", {"answer": "[Posture: Delivery]\nText."}, "en")["ok"])
        fin = essai.check_tag_placement("Delivery", {"answer": "Voici mon analyse " + "x" * 120 + "\n\n[Posture : Delivery]"}, "fr")
        self.assertFalse(fin["ok"])
        self.assertIn("première ligne : Voici mon analyse", fin["justification"])
        self.assertLessEqual(len(fin["justification"]) - len("première ligne : "), 80)
        self.assertFalse(essai.check_tag_placement("Delivery", {"answer": "[Posture: Delivery]\nTexte."}, "fr")["ok"])
        self.assertIsNone(essai.check_tag_placement("aucune", {"answer": "Une question ?"}, "fr"))
        self.assertIsNone(essai.check_tag_placement(None, {"answer": "Une question ?"}, "fr"))
        # la place ne change pas la vérification bloquante
        self.assertTrue(essai.check_posture("Delivery", {"all_text": "Texte.\n[Posture : Delivery]"}, "fr")["ok"])

    def test_aucune_balise_d_aucune_langue(self):
        self.assertTrue(essai.check_posture("aucune", self.trace("Une question ?"), "fr")["ok"])
        self.assertFalse(essai.check_posture("aucune", self.trace("[Posture: Delivery]"), "fr")["ok"])
        self.assertFalse(essai.check_posture("aucune", self.trace("[Posture : Delivery]"), "fr")["ok"])

    def test_francais_par_defaut(self):
        self.assertEqual(essai.DEFAULT_LANGUAGE, "fr")
        self.assertTrue(essai.check_posture("Delivery", self.trace("[Posture : Delivery]"))["ok"])

    CAS = {"id": "c1", "question": "Question ?", "posture": "Delivery",
           "verifications": [{"tool": "search_library"}, {"text": "hors biblioth[eè]que"}],
           "judgements": ["Critère"],
           "en": {"question": "Question?", "judgements": ["Criterion"], "text": "outside the library"}}

    def test_cas_francais_inchange_meme_avec_un_bloc_en(self):
        self.assertIs(essai.case_for_language(self.CAS, "fr"), self.CAS)

    def test_variante_en_remplace_question_criteres_et_motif(self):
        cas = essai.case_for_language(self.CAS, "en")
        self.assertEqual(cas["question"], "Question?")
        self.assertEqual(cas["judgements"], ["Criterion"])
        self.assertEqual(cas["verifications"], [{"tool": "search_library"}, {"text": "outside the library"}])
        self.assertEqual(cas["posture"], "Delivery")
        self.assertNotIn("en", cas)
        self.assertEqual(self.CAS["question"], "Question ?")       # le cas d'origine n'est pas modifié

    def test_cas_sans_variante_renvoie_none(self):
        self.assertIsNone(essai.case_for_language({"id": "c2", "question": "Q ?"}, "en"))

    def test_les_cas_reels_ont_une_variante_en_complete(self):
        """Lot 6 : chaque cas de cas.yaml a son bloc `en:` (question, critères) ; la variante garde la forme du français."""
        cas_reels = essai.normalize_cases(yaml.safe_load(CAS_REEL.read_text(encoding="utf-8")))
        self.assertEqual(len(cas_reels), 13)
        for cas in cas_reels:
            variante = essai.case_for_language(cas, "en")
            with self.subTest(cas=cas["id"]):
                self.assertIsNotNone(variante)
                self.assertNotEqual(variante["question"], cas["question"])
                self.assertEqual(len(variante.get("judgements") or []), len(cas.get("judgements") or []))
                self.assertEqual([type(j) for j in variante.get("judgements") or []], [type(j) for j in cas.get("judgements") or []])
                self.assertEqual({k: v for k, v in variante.items() if k not in ("question", "judgements", "verifications", "cases_fixture")},
                                 {k: v for k, v in cas.items() if k not in ("question", "judgements", "verifications", "cases_fixture", "en")})
                self.assertEqual("cases_fixture" in variante, "cases_fixture" in cas)
                for regle, regle_en in zip(cas.get("verifications") or [], variante.get("verifications") or []):
                    self.assertEqual(set(regle), set(regle_en))
                if any("text" in r for r in cas.get("verifications") or []):       # le motif suit la langue
                    self.assertTrue(any(r.get("text") == "outside (of )?the library" for r in variante["verifications"]))

    def test_la_variante_en_ne_contient_pas_de_formule_francaise_de_reponse(self):
        """Les critères jugés en anglais citent les formules anglaises, jamais « J'en déduis » ni « hors bibliothèque »."""
        for cas in essai.normalize_cases(yaml.safe_load(CAS_REEL.read_text(encoding="utf-8"))):
            texte = yaml.safe_dump(cas["en"], allow_unicode=True)
            for formule in ("J'en déduis", "Hypothèse", "hors bibliothèque"):
                self.assertNotIn(formule, texte, cas["id"])

    def test_les_clefs_francaises_d_un_bloc_en_sont_refusees(self):
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
            essai.normalize_cases([{"id": "c1", "en": {"jugements": ["J"], "texte": "t"}}])
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("c1 (en)", erreur.getvalue())
        self.assertIn("« jugements »", erreur.getvalue())
        self.assertIn("« judgements »", erreur.getvalue())

    def test_prompts_du_juge_par_langue(self):
        self.assertIs(essai.JUDGE_PROMPT, essai.JUDGE_PROMPT_FR)
        self.assertTrue(essai.JUDGE_PROMPT_FR.startswith("Tu évalues"))
        self.assertTrue(essai.JUDGE_PROMPT_EN.startswith("You evaluate"))
        for langue, prompt in essai.JUDGE_PROMPTS.items():
            for champ in ("{question}", "{calls}", "{sections}", "{mentions}", "{answer}", "{criteria}"):
                self.assertIn(champ, prompt, langue)
            self.assertIn(essai.JUDGE_KEYS[langue], prompt)
        self.assertNotIn("jugements", essai.JUDGE_PROMPT_EN)

    def test_le_juge_anglais_recoit_le_prompt_anglais_et_lit_sa_cle(self):
        self.reponses.append(self.termine(json.dumps({"result": json.dumps(
            {"judgements": [{"criterion": "Criterion", "justification": "Yes.", "ok": True}]})})))
        cas = {"id": "c1", "question": "Question?", "judgements": ["Criterion"]}
        trace = {"calls": [], "sections": [], "mentions": [], "answer": "An answer."}
        verdicts = essai.judge(cas, trace, None, self.tmp, "en")
        self.assertEqual(verdicts, [{"critere": "Criterion", "ok": True, "justification": "Yes."}])
        invite = self.commandes[0][self.commandes[0].index("-p") + 1]
        self.assertIn("You evaluate the answer", invite)
        self.assertIn("- none", invite)

    def test_le_juge_francais_est_inchange(self):
        self.reponses.append(self.termine(json.dumps({"result": json.dumps(
            {"jugements": [{"critere": "C", "justification": "Oui.", "ok": True}]})})))
        trace = {"calls": [], "sections": [], "mentions": [], "answer": ""}
        essai.judge({"id": "c1", "question": "Q ?", "judgements": ["C"]}, trace, None, self.tmp)
        invite = self.commandes[0][self.commandes[0].index("-p") + 1]
        self.assertTrue(invite.startswith("Tu évalues"))
        self.assertIn("- aucun", invite)
        self.assertIn("(aucune réponse)", invite)

    def test_resultats_precedents_de_la_meme_langue_seulement(self):
        for nom, langue in (("2026-10-01-000001", None), ("2026-10-01-000002", "en")):
            dossier = essai.DATA / nom
            dossier.mkdir(parents=True)
            donnees = {"cas": [{"id": "c1", "verifications": [{"critere": "k", "ok": nom.endswith("1")}]}]}
            if langue:
                donnees["langue"] = langue
            (dossier / "resultats.json").write_text(json.dumps(donnees), encoding="utf-8")
        courant = essai.DATA / "2026-10-02-000000"
        self.assertEqual(essai.previous_results(courant), {("c1", "k"): True})            # français : le passage sans champ
        self.assertEqual(essai.previous_results(courant, "en"), {("c1", "k"): False})
        self.assertEqual(essai.previous_results(courant, "fr"), {("c1", "k"): True})


class MemoireEtContexteParLangue(unittest.TestCase):
    """Mémoire et contexte neutres par langue : français à la racine, anglais dans memoire/en/ et contexte-neutre.en.md."""

    RACINE = Path(__file__).resolve().parents[2]
    POSTURES = ("delivery", "discovery", "scaling", "facilitation")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.copie = Path(self.temp.name)
        shutil.copytree(self.RACINE / ".claude" / "skills", self.copie / ".claude" / "skills",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(self.RACINE / "tests" / "postures", self.copie / "tests" / "postures")

    def tearDown(self):
        self.temp.cleanup()

    def test_la_memoire_anglaise_a_les_memes_postures_et_fichiers_que_la_francaise(self):
        fr = self.RACINE / "tests" / "postures" / "memoire"
        en = fr / "en"
        for posture in self.POSTURES:
            for nom in ("MEMORY.md", "BOND.md"):
                self.assertTrue((fr / posture / nom).is_file(), (posture, nom))
                self.assertTrue((en / posture / nom).is_file(), ("en", posture, nom))

    def test_la_memoire_anglaise_et_le_contexte_anglais_ne_contiennent_pas_de_francais(self):
        fichiers = list((self.RACINE / "tests" / "postures" / "memoire" / "en").rglob("*.md"))
        fichiers.append(self.RACINE / "tests" / "postures" / "contexte-neutre.en.md")
        for fichier in fichiers:
            texte = fichier.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"[éèêàâçùûôîï]", texte), fichier.name)
            self.assertNotIn("l'utilisateur", texte, fichier.name)

    def test_le_dossier_en_n_est_pas_une_posture_pour_le_francais(self):
        neutre = self.copie / "tests" / "postures" / "memoire"
        self.assertEqual([p.name for p in essai.neutral_postures(neutre, "fr")], sorted(self.POSTURES))
        self.assertEqual([p.name for p in essai.neutral_postures(neutre / "en", "en")], sorted(self.POSTURES))

    def test_sanctums_anglais_figes_et_contexte_anglais_depose(self):
        placed = essai.prepare_memory(self.copie, real=False, language="en")
        for posture in self.POSTURES:
            sanctum = self.copie / "_bmad" / "memory" / f"pmzilla-{posture}-bmad"
            attendu = (self.copie / "tests" / "postures" / "memoire" / "en" / posture / "MEMORY.md").read_text(encoding="utf-8")
            self.assertEqual((sanctum / "MEMORY.md").read_text(encoding="utf-8"), attendu)
            self.assertIn("Language:** English", (sanctum / "BOND.md").read_text(encoding="utf-8"))
        contexte = (self.copie / ".pmzilla" / "contexte.md").read_text(encoding="utf-8")
        self.assertIn("User's local context (neutral)", contexte)
        self.assertIn(".pmzilla/contexte.md", placed)

    def test_sanctums_francais_par_defaut_inchanges(self):
        essai.prepare_memory(self.copie, real=False)
        sanctum = self.copie / "_bmad" / "memory" / "pmzilla-delivery-bmad"
        self.assertIn("Équipes suivies", (sanctum / "MEMORY.md").read_text(encoding="utf-8"))
        self.assertIn("Contexte local de l'utilisateur (neutre)", (self.copie / ".pmzilla" / "contexte.md").read_text(encoding="utf-8"))

    def test_memoire_anglaise_introuvable_est_une_erreur_claire(self):
        shutil.rmtree(self.copie / "tests" / "postures" / "memoire" / "en")
        with self.assertRaises(SystemExit) as erreur:
            essai.prepare_memory(self.copie, real=False, language="en")
        self.assertIn("memoire/en", str(erreur.exception))

    def test_contexte_neutre_anglais_manquant_est_une_erreur(self):
        (self.copie / "tests" / "postures" / "contexte-neutre.en.md").unlink()
        with mock.patch.object(essai, "WORKSPACE", self.copie / "autre"), self.assertRaises(SystemExit) as erreur:
            essai.prepare_memory(self.copie, real=False, language="en")
        self.assertIn("contexte-neutre.en.md", str(erreur.exception))


REPONSE_CONFORME = """Le goulot se déplace vers la revue. Yeret (2026-05-21) y voit la vérification, Murphy (2026-09-19) la décision.

J'en déduis que la file de revue grossit.

## Sources
- Yeret, Yuval, « AI Made Engineering Faster », 2026-05-21, https://exemple.test/a
- Murphy, Ant, « Decision capacity », 2026-09-19, https://exemple.test/b
- agilepainrelief.com (auteur non indiqué), « Skill loss », 2026-04-23, https://agilepainrelief.com/c
"""


class VerificationsDeSources(unittest.TestCase):
    """ends_with_sources, dates_in_sources, sources_cited : structure d'une réponse qui cite des articles de veille."""

    def trace(self, texte: str) -> dict:
        return {"answer": texte, "all_text": texte}

    def test_les_dates_d_un_titre_ne_comptent_pas_mais_celles_du_texte_oui(self):
        """La période du titre d'une synthèse n'est pas la date d'un article ; une date d'article hors Sources reste refusée."""
        titre = "# Synthèse de veille, du 2026-09-27 au 2026-10-07\n\n### Du 2026-09-01 au 2026-09-30\n\n"
        self.assertTrue(essai.check_dates_in_sources(self.trace(titre + REPONSE_CONFORME))["ok"])
        verdict = essai.check_dates_in_sources(self.trace(titre + REPONSE_CONFORME.replace("Murphy (2026-09-19)", "Murphy (2026-08-02)", 1)))
        self.assertFalse(verdict["ok"])
        self.assertIn("2026-08-02", verdict["justification"])
        self.assertNotIn("2026-09-27", verdict["justification"])
        # une date dans un paragraphe qui ressemble à un titre mais ne commence pas par « # » compte
        self.assertFalse(essai.check_dates_in_sources(self.trace("Période du 2026-09-27.\n\n" + REPONSE_CONFORME))["ok"])

    def test_reponse_conforme(self):
        trace = self.trace(REPONSE_CONFORME + "")
        self.assertTrue(essai.check_ends_with_sources(trace)["ok"])
        self.assertTrue(essai.check_dates_in_sources(trace)["ok"])
        # agilepainrelief.com : cité par son radical, même écrit « Agile Pain Relief »
        avec_site = self.trace(REPONSE_CONFORME.replace("la décision.", "la décision. Agile Pain Relief (2026-04-23) parle de perte de compétence."))
        self.assertTrue(essai.check_sources_cited(avec_site)["ok"])

    def test_livre_apres_sources(self):
        verdict = essai.check_ends_with_sources(self.trace(REPONSE_CONFORME + "\nLivre : Reinertsen, *The Principles of Product Development Flow*, section X.\n"))
        self.assertFalse(verdict["ok"])
        self.assertIn("texte après la liste : « Livre : Reinertsen", verdict["justification"])

    def test_question_apres_sources(self):
        verdict = essai.check_ends_with_sources(self.trace(REPONSE_CONFORME + "\nVeux-tu que je confronte ces positions aux livres ?\n"))
        self.assertFalse(verdict["ok"])

    def test_sources_sans_titre_ou_absente(self):
        self.assertFalse(essai.check_ends_with_sources(self.trace("Une réponse sans section."))["ok"])
        self.assertIn("aucune section", essai.check_dates_in_sources(self.trace("Yeret (2026-05-21)."))["justification"])
        self.assertFalse(essai.check_sources_cited(self.trace("Rien."))["ok"])

    def test_titre_sources_en_gras_ou_avec_deux_points(self):
        for titre in ("**Sources**", "Sources :", "### Sources"):
            trace = self.trace(REPONSE_CONFORME.replace("## Sources", titre))
            self.assertTrue(essai.check_ends_with_sources(trace)["ok"], titre)

    def test_lignes_sources_sans_puce_acceptees(self):
        avec_site = REPONSE_CONFORME.replace("la décision.", "la décision. Agile Pain Relief (2026-04-23) parle de perte de compétence.")
        sans_puce = avec_site.replace("\n- ", "\n")
        trace = self.trace(sans_puce)
        self.assertTrue(essai.check_ends_with_sources(trace)["ok"])
        self.assertTrue(essai.check_dates_in_sources(trace)["ok"])
        self.assertTrue(essai.check_sources_cited(trace)["ok"])
        self.assertIn("3 ligne(s) Sources", essai.check_ends_with_sources(trace)["justification"])

    def test_livre_en_puce_sans_date_ni_lien_n_est_pas_une_entree(self):
        trace = self.trace(REPONSE_CONFORME + "- Livres : Reinertsen, *The Principles of Product Development Flow*\n")
        verdict = essai.check_ends_with_sources(trace)
        self.assertFalse(verdict["ok"])
        self.assertIn("Livres : Reinertsen", verdict["justification"])

    def test_sous_titre_dans_sources_est_une_sous_section(self):
        trace = self.trace(REPONSE_CONFORME.replace("## Sources\n", "## Sources\n\nArticles de veille :\n\n"))
        verdict = essai.check_ends_with_sources(trace)
        self.assertFalse(verdict["ok"])
        self.assertIn("Articles de veille", verdict["justification"])

    def test_une_ligne_avec_un_lien_sans_date_est_une_entree(self):
        trace = self.trace(REPONSE_CONFORME + "- Autre, « Sans date », https://exemple.test/z\n")
        self.assertTrue(essai.check_ends_with_sources(trace)["ok"])

    def test_continuation_indentee_d_une_ligne_n_est_pas_du_texte_apres(self):
        trace = self.trace(REPONSE_CONFORME.replace("https://exemple.test/b", "https://exemple.test/b\n  suite du lien"))
        self.assertTrue(essai.check_ends_with_sources(trace)["ok"])

    def test_date_du_texte_absente_de_sources(self):
        verdict = essai.check_dates_in_sources(self.trace(REPONSE_CONFORME.replace("Murphy (2026-09-19)", "Murphy (2026-08-02)", 1)))
        self.assertFalse(verdict["ok"])
        self.assertIn("2026-08-02", verdict["justification"])

    def test_la_date_est_comparee_aux_lignes_sources_seulement(self):
        # une date présente dans la liste mais pas dans le texte ne compte pas ; une date du texte hors liste est signalée
        trace = self.trace(REPONSE_CONFORME + "")
        self.assertTrue(essai.check_dates_in_sources(trace)["ok"])

    def test_ligne_sources_jamais_citee(self):
        trace = self.trace(REPONSE_CONFORME.replace("Murphy (2026-09-19) la décision", "un autre auteur la décision"))
        verdict = essai.check_sources_cited(trace)
        self.assertFalse(verdict["ok"])
        self.assertIn("Murphy", verdict["justification"])

    def test_un_mot_court_ne_declenche_pas_de_citation(self):
        # « ant » dans « consultants » ne doit pas faire croire que la ligne de Murphy, Ant est citée
        trace = self.trace(REPONSE_CONFORME.replace("Murphy (2026-09-19) la décision", "des consultants (2026-09-19) la décision"))
        self.assertFalse(essai.check_sources_cited(trace)["ok"])


class CritereJugeNonBloquant(Base):
    """Un critère jugé peut être `{text: …, non_blocking: true}` : un indicateur, rapporté à part."""

    TRACE = {"calls": [], "sections": [], "mentions": [], "answer": "Une réponse."}

    def juger(self, criteres):
        self.reponses.append(self.termine(json.dumps({"result": json.dumps({"jugements": [
            {"critere": "x", "justification": "Oui.", "ok": True}, {"critere": "y", "justification": "Non.", "ok": False}]})})))
        return essai.judge({"id": "c1", "question": "Q ?", "judgements": criteres}, self.TRACE, None, self.tmp)

    def test_critere_texte_reste_bloquant_et_critere_dict_devient_indicateur(self):
        verdicts = self.juger(["Critère un", {"text": "Critère deux", "non_blocking": True}])
        self.assertEqual([v["critere"] for v in verdicts], ["Critère un", "Critère deux"])
        self.assertNotIn("indicateur", verdicts[0])
        self.assertTrue(verdicts[1]["indicateur"])
        self.assertFalse(verdicts[1]["ok"])
        self.assertEqual(len(essai.blocking(verdicts)), 1)
        self.assertEqual(len(essai.indicators(verdicts)), 1)

    def test_le_prompt_du_juge_ne_contient_que_le_texte_du_critere(self):
        self.juger(["Critère un", {"text": "Critère deux", "non_blocking": True}])
        invite = self.commandes[0][self.commandes[0].index("-p") + 1]
        self.assertIn("2. Critère deux", invite)
        self.assertNotIn("non_blocking", invite)

    def test_le_critere_de_paragraphe_de_veille_goulot_est_un_indicateur_et_les_trois_verifications_sont_bloquantes(self):
        cas = {c["id"]: c for c in yaml.safe_load(CAS_REEL.read_text(encoding="utf-8"))}["veille-goulot"]
        paragraphe = cas["judgements"][0]
        self.assertTrue(isinstance(paragraphe, dict) and paragraphe["non_blocking"] is True)
        self.assertIn("Chaque paragraphe", paragraphe["text"])
        self.assertIsInstance(cas["judgements"][1], str)                      # « poids d'un livre » reste bloquant
        regles = [r for r in cas["verifications"] if set(r) & {"ends_with_sources", "dates_in_sources", "sources_cited"}]
        self.assertEqual(len(regles), 3)
        self.assertTrue(all(not r.get("non_blocking") for r in regles))

    def test_total_bloquant_des_cas_reels_est_38(self):
        """32 d'avant, moins le critère de paragraphe de veille-goulot (indicateur), plus ses trois vérifications (34), plus un par cas du module de cas (3), plus un pour le second critère de experimentation-en-cours (38)."""
        total = 0
        for cas in yaml.safe_load(CAS_REEL.read_text(encoding="utf-8")):
            total += 1 if cas.get("posture") is not None else 0
            total += sum(1 for r in cas.get("verifications") or [] if not r.get("non_blocking"))
            total += sum(1 for j in cas.get("judgements") or [] if not (isinstance(j, dict) and j.get("non_blocking")))
        self.assertEqual(total, 38)


class IndicateursNonBloquants(Base):
    """`non_blocking: true` : la vérification est rapportée à part et ne compte ni dans le total ni dans les régressions."""

    def test_check_auto_marque_l_indicateur(self):
        trace = {"answer": "Pas de Sources.", "all_text": "Pas de Sources."}
        bloquant = essai.check_auto({"ends_with_sources": True}, trace, {})
        indicateur = essai.check_auto({"ends_with_sources": True, "non_blocking": True}, trace, {})
        self.assertNotIn("indicateur", bloquant)
        self.assertTrue(indicateur["indicateur"])
        self.assertFalse(indicateur["ok"])
        self.assertEqual(essai.blocking([bloquant, indicateur]), [bloquant])
        self.assertEqual(essai.indicators([bloquant, indicateur]), [indicateur])

    def test_non_blocking_s_applique_a_n_importe_quelle_regle(self):
        trace = {"answer": "x", "all_text": "x", "calls": []}
        self.assertTrue(essai.check_auto({"text": "x", "non_blocking": True}, trace, {})["indicateur"])

    def test_rapport_et_bilan_hors_indicateurs(self):
        resultats = [{"id": "c1", "question": "Q ?", "posture": "Delivery", "cost": 0.5, "turns": 3, "error": False,
                      "verifications": [{"critere": "Posture Delivery", "ok": True, "justification": "ok"},
                                        {"critere": "Sources dernière", "ok": False, "justification": "texte après", "indicateur": True}]}]
        chemin = essai.write_report("2026-10-08-000000", resultats, {}, "abcdef1234")
        texte = chemin.read_text(encoding="utf-8")
        self.assertIn("1/1 vérifications réussies sur 1 cas", texte)               # l'indicateur n'est pas compté
        self.assertIn("Indicateurs non bloquants (rapportés à part, hors du décompte) : 0/1 réussis", texte)
        self.assertIn("| c1 | 1/1 (+ indicateurs 0/1) |", texte)
        self.assertIn("❌ Sources dernière (indicateur, non bloquant)", texte)
        self.assertNotIn("Régressions", texte)

    def test_un_indicateur_en_echec_n_est_pas_une_regression(self):
        resultats = [{"id": "c1", "question": "Q ?", "posture": "", "cost": None, "turns": None, "error": False,
                      "verifications": [{"critere": "Sources dernière", "ok": False, "justification": "x", "indicateur": True}]}]
        texte = essai.write_report("2026-10-08-000001", resultats, {("c1", "Sources dernière"): True}, "abcdef1234").read_text(encoding="utf-8")
        self.assertNotIn("Régressions", texte)


class DernierEchange(Base):
    """Le juge lit tous les messages du dernier échange (lot de fiabilité du jeu d'essai, 2026-10-08), pas seulement le
    dernier `result` ; l'indicateur « un seul message final » repère un Critic restitué dans un second message."""

    # forme de la séance delivery-estimation du 2026-10-07-080429 : amorce, outils, Critic en arrière-plan, analyse,
    # texte du sous-agent, restitution de Critic, puis deux événements result
    ARRIERE_PLAN = [
        assistant(texte("[Posture : Delivery] Je charge l'agent."), appel("Skill", {}, "s1")),
        resultat_outil("s1", "ok"),
        assistant(appel("Agent", {"subagent_type": "pmzilla-critic"}, "a1")),
        resultat_outil("a1", "lancé en arrière-plan"),
        assistant(texte("[Posture : Delivery] Analyse du flux, sans Critic."), parent=None),
        assistant(texte("Texte du sous-agent Critic."), parent="a1"),
        assistant(texte("[Posture : Critic] Critiques de Critic : le diagnostic reste dans l'équipe.")),
        fin("[Posture : Delivery] Analyse du flux, sans Critic."),
        fin("[Posture : Critic] Critiques de Critic : le diagnostic reste dans l'équipe."),
    ]

    def test_les_messages_du_dernier_echange_dans_l_ordre(self):
        trace = essai.read_trace(self.ARRIERE_PLAN)
        self.assertEqual(trace["messages"], ["[Posture : Delivery] Analyse du flux, sans Critic.",
                                             "[Posture : Critic] Critiques de Critic : le diagnostic reste dans l'équipe."])
        self.assertEqual(trace["result_count"], 2)
        self.assertNotIn("Je charge", " ".join(trace["messages"]))      # l'amorce avant les outils est exclue
        self.assertNotIn("sous-agent", " ".join(trace["messages"]))
        self.assertTrue(trace["answer"].startswith("[Posture : Critic]"))   # les contrôles bloquants lisent toujours le dernier

    def test_le_juge_recoit_les_messages_separes(self):
        trace = essai.read_trace(self.ARRIERE_PLAN)
        lu = essai.judged_answer(trace)
        self.assertIn("2 messages successifs", lu)
        self.assertLess(lu.index("=== message 1/2 ==="), lu.index("Analyse du flux"))
        self.assertLess(lu.index("=== message 2/2 ==="), lu.index("Critiques de Critic"))
        self.assertIn("successive messages", essai.judged_answer(trace, "en"))

    def test_un_seul_message_laisse_l_entree_du_juge_inchangee(self):
        trace = essai.read_trace(SEANCE)
        self.assertEqual(trace["messages"], ["Réponse finale avec Auteur, Titre."])
        self.assertEqual(essai.judged_answer(trace), trace["answer"])

    def test_le_prompt_envoye_au_juge_contient_les_deux_messages(self):
        trace = essai.read_trace(self.ARRIERE_PLAN)
        self.reponses = [self.termine(json.dumps({"result": json.dumps(
            {"jugements": [{"critere": "c", "justification": "j", "ok": True}]})}))]
        essai.judge({"question": "Q ?", "judgements": ["c"]}, trace, None, self.tmp)
        prompt = self.commandes[0][2]
        self.assertIn("=== message 1/2 ===", prompt)
        self.assertIn("Critiques de Critic", prompt)

    def test_indicateur_un_seul_message_final(self):
        mauvais = essai.check_single_final(essai.read_trace(self.ARRIERE_PLAN))
        self.assertFalse(mauvais["ok"])
        self.assertTrue(mauvais["indicateur"])
        self.assertIn("2 messages", mauvais["justification"])
        bon = essai.check_single_final(essai.read_trace(SEANCE))
        self.assertTrue(bon["ok"])
        self.assertEqual(essai.blocking([mauvais, bon]), [])         # jamais bloquant

    def test_result_dont_le_message_precede_l_outil_est_replace_a_sa_position(self):
        seance = [assistant(texte("Analyse"), appel("Agent", {}, "a1")), resultat_outil("a1", "ok"),
                  assistant(texte("Restitution de Critic")), fin("Analyse"), fin("Restitution de Critic")]
        trace = essai.read_trace(seance)
        self.assertEqual(trace["messages"], ["Analyse", "Restitution de Critic"])
        self.assertFalse(essai.check_single_final(trace)["ok"])


class Rejeux(Base):
    """Un cas dont une vérification bloquante échoue est rejoué 2 fois (réglable) : instable s'il réussit tous les rejeux,
    échec confirmé sinon ; au-delà de 3 cas en échec, aucun rejeu (2026-10-08)."""

    def setUp(self):
        super().setUp()
        self.cas = [{"id": f"c{i}", "question": f"Question {i} ?", "posture": "Delivery"} for i in (1, 2, 3, 4, 5)]
        self.sessions: list[str] = []
        self.sort: dict[str, list[bool]] = {}      # id du cas -> réussite de chaque séance successive (la première est l'essai)
        for patch in (mock.patch.object(essai, "git", lambda *a, **k: ""),
                      mock.patch.object(essai, "make_copy", lambda *a, **k: None),
                      mock.patch.object(essai, "prepare_memory", lambda *a, **k: {}),
                      mock.patch.object(essai, "drop_copy"),
                      mock.patch.object(essai, "run_session", self.fausse_seance)):
            patch.start()
            self.addCleanup(patch.stop)

    def fausse_seance(self, question, copie, mcp, model, trace, *a, **k):
        ident = "c" + question.split()[1]
        self.sessions.append(trace.name)
        reussit = self.sort.get(ident, [True]).pop(0) if self.sort.get(ident) else True
        etiquette = "Delivery" if reussit else "Discovery"          # la posture attendue est Delivery
        return [assistant(texte(f"[Posture : {etiquette}] réponse")), fin(f"[Posture : {etiquette}] réponse", cout=0.10)]

    def lancer(self, cas, *arguments) -> str:
        essai.CASES_FILE.write_text(yaml.safe_dump(cas, allow_unicode=True), encoding="utf-8")
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["posture_evals.py", *arguments]), contextlib.redirect_stdout(sortie):
            essai.main()
        return sortie.getvalue()

    def resultats(self) -> dict:
        chemin = max(essai.DATA.glob("*/resultats.json"))
        return {c["id"]: c for c in json.loads(chemin.read_text(encoding="utf-8"))["cas"]}

    def test_aucun_echec_aucun_rejeu(self):
        sortie = self.lancer(self.cas[:2])
        self.assertEqual(len(self.sessions), 2)
        self.assertIn("BILAN 2/2 · 0 régression(s) ·", sortie)
        self.assertNotIn("rejeux", sortie)

    def test_echec_puis_deux_reussites_est_instable_et_compte_comme_reussi(self):
        self.sort = {"c1": [False, True, True]}
        sortie = self.lancer(self.cas[:2])
        self.assertEqual(self.sessions, ["c1.jsonl", "c2.jsonl", "c1.rejeu1.jsonl", "c1.rejeu2.jsonl"])
        self.assertIn("BILAN 2/2 · 0 régression(s) · 1 instable(s) · rejeux 0.20 $", sortie)
        cas = self.resultats()["c1"]
        self.assertEqual((cas["statut"], len(cas["rejeux"])), ("instable", 2))
        self.assertTrue(cas["premier_echec"])
        rapport = next(essai.REPORT_DIR.glob("essai-*.md")).read_text(encoding="utf-8")
        self.assertIn("instable (1 échec sur 3)", rapport)
        self.assertIn("coût des rejeux 0.20 $", rapport)
        self.assertNotIn("Régressions", rapport)

    def test_echec_confirme_au_premier_rejeu_en_echec_et_serie_arretee(self):
        self.sort = {"c1": [False, False]}
        sortie = self.lancer(self.cas[:1])
        self.assertEqual(self.sessions, ["c1.jsonl", "c1.rejeu1.jsonl"])        # le second rejeu n'est pas payé
        self.assertIn("BILAN 0/1", sortie)
        self.assertIn("1 échec(s) confirmé(s)", sortie)
        self.assertEqual(self.resultats()["c1"]["statut"], "echec_confirme")

    def test_echec_confirme_apres_un_rejeu_reussi_puis_un_echec(self):
        self.sort = {"c1": [False, True, False]}
        self.lancer(self.cas[:1])
        self.assertEqual(len(self.sessions), 3)
        self.assertEqual(self.resultats()["c1"]["statut"], "echec_confirme")

    def test_regression_confirmee_quand_le_critere_avait_reussi_avant(self):
        self.lancer(self.cas[:1])                                    # premier passage : réussi
        self.sort = {"c1": [False, False]}
        with mock.patch.object(essai.dt, "datetime", wraps=essai.dt.datetime) as faux_dt:
            faux_dt.now.return_value = essai.dt.datetime(2099, 1, 1, 0, 0, 0)    # horodatage distinct du premier passage
            sortie = self.lancer(self.cas[:1])
        self.assertIn("1 régression(s)", sortie)

    def test_retries_0_desactive_les_rejeux(self):
        self.sort = {"c1": [False, True, True]}
        sortie = self.lancer(self.cas[:1], "--retries", "0")
        self.assertEqual(self.sessions, ["c1.jsonl"])
        self.assertIn("BILAN 0/1", sortie)
        self.assertNotIn("instable", sortie)

    def test_plus_de_trois_cas_en_echec_aucun_rejeu(self):
        self.sort = {f"c{i}": [False, True, True] for i in (1, 2, 3, 4)}
        sortie = self.lancer(self.cas)
        self.assertEqual(len(self.sessions), 5)
        self.assertIn("Aucun rejeu : 4 cas en échec", sortie)

    def test_plafond_reglable(self):
        self.sort = {f"c{i}": [False, True, True] for i in (1, 2)}
        sortie = self.lancer(self.cas, "--max-retried-cases", "1")
        self.assertEqual(len(self.sessions), 5)
        self.assertIn("Aucun rejeu : 2 cas en échec", sortie)

    def test_un_indicateur_en_echec_ne_declenche_pas_de_rejeu(self):
        for_each = [{"id": "c1", "question": "Question 1 ?", "posture": "Delivery",
                     "verifications": [{"text": "introuvable", "non_blocking": True}]}]
        sortie = self.lancer(for_each)
        self.assertEqual(self.sessions, ["c1.jsonl"])
        self.assertIn("BILAN 1/1", sortie)

    def test_instable_repete_au_passage_complet_suivant(self):
        cas = [{"id": f"c{i}", "question": f"Question {i} ?", "posture": "Delivery"} for i in range(1, 11)]
        self.sort = {"c1": [False, True, True]}
        self.lancer(cas)
        self.assertFalse(self.resultats()["c1"].get("instable_repete"))
        # le second passage doit porter un horodatage postérieur
        with mock.patch.object(essai.dt, "datetime", wraps=essai.dt.datetime) as faux_dt:
            faux_dt.now.return_value = essai.dt.datetime(2099, 1, 1, 0, 0, 0)
            self.sort = {"c1": [False, True, True]}
            self.lancer(cas)
        self.assertTrue(self.resultats()["c1"]["instable_repete"])
        rapport = sorted(essai.REPORT_DIR.glob("essai-*.md"))[-1].read_text(encoding="utf-8")
        self.assertIn("instable répété", rapport)

    def test_un_passage_partiel_ne_compte_pas_pour_l_instabilite_repetee(self):
        cas = [{"id": f"c{i}", "question": f"Question {i} ?", "posture": "Delivery"} for i in range(1, 11)]
        self.sort = {"c1": [False, True, True]}
        self.lancer(cas, "--cases", "c1")                                # partiel
        with mock.patch.object(essai.dt, "datetime", wraps=essai.dt.datetime) as faux_dt:
            faux_dt.now.return_value = essai.dt.datetime(2099, 1, 1, 0, 0, 0)
            self.sort = {"c1": [False, True, True]}
            self.lancer(cas, "--cases", "c1")
        self.assertFalse(self.resultats()["c1"]["instable_repete"])

    def test_rejudge_ne_rejoue_jamais(self):
        self.lancer(self.cas[:1])
        passage = max(p.name for p in essai.DATA.iterdir() if (p / "resultats.json").exists())
        (essai.DATA / passage / "c1.jsonl").write_text(
            "\n".join(json.dumps(e) for e in [assistant(texte("[Posture : Discovery] x")), fin("[Posture : Discovery] x")]),
            encoding="utf-8")
        avant = len(self.sessions)
        self.lancer(self.cas[:1], "--rejudge", passage)
        self.assertEqual(len(self.sessions), avant)


class CasQuiPlante(Base):
    """Un cas dont la préparation ou la séance plante est un échec du cas : le passage va au bout, avec un bilan,
    et la copie temporaire est supprimée (avant : le passage s'arrêtait sans bilan et laissait la copie)."""

    CAS = [{"id": "c1", "question": "Question un ?", "posture": "Delivery"},
           {"id": "c2", "question": "Question deux ?", "posture": "Delivery"}]

    def setUp(self):
        super().setUp()
        essai.CASES_FILE.write_text(yaml.safe_dump(self.CAS, allow_unicode=True), encoding="utf-8")
        patch = mock.patch.object(essai, "git", lambda *a, **k: "")
        patch.start()
        self.addCleanup(patch.stop)

    def lancer(self, *arguments) -> str:
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["posture_evals.py", *arguments]), contextlib.redirect_stdout(sortie):
            essai.main()
        return sortie.getvalue()

    def test_la_preparation_qui_plante_ne_coupe_pas_le_passage(self):
        copies = []

        def fausse_copie(cible, commit, untracked=True):
            copies.append(cible.name)
            if cible.name == "copie-c1":
                raise OSError("disque plein")

        with mock.patch.object(essai, "make_copy", fausse_copie), \
             mock.patch.object(essai, "prepare_memory", lambda copie, reel: {}), \
             mock.patch.object(essai, "run_session", lambda *a, **k: SEANCE), \
             mock.patch.object(essai, "drop_copy") as drop:
            sortie = self.lancer()
        self.assertEqual(copies, ["copie-c1", "copie-c2"])
        self.assertIn("ERREUR : OSError : disque plein", sortie)
        self.assertIn("BILAN", sortie)
        self.assertEqual(drop.call_count, 2)           # la copie du cas qui plante est supprimée aussi
        rapport = next(essai.REPORT_DIR.glob("essai-*.md")).read_text(encoding="utf-8")
        self.assertIn("## c1", rapport)
        self.assertIn("La séance a échoué", rapport)

    def test_etat_ancien_sans_contexte_neutre_utilise_celui_du_workspace(self):
        copie = self.tmp / "copie"
        (copie / "tests" / "postures" / "memoire").mkdir(parents=True)
        neutre = essai.WORKSPACE / essai.CONTEXTE_NEUTRE
        neutre.parent.mkdir(parents=True)
        neutre.write_text("contexte neutre du workspace", encoding="utf-8")
        with mock.patch.object(essai, "build_sanctums"), mock.patch.object(essai, "freeze_memory", lambda c, language="fr": {}):
            placed = essai.prepare_memory(copie, real=False)
        self.assertEqual((copie / ".pmzilla" / "contexte.md").read_text(encoding="utf-8"), "contexte neutre du workspace")
        self.assertIn(".pmzilla/contexte.md", placed)


class SanctumReelProtege(Base):
    """--real-memory copie le sanctum, ne l'utilise jamais en place et le laisse identique ; un seul passage à la fois."""

    def setUp(self):
        super().setUp()
        self.reel = essai.WORKSPACE / "_bmad" / "memory" / "pmzilla-delivery-bmad"
        (self.reel / "sessions").mkdir(parents=True)
        (self.reel / "MEMORY.md").write_text("vécu réel", encoding="utf-8")
        (self.reel / "sessions" / "2026-10-07.md").write_text("session réelle", encoding="utf-8")
        (self.reel / "CREED.md").write_text(f"sanctum : {essai.WORKSPACE}/_bmad/memory/pmzilla-delivery-bmad/", encoding="utf-8")
        self.copie = self.tmp / "copie"
        self.copie.mkdir()

    def test_le_sanctum_est_copie_pas_utilise_en_place(self):
        essai.prepare_memory(self.copie, real=True)
        copie = self.copie / "_bmad" / "memory" / "pmzilla-delivery-bmad"
        self.assertEqual((copie / "MEMORY.md").read_text(encoding="utf-8"), "vécu réel")
        self.assertNotEqual(copie.resolve(), self.reel.resolve())
        self.assertFalse(copie.is_symlink())
        self.assertNotEqual((copie / "MEMORY.md").stat().st_ino, (self.reel / "MEMORY.md").stat().st_ino)

    def test_ecrire_dans_la_copie_laisse_le_reel_identique(self):
        avant = essai.sanctum_digest()
        essai.prepare_memory(self.copie, real=True)
        copie = self.copie / "_bmad" / "memory" / "pmzilla-delivery-bmad"
        (copie / "MEMORY.md").write_text("modifié par la séance", encoding="utf-8")
        (copie / "sessions" / "2026-10-07.md").write_text("session de la séance", encoding="utf-8")
        self.assertEqual(essai.sanctum_digest(), avant)

    def test_les_chemins_absolus_du_sanctum_visent_la_copie(self):
        essai.prepare_memory(self.copie, real=True)
        texte = (self.copie / "_bmad" / "memory" / "pmzilla-delivery-bmad" / "CREED.md").read_text(encoding="utf-8")
        self.assertIn(str(self.copie), texte)
        self.assertNotIn(str(essai.WORKSPACE), texte)
        # le fichier réel garde son chemin : seule la copie est réécrite
        self.assertIn(str(essai.WORKSPACE), (self.reel / "CREED.md").read_text(encoding="utf-8"))

    def test_empreinte_change_si_le_reel_change(self):
        avant = essai.sanctum_digest()
        (self.reel / "sessions" / "2026-10-07.md").write_text("autre", encoding="utf-8")
        self.assertNotEqual(essai.sanctum_digest(), avant)

    def test_un_cas_qui_ecrit_dans_le_reel_est_un_echec(self):
        essai.CASES_FILE.write_text(yaml.safe_dump([{"id": "c1", "question": "Q ?", "posture": "Delivery"}]), encoding="utf-8")

        def seance_qui_ecrit_dans_le_reel(*a, **k):
            (self.reel / "MEMORY.md").write_text("écrit hors de la copie", encoding="utf-8")
            return SEANCE

        sortie = io.StringIO()
        with mock.patch.object(essai, "git", lambda *a, **k: ""), \
             mock.patch.object(essai, "make_copy", lambda *a, **k: None), \
             mock.patch.object(essai, "prepare_memory", lambda *a, **k: {}), \
             mock.patch.object(essai, "drop_copy"), \
             mock.patch.object(essai, "run_session", seance_qui_ecrit_dans_le_reel), \
             mock.patch.object(sys, "argv", ["posture_evals.py", "--real-memory"]), contextlib.redirect_stdout(sortie):
            essai.main()
        self.assertIn("le sanctum réel a changé pendant ce cas", sortie.getvalue())
        rapport = next(essai.REPORT_DIR.glob("essai-*.md")).read_text(encoding="utf-8")
        self.assertIn("❌ Sanctum réel intact", rapport)

    def test_un_second_passage_est_refuse(self):
        premier = essai.lock_pass(self.tmp / "essais")
        try:
            with self.assertRaises(SystemExit) as erreur:
                essai.lock_pass(self.tmp / "essais")
            self.assertIn("Un autre passage du jeu d'essai est en cours", str(erreur.exception))
        finally:
            premier.close()
        essai.lock_pass(self.tmp / "essais").close()      # libéré à la fin du premier passage


def _sans_accents(texte: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn")


class FauxLecteur:
    """Lecteur de prérequis inventé : mêmes réponses que LibraryReader (titres sans casse, collection exacte, tous les mots du
    sujet sans casse ni accents), sans base. `close` est compté."""

    def __init__(self, livres=(("The Principles of Product Development Flow", ("flow",)), ("Un article", ("watch",)),
                               ("Autre", ("watch",))), passages=("S le goulot du flux", "S Les équipes et le délai")):
        self.livres, self.passages, self.fermetures, self.erreur = list(livres), list(passages), 0, None

    def books_with_title(self, texte):
        return sum(texte.lower() in titre.lower() for titre, _ in self.livres)

    def books_in_collection(self, nom):
        return sum(nom in collections for _, collections in self.livres)

    def passages_on_topic(self, alternatives):
        if self.erreur:
            raise self.erreur
        self.alternatives = list(alternatives)

        def correspond(passage, alternative):
            texte, expression = alternative
            mots = re.findall(r"\w+", _sans_accents(texte))
            lus = re.findall(r"\w+", _sans_accents(passage))
            if expression:          # mots voisins, dans l'ordre
                return bool(mots) and any(lus[i:i + len(mots)] == mots for i in range(len(lus)))
            return bool(mots) and all(m in lus for m in mots)
        return sum(any(correspond(p, a) for a in alternatives) for p in self.passages)

    def close(self):
        self.fermetures += 1


class Prerequis(unittest.TestCase):
    """Champ `prerequisites` de cas.yaml, lu dans la base de la bibliothèque (lecteur inventé ici ; classe avec base dans
    test_prerequis_base.py) : un cas dont la bibliothèque manque est « non évaluable ici »."""

    def setUp(self):
        self.lecteur = FauxLecteur()

    def manque(self, regles):
        return essai.unmet_prerequisites(regles, reader=self.lecteur)

    def test_sans_prerequis_rien_a_dire_et_aucune_connexion(self):
        with mock.patch.object(essai, "open_library_reader", side_effect=AssertionError("aucune connexion attendue")):
            self.assertEqual(essai.unmet_prerequisites(None), [])
            self.assertEqual(essai.unmet_prerequisites([]), [])

    def test_prerequis_satisfaits(self):
        regles = [{"book": "product development flow"}, {"collection": "watch", "minimum": 2},
                  {"absent_topic": "prototypage"}]
        self.assertEqual(self.manque(regles), [])

    def test_livre_manquant(self):
        raisons = self.manque([{"book": "Inconnu"}])
        self.assertEqual(len(raisons), 1)
        self.assertIn("Inconnu", raisons[0])

    def test_collection_par_nom_exact_et_minimum(self):
        self.assertIn("1", self.manque([{"collection": "flow", "minimum": 5}])[0])
        self.assertIn("0 livre", self.manque([{"collection": "wat"}])[0])           # pas de correspondance partielle

    def test_sujet_present_alors_qu_il_doit_etre_absent(self):
        self.assertIn("présent", self.manque([{"absent_topic": "goulot"}])[0])

    def test_sujet_absent_demande_tous_les_mots_sans_casse_ni_accents(self):
        self.assertIn("présent", self.manque([{"absent_topic": "GOULOT flux"}])[0])
        self.assertIn("présent", self.manque([{"absent_topic": "equipes delai"}])[0])   # accents ignorés
        self.assertEqual(self.manque([{"absent_topic": "goulot prototypage"}]), [])     # un mot manque : absent

    def test_alternatives_or_une_seule_suffit(self):
        self.assertEqual(essai.topic_alternatives('"prototypage génératif" OR "generative prototyping"'),
                         [("prototypage génératif", True), ("generative prototyping", True)])
        self.assertEqual(essai.topic_alternatives("goulot flux"), [("goulot flux", False)])
        self.assertEqual(essai.topic_alternatives("or et argent"), [("or et argent", False)])   # « or » en minuscules : un mot
        self.assertEqual(essai.topic_alternatives('prototypage OR "équipes délai"'),
                         [("prototypage", False), ("équipes délai", True)])
        self.assertIn("présent", self.manque([{"absent_topic": '"prototypage génératif" OR "le goulot"'}])[0])
        self.assertEqual(self.lecteur.alternatives, [("prototypage génératif", True), ("le goulot", True)])
        self.assertIn("présent", self.manque([{"absent_topic": 'prototypage OR "équipes et le délai"'}])[0])
        self.assertEqual(self.manque([{"absent_topic": '"prototypage génératif" OR "generative prototyping"'}]), [])
        self.assertEqual(self.manque([{"absent_topic": '"goulot prototypage" OR "flux generative"'}]), [])   # aucune complète
        self.assertEqual(self.manque([{"absent_topic": '"goulot flux" OR "équipes délai"'}]), [])   # mots présents mais non voisins

    def test_expression_entre_guillemets_mots_voisins_dans_l_ordre(self):
        self.assertIn("présent", self.manque([{"absent_topic": '"le goulot"'}])[0])         # voisins, dans l'ordre
        self.assertEqual(self.manque([{"absent_topic": '"goulot flux"'}]), [])              # mots du passage, pas voisins
        self.assertEqual(self.manque([{"absent_topic": '"flux goulot"'}]), [])              # voisins mais pas dans l'ordre
        self.assertIn("présent", self.manque([{"absent_topic": "goulot flux"}])[0])         # sans guillemets : tous les mots

    def test_sujet_tolere_jusqu_au_maximum(self):
        self.assertEqual(self.manque([{"absent_topic": "goulot", "maximum": 1}]), [])

    def test_base_injoignable(self):
        import db
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("Connexion à la base impossible : refusée.")):
            self.assertEqual(essai.unmet_prerequisites([{"book": "x"}]), ["base de la bibliothèque injoignable"])
        with mock.patch.object(essai, "open_library_reader", side_effect=RuntimeError("secret")):
            self.assertEqual(essai.unmet_prerequisites([{"book": "x"}], dbname="pmzilla_eval_x"),
                             ["base de la bibliothèque injoignable"])

    def test_lecture_sous_le_role_de_lecture_seule_de_la_base_designee(self):
        import db
        for dbname in (None, "pmzilla_eval_inventee"):
            with self.subTest(dbname=dbname), mock.patch.object(db, "connect", return_value=mock.MagicMock()) as connect:
                essai.open_library_reader(dbname)
                connect.assert_called_once_with(role="pmzilla_knowledge_ro", dbname=dbname)

    def test_le_lecteur_ouvert_ici_est_ferme(self):
        with mock.patch.object(essai, "open_library_reader", return_value=self.lecteur) as ouvrir:
            essai.unmet_prerequisites([{"book": "flow"}], dbname="pmzilla_eval_x")
        ouvrir.assert_called_once_with("pmzilla_eval_x")
        self.assertEqual(self.lecteur.fermetures, 1)

    def test_requete_en_echec_non_verifiable_sans_detail(self):
        self.lecteur.erreur = RuntimeError("texte de la base")
        raison = self.manque([{"absent_topic": "goulot"}])[0]
        self.assertIn("non vérifiable (RuntimeError)", raison)
        self.assertNotIn("texte de la base", raison)

    def test_regle_inconnue(self):
        self.assertIn("inconnu", self.manque([{"bizarre": 1}])[0])

    def test_plus_d_index_sqlite(self):
        self.assertFalse(hasattr(essai, "library_db"))
        self.assertFalse(hasattr(essai, "sqlite3"))
        self.assertNotIn("library.sqlite", Path(essai.__file__).read_text(encoding="utf-8"))

    def test_lecteur_reel_compte_et_termine_chaque_transaction(self):
        conn = mock.MagicMock()
        curseur = conn.cursor.return_value.__enter__.return_value
        curseur.fetchone.return_value = (3,)
        lecteur = essai.LibraryReader(conn)
        self.assertEqual(lecteur.passages_on_topic([("équipe délai", False)]), 3)
        sql, parametres = curseur.execute.call_args.args
        self.assertIn("plainto_tsquery('simple', knowledge.immutable_unaccent(%s))", sql)
        self.assertEqual(parametres, ("équipe délai",))
        lecteur.passages_on_topic([("a b", False), ("c", False)])
        sql, parametres = curseur.execute.call_args.args
        self.assertEqual(sql.count("plainto_tsquery"), 2)
        self.assertIn(" || ", sql)
        self.assertEqual(parametres, ("a b", "c"))
        self.assertEqual(lecteur.books_in_collection("watch"), 3)
        self.assertIn("co.name = %s", curseur.execute.call_args.args[0])
        self.assertEqual(lecteur.books_with_title("Flow"), 3)
        self.assertIn("lower(title)", curseur.execute.call_args.args[0])
        self.assertEqual(conn.rollback.call_count, 4)

    def test_requete_expression_exacte_phraseto_tsquery_mots_sans_guillemets(self):
        conn = mock.MagicMock()
        curseur = conn.cursor.return_value.__enter__.return_value
        curseur.fetchone.return_value = (1,)
        lecteur = essai.LibraryReader(conn)
        lecteur.passages_on_topic(essai.topic_alternatives('"a b" OR c d OR "e f"'))
        sql, parametres = curseur.execute.call_args.args
        parties = sql.split(" || ")
        self.assertEqual(len(parties), 3)                   # une partie par alternative
        self.assertIn("phraseto_tsquery('simple', knowledge.immutable_unaccent(%s))", parties[0])
        self.assertIn("plainto_tsquery('simple', knowledge.immutable_unaccent(%s))", parties[1])
        self.assertNotIn("phraseto", parties[1])
        self.assertIn("phraseto_tsquery", parties[2])
        self.assertEqual(parametres, ("a b", "c d", "e f"))   # aucun guillemet transmis
        self.assertNotIn('"', "".join(parametres))

    def test_sujet_du_cas_reel_deux_expressions_exactes(self):
        cas = yaml.safe_load(CAS_REEL.read_text(encoding="utf-8"))
        sujets = [r["absent_topic"] for c in cas for r in c.get("prerequisites") or [] if "absent_topic" in r]
        self.assertIn('"prototypage génératif" OR "generative prototyping"', sujets)
        self.assertEqual(essai.topic_alternatives('"prototypage génératif" OR "generative prototyping"'),
                         [("prototypage génératif", True), ("generative prototyping", True)])
        conn = mock.MagicMock()
        curseur = conn.cursor.return_value.__enter__.return_value
        curseur.fetchone.return_value = (0,)
        essai.LibraryReader(conn).passages_on_topic(essai.topic_alternatives(sujets[sujets.index(
            '"prototypage génératif" OR "generative prototyping"')]))
        self.assertEqual(curseur.execute.call_args.args[0].count("phraseto_tsquery"), 2)

    def test_cas_reels_n_utilisent_que_des_regles_connues(self):
        for cas in yaml.safe_load(CAS_REEL.read_text(encoding="utf-8")):
            for regle in cas.get("prerequisites") or []:
                self.assertTrue({"book", "collection", "absent_topic"} & set(regle), (cas["id"], regle))


class PrerequisSeuls(Base):
    """--prerequisites-only : identifiant et raisons (ou « prérequis satisfaits ») de chaque cas à prérequis ; aucune séance,
    aucun juge, aucune base jetable, aucun rapport ; code de sortie 0 ou 1."""

    CAS = [{"id": "c1", "question": "Q1 ?", "posture": "Delivery", "prerequisites": [{"book": "flow"}]},
           {"id": "c2", "question": "Q2 ?", "posture": "Delivery"},
           {"id": "c3", "question": "Q3 ?", "posture": "Delivery", "prerequisites": [{"book": "Inconnu"}]}]

    def lancer(self, cas, *arguments):
        essai.CASES_FILE.write_text(yaml.safe_dump(cas, allow_unicode=True), encoding="utf-8")
        sortie, self.code = io.StringIO(), 0
        lecteurs = []

        def ouvrir(dbname=None):
            lecteurs.append(dbname)
            return FauxLecteur()

        with mock.patch.object(essai, "open_library_reader", ouvrir), \
                mock.patch.object(essai, "create_cases_database", side_effect=AssertionError("aucune base jetable")), \
                mock.patch.object(essai, "run_session", side_effect=AssertionError("aucune séance")), \
                mock.patch.object(essai, "lock_pass", side_effect=AssertionError("aucun verrou")), \
                mock.patch.object(sys, "argv", ["posture_evals.py", "--prerequisites-only", *arguments]), \
                contextlib.redirect_stdout(sortie):
            try:
                essai.main()
            except SystemExit as fin:
                self.code = fin.code
        self.lecteurs = lecteurs
        return sortie.getvalue()

    def test_un_prerequis_manquant_sort_1(self):
        sortie = self.lancer(self.CAS)
        self.assertEqual(self.code, 1)
        self.assertIn("c1 : prérequis satisfaits", sortie)
        self.assertRegex(sortie, r"c3 : livre absent .*Inconnu")
        self.assertNotIn("c2", sortie)                                          # sans prérequis : pas listé
        self.assertEqual(self.lecteurs, [None, None])                           # la base de l'installation
        self.assertEqual(self.commandes, [])                                    # ni séance ni juge
        self.assertFalse(essai.REPORT_DIR.exists() and any(essai.REPORT_DIR.iterdir()))
        self.assertFalse(essai.DATA.exists() and any(essai.DATA.iterdir()))

    def test_tout_satisfait_sort_0(self):
        sortie = self.lancer(self.CAS[:2])
        self.assertEqual(self.code, 0)
        self.assertEqual(sortie.strip(), "c1 : prérequis satisfaits")

    def test_selection_de_cas(self):
        sortie = self.lancer(self.CAS, "--cases", "c3")
        self.assertEqual(self.code, 1)
        self.assertNotIn("c1", sortie)


class SanctumsEtContexte(unittest.TestCase):
    """prepare_memory : sanctums créés dans la copie, vécu neutre, contexte neutre (jamais le contexte personnel)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.copie = Path(self.temp.name)
        racine = Path(__file__).resolve().parents[2]
        shutil.copytree(racine / ".claude" / "skills", self.copie / ".claude" / "skills",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(racine / "tests" / "postures", self.copie / "tests" / "postures")

    def tearDown(self):
        self.temp.cleanup()

    def test_sanctums_crees_figes_et_contexte_neutre_depose(self):
        placed = essai.prepare_memory(self.copie, real=False)
        for posture in ("delivery", "discovery", "scaling", "facilitation"):
            sanctum = self.copie / "_bmad" / "memory" / f"pmzilla-{posture}-bmad"
            self.assertTrue((sanctum / "CREED.md").is_file(), posture)
            neutre = (self.copie / "tests" / "postures" / "memoire" / posture / "MEMORY.md").read_text(encoding="utf-8")
            self.assertEqual((sanctum / "MEMORY.md").read_text(encoding="utf-8"), neutre)
            self.assertFalse((sanctum / "sessions").exists())
        contexte = self.copie / ".pmzilla" / "contexte.md"
        self.assertEqual(contexte.read_text(encoding="utf-8"),
                         (self.copie / "tests" / "postures" / "contexte-neutre.md").read_text(encoding="utf-8"))
        self.assertIn(".pmzilla/contexte.md", placed)

    def test_contexte_neutre_manquant_est_une_erreur(self):
        (self.copie / "tests" / "postures" / "contexte-neutre.md").unlink()
        with mock.patch.object(essai, "WORKSPACE", self.copie / "autre"), self.assertRaises(SystemExit):
            essai.prepare_memory(self.copie, real=False)


class FormulesDeLAutreLangue(unittest.TestCase):
    """Indicateur non bloquant : aucune formule fixe de l'autre langue dans la réponse finale."""

    def trace(self, texte: str) -> dict:
        return {"answer": texte, "all_text": texte}

    def test_reponse_francaise_avec_formules_francaises(self):
        verdict = essai.check_language_formulas(self.trace("[Posture : Delivery]\nJ'en déduis que c'est hors bibliothèque. Hypothèse : le WIP."), "fr")
        self.assertTrue(verdict["ok"])
        self.assertTrue(verdict["indicateur"])

    def test_reponse_francaise_avec_une_formule_anglaise(self):
        verdict = essai.check_language_formulas(self.trace("C'est outside the library. I infer que le WIP pèse."), "fr")
        self.assertFalse(verdict["ok"])
        self.assertIn("outside the library", verdict["justification"])
        self.assertIn("i infer", verdict["justification"].lower())

    def test_reponse_anglaise_avec_une_formule_francaise_et_apostrophe_typographique(self):
        verdict = essai.check_language_formulas(self.trace("This is hors bibliothèque. J\u2019en déduis that WIP is high."), "en")
        self.assertFalse(verdict["ok"])
        self.assertIn("hors bibliothèque", verdict["justification"])

    def test_reponse_anglaise_propre(self):
        self.assertTrue(essai.check_language_formulas(self.trace("I infer that WIP is high. Hypothesis: queues. Outside the library."), "en")["ok"])

    def test_un_indicateur_ne_compte_ni_dans_le_total_ni_dans_les_regressions(self):
        verdict = essai.check_language_formulas(self.trace("I infer"), "fr")
        self.assertEqual(essai.blocking([verdict]), [])
        self.assertEqual(essai.indicators([verdict]), [verdict])


class CasDeCommandes(Base):
    """Cas à fichiers inventés (`files`) et à bibliothèque jetable (`library`) : tests/postures/cas-commandes.yaml."""
    RACINE = Path(__file__).resolve().parents[2]
    CAS_COMMANDES = RACINE / "tests" / "postures" / "cas-commandes.yaml"

    def test_place_files_copie_dans_la_copie_seulement(self):
        racine = self.tmp / "workspace"
        (racine / "fx").mkdir(parents=True)
        (racine / "fx" / "a.md").write_text("inventé", encoding="utf-8")
        copie = self.tmp / "copie"
        copie.mkdir()
        essai.place_files({"files": [{"from": "fx/a.md", "to": "Flux-Lab/rapports/a.md"}]}, copie)
        self.assertEqual((copie / "Flux-Lab" / "rapports" / "a.md").read_text(encoding="utf-8"), "inventé")
        with self.assertRaises(ValueError):
            essai.place_files({"files": [{"from": "fx/a.md", "to": "../dehors.md"}]}, copie)
        essai.place_files({}, copie)          # sans `files` : rien à faire

    def bibliotheque(self, base="pmzilla_eval_inventee", **options):
        """case_library avec le vidage enregistré dans self.vidages ; les options de subprocess.run dans self.options."""
        self.vidages, self.options = [], []
        reel = essai.subprocess.run

        def run(commande, **opts):
            self.options.append(opts)
            return reel(commande, **opts)

        with mock.patch.object(essai, "reset_case_library", lambda nom: self.vidages.append(nom)), \
                mock.patch.object(essai.subprocess, "run", run):
            return essai.case_library({"id": "c", "library": "fx/collections"}, self.tmp, dbname=base, **options)

    def test_case_library_vide_puis_indexe_dans_la_base_jetable(self):
        self.assertIsNone(essai.case_library({"id": "c"}, self.tmp))
        config = self.bibliotheque()
        self.assertEqual(self.vidages, ["pmzilla_eval_inventee"])
        commande = self.commandes[0]
        self.assertEqual(commande[-3:], [str(essai.TOOLS / "pmzilla_lab_library.py"), "index",
                                         str(self.tmp / "workspace" / "fx" / "collections")])
        self.assertEqual(self.options[0]["env"]["PMZILLA_LAB_KNOWLEDGE_DBNAME"], "pmzilla_eval_inventee")
        serveur = json.loads(config.read_text(encoding="utf-8"))["mcpServers"]["pmzilla-library"]
        self.assertEqual(serveur["env"], {"PMZILLA_LAB_KNOWLEDGE_DBNAME": "pmzilla_eval_inventee"})
        self.assertNotIn("--backend", serveur["args"])
        self.assertNotEqual(config.name, "mcp.json")         # la configuration de l'installation n'est pas écrasée

    def test_case_library_sans_base_jetable_n_indexe_rien(self):
        with self.assertRaises(essai.LibraryUnavailable) as erreur:
            self.bibliotheque(base=None)
        self.assertEqual(str(erreur.exception), "throwaway library unavailable")
        self.assertEqual((self.vidages, self.commandes), ([], []))

    def test_case_library_indexation_en_echec(self):
        for code in (1, 2):
            with self.subTest(code=code):
                self.commandes.clear()
                self.reponses.append(self.termine("", code, "Database unreachable: nothing was indexed."))
                with self.assertRaises(essai.LibraryUnavailable) as erreur:
                    self.bibliotheque()
                self.assertIn(f"throwaway library unavailable : indexation en échec (code {code})", str(erreur.exception))
                self.assertIn("Database unreachable", str(erreur.exception))

    def test_mcp_config_sans_index_jetable_garde_l_installation(self):
        serveur = json.loads(essai.mcp_config(self.tmp).read_text(encoding="utf-8"))["mcpServers"]["pmzilla-library"]
        self.assertNotIn("env", serveur)

    def test_cas_commandes_sont_complets_et_hors_du_total_de_cas_yaml(self):
        cas = essai.normalize_cases(yaml.safe_load(self.CAS_COMMANDES.read_text(encoding="utf-8")))
        self.assertEqual([c["id"] for c in cas], ["cmd-monthly-flow", "cmd-watch-digest"])
        for c in cas:
            for item in c.get("files") or []:
                self.assertTrue((self.RACINE / item["from"]).is_file(), item["from"])
            if c.get("library"):
                collections = self.RACINE / c["library"]
                self.assertTrue(any(collections.glob("*/*.md")), c["library"])
        ids_reels = {c["id"] for c in yaml.safe_load(CAS_REEL.read_text(encoding="utf-8"))}
        self.assertFalse(ids_reels & {c["id"] for c in cas})


class PassageAvecBibliothequeJetable(Base):
    """main() sur un cas `library:` : la bibliothèque jetable est indexée dans la base jetable du passage, ses prérequis y sont lus,
    sa séance lit cette base ; sans base jetable, le cas est non évaluable et rien n'est indexé. Séances et indexeur simulés."""

    CAS = [{"id": "lib", "question": "Question lib ?", "posture": "Delivery", "library": "fx/collections",
            "prerequisites": [{"book": "flow"}]},
           {"id": "std", "question": "Question std ?", "posture": "Delivery", "prerequisites": [{"book": "flow"}]}]

    def setUp(self):
        super().setUp()
        self.seances, self.vidages, self.lecteurs = [], [], []

        def seance(question, copie, mcp, model, trace, *a, **k):
            self.seances.append((question, Path(mcp)))
            return [assistant(texte("[Posture : Delivery] réponse")), fin("[Posture : Delivery] réponse")]

        def ouvrir(dbname=None):
            self.lecteurs.append(dbname)
            return FauxLecteur()

        for patch in (mock.patch.object(essai, "git", lambda *a, **k: ""),
                      mock.patch.object(essai, "make_copy", lambda *a, **k: None),
                      mock.patch.object(essai, "prepare_memory", lambda *a, **k: {}),
                      mock.patch.object(essai, "drop_copy"),
                      mock.patch.object(essai, "run_session", seance),
                      mock.patch.object(essai, "open_library_reader", ouvrir),
                      mock.patch.object(essai, "reset_cases_database", lambda *a: None),
                      mock.patch.object(essai, "drop_cases_database", lambda *a: None),
                      mock.patch.object(essai, "reset_case_library", lambda nom: self.vidages.append(nom))):
            patch.start()
            self.addCleanup(patch.stop)
        essai.CASES_FILE.write_text(yaml.safe_dump(self.CAS, allow_unicode=True), encoding="utf-8")

    def lancer(self, base_jetable):
        sortie, self.code = io.StringIO(), 0
        with mock.patch.object(essai, "create_cases_database", lambda: base_jetable), \
                mock.patch.object(sys, "argv", ["posture_evals.py", "--retries", "0"]), contextlib.redirect_stdout(sortie):
            try:
                essai.main()
            except SystemExit as fin_passage:
                self.code = fin_passage.code
        return {c["id"]: c for c in json.loads(max(essai.DATA.glob("*/resultats.json")).read_text(encoding="utf-8"))["cas"]}

    def test_sans_base_jetable_le_cas_est_non_evaluable_et_rien_n_est_indexe(self):
        resultats = self.lancer(None)
        self.assertEqual(resultats["lib"]["non_evaluable"], ["throwaway library unavailable"])
        self.assertNotIn("non_evaluable", resultats["std"])
        self.assertEqual([q for q, _ in self.seances], ["Question std ?"])
        self.assertFalse(any("index" in commande for commande in self.commandes))
        self.assertEqual(self.vidages, [])
        self.assertEqual(self.lecteurs, [None])                                   # le cas standard lit la base de l'installation
        self.assertEqual(self.code, essai.EXIT_NOT_VALIDATING)

    def test_avec_base_jetable_indexation_prerequis_et_seance_sur_cette_base(self):
        resultats = self.lancer("pmzilla_eval_inventee")
        self.assertNotIn("non_evaluable", resultats["lib"])
        self.assertEqual(self.vidages, ["pmzilla_eval_inventee"])
        index = [c for c in self.commandes if "index" in c]
        self.assertEqual(len(index), 1)
        self.assertEqual(index[0][-1], str(essai.WORKSPACE / "fx" / "collections"))
        self.assertEqual(self.lecteurs, ["pmzilla_eval_inventee", None])          # prérequis du cas lib : la base jetable
        mcp = dict(self.seances)
        serveur = json.loads(mcp["Question lib ?"].read_text(encoding="utf-8"))["mcpServers"]["pmzilla-library"]
        self.assertNotIn("--backend", serveur["args"])
        self.assertEqual(serveur["env"]["PMZILLA_LAB_KNOWLEDGE_DBNAME"], "pmzilla_eval_inventee")
        self.assertNotIn("PMZILLA_LAB_DATA", serveur["env"])
        standard = json.loads(mcp["Question std ?"].read_text(encoding="utf-8"))["mcpServers"]["pmzilla-library"]
        self.assertNotIn("PMZILLA_LAB_KNOWLEDGE_DBNAME", standard.get("env", {}))
        self.assertEqual(mcp["Question std ?"].name, "mcp.json")

    def test_indexation_en_echec_rend_le_cas_non_evaluable(self):
        self.reponses.append(self.termine("", 2, "Database unreachable: nothing was indexed."))
        resultats = self.lancer("pmzilla_eval_inventee")
        self.assertIn("indexation en échec (code 2)", resultats["lib"]["non_evaluable"][0])
        self.assertEqual([q for q, _ in self.seances], ["Question std ?"])


class ChoixDuModele(Base):
    """--model (séances) et --judge-model (juge) : enregistrés dans le résultat, l'en-tête du rapport et le tableau de bord ;
    un modèle de séances autre que l'habituel rend le passage non validant ; --rejudge accepte --judge-model ;
    --compare liste les verdicts qui diffèrent (2026-10-09). Séances simulées : aucun modèle appelé."""

    JUGE = {"result": json.dumps({"jugements": [{"critere": "Critère un", "justification": "Oui.", "ok": True}]})}

    def setUp(self):
        super().setUp()
        self.modeles_seances: list = []
        self.cas = [{"id": "c1", "question": "Question 1 ?", "posture": "Delivery", "judgements": ["Critère un"]}]
        for patch in (mock.patch.object(essai, "git", lambda *a, **k: ""),
                      mock.patch.object(essai, "make_copy", lambda *a, **k: None),
                      mock.patch.object(essai, "prepare_memory", lambda *a, **k: {}),
                      mock.patch.object(essai, "drop_copy"),
                      mock.patch.object(essai, "run_session", self.fausse_seance)):
            patch.start()
            self.addCleanup(patch.stop)

    def fausse_seance(self, question, copie, mcp, model, trace, *a, **k):
        self.modeles_seances.append(model)
        return [assistant(texte("[Posture : Delivery] réponse")), fin("[Posture : Delivery] réponse", cout=0.10)]

    def lancer(self, *arguments) -> str:
        essai.CASES_FILE.write_text(yaml.safe_dump(self.cas, allow_unicode=True), encoding="utf-8")
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["posture_evals.py", *arguments]), contextlib.redirect_stdout(sortie):
            essai.main()
        return sortie.getvalue()

    def dernier(self) -> dict:
        return json.loads(max(essai.DATA.glob("*/resultats.json")).read_text(encoding="utf-8"))

    def rapport(self) -> str:
        return max(essai.REPORT_DIR.glob("essai-*.md")).read_text(encoding="utf-8")

    def test_passage_habituel_est_validant_et_le_rapport_nomme_les_modeles_par_defaut(self):
        self.reponses.append(self.termine(json.dumps(self.JUGE)))
        self.lancer()
        self.assertEqual(self.modeles_seances, [None])
        resultats = self.dernier()
        self.assertEqual((resultats["modele_sessions"], resultats["modele_juge"], resultats["validant"]), (None, "sonnet", True))
        self.assertEqual(self.commandes[0][-2:], ["--model", essai.DEFAULT_JUDGE_MODEL])   # juge par défaut : sonnet (calibration du 2026-10-09)
        rapport = self.rapport()
        self.assertIn("modèles : sessions défaut · juge sonnet", rapport)
        self.assertNotIn("non validant", rapport)

    def test_modele_des_seances_et_du_juge_transmis_enregistres_et_passage_non_validant(self):
        self.reponses.append(self.termine(json.dumps(self.JUGE)))
        self.lancer("--model", "sonnet", "--judge-model", "opus")
        self.assertEqual(self.modeles_seances, ["sonnet"])
        self.assertEqual(self.commandes[0][-2:], ["--model", "opus"])          # le juge
        resultats = self.dernier()
        self.assertEqual((resultats["modele_sessions"], resultats["modele_juge"], resultats["validant"]),
                         ("sonnet", "opus", False))
        rapport = self.rapport()
        self.assertIn("modèles : sessions sonnet · juge opus", rapport)
        self.assertIn("**Passage non validant**", rapport)

    def test_juge_different_seul_laisse_le_passage_validant(self):
        self.reponses.append(self.termine(json.dumps(self.JUGE)))
        self.lancer("--judge-model", "opus")
        self.assertTrue(self.dernier()["validant"])
        self.assertIn("modèles : sessions défaut · juge opus", self.rapport())

    def test_un_passage_non_validant_n_est_jamais_la_reference(self):
        def passage(nom, ok, **extra):
            dossier = essai.DATA / nom
            dossier.mkdir(parents=True)
            (dossier / "resultats.json").write_text(json.dumps(
                {"cas": [{"id": "c1", "statut": "reussi" if ok else "instable",
                          "verifications": [{"critere": "X", "ok": ok}]}], "complet": True, **extra}), encoding="utf-8")
        passage("2026-10-01-100000", True)
        passage("2026-10-02-100000", False, modele_sessions="sonnet", validant=False)
        courant = essai.DATA / "2026-10-03-100000"
        self.assertEqual(essai.previous_results(courant), {("c1", "X"): True})      # le non validant, plus récent, est ignoré
        self.assertEqual(essai.previous_statuses(courant), {"c1": "reussi"})

    def test_rejuger_avec_un_autre_juge_garde_les_modeles_des_seances_et_le_statut(self):
        source = essai.DATA / "2026-10-01-090000"
        source.mkdir(parents=True)
        (source / "c1.jsonl").write_text("\n".join(json.dumps(e) for e in SEANCE), encoding="utf-8")
        (source / "resultats.json").write_text(json.dumps(
            {"base": "basebase12", "cas": [], "modele_sessions": "sonnet", "modele_juge": None, "validant": False}), encoding="utf-8")
        self.reponses.append(self.termine(json.dumps(self.JUGE)))
        self.lancer("--rejudge", "2026-10-01-090000", "--judge-model", "sonnet")
        self.assertEqual(self.modeles_seances, [])                              # aucune séance
        self.assertEqual(self.commandes[0][-2:], ["--model", "sonnet"])
        nouveau = self.dernier_apres(source)
        self.assertEqual((nouveau["modele_sessions"], nouveau["modele_juge"], nouveau["validant"], nouveau["rejuge"]),
                         ("sonnet", "sonnet", False, True))
        rapport = self.rapport()
        self.assertIn("modèles : sessions sonnet · juge sonnet", rapport)
        self.assertIn("**Passage non validant**", rapport)

    def dernier_apres(self, source: Path) -> dict:
        autres = [d for d in essai.DATA.iterdir() if d != source]
        return json.loads((autres[0] / "resultats.json").read_text(encoding="utf-8"))

    def test_rejuger_refuse_model(self):
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("--rejudge", "2026-10-01-090000", "--model", "sonnet")
        self.assertIn("--model ne s'applique pas à --rejudge", str(erreur.exception))

    def passage_de_verdicts(self, nom: str, verdicts: dict, juge=None) -> None:
        dossier = essai.DATA / nom
        dossier.mkdir(parents=True)
        (dossier / "resultats.json").write_text(json.dumps({"modele_juge": juge, "cas": [
            {"id": cas, "verifications": [{"critere": c, "ok": ok, "justification": "TEXTE_DE_JUSTIFICATION",
                                           **({"indicateur": True} if c.startswith("Ind") else {})}
                                          for c, ok in checks.items()]} for cas, checks in verdicts.items()]}), encoding="utf-8")

    def test_comparaison_liste_seulement_les_verdicts_qui_different(self):
        self.passage_de_verdicts("2026-10-01-100000", {"c1": {"Critère un": True, "Critère deux": True, "Ind non bloquant": True},
                                                       "c2": {"Critère trois": True}})
        self.passage_de_verdicts("2026-10-02-100000", {"c1": {"Critère un": True, "Critère deux": False, "Ind non bloquant": False},
                                                       "c2": {"Critère trois": True, "Critère quatre": True}}, juge="sonnet")
        sortie = self.lancer("--compare", "2026-10-01-100000", "2026-10-02-100000")
        self.assertIn("B : 2026-10-02-100000 · modèles sessions défaut, juge sonnet", sortie)
        self.assertIn("3 verdict(s) différent(s)", sortie)
        self.assertIn("- c1 · Critère deux · bloquante · A réussi · B échec", sortie)
        self.assertIn("- c1 · Ind non bloquant · non bloquante · A réussi · B échec", sortie)
        self.assertIn("- c2 · Critère quatre · bloquante · A — · B réussi", sortie)
        self.assertNotIn("Critère un ·", sortie)                               # verdict identique : absent
        self.assertNotIn("TEXTE_DE_JUSTIFICATION", sortie)                     # ni justification ni réponse
        self.assertEqual(self.commandes, [])                                   # aucun appel de modèle

    def test_comparaison_d_un_passage_introuvable(self):
        with self.assertRaises(SystemExit) as erreur:
            self.lancer("--compare", "1999-01-01-000000", "1999-01-02-000000")
        self.assertIn("Passage introuvable", str(erreur.exception))


class AgentSpecWriter(unittest.TestCase):
    def test_l_agent_est_fixe_sur_opus_meme_appele_depuis_une_session_sonnet(self):
        texte = (RACINE_DEPOT / ".claude" / "agents" / "spec-writer.md").read_text(encoding="utf-8")
        entete = texte.split("---")[1]
        self.assertEqual(re.findall(r"(?m)^model:\s*(\S+)\s*$", entete), ["opus"])


if __name__ == "__main__":
    unittest.main()
