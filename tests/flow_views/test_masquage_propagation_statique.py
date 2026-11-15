"""
Lecture statique de la migration de la propagation des bornes (change du masquage des sommes, R-144, groupe 6, tâches 6.2 et 6.5 ; conception D9, D12, D15).

    bash tests/run_all.sh flow_views

N'importe aucun module de base : lit seulement le texte de db/migrations/*_flow_masquage_propagation.sql et tools/flow_views.py. Les tests avec base
(X23 contre la vue, limites abaissées, parité sur photos de plusieurs semaines) sont dans tests/db/test_masquage_propagation_vues.py, lancé par le
dbtest de l'auteur. Cette migration suit celle du masquage des sommes (0022) sans la modifier : le marqueur monte à 2 dans un fichier à elle.
"""
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

DOSSIER = RACINE / "db" / "migrations"
SUFFIXE = "_flow_masquage_propagation.sql"
SUFFIXE_SOMMES = "_flow_masquage_somme.sql"
FONCTIONS = ("propager_bornes", "photo_masque")


def fichier(suffixe):
    candidats = [m for m in sorted(DOSSIER.glob("*.sql")) if m.name.endswith(suffixe)]
    return candidats[0] if len(candidats) == 1 else None


def texte():
    chemin = fichier(SUFFIXE)
    assert chemin is not None, f"une migration *{SUFFIXE} est attendue"
    return chemin.read_text(encoding="utf-8")


def code():
    return re.sub(r"--[^\n]*", "", texte())


def corps_de(fonction):
    trouve = re.search(rf"(?is)CREATE\s+FUNCTION\s+flow\.{fonction}\(.*?AS\s+\$\$(.*?)\$\$;", code())
    assert trouve, fonction
    return trouve.group(1)


def lectures_de_table(corps):
    """Vraies lectures de table : `FROM` ou `JOIN` suivi d'un nom (éventuellement qualifié) qui n'est PAS un appel de fonction (`nom(`). Un
    `FROM flow.propager_bornes(` ou `FROM generate_series(` n'est pas une lecture de table ; `IS NOT DISTINCT FROM` et le `IN ARRAY` d'un FOREACH non plus."""
    texte_ = re.sub(r"(?is)\bFOREACH\b.*?\bIN\s+ARRAY\b", "", corps)
    texte_ = re.sub(r"(?i)\bIS\s+(?:NOT\s+)?DISTINCT\s+FROM\b", "", texte_)
    identifiant = r'(?:"[^"]+"|[A-Za-z_][\w$]*)'
    return [m for m in re.findall(rf"(?i)\b(?:FROM|JOIN)\s+({identifiant}(?:\.{identifiant})?)(?!\s*\()(?=\s|$|;|\))", texte_)]


def formule(ligne):
    """Évalue une ligne de formule de la migration (`1 + V x (2M + 3)`, `C + 1`, `2 x W + 1`) avec des valeurs données."""
    def evaluer(valeurs):
        expression = ligne.replace("x", "*")
        expression = re.sub(r"(\d)([A-Z])", r"\1*\2", expression)        # « 2M » : 2 * M
        return eval(expression, {"__builtins__": {}}, valeurs)           # noqa: S307 : texte du dépôt, jamais une entrée extérieure
    return evaluer


def lignes_de_formule(nom):
    return re.findall(rf"(?m)^-- {nom} (.*?)\s*$", texte())


class LectureDeTable(unittest.TestCase):
    def test_un_appel_de_fonction_n_est_pas_une_lecture(self):
        self.assertEqual(lectures_de_table("FOR rec IN SELECT * FROM flow.propager_bornes(a, b) LOOP x := 1; END LOOP;"), [])
        self.assertEqual(lectures_de_table("(SELECT array_agg(g) FROM generate_series(1, nv) AS g)"), [])

    def test_une_table_est_une_lecture(self):
        self.assertEqual(lectures_de_table("x := (SELECT count(*) FROM flow.version_photo_rows);"), ["flow.version_photo_rows"])
        self.assertEqual(lectures_de_table("SELECT 1 FROM flow.issues i JOIN flow.teams t ON true"), ["flow.issues", "flow.teams"])


