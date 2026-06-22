// ── State ──────────────────────────────────────────────────────────────────
const S = {
  positions: [],
  summary: {},
  dividendEvents: [],
  upcoming: [],
  received: [],
  settings: { cash_balance: 0 },
  projections: null,
  charts: {},
  sort: { col: "name", dir: 1 },
  filter: "",
  profiles: [],
};

// ── Utilities ──────────────────────────────────────────────────────────────
const fmt = {
  gbp: (v) => v == null ? '—' : '£' + Number(v).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  pct: (v) => v == null ? '—' : (v >= 0 ? '+' : '') + Number(v).toFixed(2) + '%',
  num: (v, dp = 4) => v == null ? '—' : Number(v).toLocaleString('en-GB', { minimumFractionDigits: 0, maximumFractionDigits: dp }),
  pnlClass: (v) => v > 0 ? 'pnl-pos' : v < 0 ? 'pnl-neg' : 'pnl-zero',
  datetime: (s) => {
    if (!s) return '—';
    try {
      const d = new Date(s);
      return d.toLocaleDateString('en-GB') + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    } catch { return s; }
  },
  native: (price, currency) => {
    if (price == null || !currency) return '—';
    const sym = { GBP: '£', USD: '$', EUR: '€', CHF: 'CHF ', JPY: '¥', CAD: 'C$', AUD: 'A$' };
    if (currency === 'GBp') return price.toFixed(2) + 'p';
    return (sym[currency] || currency + ' ') + price.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  },
};

