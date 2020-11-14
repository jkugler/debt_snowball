import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import unittest

import debt_snowball as ds

class TestAmortization(unittest.TestCase):
    def test_single_loan(self):
        """Test running with one loan"""
        result = ds.do_amortization('dummy', '95113.31', '1111.67', '5.375')
        self.assertEqual(len(result), 109)
        self.assertEqual(ds.money_fmt(147.32), result[-1]['start_balance'])

    def test_growing_balance_abort(self):
        """Amortization should abort if balance is growing"""
        self.assertRaises(ds.RisingBalance, ds.do_amortization, 'dummy', '95113.31', '100', '5.375')

    def test_multi_loan(self):
        """Test running with one loan and additional paydown"""
        today = datetime.date.today()
        additional_start = today + relativedelta(years=5)
        result = ds.do_amortization('dummy', '95113.31', '1111.67', '5.375', additional_start, 1000)
        self.assertEqual(result[-1]['start_balance'], ds.money_fmt(1205.32))

class TestMoneyFormat(unittest.TestCase):
    def test_negative_sign(self):
        """A test case so we get full covergage :)"""
        self.assertEqual(ds.money_fmt(-10), '-$10.00')

    def test_blank(self):
        """Test an empty number, again, for full coverage"""
        self.assertEqual(ds.money_fmt(0), '$0.00')

class TestFromProcessing(unittest.TestCase):
    def test_incomplete_values(self):
        """Send a line with incomplete data"""
        self.assertRaises(ds.MissingFields,
                          ds.process_form,
                          {'row_count': '10', 'debt_name_1': 'test_name','balance_1': '1',
                           'payment_1': '1', 'apr_1':''})

    def test_too_few_debts(self):
        """Send only one debt"""
        self.assertRaises(ds.TooFewDebts,
                          ds.process_form,
                          {'row_count': '1', 'debt_name_1': 'test_name', 'balance_1': '1',
                           'payment_1': '1', 'apr_1':'5.3'} )

    def test_negative_numbers(self):
        """Throw exception on negative numbers"""
        self.assertRaises(ds.NegativeNumbers,
                          ds.process_form,
                          {'row_count': '1', 'debt_name_1': 'test_name', 'balance_1': '1',
                           'payment_1': '1', 'apr_1':'-5.3'})

    def test_duplicate_names(self):
        """Throw exception on duplicate debt names"""
        self.assertRaises(ds.DuplicateNames,
                          ds.process_form,
                          {'row_count': '2', 'debt_name_1': 'test_name', 'balance_1': '1',
                           'payment_1': '1', 'apr_1':'5.3', 'debt_name_2': 'test_name',
                           'balance_2': '1', 'payment_2': '1', 'apr_2': '5.3'})

    def test_invalid_values(self):
        """Throw an exception when values aren't numeric"""
        self.assertRaises(ValueError,
                          ds.process_form,
                          {'row_count': '1', 'debt_name_1': 'test_name', 'balance_1': 'Dog',
                           'payment_1': '1', 'apr_1':'-5.3'})

    def test_strip_invalid_but_expected_characters(self):
        """We should be able to handle things like $, %, and ,"""
        result = ds.process_form({'row_count': '2', 'debt_name_1': 'debt_a', 'balance_1': '$10,000',
                                  'payment_1': '$300', 'apr_1':'12%',
                                  'debt_name_2': 'debt b', 'balance_2':'$10,000',
                                  'payment_2': '$300', 'apr_2': '12%'})

    def test_blank_row(self):
        """Handle blank rows gracefully"""
        result = ds.process_form({'row_count': '3', 'debt_name_1': 'test_name_1', 'balance_1': '1',
                                  'payment_1': '1', 'apr_1':'5.3', 'debt_name_2': 'test_name_2',
                                  'balance_2': '1', 'payment_2': '1', 'apr_2': '5.3',
                                  'debt_name_3': '', 'balance_3': '', 'payment_3': '', 'apr_3':''})


class TestDebtSorting(unittest.TestCase):
    def test_sort_debts(self):
        """Sort debts by unassisted payoff time"""
        results = ds.sort_by_payoff_time({'row_count': '3',
                                         'debt_name_1': 'debt a', 'balance_1':'10000',
                                         'payment_1': '200', 'apr_1': '12',
                                         'debt_name_2': 'debt b', 'balance_2':'10000',
                                         'payment_2': '300', 'apr_2': '12',
                                         'debt_name_3': 'debt c', 'balance_3':'10000',
                                         'payment_3': '150', 'apr_3': '12'})
        self.assertEqual('debt b', results[0]['debt_name'])
        self.assertEqual('debt a', results[1]['debt_name'])
        self.assertEqual('debt c', results[2]['debt_name'])

class TestDebtCombinedPayoff(unittest.TestCase):
    def test_combined_payoff(self):
        """Payoff debts, with snowball"""
        results = ds.calculate_combined_payoff_tables([{'apr': '12', 'balance': '10000',
                                                       'payments': 41, 'debt_name': 'debt b',
                                                       'payment': '300'},
                                                      {'apr': '12', 'balance': '10000',
                                                       'payments': 70, 'debt_name': 'debt a',
                                                       'payment': '200'},
                                                      {'apr': '12', 'balance': '10000',
                                                       'payments': 111, 'debt_name': 'debt c',
                                                       'payment': '150'}])
        self.assertEqual('debt b', results[0]['debt_name'])
        self.assertEqual('debt a', results[1]['debt_name'])
        self.assertEqual('debt c', results[2]['debt_name'])
        self.assertEqual(ds.money_fmt(222.73), results[0]['payoff_chart'][-1]['start_balance'])
        self.assertEqual(ds.money_fmt(250.55), results[1]['payoff_chart'][-1]['start_balance'])
        self.assertEqual(ds.money_fmt(502.83), results[2]['payoff_chart'][-1]['start_balance'])
