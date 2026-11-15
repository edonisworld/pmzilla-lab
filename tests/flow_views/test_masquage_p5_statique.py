"""
Lecture statique de P5 et de la voisine seule candidate, côté Python et côté SQL (change du masquage des sommes, R-144, groupe 20, tâche 20.1 ; décision
R-20261104-49, réponses Q1 (e) et Q2 (a) ; conception D15, P5 et B15 ; revue 19.1, correction C1 : les endroits qui LISENT la borne enregistrée).

    bash tests/run_all.sh flow_views

N'importe aucun module de base : lit seulement le texte de db/migrations/*_flow_masquage_propagation.sql (la migration du groupe 6) et de
tools/flow_views.py. Vérifie que P5 est construite aux deux endroits, dans le même ordre (après P4, avant la propagation), que la relation des sommes n'est
pas traversée par la règle du voisin des deux côtés, et que la borne de départ d'une voisine seule candidate (None en Python, NULL en SQL) est lue comme
« sans borne haute » là où les bornes de départ sont construites (`_construire`, et `hi0` : `greatest` ignorerait le NULL et garderait T - 1).
Replaces: rien (tests neufs). Removal: tombent avec P5 et avec la règle de la voisine seule (B15).
"""
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402,F401

DOSSIER = RACINE / "db" / "migrations"
SUFFIXE = "_flow_masquage_propagation.sql"


def sql_code():
    candidats = [m for m in sorted(DOSSIER.glob("*.sql")) if m.name.endswith(SUFFIXE)]
    assert len(candidats) == 1, f"une migration *{SUFFIXE} est attendue"
    return re.sub(r"--[^\n]*", "", candidats[0].read_text(encoding="utf-8"))


def sql_corps():
    trouve = re.search(r"(?is)CREATE\s+FUNCTION\s+flow\.photo_masque\(.*?AS\s+\$\$(.*?)\$\$;", sql_code())
    assert trouve
    return trouve.group(1)


def python_construire():
    source = (RACINE / "tools" / "flow_views.py").read_text(encoding="utf-8")
    debut = source.index("    def _construire(self) -> dict:")
    return source[debut:source.index("    def _epingles(self")]


class P5ConstruiteDansLeMemeOrdre(unittest.TestCase):
    def test_python_construit_p5_apres_p4_et_avant_le_rendu(self):
        corps = python_construire()
        positions = [corps.index(m) for m in ("p1.append(", "p2.append(", "p3.append(", "p4.append(", "p5.append(")]
        self.assertEqual(positions, sorted(positions))                                   # P1, P2, P3, P4, puis P5
        self.assertLess(corps.index("p5.append("), corps.index("return {"))
        self.assertIn("for groupe in (p1, p2, p3, p4)]", corps)                          # les quatre premiers genres triés comme avant
        self.assertRegex(corps, r"toutes\s*=\s*\[rel for groupe in relations for rel in groupe\]\s*\+\s*\[e\[0\] for e in p5\]")      # P5 en dernier

    def test_sql_construit_p5_apres_p4_et_avant_le_rangement_des_termes(self):
        corps = sql_corps()
        marques = ["IF paire_de[c] > c", "IF ver[i] IS NULL AND var_d[i] > 0", "passe_p IN 1..2", "FOR t_i IN 1..n LOOP", "hors_anneau[nr] := true;",
                   "r_deb := ARRAY[]"]
        positions = [corps.index(m) for m in marques]
        self.assertEqual(positions, sorted(positions))                                   # P1, P2, P3, P4, puis P5, puis le rangement des termes

    def test_les_deux_cotes_creent_le_d_latent_des_lignes_sans_d_r_et_sa_relation(self):
        corps = python_construire()
        self.assertIn('("Dt", i)', corps)                                                # D_t latent, rang de colonne 100 comme D_r
        self.assertRegex(corps, r"\(\*self\._cle_ligne\(i\), 100\), \(\"Dt\", i\)")
        sql = sql_corps()
        self.assertRegex(sql, r"ELSIF\s+p5_ok\[i\]\s+THEN\s+nv\s*:=\s*nv\s*\+\s*1;\s*var_dt\[i\]\s*:=\s*nv;\s*v_row\[nv\]\s*:=\s*i;\s*v_col\[nv\]\s*:=\s*10;")
        # créés - sans affects - D_t = 0 : mêmes coefficients des deux côtés (+1, -1, -1) et même second membre 0
        self.assertRegex(sql, r"tv\s*:=\s*tv\s*\|\|\s*var_ix\[\(i - 1\) \* 9 \+ 6\]\s*\|\|\s*var_ix\[\(i - 1\) \* 9 \+ 7\]\s*\|\|\s*var_dt\[i\];\s*"
                              r"tc\s*:=\s*tc\s*\|\|\s*1::smallint\s*\|\|\s*\(-1\)::smallint\s*\|\|\s*\(-1\)::smallint;")
        self.assertIn("((crees, 1), (sans, -1), (d_de(i), -1))", corps)

    def test_les_sommes_de_p5_listent_les_d_d_equipe_en_moins_un_puis_celui_du_produit_en_plus_un_des_deux_cotes(self):
        corps = python_construire()
        self.assertIn("((d_de(p), 1), *((d_de(e), -1) for e in equipes))", corps)
        sql = sql_corps()
        debut = sql.index("hors_anneau[nr] := true;")
        bloc = sql[debut:sql.index("r_deb := ARRAY[]")]
        self.assertLess(bloc.index("tc := tc || (-1)::smallint;"), bloc.index("tc := tc || 1::smallint;"))      # l'équipe avant le produit
        self.assertRegex(bloc, r"CASE WHEN var_d\[j\] > 0 THEN var_d\[j\] ELSE var_dt\[j\] END")

    def test_p5_n_est_construite_que_si_chaque_ligne_d_equipe_et_le_produit_ont_leurs_deux_cellules(self):
        corps = python_construire()
        self.assertRegex(corps, r"if equipes and all\(\(i, \"defects_created\"\) in presentes and \(i, \"defects_without_affects\"\) in presentes for i in lignes\)")
        sql = sql_corps()
        self.assertRegex(sql, r"IF\s+eq\[i\]\s*=\s*prod\s+AND\s+ver\[i\]\s+IS\s+NULL\s+THEN\s+ok5\s*:=\s*false;")
        self.assertRegex(sql, r"IF\s+ok5\s+THEN\s+p5_ok\[i\]\s*:=\s*true;")


