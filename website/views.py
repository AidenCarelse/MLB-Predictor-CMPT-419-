from flask import Blueprint, render_template, request, url_for
import statsapi

views = Blueprint('views', __name__)

batter = "Bo Bichette"
pitcher = "Kevin Gausman"
batter_error = ""
pitcher_error = ""


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
    batter_img = ('https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/'
                  +str(batter_id)+'/headshot/67/current')
    hitting_data = statsapi.player_stat_data(batter_id, "hitting", "career")

    pitcher_data = statsapi.lookup_player(pitcher.split()[1])[0]
    pitcher_id = pitcher_data['id']
    pitcher_img = ('https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/'
                  + str(pitcher_id) + '/headshot/67/current')
    pitching_data = statsapi.player_stat_data(pitcher_id, "pitching", "career")

    # RESET errors on calculation

    return render_template('home.html', batter_data=batter_data, hitting_data=hitting_data,
                           batter_error=batter_error, batter_img=batter_img, pitcher_data=pitcher_data, pitching_data=pitching_data,
                           pitcher_error=pitcher_error, pitcher_img=pitcher_img)
