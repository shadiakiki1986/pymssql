from os import path
import time

from nose.tools import eq_

import _mssql
import pymssql

class Config(object):
    pass
config = Config()

cdir = path.dirname(__file__)
tmpdir = path.join(cdir, 'tmp')
cfgpath = path.join(cdir, 'tests.cfg')
global_mssqlconn = None

def mssqlconn():
    return _mssql.connect(
            server=config.server,
            user=config.user,
            password=config.password,
            database=config.database,
            port=config.port,
        )

def pymssqlconn():
    return pymssql.connect(
            server=config.server,
            user=config.user,
            password=config.password,
            database=config.database,
            port=config.port,
        )

def get_app_lock():
    global global_mssqlconn

    if global_mssqlconn is None:
        global_mssqlconn = mssqlconn()

    t1 = time.time()
    print("*** %d: Grabbing app lock for pymssql tests" % (t1,))
    global_mssqlconn.execute_query("""
    DECLARE @result INTEGER;
    EXEC @result = sp_getapplock
        @Resource = 'pymssql_tests',
        @LockMode = 'Exclusive',
        @LockOwner = 'Session';
    SELECT @result AS result;
    """)
    t2 = time.time()
    for row in global_mssqlconn:
        print("*** %d: sp_getapplock for 'pymssql_tests' returned %d - it took %d seconds" % (t2, row['result'], t2 - t1))

def release_app_lock():
    t1 = time.time()
    global_mssqlconn.execute_query("""
    DECLARE @result INTEGER;
    EXEC @result = sp_releaseapplock
        @Resource = 'pymssql_tests',
        @LockOwner = 'Session';
    SELECT @result AS result;
    """)
    print("*** %d: sp_releaseapplock for 'pymssql_tests' returned" % (t1,))
    for row in global_mssqlconn:
        print("*** %d: sp_releaseapplock for 'pymssql_tests' returned %d" % (t1, row['result'],))

def drop_table(conn, tname):
    sql = "if object_id('%s') is not null drop table %s" % (tname, tname)
    conn.execute_non_query(sql)

def clear_table(conn, tname):
    sql = 'delete from %s' % tname
    conn.execute_non_query(sql)

class PyTableBase(object):
    tname = 'pymssql'
    cols = tuple()
    idtype = None

    @classmethod
    def table_sql(cls):
        return 'CREATE TABLE %s (%s)' % (cls.tname, ', '.join(cls.cols))

    @classmethod
    def newconn(cls):
        cls.conn = pymssqlconn()

    @classmethod
    def setup_class(cls):
        cls.newconn()
        # table related commands managed by this class are handled in a
        # different connection
        cls._conn = mssqlconn()
        drop_table(cls._conn, cls.tname)
        cls._conn.execute_non_query(cls.table_sql())

    def setUp(self):
        clear_table(self._conn, self.tname)

    def row_count(self):
        sql = 'select count(*) from %s' % self.tname
        return self.conn._conn.execute_scalar(sql)

    def execute(self, sql, params=None):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur

class TableManager(object):
    def __init__(self, conn, tname, *cols):
        self.conn = conn
        self.tname = tname
        self.cols = cols

        self.create()

    def table_sql(self):
        return 'CREATE TABLE %s (%s)' % (self.tname, ', '.join(self.cols))

    def drop(self):
        #mssql
        sql = "if object_id('%s') is not null drop table %s" % (self.tname, self.tname)
        try:
            self.execute(sql)
        except Exception as e:
            self.conn.rollback()
            if 'syntax error' not in str(e):
                raise
            #sqlite
            sql = 'drop table if exists %s' % self.tname
            self.execute(sql)

    def execute(self, sql):
        cur = self.conn.cursor()
        cur.execute(sql)
        self.conn.commit()

    def create(self):
        self.drop()
        self.execute(self.table_sql())

    def clear(self):
        sql = 'delete from %s' % self.tname
        self.execute(sql)

    def count(self):
        sql = 'select count(*) from %s' % self.tname
        cur = self.conn.cursor()
        cur.execute(sql)
        return cur.fetchone()[0]

class DBAPIBase(object):

    def newconn(self):
        self.conn = self.__class__.get_conn()

    def __init__(self):
        self.newconn()

    def setUp(self):
        self.conn.rollback()

    def execute(self, sql):
        cur = self.conn.cursor()
        cur.execute(sql)
        return cur

    def executemany(self, sql, params_seq):
        cur = self.conn.cursor()
        cur.executemany(sql, params_seq)
        return cur

