# Vendor Portal & Purchase Automation System (`vendor_portal`)

A production-grade Frappe custom app that extends ERPNext's purchasing workflow with automated vendor onboarding, intelligent purchase validation, supplier performance scoring, background automation, and executive reporting — built without modifying ERPNext core code.

Developed as part of the **Sanskar Developer Training Program - Month 3 Practical Assessment**.

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

## Day 1 Implementation Summary (Section 3.1)

### 1. Custom DocTypes
- **Vendor Category (`vendor_category`)**: Master for categorizing suppliers with minimum rating thresholds, default payment terms, and active status. Autonamed by `category_name`.
- **Vendor Document (`vendor_document`)**: Child table for verification documents (GST Certificate, PAN Card, Bank Statement, etc.) with attachment and verification status.
- **Vendor Onboarding (`vendor_onboarding`)**: Submittable document capturing supplier credentials, tax details, bank info, address, contacts, and verification documents (`VOB-.YYYY.-.#####`).
- **Vendor Rating Log (`vendor_rating_log`)**: Performance log capturing ratings (1.0 to 5.0) across Delivery, Quality, Pricing, and Communication dimensions (`VRL-.YYYY.-.#####`).
- **Vendor Portal Settings (`vendor_portal_settings`)**: Single DocType for system configuration, including rating weights, threshold levels, and required documents.

### 2. ERPNext Supplier Extension & Fixtures
The standard ERPNext `Supplier` DocType has been augmented with custom fields:
- `vendor_category` (Link to Vendor Category)
- `vendor_rating` (Rating 1–5, auto-calculated)
- `total_rating_count` (Int, read-only)
- `onboarding_reference` (Link to Vendor Onboarding, read-only)
- `is_blacklisted` (Check)
- `blacklist_reason` (Small Text, conditionally visible when blacklisted)

All custom fields, workflow states, workflow action masters, and workflows are exported as upgrade-safe **fixtures** in `vendor_portal/fixtures/`.

### 3. Controller Overrides vs. Hooks
- **Purchase Order (`override_doctype_class`)**:
  - `CustomPurchaseOrder` extends ERPNext `PurchaseOrder`.
  - Always calls `super()` first to preserve standard core ERPNext logic.
  - Prevents creation of POs for blacklisted suppliers with custom error and reason.
  - Prevents creation of POs if supplier rating is below the category threshold.
  - On submit: auto-creates `Pricing` rating log comparing PO value against historical averages.
  - On cancel: deletes linked `Pricing` rating log and recalculates score.
- **Purchase Receipt (`doc_events`)**:
  - `validate`: flags short deliveries where `qty < 0.9 * ordered_qty` and records audit comments.
  - `on_submit`: auto-creates `Delivery` rating log evaluating timeliness and delivery completeness.

---

## Day 2 Implementation Summary (Section 3.2)

### 1. Client Scripts & Form Customizations
- **Purchase Order Form Override (`purchase_order.js`)**:
  - Dynamically renders supplier category, rating stars, and rating count via `frm.dashboard.set_headline()`.
  - Displays red banner and disables Save button (`frm.disable_save()`) if supplier is blacklisted.
  - "View Vendor Rating History" item under the Actions menu rendering an interactive table dialog.
  - "Rate This Supplier" custom button (visible after submission) to rate vendors interactively.
  - "Compare Suppliers" action invoking the side-by-side comparative matrix dialog.
- **Supplier Form Override (`supplier.js`)**:
  - Injected dashboard metric cards for Total POs, Total PO Value, Average Rating, and Total Ratings.
  - "Blacklist Supplier" prompt action (restricted to Purchase/Vendor Managers) and "Remove Blacklist" action.
  - "View Onboarding" action button navigating to linked onboarding records.
  - Form indicator displaying `Low Rating — Review Required` when rating is below the configured threshold.

### 2. JavaScript Desk Overrides (`vendor_portal.js`)
- **Purchase Order List View Indicators**:
  - `Completed` (Green): `per_received >= 100` or status `Completed`.
  - `Overdue` (Red): `schedule_date` passed with `per_received < 100`.
  - `To Receive` (Orange): `status == "To Receive"` or `per_received < 100`.
  - Injected action item and context menu for "Quick Rate Supplier".
- **Purchase Invoice Banner**:
  - Advisory warning headline when a supplier's rating drops below 3.0 stars.
- **Print Format Filtering**:
  - Automatically filters print formats so only `Vendor Purchase Order` and relevant formats are suggested.

