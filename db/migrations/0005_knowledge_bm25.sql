-- Schéma touché : knowledge (knowledge.chunks : colonne fts_text, index BM25 chunks_bm25) ; schémas pdb et paradedb (droit d'usage, extension pg_search).
-- Lot 4 : plein texte BM25 par pg_search (ParadeDB 0.26), à la place du classement ts_rank_cd de la 0004, qui ignore l'IDF : un OU de mots courants
-- classait les passages d'après leurs mots vides (parité plein texte mesurée à 0,09 sur les vraies données). La colonne search_vector (tsvector)
-- et son index GIN restent : la voie `--fulltext tsvector` sert à comparer.
--
-- Équivalence avec FTS5 (pmzilla_lab_library.py : `tokenize='unicode61 remove_diacritics 2'`, colonnes `text` et `section`) :
--   FTS5 unicode61  coupe aux caractères qui ne sont ni lettres ni chiffres (l'apostrophe et le tiret bas séparent), met en minuscules,
--                   ôte les accents (remove_diacritics 2), ne racinise pas, n'ôte aucun mot vide ;
--   pdb.simple      coupe aux caractères non alphanumériques, met en minuscules (filtre par défaut), ne racinise pas (aucun filtre `stemmer`),
--                   aucun mot vide ; le filtre ascii_folding=true ôte les accents des lettres latines (café, équipe -> cafe, equipe).
--   Écart assumé     pour les alphabets non latins, ascii_folding ne fait rien alors que unicode61 replie aussi d'autres diacritiques : sans
--                   effet sur des livres en français et en anglais.
-- Les deux colonnes de FTS5 (section puis texte) comptent pour une seule longueur de document dans bm25() : la colonne générée fts_text les
-- concatène (comme search_vector), ce qui donne la même normalisation de longueur. Paramètres BM25 par défaut des deux côtés (k1 = 1,2 ; b = 0,75).
-- La formule d'IDF diffère légèrement (FTS5 : ln((N - n + 0,5) / (n + 0,5)) borné ; Tantivy : ln(1 + (N - n + 0,5) / (n + 0,5))) : mêmes classements,
-- scores un peu différents.
--
-- pg_search 0.26 : syntaxe `USING bm25 (id, (colonne::pdb.simple('ascii_folding=true')))` ; `key_field` est encore accepté (ignoré).

DO $$
DECLARE
    nom_schema text;
    role_nom text;
BEGIN
    FOREACH nom_schema IN ARRAY ARRAY['pdb', 'paradedb'] LOOP
        IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = nom_schema) THEN
            FOREACH role_nom IN ARRAY ARRAY['pmzilla_owner', 'pmzilla_knowledge', 'pmzilla_knowledge_ro', 'pmzilla_cases', 'pmzilla_cases_ro',
                                            'pmzilla_flow', 'pmzilla_flow_ro'] LOOP
                EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I', nom_schema, role_nom);
            END LOOP;
        END IF;
    END LOOP;
END
$$;

SET LOCAL ROLE pmzilla_owner;

-- Filet de sécurité : la construction parallèle de l'index BM25 demande un segment de mémoire partagée proportionnel à la bibliothèque (366 Mio sur
-- la première tentative, qui a échoué avec le /dev/shm de 64 Mo du conteneur). docker-compose.yml pose shm_size: 1gb ; sans travailleur parallèle,
-- la migration passe aussi avec un petit /dev/shm. Seule cette transaction est concernée (SET LOCAL) ; la construction est un peu plus longue.
SET LOCAL max_parallel_maintenance_workers = 0;

ALTER TABLE knowledge.chunks ADD COLUMN fts_text text GENERATED ALWAYS AS (section || ' ' || text) STORED;

CREATE INDEX chunks_bm25 ON knowledge.chunks
    USING bm25 (id, (fts_text::pdb.simple('ascii_folding=true')))
    WITH (key_field = 'id');

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
