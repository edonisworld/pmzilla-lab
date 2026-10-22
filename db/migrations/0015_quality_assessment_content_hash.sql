-- Schéma touché : quality (colonne quality.assessments.content_hash).
-- Change story-quality-audit, design D7 (« whose text … changed ») : un verdict d'audit garde l'empreinte du texte nettoyé réellement
-- envoyé au moteur (quality.contents.content_hash lu avec ce texte). `analyse` resélectionne un élément quand l'empreinte de son texte
-- actuel diffère de celle de son dernier verdict d'audit à la paire courante ; une mise à jour Jira sans changement de texte (un statut,
-- par exemple) ne le renvoie plus au moteur. NULL : verdict antérieur à cette colonne, l'élément est à réauditer.
--
-- L'empreinte est un condensé du texte, jamais un extrait : aucune colonne de texte libre n'est ajoutée. Aucune vue ne lit la colonne
-- (les trois vues agrégées sont inchangées). Aucune donnée, aucun rôle créé ni modifié, aucun mot de passe : les droits existants des
-- rôles du schéma sur la table valent pour la nouvelle colonne.

SET LOCAL ROLE pmzilla_owner;

ALTER TABLE quality.assessments ADD COLUMN content_hash text;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
