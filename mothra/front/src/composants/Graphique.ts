// The lead time / cycle time chart (design D19, D22). The chart is drawn by ECharts in the browser from options built by a pure
// function; the table beside it shows the same points, so the chart is never the only way to read a figure. Labels come from the
// catalogue, colours and styles from the design tokens. ECharts is loaded on demand (its own chunk): the page shows its table first.
import { createElement as h, Fragment, useEffect, useRef, useState } from "react";
import type { ReactElement } from "react";
import { useIntl } from "react-intl";
import type { PointTrimestre } from "@mothra/contract";

import { cleErreur } from "../api/vue.ts";
import { construireOptions, lirePalette, lireStyle } from "./optionsGraphique.ts";
import type { Libelles } from "./optionsGraphique.ts";
import { libelleTrimestre } from "./trimestre.ts";

type Instance = ReturnType<typeof import("./echarts.ts").creerGraphique>;

interface PropsGraphique {
  points: readonly PointTrimestre[];
  // The ids of the equivalent table and of the sentence that states the masking threshold (aria-describedby).
  idTableau?: string;
  idSeuil?: string;
}

export function Graphique({ points, idTableau, idSeuil }: PropsGraphique): ReactElement {
  const intl = useIntl();
  const conteneur = useRef<HTMLDivElement>(null);
  const [echec, setEchec] = useState(false);
  const libelles: Libelles = {
    lead: intl.formatMessage({ id: "tableau.series.lead" }),
    cycle: intl.formatMessage({ id: "tableau.series.cycle" }),
    axis: intl.formatMessage({ id: "tableau.axis.days" }),
    masked: intl.formatMessage({ id: "cellState.masked" }),
    insufficient: intl.formatMessage({ id: "state.insufficient_sample" }),
    quarter: (brut) => libelleTrimestre(brut, (id, valeurs) => intl.formatMessage({ id }, valeurs)),
  };
  const etiquette = [
    libelles.lead,
    libelles.cycle,
    libelles.axis,
    libelles.masked,
    libelles.insufficient,
    intl.locale,
  ].join("|");
  useEffect(() => {
    const element = conteneur.current;
    if (element === null) return undefined;
    let annule = false;
    let graphique: Instance | null = null;
    const adapter = (): void => graphique?.resize();
    setEchec(false);
    // A failed load (or a failed drawing) is shown as the internal error beside the table, never a silent empty zone (A-84).
    void import("./echarts.ts")
      .then(({ creerGraphique }) => {
        if (annule) return;
        graphique = creerGraphique(element);
        graphique.setOption(construireOptions(points, libelles, lirePalette(document.documentElement), lireStyle(document.documentElement)));
        window.addEventListener("resize", adapter);
      })
      .catch(() => {
        if (!annule) setEchec(true);
      });
    return () => {
      annule = true;
      window.removeEventListener("resize", adapter);
      graphique?.dispose();
    };
    // The labels are rebuilt on every render; their joined text changes only with the language.
  }, [points, etiquette]);
  const decritPar = [idTableau, idSeuil].filter((i): i is string => i !== undefined).join(" ");
  return h(
    Fragment,
    null,
    h("div", {
      className: "graphique",
      role: "img",
      "aria-label": intl.formatMessage({ id: "tableau.chart.label" }),
      "aria-describedby": decritPar === "" ? undefined : decritPar,
      ref: conteneur,
    }),
    echec ? h("p", { role: "alert", className: "page-erreur" }, intl.formatMessage({ id: cleErreur("INTERNAL") })) : null,
  );
}
