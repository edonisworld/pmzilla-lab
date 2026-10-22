"""
Masquage des vues de qualité sans reste (change story-quality-audit, décision de l'auteur du 2026-10-20, R-94 Q1 (a) ; migration
0016_quality_views_masking.sql ; design D15, D18, O13, T7). Une cellule de moins de 5 n'est jamais retrouvable :
  - dans une ligne de quality_by_team ou de quality_by_product, par `audited` moins des comptes visibles ;
  - entre la ligne de quality_by_product et les lignes d'équipe visibles du même genre et du même critère (D18) ;
  - dans une ligne de quality_coverage_by_team, par la différence de deux colonnes visibles.

    uv run --with "psycopg[binary]" python -W ignore -m unittest discover -s tests/db -p "test_quality_masking.py" -q

Deux parties :
  - SansBase (toujours lancée) : une référence en mémoire des trois règles, vérifiée sur toutes les lignes de comptes de 0 à 12 et sur des
    jeux tirés au hasard (graine fixe), par les vérificateurs de fuite qui énumèrent toutes les différences simples entre cellules visibles ;
  - AvecBase (sautée sans base jetable, bash tools/dbtest.sh db) : les trois vues migrées rendent exactement la référence sur des données
    fictives, et les mêmes vérificateurs ne trouvent aucune fuite.
Données inventées : clés ZZM-n, équipes Zzalpha à Zzdelta, critères c1 et c2, aucun texte réel.
"""
from __future__ import annotations

import contextlib
import itertools
import random
import re
import secrets
import unittest
from pathlib import Path

import test_db as base          # noqa: E402
from test_db import db          # noqa: E402

SEUIL = 5
MIGRATION = "0016_quality_views_masking.sql"   # nommée en entier : le sélecteur de suites rattache la migration à tests/db
VERDICTS = ("met", "not_met", "not_applicable", "undetermined")
SANS_EQUIPE = "(sans équipe)"


# --- référence en mémoire (la règle de la migration, écrite une seconde fois pour la vérifier) ------------------------------------------

def masquer_comptes(comptes):
    """Les quatre comptes d'une ligne : sous 5 masqué ; si un compte est sous 5, les plus petits sont masqués tant que leur somme est sous 5."""
    une = any(c < SEUIL for c in comptes)
    resultat, avant = list(comptes), 0
    for i in sorted(range(len(comptes)), key=lambda k: (comptes[k], k)):
        if comptes[i] < SEUIL or (une and avant < SEUIL):
            resultat[i] = None
        avant += comptes[i]
    return resultat


def masquer(n):
    return None if n < SEUIL else n


def masquer_couverture(collectes, audites, vides):
    collectes_masques = collectes >= SEUIL and audites >= SEUIL and collectes - audites < SEUIL
    vides_masques = vides >= SEUIL and ((audites >= SEUIL and abs(audites - vides) < SEUIL)
                                        or (collectes >= SEUIL and not collectes_masques and collectes - vides < SEUIL))
    return (None if collectes_masques else masquer(collectes), masquer(audites), None if vides_masques else masquer(vides))


def ligne_visible(audites, comptes):
    """(audited, met, not_met, not_applicable, undetermined) tels que la vue les rend."""
    return (masquer(audites), *masquer_comptes(comptes))


def secondaire(produit_visible, lignes_equipe_brutes):
    """Vrai si la ligne du produit doit être masquée : une colonne où la cellule du produit est visible a une seule cellule d'équipe
    masquée, ou des cellules masquées de somme sous 5. `lignes_equipe_brutes` : liste de (audited, [quatre comptes])."""
    for colonne in range(5):
        if produit_visible[colonne] is None:
            continue
        masquees = []
        for audites, comptes in lignes_equipe_brutes:
            brut = (audites, *comptes)[colonne]
            if ligne_visible(audites, comptes)[colonne] is None:
                masquees.append(brut)
        if masquees and (len(masquees) == 1 or sum(masquees) < SEUIL):
            return True
    return False


def ligne_produit_visible(audites, comptes, lignes_equipe_brutes):
    visible = ligne_visible(audites, comptes)
    return (None,) * 5 if secondaire(visible, lignes_equipe_brutes) else visible


# --- vérificateurs de fuite : énumèrent toutes les différences simples entre cellules visibles ---------------------------------------

