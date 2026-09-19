/**
 * khujo.js — Khujo Search Engine
 * All client logic: search bar, suggestions, SERP loader, KG renderer
 * Vanilla ES module. No framework. No bundler. Target: < 8 KB.
 */

/* ── 1. CONFIG ──────────────────────────────────────────── */
function getApiBase() {
  const meta = document.querySelector('meta[name="khujo-api"]');
  if (meta && meta.content && !meta.content.includes('localhost')) {
    return meta.content.replace(/\/$/, '');
  }
  if (window.location.port === '8080' || window.location.hostname !== 'localhost') {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return window.location.origin;
}
const API_BASE = getApiBase();

/* ── 2. ICON HELPERS (inline SVG strings) ───────────────── */

const icon = {
  search: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>`,
  x: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>`,
  arrowUpRight: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg>`,
  externalLink: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>`,
  fileText: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>`,
  sparkles: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>`,
  network: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M12 12V8"/></svg>`,
  shieldCheck: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>`,
  searchX: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m13.5 8.5-5 5"/><path d="m8.5 8.5 5 5"/><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`,
  alertTriangle: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
};

/* ── 3. SEARCH BAR ──────────────────────────────────────── */
class SearchBar {
  constructor(inputEl, wrapEl, opts = {}) {
    this.input = inputEl;
    this.wrap = wrapEl;
    this.onSearch = opts.onSearch || null; // callback(query)
    this.suggestions = [];
    this.activeIndex = -1;
    this.debounceTimer = null;
    this.focused = false;

    // Build DOM elements
    this.inputRow = wrapEl.querySelector('.search-input-row');
    this.clearBtn = this._createClearBtn();

    this._bind();
  }

  _createClearBtn() {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'search-clear hidden';
    btn.setAttribute('aria-label', 'খোঁজ মুছুন');
    btn.innerHTML = icon.x;
    btn.addEventListener('click', () => {
      this.input.value = '';
      this.input.focus();
      this._hideSuggestions();
      this._updateClearBtn();
    });
    this.inputRow.appendChild(btn);
    return btn;
  }

  _updateClearBtn() {
    this.clearBtn.classList.toggle('hidden', !this.input.value);
  }

  _bind() {
    this.input.addEventListener('input', (e) => {
      this._updateClearBtn();
      this._debounceFetch();
    });

    this.input.addEventListener('focus', () => {
      this.focused = true;
      if (this.input.value.trim().length >= 1) this._debounceFetch();
    });

    this.input.addEventListener('click', () => {
      this.focused = true;
      if (this.input.value.trim().length >= 1) this._debounceFetch();
    });

    this.input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { this._hideSuggestions(); return; }
      if (!this.dropdownEl || this.suggestions.length === 0) {
        if (e.key === 'Enter') this._submit();
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        this.activeIndex = Math.min(this.activeIndex + 1, this.suggestions.length - 1);
        this._highlightItem();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        this.activeIndex = Math.max(this.activeIndex - 1, 0);
        this._highlightItem();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const q = this.activeIndex >= 0 ? this.suggestions[this.activeIndex] : this.input.value;
        this.input.value = q;
        this._hideSuggestions();
        this._updateClearBtn();
        this._submit(q);
      }
    });

    // Hide ONLY when clicking outside the search wrapper
    document.addEventListener('mousedown', (e) => {
      if (!this.wrap.contains(e.target)) {
        this.focused = false;
        this._hideSuggestions();
      }
    });
  }


  _debounceFetch() {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      let q = this.input.value.trim();
      if (!q) {
        this._hideSuggestions();
        return;
      }
      this._fetchSuggestions(q);
    }, 150);
  }

  async _fetchSuggestions(q) {
    try {
      const baseUrl = getApiBase();
      const url = `${baseUrl}/api/v1/suggestions?q=${encodeURIComponent(q)}&limit=8`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      this.suggestions = Array.isArray(data) ? data : [];
      this.activeIndex = -1;
      if (this.suggestions.length > 0) {
        this._renderSuggestions(q);
      } else {
        this._hideSuggestions();
      }
    } catch {
      this._hideSuggestions();
    }
  }


  _renderSuggestions(query) {
    this._removeSuggestions();
    this.inputRow.classList.add('has-suggestions');

    const dropdown = document.createElement('div');
    dropdown.className = 'suggestions-list';
    dropdown.setAttribute('role', 'listbox');

    const separator = document.createElement('div');
    separator.style.height = '1px';
    separator.style.background = 'var(--surface-3)';
    separator.style.margin = '0 16px 8px 16px';
    dropdown.appendChild(separator);

    this.suggestions.forEach((s, i) => {
      const item = document.createElement('div');
      item.className = 'suggestion-item';
      item.setAttribute('role', 'option');
      item.setAttribute('data-index', String(i));

      let formattedText = esc(s);
      const qLower = query ? query.toLowerCase() : '';
      const sLower = s.toLowerCase();

      if (qLower && sLower.startsWith(qLower)) {
        const prefix = esc(s.slice(0, query.length));
        const rest = esc(s.slice(query.length));
        formattedText = `${prefix}<b>${rest}</b>`;
      } else if (qLower && sLower.includes(qLower)) {
        const idx = sLower.indexOf(qLower);
        const before = esc(s.slice(0, idx));
        const match = esc(s.slice(idx, idx + query.length));
        const after = esc(s.slice(idx + query.length));
        formattedText = `${before}<b>${match}</b>${after}`;
      }

      item.innerHTML = `
        <span class="suggestion-icon">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        </span>
        <span class="suggestion-text">${formattedText}</span>
      `;

      item.addEventListener('mousedown', (e) => {
        e.preventDefault();
        this.input.value = s;
        this._updateClearBtn();
        this._hideSuggestions();
        this._submit(s);
      });

      dropdown.appendChild(item);
    });

    // Append to native wrapper so width/left/right align natively via CSS
    this.dropdownEl = dropdown;
    this.wrap.appendChild(dropdown);
  }


  _showExisting() {
    if (this.suggestions.length > 0 && !this.dropdownEl) this._renderSuggestions();
  }

  _highlightItem() {
    if (!this.dropdownEl) return;
    this.dropdownEl.querySelectorAll('.suggestion-item').forEach((el, i) => {
      el.classList.toggle('active', i === this.activeIndex);
    });
  }

  _hideSuggestions() {
    this.inputRow.classList.remove('has-suggestions');
    this._removeSuggestions();
  }

  _removeSuggestions() {
    if (this.dropdownEl) {
      this.dropdownEl.remove();
      this.dropdownEl = null;
    }
  }

  _submit(q) {
    this._hideSuggestions();
    let val = (q || this.input.value).trim();
    if (!val) return;
    
    if (this.onSearch) {
      this.onSearch(val);
    } else {
      window.location.href = `/search.html?q=${encodeURIComponent(val)}`;
    }
  }

  setValue(v) {
    this.input.value = v;
    this._updateClearBtn();
  }
}

