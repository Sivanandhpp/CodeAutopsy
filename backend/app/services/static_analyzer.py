"""
Static Analyzer Service
Runs DB-driven static analysis using pluggable engines.
"""

import hashlib
import logging

from sqlalchemy import select

from app.models.analysis_rule import AnalysisRule
from app.services.analysis_engines import EngineRegistry, RegexEngine, SemgrepEngine

logger = logging.getLogger(__name__)


# â”€â”€â”€ Severity Scoring â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SEVERITY_WEIGHTS = {
    'trace': 0,
    'info': 1,
    'low': 2,
    'medium': 5,
    'high': 10,
    'critical': 15,
    'blocker': 25,
}

# High-impact defect families get extra penalty
HIGH_IMPACT_FAMILIES = {
    'injection', 'path_traversal', 'deserialization', 'ssrf',
}

SCANNABLE_LANGUAGES = {
    'python', 'javascript', 'typescript', 'java', 'go', 'ruby', 'php',
    'c', 'c++', 'c#', 'rust', 'kotlin', 'swift', 'shell',
}


# --- Legacy Regex Patterns (migrated to DB) ---
# Kept for seed script compatibility until migration is verified.

REGEX_RULES = [
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # CRITICAL â€” Remote Code Execution, Injection, etc.
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    {
        'id': 'command-injection',
        'pattern': r'(?i)(os\.system|subprocess\.call|subprocess\.Popen|subprocess\.run|child_process\.exec|Runtime\.getRuntime\(\)\.exec)\s*\(.*[\+f"\{]',
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
        'message': 'SQL query built with string concatenation â€” use parameterized queries',
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
        'message': 'JWT verification disabled â€” tokens are not validated',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'javascript'],
    },
    {
        'id': 'insecure-deserialization',
        'pattern': r'(?i)(pickle\.loads?|yaml\.load\s*\((?!.*Loader)|unserialize|Marshal\.load|ObjectInputStream)',
        'message': 'Insecure deserialization â€” can lead to remote code execution',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'ruby', 'php'],
    },
    {
        'id': 'xxe-vulnerability',
        'pattern': r'(?i)(XMLParser|etree\.parse|SAXParser|DocumentBuilder).*(?!.*disable.*external)',
        'message': 'Potential XXE (XML External Entity) vulnerability â€” disable external entities',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'java', 'php', 'c#'],
    },

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # HIGH â€” Secrets, Auth, Crypto, Injection
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    {
        'id': 'hardcoded-secret',
        'pattern': r'(?i)(password|secret|api_key|apikey|token|access_key|private_key|secret_key)\s*=\s*["\'][^"\']{8,}["\']',
        'message': 'Potential hardcoded secret or credential â€” use environment variables',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'typescript', 'java', 'go', 'ruby', 'php', 'kotlin', 'swift', 'c#', 'rust'],
    },
    {
        'id': 'hardcoded-ip',
        'pattern': r'["\'](\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})["\']',
        'message': 'Hardcoded IP address found â€” use configuration or DNS',
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
        'message': 'Potential SSRF â€” user input in outbound HTTP request URL',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'go', 'ruby', 'php'],
    },
    {
        'id': 'insecure-hash',
        'pattern': r'(?i)(md5|sha1)\s*\(',
        'message': 'Use of weak cryptographic hash (MD5/SHA1) â€” use SHA-256 or bcrypt',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'php', 'ruby', 'go', 'c', 'c++'],
    },
    {
        'id': 'insecure-random',
        'pattern': r'(?i)\brandom\.(random|randint|choice|randrange)\b',
        'message': 'Use of non-cryptographic random â€” use secrets module for security-sensitive ops',
        'severity': 'high',
        'category': 'security',
        'languages': ['python'],
    },
    {
        'id': 'insecure-random-js',
        'pattern': r'Math\.random\s*\(\s*\)',
        'message': 'Math.random() is not cryptographically secure â€” use crypto.getRandomValues()',
        'severity': 'high',
        'category': 'security',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'prototype-pollution',
        'pattern': r'(?i)(Object\.assign|__proto__|constructor\s*\[)',
        'message': 'Potential prototype pollution â€” validate input object keys',
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
        'message': 'CORS wildcard (*) allows any origin â€” may expose sensitive data',
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
        'message': 'Sensitive data may be logged â€” mask credentials before logging',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'typescript', 'java', 'go', 'ruby', 'php'],
    },

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # MEDIUM â€” Reliability, Robustness, Code Smell
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    {
        'id': 'null-pointer',
        'pattern': r'(?i)(\w+)\.(length|size|count|trim|split|strip|upper|lower|replace|append|extend|keys|values|items)\s*\(',
        'message': 'Potential null/None pointer dereference â€” add null check before method call',
        'severity': 'medium',
        'category': 'reliability',
        'languages': [],  # too noisy as-is, we handle this differently below
    },
    {
        'id': 'null-dereference-pattern',
        'pattern': r'(?i)(result|response|data|user|obj|record|item|row|node)\s*\[\s*["\']',
        'message': 'Accessing property on potentially null variable â€” add null guard',
        'severity': 'low',
        'category': 'reliability',
        'languages': [],  # disabled â€” too many false positives
    },
    {
        'id': 'division-by-zero',
        'pattern': r'(?i)\b\w+\s*/\s*(?:\w+\s*)(?:#|//|/\*)?$',
        'message': 'Potential division by zero â€” add zero-check before dividing',
        'severity': 'medium',
        'category': 'reliability',
        'languages': [],  # disabled â€” regex too imprecise
    },
    {
        'id': 'unchecked-division',
        'pattern': r'(?i)(\s/\s+(?:len|count|size|total|num)\s*\()',
        'message': 'Division by result of len/count/size â€” may be zero for empty collections',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python', 'javascript', 'java', 'go', 'ruby'],
    },
    {
        'id': 'empty-except',
        'pattern': r'except\s*:\s*\n\s*(pass|\.\.\.)',
        'message': 'Empty except clause silently catches all exceptions â€” handle or log errors',
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
        'message': 'Empty catch block silently swallows errors â€” log or handle the exception',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['javascript', 'typescript', 'java', 'c#', 'kotlin'],
    },
    {
        'id': 'debug-enabled',
        'pattern': r'(?i)debug\s*=\s*true',
        'message': 'Debug mode enabled â€” should be disabled in production',
        'severity': 'medium',
        'category': 'best-practice',
        'languages': ['python', 'javascript', 'java', 'php', 'ruby', 'go'],
    },
    {
        'id': 'http-not-https',
        'pattern': r'["\']http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)',
        'message': 'Insecure HTTP URL â€” use HTTPS for external connections',
        'severity': 'medium',
        'category': 'security',
        'languages': ['python', 'javascript', 'typescript', 'java', 'go', 'ruby', 'php', 'c#', 'kotlin', 'swift'],
    },
    {
        'id': 'disabled-ssl-verify',
        'pattern': r'(?i)(verify\s*=\s*false|ssl_verify\s*=\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*["\']0|InsecureSkipVerify:\s*true)',
        'message': 'SSL/TLS certificate verification disabled â€” vulnerable to MITM attacks',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'go', 'java', 'ruby'],
    },
    {
        'id': 'assert-in-production',
        'pattern': r'^\s*assert\s+',
        'message': 'Assert statements are stripped in optimized mode â€” use proper validation',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python'],
    },
    {
        'id': 'mutable-default-arg',
        'pattern': r'def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\))',
        'message': 'Mutable default argument â€” shared across all calls (use None instead)',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python'],
    },
    {
        'id': 'global-variable',
        'pattern': r'^\s*global\s+\w+',
        'message': 'Global variable usage â€” makes code harder to test and maintain',
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
        'message': 'HTTP request without timeout â€” may hang indefinitely',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python'],
    },
    {
        'id': 'file-not-closed',
        'pattern': r'(?i)(\w+)\s*=\s*open\s*\((?!.*with\s)',
        'message': 'File opened without "with" statement â€” may not be properly closed',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['python'],
    },
    {
        'id': 'insecure-file-permissions',
        'pattern': r'(?i)(chmod|os\.chmod)\s*\(.*0o?777',
        'message': 'World-writable file permissions (777) â€” use restrictive permissions',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'ruby', 'shell'],
    },
    {
        'id': 'race-condition',
        'pattern': r'(?i)if\s+(os\.path\.exists|os\.path\.isfile|os\.path\.isdir)\s*\(.*\)\s*:',
        'message': 'TOCTOU race condition â€” file may change between check and use',
        'severity': 'medium',
        'category': 'security',
        'languages': ['python'],
    },
    {
        'id': 'unvalidated-redirect',
        'pattern': r'(?i)(redirect|res\.redirect|response\.redirect)\s*\(\s*(req\.|request\.|params|args)',
        'message': 'Unvalidated redirect with user input â€” validate against whitelist',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'ruby', 'java', 'php'],
    },
    {
        'id': 'template-injection',
        'pattern': r'(?i)(render_template_string|Template\s*\().*(request\.|req\.|params)',
        'message': 'Potential Server-Side Template Injection (SSTI) â€” never pass user input to templates',
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
        'message': 'Wildcard import pollutes namespace â€” import specific names',
        'severity': 'low',
        'category': 'maintainability',
        'languages': ['python'],
    },
    {
        'id': 'dangerously-set-html',
        'pattern': r'dangerouslySetInnerHTML',
        'message': 'dangerouslySetInnerHTML can introduce XSS â€” sanitize content first',
        'severity': 'high',
        'category': 'security',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'no-error-handling-promise',
        'pattern': r'\.then\s*\([^)]*\)\s*(?!\.catch)',
        'message': 'Promise without .catch() â€” unhandled rejections crash Node.js',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'var-usage',
        'pattern': r'\bvar\s+\w+',
        'message': 'Use of "var" â€” prefer "const" or "let" for block scoping',
        'severity': 'low',
        'category': 'maintainability',
        'languages': ['javascript'],
    },
    {
        'id': 'loose-equality',
        'pattern': r'[^!=]==[^=]',
        'message': 'Loose equality (==) â€” use strict equality (===) to avoid type coercion',
        'severity': 'low',
        'category': 'reliability',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'console-log',
        'pattern': r'console\.(log|debug|info|warn|error)\s*\(',
        'message': 'Console statements found â€” verify if this should be in production or if it logs sensitive data',
        'severity': 'low',
        'category': 'best-practice',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'python-print',
        'pattern': r'^\s*print\s*\(',
        'message': 'Print statement used instead of proper logging framework',
        'severity': 'low',
        'category': 'best-practice',
        'languages': ['python'],
    },
    {
        'id': 'react-missing-deps',
        'pattern': r'useEffect\s*\(\s*\(\)\s*=>\s*\{(?![^}]*\}\s*,)',
        'message': 'useEffect might be missing a dependency array, causing it to run on every render',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'todo-fixme',
        'pattern': r'(?i)(#|//|/\*)\s*(TODO|FIXME|HACK|XXX|BUG)',
        'message': 'Code contains TODO/FIXME marker that needs attention',
        'severity': 'low',
        'category': 'maintainability',
        'languages': ['python', 'javascript', 'typescript', 'java', 'go', 'ruby', 'php', 'c', 'c++', 'c#', 'kotlin', 'swift', 'rust', 'shell'],
    },
    {
        'id': 'hardcoded-port',
        'pattern': r'(?i)(listen|bind|port)\s*[\(=]\s*["\']?\d{4,5}["\']?',
        'message': 'Hardcoded port number â€” use configuration/environment variable',
        'severity': 'low',
        'category': 'best-practice',
        'languages': ['python', 'javascript', 'java', 'go', 'ruby', 'php'],
    },
    {
        'id': 'buffer-overflow-c',
        'pattern': r'(?i)\b(gets|sprintf|strcpy|strcat)\s*\(',
        'message': 'Unsafe C function â€” use bounds-checking alternatives (fgets, snprintf, strncpy)',
        'severity': 'critical',
        'category': 'security',
        'languages': ['c', 'c++'],
    },
    {
        'id': 'format-string-c',
        'pattern': r'(?i)(printf|fprintf|sprintf)\s*\(\s*\w+\s*\)',
        'message': 'Format string vulnerability â€” user-controlled format string',
        'severity': 'critical',
        'category': 'security',
        'languages': ['c', 'c++'],
    },
    {
        'id': 'memory-leak-c',
        'pattern': r'\bmalloc\s*\((?!.*free)',
        'message': 'Memory allocated with malloc() â€” ensure corresponding free() exists',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['c', 'c++'],
    },
    {
        'id': 'null-check-after-deref',
        'pattern': r'(\w+)->\w+.*\n.*if\s*\(\s*\1\s*[!=]=\s*NULL',
        'message': 'Pointer dereferenced before null check â€” check first',
        'severity': 'high',
        'category': 'reliability',
        'languages': ['c', 'c++'],
    },
    {
        'id': 'unsafe-unwrap',
        'pattern': r'\.(unwrap|expect)\s*\(\s*\)',
        'message': 'Unwrap on Result/Option may panic â€” handle error case explicitly',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['rust'],
    },
    {
        'id': 'go-error-ignored',
        'pattern': r'(?i)(\w+),\s*_\s*:?=\s*\w+\.\w+\s*\(',
        'message': 'Error return value ignored â€” always handle errors in Go',
        'severity': 'medium',
        'category': 'reliability',
        'languages': ['go'],
    },
    {
        'id': 'shell-injection',
        'pattern': r'(?i)(\$\(|`)\s*.*\$\{?\w+',
        'message': 'Variable in shell command substitution â€” may allow injection',
        'severity': 'high',
        'category': 'security',
        'languages': ['shell'],
    },
    {
        'id': 'php-type-juggling',
        'pattern': r'(?i)\$\w+\s*==\s*["\']',
        'message': 'Loose comparison in PHP â€” use === to prevent type juggling attacks',
        'severity': 'high',
        'category': 'security',
        'languages': ['php'],
    },
    {
        'id': 'php-file-include',
        'pattern': r'(?i)(include|require|include_once|require_once)\s*\(\s*\$',
        'message': 'Dynamic file inclusion with variable â€” potential Local File Inclusion (LFI)',
        'severity': 'critical',
        'category': 'security',
        'languages': ['php'],
    },
    {
        'id': 'nosql-injection',
        'pattern': r'(?i)\.(find|findOne|aggregate|updateOne|deleteOne)\s*\(.*\$\w+',
        'message': 'Potential NoSQL injection â€” sanitize user input in database queries',
        'severity': 'high',
        'category': 'security',
        'languages': ['javascript', 'typescript', 'python'],
    },
    {
        'id': 'timing-attack',
        'pattern': r'(?i)(password|token|secret|hash)\s*==\s*',
        'message': 'String comparison may be vulnerable to timing attacks â€” use constant-time compare',
        'severity': 'medium',
        'category': 'security',
        'languages': ['python', 'javascript', 'java', 'go', 'ruby'],
    },
    {
        'id': 'deprecated-function',
        'pattern': r'(?i)\b(atoi|gets|tmpnam|mktemp)\s*\(',
        'message': 'Deprecated/unsafe function â€” use modern alternatives',
        'severity': 'medium',
        'category': 'maintainability',
        'languages': ['c', 'c++', 'python'],
    },
    {
        'id': 'logging-exception',
        'pattern': r'except\s+\w+.*:\s*\n\s*(pass|return)',
        'message': 'Exception caught but not logged â€” add logging for debugging',
        'severity': 'low',
        'category': 'reliability',
        'languages': ['python'],
    },
]


