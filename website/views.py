from flask import Blueprint, render_template, request
import datetime
import statsapi

views = Blueprint('views', __name__)

batter = "Bo Bichette"
pitcher = "Kevin Gausman"
head_to_head_data = None

'''
- RESET errors on calculation or RESET calculation on new player
- Player search dropdown
- Accents in names
- Somtimes refresh/new search changes back to default players
- Make 'outcomes' appear clicked by default
- Make player name's and 'vs' dynamic size (or just smaller)
- Insufficient data warning
- Async, make loading easier to understand for user
'''


@views.route('/', methods=['GET', 'POST'])
def home():
    global batter, pitcher, head_to_head_data
    batter_error = ""
    pitcher_error = ""

    if request.method == 'POST':
        if 'batter' in request.form:
            tmp = request.form.get('batter')
            tmp_data = statsapi.lookup_player(tmp)

            if len(tmp_data) == 0 or len(tmp) == 0:
                batter_error = "Player not found!"
            elif tmp_data[0]['primaryPosition']['abbreviation'] == 'P':
                batter_error = "Player is not a batter!"
            else:
                batter = tmp

        elif 'pitcher' in request.form:
            tmp = request.form.get('pitcher')
            tmp_data = statsapi.lookup_player(tmp)

            if len(tmp_data) == 0 or len(tmp) == 0:
                pitcher_error = "Player not found!"
            elif (tmp_data[0]['primaryPosition']['abbreviation'] != 'P'
                  and tmp_data[0]['primaryPosition']['abbreviation'] != 'TWP'):
                pitcher_error = "Player is not a pitcher!"
            else:
                pitcher = tmp

    batter_data = statsapi.lookup_player(batter)[0]
    batter_id = batter_data['id']
    batter_img = (
            'https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/'
            + str(batter_id) + '/headshot/67/current')
    hitting_data = statsapi.player_stat_data(batter_id, "hitting", "career")

    pitcher_data = statsapi.lookup_player(pitcher)[0]
    pitcher_id = pitcher_data['id']
    pitcher_img = (
            'https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/'
            + str(pitcher_id) + '/headshot/67/current')
    pitching_data = statsapi.player_stat_data(pitcher_id, "pitching", "career")

    head_to_head_data = fetch_head_to_head(batter_id, pitcher_id)

    return render_template('home.html', batter_data=batter_data, hitting_data=hitting_data,
                           batter_error=batter_error, batter_img=batter_img, pitcher_data=pitcher_data,
                           pitching_data=pitching_data, pitcher_error=pitcher_error, pitcher_img=pitcher_img,
                           outcomes=calculate_outcomes(hitting_data, pitching_data),
                           head_to_head_data=head_to_head_data)


def calculate_outcomes(batting_data, pitching_data):
    return [calculate_reach_base_chance(batting_data, pitching_data),
            calculate_hit_chance(batting_data, pitching_data),
            calculate_strikeout_chance(batting_data, pitching_data),
            calculate_home_run_chance(batting_data, pitching_data)]


def calculate_reach_base_chance(batting_data, pitching_data):
    batting_obp = float(batting_data['stats'][0]['stats']['obp'])
    pitching_obp = float(pitching_data['stats'][0]['stats']['obp'])

    obp = 100 * (batting_obp + pitching_obp) / 2
    return round(obp, 1)


def calculate_hit_chance(batting_data, pitching_data):
    x = float(batting_data['stats'][0]['stats']['avg'])
    y = float(pitching_data['stats'][0]['stats']['avg'])

    min_year = int(batting_data['mlb_debut'][0:4])
    p_debut = int(pitching_data['mlb_debut'][0:4])
    if p_debut < min_year:
        min_year = p_debut

    z = get_seasons_average(min_year, datetime.datetime.now().year)

    num1 = (x * y) / z
    num2 = ((1 - x) * (1 - y)) / (1 - z)
    avg = num1 / (num1 + num2)

    if int(head_to_head_data[0]) > 0:
        avg_head_to_head = float(head_to_head_data[4])

        avg = (0.2 * avg_head_to_head) + (0.8 * avg)

    return round(avg * 100, 1)


def calculate_strikeout_chance(batting_data, pitching_data):
    batting_strikeouts = float(batting_data['stats'][0]['stats']['strikeOuts'])
    batting_pas = float(batting_data['stats'][0]['stats']['plateAppearances'])
    batting_k_rate = batting_strikeouts / batting_pas

    pitching_k_rate = float(pitching_data['stats'][0]['stats']['strikePercentage'])

    avg = 100 * (batting_k_rate + pitching_k_rate) / 2
    return round(avg, 1)


def calculate_home_run_chance(batting_data, pitching_data):
    batting_homeruns = float(batting_data['stats'][0]['stats']['homeRuns'])
    batting_pas = float(batting_data['stats'][0]['stats']['plateAppearances'])
    batting_hr_rate = batting_homeruns / batting_pas

    pitching_homeruns = float(pitching_data['stats'][0]['stats']['homeRuns'])
    pitching_pas = float(pitching_data['stats'][0]['stats']['atBats'])
    pitching_hr_rate = pitching_homeruns / pitching_pas

    avg = 100 * (batting_hr_rate + pitching_hr_rate) / 2
    return round(avg, 1)


def fetch_head_to_head(batter_id, pitcher_id):
    params = {
        'personIds': str(batter_id),
        'hydrate': 'stats(group=[hitting],type=[vsPlayer],opposingPlayerId={},sportId=1)'.format(pitcher_id)
    }
    data = statsapi.get('people', params=params)['people'][0]['stats']

    if 'season' in str(data[0]):
        data = data[1]
    else:
        data = data[0]

    if data['totalSplits'] == 0:
        return ['0', '0', '0', '0', '0.000', '0.000', '0']
    else:
        pa = data['splits'][0]['stat']['plateAppearances']
        h = data['splits'][0]['stat']['hits']
        k = data['splits'][0]['stat']['strikeOuts']
        bb = data['splits'][0]['stat']['baseOnBalls']
        avg = data['splits'][0]['stat']['avg']
        ops = data['splits'][0]['stat']['ops']
        hr = data['splits'][0]['stat']['homeRuns']

        return [pa, h, k, bb, avg, ops, hr]


def get_seasons_average(start_year, end_year):
    ab = 0
    h = 0

    for i in range(start_year, end_year + 1):
        params = {
            'stats': 'Season',
            'group': 'hitting',
            'season': str(i),
            'playerPool': 'ALL',
            'limit': '2000'
        }

        data = statsapi.get('stats', params=params)

        for split in data['stats'][0]['splits']:
            ab += split['stat']['atBats']
            h += split['stat']['hits']

    return h/ab