/* ── 4. KNOWLEDGE GRAPH RENDERER ────────────────────────── */
// Ported from src/components/search/KnowledgeGraphCard.tsx
const KG_COLOURS = ['#006a4e', '#0f766e', '#2563eb'];

function sourceColour(index) {
  return KG_COLOURS[index % KG_COLOURS.length];
}

/**
/**
 * drawKnowledgeGraph(kg, containerEl)
 * Renders an interactive SVG relationship graph linking the central entity
 * to its verified related entities. (Fixes D8)
 */
function drawKnowledgeGraph(kg, containerEl) {
  if (!containerEl || !kg) return;
  const related = (kg.related_entities || []).slice(0, 4);
  if (related.length === 0) {
    containerEl.innerHTML = '';
    return;
  }

  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('viewBox', '0 0 288 170');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', `জ্ঞানকোষ সম্পর্ক: ${kg.title}`);

  // Background defs
  const defs = document.createElementNS(svgNS, 'defs');
  const grad = document.createElementNS(svgNS, 'linearGradient');
  grad.setAttribute('id', 'khujoEntityGraphSurface');
  grad.setAttribute('x1', '0'); grad.setAttribute('x2', '1');
  grad.setAttribute('y1', '0'); grad.setAttribute('y2', '1');
  const stop1 = document.createElementNS(svgNS, 'stop');
  stop1.setAttribute('offset', '0%'); stop1.setAttribute('stop-color', '#ecfdf5');
  const stop2 = document.createElementNS(svgNS, 'stop');
  stop2.setAttribute('offset', '100%'); stop2.setAttribute('stop-color', '#f0fdf4');
  grad.appendChild(stop1); grad.appendChild(stop2);
  defs.appendChild(grad);
  svg.appendChild(defs);

  const rect = document.createElementNS(svgNS, 'rect');
  rect.setAttribute('x', '1'); rect.setAttribute('y', '1');
  rect.setAttribute('width', '286'); rect.setAttribute('height', '168');
  rect.setAttribute('rx', '12');
  rect.setAttribute('fill', 'url(#khujoEntityGraphSurface)');
  rect.setAttribute('stroke', '#d1fae5');
  svg.appendChild(rect);

  const cx = 72, cy = 85;

  // Spoke Entity nodes
  related.forEach((rel, index) => {
    const total = related.length;
    const y = 28 + index * (114 / Math.max(1, total - 1));
    const nx = 195, ny = y;

    // Connecting curve
    const path = document.createElementNS(svgNS, 'path');
    path.setAttribute('d', `M${cx} ${cy} C ${cx + 50} ${cy}, ${nx - 40} ${ny}, ${nx} ${ny}`);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', '#10b981');
    path.setAttribute('stroke-width', '1.5');
    path.setAttribute('stroke-dasharray', '3 2');
    path.setAttribute('opacity', '0.65');
    svg.appendChild(path);

    // Clickable spoke group
    const g = document.createElementNS(svgNS, 'g');
    g.style.cursor = 'pointer';
    g.addEventListener('click', () => {
      window.location.href = `/search.html?q=${encodeURIComponent(rel.title)}`;
    });

    const circle = document.createElementNS(svgNS, 'circle');
    circle.setAttribute('cx', String(nx)); circle.setAttribute('cy', String(ny));
    circle.setAttribute('r', '13');
    circle.setAttribute('fill', '#059669');
    g.appendChild(circle);

    const numText = document.createElementNS(svgNS, 'text');
    numText.setAttribute('x', String(nx)); numText.setAttribute('y', String(ny + 4));
    numText.setAttribute('fill', 'white');
    numText.setAttribute('font-size', '10');
    numText.setAttribute('font-weight', 'bold');
    numText.setAttribute('text-anchor', 'middle');
    numText.textContent = String(index + 1);
    g.appendChild(numText);

    const labelText = document.createElementNS(svgNS, 'text');
    labelText.setAttribute('x', String(nx + 16)); labelText.setAttribute('y', String(ny + 4));
    labelText.setAttribute('fill', '#0f172a');
    labelText.setAttribute('font-size', '11');
    labelText.setAttribute('font-weight', '500');
    labelText.textContent = (rel.title || '').slice(0, 10);
    g.appendChild(labelText);

    svg.appendChild(g);
  });

  // Central root entity node
  const rootG = document.createElementNS(svgNS, 'g');
  const outer = document.createElementNS(svgNS, 'circle');
  outer.setAttribute('cx', String(cx)); outer.setAttribute('cy', String(cy));
  outer.setAttribute('r', '28');
  outer.setAttribute('fill', '#006a4e');
  rootG.appendChild(outer);

  const innerRing = document.createElementNS(svgNS, 'circle');
  innerRing.setAttribute('cx', String(cx)); innerRing.setAttribute('cy', String(cy));
  innerRing.setAttribute('r', '22');
  innerRing.setAttribute('fill', 'none');
  innerRing.setAttribute('stroke', '#a7f3d0');
  innerRing.setAttribute('stroke-width', '1.5');
  rootG.appendChild(innerRing);

  const centerLabel = document.createElementNS(svgNS, 'text');
  centerLabel.setAttribute('x', String(cx)); centerLabel.setAttribute('y', String(cy + 4));
  centerLabel.setAttribute('fill', 'white');
  centerLabel.setAttribute('font-size', '11');
  centerLabel.setAttribute('font-weight', '600');
  centerLabel.setAttribute('text-anchor', 'middle');
  centerLabel.textContent = (kg.title || 'সত্তা').slice(0, 8);
  rootG.appendChild(centerLabel);

  svg.appendChild(rootG);

  containerEl.innerHTML = '';
  containerEl.appendChild(svg);
}

