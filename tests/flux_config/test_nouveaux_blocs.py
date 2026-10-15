"""tools/flux_config.py : nouveaux réglages du change R-58 (identifiant cloud, échéance du jeton, étiquettes déclarées,
cycles, patches, Discovery Workflow, conservation) et refus de export_po_field.

Chaque test d'erreur vérifie : ErreurConfig (arrêt, code 1), chemin de clé et ligne dans le message, valeur absente.
Données inventées ; aucun accès à Flux-Lab/ ni à Jira."""
import contextlib
import datetime
import io
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flux_config  # noqa: E402
from yaml_strict import ErreurConfig, charger  # noqa: E402

# six cycles de huit semaines consécutifs (lundi -> vendredi) et une version de fin d'année
CYCLES_VALIDES = """cycles:
  2026-C1: {fix_version: vA-1, start: 2026-01-05, end: 2026-02-27}
  2026-C2: {fix_version: vA-2, start: 2026-03-02, end: 2026-04-24}
  2026-C3: {fix_version: vA-3, start: 2026-04-27, end: 2026-06-19}
  2026-C4: {fix_version: vA-4, start: 2026-06-22, end: 2026-08-14}
  2026-C5: {fix_version: vA-5, start: 2026-08-17, end: 2026-10-09}
  2026-C6: {fix_version: vA-6, start: 2026-10-12, end: 2026-12-04}
  2026-EOY: {fix_version: vA-eoy, start: 2026-12-07, end: 2026-12-18}
"""


def lire(texte: str) -> dict:
    return flux_config.to_internal(charger(texte))


class Base(unittest.TestCase):
    def refus(self, texte: str, *attendus: str, interdits: tuple = ()) -> str:
        """Le texte est refusé : le message contient chaque attendu et aucun interdit (valeurs données)."""
        with self.assertRaises(ErreurConfig) as c:
            lire(texte)
        message = str(c.exception)
        for a in attendus:
            self.assertIn(a, message)
        for i in interdits:
            self.assertNotIn(i, message)
        return message


class TestPoField(Base):
    def test_present_refuse_avec_phrase_cle_et_ligne(self):
        m = self.refus("jira_site: x\nexport_po_field: ValeurDistinctivePO\n",
                       "réglage non pris en charge : export_po_field", "setting not supported: export_po_field", "L2",
                       interdits=("ValeurDistinctivePO",))
        self.assertNotIn("customfield", m)

    def test_absent_sans_refus(self):
        self.assertNotIn("export_po_field", lire("jira_site: x\n"))


class TestIdentifiantEtJeton(Base):
    def test_lus_tels_quels(self):
        i = lire("jira_cloud_id: abc-123\njira_token_expires: 2027-01-31\njira_token_warning_days: 14\n")
        self.assertEqual(flux_config.cloud_id(i), "abc-123")
        self.assertEqual(flux_config.token_expiry(i), (datetime.date(2027, 1, 31), 14))

    def test_defauts_et_chaine_iso(self):
        i = lire("jira_token_expires: '2027-02-01'\n")
        self.assertEqual(flux_config.token_expiry(i), (datetime.date(2027, 2, 1), 30))
        self.assertEqual(flux_config.token_expiry(lire("jira_site: x\n")), (None, 30))
        self.assertIsNone(flux_config.cloud_id(lire("jira_site: x\n")))

    def test_refus(self):
        self.refus("jira_cloud_id: 12\n", "jira_cloud_id", "L1")
        self.refus("jira_token_expires: PasUneDateZZ\n", "jira_token_expires", "L1", interdits=("PasUneDateZZ",))
        self.refus("jira_token_warning_days: 0\n", "jira_token_warning_days", "L1")
        self.refus("a: 1\njira_token_warning_days: abcZZ\n", "jira_token_warning_days", "L2", interdits=("abcZZ",))


