// ECharts option builders. Pure functions: data + colour tokens in, option out.
// Colours follow the entity (strategy = slot 1, S&P 500 = slot 2, ...), never rank.

import { esc, monthLabel, num, pct, usd, usdCompact } from './format.js';

export const ENTITY_SLOT = { strategy: 0, sp500: 1, global: 2, omxs30: 3, ew_universe: 4 };
export const ASSET_SLOT = { SPY: 0, EFA: 2, IEF: 3, AGG: 4, ACWI: 5 };

export function colorFor(key, t) {
  if (key === 'CASH') return t.axis;
  return t.series[ENTITY_SLOT[key] ?? 0];
}

/** '#rrggbb' + alpha -> rgba() */
function hexAlpha(hex, a) {
  const n = parseInt(hex.replace('#', ''), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

function tooltipBase(t) {
  return {
    backgroundColor: t.dark ? 'rgba(13,18,25,0.92)' : 'rgba(251,252,253,0.95)',
    borderColor: t.baseline,
    borderWidth: 1,
    padding: [9, 12],
    textStyle: { color: t.ink, fontFamily: t.font, fontSize: 12.5 },
    extraCssText: `box-shadow:0 10px 30px rgba(0,0,0,${t.dark ? 0.5 : 0.14});border-radius:6px;backdrop-filter:blur(8px);font-family:${t.font}`,
  };
}

function axisCommon(t) {
  return {
    axisLine: { lineStyle: { color: t.baseline } },
    axisTick: { show: false },
    axisLabel: { color: t.muted, fontSize: 10.5, fontFamily: t.font, hideOverlap: true },
    splitLine: { lineStyle: { color: t.grid, width: 1, type: [3, 3] } },
  };
}

/** Category x-axis over month-end dates: one label per January, thinned for long spans. */
function yearAxis(dates, t) {
  const span = Number(dates.at(-1).slice(0, 4)) - Number(dates[0].slice(0, 4)) || 1;
  const step = span > 16 ? 4 : span > 8 ? 2 : 1;
  return {
    type: 'category',
    data: dates,
    boundaryGap: false,
    ...axisCommon(t),
    splitLine: { show: false },
    axisLabel: {
      color: t.muted,
      fontSize: 10.5,
      fontFamily: t.font,
      interval: (i, v) => v.slice(5, 7) === '01' && Number(v.slice(0, 4)) % step === 0,
      formatter: (v) => v.slice(0, 4),
    },
  };
}

const row = (color, name, value) =>
  `<div style="display:flex;align-items:center;gap:8px;justify-content:space-between;min-width:190px">
     <span style="display:flex;align-items:center;gap:6px"><span style="width:10px;height:3px;border-radius:2px;background:${color}"></span>${esc(name)}</span>
     <b style="font-weight:650;font-variant-numeric:tabular-nums">${value}</b></div>`;

/** Growth of $X: strategy + benchmarks. */
export function growthOption({ dates, series, t, log = false, startValue = 10000 }) {
  return {
    animationDuration: 300,
    grid: { left: 8, right: 96, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      ...tooltipBase(t),
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: t.axis, type: [4, 3] } },
      formatter: (ps) => {
        const head = `<div style="color:${t.ink2};margin-bottom:4px">${monthLabel(dates[ps[0].dataIndex])}</div>`;
        const items = ps
          .filter((p) => p.value != null)
          .sort((a, b) => b.value - a.value)
          .map((p) => row(p.color, p.seriesName, `${usd(p.value * startValue)} <span style="color:${t.muted};font-weight:500">(${pct(p.value - 1, 0, true)})</span>`));
        return head + items.join('');
      },
    },
    xAxis: yearAxis(dates, t),
    yAxis: {
      type: log ? 'log' : 'value',
      scale: true,
      // Log scale in doublings ($5k, $10k, $20k ...) keeps the plot tight around the data.
      ...(log
        ? {
            logBase: 2,
            min: (e) => 2 ** Math.floor(Math.log2(e.min)),
            max: (e) => 2 ** Math.ceil(Math.log2(e.max)),
          }
        : {}),
      ...axisCommon(t),
      axisLine: { show: false },
      axisLabel: { ...axisCommon(t).axisLabel, formatter: (v) => usdCompact(v * startValue) },
    },
    series: series.map((s) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      showSymbol: false,
      symbolSize: 8,
      connectNulls: false,
      lineStyle: s.main
        ? { width: 2.5, color: s.color, shadowColor: s.color, shadowBlur: t.dark ? 12 : 4 }
        : { width: 2, color: s.color },
      itemStyle: { color: s.color, borderColor: t.surface, borderWidth: 2 },
      areaStyle: s.main && !log
        ? {
            origin: 'start',
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: hexAlpha(s.color, t.dark ? 0.28 : 0.16) },
              { offset: 1, color: hexAlpha(s.color, 0) },
            ]),
          }
        : undefined,
      emphasis: { focus: 'series' },
      z: s.main ? 5 : 2,
      endLabel: {
        show: true,
        color: t.ink2,
        fontFamily: t.font,
        fontSize: 10.5,
        fontWeight: s.main ? 700 : 500,
        formatter: (p) => `${s.short ?? s.name}\n${usdCompact(p.value * startValue)}`,
      },
      labelLayout: { moveOverlap: 'shiftY' },
    })),
  };
}

