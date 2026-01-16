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

    print("Network Patch: Applied IPv4-only patch to socket.getaddrinfo")

    def patched_getaddrinfo(*args, **kwargs):
        # Allow looking up specific families if requested, but if UNSPEC, default to INET
        # Note: asyncio calls getaddrinfo with family=0 (AF_UNSPEC) usually.
        
        try:
            # Call original
            res = original_getaddrinfo(*args, **kwargs)
            
            # Debugging what we got
            # print(f"DEBUG DNS: Looked up {args[0] if args else '?'}. Got {len(res)} results.")
            
            # Filter for IPv4 (AF_INET = 2)
            ipv4_res = [r for r in res if r[0] == socket.AF_INET]
            
            if ipv4_res:
                # print(f"DEBUG DNS: Returning {len(ipv4_res)} IPv4 addresses.")
                return ipv4_res
            
            # If we are here, NO IPv4 addresses were found.
            # If we return IPv6, it will fail with "Network unreachable".
            # So let's output a warning and return empty/raise to show the real issue.
            print(f"CRITICAL DNS WARNING: Only IPv6 results found for {args[0]}. This environment likely lacks IPv4 connectivity to this host!")
            
            # We explicitly DO NOT return IPv6 results usually, but if we do, it crashes.
            # Let's try to return them anyway but warn? 
            # No, user wants to fix the crash. If we return IPv6 it crashes.
            # If we return empty, it raises GAIErrors.
            # better to raise a clear error.
            raise socket.gaierror(f"No IPv4 address found for {args[0]} (IPv6 suppressed)")

        except socket.gaierror as e:
            # print(f"DNS Resolution failed for {args[0]}: {e}")
            raise

    socket.getaddrinfo = patched_getaddrinfo
    logger.info("Applied IPv4-only network patch.")
