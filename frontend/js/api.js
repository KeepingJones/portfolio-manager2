const API = {
  async _fetch(url, opts = {}) {
    const profile = localStorage.getItem('portfolio_profile') || 'default';
    const headers = { 
        'Content-Type': 'application/json',
        'X-Profile': profile
    };
    const r = await fetch(url, { headers: headers, ...opts });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(err.detail || r.statusText);
    }
    if (r.status === 204) return null;
    return r.json();
  },

  // Positions
  getPositions: () => API._fetch('/api/positions'),
  getPosition: (id) => API._fetch(`/api/positions/${id}`),
  createPosition: (data) => API._fetch('/api/positions', { method: 'POST', body: JSON.stringify(data) }),
  updatePosition: (id, data) => API._fetch(`/api/positions/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePosition: (id) => API._fetch(`/api/positions/${id}`, { method: 'DELETE' }),

  // Summary
  getSummary: () => API._fetch('/api/summary'),

  // Refresh
  refreshAll: () => API._fetch('/api/refresh', { method: 'POST' }),
  refreshOne: (id) => API._fetch(`/api/refresh/${id}`, { method: 'POST' }),

  // Dividends
  getDividendEvents: () => API._fetch('/api/dividends'),
  getUpcomingDividends: () => API._fetch('/api/dividends/upcoming'),
  getReceivedDividends: () => API._fetch('/api/dividends/received'),
  logReceived: (data) => API._fetch('/api/dividends/received', { method: 'POST', body: JSON.stringify(data) }),
  deleteReceived: (id) => API._fetch(`/api/dividends/received/${id}`, { method: 'DELETE' }),
  fetchDividends: (positionId) => API._fetch(`/api/dividends/fetch/${positionId}`, { method: 'POST' }),
  fetchAllDividends: () => API._fetch('/api/dividends/fetch-all', { method: 'POST' }),
  getCalendar: () => API._fetch('/api/dividends/calendar'),

  // Manual price
  setManualPrice: (id, price, currency) => API._fetch(`/api/positions/${id}/price`, { method: 'POST', body: JSON.stringify({ price, currency }) }),

  // Projections
  getProjections: () => API._fetch('/api/projections'),

  // T212
  previewT212: () => API._fetch('/api/t212/preview'),
  importT212: () => API._fetch('/api/t212/import', { method: 'POST' }),

  // Settings
  getSettings: () => API._fetch('/api/settings'),
  updateSettings: (data) => API._fetch('/api/settings', { method: 'PUT', body: JSON.stringify(data) }),

  // Profiles
  getProfiles: () => API._fetch('/api/profiles'),
  createProfile: (id, name) => API._fetch('/api/profiles', { method: 'POST', body: JSON.stringify({ id, name }) }),
  updateProfile: (id, name) => API._fetch(`/api/profiles/${id}`, { method: 'PUT', body: JSON.stringify({ id, name }) }),
  deleteProfile: (id) => API._fetch(`/api/profiles/${id}`, { method: 'DELETE' }),

  // AI
  streamAIAnalysis: async (onChunk, onDone, onError) => {
    try {
      const profile = localStorage.getItem('portfolio_profile') || 'default';
      const r = await fetch('/api/ai/analyze', { headers: { 'X-Profile': profile } });
      if (!r.ok) {
        const err = await r.text();
        throw new Error(err || r.statusText);
      }
      
      const reader = r.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        if (chunk) onChunk(chunk);
      }
      onDone();
    } catch (err) {
      onError(err);
    }
  },

  getOllamaModels: async () => {
    const profile = localStorage.getItem('portfolio_profile') || 'default';
    const r = await fetch('/api/ai/models', { headers: { 'X-Profile': profile } });
    if (!r.ok) {
      const err = await r.text();
      throw new Error(err || r.statusText);
    }
    return await r.json();
  }
};
