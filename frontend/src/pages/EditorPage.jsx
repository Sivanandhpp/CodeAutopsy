/**
 * Editor Page — Split-pane layout with file browser, Monaco editor, and problems panel
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Loader2, AlertTriangle, Microscope } from 'lucide-react';

import FileBrowser from '../components/editor/FileBrowser';
import CodeEditor from '../components/editor/CodeEditor';
import ProblemsPanel from '../components/editor/ProblemsPanel';
import ArchaeologyPanel from '../components/archaeology/ArchaeologyPanel';
import { getAnalysisResults, getFileContent } from '../lib/api';

export default function EditorPage() {
  const { id: analysisId } = useParams();

  // Analysis data
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Editor state
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileCode, setFileCode] = useState('');
  const [fileLanguage, setFileLanguage] = useState('plaintext');
  const [fileLoading, setFileLoading] = useState(false);

  // Archaeology
  const [archaeologyTarget, setArchaeologyTarget] = useState(null);

  // Editor ref for jumping
  const editorRef = useRef(null);

  // Detect dark mode
  const isDark = typeof document !== 'undefined' &&
    document.documentElement.getAttribute('data-theme') !== 'light';

  // Fetch analysis on mount
  useEffect(() => {
    fetchAnalysis();
  }, [analysisId]);

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
    // Use Monaco's revealLineInCenter via the editor reference
    const editorEl = document.querySelector('.ce-wrap .monaco-editor');
    if (editorEl) {
      // Access the editor through Monaco's internal ref
      const editor = editorEl.__monacoEditor;
      if (editor) {
        editor.revealLineInCenter(lineNumber);
        editor.setPosition({ lineNumber, column: 1 });
        editor.focus();
        return;
      }
    }
    // Fallback — scroll to approximate position
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
      {/* File Browser Sidebar */}
      <div className="ep-sidebar">
        <FileBrowser
          fileTree={analysis?.file_tree || []}
          issues={analysis?.issues || []}
          selectedFile={selectedFile}
          onSelectFile={(path) => loadFile(path)}
        />
      </div>

      {/* Main Editor Area */}
      <div className="ep-main">
        {/* Top bar */}
        <div className="ep-topbar">
          <Link to={`/analysis/${analysisId}`} className="ep-back">
            <ArrowLeft size={15} />
            Dashboard
          </Link>
          {selectedFile && (
            <div className="ep-breadcrumb">
              <span className="ep-repo">{analysis?.repo_name || 'repo'}</span>
              <span className="ep-sep">/</span>
              <span className="ep-filepath">{selectedFile}</span>
              {currentFileIssues.length > 0 && (
                <span className="ep-file-issues">{currentFileIssues.length} issues</span>
              )}
            </div>
          )}
        </div>

        {/* Editor */}
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

        {/* Problems Panel */}
        <ProblemsPanel
          issues={analysis?.issues || []}
          filePath={selectedFile || ''}
          onJumpToLine={handleJumpToLine}
          onTraceOrigin={handleTraceOrigin}
        />
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
    height: 100vh;
    overflow: hidden;
    background: var(--ca-bg);
  }
  .ep-sidebar {
    width: 260px;
    min-width: 200px;
    flex-shrink: 0;
    height: 100%;
    overflow: hidden;
  }
  .ep-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    height: 100%;
  }
  .ep-topbar {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 16px;
    border-bottom: 1px solid var(--ca-border);
    background: var(--ca-bg-card);
    height: 40px;
    flex-shrink: 0;
  }
  .ep-back {
    display: flex;
    align-items: center;
    gap: 4px;
    color: var(--ca-text-muted);
    font-size: 0.8rem;
    text-decoration: none;
    transition: color 0.15s;
    flex-shrink: 0;
  }
  .ep-back:hover { color: var(--ca-primary-light); }
  .ep-breadcrumb {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.82rem;
    min-width: 0;
    overflow: hidden;
  }
  .ep-repo { color: var(--ca-text-muted); font-weight: 600; flex-shrink: 0; }
  .ep-sep { color: var(--ca-text-muted); opacity: 0.4; }
  .ep-filepath {
    color: var(--ca-text);
    font-family: var(--ca-font-mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ep-file-issues {
    background: rgba(239,68,68,0.1);
    color: var(--ca-critical);
    font-size: 0.68rem;
    font-weight: 600;
    padding: 1px 8px;
    border-radius: 4px;
    flex-shrink: 0;
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
    animation: editor-spin 1s linear infinite;
    color: var(--ca-primary-light);
  }
  @keyframes editor-spin {
    to { transform: rotate(360deg); }
  }
`;
