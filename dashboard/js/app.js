/**
 * app.js — Main application logic for Sentiment Stream Dashboard
 * Polling, error handling, offline banner, auto-refresh, keyboard shortcuts.
 */

(function (global) {
  'use strict';

  const U = global.DashboardUtils;
  const C = global.DashboardCharts;

  /* ============================================================
     Configuration
     ============================================================ */

  const CONFIG = {
    API_BASE: (() => {
      // Allow override via query param or localStorage
      const params = new URLSearchParams(window.location.search);
      const paramBase = params.get('api');
      if (paramBase) return paramBase.replace(/\/$/, '');
      try {
        const stored = localStorage.getItem('sentiment_api_base');
        if (stored) return stored.replace(/\/$/, '');
      } catch (_e) { /* ignore */ }
      return 'http://localhost:8000';
    })(),
    REFRESH_INTERVAL_MS: 10000,
    RETRY_ATTEMPTS: 3,
    RETRY_DELAY_MS: 1000,
  };

  /* ============================================================
     State
     ============================================================ */

  const state = {
    polling: true,
    intervalId: null,
    retryCount: 0,
    lastStats: null,
    lastSentiments: null,
    chartsInitialized: false,
  };

  /* ============================================================
     API Helpers
     ============================================================ */

  async function fetchWithRetry(url, options = {}, retries = CONFIG.RETRY_ATTEMPTS) {
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      if (retries > 0) {
        await new Promise(resolve => setTimeout(resolve, CONFIG.RETRY_DELAY_MS));
        return fetchWithRetry(url, options, retries - 1);
      }
      throw error;
    }
  }

  async function fetchStats() {
    return fetchWithRetry(`${CONFIG.API_BASE}/stats?period=hour`);
  }

  async function fetchSentiments(limit = 50, offset = 0) {
    return fetchWithRetry(`${CONFIG.API_BASE}/sentiments?limit=${limit}&offset=${offset}`);
  }

  async function fetchModelMetrics() {
    try {
      return await fetchWithRetry(`${CONFIG.API_BASE}/model-metrics`);
    } catch (_e) {
      // Graceful fallback: if metrics don't exist yet, return null
      return null;
    }
  }

  async function fetchHealth() {
    try {
      const res = await fetch(`${CONFIG.API_BASE}/health`, { method: 'GET' });
      return res.ok;
    } catch (_e) {
      return false;
    }
  }

  /* ============================================================
     UI Updates
     ============================================================ */

  function updateStatus(online) {
    const pill = document.getElementById('status-pill');
    const label = document.getElementById('status-label');
    if (!pill || !label) return;

    if (online) {
      pill.classList.add('online');
      pill.classList.remove('offline');
      label.textContent = 'En línea';
    } else {
      pill.classList.remove('online');
      pill.classList.add('offline');
      label.textContent = 'Sin conexión';
    }
  }

  function showOfflineBanner(show) {
    const banner = document.getElementById('offline-banner');
    U.setVisible(banner, show);
  }

  function updateLastRefresh() {
    const el = document.getElementById('last-update');
    if (el) {
      el.textContent = 'Actualizado: ' + new Date().toLocaleTimeString('es-ES');
    }
  }

  function updateKPIs(stats) {
    const totalEl = document.getElementById('kpi-total-value');
    const confEl = document.getElementById('kpi-confidence-value');
    const domEl = document.getElementById('kpi-dominant-value');
    const timeEl = document.getElementById('kpi-uptime-value');

    if (totalEl) totalEl.textContent = U.formatInteger(stats.total);
    if (confEl) confEl.textContent = U.formatPercent(stats.avg_confidence, 1);

    if (domEl) {
      const dist = stats.distribution || {};
      const entries = Object.entries(dist);
      if (entries.length > 0) {
        const dominant = entries.reduce((a, b) => (a[1] > b[1] ? a : b))[0];
        domEl.textContent = U.getSentimentLabel(dominant);
        domEl.style.color = U.getSentimentColor(dominant);
      } else {
        domEl.textContent = '—';
        domEl.style.color = '';
      }
    }

    if (timeEl) timeEl.textContent = new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
  }

  /* ============================================================
     Data Refresh
     ============================================================ */

  async function refreshData(force = false) {
    if (!state.polling && !force) return;

    try {
      const [stats, sentiments, modelMetrics] = await Promise.all([
        fetchStats(),
        fetchSentiments(100, 0),
        fetchModelMetrics(),
      ]);

      state.lastStats = stats;
      state.lastSentiments = sentiments;
      state.retryCount = 0;

      // Update UI
      updateStatus(true);
      showOfflineBanner(false);
      updateLastRefresh();
      updateKPIs(stats);

      // Update charts
      const dist = stats.distribution || {};
      const hasData = Object.keys(dist).length > 0 && (stats.total || 0) > 0;

      C.updateDoughnutChart(dist);
      C.setChartReady('doughnut', hasData);

      C.updateBarChart(stats);
      C.setChartReady('bar', hasData);

      const ts = Array.isArray(stats.timeseries) ? stats.timeseries : [];
      C.updateLineChart(ts);
      C.setChartReady('line', ts.length > 0);

      if (modelMetrics && modelMetrics.metrics) {
        C.updateRadarChartMetrics(modelMetrics);
        C.setChartReady('radar', true);
      } else {
        C.updateRadarChart(stats);
        C.setChartReady('radar', hasData);
      }

      const items = sentiments.items || [];
      C.updateTable(sentiments);
      C.setTableReady(items.length > 0);

    } catch (error) {
      state.retryCount += 1;
      console.error('Refresh failed:', error);

      if (state.retryCount >= CONFIG.RETRY_ATTEMPTS) {
        updateStatus(false);
        showOfflineBanner(true);
      }
    }
  }

  /* ============================================================
     Polling Control
     ============================================================ */

  function startPolling() {
    if (state.intervalId) return;
    state.polling = true;
    state.intervalId = setInterval(() => refreshData(false), CONFIG.REFRESH_INTERVAL_MS);
    updateToggleButton(true);
  }

  function stopPolling() {
    if (state.intervalId) {
      clearInterval(state.intervalId);
      state.intervalId = null;
    }
    state.polling = false;
    updateToggleButton(false);
  }

  function togglePolling() {
    if (state.polling) {
      stopPolling();
    } else {
      startPolling();
      refreshData(true);
    }
  }

  function updateToggleButton(active) {
    const btn = document.getElementById('toggle-polling-btn');
    const pauseIcon = document.getElementById('pause-icon');
    const playIcon = document.getElementById('play-icon');
    if (!btn) return;

    btn.classList.toggle('active', active);
    btn.setAttribute('aria-label', active ? 'Pausar auto-refresh' : 'Reanudar auto-refresh');
    if (pauseIcon) U.setVisible(pauseIcon, active);
    if (playIcon) U.setVisible(playIcon, !active);
  }

  /* ============================================================
     Event Listeners
     ============================================================ */

  function bindEvents() {
    const refreshBtn = document.getElementById('refresh-btn');
    const toggleBtn = document.getElementById('toggle-polling-btn');
    const retryBtn = document.getElementById('retry-btn');

    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => refreshData(true));
    }

    if (toggleBtn) {
      toggleBtn.addEventListener('click', togglePolling);
    }

    if (retryBtn) {
      retryBtn.addEventListener('click', () => {
        state.retryCount = 0;
        refreshData(true);
      });
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      // Ignore if inside input/textarea
      const tag = (e.target && e.target.tagName) || '';
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;

      if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        refreshData(true);
      }
      if (e.key === 'p' || e.key === 'P') {
        e.preventDefault();
        togglePolling();
      }
    });

    // Visibility API: pause when tab hidden to save resources
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        // Don't stop polling completely, just let the interval fire
        // in background; browsers throttle it automatically.
      } else {
        // Refresh immediately when user returns
        refreshData(true);
      }
    });
  }

  /* ============================================================
     Initialization
     ============================================================ */

  async function init() {
    // Initialize chart instances
    C.initDoughnutChart();
    C.initBarChart();
    C.initLineChart();
    C.initRadarChart();
    C.initTable();

    // Show initial loaders
    ['doughnut', 'bar', 'line', 'radar'].forEach(id => C.setChartReady(id, false));
    C.setTableReady(false);

    bindEvents();

    // Do an immediate first fetch
    await refreshData(true);

    // Start periodic polling
    startPolling();
  }

  // Boot when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose for debugging
  global.DashboardApp = {
    refreshData,
    startPolling,
    stopPolling,
    togglePolling,
    CONFIG,
    state,
  };
})(window);
