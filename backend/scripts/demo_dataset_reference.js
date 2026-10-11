'use strict';
/*
 * 参考实现：deliverables/db-migration/reference/demoDataset.js 的忠实复刻，唯一差别是「当前时刻 now」
 * 由命令行注入（demoDataset.js 内部用 new Date()，无法对齐两侧时间）。
 * 仅供 backend/scripts/reconcile_seed.py 做「原始 JS 算法 vs 库内数据」全量逐条对账。
 *
 * 用法：
 *   node demo_dataset_reference.js "YYYY-MM-DD HH:MM:SS" [--clamp]
 *     --clamp  应用与 seed_ledger.py 相同的复核时间 clamp 修正
 * 输出：stdout 一行 JSON {now, clamp, count, records:[...]}
 *
 * 注意：本文件复制自参考基准 demoDataset.js（现位于 deliverables/db-migration/reference/），请勿修改该基准文件。
 */

const CAMERAS = [
  { id: 'CAM-03', name: '建设大道-香港路口' },
  { id: 'CAM-01', name: '珞喻路-光谷广场口' },
  { id: 'CAM-02', name: '解放大道-新华路口' },
  { id: 'CAM-04', name: '武珞路-中南路口' },
  { id: 'CAM-05', name: '钟家村-鹦鹉大道口' },
];

const SEED = 20260930;
const DAYS = 7;
const TODAY_TARGET = 190;
const PREV_DAY_COUNTS = [92, 104, 86, 118, 96, 132];
const HOUR_WEIGHTS = [
  1, 0.6, 0.4, 0.3, 0.4, 1.2, 4, 9, 12, 6, 4, 4,
  5, 4, 3.5, 4, 7, 11, 9, 6, 4, 3, 2.5, 1.5,
];
const DIRECTIONS = ['东向非机动车道', '西向非机动车道', '南向非机动车道', '北向非机动车道'];
const REVIEWERS = ['张警官 (警号: 08412)', '李警官 (警号: 08419)', '王警官 (警号: 08427)'];
const VEHICLE_POOL = [
  '白色雅迪电瓶车 [无牌照]',
  '深蓝轻便电摩 [鄂A·E8821]',
  '绿色外卖配送电动车',
  '红色电动三轮/踏板车',
  '灰色九号智能电动车',
  '黑色小牛电动踏板车 [鄂A·D3097]',
  '银灰电动自行车 [号牌污损不可辨识]',
  '蓝色共享助力车',
  '黄色闪送配送电动车 [鄂A·F2210]',
];
const REMARK_APPROVE = [
  '驾驶人头部完全裸露，未佩戴任何护具，复核无误',
  '骑行人员未佩戴头盔事实清楚，确认入卷',
  '头部区域清晰，未检测到安全头盔，确认入卷',
  '连续多帧取证完整，违规事实成立',
];
const REMARK_REJECT = [
  '误报剔除：佩戴防风毛线帽/遮阳帽，头部已有防护',
  '雨夜反光导致头部特征丢失，判定为非违规',
  '头部被随车货物遮挡，无法确认，剔除',
  '遮挡严重，无法确认头部特征，剔除',
];

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function parseLocal(s) {
  const [d, t] = s.split(' ');
  const [Y, M, D] = d.split('-').map(Number);
  const [h, m, sec] = t.split(':').map(Number);
  return new Date(Y, M - 1, D, h, m, sec);
}
function pad(v) { return String(v).padStart(2, '0'); }
function formatTime(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} `
    + `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
function stampId(date, seq) {
  return `EV-${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${String(seq).padStart(4, '0')}`;
}

const nowStr = process.argv[2];
const CLAMP = process.argv.includes('--clamp');
const now = parseLocal(nowStr);

const rand = mulberry32(SEED);
const pick = list => list[Math.floor(rand() * list.length)];
const randInt = (min, max) => min + Math.floor(rand() * (max - min + 1));
const randFloat = (min, max) => min + rand() * (max - min);

