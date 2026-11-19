// Formatting helpers (Swedish locale).

const cache = new Map();
function nf(min, max = min) {
  const k = `${min}-${max}`;
  if (!cache.has(k)) cache.set(k, new Intl.NumberFormat('sv-SE', { minimumFractionDigits: min, maximumFractionDigits: max }));
  return cache.get(k);
}
const MINUS = '−';

export const isNum = (v) => typeof v === 'number' && Number.isFinite(v);

export function num(v, d = 0) {
  return isNum(v) ? nf(d).format(v).replace('-', MINUS) : '–';
}

/** 0.1234 -> "12,3 %" */
export function pct(v, d = 1, signed = false) {
  if (!isNum(v)) return '–';
  const s = nf(d).format(Math.abs(v * 100));
  const sign = v < 0 ? MINUS : signed && v > 0 ? '+' : '';
  return `${sign}${s} %`;
}

/** Percentage points difference */
export function pp(v, d = 1) {
  if (!isNum(v)) return '–';
  const sign = v < 0 ? MINUS : v > 0 ? '+' : '±';
  return `${sign}${nf(d).format(Math.abs(v * 100))} p.e.`;
}

export function usd(v, d = 0) {
  if (!isNum(v)) return '–';
  return `${v < 0 ? MINUS : ''}$${nf(d).format(Math.abs(v))}`;
}

/** Short USD for axes and labels: $950, $12 500, $1,2 mn, $3,4 md */
export function usdCompact(v) {
  if (!isNum(v)) return '–';
  const a = Math.abs(v);
  const sign = v < 0 ? MINUS : '';
  if (a >= 1e9) return `${sign}$${nf(0, 1).format(a / 1e9)} md`;
  if (a >= 1e6) return `${sign}$${nf(0, 1).format(a / 1e6)} mn`;
  const rounded = a >= 1e4 ? Math.round(a / 100) * 100 : Math.round(a);
  return `${sign}$${nf(0).format(rounded)}`;
}

export function ratio(v, d = 2) {
  return isNum(v) ? nf(d).format(v).replace('-', MINUS) : '–';
}

export function signClass(v) {
  if (!isNum(v) || v === 0) return '';
  return v > 0 ? 'pos' : 'neg';
}

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'];

export function monthLabel(iso) {
  if (!iso) return '';
  const [y, m] = iso.split('-');
  return `${MONTHS[Number(m) - 1]} ${y}`;
}

export function dateLabel(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('sv-SE', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function timeLabel(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function years(months) {
  const y = months / 12;
  return y === 1 ? '1 år' : `${num(y, Number.isInteger(y) ? 0 : 1)} år`;
}

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

/** Format by a column spec from the API: pct | usd | x */
export function byFormat(v, fmt) {
  if (fmt === 'pct') return pct(v);
  if (fmt === 'usd') return usdCompact(v);
  if (fmt === 'x') return isNum(v) ? `${ratio(v, 2)}×` : '–';
  return num(v, 2);
}
