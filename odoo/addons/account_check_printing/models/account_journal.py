# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.depends('outbound_payment_method_ids')
    def _compute_check_printing_payment_method_selected(self):
        for journal in self:
            journal.check_printing_payment_method_selected = any(pm.code == 'check_printing' for pm in journal.outbound_payment_method_ids)

    @api.depends('check_manual_sequencing')
    def _get_check_next_number(self):
        for journal in self:
            if journal.check_sequence_id:
                journal.check_next_number = journal.check_sequence_id.number_next_actual
            else:
                journal.check_next_number = 1

    def _set_check_next_number(self):
        for journal in self:
            if journal.check_next_number and not re.match(r'^[0-9]+$', journal.check_next_number):
                raise ValidationError(_('Next Check Number should only contains numbers.'))
            if int(journal.check_next_number) < journal.check_sequence_id.number_next_actual:
                raise ValidationError(_("The last check number was %s. In order to avoid a check being rejected "
                    "by the bank, you can only use a greater number.") % journal.check_sequence_id.number_next_actual)
            if journal.check_sequence_id:
                journal.check_sequence_id.sudo().number_next_actual = int(journal.check_next_number)

    check_manual_sequencing = fields.Boolean('Manual Numbering', default=False,
        help="Check this option if your pre-printed checks are not numbered.")
    check_sequence_id = fields.Many2one('ir.sequence', 'Check Sequence', readonly=True, copy=False,
        help="Checks numbering sequence.")
    check_next_number = fields.Char('Next Check Number', compute='_get_check_next_number', inverse='_set_check_next_number',
        help="Sequence number of the next printed check.")
    check_printing_payment_method_selected = fields.Boolean(compute='_compute_check_printing_payment_method_selected',
        help="Technical feature used to know whether check printing was enabled as payment method.")

    @api.model
    def create(self, vals):
        rec = super(AccountJournal, self).create(vals)
        if not rec.check_sequence_id:
            rec._create_check_sequence()
        return rec

    def _create_check_sequence(self):
        """ Create a check sequence for the journal """
        for journal in self:
            journal.check_sequence_id = self.env['ir.sequence'].sudo().create({
                'name': journal.name + _(" : Check Number Sequence"),
                'implementation': 'no_gap',
                'padding': 5,
                'number_increment': 1,
                'company_id': journal.company_id.id,
            })

    def _default_outbound_payment_methods(self):
        methods = super(AccountJournal, self)._default_outbound_payment_methods()
        return methods + self.env.ref('account_check_printing.account_payment_method_check')

    @api.model
    def _enable_check_printing_on_bank_journals(self):
        """ Enables check printing payment method and add a check sequence on bank journals.
            Called upon module installation via data file.
        """
        check_printing = self.env.ref('account_check_printing.account_payment_method_check')
        bank_journals = self.search([('type', '=', 'bank')])
        for bank_journal in bank_journals:
            bank_journal._create_check_sequence()
            bank_journal.write({
                'outbound_payment_method_ids': [(4, check_printing.id, None)],
            })

    def get_journal_dashboard_datas(self):
        domain_checks_to_print = [
            ('journal_id', '=', self.id),
            ('payment_method_id.code', '=', 'check_printing'),
            ('state', '=', 'posted')
        ]
        return dict(
            super(AccountJournal, self).get_journal_dashboard_datas(),
            num_checks_to_print=self.env['account.payment'].search_count(domain_checks_to_print),
        )

    def action_checks_to_print(self):
        return {
            'name': _('Checks to Print'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form,graph',
            'res_model': 'account.payment',
            'context': dict(
                self.env.context,
                search_default_checks_to_send=1,
                journal_id=self.id,
                default_journal_id=self.id,
                default_payment_type='outbound',
                default_payment_method_id=self.env.ref('account_check_printing.account_payment_method_check').id,
            ),
        }
