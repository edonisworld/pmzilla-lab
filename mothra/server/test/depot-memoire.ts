// Test double of the sheet storage (task 18.1) and a synthetic body of a sheet: invented figures, no real data, no name.
import { FicheDejaPubliee, LIMITE_LISTE_FICHES } from "../src/fiches/depot.ts";
import type { ContenuFige, CorpsCalcule, DepotFiches, DepotSeuils, DepotUtilisateurs, FicheListee, FicheStockee, SeuilStocke } from "../src/fiches/depot.ts";

export class DepotMemoire implements DepotFiches, DepotSeuils, DepotUtilisateurs {
  fiches = new Map<string, FicheStockee>();
  // The users of the application: invented pseudonymous identifiers.
  utilisateurs = new Set<string>(["agile-lead-1", "agile-lead-2", "agile-lead-3"]);
  historique: SeuilStocke[] = [];
  appels: string[] = [];
  echec: Error | null = null;
  // The creation day given to the sheets (invented date), for the first reading of a sheet (task 18.4).
  aujourdHui = "2026-10-30";
  creations = new Map<string, string>();

  async creeeLe(id: string): Promise<string | null> {
    this.verifier();
    return this.creations.get(id) ?? null;
  }
  private suivant = 1;

  private verifier(): void {
    if (this.echec !== null) throw this.echec;
  }

  async creer(entree: Parameters<DepotFiches["creer"]>[0]): Promise<string> {
    this.verifier();
    this.appels.push("creer");
    const id = String(this.suivant++);
    this.fiches.set(id, {
      id,
      chart: entree.chart,
      scope: entree.scope,
      dataDate: entree.dataDate,
      state: "draft",
      managementQuestion: entree.managementQuestion,
      effect: entree.effect,
      cause: entree.cause,
      createdBy: entree.createdBy,
    });
    this.creations.set(id, this.aujourdHui);
    return id;
  }

  async lister(etat: Parameters<DepotFiches["lister"]>[0]): Promise<FicheListee[]> {
    this.verifier();
    this.appels.push("lister");
    return [...this.fiches.values()]
      .filter((f) => f.state === etat)
      .sort((a, b) => Number(b.id) - Number(a.id))
      .slice(0, LIMITE_LISTE_FICHES)
      .map((f) => ({ id: f.id, chart: f.chart, scope: f.scope, dataDate: f.dataDate, state: f.state }));
  }

  async lire(id: string): Promise<FicheStockee | null> {
    this.verifier();
    const f = this.fiches.get(id);
    return f === undefined ? null : structuredClone(f);
  }

  async modifier(id: string, changement: Parameters<DepotFiches["modifier"]>[1]): Promise<void> {
    this.verifier();
    this.appels.push("modifier");
    const f = this.fiches.get(id);
    if (f !== undefined && f.state === "draft") {
      if (changement.managementQuestion !== undefined) f.managementQuestion = changement.managementQuestion;
      if (changement.effect !== undefined) f.effect = changement.effect;
      if (changement.cause !== undefined) f.cause = changement.cause;
    }
  }

  async utilisateurExiste(id: string): Promise<boolean> {
    this.verifier();
    return this.utilisateurs.has(id);
  }

  async relire(id: string, reviewer: string): Promise<void> {
    this.verifier();
    this.appels.push("relire");
    const f = this.fiches.get(id);
    if (f !== undefined && f.state === "draft") {
      f.state = "reviewed";
      f.reviewedBy = reviewer;
    }
  }

  async publier(id: string, entree: { content: ContenuFige; fingerprint: string; publishedBy: string }): Promise<{ version: number; publishedOn: string }> {
    this.verifier();
    this.appels.push("publier");
    const f = this.fiches.get(id);
    if (f === undefined) throw new Error("fiche inconnue");
    // Like the transaction of the real depot: only a reviewed sheet is frozen.
    if (f.state !== "reviewed") throw new FicheDejaPubliee();
    const publie = { version: 1, publishedOn: "2026-11-09" };
    f.state = "published";
    f.published = { ...publie, content: entree.content, fingerprint: entree.fingerprint, publishedBy: entree.publishedBy };
    return publie;
  }

  async seuils(): Promise<SeuilStocke[]> {
    this.verifier();
    return structuredClone(this.historique);
  }

  async ajouterSeuil(seuil: SeuilStocke): Promise<void> {
    this.verifier();
    this.historique.push({ ...seuil });
  }
}

// A synthetic body: a verdict "not settled", the three explanations, an unraised signal, the method face with codes and parameters only.
export function corpsSynthetique(extra: Record<string, unknown> = {}): CorpsCalcule {
  return {
    verdict: "not_settled",
    verdictReasons: [{ explanation: "capacity", state: "not_measurable", reason: "ready_queue_not_measured" }],
    h1Reasons: [],
    h5Reasons: [],
    explanations: [
      { name: "unplanned_work", state: "not_measurable", reason: "defects_without_team" },
      { name: "capacity", state: "not_measurable" },
      { name: "dependencies", state: "ruled_out" },
    ],
    attachmentSignal: "not_raised",
    attachmentSignalReasons: [],
    attachmentSignalShown: false,
    method: {
      method: "lead_time_against_cycle_time",
      scope: { level: "team", id: "team-a" },
      period: { quarters: [{ year: 2026, quarter: 1 }, { year: 2026, quarter: 2 }] },
      thresholds: [{ code: "h5_band", value: 0.2, fixedOn: "2026-10-30", fixedBy: "author_alone" }],
      thresholdsFixedOn: "2026-10-30",
      dataDate: "2026-10-01",
      fingerprint: "a".repeat(64),
      coverage: { state: "value", value: 12 },
      maskedCells: [{ measure: "throughput", cell: { state: "masked", threshold: 5 } }],
      insufficientSamples: [],
      excluded: { median: [], p85: [], throughput: [] },
      limits: ["no_per_team_unplanned_measure"],
      authorRole: "agile_lead",
      version: 1,
      hypothesis: "h5",
    },
    ...extra,
  } as CorpsCalcule;
}
