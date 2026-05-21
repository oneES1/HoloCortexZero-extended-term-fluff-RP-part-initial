from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _default_snapshot_path() -> Path:
    configured_data_dir = os.environ.get('HCZ_DATA_DIR') or os.environ.get('DATA_DIR')
    if configured_data_dir:
        return Path(configured_data_dir).expanduser() / 'backups' / '2026-03-28_legacy_presets_snapshot.json'
    return REPO_ROOT / 'backups' / '2026-03-28_legacy_presets_snapshot.json'


DEFAULT_CONFIG_PATH = Path(os.environ.get('HCZ_SYSTEM_CONFIG_PATH', str(REPO_ROOT / 'configs' / 'holo-cortex-zero.yaml')))
DEFAULT_SNAPSHOT_PATH = _default_snapshot_path()


def _load_config_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    return loaded if isinstance(loaded, dict) else {}


def _query_json_via_psycopg(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    dbname: str,
    sql: str,
) -> list[dict[str, Any]]:
    import psycopg2

    conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            value = cur.fetchone()[0]
            if not value:
                return []
            return value if isinstance(value, list) else json.loads(value)
    finally:
        conn.close()


def _exec_drop_via_psycopg(*, host: str, port: int, user: str, password: str, dbname: str) -> None:
    import psycopg2

    conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute('ALTER TABLE IF EXISTS chat_channel DROP COLUMN IF EXISTS preset_id')
            cur.execute('DROP TABLE IF EXISTS presets CASCADE')
    finally:
        conn.close()


def _docker_psql(container: str, user: str, password: str, dbname: str, sql: str) -> str:
    cmd = [
        'docker', 'exec', '-e', f'PGPASSWORD={password}', container,
        'psql', '-U', user, '-d', dbname, '-Atqc', sql,
    ]
    return subprocess.check_output(cmd, text=True).strip()


def _query_json_via_docker(*, container: str, user: str, password: str, dbname: str, sql: str) -> list[dict[str, Any]]:
    raw = _docker_psql(container, user, password, dbname, sql)
    if not raw:
        return []
    return json.loads(raw)


def _exec_drop_via_docker(*, container: str, user: str, password: str, dbname: str) -> None:
    _docker_psql(container, user, password, dbname, 'ALTER TABLE IF EXISTS chat_channel DROP COLUMN IF EXISTS preset_id; DROP TABLE IF EXISTS presets CASCADE;')


def _snapshot_payload(config_path: Path, presets: list[dict[str, Any]], refs: list[dict[str, Any]]) -> dict[str, Any]:
    config_data = _load_config_payload(config_path)
    return {
        'created_at': '2026-03-28',
        'source': {
            'config_path': str(config_path),
        },
        'legacy_config': {
            'AI_CHAT_PRESET_NAME': config_data.get('AI_CHAT_PRESET_NAME'),
            'AI_CHAT_PRESET_SETTING': config_data.get('AI_CHAT_PRESET_SETTING'),
        },
        'presets_count': len(presets),
        'chat_channel_preset_refs_count': len(refs),
        'presets': presets,
        'chat_channel_preset_refs': refs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='导出并删除旧 preset schema')
    parser.add_argument('--config-path', default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument('--snapshot-file', default=str(DEFAULT_SNAPSHOT_PATH))
    parser.add_argument('--db-host', default='127.0.0.1')
    parser.add_argument('--db-port', type=int, default=5432)
    parser.add_argument('--db-user', default='holo_cortex_zero')
    parser.add_argument('--db-password', default='holo_cortex_zero')
    parser.add_argument('--db-name', default='holo_cortex_zero')
    parser.add_argument('--docker-container', default='')
    args = parser.parse_args()

    config_path = Path(args.config_path).expanduser().resolve()
    snapshot_file = Path(args.snapshot_file).expanduser().resolve()
    snapshot_file.parent.mkdir(parents=True, exist_ok=True)

    presets_sql = "select coalesce(json_agg(t), '[]'::json)::text from (select * from presets order by id) t;"
    refs_sql = "select coalesce(json_agg(t), '[]'::json)::text from (select * from chat_channel where preset_id is not null order by id) t;"

    try:
        if args.docker_container:
            presets = _query_json_via_docker(
                container=args.docker_container,
                user=args.db_user,
                password=args.db_password,
                dbname=args.db_name,
                sql=presets_sql,
            )
            refs = _query_json_via_docker(
                container=args.docker_container,
                user=args.db_user,
                password=args.db_password,
                dbname=args.db_name,
                sql=refs_sql,
            )
        else:
            presets = _query_json_via_psycopg(
                host=args.db_host,
                port=args.db_port,
                user=args.db_user,
                password=args.db_password,
                dbname=args.db_name,
                sql=presets_sql,
            )
            refs = _query_json_via_psycopg(
                host=args.db_host,
                port=args.db_port,
                user=args.db_user,
                password=args.db_password,
                dbname=args.db_name,
                sql=refs_sql,
            )
    except Exception as exc:
        print(json.dumps({'ok': False, 'stage': 'snapshot', 'error': f'{type(exc).__name__}: {exc}'}, ensure_ascii=False, indent=2))
        return 1

    snapshot = _snapshot_payload(config_path, presets, refs)
    snapshot_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')

    try:
        if args.docker_container:
            _exec_drop_via_docker(
                container=args.docker_container,
                user=args.db_user,
                password=args.db_password,
                dbname=args.db_name,
            )
        else:
            _exec_drop_via_psycopg(
                host=args.db_host,
                port=args.db_port,
                user=args.db_user,
                password=args.db_password,
                dbname=args.db_name,
            )
    except Exception as exc:
        print(json.dumps({
            'ok': False,
            'stage': 'drop',
            'snapshot_file': str(snapshot_file),
            'error': f'{type(exc).__name__}: {exc}',
        }, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({
        'ok': True,
        'snapshot_file': str(snapshot_file),
        'presets_count': len(presets),
        'chat_channel_preset_refs_count': len(refs),
        'dropped': ['chat_channel.preset_id', 'presets'],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
