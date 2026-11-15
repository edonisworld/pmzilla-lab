"""
Tests du jeu synthétique de la page « préparation d'un cycle » de Mothra (tâche 39.1 de mothra-slices, conception D35).

Sans base : la forme du jeu. Les comptes attendus sont recalculés ici d'après les épiques et le référentiel synthétique (importé de
referentiel_synthetique.py, jamais copié), puis comparés aux tables que le module déclare : le jeu ne dit pas seulement qu'un témoin existe, il le
prouve. Aucune vue n'est lue : les vues de la tâche 38.1 liront ce jeu, leurs cellules sont vérifiées par la tâche 38.1.

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import ast
import builtins
import sys
import unittest
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
import jeu_synthetique as base  # noqa: E402
import panneaux_r150 as panneaux  # noqa: E402
import preparation_cycle as pc  # noqa: E402
import referentiel_synthetique as rs  # noqa: E402

SOURCE = DOSSIER / "preparation_cycle.py"
SEUIL = 5       # le plancher de masquage : en dur, comme dans les autres tests du jeu (floor of 5)
JOUR = date(2026, 1, 15)
JOURS = [JOUR + timedelta(days=i) for i in range(0, 120)]


def role_de(ref, etiquette):
    return {e.etiquette: e for e in ref.etiquettes}[etiquette]


def cycle_de_l_epique(jeu, epique):
    """Indice du cycle porté par l'étiquette de cycle sans fin de l'épique, None sans étiquette de cycle."""
    cles = [c.cle for c in jeu.referentiel.cycles]
    portees = [role_de(jeu.referentiel, p["etiquette"]).cycle_cle for p in epique["etiquettes"]
               if p["fin"] is None and role_de(jeu.referentiel, p["etiquette"]).role == "cycle"]
    assert len(portees) <= 1, epique["cle"]
    return cles.index(portees[0]) if portees else None


def dans_le_domaine(jeu, epique):
    return any(role_de(jeu.referentiel, p["etiquette"]).role == "pilot_domain" for p in epique["etiquettes"])


def colonne_de(jeu, epique):
    """La colonne du statut de l'épique d'après le référentiel ; STATUT_NON_ASSOCIE quand le statut n'est dans aucune colonne."""
    par_statut = {s.statut: s.colonne for s in jeu.referentiel.statuts}
    return par_statut.get(epique["statut"], pc.NON_ASSOCIE)


def epiques_prevues(jeu):
    """Par cycle, les épiques du domaine prévues au début du cycle : l'étiquette de ce cycle est active à l'instant du début (instant de lecture de D35)."""
    cles = [c.cle for c in jeu.referentiel.cycles]
    par_cycle = {}
    for e in jeu.epiques:
        if not dans_le_domaine(jeu, e):
            continue
        for p in e["etiquettes"]:
            r = role_de(jeu.referentiel, p["etiquette"])
            if r.role != "cycle":
                continue
            index = cles.index(r.cycle_cle)
            debut = _debut(jeu, index)
            if p["debut"] <= debut and (p["fin"] is None or p["fin"] > debut):
                par_cycle.setdefault(index, []).append(e)
    return par_cycle


def confirmation(jeu, epique):
    """La période de l'étiquette de confirmation de l'épique (la plus récente), None sans confirmation ni refus."""
    periodes = [p for p in epique["etiquettes"] if role_de(jeu.referentiel, p["etiquette"]).role == "confirmation"]
    return max(periodes, key=lambda p: p["debut"]) if periodes else None


def cycle_a_l_instant(jeu, epique, instant):
    """L'indice du cycle dont l'étiquette de cycle est posée à cet instant, None quand aucune ne l'est."""
    cles = [c.cle for c in jeu.referentiel.cycles]
    actifs = [cles.index(role_de(jeu.referentiel, p["etiquette"]).cycle_cle) for p in epique["etiquettes"]
              if role_de(jeu.referentiel, p["etiquette"]).role == "cycle" and p["debut"] <= instant and (p["fin"] is None or p["fin"] > instant)]
    return actifs[0] if len(actifs) == 1 else None


def issue_de_confirmation(jeu, epique, cycle):
    """taken_in, not_taken_in ou sans, pour ce cycle : la confirmation ne compte qu'au cycle dont l'étiquette était posée à son instant (R-20261031-63)."""
    p = confirmation(jeu, epique)
    if p is None or cycle_a_l_instant(jeu, epique, p["debut"]) != cycle:
        return "sans"
    return role_cle(jeu.referentiel, p["etiquette"])


