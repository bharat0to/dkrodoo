
# -*- coding: utf-8 -*-
import re, json, mimetypes, base64
from collections import defaultdict
from odoo import http, Command
from odoo.http import request, Controller
import requests
import logging
import json 

_logger = logging.getLogger(__name__)

IR_CONFIG_PARAM_EMAIL_TO = 'vrs_bot_mail_to'

def get_count_of(field_name, value, and_domain=None):
    and_domain = and_domain or list()
    return request.env['res.partner'].sudo().with_context(
            show_all_res_partner=True).search(and_domain + [(field_name, '=ilike', value), ('is_vendor', '=', True)], count=True)

def do_dup_check_on(field_name, value, and_domain=None):
    c = get_count_of(field_name, value, and_domain)
    _logger.info(f"YM_API dup check on {and_domain} {field_name}: {value} = {c}")
    return { 'duplicate': c != 0 }

def dup_old_vat_check(vendor_id, gstin):
    return gstin == request.env['res.partner'].sudo().browse(vendor_id).old_vat

def parse_gst_pan_address(address, raise_exception=False):
    pattern = r'^(?P<address_line_1>.*),\s*(?P<address_line_2>.*),\s*(?P<city>.*),\s*(?P<state>.*),\s*(?P<pin_code>\d{6})$'
    match = re.match(pattern, address)
    if match:
        return {
            'address_line_1': match.group('address_line_1').strip(),
            'address_line_2': match.group('address_line_2').strip(),
            'city': match.group('city').strip(),
            'state': match.group('state').strip(),
            'country': 'India',
            'pin_code': match.group('pin_code').strip()
        }
    else:
        _logger.info(f"VRSYM_PARSE_ADD_GST_ADDR_FAIL: {address}")
        if raise_exception:
            raise InvalidAddressFound()
        return None

def get_account_name(cheque_data, verify_data):
    cheque_name = cheque_data['account_name']
    if not cheque_name and verify_data:
        cheque_name = verify_data['result']['name_at_bank']
    return cheque_name

def _fix_state_name_gov_in(state_name):
    _state_name_map = {
        'ANDAMAN AND NICOBAR ISLANDS' : 'ANDAMAN AND NICOBAR',
        'CHHATTISGARH': 'CHATTISGARH',
        'ODISHA': 'ORISSA',
        'THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU': 'DADRA AND NAGAR HAVELI'
    }
    return _state_name_map.get(state_name.upper(), state_name)

def _check_name_score_with_pan(vendor, account_name, idfy_name_score, pan_data):
    if (idfy_name_score == -1) and pan_data:
        if vendor._compare_company_name(pan_data["result"]["extraction_output"]["name_on_card"], account_name):
            _logger.info(f"CNSWP: {vendor.name} {pan_data}")
            return 6 # If name dosen't match with GST but matches with PAN then don't ask for name declaration
    _logger.info(f"CNSWP RETURN: {vendor} {vendor.name} {pan_data} {idfy_name_score}")
    return idfy_name_score

class InvalidAddressFound(Exception):
    pass