/* ── 5. SERP LOADER ─────────────────────────────────────── */

// Session history: stored per browser session (cleared on tab close)
const SESSION_KEY = 'khujo_session';
function getSession() {
  try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || '[]'); } catch { return []; }
}
function pushSession(query) {
  const ts = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const history = getSession().filter((h) => h.query !== query);
  history.unshift({ query, ts });
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(history.slice(0, 8)));
}

// Dynamic contextual perspectives per query and retrieval state (Fixes D13)
function getPerspectives(query, data) {
  const bn = /[\u0980-\u09FF]/.test(query);
  const kg = data?.knowledge_graph;
  const results = data?.results || [];
  const perspectives = [];

  if (kg && kg.title) {
    perspectives.push({
      label: bn ? `সত্তা সন্ধান: ${kg.title}` : `Entity focus: ${kg.title}`,
      tone: 'Verified Entity',
      text: bn 
        ? `"${kg.title}" একটি যাচাইকৃত বিষয়। এর সাথে সম্পর্কিত তথ্য ও অফিশিয়াল সূত্রগুলো পাশের জ্ঞানকোষ প্যানেলে দেখুন।`
        : `"${kg.title}" is a verified knowledge entity. Check key facts and official sources in the sidebar.`
    });
  }

  const hasGov = results.some(r => (r.url || '').includes('.gov.bd'));
  if (hasGov) {
    perspectives.push({
      label: bn ? 'সরকারি তথ্য' : 'Official Portal',
      tone: 'Government',
      text: bn
        ? 'এই অনুসন্ধানের ফলাফলে সরাসরি বাংলাদেশ সরকারের প্রাতিষ্ঠানিক বা দাপ্তরিক পোর্টালের তথ্য অন্তর্ভুক্ত রয়েছে।'
        : 'Official Bangladesh government portal records were discovered for this query.'
    });
  } else {
    perspectives.push({
      label: bn ? 'স্থানীয় খোঁজ' : 'Local Context',
      tone: 'Local Angle',
      text: bn
        ? 'জেলা বা বিভাগের নাম যুক্ত করলে (যেমন "ঢাকায়", "সিলেটের") নির্দিষ্ট এলাকাভিত্তিক স্থানীয় ফলাফল পাবেন।'
        : 'Add a district or division name for targeted regional results.'
    });
  }

  perspectives.push({
    label: bn ? 'উৎস ও বিশ্বাসযোগ্যতা' : 'Source Trust',
    tone: 'Trust',
    text: bn
      ? 'খোঁজো রেজাল্টের ডোমেইন আইকন ও সোর্স দেখে নির্ভরযোগ্য ও যাচাইকৃত তথ্য বেছে নিন।'
      : 'Review source domain icons on each result card to verify authoritative publisher provenance.'
  });

  return perspectives;
}

