// Rendering of the strategy tabs and the comparison view.

import {
  allocationOption, colorFor, drawdownOption, fanOption, groupedBarsOption, growthOption, hBarsOption, histogramOption, savingsOption,
} from './charts.js';
import { byFormat, dateLabel, esc, isNum, monthLabel, num, pct, pp, ratio, signClass, usd, years } from './format.js';
import { $, $$, mountChart, seg, sortableTable, statTile } from './ui.js';

export const BENCH_SHORT = { sp500: 'S&P 500', global: 'Global', omxs30: 'OMXS30', ew_universe: 'Lika vikt' };
export const BENCH_LONG = { sp500: 'S&P 500', global: 'Globalindex (ACWI)', omxs30: 'OMXS30 (prisindex)', ew_universe: 'Lika vikt – universum' };
const ASSET_NAMES = { SPY: 'Aktier USA (SPY)', EFA: 'Aktier internationellt (EFA)', IEF: 'Statsobligationer (IEF)', AGG: 'Obligationer (AGG)', ACWI: 'Globala aktier (ACWI)', CASH: 'Kontanter' };

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------

export function renderOverview(root, d, ui) {
  const s = d.stats.strategy;
  const sp = d.stats.sp500;
  const final = d.series.strategy.at(-1);
  root.innerHTML = `
    <div class="stats">
      ${statTile('Årlig avkastning', pct(s.cagr), `S&P 500: ${pct(sp.cagr)}`, signClass(s.cagr))}
      ${statTile('Mot S&P 500 per år', pp(s.excess_cagr), `Alfa ${pct(s.alpha, 1, true)} · beta ${ratio(s.beta)}`, signClass(s.excess_cagr))}
      ${statTile('Total avkastning', pct(s.total_return, 0), `$10 000 → ${usd(final * 10000)} på ${years(s.months)}`)}
      ${statTile('Volatilitet', pct(s.volatility), `S&P 500: ${pct(sp.volatility)}`)}
      ${statTile('Sharpekvot', ratio(s.sharpe), `S&P 500: ${ratio(sp.sharpe)}`)}
      ${statTile('Största fall', pct(s.max_drawdown), `Botten ${monthLabel(s.max_drawdown_date)}`, 'neg')}
    </div>

    <section class="card">
      <div class="card-head">
        <div><h2>Så hade $10 000 vuxit</h2><div class="sub">${monthLabel(d.series.dates[0])} – ${monthLabel(d.series.dates.at(-1))}, utdelningar återinvesterade, efter kostnader</div></div>
        ${seg('scale', [['log', 'Logaritmisk'], ['lin', 'Linjär']], ui.log ? 'log' : 'lin')}
      </div>
      <div id="ch-growth" class="chart h-lg" role="img" aria-label="Värdeutveckling för strategin jämfört med index"></div>
      <p class="note">Logaritmisk skala visar procentuell förändring rättvist över tid: samma lutning = samma avkastning.
      ${d.strategy.kind === 'stocks' ? ' <b>Lika vikt</b> är den rättvisa jämförelsen för aktiestrategier (samma bolag och samma överlevnadsbias).' : ''}</p>
    </section>

    <div class="grid-2">
      <section class="card">
        <div class="card-head"><div><h2>Fall från toppen (drawdown)</h2><div class="sub">Hur långt under sin tidigare topp portföljen låg</div></div></div>
        <div id="ch-dd" class="chart h-md" role="img" aria-label="Drawdown"></div>
      </section>
      <section class="card">
        <div class="card-head"><div><h2>Avkastning per år</h2><div class="sub">Strategin jämfört med S&amp;P 500</div></div>
          ${seg('annual-view', [['chart', 'Diagram'], ['table', 'Tabell']], ui.annualView)}</div>
        <div id="ch-annual" class="chart h-md" role="img" aria-label="Årsavkastning" ${ui.annualView === 'table' ? 'hidden' : ''}></div>
        <div id="tb-annual" class="table-wrap scroll" ${ui.annualView === 'table' ? '' : 'hidden'} style="max-height:300px"></div>
      </section>
    </div>

    <section class="card">
      <div class="card-head"><div><h2>Nyckeltal</h2><div class="sub">Samma period för alla. Beta, alfa och försprång mäts mot S&amp;P 500.</div></div></div>
      <div id="tb-stats" class="table-wrap"></div>
    </section>`;

  const lines = [{ key: 'strategy', name: d.strategy.name, short: 'Strategin', data: d.series.strategy, main: true }];
  for (const k of ['sp500', 'global', 'omxs30']) {
    if (ui.benchmarks.has(k)) lines.push({ key: k, name: BENCH_LONG[k], short: BENCH_SHORT[k], data: d.series.benchmarks[k] });
  }
  if (d.series.ew_universe && ui.benchmarks.has('ew_universe')) {
    lines.push({ key: 'ew_universe', name: BENCH_LONG.ew_universe, short: BENCH_SHORT.ew_universe, data: d.series.ew_universe });
  }
  mountChart($('#ch-growth', root), (t) =>
    growthOption({ dates: d.series.dates, series: lines.map((l) => ({ ...l, color: colorFor(l.key, t) })), t, log: ui.log }),
  );
  mountChart($('#ch-dd', root), (t) =>
    drawdownOption({
      dates: d.series.dates,
      series: [
        { name: 'Strategin', data: d.series.drawdown.strategy, color: colorFor('strategy', t) },
        { name: 'S&P 500', data: d.series.drawdown.sp500, color: colorFor('sp500', t) },
      ],
      t,
    }),
  );
  mountChart($('#ch-annual', root), (t) =>
    groupedBarsOption({
      categories: d.annual.years.map(String),
      series: [
        { name: 'Strategin', data: d.annual.strategy, color: colorFor('strategy', t) },
        { name: 'S&P 500', data: d.annual.benchmarks.sp500, color: colorFor('sp500', t) },
      ],
      t,
    }),
  );
  $('#tb-annual', root).innerHTML = `<table class="data"><thead><tr><th>År</th><th class="num">Strategin</th><th class="num">S&amp;P 500</th><th class="num">Skillnad</th><th class="num">Global</th><th class="num">OMXS30</th></tr></thead><tbody>${d.annual.years
    .map((y, i) => {
      const a = d.annual.strategy[i], b = d.annual.benchmarks.sp500[i];
      return `<tr><td>${y}</td><td class="num ${signClass(a)}">${pct(a)}</td><td class="num">${pct(b)}</td><td class="num ${signClass(a - b)}">${isNum(a) && isNum(b) ? pp(a - b) : '–'}</td><td class="num">${pct(d.annual.benchmarks.global[i])}</td><td class="num">${pct(d.annual.benchmarks.omxs30[i])}</td></tr>`;
    })
    .reverse()
    .join('')}</tbody></table>`;

  renderStatsTable($('#tb-stats', root), d);
}

