import numpy as np
from flask import Blueprint, render_template, request
import datetime
import statsapi
import random

views = Blueprint('views', __name__)

# Default values
batter = ""
pitcher = ""
head_to_head_data = None

'''
- RESET errors on calculation or RESET calculation on new player
- Player search dropdown
- Accents in names
- Somtimes refresh/new search changes back to default players
- Make player name's and 'vs' dynamic size (or just smaller)
- Insufficient data warning
- Async, make loading easier to understand for user
- Low data warnings (0% home run)
- Clean code (add comments, remove prints, fix formatting)
- Add more parameters?
- Header
- Don't divide by zero!
'''


@views.route('/', methods=['GET', 'POST'])
def home():
    global batter, pitcher, head_to_head_data

    if batter == "":
        batter = get_random_player(False)['person']['fullName']
    if pitcher == "":
        pitcher = get_random_player(True)['person']['fullName']

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

    head_to_head_data = fetch_head_to_head(batter_id, pitcher_id, None)

    return render_template('home.html', batter_data=batter_data, hitting_data=hitting_data,
                           batter_error=batter_error, batter_img=batter_img, pitcher_data=pitcher_data,
                           pitching_data=pitching_data, pitcher_error=pitcher_error, pitcher_img=pitcher_img,
                           outcomes=calculate_outcomes(hitting_data, pitching_data, None),
                           head_to_head_data=head_to_head_data)


def calculate_outcomes(batting_data, pitching_data, exclude_year):
    min_year = int(batting_data['mlb_debut'][0:4])
    p_debut = int(pitching_data['mlb_debut'][0:4])

    max_year = min_year
    if p_debut < min_year:
        min_year = p_debut
    else:
        max_year = p_debut

    batter_hand = batting_data['bat_side'][0].lower()
    pitcher_hand = pitching_data['pitch_hand'][0].lower()

    league_averages = get_league_averages(min_year, datetime.datetime.now().year, exclude_year)

    b_h2h = fetch_head_to_head(batting_data['id'], pitching_data['id'], exclude_year)[0]
    b_hand = get_career_vs_handedness(batting_data['id'], pitcher_hand, int(batting_data['mlb_debut'][0:4]),
                                      'hitting', exclude_year)
    b_recent = get_last_x_games(batting_data['id'], 'batting', exclude_year)
    b_career = get_player_averages(batting_data, False, exclude_year)

    if np.all(b_h2h == 0):
        b_h2h = b_career

    batter_averages = (0.15 * b_h2h) + (0.15 * b_hand) + (0.15 * b_recent) + (0.55 * b_career)

    p_h2h = fetch_head_to_head(batting_data['id'], pitching_data['id'], exclude_year)[0]
    p_hand = get_career_vs_handedness(pitching_data['id'], batter_hand, int(pitching_data['mlb_debut'][0:4]),
                                      'pitching', exclude_year)
    p_recent = get_last_x_games(pitching_data['id'], 'pitching', exclude_year)
    p_career = get_player_averages(pitching_data, True, exclude_year)

    if np.all(p_h2h == 0):
        p_h2h = p_career

    pitcher_averages = (0.15 * p_h2h) + (0.15 * p_hand) + (0.15 * p_recent) + (0.55 * p_career)

    outcomes = predict_outcomes(league_averages, batter_averages, pitcher_averages)

    hit = outcomes[0] + outcomes[1] + outcomes[2] + outcomes[3]
    reach_base = hit + outcomes[4] + outcomes[5]
    strikeout = outcomes[7]
    home_run = outcomes[3]

    predictions = ["{:.1f}".format(reach_base), "{:.1f}".format(hit), "{:.1f}".format(strikeout),
                   "{:.1f}".format(home_run)]

    '''if exclude_year is None:
        print(exclude_year, predictions)
        curr_year = datetime.datetime.now().year + 1
        exclude_predictions = np.zeros((curr_year - max_year, 5))

        for i in range(max_year, curr_year):
            curr_pred = calculate_outcomes(batting_data, pitching_data, i)
            diff = np.sum(np.abs(np.array(predictions).astype(np.float_) - np.array(curr_pred).astype(np.float_)))

            print(i, curr_pred, diff)
            curr_pred = np.insert(curr_pred, 0, diff)
            exclude_predictions[i - max_year] = curr_pred

        print(exclude_predictions)
        sorted_indices = np.argsort(exclude_predictions[:, 0])[::-1]
        print(exclude_predictions[sorted_indices])'''

    return predictions


