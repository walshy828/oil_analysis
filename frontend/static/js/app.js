/**
 * Oil Price Tracker - Main Application
 */

// State
let currentPage = 'dashboard';
let locations = [];
let companies = [];

// Analytics State
let analyticsStartDate = null;
let analyticsEndDate = null;
let analyticsAggregation = 'daily';
let yoyMetric = 'usage_gallons';
let yoyYear = new Date().getFullYear();

// ==================== Initialization ====================

document.addEventListener('DOMContentLoaded', async () => {
  // Handle navigation
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const page = item.dataset.page;
      navigateTo(page);
    });
  });

  // Handle hash navigation
  window.addEventListener('hashchange', () => {
    const page = window.location.hash.slice(1) || 'dashboard';
    navigateTo(page, false);
  });

  // Load reference data FIRST before rendering any page
  await loadReferenceData();

  // Load initial page after data is ready
  const initialPage = window.location.hash.slice(1) || 'dashboard';
  navigateTo(initialPage, false);
});

async function loadReferenceData() {
  try {
    [locations, companies] = await Promise.all([
      api.getLocations(),
      api.getCompanies(),
    ]);
  } catch (error) {
    console.error('Failed to load reference data:', error);
  }
}

// ==================== Navigation ====================

function navigateTo(page, updateHash = true) {
  currentPage = page;

  // Update URL hash
  if (updateHash) {
    window.location.hash = page;
  }

  // Update active nav item
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.page === page);
  });

  // Close mobile sidebar
  document.getElementById('sidebar').classList.remove('open');

  // Render page
  renderPage(page);
}

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  sidebar.classList.toggle('open');
  if (overlay) {
    overlay.classList.toggle('active', sidebar.classList.contains('open'));
  }
}

function toggleSidebarCollapse() {
  const sidebar = document.getElementById('sidebar');
  sidebar.classList.toggle('collapsed');

  // Switch icon orientation
  const btn = document.getElementById('sidebar-collapse-btn');
  if (sidebar.classList.contains('collapsed')) {
    btn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect>
                <line x1="9" y1="3" x2="9" y2="21"></line>
                <path d="m13 9 3 3-3 3"></path>
            </svg>
        `;
  } else {
    btn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect>
                <line x1="9" y1="3" x2="9" y2="21"></line>
                <path d="m15 9-3 3 3 3"></path>
            </svg>
        `;
  }

  // Expert UX: Resize charts after sidebar transition
  setTimeout(() => {
    if (typeof resizeAllCharts === 'function') {
      resizeAllCharts();
    }
  }, 250);
}

// ==================== Page Rendering ====================

async function renderPage(page) {
  const container = document.getElementById('page-content');
  container.innerHTML = '<div class="loading-container"><div class="loading-spinner"></div></div>';

  try {
    switch (page) {
      case 'dashboard':
        await renderDashboard(container);
        break;
      case 'analytics':
        await renderAnalyticsPage(container);
        break;
      case 'yoy':
        await renderYoYPage(container);
        break;
      case 'prices':
        await renderPricesPage(container);
        break;
      case 'orders':
        await renderOrdersPage(container);
        break;
      case 'locations':
        await renderLocationsPage(container);
        break;
      case 'companies':
        await renderCompaniesPage(container);
        break;
      case 'usage':
        renderUsagePage(container);
        break;
      case 'settings':
        await renderSettingsPage(container);
        break;
      case 'scrape':
        await renderScrapePage(container);
        break;
      default:
        container.innerHTML = '<div class="page-body"><h1>Page Not Found</h1></div>';
    }
  } catch (error) {
    container.innerHTML = `
      <div class="page-body">
        <div class="empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <h3 class="empty-state-title">Error Loading Page</h3>
          <p class="empty-state-text">${error.message}</p>
          <button class="btn btn-primary" onclick="renderPage('${page}')">Retry</button>
        </div>
      </div>
    `;
  }
}

async function renderYoYPage(container) {
  const data = await api.getYoYComparison(yoyYear);

  // Calculate high-level insights
  const curTotalGallons = data.current.reduce((sum, m) => sum + m.usage_gallons, 0);
  const prevTotalGallons = data.previous.reduce((sum, m) => sum + m.usage_gallons, 0);
  const curTotalHDD = data.current.reduce((sum, m) => sum + m.total_hdd, 0);
  const prevTotalHDD = data.previous.reduce((sum, m) => sum + m.total_hdd, 0);
  const curTotalCost = data.current.reduce((sum, m) => sum + m.usage_cost, 0);
  const prevTotalCost = data.previous.reduce((sum, m) => sum + m.usage_cost, 0);

  const gallonDiff = curTotalGallons - prevTotalGallons;
  const costDiff = curTotalCost - prevTotalCost;
  const hddDiff = curTotalHDD - prevTotalHDD;

  const avgPrice = curTotalGallons > 0 ? curTotalCost / curTotalGallons : 0;
  const prevAvgPrice = prevTotalGallons > 0 ? prevTotalCost / prevTotalGallons : 0;
  const priceDiff = avgPrice - prevAvgPrice;

  // Build year options
  const yearOptions = [0, 1, 2, 3, 4].map(i => {
    const y = new Date().getFullYear() - i;
    return { value: y.toString(), label: y.toString(), selected: y === yoyYear };
  });

  // Build metric options  
  const metricOptions = [
    { value: 'usage_gallons', label: 'Gallons Consumed', selected: yoyMetric === 'usage_gallons' },
    { value: 'usage_cost', label: 'Consumption Cost', selected: yoyMetric === 'usage_cost' },
    { value: 'total_hdd', label: 'Degree Days (HDD)', selected: yoyMetric === 'total_hdd' },
    { value: 'avg_price', label: 'Avg Price/Gallon', selected: yoyMetric === 'avg_price' },
    { value: 'usage_per_day', label: 'Usage (Gal/Day)', selected: yoyMetric === 'usage_per_day' }
  ];

  // Build unified header
  const headerHtml = generateUnifiedHeader({
    title: 'YoY Intelligence',
    subtitle: `Comparing ${yoyYear} vs ${yoyYear - 1}`,
    primaryActions: [],
    secondaryActions: [],
    controls: [
      {
        label: 'Year',
        items: [
          {
            type: 'select',
            id: 'yoy-year-select',
            onchange: 'document.getElementById(\"yoy-year-select\").dispatchEvent(new Event(\"change\"))',
            options: yearOptions
          }
        ]
      },
      {
        label: 'Metric',
        items: [
          {
            type: 'select',
            id: 'yoy-metric-select',
            onchange: 'document.getElementById(\"yoy-metric-select\").dispatchEvent(new Event(\"change\"))',
            options: metricOptions
          }
        ]
      }
    ]
  });

  container.innerHTML = `
    ${headerHtml}
    <div class="page-body">

      
      <!-- YoY Synthesis Insights -->
      <div class="yoy-insight-grid">
         <div class="correlation-card">
            <div class="kpi-mini-label">Efficiency Delta</div>
            <div class="kpi-mini-value ${hddDiff > 0 && gallonDiff < 0 ? 'sentiment-good' : (hddDiff < 0 && gallonDiff > 0 ? 'sentiment-bad' : '')}">
                ${gallonDiff > 0 ? '+' : ''}${gallonDiff.toFixed(0)} gal
            </div>
            <p class="text-xs text-secondary mt-xs">
                ${gallonDiff > 0 ? 'Higher consumption' : 'Saved fuel'} vs last year. 
                ${Math.abs(hddDiff) > 50 ? `Market context: This year was <strong>${hddDiff > 0 ? 'colder' : 'warmer'}</strong> than last.` : 'Weather was comparable.'}
            </p>
         </div>
         <div class="correlation-card">
            <div class="kpi-mini-label">Price Impact</div>
            <div class="kpi-mini-value ${priceDiff > 0 ? 'sentiment-bad' : 'sentiment-good'}">
                ${priceDiff > 0 ? '+' : ''}${formatCurrency(priceDiff)}/gal
            </div>
            <p class="text-xs text-secondary mt-xs">
                Unit price shift. ${priceDiff > 0 ? 'Market inflation' : 'Market cooling'} 
                contributed <strong>${formatCurrency(Math.abs(priceDiff * curTotalGallons))}</strong> to your total cost shift.
            </p>
         </div>
         <div class="correlation-card">
            <div class="kpi-mini-label">Total Spend Shift</div>
            <div class="kpi-mini-value ${costDiff > 0 ? 'sentiment-bad' : 'sentiment-good'}">
                ${costDiff > 0 ? '+' : ''}${formatCurrency(costDiff)}
            </div>
            <p class="text-xs text-secondary mt-xs">
                Combined effect of weather and pricing. ${costDiff > 0 ? 'Higher annual liability.' : 'Annual budget relief.'}
            </p>
         </div>
      </div>

      <div class="grid grid-2-1 gap-lg">
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">${yoyMetric.charAt(0).toUpperCase() + yoyMetric.slice(1).replace('_', ' ')} Trend</h3>
            </div>
            <div class="card-body">
                <div class="chart-container" style="height: 350px;">
                    <canvas id="yoy-chart"></canvas>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3 class="card-title">Economic Variables</h3>
            </div>
            <div class="card-body">
                <div class="help-text-box">
                    <span class="variable-tag">HDD</span>
                    <strong>Heating Degree Days:</strong> A measure of how much (in degrees) and for how long (in days) the outside air temperature was below 65°F. 
                    <br><br>
                    <span class="text-xs italic">Impact: Higher HDD = More Burn. Use this to debunk price hikes vs weather spikes.</span>
                </div>
                <div class="help-text-box mt-md">
                    <span class="variable-tag">Cost</span>
                    <strong>Usage-Based Cost:</strong> Calculated by applying the average local price at the time of burn to your gallons consumed.
                </div>
            </div>
        </div>
      </div>

      <div class="card mt-lg">
        <div class="card-header">
            <h3 class="card-title">Monthly Detailed Comparison</h3>
        </div>
        <div class="card-body">
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Month</th>
                  <th>${data.current_year}</th>
                  <th>${data.previous_year}</th>
                  <th>Change</th>
                  <th>HDD Shift</th>
                  <th>Temp (Avg)</th>
                </tr>
              </thead>
              <tbody>
                ${data.current.map((curr, i) => {
    const prev = data.previous[i];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const valCurr = curr[yoyMetric] || 0;
    const valPrev = prev[yoyMetric] || 0;
    const diff = valCurr - valPrev;
    const pct = valPrev !== 0 ? ((diff / valPrev) * 100).toFixed(1) + '%' : '-';
    const isCurrency = yoyMetric.includes('cost') || yoyMetric === 'avg_price';
    const hddShift = curr.total_hdd - prev.total_hdd;

    return `
                    <tr>
                      <td class="font-bold">${months[i]}</td>
                      <td class="mono">${isCurrency ? formatCurrency(valCurr) : valCurr.toFixed(1)}</td>
                      <td class="mono">${isCurrency ? formatCurrency(valPrev) : valPrev.toFixed(1)}</td>
                      <td class="mono ${diff > 0 ? 'sentiment-bad' : (diff < 0 ? 'sentiment-good' : '')}">
                        ${diff > 0 ? '+' : ''}${isCurrency ? formatCurrency(diff) : diff.toFixed(1)} (${pct})
                      </td>
                      <td class="mono ${hddShift > 0 ? 'sentiment-bad' : 'sentiment-good'}">
                        ${hddShift > 0 ? '+' : ''}${hddShift.toFixed(0)}
                      </td>
                      <td class="mono">${curr.avg_temp ? curr.avg_temp + '°F' : '-'}</td>
                    </tr>
                  `;
  }).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `;

  // Chart
  const chartCtx = document.getElementById('yoy-chart');
  if (chartCtx) {
    storeChart('yoy', createYoYComparisonChart(chartCtx, data, yoyMetric));
  }

  // Events
  document.getElementById('yoy-year-select').addEventListener('change', (e) => {
    yoyYear = parseInt(e.target.value);
    renderYoYPage(container);
  });

  document.getElementById('yoy-metric-select').addEventListener('change', (e) => {
    yoyMetric = e.target.value;
    renderYoYPage(container);
  });
}

// ==================== Dashboard ====================

async function renderDashboard(container) {
  const d = new Date();
  const todayStr = getLocalDateString(d);
  d.setDate(d.getDate() - 90);
  const startStr = getLocalDateString(d);

  const [summary, priceTrends, orderInsights, tempCorrelation, leadLag, latestPrices, crackSpread] = await Promise.all([
    api.getDashboardSummary(),
    api.getPriceTrends(90),
    api.getOrderInsights(),
    api.getTemperatureCorrelation(),
    api.getLeadLagAnalysis(startStr, todayStr),
    api.getLatestPrices({ type: 'local' }),
    api.getCrackSpread(startStr, todayStr)
  ]);

  // --- Market Snapshot Logic ---
  let snapshotHtml = '';
  if (latestPrices && latestPrices.length > 0) {
    // Use all latest prices as requested (no filtering by freshness)
    const activePrices = latestPrices;

    const prices = activePrices.map(p => p.price_per_gallon);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const avgPrice = prices.reduce((a, b) => a + b, 0) / prices.length;
    const spread = maxPrice - minPrice;

    // Stale Data Check (24 hours)
    const lastUpdateTimes = activePrices.map(p => new Date(p.scraped_at || p.date_reported).getTime());
    const mostRecentMs = Math.max(...lastUpdateTimes);
    const hoursSinceUpdate = (new Date().getTime() - mostRecentMs) / (1000 * 60 * 60);
    const isStale = hoursSinceUpdate > 24;

    // Vendor Spread Visualization
    // Vendor Spread Visualization
    // Group prices to handle overlaps
    const priceGroups = {};
    activePrices.forEach(p => {
      const priceKey = p.price_per_gallon.toFixed(3);
      if (!priceGroups[priceKey]) priceGroups[priceKey] = [];
      priceGroups[priceKey].push(p);
    });

    const vendorDots = Object.values(priceGroups).sort((a, b) => a[0].price_per_gallon - b[0].price_per_gallon).map(group => {
      const p = group[0]; // Representative
      const count = group.length;

      const pct = spread > 0 ? ((p.price_per_gallon - minPrice) / spread) * 100 : 0;
      const isCheapest = p.price_per_gallon === minPrice;
      const color = isCheapest ? 'var(--accent-success)' : 'rgba(255,255,255,0.4)';
      const zIndex = isCheapest ? 20 : 10;

      // Make dot slightly larger if it represents multiple vendors
      let size = isCheapest ? 14 : 8;
      if (count > 1 && !isCheapest) size = 10;
      if (count > 1 && isCheapest) size = 16;

      // Smart Tooltip Layout
      let tooltipClass = 'tooltip-center';
      if (pct < 20) tooltipClass = 'tooltip-left';
      else if (pct > 80) tooltipClass = 'tooltip-right';

      // Format date (use latest from group)
      const dates = group.map(g => new Date(g.date_reported));
      const maxDate = new Date(Math.max(...dates));
      const dateStr = maxDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

      // Build Tooltip Text
      let tooltipText;
      const priceStr = `$${p.price_per_gallon.toFixed(3)}`;

      if (count === 1) {
        tooltipText = `${p.company_name}\n${priceStr} • ${dateStr}`;
      } else {
        // List up to 3 names, then "+ X others"
        const names = group.map(g => g.company_name);
        let nameStr = names.slice(0, 3).join(', ');
        if (names.length > 3) nameStr += ` (+${names.length - 3} others)`;
        tooltipText = `${count} Vendors @ ${priceStr}\n${nameStr}\n${dateStr}`;
      }

      return `<div class="vendor-dot ${tooltipClass}" 
                  style="left:${pct}%; background:${color}; z-index:${zIndex}; width:${size}px; height:${size}px;"
                  data-tooltip="${tooltipText}"></div>`;
    }).join('');

    // --- Advanced Prediction Logic ---
    const trend7d = leadLag.analysis?.local_trends?.['7d'] || 0;
    const predictedDir = leadLag.prediction?.direction || (trend7d > 0 ? 'UP' : 'DOWN');
    const isPredictedUp = predictedDir === 'UP';
    const spreadTrend = crackSpread.analysis?.trend_direction || 'neutral';

    let biasText = '';
    if (spreadTrend === 'widening') biasText = ' and widening refinery margins';
    if (spreadTrend === 'narrowing') biasText = ' despite narrowing refinery margins';

    const trendLabel = isPredictedUp ? 'Trending Up' : 'Trending Down';
    const trendIcon = isPredictedUp ? '↗' : '↘';
    const trendClass = isPredictedUp ? 'sentiment-bad' : 'sentiment-good';
    const cheapestVendor = activePrices.find(p => p.price_per_gallon === minPrice);

    snapshotHtml = `
      <div class="card mb-lg animate-fade-in" style="border-left: 4px solid ${isPredictedUp ? 'var(--accent-error)' : 'var(--accent-success)'};">
        <div class="card-header border-0 pb-0" style="border-bottom: none;">
             <div class="flex flex-between align-center w-full">
                <h3 class="card-title">Market Snapshot & Vendor Spread</h3>
                <div class="flex gap-sm align-center">
                    ${isStale ? `<span class="badge bg-warning text-dark flex items-center gap-xs" style="background:var(--accent-warning); color:#000;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                        DATA STALE
                    </span>` : ''}
                    <div class="badge ${trendClass} flex items-center gap-xs">
                        <span style="font-size:1.2em; line-height:1;">${trendIcon}</span>
                        <span>${trendLabel}</span>
                    </div>
                </div>
             </div>
        </div>
        <div class="card-body">
           ${isStale ? `
           <div class="alert alert-warning mb-md flex flex-between align-center" style="background: rgba(251, 191, 36, 0.1); border: 1px solid rgba(251, 191, 36, 0.3); color: var(--accent-warning);">
              <span>Local market data is ${hoursSinceUpdate.toFixed(0)} hours old.</span>
              <button class="btn btn-sm btn-outline-warning" onclick="runQuickScrape()">Refresh Now</button>
           </div>` : ''}

           <div class="flex flex-column gap-lg">
             <!-- Metrics Grid -->
             <div class="grid grid-3 gap-md mobile-grid-1">
                 <!-- Lowest -->
                 <div class="p-md rounded" style="background: var(--bg-secondary);">
                     <div class="text-xs text-secondary uppercase tracking-wider mb-xs">Lowest Price</div>
                     <div class="flex align-baseline gap-xs">
                       <span class="text-2xl font-bold font-mono text-success">$${minPrice.toFixed(3)}</span>
                     </div>
                     <div class="text-sm text-secondary truncate" title="${cheapestVendor?.company_name}">${cheapestVendor?.company_name}</div>
                 </div>
                 <!-- Average -->
                 <div class="p-md rounded" style="background: var(--bg-secondary);">
                     <div class="text-xs text-secondary uppercase tracking-wider mb-xs">Market Average</div>
                     <div class="flex align-baseline gap-xs">
                       <span class="text-2xl font-bold font-mono">$${avgPrice.toFixed(3)}</span>
                     </div>
                     <div class="text-sm text-secondary">
                        <span class="${avgPrice > minPrice ? 'text-error' : 'text-success'}">+${(avgPrice - minPrice).toFixed(2)} vs Low</span>
                     </div>
                 </div>
                 <!-- Spread -->
                 <div class="p-md rounded" style="background: var(--bg-secondary);">
                      <div class="text-xs text-secondary uppercase tracking-wider mb-xs">Spread</div>
                      <div class="flex align-baseline gap-xs">
                        <span class="text-2xl font-bold font-mono">$${spread.toFixed(2)}</span>
                      </div>
                      <div class="text-sm text-secondary">High: $${maxPrice.toFixed(3)}</div>
                 </div>
             </div>

             <!-- Analyst Prediction Box -->
             <div class="p-md rounded flex gap-md items-start" 
                  style="background: var(--bg-tertiary); border-left: 3px solid ${isPredictedUp ? 'var(--accent-error)' : 'var(--accent-success)'}">
                  <div class="mt-xs text-2xl hidden-mobile">
                     ${isPredictedUp ? '📈' : '📉'}
                  </div>
                  <div>
                     <div class="font-bold mb-xs text-sm uppercase text-secondary">Analyst Prediction</div>
                     <div class="text-base text-primary" style="line-height: 1.5;">
                         The lowest vendor is expected to <strong class="${trendClass}">${isPredictedUp ? 'RISE' : 'FALL'}</strong> 
                         based on ULSD signals${biasText}.
                     </div>
                  </div>
             </div>

             <!-- Visualization -->
             <div>
                <div class="flex flex-between align-end mb-sm">
                    <span class="text-xs font-bold uppercase text-secondary">Full Vendor Spread</span>
                    <span class="text-xs text-secondary">${activePrices.length} companies</span>
                </div>
                <div class="market-spread-viz">
                   <div class="spread-track"></div>
                   ${vendorDots}
                   <div class="spread-labels">
                      <span class="text-xs text-secondary">$${minPrice.toFixed(2)}</span>
                      <span class="text-xs text-secondary" style="left: 50%; transform: translateX(-50%); position: absolute;">Avg: $${avgPrice.toFixed(2)}</span>
                      <span class="text-xs text-secondary">$${maxPrice.toFixed(2)}</span>
                   </div>
                </div>
             </div>
           </div>
        </div>
      </div>
    `;

  }

  // Build unified header
  const headerHtml = generateUnifiedHeader({
    title: 'Dashboard',
    subtitle: `Market Overview – ${todayStr}`,
    primaryActions: [
      {
        label: 'Refresh Prices',
        icon: headerIcons.refresh,
        onclick: 'runQuickScrape()',
        class: 'btn-primary'
      }
    ],
    secondaryActions: []
  });

  container.innerHTML = `
    ${headerHtml}

    <div class="page-body">
      <!-- KPI Cards -->
      <div class="kpi-grid mb-lg">
        <div class="kpi-card">
          <div class="kpi-label">Current Low Price</div>
          <div class="kpi-value mono">${summary.latest_price ? `$${summary.latest_price.price.toFixed(3)}` : 'N/A'}</div>
          <div class="kpi-meta">${summary.latest_price?.company || 'No data'}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">30-Day Average</div>
          <div class="kpi-value mono">${summary.avg_price_30d ? `$${summary.avg_price_30d.toFixed(3)}` : 'N/A'}</div>
          <div class="kpi-meta">Per gallon</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Days Since Delivery</div>
          <div class="kpi-value mono ${summary.days_since_delivery > 60 ? 'negative' : ''}">${summary.days_since_delivery ?? 'N/A'}</div>
          <div class="kpi-meta">${summary.last_order ? `Last: ${formatDate(summary.last_order.date)}` : 'No orders'}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Year to Date</div>
          <div class="kpi-value mono">${formatCurrency(summary.year_to_date?.total_cost || 0)}</div>
          <div class="kpi-meta">${summary.year_to_date?.total_gallons?.toFixed(0) || 0} gallons</div>
        </div>
      </div>

      <!-- New Market Snapshot Module -->
      ${snapshotHtml}

      <!-- Charts -->
      <div class="chart-grid">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Price Trends (90 Days)</h3>
          </div>
          <div class="card-body">
            <div class="chart-container">
              <canvas id="price-trend-chart"></canvas>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Long-Term Order Analysis</h3>
          </div>
          <div class="card-body">
            <p class="text-xs text-secondary mb-md">Comparison of yearly gallons, total spend, and average price.</p>
            <div class="chart-container">
              <canvas id="order-chart"></canvas>
            </div>
          </div>
        </div>
      </div>

      <div class="card mt-lg">
        <div class="card-header">
          <h3 class="card-title">Temperature & Usage Correlation</h3>
        </div>
        <div class="card-body">
          <div class="chart-container">
            <canvas id="temp-chart"></canvas>
          </div>
        </div>
      </div>
    </div>
  `;

  // Initialize charts
  if (priceTrends.labels?.length > 0) {
    const priceCtx = document.getElementById('price-trend-chart');
    storeChart('price-trend', createPriceTrendChart(priceCtx, priceTrends));
  }

  if (orderInsights && orderInsights.length > 0) {
    const orderCtx = document.getElementById('order-chart');
    storeChart('order-chart', createYearlyOrderInsightChart(orderCtx, orderInsights));
  }

  const tempCtx = document.getElementById('temp-chart');
  if (tempCorrelation.temperatures?.labels?.length > 0) {
    storeChart('temp-chart', createTemperatureChart(tempCtx, tempCorrelation));
  } else {
    tempCtx.parentElement.innerHTML = `
      <div class="empty-state" style="padding: var(--space-xl) 0;">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--text-tertiary); margin-bottom: var(--space-md);">
              <path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"></path>
          </svg>
          <h3 class="empty-state-title">No Weather Data</h3>
          <p class="empty-state-text">Configure a location to see temperature correlation.</p>
      </div>
    `;
  }
}

