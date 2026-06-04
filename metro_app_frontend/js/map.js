// ── Leaflet 地图初始化 ──
const LINE_COLORS = { '1号线': '#c23a30', '2号线': '#107dc0', '3号线': '#e8791d' };
const map = L.map('map').setView([39.92, 116.38], 12);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap', maxZoom: 18
}).addTo(map);

const stationMarkers = {};
const lineLayers = {};
const routeLayers = [];
const facilityLayers = [];

// ── 加载并绘制路网 ──
async function loadNetwork() {
  try {
    const [sResp, eResp] = await Promise.all([
      fetch(API + '/api/stations'), fetch(API + '/api/line_edges')
    ]);
    const stations = (await sResp.json()).stations;
    const edges = (await eResp.json()).edges;

    // 绘制线路
    const edgeMap = {};
    for (const e of edges) {
      const key = e.line + '|' + e.direction;
      if (!edgeMap[key]) edgeMap[key] = [];
      edgeMap[key].push(e);
    }

    // 按线路→方向组织坐标序列
    const linePaths = {};
    for (const e of edges) {
      if (!linePaths[e.line]) linePaths[e.line] = { up: [], down: [] };
      const arr = linePaths[e.line][e.direction];
      if (arr.length === 0 || arr[arr.length - 1].to_station !== e.from_station) {
        arr.push([{ lat: e.from_lat, lng: e.from_lng, id: e.from_station }, { lat: e.to_lat, lng: e.to_lng, id: e.to_station }]);
      } else {
        arr[arr.length - 1].push({ lat: e.to_lat, lng: e.to_lng, id: e.to_station });
      }
    }

    for (const [line, dirs] of Object.entries(linePaths)) {
      for (const segs of Object.values(dirs)) {
        for (const seg of segs) {
          const coords = seg.map(p => [p.lat, p.lng]);
          const poly = L.polyline(coords, {
            color: LINE_COLORS[line] || '#666', weight: 5, opacity: 0.8
          }).addTo(map);
          if (!lineLayers[line]) lineLayers[line] = [];
          lineLayers[line].push(poly);
        }
      }
    }

    // 绘制站点
    for (const s of stations) {
      const color = LINE_COLORS[s.line] || '#666';
      const icon = L.divIcon({
        className: 'station-marker',
        html: `<div style="background:${color};width:10px;height:10px;border-radius:50%;border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3)"></div>`,
        iconSize: [14, 14], iconAnchor: [7, 7]
      });
      const marker = L.marker([s.lat, s.lng], { icon })
        .bindPopup(`<b>${s.name}</b><br>${s.line} · ${s.platform_type === 'island' ? '岛式站台' : '侧式站台'}`)
        .addTo(map);
      stationMarkers[s.id] = marker;
    }
  } catch (e) { console.error('Map load failed:', e); }
}

// ── 高亮路线 ──
function highlightRoute(planResult) {
  clearRoute();
  if (!planResult || !planResult.routes || !planResult.routes.length) return;
  const route = planResult.routes[0];
  const stations = route.details.stations;
  const coords = [];
  for (const name of stations) {
    for (const [id, m] of Object.entries(stationMarkers)) {
      const popup = m.getPopup();
      if (popup && popup.getContent().includes('<b>' + name + '</b>')) {
        coords.push(m.getLatLng());
        // 高亮站点
        const color = LINE_COLORS[route.lines[0]] || '#c23a30';
        const bigIcon = L.divIcon({
          className: 'station-marker-hl',
          html: `<div style="background:${color};width:16px;height:16px;border-radius:50%;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.4);animation:pulse 1s infinite"></div>`,
          iconSize: [22, 22], iconAnchor: [11, 11]
        });
        const hl = L.marker(m.getLatLng(), { icon: bigIcon }).addTo(map);
        hl.bindPopup(`<b>${name}</b><br>${route.lines.join(' → ')}`);
        routeLayers.push(hl);
        break;
      }
    }
  }
  if (coords.length >= 2) {
    const path = L.polyline(coords, { color: '#ff6d00', weight: 6, opacity: 0.9, dashArray: '10,6' }).addTo(map);
    routeLayers.push(path);
    map.fitBounds(coords, { padding: [40, 40] });
  }
}

function clearRoute() {
  routeLayers.forEach(l => map.removeLayer(l));
  routeLayers.length = 0;
}

// ── 显示设施位置 ──
function showFacilitiesOnMap(facData) {
  clearFacilities();
  if (!facData || !facData.facilities || !facData.facilities.length) return;

  // 找到对应站坐标
  let lat = null, lng = null;
  for (const [id, m] of Object.entries(stationMarkers)) {
    const popup = m.getPopup();
    if (popup && popup.getContent().includes('<b>' + facData.station + '</b>')) {
      lat = m.getLatLng().lat; lng = m.getLatLng().lng; break;
    }
  }
  if (!lat) return;

  const iconMap = {
    restroom: { icon: '♿', color: '#34a853', label: '卫生间' },
    accessible_restroom: { icon: '♿', color: '#1a73e8', label: '无障碍卫生间' },
    nursing_room: { icon: '👶', color: '#e8710a', label: '母婴室' },
    accessible_elevator: { icon: '⬆', color: '#7b1fa2', label: '无障碍电梯' },
    elevator: { icon: '⬆', color: '#00838f', label: '直梯' },
    escalator: { icon: '↗', color: '#795548', label: '扶梯' },
  };

  // 在站周围分布设施标记（微偏移避免重叠）
  const offsets = [
    [0, 0], [30, 0], [-30, 0], [0, 30], [0, -30],
    [20, 20], [-20, 20], [20, -20], [-20, -20]
  ];
  let idx = 0;
  for (const f of facData.facilities) {
    const cfg = iconMap[f.type] || { icon: '?', color: '#999', label: f.label };
    const [dx, dy] = offsets[idx % offsets.length]; idx++;
    const icon = L.divIcon({
      className: 'facility-marker',
      html: `<div style="background:${cfg.color};color:white;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.3)">${cfg.icon}</div>`,
      iconSize: [28, 28], iconAnchor: [14, 14]
    });
    const m = L.marker([lat + dy * 0.00005, lng + dx * 0.00005], { icon })
      .bindPopup(`<b>${cfg.label}</b><br>${f.floor} ${f.location}`)
      .addTo(map);
    facilityLayers.push(m);
  }
  map.setView([lat, lng], 15);
}

function clearFacilities() {
  facilityLayers.forEach(l => map.removeLayer(l));
  facilityLayers.length = 0;
}

// 启动加载路网
loadNetwork();
