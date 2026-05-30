const Database = require('better-sqlite3');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const dbPath = process.env.SQLITE_PATH || './metro_network.sqlite';
const db = new Database(dbPath);

// 创建表结构
db.exec(`
    CREATE TABLE IF NOT EXISTS stations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        line TEXT NOT NULL,
        lat REAL,
        lng REAL,
        platform_type TEXT DEFAULT 'island'
    );

    CREATE TABLE IF NOT EXISTS edges (
        from_station TEXT NOT NULL,
        to_station TEXT NOT NULL,
        line TEXT NOT NULL,
        direction TEXT NOT NULL CHECK(direction IN ('up','down')),
        travel_time INT NOT NULL,
        distance_km REAL,
        PRIMARY KEY (from_station, to_station, line)
    );

    CREATE TABLE IF NOT EXISTS transfers (
        station_id TEXT NOT NULL,
        from_line TEXT NOT NULL,
        to_line TEXT NOT NULL,
        walk_time INT DEFAULT 5,
        is_cross_platform INT DEFAULT 0
    );
`);

// 插入示例数据（广州地铁示例，实际应批量导入真实数据）
const insertStations = db.prepare(`
    INSERT OR IGNORE INTO stations (id, name, line, lat, lng, platform_type)
    VALUES (?, ?, ?, ?, ?, ?)
`);

const insertEdges = db.prepare(`
    INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km)
    VALUES (?, ?, ?, ?, ?, ?)
`);

const insertTransfers = db.prepare(`
    INSERT OR IGNORE INTO transfers (station_id, from_line, to_line, walk_time, is_cross_platform)
    VALUES (?, ?, ?, ?, ?)
`);

// 插入示例线路数据（简化版，实际需覆盖全路网）
const seedData = () => {
  // 1号线示例
    const line1Stations = [
        { id: 'line1_001', name: '西朗', line: '1号线', lat: 23.080, lng: 113.230, type: 'island' },
        { id: 'line1_002', name: '坑口', line: '1号线', lat: 23.085, lng: 113.240, type: 'island' },
        { id: 'line1_003', name: '花地湾', line: '1号线', lat: 23.090, lng: 113.250, type: 'island' },
        { id: 'line1_004', name: '芳村', line: '1号线', lat: 23.100, lng: 113.255, type: 'island' },
        { id: 'line1_005', name: '黄沙', line: '1号线', lat: 23.110, lng: 113.260, type: 'island' },
    ];

    line1Stations.forEach(s => {
        insertStations.run(s.id, s.name, s.line, s.lat, s.lng, s.type);
    });

  // 插入边（上行：西朗 -> 坑口 -> ...，下行反向）
  for (let i = 0; i < line1Stations.length - 1; i++) {
    insertEdges.run(
      line1Stations[i].id, line1Stations[i+1].id,
      '1号线', 'up', 3, 1.2
    );
    insertEdges.run(
      line1Stations[i+1].id, line1Stations[i].id,
      '1号线', 'down', 3, 1.2
    );
  }

  // 2号线示例（仅两个站做换乘演示）
  const line2Stations = [
    { id: 'line2_001', name: '公园前', line: '2号线', lat: 23.125, lng: 113.270, type: 'island' },
    { id: 'line2_002', name: '纪念堂', line: '2号线', lat: 23.130, lng: 113.275, type: 'island' },
  ];
  line2Stations.forEach(s => {
    insertStations.run(s.id, s.name, s.line, s.lat, s.lng, s.type);
  });
  insertEdges.run('line2_001', 'line2_002', '2号线', 'up', 2, 0.9);
  insertEdges.run('line2_002', 'line2_001', '2号线', 'down', 2, 0.9);

  // 换乘关系：芳村站 1号线 <-> 2号线？示例中不存在，改为公园前作为换乘站
  // 假设公园前也是1号线某站，添加1号线公园前站
  const parkStations = [
    { id: 'line1_010', name: '公园前', line: '1号线', lat: 23.125, lng: 113.270, type: 'island' },
  ];
  parkStations.forEach(s => {
    insertStations.run(s.id, s.name, s.line, s.lat, s.lng, s.type);
  });
  // 连接1号线公园前前后（略），插入换乘
  insertTransfers.run('line1_010', '1号线', '2号线', 5, 0);
  insertTransfers.run('line2_001', '2号线', '1号线', 5, 0);

  console.log('Seed data inserted successfully.');
};

seedData();
db.close();