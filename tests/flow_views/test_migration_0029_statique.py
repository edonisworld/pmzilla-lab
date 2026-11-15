"""
Test statique (aucune base, aucun module de base) de la migration 0029 (mothra-slices tâche 15.2, décision R-20261030-08) : tasks_without_team,
blocked et unplanned passent par flow.mask_count et ne sont jamais plus permissifs que dans la migration 0026.

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v
"""
import re
import unittest
from pathlib import Path

from test_contrat_vues import colonnes_du_select

RACINE = Path(__file__).resolve().parents[2]
MIGRATIONS = RACINE / "db" / "migrations"

# vue -> (colonne de compte, expression de 0026, expression de 0029 ; le reste de 0026 est gardé dans l'appel)
COMPTES = {
    "v_task_without_team_share": ("tasks_without_team", "CASE WHEN p.sans >= 5 AND p.avec >= 5 THEN p.sans END",
                                  "flow.mask_count(CASE WHEN p.avec >= 5 THEN p.sans END)"),
    "v_team_blocked_share": ("blocked", "CASE WHEN p.b >= 5 AND p.r >= 5 THEN p.b END", "flow.mask_count(CASE WHEN p.r >= 5 THEN p.b END)"),
    "v_unplanned_share": ("unplanned", "CASE WHEN p.u >= 5 AND p.r >= 5 THEN p.u END", "flow.mask_count(CASE WHEN p.r >= 5 THEN p.u END)"),
}


def sans_commentaires(texte: str) -> str:
    return re.sub(r"--[^\n]*", "", texte)


def migration(suffixe: str) -> str:
    candidats = sorted(MIGRATIONS.glob(f"*{suffixe}"))
    assert len(candidats) == 1, f"une migration *{suffixe} est attendue"
    return sans_commentaires(candidats[0].read_text(encoding="utf-8"))


def definition(sql: str, vue: str) -> str:
    return re.search(rf"(?is)CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+flow\.{vue}\s+AS(.*?);", sql).group(1)


def elements(sql: str, vue: str) -> dict:
    """Colonne -> expression (normalisée : espaces uniques) du SELECT final de la vue."""
    resultat = {}
    for element in colonnes_du_select(definition(sql, vue)):
        m = re.match(r"(?s)(.*?)\s+AS\s+(\w+)$", element.strip())
        nom, expression = (m.group(2), m.group(1)) if m else (element.split(".")[-1], element)
        resultat[nom] = " ".join(expression.split())
    return resultat


def colonnes_dans_l_ordre(sql: str, vue: str) -> list:
    return list(elements(sql, vue))


class Migration0029(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nouvelle = migration("_flow_slice1_mask_comptes.sql")
        cls.ancienne = migration("_flow_slice1_views.sql")

    def test_la_migration_redefinit_exactement_les_trois_vues(self):
        self.assertEqual(sorted(re.findall(r"(?i)\bCREATE\s+OR\s+REPLACE\s+VIEW\s+flow\.(\w+)", self.nouvelle)), sorted(COMPTES))
        self.assertNotRegex(self.nouvelle, r"(?i)\bCREATE\s+VIEW\b")

    def test_mask_count_enveloppe_les_trois_colonnes(self):
        for vue, (colonne, _, nouvelle) in COMPTES.items():
            self.assertEqual(elements(self.nouvelle, vue)[colonne], nouvelle, f"{vue}.{colonne}")
            self.assertRegex(elements(self.nouvelle, vue)[colonne], r"^flow\.mask_count\(")

    def test_l_expression_de_0026_est_bien_celle_que_la_migration_remplace(self):
        for vue, (colonne, ancienne, _) in COMPTES.items():
            self.assertEqual(elements(self.ancienne, vue)[colonne], ancienne, f"{vue}.{colonne}")

    def test_la_condition_de_reste_de_0026_est_gardee(self):
        """mask_count ne couvre pas le reste : la condition de reste (>= 5) de 0026 doit rester dans la nouvelle expression."""
        for vue, (colonne, _, nouvelle) in COMPTES.items():
            self.assertRegex(nouvelle, r"WHEN p\.(avec|r) >= 5 THEN")
            self.assertEqual(sorted(re.findall(r"p\.(\w+) >= 5", nouvelle)), sorted(re.findall(r"p\.(avec|r) >= 5", COMPTES[vue][1])))

    def test_share_percent_est_inchangee_mot_pour_mot(self):
        for vue in COMPTES:
            self.assertEqual(elements(self.nouvelle, vue)["share_percent"], elements(self.ancienne, vue)["share_percent"], vue)

    def test_memes_colonnes_dans_le_meme_ordre_et_autres_expressions_inchangees(self):
        for vue, (colonne, _, _) in COMPTES.items():
            nouvelles, anciennes = elements(self.nouvelle, vue), elements(self.ancienne, vue)
            self.assertEqual(list(nouvelles), list(anciennes), vue)
            for nom in nouvelles:
                if nom != colonne:
                    self.assertEqual(nouvelles[nom], anciennes[nom], f"{vue}.{nom}")

    def test_le_corps_des_vues_hors_select_final_est_inchange(self):
        for vue in COMPTES:
            n, a = " ".join(definition(self.nouvelle, vue).split()), " ".join(definition(self.ancienne, vue).split())
            self.assertEqual(n.split("SELECT p.")[0], a.split("SELECT p.")[0], vue)

    def test_aucun_droit_donne_ni_donnee_ni_table(self):
        self.assertNotRegex(self.nouvelle, r"(?i)\bGRANT\b|\bREVOKE\b|\bCREATE\s+(TABLE|ROLE|FUNCTION)\b|\bALTER\s+ROLE\b|\bPASSWORD\b")
        self.assertNotRegex(self.nouvelle, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertLess(re.search(r"(?i)SET\s+LOCAL\s+ROLE\s+pmzilla_owner", self.nouvelle).start(), re.search(r"(?i)CREATE\s+OR\s+REPLACE", self.nouvelle).start())


if __name__ == "__main__":
    unittest.main()
