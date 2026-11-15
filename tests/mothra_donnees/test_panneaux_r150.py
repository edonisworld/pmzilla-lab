"""
Tests de l'extension du jeu synthétique de Mothra pour les panneaux de R-150 (tâche 36.2, conception D35, D33 point 1).

Sans base : la forme du jeu. Les comptes attendus par équipe, groupe de types et trimestre clos sont recalculés ici d'après les tickets,
puis comparés aux tables que le module déclare : le jeu ne dit pas seulement qu'un témoin existe, il le prouve. Aucune base, aucune vue :
la vue v_team_flow_inout (tâche 36.1) lira ce jeu, ses cellules sont vérifiées par la tâche 36.1.

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from datetime import timedelta
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
import jeu_synthetique as base  # noqa: E402
import tranche1 as t1  # noqa: E402
import panneaux_r150 as p  # noqa: E402

MAINTENANT = base.INSTANT_FIXE
SEUIL = 5   # le plancher de masquage : en dur, comme dans les autres tests du jeu (floor of 5)


def groupe(t):
    """Le groupe de types de la vue : « story » ou « defect » ; rien pour un autre type."""
    if t["type"] == "Story":
        return "story"
    if t["type"] == base.TYPE_DEFAUT:
        return "defect"
    return None


def dans_la_population(t):
    """La population de la série du périmètre produit : ni type de portefeuille, ni projet exclu."""
    return t["type"] not in p.TYPES_PORTEFEUILLE and t["projet"] not in p.PROJETS_EXCLUS and groupe(t) is not None


def indice(date, maintenant=MAINTENANT):
    """0 : dernier trimestre civil clos ; -1 : trimestre en cours ; 4 et plus : avant l'année retenue."""
    return t1.indice_trimestre(maintenant, date)


def tables(tickets, maintenant=MAINTENANT):
    """(créés, terminés) par (équipe ou None, groupe, k) pour les trimestres clos 0 à 3, population seule : ce que la vue peut servir."""
    crees, termines = Counter(), Counter()
    for t in tickets:
        if not dans_la_population(t):
            continue
        k = indice(t["cree"], maintenant)
        if 0 <= k <= 3:
            crees[(t["equipe"], groupe(t), k)] += 1
        if t["resolu"]:
            k = indice(t["resolu"], maintenant)
            if 0 <= k <= 3:
                termines[(t["equipe"], groupe(t), k)] += 1
    return crees, termines


class Forme(unittest.TestCase):
    def setUp(self):
        self.tickets = p.construire_panneaux(MAINTENANT)

    def test_deterministe(self):
        self.assertEqual(p.construire_panneaux(MAINTENANT), p.construire_panneaux(MAINTENANT))

    def test_cles_inventees_uniques_et_disjointes_des_autres_tranches(self):
        cles = [t["cle"] for t in self.tickets]
        self.assertEqual(len(cles), len(set(cles)))
        for cle in cles:
            self.assertRegex(cle, r"^SYN-[1-9][0-9]*$")
        autres = {t["cle"] for t in base.construire(MAINTENANT)} | {t["cle"] for t in t1.construire_tranche1(MAINTENANT)}
        self.assertFalse(set(cles) & autres)

    def test_equipes_generiques_hors_des_tranches_0_et_1(self):
        noms = {t["equipe"] for t in self.tickets if t["equipe"]}
        self.assertEqual(noms, set(p.EQUIPES_PANNEAUX))
        for nom in noms:
            self.assertRegex(nom, r"^équipe [A-Z][0-9]?$")          # R-20261114-79 : « équipe W2 », témoin des tâches, sans lettre libre
        self.assertFalse(noms & base.EQUIPES_GENERIQUES)
        self.assertFalse(noms & set(t1.EQUIPES_TRANCHE1))
        for t in self.tickets:
            self.assertEqual(t["equipes"], [t["equipe"]] if t["equipe"] else [], t["cle"])

    def test_dates_coherentes(self):
        for t in self.tickets:
            self.assertLessEqual(t["cree"], MAINTENANT - timedelta(hours=1), t["cle"])
            self.assertLessEqual(t["maj"], MAINTENANT, t["cle"])
            self.assertEqual(t["categorie"] == "Done", t["resolu"] is not None, t["cle"])
            if t["resolu"]:
                self.assertLessEqual(t["resolu"], MAINTENANT - timedelta(hours=1), t["cle"])
                self.assertLess(t["cree"], t["resolu"], t["cle"])

    def test_marge_de_cinq_jours_aux_bords_des_trimestres_clos(self):
        for t in self.tickets:
            if t["resolu"] and 0 <= indice(t["resolu"]) <= 3:
                debut = t1.debut_trimestre(MAINTENANT, indice(t["resolu"]) + 1)
                fin = t1.debut_trimestre(MAINTENANT, indice(t["resolu"]))
                self.assertGreaterEqual(t["resolu"] - debut, timedelta(days=5), t["cle"])
                self.assertGreaterEqual(fin - t["resolu"], timedelta(days=5), t["cle"])
            if 0 <= indice(t["cree"]) <= 3:
                debut = t1.debut_trimestre(MAINTENANT, indice(t["cree"]) + 1)
                fin = t1.debut_trimestre(MAINTENANT, indice(t["cree"]))
                self.assertGreaterEqual(t["cree"] - debut, timedelta(days=5), t["cle"])
                self.assertGreaterEqual(fin - t["cree"], timedelta(days=5), t["cle"])

    def test_aucune_cible_de_lien_hors_du_jeu(self):
        cles = {t["cle"] for t in self.tickets}
        for t in self.tickets:
            for cible, genre in t["liens"]:
                self.assertIn(cible, cles, t["cle"])
                self.assertEqual(genre, "blocks", t["cle"])


