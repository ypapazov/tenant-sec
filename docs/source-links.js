/**
 * Controls Explorer source-link helpers.
 * Collects control/service references (and evidence_item URLs already present
 * on the same control) into safe, deduplicated, readable link records.
 * Does not invent sources that are absent from the assessment payload.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  root.TenantSecSourceLinks = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function isSafeHttpUrl(url) {
    if (typeof url !== 'string') return false;
    const trimmed = url.trim();
    if (!trimmed) return false;
    try {
      const parsed = new URL(trimmed);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:';
    } catch {
      return false;
    }
  }

  function readableTitleFromUrl(url) {
    try {
      const parsed = new URL(url);
      const parts = parsed.pathname.split('/').filter(Boolean);
      if (parts.length) {
        let leaf = parts[parts.length - 1];
        try {
          leaf = decodeURIComponent(leaf);
        } catch {
          /* keep raw segment */
        }
        leaf = leaf.replace(/\.(html?|md|pdf)$/i, '').replace(/[-_]+/g, ' ').trim();
        if (leaf) return leaf;
      }
      return parsed.hostname;
    } catch {
      return url;
    }
  }

  function preferTitle(title, url) {
    const candidate = typeof title === 'string' ? title.trim() : '';
    if (candidate && candidate !== url) return candidate;
    return readableTitleFromUrl(url);
  }

  function addSource(byUrl, url, title, serviceId) {
    if (!isSafeHttpUrl(url)) return;
    const key = url.trim();
    let entry = byUrl.get(key);
    if (!entry) {
      entry = { url: key, title: null, services: new Set() };
      byUrl.set(key, entry);
    }
    const candidate = typeof title === 'string' ? title.trim() : '';
    if (candidate && candidate !== key) {
      if (!entry.title || entry.title === key) entry.title = candidate;
    } else if (!entry.title) {
      entry.title = null;
    }
    if (typeof serviceId === 'string' && serviceId.trim()) {
      entry.services.add(serviceId.trim());
    }
  }

  function addReferenceList(byUrl, refs, serviceId) {
    if (!Array.isArray(refs)) return;
    for (const ref of refs) {
      if (!ref || typeof ref !== 'object') continue;
      addSource(byUrl, ref.url, ref.title, serviceId);
    }
  }

  /**
   * Collect clickable sources for one control assessment object.
   * @param {object|null|undefined} ctrl Provider control entry from YAML/JSON
   * @returns {{url: string, title: string, services: string[]}[]}
   */
  function collectControlSources(ctrl) {
    if (!ctrl || typeof ctrl !== 'object') return [];
    const byUrl = new Map();

    addReferenceList(byUrl, ctrl.references, null);

    const services = ctrl.services;
    if (services && typeof services === 'object' && !Array.isArray(services)) {
      for (const [svcId, svc] of Object.entries(services)) {
        if (!svc || typeof svc !== 'object') continue;
        addReferenceList(byUrl, svc.references, svcId);
      }
    }

    // evidence_items are already on the control; reuse their titles / URLs
    // and applicability.services for association — do not fabricate new docs.
    const items = ctrl.evidence_items;
    if (Array.isArray(items)) {
      for (const item of items) {
        if (!item || typeof item !== 'object') continue;
        const apps = item.applicability && Array.isArray(item.applicability.services)
          ? item.applicability.services
          : [];
        if (apps.length) {
          for (const svc of apps) {
            if (typeof svc === 'string' && svc.trim()) {
              addSource(byUrl, item.url, item.title, svc);
            }
          }
        } else {
          addSource(byUrl, item.url, item.title, null);
        }
      }
    }

    return Array.from(byUrl.values())
      .map((entry) => ({
        url: entry.url,
        title: preferTitle(entry.title, entry.url),
        services: Array.from(entry.services).sort((a, b) => a.localeCompare(b)),
      }))
      .sort((a, b) => a.title.localeCompare(b.title) || a.url.localeCompare(b.url));
  }

  /**
   * Sources for one expanded service row (service refs only).
   * @param {object|null|undefined} svc
   * @param {string} [serviceId]
   */
  function collectServiceSources(svc, serviceId) {
    if (!svc || typeof svc !== 'object') return [];
    const byUrl = new Map();
    addReferenceList(byUrl, svc.references, serviceId || null);
    return Array.from(byUrl.values())
      .map((entry) => ({
        url: entry.url,
        title: preferTitle(entry.title, entry.url),
        services: Array.from(entry.services).sort((a, b) => a.localeCompare(b)),
      }))
      .sort((a, b) => a.title.localeCompare(b.title) || a.url.localeCompare(b.url));
  }

  /**
   * @param {{url: string, title: string, services?: string[]}[]} sources
   * @param {(value: string) => string} escHtml
   * @param {{emptyHtml?: string, showServices?: boolean}} [opts]
   */
  function renderSourceLinksHtml(sources, escHtml, opts) {
    const options = opts || {};
    const showServices = options.showServices !== false;
    if (!Array.isArray(sources) || !sources.length) {
      return options.emptyHtml != null
        ? options.emptyHtml
        : '<div class="pa-no-refs">No reference links yet</div>';
    }
    return sources.map((src) => {
      const safeUrl = escHtml(src.url);
      const safeTitle = escHtml(src.title || src.url);
      const services = Array.isArray(src.services) ? src.services : [];
      const svcHtml = showServices && services.length
        ? `<span class="ref-services" title="Associated services">${services.map((s) => escHtml(s)).join(', ')}</span>`
        : '';
      return `<div class="ref-item">` +
        `<a class="ref-link" href="${safeUrl}" target="_blank" rel="noopener noreferrer">${safeTitle}</a>` +
        svcHtml +
        `</div>`;
    }).join('');
  }

  return {
    isSafeHttpUrl,
    preferTitle,
    readableTitleFromUrl,
    collectControlSources,
    collectServiceSources,
    renderSourceLinksHtml,
  };
});
