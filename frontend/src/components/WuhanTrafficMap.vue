<template>
  <div
    class="traffic-map-shell"
    :class="[`basemap-${basemap}`, { 'is-overview': zoomLevel <= 12, 'search-open': searchOpen }]"
  >
    <div ref="mapContainer" class="traffic-map" aria-label="武汉市真实道路地图"></div>

    <!-- ── 地点检索：定位区域 / 商圈 / 卡口 ── -->
    <div class="map-search" :class="{ 'is-open': searchOpen }">
      <div class="map-search__field">
        <svg class="map-search__icon" viewBox="0 0 16 16" aria-hidden="true">
          <circle cx="7" cy="7" r="4.6" fill="none" stroke="currentColor" stroke-width="1.5" />
          <path d="M10.5 10.5 L14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        </svg>
        <input
          ref="searchInput"
          class="map-search__input"
          type="text"
          autocomplete="off"
          placeholder="搜索区域 / 商圈 / 卡口"
          aria-label="搜索区域、商圈或卡口"
          :value="searchKeyword"
          @input="onSearchInput"
          @focus="searchOpen = true"
          @keydown.enter.prevent="confirmSearch"
          @keydown.down.prevent="moveActive(1)"
          @keydown.up.prevent="moveActive(-1)"
          @keydown.esc="closeSearch"
        />
        <button
          v-if="searchKeyword"
          type="button"
          class="map-search__clear"
          aria-label="清空搜索"
          @click="clearSearch"
        >×</button>
      </div>

      <ul v-if="searchOpen && searchResults.length" class="map-search__list" role="listbox">
        <li
          v-for="(place, index) in searchResults"
          :key="place.key"
          class="map-search__item"
          :class="[`cat-${place.category}`, { 'is-active': index === activeResultIndex }]"
          role="option"
          :aria-selected="String(index === activeResultIndex)"
          @mouseenter="activeResultIndex = index"
          @click="applyPlace(place)"
        >
          <span class="map-search__name">{{ place.name }}</span>
          <span class="map-search__cat">{{ place.category }}</span>
          <span v-if="place.nearbyCount" class="map-search__meta">{{ place.nearbyCount }} 个卡口</span>
        </li>
      </ul>

      <div v-else-if="searchOpen && searchKeyword.trim()" class="map-search__empty">
        未收录「{{ searchKeyword.trim() }}」，可试 光谷 / 汉街 / 江汉路 / 中山公园
      </div>
    </div>

    <!-- ── 区域状况概览：搜到一片区域后，直接把该范围的卡口态势摊开 ── -->
    <div v-if="regionSummary" class="region-card">
      <div class="region-card__head">
        <span class="region-card__name">{{ regionSummary.place.name }}</span>
        <span class="region-card__cat">{{ regionSummary.place.category }}</span>
        <button type="button" class="region-card__close" aria-label="关闭区域概览" @click="regionSummary = null">×</button>
      </div>

      <p class="region-card__stat">
        半径 {{ regionSummary.radiusKm }} km 内布控卡口 <strong>{{ regionSummary.cameras.length }}</strong> 个 ·
        今日抓拍合计 <strong>{{ regionSummary.total }}</strong> 起
      </p>

      <ul v-if="regionSummary.cameras.length" class="region-card__list">
        <li v-for="camera in regionSummary.cameras" :key="camera.id" @click="focusCameraById(camera.id)">
          <i class="region-card__dot" :style="{ backgroundColor: levelStyles[camera.level].fill }"></i>
          <span class="region-card__id">{{ camera.id }}</span>
          <span class="region-card__label">{{ camera.name }}</span>
          <strong class="region-card__count">{{ camera.count }}起</strong>
        </li>
      </ul>
      <p v-else class="region-card__empty">该范围内暂无布控卡口</p>
    </div>

    <!-- ── 右上角：底图样式切换 + 数据来源 ── -->
    <div class="map-toolbar">
      <div class="basemap-switch" role="group" aria-label="底图样式">
        <button
          v-for="option in basemapOptions"
          :key="option.key"
          type="button"
          class="basemap-switch__btn"
          :class="{ 'is-active': basemap === option.key }"
          :aria-pressed="String(basemap === option.key)"
          @click="selectBasemap(option.key)"
        >
          {{ option.label }}
        </button>
      </div>
      <span class="map-source">
        <i class="source-dot"></i>
        高德地图 · 真实路网
      </span>
    </div>

    <div v-if="tileLoadError" class="map-error">
      地图瓦片加载失败，请检查网络连接
    </div>

    <div v-if="activeLayer !== 'cams'" class="heat-legend">
      <span class="legend-title">热力密度</span>
      <span v-for="item in heatLegend" :key="item.label" class="legend-item">
        <i :style="{ backgroundColor: item.color }"></i>
        {{ item.label }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { wuhanPlaces } from '../data/wuhanPlaces'
import { CAMERAS, levelOf, cameraKey } from '../data/cameras'
import { useViolationStore } from '../stores/violations'

const props = defineProps({
  activeLayer: {
    type: String,
    default: 'all'
  },
  activeCam: {
    type: String,
    default: 'ALL'
  },
  // 'vivid' = 高德原色底图；'blend' = 降噪压暗后融入大屏（默认）；'dark' = 深色科技风底图
  basemap: {
    type: String,
    default: 'blend'
  }
})

const emit = defineEmits(['update:activeCam', 'update:basemap'])

const basemapOptions = [
  { key: 'vivid', label: '原色' },
  { key: 'blend', label: '融合' },
  { key: 'dark', label: '深色' }
]

function selectBasemap(key) {
  if (props.basemap !== key) emit('update:basemap', key)
}

const mapContainer = ref(null)
const tileLoadError = ref(false)
const zoomLevel = ref(12)

const WUHAN_CENTER_WGS84 = [30.5736, 114.3054]
const WUHAN_BOUNDS_WGS84 = [
  [30.489, 114.185],
  [30.635, 114.435]
]

// Source coordinates are WGS84; they are converted to GCJ-02 for the AMap tiles.
// 卡口主数据与"今日抓拍量"统一取自 data/cameras + 台账 ——
// 之前这里写死 142/96/74/52/38，会和同屏的 TOP5 排名、研判页各自对不上。
// 计数口径统一为"今日"，与地图气泡/弹窗上的「今日抓拍」文案、以及同屏 TOP5 保持一致。
const violationStore = useViolationStore()

// 计数改走后端聚合接口 /api/stats/by-camera（近 24h），不再依赖"当前页"记录：
// 服务端分页后 records 只是某一页，用它统计会得到错误的小数字。
const cameras = computed(() => {
  const counts = new Map()
  for (const item of violationStore.byCamera || []) {
    const key = cameraKey(item.camera_id)
    counts.set(key, (counts.get(key) || 0) + (item.total || 0))
  }
  return CAMERAS.map(cam => {
    const count = counts.get(cam.id) || 0
    return { ...cam, count, level: levelOf(count) }
  })
})

const levelStyles = {
  high: { color: '#fb7185', fill: '#e11d48', symbol: '!', label: '高危' },
  medium: { color: '#fbbf24', fill: '#d97706', symbol: '▲', label: '中危' },
  low: { color: '#34d399', fill: '#059669', symbol: '✓', label: '低危' }
}

// 浅色真实底图上，热力色阶改用与地图本身（水系蓝 / 绿地绿 / 干道黄）区分度更高的暖色递进
const heatLegend = [
  { label: '低危', color: '#1FA97F' },
  { label: '中危', color: '#E8890C' },
  { label: '高危集中', color: '#DC2F3F' }
]

let map = null
let tileLayer = null
let markerLayer = null
let heatLayer = null
let resizeObserver = null
let hasFitted = false
let tileErrorCount = 0
const markerById = new Map()

/* ── 地点检索 ───────────────────────────────────────────── */

const searchInput = ref(null)
const searchKeyword = ref('')
const searchOpen = ref(false)
const activeResultIndex = ref(0)
const regionSummary = ref(null)

// 概览半径：3km 大致覆盖一个街道办的布控范围，再大就会把不相干卡口也算进来
const SEARCH_RADIUS_KM = 3

function distanceKm([lat1, lng1], [lat2, lng2]) {
  const toRad = deg => deg * Math.PI / 180
  const earthRadius = 6371
  const deltaLat = toRad(lat2 - lat1)
  const deltaLng = toRad(lng2 - lng1)
  const a = Math.sin(deltaLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(deltaLng / 2) ** 2
  return 2 * earthRadius * Math.asin(Math.min(1, Math.sqrt(a)))
}

function camerasNear(coords) {
  return cameras.value
    .map(camera => ({ ...camera, distance: distanceKm(coords, camera.coords) }))
    .filter(camera => camera.distance <= SEARCH_RADIUS_KM)
    .sort((a, b) => a.distance - b.distance)
}

// 卡口本身也能被检索到：搜「光谷」既会出现商圈，也能直接跳到 CAM-01
const searchablePlaces = computed(() => [
  ...wuhanPlaces.map(place => ({
    key: `place-${place.name}`,
    name: place.name,
    category: place.category,
    coords: place.coords,
    zoom: place.zoom,
    aliases: place.aliases || [],
    camId: null
  })),
  ...cameras.value.map(camera => ({
    key: `cam-${camera.id}`,
    name: `${camera.name}（${camera.id}）`,
    category: '卡口',
    coords: camera.coords,
    zoom: 15,
    aliases: [camera.id, camera.area, camera.name],
    camId: camera.id
  }))
])

function scorePlace(place, query) {
  const name = place.name.toLowerCase()
  if (name === query) return 120
  if (name.startsWith(query)) return 100
  if (name.includes(query)) return 80
  if (place.aliases.some(alias => alias.toLowerCase() === query)) return 70
  if (place.aliases.some(alias => alias.toLowerCase().includes(query))) return 55
  return 0
}

const searchResults = computed(() => {
  const query = searchKeyword.value.trim().toLowerCase()
  if (!query) return []

  return searchablePlaces.value
    .map(place => ({ place, score: scorePlace(place, query) }))
    .filter(item => item.score > 0)
    .sort((a, b) => b.score - a.score || a.place.name.length - b.place.name.length)
    .slice(0, 7)
    .map(({ place }) => ({ ...place, nearbyCount: camerasNear(place.coords).length }))
})

function onSearchInput(event) {
  searchKeyword.value = event.target.value
  activeResultIndex.value = 0
  searchOpen.value = true
}

function moveActive(step) {
  const total = searchResults.value.length
  if (!total) return
  searchOpen.value = true
  activeResultIndex.value = (activeResultIndex.value + step + total) % total
}

function closeSearch() {
  searchOpen.value = false
}

function clearSearch() {
  searchKeyword.value = ''
  regionSummary.value = null
  searchOpen.value = false
  activeResultIndex.value = 0
  searchInput.value?.focus()
}

function buildRegionSummary(place) {
  const nearby = camerasNear(place.coords)
  regionSummary.value = {
    place,
    radiusKm: SEARCH_RADIUS_KM,
    cameras: nearby,
    total: nearby.reduce((sum, camera) => sum + camera.count, 0)
  }
}

function applyPlace(place) {
  searchKeyword.value = place.name
  searchOpen.value = false
  activeResultIndex.value = 0
  searchInput.value?.blur()

  if (place.camId) {
    // 卡口条目走父组件的选中联动，复用 focusCamera 的飞行 + 弹窗流程
    emit('update:activeCam', place.camId)
  } else if (map) {
    map.closePopup()
    map.flyTo(wgs84ToGcj02(place.coords), place.zoom || 14, { duration: 0.8 })
  }

  buildRegionSummary(place)
}

function confirmSearch() {
  const place = searchResults.value[activeResultIndex.value]
  if (place) applyPlace(place)
}

function focusCameraById(cameraId) {
  emit('update:activeCam', cameraId)
}

/* ── 坐标与地图 ─────────────────────────────────────────── */

const PI = Math.PI
const GCJ_A = 6378245.0
const GCJ_EE = 0.006693421622965943

function transformLatitude(longitude, latitude) {
  let value = -100 + 2 * longitude + 3 * latitude + 0.2 * latitude * latitude
  value += 0.1 * longitude * latitude + 0.2 * Math.sqrt(Math.abs(longitude))
  value += (20 * Math.sin(6 * longitude * PI) + 20 * Math.sin(2 * longitude * PI)) * 2 / 3
  value += (20 * Math.sin(latitude * PI) + 40 * Math.sin(latitude / 3 * PI)) * 2 / 3
  value += (160 * Math.sin(latitude / 12 * PI) + 320 * Math.sin(latitude * PI / 30)) * 2 / 3
  return value
}

function transformLongitude(longitude, latitude) {
  let value = 300 + longitude + 2 * latitude + 0.1 * longitude * longitude
  value += 0.1 * longitude * latitude + 0.1 * Math.sqrt(Math.abs(longitude))
  value += (20 * Math.sin(6 * longitude * PI) + 20 * Math.sin(2 * longitude * PI)) * 2 / 3
  value += (20 * Math.sin(longitude * PI) + 40 * Math.sin(longitude / 3 * PI)) * 2 / 3
  value += (150 * Math.sin(longitude / 12 * PI) + 300 * Math.sin(longitude / 30 * PI)) * 2 / 3
  return value
}

function wgs84ToGcj02([latitude, longitude]) {
  const latitudeOffset = transformLatitude(longitude - 105, latitude - 35)
  const longitudeOffset = transformLongitude(longitude - 105, latitude - 35)
  const radianLatitude = latitude / 180 * PI
  let magic = Math.sin(radianLatitude)
  magic = 1 - GCJ_EE * magic * magic
  const sqrtMagic = Math.sqrt(magic)
  const adjustedLatitude = latitudeOffset * 180 / ((GCJ_A * (1 - GCJ_EE)) / (magic * sqrtMagic) * PI)
  const adjustedLongitude = longitudeOffset * 180 / (GCJ_A / sqrtMagic * Math.cos(radianLatitude) * PI)
  return [latitude + adjustedLatitude, longitude + adjustedLongitude]
}

const WUHAN_CENTER = wgs84ToGcj02(WUHAN_CENTER_WGS84)
const WUHAN_BOUNDS = L.latLngBounds(
  wgs84ToGcj02(WUHAN_BOUNDS_WGS84[0]),
  wgs84ToGcj02(WUHAN_BOUNDS_WGS84[1])
)

// 拖拽/缩放的硬边界：只允许在武汉都市圈范围内活动，避免画面跑到长沙或整个湖北省
const WUHAN_MAX_BOUNDS = L.latLngBounds(
  wgs84ToGcj02([30.28, 113.82]),
  wgs84ToGcj02([30.94, 114.84])
)

function cameraMapCoords(camera) {
  return wgs84ToGcj02(camera.coords)
}

function makeMarkerIcon(camera) {
  const style = levelStyles[camera.level]
  return L.divIcon({
    className: 'traffic-camera-icon',
    iconSize: [190, 46],
    iconAnchor: [18, 18],
    popupAnchor: [0, -16],
    html: `
      <div class="camera-marker camera-marker--${camera.level}">
        <div class="camera-marker__pin" style="--marker-color:${style.fill};--marker-border:${style.color}">
          <span>${style.symbol}</span>
        </div>
        <div class="camera-marker__label" style="--marker-border:${style.color}">
          <span class="camera-marker__label-full">${camera.id} · ${camera.name}</span>
          <span class="camera-marker__label-short">${camera.id}</span>
          <strong style="background:${style.fill}">${camera.count}起</strong>
        </div>
      </div>
    `
  })
}

function createPopup(camera) {
  const style = levelStyles[camera.level]
  const mapCoords = cameraMapCoords(camera)
  return `
    <div class="camera-popup">
      <div class="camera-popup__title">${camera.name}</div>
      <div class="camera-popup__meta">${camera.id} · ${camera.area}</div>
      <div>今日抓拍 <strong>${camera.count}</strong> 起 · ${style.label}</div>
      <div class="camera-popup__coords">GCJ-02 ${mapCoords[0].toFixed(6)}, ${mapCoords[1].toFixed(6)}</div>
    </div>
  `
}

function buildMarkers() {
  markerLayer = L.layerGroup()
  markerById.clear()

  cameras.value.forEach(camera => {
    const marker = L.marker(cameraMapCoords(camera), {
      icon: makeMarkerIcon(camera),
      riseOnHover: true,
      title: `${camera.id} ${camera.name}`
    })
      .bindPopup(createPopup(camera), {
        className: 'traffic-map-popup',
        closeButton: false,
        offset: [0, -4]
      })
      .on('click', () => emit('update:activeCam', camera.id))

    markerById.set(camera.id, marker)
    markerLayer.addLayer(marker)
  })
}

// 每个卡口只产生一个热力点，强度 = (该卡口今日起数 / 最大起数) ^ HEAT_GAMMA。
//
// ⚠️ 为什么不做"多环散布"（曾经的实现，已废弃）：leaflet.heat 在绘制前会先按
//    r/2 的网格，把落进同一格的点做「加权合并」（HeatLayer.js:157-164，
//    cell[2] += k 即强度求和）。原先每个卡口铺 3 环共 76 个采样点，合并后
//    单点强度可达 15~20，而 max 只有 3 —— 于是每个卡口都被顶到色阶最顶端，
//    颜色完全无法区分计数：热力图实际只是画了 5 个一样红的圆，对比度为零，
//    且 0 起的卡口（采样权重被 Math.max(0.1, …) 兜底）同样有热力。
//    改为「每卡口一个点」后不存在跨点合并，强度与 count 严格成正比，
//    色阶才真正表达数据。
const HEAT_GAMMA = 0.6

function heatSamples() {
  const maxCount = Math.max(1, ...cameras.value.map(item => item.count))
  const points = []

  cameras.value.forEach(camera => {
    if (!(camera.count > 0)) return        // 0 起 = 无热力，不铺点
    const [latitude, longitude] = cameraMapCoords(camera)
    // γ < 1 用于抬升低计数档，使 1327 / 350 / 211 这类量级差在色阶上拉开
    const intensity = Math.pow(camera.count / maxCount, HEAT_GAMMA)
    points.push([latitude, longitude, intensity])
  })

  return points
}

function buildHeatZones() {
  heatLayer = L.heatLayer(heatSamples(), {
    radius: 28,
    blur: 26,
    // 注意：leaflet.heat 的 maxZoom 不是"最大缩放级别"，而是"强度满值对应的缩放级别"。
    // 插件内部会算 v = 1 / 2^clamp(maxZoom - 当前zoom, 0, 12) 再乘到每个点的强度上
    // （HeatLayer.js:134），zoom ≥ maxZoom 时 v = 1。大屏固定在 z11~13，
    // 取 11 可让这三个缩放级都落在 v = 1，颜色不随缩放漂移。
    maxZoom: 11,
    // 低计数档的最低可见度：否则 211 起那档会淡到几乎看不见
    minOpacity: 0.3,
    // 单点方案下每点强度 ≤ 1，max 取 1 即让最高卡口正好落在色阶顶端
    max: 1,
    gradient: {
      0.12: '#1FA97F',
      0.48: '#E8890C',
      0.80: '#DC2F3F'
    }
  })
}

function updateVisibleLayers() {
  if (!map || !markerLayer || !heatLayer) return

  const showMarkers = props.activeLayer === 'all' || props.activeLayer === 'cams'
  const showHeat = props.activeLayer === 'all' || props.activeLayer === 'heatmap'

  if (showMarkers && !map.hasLayer(markerLayer)) markerLayer.addTo(map)
  if (!showMarkers && map.hasLayer(markerLayer)) map.removeLayer(markerLayer)
  if (showHeat && !map.hasLayer(heatLayer)) heatLayer.addTo(map)
  if (!showHeat && map.hasLayer(heatLayer)) map.removeLayer(heatLayer)

  if (showMarkers) markerLayer.bringToFront?.()
}

function focusCamera(cameraId, animate = true) {
  if (!map) return

  if (cameraId === 'ALL') {
    map.fitBounds(WUHAN_BOUNDS, { padding: [22, 22], animate })
    map.closePopup()
    return
  }

  const camera = cameras.value.find(item => item.id === cameraId)
  if (!camera) return

  map.flyTo(cameraMapCoords(camera), 15, { animate, duration: 0.75 })
  if (props.activeLayer !== 'heatmap') {
    window.setTimeout(() => markerById.get(cameraId)?.openPopup(), animate ? 760 : 0)
  }
}

function initMap() {
  if (!mapContainer.value) return

  map = L.map(mapContainer.value, {
    center: WUHAN_CENTER,
    zoom: 12,
    minZoom: 11,
    maxZoom: 18,
    zoomControl: true,
    attributionControl: true,
    preferCanvas: true,
    maxBounds: WUHAN_MAX_BOUNDS,
    maxBoundsViscosity: 0.85
  })
  zoomLevel.value = map.getZoom()
  map.on('zoomend', () => {
    zoomLevel.value = map.getZoom()
  })
  // 点空白处收起候选，避免下拉一直悬在地图上
  map.on('click', () => {
    searchOpen.value = false
  })

  tileLayer = L.tileLayer('https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}', {
    maxZoom: 18,
    subdomains: ['1', '2', '3', '4'],
    attribution: '&copy; 高德地图',
    crossOrigin: true
  })
    .on('loading', () => {
      tileErrorCount = 0
      tileLoadError.value = false
    })
    .on('tileerror', () => {
      // 单块瓦片偶发失败（网络抖动、边缘瓦片）不该整块地图报警，累计到阈值再提示
      tileErrorCount += 1
      if (tileErrorCount >= 6) tileLoadError.value = true
    })
    .addTo(map)

  buildMarkers()
  buildHeatZones()
  updateVisibleLayers()

  // 关键修复：此刻容器往往还没量到真实高度，直接 fitBounds 会按错误尺寸算出过小的
  // 缩放级别（画面会漏出孝感、黄冈甚至整个都市圈）。先 invalidateSize，等一帧再定视野。
  map.invalidateSize(false)
  requestAnimationFrame(() => {
    if (!map) return
    map.invalidateSize(false)
    focusCamera(props.activeCam, false)
    hasFitted = true
  })

  resizeObserver = new ResizeObserver(() => {
    if (!map) return
    map.invalidateSize({ pan: false })
    if (!hasFitted) {
      focusCamera('ALL', false)
      hasFitted = true
    }
  })
  resizeObserver.observe(mapContainer.value)
}

// 卡口计数是异步取回的：拿到 by-camera 聚合后再重建覆盖物，
// 否则标记会停在初始的 "0起"。重建只在数据变化时触发，不影响视野交互。
function rebuildOverlays() {
  if (!map) return
  if (markerLayer) map.removeLayer(markerLayer)
  if (heatLayer) map.removeLayer(heatLayer)
  buildMarkers()
  buildHeatZones()
  updateVisibleLayers()
}

watch(() => props.activeLayer, updateVisibleLayers)
watch(() => props.activeCam, value => focusCamera(value))
watch(cameras, rebuildOverlays)

// leaflet.heat 是 UMD 插件，运行时依赖全局 L，必须先挂到 window 上再动态引入
async function ensureHeatPlugin() {
  if (typeof L.heatLayer === 'function') return
  window.L = L
  await import('leaflet.heat')
}

onMounted(async () => {
  // 卡口计数来自后端聚合；失败时按 0 渲染（地图仍可用，不阻塞底图）
  violationStore.fetchByCamera('24h')
  await ensureHeatPlugin()
  await nextTick()
  initMap()
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  tileLayer?.off()
  map?.remove()
  map = null
})
</script>

<style>
/* ─────────────────────────────────────────────────────────────
   底图与覆盖物都做成设计变量：切换 basemap 时只换一组 token，
   覆盖物（标记 / 图例 / 缩放控件 / 弹窗）随之整体切换配色，
   不会出现"浅底图配深色标签"这种读不清的组合。
   ───────────────────────────────────────────────────────────── */
.traffic-map-shell {
  /* 容器底色取大屏卡片同色：让地图落在与大屏同一个深色基调上 */
  --map-canvas-bg: #0A1224;
  /* 降噪而非反相：降饱和 + 等比例压暗 + 色相微偏青。
     注意这里刻意不用 opacity —— 透明度是把瓦片与深色底做线性混合，
     浅底与深字会被一起拉到中灰，地名糊掉、整张图发闷。
     brightness 是等比例缩放，压暗的同时保住明暗比值，路名依然读得清。 */
  --tile-filter: saturate(.42) brightness(.54) contrast(1.14) hue-rotate(-8deg);
  --tile-opacity: 1;
  /* 蒙层：极淡的冷蓝，把高德偏暖的米色底拉向大屏的冷调；
     强度必须低，再高就会重蹈 opacity 的覆辙——把明暗一起压平、地名发糊。 */
  --map-tint: rgba(10, 18, 46, 0.24);
  /* 内暗角：把地图四边"沉"进大屏底色，它不再是一块方正的亮补丁，
     而像一块嵌进操作台的屏幕。z-index 夹在 tilePane(200) 与 markerPane(600) 之间，
     只压底图与热力，不碰卡口标记和弹窗。 */
  --map-vignette: inset 0 0 52px 14px rgba(7, 12, 24, 0.78);

  --overlay-bg: rgba(255, 255, 255, 0.94);
  --overlay-border: rgba(15, 23, 42, 0.12);
  --overlay-text: #334155;
  --overlay-text-dim: #64748B;
  --overlay-shadow: 0 2px 8px rgba(15, 23, 42, 0.14);
  --heat-opacity: 1;

  --marker-label-bg: rgba(255, 255, 255, 0.97);
  --marker-label-text: #0F172A;
  --marker-label-shadow: 0 2px 7px rgba(15, 23, 42, 0.2);
  --marker-pin-ring: #FFFFFF;
  --marker-pin-shadow: 0 2px 6px rgba(15, 23, 42, 0.3);

  --popup-bg: #FFFFFF;
  --popup-border: rgba(15, 23, 42, 0.12);
  --popup-text: #334155;
  --popup-title: #0F172A;

  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--map-canvas-bg);
  transition: background-color 220ms ease;
}

/* 原色底图：高德原始配色，不做任何处理。
   最真实，但也是画面里最亮最抢眼的一块 —— 适合需要"看清水系、绿地、POI"的场景。 */
.traffic-map-shell.basemap-vivid {
  --tile-filter: none;
  --map-tint: transparent;
  --map-vignette: inset 0 0 40px 10px rgba(7, 12, 24, 0.42);
}

/* 暗色底图：完整保留原有科技风取色方案 */
.traffic-map-shell.basemap-dark {
  --map-canvas-bg: #07101F;
  /* 去色后反相保留明暗关系：陆地转深、水系与路网骨骼呈中灰、黑色注记转白。
     早先用 invert(1) hue-rotate(180deg) 会把高德的橙黄干道反相成橙红，
     同时把白色支路压成纯黑（与陆地同色）——画面上只剩一张橙色蛛网，水体和支路全部消失。 */
  --tile-filter: grayscale(1) invert(1) sepia(0.55) hue-rotate(178deg) saturate(2.6) brightness(0.92) contrast(1.12);
  --tile-opacity: 1;
  /* 深色底图本身就压得住，暗角只留一点点收边，也不再叠冷色蒙层 */
  --map-tint: transparent;
  --map-vignette: inset 0 0 36px 6px rgba(2, 6, 23, 0.55);

  --overlay-bg: rgba(2, 6, 23, 0.9);
  --overlay-border: rgba(51, 65, 85, 0.92);
  --overlay-text: #CBD5E1;
  --overlay-text-dim: #64748B;
  --overlay-shadow: 0 8px 24px rgba(2, 6, 23, 0.42);
  --heat-opacity: 1;

  --marker-label-bg: rgba(2, 6, 23, 0.94);
  --marker-label-text: #E2E8F0;
  --marker-label-shadow: 0 7px 18px rgba(2, 6, 23, 0.68);
  --marker-pin-ring: rgba(226, 232, 240, 0.92);
  --marker-pin-shadow: 0 0 0 4px color-mix(in srgb, var(--marker-border) 16%, transparent), 0 2px 6px rgba(2, 6, 23, 0.6);

  --popup-bg: rgba(5, 12, 26, 0.96);
  --popup-border: rgba(34, 211, 238, 0.45);
  --popup-text: #CBD5E1;
  --popup-title: #67E8F9;
}

.traffic-map {
  width: 100%;
  height: 100%;
  background: var(--map-canvas-bg);
  transition: background-color 220ms ease;
}

.traffic-map::after {
  position: absolute;
  inset: 0;
  z-index: 300;
  background: var(--map-tint);
  box-shadow: var(--map-vignette);
  content: '';
  pointer-events: none;
}

.traffic-map .leaflet-tile-pane {
  filter: var(--tile-filter);
  opacity: var(--tile-opacity);
  transition: opacity 220ms ease;
}

.traffic-map .leaflet-heatmap-layer {
  opacity: var(--heat-opacity);
}

/* ── 缩放控件（下移，给检索框让位） ── */
.traffic-map .leaflet-control-zoom {
  margin-top: 58px;
  margin-left: 12px;
  border: 1px solid var(--overlay-border);
  border-radius: 6px;
  overflow: hidden;
  box-shadow: var(--overlay-shadow);
  transition: opacity 150ms ease, transform 150ms ease;
}

.traffic-map .leaflet-control-zoom a {
  width: 28px;
  height: 28px;
  line-height: 27px;
  color: var(--overlay-text);
  background: var(--overlay-bg);
  border-color: var(--overlay-border);
  font-weight: 400;
}

.traffic-map .leaflet-control-zoom a:hover {
  color: #0F172A;
  background: rgba(15, 23, 42, 0.08);
}

/* 下拉展开时让缩放控件退场，它和候选列表是同一块位置，留着会透出白块 */
.traffic-map-shell.search-open .leaflet-control-zoom {
  opacity: 0;
  transform: translateX(-8px);
  pointer-events: none;
  transition: opacity 150ms ease, transform 150ms ease;
}

.traffic-map-shell.basemap-dark .leaflet-control-zoom a:hover {
  color: #FFFFFF;
  background: #0E7490;
}

/* ── 版权信息（保留高德署名） ── */
.traffic-map .leaflet-control-attribution {
  color: var(--overlay-text-dim);
  background: rgba(7, 12, 24, 0.55);
  border-top-left-radius: 4px;
  font-size: 11px;
  padding: 0 4px;
}

.traffic-map .leaflet-control-attribution a {
  color: #CBD5E1;
}

/* ── 卡口标记 ── */
.traffic-camera-icon {
  background: transparent;
  border: 0;
}

.camera-marker {
  display: flex;
  align-items: flex-start;
  width: 190px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: var(--marker-label-text);
}

.camera-marker__pin {
  position: relative;
  z-index: 2;
  display: grid;
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  place-items: center;
  border: 1.5px solid var(--marker-pin-ring);
  border-radius: 50%;
  color: #ffffff;
  background: var(--marker-color);
  box-shadow: var(--marker-pin-shadow);
  font-size: 11px;
  font-weight: 700;
}

.camera-marker--high .camera-marker__pin::after,
.camera-marker--medium .camera-marker__pin::after {
  position: absolute;
  inset: -8px;
  border: 1px solid var(--marker-border);
  border-radius: 50%;
  content: '';
  animation: camera-pulse 1.8s ease-out infinite;
}

.camera-marker__label {
  display: flex;
  align-items: center;
  min-height: 24px;
  margin: 18px 0 0 -7px;
  padding: 3px 4px 3px 9px;
  border: 1px solid var(--marker-border);
  border-radius: 4px;
  background: var(--marker-label-bg);
  box-shadow: var(--marker-label-shadow);
  color: var(--marker-label-text);
  font-size: 11px;
  line-height: 17px;
  white-space: nowrap;
  transition: opacity 160ms ease, transform 160ms ease;
}

.camera-marker__label-short {
  display: none;
}

/* 总览级别（zoom <= 12）也要看得见卡口，大屏的意义就是"一眼看出哪个路口最严重"。
   只收起详细路名，保留编号与起数，而不是把整块标签藏掉。 */
.traffic-map-shell.is-overview .camera-marker__label-full {
  display: none;
}

.traffic-map-shell.is-overview .camera-marker__label-short {
  display: inline;
}

.camera-marker__label strong {
  margin-left: 5px;
  padding: 0 4px;
  border-radius: 3px;
  color: #ffffff;
  font-size: 11px;
}

/* ── 地点检索 ── */
.map-search {
  position: absolute;
  top: 12px;
  left: 12px;
  /* 必须高过 Leaflet 的 .leaflet-top（z-index 1000），否则缩放控件会压在下拉列表上 */
  z-index: 1100;
  width: 236px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.map-search__field {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--overlay-border);
  border-radius: 8px;
  background: var(--overlay-bg);
  box-shadow: var(--overlay-shadow);
  backdrop-filter: blur(6px);
  transition: border-color 150ms ease, box-shadow 150ms ease;
}

.map-search.is-open .map-search__field {
  border-color: #06B6D4;
  box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.18), var(--overlay-shadow);
}

