import { Moon, Sun } from '@phosphor-icons/react'
import { useTheme } from '../lib/theme'

export function ThemeToggle({ className = '' }) {
  const { theme, toggleTheme } = useTheme()
  const nextTheme = theme === 'dark' ? 'light' : 'dark'
  const Icon = theme === 'dark' ? Sun : Moon

  return (
    <button
      type="button"
      className={`theme-toggle ${className}`.trim()}
      onClick={toggleTheme}
      aria-label={`Switch to ${nextTheme} mode`}
      title={`Switch to ${nextTheme} mode`}
      aria-pressed={theme === 'light'}
    >
      <Icon size={17} weight="bold" aria-hidden="true" />
      <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
    </button>
  )
}