function notify(msg, type = 'success') {
  const el = document.createElement('div');
  el.className = `notif ${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function setRefreshing(v) {
  const btn = document.getElementById('refreshBtn');
  if (v) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Refreshing…';
  } else {
    btn.disabled = false;
    btn.innerHTML = '⟳ Refresh Prices';
  }
}

// ── Navigation ─────────────────────────────────────────────────────────────
function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`page-${page}`).classList.add('active');
  document.querySelector(`.nav-item[data-page="${page}"]`).classList.add('active');
  try {
    if (page === 'dashboard') renderDashboard();
    if (page === 'portfolio') renderPortfolio();
    if (page === 'income') renderIncome();
    if (page === 'projections') renderProjections();
  } catch (e) {
    console.error('render error on page', page, e);
  }
}

// ── Data loading ───────────────────────────────────────────────────────────
async function loadAll() {
  try {
    [S.positions, S.summary, S.dividendEvents, S.upcoming, S.received, S.settings, S.profiles] = await Promise.all([
      API.getPositions(),
      API.getSummary(),
      API.getDividendEvents(),
      API.getUpcomingDividends(),
      API.getReceivedDividends(),
      API.getSettings().catch(() => ({ cash_balance: 0 })),
      API.getProfiles().catch(() => ([{id: 'default', name: 'Default'}])),
    ]);
    renderProfilesUI();
    document.getElementById('setting-ollama-url').value = S.settings.ollama_url || 'http://localhost:11434';
    const savedModel = S.settings.ollama_model || 'llama3';
    const select = document.getElementById('setting-ollama-model');
    select.innerHTML = `<option value="${savedModel}">${savedModel}</option>`;
    select.value = savedModel;
  } catch (e) {
    notify('Failed to load data: ' + e.message, 'error');
  }
}

// ── Dashboard ──────────────────────────────────────────────────────────────
function renderDashboard() {
  const s = S.summary;

  document.getElementById('card-total-value').textContent = fmt.gbp(s.total_current_value);
  document.getElementById('card-book-cost').textContent = 'Book cost ' + fmt.gbp(s.total_book_cost);

  const cg = s.capital_growth ?? 0;
  document.getElementById('card-pnl').textContent = (cg >= 0 ? '+' : '') + fmt.gbp(cg);
  document.getElementById('card-pnl').className = 'card-value ' + fmt.pnlClass(cg);
  document.getElementById('card-pnl-pct').textContent = fmt.pct(s.capital_growth_pct) + ' vs book cost';

  document.getElementById('card-income-ttm').textContent = fmt.gbp(s.income_ttm);
  document.getElementById('card-proj-income').textContent = 'projected ' + fmt.gbp(s.projected_annual_income) + '/yr';
  document.getElementById('card-holdings').textContent = s.positions_count ?? 0;

  // Capital growth split card
  document.getElementById('growth-value').textContent = fmt.gbp(s.total_current_value);
  document.getElementById('growth-book').textContent = fmt.gbp(s.total_book_cost);
  const gpnlEl = document.getElementById('growth-pnl');
  gpnlEl.textContent = (cg >= 0 ? '+' : '') + fmt.gbp(cg);
  gpnlEl.className = 'split-row-val ' + fmt.pnlClass(cg);
  const gpctEl = document.getElementById('growth-pct');
  gpctEl.textContent = fmt.pct(s.capital_growth_pct);
  gpctEl.className = 'split-row-val ' + fmt.pnlClass(cg);

  // Income split card
  document.getElementById('income-ttm').textContent = fmt.gbp(s.income_ttm);
  document.getElementById('income-proj').textContent = fmt.gbp(s.projected_annual_income);
  const bk = s.total_book_cost || 1;
  const mv = s.total_current_value || 1;
  const inc = s.annual_dividend_income_est || 0;
  document.getElementById('income-yield').textContent = inc ? ((inc / bk * 100).toFixed(2) + '%') : '—';
  document.getElementById('income-yield-mkt').textContent = inc ? ((inc / mv * 100).toFixed(2) + '%') : '—';

  // Overview card (cash + total)
  const cash = S.settings?.cash_balance ?? 0;
  const invested = s.total_current_value ?? 0;
  document.getElementById('overview-invested').textContent = fmt.gbp(invested);
  document.getElementById('overview-cash').textContent = fmt.gbp(cash);
  document.getElementById('overview-cg').textContent = (cg >= 0 ? '+' : '') + fmt.gbp(cg);
  document.getElementById('overview-cg').className = 'split-row-val ' + fmt.pnlClass(cg);
  document.getElementById('overview-total').textContent = fmt.gbp(invested + cash);
  document.getElementById('cash-input').value = cash.toFixed(2);
  
  const cagr = s.historical_cagr;
  const cagrStr = cagr != null ? (cagr >= 0 ? '+' : '') + (cagr * 100).toFixed(2) + '%' : '—';
  document.getElementById('overview-cagr').textContent = cagrStr;
  document.getElementById('overview-cagr').className = 'split-row-val ' + fmt.pnlClass(cagr);

  renderAllocationChart(s.by_asset_type || {});
  renderReturnChart(s);
}

function renderAllocationChart(byType) {
  const labels = Object.keys(byType);
  const values = labels.map(k => byType[k].value || byType[k].book_cost || 0);
  const colors = ['#388bfd', '#d29922', '#3fb950', '#a371f7', '#ff7b72'];
  const ctx = document.getElementById('allocChart').getContext('2d');
  if (S.charts.alloc) S.charts.alloc.destroy();
  S.charts.alloc = new Chart(ctx, {
    type: 'doughnut',
    data: { labels: labels.map(l => l.replace(/_/g, ' ')), datasets: [{ data: values, backgroundColor: colors, borderWidth: 2, borderColor: '#161b22' }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: '#8b949e', font: { size: 11 } } } } },
  });
}

function renderReturnChart(s) {
  const cg = Math.max(0, s.capital_growth || 0);
  const inc = s.income_ttm || 0;
  const ctx = document.getElementById('returnChart').getContext('2d');
  if (S.charts.ret) S.charts.ret.destroy();
  S.charts.ret = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Total Return Components'],
      datasets: [
        { label: 'Capital Growth', data: [cg], backgroundColor: '#388bfd99', borderColor: '#388bfd', borderWidth: 1 },
        { label: 'Dividend Income (12m)', data: [inc], backgroundColor: '#3fb95099', borderColor: '#3fb950', borderWidth: 1 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#8b949e', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
        y: { ticks: { color: '#8b949e', callback: v => '£' + v.toLocaleString() }, grid: { color: '#21262d' } },
      },
    },
  });
}

// ── Portfolio table ─────────────────────────────────────────────────────────
function getSortedFiltered() {
  let rows = [...S.positions];
  const showClosed = document.getElementById('toggle-closed-positions').checked;
  if (!showClosed) {
    rows = rows.filter(p => p.status !== 'closed');
  }
  const f = S.filter.toLowerCase();
  if (f) {
    rows = rows.filter(p =>
      (p.name || '').toLowerCase().includes(f) ||
      (p.isin || '').toLowerCase().includes(f) ||
      (p.ticker || '').toLowerCase().includes(f) ||
      (p.asset_type || '').toLowerCase().includes(f)
    );
  }
  const { col, dir } = S.sort;
  rows.sort((a, b) => {
    let av = a[col], bv = b[col];
    if (typeof av === 'string') av = av.toLowerCase();
    if (typeof bv === 'string') bv = bv.toLowerCase();
    if (av == null) return 1;
    if (bv == null) return -1;
    return av < bv ? -dir : av > bv ? dir : 0;
  });
  return rows;
}

function setSort(col) {
  if (S.sort.col === col) {
    S.sort.dir *= -1;
  } else {
    S.sort.col = col;
    S.sort.dir = 1;
  }
  document.querySelectorAll('.sort-icon').forEach(el => el.textContent = '↕');
  const th = document.querySelector(`th[data-col="${col}"] .sort-icon`);
  if (th) th.textContent = S.sort.dir === 1 ? '↑' : '↓';
  renderPortfolio();
}

function renderPortfolio() {
  const tbody = document.getElementById('portfolio-tbody');
  const rows = getSortedFiltered();

  if (!rows.length && !S.positions.length) {
    tbody.innerHTML = `<tr><td colspan="15"><div class="empty"><p>No positions yet.</p><button class="btn btn-primary" onclick="openAddModal()">+ Add Position</button></div></td></tr>`;
    return;
  }
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="15" style="text-align:center;color:var(--muted);padding:24px">No positions match your filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(p => {
    const isClosed = p.status === 'closed';
    const pnl = isClosed ? p.realised_pnl : p.unrealised_pnl;
    const pnlPct = isClosed ? p.realised_pnl_pct : p.unrealised_pnl_pct;
    const pnlClass = fmt.pnlClass(pnl);
    const pnlStr = pnl != null ? (pnl >= 0 ? '+' : '') + fmt.gbp(pnl) : '—';
    const pnlPctStr = pnlPct != null ? (pnlPct >= 0 ? '+' : '') + pnlPct.toFixed(2) + '%' : '—';
    
    const cagr = p.cagr;
    const cagrClass = fmt.pnlClass(cagr);
    const cagrStr = cagr != null ? (cagr >= 0 ? '+' : '') + (cagr * 100).toFixed(2) + '%' : '—';
    
    const nativeCcy = p.native_currency;
    const showFx = nativeCcy && nativeCcy !== 'GBP';
    return `<tr style="opacity: ${isClosed ? '0.6' : '1'}">
      <td>
        <strong>${esc(p.name)}</strong>${isClosed ? ' <span class="badge badge-bond">CLOSED</span>' : ''}<br>
        <span style="color:var(--muted);font-size:11px">${esc(p.isin || '')}${p.ticker ? ' · ' + esc(p.ticker) : ''}</span>
      </td>
      <td><span class="badge badge-${p.asset_type}">${p.asset_type.replace(/_/g,' ')}</span></td>
      <td style="font-size:12px;color:var(--muted)">${p.purchase_date || '—'}</td>
      <td>${fmt.num(p.units, 6)}</td>
      <td>${fmt.gbp(p.book_cost_per_unit)}</td>
      <td>${fmt.gbp(p.total_book_cost)}</td>
      <td style="font-size:12px">
        ${p.native_price != null ? fmt.native(p.native_price, p.native_currency) : '<span style="color:var(--muted)">—</span>'}
      </td>
      <td>${p.last_price != null ? fmt.gbp(p.last_price) : '<span style="color:var(--muted)">—</span>'}</td>
      <td>${p.current_value != null ? fmt.gbp(p.current_value) : '<span style="color:var(--muted)">—</span>'}</td>
      <td class="${isClosed ? '' : pnlClass}">${isClosed ? '—' : pnlStr}</td>
      <td class="${isClosed ? pnlClass : ''}">${isClosed ? pnlStr : '—'}</td>
      <td class="${isClosed ? pnlClass : pnlClass}">${pnlPctStr}</td>
      <td class="${cagrClass}"><strong>${cagrStr}</strong></td>
      <td style="color:var(--pos);font-weight:600">${p.annual_yield != null ? (p.annual_yield * 100).toFixed(2) + '%' : '<span style="color:var(--muted)">—</span>'}</td>
      <td style="font-size:11px;color:var(--muted)">
        ${showFx && p.last_fx_rate ? p.last_fx_rate.toFixed(4) + '<br>' + esc(nativeCcy) + '→GBP' : '—'}
      </td>
      <td style="font-size:11px;white-space:normal;min-width:90px" class="${_priceAgeClass(p.last_price_at)}">${fmt.datetime(p.last_price_at)}</td>
      <td style="font-size:11px;color:var(--muted)">${esc(p.last_price_source || '—')}</td>
      <td>
        <div style="display:flex;gap:4px">
          <button class="btn btn-sm btn-icon" title="Refresh price" onclick="refreshOne(${p.id})">⟳</button>
          <button class="btn btn-sm btn-icon" title="Set manual price" onclick="openPriceModal(${p.id})">✎₤</button>
          <button class="btn btn-sm btn-icon" title="Fetch dividends" onclick="fetchDivs(${p.id})">₤</button>
          <button class="btn btn-sm btn-icon" title="Edit" onclick="openEditModal(${p.id})">✎</button>
          <button class="btn btn-sm btn-icon btn-danger" title="Delete" onclick="deletePos(${p.id})">✕</button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

async function refreshOne(id) {
  try {
    const r = await API.refreshOne(id);
    if (r.status === 'ok') {
      const native = fmt.native(r.native_price, r.native_currency);
      notify(`${r.name}: ${native} → ${fmt.gbp(r.gbp_price)}`);
      await reload();
    } else {
      notify(`Could not find price for position #${id}`, 'error');
    }
  } catch (e) { notify(e.message, 'error'); }
}

async function fetchDivs(id) {
  try {
    const r = await API.fetchDividends(id);
    const yieldStr = r.annual_yield != null ? ` · yield ${(r.annual_yield * 100).toFixed(2)}%` : '';
    notify(`Fetched ${r.inserted} dividend event(s)${yieldStr}`);
    [S.positions, S.dividendEvents, S.upcoming] = await Promise.all([
      API.getPositions(), API.getDividendEvents(), API.getUpcomingDividends(),
    ]);
    renderPortfolio();
  } catch (e) { notify(e.message, 'error'); }
}

async function deletePos(id) {
  const pos = S.positions.find(p => p.id === id);
  if (!confirm(`Delete "${pos?.name}"? This cannot be undone.`)) return;
  try {
    await API.deletePosition(id);
    notify('Position deleted');
    await reload();
  } catch (e) { notify(e.message, 'error'); }
}

// ── Manual Price Modal ──────────────────────────────────────────────────────
let _pricingId = null;

function openPriceModal(id) {
  _pricingId = id;
  const pos = S.positions.find(p => p.id === id);
  document.getElementById('price-modal-title').textContent = `Set Price — ${pos?.name || ''}`;
  document.getElementById('manual-price').value = pos?.native_price ?? pos?.last_price ?? '';
  document.getElementById('manual-currency').value = pos?.native_currency || 'GBP';
  document.getElementById('price-modal').classList.add('open');
}

function closePriceModal() {
  document.getElementById('price-modal').classList.remove('open');
}

async function saveManualPrice() {
  const price = parseFloat(document.getElementById('manual-price').value);
  const currency = document.getElementById('manual-currency').value;
  if (!price || isNaN(price)) { notify('Enter a valid price', 'error'); return; }
  try {
    const r = await API.setManualPrice(_pricingId, price, currency);
    notify(`Price set: ${fmt.native(r.native_price, r.native_currency)} → ${fmt.gbp(r.gbp_price)}`);
    closePriceModal();
    await reload();
  } catch (e) { notify(e.message, 'error'); }
}

// ── Cash balance & Settings ───────────────────────────────────────────────────
async function saveCash() {
  const val = parseFloat(document.getElementById('cash-input').value);
  if (isNaN(val) || val < 0) { notify('Enter a valid cash amount', 'error'); return; }
  try {
    const cash = val;
    const ollama_url = S.settings.ollama_url || 'http://localhost:11434';
    const ollama_model = S.settings.ollama_model || 'llama3';
    S.settings = await API.updateSettings({ cash_balance: cash, ollama_url, ollama_model });
    notify(`Cash balance saved: ${fmt.gbp(val)}`);
    renderDashboard();
  } catch (e) { notify(e.message, 'error'); }
}
async function saveSettings() {
  const cash = parseFloat(document.getElementById('cash-input').value) || 0;
  const ollama_url = document.getElementById('setting-ollama-url').value;
  const ollama_model = document.getElementById('setting-ollama-model').value;
  try {
    S.settings = await API.updateSettings({ cash_balance: cash, ollama_url, ollama_model });
    notify('Settings saved');
    renderDashboard();
  } catch (e) { notify(e.message, 'error'); }
}

// ── AI ──────────────────────────────────────────────────────────────────────
document.getElementById('ai-generate')?.addEventListener('click', async () => {
  notify('Generating insights...');
  try {
    const res = await API.aiGenerate();
    document.getElementById('ai-output').textContent = res.text;
  } catch (e) { notify(e.message, 'error'); }
});

async function fetchOllamaModels() {
  try {
    notify('Scanning local Ollama for models...');
    const data = await API.getOllamaModels();
    if (data.status === 'ok') {
      const select = document.getElementById('setting-ollama-model');
      const currentVal = select.value;
      select.innerHTML = data.models.map(m => `<option value="${m}">${m}</option>`).join('');
      if (data.models.includes(currentVal)) {
        select.value = currentVal;
      } else if (data.models.length > 0) {
        select.value = data.models[0];
      }
      notify(`Found ${data.models.length} models`);
    } else {
      notify(data.message, 'error');
    }
  } catch (err) {
    notify('Failed to scan models: ' + err.message, 'error');
  }
}

// ── Income ─────────────────────────────────────────────────────────────────
function renderIncome() {
  loadCalendar();
  const upTbody = document.getElementById('upcoming-tbody');
  if (!S.upcoming.length) {
    upTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:24px">No upcoming events. Use the ₤ button on a holding to fetch dividend data.</td></tr>`;
  } else {
    upTbody.innerHTML = S.upcoming.map(d => `<tr>
      <td><strong>${esc(d.position_name)}</strong></td>
      <td>${fmt.datetime(d.ex_date)?.split(' ')[0] || '—'}</td>
      <td>${fmt.datetime(d.pay_date)?.split(' ')[0] || '—'}</td>
      <td>${d.amount_per_unit != null ? fmt.gbp(d.amount_per_unit) : '—'}</td>
      <td class="pnl-pos">${d.projected_total != null ? fmt.gbp(d.projected_total) : '—'}</td>
    </tr>`).join('');
  }

  const rcTbody = document.getElementById('received-tbody');
  if (!S.received.length) {
    rcTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:24px">No received dividends logged yet.</td></tr>`;
  } else {
    const total = S.received.reduce((a, d) => a + d.amount, 0);
    rcTbody.innerHTML = S.received.map(d => `<tr>
      <td><strong>${esc(d.position_name)}</strong></td>
      <td>${d.pay_date}</td>
      <td class="pnl-pos">${fmt.gbp(d.amount)}</td>
      <td>${esc(d.currency)}</td>
      <td><button class="btn btn-sm btn-danger" onclick="deleteReceived(${d.id})">✕</button></td>
    </tr>`).join('') +
    `<tr style="background:var(--surface2)"><td colspan="2"><strong>Total</strong></td><td class="pnl-pos"><strong>${fmt.gbp(total)}</strong></td><td colspan="2"></td></tr>`;
  }
}

async function loadCalendar() {
  try {
    const cal = await API.getCalendar();
    renderCalendar(cal);
  } catch (e) { notify('Calendar: ' + e.message, 'error'); }
}

function renderCalendar(cal) {
  const months = cal.months || [];
  const tbody = document.getElementById('calendar-tbody');

  if (!months.length) {
    tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--muted);padding:24px">No dividend projections available. Use ₤ or Fetch All Dividends to load data.</td></tr>`;
    if (S.charts.calendar) { S.charts.calendar.destroy(); S.charts.calendar = null; }
    return;
  }

  const rows = [];
  months.forEach((m, i) => {
    const label = new Date(m.year_month + '-01').toLocaleDateString('en-GB', { year: 'numeric', month: 'long' });
    const count = m.payments.length;
    rows.push(`<tr class="cal-month-row" data-idx="${i}" style="cursor:pointer">
      <td><span id="chev-${i}" style="font-size:10px;margin-right:6px;color:var(--muted)">▶</span><strong>${label}</strong></td>
      <td style="color:var(--muted)">${count} position${count !== 1 ? 's' : ''}</td>
      <td class="pnl-pos"><strong>${fmt.gbp(m.total)}</strong></td>
    </tr>`);

    const detailRows = [...m.payments]
      .sort((a, b) => b.projected_total - a.projected_total)
      .map(p => `<tr>
        <td style="padding-left:36px">${esc(p.position_name)}</td>
        <td style="color:var(--muted);font-size:11px">${p.frequency_label}</td>
        <td class="pnl-pos">${fmt.gbp(p.projected_total)}</td>
      </tr>`).join('');

    rows.push(`<tr id="detail-${i}" style="display:none">
      <td colspan="3" style="padding:0;border-top:none">
        <table style="width:100%;border-collapse:collapse">
          <thead><tr style="background:var(--surface2)">
            <th style="padding:6px 36px;font-size:11px;text-align:left;color:var(--muted)">Position</th>
            <th style="padding:6px 14px;font-size:11px;text-align:left;color:var(--muted)">Frequency</th>
            <th style="padding:6px 14px;font-size:11px;text-align:left;color:var(--muted)">Projected Total</th>
          </tr></thead>
          <tbody>${detailRows}</tbody>
        </table>
      </td>
    </tr>`);
  });

  const grandTotal = months.reduce((a, m) => a + m.total, 0);
  rows.push(`<tr style="background:var(--surface2)"><td colspan="2"><strong>12-Month Total</strong></td><td class="pnl-pos"><strong>${fmt.gbp(grandTotal)}</strong></td></tr>`);

  tbody.innerHTML = rows.join('');

  tbody.querySelectorAll('.cal-month-row').forEach(row => {
    row.addEventListener('click', () => {
      const idx = row.dataset.idx;
      const detail = document.getElementById(`detail-${idx}`);
      const chev = document.getElementById(`chev-${idx}`);
      const opening = detail.style.display === 'none';
      detail.style.display = opening ? 'table-row' : 'none';
      chev.textContent = opening ? '▼' : '▶';
      row.style.background = opening ? 'var(--accent-dim)' : '';
    });
  });

  const ctx = document.getElementById('calendarChart').getContext('2d');
  if (S.charts.calendar) S.charts.calendar.destroy();
  S.charts.calendar = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: months.map(m => new Date(m.year_month + '-01').toLocaleDateString('en-GB', { month: 'short', year: '2-digit' })),
      datasets: [{ label: 'Projected Income (£)', data: months.map(m => m.total), backgroundColor: '#3fb95066', borderColor: '#3fb950', borderWidth: 1 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8b949e', font: { size: 10 } }, grid: { color: '#21262d' } },
        y: { ticks: { color: '#8b949e', callback: v => '£' + v.toLocaleString() }, grid: { color: '#21262d' } },
      },
    },
  });
}

