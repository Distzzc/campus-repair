"""Fill missing local-only demo credentials, never overwrite existing secrets."""
from pathlib import Path
import secrets


def main():
    root = Path(__file__).resolve().parents[1]
    path = root / '.env'
    if not path.exists():
        path.write_text((root / '.env.example').read_text())
    lines = path.read_text().splitlines()
    values = dict(line.split('=', 1) for line in lines if '=' in line and not line.lstrip().startswith('#'))
    updates = {'DEMO_MODE': 'true'}
    for name in ['DEMO_PASSWORD', 'ADMIN_INVITE_CODE', 'WORKER_INVITE_CODE']:
        if not values.get(name, '').strip().strip('"\''):
            updates[name] = secrets.token_urlsafe(20)
    for key, value in updates.items():
        indices = [index for index, line in enumerate(lines) if line.startswith(key + '=')]
        if indices:
            for index in indices:
                lines[index] = key + '=' + value
        else:
            lines.append(key + '=' + value)
    path.write_text('\n'.join(lines) + '\n')
    path.chmod(0o600)
    print('Demo enabled. Credentials remain in your local ignored .env; no values were printed.')


if __name__ == '__main__':
    main()