def role_cle(ref, etiquette):
    e = role_de(ref, etiquette)
    return e.sens if e.role == "confirmation" else e.role


class Forme(unittest.TestCase):
    def test_quatre_cycles_du_referentiel_synthetique_importe(self):
        jeu = pc.construire(JOUR)
        self.assertEqual(jeu.referentiel, rs.construire(JOUR))
        self.assertEqual(len(jeu.referentiel.cycles), 4)

    def test_le_module_ne_construit_aucun_referentiel_a_lui(self):
        arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
        interdits = {"Referentiel", "Colonne", "Statut", "Etiquette", "Cycle", "StatutFlux"}
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call):
                fonction = noeud.func
                nom = fonction.attr if isinstance(fonction, ast.Attribute) else getattr(fonction, "id", "")
                self.assertNotIn(nom, interdits)
        texte = SOURCE.read_text(encoding="utf-8")
        self.assertIn("referentiel_synthetique", texte)
        self.assertNotIn(rs.PREFIXE + "colonne", texte)
        self.assertNotIn(rs.PREFIXE + "statut", texte)

    def test_aucun_fichier_ouvert(self):
        ouvrir = mock.Mock(side_effect=AssertionError("fichier ouvert"))
        with mock.patch.object(builtins, "open", ouvrir):
            pc.construire(JOUR)
        texte = SOURCE.read_text(encoding="utf-8")
        for mot in ("Flux-Lab", "open(", "read_text", "environ"):
            self.assertNotIn(mot, texte)

    def test_deterministe_et_independant_de_l_horloge(self):
        for jour in JOURS[::17]:
            self.assertEqual(pc.construire(jour), pc.construire(jour))
        self.assertNotEqual(pc.construire(JOUR).epiques, pc.construire(JOUR + timedelta(days=7)).epiques)

    def test_les_epiques_sont_les_memes_dans_les_deux_variantes(self):
        for jour in JOURS[::13]:
            valide, provisoire = pc.construire(jour, "validated"), pc.construire(jour, "not_validated")
            self.assertEqual(valide.epiques, provisoire.epiques)
            self.assertIsNotNone(valide.referentiel.valide_le)
            self.assertIsNone(provisoire.referentiel.valide_le)

    def test_variante_par_defaut_non_validee_et_variante_inconnue_refusee(self):
        self.assertIsNone(pc.construire(JOUR).referentiel.valide_le)
        with self.assertRaises(ValueError):
            pc.construire(JOUR, "autre")

    def test_instant_du_chargement_a_midi_utc_du_jour(self):
        self.assertEqual(pc.construire(JOUR).instant, datetime(2026, 1, 15, 12, tzinfo=timezone.utc))


