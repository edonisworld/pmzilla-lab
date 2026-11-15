"""Jeu synthétique déterministe du schéma flow pour Mothra (#240, conception D13) et son chargeur.

    uv run --with "psycopg[binary]" python tests/mothra_donnees/jeu_synthetique.py

Tranche 0 : de quoi peupler la vue « statut par équipe » (flow.v_team_status) avec ses valeurs témoins, rien de plus.
  - équipes : désignations génériques (« équipe A »...), jamais un nom réel ; un groupe de tickets sans équipe ;
  - clés : inventées (SYN-<n>), dans les tables seulement, jamais dans une vue ;
  - dates des tickets ouverts : relatives à l'instant du chargement, pour que les âges soient peuplés quel que soit le jour ;
  - dates des tickets « Done » : relatives à une ancre de trimestre (`ancre`, lundi 00:00 UTC de la semaine qui contient le début du
    dernier trimestre terminé + 21 jours), avec l'espacement par rang d'avant (R-20261105-16 et -17) : leurs semaines et leurs trimestres
    ne dépendent plus de l'heure ni du jour du chargement, donc la règle T3 (b) de db/migrations/0030_flow_t3_withheld.sql ne retire
    jamais le trimestre de l'équipe C, la première du tableau lead time de l'e2e, et les semaines témoins de 1 à 2 Story restent ;
  - comptes témoins : des cellules de 1 à 4 tickets (la vue les masque), des cellules d'exactement 5 (la vue les rend), des cellules
    plus grandes ;
  - chaînes sentinelles : dans des colonnes qu'aucune vue n'expose (projet, résolution, ticket parent) ; elles ne doivent jamais
    atteindre une réponse de l'API, un journal ni le bundle.

Le chargeur refuse sans base jetable : sans DBTEST_PORT (posé par tools/dbtest.sh seul), ou si la garde des tests avec base ne
reconnaît pas la base jetable, il sort avec le code 2 et « jeu synthétique : base jetable absente », sans ouvrir de connexion. Il
écrit sous le rôle d'import (pmzilla_flow, SET LOCAL dans une seule transaction, rôle vérifié avant d'écrire ; une connexion en
autocommit est refusée), puis valide. Deux transactions suivent, chacune sur la même connexion : le marqueur (sous pmzilla_owner) puis les deux
utilisateurs synthétiques de mothra.users (sous pmzilla_mothra, le rôle d'import n'ayant aucun droit sur le schéma mothra). Avant d'écrire, il refuse (même sortie 2, même phrase) une base qui contient une clé hors SYN-% ou
un nom d'équipe hors des désignations génériques du jeu : une copie de données réelles. Il ne lit aucun fichier : les données sont
toutes écrites ici.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MESSAGE_REFUS = "jeu synthétique : base jetable absente"
ROLE_IMPORT = "pmzilla_flow"
INSTANT_FIXE = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)   # pour les tests : un chargement sans horloge

PREFIXE_CLE = "SYN-"
TYPE_DEFAUT = "Bug"                  # le type de défaut du jeu ; `main` le passe au référentiel synthétique avec les statuts de GROUPES (D8, R-20261029-15)
EQUIPES_GENERIQUES = frozenset({"équipe A", "équipe B", "équipe C", "équipe D"})   # l'ensemble des équipes de GROUPES
SENTINELLES = ("SENTINELLE-PROJET", "SENTINELLE-RESOLUTION", "SENTINELLE-PARENT")

# (équipe ou None, type, catégorie, statut, nombre de tickets). Catégorie et statut portent le même libellé : le jeu n'en a pas besoin de plus.
GROUPES = (
    ("équipe A", "Story", "In Progress", "In Progress", 12),
    ("équipe A", "Story", "Done", "Done", 5),
    ("équipe A", "Story", "To Do", "To Do", 1),
    ("équipe B", "Story", "Done", "Done", 5),
    ("équipe B", "Bug", "In Progress", "In Progress", 2),
    ("équipe B", "Story", "To Do", "To Do", 3),
    ("équipe C", "Story", "In Progress", "In Progress", 4),
    ("équipe C", "Bug", "To Do", "To Do", 1),
    ("équipe C", "Story", "Done", "Done", 9),
    ("équipe D", "Epic", "To Do", "To Do", 4),
    ("équipe D", "Story", "Done", "Done", 5),
    (None, "Story", "To Do", "To Do", 6),
    (None, "Bug", "Done", "Done", 2),
)


DECALAGE_ANCRE = timedelta(days=100)   # réglé une fois (R-20261105-16) : équipes C et A publiées sous T3 (b), semaines témoins gardées


def ancre(maintenant: datetime) -> datetime:
    """Lundi 00:00 UTC de la semaine qui contient (début du dernier trimestre terminé + 21 jours), le trimestre étant celui de `maintenant` en UTC."""
    jour = maintenant.astimezone(timezone.utc).date()
    mois = jour.year * 12 + 3 * ((jour.month - 1) // 3) - 3          # début du dernier trimestre terminé, en mois depuis l'an 0
    repere = datetime(mois // 12, mois % 12 + 1, 1, tzinfo=timezone.utc) + timedelta(days=21)
    return repere - timedelta(days=repere.weekday())


def construire(maintenant: datetime) -> list[dict]:
    """Les tickets du jeu, dans un ordre fixe ; chaque date se déduit du rang du ticket (aucun hasard) et de `maintenant` pour un ticket
    ouvert, de `ancre(maintenant)` pour un ticket « Done » (même écart au repère que l'ancien calcul, compté depuis ancre + 100 jours)."""
    tickets: list[dict] = []
    repere_done = ancre(maintenant) + DECALAGE_ANCRE
    rang = 0
    for equipe, type_, categorie, statut, nombre in GROUPES:
        for _ in range(nombre):
            rang += 1
            ecart = timedelta(days=3 + (rang * 7) % 180, hours=rang % 24)
            duree = timedelta(days=2 + rang % 9)
            if categorie == "Done":
                # jamais dans le futur : bornée à une heure avant l'instant du chargement ; la création suit, donc jamais après la résolution
                resolu = min(repere_done - ecart + duree, maintenant - timedelta(hours=1))
                cree = resolu - duree
            else:
                resolu = None
                cree = maintenant - ecart
            tickets.append({
                "cle": f"{PREFIXE_CLE}{rang}",
                "projet": SENTINELLES[0],
                "type": type_,
                "statut": statut,
                "categorie": categorie,
                "cree": cree,
                "resolu": resolu,
                "resolution": SENTINELLES[1] if resolu else None,
                "debut": resolu or cree + timedelta(days=1),
                "points": 1 + rang % 5,
                "maj": resolu or cree + timedelta(days=1),
                "equipe": equipe,
                "parent": SENTINELLES[2] if rang % 3 == 0 else None,
            })
    return tickets


class RefusJeu(Exception):
    """Le chargement n'a pas lieu : le message est dit sur la sortie d'erreur, le code de sortie est 2, rien n'a été écrit."""


def charger(conn, maintenant: datetime, supplement=None, types_liens=None) -> int:
    """Écrit le jeu sous le rôle d'import, remplace un chargement précédent et valide. Rend le nombre de tickets.

    `supplement` : `(tickets, équipes)` d'un jeu qui s'ajoute à la tranche 0 (le jeu de la tranche 1, tâche 14.2) ; ses équipes entrent dans l'ensemble
    contrôlé, et une équipe de ses tickets hors de cet ensemble refuse le chargement en nommant son code, avant toute écriture. Les clés `transitions`
    (instant, statut de départ, statut d'arrivée) et `liens` (cible, genre) d'un ticket sont écrites quand il les porte ; `types_liens` donne, pour un
    genre de lien du jeu, le type de lien à écrire (le genre « blocks » prend le type déclaré par le référentiel synthétique) ; un lien sans entrée
    garde son genre pour type.

    Tout se passe dans une seule transaction (la connexion ne doit pas être en autocommit) : le rôle est pris par SET LOCAL, donc rendu
    à la validation comme à l'annulation, et vérifié (current_user) avant toute écriture. Avant d'écrire, la base est contrôlée : une clé
    hors SYN-% ou un nom d'équipe hors de l'ensemble générique du jeu y trahit une copie de données réelles, et le chargement est refusé.
    """
    if getattr(conn, "autocommit", False):
        raise RefusJeu("jeu synthétique : connexion en autocommit refusée")
    info = getattr(conn, "info", None)
    if info is not None and int(info.transaction_status) != 0:   # 0 : au repos ; sinon la transaction du chargeur ne serait qu'un point de reprise
        raise RefusJeu("jeu synthétique : connexion déjà dans une transaction")
    tickets = construire(maintenant)
    controlees = EQUIPES_GENERIQUES
    if supplement is not None:
        tickets = tickets + list(supplement[0])
        controlees = EQUIPES_GENERIQUES | frozenset(supplement[1])
    for t in tickets:
        for nom in [t["equipe"], *t.get("equipes", [])]:
            if nom and nom not in controlees:
                raise RefusJeu(f"jeu synthétique : équipe hors de l'ensemble contrôlé : {nom}")
    with conn.transaction():
        conn.execute(f"SET LOCAL ROLE {ROLE_IMPORT}")
        if conn.execute("SELECT current_user").fetchone()[0] != ROLE_IMPORT:
            raise RefusJeu(f"jeu synthétique : le rôle {ROLE_IMPORT} n'est pas pris")
        cles_reelles = conn.execute("SELECT count(*) FROM flow.issues WHERE key NOT LIKE %s", (PREFIXE_CLE + "%",)).fetchone()[0]
        noms = [ligne[0] for ligne in conn.execute("SELECT name FROM flow.teams").fetchall()]
        if cles_reelles or any(nom not in controlees for nom in noms):
            raise RefusJeu(MESSAGE_REFUS)
        conn.execute("DELETE FROM flow.issues WHERE key LIKE %s", (PREFIXE_CLE + "%",))
        ids: dict[str, int] = {}
        for equipe in dict.fromkeys(t["equipe"] for t in tickets if t["equipe"]):
            ids[equipe] = conn.execute(
                "INSERT INTO flow.teams (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
                (equipe,)).fetchone()[0]
        for t in tickets:
            equipe_id = ids.get(t["equipe"]) if t["equipe"] else None
            conn.execute(
                "INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, resolution, "
                "status_category_changed_at, story_points, updated_at, team_id, parent_key) "
                "VALUES (" + ", ".join(["%s"] * 13) + ")",
                (t["cle"], t["projet"], t["type"], t["statut"], t["categorie"], t["cree"], t["resolu"], t["resolution"],
                 t["debut"], t["points"], t["maj"], equipe_id, t["parent"]))
            if equipe_id is not None:
                conn.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) VALUES (%s, %s, 1)", (t["cle"], equipe_id))
        for t in tickets:       # après tous les tickets : un lien part d'un ticket écrit, sa cible n'est pas une clé étrangère
            for instant, depart, arrivee in t.get("transitions", ()):
                conn.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, from_status, to_status) VALUES (%s, %s, %s, %s)",
                             (t["cle"], instant, depart, arrivee))
            for cible, genre in t.get("liens", ()):
                conn.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES (%s, %s, %s, 'outward')",
                             (t["cle"], cible, (types_liens or {}).get(genre, genre)))
    return len(tickets)


