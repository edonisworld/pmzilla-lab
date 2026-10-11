/* PMZilla Lab : page du tableau de bord des flux (flow_board.py). Aucune requête réseau : les données et la
   bibliothèque de graphiques sont dans le fichier. Les constructeurs d'options (build*) sont purs : ils ne touchent ni
   au DOM ni à ECharts, ce qui permet de les tester sous Node. */
(function (root) {
  'use strict';

  // ---- thème : palette Okabe-Ito (lisible par les daltoniens) ; la couleur ne porte jamais seule l'information :
  // formes, motifs (decal d'ECharts), libellés et valeurs s'y ajoutent.
  var PALETTES = {
    light: {fg: '#1c1c1a', muted: '#5f5e5a', grid: '#d3d1c7', bg: '#ffffff',
            colors: ['#0072B2', '#E69F00', '#009E73', '#D55E00', '#CC79A7', '#56B4E9', '#7a6f00'], neutral: '#8a8880'},
    dark: {fg: '#ecebe6', muted: '#a7a59d', grid: '#3d3d3a', bg: '#1f1f1d',
           colors: ['#56B4E9', '#F0B83A', '#2FC79A', '#FF8A4C', '#E39BC4', '#8DCCF3', '#E8DC6A'], neutral: '#9b9a93'}
  };
  var NATURE_SYMBOL = {active: 'circle', waiting: 'triangle', dormant: 'diamond'};

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
    });
  }
  function md(s) { return esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>'); }

  function Ctx(data, dark) {
    this.T = data.texts; this.lang = data.lang; this.th = PALETTES[dark ? 'dark' : 'light'];
  }
  Ctx.prototype.num = function (v, d) {
    if (v == null || isNaN(v)) return this.T.nd;
    var s = Number(v).toFixed(d == null ? 0 : d);
    return this.lang === 'fr' ? s.replace('.', ',') : s;
  };
  Ctx.prototype.days = function (v) { return v == null ? this.T.nd : this.num(v, 0) + ' ' + this.T.unit_day; };
  Ctx.prototype.pct = function (v) { return v == null ? this.T.nd : this.num(100 * v, 0) + '%'; };
  Ctx.prototype.fmt = function (s) {
    var args = Array.prototype.slice.call(arguments, 1);
    return String(s).replace(/\{(\w+)\}/g, function (m, k) { return args[0] && args[0][k] != null ? args[0][k] : m; });
  };

  function base(ctx) {
    var th = ctx.th;
    return {
      backgroundColor: 'transparent', animation: false, color: th.colors,
      textStyle: {color: th.fg, fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif'},
      aria: {enabled: true, decal: {show: true}},
      tooltip: {confine: true, backgroundColor: th.bg, borderColor: th.grid, textStyle: {color: th.fg}},
      legend: {textStyle: {color: th.fg}, top: 0, type: 'scroll'},
      grid: {left: 12, right: 40, top: 60, bottom: 28, containLabel: true}
    };
  }
  function axisStyle(ctx) {
    return {axisLine: {lineStyle: {color: ctx.th.grid}}, axisLabel: {color: ctx.th.muted},
            splitLine: {lineStyle: {color: ctx.th.grid, opacity: 0.6}}, nameTextStyle: {color: ctx.th.muted}};
  }
  function merge(a, b) { for (var k in b) a[k] = b[k]; return a; }
  // axe vertical : le nom reste aligné à gauche de l'axe (il ne déborde pas de la page)
  function yAxis(ctx, name, extra) {
    var a = merge({type: 'value', name: name, nameLocation: 'end', nameGap: 14}, axisStyle(ctx));
    a.nameTextStyle = {color: ctx.th.muted, align: 'left'};
    return merge(a, extra || {});
  }
  function empty(msg) { return {empty: msg}; }

  // ---- 1. arrivées et sorties
  function buildFlow(view, ctx) {
    var T = ctx.T;
    if (!view || !view.weeks || !view.weeks.length) return empty(T.no_data);
    var series = [{name: T.departures, type: 'line', data: view.departures, symbol: 'circle', symbolSize: 8,
                   lineStyle: {width: 2.6, type: 'solid'}, itemStyle: {color: ctx.th.colors[0]}}];
    var note = null;
    if (view.arrivals) {
      series.push({name: T.arrivals, type: 'line', data: view.arrivals, symbol: 'triangle', symbolSize: 9,
                   lineStyle: {width: 2.2, type: 'dashed'}, itemStyle: {color: ctx.th.colors[1]}});
    } else { note = T.arrivals_missing; }
    var o = base(ctx);
    o.tooltip.trigger = 'axis';
    o.xAxis = merge({type: 'category', data: view.weeks, name: T.week_of, nameLocation: 'middle', nameGap: 34,
                     axisLabel: {color: ctx.th.muted, hideOverlap: true}}, {axisLine: axisStyle(ctx).axisLine});
    o.yAxis = yAxis(ctx, T.per_week, {minInterval: 1});
    o.series = series;
    o.grid.bottom = 52;
    return {option: o, note: note};
  }

  // ---- 2. diagramme de flux cumulé
  function segLabel(seg, labels) { return (labels && labels[seg]) || seg; }
  function buildCfd(view, ctx, order, labels) {
    var T = ctx.T, c = view && view.cfd;
    if (!c || !c.weeks || !c.weeks.length) return empty(T.cfd_missing);
    var bands = [{name: T.cfd_delivered, data: c.delivered, color: ctx.th.colors[2]}];
    var segs = (order && order.length ? order : Object.keys(c.segments || {})).filter(function (s) { return c.segments[s]; });
    var rev = segs.slice().reverse();
    rev.forEach(function (s, i) {
      bands.push({name: segLabel(s, labels), data: c.segments[s], color: ctx.th.colors[(i + 3) % ctx.th.colors.length]});
    });
    bands.push({name: T.cfd_backlog, data: c.backlog, color: ctx.th.neutral});
    var o = base(ctx);
    o.tooltip.trigger = 'axis';
    o.xAxis = merge({type: 'category', boundaryGap: false, data: c.weeks, name: T.week_of, nameLocation: 'middle',
                     nameGap: 34, axisLabel: {color: ctx.th.muted, hideOverlap: true}}, {axisLine: axisStyle(ctx).axisLine});
    o.yAxis = yAxis(ctx, T.unit_items, {minInterval: 1});
    o.series = bands.map(function (b) {
      return {name: b.name, type: 'line', stack: 'cfd', symbol: 'none', data: b.data, lineStyle: {width: 1, color: b.color},
              areaStyle: {opacity: 0.8, color: b.color}, itemStyle: {color: b.color}, emphasis: {focus: 'series'}};
    });
    o.grid.bottom = 52;
    return {option: o, note: ctx.fmt(T.cfd_coverage, {n: c.n, m: c.without_history})};
  }

  // ---- 3. temps par segment (P50 et P85 en barres)
  function buildSegments(view, ctx, labels) {
    var T = ctx.T, s = view && view.segments;
    if (!s) return empty(T.seg_missing);
    var order = (s.order || Object.keys(s.left)).filter(function (k) { return s.left[k]; });
    if (!order.length) return empty(T.no_data);
    var cats = order.map(function (k) { return segLabel(k, labels) + '\n(' + ctx.fmt(T.tickets_n, {n: s.left[k].n}) + ')'; });
    function bar(name, key, color) {
      return {name: name, type: 'bar', data: order.map(function (k) { return s.left[k][key]; }),
              itemStyle: {color: color}, label: {show: true, position: 'top', color: ctx.th.fg,
              formatter: function (p) { return p.value == null ? '' : ctx.days(p.value); }}};
    }
    var o = base(ctx);
    o.tooltip.trigger = 'axis'; o.tooltip.axisPointer = {type: 'shadow'};
    o.xAxis = merge({type: 'category', data: cats, axisLabel: {color: ctx.th.fg, interval: 0}}, {axisLine: axisStyle(ctx).axisLine});
    o.yAxis = yAxis(ctx, T.days + ' (' + T.left_segment + ')');
    o.series = [bar(T.p50, 'p50', ctx.th.colors[0]), bar(T.p85, 'p85', ctx.th.colors[1])];
    return {option: o};
  }

  // ---- 4. Aging WIP : un point par ticket en cours, sans clé
  function jitter(i) { return Math.round((((i * 37) % 100) / 100) * 40 - 20); }      // décalage horizontal en pixels
  function buildAging(points, team, mode, view, ctx, labels) {
    var T = ctx.T;
    if (!points || !points.items) return empty(T.aging_missing);
    var items = points.items.filter(function (p) { return !team || p.team === team; });
    if (!items.length) return empty(T.no_data);
    var useSeg = mode === 'segment';
    function cat(p) { return useSeg ? (p.segment ? segLabel(p.segment, labels) : T.no_history) : p.status; }
    var cats = [];
    if (useSeg) {
      (points.segments || []).forEach(function (s) { cats.push(segLabel(s, labels)); });
      if (items.some(function (p) { return !p.segment; })) cats.push(T.no_history);
      items.forEach(function (p) { var c = cat(p); if (cats.indexOf(c) < 0) cats.push(c); });
    } else {
      items.forEach(function (p) { var c = cat(p); if (cats.indexOf(c) < 0) cats.push(c); });
      cats.sort(function (a, b) { return String(a).toLowerCase() < String(b).toLowerCase() ? -1 : 1; });
    }
    var names = {active: T.nature_active, waiting: T.nature_waiting, dormant: T.nature_dormant};
    var series = ['active', 'waiting', 'dormant'].map(function (nat, k) {
      var color = ctx.th.colors[[0, 1, 3][k]];
      var data = [];
      items.forEach(function (p, i) {
        if (p.nature !== nat) return;
        data.push({value: [cat(p), p.age], symbolOffset: [jitter(i), 0], p: p});
      });
      return {name: names[nat], type: 'scatter', symbol: NATURE_SYMBOL[nat], symbolSize: nat === 'waiting' ? 11 : 10,
              data: data, itemStyle: nat === 'dormant' ? {color: 'transparent', borderColor: color, borderWidth: 2}
                                                       : {color: color, opacity: 0.85},
              emphasis: {scale: 1.5}};
    });
    var p85 = view && view.lead_time ? view.lead_time[85] : null;
    if (p85 != null) {
      series[0].markLine = {silent: true, symbol: 'none', lineStyle: {color: ctx.th.fg, type: 'dashed', width: 1.4},
                            label: {color: ctx.th.fg, formatter: T.aging_p85 + ' ' + ctx.days(p85), position: 'insideEndTop'},
                            data: [{yAxis: p85}]};
    }
    var o = base(ctx);
    o.tooltip.trigger = 'item';
    o.tooltip.formatter = function (q) {
      var p = q.data.p, rows = [esc(q.seriesName), esc(p.team), T.status + ': ' + esc(p.status),
                                T.segment + ': ' + esc(p.segment ? segLabel(p.segment, labels) : T.no_history),
                                T.age_days + ': ' + ctx.num(p.age, 0)];
      if (p.age_segment != null) rows.push(T.in_segment_age + ': ' + ctx.num(p.age_segment, 0));
      return rows.join('<br>');
    };
    o.xAxis = {type: 'category', data: cats, axisLine: axisStyle(ctx).axisLine, axisTick: {alignWithLabel: true},
               axisLabel: {color: ctx.th.fg, interval: 0}, splitLine: {show: true, lineStyle: {color: ctx.th.grid, opacity: 0.35}}};
    o.yAxis = yAxis(ctx, T.age_days);
    o.series = series;
    o.grid.bottom = 36;
    return {option: o, note: T.aging_note, count: items.length, categories: cats};
  }

  // ---- 5. répartition du WIP et son évolution
  function natureParts(w) { return [w.active, w.waiting, w.dormant]; }
  function buildWip(view, ctx) {
    var T = ctx.T, w = view && view.wip;
    if (!w || w.total == null) return empty(T.no_data);
    var hasSplit = w.active != null || w.waiting != null || w.dormant != null;
    var o = base(ctx);
    o.tooltip.trigger = 'item';
    o.xAxis = merge({type: 'value', minInterval: 1}, axisStyle(ctx));
    o.yAxis = {type: 'category', data: [T.wip_now], axisLabel: {color: ctx.th.fg}, axisLine: axisStyle(ctx).axisLine};
    if (!hasSplit) {
      o.series = [{name: T.wip_total, type: 'bar', data: [w.total], barWidth: 46, itemStyle: {color: ctx.th.colors[0]},
                   label: {show: true, color: ctx.th.fg, position: 'right', formatter: function (p) { return T.wip_total + ' ' + p.value; }}}];
      return {option: o, note: T.wip_only_total};
    }
    var defs = [[T.nature_active, w.active, 0], [T.nature_waiting, w.waiting, 1], [T.nature_dormant, w.dormant, 3]];
    o.series = defs.filter(function (d) { return d[1] != null; }).map(function (d) {
      return {name: d[0], type: 'bar', stack: 'wip', data: [d[1]], barWidth: 46, itemStyle: {color: ctx.th.colors[d[2]]},
              label: {show: d[1] > 0, color: '#fff', formatter: function (p) {
                return p.seriesName + ' ' + p.value + (w.total ? ' (' + ctx.pct(p.value / w.total) + ')' : '');
              }, textBorderColor: 'rgba(0,0,0,.55)', textBorderWidth: 2}};
    });
    o.grid.left = 12;
    return {option: o};
  }
  function buildWipHistory(view, ctx) {
    var T = ctx.T, h = (view && view.history || []).filter(function (e) { return e.wip && e.wip.total != null; });
    if (h.length < 2) return empty(T.no_data);
    var dates = h.map(function (e) { return e.date; });
    function col(f) { return h.map(function (e) { return f(e.wip); }); }
    var split = function (w) { return w.active != null || w.waiting != null || w.dormant != null; };
    var o = base(ctx);
    o.tooltip.trigger = 'axis'; o.tooltip.axisPointer = {type: 'shadow'};
    o.xAxis = merge({type: 'category', data: dates}, {axisLine: axisStyle(ctx).axisLine, axisLabel: {color: ctx.th.fg}});
    o.yAxis = yAxis(ctx, T.unit_items, {minInterval: 1});
    o.series = [
      {name: T.nature_active, type: 'bar', stack: 'h', data: col(function (w) { return split(w) ? w.active : null; }), itemStyle: {color: ctx.th.colors[0]}},
      {name: T.nature_waiting, type: 'bar', stack: 'h', data: col(function (w) { return split(w) ? w.waiting : null; }), itemStyle: {color: ctx.th.colors[1]}},
      {name: T.nature_dormant, type: 'bar', stack: 'h', data: col(function (w) { return split(w) ? w.dormant : null; }), itemStyle: {color: ctx.th.colors[3]}},
      {name: T.wip_total + ' (' + T.dormant_unknown + ')', type: 'bar', stack: 'h',
       data: col(function (w) { return split(w) ? null : w.total; }), itemStyle: {color: ctx.th.neutral},
       label: {show: true, color: ctx.th.fg, position: 'inside'}}];
    return {option: o, note: T.wip_hist_note};
  }

  // ---- 6. lead time de livraison et efficacité de flux
  function buildLeadTimes(view, ctx) {
    var T = ctx.T, d = view && view.delivery;
    if (!d || !d.commitment) return empty(T.eff_missing);
    var keys = [50, 70, 85, 95], names = [T.p50, T.p70, T.p85, T.p95];
    function bar(name, src, color) {
      return {name: name, type: 'bar', data: keys.map(function (k) { return src ? src[k] : null; }), itemStyle: {color: color},
              label: {show: true, position: 'top', color: ctx.th.fg, formatter: function (p) { return p.value == null ? '' : ctx.days(p.value); }}};
    }
    var o = base(ctx);
    o.tooltip.trigger = 'axis'; o.tooltip.axisPointer = {type: 'shadow'};
    o.xAxis = merge({type: 'category', data: names}, {axisLine: axisStyle(ctx).axisLine, axisLabel: {color: ctx.th.fg}});
    o.yAxis = yAxis(ctx, T.days);
    o.series = [bar(T.lt_from_commitment, d.commitment, ctx.th.colors[0]), bar(T.lt_from_creation, d.creation, ctx.th.colors[1])];
    o.legend.top = 0;
    o.grid.top = 70;
    return {option: o, note: ctx.fmt(T.delivered_n, {n: d.n})};
  }
  function buildEfficiency(view, ctx) {
    var T = ctx.T, e = view && view.efficiency;
    if (!e) return empty(T.eff_missing);
    var o = base(ctx);
    o.tooltip.trigger = 'item';
    o.legend = {show: false};
    o.xAxis = merge({type: 'value', min: 0, max: 1, axisLabel: {color: ctx.th.muted, formatter: function (v) { return Math.round(v * 100) + '%'; }}},
                    {axisLine: axisStyle(ctx).axisLine, splitLine: axisStyle(ctx).splitLine});
    o.yAxis = {type: 'category', data: [T.flow_eff_median, T.flow_eff_aggregate], axisLabel: {color: ctx.th.fg},
               axisLine: axisStyle(ctx).axisLine};
    o.series = [{type: 'bar', barWidth: 34, data: [e.p50, e.aggregate], itemStyle: {color: ctx.th.colors[2]},
                 label: {show: true, position: 'right', color: ctx.th.fg, formatter: function (p) { return ctx.pct(p.value); }}}];
    o.grid.top = 20;
    var cov = view.coverage, lines = [];
    if (cov && cov.share != null) {
      lines.push(T.coverage + ': ' + ctx.pct(cov.share) + ' (' + cov.with + '/' + cov.total + ')');
      if (cov.share < 0.9) lines.push(T.coverage_low);
    }
    return {option: o, note: lines.join(' '), lowCoverage: cov && cov.share != null && cov.share < 0.9};
  }

  // ---- 7. carte des dépendances (graphe interactif)
  function buildGraph(dep, team, ctx) {
    var T = ctx.T;
    if (!dep || !dep.nodes || !dep.nodes.length) return empty(T.graph_missing);
    var max = Math.max.apply(null, dep.nodes.map(function (n) { return n.tickets || 0; }).concat([1]));
    var nodes = dep.nodes.map(function (n) {
      var sel = team && n.name === team;
      return {name: n.name, symbolSize: 24 + 34 * Math.sqrt((n.tickets || 0) / max), value: n.tickets,
              itemStyle: {color: ctx.th.colors[0], borderColor: ctx.th.fg, borderWidth: sel ? 4 : 1, opacity: team && !sel ? 0.55 : 1},
              label: {show: true, color: ctx.th.fg, fontWeight: sel ? 'bold' : 'normal'}};
    });
    var links = dep.edges.filter(function (e) { return e.all > 0; }).map(function (e) {
      var open = e.open > 0;
      return {source: e.from, target: e.to, value: e.open,
              lineStyle: {width: open ? 1.5 + 1.6 * Math.sqrt(e.open) : 1.2, type: open ? 'solid' : 'dashed',
                          color: open ? ctx.th.colors[3] : ctx.th.neutral, curveness: 0.18, opacity: 0.9},
              label: {show: true, color: ctx.th.fg, formatter: String(e.open), fontSize: 12, fontWeight: 'bold'}};
    });
    var o = base(ctx);
    o.legend = {show: false};
    o.tooltip = merge(o.tooltip, {trigger: 'item', formatter: function (p) {
      if (p.dataType === 'edge') {
        var e = dep.edges.filter(function (x) { return x.from === p.data.source && x.to === p.data.target; })[0] || {};
        var rows = [esc(p.data.source) + ' → ' + esc(p.data.target), T.graph_open + ': ' + (e.open || 0),
                    T.graph_unknown + ': ' + (e.unknown || 0), T.graph_all + ': ' + (e.all || 0)];
        if (e.epics) rows.push(T.graph_epics + ': ' + e.epics);
        if (e.age) rows.push(T.graph_age + ': ' + ctx.num(e.age[50] != null ? e.age[50] : e.age.p50, 0) + ' / ' + ctx.num(e.age[85] != null ? e.age[85] : e.age.p85, 0));
        return rows.join('<br>');
      }
      return esc(p.name) + '<br>' + (p.value || 0) + ' ' + T.graph_tickets;
    }});
    o.series = [{type: 'graph', layout: 'force', roam: true, draggable: true, data: nodes, links: links,
                 edgeSymbol: ['none', 'arrow'], edgeSymbolSize: [0, 9], force: {repulsion: 1100, edgeLength: [150, 300], gravity: 0.05},
                 emphasis: {focus: 'adjacency'}, labelLayout: {hideOverlap: false}, label: {position: 'bottom'}}];
    o.grid = undefined;
    var notes = [];
    if (dep.truncated) notes.push(T.graph_truncated);
    if (dep.oriented === false) notes.push(T.graph_unoriented);
    return {option: o, notes: notes};
  }

  // ---- 8. évolution depuis la base
  var BASE_METRICS = [
    ['m_departures', function (s) { return s.departures_avg; }, 1], ['m_arrivals', function (s) { return s.arrivals_avg; }, 1],
    ['m_lead85', function (s) { return s.lead_p85; }, 0, true], ['m_wip', function (s) { return s.wip ? s.wip.total : null; }, 0],
    ['m_wip_active', function (s) { return s.wip ? s.wip.active : null; }, 0], ['m_wip_waiting', function (s) { return s.wip ? s.wip.waiting : null; }, 0],
    ['m_wip_dormant', function (s) { return s.wip ? s.wip.dormant : null; }, 0],
    ['m_delivery85', function (s) { return s.delivery_p85; }, 0, true],
    ['m_efficiency', function (s) { return s.efficiency; }, 0, false, true]
  ];
  function baselineRows(view, ctx) {
    var T = ctx.T, b = view && view.base, h = view && view.history || [], last = h.length ? h[h.length - 1] : null;
    if (!b || !last) return null;
    return BASE_METRICS.map(function (m) {
      var v0 = m[1](b), v1 = m[1](last), unit = m[3] ? ' ' + T.unit_day : '';
      var show = function (v) { return v == null ? T.nd : (m[4] ? ctx.pct(v) : ctx.num(v, m[2]) + unit); };
      var change = T.nd, sign = '';
      if (v0 != null && v1 != null) {
        var diff = v1 - v0;
        sign = Math.abs(diff) < 1e-9 ? '=' : diff > 0 ? '▲' : '▼';
        var word = sign === '=' ? T.base_same : diff > 0 ? T.base_higher : T.base_lower;
        var rel = v0 !== 0 ? ' (' + (diff > 0 ? '+' : '') + ctx.num(100 * diff / v0, 0) + '%)' : '';
        change = sign + ' ' + word + rel;
      }
      return {label: T[m[0]], base: show(v0), now: show(v1), change: change};
    });
  }
  function buildBaselineLine(view, ctx, key, title, unit) {
    var T = ctx.T, b = view && view.base, h = (view && view.history || []).filter(function (e) { return b && e.date >= b.date; });
    var f = key === 'lead' ? function (s) { return s.lead_p85; } : function (s) { return s.wip ? s.wip.total : null; };
    var pts = h.map(function (e) { return f(e); });
    if (!pts.some(function (v) { return v != null; }) || h.length < 2) return empty(T.no_data);
    var o = base(ctx);
    o.tooltip.trigger = 'axis';
    o.legend = {show: false};
    o.title = {text: title, left: 0, top: 0, textStyle: {color: ctx.th.fg, fontSize: 13, fontWeight: 600}};
    o.xAxis = merge({type: 'category', data: h.map(function (e) { return e.date; })}, {axisLine: axisStyle(ctx).axisLine, axisLabel: {color: ctx.th.fg}});
    o.yAxis = yAxis(ctx, unit);
    o.series = [{name: title, type: 'line', data: pts, symbol: 'circle', symbolSize: 8, lineStyle: {width: 2.4},
                 itemStyle: {color: ctx.th.colors[0]}, label: {show: true, color: ctx.th.fg, position: 'top',
                 formatter: function (p) { return p.value == null ? '' : ctx.num(p.value, 0); }},
                 markLine: {silent: true, symbol: 'none', lineStyle: {color: ctx.th.neutral, type: 'dashed'},
                            label: {color: ctx.th.muted, formatter: T.baseline}, data: [{xAxis: b.date}]}}];
    return {option: o};
  }

  var api = {PALETTES: PALETTES, Ctx: Ctx, esc: esc, md: md, buildFlow: buildFlow, buildCfd: buildCfd,
             buildSegments: buildSegments, buildAging: buildAging, buildWip: buildWip, buildWipHistory: buildWipHistory,
             buildLeadTimes: buildLeadTimes, buildEfficiency: buildEfficiency, buildGraph: buildGraph,
             baselineRows: baselineRows, buildBaselineLine: buildBaselineLine, jitter: jitter};
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; return; }

  // ---------------------------------------------------------------------------------------------
  // Page (navigateur seulement)
  // ---------------------------------------------------------------------------------------------
  var data = JSON.parse(document.getElementById('tf-data').textContent);
  var T = data.texts;
  var state = {series: 0, team: '', agingMode: 'status', depKind: 0, printing: false, theme: ''};
  var charts = [];
  var app = document.getElementById('app');
  // la vue (série, équipe, mode de l'Aging WIP) se lit dans l'adresse (#s=0&t=Équipe&a=segment) et s'y écrit : un lien
  // montre la même vue
  (function () {
    var hash = (root.location && root.location.hash || '').replace(/^#/, '');
    hash.split('&').forEach(function (kv) {
      var p = kv.split('='), k = p[0], v = decodeURIComponent(p.slice(1).join('=') || '');
      if (k === 's' && +v >= 0 && +v < data.series.length) state.series = +v;
      if (k === 't') state.team = v;
      if (k === 'a' && (v === 'segment' || v === 'status')) state.agingMode = v;
      if (k === 'd') state.depKind = +v || 0;
      if (k === 'th' && (v === 'dark' || v === 'light')) state.theme = v;
    });
    var s = data.series[state.series];
    if (s && state.team && s.teams.indexOf(state.team) < 0) state.team = '';
  })();
  function writeHash() {
    if (!root.history || !root.history.replaceState) return;
    try {
      root.history.replaceState(null, '', '#s=' + state.series + '&t=' + encodeURIComponent(state.team) + '&a=' + state.agingMode + '&d=' + state.depKind + (state.theme ? '&th=' + state.theme : ''));
    } catch (e) { /* page ouverte depuis un fichier restreint : sans effet */ }
  }

  function h(tag, attrs, html) {
    var e = document.createElement(tag);
    for (var k in (attrs || {})) { if (k === 'class') e.className = attrs[k]; else e.setAttribute(k, attrs[k]); }
    if (html != null) e.innerHTML = html;
    return e;
  }
  function isDark() {
    if (state.printing) return false;
    if (state.theme) return state.theme === 'dark';
    return !!(root.matchMedia && root.matchMedia('(prefers-color-scheme: dark)').matches);
  }
  function ctxNow() { return new Ctx(data, isDark()); }
  function how(ids) {
    var d = h('details', {class: 'how'}, '<summary>' + esc(T.how_to_read) + '</summary>');
    ids.forEach(function (id) { d.appendChild(h('p', {}, md(data.glossary[id] || ''))); });
    return d;
  }
  function panel(id, titleKey, readKey) {
    var s = h('section', {class: 'panel', id: id, 'aria-labelledby': id + '-t'}, '<h2 id="' + id + '-t">' + esc(T[titleKey]) + '</h2>');
    return s;
  }
  // largeur et hauteur d'impression (A4 paysage, marges de 12 mm) : à l'impression, la page est dessinée à ces tailles,
  // car la mise en page de l'impression n'est pas encore connue quand l'événement beforeprint se déclenche
  var PRINT_HEIGHT = {'': 300, tall: 360, small: 260};
  function chartIn(section, cls, label, half) {
    var div = h('div', {class: 'chart ' + (cls || ''), role: 'img', 'aria-label': label});
    div.printWidth = half ? 480 : 1000; div.printHeight = PRINT_HEIGHT[cls || ''];
    section.appendChild(div);
    return div;
  }
  function draw(div, built) {
    if (built.empty) { div.className = 'empty'; div.style.height = 'auto'; div.textContent = built.empty; return null; }
    var opts = {renderer: 'svg'};
    if (state.printing) { opts.width = div.printWidth; opts.height = div.printHeight; }
    var c = root.echarts.init(div, null, opts);
    c.setOption(built.option);
    charts.push(c);
    return c;
  }
  function note(section, text, warn) { if (text) section.appendChild(h('p', {class: warn ? 'warn' : 'note'}, esc(text))); }

  function render() {
    writeHash();
    if (state.theme) document.documentElement.setAttribute('data-theme', state.theme);
    if (state.printing) document.documentElement.setAttribute('data-theme', 'light');
    charts.forEach(function (c) { c.dispose(); }); charts = [];
    var ctx = ctxNow();
    app.innerHTML = '';
    var wrap = h('div', {class: 'wrap'});
    app.appendChild(wrap);
    var top = h('header', {class: 'top'}, '<h1>' + esc(T.title) + (data.anonymous ? ' · ' + esc(T.anonymous) : '') + '</h1>');
    wrap.appendChild(top);
    if (!data.series.length) {
      wrap.appendChild(h('div', {class: 'empty'}, esc(T.empty_page)));
      return;
    }
    var s = data.series[state.series];
    var controls = h('div', {class: 'controls'});
    var selS = h('select', {id: 'sel-series'});
    data.series.forEach(function (x, i) { selS.appendChild(h('option', {value: i}, esc(x.name))); });
    selS.value = state.series;
    selS.onchange = function () { state.series = +selS.value; state.team = ''; render(); };
    controls.appendChild(h('label', {class: 'noprint'}, esc(T.series))); controls.lastChild.appendChild(selS);
    var selT = h('select', {id: 'sel-team'});
    selT.appendChild(h('option', {value: ''}, esc(T.all_teams)));
    s.teams.forEach(function (t) { selT.appendChild(h('option', {value: t}, esc(t))); });
    selT.value = state.team;
    selT.onchange = function () { state.team = selT.value; render(); };
    controls.appendChild(h('label', {class: 'noprint'}, esc(T.team))); controls.lastChild.appendChild(selT);
    var pb = h('button', {type: 'button', class: 'noprint'}, esc(T.print));
    pb.onclick = function () { root.print(); };
    controls.appendChild(pb);
    top.appendChild(controls);
    var scope = s.scope === 'all' ? T.all_projects : (s.scope || []).join(', ');
    top.appendChild(h('p', {class: 'meta'}, esc(T.series) + ': <strong>' + esc(s.name) + '</strong> · ' + esc(T.team) + ': <strong>' +
      esc(state.team || T.all_teams) + '</strong> · ' + esc(T.latest_report) + ': ' + esc(s.date) + ' · ' + esc(T.period) + ': ' +
      esc(s.period ? s.period[0] + ' → ' + s.period[1] : T.nd) + (s.weeks_n ? ' (' + s.weeks_n + ' ' + esc(T.weeks) + ')' : '') +
      ' · ' + esc(T.scope) + ': ' + esc(scope) + ' · ' + esc(T.generated) + ': ' + esc(data.generated)));
    top.appendChild(h('p', {class: 'note'}, esc(T.teams_note)));
    var view = s.views[state.team] || s.views[''];

    function guard(fn, sec) {
      try { fn(sec); } catch (e) { sec.appendChild(h('p', {class: 'warn'}, esc(T.error_section))); }
    }
    var sec;
    sec = panel('flow', 'sec_flow'); wrap.appendChild(sec);
    guard(function (el) { var b = buildFlow(view, ctx); draw(chartIn(el, '', T.sec_flow), b); note(el, b.note); el.appendChild(how(data.reading.flow)); }, sec);

    sec = panel('cfd', 'sec_cfd'); wrap.appendChild(sec);
    guard(function (el) { var b = buildCfd(view, ctx, s.segment_order, s.segment_labels); draw(chartIn(el, 'tall', T.sec_cfd), b); note(el, b.note); el.appendChild(how(data.reading.cfd)); }, sec);

    sec = panel('segments', 'sec_segments'); wrap.appendChild(sec);
    guard(function (el) { var b = buildSegments(view, ctx, s.segment_labels); draw(chartIn(el, 'small', T.sec_segments), b); note(el, b.note); el.appendChild(how(data.reading.segments)); }, sec);

    sec = panel('aging', 'sec_aging'); wrap.appendChild(sec);
    guard(function (el) {
      var seg = h('div', {class: 'segmented noprint', role: 'group', 'aria-label': T.sec_aging});
      [['status', T.aging_by_status], ['segment', T.aging_by_segment]].forEach(function (m) {
        var b = h('button', {type: 'button', 'aria-pressed': String(state.agingMode === m[0])}, esc(m[1]));
        b.onclick = function () { state.agingMode = m[0]; render(); };
        seg.appendChild(b);
      });
      el.appendChild(seg);
      var shapes = h('div', {class: 'legend-shapes'}, '<span>● ' + esc(T.nature_active) + '</span><span>▲ ' + esc(T.nature_waiting) +
        '</span><span>◇ ' + esc(T.nature_dormant) + '</span>');
      el.appendChild(shapes);
      var b = buildAging(s.points, state.team, state.agingMode, view, ctx, s.segment_labels);
      draw(chartIn(el, 'tall', T.sec_aging), b); note(el, b.note); el.appendChild(how(data.reading.aging));
    }, sec);

    sec = panel('wip', 'sec_wip'); wrap.appendChild(sec);
    guard(function (el) {
      var pair = h('div', {class: 'pair'}); el.appendChild(pair);
      var b1 = buildWip(view, ctx), b2 = buildWipHistory(view, ctx);
      var d1 = h('div'); var d2 = h('div'); pair.appendChild(d1); pair.appendChild(d2);
      d1.appendChild(h('h3', {}, esc(T.wip_now))); draw(chartIn(d1, 'small', T.wip_now, true), b1); note(d1, b1.note);
      d2.appendChild(h('h3', {}, esc(T.wip_history))); draw(chartIn(d2, 'small', T.wip_history, true), b2); note(d2, b2.note);
      el.appendChild(how(data.reading.wip));
    }, sec);

    sec = panel('efficiency', 'sec_efficiency'); wrap.appendChild(sec);
    guard(function (el) {
      var pair = h('div', {class: 'pair'}); el.appendChild(pair);
      var b1 = buildLeadTimes(view, ctx), b2 = buildEfficiency(view, ctx);
      var d1 = h('div'); var d2 = h('div'); pair.appendChild(d1); pair.appendChild(d2);
      draw(chartIn(d1, 'small', T.lt_from_commitment, true), b1); note(d1, b1.note);
      draw(chartIn(d2, 'small', T.flow_eff_aggregate, true), b2); note(d2, b2.note, b2.lowCoverage);
      if (s.commitment) note(el, ctx.fmt(T.commitment_note, {s: segLabel(s.commitment, s.segment_labels)}));
      el.appendChild(how(data.reading.efficiency));
    }, sec);

    sec = panel('deps', 'sec_deps'); wrap.appendChild(sec);
    guard(function (el) {
      var deps = s.dependencies || [];
      if (!deps.length) { el.appendChild(h('div', {class: 'empty'}, esc(T.graph_missing))); el.appendChild(how(data.reading.deps)); return; }
      if (deps.length > 1) {
        var seg = h('div', {class: 'segmented noprint', role: 'group', 'aria-label': T.sec_deps});
        deps.forEach(function (d, i) {
          var b = h('button', {type: 'button', 'aria-pressed': String(state.depKind === i)}, esc(d.kind === 'project' ? T.graph_by_project : T.graph_by_team));
          b.onclick = function () { state.depKind = i; render(); };
          seg.appendChild(b);
        });
        el.appendChild(seg);
      }
      var dep = deps[Math.min(state.depKind, deps.length - 1)];
      el.appendChild(h('p', {class: 'note'}, esc(T.graph_date) + ' ' + esc(dep.date)));
      var b = buildGraph(dep, state.team, ctx);
      b.notes && b.notes.forEach(function (n) { note(el, n, true); });
      draw(chartIn(el, 'tall', T.sec_deps), b);
      if (!b.empty) {
        var rows = dep.edges.filter(function (e) { return e.all > 0; }).map(function (e) {
          return '<tr><td>' + esc(e.from) + '</td><td>' + esc(e.to) + '</td><td class="num">' + e.open + '</td><td class="num">' + e.unknown +
                 '</td><td class="num">' + e.all + '</td></tr>';
        }).join('');
        var det = h('details', {class: 'how'}, '<summary>' + esc(T.graph_table) + '</summary>');
        det.appendChild(h('table', {class: 'data'}, '<thead><tr><th>' + esc(T.graph_team) + '</th><th>' + esc(T.graph_from) +
          '</th><th class="num">' + esc(T.graph_open) + '</th><th class="num">' + esc(T.graph_unknown) + '</th><th class="num">' +
          esc(T.graph_all) + '</th></tr></thead><tbody>' + rows + '</tbody>'));
        el.appendChild(det);
        el.appendChild(h('p', {class: 'note'}, esc(T.graph_loops) + ': ' + (dep.loops.length ? esc(dep.loops.map(function (l) { return l.join(' → '); }).join(' ; ')) : esc(T.graph_none))));
      }
      el.appendChild(how(data.reading.deps));
    }, sec);

    if (s.baseline) {
      sec = panel('base', 'sec_base'); wrap.appendChild(sec);
      guard(function (el) {
        el.appendChild(h('p', {class: 'note'}, esc(T.baseline) + ': ' + esc(s.baseline.date)));
        if (!s.baseline.found) { el.appendChild(h('div', {class: 'empty'}, esc(T.base_missing))); }
        else {
          if (s.baseline.differences.length) note(el, ctx.fmt(T.base_not_comparable, {d: s.baseline.differences.join(', ')}), true);
          var rows = baselineRows(view, ctx);
          if (rows) {
            el.appendChild(h('table', {class: 'data'}, '<thead><tr><th>' + esc(T.base_metric) + '</th><th class="num">' + esc(T.base_value) +
              ' (' + esc(s.baseline.date) + ')</th><th class="num">' + esc(T.base_now) + ' (' + esc(s.date) + ')</th><th>' + esc(T.base_change) +
              '</th></tr></thead><tbody>' + rows.map(function (r) {
                return '<tr><td>' + esc(r.label) + '</td><td class="num">' + esc(r.base) + '</td><td class="num">' + esc(r.now) +
                       '</td><td>' + esc(r.change) + '</td></tr>';
              }).join('') + '</tbody>'));
          }
          var pair = h('div', {class: 'pair'}); el.appendChild(pair);
          var l1 = h('div'), l2 = h('div'); pair.appendChild(l1); pair.appendChild(l2);
          draw(chartIn(l1, 'small', T.m_lead85, true), buildBaselineLine(view, ctx, 'lead', T.m_lead85, T.unit_day));
          draw(chartIn(l2, 'small', T.m_wip, true), buildBaselineLine(view, ctx, 'wip', T.m_wip, T.unit_items));
        }
        el.appendChild(how(data.reading.base));
      }, sec);
    }
  }

  function resizeAll() { charts.forEach(function (c) { c.resize(); }); }
  root.addEventListener('resize', resizeAll);
  root.addEventListener('beforeprint', function () {
    state.printing = true; render();
    Array.prototype.forEach.call(document.querySelectorAll('details'), function (d) { d.open = true; });
  });
  root.addEventListener('afterprint', function () { state.printing = false; render(); });
  if (root.matchMedia) {
    var mq = root.matchMedia('(prefers-color-scheme: dark)');
    var again = function () { if (!state.printing) render(); };
    if (mq.addEventListener) mq.addEventListener('change', again); else if (mq.addListener) mq.addListener(again);
  }
  render();
})(typeof window !== 'undefined' ? window : globalThis);