class StaticAnalyzer:
    """Runs static analysis using registered analysis engines."""

    def __init__(self):
        pass

    async def run_analysis(
        self,
        repo_path: str,
        db,
        file_tree: list[dict] | None = None,
    ) -> list[dict]:
        """Run static analysis on a repository using DB-driven rules."""
        regex_rules, semgrep_rules = await self._load_rules(db)

        registry = EngineRegistry()
        registry.register(RegexEngine(repo_path, regex_rules))
        registry.register(SemgrepEngine(repo_path, semgrep_rules))

        issues: list[dict] = []
        files_to_scan = self._get_files_to_scan(repo_path, file_tree)
        for rel_path, language in files_to_scan:
            findings = await registry.run_all(rel_path, language)
            for finding in findings:
                data = finding.model_dump()
                data.setdefault("issue_type", data.get("rule_id", ""))
                data["category"] = data.get("defect_family")
                issues.append(data)

        self._assign_ids(issues)
        return issues

    async def _load_rules(self, db) -> tuple[list[dict], dict[str, dict]]:
        """Load active rules from the database once per analysis run."""
        result = await db.execute(
            select(AnalysisRule).where(
                AnalysisRule.is_active.is_(True),
                AnalysisRule.match_type.in_(
                    ("regex_line", "regex_multiline", "ast_semgrep")
                ),
            )
        )
        rules = result.scalars().all()

        regex_rules: list[dict] = []
        semgrep_rules: dict[str, dict] = {}
        for rule in rules:
            rule_dict = self._rule_to_dict(rule)
            if rule.match_type in ("regex_line", "regex_multiline"):
                regex_rules.append(rule_dict)
            elif rule.match_type == "ast_semgrep":
                semgrep_rules[rule.rule_id] = rule_dict
        return regex_rules, semgrep_rules

    @staticmethod
    def _rule_to_dict(rule: AnalysisRule) -> dict:
        return {
            "rule_id": rule.rule_id,
            "name": rule.name,
            "description": rule.description,
            "language": rule.language,
            "defect_family": rule.defect_family,
            "severity": rule.severity,
            "pattern": rule.pattern,
            "match_type": rule.match_type,
            "message": rule.message,
            "fix_hint": rule.fix_hint,
            "cwe_id": rule.cwe_id,
            "owasp_ref": rule.owasp_ref,
        }

    @staticmethod
    def _assign_ids(issues: list[dict]) -> None:
        for i, issue in enumerate(issues):
            if issue.get("id"):
                continue
            fp = issue.get("file_path", "")
            ln = issue.get("line_number", 0)
            rule_id = issue.get("rule_id", "")
            hash_str = hashlib.md5(f"{fp}{ln}{rule_id}".encode()).hexdigest()[:8]
            issue["id"] = f"issue_{i}_{hash_str}"

    def _get_files_to_scan(
        self,
        repo_path: str,
        file_tree: list[dict] | None,
    ) -> list[tuple[str, str]]:
        if file_tree:
            return [
                (f["path"], f["language"])
                for f in file_tree
                if f.get("language") in SCANNABLE_LANGUAGES
            ]
        return self._find_source_files(repo_path)

    def _find_source_files(self, repo_path: str) -> list[tuple[str, str]]:
        """Find source files using FileFilter for fast, smart selection."""
        from app.services.file_filter import FileFilter
        from app.services.git_service import GitService

        gs = GitService()
        ff = FileFilter(repo_path)
        user_files = ff.user_authored_files(max_files=100)

        result: list[tuple[str, str]] = []
        for fpath in user_files:
            rel_path = str(fpath.relative_to(repo_path)).replace("\\", "/")
            language = gs.detect_language(fpath.name)
            if language in SCANNABLE_LANGUAGES:
                result.append((rel_path, language))
        return result
    
    def calculate_health_score(self, issues: list[dict]) -> int:
        """
        Calculate code health score (0-100).
        Starts at 100 and deducts points per issue based on severity.
        """
        score = 100.0
        
        for issue in issues:
            severity = issue.get('severity', 'medium')
            base_penalty = SEVERITY_WEIGHTS.get(severity, 5)

            # Extra penalty for high-impact defect families
            defect_family = issue.get('defect_family', '')
            if defect_family in HIGH_IMPACT_FAMILIES:
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
        summary = {
            'blocker': 0,
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'info': 0,
            'trace': 0,
        }
        for issue in issues:
            severity = issue.get('severity', 'medium')
            if severity in summary:
                summary[severity] += 1
        return summary


# Singleton instance
static_analyzer = StaticAnalyzer()