function renderStatsTable(el, d) {
  const cols = [['strategy', d.strategy.name], ['sp500', 'S&P 500'], ['global', 'Global'], ['omxs30', 'OMXS30']];
  if (d.stats.ew_universe) cols.push(['ew_universe', 'Lika vikt']);
  const rows = [
    ['Årlig avkastning (CAGR)', 'cagr', (v) => pct(v)],
    ['Total avkastning', 'total_return', (v) => pct(v, 0)],
    ['Volatilitet', 'volatility', (v) => pct(v)],
    ['Sharpekvot', 'sharpe', (v) => ratio(v)],
    ['Sortinokvot', 'sortino', (v) => ratio(v)],
    ['Största fall', 'max_drawdown', (v) => pct(v)],
    ['Calmar (CAGR / största fall)', 'calmar', (v) => ratio(v)],
    ['Bästa år', 'best_year', (v) => pct(v)],
    ['Sämsta år', 'worst_year', (v) => pct(v)],
    ['Sämsta månad', 'worst_month', (v) => pct(v)],
    ['Andel positiva månader', 'positive_months', (v) => pct(v, 0)],
    ['Beta mot S&P 500', 'beta', (v) => ratio(v)],
    ['Alfa per år', 'alpha', (v) => pct(v, 1, true)],
    ['Andel månader bättre än S&P 500', 'months_beating', (v) => pct(v, 0)],
    ['Tracking error', 'tracking_error', (v) => pct(v)],
  ];
  el.innerHTML = `<table class="data"><thead><tr><th>Nyckeltal</th>${cols.map(([, n]) => `<th class="num">${esc(n)}</th>`).join('')}</tr></thead><tbody>${rows
    .map(([label, key, f]) => `<tr><td>${label}</td>${cols.map(([c]) => `<td class="num">${d.stats[c]?.[key] != null ? f(d.stats[c][key]) : '–'}</td>`).join('')}</tr>`)
    .join('')}
    <tr><td>Omsättning per år</td><td class="num">${pct(d.stats.strategy.annual_turnover, 0)}</td>${cols.slice(1).map(() => '<td class="num">–</td>').join('')}</tr>
    </tbody></table>
    <p class="note">Perioden för index kan vara kortare om de startar senare (ACWI från 2008, OMXS30 från slutet av 2008).</p>`;
}

// ---------------------------------------------------------------------------
// How it works
// ---------------------------------------------------------------------------

