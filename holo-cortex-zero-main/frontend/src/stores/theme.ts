import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'light' | 'dark'

interface ColorModeState {
  mode: ThemeMode
  toggleColorMode: () => void
  setColorMode: (mode: ThemeMode) => void
  getEffectiveMode: () => 'light' | 'dark'
}

export const useColorMode = create<ColorModeState>()(
  persist(
    (set, get) => ({
      mode: 'dark' as ThemeMode,
      toggleColorMode: () => set({ mode: get().mode === 'dark' ? 'light' : 'dark' }),
      setColorMode: (mode: ThemeMode) => set({ mode }),
      getEffectiveMode: (): 'light' | 'dark' => {
        return get().mode as 'light' | 'dark'
      },
    }),
    {
      name: 'color-mode-v2',
      partialize: state => ({
        mode: state.mode,
      }),
    }
  )
)
