from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    
    path('members/', views.member_list_view, name='member_list'),
    path('members/create/', views.create_member_view, name='create_member'),
    path('members/<int:member_id>/edit/', views.edit_member_view, name='edit_member'),
    path('members/<int:member_id>/delete/', views.delete_member_view, name='delete_member'),
    
    path('contributions/', views.contribution_list_view, name='contribution_list'),
    path('contributions/record/', views.record_contribution_view, name='record_contribution'),
    path('contributions/<int:contrib_id>/edit/', views.edit_contribution_view, name='edit_contribution'),
    path('contributions/<int:contrib_id>/delete/', views.delete_contribution_view, name='delete_contribution'),
    
    path('loans/', views.loan_list_view, name='loan_list'),
    path('loans/issue/', views.issue_loan_view, name='issue_loan'),
    path('loans/request/', views.request_loan_view, name='request_loan'),
    path('loans/<int:loan_id>/approve/', views.approve_loan_view, name='approve_loan'),
    path('loans/<int:loan_id>/repay/', views.record_repayment_view, name='record_repayment'),
    
    path('reports/', views.reports_view, name='reports'),
    path('reports/general-ledger/pdf/', views.download_general_ledger_pdf, name='download_ledger_pdf'),
    
    path('meetings/', views.meeting_list_view, name='meeting_list'),
    path('meetings/create/', views.create_meeting_view, name='create_meeting'),
    path('meetings/<int:meeting_id>/edit/', views.edit_meeting_view, name='edit_meeting'),
    path('meetings/<int:meeting_id>/delete/', views.delete_meeting_view, name='delete_meeting'),
]
