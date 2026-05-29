from django.db import transaction
from decimal import Decimal
from datetime import date
from .models import Loan, LoanRepayment
from core.models import Member, User
from ledger.services import LedgerEngine

class LoanService:
    @staticmethod
    @transaction.atomic
    def issue_loan(
        member: Member,
        principal_amount: Decimal,
        interest_rate: Decimal,
        issued_date: date,
        due_date: date,
        payment_mode: str = 'bank_transfer',
        remarks: str = "",
        created_by: User = None
    ) -> Loan:
        """
        Record an approved loan and generate ledger entries.
        """
        loan = Loan.objects.create(
            member=member,
            principal_amount=principal_amount,
            interest_rate=interest_rate,
            issued_date=issued_date,
            due_date=due_date,
            outstanding_amount=principal_amount,
            loan_status='active',
            remarks=remarks,
            created_by=created_by
        )
        
        asset_category = 'Bank Balance' if payment_mode in ['bank_transfer', 'cheque'] else 'Cash in Hand'

        # Money going out of Bank to Loans Receivable
        LedgerEngine.record_double_entry(
            organization=member.organization,
            transaction_date=issued_date,
            debit_category='Loans Receivable',
            credit_category=asset_category,
            amount=principal_amount,
            reference_object=loan,
            remarks=f"Loan Issued to {member.full_name}",
            created_by=created_by
        )
        
        return loan

    @staticmethod
    @transaction.atomic
    def record_repayment(
        loan: Loan,
        payment_date: date,
        principal_paid: Decimal = Decimal('0.00'),
        interest_paid: Decimal = Decimal('0.00'),
        penalty_paid: Decimal = Decimal('0.00'),
        payment_mode: str = 'cash',
        remarks: str = "",
        created_by: User = None
    ) -> LoanRepayment:
        """
        Record a repayment, update outstanding balance, and generate ledger entries.
        """
        repayment = LoanRepayment.objects.create(
            loan=loan,
            payment_date=payment_date,
            principal_paid=principal_paid,
            interest_paid=interest_paid,
            penalty_paid=penalty_paid,
            payment_mode=payment_mode,
            remarks=remarks,
            created_by=created_by
        )

        # Update Loan Outstanding
        loan.outstanding_amount -= principal_paid
        if loan.outstanding_amount <= 0:
            loan.outstanding_amount = Decimal('0.00')
            loan.loan_status = 'closed'
        loan.save()
        
        asset_category = 'Bank Balance' if payment_mode in ['bank_transfer', 'cheque'] else 'Cash in Hand'

        # Ledger Entry for Principal Repayment
        if principal_paid > 0:
            LedgerEngine.record_double_entry(
                organization=loan.member.organization,
                transaction_date=payment_date,
                debit_category=asset_category,
                credit_category='Loans Receivable',
                amount=principal_paid,
                reference_object=repayment,
                remarks=f"Loan Principal Repayment by {loan.member.full_name}",
                created_by=created_by
            )

        # Ledger Entry for Interest
        if interest_paid > 0:
            LedgerEngine.record_double_entry(
                organization=loan.member.organization,
                transaction_date=payment_date,
                debit_category=asset_category,
                credit_category='Interest Income',
                amount=interest_paid,
                reference_object=repayment,
                remarks=f"Loan Interest Repayment by {loan.member.full_name}",
                created_by=created_by
            )
            
        # Ledger Entry for Penalty
        if penalty_paid > 0:
            LedgerEngine.record_double_entry(
                organization=loan.member.organization,
                transaction_date=payment_date,
                debit_category=asset_category,
                credit_category='Penalty Income',
                amount=penalty_paid,
                reference_object=repayment,
                remarks=f"Loan Penalty Repayment by {loan.member.full_name}",
                created_by=created_by
            )

        return repayment

    @staticmethod
    @transaction.atomic
    def approve_loan(
        loan: Loan,
        interest_rate: Decimal,
        issued_date: date,
        due_date: date,
        payment_mode: str = 'bank_transfer',
        remarks: str = "",
        created_by: User = None
    ) -> Loan:
        """
        Approve a pending loan request and generate ledger entries.
        """
        loan.interest_rate = interest_rate
        loan.issued_date = issued_date
        loan.due_date = due_date
        loan.loan_status = 'active'
        loan.remarks = remarks
        loan.save()
        
        asset_category = 'Bank Balance' if payment_mode in ['bank_transfer', 'cheque'] else 'Cash in Hand'

        # Money going out of Bank to Loans Receivable
        LedgerEngine.record_double_entry(
            organization=loan.member.organization,
            transaction_date=issued_date,
            debit_category='Loans Receivable',
            credit_category=asset_category,
            amount=loan.principal_amount,
            reference_object=loan,
            remarks=f"Loan Approved & Issued to {loan.member.full_name}",
            created_by=created_by
        )
        return loan