async function runQuickScrape() {
  try {
    const configs = await api.getScrapeConfigs();
    const oilConfig = configs.find(c => c.scraper_type === 'newengland_oil');

    if (oilConfig) {
      await api.runScrapeNow(oilConfig.id);
      showToast('Scrape started! Refresh in a moment to see new prices.', 'success');
    } else {
      showToast('No oil price scraper configured. Go to Scrape Config to set one up.', 'warning');
    }
  } catch (error) {
    showToast('Failed to start scrape: ' + error.message, 'error');
  }
}

// ==================== Prices Page ====================

let selectedPrices = new Set();
let currentPricesData = [];
let showLatestScrapeOnly = false;
let groupPricesByCompany = false;
let viewType = 'local';
let scrapeHistoryFilters = { configId: '', days: 30 };

async function renderPricesPage(container) {
  selectedPrices.clear();
  currentPricesData = [];

  // Build unified header
  const headerHtml = generateUnifiedHeader({
    title: 'Oil Prices',
    subtitle: 'Track and manage local and market prices',
    primaryActions: [
      {
        label: 'Import',
        icon: headerIcons.import,
        onclick: 'showImportPricesModal()',
        class: 'btn-primary'
      }
    ],
    secondaryActions: [
      {
        label: 'Cleanup Old Data',
        icon: headerIcons.trash,
        onclick: 'openCleanupModal()'
      }
    ],
    controls: [
      {
        label: 'View',
        items: [
          {
            type: 'select',
            id: 'view-type-select',
            onchange: 'toggleViewType()',
            options: [
              { value: 'local', label: 'Local Only', selected: viewType === 'local' },
              { value: 'all', label: 'Local & Market', selected: viewType === 'all' },
              { value: 'market', label: 'Market Only', selected: viewType === 'market' }
            ]
          }
        ]
      },
      {
        label: 'Display',
        items: [
          {
            type: 'toggle',
            id: 'toggle-latest-scrape',
            label: 'Latest Only',
            checked: showLatestScrapeOnly,
            onchange: 'toggleLatestScrape()'
          },
          {
            type: 'toggle',
            id: 'toggle-group-company',
            label: 'Group Companies',
            checked: groupPricesByCompany,
            onchange: 'toggleGroupCompany()'
          },
          {
            type: 'toggle',
            id: 'toggle-history',
            label: 'History',
            checked: false,
            onchange: 'togglePriceHistory()'
          }
        ]
      }
    ]
  });

  container.innerHTML = `
    ${headerHtml}
    <div class="page-body">
      <div class="filter-bar">
        <div class="filter-group">
            <label class="filter-label">Company</label>
            <input type="text" class="form-input" id="filter-company" placeholder="Search company...">
        </div>
         <div class="filter-group">
          <label class="filter-label">Date From</label>
          <input type="date" class="form-input" id="filter-date-from">
        </div>
        <div class="filter-group">
          <label class="filter-label">Date To</label>
          <input type="date" class="form-input" id="filter-date-to">
        </div>
        <div class="filter-group">
          <label class="filter-label">Min Price</label>
          <input type="number" class="form-input" id="filter-price-min" step="0.01" placeholder="0.00">
        </div>
        <div class="filter-group">
          <label class="filter-label">Max Price</label>
          <input type="number" class="form-input" id="filter-price-max" step="0.01" placeholder="10.00">
        </div>
        <div class="filter-group" style="justify-content: flex-end;">
          <button class="btn btn-primary" onclick="applyPriceFilters()">Apply Filters</button>
        </div>
      </div>

      <div class="card">
        <div class="card-body">
          <div class="table-container">
            <table class="data-table" id="prices-table">
              <thead>
                <tr>
                  <th style="width: 40px;"><input type="checkbox" onchange="toggleAllVisiblePrices(this)"></th>
                  <th class="sortable" onclick="handleSort('prices-table', 1, 'date')">Date</th>
                  <th class="sortable" onclick="handleSort('prices-table', 2, 'text')">Company</th>
                  <th class="sortable" onclick="handleSort('prices-table', 3, 'number')">Price/Gallon</th>
                  <th class="sortable" onclick="handleSort('prices-table', 4, 'text')">Town</th>
                  <th style="width: 100px;">Actions</th>
                </tr>
              </thead>
              <tbody id="prices-tbody">
                <tr><td colspan="6" class="text-center">Loading...</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `;

  // Set up selection bar actions
  const selectionActions = document.getElementById('selection-actions');
  if (selectionActions) {
    selectionActions.innerHTML = `
      <button class="btn btn-danger btn-sm" onclick="deleteSelectedPrices()">
        ${headerIcons.trash}
        <span>Delete Selected</span>
      </button>
    `;
  }

  await loadPrices();
}


