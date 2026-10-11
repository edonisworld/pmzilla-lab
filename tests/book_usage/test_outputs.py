"""Garanties de sortie : aucune sentinelle, aucun réseau, aucune écriture en base : tâche 3.4."""
import io
import socket
import unittest
from unittest import mock

from fixtures_book_usage import ARTICLE_FILES, Base, Transcript, hit, SENTINELS, SENT_ANSWER, SENT_AFTER, FAKE_PERSON, SENT_USER


def chargee():
    t = Transcript()
    t.user(f"{SENT_USER} {FAKE_PERSON}")
    t.search([hit("flux-et-valeur.md"), hit("billet-veille.md")])
    t.read("flux-et-valeur.md")
    t.say(f"[Posture: Delivery]\n{SENT_ANSWER} {FAKE_PERSON} : Flux et valeur. hors bibliothèque {SENT_AFTER}")
    return t


LOCAL = ("127.0.0.1", "::1", "localhost")


def garde_reseau(*args, **kwargs):
    """Échoue pour toute connexion hors boucle locale (l'adresse est le dernier argument positionnel)."""
    adresse = args[-1] if args else None
    hote = adresse[0] if isinstance(adresse, tuple) and adresse else adresse
    if hote in LOCAL:
        return None
    raise AssertionError(f"connexion réseau tentée vers {hote!r}")


class Sorties(Base):
    def lancer(self):
        self.put(chargee())
        with mock.patch.object(socket.socket, "connect", garde_reseau), \
                mock.patch.object(socket, "create_connection", garde_reseau):
            sortie = self.collect()[1] + self.report()[1]
        return sortie

    def test_sentinelles_absentes_du_rapport_et_de_la_console(self):
        sortie = self.lancer()
        rapport = self.report_text()
        self.assertIn("Flux et valeur", rapport)
        for sentinelle in SENTINELS:
            self.assertNotIn(sentinelle, rapport, sentinelle)
            self.assertNotIn(sentinelle, sortie, sentinelle)

    def test_titres_d_articles_absents(self):
        self.lancer()
        rapport = self.report_text()
        for fichier, (titre, _) in ARTICLE_FILES.items():
            self.assertNotIn(titre, rapport)
            self.assertNotIn(fichier, rapport)

    def test_la_garde_refuse_hors_boucle_locale(self):
        garde_reseau(("127.0.0.1", 80))
        with self.assertRaises(AssertionError):
            garde_reseau(("93.184.216.34", 443))

    def test_aucun_reseau(self):
        self.lancer()      # la garde lève si une connexion est ouverte : le lancement aurait échoué
        self.assertTrue(self.ledger.exists())

    def test_la_lecture_des_livres_est_injectable_et_la_base_jamais_ouverte(self):
        with mock.patch("db.connect", side_effect=AssertionError("base ouverte")):
            self.lancer()

    def test_aucune_ecriture_hors_registre_et_dossier_des_rapports(self):
        self.lancer()
        ecrits = {p for p in self.data.rglob("*") if p.is_file()}
        self.assertEqual({p.name for p in ecrits}, {"registre.jsonl"})
        autour = {p.relative_to(self.workspace).parts[:3] for p in self.workspace.rglob("*") if p.is_file()}
        self.assertEqual(autour, {("_bmad-output", "pmzilla", "usage-livres")})

    def test_les_transcriptions_ne_sont_pas_modifiees(self):
        chemin = self.put(chargee())
        avant = (chemin.read_bytes(), chemin.stat().st_mtime)
        self.collect()
        self.assertEqual((chemin.read_bytes(), chemin.stat().st_mtime), avant)


if __name__ == "__main__":
    unittest.main()
