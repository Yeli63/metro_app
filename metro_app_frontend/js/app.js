// ── API 基础地址 ──
const API = window.location.origin;

// ── 站点自动补全 ──
const allStations = ['苹果园','古城','八角游乐园','八宝山','玉泉路','五棵松','万寿路','公主坟','军事博物馆','木樨地','南礼士路','复兴门','西单','天安门西','天安门东','王府井','东单','建国门','永安里','国贸','大望路','四惠','四惠东','西直门','积水潭','鼓楼大街','安定门','雍和宫','东直门','东四十条','朝阳门','北京站','崇文门','前门','和平门','宣武门','长椿街','阜成门','车公庄','工人体育场','团结湖','朝阳公园','石佛营','北京朝阳站','姚家园','东坝南','东坝','东坝北'];

function showSuggestions(inputId, suggestId) {
  const input = document.getElementById(inputId);
  const suggest = document.getElementById(suggestId);
  const val = input.value.trim();
  if (!val) { suggest.classList.remove('show'); return; }
  const matches = allStations.filter(s => s.includes(val));
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
          ${badgeHtml}
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

// ── 用户认证 ──
let authToken = localStorage.getItem('metro_token') || '';

document.getElementById('loginBtn').addEventListener('click', async () => {
  const phone = document.getElementById('phone').value.trim();
  const password = document.getElementById('password').value;
  const resultEl = document.getElementById('authResult');
  if (phone.length !== 11) { resultEl.innerHTML = '请输入正确的11位手机号'; resultEl.className = 'auth-result error show'; return; }
  if (!password) { resultEl.innerHTML = '请输入密码'; resultEl.className = 'auth-result error show'; return; }

  try {
    const resp = await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, password }),
    });
    const data = await resp.json();
    if (!resp.ok) { resultEl.innerHTML = data.detail || '登录失败'; resultEl.className = 'auth-result error show'; return; }
    authToken = data.token;
    localStorage.setItem('metro_token', authToken);
    resultEl.innerHTML = `${data.user.nickname || phone} — 登录成功`;
    resultEl.className = 'auth-result success show';
  } catch (err) {
    resultEl.innerHTML = '服务器连接失败';
    resultEl.className = 'auth-result error show';
  }
});

document.getElementById('registerBtn').addEventListener('click', async () => {
  const phone = document.getElementById('phone').value.trim();
  const password = document.getElementById('password').value;
  const resultEl = document.getElementById('authResult');
  if (phone.length !== 11) { resultEl.innerHTML = '请输入正确的11位手机号'; resultEl.className = 'auth-result error show'; return; }
  if (password.length < 6) { resultEl.innerHTML = '密码至少6位'; resultEl.className = 'auth-result error show'; return; }

  try {
    const resp = await fetch(`${API}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, password, nickname: phone }),
    });
    const data = await resp.json();
    if (!resp.ok) { resultEl.innerHTML = data.detail || '注册失败'; resultEl.className = 'auth-result error show'; return; }
    resultEl.innerHTML = `注册成功 — ${data.phone}`;
    resultEl.className = 'auth-result success show';
  } catch (err) {
    resultEl.innerHTML = '服务器连接失败 (MongoDB 可能需要启动)';
    resultEl.className = 'auth-result error show';
  }
});
