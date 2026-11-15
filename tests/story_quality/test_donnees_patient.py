"""
Tests du détecteur de données de patient tools/patient_data.py (change patient-data-detection, tâches 2.1 à 2.4, design D1, D2 et D14).

Jeu synthétique construit ICI : un cas positif et les faux positifs attendus de D2 par catégorie, noms-sentinelles inventés, numéros
construits par le test (structure nationale et clé valide), téléphones, adresses et étiquette facultative inventés. Aucun texte réel,
aucune valeur lue dans une base.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import patient_data as pd  # noqa: E402

NOM = "Zzpatientnom"                    # nom-sentinelle inventé
PRENOM = "Zzprenomfictif"
NOM_MAJ = "ZZNOMFICTIF"
ETIQUETTE = "zzdossierlocal"           # étiquette facultative inventée


def numero_secu(sexe="1", annee="85", mois="05", dept="75", commune="123", ordre="456", cle=True, separateur="") -> str:
    """Numéro construit avec la structure nationale et, si demandé, la clé valide ; `cle` peut être un texte (clé forcée)."""
    base = sexe + annee + mois + dept + commune + ordre
    calcul = int(base.replace("2A", "19").replace("2B", "18"))
    suffixe = f"{97 - calcul % 97:02d}" if cle is True else (cle or "")
    morceaux = [sexe, annee, mois, dept, commune, ordre] + ([suffixe] if suffixe else [])
    return separateur.join(morceaux)


def comptes(texte, extra=()):
    return {c: n for c, n in pd.count(texte, extra).items() if n}


class UnParUnePourChaqueCategorie(unittest.TestCase):
    def test_p1_numero_de_securite_sociale(self):
        self.assertEqual(comptes(f"Le numéro {numero_secu()} est saisi."), {"P1": 1})
        self.assertEqual(comptes(f"Numéro {numero_secu(separateur=' ')} saisi"), {"P1": 1})
        self.assertEqual(comptes(f"Numéro {numero_secu(dept='2A')} saisi"), {"P1": 1})

    def test_p1_sans_cle_compte_et_cle_invalide_non(self):
        self.assertEqual(comptes(f"numéro {numero_secu(cle=False)}"), {"P1": 1})
        faux = numero_secu(cle="00")
        self.assertEqual(comptes(f"numéro {faux}"), {})

    def test_p1_longs_nombres_sans_la_structure_ne_comptent_pas(self):
        self.assertEqual(comptes("référence 9999999999999 interne"), {})
        self.assertEqual(comptes("version 2026102912345678"), {})

    def test_p2_identifiant_de_patient(self):
        self.assertEqual(comptes("Patient ID: 4821973 saisi"), {"P2": 1})
        self.assertEqual(comptes("Numéro patient : 4821973"), {"P2": 1})
        self.assertEqual(comptes("IPP 48219734"), {"P2": 1})
        self.assertEqual(comptes("patient n°4821973"), {"P2": 1})

    def test_p2_faux_positifs_attendus_et_absences(self):
        self.assertEqual(comptes("Le champ patient id field est affiché"), {})
        self.assertEqual(comptes("patient id 12"), {})          # moins de quatre chiffres
        self.assertEqual(comptes("la capacité identity 123456"), {})

    def test_p3_numero_de_sejour_ou_de_dossier(self):
        self.assertEqual(comptes("Record number 556677 saisi"), {"P3": 1})
        self.assertEqual(comptes("Numéro de séjour 556677"), {"P3": 1})
        self.assertEqual(comptes("encounter id: 99887766"), {"P3": 1})
        self.assertEqual(comptes("specimen no 1234AB56"), {"P3": 1})

    def test_p3_numero_interne_du_produit_sans_etiquette_ne_compte_pas(self):
        self.assertEqual(comptes("build 556677 du produit"), {})

    def test_p4_date_de_naissance(self):
        self.assertEqual(comptes("Date of birth: 12/05/1985"), {"P4": 1})
        self.assertEqual(comptes("né le 3 mai 1985"), {"P4": 1})
        self.assertEqual(comptes("born on 1985-05-12"), {"P4": 1})
        self.assertEqual(comptes("DOB 12.05.85"), {"P4": 1})
        self.assertEqual(comptes("Date de naissance : 03 mars 1985"), {"P4": 1})

    def test_p4_etiquette_sans_date_complete_ne_compte_pas(self):
        self.assertEqual(comptes("date of birth field is mandatory"), {})
        self.assertEqual(comptes("la date de naissance est affichée"), {})
        self.assertEqual(comptes("créé le 12/05/2026"), {})

    def test_p5_nom_de_patient(self):
        self.assertEqual(comptes(f"Patient {NOM} admis"), {"P5": 1})
        self.assertEqual(comptes(f"Mme {NOM} admise"), {"P5": 1})
        self.assertEqual(comptes(f"Mr {NOM_MAJ} {PRENOM} sorti"), {"P5": 1})
        self.assertEqual(comptes(f"Monsieur {NOM} {PRENOM}"), {"P5": 1})

    def test_p5_mots_courants_et_marques_ne_comptent_pas(self):
        self.assertEqual(comptes("Patient Management module"), {})
        self.assertEqual(comptes("Patient Journey et Patient Portal"), {})
        self.assertEqual(comptes("le patient ID est affiché"), {})
        self.assertEqual(comptes("Patient [name] admis"), {})
        self.assertEqual(comptes("Mr [person] et Mme [patient-name]"), {})

    def test_p5_nom_en_minuscule_ou_sans_civilite_ne_compte_pas(self):
        self.assertEqual(comptes(f"{NOM} est un exemple"), {})
        self.assertEqual(comptes("le patient zzminuscule"), {})

    def test_p6_date_et_nom_dans_la_meme_phrase(self):
        self.assertEqual(comptes(f"Patient {NOM}, born on 12/05/1985."), {"P4": 1, "P5": 1, "P6": 1})
        self.assertEqual(comptes(f"Patient {NOM}. Date of birth: 12/05/1985."), {"P4": 1, "P5": 1})

    def test_p7_telephone(self):
        self.assertEqual(comptes("Appeler le +33 6 12 34 56 78 demain"), {"P7": 1})
        self.assertEqual(comptes("Tel 01 23 45 67 89"), {"P7": 1})
        self.assertEqual(comptes("call (555) 123-4567"), {"P7": 1})
        self.assertEqual(comptes("call 555-123-4567"), {"P7": 1})

    def test_p7_dates_et_versions_ne_comptent_pas(self):
        self.assertEqual(comptes("le 2026-10-29 version 1.2.3 build 20261029"), {})

    def test_p7_identifiant_hexadecimal_ne_compte_pas(self):
        self.assertEqual(comptes('</pasted_content id="0123456789abcdef0123456789abcdef">'), {})

    def test_p8_adresse_postale(self):
        self.assertEqual(comptes("12 rue des Fictifs 99999 Villefictive"), {"P8": 1})
        self.assertEqual(comptes("221 bis avenue Imaginaire, 88888 Ailleurs"), {"P8": 1})
        self.assertEqual(comptes("12 rue des Fictifs sans code postal"), {})
        self.assertEqual(comptes("12 rue des Fictifs\n99999 Villefictive"), {})          # pas sur la même ligne

    def test_p9_fait_de_sante_lie_a_un_patient(self):
        self.assertEqual(comptes(f"Patient {NOM} a une allergy connue."), {"P5": 1, "P9": 1})
        self.assertEqual(comptes(f"Résultat du patient id 4821973."), {"P2": 1, "P9": 1})
        self.assertEqual(comptes(f"Patient {NOM}. Allergy connue."), {"P5": 1})              # une autre phrase

    def test_vocabulaire_clinique_seul_ne_compte_jamais(self):
        for texte in ("Afficher le diagnosis et le treatment dans l'écran", "L'allergie et le traitement sont listés",
                      "La condition d'acceptation porte sur le résultat", "Le patient est transféré vers le service"):
            self.assertEqual(comptes(texte), {}, texte)

    def test_identifiants_de_soignants_et_d_etablissements_ne_comptent_pas(self):
        self.assertEqual(comptes("RPPS 12345678901 du soignant, FINESS 123456789 de l'établissement"), {})
        self.assertEqual(comptes("Dr Zzmedecin du service, établissement 998877"), {})

    def test_une_marque_existante_n_est_jamais_reconnue(self):
        marques = "[person] [email] [name] [media] [ssn] [patient-id] [record-no] [birth-date] [patient-name] [phone] [address]"
        self.assertEqual(comptes(marques), {})
        self.assertEqual(comptes("patient id [patient-id] né le [birth-date] Mr [patient-name] tel [phone]"), {})
        self.assertEqual(comptes("Patient [name] born on [birth-date]."), {})


class Contrats(unittest.TestCase):
    def test_le_resultat_ne_porte_que_des_codes_et_des_entiers(self):
        texte = f"Patient {NOM}, born on 12/05/1985, numéro {numero_secu()}, tel 01 23 45 67 89."
        resultat = pd.count(texte)
        self.assertEqual(tuple(resultat), pd.CATEGORIES)
        self.assertTrue(all(isinstance(c, str) and isinstance(n, int) and not isinstance(n, bool) for c, n in resultat.items()))
        self.assertNotIn(NOM, repr(resultat))
        self.assertNotIn(numero_secu(), repr(resultat))

    def test_texte_vide_ou_absent(self):
        self.assertEqual(sum(pd.count("").values()), 0)
        self.assertEqual(sum(pd.count(None).values()), 0)

    def test_une_etiquette_facultative_etend_p2(self):
        texte = f"{ETIQUETTE} 99887766 saisi"
        self.assertEqual(comptes(texte), {})
        self.assertEqual(comptes(texte, [ETIQUETTE]), {"P2": 1})
        self.assertEqual(comptes(texte.upper(), [ETIQUETTE.capitalize()]), {"P2": 1})
        self.assertEqual(comptes(f"{ETIQUETTE} sans chiffres", [ETIQUETTE]), {})

    def test_l_etiquette_facultative_n_apparait_pas_dans_le_resultat(self):
        self.assertNotIn(ETIQUETTE, repr(pd.count(f"{ETIQUETTE} 99887766", [ETIQUETTE])))

    def test_empreinte_de_la_liste_facultative(self):
        self.assertIsNone(pd.labels_fingerprint(None))
        self.assertIsNone(pd.labels_fingerprint([]))
        self.assertIsNone(pd.labels_fingerprint(["  "]))
        a = pd.labels_fingerprint([ETIQUETTE, "zzautre"])
        self.assertEqual(a, pd.labels_fingerprint(["ZZAUTRE", ETIQUETTE.upper()]))
        self.assertNotEqual(a, pd.labels_fingerprint([ETIQUETTE]))
        self.assertNotIn(ETIQUETTE, a)

    def test_la_version_du_detecteur_est_un_entier_positif(self):
        self.assertIsInstance(pd.DETECTOR_VERSION, int)
        self.assertGreaterEqual(pd.DETECTOR_VERSION, 1)

    def test_aucune_bibliotheque_reseau(self):
        arbre = ast.parse((TOOLS / "patient_data.py").read_text(encoding="utf-8"))
        importes = {a.name.split(".")[0] for n in ast.walk(arbre) if isinstance(n, ast.Import) for a in n.names}
        importes |= {n.module.split(".")[0] for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertEqual(importes - {"__future__", "bisect", "hashlib", "re", "unicodedata", "functools"}, set())


class Masquage(unittest.TestCase):
    TEXTES = (
        f"Le numéro {numero_secu()} est saisi.",
        "Patient ID: 4821973 saisi",
        "Record number 556677 saisi",
        "Date of birth: 12/05/1985",
        f"Patient {NOM} admis",
        f"Mr {NOM_MAJ} {PRENOM} sorti",
        f"Patient {NOM}, born on 12/05/1985.",
        "Appeler le +33 6 12 34 56 78 demain",
        "Tel 01 23 45 67 89",
        "12 rue des Fictifs 99999 Villefictive",
        f"Patient {NOM} a une allergy connue.",
        f"{ETIQUETTE} 99887766 saisi",
        f"Patient {NOM} né le 3 mai 1985, numéro {numero_secu(separateur=' ')}, tel 01 23 45 67 89, 12 rue des Fictifs 99999 Ville.",
    )

    def test_count_de_mask_est_zero_pour_toutes_les_categories(self):
        for texte in self.TEXTES:
            with self.subTest(texte=texte):
                masque, _ = pd.mask(texte, [ETIQUETTE])
                self.assertEqual(comptes(masque, [ETIQUETTE]), {}, masque)

    def test_les_valeurs_trouvees_disparaissent_et_les_marques_apparaissent(self):
        masque, n = pd.mask(f"Patient {NOM} né le 3 mai 1985, numéro {numero_secu()}, tel 01 23 45 67 89.")
        for valeur in (NOM, "3 mai 1985", numero_secu(), "01 23 45 67 89"):
            self.assertNotIn(valeur, masque)
        for marque in ("[patient-name]", "[birth-date]", "[ssn]", "[phone]"):
            self.assertIn(marque, masque)
        self.assertEqual(n, 4)

    def test_le_masquage_garde_le_reste_du_texte(self):
        masque, n = pd.mask("Afficher le diagnosis dans l'écran, sans patient identifié.")
        self.assertEqual((masque, n), ("Afficher le diagnosis dans l'écran, sans patient identifié.", 0))

    def test_mask_ne_touche_pas_aux_marques_existantes(self):
        texte = "Patient [name] et [person] écrit à [email]"
        self.assertEqual(pd.mask(texte), (texte, 0))

    def test_mask_n_ajoute_rien_pour_p6_et_p9(self):
        masque, n = pd.mask(f"Patient {NOM}, born on 12/05/1985, a une allergy.")
        self.assertEqual(n, 2)
        self.assertEqual(masque, "Patient [patient-name], born on [birth-date], a une allergy.")


if __name__ == "__main__":
    unittest.main()
