/* Market Intel: signal model outlook, supporting charts, event log, feeds and backtest.
 * Rendered into #mi-top and #mi-bottom, which renderAnalyticsPage() in app.js provides.
 * Colour convention (matches the rest of the app): prices going UP is red, DOWN is green. */

const MI_HORIZONS = ['days', 'weeks', 'months'];
const MI_HORIZON_NAMES = { days: 'Next 1-7 days', weeks: 'Next 2-4 weeks', months: 'Next 2-3 months' };

const MI_EVENT_PRESETS = [
  { label: 'Export ban (supplier country)', title: 'Export ban in effect', category: 'export_ban', direction: 1, magnitude: 3 },
  { label: 'Refinery outage / strikes', title: 'Refinery outages', category: 'refinery_outage', direction: 1, magnitude: 2 },
  { label: 'Shipping disruption (Hormuz, Red Sea)', title: 'Shipping disruption', category: 'shipping', direction: 1, magnitude: 3 },
  { label: 'East Coast pipeline / terminal outage', title: 'Pipeline or terminal outage', category: 'refinery_outage', direction: 1, magnitude: 2 },
  { label: 'Diplomatic progress / ceasefire', title: 'Diplomatic progress', category: 'diplomacy', direction: -1, magnitude: 2 },
  { label: 'Strategic reserve release', title: 'Strategic reserve release', category: 'policy', direction: -1, magnitude: 2 },
];

const miState = { stocksSeries: 'padd1a', charts: {} };

