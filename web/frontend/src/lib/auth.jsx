import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { clearSession, getEmail, getToken, setSession } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSessionState] = useState(() => ({
    token: getToken(),
    email: getEmail(),
  }))

  useEffect(() => {
    const sync = () =>
      setSessionState({ token: getToken(), email: getEmail() })
    window.addEventListener('anpr:session', sync)
    return () => window.removeEventListener('anpr:session', sync)
  }, [])

  const value = useMemo(
    () => ({
      token: session.token,
      email: session.email,
      isAuthed: Boolean(session.token),
      login(token, email) {
        setSession(token, email)
        setSessionState({ token, email })
      },
      logout() {
        clearSession()
      },
    }),
    [session],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}

export function RequireAuth({ children }) {
  const { isAuthed } = useAuth()
  const location = useLocation()

  if (!isAuthed) {
    return (
      <Navigate
        to="/login"
        state={{ from: location.pathname }}
        replace
      />
    )
  }

  return children
}
