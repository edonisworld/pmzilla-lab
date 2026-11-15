"""
La vue v_team_delivery_fields_coverage (change jira-delivery-fields, design D9 ; spec jira-flow-views « Delivery fields coverage view »,
« Coverage view masking », « Known views »).

    bash tests/run_all.sh flow_views

Partie sans base : la migration se lit comme du texte (retrouvée par son suffixe, jamais par son numéro) et le masquage du lecteur
(`masquer_vue`) s'essaie sur des lignes inventées, telles que la vue les rend (un nul est une cellule déjà masquée dans la base). Les
scénarios sur la base jetable sont dans tests/db/test_flow_delivery_fields.py (dbtest de l'auteur). La migration, 0033_flow_delivery_fields_view.sql, se retrouve
par son suffixe dans le code (jamais par son numéro) ; son nom complet n'est écrit qu'ici, pour le sélecteur de suites.
"""
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402
from flow_views_messages import CATALOGS  # noqa: E402

SUFFIXE = "_flow_delivery_fields_view.sql"
VUE = "v_team_delivery_fields_coverage"
NOMS = ["team", "quarter_start", "item_kind", "items", *fv.COLONNES_COUVERTURE]


def sans_commentaires(texte: str) -> str:
    return re.sub(r"--[^\n]*", "", texte)


def migration() -> str:
    candidats = sorted((RACINE / "db" / "migrations").glob(f"*{SUFFIXE}"))
    assert len(candidats) == 1, f"une migration *{SUFFIXE} est attendue"
    return candidats[0].read_text(encoding="utf-8")


def ligne(items, remplis=None, equipe="Equipe A", genre="story", **par_champ):
    """Une ligne telle que la vue la rend : `remplis` pour tous les champs, ou champ par champ (with_sprint=3…)."""
    valeurs = {c: remplis for c in fv.COLONNES_COUVERTURE}
    valeurs.update({f"with_{k}": v for k, v in par_champ.items()})
    return (equipe, "2026-04-01", genre, items, *[valeurs[c] for c in fv.COLONNES_COUVERTURE])


def cellules(lignes, seuil=5):
    return fv.masquer_vue(VUE, NOMS, lignes, seuil)


class Liste(unittest.TestCase):
    def test_la_vue_est_connue_et_decrite_dans_les_deux_langues(self):
        self.assertIn(VUE, fv.VUES)
        self.assertEqual(len(fv.VUES), len(set(fv.VUES)))
        for langue in ("fr", "en"):
            self.assertTrue(CATALOGS[langue][f"desc_{VUE}"].strip())

    def test_bornes_declarees_pour_chaque_colonne_de_comptage(self):
        self.assertEqual(set(fv.BORNES[VUE]), {"items", *fv.COLONNES_COUVERTURE})
        for colonne in ("items", *fv.COLONNES_COUVERTURE):
            self.assertIn(colonne, fv.COLONNES_COMPTE)

    def test_un_champ_de_livraison_par_colonne(self):
        self.assertEqual(len(fv.COLONNES_COUVERTURE), 16)
        self.assertEqual(len(set(fv.COLONNES_COUVERTURE)), 16)