.map-search__icon {
  width: 14px;
  height: 14px;
  flex: 0 0 14px;
  color: var(--overlay-text-dim);
}

.map-search__input {
  width: 100%;
  border: 0;
  outline: none;
  background: transparent;
  color: #0F172A;
  font: inherit;
  font-size: 12px;
  line-height: 1;
}

.map-search__input::placeholder {
  color: #94A3B8;
}

.map-search__clear {
  width: 16px;
  height: 16px;
  flex: 0 0 16px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: #E2E8F0;
  color: #475569;
  font-size: 13px;
  line-height: 15px;
  cursor: pointer;
}

.map-search__clear:hover {
  background: #CBD5E1;
  color: #0F172A;
}

.map-search__list {
  margin: 4px 0 0;
  padding: 4px;
  list-style: none;
  border: 1px solid var(--overlay-border);
  border-radius: 8px;
  background: var(--overlay-bg);
  box-shadow: var(--overlay-shadow);
  backdrop-filter: blur(6px);
  max-height: 246px;
  overflow-y: auto;
}

.map-search__item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 6px 5px 8px;
  border-left: 2px solid transparent;
  border-radius: 5px;
  cursor: pointer;
  font-size: 12px;
  color: #0F172A;
}

.map-search__item.is-active {
  background: rgba(6, 182, 212, 0.12);
}

