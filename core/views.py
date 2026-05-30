from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse, Http404
from decimal import Decimal
from datetime import date, datetime
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.core.paginator import Paginator

from .models import Organization, User, Member, Meeting
from contributions.models import ContributionPlan, Contribution
from contributions.services import ContributionService
from loans.models import Loan, LoanRepayment
from loans.services import LoanService
from ledger.models import LedgerEntry
from reports.services import PDFExportSystem

# Helper function to check if user has access to create/edit financial records
def can_manage_finance(user):
    return user.role in [User.Role.SUPER_ADMIN, User.Role.ORG_ADMIN, User.Role.TREASURER]

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        login_type = request.POST.get('login_type')
        
        if login_type == 'password':
            username = request.POST.get('username')
            password = request.POST.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                if user.status == 'active':
                    login(request, user)
                    return redirect('dashboard')
                else:
                    messages.error(request, "Your account is currently inactive.")
            else:
                messages.error(request, "Invalid username or password.")
                
        elif login_type == 'otp':
            email = request.POST.get('email')
            try:
                user = User.objects.get(email=email)
                if user.status != 'active':
                    messages.error(request, "Your account is currently inactive.")
                    return render(request, 'core/login.html')
                
                # Generate and send OTP
                otp = user.generate_otp()
                subject = f"Your LedgerFund Login OTP: {otp}"
                message = f"Hello {user.first_name or user.username},\n\nYour one-time password for LedgerFund is: {otp}\n\nThis code expires in 10 minutes."
                
                try:
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
                    request.session['otp_user_id'] = user.id
                    messages.success(request, f"A 6-digit OTP has been sent to {user.email}")
                    return redirect('verify_otp')
                except Exception as e:
                    messages.error(request, f"Error sending email: {e}")
            except User.DoesNotExist:
                messages.error(request, "No account found with this email.")
            
    return render(request, 'core/login.html')


def verify_otp_view(request):
    user_id = request.session.get('otp_user_id')
    if not user_id:
        return redirect('login')
        
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code')
        if user.verify_otp(otp_code):
            login(request, user)
            del request.session['otp_user_id']
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid or expired OTP.")
            
    return render(request, 'core/verify_otp.html', {'email': user.email})

@login_required
def profile_edit_view(request):
    user = request.user
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        profile_photo = request.POST.get('profile_photo')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        try:
            if email:
                user.email = email
            if password:
                user.set_password(password)
            if profile_photo:
                user.profile_photo = profile_photo
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
                
            user.save()
            if password: # Log back in if password changed
                login(request, user)
                
            messages.success(request, "Profile updated successfully!")
            return redirect('dashboard')
        except Exception as e:
            messages.error(request, f"Error updating profile: {e}")
            
    return render(request, 'core/profile_edit.html', {'u': user})


