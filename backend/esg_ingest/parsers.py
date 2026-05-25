import csv
import io
import math
from datetime import datetime, date
from decimal import Decimal
from django.db import transaction
from .models import (
    Tenant, Facility, UtilityAccount, Airport, EmissionFactor,
    IngestionJob, RawRecord, NormalizedRecord, AuditLog
)

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate Great Circle Distance in kilometers using Haversine formula.
    """
    R = 6371.0 # Earth radius in km
    
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2 - lat1))
    delta_lambda = math.radians(float(lon2 - lon1))
    
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return Decimal(str(round(R * c, 2)))

def clean_decimal(val):
    """
    Parse a string value to Decimal, handling European/German commas and dots.
    Example: "1.250,50" -> 1250.50
    """
    if not val:
        return Decimal('0')
    val_str = str(val).strip()
    
    # Handle German formatting
    if ',' in val_str and '.' in val_str:
        if val_str.find('.') < val_str.find(','):
            # dot is thousands separator, comma is decimal
            val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str:
        # If there's only a comma, it could be decimal (German) or thousands (US)
        parts = val_str.split(',')
        if len(parts[-1]) != 3:
            val_str = val_str.replace(',', '.')
        else:
            val_str = val_str.replace(',', '')
            
    try:
        return Decimal(val_str)
    except Exception:
        return Decimal('0')

def parse_date(date_str):
    """
    Parse date from SAP format (YYYYMMDD or DD.MM.YYYY) or standard formats (YYYY-MM-DD or MM/DD/YYYY).
    """
    if not date_str:
        raise ValueError("Empty date string")
        
    date_str = str(date_str).strip()
    
    # SAP YYYYMMDD
    if len(date_str) == 8 and date_str.isdigit():
        return datetime.strptime(date_str, '%Y%m%d').date()
        
    # SAP DD.MM.YYYY
    if '.' in date_str:
        parts = date_str.split('.')
        if len(parts) == 3:
            return datetime.strptime(date_str, '%d.%m.%Y').date()
            
    # Try other common formats
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
            
    raise ValueError(f"Unknown date format: {date_str}")

def parse_sap_row(row, tenant, index, job):
    mblnr = row.get('MBLNR') or row.get('Material Document') or ''
    budat_str = row.get('BUDAT') or row.get('Posting Date') or ''
    werks = row.get('WERKS') or row.get('Plant') or ''
    matnr = row.get('MATNR') or row.get('Material') or ''
    menge_str = row.get('MENGE') or row.get('Quantity') or '0'
    meins = row.get('MEINS') or row.get('Unit') or ''
    maktx = row.get('MAKTX') or row.get('Description') or ''

    raw_rec = RawRecord(job=job, row_index=index, raw_data=row)

    if not mblnr or not budat_str or not werks or not matnr:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = "Missing critical SAP fields: MBLNR, BUDAT, WERKS, or MATNR"
        raw_rec.save()
        return

    # Filter out non-emissions data
    valid_materials = ['DIESEL', 'GASOLINE', 'NATURAL_GAS']
    mat_upper = matnr.upper()
    desc_upper = maktx.upper()
    
    is_emissions = False
    activity_type = None
    for vm in valid_materials:
        if vm in mat_upper or vm in desc_upper:
            is_emissions = True
            activity_type = vm
            break
            
    if not is_emissions:
        raw_rec.status = 'SKIPPED'
        raw_rec.error_message = f"Material {matnr} ({maktx}) classified as non-emissions procurement."
        raw_rec.save()
        return

    try:
        activity_date = parse_date(budat_str)
    except Exception as e:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = f"Date parsing failed for BUDAT '{budat_str}': {str(e)}"
        raw_rec.save()
        return

    facility = Facility.objects.filter(tenant=tenant, plant_code=werks).first()
    if not facility:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = f"Plant code '{werks}' not mapped to any Facility for tenant."
        raw_rec.save()
        return

    raw_qty = clean_decimal(menge_str)
    raw_unit = meins.strip().upper()
    
    unit_mapping = {
        'L': 'L', 'LTR': 'L', 'LIT': 'L',
        'M3': 'm3', 'M³': 'm3', 'CUM': 'm3',
        'KG': 'KG', 'KIL': 'KG'
    }
    norm_unit = unit_mapping.get(raw_unit, raw_unit)
    norm_qty = raw_qty

    ef = EmissionFactor.objects.filter(
        scope=1, category='FUEL', activity_type=activity_type
    ).first()
    
    if not ef:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = f"No Scope 1 Fuel emission factor found for activity type '{activity_type}'."
        raw_rec.save()
        return

    emissions = (norm_qty * ef.factor) / Decimal('1000.0')

    raw_rec.status = 'SUCCESS'
    raw_rec.save()

    norm_rec = NormalizedRecord.objects.create(
        tenant=tenant,
        raw_record=raw_rec,
        facility=facility,
        scope=1,
        category='FUEL',
        activity_type=activity_type,
        start_date=activity_date,
        end_date=activity_date,
        raw_quantity=raw_qty,
        raw_unit=raw_unit,
        normalized_quantity=norm_qty,
        normalized_unit=norm_unit,
        carbon_emissions_mtco2e=emissions,
        status='PENDING'
    )
    
    AuditLog.objects.create(
        tenant=tenant,
        normalized_record=norm_rec,
        action='CREATE',
        new_value=f"Normalized record created from SAP material document {mblnr}."
    )

def parse_utility_row(row, tenant, index, job):
    account_num = row.get('Account Number') or row.get('Account ID') or ''
    meter_num = row.get('Meter Number') or row.get('Meter ID') or ''
    start_date_str = row.get('Start Date') or row.get('Billing Start') or ''
    end_date_str = row.get('End Date') or row.get('Billing End') or ''
    usage_str = row.get('Usage kWh') or row.get('Usage') or '0'
    
    raw_rec = RawRecord(job=job, row_index=index, raw_data=row)

    if not meter_num or not start_date_str or not end_date_str:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = "Missing critical utility fields: Meter Number, Start Date, or End Date"
        raw_rec.save()
        return

    try:
        start_date = parse_date(start_date_str)
        end_date = parse_date(end_date_str)
    except Exception as e:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = f"Date parsing failed: {str(e)}"
        raw_rec.save()
        return

    if start_date > end_date:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = f"Start Date ({start_date}) cannot be after End Date ({end_date})"
        raw_rec.save()
        return

    utility_acct = UtilityAccount.objects.filter(tenant=tenant, meter_number=meter_num).first()
    if not utility_acct:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = f"Meter '{meter_num}' not registered to any Utility Account for this tenant."
        raw_rec.save()
        return

    facility = utility_acct.facility
    raw_qty = clean_decimal(usage_str)
    raw_unit = 'kWh'

    # Check for overlaps in Python
    potential_overlaps = NormalizedRecord.objects.filter(
        tenant=tenant,
        category='ELECTRICITY',
        start_date__lte=end_date,
        end_date__gte=start_date
    ).exclude(status='REJECTED').select_related('raw_record')

    overlaps = False
    for rec in potential_overlaps:
        rec_raw = rec.raw_record.raw_data
        rec_meter = rec_raw.get('Meter Number') or rec_raw.get('Meter ID')
        if rec_meter == meter_num:
            overlaps = True
            break

    comments = ""
    is_suspicious = False
    if overlaps:
        is_suspicious = True
        comments = f"Warning: Overlapping billing cycle detected for meter {meter_num}."

    ef = EmissionFactor.objects.filter(
        scope=2, category='ELECTRICITY', region=facility.region
    ).first()
    
    if not ef:
        ef = EmissionFactor.objects.filter(
            scope=2, category='ELECTRICITY', region=facility.country
        ).first()

    if not ef:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = f"No electricity grid emission factor found for region '{facility.region}' or country '{facility.country}'."
        raw_rec.save()
        return

    emissions = (raw_qty * ef.factor) / Decimal('1000.0')

    # Add proration text info
    total_days = (end_date - start_date).days + 1
    if total_days > 0:
        daily_usage = raw_qty / Decimal(str(total_days))
        daily_emissions = emissions / Decimal(str(total_days))
        
        months = {}
        curr = start_date
        while curr <= end_date:
            m_key = curr.strftime('%B %Y')
            months[m_key] = months.get(m_key, 0) + 1
            curr = datetime.fromordinal(curr.toordinal() + 1).date()
            
        proration_info = []
        for m, days in months.items():
            m_usage = daily_usage * Decimal(str(days))
            m_emissions = daily_emissions * Decimal(str(days))
            proration_info.append(f"{m}: {days} days, {m_usage:.2f} kWh, {m_emissions:.4f} MT CO2e")
        
        comments += (" | " if comments else "") + "Proration breakdown: " + ", ".join(proration_info)

    raw_rec.status = 'SUCCESS'
    raw_rec.save()

    norm_rec = NormalizedRecord.objects.create(
        tenant=tenant,
        raw_record=raw_rec,
        facility=facility,
        scope=2,
        category='ELECTRICITY',
        activity_type='GRID_ELECTRICITY',
        start_date=start_date,
        end_date=end_date,
        raw_quantity=raw_qty,
        raw_unit=raw_unit,
        normalized_quantity=raw_qty,
        normalized_unit='kWh',
        carbon_emissions_mtco2e=emissions,
        status='PENDING',
        rejection_reason=comments
    )

    AuditLog.objects.create(
        tenant=tenant,
        normalized_record=norm_rec,
        action='CREATE',
        new_value=f"Normalized record created from electricity meter {meter_num}. " + comments
    )

def parse_travel_row(row, tenant, index, job):
    booking_id = row.get('Booking ID') or row.get('Expense ID') or ''
    travel_date_str = row.get('Date') or row.get('Transaction Date') or ''
    segment_type = row.get('Type') or row.get('Segment Type') or ''
    
    raw_rec = RawRecord(job=job, row_index=index, raw_data=row)

    if not segment_type or not travel_date_str:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = "Missing critical travel fields: Type or Date"
        raw_rec.save()
        return

    try:
        travel_date = parse_date(travel_date_str)
    except Exception as e:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = f"Date parsing failed: {str(e)}"
        raw_rec.save()
        return

    seg_type_upper = segment_type.strip().upper()
    comments = ""
    is_suspicious = False

    if 'FLIGHT' in seg_type_upper:
        origin = (row.get('Flight Origin') or '').strip().upper()
        dest = (row.get('Flight Destination') or '').strip().upper()
        cabin = (row.get('Cabin Class') or 'Economy').strip()
        
        if not origin or not dest:
            raw_rec.status = 'FAILED'
            raw_rec.error_message = "Flight segment requires Flight Origin and Flight Destination IATA codes"
            raw_rec.save()
            return
            
        ap_origin = Airport.objects.filter(iata_code=origin).first()
        ap_dest = Airport.objects.filter(iata_code=dest).first()
        
        if not ap_origin or not ap_dest:
            raw_rec.status = 'FAILED'
            raw_rec.error_message = f"Airports not found in reference DB: origin '{origin}', dest '{dest}'"
            raw_rec.save()
            return
            
        distance = calculate_haversine_distance(
            ap_origin.latitude, ap_origin.longitude,
            ap_dest.latitude, ap_dest.longitude
        )
        
        if distance < Decimal('3700.0'):
            activity_type = 'FLIGHT_SHORT_HAUL'
        else:
            activity_type = 'FLIGHT_LONG_HAUL'
            
        ef = EmissionFactor.objects.filter(
            scope=3, category='FLIGHT', activity_type=activity_type
        ).first()
        
        if not ef:
            raw_rec.status = 'FAILED'
            raw_rec.error_message = f"No emission factor found for travel segment '{activity_type}'"
            raw_rec.save()
            return

        cabin_upper = cabin.upper()
        if 'BUS' in cabin_upper or cabin_upper == 'C':
            multiplier = Decimal('2.90')
            comments = "Cabin class: Business (multiplier 2.90 applied)"
        elif 'FIRST' in cabin_upper or cabin_upper == 'F':
            multiplier = Decimal('4.00')
            comments = "Cabin class: First class (multiplier 4.00 applied)"
        elif 'ECON' in cabin_upper or cabin_upper == 'Y' or not cabin:
            multiplier = Decimal('1.00')
            if not cabin:
                is_suspicious = True
                comments = "Warning: Cabin class missing, defaulted to Economy (multiplier 1.00)"
        else:
            multiplier = Decimal('1.00')
            comments = f"Cabin class: {cabin} (multiplier 1.00)"

        raw_qty = distance
        raw_unit = 'km'
        norm_qty = distance
        norm_unit = 'pkm'
        emissions = (norm_qty * ef.factor * multiplier) / Decimal('1000.0')

    elif 'HOTEL' in seg_type_upper:
        country = (row.get('Hotel Country') or '').strip().upper()
        nights_str = row.get('Hotel Nights') or '0'
        raw_qty = clean_decimal(nights_str)
        raw_unit = 'room_night'
        
        if raw_qty <= 0:
            raw_rec.status = 'FAILED'
            raw_rec.error_message = f"Invalid hotel nights quantity: '{nights_str}'"
            raw_rec.save()
            return
            
        if not country:
            country = tenant.hq_country
            is_suspicious = True
            comments = f"Warning: Hotel country missing, defaulted to tenant HQ country '{country}'."
            
        ef = EmissionFactor.objects.filter(
            scope=3, category='HOTEL', region=country
        ).first()
        
        if not ef:
            ef = EmissionFactor.objects.filter(
                scope=3, category='HOTEL', region='GLOBAL'
            ).first()
            
        if not ef:
            raw_rec.status = 'FAILED'
            raw_rec.error_message = f"No emission factor found for Hotel stays in region '{country}' or 'GLOBAL'"
            raw_rec.save()
            return
            
        norm_qty = raw_qty
        norm_unit = 'room_night'
        activity_type = 'HOTEL_NIGHT'
        emissions = (norm_qty * ef.factor) / Decimal('1000.0')

    elif 'CAR' in seg_type_upper or 'DRIVE' in seg_type_upper or 'GROUND' in seg_type_upper:
        car_cat = (row.get('Car Category') or 'Gasoline').strip().upper()
        dist_str = row.get('Distance km') or row.get('Distance') or ''
        days_str = row.get('Rental Days') or ''
        
        if 'ELEC' in car_cat or 'EV' in car_cat:
            activity_type = 'CAR_RENTAL_ELECTRIC'
        else:
            activity_type = 'CAR_RENTAL_GASOLINE'
            
        ef = EmissionFactor.objects.filter(
            scope=3, category='GROUND_TRANSPORT', activity_type=activity_type
        ).first()
        
        if not ef:
            raw_rec.status = 'FAILED'
            raw_rec.error_message = f"No ground transport emission factor found for activity type '{activity_type}'."
            raw_rec.save()
            return

        raw_qty = clean_decimal(dist_str)
        raw_unit = 'km'
        
        if raw_qty <= 0:
            days = clean_decimal(days_str)
            if days > 0:
                is_suspicious = True
                raw_qty = days * Decimal('80.0')
                comments = f"Warning: Missing distance, estimated {raw_qty} km based on {days} rental days (80 km/day)."
            else:
                raw_rec.status = 'FAILED'
                raw_rec.error_message = "Ground segment requires either 'Distance' or 'Rental Days' for calculation."
                raw_rec.save()
                return

        norm_qty = raw_qty
        norm_unit = 'km'
        emissions = (norm_qty * ef.factor) / Decimal('1000.0')

    else:
        raw_rec.status = 'FAILED'
        raw_rec.error_message = f"Unsupported corporate travel segment type: '{segment_type}'"
        raw_rec.save()
        return

    raw_rec.status = 'SUCCESS'
    raw_rec.save()

    norm_rec = NormalizedRecord.objects.create(
        tenant=tenant,
        raw_record=raw_rec,
        facility=None,
        scope=3,
        category=ef.category,
        activity_type=activity_type,
        start_date=travel_date,
        end_date=travel_date,
        raw_quantity=raw_qty,
        raw_unit=raw_unit,
        normalized_quantity=norm_qty,
        normalized_unit=norm_unit,
        carbon_emissions_mtco2e=emissions,
        status='PENDING',
        rejection_reason=comments
    )

    AuditLog.objects.create(
        tenant=tenant,
        normalized_record=norm_rec,
        action='CREATE',
        new_value=f"Normalized record created from travel booking {booking_id}. " + comments
    )

def run_parser_on_csv(job, file_content_str):
    tenant = job.tenant
    source_type = job.source_type
    
    f = io.StringIO(file_content_str.strip())
    reader = csv.DictReader(f)
    
    if not reader.fieldnames:
        job.status = 'FAILED'
        job.error_summary = "CSV is empty or lacks headers."
        job.save()
        return False

    success_count = 0
    failed_count = 0
    skipped_count = 0

    with transaction.atomic():
        for i, row in enumerate(reader, start=1):
            # Skip completely empty or whitespace rows (common in spreadsheet CSV exports)
            if not row or not any(str(v).strip() for v in row.values() if v is not None):
                continue
            try:
                if source_type == 'SAP_FUEL_PROCUREMENT':
                    parse_sap_row(row, tenant, i, job)
                elif source_type == 'UTILITY_PORTAL_CSV':
                    parse_utility_row(row, tenant, i, job)
                elif source_type == 'CONCUR_TRAVEL':
                    parse_travel_row(row, tenant, i, job)
            except Exception as e:
                RawRecord.objects.create(
                    job=job,
                    row_index=i,
                    raw_data=row,
                    status='FAILED',
                    error_message=f"System error: {str(e)}"
                )

        raws = RawRecord.objects.filter(job=job)
        for r in raws:
            if r.status == 'SUCCESS':
                success_count += 1
            elif r.status == 'FAILED':
                failed_count += 1
            elif r.status == 'SKIPPED':
                skipped_count += 1

    job.status = 'COMPLETED'
    job.error_summary = f"Parsed {success_count + failed_count + skipped_count} rows: {success_count} success, {failed_count} failed, {skipped_count} skipped."
    job.save()
    return True
