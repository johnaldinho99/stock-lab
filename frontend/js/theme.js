// Light/dark theme: follows the OS by default, the toggle overrides it.

const KEY = 'stocklab.theme';
const media = window.matchMedia('(prefers-color-scheme: dark)');

export function isDark() {
  const forced = document.documentElement.dataset.theme;
  return forced ? forced === 'dark' : media.matches;
}

export function initTheme(button, onChange) {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === 'light' || saved === 'dark') document.documentElement.dataset.theme = saved;
  } catch {
    /* storage unavailable */
  }

  button.addEventListener('click', () => {
    const next = isDark() ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* ignore */
    }
    onChange();
  });

  media.addEventListener('change', () => {
    if (!document.documentElement.dataset.theme) onChange();
  });
}

/** Read the current colour tokens from CSS so charts match the theme. */
export function tokens() {
  const cs = getComputedStyle(document.documentElement);
  const v = (name) => cs.getPropertyValue(name).trim();
  return {
    surface: v('--surface'),
    ink: v('--ink'),
    ink2: v('--ink-2'),
    muted: v('--muted'),
    axis: v('--axis'),
    grid: v('--grid'),
    baseline: v('--baseline'),
    border: v('--border'),
    empty: v('--empty'),
    series: [1, 2, 3, 4, 5, 6].map((i) => v(`--series-${i}`)),
    ramp: [1, 2, 3, 4, 5, 6, 7].map((i) => v(`--seq-${i}`)),
  };
}
