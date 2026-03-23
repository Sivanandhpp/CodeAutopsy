"""
Static Analyzer Service
Wraps Semgrep for security vulnerability detection and provides
a fallback regex-based scanner when Semgrep is not available.
"""

import json
import subprocess
import os
import re
import uuid
import hashlib
from pathlib import Path


# ─── Severity Scoring ─────────────────────────────────────────

SEVERITY_WEIGHTS = {
    'critical': 15,
    'high': 10,
    'medium': 5,
    'low': 2,
    'info': 1,
}

# High-impact issue types get extra penalty
HIGH_IMPACT_TYPES = {
    'sql-injection', 'xss', 'command-injection', 'path-traversal',
    'ssrf', 'insecure-deserialization', 'remote-code-execution',
}


# ─── Fallback Regex Patterns ──────────────────────────────────
# Used when Semgrep is not installed — expanded to 50+ rules

REGEX_RULES = [
    # ═══════════════════════════════════════════════════════════════
    # CRITICAL — Remote Code Execution, Injection, etc.
    # ═══════════════════════════════════════════════════════════════
    {
        'id': 'command-injection',
        'pattern': r'(?i)(os\.system|subprocess\.call|subprocess\.Popen|child_process\.exec|Runtime\.getRuntime\(\)\.exec)\s*\(.*[\+f"\{]',
        'message': 'Potential command injection: user input in system command',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'ruby'],
    },
    {
        'id': 'sql-injection',
        'pattern': r'(?i)(execute|cursor\.execute|query|raw_query)\s*\(\s*[f"\'].*(%s|%d|\{|\+\s*\w+)',
        'message': 'Potential SQL injection via string concatenation/formatting in query',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'php', 'ruby', 'go'],
    },
    {
        'id': 'sql-injection-concatenation',
        'pattern': r'(?i)(SELECT|INSERT|UPDATE|DELETE|DROP)\s+.*\"\s*\+\s*\w+',
        'message': 'SQL query built with string concatenation — use parameterized queries',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'php', 'ruby', 'c#', 'go'],
    },
    {
        'id': 'xss-innerhtml',
        'pattern': r'\.(innerHTML|outerHTML)\s*=(?!\s*["\']<)',
        'message': 'Direct innerHTML/outerHTML assignment may lead to XSS vulnerabilities',
        'severity': 'critical',
        'category': 'security',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'xss-document-write',
        'pattern': r'document\.(write|writeln)\s*\(',
        'message': 'document.write() can introduce XSS vulnerabilities',
        'severity': 'high',
        'category': 'security',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'jwt-no-verify',
        'pattern': r'(?i)jwt\.(decode|verify).*verify\s*=\s*false',
        'message': 'JWT verification disabled — tokens are not validated',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'javascript'],
    },
    {
        'id': 'insecure-deserialization',
        'pattern': r'(?i)(pickle\.loads?|yaml\.load\s*\((?!.*Loader)|unserialize|Marshal\.load|ObjectInputStream)',
        'message': 'Insecure deserialization — can lead to remote code execution',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'ruby', 'php'],
    },
    {
        'id': 'xxe-vulnerability',
        'pattern': r'(?i)(XMLParser|etree\.parse|SAXParser|DocumentBuilder).*(?!.*disable.*external)',
        'message': 'Potential XXE (XML External Entity) vulnerability — disable external entities',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'java', 'php', 'c#'],
    },

    # ═══════════════════════════════════════════════════════════════
    # HIGH — Secrets, Auth, Crypto, Injection
    # ═══════════════════════════════════════════════════════════════
    {
        'id': 'hardcoded-secret',
        'pattern': r'(?i)(password|secret|api_key|apikey|token|access_key|private_key|secret_key)\s*=\s*["\'][^"\']{8,}["\']',
        'message': 'Potential hardcoded secret or credential — use environment variables',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'typescript', 'java', 'go', 'ruby', 'php', 'kotlin', 'swift', 'c#', 'rust'],
    },
    {
        'id': 'hardcoded-ip',
        'pattern': r'["\'](\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})["\']',
        'message': 'Hardcoded IP address found — use configuration or DNS',
        'severity': 'medium',
        'category': 'best-practice',
        'languages': ['python', 'javascript', 'typescript', 'java', 'go', 'ruby', 'php', 'c', 'c++'],
    },
    {
        'id': 'eval-usage',
        'pattern': r'\beval\s*\(',
        'message': 'Use of eval() can lead to code injection attacks',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'typescript', 'php', 'ruby'],
    },
    {
        'id': 'exec-usage',
        'pattern': r'\bexec\s*\(',
        'message': 'Use of exec() can lead to code injection attacks',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'php'],
    },
    {
        'id': 'open-redirect',
        'pattern': r'(?i)(redirect|location\.href|window\.location)\s*=\s*.*req\.',
        'message': 'Potential open redirect vulnerability with user-controlled input',
        'severity': 'high',
        'category': 'security',
        'languages': ['javascript', 'python', 'php', 'ruby'],
    },
    {
        'id': 'path-traversal',
        'pattern': r'(?i)(open|read_file|send_file|readFile|createReadStream)\s*\(.*\+.*(params|query|body|args|req\.|request\.)',
        'message': 'Potential path traversal: user input in file path',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'php', 'ruby', 'go'],
    },
    {
        'id': 'ssrf',
        'pattern': r'(?i)(requests\.get|fetch|urllib\.request|http\.get|axios\.get|HttpClient)\s*\(.*\+.*(params|query|body|args|req\.|request\.)',
        'message': 'Potential SSRF — user input in outbound HTTP request URL',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'go', 'ruby', 'php'],
    },
    {
        'id': 'insecure-hash',
        'pattern': r'(?i)(md5|sha1)\s*\(',
        'message': 'Use of weak cryptographic hash (MD5/SHA1) — use SHA-256 or bcrypt',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'php', 'ruby', 'go', 'c', 'c++'],
    },
    {
        'id': 'insecure-random',
        'pattern': r'(?i)\brandom\.(random|randint|choice|randrange)\b',
        'message': 'Use of non-cryptographic random — use secrets module for security-sensitive ops',
        'severity': 'high',
        'category': 'security',
        'languages': ['python'],
    },
    {
        'id': 'insecure-random-js',
        'pattern': r'Math\.random\s*\(\s*\)',
        'message': 'Math.random() is not cryptographically secure — use crypto.getRandomValues()',
        'severity': 'high',
        'category': 'security',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'prototype-pollution',
        'pattern': r'(?i)(Object\.assign|__proto__|constructor\s*\[)',
        'message': 'Potential prototype pollution — validate input object keys',
        'severity': 'high',
        'category': 'security',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'insecure-cookie',
        'pattern': r'(?i)(set_cookie|set-cookie|cookie\s*=)(?!.*(secure|httponly|samesite))',
        'message': 'Cookie set without Secure/HttpOnly/SameSite flags',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'php', 'ruby'],
    },
    {
        'id': 'cors-wildcard',
        'pattern': r'(?i)(access-control-allow-origin|cors).*\*',
        'message': 'CORS wildcard (*) allows any origin — may expose sensitive data',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'go', 'ruby', 'php'],
    },
    {
        'id': 'missing-csrf',
        'pattern': r'(?i)(app\.post|router\.post|@app\.route.*methods.*POST)(?!.*csrf)',
        'message': 'POST endpoint may lack CSRF protection',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'java'],
    },
    {
        'id': 'sensitive-data-logging',
        'pattern': r'(?i)(log|print|console\.log|logger)\s*\(.*(?:password|token|secret|credit.?card|ssn)',
        'message': 'Sensitive data may be logged — mask credentials before logging',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'typescript', 'java', 'go', 'ruby', 'php'],
    },

    # ═══════════════════════════════════════════════════════════════
    # MEDIUM — Reliability, Robustness, Code Smell
    # ═══════════════════════════════════════════════════════════════
    {
        'id': 'null-pointer',
        'pattern': r'(?i)(\w+)\.(length|size|count|trim|split|strip|upper|lower|replace|append|extend|keys|values|items)\s*\(',
        'message': 'Potential null/None pointer dereference — add null check before method call',
        'severity': 'medium',
        'category': 'reliability',
        'languages': [],  # too noisy as-is, we handle this differently below
    },
    {
        'id': 'null-dereference-pattern',
        'pattern': r'(?i)(result|response|data|user|obj|record|item|row|node)\s*\[\s*["\']',
        'message': 'Accessing property on potentially null variable — add null guard',
        'severity': 'low',
        'category': 'reliability',
        'languages': [],  # disabled — too many false positives
    },
    {
        'id': 'division-by-zero',
        'pattern': r'(?i)\b\w+\s*/\s*(?:\w+\s*)(?:#|//|/\*)?$',
        'message': 'Potential division by zero — add zero-check before dividing',
        'severity': 'medium',
        'category': 'reliability',
        'languages': [],  # disabled — regex too imprecise
    },
    {
        'id': 'unchecked-division',
        'pattern': r'(?i)(\s/\s+(?:len|count|size|total|num)\s*\()',
        'message': 'Division by result of len/count/size — may be zero for empty collections',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python', 'javascript', 'java', 'go', 'ruby'],
    },
    {
        'id': 'empty-except',
        'pattern': r'except\s*:\s*\n\s*(pass|\.\.\.)',
        'message': 'Empty except clause silently catches all exceptions — handle or log errors',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python'],
    },
    {
        'id': 'bare-except',
        'pattern': r'except\s*:',
        'message': 'Bare except catches all exceptions including SystemExit/KeyboardInterrupt',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python'],
    },
    {
        'id': 'empty-catch-js',
        'pattern': r'catch\s*\([^)]*\)\s*\{\s*\}',
        'message': 'Empty catch block silently swallows errors — log or handle the exception',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['javascript', 'typescript', 'java', 'c#', 'kotlin'],
    },
    {
        'id': 'debug-enabled',
        'pattern': r'(?i)debug\s*=\s*true',
        'message': 'Debug mode enabled — should be disabled in production',
        'severity': 'medium',
        'category': 'best-practice',
        'languages': ['python', 'javascript', 'java', 'php', 'ruby', 'go'],
    },
    {
        'id': 'http-not-https',
        'pattern': r'["\']http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)',
        'message': 'Insecure HTTP URL — use HTTPS for external connections',
        'severity': 'medium',
        'category': 'security',
        'languages': ['python', 'javascript', 'typescript', 'java', 'go', 'ruby', 'php', 'c#', 'kotlin', 'swift'],
    },
    {
        'id': 'disabled-ssl-verify',
        'pattern': r'(?i)(verify\s*=\s*false|ssl_verify\s*=\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*["\']0|InsecureSkipVerify:\s*true)',
        'message': 'SSL/TLS certificate verification disabled — vulnerable to MITM attacks',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'go', 'java', 'ruby'],
    },
    {
        'id': 'assert-in-production',
        'pattern': r'^\s*assert\s+',
        'message': 'Assert statements are stripped in optimized mode — use proper validation',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python'],
    },
    {
        'id': 'mutable-default-arg',
        'pattern': r'def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\))',
        'message': 'Mutable default argument — shared across all calls (use None instead)',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python'],
    },
    {
        'id': 'global-variable',
        'pattern': r'^\s*global\s+\w+',
        'message': 'Global variable usage — makes code harder to test and maintain',
        'severity': 'low',
        'category': 'maintainability',
        'languages': ['python'],
    },
    {
        'id': 'unsafe-regex',
        'pattern': r're\.(compile|match|search|findall)\s*\(\s*["\'].*(\.\*|\.\+).*["\']',
        'message': 'Potential ReDoS (Regular Expression Denial of Service) with greedy quantifiers',
        'severity': 'medium',
        'category': 'security',
        'languages': ['python', 'javascript', 'java'],
    },
    {
        'id': 'no-timeout-request',
        'pattern': r'(?i)(requests\.(get|post|put|delete|patch)|fetch|axios\.(get|post))\s*\([^)]*\)(?!.*timeout)',
        'message': 'HTTP request without timeout — may hang indefinitely',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python'],
    },
    {
        'id': 'file-not-closed',
        'pattern': r'(?i)(\w+)\s*=\s*open\s*\((?!.*with\s)',
        'message': 'File opened without "with" statement — may not be properly closed',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python'],
    },
    {
        'id': 'insecure-file-permissions',
        'pattern': r'(?i)(chmod|os\.chmod)\s*\(.*0o?777',
        'message': 'World-writable file permissions (777) — use restrictive permissions',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'ruby', 'shell'],
    },
    {
        'id': 'race-condition',
        'pattern': r'(?i)if\s+(os\.path\.exists|os\.path\.isfile|os\.path\.isdir)\s*\(.*\)\s*:',
        'message': 'TOCTOU race condition — file may change between check and use',
        'severity': 'medium',
        'category': 'security',
        'languages': ['python'],
    },
    {
        'id': 'unvalidated-redirect',
        'pattern': r'(?i)(redirect|res\.redirect|response\.redirect)\s*\(\s*(req\.|request\.|params|args)',
        'message': 'Unvalidated redirect with user input — validate against whitelist',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'ruby', 'java', 'php'],
    },
    {
        'id': 'template-injection',
        'pattern': r'(?i)(render_template_string|Template\s*\().*(request\.|req\.|params)',
        'message': 'Potential Server-Side Template Injection (SSTI) — never pass user input to templates',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'javascript', 'java'],
    },
    {
        'id': 'unsafe-yaml',
        'pattern': r'yaml\.load\s*\((?!.*Loader\s*=\s*(yaml\.)?SafeLoader)',
        'message': 'yaml.load() without SafeLoader allows arbitrary code execution',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python'],
    },
    {
        'id': 'wildcard-import',
        'pattern': r'^from\s+\S+\s+import\s+\*',
        'message': 'Wildcard import pollutes namespace — import specific names',
        'severity': 'low',
        'category': 'maintainability',
        'languages': ['python'],
    },
    {
        'id': 'dangerously-set-html',
        'pattern': r'dangerouslySetInnerHTML',
        'message': 'dangerouslySetInnerHTML can introduce XSS — sanitize content first',
        'severity': 'high',
        'category': 'security',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'no-error-handling-promise',
        'pattern': r'\.then\s*\([^)]*\)\s*(?!\.catch)',
        'message': 'Promise without .catch() — unhandled rejections crash Node.js',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'var-usage',
        'pattern': r'\bvar\s+\w+',
        'message': 'Use of "var" — prefer "const" or "let" for block scoping',
        'severity': 'low',
        'category': 'maintainability',
        'languages': ['javascript'],
    },
    {
        'id': 'loose-equality',
        'pattern': r'[^!=]==[^=]',
        'message': 'Loose equality (==) — use strict equality (===) to avoid type coercion',
        'severity': 'low',
        'category': 'reliability',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'console-log',
        'pattern': r'console\.(log|debug|info)\s*\(',
        'message': 'Console logging found — remove before production deployment',
        'severity': 'low',
        'category': 'best-practice',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'todo-fixme',
        'pattern': r'(?i)(#|//|/\*)\s*(TODO|FIXME|HACK|XXX|BUG):?\s+',
        'message': 'Code contains TODO/FIXME marker that needs attention',
        'severity': 'low',
        'category': 'maintainability',
        'languages': ['python', 'javascript', 'typescript', 'java', 'go', 'ruby', 'php', 'c', 'c++', 'c#', 'kotlin', 'swift', 'rust', 'shell'],
    },
    {
        'id': 'hardcoded-port',
        'pattern': r'(?i)(listen|bind|port)\s*[\(=]\s*["\']?\d{4,5}["\']?',
        'message': 'Hardcoded port number — use configuration/environment variable',
        'severity': 'low',
        'category': 'best-practice',
        'languages': ['python', 'javascript', 'java', 'go', 'ruby', 'php'],
    },
    {
        'id': 'buffer-overflow-c',
        'pattern': r'(?i)\b(gets|sprintf|strcpy|strcat)\s*\(',
        'message': 'Unsafe C function — use bounds-checking alternatives (fgets, snprintf, strncpy)',
        'severity': 'critical',
        'category': 'security',
        'languages': ['c', 'c++'],
    },
    {
        'id': 'format-string-c',
        'pattern': r'(?i)(printf|fprintf|sprintf)\s*\(\s*\w+\s*\)',
        'message': 'Format string vulnerability — user-controlled format string',
        'severity': 'critical',
        'category': 'security',
        'languages': ['c', 'c++'],
    },
    {
        'id': 'memory-leak-c',
        'pattern': r'\bmalloc\s*\((?!.*free)',
        'message': 'Memory allocated with malloc() — ensure corresponding free() exists',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['c', 'c++'],
    },
    {
        'id': 'null-check-after-deref',
        'pattern': r'(\w+)->\w+.*\n.*if\s*\(\s*\1\s*[!=]=\s*NULL',
        'message': 'Pointer dereferenced before null check — check first',
        'severity': 'high',
        'category': 'reliability',
        'languages': ['c', 'c++'],
    },
    {
        'id': 'unsafe-unwrap',
        'pattern': r'\.(unwrap|expect)\s*\(\s*\)',
        'message': 'Unwrap on Result/Option may panic — handle error case explicitly',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['rust'],
    },
    {
        'id': 'go-error-ignored',
        'pattern': r'(?i)(\w+),\s*_\s*:?=\s*\w+\.\w+\s*\(',
        'message': 'Error return value ignored — always handle errors in Go',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['go'],
    },
    {
        'id': 'shell-injection',
        'pattern': r'(?i)(\$\(|`)\s*.*\$\{?\w+',
        'message': 'Variable in shell command substitution — may allow injection',
        'severity': 'high',
        'category': 'security',
        'languages': ['shell'],
    },
    {
        'id': 'php-type-juggling',
        'pattern': r'(?i)\$\w+\s*==\s*["\']',
        'message': 'Loose comparison in PHP — use === to prevent type juggling attacks',
        'severity': 'high',
        'category': 'security',
        'languages': ['php'],
    },
    {
        'id': 'php-file-include',
        'pattern': r'(?i)(include|require|include_once|require_once)\s*\(\s*\$',
        'message': 'Dynamic file inclusion with variable — potential Local File Inclusion (LFI)',
        'severity': 'critical',
        'category': 'security',
        'languages': ['php'],
    },
    {
        'id': 'nosql-injection',
        'pattern': r'(?i)\.(find|findOne|aggregate|updateOne|deleteOne)\s*\(.*\$\w+',
        'message': 'Potential NoSQL injection — sanitize user input in database queries',
        'severity': 'high',
        'category': 'security',
        'languages': ['javascript', 'typescript', 'python'],
    },
    {
        'id': 'timing-attack',
        'pattern': r'(?i)(password|token|secret|hash)\s*==\s*',
        'message': 'String comparison may be vulnerable to timing attacks — use constant-time compare',
        'severity': 'medium',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'go', 'ruby'],
    },
    {
        'id': 'deprecated-function',
        'pattern': r'(?i)\b(atoi|gets|tmpnam|mktemp)\s*\(',
        'message': 'Deprecated/unsafe function — use modern alternatives',
        'severity': 'medium',
        'category': 'maintainability',
        'languages': ['c', 'c++', 'python'],
    },
    {
        'id': 'logging-exception',
        'pattern': r'except\s+\w+.*:\s*\n\s*(pass|return)',
        'message': 'Exception caught but not logged — add logging for debugging',
        'severity': 'low',
        'category': 'reliability',
        'languages': ['python'],
    },
]


