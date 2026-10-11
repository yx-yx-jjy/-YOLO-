// 卡口主数据 —— 全站唯一来源（大屏地图 / 演示台账 / 研判页都从这里取）
//
// 之前每个页面各写一份点位名与计数：地图里写死 142/96/74/52/38，
// 研判页另写 6 行"过车总量"，大屏再写一遍 TOP5 —— 三份数字互不相干。
// 现在只保留这一份，计数一律由台账实时派生。
//
// coords 为 WGS84，显示前由 WuhanTrafficMap 统一转 GCJ-02 对齐高德瓦片。

export const CAMERAS = [
  { id: 'CAM-03', name: '建设大道-香港路口', area: '汉口金融街', coords: [30.5979, 114.2857], heatRadius: 950 },
  { id: 'CAM-01', name: '珞喻路-光谷广场口', area: '武昌光谷', coords: [30.5054, 114.4142], heatRadius: 800 },
  { id: 'CAM-02', name: '解放大道-新华路口', area: '汉口中山公园', coords: [30.5846, 114.2717], heatRadius: 700 },
  { id: 'CAM-04', name: '武珞路-中南路口', area: '武昌中南商圈', coords: [30.537317, 114.324538], heatRadius: 620 },
  { id: 'CAM-05', name: '钟家村-鹦鹉大道口', area: '汉阳钟家村', coords: [30.5510787, 114.2607073], heatRadius: 560 }
]

/** 卡口危险等级由抓拍量派生，不再写死 */
export function levelOf(count) {
  if (count >= 100) return 'high'
  if (count >= 60) return 'medium'
  return 'low'
}

/** 卡口短名：CAM-03 → 建设大道-香港路口 */
export function cameraName(cameraId) {
  if (!cameraId) return '未知点位'
  const cam = CAMERAS.find(item => cameraId.startsWith(item.id))
  return cam ? cam.name : cameraId
}

/** 卡口主键：'CAM-03-东向非机动车道' → 'CAM-03' */
export function cameraKey(cameraId) {
  if (!cameraId) return ''
  const cam = CAMERAS.find(item => cameraId.startsWith(item.id))
  return cam ? cam.id : cameraId
}
