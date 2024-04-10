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

''' TODO (if time)
- Player search dropdown
- Accents in names
- Async, make loading easier to understand for user
- Allow users to select both players at once
'''


# Main view function, computes values and returns home view
@views.route('/', methods=['GET', 'POST'])
def home():
    global batter, pitcher, head_to_head_data

    # Generate random players if not chosen
    if batter == "":
        batter = get_random_player(False)['person']['fullName']
    if pitcher == "":
        pitcher = get_random_player(True)['person']['fullName']

    # Rest error text
    batter_error = ""
    pitcher_error = ""

    # Handle POST requests (searching for a player)
    if request.method == 'POST':

        # Receive batter name
        if 'batter' in request.form:
            tmp = request.form.get('batter')
            tmp_data = statsapi.lookup_player(tmp)

            # Verify player
            if len(tmp_data) == 0 or len(tmp) == 0:
                batter_error = "Player not found!"
            elif tmp_data[0]['primaryPosition']['abbreviation'] == 'P':
                batter_error = "Player is not a batter!"
            else:
                batter = tmp

        # Receive pitcher name
        elif 'pitcher' in request.form:
            tmp = request.form.get('pitcher')
            tmp_data = statsapi.lookup_player(tmp)

            # Verify player
            if len(tmp_data) == 0 or len(tmp) == 0:
                pitcher_error = "Player not found!"
            elif (tmp_data[0]['primaryPosition']['abbreviation'] != 'P'
                  and tmp_data[0]['primaryPosition']['abbreviation'] != 'TWP'):
                pitcher_error = "Player is not a pitcher!"
            else:
                pitcher = tmp

    # Get batter info
    batter_data = statsapi.lookup_player(batter)[0]
    batter_id = batter_data['id']
    batter_img = (
            'https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/'
            + str(batter_id) + '/headshot/67/current')
    hitting_data = statsapi.player_stat_data(batter_id, "hitting", "career")

    # Get pitcher info
    pitcher_data = statsapi.lookup_player(pitcher)[0]
    pitcher_id = pitcher_data['id']
    pitcher_img = (
            'https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/'
            + str(pitcher_id) + '/headshot/67/current')
    pitching_data = statsapi.player_stat_data(pitcher_id, "pitching", "career")

    # Calculate outcomes (including leave one out year influence)
    outcomes, loo_year = calculate_outcomes(hitting_data, pitching_data, None)

    # Render the view with calculated items
    return render_template('home.html', batter_data=batter_data, hitting_data=hitting_data,
                           batter_error=batter_error, batter_img=batter_img, pitcher_data=pitcher_data,
                           pitching_data=pitching_data, pitcher_error=pitcher_error, pitcher_img=pitcher_img,
                           outcomes=outcomes, loo_year=loo_year, head_to_head_data=head_to_head_data)


