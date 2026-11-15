"""
Tests des définitions de flux de tools/flow_referential.py (change flow-definitions-referential, tâche 2.1, conception D2 à D4), sans base :
les six codes de D4 après les treize du référentiel des cycles, un référentiel sans définition valide et écrit avec trois tables vidées,
`definir_statut` (les deux drapeaux des sept segments, deux points d'engagement, deux refus), des refus sans aucune valeur,
et `ecrire` avec une fausse connexion (huit tables vidées, trois tables de définitions insérées avant la ligne d'état, aucun UPDATE).

    bash tests/run_all.sh flow_referential
"""
from __future__ import annotations

import dataclasses
import re
import sys
import unittest
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
sys.path.insert(0, str(DOSSIER.parents[1] / "tools"))
import flow_referential as fr  # noqa: E402
import test_flow_referential as base  # noqa: E402

CODES_CYCLES = base.CODES[:13]
CODES_DEFINITIONS = ("flow_status_duplicate", "flow_status_segment", "commitment_flag", "ready_flag", "unplanned_type",
                     "blocking_link_type")
SEGMENTS_CALCULES = ("definition", "ready", "implementation", "review_verification", "acceptance")
SEGMENTS = SEGMENTS_CALCULES + ("todo", "done")
PREFIXE_MESSAGE = base.PREFIXE_MESSAGE


def avec_definitions() -> fr.Referentiel:
    """Le référentiel valide de base, plus une définition inventée : un statut par segment (point d'engagement : ready), un type, deux liens."""
    statuts = tuple(fr.definir_statut(f"t-flux-{segment}", segment, "ready") for segment in SEGMENTS)
    return dataclasses.replace(
        base.valide(), statuts_flux=statuts,
        types_non_planifies=(fr.TypeNonPlanifie("t-defaut", "defect"),),
        types_liens_bloquants=(fr.TypeLienBloquant("t-bloque", "blocks"), fr.TypeLienBloquant("t-attend", "waits_for")))


def constats(ref: fr.Referentiel) -> list[str]:
    return list(fr.valider(ref, base.declarees(ref)))


def statut(ref: fr.Referentiel, segment: str) -> int:
    return next(i for i, s in enumerate(ref.statuts_flux) if s.segment == segment)