### 3. Core Whitelisted APIs (`api.py`)
- `get_vendor_dashboard(supplier)`: Full metrics payload (POs, PRs, PIs, rating breakdown, recent ratings).
- `submit_vendor_rating(supplier, rating_type, score, remarks, ...)`: Creates rating and recalculates weighted average.
- `get_supplier_comparison(item_code, qty)`: Side-by-side comparative analysis of suppliers for an item.
- `get_onboarding_status_summary()`: Aggregated counts for onboarding pipeline and recent submissions.
- `get_vendor_rating_history(supplier)`: Chronological rating logs for form dialogs.

### 4. Permissions & Role-Based Access Control
- Custom Roles: `Vendor Manager` and `Purchase Team`.
- `has_permission` hooks enforcing that users with `Purchase Team` can only edit their own rating records, while `Vendor Manager` and `System Manager` have full read/write/delete capabilities.
- `permission_query_conditions` filtering rating log list queries.

---

## Day 3 Implementation Summary (Section 3.3)

### 1. Scheduled Background Automation (`tasks.py`)
- **Daily (`recalculate_all_vendor_ratings`)**: Recalculates weighted ratings across all suppliers and synchronizes ERPNext Supplier Scorecards. Sends email alerts to Vendor Managers if any vendor drops below their category threshold.
- **Hourly (`auto_rate_deliveries`)**: Identifies recently submitted Purchase Receipts and automatically logs Delivery ratings based on schedule date and accepted quantity.
- **Weekly (`send_weekly_vendor_digest`)**: Sends an executive summary report to Vendor Managers detailing Top 5 vendors, Bottom 5 vendors, total PO spend, and vendors requiring attention.
- **Cron (`auto_expire_stale_onboardings`)**: Runs every Monday at midnight (`0 0 * * 1`) to flag or reject onboarding applications pending for over 30 days without review.

### 2. Data Migration Patches (`vendor_portal/patches/v1_0/`)
- `populate_vendor_category_on_suppliers.py`: Assigns existing suppliers without category to the default "Raw Materials" category.
- `recalculate_vendor_ratings.py`: Iterates through all suppliers and recalculates their overall rating from rating logs.
- `migrate_supplier_notes_to_rating_logs.py`: Parses historical supplier comments and migrates legacy ratings into structured `Vendor Rating Log` records.

### 3. Executive Script Reports
- **Vendor Performance Report**: Comprehensive tabular report combining Suppliers, PO volume, PR completion, and rating dimensions with interactive charts.
- **Purchase Analysis by Vendor Category**: Aggregated spending, item count, and vendor distribution per category with bar chart visualization.

### 4. Custom Print Format (`Vendor Purchase Order`)
- Professional Jinja print format rendering corporate branding, GSTIN, PAN, items table, and visual star ratings via custom Jinja filter `star_rating`.

---

## Section 4: Bonus Tasks Implementation (All 5 Implemented)

### Bonus Task 1: Vendor Self-Service Portal
Public-facing web pages enabling prospective vendors to register and monitor onboarding progress without Desk access:
- **Registration Portal (`/vendor-register`)**:
  - Accessible to guests at `/vendor-register` and `/vendor_register`.
  - Captures company details, tax identifiers (GSTIN, PAN), banking information (account number, IFSC code), and addresses.
  - Automatically derives PAN from GSTIN client-side.
  - Submits to `@frappe.whitelist(allow_guest=True)` endpoint `register_vendor_web`.
  - Creates a `Vendor Onboarding` record in `Draft` status and displays a unique reference tracking ID.
- **Application Status Tracker (`/vendor-status`)**:
  - Accessible at `/vendor-status` and `/vendor_status`.
  - Prospective vendors can query their application status using Application Reference ID (`VOB-...`), GSTIN, or email address.
  - Calls `check_vendor_status_web` to display real-time application status, review notes, rejection reasons, and linked ERPNext Supplier code once approved.

### Bonus Task 2: ERPNext Supplier Scorecard Integration
- Dedicated integration module in `vendor_portal/scorecard.py`:
  - Directly connects custom 1–5 star ratings to ERPNext's native `Supplier Scorecard` and `Supplier Scorecard Standing` mechanism.
  - Maps vendor ratings to a 0–100% standing score:
    - **80% – 100%**: `Excellent` (Green, uninhibited purchasing).
    - **50% – 80%**: `Average` (Orange, standard purchasing).
    - **30% – 50%**: `Poor` (Red, `warn_pos=1`).
    - **0% – 30%** or Blacklisted: `Very Poor` (Red, `prevent_pos=1`, `warn_pos=1`).
  - Automatically updates `Supplier` document flags (`prevent_pos`, `warn_pos`), activating ERPNext's built-in purchase prevention and warning mechanisms.
  - Automatically hooked into `recalculate_vendor_rating` in `utils.py`, `on_supplier_update` in `events.py`, and scheduled jobs in `tasks.py`.