.map-search__item.cat-卡口 {
  border-left-color: #DC2F3F;
}

.map-search__name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.map-search__cat {
  flex: 0 0 auto;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(15, 23, 42, 0.07);
  color: #64748B;
  font-size: 11px;
}

.map-search__meta {
  flex: 0 0 auto;
  color: #0F6E56;
  font-size: 11px;
}

.map-search__empty {
  margin-top: 4px;
  padding: 8px 10px;
  border: 1px solid var(--overlay-border);
  border-radius: 8px;
  background: var(--overlay-bg);
  box-shadow: var(--overlay-shadow);
  color: #64748B;
  font-size: 11px;
  line-height: 1.6;
}

/* ── 区域状况概览 ── */
.region-card {
  position: absolute;
  bottom: 56px;
  left: 12px;
  z-index: 600;
  width: 268px;
  padding: 9px 10px 8px;
  border: 1px solid var(--overlay-border);
  border-radius: 10px;
  background: var(--overlay-bg);
  box-shadow: var(--overlay-shadow);
  backdrop-filter: blur(6px);
  color: #0F172A;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.region-card__head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.region-card__name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 500;
}

.region-card__cat {
  flex: 0 0 auto;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(15, 23, 42, 0.07);
  color: #64748B;
  font-size: 11px;
}