async function loadPrices(filters = {}) {
  try {
    const showHistory = document.getElementById('toggle-history')?.checked;
    // Ensure type is in filters if not passed explicitly (though loadPrices is usually called with getCurrentFilters)
    if (!filters.type) filters.type = viewType;

    let rawData = showHistory ? await api.getOilPrices(filters) : await api.getLatestPrices(filters);

    if (showLatestScrapeOnly && rawData.length > 0) {
      let maxScrapeTime = "";
      rawData.forEach(p => {
        if (p.scraped_at && p.scraped_at > maxScrapeTime) maxScrapeTime = p.scraped_at;
      });

      if (maxScrapeTime) {
        const maxDate = new Date(maxScrapeTime);
        // 15 minute tolerance window for a single scrape batch
        const windowMs = 15 * 60 * 1000;
        rawData = rawData.filter(p => {
          if (!p.scraped_at) return false;
          return (maxDate - new Date(p.scraped_at)) < windowMs;
        });
      }
    }

    currentPricesData = rawData;
    selectedPrices.clear();
    updateSelectionUI();

    const tbody = document.getElementById('prices-tbody');

    if (currentPricesData.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6">
            <div class="empty-state">
              <p class="empty-state-text">No prices found. Try adjusting your filters or run a scrape.</p>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    if (groupPricesByCompany) {
      // Primary sort by company name to ensure groups are ordered
      // Secondary sort by date (desc) within group
      currentPricesData.sort((a, b) => {
        const c = a.company_name.localeCompare(b.company_name);
        if (c !== 0) return c;
        return parseLocalDate(b.date_reported) - parseLocalDate(a.date_reported);
      });

      const groups = {};
      currentPricesData.forEach(p => {
        if (!groups[p.company_name]) groups[p.company_name] = [];
        groups[p.company_name].push(p);
      });

      tbody.innerHTML = Object.entries(groups).map(([company, prices]) => {
        const header = `
              <tr class="group-header" style="background: var(--bg-secondary); cursor: pointer;" onclick="toggleGroupVisibility(this)">
                  <td colspan="6" style="padding: var(--space-sm) var(--space-md); font-weight: 600;">
                      <div class="flex items-center gap-sm">
                          <span class="group-toggle-icon" style="transition: transform 0.2s;">▼</span>
                          ${company} <span class="badge badge-sm" style="margin-left: auto;">${prices.length}</span>
                      </div>
                  </td>
              </tr>
           `;
        const rows = prices.map(price => renderPriceRow(price)).join('');
        return header + rows;
      }).join('');

    } else {
      tbody.innerHTML = currentPricesData.map(price => renderPriceRow(price)).join('');
    }
  } catch (error) {
    showToast('Failed to load prices: ' + error.message, 'error');
  }
}

function renderPriceRow(price) {
  return `
    <tr data-price-id="${price.id}" class="price-row">
        <td><input type="checkbox" class="price-select" value="${price.id}" onchange="togglePriceSelection(${price.id})"></td>
        <td class="mono">
            <div>${formatDate(price.date_reported)}</div>
            ${price.scraped_at ? `<div style="font-size: 0.7em; color: var(--text-secondary);" title="Snapshot time">Snap: ${formatDateTime(price.scraped_at)}</div>` : ''}
        </td>
        <td>${price.company_name}</td>
        <td class="mono">$${parseFloat(price.price_per_gallon).toFixed(3)}</td>
        <td>${price.town || '-'}</td>
        <td>
            <div class="flex gap-sm">
                <button class="btn btn-ghost btn-sm" onclick="editPrice(${price.id})" title="Edit">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                </button>
                <button class="btn btn-ghost btn-sm text-error" onclick="deletePrice(${price.id})" title="Delete">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
            </div>
        </td>
      </tr>
    `;
}

function toggleGroupVisibility(headerRow) {
  const icon = headerRow.querySelector('.group-toggle-icon');
  let transform = icon.style.transform;
  let isCollapsed = transform === 'rotate(-90deg)';

  icon.style.transform = isCollapsed ? '' : 'rotate(-90deg)';

  let next = headerRow.nextElementSibling;
  while (next && !next.classList.contains('group-header')) {
    next.style.display = isCollapsed ? '' : 'none';
    next = next.nextElementSibling;
  }
}

function applyPriceFilters() {
  loadPrices(getCurrentFilters());
}

function togglePriceHistory() {
  applyPriceFilters();
}

function toggleLatestScrape() {
  showLatestScrapeOnly = document.getElementById('toggle-latest-scrape').checked;
  loadPrices(getCurrentFilters());
}

function toggleGroupCompany() {
  groupPricesByCompany = document.getElementById('toggle-group-company').checked;
  // Re-render table structure if needed, but loadPrices handles body
  loadPrices(getCurrentFilters());
}

function toggleViewType() {
  viewType = document.getElementById('view-type-select').value;
  loadPrices(getCurrentFilters());
}

function getCurrentFilters() {
  return {
    company_name: document.getElementById('filter-company')?.value || '',
    date_from: document.getElementById('filter-date-from')?.value || '',
    date_to: document.getElementById('filter-date-to')?.value || '',
    price_min: document.getElementById('filter-price-min')?.value || '',
    price_max: document.getElementById('filter-price-max')?.value || '',
    type: viewType,
  };
}

function togglePriceSelection(id) {
  if (selectedPrices.has(id)) {
    selectedPrices.delete(id);
  } else {
    selectedPrices.add(id);
  }
  updateSelectionUI();
}

function toggleAllVisiblePrices(checkbox) {
  const checkboxes = document.querySelectorAll('.price-select');
  checkboxes.forEach(cb => {
    cb.checked = checkbox.checked;
    const id = parseInt(cb.value);
    if (checkbox.checked) {
      selectedPrices.add(id);
    } else {
      selectedPrices.delete(id);
    }
  });
  updateSelectionUI();
}

function updateSelectionUI() {
  // Update the new unified selection bar
  updateSelectionBar(selectedPrices.size, 'prices');

  // Also update the count display if exists
  const countSpan = document.getElementById('selection-count');
  if (countSpan && selectedPrices.size > 0) {
    countSpan.textContent = `${selectedPrices.size} price${selectedPrices.size !== 1 ? 's' : ''} selected`;
  }
}

// --- Modal Helpers ---

function confirmAction(title, message, confirmText, onConfirm) {
  const modalTitle = document.getElementById('modal-title');
  const modalBody = document.getElementById('modal-body');
  const confirmBtn = document.getElementById('modal-confirm');

  if (!modalTitle || !modalBody || !confirmBtn) return;

  modalTitle.textContent = title;
  modalBody.innerHTML = `<p>${message}</p>`;
  confirmBtn.textContent = confirmText || 'Confirm';

  // Style button based on intent
  confirmBtn.className = (confirmText && confirmText.toLowerCase().includes('delete'))
    ? 'btn btn-danger'
    : 'btn btn-primary';

  confirmBtn.onclick = async () => {
    confirmBtn.disabled = true;
    const originalText = confirmBtn.textContent;
    confirmBtn.textContent = 'Processing...';

    try {
      await onConfirm();
      closeModal();
    } catch (error) {
      showToast('Action failed: ' + error.message, 'error');
    } finally {
      confirmBtn.disabled = false;
      confirmBtn.textContent = originalText;
    }
  };

  openModal();
}

async function deleteSelectedPrices() {
  if (selectedPrices.size === 0) return;

  confirmAction(
    'Delete Selected Prices',
    `Are you sure you want to delete <strong class="text-error">${selectedPrices.size}</strong> records?<br><br><span class="text-secondary text-sm">This action cannot be undone.</span>`,
    'Delete Selected',
    async () => {
      await api.deleteOilPricesBulk(Array.from(selectedPrices));
      showToast('Selected prices deleted', 'success');
      loadPrices();
    }
  );
}

async function deletePrice(id) {
  confirmAction(
    'Delete Price',
    'Are you sure you want to delete this price record?',
    'Delete',
    async () => {
      await api.deleteOilPrice(id);
      showToast('Price deleted', 'success');
      loadPrices();
    }
  );
}

function openCleanupModal() {
  document.getElementById('modal-title').textContent = 'Cleanup Old Data';
  document.getElementById('modal-body').innerHTML = `
    <p class="mb-md">Delete all oil price records older than a specific date.</p>
        <div class="form-group">
            <label class="form-label">Delete records before:</label>
            <input type="date" class="form-input" id="cleanup-date">
        </div>
        <p class="text-secondary text-sm">This action cannot be undone.</p>
  `;

  // Set default date to 1 year ago
  const d = new Date();
  d.setFullYear(d.getFullYear() - 1);
  setTimeout(() => {
    document.getElementById('cleanup-date').valueAsDate = d;
  }, 100);

  document.getElementById('modal-confirm').onclick = async () => {
    const date = document.getElementById('cleanup-date').value;
    if (!date) return;

    try {
      const result = await api.deleteOilPricesBulk(null, date);
      showToast(result.message, 'success');
      closeModal();
      loadPrices();
    } catch (error) {
      showToast('Cleanup failed: ' + error.message, 'error');
    }
  };
  openModal();
}

function editPrice(id) {
  const price = currentPricesData.find(p => p.id === id);
  if (!price) return;

  document.getElementById('modal-title').textContent = 'Edit Price';
  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
            <label class="form-label">Company</label>
            <input type="text" class="form-input" value="${price.company_name}" disabled>
        </div>
        <div class="form-group">
            <label class="form-label">Price per Gallon</label>
            <input type="number" step="0.001" class="form-input" id="edit-price-val" value="${price.price_per_gallon}">
        </div>
        <div class="form-group">
            <label class="form-label">Town</label>
            <input type="text" class="form-input" id="edit-town-val" value="${price.town || ''}">
        </div>
  `;

  document.getElementById('modal-confirm').onclick = async () => {
    const newPrice = document.getElementById('edit-price-val').value;
    const newTown = document.getElementById('edit-town-val').value;

    try {
      await api.updateOilPrice(id, { price_per_gallon: newPrice, town: newTown });
      showToast('Price updated', 'success');
      closeModal();
      loadPrices();
    } catch (error) {
      showToast('Update failed: ' + error.message, 'error');
    }
  };
  openModal();
}

// ==================== Companies Page ====================

// ==================== Companies Page ====================

let selectedCompanies = [];
let showMergedCompanies = false;
let snapshotFilter = '30';

async function renderCompaniesPage(container) {
  let companiesData = [];

  if (showMergedCompanies) {
    companiesData = await api.getCompanies({ merged: true });
  } else {
    companiesData = await api.getLatestPrices();
  }

  // Filter based on snapshot date if applicable (only for active companies with prices)
  if (!showMergedCompanies && snapshotFilter !== 'all') {
    const days = parseInt(snapshotFilter);
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);

    companiesData = companiesData.filter(c => {
      if (!c.date_reported) return false;
      const parts = c.date_reported.split('-');
      if (parts.length < 3) return false;
      const reported = new Date(parts[0], parts[1] - 1, parts[2]);
      return reported >= cutoff;
    });
  }

  selectedCompanies = [];

  // Calculate lowest price for active view to show diffs
  let minPrice = Infinity;
  if (!showMergedCompanies && companiesData.length > 0) {
    companiesData.forEach(c => {
      const p = parseFloat(c.price_per_gallon);
      if (!isNaN(p) && p > 0 && p < minPrice) {
        minPrice = p;
      }
    });
  }
  if (minPrice === Infinity) minPrice = null;

  // Build unified header
  const headerHtml = generateUnifiedHeader({
    title: 'Companies',
    subtitle: `${companiesData.length} companies found`,
    primaryActions: [],
    secondaryActions: [
      {
        label: 'Merge Selected',
        icon: headerIcons.merge,
        onclick: 'mergeSelectedCompanies()',
        id: 'merge-btn',
        style: 'display: none;'
      }
    ],
    controls: [
      {
        label: 'Filter',
        items: [
          {
            type: 'toggle',
            id: 'toggle-merged',
            label: 'Show Merged Only',
            checked: showMergedCompanies,
            onchange: 'toggleMergedCompanies()'
          }
        ]
      }
    ]
  });

  container.innerHTML = `
    ${headerHtml}

    <div class="page-body">
      <div class="filter-bar">
        <div class="filter-group">
          <label class="filter-label">Search Company</label>
          <input type="text" class="form-input" id="search-companies" placeholder="Filter by name..." onkeyup="filterCompaniesTable()">
        </div>

        ${!showMergedCompanies ? `
        <div class="filter-group">
            <label class="filter-label">Snapshot Date</label>
            <select class="form-input" id="snapshot-filter" onchange="changeSnapshotFilter(this.value)">
                <option value="7" ${snapshotFilter === '7' ? 'selected' : ''}>Last 7 Days</option>
                <option value="30" ${snapshotFilter === '30' ? 'selected' : ''}>Last 30 Days</option>
                <option value="90" ${snapshotFilter === '90' ? 'selected' : ''}>Last 90 Days</option>
                <option value="365" ${snapshotFilter === '365' ? 'selected' : ''}>Last Year</option>
                <option value="all" ${snapshotFilter === 'all' ? 'selected' : ''}>All Time</option>
            </select>
        </div>
        ` : ''}

        <div class="filter-group" style="flex: 1;">
          <small class="text-secondary" id="select-hint">${showMergedCompanies ? 'Viewing merged companies' : 'Select 2 companies to merge duplicates'}</small>
        </div>
      </div>

      <div class="card">
        <div class="card-body" style="padding: var(--space-sm);">
          <div class="table-responsive-wrapper">
            <table class="data-table" id="companies-table">
              <thead>
                <tr>
                  <th style="width: 40px;"></th>
                  <th class="sortable" onclick="handleSort('companies-table', 1, 'text')">Company Name</th>
                  ${showMergedCompanies ? '<th>Merged Into</th>' : `
                  <th class="sortable" onclick="handleSort('companies-table', 2, 'number')">Latest Price</th>
                  <th class="sortable" onclick="handleSort('companies-table', 3, 'date')">Last Updated</th>
                  `}
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody id="companies-tbody">
                ${companiesData.length === 0 ? `
                  <tr><td colspan="${showMergedCompanies ? 4 : 5}" class="text-center">No company data found.</td></tr>
                ` : companiesData.map(c => {
    // Normalize data structure since getCompanies and getLatestPrices return slightly different shapes
    const id = c.id || c.company_id;
    const name = c.name || c.company_name;
    const price = c.price_per_gallon ? parseFloat(c.price_per_gallon) : null;
    const date = c.date_reported;
    const website = c.website || c.company_website;
    const phone = c.phone || c.company_phone;
    const town = c.town;

    let priceDisplay = '-';
    if (!showMergedCompanies && price !== null) {
      if (minPrice !== null && Math.abs(price - minPrice) < 0.001) {
        priceDisplay = `
                 <div>${formatCurrency(price)}</div>
                 <div style="font-size: 11px; color: var(--success); font-weight: 500; margin-top: 2px;">Lowest Price</div>
             `;
      } else if (minPrice !== null) {
        const diff = price - minPrice;
        priceDisplay = `
                 <div>${formatCurrency(price)}</div>
                 <div style="font-size: 11px; color: var(--error); margin-top: 2px;">+${formatCurrency(diff)}</div>
             `;
      } else {
        priceDisplay = formatCurrency(price);
      }
    } else if (!showMergedCompanies) {
      priceDisplay = '-';
    }

    return `
                  <tr data-company-id="${id}" data-company-name="${name}">
                    <td>${!showMergedCompanies ? `<input type="checkbox" class="company-select" onchange="toggleCompanySelection(${id}, '${name.replace(/'/g, "\\'")}')">` : ''}</td>
                    <td>
                        <div class="flex items-center gap-sm">
                            <strong>${name}</strong>
                            ${website ? `
                                <a href="${website.startsWith('http') ? website : 'http://' + website}" target="_blank" class="text-primary hover:text-primary-dark" title="Visit Website">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                                </a>
                            ` : ''}
                        </div>
                        
                        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 4px; display: flex; gap: 8px; flex-wrap: wrap;">
                             ${town ? `<span class="flex items-center gap-xs" title="Town"><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> ${town}</span>` : ''}
                             ${phone ? `<span class="flex items-center gap-xs" title="Phone"><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg> ${phone}</span>` : ''}
                        </div>

                        ${c.aliases && c.aliases.length > 0 ? `
                        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">
                            <span style="opacity: 0.7;">AKA:</span> ${c.aliases.map(a => a.alias_name).join(', ')}
                        </div>
                        ` : ''}
                    </td>
                    ${showMergedCompanies ? `<td><span class="badge badge-warning">Merged</span></td>` : `
                    <td class="mono">${priceDisplay}</td>
                    <td class="mono">
                        <div>${formatDate(date)}</div>
                        ${c.scraped_at ? `<div style="font-size: 0.7em; color: var(--text-secondary);" title="Snapshot time">Snap: ${formatDateTime(c.scraped_at)}</div>` : ''}
                    </td>
                    `}
                    <td>
                        <div class="flex gap-sm">
                            <button class="btn btn-ghost btn-sm" onclick="viewCompanyPrices('${name}')" title="View History">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                            </button>
                            ${showMergedCompanies ? '' : `
                            <button class="btn btn-ghost btn-sm text-error" onclick="deleteCompany(${id}, '${name}')" title="Delete Company">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                            </button>
                            `}
                        </div>
                    </td>
                  </tr>
                `}).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `;
}

async function changeSnapshotFilter(value) {
  snapshotFilter = value;
  await renderCompaniesPage(document.getElementById('page-content'));
}

async function toggleMergedCompanies() {
  showMergedCompanies = document.getElementById('toggle-merged').checked;
  await renderCompaniesPage(document.getElementById('page-content'));
}

async function deleteCompany(id, name) {
  if (!confirm(`Are you sure you want to delete "${name}" ? This will delete all associated prices.Orders will be unlinked(preserved).`)) {
    return;
  }

  try {
    await api.deleteCompany(id);
    showToast(`Deleted company "${name}"`, 'success');
    renderCompaniesPage(document.getElementById('page-content'));
  } catch (error) {
    showToast('Failed to delete company: ' + error.message, 'error');
  }
}

function toggleCompanySelection(companyId, companyName) {
  const idx = selectedCompanies.findIndex(c => c.id === companyId);
  if (idx >= 0) {
    selectedCompanies.splice(idx, 1);
  } else {
    selectedCompanies.push({ id: companyId, name: companyName });
  }

  // Update merge button visibility
  const mergeBtn = document.getElementById('merge-btn');
  if (selectedCompanies.length === 2) {
    mergeBtn.style.display = 'inline-flex';
    document.getElementById('select-hint').textContent = `Ready to merge: ${selectedCompanies[0].name} → ${selectedCompanies[1].name} `;
  } else {
    mergeBtn.style.display = 'none';
    document.getElementById('select-hint').textContent = selectedCompanies.length === 1
      ? `Selected: ${selectedCompanies[0].name}. Select one more to merge.`
      : 'Select 2 companies to merge duplicates';
  }
}

async function mergeSelectedCompanies() {
  if (selectedCompanies.length !== 2) {
    showToast('Please select exactly 2 companies to merge.', 'error');
    return;
  }

  const [source, target] = selectedCompanies;

  // Show confirmation modal
  document.getElementById('modal-title').textContent = 'Merge Companies';
  document.getElementById('modal-body').innerHTML = `
    < p > This will merge < strong > ${source.name}</strong > into < strong > ${target.name}</strong >.</p >
    <ul style="margin: var(--space-md) 0; padding-left: var(--space-lg); color: var(--text-secondary);">
      <li>All oil prices from "${source.name}" will be reassigned to "${target.name}"</li>
      <li>All oil orders from "${source.name}" will be reassigned to "${target.name}"</li>
      <li>"${source.name}" will be saved as an alias for future scrapes</li>
    </ul>
    <p class="text-secondary">Note: The first selected company is merged INTO the second.</p>
  `;

  document.getElementById('modal-confirm').onclick = async () => {
    try {
      await api.mergeCompanies(source.id, target.id);
      showToast(`Merged "${source.name}" into "${target.name}"`, 'success');
      closeModal();
      renderCompaniesPage(document.getElementById('page-content'));
    } catch (error) {
      showToast('Failed to merge: ' + error.message, 'error');
    }
  };
  openModal();
}

function filterCompaniesTable() {
  const query = document.getElementById('search-companies').value.toLowerCase();
  const rows = document.querySelectorAll('#companies-tbody tr');
  rows.forEach(row => {
    const name = row.cells[1]?.textContent.toLowerCase() || '';
    row.style.display = name.includes(query) ? '' : 'none';
  });
}

async function viewCompanyPrices(companyName) {
  navigateTo('prices');
  // Set filter and apply
  setTimeout(() => {
    document.getElementById('filter-company').value = companyName;
    document.getElementById('toggle-history').checked = true;
    applyPriceFilters();
  }, 100);
}

// ==================== Orders Page ====================

async function renderOrdersPage(container) {
  const orders = await api.getOrders();

  // Calculate KPIs
  const now = new Date();
  const currentYear = now.getFullYear();

  const yearOrders = orders.filter(o => {
    const d = parseLocalDate(o.start_date);
    return d.getFullYear() === currentYear;
  });

  const costThisYear = yearOrders.reduce((sum, o) => sum + (parseFloat(o.total_cost) || 0), 0);
  const deliveriesThisYear = yearOrders.length;

  const lastOrder = orders.length > 0 ?
    [...orders].sort((a, b) => parseLocalDate(b.start_date) - parseLocalDate(a.start_date))[0] :
    null;

  let daysSinceLast = '-';
  if (lastOrder) {
    const lastDate = parseLocalDate(lastOrder.start_date);
    const diffTime = Math.abs(now - lastDate);
    daysSinceLast = Math.floor(diffTime / (1000 * 60 * 60 * 24));
  }

  // Build unified header
  const headerHtml = generateUnifiedHeader({
    title: 'Oil Orders',
    subtitle: `Tracking ${orders.length} deliveries`,
    primaryActions: [
      {
        label: 'Add Order',
        icon: headerIcons.add,
        onclick: 'showOrderModal()',
        class: 'btn-primary',
        id: 'btn-add-order'
      }
    ],
    secondaryActions: [
      {
        label: 'Import CSV',
        icon: headerIcons.import,
        onclick: 'showImportModal()'
      }
    ]
  });

  container.innerHTML = `
    ${headerHtml}

    <div class="page-body">
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Cost This Year (${currentYear})</div>
          <div class="kpi-value">${formatCurrency(costThisYear)}</div>
          <div class="kpi-meta">${deliveriesThisYear} delivery events</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Deliveries This Year</div>
          <div class="kpi-value">${deliveriesThisYear}</div>
          <div class="kpi-meta">Across current year</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Last Delivery</div>
          <div class="kpi-value">${lastOrder ? formatDate(lastOrder.start_date) : '-'}</div>
          <div class="kpi-meta">${lastOrder ? `${parseFloat(lastOrder.gallons).toFixed(1)} gal @ $${parseFloat(lastOrder.price_per_gallon).toFixed(3)}` : 'No history'}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Days Since Delivery</div>
          <div class="kpi-value">${daysSinceLast}</div>
          <div class="kpi-meta">Since last tracked order</div>
        </div>
      </div>

      ${orders.length > 0 ? `
        <div class="card mb-lg">
          <div class="card-header">
            <h3 class="card-title">Order Volume & Spend Relationship</h3>
          </div>
          <div class="card-body">
            <div class="chart-container" style="height: 250px;">
              <canvas id="order-volume-chart"></canvas>
            </div>
          </div>
        </div>
      ` : ''}

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Order History</h3>
        </div>
        <div class="card-body">
          <div class="table-container">
            <table class="data-table" id="orders-table">
              <thead>
                <tr>
                  <th class="sortable" onclick="handleSort('orders-table', 0, 'date')">Start Date</th>
                  <th class="sortable" onclick="handleSort('orders-table', 1, 'date')">End Date</th>
                  <th class="sortable" onclick="handleSort('orders-table', 2, 'text')">Location</th>
                  <th class="sortable" onclick="handleSort('orders-table', 3, 'text')">Vendor</th>
                  <th class="sortable" onclick="handleSort('orders-table', 4, 'number')">Gallons</th>
                  <th class="sortable" onclick="handleSort('orders-table', 5, 'number')">Price/Gal</th>
                  <th class="sortable" onclick="handleSort('orders-table', 6, 'number')">Total</th>
                  <th class="sortable" onclick="handleSort('orders-table', 7, 'number')">$/Day</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                ${orders.length === 0 ? `
                  <tr>
                    <td colspan="9">
                      <div class="empty-state">
                        <p class="empty-state-text">No orders yet. Add your first oil delivery!</p>
                      </div>
                    </td>
                  </tr>
                ` : orders.sort((a, b) => parseLocalDate(b.start_date) - parseLocalDate(a.start_date)).map(order => `
                  <tr>
                    <td class="mono">${formatDate(order.start_date)}</td>
                    <td class="mono">${order.end_date ? formatDate(order.end_date) : '-'}</td>
                    <td>${order.location_name || '-'}</td>
                    <td>${order.company_name || '-'}</td>
                    <td class="mono">${parseFloat(order.gallons).toFixed(1)}</td>
                    <td class="mono">$${parseFloat(order.price_per_gallon).toFixed(3)}</td>
                    <td class="mono">${formatCurrency(order.total_cost)}</td>
                    <td class="mono">${order.cost_per_day ? formatCurrency(order.cost_per_day) : '-'}</td>
                    <td>
                      <div class="flex gap-sm">
                        <button class="btn btn-ghost btn-sm" onclick="showOrderModal(${order.id})">Edit</button>
                        <button class="btn btn-ghost btn-sm" onclick="deleteOrder(${order.id})">Delete</button>
                      </div>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `;

  if (orders.length > 0) {
    const chartCtx = document.getElementById('order-volume-chart');
    if (chartCtx) {
      storeChart('order-volume', createOrderVolumeInsightChart(chartCtx, orders));
    }
  }
}

async function showImportModal() {
  document.getElementById('modal-title').textContent = 'Import Oil Orders';
  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">Location *</label>
      <select class="form-select" id="import-location" required>
        ${locations.map(loc => `
          <option value="${loc.id}">${loc.name}</option>
        `).join('')}
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">CSV File *</label>
      <input type="file" class="form-input" id="import-file" accept=".csv" required>
      <p class="text-secondary text-sm" style="margin-top: var(--space-xs);">
        Required columns: <strong>StartDate, CompanyName, Price, Gallons</strong><br>
        Optional: <strong>EndDate</strong>
      </p>
    </div>
    <div id="import-status" style="margin-top: var(--space-md);"></div>
  `;

  const confirmBtn = document.getElementById('modal-confirm');
  confirmBtn.textContent = 'Start Import';
  confirmBtn.onclick = async () => {
    const locationId = document.getElementById('import-location').value;
    const fileInput = document.getElementById('import-file');
    const statusEl = document.getElementById('import-status');

    if (!fileInput.files.length) {
      showToast('Please select a file', 'warning');
      return;
    }

    const file = fileInput.files[0];
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Importing...';
    statusEl.innerHTML = '<div class="loading-spinner-sm"></div> Importing data...';

    try {
      const result = await api.importOrders(locationId, file);

      let statusHtml = `
        <div class="alert alert-success">
          <strong>Success!</strong> ${result.message}
        </div>
      `;

      if (result.errors && result.errors.length > 0) {
        statusHtml += `
          <div class="mt-md">
            <h4 class="text-sm font-bold text-error">Errors/Warnings:</h4>
            <ul class="text-xs text-error" style="max-height: 150px; overflow-y: auto; padding-left: var(--space-md); margin-top: var(--space-xs);">
              ${result.errors.map(err => `<li>${err}</li>`).join('')}
            </ul>
          </div>
        `;
      }

      statusEl.innerHTML = statusHtml;
      confirmBtn.textContent = 'Done';
      confirmBtn.onclick = () => {
        closeModal();
        renderPage('orders');
      };

      showToast(result.message, 'success');
      // Refresh reference data in case new companies were created
      loadReferenceData();

    } catch (error) {
      statusEl.innerHTML = `
        <div class="alert alert-danger">
          <strong>Error:</strong> ${error.message}
        </div>
      `;
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Try Again';
      showToast('Import failed: ' + error.message, 'error');
    }
  };

  openModal();
}

async function showImportPricesModal() {
  document.getElementById('modal-title').textContent = 'Import Oil Price History';
  document.getElementById('modal-body').innerHTML = `
    <div class="form-group">
      <label class="form-label">CSV File *</label>
      <input type="file" class="form-input" id="import-file" accept=".csv" required>
      <p class="text-secondary text-sm" style="margin-top: var(--space-xs);">
        Required columns: <strong>CompanyName, Price, PriceDate</strong> (or <strong>Date</strong>)<br>
        Optional: <strong>Town</strong> (defaults to 'Default')
      </p>
    </div>
    <div id="import-status" style="margin-top: var(--space-md);"></div>
  `;

  const confirmBtn = document.getElementById('modal-confirm');
  confirmBtn.textContent = 'Start Import';
  confirmBtn.onclick = async () => {
    const fileInput = document.getElementById('import-file');
    const statusEl = document.getElementById('import-status');

    if (!fileInput.files.length) {
      showToast('Please select a file', 'warning');
      return;
    }

    const file = fileInput.files[0];
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Importing...';
    statusEl.innerHTML = '<div class="loading-spinner-sm"></div> Importing data...';

    try {
      const result = await api.importPrices(file);

      let statusHtml = `
        <div class="alert alert-success">
          <strong>Success!</strong> ${result.message}
        </div>
      `;

      if (result.errors && result.errors.length > 0) {
        statusHtml += `
          <div class="mt-md">
            <h4 class="text-sm font-bold text-error">Errors/Warnings:</h4>
            <ul class="text-xs text-error" style="max-height: 150px; overflow-y: auto; padding-left: var(--space-md); margin-top: var(--space-xs);">
              ${result.errors.map(err => `<li>${err}</li>`).join('')}
            </ul>
          </div>
        `;
      }

      statusEl.innerHTML = statusHtml;
      confirmBtn.textContent = 'Done';
      confirmBtn.onclick = () => {
        closeModal();
        renderPage('prices');
      };

      showToast(result.message, 'success');
      loadReferenceData();

    } catch (error) {
      statusEl.innerHTML = `
        <div class="alert alert-danger">
          <strong>Error:</strong> ${error.message}
        </div>
      `;
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Try Again';
      showToast('Import failed: ' + error.message, 'error');
    }
  };

  openModal();
}

async function showOrderModal(orderId = null) {
  const isEdit = orderId !== null;
  let order = null;

  if (isEdit) {
    try {
      order = await api.getOrders().then(orders => orders.find(o => o.id === orderId));
    } catch (error) {
      showToast('Failed to load order', 'error');
      return;
    }
  }

  // Get suggested start date if creating new
  let suggestedStart = '';
  if (!isEdit && locations.length > 0) {
    try {
      const validation = await api.validateOrderDates(locations[0].id, getLocalDateString());
      suggestedStart = validation.suggested_start_date || '';
    } catch (e) { }
  }

  document.getElementById('modal-title').textContent = isEdit ? 'Edit Order' : 'Add Order';
  document.getElementById('modal-body').innerHTML = `
    <form id="order-form">
      <div class="form-group">
        <label class="form-label">Location *</label>
        <select class="form-select" id="order-location" required>
          ${locations.map(loc => `
            <option value="${loc.id}" ${order?.location_id === loc.id ? 'selected' : ''}>${loc.name}</option>
          `).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Vendor</label>
        <select class="form-select" id="order-company">
          <option value="">-- Select Vendor --</option>
          ${companies.map(c => `
            <option value="${c.id}" ${order?.company_id === c.id ? 'selected' : ''}>${c.name}</option>
          `).join('')}
        </select>
      </div>
      <div class="flex gap-md">
        <div class="form-group" style="flex: 1;">
          <label class="form-label">Start Date *</label>
          <input type="date" class="form-input" id="order-start-date" 
                 value="${order?.start_date || suggestedStart}" required>
        </div>
        <div class="form-group" style="flex: 1;">
          <label class="form-label">End Date</label>
          <input type="date" class="form-input" id="order-end-date" 
                 value="${order?.end_date || ''}">
        </div>
      </div>
      <div class="flex gap-md">
        <div class="form-group" style="flex: 1;">
          <label class="form-label">Gallons *</label>
          <input type="number" class="form-input" id="order-gallons" 
                 value="${order?.gallons || ''}" step="0.1" min="0" required>
        </div>
        <div class="form-group" style="flex: 1;">
          <label class="form-label">Price per Gallon *</label>
          <input type="number" class="form-input" id="order-price" 
                 value="${order?.price_per_gallon || ''}" step="0.001" min="0" required>
        </div>
      </div>
      <div id="date-validation-msg" class="text-secondary" style="font-size: var(--text-sm);"></div>
    </form>
    `;

  // Validate dates on change
  const validateDates = async () => {
    const locationId = document.getElementById('order-location').value;
    const startDate = document.getElementById('order-start-date').value;
    const endDate = document.getElementById('order-end-date').value;
    const msgEl = document.getElementById('date-validation-msg');

    if (locationId && startDate) {
      try {
        const result = await api.validateOrderDates(locationId, startDate, endDate, orderId);
        if (!result.valid) {
          msgEl.innerHTML = '<span style="color: var(--accent-error);">⚠ Dates overlap with an existing order</span>';
        } else {
          msgEl.innerHTML = '<span style="color: var(--accent-success);">✓ Dates are valid</span>';
        }
      } catch (e) {
        msgEl.innerHTML = '';
      }
    }
  };

  document.getElementById('order-location').addEventListener('change', validateDates);
  document.getElementById('order-start-date').addEventListener('change', validateDates);
  document.getElementById('order-end-date').addEventListener('change', validateDates);

  document.getElementById('modal-confirm').onclick = () => saveOrder(orderId);
  openModal();
}

async function saveOrder(orderId) {
  const data = {
    location_id: parseInt(document.getElementById('order-location').value),
    company_id: document.getElementById('order-company').value ? parseInt(document.getElementById('order-company').value) : null,
    start_date: document.getElementById('order-start-date').value,
    end_date: document.getElementById('order-end-date').value || null,
    gallons: parseFloat(document.getElementById('order-gallons').value),
    price_per_gallon: parseFloat(document.getElementById('order-price').value),
  };

  try {
    if (orderId) {
      await api.updateOrder(orderId, data);
      showToast('Order updated successfully', 'success');
    } else {
      await api.createOrder(data);
      showToast('Order created successfully', 'success');
    }
    closeModal();
    renderOrdersPage(document.getElementById('page-content'));
  } catch (error) {
    showToast('Failed to save order: ' + error.message, 'error');
  }
}

async function deleteOrder(orderId) {
  confirmAction(
    'Delete Order',
    'Are you sure you want to delete this order?',
    'Delete',
    async () => {
      await api.deleteOrder(orderId);
      showToast('Order deleted', 'success');
      renderOrdersPage(document.getElementById('page-content'));
    }
  );
}
// ==================== Locations Page ====================

async function renderLocationsPage(container) {
  locations = await api.getLocations();

  // Build unified header
  const headerHtml = generateUnifiedHeader({
    title: 'Locations',
    subtitle: `${locations.length} configured location${locations.length !== 1 ? 's' : ''}`,
    primaryActions: [
      {
        label: 'Add Location',
        icon: headerIcons.add,
        onclick: 'showLocationModal()',
        class: 'btn-primary'
      }
    ],
    secondaryActions: []
  });

  container.innerHTML = `
    ${headerHtml}
    <div class="page-body">

      ${locations.length === 0 ? `
        <div class="empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
            <circle cx="12" cy="10" r="3"></circle>
          </svg>
          <h3 class="empty-state-title">No Locations Yet</h3>
          <p class="empty-state-text">Add your first delivery location to start tracking oil orders.</p>
          <button class="btn btn-primary" onclick="showLocationModal()">Add Location</button>
        </div>
      ` : `
        <div class="kpi-grid">
          ${locations.map(loc => `
            <div class="card">
              <div class="card-body">
                <div class="flex justify-between items-center mb-md">
                  <h3>${loc.name}</h3>
                  <div class="flex gap-sm">
                    <button class="btn btn-ghost btn-sm" onclick="showLocationModal(${loc.id})">Edit</button>
                    <button class="btn btn-ghost btn-sm" onclick="deleteLocation(${loc.id})">Delete</button>
                  </div>
                </div>
                <p class="text-secondary">${loc.address || ''}</p>
                <p class="text-secondary">${[loc.city, loc.state, loc.zip_code].filter(Boolean).join(', ')}</p>
                <p class="text-sm text-secondary mt-sm">Tank: ${loc.tank_capacity || 275} gal</p>
              </div>
            </div>
          `).join('')}
        </div>
      `}
    </div>
  `;
}


async function fetchZipCoords(zip) {
  if (!zip || zip.length < 5) return;

  try {
    const response = await fetch(`https://api.zippopotam.us/us/${zip}`);
    if (!response.ok) return;

    const data = await response.json();
    const place = data.places?.[0];

    if (place) {
      const cityInput = document.getElementById('location-city');
      const stateInput = document.getElementById('location-state');
      const latInput = document.getElementById('location-lat');
      const lonInput = document.getElementById('location-lon');

      if (cityInput && !cityInput.value) cityInput.value = place['place name'];
      if (stateInput && !stateInput.value) stateInput.value = place['state abbreviation'];

      if (latInput) latInput.value = place.latitude;
      if (lonInput) lonInput.value = place.longitude;

      showToast('Location details found', 'success');
    }
  } catch (e) {
    console.error('Zip lookup failed', e);
  }
}

async function showLocationModal(locationId = null) {
  const isEdit = locationId !== null;
  const location = isEdit ? locations.find(l => l.id === locationId) : null;

  document.getElementById('modal-title').textContent = isEdit ? 'Edit Location' : 'Add Location';
  document.getElementById('modal-body').innerHTML = `
    <form id="location-form">
      <div class="form-group">
        <label class="form-label">Name *</label>
        <input type="text" class="form-input" id="location-name" value="${location?.name || ''}" required placeholder="e.g., Home, Vacation House">
      </div>
      <div class="form-group">
        <label class="form-label">Address</label>
        <input type="text" class="form-input" id="location-address" value="${location?.address || ''}" placeholder="123 Main St">
      </div>
      <div class="flex gap-md">
        <div class="form-group" style="flex: 2;">
          <label class="form-label">City</label>
          <input type="text" class="form-input" id="location-city" value="${location?.city || ''}">
        </div>
        <div class="form-group" style="flex: 1;">
          <label class="form-label">State</label>
          <input type="text" class="form-input" id="location-state" value="${location?.state || ''}" placeholder="MA">
        </div>
        <div class="form-group" style="flex: 1;">
          <label class="form-label">ZIP</label>
          <input type="text" class="form-input" id="location-zip" value="${location?.zip_code || ''}" onchange="fetchZipCoords(this.value)">
        </div>
      </div>
      <div class="flex gap-md">
        <div class="form-group flex-1">
          <label class="form-label">Latitude</label>
          <input type="number" step="0.0001" class="form-input" id="location-lat" value="${location?.latitude || ''}" placeholder="42.3601">
        </div>
        <div class="form-group flex-1">
          <label class="form-label">Longitude</label>
          <input type="number" step="0.0001" class="form-input" id="location-lon" value="${location?.longitude || ''}" placeholder="-71.0589">
        </div>
      </div>
      <p class="text-xs text-secondary mb-md">Coordinates used for weather data. Find at <a href="https://www.latlong.net/" target="_blank">latlong.net</a></p>
      <div class="form-group">
        <label class="form-label">Tank Capacity (gallons)</label>
        <input type="number" class="form-input" id="location-tank-capacity" value="${location?.tank_capacity || 275}" min="50" max="1000" step="1">
        <p class="text-xs text-secondary mt-xs">Standard residential tank is 275 gallons</p>
      </div>
    </form>
    `;

  const confirmBtn = document.getElementById('modal-confirm');
  confirmBtn.textContent = 'Save';
  confirmBtn.disabled = false;
  confirmBtn.onclick = () => saveLocation(locationId);
  openModal();
}

async function saveLocation(locationId) {
  const latValue = document.getElementById('location-lat').value;
  const lonValue = document.getElementById('location-lon').value;

  const data = {
    name: document.getElementById('location-name').value,
    address: document.getElementById('location-address').value || null,
    city: document.getElementById('location-city').value || null,
    state: document.getElementById('location-state').value || null,
    zip_code: document.getElementById('location-zip').value || null,
    tank_capacity: parseFloat(document.getElementById('location-tank-capacity').value) || 275,
    latitude: latValue ? parseFloat(latValue) : null,
    longitude: lonValue ? parseFloat(lonValue) : null,
  };

  try {
    if (locationId) {
      await api.updateLocation(locationId, data);
      showToast('Location updated successfully', 'success');
    } else {
      await api.createLocation(data);
      showToast('Location created successfully', 'success');
    }
    closeModal();
    await loadReferenceData();
    renderLocationsPage(document.getElementById('page-content'));
  } catch (error) {
    showToast('Failed to save location: ' + error.message, 'error');
  }
}

async function deleteLocation(locationId) {
  if (!confirm('Are you sure you want to delete this location?')) return;

  try {
    await api.deleteLocation(locationId);
    showToast('Location deleted', 'success');
    await loadReferenceData();
    renderLocationsPage(document.getElementById('page-content'));
  } catch (error) {
    showToast('Failed to delete location: ' + error.message, 'error');
  }
}

// ==================== Usage Page (Placeholder) ====================

// ==================== Oil Usage Page ====================

let usageLocationId = null;
let usageStartDate = null;
let usageEndDate = null;
let usageAggregation = 'daily'; // daily, weekly, monthly

function getDefaultDateRange() {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0]
  };
}

function getUsageDays() {
  if (!usageStartDate || !usageEndDate) {
    const defaults = getDefaultDateRange();
    usageStartDate = defaults.start;
    usageEndDate = defaults.end;
  }
  const start = parseLocalDate(usageStartDate);
  const end = parseLocalDate(usageEndDate);
  return Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1;
}

async function renderUsagePage(container) {
  // If no locations, show placeholder
  if (!locations || locations.length === 0) {
    const headerHtml = generateUnifiedHeader({
      title: 'Oil Usage',
      subtitle: 'Track consumption analytics',
      primaryActions: [],
      secondaryActions: []
    });

    container.innerHTML = `
      ${headerHtml}
  <div class="page-body">
    <div class="empty-state">
      <h3 class="empty-state-title">No Locations</h3>
      <p class="empty-state-text">Please add a location first to track tank usage.</p>
      <a href="#locations" class="btn btn-primary">Add Location</a>
    </div>
  </div>
  `;
    return;
  }

  // Default to first location
  if (!usageLocationId) {
    usageLocationId = locations[0].id;
  }

  // Initialize dates if not set
  if (!usageStartDate || !usageEndDate) {
    const defaults = getDefaultDateRange();
    usageStartDate = defaults.start;
    usageEndDate = defaults.end;
  }

  const selectedLocation = locations.find(l => l.id === usageLocationId) || locations[0];

  // Build unified header
  const headerHtml = generateUnifiedHeader({
    title: 'Oil Usage',
    subtitle: selectedLocation ? `${selectedLocation.name} (${selectedLocation.tank_capacity || 275}g tank)` : 'Consumption Analysis',
    primaryActions: [],
    secondaryActions: [],
    controls: [
      {
        label: 'Location',
        items: [
          {
            type: 'select',
            id: 'usage-location-select',
            onchange: 'changeUsageLocation(this.value)',
            options: locations.map(l => ({
              value: l.id,
              label: l.name,
              selected: l.id === usageLocationId
            }))
          }
        ]
      }
    ]
  });

  container.innerHTML = `
    ${headerHtml}
    <div class="page-body">

      
      <!-- Stats Row -->
      <div class="usage-stats-row mb-lg">
        <div class="usage-stat-card" id="tank-level-card">
          <div class="usage-stat-icon" style="background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2v6l3-3M12 22v-6l-3 3"></path>
              <circle cx="12" cy="12" r="10"></circle>
            </svg>
          </div>
          <div class="usage-stat-content">
            <div class="usage-stat-label">Current Level</div>
            <div class="usage-stat-value" id="tank-level-value">--</div>
            <div class="usage-stat-sub" id="tank-level-sub">Loading...</div>
          </div>
          <div class="usage-stat-bar" id="tank-level-bar"></div>
        </div>
        
        <div class="usage-stat-card" id="usage-summary-card">
          <div class="usage-stat-icon" style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
            </svg>
          </div>
          <div class="usage-stat-content">
            <div class="usage-stat-label">Period Usage</div>
            <div class="usage-stat-value" id="usage-total-value">--</div>
            <div class="usage-stat-sub" id="usage-avg-sub">Loading...</div>
          </div>
        </div>
        
        <div class="usage-stat-card" id="cost-estimate-card">
          <div class="usage-stat-icon" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%);">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="1" x2="12" y2="23"></line>
              <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
            </svg>
          </div>
          <div class="usage-stat-content">
            <div class="usage-stat-label">Est. Cost</div>
            <div class="usage-stat-value" id="cost-total-value">--</div>
            <div class="usage-stat-sub" id="cost-price-sub">Loading...</div>
          </div>
        </div>
        
        <div class="usage-stat-card usage-upload-card">
          <div class="usage-stat-icon" style="background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
          </div>
          <div class="usage-stat-content">
            <div class="usage-stat-label">Import Data</div>
            <input type="file" id="tank-csv-file" accept=".csv" style="display:none" onchange="handleTankCsvUpload(this)">
            <button class="btn btn-sm" style="background: rgba(139,92,246,0.15); color: #8b5cf6; border: none; margin-top: 4px;" onclick="document.getElementById('tank-csv-file').click()">
              Upload CSV
            </button>
            <div class="usage-stat-sub">Smart Oil Gauge format</div>
          </div>
        </div>
      </div>

      <!-- Controls Row -->
      <div class="card mb-lg">
        <div class="card-body" style="padding: 12px 16px;">
          <div class="flex flex-between align-center flex-wrap gap-md">
            <div class="flex gap-md align-center">
              <div class="flex gap-xs align-center">
                <label class="text-sm text-secondary">From:</label>
                <input type="date" id="usage-start-date" class="form-input" style="width: 150px;" value="${usageStartDate}" onchange="updateUsageDateRange()">
              </div>
              <div class="flex gap-xs align-center">
                <label class="text-sm text-secondary">To:</label>
                <input type="date" id="usage-end-date" class="form-input" style="width: 150px;" value="${usageEndDate}" onchange="updateUsageDateRange()">
              </div>
              <div class="flex gap-xs">
                <button class="btn btn-ghost btn-sm" onclick="setQuickDateRange(7)">7d</button>
                <button class="btn btn-ghost btn-sm" onclick="setQuickDateRange(30)">30d</button>
                <button class="btn btn-ghost btn-sm" onclick="setQuickDateRange(90)">90d</button>
                <button class="btn btn-ghost btn-sm" onclick="setQuickDateRange(365)">1y</button>
              </div>
            </div>
            <div class="flex gap-md align-center">
              <label class="text-sm text-secondary">Aggregate:</label>
              <div class="btn-group">
                <button class="btn btn-sm ${usageAggregation === 'daily' ? 'btn-primary' : 'btn-ghost'}" onclick="setUsageAggregation('daily')">Daily</button>
                <button class="btn btn-sm ${usageAggregation === 'weekly' ? 'btn-primary' : 'btn-ghost'}" onclick="setUsageAggregation('weekly')">Weekly</button>
                <button class="btn btn-sm ${usageAggregation === 'monthly' ? 'btn-primary' : 'btn-ghost'}" onclick="setUsageAggregation('monthly')">Monthly</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Usage Chart -->
      <div class="card mb-lg">
        <div class="card-header">
          <h3 class="card-title" id="usage-chart-title">Usage Trend</h3>
        </div>
        <div class="card-body">
          <div class="chart-container" style="height: 280px;">
            <canvas id="usage-chart"></canvas>
          </div>
        </div>
      </div>

      <!-- Temperature & HDD Section -->
      <div class="grid grid-2 gap-md mb-lg">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Heating Degree Days (HDD)</h3>
            <button class="btn btn-ghost btn-sm" onclick="showWeatherFetchModal()">Fetch Weather</button>
          </div>
          <div class="card-body">
            <div class="flex gap-lg mb-md">
              <div class="text-center">
                <div class="text-2xl font-bold" id="hdd-total">--</div>
                <div class="text-xs text-secondary">Total HDD</div>
              </div>
              <div class="text-center">
                <div class="text-2xl font-bold" id="hdd-avg">--</div>
                <div class="text-xs text-secondary">Daily Avg</div>
              </div>
              <div class="text-center">
                <div class="text-2xl font-bold" id="hdd-days">--</div>
                <div class="text-xs text-secondary">Days</div>
              </div>
            </div>
            <div class="chart-container" style="height: 180px;">
              <canvas id="hdd-chart"></canvas>
            </div>
          </div>
        </div>
        
      </div>

      <!-- Tank Level Chart -->
      <div class="card mb-lg">
        <div class="card-header">
          <h3 class="card-title">Tank Level History</h3>
          <label class="toggle-label" style="font-weight:normal; font-size: 13px;">
            <input type="checkbox" id="show-anomalies" onchange="loadTankChart()">
            <span>Show Anomalies</span>
          </label>
        </div>
        <div class="card-body">
          <div class="chart-container" style="height: 250px;">
            <canvas id="tank-level-chart"></canvas>
          </div>
        </div>
      </div>

      <!-- Detailed Usage Table -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Usage History Details</h3>
        </div>
        <div class="card-body">
          <div class="table-container" id="usage-detail-container">
            <p class="text-secondary text-center p-lg">Loading details...</p>
          </div>
        </div>
      </div>
    </div>
    
    <style>
      .usage-stats-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
      }
      @media (max-width: 1200px) {
        .usage-stats-row { grid-template-columns: repeat(2, 1fr); }
      }
      @media (max-width: 600px) {
        .usage-stats-row { grid-template-columns: 1fr; }
      }
      .usage-stat-card {
        background: var(--bg-primary);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 20px;
        display: flex;
        align-items: flex-start;
        gap: 16px;
        position: relative;
        overflow: hidden;
      }
      .usage-stat-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        flex-shrink: 0;
      }
      .usage-stat-content {
        flex: 1;
        min-width: 0;
      }
      .usage-stat-label {
        font-size: 13px;
        color: var(--text-secondary);
        margin-bottom: 4px;
      }
      .usage-stat-value {
        font-size: 28px;
        font-weight: 700;
        line-height: 1.1;
        margin-bottom: 4px;
      }
      .usage-stat-sub {
        font-size: 12px;
        color: var(--text-secondary);
      }
      .usage-stat-bar {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: var(--bg-secondary);
      }
      .usage-stat-bar::after {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        height: 100%;
        width: var(--bar-width, 0%);
        background: var(--bar-color, var(--primary-color));
        transition: width 0.5s ease;
      }
      .btn-group {
        display: flex;
        gap: 0;
      }
      .btn-group .btn {
        border-radius: 0;
      }
      .btn-group .btn:first-child {
        border-radius: 6px 0 0 6px;
      }
      .btn-group .btn:last-child {
        border-radius: 0 6px 6px 0;
      }
    </style>
  `;

  // Load data
  loadUsageData();
}

function setQuickDateRange(days) {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - days);

  usageStartDate = start.toISOString().split('T')[0];
  usageEndDate = end.toISOString().split('T')[0];

  document.getElementById('usage-start-date').value = usageStartDate;
  document.getElementById('usage-end-date').value = usageEndDate;

  loadUsageData();
}

