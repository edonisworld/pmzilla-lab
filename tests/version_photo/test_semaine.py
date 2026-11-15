"""
Fonction pure d'une semaine de tools/version_photo.py (change version-quality-photo, tâche 1.2 ; spec jira-flow-version-photo, design D6 et D7).
Aucune base, aucune sortie : des tickets inventés et un instant d'état.
"""
import datetime as dt
import unittest

from aide_version_photo import defaut, jour, regles, vp

W = {n: dt.date(2026, 3, 2) + dt.timedelta(days=7 * (n - 1)) for n in range(1, 9)}          # les lundis des semaines 1 à 8


def photo(tickets, n, vivant=False, **remplacements):
    return vp.lignes_de_la_semaine(tickets, regles(**remplacements), W[n], vp.instant_de_la_semaine(W[n]), vivant=vivant)


def version(lignes, equipe, nom):
    trouvees = [l for l in lignes if l["team"] == equipe and l["version"] == nom]
    return trouvees[0] if trouvees else None


def libre(lignes, equipe):
    trouvees = [l for l in lignes if l["team"] == equipe and l["version"] is None]
    return trouvees[0] if trouvees else None


class InstantEtSemaine(unittest.TestCase):
    def test_etat_de_la_semaine_fin_du_vendredi_utc(self):
        self.assertEqual(vp.instant_de_la_semaine(W[1]), dt.datetime(2026, 3, 6, 23, 59, 59, 999999, tzinfo=dt.timezone.utc))

    def test_lundi_de_n_importe_quel_jour(self):
        for decalage in range(7):
            self.assertEqual(vp.lundi_de(W[1] + dt.timedelta(days=decalage)), W[1])


class TrouveEtCorrigeJamaisAdditionnes(unittest.TestCase):
    def test_defaut_dans_les_deux_comptes(self):
        d = defaut(cree="2026-03-17", resolu="2026-03-18", affects={"V"}, fix={"V"}, periodes=[("V", jour("2026-03-18"), None)])
        avant = photo([d], 2)
        self.assertEqual(avant, [])                                   # pas encore créé en semaine 2
        for n in (3, 4):
            ligne = version(photo([d], n), "Alpha", "V")
            self.assertEqual((ligne["found"], ligne["found_open"], ligne["corrected_at_week"], ligne["corrected_now"]), (1, 0, 1, 1))

    def test_aucune_colonne_ne_porte_une_somme(self):
        lignes = photo([defaut(cree="2026-03-03", resolu="2026-03-04", affects={"V"}, fix={"V"}, periodes=[("V", jour("2026-03-04"), None)])], 1)
        for ligne in lignes:
            self.assertEqual(set(ligne), {"team", "version", *vp.COMPTES_VERSION, *vp.COMPTES_LIBRES})
        self.assertFalse([c for l in lignes for c in l if "total" in c or "sum" in c or "both" in c])

    def test_trouve_ouvert_tant_que_non_resolu(self):
        d = defaut(cree="2026-03-03", resolu="2026-03-12", affects={"V"})
        self.assertEqual(version(photo([d], 1), "Alpha", "V")["found_open"], 1)
        self.assertEqual(version(photo([d], 2), "Alpha", "V")["found_open"], 0)

    def test_defaut_cree_apres_l_etat_est_ignore(self):
        self.assertEqual(photo([defaut(cree="2026-03-07", affects={"V"})], 1), [])             # un samedi : après le vendredi de la semaine

    def test_types_sans_casse_ni_espaces(self):
        d = defaut(cree="2026-03-03", affects={"V"}, type_=" BUG ")
        self.assertEqual(version(photo([d], 1), "Alpha", "V")["found"], 1)
        self.assertEqual(photo([defaut(cree="2026-03-03", affects={"V"}, type_="Story")], 1), [])


class DefautsSansVersionDAffects(unittest.TestCase):
    def test_compte_a_part_et_jamais_dans_trouve(self):
        d = defaut(cree="2026-03-10", resolu="2026-03-20", fix={"V"}, periodes=[("V", jour("2026-03-20"), None)])
        self.assertEqual(photo([d], 1), [])
        semaine2 = photo([d], 2)
        self.assertEqual(libre(semaine2, "Alpha")["defects_without_affects"], 1)
        self.assertEqual(libre(semaine2, "Alpha")["defects_created"], 1)
        self.assertIsNone(version(semaine2, "Alpha", "V"))                 # ni trouvé, ni corrigé : pas encore résolu
        semaine3 = photo([d], 3)
        self.assertEqual(version(semaine3, "Alpha", "V")["corrected_now"], 1)
        self.assertEqual(version(semaine3, "Alpha", "V")["found"], 0)

    def test_defaut_avec_version_d_affects_n_est_pas_sans_version(self):
        d = defaut(cree="2026-03-03", affects={"V"})
        self.assertEqual(libre(photo([d], 1), "Alpha")["defects_without_affects"], 0)


