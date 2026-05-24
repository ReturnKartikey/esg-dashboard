from rest_framework import viewsets, status, exceptions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, date
from django.db.models import Sum, Count

from .models import (
    Tenant, UserProfile, Facility, UtilityAccount, Airport,
    EmissionFactor, IngestionJob, RawRecord, NormalizedRecord, AuditLog
)
from .serializers import (
    TenantSerializer, UserProfileSerializer, FacilitySerializer,
    UtilityAccountSerializer, AirportSerializer, EmissionFactorSerializer,
    IngestionJobSerializer, RawRecordSerializer, NormalizedRecordSerializer,
    AuditLogSerializer
)
from .parsers import run_parser_on_csv

def get_tenant_from_request(request):
    """
    Looks up the mock user from the X-Mock-User header or mock_user query param.
    Extracts the user's profile and tenant. Defaults to 'acme_analyst' if not provided.
    """
    mock_username = request.headers.get('X-Mock-User') or request.query_params.get('mock_user')
    if not mock_username:
        # Default to acme_analyst for local development/testing convenience
        mock_username = 'acme_analyst'
        
    profile = UserProfile.objects.filter(user__username=mock_username).first()
    if not profile:
        raise exceptions.AuthenticationFailed(f"Mock user '{mock_username}' not found. Please log in or set X-Mock-User header.")
    return profile.tenant, profile

class TenantScopedViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet that automatically scopes querysets and creations to the request tenant.
    """
    def get_queryset(self):
        tenant, _ = get_tenant_from_request(self.request)
        return self.queryset.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant, _ = get_tenant_from_request(self.request)
        serializer.save(tenant=tenant)

class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    
    def list(self, request, *args, **kwargs):
        # Allow listing all profiles so the frontend can display a user switcher
        queryset = self.get_queryset()
        serializer = UserProfileSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='current')
    def current_user(self, request):
        tenant, profile = get_tenant_from_request(request)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

class FacilityViewSet(TenantScopedViewSet):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer

class UtilityAccountViewSet(TenantScopedViewSet):
    queryset = UtilityAccount.objects.all()
    serializer_class = UtilityAccountSerializer

class AirportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Airport.objects.all()
    serializer_class = AirportSerializer

class EmissionFactorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EmissionFactor.objects.all()
    serializer_class = EmissionFactorSerializer

class IngestionJobViewSet(TenantScopedViewSet):
    queryset = IngestionJob.objects.all()
    serializer_class = IngestionJobSerializer

    @action(detail=False, methods=['post'], url_path='upload')
    def upload_file(self, request):
        tenant, profile = get_tenant_from_request(request)
        source_type = request.data.get('source_type')
        uploaded_file = request.FILES.get('file')

        if not source_type or not uploaded_file:
            return Response(
                {"error": "Both 'source_type' and 'file' fields are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Basic verification of source type
        valid_sources = [choice[0] for choice in IngestionJob.SOURCE_CHOICES]
        if source_type not in valid_sources:
            return Response(
                {"error": f"Invalid source type. Must be one of: {valid_sources}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Read file contents
        try:
            file_content = uploaded_file.read().decode('utf-8-sig') # handles BOM
        except Exception as e:
            return Response(
                {"error": f"Failed to read file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create IngestionJob
        job = IngestionJob.objects.create(
            tenant=tenant,
            source_type=source_type,
            file_name=uploaded_file.name,
            uploaded_by=profile,
            status='PENDING'
        )

        # Parse CSV file synchronously (for prototype, simple & direct)
        success = run_parser_on_csv(job, file_content)

        if success:
            serializer = self.get_serializer(job)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(
                {"error": "File ingestion failed.", "job_status": job.status, "summary": job.error_summary},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class NormalizedRecordViewSet(TenantScopedViewSet):
    queryset = NormalizedRecord.objects.all()
    serializer_class = NormalizedRecordSerializer
    filterset_fields = ['scope', 'category', 'status', 'facility']

    def get_queryset(self):
        # Support filtering and search
        tenant, _ = get_tenant_from_request(self.request)
        qs = self.queryset.filter(tenant=tenant)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
            
        scope_filter = self.request.query_params.get('scope')
        if scope_filter:
            qs = qs.filter(scope=scope_filter)
            
        category_filter = self.request.query_params.get('category')
        if category_filter:
            qs = qs.filter(category=category_filter)
            
        facility_filter = self.request.query_params.get('facility')
        if facility_filter:
            qs = qs.filter(facility_id=facility_filter)
            
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(activity_type__icontains=search) | qs.filter(raw_unit__icontains=search)
            
        return qs.order_by('-start_date')

    def perform_update(self, serializer):
        """
        Custom update to recalculate carbon emissions when analyst modifies quantity or activity type.
        Logs change to AuditLog.
        """
        tenant, profile = get_tenant_from_request(self.request)
        record = self.get_object()
        
        # Check if record is approved
        if record.status == 'APPROVED':
            raise exceptions.ValidationError("Approved records are locked and cannot be edited.")

        # Capture old values
        old_qty = record.normalized_quantity
        old_activity = record.activity_type
        old_facility = record.facility

        # Save serializer data
        updated_record = serializer.save(is_edited=True)

        # Check what fields were modified
        qty_changed = updated_record.normalized_quantity != old_qty
        act_changed = updated_record.activity_type != old_activity
        fac_changed = updated_record.facility != old_facility

        if qty_changed or act_changed or fac_changed:
            # Recalculate carbon emissions
            # Look up corresponding emission factor
            factor_query = EmissionFactor.objects.filter(
                scope=updated_record.scope,
                category=updated_record.category,
                activity_type=updated_record.activity_type
            )
            
            # For Scope 2 electricity, prioritize region/country
            if updated_record.category == 'ELECTRICITY' and updated_record.facility:
                ef = factor_query.filter(region=updated_record.facility.region).first()
                if not ef:
                    ef = factor_query.filter(region=updated_record.facility.country).first()
            elif updated_record.category == 'HOTEL' and updated_record.raw_record:
                # Hotels might check country
                country = updated_record.raw_record.raw_data.get('Hotel Country', tenant.hq_country)
                ef = factor_query.filter(region=country).first()
                if not ef:
                    ef = factor_query.filter(region='GLOBAL').first()
            else:
                ef = factor_query.first()

            if ef:
                # Update quantity and calculate
                updated_record.normalized_quantity = updated_record.raw_quantity # Reset or map
                updated_record.carbon_emissions_mtco2e = (updated_record.normalized_quantity * ef.factor) / Decimal('1000.0')
                updated_record.save()
            else:
                raise exceptions.ValidationError(f"Could not find matching Emission Factor to recalculate emissions for '{updated_record.activity_type}'.")

            # Create Audit Logs for each change
            if qty_changed:
                AuditLog.objects.create(
                    tenant=tenant,
                    normalized_record=updated_record,
                    action='UPDATE',
                    field_name='normalized_quantity',
                    old_value=str(old_qty),
                    new_value=str(updated_record.normalized_quantity),
                    changed_by=profile
                )
            if act_changed:
                AuditLog.objects.create(
                    tenant=tenant,
                    normalized_record=updated_record,
                    action='UPDATE',
                    field_name='activity_type',
                    old_value=old_activity,
                    new_value=updated_record.activity_type,
                    changed_by=profile
                )
            if fac_changed:
                AuditLog.objects.create(
                    tenant=tenant,
                    normalized_record=updated_record,
                    action='UPDATE',
                    field_name='facility',
                    old_value=old_facility.name if old_facility else "None",
                    new_value=updated_record.facility.name if updated_record.facility else "None",
                    changed_by=profile
                )

    @action(detail=False, methods=['post'], url_path='bulk-action')
    def bulk_action(self, request):
        tenant, profile = get_tenant_from_request(request)
        action_type = request.data.get('action') # 'approve' or 'reject'
        record_ids = request.data.get('ids', [])
        rejection_reason = request.data.get('rejection_reason', '')

        if action_type not in ['approve', 'reject']:
            return Response(
                {"error": "Invalid action. Must be 'approve' or 'reject'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not record_ids:
            return Response(
                {"error": "List of 'ids' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        records = NormalizedRecord.objects.filter(tenant=tenant, id__in=record_ids)
        updated_count = 0

        with transaction.atomic():
            for record in records:
                # Prevent updates to already approved records (keeps audit trail immutable once approved)
                if record.status == 'APPROVED' and action_type == 'approve':
                    continue

                if action_type == 'approve':
                    record.status = 'APPROVED'
                    record.reviewed_by = profile
                    record.reviewed_at = timezone.now()
                    record.save()

                    AuditLog.objects.create(
                        tenant=tenant,
                        normalized_record=record,
                        action='APPROVE',
                        changed_by=profile,
                        new_value="Record signed off and locked for audit."
                    )
                elif action_type == 'reject':
                    record.status = 'REJECTED'
                    record.rejection_reason = rejection_reason
                    record.reviewed_by = profile
                    record.reviewed_at = timezone.now()
                    record.save()

                    AuditLog.objects.create(
                        tenant=tenant,
                        normalized_record=record,
                        action='REJECT',
                        field_name='status',
                        old_value='PENDING',
                        new_value=f"REJECTED. Reason: {rejection_reason}",
                        changed_by=profile
                    )
                updated_count += 1

        return Response(
            {"message": f"Successfully processed {updated_count} records.", "action": action_type},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='dashboard-stats')
    def dashboard_stats(self, request):
        """
        Returns high-level ESG metrics for the active tenant:
        - Total Carbon Emissions (Approved vs Pending vs Total)
        - Scope 1, 2, 3 approved emissions
        - Record Counts by Status
        - Monthly emissions timeline (prorated by calendar months!)
        """
        tenant, _ = get_tenant_from_request(request)
        records = NormalizedRecord.objects.filter(tenant=tenant)

        # Total emissions summary
        stats = records.values('status').annotate(total_co2=Sum('carbon_emissions_mtco2e'), count=Count('id'))
        
        total_approved = Decimal('0')
        total_pending = Decimal('0')
        total_rejected = Decimal('0')
        approved_count = 0
        pending_count = 0
        rejected_count = 0

        for s in stats:
            val = s['total_co2'] or Decimal('0')
            if s['status'] == 'APPROVED':
                total_approved = val
                approved_count = s['count']
            elif s['status'] == 'PENDING':
                total_pending = val
                pending_count = s['count']
            elif s['status'] == 'REJECTED':
                total_rejected = val
                rejected_count = s['count']

        # Scope Breakdown (for Approved records)
        scope_stats = records.filter(status='APPROVED').values('scope').annotate(total_co2=Sum('carbon_emissions_mtco2e'))
        scope_breakdown = {1: Decimal('0'), 2: Decimal('0'), 3: Decimal('0')}
        for s in scope_stats:
            scope_breakdown[s['scope']] = s['total_co2'] or Decimal('0')

        # Calendar month proration calculation
        # To display a timeline chart of emissions by month, we need to divide emissions across their dates.
        # Since this is a prototype, we can build a proration map for all APPROVED records.
        monthly_emissions = {}
        
        # Pull approved records to prorate
        approved_records = records.filter(status='APPROVED')
        for rec in approved_records:
            co2 = rec.carbon_emissions_mtco2e
            start = rec.start_date
            end = rec.end_date
            
            days = (end - start).days + 1
            if days <= 0:
                continue
                
            daily_co2 = co2 / Decimal(str(days))
            
            curr = start
            while curr <= end:
                m_key = curr.strftime('%Y-%m') # e.g. "2026-04"
                monthly_emissions[m_key] = monthly_emissions.get(m_key, Decimal('0')) + daily_co2
                curr = datetime.fromordinal(curr.toordinal() + 1).date()

        # Format timeline data sorted by month key
        timeline = []
        for m_key in sorted(monthly_emissions.keys()):
            timeline.append({
                "month": m_key,
                "emissions": round(float(monthly_emissions[m_key]), 4)
            })

        return Response({
            "total_emissions_mtco2e": round(float(total_approved), 2),
            "pending_emissions_mtco2e": round(float(total_pending), 2),
            "counts": {
                "approved": approved_count,
                "pending": pending_count,
                "rejected": rejected_count,
                "total": approved_count + pending_count + rejected_count
            },
            "scopes": {
                "scope_1": round(float(scope_breakdown[1]), 2),
                "scope_2": round(float(scope_breakdown[2]), 2),
                "scope_3": round(float(scope_breakdown[3]), 2),
            },
            "timeline": timeline
        })

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        tenant, _ = get_tenant_from_request(self.request)
        qs = self.queryset.filter(tenant=tenant)
        
        record_id = self.request.query_params.get('normalized_record')
        if record_id:
            qs = qs.filter(normalized_record_id=record_id)
            
        return qs