class Codes(unittest.TestCase):
    def test_les_codes_de_definition_suivent_les_treize_codes_des_cycles(self):
        self.assertEqual(tuple(fr.CODES), CODES_CYCLES + CODES_DEFINITIONS)

    def test_referentiel_sans_definition_valide(self):
        self.assertEqual(constats(base.valide()), [])
        self.assertEqual((base.valide().statuts_flux, base.valide().types_non_planifies, base.valide().types_liens_bloquants),
                         ((), (), ()))

    def test_referentiel_avec_definitions_valide(self):
        self.assertEqual(constats(avec_definitions()), [])

    def test_flow_status_duplicate_deux_fois_la_meme_casse_et_espaces_ignores(self):
        ref = avec_definitions()
        doublon = dataclasses.replace(ref.statuts_flux[0], statut="  T-FLUX-" + ref.statuts_flux[0].statut[7:].upper() + " ")
        self.assertEqual(constats(dataclasses.replace(ref, statuts_flux=(*ref.statuts_flux, doublon))), ["flow_status_duplicate"])

    def test_flow_status_duplicate_statut_vide(self):
        ref = avec_definitions()
        vide = dataclasses.replace(ref.statuts_flux[0], statut="   ")
        self.assertEqual(constats(dataclasses.replace(ref, statuts_flux=(*ref.statuts_flux, vide))), ["flow_status_duplicate"])

    def test_flow_status_segment_inconnu(self):
        ref = avec_definitions()
        statuts = list(ref.statuts_flux)
        statuts[0] = dataclasses.replace(statuts[0], segment="inconnu")
        self.assertEqual(constats(dataclasses.replace(ref, statuts_flux=tuple(statuts))), ["flow_status_segment"])

    def test_commitment_flag_sur_todo_ou_done(self):
        for segment in ("todo", "done"):
            with self.subTest(segment=segment):
                ref = avec_definitions()
                statuts = list(ref.statuts_flux)
                i = statut(ref, segment)
                statuts[i] = dataclasses.replace(statuts[i], engage=True)
                self.assertEqual(constats(dataclasses.replace(ref, statuts_flux=tuple(statuts))), ["commitment_flag"])

    def test_commitment_flag_deux_statuts_d_un_segment_avec_des_drapeaux_differents(self):
        ref = avec_definitions()
        i = statut(ref, "ready")
        autre = dataclasses.replace(ref.statuts_flux[i], statut="t-flux-ready-bis", engage=False)
        self.assertEqual(constats(dataclasses.replace(ref, statuts_flux=(*ref.statuts_flux, autre))), ["commitment_flag"])

    def test_commitment_flag_dans_deux_segments(self):
        ref = avec_definitions()
        statuts = list(ref.statuts_flux)
        i = statut(ref, "implementation")
        statuts[i] = dataclasses.replace(statuts[i], engage=True)
        self.assertEqual(constats(dataclasses.replace(ref, statuts_flux=tuple(statuts))), ["commitment_flag"])

    def test_ready_flag_sur_todo_ou_done(self):
        for segment in ("todo", "done"):
            with self.subTest(segment=segment):
                ref = avec_definitions()
                statuts = list(ref.statuts_flux)
                i = statut(ref, segment)
                statuts[i] = dataclasses.replace(statuts[i], file_prete=True)
                self.assertEqual(constats(dataclasses.replace(ref, statuts_flux=tuple(statuts))), ["ready_flag"])

    def test_ready_flag_refuse_sur_un_segment_autre_que_ready_meme_seul(self):
        ref = avec_definitions()
        statuts = [dataclasses.replace(s, file_prete=(s.segment == "definition")) for s in ref.statuts_flux]       # la file Ready sur definition seul
        self.assertEqual(constats(dataclasses.replace(ref, statuts_flux=tuple(statuts))), ["ready_flag"])

    def test_ready_flag_deux_statuts_d_un_segment_avec_des_drapeaux_differents(self):
        ref = avec_definitions()
        i = statut(ref, "ready")
        autre = dataclasses.replace(ref.statuts_flux[i], statut="t-flux-ready-bis", file_prete=False)
        self.assertEqual(constats(dataclasses.replace(ref, statuts_flux=(*ref.statuts_flux, autre))), ["ready_flag"])

    def test_ready_flag_dans_deux_segments(self):
        ref = avec_definitions()
        statuts = list(ref.statuts_flux)
        i = statut(ref, "implementation")
        statuts[i] = dataclasses.replace(statuts[i], file_prete=True)
        self.assertEqual(constats(dataclasses.replace(ref, statuts_flux=tuple(statuts))), ["ready_flag"])

    def test_unplanned_type_doublon_vide_ou_genre_inconnu(self):
        ref = avec_definitions()
        for type_ in (fr.TypeNonPlanifie(" T-DEFAUT", "defect"), fr.TypeNonPlanifie("  ", "defect"), fr.TypeNonPlanifie("t-autre", "support")):
            with self.subTest(type_=type_):
                self.assertEqual(constats(dataclasses.replace(ref, types_non_planifies=(*ref.types_non_planifies, type_))),
                                 ["unplanned_type"])

    def test_blocking_link_type_doublon_vide_ou_sens_inconnu(self):
        ref = avec_definitions()
        for lien in (fr.TypeLienBloquant(" T-BLOQUE", "blocks"), fr.TypeLienBloquant("", "blocks"), fr.TypeLienBloquant("t-autre", "x")):
            with self.subTest(lien=lien):
                self.assertEqual(constats(dataclasses.replace(ref, types_liens_bloquants=(*ref.types_liens_bloquants, lien))),
                                 ["blocking_link_type"])

    def test_constats_de_definition_apres_ceux_des_cycles_dans_l_ordre(self):
        ref = base.remplacer(avec_definitions(), "cycles", 0, fin=base.date(2098, 12, 31))
        statuts = list(ref.statuts_flux)
        j = statut(ref, "implementation")
        statuts[j] = dataclasses.replace(statuts[j], engage=True)       # engagement dans deux segments (ready et implementation)
        ref = dataclasses.replace(ref, statuts_flux=tuple(statuts),
                                  types_liens_bloquants=(*ref.types_liens_bloquants, fr.TypeLienBloquant("t-autre", "x")))
        self.assertEqual(constats(ref), ["cycle_dates", "commitment_flag", "blocking_link_type"])

    def test_deux_statuts_d_un_meme_segment_avec_les_memes_drapeaux_acceptes(self):
        ref = avec_definitions()
        i = statut(ref, "ready")
        autre = dataclasses.replace(ref.statuts_flux[i], statut="t-flux-ready-bis")
        self.assertEqual(constats(dataclasses.replace(ref, statuts_flux=(*ref.statuts_flux, autre))), [])


