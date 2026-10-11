# Pré-tri de la veille : correspondance des prompts français et anglais

Fichier de relecture du lot 5b. Le texte anglais est celui de `tools/watch_prompts_en.py`, le texte français celui de `tools/watch_triage.py` (`SYSTEM_PROMPT`, `USER_PROMPT`, `CRITERIA`, thèmes de `DEFAULT_CONFIG`). **Depuis le lot 5b, les prompts anglais sont ceux de l'édition publiée** : ils décident quand `language: en` dans `watch/tri.yaml` (décision du 10 octobre : le filtre de l'auteur garde `language: fr`). Le texte français est figé par un test d'empreinte et n'a pas changé. Deux ajustements volontaires du lot 5b, sur les items compilation et promotionnel, corrigent ce que la notation en ombre du 10 octobre a montré : l'anglais ne voyait pas le promotionnel des extraits et annonces de livres et des webinaires, et classait en compilation des articles argumentés. Ils sont acceptés seulement après la mesure de l'utilisateur (`shadow-backfill` puis `shadow-report`, critères dans le change `lot5b-watch-prompts-en`, design, section 2).

Volontairement identiques : les clés JSON `resume`, `pourquoi`, `compilation`, `dans_themes`, `promotionnel`, `these`, `etaye`, `original`, `sources`, `non_promo`, `ok` et `justification` sont des identifiants de code (schéma de sortie, lecture de la réponse), jamais traduits ; les marqueurs `{themes}`, `{title}`, `{source}`, `{text}`, `{criteria}` aussi.

Consigne de langue : les réponses du modèle (résumé, justifications) sont demandées en anglais. La phrase française « garde les termes anglais du métier tels quels » n'a plus d'objet et est retirée.

## SYSTEM_PROMPT

| Français | Anglais | Remarque |
|---|---|---|
| Tu évalues des articles pour la bibliothèque d'un Agile Lead qui accompagne une organisation dans sa transformation produit. | You evaluate articles for the library of an Agile Lead who supports an organisation in its product transformation. | Fidèle. « Tu » devient l'impératif implicite de l'anglais (« You »). |
| Ses thèmes : {themes}. | Their themes: {themes}. | « Their » (neutre) car la personne n'est pas nommée. |
| Évalue chaque critère séparément, à partir du texte seulement : un article peut en remplir certains et pas d'autres. | Evaluate each criterion separately, from the text only: an article can meet some of them and not others. | Fidèle. |
| Un critère n'est vrai que si l'article le remplit nettement. | A criterion is true only if the article clearly meets it. | Fidèle (« nettement » : « clearly »). |
| Écris en français, mais garde les termes anglais du métier tels quels (product manager, discovery, delivery, outcome, roadmap, build to learn…). | Write in English. | Ajustement volontaire : la réponse est en anglais, la réserve sur les termes anglais du métier est sans objet. |
| Réponds uniquement en JSON. | Reply only in JSON. | Fidèle. |

## USER_PROMPT

