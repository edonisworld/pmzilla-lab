"""tools/flux_config.py : réglages du change epic-flow-report (R-89) : colonne Ready et colonnes actives du Discovery Workflow
(conception D4), rôles d'étiquettes pilot_domain, ready et confirmation, clé de cycle d'une étiquette de cycle (D4b).

Chaque test d'erreur vérifie : ErreurConfig (arrêt, code 1), chemin de clé et ligne dans le message, valeur absente.
Données inventées ; aucun accès à Flux-Lab/ ni à Jira."""
import contextlib
import io
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flux_config  # noqa: E402
from yaml_strict import ErreurConfig, charger  # noqa: E402

CYCLES = """cycles:
  2026-C1: {fix_version: vA-1, start: 2026-01-05, end: 2026-02-27}
  2026-C2: {fix_version: vA-2, start: 2026-03-02, end: 2026-04-24}
"""


def lire(texte: str) -> dict:
    return flux_config.to_internal(charger(texte))


class Base(unittest.TestCase):
    def refus(self, texte: str, *attendus: str, interdits: tuple = ()) -> str:
        with self.assertRaises(ErreurConfig) as c:
            lire(texte)
        message = str(c.exception)
        for a in attendus:
            self.assertIn(a, message)
        for i in interdits:
            self.assertNotIn(i, message)
        return message

    def lu_sans_message(self, texte: str) -> dict:
        with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()) as out:
            interne = lire(texte)
        self.assertEqual(err.getvalue() + out.getvalue(), "")
        return interne


class TestColonnesReadyEtActives(Base):
    BLOC = """discovery_workflow:
  columns:
    Idee: [s-idee, s-cadrage]
    Revue: [s-revue]
    Pret: [s-pret]
    Valide: [s-ok]
  start_column: Idee
  review_passed_columns: [Valide]
  ready_column: Pret
  active_columns: [Idee, Revue]
  validated_on: 2026-09-01
"""
    SANS = BLOC.replace("  ready_column: Pret\n", "").replace("  active_columns: [Idee, Revue]\n", "")

    def test_lues(self):
        d = flux_config.discovery_workflow(self.lu_sans_message(self.BLOC))
        self.assertEqual(d["ready_column"], "Pret")
        self.assertEqual(d["active_columns"], ["Idee", "Revue"])
        self.assertTrue(d["validated"])

    def test_colonne_de_depart_active_permise(self):
        d = flux_config.discovery_workflow(lire(self.BLOC))
        self.assertIn(d["start_column"], d["active_columns"])
        d = flux_config.discovery_workflow(lire(self.BLOC.replace("[Idee, Revue]", "[Revue]")))
        self.assertEqual(d["active_columns"], ["Revue"])

    def test_cles_absentes_lues_sans_message(self):
        d = flux_config.discovery_workflow(self.lu_sans_message(self.SANS))
        self.assertIsNone(d["ready_column"])
        self.assertEqual(d["active_columns"], [])
        self.assertEqual(d["start_column"], "Idee")
        self.assertEqual(d["review_passed_columns"], ["Valide"])

    def test_colonne_ready_non_declaree(self):
        self.refus(self.BLOC.replace("ready_column: Pret", "ready_column: InconnueZZ"),
                   "discovery_workflow.ready_column", "L9", interdits=("InconnueZZ",))

    def test_colonne_ready_pas_une_chaine(self):
        # une liste à la place d'un nom de colonne : refus avec chemin et ligne, pas une exception Python
        self.refus(self.BLOC.replace("ready_column: Pret", "ready_column: [Pret]"),
                   "discovery_workflow.ready_column", "L9", interdits=("Pret",))

    def test_colonne_active_non_declaree(self):
        self.refus(self.BLOC.replace("[Idee, Revue]", "[Idee, InconnueZZ]"), "discovery_workflow.active_columns", "L10",
                   interdits=("InconnueZZ",))

    def test_colonne_ready_parmi_les_actives(self):
        self.refus(self.BLOC.replace("[Idee, Revue]", "[Idee, Pret]"), "discovery_workflow.active_columns", "L10",
                   interdits=("Pret",))

    def test_colonnes_actives_pas_une_liste(self):
        self.refus(self.BLOC.replace("[Idee, Revue]", "Idee"), "discovery_workflow.active_columns", "L10",
                   interdits=("Idee",))

    def test_les_lecteurs_des_cycles_et_des_statuts_d_epics_ignorent_les_cles(self):
        """Le lecteur partagé rend le bloc avec ou sans les deux clés : start_column et les colonnes ne changent pas."""
        avec = flux_config.discovery_workflow(lire(self.BLOC))
        sans = flux_config.discovery_workflow(lire(self.SANS))
        self.assertEqual(avec["columns"], sans["columns"])
        self.assertEqual(avec["start_column"], sans["start_column"])
        self.assertEqual(avec["review_passed_columns"], sans["review_passed_columns"])


