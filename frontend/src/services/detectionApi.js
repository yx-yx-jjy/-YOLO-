import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 30_000 })

export async function getInferenceHealth() {
  const { data } = await api.get('/health', { timeout: 4000 })
  return data
}

export async function createDetection(file, onProgress) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/detections', form, {
    timeout: 10 * 60_000,
    onUploadProgress(event) {
      if (event.total && onProgress) onProgress(Math.round(event.loaded / event.total * 100))
    }
  })
  return data
}

export async function getDetection(jobId) {
  const { data } = await api.get(`/detections/${jobId}`)
  return data
}

export async function getCameraStatus(camId = 'CAM-04') {
  const { data } = await api.get(`/camera/status?cam_id=${camId}`)
  return data
}

export async function triggerCameraSnapshot(camId = 'CAM-04') {
  const { data } = await api.post(`/camera/snapshot?cam_id=${camId}`)
  return data
}

export async function getCameraViolations() {
  const { data } = await api.get('/camera/violations')
  return data
}

export function getCameraStreamUrl(camId = 'CAM-04', showHelmet = true) {
  return `/api/camera/stream?cam_id=${camId}&show_helmet=${showHelmet}`
}

export function getApiErrorMessage(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  if (error?.code === 'ERR_NETWORK') return '无法连接推理服务，请确认后端已启动'
  return error?.message || '检测请求失败'
}