class EpiquesDansLesColonnes(unittest.TestCase):
    """Les épiques dans les colonnes de la correspondance, provisoire (non validée) ou validée."""

    def test_comptes_par_cycle_et_colonne_des_prevues_au_debut_recalcules_egaux_aux_declares(self):
        """R-20261031-62 : les colonnes se comptent sur les épiques prévues au début du cycle ; les tardives en sortent, la déplacée reste au cycle d'origine."""
        for jour in JOURS[::11]:
            jeu = pc.construire(jour, "validated")
            noms = [c.nom for c in sorted(jeu.referentiel.colonnes, key=lambda c: c.position)] + [pc.NON_ASSOCIE]
            vu = Counter()
            for cycle, lot in epiques_prevues(jeu).items():
                for e in lot:
                    vu[(cycle, noms.index(colonne_de(jeu, e)))] += 1
            attendu = {(c, j): n for c, par_colonne in pc.COMPTES_PAR_CYCLE_ET_COLONNE.items() for j, n in enumerate(par_colonne) if n}
            self.assertEqual(dict(vu), attendu, jour)

    def test_prevues_egales_a_la_somme_des_colonnes_par_cycle(self):
        for cycle, prevues in enumerate(pc.PREVUES_AU_DEBUT):
            self.assertEqual(sum(pc.COMPTES_PAR_CYCLE_ET_COLONNE[cycle]), prevues, cycle)
        for jour in JOURS[::11]:
            jeu = pc.construire(jour, "validated")
            self.assertEqual({c: len(lot) for c, lot in epiques_prevues(jeu).items() if lot}, {c: n for c, n in enumerate(pc.PREVUES_AU_DEBUT) if n}, jour)

    def test_confirmees_plus_refusees_plus_sans_confirmation_egales_aux_prevues_par_cycle(self):
        for cycle, (confirmees, refusees, sans) in pc.CONFIRMATIONS_PREVUES.items():
            self.assertEqual(confirmees + refusees + sans, pc.PREVUES_AU_DEBUT[cycle], cycle)
        for jour in JOURS[::11]:
            jeu = pc.construire(jour, "validated")
            prevues = epiques_prevues(jeu)
            for cycle, (confirmees, refusees, sans) in pc.CONFIRMATIONS_PREVUES.items():
                vu = Counter(issue_de_confirmation(jeu, e, cycle) for e in prevues.get(cycle, []))
                self.assertEqual((vu["taken_in"], vu["not_taken_in"], vu["sans"]), (confirmees, refusees, sans), (jour, cycle))

    def test_une_confirmation_ne_compte_qu_au_cycle_dont_l_etiquette_etait_posee_a_son_instant(self):
        """R-20261031-63 : l'épique déplacée après le début compte « sans confirmation » dans le cycle d'origine, confirmée dans l'autre."""
        jeu = pc.construire(JOUR, "validated")
        prevues = epiques_prevues(jeu)
        deplacees = [e for e in prevues[0] if cycle_de_l_epique(jeu, e) == 1]
        self.assertEqual(len(deplacees), 2)
        for e in deplacees:
            self.assertEqual(issue_de_confirmation(jeu, e, 0), "sans")
        self.assertEqual([issue_de_confirmation(jeu, e, 1) for e in sorted(deplacees, key=lambda e: e["cle"])], ["taken_in", "not_taken_in"])

    def test_un_refus_deplace_ne_compte_pas_au_cycle_d_origine(self):
        jeu = pc.construire(JOUR, "validated")
        refus = [e for e in epiques_prevues(jeu)[0] if cycle_de_l_epique(jeu, e) == 1 and issue_de_confirmation(jeu, e, 1) == "not_taken_in"]
        self.assertEqual(len(refus), 1)
        self.assertEqual(issue_de_confirmation(jeu, refus[0], 0), "sans")

    def test_cas_indetermine_aucune_etiquette_de_cycle_a_l_instant_de_la_confirmation_est_sans_confirmation_une_seule_fois(self):
        jeu = pc.construire(JOUR, "validated")
        prevues = epiques_prevues(jeu)
        indetermines = [e for e in prevues[0] if cycle_de_l_epique(jeu, e) is None]
        self.assertEqual(len(indetermines), pc.INDETERMINEES)
        self.assertEqual({tuple(sorted(r)) for e in indetermines for r in [{role_cle(jeu.referentiel, p["etiquette"]) for p in e["etiquettes"]} & {"taken_in", "not_taken_in"}]},
                         {("taken_in",), ("not_taken_in",)})        # une prise et un refus, datés
        for e in indetermines:
            self.assertIsNone(cycle_a_l_instant(jeu, e, confirmation(jeu, e)["debut"]))
            self.assertEqual([c for c in range(4) if issue_de_confirmation(jeu, e, c) != "sans"], [])
            self.assertEqual([c for c, lot in prevues.items() if e in lot], [0])

    def test_les_tardives_sortent_des_colonnes_et_la_deplacee_reste_au_cycle_d_origine(self):
        jeu = pc.construire(JOUR, "validated")
        prevues = epiques_prevues(jeu)
        for cycle, nombre in enumerate(pc.TARDIVES):
            tardives = [e for e in jeu.epiques if dans_le_domaine(jeu, e) and cycle_de_l_epique(jeu, e) == cycle and
                        all(p["debut"] > _debut(jeu, cycle) for p in e["etiquettes"] if role_de(jeu.referentiel, p["etiquette"]).role == "cycle")]
            self.assertEqual(len(tardives), nombre, cycle)
            self.assertFalse({e["cle"] for e in tardives} & {e["cle"] for e in prevues.get(cycle, [])}, cycle)
        deplacees_apres = [e for e in prevues[0] if cycle_de_l_epique(jeu, e) == 1]
        self.assertEqual(len(deplacees_apres), 2)       # le déplacement (0, 1, 2, False) : prévues au cycle 0 et au cycle 1

    def test_les_cinq_lignes_dont_la_ligne_statut_non_associe_ont_une_epique_au_moins_dans_un_cycle(self):
        for j in range(5):
            self.assertTrue(any(par_colonne[j] for par_colonne in pc.COMPTES_PAR_CYCLE_ET_COLONNE.values()), j)

    def test_le_statut_non_associe_est_celui_du_referentiel_synthetique(self):
        jeu = pc.construire(JOUR, "validated")
        self.assertEqual(pc.NON_ASSOCIE, "statut-non-associe")      # le nom de la ligne de la page, distinct du statut inventé
        self.assertNotIn(rs.STATUT_NON_ASSOCIE, {s.statut for s in jeu.referentiel.statuts})
        self.assertTrue(any(e["statut"] == rs.STATUT_NON_ASSOCIE for e in jeu.epiques))

    def test_chaque_statut_porte_est_dans_le_referentiel_ou_est_le_statut_non_associe(self):
        jeu = pc.construire(JOUR)
        connus = {s.statut for s in jeu.referentiel.statuts} | {rs.STATUT_NON_ASSOCIE}
        self.assertLessEqual({e["statut"] for e in jeu.epiques}, connus)

    def test_toutes_les_colonnes_du_referentiel_recoivent_des_epiques(self):
        jeu = pc.construire(JOUR)
        self.assertEqual({colonne_de(jeu, e) for e in jeu.epiques} - {pc.NON_ASSOCIE}, {c.nom for c in jeu.referentiel.colonnes})

    def test_colonnes_calculees_seulement_avec_une_correspondance_validee(self):
        self.assertEqual(pc.lignes_par_colonne(pc.construire(JOUR, "validated")), pc.COMPTES_PAR_CYCLE_ET_COLONNE)
        self.assertIsNone(pc.lignes_par_colonne(pc.construire(JOUR, "not_validated")))

    def test_effectifs_temoins_de_1_a_4_et_exactement_5_par_cycle_et_colonne(self):
        cellules = [n for par_colonne in pc.COMPTES_PAR_CYCLE_ET_COLONNE.values() for n in par_colonne if n]
        for temoin in (1, 2, 3, 4, SEUIL):
            self.assertIn(temoin, cellules, temoin)
        self.assertTrue(any(n > SEUIL for n in cellules))

    def test_les_epiques_hors_du_domaine_pilote_ne_comptent_pas(self):
        jeu = pc.construire(JOUR, "validated")
        dehors = [e for e in jeu.epiques if not dans_le_domaine(jeu, e)]
        self.assertEqual(len(dehors), pc.HORS_DOMAINE)
        self.assertGreater(len(dehors), 0)
        self.assertTrue(all(cycle_de_l_epique(jeu, e) is not None for e in dehors))     # ils portent un cycle : seul le domaine les écarte

    def test_des_epiques_sans_etiquette_de_cycle_restent_hors_des_comptes(self):
        jeu = pc.construire(JOUR, "validated")
        sans = [e for e in jeu.epiques if cycle_de_l_epique(jeu, e) is None]
        self.assertEqual(len(sans), pc.SANS_CYCLE + pc.INDETERMINEES)       # les indéterminées n'ont plus d'étiquette de cycle active
        self.assertGreater(len(sans), 0)


