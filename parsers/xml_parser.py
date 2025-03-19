"""XML file parser for Odoo analyzer with improved data/view distinction"""
import logging
import os
import re
from collections import defaultdict
from utils.file_utils import get_files, get_module_name
from models.field_usage import FieldUsage

logger = logging.getLogger(__name__)

# Try to import lxml for better XML parsing if available
try:
    from lxml import etree as ET

    USING_LXML = True
except ImportError:
    # Fall back to standard ElementTree
    import xml.etree.ElementTree as ET

    USING_LXML = False
    logger.info("Using standard ElementTree for XML parsing. Consider installing lxml for better performance.")

# Record types classification
RECORD_TYPE_VIEW = 'view'
RECORD_TYPE_DATA = 'data'
RECORD_TYPE_UNKNOWN = 'unknown'

# View-related models
VIEW_MODELS = {
    'ir.ui.view',
    'ir.actions.act_window',
    'ir.actions.report',
    'ir.actions.server',
    'ir.actions.client',
    'ir.ui.menu',
    'ir.model.access',
    'ir.rule',
}


def classify_xml_record(record, registry):
    """
    Classify XML record as data record or view definition

    Args:
        record: XML record element
        registry: Model registry for model lookups

    Returns:
        str: 'view', 'data', or 'unknown'
    """
    model_attr = record.get('model')

    if not model_attr:
        return RECORD_TYPE_UNKNOWN

    # View-related models
    if model_attr in VIEW_MODELS:
        return RECORD_TYPE_VIEW

    # Check if this is a data record for a model we know about
    if model_attr in registry.models:
        return RECORD_TYPE_DATA

    return RECORD_TYPE_UNKNOWN


def find_parent_record(elem, root, max_depth=100):
    """
    Find the parent record element for an XML element with a depth limit
    to prevent recursion errors
    """
    depth = 0
    parent = elem

    # Try to navigate up the tree to find the record
    while parent is not None and parent != root and depth < max_depth:
        if parent.tag == 'record':
            return parent

        depth += 1

        # Try to move up to the parent
        try:
            # This works for lxml
            parent = parent.getparent()
        except (AttributeError, NameError):
            # Fallback for standard ElementTree - limit search to direct children
            # This avoids deep recursion
            for potential_parent in list(root)[:100]:  # Limit search to first 100 children
                if elem in list(potential_parent)[:100]:  # Only check first 100 children
                    parent = potential_parent
                    break
            else:
                # No parent found
                parent = None

    # No record found or max depth reached
    if depth >= max_depth:
        logger.warning(f"Max depth reached while finding parent record for {elem.tag}")

    return None


def find_parent_template_id(field_elem, root, max_depth=100):
    """
    Find the ID of the parent template for a field element with a depth limit
    to prevent recursion errors
    """
    depth = 0
    parent = field_elem

    # Try to navigate up the tree to find the template
    while parent is not None and parent != root and depth < max_depth:
        if parent.tag == 'template' and 'id' in parent.attrib:
            return parent.attrib['id']

        depth += 1

        # Try to move up to the parent
        try:
            # This works for lxml
            parent = parent.getparent()
        except (AttributeError, NameError):
            # Fallback for standard ElementTree - limit search to direct children
            # This avoids deep recursion
            for potential_parent in list(root)[:100]:  # Limit search to first 100 children
                if field_elem in list(potential_parent)[:100]:  # Only check first 100 children
                    parent = potential_parent
                    break
            else:
                # No parent found
                parent = None

    # No template ID found or max depth reached
    if depth >= max_depth:
        logger.warning(f"Max depth reached while finding parent template for {field_elem.tag}")

    return None

def extract_view_definitions(root, registry, module):
    """Extract view definitions and models from XML"""
    # Extract view definitions (<record model="ir.ui.view">)
    for record in root.findall(".//record"):
        record_id = record.get('id')
        model_attr = record.get('model')

        if not record_id:
            continue

        # Format the record ID with module prefix if needed
        if '.' not in record_id:
            record_id = f"{module}.{record_id}"

        # If this is a view definition
        if model_attr == 'ir.ui.view':
            # Find the model this view is for
            model_field = record.find("./field[@name='model']")
            inherit_field = record.find("./field[@name='inherit_id']")

            model_name = None
            inherit_id = None

            if model_field is not None and model_field.text:
                model_name = model_field.text

            if inherit_field is not None:
                inherit_id = inherit_field.get('ref')
                if inherit_id and '.' not in inherit_id:
                    inherit_id = f"{module}.{inherit_id}"

            # Find view type
            view_type = None
            type_field = record.find("./field[@name='type']")
            if type_field is not None and type_field.text:
                view_type = type_field.text

            # Register the view
            registry.register_view(record_id, model_name, inherit_id, view_type)


