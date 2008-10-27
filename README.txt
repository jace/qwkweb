QwkWeb
======

QwkWeb parses QWK message archive packets, loads into a database, and presents
a web-based browsing interface. QwkWeb is derived from ZQWK, a Zope-based
implementation that targeted Zope 2.7 in 2003. This version contains:

* qwk.py, a QWK library in Python.
* qwkweb.py, a web-based interface built using the web.py framework.
* Templates for the web interface.

Usage
-----

Copy the configuration template file qwkweb.conf into any of the following
locations and edit it to indicate your database settings:

* .qwkweb.conf (current folder of wherever the web server is run from)
* ~/.qwkweb.conf
* /etc/qwkweb.conf

Supported databases include "sqlite", "mysql" and "postgres". To initialise the
SQLite database, use::

  sqlite3 qwkweb.db < sqlite.sql

(Support for the other databases is incomplete at this time.)