async function deleteReceived(id) {
  if (!confirm('Remove this dividend record?')) return;
  try {
    await API.deleteReceived(id);
    [S.received, S.summary] = await Promise.all([API.getReceivedDividends(), API.getSummary()]);
    S.projections = null;
    renderIncome();
    notify('Removed');
  } catch (e) { notify(e.message, 'error'); }
}

// ── Projections ────────────────────────────────────────────────────────────
async function renderProjections() {
  if (!S.projections) {
    try { S.projections = await API.getProjections(); } catch (e) { notify(e.message, 'error'); return; }
  }
  const p = S.projections;
  document.getElementById('proj-current-value').textContent = fmt.gbp(p.stats.total_value);
  document.getElementById('proj-cap-growth').textContent = (p.stats.total_value - (S.summary.total_book_cost || 0)) >= 0
    ? '+' + fmt.gbp(p.stats.total_value - (S.summary.total_book_cost || 0))
    : fmt.gbp(p.stats.total_value - (S.summary.total_book_cost || 0));
  document.getElementById('proj-annual-income').textContent = fmt.gbp(p.stats.annual_income);
  document.getElementById('proj-ttm').textContent = fmt.gbp(S.summary.income_ttm);

  renderGrowthChart(p.growth);
  renderIncomeChart(p.income);
  renderTotalReturnChart(p.total_return);
}

