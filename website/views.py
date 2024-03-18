from flask import Blueprint, render_template, request, url_for
import statsapi

views = Blueprint('views', __name__)

batter = "Bo Bichette"
pitcher = "Kevin Gausman"


@views.route('/', methods=['GET', 'POST'])
def home():
    global batter, pitcher

    if request.method == 'POST':
        if 'batter' in request.form:
            batter = request.form.get('batter')
        elif 'pitcher' in request.form:
            pitcher = request.form.get('pitcher')

    batter_data = statsapi.lookup_player(batter.split()[1])[0]
    batter_id = batter_data['id']
    hitting_data = statsapi.player_stat_data(batter_id, "hitting", "career")

    pitcher_data = statsapi.lookup_player(pitcher.split()[1])[0]
    pitcher_id = pitcher_data['id']
    pitching_data = statsapi.player_stat_data(pitcher_id, "pitching", "career")

    return render_template('home.html', batter_data=batter_data, hitting_data=hitting_data, pitcher_data=pitcher_data,
                           pitching_data=pitching_data)
