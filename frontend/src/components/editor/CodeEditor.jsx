/**
 * Code Editor — Monaco editor wrapper with issue decorations, hover tooltips,
 * right-click "Trace Origin" context menu, and imperative jumpToLine via ref.
 */

import { useRef, useEffect, useCallback, useImperativeHandle, forwardRef } from 'react';
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


const CodeEditor = forwardRef(function CodeEditor({
  code = '',
  language = 'plaintext',
  issues = [],
  onChange,
  onTraceOrigin,
  isDark = true,
}, ref) {
  const editorRef = useRef(null);
  const monacoRef = useRef(null);
  const decorationsRef = useRef([]);
  const traceOriginRef = useRef(onTraceOrigin);

  // Keep callback ref in sync without re-registering the action
  useEffect(() => {
    traceOriginRef.current = onTraceOrigin;
  }, [onTraceOrigin]);

  const monacoLang = MONACO_LANG_MAP[language?.toLowerCase()] || 'plaintext';

  // Expose jumpToLine to parent via ref
  useImperativeHandle(ref, () => ({
    jumpToLine(lineNumber) {
      const editor = editorRef.current;
      if (editor) {
        editor.revealLineInCenter(lineNumber);
        editor.setPosition({ lineNumber, column: 1 });
        editor.focus();
      }
    },
  }), []);

  const handleEditorMount = useCallback((editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    // Apply decorations for issues
    applyDecorations(editor, monaco, issues);

    // ── Register "Trace Origin" context-menu action ──────────
    editor.addAction({
      id: 'codeautopsy.traceOrigin',
      label: 'Trace Origin',
      contextMenuGroupId: 'navigation',
      contextMenuOrder: 1.5,
      // Show always — the action handler will check selection
      run(ed) {
        const selection = ed.getSelection();
        const selectedText = ed.getModel().getValueInRange(selection);
        const lineNumber = selection.startLineNumber;

        if (traceOriginRef.current) {
          traceOriginRef.current({
            lineNumber,
            selectedText: selectedText || null,
            startLine: selection.startLineNumber,
            endLine: selection.endLineNumber,
          });
        }
      },
    });
  }, [issues]);

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
        blocker: 'squiggly-blocker',
        critical: 'squiggly-critical',
        high: 'squiggly-high',
        medium: 'squiggly-medium',
        low: 'squiggly-low',
        info: 'squiggly-info',
        trace: 'squiggly-trace',
      }[severity] || 'squiggly-medium';

      const glyphClass = {
        blocker: 'glyph-blocker',
        critical: 'glyph-critical',
        high: 'glyph-high',
        medium: 'glyph-medium',
        low: 'glyph-low',
        info: 'glyph-info',
        trace: 'glyph-trace',
      }[severity] || 'glyph-medium';

      return {
        range: new monaco.Range(issue.line_number, 1, issue.line_number, 1),
        options: {
          isWholeLine: true,
          className: sevClass,
          glyphMarginClassName: glyphClass,
          hoverMessage: {
            value: [
              `**${severity.toUpperCase()}** — ${issue.defect_family || 'unknown'}`,
              '',
              issue.message,
              '',
              issue.code_snippet ? `\`\`\`\n${issue.code_snippet}\n\`\`\`` : '',
              '',
              '_Right-click → **Trace Origin** to investigate_',
            ].join('\n'),
          },
          overviewRuler: {
            color: {
              blocker: '#7f1d1d',
              critical: '#ef4444',
              high: '#f97316',
              medium: '#eab308',
              low: '#06b6d4',
              info: '#8b5cf6',
              trace: '#64748b',
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

  return (
    <div className="ce-wrap">
      <Editor
        height="100%"
        language={monacoLang}
        value={code}
        onChange={onChange}
        theme={isDark ? 'vs-dark' : 'vs'}
        onMount={handleEditorMount}
        options={{
          readOnly: false,
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
        .squiggly-blocker {
          background: rgba(127, 29, 29, 0.1);
          border-bottom: 2px wavy #7f1d1d;
        }
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
        .squiggly-info {
          background: rgba(139, 92, 246, 0.05);
          border-bottom: 2px wavy #8b5cf6;
        }
        .squiggly-trace {
          background: rgba(100, 116, 139, 0.05);
          border-bottom: 2px wavy #64748b;
        }
        /* Glyph margin dots */
        .glyph-blocker { background: #7f1d1d; border-radius: 50%; width: 8px !important; height: 8px !important; margin: 6px 4px; }
        .glyph-critical { background: #ef4444; border-radius: 50%; width: 8px !important; height: 8px !important; margin: 6px 4px; }
        .glyph-high { background: #f97316; border-radius: 50%; width: 8px !important; height: 8px !important; margin: 6px 4px; }
        .glyph-medium { background: #eab308; border-radius: 50%; width: 8px !important; height: 8px !important; margin: 6px 4px; }
        .glyph-low { background: #06b6d4; border-radius: 50%; width: 8px !important; height: 8px !important; margin: 6px 4px; }
        .glyph-info { background: #8b5cf6; border-radius: 50%; width: 8px !important; height: 8px !important; margin: 6px 4px; }
        .glyph-trace { background: #64748b; border-radius: 50%; width: 8px !important; height: 8px !important; margin: 6px 4px; }
      `}</style>
    </div>
  );
});

export default CodeEditor;