const PROJ_COLORS = {
  'Conservative (3%)': '#8b949e',
  'Moderate (5%)': '#388bfd',
  'Optimistic (7%)': '#a371f7',
  'Aggressive (10%)': '#3fb950',
  'Flat': '#8b949e',
  '3% Growth': '#388bfd',
  '5% Growth': '#3fb950',
};

function _chartBase() {
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: '#8b949e', font: { size: 11 } } } },
    scales: {
      x: { ticks: { color: '#8b949e', font: { size: 10 }, maxTicksLimit: 10 }, grid: { color: '#21262d' } },
      y: { ticks: { color: '#8b949e', font: { size: 10 }, callback: v => '£' + v.toLocaleString() }, grid: { color: '#21262d' } },
    },
  };
}

function renderGrowthChart(g) {
  const ctx = document.getElementById('growthChart').getContext('2d');
  if (S.charts.growth) S.charts.growth.destroy();
  S.charts.growth = new Chart(ctx, {
    type: 'line',
    data: {
      labels: g.years.map(y => `Y${y}`),
      datasets: Object.entries(g.scenarios).map(([label, vals]) => ({
        label, data: vals,
        borderColor: PROJ_COLORS[label] || '#fff',
        backgroundColor: 'transparent',
        borderWidth: 2, pointRadius: 0, tension: 0.3,
      })),
    },
    options: _chartBase(),
  });
}