export function renderHow(root, d, general) {
  const sections = d.doc.map((s) => `<section><h3>${esc(s.title)}</h3>${s.html}</section>`).join('');
  root.innerHTML = `
    <div class="doc">${sections}</div>
    ${d.diagnostics ? mlDiagnostics(d.diagnostics) : ''}
    <details class="general"><summary>Metod, data och begränsningar (gäller alla strategier)</summary>
      <div class="doc">${general.map((s) => `<section><h3>${esc(s.title)}</h3>${s.html}</section>`).join('')}</div>
    </details>`;
  if (d.diagnostics) {
    const g = d.diagnostics;
    const imp = g.importance;
    mountChart($('#ch-imp', root), (t) =>
      hBarsOption({ labels: imp.map((x) => x.label), values: imp.map((x) => x.value), t, fmt: (v) => num(v, 4), signed: true }),
    );
    const yrs = Object.keys(g.ic.yearly);
    mountChart($('#ch-ic', root), (t) =>
      groupedBarsOption({
        categories: yrs,
        series: [{ name: 'Genomsnittlig IC', data: yrs.map((y) => g.ic.yearly[y]), color: colorFor('strategy', t) }],
        t,
        fmt: (v) => num(v, 3),
      }),
    );
  }
}

function mlDiagnostics(g) {
  return `
  <section class="card">
    <div class="card-head"><div><h2>Inuti modellen</h2><div class="sub">${esc(g.model)} · ${g.n_models} modeller tränade walk-forward · ${num(g.n_rows)} observationer · senast tränad ${monthLabel(g.trained_until)}</div></div></div>
    <div class="grid-2">
      <div>
        <h3>Vilka variabler modellen använder</h3>
        <p class="note" style="margin:0 0 6px">${esc(g.importance_kind)}</p>
        <div id="ch-imp" class="chart" style="height:${Math.max(260, g.importance.length * 26)}px" role="img" aria-label="Variabelbetydelse"></div>
      </div>
      <div>
        <h3>Träffsäkerhet per år (IC)</h3>
        <dl class="kv" style="margin:6px 0 10px">
          <dt>Genomsnittlig IC</dt><dd>${num(g.ic.mean, 4)}</dd>
          <dt>Andel månader med positiv IC</dt><dd>${pct(g.ic.positive_share, 0)}</dd>
          <dt>t-värde</dt><dd>${num(g.ic.t_stat, 2)} ${Math.abs(g.ic.t_stat) >= 2 ? '(statistiskt signifikant)' : '(inte säkert skild från slump)'}</dd>
        </dl>
        <div id="ch-ic" class="chart h-md" role="img" aria-label="IC per år"></div>
      </div>
    </div>
  </section>`;
}

// ---------------------------------------------------------------------------
// How you would have invested
// ---------------------------------------------------------------------------

