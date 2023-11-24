from odoo import models, fields

class DocumentType(models.Model):
    _name = "documenttype"
    _description = "document_type"

    name = fields.Char(string="Document Type Name", required=True)
    active = fields.Boolean('Active', default=True)