function pickHour() {
  const total = HOUR_WEIGHTS.reduce((sum, w) => sum + w, 0);
  let point = rand() * total;
  for (let hour = 0; hour < HOUR_WEIGHTS.length; hour += 1) {
    point -= HOUR_WEIGHTS[hour];
    if (point <= 0) return hour;
  }
  return HOUR_WEIGHTS.length - 1;
}
function pickConfidence() {
  const roll = rand();
  if (roll < 0.12) return Number(randFloat(0.36, 0.69).toFixed(2));
  if (roll < 0.42) return Number(randFloat(0.70, 0.89).toFixed(2));
  return Number(randFloat(0.90, 0.99).toFixed(2));
}
function buildType() { return '未按规定佩戴安全头盔'; }
function buildDetails() {
  return {
    helmet_status: 'not_wearing',
    consecutive_frames: randInt(3, 12),
    plate_or_vehicle: pick(VEHICLE_POOL),
  };
}

function buildRecords() {
  const output = [];
  for (let offset = DAYS - 1; offset >= 0; offset -= 1) {
    const isToday = offset === 0;
    const target = isToday ? TODAY_TARGET : PREV_DAY_COUNTS[DAYS - 1 - offset];
    const day = new Date(now.getFullYear(), now.getMonth(), now.getDate() - offset);
    let seq = 1;
    for (let i = 0; i < target; i += 1) {
      const hour = pickHour();
      const minute = randInt(0, 59);
      const second = randInt(0, 59);
      const captured = new Date(day.getFullYear(), day.getMonth(), day.getDate(), hour, minute, second);

      const cam = CAMERAS[Math.floor(rand() * CAMERAS.length)];
      const category = 'helmet';
      const confidence = pickConfidence();

      const statusRoll = rand();
      let status;
      if (isToday) {
        status = statusRoll < 0.55 ? 'pending' : (statusRoll < 0.90 ? 'approved' : 'rejected');
      } else {
        status = statusRoll < 0.06 ? 'pending' : (statusRoll < 0.90 ? 'approved' : 'rejected');
      }
      const reviewed = status !== 'pending';
      let reviewTime = new Date(captured.getTime() + randInt(4, 90) * 60 * 1000);
      if (CLAMP && reviewTime > now) reviewTime = new Date(now.getTime());

      const record = {
        id: stampId(day, seq),
        camera_id: `${cam.id}-${pick(DIRECTIONS)}`,
        track_id: randInt(20, 980),
        violation_type: buildType(),
        category,
        confidence,
        status,
        reviewer: reviewed ? pick(REVIEWERS) : null,
        review_time: reviewed ? formatTime(reviewTime) : null,
        review_remark: reviewed ? pick(status === 'approved' ? REMARK_APPROVE : REMARK_REJECT) : '',
        capture_time: formatTime(captured),
        details: buildDetails(),
      };

      if (isToday && captured > now) continue;
      output.push(record);
      seq += 1;
    }
  }
  return output;
}

function buildEdgeCases() {
  const back = minutes => formatTime(new Date(now.getTime() - minutes * 60 * 1000));
  const idOf = (minutes, seq) => stampId(new Date(now.getTime() - minutes * 60 * 1000), seq);
  return [
    {
      id: idOf(26, 9001), camera_id: 'CAM-04-南向非机动车道', track_id: 411,
      violation_type: '未按规定佩戴安全头盔', category: 'helmet', confidence: 0.38,
      status: 'pending', reviewer: null, review_time: null, review_remark: '',
      capture_time: back(26),
      details: { helmet_status: 'not_wearing', consecutive_frames: 3, plate_or_vehicle: '银灰电动自行车 [号牌污损不可辨识]' },
    },
    {
      id: idOf(53, 9002), camera_id: 'CAM-02-北向非机动车道', track_id: 377,
      violation_type: '未按规定佩戴安全头盔', category: 'helmet', confidence: 0.52,
      status: 'rejected', reviewer: '张警官 (警号: 08412)', review_time: back(41),
      review_remark: '雨夜反光导致头部特征丢失，判定为非违规', capture_time: back(53),
      details: { helmet_status: 'not_wearing', consecutive_frames: 4, plate_or_vehicle: '绿色外卖配送电动车' },
    },
    {
      id: idOf(78, 9003), camera_id: 'CAM-03-东向非机动车道', track_id: 502,
      violation_type: '未按规定佩戴安全头盔', category: 'helmet', confidence: 0.93,
      status: 'approved', reviewer: '李警官 (警号: 08419)', review_time: back(70),
      review_remark: '头部区域清晰，未佩戴安全头盔，确认入卷', capture_time: back(78),
      details: { helmet_status: 'not_wearing', consecutive_frames: 11, plate_or_vehicle: '红色电动三轮/踏板车' },
    },
    {
      id: idOf(112, 9004), camera_id: 'CAM-05-西向非机动车道', track_id: 268,
      violation_type: '未按规定佩戴安全头盔', category: 'helmet', confidence: 0.64,
      status: 'pending', reviewer: null, review_time: null, review_remark: '',
      capture_time: back(112),
      details: { helmet_status: 'not_wearing', consecutive_frames: 5, plate_or_vehicle: '遮挡严重 · 无法辨识车身特征' },
    },
  ];
}

