from django.test import TestCase, Client
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date
from .models import Tenant, UserProfile, Facility, UtilityAccount, Airport, EmissionFactor, NormalizedRecord, IngestionJob, RawRecord
from .parsers import calculate_haversine_distance, clean_decimal, parse_date, run_parser_on_csv

class ESGCalculationTests(TestCase):
    def test_haversine_distance(self):
        # Coordinates of JFK and SFO
        # JFK: 40.639751, -73.778925
        # SFO: 37.618999, -122.374888
        # Expected distance is approx 4150 km
        dist = calculate_haversine_distance(
            Decimal('40.639751'), Decimal('-73.778925'),
            Decimal('37.618999'), Decimal('-122.374888')
        )
        self.assertGreater(dist, Decimal('4100.0'))
        self.assertLess(dist, Decimal('4200.0'))

    def test_clean_decimal(self):
        # US Format
        self.assertEqual(clean_decimal("1250.50"), Decimal("1250.50"))
        # German Format with thousands dot and decimal comma
        self.assertEqual(clean_decimal("1.250,50"), Decimal("1250.50"))
        # German Format with comma only
        self.assertEqual(clean_decimal("1250,50"), Decimal("1250.50"))
        # Clean plain numbers
        self.assertEqual(clean_decimal("100"), Decimal("100"))

    def test_parse_date(self):
        # YYYYMMDD SAP
        self.assertEqual(parse_date("20260425"), date(2026, 4, 25))
        # DD.MM.YYYY SAP
        self.assertEqual(parse_date("25.04.2026"), date(2026, 4, 25))
        # YYYY-MM-DD
        self.assertEqual(parse_date("2026-04-25"), date(2026, 4, 25))
        # MM/DD/YYYY US
        self.assertEqual(parse_date("04/25/2026"), date(2026, 4, 25))


class ESGParserTests(TestCase):
    def setUp(self):
        # Set up tenant
        self.tenant = Tenant.objects.create(name="Test Corp", hq_country="US")
        
        # Set up analyst user
        self.user = User.objects.create_user(username="test_analyst", password="password")
        self.profile = UserProfile.objects.create(user=self.user, tenant=self.tenant, role='ANALYST')
        
        # Set up facility and mapping
        self.facility = Facility.objects.create(
            tenant=self.tenant, name="Test Plant", plant_code="PL01", country="US", region="US-CA"
        )
        
        self.meter = UtilityAccount.objects.create(
            tenant=self.tenant, facility=self.facility, account_number="ACCT123", meter_number="MET456", provider_name="Test Utility"
        )

        # Set up airports
        Airport.objects.create(iata_code="SFO", name="SF Airport", city="SF", country="US", latitude=Decimal("37.618"), longitude=Decimal("-122.374"))
        Airport.objects.create(iata_code="JFK", name="NY Airport", city="NY", country="US", latitude=Decimal("40.639"), longitude=Decimal("-73.778"))

        # Set up emission factors
        EmissionFactor.objects.create(scope=1, category="FUEL", activity_type="DIESEL", region="GLOBAL", factor=Decimal("2.68"), unit="L")
        EmissionFactor.objects.create(scope=2, category="ELECTRICITY", activity_type="GRID_ELECTRICITY", region="US-CA", factor=Decimal("0.23"), unit="kWh")
        EmissionFactor.objects.create(scope=3, category="FLIGHT", activity_type="FLIGHT_LONG_HAUL", region="GLOBAL", factor=Decimal("0.18"), unit="pkm")

    def test_sap_ingestion(self):
        # SAP CSV content: DIESEL fuel row and unrelated steel row (skipped)
        csv_data = (
            "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,MAKTX\n"
            "DOC101,20260425,PL01,DIESEL,1000,L,Diesel Fuel\n"
            "DOC102,20260425,PL01,STEEL,500,KG,Steel Rebars"
        )
        job = IngestionJob.objects.create(
            tenant=self.tenant, source_type="SAP_FUEL_PROCUREMENT", file_name="sap.csv", uploaded_by=self.profile
        )
        run_parser_on_csv(job, csv_data)
        
        # Verify job completed
        self.assertEqual(job.status, "COMPLETED")
        
        # Verify raw records counts
        self.assertEqual(RawRecord.objects.filter(job=job, status="SUCCESS").count(), 1)
        self.assertEqual(RawRecord.objects.filter(job=job, status="SKIPPED").count(), 1)
        
        # Verify normalized record emissions: 1000 Liters * 2.68 kg/L = 2680 kg = 2.68 MT CO2e
        norm_rec = NormalizedRecord.objects.filter(tenant=self.tenant, category="FUEL").first()
        self.assertIsNotNone(norm_rec)
        self.assertEqual(norm_rec.carbon_emissions_mtco2e, Decimal("2.68"))
        self.assertEqual(norm_rec.facility, self.facility)

    def test_utility_ingestion(self):
        # Utility CSV content
        csv_data = (
            "Account Number,Meter Number,Start Date,End Date,Usage kWh\n"
            "ACCT123,MET456,2026-04-12,2026-05-11,10000"
        )
        job = IngestionJob.objects.create(
            tenant=self.tenant, source_type="UTILITY_PORTAL_CSV", file_name="utility.csv", uploaded_by=self.profile
        )
        run_parser_on_csv(job, csv_data)
        
        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(RawRecord.objects.filter(job=job, status="SUCCESS").count(), 1)
        
        # Verify emissions: 10000 kWh * 0.23 kg/kWh = 2300 kg = 2.30 MT CO2e
        norm_rec = NormalizedRecord.objects.filter(tenant=self.tenant, category="ELECTRICITY").first()
        self.assertIsNotNone(norm_rec)
        self.assertEqual(norm_rec.carbon_emissions_mtco2e, Decimal("2.30"))

    def test_travel_flight_ingestion(self):
        # Travel flight CSV content
        csv_data = (
            "Booking ID,Date,Type,Flight Origin,Flight Destination,Cabin Class\n"
            "B101,2026-04-15,Flight,SFO,JFK,Business"
        )
        job = IngestionJob.objects.create(
            tenant=self.tenant, source_type="CONCUR_TRAVEL", file_name="travel.csv", uploaded_by=self.profile
        )
        run_parser_on_csv(job, csv_data)
        
        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(RawRecord.objects.filter(job=job, status="SUCCESS").count(), 1)
        
        # Verify normalized record exists
        norm_rec = NormalizedRecord.objects.filter(tenant=self.tenant, category="FLIGHT").first()
        self.assertIsNotNone(norm_rec)
        
        # Multiplier of 2.9 should be applied for Business Class
        # Distance between SFO and JFK is roughly 4150 km, emissions: dist * 0.18 * 2.9 / 1000
        self.assertGreater(norm_rec.carbon_emissions_mtco2e, Decimal("1.5"))


