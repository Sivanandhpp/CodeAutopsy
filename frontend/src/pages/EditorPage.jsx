/**
 * Editor Page — Full-viewport layout with merged single toolbar.
 * No global navbar; editor has its own integrated bar.
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Loader2, AlertTriangle, ArrowLeft, Sun, Moon } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

import FileBrowser from '../components/editor/FileBrowser';
import CodeEditor from '../components/editor/CodeEditor';
import ProblemsPanel from '../components/editor/ProblemsPanel';
import ArchaeologyPanel from '../components/archaeology/ArchaeologyPanel';
import { getAnalysisResults, getFileContent } from '../lib/api';
import useThemeStore from '../lib/themeStore';
import useAnalysisStore from '../lib/analysisStore';

export default function EditorPage() {
  const { id: analysisId } = useParams();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useThemeStore();
  const { analysisResult } = useAnalysisStore();

  // Analysis data
  const [analysis, setAnalysis] = useState(analysisResult || null);
  const [loading, setLoading] = useState(!analysisResult);
  const [error, setError] = useState(null);

  // Editor state
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileCode, setFileCode] = useState('');
  const [fileLanguage, setFileLanguage] = useState('plaintext');
  const [fileLoading, setFileLoading] = useState(false);


  // Archaeology
  const [archaeologyTarget, setArchaeologyTarget] = useState(null);

  const isDark = theme === 'dark';

  // Fetch analysis on mount if not in store
  useEffect(() => {
    if (!analysisResult) {
      fetchAnalysis();
    } else {
      // Auto-select first file with issues if using cached data
      const fileWithIssues = (analysisResult.file_tree || []).find(f => {
        return (analysisResult.issues || []).some(i => i.file_path === f.path);
      });
      if (fileWithIssues && !selectedFile) {
        loadFile(fileWithIssues.path, analysisResult);
      }
    }
  }, [analysisId, analysisResult]);

  async function fetchAnalysis() {
    try {
      setLoading(true);
      const data = await getAnalysisResults(analysisId);
      setAnalysis(data);

      // Auto-select first file with issues
      const fileWithIssues = (data.file_tree || []).find(f => {
        return (data.issues || []).some(i => i.file_path === f.path);
      });
      if (fileWithIssues) {
        loadFile(fileWithIssues.path, data);
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }

  const loadFile = useCallback(async (filePath, analysisData = analysis) => {
    setSelectedFile(filePath);
    setFileLoading(true);
    try {
      const data = await getFileContent(analysisId, filePath);
      setFileCode(data.content || '');
      setFileLanguage(data.language || 'plaintext');
    } catch (e) {
      setFileCode(`// Error loading file: ${e.message || 'Unknown error'}`);
      setFileLanguage('plaintext');
    } finally {
      setFileLoading(false);
    }
  }, [analysisId, analysis]);

  // Get issues for the selected file
  const currentFileIssues = (analysis?.issues || []).filter(
    i => i.file_path === selectedFile
  );

  // Jump to line handler
  const handleJumpToLine = useCallback((lineNumber) => {
    const editorEl = document.querySelector('.ce-wrap .monaco-editor');
    if (editorEl) {
      const editor = editorEl.__monacoEditor;
      if (editor) {
        editor.revealLineInCenter(lineNumber);
        editor.setPosition({ lineNumber, column: 1 });
        editor.focus();
        return;
      }
    }
    const wrapper = document.querySelector('.ce-wrap');
    if (wrapper) {
      const lineHeight = 18;
      wrapper.scrollTop = (lineNumber - 5) * lineHeight;
    }
  }, []);

  // Trace origin handler
  const handleTraceOrigin = useCallback((issue) => {
    setArchaeologyTarget({
      filePath: issue.file_path,
      lineNumber: issue.line_number,
      issueType: issue.issue_type,
    });
  }, []);

  if (loading) {
    return (
      <div className="ep-loading">
        <Loader2 size={32} className="ep-spin" />
        <p>Loading editor...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ep-error">
        <AlertTriangle size={32} />
        <p>{error}</p>
        <Link to="/">Go Home</Link>
      </div>
    );
  }

  return (
    <div className="ep-layout">
      {/* ── Single Merged Toolbar ───────────── */}
      <div className="ep-bar">
        {/* Left section: Logo + back + breadcrumb */}
        <div className="ep-bar-left">
          <Link to="/" className="ep-bar-logo">CodeAutopsy</Link>
          <span className="ep-bar-sep">|</span>
          <button className="ep-bar-back" onClick={() => navigate(`/analysis/${analysisId}`)}>
            <ArrowLeft size={13} />
            Dashboard
          </button>
          {selectedFile && (
            <>
              <span className="ep-bar-sep">›</span>
              <span className="ep-bar-repo">{analysis?.repo_name}</span>
              <span className="ep-bar-sep">/</span>
              <span className="ep-bar-file">{selectedFile}</span>
              {currentFileIssues.length > 0 && (
                <span className="ep-bar-issues">{currentFileIssues.length}</span>
              )}
            </>
          )}
        </div>

        {/* Right: Theme + Login */}
        <div className="ep-bar-right">
          <motion.button
            className="ep-bar-theme"
            onClick={toggleTheme}
            whileTap={{ scale: 0.9 }}
            title={`Switch to ${isDark ? 'light' : 'dark'} mode`}
          >
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={theme}
                initial={{ y: -12, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 12, opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                {isDark ? <Sun size={14} /> : <Moon size={14} />}
              </motion.div>
            </AnimatePresence>
          </motion.button>
          <button className="ep-bar-login">Login</button>
        </div>
      </div>

      {/* ── Body ─────────────────────────────── */}
      <div className="ep-body">
        <div className="ep-sidebar">
          <FileBrowser
            fileTree={analysis?.file_tree || []}
            issues={analysis?.issues || []}
            selectedFile={selectedFile}
            onSelectFile={(path) => loadFile(path)}
          />
        </div>

        <div className="ep-main">
          <div className="ep-editor-area">
            {fileLoading ? (
              <div className="ep-file-loading">
                <Loader2 size={24} className="ep-spin" />
                <span>Loading file...</span>
              </div>
            ) : selectedFile ? (
              <CodeEditor
                code={fileCode}
                language={fileLanguage}
                issues={currentFileIssues}
                onLineClick={handleJumpToLine}
                isDark={isDark}
              />
            ) : (
              <div className="ep-no-file">
                <p>Select a file from the explorer to view it</p>
              </div>
            )}
          </div>

          <ProblemsPanel
            issues={analysis?.issues || []}
            filePath={selectedFile || ''}
            onJumpToLine={handleJumpToLine}
            onTraceOrigin={handleTraceOrigin}
          />
        </div>
      </div>

      {/* Archaeology Panel Modal */}
      {archaeologyTarget && (
        <ArchaeologyPanel
          analysisId={analysisId}
          filePath={archaeologyTarget.filePath}
          lineNumber={archaeologyTarget.lineNumber}
          issueType={archaeologyTarget.issueType}
          onClose={() => setArchaeologyTarget(null)}
        />
      )}

      <style>{editorPageStyles}</style>
    </div>
  );
}

