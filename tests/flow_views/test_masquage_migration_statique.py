"""Lecture statique de la migration du masquage des sommes (change masking-sums, R-144 ; tâche 2.1 ; conception D2 à D5, D12 ; revue B1, M2, M3, m1).

    bash tests/run_all.sh flow_views

N'importe aucun module de base : lit seulement le texte de db/migrations/*_flow_masquage_somme.sql et tools/flow_views.py. Les tests avec base
(contre-exemples contre les vues, parité) restent dans tests/db/test_masquage_somme_vues.py, lancé par le dbtest de l'auteur.
"""
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

SUFFIXE = "_flow_masquage_somme.sql"
VUES_RECREEES = ("v_team_fix_version_share", "v_version_quality_photo", "v_teams", "v_team_jira_ids", "v_team_fix_version_lag")
DOSSIER = RACINE / "db" / "migrations"
FIN_VUE = r".*?;\s*(?=CREATE\s+(?:OR\s+REPLACE\s+VIEW|FUNCTION)|RESET\s+ROLE)"


def migrations():
    return sorted(DOSSIER.glob("*.sql"))


def fichier_migration():
    candidats = [m for m in migrations() if m.name.endswith(SUFFIXE)]
    return candidats[0] if len(candidats) == 1 else None


def sans_commentaires(texte):
    return re.sub(r"--[^\n]*", "", texte)


def corps_vue(code, vue):
    trouve = re.search(rf"(?is)CREATE\s+OR\s+REPLACE\s+VIEW\s+flow\.{vue}\b{FIN_VUE}", code)
    return trouve.group(0) if trouve else None


def lectures_de_table(corps):
    """Vraies lectures de table d'un corps de fonction (décision du 2026-10-28) : `FROM` ou `JOIN` suivi d'un nom de table (identifiant, éventuellement
    qualifié par un schéma). `IS NOT DISTINCT FROM` est exclu, et le `FROM` d'un `FOREACH … IN ARRAY` toujours toléré."""
    texte = re.sub(r"(?is)\bFOREACH\b.*?\bIN\s+ARRAY\b", "", corps)
    texte = re.sub(r"(?i)\bIS\s+(?:NOT\s+)?DISTINCT\s+FROM\b", "", texte)
    identifiant = r'(?:"[^"]+"|[A-Za-z_][\w$]*)'                       # nu ou entre guillemets
    return re.findall(rf"(?i)\b(?:FROM|JOIN)\s+({identifiant}(?:\.{identifiant})?)", texte)


class LectureDeTable(unittest.TestCase):
    """Le contrôle « aucune lecture de table » se teste lui-même."""

    def test_is_not_distinct_from_n_est_pas_une_lecture(self):
        self.assertEqual(lectures_de_table("IF dc IS NOT DISTINCT FROM avant_dc AND dwa IS DISTINCT FROM avant_dwa THEN EXIT; END IF;"), [])

    def test_le_from_d_un_foreach_est_tolere(self):
        self.assertEqual(lectures_de_table("FOREACH m IN ARRAY ARRAY[np[i], nc[i]] LOOP besoin := true; END LOOP;"), [])

    def test_from_d_une_table_qualifiee_est_refuse(self):
        self.assertEqual(lectures_de_table("x := (SELECT count(*) FROM flow.version_photo_rows);"), ["flow.version_photo_rows"])
        self.assertEqual(lectures_de_table("SELECT 1 FROM un_nom"), ["un_nom"])

    def test_nom_de_table_entre_guillemets_est_refuse(self):
        self.assertEqual(lectures_de_table('SELECT 1 FROM "flow".x'), ['"flow".x'])
        self.assertEqual(lectures_de_table('SELECT 1 FROM a JOIN "x" ON true'), ["a", '"x"'])
        self.assertEqual(lectures_de_table('SELECT 1 FROM flow."Une Table"'), ['flow."Une Table"'])

    def test_join_d_une_table_qualifiee_est_refuse(self):
        self.assertEqual(lectures_de_table("SELECT 1 FROM flow.a JOIN flow.b ON true"), ["flow.a", "flow.b"])
        self.assertEqual(lectures_de_table("x JOIN flow.teams t ON t.id = 1"), ["flow.teams"])


