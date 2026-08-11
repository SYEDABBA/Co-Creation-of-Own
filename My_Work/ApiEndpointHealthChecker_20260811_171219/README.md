    # ApiEndpointHealthChecker

    ## Purpose
    A lightweight, zero-dependency command-line utility for monitoring the availability, HTTP status codes, and response latency of multiple web endpoints concurrently or sequentially.

    ## Usefulness
    Helps DevOps engineers, backend developers, and system administrators quickly verify service uptime, monitor API health after deployments, and detect slow response times without external monitoring software.

    ## How to Use
    Run with a list of URLs:
python script.py https://api.github.com https://httpbin.org/status/200

Run with custom timeout and JSON output:
python script.py --timeout 3.0 --json-out https://api.github.com
