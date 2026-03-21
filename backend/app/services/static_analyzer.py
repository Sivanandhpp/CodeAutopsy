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
# Used when Semgrep is not installed

REGEX_RULES = [
    {
        'id': 'hardcoded-secret',
        'pattern': r'(?i)(password|secret|api_key|apikey|token|access_key)\s*=\s*["\'][^"\']{8,}["\']',
        'message': 'Potential hardcoded secret or credential detected',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'typescript', 'java'],
    },
    {
        'id': 'sql-injection',
        'pattern': r'(?i)(execute|cursor\.execute|query)\s*\(\s*[f"\'].*(%s|%d|\{|\+\s*\w+)',
        'message': 'Potential SQL injection: string concatenation/formatting in SQL query',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript', 'java'],
    },
    {
        'id': 'eval-usage',
        'pattern': r'\beval\s*\(',
        'message': 'Use of eval() can lead to code injection attacks',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript'],
    },
    {
        'id': 'exec-usage',
        'pattern': r'\bexec\s*\(',
        'message': 'Use of exec() can lead to code injection attacks',
        'severity': 'high',
        'category': 'security',
        'languages': ['python'],
    },
    {
        'id': 'command-injection',
        'pattern': r'(?i)(os\.system|subprocess\.call|subprocess\.Popen|child_process\.exec)\s*\(.*[\+f"\{]',
        'message': 'Potential command injection: user input in system command',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'javascript'],
    },
    {
        'id': 'insecure-hash',
        'pattern': r'(?i)(md5|sha1)\s*\(',
        'message': 'Use of weak cryptographic hash function (MD5/SHA1)',
        'severity': 'medium',
        'category': 'security',
        'languages': ['python', 'javascript', 'java'],
    },
    {
        'id': 'debug-enabled',
        'pattern': r'(?i)debug\s*=\s*true',
        'message': 'Debug mode enabled - should be disabled in production',
        'severity': 'medium',
        'category': 'best-practice',
        'languages': ['python', 'javascript', 'java'],
    },
    {
        'id': 'console-log',
        'pattern': r'console\.(log|debug|info)\s*\(',
        'message': 'Console logging found - remove before production deployment',
        'severity': 'low',
        'category': 'best-practice',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'todo-fixme',
        'pattern': r'(?i)#\s*(TODO|FIXME|HACK|XXX|BUG):?\s+',
        'message': 'Code contains TODO/FIXME marker that needs attention',
        'severity': 'low',
        'category': 'maintainability',
        'languages': ['python', 'javascript', 'typescript', 'java'],
    },
    {
        'id': 'empty-except',
        'pattern': r'except\s*:\s*\n\s*(pass|\.\.\.)',
        'message': 'Empty except clause silently catches all exceptions',
        'severity': 'medium',
        'category': 'best-practice',
        'languages': ['python'],
    },
    {
        'id': 'insecure-random',
        'pattern': r'(?i)\brandom\.(random|randint|choice|randrange)\b',
        'message': 'Using non-cryptographic random for potentially security-sensitive operation',
        'severity': 'medium',
        'category': 'security',
        'languages': ['python'],
    },
    {
        'id': 'xss-innerhtml',
        'pattern': r'\.innerHTML\s*=',
        'message': 'Direct innerHTML assignment may lead to XSS vulnerabilities',
        'severity': 'high',
        'category': 'security',
        'languages': ['javascript', 'typescript'],
    },
    {
        'id': 'open-redirect',
        'pattern': r'(?i)(redirect|location\.href|window\.location)\s*=\s*.*req\.',
        'message': 'Potential open redirect vulnerability with user-controlled input',
        'severity': 'high',
        'category': 'security',
        'languages': ['javascript', 'python'],
    },
    {
        'id': 'jwt-no-verify',
        'pattern': r'(?i)jwt\.(decode|verify).*verify\s*=\s*false',
        'message': 'JWT verification disabled - tokens are not validated',
        'severity': 'critical',
        'category': 'security',
        'languages': ['python', 'javascript'],
    },
    {
        'id': 'cors-wildcard',
        'pattern': r'(?i)(access-control-allow-origin|cors).*\*',
        'message': 'CORS wildcard (*) allows any origin - may expose sensitive data',
        'severity': 'medium',
        'category': 'security',
        'languages': ['python', 'javascript', 'java'],
    },
    {
        'id': 'path-traversal',
        'pattern': r'(?i)(open|read_file|send_file)\s*\(.*\+.*\.(params|query|body|args)',
        'message': 'Potential path traversal: user input in file path',
        'severity': 'high',
        'category': 'security',
        'languages': ['python', 'javascript'],
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
                if f['language'] in ('python', 'javascript', 'typescript', 'java')
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