class FixVersionALaSemaineEtMaintenant(unittest.TestCase):
    def test_fix_version_posee_tard(self):
        d = defaut(cree="2026-03-02", resolu="2026-03-11", fix={"V"}, periodes=[("V", jour("2026-04-08"), None)])
        for n in (2, 3, 4, 5):
            ligne = version(photo([d], n), "Alpha", "V")
            self.assertEqual((ligne["corrected_at_week"], ligne["corrected_now"]), (0, 1), n)
        ligne = version(photo([d], 6), "Alpha", "V")
        self.assertEqual((ligne["corrected_at_week"], ligne["corrected_now"]), (1, 1))

    def test_periode_retiree_avant_l_etat(self):
        d = defaut(cree="2026-03-02", resolu="2026-03-04", fix={"W"},
                   periodes=[("V", jour("2026-03-04"), jour("2026-03-12")), ("W", jour("2026-03-12"), None)])
        semaine1 = photo([d], 1)
        self.assertEqual(version(semaine1, "Alpha", "W")["corrected_at_week"], 0)
        semaine2 = photo([d], 2)
        self.assertEqual(version(semaine2, "Alpha", "W")["corrected_at_week"], 1)
        self.assertIsNone(version(semaine2, "Alpha", "V"))                  # V n'est plus une fix version courante : jamais inférée

    def test_ticket_sans_historique_dans_maintenant_seulement(self):
        d = defaut(cree="2026-03-02", resolu="2026-03-04", fix={"V"})
        ligne = version(photo([d], 1), "Alpha", "V")
        self.assertEqual((ligne["corrected_at_week"], ligne["corrected_now"]), (0, 1))
        self.assertEqual(vp.sans_historique([d], regles()), 1)

    def test_sans_historique_ne_compte_que_les_defauts_a_fix_version(self):
        tickets = [defaut(fix={"V"}), defaut(fix={"V"}, periodes=[("V", jour("2026-03-04"), None)]), defaut(), defaut(type_="Story", fix={"V"}),
                   defaut(fix={"V"}, hors_export=True)]
        self.assertEqual(vp.sans_historique(tickets, regles()), 1)

    def test_photo_vivante_meme_valeur_dans_les_deux_comptes(self):
        d = defaut(cree="2026-03-02", resolu="2026-03-04", fix={"V"})                      # aucune période, comme un historique jamais collecté
        ligne = version(photo([d], 1, vivant=True), "Alpha", "V")
        self.assertEqual((ligne["corrected_at_week"], ligne["corrected_now"]), (1, 1))


