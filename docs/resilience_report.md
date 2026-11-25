# Resilience tests (2026-11-22 21:14, us-east-1)

| Test | Failure injected | Expected | Observed | Recovery (s) | Result |
|---|---|---|---|---|---|
| crash-app | kill -9 of the GlassFish process | systemd restarts GlassFish by itself (Restart=always); the app comes back with the same data | 1x HTTP 200, 3x HTTP 404, 6x HTTP 502; data before {'restaurants': 7, 'reviews': 15}, after {'restaurants': 7, 'reviews': 15} | 21.2 | PASS |
| crash-db | kill -9 of the mysqld process (a crash, not a manual stop) | while MySQL is down the API answers 500 (it does not crash); Docker restarts MySQL (unless-stopped); data intact | 1x HTTP 200, 2x HTTP 500; data before {'restaurants': 7, 'reviews': 15}, after {'restaurants': 7, 'reviews': 15}; errors were clean HTTP codes | 4.5 | PASS |
| load | 300 requests with 20 concurrent users, then 60 simultaneous login attempts | no failed request; nginx limits the login burst (HTTP 503) and the API keeps answering | 300/300 requests OK in 2.6s (116 req/s), median 163 ms, p95 192 ms; login burst: 5 answered 401, 48 blocked by the limiter; API after the burst: HTTP 200 | - | PASS |
| bad-war | publish a file that is not a WAR as the new version | the file is rejected before touching the running app: zero downtime | 5x HTTP 200; deployer log shows the expected lines; API at the end: HTTP 200 | no outage | PASS |
| bad-war | publish a WAR with a broken web.xml as the new version | GlassFish fails to deploy it and the previous version is restored automatically | 13x HTTP 200, 1x HTTP 404; deployer log shows the expected lines; API at the end: HTTP 200 | 6.0 | PASS |
| server-loss | terminate the EC2 instance (server and disks lost) | deploy.py rebuilds the server, the Elastic IP is reattached and the latest backup restores the data | deploy.py exit code 0; data before {'restaurants': 7, 'reviews': 15}, after {'restaurants': 7, 'reviews': 15} | 272.6 | PASS |