export function renderHistory(root, d, ui, onChange) {
  const reb = [...d.rebalances].reverse();
  const s = d.stats.strategy;
  const selected = reb.find((r) => r.date === ui.rebalDate) ?? reb[0];
  root.innerHTML = `
    <section class="card">
      <div class="card-head"><div><h2>Om du hade sparat i strategin</h2><div class="sub">Startbelopp plus månadssparande från ${monthLabel(d.series.dates[0])}, jämfört med att spara samma belopp i S&amp;P 500</div></div>
        <div class="checks">
          <div class="field"><label for="sv-initial">Startbelopp (USD)</label><input id="sv-initial" type="number" min="0" step="1000" value="${ui.savings.initial}"></div>
          <div class="field"><label for="sv-monthly">Per månad (USD)</label><input id="sv-monthly" type="number" min="0" step="100" value="${ui.savings.monthly}"></div>
        </div>
      </div>
      <div id="sv-tiles" class="stats" style="grid-template-columns:repeat(auto-fit,minmax(170px,1fr));margin-bottom:12px"></div>
      <div id="ch-savings" class="chart h-md" role="img" aria-label="Sparande över tid"></div>
    </section>

    ${d.allocation ? `<section class="card"><div class="card-head"><div><h2>Fördelning över tid</h2><div class="sub">Vad strategin ägde varje månad</div></div></div>
      <div id="ch-alloc" class="chart h-md" role="img" aria-label="Fördelning över tid"></div></section>` : ''}

    <section class="card">
      <div class="card-head">
        <div><h2>Varje ombalansering</h2><div class="sub">${num(s.rebalances)} tillfällen · i snitt ${pct(s.avg_turnover, 0)} av portföljen omsatt per gång · ${pct(s.annual_turnover, 0)} per år</div></div>
        <div class="field"><label for="rb-date">Välj datum</label>
          <select id="rb-date">${reb.map((r) => `<option value="${r.date}" ${r.date === selected?.date ? 'selected' : ''}>${dateLabel(r.date)} – ${r.buys.length} köp, ${r.sells.length} sälj</option>`).join('')}</select>
        </div>
      </div>
      <div id="rb-detail"></div>
    </section>

    <section class="card">
      <div class="card-head"><div><h2>Tidslinje</h2><div class="sub">Klicka på en rad för att se portföljen det datumet</div></div></div>
      <div id="rb-timeline" class="table-wrap scroll" style="max-height:360px"></div>
    </section>`;

  const draw = () => drawSavings(root, d, ui);
  draw();
  for (const id of ['sv-initial', 'sv-monthly']) {
    $(`#${id}`, root).addEventListener('input', (e) => {
      const v = Math.max(0, Number(e.target.value) || 0);
      ui.savings[id === 'sv-initial' ? 'initial' : 'monthly'] = v;
      draw();
      onChange();
    });
  }

  if (d.allocation) {
    mountChart($('#ch-alloc', root), (t) => allocationOption({ dates: d.allocation.dates, assets: d.allocation.assets, names: ASSET_NAMES, t }));
  }

  const showDetail = (date) => {
    const r = reb.find((x) => x.date === date);
    ui.rebalDate = date;
    $('#rb-detail', root).innerHTML = r ? rebalanceDetail(r, d) : '';
  };
  showDetail(selected?.date);
  $('#rb-date', root).addEventListener('change', (e) => showDetail(e.target.value));

  $('#rb-timeline', root).innerHTML = `<table class="data"><thead><tr><th>Datum</th><th class="num">Innehav</th><th class="num">Köp</th><th class="num">Sälj</th><th class="num">Omsättning</th><th>Köpte bland annat</th></tr></thead><tbody>${reb
    .map((r) => `<tr data-date="${r.date}" style="cursor:pointer"><td>${dateLabel(r.date)}</td><td class="num">${r.holdings.length}</td><td class="num">${r.buys.length}</td><td class="num">${r.sells.length}</td><td class="num">${pct(r.turnover, 0)}</td><td class="name">${esc(r.buys.slice(0, 6).join(', '))}${r.buys.length > 6 ? ' …' : ''}</td></tr>`)
    .join('')}</tbody></table>`;
  $$('#rb-timeline tr[data-date]', root).forEach((tr) =>
    tr.addEventListener('click', () => {
      $('#rb-date', root).value = tr.dataset.date;
      showDetail(tr.dataset.date);
      $('#rb-detail', root).scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }),
  );
}

function rebalanceDetail(r, d) {
  const isAlloc = d.strategy.kind === 'allocation';
  const buys = new Set(r.buys);
  const sold = r.sells;
  return `
    <p class="small" style="margin-bottom:8px">Den <b>${dateLabel(r.date)}</b> ${isAlloc ? 'ställdes portföljen om till' : `ägde strategin ${r.holdings.length} aktier`}.
      ${r.cash > 0.001 ? `${pct(r.cash, 0)} låg i kontanter.` : ''}
      ${sold.length ? `Sålde: <span class="tag-list" style="display:inline-flex">${sold.slice(0, 40).map((t) => `<span class="badge sell">${esc(t)}</span>`).join('')}${sold.length > 40 ? ` +${sold.length - 40}` : ''}</span>` : ''}</p>
    <div class="table-wrap scroll" style="max-height:420px"><table class="data"><thead><tr><th>${isAlloc ? 'Tillgång' : 'Aktie'}</th><th>Namn</th><th class="num">Vikt</th><th class="num">Av $10 000</th><th></th></tr></thead><tbody>${r.holdings
      .map((h) => `<tr><td class="ticker">${esc(h.ticker)}</td><td class="name">${esc(h.name)}</td><td class="num">${pct(h.weight, 1)}</td><td class="num">${usd(h.weight * 10000)}</td><td>${buys.has(h.ticker) ? '<span class="badge buy">Köp</span>' : '<span class="badge">Behåll</span>'}</td></tr>`)
      .join('')}</tbody></table></div>`;
}