class DefautsRouverts(unittest.TestCase):
    def transitions(self, *etapes):
        return [(jour(j), de, vers) for j, de, vers in etapes]

    def test_rouvert_une_fois_des_la_semaine_de_la_reouverture(self):
        # resolved_at est la dernière résolution (2 avril) ; la première fermeture date du 10 mars (semaine 2)
        d = defaut(cree="2026-03-02", resolu="2026-04-02", fix={"V"}, periodes=[("V", jour("2026-03-18"), None)],
                   transitions=self.transitions(("2026-03-10", "Open", "Closed"), ("2026-03-24", "Closed", "In Progress"),
                                                ("2026-03-26", "In Progress", "Closed"), ("2026-03-31", "Closed", "In Progress"),
                                                ("2026-04-02", "In Progress", "Closed")))
        self.assertEqual(version(photo([d], 3), "Alpha", "V")["reopened"], 0)           # fermé en semaine 2, pas encore rouvert
        self.assertEqual(version(photo([d], 4), "Alpha", "V")["reopened"], 1)           # première réouverture le 24 mars
        self.assertEqual(version(photo([d], 5), "Alpha", "V")["reopened"], 1)           # une seconde réouverture ne recompte pas
        self.assertEqual(version(photo([d], 6), "Alpha", "V")["corrected_now"], 1)

    def test_resolu_en_semaine_2_rouvert_en_4_resolu_de_nouveau_en_5(self):
        """Décision A du 2026-10-23 : l'instant de résolution se dérive des transitions, à chaque instant de photo."""
        d = defaut(cree="2026-03-02", resolu="2026-04-01", affects={"V"}, fix={"V"}, periodes=[("V", jour("2026-03-10"), None)],
                   transitions=self.transitions(("2026-03-10", "Open", "Closed"), ("2026-03-24", "Closed", "In Progress"),
                                                ("2026-04-01", "In Progress", "Closed")))
        comptes = {n: version(photo([d], n), "Alpha", "V") for n in range(1, 7)}
        self.assertEqual((comptes[1]["found_open"], comptes[1]["corrected_at_week"], comptes[1]["corrected_now"]), (1, 0, 0))
        for n in (2, 3):                                          # corrigé en semaine 2 et 3, pas rouvert
            self.assertEqual((comptes[n]["found_open"], comptes[n]["corrected_at_week"], comptes[n]["corrected_now"], comptes[n]["reopened"]),
                             (0, 1, 1, 0), n)
        for n in (4, 5, 6):                                       # rouvert dès la semaine 4, parmi les défauts corrigés au moins une fois
            self.assertEqual((comptes[n]["corrected_now"], comptes[n]["reopened"]), (1, 1), n)
        debit = {n: libre(photo([d], n), "Alpha")["resolved_week"] for n in range(1, 7)}
        self.assertEqual(debit, {1: 0, 2: 1, 3: 0, 4: 0, 5: 1, 6: 0})          # résolu en semaine 2, puis de nouveau en semaine 5

    def test_rouvert_compte_de_nouveau_comme_ouvert_jusqu_a_sa_nouvelle_resolution(self):
        """Décision 6 du 2026-10-23 : un défaut rouvert compte de nouveau comme ouvert (found_open) dès sa réouverture, en plus de « rouvert »
        parmi les défauts déjà corrigés ; il ne l'est plus une fois résolu de nouveau."""
        d = defaut(cree="2026-03-02", resolu="2026-04-01", affects={"V"}, fix={"V"}, periodes=[("V", jour("2026-03-10"), None)],
                   transitions=self.transitions(("2026-03-10", "Open", "Closed"), ("2026-03-24", "Closed", "In Progress"),
                                                ("2026-04-01", "In Progress", "Closed")))
        attendu = {1: (1, 0, 0, 0), 2: (0, 1, 1, 0), 3: (0, 1, 1, 0), 4: (1, 1, 1, 1), 5: (0, 1, 1, 1), 6: (0, 1, 1, 1)}
        for n, comptes in attendu.items():
            ligne = version(photo([d], n), "Alpha", "V")
            self.assertEqual((ligne["found_open"], ligne["corrected_at_week"], ligne["corrected_now"], ligne["reopened"]), comptes, n)

    def test_l_historique_prime_sur_resolved_at(self):
        d = defaut(cree="2026-03-02", resolu="2026-03-04", fix={"V"}, transitions=self.transitions(("2026-03-12", "Open", "Closed")))
        self.assertIsNone(version(photo([d], 1), "Alpha", "V"))                          # la première fermeture date de la semaine 2 : rien de corrigé
        self.assertEqual(version(photo([d], 2), "Alpha", "V")["corrected_now"], 1)

    def test_repli_sur_resolved_at_sans_historique_ni_fermeture(self):
        sans = defaut(cree="2026-03-02", resolu="2026-03-04", fix={"V"})
        autre = defaut(cree="2026-03-02", resolu="2026-03-04", fix={"V"}, transitions=self.transitions(("2026-03-05", "Open", "In Progress")))
        for d in (sans, autre):
            self.assertEqual(version(photo([d], 1), "Alpha", "V")["corrected_now"], 1)
        self.assertIsNone(version(photo([defaut(cree="2026-03-02", fix={"V"})], 1), "Alpha", "V"))      # jamais résolu : rien de corrigé

    def test_meme_statut_ignore(self):
        d = defaut(cree="2026-03-02", resolu="2026-03-04", fix={"V"}, transitions=self.transitions(("2026-03-05", "Closed", "closed ")))
        self.assertEqual(version(photo([d], 1), "Alpha", "V")["reopened"], 0)

    def test_statut_inconnu_n_est_pas_termine(self):
        d = defaut(cree="2026-03-02", resolu="2026-03-04", fix={"V"}, transitions=self.transitions(("2026-03-05", "Inconnu", "Open")))
        self.assertEqual(version(photo([d], 1), "Alpha", "V")["reopened"], 0)

    def test_un_defaut_rouvert_et_corrige_compte_dans_corrige_maintenant(self):
        d = defaut(cree="2026-03-02", resolu="2026-03-04", fix={"V"}, transitions=self.transitions(("2026-03-05", "Closed", "Open")))
        ligne = version(photo([d], 1), "Alpha", "V")
        self.assertEqual((ligne["corrected_now"], ligne["reopened"]), (1, 1))


