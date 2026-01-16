import socket
import logging

logger = logging.getLogger(__name__)

def force_ipv4_resolution():
    """
    DEPRECATED: Network Patch Neutralized.
    Relying on system default DNS resolution (IPv4/IPv6 auto).
    This fixes 'Network is unreachable' on Render when forcing IPv4.
    """
    # No-op: Do not patch socket.getaddrinfo
    logger.info("Network Patch: Using system default DNS resolution.")
