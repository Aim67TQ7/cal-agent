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
# Emails CC'd or forwarded here get auto-processed by Cal

vendor_emails := {
  # When Cal sees email FROM these addresses, classify as calibration-related
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
  snap_gages   → Go/no-go dimensional checks · most common category (~40 tools)
  micrometers  → Precision dimensional measurement · outside/inside/depth
  calipers     → Vernier/digital calipers · general dimensional
  bore_gages   → Internal diameter measurement
  gaussmeters  → Magnetic field strength measurement · CRITICAL for product QA
  indicators   → Dial indicators, test indicators
  height_gages → Precision height measurement
  scales       → Weighing scales and balances
  hardness     → Rockwell/Brinell hardness testers
  force_gages  → Push/pull force measurement
}

critical_equipment := {
  gaussmeters    → Core product verification — CANNOT ship without current cal
  hardness_tester → Material certification requirement
  CMM            → If present, complex calibration, 2-week lead time
}
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
```

---

### 典型问题·SQL映射 | Typical Questions → SQL Patterns
```
# These patterns help Cal construct accurate SQL queries for common Bunting questions

用户问 "what snap gages are due?" →
  SELECT number, description, next_due_date, calibration_status
  FROM cal.tools WHERE company_id = :cid
  AND type ILIKE '%snap%' AND (calibration_status = 'expiring_soon' OR calibration_status = 'overdue')
  ORDER BY next_due_date ASC

用户问 "show me all gaussmeters" →
  SELECT number, description, manufacturer, calibration_status, last_calibration_date, next_due_date
  FROM cal.tools WHERE company_id = :cid
  AND (type ILIKE '%gauss%' OR description ILIKE '%gauss%')
  ORDER BY number

用户问 "what's overdue?" →
  SELECT number, type, description, next_due_date, calibration_status
  FROM cal.tools WHERE company_id = :cid
  AND (calibration_status = 'overdue' OR (next_due_date IS NOT NULL AND next_due_date < CURRENT_DATE))
  ORDER BY next_due_date ASC

用户问 "compliance rate" / "how are we doing?" →
  SELECT calibration_status, COUNT(*) as cnt
  FROM cal.tools WHERE company_id = :cid
  GROUP BY calibration_status

用户问 "what's in building X?" / "what's on the floor?" →
  SELECT number, type, description, location, building, calibration_status
  FROM cal.tools WHERE company_id = :cid
  AND (location ILIKE '%{user_term}%' OR building ILIKE '%{user_term}%')
  ORDER BY type, number

用户问 "calibration history for [tool]" →
  SELECT c.calibration_date, c.result, c.technician, c.next_due_date, c.comments
  FROM cal.calibrations c JOIN cal.tools t ON c.tool_id = t.id
  WHERE t.company_id = :cid AND (t.number ILIKE '%{tool_ref}%' OR t.description ILIKE '%{tool_ref}%')
  ORDER BY c.calibration_date DESC

用户问 "who calibrated [tool] last?" →
  SELECT t.number, c.technician, c.calibration_date, c.result
  FROM cal.calibrations c JOIN cal.tools t ON c.tool_id = t.id
  WHERE t.company_id = :cid AND t.number ILIKE '%{tool_ref}%'
  ORDER BY c.calibration_date DESC LIMIT 1

用户问 "what did we get from [vendor]?" →
  SELECT t.number, t.type, c.calibration_date, c.result, c.technician
  FROM cal.calibrations c JOIN cal.tools t ON c.tool_id = t.id
  WHERE t.company_id = :cid AND c.technician ILIKE '%{vendor_name}%'
  ORDER BY c.calibration_date DESC

用户问 "how many tools do we have?" →
  SELECT type, COUNT(*) as cnt FROM cal.tools
  WHERE company_id = :cid GROUP BY type ORDER BY cnt DESC

用户问 "what needs to go out this month?" →
  SELECT number, type, description, next_due_date
  FROM cal.tools WHERE company_id = :cid
  AND next_due_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '30 days')
  ORDER BY next_due_date ASC

用户问 "any emails about calibration?" →
  SELECT from_address, subject, status, processing_result, received_at
  FROM cal.email_log WHERE company_id = :cid
  ORDER BY received_at DESC LIMIT 10
```

---

### 术语 | Tenant Vocabulary
```
# Bunting-specific terms and informal names
"snap gage"    = type ILIKE '%snap%'
"mic"          = type ILIKE '%micrometer%'
"digital"      = description ILIKE '%digital%'
"indicator"    = type ILIKE '%indicator%'
"bore gage"    = type ILIKE '%bore%'
"caliper"      = type ILIKE '%caliper%'
"gauss meter"  = type ILIKE '%gauss%' OR description ILIKE '%gauss%'
"pin gage"     = type ILIKE '%pin%'
"thread gage"  = type ILIKE '%thread%'
"height gage"  = type ILIKE '%height%'
"ring gage"    = type ILIKE '%ring%'
"scale"        = type ILIKE '%scale%' OR type ILIKE '%balance%'
```

---

### 品牌标识 | Branding
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

### 注意事项 | Special Notes
```
# Gaussmeters are business-critical — always flag if overdue
# Snap gages are the highest-volume category — collect in batches for vendor pickup
# Brandon handles day-to-day cal coordination, Ryan is management escalation
# Building/location data may be sparse — don't assume if not in records
# Some legacy tools have manufacturer-assigned numbers, not internal IDs
```