function updateUsageDateRange() {
  usageStartDate = document.getElementById('usage-start-date').value;
  usageEndDate = document.getElementById('usage-end-date').value;
  loadUsageData();
}

function setUsageAggregation(agg) {
  usageAggregation = agg;
  // Re-render page to update button states
  renderUsagePage(document.getElementById('page-content'));
}

async function loadUsageData() {
  const days = getUsageDays();

  try {
    const [currentLevel, usageSummary] = await Promise.all([
      api.getTankCurrentLevel(usageLocationId),
      api.getTankUsageSummary(usageLocationId, days)
    ]);

    // Tank Level Card
    const levelValue = document.getElementById('tank-level-value');
    const levelSub = document.getElementById('tank-level-sub');
    const levelBar = document.getElementById('tank-level-bar');

    if (currentLevel.current_gallons !== null) {
      const percent = currentLevel.percent_full;
      const color = percent > 30 ? '#10b981' : percent > 15 ? '#f59e0b' : '#ef4444';

      levelValue.textContent = `${currentLevel.current_gallons} gal`;
      levelValue.style.color = color;
      levelSub.textContent = `${percent}% of ${currentLevel.tank_capacity} gal capacity`;
      levelBar.style.setProperty('--bar-width', `${percent}% `);
      levelBar.style.setProperty('--bar-color', color);
    } else {
      levelValue.textContent = 'No data';
      levelValue.style.color = 'var(--text-secondary)';
      levelSub.textContent = 'Upload CSV to get started';
    }

    // Usage Summary
    document.getElementById('usage-total-value').textContent = `${usageSummary.total_usage} gal`;
    document.getElementById('usage-avg-sub').textContent = `${usageSummary.avg_daily_usage} gal / day average`;

    // Cost Estimate
    document.getElementById('cost-total-value').textContent = `$${usageSummary.estimated_cost.toFixed(2)} `;
    document.getElementById('cost-price-sub').textContent = usageSummary.latest_price
      ? `@$${usageSummary.latest_price.toFixed(3)}/gal`
      : 'No price data';

    // Chart title
    const titles = { daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly' };
    document.getElementById('usage-chart-title').textContent = `${titles[usageAggregation]} Usage Trend`;

    // Aggregate data based on selection
    const aggregatedData = aggregateUsageData(usageSummary.daily_usage, usageAggregation);
    renderUsageChart(aggregatedData);

    // Tank Level Chart
    loadTankChart();

    // Load temperature/HDD data
    loadTemperatureData(days);

  } catch (err) {
    showToast('Failed to load usage data: ' + err.message, 'error');
  }
}

async function loadTemperatureData(days) {
  try {
    const [hddSummary, correlation] = await Promise.all([
      api.getHddSummary(usageLocationId, days),
      api.getUsageCorrelation(usageLocationId, days)
    ]);

    // HDD Summary
    document.getElementById('hdd-total').textContent = hddSummary.total_hdd;
    document.getElementById('hdd-avg').textContent = hddSummary.avg_daily_hdd;
    document.getElementById('hdd-days').textContent = hddSummary.days_analyzed;

    // HDD Chart
    renderHddChart(hddSummary.daily_data);

    // Correlation
    if (correlation.correlation !== null) {
      document.getElementById('correlation-value').textContent = correlation.correlation.toFixed(2);
      document.getElementById('correlation-text').textContent = correlation.correlation_interpretation +
        ' correlation between HDD and oil usage. Higher HDD means colder weather.';
    } else {
      document.getElementById('correlation-value').textContent = '--';
      document.getElementById('correlation-text').textContent = 'Need more data to calculate correlation. Fetch weather data and upload tank readings.';
    }

    // Correlation Chart
    renderCorrelationChart(correlation.daily_data);

  } catch (err) {
    console.error('Failed to load temperature data:', err);
    document.getElementById('hdd-total').textContent = '--';
    document.getElementById('correlation-text').textContent = 'Failed to load temperature data. Try fetching weather.';
  }
}

function renderHddChart(data) {
  const ctx = document.getElementById('hdd-chart');
  if (!ctx) return;

  if (window.hddChartInstance) {
    window.hddChartInstance.destroy();
  }

  if (!data || data.length === 0) return;

  const labels = data.map(d => d.date);
  const hddValues = data.map(d => d.hdd);
  const tempValues = data.map(d => d.avg_temp);

  window.hddChartInstance = new Chart(ctx.getContext('2d'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'HDD',
          data: hddValues,
          borderColor: 'rgba(239, 68, 68, 0.8)',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          fill: true,
          tension: 0.3,
          yAxisID: 'y'
        },
        {
          label: 'Avg Temp (°F)',
          data: tempValues,
          borderColor: 'rgba(59, 130, 246, 0.8)',
          borderDash: [5, 5],
          tension: 0.3,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'top', labels: { boxWidth: 12 } } },
      scales: {
        x: { type: 'time', time: { unit: 'day' }, grid: { display: false } },
        y: { type: 'linear', position: 'left', title: { display: true, text: 'HDD' } },
        y1: { type: 'linear', position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: '°F' } }
      }
    }
  });
}

