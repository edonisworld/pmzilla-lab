// ECharts, registered by module (bundle size): a line chart, a custom series (the marked quarters), a grid, a legend and the SVG
// renderer, nothing else. The SVG renderer draws text, so a label stays readable and testable; the canvas renderer is not registered.
// With no element, the chart is created for server-side rendering (no browser), which the tests use to read the SVG. The chart
// component loads this module on demand, so ECharts is its own chunk.
import { CustomChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent } from "echarts/components";
import { init, use } from "echarts/core";
import { SVGRenderer } from "echarts/renderers";

use([LineChart, CustomChart, GridComponent, LegendComponent, SVGRenderer]);

export function creerGraphique(element: HTMLElement | null, largeur?: number, hauteur?: number) {
  if (element === null) return init(null, null, { renderer: "svg", ssr: true, width: largeur, height: hauteur });
  return init(element, null, { renderer: "svg" });
}