class TestRolesEtiquettes(Base):
    BLOC = """declared_labels:
  cycle: {prefix: "cy-", labels: ["cy-a", "cy-b"], cycle_keys: {cy-a: 2026-C1, cy-b: 2026-C2}}
  pilot_domain: {prefix: "pd-", labels: ["pd-x"]}
  ready: {prefix: "rd-", labels: ["rd-x"]}
  confirmation: {prefix: "cf-", labels: ["cf-in", "cf-out"], meanings: {cf-in: taken_in, cf-out: not_taken_in}}
""" + CYCLES

    def test_roles_lus(self):
        d = flux_config.declared_labels(self.lu_sans_message(self.BLOC))
        self.assertEqual(d["pilot_domain"]["labels"], ["pd-x"])
        self.assertEqual(d["ready"]["labels"], ["rd-x"])
        self.assertEqual(d["confirmation"]["meanings"], {"cf-in": "taken_in", "cf-out": "not_taken_in"})
        self.assertEqual(d["cycle"]["cycle_keys"], {"cy-a": "2026-C1", "cy-b": "2026-C2"})
        self.assertEqual(d["cycle"]["labels"], ["cy-a", "cy-b"])

    def test_etiquette_de_cycle_sans_cle_de_cycle(self):
        d = flux_config.declared_labels(lire(self.BLOC.replace(
            ', cycle_keys: {cy-a: 2026-C1, cy-b: 2026-C2}', "")))
        self.assertEqual(d["cycle"]["labels"], ["cy-a", "cy-b"])
        self.assertEqual(d["cycle"].get("cycle_keys", {}), {})

    def test_cle_de_cycle_partielle(self):
        d = flux_config.declared_labels(lire(self.BLOC.replace(", cy-b: 2026-C2", "")))
        self.assertEqual(d["cycle"]["cycle_keys"], {"cy-a": "2026-C1"})

    def test_ready_vide_lu_sans_message(self):
        for ready in ('{prefix: "rd-", labels: []}', '{prefix: "rd-"}', '{prefix: "rd-", labels: }', '{labels: []}'):
            with self.subTest(ready=ready):
                texte = self.BLOC.replace('{prefix: "rd-", labels: ["rd-x"]}', ready)
                d = flux_config.declared_labels(self.lu_sans_message(texte))
                self.assertEqual(d["ready"]["labels"], [])

    def test_ready_absent_pas_une_erreur(self):
        texte = self.BLOC.replace('  ready: {prefix: "rd-", labels: ["rd-x"]}\n', "")
        self.assertNotIn("ready", flux_config.declared_labels(lire(texte)))

    def test_roles_anciens_inchanges(self):
        d = flux_config.declared_labels(lire('declared_labels:\n  epic_review: {prefix: "er-", labels: ["er-x"]}\n'))
        self.assertEqual(d, {"epic_review": {"prefix": "er-", "labels": ["er-x"]}})

    def test_domaine_pilote_sans_exactement_une_etiquette(self):
        self.refus(self.BLOC.replace('labels: ["pd-x"]', 'labels: ["pd-x", "pd-y"]'), "declared_labels.pilot_domain", "L3",
                   interdits=("pd-x", "pd-y"))
        self.refus(self.BLOC.replace('labels: ["pd-x"]', "labels: []"), "declared_labels.pilot_domain", "L3")

    def test_ready_avec_deux_etiquettes(self):
        self.refus(self.BLOC.replace('labels: ["rd-x"]', 'labels: ["rd-x", "rd-y"]'), "declared_labels.ready", "L4",
                   interdits=("rd-x", "rd-y"))

    def test_confirmation_sans_sens(self):
        self.refus(self.BLOC.replace(", cf-out: not_taken_in", ""), "declared_labels.confirmation", "L5",
                   interdits=("cf-out", "cf-in"))
        self.refus(self.BLOC.replace(", meanings: {cf-in: taken_in, cf-out: not_taken_in}", ""),
                   "declared_labels.confirmation", "L5")

    def test_confirmation_sens_inconnu(self):
        self.refus(self.BLOC.replace("cf-in: taken_in", "cf-in: SensZZ"), "declared_labels.confirmation", "L5",
                   interdits=("SensZZ", "cf-in"))

    def test_sens_pour_une_etiquette_non_declaree(self):
        self.refus(self.BLOC.replace("meanings: {", "meanings: {cf-zz: taken_in, "), "declared_labels.confirmation", "L5",
                   interdits=("cf-zz",))

    def test_cle_de_cycle_absente_du_bloc_cycles(self):
        self.refus(self.BLOC.replace("cy-b: 2026-C2", "cy-b: 2026-C9"), "declared_labels.cycle", "L2",
                   interdits=("2026-C9", "cy-b"))

    def test_cle_de_cycle_sans_bloc_cycles(self):
        texte = self.BLOC.replace(CYCLES, "")
        self.refus(texte, "declared_labels.cycle", "L2", interdits=("2026-C1",))

    def test_cle_de_cycle_pour_une_etiquette_non_declaree(self):
        self.refus(self.BLOC.replace("cycle_keys: {", "cycle_keys: {cy-zz: 2026-C1, "), "declared_labels.cycle", "L2",
                   interdits=("cy-zz",))

    def test_etiquette_hors_du_prefixe_de_son_role(self):
        self.refus(self.BLOC.replace('"pd-x"', '"ZZdistinct"'), "declared_labels.pilot_domain", "L3",
                   interdits=("ZZdistinct",))

    def test_meme_etiquette_dans_deux_roles(self):
        self.refus(self.BLOC.replace('{prefix: "rd-", labels: ["rd-x"]}', '{prefix: "pd-", labels: ["pd-x"]}'),
                   "declared_labels", "L4", interdits=("pd-x",))

    def test_cle_inconnue_d_un_role(self):
        self.refus(self.BLOC.replace('labels: ["pd-x"]', 'labels: ["pd-x"], meanings: {pd-x: taken_in}'),
                   "declared_labels.pilot_domain", "L3")


if __name__ == "__main__":
    unittest.main()
