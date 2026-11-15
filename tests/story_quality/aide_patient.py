"""
Aide des tests de `patient-scan`, `patient-lift`, de la porte de suspension et du contrôle avant envoi (change patient-data-detection,
tâches 3.6, 4.4 et 5.1). Elle prolonge le montage de l'analyse (faux moteur, fausse clé, faux magasin, réglages et socle fictifs) : le même
faux magasin sert au scan, à la levée et à la porte, pour que l'état d'une sous-commande soit lu par l'autre.

Tout texte est inventé et construit ici : noms-sentinelles, numéros construits avec la structure et une clé valide, étiquette facultative
inventée. Aucun texte réel, aucune valeur lue dans une base.
"""
from __future__ import annotations

import json
import socket
from unittest import mock

from aide_analyse import BLOC, SERVICE_CLE, EspaceAnalyse
from aide_story_quality import EQUIPE_A, EQUIPE_B
import patient_data as pd                                                  # noqa: E402
import story_quality_review as review                                      # noqa: E402
import story_quality_store as store                                        # noqa: E402

NOM = "Zzpatientnom"                  # nom-sentinelle inventé (P5 : civilité ou « patient » devant)
ETIQUETTE = "zzdossierlocal"          # étiquette facultative inventée (P2)
NUMERO_DOSSIER = "Record number 556677"
NUMERO_LOCAL = f"{ETIQUETTE} 99887766"
TEXTE_P5 = f"Patient {NOM} admis"
TEXTE_PROPRE = "Afficher le diagnosis et la liste des allergies dans l'écran"
SENTINELLES = (NOM, ETIQUETTE, "556677", "99887766", "ZZA-", EQUIPE_A, EQUIPE_B)


class EspacePatient(EspaceAnalyse):
    """Prolonge le montage de l'analyse : `store.ouvrir` (scan et levée) rend le faux magasin, le terminal et la réponse de la levée sont
    ceux du test. `self.ouvertures_patient` compte les ouvertures du magasin par `patient-scan` et `patient-lift`."""

    def setUp(self):
        super().setUp()
        self.ouvertures_patient = 0
        self.injoignable = False               # vrai : l'ouverture du magasin de `patient-scan` et `patient-lift` échoue (base injoignable)
        self.service_demande = None            # le service du Trousseau demandé : None tant que la clé n'a pas été lue

    def etiquettes(self, *libelles):
        """Écrit la liste facultative `patient_id_labels` dans les réglages."""
        bloc = BLOC.format(service=SERVICE_CLE, plafond=self.PLAFOND) + f"patient_id_labels: {json.dumps(list(libelles))}\n"
        self.ecrire_reglages(bloc=bloc)

    def lancer(self, *argv, environ=None, reponse: str | None = "confirmer", terminal: bool = True, **autres):
        if reponse == "confirmer":
            reponse = "yes" if "--language" in argv and argv[argv.index("--language") + 1:][:1] == ("en",) else "oui"
        self.invites_levee: list[str] = []

        def ouvrir():
            if self.injoignable:
                raise store.ErreurMagasin()
            self.ouvertures_patient += 1
            return self.analyse

        def demander(question):
            self.invites_levee.append(question)
            if reponse is None:
                raise EOFError
            return reponse

        with mock.patch.object(store, "ouvrir", ouvrir), mock.patch.object(review, "demander", demander), \
                mock.patch.object(review, "est_terminal", lambda: terminal):
            return super().lancer(*argv, environ=environ, reponse=reponse, terminal=terminal, **autres)

    def lancer_sans_reseau(self, *argv, **options):
        """Lance avec la couche des sockets remplacée par une couche qui échoue : un accès réseau ferait échouer le lancement."""
        def refus(*a, **k):
            raise OSError("réseau interdit dans ce test")
        with mock.patch.object(socket, "socket", refus), mock.patch.object(socket, "create_connection", refus), \
                mock.patch.object(socket, "getaddrinfo", refus):
            return self.lancer(*argv, **options)

    def lever(self, *acceptees, version=None, empreinte=None):
        """Une levée enregistrée à la main (version du détecteur et empreinte de la liste donnés, ceux du jour par défaut)."""
        self.analyse.levees.clear()
        self.analyse.enregistrer_levee(pd.DETECTOR_VERSION if version is None else version, empreinte, 0, list(acceptees))

    def trouver(self, *codes):
        """Un passage enregistré à la main qui a trouvé ces catégories."""
        self.analyse.enregistrer_detection(pd.DETECTOR_VERSION, None, {"story": 1}, {c: c in codes for c in pd.CATEGORIES})

    def sans_levee(self):
        self.analyse.levees.clear()

    def propre(self, n, debut=1, genre="story", equipes=(EQUIPE_A,)):
        for i in range(debut, debut + n):
            self.analyse.ajouter(f"ZZA-{i:03d}", equipes, genre, titre=f"Titre propre {i}", description=TEXTE_PROPRE, criteres="")

    def avec(self, n, description="", titre=None, criteres="", debut=100, genre="story", equipes=(EQUIPE_A,)):
        """`n` éléments dont les textes sont ceux donnés (titre : un titre propre par défaut)."""
        for i in range(debut, debut + n):
            self.analyse.ajouter(f"ZZA-{i:03d}", equipes, genre, titre=titre if titre is not None else f"Titre propre {i}",
                                 description=description, criteres=criteres)

    def document(self, *argv, **options):
        code, sortie, erreur = self.lancer("patient-scan", "--json", *argv, **options)
        return code, json.loads(sortie), erreur

    @staticmethod
    def cellule(doc, code, genre):
        categorie = next(c for c in doc["categories"] if c["code"] == code)
        return next(c for c in categorie["by_kind"] if c["kind"] == genre)
