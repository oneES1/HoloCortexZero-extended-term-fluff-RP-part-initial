import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

interface AuthState {
  token: string | null
  setToken: (token: string | null) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    set => ({
      token: null,
      setToken: token => set({ token }),
      logout: () => set({ token: null }),
    }),
    {
      name: 'platform-admin-session-state',
      storage: createJSONStorage(() => sessionStorage),
      partialize: state => ({ token: state.token }),
    }
  )
)