function renderIncomeChart(inc) {
  const ctx = document.getElementById('incomeChart').getContext('2d');
  if (S.charts.income) S.charts.income.destroy();
  S.charts.income = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: inc.years.map(y => `Y${y}`),
      datasets: Object.entries(inc.scenarios).map(([label, vals]) => ({
        label, data: vals,
        backgroundColor: (PROJ_COLORS[label] || '#888') + '99',
        borderColor: PROJ_COLORS[label] || '#888',
        borderWidth: 1,
      })),
    },
    options: _chartBase(),
  });
}

function renderTotalReturnChart(tr) {
  const ctx = document.getElementById('totalReturnChart').getContext('2d');
  if (S.charts.totalReturn) S.charts.totalReturn.destroy();
  S.charts.totalReturn = new Chart(ctx, {
    type: 'line',
    data: {
      labels: tr.years.map(y => `Y${y}`),
      datasets: [
        { label: 'Reinvested (portfolio value)', data: tr.reinvested_portfolio_value, borderColor: '#3fb950', backgroundColor: 'rgba(63,185,80,.08)', borderWidth: 2, pointRadius: 0, tension: 0.3, fill: true },
        { label: 'Cash out (portfolio value)', data: tr.cash_portfolio_value, borderColor: '#388bfd', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0.3 },
        { label: 'Cash out (cumulative income)', data: tr.cash_cumulative_income, borderColor: '#d29922', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 0, tension: 0.3, borderDash: [4, 4] },
      ],
    },
    options: _chartBase(),
  });
}

