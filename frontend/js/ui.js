// Small DOM + chart helpers shared by the views.

import { tokens } from './theme.js';

const charts = new Map(); // element id -> { chart, build }
let resizeObs = null;

/** Mount (or update) an ECharts instance. `build(t)` returns the option for the current theme. */
export function mountChart(el, build) {
  if (!el) return null;
  let entry = charts.get(el.id);
  if (entry && entry.chart.getDom() !== el) {
    entry.chart.dispose();
    entry = null;
  }
  if (!entry) {
    const chart = echarts.init(el, null, { renderer: 'canvas' });
    entry = { chart, build };
    charts.set(el.id, entry);
    resizeObserver().observe(el);
  }
  entry.build = build;
  entry.chart.setOption(build(tokens()), true);
  return entry.chart;
}

export function disposeCharts() {
  for (const { chart } of charts.values()) chart.dispose();
  charts.clear();
  resizeObs?.disconnect();
  resizeObs = null;
}

export function rethemeCharts() {
  const t = tokens();
  for (const entry of charts.values()) entry.chart.setOption(entry.build(t), true);
}

function resizeObserver() {
  if (!resizeObs) {
    resizeObs = new ResizeObserver((entries) => {
      for (const e of entries) {
        const entry = charts.get(e.target.id);
        entry?.chart.resize();
      }
    });
  }
  return resizeObs;
}

export function h(html) {
  const tpl = document.createElement('template');
  tpl.innerHTML = html.trim();
  return tpl.content;
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function statTile(label, value, sub = '', cls = '') {
  return `<div class="stat"><span class="stat-label">${label}</span><span class="stat-value ${cls}">${value}</span><span class="stat-sub">${sub}</span></div>`;
}

export function seg(name, options, current) {
  return `<div class="seg" role="group" data-seg="${name}">${options
    .map(([v, label]) => `<button type="button" data-value="${v}" aria-pressed="${String(v) === String(current)}">${label}</button>`)
    .join('')}</div>`;
}

/** Simple sortable table: columns [{key,label,num,fmt,cls}] */
export function sortableTable(el, columns, rows, { sortKey, desc = true, rowClass = () => '', onRow } = {}) {
  let key = sortKey ?? columns[0].key;
  let down = desc;
  const render = () => {
    const sorted = [...rows].sort((a, b) => {
      const va = a[key], vb = b[key];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const c = typeof va === 'string' ? va.localeCompare(vb, 'sv') : va - vb;
      return down ? -c : c;
    });
    el.innerHTML = `<table class="data"><thead><tr>${columns
      .map((c) => `<th class="sortable ${c.num ? 'num' : ''}" data-key="${c.key}" aria-sort="${c.key === key ? (down ? 'descending' : 'ascending') : 'none'}">${c.label}${c.key === key ? (down ? ' ↓' : ' ↑') : ''}</th>`)
      .join('')}</tr></thead><tbody>${sorted
      .map((r) => `<tr class="${rowClass(r)}" data-id="${r.id ?? ''}">${columns
        .map((c) => `<td class="${c.num ? 'num' : ''} ${c.cls ? c.cls(r) : ''}">${c.fmt ? c.fmt(r[c.key], r) : r[c.key] ?? '–'}</td>`)
        .join('')}</tr>`)
      .join('')}</tbody></table>`;
    el.querySelectorAll('th.sortable').forEach((th) =>
      th.addEventListener('click', () => {
        if (key === th.dataset.key) down = !down;
        else { key = th.dataset.key; down = true; }
        render();
      }),
    );
    if (onRow) el.querySelectorAll('tbody tr').forEach((tr) => tr.addEventListener('click', (ev) => onRow(tr.dataset.id, ev)));
  };
  render();
}
