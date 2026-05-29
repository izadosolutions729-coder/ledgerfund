from django.core.management.base import BaseCommand
from core.models import Organization, User, Member
from contributions.models import ContributionPlan
from contributions.services import ContributionService
from loans.models import Loan
from loans.services import LoanService
from ledger.models import LedgerEntry
from reports.services import PDFExportSystem
from decimal import Decimal
from datetime import date
from django.db.models import Sum

class Command(BaseCommand):
    help = 'Verify and validate financial workflows, ledger double-entry reconciliation, and PDF generation'

    def handle(self, *args, **options):
        self.stdout.write("--- Starting Financial Verification ---")
        
        # 1. Setup Organization and Admin User
        org, _ = Organization.objects.get_or_create(
            organization_name="Enterprise Community Fund",
            registration_number="ECF-2026-999"
        )
        
        admin_user, created = User.objects.get_or_create(
            username="treasurer_bob",
            email="bob@fund.org",
            defaults={
                "first_name": "Bob",
                "last_name": "Treasurer",
                "role": User.Role.TREASURER,
                "organization": org
            }
        )
        if created:
            admin_user.set_password("bobpassword123")
            admin_user.save()
            
        # 2. Setup Member
        member, _ = Member.objects.get_or_create(
            member_code="MEM-001",
            defaults={
                "organization": org,
                "full_name": "John Doe",
                "join_date": date(2026, 1, 1),
                "share_count": 5,
                "status": "active"
            }
        )
        
        # 3. Setup Contribution Plan
        plan, _ = ContributionPlan.objects.get_or_create(
            organization=org,
            plan_name="Standard Plan",
            defaults={
                "monthly_amount": Decimal("100.00"),
                "active_status": True
            }
        )
        
        # Reset existing ledger entries to run a clean dry-run verification
        LedgerEntry.objects.filter(organization=org).delete()
        
        # Seed cash in hand for the organization to be able to issue loans
        # Debit: Cash in Hand $5000 (Asset increased)
        # Credit: Share Capital $5000 (Liability/Equity increased)
        from ledger.services import LedgerEngine
        LedgerEngine.record_double_entry(
            organization=org,
            transaction_date=date(2026, 5, 1),
            debit_category="Cash in Hand",
            credit_category="Share Capital",
            amount=Decimal("5000.00"),
            remarks="Initial capital seeding",
            created_by=admin_user
        )
        self.stdout.write("Seeded Initial Capital: $5000.00 Debit to Cash in Hand, $5000.00 Credit to Share Capital")

        # 4. Record Contribution
        self.stdout.write("\nRecording Contribution of $100.00...")
        contribution = ContributionService.record_contribution(
            member=member,
            plan=plan,
            contribution_month=date(2026, 5, 1),
            paid_amount=Decimal("100.00"),
            penalty_amount=Decimal("10.00"),
            payment_mode="cash",
            payment_date=date(2026, 5, 10),
            remarks="May 2026 contribution + penalty",
            created_by=admin_user
        )
        self.stdout.write(f"Recorded contribution ID: {contribution.id}")

        # 5. Issue a Loan of $1000.00
        self.stdout.write("\nIssuing Loan of $1000.00...")
        loan = LoanService.issue_loan(
            member=member,
            principal_amount=Decimal("1000.00"),
            interest_rate=Decimal("12.00"),  # 12% annual
            issued_date=date(2026, 5, 12),
            due_date=date(2027, 5, 12),
            payment_mode="cash",
            remarks="Approved medical support loan",
            created_by=admin_user
        )
        self.stdout.write(f"Issued Loan ID: {loan.id}. Outstanding: ${loan.outstanding_amount:.2f}")

        # 6. Record Loan Repayment
        self.stdout.write("\nRecording Repayment of $200.00 principal and $20.00 interest...")
        repayment = LoanService.record_repayment(
            loan=loan,
            payment_date=date(2026, 5, 20),
            principal_paid=Decimal("200.00"),
            interest_paid=Decimal("20.00"),
            penalty_paid=Decimal("0.00"),
            payment_mode="cash",
            remarks="First monthly installment",
            created_by=admin_user
        )
        # Refresh loan
        loan.refresh_from_db()
        self.stdout.write(f"Recorded Repayment. New Loan Outstanding: ${loan.outstanding_amount:.2f}")

        # 7. Print Ledger Ledger Entries to console to verify double-entry balancing
        self.stdout.write("\n--- LEDGER DOUBLE-ENTRY VERIFICATION ---")
        entries = LedgerEntry.objects.filter(organization=org).order_by('id')
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        
        self.stdout.write(f"{'Date':<12} | {'Category':<22} | {'Type':<8} | {'Debit':<10} | {'Credit':<10} | {'Balance':<10}")
        self.stdout.write("-" * 82)
        for entry in entries:
            self.stdout.write(
                f"{entry.transaction_date.strftime('%Y-%m-%d'):<12} | "
                f"{entry.category:<22} | "
                f"{entry.transaction_type:<8} | "
                f"{entry.debit_amount:<10.2f} | "
                f"{entry.credit_amount:<10.2f} | "
                f"{entry.balance_after_transaction:<10.2f}"
            )
            total_debit += entry.debit_amount
            total_credit += entry.credit_amount
            
        self.stdout.write("-" * 82)
        self.stdout.write(f"{'TOTALS':<12} | {'':<22} | {'':<8} | {total_debit:<10.2f} | {total_credit:<10.2f} |")
        
        # 8. Integrity Checks
        self.stdout.write("\n--- FINANCIAL INTEGRITY CHECKS ---")
        
        # Balance reconciliation
        if total_debit == total_credit:
            self.stdout.write(self.style.SUCCESS("[OK] SUCCESS: Double-Entry Ledger is perfectly balanced!"))
        else:
            self.stdout.write(self.style.ERROR(f"[FAIL] ERROR: Ledger is out of balance! Diff: {total_debit - total_credit}"))

        # Outstanding Loan reconciliation
        expected_outstanding = Decimal("800.00")
        if loan.outstanding_amount == expected_outstanding:
            self.stdout.write(self.style.SUCCESS(f"[OK] SUCCESS: Outstanding Loan amount is accurately derived (${loan.outstanding_amount:.2f})"))
        else:
            self.stdout.write(self.style.ERROR(f"[FAIL] ERROR: Expected outstanding ${expected_outstanding}, got ${loan.outstanding_amount}"))

        # Cash & Bank Balance derived calculation check
        # Seed cash in hand: +5000
        # Contribution cash: +100
        # Penalty cash: +10
        # Loan cash out: -1000
        # Repayment cash: +200 principal, +20 interest = +220
        # Final Cash in Hand should be: 5000 + 100 + 10 - 1000 + 220 = 4330
        cash_in_hand_entries = LedgerEntry.objects.filter(organization=org, category="Cash in Hand")
        derived_cash = Decimal("0.00")
        for ent in cash_in_hand_entries:
            derived_cash += ent.debit_amount - ent.credit_amount
        
        expected_cash = Decimal("4330.00")
        if derived_cash == expected_cash:
            self.stdout.write(self.style.SUCCESS(f"[OK] SUCCESS: Derived Cash in Hand ledger balance matches expectation (${derived_cash:.2f})"))
        else:
            self.stdout.write(self.style.ERROR(f"[FAIL] ERROR: Expected derived Cash in Hand balance ${expected_cash}, got ${derived_cash}"))

        # 9. Generate and save PDF report
        self.stdout.write("\nGenerating General Ledger PDF Report...")
        pdf_data = PDFExportSystem.export_general_ledger_pdf(
            organization=org,
            generated_by=admin_user
        )
        
        with open("general_ledger_verification_report.pdf", "wb") as f:
            f.write(pdf_data)
            
        self.stdout.write(self.style.SUCCESS("[OK] SUCCESS: PDF Report generated and saved to 'general_ledger_verification_report.pdf'"))
        self.stdout.write("--- Financial Verification Complete ---")
