// The start of the bundle (task 19.7, Q69): the loading state while the server is looked for, then the application; in production, a failed
// probe shows its error from the catalogue and a button that starts the probe again. The probe and the application are injected.
import { createElement as h, useEffect, useState } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";

import type { SourceLeadCycle } from "../api/leadCycle.ts";
import { PageChargement } from "./PageChargement.ts";

export type EtatDemarrage = { genre: "sonde" } | { genre: "echec" } | { genre: "pret"; source: SourceLeadCycle };

export function VueDemarrage({ etat, reessayer }: { etat: EtatDemarrage; reessayer: () => void }): ReactElement {
  const intl = useIntl();
  if (etat.genre === "sonde") return h(PageChargement);
  return h(
    "div",
    { role: "alert", className: "page-erreur" },
    h("p", null, intl.formatMessage({ id: "page.serverUnreachable" })),
    h("button", { type: "button", className: "bouton", onClick: reessayer }, intl.formatMessage({ id: "page.retry" })),
  );
}

interface Props {
  // The probe: the source to use, or none when the server is absent and no simulated source is allowed.
  sonder: () => Promise<SourceLeadCycle | undefined>;
  application: (source: SourceLeadCycle) => ReactElement;
}

export function PageDemarrage({ sonder, application }: Props): ReactElement {
  const [etat, changerEtat] = useState<EtatDemarrage>({ genre: "sonde" });
  const lancer = (): void => {
    changerEtat({ genre: "sonde" });
    void sonder().then((source) => changerEtat(source === undefined ? { genre: "echec" } : { genre: "pret", source }));
  };
  useEffect(lancer, []);
  return etat.genre === "pret" ? application(etat.source) : h(VueDemarrage, { etat, reessayer: lancer });
}