def extract_field_usage(root, registry, module, file_path, field_usages):
    """Extract field usage from XML elements with record type classification"""
    # First, extract and classify all records
    classified_records = {}
    for record in root.findall(".//record"):
        record_id = record.get('id')
        if record_id:
            if '.' not in record_id:
                record_id = f"{module}.{record_id}"

            record_type = classify_xml_record(record, registry)
            classified_records[record] = {
                'id': record_id,
                'type': record_type,
                'model': record.get('model')
            }

    # Look for standard field tags: <field name="field_name"/>
    extract_standard_fields(root, registry, module, file_path, field_usages, classified_records)

    # Look for QWeb expressions: t-field="record.field_name"
    extract_qweb_fields(root, registry, module, file_path, field_usages)

    # Look for domain expressions: domain="[('field_name', ...)]"
    extract_domain_fields(root, registry, module, file_path, field_usages, classified_records)


def extract_standard_fields(root, registry, module, file_path, field_usages, classified_records):
    """Extract standard field tags from XML with record type classification"""
    for field_elem in root.findall(".//field[@name]"):
        field_name = field_elem.get('name')

        # Skip meta fields
        if field_name in ('model', 'arch', 'inherit_id', 'priority', 'sequence', 'mode', 'type'):
            continue

        # Find the containing record to determine the view
        record = find_parent_record(field_elem, root)

        record_id = None
        model_name = None
        record_type = RECORD_TYPE_UNKNOWN
        view_type = None

        if record is not None:
            if record in classified_records:
                record_data = classified_records[record]
                record_id = record_data['id']
                record_type = record_data['type']

                # For view records, try to find model from view definition
                if record_type == RECORD_TYPE_VIEW and record_data['model'] == 'ir.ui.view':
                    view_info = registry.views.get(record_id, {})
                    model_name = view_info.get('model')
                    view_type = view_info.get('view_type')
                # For data records, use the record model
                elif record_type == RECORD_TYPE_DATA:
                    model_name = record_data['model']
            else:
                # Fallback for records not in the classification
                record_id = record.get('id')
                if record_id and '.' not in record_id:
                    record_id = f"{module}.{record_id}"

                if record.get('model') == 'ir.ui.view':
                    record_type = RECORD_TYPE_VIEW
                    view_info = registry.views.get(record_id, {})
                    model_name = view_info.get('model')
                    view_type = view_info.get('view_type')
                elif record.get('model') in registry.models:
                    record_type = RECORD_TYPE_DATA
                    model_name = record.get('model')

        # If we have a model, try to resolve the field owner
        field_key = None
        if model_name:
            # Try to find the true owner of this field through inheritance
            field_owner = registry.resolve_field_owner(field_name, model_name)
            if field_owner:
                field_key = f"{field_owner}.{field_name}"
            else:
                field_key = f"{model_name}.{field_name}"
        else:
            # Without model info, just use the field name
            field_key = field_name

        # Add this field usage with record type info
        context = record_id if record_id else os.path.basename(file_path)
        usage = FieldUsage(field_key, context, module, file_path, model_name)
        usage.record_type = record_type  # Add record type information
        usage.view_type = view_type if view_type else ''  # Add view type if available
        field_usages.append(usage)


def extract_qweb_fields(root, registry, module, file_path, field_usages):
    """Extract field references from QWeb templates"""
    # Regex patterns for QWeb expressions
    qweb_field_pattern = re.compile(r'(?:o|object|doc|record|line)\.([A-Za-z_0-9]+)')

    # Try to find templates with t-model attribute
    for elem in root.findall(".//*[@t-model]"):
        model_name = elem.get('t-model')
        process_qweb_element(elem, model_name, qweb_field_pattern, registry, module, file_path, root, field_usages)

    # Also look for regular template definitions (without t-model)
    for template in root.findall(".//template"):
        template_id = template.get('id')
        # Try to infer model from template ID or other patterns
        model_name = infer_template_model(template, template_id)
        process_qweb_element(template, model_name, qweb_field_pattern, registry, module, file_path, root, field_usages)