class YellowMessenger(Controller):

    def _send_mail_notification(self, type, status, msg):
        email_to = request.env['ir.config_parameter'].sudo().get_param(IR_CONFIG_PARAM_EMAIL_TO, '')
        if email_to:
            subject = "VRS Bot: "
            if type == 'create' and status == 'success':
                subject += "Vendor creation successful"
            if type == 'create' and status == 'failed':
                return None # disable failure mails
                subject += "Vendor creation failed"
            if type == 'update' and status == 'success':
                subject += "Vendor updation successful"
            if type == 'update' and status == 'failed':
                return None # disable failure mails
                subject += "Vendor updation failed"
            
            _mt = request.env.ref('isha_life_vrs.vendor_create_update_success_failed_template')
            mail_values = {
                'subject': subject,
                'email_to': email_to,
            }
            _mt.with_context(message=msg).send_mail(2, email_values=mail_values)

    @http.route('/api/ym/check_dup_on_email_phone', type='json', auth='public', csrf='*')
    def check_dup_on_email(self, **kw):
        email = json.loads(request.httprequest.data).get('email')
        name = json.loads(request.httprequest.data).get('name')
        phone = json.loads(request.httprequest.data).get('phone')
        entity = 0
        if email:
            email_dup = do_dup_check_on('email', email, [('name', '=ilike', name)])
            if email_dup['duplicate']:
                entity += 1
        if phone:
            phone_dup = do_dup_check_on('phone', phone, [('name', '=ilike', name)])
            if phone_dup['duplicate']:
                entity += 2
        return { 'duplicate': entity != 0, 'entity': {0: 'none', 1: 'email', 2: 'phone', 3: 'both'}[entity] }

    @http.route('/api/check_dup_on_gst', type='json', auth='user', csrf='*')
    def check_dup_on_gst(self, **kw):
        gstin = json.loads(request.httprequest.data)['gstin']
        d = do_dup_check_on('vat', gstin, [('is_company', '=', True)])
        if not d['duplicate']:
            vendor_id = json.loads(request.httprequest.data).get('vendor_id')
            if vendor_id and dup_old_vat_check(vendor_id, gstin):
                return { 'duplicate': False }
            d = do_dup_check_on('old_vat', gstin, [('is_company', '=', True)])
        return d

    @http.route('/api/ym/check_dup_on_vendor', type='json', auth='user', csrf='*')
    def check_dup_on_pan(self, **kw):
        data = json.loads(request.httprequest.data)
        entity = data.get('entity') # email, pan_no, vat, account_number
        value = data.get('value')
        if entity and value:
            if entity == 'account_number':
                c = request.env['res.partner.bank'].sudo().search_count([('acc_number', '=', value), ('partner_id.is_vendor', '=', True), ('partner_id.is_company', '=', True)])
                return { 'duplicate': c != 0 }
            return do_dup_check_on(entity, value, [('is_company', '=', True)])
        return {}
    
    @http.route("/api/ym/pincode_to_state", type='json', auth='user', csrf='*')
    def pincode_to_state(self, **kw):
        pincode = json.loads(request.httprequest.data)['pincode']
        return {
            'state_names': request.env['in.pincode.state'].sudo().search([('pincode', '=', pincode)]).mapped('state_name')
        }

    @http.route('/api/ym/verify_vendor', type='json', methods=['POST'], auth='user', csrf='*')
    def verify_vendor(self, **kw):
        data = json.loads(request.httprequest.data)
        entity = data['entity']
        value = data['value']
        domain = None 
        vendor = None 
        # TODO is acc_number, pan_no, vat unique to avoid singleton error?
        if entity == 'account_number':
            vendor = request.env['res.partner.bank'].sudo().search([('acc_number', '=', value), ('partner_id.is_vendor', '=', True), ('partner_id.is_company', '=', True)]).partner_id
        else:
            if entity == 'pan_number':
                domain = [('pan_no', '=', value), ('is_vendor', '=', True), ('is_company','=',True)]
            else: # entity == 'gst_number':
                domain = [('vat', '=', value), ('is_vendor', '=', True), ('is_company', '=', True)]
            vendor = request.env['res.partner'].with_context(show_all_res_partner=True).sudo().search(domain)
        return { 
            'is_existing_vendor': bool(vendor),
            'vendor_id': vendor.id if vendor else None,
            'vendor_name': vendor.name if vendor else None
        }
    
    @http.route('/api/ym/vendor_has_gst', type='json', methods=['GET'], auth='user', csrf='*')
    def vendor_has_gst(self, **kw):
        data = json.loads(request.httprequest.data)
        vendor = request.env['res.partner'].sudo().browse(data['vendor_id'])
        if vendor.exists():
            return { 'has_gst': bool(vendor.vat) }
        raise Exception("Invalid vendor id provided")

    def _get_primary_dept(self, fin_dept_type):
        return request.env['hr.department'].search([('fin_dept_type', '=', fin_dept_type )], limit=1).id

    def _get_associated_depts(self):
        dept_id = request.env.user.defult_department_id
        if dept_id:
            return [Command.link(dept_id.id)]
        return []

    def _create_contact_for_vendor(self, vendor, pan_name):
        if pan_name != vendor.name:
            contact_data = {
                'name': pan_name,
                'parent_id': vendor.id,
                'is_vendor': True,
                'state': 'draft',
                'email': vendor.email,
                'phone': vendor.phone,
                'vat': vendor.vat,
                'pan_no': vendor.pan_no,
                'street': vendor.street,
                'street2': vendor.street2,
                'zip': vendor.zip,
                'city': vendor.city,
                'country_id': vendor.country_id.id,
                'state_id': vendor.state_id.id,
            }
            request.env['res.partner'].sudo().create(contact_data)

    @http.route(['/api/ym/new_vendor'], type='json', auth='user', csrf='*')
    def new_vendor(self, **kw):
        try:
            data = json.loads(request.httprequest.data)
            _logger.info(f"YM_API new_vendor: , {kw} - {data}")
            drafted_response = None
            idfy_name_score = data['idfy_name_score'] if data.get('idfy_name_score') else -1
            
            vendor_data = {
                'is_vendor': True,
                'company_type': 'company',
                'primary_dep_id': self._get_primary_dept(data['primary_department']),
                'department_ids': self._get_associated_depts(),
                'state': 'done'
            }
            if idfy_name_score == 2:
                vendor_data['state'] = 'draft'
                drafted_response = " Vendor name needs to be verified manually"

            if data.get('email'):
                vendor_data['email'] = data['email'].lower()
            if data.get('phone'):
                vendor_data['phone'] = data['phone']
            if data.get('pan_data'):
                vendor_data['pan_no'] = data['pan_data']['result']['extraction_output']['id_number']
            if data.get('gst_data'):
                vendor_data['vat'] = data['gst_data']['result']['extraction_output']['gstin']
                parsed_address = parse_gst_pan_address(
                    data['gst_data']['result']['extraction_output']['address'])
                if parsed_address:
                    vendor_data.update(self._extract_address(parsed_address))
                else:
                    vendor_data['state'] = 'draft'
                    drafted_response = "Invalid Address received in GST"
            if data.get("address_data"):
                vendor_data.update(self._extract_address(data['address_data']))

            if data.get('given_vendor_name'):
                vendor_data['name'] = data['given_vendor_name']
            else:
                raise Exception("Vendor name is not provided")
            # elif data.get('gst_data'):
            #     vendor_data['name'] = data['gst_data']['result']['extraction_output']['trade_name']
            # elif data.get('pan_data'):
            #     vendor_data['name'] = data['pan_data']['result']['extraction_output']['name_on_card']
            # elif data.get('cheque_data'):
            #     vendor_data['name'] = get_account_name(data['cheque_data']['result']['extraction_output'], data.get('account_verify_data'))
            # elif data.get('name'):
            #     vendor_data['name'] = data['name']
            
            # if not vendor_data.get('name'):
            #     # return self.error_response(f'Error: {e}')
            
            vendor = request.env['res.partner'].sudo().create(vendor_data)
            _logger.info(f"id of created vendor is {vendor.id}")
            if data.get('pan_file'):
                add_idproof_to_vendor_from_url(vendor, "Pan Card", 'PAN Card', data['pan_file'])
            if data.get('gst_file'):
                add_idproof_to_vendor_from_url(vendor, "GSTIN", 'GSTIN', data['gst_file'])
            if data.get('cheque_file') or data.get('account_verify_data'):
                _logger.info(f"cheque file-- {data.get('cheque_file')}")
                _logger.info (f"account verify data {data.get('account_verify_data')}")
                if data.get('cheque_data'):
                    bank_data = data['cheque_data']['result']['extraction_output']
                else:
                    bank_data = defaultdict(lambda:"")
                _resp = self.add_bank_account(vendor, bank_data, data['correct_acc_number'], data.get('account_verify_data', None), name_mismatch_reason=data.get('declared_name'), idfy_name_score=idfy_name_score)
                if 'ym_error_message' in _resp:
                    raise Exception(f"FAILED TO ADD BANK ACCOUNT  NMAE MISMATCH: {_resp}")
                if data.get('cheque_file'):
                    add_idproof_to_vendor_from_url(vendor, "Cancelled Cheque", 'Cancelled Cheque', data['cheque_file'])

            if data.get('declaration_form_url'):
                add_idproof_to_vendor_from_url(vendor, "Vendor Form", 'Vendor Form', data['declaration_form_url'])
            if data.get('name_mismatch_file'):
                add_idproof_to_vendor_from_url(vendor, "Name Mismatch Declaration", 'Name Mismatch Declaration', data['name_mismatch_file'])
            
            if data.get('pan_data') and data.get('gst_data'):
                pan_name = data['pan_data']['result']['extraction_output']['name_on_card']
                if pan_name and (pan_name != vendor.name):
                    self._create_contact_for_vendor(vendor, pan_name)
            _msg = f', Needs manual Approval due to {drafted_response}' if drafted_response else ''
            self._send_mail_notification('create', 'success', f'Vendor creation successful: {vendor_data["name"]}{_msg}')
            return { 'success': True, 'drafted_response': drafted_response }          
        except Exception as e:
            request.env.cr.rollback()
            self._send_mail_notification('create', 'failed', str(e))
            _logger.exception(f"YM_CREATE_VENDOR: {e}")
            return self.error_response(f'Error: {e}')
    
    def _ym_update_vendor(self, vendor, data):
        idfy_name_score = data['idfy_name_score'] if data.get('idfy_name_score') else -1
        if data.get('name_mismatch_file'):
            add_idproof_to_vendor_from_url(vendor, "Name Mismatch Declaration", 'Name Mismatch Declaration', data['name_mismatch_file'])
        if data['update_type'] == 'add_bank_account': 
            _resp = self.add_bank_account(vendor, data.get('bank_data', defaultdict(lambda: '')), data.get('correct_acc_number'), data.get('account_verify_data', None), name_mismatch_reason=data.get('declared_name'), idfy_name_score=idfy_name_score)
            if 'ym_error_message' not in _resp and data.get('cheque_file'):
                add_idproof_to_vendor_from_url(vendor, "Cancelled Cheque", 'Cancelled Cheque', data['cheque_file'])
            return _resp
        # elif data['update_type'] == 'remove_bank_account':
        #     # TODO need to remove :pray: in ishafoundation menu
        #     return self.remove_bank_account(vendor, data['acc_number'])
        elif data['update_type'] == 'update_address':
            return self.update_address(vendor, data['address_data'])
        elif data['update_type'] == 'add_gst':
            add_idproof_to_vendor_from_url(vendor, "GSTIN", 'GSTIN', data['gst_file'])
            return self.add_gst(vendor, data['gst_data'], name_mismatch=bool(data.get('name_mismatch_file')), idfy_name_score=idfy_name_score)
        elif data['update_type'] == 'remove_gst':
            return self.remove_gst(vendor)

    @http.route(['/api/ym/update_vendor'], type='json', auth='user', csrf='*')
    def update_vendor(self, **kw):
        try:
            data = json.loads(request.httprequest.data)
            _logger.info(f"YM_API DATA: , {json.dumps(data, indent=4)}")
            vendor_id = data['vendor_id']
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if vendor.exists():
                resp = self._ym_update_vendor(vendor, data)
                if resp:
                    if resp.get('ym_success_message'):
                        self._send_mail_notification('update', 'success', f"Vendor ({vendor.name}) update successfull\n{resp.get('ym_success_message')}")
                    return resp
            raise Exception(f"Invalid request update type not found {data.get('update_type')}")
        except Exception as e:
            request.env.cr.rollback()
            self._send_mail_notification('update', 'failed', f"Vendor ({vendor.name}) update failed\n{e}")
            _logger.exception(f"YM_UPDATE_VENDOR: {e}")
            return self.error_response(f'Error: {e}')

    def _extract_address(self, address_data):
        vals = {
            'street': address_data['address_line_1'],
            'street2': address_data['address_line_2'],
            'zip': address_data['pin_code'],
            'city': address_data['city'],
            'country_id': 104,
        }
        if address_data.get('res_state_id'):
            vals['state_id'] = address_data['res_state_id']
        else:
            state = address_data['state']
            state = _fix_state_name_gov_in(state)
            state_id = request.env['res.country.state'].sudo().search([('country_id', '=', 104), ('name', '=ilike', state)])
            if state_id.exists():
                vals['state_id'] = state_id.id
            else:
                # TODO show options?
                raise Exception(f"Invalid state name: {state}")
        return vals
    
    def update_address(self, vendor, address_data):
        _data = self._extract_address(address_data)
        _logger.info(f"ADDR: UPDATE: {_data}")
        vendor.write(_data)
        return self.success_response('Address Updated')

    def add_gst(self, vendor, gst_data, name_mismatch=None, idfy_name_score=-1):
        if vendor.vat:
            return self.error_response(f'Vendor already has GST : {vendor.vat} . Please remove it before adding the new GST')
        if vendor.pan_no and (vendor.pan_no != gst_data['pan_number']):
            return self.error_response(f'The PAN number associated with given GST does not match the existing PAN number of vendor')
        if not name_mismatch and not vendor._compare_company_name(gst_data['trade_name']) and not idfy_name_score >=2:
            return self.error_response(f'GST Trade name ({gst_data["trade_name"]}) and vendor name ({vendor.name}) mismatch', name_mismatch=True)
        try:
            if not vendor.state_id:
                parsed_address = parse_gst_pan_address(gst_data['address'], raise_exception=True)
                if parsed_address:
                    self.update_address(vendor, parsed_address)
            vendor.write({ 'vat': gst_data['gstin'] })
        except InvalidAddressFound as e:
            request.env.cr.rollback()
            return self.error_response(f'Failed adding the GST due to Invalid address received. Please update GST manually')
        except Exception as e:
            request.env.cr.rollback()
            _logger.exception(f"YM_ADD_GST_ERROR: {e}")
            return self.error_response(f'Failed adding the GST {e}')
        return self.success_response(f'Added GST for vendor')

    def remove_gst(self, vendor):
        gst_no = None
        if vendor.vat:
            gst_no = vendor.vat
            vendor.write({ 'vat': None })
            return self.success_response(f"Removed GST: {gst_no}")
        return self.success_response(f'No GST to remove')

    def _get_vendor_bank_account(self, vendor, acc_no):
        # TODO will acc_number and res_partner be unique? can acc_number be same for multiple vendors?
        return request.env['res.partner.bank'].sudo().search([('acc_number', '=', acc_no), ('partner_id', '=', vendor.id), ('partner_id.is_company', '=', True)])

    def remove_bank_account(self, vendor, acc_no):
        bank_of_account_id = self._get_vendor_bank_account(vendor, acc_no)
        _logger.info(f"BOA id: {bank_of_account_id}, {vendor}, {acc_no}")
        if bank_of_account_id:
            vendor.write({ 'bank_ids': [Command.unlink(bank_of_account_id.id)] })
            # bank_of_account_id.unlink()
            return self.success_response(f'Bank account is removed successfully')
        else:
            return self.error_response(f'Bank account does not exists')
    
    def add_bank_account(self, vendor, bank_data, correct_acc_number, account_verify_data=None, name_mismatch_reason=None, idfy_name_score=-1):
        # TODO single for sulaba with api to get bank details
        if account_verify_data:
            ifsc_code = account_verify_data['result']['ifsc_code']
        else:
            ifsc_code = bank_data['ifsc_code']
        bank_id = request.env['res.bank'].sudo().search([('bic', '=', ifsc_code)])
        if not bank_id:
            bank_id = request.env['res.bank'].sudo().create({
                'bic': ifsc_code,
                'name': bank_data['bank_name'],
                'street': bank_data['bank_address']
            })
        
        if(correct_acc_number):
            acc_no = correct_acc_number
        else:
            acc_no = bank_data['account_no']
            if account_verify_data:
                acc_no = account_verify_data['result']['bank_account_number']

        bank_of_account_id = self._get_vendor_bank_account(vendor, acc_no)
        if not bank_of_account_id:
            account_name = get_account_name(bank_data, account_verify_data)
            if not name_mismatch_reason and not vendor._compare_company_name(account_name) and not (idfy_name_score >= 2):
                return self.error_response(f'Account name ({account_name}) and vendor name ({vendor.name}) mismatch', name_mismatch=True)
            vendor.write({
                'bank_ids': [
                    Command.create({
                        'rpb_tally_ledger_name': account_name,
                        'acc_holder_name': account_name,
                        'acc_number': acc_no,
                        'bank_id': bank_id.id,
                        'reason_acc_holder_mismatch': name_mismatch_reason if name_mismatch_reason else False,
                        'idfy_name_score': idfy_name_score
                    })
                ]
            })
            return self.success_response(f'Bank account is added successfully')
        else:
            return self.error_response(f'Bank with same account number alread exists for vendor')

    def success_response(self, msg, **kw):
        return { 'ym_success_message': msg, **kw }
    
    def error_response(self, msg, **kw):
        return { 'ym_error_message': msg, **kw }

def add_idproof_to_vendor_from_url(vendor, doc_name, doc_type_name, url):
    datas = get_binary_file_data_from_url(url)
    doc_att = request.env['ir.attachment'].sudo().create({
                                'name': f"{doc_name}.{url.split('.')[-1]}",
                                'datas': datas,
                                'url': url,
                                'mimetype': mimetypes.guess_type(url)[0],
                                'res_model': 'res.partner',
                                'res_id': vendor.id
                            })
    _logger.info(f"the document_type_name trying to be inserted is {doc_type_name}")
    doc_type_id = request.env['documenttype'].sudo().search([('name','=',doc_type_name)], order='id desc', limit=1).id
    _logger.info(f"the doctype id  = *************{doc_type_id}*************")
    vendor.write({
        'proof_ids': [ Command.create({
            'idproof_id': vendor.id,
            'idproof_document_type': doc_type_id,
            'attached_file': doc_att,
        })]
    })

def get_binary_file_data_from_url(url):
    return base64.b64encode(requests.get(url).content)
