

from flask import Flask,request,json,jsonify,session,g,_app_ctx_stack, \
        redirect,url_for,flash,render_template,abort
import sqlite3
import urllib2

DATABASE = "/tmp/meet.n.eat"
PLACES_API_KEY = "AIzaSyDie5yxhWorjwPLw8n-bshLujxU9rWxAoA"
PLACES_BASE_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
DIRECTIONS_BASE_URL = "http://maps.googleapis.com/maps/api/directions/json?"
PLACES_RADIUS = 3000

#### XXX:
####    Veto / approve
####    lazy direction getting
####    error codes
####    error message handling from apis
####    insert/update location helper
####    license
####    other helpers
####    location - sql join


app = Flask(__name__)
app.config.from_object(__name__)


#### Initialization methods ####
def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql') as f:
            db.cursor().executescript(f.read())
        db.commit()

def get_db():
    top = _app_ctx_stack.top
    if not hasattr(top, 'sqlite_db'):
        top.sqlite_db = sqlite3.connect(app.config['DATABASE'])
    return top.sqlite_db

#### Helpers ####

def count_sessions(db, sessionid, expected_value):
    cur = db.execute('select count(*) from sessions where sessionid = ?',
            (sessionid,))
    if cur.fetchone()[0] == expected_value:
        return True
    return False

# Process takes a session id, gets the two locations, finds the middle,
#   uses the places API to find places matching "foodtype", put them in
#   destinations table, and returns true
def process(sessionid):
    db = get_db()
    if not count_sessions(db, sessionid, 1):
        return False
    cur = db.execute('select a_location,b_location,food_pref from sessions where \
            sessionid = ?', (sessionid,))
    result = cur.fetchone()
    food_pref = result[2]
    a_location = db.execute('select latitude, longitude from locations where \
            id = ?', (result[0],))
    a_location = a_location.fetchone()
    b_location = db.execute('select latitude, longitude from locations where \
            id = ?', (result[1],))
    b_location = b_location.fetchone()
    #XXX Make this deal with things correctly
    center_latitude = (a_location[0] + b_location[0]) / 2
    center_longitude = (a_location[1] + b_location[1]) / 2
    #XXX Update sessions center location (create helper to update location)
    url = ("%slocation=%f,%f&radius=%d&types=food&keyword=%s&key=%s&sensor=false" % \
            (PLACES_BASE_URL, center_latitude, center_longitude, PLACES_RADIUS, food_pref, \
            PLACES_API_KEY))
    places = json.loads(urllib2.urlopen(url).read())
    for place in places["results"][:2]:
        a_c_directions_url = ("%sorigin=%f,%f&destination=%f,%f&sensor=false&mode=walking" % \
                (DIRECTIONS_BASE_URL, a_location[0], a_location[1],\
                place["geometry"]["location"]["lat"], place["geometry"]["location"]["lng"]))
        b_c_directions_url = ("%sorigin=%f,%f&destination=%f,%f&sensor=false&mode=walking" % \
                (DIRECTIONS_BASE_URL, b_location[0], b_location[1],\
                place["geometry"]["location"]["lat"], place["geometry"]["location"]["lng"]))
        a_directions = json.loads(urllib2.urlopen(a_c_directions_url).read())
        b_directions = json.loads(urllib2.urlopen(b_c_directions_url).read())
        if a_directions["status"] == 'OVER_QUERY_LIMIT' or b_directions["status"] == 'OVER_QUERY_LIMIT':
            #XXX Correct abort
            abort(400)
        a_routes = a_directions["routes"]
        b_routes = b_directions["routes"]
        if len(a_routes) >= 1:
            a_route = a_routes[0]
        else:
            #XXX Correct abort
            abort(400)
        if len(b_routes) >= 1:
            b_route = b_routes[0]
        else:
            #XXX Correct abort
            abort(400)

        a_time = a_route["legs"][0]["duration"]["value"]
        b_time = a_route["legs"][0]["duration"]["value"]
        a_distance = b_route["legs"][0]["distance"]["value"]
        b_distance = b_route["legs"][0]["distance"]["value"]
        lat = place["geometry"]["location"]["lat"]
        lng = place["geometry"]["location"]["lng"]
        db.execute('insert into locations (latitude, longitude) values (?, ?)',
                (lat, lng))
        rowid = db.execute('select last_insert_rowid()')
        db.execute('insert into destinations values (?, ?, ?, ?, ?, ?, ?)', \
                (sessionid, place["name"], rowid.fetchone()[0], a_distance, b_distance, \
                a_time, b_time))
    db.commit()
    return True

