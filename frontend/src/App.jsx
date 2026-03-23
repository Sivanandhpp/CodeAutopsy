/**
 * CodeAutopsy — App Root
 * Main application component with React Router and global layout.
 */

import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import Navbar from './components/ui/Navbar';
import LandingPage from './pages/LandingPage';
import AnalysisPage from './pages/AnalysisPage';
import EditorPage from './pages/EditorPage';

function AppLayout() {
  const location = useLocation();
  const isLanding = location.pathname === '/';
  const isAnalysis = location.pathname.startsWith('/analysis');
  const isEditor = location.pathname.startsWith('/editor');
  const hideNavbar = isLanding || isAnalysis || isEditor;

  return (
    <>
      {!hideNavbar && <Navbar />}
      <main className={hideNavbar ? '' : 'page-content'}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/analysis/:id" element={<AnalysisPage />} />
          <Route path="/editor/:id" element={<EditorPage />} />
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