function miEsc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function miFmt(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function miScoreClass(score) {
  if (score === null || score === undefined) return 'mi-na';
  if (score >= 0.35) return 'mi-up';
  if (score <= -0.35) return 'mi-down';
  return 'mi-flat';
}

function miScoreChip(score) {
  if (score === null || score === undefined) return '<span class="mi-chip mi-na">-</span>';
  return `<span class="mi-chip ${miScoreClass(score)}">${score > 0 ? '+' : ''}${score.toFixed(1)}</span>`;
}

function miOutlookBadgeClass(label) {
  if (/Rise|Upward/.test(label)) return 'bg-sentiment-bad';
  if (/Fall|Downward/.test(label)) return 'bg-sentiment-good';
  return 'bg-sentiment-warning';
}

// ------------------------------------------------------------------ top: horizons + weekly strip

function miHorizonCard(h, res, vol) {
  if (!res || res.score === null) {
    return `
      <div class="mi-horizon">
        <div class="mi-h-title">${MI_HORIZON_NAMES[h]}</div>
        <div class="text-sm text-secondary">Not enough data yet. Set up the market data feeds below.</div>
      </div>`;
  }
  const pos = Math.max(0, Math.min(100, (res.score + 2) / 4 * 100));
  const range = vol?.ranges?.[h];
  const drivers = res.drivers.map(d => `<li>${miEsc(d.label)} <span class="text-secondary">${miEsc(d.display)}</span></li>`).join('');
  const against = res.headwinds.map(d => `<li>${miEsc(d.label)} <span class="text-secondary">${miEsc(d.display)}</span></li>`).join('');
  return `
    <div class="mi-horizon">
      <div class="mi-h-title">${MI_HORIZON_NAMES[h]}</div>
      <div class="badge ${miOutlookBadgeClass(res.outlook)} font-bold mi-h-badge">${miEsc(res.outlook)}</div>
      <div class="mi-meter" title="Score ${res.score} (-2 bearish to +2 bullish for prices)">
        <div class="mi-meter-mid"></div><div class="mi-meter-marker" style="left:${pos}%"></div>
      </div>
      <div class="mi-meter-labels"><span>Lower</span><span>Higher</span></div>
      <div class="text-xs text-secondary mb-sm">${miEsc(res.confidence)} confidence &middot; ${res.signals_used} signals &middot; ${Math.round(res.coverage * 100)}% of weight available</div>
      ${drivers ? `<div class="mi-list-title">Pushing prices ${res.score >= 0 ? 'up' : 'down'}</div><ul class="mi-list">${drivers}</ul>` : ''}
      ${against ? `<div class="mi-list-title">Pulling the other way</div><ul class="mi-list">${against}</ul>` : ''}
      ${range ? `<div class="mi-range" title="One standard deviation of recent ULSD volatility. A measure of how far prices typically move, not a forecast.">Typical swing: $${miFmt(range.low, 2)} - $${miFmt(range.high, 2)}/gal</div>` : ''}
    </div>`;
}

function miWeeklyStrip(changes) {
  if (!changes || !changes.length) return '';
  const items = changes.map(c => {
    const cls = c.bullish === null ? 'mi-flat' : (c.bullish ? 'mi-up' : 'mi-down');
    const arrow = c.delta === null || c.delta === 0 ? '' : (c.delta > 0 ? '&uarr;' : '&darr;');
    const big = c.unit === 'kbbl' || c.unit === 'kb/d';
    const now = big ? `${miFmt(c.now / 1000, 1)}M` : miFmt(c.now, c.decimals);
    const delta = c.delta === null ? 'n/a' : (big ? `${c.delta > 0 ? '+' : ''}${miFmt(c.delta / 1000, 2)}M` : `${c.delta > 0 ? '+' : ''}${miFmt(c.delta, c.decimals)}`);
    return `
      <div class="mi-week-item">
        <div class="mi-week-label">${miEsc(c.label)}</div>
        <div class="mi-week-now">${now}</div>
        <div class="mi-week-delta ${cls}">${arrow} ${delta} <span class="text-secondary">7d</span></div>
      </div>`;
  }).join('');
  return `
    <div class="card glass-effect mb-lg">
      <div class="card-header"><div class="card-title">What changed this week</div></div>
      <div class="card-body"><div class="mi-week-grid">${items}</div>
        <p class="text-xs text-secondary" style="margin-top:8px;">Red = pushes prices up, green = pushes prices down. Inventory draws count as upward pressure.</p>
      </div>
    </div>`;
}

// ------------------------------------------------------------------ signals table

function miSignalRows(signals) {
  const groups = {};
  signals.forEach(s => { (groups[s.group] = groups[s.group] || []).push(s); });
  return Object.entries(groups).map(([group, list]) => {
    const rows = list.map(s => {
      const pct = s.percentile === null || s.percentile === undefined ? '' :
        `<div class="mi-pct" title="Percentile vs history"><div class="mi-pct-fill" style="width:${s.percentile}%"></div></div>`;
      const weights = Object.entries(s.weights || {}).map(([h, w]) => `${h} ${w}`).join(' &middot; ');
      if (!s.available) {
        return `
          <tr class="mi-unavailable">
            <td>${miEsc(s.label)}</td>
            <td colspan="4" class="text-secondary text-xs">${miEsc(s.reason)}</td>
          </tr>`;
      }
      return `
        <tr class="mi-row" onclick="miToggleDetail('${s.key}')">
          <td>${miEsc(s.label)}</td>
          <td class="mono text-xs">${miEsc(s.display)}</td>
          ${MI_HORIZONS.map(h => `<td class="text-center">${miScoreChip(s.scores[h])}</td>`).join('')}
        </tr>
        <tr class="mi-detail" id="mi-detail-${s.key}" style="display:none;">
          <td colspan="5">
            <div class="text-xs text-secondary" style="line-height:1.5;">${miEsc(s.detail)}</div>
            ${pct}
            <div class="text-xs text-secondary">Weight by horizon: ${weights || 'n/a'}${s.as_of ? ` &middot; data as of ${miEsc(s.as_of)}` : ''}</div>
          </td>
        </tr>`;
    }).join('');
    return `<tr class="mi-group"><td colspan="5">${miEsc(group)}</td></tr>${rows}`;
  }).join('');
}

function miToggleDetail(key) {
  const el = document.getElementById(`mi-detail-${key}`);
  if (el) el.style.display = el.style.display === 'none' ? 'table-row' : 'none';
}

// ------------------------------------------------------------------ charts

function miDestroy(key) {
  if (miState.charts[key]) {
    try { miState.charts[key].destroy(); } catch (e) { /* already gone */ }
    delete miState.charts[key];
  }
}

function miClearEmpty(canvasId) {
  const el = document.getElementById(canvasId);
  if (!el) return null;
  el.style.display = '';
  const msg = el.parentElement.querySelector('.mi-empty');
  if (msg) msg.remove();
  return el;
}

function miEmpty(canvasId, message) {
  const el = document.getElementById(canvasId);
  if (!el) return;
  el.style.display = 'none';
  let msg = el.parentElement.querySelector('.mi-empty');
  if (!msg) {
    msg = document.createElement('div');
    msg.className = 'mi-empty text-sm text-secondary';
    el.parentElement.appendChild(msg);
  }
  msg.textContent = message;
}

function miRenderCrack(data) {
  miDestroy('crack');
  const canvas = miClearEmpty('miCrackChart');
  if (!canvas) return;
  if (!data.dates.length) return miEmpty('miCrackChart', 'No crack data yet. It needs Brent and ULSD price history (and ICE gasoil from the forward curve feed).');
  const datasets = [{
    label: 'NYMEX HO - Brent', data: data.ho_crack, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.08)',
    fill: true, tension: 0.3, pointRadius: 0, spanGaps: true,
  }];
  if (data.gasoil_crack.some(v => v !== null)) {
    datasets.push({ label: 'ICE gasoil - Brent', data: data.gasoil_crack, borderColor: '#fbbf24', borderDash: [5, 4],
      fill: false, tension: 0.3, pointRadius: 0, spanGaps: true });
  }
  miState.charts.crack = new Chart(canvas.getContext('2d'), {
    type: 'line', data: { labels: data.dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      scales: { x: { type: 'time', time: { unit: 'month' }, grid: { display: false } }, y: { title: { display: true, text: '$/bbl' } } },
    },
  });
}

