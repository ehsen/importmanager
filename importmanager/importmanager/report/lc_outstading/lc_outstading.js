// Copyright (c) 2025, SpotLedger and contributors
// For license information, please see license.txt

frappe.query_reports["LC Outstading"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"fieldtype": "Date",
			"label": "From Date",
			"mandatory": 1,
			"wildcard_filter": 0
		},
		{
			"fieldname": "to_date",
			"fieldtype": "Date",
			"label": "To Date",
			"mandatory": 1,
			"wildcard_filter": 0
		},
		{
			"fieldname": "company",
			"fieldtype": "Link",
			"label": "Company",
			"mandatory": 1,
			"options": "Company",
			"wildcard_filter": 0
		}
	]
};