#### App routing methods ####

@app.route("/")
def hello():
    return "Fuck off\n"

@app.route("/<sessionid>/init", methods = ['POST'])
def api_init(sessionid):
    if request.method == 'POST':
        if request.headers['Content-Type'] == 'application/json':
            latitude = request.json['latitude']
            longitude = request.json['longitude']
            foodtype = request.json['foodtype']
            if latitude is None or \
                    longitude is None or \
                    foodtype is None:
                        #XXX Correct error codes?
                        abort(400)
            db = get_db()
            if not count_sessions(db, sessionid, 0):
                abort(400)
            db.execute('insert into locations (latitude, longitude) values (?, ?)',
                    (latitude, longitude))
            rowid = db.execute('select last_insert_rowid()')
            db.execute('insert into sessions (sessionid, a_location, food_pref) values \
                    (?, ?, ?)', (sessionid, rowid.fetchone()[0], foodtype))
            db.commit()
            return jsonify({"success":sessionid})
        else:

            #XXX Return error code 400
            abort(400)
    else:
        #XXX Return some error code
        abort(400)

@app.route("/<sessionid>/join", methods = ['POST'])
def api_join(sessionid):
    if request.method == 'POST':
        if request.headers['Content-Type'] == 'application/json':
            latitude = request.json['latitude']
            longitude = request.json['longitude']
            if latitude is None or \
                    longitude is None:
                        #XXX Correct error code
                        abort(400)
            db = get_db()
            if not count_sessions(db, sessionid, 1):
                #XXX Correct error code
                abort(400)
            db.execute('insert into locations (latitude, longitude) values (?, ?)',
                    (latitude, longitude))
            rowid = db.execute('select last_insert_rowid()')
            db.execute('update sessions set b_location = ? where sessionid = ?',
                    (rowid.fetchone()[0], sessionid))
            db.commit()
            #XXX Process!
            if process(sessionid):
                return jsonify({"success":sessionid})
            else:
                #XXX Correct error code
                abort(400)
        else:
            #XXX Correct error code
            abort(400)
    else:
        #XXX Return something useful
        abort(400)

@app.route("/<sessionid>/results", methods = ['GET', 'POST'])
def api_results(sessionid):
    if request.method == 'GET':
        db = get_db()
        if not count_sessions(db, sessionid, 1):
            #XXX Correct error code
            abort(418)
        cur = db.execute('select name, location, a_distance, b_distance, \
                a_time, b_time, a_veto, b_veto, a_approve, b_approve from destinations \
                where sessionid = ?',
                (sessionid,))
        results = {}
        for row in cur.fetchall():
            loc = db.execute('select latitude, longitude from locations where id = ?',
                    (row[1],))
            location = loc.fetchone()
            results[row[0]] = ((location[0], location[1]), row[2], row[3], row[4], row[5],
                    row[6], row[7], row[8], row[9])
        if len(results) == 0:
            #XXX Correct error code
            abort(304)
        else:
            return jsonify(results)
    elif request.method == 'POST':
        db = get_db()
        if not count_sessions(db, sessionid, 1):
            #XXX Correct error code
            abort(418)
        #XXX veto/approve by flag
        a_veto = request['a_veto']
        b_veto = request['b_veto']
        a_approve = request['a_approve']
        b_approve = request['b_approve']
        name = request['name']
        if a_veto is not None:
            db.execute('update destinations set a_veto 1 where name = ?',
                    (name))
        if b_veto is not None:
            db.execute('update destinations set b_veto 1 where name = ?',
                    (name))
        if a_approve is not None:
            db.execute('update destinations set a_approve 1 where name = ?',
                    (name))
        if b_approve is not None:
            db.execute('update destinations set b_approve 1 where name = ?',
                    (name))

    else:
        #XXX Return something useful
        abort(400)

#### RUN ####

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host='0.0.0.0', port=80)