function miRenderCurve(data) {
  miDestroy('curve');
  const canvas = miClearEmpty('miCurveChart');
  if (!canvas) return;
  if (!data.curves.length) return miEmpty('miCurveChart', 'No forward curve yet. Run the ULSD Forward Curve feed or load a curve manually.');
  const styles = [
    { borderColor: '#ef4444', borderWidth: 2.5 },
    { borderColor: '#fbbf24', borderWidth: 1.5, borderDash: [6, 4] },
    { borderColor: '#38bdf8', borderWidth: 1.5, borderDash: [2, 4] },
  ];
  const datasets = data.curves.map((c, i) => {
    const map = Object.fromEntries(c.points.map(p => [p.month, p.price]));
    return { label: `${c.label} (${c.as_of})`, data: data.months.map(m => map[m] ?? null), tension: 0.25,
      pointRadius: i === 0 ? 3 : 0, spanGaps: true, fill: false, ...styles[i] };
  });
  miState.charts.curve = new Chart(canvas.getContext('2d'), {
    type: 'line', data: { labels: data.months, datasets },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      scales: { y: { title: { display: true, text: '$/gal' } }, x: { grid: { display: false } } },
    },
  });
}

function miRenderStocks(data) {
  miDestroy('stocks');
  const canvas = miClearEmpty('miStocksChart');
  if (!canvas) return;
  if (!data.dates.length) return miEmpty('miStocksChart', 'No inventory data yet. Run the EIA Market Fundamentals feed (needs EIA_API_KEY).');
  const m = arr => arr.map(v => (v === null ? null : v / 1000));
  miState.charts.stocks = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels: data.dates,
      datasets: [
        { label: '5-yr max', data: m(data.band_max), borderColor: 'rgba(148,163,184,0.35)', borderWidth: 1, pointRadius: 0, fill: false, spanGaps: true },
        { label: '5-yr range', data: m(data.band_min), borderColor: 'rgba(148,163,184,0.35)', borderWidth: 1, pointRadius: 0,
          backgroundColor: 'rgba(148,163,184,0.12)', fill: '-1', spanGaps: true },
        { label: '5-yr avg', data: m(data.band_avg), borderColor: 'rgba(148,163,184,0.8)', borderDash: [4, 4], borderWidth: 1, pointRadius: 0, fill: false, spanGaps: true },
        { label: 'Stocks', data: m(data.stocks), borderColor: '#ef4444', borderWidth: 2.5, pointRadius: 0, tension: 0.2, fill: false },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      scales: { x: { type: 'time', time: { unit: 'month' }, grid: { display: false } }, y: { title: { display: true, text: 'Million bbl' } } },
    },
  });
}

async function miChangeStocksSeries(series) {
  miState.stocksSeries = series;
  try {
    miRenderStocks(await api.getMarketStocksChart(series));
  } catch (err) {
    showToast('Could not load inventory chart: ' + err.message, 'error');
  }
}

// ------------------------------------------------------------------ events