class DefinirStatut(unittest.TestCase):
    def test_point_d_engagement_ready_seul_le_segment_ready_est_engage_et_file_prete(self):
        for segment in SEGMENTS:
            with self.subTest(segment=segment):
                s = fr.definir_statut("t-s", segment, "ready")
                self.assertEqual((s.statut, s.segment), ("t-s", segment))
                self.assertEqual(s.engage, segment == "ready")
                self.assertEqual(s.file_prete, segment == "ready")

    def test_point_d_engagement_implementation(self):
        for segment in SEGMENTS:
            with self.subTest(segment=segment):
                s = fr.definir_statut("t-s", segment, "implementation")
                self.assertEqual(s.engage, segment == "implementation")
                self.assertEqual(s.file_prete, segment == "ready")

    def test_point_d_engagement_hors_des_segments_calcules_refuse(self):
        for point in ("done", "todo", "inconnu"):
            with self.subTest(point=point):
                with self.assertRaises(fr.ReferentielInvalide) as refus:
                    fr.definir_statut("t-s", "ready", point)
                self.assertEqual(str(refus.exception), PREFIXE_MESSAGE + "commitment_flag")
                self.assertEqual(str(refus.exception).count(point) if point == "inconnu" else 0, 0)

    def test_segment_inconnu_refuse(self):
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fr.definir_statut("SENTINELLE-STATUT", "SENTINELLE-SEGMENT", "ready")
        self.assertEqual(str(refus.exception), PREFIXE_MESSAGE + "flow_status_segment")
        self.assertNotIn("SENTINELLE", str(refus.exception))

    def test_aucun_point_d_engagement_par_defaut(self):
        with self.assertRaises(TypeError):
            fr.definir_statut("t-s", "ready")          # type: ignore[call-arg]


class Refus(unittest.TestCase):
    def test_refus_sans_aucune_valeur(self):
        ref = dataclasses.replace(
            base.valide(),
            statuts_flux=(fr.StatutFlux("SENTINELLE-STATUT", "SENTINELLE-SEGMENT", True, True),
                          fr.StatutFlux("sentinelle-statut", "todo", False, False)),
            types_non_planifies=(fr.TypeNonPlanifie("SENTINELLE-TYPE", "SENTINELLE-GENRE"),),
            types_liens_bloquants=(fr.TypeLienBloquant("SENTINELLE-LIEN", "SENTINELLE-SENS"),))
        conn = base.FausseConnexion()
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fr.ecrire(conn, ref, base.declarees(ref))
        message = str(refus.exception)
        self.assertEqual(message, PREFIXE_MESSAGE + "flow_status_duplicate, flow_status_segment, unplanned_type, blocking_link_type")
        self.assertNotRegex(message.lower(), "sentinelle")
        self.assertEqual(conn.instructions, [])

    def test_scenario_cycles_puis_definitions(self):
        ref = base.remplacer(base.valide(), "cycles", 0, fin=base.date(2098, 12, 31))
        i_a = fr.definir_statut("t-a", "ready", "ready")
        i_b = dataclasses.replace(fr.definir_statut("t-b", "ready", "ready"), engage=False)
        ref = dataclasses.replace(ref, statuts_flux=(i_a, i_b), types_liens_bloquants=(fr.TypeLienBloquant("t-l", "inconnu"),))
        conn = base.FausseConnexion()
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fr.ecrire(conn, ref, base.declarees(ref))
        self.assertEqual(str(refus.exception), PREFIXE_MESSAGE + "cycle_dates, commitment_flag, blocking_link_type")
        self.assertEqual(conn.instructions, [])


