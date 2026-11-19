// App state, routing (URL hash), navigation, filters and live prices.

import { api } from './api.js';
import { colorFor } from './charts.js';
import { esc, monthLabel, pct, signClass, timeLabel } from './format.js';
import { initTheme, tokens } from './theme.js';
import { $, $$, disposeCharts, rethemeCharts } from './ui.js';
import { BENCH_SHORT, drawBuyTable, renderCompare, renderFuture, renderHistory, renderHow, renderOverview, renderToday } from './views.js';

const TABS = [
  ['overview', 'Översikt'],
  ['how', 'Så fungerar den'],
  ['history', 'Så hade du investerat'],
  ['future', 'Framtid & osäkerhet'],
  ['today', 'Köp idag'],
];

const state = {
  list: null,
  route: { id: 'compare', tab: 'overview', params: {}, start: 'common' },
  detail: null,
  ui: {
    log: true,
    annualView: 'chart',
    benchmarks: new Set(['sp500', 'global', 'omxs30', 'ew_universe']),
    savings: { initial: 10000, monthly: 500 },
    amount: 10000,
    rebalDate: null,
  },
  live: { enabled: false, quotes: {} },
  liveTimer: null,
  loadSeq: 0,
};

// ---------------------------------------------------------------------------
// Routing: #/<id>?tab=..&start=..&<param>=..
// ---------------------------------------------------------------------------

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [id, query = ''] = raw.split('?');
  const q = new URLSearchParams(query);
  const params = {};
  for (const [k, v] of q) if (!['tab', 'start'].includes(k)) params[k] = v;
  return { id: id || 'compare', tab: q.get('tab') || 'overview', start: q.get('start') || 'common', params };
}

function writeHash(route) {
  const q = new URLSearchParams();
  if (route.id !== 'compare' && route.tab !== 'overview') q.set('tab', route.tab);
  if (route.start !== 'common') q.set('start', route.start);
  for (const [k, v] of Object.entries(route.params)) q.set(k, v);
  const s = q.toString();
  const next = `#/${route.id}${s ? `?${s}` : ''}`;
  if (location.hash !== next) history.replaceState(null, '', next);
}

