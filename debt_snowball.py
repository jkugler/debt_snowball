#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

#from email.MIMEMultipart import MIMEMultipart
#from email.MIMEText import MIMEText
from decimal import Decimal
import datetime
import os
import re
import sqlite3
import sys
from time import gmtime, strftime
from urllib.parse import urlparse
import warnings

from dateutil.relativedelta import relativedelta
from jinja2 import Environment, PackageLoader, select_autoescape
from jinja2 import Template
from werkzeug import Request, Response
from werkzeug.exceptions import HTTPException,BadRequest, NotFound

import debt_snowball_config as rc

__version__ = '2020-11-13-16-05'

class NoFormData(BadRequest):
    pass

class MissingFields(Exception):
    pass

class NegativeNumbers(Exception):
    pass

class TooFewDebts(Exception):
    pass

class RisingBalance(Exception):
    pass

class InvalidData(Exception):
    pass

class DuplicateNames(Exception):
    pass

def money_fmt(value, places=2, curr='$', sep=',', dp='.',
             pos='', neg='-', trailneg=''):
    """Convert Decimal to a money formatted string.
    Gleaned from https://docs.python.org/3/library/decimal.html#recipes

    places:  required number of places after the decimal point
    curr:    optional currency symbol before the sign (may be blank)
    sep:     optional grouping separator (comma, period, space, or blank)
    dp:      decimal point indicator (comma or period)
             only specify as blank when places is zero
    pos:     optional sign for positive numbers: '+', space or blank
    neg:     optional sign for negative numbers: '-', '(', space or blank
    trailneg:optional trailing minus indicator:  '-', ')', space or blank

    >>> d = Decimal('-1234567.8901')
    >>> moneyfmt(d, curr='$')
    '-$1,234,567.89'
    >>> moneyfmt(d, places=0, sep='.', dp='', neg='', trailneg='-')
    '1.234.568-'
    >>> moneyfmt(d, curr='$', neg='(', trailneg=')')
    '($1,234,567.89)'
    >>> moneyfmt(Decimal(123456789), sep=' ')
    '123 456 789.00'
    >>> moneyfmt(Decimal('-0.02'), neg='<', trailneg='>')
    '<0.02>'

    """
    if not isinstance(value, Decimal):
        value = Decimal(value)

    q = Decimal(10) ** -places      # 2 places --> '0.01'
    sign, digits, exp = value.quantize(q).as_tuple()
    result = []
    digits = list(map(str, digits))
    build, next = result.append, digits.pop
    if sign:
        build(trailneg)
    for i in range(places):
        build(next() if digits else '0')
    if places:
        build(dp)
    if not digits:
        build('0')
    i = 0
    while digits:
        build(next())
        i += 1
        if i == 3 and digits:
            i = 0
            build(sep)
    build(curr)
    build(neg if sign else pos)
    return ''.join(reversed(result))

def do_amortization(debt_name, balance, payment, apr, additional_start=datetime.date(9999, 12,31), additional_payment=0):
    apr = float(apr)/100.0
    monthly_pr = apr/12.0

    if rc.debug: #pragma: no cover
        print("month, start_balance, new_balance, paid_balance, payment, interest_payment, principal_payment")

    month_count = 0
    start_date = datetime.date.today()
    results = []
    original_payment = float(payment)
    balance = float(balance)
    additional_payment = float(additional_payment)

    while balance > 0:
        start_balance = balance
        new_balance = balance + balance * monthly_pr
        this_month = start_date + relativedelta(months=month_count)

        if additional_payment > 0 and this_month > additional_start:
            payment = original_payment + additional_payment
        else:
            payment = original_payment

        paid_balance = new_balance - payment

        if paid_balance >= start_balance:
            raise RisingBalance(debt_name)

        if paid_balance < 0:
            paid_balance = 0
            payment = new_balance

        interest_payment = new_balance - start_balance
        principal_payment = payment - interest_payment

        balance = paid_balance

        if rc.debug: #pragma: no cover
            print("%s-%s" % (this_month.year, this_month.month),
                  money_fmt(start_balance), money_fmt(new_balance),
                  money_fmt(paid_balance), money_fmt(payment),
                  money_fmt(interest_payment), money_fmt(principal_payment))

        month_count += 1

        results.append({'month': this_month,
                        'start_balance': money_fmt(start_balance),
                        'payment': money_fmt(payment),
                        'new_balance': money_fmt(new_balance),
                        'paid_balance': money_fmt(paid_balance),
                        'interest_payment': money_fmt(interest_payment),
                        'principal_payment': money_fmt(principal_payment)})

    return results