def process_qweb_element(elem, model_name, pattern, registry, module, file_path, root, field_usages):
    """Process a QWeb element to extract field references"""
    # Process t-field attributes
    for field_elem in elem.findall(".//*[@t-field]"):
        field_expr = field_elem.get('t-field')
        if not field_expr:
            continue

        matches = pattern.findall(field_expr)
        for field_name in matches:
            # Add this field usage
            add_qweb_field_usage(field_name, model_name, field_elem, registry, module, file_path, root, field_usages)

    # Process t-esc attributes
    for field_elem in elem.findall(".//*[@t-esc]"):
        field_expr = field_elem.get('t-esc')
        if not field_expr:
            continue

        matches = pattern.findall(field_expr)
        for field_name in matches:
            # Add this field usage
            add_qweb_field_usage(field_name, model_name, field_elem, registry, module, file_path, root, field_usages)

    # Process other attributes that might contain field references (t-if, t-foreach, etc.)
    for field_elem in elem.findall(".//*[@t-if]"):
        field_expr = field_elem.get('t-if')
        if not field_expr:
            continue

        matches = pattern.findall(field_expr)
        for field_name in matches:
            # Add this field usage
            add_qweb_field_usage(field_name, model_name, field_elem, registry, module, file_path, root, field_usages)

    for field_elem in elem.findall(".//*[@t-foreach]"):
        field_expr = field_elem.get('t-foreach')
        if not field_expr:
            continue

        matches = pattern.findall(field_expr)
        for field_name in matches:
            # Add this field usage
            add_qweb_field_usage(field_name, model_name, field_elem, registry, module, file_path, root, field_usages)


def infer_template_model(template, template_id):
    """Try to infer model from template information"""
    # This is a heuristic function and can be expanded with more patterns
    if not template_id:
        return None

    # Some common patterns in template IDs
    if 'product_template' in template_id:
        return 'product.template'
    elif 'product_product' in template_id:
        return 'product.product'
    elif 'sale_order' in template_id:
        return 'sale.order'
    elif 'purchase_order' in template_id:
        return 'purchase.order'
    elif 'account_move' in template_id or 'account_invoice' in template_id:
        return 'account.move'
    elif 'res_partner' in template_id:
        return 'res.partner'

    # If we can't infer, return None
    return None


def add_qweb_field_usage(field_name, model_name, field_elem, registry, module, file_path, root, field_usages):
    """Add a field usage found in QWeb templates"""
    # Resolve the field owner
    field_key = None
    if model_name:
        field_owner = registry.resolve_field_owner(field_name, model_name)
        if field_owner:
            field_key = f"{field_owner}.{field_name}"
        else:
            field_key = f"{model_name}.{field_name}"
    else:
        field_key = field_name

    # Find containing template
    template_id = find_parent_template_id(field_elem, root)
    context = template_id if template_id else os.path.basename(file_path)

    # QWeb fields are always used in views/templates
    usage = FieldUsage(field_key, context, module, file_path, model_name)
    usage.record_type = RECORD_TYPE_VIEW  # QWeb fields are in views
    usage.view_type = 'qweb'  # Mark as qweb template
    field_usages.append(usage)


def extract_domain_fields(root, registry, module, file_path, field_usages, classified_records):
    """Extract field references from domain attributes"""
    # Look for elements with domain or context attributes
    domain_pattern = re.compile(r'\[([\'"])([a-zA-Z0-9_]+)([\'"])')

    # Process domain attributes
    for elem in root.findall(".//*[@domain]"):
        domain_expr = elem.get('domain')
        if not domain_expr:
            continue

        # Find all field references in the domain
        matches = domain_pattern.findall(domain_expr)
        process_field_matches(matches, elem, root, registry, module, file_path, field_usages, classified_records)

    # Also check context attributes which may have domain expressions
    for elem in root.findall(".//*[@context]"):
        context_expr = elem.get('context')
        if not context_expr:
            continue

        # Find all field references in the context
        matches = domain_pattern.findall(context_expr)
        process_field_matches(matches, elem, root, registry, module, file_path, field_usages, classified_records)


