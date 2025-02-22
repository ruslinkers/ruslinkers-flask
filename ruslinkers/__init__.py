import os

from collections import defaultdict

from flask import Flask, render_template, request, redirect, url_for, send_file

from ruslinkers.database import db_session, diachronic
from ruslinkers.models import *
import sqlalchemy as db

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'ruslinkers-new4.db'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route('/oss-connectors/<path:path>', methods=['GET'])
    def oss_connectors(path):
        # return send_file(url_for('static', filename='oss-connectors-r/_site/' + path))
        return app.send_static_file('oss-connectors-r/_site/' + path)
    
    @app.route('/bezhta-connectors/<path:path>', methods=['GET'])
    def bezhta_connectors(path):
        # return send_file(url_for('static', filename='oss-connectors-r/_site/' + path))
        return app.send_static_file('bezhta-connectors-r/_site/' + path)    
    
    @app.route('/uralic-connectors/<path:path>', methods=['GET'])
    def uralic_connectors(path):
        # return send_file(url_for('static', filename='oss-connectors-r/_site/' + path))
        return app.send_static_file('fu-connectors-r/_site/' + path)    

    @app.route('/', methods=['GET'])
    def home():
        return render_template('home.html')

    @app.route('/participants', methods=['GET'])
    def participants():
        return render_template('participants.html')

    # show unit
    @app.route('/units/<linker>', methods=['GET','POST'])
    def units(linker: str):
        error = None

        if request.method == 'POST':
            if request.form['action'] == 'setattr' or request.form['action'] == 'delobject':
                match request.form['target_type']:
                    case 'unit':
                        targetClass = Unit
                    case 'form':
                        targetClass = Form
                    case _:
                        return('',422)
                target = db_session.scalars(db.select(targetClass).where(targetClass.id == int(request.form['target_id']))).one()
                if request.form['action'] == 'setattr':
                    setattr(target,request.form['attr'],request.form['newvalue'])
                elif request.form['action'] == 'delobject':
                    db_session.delete(target)
                    db_session.commit()
            elif request.form['action'] == 'addform':
                formtype = db_session.scalars(db.select(FormType).where(FormType.keyword == request.form['formtype'])).one()
                newform = Form(
                    unit_id = request.form['unit_id'],
                    formtype = formtype,
                    text = request.form['text']
                )
                db_session.add(newform)
            db_session.commit()
            return redirect(url_for('units',linker=linker))

        # Filter the units according to search request
        stmt = db.select(Unit)
        if request.args.get("search-pos") is not None:
            stmt = stmt.where(Meaning.pos == request.args.get("search-pos")).where(Meaning.unit_id == Unit.id)
        if request.args.get("search-dict") is not None:
            # stmt = stmt.where(Source.id == request.args.get("search-dict"))
            stmt = stmt.where(sources_to_units.c.source_id == request.args.get("search-dict")).where(sources_to_units.c.unit_id == Unit.id)
        if request.args.get("search-conn") is not None:
            stmt = stmt.where(Unit.linker == request.args.get("search-conn"))
        if request.args.get("search-correl") is not None:
            stmt = stmt.where(FormType.keyword == 'correl').where(Form.formtype_id == FormType.id and Form.unit_id == Unit.id)

        units = db_session.scalars(stmt.distinct()).all()

        units_gr = defaultdict(list)
        for u in units:
            units_gr[u.linker].append(u)
        examples = db_session.scalars(db.select(Example)).all()
        meanings = db_session.scalars(db.select(Meaning)).all()
        # Collect all unique parts of speech
        pos_list = [mng.pos for mng in meanings]
        seen = set()
        pos_uniq = [val for val in pos_list if val not in seen and (seen.add(val) or True)]
        pos_uniq.sort()
        # Get sources
        sources = sorted(db_session.scalars(db.select(Source)).all(), key = lambda source: source.biblio)
        return render_template('units.html',
                               sources=sources,
                               pos_list=pos_uniq,
                               edit=False,
                               units=units_gr,
                               examples=examples,
                               linker=linker,
                               error=error,
                               olds=diachronic[linker] if linker in diachronic.keys() else None)
    
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    return app