async function loadSERP() {
  const params = new URLSearchParams(window.location.search);
  const query = params.get('q') || '';
  const tab = params.get('tab') || 'all';

  // Handle Tab UI
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
    const bTab = btn.getAttribute('data-tab') || 'all';
    if (bTab === tab) btn.classList.add('active');

    // Remove old listeners and add new one to avoid duplicates if loadSERP called multiple times
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    newBtn.addEventListener('click', (e) => {
      if (newBtn.classList.contains('coming-soon')) return;
      const t = newBtn.getAttribute('data-tab') || 'all';
      window.location.href = `/search.html?q=${encodeURIComponent(query)}${t !== 'all' ? '&tab='+t : ''}`;
    });
  });

  // Sync search input
  const serpInput = document.getElementById('serpSearchInput');
  if (serpInput) serpInput.value = query;

  const resultMeta        = document.getElementById('resultMeta');
  const resultsList       = document.getElementById('resultsList');
  const kgCard            = document.getElementById('kgCard');
  const kgGraphArea       = document.getElementById('kgGraphArea');
  const sourcesCard       = document.getElementById('sourcesCard');
  const sourcesList       = document.getElementById('sourcesList');
  const perspectivesCard  = document.getElementById('perspectivesCard');
  const perspectivesList  = document.getElementById('perspectivesList');
  const sessionCard       = document.getElementById('sessionCard');
  const sessionList       = document.getElementById('sessionList');

  // Update page title
  if (query) document.title = `${query} — খোঁজো`;

  if (!query || !resultsList) return;

  // Push to session history immediately
  pushSession(query);
  renderSessionCard(sessionCard, sessionList, query);

  // Show skeleton
  resultsList.innerHTML = renderSkeleton();
  if (resultMeta) resultMeta.innerHTML = 'খুঁজছে...';
  if (kgCard) kgCard.classList.add('hidden');
  if (sourcesCard) sourcesCard.classList.add('hidden');
  if (perspectivesCard) perspectivesCard.classList.add('hidden');

  try {
    if (tab === 'images') {
      const res = await fetch(`${API_BASE}/api/v1/search/images?q=${encodeURIComponent(query)}&limit=20`);
      if (!res.ok) throw new Error('Image Search failed');
      const data = await res.json();
      
      if (resultMeta) {
        resultMeta.innerHTML = data.results.length > 0
          ? `${data.results.length}টি ছবি পাওয়া গেছে <strong>"${esc(query)}"</strong>`
          : '';
      }

      if (data.results.length === 0) {
        resultsList.innerHTML = renderEmpty();
        return;
      }

      const gridHtml = `
        <div class="image-grid">
          ${data.results.map(r => {
            let domain = '';
            try { domain = new URL(r.source_url).hostname.replace(/^www\./, ''); } catch(e){}
            return `
            <a href="${esc(r.source_url)}" target="_blank" rel="noopener noreferrer" class="image-result-card">
              <div class="image-result-img-wrapper">
                <img src="${esc(r.thumbnail_url)}" alt="${esc(r.title)}" class="image-result-img" loading="lazy">
              </div>
              <div class="image-result-info">
                <div class="image-result-title">${esc(r.title)}</div>
                <div class="image-result-domain">${esc(domain)}</div>
              </div>
            </a>
            `;
          }).join('')}
        </div>
      `;
      resultsList.innerHTML = gridHtml;
      return;
    }

    const res = await fetch(
      `${API_BASE}/api/v1/search?q=${encodeURIComponent(query)}&limit=10&offset=0`
    );
    if (!res.ok) throw new Error('Search failed');
    const data = await res.json();

    // Filter crawl_queue type
    const results = (data.results || []).filter((r) => r.type !== 'crawl_queue');

    // Result meta & correction notice
    if (resultMeta) {
      if (data.correction && data.correction.target_name) {
        const orig = esc(data.correction.original_query);
        const target = esc(data.correction.target_name);
        resultMeta.innerHTML = `<div class="kg-did-you-mean" style="font-size:15px;margin-bottom:8px;">আপনি কি বুঝাতে চেয়েছেন: <a href="/search.html?q=${encodeURIComponent(target)}" style="color:var(--primary-color);font-weight:600;text-decoration:underline;">${target}</a></div>`;
      } else {
        resultMeta.innerHTML = results.length > 0
          ? `<strong>"${esc(query)}"</strong> এর জন্য ফলাফল`
          : '';
      }
    }

    // ── Build Inline Knowledge Graph (Google Style)
    let inlineKgHtml = '';
    const kg = data.knowledge_graph;
    if (kg) {
      let factsHtml = '';
      if (kg.facts && Object.keys(kg.facts).length > 0) {
        const skipKeys = ['UN/LOCODE', 'ওয়েবসাইট', 'পৌর এলাকা', 'প্রতিষ্ঠিত', 'স্থানাঙ্ক'];
        let validFacts = Object.entries(kg.facts).filter(([k, v]) => !skipKeys.includes(k)).slice(0, 5);
        if (validFacts.length > 0) {
          factsHtml = '<div class="kg-facts-box">';
          for (const [key, val] of validFacts) {
            factsHtml += `<div class="kg-fact-row"><span class="kg-fact-key">${esc(key)}</span><span class="kg-fact-val">${esc(val)}</span></div>`;
          }
          factsHtml += '</div>';
        }
      }
      
      let relatedHtml = '';
      if (kg.related_entities && kg.related_entities.length > 0) {
        relatedHtml = `
          <div class="kg-related-sq">
            <h4 class="kg-related-title">লোকজন এগুলিও সার্চ করেছে</h4>
            <div class="kg-related-slider-sq">
              ${kg.related_entities.map(re => `
                <a href="/?q=${encodeURIComponent(re.title)}" class="kg-related-item-sq">
                  <img src="${esc(re.image_url)}" alt="${esc(re.title)}" class="kg-related-img-sq" loading="lazy">
                  <span class="kg-related-name-sq">${esc(re.title)}</span>
                </a>
              `).join('')}
            </div>
          </div>
        `;
      }

      let imageHtml = '';
      let cardClass = 'kg-inline-card';
      const imgs = (kg.images && kg.images.length > 0) ? kg.images.slice(0, 3) : (kg.image_url ? [kg.image_url] : []);
      
      if (imgs.length === 1) {
        cardClass += ' has-single-hero';
        imageHtml = `<img src="${esc(imgs[0])}" alt="${esc(kg.title)}" class="kg-inline-hero">`;
      } else if (imgs.length > 1) {
        cardClass += ' has-multi-collage';
        const count = imgs.length;
        imageHtml = `<div class="kg-collage kg-collage-${count}">`;
        imgs.forEach((img) => {
          imageHtml += `<div class="kg-collage-img-wrap"><img src="${esc(img)}" alt="${esc(kg.title)}" class="kg-collage-img" onerror="this.closest('.kg-collage-img-wrap')?.remove();"></div>`;
        });
        imageHtml += `</div>`;
      }

      let aboutHtml = '';
      const isFallbackDesc = kg.description && kg.description.includes('সম্পর্কিত তথ্য');
      if (kg.description && kg.description.trim() !== '' && !isFallbackDesc) {
        aboutHtml = `
          <div class="kg-about-section">
            <div class="kg-inline-overview">
              <p>${esc(kg.description)}</p>
              ${kg.title ? `<a href="https://bn.wikipedia.org/wiki/${encodeURIComponent(kg.title)}" target="_blank" rel="noopener" class="kg-wiki-link">উইকিপিডিয়া</a>` : ''}
            </div>
          </div>
        `;
      } else if (kg.title) {
        // Just provide the wiki link if no proper description
        aboutHtml = `
          <div class="kg-about-section" style="padding-top:0; border:none;">
            <a href="https://bn.wikipedia.org/wiki/${encodeURIComponent(kg.title)}" target="_blank" rel="noopener" class="kg-wiki-link">উইকিপিডিয়া</a>
          </div>
        `;
      }

      inlineKgHtml = `
        <div class="${cardClass}">
          ${imageHtml}
          <div class="kg-inline-content">
            <h2 class="kg-inline-title">${esc(kg.title)}</h2>
            ${aboutHtml}
            ${factsHtml}
          </div>
          ${relatedHtml}
        </div>
      `;
    }

    if (results.length === 0) {
      resultsList.innerHTML = inlineKgHtml + renderEmpty();
      return;
    }

    // Collect unique sources for top-sources
    const sourceMap = new Map();
    results.forEach((r) => {
      if (!r.url) return;
      let label;
      try { label = new URL(r.url).hostname.replace(/^www\./, ''); } catch { label = r.source; }
      if (!sourceMap.has(label)) sourceMap.set(label, { label, url: r.url });
    });
    const sources = Array.from(sourceMap.values());

    // ── Render results
    resultsList.innerHTML = inlineKgHtml; // Prepend KG inline card
    resultsList.insertAdjacentHTML('beforeend', renderContextCard(sources.length, query));
    
    const list = document.createElement('div');
    list.className = 'result-list';
    results.forEach((r) => list.insertAdjacentHTML('beforeend', renderResultCard(r)));
    resultsList.appendChild(list);


    // ── Knowledge Card sidebar (Fixes D7 & D8)
    if (kg && kgCard) {
      const kgCardContent = document.getElementById('kgCardContent');
      if (kgCardContent) {
        let kgHtml = '';
        if (kg.image_url) {
          kgHtml += `<div style="margin-bottom:10px;"><img src="${esc(kg.image_url)}" alt="${esc(kg.title)}" style="width:100%;max-height:160px;object-fit:cover;border-radius:8px;"></div>`;
        }
        kgHtml += `<h3 style="font-size:16px;font-weight:600;margin-bottom:6px;color:var(--text-primary);">${esc(kg.title)}</h3>`;
        if (kg.description) {
          kgHtml += `<p style="font-size:13px;line-height:1.5;color:var(--text-secondary);margin-bottom:10px;">${esc(kg.description.slice(0, 180))}${kg.description.length > 180 ? '...' : ''}</p>`;
        }
        if (kg.title) {
          kgHtml += `<div style="margin-bottom:8px;"><a href="https://bn.wikipedia.org/wiki/${encodeURIComponent(kg.title)}" target="_blank" rel="noopener noreferrer" style="font-size:12px;color:var(--primary);font-weight:500;">উইকিপিডিয়া নিবন্ধ ↗</a></div>`;
        }
        kgCardContent.innerHTML = kgHtml;
      }
      if (kgGraphArea) {
        drawKnowledgeGraph(kg, kgGraphArea);
      }
      kgCard.classList.remove('hidden');
    }

    // ── Top sources sidebar
    if (sources.length > 0 && sourcesCard && sourcesList) {
      sourcesCard.classList.remove('hidden');
      sourcesList.innerHTML = '';
      sources.slice(0, 5).forEach((s) => {
        const a = document.createElement('a');
        a.href = s.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
        a.className = 'source-item';
        a.innerHTML = `<span class="truncate">${esc(s.label)}</span>${icon.externalLink}`;
        sourcesList.appendChild(a);
      });
    }

    // ── Perspectives sidebar (Fixes D13)
    if (perspectivesCard && perspectivesList) {
      const persp = getPerspectives(query, data);
      perspectivesList.innerHTML = persp.map((p) => `
        <div class="perspective-item">
          <div class="perspective-header">
            <span class="perspective-label">${esc(p.label)}</span>
            <span class="perspective-tone">${esc(p.tone)}</span>
          </div>
          <p class="perspective-text">${esc(p.text)}</p>
        </div>`).join('');
      perspectivesCard.classList.remove('hidden');
    }

  } catch {
    if (resultsList) {
      resultsList.innerHTML = renderError(query);
      document.getElementById('retryBtn')?.addEventListener('click', loadSERP);
    }
  }
}

