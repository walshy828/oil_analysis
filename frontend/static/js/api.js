/**
 * Oil Price Tracker - API Client
 */

const API_BASE = '/api';
const API_KEY_STORAGE = 'oil_tracker_api_key';

/** Retrieve the stored API key, prompting the user if absent. */
function getApiKey() {
  return localStorage.getItem(API_KEY_STORAGE) || '';
}

/** Persist a new API key and reload so all pending calls use it. */
function setApiKey(key) {
  localStorage.setItem(API_KEY_STORAGE, key.trim());
}

/** Show a simple inline modal asking for the API key. Returns a Promise<string>. */
function promptApiKey(message = 'Enter your API key to access the Oil Price Tracker:') {
  return new Promise((resolve) => {
    // Reuse or create overlay
    let overlay = document.getElementById('api-key-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'api-key-overlay';
      overlay.style.cssText = [
        'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9999',
        'display:flex;align-items:center;justify-content:center',
      ].join(';');
      overlay.innerHTML = `
        <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:32px;min-width:340px;max-width:420px;box-shadow:0 24px 48px rgba(0,0,0,0.5)">
          <h3 style="margin:0 0 8px;color:#f1f5f9;font-size:18px;font-weight:600">API Key Required</h3>
          <p id="api-key-msg" style="margin:0 0 20px;color:#94a3b8;font-size:14px"></p>
          <input id="api-key-input" type="password" placeholder="Paste your API key"
            style="width:100%;box-sizing:border-box;padding:10px 14px;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#f1f5f9;font-size:14px;outline:none;margin-bottom:16px"/>
          <div style="display:flex;gap:10px;justify-content:flex-end">
            <button id="api-key-save" style="padding:9px 20px;border-radius:8px;border:none;background:#3b82f6;color:#fff;font-size:14px;font-weight:500;cursor:pointer">Save &amp; Continue</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
    }

    document.getElementById('api-key-msg').textContent = message;
    const input = document.getElementById('api-key-input');
    input.value = '';
    overlay.style.display = 'flex';

    const save = () => {
      const val = input.value.trim();
      if (!val) return;
      overlay.style.display = 'none';
      resolve(val);
    };

    document.getElementById('api-key-save').onclick = save;
    input.onkeydown = (e) => { if (e.key === 'Enter') save(); };
    setTimeout(() => input.focus(), 50);
  });
}

class ApiClient {
  constructor(baseUrl = API_BASE) {
    this.baseUrl = baseUrl;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;

    // Default headers
    const headers = { ...options.headers };

    // Only set default JSON content-type if not FormData
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }

    // Attach API key
    const apiKey = getApiKey();
    if (apiKey) headers['X-API-Key'] = apiKey;

    const config = {
      ...options,
      headers
    };

    if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
      config.body = JSON.stringify(config.body);
    }

    try {
      const response = await fetch(url, config);

      // If forbidden, the key is missing or wrong — prompt and retry once
      if (response.status === 403) {
        const newKey = await promptApiKey('Invalid or missing API key. Enter your API key:');
        setApiKey(newKey);
        return this.request(endpoint, options);
      }

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch (e) {
          errorData = { detail: `HTTP ${response.status}: ${response.statusText}` };
        }

        let message = 'An error occurred';
        if (typeof errorData.detail === 'string') {
          message = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          // Handle FastAPI validation errors
          message = errorData.detail.map(err => `${err.loc.join('.')}: ${err.msg}`).join('; ');
        } else if (errorData.detail && typeof errorData.detail === 'object') {
          message = JSON.stringify(errorData.detail);
        } else if (errorData.message) {
          message = errorData.message;
        }

        throw new Error(message);
      }

      return await response.json();
    } catch (error) {
      console.error(`API Error [${endpoint}]:`, error);
      throw error;
    }
  }

  // Dashboard
  async getDashboardSummary() {
    return this.request('/dashboard/summary');
  }

  async getPriceTrends(days = 90, companyId = null) {
    const params = new URLSearchParams({ days });
    if (companyId) params.append('company_id', companyId);
    return this.request(`/dashboard/price-trends?${params}`);
  }

  async getOrderTrends(months = 12, locationId = null) {
    const params = new URLSearchParams({ months });
    if (locationId) params.append('location_id', locationId);
    return this.request(`/dashboard/order-trends?${params}`);
  }

  async getOrderInsights() {
    return this.request('/dashboard/order-insights');
  }

  async getTemperatureCorrelation(dateFrom = null, dateTo = null, aggregation = 'daily', locationId = null) {
    const params = new URLSearchParams();
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    if (aggregation) params.append('aggregation', aggregation);
    if (locationId) params.append('location_id', locationId);
    return this.request(`/dashboard/temperature-correlation?${params}`);
  }

  // Companies
  async getCompanies(search = '') {
    const params = search ? `?search=${encodeURIComponent(search)}` : '';
    return this.request(`/companies${params}`);
  }

  async createCompany(data) {
    return this.request('/companies', { method: 'POST', body: data });
  }

  async mergeCompanies(sourceId, targetId) {
    return this.request(`/companies/${sourceId}/merge/${targetId}`, { method: 'POST' });
  }

  async deleteCompany(id) {
    return this.request(`/companies/${id}`, { method: 'DELETE' });
  }

  // Oil Prices
  async getOilPrices(filters = {}) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        params.append(key, value);
      }
    });
    return this.request(`/oil-prices?${params}`);
  }

  async getLatestPrices(filters = {}) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        params.append(key, value);
      }
    });
    // stale_days=0 means "no age-out" — all companies regardless of last price date.
    // Callers may pass stale_days > 0 to filter out stale vendors.
    if (!('stale_days' in filters)) params.append('stale_days', '0');
    return this.request(`/oil-prices/latest?${params}`);
  }

  async getCompanyPriceHistory(companyId, days = 90) {
    return this.request(`/oil-prices/history/${companyId}?days=${days}`);
  }

  async importPrices(file) {
    const formData = new FormData();
    formData.append('file', file);
    return this.request('/oil-prices/import', { method: 'POST', body: formData });
  }

  async resetDatabase(includeLocations = false) {
    return this.request(`/system/reset-database?include_locations=${includeLocations}`, {
      method: 'POST'
    });
  }

  async updateOilPrice(id, data) {
    return this.request(`/oil-prices/${id}`, { method: 'PUT', body: data });
  }

  async deleteOilPrice(id) {
    return this.request(`/oil-prices/${id}`, { method: 'DELETE' });
  }

  async deleteOilPricesBulk(ids = null, dateBefore = null) {
    const params = new URLSearchParams();
    if (ids) {
      ids.forEach(id => params.append('ids', id));
    }
    if (dateBefore) {
      params.append('date_before', dateBefore);
    }
    return this.request(`/oil-prices?${params}`, { method: 'DELETE' });
  }

  // Locations
  async getLocations() {
    return this.request('/locations');
  }

  async createLocation(data) {
    return this.request('/locations', { method: 'POST', body: data });
  }

  async updateLocation(id, data) {
    return this.request(`/locations/${id}`, { method: 'PUT', body: data });
  }

  async deleteLocation(id) {
    return this.request(`/locations/${id}`, { method: 'DELETE' });
  }

  // Oil Orders
  async getOrders(locationId = null) {
    const params = locationId ? `?location_id=${locationId}` : '';
    return this.request(`/orders${params}`);
  }

  async createOrder(data) {
    return this.request('/orders', { method: 'POST', body: data });
  }

  async updateOrder(id, data) {
    return this.request(`/orders/${id}`, { method: 'PUT', body: data });
  }

  async deleteOrder(id) {
    return this.request(`/orders/${id}`, { method: 'DELETE' });
  }

  async importOrders(locationId, file) {
    const formData = new FormData();
    formData.append('location_id', locationId);
    formData.append('file', file);

    return this.request('/orders/import', {
      method: 'POST',
      body: formData
    });
  }

  async validateOrderDates(locationId, startDate, endDate = null, excludeOrderId = null) {
    const params = new URLSearchParams({ location_id: locationId, start_date: startDate });
    if (endDate) params.append('end_date', endDate);
    if (excludeOrderId) params.append('exclude_order_id', excludeOrderId);
    return this.request(`/orders/validate-dates?${params}`);
  }

  // Temperatures
  async getTemperatures(filters = {}) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        params.append(key, value);
      }
    });
    return this.request(`/temperatures?${params}`);
  }

  async uploadTemperatures(file, locationId = null) {
    const formData = new FormData();
    formData.append('file', file);

    const url = `/temperatures/upload${locationId ? `?location_id=${locationId}` : ''}`;
    return this.request(url, {
      method: 'POST',
      body: formData
    });
  }

  // Analytics
  async getLeadLagAnalysis(dateFrom, dateTo, aggregation = 'daily') {
    let url = `/analytics/lead-lag?aggregation=${aggregation}`;
    if (dateFrom) url += `&date_from=${dateFrom}`;
    if (dateTo) url += `&date_to=${dateTo}`;
    return this.request(url);
  }

  async getCompanyRankings(dateFrom, dateTo) {
    let url = '/analytics/company-rankings?';
    if (dateFrom) url += `date_from=${dateFrom}`;
    if (dateTo) url += `&date_to=${dateTo}`;
    return this.request(url);
  }

  async getCrackSpread(dateFrom, dateTo, aggregation = 'daily') {
    let url = `/analytics/crack-spread?aggregation=${aggregation}`;
    if (dateFrom) url += `&date_from=${dateFrom}`;
    if (dateTo) url += `&date_to=${dateTo}`;
    return this.request(url);
  }

  async getCompanyTrends(companyIds, dateFrom, dateTo, aggregation = 'daily') {
    const params = new URLSearchParams({ aggregation });
    companyIds.forEach(id => params.append('company_ids', id));
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    return this.request(`/analytics/company-trends?${params}`);
  }

  async getYoYComparison(year = null, locationId = null) {
    let url = '/analytics/yoy-comparison?';
    if (year) url += `year=${year}`;
    if (locationId) url += `${year ? '&' : ''}location_id=${locationId}`;
    return this.request(url);
  }

  // Tank Usage
  async uploadTankReadings(file, locationId) {
    const formData = new FormData();
    formData.append('file', file);

    const url = `${this.baseUrl}/tank/upload?location_id=${locationId}`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail);
    }

    return response.json();
  }

  async getTankReadings(locationId, days = 30, includeAnomalies = false) {
    return this.request(`/tank/readings?location_id=${locationId}&days=${days}&include_anomalies=${includeAnomalies}`);
  }

  async getTankUsageSummary(locationId, days = 30) {
    return this.request(`/tank/usage-summary?location_id=${locationId}&days=${days}`);
  }

  async getTankCurrentLevel(locationId) {
    return this.request(`/tank/current-level?location_id=${locationId}`);
  }

  async getTankFillEvents(locationId) {
    return this.request(`/tank/fill-events?location_id=${locationId}`);
  }

  async syncSmartOilGauge() {
    return this.request('/tank/sync', { method: 'POST' });
  }

  async getSnapshots(type = 'local', limit = 30) {
    return this.request(`/oil-prices/snapshots?type=${type}&limit=${limit}`);
  }

  // Temperature / Weather
  async getTemperatures(locationId, days = 30) {
    const dateFrom = new Date();
    dateFrom.setDate(dateFrom.getDate() - days);
    return this.request(`/temperatures?location_id=${locationId}&date_from=${dateFrom.toISOString().split('T')[0]}`);
  }

  async fetchWeatherData(latitude, longitude, locationId, startDate, endDate) {
    let url = `/temperatures/fetch-weather?latitude=${latitude}&longitude=${longitude}`;
    if (locationId) url += `&location_id=${locationId}`;
    if (startDate) url += `&start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;
    return this.request(url, { method: 'POST' });
  }

  async getHddSummary(locationId, days = 30) {
    return this.request(`/temperatures/hdd-summary?location_id=${locationId}&days=${days}`);
  }

  async getUsageCorrelation(locationId, days = 90) {
    return this.request(`/temperatures/usage-correlation?location_id=${locationId}&days=${days}`);
  }

  async uploadTemperatureCsv(file, locationId) {
    const formData = new FormData();
    formData.append('file', file);

    const url = `${this.baseUrl}/temperatures/upload?location_id=${locationId}`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail);
    }

    return response.json();
  }

  // Scrape Config
  async getScrapeConfigs() {
    return this.request('/scrape/configs');
  }

  async createScrapeConfig(data) {
    return this.request('/scrape/configs', { method: 'POST', body: data });
  }

  async updateScrapeConfig(id, data) {
    return this.request(`/scrape/configs/${id}`, { method: 'PUT', body: data });
  }

  async deleteScrapeConfig(id) {
    return this.request(`/scrape/configs/${id}`, { method: 'DELETE' });
  }

  async runScrapeNow(configId) {
    return this.request(`/scrape/run/${configId}`, { method: 'POST' });
  }

  async getScrapeHistory(configId = null, days = null, limit = 50) {
    const params = new URLSearchParams({ limit });
    if (configId) params.append('config_id', configId);
    if (days) params.append('days', days);
    return this.request(`/scrape/history?${params}`);
  }

  async getScraperTypes() {
    return this.request('/scrape/types');
  }

  // Historical Import
  async getAvailableImportSymbols() {
    return this.request('/import/available-symbols');
  }

  async importYahooHistorical(symbol, days = null, startDate = null, endDate = null) {
    let url = `/import/yahoo-finance?symbol=${symbol}`;
    if (days) url += `&days=${days}`;
    if (startDate) url += `&start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;
    return this.request(url, { method: 'POST' });
  }

  async importEiaHistorical(series, apiKey, startDate, endDate) {
    let url = `/import/eia?series=${series}`;
    if (apiKey) url += `&api_key=${apiKey}`;
    if (startDate) url += `&start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;
    return this.request(url, { method: 'POST' });
  }

  async importEiaCrackSpreadBulk(apiKey, days = 365) {
    let url = `/import/eia/crack-spread-bulk?days=${days}`;
    if (apiKey) url += `&api_key=${apiKey}`;
    return this.request(url, { method: 'POST' });
  }

  // AI Analysis
  async getAiAnalysis() {
    return this.request('/ai/analysis');
  }

  // Dashboard tank status
  async getDashboardTankStatus(locationId = null) {
    const params = locationId ? `?location_id=${locationId}` : '';
    return this.request(`/dashboard/tank-status${params}`);
  }
}

// Global API instance
const api = new ApiClient();
