"""Contrôle interpreteur_crochets (R-20261108-10) : l'interpréteur absolu des crochets Git existe, appartient à root et n'est inscriptible que par
root (le lien, sa cible résolue et les dossiers jusqu'à /Library/Developer/CommandLineTools inclus). Tout se joue sur des métadonnées factices
injectées (fonctions lstat, stat et de résolution) ; aucun fichier réel n'est lu. Le doctor n'écrit rien."""
import errno
import stat
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import TOOLS  # noqa: E402,F401  (met tools/ dans sys.path)

import doctor  # noqa: E402
from doctor_messages import CATALOGS  # noqa: E402
from messages import Messages  # noqa: E402

RACINE_CLT = "/Library/Developer/CommandLineTools"
LIEN = RACINE_CLT + "/usr/bin/python3"
CIBLE = RACINE_CLT + "/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3"
DOSSIER, FICHIER, SYMLINK = stat.S_IFDIR | 0o755, stat.S_IFREG | 0o755, stat.S_IFLNK | 0o755


def metadonnees():
    """Un système de fichiers factice conforme : tout à root, 755, le lien pointant sur la cible."""
    m = {LIEN: SimpleNamespace(st_uid=0, st_mode=SYMLINK), CIBLE: SimpleNamespace(st_uid=0, st_mode=FICHIER)}
    for chemin in (LIEN, CIBLE):
        for parent in Path(chemin).parents:
            if str(parent) == RACINE_CLT or RACINE_CLT in map(str, parent.parents):
                m[str(parent)] = SimpleNamespace(st_uid=0, st_mode=DOSSIER)
    return m