class LaRelationDesSommesNEstPasTraversee(unittest.TestCase):
    def test_python_exclut_la_relation_des_sommes_des_anneaux(self):
        source = (RACINE / "tools" / "flow_views.py").read_text(encoding="utf-8")
        debut = source.index("    def _voisine(self")
        corps = source[debut:source.index("    def propager(self")]
        self.assertIn('hors_anneau = u.get("hors_anneau")', corps)
        self.assertRegex(corps, r"for \(_, _, termes\), hors in zip\(u\[\"relations\"\], hors_anneau\) if not hors\]")

    def test_sql_exclut_la_relation_des_sommes_des_anneaux(self):
        sql = sql_corps()
        self.assertRegex(sql, r"FOR\s+r\s+IN\s+1\.\.nr\s+LOOP\s+CONTINUE\s+WHEN\s+coalesce\(hors_anneau\[r\],\s*false\);\s*touche\s*:=\s*false;")


class LaBorneDeLaVoisineSeuleEstLueCommeSansBorneHaute(unittest.TestCase):
    """C1 de la revue 19.1 : le producteur de la borne (`_voisine`, `haut`) ET ses consommateurs (`_construire`, `hi0`) changent ensemble."""

    def test_python_producteur_et_consommateur(self):
        source = (RACINE / "tools" / "flow_views.py").read_text(encoding="utf-8")
        self.assertIn("return y, (max(self.seuil - 1, min(autres)) if autres else None)", source)             # producteur : None sans autre candidate
        self.assertIn('hi[v] = None if raison[1] is None else max(t - 1, raison[1])', source)                  # consommateur : _construire
        self.assertNotIn("max(self.seuil - 1, min(autres)) if autres else self.seuil - 1", source)            # l'ancienne valeur T - 1
        self.assertNotRegex(source, r"(?m)^\s*hi\[v\]\s*=\s*max\(t - 1,\s*raison\[1\]\)\s*$")                  # l'ancien consommateur, qui lèverait TypeError sur None

    def test_sql_producteur_et_consommateur(self):
        sql = sql_corps()
        self.assertRegex(sql, r"haut\s*:=\s*CASE\s+WHEN\s+plus_petite_autre\s+IS\s+NULL\s+THEN\s+NULL\s+ELSE\s+greatest\(t - 1,\s*plus_petite_autre\)\s+END;")
        self.assertRegex(sql, r"ELSIF\s+regle\[ix\]\s*=\s*6\s+THEN\s+IF\s+reg_a\[ix\]\s+IS\s+NOT\s+NULL\s+THEN\s+hi0\[v\]\s*:=\s*greatest\(t - 1,\s*reg_a\[ix\]\);\s+END IF;")
        self.assertNotRegex(sql, r"THEN\s+t - 1\s+ELSE\s+greatest\(t - 1,\s*plus_petite_autre\)")                # l'ancienne valeur T - 1
        self.assertNotRegex(sql, r"ELSIF\s+regle\[ix\]\s*=\s*6\s+THEN\s+hi0\[v\]\s*:=\s*greatest")             # l'ancien consommateur : greatest ignorait le NULL


if __name__ == "__main__":
    unittest.main()
