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

def get_trial_orders(workflows, counter, block_idx, num_products=10):
    """
    为一个block的所有商品生成trial顺序。
    - 两个trial相同（L1/L3/L5）：顺序无意义，直接返回
    - 两个trial不同（L2/L4）：每个商品独立随机，但同一顺序不超过连续2次
    """
    if workflows[0] == workflows[1]:
        return [list(workflows)] * num_products

    orders = []
    for product_idx in range(num_products):
        seed = counter * 1000 + block_idx * 10 + product_idx
        random.seed(seed)
        order = list(workflows)
        random.shuffle(order)
        # 若已连续2次相同顺序，强制翻转，避免出现连续3次
        if len(orders) >= 2 and orders[-1] == orders[-2] == order:
            order = list(reversed(order))
        orders.append(order)
    return orders


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
        # 随机打乱5个block的呈现顺序（S+L绑定不变）
        blocks = list(LATIN_SQUARE[position])
        random.seed(counter)
        random.shuffle(blocks)

        # 为每个block的每个商品预生成trial顺序
        blocks_with_trials = []
        for block_idx, (s, l) in enumerate(blocks):
            trial_orders = get_trial_orders(L_INFO[l]['workflows'], counter, block_idx)
            blocks_with_trials.append((s, l, trial_orders))

        session['name'] = name
        session['display_number'] = display_number
        session['position'] = position
        session['blocks'] = blocks_with_trials
        return redirect(url_for('experiment'))
    return render_template('login.html', error=None)

@app.route('/experiment')
def experiment():
    if 'name' not in session:
        return redirect(url_for('login'))
    blocks_info = []
    for i, (s, l, trial_orders) in enumerate(session['blocks']):
        blocks_info.append({
            'block_num': i + 1,
            'set': s,
            'level': l,
            'level_label': L_INFO[l]['label'],
            'trial_orders': trial_orders,  # 10个商品各自的trial顺序
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
