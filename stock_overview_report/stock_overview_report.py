# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution   
#    Copyright (C) 2014 credativ ltd (<http://www.credativ.co.uk>). All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp import SUPERUSER_ID
from datetime import datetime, timedelta
import pytz

class StockOverviewReport(osv.osv_memory):
    _name = 'stock.overview.report'
    _description = "Stock Overview Report"
    _rec_name = 'date'

    _columns = {
        'date': fields.datetime('Stock level date', help='The date the stock levels will be taken for. Leave blank to use the current date and time.'),
        'line_ids': fields.one2many('stock.overview.report.line', 'wizard_id', 'Stock Overview Report Lines'),
     }

    def __init__(self, pool, cr):
        res = super(StockOverviewReport, self).__init__(pool, cr)
        self._transient_max_hours = 48.0
        self._transient_max_count = False
        return res

    def _search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
        """ Use the Superuser ID here to allow all users to see all other runs of the wizard if the ACL permits """
        return super(StockOverviewReport, self)._search(cr, SUPERUSER_ID, args, offset=offset, limit=limit, order=order, context=context, count=count, access_rights_uid=access_rights_uid)

    def _get_report_fields(self):
        return ['uom_id', 'qty_available', 'virtual_available', 'incoming_qty', 'outgoing_qty', 'categ_id']

    def _prepare_data_line(self, cr, uid, data, default=None):
        if default is None:
            default = {}
        res = {}
        res.update(default)
        res.update({
                'product_id': data['id'],
                'uom_id': data.get('uom_id', [None,])[0],
                'categ_id': data.get('categ_id', [None,])[0],
                'qty_available': data.get('qty_available'),
                'virtual_available': data.get('virtual_available'),
                'incoming_qty': data.get('incoming_qty'),
                'outgoing_qty': data.get('outgoing_qty'),
            })
        return res

    def _view(self, cr, uid, id, context=None):
        user = self.pool.get("res.users").read(cr, uid, uid, ['partner_id'], context=context)
        user_timezone = self.pool.get("res.partner").read(cr, uid, user['partner_id'][0],['tz'], context=context)['tz']
        if not user_timezone:
            user_timezone = 'UTC'

        wizard = self.browse(cr, uid, id, context=context)

        cr.execute('select id from ir_ui_view where model=%s and type=%s', ('stock.overview.report.line', 'tree'))
        view_ids = cr.fetchone()
        view_id = view_ids and view_ids[0] or False

        cr.execute('select id from ir_ui_view where model=%s and type=%s', ('stock.overview.report.line', 'search'))
        search_ids = cr.fetchone()
        search_id = search_ids and search_ids[0] or False

        return {
            'domain': "[('wizard_id','=',%d)]" % (id,),
            'name': _('Stock Overview Report for %s - %s') % (wizard.date, user_timezone),
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'stock.overview.report.line',
            'views': [(view_id, 'tree'),],
            'search_view_id': search_id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'limit': 200,
            'context': '{"search_default_has_stock": True, "product_display_format": "code"}',
        }

    def view_or_populate_lines(self, cr, uid, ids, context=None):
        for wizard in self.browse(cr, uid, ids, context=context):
            if not wizard.date:
                date_start = datetime.now().strftime('%Y-%m-%d')
                date_end = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                wizard_ids = self.search(cr, uid, [('date', '>=', date_start), ('date', '<=', date_end)], order='date desc', context=context)
                if wizard_ids:
                    return self._view(cr, uid, wizard_ids[0], context=context)
            return self.populate_lines(cr, uid, [wizard.id], context=context)

    def populate_lines(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        company_obj = self.pool.get('res.company')
        warehouse_obj = self.pool.get('stock.warehouse')
        product_obj = self.pool.get('product.product')
        line_obj = self.pool.get('stock.overview.report.line')

        res = {'type': 'ir.actions.act_window_close'}

        for wizard in self.browse(cr, uid, ids, context=context):
            if wizard.line_ids:
                line_obj.unlink(cr, uid, [x.id for x in wizard.line_ids], context=context)

            user = self.pool.get("res.users").read(cr, uid, uid, ['partner_id'], context=context)
            user_timezone = self.pool.get("res.partner").read(cr, uid, user['partner_id'][0],['tz'], context=context)['tz']
            if not user_timezone:
                user_timezone = 'UTC'
            if wizard.date:
                date = datetime.strptime(wizard.date, DEFAULT_SERVER_DATETIME_FORMAT)
                local_date = pytz.utc.localize(date, is_dst=None).astimezone(pytz.timezone(user_timezone))
            else:
                self.write(cr, uid, [wizard.id], {'date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)}, context=context)
                local_date = datetime.now(pytz.timezone(user_timezone))
            sql_mode = self.pool.get('ir.config_parameter').get_param(cr, uid, 'stock.overview.report.sql_mode')
            if sql_mode == 'True':
                field_names, insert_query, insert_params, with_query, with_params, select_query, select_params, from_query = self._get_sql(cr, uid, ids, wizard, context=None)
                cr.execute(with_query + insert_query + select_query + from_query, with_params + insert_params + select_params)
            else:
                for company_id in company_obj.search(cr, uid, [], context=context):
                    for warehouse_id in warehouse_obj.search(cr, uid, [('company_id', '=', company_id),], context=context):
                        ctx = context.copy()
                        ctx.update({'shop': False, 'warehouse': warehouse_id, 'location': False,
                                    'to_date': wizard.date or False})
                        product_ids = product_obj.search(cr, uid, [], context=context)
                        for product in product_obj.read(cr, uid, product_ids, self._get_report_fields(), context=ctx):
                            data = self._prepare_data_line(cr, uid, product, {
                                    'wizard_id': wizard.id,
                                    'company_id': company_id,
                                    'warehouse_id': warehouse_id,
                                })
                            line_obj.create(cr, uid, data, context=context)

            res = self._view(cr, uid, wizard.id, context=context)
        return res

    def _get_sql(self, cr, uid, ids, wizard, context=None):
        if context is None:
            context = {}

        field_names = ['create_date',
                        'create_uid',
                        'wizard_id',
                        'product_id',
                        'categ_id',
                        'company_id',
                        'warehouse_id',
                        'uom_id',
                        'qty_available',
                        'virtual_available',
                        'incoming_qty',
                        'outgoing_qty',]

        insert_query = " INSERT INTO stock_overview_report_line (" + ",".join(field_names) + ")"
        insert_params = []

        with_where_query = ""
        if wizard.date:
            with_where_query = " AND sm.date < %s "
        with_query = """ WITH RECURSIVE locations(parent_id, child_id) AS (
                            SELECT sl.location_id, sl.id FROM stock_location sl
                            UNION
                            SELECT sl.id, sl.id FROM stock_location sl
                            UNION
                            SELECT l.parent_id, sl.id FROM stock_location sl
                            INNER JOIN locations l ON sl.location_id = l.child_id
                            AND l.parent_id IS NOT NULL
                        ), stock_incoming_done AS (
                            SELECT
                                sm.product_id,
                                SUM(sm.product_qty) product_qty,
                                sw.id warehouse_id
                            FROM stock_warehouse sw
                            INNER JOIN stock_move sm
                                ON sm.location_dest_id IN (SELECT child_id FROM locations WHERE parent_id = sw.lot_stock_id)
                                AND sm.location_id NOT IN (SELECT child_id FROM locations WHERE parent_id = sw.lot_stock_id)
                                AND sm.state IN ('done')
                                """+with_where_query+"""
                            GROUP BY sm.product_id, sw.id
                        ), stock_outgoing_done AS (
                            SELECT
                                sm.product_id,
                                SUM(sm.product_qty) product_qty,
                                sw.id warehouse_id
                            FROM stock_warehouse sw
                            INNER JOIN stock_move sm
                                ON sm.location_dest_id NOT IN (SELECT child_id FROM locations WHERE parent_id = sw.lot_stock_id)
                                AND sm.location_id IN (SELECT child_id FROM locations WHERE parent_id = sw.lot_stock_id)
                                AND sm.state IN ('done')
                                """+with_where_query+"""
                            GROUP BY sm.product_id, sw.id
                        ), stock_incoming_pending AS (
                            SELECT
                                sm.product_id,
                                SUM(sm.product_qty) product_qty,
                                sw.id warehouse_id
                            FROM stock_warehouse sw
                            INNER JOIN stock_move sm
                                ON sm.location_dest_id IN (SELECT child_id FROM locations WHERE parent_id = sw.lot_stock_id)
                                AND sm.location_id NOT IN (SELECT child_id FROM locations WHERE parent_id = sw.lot_stock_id)
                                AND sm.state IN ('confirmed', 'assigned', 'waiting')
                                """+with_where_query+"""
                            GROUP BY sm.product_id, sw.id
                        ), stock_outgoing_pending AS (
                            SELECT
                                sm.product_id,
                                SUM(sm.product_qty) product_qty,
                                sw.id warehouse_id
                            FROM stock_warehouse sw
                            INNER JOIN stock_move sm
                                ON sm.location_dest_id NOT IN (SELECT child_id FROM locations WHERE parent_id = sw.lot_stock_id)
                                AND sm.location_id IN (SELECT child_id FROM locations WHERE parent_id = sw.lot_stock_id)
                                AND sm.state IN ('confirmed', 'assigned', 'waiting')
                                """+with_where_query+"""
                            GROUP BY sm.product_id, sw.id
                        )"""
        with_params = []
        if wizard.date:
            with_params = [wizard.date, wizard.date, wizard.date, wizard.date]

        select_query = """ SELECT NOW(), %s, %s, pp.id, pt.categ_id, rc.id, sw.id, pt.uom_id,
                        COALESCE(in_done.product_qty, 0.0) - COALESCE(out_done.product_qty, 0.0) qty_available,
                        COALESCE(in_done.product_qty, 0.0) - COALESCE(out_done.product_qty, 0.0)
                            + COALESCE(in_pending.product_qty, 0.0) - COALESCE(out_pending.product_qty, 0.0) virtual_available,
                        COALESCE(in_pending.product_qty, 0.0) incoming_qty,
                        -COALESCE(out_pending.product_qty, 0.0) outgoing_qty
        """
        select_params = [uid, wizard.id]

        from_query = """ FROM res_company rc
                        INNER JOIN stock_warehouse sw
                            ON sw.company_id = rc.id
                        CROSS JOIN product_product pp
                        INNER JOIN product_template pt
                            ON pp.product_tmpl_id = pt.id
                        LEFT OUTER JOIN stock_incoming_done in_done ON in_done.product_id = pp.id AND in_done.warehouse_id = sw.id
                        LEFT OUTER JOIN stock_outgoing_done out_done ON out_done.product_id = pp.id AND out_done.warehouse_id = sw.id
                        LEFT OUTER JOIN stock_incoming_pending in_pending ON in_pending.product_id = pp.id AND in_pending.warehouse_id = sw.id
                        LEFT OUTER JOIN stock_outgoing_pending out_pending ON out_pending.product_id = pp.id AND out_pending.warehouse_id = sw.id
                        """

        return field_names, insert_query, insert_params, with_query, with_params, select_query, select_params, from_query

    def autopopulate(self, cr, uid, context=None):
        wizard_id = self.create(cr, uid, {}, context=context)
        self.populate_lines(cr, uid, [wizard_id], context=context)

class StockOverviewReportLine(osv.osv_memory):
    _name = 'stock.overview.report.line'
    _description = "Stock Overview Report Line"
    _rec_name = 'product_id'

    def __init__(self, pool, cr):
        res = super(StockOverviewReportLine, self).__init__(pool, cr)
        self._transient_max_hours = 48.0
        self._transient_max_count = False
        return res

    def _search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
        """ Use the Superuser ID here to allow all users to see all other runs of the wizard if the ACL permits """
        return super(StockOverviewReportLine, self)._search(cr, SUPERUSER_ID, args, offset=offset, limit=limit, order=order, context=context, count=count, access_rights_uid=access_rights_uid)

    _columns = {
        'wizard_id': fields.many2one('stock.overview.report', 'Stock Overview Report'),
        'product_id': fields.many2one('product.product', 'Product', select=True),
        'categ_id': fields.many2one('product.category', string='Primary Category', readonly=True),
        'categ_ids': fields.related('product_id', 'categ_ids', type='many2many', relation='product.category', string='Product Categories', readonly=True),
        'company_id': fields.many2one('res.company', 'Company'),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse'),
        'uom_id': fields.many2one('product.uom', 'UoM'),
        'qty_available': fields.float('Quantity On Hand', digits_compute=dp.get_precision('Product Unit of Measure'),
            help="Current quantity of products.\n"
                 "In a context with a single Stock Location, this includes "
                 "goods stored at this Location, or any of its children.\n"
                 "In a context with a single Warehouse, this includes "
                 "goods stored in the Stock Location of this Warehouse, or any "
                 "of its children.\n"
                 "In a context with a single Shop, this includes goods "
                 "stored in the Stock Location of the Warehouse of this Shop, "
                 "or any of its children.\n"
                 "Otherwise, this includes goods stored in any Stock Location "
                 "with 'internal' type."),
        'virtual_available': fields.float('Forecasted Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),
            help="Forecast quantity (computed as Quantity On Hand "
                 "- Outgoing + Incoming)\n"
                 "In a context with a single Stock Location, this includes "
                 "goods stored in this location, or any of its children.\n"
                 "In a context with a single Warehouse, this includes "
                 "goods stored in the Stock Location of this Warehouse, or any "
                 "of its children.\n"
                 "In a context with a single Shop, this includes goods "
                 "stored in the Stock Location of the Warehouse of this Shop, "
                 "or any of its children.\n"
                 "Otherwise, this includes goods stored in any Stock Location "
                 "with 'internal' type."),
        'incoming_qty': fields.float('Incoming', digits_compute=dp.get_precision('Product Unit of Measure'),
            help="Quantity of products that are planned to arrive.\n"
                 "In a context with a single Stock Location, this includes "
                 "goods arriving to this Location, or any of its children.\n"
                 "In a context with a single Warehouse, this includes "
                 "goods arriving to the Stock Location of this Warehouse, or "
                 "any of its children.\n"
                 "In a context with a single Shop, this includes goods "
                 "arriving to the Stock Location of the Warehouse of this "
                 "Shop, or any of its children.\n"
                 "Otherwise, this includes goods arriving to any Stock "
                 "Location with 'internal' type."),
        'outgoing_qty': fields.float('Outgoing', digits_compute=dp.get_precision('Product Unit of Measure'),
            help="Quantity of products that are planned to leave.\n"
                 "In a context with a single Stock Location, this includes "
                 "goods leaving this Location, or any of its children.\n"
                 "In a context with a single Warehouse, this includes "
                 "goods leaving the Stock Location of this Warehouse, or "
                 "any of its children.\n"
                 "In a context with a single Shop, this includes goods "
                 "leaving the Stock Location of the Warehouse of this "
                 "Shop, or any of its children.\n"
                 "Otherwise, this includes goods leaving any Stock "
                 "Location with 'internal' type."),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