class ComptesParEquipeEtTrimestre(unittest.TestCase):
    def setUp(self):
        self.tickets = p.construire_panneaux(MAINTENANT)
        self.crees, self.termines = tables(self.tickets)

    def test_les_tables_declarees_egalent_les_comptes_recalcules(self):
        self.assertEqual(dict(self.crees), p.CREES_ATTENDUS)
        self.assertEqual(dict(self.termines), p.TERMINES_ATTENDUS)

    def test_histoires_et_defauts_crees_et_finis_par_trimestre(self):
        for (equipe, g, k), n in p.CREES_ATTENDUS.items():
            self.assertIn(g, ("story", "defect"))
            self.assertIn(k, (0, 1, 2, 3))
        groupes_par_k = {(g, k) for (_, g, k) in self.crees} | {(g, k) for (_, g, k) in self.termines}
        for g in ("story", "defect"):
            for k in range(4):
                self.assertIn((g, k), groupes_par_k, (g, k))
        # des équipes aux comptes de création et de fin qui diffèrent, pour que « créé moins fini » ne soit pas nul partout
        self.assertTrue(any(self.crees[c] != self.termines[c] for c in self.crees))

    def test_des_defauts_avec_equipe_et_des_defauts_sans_equipe(self):
        defauts = [t for t in self.tickets if t["type"] == base.TYPE_DEFAUT]
        self.assertTrue(any(t["equipe"] for t in defauts) and any(t["equipe"] is None for t in defauts))
        for sans in (True, False):
            lot = [t for t in defauts if (t["equipe"] is None) == sans]
            self.assertTrue(any(t["resolu"] for t in lot) and any(not t["resolu"] for t in lot), sans)
        equipes_des_defauts = {e for (e, g, _) in self.crees if g == "defect"}
        self.assertIn(None, equipes_des_defauts)
        self.assertTrue(equipes_des_defauts - {None})
        # le groupe « sans équipe » ne contient que des défauts : aucune histoire du jeu n'est sans équipe
        self.assertEqual({g for (e, g, _) in self.crees if e is None}, {"defect"})

    def test_effectifs_temoins_de_1_a_4_et_de_5_pour_les_defauts_avec_et_sans_equipe(self):
        for avec in (True, False):
            valeurs = {n for table in (self.crees, self.termines) for (e, g, _), n in table.items() if g == "defect" and (e is not None) == avec}
            for temoin in (1, 2, 3, 4, SEUIL):
                self.assertIn(temoin, valeurs, (avec, temoin))
            self.assertTrue(any(v > SEUIL for v in valeurs), avec)

    def test_temoins_d_effectif_de_1_a_4_et_a_5(self):
        valeurs = set(self.crees.values()) | set(self.termines.values())
        for temoin in (1, 2, 3, 4, SEUIL):
            self.assertIn(temoin, valeurs, temoin)
        self.assertTrue(any(v > SEUIL for v in valeurs))

    def test_les_effectifs_temoins_sont_portes_par_une_equipe_de_petite_taille(self):
        w = [n for table in (self.crees, self.termines) for c, n in table.items() if c[0] == p.TEMOIN_PETIT]
        self.assertTrue(w)
        self.assertTrue(any(n < SEUIL for n in w) and any(n == SEUIL for n in w))