def sort_by_payoff_time(fields):
    debts = {}

    for num in range(1, int(fields['row_count']) + 1):
        debt_name = fields["debt_name_%s" % num].strip()
        if debt_name == '':
            continue

        balance = fields["balance_%s" % num].strip().replace('$%,', '')
        payment = fields["payment_%s" % num].strip().replace('$%,', '')
        apr = fields["apr_%s" % num].strip().replace('$%,', '')

        payments = len(do_amortization(debt_name, balance, payment, apr))

        debts[debt_name] = {'debt_name': debt_name, 'payments': payments, 'balance': balance,
                            'payment': payment, 'apr': apr}

    sorted_debts = sorted(debts.values(), key=lambda x: x['payments'])

    return sorted_debts

def calculate_combined_payoff_tables(sorted_debts):
    additional_start = datetime.date(9999, 12,31)
    additional_payment = 0
    results = []

    for debt in sorted_debts:
        results.append({'debt_name': debt['debt_name'],
                        'payoff_chart': do_amortization(debt['debt_name'],
                                                        debt['balance'], debt['payment'],
                                                        debt['apr'], additional_start,
                                                        additional_payment)})

        additional_start = results[-1]['payoff_chart'][-1]['month']
        additional_payment = additional_payment + float(debt['payment'])

    return results

def process_form(fields):
    ##TODO: Make sure all values are positive
    ##TODO: Make sure all values are numerical
    ##TODO: Make sure all values are positive
    ##TODO: Do this checking client-side too
    ##TODO: Return names of fields to highlight in red
    ##TODO: Move a good chunk of this into validate_form()
    ##TODO: Reduce the number of todos
    missing = []
    debt_count = 0
    debt_names = {}

    # Sanitized fields
    s_fields = fields.copy()

    # Make sure all values are filled out if one value on a line is filled out
    for num in range(1, int(fields['row_count']) + 1):
        not_blank = [bool(fields["%s_%s" % (f, num)].strip()) for f in ['debt_name', 'balance', 'payment', 'apr']]
        if any(not_blank) and not all(not_blank):
            raise MissingFields

        for f in ['balance', 'payment', 'apr']:
            s_fields["%s_%s" % (f, num)] = re.sub('[$%,]', '', s_fields["%s_%s" % (f, num)].strip())

        if any([s_fields["debt_name_%s" % (num)] != '' and float(s_fields["%s_%s" % (f, num)]) < 0 for f in ['balance', 'payment', 'apr']]):
            raise NegativeNumbers

        if s_fields["debt_name_%s" % (num)] == '':
            continue

        debt_names[s_fields["debt_name_%s" % num]] = 1

        debt_count += 1

    if debt_count < 2:
        raise TooFewDebts

    if len(debt_names) < debt_count:
        raise DuplicateNames

    sorted_debts = sort_by_payoff_time(s_fields)

    payoff_tables = calculate_combined_payoff_tables(sorted_debts)

    return render_page(fields, payoff_tables, '')

def render_page(fields={}, results=[], message=''):
    template = Template(open(rc.template_file).read())
    return template.render(fields=fields, results=results, message=message,
                           data_ad_client=rc.data_ad_client, version=__version__)

@Request.application
def application(request):

    response = Response(mimetype='text/html')

    try:
        # Only accept requests for rc.base_path
        if urlparse(request.url).path != rc.base_path:
            raise NotFound

        fields = request.form.to_dict()

        if request.method == 'GET':
            raise NoFormData
        elif request.method == 'POST':
            if not request.form:
                raise NoFormData
        else:
            raise BadRequest

        response.data = process_form(fields)

    except NoFormData as e:
        response.data = render_page()

    except MissingFields as e:
        response.data = render_page(fields=fields,
                                    message='All fields on a line must be filled out.')

    except TooFewDebts as e:
        response.data = render_page(fields=fields,
                                    message='Two or more debts must be provided.')

    except NegativeNumbers as e:
        response.data = render_page(fields=fields,
                                    message='All numbers must be positive.')

    except DuplicateNames as e:
        response.data = render_page(fields=fields,
                                    message='To avoid confusion, all debts must have unique names.')

    except RisingBalance as e:
        response.data = render_page(fields=fields,
                                    message="Debt '%s' does not have a large enough payment to reduce the balance." % e.args[0])

    except ValueError as e:
        response.data = render_page(fields=fields,
                                    message='Balance, payment, and APR must be numeric.')

    except HTTPException as e:
        return e

    return response

if __name__ == '__main__': #pragma: no cover
    from werkzeug.serving import run_simple
    if sys.argv[1:]:
        port = int(sys.argv[1])
    else:
        port = 8000

    print("Serving on port %s" % port)

    run_simple('127.0.0.1', port, application, use_debugger=False, use_reloader=False,
               passthrough_errors=True, threaded=False)