### Bonus Task 3: Vendor Analytics Dashboard Page (`/app/vendor-dashboard`)
Custom Desk Page (`vendor_dashboard`) featuring real-time KPI metrics and 4 interactive Frappe Charts:
1. **Vendor Rating Distribution (Histogram / Bar)**: Visualizes vendor count across 1 to 5 star rating brackets.
2. **Onboarding Pipeline (Funnel / Bar)**: Real-time count of applications across Draft, Under Review, Approved, and Rejected stages.
3. **PO Volume by Vendor Category (Bar)**: Spend distribution and financial volume per supplier category.
4. **Delivery Performance Trend (Line)**: Six-month trendline of monthly average delivery timeliness and accuracy percentages.
- Includes quick-action buttons for "Compare Suppliers" and "Bulk Import".

### Bonus Task 4: Bulk Vendor Import
- **API Endpoint (`bulk_vendor_import`)**:
  - Accepts raw CSV content or uploaded file URL (`File` doctype).
  - Validates required fields, formats GSTIN/PAN, and creates `Vendor Onboarding` records in bulk.
  - Supports synchronous execution for small batches and asynchronous queuing via `frappe.enqueue("vendor_portal.tasks.process_bulk_vendor_import", ...)` for scalable background execution.
  - Implements periodic database commits (`frappe.db.commit()` every 10 records) to maintain database stability and avoid lock escalations.
- Accessible directly via the Desk UI modal on the Vendor Dashboard.

### Bonus Task 5: Vendor Comparison Matrix
- **Interactive UI Dialog (`show_vendor_comparison_dialog`)**:
  - Accessible from the Purchase Order form (Actions menu) and the Vendor Dashboard.
  - Allows procurement officers to select any Item and input required quantity.
  - Calls `get_supplier_comparison(item_code, qty)` and renders a comparative side-by-side matrix:
    - Supplier Name with direct link
    - Star Rating and numeric score
    - On-Time Delivery Rate badge
    - Last Purchase Price
    - Recent Pricing History pills
    - Estimated Total cost for the requested quantity
    - "Select Supplier" action button that automatically sets the chosen supplier on the Purchase Order form.

---

## Section 7: Important Notes & Best Practices Adherence

Throughout the entire development lifecycle, the implementation strictly adheres to production-grade Frappe & ERPNext standards:

1. **Zero Core Modifications**:
   - 100% of custom logic, schemas, and overrides reside strictly within `apps/vendor_portal`. Not a single line of ERPNext or Frappe core code was modified.
2. **Controller Overrides with `super()`**:
   - `CustomPurchaseOrder` always calls `super().validate()` and `super().on_submit()` to ensure all native ERPNext validations and GL/Stock hooks execute undisturbed.
3. **Architectural Separation**:
   - `override_doctype_class` was selected for deep purchasing business logic (Purchase Order), while `doc_events` was utilized for receipt short-delivery audits to maximize upgrade safety.
4. **100% Parameterized SQL Queries**:
   - Every raw database query uses strictly parameterized arguments (`frappe.db.sql(..., (values,))` or dictionary binding `%(key)s`), completely eliminating SQL injection risks.
5. **Localization & Translations**:
   - All user-facing error messages, alerts, labels, and notifications are wrapped in `_()`.
6. **Exception Handling & Error Logging**:
   - All whitelisted APIs and scheduled background tasks wrap execution in `try ... except` blocks and log failures using `frappe.log_error(title="Context")` and `frappe.logger("vendor_portal")`.
7. **Background Job Commit Hygiene**:
   - Bulk background processes (`process_bulk_vendor_import`, `recalculate_all_vendor_ratings`) issue periodic `frappe.db.commit()` calls to prevent transaction timeouts and maintain data integrity.
8. **Asynchronous Task Offloading**:
   - Heavy operations exceeding a few seconds are offloaded to background workers via `frappe.enqueue()`.
9. **Server-Side Authority**:
   - All business constraints (blacklist blocking, minimum rating checks, mandatory document requirements) are strictly enforced server-side. Client scripts are used purely for enhanced UX.

---

## Automated Test Results

