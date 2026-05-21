import axios from './axios'

export const configApi = {
  getVersion: async () => {
    const response = await axios.get<{ data: string }>('/config/version')
    return response.data.data
  },
}
