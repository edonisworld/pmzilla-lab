-- Schéma touché : flow (tables des champs de livraison). Aucune donnée, aucun mot de passe, aucun rôle créé ni modifié.
-- Change jira-delivery-fields, correction R-20261102-51 (identifiant d'option seulement) et R-20261102-50 (présence seulement).
-- La migration 0032 n'a pas été appliquée sur la vraie base avec des données : les tables sont vides, les colonnes de valeur sont supprimées.
--
--   flow.issue_delivery_fields   release_target, verification_required, product_safety, isp, code_review_status deviennent
--                                *_id : l'identifiant d'option seul (jamais le libellé). Les colonnes sont renommées ; la vue de la
--                                migration 0033 les suit (elle ne teste que leur présence).
--   flow.issue_delivery_options  la colonne value est supprimée ; option_id devient obligatoire.
--   flow.issue_defect_fields     detected_by et installed_base (valeurs) sont supprimées ; detection_phase ne porte plus qu'un code
--                                fermé (production, piloting, other), jamais un libellé libre.
--
-- Remplace : les colonnes de valeur de 0032. Retrait : permanent (la valeur d'option n'est plus jamais stockée pour ces champs).

SET LOCAL ROLE pmzilla_owner;

ALTER TABLE flow.issue_delivery_fields RENAME COLUMN release_target TO release_target_id;
ALTER TABLE flow.issue_delivery_fields RENAME COLUMN verification_required TO verification_required_id;
ALTER TABLE flow.issue_delivery_fields RENAME COLUMN product_safety TO product_safety_id;
ALTER TABLE flow.issue_delivery_fields RENAME COLUMN isp TO isp_id;
ALTER TABLE flow.issue_delivery_fields RENAME COLUMN code_review_status TO code_review_status_id;

DELETE FROM flow.issue_delivery_options;
ALTER TABLE flow.issue_delivery_options DROP COLUMN value;
ALTER TABLE flow.issue_delivery_options ALTER COLUMN option_id SET NOT NULL;

UPDATE flow.issue_defect_fields SET detection_phase = CASE detection_phase WHEN 'Production' THEN 'production'
                                                                        WHEN 'Piloting' THEN 'piloting' ELSE 'other' END
    WHERE detection_phase IS NOT NULL AND detection_phase NOT IN ('production', 'piloting');
ALTER TABLE flow.issue_defect_fields DROP COLUMN detected_by;
ALTER TABLE flow.issue_defect_fields DROP COLUMN installed_base;
ALTER TABLE flow.issue_defect_fields ADD CONSTRAINT issue_defect_fields_phase_code
    CHECK (detection_phase IS NULL OR detection_phase IN ('production', 'piloting', 'other'));

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
