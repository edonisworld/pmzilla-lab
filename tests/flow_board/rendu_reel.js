// Rend chaque graphique avec le VRAI ECharts, côté serveur (SVG en chaîne), pour attraper une option invalide.
// Usage : node rendu_reel.js <echarts.min.js> <flow_board_page.js> <donnees.json>
const fs = require('fs');
const echarts = require(process.argv[2]);
const page = require(process.argv[3]);
const data = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
const sorties = [];
for (const dark of [false, true]) {
  const ctx = new page.Ctx(data, dark);
  data.series.forEach((s, si) => {
    ['', ...s.teams].forEach((team) => {
      const v = s.views[team];
      const builds = {
        flow: page.buildFlow(v, ctx), cfd: page.buildCfd(v, ctx, s.segment_order, s.segment_labels),
        segments: page.buildSegments(v, ctx, s.segment_labels),
        agingStatus: page.buildAging(s.points, team, 'status', v, ctx, s.segment_labels),
        agingSegment: page.buildAging(s.points, team, 'segment', v, ctx, s.segment_labels),
        wip: page.buildWip(v, ctx), wipHistory: page.buildWipHistory(v, ctx), leadTimes: page.buildLeadTimes(v, ctx),
        efficiency: page.buildEfficiency(v, ctx), lineLead: page.buildBaselineLine(v, ctx, 'lead', 'x', 'd'),
        lineWip: page.buildBaselineLine(v, ctx, 'wip', 'x', 'i'),
      };
      (s.dependencies || []).forEach((dep, i) => { builds['graph' + i] = page.buildGraph(dep, team, ctx); });
      for (const [nom, b] of Object.entries(builds)) {
        if (b.empty) { sorties.push({dark, serie: si, team, nom, vide: true}); continue; }
        const c = echarts.init(null, null, {renderer: 'svg', ssr: true, width: 900, height: 420});
        c.setOption(b.option);
        const svg = c.renderToSVGString();
        c.dispose();
        sorties.push({dark, serie: si, team, nom, taille: svg.length, formes: (svg.match(/<(path|circle|rect|polygon)/g) || []).length});
      }
    });
  });
}
console.log(JSON.stringify(sorties));
