from __future__ import annotations

import datetime as dt
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

from project.core import config
from project.db.db_connection import get_connection
from project.db.db_init import initialize_database
from project.services.document_service import record_system_event
from project.services.settings_service import get_active_template_path, set_active_template_path, set_setting
from project.services.template_validation_service import (
    format_validation_report,
    remember_template_validation,
    summarize_validation_report,
    validate_template_file,
)
from project.utils.logging_utils import log_error

USB_SEARCH_ROOTS = [Path('/media'), Path('/run/media'), Path('/mnt')]
MANAGED_TEMPLATES_DIR = config.VAR_DIR / 'templates'
BACKUPS_DIR = config.VAR_DIR / 'backups'


RESTORE_BLOCKED_KEYS = {'active_template_path'}


def _safe_display_name(path: Path) -> str:
    try:
        return path.name or str(path)
    except Exception:
        return str(path)



def list_usb_mounts() -> List[Dict[str, Any]]:
    mounts: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for root in USB_SEARCH_ROOTS:
        if not root.exists() or not root.is_dir():
            continue
        candidates: List[Path] = []
        if root == Path('/run/media'):
            for child in root.iterdir():
                if child.is_dir():
                    candidates.extend([p for p in child.iterdir() if p.is_dir()])
        elif root == Path('/media'):
            for child in root.iterdir():
                if child.is_dir():
                    inner_dirs = [p for p in child.iterdir() if p.is_dir()]
                    if inner_dirs and (child.name.lower() in {'pi', 'root'} or child.parent == root):
                        candidates.extend(inner_dirs)
                    else:
                        candidates.append(child)
        else:
            candidates.extend([p for p in root.iterdir() if p.is_dir()])

        for mount in candidates:
            try:
                resolved = str(mount.resolve())
            except Exception:
                resolved = str(mount)
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                usage = shutil.disk_usage(mount)
                free_gb = round(usage.free / (1024 ** 3), 2)
            except Exception:
                free_gb = None
            mounts.append({
                'path': resolved,
                'label': _safe_display_name(mount),
                'free_gb': free_gb,
            })
    mounts.sort(key=lambda m: m['path'])
    return mounts



def list_docx_candidates(mount_path: str, *, limit: int = 50) -> List[Dict[str, Any]]:
    base = Path(mount_path)
    if not base.exists() or not base.is_dir():
        return []
    found: List[Dict[str, Any]] = []
    try:
        for path in base.rglob('*.docx'):
            if len(found) >= limit:
                break
            if path.name.startswith('~$'):
                continue
            try:
                stat = path.stat()
            except Exception:
                continue
            found.append({
                'path': str(path),
                'name': path.name,
                'size_kb': max(1, int(stat.st_size / 1024)),
                'modified_at': dt.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
            })
    except Exception as e:
        log_error(f'[STORAGE] DOCX scan failed for {mount_path}: {e}')
        return []
    found.sort(key=lambda row: (row['name'].lower(), row['path'].lower()))
    return found



