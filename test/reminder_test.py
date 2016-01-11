from __future__ import print_function
import sys
sys.path.append('..')

import reminder
import unittest

class TestReminder(unittest.TestCase):


    def test_parse_arguments(self):
        args = reminder.parse_arguments(['--start'])
        self.assertTrue(args.start)

        args = reminder.parse_arguments(['--start', '--stop'])
        self.assertTrue(args.start)
        self.assertTrue(args.stop)

        args = reminder.parse_arguments(['--restart'])
        self.assertTrue(args.restart)

        args = reminder.parse_arguments(['--repeat', '4'])
        self.assertEqual(args.repeat, 4)

        args = reminder.parse_arguments(['-r', '5'])
        self.assertEqual(args.repeat, 5)

        args = reminder.parse_arguments(['hello world'])
        self.assertEqual(args.content, 'hello world')

        args = reminder.parse_arguments(['--when', '13h2m', '--after', '360s'])
        self.assertEqual(args.when, '13h2m')
        self.assertEqual(args.after, '360s')

        args = reminder.parse_arguments(['--when', '13h2m', 'hello world'])
        self.assertEqual(args.when, '13h2m')
        self.assertEqual(args.content, 'hello world')


    def test_valid_datetime(self):
        self.assertTrue(reminder.valid_datetime(2015,10,12,15,22,30))
        self.assertTrue(reminder.valid_datetime(2015,10,12,15,22,59))
        self.assertTrue(reminder.valid_datetime(2015,10,12,0,0,0))
        self.assertTrue(reminder.valid_datetime(2015,10,12,23,0,0))

        self.assertFalse(reminder.valid_datetime(2015,10,12,24,0,0))
        self.assertFalse(reminder.valid_datetime(2015,10,12,23,60,0))
        self.assertFalse(reminder.valid_datetime(2015,10,32,4,0,0))
        self.assertFalse(reminder.valid_datetime(2015,10,-3,4,0,0))
        self.assertFalse(reminder.valid_datetime(2015,2,29,4,0,0))


    def test_parse_time(self):
        when  = '12h3m45s'
        after = '12h3m5s'

        result = str(reminder.parse_time(when=when, after=None))
        self.assertEqual(result[-6:], '120345')

        result = str(reminder.parse_time(when=when, after=after))
        self.assertEqual(result[-6:], '120345')


if __name__ == '__main__':
    unittest.main()