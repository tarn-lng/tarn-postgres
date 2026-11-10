"""Run the native driver against an isolated, ephemeral PostgreSQL TLS/SCRAM DB."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TARN = os.environ.get('TARN', str(ROOT.parents[1] / 'tarn/target/debug/tarn'))
IMAGE = os.environ.get('POSTGRES_TEST_IMAGE', 'pgvector/pgvector:pg17')
NAME = f'tarn-registry-postgres-test-{os.getpid()}'


def command(*args, **kw):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kw)


with tempfile.TemporaryDirectory(prefix='tarn-postgres-') as directory:
    root = Path(directory)
    root.chmod(0o755)
    cert, key = root / 'server.crt', root / 'server.key'
    command('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
            '-keyout', str(key), '-out', str(cert), '-days', '1', '-subj', '/CN=localhost',
            '-addext', 'subjectAltName=DNS:localhost')
    # Disposable test key only: copied to a private, postgres-owned path inside
    # this container before PostgreSQL starts; never a production credential.
    key.chmod(0o644)
    executable = root / 'integration'
    command(TARN, 'build', 'integration_test.tarn', '-o', str(executable), cwd=ROOT)
    try:
        command('docker', 'run', '--rm', '-d', '--name', NAME,
                '-e', 'POSTGRES_PASSWORD=local-test-only',
                '-e', 'POSTGRES_HOST_AUTH_METHOD=scram-sha-256',
                '-e', 'POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256',
                '-p', '127.0.0.1::5432', '-v', f'{root}:/fixture:ro',
                '--entrypoint', 'sh', IMAGE, '-c',
                'mkdir /tmp/pg-tls && cp /fixture/server.* /tmp/pg-tls/ && '
                'chown -R postgres:postgres /tmp/pg-tls && chmod 600 /tmp/pg-tls/server.key && '
                'exec docker-entrypoint.sh postgres -c ssl=on '
                '-c ssl_cert_file=/tmp/pg-tls/server.crt -c ssl_key_file=/tmp/pg-tls/server.key')
        for _ in range(100):
            ready = subprocess.run(['docker', 'exec', NAME, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres'], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(command('docker', 'logs', NAME).stdout)
        mapping = command('docker', 'port', NAME, '5432/tcp').stdout.strip()
        port = int(mapping.rsplit(':', 1)[1])
        url = f'postgresql://postgres:local-test-only@localhost:{port}/postgres?sslmode=require'
        result = command(str(executable), url, str(cert), timeout=60)
        print(result.stdout, end='')
        assert result.stdout == 'PostgreSQL TLS + SCRAM + parameters + transactions passed\n'
    except subprocess.CalledProcessError as exc:
        print(exc.stdout, exc.stderr, file=sys.stderr)
        logs = command("docker", "logs", NAME)
        print(logs.stdout, logs.stderr, file=sys.stderr)
        raise
    finally:
        subprocess.run(['docker', 'rm', '-f', '-v', NAME], capture_output=True)