class CycleSansEpique(unittest.TestCase):
    def test_le_dernier_cycle_a_venir_n_a_aucune_epique_ni_aucune_etiquette(self):
        for jour in JOURS[::7]:
            jeu = pc.construire(jour, "validated")
            dernier = len(jeu.referentiel.cycles) - 1
            self.assertEqual(pc.CYCLE_SANS_EPIQUE, dernier)
            self.assertEqual([e for e in jeu.epiques if cycle_de_l_epique(jeu, e) == dernier], [])
            etiquette = next(e.etiquette for e in jeu.referentiel.etiquettes if e.role == "cycle" and e.cycle_cle == jeu.referentiel.cycles[dernier].cle)
            for e in jeu.epiques:
                self.assertNotIn(etiquette, [p["etiquette"] for p in e["etiquettes"]])
            self.assertEqual(sum(pc.COMPTES_PAR_CYCLE_ET_COLONNE[dernier]), 0)

    def test_les_autres_cycles_ont_des_epiques(self):
        for cycle in range(pc.CYCLE_SANS_EPIQUE):
            self.assertGreater(sum(pc.COMPTES_PAR_CYCLE_ET_COLONNE[cycle]), 0)


class PeriodesDesEtiquettes(unittest.TestCase):
    def test_comptes_par_cycle_et_etiquette_recalcules_egaux_aux_declares(self):
        for jour in JOURS[::11]:
            jeu = pc.construire(jour, "validated")
            vu = Counter()
            for e in jeu.epiques:
                cycle = cycle_de_l_epique(jeu, e)
                if cycle is None or not dans_le_domaine(jeu, e):
                    continue
                for cle in {role_cle(jeu.referentiel, p["etiquette"]) for p in e["etiquettes"]} & set(pc.ETIQUETTES_DU_WORKFLOW):
                    vu[(cle, cycle)] += 1
            attendu = {(cle, c): n for cle, par_cycle in pc.COMPTES_PAR_CYCLE_ET_ETIQUETTE.items() for c, n in enumerate(par_cycle) if n}
            self.assertEqual(dict(vu), attendu, jour)

    def test_effectifs_temoins_de_1_a_4_et_exactement_5_pour_les_etiquettes(self):
        valeurs = [n for par_cycle in pc.COMPTES_PAR_CYCLE_ET_ETIQUETTE.values() for n in par_cycle if n]
        for temoin in (1, 2, 3, 4, SEUIL):
            self.assertIn(temoin, valeurs, temoin)

    def test_les_quatre_etiquettes_du_workflow_sont_celles_des_roles_du_referentiel(self):
        jeu = pc.construire(JOUR)
        roles = {role_cle(jeu.referentiel, e.etiquette) for e in jeu.referentiel.etiquettes}
        self.assertLessEqual(set(pc.ETIQUETTES_DU_WORKFLOW), roles)
        self.assertEqual(set(pc.COMPTES_PAR_CYCLE_ET_ETIQUETTE), set(pc.ETIQUETTES_DU_WORKFLOW))

    def test_etiquettes_toutes_declarees_par_le_jeu_synthetique(self):
        for jour in JOURS[::19]:
            jeu = pc.construire(jour)
            declarees = rs.etiquettes_declarees(jour)
            for e in jeu.epiques:
                for p in e["etiquettes"]:
                    self.assertIn(p["etiquette"], declarees)

    def test_periodes_bien_formees_et_aucune_dans_le_futur(self):
        for jour in JOURS[::11]:
            jeu = pc.construire(jour)
            for e in jeu.epiques:
                for p in e["etiquettes"]:
                    self.assertLessEqual(p["debut"], jeu.instant, (e["cle"], p))
                    if p["fin"] is not None:
                        self.assertLess(p["debut"], p["fin"], (e["cle"], p))
                        self.assertLessEqual(p["fin"], jeu.instant, (e["cle"], p))

    def test_etiquettes_actives_aujourd_hui_recalculees_egales_aux_declarees(self):
        for role in ("ready", "epic_review"):
            for jour in JOURS[::11]:
                jeu = pc.construire(jour, "validated")
                vu = Counter()
                for e in jeu.epiques:
                    cycle = cycle_de_l_epique(jeu, e)
                    if cycle is None or not dans_le_domaine(jeu, e):
                        continue
                    for p in e["etiquettes"]:
                        if role_cle(jeu.referentiel, p["etiquette"]) == role and p["debut"] <= jeu.instant and (p["fin"] is None or p["fin"] > jeu.instant):
                            vu[cycle] += 1
                self.assertEqual({c: n for c, n in enumerate(pc.ACTIFS_AUJOURDHUI[role]) if n}, dict(vu), (role, jour))

    def test_une_periode_close_pour_ready_et_pour_la_revue_distingue_aujourd_hui_de_au_moins_une_fois(self):
        for role, closes in (("ready", pc.CLOSES_PRET), ("epic_review", pc.CLOSES_REVUE)):
            self.assertGreater(closes, 0)
            self.assertEqual(pc.COMPTES_PAR_CYCLE_ET_ETIQUETTE[role][0] - pc.ACTIFS_AUJOURDHUI[role][0], closes, role)
            jeu = pc.construire(JOUR)
            fermees = [p for e in jeu.epiques for p in e["etiquettes"] if p["fin"] is not None and role_cle(jeu.referentiel, p["etiquette"]) == role]
            self.assertEqual(len(fermees), closes, role)

    def test_sans_confirmation_declare_egal_au_reste_des_epiques_du_cycle_final(self):
        jeu = pc.construire(JOUR, "validated")
        for cycle, declare in enumerate(pc.SANS_CONFIRMATION):
            lot = [e for e in jeu.epiques if cycle_de_l_epique(jeu, e) == cycle and dans_le_domaine(jeu, e)]
            sans = [e for e in lot if not {role_cle(jeu.referentiel, p["etiquette"]) for p in e["etiquettes"]} & {"taken_in", "not_taken_in"}]
            self.assertEqual(len(sans), declare, cycle)

    def test_une_seule_etiquette_de_cycle_active_par_epique(self):
        jeu = pc.construire(JOUR)
        for e in jeu.epiques:
            actives = [p for p in e["etiquettes"] if p["fin"] is None and role_de(jeu.referentiel, p["etiquette"]).role == "cycle"]
            self.assertLessEqual(len(actives), 1, e["cle"])

    def test_confirmations_prises_et_non_prises_disjointes_et_sans_confirmation_a_cote(self):
        jeu = pc.construire(JOUR, "validated")
        for cycle, (pris, non_pris) in enumerate(zip(pc.COMPTES_PAR_CYCLE_ET_ETIQUETTE["taken_in"], pc.COMPTES_PAR_CYCLE_ET_ETIQUETTE["not_taken_in"])):
            lot = [e for e in jeu.epiques if cycle_de_l_epique(jeu, e) == cycle and dans_le_domaine(jeu, e)]
            sans = [e for e in lot if not {role_cle(jeu.referentiel, p["etiquette"]) for p in e["etiquettes"]} & {"taken_in", "not_taken_in"}]
            self.assertEqual(len(sans) + pris + non_pris, len(lot), cycle)
            for e in lot:
                roles = {role_cle(jeu.referentiel, p["etiquette"]) for p in e["etiquettes"]}
                self.assertFalse({"taken_in", "not_taken_in"} <= roles, e["cle"])


