import axios from 'axios'

export const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '/api'

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add CORS headers for production
if (!import.meta.env.DEV) {
  api.defaults.headers.common['Access-Control-Allow-Origin'] = '*'
}

export default api
