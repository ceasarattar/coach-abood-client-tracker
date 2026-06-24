"""Unit tests for pure-Python logic in app.py (no HTTP / DB needed)."""
import pytest
from tests.conftest import _make_form


# ---------------------------------------------------------------------------
# _parse_program_form
# ---------------------------------------------------------------------------

def test_parse_program_form_empty_sessions(flask_app):
    """No session labels → empty schedule."""
    with flask_app.app_context():
        from app import _parse_program_form
        form = _make_form(name='Test', notes='', ex_name='')
        result = _parse_program_form(form)
    assert result['schedule'] == []
    assert result['exercises'] == []
    assert result['name'] == 'Test'


def test_parse_program_form_three_sessions(flask_app):
    """Three session labels → ordered schedule entries."""
    with flask_app.app_context():
        from app import _parse_program_form
        form = _make_form(
            name='PPL',
            notes='',
            session_label=['Push', 'Pull', 'Legs'],
            ex_name='',
        )
        result = _parse_program_form(form)
    sched = result['schedule']
    assert len(sched) == 3
    assert sched[0] == {'day_order': 1, 'day_name': 'Push', 'workout_type': 'Push'}
    assert sched[1] == {'day_order': 2, 'day_name': 'Pull', 'workout_type': 'Pull'}
    assert sched[2] == {'day_order': 3, 'day_name': 'Legs', 'workout_type': 'Legs'}


def test_parse_program_form_strips_whitespace(flask_app):
    """Leading/trailing whitespace in session labels is stripped."""
    with flask_app.app_context():
        from app import _parse_program_form
        form = _make_form(
            name='X', notes='',
            session_label=['  Push  ', '  Pull'],
        )
        result = _parse_program_form(form)
    assert result['schedule'][0]['day_name'] == 'Push'
    assert result['schedule'][1]['day_name'] == 'Pull'


def test_parse_program_form_skips_blank_session_labels(flask_app):
    """Blank session labels (empty strings, whitespace-only) are dropped."""
    with flask_app.app_context():
        from app import _parse_program_form
        form = _make_form(
            name='X', notes='',
            session_label=['Push', '   ', '', 'Legs'],
        )
        result = _parse_program_form(form)
    assert len(result['schedule']) == 2
    assert result['schedule'][0]['workout_type'] == 'Push'
    assert result['schedule'][1]['workout_type'] == 'Legs'


def test_parse_program_form_exercises(flask_app):
    """Exercises are parsed from parallel arrays and skip blank names."""
    with flask_app.app_context():
        from app import _parse_program_form
        form = _make_form(
            name='PPL', notes='',
            session_label=['Push'],
            ex_type=['Push', 'Push'],
            ex_name=['Bench Press', ''],          # second row has blank name
            ex_sets=['4', '3'],
            ex_reps=['8', '10'],
            ex_notes=['Heavy', ''],
            ex_url=['https://example.com', ''],
        )
        result = _parse_program_form(form)
    exs = result['exercises']
    assert len(exs) == 1
    assert exs[0]['exercise'] == 'Bench Press'
    assert exs[0]['target_sets'] == '4'
    assert exs[0]['target_reps'] == '8'
    assert exs[0]['coach_notes'] == 'Heavy'
    assert exs[0]['tutorial_url'] == 'https://example.com'
    assert exs[0]['workout_type'] == 'Push'


# ---------------------------------------------------------------------------
# _build_config_payload
# ---------------------------------------------------------------------------

def _sample_wizard_data():
    return {
        'info': {
            'name': 'John Doe',
            'email': 'john@example.com',
            'program_name': 'Hypertrophy',
            'goal': 'Build muscle',
            'start_date': '01/07/2026',
            'weight_unit': 'kg',
            'plan_usd': '150',
            'billing_day': '1',
        },
        'schedule': [
            {'day_order': 1, 'day_name': 'Push', 'workout_type': 'Push'},
            {'day_order': 2, 'day_name': 'Pull', 'workout_type': 'Pull'},
        ],
        'exercises': [
            {'workout_type': 'Push', 'position': 0, 'exercise': 'Bench Press',
             'target_sets': '4', 'target_reps': '8', 'coach_notes': '', 'tutorial_url': ''},
            {'workout_type': 'Pull', 'position': 1, 'exercise': 'Row',
             'target_sets': '4', 'target_reps': '10', 'coach_notes': '', 'tutorial_url': ''},
        ],
        'weeks': [{'week': 1, 'rir': '3'}, {'week': 2, 'rir': '2'}],
        'targets': {'calories': '2400', 'protein': '180', 'carbs': '250', 'fat': '70', 'fiber': '35'},
        'sleep_target': '8',
    }


def test_build_config_payload_shape(flask_app):
    """Config payload contains all required top-level keys."""
    with flask_app.app_context():
        from app import _build_config_payload
        cfg = _build_config_payload(_sample_wizard_data())
    assert set(cfg.keys()) == {'info', 'sessions', 'weeks', 'targets', 'sleepTarget'}


