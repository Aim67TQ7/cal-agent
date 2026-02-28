# 租户内核 | Tenant Kernel: Bunting Magnetics
## ∀ {TENANT_NAME} · 租户特定配置

---

### 公司概况 | Company Profile
```
company  := Bunting Magnetics Company
industry := 磁性设备制造 · Magnetic equipment manufacturing & separation
parent   := BFR Group (Bunting Family of Recyclers)
locations := Newton, KS (HQ + manufacturing) · additional facilities
standards := ISO 9001:2015 · customer-specific QA requirements
timezone  := America/Chicago (CST/CDT)
company_id := 3
```

---

### 联系人 | Key Contacts
```
quality_team := {
  ryan_linton   := rlinton@buntingmagnetics.com · Quality Manager · company_admin
  brandon_dick  := bdick@buntingmagnetics.com · Quality Tech Lead · company_admin
  derek_sanchez := dsanchez@buntingmagnetics.com · Quality Technician
  steve_bryant  := sbryant@buntingmagnetics.com · Quality Technician
}
escalation := Derek/Steve → Brandon → Ryan
```

---

### 校准实验室 | Calibration Labs & Vendors
```
primary_lab     := Precision Calibration Services (local, Newton KS area)
secondary_lab   := Transcat (national, for complex instruments)
in_house        := Snap gages, go/no-go gages — verified in-house per procedure
turnaround_std  := 5-10 business days standard
turnaround_rush := 2-3 business days (surcharge applies)
```

---

### 邮件路由 | Email Routing
```
cal_inbox := cal@bunting.gp3.app

vendor_emails := {
  precision_cal := *@precisioncal.com
  transcat      := *@transcat.com
}

internal_routing := {
  cert_received   → notify: brandon_dick, derek_sanchez
  po_confirmation → notify: ryan_linton
  overdue_alert   → notify: ryan_linton, brandon_dick
  audit_prep      → notify: ryan_linton
}

purchasing_email := purchasing@buntingmagnetics.com
receiving_email  := receiving@buntingmagnetics.com
```

---

### 设备类别 | Equipment Categories
```
measurement_types := {
  Snap Gage    → Go/no-go dimensional checks · most common category (~40 tools)
  Micrometer   → Precision dimensional measurement · outside/inside/depth/blade/disc/flange/thread
  Caliper      → Vernier/digital calipers · general dimensional
  Bore Gage    → Internal diameter measurement
  Gaussmeter   → Magnetic field strength measurement · CRITICAL for product QA
  Indicator    → Dial indicators, test indicators, digital gage heads
  Height Gage  → Precision height measurement
  Scale        → Weighing scales and balances
  Hardness Tester → Rockwell/Brinell hardness, durometers
  Force Gage   → Push/pull force measurement
  Gage Block Set → Ceramic gage blocks for reference
  Surface Plate → Granite inspection tables
  Probe        → Gauss probes (axial, transverse)
}

critical_equipment := {
  Gaussmeter      → Core product verification — CANNOT ship without current cal
  Hardness Tester → Material certification requirement
}
```

---

### 查询模板 | Query Templates (Parameterized)
```xml
<QUERY_TEMPLATES note="Use {{var}} params — adapt to user question">

find_by_category({{category}}):
  SELECT asset_tag, tool_name, tool_type, manufacturer, calibration_status, next_due_date
  FROM cal.tools WHERE company_id = :cid
  AND tool_type = '{{category}}'
  ORDER BY next_due_date ASC

find_by_category_fuzzy({{term}}):
  SELECT asset_tag, tool_name, tool_type, manufacturer, calibration_status, next_due_date
  FROM cal.tools WHERE company_id = :cid
  AND (tool_type ILIKE '%{{term}}%' OR tool_name ILIKE '%{{term}}%')
  ORDER BY next_due_date ASC

find_by_method({{method}}):
  SELECT asset_tag, tool_name, tool_type, calibration_method, calibration_status
  FROM cal.tools WHERE company_id = :cid
  AND calibration_method ILIKE '%{{method}}%'
  ORDER BY tool_type, asset_tag

due_within({{days}}):
  SELECT asset_tag, tool_name, tool_type, next_due_date, calibration_status
  FROM cal.tools WHERE company_id = :cid
  AND next_due_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '{{days}} days')
  ORDER BY next_due_date ASC

overdue():
  SELECT asset_tag, tool_name, tool_type, next_due_date, calibration_status
  FROM cal.tools WHERE company_id = :cid
  AND (calibration_status = 'overdue'
    OR (next_due_date IS NOT NULL AND next_due_date < CURRENT_DATE))
  ORDER BY next_due_date ASC

compliance():
  SELECT calibration_status, COUNT(*) as cnt
  FROM cal.tools WHERE company_id = :cid
  GROUP BY calibration_status

inventory():
  SELECT tool_type, COUNT(*) as cnt
  FROM cal.tools WHERE company_id = :cid
  GROUP BY tool_type ORDER BY cnt DESC

by_location({{location_term}}):
  SELECT asset_tag, tool_name, tool_type, location, building, calibration_status
  FROM cal.tools WHERE company_id = :cid
  AND (location ILIKE '%{{location_term}}%' OR building ILIKE '%{{location_term}}%')
  ORDER BY tool_type

cal_history({{tool_ref}}):
  SELECT c.calibration_date, c.result, c.performed_by, c.next_calibration_date, c.notes
  FROM cal.calibrations c JOIN cal.tools t ON c.tool_id = t.id
  WHERE t.company_id = :cid
  AND (t.asset_tag ILIKE '%{{tool_ref}}%' OR t.tool_name ILIKE '%{{tool_ref}}%')
  ORDER BY c.calibration_date DESC

last_cal({{tool_ref}}):
  SELECT t.asset_tag, t.tool_name, c.performed_by, c.calibration_date, c.result
  FROM cal.calibrations c JOIN cal.tools t ON c.tool_id = t.id
  WHERE t.company_id = :cid
  AND (t.asset_tag ILIKE '%{{tool_ref}}%' OR t.tool_name ILIKE '%{{tool_ref}}%')
  ORDER BY c.calibration_date DESC LIMIT 1

by_vendor({{vendor_name}}):
  SELECT t.asset_tag, t.tool_name, c.calibration_date, c.result
  FROM cal.calibrations c JOIN cal.tools t ON c.tool_id = t.id
  WHERE t.company_id = :cid AND c.performed_by ILIKE '%{{vendor_name}}%'
  ORDER BY c.calibration_date DESC

email_log({{limit|10}}):
  SELECT from_address, subject, status, processing_result, received_at
  FROM cal.email_log WHERE company_id = :cid
  ORDER BY received_at DESC LIMIT {{limit}}

</QUERY_TEMPLATES>
```