# Calculate the predictions for the given match up
def calculate_outcomes(batting_data, pitching_data, exclude_year):
    global head_to_head_data

    # Find the data range
    min_year = int(batting_data['mlb_debut'][0:4])
    p_debut = int(pitching_data['mlb_debut'][0:4])

    max_year = min_year
    if p_debut < min_year:
        min_year = p_debut
    else:
        max_year = p_debut

    # Get the handedness of the players
    batter_hand = batting_data['bat_side'][0].lower()
    pitcher_hand = pitching_data['pitch_hand'][0].lower()

    # Get the league average in the year range
    league_averages = get_league_averages(min_year, datetime.datetime.now().year, exclude_year)

    # Get the head-to-head data
    b_h2h, d_h2h = fetch_head_to_head(batting_data['id'], pitching_data['id'], exclude_year)
    if exclude_year is None:
        head_to_head_data = d_h2h

    # Get the rest of the batter's career data
    b_hand = get_career_vs_handedness(batting_data['id'], pitcher_hand, int(batting_data['mlb_debut'][0:4]),
                                      'hitting', exclude_year)
    b_recent = get_last_x_games(batting_data['id'], 'batting', exclude_year)
    b_career = get_player_averages(batting_data, False, exclude_year)

    if np.all(b_h2h == 0):
        b_h2h = b_career

    # Calculate the batter's averages
    batter_averages = (0.2 * b_h2h) + (0.15 * b_hand) + (0.3 * b_recent) + (0.35 * b_career)

    # Get the pitcher's data
    p_h2h = fetch_head_to_head(batting_data['id'], pitching_data['id'], exclude_year)[0]
    p_hand = get_career_vs_handedness(pitching_data['id'], batter_hand, int(pitching_data['mlb_debut'][0:4]),
                                      'pitching', exclude_year)
    p_recent = get_last_x_games(pitching_data['id'], 'pitching', exclude_year)
    p_career = get_player_averages(pitching_data, True, exclude_year)

    if np.all(p_h2h == 0):
        p_h2h = p_career

    # Get the rest of the batter's data
    pitcher_averages = (0.2 * p_h2h) + (0.15 * p_hand) + (0.3 * p_recent) + (0.35 * p_career)

    # Predict the outcomes with the calculated data
    outcomes = predict_outcomes(league_averages, batter_averages, pitcher_averages)

    # Parse results (There is never a 0% chance of one of these events happening, it data is limited, calculations may reflect that)
    hit = max(outcomes[0] + outcomes[1] + outcomes[2] + outcomes[3], 0.1)
    reach_base = max(hit + outcomes[4] + outcomes[5], 0.1)
    strikeout = max(outcomes[7], 0.1)
    home_run = max(outcomes[3], 0.1)

    # Format the predicted results
    predictions = ["{:.1f}".format(reach_base), "{:.1f}".format(hit), "{:.1f}".format(strikeout),
                   "{:.1f}".format(home_run)]

    # Create a list for holding LOO year influences
    curr_year = datetime.datetime.now().year + 1
    exclude_predictions = np.zeros((curr_year - max_year, 9))
    exclude_predictions = list(map(str, exclude_predictions))

    # If the current function isn't computing LOO, begin recursion
    if exclude_year is None:
        print(exclude_year, predictions)
        diffs = np.zeros(curr_year - max_year)

        # Loop through every year in which both players were in the league
        for i in range(max_year, curr_year):

            # Calculate the predictions with the year excluded
            curr_pred = calculate_outcomes(batting_data, pitching_data, i)[0]
            diff = np.sum(np.abs(np.array(predictions).astype(np.float_) - np.array(curr_pred).astype(np.float_)))

            curr_pred = list(map(str, curr_pred))
            print(i, curr_pred, diff)

            # Append both new prediction and differences from total career stats
            curr_pred = np.append(curr_pred, compute_difference(curr_pred[0], predictions[0]))
            curr_pred = np.append(curr_pred, compute_difference(curr_pred[1], predictions[1]))
            curr_pred = np.append(curr_pred, compute_difference(curr_pred[2], predictions[2]))
            curr_pred = np.append(curr_pred, compute_difference(curr_pred[3], predictions[3]))

            # Save the data into the lists
            curr_pred = np.append(curr_pred, str(i))
            diffs[i - max_year] = diff
            exclude_predictions[i - max_year] = curr_pred

        # Sort the data by placing the years with the highest total difference first
        combined_data = list(zip(diffs, exclude_predictions))
        sorted_combined_data = sorted(combined_data, key=lambda x: x[0], reverse=True)
        exclude_predictions = np.array([item[1] for item in sorted_combined_data])

        # Append blank rows if there is insufficient data
        rows = exclude_predictions.shape[0]
        while rows < 3:
            rows += 1
            new_row = ['', '', '', '', '', '', '', '', '']
            exclude_predictions = np.vstack((exclude_predictions, new_row))

        # Round values
        exclude_predictions[exclude_predictions == 'nan'] = 0.0
        exclude_predictions = [[s.split('.')[0] + '.' + s.split('.')[1][0] if '.' in s else s for s in row] for row in
                               exclude_predictions]

    # Return the career and LOO predictions
    return predictions, exclude_predictions


# Get the average stats of the entire league for a given range
def get_league_averages(start_year, end_year, exclude_year):
    league_averages = np.zeros(9)

    # Loop through the range
    for i in range(start_year, end_year + 1):

        # Skip the year if it's being excluded
        if i == exclude_year:
            continue

        # Specify parameters
        params = {
            'stats': 'Season',
            'group': 'hitting',
            'season': str(i),
            'playerPool': 'ALL',
            'limit': '2000'
        }

        # Get the specified data
        data = statsapi.get('stats', params=params)

        # Loop through each player in the data (MLB-Stats API does not have the option for getting league average stats)
        for split in data['stats'][0]['splits']:

            # Save values
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


# Get the stat averages of a specific player
def get_player_averages(player_data, pitcher, exclude_year):
    if len(player_data['stats']) == 0:
        return np.zeros(9)

    # Save the values from the data
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

    # Remove a specific year's data if LOO year influence is being calculated
    if exclude_year is not None:
        p_type = 'hitting'
        if pitcher:
            p_type = 'pitching'

        year_data = statsapi.player_stat_data(player_data['id'], p_type, 'yearByYear')

        for year in year_data['stats']:
            if year['season'] == str(exclude_year):

                # Remove the year form a player's total stats
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

                player_averages = subtract_arrays(player_averages,
                                                  [singles, doubles, triples, home_runs, walks, hbps, strikeouts,
                                                   other_outs, pas])

    return normalize_averages(player_averages)


