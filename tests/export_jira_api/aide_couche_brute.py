"""Faux magasin de la couche brute pour les tests de l'export (change jira-data-architecture, D4) : tout en mémoire, aucune base.

Il suit le protocole de flow_raw.MagasinBase (`enregistrer`, `fermer`) et la même règle de choix des instantanés
(flow_raw.choisir). Il garde ce qu'une transaction validée aurait écrit ; une erreur injectée (`echec_ecriture`, `echec_validation`)
ne laisse rien. Aucune donnée réelle.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flow_raw  # noqa: E402


class MagasinMemoire:
    def __init__(self):
        self.passages: list[dict] = []          # {"genre", "nb_requetes", "toutes"}
        self.visites: list[tuple[int, str]] = []   # (numéro de passage, clé)
        self.instantanes: list[dict] = []       # chaque instantané porte "passage"
        self.echec_ecriture: Exception | None = None      # levée pendant l'écriture, avant la validation
        self.echec_validation: Exception | None = None    # levée à la validation
        self.ferme = False
        self.types: dict[str, str | None] = {}          # flow.teams en mémoire : nom d'équipe -> type (None : type nul)
        self.sans_type = 0                              # équipes rencontrées au type nul, après le dernier enregistrement
        self.ecritures_de_type: list[str] = []          # noms d'équipe dont la colonne a été écrite (créée ou mise à jour)

    def derniers(self) -> dict:
        derniers: dict = {}
        for instantane in self.instantanes:          # un passage plus récent écrase le précédent
            derniers[instantane["issue_key"]] = (instantane["updated_at"], instantane["content_hash"])
        return derniers

    def enregistrer(self, *, genre, nb_requetes, toutes, vus, instantanes, types_equipes=None):
        a_ajouter = flow_raw.choisir(instantanes, self.derniers())
        if self.echec_ecriture is not None:
            raise self.echec_ecriture
        if self.echec_validation is not None:
            raise self.echec_validation
        numero = len(self.passages) + 1
        self.passages.append({"genre": genre, "nb_requetes": nb_requetes, "toutes": toutes})
        self.visites += [(numero, cle) for cle in vus]
        self.instantanes += [{**i, "passage": numero} for i in a_ajouter]
        if types_equipes is not None:          # même règle que flow_raw.MagasinBase._ecrire_types
            for nom, type_ in types_equipes.items():
                if nom not in self.types:
                    self.types[nom] = type_
                    self.ecritures_de_type.append(nom)
                elif type_ is not None and self.types[nom] != type_:
                    self.types[nom] = type_
                    self.ecritures_de_type.append(nom)
            self.sans_type = sum(1 for nom in types_equipes if self.types[nom] is None)
        return len(set(vus)), len(a_ajouter)

    def fermer(self):
        self.ferme = True

    def cles_vues(self, numero: int = 1) -> set[str]:
        return {cle for n, cle in self.visites if n == numero}

    def instantanes_de(self, cle: str) -> list[dict]:
        return [i for i in self.instantanes if i["issue_key"] == cle]

    def dernier(self, cle: str) -> dict:
        """Le dernier instantané écrit pour la clé (les attributs autorisés du ticket)."""
        return self.instantanes_de(cle)[-1]
