"""
Catalogues de messages de tools/train_auto.py et de tools/train_ready.py (change autonomous-trains-observe, conception D11) : français et anglais
cohérents, un libellé pour chaque code de raison de la conception, et les phrases clés mot pour mot.
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import messages  # noqa: E402
import train_auto_messages  # noqa: E402
import train_ready_messages  # noqa: E402

CODES_DE_RAISON = ("hors-fenetre", "matin", "verrou-fin", "espace-de-travail", "distant", "main-different", "dossier-execution",
                   "crochets", "identite", "liste-illisible", "garde-noms", "arret-disparu", "sommet-change", "empreinte", "branche-absente",
                   "deja-fusionnee", "outillage-protege", "postures", "base", "front", "session-active", "revue", "plafond", "controle-impossible", "nom")


class Catalogues(unittest.TestCase):
    def test_les_deux_langues_sont_coherentes(self):
        self.assertEqual(messages.check_catalogs(train_auto_messages.CATALOGS), [])
        self.assertEqual(messages.check_catalogs(train_ready_messages.CATALOGS), [])

    def test_un_libelle_par_code_de_raison_dans_les_deux_langues(self):
        for code in CODES_DE_RAISON:
            for langue in ("fr", "en"):
                self.assertNotEqual(train_auto_messages.label(code, langue), code, f"{code} ({langue})")
        self.assertEqual(train_auto_messages.label("hors-fenetre", "fr"), "hors fenêtre")
        self.assertEqual(train_auto_messages.label("code-inconnu"), "code-inconnu")

    def test_les_libelles_de_la_conception(self):
        # R-20261102-3 et R-20261102-5 (D4), réécrit : le libellé du contrôle 4 dit ce qu'il refuse désormais
        attendus = {"matin": "veille ou sauvegarde du jour en cours","verrou-fin": "verrou de fin tenu",
                    "sommet-change": "sommet changé depuis l'inscription", "plafond": "au-delà du plafond : fenêtre suivante",
                    "session-active": "session active dans son worktree", "nom": "nom refusé par la garde"}
        for code, texte in attendus.items():
            self.assertEqual(train_auto_messages.label(code, "fr"), texte)

    def test_phrases_cles_du_passage(self):
        t = messages.Messages(train_auto_messages.CATALOGS, "fr")
        self.assertEqual(t("observation", n=2, k=1, c=0), "train_auto : observation : 2 branche(s) retenue(s), 1 écartée(s) ; essai code 0")
        self.assertEqual(t("nothing"), "train_auto : rien à faire")
        self.assertEqual(t("stopped"), "train_auto : arrêté (arrêt d'urgence actif)")
        self.assertEqual(t("session_refused"), "train_auto : session Claude Code, lancement refusé")
        self.assertEqual(t("already_running"), "train_auto : un autre passage est en cours")
        self.assertEqual(t("stop_armed", c=65), "train_auto : arrêt armé après le code 65")
        self.assertEqual(t("stop_vanished"), "train_auto : arrêt disparu sans « reprendre » : recréé")
        self.assertEqual(t("discarded", branch="feat/x", label="hors fenêtre"), "train_auto : écartée : feat/x : hors fenêtre")

    def test_phrases_cles_de_la_liste(self):
        t = messages.Messages(train_ready_messages.CATALOGS, "fr")
        self.assertEqual(t("added", branch="feat/x", tip="0123456789ab", review="faite"), "train_ready : inscrite : feat/x (sommet 0123456789ab, revue faite)")
        self.assertEqual(t("refused", branch="feat/x", label="revue"), "train_ready : refusée : feat/x : revue")
        self.assertEqual(t("dropped", branch="feat/x"), "train_ready : retirée : feat/x")
        self.assertEqual(t("absent", branch="feat/x"), "train_ready : absente de la liste : feat/x")
        self.assertEqual(t("pruned", n=2), "train_ready : 2 ligne(s) retirée(s) (fusionnées ou disparues)")
        self.assertEqual(t("unreadable", n=3), "train_ready : liste illisible : ligne 3")

    def test_toute_ligne_commence_par_le_nom_de_l_outil(self):
        for langue in ("fr", "en"):
            for cle, texte in train_auto_messages.CATALOGS[langue].items():
                if not cle.startswith(("reason:", "decision:")) and cle not in ("masked_branch", "stop_active", "stop_absent"):
                    self.assertTrue(texte.startswith("train_auto"), f"{langue} {cle}")
            for cle, texte in train_ready_messages.CATALOGS[langue].items():
                if cle not in ("review_given", "review_not_required", "cap"):
                    self.assertTrue(texte.startswith("train_ready"), f"{langue} {cle}")


if __name__ == "__main__":
    unittest.main()