def test_build_config_payload_info(flask_app):
    """Info block has all 8 required fields."""
    with flask_app.app_context():
        from app import _build_config_payload
        cfg = _build_config_payload(_sample_wizard_data())
    info = cfg['info']
    assert info['name'] == 'John Doe'
    assert info['email'] == 'john@example.com'
    assert info['program'] == 'Hypertrophy'
    assert info['goal'] == 'Build muscle'
    assert info['start'] == '01/07/2026'
    assert info['unit'] == 'kg'
    assert info['plan'] == '150'
    assert info['billing'] == '1'


def test_build_config_payload_sessions(flask_app):
    """Sessions list groups exercises by workout_type."""
    with flask_app.app_context():
        from app import _build_config_payload
        cfg = _build_config_payload(_sample_wizard_data())
    sessions = cfg['sessions']
    assert len(sessions) == 2
    push = sessions[0]
    assert push['label'] == 'Push'
    assert len(push['exercises']) == 1
    assert push['exercises'][0]['ex'] == 'Bench Press'
    pull = sessions[1]
    assert pull['label'] == 'Pull'
    assert pull['exercises'][0]['ex'] == 'Row'


def test_build_config_payload_targets_list(flask_app):
    """Targets are serialised as a list [cal, protein, carbs, fat, fiber]."""
    with flask_app.app_context():
        from app import _build_config_payload
        cfg = _build_config_payload(_sample_wizard_data())
    assert cfg['targets'] == ['2400', '180', '250', '70', '35']


def test_build_config_payload_weeks(flask_app):
    """Weeks list is passed through unchanged."""
    with flask_app.app_context():
        from app import _build_config_payload
        cfg = _build_config_payload(_sample_wizard_data())
    assert cfg['weeks'] == [{'week': 1, 'rir': '3'}, {'week': 2, 'rir': '2'}]


def test_build_config_payload_sleep_target(flask_app):
    """sleepTarget is taken from data['sleep_target']."""
    with flask_app.app_context():
        from app import _build_config_payload
        cfg = _build_config_payload(_sample_wizard_data())
    assert cfg['sleepTarget'] == '8'


def test_build_config_payload_missing_sleep_target(flask_app):
    """sleepTarget defaults to '' when not present."""
    with flask_app.app_context():
        from app import _build_config_payload
        data = _sample_wizard_data()
        del data['sleep_target']
        cfg = _build_config_payload(data)
    assert cfg['sleepTarget'] == ''


def test_build_config_payload_exercise_link_to_wrong_session(flask_app):
    """Exercise whose workout_type matches no session gets grouped under that label with empty list."""
    with flask_app.app_context():
        from app import _build_config_payload
        data = _sample_wizard_data()
        # Add a session 'Legs' but no exercises for it.
        data['schedule'].append({'day_order': 3, 'day_name': 'Legs', 'workout_type': 'Legs'})
        cfg = _build_config_payload(data)
    legs = cfg['sessions'][2]
    assert legs['label'] == 'Legs'
    assert legs['exercises'] == []


# ---------------------------------------------------------------------------
# _parse_wizard_form
# ---------------------------------------------------------------------------

def test_parse_wizard_form_full(flask_app):
    """Full wizard form parse produces correct shape."""
    with flask_app.app_context():
        from app import _parse_wizard_form
        form = _make_form(
            name='Jane', email='jane@example.com',
            program_name='Cut', goal='Lose fat',
            start_date='01/08/2026', weight_unit='lbs',
            plan_usd='100', billing_day='15',
            session_label=['Upper', 'Lower'],
            ex_type=['Upper', 'Lower'],
            ex_name=['OHP', 'Squat'],
            ex_sets=['3', '4'],
            ex_reps=['10', '8'],
            ex_notes=['', ''],
            ex_url=['', ''],
            num_weeks='2',
            rir_1='3', rir_2='2',
            calories='2000', protein='150',
            carbs='200', fat='60', fiber='30',
            sleep_target='7',
        )
        result = _parse_wizard_form(form)

    assert result['info']['name'] == 'Jane'
    assert result['info']['email'] == 'jane@example.com'
    assert result['info']['weight_unit'] == 'lbs'
    assert len(result['schedule']) == 2
    assert len(result['exercises']) == 2
    assert len(result['weeks']) == 2
    assert result['weeks'][0] == {'week': 1, 'rir': '3'}
    assert result['weeks'][1] == {'week': 2, 'rir': '2'}
    assert result['targets']['calories'] == '2000'
    assert result['sleep_target'] == '7'


def test_parse_wizard_form_defaults_weight_unit(flask_app):
    """weight_unit defaults to 'kg' when not supplied."""
    with flask_app.app_context():
        from app import _parse_wizard_form
        form = _make_form(name='X', email='', program_name='', goal='',
                          start_date='', plan_usd='', billing_day='', num_weeks='0',
                          calories='', protein='', carbs='', fat='', fiber='')
        result = _parse_wizard_form(form)
    assert result['info']['weight_unit'] == 'kg'