def get_league_averages(start_year, end_year, exclude_year):
    league_averages = np.zeros(9)

    for i in range(start_year, end_year + 1):

        if i == exclude_year:
            continue

        params = {
            'stats': 'Season',
            'group': 'hitting',
            'season': str(i),
            'playerPool': 'ALL',
            'limit': '2000'
        }

        data = statsapi.get('stats', params=params)

        for split in data['stats'][0]['splits']:
            doubles = split['stat']['doubles']
            triples = split['stat']['triples']
            homeRuns = split['stat']['homeRuns']
            walks = (split['stat']['baseOnBalls'] + split['stat']['intentionalWalks'])
            hbps = split['stat']['hitByPitch']
            pas = split['stat'].get('plateAppearances', split['stat'].get('battersFaced'))
            strikeouts = split['stat']['strikeOuts']

            # Singles = hits - doubles - triples - home runs
            singles = split['stat']['hits'] - doubles - triples - homeRuns

            # Other outs = abs - all other categories
            other_outs = pas - split['stat']['hits'] - walks - hbps - strikeouts

            league_averages[0] += singles
            league_averages[1] += doubles
            league_averages[2] += triples
            league_averages[3] += homeRuns
            league_averages[4] += walks
            league_averages[5] += hbps
            league_averages[6] += strikeouts
            league_averages[7] += other_outs
            league_averages[8] += pas

    return normalize_averages(league_averages)


def get_player_averages(player_data, pitcher, exclude_year):
    data = player_data['stats'][0]['stats']

    doubles = data['doubles']
    triples = data['triples']
    home_runs = data['homeRuns']
    walks = (data['baseOnBalls'] + data['intentionalWalks'])
    hbps = data['hitByPitch']
    pas = data.get('plateAppearances', data.get('battersFaced'))
    strikeouts = data['strikeOuts']

    # Singles = hits - doubles - triples - home runs
    singles = data['hits'] - doubles - triples - home_runs

    # Outs = abs - all other categories
    other_outs = pas - data['hits'] - walks - hbps - strikeouts

    player_averages = [singles, doubles, triples, home_runs, walks, hbps, strikeouts, other_outs, pas]

    if exclude_year is not None:
        p_type = 'hitting'
        if pitcher:
            p_type = 'pitching'

        year_data = statsapi.player_stat_data(player_data['id'], p_type, 'yearByYear')

        for year in year_data['stats']:
            if year['season'] == str(exclude_year):
                data = year['stats']

                doubles = data['doubles']
                triples = data['triples']
                home_runs = data['homeRuns']
                walks = (data['baseOnBalls'] + data['intentionalWalks'])
                hbps = data['hitByPitch']
                pas = data.get('plateAppearances', data.get('battersFaced'))
                strikeouts = data['strikeOuts']

                # Singles = hits - doubles - triples - home runs
                singles = data['hits'] - doubles - triples - home_runs

                # Outs = abs - all other categories
                other_outs = pas - data['hits'] - walks - hbps - strikeouts

                player_averages = subtract_arrays(player_averages, [singles, doubles, triples, home_runs, walks, hbps, strikeouts, other_outs, pas])

    return normalize_averages(player_averages)


def predict_outcomes(league, batter_avg, pitcher_avg):
    sum = 0
    for i in range(0, 8):
        sum += (batter_avg[i] * pitcher_avg[i]) / league[i]

    outcomes = np.zeros(8)
    for i in range(0, 8):
        num = (batter_avg[i] * pitcher_avg[i]) / league[i]
        outcomes[i] = 100 * num / sum

    return outcomes


def get_last_x_games(id, group, exclude_year):
    x = 50
    if group == 'pitching':
        x = 20
    year = datetime.datetime.now().year

    player_averages = np.zeros(9)

    while x > 0:
        if year == exclude_year:
            year -= 1
            continue

        params = {
            'personIds': str(id),
            'hydrate': 'stats(group=[' + group + '],type=[lastXGames],limit=' + str(x) + ',season=' + str(year) + ')'
        }

        data = statsapi.get('people', params=params)['people'][0]

        if not ('stats' in data):
            break
        else:
            data = data['stats'][0]['splits'][0]['stat']

            doubles = data['doubles']
            triples = data['triples']
            home_runs = data['homeRuns']
            walks = (data['baseOnBalls'] + data['intentionalWalks'])
            hbps = data['hitByPitch']
            pas = data.get('plateAppearances', data.get('battersFaced'))
            strikeouts = data['strikeOuts']

            # Singles = hits - doubles - triples - home runs
            singles = data['hits'] - doubles - triples - home_runs

            # Outs = abs - all other categories
            other_outs = pas - data['hits'] - walks - hbps - strikeouts

            player_averages += [singles, doubles, triples, home_runs, walks, hbps, strikeouts, other_outs, pas]

            games = data['gamesPlayed']
            x -= games
            year -= 1

    return player_averages


def normalize_averages(averages):
    for i in range(0, 8):
        averages[i] = averages[i] / averages[8]

    return np.array(averages).astype(float)