function renderSessionCard(card, list, currentQuery) {
  if (!card || !list) return;
  const history = getSession();
  if (history.length === 0) return;
  list.innerHTML = '';
  history.forEach((h) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'session-item';
    btn.innerHTML = `<span class="session-query">${esc(h.query)}</span><span class="session-time">${esc(h.ts)}</span>`;
    btn.addEventListener('click', () => {
      window.location.href = `/search.html?q=${encodeURIComponent(h.query)}`;
    });
    list.appendChild(btn);
  });
  card.classList.remove('hidden');
}

/* ── 6. RENDER HELPERS ──────────────────────────────────── */
function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function sourceLabel(url, fallback) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return fallback || url; }
}

function renderSkeleton() {
  return `<div class="skeleton">${[1,2,3].map(() => `
    <div class="skeleton-card">
      <div class="skel-line short"></div>
      <div class="skel-line medium"></div>
      <div class="skel-line long"></div>
      <div class="skel-line full"></div>
      <div class="skel-line" style="width:40%"></div>
    </div>`).join('')}</div>`;
}

function renderContextCard(sourceCount, query) {
  return `<section class="context-card">
    <div class="context-icon">${icon.sparkles}</div>
    <div>
      <p class="context-label">Khujo context</p>
      <p class="context-body">
        এই অনুসন্ধানে ${sourceCount}টি আলাদা উৎস পাওয়া গেছে।
        খোঁজো উৎসের ঠিকানা দেখায়, যাতে আপনি নিজে তথ্য যাচাই করতে পারেন।
      </p>
    </div>
  </section>`;
}

