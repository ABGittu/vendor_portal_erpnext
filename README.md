# Vendor Portal & Purchase Automation System (`vendor_portal`)

A production-grade Frappe custom app that extends ERPNext's purchasing workflow with automated vendor onboarding, intelligent purchase validation, supplier performance scoring, and comprehensive vendor management — built without modifying ERPNext core code.

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

## Day 1 Implementation Summary

### 1. Custom DocTypes
- **Vendor Category (`vendor_category`)**: Master for categorizing suppliers (Raw Materials, Packaging, IT Services, Office Supplies, Logistics) with minimum rating thresholds, default payment terms, and active status. Autonamed by `category_name`.
- **Vendor Document (`vendor_document`)**: Child table for verification documents (GST Certificate, PAN Card, Bank Statement, Trade License, MSME Certificate, Other) with attachment and verification tracking.
- **Vendor Onboarding (`vendor_onboarding`)**: Submittable document capturing supplier credentials, tax details, bank info, address, contacts, and verification documents. Managed via naming series `VOB-.YYYY.-.#####`.
- **Vendor Rating Log (`vendor_rating_log`)**: Immutable performance log capturing ratings (1.0 to 5.0) across Delivery, Quality, Pricing, and Communication dimensions, linked to Purchase Orders and Receipts. Series `VRL-.YYYY.-.#####`.
- **Vendor Portal Settings (`vendor_portal_settings`)**: Single DocType for system configuration, including automated supplier creation, minimum document requirements, rating weights, and rating thresholds.

### 2. ERPNext Supplier Extension & Fixtures
The standard ERPNext `Supplier` DocType has been augmented with custom fields:
- `vendor_category` (Link to Vendor Category)
- `vendor_rating` (Rating 1–5, auto-calculated)
- `total_rating_count` (Int, read-only)
- `onboarding_reference` (Link to Vendor Onboarding, read-only)
- `is_blacklisted` (Check)
- `blacklist_reason` (Small Text, conditionally visible when blacklisted)

All custom fields, workflow states, workflow action masters, and workflows are exported as upgrade-safe **fixtures** in `vendor_portal/fixtures/`.

### 3. Vendor Onboarding Lifecycle & Approval Workflow
- **Validation**:
  - Validates GST format against 15-character alphanumeric pattern (`^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`).
  - Validates PAN format (`^[A-Z]{5}[0-9]{4}[A-Z]{1}$`) and cross-verifies PAN against GST digits 3–12.
  - Validates email syntax.
  - Enforces minimum document upload count configured in `Vendor Portal Settings`.
  - Checks for duplicate GST numbers against existing approved onboardings and active ERPNext suppliers.
- **Submission**: Sets document status to `Under Review`.
- **Approval API (`approve_onboarding`)**:
  - Restricts action to `Purchase Manager` or `System Manager`.
  - Sets status to `Approved`, records reviewer timestamp.
  - Automatically provisions ERPNext `Supplier`, `Address`, `Contact`, and `Bank Account` records.
  - Dispatches approval email notification to the vendor.
- **Rejection API (`reject_onboarding`)**:
  - Enforces mandatory rejection reason.
  - Transitions status to `Rejected` and sends notification email.
- **Workflow State Engine**: Configured states (`Draft` -> `Under Review` -> `Approved` / `Rejected` -> `Under Review`).

### 4. Controller Override vs. Hook Implementation
This project deliberately demonstrates both primary Frappe extension paradigms:

#### A) Purchase Order: `override_doctype_class` (Task 1.4)
Configured in `hooks.py` via `override_doctype_class`:
```python
override_doctype_class = {
    "Purchase Order": "vendor_portal.overrides.purchase_order.CustomPurchaseOrder"
}
```
In `CustomPurchaseOrder` (inheriting from `erpnext.buying.doctype.purchase_order.purchase_order.PurchaseOrder`):
- `validate()`:
  - Invokes `super().validate()` first to preserve standard ERPNext business rules.
  - Prevents creation of POs for blacklisted suppliers with error: `Cannot create Purchase Order for blacklisted supplier {name}. Reason: {reason}`.
  - Prevents creation of POs if supplier rating is below the category threshold: `Supplier {name} rating ({rating}) is below the minimum threshold ({threshold}) for {category}.`
  - Logs validation event using `frappe.logger().info()`.
- `on_submit()`:
  - Invokes `super().on_submit()`.
  - Computes historical average PO grand total for the supplier.
  - Automatically creates a `Pricing` rating log (5.0 if >10% cheaper than avg, 4.0 if on-par, 3.0 if >10% more expensive).
  - Triggers supplier weighted rating recalculation.
- `on_cancel()`:
  - Invokes `super().on_cancel()`.
  - Deletes all linked `Vendor Rating Log` entries and triggers rating recalculation.

#### B) Purchase Receipt: `doc_events` (Task 1.5)
Configured in `hooks.py` via `doc_events`:
```python
doc_events = {
    "Purchase Receipt": {
        "validate": "vendor_portal.overrides.purchase_receipt.validate",
        "on_submit": "vendor_portal.overrides.purchase_receipt.on_submit",
    }
}
```
In `vendor_portal.overrides.purchase_receipt`:
- `validate(doc, method)`:
  - Iterates over received items and checks if `accepted_qty < 0.9 * ordered_qty` from the linked Purchase Order Item.
  - Sets flag `doc.flags.has_short_delivery = True`.
  - Adds an audit comment on the document noting short delivery.
- `on_submit(doc, method)`:
  - Computes variance between PR `posting_date` and PO `expected_delivery_date`.
  - Classifies delivery as Late if >2 days past expected.
  - Scores delivery performance:
    - **5.0**: On-time, full quantity
    - **4.0**: On-time, short delivery (<90%)
    - **3.0**: Late (>2 days), full quantity
    - **2.0**: Late (>2 days), short delivery (<90%)
  - Creates a `Delivery` rating log and recalculates the supplier's weighted score.

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

### Preferred Approach & Engineering Rationale
- **Preference**: Use `doc_events` by default for all cross-cutting concerns (scoring, logging, notifications, validation flags).
- **When `override_doctype_class` is required**: Only when custom business requirements necessitate replacing or wrapping core algorithmic logic that does not emit a document event (e.g., modifying tax calculations, inventory allocation algorithms, or replacing internal subroutines).
- **Rule of Thumb**: Calling `super()` is strictly mandatory in `override_doctype_class` to ensure ERPNext core integrity is never broken.

---

## Installation & Setup

1. Clone or add the app to your bench:
```bash
cd /path/to/frappe-bench
bench get-app vendor_portal
bench --site [site_name] install-app vendor_portal
```

2. Migrate and sync fixtures:
```bash
bench --site [site_name] migrate
```

---

## Git Workflow & Commits

This project strictly follows Conventional Commits:
- `feat(doctype): create vendor category, document, onboarding, rating log and settings doctypes`
- `feat(custom-fields): add custom fields to supplier doctype and export fixtures`
- `feat(workflow): implement vendor onboarding controller and approval workflow`
- `feat(purchase-order): override purchase order controller with validation and auto-rating`
- `feat(purchase-receipt): add doc_events hook for purchase receipt validation and delivery rating`
- `docs: add comprehensive README with override trade-off analysis and architecture documentation`

---

## License
MIT
