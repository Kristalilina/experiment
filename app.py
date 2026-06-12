from flask import Flask, render_template, request, session, redirect, url_for
import random
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'experiment_secret_2024'

LATIN_SQUARE = [
    [('S1','L1'), ('S2','L2'), ('S3','L3'), ('S4','L4'), ('S5','L5')],
    [('S2','L3'), ('S3','L4'), ('S4','L5'), ('S5','L1'), ('S1','L2')],
    [('S3','L5'), ('S4','L1'), ('S5','L2'), ('S1','L3'), ('S2','L4')],
    [('S4','L2'), ('S5','L3'), ('S1','L4'), ('S2','L5'), ('S3','L1')],
    [('S5','L4'), ('S1','L5'), ('S2','L1'), ('S3','L2'), ('S4','L3')],
]

L_INFO = {
    'L1': {'label': '非常不礼貌', 'workflows': ['impolite', 'impolite']},
    'L2': {'label': '不礼貌',     'workflows': ['impolite', 'original']},
    'L3': {'label': '中性',       'workflows': ['original', 'original']},
    'L4': {'label': '礼貌',       'workflows': ['original', 'polite']},
    'L5': {'label': '非常礼貌',   'workflows': ['polite',   'polite']},
}

DB_FILE = 'experiment.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS counter (
            id INTEGER PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0
        )
    ''')
    conn.execute('INSERT OR IGNORE INTO counter (id, count) VALUES (1, 0)')
    conn.commit()
    conn.close()

def get_next_participant_number():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('UPDATE counter SET count = count + 1 WHERE id = 1')
    conn.commit()
    count = conn.execute('SELECT count FROM counter WHERE id = 1').fetchone()[0]
    conn.close()
    return count - 1  # 0-based

def reset_counter():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('UPDATE counter SET count = 0 WHERE id = 1')
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            return render_template('login.html', error='请输入您的姓名或编号')
        counter = get_next_participant_number()
        position = counter % 5
        display_number = counter + 1
        blocks = list(LATIN_SQUARE[position])
        random.seed(counter)
        random.shuffle(blocks)
        session['name'] = name
        session['display_number'] = display_number
        session['position'] = position
        session['blocks'] = blocks
        return redirect(url_for('experiment'))
    return render_template('login.html', error=None)

@app.route('/experiment')
def experiment():
    if 'name' not in session:
        return redirect(url_for('login'))
    blocks_info = []
    for i, (s, l) in enumerate(session['blocks']):
        blocks_info.append({
            'block_num': i + 1,
            'set': s,
            'level': l,
            'level_label': L_INFO[l]['label'],
            'workflows': L_INFO[l]['workflows'],
        })
    return render_template('experiment.html',
                           name=session['name'],
                           display_number=session['display_number'],
                           position=session['position'] + 1,
                           blocks=blocks_info)

@app.route('/reset')
def reset():
    reset_counter()
    return '计数器已重置，<a href="/">返回首页</a>'

if __name__ == '__main__':
    app.run(debug=True, port=5000)