const DISPOSITION_SEED = 20261002;
const dispositionRand = mulberry32(DISPOSITION_SEED);
const DISPOSITION_METHODS = [
  { method: '罚款处罚', remark: '按《道路交通安全法》相关条款处以罚款，处罚决定书已送达当事人' },
  { method: '警告处罚', remark: '首次违规且情节轻微，予以警告并现场教育纠正' },
  { method: '安全教育学习', remark: '责令参加交通安全教育学习，已完成签到与结业登记' },
  { method: '现场拦查处置', remark: '已通知路面警力拦查，当场纠正违法行为并登记' },
];
const DISPOSITION_HANDLERS = ['张建国 (警号: 08412)', '李文博 (警号: 08419)', '王海涛 (警号: 08427)'];
const DISPOSITION_DEFAULT = { status: null, method: '', notified_at: '', disposed_at: '', handler: '', remark: '', history: [] };

function addHours(date, hours) { return new Date(date.getTime() + hours * 3600 * 1000); }

function buildDisposition(record) {
  if (record.status !== 'approved') return { ...DISPOSITION_DEFAULT, history: [] };
  const reviewed = record.review_time
    ? new Date(record.review_time.replace(' ', 'T'))
    : new Date(record.capture_time.replace(' ', 'T'));
  const notifyPlan = addHours(reviewed, 0.5 + dispositionRand() * 18);
  const disposePlan = addHours(notifyPlan, 1 + dispositionRand() * 6);
  const archivePlan = addHours(disposePlan, 12 + dispositionRand() * 72);

  let stage = 'to_notify';
  if (now >= archivePlan) stage = 'archived';
  else if (now >= disposePlan) stage = 'disposed';
  else if (now >= notifyPlan) stage = 'notified';

  const item = DISPOSITION_METHODS[Math.floor(dispositionRand() * DISPOSITION_METHODS.length)];
  const handler = DISPOSITION_HANDLERS[Math.floor(dispositionRand() * DISPOSITION_HANDLERS.length)];

  const hasNotified = stage !== 'to_notify';
  const hasDisposed = stage === 'disposed' || stage === 'archived';
  const notifiedText = formatTime(notifyPlan);
  const disposedText = formatTime(disposePlan);

  const history = [];
  if (hasNotified) {
    history.push({ action: 'notify', operator: record.reviewer || handler, remark: `已告知当事人违法事实、处理依据与办理地点（${record.camera_id}）`, time: notifiedText });
  }
  if (hasDisposed) {
    history.push({ action: 'dispose', operator: handler, remark: item.remark, time: disposedText });
  }
  if (stage === 'archived') {
    history.push({ action: 'archive', operator: handler, remark: '处理结果已执行完毕，证据材料归档入卷', time: formatTime(archivePlan) });
  }

  return {
    status: stage,
    method: hasDisposed ? item.method : '',
    notified_at: hasNotified ? notifiedText : '',
    disposed_at: hasDisposed ? disposedText : '',
    handler: hasNotified ? handler : '',
    remark: hasDisposed ? item.remark : (hasNotified ? '已告知当事人，等待处理结果' : ''),
    history,
  };
}

const demoRecords = [...buildRecords(), ...buildEdgeCases()]
  .sort((a, b) => b.capture_time.localeCompare(a.capture_time))
  .map(record => ({ ...record, disposition: buildDisposition(record) }));

process.stdout.write(JSON.stringify({ now: nowStr, clamp: CLAMP, count: demoRecords.length, records: demoRecords }));
