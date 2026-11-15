"""
Lecture statique de la migration des quatre colonnes « sans les anciens » de v_team_lead_time_throughput (change masking-sums, tâche 22.1 ; conception D16,
« Grouped year without the old items » ; R-20261105-30 ; R-20261106-52, Q2 (a)).

    bash tests/run_all.sh flow_views     (aucune base)

Règle (D16) : quatre colonnes ajoutées après les existantes, dans cet ordre, sur chaque ligne (les quatre trimestres et l'année groupée) : la médiane et le P85 du
lead time, la médiane et le P85 du cycle time, calculés comme leurs équivalents sur les éléments qui ne sont pas anciens. Une statistique de lead time est montrée
si l'effectif du lead time est montré (d_m), si items_old de la même ligne est montré (d_o) et que m - o >= 5 ; une statistique de cycle time si l'effectif du cycle time
est montré (d_c), si items_old de la même ligne est montré (d_o) et que c - o >= 5 (R-20261106-59, Q1 (a)). Aucune colonne de compte n'est ajoutée. La migration repart de
0037, sa dernière définition de la vue : une fois retirées les lignes des nouvelles colonnes (et les virgules finales), la vue est celle de 0037 mot pour mot. Les parités
avec la base sont dans tests/db/test_flow_lead_time_sans_anciens_vues.py (preuve en conteneur), les fuites dans tests/oracle_masquage.
"""
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOSSIER = RACINE / "db" / "migrations"
SUFFIXE = "_flow_lead_time_without_old.sql"
SUFFIXE_PRECEDENTE = "_flow_lead_time_old_zero.sql"
NOUVELLES = ("lead_median_days_excl_old", "lead_p85_days_excl_old", "cycle_median_days_excl_old", "cycle_p85_days_excl_old")
MARQUE_CTE = "_sans_anc"


def fichier(suffixe):
    candidats = [m for m in sorted(DOSSIER.glob("*.sql")) if m.name.endswith(suffixe)]
    return candidats[0] if len(candidats) == 1 else None


def vue(chemin):
    """Lignes significatives de la vue : de CREATE OR REPLACE VIEW à la ligne qui précède RESET ROLE, sans ligne vide ni ligne de commentaire seul."""
    brut = chemin.read_text(encoding="utf-8").splitlines()
    debut = next(i for i, ligne in enumerate(brut) if ligne.startswith("CREATE OR REPLACE VIEW flow.v_team_lead_time_throughput"))
    fin = next(i for i, ligne in enumerate(brut) if ligne.startswith("RESET ROLE"))
    return [ligne for ligne in brut[debut:fin] if ligne.strip() and not ligne.strip().startswith("--")]


def sans_nouvelles(lignes):
    """Les lignes sans celles des nouvelles colonnes (celles de la vue qui nomment une colonne en `_excl_old` ou une colonne de CTE en `_sans_anc`), sans la
    virgule finale ni l'espace de fin de chaque ligne : ajouter une colonne en fin de liste ajoute une virgule à la ligne qui précède."""
    gardees = [ligne for ligne in lignes if "_excl_old" not in ligne and MARQUE_CTE not in ligne]
    return [re.sub(r",\s*$", "", ligne.rstrip()) for ligne in gardees]


def lignes_nouvelles(lignes):
    return [ligne for ligne in lignes if "_excl_old" in ligne or MARQUE_CTE in ligne]