TABLES_DEFINITIONS = ("ref_flow_statuses", "ref_unplanned_types", "ref_blocking_link_types")
HUIT_TABLES = {"ref_cycles", "ref_labels", "ref_dw_columns", "ref_dw_statuses", "ref_state", *TABLES_DEFINITIONS}


def table(sql: str) -> str:
    return re.search(r"flow\.(ref_\w+)", sql).group(1)


class Ecrire(unittest.TestCase):
    def test_referentiel_sans_definition_vide_les_huit_tables_et_n_insere_aucune_definition(self):
        conn = base.FausseConnexion()
        ref = base.valide()
        fr.ecrire(conn, ref, base.declarees(ref))
        ecritures = conn.ecritures()
        self.assertEqual({table(s) for s in ecritures if s.startswith("DELETE")}, HUIT_TABLES)
        self.assertEqual([s for s in ecritures if s.startswith("INSERT") and table(s) in TABLES_DEFINITIONS], [])

    def test_huit_tables_videes_trois_tables_inserees_avant_l_etat_dans_une_seule_transaction_sans_update(self):
        conn = base.FausseConnexion()
        ref = avec_definitions()
        fr.ecrire(conn, ref, base.declarees(ref))
        ecritures = conn.ecritures()
        for sql in conn.instructions:
            self.assertNotRegex(sql, r"(?i)\bUPDATE\b", sql)
        suppressions = [i for i, s in enumerate(ecritures) if s.startswith("DELETE")]
        insertions = [i for i, s in enumerate(ecritures) if s.startswith("INSERT")]
        self.assertEqual({table(ecritures[i]) for i in suppressions}, HUIT_TABLES)
        self.assertLess(max(suppressions), min(insertions))
        ordre = [table(ecritures[i]) for i in insertions]
        self.assertEqual(ordre[-1], "ref_state")
        self.assertEqual(ordre.count("ref_state"), 1)
        for nom in TABLES_DEFINITIONS:
            self.assertLess(ordre.index("ref_cycles"), ordre.index(nom))
            self.assertLess(ordre.index("ref_dw_statuses"), ordre.index(nom))
            self.assertLess(ordre.index(nom), ordre.index("ref_state"))
        self.assertEqual(ordre.count("ref_flow_statuses"), len(ref.statuts_flux))
        self.assertEqual(ordre.count("ref_unplanned_types"), len(ref.types_non_planifies))
        self.assertEqual(ordre.count("ref_blocking_link_types"), len(ref.types_liens_bloquants))
        self.assertEqual(conn.evenements.count("BEGIN"), 1)
        self.assertEqual(conn.evenements[-1], "COMMIT")
        self.assertEqual(conn.instructions[0], "SELECT current_user")

    def test_les_valeurs_inserees_sont_celles_de_la_structure(self):
        conn = base.FausseConnexion()
        ref = avec_definitions()
        fr.ecrire(conn, ref, base.declarees(ref))
        valeurs = [p for sql, p in zip(conn.instructions, conn.parametres) if sql.startswith("INSERT INTO flow.ref_flow_statuses")]
        self.assertEqual(sorted(tuple(v) for v in valeurs),
                         sorted((s.statut, s.segment, s.engage, s.file_prete) for s in ref.statuts_flux))

    def test_definition_invalide_refusee_sans_instruction(self):
        conn = base.FausseConnexion()
        ref = dataclasses.replace(avec_definitions(), types_non_planifies=(fr.TypeNonPlanifie("t", "support"),))
        with self.assertRaises(fr.ReferentielInvalide):
            fr.ecrire(conn, ref, base.declarees(ref))
        self.assertEqual(conn.instructions, [])

    def test_insert_de_definition_qui_echoue_annule_tout_et_n_ecrit_pas_l_etat(self):
        conn = base.FausseConnexion(echec_sur=r"^INSERT INTO flow\.ref_blocking_link_types")
        ref = avec_definitions()
        with self.assertRaises(RuntimeError):
            fr.ecrire(conn, ref, base.declarees(ref))
        self.assertEqual(conn.evenements[-1], "ROLLBACK")
        self.assertFalse([s for s in conn.instructions if s.startswith("INSERT INTO flow.ref_state")])


if __name__ == "__main__":
    unittest.main()
