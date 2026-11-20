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
- **Supplier Form Override (`supplier.js`)**:
  - Injected dashboard metric cards for Total POs, Total PO Value, Average Rating, and Total Ratings.
  - "Blacklist Supplier" prompt action (restricted to Purchase/Vendor Managers) and "Remove Blacklist" action.
  - "View Onboarding" action button navigating to linked onboarding records.
  - Form indicator displaying `Low Rating — Review Required` when rating is below the configured threshold.
- **Vendor Onboarding Form Script (`vendor_onboarding.js`)**:
  - "Approve" and "Reject" buttons for Purchase/Vendor Managers when status is Under Review.
  - Auto-fetches and displays `minimum_rating_threshold` dynamically on category selection.
  - Client-side regex format checks for Indian GSTIN and PAN numbers.
  - Live progress banner tracking verified child table documents (`X of Y documents verified`).

### 2. Global JS Overrides (`vendor_portal.js`)
- **Purchase Order List View Overrides**:
  - Configured custom color indicators: Green (Completed), Orange (To Receive), Red (Overdue).
  - Added "Quick Rate Supplier" action item and right-click context menu integration.
  - Extended list view columns: `supplier_name`, `grand_total`, `per_received`, `status`.
- **Purchase Invoice Warning Banner**:
  - Hooks into Purchase Invoice refresh event.
  - Displays an advisory warning banner when a supplier's rating is `< 3.0`.

### 3. Whitelisted APIs (`api.py`)
- `get_vendor_dashboard(supplier)`: Comprehensive metrics aggregating POs, receipts, invoices, rating breakdown across all 4 dimensions, and recent logs.
- `submit_vendor_rating(...)`: Validates input, creates `Vendor Rating Log`, recalculates weighted rating, and updates the Supplier master.
- `get_supplier_comparison(item_code, qty=1)`: Returns comparative breakdown of past suppliers with last rate, avg rate, overall rating, delivery score, and total supplied quantity.
- `get_onboarding_status_summary()`: Aggregated status statistics (pending, approved, rejected) and recent submissions for dashboard widgets.

### 4. Role-Based Permissions (`permissions.py`)
- Created roles `Vendor Manager` and `Purchase Team`.
- Configured DocType permission matrices across `Vendor Onboarding`, `Vendor Rating Log`, `Vendor Category`, and `Vendor Portal Settings`.
- `has_rating_log_permission`: Restricts regular users to editing their own ratings, while Vendor Managers have full edit access.
- `get_onboarding_permission_conditions`: Applies SQL query filters restricting Purchase Team users to their own submissions.

---

## Day 3 Implementation Summary (Section 3.3)

### 1. Scheduled Background Automation (`tasks.py`)
- **Auto-Calculate Vendor Ratings (Daily)**: Iterates over active suppliers, recalculates weighted ratings from `Vendor Portal Settings`, and emails Vendor Managers if ratings drop below threshold.
- **Auto-Rate Deliveries (Hourly)**: Finds recent Purchase Receipts without a Delivery rating log and evaluates timeliness against PO `schedule_date` and quantity completeness.
- **Vendor Performance Digest (Weekly)**: Sends an executive HTML digest to Vendor Managers featuring Top 5 suppliers, Bottom 5 suppliers, weekly PO volume/value, new onboardings, and critical alerts.
- **Auto-Expire Stale Onboardings (Daily via cron `0 9 * * *`)**: Identifies onboarding applications pending review for >7 days (reminder email) and auto-rejects inactive applications older than 14 days.

### 2. Complete `hooks.py` Configuration
- `doc_events`: Configured on `Purchase Receipt`, `Vendor Onboarding` (`after_insert` welcome email), and `Supplier` (`on_update` blacklist security alert).
- `override_doctype_class`: Mapped `Purchase Order` to `CustomPurchaseOrder`.
- `scheduler_events`: Registered daily, hourly, weekly, and cron jobs.
- `permission_query_conditions` and `has_permission`: Connected to `vendor_portal.permissions`.
- `jinja`: Custom `star_rating` Unicode star filter.
- `fixtures`: Export of Custom Fields, Workflows, Workflow States, Workflow Action Masters, Roles, and Print Formats.

### 3. Script Reports
- **Vendor Performance Report**: Cross-module SQL analysis linking `Supplier`, `Purchase Order`, `Purchase Receipt`, and `Vendor Rating Log` with on-time delivery %, short delivery counts, dimensional score averages, and Top 10 bar chart.
- **Purchase Analysis by Vendor Category**: Aggregates total suppliers, active counts, total PO spend, average order value, item quantities, average category ratings, lowest rating vendors, and category spend pie chart.

### 4. Data Migration Patches (`patches/v1_0/`)
Registered in `patches.txt`:
1. `populate_vendor_category_on_suppliers.py`: Maps legacy `supplier_group` values to standard `vendor_categories` and ensures category masters exist.
2. `recalculate_vendor_ratings.py`: Recalculates supplier scores across the database using weighted formulas.
3. `migrate_supplier_notes_to_rating_logs.py`: Intelligently parses historical supplier comments containing performance keywords into structured `Vendor Rating Log` entries.

### 5. Custom Print Format (`Vendor Purchase Order`)
- Professional Jinja2 + HTML template for Purchase Orders.
- Dynamic vendor category badges.
- Visual star rating output using `star_rating` filter.
- Prominent low-rating advisory notice when rating is `< 3.0` ("Caution: Low-rated vendor").
- "Vendor Portal" watermark styling and procurement branding.

### 6. Comprehensive Unit Testing
22 passing unit tests covering all required business workflows:
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

----------------------------------------------------------------------
Ran 22 tests in 0.890s
OK
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
- [x] All 4 whitelisted APIs return correct data
- [x] 2 custom roles with proper permissions configured and tested
- [x] `has_permission` and `permission_query_conditions` working
- [x] All 4 background jobs registered and working
- [x] `hooks.py` complete: doc_events, override, scheduler, fixtures, app_include, jinja
- [x] 2 Script Reports with filters, SQL JOINs, and charts
- [x] Custom Print Format with star rating and vendor info
- [x] All 3 patches in `patches.txt`, executed via `bench migrate`
- [x] All 22 unit tests pass
- [x] `README.md` documents override approaches with trade-offs
- [x] Code committed to Git with conventional commits (10+ commits)
- [x] App installs and migrates cleanly

---

## License
MIT
