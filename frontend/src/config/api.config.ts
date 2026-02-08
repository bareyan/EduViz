import axios from 'axios'

export const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '/api'

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

export default api
