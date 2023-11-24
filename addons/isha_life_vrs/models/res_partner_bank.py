from odoo import models, fields

class ResPartnerBank(models.Model):
    _name = 'res.partner.bank'
    _inherit = ['res.partner.bank', 'mail.thread', 'mail.activity.mixin']
    
    rpb_tally_ledger_name = fields.Char(string="Tally Ledger Name", store=True, required=True)
    reason_acc_holder_mismatch = fields.Text('Reason for account holder name mismatch')
    idfy_name_score = fields.Integer(string="IDFY name score", default=-1)
    