class MigrationStatique(unittest.TestCase):
    def texte(self):
        migration = fichier_migration()
        self.assertIsNotNone(migration, f"une migration *{SUFFIXE} est attendue")
        return migration.read_text(encoding="utf-8")

    def code(self):
        return sans_commentaires(self.texte())

    def test_premiere_ligne_et_role_proprietaire_avant_la_premiere_vue(self):
        texte = self.texte()
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        code = self.code()
        self.assertRegex(code, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;.*?CREATE\s+(?:OR\s+REPLACE\s+)?VIEW")
        self.assertLess(re.search(r"(?i)SET\s+LOCAL\s+ROLE\s+pmzilla_owner", code).start(), re.search(r"(?i)CREATE\s+(OR\s+REPLACE\s+)?VIEW", code).start())
        self.assertRegex(code, r"(?is)RESET\s+ROLE\s*;")

    def test_aucune_donnee_aucun_mot_de_passe_aucun_role(self):
        code = self.code()
        self.assertNotRegex(code, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(code, r"(?i)\bPASSWORD\b|\bLOGIN\b")
        self.assertNotRegex(code, r"(?i)\b(CREATE|ALTER|DROP)\s+ROLE\b")
        self.assertNotRegex(code, r"(?i)\b(CREATE|ALTER|DROP)\s+TABLE\b")

    def test_les_cinq_vues_sont_recreees_et_les_colonnes_ne_sont_pas_declarees_autrement(self):
        code = self.code()
        vues = re.findall(r"(?i)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+flow\.(\w+)", code)
        self.assertEqual(sorted(vues), sorted(VUES_RECREEES))
        self.assertNotRegex(code, r"(?i)\bDROP\s+VIEW\b")                          # mêmes colonnes : aucune suppression
        for vue in VUES_RECREEES:
            self.assertRegex(code, rf"(?i)CREATE\s+OR\s+REPLACE\s+VIEW\s+flow\.{vue}\b")

    def test_la_vue_du_retard_lit_la_nouvelle_part_et_applique_la_regle_de_complement_d2(self):
        code = self.code()
        corps = corps_vue(code, "v_team_fix_version_lag")
        self.assertIsNotNone(corps)
        part = re.search(r"(?i)CREATE\s+OR\s+REPLACE\s+VIEW\s+flow\.v_team_fix_version_share\b", code)
        self.assertLess(part.start(), code.index(corps), "la part est recréée avant le retard qui la lit")
        self.assertIn("flow.v_team_fix_version_share", corps)
        self.assertRegex(self.fonction("retard_d2"), r"(?i)k\s*>=\s*2\s+AND\s+somme\s*>=\s*5\s+AND\s+somme\s*<>\s*k\s*\*\s*haut")      # D2 : deux, 5, bornes hautes
        self.assertNotRegex(corps, r"nb = 1 OR")                                    # l'ancienne règle « exactement une ou somme sous 5 » n'y est plus

    def test_bornes_de_flow_views_egales_a_celles_que_la_migration_declare(self):
        """Revue R-144, M3 : la table BORNES de tools/flow_views.py et les constantes de la migration (lignes « -- BORNES vue.colonne lo=N
        complement=oui|non » de son en-tête) sont confrontées ; une borne changée d'un côté seulement fait échouer ce test."""
        declarees = {}
        for vue, colonne, lo, complement in re.findall(r"(?m)^-- BORNES (\w+)\.(\w+) lo=(\d+) complement=(oui|non)\s*$", self.texte()):
            declarees.setdefault(vue, {})[colonne] = (int(lo), complement == "oui")
        self.assertEqual(declarees, {vue: fv.BORNES[vue] for vue in VUES_RECREEES})

    def test_bornes_de_flow_views_egales_aux_constantes_du_code_sql(self):
        """Revue 2, m1 : BORNES est aussi confrontée aux constantes du code (pas seulement aux commentaires) : la borne haute 4 (seuil - 1) et la
        borne basse lo = 1 d'une famille de GROUP BY (`s >= k`), lo = 0 ailleurs (aucune borne basse non nulle sur les termes de la photo)."""
        code = self.code()
        self.assertEqual(fv.PLANCHER - 1, 4)
        for vue in ("v_teams", "v_team_jira_ids"):
            lo = fv.BORNES[vue]["tickets"][0]
            corps = corps_vue(code, vue)
            self.assertIsNotNone(corps, vue)
            self.assertRegex(corps, r"(?i)\bt\.s\s*>=\s*t\.k\b" if lo == 1 else r"(?i)\bt\.s\s*>=\s*0\b", f"{vue} : borne basse")
            self.assertRegex(corps, r"(?i)greatest\(\s*4\b", f"{vue} : borne haute")
        photo = corps_vue(code, "v_version_quality_photo")
        self.assertIsNotNone(photo)
        self.assertEqual({lo for lo, _ in fv.BORNES["v_version_quality_photo"].values()}, {0})
        d2 = self.fonction("photo_serie")
        self.assertRegex(d2, r"=\s*4\s*\*\s*m\b")                                        # borne haute 4 par terme caché
        self.assertRegex(d2, r"=\s*4\s*\*\s*\(1\s*\+\s*m\)")                             # sans affects masqué : 4 de plus
        retard = corps_vue(code, "v_team_fix_version_lag")
        self.assertEqual({lo for col, (lo, _) in fv.BORNES["v_team_fix_version_lag"].items() if col != "items"}, {0})
        self.assertRegex(self.fonction("retard_d2"), r"(?i)somme\s*>=\s*5\s+AND\s+somme\s*<>\s*k\s*\*\s*haut")
        self.assertRegex(self.fonction("retard_d2"), r"(?i)haut\s*:=\s*greatest\(\s*4\b")
        self.assertIn("flow.retard_d2(", retard)

    def test_la_ligne_a_completer_est_decidee_avec_les_termes_publies_et_tous_les_termes_caches_b1_revue_2(self):
        photo = corps_vue(self.code(), "v_version_quality_photo")
        self.assertIsNotNone(photo)
        self.assertRegex(photo, r"(?is)flow\.photo_serie\(\s*g\.crees\s*,\s*g\.sans\s*,\s*g\.ok_dc\s*,\s*g\.ok_dwa\s*,\s*g\.np\s*,\s*g\.nc\s*,\s*g\.sv\s*\)",
                         "libre : la série de l'équipe passe par la fonction, avec n_publies puis n_caches")
        self.assertRegex(photo, r"(?is)flow\.photo_serie\(\s*a\.crees\s*,\s*a\.sans\s*,\s*a\.ok_dc\s*,\s*a\.ok_dwa\s*,\s*a\.np\s*,\s*a\.nc\s*,\s*a\.sv\s*\)",
                         "produit_libre : même fonction, après D3")
        self.assertRegex(self.fonction("photo_serie"), r"(?is)ARRAY\s*\[\s*np\s*\[\s*i\s*\]\s*,\s*nc\s*\[\s*i\s*\]\s*\]", "les deux passes n_publies et n_caches")
        self.assertNotRegex(photo, r"(?i)chaine_equipes|chaine_produit", "D5-d est dans la fonction, repassé avec D2")

    def fonction(self, nom):
        trouve = re.search(rf"(?is)CREATE\s+FUNCTION\s+flow\.{nom}\(.*?\$\$;", self.code())
        self.assertIsNotNone(trouve, f"la fonction flow.{nom} est attendue")
        return trouve.group(0)

    def test_point_fixe_de_la_regle_complementaire_limite_declaree_et_controle(self):
        """Décision du 2026-10-27 : la limite de passes est 2 x W + 1 (W : nombre de semaines de la série), déclarée par la ligne `-- PASSES-MAX 2 x W + 1`
        de l'en-tête, calculée par le code SQL (`limite := 2 * n + 1`, n : longueur des tableaux) et par fv.passes_max ; limite atteinte, la fonction
        lève une erreur ; la fonction ne lit aucune table ; EXECUTE est accordé au seul rôle des vues (PostgreSQL vérifie ce droit pour le lecteur de
        la vue, pas pour son propriétaire)."""
        declarees = re.findall(r"(?m)^-- PASSES-MAX (.*?)\s*$", self.texte())
        self.assertEqual(declarees, ["2 x W + 1"])
        self.assertEqual([fv.passes_max(w) for w in (0, 1, 5, 30)], [1, 3, 11, 61])
        d2 = self.fonction("photo_serie")
        self.assertRegex(d2, r"(?i)\bn\s+integer\s*:=\s*coalesce\(\s*array_length\(\s*crees\s*,\s*1\s*\)\s*,\s*0\s*\)")
        self.assertRegex(d2, r"(?i)\blimite\s+integer\s*:=\s*2\s*\*\s*n\s*\+\s*1\b")
        self.assertRegex(d2, r"(?is)IF\s+passe\s*>=\s*limite\s+THEN\s+RAISE\s+EXCEPTION")
        self.assertRegex(d2, r"(?is)\bLOOP\b.*?\bEND\s+LOOP\b")
        self.assertEqual(lectures_de_table(d2), [], "aucune table lue")
        code = self.code()
        photo = re.search(r"(?i)CREATE\s+OR\s+REPLACE\s+VIEW\s+flow\.v_version_quality_photo\b", code)
        retard_vue = re.search(r"(?i)CREATE\s+OR\s+REPLACE\s+VIEW\s+flow\.v_team_fix_version_lag\b", code)
        for nom, signature, avant in (("photo_serie", r"\(\s*bigint\[\]\s*(?:,\s*(?:bigint|boolean)\[\]\s*){6}\)", photo),
                                      ("retard_d2", r"\(\s*(?:bigint\s*,\s*){5}(?:boolean\s*,\s*){5}boolean\s*\)", retard_vue)):
            corps = self.fonction(nom)
            self.assertRegex(corps, r"(?i)SET\s+search_path\s*=\s*pg_catalog\s*,\s*pg_temp", f"{nom} : search_path fixé")
            self.assertRegex(corps, r"(?i)\bIMMUTABLE\b")
            self.assertEqual(lectures_de_table(corps), [], f"{nom} : aucune table lue")
            revoke = re.search(rf"(?is)REVOKE\s+ALL\s+ON\s+FUNCTION\s+flow\.{nom}\([^)]*\)\s+FROM\s+([^;]*);", code)
            self.assertIsNotNone(revoke, nom)
            for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_views", "pmzilla_flow_ro", "pmzilla_quality_views"):
                self.assertRegex(revoke.group(1), rf"\b{role}\b")
            accords = re.findall(rf"(?is)GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+flow\.{nom}{signature}\s+TO\s+([^;]*);", code)
            self.assertEqual([a.strip() for a in accords], ["pmzilla_flow_views"], nom)
            self.assertLess(revoke.start(), re.search(rf"(?is)GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+flow\.{nom}\b", code).start())
            self.assertLess(code.index(corps), avant.start(), f"{nom} est créée avant la vue qui l'appelle")

    def test_les_vues_a_complement_utilisent_la_borne_haute_du_plus_grand_de_4_et_du_plus_petit_visible(self):
        code = self.code()
        for vue in VUES_RECREEES:
            if any(complement for _, complement in fv.BORNES[vue].values()):
                corps = corps_vue(code, vue)
                self.assertIsNotNone(corps, vue)
                if vue == "v_team_fix_version_lag":                   # la règle est dans la fonction que la vue appelle
                    corps = corps + self.fonction("retard_d2")
                self.assertRegex(corps, r"(?i)greatest\(\s*4\b", vue)

    def test_la_ligne_a_completer_de_la_photo_applique_la_somme_des_bornes_hautes_b1(self):
        """Revue R-144, B1 : « créés moins sans affects moins trouvés visibles = 4 fois les termes cachés » dans la ligne des équipes et dans celle
        du produit (la CTE `libre` et `produit_libre`)."""
        d2 = self.fonction("photo_serie")
        self.assertRegex(d2, r"=\s*4\s*\*\s*m\b", "la somme des bornes hautes (4 fois n) manque")
        self.assertRegex(d2, r"=\s*4\s*\*\s*\(1\s*\+\s*m\)", "la somme des bornes hautes (4 fois 1 + n) manque")

    def test_le_corps_de_photo_serie_porte_toutes_les_regles_de_la_ligne_a_completer(self):
        """Chaque règle que le texte de la vue portait, vérifiée sur le CORPS de flow.photo_serie (pas sur son nom) : D5-d sur les cellules publiées
        (écart de 1 à 4, les deux colonnes), D2 avec sans affects publié (au moins deux termes, somme sous 5, 4 fois n), sans affects masqué (1 + n),
        D5-e (aucun terme caché, excès sous 5), borne haute 4 sans complément (BORNES de la photo : complement=non), passes n_publies et n_caches."""
        corps = self.fonction("photo_serie")
        self.assertRegex(corps, r"(?is)abs\(\s*crees\[i\]\s*-\s*dernier_c\s*\)\s+BETWEEN\s+1\s+AND\s+4", "D5-d : créés")
        self.assertRegex(corps, r"(?is)abs\(\s*sans\[i\]\s*-\s*dernier_a\s*\)\s+BETWEEN\s+1\s+AND\s+4", "D5-d : sans affects")
        self.assertRegex(corps, r"(?is)IF\s+dc\[i\]\s+THEN\s+IF\s+dernier_c\s+IS\s+NOT\s+NULL", "D5-d : seules les cellules publiées s'enchaînent")
        self.assertRegex(corps, r"(?is)IF\s+dwa\[i\]\s+THEN\s+IF\s+dernier_a\s+IS\s+NOT\s+NULL", "D5-d : sans affects, seules les cellules publiées s'enchaînent")
        self.assertRegex(corps, r"(?is)IF\s+dc\s+IS\s+NOT\s+DISTINCT\s+FROM\s+avant_dc\s+AND\s+dwa\s+IS\s+NOT\s+DISTINCT\s+FROM\s+avant_dwa",
                         "m5 : la stabilité se lit avec IS NOT DISTINCT FROM (une série vide a des tableaux nuls)")
        self.assertNotRegex(corps, r"(?i)IF\s+dc\s*=\s*avant_dc", "m5 : l'égalité simple resterait nulle pour n = 0")
        self.assertRegex(corps, r"(?i)m\s*>=\s*1\s+AND\s*\(\s*m\s*<\s*2", "D2, sans affects publié : au moins deux termes cachés")
        self.assertRegex(corps, r"(?i)crees\[i\]\s*-\s*sans\[i\]\s*-\s*sv\[i\]\s*<\s*5", "D2, sans affects publié : somme sous le seuil")
        self.assertRegex(corps, r"(?i)1\s*\+\s*m\s*<\s*2", "D2, sans affects masqué : au moins deux termes cachés")
        self.assertRegex(corps, r"(?i)crees\[i\]\s*-\s*sv\[i\]\s*<\s*5", "D2, sans affects masqué : somme sous le seuil")
        self.assertRegex(corps, r"(?i)m\s*=\s*0\s+AND\s+sv\[i\]\s*-\s*\(\s*crees\[i\]\s*-\s*sans\[i\]\s*\)\s*<\s*5", "D5-e : aucun terme caché, excès sous le seuil")
        self.assertRegex(corps, r"(?i)nouveau_dc\s*:=\s*dc\[i\]\s+AND\s+NOT\s*\(\s*besoin\s+AND\s+NOT\s+dwa\[i\]\s*\)", "sans affects masqué : ce sont les créés qui le sont")
        self.assertRegex(corps, r"(?i)nouveau_dwa\s*:=\s*dwa\[i\]\s+AND\s+NOT\s+besoin", "sans affects publié : c'est lui qui est masqué")
        self.assertNotRegex(corps, r"(?i)greatest\(", "BORNES de la photo : aucun complément, la borne haute reste 4")
        self.assertEqual({c for _, c in fv.BORNES["v_version_quality_photo"].values()}, {False})

    def test_le_corps_de_retard_d2_porte_toutes_les_regles_du_complement_du_retard(self):
        """Chaque règle que le texte de la vue du retard portait, vérifiée sur le CORPS de flow.retard_d2 : au moins deux cellules cachées, somme d'au
        moins 5, somme différente de k fois la borne haute, borne haute = plus grand de 4 et de la plus petite cellule visible (complément oui), la
        plus petite visible (à égalité la première) masquée puis la vérification repart, sans cellule visible les items sont masqués, un zéro masqué
        compte, borne basse 0 (aucun terme de borne basse : la somme des bornes basses est nulle)."""
        corps = self.fonction("retard_d2")
        self.assertRegex(corps, r"(?i)EXIT\s+WHEN\s+k\s*>=\s*2\s+AND\s+somme\s*>=\s*5\s+AND\s+somme\s*<>\s*k\s*\*\s*haut")
        self.assertRegex(corps, r"(?i)haut\s*:=\s*greatest\(\s*4\s*,\s*coalesce\(\s*val\[petit\]\s*,\s*4\s*\)\s*\)")
        self.assertRegex(corps, r"(?i)val\[i\]\s*<\s*val\[petit\]", "la plus petite visible, la première à égalité (comparaison stricte)")
        self.assertRegex(corps, r"(?is)IF\s+petit\s+IS\s+NULL\s+THEN\s+vn\s*:=\s*false", "sans cellule visible : les items sont masqués")
        self.assertRegex(corps, r"(?is)vis\[petit\]\s*:=\s*false\s*;\s*END\s+LOOP", "la plus petite visible est masquée puis la vérification repart")
        self.assertRegex(corps, r"(?i)EXIT\s+WHEN\s+k\s*=\s*0", "aucune cellule cachée : rien à compléter")
        self.assertRegex(corps, r"(?i)ELSE\s+k\s*:=\s*k\s*\+\s*1", "chaque cellule non publiée compte, un zéro masqué aussi")
        self.assertEqual({lo for col, (lo, _) in fv.BORNES["v_team_fix_version_lag"].items() if col != "items"}, {0})
        self.assertEqual({c for col, (_, c) in fv.BORNES["v_team_fix_version_lag"].items() if col != "items"}, {True})

    def test_la_famille_des_identifiants_complete_et_reverifie_et_masque_le_plus_petit_identifiant_d_un_nom_masque(self):
        """Revue R-144, M2 (a) et m1 : la borne haute d'un identifiant masqué est le plus grand de 4 et du plus petit visible, la vérification
        repart après chaque complément (paliers), et un nom masqué masque aussi son plus petit identifiant visible."""
        code = self.code()
        for vue in ("v_teams", "v_team_jira_ids"):
            corps = corps_vue(code, vue)
            self.assertIsNotNone(corps, vue)
            self.assertRegex(corps, r"(?i)generate_series\(\s*0\s*,", f"{vue} : les paliers de complément manquent")
            self.assertRegex(corps, r"(?i)row_number\(\)\s+OVER\s*\(\s*PARTITION\s+BY\s+b\.team\s+ORDER\s+BY\s+b\.n\s*,\s*b\.jira_team_id", vue)
        ids = corps_vue(code, "v_team_jira_ids")
        self.assertRegex(ids, r"(?i)masque_avant", "v_team_jira_ids : un nom masqué avant la famille masque ses identifiants visibles")
        # 5.11 : tous les identifiants visibles, pas seulement le plus petit (rang 1)
        self.assertRegex(ids, r"(?is)WHEN\s+x\.masque_avant\s+THEN\s+NULL\b", "la branche masque_avant masque tout identifiant visible")
        self.assertNotRegex(ids, r"(?is)masque_avant\s+THEN\s+CASE", "la branche masque_avant ne garde plus un rang épinglé")

    def test_select_au_seul_role_des_vues_apres_retrait(self):
        code = self.code()
        grants = [g for g in re.findall(r"(?is)\bGRANT\b.*?;", code) if "EXECUTE" not in g.upper()]
        self.assertEqual(len(grants), len(VUES_RECREEES), grants)
        for vue in VUES_RECREEES:
            self.assertTrue([g for g in grants if re.search(rf"(?is)GRANT\s+SELECT\s+ON\s+flow\.{vue}\s+TO\s+pmzilla_flow_views\s*;", g)], vue)
            revoke = re.search(rf"(?is)REVOKE\s+ALL\s+ON\s+flow\.{vue}\s+FROM\s+([^;]*);", code)
            self.assertIsNotNone(revoke, vue)
            for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views"):
                self.assertRegex(revoke.group(1), rf"\b{role}\b")
            self.assertNotRegex(revoke.group(1), r"pmzilla_flow_views")
            self.assertLess(revoke.start(), re.search(rf"(?is)GRANT\s+SELECT\s+ON\s+flow\.{vue}\b", code).start())

    def test_marqueur_immuable_execute_au_seul_role_d_import(self):
        code = self.code()
        self.assertRegex(code, r"(?is)CREATE\s+FUNCTION\s+flow\.masking_version\(\)\s+RETURNS\s+integer\s+LANGUAGE\s+sql\s+IMMUTABLE")
        revoke = re.search(r"(?is)REVOKE\s+ALL\s+ON\s+FUNCTION\s+flow\.masking_version\(\)\s+FROM\s+([^;]*);", code)
        self.assertIsNotNone(revoke)
        for role in ("PUBLIC", "pmzilla_flow_views", "pmzilla_flow_ro", "pmzilla_quality_views"):
            self.assertRegex(revoke.group(1), rf"\b{role}\b")
        accords = re.findall(r"(?is)GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+flow\.masking_version\(\)\s+TO\s+([^;]*);", code)
        self.assertEqual([a.strip() for a in accords], ["pmzilla_flow"])
        self.assertNotRegex(re.search(r"(?is)CREATE\s+FUNCTION\s+flow\.masking_version.*?\$\$;", code).group(0), r"(?i)\bFROM\b")      # aucune table lue

    def test_numerotee_apres_la_derniere_sans_trou_et_nommee_masquage_somme(self):
        migration = fichier_migration()
        self.assertIn("masquage_somme", migration.name)
        numeros = {m.name.split("_", 1)[1]: int(m.name.split("_", 1)[0]) for m in migrations()}
        self.assertGreater(numeros["flow_masquage_somme.sql"], numeros["flow_version_release_date.sql"])
        liste = sorted(numeros.values())
        self.assertEqual(liste, list(range(1, len(liste) + 1)))


if __name__ == "__main__":
    unittest.main()