def list_backup_bundles(mount_path: str, *, limit: int = 30) -> List[Dict[str, Any]]:
    base = Path(mount_path)
    if not base.exists() or not base.is_dir():
        return []
    bundles: List[Dict[str, Any]] = []
    try:
        for manifest_path in base.rglob('manifest.json'):
            if len(bundles) >= limit:
                break
            bundle = manifest_path.parent
            settings_path = bundle / 'settings.json'
            if not settings_path.exists():
                continue
            manifest: Dict[str, Any] = {}
            try:
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            except Exception:
                manifest = {}
            docx_files = sorted(bundle.glob('*.docx'))
            template_name = docx_files[0].name if docx_files else ''
            created_at = manifest.get('created_at') or dt.datetime.fromtimestamp(bundle.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            bundles.append({
                'bundle_path': str(bundle),
                'name': bundle.name,
                'created_at': str(created_at),
                'template_name': template_name,
                'settings_count': len(json.loads(settings_path.read_text(encoding='utf-8'))),
                'has_db': (bundle / config.DB_PATH.name).exists(),
            })
    except Exception as e:
        log_error(f'[STORAGE] Backup scan failed for {mount_path}: {e}')
        return []
    bundles.sort(key=lambda row: str(row.get('created_at') or ''), reverse=True)
    return bundles



def import_template_from_path(source_path: str) -> Dict[str, Any]:
    src = Path(source_path)
    if not src.exists() or not src.is_file() or src.suffix.lower() != '.docx':
        raise ValueError('Odabrani template nije validan .docx fajl.')

    validation = validate_template_file(str(src), run_probe_render=True)
    remember_template_validation(validation)
    if not validation.get('ok'):
        raise ValueError(summarize_validation_report(validation))

    MANAGED_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = ''.join(ch if ch.isalnum() or ch in {'-', '_', '.'} else '_' for ch in src.name)
    target = MANAGED_TEMPLATES_DIR / f'{timestamp}_{safe_name}'
    shutil.copy2(src, target)
    set_active_template_path(str(target))
    record_system_event('template_imported', f'Template imported and activated: {target}')
    return {
        'ok': True,
        'source_path': str(src),
        'target_path': str(target),
        'active_template_path': str(target),
        'message': f'Template uvezen i postavljen aktivnim: {target.name}',
        'validation': validation,
        'validation_report': format_validation_report(validation),
    }



def use_default_template() -> Dict[str, Any]:
    target = Path(config.TEMPLATE_FILE)
    if not target.exists():
        raise FileNotFoundError(f'Default template ne postoji: {target}')
    validation = validate_template_file(str(target), run_probe_render=True)
    remember_template_validation(validation)
    if not validation.get('ok'):
        raise ValueError(summarize_validation_report(validation))
    set_active_template_path(str(target))
    record_system_event('template_default_selected', f'Default template activated: {target}')
    return {
        'ok': True,
        'active_template_path': str(target),
        'message': f'Korišten default template: {target.name}',
        'validation': validation,
        'validation_report': format_validation_report(validation),
    }



def export_backup_to_mount(mount_path: str) -> Dict[str, Any]:
    base = Path(mount_path)
    if not base.exists() or not base.is_dir():
        raise ValueError('USB lokacija nije dostupna.')
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    bundle_name = f'uvjerenja_backup_{ts}'
    bundle = base / bundle_name
    bundle.mkdir(parents=True, exist_ok=True)

    copied: List[str] = []
    if config.DB_PATH.exists():
        db_target = bundle / config.DB_PATH.name
        shutil.copy2(config.DB_PATH, db_target)
        copied.append(db_target.name)

    initialize_database()
    settings_rows: Dict[str, str] = {}
    try:
        with get_connection() as conn:
            rows = conn.execute('SELECT key, value FROM settings ORDER BY key ASC').fetchall()
            settings_rows = {str(r['key']): str(r['value']) for r in rows}
    except Exception as e:
        log_error(f'[STORAGE] Failed to export settings: {e}')

    settings_path = bundle / 'settings.json'
    settings_path.write_text(json.dumps(settings_rows, ensure_ascii=False, indent=2), encoding='utf-8')
    copied.append(settings_path.name)

    active_template = Path(get_active_template_path())
    if active_template.exists() and active_template.is_file():
        template_target = bundle / active_template.name
        shutil.copy2(active_template, template_target)
        copied.append(template_target.name)

    manifest = {
        'created_at': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'app_id': config.APP_ID,
        'var_dir': str(config.VAR_DIR),
        'active_template_path': str(active_template),
        'copied_files': copied,
    }
    manifest_path = bundle / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    copied.append(manifest_path.name)

    set_setting('backup_last_tested_at', dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    set_setting('backup_last_test_mount', str(base))
    record_system_event('backup_exported', f'Backup exported to USB: {bundle}')
    return {
        'ok': True,
        'bundle_path': str(bundle),
        'copied_files': copied,
        'message': f'Backup izvezen na USB: {bundle}',
    }



def restore_backup_bundle(
    bundle_path: str,
    *,
    restore_settings: bool = True,
    restore_template: bool = True,
    restore_db: bool = False,
) -> Dict[str, Any]:
    bundle = Path(bundle_path)
    if not bundle.exists() or not bundle.is_dir():
        raise ValueError('Backup bundle nije pronađen.')
    settings_path = bundle / 'settings.json'
    if restore_settings and not settings_path.exists():
        raise ValueError('settings.json ne postoji u backup bundle-u.')
    if restore_db:
        raise RuntimeError('Restore baze je namjerno isključen u live radu. Za DB restore ugasi aplikaciju i uradi servisni restore ručno.')

    restored_keys: List[str] = []
    template_result = None
    initialize_database()

    if restore_settings:
        settings_data = json.loads(settings_path.read_text(encoding='utf-8'))
        if not isinstance(settings_data, dict):
            raise ValueError('settings.json nije validan backup format.')
        for key, value in settings_data.items():
            if key in RESTORE_BLOCKED_KEYS:
                continue
            set_setting(str(key), str(value))
            restored_keys.append(str(key))

    manifest_path = bundle / 'manifest.json'
    preferred_template = None
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            preferred = Path(str(manifest.get('active_template_path') or '')).name
            if preferred:
                candidate = bundle / preferred
                if candidate.exists() and candidate.is_file():
                    preferred_template = candidate
        except Exception:
            preferred_template = None

    if preferred_template is None:
        docx_files = sorted(bundle.glob('*.docx'))
        preferred_template = docx_files[0] if docx_files else None

    if restore_template and preferred_template is not None:
        template_result = import_template_from_path(str(preferred_template))

    set_setting('backup_last_tested_at', dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    set_setting('backup_last_restore_mode', (('settings' if restore_settings else '') + ('+template' if restore_template else '')).strip('+') or 'none')
    record_system_event('backup_restored', f'Backup restored from USB: {bundle} | settings={int(bool(restore_settings))} template={int(bool(restore_template))}')
    mode_parts = []
    if restore_settings:
        mode_parts.append('postavke')
    if restore_template:
        mode_parts.append('template')
    mode_label = ' + '.join(mode_parts) if mode_parts else 'ništa'
    return {
        'ok': True,
        'bundle_path': str(bundle),
        'restored_keys': restored_keys,
        'restored_settings_count': len(restored_keys),
        'template_result': template_result,
        'restore_settings': restore_settings,
        'restore_template': restore_template,
        'message': f'Backup vraćen iz bundle-a ({mode_label}): {bundle.name}',
    }