class CursorBase(DBAPIBase):
    """
        This is a "base" object because I have an uncommitted test module
        that runs these tests against psycopg to see what its behavior is.
        When psycopg comparison isn't needed anymore, this class can be moved to
        test_pymssql and used directly.
    """
    def __init__(self):
        DBAPIBase.__init__(self)
        self.t1 = TableManager(self.conn, 'test', 'id int', 'name varchar(50)')

    def setUp(self):
        DBAPIBase.setUp(self)
        self.t1.clear()
        self.execute("insert into test values (1, 'one')")
        self.execute("insert into test values (2, 'two')")
        self.execute("insert into test values (3, 'three')")
        self.execute("insert into test values (4, 'four')")
        self.execute("insert into test values (5, 'five')")
        self.conn.commit()

    def test_description_not_used(self):
        cur = self.conn.cursor()
        assert cur.description is None

    def test_description_after_insert(self):
        cur = self.execute("insert into test values (6, 'six')")
        self.conn.commit()
        assert cur.description is None

    def test_description_after_select(self):
        cur = self.execute('select * from test')
        eq_(len(cur.description), 2)
        eq_(cur.description[0][0], 'id')
        eq_(self.dbmod.NUMBER, cur.description[0][1])
        eq_(cur.description[1][0], 'name')
        eq_(self.dbmod.STRING, cur.description[1][1])

    def test_sticky_description(self):
        cur = self.execute('select * from test')
        eq_(len(cur.description), 2)

        cur2 = self.execute('select id from test')
        eq_(len(cur2.description), 1)

        # description of first cursor should not be affected
        eq_(len(cur.description), 2)

    def test_fetchone(self):
        cur = self.execute('select * from test order by id')
        res = cur.fetchone()
        eq_(res[0], 1)
        res = cur.fetchone()
        eq_(res[0], 2)
        for x in range(0, 5):
            if cur.fetchone() is None:
                # make sure another call is also None and no execption is raised
                assert cur.fetchone() is None
                break
            if x == 5:
                assert False, 'expected cur.fetchone() to be None'

    def test_insert_rowcount(self):
        cur = self.execute("insert into test values (6, 'six')")
        eq_(cur.rowcount, 1)
        self.conn.rollback()

    def test_delete_rowcount(self):
        cur = self.execute("delete from test where id = 5")
        eq_(cur.rowcount, 1)
        cur = self.execute("delete from test where id > 1")
        eq_(cur.rowcount, 3)
        self.conn.rollback()

    def test_update_rowcount(self):
        cur = self.execute("update test set name = 'foo' where id > 1")
        eq_(cur.rowcount, 4)
        self.conn.rollback()

    def test_select_rowcount(self):
        cur = self.execute('select * from test')
        eq_(cur.rowcount, -1)
        cur.fetchall()
        eq_(cur.rowcount, 5)

    def test_as_dict(self):
        # test for http://code.google.com/p/pymssql/issues/detail?id=92
        cur = self.conn.cursor(as_dict=True)
        cur.execute("SELECT 'foo' AS first_name, 'bar' AS last_name")
        eq_(cur.fetchall(), [{'first_name': u'foo', 'last_name': u'bar'}])

    def test_fetchmany(self):
        cur = self.conn.cursor()
        cur.execute('select * from test')
        eq_(len(cur.fetchmany(2)), 2)
        eq_(len(cur.fetchmany(2)), 2)
        eq_(len(cur.fetchmany(2)), 1)

        # now a couple extra for good measure
        eq_(len(cur.fetchmany(2)), 0)
        eq_(len(cur.fetchmany(2)), 0)

    def test_execute_many(self):
        cur = self.executemany("delete from test where id = %(id)s", [{'id': 1}, {'id': 2}])
        self.conn.commit()
        eq_(self.t1.count(), 3)
        eq_(cur.rowcount, 2)

def clear_db():
    conn = mssqlconn()
    mapping = {
        'P': 'drop procedure [%(name)s]',
        'C': 'alter table [%(parent_name)s] drop constraint [%(name)s]',
        ('FN', 'IF', 'TF'): 'drop function [%(name)s]',
        'V': 'drop view [%(name)s]',
        'F': 'alter table [%(parent_name)s] drop constraint [%(name)s]',
        'U': 'drop table [%(name)s]',
    }
    delete_sql = []
    to_repeat_sql = []
    for type, drop_sql in mapping.items():
        sql = 'select name, object_name( parent_object_id ) as parent_name '\
            'from sys.objects where type in (\'%s\')' % '", "'.join(type)
        conn.execute_query(sql)
        for row in conn:
            delete_sql.append(drop_sql % dict(row))
    for sql in delete_sql:
        conn.execute_non_query(sql)
