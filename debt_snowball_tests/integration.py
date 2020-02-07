import unittest

from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse

import debt_snowball as ds

class TestWebResponses(unittest.TestCase):
    def setUp(self):
        self.c = Client(ds.application, BaseResponse)

    def test_file_404(self):
        """Any file request should return 404"""
        resp = self.c.get('/favicon.ico')
        self.assertEqual(resp.status_code, 404)

    def test_valid_get(self):
        """Test a valid get"""
        resp = self.c.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Snowball debt paydown', resp.data)

    def test_invalid_method(self):
        """Test an invalid method"""
        resp = self.c.head('/')
        self.assertEqual(resp.status_code, 400)

    def test_empty_post(self):
        """Sent an empty post"""
        resp = self.c.post('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Snowball debt paydown', resp.data)

    def test_incomplete_values(self):
        """Send a line with incomplete data"""
        resp = self.c.post('/', data={'row_count': '10', 'debt_name_1': 'test_name',
                                      'balance_1': '0', 'payment_1': '0', 'apr_1':''})
        self.assertIn('All fields on a line must be filled out.', resp.data)

    def test_too_few_debts(self):
        """Send only one debt"""
        resp = self.c.post('/', data={'row_count': '1', 'debt_name_1': 'test_name',
                                      'balance_1': '0', 'payment_1': '0', 'apr_1':'5.3'})
        self.assertIn('Two or more debts must be provided', resp.data)

    def test_negative_numbers(self):
        """Throw exception on negative numbers"""
        resp = self.c.post('/', data={'row_count': '1', 'debt_name_1': 'test_name',
                                      'balance_1': '1', 'payment_1': '1', 'apr_1':'-5.3'})
        self.assertIn('All numbers must be positive.', resp.data)

    def test_duplicate_names(self):
        """Throw exception on duplicate debt names"""
        resp = self.c.post('/', data={'row_count': '2', 'debt_name_1': 'test_name',
                                      'balance_1': '1', 'payment_1': '1', 'apr_1':'5.3',
                                      'debt_name_2': 'test_name', 'balance_2': '1',
                                      'payment_2': '1', 'apr_2': '5.3'})
        self.assertIn('To avoid confusion, all debts must have unique names.', resp.data)

    def test_invalid_values(self):
        """Throw an exception on non-numeric values"""
        resp = self.c.post('/', data={'row_count': '1', 'debt_name_1': 'test_name',
                                      'balance_1': 'Dog', 'payment_1': '1', 'apr_1':'-5.3'})
        self.assertIn('Balance, payment, and APR must be numeric.', resp.data)

    def test_valid_run(self):
        """Run valid values all the way through and get a result"""
        resp = self.c.post('/', data={'row_count': '3',
                                      'debt_name_1': 'debt a', 'balance_1':'10000',
                                      'payment_1': '200', 'apr_1': '12',
                                      'debt_name_2': 'debt b', 'balance_2':'10000',
                                      'payment_2': '300', 'apr_2': '12',
                                      'debt_name_3': 'debt c', 'balance_3':'10000',
                                      'payment_3': '150', 'apr_3': '12'})
        self.assertIn('debt a', resp.data)
        self.assertIn('debt b', resp.data)
        self.assertIn('debt c', resp.data)
        self.assertIn('$222.73', resp.data)
        self.assertIn('$250.55', resp.data)
        self.assertIn('$502.83', resp.data)
