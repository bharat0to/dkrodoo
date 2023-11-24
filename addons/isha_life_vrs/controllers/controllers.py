# -*- coding: utf-8 -*-
import odoo
from odoo import http, _
from datetime import datetime, date
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import base64
import json
from dateutil.relativedelta import relativedelta
from odoo.http import request
from odoo.addons.web.controllers.main import Home, ensure_db
from odoo.exceptions import AccessError, UserError, AccessDenied
import werkzeug.urls
import werkzeug.utils
from werkzeug.exceptions import BadRequest
import logging
import requests
from odoo.exceptions import ValidationError

from odoo import registry as registry_get
from odoo import SUPERUSER_ID
from odoo.api import Environment
_logger = logging.getLogger(__name__)


class CustomerPortal(CustomerPortal):

    PARENT_MANDATORY_FIELDS = ['nature_of_company', 'gst_status','city', 'country_id', 'state_id', 'zipcode', 'declaration_acceptance']
    PARENT_OPTIONAL_FIELDS = ['pan_no', 'vat', 'proof_ids', 'acc_number', 'acc_holder_name', 'account_type',
                              'bic', 'bank_name', 'branch', 'bank_ids','is_registered_with_msme','declaration_text',
                               'phone','street','street2','reason_acc_holder_mismatch']
    PARENT_FIELDS = PARENT_MANDATORY_FIELDS + PARENT_OPTIONAL_FIELDS

    def _prepare_portal_layout_values(self):
        values = super(CustomerPortal, self)._prepare_portal_layout_values()
        _logger.info(values)
        return values

    def details_form_validate(self, data):
        error, error_message = super(CustomerPortal, self).details_form_validate(data)
        # return error, error_message
        partner = request.env.user.partner_id
        if not partner.state == 'draft':
            error["vendor_state"] = 'error'
            error_message.append(_('Vendor details cannot be changed. Please contact us thorough helpdesk {0}'.format(partner.parent_id.state)))
        _logger.info("Errors are {0}".format(error))
        if 'vat' in error:
            del error['vat']
        if 'email' in error:
            del error['email']
        if 'name' in error:
            _logger.info("____________________________yes, name is therein error - ")
            del error['name']
        return error, error_message

    @http.route(['/my/account'], type='http', auth='user', website=True)
    def account(self, redirect=None, **post):
        if request.env.user.partner_id.is_vendor:
            values = self._prepare_portal_layout_values()
            partner = request.env.user.partner_id
            values.update({
                'error': {},
                'error_message': [],
                'success': False
            })

            if post and request.httprequest.method == 'POST':

                # Add parent fields to optional fields to pass the validatio nof unknown fields
                self.MANDATORY_BILLING_FIELDS.append('myemail')
                self.OPTIONAL_BILLING_FIELDS.append('myphone')
                #self.MANDATORY_BILLING_FIELDS.remove('vat')
                #self.OPTIONAL_BILLING_FIELDS.append('vat')
                self.MANDATORY_BILLING_FIELDS = self.MANDATORY_BILLING_FIELDS + self.PARENT_MANDATORY_FIELDS
                self.OPTIONAL_BILLING_FIELDS = self.OPTIONAL_BILLING_FIELDS + self.PARENT_OPTIONAL_FIELDS
                post.pop('new_prooftype[]', '')
                # post.pop('new_filename[]', '')
                post.pop('new_file[]', '')
                error, error_message = self.details_form_validate(post)
                values.update({'error': error, 'error_message': error_message})
                _logger.info(post)
                values.update(post)
                _logger.info("error msgss are %s", error_message)

                parent = request.env['res.partner'].sudo().search([('id', '=', partner.parent_id.id)])
                _logger.info("Partner Parent id {0}".format(partner.parent_id))

                if not error:
                    try:
                        attached_file = request.httprequest.files.getlist('new_file[]')
                    except:
                        pass

                    # attached_filename = request.httprequest.form.getlist('new_filename[]')
                    attached_prooftype = request.httprequest.form.getlist('new_prooftype[]')
                    try:
                        for proof in values.get('proof_ids').split(','):
                            _logger.info(proof)
                            attachment_sudo = self._document_check_access('idproof.attachment', int(proof)).unlink()
                            _logger.info("***************DELETED************")
                    except:
                        _logger.info("No array formed ")

                    for x in range(len(attached_file)):
                        read = attached_file[x].read()
                        _logger.info(attached_prooftype[x])

                        datas = base64.b64encode(read)
                        if datas:
                            new_attachment = request.env['ir.attachment'].sudo().create({
                                'name': attached_file[x].filename,
                                'datas': datas,
                                'res_model': 'res.partner',
                                'res_id': partner.parent_id.id
                            })

                            res_attach = request.env['idproof.attachment'].sudo().create({
                                'idproof_id': partner.parent_id.id,
                                'idproof_document_type': int(attached_prooftype[x]),
                                'attached_file': new_attachment,
                            })

                    # Remove parent fields from optional and mandatory fields to avoid updating the coany details in contacts
                    self.OPTIONAL_BILLING_FIELDS = [v for v in self.OPTIONAL_BILLING_FIELDS if
                                                    v not in self.PARENT_OPTIONAL_FIELDS]
                    self.MANDATORY_BILLING_FIELDS = [v for v in self.MANDATORY_BILLING_FIELDS if
                                                    v not in self.PARENT_MANDATORY_FIELDS]

                    try:
                        self.MANDATORY_BILLING_FIELDS.remove('email')
                    except:
                        pass
                    values = {key: post[key] for key in self.MANDATORY_BILLING_FIELDS}
                    values.update({key: post[key] for key in self.OPTIONAL_BILLING_FIELDS if key in post})
                    if 'zipcode' in values:
                        values.update({'zip': values.pop('zipcode', '')})
                    if 'myemail' in values:
                        values.update({'email': values.pop('myemail', '')})
                    if 'myphone' in values:
                        values.update({'phone': values.pop('myphone', '')})

                    pvalues = {key: post[key] for key in self.PARENT_MANDATORY_FIELDS}
                    pvalues.update({key: post[key] for key in self.PARENT_OPTIONAL_FIELDS if key in post})
                    #pvalues = {key: post[key] for key in self.PARENT_FIELDS}
                    if 'zipcode' in pvalues:
                        pvalues.update({'zip': pvalues.pop('zipcode', '')})
                    if pvalues.get('nature_of_company') == '':
                        pvalues.update({'nature_of_company': False})
                    else:
                        pvalues.update({'nature_of_company': int(pvalues.get('nature_of_company'))})
                    if pvalues.get('gst_status') == '':
                        pvalues.update({'gst_status': False})
                    else:
                        pvalues.update({'gst_status': int(pvalues.get('gst_status'))})
                    if pvalues.get('is_registered_with_msme') == '':
                        pvalues.update({'is_registered_with_msme': False})
                    #else:
                    #    pvalues.update({'is_registered_with_msme': 1})
                # if not values.get('company_name') == '':
                #     pvalues.update({'name': values.get('company_name')})

                    if pvalues.get('bic'):
                        temp_bank_id = request.env['res.bank'].sudo().search([('bic', '=', pvalues.get('bic'))], limit=1).id
                        if not temp_bank_id:
                            url = 'https://ifsc.razorpay.com/' + str(pvalues.get('bic'))
                            response = requests.get(url, verify=False)

                            if response.ok:
                                response = response.json()
                                state_obj = request.env['res.country.state'].sudo().search([('name', 'ilike', response['STATE'])],
                                                                                limit=1)
                                temp_bank_id =request.env['res.bank'].sudo().create({
                                    'name': response['BANK'],
                                    'branch_name': response['BRANCH'],
                                    'bic': response['IFSC'],
                                    'micr': response['MICR'],
                                    'street': response['ADDRESS'],
                                    'phone': response['CONTACT'],
                                    'city': response['CITY'],
                                    'state': state_obj.id,
                                    'country': state_obj.country_id.id,

                                }).id


                            else:
                                raise ValidationError(
                                    'Sorry! For this IFSC there is no Bank has been added kindly'
                                    'Contact System Administrator .')
                    else:
                        temp_bank_id = pvalues.get('bank_id')

                    bank_acc_lines = []
                    if pvalues.get('acc_number'):
                        bank_acc_lines.append((0, _, {
                                'acc_number': pvalues.get('acc_number'),
                                # 'bank_id': pvalues.get('bank_id'),
                                'acc_holder_name': pvalues.get('acc_holder_name'),
                                'account_type': pvalues.get('account_type'),
                                'bank_id': temp_bank_id,
                                'reason_acc_holder_mismatch': pvalues.get('reason_acc_holder_mismatch'),

                        }))
                    _logger.info("Bank values are {0}".format(bank_acc_lines))
                    pvalues.update({
                        'bank_ids': bank_acc_lines
                    })

                    if 'state_id' in values and values.get('state_id') == '':
                        values.update({'state_id': False})
                    if 'country_id' in values and values.get('country_id') != '':
                        values.update({'country_id': int(values.get('country_id'))})
                    if 'state_id' in values and values.get('state_id') != '':
                        values.update({'state_id': int(values.get('state_id'))})

                    _logger.info("checking for pvalue fields : %s", pvalues)
                    if 'state_id' in pvalues and pvalues.get('state_id') == '':
                        pvalues.update({'state_id': False})
                    if 'country_id' in pvalues and pvalues.get('country_id') == '':
                        pvalues.update({'country_id': False})
                    if 'country_id' in pvalues and pvalues.get('country_id') != '':
                        pvalues.update({'country_id': int(pvalues.get('country_id'))})
                    if 'state_id' in pvalues and pvalues.get('state_id') != '':
                        pvalues.update({'state_id': int(pvalues.get('state_id'))})

                    pvalues.pop('bank_id', '')
                    pvalues.pop('account_type', '')
                    pvalues.pop('acc_number', '')
                    pvalues.pop('acc_holder_name', '')
                    pvalues.pop('reason_acc_holder_mismatch', '')
                    pvalues.pop('bic')
                    pvalues.pop('bank_name')
                    pvalues.pop('branch')
    #               pvalues.pop('bank_micr_code')

                    parent = request.env['res.partner'].sudo().search([('id', '=', partner.company_id.id)])
                    if partner.parent_id.state == 'draft':
                        pvalues.pop('proof_ids', '')
                        pvalues.update({'vendor_upload': True})
                        # new addition
        #                pvalues.pop('bank_ids', '')
                        _logger.info("Values that are being updated - {0}".format(pvalues))
                        partner.parent_id.sudo().write(pvalues)

                    partner.sudo().write(values)
                    related_requests = request.env['request.request'].with_user(SUPERUSER_ID).search([('partner_id','=',partner.parent_id.id)])
                    _logger.info("requests are ==============================={0} for {1}".format(related_requests,partner.parent_id.id))
                    if related_requests:
                        _logger.info("requests found for company {0}".format(partner.parent_id.name))
                        _logger.info("======================inside earching requets==={0} {1}".format(related_requests, partner.company_id.id))
                        for r in related_requests:
                            _logger.info("=========== - {0} {1} {2}".format(r.stage_id, r.stage_id.auto_route, r.next_stage_ids))
                            for stage in r.next_stage_ids:
                                _logger.info("=========== - {0} {1}".format(stage, stage.auto_route))
                                if stage.auto_route and not stage == r.stage_id:
                                    r.write({'stage_id':stage})
                                    request.env['mail.message'].sudo().create({'message_type': "notification",
                                                        'body': "The Vendor has uploaded details that maybe relevant for this request ",
                                                        'subject': "update from helpdesk request",
                                                        'model': 'request.request',
                                                        'res_id': r.id,
                                                        })
                                    break

                    else:
                        _logger.info("no requests found")
                    values.update({"success_message": 'success'})

                    values.update({
                        "success_msg": True,
                        'error': {},
                        'error_message': [],
                    })
                    _logger.info("Success written: " + values.__str__())

    #                if redirect:
    #                    return request.redirect(redirect)
    #                return request.redirect('/my/account')

            countries = request.env['res.country'].sudo().search([])
            states = request.env['res.country.state'].sudo().search([])
            noc = request.env['company.nature'].sudo().search([])
            gsts = request.env['gst.status'].sudo().search([])
            doctypes = request.env['documenttype'].sudo().search([])
            #        bank = request.env['res.bank'].sudo().search([])
            bank = ''
            _logger.info("__________________________________GSTStatueses are {0}".format(gsts))
            _logger.info("__________________________________noc are {0}".format(noc))
            values.update({
                'partner': partner,
                'countries': countries,
                'states': states,
                'has_check_vat': hasattr(request.env['res.partner'], 'check_vat'),
                'redirect': redirect,
                'page_name': 'my_details',
                'natures_of_company': noc,
                'gst_statuses': gsts,
                'doctypes': doctypes,
                'bank_obj': bank,
                'msme_values': [{'id':'yes','name':'Yes'},{'id':'no','name':'No'},{'id':'under_process','name':'Under Process'}]
            })

            response = request.render("portal.portal_my_details", values)
            response.headers['X-Frame-Options'] = 'DENY'
            return response
        else:
            return super(CustomerPortal, self).account(redirect, **post)
    
    @http.route(['/vrs'], type='http', auth='user', website=True)
    def vrs_bot(self):
        # return "VRS BOT"
        return request.render("isha_life_vrs.yellow_ai_widget_in_request",{})
        # return request.render('http_routing.404')



