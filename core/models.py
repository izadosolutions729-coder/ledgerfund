from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import random
import datetime


class Organization(models.Model):
    organization_name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.organization_name


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', _('Super Admin')
        ORG_ADMIN = 'org_admin', _('Organization Admin')
        TREASURER = 'treasurer', _('Treasurer')
        AUDITOR = 'auditor', _('Auditor')
        COMMITTEE = 'committee', _('Committee Member')
        STANDARD = 'standard', _('Standard Member')

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='users')
    mobile_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STANDARD)
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active')
    
    # OTP and Profile Fields
    profile_photo = models.URLField(max_length=500, null=True, blank=True, default="https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&q=80&w=120")
    otp_code = models.CharField(max_length=6, null=True, blank=True)
    otp_expiry = models.DateTimeField(null=True, blank=True)

    def generate_otp(self):
        self.otp_code = str(random.randint(100000, 999999))
        self.otp_expiry = timezone.now() + datetime.timedelta(minutes=10)
        self.save()
        return self.otp_code

    def verify_otp(self, code):
        if self.otp_code == code and self.otp_expiry > timezone.now():
            self.otp_code = None  # Use once
            self.save()
            return True
        return False


    def __str__(self):
        return self.username


class Member(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='members')
    member_code = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    address = models.TextField(null=True, blank=True)
    aadhaar_number = models.CharField(max_length=20, null=True, blank=True, help_text="Aadhaar or National ID")
    photo_url = models.CharField(max_length=500, null=True, blank=True, default="https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&q=80&w=120", help_text="Link to profile photo")
    join_date = models.DateField()
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('inactive', 'Inactive'), ('suspended', 'Suspended')], default='active')
    share_count = models.PositiveIntegerField(default=1)
    nominee_name = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.member_code} - {self.full_name}"


class Meeting(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='meetings')
    meeting_date = models.DateField()
    title = models.CharField(max_length=255)
    notes = models.TextField(null=True, blank=True)
    attachment = models.FileField(upload_to='meetings/', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_meetings')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} on {self.meeting_date}"
