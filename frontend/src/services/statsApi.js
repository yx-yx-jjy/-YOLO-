// 汇总统计（Stats）接口封装
// 契约见 deliverables/db-migration/01-改造架构方案.md §4.2

import { http, cleanParams } from './http'

/** 概览：{ date, total, status:{pending,approved,rejected}, disposition:{...}, review_rate, disposition_rate, low_confidence, avg_confidence, generated_at } */
export async function fetchOverview(date) {
  const { data } = await http.get('/stats/overview', { params: cleanParams({ date }) })
  return data
}

/** 时序：{ bucket, keys, series:[{ name, data:[] }] } */
export async function fetchTimeseries({ bucket = 'hour', range = '24h', camera_id = 'ALL' } = {}) {
  const { data } = await http.get('/stats/timeseries', {
    params: cleanParams({ bucket, range, camera_id })
  })
  return data
}

/** 按卡口：{ items:[{ camera_id, name, total, no_helmet, avg_confidence, last_capture_time }] } */
export async function fetchByCamera(range = '24h') {
  const { data } = await http.get('/stats/by-camera', { params: cleanParams({ range }) })
  return data
}

/** 预测：{ history:{keys,values}, forecast:{keys,values} } */
export async function fetchForecast(camera_id) {
  const { data } = await http.get('/stats/forecast', { params: cleanParams({ camera_id }) })
  return data
}
