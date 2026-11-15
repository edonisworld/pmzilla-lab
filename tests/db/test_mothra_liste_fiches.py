"""
Test de la requête SQL de la liste des fiches de Mothra (audit #629, A-04 ; question 8 du lot 5, R-20261108-01) : la requête de
`lister` du stockage du serveur (mothra/server/src/db/stockage.ts) est lue dans ce fichier et exécutée telle quelle, sous le rôle du
stockage, sur la base jetable migrée. Elle donne les fiches d'un seul état, les plus récentes d'abord (ordre numérique de
l'identifiant), bornées à 100, avec leur identifiant, leur genre, leur portée, leur date de données et leur état, et rien d'autre.

    bash tools/dbtest.sh db        (passe de l'auteur : les modules de tests/db ne sont pas lancés par une session)

Les tests sans base (classe SansBase) lisent le fichier du serveur. Les autres utilisent une base jetable migrée (même mécanisme que
test_mothra_schema.py) et sont sautés sans base disponible (DBTEST_PORT). Données inventées : identifiant pseudonyme u1.
Remplace : rien (la requête n'était exercée que par un dépôt en mémoire). Retrait : tombe avec la requête de `lister`, ou avec R-20261108-01
si la liste des fiches change de forme.
"""
import re
import unittest
from pathlib import Path

from test_mothra_schema import BaseJetable, ROLE   # noqa: E402

STOCKAGE = Path(__file__).resolve().parents[2] / "mothra" / "server" / "src" / "db" / "stockage.ts"
LIMITE = 100


def requete_lister():
    """La requête de `lister` du serveur, avec les paramètres numérotés ($1, $2) du pilote pg écrits à la manière de psycopg (%s)."""
    texte = STOCKAGE.read_text(encoding="utf-8")
    corps = re.search(r"async lister\(.*?\{(.*?)\n    \},", texte, re.S)
    assert corps is not None, "méthode lister introuvable dans le stockage du serveur"
    trouvees = re.findall(r'"(SELECT [^"]*FROM sheets[^"]*)"', corps.group(1))
    assert len(trouvees) == 1, "une seule requête SELECT attendue dans lister"
    return re.sub(r"\$\d", "%s", trouvees[0])


class SansBase(unittest.TestCase):
    def test_la_requete_est_lue_dans_le_serveur_avec_deux_parametres(self):
        sql = requete_lister()
        self.assertEqual(sql.count("%s"), 2)
        self.assertRegex(sql, r"WHERE state = %s")
        self.assertRegex(sql, r"LIMIT %s$")

    def test_l_ordre_vise_la_colonne_et_non_l_alias_texte(self):
        # `id::text AS id` : un `ORDER BY id` seul trierait sur l'alias texte ("9" après "10"), pas sur le nombre.
        self.assertRegex(requete_lister(), r"ORDER BY sheets\.id DESC")


class AvecBase(BaseJetable):
    def poser(self, c, nombre, etat="draft"):
        for rang in range(nombre):
            self.execute(c, ROLE, "INSERT INTO mothra.sheets (kind, created_by, scope, data_date, management_question) "
                                  "VALUES ('lead_cycle_h1', 'u1', 'team.t0001', '2026-10-05', 'predictability')")
        if etat != "draft":
            self.execute(c, ROLE, "UPDATE mothra.sheets SET state = %s, reviewed_by = 'u1'", (etat,))

    def lister(self, c, etat, limite=LIMITE):
        # Le serveur pose le schéma mothra dans le chemin de recherche de sa session (noms de table non qualifiés).
        with c.transaction():
            c.execute(f"SET LOCAL ROLE {ROLE}")
            c.execute("SET LOCAL search_path TO mothra")
            return c.execute(requete_lister(), (etat, limite)).fetchall()

    def test_une_ligne_a_cinq_colonnes_et_aucun_texte_ecrit(self):
        c = self.conn()
        self.poser(c, 1)
        lignes = self.lister(c, "draft")
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0], ("1", "lead_cycle_h1", "team.t0001", "2026-10-05", "draft"))

    def test_le_plus_recent_d_abord_dans_l_ordre_numerique_de_l_identifiant(self):
        c = self.conn()
        self.poser(c, 12)
        identifiants = [ligne[0] for ligne in self.lister(c, "draft")]
        self.assertEqual(identifiants, [str(n) for n in range(12, 0, -1)])    # "10", "11", "12" avant "9" si le tri portait sur le texte

    def test_un_seul_etat_a_la_fois(self):
        c = self.conn()
        self.poser(c, 3)
        self.execute(c, ROLE, "UPDATE mothra.sheets SET state = 'reviewed', reviewed_by = 'u1' WHERE id = 2")
        self.assertEqual([ligne[0] for ligne in self.lister(c, "draft")], ["3", "1"])
        self.assertEqual([ligne[0] for ligne in self.lister(c, "reviewed")], ["2"])
        self.assertEqual(self.lister(c, "published"), [])

    def test_la_liste_est_bornee_a_cent_fiches(self):
        c = self.conn()
        self.poser(c, LIMITE + 5)
        identifiants = [ligne[0] for ligne in self.lister(c, "draft")]
        self.assertEqual(len(identifiants), LIMITE)
        self.assertEqual(identifiants[0], str(LIMITE + 5))
        self.assertEqual(identifiants[-1], "6")


if __name__ == "__main__":
    unittest.main()
