from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import random, sqlite3, os, json

app = Flask(__name__)
app.secret_key = 'experiment_secret_2024'

GITHUB_RAW = "https://raw.githubusercontent.com/Kristalilina/experiment/main/images"

DIFY_KEYS = {
    'impolite': 'app-2U7wxhiNamGrF22tAACAwlpU',
    'original':  'app-guzw4NnInEtfZIbxIizHPBMK',
    'polite':    'app-a5Mm3Ha6HVZyfFKQogdSE2kY',
}

# 商品数据：名称 + 图片扩展名
PRODUCTS = {
    'practice': [('专业运动服','.jpeg'),('独轮车','.png'),('计算器','.jpeg')],
    'S1': [('专业自行车','.png'),('便利贴','.jpeg'),('冲锋衣','.jpeg'),('基础自行车','.png'),
           ('奶茶','.jpeg'),('姜糖水','.jpeg'),('校服','.jpeg'),('椰子水','.jpeg'),
           ('滑板车','.png'),('酒店热水壶','.png')],
    'S2': [('cos服','.jpeg'),('塑料回形针','.png'),('微波炉','.jpeg'),('桌面摆件','.png'),
           ('桌面收纳盒','.png'),('氛围灯','.jpeg'),('电动行李箱','.png'),('电饭煲','.png'),
           ('脚踏式三轮车','.png'),('运动饮料','.jpeg')],
    'S3': [('家用衣物护理机','.png'),('彩色笔（黑色）','.png'),('拖拉机','.jpeg'),('果味汽水','.jpeg'),
           ('热得快','.jpeg'),('电动车','.png'),('礼服','.jpeg'),('维他命水','.jpeg'),
           ('绿豆汤','.jpeg'),('订书机','.jpeg')],
    'S4': [('工作正装','.jpeg'),('折叠水壶','.png'),('文件夹','.png'),('智能电视','.png'),
           ('洛丽塔','.jpeg'),('茶饮料','.png'),('蛋白饮料','.jpeg'),('轮椅','.png'),
           ('迷你加湿器','.jpeg'),('雪碧','.jpeg')],
    'S5': [('传统电风扇','.jpeg'),('可乐','.jpeg'),('夹克','.jpeg'),('干姜水','.png'),
           ('打印机','.png'),('扭扭车','.png'),('智能冰箱','.jpeg'),('纯净水','.png'),
           ('造型款小电扇','.png'),('金银花露','.jpeg')],
}

LATIN_SQUARE = [
    [('S1','L1'),('S2','L2'),('S3','L3'),('S4','L4'),('S5','L5')],
    [('S2','L3'),('S3','L4'),('S4','L5'),('S5','L1'),('S1','L2')],
    [('S3','L5'),('S4','L1'),('S5','L2'),('S1','L3'),('S2','L4')],
    [('S4','L2'),('S5','L3'),('S1','L4'),('S2','L5'),('S3','L1')],
    [('S5','L4'),('S1','L5'),('S2','L1'),('S3','L2'),('S4','L3')],
]

L_WORKFLOWS = {
    'L1': ['impolite','impolite'],
    'L2': ['impolite','original'],
    'L3': ['original','original'],
    'L4': ['original','polite'],
    'L5': ['polite','polite'],
}

DB_FILE = 'experiment.db'

# ── 数据库 ──────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS counter (
            id INTEGER PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0
        );
        INSERT OR IGNORE INTO counter (id, count) VALUES (1, 0);

        CREATE TABLE IF NOT EXISTS pre_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER, product_name TEXT, value_rating INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trial_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER, phase TEXT,
            block_num INTEGER, product_name TEXT,
            trial_num INTEGER, workflow TEXT,
            question TEXT, response TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS post_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER, phase TEXT,
            block_num INTEGER, product_name TEXT,
            politeness_rating INTEGER, value_rating INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()

def get_next_participant_number():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('UPDATE counter SET count = count + 1 WHERE id = 1')
    conn.commit()
    n = conn.execute('SELECT count FROM counter WHERE id=1').fetchone()[0]
    conn.close()
    return n - 1  # 0-based

init_db()

# ── 实验计划生成（由被试编号确定性生成，不存入session）─────────────────────

def img_url(set_key, name, ext):
    folder = 'practice' if set_key == 'practice' else set_key.lower().replace('s','set',1)
    return f"{GITHUB_RAW}/{folder}/{name}{ext}"

def build_plan(pid):
    """根据被试编号生成完整实验方案"""
    # 前测：所有53个商品随机排序
    all_products = []
    for name, ext in PRODUCTS['practice']:
        all_products.append({'name': name, 'img': img_url('practice', name, ext), 'set': 'practice'})
    for sk in ['S1','S2','S3','S4','S5']:
        for name, ext in PRODUCTS[sk]:
            all_products.append({'name': name, 'img': img_url(sk, name, ext), 'set': sk})
    random.seed(pid * 10)
    random.shuffle(all_products)

    # 拉丁方：确定5个block的S+L分配
    position = pid % 5
    blocks = list(LATIN_SQUARE[position])
    random.seed(pid)
    random.shuffle(blocks)

    # 每个block内商品顺序 + 每个商品的trial顺序
    formal_blocks = []
    for block_idx, (sk, lk) in enumerate(blocks):
        products_in_set = list(PRODUCTS[sk])
        random.seed(pid * 100 + block_idx)
        random.shuffle(products_in_set)
        wfs = L_WORKFLOWS[lk]
        trial_orders = []
        for pi in range(10):
            seed = pid * 1000 + block_idx * 10 + pi
            random.seed(seed)
            order = list(wfs)
            random.shuffle(order)
            if len(trial_orders) >= 2 and trial_orders[-1] == trial_orders[-2] == order:
                order = list(reversed(order))
            trial_orders.append(order)
        formal_blocks.append({
            'set': sk, 'level': lk,
            'products': [{'name': n, 'img': img_url(sk, n, e), 'trials': trial_orders[i]}
                         for i, (n, e) in enumerate(products_in_set)],
        })

    # 练习block（使用original+original，顺序随机）
    practice_products = []
    for i, (name, ext) in enumerate(PRODUCTS['practice']):
        practice_products.append({
            'name': name, 'img': img_url('practice', name, ext),
            'trials': ['original', 'original']
        })

    return {
        'pre_rating': all_products,
        'practice': practice_products,
        'formal': formal_blocks,
    }