class ControleInterpreteurCrochets(unittest.TestCase):
    def verifier(self, m, plateforme="darwin", cible=CIBLE):
        def lire(chemin):
            try:
                return m[str(chemin)]
            except KeyError:
                raise FileNotFoundError(str(chemin))
        return doctor.verifier_interpreteur(LIEN, lstat=lire, stat_=lire, resoudre=lambda _: cible, plateforme=plateforme)

    def verifier_separe(self, m_lstat, m_stat):
        """lstat et stat lisent deux systèmes de fichiers factices distincts : le code ne doit lire le lien que par lstat et la cible que par stat."""
        def lecteur(m):
            def lire(chemin):
                try:
                    return m[str(chemin)]
                except KeyError:
                    raise FileNotFoundError(str(chemin))
            return lire
        return doctor.verifier_interpreteur(LIEN, lstat=lecteur(m_lstat), stat_=lecteur(m_stat), resoudre=lambda _: CIBLE, plateforme="darwin")

    @staticmethod
    def separer():
        """Deux tables : lstat ne connaît que le lien et ses dossiers, stat que la cible et ses dossiers."""
        m = metadonnees()
        m_lstat = {c: i for c, i in m.items() if c == LIEN or c in map(str, Path(LIEN).parents)}
        m_stat = {c: i for c, i in m.items() if c == CIBLE or c in map(str, Path(CIBLE).parents)}
        return m_lstat, m_stat

    def test_lstat_pour_le_lien_et_stat_pour_la_cible(self):
        m_lstat, m_stat = self.separer()
        self.assertEqual(self.verifier_separe(m_lstat, m_stat), "ok")
        # lien conforme en lstat, cible non conforme en stat
        m_lstat, m_stat = self.separer()
        m_stat[CIBLE] = SimpleNamespace(st_uid=501, st_mode=FICHIER)
        self.assertEqual(self.verifier_separe(m_lstat, m_stat), "owner")
        # lien non conforme en lstat, cible conforme en stat
        m_lstat, m_stat = self.separer()
        m_lstat[LIEN] = SimpleNamespace(st_uid=0, st_mode=SYMLINK | stat.S_IWOTH)
        self.assertEqual(self.verifier_separe(m_lstat, m_stat), "writable")

    def test_stat_de_la_cible_en_boucle_alerte(self):
        m = metadonnees()

        def lire(chemin):
            return m[str(chemin)]

        def boucle(chemin):
            raise OSError(errno.ELOOP, "Too many levels of symbolic links")
        self.assertEqual(doctor.verifier_interpreteur(LIEN, lstat=lire, stat_=boucle, resoudre=lambda _: CIBLE, plateforme="darwin"), "missing")

    def test_cible_hors_de_la_racine_alerte(self):
        for cible in ("/usr/bin/python3", "/Library/Developer/CommandLineToolsX/usr/bin/python3", RACINE_CLT):
            with self.subTest(cible=cible):
                m = metadonnees()
                m[cible] = SimpleNamespace(st_uid=0, st_mode=FICHIER)
                self.assertEqual(self.verifier(m, cible=cible), "outside")

    def test_present_et_conforme_ok(self):
        self.assertEqual(self.verifier(metadonnees()), "ok")

    def test_lien_absent_alerte(self):
        m = metadonnees()
        del m[LIEN]
        self.assertEqual(self.verifier(m), "missing")

    def test_cible_absente_alerte(self):
        m = metadonnees()
        del m[CIBLE]
        self.assertEqual(self.verifier(m), "missing")

    def test_proprietaire_non_root_alerte(self):
        for chemin in (LIEN, CIBLE, RACINE_CLT, RACINE_CLT + "/usr/bin"):
            with self.subTest(chemin=chemin):
                m = metadonnees()
                m[chemin].st_uid = 501
                self.assertEqual(self.verifier(m), "owner")

    def test_inscriptible_par_le_groupe_ou_les_autres_alerte(self):
        for droit in (stat.S_IWGRP, stat.S_IWOTH):
            for chemin in (LIEN, CIBLE, RACINE_CLT, RACINE_CLT + "/usr"):
                with self.subTest(chemin=chemin, droit=droit):
                    m = metadonnees()
                    m[chemin].st_mode |= droit
                    self.assertEqual(self.verifier(m), "writable")

    def test_lien_vers_une_cible_non_conforme_alerte(self):
        m = metadonnees()
        m[CIBLE].st_mode |= stat.S_IWOTH
        self.assertEqual(self.verifier(m), "writable")
        m = metadonnees()
        m[CIBLE].st_uid = 501
        self.assertEqual(self.verifier(m), "owner")

    def test_dossier_au_dessus_de_la_racine_n_est_pas_controle(self):
        m = metadonnees()
        m["/Library"] = SimpleNamespace(st_uid=501, st_mode=DOSSIER | stat.S_IWGRP)
        self.assertEqual(self.verifier(m), "ok")

    def test_hors_du_mac_sans_objet(self):
        self.assertEqual(self.verifier({}, plateforme="linux"), "not_mac")

    def test_niveaux_du_controle(self):
        attendus = {"ok": "ok", "missing": "problem", "owner": "problem", "writable": "problem", "outside": "problem",
                    "not_mac": "skipped"}
        for cle, niveau in attendus.items():
            with self.subTest(cle=cle), mock.patch.object(doctor, "verifier_interpreteur", return_value=cle):
                r = doctor.controle_interpreteur_crochets(None, [])
                self.assertEqual((r.id, r.niveau, r.cle), ("interpreteur-crochets", niveau, cle))

    def test_lignes_fr_et_en_et_ordre(self):
        self.assertIn("interpreteur-crochets", doctor.ORDRE)
        self.assertIn(doctor.controle_interpreteur_crochets, doctor.CONTROLES)
        cles = {cle for controle, cle in doctor.TOUTES_LES_RAISONS if controle == "interpreteur-crochets"}
        self.assertEqual(cles, {"ok", "missing", "owner", "writable", "not_mac", "outside"})
        for langue, fragment in (("fr", "les crochets risquent de ne plus démarrer"), ("en", "the hooks may no longer start")):
            t = Messages(CATALOGS, langue)
            for cle in ("missing", "owner", "writable", "outside"):
                texte = doctor.raison(doctor.Resultat("interpreteur-crochets", "problem", cle), t)
                self.assertIn(fragment, texte)
                self.assertNotIn("/Library", texte)
                self.assertNotIn("tests/", texte)


if __name__ == "__main__":
    unittest.main()