function miEventRow(e) {
  const dir = e.direction > 0 ? '<span class="mi-chip mi-up">Bullish</span>' : e.direction < 0 ? '<span class="mi-chip mi-down">Bearish</span>' : '<span class="mi-chip mi-flat">Neutral</span>';
  return `
    <div class="mi-event">
      <div class="mi-event-main">
        <div class="font-bold text-sm">${miEsc(e.title)}</div>
        <div class="text-xs text-secondary">${miEsc(e.category || 'other')} &middot; size ${e.magnitude}/3 &middot; ${miEsc(e.horizon)} &middot; since ${miEsc(e.start_date)}${e.expires_on ? ` &middot; expires ${miEsc(e.expires_on)}` : ''}</div>
      </div>
      <div class="mi-event-actions">${dir}
        <button class="btn btn-ghost btn-sm" onclick="miDeleteEvent(${e.id})" title="Remove event">Remove</button>
      </div>
    </div>`;
}

async function miRefreshEvents() {
  const el = document.getElementById('mi-events-list');
  if (!el) return;
  try {
    const events = await api.getMarketEvents();
    el.innerHTML = events.length ? events.map(miEventRow).join('') :
      '<div class="text-sm text-secondary">No active events. Log supply disruptions or diplomatic news so the model can weigh them.</div>';
  } catch (err) {
    el.innerHTML = `<div class="text-sm text-error">${miEsc(err.message)}</div>`;
  }
}

function miApplyPreset() {
  const idx = document.getElementById('mi-ev-preset').value;
  if (idx === '') return;
  const p = MI_EVENT_PRESETS[Number(idx)];
  document.getElementById('mi-ev-title').value = p.title;
  document.getElementById('mi-ev-category').value = p.category;
  document.getElementById('mi-ev-direction').value = String(p.direction);
  document.getElementById('mi-ev-magnitude').value = String(p.magnitude);
}

async function miAddEvent() {
  const title = document.getElementById('mi-ev-title').value.trim();
  if (!title) { showToast('Give the event a short title', 'error'); return; }
  const expires = document.getElementById('mi-ev-expires').value;
  try {
    await api.createMarketEvent({
      title,
      category: document.getElementById('mi-ev-category').value,
      direction: Number(document.getElementById('mi-ev-direction').value),
      magnitude: Number(document.getElementById('mi-ev-magnitude').value),
      horizon: document.getElementById('mi-ev-horizon').value,
      expires_on: expires || null,
    });
    document.getElementById('mi-ev-title').value = '';
    document.getElementById('mi-ev-expires').value = '';
    showToast('Event added. Refreshing outlook...', 'success');
    await miRefreshEvents();
    renderMarketIntelPanels();
  } catch (err) {
    showToast('Could not add event: ' + err.message, 'error');
  }
}

async function miDeleteEvent(id) {
  try {
    await api.deleteMarketEvent(id);
    await miRefreshEvents();
    renderMarketIntelPanels();
  } catch (err) {
    showToast('Could not remove event: ' + err.message, 'error');
  }
}

// ------------------------------------------------------------------ feeds

function miFeedRows(feeds) {
  return feeds.map(f => {
    const dates = f.series.map(s => s.latest).filter(Boolean).sort();
    const latest = dates.length ? dates[dates.length - 1] : null;
    const status = !f.configured ? ['Not set up', 'badge-warning'] : !f.enabled ? ['Disabled', 'badge-warning'] :
      latest ? ['Receiving data', 'badge-success'] : ['Configured, no data yet', 'badge-info'];
    return `
      <tr>
        <td>${miEsc(f.name)}${f.needs ? `<div class="text-xs text-secondary">needs ${miEsc(f.needs)}</div>` : ''}</td>
        <td><span class="badge ${status[1]}">${status[0]}</span></td>
        <td class="mono text-xs">${latest ? miEsc(latest) : '-'}</td>
        <td class="text-xs text-secondary">${f.last_run ? new Date(f.last_run).toLocaleString() : 'never'}</td>
      </tr>`;
  }).join('');
}