// ── Add / Edit Modal ────────────────────────────────────────────────────────
let _editingId = null;

function toggleClosedFields() {
  const status = document.getElementById('pos-form').status.value;
  document.getElementById('closed-fields').style.display = status === 'closed' ? 'flex' : 'none';
}

function openAddModal() {
  _editingId = null;
  document.getElementById('modal-title').textContent = 'Add Position';
  const f = document.getElementById('pos-form');
  f.reset();
  f.status.value = 'open';
  toggleClosedFields();
  document.getElementById('pos-modal').classList.add('open');
}

function openEditModal(id) {
  const p = S.positions.find(x => x.id === id);
  if (!p) return;
  _editingId = id;
  document.getElementById('modal-title').textContent = 'Edit Position';
  const f = document.getElementById('pos-form');
  f.name.value = p.name;
  f.isin.value = p.isin || '';
  f.ticker.value = p.ticker || '';
  f.asset_type.value = p.asset_type;
  f.native_currency.value = p.native_currency || 'GBP';
  f.units.value = p.units;
  f.book_cost_per_unit.value = p.book_cost_per_unit;
  f.currency.value = p.currency;
  f.t212_ticker.value = p.t212_ticker || '';
  f.notes.value = p.notes || '';
  f.annual_yield.value = p.annual_yield != null ? (p.annual_yield * 100).toFixed(2) : '';
  f.purchase_date.value = p.purchase_date || '';
  f.status.value = p.status || 'open';
  f.sell_date.value = p.sell_date || '';
  f.sell_price.value = p.sell_price || '';
  toggleClosedFields();
  document.getElementById('pos-modal').classList.add('open');
}

function closeModal() {
  document.getElementById('pos-modal').classList.remove('open');
  document.getElementById('div-modal').classList.remove('open');
}

async function savePosition() {
  const f = document.getElementById('pos-form');
  const data = {
    name: f.name.value.trim(),
    isin: f.isin.value.trim() || null,
    ticker: f.ticker.value.trim() || null,
    asset_type: f.asset_type.value,
    native_currency: f.native_currency.value,
    units: parseFloat(f.units.value),
    book_cost_per_unit: parseFloat(f.book_cost_per_unit.value),
    currency: f.currency.value,
    t212_ticker: f.t212_ticker.value.trim() || null,
    notes: f.notes.value.trim() || null,
    annual_yield: f.annual_yield.value ? (parseFloat(f.annual_yield.value) / 100) : null,
    purchase_date: f.purchase_date.value || null,
    status: f.status.value,
    sell_date: f.sell_date.value || null,
    sell_price: f.sell_price.value ? parseFloat(f.sell_price.value) : null,
  };
  if (!data.name || !data.units || !data.book_cost_per_unit) {
    notify('Please fill required fields', 'error'); return;
  }
  try {
    if (_editingId) {
      await API.updatePosition(_editingId, data);
      notify('Position updated');
    } else {
      await API.createPosition(data);
      notify('Position added');
    }
    closeModal();
    await reload();
  } catch (e) { notify(e.message, 'error'); }
}