# Calculate the predicted outcomes
def predict_outcomes(league, batter_avg, pitcher_avg):

    # Find the sum of all outcomes
    sum = 0
    for i in range(0, 8):
        sum += (batter_avg[i] * pitcher_avg[i]) / league[i]

    # Find the probability of specific outcomes
    outcomes = np.zeros(8)
    for i in range(0, 8):
        num = (batter_avg[i] * pitcher_avg[i]) / league[i]
        outcomes[i] = 100 * num / sum

    return outcomes


# Get a player's statistics over their most recent games
def get_last_x_games(id, group, exclude_year):

    # Determine how many games should be used (pitchers have more data per game and need less recent games)
    x = 50
    if group == 'pitching':
        x = 20
    year = datetime.datetime.now().year

    player_averages = np.zeros(9)

    # Keep looping until x games have been calculated
    while x > 0:

        # Skip the year if it's being excluded
        if year == exclude_year:
            year -= 1
            continue

        # Specify parameters
        params = {
            'personIds': str(id),
            'hydrate': 'stats(group=[' + group + '],type=[lastXGames],limit=' + str(x) + ',season=' + str(year) + ')'
        }

        # Get the data
        data = statsapi.get('people', params=params)['people'][0]

        if not ('stats' in data):
            break
        else:
            # Save data
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


# Convert the number for each outcome to the percentage over total at bats
def normalize_averages(averages):
    if averages[8] == 0:
        return np.zeros(9, dtype=float)

    # Divide each stat by total occurences
    for i in range(0, 8):
        averages[i] = averages[i] / averages[8]

    return np.array(averages).astype(float)


# Get a random MLB player
def get_random_player(is_pitcher):
    # Choose a random team
    team_id = get_random_team()

    # Specify params
    params = {
        'teamId': str(team_id),
        'sportId': 1
    }

    # Get the chosen team's roster
    roster = statsapi.get('team_roster', params=params)['roster']

    # Choose r random player that fits the wanted type
    while True:
        r = random.randint(0, len(roster) - 1)
        curr_player = roster[r]
        position = curr_player['position']['abbreviation']

        if position == 'TWP' or (position == 'P' and is_pitcher) or (position != 'P' and not is_pitcher):
            return curr_player


# Get a random team's ID
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


# Get the statistics from two players' past match ups
def fetch_head_to_head(batter_id, pitcher_id, exclude_year):

    # Specify params
    params = {
        'personIds': str(batter_id),
        'hydrate': 'stats(group=[hitting],type=[vsPlayer],opposingPlayerId={},sportId=1)'.format(pitcher_id)
    }

    # Get the data
    data = statsapi.get('people', params=params)['people'][0]['stats']
    year_data = data

    # Find career splits
    if 'season' in str(data[0]):
        data = data[1]
    else:
        data = data[0]

    if data['totalSplits'] == 0:
        return np.zeros(9), ['0', '0', '0', '0', '0.000', '0.000', '0']
    else:
        # Save data
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

        # If LOO influence is being calculated, exclude values
        if exclude_year is not None:
            year_data = year_data[1]['splits']
            for year in year_data:

                if not 'season' in year:
                    continue

                if year['season'] == str(exclude_year):

                    # Save data to remove
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

                    player_averages = subtract_arrays(player_averages,
                                                      [singles, doubles, triples, homeRuns, walks, hbps, strikeouts,
                                                       other_outs, pas])

        return normalize_averages(player_averages), [pa, h, k, bb, avg, ops, hr]


# Get a player's career stats vs players of the specific handedness
def get_career_vs_handedness(id, handedness, start_year, group, exclude_year):
    player_averages = np.zeros(9)

    # Loop through every year in a player's career
    for year in range(start_year, datetime.datetime.now().year + 1):

        # If the year is being excluded, skip it
        if year == exclude_year:
            continue

        # Specify params
        params = {
            'personIds': str(id),
            'hydrate': 'stats(group=[' + group + '],type=[statSplits],sitCodes=[v' + handedness + '],season=' + str(
                year) + ')'
        }

        # Get the data
        data = statsapi.get('people', params=params)

        # If data exists, save it
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


# Subtract two array's values
def subtract_arrays(a, b):
    for i in range(len(a)):
        a[i] -= b[i]

    return a


# Compute the percent change between two values
def compute_difference(a, b):
    if a == 'nan':
        a = '0.0'
    if b == 'nan':
        b = '0.0'

    number1 = float(a)
    number2 = float(b)

    result = number1 - number2

    # Create a readable string, including the change's sign
    if result >= 0:
        result_str = '+' + str(result)
    else:
        result_str = str(result)

    return result_str
