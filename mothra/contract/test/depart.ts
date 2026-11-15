// Starting configuration of the synthetic runs (annex of design D30, non-normative). It lives with the tests: the adopted values come
// from the threshold history, never from the contract package, and the server does not import this file.
export const DEPART_H1 = { lower: 1.5, upper: 3 } as const;
export const DEPART_H5 = { band: 0.2, doubleBand: 0.4, runRises: 2, runMinCumulativeRise: 0.1, floor: 0.8, lowFloor: 0.6 } as const;
export const DEPART_RATTACHEMENT = { thresholdPoints: 10 } as const;
export const DEPART_LIEN = { minTeams: 3 } as const;
export const DEPART_ECHANTILLON = { medianMinItems: 10, p85MinItems: 20 } as const;