def fuites_ligne(audites, comptes, visibles):
    """Fuites d'une ligne de résultats : `visibles` = (audited, met, not_met, not_applicable, undetermined), None pour masqué.
    Pour toute partie des comptes visibles, `audited` moins leur somme vaut la somme des autres cellules : si ces autres cellules sont
    toutes masquées et qu'il n'y en a qu'une, ou que leur somme est sous 5, une cellule masquée se retrouve."""
    fuites = [("visible sous le seuil", i) for i, v in enumerate(visibles) if v is not None and v < SEUIL]
    if visibles[0] is None:
        if any(v is not None for v in visibles[1:]):
            fuites.append(("compte visible avec audited masqué", visibles))
        return fuites
    vis = [i for i in range(4) if visibles[i + 1] is not None]
    for taille in range(len(vis) + 1):
        for partie in itertools.combinations(vis, taille):
            reste = [i for i in range(4) if i not in partie]
            valeur = audites - sum(comptes[i] for i in partie)
            if reste and all(visibles[i + 1] is None for i in reste) and (len(reste) == 1 or valeur < SEUIL):
                fuites.append(("différence dans la ligne", partie, reste, valeur))
    return fuites


def fuites_produit(produit_brut, produit_visible, equipes_brutes, equipes_visibles):
    """Fuites entre la ligne du produit et les lignes d'équipe d'un même genre et critère, colonne par colonne : le produit visible moins
    toute partie des cellules d'équipe visibles redonne la somme des autres (exact quand aucun élément n'a deux équipes)."""
    fuites = []
    for colonne in range(5):
        if produit_visible[colonne] is None:
            continue
        cellules = [(brut[colonne], vis[colonne]) for brut, vis in zip(equipes_brutes, equipes_visibles)]
        vis = [j for j, (_, v) in enumerate(cellules) if v is not None]
        for taille in range(len(vis) + 1):
            for partie in itertools.combinations(vis, taille):
                reste = [j for j in range(len(cellules)) if j not in partie]
                valeur = produit_brut[colonne] - sum(cellules[j][0] for j in partie)
                if reste and all(cellules[j][1] is None for j in reste) and (len(reste) == 1 or valeur < SEUIL):
                    fuites.append(("produit moins équipes", colonne, partie, reste, valeur))
    return fuites


def fuites_couverture(visibles):
    """Fuites d'une ligne de couverture (collected, audited, empty_acceptance_criteria) : une cellule visible sous 5, ou deux cellules
    visibles dont la différence est sous 5. `audited` compte comme visible dès 5 (il est public par quality_by_team)."""
    fuites = [("visible sous le seuil", i) for i, v in enumerate(visibles) if v is not None and v < SEUIL]
    for i, j in itertools.combinations(range(3), 2):
        if visibles[i] is not None and visibles[j] is not None and abs(visibles[i] - visibles[j]) < SEUIL:
            fuites.append(("différence dans la ligne", i, j))
    return fuites


# --- jeux de données fictifs -----------------------------------------------------------------------------------------------------------

def jeu(graine):
    """Éléments fictifs : (clé, genre, équipes, critère d'acceptation vide, {critère: verdict} ou None si non audité). Des équipes de
    tailles variées (dont des petites), quelques éléments sans équipe (jamais audités, Q2 (b)), des verdicts très déséquilibrés."""
    hasard = random.Random(graine)
    elements = []
    numero = 0
    for equipe in ("Equipe Zzalpha", "Equipe Zzbeta", "Equipe Zzgamma", "Equipe Zzdelta"):
        for genre in ("story", "epic"):
            poids = [hasard.choice((0, 1, 2, 10, 30)) + 0.01 for _ in VERDICTS]
            taux_audit = hasard.choice((1.0, 1.0, 0.9, 0.6))
            taux_vide = hasard.choice((0.0, 0.1, 0.5, 0.95))
            for _ in range(hasard.choice((0, 2, 4, 6, 9, 15, 30))):
                numero += 1
                audite = hasard.random() < taux_audit
                verdicts = {code: hasard.choices(VERDICTS, poids)[0] for code in ("c1", "c2")} if audite else None
                elements.append((f"ZZM-{numero}", genre, (equipe,), hasard.random() < taux_vide, verdicts))
    for _ in range(hasard.choice((0, 3, 7))):
        numero += 1
        elements.append((f"ZZM-{numero}", "story", (), hasard.random() < 0.5, None))
    return elements


