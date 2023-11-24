from odoo import fields, models,api
from odoo.exceptions import ValidationError

class idproof_attach(models.Model):
    _name = "idproof.attachment"
    _description = "ID Proof Attachment"

    idproof_id = fields.Many2one('res.partner', string='idproof_attach')
    attached_file = fields.Many2many(comodel_name="ir.attachment",
                                     relation="m2m_ir_attached_file_rel",
                                     column1="m2m_id", column2="attachment_id",
                                     string="File Attachment", required=True
                                     )
    idproof_document_type = fields.Many2one('documenttype', string="ID Type", required=True)

    # Removing as per the UAT feedback
    # idproof_file = fields.Char(string="File Name", required=True)
    active = fields.Boolean('Active', default=True)

    #    state = fields.Boolean('State', default=True)

    # hide by karthik
    # def _compute_assign_attach(self):
    #     for record in self:
    #         if record.attached_file.ids:
    #             if record.attached_file.mimetype == 'image/jpeg' or \
    #                     record.attached_file.mimetype == 'image/png':
    #                 record.idproof_temp = record.attached_file[0].datas
    #             else:
    #                 record.idproof_temp = _get_default_image()
    #         else:
    #             record.idproof_temp =_get_default_image()

    def unlink(self):
        if len(self.attached_file) > 0:
            for x in self.attached_file:
                x.unlink()
        return super(idproof_attach, self).unlink()


    @api.onchange('attached_file')
    def limit_attached_file(self):
        attachement = len(self.attached_file)
        if attachement > 1:
            raise ValidationError(_('You can add only 1 files per ID Proof'))