ROLE_PROPRIETAIRE = "pmzilla_owner"
ROLE_DES_VUES = "pmzilla_flow_views"


def poser_marqueur(conn) -> None:
    """Crée `flow.synthetic_dataset_marker()` dans la base jetable chargée (mothra-slices, tâche 16.2, design D17 et D34).

    La fonction n'a pas d'argument et rend l'entier 1, sur le modèle de flow.masking_version() ; EXECUTE est donné au seul rôle des vues
    de flow. Aucune migration ne la crée : la vraie base ne la détient jamais, et une base sans marqueur est réelle. Le rôle d'import n'a
    aucun DDL : le marqueur se crée sous le propriétaire (SET LOCAL, une seule transaction).
    """
    if getattr(conn, "autocommit", False):
        raise RefusJeu("jeu synthétique : connexion en autocommit refusée")
    info = getattr(conn, "info", None)
    if info is not None and int(info.transaction_status) != 0:
        raise RefusJeu("jeu synthétique : connexion déjà dans une transaction")
    with conn.transaction():
        conn.execute(f"SET LOCAL ROLE {ROLE_PROPRIETAIRE}")
        # SET LOCAL ROLE échoue de lui-même si le rôle ne peut pas être pris : aucune création n'a alors lieu.
        conn.execute("CREATE OR REPLACE FUNCTION flow.synthetic_dataset_marker() RETURNS integer LANGUAGE sql IMMUTABLE AS 'SELECT 1'")
        conn.execute("REVOKE ALL ON FUNCTION flow.synthetic_dataset_marker() FROM PUBLIC")
        conn.execute(f"GRANT EXECUTE ON FUNCTION flow.synthetic_dataset_marker() TO {ROLE_DES_VUES}")