def attendu(elements):
    """Les trois vues selon la référence : {vue: {clé de ligne: cellules}} et les comptes bruts pour les vérificateurs."""
    equipe_brut, produit_brut, couv_brut = {}, {}, {}
    for _, genre, equipes, vide, verdicts in elements:
        for equipe in equipes or (SANS_EQUIPE,):
            c = couv_brut.setdefault((equipe, genre), [0, 0, 0])
            c[0] += 1
            c[1] += verdicts is not None
            c[2] += vide
        if verdicts is None:
            continue
        for code, verdict in verdicts.items():
            for equipe in equipes or (SANS_EQUIPE,):
                ligne = equipe_brut.setdefault((equipe, genre, code), [0, [0, 0, 0, 0]])
                ligne[0] += 1
                ligne[1][VERDICTS.index(verdict)] += 1
            ligne = produit_brut.setdefault((genre, code), [0, [0, 0, 0, 0]])
            ligne[0] += 1
            ligne[1][VERDICTS.index(verdict)] += 1
    vues = {
        "quality_by_team": {cle: ligne_visible(a, c) for cle, (a, c) in equipe_brut.items()},
        "quality_coverage_by_team": {cle: masquer_couverture(*c) for cle, c in couv_brut.items()},
        "quality_by_product": {(g, code): ligne_produit_visible(a, c, [v for (e, gg, cc), v in equipe_brut.items() if (gg, cc) == (g, code)])
                               for (g, code), (a, c) in produit_brut.items()},
    }
    return vues, equipe_brut, produit_brut, couv_brut


def toutes_les_fuites(vues, equipe_brut, produit_brut, couv_brut):
    fuites = []
    for cle, (a, c) in equipe_brut.items():
        fuites += [(cle, f) for f in fuites_ligne(a, c, vues["quality_by_team"][cle])]
    for cle, (a, c) in produit_brut.items():
        visible = vues["quality_by_product"][cle]
        fuites += [(cle, f) for f in fuites_ligne(a, c, visible)]
        cles_equipes = [k for k in equipe_brut if k[1:] == cle]
        fuites += [(cle, f) for f in fuites_produit((a, *c), visible, [(equipe_brut[k][0], *equipe_brut[k][1]) for k in cles_equipes],
                                                    [vues["quality_by_team"][k] for k in cles_equipes])]
    for cle in couv_brut:
        fuites += [(cle, f) for f in fuites_couverture(vues["quality_coverage_by_team"][cle])]
    return fuites


