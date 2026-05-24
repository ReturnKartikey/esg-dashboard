import os
import django
from decimal import Decimal

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from esg_ingest.models import Tenant, UserProfile, Facility, UtilityAccount, Airport, EmissionFactor

def seed_database():
    print("Starting database seeding...")

    # 1. Tenants
    acme, _ = Tenant.objects.get_or_create(name="Acme Corporation", hq_country="US")
    ecosphere, _ = Tenant.objects.get_or_create(name="EcoSphere Industries", hq_country="US")
    print(f"Created/found tenants: {acme.name}, {ecosphere.name}")

    # 2. Users (Analysts & Auditors)
    users_data = [
        # Acme Users
        ('acme_analyst', 'analyst@acme.com', 'password123', acme, 'ANALYST'),
        ('acme_auditor', 'auditor@acme.com', 'password123', acme, 'AUDITOR'),
        ('acme_admin', 'admin@acme.com', 'password123', acme, 'ADMIN'),
        # EcoSphere Users
        ('eco_analyst', 'analyst@ecosphere.com', 'password123', ecosphere, 'ANALYST'),
        ('eco_auditor', 'auditor@ecosphere.com', 'password123', ecosphere, 'AUDITOR'),
        ('eco_admin', 'admin@ecosphere.com', 'password123', ecosphere, 'ADMIN'),
    ]

    for username, email, pwd, tenant, role in users_data:
        user, created = User.objects.get_or_create(username=username, email=email)
        if created:
            user.set_password(pwd)
            user.save()
        
        profile, _ = UserProfile.objects.get_or_create(user=user, tenant=tenant)
        profile.role = role
        profile.save()
        print(f"User {username} ({role}) ready for tenant {tenant.name}.")

    # 3. Facilities
    facilities_data = [
        # Acme Plants
        (acme, "Acme California Manufacturing", "US10", "US", "US-CA"),
        (acme, "Acme Berlin Assembly", "DE20", "DE", "DE"),
        # EcoSphere Plants
        (ecosphere, "EcoSphere Texas Petrochemical", "TX01", "US", "US-TX"),
        (ecosphere, "EcoSphere London Head Office", "UK02", "GB", "GB"),
    ]

    facility_map = {}
    for tenant, name, code, country, region in facilities_data:
        fac, _ = Facility.objects.get_or_create(
            tenant=tenant, plant_code=code,
            defaults={'name': name, 'country': country, 'region': region}
        )
        facility_map[(tenant.id, code)] = fac
        print(f"Facility: {fac.name} [{fac.plant_code}]")

    # 4. Utility Accounts
    utility_data = [
        (acme, facility_map[(acme.id, "US10")], "ACME-ELEC-99", "METER-CA-101", "PG&E"),
        (acme, facility_map[(acme.id, "DE20")], "ACME-ELEC-88", "METER-DE-202", "Vattenfall"),
        (ecosphere, facility_map[(ecosphere.id, "TX01")], "ECO-ELEC-77", "METER-TX-707", "Oncor"),
        (ecosphere, facility_map[(ecosphere.id, "UK02")], "ECO-ELEC-66", "METER-UK-606", "British Gas"),
    ]

    for tenant, fac, acct_num, meter_num, provider in utility_data:
        ua, _ = UtilityAccount.objects.get_or_create(
            tenant=tenant, meter_number=meter_num,
            defaults={'facility': fac, 'account_number': acct_num, 'provider_name': provider}
        )
        print(f"Utility Account: {ua.provider_name} Account {ua.account_number} Meter {ua.meter_number}")

    # 5. Airports
    airports_data = [
        ('JFK', 'John F. Kennedy International Airport', 'New York', 'US', Decimal('40.639751'), Decimal('-73.778925')),
        ('SFO', 'San Francisco International Airport', 'San Francisco', 'US', Decimal('37.618999'), Decimal('-122.374888')),
        ('LHR', 'London Heathrow Airport', 'London', 'GB', Decimal('51.470020'), Decimal('-0.454295')),
        ('TXL', 'Berlin Tegel Airport', 'Berlin', 'DE', Decimal('52.559688'), Decimal('13.287711')),
        ('BER', 'Berlin Brandenburg Airport', 'Berlin', 'DE', Decimal('52.366667'), Decimal('13.503333')),
        ('CDG', 'Charles de Gaulle Airport', 'Paris', 'FR', Decimal('49.009724'), Decimal('2.547912')),
        ('BOM', 'Chhatrapati Shivaji Maharaj Airport', 'Mumbai', 'IN', Decimal('19.089600'), Decimal('72.865600')),
        ('BLR', 'Kempegowda International Airport', 'Bengaluru', 'IN', Decimal('13.198600'), Decimal('77.706600')),
        ('HND', 'Haneda Airport', 'Tokyo', 'JP', Decimal('35.549400'), Decimal('139.779800')),
    ]

    for code, name, city, country, lat, lon in airports_data:
        ap, _ = Airport.objects.get_or_create(
            iata_code=code,
            defaults={'name': name, 'city': city, 'country': country, 'latitude': lat, 'longitude': lon}
        )
        print(f"Airport: {ap.iata_code} ({ap.city})")

    # 6. Emission Factors
    # Units: L (Liters), m3 (Cubic Meters), kWh (Kilowatt Hours), pkm (Passenger Kilometers), room_night
    factors_data = [
        # Scope 1: Fuel Combustion
        (1, 'FUEL', 'DIESEL', 'GLOBAL', Decimal('2.680000'), 'L', 'EPA Greenhouse Gas Hub 2024'),
        (1, 'FUEL', 'GASOLINE', 'GLOBAL', Decimal('2.310000'), 'L', 'EPA Greenhouse Gas Hub 2024'),
        (1, 'FUEL', 'NATURAL_GAS', 'GLOBAL', Decimal('1.880000'), 'm3', 'EPA Greenhouse Gas Hub 2024'),
        
        # Scope 2: Grid Electricity
        (2, 'ELECTRICITY', 'GRID_ELECTRICITY', 'US-CA', Decimal('0.231000'), 'kWh', 'EPA eGRID 2023 (CAMX)'),
        (2, 'ELECTRICITY', 'GRID_ELECTRICITY', 'US-TX', Decimal('0.384000'), 'kWh', 'EPA eGRID 2023 (ERCOT)'),
        (2, 'ELECTRICITY', 'GRID_ELECTRICITY', 'DE', Decimal('0.352000'), 'kWh', 'IEA Country Factors 2023'),
        (2, 'ELECTRICITY', 'GRID_ELECTRICITY', 'GB', Decimal('0.207000'), 'kWh', 'UK DEFRA 2023'),
        
        # Scope 3: Travel - Flights
        (3, 'FLIGHT', 'FLIGHT_SHORT_HAUL', 'GLOBAL', Decimal('0.151000'), 'pkm', 'UK DEFRA 2024 (Short-haul Economy)'),
        (3, 'FLIGHT', 'FLIGHT_LONG_HAUL', 'GLOBAL', Decimal('0.185000'), 'pkm', 'UK DEFRA 2024 (Long-haul Economy)'),
        
        # Scope 3: Travel - Hotels
        (3, 'HOTEL', 'HOTEL_NIGHT', 'US', Decimal('20.400000'), 'room_night', 'DEFRA Hotel Factors 2024'),
        (3, 'HOTEL', 'HOTEL_NIGHT', 'DE', Decimal('15.600000'), 'room_night', 'DEFRA Hotel Factors 2024'),
        (3, 'HOTEL', 'HOTEL_NIGHT', 'GB', Decimal('13.800000'), 'room_night', 'DEFRA Hotel Factors 2024'),
        (3, 'HOTEL', 'HOTEL_NIGHT', 'IN', Decimal('45.100000'), 'room_night', 'DEFRA Hotel Factors 2024'),
        (3, 'HOTEL', 'HOTEL_NIGHT', 'GLOBAL', Decimal('22.000000'), 'room_night', 'DEFRA Hotel Factors 2024'),

        # Scope 3: Travel - Ground Transport
        (3, 'GROUND_TRANSPORT', 'CAR_RENTAL_GASOLINE', 'GLOBAL', Decimal('0.171000'), 'km', 'UK DEFRA 2024 (Average Medium Car)'),
        (3, 'GROUND_TRANSPORT', 'CAR_RENTAL_ELECTRIC', 'GLOBAL', Decimal('0.048000'), 'km', 'UK DEFRA 2024 (Electric Vehicle)'),
    ]

    for scope, cat, act, reg, fact, unit, citation in factors_data:
        ef, _ = EmissionFactor.objects.get_or_create(
            scope=scope, category=cat, activity_type=act, region=reg,
            defaults={'factor': fact, 'unit': unit, 'source_citation': citation}
        )
        print(f"Emission Factor: {ef.category}:{ef.activity_type} ({ef.region}) = {ef.factor} kg CO2e/{ef.unit}")

    print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed_database()
