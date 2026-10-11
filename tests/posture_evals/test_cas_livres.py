"""
Les trois cas livrés du module de cas (db-lot2, groupe 13, design.md 7.3) : jeux d'essai inventés, un seul critère bloquant par cas,
indicateurs non bloquants, bloc `en` complet, aucune date de revue échue.

    bash tests/run_all.sh posture_evals

Aucune base, aucun appel payant : les fixtures sont validées avec les fonctions de lecture de `cases_store` (sans connexion).
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import posture_evals as essai  # noqa: E402
import cases_store  # noqa: E402

CAS_YAML = RACINE / "tests" / "postures" / "cas.yaml"
DOSSIER = RACINE / "tests" / "postures" / "cases"
NOUVEAUX = {
    "cas-proche-reussi": ("cas-proche-reussi.yaml", "cas-proche-reussi.en.yaml"),
    "cas-proche-echoue": ("cas-proche-echoue.yaml", "cas-proche-echoue.en.yaml"),
    "experimentation-en-cours": ("experimentation-en-cours.yaml", "experimentation-en-cours.en.yaml"),
}
FIN_2027 = dt.date(2027, 12, 31)


def cas_livres():
    return {c["id"]: c for c in yaml.safe_load(CAS_YAML.read_text(encoding="utf-8"))}


def lire(nom):
    return yaml.safe_load((DOSSIER / nom).read_text(encoding="utf-8")) or {}


def compte_bloquant(cas):
    total = 1 if cas.get("posture") is not None else 0
    total += sum(1 for r in cas.get("verifications") or [] if not r.get("non_blocking"))
    total += sum(1 for j in cas.get("judgements") or [] if not (isinstance(j, dict) and j.get("non_blocking")))
    return total


def compte_indicateurs(cas):
    total = sum(1 for r in cas.get("verifications") or [] if r.get("non_blocking"))
    total += sum(1 for j in cas.get("judgements") or [] if isinstance(j, dict) and j.get("non_blocking"))
    return total


class CasLivres(unittest.TestCase):
    def test_treize_cas_et_trente_huit_verifications_bloquantes(self):
        cas = yaml.safe_load(CAS_YAML.read_text(encoding="utf-8"))
        self.assertEqual(len(cas), 13)
        self.assertEqual(sum(compte_bloquant(c) for c in cas), 38)

    def test_six_indicateurs_de_plus_qu_avant(self):
        tous = cas_livres()
        self.assertEqual(sum(compte_indicateurs(tous[i]) for i in NOUVEAUX), 6)

    def test_criteres_bloquants_sans_posture_par_nouveau_cas(self):
        """Un critère bloquant par nouveau cas, deux pour experimentation-en-cours (mention et note ; pas d'avis sur le chemin)."""
        tous = cas_livres()
        for ident in NOUVEAUX:
            cas = tous[ident]
            with self.subTest(cas=ident):
                self.assertNotIn("posture", cas)
                self.assertEqual(compte_bloquant(cas), 2 if ident == "experimentation-en-cours" else 1)
                self.assertEqual(compte_indicateurs(cas), 2)
                self.assertNotIn("critic", yaml.safe_dump(cas))

    def test_questions_de_design(self):
        tous = cas_livres()
        self.assertEqual(tous["cas-proche-reussi"]["question"],
                         "Dans mon équipe, les parties prenantes ne viennent plus aux revues de sprint. Comment je m'y prends ?")
        self.assertEqual(tous["cas-proche-echoue"]["question"],
                         "Je veux imposer une limite de WIP à une équipe qui a trop de travail en cours. Bonne idée ?")
        self.assertEqual(tous["experimentation-en-cours"]["question"],
                         "Les refinements de mon équipe s'éternisent sans décision. Tu me proposes une expérimentation ?")

    def test_outils_verifies(self):
        tous = cas_livres()
        attendu = {"cas-proche-reussi": "search_cases", "cas-proche-echoue": "search_cases",
                   "experimentation-en-cours": "search_experiments"}
        for ident, outil in attendu.items():
            regles = tous[ident]["verifications"]
            self.assertEqual(regles, [{"tool": outil, "non_blocking": True}], ident)

    def test_variante_en_complete_avec_sa_fixture(self):
        tous = cas_livres()
        for ident, (fr, en) in NOUVEAUX.items():
            cas = tous[ident]
            variante = essai.case_for_language(cas, "en")
            with self.subTest(cas=ident):
                self.assertEqual(cas["cases_fixture"], f"tests/postures/cases/{fr}")
                self.assertEqual(variante["cases_fixture"], f"tests/postures/cases/{en}")
                self.assertNotEqual(variante["question"], cas["question"])
                self.assertEqual([type(j) for j in variante["judgements"]], [type(j) for j in cas["judgements"]])
                self.assertEqual(compte_bloquant(variante), compte_bloquant(cas))
                self.assertEqual(compte_indicateurs(variante), compte_indicateurs(cas))
                texte = yaml.safe_dump(cas["en"], allow_unicode=True)
                for formule in ("J'en déduis", "Hypothèse", "hors bibliothèque", "Cas n°"):
                    self.assertNotIn(formule, texte)
        essai.check_fixtures([cas for cas in tous.values()])      # existence et dossier


class FixturesLivrees(unittest.TestCase):
    def fichiers(self):
        return [nom for paire in NOUVEAUX.values() for nom in paire]

    def test_fixtures_valides_comme_le_chargeur_les_lit(self):
        for nom in self.fichiers():
            data = lire(nom)
            with self.subTest(fixture=nom):
                self.assertLessEqual(set(data), {"experiments", "cases"})
                for brut in data.get("experiments") or []:
                    cases_store._fixture_experiment(brut)
                for brut in data.get("cases") or []:
                    cases_store._fixture_case(brut)

    def test_toute_experimentation_en_cours_est_a_revoir_apres_fin_2027(self):
        vues = 0
        for nom in sorted(p.name for p in DOSSIER.glob("*.yaml")):
            for brut in lire(nom).get("experiments") or []:
                if brut.get("status", "running") != "running":
                    continue
                vues += 1
                with self.subTest(fixture=nom):
                    self.assertGreater(cases_store._fixture_experiment(brut)["review_due"], FIN_2027)
        self.assertEqual(vues, 2)           # une par version de la fixture experimentation-en-cours

    def test_contenu_des_fixtures_de_design_7_3(self):
        for en in (False, True):
            i = 1 if en else 0
            reussi = lire(NOUVEAUX["cas-proche-reussi"][i])
            self.assertEqual([c["outcome"] for c in reussi["cases"]], ["worked", "partly"])
            self.assertEqual(reussi["cases"][0]["confidence"], "medium")
            self.assertFalse(reussi.get("experiments"))
            echoue = lire(NOUVEAUX["cas-proche-echoue"][i])
            self.assertEqual([c["outcome"] for c in echoue["cases"]], ["failed"])
            self.assertTrue(echoue["cases"][0]["what_got_stuck"])
            encours = lire(NOUVEAUX["experimentation-en-cours"][i])
            self.assertEqual(len(encours["experiments"]), 1)
            self.assertEqual(encours["experiments"][0]["status"], "running")
            self.assertFalse(encours.get("cases"))

    def test_contenu_invente_seulement(self):
        for nom in self.fichiers():
            brut = (DOSSIER / nom).read_text(encoding="utf-8")
            data = lire(nom)
            with self.subTest(fixture=nom):
                for entree in (data.get("experiments") or []) + (data.get("cases") or []):
                    self.assertIn(entree["author"], ("agile-lead-test", "agile-lead-b"))
                self.assertNotRegex(brut, r"\b[A-Z][A-Z0-9]+-\d+\b")      # aucune clé de ticket

    def test_versions_fr_et_en_ont_la_meme_forme(self):
        for fr, en in NOUVEAUX.values():
            a, b = lire(fr), lire(en)
            with self.subTest(fixture=fr):
                self.assertEqual(set(a), set(b))
                for cle in a:
                    self.assertEqual(len(a[cle]), len(b[cle]))
                    for x, y in zip(a[cle], b[cle]):
                        for champ in ("author", "status", "outcome", "confidence", "started_on", "review_due", "launched_on", "reviewed_on"):
                            self.assertEqual(x.get(champ), y.get(champ))
                        self.assertNotEqual(x["problem"], y["problem"])


if __name__ == "__main__":
    unittest.main()
