from odoo import models, fields


class InPincodeState(models.Model):
    _name = 'in.pincode.state'
    _description = 'Indian Pincode State Map'

    pincode = fields.Char(string='Pincode', index=True)
    state_name = fields.Char(string='State Name')