| Français | Anglais | Remarque |
|---|---|---|
| Titre : {title} | Title: {title} | Fidèle. |
| Source : {source} | Source: {source} | Fidèle. |
| Texte : {text} | Text: {text} | Fidèle (le texte suit sur la ligne suivante, comme en français). |
| Dans cet ordre : | In this order: | Fidèle. |
| 1. resume : deux phrases sur ce que dit l'article. | 1. resume: two sentences on what the article says. | Fidèle. |
| 2. pourquoi : une phrase sur ce que l'article apporte à ces thèmes (pas un jugement sur sa qualité), ou « hors sujet ». | 2. pourquoi: one sentence on what the article brings to these themes (not a judgement of its quality), or "off topic". | La valeur de repli « hors sujet » devient "off topic". Le code ne la teste pas : elle est stockée telle quelle dans `pourquoi`. |
| 3. compilation : « justification », puis « ok ». | 3. compilation: "justification", then "ok". | Fidèle ; guillemets droits dans le texte anglais. |
| Sois strict : true seulement si l'essentiel du texte est une liste de contenus d'AUTRES auteurs (articles, vidéos, livres), chacun présenté en quelques lignes, sans argumentation suivie de l'auteur : revue de liens, « what I've been reading », newsletter de liens, programme d'un événement. | Be strict: true only if most of the text is a list of content by OTHER authors (articles, videos, books), each presented in a few lines, without a sustained argument by the author: a link roundup, "what I've been reading", a link newsletter, an event programme. | « Sois strict » conservé. « revue de liens » : « link roundup ». L'exemple « what I've been reading » est déjà en anglais, gardé. Les majuscules d'AUTRES / OTHER sont conservées. |
| false dans tous les autres cas, en particulier : un essai qui cite plusieurs sources, un épisode de podcast ou un entretien, un guide de lecture écrit par l'auteur du livre, un article qui commente longuement une seule source. | false in all other cases, in particular: an essay that cites several sources, a podcast episode or an interview, a reading guide written by the author of the book, an article that comments at length on a single source. | Fidèle, mêmes quatre contre-exemples dans le même ordre. |
| (pas d'équivalent) | Also false: an article in which the author's own argument runs through the text, even when it is organised as a list of items each commented at some length. A short introduction followed by a list of other people's content stays true. | Ajustement volontaire (lot 5b) : l'anglais classait en compilation des articles argumentés organisés en liste, que l'auteur garde. La seconde phrase garde vraie la revue de liens. |
| 4. dans_themes : « justification », puis « ok » à true si le sujet principal de l'article relève d'au moins un des thèmes listés, même indirectement (par exemple le leadership ou la conduite du changement pour le coaching, la gestion de portefeuille pour la stratégie produit) ; | 4. dans_themes: "justification", then "ok" set to true if the main subject of the article falls under at least one of the listed themes, even indirectly (for example leadership or change management for coaching, portfolio management for product strategy); | Fidèle. « conduite du changement » : « change management » (équivalent usuel). Les exemples renvoient aux thèmes « coaching » et « product strategy » de la liste anglaise. |
| false s'il relève d'un autre domaine (technique pure, santé, finance, vie personnelle…). | false if it falls under another field (pure technology, health, finance, personal life…). | « technique pure » : « pure technology » (sens : sujet purement technique). |
| 5. promotionnel : « justification », puis « ok ». | 5. promotionnel: "justification", then "ok". | Fidèle. |
| Fais ce test : si on retire du texte tous les passages qui présentent une offre (livre, workshop, webinaire, club, newsletter, outil, service, appel à acheter ou à s'inscrire), reste-t-il un article argumenté complet ? | Run this test: if you remove from the text every passage that presents an offer (book, workshop, webinar, club, newsletter, tool, service, call to buy or to sign up, paid course), is a complete, argued article left? | Ajustement volontaire (lot 5b) : « paid course » ajouté à la liste des offres. |
| Si oui, réponds false, même si l'offre est mise en avant au début ou à la fin. | If so, answer false, even if the offer is highlighted at the start or at the end. | Fidèle. |
| Réponds true seulement s'il ne reste presque rien : annonce de webinaire ou de formation, page de présentation d'un livre ou d'un outil, invitation à télécharger ou à s'inscrire. | Answer true only if the main purpose of the text is to sell or to get the reader to sign up: a book excerpt or chapter published to launch that book (with a launch, pre-order or purchase mention); a book announcement; an announcement of, or registration for, a webinar, event, live session, paid course, cohort or programme; a commercial offer (presentation page for a tool or a service, invitation to download or to sign up). An author who mentions in passing their own book, newsletter, consultancy or services does not make promotional an article that develops a substantive thesis: answer false. | Ajustement volontaire (lot 5b, itération 2b) : « s'il ne reste presque rien » devient « si le but principal du texte est de vendre ou de faire s'inscrire ». Le 10 octobre, l'anglais d'origine gardait des extraits de chapitres d'un livre publiés par une newsletter produit et une annonce de livre, et ne voyait pas les webinaires : d'où les exemples explicites. La première itération (« même s'il reste un passage argumenté ») sur-détectait : elle écartait des articles de fond dont l'auteur cite son propre livre, sa newsletter ou ses services ; la mention en passant est donc exclue explicitement. |
| 6. Pour chaque critère ci-dessous : « justification », une phrase qui cite ou décrit l'élément précis du texte sur lequel tu t'appuies, puis « ok » (true ou false) cohérent avec cette justification. | 6. For each criterion below: "justification", one sentence that quotes or describes the specific element of the text you rely on, then "ok" (true or false) consistent with that justification. | Fidèle. |
| {criteria} | {criteria} | Marqueur identique ; il reçoit les questions anglaises du bloc CRITERIA. |

## CRITERIA : questions posées au modèle

| Clé | Français | Anglais | Remarque |
|---|---|---|---|
| these | L'article défend une idée centrale ou une position claire (une FAQ ou un entretien peut en avoir une). | The article defends a central idea or a clear position (an FAQ or an interview can have one). | Fidèle. |
| etaye | Les affirmations sont étayées par des données, des cas concrets ou des retours d'expérience. | The claims are backed by data, concrete cases or lessons from experience. | « retours d'expérience » : « lessons from experience ». |
| original | L'article apporte un point de vue propre, pas une reformulation de notions connues. | The article brings its own point of view, not a rewording of well-known notions. | Fidèle. |
| sources | L'article cite des sources, des auteurs ou des études identifiables. | The article cites identifiable sources, authors or studies. | Fidèle. |
| non_promo | L'article n'est ni promotionnel, ni une liste générique de conseils. | The article is neither promotional nor a generic list of tips. | Fidèle. |

## CRITERIA : raisons d'écart affichées quand le critère manque

| Clé | Français | Anglais | Remarque |
|---|---|---|---|
| these | pas de position claire | no clear position | Fidèle. |
| etaye | affirmations non étayées | claims not backed up | Fidèle. |
| original | reformulation de notions connues | rewording of well-known notions | Fidèle. |
| sources | aucune source citée | no source cited | Fidèle. |
| non_promo | promotionnel ou liste générique | promotional or generic list | Fidèle. |

## Thèmes (DEFAULT_CONFIG de `watch_triage.py`, même ordre)

| Français | Anglais | Remarque |
|---|---|---|
| discovery produit et expérimentation | product discovery and experimentation | « Discovery » reste le terme du métier ; « product » placé devant, ordre naturel en anglais. |
| flux, métriques de flux et prédictibilité | flow, flow metrics and predictability | Fidèle. |
| Product Operating Model et transformation produit | Product Operating Model and product transformation | Fidèle. |
| organisation multi-équipes, Team Topologies, dépendances | multi-team organisation, Team Topologies, dependencies | Fidèle. |
| OKR, priorisation, stratégie produit | OKRs, prioritisation, product strategy | Pluriel anglais « OKRs » ; orthographe britannique, comme le reste du dépôt. |
| plateformes internes et developer experience | internal platforms and developer experience | Fidèle. |
| coaching agile, facilitation, posture de Scrum Master | agile coaching, facilitation, Scrum Master stance | « posture » : « stance », terme retenu pour la posture du coach dans le dépôt. |
| IA dans le travail produit | AI in product work | Fidèle. |