// ── Log Dividend Modal ──────────────────────────────────────────────────────
function openLogDividend() {
  const sel = document.getElementById('div-position');
  sel.innerHTML = S.positions.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
  document.getElementById('div-date').value = new Date().toISOString().split('T')[0];
  document.getElementById('div-modal').classList.add('open');
}

async function saveReceived() {
  const data = {
    position_id: parseInt(document.getElementById('div-position').value),
    pay_date: document.getElementById('div-date').value,
    amount: parseFloat(document.getElementById('div-amount').value),
    currency: document.getElementById('div-currency').value,
    notes: document.getElementById('div-notes').value.trim() || null,
  };
  if (!data.pay_date || !data.amount) { notify('Fill required fields', 'error'); return; }
  try {
    await API.logReceived(data);
    notify('Dividend logged');
    closeModal();
    [S.received, S.summary] = await Promise.all([API.getReceivedDividends(), API.getSummary()]);
    S.projections = null;
    renderIncome();
  } catch (e) { notify(e.message, 'error'); }
}

// ── T212 Import ─────────────────────────────────────────────────────────────
async function importT212() {
  if (!confirm('Import all T212 positions? Existing T212-linked positions will be skipped.')) return;
  try {
    const r = await API.importT212();
    notify(`Imported ${r.imported}, skipped ${r.skipped}`);
    await reload();
  } catch (e) { notify(e.message, 'error'); }
}

// ── Global refresh ──────────────────────────────────────────────────────────
async function refreshAll() {
  setRefreshing(true);
  try {
    const r = await API.refreshAll();
    S._lastRefreshed = Date.now();
    _updateLastRefreshedLabel();
    notify(`Refreshed ${r.refreshed}${r.failed ? `, ${r.failed} failed` : ''}`);
    await reload();
  } catch (e) {
    notify('Refresh failed: ' + e.message, 'error');
  } finally {
    setRefreshing(false);
  }
}

// ── Auto-refresh timer ──────────────────────────────────────────────────────
let _autoRefreshTimer = null;
let _countdownTimer = null;
let _nextRefreshAt = null;

function _updateLastRefreshedLabel() {
  if (!S._lastRefreshed) return;
  const age = Math.floor((Date.now() - S._lastRefreshed) / 1000);
  const m = Math.floor(age / 60);
  const s = age % 60;
  let label = m > 0 ? `Updated ${m}m ${s}s ago` : `Updated ${s}s ago`;
  if (_nextRefreshAt) {
    const left = Math.max(0, Math.ceil((_nextRefreshAt - Date.now()) / 1000));
    const lm = Math.floor(left / 60);
    const ls = left % 60;
    label += ` · next in ${lm > 0 ? lm + 'm ' : ''}${ls}s`;
  }
  document.getElementById('last-updated').textContent = label;
}

function setAutoRefresh(minutes) {
  clearInterval(_autoRefreshTimer);
  clearInterval(_countdownTimer);
  _nextRefreshAt = null;
  localStorage.setItem('autoRefreshMinutes', String(minutes));

  if (!minutes) return;

  const ms = minutes * 60 * 1000;
  _nextRefreshAt = Date.now() + ms;
  _countdownTimer = setInterval(_updateLastRefreshedLabel, 1000);
  _autoRefreshTimer = setInterval(() => {
    _nextRefreshAt = Date.now() + ms;
    refreshAll();
  }, ms);
}

async function reload() {
  await loadAll();
  S.projections = null;
  const activePage = document.querySelector('.nav-item.active')?.dataset.page || 'dashboard';
  navigate(activePage);
}

// ── Tabs ────────────────────────────────────────────────────────────────────
function switchTab(tabId) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelector(`.tab[data-tab="${tabId}"]`).classList.add('active');
  document.getElementById(tabId).classList.add('active');
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function _priceAgeClass(isoStr) {
  if (!isoStr) return 'price-stale-old';
  const ageHours = (Date.now() - new Date(isoStr).getTime()) / 3600000;
  if (ageHours > 48) return 'price-stale-old';
  if (ageHours > 24) return 'price-stale-warn';
  return 'price-fresh';
}

// ── Profiles & Settings ──────────────────────────────────────────────────
function renderProfilesUI() {
  const profileId = localStorage.getItem('portfolio_profile') || 'default';
  const sel = document.getElementById('profileSelect');
  if (sel) {
    sel.innerHTML = S.profiles.map(p => `<option value="${p.id}" ${p.id === profileId ? 'selected' : ''}>${esc(p.name)}</option>`).join('');
  }

  const tbody = document.getElementById('profiles-tbody');
  if (tbody) {
    tbody.innerHTML = S.profiles.map(p => `<tr>
      <td><strong>${esc(p.name)}</strong></td>
      <td style="color:var(--muted)">${p.id}</td>
      <td>
        <button class="btn btn-sm" onclick="renameProfile('${p.id}', '${esc(p.name).replace(/'/g, "\\'")}')">✎ Rename</button>
        ${p.id !== 'default' ? `<button class="btn btn-sm btn-danger" onclick="deleteProfile('${p.id}')">✕</button>` : ''}
      </td>
    </tr>`).join('');
  }
}

