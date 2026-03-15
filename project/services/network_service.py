from __future__ import annotations

import shutil
import socket
import subprocess
from typing import Any, Dict, List

from project.core import config
from project.services.document_service import record_system_event
from project.services.settings_service import set_setting
from project.utils.logging_utils import log_error


def _run(args: List[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout or config.SUBPROCESS_TIMEOUT,
        check=False,
    )


def _command_exists(name: str) -> bool:
    return bool(shutil.which(name))


def _safe_lines(value: str) -> List[str]:
    return [line.strip() for line in (value or '').splitlines() if line.strip()]


def _parse_device_status(stdout: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for raw in _safe_lines(stdout):
        parts = raw.split(':')
        if len(parts) < 4:
            continue
        device, dev_type, state, connection = parts[:4]
        rows.append({
            'device': device,
            'type': dev_type,
            'state': state,
            'connection': connection,
        })
    return rows


def _parse_ip_lines(stdout: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for raw in _safe_lines(stdout):
        parts = raw.split()
        if len(parts) < 4:
            continue
        iface = parts[1]
        address = parts[3]
        rows.append({'interface': iface, 'address': address})
    return rows


def _parse_wifi_scan(stdout: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for raw in _safe_lines(stdout):
        parts = raw.split(':')
        if len(parts) < 5:
            continue
        active, ssid, signal, security, bars = parts[:5]
        ssid = ssid.strip()
        if not ssid:
            ssid = '<skriven SSID>'
        try:
            signal_value = int(signal)
        except Exception:
            signal_value = 0
        rows.append({
            'active': str(active).strip().lower() in {'yes', 'true', '*'},
            'ssid': ssid,
            'signal': signal_value,
            'security': security or '-',
            'bars': bars or '-',
        })
    rows.sort(key=lambda r: (0 if r.get('active') else 1, -int(r.get('signal') or 0), str(r.get('ssid') or '').lower()))
    return rows


def get_network_snapshot() -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {
        'hostname': socket.gethostname(),
        'nmcli_available': _command_exists('nmcli'),
        'ip_available': _command_exists('ip'),
        'interfaces': [],
        'ip_addresses': [],
        'wifi_networks': [],
        'internet_status': 'unknown',
        'internet_ok': None,
        'current_ssid': '',
        'current_connection': '',
        'device_summary': '',
        'raw': {},
        'ok': True,
        'message': 'Mrežni status učitan.',
    }

    try:
        if snapshot['nmcli_available']:
            dev = _run(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE,CONNECTION', 'device', 'status'], timeout=10)
            snapshot['raw']['nmcli_device_status'] = (dev.stdout or dev.stderr or '').strip()
            if dev.returncode == 0:
                snapshot['interfaces'] = _parse_device_status(dev.stdout)
                active_connections = [row for row in snapshot['interfaces'] if row.get('state') == 'connected']
                wifi_active = next((row for row in active_connections if row.get('type') == 'wifi'), None)
                if wifi_active:
                    snapshot['current_ssid'] = wifi_active.get('connection', '')
                if active_connections:
                    snapshot['current_connection'] = ', '.join(sorted({row.get('connection', '') for row in active_connections if row.get('connection')}))

            conn = _run(['nmcli', '-t', '-f', 'STATE', 'networking', 'connectivity', 'check'], timeout=8)
            snapshot['raw']['nmcli_connectivity'] = (conn.stdout or conn.stderr or '').strip()
            state = (conn.stdout or '').strip().lower()
            if state:
                snapshot['internet_status'] = state
                snapshot['internet_ok'] = state in {'full', 'portal', 'limited'}

        if snapshot['ip_available']:
            ip_proc = _run(['ip', '-o', '-4', 'addr', 'show', 'up'], timeout=10)
            snapshot['raw']['ip_addr'] = (ip_proc.stdout or ip_proc.stderr or '').strip()
            if ip_proc.returncode == 0:
                snapshot['ip_addresses'] = _parse_ip_lines(ip_proc.stdout)

            route_proc = _run(['ip', 'route', 'show', 'default'], timeout=10)
            snapshot['raw']['ip_route_default'] = (route_proc.stdout or route_proc.stderr or '').strip()

        if snapshot['nmcli_available']:
            wifi_proc = _run(['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL,SECURITY,BARS', 'device', 'wifi', 'list', '--rescan', 'auto'], timeout=15)
            snapshot['raw']['wifi_scan'] = (wifi_proc.stdout or wifi_proc.stderr or '').strip()
            if wifi_proc.returncode == 0:
                snapshot['wifi_networks'] = _parse_wifi_scan(wifi_proc.stdout)

        device_parts = []
        for row in snapshot['interfaces']:
            device_parts.append(f"{row.get('device')}: {row.get('type')} / {row.get('state')} / {row.get('connection') or '-'}")
        snapshot['device_summary'] = '\n'.join(device_parts) if device_parts else 'Mrežni uređaji nisu dostupni.'

        if snapshot['current_ssid']:
            snapshot['message'] = f"Aktivna Wi‑Fi mreža: {snapshot['current_ssid']}"
        elif snapshot['current_connection']:
            snapshot['message'] = f"Aktivna konekcija: {snapshot['current_connection']}"
        elif snapshot['ip_addresses']:
            snapshot['message'] = 'Mreža djeluje aktivno, ali nema očitan SSID.'
        else:
            snapshot['message'] = 'Trenutno nema aktivne mrežne veze.'
    except Exception as e:
        snapshot['ok'] = False
        snapshot['message'] = f'Mrežni status nije dostupan: {e}'
        log_error(f'[NETWORK] snapshot failed: {e}')
    return snapshot


def scan_wifi_networks() -> Dict[str, Any]:
    if not _command_exists('nmcli'):
        return {
            'ok': False,
            'code': 'NMCLI_MISSING',
            'message': 'nmcli nije dostupan. Instaliraj/omogući NetworkManager za touchscreen Wi‑Fi setup.',
            'networks': [],
        }
    try:
        proc = _run(['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL,SECURITY,BARS', 'device', 'wifi', 'list', '--rescan', 'yes'], timeout=20)
        rows = _parse_wifi_scan(proc.stdout) if proc.returncode == 0 else []
        return {
            'ok': proc.returncode == 0,
            'code': 'OK' if proc.returncode == 0 else 'SCAN_FAILED',
            'message': 'Wi‑Fi mreže osvježene.' if proc.returncode == 0 else (proc.stderr or proc.stdout or 'Skeniranje nije uspjelo.'),
            'networks': rows,
            'stdout': proc.stdout,
            'stderr': proc.stderr,
        }
    except Exception as e:
        log_error(f'[NETWORK] scan failed: {e}')
        return {'ok': False, 'code': 'SCAN_ERROR', 'message': str(e), 'networks': []}


def connect_wifi_network(ssid: str, password: str = '', *, hidden: bool = False) -> Dict[str, Any]:
    normalized_ssid = (ssid or '').strip()
    if not normalized_ssid:
        raise ValueError('SSID ne može biti prazan.')
    if not _command_exists('nmcli'):
        return {
            'ok': False,
            'code': 'NMCLI_MISSING',
            'message': 'nmcli nije dostupan. Instaliraj/omogući NetworkManager za touchscreen Wi‑Fi setup.',
        }
    cmd = ['nmcli', 'device', 'wifi', 'connect', normalized_ssid]
    if password:
        cmd += ['password', password]
    if hidden:
        cmd += ['hidden', 'yes']
    try:
        proc = _run(cmd, timeout=45)
        ok = proc.returncode == 0
        message = (proc.stdout or proc.stderr or '').strip() or ('Wi‑Fi konekcija uspostavljena.' if ok else 'Wi‑Fi konekcija nije uspjela.')
        code = 'OK' if ok else 'CONNECT_FAILED'
        if ok:
            set_setting('network_last_connected_ssid', normalized_ssid)
            set_setting('network_last_tested_at', __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            record_system_event('wifi_connected', f'Wi‑Fi connected: {normalized_ssid}')
        else:
            record_system_event('wifi_connect_failed', f'Wi‑Fi connect failed: {normalized_ssid} | {message}', level='warning')
        return {
            'ok': ok,
            'code': code,
            'message': message,
            'ssid': normalized_ssid,
            'stdout': proc.stdout,
            'stderr': proc.stderr,
        }
    except Exception as e:
        log_error(f'[NETWORK] connect failed: {e}')
        return {'ok': False, 'code': 'CONNECT_ERROR', 'message': str(e), 'ssid': normalized_ssid}


def get_saved_wifi_connections() -> List[Dict[str, str]]:
    if not _command_exists('nmcli'):
        return []
    try:
        proc = _run(['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show'], timeout=10)
        if proc.returncode != 0:
            return []
        rows: List[Dict[str, str]] = []
        for raw in _safe_lines(proc.stdout):
            parts = raw.split(':')
            if len(parts) < 3:
                continue
            name, conn_type, device = parts[:3]
            if conn_type != '802-11-wireless':
                continue
            rows.append({'name': name, 'type': conn_type, 'device': device})
        rows.sort(key=lambda r: str(r.get('name') or '').lower())
        return rows
    except Exception as e:
        log_error(f'[NETWORK] saved connections failed: {e}')
        return []


def forget_wifi_connection(connection_name: str) -> Dict[str, Any]:
    normalized = (connection_name or '').strip()
    if not normalized:
        raise ValueError('Naziv konekcije ne može biti prazan.')
    if not _command_exists('nmcli'):
        return {'ok': False, 'code': 'NMCLI_MISSING', 'message': 'nmcli nije dostupan.'}
    try:
        proc = _run(['nmcli', 'connection', 'delete', normalized], timeout=15)
        ok = proc.returncode == 0
        message = (proc.stdout or proc.stderr or '').strip() or ('Konekcija obrisana.' if ok else 'Brisanje konekcije nije uspjelo.')
        if ok:
            record_system_event('wifi_connection_deleted', f'Wi‑Fi connection removed: {normalized}')
        return {'ok': ok, 'code': 'OK' if ok else 'DELETE_FAILED', 'message': message, 'name': normalized}
    except Exception as e:
        log_error(f'[NETWORK] forget failed: {e}')
        return {'ok': False, 'code': 'DELETE_ERROR', 'message': str(e), 'name': normalized}


def format_network_snapshot(snapshot: Dict[str, Any]) -> str:
    lines = [f"Hostname: {snapshot.get('hostname', '-')}"]
    if snapshot.get('current_ssid'):
        lines.append(f"Aktivni SSID: {snapshot.get('current_ssid')}")
    if snapshot.get('current_connection'):
        lines.append(f"Aktivne konekcije: {snapshot.get('current_connection')}")
    if snapshot.get('ip_addresses'):
        lines.append('IPv4 adrese:')
        for row in snapshot.get('ip_addresses', []):
            lines.append(f"  - {row.get('interface')}: {row.get('address')}")
    if snapshot.get('interfaces'):
        lines.append('Uređaji:')
        for row in snapshot.get('interfaces', []):
            lines.append(f"  - {row.get('device')}: {row.get('type')} / {row.get('state')} / {row.get('connection') or '-'}")
    lines.append(f"Internet status: {snapshot.get('internet_status', 'unknown')}")
    return '\n'.join(lines)