function go(patch) {
  const prev = state.route;
  state.route = { ...prev, ...patch };
  if (patch.id && patch.id !== prev.id) {
    state.route.params = patch.params ?? {};
    state.ui.rebalDate = null;
  }
  writeHash(state.route);
  load();
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

function renderNav() {
  const { strategies, families } = state.list;
  const cur = state.route.id;
  const groups = families
    .map((fam) => {
      const items = strategies.filter((s) => s.family === fam);
      return `<div class="nav-group"><div class="nav-group-title">${esc(fam)}</div>${items
        .map((s) => {
          const h = s.headline;
          const cagr = h ? `<span class="nav-cagr ${signClass(h.cagr - h.sp500_cagr)}">${pct(h.cagr, 1)}</span>` : '<span class="nav-cagr muted">–</span>';
          return `<button class="nav-item" type="button" data-id="${s.id}" ${s.id === cur ? 'aria-current="page"' : ''}>
              <span class="nav-name">${esc(s.name)}</span>${cagr}
              <span class="nav-sub">${s.error ? esc(s.error) : esc(s.kind === 'allocation' ? 'ETF-allokering' : 'Aktier')}</span></button>`;
        })
        .join('')}</div>`;
    })
    .join('');
  $('#nav').innerHTML = `<div class="nav-group"><button class="nav-item" type="button" data-id="compare" ${cur === 'compare' ? 'aria-current="page"' : ''}>
      <span class="nav-name">Jämför alla strategier</span><span class="nav-cagr"></span><span class="nav-sub">Samma period, sida vid sida</span></button></div>${groups}`;
  $('#nav-note').innerHTML = `Siffran = årlig avkastning ${monthLabel(state.list.common_start)}–idag. Grön = bättre än S&amp;P 500 (${pct(state.list.strategies.find((s) => s.headline)?.headline.sp500_cagr, 1)}).`;
  $$('#nav .nav-item').forEach((b) =>
    b.addEventListener('click', () => {
      closeMenu();
      go({ id: b.dataset.id, tab: state.route.tab === 'overview' || b.dataset.id === 'compare' ? 'overview' : state.route.tab });
    }),
  );
}

// ---------------------------------------------------------------------------
// Header, filters, tabs
// ---------------------------------------------------------------------------

function startOptions(meta) {
  const common = state.list.common_start;
  const first = meta?.available_from ?? common;
  const lastYear = Number(state.list.data.last_price_date.slice(0, 4));
  const opts = [['common', `Gemensam period (${common.slice(0, 4)}–)`]];
  // The comparison view only offers periods every strategy covers.
  if (meta) opts.push(['full', `Hela historiken (${first.slice(0, 4)}–)`]);
  const from = Number((meta ? first : common).slice(0, 4)) + 1;
  for (let y = from; y <= lastYear - 3; y++) opts.push([`${y - 1}-12-31`, `Från ${y}`]);
  return opts;
}

function resolveStart(meta) {
  const s = state.route.start;
  if (s === 'common') return state.list.common_start;
  if (s === 'full') return null;
  return s;
}

function renderHeader(meta) {
  const title = $('#title');
  if (!meta) {
    title.innerHTML = `<span class="family">Översikt</span><h1>Jämför alla strategier</h1><p class="tagline">${state.list.strategies.length} strategier mot S&amp;P 500, globalindex och OMXS30. Välj en strategi till vänster för detaljer, förklaringar och dagens köplista.</p>`;
    return;
  }
  title.innerHTML = `<span class="family">${esc(meta.family)}</span><h1>${esc(meta.name)}</h1><p class="tagline">${esc(meta.tagline)}</p>`;
  document.title = `${meta.name} – Aktielabbet`;
}

function renderFilters(meta) {
  const el = $('#filters');
  const startSel = `<div class="field"><label for="f-start">Period</label><select id="f-start">${startOptions(meta)
    .map(([v, l]) => `<option value="${v}" ${v === state.route.start ? 'selected' : ''}>${l}</option>`)
    .join('')}</select></div>`;
  if (!meta) {
    el.innerHTML = startSel;
  } else {
    const p = state.detail?.params ?? {};
    const params = meta.params
      .filter((x) => x.options.length > 1)
      .map(
        (x) => `<div class="field" title="${esc(x.help)}"><label for="f-${x.key}">${esc(x.label)}</label><select id="f-${x.key}" data-param="${x.key}">${x.options
          .map((o, i) => `<option value="${o}" ${String(o) === String(p[x.key] ?? state.route.params[x.key] ?? x.default) ? 'selected' : ''}>${esc(x.labels[i])}</option>`)
          .join('')}</select></div>`,
      )
      .join('');
    const t = tokens();
    const benches = ['sp500', 'global', 'omxs30', ...(meta.kind === 'stocks' && meta.id !== 'ew_universe' ? ['ew_universe'] : [])];
    const checks = `<div class="field"><span class="label">Jämför med</span><div class="checks">${benches
      .map((k) => `<label class="check"><input type="checkbox" data-bench="${k}" ${state.ui.benchmarks.has(k) ? 'checked' : ''}><span class="swatch" style="background:${colorFor(k, t)}"></span>${BENCH_SHORT[k]}</label>`)
      .join('')}</div></div>`;
    el.innerHTML = params + startSel + (state.route.tab === 'overview' ? checks : '');
  }
  $('#f-start', el)?.addEventListener('change', (e) => go({ start: e.target.value }));
  $$('select[data-param]', el).forEach((s) =>
    s.addEventListener('change', () => go({ params: { ...state.route.params, [s.dataset.param]: s.value } })),
  );
  $$('input[data-bench]', el).forEach((c) =>
    c.addEventListener('change', () => {
      c.checked ? state.ui.benchmarks.add(c.dataset.bench) : state.ui.benchmarks.delete(c.dataset.bench);
      renderTab();
    }),
  );
}

function renderTabs(meta) {
  const el = $('#tabs');
  el.hidden = !meta;
  if (!meta) return;
  el.innerHTML = TABS.map(([k, l]) => `<button class="tab" role="tab" type="button" data-tab="${k}" aria-selected="${k === state.route.tab}">${l}</button>`).join('');
  $$('.tab', el).forEach((b) => b.addEventListener('click', () => {
    state.route.tab = b.dataset.tab;
    writeHash(state.route);
    renderTabs(meta);
    renderFilters(meta);
    renderTab();
  }));
}

// ---------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------

function showStatus(html) {
  const s = $('#status');
  s.innerHTML = html;
  s.hidden = !html;
}

async function load() {
  const seq = ++state.loadSeq;
  const { id } = state.route;
  const meta = state.list.strategies.find((s) => s.id === id) ?? null;
  renderNav();
  renderHeader(meta);
  renderTabs(meta);
  const view = $('#view');
  view.classList.add('is-refreshing');
  stopLive();

  try {
    if (!meta) {
      state.detail = null;
      renderFilters(null);
      showStatus('');
      const start = state.route.start === 'full' ? '' : resolveStart(null);
      const data = await api.compare(start);
      if (seq !== state.loadSeq) return;
      disposeCharts();
      renderCompare(view, data, (sid) => go({ id: sid, tab: 'overview' }));
    } else {
      renderFilters(meta);
      if (!state.detail || state.detail.strategy.id !== id) {
        showStatus(`<div class="spinner"></div>${meta.heavy ? 'Laddar modellen – första gången kan det ta en stund…' : 'Räknar…'}`);
      }
      const d = await api.strategy(id, state.route.params, resolveStart(meta));
      if (seq !== state.loadSeq) return;
      state.detail = d;
      showStatus('');
      renderFilters(meta);
      renderTab();
    }
  } catch (err) {
    if (seq !== state.loadSeq) return;
    disposeCharts();
    view.innerHTML = '';
    showStatus(`<b>Något gick fel.</b><br><span class="small">${esc(err.message)}</span>`);
  } finally {
    if (seq === state.loadSeq) view.classList.remove('is-refreshing');
  }
}

function renderTab() {
  const d = state.detail;
  if (!d) return;
  const view = $('#view');
  disposeCharts();
  stopLive();
  const tab = state.route.tab;
  if (tab === 'how') renderHow(view, d, state.list.general);
  else if (tab === 'history') renderHistory(view, d, state.ui, () => {});
  else if (tab === 'future') renderFuture(view, d);
  else if (tab === 'today') {
    renderToday(view, d, state.ui, state.live, () => {});
    startLive();
  } else {
    renderOverview(view, d, state.ui);
    view.querySelectorAll('[data-seg]').forEach((g) =>
      g.querySelectorAll('button').forEach((b) =>
        b.addEventListener('click', () => {
          if (g.dataset.seg === 'scale') state.ui.log = b.dataset.value === 'log';
          if (g.dataset.seg === 'annual-view') state.ui.annualView = b.dataset.value;
          renderTab();
        }),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Live prices (Alpaca via backend)
// ---------------------------------------------------------------------------

function stopLive() {
  clearInterval(state.liveTimer);
  state.liveTimer = null;
}

async function pollLive() {
  const d = state.detail;
  if (!d || state.route.tab !== 'today') return;
  const tickers = d.current.holdings.filter((h) => h.tradable).map((h) => h.ticker);
  const chip = $('#live-chip');
  try {
    const res = await api.live(tickers);
    state.live = res;
    if (!res.enabled) {
      if (chip) chip.innerHTML = '<span class="dot"></span><span>Stängningskurser (ingen Alpaca-nyckel)</span>';
      stopLive();
      return;
    }
    const prev = { ...(state.prevQuotes ?? {}) };
    drawBuyTable($('#view'), d, state.ui, res);
    // Highlight rows whose price moved.
    for (const [t, q] of Object.entries(res.quotes)) {
      if (prev[t] && prev[t].price !== q.price) $(`#buy-table tr[data-t="${CSS.escape(t)}"] .price`)?.classList.add('flash');
    }
    state.prevQuotes = res.quotes;
    if (chip) {
      chip.innerHTML = res.error
        ? `<span class="dot err"></span><span>${esc(res.error)}</span>`
        : `<span class="dot on"></span><span>Live · ${timeLabel(new Date().toISOString())}</span>`;
    }
  } catch (err) {
    if (chip) chip.innerHTML = `<span class="dot err"></span><span>Live-fel: ${esc(err.message)}</span>`;
  }
}

function startLive() {
  stopLive();
  pollLive();
  state.liveTimer = setInterval(pollLive, 15000);
}

async function refreshStatus() {
  try {
    const s = await api.status();
    const dc = $('#data-chip');
    dc.innerHTML = `<span class="dot on"></span><span>Data t.o.m. ${s.data.last_price_date} · ${s.data.stocks} aktier</span>`;
    const ac = $('#alpaca-chip');
    const a = s.alpaca;
    if (!a.enabled) {
      ac.innerHTML = '<span class="dot"></span><span>Alpaca ej kopplat</span>';
      ac.title = 'Lägg in ALPACA_API_KEY_ID och ALPACA_API_SECRET_KEY i .env och starta om servern.';
    } else if (!a.ok) {
      ac.innerHTML = '<span class="dot err"></span><span>Alpaca: fel</span>';
      ac.title = a.error;
    } else {
      ac.innerHTML = `<span class="dot ${a.market_open ? 'on' : ''}"></span><span>Alpaca paper · ${a.market_open ? 'börsen öppen' : 'börsen stängd'}</span>`;
      ac.title = `Paper-konto: $${Math.round(a.equity).toLocaleString('sv-SE')} · köpkraft $${Math.round(a.buying_power).toLocaleString('sv-SE')} · dataflöde ${a.feed}`;
    }
    state.live.enabled = a.enabled && a.ok !== false;
  } catch {
    /* status is decorative */
  }
}

// ---------------------------------------------------------------------------

function closeMenu() {
  $('#sidebar').classList.remove('open');
}

async function init() {
  initTheme($('#theme-toggle'), () => {
    rethemeCharts();
    if (state.detail || state.route.id === 'compare') renderFilters(state.list?.strategies.find((s) => s.id === state.route.id));
  });
  $('#menu-btn').addEventListener('click', () => $('#sidebar').classList.toggle('open'));
  $('#backdrop').addEventListener('click', closeMenu);

  showStatus('<div class="spinner"></div>Laddar strategier – första starten räknar alla backtester (ca 30–60 s)…');
  try {
    state.list = await api.strategies();
  } catch (err) {
    showStatus(`<b>Kunde inte ladda data.</b><br><span class="small">${esc(err.message)}</span>`);
    return;
  }
  showStatus('');
  state.route = parseHash();
  refreshStatus();
  setInterval(refreshStatus, 60000);
  window.addEventListener('hashchange', () => {
    const r = parseHash();
    if (JSON.stringify(r) !== JSON.stringify(state.route)) {
      state.route = r;
      load();
    }
  });
  load();
}

init();
