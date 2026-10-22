"""
Tests du nettoyage des textes avant stockage (change story-quality-audit, tâche 3.2, design D4 ; spec story-quality-collect, « Mentions
and listed names are replaced before storage », « E-mail addresses and media are replaced before storage », « Replaced values are never
shown »). Module tools/story_quality_scrub.py : fonctions pures, aucune base, aucun Jira.

Données inventées : comptes, adresses et noms « zz » sont distinctifs ; aucun ne doit rester dans un texte nettoyé.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import story_quality_scrub as scrub  # noqa: E402

NOMS = ["Zorglub Quarante", "Zorglub", "Equipe Zzorange", "media", "AB"]
COMPTE = "5b10zz2844c20165700ede21g"


def doc(*blocs):
    return {"type": "doc", "version": 1, "content": list(blocs)}


def paragraphe(*noeuds):
    return {"type": "paragraph", "content": list(noeuds)}


def texte(t, **attrs):
    return {"type": "text", "text": t, **attrs}


class Nettoyage(unittest.TestCase):
    def setUp(self):
        self.n = scrub.Nettoyeur(NOMS)

    def test_mention_riche_sans_identifiant_de_compte(self):
        valeur = doc(paragraphe(texte("Voir avec "), {"type": "mention", "attrs": {"id": COMPTE, "text": "@Personne Zzinventee",
                                                                                       "accessLevel": ""}}, texte(" demain.")))
        propre, n = self.n.nettoyer(valeur)
        self.assertEqual(propre, "Voir avec [person] demain.")
        self.assertEqual(n, 1)

    def test_liens_utilisateur_de_style_wiki(self):
        propre, n = self.n.nettoyer(f"Relu par [~accountid:{COMPTE}] et [~zzlogin].")
        self.assertEqual(propre, "Relu par [person] et [person].")
        self.assertEqual(n, 2)

    def test_adresses_electroniques(self):
        propre, n = self.n.nettoyer("Écrire à zz.personne@exemple.org ou mailto:autre_zz@exemple.fr.")
        self.assertEqual(propre, "Écrire à [email] ou mailto:[email].")
        self.assertEqual(n, 2)

    def test_noms_sensibles_sans_casse_et_en_mot_entier(self):
        propre, n = self.n.nettoyer("ZORGLUB QUARANTE a vu zorglub ; zorglubesque reste ; l'equipe zzorange aussi ; ab et AB.")
        self.assertEqual(propre, "[name] a vu [name] ; zorglubesque reste ; l'[name] aussi ; [name] et [name].")
        self.assertEqual(n, 5)

    def test_un_nom_egal_a_une_marque_ne_la_double_pas(self):
        propre, n = self.n.nettoyer(doc(paragraphe(texte("Capture :")), {"type": "mediaSingle", "content": [
            {"type": "media", "attrs": {"id": "zzmedia-id", "type": "file", "collection": "zzcollection"}}]}))
        self.assertEqual(propre, "Capture :\n[media]")
        self.assertEqual(n, 1)

    def test_medias_et_pieces_jointes(self):
        valeur = doc(paragraphe(texte("Avant")),
                     {"type": "mediaGroup", "content": [{"type": "media", "attrs": {"id": "zz1"}}, {"type": "media", "attrs": {"id": "zz2"}}]},
                     paragraphe({"type": "mediaInline", "attrs": {"id": "zz3"}}),
                     paragraphe({"type": "inlineCard", "attrs": {"url": "https://exemple.atlassian.net/rest/api/3/attachment/content/zz4"}}))
        propre, n = self.n.nettoyer(valeur)
        self.assertEqual(propre, "Avant\n[media]\n[media]\n[media]")
        self.assertEqual(n, 3)
        propre, n = self.n.nettoyer("Voir !zzcapture.png|thumbnail! et [^zzplan.pdf] ; Attention! Important!")
        self.assertEqual(propre, "Voir [media] et [media] ; Attention! Important!")
        self.assertEqual(n, 2)

    def test_structure_du_texte_riche(self):
        valeur = doc({"type": "heading", "attrs": {"level": 2}, "content": [texte("Contexte")]},
                     paragraphe(texte("Ligne un"), {"type": "hardBreak"}, texte("ligne deux")),
                     {"type": "bulletList", "content": [{"type": "listItem", "content": [paragraphe(texte("point"))]}]},
                     paragraphe(texte("Lien", marks=[{"type": "link", "attrs": {"href": "mailto:zzcache@exemple.org"}}])))
        propre, n = self.n.nettoyer(valeur)
        self.assertEqual(propre, "Contexte\nLigne un\nligne deux\npoint\nLien")
        self.assertEqual(n, 0)

    def test_valeurs_vides_et_autres_formes(self):
        self.assertEqual(self.n.nettoyer(None), ("", 0))
        self.assertEqual(self.n.nettoyer(""), ("", 0))
        self.assertEqual(self.n.nettoyer(doc()), ("", 0))
        self.assertEqual(self.n.nettoyer(["un", "zorglub"]), ("un\n[name]", 1))
        self.assertEqual(self.n.nettoyer({"value": "option zorglub"}), ("option [name]", 1))

    def test_les_attributs_inconnus_ne_ressortent_pas(self):
        valeur = doc(paragraphe(texte("ok"), {"type": "status", "attrs": {"text": "EN COURS", "localId": "zzlocal"}},
                                {"type": "date", "attrs": {"timestamp": "1700000000000"}},
                                {"type": "nouveauNoeud", "attrs": {"secret": "zzattribut"}, "content": [texte(" fin")]}))
        propre, _ = self.n.nettoyer(valeur)
        self.assertEqual(propre, "okEN COURS fin")

    def test_aucune_valeur_remplacee_ne_reste(self):
        valeur = doc(paragraphe({"type": "mention", "attrs": {"id": COMPTE, "text": "@zzmention"}},
                                texte(f" zz.mail@exemple.org Zorglub [~accountid:{COMPTE}] !zzimage.jpg!")))
        propre, n = self.n.nettoyer(valeur)
        self.assertEqual(n, 5)
        for valeur_remplacee in (COMPTE, "zzmention", "zz.mail", "Zorglub", "zzimage"):
            self.assertNotIn(valeur_remplacee, propre)

    def test_les_marques_sont_les_memes_dans_les_deux_langues(self):
        self.assertEqual(scrub.MARQUES, ("[person]", "[email]", "[name]", "[media]"))

    def test_nom_compose_malgre_les_variantes_d_ecriture(self):
        variantes = ("Zorglub Quarante", "Zorglub Quarante", "Zorglub Quarante", "Zorglub  Quarante", "Zorglub \t Quarante",
                     "Zor​glub Quarante", "Zorglub⁠ Quar﻿ante", "Zorglub ‌‍ Quarante")
        for variante in variantes:
            with self.subTest(variante=variante):
                propre, n = self.n.nettoyer(f"vu avec {variante} hier")
                self.assertEqual((propre, n), ("vu avec [name] hier", 1))

    def test_nom_avec_accent_en_forme_decomposee_dans_le_texte_ou_dans_la_liste(self):
        nettoyeur = scrub.Nettoyeur(["Zoé Zzquarante"])
        self.assertEqual(nettoyeur.nettoyer("avec Zoé Zzquarante")[0], "avec [name]")
        self.assertEqual(scrub.Nettoyeur(["Zoé Zzquarante"]).nettoyer("avec Zoé Zzquarante")[0], "avec [name]")

    def test_le_texte_rendu_est_normalise(self):
        propre, _ = self.n.nettoyer("café a​b")
        self.assertEqual(propre, "café [name]")       # « a<largeur nulle>b » est devenu « ab », nom de la liste

    def test_lien_wiki_avec_libelle(self):
        propre, n = self.n.nettoyer("Relu par [Prénom Zznom|~zzidentifiant] et [Autre Zz|~accountid:zz123], puis [~zzlogin] ; [doc|http://x.zz].")
        self.assertEqual(propre, "Relu par [person] et [person], puis [person] ; [doc|http://x.zz].")
        self.assertEqual(n, 3)

    def test_carte_vers_un_profil(self):
        adresses = ("https://exemple.atlassian.net/jira/people/zzcompte123", "https://exemple.zz/secure/ViewProfile.jspa?name=zzlogin",
                    "https://exemple.zz/ViewProfile.jspa?name=zzlogin", "https://exemple.zz/secure/ViewProfile?x=1",
                    "https://exemple.zz/page?accountId=zzcompte123")
        for adresse in adresses:
            with self.subTest(adresse=adresse):
                for genre in ("inlineCard", "blockCard", "embedCard"):
                    propre, n = self.n.nettoyer(doc(paragraphe({"type": genre, "attrs": {"url": adresse}})))
                    self.assertEqual((propre, n), ("[person]", 1))
        propre, n = self.n.nettoyer(doc(paragraphe({"type": "inlineCard", "attrs": {"url": "https://exemple.zz/browse/ZZ-1"}})))
        self.assertEqual((propre, n), ("https://exemple.zz/browse/ZZ-1", 0))

    # Revue 4.1, E2 : le texte visible d'un lien vers une page de profil est souvent un nom ; il devient la marque d'une personne.
    def test_texte_d_un_lien_vers_un_profil(self):
        lien = [{"type": "link", "attrs": {"href": "https://exemple.atlassian.net/jira/people/zzcompte123"}}]
        propre, n = self.n.nettoyer(doc(paragraphe(texte("Voir "), texte("Prénom Zzinvente", marks=lien), texte(" demain."))))
        self.assertEqual((propre, n), ("Voir [person] demain.", 1))
        autre = [{"type": "link", "attrs": {"href": "https://exemple.zz/browse/ZZ-1"}}]
        self.assertEqual(self.n.nettoyer(doc(paragraphe(texte("ticket", marks=autre))))[0], "ticket")

    def test_lien_wiki_avec_libelle_vers_un_profil(self):
        propre, n = self.n.nettoyer("Relu par [Prénom Zzinvente|https://exemple.zz/secure/ViewProfile.jspa?name=zzlogin] et "
                                    "[Autre Zzinvente|https://exemple.atlassian.net/jira/people/zzcompte123] ; [doc|https://exemple.zz/browse/ZZ-1].")
        self.assertEqual(propre, "Relu par [person] et [person] ; [doc|https://exemple.zz/browse/ZZ-1].")
        self.assertEqual(n, 2)
        for reste in ("Zzinvente", "zzlogin", "zzcompte123"):
            self.assertNotIn(reste, propre)

    def test_liste_vide_refusee(self):
        with self.assertRaises(ValueError):
            scrub.Nettoyeur([])


if __name__ == "__main__":
    unittest.main()