ROLE_STOCKAGE = "pmzilla_mothra"
# Les deux utilisateurs synthétiques de l'e2e (mothra-slices, tâche 20.1, R-20261102-65 (1)) : identifiants pseudonymes de rôle (motif de
# mothra.users.id), jamais un nom de personne ; rôles permis par la contrainte de la table : author et reviewer.
UTILISATEURS_SYNTHETIQUES = (("author-synth", "author"), ("reviewer-synth", "reviewer"))


def poser_utilisateurs(conn) -> None:
    """Écrit les deux utilisateurs synthétiques dans mothra.users de la base jetable chargée (mothra-slices, tâche 20.1, R-20261102-65 (1)).

    Le rôle d'import (pmzilla_flow) n'a aucun droit sur le schéma mothra : l'écriture se fait sous le rôle de stockage de Mothra (SET LOCAL ROLE,
    une seule transaction), qui a INSERT sur mothra.users (migration 0024) et nul autre droit ici. Rejouable : un identifiant déjà présent est
    laissé tel quel. Remplace : rien. Retrait : permanent tant que l'e2e écrit des fiches (le serveur refuse un identifiant inconnu, 403 UNKNOWN_USER).
    """
    if getattr(conn, "autocommit", False):
        raise RefusJeu("jeu synthétique : connexion en autocommit refusée")
    info = getattr(conn, "info", None)
    if info is not None and int(info.transaction_status) != 0:
        raise RefusJeu("jeu synthétique : connexion déjà dans une transaction")
    with conn.transaction():
        conn.execute(f"SET LOCAL ROLE {ROLE_STOCKAGE}")
        for identifiant, role in UTILISATEURS_SYNTHETIQUES:
            conn.execute("INSERT INTO mothra.users (id, role) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING", (identifiant, role))


