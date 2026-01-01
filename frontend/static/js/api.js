/**
 * Oil Price Tracker - API Client
 */

const API_BASE = '/api';

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

    const config = {
      ...options,
      headers
    };

    if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
      config.body = JSON.stringify(config.body);
    }

    try {
      const response = await fetch(url, config);

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

  async getTemperatureCorrelation(days = 365, locationId = null) {
    const params = new URLSearchParams({ days });
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

  async importYahooHistorical(symbol, days = 365) {
    return this.request(`/import/yahoo-finance?symbol=${symbol}&days=${days}`, { method: 'POST' });
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
}

// Global API instance
const api = new ApiClient();