function drawSavings(root, d, ui) {
  const { initial, monthly } = ui.savings;
  const dates = d.series.dates;
  const sim = (growth) => {
    const out = [];
    let v = initial;
    for (let i = 0; i < growth.length; i++) {
      if (i > 0) {
        const r = isNum(growth[i]) && isNum(growth[i - 1]) ? growth[i] / growth[i - 1] - 1 : 0;
        v = v * (1 + r) + monthly;
      }
      out.push(Math.round(v));
    }
    return out;
  };
  const strat = sim(d.series.strategy);
  const bench = sim(d.series.benchmarks.sp500);
  const deposits = dates.map((_, i) => initial + monthly * i);
  const dep = deposits.at(-1);
  $('#sv-tiles', root).innerHTML =
    statTile('Insatt totalt', usd(dep), `${num(dates.length - 1)} månader`) +
    statTile('Strategin idag', usd(strat.at(-1)), `${pct(strat.at(-1) / dep - 1, 0, true)} på insatt`, signClass(strat.at(-1) - dep)) +
    statTile('S&P 500 idag', usd(bench.at(-1)), `${pct(bench.at(-1) / dep - 1, 0, true)} på insatt`) +
    statTile('Skillnad', usd(strat.at(-1) - bench.at(-1)), 'Strategin minus S&P 500', signClass(strat.at(-1) - bench.at(-1)));
  mountChart($('#ch-savings', root), (t) =>
    savingsOption({
      dates,
      t,
      series: [
        { name: 'Strategin', short: 'Strategin', data: strat, color: colorFor('strategy', t), main: true },
        { name: 'S&P 500', short: 'S&P 500', data: bench, color: colorFor('sp500', t) },
        { name: 'Insatt kapital', short: 'Insatt', data: deposits, color: t.axis, dashed: true },
      ],
    }),
  );
}

// ---------------------------------------------------------------------------
// Future & uncertainty
// ---------------------------------------------------------------------------

export function renderFuture(root, d) {
  const u = d.uncertainty;
  const f = u.forecast;
  const hist = u.historical;
  const roll = u.rolling12;
  const rollB = u.rolling12_bench;
  const minA = Math.min(...f.table.map((r) => r.annualized.p5), 0);
  const maxA = Math.max(...f.table.map((r) => r.annualized.p95), 0);
  const scale = (v) => ((v - minA) / (maxA - minA || 1)) * 100;
  const rangeBar = (a) => `<div class="range" aria-hidden="true"><div class="track"></div><div class="zero" style="left:${scale(0)}%"></div>
      <div class="outer" style="left:${scale(a.p5)}%;width:${scale(a.p95) - scale(a.p5)}%"></div>
      <div class="inner" style="left:${scale(a.p25)}%;width:${scale(a.p75) - scale(a.p25)}%"></div>
      <div class="mid" style="left:calc(${scale(a.p50)}% - 1px)"></div></div>`;
  const edge = hist.edge;

  root.innerHTML = `
    <div class="callout">Här simuleras <b>${num(f.paths)} möjliga framtider</b> genom att slumpvis dra hela år (block om ${f.block} månader) ur strategins
      historiska avkastning ${monthLabel(d.series.dates[0])}–${monthLabel(d.series.dates.at(-1))}. Det visar spridningen <i>om framtiden liknar det förflutna</i> –
      vilket är det stora antagandet. Verklig osäkerhet är större.</div>

    <section class="card">
      <div class="card-head"><div><h2>Vad kan $10 000 bli?</h2><div class="sub">Median, 50 %- och 90 %-intervall för simulerat värde de kommande 10 åren (logaritmisk skala)</div></div></div>
      <div id="ch-fan" class="chart h-lg" role="img" aria-label="Solfjäderdiagram med framtida utfall"></div>
    </section>

    <section class="card">
      <div class="card-head"><div><h2>Förväntad årlig avkastning per tidshorisont</h2><div class="sub">Ljus stapel = 90 % av utfallen, mörk = mittersta 50 %, streck = median. Linjen = 0 %.</div></div></div>
      <div class="table-wrap"><table class="data"><thead><tr><th>Horisont</th><th class="num">5 %</th><th class="num">25 %</th><th class="num">Median</th><th class="num">75 %</th><th class="num">95 %</th><th>Spridning</th><th class="num">Risk för förlust</th><th class="num">Slår S&amp;P 500</th><th class="num">Fördubblas</th></tr></thead><tbody>${f.table
        .map((r) => `<tr><td>${years(r.months)}</td>
          <td class="num ${signClass(r.annualized.p5)}">${pct(r.annualized.p5)}</td><td class="num">${pct(r.annualized.p25)}</td>
          <td class="num"><b>${pct(r.annualized.p50)}</b></td><td class="num">${pct(r.annualized.p75)}</td><td class="num">${pct(r.annualized.p95)}</td>
          <td>${rangeBar(r.annualized)}</td>
          <td class="num">${pct(r.prob_loss, 0)}</td><td class="num">${r.prob_beat_bench != null ? pct(r.prob_beat_bench, 0) : '–'}</td><td class="num">${pct(r.prob_double, 0)}</td></tr>`)
        .join('')}</tbody></table></div>
      <p class="note">Årlig avkastning (annualiserad). "Risk för förlust" = andel simuleringar där du har mindre än du satte in efter perioden.</p>
    </section>

    <div class="grid-2">
      <section class="card">
        <div class="card-head"><div><h2>Var den historiska avkastningen tur?</h2><div class="sub">95 % konfidensintervall via bootstrap av hela perioden</div></div></div>
        <dl class="kv">
          <dt>Historisk årsavkastning</dt><dd>${pct(d.stats.strategy.cagr)}</dd>
          <dt>95 % intervall</dt><dd>${pct(hist.cagr.p2_5)} till ${pct(hist.cagr.p97_5)}</dd>
          ${edge ? `<dt>Försprång mot S&amp;P 500</dt><dd class="${signClass(edge.p50)}">${pp(edge.p50)}</dd>
          <dt>95 % intervall för försprånget</dt><dd>${pp(edge.p2_5)} till ${pp(edge.p97_5)}</dd>
          <dt>Sannolikhet att försprånget är verkligt (&gt; 0)</dt><dd>${pct(hist.prob_edge_positive, 0)}</dd>
          <dt>t-värde (månatlig skillnad)</dt><dd>${num(hist.t_stat, 2)}</dd>` : ''}
        </dl>
        <p class="note">${edge ? verdict(edge, hist) : ''}</p>
      </section>
      <section class="card">
        <div class="card-head"><div><h2>Alla historiska 12-månadersperioder</h2><div class="sub">Vad ett köp en slumpmässig månad gav året efter (${num(roll.n)} perioder)</div></div></div>
        <div id="ch-hist" class="chart h-sm" role="img" aria-label="Fördelning av 12-månadersavkastning"></div>
        <dl class="kv" style="margin-top:8px">
          <dt>Median</dt><dd>${pct(roll.pcts.p50)} <span class="muted">(S&amp;P 500: ${pct(rollB.pcts.p50)})</span></dd>
          <dt>90 % av perioderna</dt><dd>${pct(roll.pcts.p5)} till ${pct(roll.pcts.p95)} <span class="muted">(S&amp;P 500: ${pct(rollB.pcts.p5)} till ${pct(rollB.pcts.p95)})</span></dd>
          <dt>Andel med förlust</dt><dd>${pct(roll.prob_loss, 0)} <span class="muted">(S&amp;P 500: ${pct(rollB.prob_loss, 0)})</span></dd>
        </dl>
      </section>
    </div>`;

  mountChart($('#ch-fan', root), (t) => fanOption({ months: f.months, fan: f.fan, t }));
  mountChart($('#ch-hist', root), (t) => histogramOption({ edges: roll.hist.edges, counts: roll.hist.counts, t, pcts: roll.pcts }));
}