class DebitEnCorrection(unittest.TestCase):
    def test_douze_items_dont_quatre_defauts_et_une_epic(self):
        tickets = [defaut(cree="2026-02-01", resolu="2026-03-04", type_="Bug") for _ in range(4)]
        tickets += [defaut(cree="2026-02-01", resolu="2026-03-05", type_="Story") for _ in range(8)]
        tickets += [defaut(cree="2026-02-01", resolu="2026-03-05", type_="Epic")]
        ligne = libre(photo(tickets, 1), "Alpha")
        self.assertEqual((ligne["resolved_week"], ligne["resolved_week_defects"]), (12, 4))

    def test_seuls_les_items_resolus_dans_la_semaine(self):
        tickets = [defaut(cree="2026-02-01", resolu="2026-02-27", type_="Story"), defaut(cree="2026-02-01", resolu="2026-03-12", type_="Story"),
                   defaut(cree="2026-02-01", resolu="2026-03-03", type_="Story")]
        self.assertEqual(libre(photo(tickets, 1), "Alpha")["resolved_week"], 1)

    def test_meme_definition_des_fermetures_pour_tous_les_types(self):
        """Décision 3 du 2026-10-23 : un item qui n'est pas un défaut se lit lui aussi dans ses transitions (repli sur resolved_at sans fermeture)."""
        histoire = vp.Ticket(type="Story", equipe="Alpha", cree=jour("2026-02-01"), resolu=jour("2026-03-04"),
                             transitions=((jour("2026-03-12"), "Open", "Closed"),))      # resolved_at (semaine 1) devance la première fermeture
        sans = vp.Ticket(type="Story", equipe="Alpha", cree=jour("2026-02-01"), resolu=jour("2026-03-04"))
        self.assertEqual(libre(photo([histoire], 1), "Alpha"), None)                     # la première fermeture est en semaine 2 : rien résolu en 1
        self.assertEqual(libre(photo([histoire], 2), "Alpha")["resolved_week"], 1)
        self.assertEqual(libre(photo([sans], 1), "Alpha")["resolved_week"], 1)           # sans transition : repli sur resolved_at
        refermee = vp.Ticket(type="Story", equipe="Alpha", cree=jour("2026-02-01"), resolu=jour("2026-03-26"),
                             transitions=((jour("2026-03-04"), "Open", "Closed"), (jour("2026-03-12"), "Closed", "Open"),
                                          (jour("2026-03-26"), "Open", "Closed")))
        debit = {n: (libre(photo([refermee], n), "Alpha") or {}).get("resolved_week", 0) for n in range(1, 6)}
        self.assertEqual(debit, {1: 1, 2: 0, 3: 0, 4: 1, 5: 0})                          # résolu en semaine 1, de nouveau en semaine 4

    def test_pas_de_part_stockee(self):
        ligne = libre(photo([defaut(cree="2026-02-01", resolu="2026-03-04", type_="Story")], 1), "Alpha")
        self.assertFalse([c for c in ligne if "share" in c or "percent" in c])


class PerimetreEtEquipes(unittest.TestCase):
    def test_tickets_sortis_de_l_export_ecartes(self):
        tickets = [defaut(cree="2026-02-01", resolu="2026-03-04", affects={"V"}, fix={"V"}, hors_export=True),
                   defaut(cree="2026-02-01", resolu="2026-03-04", type_="Story", hors_export=True)]
        self.assertEqual(photo(tickets, 1), [])

    def test_une_ligne_par_equipe_et_la_marque_sans_equipe(self):
        tickets = [defaut(cree="2026-02-01", affects={"V"}, equipe="Alpha"), defaut(cree="2026-02-01", affects={"V"}, equipe="Beta"),
                   defaut(cree="2026-02-01", affects={"V"}, equipe=vp.SANS_EQUIPE)]
        lignes = photo(tickets, 1)
        self.assertEqual(sorted(l["team"] for l in lignes if l["version"] == "V"), ["(sans équipe)", "Alpha", "Beta"])

    def test_deux_versions_une_ligne_chacune(self):
        lignes = photo([defaut(cree="2026-02-01", affects={"V", "W"})], 1)
        self.assertEqual(sorted(l["version"] for l in lignes if l["version"]), ["V", "W"])
        self.assertEqual(libre(lignes, "Alpha")["defects_created"], 1)                   # le défaut n'est créé qu'une fois

    def test_lignes_de_version_sans_compte_libre_et_inversement(self):
        lignes = photo([defaut(cree="2026-02-01", affects={"V"})], 1)
        for ligne in lignes:
            comptes = vp.COMPTES_VERSION if ligne["version"] else vp.COMPTES_LIBRES
            autres = vp.COMPTES_LIBRES if ligne["version"] else vp.COMPTES_VERSION
            self.assertTrue(all(ligne[c] is not None for c in comptes))
            self.assertTrue(all(ligne[c] is None for c in autres))


