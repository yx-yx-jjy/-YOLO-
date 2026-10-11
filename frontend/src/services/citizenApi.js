// 公众服务端接口封装
//
// 与台账接口的关键差异：
//   · 台账 /api/ledger/* 是执法侧全量视图，**无鉴权**（答辩演示要连着视频流）
//   · 本文件 /api/citizen/* 是市民个人视图，**必须带令牌**，且按绑定车牌过滤
// 两者语义不同，绝不能混用——否则会让市民看到全站数据。

import { http, cleanParams } from './http'

/** 当前市民绑定车牌名下的违法记录 */
export async function fetchMyRecords() {
  const { data } = await http.get('/citizen/my-records')
  return data
}

/** 当前市民绑定的号牌 */
export async function fetchMyVehicles() {
  const { data } = await http.get('/citizen/my-vehicles')
  return data
}

/** 提交交通违法线索 */
export async function submitPublicReport(payload) {
  const { data } = await http.post('/citizen/reports', payload)
  return data
}

/** 我提交过的线索及核查状态 */
export async function fetchMyReports() {
  const { data } = await http.get('/citizen/my-reports')
  return data
}