function renderResultCard(r) {
  const domain = sourceLabel(r.url, r.source);
  const faviconHtml = r.favicon
    ? `<img class="result-favicon" src="${esc(r.favicon)}" alt="" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='grid';"><span class="result-favicon-fallback" style="display:none">${icon.fileText}</span>`
    : `<span class="result-favicon-fallback">${icon.fileText}</span>`;

  const pathPart = (() => {
    try {
      const u = new URL(r.url);
      let p = u.pathname.slice(1);
      try { p = decodeURIComponent(p); } catch {}
      return p ? `<span class="result-domain-sep">/</span><span class="result-path">${esc(p)}</span>` : '';
    } catch { return ''; }
  })();


  const timestampHtml = r.timestamp
    ? `<span class="result-timestamp">${esc(r.timestamp)}</span>`
    : '';

  return `<article class="result-card">
    <div class="result-breadcrumb">
      ${faviconHtml}
      <span class="result-domain">${esc(domain)}</span>
      ${pathPart}
    </div>
    <a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" class="result-title">
      <span>${esc(r.title)}</span>
      ${icon.arrowUpRight}
    </a>
    <p class="result-snippet">${esc(r.snippet)}</p>
    <div class="result-footer">
      <span class="result-source-badge">${esc(r.source)}</span>
      ${timestampHtml}
    </div>
  </article>`;
}

