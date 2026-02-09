import api from '../config/api.config'

export interface AuthResponse {
  authenticated: boolean
  auth_enabled: boolean
  token?: string | null
}

export const authService = {
  login: async (password: string): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/auth/login', { password })
    return response.data
  },

  logout: async (): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/auth/logout')
    return response.data
  },

  getSession: async (): Promise<AuthResponse> => {
    const response = await api.get<AuthResponse>('/auth/session')
    return response.data
  },
}
