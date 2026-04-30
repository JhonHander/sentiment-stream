/**
 * utils.js — Utility functions for the Sentiment Stream Dashboard
 * Date formatting, number formatting, debounce/throttle, color utilities
 */

(function (global) {
  'use strict';

  const SENTIMENT_COLORS = {
    positivo:  '#10b981',
    negativo:  '#ef4444',
    neutral:   '#6b7280',
  };

  const SENTIMENT_LABELS = {
    positivo: 'Positivo',
    negativo: 'Negativo',
    neutral:  'Neutral',
  };

  /* ============================================================
     Date / Time Formatting
     ============================================================ */

  function formatDateTime(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return String(isoString);
    return d.toLocaleString('es-ES', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  }

  function formatRelativeTime(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return String(isoString);
    const diff = Date.now() - d.getTime();
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (seconds < 10) return 'hace un instante';
    if (seconds < 60) return `hace ${seconds}s`;
    if (minutes < 60) return `hace ${minutes}m`;
    if (hours < 24) return `hace ${hours}h`;
    if (days < 7) return `hace ${days}d`;
    return formatDateTime(isoString);
  }

  function formatTimeOnly(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return String(isoString);
    return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
  }

  /* ============================================================
     Number Formatting
     ============================================================ */

  function formatPercent(value, decimals = 1) {
    if (value === null || value === undefined || isNaN(value)) return '—';
    return (Number(value) * 100).toFixed(decimals) + '%';
  }

  function formatDecimal(value, decimals = 2) {
    if (value === null || value === undefined || isNaN(value)) return '—';
    return Number(value).toFixed(decimals);
  }

  function formatInteger(value) {
    if (value === null || value === undefined || isNaN(value)) return '—';
    return Number(value).toLocaleString('es-ES');
  }

  /* ============================================================
     Debounce / Throttle
     ============================================================ */

  function debounce(fn, wait = 300) {
    let timer = null;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  function throttle(fn, limit = 300) {
    let inThrottle = false;
    return function (...args) {
      if (!inThrottle) {
        fn.apply(this, args);
        inThrottle = true;
        setTimeout(() => { inThrottle = false; }, limit);
      }
    };
  }

  /* ============================================================
     Color Utilities
     ============================================================ */

  function hexToRgba(hex, alpha = 1) {
    const clean = hex.replace('#', '');
    const bigint = parseInt(clean, 16);
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function getSentimentColor(key, alpha = 1) {
    const hex = SENTIMENT_COLORS[key] || SENTIMENT_COLORS.neutral;
    return alpha === 1 ? hex : hexToRgba(hex, alpha);
  }

  function getSentimentLabel(key) {
    return SENTIMENT_LABELS[key] || key;
  }

  /* ============================================================
     DOM Helpers
     ============================================================ */

  function toggleClass(el, className, force) {
    if (!el) return;
    if (typeof force === 'boolean') {
      el.classList.toggle(className, force);
    } else {
      el.classList.toggle(className);
    }
  }

  function setVisible(el, visible) {
    toggleClass(el, 'hidden', !visible);
  }

  /* ============================================================
     Export
     ============================================================ */

  global.DashboardUtils = {
    formatDateTime,
    formatRelativeTime,
    formatTimeOnly,
    formatPercent,
    formatDecimal,
    formatInteger,
    debounce,
    throttle,
    hexToRgba,
    getSentimentColor,
    getSentimentLabel,
    toggleClass,
    setVisible,
    SENTIMENT_COLORS,
    SENTIMENT_LABELS,
  };
})(window);
