// ── API 基础地址 ──
const API = window.location.origin;

// ── 站点自动补全（从API动态获取） ──
let allStationsCache = [];

async function loadStationList() {
  try {
    const resp = await fetch(API + '/api/stations');
    const data = await resp.json();
    const names = new Set();
    data.stations.forEach(s => names.add(s.name));
    allStationsCache = Array.from(names).sort();
  } catch(e) { console.error('Station list load failed:', e); }
}
loadStationList();

function showSuggestions(inputId, suggestId) {
  const input = document.getElementById(inputId);
  const suggest = document.getElementById(suggestId);
  const val = input.value.trim();
  if (!val) { suggest.classList.remove('show'); return; }
  const matches = allStationsCache.filter(s => s.includes(val)).slice(0, 10);
  if (matches.length === 0) { suggest.classList.remove('show'); return; }
  suggest.innerHTML = matches.map(s => `<div>${s}</div>`).join('');
  suggest.querySelectorAll('div').forEach(div => {
    div.addEventListener('click', () => {
      input.value = div.textContent;
      suggest.classList.remove('show');
    });
  });
  suggest.classList.add('show');
}

document.getElementById('fromStation').addEventListener('input', () => showSuggestions('fromStation', 'fromSuggestions'));
document.getElementById('toStation').addEventListener('input', () => showSuggestions('toStation', 'toSuggestions'));

// 点击空白关闭建议
document.addEventListener('click', (e) => {
  if (!e.target.closest('.form-group')) {
    document.querySelectorAll('.suggestions').forEach(s => s.classList.remove('show'));
  }
});

// 交换起终点
document.getElementById('swapBtn').addEventListener('click', () => {
  const from = document.getElementById('fromStation');
  const to = document.getElementById('toStation');
  [from.value, to.value] = [to.value, from.value];
});

// ── 路线查询 ──
document.getElementById('searchBtn').addEventListener('click', searchRoutes);

async function searchRoutes() {
  const from = document.getElementById('fromStation').value.trim();
  const to = document.getElementById('toStation').value.trim();
  const strategy = document.getElementById('strategy').value;
  const errorEl = document.getElementById('errorMsg');
  const loadingEl = document.getElementById('loading');
  const resultsEl = document.getElementById('results');

  errorEl.classList.remove('show');
  resultsEl.innerHTML = '';

  if (!from || !to) {
    errorEl.textContent = '请输入起点和终点站名';
    errorEl.classList.add('show');
    return;
  }

  loadingEl.style.display = 'block';
  try {
    const params = new URLSearchParams({ from, to, strategy });
    const resp = await fetch(`${API}/api/plan?${params}`);
    const data = await resp.json();
    loadingEl.style.display = 'none';

    if (data.error) {
      errorEl.textContent = data.error;
      errorEl.classList.add('show');
      return;
    }
    if (!data.routes || data.routes.length === 0) {
      errorEl.textContent = '未找到可达路线，请尝试其他站点';
      errorEl.classList.add('show');
      return;
    }
    renderRoutes(data.routes);
    highlightRoute(data);
  } catch (err) {
    loadingEl.style.display = 'none';
    errorEl.textContent = '网络错误，请检查服务器是否启动';
    errorEl.classList.add('show');
  }
}

function renderRoutes(routes) {
  const resultsEl = document.getElementById('results');
  resultsEl.innerHTML = routes.map((r, i) => {
    const isBest = i === 0;
    const badgeHtml = isBest ? '<span class="route-badge green">推荐</span>' : '';
    const starBtn = `<span class="fav-star" data-from="${r.details.stations[0]}" data-to="${r.details.stations[r.details.stations.length-1]}" data-lines="${r.lines.join(',')}" title="收藏路线">&#9734;</span>`;
    const transferBadges = r.details.transfers.map(t =>
      `<span class="transfer-info">换乘: ${t.station} (${t.fromLine} → ${t.toLine}) 步行${t.walkTime}分钟</span>`
    ).join('');

    const stationHtml = r.details.stations.map((s, j) => {
      const isTransfer = r.details.transfers.some(t => t.station === s);
      const cls = isTransfer ? 'station-dot transfer' : 'station-dot';
      const arrow = j < r.details.stations.length - 1 ? ' → ' : '';
      return `<span class="${cls}">${s}</span>${arrow}`;
    }).join('');

    return `
      <div class="route-card ${isBest ? 'best' : ''}">
        <div class="route-header">
          <div class="route-stats">
            <div class="stat"><div class="stat-val">${r.totalTime}min</div><div class="stat-lbl">总时间</div></div>
            <div class="stat"><div class="stat-val">${r.transfers}次</div><div class="stat-lbl">换乘</div></div>
            <div class="stat"><div class="stat-val">¥${r.price}</div><div class="stat-lbl">票价</div></div>
          </div>
          ${badgeHtml} ${starBtn}
        </div>
        <div class="station-line">${stationHtml}</div>
        <div style="margin-top:0.3rem">
          ${r.lines.map(l => `<span class="line-tag line-${l}">${l}</span>`).join(' ')}
        </div>
        ${transferBadges}
      </div>`;
  }).join('');
}

