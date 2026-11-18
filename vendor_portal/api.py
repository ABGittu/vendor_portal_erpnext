# Copyright (c) 2026, Abhijit Prakashkumar Dodiya and contributors
# For license information, please see license.txt

import frappe
from vendor_portal.vendor_portal.doctype.vendor_onboarding.vendor_onboarding import (
	approve_onboarding,
	reject_onboarding,
)

__all__ = ["approve_onboarding", "reject_onboarding"]