def main(argv: list[str] | None = None, env=None, connecter=None, fournir_supplement=None) -> int:
    """`fournir_supplement(maintenant)` rend `(tickets, équipes)` d'un jeu qui s'ajoute à la tranche 0 (tranche1.main le fournit) ; sans lui, tranche 0 seule."""
    env = os.environ if env is None else env
    if not env.get("DBTEST_PORT"):
        print(MESSAGE_REFUS, file=sys.stderr)
        return 2
    sys.path.insert(0, str(RACINE / "tests" / "db"))
    import garde_base_jetable as garde  # noqa: E402  (la garde des tests avec base : une seule règle, sans effet de bord)
    db = garde.db
    connecter = db.connect if connecter is None else connecter
    if not garde.base_jetable_disponible(env, connecter):
        print(MESSAGE_REFUS, file=sys.stderr)
        return 2
    port = env["DBTEST_PORT"]
    adresse = env.get(db.VARIABLE_URL) or f"postgresql://postgres@127.0.0.1:{port}/pmzilla"
    conn = connecter(adresse, password=env.get(db.VARIABLE_MOT_DE_PASSE))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import referentiel_synthetique as referentiel  # noqa: E402  (change cycle-referential-schema, D6 ; décision R-20261028-107)
    try:
        maintenant = datetime.now(timezone.utc)
        supplement = fournir_supplement(maintenant) if fournir_supplement is not None else None
        # le statut prêt et le type de lien bloquant sont ceux que déclare le référentiel synthétique (R-20261029-21), jamais recopiés ici
        nombre = charger(conn, maintenant, supplement, {"blocks": referentiel.TYPE_LIEN_BLOQUE})
        noms_du_jeu = {"statuts": {statut: categorie for _, _, categorie, statut, _ in GROUPES}, "type_defaut": TYPE_DEFAUT,
                       "statut_pret": referentiel.STATUT_PRET, "type_lien_bloquant": referentiel.TYPE_LIEN_BLOQUE}
        referentiel.charger(conn, maintenant.date(), noms_du_jeu=noms_du_jeu)      # après le jeu et ses contrôles, sous le rôle d'import, par flow_referential.ecrire
        poser_marqueur(conn)
        poser_utilisateurs(conn)
    except RefusJeu as refus:
        print(refus, file=sys.stderr)
        return 2
    finally:
        conn.close()
    print(f"jeu synthétique : {nombre} tickets chargés (base jetable, port {port})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
