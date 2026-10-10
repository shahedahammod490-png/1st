"""Loopback-only research service: python -m ocurisk_lab.server."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import logging
import mimetypes
from pathlib import Path
import socket
from urllib.parse import unquote, urlsplit

from .schema import ValidationError, require
from .store import runtime_versions
from .research_store import ResearchStore, MAX_MEDIA_BYTES, json_text
from .jobs import JobManager
import shutil
import subprocess

MAX_REQUEST_BYTES = 34 * 1024 * 1024
WEB = Path(__file__).parent / 'web'


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ValidationError('Non-finite JSON number')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValidationError('Invalid strict JSON') from exc


def capabilities():
    return {'capture_import': 'IMPLEMENTED', 'manual_anatomical_annotation': 'IMPLEMENTED', 'candidate_image_features': 'IMPLEMENTED', 'advanced_models': 'IMPLEMENTED_UNTRAINED_OR_RESEARCH_ONLY', 'clinical_prediction': 'AWAITING_REFERENCE_DATA', 'clinical_uncertainty': 'NOT_IMPLEMENTED', 'reference_dataset_registry': 'IMPLEMENTED_CALLER_SUPPLIED_UNVERIFIED', 'verified_reference_dataset': None, 'phone_connection': 'NOT_VERIFIED', 'physical_illumination': 'NOT_VERIFIED', 'geometry_calibration': 'NOT_VERIFIED', 'prediction': None, 'uncertainty': None}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def _host(self):
        hosts = self.headers.get_all('Host', [])
        require(len(hosts) == 1, 'Exactly one Host header required')
        host = hosts[0]
        require(host in self.server.allowed_hosts, 'Host is not an allowed loopback authority')
        return host

    def _route(self):
        require(not self.path.startswith('//'), 'Invalid request path')
        parsed = urlsplit(self.path)
        require(not parsed.scheme and not parsed.netloc and not parsed.fragment, 'Invalid request target')
        from urllib.parse import parse_qs
        self.query = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
        path = unquote(parsed.path, errors='strict')
        require('\\' not in path and '\x00' not in path and not any(part in ('.', '..') for part in path.split('/')), 'Unsafe request path')
        return path.split('/')[1:]

    def _send(self, status, body, content_type='application/json; charset=utf-8', disposition=None):
        if not isinstance(body, bytes):
            body = json_text(body).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if disposition:
            self.send_header('Content-Disposition', disposition)
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, disposition=None):
        size = path.stat().st_size
        content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        start, end, status = 0, size - 1, 200
        header = self.headers.get('Range')
        if header:
            import re
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
            require(match is not None and any(match.groups()), 'Invalid byte range')
            a, b = match.groups()
            if not a:
                start, end = max(0, size - int(b)), size - 1
            else:
                start, end = int(a), int(b) if b else size - 1
            if start >= size or end < start:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            end, status = min(end, size - 1), 206
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(max(0, end-start+1)))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        if disposition:
            self.send_header('Content-Disposition', disposition)
        self.end_headers()
        with path.open('rb') as stream:
            stream.seek(start)
            remaining = end-start+1
            while remaining > 0:
                chunk = stream.read(min(1024*1024, remaining))
                if not chunk: break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _research(self, method, route, payload=None):
        store = self.server.store
        if method == 'GET':
            if route == ['legacy'] or route == ['legacy', ''] or route == ['legacy', 'index.html']:
                return self._file(WEB / 'legacy' / 'index.html'), True
            if len(route) == 2 and route[0] == 'legacy' and route[1] in ('app.js', 'style.css'):
                return self._file(WEB / 'legacy' / route[1]), True
            if route == ['api', 'experiments']:
                return self._send(200, store.records('experiment')), True
            if route == ['api', 'dataset']:
                rows = store.records('experiment')
                for key in ('mode', 'data_origin'):
                    if key in self.query:
                        rows = [x for x in rows if x[key] == self.query[key][0]]
                if 'q' in self.query:
                    q = self.query['q'][0].lower()
                    rows = [x for x in rows if q in json_text(x).lower()]
                return self._send(200, rows), True
            if route == ['api', 'device']:
                return self._send(200, device_status()), True
            if route == ['api', 'overview']:
                experiments, jobs = store.records('experiment'), store.records('job')
                return self._send(200, {'counts': {'experiments': len(experiments), 'media': len(store.records('media')), 'jobs': len(jobs), 'references': len(store.records('reference')), 'reviews': len(store.records('review'))}, 'recent_experiments': experiments[-10:][::-1], 'recent_jobs': jobs[-10:][::-1], 'device': device_status(), 'software': runtime_versions(), 'scientific_blockers': ['Device geometry and illumination unverified', 'No approved clinical validation', 'Candidate signal is not confirmed retinal reflex']}), True
            if route == ['api', 'algorithms']:
                from .optical_compare import registry
                return self._send(200, registry()), True
            if route == ['api', 'jobs']:
                return self._send(200, store.records('job')), True
            if route == ['api', 'models']:
                return self._send(200, self.server.models.registry()), True
            if len(route) == 3 and route[:2] == ['api', 'models']:
                return self._send(200, self.server.models.model(route[2])), True
            if len(route) == 3 and route[:2] == ['api', 'experiments']:
                return self._send(200, store.experiment(route[2])), True
            if len(route) == 4 and route[:2] == ['api', 'experiments'] and route[3] == 'export':
                archive = store.export(route[2])
                try:
                    self._file(archive, f'attachment; filename="experiment-{route[2]}.zip"')
                finally:
                    archive.unlink(missing_ok=True)
                return None, True
            if len(route) == 3 and route[:2] == ['api', 'media']:
                return self._send(200, store.media(route[2])), True
            if len(route) == 4 and route[:2] == ['api', 'media'] and route[3] == 'original':
                return self._file(store.original(route[2])), True
            if len(route) == 3 and route[:2] == ['api', 'jobs']:
                return self._send(200, store.checked_job(route[2])), True
            if len(route) == 5 and route[:2] == ['api', 'jobs'] and route[3] == 'artifacts':
                return self._file(store.artifact(route[2], route[4])), True
        if method == 'POST':
            if route == ['api', 'quality', 'compare']:
                return self._send(200, store.quality_comparison(payload)), True
            if route == ['api', 'experiments']:
                return self._send(201, store.create_experiment(payload)), True
            if len(route) == 4 and route[:2] == ['api', 'experiments'] and route[3] == 'references':
                return self._send(201, store.reference(route[2], payload)), True
            if len(route) == 4 and route[:2] == ['api', 'media']:
                action = route[3]
                if action == 'process':
                    return self._send(202, self.server.jobs.submit(route[2], payload)), True
                if action == 'annotations':
                    return self._send(201, store.annotate(route[2], payload)), True
                if action == 'reviews':
                    return self._send(201, store.review(route[2], payload)), True
            if len(route) == 4 and route[:2] == ['api', 'jobs'] and route[3] == 'cancel':
                require(payload == {}, 'Cancel expects empty object')
                return self._send(200, self.server.jobs.cancel(route[2])), True
            if route == ['api', 'models', 'train']:
                return self._send(201, self.server.models.train(payload)), True
            if len(route) == 4 and route[:2] == ['api', 'models'] and route[3] == 'predict':
                require(isinstance(payload, dict) and set(payload) == {'features'}, 'Predict expects features')
                return self._send(200, self.server.models.predict(route[2], payload['features'])), True
            if route in (['api', 'physics', 'legacy'], ['api', 'physics', 'power-vectors']):
                from .models import legacy_physics, power_vectors
                expected = {'sphere_d', 'cylinder_d', 'axis_deg'} if route[-1] == 'power-vectors' else {'crescent_ratio', 'pupil_diameter_mm', 'reflex_ratio', 'working_distance_cm', 'flash_eccentricity_mm', 'optical_constant_k', 'orientation'}
                require(isinstance(payload, dict) and set(payload) == expected, 'Physics request requires exact explicit parameters')
                result = legacy_physics(payload) if route[-1] == 'legacy' else power_vectors(payload)
                return self._send(200, result), True
        return None, False

    def _dispatch(self, method):
        self._host()
        route = self._route()
        require(not self.query or route == ['api', 'dataset'], 'Query parameters unsupported for this route')
        store = self.server.store
        if method == 'GET':
            if self._research(method, route)[1]:
                return
            if route == ['']:
                return self._file(WEB / 'index.html')
            if len(route) == 1 and route[0] in ('app.js', 'style.css', 'ui.js', 'optical-workspace.js', 'models-workspace.js', 'live-capture.js', 'quality-workspace.js'):
                return self._file(WEB / route[0])
            if route == ['api', 'health']:
                return self._send(200, {'status': 'running', 'service': 'OcuRisk Research Lab', 'runtime_versions': runtime_versions(), 'device_connection': 'NOT_VERIFIED'})
            if route == ['api', 'status']:
                return self._send(200, capabilities())
            if route == ['api', 'captures']:
                return self._send(200, store.captures())
            if len(route) == 3 and route[:2] == ['api', 'captures']:
                return self._send(200, store.capture(route[2]))
            if route == ['api', 'runs']:
                return self._send(200, store.runs())
            if len(route) == 3 and route[:2] == ['api', 'runs']:
                return self._send(200, store.run(route[2]))
            if len(route) == 3 and route[:2] == ['api', 'export']:
                return self._send(200, store.run(route[2]), disposition=f'attachment; filename="run-{route[2]}.json"')
            if len(route) == 4 and route[:2] == ['api', 'artifacts']:
                return self._file(store.artifact_path(route[2], route[3]))
            if len(route) == 4 and route[:2] == ['api', 'images']:
                return self._file(store.image_path(route[2], route[3]))
        if method == 'POST':
            host = self._host()
            origin = self.headers.get('Origin')
            require(origin is None or origin == f'http://{host}', 'Cross-origin writes forbidden')
            require(self.headers.get('Sec-Fetch-Site') in (None, 'same-origin', 'none'), 'Cross-site writes forbidden')
            binary = len(route) == 5 and (route[:2] == ['api', 'experiments'] and route[3] == 'media' or route[:2] == ['api', 'media'] and route[3] == 'sidecars')
            require(self.headers.get_content_type() == ('application/octet-stream' if binary else 'application/json'), 'Invalid Content-Type')
            require(self.headers.get('Transfer-Encoding') is None, 'Transfer-Encoding unsupported')
            lengths = self.headers.get_all('Content-Length', [])
            require(len(lengths) == 1 and lengths[0].isdigit(), 'Content-Length required')
            length = int(lengths[0])
            require(0 < length <= (MAX_MEDIA_BYTES if binary else MAX_REQUEST_BYTES), 'Request exceeds size bound')
            raw = self.rfile.read(length)
            require(len(raw) == length, 'Incomplete request body')
            if binary:
                if route[:2] == ['api', 'media']:
                    return self._send(201, store.sidecar(route[2], route[4], raw))
                mirrored = self.headers.get('X-Mirrored', 'unknown')
                require(mirrored in ('true', 'false', 'unknown'), 'Invalid X-Mirrored')
                return self._send(201, store.import_media(route[2], route[4], raw, self.headers.get('X-Media-Direction', 'STATIC'), {'true': True, 'false': False, 'unknown': None}[mirrored]))
            payload = strict_json(raw)
            if self._research(method, route, payload)[1]:
                return
            if route == ['api', 'captures']:
                return self._send(201, store.import_capture(payload))
            if len(route) == 4 and route[:2] == ['api', 'captures'] and route[3] == 'process':
                require(payload == {}, 'Processing request must be an empty object')
                return self._send(201, store.process(route[2]))
        self._send(404, {'error': 'Route not found'})

    def _handle(self, method):
        try:
            self._dispatch(method)
        except (ValidationError, ValueError) as exc:
            self._send(400, {'error': str(exc)})
        except (KeyError, FileNotFoundError):
            self._send(404, {'error': 'Record or file not found'})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except Exception:
            logging.getLogger(__name__).exception('Unhandled %s %s', method, urlsplit(self.path).path)
            self._send(500, {'error': 'Operation failed; no completed run was persisted'})

    def do_GET(self):
        self._handle('GET')

    def do_POST(self):
        self._handle('POST')


def create_server(host, port, data_dir, analyzer=None):
    # Resolve localhost without allowing arbitrary DNS names or non-loopback binds.
    require(host in ('localhost', '127.0.0.1', '::1'), 'Only loopback host 127.0.0.1, ::1 or localhost is allowed')
    bind_host = '127.0.0.1' if host == 'localhost' else host
    require(ipaddress.ip_address(bind_host).is_loopback, 'Public bind forbidden')
    require(type(port) is int and 0 <= port <= 65535, 'Invalid port')
    class LocalServer(ThreadingHTTPServer):
        address_family = socket.AF_INET6 if ':' in bind_host else socket.AF_INET
        daemon_threads = True
    server = LocalServer((bind_host, port), Handler)
    try:
        server.store = ResearchStore(data_dir, analyzer)
        server.jobs = JobManager(server.store)
        from .models import ModelLab
        server.models = ModelLab(server.store.root)
    except Exception:
        server.server_close()
        raise
    actual_port = server.server_address[1]
    authorities = [f'127.0.0.1:{actual_port}', f'localhost:{actual_port}', f'[::1]:{actual_port}']
    if actual_port == 80:
        authorities += ['127.0.0.1', 'localhost', '[::1]']
    server.allowed_hosts = set(authorities)
    return server


def device_status():
    adb = shutil.which('adb')
    if adb is None:
        return {'status': 'UNAVAILABLE', 'reason': 'adb executable not installed', 'devices': []}
    try:
        result = subprocess.run([adb, 'devices', '-l'], capture_output=True, timeout=4, check=False, text=True)
        return {'status': 'INSPECTED' if result.returncode == 0 else 'ERROR', 'devices': [line for line in result.stdout[:16384].splitlines()[1:] if line.strip()], 'returncode': result.returncode, 'stderr': result.stderr[:4096], 'physical_verification': 'NOT_VERIFIED'}
    except subprocess.TimeoutExpired:
        return {'status': 'UNAVAILABLE', 'reason': 'adb inspection timed out', 'devices': []}
    except OSError as exc:
        return {'status': 'UNAVAILABLE', 'reason': str(exc), 'devices': []}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=8765, type=int)
    parser.add_argument('--data-dir', default='data')
    args = parser.parse_args()
    try:
        server = create_server(args.host, args.port, args.data_dir)
    except ValidationError as exc:
        parser.error(str(exc))
    print(f'OcuRisk research service: http://{args.host}:{server.server_address[1]}', flush=True)
    print(json_text({'runtime_versions': runtime_versions(), 'capabilities': capabilities()}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.jobs.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