class SansBase(unittest.TestCase):
    def test_toute_ligne_de_comptes_jusqu_a_12_sans_fuite(self):
        for comptes in itertools.product(range(13), repeat=4):
            audites = sum(comptes)
            visibles = ligne_visible(audites, list(comptes))
            self.assertEqual(fuites_ligne(audites, list(comptes), visibles), [], comptes)

    def test_un_seul_compte_sous_5_en_masque_un_second_jamais_audited(self):
        self.assertEqual(ligne_visible(63, [3, 20, 20, 20]), (63, None, None, 20, 20))       # égalité : l'ordre des colonnes
        self.assertEqual(ligne_visible(29, [20, 3, 6, 0]), (29, 20, None, None, None))      # 3 + 0 sous 5 : le 6 est masqué aussi
        self.assertEqual(ligne_visible(23, [3, 20, 0, 0]), (23, None, None, None, None))    # 3 + 0 + 0 sous 5 : le 20 aussi
        self.assertEqual(ligne_visible(12, [6, 6, 0, 0]), (12, None, 6, None, None))        # deux zéros : leur somme nulle les redonnerait

    def test_toute_ligne_de_couverture_jusqu_a_40_sans_fuite(self):
        for collectes in range(41):
            for audites in range(collectes + 1):
                for vides in range(collectes + 1):
                    self.assertEqual(fuites_couverture(masquer_couverture(collectes, audites, vides)), [], (collectes, audites, vides))

    def test_tout_audite_masque_les_collectes(self):
        self.assertEqual(masquer_couverture(40, 40, 0), (None, 40, None))
        self.assertEqual(masquer_couverture(40, 30, 12), (40, 30, 12))

    def test_une_seule_petite_equipe_masque_la_ligne_du_produit(self):
        self.assertEqual(ligne_produit_visible(33, [11, 11, 6, 5], [(30, [10, 10, 5, 5]), (3, [1, 1, 1, 0])]), (None,) * 5)
        self.assertEqual(ligne_produit_visible(60, [20, 20, 10, 10], [(30, [10, 10, 5, 5]), (30, [10, 10, 5, 5])]), (60, 20, 20, 10, 10))

    def test_une_colonne_masquee_au_produit_ne_declenche_pas_le_masquage_secondaire(self):
        # aucun « sans objet » ni « indéterminé » nulle part : les zéros sont masqués au produit comme aux équipes, rien ne se soustrait
        equipes = [(30, [15, 15, 0, 0]), (20, [10, 10, 0, 0])]
        self.assertEqual(ligne_produit_visible(50, [25, 25, 0, 0], equipes), (50, None, 25, None, None))

    def test_jeux_tires_au_hasard_sans_fuite(self):
        for graine in range(200):
            vues, *bruts = attendu(jeu(graine))
            self.assertEqual(toutes_les_fuites(vues, *bruts), [], graine)

    def test_les_verificateurs_trouvent_une_fuite_quand_on_retire_un_masquage(self):
        # garde du test : sans le complément, un compte masqué seul se retrouve, et une seule cellule d'équipe masquée aussi
        self.assertNotEqual(fuites_ligne(33, [3, 20, 5, 5], (33, None, 20, 5, 5)), [])       # un seul compte masqué
        self.assertNotEqual(fuites_ligne(28, [3, 20, 5, 0], (28, None, 20, 5, None)), [])    # deux masqués de somme 3
        self.assertNotEqual(fuites_ligne(28, [3, 20, 5, 0], (28, None, 20, 5, 0)), [])       # un zéro visible
        self.assertEqual(fuites_ligne(33, [3, 20, 5, 5], (33, None, 20, None, 5)), [])       # deux masqués de somme 8 : un intervalle
        self.assertNotEqual(fuites_produit((33, 11, 11, 6, 5), (33, 11, 11, 6, 5), [(30, 10, 10, 5, 5), (3, 1, 1, 1, 0)],
                                           [(30, 10, 10, 5, 5), (None,) * 5]), [])
        self.assertNotEqual(fuites_couverture((40, 38, None)), [])

    def test_la_migration_recree_les_trois_vues_avec_leurs_droits(self):
        texte = (Path(db.DOSSIER_MIGRATIONS) / MIGRATION).read_text(encoding="utf-8")
        for vue in ("quality_by_team", "quality_coverage_by_team", "quality_by_product"):
            self.assertIn(f"DROP VIEW quality.{vue};", texte)
            self.assertIn(f"CREATE VIEW quality.{vue} AS", texte)
        self.assertRegex(texte, r"GRANT SELECT ON quality\.quality_by_team, quality\.quality_coverage_by_team, quality\.quality_by_product "
                                r"TO pmzilla_quality_views;")
        self.assertIn("GRANT EXECUTE ON FUNCTION quality.mask_verdicts(bigint[]) TO pmzilla_quality, pmzilla_quality_ro, pmzilla_quality_views;",
                      texte)
        sans_commentaires = "\n".join(l.split("--")[0] for l in texte.splitlines())
        self.assertNotIn("overlay_id AS", sans_commentaires)
        self.assertEqual(len(re.findall(r"c\.core_grid_version, c\.overlay_version\s*\nFROM", sans_commentaires)), 3)


