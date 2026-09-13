#!/usr/bin/env python3
"""Deploy only the canonical board routing section, preserving installed skill versions."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PATHS = ['company-os/company-os/SKILL.md',
         'company-os/manage-company-program/SKILL.md',
         'autonomy-suite/strategy/strategy-pillar/SKILL.md',
         'company-os/direct-outcome/SKILL.md',
         'autonomy-suite/strategy/portfolio-direction/SKILL.md']
BEGIN = '<!-- council-os:begin -->'
END = '<!-- council-os:end -->'


def render(text, section):
    if BEGIN in text or END in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) > text.index(END):
            raise ValueError('malformed existing council routing markers')
        a, b = text.index(BEGIN), text.index(END) + len(END)
        return text[:a] + section.rstrip() + text[b:]
    start = text.index('\n# ')
    end = text.index('\n', start + 1)
    return text[:end] + '\n\n' + section + text[end:]


def install(target):
    section = (ROOT / 'docs/council/routing.md').read_text()
    planned = []
    for rel in PATHS:
        p = target / rel
        if any(part.is_symlink() for part in [p, *p.parents]):
            raise ValueError(f'refusing symlink: {p}')
        if not p.exists():
            if rel in ('company-os/direct-outcome/SKILL.md', 'company-os/manage-company-program/SKILL.md'):
                continue  # Older distributions do not have this director.
            raise ValueError(f'missing installed entry point: {p}')
        original = p.read_bytes()
        changed = render(original.decode(), section).encode()
        planned.append((p, original, changed))
    # Install the role before routing any entrypoint to it. Preserve an existing
    # role snapshot as a sibling backup; source remains this repository.
    role = target / 'company-os/company-board'
    if any(part.is_symlink() for part in [role, *role.parents]):
        raise ValueError(f'refusing symlink: {role}')
    source_role = ROOT / 'skills/company-os/company-board'
    role_digest = hashlib.sha256(b''.join(
        str(p.relative_to(source_role)).encode() + p.read_bytes()
        for p in sorted(source_role.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
    )).hexdigest()[:12]
    with tempfile.TemporaryDirectory(dir=role.parent, prefix='.board-install-') as scratch:
        staged = Path(scratch) / 'company-board'
        shutil.copytree(source_role, staged, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        if role.exists():
            backup = Path(scratch) / 'previous'
            os.replace(role, backup)
            try:
                os.replace(staged, role)
            except Exception:
                os.replace(backup, role)
                raise
            archive = target / '.company-board-backups'
            archive.mkdir(exist_ok=True)
            shutil.make_archive(str(archive / ('before-' + role_digest)), 'gztar', backup)
        else:
            os.replace(staged, role)
    receipt = []
    for p, original, changed in planned:
        if p.read_bytes() != original:
            raise ValueError(f'concurrent edit: {p}')
        digest = hashlib.sha256(original).hexdigest()
        if original != changed:
            backup = p.with_name(p.name + '.pre-council-' + digest[:12])
            if not backup.exists():
                with backup.open('xb') as f:
                    f.write(original)
            elif backup.read_bytes() != original:
                raise ValueError(f'backup mismatch: {backup}')
            fd, tmp = tempfile.mkstemp(dir=p.parent, prefix='.council-')
            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write(changed)
                os.replace(tmp, p)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        receipt.append({'path': str(p), 'prior_sha256': digest,
                        'sha256': hashlib.sha256(changed).hexdigest(), 'changed': original != changed})
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps({'ok': True, 'files': install(args.target.expanduser())}, indent=2))
    except (ValueError, OSError) as e:
        parser.exit(1, str(e) + '\n')