async function miSetupFeeds() {
  const btn = document.getElementById('mi-setup-btn');
  if (btn) btn.disabled = true;
  try {
    const configs = await api.setupMarketFeeds();
    await Promise.all(configs.map(c => api.runScrapeNow(c.config_id)));
    showToast('Market data feeds set up and started. The first run takes a minute or two; refresh afterwards.', 'success');
    setTimeout(() => renderMarketIntelPanels(), 15000);
  } catch (err) {
    showToast('Feed setup failed: ' + err.message, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

function miOpenCurveImport() {
  document.getElementById('modal-title').textContent = 'Load ULSD Forward Curve';
  document.getElementById('modal-body').innerHTML = `
    <p class="text-sm text-secondary mb-md">Paste one line per delivery month as <span class="mono">YYYY-MM, price</span> ($/gal), for example from your supplier's daily market update.</p>
    <div class="form-group"><textarea id="mi-curve-text" class="form-input" rows="8" placeholder="2026-11, 4.52&#10;2026-12, 4.41&#10;2027-01, 4.30"></textarea></div>
    <div class="form-group"><label class="form-label">ICE gasoil front month (USD/tonne, optional)</label>
      <input type="number" step="0.01" id="mi-curve-gasoil" class="form-input"></div>
    <div class="form-group"><label class="form-label">As of</label>
      <input type="date" id="mi-curve-asof" class="form-input" value="${new Date().toISOString().slice(0, 10)}"></div>`;
  document.getElementById('modal-confirm').onclick = async () => {
    const rows = [];
    for (const line of document.getElementById('mi-curve-text').value.split('\n')) {
      const t = line.trim();
      if (!t) continue;
      const m = t.match(/^(\d{4}-\d{2})\s*[,\t ]\s*([\d.]+)$/);
      if (!m) { showToast(`Could not read line: "${t}"`, 'error'); return; }
      rows.push({ month: m[1], price: Number(m[2]) });
    }
    if (!rows.length) { showToast('Enter at least one month', 'error'); return; }
    const gasoil = document.getElementById('mi-curve-gasoil').value;
    try {
      await api.importMarketCurve({
        as_of: document.getElementById('mi-curve-asof').value || null,
        rows, gasoil_usd_per_tonne: gasoil ? Number(gasoil) : null,
      });
      closeModal();
      showToast('Curve loaded', 'success');
      renderMarketIntelPanels();
    } catch (err) {
      showToast('Import failed: ' + err.message, 'error');
    }
  };
  openModal();
}

// ------------------------------------------------------------------ backtest

async function miRunBacktest() {
  const out = document.getElementById('mi-backtest-out');
  const btn = document.getElementById('mi-backtest-btn');
  if (btn) btn.disabled = true;
  out.innerHTML = '<div class="text-sm text-secondary">Replaying history...</div>';
  try {
    const bt = await api.getMarketBacktest(365, 7);
    if (bt.error) { out.innerHTML = `<div class="text-sm text-secondary">${miEsc(bt.error)}</div>`; return; }
    const rows = MI_HORIZONS.map(h => {
      const r = bt.horizons[h];
      const pct = v => (v === null || v === undefined ? '-' : `${v > 0 ? '+' : ''}${v}%`);
      return `<tr>
        <td>${MI_HORIZON_NAMES[h]}</td><td>${r.samples}</td>
        <td>${r.hit_rate === null ? '-' : r.hit_rate + '%'} <span class="text-xs text-secondary">(${r.directional_calls} calls)</span></td>
        <td>${r.correlation === null ? '-' : r.correlation}</td>
        <td>${pct(r.avg_move_when_bullish_pct)}</td><td>${pct(r.avg_move_when_bearish_pct)}</td><td>${pct(r.avg_move_when_stable_pct)}</td>
      </tr>`;
    }).join('');
    const perSignal = MI_HORIZONS.map(h => {
      const list = bt.horizons[h].signals.slice(0, 8).map(s =>
        `<tr><td>${miEsc(s.key)}</td><td>${s.samples}</td><td>${s.correlation === null ? '-' : s.correlation}</td><td>${s.hit_rate}%</td></tr>`).join('');
      return `<details class="mi-backtest-detail"><summary class="text-sm">Per-signal results: ${MI_HORIZON_NAMES[h]}</summary>
        <table class="data-table"><thead><tr><th>Signal</th><th>Samples</th><th>Correlation</th><th>Hit rate</th></tr></thead><tbody>${list || '<tr><td colspan="4">No data</td></tr>'}</tbody></table></details>`;
    }).join('');
    out.innerHTML = `
      <div class="table-responsive-wrapper"><table class="data-table">
        <thead><tr><th>Horizon</th><th>Weeks tested</th><th>Direction hit rate</th><th>Score vs move</th><th>Avg move when bullish</th><th>when bearish</th><th>when stable</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      ${perSignal}
      <p class="text-xs text-secondary" style="margin-top:8px;">${miEsc(bt.caveat)}</p>`;
  } catch (err) {
    out.innerHTML = `<div class="text-sm text-error">${miEsc(err.message)}</div>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ------------------------------------------------------------------ orchestration

function miBottomShell() {
  return `
    <div class="card glass-effect mb-lg animate-fade-in">
      <div class="card-header">
        <div class="card-title">Signal breakdown</div>
        <span class="text-xs text-secondary">Scores: -2 prices fall, +2 prices rise. Click a row for detail.</span>
      </div>
      <div class="card-body" style="padding: var(--space-sm);">
        <div class="table-responsive-wrapper">
          <table class="data-table mi-table">
            <thead><tr><th>Signal</th><th>Reading</th><th class="text-center">Days</th><th class="text-center">Weeks</th><th class="text-center">Months</th></tr></thead>
            <tbody id="mi-signal-rows"><tr><td colspan="5" class="text-secondary text-center">Loading signals...</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="analytics-charts-grid mb-lg">
      <div class="card glass-effect">
        <div class="card-header"><div class="card-title">Distillate crack spread</div></div>
        <div class="card-body">
          <p class="text-xs text-secondary mb-sm">Heating oil and ICE gasoil margin over Brent. The key gauge of distillate scarcity.</p>
          <div class="chart-container" style="height: 260px;"><canvas id="miCrackChart"></canvas></div>
        </div>
      </div>
      <div class="card glass-effect">
        <div class="card-header"><div class="card-title">ULSD forward curve</div>
          <button class="btn btn-ghost btn-sm" onclick="miOpenCurveImport()">Load manually</button></div>
        <div class="card-body">
          <p class="text-xs text-secondary mb-sm">Price by delivery month. Falling to the right (backwardation) means the market expects prices to ease.</p>
          <div class="chart-container" style="height: 260px;"><canvas id="miCurveChart"></canvas></div>
        </div>
      </div>
    </div>

    <div class="card glass-effect mb-lg">
      <div class="card-header">
        <div class="card-title">Distillate inventories vs 5-year range</div>
        <select class="form-select form-select-sm" style="width:auto;" onchange="miChangeStocksSeries(this.value)">
          <option value="padd1a">New England (PADD 1A)</option>
          <option value="padd1">East Coast (PADD 1)</option>
          <option value="us">United States</option>
        </select>
      </div>
      <div class="card-body">
        <div class="chart-container" style="height: 260px;"><canvas id="miStocksChart"></canvas></div>
      </div>
    </div>

    <div class="analytics-charts-grid mb-lg">
      <div class="card glass-effect">
        <div class="card-header"><div class="card-title">Event log</div></div>
        <div class="card-body">
          <p class="text-xs text-secondary mb-sm">Supply shocks and diplomacy move prices faster than any feed. Log what you see; the model weighs each by size and horizon.</p>
          <div class="mi-event-form">
            <select id="mi-ev-preset" class="form-select form-select-sm" onchange="miApplyPreset()">
              <option value="">Quick fill...</option>
              ${MI_EVENT_PRESETS.map((p, i) => `<option value="${i}">${miEsc(p.label)}</option>`).join('')}
            </select>
            <input id="mi-ev-title" class="form-input form-input-sm" maxlength="255" placeholder="Event title">
            <select id="mi-ev-direction" class="form-select form-select-sm">
              <option value="1">Bullish (prices up)</option><option value="-1">Bearish (prices down)</option><option value="0">Neutral</option>
            </select>
            <select id="mi-ev-magnitude" class="form-select form-select-sm">
              <option value="1">Minor</option><option value="2">Moderate</option><option value="3">Major</option>
            </select>
            <select id="mi-ev-horizon" class="form-select form-select-sm">
              <option value="all">All horizons</option><option value="days">Days</option><option value="weeks">Weeks</option><option value="months">Months</option>
            </select>
            <select id="mi-ev-category" class="form-select form-select-sm">
              <option value="other">Other</option><option value="export_ban">Export ban</option><option value="refinery_outage">Refinery / terminal</option>
              <option value="shipping">Shipping</option><option value="diplomacy">Diplomacy</option><option value="policy">Policy</option><option value="weather">Weather</option>
            </select>
            <label class="text-xs text-secondary">Expires <input id="mi-ev-expires" type="date" class="form-input form-input-sm"></label>
            <button class="btn btn-primary btn-sm" onclick="miAddEvent()">Add event</button>
          </div>
          <div id="mi-events-list" style="margin-top: var(--space-md);"></div>
        </div>
      </div>

      <div class="card glass-effect">
        <div class="card-header"><div class="card-title">Data feeds</div>
          <button class="btn btn-primary btn-sm" id="mi-setup-btn" onclick="miSetupFeeds()">Set up &amp; run feeds</button></div>
        <div class="card-body" style="padding: var(--space-sm);">
          <div class="table-responsive-wrapper"><table class="data-table">
            <thead><tr><th>Feed</th><th>Status</th><th>Latest data</th><th>Last run</th></tr></thead>
            <tbody id="mi-feed-rows"><tr><td colspan="4" class="text-secondary text-center">Loading...</td></tr></tbody>
          </table></div>
          <p class="text-xs text-secondary" style="padding: 8px;">The forward curve feed uses a free source that sometimes blocks servers. If it shows no data, use "Load manually" on the curve chart.</p>
        </div>
      </div>
    </div>

    <div class="card glass-effect mb-lg">
      <div class="card-header"><div class="card-title">Backtest</div>
        <button class="btn btn-ghost btn-sm" id="mi-backtest-btn" onclick="miRunBacktest()">Run backtest</button></div>
      <div class="card-body">
        <p class="text-xs text-secondary mb-sm">Replays the past year week by week and compares each outlook with what ULSD actually did. Treat as a sanity check on the weights, not proof of skill.</p>
        <div id="mi-backtest-out"></div>
      </div>
    </div>`;
}

async function renderMarketIntelPanels() {
  const top = document.getElementById('mi-top');
  const bottom = document.getElementById('mi-bottom');
  if (!top || !bottom) return;
  if (!bottom.dataset.ready) {
    bottom.innerHTML = miBottomShell();
    bottom.dataset.ready = '1';
    miRefreshEvents();
  }

  const [signals, weekly, crack, curve, stocks, feeds] = await Promise.allSettled([
    api.getMarketSignals(), api.getMarketWeeklyChanges(), api.getMarketCrackChart(),
    api.getMarketCurveChart(), api.getMarketStocksChart(miState.stocksSeries), api.getMarketFeeds(),
  ]);

  if (signals.status === 'fulfilled') {
    const o = signals.value;
    const missing = o.unavailable.length;
    top.innerHTML = `
      <div class="card glass-effect mb-lg animate-fade-in" style="border-left: 4px solid var(--accent-primary);">
        <div class="card-header">
          <div class="card-title">Outlook by horizon</div>
          <span class="text-xs text-secondary">${o.signals_available} of ${o.signals_total} signals live${missing ? ` &middot; ${missing} waiting on data` : ''}</span>
        </div>
        <div class="card-body">
          <div class="mi-horizon-grid">${MI_HORIZONS.map(h => miHorizonCard(h, o.horizons[h], o.volatility)).join('')}</div>
          <p class="text-xs text-secondary" style="margin-top:12px;">A transparent scoring of market signals, not a guarantee. Headlines can reverse the call quickly, so keep the event log current.</p>
        </div>
      </div>
      ${weekly.status === 'fulfilled' ? miWeeklyStrip(weekly.value) : ''}`;
    const rowsEl = document.getElementById('mi-signal-rows');
    if (rowsEl) rowsEl.innerHTML = miSignalRows(o.signals);
  } else {
    top.innerHTML = `<div class="card mb-lg"><div class="card-body text-sm text-error">Could not load the outlook: ${miEsc(signals.reason?.message)}</div></div>`;
  }

  if (crack.status === 'fulfilled') miRenderCrack(crack.value);
  if (curve.status === 'fulfilled') miRenderCurve(curve.value);
  if (stocks.status === 'fulfilled') miRenderStocks(stocks.value);
  const feedRows = document.getElementById('mi-feed-rows');
  if (feedRows && feeds.status === 'fulfilled') feedRows.innerHTML = miFeedRows(feeds.value);
}

window.renderMarketIntelPanels = renderMarketIntelPanels;
window.miToggleDetail = miToggleDetail;
window.miChangeStocksSeries = miChangeStocksSeries;
window.miApplyPreset = miApplyPreset;
window.miAddEvent = miAddEvent;
window.miDeleteEvent = miDeleteEvent;
window.miSetupFeeds = miSetupFeeds;
window.miOpenCurveImport = miOpenCurveImport;
window.miRunBacktest = miRunBacktest;