class ElementsQuiResteDehors(unittest.TestCase):
    def setUp(self):
        self.tickets = p.construire_panneaux(MAINTENANT)

    def test_des_elements_de_portefeuille_dans_les_trimestres_retenus(self):
        portefeuille = [t for t in self.tickets if t["type"] in p.TYPES_PORTEFEUILLE]
        self.assertTrue(portefeuille)
        self.assertEqual({t["type"] for t in portefeuille}, set(p.TYPES_PORTEFEUILLE))
        self.assertTrue(any(t["resolu"] and 0 <= indice(t["resolu"]) <= 3 for t in portefeuille))
        self.assertTrue(any(not t["resolu"] for t in portefeuille))
        self.assertFalse(any(dans_la_population(t) for t in portefeuille))

    def test_des_elements_d_un_projet_exclu_des_types_de_la_population(self):
        exclus = [t for t in self.tickets if t["projet"] in p.PROJETS_EXCLUS]
        self.assertTrue(exclus)
        self.assertTrue({"story", "defect"} <= {groupe(t) for t in exclus})
        self.assertTrue(any(t["resolu"] and 0 <= indice(t["resolu"]) <= 3 for t in exclus))
        self.assertFalse(any(dans_la_population(t) for t in exclus))
        for t in self.tickets:
            if t["projet"] not in p.PROJETS_EXCLUS:
                self.assertEqual(t["projet"], base.SENTINELLES[0], t["cle"])

    def test_les_tenir_dedans_changerait_les_comptes(self):
        # sans l'exclusion, les comptes de l'équipe V (histoires terminées au dernier trimestre clos) seraient plus gros
        def termines_v(filtre):
            return sum(1 for t in self.tickets if filtre(t) and t["equipe"] == "équipe V" and t["type"] in ("Story", *p.TYPES_PORTEFEUILLE)
                       and t["resolu"] and indice(t["resolu"]) == 0)
        self.assertGreater(termines_v(lambda t: True), termines_v(dans_la_population))
        # les défauts sans équipe d'un projet exclu changeraient le compte du groupe « sans équipe »
        sans = [t for t in self.tickets if t["equipe"] is None and t["type"] == base.TYPE_DEFAUT and t["resolu"] and indice(t["resolu"]) == 1]
        self.assertGreater(len(sans), sum(1 for t in sans if dans_la_population(t)))

    def test_cas_vide_une_equipe_sans_cellule_servie(self):
        z = [t for t in self.tickets if t["equipe"] == p.TEMOIN_VIDE]
        self.assertTrue(z)
        crees, termines = tables(self.tickets)
        self.assertFalse([c for c in (*crees, *termines) if c[0] == p.TEMOIN_VIDE])
        self.assertNotIn(p.TEMOIN_VIDE, {c[0] for c in p.CREES_ATTENDUS} | {c[0] for c in p.TERMINES_ATTENDUS})


class PremierTrimestreTronque(unittest.TestCase):
    def setUp(self):
        self.tickets = p.construire_panneaux(MAINTENANT)

    def test_un_pic_de_creations_a_l_import_au_premier_trimestre_retenu(self):
        pic = t1.debut_trimestre(MAINTENANT, 4) + timedelta(days=p.JOURS_AVANT_LE_PIC)
        du_pic = [t for t in self.tickets if dans_la_population(t) and pic <= t["cree"] < pic + timedelta(days=2)]
        self.assertGreaterEqual(len(du_pic), p.ELEMENTS_DU_PIC)
        self.assertEqual({indice(t["cree"]) for t in du_pic}, {3})
        crees, _ = tables(self.tickets)
        v = {k: crees[("équipe V", "story", k)] for k in range(4)}
        self.assertGreaterEqual(v[3], 1.5 * max(v[0], v[1], v[2]))
        d = {k: crees[(None, "defect", k)] for k in range(4)}
        self.assertGreater(d[3], max(d[0], d[1], d[2]))

    def test_peu_d_elements_finis_au_premier_trimestre_retenu(self):
        _, termines = tables(self.tickets)
        self.assertLess(termines[("équipe V", "story", 3)], min(termines[("équipe V", "story", k)] for k in (0, 1, 2)))

    def test_des_elements_crees_avant_l_annee_retenue_et_finis_dedans(self):
        avant = [t for t in self.tickets if t["resolu"] and indice(t["cree"]) >= 4]
        self.assertTrue(avant)
        for t in avant:
            self.assertLessEqual(indice(t["resolu"]), 3, t["cle"])
        # aucune création hors de l'année retenue n'entre dans une cellule servie
        crees, _ = tables(self.tickets)
        self.assertEqual(sum(crees.values()), sum(p.CREES_ATTENDUS.values()))


