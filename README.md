# Vendor Portal & Purchase Automation System (`vendor_portal`)

A production-grade Frappe custom app that extends ERPNext's purchasing workflow with automated vendor onboarding, intelligent purchase validation, supplier performance scoring, background automation, and executive reporting — built strictly without modifying ERPNext core code.

Developed as part of the **Sanskar Developer Training Program - Month 3 Practical Assessment** for **Sanskar Technologies Pvt Ltd**.

---

## Table of Contents
1. [Installation & Setup Instructions](#installation--setup-instructions)
2. [Assumptions](#assumptions)
3. [Limitations](#limitations)
4. [Architecture Overview](#architecture-overview)
5. [Custom DocTypes Specification](#custom-doctypes-specification)
6. [ERPNext Overrides & Customizations (Which Approach Used Where & Why)](#erpnext-overrides--customizations-which-approach-used-where--why)
7. [Architectural Comparison: `override_doctype_class` vs `doc_events`](#architectural-comparison-override_doctype_class-vs-doc_events)
8. [Whitelisted APIs Reference (API Docs)](#whitelisted-apis-reference-api-docs)
9. [Client Scripts & JavaScript Desk Overrides](#client-scripts--javascript-desk-overrides)
10. [Role-Based Access Control & Security](#role-based-access-control--security)
11. [Background Automation & Scheduler Jobs](#background-automation--scheduler-jobs)
12. [Migration Patches & Fixtures](#migration-patches--fixtures)
13. [Script Reports & Print Formats](#script-reports--print-formats)
14. [Bonus Tasks Implementation (All 5 Implemented)](#bonus-tasks-implementation-all-5-implemented)
15. [Automated Verification & Test Instructions](#automated-verification--test-instructions)
16. [Section 5.2 Submission Checklist Verification](#section-52-submission-checklist-verification)
17. [Git Repository & Commit Conventions](#git-repository--commit-conventions)
18. [License](#license)

---

## Installation & Setup Instructions

Follow these step-by-step instructions to set up the app on any Frappe/ERPNext bench environment:

### Prerequisites
- Frappe Framework v16+ & ERPNext v16+ installed on Linux
- Python 3.12+ / 3.14+
- MariaDB 10.6+
- Node.js 18+

### Step 1: Clone & Install the App
```bash
# Navigate to your bench root directory
cd ~/frappe/vendor-bench

# Get the app into your bench apps directory
bench get-app /home/abhijit/frappe/vendor-bench/apps/vendor_portal

# Install the app onto your site
bench --site vendor.localhost install-app vendor_portal
```

### Step 2: Apply Database Migrations & Sync Fixtures
```bash
# Applies all schema updates, custom fields, print formats, roles, and workflows
bench --site vendor.localhost migrate
```

### Step 3: Seed Complete Master & Historical Demo Data
The app includes an automated seed script configuring `Sanskar Technologies Pvt Ltd` with realistic vendors, categories, purchase orders, purchase receipts, and rating logs across all dimensions:
```bash
bench --site vendor.localhost execute vendor_portal.setup_demo_data.setup_all
```

### Step 4: Run Automated Verification Tests
Execute the comprehensive test suite (30 unit tests covering DocTypes, controller overrides, doc_events, APIs, permissions, and bonus tasks):
```bash
bench --site vendor.localhost run-tests --app vendor_portal
```

---

## Assumptions

1. **Indian Taxation & Compliance Regimes**:
   - Primary tax identifier is **GSTIN** (Goods & Services Tax Identification Number), adhering to standard 15-character format (`^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`).
   - Primary national tax identity is **PAN** (Permanent Account Number), adhering to standard 10-character format (`^[A-Z]{5}[0-9]{4}[A-Z]{1}$`), which automatically matches characters 3 through 12 of the GSTIN.
2. **Enterprise Entity Context**:
   - The primary enterprise operating entity is **Sanskar Technologies Pvt Ltd**. All transactions, purchase workflows, and demo data operate within this corporate context.
3. **Currency & Financial Accounting**:
   - Base corporate accounting currency defaults to **INR (₹)** with full standard Frappe multi-currency support for foreign vendor purchase orders and receipts.
4. **Performance Scoring Scale**:
   - Supplier performance is measured on a continuous **1.0 to 5.0 Star scale** across four dimensions: Delivery (30%), Quality (30%), Pricing (20%), and Communication (20%).
   - Thresholds are configurable via the `Vendor Portal Settings` single DocType.
5. **Scorecard Integration**:
   - Vendor ratings normalize onto a 0–100% standing scale mapped to ERPNext native `Supplier Scorecard` standings (Excellent, Average, Poor, Very Poor), driving `prevent_pos` and `warn_pos` purchase order blocks.

---

## Limitations

1. **Direct Supplier Evaluation**:
   - Supplier item comparisons and rating calculations operate directly between the purchasing company (`Sanskar Technologies Pvt Ltd`) and the primary tier-1 vendor. Multi-tier subcontractor trees and tier-2 vendor tracking are not modeled.
2. **Bulk Import Format**:
   - The CSV import endpoint requires UTF-8 encoded CSV files matching standard column headers (`supplier_name`, `email`, `phone`, `vendor_category`, `gst_number`, `city`, `state`, `pincode`).
3. **Print Format PDF Generation**:
   - The `Vendor Purchase Order` print format is implemented using strict HTML table layouts and solid colors to guarantee rendering fidelity across both headless Chromium and wkhtmltopdf engines, avoiding modern CSS flexbox bugs in legacy PDF generators.
4. **Single Active Workflow**:
   - The `Vendor Onboarding Approval` workflow governs the `Vendor Onboarding` DocType. If an organization already has an active custom workflow on `Vendor Onboarding`, it must be merged or deactivated before installing.

---

## Architecture Overview

```
                                      +-------------------------------+
                                      |     Vendor Portal Settings    |
                                      +---------------+---------------+
                                                      |
                                                      v
+---------------------+     Submit      +-----------------------------+     Approve     +-----------------------+
|  Vendor Onboarding  | --------------> |  Under Review (Workflow)    | --------------> |   ERPNext Supplier    |
|    (Submittable)    |                 +-----------------------------+                 |   + Custom Fields     |
+---------------------+                                                                 +-----------+-----------+
                                                                                                    |
                                  +-----------------------------------------------------------------+
                                  |
                                  v
                    +-----------------------------+                 +-------------------------------+
                    |  CustomPurchaseOrder        |                 |   Purchase Receipt Hook       |
                    |  (override_doctype_class)   |                 |   (doc_events)                |
                    |                             |                 |                               |
                    |  - Blacklist validation     |                 |  - Short delivery detection   |
                    |  - Rating threshold check   |                 |  - Delivery rating auto-calc  |
                    |  - Auto pricing rating      |                 |  - On-time vs late scoring    |
                    +--------------+--------------+                 +---------------+---------------+
                                   |                                                |
                                   +-----------------------+------------------------+
                                                           |
                                                           v
                                            +------------------------------+
                                            |   Vendor Rating Log (VRL)    |
                                            |   - Delivery (30%)           |
                                            |   - Quality  (30%)           |
                                            |   - Pricing  (20%)           |
                                            |   - Comm.    (20%)           |
                                            +--------------+---------------+
                                                           |
                                                           v
                                            +------------------------------+
                                            | Weighted Rating Calculation  |
                                            | Updates Supplier rating & cnt|
                                            +--------------+---------------+
                                                           |
                                                           v
                                            +------------------------------+
                                            | ERPNext Supplier Scorecard   |
                                            | - Standings (0-100%)         |
                                            | - prevent_pos / warn_pos     |
                                            +------------------------------+
```

---

## Custom DocTypes Specification

The app creates **4 custom DocTypes**, **1 child table**, and **1 single DocType** under the `Vendor Portal` module, plus custom fields on ERPNext's standard `Supplier`:

| DocType Name | Nature | Primary Key / Naming | Purpose | Key Fields | Permissions |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Vendor Category** (`vendor_category`) | Master | `category_name` (e.g. `Raw Materials`) | Categorizes suppliers with operational thresholds and defaults | `category_name`, `min_rating_threshold`, `default_payment_terms`, `is_active`, `description` | Full: Vendor Manager; Read: Purchase Team |
| **Vendor Document** (`vendor_document`) | Child Table | Autoincrement / Hash | Stores compliance verification documents attached to an onboarding application | `document_type`, `document_name`, `attachment`, `verification_status`, `verified_by`, `verification_date` | Inherited from Vendor Onboarding |
| **Vendor Onboarding** (`vendor_onboarding`) | Submittable Transaction | `VOB-.YYYY.-.#####` | Governs the end-to-end lifecycle of onboarding new vendors | `vendor_name`, `vendor_category`, `email`, `phone`, `gst_number`, `pan_number`, `bank_name`, `bank_account_no`, `bank_ifsc`, `address_line1`, `city`, `state`, `pincode`, `documents` (Child Table), `rejection_reason`, `rework_notes` | Workflow-driven: Purchase Team creates; Vendor Manager approves/rejects |
| **Vendor Rating Log** (`vendor_rating_log`) | Transaction Log | `VRL-.YYYY.-.#####` | Immutable record of performance ratings across 4 dimensions | `supplier`, `rating_type` (Delivery, Quality, Pricing, Communication), `score` (1.0–5.0), `rated_by`, `rating_date`, `purchase_order`, `purchase_receipt`, `remarks` | Purchase Team (own ratings); Vendor Manager (all) |
| **Vendor Portal Settings** (`vendor_portal_settings`) | Single | `Vendor Portal Settings` | System-wide configuration for rating weights, thresholds, and grace periods | `delivery_weight`, `quality_weight`, `pricing_weight`, `communication_weight`, `default_min_rating`, `stale_onboarding_days`, `auto_rate_delivery_tolerance` | Vendor Manager, System Manager |
| **Supplier** (ERPNext Core Extended) | Standard DocType | Supplier Name | Augments core Supplier master with vendor management data | `vendor_category` (Link), `vendor_rating` (Float/Rating), `total_rating_count` (Int), `onboarding_reference` (Link), `is_blacklisted` (Check), `blacklist_reason` (Small Text) | Managed via `custom_field.json` fixtures |

---

## ERPNext Overrides & Customizations (Which Approach Used Where & Why)

### 1. Purchase Order Controller Override (`override_doctype_class`)
- **Target**: `Purchase Order`
- **Controller**: `vendor_portal.overrides.purchase_order.CustomPurchaseOrder`
- **Registration**: Registered in `hooks.py` under `override_doctype_class`:
  ```python
  override_doctype_class = {
      "Purchase Order": "vendor_portal.overrides.purchase_order.CustomPurchaseOrder"
  }
  ```
- **Why `override_doctype_class` was selected**:
  - Purchase order validation requires intercepting core workflow methods (`validate`, `before_submit`, `on_submit`, `on_cancel`).
  - Strict subclassing enables calling `super().validate()` and `super().on_submit()` so that standard ERPNext validation, taxes, pricing rules, and GL entry checks run undisturbed.
  - Allows injecting deep business logic:
    1. **Blacklist Validation**: Blocks saving or submitting POs for blacklisted suppliers with custom descriptive error messages.
    2. **Rating Threshold Check**: Compares the supplier's average rating against the `min_rating_threshold` configured on their `Vendor Category` (or default in `Vendor Portal Settings`) and throws a validation error if below threshold.
    3. **Auto Pricing Rating**: On PO submission (`on_submit`), compares the PO's unit prices against historical 180-day purchase order item averages and creates an automated `Pricing` rating log.
    4. **Rating Cleanup**: On PO cancellation (`on_cancel`), automatically deletes any linked pricing rating logs and recalculates the supplier's weighted score.

### 2. Purchase Receipt Document Hook (`doc_events`)
- **Target**: `Purchase Receipt`
- **Handler**: `vendor_portal.overrides.purchase_receipt`
- **Registration**: Registered in `hooks.py` under `doc_events`:
  ```python
  doc_events = {
      "Purchase Receipt": {
          "validate": "vendor_portal.overrides.purchase_receipt.validate",
          "on_submit": "vendor_portal.overrides.purchase_receipt.on_submit",
      }
  }
  ```
- **Why `doc_events` was selected**:
  - Purchase Receipt validation is observational and additive (short-delivery audit and delivery timeliness calculation).
  - Multiple apps in an ERPNext deployment often need hooks on `Purchase Receipt` (e.g., quality inspection, batch tracking, logistics). Using `override_doctype_class` would prevent other apps from functioning.
  - Using `doc_events` provides 100% cooperative multi-app compatibility and upgrade safety across major ERPNext releases.
  - Injected logic:
    1. **Short Delivery Detection (`validate`)**: Detects when received quantity is less than 90% of the ordered PO quantity (`qty < 0.9 * ordered_qty`) and adds an automated audit comment to the document timeline.
    2. **Auto Delivery Rating (`on_submit`)**: Evaluates delivery timeliness against the linked PO's `schedule_date` and quantity completeness (awarding 5.0 for early/on-time complete deliveries, scaling down for delays > 3 days or short quantities), creating an automated `Delivery` rating log.

---

## Architectural Comparison: `override_doctype_class` vs `doc_events`

| Feature / Criteria | `override_doctype_class` | `doc_events` |
| :--- | :--- | :--- |
| **Mechanic** | Python class inheritance (`class CustomPO(PurchaseOrder)`) | Event-driven pub/sub callbacks |
| **Execution Order** | Controlled precisely by author (`super().validate()` first or last) | Hook runs alongside/after standard methods |
| **Internal Method Overrides** | Can override ANY internal/private method or lifecycle hook | Can only hook into standard trigger points (`validate`, `on_submit`, etc.) |
| **Multi-App Compatibility** | **High Collision Risk**: Only ONE app can override the controller class. If two apps define `override_doctype_class` for `Purchase Order`, the last one in `installed_apps` wins and overwrites the other! | **Safe & Cooperative**: Multiple apps can register hooks on the same document event without conflict. |
| **Upgrade Safety** | Fragile across major version upgrades if core class signatures, `__init__`, or internal methods change. | Highly upgrade-safe because it interacts only with high-level document lifecycle events. |
| **Access to Document State** | Direct `self` access; can modify instance variables and add helper methods. | Receives `(doc, method)` tuple; operates via public document API. |

---

## Whitelisted APIs Reference (API Docs)

All endpoints are registered with `@frappe.whitelist()` in `vendor_portal/api.py`.

### 1. `get_vendor_dashboard(supplier)`
Returns complete supplier analytics, purchase history, and rating breakdown.

- **Endpoint**: `/api/method/vendor_portal.api.get_vendor_dashboard`
- **Method**: `GET` / `POST`
- **Parameters**:
  - `supplier` *(string, required)*: Supplier name or ID.
- **Response Format**:
  ```json
  {
    "message": {
      "supplier": "Tata Steel Ltd",
      "vendor_category": "Raw Materials",
      "vendor_rating": 4.5,
      "total_rating_count": 12,
      "is_blacklisted": 0,
      "total_pos": 8,
      "total_po_value": 450000.0,
      "total_prs": 7,
      "total_invoiced": 420000.0,
      "rating_breakdown": {
        "Delivery": 4.6,
        "Quality": 4.8,
        "Pricing": 4.2,
        "Communication": 4.4
      },
      "recent_ratings": [
        {
          "name": "VRL-2026-00001",
          "rating_type": "Quality",
          "score": 5.0,
          "rated_by": "Administrator",
          "rating_date": "2026-11-18",
          "remarks": "Batch meets strict tensile strength tolerances"
        }
      ]
    }
  }
  ```
- **Example cURL**:
  ```bash
  curl -X POST "http://vendor.localhost/api/method/vendor_portal.api.get_vendor_dashboard" \
    -H "Authorization: token <api_key>:<api_secret>" \
    -d "supplier=Tata Steel Ltd"
  ```

---

### 2. `submit_vendor_rating(...)`
Creates a new `Vendor Rating Log` and automatically updates the supplier's weighted average rating and ERPNext scorecard standing.

- **Endpoint**: `/api/method/vendor_portal.api.submit_vendor_rating`
- **Method**: `POST`
- **Parameters**:
  - `supplier` *(string, required)*: Target supplier.
  - `rating_type` *(string, required)*: One of `Delivery`, `Quality`, `Pricing`, `Communication`.
  - `score` *(float, required)*: Float between `1.0` and `5.0`.
  - `remarks` *(string, optional)*: Review notes or feedback.
  - `purchase_order` *(string, optional)*: Linked PO name.
  - `purchase_receipt` *(string, optional)*: Linked PR name.
- **Response Format**:
  ```json
  {
    "message": {
      "status": "success",
      "rating_log": "VRL-2026-00015",
      "new_vendor_rating": 4.35,
      "total_rating_count": 13
    }
  }
  ```
- **Example cURL**:
  ```bash
  curl -X POST "http://vendor.localhost/api/method/vendor_portal.api.submit_vendor_rating" \
    -H "Authorization: token <api_key>:<api_secret>" \
    -d "supplier=Tata Steel Ltd&rating_type=Quality&score=4.5&remarks=Excellent surface finish"
  ```

---

### 3. `get_supplier_comparison(item_code, qty=1)`
Performs parameterized cross-supplier comparison for a specified item code, analyzing latest purchase rates, historical average rates, ratings, and delivery scores.

- **Endpoint**: `/api/method/vendor_portal.api.get_supplier_comparison`
- **Method**: `GET` / `POST`
- **Parameters**:
  - `item_code` *(string, required)*: ERPNext Item Code.
  - `qty` *(float, optional, default=1)*: Requested quotation quantity.
- **Response Format**:
  ```json
  {
    "message": [
      {
        "supplier": "Tata Steel Ltd",
        "vendor_rating": 4.5,
        "delivery_score": 4.6,
        "last_purchase_rate": 850.0,
        "avg_purchase_rate": 862.5,
        "total_qty_ordered": 2500,
        "lead_time_days": 5,
        "is_blacklisted": 0
      }
    ]
  }
  ```
- **Example cURL**:
  ```bash
  curl -X POST "http://vendor.localhost/api/method/vendor_portal.api.get_supplier_comparison" \
    -H "Authorization: token <api_key>:<api_secret>" \
    -d "item_code=STEEL-ROD-10MM&qty=100"
  ```

---

### 4. `get_onboarding_status_summary()`
Returns aggregated counts across all onboarding workflow states and the 10 most recent submissions for executive KPI dashboards.

- **Endpoint**: `/api/method/vendor_portal.api.get_onboarding_status_summary`
- **Method**: `GET` / `POST`
- **Parameters**: None.
- **Response Format**:
  ```json
  {
    "message": {
      "total_pending": 8,
      "total_approved": 35,
      "total_rejected": 6,
      "total_rework": 4,
      "recent_submissions": [
        {
          "name": "VOB-2026-00053",
          "vendor_name": "Apex Fasteners",
          "vendor_category": "Hardware",
          "workflow_state": "Under Review",
          "creation": "2026-11-20 06:15:00"
        }
      ]
    }
  }
  ```

---

### 5. `get_vendor_rating_history(supplier)`
Fetches chronological rating history for dialog popups on Purchase Orders and Suppliers.

- **Endpoint**: `/api/method/vendor_portal.api.get_vendor_rating_history`
- **Parameters**: `supplier` *(string, required)*.

---

### 6. Bonus API Endpoints
- **`bulk_vendor_import`**: Accepts raw CSV or file path. Supports synchronous processing or asynchronous queuing via `frappe.enqueue("vendor_portal.tasks.process_bulk_vendor_import", ...)` with batch DB commits every 10 records.
- **`register_vendor_web`** (`allow_guest=True`): Public endpoint powering `/vendor-register`.
- **`get_vendor_onboarding_status`** (`allow_guest=True`): Public status lookup powering `/vendor-status`.

---

## Client Scripts & JavaScript Desk Overrides

### 1. Purchase Order Form Override (`purchase_order.js`)
- Dynamically renders supplier category, rating stars, and rating count via `frm.dashboard.set_headline()`.
- Displays red banner and disables Save button (`frm.disable_save()`) if supplier is blacklisted.
- "View Vendor Rating History" item under the Actions menu rendering an interactive table dialog.
- "Rate This Supplier" custom button (visible after submission) to rate vendors interactively.
- "Compare Suppliers" action invoking the side-by-side comparative matrix dialog.

### 2. Supplier Form Override (`supplier.js`)
- Injected dashboard metric cards for Total POs, Total PO Value, Average Rating, and Total Ratings.
- "Blacklist Supplier" prompt action (restricted to Purchase/Vendor Managers) and "Remove Blacklist" action.
- "View Onboarding" action button navigating to linked onboarding records.
- Form indicator displaying `Low Rating — Review Required` when rating is below the configured threshold.

### 3. JavaScript Desk Overrides (`vendor_portal.js` via `app_include_js`)
- **Purchase Order List View Indicators**:
  - `Completed` (Green): `per_received >= 100` or status `Completed`.
  - `Overdue` (Red): `schedule_date` passed with `per_received < 100`.
  - `To Receive` (Orange): `status == "To Receive"` or `per_received < 100`.
  - Injected action item and context menu for "Quick Rate Supplier".
- **Purchase Invoice Banner**:
  - Advisory warning headline when a supplier's rating drops below 3.0 stars.
- **Print Format Filtering**:
  - Automatically filters print formats so only `Vendor Purchase Order` and relevant formats are suggested.

---

## Role-Based Access Control & Security

### 1. Custom Roles
- **`Vendor Manager`**: Full CRUD + Submit/Cancel on Vendor Onboarding, Vendor Rating Log, and Vendor Category. Has permission to blacklist/un-blacklist suppliers and full access to executive reports.
- **`Purchase Team`**: Can create and submit Vendor Onboarding records for review. Can create Vendor Rating Logs. Read-only on Vendor Category and Vendor Portal Settings.

### 2. Scripted Permission Hooks
- **`has_permission` (`vendor_portal.permissions.has_rating_log_permission`)**:
  - Registered on `Vendor Rating Log`.
  - Regular users (`Purchase Team`) can only edit or cancel rating logs that they authored (`doc.rated_by == frappe.session.user`).
  - Users with `Vendor Manager` or `System Manager` retain full edit and delete permissions.
- **`permission_query_conditions` (`vendor_portal.permissions.get_onboarding_permission_conditions`)**:
  - Registered on `Vendor Onboarding`.
  - Filters list views and database queries so users with only `Purchase Team` see exclusively their own submitted onboardings (`owner = '{user}'`).
  - Vendor Managers and System Managers see all records.

### 3. Verified Demo Users
| User Email | Assigned Roles | Access Capability |
| :--- | :--- | :--- |
| `vendor_mgr@test.com` | `Vendor Manager`, `Purchase Manager` | Full administrative review, approve/reject, blacklist suppliers, see all submissions |
| `purchase_user@test.com` | `Purchase Team`, `Purchase User` | Operational onboarding submission, view own submissions, rate suppliers |

---

## Background Automation & Scheduler Jobs

Configured in `vendor_portal/tasks.py` and registered under `scheduler_events` in `hooks.py`:

```python
scheduler_events = {
    "hourly": [
        "vendor_portal.tasks.auto_rate_deliveries",
    ],
    "daily": [
        "vendor_portal.tasks.auto_calculate_vendor_ratings",
    ],
    "weekly": [
        "vendor_portal.tasks.send_vendor_performance_digest",
    ],
    "cron": {
        "0 9 * * *": [
            "vendor_portal.tasks.auto_expire_stale_onboardings",
        ]
    },
}
```

1. **Daily (`auto_calculate_vendor_ratings`)**:
   - Recalculates weighted averages across all suppliers from historical logs.
   - Updates `vendor_rating` and `total_rating_count` on `Supplier`.
   - Synchronizes ERPNext native `Supplier Scorecard` standings.
   - Automatically dispatches email notifications to Vendor Managers if any vendor drops below threshold.
2. **Hourly (`auto_rate_deliveries`)**:
   - Queries newly submitted Purchase Receipts.
   - Automatically computes on-time delivery score and completeness, inserting automated `Delivery` rating logs.
3. **Weekly (`send_vendor_performance_digest`)**:
   - Compiles an executive digest email summarizing Top 5 vendors, Bottom 5 vendors, weekly PO spend, and pending onboarding queues.
4. **Cron (`auto_expire_stale_onboardings`)**:
   - Runs daily at 09:00 AM (`0 9 * * *`).
   - Identifies `Vendor Onboarding` applications remaining in `Draft` or `Under Review` beyond the threshold configured in `Vendor Portal Settings` (default 30 days) and marks them expired/rejected.

---

## Migration Patches & Fixtures

### 1. Patches in `patches.txt`
```
[post_model_sync]
vendor_portal.patches.v1_0.populate_vendor_category_on_suppliers
vendor_portal.patches.v1_0.recalculate_vendor_ratings
vendor_portal.patches.v1_0.migrate_supplier_notes_to_rating_logs
```
- **`populate_vendor_category_on_suppliers`**: Ensures all legacy suppliers have a valid `Vendor Category` assigned, defaulting to `Raw Materials`.
- **`recalculate_vendor_ratings`**: Iterates through existing suppliers and recalculates their ratings from all historical rating logs.
- **`migrate_supplier_notes_to_rating_logs`**: Migrates freeform legacy text comments on suppliers containing rating patterns into structured `Vendor Rating Log` documents.

### 2. Exported Fixtures (`fixtures/`)
All customizations are exported as upgrade-safe JSON fixtures:
- `custom_field.json`: 6 custom fields on `Supplier`.
- `role.json`: Custom roles (`Vendor Manager`, `Purchase Team`).
- `workflow.json`: Complete `Vendor Onboarding Approval` workflow.
- `workflow_state.json`: States (`Draft`, `Under Review`, `Approved`, `Rejected`, `Rework`).
- `workflow_action_master.json`: Actions (`Submit for Review`, `Approve`, `Reject`, `Resubmit`, `Request Rework`).
- `print_format.json`: `Vendor Purchase Order` Jinja template.

---

## Script Reports & Print Formats

### 1. Vendor Performance Report
- **Module**: `Vendor Portal`
- **Location**: `vendor_portal/report/vendor_performance_report/`
- **Features**:
  - Filterable by `Supplier`, `Vendor Category`, `From Date`, `To Date`, and `Status`.
  - Multi-table SQL JOIN across `tabSupplier`, `tabVendor Rating Log`, and `tabPurchase Order`.
  - Formatted Star ratings and compliance badges.
  - Interactive bar chart comparing delivery vs quality scores per vendor.

### 2. Purchase Analysis by Vendor Category
- **Module**: `Vendor Portal`
- **Location**: `vendor_portal/report/purchase_analysis_by_vendor_category/`
- **Features**:
  - Aggregates total purchase orders, net spend, average order value, and vendor count per category.
  - 100% parameterized SQL query with group-by aggregation.
  - Pie/Donut chart visualizing category spend distribution.

### 3. Custom Print Format (`Vendor Purchase Order`)
- **Format**: Jinja2 + HTML (Table layout optimized for Chromium headless & wkhtmltopdf).
- **Branding**: Includes corporate header, GSTIN, PAN, items breakdown, and "Vendor Portal" watermark.
- **Dynamic Jinja Filters**:
  - Utilizes custom Jinja filter `star_rating` (`{{ doc.vendor_rating | star_rating }}`) to render gold Unicode star glyphs (★).
  - Displays red warning banner (`"Caution: Low-rated vendor"`) if `vendor_rating < 3.0`.

---

## Bonus Tasks Implementation (All 5 Implemented)

### Bonus Task 1: Vendor Self-Service Portal
Public-facing web pages enabling prospective vendors to register and monitor onboarding progress without Desk access:
- **Registration Portal (`/vendor-register`)**:
  - Captures company details, tax identifiers (GSTIN, PAN), banking information (account number, IFSC code), and addresses.
  - Automatically derives PAN from GSTIN client-side.
  - Submits to `@frappe.whitelist(allow_guest=True)` endpoint `register_vendor_web`.
  - Creates a `Vendor Onboarding` record in `Draft` status and returns a unique tracking ID.
- **Application Status Tracker (`/vendor-status`)**:
  - Allows applicants to look up their real-time application status using their registered email and reference number without logging into Desk.

### Bonus Task 2: ERPNext Supplier Scorecard Integration
- Integrates custom rating logs with ERPNext's native `Supplier Scorecard` mechanism.
- Automatically maps 1.0–5.0 star ratings into standard 0–100% scorecard standings:
  - `Excellent` (Rating ≥ 4.5)
  - `Average` (3.5 ≤ Rating < 4.5)
  - `Poor` (2.5 ≤ Rating < 3.5) — Triggers `warn_pos`
  - `Very Poor` (Rating < 2.5) — Triggers `prevent_pos`

### Bonus Task 3: Vendor Analytics Dashboard Desk Page (`/app/vendor-dashboard`)
- Custom interactive Desk Page featuring 4 responsive Frappe charts:
  1. **Rating Distribution (Histogram)**: Categorizes vendors into rating tiers.
  2. **Onboarding Pipeline (Funnel/Bar)**: Real-time visual count of Draft, Under Review, Approved, Rejected, and Rework applications.
  3. **PO Volume by Vendor Category (Bar Chart)**: Total spend per category.
  4. **Delivery Performance Trend (Line Chart)**: Six-month trendline of monthly average delivery timeliness and accuracy.
- Action buttons for Quick Compare and Bulk Import directly within the dashboard.

### Bonus Task 4: Bulk Vendor Import
- **API Endpoint (`bulk_vendor_import`)**:
  - Accepts raw CSV content or uploaded file URL.
  - Validates required fields, formats GSTIN/PAN, and creates `Vendor Onboarding` records in bulk.
  - Supports synchronous execution for small batches and asynchronous queuing via `frappe.enqueue("vendor_portal.tasks.process_bulk_vendor_import", ...)` for scalable background execution.
  - Implements periodic database commits (`frappe.db.commit()` every 10 records) to maintain database stability and avoid lock escalations.

### Bonus Task 5: Vendor Comparison Matrix
- Interactive modal dialog accessible from Purchase Orders, Suppliers, and the Vendor Dashboard.
- Allows users to select an Item Code and immediately view side-by-side comparative pricing history, current ratings, delivery scores, and lead times across all competing suppliers.

---

## Automated Verification & Test Instructions

Run the complete automated test suite on your bench environment:

```bash
bench --site vendor.localhost run-tests --app vendor_portal
```

### Actual Test Suite Output (30 Tests Passing, 100% Success Rate)

```
Starting test run with parameters: site=vendor.localhost, app=vendor_portal, verbose=False, tests=(), force=False, profile=False, failfast=False, skip_before_tests=False, debug=False, selected_categories=[]
View detailed logs (using --verbose): /home/abhijit/frappe/vendor-bench/logs/frappe.testing.log

Running 30 old-frappe-test-class-category tests for vendor_portal

vendor_portal.tests.test_bonus.TestBonusTasks
    ✔  test_bonus_1_web_status_check
    ✔  test_bonus_1_web_vendor_registration
    ✔  test_bonus_2_scorecard_sync
    ✔  test_bonus_3_dashboard_page_data
    ✔  test_bonus_4_bulk_vendor_import_async_queue
    ✔  test_bonus_4_bulk_vendor_import_sync
    ✔  test_bonus_5_vendor_comparison_matrix
    ✔  test_rework_workflow_and_mandatory_remarks

vendor_portal.tests.test_api.TestVendorPortalAPIAndFlows
    ✔  test_blacklisted_supplier_blocks_po
    ✔  test_low_rating_blocks_po
    ✔  test_permission_own_ratings_only
    ✔  test_po_cancel_deletes_rating
    ✔  test_po_submit_creates_pricing_rating
    ✔  test_pr_submit_creates_delivery_rating
    ✔  test_supplier_comparison_api
    ✔  test_vendor_rating_recalculation

vendor_portal.tests.test_day2.TestDay2
    ✔  test_get_onboarding_status_summary_api
    ✔  test_get_supplier_comparison_api
    ✔  test_get_vendor_dashboard_api
    ✔  test_get_vendor_rating_history_api
    ✔  test_print_format_rendering
    ✔  test_role_based_permission_hooks
    ✔  test_star_rating_filter
    ✔  test_submit_vendor_rating_api

vendor_portal.vendor_portal.doctype.vendor_onboarding.test_vendor_onboarding.TestVendorOnboarding
    ✔  test_approve_creates_supplier
    ✔  test_duplicate_gst_blocked
    ✔  test_gst_validation_format
    ✔  test_minimum_documents_required
    ✔  test_pan_validation_format
    ✔  test_reject_sets_reason

----------------------------------------------------------------------
Ran 30 tests in 1.157s

OK (Total tests run: 30, Errors: 0, Failures: 0)
```

---

## Section 5.2 Submission Checklist Verification

All 22 items specified in **Section 5.2 (Submission Checklist)** of the assessment document are thoroughly verified and satisfied:

| # | Checklist Item from Assessment | Status | Implementation Details / Reference |
| :-: | :--- | :---: | :--- |
| **1** | All custom DocTypes (4 + 1 child table + 1 single) created and accessible | **DONE** [x] | `vendor_category`, `vendor_document`, `vendor_onboarding`, `vendor_rating_log`, `vendor_portal_settings` |
| **2** | Custom Fields on Supplier exported as fixtures and restorable | **DONE** [x] | 6 custom fields on `Supplier` exported in `fixtures/custom_field.json` |
| **3** | Vendor Onboarding lifecycle: Draft → Submit → Approve → Supplier created | **DONE** [x] | Verified by controller `on_update_after_submit` & unit test `test_approve_creates_supplier` |
| **4** | Vendor Onboarding Workflow with correct state transitions | **DONE** [x] | `Draft` → `Under Review` → `Approved` / `Rejected` / `Rework` governed by workflow |
| **5** | `override_doctype_class` on Purchase Order: blacklist check, rating check, auto-rating | **DONE** [x] | `CustomPurchaseOrder` in `overrides/purchase_order.py` with `super()` calls |
| **6** | `doc_events` on Purchase Receipt: short delivery detection, delivery rating | **DONE** [x] | In `overrides/purchase_receipt.py` hooks `validate` and `on_submit` |
| **7** | Client scripts on PO form: vendor info display, rating dialog, blacklist warning | **DONE** [x] | In `public/js/purchase_order.js`: headline stats, banner, disable save, dialogs |
| **8** | Client scripts on Supplier form: dashboard stats, blacklist button | **DONE** [x] | In `public/js/supplier.js`: dynamic metric cards, blacklist action buttons |
| **9** | JS overrides: PO list view indicators, PI banner, print format filter | **DONE** [x] | In `public/js/vendor_portal.js` loaded via `app_include_js` |
| **10** | All 4 whitelisted APIs return correct data | **DONE** [x] | `get_vendor_dashboard`, `submit_vendor_rating`, `get_supplier_comparison`, `get_onboarding_status_summary` |
| **11** | 2 custom roles with proper permissions configured and tested | **DONE** [x] | `Vendor Manager` and `Purchase Team` roles exported in fixtures and tested |
| **12** | `has_permission` and `permission_query_conditions` working | **DONE** [x] | `has_rating_log_permission` and `get_onboarding_permission_conditions` in `permissions.py` |
| **13** | All 4 background jobs registered and working | **DONE** [x] | Daily recalculation, Hourly deliveries, Weekly digest, Cron stale expiry in `tasks.py` |
| **14** | `hooks.py` complete: doc_events, override, scheduler, fixtures, app_include, jinja | **DONE** [x] | Fully configured and verified in `vendor_portal/hooks.py` |
| **15** | 2 Script Reports with filters, SQL JOINs, and charts | **DONE** [x] | `Vendor Performance Report` and `Purchase Analysis by Vendor Category` |
| **16** | Custom Print Format with star rating and vendor info | **DONE** [x] | `Vendor Purchase Order` with custom Jinja filter `star_rating` and watermark |
| **17** | All 3 patches in `patches.txt`, execute via `bench migrate` | **DONE** [x] | 3 patches in `patches.txt` execute idempotently via `bench migrate` |
| **18** | All 14+ unit tests pass | **DONE** [x] | **30 tests pass** (100% pass rate, exceeding the 14+ test requirement) |
| **19** | Sample data entered for all DocTypes and ERPNext records | **DONE** [x] | Seed script `setup_all` seeds 13 categories, 53 onboardings, 21 suppliers, 38 POs, 31 PRs, 64 rating logs |
| **20** | `README.md` documents override approaches with trade-offs | **DONE** [x] | Comprehensive comparison table and architectural rationale included |
| **21** | Code pushed to Git with meaningful commits (9+ commits) | **DONE** [x] | **30 conventional commits** following `feat:`, `fix:`, `docs:`, `test:`, `chore:` structure |
| **22** | App installs and migrates cleanly on a fresh ERPNext site | **DONE** [x] | Zero core modifications; clean dependencies, schema definitions, and fixtures |

### Bonus Deliverables Verification
- [x] **Bonus Task 1**: Vendor Self-Service Portal (`/vendor-register`, `/vendor-status`)
- [x] **Bonus Task 2**: ERPNext Supplier Scorecard Integration & Standing Sync
- [x] **Bonus Task 3**: Custom Desk Page `vendor_dashboard` with 4 interactive charts
- [x] **Bonus Task 4**: Bulk Vendor Import via `frappe.enqueue` with batch DB commits
- [x] **Bonus Task 5**: Interactive Vendor Comparison Matrix Dialog
- [x] **Section 7**: Best Practices audited (Parameterized SQL, Translations, Zero Core Edits)

---

## Git Repository & Commit Conventions

The repository follows the [Conventional Commits](https://www.conventionalcommits.org/) specification:
- `feat:` for new features and DocTypes
- `fix:` for bug fixes and SQL parameterization
- `docs:` for documentation and README updates
- `test:` for test suites and automated test cases
- `chore:` for maintenance, cleanup, and configuration

### Commit History (30 Commits, Branch: `version-16` / `main`)
```
b8099bb docs(readme): sync submission checklist, api docs, doctype specs, and fixture hooks
e29bb62 fix(quality): enhance api role checks, patch guards, table print layout, workflow dialogs, and docs
1a8143d test(workflow): add test cases for rework lifecycle and mandatory remarks
b4f582c feat(demo-data): add complete Sanskar Technolabs master data and historical transactions
c7c06ba feat(workspace): add Vendor Portal and Sanskar Operations workspaces
2461164 feat(workflow): add rework state with mandatory remarks on reject and rework
d1f52a9 docs: document bonus task deliverables, architecture trade-offs, and test results
52a02d1 test(bonus): add automated unit test suite for all bonus features
ad218c5 fix(reports): ensure 100% parameterized SQL query execution in purchase analysis report
393b617 feat(comparison-matrix): add interactive vendor comparison dialog on purchase order and dashboard
3d66c70 feat(bulk-import): add bulk vendor import background worker with batch commits
b2fe49a feat(dashboard): add vendor analytics desk page with 4 interactive frappe charts and kpis
27e05ab feat(scorecard): integrate vendor scoring with ERPNext native supplier scorecard standing mechanism
feab4da feat(web-portal): implement vendor self-service registration and status tracker pages
303c6dc test(vendor-portal): add complete unit test suite for onboarding, APIs and lifecycle flows
43ec50a feat(print-format): enhance PO print format with watermark branding and update documentation
7c65d89 feat(patches): add data migration patches for categories, ratings and comment migration
c05b563 feat(reports): add Vendor Performance and Purchase Analysis script reports
12e5726 feat(tasks): implement scheduled background automation and doc_events hooks
05bc113 feat(permissions): add role-based permissions, custom roles, permission hooks and test suite
9de8c10 feat(js-overrides): implement PO listview indicators, quick rate supplier dialog and PI warning banner
8134c8f feat(client-scripts): add standard form overrides for Purchase Order, Supplier and Vendor Onboarding
281b108 feat(api): implement whitelisted APIs for dashboard, ratings, supplier comparison and onboarding summary
857f814 docs: add comprehensive README with override trade-off analysis and architecture documentation
1dcbb16 feat(purchase-receipt): add doc_events hook for purchase receipt validation and delivery rating
13c0ceb feat(purchase-order): override purchase order controller with validation and auto-rating
3cf4778 feat(workflow): implement vendor onboarding controller and approval workflow
44d31c5 feat(custom-fields): add custom fields to supplier doctype and export fixtures
12e08ff feat(doctype): create vendor category, document, onboarding, rating log and settings doctypes
7679e61 feat: Initialize App
```

---

## License
MIT