export function drawdownOption({ dates, series, t }) {
  return {
    animationDuration: 300,
    grid: { left: 8, right: 16, top: 12, bottom: 8, containLabel: true },
    legend: { show: false },
    tooltip: {
      ...tooltipBase(t),
      trigger: 'axis',
      formatter: (ps) =>
        `<div style="color:${t.ink2};margin-bottom:4px">${monthLabel(dates[ps[0].dataIndex])}</div>` +
        ps.map((p) => row(p.color, p.seriesName, pct(p.value, 1))).join(''),
    },
    xAxis: yearAxis(dates, t),
    yAxis: { type: 'value', max: 0, ...axisCommon(t), axisLine: { show: false }, axisLabel: { ...axisCommon(t).axisLabel, formatter: (v) => pct(v, 0) } },
    series: series.map((s, i) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      showSymbol: false,
      lineStyle: { width: i === 0 ? 2 : 1.5, color: s.color },
      itemStyle: { color: s.color },
      areaStyle: i === 0 ? { color: s.color, opacity: 0.14 } : undefined,
      z: i === 0 ? 3 : 2,
    })),
  };
}

/** Grouped vertical bars by category (years). */
export function groupedBarsOption({ categories, series, t, fmt = (v) => pct(v, 1) }) {
  return {
    animationDuration: 300,
    grid: { left: 8, right: 12, top: 12, bottom: 8, containLabel: true },
    tooltip: {
      ...tooltipBase(t),
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: t.grid, opacity: 0.5 } },
      formatter: (ps) =>
        `<div style="color:${t.ink2};margin-bottom:4px">${esc(ps[0].axisValue)}</div>` +
        ps.map((p) => row(p.color, p.seriesName, fmt(p.value))).join(''),
    },
    xAxis: { type: 'category', data: categories, ...axisCommon(t), splitLine: { show: false } },
    yAxis: { type: 'value', ...axisCommon(t), axisLine: { show: false }, axisLabel: { ...axisCommon(t).axisLabel, formatter: (v) => fmt(v) } },
    series: series.map((s) => ({
      name: s.name,
      type: 'bar',
      data: s.data.map((v) => ({
        value: v,
        itemStyle: { borderRadius: v >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4] },
      })),
      barMaxWidth: 14,
      barGap: '15%',
      itemStyle: { color: s.color },
    })),
  };
}

/** Allocation over time: stacked area of weights. */
export function allocationOption({ dates, assets, names, t }) {
  const keys = Object.keys(assets);
  return {
    animationDuration: 300,
    grid: { left: 8, right: 12, top: 36, bottom: 8, containLabel: true },
    legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 12, itemHeight: 4, textStyle: { color: t.ink2, fontSize: 12 } },
    tooltip: {
      ...tooltipBase(t),
      trigger: 'axis',
      formatter: (ps) =>
        `<div style="color:${t.ink2};margin-bottom:4px">${monthLabel(dates[ps[0].dataIndex])}</div>` +
        ps.filter((p) => p.value > 0.0005).map((p) => row(p.color, p.seriesName, pct(p.value, 0))).join(''),
    },
    xAxis: yearAxis(dates, t),
    yAxis: { type: 'value', max: 1, ...axisCommon(t), axisLine: { show: false }, axisLabel: { ...axisCommon(t).axisLabel, formatter: (v) => pct(v, 0) } },
    series: keys.map((k) => {
      const c = k === 'CASH' ? t.axis : t.series[ASSET_SLOT[k] ?? 5];
      return {
        name: names[k] ?? k,
        type: 'line',
        step: 'end',
        stack: 'w',
        data: assets[k],
        showSymbol: false,
        lineStyle: { width: 0 },
        areaStyle: { color: c, opacity: 0.85 },
        itemStyle: { color: c },
      };
    }),
  };
}

