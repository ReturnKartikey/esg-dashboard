from rest_framework import serializers
from .models import (
    Tenant, UserProfile, Facility, UtilityAccount, Airport,
    EmissionFactor, IngestionJob, RawRecord, NormalizedRecord, AuditLog
)
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'role', 'tenant', 'tenant_name']

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'hq_country', 'created_at']

class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = ['id', 'name', 'plant_code', 'country', 'region']

class UtilityAccountSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source='facility.name', read_only=True)
    
    class Meta:
        model = UtilityAccount
        fields = ['id', 'facility', 'facility_name', 'account_number', 'meter_number', 'provider_name']

class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = ['iata_code', 'name', 'city', 'country', 'latitude', 'longitude']

class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = ['id', 'scope', 'category', 'activity_type', 'region', 'factor', 'unit', 'source_citation']

class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ['id', 'row_index', 'raw_data', 'status', 'error_message']

class IngestionJobSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source='uploaded_by.user.username', read_only=True)
    
    class Meta:
        model = IngestionJob
        fields = ['id', 'source_type', 'file_name', 'status', 'error_summary', 'uploaded_by_username', 'uploaded_at']

class NormalizedRecordSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source='facility.name', read_only=True)
    raw_data = serializers.JSONField(source='raw_record.raw_data', read_only=True)
    raw_record_status = serializers.CharField(source='raw_record.status', read_only=True)
    raw_record_error = serializers.CharField(source='raw_record.error_message', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.user.username', read_only=True)
    
    class Meta:
        model = NormalizedRecord
        fields = [
            'id', 'raw_record', 'facility', 'facility_name', 'scope', 'category', 'activity_type',
            'start_date', 'end_date', 'raw_quantity', 'raw_unit', 'normalized_quantity',
            'normalized_unit', 'carbon_emissions_mtco2e', 'status', 'is_edited',
            'rejection_reason', 'reviewed_by_username', 'reviewed_at', 'raw_data',
            'raw_record_status', 'raw_record_error'
        ]
        read_only_fields = ['id', 'raw_record', 'scope', 'category', 'normalized_unit', 'carbon_emissions_mtco2e', 'reviewed_by_username', 'reviewed_at']

    def validate(self, data):
        # Prevent edits to approved records
        if self.instance and self.instance.status == 'APPROVED':
            raise serializers.ValidationError("Approved records are locked for audit and cannot be modified.")
        return data

class AuditLogSerializer(serializers.ModelSerializer):
    changed_by_username = serializers.SerializerMethodField()
    
    class Meta:
        model = AuditLog
        fields = ['id', 'normalized_record', 'action', 'field_name', 'old_value', 'new_value', 'changed_by_username', 'changed_at']

    def get_changed_by_username(self, obj):
        if obj.changed_by and obj.changed_by.user:
            return obj.changed_by.user.username
        return "System"
