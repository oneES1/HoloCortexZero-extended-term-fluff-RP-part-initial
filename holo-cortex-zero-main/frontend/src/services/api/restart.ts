import axios from './axios'

export interface RestartResponse {
  code: number
  msg: string
  data?: unknown
}

export const restartApi = {
  restartSystem: async (): Promise<RestartResponse> => {
    const response = await axios.post<RestartResponse>('/restart')
    return response.data
  },
}