class EpiquesReplanifiees(unittest.TestCase):
    def test_replanifiees_avant_le_debut_recalculees_egales_aux_declarees(self):
        for jour in JOURS[::11]:
            jeu = pc.construire(jour, "validated")
            cycles = jeu.referentiel.cycles
            vu = Counter()
            for e in jeu.epiques:
                for p in e["etiquettes"]:
                    r = role_de(jeu.referentiel, p["etiquette"])
                    if r.role != "cycle" or p["fin"] is None:
                        continue
                    origine = [c.cle for c in cycles].index(r.cycle_cle)
                    if p["fin"].date() < cycles[origine].debut:
                        vu[origine] += 1
            self.assertEqual({c: n for c, n in pc.REPLANIFIEES_AVANT_LE_DEBUT.items() if n}, dict(vu), jour)

    def test_une_epique_deplacee_apres_le_debut_de_son_cycle_d_origine_existe(self):
        self.assertTrue(any(avant is False for (_, _, _, avant) in pc.DEPLACEMENTS))
        self.assertTrue(any(avant is True for (_, _, _, avant) in pc.DEPLACEMENTS))

    def test_le_nombre_d_epiques_a_deux_etiquettes_de_cycle_par_destination_egale_la_somme_des_deplacements(self):
        jeu = pc.construire(JOUR, "validated")
        for destination in {d for _, d, _, _ in pc.DEPLACEMENTS}:
            deplacees = [e for e in jeu.epiques if len([p for p in e["etiquettes"] if role_de(jeu.referentiel, p["etiquette"]).role == "cycle"]) == 2
                         and cycle_de_l_epique(jeu, e) == destination]
            self.assertEqual(len(deplacees), sum(n for _, d, n, _ in pc.DEPLACEMENTS if d == destination), destination)

    def test_temoins_replanifiees_avant_le_debut_de_3_et_exactement_5(self):
        self.assertEqual(sorted(n for n in pc.REPLANIFIEES_AVANT_LE_DEBUT.values() if n), [3, SEUIL])


