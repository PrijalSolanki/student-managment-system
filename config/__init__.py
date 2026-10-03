"""Project configuration package.

A tiny PyMySQL shim is installed here (before Django touches the MySQL
backend) so that the project also runs on platforms where the compiled
``mysqlclient`` wheel is unavailable (most Windows setups).  If
``mysqlclient`` is installed it is used as-is and the shim is skipped.
"""

try:  # pragma: no cover - depends on the local environment
    import MySQLdb  # noqa: F401

    HAS_MYSQLDB = True
except ImportError:  # pragma: no cover
    try:
        import pymysql

        pymysql.install_as_MySQLdb()
        HAS_MYSQLDB = False
    except ImportError:
        HAS_MYSQLDB = None
