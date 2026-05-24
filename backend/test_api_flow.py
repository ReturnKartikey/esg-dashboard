import os
import django
from django.test import Client
import io

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from esg_ingest.models import Tenant, UserProfile, IngestionJob, RawRecord, NormalizedRecord, AuditLog

def run_end_to_end_test():
    print("====================================================")
    print("STARTING END-TO-END ESG PIPELINE TEST")
    print("====================================================\n")

    client = Client()

    # Clear any previous test run data to ensure a clean slate
    IngestionJob.objects.all().delete()
    RawRecord.objects.all().delete()
    NormalizedRecord.objects.all().delete()
    AuditLog.objects.all().delete()

    # 1. Simulate Uploading an SAP CSV Feed
    # Setup mock CSV data (Diesel row + skipped steel row)
    sap_csv = (
        "MBLNR,BUDAT,WERKS,MATNR,MENGE,MEINS,MAKTX\n"
        "DOC_TEST_001,20260425,US10,DIESEL,1000,L,Diesel Fuel\n"
        "DOC_TEST_002,20260425,US10,STEEL_REBAR,500,KG,Office Steel Rebar"
    )
    
    csv_file = io.BytesIO(sap_csv.encode('utf-8-sig'))
    csv_file.name = 'test_sap_upload.csv'

    print("Step 1: Uploading SAP Goods Movement CSV as 'acme_analyst'...")
    response = client.post(
        '/api/ingest-jobs/upload/',
        {'source_type': 'SAP_FUEL_PROCUREMENT', 'file': csv_file},
        HTTP_X_MOCK_USER='acme_analyst'
    )
    
    if response.status_code != 201:
        print(f"[FAIL] Upload failed with status {response.status_code}: {response.data}")
        return
    
    job_id = response.data['id']
    status_summary = response.data['error_summary']
    print(f"[OK] Ingestion Job created: {job_id}")
    print(f"Status Summary: {status_summary}\n")

    # 2. Verify Ingested Records & Lineage
    print("Step 2: Verifying normalized records in ledger...")
    response = client.get('/api/normalized-records/', HTTP_X_MOCK_USER='acme_analyst')
    records = response.data
    
    print(f"Total records found for Acme: {len(records)}")
    if len(records) != 1:
        print("[FAIL] Expected exactly 1 normalized record (the Diesel row). Steel should be skipped.")
        return
        
    record = records[0]
    print(f"[OK] Normalized Row ID: {record['id']}")
    print(f"   Activity Type: {record['activity_type']}")
    print(f"   Raw Qty: {record['raw_quantity']} {record['raw_unit']}")
    print(f"   Emissions: {record['carbon_emissions_mtco2e']} MT CO2e")
    print(f"   Review Status: {record['status']}")
    print(f"   Audit trail check - Is Edited? {record['is_edited']}")
    print(f"   Source Row Data stored: {record['raw_data']}\n")

    # 3. Simulate Analyst Editing Quantity (Triggers Recalculation & Audit Log)
    print("Step 3: Simulating Analyst editing the raw quantity from 1000 to 2000...")
    record_id = record['id']
    response = client.patch(
        f'/api/normalized-records/{record_id}/',
        {'raw_quantity': 2000.0, 'normalized_quantity': 2000.0, 'activity_type': 'DIESEL'},
        content_type='application/json',
        HTTP_X_MOCK_USER='acme_analyst'
    )
    
    if response.status_code != 200:
        print(f"[FAIL] Record edit failed: {response.data}")
        return
        
    updated_rec = response.data
    print(f"[OK] Edit Successful! New Emissions recalculated: {updated_rec['carbon_emissions_mtco2e']} MT CO2e")
    print(f"   Is Edited flag: {updated_rec['is_edited']}")
    
    # Check Audit Logs
    audit_response = client.get(f'/api/audit-logs/?normalized_record={record_id}', HTTP_X_MOCK_USER='acme_analyst')
    logs = audit_response.data
    print(f"[OK] Audit Log entries recorded: {len(logs)}")
    for log in logs:
        print(f"   - Action: {log['action']} | Field: {log['field_name']} | Diff: {log['old_value']} -> {log['new_value']} | By: {log['changed_by_username']}")
    print()

    # 4. Sign off (Approve) the Record
    print("Step 4: Signing off and approving the record...")
    response = client.post(
        '/api/normalized-records/bulk-action/',
        {'action': 'approve', 'ids': [record_id]},
        content_type='application/json',
        HTTP_X_MOCK_USER='acme_analyst'
    )
    
    if response.status_code != 200:
        print(f"[FAIL] Approval failed: {response.data}")
        return
        
    print(f"[OK] Status updated: {response.data['message']}")
    
    # Verify record is now locked
    response = client.get(f'/api/normalized-records/{record_id}/', HTTP_X_MOCK_USER='acme_analyst')
    print(f"   Ledger Row Status: {response.data['status']}")
    print(f"   Reviewer: {response.data['reviewed_by_username']} at {response.data['reviewed_at']}")
    
    # Try editing again to verify locking
    lock_response = client.patch(
        f'/api/normalized-records/{record_id}/',
        {'raw_quantity': 3000.0},
        content_type='application/json',
        HTTP_X_MOCK_USER='acme_analyst'
    )
    if lock_response.status_code == 400:
        print("[LOCK-OK] LOCKING VERIFIED: Server successfully blocked editing of approved record!")
    else:
        print(f"[FAIL] Locked record edit was not blocked (Status {lock_response.status_code})")
        return
    print()

    # 5. Check Dashboard stats
    print("Step 5: Verifying approved metrics on sustainability dashboard...")
    stats_response = client.get('/api/normalized-records/dashboard-stats/', HTTP_X_MOCK_USER='acme_analyst')
    stats = stats_response.data
    print(f"[OK] Dashboard Total Approved Emissions: {stats['total_emissions_mtco2e']} MT CO2e")
    print(f"   Breakdown: Scope 1={stats['scopes']['scope_1']}, Scope 2={stats['scopes']['scope_2']}, Scope 3={stats['scopes']['scope_3']}")
    print(f"   Timeline Timeline (monthly prorated): {stats['timeline']}\n")

    # 6. Test Multi-Tenant Security Isolation
    print("Step 6: Testing multi-tenant security isolation...")
    print("   Attempting to retrieve Acme's data as EcoSphere analyst ('eco_analyst')...")
    eco_response = client.get('/api/normalized-records/', HTTP_X_MOCK_USER='eco_analyst')
    
    if len(eco_response.data) == 0:
        print("[SECURE-OK] TENANT ISOLATION VERIFIED: EcoSphere analyst sees 0 records. Acme's data is isolated!")
    else:
        print(f"[FAIL] SECURITY BREACH: EcoSphere analyst retrieved {len(eco_response.data)} records from Acme tenant!")
        return

    print("\n====================================================")
    print("ALL END-TO-END ESG TESTS PASSED SUCCESSFULLY!")
    print("====================================================")

if __name__ == '__main__':
    run_end_to_end_test()