class TestEtiquettesDeclarees(Base):
    BLOC = """declared_labels:
  up_merge: {prefix: "um-", labels: ["um-legal", "um-hotfix"]}
  cycle: {prefix: "cy-", labels: ["cy-a"]}
  epic_review: {prefix: "er-", labels: ["er-x"]}
"""

    def test_valide(self):
        d = flux_config.declared_labels(lire(self.BLOC))
        self.assertEqual(d["up_merge"], {"prefix": "um-", "labels": ["um-legal", "um-hotfix"]})
        self.assertEqual(set(d), {"up_merge", "cycle", "epic_review"})

    def test_sans_bloc(self):
        self.assertIsNone(flux_config.declared_labels(lire("jira_site: x\n")))

    def test_etiquette_hors_prefixe(self):
        self.refus(self.BLOC.replace('["cy-a"]', '["ZZdistinct"]'), "declared_labels.cycle", "L3",
                   interdits=("ZZdistinct",))

    def test_etiquette_deux_fois(self):
        self.refus(self.BLOC.replace('["cy-a"]', '["cy-a", "cy-a"]'), "declared_labels", "L3")
        # même étiquette dans deux rôles
        self.refus(self.BLOC.replace('prefix: "er-", labels: ["er-x"]', 'prefix: "cy-", labels: ["cy-a"]'),
                   "declared_labels", "L4", interdits=("cy-a",))

    def test_role_inconnu(self):
        self.refus(self.BLOC + '  autre: {prefix: "x", labels: ["x"]}\n', "declared_labels", "L5")

    def test_up_merge_sans_deux_etiquettes(self):
        self.refus(self.BLOC.replace('["um-legal", "um-hotfix"]', '["um-legal"]'), "declared_labels.up_merge", "L2",
                   interdits=("um-legal",))
        self.refus(self.BLOC.replace('["um-legal", "um-hotfix"]', '["um-legal", "um-hotfix", "um-z"]'),
                   "declared_labels.up_merge", "L2")

    def test_sous_cle_inconnue_ou_type(self):
        self.refus(self.BLOC.replace('prefix: "cy-", ', 'prefix: "cy-", x: 1, '), "declared_labels.cycle", "L3")
        self.refus(self.BLOC.replace('labels: ["cy-a"]', 'labels: cy-a'), "declared_labels.cycle", "L3")


