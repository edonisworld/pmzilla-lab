"""
L'écart D4 (d) rétabli, côté Python et lecture statique du SQL (R-20261106-22, qui remplace R-20261105-6 Q4 (a) ; revue des chemins de démasquage de 0035).

    bash tests/run_all.sh flow_views

N'importe aucun module de base. Règle : une ligne d'équipe, ou du produit, sans ligne de version retenue cette semaine-là fait masquer ses défauts créés et
sans affects (D2, D5-e), comme le faisait flow.photo_serie de 0022 (l. 192-196 : m = 0, l'excès étant sous 5). Elle vaut dans le lecteur Python
(`masquer_vue`) et dans une migration après 0035, qui remplace flow.photo_masque sans toucher 0035 (appliquée sur la vraie base). Les parités avec la
base (la fonction et la vue contre `masquer_vue`) sont dans tests/db/test_masquage_ecart_d4d_vues.py, lancé par le dbtest de l'auteur ; les
cas d'oracle (une semaine, plusieurs semaines, balayage 0 <= w <= c <= 30) sont dans tests/oracle_masquage/test_oracle_ecart_d4d.py.
Données inventées (équipe A, semaines de mars 2026).
"""
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

DOSSIER = RACINE / "db" / "migrations"
SUFFIXE = "_flow_masquage_ecart_d4d.sql"
SUFFIXE_PROPAGATION = "_flow_masquage_propagation.sql"
NOMS = ["week_start", "n_adopted", "team", "version_no", "found", "defects_created", "defects_without_affects", "resolved_week",
        "resolved_week_defects"]
SIGNATURE = r"flow\.photo_masque\(sem date\[\], eq text\[\], ver integer\[\], val bigint\[\], extra bigint\[\],\s*lim_boucle integer DEFAULT NULL, lim_balayages bigint DEFAULT NULL\)"


def fichier(suffixe):
    candidats = [m for m in sorted(DOSSIER.glob("*.sql")) if m.name.endswith(suffixe)]
    return candidats[0] if len(candidats) == 1 else None


def code(chemin):
    return re.sub(r"--[^\n]*", "", chemin.read_text(encoding="utf-8"))


def corps_photo_masque(chemin, remplace):
    motif = r"(?is)CREATE\s+" + (r"OR\s+REPLACE\s+" if remplace else "") + r"FUNCTION\s+" + SIGNATURE + r".*?AS\s+\$\$(.*?)\$\$;"
    trouve = re.search(motif, code(chemin))
    assert trouve, chemin.name
    return trouve.group(1)


def normalise(texte):
    return re.sub(r"\s+", " ", texte).strip()


def lignes(*cellules):
    """Une semaine d'une équipe A sans ligne de version et celle du produit qui la reprend : [(créés, sans affects)] par semaine."""
    sortie = []
    for k, (crees, sans) in enumerate(cellules):
        semaine = f"2026-03-{2 + 7 * k:02d}"
        sortie.append((semaine, True, "A", None, None, crees, sans, 20, 10))
        sortie.append((semaine, True, fv.PRODUIT, None, None, crees, sans, 20, 10))
    return sortie


def libres(cellules):
    return [{k: (c[k].get("value") if "masked" not in c[k] else None) for k in ("defects_created", "defects_without_affects")} for c in cellules]


