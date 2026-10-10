import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, RequireAuth } from './lib/auth'
import { Layout } from './components/Layout'
import { RouteCurtain } from './components/RouteCurtain'

const PublicDashboard = lazy(() =>
  import('./pages/PublicDashboard').then((module) => ({
    default: module.PublicDashboard,
  })),
)
const Meridian = lazy(() =>
  import('./pages/Meridian').then((module) => ({ default: module.Meridian })),
)
const Login = lazy(() =>
  import('./pages/Login').then((module) => ({ default: module.Login })),
)
const Register = lazy(() =>
  import('./pages/Register').then((module) => ({ default: module.Register })),
)
const Console = lazy(() =>
  import('./pages/Console').then((module) => ({ default: module.Console })),
)
const Search = lazy(() =>
  import('./pages/Search').then((module) => ({ default: module.Search })),
)
const Tracking = lazy(() =>
  import('./pages/Tracking').then((module) => ({ default: module.Tracking })),
)

function RouteFallback() {
  return (
    <div className="panel">
      <div className="skeleton skeleton--line" style={{ width: '45%' }} />
      <div className="skeleton skeleton--line" style={{ width: '70%' }} />
      <div className="skeleton skeleton--block" style={{ marginTop: 16 }} />
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route
              index
              element={
                <Suspense fallback={<RouteFallback />}>
                  <Meridian />
                </Suspense>
              }
            />
            <Route
              path="overview"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <PublicDashboard />
                </Suspense>
              }
            />
            <Route
              path="login"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <Login />
                </Suspense>
              }
            />
            <Route
              path="register"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <Register />
                </Suspense>
              }
            />
            <Route
              path="console"
              element={
                <RequireAuth>
                  <Suspense fallback={<RouteFallback />}>
                    <Console />
                  </Suspense>
                </RequireAuth>
              }
            />
            <Route
              path="search"
              element={
                <RequireAuth>
                  <Suspense fallback={<RouteFallback />}>
                    <Search />
                  </Suspense>
                </RequireAuth>
              }
            />
            <Route
              path="tracking"
              element={
                <RequireAuth>
                  <Suspense fallback={<RouteFallback />}>
                    <Tracking />
                  </Suspense>
                </RequireAuth>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
        <RouteCurtain />
      </BrowserRouter>
    </AuthProvider>
  )
}
