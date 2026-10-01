__version__ = "0.0.1"

# Import printview override to apply monkey patch
try:
	from kpws_customization.kpws_customization.overrides import printview
except ImportError:
	pass

# Import frappe_init override to fix PropertySetter validate_fieldtype_change error
try:
	from kpws_customization.kpws_customization.overrides import frappe_init
except ImportError:
	pass