def _debut(jeu, c):
    return datetime.combine(jeu.referentiel.cycles[c].debut, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=8)


def prevues_au_debut(jeu):
    """Par cycle, les épiques du domaine dont l'étiquette de ce cycle est active au début du cycle (le cycle prévu à l'instant du début)."""
    cles = [c.cle for c in jeu.referentiel.cycles]
    vu = Counter()
    for e in jeu.epiques:
        if not dans_le_domaine(jeu, e):
            continue
        for p in e["etiquettes"]:
            r = role_de(jeu.referentiel, p["etiquette"])
            if r.role != "cycle":
                continue
            index = cles.index(r.cycle_cle)
            debut = _debut(jeu, index)
            if p["debut"] <= debut and (p["fin"] is None or p["fin"] > debut):
                vu[index] += 1
    return vu


class CycleAuDebut(unittest.TestCase):
    """Instant de lecture D35 : le cycle prévu quand le cycle a commencé, distinct de l'étiquette actuelle."""

    def test_prevues_au_debut_recalculees_egales_aux_declarees(self):
        for jour in JOURS[::11]:
            jeu = pc.construire(jour, "validated")
            self.assertEqual({c: n for c, n in enumerate(pc.PREVUES_AU_DEBUT) if n}, dict(prevues_au_debut(jeu)), jour)

    def test_la_table_des_prevues_differe_de_celle_des_etiquettes_actuelles(self):
        actuelles = tuple(sum(par_colonne) for par_colonne in pc.EPIQUES_PAR_CYCLE_ET_COLONNE.values())
        self.assertNotEqual(pc.PREVUES_AU_DEBUT, actuelles)

    def test_l_epique_deplacee_du_cycle_0_au_cycle_1_apres_le_debut_compte_au_cycle_0(self):
        jeu = pc.construire(JOUR, "validated")
        cycle_0, debut = jeu.referentiel.cycles[0], _debut(jeu, 0)
        trouvees = [e for e in jeu.epiques if cycle_de_l_epique(jeu, e) == 1 and any(
            role_de(jeu.referentiel, p["etiquette"]).role == "cycle" and role_de(jeu.referentiel, p["etiquette"]).cycle_cle == cycle_0.cle
            and p["fin"] is not None and p["debut"] <= debut < p["fin"] for p in e["etiquettes"])]
        self.assertEqual(len(trouvees), 2)       # le déplacement (0, 1, 2, False)

    def test_temoin_prevue_tard_etiquette_posee_apres_le_debut_du_cycle(self):
        for jour in JOURS[::17]:
            jeu = pc.construire(jour, "validated")
            for c, attendu in enumerate(pc.TARDIVES):
                tardives = [e for e in jeu.epiques if dans_le_domaine(jeu, e) and cycle_de_l_epique(jeu, e) == c and
                            all(p["debut"] > _debut(jeu, c) for p in e["etiquettes"] if role_de(jeu.referentiel, p["etiquette"]).role == "cycle")]
                self.assertEqual(len(tardives), attendu, (jour, c))
        self.assertTrue(all(n > 0 for n in pc.TARDIVES[:2]))