class TrimestreEnCours(unittest.TestCase):
    def setUp(self):
        self.tickets = p.construire_panneaux(MAINTENANT)

    def test_des_elements_crees_et_finis_dans_le_trimestre_en_cours(self):
        en_cours = [t for t in self.tickets if indice(t["cree"]) == -1 or (t["resolu"] and indice(t["resolu"]) == -1)]
        self.assertTrue(any(indice(t["cree"]) == -1 for t in en_cours))
        self.assertTrue(any(t["resolu"] and indice(t["resolu"]) == -1 for t in en_cours))
        self.assertTrue(any(indice(t["cree"]) == -1 and t["resolu"] and indice(t["resolu"]) == -1 for t in en_cours))
        # créé avant, fini dans le trimestre en cours : compte comme créé dans son trimestre, jamais comme fini dans un trimestre clos
        self.assertTrue(any(0 <= indice(t["cree"]) <= 3 and t["resolu"] and indice(t["resolu"]) == -1 for t in en_cours))

    def test_aucune_table_ne_sert_le_trimestre_en_cours(self):
        for table in (p.CREES_ATTENDUS, p.TERMINES_ATTENDUS):
            self.assertEqual({k for (_, _, k) in table}, {0, 1, 2, 3})
        # les éléments du trimestre en cours existent dans la population : seule la règle des trimestres clos les tient dehors
        self.assertTrue(any(dans_la_population(t) and indice(t["cree"]) == -1 for t in self.tickets))

    def test_les_elements_du_trimestre_en_cours_restent_dedans_a_deux_instants(self):
        debut = t1.debut_trimestre(MAINTENANT, 0)
        for instant in (debut + timedelta(days=3), MAINTENANT.replace(month=3, day=31, hour=23, minute=59)):
            tickets = p.construire_panneaux(instant)
            self.assertTrue(any(indice(t["cree"], instant) == -1 for t in tickets))
            for t in tickets:
                self.assertLessEqual(t["cree"], instant - timedelta(hours=1), t["cle"])
                if t["resolu"]:
                    self.assertLessEqual(t["resolu"], instant - timedelta(hours=1), t["cle"])


class Blocages(unittest.TestCase):
    def setUp(self):
        self.tickets = p.construire_panneaux(MAINTENANT)
        self.par_cle = {t["cle"]: t for t in self.tickets}

    def bloques(self, meme_equipe):
        """Éléments terminés par (équipe, k) qui portent un lien « blocks » entrant d'un élément d'une autre équipe (ou de la même équipe)."""
        ensemble = {}
        for t in self.tickets:
            for cible, genre in t["liens"]:
                c = self.par_cle[cible]
                if genre == "blocks" and t["equipe"] and c["equipe"] and (t["equipe"] == c["equipe"]) == meme_equipe and c["resolu"] \
                        and 0 <= indice(c["resolu"]) <= 3:
                    ensemble.setdefault((c["equipe"], indice(c["resolu"])), set()).add(c["cle"])
        return {k: len(v) for k, v in ensemble.items()}

    def test_elements_bloques_par_une_autre_equipe(self):
        self.assertEqual(self.bloques(False), p.BLOQUES_PAR_UNE_AUTRE_EQUIPE)
        valeurs = list(p.BLOQUES_PAR_UNE_AUTRE_EQUIPE.values())
        self.assertTrue(any(v < SEUIL for v in valeurs), "une cellule sous 5")
        self.assertTrue(any(v == SEUIL for v in valeurs), "une cellule exactement à 5")
        self.assertTrue(any(v > SEUIL for v in valeurs), "une cellule plus grande")

    def test_elements_bloques_par_la_meme_equipe_ne_comptent_pas_dans_la_part(self):
        self.assertEqual(self.bloques(True), p.BLOQUES_PAR_LA_MEME_EQUIPE)
        self.assertTrue(p.BLOQUES_PAR_LA_MEME_EQUIPE)
        # les éléments bloqués par la même équipe ne sont pas ceux qu'une autre équipe bloque : les deux comptes sont disjoints
        autre, meme = set(), set()
        for t in self.tickets:
            for cible, _ in t["liens"]:
                c = self.par_cle[cible]
                (meme if t["equipe"] == c["equipe"] else autre).add(cible)
        self.assertFalse(autre & meme)

    def test_le_bloqueur_est_d_une_autre_equipe_et_porte_le_lien(self):
        pairs = [(t, self.par_cle[cible]) for t in self.tickets for cible, _ in t["liens"]]
        self.assertTrue(any(t["equipe"] != c["equipe"] for t, c in pairs))
        self.assertTrue(any(t["equipe"] == c["equipe"] for t, c in pairs))
        for t, c in pairs:
            self.assertIsNotNone(t["equipe"])
            self.assertNotEqual(t["cle"], c["cle"])


