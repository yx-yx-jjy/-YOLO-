/**
 * 武汉常用检索地点：片区 / 行政区 / 商圈 / 地标 / 枢纽。
 *
 * 坐标约定：一律按 WGS84 记录（与 CAM-xx 卡口同一套源坐标系），
 * 渲染前由 WuhanTrafficMap 内的 wgs84ToGcj02() 统一转成 GCJ-02 去对齐高德瓦片。
 * 不要在检索完成后再做二次偏移。
 *
 * 精度为街区级（±300m），用途是"把视野快速带到某片区域"，
 * 不承担门牌级寻址与导航精度。
 */
export const wuhanPlaces = [
  // ── 片区：大屏值班最常用的粗定位 ──
  { name: '汉口', category: '片区', coords: [30.5900, 114.2800], zoom: 13, aliases: ['汉口片区', 'hankou'] },
  { name: '武昌', category: '片区', coords: [30.5450, 114.3100], zoom: 13, aliases: ['武昌片区', 'wuchang'] },
  { name: '汉阳', category: '片区', coords: [30.5540, 114.2500], zoom: 13, aliases: ['汉阳片区', 'hanyang'] },
  { name: '光谷', category: '片区', coords: [30.5068, 114.4020], zoom: 13, aliases: ['光谷片区', '东湖高新'] },
  { name: '四新', category: '片区', coords: [30.5300, 114.2400], zoom: 14, aliases: ['四新片区'] },
  { name: '南湖', category: '片区', coords: [30.5100, 114.3300], zoom: 14, aliases: ['南湖片区'] },
  { name: '后湖', category: '片区', coords: [30.6420, 114.2880], zoom: 14, aliases: ['后湖片区'] },
  { name: '青山', category: '片区', coords: [30.6280, 114.3880], zoom: 14, aliases: ['青山区', '红钢城'] },

  // ── 行政区 ──
  { name: '江岸区', category: '行政区', coords: [30.6010, 114.2990], zoom: 13, aliases: ['江岸'] },
  { name: '江汉区', category: '行政区', coords: [30.6053, 114.2718], zoom: 13, aliases: ['江汉'] },
  { name: '硚口区', category: '行政区', coords: [30.5700, 114.2360], zoom: 13, aliases: ['硚口'] },
  { name: '汉阳区', category: '行政区', coords: [30.5540, 114.2480], zoom: 13, aliases: [] },
  { name: '武昌区', category: '行政区', coords: [30.5480, 114.3160], zoom: 13, aliases: [] },
  { name: '洪山区', category: '行政区', coords: [30.5000, 114.3600], zoom: 12, aliases: ['洪山'] },
  { name: '东西湖区', category: '行政区', coords: [30.6200, 114.1400], zoom: 13, aliases: ['东西湖'] },

  // ── 商圈 / 街道 ──
  { name: '光谷广场', category: '商圈', coords: [30.5065, 114.4008], zoom: 15, aliases: ['鲁巷', '光谷步行街'] },
  { name: '楚河汉街', category: '商圈', coords: [30.5513, 114.3290], zoom: 15, aliases: ['汉街'] },
  { name: '江汉路步行街', category: '商圈', coords: [30.5810, 114.2920], zoom: 15, aliases: ['江汉路'] },
  { name: '武商摩尔', category: '商圈', coords: [30.5390, 114.3250], zoom: 15, aliases: ['亚贸', '武商量贩'] },
  { name: '街道口', category: '商圈', coords: [30.5290, 114.3520], zoom: 15, aliases: ['群光广场'] },
  { name: '中南路', category: '商圈', coords: [30.5375, 114.3255], zoom: 15, aliases: ['中南商圈', '中南'] },
  { name: '徐东大街', category: '商圈', coords: [30.5870, 114.3600], zoom: 15, aliases: ['徐东'] },
  { name: '王家湾', category: '商圈', coords: [30.5480, 114.2060], zoom: 15, aliases: [] },
  { name: '钟家村', category: '商圈', coords: [30.5510, 114.2610], zoom: 15, aliases: [] },
  { name: '汉正街', category: '商圈', coords: [30.5730, 114.2790], zoom: 15, aliases: [] },
  { name: '武汉天地', category: '商圈', coords: [30.6050, 114.3110], zoom: 15, aliases: [] },
  { name: '循礼门', category: '商圈', coords: [30.5900, 114.2900], zoom: 15, aliases: [] },
  { name: '汉口金融街', category: '商圈', coords: [30.5980, 114.2860], zoom: 15, aliases: ['建设大道'] },

  // ── 地标 / 景点 / 院校 ──
  { name: '黄鹤楼', category: '地标', coords: [30.5450, 114.3040], zoom: 16, aliases: [] },
  { name: '武汉大学', category: '地标', coords: [30.5390, 114.3640], zoom: 15, aliases: ['武大', '珞珈山'] },
  { name: '华中科技大学', category: '地标', coords: [30.5130, 114.4200], zoom: 15, aliases: ['华科', '华工'] },
  { name: '华中师范大学', category: '地标', coords: [30.5200, 114.3650], zoom: 15, aliases: ['华师'] },
  { name: '湖北省博物馆', category: '地标', coords: [30.5620, 114.3630], zoom: 16, aliases: ['省博'] },
  { name: '沙湖公园', category: '地标', coords: [30.5750, 114.3320], zoom: 15, aliases: ['沙湖'] },
  { name: '东湖听涛景区', category: '地标', coords: [30.5680, 114.3720], zoom: 14, aliases: ['东湖', '东湖景区'] },
  { name: '归元寺', category: '地标', coords: [30.5528, 114.2580], zoom: 16, aliases: [] },
  { name: '晴川阁', category: '地标', coords: [30.5630, 114.2870], zoom: 16, aliases: [] },
  { name: '中山公园', category: '地标', coords: [30.5850, 114.2720], zoom: 16, aliases: [] },
  { name: '解放公园', category: '地标', coords: [30.6000, 114.3000], zoom: 16, aliases: [] },
  { name: '汉口江滩', category: '地标', coords: [30.6000, 114.3010], zoom: 15, aliases: ['江滩'] },
  { name: '户部巷', category: '地标', coords: [30.5450, 114.3050], zoom: 16, aliases: [] },

  // ── 交通枢纽 ──
  { name: '武昌火车站', category: '枢纽', coords: [30.5340, 114.3170], zoom: 15, aliases: ['武昌站'] },
  { name: '汉口火车站', category: '枢纽', coords: [30.6180, 114.2540], zoom: 15, aliases: ['汉口站'] },
  { name: '武汉火车站', category: '枢纽', coords: [30.6080, 114.4230], zoom: 15, aliases: ['武汉站', '青山高铁站'] }
]

/** 类别筛选标签，顺序即下拉里标签的出现顺序 */
export const placeCategories = ['片区', '行政区', '商圈', '地标', '枢纽', '卡口']
