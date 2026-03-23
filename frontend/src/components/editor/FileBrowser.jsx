/**
 * File Browser — Collapsible tree of analyzed files with issue badges
 */

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronRight, ChevronDown, FileCode, Folder, FolderOpen,
  Search, Bug, AlertTriangle
} from 'lucide-react';

export default function FileBrowser({ 
  fileTree = [], 
  issues = [],
  selectedFile, 
  onSelectFile
}) {
  const [expandedDirs, setExpandedDirs] = useState(new Set());
  const [search, setSearch] = useState('');

  // Build issue count per file
  const issueCountMap = useMemo(() => {
    const map = {};
    (issues || []).forEach(i => {
      map[i.file_path] = (map[i.file_path] || 0) + 1;
    });
    return map;
  }, [issues]);

  // Build tree structure from flat file list
  const tree = useMemo(() => {
    let files = fileTree;
    if (search) {
      const q = search.toLowerCase();
      files = files.filter(f => f.path.toLowerCase().includes(q));
    }

    const root = {};
    files.forEach(f => {
      const parts = f.path.split('/');
      let node = root;
      parts.forEach((part, i) => {
        if (i === parts.length - 1) {
          // File
          if (!node.__files__) node.__files__ = [];
          node.__files__.push({ ...f, issueCount: issueCountMap[f.path] || 0 });
        } else {
          // Directory
          if (!node[part]) node[part] = {};
          node = node[part];
        }
      });
    });
    return root;
  }, [fileTree, search, issueCountMap]);

  const toggleDir = (path) => {
    const next = new Set(expandedDirs);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    setExpandedDirs(next);
  };

  // Count total issues in a directory subtree
  const getDirIssueCount = (node) => {
    let count = 0;
    if (node.__files__) {
      count += node.__files__.reduce((sum, f) => sum + f.issueCount, 0);
    }
    Object.entries(node).forEach(([key, child]) => {
      if (key !== '__files__' && typeof child === 'object') {
        count += getDirIssueCount(child);
      }
    });
    return count;
  };

  const renderNode = (node, parentPath = '', depth = 0) => {
    const entries = [];

    // Directories first
    const dirs = Object.entries(node)
      .filter(([k]) => k !== '__files__')
      .sort(([a], [b]) => a.localeCompare(b));

    dirs.forEach(([name, child]) => {
      const fullPath = parentPath ? `${parentPath}/${name}` : name;
      const isOpen = expandedDirs.has(fullPath);
      const dirIssues = getDirIssueCount(child);

      entries.push(
        <div key={`dir-${fullPath}`}>
          <button
            className="fb-item fb-dir"
            style={{ paddingLeft: `${12 + depth * 16}px` }}
            onClick={() => toggleDir(fullPath)}
          >
            {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {isOpen ? <FolderOpen size={14} className="fb-folder-icon" /> : <Folder size={14} className="fb-folder-icon" />}
            <span className="fb-name">{name}</span>
            {dirIssues > 0 && <span className="fb-issue-dot">{dirIssues}</span>}
          </button>
          <AnimatePresence>
            {isOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.15 }}
                style={{ overflow: 'hidden' }}
              >
                {renderNode(child, fullPath, depth + 1)}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      );
    });

    // Files
    const files = (node.__files__ || []).sort((a, b) => {
      // Issues first, then alphabetical
      if (a.issueCount !== b.issueCount) return b.issueCount - a.issueCount;
      return a.path.localeCompare(b.path);
    });

    files.forEach(f => {
      const fileName = f.path.split('/').pop();
      const isActive = selectedFile === f.path;

      entries.push(
        <button
          key={`file-${f.path}`}
          className={`fb-item fb-file ${isActive ? 'active' : ''}`}
          style={{ paddingLeft: `${12 + (depth + 1) * 16}px` }}
          onClick={() => onSelectFile(f.path)}
          title={f.path}
        >
          <FileCode size={14} className="fb-file-icon" />
          <span className="fb-name">{fileName}</span>
          {f.issueCount > 0 && (
            <span className="fb-issue-badge">
              <Bug size={10} />
              {f.issueCount}
            </span>
          )}
          <span className="fb-lang">{f.language}</span>
        </button>
      );
    });

    return entries;
  };

  return (
    <div className="fb-wrap">
      <div className="fb-header">
        <h3>Explorer</h3>
        <span className="fb-count">{fileTree.length} files</span>
      </div>
      <div className="fb-search">
        <Search size={13} />
        <input
          type="text"
          placeholder="Find file..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>
      <div className="fb-tree">
        {renderNode(tree)}
        {fileTree.length === 0 && (
          <div className="fb-empty">No files found</div>
        )}
      </div>

      <style>{`
        .fb-wrap {
          height: 100%;
          display: flex;
          flex-direction: column;
          background: var(--ca-bg);
        }
        .fb-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 14px 8px;
          border-bottom: 1px solid var(--ca-border);
        }
        .fb-header h3 {
          font-size: 0.75rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: var(--ca-text-muted);
        }
        .fb-count {
          font-size: 0.7rem;
          color: var(--ca-text-muted);
          font-family: var(--ca-font-mono);
        }
        .fb-search {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 5px 10px;
          margin: 6px 8px;
          background: var(--ca-bg-secondary);
          border: 1px solid var(--ca-border);
          border-radius: 6px;
        }
        .fb-search svg { color: var(--ca-text-muted); flex-shrink: 0; }
        .fb-search input {
          background: transparent;
          border: none;
          outline: none;
          color: var(--ca-text);
          font-size: 0.78rem;
          width: 100%;
          font-family: var(--ca-font-sans);
        }
        .fb-search input::placeholder { color: var(--ca-text-muted); }
        .fb-tree {
          flex: 1;
          overflow-y: auto;
          overflow-x: hidden;
          padding: 4px 0;
        }
        .fb-item {
          display: flex;
          align-items: center;
          gap: 6px;
          width: 100%;
          padding: 4px 12px;
          border: none;
          background: transparent;
          color: var(--ca-text-secondary);
          font-size: 0.82rem;
          font-family: var(--ca-font-sans);
          cursor: pointer;
          text-align: left;
          transition: background 0.1s;
          white-space: nowrap;
        }
        .fb-item:hover { background: rgba(99,102,241,0.06); }
        .fb-file.active {
          background: rgba(99,102,241,0.1);
          color: var(--ca-primary-light);
        }
        .fb-folder-icon { color: var(--ca-medium); }
        .fb-file-icon { color: var(--ca-text-muted); }
        .fb-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
        .fb-issue-dot {
          background: var(--ca-critical);
          color: white;
          font-size: 0.6rem;
          font-weight: 700;
          min-width: 16px;
          height: 16px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0 4px;
        }
        .fb-issue-badge {
          display: flex;
          align-items: center;
          gap: 3px;
          background: rgba(239,68,68,0.1);
          color: var(--ca-critical);
          font-size: 0.68rem;
          font-weight: 600;
          padding: 1px 6px;
          border-radius: 4px;
        }
        .fb-lang {
          font-size: 0.65rem;
          color: var(--ca-text-muted);
          font-family: var(--ca-font-mono);
          opacity: 0.6;
        }
        .fb-empty {
          padding: 20px;
          text-align: center;
          color: var(--ca-text-muted);
          font-size: 0.82rem;
        }
      `}</style>
    </div>
  );
}