class Couverture(unittest.TestCase):
    def test_semaine_avant_la_limite_partielle(self):
        aujourdhui = dt.date(2026, 3, 30)
        limite = aujourdhui - dt.timedelta(days=60)
        r = regles(periode_jours=60)
        self.assertEqual(vp.couverture(limite - dt.timedelta(days=7), aujourdhui, r), "partial")
        self.assertEqual(vp.couverture(limite - dt.timedelta(days=1), aujourdhui, r), "partial")
        self.assertEqual(vp.couverture(limite, aujourdhui, r), "complete")                # une semaine qui commence à la limite est entière
        self.assertEqual(vp.couverture(limite + dt.timedelta(days=7), aujourdhui, r), "complete")

    def test_limite_en_milieu_de_semaine_la_semaine_de_la_limite_est_partielle(self):
        """Règle D7 : une semaine dont le lundi précède la limite est partielle, même quand la limite tombe en milieu de semaine."""
        aujourdhui = dt.date(2026, 3, 30)
        limite = aujourdhui - dt.timedelta(days=60)                                  # un jeudi
        r = regles(periode_jours=60)
        lundi = vp.lundi_de(limite)
        self.assertGreater(limite, lundi)
        self.assertEqual(vp.couverture(lundi, aujourdhui, r), "partial")
        self.assertEqual(vp.couverture(lundi + dt.timedelta(days=7), aujourdhui, r), "complete")

    def test_semaines_a_reconstruire_jusqu_a_la_derniere_terminee(self):
        d = defaut(cree="2026-01-01", resolu="2026-03-11")
        lundis = vp.semaines_a_reconstruire([d], dt.date(2026, 3, 27), regles())      # un vendredi de la semaine 4
        self.assertEqual(lundis, [W[2], W[3]])                                      # la semaine 4 est en cours : jamais reconstruite

    def test_sans_resolution_aucune_semaine(self):
        self.assertEqual(vp.semaines_a_reconstruire([defaut(cree="2026-01-01")], dt.date(2026, 3, 27), regles()), [])
        self.assertEqual(vp.semaines_a_reconstruire([], dt.date(2026, 3, 27), regles()), [])

    def test_resolution_hors_export_ignoree_pour_la_premiere_semaine(self):
        tickets = [defaut(cree="2026-01-01", resolu="2026-01-14", hors_export=True), defaut(cree="2026-01-01", resolu="2026-03-11")]
        self.assertEqual(vp.semaines_a_reconstruire(tickets, dt.date(2026, 3, 27), regles())[0], W[2])

    def test_premiere_semaine_au_plus_tot_de_la_premiere_fermeture_et_de_resolved_at(self):
        """Décision 8 du 2026-10-23 : la première fermeture des transitions peut précéder resolved_at (défaut refermé), ou l'historique être le seul
        à parler (aucun resolved_at)."""
        aujourdhui = dt.date(2026, 3, 27)
        refermee = defaut(cree="2026-01-01", resolu="2026-03-25", transitions=[(jour("2026-03-04"), "Open", "Closed"),
                                                                                 (jour("2026-03-12"), "Closed", "Open"),
                                                                                 (jour("2026-03-25"), "Open", "Closed")])
        self.assertEqual(vp.semaines_a_reconstruire([refermee], aujourdhui, regles())[0], W[1])      # première fermeture : semaine 1, resolved_at : semaine 4
        seule = defaut(cree="2026-01-01", transitions=[(jour("2026-03-11"), "Open", "Closed")])
        self.assertEqual(vp.semaines_a_reconstruire([seule], aujourdhui, regles())[0], W[2])
        tard = defaut(cree="2026-01-01", resolu="2026-03-11", transitions=[(jour("2026-03-19"), "Open", "Closed")])
        self.assertEqual(vp.semaines_a_reconstruire([tard], aujourdhui, regles())[0], W[2])         # resolved_at plus tôt que l'historique : il l'emporte
        rouverture = defaut(cree="2026-01-01", transitions=[(jour("2026-03-04"), "Closed", "Open")])
        self.assertEqual(vp.semaines_a_reconstruire([rouverture], aujourdhui, regles()), [])         # aucune fermeture : rien


if __name__ == "__main__":
    unittest.main()
