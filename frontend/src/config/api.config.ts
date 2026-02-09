import axios from 'axios'

// export const API_BASE = 'https://edu.armtick.am'
export const API_BASE = 'http://localhost:8000'

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
