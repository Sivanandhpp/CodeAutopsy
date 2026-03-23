/**
 * Code Editor — Monaco editor wrapper with issue decorations and hover tooltips
 */

import { useRef, useEffect, useCallback } from 'react';
import Editor from '@monaco-editor/react';

// Map our language names (from languages.py) to Monaco language IDs
// Monaco supports ~70 languages natively. For unsupported ones, we map
// to the closest available highlighter (e.g. 'crystal' → 'ruby').
const MONACO_LANG_MAP = {
  // ── Core languages ─────────────────────────────────────────
  'python': 'python', 'javascript': 'javascript', 'typescript': 'typescript',
  'java': 'java', 'c': 'c', 'c++': 'cpp', 'c#': 'csharp', 'go': 'go',
  'rust': 'rust', 'ruby': 'ruby', 'php': 'php', 'swift': 'swift',
  'kotlin': 'kotlin', 'scala': 'scala', 'dart': 'dart', 'lua': 'lua',
  'perl': 'perl', 'r': 'r', 'shell': 'shell', 'powershell': 'powershell',
  // ── Web & markup ───────────────────────────────────────────
  'html': 'html', 'css': 'css', 'scss': 'scss', 'less': 'less',
  'json': 'json', 'yaml': 'yaml', 'xml': 'xml', 'markdown': 'markdown',
  'sql': 'sql', 'graphql': 'graphql', 'dockerfile': 'dockerfile',
  'svg': 'xml', 'toml': 'ini',
  // ── Systems & low-level ────────────────────────────────────
  'assembly': 'mips', 'cuda': 'cpp', 'objective-c': 'objective-c',
  'objective-c++': 'objective-c', 'fortran': 'fortran',
  // ── JVM & .NET ─────────────────────────────────────────────
  'groovy': 'java', 'clojure': 'clojure', 'haskell': 'haskell',
  'erlang': 'erlang', 'elixir': 'elixir', 'f#': 'fsharp',
  'visual basic': 'vb', 'apex': 'apex',
  // ── Scripting & dynamic ────────────────────────────────────
  'coffeescript': 'coffeescript', 'livescript': 'javascript',
  'crystal': 'ruby', 'nim': 'python', 'julia': 'julia',
  // ── Config & data ──────────────────────────────────────────
  'ini': 'ini', 'hcl': 'hcl', 'jsonld': 'json', 'json5': 'json',
  'csv': 'plaintext', 'protocol buffers': 'protobuf',
  // ── Template & web frameworks ──────────────────────────────
  'handlebars': 'handlebars', 'twig': 'twig', 'jade': 'pug',
  'haml': 'haml', 'slim': 'ruby', 'liquid': 'liquid',
  'html+django': 'html', 'html+erb': 'html', 'html+php': 'php',
  'html+eex': 'html', 'rhtml': 'html',
  // ── Database ───────────────────────────────────────────────
  'plsql': 'sql', 'sqlpl': 'sql',
  // ── Shader & GPU ───────────────────────────────────────────
  'glsl': 'c', 'hlsl': 'cpp', 'metal': 'cpp', 'opencl': 'c',
  // ── DevOps & infrastructure ────────────────────────────────
  'batchfile': 'bat', 'tcl': 'tcl',
  'nginx': 'plaintext', 'apacheconf': 'plaintext',
  // ── Functional ─────────────────────────────────────────────
  'ocaml': 'plaintext', 'scheme': 'scheme', 'racket': 'scheme',
  'common lisp': 'plaintext', 'emacs lisp': 'plaintext',
  'standard ml': 'plaintext', 'purescript': 'typescript',
  // ── Misc ───────────────────────────────────────────────────
  'tex': 'latex', 'restructuredtext': 'restructuredtext',
  'pascal': 'pascal', 'ada': 'ada', 'cobol': 'cobol',
  'prolog': 'prolog', 'solidity': 'sol', 'arduino': 'cpp',
  'processing': 'java', 'cython': 'python', 'sass': 'scss',
  'stylus': 'css', 'diff': 'diff',
  'plaintext': 'plaintext', 'text': 'plaintext',
};


