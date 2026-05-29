from django.db import models
from core.models import Member, User

class Loan(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='loans')
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Annual Interest Rate %", null=True, blank=True, default=12.00)
    issued_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2)
    loan_status = models.CharField(
        max_length=50, 
        choices=[
            ('pending', 'Pending'), 
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('active', 'Active'), 
            ('closed', 'Closed'), 
            ('defaulted', 'Defaulted')
        ], 
        default='pending'
    )
    reason = models.TextField(null=True, blank=True, help_text="Why the member is requesting the loan")
    approval_comments = models.TextField(null=True, blank=True, help_text="Notes from the committee/treasurer")
    remarks = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_loans')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Loan Request #{self.id} - {self.member.full_name} (${self.principal_amount})"


class LoanRepayment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    payment_date = models.DateField()
    principal_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    interest_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    penalty_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_mode = models.CharField(max_length=50, choices=[('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'), ('cheque', 'Cheque')], default='cash')
    remarks = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_repayments')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Repayment {self.id} for Loan {self.loan_id}"