function renderCorrelationChart(data) {
  const ctx = document.getElementById('correlation-chart');
  if (!ctx) return;

  if (window.correlationChartInstance) {
    window.correlationChartInstance.destroy();
  }

  if (!data || data.length === 0) return;

  // Filter to days with usage
  const filteredData = data.filter(d => d.usage > 0);

  window.correlationChartInstance = new Chart(ctx.getContext('2d'), {
    type: 'scatter',
    data: {
      datasets: [{
        label: 'HDD vs Usage',
        data: filteredData.map(d => ({ x: d.hdd, y: d.usage })),
        backgroundColor: 'rgba(59, 130, 246, 0.6)',
        borderColor: 'rgba(59, 130, 246, 1)',
        pointRadius: 5,
        pointHoverRadius: 7
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: 'Heating Degree Days (HDD)' } },
        y: { title: { display: true, text: 'Usage (gal)' }, beginAtZero: true }
      }
    }
  });
}

function showWeatherFetchModal() {
  const selectedLocation = locations.find(l => l.id === usageLocationId);
  const defaultLat = selectedLocation?.latitude || '';
  const defaultLon = selectedLocation?.longitude || '';
  const hasCoords = defaultLat && defaultLon;

  document.getElementById('modal-title').textContent = 'Fetch Weather Data';
  document.getElementById('modal-body').innerHTML = `
    <form id="weather-fetch-form">
      <p class="text-sm text-secondary mb-md">
        Fetch historical weather data from Open-Meteo (free, no API key needed).
        ${hasCoords ? 'Using coordinates from location settings.' : 'Enter coordinates for your location.'}
      </p>
      <div class="flex gap-md mb-md">
        <div class="form-group flex-1">
          <label class="form-label">Latitude</label>
          <input type="number" step="0.0001" class="form-input" id="weather-lat" value="${defaultLat}" placeholder="42.3601" required>
        </div>
        <div class="form-group flex-1">
          <label class="form-label">Longitude</label>
          <input type="number" step="0.0001" class="form-input" id="weather-lon" value="${defaultLon}" placeholder="-71.0589" required>
        </div>
      </div>
      <div class="flex gap-md mb-md">
        <div class="form-group flex-1">
          <label class="form-label">Start Date</label>
          <input type="date" class="form-input" id="weather-start" value="${usageStartDate}">
        </div>
        <div class="form-group flex-1">
          <label class="form-label">End Date</label>
          <input type="date" class="form-input" id="weather-end" value="${usageEndDate}">
        </div>
      </div>
      ${!hasCoords ? `<p class="text-xs text-secondary">
        <strong>Tip:</strong> Save coordinates in Location settings to auto-fill next time.
        Find coordinates at <a href="https://www.latlong.net/" target="_blank">latlong.net</a>
      </p>` : ''}
    </form>
  `;

  document.getElementById('modal-confirm').onclick = () => fetchWeatherData();
  openModal();
}

async function fetchWeatherData() {
  const lat = parseFloat(document.getElementById('weather-lat').value);
  const lon = parseFloat(document.getElementById('weather-lon').value);
  const startDate = document.getElementById('weather-start').value;
  const endDate = document.getElementById('weather-end').value;

  if (!lat || !lon) {
    showToast('Please enter valid coordinates', 'error');
    return;
  }

  try {
    closeModal();
    showToast('Fetching weather data...', 'info');

    const result = await api.fetchWeatherData(lat, lon, usageLocationId, startDate, endDate);
    showToast(`Weather data fetched: ${result.created} created, ${result.updated} updated`, 'success');

    // Reload temperature data
    loadTemperatureData(getUsageDays());
  } catch (err) {
    showToast('Failed to fetch weather: ' + err.message, 'error');
  }
}

