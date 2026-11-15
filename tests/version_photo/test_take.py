"""
`take` de tools/version_photo.py (change version-quality-photo, tâche 3.1 ; spec jira-flow-version-photo : photo hebdomadaire, une photo vivante
par semaine, types de défaut obligatoires). Magasin en mémoire : aucune base.
"""
import copy
import datetime as dt
import unittest

from aide_version_photo import AUJOURDHUI, MARQUES, Espace, MagasinMemoire, defaut, jour

V = "zzversion-a"
SEMAINE = dt.date(2026, 10, 19)                    # la semaine du vendredi 2026-10-23


def un_defaut(**remplacements):
    base = dict(cree="2026-01-05", resolu="2026-10-20", affects={V}, fix={V}, periodes=[(V, jour("2026-10-20"), None)], type_="zzdefaut",
                equipe="zzequipe-alpha")
    base.update(remplacements)
    return defaut(**base)


class PhotoDuVendredi(Espace):
    def test_ecrit_un_passage_vivant_complet(self):
        magasin = MagasinMemoire([un_defaut()])
        code, sortie, erreur, _, _ = self.lancer("take", "--language", "en", magasin=magasin)
        self.assertEqual(code, 0, erreur)
        self.assertIn("photo taken: week of 2026-10-19, 2 rows", sortie)                 # une ligne de version et une ligne libre
        self.assertIn("defects without fix version history: 0", sortie)
        self.assertEqual([p["source"] for p in magasin.etat["passages"]], ["live"])
        self.assertEqual(magasin.etat["passages"][0]["instant"], AUJOURDHUI)
        self.assertEqual(magasin.etat["semaines"][SEMAINE]["coverage"], "complete")
        for marque in MARQUES:
            self.assertNotIn(marque, sortie + erreur)

    def test_francais_par_defaut(self):
        _, sortie, _, _, _ = self.lancer("take", magasin=MagasinMemoire([un_defaut()]))
        self.assertEqual(sortie.splitlines(), ["photo prise : semaine du 2026-10-19, 2 lignes", "défauts sans historique de fix version : 0",
                                               "versions sans date de sortie : 1",                       # change version-release-date, design D9
                                               "versions aux attributs de sortie divergents : 0"])

    def test_meme_fonction_de_semaine_que_la_reconstruction(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("take", magasin=magasin)
        lignes = {(l["team"], l["version_no"]): l for l in magasin.lignes_de(SEMAINE)}
        ligne = lignes[("zzequipe-alpha", 1)]
        self.assertEqual((ligne["found"], ligne["found_open"], ligne["corrected_now"]), (1, 0, 1))
        libre = lignes[("zzequipe-alpha", None)]
        self.assertEqual((libre["defects_created"], libre["resolved_week"], libre["resolved_week_defects"]), (1, 1, 1))

    def test_photo_vivante_meme_valeur_a_la_semaine_et_maintenant(self):
        magasin = MagasinMemoire([un_defaut(periodes=[])])                               # historique jamais collecté
        _, sortie, _, _, _ = self.lancer("take", "--language", "en", magasin=magasin)
        ligne = [l for l in magasin.lignes_de(SEMAINE) if l["version_no"] is not None][0]
        self.assertEqual((ligne["corrected_at_week"], ligne["corrected_now"]), (1, 1))
        self.assertIn("defects without fix version history: 1", sortie)

    def test_un_ticket_resolu_apres_l_instant_de_la_photo_n_est_pas_compte(self):
        magasin = MagasinMemoire([un_defaut(resolu="2026-10-24")])
        self.lancer("take", magasin=magasin)
        ligne = [l for l in magasin.lignes_de(SEMAINE) if l["version_no"] is not None][0]
        self.assertEqual((ligne["found_open"], ligne["corrected_now"]), (1, 0))

    def test_types_de_defaut_non_regles(self):
        self.ecrire_reglages("jira_site: x\n")
        magasin = MagasinMemoire([un_defaut()])
        code, sortie, _, _, ouvertures = self.lancer("take", "--language", "en", magasin=magasin)
        self.assertEqual((code, ouvertures), (3, 0))
        self.assertIn("defect types not set", sortie)
        self.assertEqual(magasin.etat["passages"], [])


class UnePhotoParSemaine(Espace):
    def test_seconde_photo_de_la_semaine_refusee(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("take", magasin=magasin)
        avant = copy.deepcopy(magasin.etat)
        code, sortie, _, _, _ = self.lancer("take", "--language", "en", magasin=magasin)
        self.assertEqual(code, 3)
        self.assertIn("photo already taken for this week: use --replace", sortie)
        self.assertNotIn("photo taken", sortie)
        self.assertEqual(magasin.etat, avant)

    def test_seconde_photo_refusee_en_francais(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("take", magasin=magasin)
        code, sortie, _, _, _ = self.lancer("take", magasin=magasin)
        self.assertEqual(code, 3)
        self.assertIn("photo déjà prise pour cette semaine : utiliser --replace", sortie)

    def test_replace_remplace_la_semaine_en_cours_seulement(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("take", magasin=magasin, maintenant=jour("2026-10-16", 14))          # semaine passée du 2026-10-12
        self.lancer("take", magasin=magasin)
        passee = copy.deepcopy(magasin.lignes_de(dt.date(2026, 10, 12)))
        magasin.tickets.append(un_defaut(equipe="zzequipe-beta"))                        # un nouveau défaut : la photo remplacée le voit
        code, sortie, erreur, _, _ = self.lancer("take", "--replace", "--language", "en", magasin=magasin)
        self.assertEqual(code, 0, erreur)
        self.assertIn("photo taken: week of 2026-10-19, 4 rows", sortie)
        self.assertEqual(magasin.lignes_de(dt.date(2026, 10, 12)), passee)               # la semaine passée n'a pas bougé
        self.assertEqual(sorted({l["team"] for l in magasin.lignes_de(SEMAINE)}), ["zzequipe-alpha", "zzequipe-beta"])
        self.assertEqual(sorted(magasin.vivantes()), [dt.date(2026, 10, 12), SEMAINE])
        self.assertEqual(len([r for r in magasin.etat["lignes"] if r["week"] == SEMAINE and r["version_no"] is None]), 2)   # pas de doublon

    def test_replace_sans_photo_existante_prend_la_photo(self):
        magasin = MagasinMemoire([un_defaut()])
        code, sortie, _, _, _ = self.lancer("take", "--replace", "--language", "en", magasin=magasin)
        self.assertEqual(code, 0)
        self.assertIn("photo taken", sortie)

    def test_une_semaine_reconstruite_n_est_jamais_remplacee(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("reconstruct", magasin=magasin, maintenant=jour("2026-11-06", 14))   # reconstruit jusqu'à la semaine du 2026-10-26
        avant = copy.deepcopy(magasin.etat)
        for options in ((), ("--replace",)):
            code, sortie, _, _, _ = self.lancer("take", *options, "--language", "en", magasin=magasin, maintenant=jour("2026-10-28", 14))
            self.assertEqual(code, 3, options)
            self.assertIn("photo already taken for this week: use --replace", sortie)
            self.assertEqual(magasin.etat, avant)

    def test_deux_semaines_differentes_se_prennent(self):
        magasin = MagasinMemoire([un_defaut()])
        self.assertEqual(self.lancer("take", magasin=magasin, maintenant=jour("2026-10-23", 14))[0], 0)
        self.assertEqual(self.lancer("take", magasin=magasin, maintenant=jour("2026-10-30", 14))[0], 0)
        self.assertEqual(sorted(magasin.vivantes()), [SEMAINE, dt.date(2026, 10, 26)])


if __name__ == "__main__":
    unittest.main()