class CandidatsEtSources(unittest.TestCase):
    def test_candidats_recalcules_egaux_aux_declares(self):
        for jour in JOURS[::11]:
            jeu = pc.construire(jour, "validated")
            drapeaux = {c.nom for c in jeu.referentiel.colonnes if c.depart or c.revue_passee}
            vu = Counter()
            for e in jeu.epiques:
                cycle = cycle_de_l_epique(jeu, e)
                if cycle is None or not dans_le_domaine(jeu, e) or colonne_de(jeu, e) not in drapeaux:
                    continue
                avec = any(role_cle(jeu.referentiel, p["etiquette"]) == "epic_review" for p in e["etiquettes"])
                vu[(cycle, avec)] += 1
            attendu = {(c, avec): n for c, (a, s) in pc.CANDIDATS.items() for avec, n in ((True, a), (False, s)) if n}
            self.assertEqual(dict(vu), attendu, jour)

    def test_avec_etiquette_de_revue_veut_dire_au_moins_une_fois_pas_aujourd_hui(self):
        """Les candidats « avec étiquette » portent l'étiquette de revue au moins une fois, période close comprise (décision de la revue de contrôle)."""
        jeu = pc.construire(JOUR, "validated")
        drapeaux = {c.nom for c in jeu.referentiel.colonnes if c.depart or c.revue_passee}
        closes = [e for e in jeu.epiques if cycle_de_l_epique(jeu, e) is not None and dans_le_domaine(jeu, e) and colonne_de(jeu, e) in drapeaux
                  and any(p["fin"] is not None and role_cle(jeu.referentiel, p["etiquette"]) == "epic_review" for p in e["etiquettes"])]
        self.assertGreater(len(closes), 0)       # un candidat dont l'étiquette de revue est close compte parmi « avec »

    def test_des_candidats_avec_et_sans_etiquette_de_revue(self):
        self.assertTrue(any(a for a, _ in pc.CANDIDATS.values()))
        self.assertTrue(any(s for _, s in pc.CANDIDATS.values()))

    def test_candidats_seulement_avec_une_correspondance_validee(self):
        self.assertEqual(pc.candidats(pc.construire(JOUR, "validated")), pc.CANDIDATS)
        self.assertIsNone(pc.candidats(pc.construire(JOUR, "not_validated")))

    def test_source_du_pret_selon_la_variante(self):
        self.assertEqual(pc.source_du_pret(pc.construire(JOUR, "not_validated")), "ready_source_label")
        self.assertEqual(pc.source_du_pret(pc.construire(JOUR, "validated")), "ready_source_column")


