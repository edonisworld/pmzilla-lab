-- Schéma touché : mothra (ajout de trois colonnes à mothra.sheets, aucune donnée, aucun droit modifié).
-- Tâche 18.1 du change mothra-slices (design D20, D29 ; décision de l'auteur du 2026-10-29) : une fiche en brouillon se souvient de ce dont elle
-- est faite, pour que le corps (verdict, explications, signal) soit recalculé à la lecture et gelé à la publication :
--   scope               la portée, un code (un code d'équipe ou product_level), jamais un texte libre ;
--   data_date           la date des données lues ;
--   management_question la question de direction à laquelle la fiche répond, choisie à la création, dans la liste fermée des quatre
--                       questions de direction (design D19) ; vide tant qu'elle n'est pas choisie : la relecture la demande.
-- Le graphique d'origine reste dans `kind`. Les trois colonnes sont facultatives pour la base (les lignes écrites avant elles n'en ont pas) ;
-- le dépôt de fiches du serveur les écrit toujours. Colonnes sans nom, sans clé de ticket, sans titre, sans description.
-- Droits : inchangés (migration 0024). Le rôle du stockage lit, insère et met à jour `sheets`, ne supprime rien ; le gel d'une version
-- publiée reste dans published_versions (insertion seulement).

SET LOCAL ROLE pmzilla_owner;

ALTER TABLE mothra.sheets
    ADD COLUMN scope               text CHECK (scope IS NULL OR scope ~ '^[a-z0-9_.-]{1,64}$'),
    ADD COLUMN data_date           date,
    ADD COLUMN management_question text CHECK (management_question IS NULL OR management_question IN
        ('scope_growth', 'scope_reachability', 'predictability', 'next_version_quality')),
    ADD CONSTRAINT sheets_scope_and_data_date_together CHECK ((scope IS NULL) = (data_date IS NULL));

RESET ROLE;