async function createNewProfile() {
  const input = document.getElementById('new-profile-name');
  const name = input.value.trim();
  if (!name) return;
  const id = name.toLowerCase().replace(/[^a-z0-9-_]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
  if (!id) { notify('Invalid name', 'error'); return; }
  try {
    await API.createProfile(id, name);
    input.value = '';
    S.profiles = await API.getProfiles();
    renderProfilesUI();
    notify('Portfolio created');
  } catch (e) { notify(e.message, 'error'); }
}

async function renameProfile(id, currentName) {
  const name = prompt('Enter new portfolio name:', currentName);
  if (!name || name.trim() === currentName) return;
  try {
    await API.updateProfile(id, name.trim());
    S.profiles = await API.getProfiles();
    renderProfilesUI();
    notify('Portfolio renamed');
  } catch (e) { notify(e.message, 'error'); }
}

async function deleteProfile(id) {
  if (id === 'default') return;
  if (!confirm(`Are you sure you want to permanently delete portfolio "${id}"? This will delete all its holdings, prices, and history.`)) return;
  try {
    await API.deleteProfile(id);
    const active = localStorage.getItem('portfolio_profile');
    if (active === id) {
      localStorage.setItem('portfolio_profile', 'default');
      window.location.reload();
    } else {
      S.profiles = await API.getProfiles();
      renderProfilesUI();
      notify('Portfolio deleted');
    }
  } catch (e) { notify(e.message, 'error'); }
}

// ── Init ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  document.querySelectorAll('.nav-item').forEach(el => el.addEventListener('click', () => navigate(el.dataset.page)));
  document.getElementById('refreshBtn').addEventListener('click', refreshAll);
  document.getElementById('addPosBtn').addEventListener('click', openAddModal);
  document.getElementById('savePos').addEventListener('click', savePosition);
  document.getElementById('importT212Btn').addEventListener('click', importT212);

  document.getElementById('fetchAllDivBtn').addEventListener('click', async () => {
    const btn = document.getElementById('fetchAllDivBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Fetching…';
    try {
      const r = await API.fetchAllDividends();
      notify(`Fetched dividends for ${r.fetched} positions, ${r.total_inserted} new events${r.failed ? `, ${r.failed} failed` : ''}`);
      [S.positions, S.dividendEvents, S.upcoming] = await Promise.all([
        API.getPositions(), API.getDividendEvents(), API.getUpcomingDividends(),
      ]);
      renderIncome();
    } catch (e) { notify(e.message, 'error'); } finally {
      btn.disabled = false;
      btn.innerHTML = '⬇ Fetch All Dividends';
    }
  });

  document.getElementById('price-modal').addEventListener('click', (e) => {
    if (e.target === document.getElementById('price-modal')) closePriceModal();
  });

  document.querySelectorAll('.modal-close').forEach(el => el.addEventListener('click', () => {
    closeModal(); closePriceModal();
  }));
  document.querySelectorAll('.modal-backdrop').forEach(el => {
    el.addEventListener('click', (e) => { if (e.target === el) { closeModal(); closePriceModal(); } });
  });
  document.querySelectorAll('.tab').forEach(el => el.addEventListener('click', () => switchTab(el.dataset.tab)));

  // Sort headers
  document.querySelectorAll('th.sortable').forEach(th => {
    th.style.cursor = 'pointer';
    th.addEventListener('click', () => setSort(th.dataset.col));
  });

  // Filter box
  document.getElementById('tbl-filter').addEventListener('input', (e) => {
    S.filter = e.target.value;
    renderPortfolio();
  });

  // Profile selector
  const profileSel = document.getElementById('profileSelect');
  if (profileSel) {
    profileSel.addEventListener('change', (e) => {
      localStorage.setItem('portfolio_profile', e.target.value);
      window.location.reload();
    });
  }

  // Auto-refresh selector
  const arSel = document.getElementById('autoRefreshSelect');
  const savedAr = parseInt(localStorage.getItem('autoRefreshMinutes') || '0', 10);
  arSel.value = String(savedAr);
  arSel.addEventListener('change', () => setAutoRefresh(parseInt(arSel.value, 10)));
  if (savedAr) setAutoRefresh(savedAr);

  // Tick the "Updated X ago" label every second
  setInterval(_updateLastRefreshedLabel, 1000);

  // AI Insights Generation
  document.getElementById('btn-generate-ai').addEventListener('click', () => {
    const btn = document.getElementById('btn-generate-ai');
    const content = document.getElementById('ai-content');
    
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Generating...';
    content.innerHTML = '<div style="color:var(--muted);text-align:center;padding:40px 0">Connecting to Ollama...</div>';
    
    let md = '';
    API.streamAIAnalysis(
      (chunk) => {
        md += chunk;
        content.innerHTML = marked.parse(md);
      },
      () => { // done
        btn.disabled = false;
        btn.innerHTML = '✨ Generate Analysis';
      },
      (err) => { // error
        btn.disabled = false;
        btn.innerHTML = '✨ Generate Analysis';
        notify(err.message, 'error');
        content.innerHTML = `<div style="color:var(--fg-danger);padding:20px">${err.message}</div>`;
      }
    );
  });

  await loadAll();
  S._lastRefreshed = Date.now();
  _updateLastRefreshedLabel();
  navigate('dashboard');
});
