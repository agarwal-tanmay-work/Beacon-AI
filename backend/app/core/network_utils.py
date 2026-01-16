import socket
import logging

logger = logging.getLogger(__name__)

def force_ipv4_resolution():
    """
    Patches socket.getaddrinfo to filter out non-IPv4 results.
    This fixes 'Network is unreachable' on Render when the container tries to use IPv6 
    routes that are not properly configured or reachable for Supabase.
    """
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(*args, **kwargs):
        # Filter results to strictly include only AF_INET (IPv4)
        try:
            res = original_getaddrinfo(*args, **kwargs)
            # Filter for AF_INET family (usually integer 2)
            return [r for r in res if r[0] == socket.AF_INET]
        except Exception as e:
            # If resolution itself fails, re-raise
            raise e

    socket.getaddrinfo = patched_getaddrinfo
    logger.info("Network Patch: FORCED IPv4 Resolution (socket.getaddrinfo patched).")
