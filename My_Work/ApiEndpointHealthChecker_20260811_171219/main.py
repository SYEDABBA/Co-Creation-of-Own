import argparse
import json
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

def check_endpoint(url: str, timeout: float = 10.0) -> dict:
    headers = {'User-Agent': 'ApiEndpointHealthChecker/1.0'}
    req = Request(url, headers=headers)
    start_time = time.time()
    try:
        with urlopen(req, timeout=timeout) as response:
            latency = round((time.time() - start_time) * 1000, 2)
            return {
                'url': url,
                'status': response.status,
                'reason': response.reason,
                'latency_ms': latency,
                'ok': 200 <= response.status < 400
            }
    except HTTPError as e:
        latency = round((time.time() - start_time) * 1000, 2)
        return {
            'url': url,
            'status': e.code,
            'reason': e.reason,
            'latency_ms': latency,
            'ok': False
        }
    except URLError as e:
        latency = round((time.time() - start_time) * 1000, 2)
        return {
            'url': url,
            'status': None,
            'reason': str(e.reason),
            'latency_ms': latency,
            'ok': False
        }
    except Exception as e:
        return {
            'url': url,
            'status': None,
            'reason': str(e),
            'latency_ms': 0.0,
            'ok': False
        }

def main():
    parser = argparse.ArgumentParser(description='API Health Checker Utility')
    parser.add_argument('urls', nargs='+', help='List of HTTP/HTTPS URLs to check')
    parser.add_argument('--timeout', type=float, default=5.0, help='Request timeout in seconds')
    parser.add_argument('--json-out', action='store_true', help='Output results as formatted JSON')
    args = parser.parse_args()

    results = []
    for url in args.urls:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        res = check_endpoint(url, timeout=args.timeout)
        results.append(res)

    if args.json_out:
        print(json.dumps(results, indent=2))
    else:
        print('=' * 65)
        print(f'{"URL":<35} | {"STATUS":<8} | {"LATENCY":<10} | {"STATE":<5}')
        print('=' * 65)
        for r in results:
            status_str = str(r['status']) if r['status'] is not None else 'ERR'
            state_str = 'UP' if r['ok'] else 'DOWN'
            print(f"{r['url'][:35]:<35} | {status_str:<8} | {r['latency_ms']:>7.2f}ms | {state_str:<5}")
        print('=' * 65)

if __name__ == '__main__':
    main()