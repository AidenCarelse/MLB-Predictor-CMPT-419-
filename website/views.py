from flask import Blueprint, render_template, request, url_for
import statsapi

views = Blueprint('views', __name__)

batter = "Bo Bichette"
pitcher = "Kevin Gausman"
batter_error = ""
pitcher_error = ""

'''
- RESET errors on calculation or RESET calculation on new player
- Player search dropdown
- Accents in names
'''


@views.route('/', methods=['GET', 'POST'])
def home():
    global batter, pitcher, batter_error, pitcher_error

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
                batter_error = ""

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
                pitcher_error = ""

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

    fetch_head_to_head(batter_id, pitcher_id)

    return render_template('home.html', batter_data=batter_data, hitting_data=hitting_data,
                           batter_error=batter_error, batter_img=batter_img, pitcher_data=pitcher_data,
                           pitching_data=pitching_data, pitcher_error=pitcher_error, pitcher_img=pitcher_img,
                           outcomes=calculate_outcomes(hitting_data, pitching_data),
                           head_to_head_data=fetch_head_to_head(batter_id, pitcher_id))


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
    batting_avg = float(batting_data['stats'][0]['stats']['avg'])
    pitching_avg = float(pitching_data['stats'][0]['stats']['avg'])

    avg = 100 * (batting_avg + pitching_avg) / 2
    return round(avg, 1)


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
    data = statsapi.get('people', params=params)['people'][0]['stats'][0]
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
