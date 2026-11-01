"""Repository checks for naming and forbidden infrastructure dependencies."""
import argparse
import ast
from pathlib import Path
import re


def check(root):
    issues = []
    infrastructure = {'config', 'db', 'errors', 'logging_config', 'server_logging'}
    for path in sorted((root / 'campus_repair').rglob('*.py')):
        if not re.fullmatch(r'[a-z_][a-z0-9_]*\.py', path.name):
            issues.append(f'{path.relative_to(root)}: invalid module name')
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not re.fullmatch(r'[a-z_][a-z0-9_]*', node.name):
                    issues.append(f'{path.relative_to(root)}:{node.lineno}: invalid function name')
            if isinstance(node, ast.ClassDef) and not re.fullmatch(r'[A-Z][A-Za-z0-9]*', node.name):
                issues.append(f'{path.relative_to(root)}:{node.lineno}: invalid class name')
            if path.stem in infrastructure or 'repositories' in path.parts or 'services' in path.parts:
                names = []
                if isinstance(node, ast.ImportFrom):
                    names = [node.module or ''] + [alias.name for alias in node.names]
                elif isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                forbidden = {'routes', 'services'} if path.stem in infrastructure or 'repositories' in path.parts else {'routes'}
                if any(any(part in forbidden for part in name.split('.')) for name in names):
                    issues.append(f'{path.relative_to(root)}:{node.lineno}: reverse dependency')
    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    issues = check(args.root)
    for issue in issues:
        print(issue)
    print(f'Standards defects: {len(issues)}')
    return bool(issues)


if __name__ == '__main__':
    raise SystemExit(main())
