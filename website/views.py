from flask import Blueprint, render_template, request

views = Blueprint('views', __name__)


@views.route('/', methods=['GET', 'POST'])
def home():
    name = ""
    if request.method == 'POST':
        name = request.form.get('name')

    return render_template('home.html', batter=name)