def get_random_player(is_pitcher):
    team_id = get_random_team()
    params = {
        'teamId': str(team_id),
        'sportId': 1
    }

    roster = statsapi.get('team_roster', params=params)['roster']

    while True:
        r = random.randint(0, len(roster) - 1)
        curr_player = roster[r]
        position = curr_player['position']['abbreviation']

        if position == 'TWP' or (position == 'P' and is_pitcher) or (position != 'P' and not is_pitcher):
            return curr_player


def get_random_team():
    team_ids = [108,  # LAA
                109,  # ARI
                110,  # BAL
                111,  # BOS
                112,  # CHC
                113,  # CIN
                114,  # CLE
                115,  # COL
                116,  # DET
                117,  # HOU
                118,  # KC
                119,  # LAD
                120,  # WSH
                121,  # NYM
                133,  # OAK
                134,  # PIT
                135,  # SD
                136,  # SEA
                137,  # SF
                138,  # STL
                139,  # TB
                140,  # TEX
                141,  # TOR
                142,  # MIN
                143,  # PHI
                144,  # ATL
                145,  # CWS
                146,  # MIA
                147,  # NYY
                158  # NIM
                ]

    return random.choice(team_ids)


def fetch_head_to_head(batter_id, pitcher_id, exclude_year):
    params = {
        'personIds': str(batter_id),
        'hydrate': 'stats(group=[hitting],type=[vsPlayer],opposingPlayerId={},sportId=1)'.format(pitcher_id)
    }
    data = statsapi.get('people', params=params)['people'][0]['stats']
    year_data = data

    if 'season' in str(data[0]):
        data = data[1]
    else:
        data = data[0]

    if data['totalSplits'] == 0:
        return np.zeros(9), ['0', '0', '0', '0', '0.000', '0.000', '0']
    else:
        data = data['splits'][0]['stat']
        pa = data.get('plateAppearances', data.get('battersFaced'))
        h = data['hits']
        k = data['strikeOuts']
        bb = data['baseOnBalls']
        avg = data['avg']
        ops = data['ops']
        hr = data['homeRuns']

        doubles = data['doubles']
        triples = data['triples']
        homeRuns = data['homeRuns']
        walks = (data['baseOnBalls'] + data['intentionalWalks'])
        hbps = data['hitByPitch']
        pas = data.get('plateAppearances', data.get('battersFaced'))
        strikeouts = data['strikeOuts']

        # Singles = hits - doubles - triples - home runs
        singles = data['hits'] - doubles - triples - homeRuns

        # Outs = abs - all other categories
        other_outs = pas - data['hits'] - walks - hbps - strikeouts

        player_averages = [singles, doubles, triples, homeRuns, walks, hbps, strikeouts, other_outs, pas]

        if exclude_year is not None:
            year_data = year_data[1]['splits']
            for year in year_data:
                if year['season'] == str(exclude_year):
                    data = year['stat']

                    doubles = data['doubles']
                    triples = data['triples']
                    homeRuns = data['homeRuns']
                    walks = (data['baseOnBalls'] + data['intentionalWalks'])
                    hbps = data['hitByPitch']
                    pas = data.get('plateAppearances', data.get('battersFaced'))
                    strikeouts = data['strikeOuts']

                    # Singles = hits - doubles - triples - home runs
                    singles = data['hits'] - doubles - triples - homeRuns

                    # Outs = abs - all other categories
                    other_outs = pas - data['hits'] - walks - hbps - strikeouts

                    player_averages = subtract_arrays(player_averages, [singles, doubles, triples, homeRuns, walks, hbps, strikeouts, other_outs, pas])

        return normalize_averages(player_averages), [pa, h, k, bb, avg, ops, hr]


def get_career_vs_handedness(id, handedness, start_year, group, exclude_year):
    player_averages = np.zeros(9)

    for year in range(start_year, datetime.datetime.now().year + 1):
        if year == exclude_year:
            continue

        params = {
            'personIds': str(id),
            'hydrate': 'stats(group=[' + group + '],type=[statSplits],sitCodes=[v' + handedness + '],season=' + str(
                year) + ')'
        }
        data = statsapi.get('people', params=params)

        if len(data['people'][0]['stats'][0]['splits']) > 0:
            data = data['people'][0]['stats'][0]['splits'][0]['stat']

            doubles = data['doubles']
            triples = data['triples']
            home_runs = data['homeRuns']
            walks = (data['baseOnBalls'] + data['intentionalWalks'])
            hbps = data['hitByPitch']
            pas = data.get('plateAppearances', data.get('battersFaced'))
            strikeouts = data['strikeOuts']

            # Singles = hits - doubles - triples - home runs
            singles = data['hits'] - doubles - triples - home_runs

            # Outs = abs - all other categories
            other_outs = pas - data['hits'] - walks - hbps - strikeouts

            player_averages += [singles, doubles, triples, home_runs, walks, hbps, strikeouts, other_outs, pas]

    return normalize_averages(player_averages)


def subtract_arrays(a, b):
    for i in range(len(a)):
        a[i] -= b[i]

    return a
