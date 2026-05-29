from django.db import transaction
from decimal import Decimal
from datetime import date
from .models import Contribution, ContributionPlan
from core.models import Member, User
from ledger.services import LedgerEngine

class ContributionService:
    @staticmethod
    @transaction.atomic
    def record_contribution(
        member: Member,
        plan: ContributionPlan,
        contribution_month: date,
        paid_amount: Decimal,
        penalty_amount: Decimal = Decimal('0.00'),
        payment_mode: str = 'cash',
        payment_date: date = None,
        remarks: str = "",
        created_by: User = None
    ) -> Contribution:
        
        payment_date = payment_date or date.today()
        
        # Determine expected amount based on plan
        expected_amount = plan.monthly_amount
        
        # Create the Contribution Record
        contribution = Contribution.objects.create(
            member=member,
            contribution_plan=plan,
            contribution_month=contribution_month,
            expected_amount=expected_amount,
            paid_amount=paid_amount,
            penalty_amount=penalty_amount,
            payment_date=payment_date,
            payment_mode=payment_mode,
            remarks=remarks,
            created_by=created_by
        )
        
        asset_category = 'Bank Balance' if payment_mode in ['bank_transfer', 'cheque'] else 'Cash in Hand'

        # Ledger Entry for Contribution (Principal)
        if paid_amount > 0:
            LedgerEngine.record_double_entry(
                organization=member.organization,
                transaction_date=payment_date,
                debit_category=asset_category,
                credit_category='Member Contributions',
                amount=paid_amount,
                reference_object=contribution,
                remarks=f"Contribution for {contribution_month.strftime('%b %Y')}",
                created_by=created_by
            )
            
        # Ledger Entry for Penalty
        if penalty_amount > 0:
            LedgerEngine.record_double_entry(
                organization=member.organization,
                transaction_date=payment_date,
                debit_category=asset_category,
                credit_category='Penalty Income',
                amount=penalty_amount,
                reference_object=contribution,
                remarks=f"Penalty for {contribution_month.strftime('%b %Y')}",
                created_by=created_by
            )

        return contribution
