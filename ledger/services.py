from django.db import transaction
from django.db.models import Sum
from .models import LedgerEntry
from core.models import Organization, User
from django.contrib.contenttypes.models import ContentType
from datetime import date
from decimal import Decimal

class LedgerEngine:
    @staticmethod
    def _calculate_new_balance(organization: Organization, category: str, transaction_type: str, amount: Decimal) -> Decimal:
        """
        Calculate the new balance for a specific category.
        This simply aggregates all past entries for the category.
        """
        # Note: In a true accounting system, Asset/Expense increase with Debit, Liability/Income increase with Credit
        # For simplicity in the MVP balance derivation, we'll return the absolute balance for the category.
        
        # Categorization Logic:
        ASSET_EXPENSE = ['Bank Balance', 'Cash in Hand', 'Loans Receivable', 'Administrative Expenses', 'Meeting Expenses']
        LIABILITY_INCOME = ['Member Contributions', 'Share Capital', 'Deposits', 'Interest Income', 'Penalty Income']

        aggregated = LedgerEntry.objects.filter(organization=organization, category=category).aggregate(
            total_debit=Sum('debit_amount'),
            total_credit=Sum('credit_amount')
        )
        
        total_debit = aggregated['total_debit'] or Decimal('0.00')
        total_credit = aggregated['total_credit'] or Decimal('0.00')

        if category in ASSET_EXPENSE:
            current_balance = total_debit - total_credit
        else:
            current_balance = total_credit - total_debit
            
        if transaction_type == 'debit':
            return current_balance + amount if category in ASSET_EXPENSE else current_balance - amount
        else:
            return current_balance - amount if category in ASSET_EXPENSE else current_balance + amount

    @staticmethod
    @transaction.atomic
    def create_entry(
        organization: Organization,
        transaction_date: date,
        transaction_type: str,
        category: str,
        amount: Decimal,
        reference_object=None,
        remarks: str = "",
        created_by: User = None
    ) -> LedgerEntry:
        """
        Core method to create a single ledger entry.
        """
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        
        if transaction_type not in ['debit', 'credit']:
            raise ValueError("Transaction type must be 'debit' or 'credit'.")

        new_balance = LedgerEngine._calculate_new_balance(organization, category, transaction_type, amount)

        entry = LedgerEntry(
            organization=organization,
            transaction_date=transaction_date,
            transaction_type=transaction_type,
            category=category,
            debit_amount=amount if transaction_type == 'debit' else Decimal('0.00'),
            credit_amount=amount if transaction_type == 'credit' else Decimal('0.00'),
            balance_after_transaction=new_balance,
            remarks=remarks,
            created_by=created_by
        )
        
        if reference_object:
            entry.reference_type = ContentType.objects.get_for_model(reference_object)
            entry.reference_id = reference_object.id
            
        entry.save()
        return entry

    @staticmethod
    @transaction.atomic
    def record_double_entry(
        organization: Organization,
        transaction_date: date,
        debit_category: str,
        credit_category: str,
        amount: Decimal,
        reference_object=None,
        remarks: str = "",
        created_by: User = None
    ):
        """
        Creates a balanced double-entry (one debit, one credit).
        """
        debit_entry = LedgerEngine.create_entry(
            organization=organization,
            transaction_date=transaction_date,
            transaction_type='debit',
            category=debit_category,
            amount=amount,
            reference_object=reference_object,
            remarks=remarks,
            created_by=created_by
        )

        credit_entry = LedgerEngine.create_entry(
            organization=organization,
            transaction_date=transaction_date,
            transaction_type='credit',
            category=credit_category,
            amount=amount,
            reference_object=reference_object,
            remarks=remarks,
            created_by=created_by
        )

        return debit_entry, credit_entry