def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard_view(request):
    user = request.user
    org = user.organization
    
    if not org:
        # Fallback for Super Admin without organization
        org = Organization.objects.first()
        if not org:
            org = Organization.objects.create(organization_name="Default Organization")
            user.organization = org
            user.save()
            
    # Derive all financial numbers strictly from the Ledger
    # Total Assets = Cash in Hand + Bank Balance + Loans Receivable
    cash_bal = LedgerEntry.objects.filter(organization=org, category='Cash in Hand').aggregate(
        total=Sum('debit_amount') - Sum('credit_amount')
    )['total'] or Decimal('0.00')
    
    bank_bal = LedgerEntry.objects.filter(organization=org, category='Bank Balance').aggregate(
        total=Sum('debit_amount') - Sum('credit_amount')
    )['total'] or Decimal('0.00')

    loans_receivable = LedgerEntry.objects.filter(organization=org, category='Loans Receivable').aggregate(
        total=Sum('debit_amount') - Sum('credit_amount')
    )['total'] or Decimal('0.00')

    # Total Liabilities = Member Contributions + Share Capital + Deposits
    contributions_bal = LedgerEntry.objects.filter(organization=org, category='Member Contributions').aggregate(
        total=Sum('credit_amount') - Sum('debit_amount')
    )['total'] or Decimal('0.00')

    share_capital = LedgerEntry.objects.filter(organization=org, category='Share Capital').aggregate(
        total=Sum('credit_amount') - Sum('debit_amount')
    )['total'] or Decimal('0.00')

    # Total Income = Interest Income + Penalty Income
    interest_income = LedgerEntry.objects.filter(organization=org, category='Interest Income').aggregate(
        total=Sum('credit_amount') - Sum('debit_amount')
    )['total'] or Decimal('0.00')

    penalty_income = LedgerEntry.objects.filter(organization=org, category='Penalty Income').aggregate(
        total=Sum('credit_amount') - Sum('debit_amount')
    )['total'] or Decimal('0.00')
    
    total_assets = cash_bal + bank_bal + loans_receivable
    total_liabilities = contributions_bal + share_capital
    total_income = interest_income + penalty_income
    
    # Recent activity with pagination
    recent_transactions_list = LedgerEntry.objects.filter(organization=org).order_by('-transaction_date', '-id')
    paginator = Paginator(recent_transactions_list, 60)
    page_number = request.GET.get('page')
    recent_transactions = paginator.get_page(page_number)
    
    # Member context
    if user.role == User.Role.STANDARD:
        # Standard member can only see their own contributions & loans
        try:
            member = Member.objects.get(organization=org, member_code=user.username)
        except Member.DoesNotExist:
            member = None
            
        if member:
            my_contributions = Contribution.objects.filter(member=member).order_by('-payment_date')
            my_loans = Loan.objects.filter(member=member).order_by('-issued_date')
        else:
            my_contributions = []
            my_loans = []
            
        context = {
            'member': member,
            'my_contributions': my_contributions,
            'my_loans': my_loans,
            'total_assets': total_assets,
            'contributions_bal': contributions_bal,
        }
        return render(request, 'core/member_dashboard.html', context)

    # Admin/Treasurer dashboard
    members_count = Member.objects.filter(organization=org).count()
    active_loans_count = Loan.objects.filter(member__organization=org, loan_status='active').count()
    
    context = {
        'organization': org,
        'cash_bal': cash_bal,
        'bank_bal': bank_bal,
        'loans_receivable': loans_receivable,
        'total_assets': total_assets,
        'contributions_bal': contributions_bal,
        'share_capital': share_capital,
        'total_liabilities': total_liabilities,
        'interest_income': interest_income,
        'penalty_income': penalty_income,
        'total_income': total_income,
        'recent_transactions': recent_transactions,
        'members_count': members_count,
        'active_loans_count': active_loans_count,
        'can_manage': can_manage_finance(user),
    }
    return render(request, 'core/admin_dashboard.html', context)

@login_required
def member_list_view(request):
    if request.user.role == User.Role.STANDARD:
        raise Http404("You do not have permission to view members.")
        
    members = Member.objects.filter(organization=request.user.organization)
    return render(request, 'core/member_list.html', {'members': members})

