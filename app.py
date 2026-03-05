import os

BOOTSTRAP_ALLOW_CIDR = os.environ.get('BOOTSTRAP_ALLOW_CIDR', '')
BOOTSTRAP_ALLOW_PRIVATE = os.environ.get('BOOTSTRAP_ALLOW_PRIVATE', 'false')

# Implement your logic here to check IPs against the allowlist.