function renderEmpty() {
  return `<div class="empty-box">
    <div class="empty-icon">${icon.searchX}</div>
    <h1 class="empty-title">এখনও কোনো ফলাফল নেই</h1>
    <p class="empty-body">ভিন্ন বানান, Banglish বা আরও নির্দিষ্ট স্থান ব্যবহার করে আবার খুঁজুন।</p>
  </div>`;
}

function renderError(query) {
  return `<div class="error-box">
    <div style="flex-shrink:0;width:20px;height:20px;margin-top:1px;">${icon.alertTriangle}</div>
    <div>
      <p>খোঁজো সার্ভারের সাথে এখন সংযোগ করা যাচ্ছে না।</p>
      <button id="retryBtn" class="error-retry">আবার চেষ্টা করুন</button>
    </div>
  </div>`;
}

/* ── 7. TRENDING CHIPS ──────────────────────────────────── */
function initTrendingChips() {
  document.querySelectorAll('[data-query]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const q = btn.getAttribute('data-query');
      if (q) window.location.href = `/search.html?q=${encodeURIComponent(q)}`;
    });
  });
}

/* ── 8. INIT ────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // ── Landing page search bar
  const landingInput = document.getElementById('landingSearchInput');
  const landingWrap = document.getElementById('landingSearchWrap');
  if (landingInput && landingWrap) {
    const bar = new SearchBar(landingInput, landingWrap);
    const form = document.getElementById('landingForm');
    form?.addEventListener('submit', (e) => {
      e.preventDefault();
      bar._submit();
    });
  }

  // ── SERP search bar
  const serpInput = document.getElementById('serpSearchInput');
  const serpWrap = document.getElementById('serpSearchWrap');
  if (serpInput && serpWrap) {
    new SearchBar(serpInput, serpWrap, {
      onSearch: (q) => {
        window.location.href = `/search.html?q=${encodeURIComponent(q)}`;
      },
    });
    const serpForm = document.getElementById('serpForm');
    serpForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      window.location.href = `/search.html?q=${encodeURIComponent(serpInput.value.trim())}`;
    });
  }

  // ── Trending chips
  initTrendingChips();

  // ── SERP data load
  if (document.getElementById('resultsList')) {
    loadSERP();
  }
});