class ESGMultiTenantSecurityTests(TestCase):
    def setUp(self):
        # Set up two tenants
        self.tenant_a = Tenant.objects.create(name="Tenant A", hq_country="US")
        self.tenant_b = Tenant.objects.create(name="Tenant B", hq_country="DE")
        
        # Set up users
        self.user_a = User.objects.create_user(username="user_a", password="password")
        self.profile_a = UserProfile.objects.create(user=self.user_a, tenant=self.tenant_a, role='ANALYST')

        self.user_b = User.objects.create_user(username="user_b", password="password")
        self.profile_b = UserProfile.objects.create(user=self.user_b, tenant=self.tenant_b, role='ANALYST')
        
        # Set up a record for Tenant B
        job_b = IngestionJob.objects.create(
            tenant=self.tenant_b, source_type="SAP_FUEL_PROCUREMENT", file_name="sap_b.csv", status="COMPLETED"
        )
        raw_b = RawRecord.objects.create(job=job_b, row_index=1, raw_data={}, status="SUCCESS")
        self.rec_b = NormalizedRecord.objects.create(
            tenant=self.tenant_b, raw_record=raw_b, scope=1, category="FUEL", activity_type="DIESEL",
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 1),
            raw_quantity=100, raw_unit="L", normalized_quantity=100, normalized_unit="L",
            carbon_emissions_mtco2e=Decimal("0.268"), status="PENDING"
        )

    def test_tenant_data_isolation(self):
        # Create client
        client = Client()
        
        # Request data as user_a (Tenant A)
        # We simulate this by setting the X-Mock-User header
        response = client.get('/api/normalized-records/', HTTP_X_MOCK_USER='user_a')
        self.assertEqual(response.status_code, 200)
        
        # Tenant A should see 0 records (since the only record belongs to Tenant B)
        self.assertEqual(len(response.data), 0)
        
        # Request data as user_b (Tenant B)
        response_b = client.get('/api/normalized-records/', HTTP_X_MOCK_USER='user_b')
        self.assertEqual(response_b.status_code, 200)
        
        # Tenant B should see their 1 record
        self.assertEqual(len(response_b.data), 1)
        self.assertEqual(response_b.data[0]['id'], str(self.rec_b.id))
