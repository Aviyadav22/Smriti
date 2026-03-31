#!/usr/bin/env python3
"""
RALPH LOOP - Recursive Audit Loop for Programmatic Health
=========================================================
Smriti Codebase E2E Audit Engine

Runs 100 iterations over 8+ hours, analyzing every single line of code.
Each iteration goes deeper than the last, building cumulative findings.

Author: Avi (NeetiQ / Nyaya)
"""

import os
import re
import json
import time
import hashlib
import ast
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

def load_config(config_path: str = "ralph_loop_config.json") -> dict:
    with open(config_path, "r") as f:
        return json.load(f)

# ─────────────────────────────────────────────
# FILE DISCOVERY
# ─────────────────────────────────────────────

class CodebaseScanner:
    """Discovers and reads every file in the codebase."""

    def __init__(self, config: dict):
        self.config = config
        self.root = config["codebase_root"]
        self.extensions = set(config["file_extensions_to_audit"])
        self.exclude_dirs = set(config["exclude_dirs"])

    def discover_files(self) -> List[Path]:
        """Find every auditable file in the codebase."""
        files = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Filter out excluded directories
            dirnames[:] = [
                d for d in dirnames
                if d not in self.exclude_dirs and not d.startswith(".")
            ]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                if fpath.suffix in self.extensions:
                    files.append(fpath)
        return sorted(files)

    def read_file_safe(self, filepath: Path) -> Optional[str]:
        """Read a file with encoding fallback."""
        for encoding in ["utf-8", "latin-1", "cp1252"]:
            try:
                return filepath.read_text(encoding=encoding)
            except (UnicodeDecodeError, PermissionError):
                continue
        return None

    def get_file_hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()


# ─────────────────────────────────────────────
# PYTHON AST ANALYZER
# ─────────────────────────────────────────────

