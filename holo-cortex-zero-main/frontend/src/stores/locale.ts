import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import i18next from '../config/i18n'
import type { SupportedLocale } from '../config/i18n'

interface LocaleState {
  currentLocale: SupportedLocale
  setLocale: (locale: SupportedLocale) => void
}

export const useLocaleStore = create<LocaleState>()(
  persist(
    set => ({
      currentLocale: 'en-US',
      setLocale: (locale: SupportedLocale) => {
        // 更新 i18next 语言
        i18next.changeLanguage(locale)
        // 更新状态
        set({ currentLocale: locale })
      },
    }),
    {
      name: 'holo-cortex-zero-locale',
      onRehydrateStorage: () => state => {
        if (state?.currentLocale) {
          void i18next.changeLanguage(state.currentLocale)
        }
      },
      partialize: state => ({
        currentLocale: state.currentLocale,
      }),
    }
  )
)