class Fichier(unittest.TestCase):
    def test_la_migration_suit_celle_des_sommes_et_ne_la_modifie_pas(self):
        propagation, sommes = fichier(SUFFIXE), fichier(SUFFIXE_SOMMES)
        self.assertIsNotNone(propagation)
        self.assertIsNotNone(sommes)
        self.assertGreater(int(propagation.name[:4]), int(sommes.name[:4]))
        self.assertNotIn("masquage_somme", propagation.name)                 # une seule migration porte ce nom (le test de 0022 la retrouve par lui)
        numeros = sorted(int(m.name[:4]) for m in DOSSIER.glob("*.sql"))
        self.assertEqual(numeros, list(range(1, len(numeros) + 1)))          # sans trou

    def test_proprietaire_sans_donnee_sans_mot_de_passe_sans_role(self):
        brut = texte()
        c = code()
        self.assertRegex(brut.splitlines()[0], r"^-- Schéma touché : flow")
        self.assertRegex(c, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;.*CREATE\s+FUNCTION")
        self.assertRegex(c, r"(?i)\bRESET\s+ROLE\s*;")
        self.assertNotRegex(c, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(c, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+(ROLE|TABLE)\b|\bLOGIN\b")

    def test_la_migration_dit_ce_qu_elle_remplace_et_sa_condition_de_retrait(self):
        brut = texte()
        self.assertRegex(brut, r"(?m)^-- Remplace : ")
        self.assertRegex(brut, r"Retrait\s*:")

    def test_aucun_nom_de_change_ni_d_equipe_reelle(self):
        brut = texte()
        self.assertNotIn("masking" + "-sums", brut)                           # jamais le nom exact d'un change ouvert dans un fichier du code
        self.assertNotRegex(brut, r"(?i)\bjira\b")


class Fonctions(unittest.TestCase):
    def test_chaque_fonction_est_pure_plpgsql_immutable_parallel_safe_search_path_ferme(self):
        for nom in FONCTIONS:
            entete = re.search(rf"(?is)CREATE\s+FUNCTION\s+flow\.{nom}\(.*?AS\s+\$\$", code()).group(0)
            self.assertRegex(entete, r"(?is)LANGUAGE\s+plpgsql\s+IMMUTABLE\s+PARALLEL\s+SAFE\s+SET\s+search_path\s*=\s*pg_catalog,\s*pg_temp", nom)
            self.assertNotRegex(entete, r"(?i)SECURITY\s+DEFINER", nom)

    def test_aucune_table_lue_aucun_sql_dynamique_aucune_ecriture(self):
        for nom in FONCTIONS:
            corps = corps_de(nom)
            self.assertEqual(lectures_de_table(corps), [], nom)
            self.assertNotRegex(corps, r"(?i)\bEXECUTE\b", nom)
            self.assertNotRegex(corps, r"(?i)\b(INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|TRUNCATE|CREATE\s)", nom)

    def test_execute_au_seul_role_des_vues(self):
        c = code()
        for nom in FONCTIONS:
            revoke = re.search(rf"(?is)REVOKE\s+ALL\s+ON\s+FUNCTION\s+flow\.{nom}\(([^)]*)\)\s+FROM\s+([^;]*);", c)
            self.assertIsNotNone(revoke, nom)
            for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views"):
                self.assertRegex(revoke.group(2), rf"\b{role}\b", f"{nom} : {role}")
            accords = re.findall(rf"(?is)GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+flow\.{nom}\(([^)]*)\)\s+TO\s+([^;]*);", c)
            self.assertEqual([a[1].strip() for a in accords], ["pmzilla_flow_views"], nom)
            self.assertEqual(accords[0][0], revoke.group(1), f"{nom} : la signature du REVOKE et du GRANT")

    def test_les_formules_de_limite_sont_celles_des_constantes_python(self):
        lignes = lignes_de_formule("PROPAGATION-MAX")
        self.assertEqual(lignes, ["1 + V x (2M + 3)"])
        for v, m in ((0, 5), (3, 11), (7, 40)):
            self.assertEqual(formule(lignes[0])({"V": v, "M": m}), fv.propagation_max(v, m), (v, m))
        lignes = lignes_de_formule("PROPAGATION-ZERO-MAX")
        self.assertEqual(lignes, ["4 x (V + R) + 10"])
        for v, r in ((0, 0), (12, 30), (70, 74)):
            self.assertEqual(formule(lignes[0])({"V": v, "R": r}), fv.propagation_zero_max(v, r), (v, r))
        lignes = lignes_de_formule("LOOP-MAX")
        self.assertEqual(lignes, ["C + 1"])
        for c in (0, 4, 30):
            self.assertEqual(formule(lignes[0])({"C": c}), fv.boucle_max(c), c)
        lignes = lignes_de_formule("PASSES-MAX")
        self.assertEqual(lignes, ["2 x W + 1"])
        for w in (0, 1, 9, 30):
            self.assertEqual(formule(lignes[0])({"W": w}), fv.passes_max(w), w)

    def test_les_formules_du_code_sont_celles_des_lignes_declarees(self):
        corps = corps_de("photo_masque")
        self.assertRegex(corps, r"limite_p\s*:=\s*coalesce\(lim_balayages,\s*1\s*\+\s*nv\s*\*\s*\(2\s*\*\s*borne_m\s*\+\s*3\)\)")
        self.assertRegex(corps, r"limite_b\s*:=\s*coalesce\(lim_boucle,\s*pub_n\s*\+\s*1\)")
        self.assertRegex(corps, r"least\(limite_p,\s*4\s*\*\s*\(nv\s*\+\s*nr\)\s*\+\s*10\)")      # la lecture « m = 0 » : PROPAGATION-ZERO-MAX
        # M2 (a) de la fiche R-20261104-6 : une limite atteinte de la lecture « m = 0 » est une exception (échec fermé), jamais un écart de la lecture
        self.assertRegex(corps, r"IF\s+hors3\s+THEN\s+RAISE\s+EXCEPTION")
        self.assertNotRegex(corps, r"lecture2")
        self.assertNotRegex(code(), r"(?i)\bEXCEPTION\s+WHEN\b")                                     # PARALLEL SAFE : aucun sous-bloc
        self.assertRegex(corps, r"limite_s\s*:=\s*2\s*\*\s*w\s*\+\s*1")
        self.assertRegex(corps, r"borne_m\s*:=\s*\(somme_pub\s*\+\s*t\)\s*\*\s*\(nv\s*\+\s*1\)")      # M = (somme des cellules publiées + T) x (V + 1)

    def test_limites_atteintes_levent_une_exception(self):
        propager = corps_de("propager_bornes")                                             # rend un drapeau « limite atteinte », ne lève rien
        self.assertNotRegex(propager, r"(?i)\bRAISE\b")
        self.assertRegex(propager, r"IF\s+balayage\s*>=\s*limite\s+THEN\s+hors_limite\s*:=\s*true")
        self.assertRegex(propager, r"(?s)h\[x\]\s*>\s*borne_m\)\s*THEN\s+hors_limite\s*:=\s*true")
        self.assertRegex(propager, r"limite_atteinte\s*:=\s*hors_limite")
        self.assertRegex(code(), r"(?is)RETURNS\s+TABLE\s*\(rang\s+integer,\s*borne_lo\s+bigint,\s*borne_hi\s+bigint,\s*vide\s+boolean,\s*limite_atteinte\s+boolean\)")
        self.assertRegex(corps_de("photo_masque"), r"IF\s+hors1\s+THEN\s+RAISE\s+EXCEPTION")        # la fonction appelante lève, comme MasquageInstable
        corps = corps_de("photo_masque")
        self.assertRegex(corps, r"IF\s+iter\s*>=\s*limite_b\s+THEN\s+RAISE\s+EXCEPTION")
        self.assertRegex(corps, r"IF\s+passe_s\s*>=\s*limite_s\s+THEN\s+RAISE\s+EXCEPTION")
        self.assertRegex(corps, r"IF\s+vide1\s+THEN\s+RAISE\s+EXCEPTION")                   # la lecture « m libre » vide : erreur

    def test_ordre_des_termes_du_produit_et_des_relations_sql_comme_python(self):
        """Termes dans l'ordre des clés des deux côtés : P4 liste les cellules d'équipe (coefficient -1) puis celle du produit (+1), rangées par la première
        ligne d'équipe ; P1 met le tout d'abord quand il vient avant la partie ; P3 et « D >= f » listent leurs termes par clé croissante."""
        corps = corps_de("photo_masque")
        p4 = corps[corps.index("FOR t_i IN 1..n LOOP"):corps.index("r_deb := ARRAY[]")]
        self.assertLess(p4.index("tc := tc || (-1)::smallint;"), p4.index("tc := tc || 1::smallint;"))        # l'équipe avant le produit
        p1 = corps[corps.index("IF paire_de[c] > c"):corps.index("IF ver[i] IS NULL AND var_d[i] > 0")]
        self.assertRegex(p1, r"paire_de\[q\]\s*=\s*c")
        # D >= f vient avant D + m = somme des trouvés (même premier terme D : le coefficient -1 précède +1, comme le tri de Python)
        d_f = "tv := tv || var_d[i] || var_ix[(j - 1) * 9 + 1];"
        self.assertIn(d_f, corps)
        self.assertLess(corps.index(d_f), corps.index("tv := tv || var_d[i] || var_m[i] || var_u[i];"))      # M1 (a) : D + m = trouvés + U
        self.assertIn("tc := tc || (-1)::smallint || 1::smallint;", corps)

    def test_terme_latent_lecture_par_ligne_et_exemption_a_un_terme_comme_python(self):
        """M1 (a), M2 (a) et écart 3 de M5 (a) de la fiche R-20261104-6, côté SQL comme côté Python."""
        corps = corps_de("photo_masque")
        self.assertRegex(corps, r"var_u\[i\]\s*:=\s*nv;\s*v_row\[nv\]\s*:=\s*i;\s*v_col\[nv\]\s*:=\s*12")      # U : borne basse 0, hi0 NULL (sans borne haute)
        self.assertRegex(corps, r"tc\s*:=\s*tc\s*\|\|\s*1::smallint\s*\|\|\s*1::smallint\s*\|\|\s*\(-1\)::smallint;")      # D + m - U - somme des trouvés
        self.assertRegex(corps, r"lo2\[var_m\[i\]\]\s*:=\s*0;\s*hi2\[var_m\[i\]\]\s*:=\s*0;")                  # une lecture par ligne
        # M7 (a) : par ligne, trois lectures (m = 0, U = 0, U = 0 et m = 0) écartées quand la borne basse du pari n'est plus 0, comme Python
        self.assertRegex(corps, r"lo2\[var_u\[i\]\]\s*:=\s*0;\s*hi2\[var_u\[i\]\]\s*:=\s*0;")
        self.assertRegex(corps, r"FOR\s+lect\s+IN\s+1\.\.3\s+LOOP")
        self.assertRegex(corps, r"lect\s*=\s*3\s+AND\s+lo1\[var_m\[i\]\]\s*=\s*0\s+AND\s+lo1\[var_u\[i\]\]\s*=\s*0")
        self.assertRegex(corps, r"lect\s*=\s*2\s+AND\s+lo1\[var_u\[i\]\]\s*=\s*0")
        self.assertIn("pin_zero[v] := true;", corps)

    def test_exces_controle_dans_la_lecture_u_nul_de_sa_ligne_sans_relaxation_de_structure(self):
        """M10 (a) de la revue finale du 2026-11-04 (R-20261104-13), côté SQL comme côté Python : m_r fixé sous T dans la lecture « U = 0 » de sa ligne
        (lecture 2) est épinglé, sauf pour une ligne à un seul terme retenu (seule exemption) ; plus de relaxation de structure."""
        corps = corps_de("photo_masque")
        self.assertRegex(corps, r"IF\s+lect\s*=\s*2\s+AND\s+hi3\[var_m\[i\]\]\s+IS\s+NOT\s+NULL\s+AND\s+lo3\[var_m\[i\]\]\s*=\s*hi3\[var_m\[i\]\]"
                                r"\s+AND\s+lo3\[var_m\[i\]\]\s*<\s*t\s+AND\s+nb_termes\[i\]\s*<>\s*1\s+THEN\s+pin_exces\[var_m\[i\]\]\s*:=\s*true")
        self.assertRegex(corps, r"IF\s+pin_exces\[v\]\s+THEN\s+epingle\s*:=\s*v")
        self.assertNotRegex(corps, r"(?i)structurel|hi4|lo4|vide4")
        self.assertNotRegex(corps, r"hi1\[v\]\s+IS\s+NOT\s+NULL\s+AND\s+lo1\[v\]\s*=\s*hi1\[v\]\s+AND\s+lo1\[v\]\s*<\s*t")      # le contrôle mort de « m libre »
        self.assertIn("Replaces: nothing in D15", texte())
        source = (RACINE / "tools" / "flow_views.py").read_text(encoding="utf-8")
        self.assertNotIn("structurel", source)
        self.assertIn("Replaces: nothing in D15", source)

    def test_l_ordre_des_cles_est_celui_de_python(self):
        """Le tri des lignes de la vue : rang (équipes 0, produit 1), semaine, équipe en ordre d'octets, version (la ligne sans version d'abord)."""
        c = code()
        self.assertRegex(c, r'(?is)ORDER\s+BY\s+u\.rang_t,\s*u\.week_start,\s*u\.team\s+COLLATE\s+"C",\s*u\.vno\s+NULLS\s+FIRST')
        self.assertEqual(fv.PRODUIT, "(produit)")
        self.assertRegex(code(), r"prod\s+constant\s+text\s*:=\s*'\(produit\)'")

    def test_les_paires_sont_celles_de_python(self):
        """paire_de : colonne -> colonne du tout, dans l'ordre de COMPTES_PHOTO (1 à 9) ; 0 : aucune."""
        trouve = re.search(r"paire_de\s+integer\[\]\s*:=\s*ARRAY\[([^\]]*)\]", code())
        self.assertIsNotNone(trouve)
        sql = [int(x) for x in trouve.group(1).split(",")]
        attendu = [0 if col not in fv.PAIRES_PHOTO else fv.COMPTES_PHOTO.index(fv.PAIRES_PHOTO[col]) + 1 for col in fv.COMPTES_PHOTO]
        self.assertEqual(sql, attendu)


class Marqueur(unittest.TestCase):
    def test_le_marqueur_vaut_deux_pour_le_role_d_import_seulement(self):
        c = code()
        self.assertRegex(c, r"(?is)CREATE\s+OR\s+REPLACE\s+FUNCTION\s+flow\.masking_version\(\)\s+RETURNS\s+integer\s+LANGUAGE\s+sql\s+IMMUTABLE\s+PARALLEL\s+SAFE\s+AS\s+\$\$\s*SELECT\s+2\s*\$\$;")
        revoke = re.search(r"(?is)REVOKE\s+ALL\s+ON\s+FUNCTION\s+flow\.masking_version\(\)\s+FROM\s+([^;]*);", c)
        self.assertIsNotNone(revoke)
        for role in ("PUBLIC", "pmzilla_flow_views", "pmzilla_flow_ro", "pmzilla_quality_views"):
            self.assertRegex(revoke.group(1), rf"\b{role}\b")
        accords = re.findall(r"(?is)GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+flow\.masking_version\(\)\s+TO\s+([^;]*);", c)
        self.assertEqual([a.strip() for a in accords], ["pmzilla_flow"])

    def test_la_version_attendue_par_adopt_n_est_celle_du_marqueur(self):
        source = (RACINE / "tools" / "version_photo.py").read_text(encoding="utf-8")          # lu comme texte : sans les dépendances de l'outil
        attendue = int(re.search(r"(?m)^VERSION_MASQUAGE_ATTENDUE\s*=\s*(\d+)", source).group(1))
        valeur = int(re.search(r"(?is)CREATE\s+OR\s+REPLACE\s+FUNCTION\s+flow\.masking_version\(\).*?SELECT\s+(\d+)", code()).group(1))
        # Replaces: attendue == valeur, during group 6 only (R-20261104-45 (1), adopt-n expects 3, the migration of group 6 returns 2).
        # Removal: falls with 7.0b, back to the equality. Decision R-20261104-49, answer Q3 (a).
        self.assertEqual(attendue, valeur + 1)
        self.assertEqual(valeur, 2)

    def test_la_migration_des_sommes_garde_la_version_un(self):
        anciens = re.sub(r"--[^\n]*", "", fichier(SUFFIXE_SOMMES).read_text(encoding="utf-8"))
        self.assertRegex(anciens, r"(?is)CREATE\s+FUNCTION\s+flow\.masking_version\(\)\s+RETURNS\s+integer.*?SELECT\s+1\s*\$\$")


class Vue(unittest.TestCase):
    @staticmethod
    def alias_premiere_branche(sql):
        premiere = re.search(r"(?is)--\s*1\.\s*lignes de couverture\s*(SELECT.*?)FROM\s+couverture\s+x\s+CROSS\s+JOIN\s+etat_n\s+n", sql).group(1)
        return re.findall(r"(?i)\bAS\s+(\w+)", re.sub(r"--[^\n]*", "", premiere))

    def test_les_colonnes_de_la_vue_sont_celles_de_la_migration_des_sommes(self):
        nouvelles = self.alias_premiere_branche(texte() + "\nRESET ROLE;")
        anciennes = self.alias_premiere_branche(fichier(SUFFIXE_SOMMES).read_text(encoding="utf-8"))
        self.assertTrue(nouvelles)
        self.assertEqual(nouvelles, anciennes)

    def test_la_vue_appelle_la_fonction_et_plus_la_serie_de_0022(self):
        c = code()
        vue = c[c.index("CREATE OR REPLACE VIEW flow.v_version_quality_photo"):]
        self.assertRegex(vue, r"(?is)CROSS\s+JOIN\s+LATERAL\s+flow\.photo_masque\(a\.sem,\s*a\.eq,\s*a\.ver,\s*a\.val,\s*a\.extra\)")
        self.assertNotIn("photo_serie", vue)
        for ancienne in ("libre_serie", "produit_serie", "produit_libre ", "equipe_version_vis"):
            self.assertNotIn(ancienne, vue)

    def test_les_droits_de_la_vue_sont_redonnes(self):
        c = code()
        self.assertRegex(c, r"(?is)REVOKE\s+ALL\s+ON\s+flow\.v_version_quality_photo\s+FROM\s+PUBLIC,\s*pmzilla_flow,\s*pmzilla_flow_ro,\s*pmzilla_quality_views\s*;")
        self.assertRegex(c, r"(?is)GRANT\s+SELECT\s+ON\s+flow\.v_version_quality_photo\s+TO\s+pmzilla_flow_views\s*;")


if __name__ == "__main__":
    unittest.main()
