/**
 * CodeAutopsy — App Root
 * Main application component with React Router and global layout.
 */

import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/ui/Navbar';
import LandingPage from './pages/LandingPage';
import AnalysisPage from './pages/AnalysisPage';

export default function App() {
  return (
    <Router>
      <Navbar />
      <main className="page-content">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/analysis/:id" element={<AnalysisPage />} />
          {/* Checkpoint 4: Editor page */}
          {/* <Route path="/editor/:id" element={<EditorPage />} /> */}
        </Routes>
      </main>
    </Router>
  );
}
