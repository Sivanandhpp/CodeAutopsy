"""Seed analysis_rules with comprehensive regex rules across all major languages.

Covers: Python, JavaScript, TypeScript, Dart, Go, Java, Rust, C/C++, PHP, Ruby, Kotlin, Swift
Run:
    python -m app.db.seeds.rules_seed
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.database import get_session_factory
from app.models.analysis_rule import AnalysisRule


# ---------------------------------------------------------------------------
# Defect family → one of the 12 canonical CodeAutopsy families
# ---------------------------------------------------------------------------
DEFECT_FAMILY_MAP: dict[str, str] = {
    # ── Injection ──────────────────────────────────────────────────────────
    "command-injection":           "injection",
    "sql-injection":               "injection",
    "sql-injection-concatenation": "injection",
    "xxe-vulnerability":           "injection",
    "eval-usage":                  "injection",
    "exec-usage":                  "injection",
    "prototype-pollution":         "injection",
    "template-injection":          "injection",
    "shell-injection":             "injection",
    "nosql-injection":             "injection",
    "format-string-c":             "injection",
    "ldap-injection":              "injection",
    "xpath-injection":             "injection",
    "expression-injection":        "injection",
    "server-side-template":        "injection",
    "log4j-jndi":                  "injection",
    "ognl-injection":              "injection",
    "spel-injection":              "injection",
    "groovy-injection":            "injection",
    "js-eval-injection":           "injection",
    "ruby-eval-injection":         "injection",
    "ruby-send-injection":         "injection",
    "kotlin-eval-injection":       "injection",
    "swift-eval-injection":        "injection",
    "dart-eval-injection":         "injection",
    "go-os-exec":                  "injection",
    "php-exec-injection":          "injection",
    "php-system-injection":        "injection",
    "rust-command-injection":      "injection",
    "java-runtime-exec":           "injection",
    "java-processbuilder":         "injection",

    # ── XSS ───────────────────────────────────────────────────────────────
    "xss-innerhtml":               "xss",
    "xss-document-write":          "xss",
    "dangerously-set-html":        "xss",
    "xss-outerhtml":               "xss",
    "xss-insertadjacenthtml":      "xss",
    "xss-dom-srcdoc":              "xss",
    "xss-location-href":           "xss",
    "xss-jquery-html":             "xss",
    "xss-jquery-append":           "xss",
    "xss-jquery-prepend":          "xss",
    "dart-xss-sethtml":            "xss",
    "php-echo-xss":                "xss",
    "php-print-xss":               "xss",
    "ruby-html-safe":              "xss",
    "java-xss-response-write":     "xss",
    "kotlin-xss-response":         "xss",
    "swift-xss-wkwebview":         "xss",

    # ── Auth ──────────────────────────────────────────────────────────────
    "jwt-no-verify":               "auth",
    "open-redirect":               "auth",
    "insecure-cookie":             "auth",
    "cors-wildcard":               "auth",
    "missing-csrf":                "auth",
    "unvalidated-redirect":        "auth",
    "php-type-juggling":           "auth",
    "hardcoded-password":          "auth",
    "weak-password-policy":        "auth",
    "session-fixation":            "auth",
    "broken-access-control":       "auth",
    "jwt-weak-secret":             "auth",
    "jwt-none-algorithm":          "auth",
    "oauth-state-missing":         "auth",
    "auth-bypass-empty-password":  "auth",
    "dart-insecure-http":          "auth",
    "go-jwt-no-verify":            "auth",
    "java-hardcoded-password":     "auth",
    "kotlin-insecure-ssl":         "auth",
    "swift-insecure-ssl":          "auth",
    "ruby-skip-verification":      "auth",
    "php-session-regenerate":      "auth",
    "rust-hardcoded-credentials":  "auth",

    # ── Path Traversal ────────────────────────────────────────────────────
    "path-traversal":              "path_traversal",
    "php-file-include":            "path_traversal",
    "zip-slip":                    "path_traversal",
    "path-traversal-join":         "path_traversal",
    "dart-path-traversal":         "path_traversal",
    "go-path-traversal":           "path_traversal",
    "java-path-traversal":         "path_traversal",
    "kotlin-path-traversal":       "path_traversal",
    "swift-path-traversal":        "path_traversal",
    "ruby-path-traversal":         "path_traversal",
    "rust-path-traversal":         "path_traversal",
    "php-path-traversal":          "path_traversal",

    # ── SSRF ──────────────────────────────────────────────────────────────
    "ssrf":                        "ssrf",
    "ssrf-http-client":            "ssrf",
    "dart-ssrf":                   "ssrf",
    "go-ssrf":                     "ssrf",
    "java-ssrf":                   "ssrf",
    "kotlin-ssrf":                 "ssrf",
    "ruby-ssrf":                   "ssrf",
    "php-ssrf":                    "ssrf",
    "rust-ssrf":                   "ssrf",

    # ── Crypto ────────────────────────────────────────────────────────────
    "insecure-hash":               "crypto",
    "insecure-random":             "crypto",
    "insecure-random-js":          "crypto",
    "http-not-https":              "crypto",
    "disabled-ssl-verify":         "crypto",
    "timing-attack":               "crypto",
    "weak-cipher-ecb":             "crypto",
    "weak-cipher-des":             "crypto",
    "hardcoded-iv":                "crypto",
    "hardcoded-encryption-key":    "crypto",
    "insecure-rsa-keysize":        "crypto",
    "no-certificate-validation":   "crypto",
    "dart-insecure-random":        "crypto",
    "dart-md5":                    "crypto",
    "dart-sha1":                   "crypto",
    "go-weak-hash":                "crypto",
    "go-insecure-tls":             "crypto",
    "java-weak-cipher":            "crypto",
    "java-weak-hash":              "crypto",
    "kotlin-weak-cipher":          "crypto",
    "swift-weak-hash":             "crypto",
    "swift-insecure-random":       "crypto",
    "ruby-insecure-hash":          "crypto",
    "php-weak-hash":               "crypto",
    "rust-weak-hash":              "crypto",
    "c-weak-hash":                 "crypto",

    # ── Secrets ───────────────────────────────────────────────────────────
    "hardcoded-secret":            "secrets",
    "sensitive-data-logging":      "secrets",
    "hardcoded-api-key":           "secrets",
    "hardcoded-aws-key":           "secrets",
    "hardcoded-aws-secret":        "secrets",
    "hardcoded-gcp-key":           "secrets",
    "hardcoded-azure-key":         "secrets",
    "hardcoded-private-key":       "secrets",
    "hardcoded-oauth-token":       "secrets",
    "hardcoded-github-token":      "secrets",
    "hardcoded-stripe-key":        "secrets",
    "hardcoded-twilio-key":        "secrets",
    "hardcoded-sendgrid-key":      "secrets",
    "env-secret-logged":           "secrets",

    # ── Deserialization ───────────────────────────────────────────────────
    "insecure-deserialization":    "deserialization",
    "unsafe-yaml":                 "deserialization",
    "pickle-usage":                "deserialization",
    "java-ois-readobject":         "deserialization",
    "java-xstream":                "deserialization",
    "java-kryo":                   "deserialization",
    "php-unserialize":             "deserialization",
    "ruby-yaml-load":              "deserialization",
    "ruby-marshal-load":           "deserialization",
    "dart-json-unsafe":            "deserialization",
    "go-gob-decode":               "deserialization",
    "kotlin-java-ois":             "deserialization",
    "rust-serde-untrusted":        "deserialization",
    "node-node-serialize":         "deserialization",

    # ── Reliability ───────────────────────────────────────────────────────
    "null-pointer":                "reliability",
    "null-dereference-pattern":    "reliability",
    "division-by-zero":            "reliability",
    "unchecked-division":          "reliability",
    "empty-except":                "reliability",
    "bare-except":                 "reliability",
    "empty-catch-js":              "reliability",
    "assert-in-production":        "reliability",
    "mutable-default-arg":         "reliability",
    "unsafe-regex":                "reliability",
    "no-timeout-request":          "reliability",
    "file-not-closed":             "reliability",
    "race-condition":              "reliability",
    "no-error-handling-promise":   "reliability",
    "loose-equality":              "reliability",
    "react-missing-deps":          "reliability",
    "buffer-overflow-c":           "reliability",
    "memory-leak-c":               "reliability",
    "null-check-after-deref":      "reliability",
    "unsafe-unwrap":               "reliability",
    "go-error-ignored":            "reliability",
    "logging-exception":           "reliability",
    "negative-array-index":        "reliability",
    "integer-overflow":            "reliability",
    "use-after-free":              "reliability",
    "double-free":                 "reliability",
    "dart-null-assert":            "reliability",
    "dart-empty-catch":            "reliability",
    "go-nil-dereference":          "reliability",
    "java-null-dereference":       "reliability",
    "java-empty-catch":            "reliability",
    "kotlin-force-unwrap":         "reliability",
    "kotlin-empty-catch":          "reliability",
    "swift-force-unwrap":          "reliability",
    "swift-empty-catch":           "reliability",
    "ruby-rescue-all":             "reliability",
    "php-null-coalesce-missing":   "reliability",
    "rust-unwrap-panic":           "reliability",
    "rust-expect-panic":           "reliability",
    "js-floating-promise":         "reliability",
    "js-async-constructor":        "reliability",
    "js-nan-comparison":           "reliability",
    "ts-any-type":                 "reliability",
    "ts-non-null-assertion":       "reliability",

    # ── Best Practice ─────────────────────────────────────────────────────
    "hardcoded-ip":                "best_practice",
    "debug-enabled":               "best_practice",
    "console-log":                 "best_practice",
    "python-print":                "best_practice",
    "var-usage":                   "best_practice",
    "insecure-file-permissions":   "best_practice",
    "hardcoded-port":              "best_practice",
    "dart-print-debug":            "best_practice",
    "dart-hardcoded-color":        "best_practice",
    "go-fmt-print":                "best_practice",
    "java-system-out":             "best_practice",
    "kotlin-println":              "best_practice",
    "swift-print-debug":           "best_practice",
    "ruby-puts-debug":             "best_practice",
    "php-var-dump":                "best_practice",
    "php-debug-mode":              "best_practice",
    "rust-dbg-macro":              "best_practice",
    "c-gets-usage":                "best_practice",
    "c-strcpy-usage":              "best_practice",
    "js-alert-usage":              "best_practice",
    "missing-input-validation":    "best_practice",
    "overly-permissive-file":      "best_practice",

    # ── Maintainability ───────────────────────────────────────────────────
    "global-variable":             "maintainability",
    "wildcard-import":             "maintainability",
    "todo-fixme":                  "maintainability",
    "deprecated-function":         "maintainability",
    "dart-magic-number":           "maintainability",
    "go-magic-number":             "maintainability",
    "java-magic-number":           "maintainability",
    "kotlin-magic-number":         "maintainability",
    "swift-magic-number":          "maintainability",
    "ruby-magic-number":           "maintainability",
    "long-method":                 "maintainability",
    "js-no-var":                   "maintainability",
    "ts-explicit-any":             "maintainability",
}


# ---------------------------------------------------------------------------
# Severity overrides for noisy / low-signal rules
# ---------------------------------------------------------------------------
SEVERITY_OVERRIDE: dict[str, str] = {
    "console-log":              "trace",
    "python-print":             "trace",
    "dart-print-debug":         "trace",
    "go-fmt-print":             "trace",
    "java-system-out":          "trace",
    "kotlin-println":           "trace",
    "swift-print-debug":        "trace",
    "ruby-puts-debug":          "trace",
    "php-var-dump":             "trace",
    "rust-dbg-macro":           "trace",
    "js-alert-usage":           "trace",
    "todo-fixme":               "info",
    "var-usage":                "info",
    "js-no-var":                "info",
    "wildcard-import":          "info",
    "hardcoded-port":           "info",
    "hardcoded-ip":             "info",
    "dart-magic-number":        "info",
    "go-magic-number":          "info",
    "java-magic-number":        "info",
    "kotlin-magic-number":      "info",
    "swift-magic-number":       "info",
    "ruby-magic-number":        "info",
    "ts-explicit-any":          "info",
    "ts-any-type":              "info",
    "deprecated-function":      "low",
    "long-method":              "info",
}


# ---------------------------------------------------------------------------
# Master rule catalogue
# Format: id, severity, languages, pattern, message
# ---------------------------------------------------------------------------
EXPANDED_RULES: list[dict] = [

    # ════════════════════════════════════════════════════════════════════════
    # PYTHON
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "sql-injection", "severity": "critical",
        "languages": ["python"],
        "pattern": r"(execute|executemany)\s*\(\s*[\"'][^\"']*%[sd]",
        "message": "SQL query built with % string formatting — use parameterised queries.",
    },
    {
        "id": "sql-injection-concatenation", "severity": "critical",
        "languages": ["python"],
        "pattern": r"(execute|executemany)\s*\(\s*[\"'][^\"']*\"\s*\+",
        "message": "SQL query built with string concatenation — use parameterised queries.",
    },
    {
        "id": "command-injection", "severity": "critical",
        "languages": ["python"],
        "pattern": r"(os\.system|subprocess\.(call|run|Popen|check_output))\s*\(\s*[^)]*\+",
        "message": "Shell command built with user-controlled input — use subprocess with a list and shell=False.",
    },
    {
        "id": "eval-usage", "severity": "critical",
        "languages": ["python"],
        "pattern": r"\beval\s*\(",
        "message": "eval() executes arbitrary code — never pass user input to eval().",
    },
    {
        "id": "exec-usage", "severity": "high",
        "languages": ["python"],
        "pattern": r"\bexec\s*\(",
        "message": "exec() executes arbitrary code — avoid or tightly sandbox.",
    },
    {
        "id": "pickle-usage", "severity": "high",
        "languages": ["python"],
        "pattern": r"\bpickle\.(loads?|Unpickler)\b",
        "message": "Pickle deserialization of untrusted data can lead to RCE.",
    },
    {
        "id": "unsafe-yaml", "severity": "high",
        "languages": ["python"],
        "pattern": r"yaml\.load\s*\([^)]*\)",
        "message": "yaml.load() with arbitrary input is unsafe — use yaml.safe_load().",
    },
    {
        "id": "insecure-hash", "severity": "medium",
        "languages": ["python"],
        "pattern": r"hashlib\.(md5|sha1)\s*\(",
        "message": "MD5/SHA1 are cryptographically broken — use SHA-256 or stronger.",
    },
    {
        "id": "insecure-random", "severity": "medium",
        "languages": ["python"],
        "pattern": r"\brandom\.(random|randint|choice|shuffle)\s*\(",
        "message": "random module is not cryptographically secure — use secrets module.",
    },
    {
        "id": "hardcoded-secret", "severity": "critical",
        "languages": ["python"],
        "pattern": r"(password|secret|token|api_key)\s*=\s*[\"'][^\"']{6,}[\"']",
        "message": "Hardcoded secret detected — use environment variables or a vault.",
    },
    {
        "id": "hardcoded-api-key", "severity": "critical",
        "languages": ["python"],
        "pattern": r"(api_key|apikey|auth_token)\s*=\s*[\"'][A-Za-z0-9_\-]{16,}[\"']",
        "message": "Hardcoded API key — rotate and move to environment variables.",
    },
    {
        "id": "sensitive-data-logging", "severity": "high",
        "languages": ["python"],
        "pattern": r"(logging|logger)\.(info|debug|warning|error)\s*\(.*?(password|token|secret|key)",
        "message": "Sensitive data being written to logs.",
    },
    {
        "id": "bare-except", "severity": "low",
        "languages": ["python"],
        "pattern": r"except\s*:",
        "message": "Bare except clause swallows all exceptions including KeyboardInterrupt.",
    },
    {
        "id": "empty-except", "severity": "low",
        "languages": ["python"],
        "pattern": r"except\s+\w+.*:\s*\n\s*pass",
        "message": "Exception silently swallowed with pass — at minimum log the error.",
    },
    {
        "id": "mutable-default-arg", "severity": "medium",
        "languages": ["python"],
        "pattern": r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|\(\))",
        "message": "Mutable default argument — shared across all calls, use None instead.",
    },
    {
        "id": "assert-in-production", "severity": "medium",
        "languages": ["python"],
        "pattern": r"^\s*assert\s+",
        "message": "assert statements are removed by Python's -O flag — use explicit checks.",
    },
    {
        "id": "path-traversal", "severity": "high",
        "languages": ["python"],
        "pattern": r"open\s*\(\s*.*\+",
        "message": "File path built with concatenation — validate and sanitise against traversal.",
    },
    {
        "id": "template-injection", "severity": "high",
        "languages": ["python"],
        "pattern": r"Template\s*\(\s*(request|input|data)",
        "message": "Server-side template injection risk — never pass user input as the template string.",
    },
    {
        "id": "disabled-ssl-verify", "severity": "high",
        "languages": ["python"],
        "pattern": r"verify\s*=\s*False",
        "message": "SSL certificate verification disabled — vulnerable to MITM attacks.",
    },
    {
        "id": "http-not-https", "severity": "medium",
        "languages": ["python"],
        "pattern": r"[\"']http://(?!localhost|127\.0\.0\.1)",
        "message": "Plain HTTP URL — use HTTPS for any non-local communication.",
    },
    {
        "id": "no-timeout-request", "severity": "medium",
        "languages": ["python"],
        "pattern": r"requests\.(get|post|put|delete|patch|head)\s*\([^)]*\)",
        "message": "HTTP request without timeout — can hang indefinitely, always pass timeout=.",
    },
    {
        "id": "python-print", "severity": "trace",
        "languages": ["python"],
        "pattern": r"^\s*print\s*\(",
        "message": "print() in production code — use the logging module.",
    },
    {
        "id": "global-variable", "severity": "info",
        "languages": ["python"],
        "pattern": r"^\s*global\s+\w+",
        "message": "Global variable mutation makes code harder to test and reason about.",
    },
    {
        "id": "wildcard-import", "severity": "info",
        "languages": ["python"],
        "pattern": r"from\s+\S+\s+import\s+\*",
        "message": "Wildcard import pollutes the namespace — import explicitly.",
    },
    {
        "id": "todo-fixme", "severity": "info",
        "languages": ["python", "javascript", "typescript", "dart", "go", "java", "kotlin", "swift", "ruby", "php", "rust", "c", "cpp"],
        "pattern": r"#\s*(TODO|FIXME|HACK|XXX|BUG)\b",
        "message": "Unresolved TODO/FIXME marker — track in issue tracker.",
    },
    {
        "id": "debug-enabled", "severity": "high",
        "languages": ["python"],
        "pattern": r"DEBUG\s*=\s*True",
        "message": "DEBUG mode enabled — never deploy to production with DEBUG=True.",
    },
    {
        "id": "ssrf", "severity": "high",
        "languages": ["python"],
        "pattern": r"requests\.(get|post)\s*\(\s*(request\.|input|data\[)",
        "message": "Potential SSRF — URL derived from user input without validation.",
    },
    {
        "id": "logging-exception", "severity": "low",
        "languages": ["python"],
        "pattern": r"except\s+\w+\s+as\s+\w+:\s*\n\s*(pass|continue)",
        "message": "Exception caught but not logged — silent failures are hard to debug.",
    },
    {
        "id": "timing-attack", "severity": "medium",
        "languages": ["python"],
        "pattern": r"==\s*[\"'][0-9a-fA-F]{32,}[\"']",
        "message": "Direct string equality on secrets is vulnerable to timing attacks — use hmac.compare_digest.",
    },
    {
        "id": "insecure-file-permissions", "severity": "medium",
        "languages": ["python"],
        "pattern": r"os\.chmod\s*\([^,]+,\s*0o?7[0-7]{2}",
        "message": "World-writable permissions (0o7xx) set on file.",
    },
    {
        "id": "file-not-closed", "severity": "medium",
        "languages": ["python"],
        "pattern": r"open\s*\([^)]+\)(?!\s*as\s)",
        "message": "File opened without context manager — use `with open(...)` to ensure closure.",
    },
    {
        "id": "unsafe-regex", "severity": "medium",
        "languages": ["python"],
        "pattern": r"re\.(match|search|fullmatch)\s*\(\s*[\"'][^\"']*(\.\*|\+){2}",
        "message": "Potentially catastrophic backtracking in regex — simplify the pattern.",
    },
    {
        "id": "hardcoded-aws-key", "severity": "critical",
        "languages": ["python", "javascript", "typescript", "dart", "go", "java", "kotlin", "swift", "ruby", "php", "rust"],
        "pattern": r"AKIA[0-9A-Z]{16}",
        "message": "Hardcoded AWS Access Key ID detected — revoke immediately.",
    },
    {
        "id": "hardcoded-private-key", "severity": "critical",
        "languages": ["python", "javascript", "typescript", "dart", "go", "java", "kotlin", "swift", "ruby", "php", "rust"],
        "pattern": r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "message": "Private key material embedded in source — remove and rotate.",
    },
    {
        "id": "hardcoded-github-token", "severity": "critical",
        "languages": ["python", "javascript", "typescript", "dart", "go", "java", "kotlin", "swift", "ruby", "php", "rust"],
        "pattern": r"ghp_[A-Za-z0-9]{36}",
        "message": "GitHub personal access token detected in source — revoke immediately.",
    },

    # ════════════════════════════════════════════════════════════════════════
    # JAVASCRIPT / TYPESCRIPT
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "xss-innerhtml", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"\.innerHTML\s*=\s*(?!`[^`]*`\s*;)",
        "message": "Assigning to innerHTML with dynamic data can cause XSS.",
    },
    {
        "id": "xss-outerhtml", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"\.outerHTML\s*=",
        "message": "Assigning to outerHTML with dynamic data can cause XSS.",
    },
    {
        "id": "xss-insertadjacenthtml", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"\.insertAdjacentHTML\s*\(",
        "message": "insertAdjacentHTML with user data causes XSS — use textContent or sanitise.",
    },
    {
        "id": "xss-document-write", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"document\.write\s*\(",
        "message": "document.write() with user-controlled data leads to XSS.",
    },
    {
        "id": "xss-dom-srcdoc", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"\.(srcdoc|src)\s*=\s*[^\"';]+\+",
        "message": "Setting srcdoc/src from concatenated string may allow XSS.",
    },
    {
        "id": "xss-location-href", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"location\.href\s*=\s*(?!(\"https?://|'https?://))",
        "message": "Setting location.href from user input can allow javascript: XSS.",
    },
    {
        "id": "xss-jquery-html", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"\$\([^)]+\)\.html\s*\(",
        "message": "jQuery .html() with user input causes XSS — use .text().",
    },
    {
        "id": "xss-jquery-append", "severity": "medium",
        "languages": ["javascript", "typescript"],
        "pattern": r"\$\([^)]+\)\.(append|prepend|after|before)\s*\(",
        "message": "jQuery DOM insertion with user input may cause XSS.",
    },
    {
        "id": "dangerously-set-html", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"dangerouslySetInnerHTML\s*=\s*\{",
        "message": "dangerouslySetInnerHTML used — ensure value is sanitised.",
    },
    {
        "id": "js-eval-injection", "severity": "critical",
        "languages": ["javascript", "typescript"],
        "pattern": r"\beval\s*\(",
        "message": "eval() executes arbitrary code — never pass user input.",
    },
    {
        "id": "prototype-pollution", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"\[__proto__\]|\[\"__proto__\"\]|Object\.assign\s*\(\s*\{\},",
        "message": "Potential prototype pollution — validate and sanitise merge keys.",
    },
    {
        "id": "insecure-random-js", "severity": "medium",
        "languages": ["javascript", "typescript"],
        "pattern": r"Math\.random\s*\(\s*\)",
        "message": "Math.random() is not cryptographically secure — use crypto.getRandomValues().",
    },
    {
        "id": "hardcoded-secret", "severity": "critical",
        "languages": ["javascript", "typescript"],
        "pattern": r"(password|secret|token|apiKey|api_key)\s*[:=]\s*[\"'][^\"']{6,}[\"']",
        "message": "Hardcoded secret — use environment variables.",
    },
    {
        "id": "cors-wildcard", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"[\"']Access-Control-Allow-Origin[\"']\s*[:]\s*[\"']\*[\"']",
        "message": "CORS wildcard allows any origin — restrict to trusted domains.",
    },
    {
        "id": "jwt-no-verify", "severity": "critical",
        "languages": ["javascript", "typescript"],
        "pattern": r"jwt\.decode\s*\(",
        "message": "jwt.decode() skips signature verification — use jwt.verify().",
    },
    {
        "id": "jwt-none-algorithm", "severity": "critical",
        "languages": ["javascript", "typescript"],
        "pattern": r"algorithm[s]?\s*:\s*[\"']none[\"']",
        "message": "JWT 'none' algorithm disables signature verification entirely.",
    },
    {
        "id": "var-usage", "severity": "info",
        "languages": ["javascript"],
        "pattern": r"\bvar\s+\w+",
        "message": "var has function scope — prefer const or let.",
    },
    {
        "id": "console-log", "severity": "trace",
        "languages": ["javascript", "typescript"],
        "pattern": r"\bconsole\.(log|debug|info|warn|error)\s*\(",
        "message": "console statement left in code — remove before production.",
    },
    {
        "id": "no-error-handling-promise", "severity": "medium",
        "languages": ["javascript", "typescript"],
        "pattern": r"\.then\s*\([^)]+\)(?!\s*\.catch)",
        "message": "Promise chain without .catch() — unhandled rejections can crash Node.js.",
    },
    {
        "id": "js-floating-promise", "severity": "medium",
        "languages": ["javascript", "typescript"],
        "pattern": r"^\s*(async\s+)?\w+\s*\([^)]*\)\s*;$",
        "message": "Floating promise — await the result or handle explicitly.",
    },
    {
        "id": "loose-equality", "severity": "low",
        "languages": ["javascript", "typescript"],
        "pattern": r"[^!=!]==[^=]|[^!]!=[^=]",
        "message": "Loose equality (== / !=) can cause type coercion bugs — use === / !==.",
    },
    {
        "id": "js-nan-comparison", "severity": "medium",
        "languages": ["javascript", "typescript"],
        "pattern": r"===\s*NaN|NaN\s*===",
        "message": "NaN !== NaN — use Number.isNaN() to check.",
    },
    {
        "id": "hardcoded-ip", "severity": "info",
        "languages": ["javascript", "typescript"],
        "pattern": r"[\"']\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}[\"']",
        "message": "Hardcoded IP address — use configuration / DNS.",
    },
    {
        "id": "path-traversal", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"(readFile|createReadStream|require)\s*\([^)]*\+",
        "message": "File path built from concatenation — sanitise against path traversal.",
    },
    {
        "id": "ssrf-http-client", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"(fetch|axios\.get|http\.get|https\.get)\s*\(\s*(req\.|request\.|params\.|query\.)",
        "message": "Potential SSRF — HTTP request URL derived from user-controlled input.",
    },
    {
        "id": "node-node-serialize", "severity": "critical",
        "languages": ["javascript", "typescript"],
        "pattern": r"require\s*\(\s*[\"']node-serialize[\"']\s*\)",
        "message": "node-serialize is vulnerable to RCE via deserialization (CVE-2017-5941).",
    },
    {
        "id": "unsafe-regex", "severity": "medium",
        "languages": ["javascript", "typescript"],
        "pattern": r"new RegExp\s*\([^)]*\)",
        "message": "Dynamic RegExp from user input can enable ReDoS — validate pattern first.",
    },
    {
        "id": "ts-non-null-assertion", "severity": "medium",
        "languages": ["typescript"],
        "pattern": r"\w+!\.|\w+!\[",
        "message": "Non-null assertion (!) bypasses TypeScript's null checks — handle null explicitly.",
    },
    {
        "id": "ts-explicit-any", "severity": "info",
        "languages": ["typescript"],
        "pattern": r":\s*any\b",
        "message": "Explicit any type disables type safety — use a specific type or unknown.",
    },
    {
        "id": "js-async-constructor", "severity": "medium",
        "languages": ["javascript", "typescript"],
        "pattern": r"constructor\s*\([^)]*\)\s*\{[^}]*await\s",
        "message": "Async operations in constructor are unreliable — use a static factory method.",
    },
    {
        "id": "react-missing-deps", "severity": "medium",
        "languages": ["javascript", "typescript"],
        "pattern": r"useEffect\s*\(\s*\(\s*\)\s*=>",
        "message": "useEffect with possible missing dependency array — add deps or ESLint rule.",
    },
    {
        "id": "shell-injection", "severity": "critical",
        "languages": ["javascript", "typescript"],
        "pattern": r"(exec|execSync|spawn|spawnSync)\s*\(\s*[`\"'][^`\"']*\$\{",
        "message": "Shell command built with template literal interpolation — use array form.",
    },
    {
        "id": "sensitive-data-logging", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"console\.(log|info|debug)\s*\(.*?(password|token|secret|apiKey)",
        "message": "Sensitive data written to console.",
    },
    {
        "id": "insecure-cookie", "severity": "medium",
        "languages": ["javascript", "typescript"],
        "pattern": r"(cookie|Cookie)\s*=\s*[^;](?!.*httpOnly)(?!.*secure)",
        "message": "Cookie set without HttpOnly/Secure flags.",
    },
    {
        "id": "open-redirect", "severity": "high",
        "languages": ["javascript", "typescript"],
        "pattern": r"res\.(redirect|location)\s*\(\s*(req\.|request\.)",
        "message": "Open redirect — validate redirect target against an allowlist.",
    },

    # ════════════════════════════════════════════════════════════════════════
    # DART / FLUTTER
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "dart-eval-injection", "severity": "critical",
        "languages": ["dart"],
        "pattern": r"\beval\s*\(",
        "message": "eval() is dangerous — never execute user-controlled strings.",
    },
    {
        "id": "dart-insecure-http", "severity": "high",
        "languages": ["dart"],
        "pattern": r"[\"']http://(?!localhost|127\.0\.0\.1)",
        "message": "Plain HTTP URL — Flutter requires HTTPS for non-local traffic; enable cleartext only intentionally.",
    },
    {
        "id": "dart-insecure-random", "severity": "medium",
        "languages": ["dart"],
        "pattern": r"\bRandom\s*\(\s*\)",
        "message": "dart:math Random is not cryptographically secure — use Random.secure() for security-sensitive values.",
    },
    {
        "id": "dart-md5", "severity": "medium",
        "languages": ["dart"],
        "pattern": r"\bmd5\s*\(",
        "message": "MD5 is cryptographically broken — use SHA-256 or stronger.",
    },
    {
        "id": "dart-sha1", "severity": "medium",
        "languages": ["dart"],
        "pattern": r"\bsha1\s*\(",
        "message": "SHA-1 is deprecated for security use — upgrade to SHA-256.",
    },
    {
        "id": "dart-null-assert", "severity": "medium",
        "languages": ["dart"],
        "pattern": r"\w+!\.",
        "message": "Null assertion operator (!) will throw if value is null at runtime.",
    },
    {
        "id": "dart-empty-catch", "severity": "low",
        "languages": ["dart"],
        "pattern": r"catch\s*\([^)]+\)\s*\{\s*\}",
        "message": "Empty catch block silently swallows exceptions.",
    },
    {
        "id": "dart-path-traversal", "severity": "high",
        "languages": ["dart"],
        "pattern": r"File\s*\(\s*[^)]*\+",
        "message": "File path built from concatenation — validate against traversal.",
    },
    {
        "id": "dart-ssrf", "severity": "high",
        "languages": ["dart"],
        "pattern": r"(http\.get|http\.post|Dio\(\)\.get|Dio\(\)\.post)\s*\(\s*[^)]*\+",
        "message": "HTTP request URL built from user input — SSRF risk.",
    },
    {
        "id": "dart-xss-sethtml", "severity": "high",
        "languages": ["dart"],
        "pattern": r"element\.setInnerHtml\s*\(",
        "message": "setInnerHtml without sanitisation causes XSS in Flutter Web.",
    },
    {
        "id": "dart-json-unsafe", "severity": "medium",
        "languages": ["dart"],
        "pattern": r"jsonDecode\s*\([^)]*\)(?!\s*as\s)",
        "message": "Untyped jsonDecode result — cast/validate before use to prevent runtime errors.",
    },
    {
        "id": "dart-print-debug", "severity": "trace",
        "languages": ["dart"],
        "pattern": r"^\s*print\s*\(",
        "message": "print() in production — use a logging package instead.",
    },
    {
        "id": "dart-hardcoded-color", "severity": "info",
        "languages": ["dart"],
        "pattern": r"Color\s*\(\s*0x[Ff][Ff][0-9A-Fa-f]{6}\s*\)",
        "message": "Hardcoded Color value — use a design token / theme.",
    },
    {
        "id": "dart-magic-number", "severity": "info",
        "languages": ["dart"],
        "pattern": r"(?<![A-Za-z_])[2-9][0-9]{2,}(?![A-Za-z_])",
        "message": "Magic number — extract to a named constant.",
    },
    {
        "id": "hardcoded-secret", "severity": "critical",
        "languages": ["dart"],
        "pattern": r"(apiKey|secretKey|password|token)\s*=\s*[\"'][^\"']{8,}[\"']",
        "message": "Hardcoded secret in Dart source — use --dart-define or a secrets manager.",
    },

    # ════════════════════════════════════════════════════════════════════════
    # GO
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "go-os-exec", "severity": "critical",
        "languages": ["go"],
        "pattern": r"exec\.Command\s*\([^)]*\+",
        "message": "Shell command built from string concatenation — use slice args to prevent injection.",
    },
    {
        "id": "go-error-ignored", "severity": "medium",
        "languages": ["go"],
        "pattern": r",\s*_\s*:?=\s*\w+\s*\(",
        "message": "Error return value discarded with _ — handle or log the error.",
    },
    {
        "id": "go-nil-dereference", "severity": "high",
        "languages": ["go"],
        "pattern": r"if\s+\w+\s*!=\s*nil\s*\{[^}]*\}\s*\w+\.",
        "message": "Potential nil dereference after guard — ensure all code paths are covered.",
    },
    {
        "id": "go-weak-hash", "severity": "medium",
        "languages": ["go"],
        "pattern": r'"crypto/(md5|sha1)"',
        "message": "MD5/SHA1 imported — use crypto/sha256 or stronger.",
    },
    {
        "id": "go-insecure-tls", "severity": "high",
        "languages": ["go"],
        "pattern": r"InsecureSkipVerify\s*:\s*true",
        "message": "TLS certificate verification disabled — vulnerable to MITM.",
    },
    {
        "id": "go-path-traversal", "severity": "high",
        "languages": ["go"],
        "pattern": r"(os\.Open|ioutil\.ReadFile)\s*\([^)]*\+",
        "message": "File path built from concatenation — sanitise against path traversal.",
    },
    {
        "id": "go-ssrf", "severity": "high",
        "languages": ["go"],
        "pattern": r"http\.(Get|Post)\s*\(\s*\w*(req|r)\.",
        "message": "HTTP request URL from request parameter — SSRF risk.",
    },
    {
        "id": "go-jwt-no-verify", "severity": "critical",
        "languages": ["go"],
        "pattern": r"ParseUnverified\s*\(",
        "message": "JWT parsed without verification — use Parse() with a key function.",
    },
    {
        "id": "go-fmt-print", "severity": "trace",
        "languages": ["go"],
        "pattern": r"\bfmt\.(Print|Println|Printf)\s*\(",
        "message": "fmt.Print in production code — use structured logging (zap, zerolog).",
    },
    {
        "id": "go-magic-number", "severity": "info",
        "languages": ["go"],
        "pattern": r"(?<![A-Za-z_])[2-9][0-9]{2,}(?![A-Za-z_0-9])",
        "message": "Magic number — extract to a named const.",
    },
    {
        "id": "go-gob-decode", "severity": "high",
        "languages": ["go"],
        "pattern": r"gob\.NewDecoder\s*\(",
        "message": "gob deserialization of untrusted data can panic — validate source.",
    },

    # ════════════════════════════════════════════════════════════════════════
    # JAVA
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "java-runtime-exec", "severity": "critical",
        "languages": ["java"],
        "pattern": r"Runtime\.getRuntime\(\)\.exec\s*\(",
        "message": "Runtime.exec() with user input leads to OS command injection.",
    },
    {
        "id": "java-processbuilder", "severity": "critical",
        "languages": ["java"],
        "pattern": r"new\s+ProcessBuilder\s*\(",
        "message": "ProcessBuilder with user-controlled args leads to command injection.",
    },
    {
        "id": "java-ois-readobject", "severity": "critical",
        "languages": ["java"],
        "pattern": r"ObjectInputStream\s*\(",
        "message": "Java deserialization via ObjectInputStream is a common RCE vector.",
    },
    {
        "id": "java-xstream", "severity": "critical",
        "languages": ["java"],
        "pattern": r"new\s+XStream\s*\(\s*\)",
        "message": "XStream deserialization of untrusted XML can lead to RCE.",
    },
    {
        "id": "java-weak-cipher", "severity": "high",
        "languages": ["java"],
        "pattern": r"Cipher\.getInstance\s*\(\s*[\"'](DES|RC2|RC4|Blowfish)[\"']",
        "message": "Weak cipher algorithm — use AES/GCM.",
    },
    {
        "id": "java-weak-hash", "severity": "medium",
        "languages": ["java"],
        "pattern": r"MessageDigest\.getInstance\s*\(\s*[\"'](MD5|SHA-?1)[\"']",
        "message": "Weak hash algorithm — use SHA-256 or stronger.",
    },
    {
        "id": "java-null-dereference", "severity": "high",
        "languages": ["java"],
        "pattern": r"(\w+)\s*=\s*\w+\.get\([^)]+\);\s*\1\.",
        "message": "Object returned from map/collection used without null check.",
    },
    {
        "id": "java-empty-catch", "severity": "low",
        "languages": ["java"],
        "pattern": r"catch\s*\([^)]+\)\s*\{\s*\}",
        "message": "Empty catch block swallows exception silently.",
    },
    {
        "id": "java-path-traversal", "severity": "high",
        "languages": ["java"],
        "pattern": r"new\s+File\s*\(\s*[^)]*\+",
        "message": "File path built from concatenation — sanitise against traversal.",
    },
    {
        "id": "java-ssrf", "severity": "high",
        "languages": ["java"],
        "pattern": r"new\s+URL\s*\(\s*[^)]*request\.",
        "message": "URL constructed from request parameter — SSRF risk.",
    },
    {
        "id": "java-xss-response-write", "severity": "high",
        "languages": ["java"],
        "pattern": r"response\.getWriter\(\)\.print(ln)?\s*\(\s*request\.",
        "message": "Response writes request parameter directly — XSS risk.",
    },
    {
        "id": "java-hardcoded-password", "severity": "critical",
        "languages": ["java"],
        "pattern": r"(password|passwd|secret)\s*=\s*[\"'][^\"']{4,}[\"']",
        "message": "Hardcoded password in Java source.",
    },
    {
        "id": "java-system-out", "severity": "trace",
        "languages": ["java"],
        "pattern": r"System\.out\.(print|println|printf)\s*\(",
        "message": "System.out in production — use SLF4J/Logback.",
    },
    {
        "id": "java-magic-number", "severity": "info",
        "languages": ["java"],
        "pattern": r"(?<![A-Za-z_])[2-9][0-9]{3,}(?![A-Za-z_])",
        "message": "Magic number — extract to a named constant.",
    },
    {
        "id": "log4j-jndi", "severity": "blocker",
        "languages": ["java"],
        "pattern": r"\$\{jndi:",
        "message": "Log4Shell pattern detected (CVE-2021-44228) — patch Log4j immediately.",
    },
    {
        "id": "spel-injection", "severity": "critical",
        "languages": ["java"],
        "pattern": r"new\s+SpelExpressionParser\s*\(\s*\)",
        "message": "SpEL expression parser — never evaluate user-supplied expressions.",
    },
    {
        "id": "java-kryo", "severity": "high",
        "languages": ["java"],
        "pattern": r"new\s+Kryo\s*\(\s*\)",
        "message": "Kryo deserialization of untrusted data can be exploited.",
    },

    # ════════════════════════════════════════════════════════════════════════
    # KOTLIN
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "kotlin-force-unwrap", "severity": "high",
        "languages": ["kotlin"],
        "pattern": r"\w+!!\.",
        "message": "!! non-null assertion throws NullPointerException — use safe call ?. or null checks.",
    },
    {
        "id": "kotlin-empty-catch", "severity": "low",
        "languages": ["kotlin"],
        "pattern": r"catch\s*\([^)]+\)\s*\{\s*\}",
        "message": "Empty catch block — at minimum log the exception.",
    },
    {
        "id": "kotlin-insecure-ssl", "severity": "high",
        "languages": ["kotlin"],
        "pattern": r"hostnameVerifier\s*=\s*HostnameVerifier\s*\{[^}]*true\s*\}",
        "message": "Hostname verification disabled — vulnerable to MITM.",
    },
    {
        "id": "kotlin-weak-cipher", "severity": "high",
        "languages": ["kotlin"],
        "pattern": r"Cipher\.getInstance\s*\(\s*[\"'](DES|RC4|Blowfish)[\"']",
        "message": "Weak cipher — use AES/GCM.",
    },
    {
        "id": "kotlin-path-traversal", "severity": "high",
        "languages": ["kotlin"],
        "pattern": r"File\s*\(\s*[^)]*\+",
        "message": "File path from concatenation — validate against traversal.",
    },
    {
        "id": "kotlin-ssrf", "severity": "high",
        "languages": ["kotlin"],
        "pattern": r"URL\s*\(\s*[^)]*request\.",
        "message": "URL from request parameter — SSRF risk.",
    },
    {
        "id": "kotlin-xss-response", "severity": "high",
        "languages": ["kotlin"],
        "pattern": r"response\.writer\.print(ln)?\s*\(\s*request\.",
        "message": "Response reflects request parameter — XSS risk.",
    },
    {
        "id": "kotlin-eval-injection", "severity": "critical",
        "languages": ["kotlin"],
        "pattern": r"ScriptEngineManager\s*\(\s*\).*eval\s*\(",
        "message": "ScriptEngine.eval() with user input leads to code injection.",
    },
    {
        "id": "kotlin-java-ois", "severity": "critical",
        "languages": ["kotlin"],
        "pattern": r"ObjectInputStream\s*\(",
        "message": "Java deserialization via ObjectInputStream — common RCE vector.",
    },
    {
        "id": "kotlin-println", "severity": "trace",
        "languages": ["kotlin"],
        "pattern": r"\bprintln\s*\(",
        "message": "println() in production — use a logging framework.",
    },
    {
        "id": "kotlin-magic-number", "severity": "info",
        "languages": ["kotlin"],
        "pattern": r"(?<![A-Za-z_])[2-9][0-9]{3,}(?![A-Za-z_])",
        "message": "Magic number — extract to a named constant.",
    },

    # ════════════════════════════════════════════════════════════════════════
    # SWIFT
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "swift-force-unwrap", "severity": "high",
        "languages": ["swift"],
        "pattern": r"\w+!\.",
        "message": "Force unwrap (!) will crash on nil — use if let / guard let / optional chaining.",
    },
    {
        "id": "swift-empty-catch", "severity": "low",
        "languages": ["swift"],
        "pattern": r"catch\s*\{[^}]*\}",
        "message": "Empty catch block swallows errors silently.",
    },
    {
        "id": "swift-insecure-ssl", "severity": "high",
        "languages": ["swift"],
        "pattern": r"NSAllowsArbitraryLoads\s*=\s*<true\s*/>",
        "message": "NSAllowsArbitraryLoads bypasses App Transport Security.",
    },
    {
        "id": "swift-weak-hash", "severity": "medium",
        "languages": ["swift"],
        "pattern": r"CC_MD5\s*\(|CC_SHA1\s*\(",
        "message": "MD5/SHA1 in CommonCrypto — use CC_SHA256 or CryptoKit SHA256.",
    },
    {
        "id": "swift-insecure-random", "severity": "medium",
        "languages": ["swift"],
        "pattern": r"\barc4random\s*\(",
        "message": "arc4random is deprecated — use SystemRandomNumberGenerator or SecRandomCopyBytes.",
    },
    {
        "id": "swift-path-traversal", "severity": "high",
        "languages": ["swift"],
        "pattern": r"FileManager\.default\.(contents|createFile)\s*\(atPath:\s*[^,)]*\+",
        "message": "File path from concatenation — sanitise against traversal.",
    },
    {
        "id": "swift-xss-wkwebview", "severity": "high",
        "languages": ["swift"],
        "pattern": r"evaluateJavaScript\s*\(\s*[^)]*\+",
        "message": "evaluateJavaScript with dynamic string — XSS risk in WKWebView.",
    },
    {
        "id": "swift-eval-injection", "severity": "critical",
        "languages": ["swift"],
        "pattern": r"NSExpression\s*\(format:\s*[^)]*\+",
        "message": "NSExpression with user-controlled format string — code injection risk.",
    },
    {
        "id": "swift-print-debug", "severity": "trace",
        "languages": ["swift"],
        "pattern": r"\b(print|debugPrint|dump)\s*\(",
        "message": "Debug print in production — use os_log or Swift Logging.",
    },
    {
        "id": "swift-magic-number", "severity": "info",
        "languages": ["swift"],
        "pattern": r"(?<![A-Za-z_])[2-9][0-9]{3,}(?![A-Za-z_])",
        "message": "Magic number — extract to a named constant.",
    },
    {
        "id": "swift-insecure-ssl", "severity": "high",
        "languages": ["swift"],
        "pattern": r"URLSessionConfiguration\.\w+\.tlsMinimumSupportedProtocol\s*=\s*\.tlsProtocol1",
        "message": "TLS 1.0/1.1 allowed — set minimum to TLS 1.2 or higher.",
    },

    # ════════════════════════════════════════════════════════════════════════
    # RUBY
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "ruby-eval-injection", "severity": "critical",
        "languages": ["ruby"],
        "pattern": r"\beval\s*\(",
        "message": "eval() executes arbitrary Ruby — never pass user input.",
    },
    {
        "id": "ruby-send-injection", "severity": "high",
        "languages": ["ruby"],
        "pattern": r"\.(send|public_send)\s*\(\s*params",
        "message": "Calling send() with user-controlled method name — arbitrary method invocation.",
    },
    {
        "id": "ruby-yaml-load", "severity": "high",
        "languages": ["ruby"],
        "pattern": r"YAML\.(load|unsafe_load)\s*\(",
        "message": "YAML.load() of untrusted input leads to RCE — use YAML.safe_load().",
    },
    {
        "id": "ruby-marshal-load", "severity": "critical",
        "languages": ["ruby"],
        "pattern": r"Marshal\.load\s*\(",
        "message": "Marshal.load() of untrusted data leads to RCE.",
    },
    {
        "id": "ruby-html-safe", "severity": "high",
        "languages": ["ruby"],
        "pattern": r"\.html_safe\s*$",
        "message": "html_safe on user-controlled string bypasses Rails XSS protection.",
    },
    {
        "id": "ruby-skip-verification", "severity": "high",
        "languages": ["ruby"],
        "pattern": r"OpenSSL::SSL::VERIFY_NONE",
        "message": "SSL verification disabled — vulnerable to MITM.",
    },
    {
        "id": "ruby-path-traversal", "severity": "high",
        "languages": ["ruby"],
        "pattern": r"File\.(read|open|write)\s*\(\s*[^)]*params",
        "message": "File path derived from params — path traversal risk.",
    },
    {
        "id": "ruby-ssrf", "severity": "high",
        "languages": ["ruby"],
        "pattern": r"(Net::HTTP\.get|open-uri|HTTParty\.get)\s*\(\s*[^)]*params",
        "message": "HTTP request URL from params — SSRF risk.",
    },
    {
        "id": "ruby-rescue-all", "severity": "low",
        "languages": ["ruby"],
        "pattern": r"rescue\s*Exception\b",
        "message": "rescue Exception catches SignalException and SystemExit — rescue StandardError instead.",
    },
    {
        "id": "ruby-insecure-hash", "severity": "medium",
        "languages": ["ruby"],
        "pattern": r"Digest::(MD5|SHA1)\.(hexdigest|digest)\s*\(",
        "message": "MD5/SHA1 in Digest — use Digest::SHA256 or bcrypt for passwords.",
    },
    {
        "id": "ruby-puts-debug", "severity": "trace",
        "languages": ["ruby"],
        "pattern": r"\bputs\s+",
        "message": "puts() in production — use Rails.logger.",
    },
    {
        "id": "ruby-magic-number", "severity": "info",
        "languages": ["ruby"],
        "pattern": r"(?<![A-Za-z_:])[2-9][0-9]{3,}(?![A-Za-z_])",
        "message": "Magic number — extract to a named constant.",
    },
    {
        "id": "php-session-regenerate", "severity": "medium",  # grouped here but belongs to PHP
        "languages": ["ruby"],
        "pattern": r"session\[:user_id\]\s*=",
        "message": "Session assigned without reset_session — potential session fixation.",
    },

    # ════════════════════════════════════════════════════════════════════════
    # PHP
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "php-exec-injection", "severity": "critical",
        "languages": ["php"],
        "pattern": r"\b(exec|shell_exec|system|passthru|popen)\s*\(\s*\$",
        "message": "Shell function called with PHP variable — command injection risk.",
    },
    {
        "id": "php-system-injection", "severity": "critical",
        "languages": ["php"],
        "pattern": r"\bsystem\s*\(\s*\$_(GET|POST|REQUEST|COOKIE)",
        "message": "system() called with superglobal input — OS command injection.",
    },
    {
        "id": "php-echo-xss", "severity": "high",
        "languages": ["php"],
        "pattern": r"echo\s+\$_(GET|POST|REQUEST|COOKIE)",
        "message": "Echoing superglobal input directly — XSS risk.",
    },
    {
        "id": "php-print-xss", "severity": "high",
        "languages": ["php"],
        "pattern": r"print\s+\$_(GET|POST|REQUEST|COOKIE)",
        "message": "Printing superglobal input directly — XSS risk.",
    },
    {
        "id": "php-type-juggling", "severity": "high",
        "languages": ["php"],
        "pattern": r"==\s*0|0\s*==|==\s*\"0\"|\"0\"\s*==",
        "message": "Loose comparison with 0 enables type juggling auth bypass — use ===.",
    },
    {
        "id": "php-file-include", "severity": "critical",
        "languages": ["php"],
        "pattern": r"\b(include|require|include_once|require_once)\s*\(\s*\$",
        "message": "Dynamic file include from variable — LFI/RFI risk.",
    },
    {
        "id": "php-path-traversal", "severity": "high",
        "languages": ["php"],
        "pattern": r"file_(get_contents|put_contents|open)\s*\(\s*\$_(GET|POST|REQUEST)",
        "message": "File operation with superglobal path — path traversal risk.",
    },
    {
        "id": "php-ssrf", "severity": "high",
        "languages": ["php"],
        "pattern": r"(curl_setopt\s*\([^,]+,\s*CURLOPT_URL|file_get_contents)\s*\(\s*\$_(GET|POST|REQUEST)",
        "message": "HTTP request to user-supplied URL — SSRF risk.",
    },
    {
        "id": "php-unserialize", "severity": "critical",
        "languages": ["php"],
        "pattern": r"\bunserialize\s*\(\s*\$",
        "message": "unserialize() of user-controlled data leads to RCE.",
    },
    {
        "id": "php-weak-hash", "severity": "medium",
        "languages": ["php"],
        "pattern": r"\b(md5|sha1)\s*\(",
        "message": "MD5/SHA1 used for hashing — use password_hash() for passwords, SHA-256+ for data.",
    },
    {
        "id": "php-debug-mode", "severity": "high",
        "languages": ["php"],
        "pattern": r"(ini_set|error_reporting)\s*\(\s*[\"']?(display_errors|E_ALL)",
        "message": "Error display enabled — leaks stack traces in production.",
    },
    {
        "id": "php-var-dump", "severity": "trace",
        "languages": ["php"],
        "pattern": r"\b(var_dump|print_r|var_export)\s*\(",
        "message": "Debug output function left in code.",
    },
    {
        "id": "nosql-injection", "severity": "high",
        "languages": ["php", "javascript", "typescript", "python"],
        "pattern": r"\[\s*[\"']\$where[\"']\s*\]",
        "message": "MongoDB $where operator with user data enables NoSQL injection.",
    },

    # ════════════════════════════════════════════════════════════════════════
    # RUST
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "rust-command-injection", "severity": "critical",
        "languages": ["rust"],
        "pattern": r"Command::new\s*\([^)]*\)\s*\.arg\s*\(",
        "message": "Command with user-supplied args — validate input to prevent injection.",
    },
    {
        "id": "rust-unwrap-panic", "severity": "medium",
        "languages": ["rust"],
        "pattern": r"\.unwrap\s*\(\s*\)",
        "message": ".unwrap() panics on None/Err — use ? operator or proper error handling.",
    },
    {
        "id": "rust-expect-panic", "severity": "low",
        "languages": ["rust"],
        "pattern": r"\.expect\s*\(\s*[\"'][^\"']+[\"']\s*\)",
        "message": ".expect() panics on None/Err — handle in production paths.",
    },
    {
        "id": "rust-weak-hash", "severity": "medium",
        "languages": ["rust"],
        "pattern": r"(md5|sha1)::(Md5|Sha1)",
        "message": "MD5/SHA1 — use SHA-256 (sha2 crate) or stronger.",
    },
    {
        "id": "rust-hardcoded-credentials", "severity": "critical",
        "languages": ["rust"],
        "pattern": r"(password|secret|token|api_key)\s*=\s*[\"'][^\"']{6,}[\"']",
        "message": "Hardcoded credentials in Rust source — use env vars or a secrets vault.",
    },
    {
        "id": "rust-path-traversal", "severity": "high",
        "languages": ["rust"],
        "pattern": r"(File::open|fs::read_to_string)\s*\([^)]*\+",
        "message": "File path from string concatenation — validate against path traversal.",
    },
    {
        "id": "rust-ssrf", "severity": "high",
        "languages": ["rust"],
        "pattern": r"(reqwest::get|client\.get)\s*\(\s*&?\w*(req|param|input)",
        "message": "HTTP request URL from user input — SSRF risk.",
    },
    {
        "id": "rust-serde-untrusted", "severity": "medium",
        "languages": ["rust"],
        "pattern": r"serde_json::from_str\s*\(|serde_yaml::from_str\s*\(",
        "message": "Deserializing untrusted input — validate shape and bounds.",
    },
    {
        "id": "rust-dbg-macro", "severity": "trace",
        "languages": ["rust"],
        "pattern": r"\bdbg!\s*\(",
        "message": "dbg! macro left in code — remove before production.",
    },

    # ════════════════════════════════════════════════════════════════════════
    # C / C++
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "buffer-overflow-c", "severity": "critical",
        "languages": ["c", "cpp"],
        "pattern": r"\b(strcpy|strcat|sprintf|gets|scanf)\s*\(",
        "message": "Unsafe C string function — use strncpy/strncat/snprintf/fgets.",
    },
    {
        "id": "format-string-c", "severity": "critical",
        "languages": ["c", "cpp"],
        "pattern": r"(printf|fprintf|sprintf|syslog)\s*\(\s*\w+\s*\)",
        "message": "printf with non-literal format string — can expose memory or execute code.",
    },
    {
        "id": "memory-leak-c", "severity": "high",
        "languages": ["c", "cpp"],
        "pattern": r"\bmalloc\s*\([^)]+\)(?!.*free\s*\()",
        "message": "malloc() without corresponding free() — potential memory leak.",
    },
    {
        "id": "null-check-after-deref", "severity": "high",
        "languages": ["c", "cpp"],
        "pattern": r"\*\w+[^;]+;\s*if\s*\(\w+\s*==\s*NULL\s*\)",
        "message": "Pointer dereferenced before NULL check.",
    },
    {
        "id": "use-after-free", "severity": "critical",
        "languages": ["c", "cpp"],
        "pattern": r"free\s*\(\s*(\w+)\s*\);[^\n]*\1\s*[\.\->]",
        "message": "Pointer used after free() — undefined behaviour, potential exploitable.",
    },
    {
        "id": "double-free", "severity": "critical",
        "languages": ["c", "cpp"],
        "pattern": r"free\s*\(\s*(\w+)\s*\);[^}]*free\s*\(\s*\1\s*\)",
        "message": "Double free detected — undefined behaviour.",
    },
    {
        "id": "integer-overflow", "severity": "high",
        "languages": ["c", "cpp"],
        "pattern": r"(int|unsigned)\s+\w+\s*=\s*\w+\s*\*\s*\w+",
        "message": "Integer multiplication without overflow check — use checked arithmetic.",
    },
    {
        "id": "c-gets-usage", "severity": "blocker",
        "languages": ["c", "cpp"],
        "pattern": r"\bgets\s*\(",
        "message": "gets() has no bounds check and is removed from C11 — use fgets().",
    },
    {
        "id": "c-strcpy-usage", "severity": "high",
        "languages": ["c", "cpp"],
        "pattern": r"\bstrcpy\s*\(",
        "message": "strcpy() has no bounds check — use strlcpy() or strncpy().",
    },
    {
        "id": "c-weak-hash", "severity": "medium",
        "languages": ["c", "cpp"],
        "pattern": r"\b(MD5|SHA1)_Init\s*\(",
        "message": "MD5/SHA1 in OpenSSL — use SHA256_Init or EVP_DigestInit with SHA-256.",
    },

    # ════════════════════════════════════════════════════════════════════════
    # CROSS-LANGUAGE secrets / universal
    # ════════════════════════════════════════════════════════════════════════
    {
        "id": "hardcoded-aws-secret", "severity": "critical",
        "languages": ["python", "javascript", "typescript", "dart", "go", "java", "kotlin", "swift", "ruby", "php", "rust"],
        "pattern": r"(?i)aws.{0,20}secret.{0,20}[\"'][0-9a-zA-Z/+]{40}[\"']",
        "message": "Hardcoded AWS Secret Access Key — revoke and rotate immediately.",
    },
    {
        "id": "hardcoded-stripe-key", "severity": "critical",
        "languages": ["python", "javascript", "typescript", "dart", "go", "java", "kotlin", "swift", "ruby", "php", "rust"],
        "pattern": r"(sk|pk)_(test|live)_[0-9a-zA-Z]{24,}",
        "message": "Stripe API key detected in source — rotate immediately.",
    },
    {
        "id": "hardcoded-gcp-key", "severity": "critical",
        "languages": ["python", "javascript", "typescript", "dart", "go", "java", "kotlin", "swift", "ruby", "php", "rust"],
        "pattern": r"AIza[0-9A-Za-z\-_]{35}",
        "message": "Google API key (AIza...) detected — restrict key in Cloud Console.",
    },
    {
        "id": "hardcoded-oauth-token", "severity": "critical",
        "languages": ["python", "javascript", "typescript", "dart", "go", "java", "kotlin", "swift", "ruby", "php", "rust"],
        "pattern": r"ya29\.[0-9A-Za-z\-_]+",
        "message": "Google OAuth access token detected in source.",
    },
    {
        "id": "env-secret-logged", "severity": "high",
        "languages": ["python", "javascript", "typescript"],
        "pattern": r"(console\.log|print|logger\.(info|debug))\s*\(\s*process\.env\.",
        "message": "Environment variable (possibly a secret) written to logs.",
    },
    {
        "id": "hardcoded-sendgrid-key", "severity": "critical",
        "languages": ["python", "javascript", "typescript", "dart", "go", "java", "kotlin", "swift", "ruby", "php", "rust"],
        "pattern": r"SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]{43}",
        "message": "SendGrid API key detected in source — rotate immediately.",
    },
    {
        "id": "hardcoded-twilio-key", "severity": "critical",
        "languages": ["python", "javascript", "typescript", "dart", "go", "java", "kotlin", "swift", "ruby", "php", "rust"],
        "pattern": r"SK[0-9a-fA-F]{32}",
        "message": "Twilio API key detected in source — rotate immediately.",
    },
    {
        "id": "ldap-injection", "severity": "high",
        "languages": ["java", "python", "php"],
        "pattern": r"(ldap_search|search_s|DirContext\.search)\s*\([^)]*\+",
        "message": "LDAP query built from user input — use LDAP escaping.",
    },
    {
        "id": "xpath-injection", "severity": "high",
        "languages": ["java", "python", "php", "javascript", "typescript"],
        "pattern": r"(xpath|XPath)\s*\.\s*(evaluate|select)\s*\([^)]*\+",
        "message": "XPath expression built from user input — sanitise or use parameterised queries.",
    },
    {
        "id": "zip-slip", "severity": "high",
        "languages": ["java", "python", "go", "kotlin"],
        "pattern": r"ZipEntry\s*\(\s*\)|getNextEntry\s*\(\s*\)",
        "message": "Zip extraction without path validation — potential Zip Slip traversal attack.",
    },
    {
        "id": "weak-cipher-ecb", "severity": "high",
        "languages": ["python", "java", "kotlin", "javascript", "typescript"],
        "pattern": r"(AES|DES)/(ECB)",
        "message": "ECB cipher mode leaks patterns — use GCM or CBC with HMAC.",
    },
    {
        "id": "weak-cipher-des", "severity": "high",
        "languages": ["python", "java", "kotlin", "php", "ruby"],
        "pattern": r"\bDES(ede)?\b",
        "message": "DES/3DES is deprecated — use AES-256-GCM.",
    },
    {
        "id": "hardcoded-iv", "severity": "high",
        "languages": ["python", "java", "kotlin", "javascript", "typescript"],
        "pattern": r"iv\s*=\s*b?[\"'][0-9a-fA-F]{16,32}[\"']",
        "message": "Hardcoded IV for encryption — generate a random IV per encryption operation.",
    },
    {
        "id": "insecure-rsa-keysize", "severity": "high",
        "languages": ["python", "java", "kotlin", "javascript", "typescript"],
        "pattern": r"(RSA|generateKeyPair)\s*\(\s*[\"']?RSA[\"']?,\s*(512|1024)",
        "message": "RSA key size < 2048 bits is insufficient — use at least 2048.",
    },
    {
        "id": "session-fixation", "severity": "high",
        "languages": ["php", "java", "ruby"],
        "pattern": r"session_(start|id)\s*\(",
        "message": "Potential session fixation — regenerate session ID after login.",
    },
    {
        "id": "missing-csrf", "severity": "high",
        "languages": ["python", "javascript", "typescript", "php", "ruby", "java"],
        "pattern": r"csrf_(exempt|disable|skip)|CSRF_EXEMPT\s*=\s*True",
        "message": "CSRF protection explicitly disabled — re-enable for all state-changing endpoints.",
    },
    {
        "id": "server-side-template", "severity": "critical",
        "languages": ["python", "javascript", "typescript", "ruby", "php", "java"],
        "pattern": r"(render_template_string|Mustache\.render|\.render\s*\()\s*[^,)]*request",
        "message": "Template rendered with user-controlled input string — SSTI risk.",
    },
    {
        "id": "expression-injection", "severity": "high",
        "languages": ["java", "kotlin", "python"],
        "pattern": r"(ExpressionFactory|ELProcessor|el\.eval)\s*\(",
        "message": "EL/OGNL expression evaluated — never pass user data as the expression.",
    },
    {
        "id": "groovy-injection", "severity": "critical",
        "languages": ["java", "kotlin"],
        "pattern": r"(GroovyShell|GroovyClassLoader)\s*\(\s*\)",
        "message": "Groovy execution engine — evaluating user input leads to RCE.",
    },
    {
        "id": "ognl-injection", "severity": "critical",
        "languages": ["java"],
        "pattern": r"Ognl\.(getValue|setValue)\s*\(",
        "message": "OGNL expression with user input can lead to RCE (Struts2-style).",
    },
    {
        "id": "no-certificate-validation", "severity": "high",
        "languages": ["python", "java", "go", "dart", "kotlin", "swift", "ruby", "php"],
        "pattern": r"(VERIFY_NONE|checkValidity|TrustAll|X509TrustManager.*null|badCertificateCallback\s*=\s*\(_\)\s*=>?\s*true)",
        "message": "Certificate validation disabled — vulnerable to MITM attacks.",
    },
    {
        "id": "race-condition", "severity": "high",
        "languages": ["python", "go", "java", "c", "cpp"],
        "pattern": r"(os\.path\.exists.*open|access\s*\(.*O_CREAT)",
        "message": "TOCTOU race condition — check and use are not atomic.",
    },
    {
        "id": "deprecated-function", "severity": "low",
        "languages": ["python", "javascript", "typescript"],
        "pattern": r"@deprecated|#\s*deprecated:|\/\/\s*@deprecated",
        "message": "Calling deprecated function — migrate to the recommended replacement.",
    },
]


# ---------------------------------------------------------------------------
# Helpers (mirrors legacy seed helpers)
# ---------------------------------------------------------------------------

def _rule_name(rule_id: str) -> str:
    parts = rule_id.replace("_", "-").split("-")
    return " ".join(p.capitalize() for p in parts if p)


def _derive_language(languages: list[str]) -> str:
    if not languages:
        return "any"
    if len(languages) == 1:
        return languages[0]
    return "any"


def _derive_match_type(pattern: str) -> str:
    return "regex_multiline" if r"\n" in pattern else "regex_line"


def _build_seed_rows() -> list[dict]:
    now = datetime.now(timezone.utc)
    rows: list[dict] = []
    seen: set[str] = set()

    for rule in EXPANDED_RULES:
        rule_key = rule.get("id")
        if not rule_key:
            raise ValueError("Rule is missing 'id'")
        if rule_key not in DEFECT_FAMILY_MAP:
            raise ValueError(f"No defect_family mapping for rule '{rule_key}'")

        # Per-language rows (one DB row per language for precise filtering)
        languages: list[str] = rule.get("languages", [])
        target_langs: list[str] = languages if languages else ["any"]

        for lang in target_langs:
            composite_key = f"{rule_key}::{lang}"
            if composite_key in seen:
                continue
            seen.add(composite_key)

            severity = SEVERITY_OVERRIDE.get(rule_key, rule.get("severity", "low"))
            db_rule_id = (
                f"REGEX-{rule_key}"
                if lang == "any"
                else f"REGEX-{lang}-{rule_key}"
            )

            rows.append({
                "rule_id": db_rule_id,
                "name": _rule_name(rule_key),
                "description": rule.get("message", ""),
                "language": lang,
                "defect_family": DEFECT_FAMILY_MAP[rule_key],
                "severity": severity,
                "pattern": rule.get("pattern", ""),
                "match_type": _derive_match_type(rule.get("pattern", "")),
                "message": rule.get("message", ""),
                "fix_hint": None,
                "cwe_id": None,
                "owasp_ref": None,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })

    return rows


# ---------------------------------------------------------------------------
# Async seed runner
# ---------------------------------------------------------------------------

async def seed_rules() -> None:
    rows = _build_seed_rows()
    session_factory = get_session_factory()

    async with session_factory() as session:
        stmt = insert(AnalysisRule).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["rule_id"])
        await session.execute(stmt)
        await session.commit()

    langs = sorted({r["language"] for r in rows})
    families = sorted({r["defect_family"] for r in rows})
    severities = sorted({r["severity"] for r in rows})

    print(f"\n✅ Seed complete: {len(rows)} rules across {len(langs)} languages")
    print(f"   Languages : {', '.join(langs)}")
    print(f"   Families  : {', '.join(families)}")
    print(f"   Severities: {', '.join(severities)}")


def main() -> None:
    asyncio.run(seed_rules())


if __name__ == "__main__":
    main()
