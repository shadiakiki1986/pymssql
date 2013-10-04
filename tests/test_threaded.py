import sys
import threading
import time
import unittest

from nose.plugins.skip import SkipTest
from nose.plugins.attrib import attr

import _mssql

from .helpers import mssqlconn

class TestingThread(threading.Thread):

    def run(self):
        self.running = True
        self.exc = None
        try:
            mssql = mssqlconn()
            for i in range(0, 1000):
                mssql.execute_query('SELECT %d', (i,))
                for row in mssql:
                    assert row[0] == i
            mssql.close()
        except Exception as e:
            self.exc = e
        finally:
            self.running = False

class TestingErrorThread(threading.Thread):

    def run(self):
        self.running = True
        self.exc = None
        try:
            mssql = mssqlconn()
            for i in range(0, 1000):
                try:
                    mssql.execute_query('SELECT unknown_column')
                except:
                    pass
            mssql.close()
        except Exception as e:
            self.exc = e
        finally:
            self.running = False

class SprocTestingErrorThread(threading.Thread):

    def run(self):
        self.running = True
        self.exc = None
        try:
            mssql = mssqlconn()
            for i in range(0, 1000):
                try:
                    proc = mssql.init_procedure('pymssqlErrorThreadTest')
                    proc.execute()
                except:
                    pass
            mssql.close()
        except Exception as e:
            self.exc = e
        finally:
            self.running = False

class ThreadedTests(unittest.TestCase):

    @attr('slow')
    def testThreadedUse(self):
        threads = []
        for i in range(0, 50):
            thread = TestingThread()
            thread.start()
            threads.append(thread)

        running = True
        while running:
            sys.stdout.write(".")
            sys.stdout.flush()
            running = False
            for thread in threads:
                if thread.exc:
                    raise thread.exc
                if thread.running:
                    running = True
                    break
            time.sleep(5)

        sys.stdout.write(" ")
        sys.stdout.flush()

    @attr('slow')
    def testErrorThreadedUse(self):
        threads = []
        for i in range(0, 2):
            thread = TestingErrorThread()
            thread.start()
            threads.append(thread)

        running = True
        while running:
            sys.stdout.write(".")
            sys.stdout.flush()
            running = False
            for thread in threads:
                if thread.exc:
                    raise thread.exc
                if thread.running:
                    running = True
                    break
            time.sleep(5)

        sys.stdout.write(" ")
        sys.stdout.flush()

    def testErrorSprocThreadedUse(self):
        spname = 'pymssqlErrorThreadTest'
        mssql = mssqlconn()
        try:
            mssql.execute_non_query("DROP PROCEDURE [dbo].[%s]" % spname)
        except:
            pass
        mssql.execute_non_query("""
        CREATE PROCEDURE [dbo].[%s]
        AS
        BEGIN
            SELECT unknown_column FROM unknown_table;
        END
        """ % spname)

        threads = []
        for i in range(0, 5):
            thread = SprocTestingErrorThread()
            thread.start()
            threads.append(thread)

        try:
            sys.stdout.write(".")
            sys.stdout.flush()
            running = True
            while running:
                running = False
                for thread in threads:
                    if thread.exc:
                        raise thread.exc
                    if thread.running:
                        running = True
                        break
                time.sleep(5)

            sys.stdout.write(" ")
            sys.stdout.flush()
        finally:
            mssql.execute_non_query("DROP PROCEDURE [dbo].[%s]" % spname)
            mssql.close()

suite = unittest.TestSuite()
suite.addTest(unittest.makeSuite(ThreadedTests))

if __name__ == '__main__':
    unittest.main()