function aggregateUsageData(dailyData, aggregation) {
  if (!dailyData || dailyData.length === 0) return [];
  if (aggregation === 'daily') return dailyData;

  const grouped = {};

  dailyData.forEach(d => {
    const date = parseLocalDate(d.date);
    let key;

    if (aggregation === 'weekly') {
      // Get start of week (Sunday)
      const startOfWeek = new Date(date);
      startOfWeek.setDate(date.getDate() - date.getDay());
      key = startOfWeek.toISOString().split('T')[0];
    } else if (aggregation === 'monthly') {
      key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`;
    }

    if (!grouped[key]) {
      grouped[key] = { date: key, usage: 0 };
    }
    grouped[key].usage += d.usage;
  });

  return Object.values(grouped).sort((a, b) => a.date.localeCompare(b.date));
}

function renderUsageChart(usageData) {
  const ctx = document.getElementById('usage-chart');
  if (!ctx) return;

  if (window.usageChartInstance) {
    window.usageChartInstance.destroy();
  }

  const labels = usageData.map(d => d.date);
  const data = usageData.map(d => parseFloat(d.usage.toFixed(2)));

  const timeUnit = usageAggregation === 'monthly' ? 'month' : usageAggregation === 'weekly' ? 'week' : 'day';

  window.usageChartInstance = new Chart(ctx.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Usage (gal)',
        data,
        backgroundColor: 'rgba(59, 130, 246, 0.7)',
        borderColor: 'rgba(59, 130, 246, 1)',
        borderWidth: 1,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: timeUnit },
          grid: { display: false }
        },
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Gallons' }
        }
      }
    }
  });
}

async function loadTankChart() {
  const includeAnomalies = document.getElementById('show-anomalies')?.checked || false;
  const days = getUsageDays();

  try {
    const readings = await api.getTankReadings(usageLocationId, days, includeAnomalies);

    const ctx = document.getElementById('tank-level-chart');
    if (!ctx) return;

    if (window.tankLevelChartInstance) {
      window.tankLevelChartInstance.destroy();
    }

    const labels = readings.map(r => r.timestamp);
    const data = readings.map(r => r.gallons);

    const pointColors = readings.map(r => {
      if (r.is_fill_event) return 'rgba(16, 185, 129, 1)';
      if (r.is_anomaly) return 'rgba(239, 68, 68, 0.7)';
      if (r.is_post_fill_unstable) return 'rgba(245, 158, 11, 0.7)';
      return 'rgba(59, 130, 246, 0.7)';
    });

    window.tankLevelChartInstance = new Chart(ctx.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Tank Level (gal)',
          data,
          borderColor: 'rgba(59, 130, 246, 0.6)',
          pointBackgroundColor: pointColors,
          pointRadius: includeAnomalies ? 2 : 0,
          pointHoverRadius: 4,
          fill: true,
          backgroundColor: 'rgba(59, 130, 246, 0.08)',
          tension: 0.2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false,
        },
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            type: 'time',
            time: { unit: 'day' },
            grid: { display: false }
          },
          y: {
            title: { display: true, text: 'Gallons' },
            min: 0
          }
        }
      }
    });

    renderUsageDetailTable(readings);
  } catch (err) {
    console.error('Failed to load tank chart:', err);
  }
}

function changeUsageLocation(locationId) {
  usageLocationId = parseInt(locationId);
  loadUsageData();
}

async function handleTankCsvUpload(input) {
  const file = input.files[0];
  if (!file) return;

  try {
    showToast('Uploading and processing...', 'info');
    const result = await api.uploadTankReadings(file, usageLocationId);
    showToast(`Uploaded ${result.new_readings} new readings (${result.skipped_duplicates} duplicates skipped)`, 'success');
    loadUsageData();
  } catch (err) {
    showToast('Upload failed: ' + err.message, 'error');
  }

  input.value = '';
}

function renderUsageDetailTable(readings) {
  const container = document.getElementById('usage-detail-container');
  if (!container) return;

  if (!readings || readings.length === 0) {
    container.innerHTML = '<p class="text-secondary text-center p-lg">No usage data found for this period.</p>';
    return;
  }

  // Sort descending for the table
  const sorted = [...readings].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  let html = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Date & Time</th>
                    <th>Level</th>
                    <th class="text-center">Trend</th>
                    <th class="text-center">Interval</th>
                    <th class="text-center">Burn Rate</th>
                    <th class="text-right">Status</th>
                </tr>
            </thead>
            <tbody>
    `;

  for (let i = 0; i < sorted.length; i++) {
    const r = sorted[i];
    const prev = i < sorted.length - 1 ? sorted[i + 1] : null;

    let used = 0;
    let intervalText = '-';
    let burnRateText = '-';
    let indicatorHtml = '<span class="text-muted">–</span>';

    if (prev) {
      const diffMs = new Date(r.timestamp) - new Date(prev.timestamp);
      const diffHours = diffMs / (1000 * 60 * 60);

      used = prev.gallons - r.gallons;

      if (Math.abs(used) > 0.1) {
        if (used > 0) {
          const colorClass = used > 5 ? 'sentiment-bad' : 'sentiment-good';
          indicatorHtml = `<span class="usage-pill ${colorClass}">-${used.toFixed(1)} gal</span>`;
        } else {
          indicatorHtml = `<span class="usage-pill sentiment-good">+${Math.abs(used).toFixed(1)} gal</span>`;
        }
      }

      if (diffHours > 0) {
        intervalText = diffHours < 1 ? `${(diffHours * 60).toFixed(0)}m` : `${diffHours.toFixed(1)}h`;
        if (used > 0) {
          const gph = used / diffHours;
          burnRateText = `<span class="mono">${gph.toFixed(2)}</span> <span class="text-xs text-muted">gal/h</span>`;
        }
      }
    }

    let statusHtml = '';
    if (r.is_fill_event) statusHtml = '<span class="badge bg-sentiment-good">FILL</span>';
    else if (r.is_anomaly) statusHtml = '<span class="badge bg-sentiment-bad">ANOMALY</span>';
    else if (r.is_post_fill_unstable) statusHtml = '<span class="badge bg-sentiment-warning">UNSTABLE</span>';
    else statusHtml = '<span class="badge" style="background:var(--bg-tertiary); color:var(--text-secondary);">NORMAL</span>';

    html += `
            <tr>
                <td class="text-sm">
                    <div class="font-bold">${new Date(r.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</div>
                    <div class="text-xs text-secondary">${new Date(r.timestamp).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}</div>
                </td>
                <td class="mono font-bold text-lg">${r.gallons.toFixed(1)}<span class="text-xs text-secondary font-normal ml-xs">gal</span></td>
                <td class="text-center">${indicatorHtml}</td>
                <td class="text-center text-secondary text-sm">${intervalText}</td>
                <td class="text-center">${burnRateText}</td>
                <td class="text-right">${statusHtml}</td>
            </tr>
        `;
  }

  html += `
            </tbody>
        </table>
    `;

  container.innerHTML = html;
}

// ==================== Scrape Config Page ====================

async function renderScrapePage(container) {
  const [configs, types, importInfo] = await Promise.all([
    api.getScrapeConfigs(),
    api.getScraperTypes(),
    api.getAvailableImportSymbols()
  ]);

  // Store for reuse
  window.scraperTypes = types.types;
  window.scraperConfigs = configs;
  window.isEiaConfigured = importInfo.eia_key_configured;
  const isEiaConfigured = window.isEiaConfigured;

  // Build unified header
  const headerHtml = generateUnifiedHeader({
    title: 'Scrape Configuration',
    subtitle: 'Configure automated data collection jobs',
    primaryActions: [
      {
        label: 'New Scraper',
        icon: headerIcons.add,
        onclick: 'showScrapeConfigModal()',
        class: 'btn-primary'
      }
    ],
    secondaryActions: []
  });

  container.innerHTML = `
    ${headerHtml}
    <div class="page-body">
      
      <!-- Configs Grid -->
      <div class="mb-xl">
        <div class="flex flex-between align-center mb-md">
             <h3 class="section-title" style="margin:0;">Active Scrapers</h3>
        </div>

        
        <div class="grid grid-3 gap-md">
            ${configs.map(config => renderScraperCard(config)).join('')}
             <!-- Add New Card Placeholder (Optional, but button is clear enough) -->
        </div>
        
        ${configs.length === 0 ? `
            <div class="card dashed p-xl text-center">
                <p class="text-secondary">No scrapers configured yet.</p>
                <button class="btn btn-primary mt-md" onclick="showScrapeConfigModal()">Create First Scraper</button>
            </div>
        ` : ''}
      </div>

      <!-- Historical Import Section -->
      <div class="card mb-lg">
        <div class="card-header">
          <h3 class="card-title">Historical Data Import</h3>
        </div>
        <div class="card-body">
          <p class="text-secondary mb-md">Import historical price data for market indices. Useful for trend analysis.</p>
          
          <div class="grid grid-2 gap-lg">
            <!-- Yahoo Finance -->
            <div class="border rounded-lg p-md">
              <h4 class="font-bold mb-sm">Yahoo Finance (Free)</h4>
              <p class="text-xs text-secondary mb-md">Import futures prices. No API key required.</p>
              <div class="flex gap-sm mb-sm">
                <select id="yahoo-symbol" class="form-select flex-1">
                  <option value="ulsd">ULSD Futures (HO=F)</option>
                  <option value="brent">Brent Crude (BZ=F)</option>
                  <option value="wti">WTI Crude (CL=F)</option>
                  <option value="gasoline">RBOB Gasoline (RB=F)</option>
                </select>
                <select id="yahoo-days" class="form-select" style="width: 120px;" onchange="toggleYahooCustomRange()">
                  <option value="30">30 days</option>
                  <option value="90">90 days</option>
                  <option value="180">6 months</option>
                  <option value="365" selected>1 year</option>
                  <option value="730">2 years</option>
                  <option value="1825">5 years</option>
                  <option value="custom">Custom</option>
                </select>
              </div>
              <div id="yahoo-custom-range" class="flex gap-sm mb-sm" style="display: none;">
                <input type="date" id="yahoo-start" class="form-input flex-1" style="font-size: 11px;">
                <input type="date" id="yahoo-end" class="form-input flex-1" style="font-size: 11px;">
              </div>
              <button class="btn btn-primary btn-sm" onclick="importYahooData()">Import from Yahoo</button>
            </div>
            
            <!-- EIA -->
            <div class="border rounded-lg p-md">
              <div class="flex flex-between align-center mb-sm">
                <h4 class="font-bold">EIA Spot Prices</h4>
                ${isEiaConfigured ? '<span class="badge badge-success">Key Configured</span>' : ''}
              </div>
              <p class="text-xs text-secondary mb-md">
                ${isEiaConfigured
      ? 'EIA API Key is loaded from server environment. You can override it below if needed.'
      : 'Requires free API key from <a href="https://www.eia.gov/opendata/register.php" target="_blank">eia.gov</a>'}
              </p>
              <div class="form-group mb-sm">
                <input type="password" id="eia-api-key" class="form-input" placeholder="${isEiaConfigured ? '••••••••••••••••' : 'Your EIA API Key'}">
              </div>
              <div class="flex gap-sm mb-sm">
                <select id="eia-series" class="form-select flex-1">
                  <option value="ulsd">NY Harbor ULSD Spot</option>
                  <option value="wti">WTI Crude Spot</option>
                  <option value="brent">Brent Crude Spot</option>
                  <option value="gasoline">NY Harbor Gasoline Spot</option>
                </select>
              </div>
              <div class="flex gap-sm mb-sm">
                <input type="date" id="eia-start" class="form-input flex-1" placeholder="Start Date">
                <input type="date" id="eia-end" class="form-input flex-1" placeholder="End Date">
              </div>
              <div class="flex gap-sm">
                <button class="btn btn-primary btn-sm flex-1" onclick="importEiaData()">Import Series</button>
                <button class="btn btn-ghost btn-sm" onclick="importEiaCrackSpreadBulk()" title="Import all components for 3:2:1 Crack Spread">Import Spread Data</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- History Section -->
      <div class="card">
         <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
             <div class="flex items-center gap-md">
                <h3 class="card-title">Execution Log</h3>
                <span class="badge" id="history-count-badge" style="display:none">0</span>
             </div>
             <div class="flex gap-sm">
                 <select id="history-filter-config" class="form-select" style="width: 200px;" onchange="updateHistoryFilter('configId', this.value)">
                     <option value="">All Scrapers</option>
                     ${configs.map(c => `<option value="${c.id}" ${scrapeHistoryFilters.configId == c.id ? 'selected' : ''}>${c.name}</option>`).join('')}
                 </select>
                 <select id="history-filter-days" class="form-select" style="width: 150px;" onchange="updateHistoryFilter('days', this.value)">
                     <option value="7" ${scrapeHistoryFilters.days == 7 ? 'selected' : ''}>Last 7 Days</option>
                     <option value="30" ${scrapeHistoryFilters.days == 30 ? 'selected' : ''}>Last 30 Days</option>
                     <option value="90" ${scrapeHistoryFilters.days == 90 ? 'selected' : ''}>Last 3 Months</option>
                     <option value="0" ${scrapeHistoryFilters.days == 0 ? 'selected' : ''}>All Time</option>
                 </select>
             </div>
         </div>
         <div class="card-body p-0" id="history-table-container">
             <div class="flex-center p-xl"><div class="loading-spinner"></div></div>
         </div>
      </div>
    </div>
  `;

  // Initial load of history
  loadScrapeHistoryTable();
}

function renderScraperCard(config) {
  const statusColor = config.enabled ? 'var(--success-text)' : 'var(--text-secondary)';
  const statusBg = config.enabled ? 'var(--success-bg)' : 'var(--bg-secondary)';

  return `
    <div class="card clickable-card" style="position: relative; transition: all 0.2s; border-left: 4px solid ${config.enabled ? 'var(--success-color)' : 'var(--text-secondary)'}">
        <div class="card-body">
            <div class="flex flex-between align-start mb-sm">
                <h3 class="text-md font-medium" style="margin:0">${config.name}</h3>
                <span class="badge" style="background:${statusBg}; color:${statusColor}; font-size: 11px;">
                    ${config.enabled ? 'ACTIVE' : 'DISABLED'}
                </span>
            </div>
            
            <div class="text-sm text-secondary mb-md">
                <div class="flex items-center gap-xs mb-xs" title="Scraper Type">
                     <span style="opacity:0.7">Type:</span> <span>${config.scraper_type}</span>
                </div>
                <div class="flex items-center gap-xs mb-xs" title="Schedule">
                     <span style="opacity:0.7">Run:</span> <span class="mono">${formatSchedule(config.schedule_type, config.schedule_value)}</span>
                </div>
                 <div class="flex items-center gap-xs" title="Last Run">
                     <span style="opacity:0.7">Last:</span> <span class="mono">${config.last_run ? formatDateTime(config.last_run) : 'Never'}</span>
                </div>
            </div>

            <div class="flex gap-sm mt-md pt-sm" style="border-top: 1px solid var(--border-color)">
                 <button class="btn btn-ghost btn-sm flex-1" onclick="runScrape(${config.id})">
                    Run Now
                 </button>
                 <button class="btn btn-ghost btn-sm" onclick="showScrapeConfigModal(${config.id})" title="Edit">
                    Edit
                 </button>
                 <button class="btn btn-ghost btn-sm text-error" onclick="deleteScrapeConfig(${config.id})" title="Delete">
                    Del
                 </button>
            </div>
        </div>
    </div>
    `;
}

async function loadScrapeHistoryTable() {
  const container = document.getElementById('history-table-container');
  if (!container) return;

  container.innerHTML = '<div class="flex-center p-xl"><div class="loading-spinner"></div></div>';

  try {
    const { configId, days } = scrapeHistoryFilters;
    // Assuming api.getScrapeHistory supports days parameter now
    const history = await api.getScrapeHistory(configId || null, days, 50);

    // Update badge
    const badge = document.getElementById('history-count-badge');
    if (badge) {
      badge.textContent = history.length;
      badge.style.display = 'inline-block';
    }

    if (history.length === 0) {
      container.innerHTML = `
                <div class="empty-state p-xl">
                    <p class="empty-state-text">No history found for selected filters.</p>
                </div>`;
      return;
    }

    container.innerHTML = `
            <div class="table-container" style="max-height: 500px; overflow-y: auto;">
              <table class="data-table">
                <thead style="position: sticky; top: 0; background: var(--bg-primary); z-index: 1;">
                  <tr>
                    <th>Date</th>
                    <th>Scraper</th>
                    <th>Status</th>
                    <th>Records</th>
                    <th>Duration</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  ${history.map(h => {
      const configName = window.scraperConfigs?.find(c => c.id === h.config_id)?.name || 'Unknown';
      const duration = h.completed_at ? ((new Date(h.completed_at) - new Date(h.started_at)) / 1000).toFixed(1) + 's' : '-';
      return `
                    <tr>
                      <td class="mono" style="font-size: 13px;">${formatDateTime(h.started_at)}</td>
                      <td style="font-weight: 500;">${configName}</td>
                      <td>
                        <span class="badge badge-${h.status === 'success' ? 'success' : h.status === 'failed' ? 'error' : 'info'}">
                          ${h.status}
                        </span>
                      </td>
                      <td class="mono">${h.records_scraped}</td>
                      <td class="mono text-secondary">${duration}</td>
                      <td class="text-secondary text-sm" style="max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${h.error_message || ''}">
                        ${h.error_message || ''}
                      </td>
                    </tr>
                  `}).join('')}
                </tbody>
              </table>
            </div>
        `;
  } catch (err) {
    container.innerHTML = `<div class="text-error p-md">Failed to load history: ${err.message}</div>`;
  }
}

function updateHistoryFilter(key, value) {
  if (key === 'days') value = parseInt(value) || 0;
  scrapeHistoryFilters[key] = value;
  loadScrapeHistoryTable();
}

async function importYahooData() {
  const symbol = document.getElementById('yahoo-symbol').value;
  const daysValue = document.getElementById('yahoo-days').value;

  let days = null;
  let startDate = null;
  let endDate = null;

  if (daysValue === 'custom') {
    startDate = document.getElementById('yahoo-start').value;
    endDate = document.getElementById('yahoo-end').value;
    if (!startDate || !endDate) {
      showToast('Please select both start and end dates', 'warning');
      return;
    }
  } else {
    days = parseInt(daysValue);
  }

  try {
    showToast('Importing from Yahoo Finance...', 'info');
    const result = await api.importYahooHistorical(symbol, days, startDate, endDate);
    showToast(`Imported: ${result.created} records (${result.skipped} duplicates skipped)`, 'success');
  } catch (err) {
    showToast('Import failed: ' + err.message, 'error');
  }
}

function toggleYahooCustomRange() {
  const val = document.getElementById('yahoo-days').value;
  const customDiv = document.getElementById('yahoo-custom-range');
  if (customDiv) {
    customDiv.style.display = val === 'custom' ? 'flex' : 'none';
  }
}

async function importEiaData() {
  const series = document.getElementById('eia-series').value;
  const apiKey = document.getElementById('eia-api-key').value;
  const startDate = document.getElementById('eia-start').value || null;
  const endDate = document.getElementById('eia-end').value || null;

  if (!apiKey && !window.isEiaConfigured) {
    showToast('Please enter your EIA API key', 'error');
    return;
  }

  try {
    showToast('Importing from EIA...', 'info');
    const result = await api.importEiaHistorical(series, apiKey, startDate, endDate);
    showToast(`Imported: ${result.created} records (${result.skipped} duplicates skipped)`, 'success');
  } catch (err) {
    showToast('Import failed: ' + err.message, 'error');
  }
}

async function importEiaCrackSpreadBulk() {
  const apiKey = document.getElementById('eia-api-key').value;
  if (!apiKey && !window.isEiaConfigured) {
    showToast('Please enter your EIA API key', 'error');
    return;
  }

  try {
    showToast('Importing crack spread components (WTI, ULSD, Gasoline)...', 'info');
    const result = await api.importEiaCrackSpreadBulk(apiKey, 365);
    let totalCreated = 0;
    result.results.forEach(r => totalCreated += (r.created || 0));
    showToast(`Bulk import completed. Total new records: ${totalCreated}`, 'success');
  } catch (err) {
    showToast('Bulk import failed: ' + err.message, 'error');
  }
}

async function showScrapeConfigModal(configId = null) {
  const isEdit = configId !== null;
  let config = null;

  if (isEdit) {
    const configs = await api.getScrapeConfigs();
    config = configs.find(c => c.id === configId);
  }

  document.getElementById('modal-title').textContent = isEdit ? 'Edit Scraper' : 'Add Scraper';
  document.getElementById('modal-body').innerHTML = `
    <form id="scrape-form">
      <div class="form-group">
        <label class="form-label">Name *</label>
        <input type="text" class="form-input" id="scrape-name" value="${config?.name || ''}" required placeholder="e.g., Zone 11 Oil Prices">
      </div>
      <div class="form-group">
        <label class="form-label">Scraper Type *</label>
        <select class="form-select" id="scrape-type" required ${isEdit ? 'disabled' : ''}>
          ${(window.scraperTypes || []).filter(t => !t.disabled).map(t => `
            <option value="${t.id}" ${config?.scraper_type === t.id ? 'selected' : ''}>${t.name}</option>
          `).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">URL *</label>
        <input type="url" class="form-input" id="scrape-url" value="${config?.url || 'https://www.newenglandoil.com/massachusetts/zone11.asp?x=0'}" required>
      </div>
      <div class="form-group">
        <label class="form-label">Schedule Type</label>
        <select class="form-select" id="scrape-schedule-type">
          <option value="daily" ${config?.schedule_type === 'daily' ? 'selected' : ''}>Daily</option>
          <option value="hourly" ${config?.schedule_type === 'hourly' ? 'selected' : ''}>Hourly</option>
          <option value="interval" ${config?.schedule_type === 'interval' ? 'selected' : ''}>Every X Hours</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Schedule Value</label>
        <input type="text" class="form-input" id="scrape-schedule-value" value="${config?.schedule_value || '09:00'}" placeholder="e.g., 09:00 for daily, 4 for interval">
        <small class="text-muted">For daily: time (09:00), for hourly: minute (30), for interval: hours (4)</small>
      </div>
      <div class="form-group">
        <label class="flex items-center gap-sm">
          <input type="checkbox" id="scrape-enabled" ${config?.enabled !== false ? 'checked' : ''}>
          <span>Enabled</span>
        </label>
      </div>
    </form >
    `;

  document.getElementById('modal-confirm').onclick = () => saveScrapeConfig(configId);
  openModal();
}

async function saveScrapeConfig(configId) {
  const data = {
    name: document.getElementById('scrape-name').value,
    scraper_type: document.getElementById('scrape-type').value,
    url: document.getElementById('scrape-url').value,
    schedule_type: document.getElementById('scrape-schedule-type').value,
    schedule_value: document.getElementById('scrape-schedule-value').value,
    enabled: document.getElementById('scrape-enabled').checked,
  };

  try {
    if (configId) {
      await api.updateScrapeConfig(configId, data);
      showToast('Scraper updated successfully', 'success');
    } else {
      await api.createScrapeConfig(data);
      showToast('Scraper created successfully', 'success');
    }
    closeModal();
    renderScrapePage(document.getElementById('page-content'));
  } catch (error) {
    showToast('Failed to save scraper: ' + error.message, 'error');
  }
}

async function runScrape(configId) {
  try {
    await api.runScrapeNow(configId);
    showToast('Scrape started!', 'success');
    setTimeout(() => renderScrapePage(document.getElementById('page-content')), 2000);
  } catch (error) {
    showToast('Failed to start scrape: ' + error.message, 'error');
  }
}

async function deleteScrapeConfig(configId) {
  if (!confirm('Are you sure you want to delete this scraper?')) return;

  try {
    await api.deleteScrapeConfig(configId);
    showToast('Scraper deleted', 'success');
    renderScrapePage(document.getElementById('page-content'));
  } catch (error) {
    showToast('Failed to delete scraper: ' + error.message, 'error');
  }
}

// ==================== Modal Utilities ====================

function openModal() {
  document.getElementById('modal-overlay').classList.add('active');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('active');
}

// Close modal on overlay click
document.getElementById('modal-overlay')?.addEventListener('click', (e) => {
  if (e.target === e.currentTarget) {
    closeModal();
  }
});

// ==================== Toast Notifications ====================

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast - ${type} `;
  toast.textContent = message;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideIn 0.3s ease reverse';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ==================== Sorting Logic ====================

const sortState = {};

function handleSort(tableId, colIndex, type) {
  const table = document.getElementById(tableId);
  if (!table) return;

  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const headers = table.querySelectorAll('th.sortable');

  // Toggle direction
  const key = `${tableId} -${colIndex} `;
  const currentDir = sortState[key] || 'none';
  const newDir = currentDir === 'asc' ? 'desc' : 'asc';
  sortState[key] = newDir;

  // Reset other headers classes
  headers.forEach(h => h.classList.remove('asc', 'desc'));
  const activeHeader = headers[colIndex];
  if (activeHeader) activeHeader.classList.add(newDir);

  // Sort rows
  rows.sort((a, b) => {
    let valA = a.cells[colIndex].textContent.trim();
    let valB = b.cells[colIndex].textContent.trim();

    if (type === 'number') {
      valA = parseFloat(valA.replace(/[^0-9.-]+/g, ""));
      valB = parseFloat(valB.replace(/[^0-9.-]+/g, ""));
    } else if (type === 'date') {
      valA = parseLocalDate(valA);
      valB = parseLocalDate(valB);
    } else {
      valA = valA.toLowerCase();
      valB = valB.toLowerCase();
    }

    if (valA < valB) return newDir === 'asc' ? -1 : 1;
    if (valA > valB) return newDir === 'asc' ? 1 : -1;
    return 0;
  });

  // Re-append rows
  rows.forEach(row => tbody.appendChild(row));
}

// ==================== Utility Functions ====================

function formatDate(dateStr) {
  if (!dateStr) return '-';
  const date = parseLocalDate(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function parseLocalDate(dateStr) {
  if (!dateStr) return null;
  if (dateStr instanceof Date) return dateStr;
  // If it's just YYYY-MM-DD, parse as calendar date to avoid TZ issues
  if (typeof dateStr === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const [year, month, day] = dateStr.split('-').map(Number);
    return new Date(year, month - 1, day);
  }
  return new Date(dateStr);
}

function getLocalDateString(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatDateTime(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  });
}

function formatCurrency(value) {
  if (value === null || value === undefined) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(value);
}

function formatSchedule(type, value) {
  switch (type) {
    case 'daily':
      return `Daily at ${value || '09:00'} `;
    case 'hourly':
      return `Hourly at:${value || '00'} `;
    case 'interval':
      return `Every ${value || 4} hours`;
    case 'cron':
      return value || 'Custom';
    default:
      return type;
  }
}

// ==================== Settings Page ====================

async function renderSettingsPage(container) {
  const headerHtml = generateUnifiedHeader({
    title: 'Settings',
    subtitle: 'Application configuration',
    primaryActions: [],
    secondaryActions: []
  });

  const locationOptions = locations.map(l =>
    `<option value="${l.id}">${l.name}</option>`
  ).join('');

  // Default date range: Last 1 Year
  const today = new Date();
  const oneYearAgo = new Date();
  oneYearAgo.setFullYear(today.getFullYear() - 1);
  const startDateStr = oneYearAgo.toISOString().split('T')[0];
  const endDateStr = today.toISOString().split('T')[0];

  container.innerHTML = `
    ${headerHtml}

    <div class="page-body">

      <!-- Weather Data Integration -->
      <div class="card mb-lg">
        <div class="card-header">
          <h3 class="card-title">Weather Data</h3>
        </div>
        <div class="card-body">
          <p class="text-secondary mb-md">
            Fetch historical weather data to enable temperature correlation analysis.
            <br><span class="text-xs">Requires locations to have Latitude/Longitude configured.</span>
          </p>

          <div class="grid grid-2 gap-md items-end mb-sm">
            <div class="form-group">
              <label class="form-label">Location</label>
              <select class="form-select" id="weather-location-select">
                <option value="">Select a location...</option>
                ${locationOptions}
              </select>
            </div>
            <div class="form-group">
              <button class="btn btn-primary w-full" onclick="runWeatherFetch()">
                Fetch Weather Data
              </button>
            </div>
          </div>
          
          <div class="grid grid-2 gap-md">
             <div class="form-group">
                <label class="form-label text-sm">Start Date</label>
                <input type="date" class="form-input" id="weather-start-date" value="${startDateStr}">
             </div>
             <div class="form-group">
                <label class="form-label text-sm">End Date</label>
                <input type="date" class="form-input" id="weather-end-date" value="${endDateStr}">
             </div>
          </div>

          <p class="text-xs text-secondary mt-xs">Retrieves daily history from Open-Meteo.</p>
        </div>
      </div>

      <!-- Data Normalization -->
      <div class="card mb-lg">
        <div class="card-header">
          <h3 class="card-title">Data Normalization</h3>
        </div>
        <div class="card-body">
          <p class="text-secondary mb-md">
            Reconstruct daily oil usage history by reconciling tank readings with order deliveries.
            <br><span class="text-xs text-secondary">Run this if you have added historical orders or want to smooth sensor data.</span>
          </p>

          <div class="grid grid-2 gap-md items-end mb-sm">
            <div class="form-group">
                <label class="form-label">Location</label>
                <select class="form-select" id="recalc-location-select">
                    <option value="">Select Location...</option>
                    ${locationOptions}
                </select>
            </div>
             <div class="form-group">
                <label class="form-label">Time Range</label>
                <select class="form-select" id="recalc-days">
                    <option value="">All Time (Full Rebuild)</option>
                    <option value="30">Last 30 Days</option>
                    <option value="60">Last 60 Days</option>
                    <option value="90">Last 90 Days</option>
                </select>
             </div>
          </div>
          <div class="form-group">
              <button class="btn btn-primary w-full" onclick="triggerUsageRecalculation()">
                Run Normalization
              </button>
          </div>
          <div id="normalization-status" class="mt-md text-sm"></div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Danger Zone</h3>
        </div>
        <div class="card-body">
          <p class="text-secondary mb-md">
            These actions are destructive and cannot be undone.
          </p>

          <div class="flex flex-col gap-md">
            <div class="flex items-center justify-between p-md border rounded" style="border-color: var(--error-light); background-color: rgba(255, 59, 48, 0.05);">
              <div>
                <h4 class="text-base font-medium text-error">Clear Database</h4>
                <p class="text-sm text-secondary">
                  Removes all scraped companies, prices, and aliases.
                  <br>By default, your configured locations are preserved.
                </p>
              </div>
              <button class="btn btn-danger" onclick="confirmResetDatabase()">
                Reset Data
              </button>
            </div>
          </div>
        </div>
      </div>

    </div>
  `;
}

function confirmResetDatabase() {
  document.getElementById('modal-title').textContent = 'Reset Database?';
  document.getElementById('modal-body').innerHTML = `
    < p class="mb-md text-error font-medium" > Warning: This will delete all scraped data!</p >
        <p class="mb-md">This includes:</p>
        <ul class="list-disc ml-lg mb-md text-secondary">
            <li>All companies and aliases</li>
            <li>All oil price history</li>
            <li>All oil orders (configured locations kept)</li>
        </ul>
        <div class="form-group">
            <label class="flex items-center gap-sm">
                <input type="checkbox" id="reset-include-locations">
                <span>Also delete Locations? (Factory Reset)</span>
            </label>
        </div>
        <p class="text-sm text-secondary">Are you absolutely sure?</p>
  `;

  document.getElementById('modal-confirm').onclick = async () => {
    const includeLocations = document.getElementById('reset-include-locations').checked;
    try {
      const res = await api.resetDatabase(includeLocations);
      showToast(res.message, 'success');
      closeModal();
      // Redirect to dashboard or simple reload
      setTimeout(() => window.location.reload(), 1000);
    } catch (error) {
      showToast('Reset failed: ' + error.message, 'error');
    }
  };

  // Set button style
  const confirmBtn = document.getElementById('modal-confirm');
  confirmBtn.className = 'btn btn-danger';

  openModal();
}

async function runWeatherFetch() {
  const select = document.getElementById('weather-location-select');
  const locationId = parseInt(select.value);
  const startInput = document.getElementById('weather-start-date');
  const endInput = document.getElementById('weather-end-date');

  if (!locationId) {
    showToast('Please select a location', 'error');
    return;
  }

  const location = locations.find(l => l.id === locationId);
  if (!location) { showToast('Location not found', 'error'); return; }

  if (!location.latitude || !location.longitude) {
    showToast(`Location "${location.name}" is missing Latitude/Longitude. Please edit the location details.`, 'error');
    return;
  }

  const btn = document.querySelector('button[onclick="runWeatherFetch()"]');
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<div class="loading-spinner" style="width:14px;height:14px;border-width:2px;display:inline-block;margin-right:8px;vertical-align:-2px;"></div> Fetching...';

  try {
    const startDate = startInput.value;
    const endDate = endInput.value || new Date().toISOString().split('T')[0];

    if (!startDate) {
      throw new Error('Please select a Start Date');
    }

    if (new Date(endDate) < new Date(startDate)) {
      throw new Error('End Date cannot be before Start Date');
    }

    const result = await api.fetchWeatherData(
      location.latitude,
      location.longitude,
      location.id,
      startDate,
      endDate
    );

    showToast(`Fetched weather data! Added ${result.created} new records.`, 'success');

  } catch (err) {
    showToast('Weather fetch failed: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalHtml;
  }
}

// ==================== Analytics ====================

async function renderAnalyticsPage(container) {
  // Set defaults if null
  if (!analyticsStartDate) {
    const d = new Date();
    d.setDate(d.getDate() - 90);
    analyticsStartDate = getLocalDateString(d);
  }
  if (!analyticsEndDate) {
    analyticsEndDate = getLocalDateString();
  }

  // Build unified header  
  const headerHtml = generateUnifiedHeader({
    title: 'Analytics',
    subtitle: 'Market Insights & Predictions',
    primaryActions: [],
    secondaryActions: [
      {
        label: 'Understanding Metrics',
        icon: headerIcons.help,
        onclick: 'showExpertHelpModal()'
      }
    ],
    controls: [
      {
        label: 'Date Range',
        items: [
          {
            type: 'custom',
            html: `
              <div class="flex gap-xs align-center flex-wrap">
                <input type="date" class="form-input form-input-sm" id="analytics-start" value="${analyticsStartDate}" onchange="updateAnalyticsFilters()">
                <span class="text-secondary text-sm">to</span>
                <input type="date" class="form-input form-input-sm" id="analytics-end" value="${analyticsEndDate}" onchange="updateAnalyticsFilters()">
              </div>
            `
          }
        ]
      },
      {
        label: 'Aggregation',
        items: [
          {
            type: 'select',
            id: 'analytics-aggregation',
            onchange: 'updateAnalyticsFilters()',
            options: [
              { value: 'daily', label: 'Daily', selected: analyticsAggregation === 'daily' },
              { value: 'weekly', label: 'Weekly', selected: analyticsAggregation === 'weekly' },
              { value: 'monthly', label: 'Monthly', selected: analyticsAggregation === 'monthly' }
            ]
          }
        ]
      }
    ]
  });

  // Custom inject for date inputs since they're not standard controls
  const customControlsHtml = `
    <div class="page-header-unified">
      <div class="page-header-main">
        <div class="header-title-zone">
          <h1 class="page-title">Analytics</h1>
          <p class="header-subtitle">Market Insights & Predictions</p>
        </div>
        
        <div class="header-actions-zone">
          <button class="btn btn-ghost btn-sm" onclick="showExpertHelpModal()" title="Understanding these metrics">
            ${headerIcons.help}
            <span>Guide</span>
          </button>
        </div>
      </div>
      
      <div class="header-controls-strip" id="header-controls-strip">
        <div class="controls-group">
          <span class="controls-group-label">Date Range</span>
          <div class="flex gap-xs align-center flex-wrap">
            <input type="date" class="form-input form-input-sm" id="analytics-start" value="${analyticsStartDate}" onchange="updateAnalyticsFilters()">
            <span class="text-secondary text-sm">to</span>
            <input type="date" class="form-input form-input-sm" id="analytics-end" value="${analyticsEndDate}" onchange="updateAnalyticsFilters()">
          </div>
        </div>
        <div class="controls-group">
          <span class="controls-group-label">Aggregation</span>
          <select class="form-select form-select-sm" id="analytics-aggregation" onchange="updateAnalyticsFilters()" style="width: auto; min-width: 100px;">
            <option value="daily" ${analyticsAggregation === 'daily' ? 'selected' : ''}>Daily</option>
            <option value="weekly" ${analyticsAggregation === 'weekly' ? 'selected' : ''}>Weekly</option>
            <option value="monthly" ${analyticsAggregation === 'monthly' ? 'selected' : ''}>Monthly</option>
          </select>
        </div>
      </div>
      <button class="controls-strip-toggle" id="controls-strip-toggle" onclick="toggleControlsStrip()">
        <span>Filters</span>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
    </div>
  `;

  container.innerHTML = `
    ${customControlsHtml}
    <div class="page-body">

        
        <!-- Market Outlook Card - Fully Responsive -->
        <div class="card mb-lg animate-fade-in" style="border-left: 4px solid var(--accent-primary);">
            <div class="card-body">
                <div class="market-outlook-container">
                    <!-- Top Row: Prediction + Commentary -->
                    <div class="market-outlook-header">
                        <!-- Prediction Hero -->
                        <div class="market-outlook-hero">
                            <h2 class="text-xs font-bold uppercase tracking-wider text-secondary" style="letter-spacing: 0.1em;">Market Outlook</h2>
                            <div id="prediction-badge" class="badge" style="padding: 10px 16px; font-size: 0.85rem; text-align: center; line-height: 1.3; display: flex; align-items: center; justify-content: center;">
                                Loading...
                            </div>
                        </div>

                        <!-- Analyst Commentary -->
                        <div class="market-outlook-insight">
                            <div class="expert-box-slim text-sm text-secondary" id="expert-summary" style="font-style: italic; line-height: 1.6;">
                                Analyzing market signals...
                            </div>
                        </div>
                    </div>
                    
                    <!-- KPI Strip - 4 columns on desktop, 2 on tablet, 2 on mobile -->
                    <div class="market-outlook-kpis">
                        <div class="kpi-mini">
                            <div class="kpi-mini-label">7d Trend</div>
                            <div id="trend-7d" class="kpi-mini-value">-</div>
                        </div>
                        <div class="kpi-mini">
                            <div class="kpi-mini-label">30d Trend</div>
                            <div id="trend-30d" class="kpi-mini-value">-</div>
                        </div>
                        <div class="kpi-mini">
                            <div class="kpi-mini-label">90d Trend</div>
                            <div id="trend-90d" class="kpi-mini-value">-</div>
                        </div>
                        <div class="kpi-mini">
                            <div class="kpi-mini-label">Pressure</div>
                            <div id="spread-impact" class="kpi-mini-value">-</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Charts Grid - Responsive 2:1 layout -->
        <div class="analytics-charts-grid">
            <!-- Lead-Lag Analysis (Main Chart) -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title flex items-center gap-sm flex-wrap">
                        <span>Future Price Predictor</span>
                        <span class="info-tag" data-help="lead-lag" title="Click for explanation">?</span>
                    </div>
                </div>
                <div class="card-body">
                    <p class="text-xs text-secondary mb-md" style="line-height: 1.5;">
                        <strong>How to read:</strong> When the orange line (wholesale) spikes, expect local prices (blue) to follow 2-3 days later.
                    </p>
                    <div class="chart-container" style="height: 320px;">
                        <canvas id="leadLagChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- Side Column -->
            <div class="analytics-side-column">
                <!-- Crack Spread -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title flex items-center gap-sm flex-wrap">
                            <span>3:2:1 Crack Spread</span>
                            <span class="info-tag" data-help="refinery-spread" title="Click for explanation">?</span>
                        </div>
                    </div>
                    <div class="card-body">
                        <p class="text-xs text-secondary mb-sm" style="line-height: 1.4;">
                            Refinery profit margin. High = supply strain.
                        </p>
                        <div class="chart-container" style="height: 160px;">
                            <canvas id="crackSpreadChart"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Rankings with Latest Price -->
                <div class="card rankings-card">
                    <div class="card-header">
                        <div class="card-title">Cheapest Providers</div>
                    </div>
                    <div class="card-body" style="padding: var(--space-sm);">
                        <div class="table-responsive-wrapper">
                            <table class="data-table">
                                <thead>
                                    <tr>
                                        <th>Company</th>
                                        <th>Avg</th>
                                        <th title="Latest reported price">Latest</th>
                                        <th>Samples</th>
                                    </tr>
                                </thead>
                                <tbody id="rankings-tbody">
                                    <tr><td colspan="4" class="text-center text-secondary">Loading providers...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Additional Trend Charts -->
        <div class="analytics-charts-grid mt-lg">
            <!-- Market Index Trends -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title flex items-center gap-sm">
                        <span>Market Index Trends</span>
                        <span class="info-tag" data-help="market-indices" title="Brent, WTI, Gasoline">?</span>
                    </div>
                </div>
                <div class="card-body">
                    <p class="text-xs text-secondary mb-md">
                        Global benchmarks for crude oil and refined gasoline.
                    </p>
                    <div class="chart-container" style="height: 280px;">
                        <canvas id="marketIndexChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- EIA Index Trends -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title flex items-center gap-sm">
                        <span>EIA Spot Price Trends</span>
                        <span class="info-tag" data-help="eia-indices" title="ULSD, WTI, Brent Spot">?</span>
                    </div>
                </div>
                <div class="card-body">
                    <p class="text-xs text-secondary mb-md">
                        Official EIA spot prices for key energy products.
                    </p>
                    <div class="chart-container" style="height: 280px;">
                        <canvas id="eiaIndexChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
    </div>
  `;

  try {
    // Fetch Data parallel
    const [leadLag, rankings, crackSpread, marketTrends, eiaTrends] = await Promise.all([
      api.getLeadLagAnalysis(analyticsStartDate, analyticsEndDate, analyticsAggregation),
      api.getCompanyRankings(analyticsStartDate, analyticsEndDate),
      api.getCrackSpread(analyticsStartDate, analyticsEndDate, analyticsAggregation),
      api.getCompanyTrends([2, 3, 4], analyticsStartDate, analyticsEndDate, analyticsAggregation),
      api.getCompanyTrends([5, 6, 7], analyticsStartDate, analyticsEndDate, analyticsAggregation)
    ]);

    // 1. Render Lead-Lag
    renderLeadLagChart(leadLag);

    // 2. Render Crack Spread
    renderCrackSpreadChart(crackSpread);

    // 3. Render Trend Charts
    renderMultiSeriesChart('marketIndexChart', 'marketIndex', marketTrends);
    renderMultiSeriesChart('eiaIndexChart', 'eiaIndex', eiaTrends);

    // 4. Update Outlook and Trends
    const trends = leadLag.analysis.local_trends;
    const formatDeltaFull = (val) => {
      const sign = val > 0 ? '+' : '';
      const colorClass = val > 0 ? 'sentiment-bad' : val < 0 ? 'sentiment-good' : 'text-secondary';
      const label = val > 0 ? 'Bearish' : val < 0 ? 'Bullish' : 'Neutral';
      return `
        <div class="${colorClass}">
            <span class="font-bold">${sign}${val.toFixed(3)}</span>
            <span class="trend-pill ${val > 0 ? 'bg-sentiment-bad' : 'bg-sentiment-good'}" style="margin-left: 4px;">${label}</span>
        </div>
      `;
    };

    document.getElementById('trend-7d').innerHTML = formatDeltaFull(trends['7d']);
    document.getElementById('trend-30d').innerHTML = formatDeltaFull(trends['30d']);
    document.getElementById('trend-90d').innerHTML = formatDeltaFull(trends['90d']);

    const spreadImpactEl = document.getElementById('spread-impact');
    const impactVal = leadLag.analysis.crack_spread_impact;
    spreadImpactEl.textContent = impactVal;
    spreadImpactEl.className = `kpi-mini-value ${impactVal === 'Positive' ? 'sentiment-bad' : (impactVal === 'Negative' ? 'sentiment-good' : '')}`;

    // Expert Insight Synthesis
    let insight = "";
    const pred = leadLag.analysis.prediction;
    const futTrend = leadLag.analysis.futures_trend_7d;

    if (pred.includes("Rise")) {
      insight = `Market indices (NY Harbor) are surging ($${futTrend.toFixed(2)} this week) while refinery margins are high. This indicates "Supply Pressure" is hitting wholesalers. Expect local prices to hike in 2-3 days. If tank is low, buy today.`;
    } else if (pred.includes("Fall")) {
      insight = `Market indices are cooling down. High refinery throughput is yielding a narrowing crack spread. This is the optimal window to wait—prices should soften by $0.05-$0.10 in the next 72 hours.`;
    } else {
      insight = `Neutral market sentiment. Global benchmarks are flat, and seasonal demand (90d trend: ${trends['90d'] > 0 ? 'Up' : 'Down'}) is balancing out. Stable pricing is expected for the upcoming week.`;
    }
    document.getElementById('expert-summary').textContent = insight;

    // Update Prediction Badge Styling
    const predBadge = document.getElementById('prediction-badge');
    predBadge.textContent = pred;
    if (pred.includes("Rise") || pred.includes("Upward")) {
      predBadge.className = "badge bg-sentiment-bad font-bold";
    } else if (pred.includes("Fall") || pred.includes("Downward")) {
      predBadge.className = "badge bg-sentiment-good font-bold";
    } else {
      predBadge.className = "badge bg-sentiment-warning font-bold";
    }

    // 3. Render Rankings
    const rankingBody = document.getElementById('rankings-tbody');
    if (rankings.length === 0) {
      rankingBody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary">No sufficient data.</td></tr>';
    } else {
      rankingBody.innerHTML = rankings.map(r => `
              <tr>
                  <td>${r.company}</td>
                  <td class="mono font-bold">$${r.avg_price.toFixed(3)}</td>
                  <td class="latest-price-col">
                    <div class="price-tooltip-container">
                        <span class="mono text-primary">$${r.latest_price.toFixed(3)}</span>
                        <div class="price-tooltip">Reported: ${new Date(r.latest_date).toLocaleDateString()}</div>
                    </div>
                  </td>
                  <td>${r.samples}</td>
              </tr>
          `).join('');
    }

  } catch (err) {
    showToast("Error loading analytics: " + err.message, "error");
  }

  // Fetch and Render Temperature Correlation for Analytics
  try {
    // Expert UX: Clean up previous chart instance to avoid "Canvas already in use" error
    if (typeof destroyChart === 'function') {
      destroyChart('analytics-temp');
    }

    const tempCorrelation = await api.getTemperatureCorrelation(analyticsStartDate, analyticsEndDate, analyticsAggregation);

    // Check if the container already exists from a previous render of the same page load
    let tempContainer = document.getElementById('analytics-temp-card');
    if (!tempContainer) {
      tempContainer = document.createElement('div');
      tempContainer.id = 'analytics-temp-card';
      tempContainer.className = 'card mt-lg';
      tempContainer.innerHTML = `
          <div class="card-header">
              <h3 class="card-title">Temperature & Usage Correlation</h3>
          </div>
          <div class="card-body">
              <div class="chart-container" style="height: 350px;">
                  <canvas id="analytics-temp-chart"></canvas>
              </div>
          </div>
        `;
      const pageBody = document.querySelector('.page-body');
      if (pageBody) pageBody.appendChild(tempContainer);
    }

    const tempCtx = document.getElementById('analytics-temp-chart');
    if (tempCtx && tempCorrelation.temperatures?.labels?.length > 0) {
      const chart = createTemperatureChart(tempCtx, tempCorrelation);
      if (typeof storeChart === 'function') {
        storeChart('analytics-temp', chart);
      }
    } else if (tempCtx) {
      tempCtx.parentElement.innerHTML = `
          <div class="empty-state" style="padding: var(--space-xl) 0;">
              <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--text-tertiary); margin-bottom: var(--space-md);">
                  <path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"></path>
              </svg>
              <h3 class="empty-state-title">No Weather Data</h3>
              <p class="empty-state-text">No data available for the selected period.</p>
          </div>
        `;
    }
  } catch (e) {
    console.error("Failed to load analytics temperature correlation", e);
  }

  // Expert UX: Bind interactive help tags
  document.querySelectorAll('.info-tag').forEach(tag => {
    tag.addEventListener('click', (e) => {
      e.stopPropagation();
      const helpId = tag.getAttribute('data-help');
      showExpertHelpModal(helpId);
    });
  });
}

function updateAnalyticsFilters() {
  analyticsStartDate = document.getElementById('analytics-start').value;
  analyticsEndDate = document.getElementById('analytics-end').value;
  analyticsAggregation = document.getElementById('analytics-aggregation').value;
  renderAnalyticsPage(document.getElementById('page-content'));
}

function renderLeadLagChart(data) {
  const canvas = document.getElementById('leadLagChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  // Expert UX: Ensure previous chart is destroyed BEFORE creating new one to prevent collision
  if (typeof destroyChart === 'function') {
    destroyChart('leadLag');
  }
  // Market data needs to be shifted by lag? No, backend just sends raw series. We visualize shift or just raw?
  // User requested: "If you see a $0.10 jump in futures today, you can predict a retail hike by Wednesday"
  // So plotting them on the same time axis allows seeing the lag visually.

  const dates = data.series.dates;
  const marketData = dates.map(d => data.series.market_ulds[d] || null);
  const localData = dates.map(d => data.series.local_avg[d] || null);

  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: dates,
      datasets: [
        {
          label: 'NY Harbor ULSD (Market)',
          data: marketData,
          borderColor: '#f59e0b', // Amber
          tension: 0.3,
          pointRadius: 0,
          spanGaps: true
        },
        {
          label: 'Local Avg Price',
          data: localData,
          borderColor: '#3b82f6', // Blue
          tension: 0.3,
          pointRadius: 0,
          spanGaps: true
        }
      ]
    },
    options: {
      responsive: true,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      maintainAspectRatio: false,
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day' },
          grid: { display: false }
        },
        y: {
          display: true,
          title: { display: true, text: 'Price ($/gal)' }
        }
      }
    }
  });

  // Store instance for cleanup
  if (typeof storeChart === 'function') {
    storeChart('leadLag', chart);
  }
}

function renderCrackSpreadChart(data) {
  const canvas = document.getElementById('crackSpreadChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  if (typeof destroyChart === 'function') {
    destroyChart('crackSpread');
  }
  const dates = data.map(d => d.date);
  const values = data.map(d => d.spread);

  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: dates,
      datasets: [{
        label: '3:2:1 Crack Spread ($/bbl)',
        data: values,
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'month' },
          grid: { display: false }
        },
        y: {
          title: { display: true, text: 'Margin ($/bbl)' }
        }
      }
    }
  });

  if (typeof storeChart === 'function') {
    storeChart('crackSpread', chart);
  }
}

function renderMultiSeriesChart(canvasId, chartKey, data) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  if (typeof destroyChart === 'function') {
    destroyChart(chartKey);
  }

  const colors = [
    '#3b82f6', // Blue
    '#f59e0b', // Amber
    '#10b981', // Emerald
    '#ef4444', // Red
    '#8b5cf6', // Violet
    '#ec4899'  // Pink
  ];

  let hasSecondaryAxis = false;

  const datasets = Object.keys(data.trends).map((cid, index) => {
    const trend = data.trends[cid];
    const isSecondary = trend.name.includes("RBOB Gasoline") || trend.name.includes("NY Harbor");
    if (isSecondary) hasSecondaryAxis = true;

    return {
      label: trend.name,
      data: data.dates.map(d => trend.data[d] || null),
      borderColor: colors[index % colors.length],
      backgroundColor: colors[index % colors.length] + '20',
      tension: 0.3,
      pointRadius: 0,
      spanGaps: true,
      yAxisID: isSecondary ? 'y1' : 'y'
    };
  });

  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.dates,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day' },
          grid: { display: false }
        },
        y: {
          display: true,
          position: 'left',
          title: {
            display: true,
            text: 'Price ($/bbl or $/gal)'
          },
          grid: { color: 'rgba(255, 255, 255, 0.05)' }
        },
        y1: {
          display: hasSecondaryAxis,
          position: 'right',
          title: {
            display: true,
            text: 'RBOB & NY Harbor ($/gal)'
          },
          grid: { drawOnChartArea: false },
          ticks: {
            callback: (value) => `$${value.toFixed(2)}`
          }
        }
      },
      plugins: {
        ...chartConfig.plugins,
        tooltip: {
          ...chartConfig.plugins.tooltip,
          callbacks: {
            label: (context) => `${context.dataset.label}: $${context.parsed.y.toFixed(3)}`
          }
        }
      }
    }
  });

  if (typeof storeChart === 'function') {
    storeChart(chartKey, chart);
  }
}

function showExpertHelpModal(focusId = null) {
  document.getElementById('modal-title').textContent = 'Analytics Guide';
  document.getElementById('modal-body').innerHTML = `
    <div class="help-modal-content">
      <!-- Quick Reference Legend -->
      <section>
        <h4 class="modal-section-title">Quick Reference: Color Indicators</h4>
        <div class="modal-grid-legend">
          <div class="legend-item">
            <span class="dot" style="background: var(--accent-success);"></span>
            <div>
              <div class="font-bold text-xs">Bullish</div>
              <div class="text-xs text-secondary">Price may fall</div>
            </div>
          </div>
          <div class="legend-item">
            <span class="dot" style="background: var(--accent-error);"></span>
            <div>
              <div class="font-bold text-xs">Bearish</div>
              <div class="text-xs text-secondary">Price may rise</div>
            </div>
          </div>
          <div class="legend-item">
            <span class="dot" style="background: var(--accent-warning);"></span>
            <div>
              <div class="font-bold text-xs">Neutral</div>
              <div class="text-xs text-secondary">Stable market</div>
            </div>
          </div>
        </div>
      </section>

      <!-- Future Price Predictor Explanation -->
      <section class="insight-card ${focusId === 'lead-lag' ? 'animate-pulse focus-shadow' : ''}" id="help-lead-lag">
        <div class="insight-header">
            <span class="font-bold">Future Price Predictor</span>
            <span class="badge badge-warning text-xs">Primary Signal</span>
        </div>
        <div class="insight-body">
            <p class="text-sm">
              <strong>What it shows:</strong> The orange line is the NY Harbor wholesale diesel price. The blue line is your local average price. Wholesale markets move first—local vendors follow 2-3 days later.
            </p>
            <div class="help-text-grid">
                <div class="p-xs" style="background: rgba(239, 68, 68, 0.1); border-radius: var(--radius-sm);">
                    <span class="sentiment-bad font-bold block mb-xs">↑ Orange Line Rising</span>
                    <span class="text-xs text-secondary">Wholesale is climbing. Expect local prices to rise in 2-3 days. Buy now if you need oil.</span>
                </div>
                <div class="p-xs" style="background: rgba(74, 222, 128, 0.1); border-radius: var(--radius-sm);">
                    <span class="sentiment-good font-bold block mb-xs">↓ Orange Line Falling</span>
                    <span class="text-xs text-secondary">Wholesale is dropping. Wait 3 days—local prices will follow and you'll save money.</span>
                </div>
            </div>
        </div>
      </section>

      <!-- Crack Spread Explanation -->
      <section class="insight-card ${focusId === 'refinery-spread' ? 'animate-pulse focus-shadow' : ''}" id="help-refinery-spread">
        <div class="insight-header">
            <span class="font-bold">3:2:1 Crack Spread</span>
            <span class="badge badge-error text-xs">Supply Indicator</span>
        </div>
        <div class="insight-body">
            <p class="text-sm">
              <strong>What it shows:</strong> The refinery profit margin. This measures how much refineries make turning crude oil into diesel and gasoline.
            </p>
            <div class="help-text-box" style="margin-top: var(--space-sm);">
                <div class="text-sm mb-sm">
                  <span class="sentiment-bad font-bold">High/Rising:</span> Indicates supply strain. Even if crude oil is cheap, high refinery margins keep retail prices elevated.
                </div>
                <div class="text-sm">
                  <span class="sentiment-good font-bold">Low/Falling:</span> Healthy supply conditions. Retailers have more room to offer discounts.
                </div>
            </div>
        </div>
        </div>
      </section>

      <!-- Market Indices Explanation -->
      <section class="insight-card ${focusId === 'market-indices' ? 'animate-pulse focus-shadow' : ''}" id="help-market-indices">
        <div class="insight-header">
            <span class="font-bold">Market Indices</span>
            <span class="badge badge-info text-xs">Global Benchmarks</span>
        </div>
        <div class="insight-body">
            <p class="text-sm">
              <strong>What it shows:</strong> Brent and WTI Crude are global benchmarks for raw oil. RBOB Gasoline shows the price for refined motor fuel.
            </p>
            <p class="text-xs text-secondary mt-sm">
              While heating oil is a different product, it strongly correlates with these global benchmarks.
            </p>
        </div>
      </section>

      <!-- EIA Indices Explanation -->
      <section class="insight-card ${focusId === 'eia-indices' ? 'animate-pulse focus-shadow' : ''}" id="help-eia-indices">
        <div class="insight-header">
            <span class="font-bold">EIA Spot Prices</span>
            <span class="badge badge-secondary text-xs">Official Data</span>
        </div>
        <div class="insight-body">
            <p class="text-sm">
              <strong>What it shows:</strong> Official spot prices from the Energy Information Administration (EIA). These are the "ground truth" for wholesale energy markets.
            </p>
        </div>
      </section>

      <!-- Trend Metrics Explanation -->
      <section class="insight-card">
        <div class="insight-header">
            <span class="font-bold">Understanding Trend KPIs</span>
            <span class="badge badge-info text-xs">Metrics Guide</span>
        </div>
        <div class="insight-body">
            <p class="text-sm mb-sm">
              The 7d, 30d, and 90d trends show how local oil prices have changed over each period.
            </p>
            <div class="text-sm text-secondary" style="line-height: 1.6;">
              • <strong>Bullish (green):</strong> Prices have fallen — good for buyers<br>
              • <strong>Bearish (red):</strong> Prices have risen — consider buying before further increases<br>
              • <strong>Pressure:</strong> Indicates direction of wholesale market influence
            </div>
        </div>
      </section>

       <!-- HDD Explanation -->
      <section class="insight-card">
        <div class="insight-header">
            <span class="font-bold">Heating Degree Days (HDD)</span>
            <span class="badge badge-info text-xs">Weather Indicator</span>
        </div>
        <div class="insight-body">
            <p class="text-sm mb-sm">
              HDD is based on a "base temperature"—the outdoor temperature at which a building generally requires no artificial heating. In the United States, this standard base is 65°F (18°C)
            </p>
            <p class="text-sm mb-sm">
              HDD= Base Temperature (65F) - Daily Mean Temperature
            </p>
            <div class="text-sm text-secondary" style="line-height: 1.6;">
              • <strong>Step 1:</strong> Calculate the daily mean temperature: 6$\frac{\text{High} + \text{Low}}{2}$<br>
              • <strong>Step 2:</strong> If the mean is below 65°F, subtract it from 65. The result is your HDD for that day.<br>
              • <strong>Step 3:</strong> If the mean is 65°F or higher, the HDD for that day is zero
            </div>
        </div>
      </section>
    </div>
  `;
  const confirmBtn = document.getElementById('modal-confirm');
  confirmBtn.textContent = 'Understood';
  confirmBtn.className = "btn btn-primary w-full";
  confirmBtn.onclick = closeModal;
  openModal();

  if (focusId) {
    const el = document.getElementById('help-' + focusId);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}


async function triggerUsageRecalculation() {
  const locId = document.getElementById('recalc-location-select').value;
  const days = document.getElementById('recalc-days').value;
  const statusEl = document.getElementById('normalization-status');

  if (!locId) {
    alert("Please select a location");
    return;
  }

  statusEl.innerHTML = '<span class="text-info">Processing... please wait.</span>';

  try {
    let url = `/tank/recalculate-daily-usage?location_id=${locId}`;
    if (days) url += `&days=${days}`;

    const result = await api.request(url, { method: 'POST' });

    statusEl.innerHTML = `<span class="text-success" style="color:var(--accent-success)">✔ Normalization complete. Updated ${result.total_records} records.</span>`;
    setTimeout(() => statusEl.innerHTML = '', 5000);
  } catch (e) {
    console.error(e);
    statusEl.innerHTML = `<span class="text-error" style="color:var(--accent-error)">Error: ${e.message}</span>`;
  }
}
window.triggerUsageRecalculation = triggerUsageRecalculation;

// ==================== Unified Header System Utilities ====================

/**
 * Toggle the overflow menu visibility
 */
function toggleOverflowMenu(event) {
  event?.stopPropagation();
  const menu = document.getElementById('header-overflow-menu');
  if (menu) {
    menu.classList.toggle('active');

    // Close menu when clicking outside
    if (menu.classList.contains('active')) {
      document.addEventListener('click', closeOverflowMenuOnClickOutside);
    }
  }
}

function closeOverflowMenuOnClickOutside(event) {
  const menu = document.getElementById('header-overflow-menu');
  const btn = document.getElementById('header-overflow-btn');

  if (menu && !menu.contains(event.target) && !btn?.contains(event.target)) {
    menu.classList.remove('active');
    document.removeEventListener('click', closeOverflowMenuOnClickOutside);
  }
}

function closeOverflowMenu() {
  const menu = document.getElementById('header-overflow-menu');
  if (menu) {
    menu.classList.remove('active');
    document.removeEventListener('click', closeOverflowMenuOnClickOutside);
  }
}

/**
 * Toggle the controls strip visibility (mobile)
 */
function toggleControlsStrip() {
  const strip = document.getElementById('header-controls-strip');
  const toggle = document.getElementById('controls-strip-toggle');

  if (strip && toggle) {
    strip.classList.toggle('collapsed');
    toggle.classList.toggle('expanded');
  }
}

/**
 * Update selection bar visibility and count
 */
function updateSelectionBar(count, itemType = 'items') {
  const bar = document.getElementById('header-selection-bar');
  const countEl = document.getElementById('selection-count');

  if (bar) {
    if (count > 0) {
      bar.classList.add('active');
      if (countEl) {
        countEl.textContent = `${count} ${itemType} selected`;
      }
    } else {
      bar.classList.remove('active');
    }
  }
}

/**
 * Toggle chip active state
 */
/**
 * Update chip active state based on checkbox
 */
function updateChipState(input) {
  const label = input.closest('.toggle-chip');
  if (label) {
    if (input.checked) label.classList.add('active');
    else label.classList.remove('active');
  }
}

/**
 * Generate unified header HTML
 * @param {Object} config - Header configuration
 * @returns {string} HTML string
 */
function generateUnifiedHeader(config) {
  const {
    title,
    subtitle = null,
    primaryActions = [],
    secondaryActions = [],
    controls = [],
    showOverflowOnDesktop = false
  } = config;

  // Generate primary action buttons
  const primaryButtonsHtml = primaryActions.map(action => {
    const iconHtml = action.icon || '';
    return `
      <button class="btn ${action.class || 'btn-primary'} btn-sm" 
              onclick="${action.onclick}" 
              id="${action.id || ''}"
              ${action.style ? `style="${action.style}"` : ''}>
        ${iconHtml}
        <span>${action.label}</span>
      </button>
    `;
  }).join('');

  // Generate secondary action buttons (Desktop only)
  const secondaryButtonsHtml = secondaryActions.map(action => {
    if (action.divider) return '';
    const iconHtml = action.icon || '';
    return `
      <button class="btn btn-secondary btn-sm btn-secondary-action" 
              onclick="${action.onclick}" 
              id="${action.id || ''}"
              ${action.style ? `style="${action.style}"` : ''}>
        ${iconHtml}
        <span>${action.label}</span>
      </button>
    `;
  }).join('');


  // Generate overflow menu items
  const overflowItemsHtml = secondaryActions.map(action => {
    if (action.divider) {
      return '<div class="overflow-menu-divider"></div>';
    }
    const iconHtml = action.icon || '';
    return `
      <button class="overflow-menu-item ${action.danger ? 'danger' : ''}" 
              onclick="${action.onclick}; closeOverflowMenu();">
        ${iconHtml}
        <span>${action.label}</span>
      </button>
    `;
  }).join('');

  // Generate controls strip
  let controlsHtml = '';
  if (controls.length > 0) {
    const controlGroupsHtml = controls.map(group => {
      const itemsHtml = group.items.map(item => {
        if (item.type === 'toggle') {
          return `
            <label class="toggle-chip ${item.checked ? 'active' : ''}">
              <input type="checkbox" ${item.checked ? 'checked' : ''} id="${item.id || ''}" onchange="updateChipState(this); ${item.onchange || ''}">
              <span>${item.label}</span>
            </label>
          `;
        } else if (item.type === 'select') {
          const optionsHtml = item.options.map(opt =>
            `<option value="${opt.value}" ${opt.selected ? 'selected' : ''}>${opt.label}</option>`
          ).join('');
          return `
            <select class="form-select form-select-sm" id="${item.id || ''}" onchange="${item.onchange || ''}" style="width: auto; min-width: 100px;">
              ${optionsHtml}
            </select>
          `;
        }
        return '';
      }).join('');

      return `
        <div class="controls-group">
          ${group.label ? `<span class="controls-group-label">${group.label}</span>` : ''}
          ${itemsHtml}
        </div>
      `;
    }).join('');

    controlsHtml = `
      <button class="controls-strip-toggle" id="controls-strip-toggle" onclick="toggleControlsStrip()">
        <span>View Options</span>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
      <div class="header-controls-strip" id="header-controls-strip">
        ${controlGroupsHtml}
      </div>
    `;
  }

  // Selection bar (hidden by default)
  const selectionBarHtml = `
    <div class="header-selection-bar" id="header-selection-bar">
      <div class="selection-info">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 11 12 14 22 4"></polyline>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
        </svg>
        <span id="selection-count">0 items selected</span>
      </div>
      <div class="selection-actions" id="selection-actions">
        <!-- Selection-specific actions will be injected here -->
      </div>
    </div>
  `;

  return `
    <div class="page-header-unified">
      <div class="page-header-main">
        <div class="header-title-zone">
          <h1 class="page-title">${title}</h1>
          ${subtitle ? `<p class="header-subtitle">${subtitle}</p>` : ''}
        </div>
        
        <div class="header-actions-zone">
          ${secondaryButtonsHtml}
          ${primaryButtonsHtml}
          
          ${secondaryActions.length > 0 ? `
            <button class="header-overflow-btn" id="header-overflow-btn" onclick="toggleOverflowMenu(event)">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="1"></circle>
                <circle cx="12" cy="5" r="1"></circle>
                <circle cx="12" cy="19" r="1"></circle>
              </svg>
            </button>
            <div class="header-overflow-menu" id="header-overflow-menu">
              ${overflowItemsHtml}
            </div>
          ` : ''}
        </div>
      </div>
      
      ${controlsHtml}
      ${selectionBarHtml}
    </div>
  `;
}

// Icon SVG helpers for header actions
const headerIcons = {
  add: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>`,
  import: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>`,
  trash: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`,
  settings: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>`,
  refresh: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>`,
  play: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`,
  merge: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"></path></svg>`,
  help: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`,
  filter: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>`,
  download: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>`,
};