def process_field_matches(matches, elem, root, registry, module, file_path, field_usages, classified_records):
    """Process field matches found in domain or context expressions"""
    for _, field_name, _ in matches:
        # Try to determine the model
        model_name = None
        record = find_parent_record(elem, root)

        record_id = None
        record_type = RECORD_TYPE_UNKNOWN
        view_type = None

        if record is not None:
            if record in classified_records:
                record_data = classified_records[record]
                record_id = record_data['id']
                record_type = record_data['type']

                # For view records, try to find model from view definition
                if record_type == RECORD_TYPE_VIEW and record_data['model'] == 'ir.ui.view':
                    view_info = registry.views.get(record_id, {})
                    model_name = view_info.get('model')
                    view_type = view_info.get('view_type')
                # For data records, use the record model
                elif record_type == RECORD_TYPE_DATA:
                    model_name = record_data['model']
            else:
                # Fallback if record not classified
                record_id = record.get('id')
                if record_id and '.' not in record_id:
                    record_id = f"{module}.{record_id}"

                if record.get('model') == 'ir.ui.view':
                    record_type = RECORD_TYPE_VIEW
                    view_info = registry.views.get(record_id, {})
                    model_name = view_info.get('model')
                    view_type = view_info.get('view_type')
                elif record.get('model') in registry.models:
                    record_type = RECORD_TYPE_DATA
                    model_name = record.get('model')

        # If we have a model, try to resolve the field owner
        field_key = None
        if model_name:
            # Try to find the true owner of this field through inheritance
            field_owner = registry.resolve_field_owner(field_name, model_name)
            if field_owner:
                field_key = f"{field_owner}.{field_name}"
            else:
                field_key = f"{model_name}.{field_name}"
        else:
            # Without model info, just use the field name
            field_key = field_name

        # Add this field usage with record type information
        context = record_id if record_id else os.path.basename(file_path)
        usage = FieldUsage(field_key, context, module, file_path, model_name)
        usage.record_type = record_type
        usage.view_type = view_type if view_type else ''
        field_usages.append(usage)


def parse_xml_file(file_path, registry):
    """Parse XML file to extract field usage information with better error handling"""
    try:
        # Track field usage in this file
        field_usages = []

        # Parse the XML file with robust error handling
        try:
            # Attempt to parse with proper namespace handling and recovery (for lxml)
            if USING_LXML:
                parser = ET.XMLParser(ns_clean=True, recover=True, resolve_entities=False)
                tree = ET.parse(file_path, parser=parser)
            else:
                # Fall back to standard parsing
                tree = ET.parse(file_path)
        except Exception as e:
            logger.error(f"Error parsing XML file {file_path}: {e}")
            return {}

        root = tree.getroot()
        module = get_module_name(file_path)

        # Use try/except blocks around each processing step
        try:
            # First pass: extract view definitions and models
            extract_view_definitions(root, registry, module)
        except Exception as e:
            logger.error(f"Error extracting view definitions from {file_path}: {e}")

        try:
            # Second pass: extract field usage
            extract_field_usage(root, registry, module, file_path, field_usages)
        except Exception as e:
            logger.error(f"Error extracting field usage from {file_path}: {e}")

        # Convert to dictionary format for easier processing
        field_usage_dict = defaultdict(list)
        for usage in field_usages:
            try:
                field_usage_dict[usage.field_key].append(usage.to_dict())
            except Exception as e:
                logger.error(f"Error converting field usage to dict: {e}")

        return field_usage_dict
    except RecursionError:
        logger.error(f"Recursion depth exceeded while parsing XML file {file_path}. Skipping file.")
        return {}
    except Exception as e:
        logger.error(f"Error parsing XML file {file_path}: {e}")
        return {}


def parse_xml_files(base_dir, registry):
    """Parse all XML files in the directory"""
    logger.info("Processing XML files for view definitions and field usage...")
    field_usage = {}

    for file_path in get_files(base_dir, '.xml'):
        try:
            file_usage = parse_xml_file(file_path, registry)
            # Merge usage data
            for field_key, usages in file_usage.items():
                if field_key not in field_usage:
                    field_usage[field_key] = []
                field_usage[field_key].extend(usages)
        except Exception as e:
            logger.error(f"Error processing XML file {file_path}: {e}")

    logger.info(f"Found {len(field_usage)} unique fields referenced in XML files")
    return field_usage