export default function CodeEditor({ 
  code = '', 
  language = 'plaintext',
  issues = [],
  onLineClick,
  isDark = true,
}) {
  const editorRef = useRef(null);
  const monacoRef = useRef(null);
  const decorationsRef = useRef([]);

  const monacoLang = MONACO_LANG_MAP[language?.toLowerCase()] || 'plaintext';

  const handleEditorMount = useCallback((editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    // Apply decorations for issues
    applyDecorations(editor, monaco, issues);

    // Line click handler
    editor.onMouseDown((e) => {
      if (e.target?.position?.lineNumber && onLineClick) {
        onLineClick(e.target.position.lineNumber);
      }
    });
  }, [issues, onLineClick]);

  // Update decorations when issues change
  useEffect(() => {
    if (editorRef.current && monacoRef.current) {
      applyDecorations(editorRef.current, monacoRef.current, issues);
    }
  }, [issues, code]);

  function applyDecorations(editor, monaco, fileIssues) {
    const decorations = fileIssues.map(issue => {
      const severity = issue.severity || 'medium';
      const sevClass = {
        critical: 'squiggly-critical',
        high: 'squiggly-high',
        medium: 'squiggly-medium',
        low: 'squiggly-low',
      }[severity] || 'squiggly-medium';

      const glyphClass = {
        critical: 'glyph-critical',
        high: 'glyph-high',
        medium: 'glyph-medium',
        low: 'glyph-low',
      }[severity] || 'glyph-medium';

      return {
        range: new monaco.Range(issue.line_number, 1, issue.line_number, 1),
        options: {
          isWholeLine: true,
          className: sevClass,
          glyphMarginClassName: glyphClass,
          hoverMessage: {
            value: [
              `**${severity.toUpperCase()}** — ${issue.issue_type}`,
              '',
              issue.message,
              '',
              issue.code_snippet ? `\`\`\`\n${issue.code_snippet}\n\`\`\`` : '',
              '',
              '_Click "Trace Origin" in the Problems panel below_',
            ].join('\n'),
          },
          overviewRuler: {
            color: {
              critical: '#ef4444',
              high: '#f97316', 
              medium: '#eab308',
              low: '#06b6d4',
            }[severity] || '#eab308',
            position: monaco.editor.OverviewRulerLane.Right,
          },
        },
      };
    });

    decorationsRef.current = editor.deltaDecorations(
      decorationsRef.current,
      decorations
    );
  }

  // Public method to jump to a line
  const jumpToLine = useCallback((lineNumber) => {
    if (editorRef.current) {
      editorRef.current.revealLineInCenter(lineNumber);
      editorRef.current.setPosition({ lineNumber, column: 1 });
      editorRef.current.focus();
    }
  }, []);

  // Expose jumpToLine via ref-like pattern
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current._jumpToLine = jumpToLine;
    }
  }, [jumpToLine]);

  return (
    <div className="ce-wrap">
      <Editor
        height="100%"
        language={monacoLang}
        value={code}
        theme={isDark ? 'vs-dark' : 'vs'}
        onMount={handleEditorMount}
        options={{
          readOnly: true,
          minimap: { enabled: true },
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          fontSize: 13,
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
          glyphMargin: true,
          folding: true,
          renderLineHighlight: 'all',
          smoothScrolling: true,
          cursorBlinking: 'smooth',
          padding: { top: 8 },
        }}
      />
      <style>{`
        .ce-wrap {
          height: 100%;
          width: 100%;
          border-radius: 8px;
          overflow: hidden;
        }
        /* Squiggly underline decorations */
        .squiggly-critical {
          background: rgba(239, 68, 68, 0.08);
          border-bottom: 2px wavy #ef4444;
        }
        .squiggly-high {
          background: rgba(249, 115, 22, 0.06);
          border-bottom: 2px wavy #f97316;
        }
        .squiggly-medium {
          background: rgba(234, 179, 8, 0.06);
          border-bottom: 2px wavy #eab308;
        }
        .squiggly-low {
          background: rgba(6, 182, 212, 0.04);
          border-bottom: 2px wavy #06b6d4;
        }
        /* Glyph margin dots */
        .glyph-critical { background: #ef4444; border-radius: 50%; width: 8px !important; height: 8px !important; margin: 6px 4px; }
        .glyph-high { background: #f97316; border-radius: 50%; width: 8px !important; height: 8px !important; margin: 6px 4px; }
        .glyph-medium { background: #eab308; border-radius: 50%; width: 8px !important; height: 8px !important; margin: 6px 4px; }
        .glyph-low { background: #06b6d4; border-radius: 50%; width: 8px !important; height: 8px !important; margin: 6px 4px; }
      `}</style>
    </div>
  );
}

// Export a helper to jump to line from outside
CodeEditor.jumpToLine = null;
