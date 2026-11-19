// Thin fetch wrapper. Requests for the same URL share one in-flight promise.

const inflight = new Map();

export async function getJSON(url) {
  if (inflight.has(url)) return inflight.get(url);
  const p = (async () => {
    const res = await fetch(url);
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        if (body.detail) msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      } catch {
        /* not json */
      }
      throw new Error(msg);
    }
    return res.json();
  })();
  inflight.set(url, p);
  try {
    return await p;
  } finally {
    inflight.delete(url);
  }
}

export const api = {
  strategies: () => getJSON('/api/strategies'),
  strategy: (id, params, start) => {
    const q = new URLSearchParams(params);
    if (start) q.set('start', start);
    return getJSON(`/api/strategies/${encodeURIComponent(id)}?${q}`);
  },
  compare: (start) => getJSON(`/api/compare${start ? `?start=${start}` : ''}`),
  live: (symbols) => getJSON(`/api/live?symbols=${encodeURIComponent(symbols.join(','))}`),
  status: () => getJSON('/api/status'),
};