.region-card__close {
  width: 16px;
  height: 16px;
  flex: 0 0 16px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #94A3B8;
  font-size: 14px;
  line-height: 14px;
  cursor: pointer;
}

.region-card__close:hover {
  background: #E2E8F0;
  color: #0F172A;
}

.region-card__stat {
  margin: 5px 0 7px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.1);
  color: #475569;
  font-size: 11px;
  line-height: 1.6;
}

.region-card__stat strong {
  color: #B45309;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-weight: 500;
}

.region-card__list {
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: 108px;
  overflow-y: auto;
}

.region-card__list li {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 4px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
}

.region-card__list li:hover {
  background: rgba(6, 182, 212, 0.12);
}

.region-card__dot {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  border-radius: 50%;
}

.region-card__id {
  flex: 0 0 auto;
  color: #64748B;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
}

.region-card__label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #334155;
}

.region-card__count {
  flex: 0 0 auto;
  color: #0F172A;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  font-weight: 500;
}

.region-card__empty {
  margin: 0;
  color: #94A3B8;
  font-size: 11px;
}

/* ── 地图上的浮层控件 ── */
.map-toolbar,
.heat-legend,
.map-error {
  position: absolute;
  z-index: 500;
  border: 1px solid var(--overlay-border);
  background: var(--overlay-bg);
  box-shadow: var(--overlay-shadow);
  color: var(--overlay-text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 11px;
  backdrop-filter: blur(6px);
}

.map-toolbar {
  top: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px;
  border-radius: 8px;
}

.basemap-switch {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.06);
}

