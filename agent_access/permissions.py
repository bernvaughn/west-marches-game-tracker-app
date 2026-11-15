"""Custom permissions for agent access, including restricted DCR."""

import logging

from rest_framework.permissions import BasePermission

logger = logging.getLogger("security.oauth")


class RestrictedDCRPermission(BasePermission):
    """
    Restricted Dynamic Client Registration permission.
    
    In DEBUG mode, allows all registrations (for development).
    In production, only allows registrations from pre-approved clients
    or requires manual approval workflow.
    
    This replaces the default AllowAllDCRPermission which allows any
    client to register, which is a security risk.
    """
    
    def has_permission(self, request, view=None):
        from django.conf import settings
        
        debug_value = getattr(settings, 'DEBUG', None)
        logger.info(f"DCR permission check: DEBUG={debug_value}")
        
        # In DEBUG mode, allow all for development convenience
        if debug_value:
            return True
        
        # In production, require explicit approval
        # This could be extended to check against a whitelist of allowed clients,
        # or integrate with an approval workflow
        return False
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)