class TestCycles(Base):
    def test_annee_valide_sans_avertissement(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            c = flux_config.cycles(lire(CYCLES_VALIDES))
        self.assertEqual(err.getvalue(), "")
        self.assertEqual([x.key for x in c], ["2026-C1", "2026-C2", "2026-C3", "2026-C4", "2026-C5", "2026-C6", "2026-EOY"])
        self.assertEqual(c[0].fix_version, "vA-1")
        self.assertEqual(c[0].start, datetime.date(2026, 1, 5))
        self.assertEqual(c[0].end, datetime.date(2026, 2, 27))
        self.assertIsNone(c[0].provision)
        self.assertFalse(c[0].base_version)

    def test_trie_par_debut(self):
        lignes = CYCLES_VALIDES.splitlines()
        inverse = lignes[:1] + list(reversed(lignes[1:]))
        c = flux_config.cycles(lire("\n".join(inverse) + "\n"))
        self.assertEqual([x.key for x in c][0], "2026-C1")

    def test_absent(self):
        self.assertEqual(flux_config.cycles(lire("jira_site: x\n")), [])

    def test_trou_entre_cycles(self):
        t = CYCLES_VALIDES.replace("start: 2026-03-02", "start: 2026-03-16").replace("end: 2026-04-24", "end: 2026-05-08")
        self.refus(t, "cycles.2026-C2", "L3", interdits=("2026-03-16", "2026-05-08"))

    def test_mauvaise_forme_de_cle(self):
        m = self.refus("cycles:\n  v9.9.9QQ: {fix_version: x, start: 2026-01-05, end: 2026-02-27}\n", "cycles", "L2",
                       interdits=("v9.9.9QQ",))
        self.refus("cycles:\n  2026-C7: {fix_version: x, start: 2026-01-05, end: 2026-02-27}\n", "cycles", "L2")
        self.refus("cycles:\n  2026-C0: {fix_version: x, start: 2026-01-05, end: 2026-02-27}\n", "cycles", "L2")

    def test_version_sur_deux_cles(self):
        m = self.refus(CYCLES_VALIDES.replace("vA-2", "vA-1"), "2026-C1", "2026-C2", "L3", interdits=("vA-1",))

    def test_debut_pas_un_lundi(self):
        self.refus(CYCLES_VALIDES.replace("start: 2026-01-05", "start: 2026-01-06"), "cycles.2026-C1.start", "L2",
                   interdits=("2026-01-06",))

    def test_fin_pas_un_vendredi(self):
        self.refus(CYCLES_VALIDES.replace("end: 2026-02-27", "end: 2026-02-26"), "cycles.2026-C1.end", "L2",
                   interdits=("2026-02-26",))

    def test_fin_avant_debut(self):
        self.refus("cycles:\n  2026-C1: {fix_version: x, start: 2026-02-02, end: 2026-01-30}\n", "cycles.2026-C1", "L2",
                   interdits=("2026-01-30",))

    def test_une_annee_sans_contrainte_avec_la_precedente(self):
        t = ("cycles:\n  2025-C6: {fix_version: a, start: 2025-10-13, end: 2025-12-05}\n"
             "  2026-C1: {fix_version: b, start: 2026-01-19, end: 2026-03-13}\n")
        self.assertEqual(len(flux_config.cycles(lire(t))), 2)

    def test_pas_huit_semaines_avertit_sans_arreter(self):
        t = "cycles:\n  2026-C1: {fix_version: x, start: 2026-01-05, end: 2026-02-20}\n"
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            c = flux_config.cycles(lire(t))
        self.assertEqual(len(c), 1)
        self.assertIn("2026-C1", err.getvalue())
        self.assertNotIn("2026-02-20", err.getvalue())

    def test_provision(self):
        t = CYCLES_VALIDES.replace("vA-1,", "vA-1, up_merge_provision: 0.25,")
        self.assertEqual(flux_config.cycles(lire(t))[0].provision, 0.25)
        for v in ("1.5", "-0.1", "abcZZ"):
            self.refus(CYCLES_VALIDES.replace("vA-1,", f"vA-1, up_merge_provision: {v},"),
                       "cycles.2026-C1.up_merge_provision", "L2", interdits=(v,))
        for v in ("0", "1"):
            lire(CYCLES_VALIDES.replace("vA-1,", f"vA-1, up_merge_provision: {v},"))

    def test_base_version(self):
        t = CYCLES_VALIDES.replace("vA-1,", "vA-1, base_version: true,")
        c = flux_config.cycles(lire(t))
        self.assertTrue(c[0].base_version)
        self.assertFalse(any(x.base_version for x in c[1:]))

    def test_base_version_sur_eoy_refuse(self):
        self.refus(CYCLES_VALIDES.replace("vA-eoy,", "vA-eoy, base_version: true,"), "cycles.2026-EOY", "L8")

    def test_deux_base_version_la_meme_annee(self):
        t = CYCLES_VALIDES.replace("vA-1,", "vA-1, base_version: true,").replace("vA-3,", "vA-3, base_version: true,")
        self.refus(t, "cycles.2026-C1", "cycles.2026-C3", "L2", "L4")

    def test_une_base_version_par_annee(self):
        t = ("cycles:\n  2025-C1: {fix_version: a, base_version: true, start: 2025-01-06, end: 2025-02-28}\n"
             "  2026-C1: {fix_version: b, base_version: true, start: 2026-01-05, end: 2026-02-27}\n")
        self.assertEqual(len(flux_config.cycles(lire(t))), 2)

    def test_cle_ecrite_deux_fois(self):
        t = CYCLES_VALIDES + "  2026-C1: {fix_version: z, start: 2026-01-05, end: 2026-02-27}\n"
        self.refus(t, "écrite deux fois", "L2", "L9")

    def test_champs_obligatoires_et_inconnus(self):
        self.refus("cycles:\n  2026-C1: {start: 2026-01-05, end: 2026-02-27}\n", "cycles.2026-C1", "L2")
        self.refus("cycles:\n  2026-C1: {fix_version: x, start: 2026-01-05, end: 2026-02-27, zz: 1}\n", "cycles.2026-C1", "L2")


class TestPatches(Base):
    def test_valide(self):
        i = lire("patches:\n  2026-Q1: [p-1, p-2]\n  2026-Q2: [p-3]\n")
        self.assertEqual(flux_config.patches(i), {"2026-Q1": ["p-1", "p-2"], "2026-Q2": ["p-3"]})
        self.assertEqual(flux_config.patches(lire("jira_site: x\n")), {})

    def test_forme_de_cle(self):
        self.refus("patches:\n  2026-Q5: [a]\n", "patches", "L2")
        self.refus("patches:\n  v1.2.3ZZ: [a]\n", "patches", "L2", interdits=("v1.2.3ZZ",))

    def test_version_dans_deux_cles(self):
        self.refus("patches:\n  2026-Q1: [pDistinct]\n  2026-Q2: [pDistinct]\n", "2026-Q1", "2026-Q2", "L3",
                   interdits=("pDistinct",))

    def test_version_deja_dans_cycles(self):
        self.refus(CYCLES_VALIDES + "patches:\n  2026-Q1: [vA-1]\n", "2026-Q1", "2026-C1", interdits=("vA-1",))


class TestDiscoveryWorkflow(Base):
    BLOC = """discovery_workflow:
  columns:
    Idee: [s-idee, s-cadrage]
    Revue: [s-revue]
    Valide: [s-ok]
  start_column: Idee
  review_passed_columns: [Valide]
  validated_on: 2026-09-01
"""

    def test_valide(self):
        d = flux_config.discovery_workflow(lire(self.BLOC))
        self.assertTrue(d["validated"])
        self.assertEqual(d["start_column"], "Idee")
        self.assertEqual(d["review_passed_columns"], ["Valide"])
        self.assertEqual(d["columns"]["Revue"], ["s-revue"])
        self.assertEqual(d["validated_on"], datetime.date(2026, 9, 1))

    def test_sans_date_de_validation(self):
        d = flux_config.discovery_workflow(lire(self.BLOC.replace("  validated_on: 2026-09-01\n", "")))
        self.assertFalse(d["validated"])
        self.assertIsNone(d["validated_on"])

    def test_absent(self):
        self.assertIsNone(flux_config.discovery_workflow(lire("jira_site: x\n")))

    def test_statut_dans_deux_colonnes(self):
        self.refus(self.BLOC.replace("[s-revue]", "[s-idee]"), "discovery_workflow.columns", "L2",
                   interdits=("s-idee",))

    def test_colonne_depart_inconnue(self):
        self.refus(self.BLOC.replace("start_column: Idee", "start_column: InconnueZZ"),
                   "discovery_workflow.start_column", "L6", interdits=("InconnueZZ",))

    def test_colonne_revue_passee_inconnue(self):
        self.refus(self.BLOC.replace("[Valide]", "[InconnueZZ]"), "discovery_workflow.review_passed_columns", "L7",
                   interdits=("InconnueZZ",))

    def test_date_invalide(self):
        self.refus(self.BLOC.replace("2026-09-01", "pasdateZZ"), "discovery_workflow.validated_on", "L8",
                   interdits=("pasdateZZ",))


class TestRetention(Base):
    def test_defauts(self):
        r = flux_config.retention(lire("jira_site: x\n"))
        self.assertEqual(r, {"period_days": 365, "max_file_age_days": 365, "labelled_backup_days": 30,
                             "backup_label": "rgpd", "offsite_flow_age_days": 35})
        self.assertEqual(flux_config.retention_days(lire("jira_site: x\n")), 365)

    def test_valeurs_donnees(self):
        r = flux_config.retention(lire("retention: {period_days: 200, max_file_age_days: 0, backup_label: abc1, "
                                       "labelled_backup_days: 10, offsite_flow_age_days: 20}\n"))
        self.assertEqual(r["max_file_age_days"], 0)
        self.assertEqual(r["backup_label"], "abc1")
        self.assertEqual(r["period_days"], 200)

    def test_cle_inconnue(self):
        self.refus("retention:\n  inconnue: 3\n", "retention", "L2")

    def test_valeur_non_numerique(self):
        self.refus("retention:\n  offsite_flow_age_days: abcZZ\n", "retention.offsite_flow_age_days", "L2",
                   interdits=("abcZZ",))
        self.refus("retention:\n  period_days: true\n", "retention.period_days", "L2")
        self.refus("retention:\n  labelled_backup_days: 0\n", "retention.labelled_backup_days", "L2")
        self.refus("retention:\n  period_days: 0\n", "retention.period_days", "L2")
        self.refus("retention:\n  max_file_age_days: -1\n", "retention.max_file_age_days", "L2")

    def test_etiquette_de_sauvegarde(self):
        self.refus("retention:\n  backup_label: Mauvais-ZZ\n", "retention.backup_label", "L2", interdits=("Mauvais-ZZ",))

    def test_periode_au_dessus_d_un_an_acceptee_au_chargement_refusee_a_l_usage(self):
        i = lire("retention:\n  period_days: 400\n  max_file_age_days: 10\n")
        with self.assertRaises(ErreurConfig) as c:
            flux_config.retention_days(i)
        self.assertIn("retention.period_days", str(c.exception))
        self.assertNotIn("400", str(c.exception))

    def test_age_maximal_au_dessus_de_la_periode(self):
        self.refus("retention:\n  period_days: 100\n  max_file_age_days: 200\n", "retention.max_file_age_days", "L3",
                   interdits=("200",))


class TestMigrate(unittest.TestCase):
    def test_migrate_ne_touche_pas_aux_nouvelles_cles(self):
        texte = ("jira_cloud_id: abc\njira_token_expires: 2027-01-01\njira_token_warning_days: 10\n"
                 + CYCLES_VALIDES + "patches:\n  2026-Q1: [p]\nretention:\n  period_days: 100\n"
                 "declared_labels:\n  cycle: {prefix: c, labels: [c1]}\n"
                 "discovery_workflow:\n  columns: {A: [s]}\n  start_column: A\n")
        nouveau, changements = flux_config.migrate_text(texte)
        self.assertEqual(nouveau, texte)
        self.assertEqual(changements, [])

    def test_to_public_laisse_les_nouvelles_cles(self):
        i = lire("jira_cloud_id: abc\nretention:\n  period_days: 100\n")
        self.assertEqual(flux_config.to_public(i), i)


if __name__ == "__main__":
    unittest.main()
