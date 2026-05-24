from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserProfileViewSet, FacilityViewSet, UtilityAccountViewSet,
    AirportViewSet, EmissionFactorViewSet, IngestionJobViewSet,
    NormalizedRecordViewSet, AuditLogViewSet
)

router = DefaultRouter()
router.register(r'users', UserProfileViewSet, basename='user')
router.register(r'facilities', FacilityViewSet, basename='facility')
router.register(r'utility-accounts', UtilityAccountViewSet, basename='utility-account')
router.register(r'airports', AirportViewSet, basename='airport')
router.register(r'emission-factors', EmissionFactorViewSet, basename='emission-factor')
router.register(r'ingest-jobs', IngestionJobViewSet, basename='ingest-job')
router.register(r'normalized-records', NormalizedRecordViewSet, basename='normalized-record')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('', include(router.urls)),
]