---

### 術語映射 | Vocabulary → Column Mapping
```xml
<VOCAB note="Maps user speech to correct column + match pattern">
Equipment category → use tool_type (exact match preferred):
  "snap gage|snap gauge"    → tool_type = 'Snap Gage'
  "mic|micrometer"          → tool_type ILIKE '%Micrometer%'
  "caliper"                 → tool_type = 'Caliper'
  "bore gage|bore gauge"    → tool_type = 'Bore Gage'
  "gauss|gaussmeter"        → tool_type = 'Gaussmeter'
  "indicator"               → tool_type = 'Indicator'
  "height gage"             → tool_type = 'Height Gage'
  "pin gage"                → tool_type = 'Pin Gage'
  "thread gage"             → tool_type = 'Thread Gage'
  "ring gage"               → tool_type = 'Ring Gage'
  "gage block"              → tool_type = 'Gage Block Set'
  "scale|balance"           → tool_type = 'Scale'
  "hardness|durometer"      → tool_type = 'Hardness Tester'
  "force gage"              → tool_type = 'Force Gage'
  "probe"                   → tool_type = 'Probe'
  "surface plate|granite"   → tool_type = 'Surface Plate'

Equipment name detail → use tool_name ILIKE:
  "digital"                 → tool_name ILIKE '%digital%'
  "ceramic"                 → tool_name ILIKE '%ceramic%'
  specific range "0-1"      → tool_name ILIKE '%0.0-1.0%'

Calibration method → use calibration_method:
  "in-house|internal"       → calibration_method ILIKE '%In-House%'
  "vendor|external|outside" → calibration_method ILIKE '%Vendor%'

Status → use calibration_status:
  "due|expiring"            → calibration_status = 'expiring_soon'
  "overdue|expired|late"    → calibration_status = 'overdue'
  "current|good|up to date" → calibration_status = 'current'
</VOCAB>
```

---

### 业务规则 | Business Rules
```
escalation_path         := Quality Tech → Quality Manager → Plant Manager
critical_response_hours := 24
standard_response_days  := 5
audit_prep_lead_days    := 30
cert_retention_years    := 3 (minimum)
overdue_policy          := Remove from service immediately · no exceptions
gage_labels             := Green (current) · Yellow (expiring <30d) · Red (overdue/OOS)
alert_thresholds        := {warn_d: 30, critical_d: 7, overdue_d: 0}
```

---

### 品牌標識 | Branding
```
logo_file     := bunting-logo.png
primary_color := #003366
accent_color  := #CC0000
font          := Helvetica
line1 := "Bunting Magnetics Company"
line2 := "500 S. Spencer Ave."
line3 := "Newton, KS 67114"
phone := "(316) 284-2020"
web   := "bfrgroup.com"
report_footer := "Confidential — Bunting Magnetics Quality Department"
```

---

### 注意事項 | Special Notes
```
# Gaussmeters are business-critical — always flag if overdue
# Snap gages are the highest-volume category — collect in batches for vendor pickup
# Brandon handles day-to-day cal coordination, Ryan is management escalation
# Building/location data may be sparse — don't assume if not in records
# Some legacy tools have manufacturer-assigned asset_tags, not internal IDs
```