class Sentinelles(unittest.TestCase):
    def setUp(self):
        self.tickets = p.construire_panneaux(MAINTENANT)

    def test_sentinelles_dans_des_colonnes_qu_aucune_vue_n_expose(self):
        for t in self.tickets:
            for colonne in ("cle", "equipe", "type", "categorie", "statut"):
                for sentinelle in base.SENTINELLES:
                    self.assertNotIn(sentinelle, str(t[colonne]), (t["cle"], colonne))
        texte = repr(self.tickets)
        for sentinelle in base.SENTINELLES:
            self.assertIn(sentinelle, texte)
        self.assertTrue(any(t["resolution"] == base.SENTINELLES[1] for t in self.tickets if t["resolu"]))
        self.assertTrue(any(t["parent"] == base.SENTINELLES[2] for t in self.tickets))

    def test_aucun_titre_aucune_personne_aucun_champ_hors_du_schema_du_chargeur(self):
        champs_t1 = set(t1.construire_tranche1(MAINTENANT)[0])
        champs_t1.discard("ancien")
        for t in self.tickets:
            self.assertEqual(set(t), champs_t1, t["cle"])


class Branchement(unittest.TestCase):
    def test_le_supplement_ajoute_les_panneaux_a_la_tranche_1_sans_la_changer(self):
        tickets, equipes = p.supplement(MAINTENANT)
        un = t1.construire_tranche1(MAINTENANT)
        self.assertEqual(tickets[:len(un)], un)                         # les témoins existants sont intacts, dans le même ordre
        self.assertEqual(tickets[len(un):], p.construire_panneaux(MAINTENANT))
        self.assertEqual(set(equipes), set(t1.EQUIPES_TRANCHE1) | set(p.EQUIPES_PANNEAUX))
        self.assertEqual(t1.construire_tranche1(MAINTENANT), un)

    def test_le_chargeur_ecrit_le_jeu_complet_et_ses_liens(self):
        import referentiel_synthetique as rs
        from test_chargeur import FausseConnexion
        supplement = p.supplement(MAINTENANT)
        conn = FausseConnexion(equipes=[*sorted(base.EQUIPES_GENERIQUES), *t1.EQUIPES_TRANCHE1, *p.EQUIPES_PANNEAUX])
        nombre = base.charger(conn, MAINTENANT, supplement, {"blocks": rs.TYPE_LIEN_BLOQUE})
        self.assertEqual(nombre, len(base.construire(MAINTENANT)) + len(supplement[0]))
        liens = sum(len(t["liens"]) for t in supplement[0])
        self.assertEqual(sum(e.startswith("INSERT INTO flow.links") for e in conn.ecritures()), liens)

    def test_une_equipe_des_panneaux_hors_de_l_ensemble_controle_refuse_le_chargement(self):
        from test_chargeur import FausseConnexion
        tickets, _ = p.supplement(MAINTENANT)
        with self.assertRaises(base.RefusJeu):
            base.charger(FausseConnexion(), MAINTENANT, (tickets, t1.EQUIPES_TRANCHE1))


if __name__ == "__main__":
    unittest.main()
