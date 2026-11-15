// Public entry of the contract package: what the server and the front may import by `@mothra/contract`.
// The generator (generer.ts) is an author's command, not part of the public surface.
export { PLANCHER } from "./plancher.ts";
export { REAL_DATA_COUNTS_ALLOWED } from "./donnees-reelles.ts";
export { SchemaCellule, cellule } from "./cellule.ts";
export type { Cellule } from "./cellule.ts";
export { masquerVue } from "./masquage.ts";
export type { LigneBrute } from "./masquage.ts";
export { tailleEchantillonH1 } from "./taille-echantillon.ts";
export type { GenreEchantillon } from "./taille-echantillon.ts";
export {
  MOTIF_IDENTIFIANT_EQUIPE,
  SchemaFiltres,
  TRIMESTRES_RETENUS,
  identifiantEquipe,
  scopeFiche,
  totalDePlage,
  verifierFiltres,
} from "./filtres.ts";
export type { CodeFiltre, Filtres, OptionsFiltres, PeriodeCompte, Portee, ResultatFiltres } from "./filtres.ts";
export { SchemaReponseVue, SchemaValeurDeLigne, estReponseVue, schemaReponseDeVue } from "./reponse.ts";
export type { GenreDeLigne, LigneReponse, ReponseVue, ValeurSimple } from "./reponse.ts";
export {
  SchemaBrouillon,
  SchemaDemandeFiche,
  SchemaLigneTrimestre,
  SchemaMesure,
  SchemaPointTrimestre,
  SchemaReponseLeadCycle,
  SchemaReponseLeadCycleReduite,
  SchemaSerieEquipe,
  SchemaSerieEquipeReduite,
} from "./lead-cycle.ts";
export type {
  Brouillon,
  DemandeFiche,
  LigneTrimestre,
  Mesure,
  PointTrimestre,
  ReponseLeadCycle,
  ReponseLeadCycleReduite,
  SerieEquipe,
} from "./lead-cycle.ts";
export { reduceToStatistics, reduitEnMode, servirCorps, servirPanneau, servirTableau, servirVue } from "./reduction.ts";
export type { ModeDonnees } from "./reduction.ts";
export { partsDAttente } from "./parts-attente.ts";
export type { BarreAttente, EntreePartsDAttente, PartsDAttente, RepereAttente } from "./parts-attente.ts";
export {
  CODES_PANNEAUX,
  HYPOTHESES_PANNEAUX,
  MENTIONS_PANNEAUX,
  PorteeProduitRefusee,
  SchemaPanneauBlockedShare,
  SchemaPanneauCorrectionShare,
  SchemaPanneauDefectsInout,
  SchemaPanneauReduit,
  SchemaPanneauStoriesInout,
  panneauBlockedShare,
  panneauCorrectionShare,
  panneauDefectsInout,
  panneauStoriesInout,
  partDeDebitEnCorrection,
} from "./panneaux.ts";
export type {
  CodePanneau,
  EntreeBloque,
  EntreeFlux,
  GroupeType,
  PanneauBlockedShare,
  PanneauComplet,
  PanneauCorrectionShare,
  PanneauDefectsInout,
  PanneauReduit,
  PanneauStoriesInout,
} from "./panneaux.ts";
export {
  CODES_AVIS,
  CODES_ETAT_PAGE,
  CODES_ETAT_VIDE,
  CODES_REFUS_PAGE,
  CODES_SOURCE_READY,
  CODE_COMPTES_REELS_MASQUES,
  CODE_DOMAINE_TROP_PETIT,
  EQUIPES_MINIMUM_DOMAINE,
  MOTIF_CLE_CYCLE,
  SchemaCycleOffert,
  SchemaDemandeCyclePreparation,
  SchemaRefusCyclePreparation,
  SchemaReponseCycleAffichee,
  SchemaReponseCyclePreparation,
  SchemaReponseCycleVide,
  cadrerSelonMapping,
  choisirCycle,
  choisirEtats,
  totalDesCellules,
  verifierPorteeDomaine,
} from "./cycle-preparation/index.ts";
export type {
  CodeAvis,
  CodeEtatPage,
  CodeEtatVide,
  CodeRefusPage,
  CodeSourceReady,
  CycleCle,
  CycleOffert,
  DemandeCyclePreparation,
  EntreeEtats,
  EtatCycle,
  ReponseCyclePreparation,
  ResultatCycle,
  ResultatEtats,
  ResultatPortee,
} from "./cycle-preparation/index.ts";
export type {
  CelluleMasqueeContrat,
  CorpsFiche,
  EtatEtDatePublication,
  EtatDeLaFiche,
  MethodeFiche,
  Part,
  PointDeFiche,
  RapportsH1,
  RapportsTrimestre,
  StatistiquesP85,
  ReponseFiche,
  ResultatAction,
  Seuil,
  TexteLibre,
  Trimestre,
} from "./fiche.ts";
export { BORNES_SEUILS, codeDeSeuilConnu, couplesIncoherents, seuilDansLesBornes } from "./bornes-seuils.ts";
export { ETIQUETTE_ANNEE_GROUPEE, tableauLeadCycle } from "./lead-cycle.ts";
export {
  GraphiqueInconnu,
  PorteeNonServie,
  SeuilsIncoherents,
  SeuilsNonFixes,
  TOUS_LES_CODES_SEUILS,
  corpsDepuisVues,
  lireSeuils,
  verifierCreation,
} from "./corps-fiche.ts";
export type { CorpsDepuisVues, EntreeCorps, EntreeHistorique, VuesDeLaFiche } from "./corps-fiche.ts";
export {
  ANNEE_GROUPEE,
  CODES_JEU_DE_DONNEES,
  CODES_LIMITES,
  CONSTATS_DE_VERDICT,
  ETATS_COUVERTURE,
  POSITIONS_DEBIT,
  CODES_SEUILS,
  GRAPHIQUES_DE_FICHE,
  METHODES,
  RAISONS_EXPLICATION,
  ROLE_AUTEUR,
  codeMesure,
  codesRequis,
  estGraphiqueDeFiche,
  lireCodeMesure,
} from "./listes-fiche.ts";
export { porteeDeScope } from "./equipe.ts";
export type { CodeJeuDeDonnees, CodeLimite, CodeMethode, GraphiqueDeFiche } from "./listes-fiche.ts";
export { celluleDe, mesureDeStatistique } from "./lecture-vue.ts";
export {
  dateDonneesAdmise,
  dernierTrimestreClos,
  decalerTrimestres,
  debutTrimestreContenant,
  etiquetteTrimestre,
  fenetreConforme,
  fenetreTroisTrimestres,
  fichePerimee,
  trimestreDe,
} from "./trimestres.ts";
export type { ExplicationFiche, GraphiqueFiche } from "./fiche.ts";
export { SchemaVues } from "./vues.ts";
export type { Contrat, Vue } from "./vues.ts";
export { RefusContrat, chargerContrat, lireContrat, seuilEffectif, validerContrat, vueAcceptee } from "./chargeur.ts";
export type { CodeRefus } from "./chargeur.ts";
export { chargerCasParite, jouerCasParite } from "./parite.ts";
export type { CasCellule, CasParite, CasSeuil, CasVue } from "./parite.ts";
export {
  attachmentSignal,
  constatsFinaux,
  echantillonSuffisant,
  h1Evaluer,
  h1Verdict,
  h5Evaluer,
  h5Verdict,
  linkColour,
  litLeDebit,
  coverageState,
  referenceH5,
  thresholdModifiedAfterReading,
  throughputPositions,
  twoThresholds,
  unplannedWorkExplanation,
  verdictFinal,
} from "./verdict.ts";
export type {
  ConfigEchantillon,
  ConfigH5,
  ConstatDeVerdict,
  EntreeSeuil,
  EtatCouverture,
  EtatExplication,
  EtatLien,
  EtatSignal,
  ExclusionsH5,
  Explication,
  FeuilleLien,
  LienId,
  MotifH1,
  MotifH5,
  MotifSignal,
  PositionDebit,
  RaisonVerdict,
  ResultatLien,
  TrimestreH5,
  Verdict,
  VerdictOuEchantillon,
} from "./verdict.ts";
export { chargerCasVerdict, jouerCasVerdict } from "./parite-verdict.ts";
export type { CasVerdict } from "./parite-verdict.ts";
export { TEXTE_LONGUEUR_MAX, ligneCorrespond, lireNoms, motifsDeNoms, verifierTexteEcrit } from "./texte.ts";
export type { RaisonTexte, ResultatTexte } from "./texte.ts";
export { estDistinctif, nomsDistinctifsDeLExtrait } from "./noms.ts";
export {
  QUESTIONS_DE_DIRECTION,
  SchemaQuestionDeDirection,
  SchemaModificationFiche,
  SchemaCreationFiche,
  SchemaEntreeSeuil,
  SchemaEtatDeListe,
  SchemaFicheSansCorps,
  SchemaListeFiches,
  SchemaReponseFiche,
  SchemaReponseFicheReduite,
  SchemaReponseSeuils,
  SchemaSeuilEnregistre,
  SchemaTexteLibre,
  SchemaTexteRefuse,
} from "./fiche-schema.ts";
export type { CreationFiche, EntreeSeuilRequete, EtatDeListe, FicheSansCorps, ModificationFiche, QuestionDeDirection, TexteRefuse } from "./fiche-schema.ts";