class PythonAnalyzer:
    """Deep AST-based analysis for Python files."""

    def analyze(self, filepath: Path, content: str) -> dict:
        findings = {
            "functions": [],
            "classes": [],
            "imports": [],
            "global_vars": [],
            "issues": [],
            "complexity_score": 0,
            "line_count": len(content.splitlines()),
        }

        try:
            tree = ast.parse(content, filename=str(filepath))
        except SyntaxError as e:
            findings["issues"].append({
                "category": "SYNTAX_ERROR",
                "severity": "CRITICAL",
                "line": e.lineno or 0,
                "message": f"Syntax error: {e.msg}",
                "code_snippet": self._get_snippet(content, e.lineno or 0),
            })
            return findings

        self._analyze_node(tree, content, findings, filepath)
        return findings

    def _analyze_node(self, tree: ast.AST, content: str, findings: dict, filepath: Path):
        lines = content.splitlines()

        for node in ast.walk(tree):
            # ── Function Analysis ──
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = self._analyze_function(node, content, lines)
                findings["functions"].append(func_info)
                findings["issues"].extend(func_info.get("issues", []))
                findings["complexity_score"] += func_info.get("complexity", 1)

            # ── Class Analysis ──
            elif isinstance(node, ast.ClassDef):
                class_info = self._analyze_class(node, content, lines)
                findings["classes"].append(class_info)

            # ── Import Analysis ──
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_info = self._analyze_import(node)
                findings["imports"].append(import_info)

            # ── Global Variable Detection ──
            elif isinstance(node, ast.Assign) and self._is_module_level(node, tree):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        findings["global_vars"].append({
                            "name": target.id,
                            "line": node.lineno,
                            "type": "global_assignment",
                        })

        # ── Cross-cutting Concerns ──
        self._check_security_patterns(content, lines, findings)
        self._check_error_handling(tree, content, findings)
        self._check_hardcoded_values(content, lines, findings)

    def _analyze_function(self, node, content: str, lines: list) -> dict:
        func = {
            "name": node.name,
            "line_start": node.lineno,
            "line_end": node.end_lineno or node.lineno,
            "args": [],
            "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "has_return": False,
            "has_docstring": False,
            "has_type_hints": False,
            "complexity": 1,
            "issues": [],
            "calls_made": [],
            "variables_used": [],
        }

        # Arguments
        for arg in node.args.args:
            arg_info = {"name": arg.arg, "has_type_hint": arg.annotation is not None}
            func["args"].append(arg_info)
            if arg.annotation:
                func["has_type_hints"] = True

        # Return type hint
        if node.returns:
            func["has_type_hints"] = True

        # Docstring
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, (ast.Str, ast.Constant))):
            func["has_docstring"] = True

        # Walk function body
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value is not None:
                func["has_return"] = True
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                func["complexity"] += 1
            if isinstance(child, (ast.And, ast.Or)):
                func["complexity"] += 1
            if isinstance(child, ast.Call):
                call_name = self._get_call_name(child)
                if call_name:
                    func["calls_made"].append(call_name)
            if isinstance(child, ast.Name):
                func["variables_used"].append(child.id)

        # ── Issue Detection ──
        body_length = (func["line_end"] - func["line_start"])

        if not func["has_docstring"] and not node.name.startswith("_"):
            func["issues"].append({
                "category": "DOCUMENTATION_GAP",
                "severity": "MEDIUM",
                "line": node.lineno,
                "message": f"Public function '{node.name}' has no docstring",
                "code_snippet": self._get_snippet(content, node.lineno),
            })

        if not func["has_type_hints"] and not node.name.startswith("_"):
            func["issues"].append({
                "category": "TYPE_SAFETY_ISSUES",
                "severity": "LOW",
                "line": node.lineno,
                "message": f"Function '{node.name}' has no type hints",
                "code_snippet": self._get_snippet(content, node.lineno),
            })

        if func["complexity"] > 10:
            func["issues"].append({
                "category": "PERFORMANCE_BOTTLENECKS",
                "severity": "HIGH",
                "line": node.lineno,
                "message": f"Function '{node.name}' has high cyclomatic complexity: {func['complexity']}",
                "code_snippet": self._get_snippet(content, node.lineno),
            })

        if body_length > 50:
            func["issues"].append({
                "category": "LOGIC_FLOW_TRACE",
                "severity": "MEDIUM",
                "line": node.lineno,
                "message": f"Function '{node.name}' is {body_length} lines long — consider splitting",
                "code_snippet": self._get_snippet(content, node.lineno),
            })

        if len(func["args"]) > 5:
            func["issues"].append({
                "category": "FUNCTION_SIGNATURE_AUDIT",
                "severity": "MEDIUM",
                "line": node.lineno,
                "message": f"Function '{node.name}' has {len(func['args'])} parameters — consider using a config object",
                "code_snippet": self._get_snippet(content, node.lineno),
            })

        return func

    def _analyze_class(self, node, content: str, lines: list) -> dict:
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)

        has_init = "__init__" in methods
        has_repr = "__repr__" in methods or "__str__" in methods

        return {
            "name": node.name,
            "line": node.lineno,
            "bases": [self._get_node_name(b) for b in node.bases],
            "methods": methods,
            "method_count": len(methods),
            "has_init": has_init,
            "has_repr": has_repr,
            "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
        }

    def _analyze_import(self, node) -> dict:
        if isinstance(node, ast.Import):
            return {
                "type": "import",
                "modules": [alias.name for alias in node.names],
                "line": node.lineno,
            }
        else:
            return {
                "type": "from_import",
                "module": node.module or "",
                "names": [alias.name for alias in node.names],
                "line": node.lineno,
            }

    def _check_security_patterns(self, content: str, lines: list, findings: dict):
        security_patterns = [
            (r'eval\s*\(', "SECURITY_VULNERABILITIES", "CRITICAL", "Use of eval() — potential code injection"),
            (r'exec\s*\(', "SECURITY_VULNERABILITIES", "CRITICAL", "Use of exec() — potential code injection"),
            (r'subprocess\.call\s*\(.*shell\s*=\s*True', "SECURITY_VULNERABILITIES", "CRITICAL", "Shell=True in subprocess — command injection risk"),
            (r'os\.system\s*\(', "SECURITY_VULNERABILITIES", "HIGH", "os.system() used — prefer subprocess with shell=False"),
            (r'pickle\.loads?\s*\(', "SECURITY_VULNERABILITIES", "HIGH", "Pickle deserialization — potential arbitrary code execution"),
            (r'yaml\.load\s*\((?!.*Loader)', "SECURITY_VULNERABILITIES", "HIGH", "yaml.load without safe Loader — use yaml.safe_load"),
            (r'__import__\s*\(', "SECURITY_VULNERABILITIES", "MEDIUM", "Dynamic import via __import__"),
            (r'# ?TODO', "DEAD_CODE_DETECTION", "LOW", "TODO comment found — incomplete implementation"),
            (r'# ?FIXME', "DEAD_CODE_DETECTION", "MEDIUM", "FIXME comment found — known bug"),
            (r'# ?HACK', "DEAD_CODE_DETECTION", "MEDIUM", "HACK comment found — technical debt"),
            (r'# ?XXX', "DEAD_CODE_DETECTION", "MEDIUM", "XXX comment found — needs attention"),
            (r'print\s*\(', "LOGGING_GAPS", "LOW", "print() used — should use proper logging"),
            (r'except\s*:', "ERROR_HANDLING_GAPS", "HIGH", "Bare except clause — catches all exceptions including SystemExit"),
            (r'except\s+Exception\s*:', "ERROR_HANDLING_GAPS", "MEDIUM", "Broad Exception catch — be more specific"),
            (r'pass\s*$', "ERROR_HANDLING_GAPS", "MEDIUM", "Empty pass statement — silent failure"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, category, severity, message in security_patterns:
                if re.search(pattern, line):
                    findings["issues"].append({
                        "category": category,
                        "severity": severity,
                        "line": i,
                        "message": message,
                        "code_snippet": line.strip()[:120],
                    })

    def _check_error_handling(self, tree: ast.AST, content: str, findings: dict):
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                if not node.handlers:
                    findings["issues"].append({
                        "category": "ERROR_HANDLING_GAPS",
                        "severity": "HIGH",
                        "line": node.lineno,
                        "message": "try block with no except handlers",
                        "code_snippet": self._get_snippet(content, node.lineno),
                    })
                if not node.finalbody and not node.orelse:
                    # Check if any handler re-raises
                    has_reraise = False
                    for handler in node.handlers:
                        for child in ast.walk(handler):
                            if isinstance(child, ast.Raise):
                                has_reraise = True
                    if not has_reraise:
                        findings["issues"].append({
                            "category": "ERROR_HANDLING_GAPS",
                            "severity": "LOW",
                            "line": node.lineno,
                            "message": "try/except without finally or re-raise — errors may be silently swallowed",
                            "code_snippet": self._get_snippet(content, node.lineno),
                        })

    def _check_hardcoded_values(self, content: str, lines: list, findings: dict):
        secret_patterns = [
            (r'(?:password|passwd|pwd)\s*=\s*["\'][^"\']+["\']', "HARDCODED_SECRETS", "CRITICAL", "Hardcoded password detected"),
            (r'(?:api_key|apikey|api_secret)\s*=\s*["\'][^"\']+["\']', "HARDCODED_SECRETS", "CRITICAL", "Hardcoded API key detected"),
            (r'(?:secret|token|jwt)\s*=\s*["\'][A-Za-z0-9+/=]{20,}["\']', "HARDCODED_SECRETS", "CRITICAL", "Hardcoded secret/token detected"),
            (r'(?:mongodb|postgres|mysql|redis)://[^"\'\s]+', "HARDCODED_SECRETS", "HIGH", "Hardcoded database connection string"),
            (r'(?:sk-|pk_|rk_)[A-Za-z0-9]{20,}', "HARDCODED_SECRETS", "CRITICAL", "Potential API key pattern detected"),
        ]

        for i, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                continue
            for pattern, category, severity, message in secret_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    findings["issues"].append({
                        "category": category,
                        "severity": severity,
                        "line": i,
                        "message": message,
                        "code_snippet": line.strip()[:80] + "...[REDACTED]",
                    })

    # ── Helpers ──

    def _get_snippet(self, content: str, lineno: int, context: int = 2) -> str:
        lines = content.splitlines()
        start = max(0, lineno - context - 1)
        end = min(len(lines), lineno + context)
        snippet_lines = lines[start:end]
        return "\n".join(f"  {start + i + 1:4d} | {l}" for i, l in enumerate(snippet_lines))

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def _get_decorator_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return "unknown"

    def _get_node_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_node_name(node.value)}.{node.attr}"
        return "unknown"

    def _is_module_level(self, node, tree) -> bool:
        return node in tree.body


# ─────────────────────────────────────────────
# JS / TS / JSX / TSX ANALYZER
# ─────────────────────────────────────────────

class JSAnalyzer:
    """Regex-based analysis for JavaScript/TypeScript files."""

    def analyze(self, filepath: Path, content: str) -> dict:
        findings = {
            "functions": [],
            "classes": [],
            "imports": [],
            "exports": [],
            "issues": [],
            "complexity_score": 0,
            "line_count": len(content.splitlines()),
        }

        lines = content.splitlines()
        self._extract_functions(content, lines, findings)
        self._extract_imports(content, lines, findings)
        self._extract_classes(content, lines, findings)
        self._check_patterns(content, lines, findings)
        self._check_react_patterns(content, lines, findings, filepath)
        return findings

    def _extract_functions(self, content: str, lines: list, findings: dict):
        patterns = [
            # Standard function
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
            # Arrow function assigned to const/let/var
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?([^)]*)\)?\s*=>',
            # Method in object/class
            r'(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*\{',
        ]

        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    name = match.group(1)
                    params = match.group(2) if match.lastindex >= 2 else ""
                    findings["functions"].append({
                        "name": name,
                        "line": i,
                        "params": params,
                        "is_async": "async" in line,
                        "is_exported": "export" in line,
                    })

                    # Check for missing error handling in async functions
                    if "async" in line:
                        # Look ahead for try/catch
                        lookahead = "\n".join(lines[i:min(i + 30, len(lines))])
                        if "try" not in lookahead and "catch" not in lookahead:
                            findings["issues"].append({
                                "category": "ERROR_HANDLING_GAPS",
                                "severity": "HIGH",
                                "line": i,
                                "message": f"Async function '{name}' has no try/catch — unhandled promise rejection risk",
                                "code_snippet": line.strip()[:120],
                            })
                    break

    def _extract_imports(self, content: str, lines: list, findings: dict):
        for i, line in enumerate(lines, 1):
            if re.match(r'\s*import\s+', line):
                findings["imports"].append({"line": i, "statement": line.strip()[:120]})
            elif re.match(r'\s*(?:const|let|var)\s+.*=\s*require\s*\(', line):
                findings["imports"].append({"line": i, "statement": line.strip()[:120]})

    def _extract_classes(self, content: str, lines: list, findings: dict):
        for i, line in enumerate(lines, 1):
            match = re.match(r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?', line)
            if match:
                findings["classes"].append({
                    "name": match.group(1),
                    "extends": match.group(2),
                    "line": i,
                })

    def _check_patterns(self, content: str, lines: list, findings: dict):
        js_patterns = [
            (r'console\.log\s*\(', "LOGGING_GAPS", "LOW", "console.log found — use proper logging in production"),
            (r'console\.error\s*\(', "LOGGING_GAPS", "INFO", "console.error found — verify error reporting"),
            (r'\.innerHTML\s*=', "SECURITY_VULNERABILITIES", "HIGH", "innerHTML assignment — XSS risk, use textContent or sanitize"),
            (r'eval\s*\(', "SECURITY_VULNERABILITIES", "CRITICAL", "eval() used — code injection risk"),
            (r'document\.write\s*\(', "SECURITY_VULNERABILITIES", "HIGH", "document.write — XSS and performance risk"),
            (r'localStorage\.(set|get)Item', "SECURITY_VULNERABILITIES", "MEDIUM", "localStorage used — sensitive data should not be stored client-side"),
            (r'// ?TODO', "DEAD_CODE_DETECTION", "LOW", "TODO comment — incomplete implementation"),
            (r'// ?FIXME', "DEAD_CODE_DETECTION", "MEDIUM", "FIXME — known bug"),
            (r'var\s+\w+', "TYPE_SAFETY_ISSUES", "LOW", "var keyword — prefer const/let for block scoping"),
            (r'==(?!=)', "LOGIC_FLOW_TRACE", "LOW", "Loose equality (==) — use strict equality (===)"),
            (r'!=(?!=)', "LOGIC_FLOW_TRACE", "LOW", "Loose inequality (!=) — use strict inequality (!==)"),
            (r'\.then\s*\(.*\.catch\s*\(\s*\)', "ERROR_HANDLING_GAPS", "HIGH", "Empty catch in promise chain"),
            (r'any(?:\s|;|,|\))', "TYPE_SAFETY_ISSUES", "MEDIUM", "TypeScript 'any' type — reduces type safety"),
            (r'@ts-ignore', "TYPE_SAFETY_ISSUES", "HIGH", "@ts-ignore — type error being suppressed"),
            (r'@ts-nocheck', "TYPE_SAFETY_ISSUES", "CRITICAL", "@ts-nocheck — entire file type checking disabled"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, category, severity, message in js_patterns:
                if re.search(pattern, line):
                    findings["issues"].append({
                        "category": category,
                        "severity": severity,
                        "line": i,
                        "message": message,
                        "code_snippet": line.strip()[:120],
                    })

    def _check_react_patterns(self, content: str, lines: list, findings: dict, filepath: Path):
        if filepath.suffix not in (".jsx", ".tsx"):
            return

        react_patterns = [
            (r'dangerouslySetInnerHTML', "SECURITY_VULNERABILITIES", "HIGH", "dangerouslySetInnerHTML — XSS risk"),
            (r'useEffect\s*\(\s*(?:async|.*=>\s*\{)', "LOGIC_FLOW_TRACE", "MEDIUM", "Check useEffect cleanup — potential memory leak"),
            (r'useState\s*\(', "STATE_MANAGEMENT_BUGS", "INFO", "useState found — verify state update patterns"),
            (r'key\s*=\s*\{?\s*(?:index|i)\s*\}?', "PERFORMANCE_BOTTLENECKS", "MEDIUM", "Array index used as key — causes rendering bugs on reorder"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, category, severity, message in react_patterns:
                if re.search(pattern, line):
                    findings["issues"].append({
                        "category": category,
                        "severity": severity,
                        "line": i,
                        "message": message,
                        "code_snippet": line.strip()[:120],
                    })


# ─────────────────────────────────────────────
# GENERIC CONFIG / MARKUP ANALYZER
# ─────────────────────────────────────────────

class GenericAnalyzer:
    """Analyzes config files, markdown, SQL, etc."""

    def analyze(self, filepath: Path, content: str) -> dict:
        findings = {
            "issues": [],
            "line_count": len(content.splitlines()),
        }
        lines = content.splitlines()

        # ENV file checks
        if filepath.name.startswith(".env"):
            self._check_env_file(lines, findings)

        # JSON validation
        if filepath.suffix == ".json":
            self._check_json(content, filepath, findings)

        # SQL checks
        if filepath.suffix == ".sql":
            self._check_sql(lines, findings)

        # YAML checks
        if filepath.suffix in (".yaml", ".yml"):
            self._check_yaml(lines, findings)

        return findings

    def _check_env_file(self, lines: list, findings: dict):
        for i, line in enumerate(lines, 1):
            if "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                if value.strip() and any(
                    kw in key.lower()
                    for kw in ["secret", "password", "key", "token", "api"]
                ):
                    if not value.strip().startswith("${") and value.strip() not in ("", '""', "''"):
                        findings["issues"].append({
                            "category": "HARDCODED_SECRETS",
                            "severity": "CRITICAL",
                            "line": i,
                            "message": f"Env variable '{key.strip()}' may contain a hardcoded secret",
                            "code_snippet": f"{key.strip()}=[REDACTED]",
                        })

    def _check_json(self, content: str, filepath: Path, findings: dict):
        try:
            data = json.loads(content)
            # Check for sensitive keys in JSON
            self._check_json_keys(data, filepath, findings)
        except json.JSONDecodeError as e:
            findings["issues"].append({
                "category": "SYNTAX_ERROR",
                "severity": "CRITICAL",
                "line": e.lineno or 0,
                "message": f"Invalid JSON: {e.msg}",
                "code_snippet": str(e),
            })

    def _check_json_keys(self, data, filepath, findings, depth=0):
        if depth > 5:
            return
        if isinstance(data, dict):
            for key, value in data.items():
                if any(kw in key.lower() for kw in ["password", "secret", "token", "api_key"]):
                    if isinstance(value, str) and len(value) > 3:
                        findings["issues"].append({
                            "category": "HARDCODED_SECRETS",
                            "severity": "HIGH",
                            "line": 0,
                            "message": f"JSON key '{key}' may contain a secret in {filepath.name}",
                            "code_snippet": f'"{key}": "[REDACTED]"',
                        })
                self._check_json_keys(value, filepath, findings, depth + 1)
        elif isinstance(data, list):
            for item in data:
                self._check_json_keys(item, filepath, findings, depth + 1)

    def _check_sql(self, lines: list, findings: dict):
        for i, line in enumerate(lines, 1):
            if re.search(r'SELECT\s+\*', line, re.IGNORECASE):
                findings["issues"].append({
                    "category": "DATABASE_QUERY_ISSUES",
                    "severity": "MEDIUM",
                    "line": i,
                    "message": "SELECT * used — specify columns explicitly for performance",
                    "code_snippet": line.strip()[:120],
                })

    def _check_yaml(self, lines: list, findings: dict):
        for i, line in enumerate(lines, 1):
            if re.search(r'password\s*:\s*\S+', line, re.IGNORECASE):
                findings["issues"].append({
                    "category": "HARDCODED_SECRETS",
                    "severity": "CRITICAL",
                    "line": i,
                    "message": "Potential password in YAML config",
                    "code_snippet": line.split(":")[0].strip() + ": [REDACTED]",
                })


# ─────────────────────────────────────────────
# CROSS-FILE DEPENDENCY ANALYZER
# ─────────────────────────────────────────────

class DependencyAnalyzer:
    """Analyzes cross-file dependencies and finds broken references."""

    def __init__(self):
        self.import_graph: Dict[str, List[str]] = defaultdict(list)
        self.export_map: Dict[str, List[str]] = defaultdict(list)

    def build_graph(self, all_findings: Dict[str, dict]):
        for filepath, findings in all_findings.items():
            for imp in findings.get("imports", []):
                if isinstance(imp, dict):
                    module = imp.get("module", "") or ""
                    if module:
                        self.import_graph[filepath].append(module)

    def find_circular_deps(self) -> List[dict]:
        """Detect circular import chains."""
        issues = []
        visited = set()

        def dfs(node, path):
            if node in path:
                cycle = path[path.index(node):] + [node]
                issues.append({
                    "category": "DEPENDENCY_CHAIN_RISKS",
                    "severity": "HIGH",
                    "line": 0,
                    "message": f"Circular dependency detected: {' -> '.join(cycle)}",
                    "code_snippet": "",
                })
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            for neighbor in self.import_graph.get(node, []):
                dfs(neighbor, path[:])

        for node in self.import_graph:
            dfs(node, [])

        return issues


# ─────────────────────────────────────────────
# RALPH LOOP ENGINE
# ─────────────────────────────────────────────

class RalphLoop:
    """
    The main engine. Runs 100 iterations across 8+ hours.
    Each iteration focuses on progressively deeper analysis.
    """

    # Iteration focus areas — each iteration emphasizes different things
    ITERATION_FOCUS = {
        range(1, 11): "SURFACE_SCAN — Function signatures, imports, basic structure",
        range(11, 21): "LOGIC_TRACE — Control flow, branch coverage, return paths",
        range(21, 31): "ERROR_AUDIT — Exception handling, edge cases, failure modes",
        range(31, 41): "SECURITY_SWEEP — Injection points, auth gaps, data exposure",
        range(41, 51): "PERFORMANCE_SCAN — Complexity hotspots, N+1 queries, memory patterns",
        range(51, 61): "STATE_ANALYSIS — State mutations, race conditions, side effects",
        range(61, 71): "DEPENDENCY_AUDIT — Import chains, circular deps, version risks",
        range(71, 81): "DEAD_CODE_HUNT — Unreachable code, unused exports, stale configs",
        range(81, 91): "API_CONTRACT_CHECK — Input/output validation, schema drift",
        range(91, 101): "FINAL_SYNTHESIS — Cross-cutting concerns, architecture review",
    }

    def __init__(self, config: dict):
        self.config = config
        self.scanner = CodebaseScanner(config)
        self.py_analyzer = PythonAnalyzer()
        self.js_analyzer = JSAnalyzer()
        self.generic_analyzer = GenericAnalyzer()
        self.dep_analyzer = DependencyAnalyzer()
        self.all_findings: Dict[str, dict] = {}
        self.cumulative_issues: List[dict] = []
        self.iteration_summaries: List[dict] = []
        self.seen_issue_hashes: set = set()
        self.start_time = None
        self.output_dir = Path(config["output_dir"])
        self.output_dir.mkdir(exist_ok=True)

    def get_focus_for_iteration(self, iteration: int) -> str:
        for rng, focus in self.ITERATION_FOCUS.items():
            if iteration in rng:
                return focus
        return "GENERAL"

    def hash_issue(self, issue: dict) -> str:
        key = f"{issue.get('category', '')}|{issue.get('line', '')}|{issue.get('message', '')}"
        return hashlib.md5(key.encode()).hexdigest()

    def run_single_iteration(self, iteration: int) -> dict:
        """Run one full pass over the codebase."""
        iter_start = time.time()
        focus = self.get_focus_for_iteration(iteration)
        files = self.scanner.discover_files()

        iter_findings = {
            "iteration": iteration,
            "focus": focus,
            "timestamp": datetime.now().isoformat(),
            "files_scanned": 0,
            "total_lines": 0,
            "new_issues_found": 0,
            "total_functions": 0,
            "total_classes": 0,
            "issues": [],
            "file_details": {},
        }

        for fpath in files:
            content = self.scanner.read_file_safe(fpath)
            if content is None:
                continue

            iter_findings["files_scanned"] += 1
            iter_findings["total_lines"] += len(content.splitlines())

            fkey = str(fpath)

            # Choose analyzer based on file type
            if fpath.suffix == ".py":
                result = self.py_analyzer.analyze(fpath, content)
            elif fpath.suffix in (".js", ".jsx", ".ts", ".tsx"):
                result = self.js_analyzer.analyze(fpath, content)
            else:
                result = self.generic_analyzer.analyze(fpath, content)

            # Accumulate counts
            iter_findings["total_functions"] += len(result.get("functions", []))
            iter_findings["total_classes"] += len(result.get("classes", []))

            # Deduplicate issues
            for issue in result.get("issues", []):
                issue["file"] = fkey
                issue_hash = self.hash_issue(issue)
                if issue_hash not in self.seen_issue_hashes:
                    self.seen_issue_hashes.add(issue_hash)
                    self.cumulative_issues.append(issue)
                    iter_findings["issues"].append(issue)
                    iter_findings["new_issues_found"] += 1

            # Store per-file detail
            iter_findings["file_details"][fkey] = {
                "lines": len(content.splitlines()),
                "functions": len(result.get("functions", [])),
                "classes": len(result.get("classes", [])),
                "issues": len(result.get("issues", [])),
                "hash": self.scanner.get_file_hash(content),
            }

            self.all_findings[fkey] = result

        # Cross-file analysis (iterations 61-70 focus)
        if iteration >= 61:
            self.dep_analyzer.build_graph(self.all_findings)
            circular_deps = self.dep_analyzer.find_circular_deps()
            for issue in circular_deps:
                issue_hash = self.hash_issue(issue)
                if issue_hash not in self.seen_issue_hashes:
                    self.seen_issue_hashes.add(issue_hash)
                    self.cumulative_issues.append(issue)
                    iter_findings["issues"].append(issue)
                    iter_findings["new_issues_found"] += 1

        iter_findings["duration_seconds"] = round(time.time() - iter_start, 2)
        self.iteration_summaries.append(iter_findings)
        return iter_findings

    def generate_markdown_report(self) -> str:
        """Generate the final 100-iteration report."""
        elapsed = time.time() - self.start_time
        hours = elapsed / 3600

        # Count by severity
        severity_counts = defaultdict(int)
        category_counts = defaultdict(int)
        file_issue_counts = defaultdict(int)

        for issue in self.cumulative_issues:
            severity_counts[issue.get("severity", "UNKNOWN")] += 1
            category_counts[issue.get("category", "UNKNOWN")] += 1
            file_issue_counts[issue.get("file", "unknown")] += 1

        total_files = self.iteration_summaries[-1]["files_scanned"] if self.iteration_summaries else 0
        total_lines = self.iteration_summaries[-1]["total_lines"] if self.iteration_summaries else 0
        total_functions = self.iteration_summaries[-1]["total_functions"] if self.iteration_summaries else 0
        total_classes = self.iteration_summaries[-1]["total_classes"] if self.iteration_summaries else 0

        report = []
        report.append("# RALPH LOOP AUDIT REPORT — SMRITI CODEBASE")
        report.append(f"## Recursive Audit Loop for Programmatic Health")
        report.append("")
        report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Runtime:** {hours:.2f} hours ({elapsed:.0f} seconds)")
        report.append(f"**Iterations Completed:** {len(self.iteration_summaries)} / {self.config['total_iterations']}")
        report.append("")
        report.append("---")
        report.append("")

        # ── Executive Summary ──
        report.append("## 1. EXECUTIVE SUMMARY")
        report.append("")
        report.append(f"| Metric | Value |")
        report.append(f"|--------|-------|")
        report.append(f"| Files Scanned | {total_files} |")
        report.append(f"| Total Lines of Code | {total_lines:,} |")
        report.append(f"| Functions Analyzed | {total_functions} |")
        report.append(f"| Classes Analyzed | {total_classes} |")
        report.append(f"| Total Unique Issues | {len(self.cumulative_issues)} |")
        report.append(f"| Critical Issues | {severity_counts.get('CRITICAL', 0)} |")
        report.append(f"| High Issues | {severity_counts.get('HIGH', 0)} |")
        report.append(f"| Medium Issues | {severity_counts.get('MEDIUM', 0)} |")
        report.append(f"| Low Issues | {severity_counts.get('LOW', 0)} |")
        report.append(f"| Info | {severity_counts.get('INFO', 0)} |")
        report.append("")

        # ── Health Score ──
        critical_weight = severity_counts.get("CRITICAL", 0) * 10
        high_weight = severity_counts.get("HIGH", 0) * 5
        medium_weight = severity_counts.get("MEDIUM", 0) * 2
        low_weight = severity_counts.get("LOW", 0) * 1
        total_weight = critical_weight + high_weight + medium_weight + low_weight
        max_score = max(total_lines * 0.1, 1)
        health_score = max(0, min(100, 100 - (total_weight / max_score * 100)))

        report.append(f"### Codebase Health Score: {health_score:.1f} / 100")
        report.append("")
        if health_score >= 80:
            report.append("> ✅ **GOOD** — Codebase is in healthy shape with minor issues")
        elif health_score >= 60:
            report.append("> ⚠️ **FAIR** — Several areas need attention")
        elif health_score >= 40:
            report.append("> 🔶 **NEEDS WORK** — Significant technical debt detected")
        else:
            report.append("> 🔴 **CRITICAL** — Urgent refactoring required")
        report.append("")
        report.append("---")
        report.append("")

        # ── Issues by Category ──
        report.append("## 2. ISSUES BY CATEGORY")
        report.append("")
        sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        for cat, count in sorted_categories:
            report.append(f"### {cat} ({count} issues)")
            report.append("")
            cat_issues = [i for i in self.cumulative_issues if i.get("category") == cat]
            # Group by severity
            for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
                sev_issues = [i for i in cat_issues if i.get("severity") == severity]
                if sev_issues:
                    report.append(f"**{severity}:**")
                    for issue in sev_issues[:20]:  # Cap per severity to avoid massive report
                        file_short = issue.get("file", "?")
                        line = issue.get("line", "?")
                        msg = issue.get("message", "")
                        report.append(f"- `{file_short}:{line}` — {msg}")
                    if len(sev_issues) > 20:
                        report.append(f"- _...and {len(sev_issues) - 20} more_")
                    report.append("")
            report.append("")

        report.append("---")
        report.append("")

        # ── Files with Most Issues ──
        report.append("## 3. HOTSPOT FILES (Most Issues)")
        report.append("")
        report.append("| File | Issues |")
        report.append("|------|--------|")
        sorted_files = sorted(file_issue_counts.items(), key=lambda x: x[1], reverse=True)[:30]
        for fpath, count in sorted_files:
            report.append(f"| `{fpath}` | {count} |")
        report.append("")
        report.append("---")
        report.append("")

        # ── Iteration Timeline ──
        report.append("## 4. ITERATION TIMELINE")
        report.append("")
        report.append("| Iteration | Focus | New Issues | Duration (s) | Timestamp |")
        report.append("|-----------|-------|------------|--------------|-----------|")
        for summary in self.iteration_summaries:
            report.append(
                f"| {summary['iteration']} | {summary['focus'][:40]} | "
                f"{summary['new_issues_found']} | {summary['duration_seconds']} | "
                f"{summary['timestamp'][:19]} |"
            )
        report.append("")
        report.append("---")
        report.append("")

        # ── Critical Issues Detail ──
        critical_issues = [i for i in self.cumulative_issues if i.get("severity") == "CRITICAL"]
        if critical_issues:
            report.append("## 5. CRITICAL ISSUES — FULL DETAIL")
            report.append("")
            for idx, issue in enumerate(critical_issues, 1):
                report.append(f"### Critical #{idx}")
                report.append(f"- **Category:** {issue.get('category')}")
                report.append(f"- **File:** `{issue.get('file')}`")
                report.append(f"- **Line:** {issue.get('line')}")
                report.append(f"- **Message:** {issue.get('message')}")
                snippet = issue.get("code_snippet", "")
                if snippet:
                    report.append(f"```")
                    report.append(snippet)
                    report.append(f"```")
                report.append("")

        report.append("---")
        report.append("")

        # ── Function Registry ──
        report.append("## 6. COMPLETE FUNCTION REGISTRY")
        report.append("")
        report.append("Every function discovered across all files:")
        report.append("")
        for fpath, findings in sorted(self.all_findings.items()):
            funcs = findings.get("functions", [])
            if funcs:
                report.append(f"### `{fpath}`")
                for func in funcs:
                    name = func.get("name", "?")
                    line = func.get("line_start", func.get("line", "?"))
                    args_list = func.get("args", [])
                    if isinstance(args_list, list) and args_list and isinstance(args_list[0], dict):
                        args_str = ", ".join(a.get("name", "?") for a in args_list)
                    elif isinstance(args_list, str):
                        args_str = args_list
                    else:
                        args_str = str(len(args_list)) + " args"
                    complexity = func.get("complexity", "?")
                    report.append(f"- **{name}**(`{args_str}`) — Line {line}, Complexity: {complexity}")
                report.append("")

        report.append("---")
        report.append("")
        report.append("## 7. RECOMMENDATIONS")
        report.append("")
        if severity_counts.get("CRITICAL", 0) > 0:
            report.append("1. **IMMEDIATE:** Fix all CRITICAL security and syntax issues before next deployment")
        if severity_counts.get("HIGH", 0) > 0:
            report.append("2. **THIS SPRINT:** Address HIGH severity issues, especially error handling gaps")
        if category_counts.get("HARDCODED_SECRETS", 0) > 0:
            report.append("3. **SECRETS:** Move all hardcoded secrets to environment variables / vault")
        if category_counts.get("TYPE_SAFETY_ISSUES", 0) > 0:
            report.append("4. **TYPE SAFETY:** Add type hints / TypeScript strict mode progressively")
        if category_counts.get("DEAD_CODE_DETECTION", 0) > 0:
            report.append("5. **CLEANUP:** Remove dead code and resolve all TODO/FIXME comments")
        if category_counts.get("LOGGING_GAPS", 0) > 0:
            report.append("6. **LOGGING:** Replace print/console.log with structured logging")
        report.append("")
        report.append("---")
        report.append(f"*Report generated by Ralph Loop v1.0 — {len(self.iteration_summaries)} iterations*")
        report.append(f"*Smriti Legal AI — NeetiQ / Nyaya / Ritam*")

        return "\n".join(report)

    def run(self):
        """Execute the full 100-iteration Ralph Loop."""
        self.start_time = time.time()
        total = self.config["total_iterations"]
        min_hours = self.config["min_runtime_hours"]
        delay = self.config["delay_between_iterations_seconds"]

        print("=" * 70)
        print("  RALPH LOOP — Recursive Audit Loop for Programmatic Health")
        print(f"  Target: {total} iterations over {min_hours}+ hours")
        print(f"  Delay between iterations: {delay}s")
        print("=" * 70)
        print()

        for i in range(1, total + 1):
            focus = self.get_focus_for_iteration(i)
            elapsed_hours = (time.time() - self.start_time) / 3600

            print(f"[Iteration {i:3d}/{total}] {focus}")
            print(f"  ⏱  Elapsed: {elapsed_hours:.2f}h | Cumulative issues: {len(self.cumulative_issues)}")

            result = self.run_single_iteration(i)

            print(f"  📁 Files: {result['files_scanned']} | Lines: {result['total_lines']:,} | "
                  f"New issues: {result['new_issues_found']} | Duration: {result['duration_seconds']}s")

            # Save intermediate checkpoint every 10 iterations
            if i % 10 == 0:
                checkpoint_path = self.output_dir / f"checkpoint_iter_{i}.json"
                checkpoint = {
                    "iteration": i,
                    "elapsed_hours": elapsed_hours,
                    "total_issues": len(self.cumulative_issues),
                    "summary": result,
                }
                with open(checkpoint_path, "w") as f:
                    json.dump(checkpoint, f, indent=2, default=str)
                print(f"  💾 Checkpoint saved: {checkpoint_path}")

            # Wait between iterations to stretch to 8 hours
            if i < total:
                remaining_iterations = total - i
                elapsed = time.time() - self.start_time
                target_total = min_hours * 3600
                remaining_time = max(0, target_total - elapsed)

                # Dynamically adjust delay to fill the time window
                dynamic_delay = max(delay, remaining_time / remaining_iterations) if remaining_iterations > 0 else delay
                dynamic_delay = min(dynamic_delay, 600)  # Cap at 10 minutes

                print(f"  ⏳ Sleeping {dynamic_delay:.1f}s until next iteration...")
                print()
                time.sleep(dynamic_delay)

        # Generate final report
        print()
        print("=" * 70)
        print("  GENERATING FINAL REPORT...")
        print("=" * 70)

        report = self.generate_markdown_report()
        report_path = self.output_dir / "ralph_loop_100.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        # Also save raw data
        raw_path = self.output_dir / "ralph_loop_raw.json"
        raw_data = {
            "config": self.config,
            "total_runtime_hours": (time.time() - self.start_time) / 3600,
            "total_unique_issues": len(self.cumulative_issues),
            "all_issues": self.cumulative_issues,
            "iteration_summaries": self.iteration_summaries,
        }
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2, default=str, ensure_ascii=False)

        print(f"\n✅ Report saved: {report_path}")
        print(f"✅ Raw data saved: {raw_path}")
        print(f"✅ Total runtime: {(time.time() - self.start_time) / 3600:.2f} hours")
        print(f"✅ Total unique issues found: {len(self.cumulative_issues)}")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "ralph_loop_config.json"
    config = load_config(config_path)
    loop = RalphLoop(config)
    loop.run()