class MigrationStatique(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texte = migration()
        cls.code = sans_commentaires(cls.texte)

    def test_une_vue_sous_le_proprietaire_sans_donnee_ni_table(self):
        self.assertRegex(self.texte.splitlines()[0], r"^-- Schéma touché : flow")
        self.assertEqual(re.findall(r"(?i)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+flow\.(\w+)", self.code), [VUE])
        self.assertLess(re.search(r"(?i)SET\s+LOCAL\s+ROLE\s+pmzilla_owner", self.code).start(), re.search(r"(?i)CREATE\s+VIEW", self.code).start())
        self.assertNotRegex(self.code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(self.code, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+(ROLE|TABLE)\b|\bLOGIN\b")

    def test_select_au_seul_role_des_vues(self):
        self.assertEqual(len(re.findall(r"(?i)\bGRANT\b", self.code)), 1)
        self.assertRegex(self.code, rf"(?is)GRANT\s+SELECT\s+ON\s+flow\.{VUE}\s+TO\s+pmzilla_flow_views\s*;")
        revoke = re.search(r"(?is)\bREVOKE\b.*?;", self.code).group(0)
        for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views"):
            self.assertRegex(revoke, rf"\b{role}\b")
        self.assertLess(self.code.index("REVOKE"), self.code.index("GRANT"))

    def test_colonnes_de_la_vue_et_aucune_colonne_de_valeur(self):
        sortie = re.search(r"(?is)SELECT\s+p\.team,(.*?)FROM\s+par_equipe\s+p\s*;", self.code).group(1)
        nommees = re.findall(r"(?i)\bAS\s+(\w+)", sortie)
        self.assertEqual(["items", *fv.COLONNES_COUVERTURE], nommees)
        for interdit in ("key", "summary", "title", "description", "assignee", "reporter", "sprint_id", "object_id", "number", "short_name",
                         "option_id", "value", "kind", "project"):
            self.assertNotIn(interdit, [n.lower() for n in nommees] + ["team", "quarter_start", "item_kind"])
        self.assertNotRegex(sortie, r"(?i)\b(issue_key|object_id|sprint_id|short_name|value|option_id)\b")

    def test_masquage_dans_la_vue_au_plancher_de_cinq(self):
        self.assertIn("flow.mask_count(p.n)", self.code)
        self.assertEqual(len(re.findall(r"p\.c_\w+\s*>=\s*5\s+AND\s+p\.n\s*-\s*p\.c_\w+\s*>=\s*5", self.code)), len(fv.COLONNES_COUVERTURE))

    def test_trimestres_clos_epics_a_part_et_pas_de_ligne_du_produit(self):
        self.assertIn("generate_series(1, 4)", self.code)
        self.assertRegex(self.code, r"(?i)lower\(i\.type\)\s*=\s*'epic'")
        self.assertNotIn("(produit)", self.code)
        self.assertRegex(self.code, r"(?i)i\.out_of_export_at\s+IS\s+NULL")

    def test_numerotee_apres_la_migration_des_tables(self):
        numeros = {p.name.split("_", 1)[1]: int(p.name.split("_", 1)[0])
                   for p in (RACINE / "db" / "migrations").glob("*.sql")}
        self.assertEqual(numeros[SUFFIXE.lstrip("_")], numeros["flow_delivery_fields.sql"] + 1)


class Masquage(unittest.TestCase):
    """Spec « Coverage view masking » : le lecteur rend des cellules structurées {masked: under_threshold}."""

    def test_une_equipe_un_trimestre_douze_items_sept_avec_sprint(self):
        r = cellules([ligne(12, None, sprint=7)])[0]
        self.assertEqual(r["items"], {"value": 12})
        self.assertEqual(r["with_sprint"], {"value": 7})

    def test_peu_d_items_avec_un_champ_masque(self):
        r = cellules([ligne(12, None, sprint=None)])[0]          # trois remplis : la vue rend un nul
        self.assertEqual(r["items"], {"value": 12})
        self.assertEqual(r["with_sprint"], {"value": None, "masked": "under_threshold", "threshold": 5})

    def test_peu_d_items_sans_le_champ_masque_aussi(self):
        r = cellules([ligne(20, None, target_version=None)])[0]          # dix-huit remplis, deux sans : la vue rend un nul
        self.assertEqual(r["with_target_version"], {"value": None, "masked": "under_threshold", "threshold": 5})

    def test_moins_de_cinq_items_masque_les_items(self):
        r = cellules([ligne(None, None)])[0]
        self.assertEqual(r["items"], {"value": None, "masked": "under_threshold", "threshold": 5})
        self.assertTrue(all("masked" in r[c] for c in fv.COLONNES_COUVERTURE))

    def test_un_seuil_releve_masque_davantage_jamais_moins(self):
        r = cellules([ligne(12, None, sprint=7, isp=2)], seuil=10)[0]
        self.assertEqual(r["items"], {"value": 12})
        self.assertIn("masked", r["with_sprint"])          # sept remplis, cinq sans : sous dix
        r = cellules([ligne(30, None, sprint=14)], seuil=10)[0]
        self.assertEqual(r["with_sprint"], {"value": 14})
        r = cellules([ligne(30, None, sprint=25)], seuil=10)[0]
        self.assertIn("masked", r["with_sprint"])          # cinq sans le champ : sous dix

    def test_aucune_cellule_ne_montre_ni_cle_ni_valeur_hors_comptes(self):
        r = cellules([ligne(12, None, sprint=7), ligne(30, 10, genre="epic")])
        self.assertEqual(r[1]["item_kind"], {"value": "epic"})
        self.assertEqual(r[1]["with_sprint"], {"value": 10})


if __name__ == "__main__":
    unittest.main()