// ── 开门方向查询 ──
document.getElementById('doorBtn').addEventListener('click', async () => {
  const line = document.getElementById('doorLine').value.trim();
  const station = document.getElementById('doorStation').value.trim();
  const direction = document.getElementById('doorDirection').value;
  const resultEl = document.getElementById('doorResult');

  if (!line || !station) { resultEl.innerHTML = '请输入线路和站名'; resultEl.classList.add('show'); return; }

  try {
    const params = new URLSearchParams({ line, station, direction });
    const resp = await fetch(`${API}/api/door?${params}`);
    const data = await resp.json();
    if (data.error) { resultEl.innerHTML = data.error; resultEl.className = 'door-result error show'; return; }
    const sideCls = data.doorSide === 'left' ? 'side-left' : 'side-right';
    const sideText = data.doorSide === 'left' ? '左侧门' : '右侧门';
    resultEl.innerHTML = `<strong>${data.station}</strong> (${data.line}, ${data.direction === 'up' ? '上行' : '下行'}) — 开<span class="${sideCls}">${sideText}</span> · 站台类型: ${data.platformType === 'island' ? '岛式' : '侧式'}`;
    resultEl.className = 'door-result show';
  } catch (err) {
    resultEl.innerHTML = '查询失败';
    resultEl.className = 'door-result error show';
  }
});

// ── 站内设施查询 ──
document.getElementById('facilityStation').addEventListener('input', () => showSuggestions('facilityStation', 'facilitySuggestions'));
document.getElementById('facilityBtn').addEventListener('click', async () => {
  const station = document.getElementById('facilityStation').value.trim();
  const resultEl = document.getElementById('facilityResult');
  if (!station) { resultEl.innerHTML = '请输入站名'; resultEl.classList.add('show'); return; }

  try {
    const resp = await fetch(`${API}/api/facilities?station=${encodeURIComponent(station)}`);
    const data = await resp.json();
    if (!data.facilities || data.facilities.length === 0) {
      resultEl.innerHTML = `<p>未找到「${station}」的设施数据</p>`;
      resultEl.className = 'facility-result show';
      return;
    }
    const items = data.facilities.map(f =>
      `<div class="facility-item">
        <div class="facility-icon ${f.type}">${f.icon}</div>
        <div class="facility-info">
          <div class="fname">${f.label}</div>
          <div class="fdetail">${f.floor} ${f.location}</div>
        </div>
      </div>`
    ).join('');
    const source = data.source === 'amap' ? '（来自高德地图）' : '';
    resultEl.innerHTML = `<h3>${data.station} ${data.line}</h3><div class="facility-grid">${items}</div><div class="facility-source">${source}</div>`;
    resultEl.className = 'facility-result show';
    showFacilitiesOnMap(data);
  } catch (err) {
    resultEl.innerHTML = '查询失败';
    resultEl.className = 'facility-result show';
  }
});

// ── 收藏功能 ──
let authToken = localStorage.getItem('metro_token') || '';
let allFavorites = [];

function checkLogin() {
  const link = document.getElementById('loginLink');
  const info = document.getElementById('userInfo');
  const card = document.getElementById('favCard');
  if (authToken) {
    const phone = localStorage.getItem('metro_phone') || '';
    link.style.display = 'none';
    info.style.display = 'inline';
    info.innerHTML = phone + ' | <a href=\"#\" onclick=\"logout()\" style=\"color:#fff\">退出</a>';
    card.style.display = 'block';
    loadFavorites();
  } else {
    link.style.display = 'inline';
    info.style.display = 'none';
    card.style.display = 'none';
  }
}

function logout() {
  localStorage.removeItem('metro_token');
  localStorage.removeItem('metro_phone');
  authToken = '';
  checkLogin();
}

async function loadFavorites() {
  if (!authToken) return;
  try {
    const resp = await fetch(API + '/api/favorites', {
      headers: { 'Authorization': 'Bearer ' + authToken }
    });
    if (!resp.ok) { if (resp.status === 401) logout(); return; }
    const data = await resp.json();
    allFavorites = data.favorites || [];
    renderFavorites();
  } catch(e) {}
}

function renderFavorites() {
  const el = document.getElementById('favList');
  const items = allFavorites.filter(f => f.fav_type === 'route');
  if (items.length === 0) {
    el.innerHTML = '<div class=\"fav-empty\">暂无收藏路线</div>'; return;
  }
  el.innerHTML = items.map(f =>
    `<div class=\"fav-item\">
      <span>${f.from_name} → ${f.to_name} (${f.lines || ''})</span>
      <span><span class=\"fav-use\" onclick=\"useRoute('${f.from_name}','${f.to_name}')\">查询</span>
      <span class=\"fav-del\" onclick=\"delFav(${f.id})\">删除</span></span></div>`
  ).join('');
}

function useRoute(from, to) {
  document.getElementById('fromStation').value = from;
  document.getElementById('toStation').value = to;
  searchRoutes();
}

// 事件委托：点击收藏星标
document.addEventListener('click', async (e) => {
  const star = e.target.closest('.fav-star');
  if (!star) return;
  e.preventDefault();
  if (!authToken) { window.location.href = '/login.html'; return; }
  const from = star.dataset.from || '';
  const to = star.dataset.to || '';
  const lines = star.dataset.lines || '';
  try {
    await fetch(API + '/api/favorites', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken },
      body: JSON.stringify({ fav_type: 'route', from_name: from, to_name: to, station_name: '', lines }),
    });
    star.innerHTML = '&#9733;';
    star.classList.add('saved');
    loadFavorites();
  } catch(e) {}
});

async function addFav(type, from, to, station, lines) {
  if (!authToken) { window.location.href = '/login.html'; return; }
  try {
    await fetch(API + '/api/favorites', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken },
      body: JSON.stringify({ fav_type: type, from_name: from, to_name: to, station_name: station, lines }),
    });
    loadFavorites();
  } catch(e) {}
}

async function delFav(id) {
  try {
    await fetch(API + '/api/favorites/' + id, {
      method: 'DELETE', headers: { 'Authorization': 'Bearer ' + authToken }
    });
    loadFavorites();
  } catch(e) {}
}

checkLogin();