function verdict(edge, hist) {
  if (edge.p2_5 > 0) return 'Hela intervallet ligger över noll: försprånget är statistiskt tydligt i den här perioden (men kan fortfarande bero på överlevnadsbias eller att perioden var gynnsam).';
  if (edge.p97_5 < 0) return 'Hela intervallet ligger under noll: strategin har med stor sannolikhet gått sämre än S&P 500 under perioden.';
  return `Intervallet innehåller noll, så vi kan inte säga säkert att strategin är bättre eller sämre än S&P 500 – skillnaden kan vara slump. Med ${num(hist.t_stat, 1)} i t-värde krävs normalt över 2 för att tala om en säkerställd skillnad.`;
}

// ---------------------------------------------------------------------------
// Buy today
// ---------------------------------------------------------------------------

export function renderToday(root, d, ui, live, onAmount) {
  const c = d.current;
  const f12 = d.uncertainty.forecast.table.find((r) => r.months === 12);
  const roll = d.uncertainty.rolling12;
  const lastReb = d.rebalances.at(-1);
  const held = new Set((lastReb?.holdings ?? []).map((h) => h.ticker));
  const today = new Set(c.holdings.map((h) => h.ticker));
  const newBuys = c.holdings.filter((h) => !held.has(h.ticker)).map((h) => h.ticker);
  const toSell = [...held].filter((t) => !today.has(t));
  const isStocks = d.strategy.kind === 'stocks';
  const amount = ui.amount;

  root.innerHTML = `
    <div class="callout"><b>Signal:</b> ${esc(c.signal)}<br><b>Ombalansering:</b> ${esc(c.next_rebalance)}.
      ${lastReb ? ` Senaste ordinarie ombalansering i backtesten: ${dateLabel(lastReb.date)}.` : ''}</div>

    <div class="grid-2">
      <section class="card">
        <div class="card-head"><div><h2>Om du köper idag</h2><div class="sub">Förväntad avkastning de kommande 12 månaderna, baserat på strategins historik</div></div></div>
        <div class="stats" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">
          ${statTile('Median, 12 mån', pct(f12.total.p50), usd(amount * (1 + f12.total.p50)), signClass(f12.total.p50))}
          ${statTile('90 % intervall', `${pct(f12.total.p5, 0)} – ${pct(f12.total.p95, 0)}`, `${usd(amount * (1 + f12.total.p5))} – ${usd(amount * (1 + f12.total.p95))}`)}
          ${statTile('Risk för förlust', pct(f12.prob_loss, 0), f12.prob_beat_bench != null ? `Slår S&P 500: ${pct(f12.prob_beat_bench, 0)}` : '')}
        </div>
        <p class="note">Simulerat med block-bootstrap. Historiskt gav 90 % av alla 12-månadersperioder ${pct(roll.pcts.p5, 0)} till ${pct(roll.pcts.p95, 0)}. Inget löfte – se fliken Framtid &amp; osäkerhet.</p>
      </section>
      <section class="card">
        <div class="card-head"><div><h2>Ändringar mot nuvarande portfölj</h2><div class="sub">Dagens signal jämfört med senaste ombalanseringen</div></div></div>
        ${newBuys.length || toSell.length ? `
          <p class="small"><b>Nya köp (${newBuys.length}):</b></p><div class="tag-list">${newBuys.map((t) => `<span class="badge buy">${esc(t)}</span>`).join('') || '<span class="muted small">Inga</span>'}</div>
          <p class="small" style="margin-top:10px"><b>Sälj (${toSell.length}):</b></p><div class="tag-list">${toSell.map((t) => `<span class="badge sell">${esc(t)}</span>`).join('') || '<span class="muted small">Inga</span>'}</div>
          ${isStocks && d.params.rebalance > 1 ? '<p class="note">Strategin ombalanserar inte varje månad – följ schemat ovan i stället för att handla varje gång listan ändras.</p>' : ''}`
          : '<p class="small muted">Inga ändringar – dagens signal är samma som nuvarande portfölj.</p>'}
      </section>
    </div>

    <section class="card">
      <div class="card-head">
        <div><h2>${isStocks ? `Dagens köplista – ${c.holdings.length} aktier` : 'Dagens fördelning'}</h2>
          <div class="sub">Rangordning per ${dateLabel(c.as_of)}${c.eligible ? ` bland ${num(c.eligible)} valbara bolag` : ''} · lika vikt</div></div>
        <div class="checks">
          <div class="field"><label for="buy-amount">Belopp att investera (USD)</label><input id="buy-amount" type="number" min="0" step="1000" value="${amount}"></div>
          <span id="live-chip" class="chip"><span class="dot"></span><span>Kurser</span></span>
        </div>
      </div>
      <div id="buy-table" class="table-wrap scroll" style="max-height:640px"></div>
      <p class="note">${live.enabled ? 'Kurser och dagsförändring live från Alpaca (IEX-flödet, uppdateras var 15:e sekund under handelstid).' : 'Kurserna är senaste stängningskurs. Lägg in Alpaca-nycklar i <code>.env</code> för live-kurser (se README).'}
      Antal aktier avrundas nedåt till hela aktier. Courtage och valutaväxling ingår inte.</p>
    </section>`;

  $('#buy-amount', root).addEventListener('input', (e) => {
    ui.amount = Math.max(0, Number(e.target.value) || 0);
    drawBuyTable(root, d, ui, live);
    onAmount();
  });
  drawBuyTable(root, d, ui, live);
}