class Equipes(unittest.TestCase):
    def test_au_moins_trois_equipes_generiques_du_jeu_par_defaut(self):
        jeu = pc.construire(JOUR, "validated")
        equipes = {e["equipe"] for e in jeu.epiques if dans_le_domaine(jeu, e)}
        self.assertGreaterEqual(len(equipes), 3)
        self.assertLessEqual(equipes, base.EQUIPES_GENERIQUES)

    def test_variante_a_deux_equipes(self):
        for variante in rs.VARIANTES:
            jeu = pc.construire(JOUR, variante, nombre_equipes=2)
            self.assertEqual(len({e["equipe"] for e in jeu.epiques if dans_le_domaine(jeu, e)}), 2)
            self.assertLessEqual({e["equipe"] for e in jeu.epiques}, base.EQUIPES_GENERIQUES)

    def test_les_comptes_ne_dependent_pas_du_nombre_d_equipes(self):
        deux, trois = pc.construire(JOUR, "validated", 2), pc.construire(JOUR, "validated", 3)
        self.assertEqual([{k: v for k, v in e.items() if k != "equipe"} for e in deux.epiques], [{k: v for k, v in e.items() if k != "equipe"} for e in trois.epiques])

    def test_nombre_d_equipes_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            pc.construire(JOUR, "validated", 1)


class Sentinelles(unittest.TestCase):
    def test_cle_et_titre_sentinelles_dans_des_colonnes_que_aucune_vue_n_expose(self):
        jeu = pc.construire(JOUR)
        for colonne in pc.COLONNES_NON_EXPOSEES:
            self.assertTrue(all(colonne in e for e in jeu.epiques), colonne)
        self.assertEqual(set(pc.COLONNES_NON_EXPOSEES), {"cle", "resolution", "projet", "parent"})
        self.assertTrue(all("resume" not in e for e in jeu.epiques))      # le titre sentinelle est dans la colonne resolution de flow.issues

    def test_formes_de_cle_et_de_titre_et_unicite(self):
        jeu = pc.construire(JOUR)
        cles = [e["cle"] for e in jeu.epiques]
        self.assertEqual(len(cles), len(set(cles)))
        for e in jeu.epiques:
            self.assertRegex(e["cle"], r"^SYN-[0-9]+$")
            self.assertTrue(e["resolution"].startswith(pc.PREFIXE_TITRE), e["resolution"])
            self.assertEqual(e["projet"], base.SENTINELLES[0])
        self.assertEqual(len({e["resolution"] for e in jeu.epiques}), len(jeu.epiques))

    def test_les_cles_ne_heurtent_aucune_cle_des_autres_jeux(self):
        jeu = pc.construire(base.INSTANT_FIXE.date())
        autres, _ = panneaux.supplement(base.INSTANT_FIXE)       # tranches 1 et des panneaux
        autres_cles = {t["cle"] for t in autres} | {t["cle"] for t in base.construire(base.INSTANT_FIXE)}       # et la tranche 0
        self.assertFalse({e["cle"] for e in jeu.epiques} & autres_cles)

    def test_les_sentinelles_n_entrent_dans_aucune_table_declaree(self):
        declarees = repr((pc.COMPTES_PAR_CYCLE_ET_COLONNE, pc.COMPTES_PAR_CYCLE_ET_ETIQUETTE, pc.ACTIFS_AUJOURDHUI, pc.REPLANIFIEES_AVANT_LE_DEBUT,
                          pc.PREVUES_AU_DEBUT, pc.CANDIDATS, pc.SANS_CONFIRMATION, pc.CONFIRMATIONS_PREVUES, pc.EPIQUES_PAR_CYCLE_ET_COLONNE))
        jeu = pc.construire(JOUR)
        for e in jeu.epiques:
            self.assertNotIn(e["cle"], declarees)
            self.assertNotIn(e["resolution"], declarees)

    def test_aucune_personne_dans_les_epiques_seulement_une_equipe_generique(self):
        jeu = pc.construire(JOUR)
        for e in jeu.epiques:
            self.assertEqual(set(e), {"cle", "resolution", "projet", "parent", "type", "statut", "equipe", "cree", "etiquettes"})
            self.assertEqual(e["type"], "Epic")
            self.assertIn(e["equipe"], base.EQUIPES_GENERIQUES)


if __name__ == "__main__":
    unittest.main()
