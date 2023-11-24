from odoo import models, fields, api
import re


class ResUsersModified(models.Model):
    _inherit = 'res.users'
    
    department_ids = fields.Many2many(comodel_name="hr.department",
                     relation="users_allowed_department_rel",
                     column1="user_id", column2="department_id",
                     string="Allowed Department", ondelete='restrict')
    
    defult_department_id = fields.Many2one('hr.department',string='Default Department', ondelete='restrict',required=False)


class ResPartnermodified(models.Model):
    _inherit = 'res.partner'
    _description = 'Res partner modified'

    is_vendor = fields.Boolean(string='Is Vendor')
    state = fields.Char(string='State')
    pan_no = fields.Char(string='PAN')
    old_vat = fields.Char(string='Old GSTIN', readonly=True)
    primary_dep_id = fields.Many2one('hr.department', string="Working Primarily With",
                                     domain=([('fin_dept_type', 'in', ('pf', 'ff'))]),
                                     default=lambda self: self._default_primary_dep_id())
    department_ids = fields.Many2many('hr.department', string='Associated Departments', ondelete='restrict',
                                      )
    proof_ids = fields.One2many('idproof.attachment', 'idproof_id', string="ID Proof")
    
    def _clear_company_name(self, name):
            # ignore_words = ['private', 'limited', 'pvt', 'ltd', 'india']
            ignore_words = []
            name = name.lower().split('a/c')[0].strip()
            return ' '.join(filter(lambda word: re.sub(r'\W+', '', word.lower()) not in ignore_words,
                            name.lower().split()))
    
    def _compare_company_name(self, name, name2=None):
        name2 = name2 or self.name
        return self._clear_company_name(name2) == self._clear_company_name(name)

    @api.model
    def _default_primary_dep_id(self):
        print('in _default_primary_dep_id')
        v_access_pf_tally = False
        v_access_ff_tally = False
        dept_ids = self.env.user.department_ids.ids
        rec_user_depts = self.env['hr.department'].browse(dept_ids)

        for rec in rec_user_depts:
            print(rec.id)
            # print(rec.fin_dept_type)
            if (rec.name == 'Project Finance'):
                v_access_pf_tally = True
                break

        for rec in rec_user_depts:
            print(rec.id)
            # print(rec.fin_dept_type)
            if (rec.name == 'Foundation Finance'):
                v_access_ff_tally = True
                break

        if v_access_pf_tally == True and v_access_ff_tally == True:
            print('PF - set pushed_to_tally = Not pushed')
            return
        elif v_access_pf_tally == True:
            print('Return PF', rec.id)
            return rec.id
        elif v_access_ff_tally == True:
            print('Return FF', rec.id)
            return rec.id

class HrDepartmentmodified(models.Model):
    _inherit = 'hr.department'
    
    fin_dept_type = fields.Selection([('pf', 'Project Finance'), ('ff', 'Foundation Finance')],string='Finance Department Type')
    

    



    

