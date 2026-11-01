"""G01–G04 / R06: documentation and enforceable dependency/naming rules."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys

from conftest import ROOT


def test_G02_layering_and_naming():
    result = subprocess.run([sys.executable, 'scripts/check_standards.py'], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_G02_standards_reject_real_code_mutations(tmp_path):
    shutil.copytree(ROOT / 'campus_repair', tmp_path / 'campus_repair')
    path = tmp_path / 'campus_repair' / 'db.py'
    original = path.read_text()
    for mutation in ['\nfrom campus_repair.routes import health\n', '\ndef BadFunction():\n    pass\n']:
        path.write_text(original + mutation)
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/check_standards.py'), '--root', str(tmp_path)],
                                capture_output=True, text=True)
        assert result.returncode != 0 and 'Standards defects: 1' in result.stdout
    path.write_text(original)
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/check_standards.py'), '--root', str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 0


def test_G01_G02_G03_G04_documents_and_scenario_mapping():
    agents = (ROOT / 'AGENTS.md').read_text()
    for name in ['product', 'backend', 'security', 'testing', 'operations', 'ai']:
        path = ROOT / 'docs' / 'standards' / f'{name}.md'
        text = path.read_text()
        assert f'docs/standards/{name}.md' in agents
        assert '读取时机' in text and '缺陷' in text and '检查' in text
    product = (ROOT / 'docs/standards/product.md').read_text()
    assert all(value in product for value in ['待分配', '待接单', '处理中', '待确认', '已完成', '已取消', '保留负责人'])
    ai = (ROOT / 'docs/standards/ai.md').read_text()
    assert all(value in ai for value in ['原文', '编造', '超时', '评测', '版本', '人工', '尚未'])
    import re
    specs = ROOT / 'openspec/specs'
    capabilities = ('application-foundation', 'engineering-governance',
                    'health-observability', 'reproducible-runtime')
    ids = []
    for capability in capabilities:
        path = specs / capability / 'spec.md'
        ids.extend(re.findall(r'^#### Scenario: ([A-Z]\d{2})', path.read_text(), re.M))
    matrix = (ROOT / 'docs/verification/scenario-matrix.md').read_text()
    assert len(ids) == len(set(ids)) == 26
    assert all(value in matrix for value in ids)


def test_R06_example_and_lockfiles_are_not_ignored():
    example = (ROOT / '.env.example').read_text()
    assert 'DATABASE_PATH=/absolute/path/' in example
    assert 'SECRET_KEY=' not in example
    for name in ['requirements.lock', 'requirements-dev.lock']:
        assert (ROOT / name).is_file()
    ignore = (ROOT / '.gitignore').read_text()
    dockerignore = (ROOT / '.dockerignore').read_text()
    assert '!.env.example' in ignore and '!.env.example' in dockerignore
    assert all(name in ignore for name in ['instance/', 'uploads/', 'logs/', '*.sqlite*', '.env', '.venv/'])