/** Value with monthly savings: strategy vs S&P 500 vs deposits. */
export function savingsOption({ dates, series, t }) {
  return {
    animationDuration: 300,
    grid: { left: 8, right: 96, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      ...tooltipBase(t),
      trigger: 'axis',
      formatter: (ps) =>
        `<div style="color:${t.ink2};margin-bottom:4px">${monthLabel(dates[ps[0].dataIndex])}</div>` +
        ps.filter((p) => p.value != null).map((p) => row(p.color, p.seriesName, usd(p.value))).join(''),
    },
    xAxis: yearAxis(dates, t),
    yAxis: { type: 'value', ...axisCommon(t), axisLine: { show: false }, axisLabel: { ...axisCommon(t).axisLabel, formatter: (v) => usdCompact(v) } },
    series: series.map((s) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      showSymbol: false,
      step: s.step ? 'end' : undefined,
      lineStyle: { width: s.main ? 2.5 : 2, color: s.color, type: s.dashed ? [4, 4] : 'solid' },
      itemStyle: { color: s.color },
      endLabel: { show: true, color: t.ink2, fontFamily: t.font, fontSize: 10.5, fontWeight: s.main ? 700 : 500, formatter: (p) => `${s.short ?? s.name}\n${usdCompact(p.value)}` },
      labelLayout: { moveOverlap: 'shiftY' },
      z: s.main ? 5 : 2,
    })),
  };
}

/** Fan chart: percentile bands of simulated future value. */
export function fanOption({ months, fan, t, startValue = 10000 }) {
  const c = t.series[0];
  const x = [0, ...months];
  // Plot multiples of the start value so log ticks land on $5k, $10k, $20k ...
  const withStart = (arr) => [1, ...arr];
  const money = (v) => v * startValue;
  const p5 = withStart(fan.p5), p25 = withStart(fan.p25), p50 = withStart(fan.p50), p75 = withStart(fan.p75), p95 = withStart(fan.p95);
  const band = (lo, hi) => hi.map((v, i) => v - lo[i]);
  const bench = fan.bench_p50 ? withStart(fan.bench_p50) : null;
  const yearLabel = (m) => (m % 12 === 0 ? `${m / 12} år` : '');
  return {
    animationDuration: 300,
    grid: { left: 8, right: 110, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      ...tooltipBase(t),
      trigger: 'axis',
      formatter: (ps) => {
        const i = ps[0].dataIndex;
        const m = x[i];
        const head = `<div style="color:${t.ink2};margin-bottom:4px">Om ${m < 12 ? `${m} mån` : `${num(m / 12, m % 12 ? 1 : 0)} år`}</div>`;
        return (
          head +
          row(c, '95:e percentilen (bra utfall)', usd(money(p95[i]))) +
          row(c, '75:e percentilen', usd(money(p75[i]))) +
          row(t.ink, 'Median', usd(money(p50[i]))) +
          row(c, '25:e percentilen', usd(money(p25[i]))) +
          row(c, '5:e percentilen (dåligt utfall)', usd(money(p5[i]))) +
          (bench ? row(t.series[1], 'S&P 500, median', usd(money(bench[i]))) : '')
        );
      },
    },
    xAxis: { type: 'category', data: x, boundaryGap: false, ...axisCommon(t), splitLine: { show: false }, axisLabel: { ...axisCommon(t).axisLabel, interval: 0, formatter: yearLabel } },
    yAxis: {
      type: 'log',
      // Doublings of the start value ($5k, $10k, $20k ...) keep the fan filling the plot.
      logBase: 2,
      min: 2 ** Math.floor(Math.log2(Math.min(...p5))),
      max: 2 ** Math.ceil(Math.log2(Math.max(...p95, ...(bench ?? [])))),
      ...axisCommon(t),
      axisLine: { show: false },
      axisLabel: { ...axisCommon(t).axisLabel, formatter: (v) => usdCompact(money(v)) },
    },
    series: [
      { name: 'base', type: 'line', data: p5, stack: 'fan', lineStyle: { opacity: 0 }, showSymbol: false, silent: true, tooltip: { show: false } },
      { name: '90 %', type: 'line', data: band(p5, p25), stack: 'fan', lineStyle: { opacity: 0 }, showSymbol: false, areaStyle: { color: c, opacity: 0.14 } },
      { name: '50 %', type: 'line', data: band(p25, p75), stack: 'fan', lineStyle: { opacity: 0 }, showSymbol: false, areaStyle: { color: c, opacity: 0.3 } },
      { name: '90 % top', type: 'line', data: band(p75, p95), stack: 'fan', lineStyle: { opacity: 0 }, showSymbol: false, areaStyle: { color: c, opacity: 0.14 } },
      {
        name: 'Median', type: 'line', data: p50, showSymbol: false, lineStyle: { width: 2.5, color: c, shadowColor: c, shadowBlur: t.dark ? 10 : 0 }, itemStyle: { color: c }, z: 5,
        labelLayout: { moveOverlap: 'shiftY' },
        endLabel: { show: true, color: t.ink2, fontFamily: t.font, fontSize: 10.5, lineHeight: 14, fontWeight: 700, formatter: (p) => `Median\n${usdCompact(money(p.value))}` },
      },
      ...(bench
        ? [{
            name: 'S&P 500 median', type: 'line', data: bench, showSymbol: false, labelLayout: { moveOverlap: 'shiftY' }, lineStyle: { width: 2, color: t.series[1], type: [5, 4] }, itemStyle: { color: t.series[1] },
            endLabel: { show: true, color: t.ink2, fontFamily: t.font, fontSize: 10.5, lineHeight: 14, formatter: (p) => `S&P 500\n${usdCompact(money(p.value))}` },
          }]
        : []),
    ],
  };
}