class StaticAnalyzer:
    """Runs static analysis using Semgrep or fallback regex patterns."""
    
    def __init__(self):
        self._semgrep_available = None
    
    def is_semgrep_available(self) -> bool:
        """Check if Semgrep CLI is installed."""
        if self._semgrep_available is None:
            try:
                result = subprocess.run(
                    ['semgrep', '--version'],
                    capture_output=True, text=True, timeout=10
                )
                self._semgrep_available = result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._semgrep_available = False
        return self._semgrep_available
    
    def run_analysis(self, repo_path: str, file_tree: list[dict] = None) -> list[dict]:
        """
        Run static analysis on a repository.
        Uses Semgrep if available, otherwise falls back to regex patterns.
        """
        if self.is_semgrep_available():
            issues = self._run_semgrep(repo_path)
        else:
            print("⚠️  Semgrep not installed, using fallback regex scanner")
            issues = self._run_regex_scanner(repo_path, file_tree)
        
        # Assign unique IDs to issues
        for i, issue in enumerate(issues):
            if 'id' not in issue or not issue['id']:
                fp = issue.get("file_path", "")
                ln = issue.get("line_number", 0)
                hash_str = hashlib.md5(f"{fp}{ln}".encode()).hexdigest()[:8]
                issue['id'] = f"issue_{i}_{hash_str}"
        
        return issues
    
    def _run_semgrep(self, repo_path: str) -> list[dict]:
        """Run Semgrep with auto config and parse results."""
        try:
            result = subprocess.run(
                [
                    'semgrep', 'scan',
                    '--config=auto',
                    '--json',
                    '--timeout=300',
                    '--max-target-bytes=1000000',
                    repo_path,
                ],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                cwd=repo_path,
            )
            
            if result.stdout:
                return self._parse_semgrep_results(result.stdout, repo_path)
            return []
            
        except subprocess.TimeoutExpired:
            print("⚠️  Semgrep analysis timed out")
            return []
        except Exception as e:
            print(f"⚠️  Semgrep error: {e}")
            return []
    
    def _parse_semgrep_results(self, json_output: str, repo_path: str) -> list[dict]:
        """Parse Semgrep JSON output into our issue format."""
        try:
            data = json.loads(json_output)
        except json.JSONDecodeError:
            return []
        
        issues = []
        results = data.get('results', [])
        
        for result in results:
            # Get relative file path
            file_path = result.get('path', '')
            if file_path.startswith(repo_path):
                file_path = os.path.relpath(file_path, repo_path)
            file_path = file_path.replace('\\', '/')
            
            # Map Semgrep severity to our severity levels
            semgrep_severity = result.get('extra', {}).get('severity', 'WARNING')
            severity = self._map_semgrep_severity(semgrep_severity)
            
            # Get code snippet
            lines = result.get('extra', {}).get('lines', '')
            
            # Extract issue type from rule ID
            rule_id = result.get('check_id', 'unknown')
            issue_type = self._extract_issue_type(rule_id)
            
            issues.append({
                'id': '',  # Will be assigned later
                'file_path': file_path,
                'line_number': result.get('start', {}).get('line', 0),
                'end_line': result.get('end', {}).get('line', 0),
                'column': result.get('start', {}).get('col', 0),
                'issue_type': issue_type,
                'severity': severity,
                'message': result.get('extra', {}).get('message', 'Issue detected'),
                'code_snippet': lines,
                'rule_id': rule_id,
                'category': result.get('extra', {}).get('metadata', {}).get('category', 'security'),
            })
        
        return issues
    
    def _map_semgrep_severity(self, severity: str) -> str:
        """Map Semgrep severity to our severity levels."""
        mapping = {
            'ERROR': 'high',
            'WARNING': 'medium',
            'INFO': 'low',
        }
        return mapping.get(severity.upper(), 'medium')
    
    def _extract_issue_type(self, rule_id: str) -> str:
        """Extract a human-readable issue type from rule ID."""
        # Common patterns in Semgrep rule IDs
        type_keywords = {
            'sql': 'sql-injection',
            'xss': 'xss',
            'injection': 'injection',
            'hardcoded': 'hardcoded-secret',
            'eval': 'code-injection',
            'exec': 'code-injection',
            'crypto': 'weak-crypto',
            'hash': 'weak-crypto',
            'deserialization': 'insecure-deserialization',
            'cors': 'cors-misconfiguration',
            'redirect': 'open-redirect',
            'path': 'path-traversal',
            'ssrf': 'ssrf',
            'csrf': 'csrf',
            'jwt': 'jwt-vulnerability',
        }
        
        rule_lower = rule_id.lower()
        for keyword, issue_type in type_keywords.items():
            if keyword in rule_lower:
                return issue_type
        
        # Extract last part of rule ID as type
        parts = rule_id.split('.')
        if parts:
            return parts[-1].replace('-', ' ').replace('_', '-')
        return 'security-issue'
    
    def _run_regex_scanner(self, repo_path: str, file_tree: list[dict] = None) -> list[dict]:
        """Fallback regex-based scanner when Semgrep isn't available."""
        issues = []
        
        # Determine which files to scan
        if file_tree:
            files_to_scan = [
                (os.path.join(repo_path, f['path']), f['language'], f['path'])
                for f in file_tree
                if f['language'] in (
                    'python', 'javascript', 'typescript', 'java',
                    'go', 'ruby', 'php', 'c', 'c++', 'c#',
                    'rust', 'kotlin', 'swift', 'shell',
                )
            ]
        else:
            files_to_scan = self._find_source_files(repo_path)
        
        for full_path, language, rel_path in files_to_scan:
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')
            except Exception:
                continue
            
            for rule in REGEX_RULES:
                if language not in rule['languages']:
                    continue
                
                for line_num, line in enumerate(lines, 1):
                    if re.search(rule['pattern'], line):
                        # Get surrounding code for snippet
                        start = max(0, line_num - 2)
                        end = min(len(lines), line_num + 2)
                        snippet = '\n'.join(lines[start:end])
                        
                        issues.append({
                            'id': '',
                            'file_path': rel_path,
                            'line_number': line_num,
                            'end_line': line_num,
                            'column': 1,
                            'issue_type': rule['id'],
                            'severity': rule['severity'],
                            'message': rule['message'],
                            'code_snippet': snippet,
                            'rule_id': f"regex.{rule['id']}",
                            'category': rule['category'],
                        })
        
        return issues
    
    def _find_source_files(self, repo_path: str) -> list[tuple]:
        """Find source files when file_tree isn't provided."""
        from app.services.git_service import GitService
        gs = GitService()
        tree = gs.get_file_tree(repo_path)
        return [
            (os.path.join(repo_path, f['path']), f['language'], f['path'])
            for f in tree
            if f['language'] in ('python', 'javascript', 'typescript', 'java')
        ]
    
    def calculate_health_score(self, issues: list[dict]) -> int:
        """
        Calculate code health score (0-100).
        Starts at 100 and deducts points per issue based on severity.
        """
        score = 100.0
        
        for issue in issues:
            severity = issue.get('severity', 'medium')
            base_penalty = SEVERITY_WEIGHTS.get(severity, 5)
            
            # Extra penalty for high-impact issue types
            issue_type = issue.get('issue_type', '')
            if issue_type in HIGH_IMPACT_TYPES:
                base_penalty *= 1.5
            
            score -= base_penalty
        
        # Floor at 0, cap at 100
        return max(0, min(100, int(score)))
    
    def get_health_grade(self, score: int) -> str:
        """Convert health score to letter grade."""
        if score >= 90: return 'A'
        if score >= 80: return 'B'
        if score >= 70: return 'C'
        if score >= 60: return 'D'
        return 'F'
    
    def get_severity_summary(self, issues: list[dict]) -> dict:
        """Count issues by severity."""
        summary = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        for issue in issues:
            severity = issue.get('severity', 'medium')
            if severity in summary:
                summary[severity] += 1
        return summary


# Singleton instance
static_analyzer = StaticAnalyzer()