class AvecBase(unittest.TestCase):
    """Base jetable migrée (toutes les migrations du dépôt), supprimée à la fin."""

    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.c = db.connect(base.url_vers(self.nom_base), password=base.MOT_DE_PASSE)
        db.migrer(self.c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        self.c.commit()

    def _supprimer(self):
        with contextlib.suppress(Exception):
            self.c.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def charger(self, elements, coeur="3", surcouche=("", "")):
        c = self.c
        c.execute("SET ROLE pmzilla_quality")
        c.execute("DELETE FROM quality.items")
        for cle, genre, equipes, vide, verdicts in elements:
            c.execute("INSERT INTO quality.items (key, kind, created_at, updated_at) VALUES (%s, %s, now(), now())", (cle, genre))
            for position, equipe in enumerate(equipes, start=1):
                c.execute("INSERT INTO quality.item_teams (item_key, team, position) VALUES (%s, %s, %s)", (cle, equipe, position))
            c.execute("INSERT INTO quality.contents (item_key, acceptance_criteria, content_hash) VALUES (%s, %s, 'h')",
                      (cle, "" if vide else "critère"))
            for code, verdict in (verdicts or {}).items():
                c.execute("INSERT INTO quality.assessments (item_key, core_grid_id, core_grid_version, overlay_id, overlay_version, "
                          "criterion_code, origin, link, verdict, sample) VALUES (%s, 'g', %s, %s, %s, %s, 'core', 'refinement', %s, false)",
                          (cle, coeur, surcouche[0], surcouche[1], code, verdict))
        c.execute("RESET ROLE")
        c.commit()

    def lire(self, vue, colonnes):
        self.c.execute("SET ROLE pmzilla_quality_views")
        try:
            return self.c.execute(f"SELECT {colonnes} FROM quality.{vue}").fetchall()
        finally:
            self.c.execute("RESET ROLE")

    def vues(self):
        return {
            "quality_by_team": {(r[0], r[1], r[2]): tuple(r[3:]) for r in self.lire(
                "quality_by_team", "team, item_kind, criterion_code, audited, met, not_met, not_applicable, undetermined")},
            "quality_coverage_by_team": {(r[0], r[1]): tuple(r[2:]) for r in self.lire(
                "quality_coverage_by_team", "team, item_kind, collected, audited, empty_acceptance_criteria")},
            "quality_by_product": {(r[0], r[1]): tuple(r[2:]) for r in self.lire(
                "quality_by_product", "item_kind, criterion_code, audited, met, not_met, not_applicable, undetermined")},
        }

    def test_les_vues_rendent_la_reference_et_ne_fuient_pas(self):
        for graine in range(12):
            elements = jeu(graine)
            self.charger(elements)
            obtenu = self.vues()
            reference, *bruts = attendu(elements)
            self.assertEqual(obtenu, reference, graine)
            self.assertEqual(toutes_les_fuites(obtenu, *bruts), [], graine)

    def test_un_compte_masque_seul_en_masque_un_second(self):
        verdicts = ["met"] * 20 + ["not_met"] * 3 + ["not_applicable"] * 6
        elements = [(f"ZZM-{i}", "story", ("Equipe Zzalpha",), False, {"c1": v}) for i, v in enumerate(verdicts)]
        self.charger(elements)
        self.assertEqual(self.vues()["quality_by_team"][("Equipe Zzalpha", "story", "c1")], (29, 20, None, None, None))

    def test_une_seule_petite_equipe_masque_la_ligne_du_produit(self):
        elements = [(f"ZZM-{i}", "story", ("Equipe Zzalpha",), False, {"c1": VERDICTS[i % 4]}) for i in range(40)]
        elements += [(f"ZZM-{100 + i}", "story", ("Equipe Zzbeta",), False, {"c1": "met"}) for i in range(3)]
        self.charger(elements)
        vues = self.vues()
        self.assertEqual(vues["quality_by_team"][("Equipe Zzalpha", "story", "c1")], (40, 10, 10, 10, 10))
        self.assertEqual(vues["quality_by_product"][("story", "c1")], (None,) * 5)

    def test_sans_equipe_collecte_et_non_audite_dans_la_couverture(self):
        elements = [(f"ZZM-{i}", "story", ("Equipe Zzalpha",), False, {"c1": "met"}) for i in range(10)]
        elements += [(f"ZZM-{100 + i}", "story", (), True, None) for i in range(7)]
        self.charger(elements)
        couverture = self.vues()["quality_coverage_by_team"]
        # 7 collectés, 0 audité (masqué), 7 vides masqués : collectés moins vides vaudrait 0
        self.assertEqual(couverture[(SANS_EQUIPE, "story")], (7, None, None))
        self.assertNotIn(SANS_EQUIPE, {k[0] for k in self.vues()["quality_by_team"]})

    def test_les_versions_de_la_paire_courante_et_jamais_l_identifiant_de_surcouche(self):
        elements = [(f"ZZM-{i}", "story", ("Equipe Zzalpha",), False, {"c1": "met"}) for i in range(10)]
        self.charger(elements, coeur="4", surcouche=("zzsurcouche", "2"))
        for vue in ("quality_by_team", "quality_coverage_by_team", "quality_by_product"):
            self.c.execute("SET ROLE pmzilla_quality_views")
            curseur = self.c.execute(f"SELECT * FROM quality.{vue}")
            noms = [d.name for d in curseur.description]
            lignes = curseur.fetchall()
            self.c.execute("RESET ROLE")
            self.assertEqual(noms[-2:], ["core_grid_version", "overlay_version"], vue)
            self.assertNotIn("overlay_id", noms, vue)
            self.assertEqual({tuple(l[-2:]) for l in lignes}, {("4", "2")}, vue)

    def test_le_role_des_vues_lit_les_trois_vues_et_aucune_table(self):
        self.charger([])
        for vue in ("quality_by_team", "quality_coverage_by_team", "quality_by_product"):
            self.assertEqual(self.lire(vue, "count(*)"), [(0,)])
        self.c.execute("SET ROLE pmzilla_quality_views")
        with self.assertRaises(db.psycopg.errors.InsufficientPrivilege):
            self.c.execute("SELECT * FROM quality.assessments")
        self.c.rollback()


if __name__ == "__main__":
    unittest.main()
