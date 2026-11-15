// The shape of an argument sheet as the verdict service answers it (design D20, D21, D22, D29, D33). The sheet screen only shows what it
// receives: the verdict, the states of the explanations, the signal and the shares are computed by the service (design D30), never in a
// component. Until the routes of group 18 exist, the screen is fed with simulated answers (test fixtures, declared so).
import type {
  CelluleMasqueeContrat,
  CorpsFiche,
  EtatEtDatePublication,
  EtatExplication,
  EtatSignal,
  ExclusionsH5,
  Explication,
  ExplicationFiche,
  LienId,
  MethodeFiche,
  MotifH1,
  MotifH5,
  MotifSignal,
  ModificationFiche,
  Part,
  QuestionDeDirection,
  RaisonTexte,
  RaisonVerdict,
  ReponseFiche,
  ResultatAction,
  Seuil,
  TexteLibre,
  TexteRefuse,
  Trimestre,
  Verdict,
  VerdictOuEchantillon,
} from "@mothra/contract";

// The types of the verdict service are the contract's own (group 17); the screen imports them through this module.
export type { EtatExplication, EtatSignal, ExclusionsH5, Explication, LienId, MotifH1, MotifH5, MotifSignal, RaisonVerdict, Verdict, VerdictOuEchantillon };

export const ETATS_FICHE = ["draft", "reviewed", "published"] as const;
export type EtatFiche = (typeof ETATS_FICHE)[number];

// The lists of the contract (subpath `./listes-fiche`, browser-safe): no copy in the front.
export {
  EXPLICATIONS_DE_FICHE as EXPLICATIONS,
  LIENS_DE_FICHE as LIENS,
  VERDICTS_DE_FICHE as VERDICTS_AFFICHES,
} from "@mothra/contract/listes-fiche";

// The refusal of a written text (D20, `TEXT_REFUSED`): the field, the reason, and the count and the maximum with `too_long` only. The
// refused value is never part of it. It is the contract's answer without its `error` code.
export type RefusTexte = Omit<TexteRefuse, "error">;

// What a route of the sheet raises when the service refuses: the code of the answer, and the detail of a refused text. The screen shows
// the translated label of the code, never the message.
export class RefusFiche extends Error {
  code: string;
  texte?: RefusTexte;

  constructor(code: string, texte?: RefusTexte) {
    super(code);
    this.name = "RefusFiche";
    this.code = code;
    if (texte !== undefined) this.texte = texte;
  }
}

// What the completion of a draft (PATCH /api/sheets/:id) gives back: success, or the code of the refusal and, for `TEXT_REFUSED`, its detail.
export type ResultatCompletion = { ok: true } | { ok: false; code: string; texte?: RefusTexte };

// `ModificationFiche` is the contract's: the three fields a draft is created with or completed by, each optional (design D29).
export type { ExplicationFiche, ModificationFiche, QuestionDeDirection, RaisonTexte };

// The shapes of the sheet's answer are the contract's own (one data layer, D30); the screen imports them through this module.
export type {
  CelluleMasqueeContrat,
  CorpsFiche,
  EtatEtDatePublication,
  MethodeFiche,
  Part,
  ReponseFiche,
  ResultatAction,
  Seuil,
  TexteLibre,
  Trimestre,
};
