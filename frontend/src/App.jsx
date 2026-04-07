/**
 * CodeAutopsy — App Root (v2.0)
 * Main application with auth-aware routing.
 * - `/` — Landing page (redirects to /dashboard if authenticated)
 * - `/dashboard` — Protected dashboard for authenticated users
 * - `/analysis/:id` — Analysis results page
 * - `/editor/:id` — Code editor page
 */

import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import Navbar from './components/ui/Navbar';
import LandingPage from './pages/LandingPage';
import DashboardPage from './pages/DashboardPage';
import AnalysisPage from './pages/AnalysisPage';
import EditorPage from './pages/EditorPage';
import AdminPage from './pages/AdminPage';
import useAuthStore from './lib/authStore';

/**
 * Protected route wrapper — redirects to / if not authenticated.
 */
function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/" replace />;
  return children;
}

/**
 * Admin route wrapper — redirects to /dashboard if not admin.
 */
function AdminRoute({ children }) {
  const { isAuthenticated, user } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/" replace />;
  if (!user?.is_admin) return <Navigate to="/dashboard" replace />;
  return children;
}

function AppLayout() {
  const location = useLocation();
  const { isAuthenticated } = useAuthStore();

  const isLanding = location.pathname === '/';
  const isAnalysis = location.pathname.startsWith('/analysis');
  const isEditor = location.pathname.startsWith('/editor');

  // Show navbar on dashboard and unknown pages; hide on landing, analysis, editor
  const hideNavbar = (isLanding && !isAuthenticated) || isAnalysis || isEditor;

  return (
    <>
      {!hideNavbar && <Navbar />}
      <main className={hideNavbar ? '' : 'page-content'}>
        <Routes>
          {/* Landing — redirect to dashboard if authenticated */}
          <Route
            path="/"
            element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <LandingPage />}
          />

          {/* Dashboard — protected */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />

          {/* Admin Panel — protected */}
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <AdminPage />
              </AdminRoute>
            }
          />

          {/* Analysis results */}
          <Route path="/analysis/:id" element={<AnalysisPage />} />

          {/* Code editor */}
          <Route path="/editor/:id" element={<EditorPage />} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  return (
    <Router>
      <AppLayout />
    </Router>
  );
}
