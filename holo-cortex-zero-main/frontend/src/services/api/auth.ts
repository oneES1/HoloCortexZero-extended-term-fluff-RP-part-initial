import axios from './axios'

export interface LoginParams {
  username: string
  password: string
}

export interface AdminLoginResponse {
  access_token: string
  token_type: string
}

export interface ApiResponse<T> {
  code: number
  msg: string
  data: T
}

export const adminAuthApi = {
  login: async (params: LoginParams) => {
    try {
      const response = await axios.post<ApiResponse<AdminLoginResponse>>('/admin/login', params)
      if (response.data.code !== 200) {
        throw new Error(response.data.msg)
      }
      return response.data.data
    } catch (error) {
      console.error('Login failed:', error)
      throw error
    }
  },
}
