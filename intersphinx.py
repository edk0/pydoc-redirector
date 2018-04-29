# vim: et sw=4 sts=4 ai ci pi

from flask import Flask, escape, redirect
app = Flask(__name__)

import operator
import posixpath
import requests
import threading
from sphinx.util.inventory import InventoryFile
from werkzeug.contrib.iterio import IterIO

INVENTORIES = {
    '3': [
        ('https://docs.python.org/3/', 'https://docs.python.org/3/objects.inv'),
    ],
    '2': [
        ('https://docs.python.org/2/', 'https://docs.python.org/2/objects.inv'),
    ],
    'me': [
        ('https://docs.python.org/3/', 'https://docs.python.org/3/objects.inv'),
        ('https://clize.readthedocs.io/en/stable/', 'https://clize.readthedocs.io/en/stable/objects.inv'),
        ('https://construct.readthedocs.io/en/stable/', 'https://construct.readthedocs.io/en/stable/objects.inv'),
        ('http://werkzeug.pocoo.org/docs/0.14/', 'http://werkzeug.pocoo.org/docs/0.14/objects.inv'),
        ('http://flask.pocoo.org/docs/0.12/', 'http://flask.pocoo.org/docs/0.12/objects.inv'),
    ],
}

TYPE_BIASES = {
    'py:module': -300,
    'py:class': -200,
    'py:function': -100,
}
SORT_KEY = lambda is_shortened, n_dots, typ, list_pos: \
    (is_shortened * 100, n_dots, TYPE_BIASES.get(typ, 0), list_pos)

ALL_INVENTORIES = set().union(*INVENTORIES.values())

def load_inventories(invs):
    rv = {}
    threads = []
    try:
        for inv in invs:
            def worker(inv=inv, key=inv[0]):
                rv[key] = InventoryFile.load(IterIO(requests.get(inv[1], stream=True).iter_content()), inv[0], posixpath.join)
            thread = threading.Thread(target=worker)
            thread.start()
            threads.append(thread)
    finally:
        for thread in threads:
            thread.join()
    return rv

def inv_info(inv):
    projname, version, location, dispname = next(iter(next(iter(inv.values())).values()))
    return projname, version

def map_info(n):
    return [inv_info(invs[inv[0]]) for inv in INVENTORIES.get(n, [])]

m = {}

invs = load_inventories(ALL_INVENTORIES)


def build_mapping(inventory):
    mappings = []
    for list_pos, v in enumerate(inventory):
        uri, inv = v
        inv = invs[uri]
        for typ, entries in inv.items():
            for k, v in entries.items():
                n_dots = k.count('.')
                mappings.append((SORT_KEY(False, n_dots, typ, list_pos), (k.casefold(), v)))
                mappings.append((SORT_KEY(True, n_dots, typ, list_pos), (k.split('.')[-1].casefold(), v)))
    mappings.sort(key=operator.itemgetter(0), reverse=True)
    return dict(map(operator.itemgetter(1), mappings))

for mapping, l in INVENTORIES.items():
    m[mapping] = build_mapping(l)

@app.route("/<string:mapping>/<string:obj_id>")
def bounce(mapping, obj_id):
    try:
        index = m[mapping]
    except KeyError:
        return f"I don't know about {escape(mapping)}.", 404
    try:
        projname, version, location, _ = index[obj_id.casefold()]
    except KeyError:
        ml = ', '.join(f"{x[0]} {x[1]}" for x in map_info(mapping))
        return f"I don't know about {escape(obj_id)} in {escape(ml)}", 404
    return redirect(location), 307