class MigrationApresLaPropagation(unittest.TestCase):
    def test_la_migration_existe_apres_la_propagation_et_ne_la_modifie_pas(self):
        nouvelle, propagation = fichier(SUFFIXE), fichier(SUFFIXE_PROPAGATION)
        self.assertIsNotNone(nouvelle, f"une migration *{SUFFIXE} est attendue")
        self.assertIsNotNone(propagation)
        self.assertGreater(int(nouvelle.name[:4]), int(propagation.name[:4]))
        numeros = sorted(int(m.name[:4]) for m in DOSSIER.glob("*.sql"))
        self.assertEqual(numeros, list(range(1, len(numeros) + 1)))          # sans trou
        brut = nouvelle.read_text(encoding="utf-8")
        self.assertRegex(brut.splitlines()[0], r"^-- Schéma touché : flow")
        self.assertRegex(brut, r"(?m)^-- Remplace : ")
        self.assertRegex(brut, r"Retrait\s*:")
        self.assertIn("R-20261106-22", brut)

    def test_elle_remplace_la_fonction_sans_rien_changer_d_autre(self):
        """CREATE OR REPLACE de la seule fonction, même signature ; ni vue, ni marqueur, ni donnée, ni rôle, ni table."""
        c = code(fichier(SUFFIXE))
        self.assertRegex(c, r"(?is)SET\s+LOCAL\s+ROLE\s+pmzilla_owner\s*;.*CREATE\s+OR\s+REPLACE\s+FUNCTION\s+" + SIGNATURE)
        self.assertRegex(c, r"(?i)\bRESET\s+ROLE\s*;")
        self.assertEqual(len(re.findall(r"(?i)\bCREATE\b", c)), 1)
        self.assertNotRegex(c, r"(?i)\bmasking_version\b|\bVIEW\b|\bFUNCTION\s+flow\.propager_bornes\b")
        self.assertNotRegex(c, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s|COPY\s)")
        self.assertNotRegex(c, r"(?i)\bPASSWORD\b|\b(CREATE|ALTER|DROP)\s+(ROLE|TABLE)\b|\bLOGIN\b")
        self.assertNotRegex(fichier(SUFFIXE).read_text(encoding="utf-8"), r"(?i)\bjira\b")

    def test_execute_au_seul_role_des_vues_comme_en_0035(self):
        c = code(fichier(SUFFIXE))
        revoke = re.search(r"(?is)REVOKE\s+ALL\s+ON\s+FUNCTION\s+flow\.photo_masque\(([^)]*)\)\s+FROM\s+([^;]*);", c)
        self.assertIsNotNone(revoke)
        for role in ("PUBLIC", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_quality_views"):
            self.assertRegex(revoke.group(2), rf"\b{role}\b", role)
        accords = re.findall(r"(?is)GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+flow\.photo_masque\(([^)]*)\)\s+TO\s+([^;]*);", c)
        self.assertEqual([a[1].strip() for a in accords], ["pmzilla_flow_views"])
        self.assertEqual(accords[0][0], revoke.group(1))

    def test_le_corps_est_celui_de_0035_sans_le_garde_fou_nterms(self):
        """Une seule différence avec 0035 : le garde-fou `IF nterms > 0 THEN ... END IF;` autour de la lecture de m disparaît. Toute autre dérive du corps
        (ce test les voit) est un changement de règle qui demande sa propre décision."""
        avant = corps_photo_masque(fichier(SUFFIXE_PROPAGATION), remplace=False)
        garde = re.search(r"(?is)IF\s+nterms\s*>\s*0\s+THEN\s+(FOREACH\s+m\s+IN\s+ARRAY.*?END\s+LOOP;)\s+END\s+IF;", avant)
        self.assertIsNotNone(garde, "0035 doit porter le garde-fou avec la boucle FOREACH à l'intérieur")
        attendu = normalise(avant.replace(garde.group(0), garde.group(1)))
        self.assertEqual(normalise(corps_photo_masque(fichier(SUFFIXE), remplace=True)), attendu)

    def test_plus_aucune_condition_sur_le_nombre_de_termes(self):
        corps = corps_photo_masque(fichier(SUFFIXE), remplace=True)
        self.assertNotRegex(corps, r"(?i)IF\s+nterms\s*>\s*0")
        self.assertRegex(corps, r"FOREACH\s+m\s+IN\s+ARRAY\s+ARRAY\[np,\s*np\s*\+\s*coalesce\(extra\[j\],\s*0\)\]")


class LecteurPython(unittest.TestCase):
    def test_completer_ne_sort_plus_sans_terme(self):
        """Le lecteur Python : plus de sortie anticipée quand la ligne n'a aucun terme (la règle de 0022 : k = 0, somme des visibles 0)."""
        source = (RACINE / "tools" / "flow_views.py").read_text(encoding="utf-8")
        completer = source[source.index("    def completer(i: int)"):source.index("    def boucle(lignes: list)")]
        self.assertNotRegex(completer, r"not\s+termes")

    def test_une_semaine_sans_ligne_de_version_equipe_et_produit_masques(self):
        for crees, sans in ((40, 10), (30, 0), (12, 12), (5, 5), (30, 25)):
            with self.subTest(creees=crees, sans_affects=sans):
                sortie = libres(fv.masquer_vue(fv.VUE_PHOTO, NOMS, lignes((crees, sans)), fv.PLANCHER))
                self.assertEqual(sortie, [{"defects_created": None, "defects_without_affects": None}] * 2)

    def test_plusieurs_semaines_sans_ligne_de_version_comme_la_serie_de_0022(self):
        """Trois semaines sans ligne de version, créés 28, 30, 33 et sans affects 10, 15, 20, tous publiés au départ. Comme flow.photo_serie de 0022 : la
        chaîne D5-d masque les créés de la semaine 2 (écart 2 avec la semaine 1) avant que D2 masque la semaine 1 ; D2 ne lit pas une semaine dont les créés sont
        déjà masqués, donc les sans affects de la semaine 2 (15) restent publiés ; tout le reste est masqué. Équipe A, puis produit, semaine par semaine."""
        sortie = libres(fv.masquer_vue(fv.VUE_PHOTO, NOMS, lignes((28, 10), (30, 15), (33, 20)), fv.PLANCHER))
        masquee = {"defects_created": None, "defects_without_affects": None}
        semaine_deux = {"defects_created": None, "defects_without_affects": 15}
        self.assertEqual(sortie, [masquee, masquee, semaine_deux, semaine_deux, masquee, masquee])


if __name__ == "__main__":
    unittest.main()