@login_required
def create_member_view(request):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        member_code = request.POST.get('member_code')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        address = request.POST.get('address')
        aadhaar_number = request.POST.get('aadhaar_number')
        photo_url = request.POST.get('photo_url')
        join_date_str = request.POST.get('join_date')
        nominee_name = request.POST.get('nominee_name')

        
        try:
            join_date = datetime.strptime(join_date_str, '%Y-%m-%d').date()
            
            create_params = {
                'organization': request.user.organization,
                'member_code': member_code,
                'full_name': full_name,
                'join_date': join_date,
                'share_count': 1,
                'nominee_name': nominee_name,
                'notes': ''
            }
            if phone_number: create_params['phone_number'] = phone_number
            if email: create_params['email'] = email
            if address: create_params['address'] = address
            if aadhaar_number: create_params['aadhaar_number'] = aadhaar_number
            if photo_url: create_params['photo_url'] = photo_url

            member = Member.objects.create(**create_params)
            # Create a corresponding user account for the member if requested
            create_user = request.POST.get('create_user') == 'on'
            if create_user and email:
                User.objects.create_user(
                    username=member_code,
                    email=email.lower(), # Use the Gmail provided
                    password=member_code, # Optional, OTP will be primary
                    organization=request.user.organization,
                    role=User.Role.STANDARD,
                    first_name=full_name.split()[0] if full_name else "",
                    last_name=full_name.split()[-1] if len(full_name.split()) > 1 else "",
                    profile_photo=photo_url or "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&q=80&w=120"
                )

            
            messages.success(request, f"Member {full_name} created successfully!")
            return redirect('member_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")
            
    return render(request, 'core/create_member.html')

@login_required
def edit_member_view(request, member_id):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    org = request.user.organization
    member = get_object_or_404(Member, id=member_id, organization=org)
    
    if request.method == 'POST':
        member_code = request.POST.get('member_code')
        full_name = request.POST.get('full_name')
        phone_number = request.POST.get('phone_number')
        address = request.POST.get('address')
        aadhaar_number = request.POST.get('aadhaar_number')
        photo_url = request.POST.get('photo_url')
        join_date_str = request.POST.get('join_date')
        nominee_name = request.POST.get('nominee_name')
        
        try:
            join_date = datetime.strptime(join_date_str, '%Y-%m-%d').date()
            
            member.member_code = member_code
            member.full_name = full_name
            member.email = request.POST.get('email')
            member.phone_number = phone_number

            member.address = address
            member.aadhaar_number = aadhaar_number
            if photo_url:
                member.photo_url = photo_url
            member.join_date = join_date
            member.nominee_name = nominee_name
            member.save()
            
            messages.success(request, f"Member {full_name} updated successfully!")
            return redirect('member_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")
            
    return render(request, 'core/edit_member.html', {'member': member})


@login_required
def contribution_list_view(request):
    org = request.user.organization
    if request.user.role == User.Role.STANDARD:
        contributions = Contribution.objects.filter(member__organization=org, member__member_code=request.user.username)
    else:
        contributions = Contribution.objects.filter(member__organization=org).order_by('-payment_date')
    return render(request, 'core/contribution_list.html', {'contributions': contributions})

@login_required
def record_contribution_view(request):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    org = request.user.organization
    members = Member.objects.filter(organization=org, status='active')
    plans = ContributionPlan.objects.filter(organization=org, active_status=True)
    
    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        plan_id = request.POST.get('plan_id')
        month_str = request.POST.get('month') # expected YYYY-MM
        paid_amount = Decimal(request.POST.get('paid_amount', '0.00'))
        penalty_amount = Decimal(request.POST.get('penalty_amount', '0.00'))
        payment_mode = request.POST.get('payment_mode', 'cash')
        payment_date_str = request.POST.get('payment_date')
        remarks = request.POST.get('remarks')
        
        try:
            member = Member.objects.get(id=member_id, organization=org)
            plan = ContributionPlan.objects.get(id=plan_id, organization=org)
            contribution_month = datetime.strptime(month_str + "-01", '%Y-%m-%d').date()
            payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
            
            ContributionService.record_contribution(
                member=member,
                plan=plan,
                contribution_month=contribution_month,
                paid_amount=paid_amount,
                penalty_amount=penalty_amount,
                payment_mode=payment_mode,
                payment_date=payment_date,
                remarks=remarks,
                created_by=request.user
            )
            messages.success(request, "Contribution recorded successfully!")
            return redirect('contribution_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")
            
    return render(request, 'core/record_contribution.html', {'members': members, 'plans': plans})

@login_required
def loan_list_view(request):
    org = request.user.organization
    if request.user.role == User.Role.STANDARD:
        loans = Loan.objects.filter(member__organization=org, member__member_code=request.user.username)
    else:
        loans = Loan.objects.filter(member__organization=org).order_by('-issued_date')
    return render(request, 'core/loan_list.html', {'loans': loans})

@login_required
def issue_loan_view(request):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    org = request.user.organization
    members = Member.objects.filter(organization=org, status='active')
    
    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        principal_amount = Decimal(request.POST.get('principal_amount'))
        interest_rate = Decimal(request.POST.get('interest_rate'))
        issued_date_str = request.POST.get('issued_date')
        due_date_str = request.POST.get('due_date')
        payment_mode = request.POST.get('payment_mode', 'bank_transfer')
        remarks = request.POST.get('remarks')
        
        try:
            member = Member.objects.get(id=member_id, organization=org)
            issued_date = datetime.strptime(issued_date_str, '%Y-%m-%d').date()
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            
            LoanService.issue_loan(
                member=member,
                principal_amount=principal_amount,
                interest_rate=interest_rate,
                issued_date=issued_date,
                due_date=due_date,
                payment_mode=payment_mode,
                remarks=remarks,
                created_by=request.user
            )
            messages.success(request, "Loan issued and ledger updated successfully!")
            return redirect('loan_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")
            
    return render(request, 'core/issue_loan.html', {'members': members})

@login_required
def request_loan_view(request):
    org = request.user.organization
    try:
        member = Member.objects.get(organization=org, member_code=request.user.username)
    except Member.DoesNotExist:
        messages.error(request, "Your profile is not linked to a member registry record.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        principal_amount = Decimal(request.POST.get('principal_amount'))
        reason = request.POST.get('reason')
        
        try:
            # Create a pending loan request
            Loan.objects.create(
                member=member,
                principal_amount=principal_amount,
                outstanding_amount=principal_amount,
                loan_status='pending',
                reason=reason,
                created_by=request.user
            )
            messages.success(request, "Loan request submitted successfully and sent to committee for review!")
            return redirect('loan_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")
            
    return render(request, 'core/request_loan.html', {'member': member})

@login_required
def approve_loan_view(request, loan_id):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    org = request.user.organization
    loan = get_object_or_404(Loan, id=loan_id, member__organization=org, loan_status='pending')
    
    if request.method == 'POST':
        action = request.POST.get('action') # 'approve' or 'reject'
        comments = request.POST.get('comments')
        
        if action == 'approve':
            interest_rate = Decimal(request.POST.get('interest_rate', '12.00'))
            issued_date_str = request.POST.get('issued_date')
            due_date_str = request.POST.get('due_date')
            payment_mode = request.POST.get('payment_mode', 'bank_transfer')
            
            try:
                issued_date = datetime.strptime(issued_date_str, '%Y-%m-%d').date()
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                
                LoanService.approve_loan(
                    loan=loan,
                    interest_rate=interest_rate,
                    issued_date=issued_date,
                    due_date=due_date,
                    payment_mode=payment_mode,
                    remarks=comments,
                    created_by=request.user
                )
                messages.success(request, f"Loan Request #{loan.id} approved successfully and funds issued!")
                return redirect('loan_list')
            except Exception as e:
                messages.error(request, f"Error: {e}")
        elif action == 'reject':
            try:
                loan.loan_status = 'rejected'
                loan.approval_comments = comments
                loan.save()
                messages.success(request, f"Loan Request #{loan.id} has been rejected.")
                return redirect('loan_list')
            except Exception as e:
                messages.error(request, f"Error: {e}")
                
    return render(request, 'core/approve_loan.html', {'loan': loan})

@login_required
def record_repayment_view(request, loan_id):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    org = request.user.organization
    loan = get_object_or_404(Loan, id=loan_id, member__organization=org)
    
    if request.method == 'POST':
        principal_paid = Decimal(request.POST.get('principal_paid', '0.00'))
        interest_paid = Decimal(request.POST.get('interest_paid', '0.00'))
        penalty_paid = Decimal(request.POST.get('penalty_paid', '0.00'))
        payment_mode = request.POST.get('payment_mode', 'cash')
        payment_date_str = request.POST.get('payment_date')
        remarks = request.POST.get('remarks')
        
        try:
            payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
            LoanService.record_repayment(
                loan=loan,
                payment_date=payment_date,
                principal_paid=principal_paid,
                interest_paid=interest_paid,
                penalty_paid=penalty_paid,
                payment_mode=payment_mode,
                remarks=remarks,
                created_by=request.user
            )
            messages.success(request, "Repayment successfully recorded!")
            return redirect('loan_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")
            
    return render(request, 'core/record_repayment.html', {'loan': loan})

@login_required
def close_loan_view(request, loan_id):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    org = request.user.organization
    loan = get_object_or_404(Loan, id=loan_id, member__organization=org)
    
    if request.method == 'POST':
        try:
            loan.loan_status = 'closed'
            loan.save()
            messages.success(request, f"Loan #{loan.id} has been manually closed.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            
    return redirect('loan_list')

@login_required
def reports_view(request):
    org = request.user.organization
    entries_list = LedgerEntry.objects.filter(organization=org).order_by('-transaction_date', '-id')
    
    paginator = Paginator(entries_list, 60)
    page_number = request.GET.get('page')
    entries = paginator.get_page(page_number)
    
    return render(request, 'core/reports.html', {'entries': entries})

@login_required
def download_general_ledger_pdf(request):
    org = request.user.organization
    pdf_data = PDFExportSystem.export_general_ledger_pdf(
        organization=org,
        generated_by=request.user
    )
    response = HttpResponse(pdf_data, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="general_ledger_{org.organization_name.replace(" ", "_")}.pdf"'
    return response

@login_required
def meeting_list_view(request):
    org = request.user.organization
    meetings = Meeting.objects.filter(organization=org).order_by('-meeting_date', '-id')
    return render(request, 'core/meeting_list.html', {'meetings': meetings})

@login_required
def create_meeting_view(request):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        title = request.POST.get('title')
        meeting_date_str = request.POST.get('meeting_date')
        notes = request.POST.get('notes')
        attachment = request.FILES.get('attachment')
        
        try:
            meeting_date = datetime.strptime(meeting_date_str, '%Y-%m-%d').date()
            Meeting.objects.create(
                organization=request.user.organization,
                title=title,
                meeting_date=meeting_date,
                notes=notes,
                attachment=attachment,
                created_by=request.user
            )
            messages.success(request, f"Meeting '{title}' recorded successfully!")
            return redirect('meeting_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")
            
    return render(request, 'core/create_meeting.html')


@login_required
def delete_member_view(request, member_id):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    org = request.user.organization
    member = get_object_or_404(Member, id=member_id, organization=org)
    
    if request.method == 'POST':
        full_name = member.full_name
        member_code = member.member_code
        
        # Delete corresponding user login account if it exists
        try:
            user = User.objects.get(username=member_code, organization=org)
            user.delete()
        except User.DoesNotExist:
            pass
            
        member.delete()
        messages.success(request, f"Member {full_name} and their account deleted successfully!")
        
    return redirect('member_list')


@login_required
def edit_meeting_view(request, meeting_id):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    org = request.user.organization
    meeting = get_object_or_404(Meeting, id=meeting_id, organization=org)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        meeting_date_str = request.POST.get('meeting_date')
        notes = request.POST.get('notes')
        attachment = request.FILES.get('attachment')
        
        try:
            meeting_date = datetime.strptime(meeting_date_str, '%Y-%m-%d').date()
            meeting.title = title
            meeting.meeting_date = meeting_date
            meeting.notes = notes
            if attachment:
                meeting.attachment = attachment
            meeting.save()
            
            messages.success(request, f"Meeting '{title}' updated successfully!")
            return redirect('meeting_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")
            
    return render(request, 'core/edit_meeting.html', {'meeting': meeting})


@login_required
def delete_meeting_view(request, meeting_id):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')
        
    org = request.user.organization
    meeting = get_object_or_404(Meeting, id=meeting_id, organization=org)
    
    if request.method == 'POST':
        title = meeting.title
        meeting.delete()
        messages.success(request, f"Meeting '{title}' deleted successfully!")
        
    return redirect('meeting_list')


@login_required
def edit_contribution_view(request, contrib_id):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')

    org = request.user.organization
    contrib = get_object_or_404(Contribution, id=contrib_id, member__organization=org)

    if request.method == 'POST':
        month_str = request.POST.get('month')
        payment_date_str = request.POST.get('payment_date')
        paid_amount = Decimal(request.POST.get('paid_amount', '0.00'))
        penalty_amount = Decimal(request.POST.get('penalty_amount', '0.00'))
        payment_mode = request.POST.get('payment_mode', 'cash')
        remarks = request.POST.get('remarks')

        try:
            contrib.contribution_month = datetime.strptime(month_str + "-01", '%Y-%m-%d').date()
            contrib.payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
            contrib.paid_amount = paid_amount
            contrib.penalty_amount = penalty_amount
            contrib.payment_mode = payment_mode
            contrib.remarks = remarks
            contrib.save()

            messages.success(request, f"Contribution for {contrib.member.full_name} updated successfully!")
            return redirect('contribution_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'core/edit_contribution.html', {'contrib': contrib})


@login_required
def delete_contribution_view(request, contrib_id):
    if not can_manage_finance(request.user):
        messages.error(request, "Permission Denied.")
        return redirect('dashboard')

    org = request.user.organization
    contrib = get_object_or_404(Contribution, id=contrib_id, member__organization=org)

    if request.method == 'POST':
        member_name = contrib.member.full_name
        month_label = contrib.contribution_month.strftime('%b %Y')
        contrib.delete()
        messages.success(request, f"Contribution record for {member_name} ({month_label}) deleted successfully!")

    return redirect('contribution_list')
