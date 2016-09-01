# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright 2016 credativ Ltd
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

{
    'name' : 'Web Action Permissions',
    'version' : '7.20160901.1',
    'depends' : ['base'],
    'author': 'credativ Ltd',
    'website': 'http://www.credativ.co.uk',
    'license': 'AGPL-3',
    'category': 'Web',
    'description': """
This module provides a framework with which other modules may provide finer granularity of action availability in the UI. This can be done by passing a corresponding dict of the form {action_name:bool} back in the return from fields_view_get under the key '__action_permissions_extra'.
This module does nothing useful in and of itself.
    """,
    'data': [],
    'installable': True,
    'auto_install': True,
    'web': True,
    'js': ['static/src/js/action_permissions.js'],
    'css': [],
    'qweb' : [],
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
