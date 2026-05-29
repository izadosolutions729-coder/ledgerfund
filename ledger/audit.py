from django.db.models import Model
from .models import AuditLog
from core.models import User
import json

class AuditService:
    @staticmethod
    def log_action(
        user: User,
        action_type: str,
        instance: Model,
        old_value: dict = None,
        new_value: dict = None,
        ip_address: str = None
    ):
        """
        Record an audit log for an action.
        action_type: 'CREATE', 'UPDATE', 'DELETE', etc.
        """
        AuditLog.objects.create(
            user=user,
            action_type=action_type,
            affected_table=instance._meta.db_table,
            affected_record_id=str(instance.pk),
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address
        )