The app includes an automated test suite covering all core requirements, APIs, role permissions, and bonus features:

```text
test_approve_creates_supplier (TestVendorOnboarding) ... ok
test_duplicate_gst_blocked (TestVendorOnboarding) ... ok
test_gst_validation_format (TestVendorOnboarding) ... ok
test_minimum_documents_required (TestVendorOnboarding) ... ok
test_pan_validation_format (TestVendorOnboarding) ... ok
test_reject_sets_reason (TestVendorOnboarding) ... ok
test_blacklisted_supplier_blocks_po (TestVendorPortalAPIAndFlows) ... ok
test_low_rating_blocks_po (TestVendorPortalAPIAndFlows) ... ok
test_permission_own_ratings_only (TestVendorPortalAPIAndFlows) ... ok
test_po_cancel_deletes_rating (TestVendorPortalAPIAndFlows) ... ok
test_po_submit_creates_pricing_rating (TestVendorPortalAPIAndFlows) ... ok
test_pr_submit_creates_delivery_rating (TestVendorPortalAPIAndFlows) ... ok
test_supplier_comparison_api (TestVendorPortalAPIAndFlows) ... ok
test_vendor_rating_recalculation (TestVendorPortalAPIAndFlows) ... ok
test_get_onboarding_status_summary_api (TestDay2) ... ok
test_get_supplier_comparison_api (TestDay2) ... ok
test_get_vendor_dashboard_api (TestDay2) ... ok
test_get_vendor_rating_history_api (TestDay2) ... ok
test_print_format_rendering (TestDay2) ... ok
test_role_based_permission_hooks (TestDay2) ... ok
test_star_rating_filter (TestDay2) ... ok
test_submit_vendor_rating_api (TestDay2) ... ok
test_bonus_1_web_status_check (TestBonusTasks) ... ok
test_bonus_1_web_vendor_registration (TestBonusTasks) ... ok
test_bonus_2_scorecard_sync (TestBonusTasks) ... ok
test_bonus_3_dashboard_page_data (TestBonusTasks) ... ok
test_bonus_4_bulk_vendor_import_async_queue (TestBonusTasks) ... ok
test_bonus_4_bulk_vendor_import_sync (TestBonusTasks) ... ok
test_bonus_5_vendor_comparison_matrix (TestBonusTasks) ... ok

----------------------------------------------------------------------
Ran 29 tests in 1.168s
OK (Total tests run: 29, Errors: 0, Failures: 0)
```

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

## Submission Checklist Verification

- [x] All custom DocTypes (4 + 1 child table + 1 single) created and accessible
- [x] Custom Fields on Supplier exported as fixtures and restorable
- [x] Vendor Onboarding lifecycle: Draft -> Submit -> Approve -> Supplier created
- [x] Vendor Onboarding Workflow with correct state transitions
- [x] `override_doctype_class` on Purchase Order: blacklist check, rating check, auto-rating
- [x] `doc_events` on Purchase Receipt: short delivery detection, delivery rating
- [x] Client scripts on PO form: vendor info display, rating dialog, blacklist warning
- [x] Client scripts on Supplier form: dashboard stats, blacklist button
- [x] JS overrides: PO list view indicators, PI banner, print format filter
- [x] All whitelisted APIs return correct data with structured error handling
- [x] 2 custom roles with proper permissions configured and tested
- [x] `has_permission` and `permission_query_conditions` working
- [x] All 4 background jobs registered and working
- [x] `hooks.py` complete: doc_events, override, scheduler, fixtures, app_include, jinja, website routes
- [x] 2 Script Reports with filters, SQL JOINs, and charts
- [x] Custom Print Format with star rating and vendor info
- [x] All 3 patches in `patches.txt`, executed via `bench migrate`
- [x] All 29 unit tests pass (100% pass rate)
- [x] Bonus Task 1: Vendor Self-Service Portal (`/vendor-register`, `/vendor-status`)
- [x] Bonus Task 2: ERPNext Supplier Scorecard Integration & Standing Sync
- [x] Bonus Task 3: Custom Desk Page `vendor_dashboard` with 4 charts
- [x] Bonus Task 4: Bulk Vendor Import via `frappe.enqueue` with batch DB commits
- [x] Bonus Task 5: Interactive Vendor Comparison Matrix Dialog
- [x] Section 7 Best Practices audited and fully satisfied
- [x] `README.md` documents architecture, trade-offs, and verification steps
- [x] Code committed to Git with conventional commits (11+ commits)
- [x] App installs and migrates cleanly on fresh site

---

## License
MIT