/** Histogram of 12-month returns. */
export function histogramOption({ edges, counts, t, pcts }) {
  const centers = counts.map((_, i) => (edges[i] + edges[i + 1]) / 2);
  const total = counts.reduce((a, b) => a + b, 0) || 1;
  return {
    animationDuration: 300,
    grid: { left: 8, right: 12, top: 24, bottom: 8, containLabel: true },
    tooltip: {
      ...tooltipBase(t),
      trigger: 'item',
      formatter: (p) => {
        const i = p.dataIndex;
        return `<div style="color:${t.ink2};margin-bottom:4px">${pct(edges[i], 0)} till ${pct(edges[i + 1], 0)}</div>` +
          row(t.series[0], 'Andel av 12-mån.perioder', pct(counts[i] / total, 1));
      },
    },
    xAxis: {
      type: 'category', data: centers.map((c) => pct(c, 0)), ...axisCommon(t), splitLine: { show: false },
    },
    yAxis: { type: 'value', ...axisCommon(t), axisLine: { show: false }, axisLabel: { ...axisCommon(t).axisLabel, formatter: (v) => pct(v / total, 0) } },
    series: [
      {
        type: 'bar',
        data: counts.map((v, i) => ({ value: v, itemStyle: { color: edges[i + 1] <= 0 ? t.series[1] : t.series[0], borderRadius: [4, 4, 0, 0] } })),
        barCategoryGap: '12%',
        markLine: pcts
          ? {
              symbol: 'none', silent: true,
              lineStyle: { color: t.ink2, type: 'solid', width: 1 },
              label: { color: t.ink2, fontSize: 11, formatter: (p) => p.name },
              data: [{ name: `Median ${pct(pcts.p50, 0)}`, xAxis: nearestIndex(centers, pcts.p50) }],
            }
          : undefined,
      },
    ],
  };
}

function nearestIndex(arr, v) {
  let best = 0;
  arr.forEach((a, i) => { if (Math.abs(a - v) < Math.abs(arr[best] - v)) best = i; });
  return best;
}

/** Horizontal ranked bars (one hue; highlight + signed variant). */
export function hBarsOption({ labels, values, t, fmt = (v) => pct(v, 1), highlight = new Set(), muted = new Set(), signed = false }) {
  return {
    animationDuration: 300,
    grid: { left: 8, right: 56, top: 4, bottom: 4, containLabel: true },
    tooltip: { ...tooltipBase(t), trigger: 'item', formatter: (p) => `<b>${esc(labels[p.dataIndex])}</b><br>${fmt(values[p.dataIndex])}` },
    xAxis: { type: 'value', ...axisCommon(t), axisLabel: { ...axisCommon(t).axisLabel, formatter: (v) => fmt(v) } },
    yAxis: { type: 'category', data: labels, inverse: true, ...axisCommon(t), axisLine: { show: false }, splitLine: { show: false }, axisLabel: { color: t.ink2, fontSize: 12, width: 210, overflow: 'truncate' } },
    series: [
      {
        type: 'bar',
        barMaxWidth: 16,
        data: values.map((v, i) => {
          let color = t.series[0];
          if (signed && v < 0) color = t.series[1];
          if (muted.has(labels[i])) color = t.axis;
          return {
            value: v,
            itemStyle: { color, opacity: highlight.size && !highlight.has(labels[i]) && !muted.has(labels[i]) ? 0.55 : 1, borderRadius: v >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4] },
          };
        }),
        label: { show: true, position: 'right', color: t.ink2, fontSize: 11, formatter: (p) => fmt(p.value) },
      },
    ],
  };
}
