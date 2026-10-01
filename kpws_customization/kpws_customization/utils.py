# Copyright (c) 2025, Kpws Customization
# License: MIT

import frappe


def setup_property_setter_patch():
	"""Setup the property setter patch via before_request hook"""
	from kpws_customization.kpws_customization.overrides import frappe_init
	# The patch will be applied when the module is imported
	return


def before_request():
	"""Called before each request - ensures patch is applied"""
	setup_property_setter_patch()

