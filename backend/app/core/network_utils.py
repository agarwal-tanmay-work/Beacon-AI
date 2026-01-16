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
        # Enforce AF_INET (IPv4) if family is unspecified or AF_UNSPEC
        if 'family' in kwargs:
            if kwargs['family'] == socket.AF_UNSPEC:
                kwargs['family'] = socket.AF_INET
        elif len(args) > 2 and args[2] == socket.AF_UNSPEC:
            # args structure: host, port, family, type, proto, flags
            args_list = list(args)
            args_list[2] = socket.AF_INET
            args = tuple(args_list)
        
        # Fallback: Filter results manually just in case
        try:
            res = original_getaddrinfo(*args, **kwargs)
            ipv4_res = [r for r in res if r[0] == socket.AF_INET]
            if ipv4_res:
                return ipv4_res
            return res
        except socket.gaierror as e:
            logger.error(f"DNS Resolution failed for {args[0]}: {e}")
            raise

    socket.getaddrinfo = patched_getaddrinfo
    logger.info("Applied IPv4-only network patch.")