class MigrationApres0037(unittest.TestCase):
    def test_la_migration_existe_apres_0037_sans_trou_et_la_cite(self):
        nouvelle, precedente = fichier(SUFFIXE), fichier(SUFFIXE_PRECEDENTE)
        self.assertIsNotNone(nouvelle, f"une migration *{SUFFIXE} est attendue")
        self.assertIsNotNone(precedente)
        self.assertEqual(int(nouvelle.name[:4]), int(precedente.name[:4]) + 1)
        numeros = sorted(int(m.name[:4]) for m in DOSSIER.glob("*.sql"))
        self.assertEqual(numeros, list(range(1, len(numeros) + 1)))          # sans trou
        brut = nouvelle.read_text(encoding="utf-8")
        self.assertRegex(brut.splitlines()[0], r"^-- Schéma touché : flow")
        self.assertRegex(brut, r"(?m)^-- Remplace : ")
        self.assertRegex(brut, r"(?m)^-- Retrait\s*:")
        for decision in ("R-20261105-30", "R-20261106-52"):
            self.assertIn(decision, brut)
        self.assertNotRegex(brut, r"(?i)\bjira\b")

    def test_elle_ne_change_que_la_vue_et_garde_ses_droits(self):
        """Une seule vue recréée (CREATE OR REPLACE, droits conservés) : ni GRANT, ni REVOKE, ni table, ni rôle, ni donnée, ni mot de passe."""
        code = re.sub(r"--[^\n]*", "", fichier(SUFFIXE).read_text(encoding="utf-8"))
        self.assertRegex(code, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;.*CREATE\s+OR\s+REPLACE\s+VIEW\s+flow\.v_team_lead_time_throughput\s+AS")
        self.assertRegex(code, r"(?i)\bRESET\s+ROLE\s*;")
        self.assertEqual(len(re.findall(r"(?i)\bCREATE\b", code)), 1)
        self.assertNotRegex(code, r"(?i)\bGRANT\b|\bREVOKE\b")
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+(ROLE|TABLE|FUNCTION)\b|\bLOGIN\b|\bmasking_version\b")

    def test_la_vue_est_celle_de_0037_sans_les_lignes_des_nouvelles_colonnes(self):
        """Toute autre dérive (une règle changée, une colonne existante déplacée) est un changement de règle qui demande sa propre décision (R-20261106-52, Q2 (a))."""
        avant = sans_nouvelles(vue(fichier(SUFFIXE_PRECEDENTE)))
        apres = sans_nouvelles(vue(fichier(SUFFIXE)))
        self.assertEqual(apres, avant)

    def test_quatre_colonnes_en_fin_de_liste_dans_les_deux_branches_dans_l_ordre(self):
        lignes = vue(fichier(SUFFIXE))
        finales = [ligne for ligne in lignes if "_excl_old" in ligne]
        self.assertEqual(len(finales), 4)                                   # la branche des trimestres seule porte les alias ; l'année est sans alias
        self.assertEqual([next(n for n in NOUVELLES if n in ligne) for ligne in finales], list(NOUVELLES))
        texte = "\n".join(lignes)
        annee = texte[texte.index("SELECT y.team"):]
        sans_alias = [ligne for ligne in annee.splitlines() if re.match(r"\s*CASE WHEN y\.d_[mc] AND y\.d_o AND y\.[mc] - y\.o >= 5 THEN round\(y\.(lt|ct)_(med|p85)" + MARQUE_CTE, ligne)]
        self.assertEqual(len(sans_alias), 4)
        # position : la dernière colonne existante est suivie des quatre nouvelles, dans chaque branche
        self.assertRegex(texte, r"AS items_without_commitment,\n(?:[^\n]*_excl_old[^\n]*\n){3}[^\n]*cycle_p85_days_excl_old\n")
        self.assertRegex(texte, r"CASE WHEN y\.d_g THEN y\.g END,\n(?:\s*CASE WHEN y\.d_[mc][^\n]*\n){3}\s*CASE WHEN y\.d_c AND y\.d_o AND y\.c - y\.o >= 5 THEN round\(y\.ct_p85_sans_anc::numeric, 1\) END\n")

    def test_regle_de_visibilite_de_d16_au_plancher(self):
        """Lead time : effectif montré (d_m), items_old de la même ligne montré (d_o) et m - o >= 5 ; cycle time : effectif montré (d_c), items_old montré (d_o) et
        c - o >= 5 ; chaque ligne, année groupée comprise (R-20261106-59, Q1 (a) : la visibilité ne dépend que de cellules publiées)."""
        finales = [ligne for ligne in vue(fichier(SUFFIXE)) if "_excl_old" in ligne]
        for ligne in finales:
            if "lead_" in ligne:
                self.assertRegex(ligne, r"CASE WHEN p\.d_m AND p\.d_o AND p\.m - p\.o >= 5 THEN round\(p\.lt_(med|p85)" + MARQUE_CTE)
            else:
                self.assertRegex(ligne, r"CASE WHEN p\.d_c AND p\.d_o AND p\.c - p\.o >= 5 THEN round\(p\.ct_(med|p85)" + MARQUE_CTE)
        texte = "\n".join(vue(fichier(SUFFIXE)))
        annee = texte[texte.index("SELECT y.team"):]
        self.assertEqual(len(re.findall(r"CASE WHEN y\.d_m AND y\.d_o AND y\.m - y\.o >= 5 THEN", annee)), 2)
        self.assertEqual(len(re.findall(r"CASE WHEN y\.d_c AND y\.d_o AND y\.c - y\.o >= 5 THEN", annee)), 2)

    def test_les_percentiles_excluent_les_anciens_comme_les_existants_les_incluent(self):
        """Mêmes percentiles, mêmes arrondis, sur les éléments dont `ancien` n'est pas vrai (un `ancien` nul n'est pas un ancien : il est dans c - o)."""
        lignes = lignes_nouvelles(vue(fichier(SUFFIXE)))
        cte = [ligne for ligne in lignes if "percentile_cont" in ligne]
        self.assertEqual(len(cte), 8)                                      # quatre dans par_trimestre, quatre dans annee
        attendus = {"lt_med": ("0.5", "lead_days"), "lt_p85": ("0.85", "lead_days"), "ct_med": ("0.5", "cycle_days"), "ct_p85": ("0.85", "cycle_days")}
        for nom, (rang, colonne) in attendus.items():
            ses = [ligne for ligne in cte if f"AS {nom}{MARQUE_CTE}" in ligne]
            self.assertEqual(len(ses), 2, nom)
            for ligne in ses:
                self.assertIn(f"percentile_cont({rang}) WITHIN GROUP (ORDER BY {colonne}) FILTER (WHERE ancien IS NOT TRUE)", ligne)

    def test_un_created_at_nul_est_compte_comme_non_ancien(self):
        """R-20261106-58 : `ancien` vaut NULL quand created_at est nul (l'élément a pourtant un cycle time). `count(*) FILTER (WHERE ancien)` ne le compte pas parmi les
        anciens, donc c - o le compte ; le percentile le garde aussi (`IS NOT TRUE`), jamais `WHERE NOT ancien`, qui l'écarterait. Contrôle de texte seulement :
        flow.issues.created_at est NOT NULL (0002), aucune ligne synthétique ne peut porter un created_at nul en base."""
        texte = "\n".join(vue(fichier(SUFFIXE)))
        self.assertNotRegex(texte, r"(?i)FILTER\s*\(\s*WHERE\s+NOT\s+ancien")
        self.assertEqual(len(re.findall(r"FILTER \(WHERE ancien IS NOT TRUE\)", texte)), 8)
        self.assertEqual(len(re.findall(r"count\(\*\) FILTER \(WHERE ancien\) AS o", texte)), 2)      # o ne compte que les `ancien` vrais, dans les deux CTE

    def test_aucune_colonne_de_compte_n_est_ajoutee(self):
        texte = "\n".join(lignes_nouvelles(vue(fichier(SUFFIXE))))
        self.assertNotRegex(texte, r"(?i)mask_count|count\(")


if __name__ == "__main__":
    unittest.main()
