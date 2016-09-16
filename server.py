from flask import Flask, session, render_template, request, redirect, url_for
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta, date
import time


app = Flask(__name__)

try:
    from settings import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, APP_SECRET_KEY
    app.secret_key = APP_SECRET_KEY
except ImportError:
    STRAVA_CLIENT_ID = 0
    STRAVA_CLIENT_SECRET = ''
    app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'

STRAVA_REDIRECT_PATH = 'token-exchange'
STRAVA_RESPONSE_TYPE = 'code'

def get_date(date_string):
    return datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%SZ')

def parse_date(date_string):
    return datetime.strftime(get_date(date_string), '%a	%m-%d')

def parse_time(date_string):
    return datetime.strftime(get_date(date_string), '%I:%M %p')

def parse_duration(t):
    return '%i:%i' % (int(t / 60), t % 60)

def parse_distance(d):
    return '%.2f' % (d / 1000)

@app.route('/')
def index():
    strava_request_access_url = 'https://www.strava.com/oauth/authorize'
    strava_request_access_url+= '?client_id=%s' % STRAVA_CLIENT_ID
    strava_request_access_url+= '&redirect_uri=%s' % (request.url_root + STRAVA_REDIRECT_PATH)
    strava_request_access_url+= '&response_type=%s' % STRAVA_RESPONSE_TYPE
    return render_template('index.html', strava_request_access_url=strava_request_access_url)

@app.route('/token-exchange')
def token_exchange():
    if 'error' in request.args:
        pass

    data = urllib.parse.urlencode({
        'client_id': STRAVA_CLIENT_ID,
        'client_secret': STRAVA_CLIENT_SECRET,
        'code': request.args['code']
    })
    data = data.encode('ascii')
    url = 'https://www.strava.com/oauth/token'

    with urllib.request.urlopen(url, data) as f:
        response_data = json.loads(f.read().decode('utf-8'))

    session['access_token'] = response_data['access_token']
    session['athlete'] = response_data['athlete']

    return redirect(url_for('log'))

@app.route('/log')
def log():
    if 'access_token' not in session:
        return redirect(url_for('index'))

    if 'fetch_weeks' in request.args:
        fetch_weeks = int(request.args['fetch_weeks'])
    else:
        fetch_weeks = 2

    if 'week_starts_on' in request.args:
        week_starts_on = int(request.args['week_starts_on'])
    else:
        week_starts_on = 5

    after_date = datetime.today() - timedelta(weeks=fetch_weeks)
    after_date.replace(hour=0, minute=0, second=0, microsecond=0)
    after_date_epoch = int(after_date.timestamp())
    url = 'https://www.strava.com/api/v3/athlete/activities?after=%i' % after_date_epoch

    activity_request = urllib.request.Request(url)

    activity_request.add_header('Authorization', 'Bearer ' + session['access_token'])
    with urllib.request.urlopen(activity_request) as f:
        response_data = json.loads(f.read().decode('utf-8'))

    last_x_day = date.today() - timedelta(days=(datetime.today().weekday() - week_starts_on) % 7)

    activities = [{'name': a['name'],
                   'date': parse_date(a['start_date_local']),
                   'time': parse_time(a['start_date_local']),
                   'distance': parse_distance(a['distance']),
                   'distance_raw': a['distance'],
                   'elevation': a['total_elevation_gain'],
                   'duration': parse_duration(a['elapsed_time']),
                   'elapsed_time': a['elapsed_time'],
                   'within_last_seven': True,
                   'this_week': True if last_x_day <= get_date(a['start_date_local']).date() else False
                   } for a in response_data]
    activities.reverse()

    stats = {
        'duration': parse_duration(sum(activity['elapsed_time'] for activity in activities)),
        'distance': parse_distance(sum(activity['distance_raw'] for activity in activities)),
        'elevation': '%.2f' % sum(activity['elevation'] for activity in activities),
        'total': len(activities),
    }

    this_week_activities = [activity for activity in activities if activity['this_week']]

    this_week = {
        'duration': parse_duration(sum(activity['elapsed_time'] for activity in this_week_activities)),
        'distance': parse_distance(sum(activity['distance_raw'] for activity in this_week_activities)),
        'elevation': '%.2f' % sum(activity['elevation'] for activity in this_week_activities),
        'total': len(this_week_activities),
    }

    context = {
        'username': session['athlete']['username'],
        'activities': activities,
        'stats': stats,
        'this_week': this_week,
        'fetch_weeks': fetch_weeks,
        'week_starts_on': week_starts_on,
    }

    return render_template('log.html', context=context)

if __name__ == '__main__':
    app.run(debug=True)
