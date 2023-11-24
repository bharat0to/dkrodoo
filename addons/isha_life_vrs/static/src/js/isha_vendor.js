odoo.define('isha_life_vrs.isha_vendor', function (require) {
'use strict';

var publicWidget = require('web.public.widget');

publicWidget.registry.portalDetails = publicWidget.Widget.extend({
    selector: '.o_portal_details',
    events: {
        'change select[name="state_id"]': '_onStateChange',
        'change select[name="country_id"]': '_onCountryChange',
        'change select[name="gst_status"]': '_onGSTStatusChange',
    },

    /**
     * @override
     */
    start: function () {
        var def = this._super.apply(this, arguments);

        this.$state = this.$('select[name="state_id"]');
        this.$stateOptions = this.$state.filter(':enabled').find('option:not(:first)');
        console.log("state ptions are totl[start] " + this.$stateOptions.show().length);
        this._adaptAddressForm();

        this.$gst = this.$('input[name="vat"]');
        this.$decl_text = this.$('input[name="declaration_text"]');
        this.$decl_text_lbl = this.$('h6[name="lbl_declaration_text"]');
        this._adaptGSTPattern();

        this.$gststatus = this.$('select[name="gst_status"]');
        this._adaptGSTStatus();

        return def;
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _adaptAddressForm: function () {
        console.log('country change')
        var $country = this.$('select[name="country_id"]');
        var countryID = ($country.val() || 0);
        this.$stateOptions.detach();
        var $displayedState = this.$stateOptions.filter('[data-country_id=' + countryID + ']');
        var nb = $displayedState.appendTo(this.$state).show().length;
        this.$state.parent().toggle(nb >= 1);
    },
    _adaptGSTPattern: function () {
        //this.$gstOptions.detach();
        console.log("GST t-attf-Pattern is " + this.$gst.attr('t-attf-pattern'));
        console.log("GST Pattern is " + this.$gst.attr('pattern'));
        console.log("State TIN is " + this.$state.find(":selected").attr('data-l10n_in_tin'));
        var state_tin = this.$state.find(":selected").attr('data-l10n_in_tin');
        this.$gst.attr('pattern','^(' + state_tin + ')([a-zA-Z]{5}[0-9]{4}[a-zA-Z]{1}[1-9a-zA-Z]{1}[zZ]{1}[0-9a-zA-Z]{1})?$')
        console.log("GST Pattern changed to " + this.$gst.attr('pattern'));
    },
    _adaptGSTStatus: function () {
        console.log("GST Status value is " + this.$gststatus.find(":selected").attr('gst_mandatory'));
        var gst_mandatory = this.$gststatus.find(":selected").attr('gst_mandatory');
        if(gst_mandatory === undefined) {this.$gst.attr('required',false);gst_mandatory="";}
        else{this.$gst.attr('required',true);}
        console.log("GST mandtoriiess to be set is " + gst_mandatory);
        console.log("GST required attr changed to " + this.$gst.attr('required'));

        var gst_decl_text = this.$gststatus.find(":selected").attr('gst_declaration_text');
        if(gst_decl_text === undefined) {gst_decl_text="";}
        this.$decl_text.attr('value',gst_decl_text);
        this.$decl_text_lbl.text(gst_decl_text);
        console.log("GST dclr text attr changed to " + this.$decl_text_lbl.text());
        console.log("HIDDEN GST dclr text attr changed to " + this.$decl_text.attr('value'));
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onCountryChange: function () {
        this._adaptAddressForm();
    },
    _onStateChange: function () {
        console.log("state changed...");
        this._adaptGSTPattern();
    },
    _onGSTStatusChange: function () {
        console.log("GST status changed...");
        this._adaptGSTStatus();
    },
});

publicWidget.registry.portalSearchPanel = publicWidget.Widget.extend({
    selector: '.o_portal_search_panel',
    events: {
        'click .search-submit': '_onSearchSubmitClick',
        'click .dropdown-item': '_onDropdownItemClick',
        'keyup input[name="search"]': '_onSearchInputKeyup',
    },

    /**
     * @override
     */
    start: function () {
        var def = this._super.apply(this, arguments);
        this._adaptSearchLabel(this.$('.dropdown-item.active'));
        return def;
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _adaptSearchLabel: function (elem) {
        var $label = $(elem).clone();
        $label.find('span.nolabel').remove();
        this.$('input[name="search"]').attr('placeholder', $label.text().trim());
    },
    /**
     * @private
     */
    _search: function () {
        var search = $.deparam(window.location.search.substring(1));
        search['search_in'] = this.$('.dropdown-item.active').attr('href').replace('#', '');
        search['search'] = this.$('input[name="search"]').val();
        window.location.search = $.param(search);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onSearchSubmitClick: function () {
        this._search();
    },
    /**
     * @private
     */
    _onDropdownItemClick: function (ev) {
        ev.preventDefault();
        var $item = $(ev.currentTarget);
        $item.closest('.dropdown-menu').find('.dropdown-item').removeClass('active');
        $item.addClass('active');

        this._adaptSearchLabel(ev.currentTarget);
    },
    /**
     * @private
     */
    _onSearchInputKeyup: function (ev) {
        if (ev.keyCode === $.ui.keyCode.ENTER) {
            this._search();
        }
    },
});
});