.traffic-map-shell.basemap-dark .basemap-switch {
  background: rgba(148, 163, 184, 0.14);
}

.basemap-switch__btn {
  padding: 3px 9px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--overlay-text-dim);
  font: inherit;
  font-size: 11px;
  line-height: 15px;
  cursor: pointer;
  transition: background-color 150ms ease, color 150ms ease;
}

.basemap-switch__btn:hover {
  color: var(--overlay-text);
}

.basemap-switch__btn.is-active {
  background: #FFFFFF;
  color: #0F172A;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.18);
}

.traffic-map-shell.basemap-dark .basemap-switch__btn.is-active {
  background: #0E7490;
  color: #FFFFFF;
  box-shadow: none;
}

.basemap-switch__btn:focus-visible {
  outline: 2px solid #1D4ED8;
  outline-offset: 1px;
}

.map-source {
  display: flex;
  align-items: center;
  gap: 5px;
  padding-right: 6px;
  color: var(--overlay-text-dim);
  white-space: nowrap;
}

.source-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10B981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.75);
}

.heat-legend {
  bottom: 22px;
  left: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 9px;
  border-radius: 6px;
}

.legend-title {
  color: var(--overlay-text-dim);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-item i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.map-error {
  top: 54px;
  right: 12px;
  padding: 5px 8px;
  border-color: rgba(190, 24, 45, 0.5);
  border-radius: 6px;
  color: #FECDD3;
}

/* ── 弹窗 ── */
.traffic-map-popup .leaflet-popup-content-wrapper,
.traffic-map-popup .leaflet-popup-tip {
  color: var(--popup-text);
  background: var(--popup-bg);
}

.traffic-map-popup .leaflet-popup-content-wrapper {
  border: 1px solid var(--popup-border);
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(2, 6, 23, 0.45);
}

.traffic-map-popup .leaflet-popup-content {
  min-width: 178px;
  margin: 10px 12px;
  font-size: 11px;
  line-height: 1.7;
}

.camera-popup__title {
  color: var(--popup-title);
  font-weight: 700;
}

.camera-popup__meta {
  color: var(--overlay-text-dim);
}

.camera-popup strong {
  color: #D97706;
}

.traffic-map-shell.basemap-dark .camera-popup strong {
  color: #FBBF24;
}

.camera-popup__coords {
  color: var(--overlay-text-dim);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
}

.heat-zone {
  filter: drop-shadow(0 0 8px currentColor);
}

@keyframes camera-pulse {
  0% { transform: scale(0.55); opacity: 0.95; }
  100% { transform: scale(1.7); opacity: 0; }
}
</style>