const editorPageStyles = `
  .ep-layout {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
    background: var(--ca-bg);
  }

  /* ─── Merged Toolbar ─────────────────── */
  .ep-bar {
    display: flex;
    align-items: center;
    padding: 0 16px;
    height: 44px;
    min-height: 44px;
    border-bottom: 1px solid var(--ca-border);
    background: var(--ca-bg);
    gap: 12px;
  }
  .ep-bar-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
    overflow: hidden;
  }
  .ep-bar-logo {
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: -0.3px;
    color: var(--ca-text);
    text-decoration: none;
    flex-shrink: 0;
  }
  .ep-bar-sep {
    color: var(--ca-text-muted);
    opacity: 0.4;
    font-size: 0.85rem;
    flex-shrink: 0;
  }
  .ep-bar-back {
    display: flex;
    align-items: center;
    gap: 3px;
    color: var(--ca-text-muted);
    background: none;
    border: none;
    font-size: 0.78rem;
    cursor: pointer;
    padding: 3px 6px;
    border-radius: 4px;
    transition: all 0.15s;
    font-family: var(--ca-font-sans);
    flex-shrink: 0;
  }
  .ep-bar-back:hover { color: var(--ca-text); background: var(--ca-bg-secondary); }
  .ep-bar-repo { color: var(--ca-text-secondary); font-weight: 600; font-size: 0.78rem; flex-shrink: 0; }
  .ep-bar-file {
    color: var(--ca-text);
    font-family: var(--ca-font-mono);
    font-size: 0.75rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ep-bar-issues {
    background: rgba(239,68,68,0.15);
    color: var(--ca-critical);
    font-size: 0.6rem;
    font-weight: 700;
    padding: 0px 5px;
    border-radius: 4px;
    flex-shrink: 0;
  }


  /* Right: theme + login */
  .ep-bar-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .ep-bar-theme {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: 1px solid var(--ca-border);
    background: var(--ca-bg-secondary);
    color: var(--ca-text);
    cursor: pointer;
    transition: border-color 0.2s;
  }
  .ep-bar-theme:hover { border-color: var(--ca-primary); }
  .ep-bar-login {
    background: var(--ca-text);
    color: var(--ca-bg);
    border: none;
    padding: 0.25rem 0.7rem;
    border-radius: 14px;
    font-weight: 500;
    font-size: 0.75rem;
    cursor: pointer;
    font-family: inherit;
    transition: opacity 0.2s;
  }
  .ep-bar-login:hover { opacity: 0.85; }

  /* ─── Body ───────────────────────────── */
  .ep-body {
    display: flex;
    flex: 1;
    min-height: 0;
  }
  .ep-sidebar {
    width: 240px;
    min-width: 180px;
    flex-shrink: 0;
    border-right: 1px solid var(--ca-border);
    overflow-y: auto;
    background: var(--ca-bg);
  }
  .ep-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
  }
  .ep-editor-area {
    flex: 1;
    min-height: 0;
    position: relative;
  }
  .ep-file-loading, .ep-no-file {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 8px;
    color: var(--ca-text-muted);
    font-size: 0.9rem;
  }
  .ep-loading, .ep-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    gap: 12px;
    color: var(--ca-text-secondary);
  }
  .ep-error a {
    color: var(--ca-primary-light);
    text-decoration: none;
    font-weight: 600;
  }
  .ep-spin {
    animation: ep-spin-anim 1s linear infinite;
    color: var(--ca-primary-light);
  }
  @keyframes ep-spin-anim {
    to { transform: rotate(360deg); }
  }

  @media (max-width: 768px) {
    .ep-sidebar { width: 180px; }
    .ep-bar-search { width: 160px; }
    .ep-bar-repo, .ep-bar-file { display: none; }
  }
`;