# ── 路由 ────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        if not name:
            return render_template('login.html', error='请输入您的姓名或编号')
        pid = get_next_participant_number()
        session.clear()
        session['pid']     = pid
        session['pname']   = name
        session['pnum']    = pid + 1
        session['phase']   = 'pre_rating'
        session['pr_idx']  = 0   # 前测商品索引
        return redirect(url_for('pre_rating'))
    return render_template('login.html', error=None)

@app.route('/pre-rating', methods=['GET','POST'])
def pre_rating():
    if 'pid' not in session: return redirect(url_for('login'))
    plan = build_plan(session['pid'])
    products = plan['pre_rating']
    idx = session.get('pr_idx', 0)

    if request.method == 'POST':
        value = request.form.get('value', 0)
        product_name = request.form.get('product_name')
        conn = sqlite3.connect(DB_FILE)
        conn.execute('INSERT INTO pre_ratings (participant_id,product_name,value_rating) VALUES (?,?,?)',
                     (session['pid'], product_name, value))
        conn.commit(); conn.close()
        idx += 1
        session['pr_idx'] = idx
        if idx >= len(products):
            session['phase'] = 'practice'
            session['p_idx'] = 0
            session['step']  = 'trial1'
            return redirect(url_for('experiment'))
        return redirect(url_for('pre_rating'))

    product = products[idx]
    return render_template('pre_rating.html',
        product=product, idx=idx+1, total=len(products))

@app.route('/experiment', methods=['GET','POST'])
def experiment():
    if 'pid' not in session: return redirect(url_for('login'))
    phase = session.get('phase')
    if phase == 'complete':
        return redirect(url_for('complete'))

    plan = build_plan(session['pid'])

    # 确定当前商品
    if phase == 'practice':
        products = plan['practice']
        p_idx = session.get('p_idx', 0)
        block_num = 0
        if p_idx >= len(products):
            session['phase'] = 'formal'
            session['b_idx'] = 0
            session['p_idx'] = 0
            session['step']  = 'trial1'
            return redirect(url_for('experiment'))
        product = products[p_idx]
    else:  # formal
        b_idx = session.get('b_idx', 0)
        p_idx = session.get('p_idx', 0)
        block_num = b_idx + 1
        if b_idx >= len(plan['formal']):
            session['phase'] = 'complete'
            return redirect(url_for('complete'))
        block = plan['formal'][b_idx]
        if p_idx >= len(block['products']):
            session['b_idx'] = b_idx + 1
            session['p_idx'] = 0
            session['step']  = 'trial1'
            return redirect(url_for('experiment'))
        product = block['products'][p_idx]

    step = session.get('step', 'trial1')

    if request.method == 'POST':
        if step in ('trial1', 'trial2'):
            trial_num = 1 if step == 'trial1' else 2
            workflow  = request.form.get('workflow')
            question  = request.form.get('question')
            response  = request.form.get('response')
            conn = sqlite3.connect(DB_FILE)
            conn.execute('''INSERT INTO trial_responses
                (participant_id,phase,block_num,product_name,trial_num,workflow,question,response)
                VALUES (?,?,?,?,?,?,?,?)''',
                (session['pid'], phase, block_num, product['name'],
                 trial_num, workflow, question, response))
            conn.commit(); conn.close()
            session['step'] = 'trial2' if step == 'trial1' else 'politeness'
            return redirect(url_for('experiment'))

        elif step == 'politeness':
            pol = request.form.get('politeness_rating')
            session['pol_rating'] = pol
            session['step'] = 'value'
            return redirect(url_for('experiment'))

        elif step == 'value':
            pol  = session.get('pol_rating', 0)
            val  = request.form.get('value_rating')
            conn = sqlite3.connect(DB_FILE)
            conn.execute('''INSERT INTO post_ratings
                (participant_id,phase,block_num,product_name,politeness_rating,value_rating)
                VALUES (?,?,?,?,?,?)''',
                (session['pid'], phase, block_num, product['name'], pol, val))
            conn.commit(); conn.close()
            p_idx += 1
            session['p_idx'] = p_idx
            session['step']  = 'trial1'
            return redirect(url_for('experiment'))

    # GET：根据step渲染不同页面
    trial_num = 1 if step == 'trial1' else 2
    workflow  = product['trials'][0] if step == 'trial1' else product['trials'][1]

    if step in ('trial1', 'trial2'):
        return render_template('trial.html',
            product=product, trial_num=trial_num,
            workflow=workflow, dify_key=DIFY_KEYS[workflow])
    elif step == 'politeness':
        return render_template('politeness_rating.html', product=product)
    elif step == 'value':
        return render_template('value_rating.html', product=product)

@app.route('/complete')
def complete():
    return render_template('complete.html', name=session.get('pname',''))

@app.route('/reset')
def reset():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('UPDATE counter SET count=0 WHERE id=1')
    conn.commit(); conn.close()
    return '计数器已重置 <a href="/">返回</a>'

if __name__ == '__main__':
    app.run(debug=True, port=5000)
