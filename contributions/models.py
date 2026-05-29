from django.db import models
from core.models import Organization, Member, User

class ContributionPlan(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='contribution_plans')
    plan_name = models.CharField(max_length=255)
    monthly_amount = models.DecimalField(max_digits=12, decimal_places=2)
    penalty_rules = models.TextField(null=True, blank=True)
    active_status = models.BooleanField(default=True)

    def __str__(self):
        return self.plan_name


class Contribution(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='contributions')
    contribution_plan = models.ForeignKey(ContributionPlan, on_delete=models.RESTRICT, related_name='contributions')
    contribution_month = models.DateField(help_text="The month this contribution applies to (e.g., 2023-01-01 for Jan 2023)")
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_date = models.DateField(null=True, blank=True)
    payment_mode = models.CharField(max_length=50, choices=[('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'), ('cheque', 'Cheque')], default='cash')
    remarks = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_contributions')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.member.full_name} - {self.contribution_month.strftime('%b %Y')}"