export function drawBuyTable(root, d, ui, live) {
  const el = $('#buy-table', root);
  if (!el) return;
  const c = d.current;
  const isStocks = d.strategy.kind === 'stocks';
  const extra = c.columns ?? [];
  const quotes = live.quotes ?? {};
  const rows = c.holdings
    .map((h, i) => {
      const q = quotes[h.ticker];
      const price = q?.price ?? h.price;
      const value = ui.amount * h.weight;
      const shares = h.tradable && isNum(price) && price > 0 ? Math.floor(value / price) : null;
      return `<tr data-t="${esc(h.ticker)}">
        ${isStocks ? `<td class="num muted">${h.rank ?? i + 1}</td>` : ''}
        <td class="ticker">${esc(h.ticker)}</td><td class="name" title="${esc(h.name)}">${esc(h.name)}</td>
        ${isStocks ? `<td class="name muted">${esc(h.sector ?? '')}</td>` : ''}
        <td class="num">${pct(h.weight, 1)}</td><td class="num">${usd(value)}</td>
        <td class="num price">${h.tradable ? (isNum(price) ? usd(price, 2) : '–') : ''}</td>
        <td class="num chg ${signClass(q?.change)}">${q?.change != null ? pct(q.change, 2, true) : ''}</td>
        <td class="num">${shares != null ? num(shares) : ''}</td>
        ${extra.map((col) => `<td class="num">${byFormat(h[col.key], col.format)}</td>`).join('')}
      </tr>`;
    })
    .join('');
  el.innerHTML = `<table class="data"><thead><tr>
      ${isStocks ? '<th class="num">#</th>' : ''}<th>${isStocks ? 'Aktie' : 'Tillgång'}</th><th>Namn</th>${isStocks ? '<th>Sektor</th>' : ''}
      <th class="num">Vikt</th><th class="num">Belopp</th><th class="num">Kurs</th><th class="num">Idag</th><th class="num">Antal</th>
      ${extra.map((col) => `<th class="num">${esc(col.label)}</th>`).join('')}
    </tr></thead><tbody>${rows}</tbody></table>`;
}

