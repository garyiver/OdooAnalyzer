# -*- coding: utf8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    _sql_constraints = [("alpha_card_unique", "unique(alpha_card_id)", "Alpha Card ID must be unique")]

    # -----  Add tracking to base fields  ------
    company_name = fields.Char(tracking=True)
    name = fields.Char(tracking=True)
    street = fields.Char(tracking=True)
    city = fields.Char(tracking=True)
    state_id = fields.Many2one(tracking=True)
    zip = fields.Char(tracking=True)
    function = fields.Char(tracking=True)
    active = fields.Boolean(tracking=True)
    property_product_pricelist = fields.Many2one(tracking=True)
    property_payment_term_id = fields.Many2one(tracking=True)
    property_account_position_id = fields.Many2one(tracking=True)

    # -----  Supplier fields  ------
    login_account = fields.Char(string="Login Account")
    login_username = fields.Char(string="Login User Name")
    login_password = fields.Char(string="Login Password")

    # -----  Contact Details fields  ------
    former_name = fields.Char(string="Former Company Name")
    fax = fields.Char(string="Fax")
    po_box = fields.Char(string="PO Box")
    phone_800 = fields.Char(string="Phone 800")
    phone_other = fields.Char(string="Phone Other")
    email_other = fields.Char(string="Email Other")
    residential = fields.Boolean(string="Residential Address")

    # -----  Status and ID fields  ------
    record_source = fields.Char(string="Record Source")
    source = fields.Char(string="Source", copy=False,
                     help="Source is automatically set from your website preferences.")
    date_created = fields.Date(string="Create Date")
    alpha_cust_no = fields.Char(string="Cust No")
    alpha_contact_id = fields.Char(string="Contact ID")
    alpha_card_id = fields.Char(string="Card ID")
    address_validated = fields.Boolean(string="Address Validated", tracking=True)
    address_validated_by_customer = fields.Boolean(string="Address Validated By Customer")
    supplier_status = fields.Selection([
                                        ('approved', 'Approved'),
                                        ('conditional', 'Conditional'),
                                        ('unapproved', 'Unapproved')],
                                        string="Supplier Status")

    last_touched_date = fields.Date(string="Last Touched Date", copy=False)
    first_order_date = fields.Date(string="First Order Date",
                                   compute="_compute_first_and_last_order_date")
    last_order_date = fields.Date(string="last Order Date",
                                  compute="_compute_first_and_last_order_date")
    needs_to_review = fields.Boolean("Needs Review", copy=False, default=False,
                                     help="Needs Review is automatically "
                                          "set from your website preferences.")

    # -----  Accounting fields  ------
    credit_hold_manual = fields.Boolean(string="Credit Hold Manual", tracking=True)
    credit_hold = fields.Boolean(string="Credit Hold", compute='_compute_credit_hold')
    credit_limit = fields.Monetary(string="Credit Limit", tracking=True)
    comment_accounting = fields.Char(string="Credit Notes")
    invoice_ref = fields.Char(string="Invoice Cust Ref",
                              help="Text in this field is included at the top of customer invoices")

    # -----  Settings fields  ------
    key_decision_maker = fields.Boolean(string="Decision Maker")
    primary_contact = fields.Boolean(string="Primary Contact", default=False, copy=False)
    report_add = fields.Boolean(string="Receive Reports")
    quotation_add = fields.Boolean(string="Receive Copy of Quotes", default=False,
                                   copy=False, tracking=True)
    invoice_add = fields.Boolean(string="Receive Copy of Invoices", default=False,
                                 copy=False, tracking=True)
    default_delivery_address = fields.Many2one("res.partner", string="Delivery Address")
    service_reports_requested = fields.Boolean(string="Service Reports Requested")
    blind_shipment = fields.Boolean(string="Blind Shipments Required")
    po_required = fields.Boolean(string="PO Required", copy=False)
    required_customer_no = fields.Boolean(string='Customer Item Num Required', copy=False)
    legacy_note_header = fields.Char(string="Info")

    # -----  profiling fields  ------
    num_employees_global = fields.Integer(string="Num Employees Global")
    num_employees_site = fields.Integer(string="Num Employees Site")
    num_parking_spaces = fields.Integer(string="Num Parking Space")
    annual_revenue_global = fields.Monetary(string="Annual Revenue Global", tracking=True)
    annual_revenue_site = fields.Monetary(string="Annual Revenue Site", tracking=True)
    num_machines = fields.Integer(string="Num Machines")
    date_profile_updated = fields.Date(string='Profile Update Date', readonly=True, store=True, compute='compute_profile_updates')
    profile_updated_by = fields.Char(string="Profile Update By")
    profile_updated_by_id = fields.Many2one('res.users', string='Profile Updated By', readonly=True, store=True)
    profile_notes = fields.Text(string="Profile Notes", tracking=True)
    profile_ranking = fields.Selection(string="Profile Ranking",
                                  selection = [
                                    ('A1', 'A1'), ('A2', 'A2'), ('A3', 'A3'),
                                    ('B1', 'B1'), ('B2', 'B2'), ('B3', 'B3'),
                                    ('C1', 'C1'), ('C2', 'C2'), ('C3', 'C3'),
                                    ], required = False, tracking=True)
    profile_confidence = fields.Selection(string="Profile Confidence",
                                    selection = [
                                                 ('no_data', 'No data - Pure Guess'),
                                                 ('some_data', 'Some data'),
                                                 ('customer', 'Verified with customer'),
                                                 ('history', 'Confirmed with CSL Sales History'),
                                                 ], required = False,tracking=True)
    square_feet_site = fields.Integer(string="Square Feet Site")
    annual_items_repaired = fields.Integer(string="Annual Items Repaired",
                                             help="Number of electronic repairs this site sends out for repair every year.",
                                             tracking=True)
    total_available_market = fields.Monetary(string="Total Available Market",
                                             help="Customer's total spend on electronic repair",
                                             tracking=True)
    servicable_market = fields.Monetary(string="Serviceable Market",
                                        help="Of the customer's repair spend, how much can we actually service.",
                                        tracking=True)
    entry_barrier = fields.Selection(string="Entry Barrier",
                                    selection=[('none', 'No Barriers'),
                                               ('small', 'Small Barrier'),
                                               ('medium', 'Medium Barrier'),
                                               ('high', 'High Barrier'),
                                               ], required=False,tracking=True)
    csl_competitor_ids = fields.Many2many(comodel_name="competitor.provider",
                                          string="Competition ID",
                                          help="List of competitors we know this customer uses for electronic repair")
    notes_machines = fields.Char(string="Notes Machines")
    notes_categories = fields.Char(string="Notes Categories")
    notes_brands = fields.Char(string="Notes Brands")

    # -----  Fields to REMOVE ------
    manufacturer = fields.Boolean(
        string="Is a Manufacturer",
        help="Check this box if this contact is a Manufacturer. " "It can be selected in product list.",
    )
    incoterms_id = fields.Many2one("account.incoterms", string="Shipping Terms")
    customer_contact = fields.Many2one("res.partner", string="Customer Contact")
    customer_status = fields.Char(string="Customer Status")
    tax_1 = fields.Float(string="Tax Rate")

    # ----------  Methods  ------------
    @api.constrains('name')
    def _check_unique_name(self):
        """Added constraint on name if is_company= True"""
        for rec in self:
            if rec.name:
                partner = self.with_context(active_test=False).search([
                    ('name', 'ilike', rec.name),
                    ('is_company', '=', True),
                    ('supplier_rank', '=', 0)])
                if len(partner) > 1:
                    raise ValidationError(_(
                        "Name Must be Unique ====> %s.", partner[0].name))

    def _compute_credit_hold(self):
        for rec in self:
            if (rec.credit <= rec.credit_limit
                    and not rec.credit_hold_manual
                    and (rec.property_payment_term_id.allow_pay_later or rec.profile_ids.ids)):
                self.credit_hold = False
            else:
                self.credit_hold = True

    def _compute_first_and_last_order_date(self):
        for rec in self:
            first_order_date_so = (
                self.env["sale.order"]
                    .search([('state', '!=', 'cancel'),
                             ("partner_id", "=", rec.id)],
                            order='date_order asc', limit=1)
            )
            rec.first_order_date = first_order_date_so.date_order or False

            last_order_date_so = (
                self.env["sale.order"]
                    .search([('state', '!=', 'cancel'),
                             ("partner_id", "=", rec.id)],
                            order='date_order desc', limit=1)
            )
            rec.last_order_date = last_order_date_so.date_order or False

    @api.depends('profile_ranking', 'annual_revenue_global', 'annual_revenue_site', 
                 'profile_notes', 'annual_items_repaired', 'profile_confidence')
    def compute_profile_updates(self):
        for record in self:
                record.date_profile_updated = fields.Date.today()
                record.profile_updated_by_id = self.env.user.id

    @api.onchange('profile_ranking', 'annual_revenue_global', 'annual_revenue_site',
                  'profile_notes', 'annual_items_repaired', 'profile_confidence')
    def _onchange_profile(self):
            self.date_profile_updated = fields.Date.today()
            self.profile_updated_by_id = self.env.user.id


    @api.model
    def create(self, vals):
        context = dict(self.env.context)
        if vals.get('user_id') and self.env.company.id \
                and not self.env.company.opt_for_email:
            context.update({'mail_auto_subscribe_no_notify': 1})

        result = super(ResPartner, self.with_context(context)).create(vals)
        if not vals.get('date_created'):
            for res in result:
                res.date_created = res.create_date

        return result

    def write(self, vals):
        context = dict(self.env.context)
        if vals.get('user_id') and self.env.company.id and \
                not self.env.company.opt_for_email:
            context.update({'mail_auto_subscribe_no_notify': 1})

        if 'street' in vals or 'street2' in vals or 'city' in vals or 'state_id' in vals or 'zip' in vals or 'country_id' in vals:
            if not self.env.context.get('shipengine_accepted'):
                vals.update({'address_validated': False,
                             'address_validated_by_customer':False,
                             'residential': False})
        return super(ResPartner, self.with_context(context)).write(vals)


class ResPartnerIndustry(models.Model):
    _inherit = "res.partner.industry"

    bus_type = fields.Char(string="Bus Type")
