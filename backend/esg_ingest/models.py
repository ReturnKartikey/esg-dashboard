import uuid
from django.db import models
from django.contrib.auth.models import User

class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    hq_country = models.CharField(max_length=2, default='US', help_text="ISO 2-letter country code")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('ANALYST', 'Analyst'),
        ('AUDITOR', 'Auditor'),
        ('ADMIN', 'Admin'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='users')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='ANALYST')

    def __str__(self):
        return f"{self.user.username} ({self.role}) - {self.tenant.name}"

class Facility(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='facilities')
    name = models.CharField(max_length=255)
    plant_code = models.CharField(max_length=50, help_text="SAP Plant Code (WERKS)")
    country = models.CharField(max_length=2, help_text="ISO 2-letter country code")
    region = models.CharField(max_length=50, help_text="State/Province or Grid Subregion")

    class Meta:
        unique_together = ('tenant', 'plant_code')
        verbose_name_plural = "Facilities"

    def __str__(self):
        return f"{self.name} ({self.plant_code}) - {self.tenant.name}"

class UtilityAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='utility_accounts')
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='utility_accounts')
    account_number = models.CharField(max_length=100)
    meter_number = models.CharField(max_length=100)
    provider_name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('tenant', 'meter_number')

    def __str__(self):
        return f"Meter {self.meter_number} ({self.provider_name}) - {self.facility.name}"

class Airport(models.Model):
    iata_code = models.CharField(max_length=3, primary_key=True, help_text="IATA 3-letter code")
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=2)
    latitude = models.DecimalField(max_digits=12, decimal_places=9)
    longitude = models.DecimalField(max_digits=12, decimal_places=9)

    def __str__(self):
        return f"{self.iata_code} - {self.name}"

class EmissionFactor(models.Model):
    CATEGORY_CHOICES = [
        ('FUEL', 'Fuel Combustion'),
        ('ELECTRICITY', 'Purchased Electricity'),
        ('FLIGHT', 'Business Travel - Flights'),
        ('HOTEL', 'Business Travel - Hotel Stays'),
        ('GROUND_TRANSPORT', 'Business Travel - Ground Transport'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.IntegerField(choices=[(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')])
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    activity_type = models.CharField(max_length=100, help_text="e.g. DIESEL, LPG, GRID_ELECTRICITY, FLIGHT_SHORT_HAUL, HOTEL_NIGHT")
    region = models.CharField(max_length=50, default='GLOBAL', help_text="e.g. US-CA, DE, GB, GLOBAL")
    factor = models.DecimalField(max_digits=15, decimal_places=6, help_text="kg CO2e per unit")
    unit = models.CharField(max_length=20, help_text="Standard unit e.g. L, kWh, pkm, room_night")
    source_citation = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.get_category_display()} - {self.activity_type} ({self.region}): {self.factor} kg CO2e/{self.unit}"

class IngestionJob(models.Model):
    SOURCE_CHOICES = [
        ('SAP_FUEL_PROCUREMENT', 'SAP Fuel & Procurement'),
        ('UTILITY_PORTAL_CSV', 'Utility Portal CSV'),
        ('CONCUR_TRAVEL', 'Concur/Navan Travel Export'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='ingestion_jobs')
    source_type = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    file_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    error_summary = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_source_type_display()} ({self.status}) - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"

class RawRecord(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'Successfully Normalized'),
        ('FAILED', 'Failed Parsing/Validation'),
        ('SKIPPED', 'Skipped (Non-Emissions)'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='raw_records')
    row_index = models.IntegerField(help_text="Row index in original file")
    raw_data = models.JSONField(help_text="Original raw record as JSON")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUCCESS')
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Job {self.job.id} Row {self.row_index} [{self.status}]"

class NormalizedRecord(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Analyst Sign-off'),
        ('APPROVED', 'Approved & Locked'),
        ('REJECTED', 'Rejected'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='normalized_records')
    raw_record = models.OneToOneField(RawRecord, on_delete=models.CASCADE, related_name='normalized_record')
    facility = models.ForeignKey(Facility, on_delete=models.SET_NULL, null=True, blank=True)
    scope = models.IntegerField(choices=[(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')])
    category = models.CharField(max_length=50) # e.g. FUEL, ELECTRICITY, FLIGHT, HOTEL
    activity_type = models.CharField(max_length=100) # e.g. DIESEL, GRID_ELECTRICITY, etc.
    start_date = models.DateField()
    end_date = models.DateField()
    raw_quantity = models.DecimalField(max_digits=15, decimal_places=4)
    raw_unit = models.CharField(max_length=20)
    normalized_quantity = models.DecimalField(max_digits=15, decimal_places=4)
    normalized_unit = models.CharField(max_length=20)
    carbon_emissions_mtco2e = models.DecimalField(max_digits=15, decimal_places=6)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    is_edited = models.BooleanField(default=False)
    rejection_reason = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_records')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.category} ({self.activity_type}): {self.carbon_emissions_mtco2e} MT CO2e - {self.status}"

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated/Edited'),
        ('APPROVE', 'Approved'),
        ('REJECT', 'Rejected'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='audit_logs')
    normalized_record = models.ForeignKey(NormalizedRecord, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    field_name = models.CharField(max_length=50, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    changed_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.action} on Record {self.normalized_record_id} by {self.changed_by.user.username if self.changed_by else 'System'}"