// ---------------------------------------------------------------------------
// Compare all
// ---------------------------------------------------------------------------

export function renderCompare(root, data, onPick) {
  const strategies = data.strategies.filter((s) => !s.error);
  const all = [
    ...strategies.map((s) => ({ ...s, label: s.name, isBench: false })),
    ...data.benchmarks.map((b) => ({ ...b, label: `Index: ${b.name}`, isBench: true })),
  ];
  const byCagr = [...all].sort((a, b) => b.cagr - a.cagr);
  const bySharpe = [...all].filter((x) => x.sharpe != null).sort((a, b) => b.sharpe - a.sharpe);
  const muted = new Set(all.filter((x) => x.isBench).map((x) => x.label));
  const ht = (n) => Math.max(320, n * 28);
  root.innerHTML = `
    <div class="callout">Alla strategier med standardinställningar över <b>samma period</b> (${monthLabel(data.start)} – idag), efter 0,10 % transaktionskostnad.
      Grå staplar är index. Aktiestrategier har överlevnadsbias – jämför dem främst med <b>Lika vikt – hela universumet</b>.</div>
    <div class="grid-2">
      <section class="card"><div class="card-head"><div><h2>Årlig avkastning</h2><div class="sub">CAGR</div></div></div>
        <div id="ch-cmp-cagr" class="chart" style="height:${ht(byCagr.length)}px" role="img" aria-label="Årlig avkastning per strategi"></div></section>
      <section class="card"><div class="card-head"><div><h2>Avkastning per risk</h2><div class="sub">Sharpekvot (överavkastning / volatilitet)</div></div></div>
        <div id="ch-cmp-sharpe" class="chart" style="height:${ht(bySharpe.length)}px" role="img" aria-label="Sharpekvot per strategi"></div></section>
    </div>
    <section class="card"><div class="card-head"><div><h2>Alla nyckeltal</h2><div class="sub">Klicka på en kolumn för att sortera, på en strategi för att öppna den</div></div></div>
      <div id="tb-cmp" class="table-wrap"></div></section>`;

  mountChart($('#ch-cmp-cagr', root), (t) => hBarsOption({ labels: byCagr.map((x) => x.label), values: byCagr.map((x) => x.cagr), t, muted }));
  mountChart($('#ch-cmp-sharpe', root), (t) => hBarsOption({ labels: bySharpe.map((x) => x.label), values: bySharpe.map((x) => x.sharpe), t, muted, fmt: (v) => ratio(v) }));

  const rows = all.map((x) => ({ ...x, id: x.isBench ? '' : x.id, family: x.isBench ? 'Index' : x.family }));
  sortableTable(
    $('#tb-cmp', root),
    [
      { key: 'label', label: 'Strategi', fmt: (v, r) => (r.isBench ? esc(v) : `<button class="link" type="button">${esc(v)}</button>`) },
      { key: 'family', label: 'Typ' },
      { key: 'cagr', label: 'CAGR', num: true, fmt: (v) => pct(v), cls: (r) => signClass(r.cagr) },
      { key: 'volatility', label: 'Volatilitet', num: true, fmt: (v) => pct(v) },
      { key: 'sharpe', label: 'Sharpe', num: true, fmt: (v) => ratio(v) },
      { key: 'max_drawdown', label: 'Största fall', num: true, fmt: (v) => pct(v) },
      { key: 'beta', label: 'Beta', num: true, fmt: (v) => ratio(v) },
      { key: 'alpha', label: 'Alfa', num: true, fmt: (v) => pct(v, 1, true) },
      { key: 'excess_cagr', label: 'Mot S&P 500', num: true, fmt: (v) => pp(v), cls: (r) => signClass(r.excess_cagr) },
      { key: 'worst_year', label: 'Sämsta år', num: true, fmt: (v) => pct(v) },
    ],
    rows,
    { sortKey: 'cagr', rowClass: (r) => (r.isBench ? 'is-bench' : ''), onRow: (id) => id && onPick(id) },
  );
}
