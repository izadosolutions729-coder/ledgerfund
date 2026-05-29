from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from core.models import Organization, User

class LedgerEntry(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ledger_entries')
    transaction_date = models.DateField()
    transaction_type = models.CharField(max_length=50, choices=[('debit', 'Debit'), ('credit', 'Credit')])
    category = models.CharField(max_length=100) # e.g., 'Bank Balance', 'Member Contributions'
    debit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    balance_after_transaction = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Generic relation to tie ledger entry to any model (e.g., Contribution, Loan, Repayment)
    reference_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    reference_object = GenericForeignKey('reference_type', 'reference_id')
    
    remarks = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_ledger_entries')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} of {self.debit_amount or self.credit_amount} on {self.transaction_date}"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action_type = models.CharField(max_length=50) # e.g., CREATE, UPDATE, DELETE
    affected_table = models.CharField(max_length=100)
    affected_record_id = models.CharField(max_length=50)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action_type} on {self.affected_table} by {self.user}"
