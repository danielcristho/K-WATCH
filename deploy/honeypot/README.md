# Honeypot using Falco

This component implements a honeypot for the K-IDS project.

## Strategy
1. Deploy a vulnerable application (e.g., dvwa or a simple nginx).
2. Monitor it with specific Falco rules.
3. Export alerts to the K-IDS collector.
