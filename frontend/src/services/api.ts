import axios from 'axios'
import type { ScreenerRequest, ScreenerResponse } from '@/types/api'

// Determine API URL based on where the frontend is accessed from
const getApiUrl = () => {
  const hostname = window.location.hostname
  
  // If accessing from localhost, use localhost API
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000'
  }
  
  // If accessing from public IP, use the same IP for API
  return `http://${hostname}:8000`
}

const API_BASE_URL = getApiUrl()

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const stockScreenerApi = {
  screen: async (request: ScreenerRequest): Promise<ScreenerResponse> => {
    const response = await api.post<ScreenerResponse>('/api/v1/screen', request)
    return response.data
  },
  
  screenDatabase: async (request: ScreenerRequest): Promise<ScreenerResponse> => {
    const response = await api.post<ScreenerResponse>('/api/v1/screen/database', request)
    return response.data
  },
}