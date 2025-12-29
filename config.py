# odoo_analyzer/config.py

# Default value, will be updated by main script
BASE_DIR = ""

# Modules eligible for consolidation into csl_core
ELIGIBLE_MODULES_FOR_CORE = [
    'bista_convert_product',
    'csl_account',
    'csl_attendance',
    'csl_competitor',
    'csl_compress_product_image',
    'csl_contacts',
    'csl_custom',
    'csl_invoice',
    'csl_login',
    'csl_photos',
    'csl_product',
    'csl_project_repair',
    'csl_project_repair_assignee_log',
    'csl_purchase',
    'csl_rma',
    'csl_sale',
    'csl_timesheet',
    'csl_utilities',
    'csl_website',
    'project_repair_workflow',
    'project_repair_workflow_trigger',
    'sale_disable_auto_followers',
]