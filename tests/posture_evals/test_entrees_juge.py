"""
Garde permanente : les entrées du juge ne changent pas sans qu'on l'ait voulu.

    uv run --with pyyaml python -m unittest discover -s tests/posture_evals -v

À chaque lot, ce test compare ce que le juge reçoit (le prompt français et, pour chaque cas, la question, la posture, les
vérifications dont les motifs de texte, les prérequis et les critères jugés, après contrôle des clés : une ancienne clé est refusée) à l'état de
référence : par défaut le dernier état poussé (`origin/main`). Si rien n'a changé là où une séance et le juge lisent, un
échec isolé d'un cas de la piste « Cas instables » est une variation du modèle, acceptée sans rejeu
(plan de la version anglaise, section 6.2). Un lot qui change volontairement ces entrées (4, 6 et 7) lance les tests avec
PMZILLA_ENTREES_JUGE_CHANGEES=1 : le test est alors ignoré, et l'on traite d'abord la piste « Cas instables ».

La référence se change avec PMZILLA_JUGE_REFERENCE (une référence Git). Sans dépôt Git ni référence, le test est ignoré.
Aucun appel réseau : `git show` lit les objets locaux.
"""
import ast
import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import posture_evals as essai  # noqa: E402

REFERENCE = os.environ.get("PMZILLA_JUGE_REFERENCE", "origin/main")
CHANGEES = os.environ.get("PMZILLA_ENTREES_JUGE_CHANGEES") == "1"
HARNAIS = ("tools/posture_evals.py",)
CHAMPS = ("question", "posture", "verifications", "prerequisites", "judgements")


def lire_reference(chemin: str, reference: str = REFERENCE) -> str | None:
    fait = subprocess.run(["git", "show", f"{reference}:{chemin}"], cwd=RACINE, capture_output=True, text=True)
    return fait.stdout if fait.returncode == 0 else None


def prompt_francais(source: str) -> str | None:
    """Le texte du prompt français du juge dans le source d'un harnais (JUDGE_PROMPT_FR, ou JUDGE_PROMPT avant le lot 2),
    lu sans exécuter le fichier."""
    for noeud in ast.parse(source).body:
        if isinstance(noeud, ast.Assign) and len(noeud.targets) == 1 and isinstance(noeud.targets[0], ast.Name) \
                and noeud.targets[0].id in ("JUDGE_PROMPT_FR", "JUDGE_PROMPT") \
                and isinstance(noeud.value, ast.Constant) and isinstance(noeud.value.value, str):
            return noeud.value.value
    return None


def cas_normalises(texte: str) -> dict[str, dict]:
    cas = essai.normalize_cases(yaml.safe_load(texte))      # refuse une ancienne clé (arrêt, code 2)
    return {c["id"]: c for c in cas}


def differences(reference: dict[str, dict], actuel: dict[str, dict]) -> list[str]:
    """Écarts sur les cas de la référence ; les cas ajoutés depuis ne comptent pas."""
    ecarts = []
    for ident, ancien in reference.items():
        if ident not in actuel:
            ecarts.append(f"{ident} : cas supprimé")
            continue
        for champ in CHAMPS:
            if ancien.get(champ) != actuel[ident].get(champ):
                ecarts.append(f"{ident} : {champ} modifié")
    return ecarts


@unittest.skipIf(CHANGEES, "PMZILLA_ENTREES_JUGE_CHANGEES=1 : entrées du juge NON comparées (lot qui les change volontairement) ; "
                      "le message du commit doit le dire")
class EntreesDuJugeIdentiquesALaReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cas_reference = lire_reference("tests/postures/cas.yaml")
        cls.harnais_reference = next((s for s in map(lire_reference, HARNAIS) if s), None)
        if cls.cas_reference is None or cls.harnais_reference is None:
            raise unittest.SkipTest(f"référence {REFERENCE} introuvable (pas de dépôt Git, ou jamais poussé)")

    def test_prompt_francais_du_juge_identique(self):
        ancien = prompt_francais(self.harnais_reference)
        self.assertIsNotNone(ancien, "prompt du juge introuvable dans la référence")
        self.assertEqual(essai.JUDGE_PROMPT_FR, ancien, f"le prompt français du juge diffère de {REFERENCE}")

    def test_entrees_de_chaque_cas_identiques(self):
        actuel = cas_normalises((RACINE / "tests" / "postures" / "cas.yaml").read_text(encoding="utf-8"))
        self.assertEqual(differences(cas_normalises(self.cas_reference), actuel), [],
                         f"des entrées du juge diffèrent de {REFERENCE}")

    def test_veille_goulot_question_jugements_et_textes_identiques(self):
        ancien = cas_normalises(self.cas_reference)["veille-goulot"]
        actuel = cas_normalises((RACINE / "tests" / "postures" / "cas.yaml").read_text(encoding="utf-8"))["veille-goulot"]
        self.assertEqual(actuel["question"], ancien["question"])
        self.assertEqual(actuel["judgements"], ancien["judgements"])
        self.assertEqual(actuel["verifications"], ancien["verifications"])


class OutilDeComparaison(unittest.TestCase):
    """Le comparateur lui-même, sur des cas inventés : un écart doit être vu, une clé renommée non."""

    def test_anciennes_cles_sont_refusees_et_non_comparees(self):
        vieux = "- id: c1\n  question: Q ?\n  verifications:\n    - outil: search_library\n    - texte: abc\n  jugements:\n    - J\n"
        neuf = "- id: c1\n  question: Q ?\n  verifications:\n    - tool: search_library\n    - text: abc\n  judgements:\n    - J\n"
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
            cas_normalises(vieux)
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("c1", erreur.getvalue())
        self.assertIn("« judgements »", erreur.getvalue())
        self.assertEqual(differences(cas_normalises(neuf), cas_normalises(neuf)), [])

    def test_un_critere_modifie_est_vu(self):
        a = cas_normalises("- id: c1\n  question: Q ?\n  judgements:\n    - J\n")
        b = cas_normalises("- id: c1\n  question: Q ?\n  judgements:\n    - J modifié\n")
        self.assertEqual(differences(a, b), ["c1 : judgements modifié"])

    def test_une_question_un_motif_ou_un_cas_supprime_sont_vus(self):
        a = cas_normalises("- id: c1\n  question: Q ?\n  verifications:\n    - text: a\n- id: c2\n  question: R ?\n")
        b = cas_normalises("- id: c1\n  question: Q ?!\n  verifications:\n    - text: b\n")
        self.assertEqual(sorted(differences(a, b)), ["c1 : question modifié", "c1 : verifications modifié", "c2 : cas supprimé"])

    def test_un_cas_ajoute_ou_un_bloc_en_ne_comptent_pas(self):
        a = cas_normalises("- id: c1\n  question: Q ?\n")
        b = cas_normalises("- id: c1\n  question: Q ?\n  en:\n    question: Q?\n- id: c3\n  question: S ?\n")
        self.assertEqual(differences(a, b), [])

    def test_prompt_lu_sans_executer_le_fichier(self):
        self.assertEqual(prompt_francais('JUDGE_PROMPT = """un prompt"""\n'), "un prompt")
        self.assertEqual(prompt_francais('JUDGE_PROMPT_FR = """nouveau"""\nJUDGE_PROMPT = JUDGE_PROMPT_FR\n'), "nouveau")
        self.assertIsNone(prompt_francais("X = 1\n"))

    def test_le_test_ignore_nomme_la_variable_et_le_message_de_commit(self):
        raison = getattr(EntreesDuJugeIdentiquesALaReference, "__unittest_skip_why__", None)
        if not CHANGEES:
            self.assertIsNone(raison)            # sans la variable, rien n'est ignoré
        else:
            self.assertIn("PMZILLA_ENTREES_JUGE_CHANGEES=1", raison)
            self.assertIn("le message du commit doit le dire", raison)

    def test_la_reference_par_defaut_est_le_dernier_etat_pousse(self):
        self.assertEqual(REFERENCE, os.environ.get("PMZILLA_JUGE_REFERENCE", "origin/main"))


if __name__ == "__main__":
    unittest.main()
