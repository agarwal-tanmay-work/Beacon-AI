import socket
import logging

logger = logging.getLogger(__name__)

def force_ipv4_resolution():
    """
    Monkey-patch socket.getaddrinfo to filter out IPv6 results.
    This forces the application to use IPv4, avoiding 'Network is unreachable' 
    errors on environments (like specific Render regions) where IPv6 routing 
    to specific providers (like Supabase) is broken or flaky.
    """
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(*args, **kwargs):
        # Use AF_UNSPEC to get both IPv4 and IPv6 results
        # We don't modify args to force AF_INET anymore
        
        try:
            res = original_getaddrinfo(*args, **kwargs)
            
            # Filter for IPv4
            ipv4_res = [r for r in res if r[0] == socket.AF_INET]
            if ipv4_res:
                logger.debug(f"DNS: Returning IPv4 results for {args[0]}")
                return ipv4_res
            
            # Fallback to IPv6 if no IPv4 found
            ipv6_res = [r for r in res if r[0] == socket.AF_INET6]
            if ipv6_res:
                logger.debug(f"DNS: No IPv4 found, returning IPv6 results for {args[0]}")
                return ipv6_res
                
            return res
        except socket.gaierror as e:
            logger.error(f"DNS Resolution failed for {args[0]}: {e}")
            raise

    socket.getaddrinfo = patched_getaddrinfo
    logger.info("Applied IPv4-only network patch.")
