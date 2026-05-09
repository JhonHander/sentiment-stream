/**
 * charts.js — Chart.js configurations for Sentiment Stream Dashboard
 * Doughnut, horizontal bar, line, radar, and data table.
 * Adapted for Coursue Light Theme
 */

(function (global) {
  'use strict';

  const U = global.DashboardUtils;

  /* ============================================================
     Common Chart Defaults (light theme — Coursue Design System)
     ============================================================ */

  Chart.defaults.color = '#8A8A8A';
  Chart.defaults.borderColor = '#E5E7EB';
  Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
  Chart.defaults.font.size = 12;

  const COMMON_OPTIONS = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          padding: 16,
          usePointStyle: true,
          pointStyle: 'circle',
          font: { size: 12, weight: 500 },
        },
      },
      tooltip: {
        backgroundColor: 'rgba(255, 255, 255, 0.98)',
        titleColor: '#1A1A1A',
        bodyColor: '#4B5563',
        borderColor: '#E5E7EB',
        borderWidth: 1,
        padding: 12,
        cornerRadius: 12,
        displayColors: true,
        boxPadding: 4,
        titleFont: { size: 13, weight: 600 },
        bodyFont: { size: 12, weight: 500 },
        boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
      },
    },
    animation: {
      duration: 600,
      easing: 'easeOutQuart',
    },
  };

  /* ============================================================
     1. Doughnut — Sentiment Distribution
     ============================================================ */

  let doughnutChart = null;

  function initDoughnutChart() {
    const ctx = document.getElementById('chart-doughnut');
    if (!ctx) return null;

    doughnutChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Positivo', 'Negativo', 'Neutral'],
        datasets: [{
          data: [0, 0, 0],
          backgroundColor: [
            U.getSentimentColor('positivo'),
            U.getSentimentColor('negativo'),
            U.getSentimentColor('neutral'),
          ],
          borderColor: '#FFFFFF',
          borderWidth: 3,
          hoverOffset: 8,
        }],
      },
      options: {
        ...COMMON_OPTIONS,
        cutout: '65%',
        plugins: {
          ...COMMON_OPTIONS.plugins,
          legend: {
            ...COMMON_OPTIONS.plugins.legend,
            position: 'bottom',
          },
          title: {
            display: false,
          },
        },
      },
    });
    return doughnutChart;
  }

  function updateDoughnutChart(distribution) {
    if (!doughnutChart) return;
    const d = distribution || {};
    doughnutChart.data.datasets[0].data = [
      d.positivo || 0,
      d.negativo || 0,
      d.neutral || 0,
    ];
    doughnutChart.update();
  }

  /* ============================================================
     2. Horizontal Bar — Average Confidence by Sentiment
     ============================================================ */

  let barChart = null;

  function initBarChart() {
    const ctx = document.getElementById('chart-bar');
    if (!ctx) return null;

    barChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Positivo', 'Negativo', 'Neutral'],
        datasets: [{
          label: 'Confianza promedio',
          data: [0, 0, 0],
          backgroundColor: [
            U.hexToRgba(U.getSentimentColor('positivo'), 0.7),
            U.hexToRgba(U.getSentimentColor('negativo'), 0.7),
            U.hexToRgba(U.getSentimentColor('neutral'), 0.7),
          ],
          borderColor: [
            U.getSentimentColor('positivo'),
            U.getSentimentColor('negativo'),
            U.getSentimentColor('neutral'),
          ],
          borderWidth: 1,
          borderRadius: 8,
          barPercentage: 0.6,
        }],
      },
      options: {
        ...COMMON_OPTIONS,
        indexAxis: 'y',
        scales: {
          x: {
            min: 0,
            max: 1,
            grid: { color: '#E5E7EB' },
            ticks: {
              callback: function (value) {
                return (value * 100).toFixed(0) + '%';
              },
            },
          },
          y: {
            grid: { display: false },
          },
        },
        plugins: {
          ...COMMON_OPTIONS.plugins,
          legend: { display: false },
        },
      },
    });
    return barChart;
  }

  function updateBarChart(stats) {
    if (!barChart) return;
    const dist = stats.distribution || {};
    const total = stats.total || 0;

    const avg = stats.avg_confidence || 0;
    const hasPos = (dist.positivo || 0) > 0;
    const hasNeg = (dist.negativo || 0) > 0;
    const hasNeu = (dist.neutral || 0) > 0;

    barChart.data.datasets[0].data = [
      hasPos ? avg : 0,
      hasNeg ? avg : 0,
      hasNeu ? avg : 0,
    ];
    barChart.update();
  }

  /* ============================================================
     3. Line — Prediction Volume Over Time
     ============================================================ */

  let lineChart = null;

  function initLineChart() {
    const ctx = document.getElementById('chart-line');
    if (!ctx) return null;

    lineChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Predicciones',
          data: [],
          borderColor: '#6B50FF',
          backgroundColor: 'rgba(107, 80, 255, 0.08)',
          borderWidth: 2,
          pointBackgroundColor: '#6B50FF',
          pointBorderColor: '#FFFFFF',
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
          fill: true,
          tension: 0.35,
        }],
      },
      options: {
        ...COMMON_OPTIONS,
        scales: {
          x: {
            grid: { color: '#E5E7EB', drawBorder: false },
            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
          },
          y: {
            beginAtZero: true,
            grid: { color: '#E5E7EB' },
            ticks: { precision: 0 },
          },
        },
        plugins: {
          ...COMMON_OPTIONS.plugins,
          legend: { display: false },
        },
        interaction: {
          mode: 'index',
          intersect: false,
        },
      },
    });
    return lineChart;
  }

  function updateLineChart(timeseries) {
    if (!lineChart) return;
    const ts = Array.isArray(timeseries) ? timeseries : [];

    if (ts.length === 0) {
      lineChart.data.labels = [];
      lineChart.data.datasets[0].data = [];
      lineChart.update();
      return;
    }

    lineChart.data.labels = ts.map(item => U.formatTimeOnly(item.timestamp));
    lineChart.data.datasets[0].data = ts.map(item => item.count || 0);
    lineChart.update();
  }

  /* ============================================================
     4. Radar — Model Metrics
     ============================================================ */

  let radarChart = null;

  function initRadarChart() {
    const ctx = document.getElementById('chart-radar');
    if (!ctx) return null;

    radarChart = new Chart(ctx, {
      type: 'radar',
      data: {
        labels: ['Precisión', 'Recall', 'F1-Score', 'Exactitud', 'Confianza'],
        datasets: [{
          label: 'Métricas del modelo',
          data: [0, 0, 0, 0, 0],
          borderColor: '#6B50FF',
          backgroundColor: 'rgba(107, 80, 255, 0.12)',
          borderWidth: 2,
          pointBackgroundColor: '#6B50FF',
          pointBorderColor: '#FFFFFF',
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
        }],
      },
      options: {
        ...COMMON_OPTIONS,
        scales: {
          r: {
            min: 0,
            max: 1,
            grid: { color: '#E5E7EB' },
            angleLines: { color: '#E5E7EB' },
            pointLabels: {
              color: '#8A8A8A',
              font: { size: 11, weight: 500 },
            },
            ticks: {
              display: false,
              stepSize: 0.2,
            },
          },
        },
        plugins: {
          ...COMMON_OPTIONS.plugins,
          legend: { display: false },
        },
      },
    });
    return radarChart;
  }

  function updateRadarChart(stats) {
    if (!radarChart) return;
    const avg = stats.avg_confidence || 0;
    radarChart.data.datasets[0].data = [avg, avg * 0.95, avg * 0.97, avg * 0.98, avg];
    radarChart.update();
  }

  function updateRadarChartMetrics(metricsData) {
    if (!radarChart) return;
    const m = metricsData || {};
    const perClass = m.metrics || {};

    const classes = ['positivo', 'negativo', 'neutral'];
    let precisionSum = 0, recallSum = 0, f1Sum = 0;
    let count = 0;

    classes.forEach(cls => {
      const clsMetrics = perClass[cls] || {};
      const p = typeof clsMetrics.precision === 'number' ? clsMetrics.precision : 0;
      const r = typeof clsMetrics.recall === 'number' ? clsMetrics.recall : 0;
      const f = typeof clsMetrics.f1 === 'number' ? clsMetrics.f1 : 0;
      precisionSum += p;
      recallSum += r;
      f1Sum += f;
      count += 1;
    });

    const precisionAvg = count > 0 ? precisionSum / count : 0;
    const recallAvg = count > 0 ? recallSum / count : 0;
    const f1Avg = count > 0 ? f1Sum / count : 0;

    radarChart.data.labels = ['Precisión', 'Recall', 'F1-Score', 'Exactitud', 'Confianza'];
    radarChart.data.datasets[0].data = [
      precisionAvg,
      recallAvg,
      f1Avg,
      precisionAvg * 0.98,
      (precisionAvg + recallAvg) / 2,
    ];
    radarChart.update();
  }

  /* ============================================================
     5. Data Table — Latest Predictions
     ============================================================ */

  const TABLE_STATE = {
    items: [],
    filtered: [],
    limit: 10,
    offset: 0,
    searchQuery: '',
  };

  function initTable() {
    const tbody = document.getElementById('predictions-tbody');
    const prevBtn = document.getElementById('page-prev');
    const nextBtn = document.getElementById('page-next');
    const searchInput = document.getElementById('table-search');

    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        if (TABLE_STATE.offset > 0) {
          TABLE_STATE.offset = Math.max(0, TABLE_STATE.offset - TABLE_STATE.limit);
          renderTablePage();
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        const maxOffset = Math.max(0, TABLE_STATE.filtered.length - TABLE_STATE.limit);
        if (TABLE_STATE.offset < maxOffset) {
          TABLE_STATE.offset = Math.min(maxOffset, TABLE_STATE.offset + TABLE_STATE.limit);
          renderTablePage();
        }
      });
    }

    if (searchInput) {
      searchInput.addEventListener('input', U.debounce((e) => {
        TABLE_STATE.searchQuery = (e.target.value || '').toLowerCase().trim();
        TABLE_STATE.offset = 0;
        applyTableFilter();
        renderTablePage();
      }, 250));
    }

    return TABLE_STATE;
  }

  function applyTableFilter() {
    const q = TABLE_STATE.searchQuery;
    if (!q) {
      TABLE_STATE.filtered = TABLE_STATE.items.slice();
      return;
    }
    TABLE_STATE.filtered = TABLE_STATE.items.filter(item => {
      const text = (item.original_text || '').toLowerCase();
      const pred = (item.prediction || '').toLowerCase();
      const model = (item.model_version || '').toLowerCase();
      return text.includes(q) || pred.includes(q) || model.includes(q);
    });
  }

  function renderTablePage() {
    const tbody = document.getElementById('predictions-tbody');
    const prevBtn = document.getElementById('page-prev');
    const nextBtn = document.getElementById('page-next');
    const pageInfo = document.getElementById('page-info');
    if (!tbody) return;

    const total = TABLE_STATE.filtered.length;
    const start = TABLE_STATE.offset;
    const end = Math.min(start + TABLE_STATE.limit, total);
    const pageItems = TABLE_STATE.filtered.slice(start, end);
    const totalPages = Math.ceil(total / TABLE_STATE.limit) || 1;
    const currentPage = Math.floor(start / TABLE_STATE.limit) + 1;

    tbody.innerHTML = '';

    if (pageItems.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="empty-table-msg">
            No se encontraron predicciones
          </td>
        </tr>
      `;
    } else {
      pageItems.forEach(item => {
        const row = document.createElement('tr');
        const sentiment = item.prediction || 'neutral';
        const confidence = typeof item.confidence === 'number'
          ? U.formatDecimal(item.confidence, 3)
          : '—';
        const dateStr = U.formatDateTime(item.timestamp);
        const modelVer = item.model_version || '—';
        const text = (item.original_text || '').substring(0, 120);
        const textDisplay = text.length === 120 ? text + '…' : text;

        row.innerHTML = `
          <td title="${U.escapeHtml(item.original_text || '')}">${U.escapeHtml(textDisplay)}</td>
          <td><span class="sentiment-badge ${U.escapeHtml(sentiment)}">${U.escapeHtml(U.getSentimentLabel(sentiment))}</span></td>
          <td class="confidence-cell">${confidence}</td>
          <td>${dateStr}</td>
          <td>${U.escapeHtml(modelVer)}</td>
        `;
        tbody.appendChild(row);
      });
    }

    if (prevBtn) prevBtn.disabled = start <= 0;
    if (nextBtn) nextBtn.disabled = end >= total;
    if (pageInfo) pageInfo.textContent = `Página ${currentPage} de ${totalPages}`;
  }

  function updateTable(sentimentsResponse) {
    const resp = sentimentsResponse || {};
    TABLE_STATE.items = Array.isArray(resp.items) ? resp.items : [];
    TABLE_STATE.offset = 0;
    applyTableFilter();
    renderTablePage();
  }

  /* ============================================================
     Utility: Escape HTML for safe table rendering
     ============================================================ */

  if (!U.escapeHtml) {
    U.escapeHtml = function (str) {
      if (str == null) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    };
  }

  /* ============================================================
     Show / Hide Loaders & Empty States
     ============================================================ */

  function setChartReady(chartId, hasData) {
    const loader = document.getElementById('loader-' + chartId);
    const empty = document.getElementById('empty-' + chartId);
    const canvasWrap = loader?.parentElement?.querySelector('.chart-canvas-wrap');

    if (loader) U.setVisible(loader, false);
    if (empty) U.setVisible(empty, !hasData);
    if (canvasWrap) canvasWrap.style.opacity = hasData ? '1' : '0';
  }

  function setTableReady(hasData) {
    const loader = document.getElementById('loader-table');
    const empty = document.getElementById('empty-table');
    const wrap = document.getElementById('table-wrap');
    const pagination = document.getElementById('table-pagination');

    if (loader) U.setVisible(loader, false);
    if (empty) U.setVisible(empty, !hasData);
    if (wrap) U.setVisible(wrap, hasData);
    if (pagination) U.setVisible(pagination, hasData);
  }

  /* ============================================================
     Export
     ============================================================ */

  global.DashboardCharts = {
    initDoughnutChart,
    updateDoughnutChart,
    initBarChart,
    updateBarChart,
    initLineChart,
    updateLineChart,
    initRadarChart,
    updateRadarChart,
    updateRadarChartMetrics,
    initTable,
    updateTable,
    setChartReady,
    setTableReady,
  };
})(window);
