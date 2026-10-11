// Pilote de test Node : exécute la page du tableau de bord (tools/flow_board_page.js) dans un faux DOM, avec un faux
// ECharts qui enregistre les options reçues, puis simule les choix de l'utilisateur (série, équipe, mode de l'Aging WIP,
// impression). Sortie JSON : options enregistrées, erreurs, texte visible. Usage : node driver.js <page.js> <donnees.json>
const fs = require('fs');
const vm = require('vm');

const [,, pageJs, donneesJson] = process.argv;
const data = fs.readFileSync(donneesJson, 'utf8');

function el(tag) {
  const e = {tag, children: [], attrs: {}, style: {}, className: '', _html: '', _text: '', onclick: null, onchange: null, value: '',
    appendChild(c) { this.children.push(c); this.lastChild = c; return c; },
    setAttribute(k, v) { this.attrs[k] = v; if (k === 'value') this.value = v; },
    querySelectorAll() { return []; }};
  Object.defineProperty(e, 'innerHTML', {get() { return this._html; }, set(v) { this._html = v; this.children = []; }});
  Object.defineProperty(e, 'textContent', {get() { return this._text; }, set(v) { this._text = v; }});
  return e;
}
const app = el('div');
const dataEl = el('script'); dataEl._text = data;
const doc = {documentElement: el('html'), createElement: el, getElementById: (id) => (id === 'tf-data' ? dataEl : id === 'app' ? app : null),
             querySelectorAll: () => []};
const recorded = [], listeners = {};
const win = {
  echarts: {init: () => { let last = null; return {setOption(o) { last = o; recorded.push(o); }, dispose() {}, resize() {}}; }},
  matchMedia: () => ({matches: false, addEventListener() {}}),
  addEventListener: (n, f) => { listeners[n] = f; }, print() {}
};
const errors = [];
const sandbox = {window: win, document: doc, console, JSON, Math, Object, Array, String, Number, isNaN, parseInt, parseFloat};
vm.createContext(sandbox);
try { vm.runInContext(fs.readFileSync(pageJs, 'utf8'), sandbox, {filename: 'page.js'}); } catch (e) { errors.push('load: ' + e.stack); }

function walk(e, f) { f(e); (e.children || []).forEach((c) => walk(c, f)); }
function findById(id) { let found = null; walk(app, (n) => { if (n.attrs && n.attrs.id === id) found = n; }); return found; }
function buttons() { const out = []; walk(app, (n) => { if (n.tag === 'button') out.push(n); }); return out; }
function visibleText() { const out = []; walk(app, (n) => { if (n._html) out.push(n._html); if (n._text) out.push(n._text); }); return out.join('\n'); }
function strings(o, out) {
  if (typeof o === 'string') out.push(o);
  else if (Array.isArray(o)) o.forEach((x) => strings(x, out));
  else if (o && typeof o === 'object') Object.values(o).forEach((x) => strings(x, out));
  return out;
}
function snapshot(label) {
  return {label, charts: recorded.length, text: visibleText(), optionStrings: recorded.flatMap((o) => strings(o, []))};
}
const steps = [];
function step(label, fn, keep) {
  if (!keep) recorded.length = 0;
  try { fn(); } catch (e) { errors.push(label + ': ' + e.stack); }
  steps.push(snapshot(label));
}
const parsed = JSON.parse(data);
step('initial', () => {}, true);
const selTeam = findById('sel-team'), selSeries = findById('sel-series');
(parsed.series[0] ? parsed.series[0].teams : []).forEach((team) => {
  step('team ' + team, () => { findById('sel-team').value = team; findById('sel-team').onchange(); });
});
step('all teams', () => { if (findById('sel-team')) { findById('sel-team').value = ''; findById('sel-team').onchange(); } });
step('aging by segment', () => { const b = buttons().filter((x) => /segment/i.test(x._html) || /Segment/.test(x._html))[0]; if (b) b.onclick(); });
step('aging by status', () => { const b = buttons().filter((x) => /status|état/i.test(x._html))[0]; if (b) b.onclick(); });
if (parsed.series.length > 1) step('series 2', () => { findById('sel-series').value = '1'; findById('sel-series').onchange(); });
step('print', () => { listeners.beforeprint && listeners.beforeprint(); });
step('after print', () => { listeners.afterprint && listeners.afterprint(); });
if (process.argv[4] === 'options') {
  recorded.length = 0;
  if (findById('sel-team')) { findById('sel-team').value = ''; findById('sel-team').onchange(); }
  console.log(JSON.stringify({initialOptions: recorded.slice()}));
} else {
  console.log(JSON.stringify({errors, steps, hasTeamSelector: !!selTeam, hasSeriesSelector: !!selSeries}));
}
