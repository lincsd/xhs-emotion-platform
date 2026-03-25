#!/usr/bin/env python3
"""
生成全年级 语数英 考卷真题卡片 JSON 文件
每个年级学期生成一个 {科目}_{年级短码}_考卷.json
已存在的文件(数学_三下_考卷.json, 英语_三下_考卷.json)跳过
"""
import json, os, copy

OUT_DIR = os.path.join(os.path.dirname(__file__), 'public', 'knowledge_cards', '小学')

GRADES = [
    ('一年级', '一上', '上册'),
    ('一年级', '一下', '下册'),
    ('二年级', '二上', '上册'),
    ('二年级', '二下', '下册'),
    ('三年级', '三上', '上册'),
    ('三年级', '三下', '下册'),
    ('四年级', '四上', '上册'),
    ('四年级', '四下', '下册'),
    ('五年级', '五上', '上册'),
    ('五年级', '五下', '下册'),
    ('六年级', '六上', '上册'),
    ('六年级', '六下', '下册'),
]

# ===========================
# 数学 考卷真题 - 6种题型
# E1 填空满分攻略, E2 选择秒杀专区, E3 计算零失误, E4 判断火眼金睛, E5 应用题拆解, E6 操作题规范
# ===========================

MATH_UNITS_TEMPLATE = [
    {"unit_id": "E1", "unit_name": "填空满分攻略", "card_type": "填空满分卡", "score_weight": "20-25%"},
    {"unit_id": "E2", "unit_name": "选择秒杀专区", "card_type": "选择秒杀卡", "score_weight": "10-15%"},
    {"unit_id": "E3", "unit_name": "计算零失误", "card_type": "计算零失误卡", "score_weight": "20-25%"},
    {"unit_id": "E4", "unit_name": "判断火眼金睛", "card_type": "判断火眼卡", "score_weight": "10-15%"},
    {"unit_id": "E5", "unit_name": "应用题拆解", "card_type": "应用题拆解卡", "score_weight": "25-30%"},
    {"unit_id": "E6", "unit_name": "操作题规范", "card_type": "操作题规范卡", "score_weight": "5-10%"},
]

# 每个年级的数学核心知识点 (用于生成具体卡片内容)
MATH_GRADE_CONTENT = {
    '一上': {
        'topics': ['10以内加减法', '认识钟表', '比大小', '位置关系'],
        'E1': [
            {'title': '10以内加减填空3大坑', 'question': '5 + （  ）= 9',
             'steps': ['想：9 - 5 = 4', '所以括号填4', '验证：5 + 4 = 9 ✓'],
             'answer': '4', 'tip': '减法是加法的逆运算，逆向思维填空！',
             'wrong': [('填成14（5+9=14）','括号求的是加数，不是和')]},
            {'title': '比大小符号填空不出错', 'question': '7 ○ 5，○里填 >、< 还是 =',
             'steps': ['7和5比，7大', '大数在前用 >', '所以填 >'],
             'answer': '>', 'tip': '大嘴巴朝大数，尖尖朝小数！',
             'wrong': [('填成 <（方向搞反）','大嘴对大数：7>5')]},
        ],
        'E2': [
            {'title': '钟表选择题秒杀法', 'question': '时针指向3，分针指向12，现在是几点？A.12点 B.3点 C.6点',
             'steps': ['分针指12=整点', '时针指3=3点', '选B'],
             'answer': 'B', 'tip': '分针12是整点信号，看时针定几点！',
             'wrong': [('选A（看错指针）','时针短粗，分针长细，别看反')]},
        ],
        'E3': [
            {'title': '10以内加减口算零失误', 'question': '8 - 3 + 4 = ?',
             'steps': ['从左到右算：8 - 3 = 5', '5 + 4 = 9'],
             'answer': '9', 'tip': '混合运算从左往右，不跳步！',
             'wrong': [('3+4=7，8-7=1（先算后面）','没有括号就从左往右')]},
        ],
        'E4': [
            {'title': '判断：0是最小的数', 'question': '0是最小的数。（  ）',
             'steps': ['一年级范围内0是最小的自然数', '这个说法是对的'],
             'answer': '√', 'tip': '0是最小的自然数（一年级范围）',
             'wrong': [('打✗（以为没有比0小的就不算）','0就是最小的自然数')]},
        ],
        'E5': [
            {'title': '看图列式不丢分', 'question': '树上有6只鸟，飞走了2只，还剩几只？',
             'steps': ['原来6只', '飞走=减去2', '6 - 2 = 4只'],
             'answer': '4只', 'tip': '「飞走」「拿走」「吃掉」都是减法信号词！',
             'wrong': [('6+2=8只（用成加法）','飞走是减少，用减法')]},
        ],
        'E6': [
            {'title': '数一数涂一涂不漏格', 'question': '把左起第3个○涂上颜色',
             'steps': ['从左边数: 第1个、第2个、第3个', '只涂第3个', '检查：确实是从左数'],
             'answer': '涂左起第3个', 'tip': '注意"从左"还是"从右"，圈出方向词！',
             'wrong': [('涂了前3个（把"第3个"看成"前3个"）','「第3个」只涂1个，「前3个」涂3个')]},
        ],
    },
    '一下': {
        'topics': ['20以内退位减法', '100以内数的认识', '认识人民币', '找规律'],
        'E1': [
            {'title': '20以内退位减法填空技巧', 'question': '15 -（  ）= 7',
             'steps': ['想：15 - 7 = 8', '所以括号填8', '验证：15 - 8 = 7 ✓'],
             'answer': '8', 'tip': '用被减数减差=减数，反着想！',
             'wrong': [('填22（15+7=22）','不是求和，是求减数')]},
            {'title': '人民币换算填空坑', 'question': '1元3角 =（  ）角',
             'steps': ['1元 = 10角', '10角 + 3角 = 13角'],
             'answer': '13角', 'tip': '1元=10角=100分，先换再加！',
             'wrong': [('填1.3角','要统一单位，1元=10角')]},
        ],
        'E2': [
            {'title': '找规律选择秒杀', 'question': '2, 4, 6, 8, ( ) A.9 B.10 C.12',
             'steps': ['每次+2','8+2=10','选B'],
             'answer': 'B', 'tip': '找相邻两数的差，就是规律！',
             'wrong': [('选A（以为+1）','仔细看间隔都是2')]},
        ],
        'E3': [
            {'title': '两位数加一位数进位', 'question': '28 + 5 = ?',
             'steps': ['个位：8 + 5 = 13，写3进1', '十位：2 + 1 = 3', '答案：33'],
             'answer': '33', 'tip': '个位满10进1到十位！',
             'wrong': [('=213（没进位直接写拼）','个位相加满10要进位')]},
        ],
        'E4': [
            {'title': '判断：最大两位数是99', 'question': '最大的两位数是99。（  ）',
             'steps': ['两位数从10到99', '最大的确实是99'],
             'answer': '√', 'tip': '最小两位数10，最大两位数99！',
             'wrong': [('打✗以为是100','100是三位数')]},
        ],
        'E5': [
            {'title': '比多少应用题', 'question': '小红有15朵花，小明比小红多6朵，小明有几朵？',
             'steps': ['小明比小红多→小明更多→用加法', '15 + 6 = 21朵'],
             'answer': '21朵', 'tip': '「比…多」就加，「比…少」就减！',
             'wrong': [('15-6=9朵（用成减法）','比多用加法')]},
        ],
        'E6': [
            {'title': '画图补全规律', 'question': '○□○□○（ ），画出下一个',
             'steps': ['规律：圆形和方形交替', '○后面是□'],
             'answer': '□', 'tip': '找准AB重复模式，下一个就出来了！',
             'wrong': [('画成○','注意是交替，不是连续')]},
        ],
    },
    '二上': {
        'topics': ['100以内加减法', '乘法口诀1-6', '角的认识', '观察物体'],
        'E1': [
            {'title': '乘法口诀填空3大陷阱', 'question': '（  ）× 6 = 30',
             'steps': ['想口诀：五六三十', '所以括号填5', '验证：5×6=30 ✓'],
             'answer': '5', 'tip': '看到积想口诀，反向推因数！',
             'wrong': [('填36（加法思维30+6）','这是乘法不是加法')]},
            {'title': '角的认识填空易错', 'question': '一个角有（ ）个顶点，（ ）条边',
             'steps': ['角由一个顶点和两条边组成', '1个顶点，2条边'],
             'answer': '1个顶点，2条边', 'tip': '1个尖角+2条射线=1个角！',
             'wrong': [('2个顶点（把端点算2次）','角只有1个顶点')]},
        ],
        'E2': [
            {'title': '乘加乘减选择秒杀', 'question': '3×4+2=? A.10 B.14 C.16',
             'steps': ['先乘后加：3×4=12', '12+2=14', '选B'],
             'answer': 'B', 'tip': '先乘除后加减，没括号按顺序！',
             'wrong': [('4+2=6,3×6=18','先乘后加，不是先加后乘')]},
        ],
        'E3': [
            {'title': '两位数加减笔算不出错', 'question': '48 + 36 = ?',
             'steps': ['个位：8+6=14，写4进1', '十位：4+3+1=8', '答案：84'],
             'answer': '84', 'tip': '竖式对齐，进位不忘加！',
             'wrong': [('=714（没进位）','个位满10进1给十位')]},
        ],
        'E4': [
            {'title': '判断：3+3=3×3', 'question': '3+3和3×3的结果相同。（  ）',
             'steps': ['3+3=6', '3×3=9', '6≠9，判断错'],
             'answer': '✗', 'tip': '加法和乘法结果只有2+2=2×2时相同！',
             'wrong': [('打✓以为都是两个3','加和乘运算不同')]},
        ],
        'E5': [
            {'title': '乘法应用题拆解', 'question': '每行有4棵树，有3行，一共有多少棵？',
             'steps': ['每行4棵，3行→求几个4', '4×3=12棵'],
             'answer': '12棵', 'tip': '几个几=乘法！',
             'wrong': [('4+3=7棵','几行×每行=总数，用乘法')]},
        ],
        'E6': [
            {'title': '画角操作规范', 'question': '画一个直角',
             'steps': ['1.先画一个顶点', '2.从顶点画一条横线', '3.用三角尺对齐画竖线', '4.标上直角符号┐'],
             'answer': '一个标准直角', 'tip': '直角必须标「┐」，不标扣分！',
             'wrong': [('忘记标直角符号','画完直角必须标记')]},
        ],
    },
    '二下': {
        'topics': ['表内除法', '混合运算', '万以内数', '克和千克', '数据收集'],
        'E1': [
            {'title': '除法填空求被除数', 'question': '（  ）÷ 6 = 5',
             'steps': ['被除数 = 商 × 除数', '5 × 6 = 30'],
             'answer': '30', 'tip': '被除数=商×除数+余数！',
             'wrong': [('6-5=1','除法逆运算是乘法')]},
            {'title': '万以内数的组成', 'question': '3205是由（）个千、（）个百、（）个一组成的',
             'steps': ['3205: 千位3,百位2,十位0,个位5','3个千+2个百+0个十+5个一'],
             'answer': '3个千、2个百、5个一', 'tip': '0在十位不用说，但别漏个位！',
             'wrong': [('说成3个千2个百5个十','5在个位不是十位')]},
        ],
        'E2': [
            {'title': '混合运算顺序选择', 'question': '24 ÷ 6 + 2 × 3 = ? A.10 B.7 C.16',
             'steps': ['先算除法和乘法：24÷6=4, 2×3=6','再加：4+6=10','选A'],
             'answer': 'A', 'tip': '先乘除后加减，同级从左到右！',
             'wrong': [('从左到右全部算','要先乘除后加减')]},
        ],
        'E3': [
            {'title': '有余数除法计算', 'question': '23 ÷ 5 = ?',
             'steps': ['5×4=20，5×5=25>23','所以商4余3','23÷5=4...3'],
             'answer': '4...3', 'tip': '余数一定比除数小！',
             'wrong': [('商5余-2','余数不能是负数')]},
        ],
        'E4': [
            {'title': '判断：1千克棉花比1千克铁轻', 'question': '1千克棉花比1千克铁轻。（  ）',
             'steps': ['都是1千克','一样重','判断错'],
             'answer': '✗', 'tip': '比重量看数字，不看材质！',
             'wrong': [('✓以为棉花轻','单位相同就比数字')]},
        ],
        'E5': [
            {'title': '除法应用有余数', 'question': '22人去划船，每船坐5人，至少需要几条船？',
             'steps': ['22÷5=4...2','余下2人还需1条船','4+1=5条船'],
             'answer': '5条船', 'tip': '有余数要多租1辆/条/间，进一法！',
             'wrong': [('4条船（没管余下的人）','有余数要进一')]},
        ],
        'E6': [
            {'title': '画统计图规范', 'question': '根据数据画条形统计图',
             'steps': ['1.写标题','2.标横纵轴','3.统一格子高度','4.涂色对齐不超线'],
             'answer': '规范统计图', 'tip': '标题+坐标轴+数据，三样缺一扣分！',
             'wrong': [('忘写标题','统计图必须有标题')]},
        ],
    },
    '三上': {
        'topics': ['万以内加减法', '多位数乘一位数', '分数初步', '长方形周长', '时分秒'],
        'E1': [
            {'title': '万以内加减竖式填空', 'question': '603 - 278 = （  ）',
             'steps': ['个位：3-8不够，向十位借，但十位是0→向百位借','计算得325'],
             'answer': '325', 'tip': '连续退位：0借旁边→变9再借给个位！',
             'wrong': [('=435（退位错误）','0不够借要往左找')]},
            {'title': '分数大小比较', 'question': '⅓ ○ ⅕ ，○里填 > < =',
             'steps': ['同分子比分母','分母小的分数大','3<5所以⅓>⅕'],
             'answer': '>', 'tip': '分子同看分母：分母小→分数大！',
             'wrong': [('填<（以为3<5就小）','分母越小，每份越大')]},
        ],
        'E2': [
            {'title': '周长公式选择', 'question': '正方形边长5cm，周长？A.10cm B.20cm C.25cm',
             'steps': ['正方形周长=边长×4','5×4=20cm','选B'],
             'answer': 'B', 'tip': '正方形4边等长，周长=边×4！',
             'wrong': [('选C算成面积5×5','周长是4条边之和')]},
        ],
        'E3': [
            {'title': '多位数乘一位数', 'question': '246 × 3 = ?',
             'steps': ['6×3=18写8进1','4×3=12加1=13写3进1','2×3=6加1=7','=738'],
             'answer': '738', 'tip': '从个位起乘，满几十就进几！',
             'wrong': [('=618（漏进位）','每一位乘完别忘加进位')]},
        ],
        'E4': [
            {'title': '判断：四边形都是长方形', 'question': '所有的四边形都是长方形。（  ）',
             'steps': ['四边形包括长方形、正方形、平行四边形等','长方形只是一种','判断错'],
             'answer': '✗', 'tip': '长方形是特殊四边形，不是所有！',
             'wrong': [('✓以为四边形=长方形','还有梯形、平行四边形等')]},
        ],
        'E5': [
            {'title': '周长应用题', 'question': '长方形菜地长12m宽8m，围一圈篱笆需要多少米？',
             'steps': ['围一圈=求周长','(12+8)×2=40米'],
             'answer': '40米', 'tip': '围一圈/绕一周=求周长！',
             'wrong': [('12×8=96求成面积','围一圈是周长不是面积')]},
        ],
        'E6': [
            {'title': '画长方形规范', 'question': '在方格纸上画一个长4cm宽3cm的长方形',
             'steps': ['1.数好4格横线','2.数好3格竖线','3.连接4个顶点','4.标注长和宽'],
             'answer': '标准长方形', 'tip': '标注长和宽的数字+单位！',
             'wrong': [('忘记标注边长','画完要标注数据')]},
        ],
    },
    '三下': None,  # 已存在
    '四上': {
        'topics': ['大数的认识', '三位数乘两位数', '平行与垂直', '角的度量', '条形统计图'],
        'E1': [
            {'title': '大数改写和近似数', 'question': '3860000 =（  ）万，≈（  ）万',
             'steps': ['精确值：3860000÷10000=386万','近似值：看千位，386万'],
             'answer': '386万，386万', 'tip': '改写用"="，近似用"≈"！',
             'wrong': [('用≈写精确值','精确改写用等号')]},
            {'title': '角的度数填空', 'question': '一个平角=（ ）度，一个周角=（ ）度',
             'steps': ['平角=180°','周角=360°'],
             'answer': '180, 360', 'tip': '直角90→平角180→周角360，翻倍记！',
             'wrong': [('平角=90°','直角才是90°')]},
        ],
        'E2': [
            {'title': '平行垂直选择题', 'question': '以下哪组线是互相垂直的？A.交叉成60° B.交叉成90° C.不相交',
             'steps': ['垂直=交叉成90°','选B'],
             'answer': 'B', 'tip': '垂直=90°，其他角度只是相交！',
             'wrong': [('选A以为只要交叉就垂直','必须90度才叫垂直')]},
        ],
        'E3': [
            {'title': '三位数乘两位数竖式', 'question': '312 × 26 = ?',
             'steps': ['312×6=1872','312×20=6240','1872+6240=8112'],
             'answer': '8112', 'tip': '第二层乘十位数字，末尾对十位！',
             'wrong': [('第二层没左移一位','乘十位时末尾要对齐十位')]},
        ],
        'E4': [
            {'title': '判断：两条直线不相交就平行', 'question': '不相交的两条直线一定互相平行。（  ）',
             'steps': ['在同一平面内才成立','不在同一平面可能异面','但小学范围内默认同一平面'],
             'answer': '√（小学范围）', 'tip': '小学阶段：不相交=平行（同一平面）！',
             'wrong': [('✗考虑立体情况','小学默认同一平面')]},
        ],
        'E5': [
            {'title': '统计图应用题', 'question': '根据统计图，食堂周一午餐用了180千克米，周二用了210千克，一周五天共用了多少？',
             'steps': ['读图获取5天数据','逐天相加','写完整答语'],
             'answer': '看图计算', 'tip': '看清纵轴单位和每格代表的数量！',
             'wrong': [('只看了2天就算','要看完5天才能求总数')]},
        ],
        'E6': [
            {'title': '量角器操作规范', 'question': '用量角器量一个角的度数',
             'steps': ['1.中心点对齐顶点','2.零刻度线对齐一条边','3.另一条边读度数','4.判断用内圈还是外圈'],
             'answer': '准确度数', 'tip': '角小于90°用小数，大于90°用大数！',
             'wrong': [('内外圈读反','先判断是锐角还是钝角再读数')]},
        ],
    },
    '四下': {
        'topics': ['四则运算', '运算定律', '小数意义', '三角形', '小数加减'],
        'E1': [
            {'title': '小数填空易混点', 'question': '0.3元 =（  ）角 =（  ）分',
             'steps': ['0.3元 = 3角', '3角 = 30分'],
             'answer': '3角，30分', 'tip': '元→角×10，角→分×10！',
             'wrong': [('0.3元=0.3角','要进行单位换算')]},
            {'title': '三角形三边关系', 'question': '三角形两边分别是3cm和5cm，第三边可能是（  ）cm',
             'steps': ['两边之差<第三边<两边之和','5-3<x<5+3','2<x<8'],
             'answer': '3到7之间的整数', 'tip': '两边之差<第三边<两边之和！',
             'wrong': [('填2或8（取等号）','不能取等号，要严格大于')]},
        ],
        'E2': [
            {'title': '运算定律选择', 'question': '25×12=25×4×3，用的是？A.交换律 B.结合律 C.分配律',
             'steps': ['12拆成4×3','25×(4×3)=(25×4)×3→结合律','选B'],
             'answer': 'B', 'tip': '拆因数是结合律，拆加数是分配律！',
             'wrong': [('选C分配律','分配律是a×(b+c)形式')]},
        ],
        'E3': [
            {'title': '小数加减计算', 'question': '12.5 - 3.68 = ?',
             'steps': ['小数点对齐：12.50-3.68','个位：0-8不够借1→10-8=2','十分位：4-6不够借→14-6=8','整数位：11-3=8','=8.82'],
             'answer': '8.82', 'tip': '小数点对齐，位数不够补0！',
             'wrong': [('=9.82（借位错误）','退位要连续借')]},
        ],
        'E4': [
            {'title': '判断：三角形内角和', 'question': '所有三角形的内角和都是180°。（  ）',
             'steps': ['这是定理','任何三角形内角和=180°'],
             'answer': '√', 'tip': '三角形内角和永远180°，不分大小！',
             'wrong': [('✗以为只有特殊三角形','所有三角形都是')]},
        ],
        'E5': [
            {'title': '简便运算应用', 'question': '超市购物：苹果25.8元，香蕉14.2元，牛奶10元。共多少元？',
             'steps': ['25.8+14.2=40（凑整）','40+10=50元'],
             'answer': '50元', 'tip': '先凑整再加，简便快速！',
             'wrong': [('逐个相加算错','凑整数计算更不容易出错')]},
        ],
        'E6': [
            {'title': '画三角形的高', 'question': '画出三角形BC边上的高',
             'steps': ['1.找对应顶点A','2.用三角尺从A向BC画垂线','3.标垂足和直角符号','4.标注"h"'],
             'answer': '规范高', 'tip': '高一定垂直于底边，标垂直符号！',
             'wrong': [('没从顶点画','高是从对角顶点到底边的垂线段')]},
        ],
    },
    '五上': {
        'topics': ['小数乘法', '小数除法', '简易方程', '多边形面积', '植树问题'],
        'E1': [
            {'title': '方程填空解法', 'question': '2x + 3 = 11，x = （  ）',
             'steps': ['2x = 11-3 = 8', 'x = 8÷2 = 4'],
             'answer': '4', 'tip': '移项变号：+变-，×变÷！',
             'wrong': [('x=11-3=8','要先移3再除以2')]},
            {'title': '面积公式填空', 'question': '平行四边形面积=（  ），梯形面积=（  ）',
             'steps': ['平行四边形：底×高', '梯形：(上底+下底)×高÷2'],
             'answer': '底×高，(上底+下底)×高÷2', 'tip': '梯形别忘÷2！',
             'wrong': [('梯形忘记÷2','梯形面积公式最后要除以2')]},
        ],
        'E2': [
            {'title': '小数除法选择', 'question': '7.2÷0.8=? A.9 B.0.9 C.90',
             'steps': ['同时×10：72÷8=9','选A'],
             'answer': 'A', 'tip': '除数是小数→同时扩大成整数！',
             'wrong': [('没移小数点，算成0.9','除数和被除数同时乘10')]},
        ],
        'E3': [
            {'title': '小数乘法小数点位置', 'question': '2.5 × 0.3 = ?',
             'steps': ['25×3=75','两个因数共2位小数','=0.75'],
             'answer': '0.75', 'tip': '先整数算，再数小数位！',
             'wrong': [('=7.5（少数一位小数）','2.5有1位+0.3有1位=2位小数')]},
        ],
        'E4': [
            {'title': '判断：面积相等周长也相等', 'question': '两个面积相等的长方形，周长一定相等。（  ）',
             'steps': ['面积24：可以是6×4(周长20)或8×3(周长22)', '面积同但周长不同'],
             'answer': '✗', 'tip': '面积相等≠周长相等！',
             'wrong': [('✓以为面积决定周长','同面积形状不同周长不同')]},
        ],
        'E5': [
            {'title': '方程解应用题', 'question': '小明买了3本笔记本和1支钢笔共31元，钢笔16元，每本笔记本多少元？',
             'steps': ['设笔记本x元','3x+16=31','3x=15','x=5'],
             'answer': '5元', 'tip': '设未知数→列方程→解方程→验证！',
             'wrong': [('31-16=15就是答案','15是3本的总价，还要÷3')]},
        ],
        'E6': [
            {'title': '画平行四边形的高', 'question': '画出平行四边形的高并计算面积',
             'steps': ['1.选定一条底边','2.从对边上的点向底边画垂线','3.标注高和直角符号','4.面积=底×高'],
             'answer': '底×高', 'tip': '高必须垂直于底边！',
             'wrong': [('画斜线当高','高一定要垂直')]},
        ],
    },
    '五下': {
        'topics': ['因数与倍数', '长方体正方体', '分数加减', '折线统计图', '旋转平移'],
        'E1': [
            {'title': '因数倍数填空', 'question': '18的因数有（  ），18是（  ）的倍数',
             'steps': ['18=1×18=2×9=3×6','因数：1,2,3,6,9,18','18是1,2,3,6,9,18的倍数'],
             'answer': '1,2,3,6,9,18', 'tip': '找因数：从1开始配对找，到√n为止！',
             'wrong': [('漏了1或18本身','1和本身都是因数')]},
            {'title': '长方体表面积', 'question': '长5cm宽3cm高2cm，表面积=（  ）cm²',
             'steps': ['(5×3+5×2+3×2)×2','=(15+10+6)×2','=62cm²'],
             'answer': '62', 'tip': '三对面×2，别只算三面！',
             'wrong': [('=31只算了一半','表面积要乘2')]},
        ],
        'E2': [
            {'title': '质数合数选择', 'question': '以下哪个是质数？A.9 B.15 C.17 D.21',
             'steps': ['9=3×3,15=3×5,21=3×7 都是合数','17只有1和17两个因数→质数'],
             'answer': 'C', 'tip': '质数只有1和自身两个因数！',
             'wrong': [('选奇数就行','9和15也是奇数但不是质数')]},
        ],
        'E3': [
            {'title': '异分母分数加减', 'question': '⅓ + ¼ = ?',
             'steps': ['通分：找公分母12','⅓=4/12, ¼=3/12','4/12+3/12=7/12'],
             'answer': '7/12', 'tip': '先通分→再加减→最后约分！',
             'wrong': [('分子加分子1+1=2,分母加分母3+4=7','不能直接加，要先通分')]},
        ],
        'E4': [
            {'title': '判断：长方体6个面都是长方形', 'question': '长方体的6个面一定都是长方形。（  ）',
             'steps': ['如果有两个面是正方形，其余是长方形','正方形也是特殊长方形→对'],
             'answer': '√', 'tip': '正方形是特殊长方形！',
             'wrong': [('✗以为有的面是正方形不算','正方形是特殊长方形')]},
        ],
        'E5': [
            {'title': '体积应用题', 'question': '长方体水箱，从里面量长40cm宽30cm，倒入水后水深25cm，水的体积？',
             'steps': ['V=长×宽×高','=40×30×25','=30000cm³=30升'],
             'answer': '30000cm³', 'tip': '水的体积=底面积×水深！',
             'wrong': [('用外部尺寸','题目说从里面量')]},
        ],
        'E6': [
            {'title': '画折线统计图规范', 'question': '根据数据画折线统计图',
             'steps': ['1.标好纵横轴和标题','2.描点要准确','3.用直尺连线','4.标注每个点的数据'],
             'answer': '规范折线统计图', 'tip': '先描点再连线，每个点标数值！',
             'wrong': [('先连线再标点','要先定点后连线')]},
        ],
    },
    '六上': {
        'topics': ['分数乘法', '分数除法', '比', '圆', '百分数'],
        'E1': [
            {'title': '分数除法填空', 'question': '⅔ ÷ ¼ = （  ）',
             'steps': ['除以分数=乘它的倒数','⅔ × 4 = 8/3 = 2⅔'],
             'answer': '8/3(即2⅔)', 'tip': '除以分数，翻转相乘！',
             'wrong': [('分子÷分子=2,分母÷分母=12','要翻转后相乘')]},
            {'title': '圆的周长面积', 'question': '半径3cm的圆，周长=（  ）cm，面积=（  ）cm²',
             'steps': ['周长=2πr=2×3.14×3=18.84','面积=πr²=3.14×9=28.26'],
             'answer': '18.84, 28.26', 'tip': '周长2πr，面积πr²，r和d别搞混！',
             'wrong': [('用直径算半径的公式','注意是半径还是直径')]},
        ],
        'E2': [
            {'title': '比的化简选择', 'question': '12:8的最简比？A.3:2 B.6:4 C.1.5:1',
             'steps': ['12和8的最大公因数=4','12÷4:8÷4=3:2'],
             'answer': 'A', 'tip': '最简整数比：除以最大公因数！',
             'wrong': [('选C小数比','最简比必须是整数')]},
        ],
        'E3': [
            {'title': '分数乘法计算', 'question': '⅘ × 15 = ?',
             'steps': ['⅘ × 15 = 4×15÷5','先约分：15÷5=3','4×3=12'],
             'answer': '12', 'tip': '先约分再乘，计算更简单！',
             'wrong': [('4×15=60,60÷5=12虽对但麻烦','先约分更简便')]},
        ],
        'E4': [
            {'title': '判断：半径扩大2倍面积扩大2倍', 'question': '圆的半径扩大到原来的2倍，面积也扩大到2倍。（  ）',
             'steps': ['面积=πr²','r→2r, 面积=π(2r)²=4πr²','面积扩大4倍，不是2倍'],
             'answer': '✗', 'tip': '半径翻n倍，面积翻n²倍！',
             'wrong': [('✓以为同比例','面积与半径是平方关系')]},
        ],
        'E5': [
            {'title': '百分数应用题', 'question': '原价200元打八折，现价多少？',
             'steps': ['八折=80%','200×80%=200×0.8=160元'],
             'answer': '160元', 'tip': '几折=百分之几十：八折=80%！',
             'wrong': [('200-8=192','打折是乘以折扣率')]},
        ],
        'E6': [
            {'title': '画圆操作规范', 'question': '画一个半径为2cm的圆',
             'steps': ['1.圆规两脚张开2cm','2.固定针尖不动','3.旋转一周画完整','4.标注半径和圆心'],
             'answer': '标准圆', 'tip': '圆规不能晃动，标上r和O！',
             'wrong': [('忘记标圆心和半径','画完要标注')]},
        ],
    },
    '六下': {
        'topics': ['负数', '百分数(二)', '圆柱圆锥', '比例', '数学总复习'],
        'E1': [
            {'title': '负数填空', 'question': '零下3℃记作（  ）℃, 0℃比-5℃高（  ）℃',
             'steps': ['零下3℃= -3℃','0-(-5)=5℃'],
             'answer': '-3, 5', 'tip': '零下=负号，温差用减法！',
             'wrong': [('0比-5高-5℃','0-(-5)=0+5=5')]},
            {'title': '圆柱体积', 'question': '底面半径2cm，高5cm，体积=（  ）cm³',
             'steps': ['底面积=πr²=3.14×4=12.56','V=12.56×5=62.8'],
             'answer': '62.8', 'tip': '圆柱体积=底面积×高，圆锥再÷3！',
             'wrong': [('忘记求底面积','先算底面积再乘高')]},
        ],
        'E2': [
            {'title': '比例选择题', 'question': '2:3=8:x，x=? A.12 B.16 C.6',
             'steps': ['内项积=外项积','3×8=2×x','x=24÷2=12'],
             'answer': 'A', 'tip': '交叉相乘解比例！',
             'wrong': [('2×8=16','是内项积=外项积')]},
        ],
        'E3': [
            {'title': '圆柱表面积', 'question': '底面半径3cm高10cm，表面积？',
             'steps': ['底面积=3.14×9=28.26','侧面积=2πr×h=2×3.14×3×10=188.4','表面积=28.26×2+188.4=244.92'],
             'answer': '244.92cm²', 'tip': '表面积=2个底面+侧面积！',
             'wrong': [('只算一个底面','要两个底面')]},
        ],
        'E4': [
            {'title': '判断：圆锥体积是圆柱的⅓', 'question': '圆锥的体积是圆柱体积的⅓。（  ）',
             'steps': ['前提：等底等高','题目没说等底等高','判断错'],
             'answer': '✗', 'tip': '必须等底等高才是⅓关系！',
             'wrong': [('✓忘记前提条件','要强调等底等高')]},
        ],
        'E5': [
            {'title': '比例尺应用', 'question': '地图上5cm代表实际100km，比例尺是多少？图上8cm代表多远？',
             'steps': ['比例尺=5:10000000=1:2000000','8×2000000=16000000cm=160km'],
             'answer': '1:2000000，160km', 'tip': '比例尺=图上÷实际，注意统一单位！',
             'wrong': [('5:100忘记换单位','要统一成cm')]},
        ],
        'E6': [
            {'title': '画比例尺图形', 'question': '按1:50000画一条实际长度2km的路',
             'steps': ['2km=200000cm','200000÷50000=4cm','画4cm线段并标注'],
             'answer': '4cm线段', 'tip': '先算图上距离再画！',
             'wrong': [('直接画2cm','要用比例尺换算')]},
        ],
    },
}

# ===========================
# 英语 考卷真题 - 6种题型
# E1 听力得分, E2 选择秒杀, E3 拼写零错, E4 填空必会, E5 匹配速解/阅读通关, E6 写作模板
# ===========================

ENGLISH_UNITS_TEMPLATE = [
    {"unit_id": "E1", "unit_name": "听力得分专区", "card_type": "听力得分卡", "score_weight": "30-40%"},
    {"unit_id": "E2", "unit_name": "选择秒杀专区", "card_type": "选择秒杀卡", "score_weight": "10-15%"},
    {"unit_id": "E3", "unit_name": "拼写零错攻略", "card_type": "拼写零错卡", "score_weight": "10-15%"},
    {"unit_id": "E4", "unit_name": "填空必会宝典", "card_type": "填空必会卡", "score_weight": "10-15%"},
    {"unit_id": "E5", "unit_name": "阅读通关秘籍", "card_type": "阅读通关卡", "score_weight": "15-20%"},
    {"unit_id": "E6", "unit_name": "写作模板大全", "card_type": "写作模板卡", "score_weight": "10-15%"},
]

ENGLISH_GRADE_CONTENT = {
    '三上': {
        'topics': ['Letters Aa-Zz', 'Greetings', 'Colours', 'Body parts', 'Animals', 'Food'],
        'E1': [
            {'title': '字母听辨3大陷阱', 'question': 'Listen: Which letter? You hear /biː/',
             'steps': ['b发/biː/, d发/diː/, p发/piː/','听到/biː/→选B不是D也不是P','易混组: b/d/p, m/n, g/j'],
             'answer': 'B', 'tip': '字母易混组：b/d/p，m/n，g/j 多听多辨！',
             'wrong': [('听成D','b的/b/音嘴唇先闭再打开')]},
        ],
        'E2': [
            {'title': 'Greetings选择秒杀', 'question': '— Good morning! — ___  A.Good evening! B.Good morning! C.Bye!',
             'steps': ['Good morning回应Good morning','相同时段相同问候'],
             'answer': 'B', 'tip': '同一时段问候要对称回答！',
             'wrong': [('选A时段不对','morning对morning')]},
        ],
        'E3': [
            {'title': '26字母大小写配对', 'question': '写出下列字母的小写: B D G Q R',
             'steps': ['B→b, D→d, G→g, Q→q, R→r','注意b/d镜像，q/p镜像'],
             'answer': 'b, d, g, q, r', 'tip': 'b朝右d朝左，q尾朝左p尾朝右！',
             'wrong': [('b和d写反','b肚子朝右，d肚子朝左')]},
        ],
        'E4': [
            {'title': 'Colour词填空', 'question': 'The banana is ___. (yellow/green/red)',
             'steps': ['banana=香蕉','香蕉常见颜色=黄色','填yellow'],
             'answer': 'yellow', 'tip': '水果颜色搭配要记牢！',
             'wrong': [('填green','生活常识：香蕉是黄色')]},
        ],
        'E5': [
            {'title': '图文匹配阅读', 'question': 'Read: "I have a big red bag." Which picture?',
             'steps': ['关键词: big, red, bag','找同时满足3个条件的图'],
             'answer': '大红色书包图', 'tip': '圈出所有形容词，逐个匹配！',
             'wrong': [('只看bag没看颜色和大小','要同时匹配所有描述词')]},
        ],
        'E6': [
            {'title': '自我介绍模板', 'question': 'Write about yourself',
             'steps': ['Hello! My name is ___.',  "I'm ___.", 'I like ___.', 'Nice to meet you!'],
             'answer': '4句模板', 'tip': '开头Hello+名字+特点+结尾，四句搞定！',
             'wrong': [('没有开头问候语','写作要有开头和结尾')]},
        ],
    },
    '三下': None,  # 已存在
    '四上': {
        'topics': ['Classroom', 'Schoolbag', 'Friends', 'Home', 'Food & Drinks', 'Family'],
        'E1': [
            {'title': '教室物品听力辨别', 'question': 'Listen: "Put your pencil on the desk."',
             'steps': ['关键词: pencil, on, desk','动作：把铅笔放桌上','图片匹配铅笔在桌上'],
             'answer': '铅笔在桌上', 'tip': 'on=在上面, in=在里面, under=在下面！',
             'wrong': [('in和on分不清','on在表面，in在内部')]},
        ],
        'E2': [
            {'title': 'How many选择', 'question': 'How many books do you have? A.I have book. B.I have five. C.Yes, I do.',
             'steps': ['How many问数量','回答要有数字','选B'],
             'answer': 'B', 'tip': 'How many问数量→答案必须有数字！',
             'wrong': [('选C，以为是yes/no问题','How many是特殊疑问句')]},
        ],
        'E3': [
            {'title': 'Classroom物品拼写', 'question': '补全单词: w__nd__w (窗户), d__sk (桌子)',
             'steps': ['window: w-i-n-d-o-w','desk: d-e-s-k'],
             'answer': 'window, desk', 'tip': 'window注意ow结尾，不是ou！',
             'wrong': [('windou','window的ow不是ou')]},
        ],
        'E4': [
            {'title': 'There be句型填空', 'question': 'There ___ a book on the desk. There ___ three pens.',
             'steps': ['a book单数→is','three pens复数→are'],
             'answer': 'is, are', 'tip': 'There be就近原则：看最近的名词单复数！',
             'wrong': [('都填is','复数名词用are')]},
        ],
        'E5': [
            {'title': '家庭成员阅读理解', 'question': 'Read: "This is my family. My father is tall. My mother is a teacher..."',
             'steps': ['读问题→找关键词→回原文定位','Who is a teacher? → My mother'],
             'answer': '根据文段回答', 'tip': '先看题→再读文→定位关键句！',
             'wrong': [('不看题直接读全文','先看题目更高效')]},
        ],
        'E6': [
            {'title': '描述房间模板', 'question': 'Describe your room',
             'steps': ['This is my room.', 'There is a ___ in my room.', 'There are ___ on the ___.', 'I like my room!'],
             'answer': 'There be句型描述', 'tip': 'There is+单数, There are+复数！',
             'wrong': [('全用There is','有复数名词要用are')]},
        ],
    },
    '四下': {
        'topics': ['School', 'Weather', 'Shopping', 'Farm', 'Clothes', 'Daily routine'],
        'E1': [
            {'title': '天气词汇听力', 'question': 'Listen: "It\'s rainy today. Take your umbrella."',
             'steps': ['rainy=下雨的','umbrella=雨伞','关联：rainy→need umbrella'],
             'answer': 'rainy', 'tip': 'sunny/cloudy/rainy/windy/snowy 5种天气必会！',
             'wrong': [('rainy和windy分不清','rainy有rain(雨)的词根')]},
        ],
        'E2': [
            {'title': 'What time选择', 'question': "It's time ___ lunch. A.for B.to C.at",
             'steps': ["It's time for + 名词","It's time to + 动词", 'lunch是名词→选A'],
             'answer': 'A', 'tip': "time for+名词, time to+动词！",
             'wrong': [('选B','to后面跟动词，for后面跟名词')]},
        ],
        'E3': [
            {'title': '天气单词拼写', 'question': 'w__rm(温暖), c__ld(寒冷), c__ol(凉爽)',
             'steps': ['warm, cold, cool','注意warm是ar不是or'],
             'answer': 'warm, cold, cool', 'tip': 'warm的ar发/ɔː/，不是or！',
             'wrong': [('worm(虫子)','warm=温暖，worm=虫子')]},
        ],
        'E4': [
            {'title': 'How much购物填空', 'question': 'How much ___ this dress? It ___ 50 yuan.',
             'steps': ['this dress单数→is','回答也用is'],
             'answer': 'is, is', 'tip': 'How much is+单数, How much are+复数！',
             'wrong': [('How much are this dress','this单数用is')]},
        ],
        'E5': [
            {'title': '购物对话阅读', 'question': 'Read the dialogue about shopping...',
             'steps': ['圈出价格数字','找出买了什么','计算总价'],
             'answer': '根据对话回答', 'tip': '购物阅读重点：物品+价格+数量！',
             'wrong': [('忽略单位（yuan/dollar）','注意货币单位')]},
        ],
        'E6': [
            {'title': '天气日记模板', 'question': 'Write about the weather today',
             'steps': ['Today is ___(day).', 'The weather is ___.', 'I wear my ___.', 'I can ___.'],
             'answer': '天气日记', 'tip': '天气→穿着→活动，三层递进！',
             'wrong': [('没有日期','日记要先写日期和天气')]},
        ],
    },
    '五上': {
        'topics': ['Teachers', 'Week', 'Food', 'Room', 'Nature park', 'Daily life'],
        'E1': [
            {'title': '人物描述听力', 'question': 'Listen: "My English teacher is tall and thin. She has long hair."',
             'steps': ['关键词: tall, thin, long hair, she','匹配：高瘦+长发+女性'],
             'answer': '匹配对应人物图', 'tip': '人物描述听力抓：高矮胖瘦+发型+性别！',
             'wrong': [('只听到tall就选','要综合所有特征')]},
        ],
        'E2': [
            {'title': 'What do you have选择', 'question': 'What do you have ___ Mondays? A.in B.on C.at',
             'steps': ['星期几前用on','on Mondays'],
             'answer': 'B', 'tip': 'on+星期, in+月份/季节, at+时间点！',
             'wrong': [('选A in','星期前固定搭配on')]},
        ],
        'E3': [
            {'title': '食物单词拼写', 'question': 'h__mburger, s__ndwich, sal__d',
             'steps': ['hamburger, sandwich, salad','hamburger注意ham开头'],
             'answer': 'hamburger, sandwich, salad', 'tip': 'hamburger=ham+burger，分段记！',
             'wrong': [('hanburger','是ham不是han')]},
        ],
        'E4': [
            {'title': 'There be否定句填空', 'question': 'There ___ (not) any fish in the river.',
             'steps': ['There be否定：be后加not','are not = aren\'t','There aren\'t any fish'],
             'answer': "aren't", 'tip': 'any用在否定句和疑问句中！',
             'wrong': [("isn't any fish",'fish可数复数用are')]},
        ],
        'E5': [
            {'title': '菜单阅读理解', 'question': 'Read the school menu and answer questions',
             'steps': ['读菜单标题和各项','找到问题中的关键词','在菜单中定位答案'],
             'answer': '根据菜单回答', 'tip': '菜单阅读：先看纵列分类，再横向找信息！',
             'wrong': [('看错行列','用尺子对齐避免看错行')]},
        ],
        'E6': [
            {'title': '描述老师模板', 'question': 'Describe your favourite teacher',
             'steps': ['My favourite teacher is ___.', 'He/She is ___.(外貌)', 'He/She is ___.(性格)', 'I like him/her!'],
             'answer': '人物描述模板', 'tip': '外貌+性格+原因=完整人物描述！',
             'wrong': [('只写外貌','要加上性格和喜欢的原因')]},
        ],
    },
    '五下': {
        'topics': ['Seasons', 'School life', 'Birthday', 'Shopping', 'Animals', 'Stories'],
        'E1': [
            {'title': '季节与月份听力', 'question': 'Listen: "My birthday is in January. I like winter."',
             'steps': ['January=一月→冬天','birthday in January→冬天出生'],
             'answer': '冬天/January', 'tip': '12月份对应4季节：3-5春，6-8夏，9-11秋，12-2冬！',
             'wrong': [('January=June分不清','Jan开头的是一月，June是六月')]},
        ],
        'E2': [
            {'title': '现在进行时选择', 'question': 'Look! The rabbits ___. A.jump B.is jumping C.are jumping',
             'steps': ['rabbits复数→are','正在进行→be+doing','are jumping'],
             'answer': 'C', 'tip': 'Look/Listen信号词→用现在进行时！',
             'wrong': [('选B单数is','rabbits是复数用are')]},
        ],
        'E3': [
            {'title': '月份缩写拼写', 'question': '写出缩写: January___ February___ March___',
             'steps': ['Jan. Feb. Mar.','月份前三个字母+点'],
             'answer': 'Jan. Feb. Mar.', 'tip': '月份缩写=前三字母+点，May/June/July不缩写！',
             'wrong': [('Jau','January=J-a-n')]},
        ],
        'E4': [
            {'title': 'Whose填空', 'question': '___ book is this? It\'s ___(I).',
             'steps': ['问谁的→Whose','It\'s mine(名词性物主代词)'],
             'answer': 'Whose, mine', 'tip': 'Whose问归属，回答my→mine, your→yours！',
             'wrong': [('用Who','Who问人，Whose问物品归属')]},
        ],
        'E5': [
            {'title': '生日邀请函阅读', 'question': 'Read the birthday invitation and answer',
             'steps': ['找时间When','找地点Where','找活动What'],
             'answer': '根据邀请函回答', 'tip': '邀请函三要素：时间+地点+活动！',
             'wrong': [('漏看RSVP信息','RSVP=请回复')]},
        ],
        'E6': [
            {'title': '季节作文模板', 'question': 'Write about your favourite season',
             'steps': ['My favourite season is ___.', 'Because the weather is ___.', 'I can ___.', 'I love ___!'],
             'answer': '季节描述', 'tip': '季节+天气+活动=满分三段式！',
             'wrong': [('没说原因','favourite要给原因Because...')]},
        ],
    },
    '六上': {
        'topics': ['Transport', 'Directions', 'Hobbies', 'Jobs', 'Feelings', 'Nature'],
        'E1': [
            {'title': '交通方式听力辨别', 'question': 'Listen: "I usually go to school by bus."',
             'steps': ['by bus=坐公交','usually=通常','匹配公交图片'],
             'answer': 'by bus', 'tip': 'by+交通工具：bus/bike/subway/plane！',
             'wrong': [('bus和bike听混','bus=/bʌs/, bike=/baɪk/')]},
        ],
        'E2': [
            {'title': '问路选择题', 'question': 'Excuse me, ___ is the hospital? A.What B.Where C.How',
             'steps': ['问地点位置→Where','Where is the hospital?'],
             'answer': 'B', 'tip': 'Where问地点, How问方式, What问事物！',
             'wrong': [('选C How','How问方式不问地点')]},
        ],
        'E3': [
            {'title': '职业单词拼写', 'question': 'sc__entist, p__l__t, f__sh__rman',
             'steps': ['scientist=sci-en-tist','pilot=pi-lot','fisherman=fisher-man'],
             'answer': 'scientist, pilot, fisherman', 'tip': 'scientist注意sc开头+ist结尾！',
             'wrong': [('scentist漏i','sci-en-tist')]},
        ],
        'E4': [
            {'title': '一般将来时填空', 'question': 'I ___ (go) to Beijing next week.',
             'steps': ['next week将来时间标志','am going to go / will go'],
             'answer': 'am going to go', 'tip': 'next/tomorrow/tonight→用将来时！',
             'wrong': [('go（用原形）','有将来时间标志要用将来时')]},
        ],
        'E5': [
            {'title': '地图指路阅读', 'question': 'Read the map directions and find the place',
             'steps': ['turn left=左转','turn right=右转','go straight=直走','在地图上跟着指令走'],
             'answer': '跟着指令找到目的地', 'tip': '手指跟着指令在地图上走！',
             'wrong': [('left和right搞反','left=左（L形），right=右')]},
        ],
        'E6': [
            {'title': '我的周末计划模板', 'question': 'Write about your weekend plan',
             'steps': ['This weekend, I am going to ___.', 'In the morning, I will ___.', 'In the afternoon, I will ___.', "It will be a ___ day!"],
             'answer': '周末计划', 'tip': '将来时+时间顺序=周末计划满分作文！',
             'wrong': [('用过去时','计划要用将来时')]},
        ],
    },
    '六下': {
        'topics': ['Changes', 'Last weekend', 'Holiday', 'Good memories', 'Stories', 'Graduation'],
        'E1': [
            {'title': '过去时态听力', 'question': 'Listen: "Last weekend, I went to the park and played football."',
             'steps': ['关键词: Last weekend=上周末','went=go的过去式','played=play的过去式'],
             'answer': '上周末去公园踢球', 'tip': 'last/yesterday/ago=过去时间信号！',
             'wrong': [('没听出went是过去式','went=go的过去式')]},
        ],
        'E2': [
            {'title': '一般过去时选择', 'question': 'I ___ a film last night. A.see B.saw C.seeing',
             'steps': ['last night=过去时间','see的过去式=saw','选B'],
             'answer': 'B', 'tip': 'last night/yesterday/ago → 过去式！',
             'wrong': [('选A原形','有过去时间标志用过去式')]},
        ],
        'E3': [
            {'title': '不规则动词过去式', 'question': 'go→___ eat→___ see→___ have→___',
             'steps': ['go→went, eat→ate','see→saw, have→had'],
             'answer': 'went, ate, saw, had', 'tip': '不规则动词要背熟，没有规律就死记！',
             'wrong': [('goed','go是不规则变化')]},
        ],
        'E4': [
            {'title': '比较级填空', 'question': 'Tom is ___(tall) than Sam. Lucy is the ___(thin) girl.',
             'steps': ['than前用比较级：taller','the后最高级：thinnest'],
             'answer': 'taller, thinnest', 'tip': 'than+比较级，the+最高级！',
             'wrong': [('tall than','than前面要加er')]},
        ],
        'E5': [
            {'title': '日记阅读理解', 'question': 'Read the diary about last holiday',
             'steps': ['找时间标志(last/ago)','确认是过去时','按who/when/where/what回答'],
             'answer': '根据日记回答', 'tip': '日记阅读抓4W：谁/何时/何地/做什么！',
             'wrong': [('时态答错','日记的问答也要用过去时')]},
        ],
        'E6': [
            {'title': '毕业感言模板', 'question': 'Write about your primary school memories',
             'steps': ['I remember ___(过去式).', 'My best friend is ___.', 'I will miss ___.', 'I hope to ___(将来).'],
             'answer': '毕业感言', 'tip': '回忆用过去式，展望用将来时！',
             'wrong': [('全篇用一种时态','要过去+将来时态结合')]},
        ],
    },
}

# ===========================
# 语文 考卷真题 - 6种题型
# E1 拼音基础攻略, E2 字词选择秒杀, E3 句式变换, E4 阅读理解, E5 古诗文默写, E6 作文模板
# ===========================

CHINESE_UNITS_TEMPLATE = [
    {"unit_id": "E1", "unit_name": "拼音字词基础", "card_type": "拼写默写卡", "score_weight": "20-25%"},
    {"unit_id": "E2", "unit_name": "选择判断秒杀", "card_type": "选择秒杀卡", "score_weight": "10-15%"},
    {"unit_id": "E3", "unit_name": "句式变换宝典", "card_type": "句式变换卡", "score_weight": "10-15%"},
    {"unit_id": "E4", "unit_name": "阅读理解通关", "card_type": "阅读理解卡", "score_weight": "20-25%"},
    {"unit_id": "E5", "unit_name": "古诗文填空", "card_type": "古诗默写卡", "score_weight": "10-15%"},
    {"unit_id": "E6", "unit_name": "作文满分攻略", "card_type": "作文模板卡", "score_weight": "25-30%"},
]

CHINESE_GRADE_CONTENT = {
    '一上': {
        'topics': ['声母韵母', '认字写字', '课文朗读', '简单句子'],
        'E1': [
            {'title': '声母韵母分不清', 'question': '区分: b—d, p—q, ie—ei',
             'steps': ['b右半圆(6)，d左半圆(反6)','p朝上(棍上圆)，q朝下(棍下圆)','ie衣+鹅，ei鹅+衣(谁在前读谁)'],
             'answer': '形状+口诀区分', 'tip': 'b和d看肚子方向：b朝右d朝左！',
             'wrong': [('b和d写反','b肚子朝右(像6)')]},
            {'title': '整体认读音节', 'question': '哪些是整体认读音节？zi ci si zhi chi shi ri yi wu yu',
             'steps': ['zi ci si, zhi chi shi ri','yi wu yu, ye yue yuan','yin yun ying 共16个'],
             'answer': '16个整体认读音节', 'tip': '整体认读不拼读，直接读出来！',
             'wrong': [('把zi拆成z-i拼读','整体认读不能拆')]},
        ],
        'E2': [
            {'title': '同音字选择', 'question': '选字填空：做（ ）业 A.坐 B.作 C.做',
             'steps': ['做作业的"做"→做','坐=sit, 作=create, 做=do'],
             'answer': 'C', 'tip': '做+事情，作+品/文/业！',
             'wrong': [('选B作','做作业的做是C')]},
        ],
        'E3': [
            {'title': '连词成句', 'question': '排列：我 爸爸 爱 的',
             'steps': ['找主语：我','找动词：爱','排列：我爱我的爸爸/我的爸爸爱我'],
             'answer': '我爱我的爸爸。', 'tip': '谁+做什么+什么=完整句子！',
             'wrong': [('忘加句号','句末一定要加标点')]},
        ],
        'E4': [
            {'title': '看图说话理解', 'question': '看图回答：图上有谁？在做什么？',
             'steps': ['说清楚人物','说清楚动作','说清楚地点'],
             'answer': '谁/在哪/做什么', 'tip': '看图说话三要素：谁+在哪+做什么！',
             'wrong': [('只说一个字','要说完整的句子')]},
        ],
        'E5': [
            {'title': '课文填空', 'question': '床前（  ），疑是（  ）。',
             'steps': ['床前明月光','疑是地上霜'],
             'answer': '明月光，地上霜', 'tip': '静夜思全文4句20字要背熟！',
             'wrong': [('明月亮（错字）','是"光"不是"亮"')]},
        ],
        'E6': [
            {'title': '看图写话模板', 'question': '看图写2-3句话',
             'steps': ['第1句：什么时候','第2句：谁在哪里做什么','第3句：心情怎么样'],
             'answer': '时间+人物+事件', 'tip': '一句写一件事，别忘标点！',
             'wrong': [('一句话写到底','要分成几句话')]},
        ],
    },
    '一下': {
        'topics': ['识字写字', '词语搭配', '短文阅读', '日积月累'],
        'E1': [
            {'title': '形近字组词辨析', 'question': '区分组词：请/清/青/晴/情',
             'steps': ['请=请求(言字旁→说话)','清=清水(三点水→水)','青=青草(无偏旁→颜色)','晴=晴天(日字旁→太阳)','情=感情(竖心旁→心)'],
             'answer': '看偏旁定含义', 'tip': '偏旁定意思：言说水清日晴心情！',
             'wrong': [('请/清搞混','言字旁→说话相关')]},
            {'title': '前后鼻音区分', 'question': 'an-ang, en-eng, in-ing 区别',
             'steps': ['an嘴巴张大舌尖前','ang嘴巴张大舌根后','关键：有g的舌头后缩'],
             'answer': '有g舌根后缩', 'tip': 'g结尾=后鼻音，舌头贴后面！',
             'wrong': [('分不清前后鼻音','有g后鼻，无g前鼻')]},
        ],
        'E2': [
            {'title': '量词选择', 'question': '一（ ）小鱼 A.条 B.只 C.头',
             'steps': ['鱼用"条"','鸟/猫用"只"','牛/猪用"头"'],
             'answer': 'A', 'tip': '条→鱼/蛇/路，只→鸟/猫/鸡，头→牛/象！',
             'wrong': [('一只鱼','鱼用条不用只')]},
        ],
        'E3': [
            {'title': '把字句和被字句', 'question': '改写：小猫吃了鱼。→ 把/被字句',
             'steps': ['把字句：小猫把鱼吃了。','被字句：鱼被小猫吃了。'],
             'answer': '把字句/被字句', 'tip': '把+受的→主动；被+做的→被动！',
             'wrong': [('把和被混用','把=我做，被=被做')]},
        ],
        'E4': [
            {'title': '短文数句子', 'question': '读短文，数一数有几句话',
             'steps': ['找句号。问号？感叹号！','每个标点=一句话结束'],
             'answer': '数标点定句数', 'tip': '句号/问号/叹号=一句话结束！',
             'wrong': [('逗号也算一句','逗号是停顿，不是句子结束')]},
        ],
        'E5': [
            {'title': '日积月累填空', 'question': '春雨惊春清谷天，（  ）',
             'steps': ['24节气歌第二句','夏满芒夏暑相连'],
             'answer': '夏满芒夏暑相连', 'tip': '节气歌4句背熟，考试必考！',
             'wrong': [('暑相联（错字）','是"连"不是"联"')]},
        ],
        'E6': [
            {'title': '写一段话模板', 'question': '我最喜欢的___',
             'steps': ['我最喜欢___。','它___（样子）。','因为___。','我真喜欢它！'],
             'answer': '喜欢+描写+原因', 'tip': '先说喜欢什么→再说原因→最后总结！',
             'wrong': [('写一句就完了','至少写3-4句')]},
        ],
    },
    '二上': {
        'topics': ['查字典', '多音字', '造句', '写话', '古诗两首'],
        'E1': [
            {'title': '查字典填空', 'question': '"花"字用部首查字法：先查（ ）部，再查（ ）画',
             'steps': ['花：草字头→艹部','花去掉艹=化，4画'],
             'answer': '艹部，4画', 'tip': '部首查字法：去掉部首数剩余笔画！',
             'wrong': [('总笔画7','要去掉部首再数')]},
            {'title': '多音字组词', 'question': '乐: lè（  ）yuè（  ）',
             'steps': ['lè=快乐、乐趣', 'yuè=音乐、乐器'],
             'answer': '快乐，音乐', 'tip': '快乐的乐lè，音乐的乐yuè！',
             'wrong': [('音乐读lè','音乐的乐读yuè')]},
        ],
        'E2': [
            {'title': '近义词选择', 'question': '"美丽"的近义词：A.丑陋 B.漂亮 C.高大',
             'steps': ['美丽=好看=漂亮','丑陋是反义词'],
             'answer': 'B', 'tip': '近义词=意思相近，反义词=意思相反！',
             'wrong': [('选A反义词','题目问的是近义词')]},
        ],
        'E3': [
            {'title': '造句练习', 'question': '用"一边...一边..."造句',
             'steps': ['主语+一边+动作1+一边+动作2','妈妈一边做饭一边唱歌。'],
             'answer': '完整通顺的句子', 'tip': '两个动作要能同时做！',
             'wrong': [('一边写字一边跑步','不能同时做的不行')]},
        ],
        'E4': [
            {'title': '短文主要内容', 'question': '读短文，说说主要讲了什么？',
             'steps': ['找时间地点人物','找起因经过结果','组织成一句话'],
             'answer': '谁+做了什么+结果', 'tip': '主要内容=去掉细节只留骨架！',
             'wrong': [('把全文抄一遍','要概括不是抄写')]},
        ],
        'E5': [
            {'title': '古诗理解填空', 'question': '《望庐山瀑布》：飞流直下三千尺，（  ）',
             'steps': ['疑是银河落九天'],
             'answer': '疑是银河落九天', 'tip': '李白名句：飞流银河成一对！',
             'wrong': [('银河落九天疑是','顺序不能换')]},
        ],
        'E6': [
            {'title': '看图写话升级', 'question': '观察图片写一段话(4-5句)',
             'steps': ['第1句：什么时候什么地方','第2句：谁在做什么','第3句：具体描写(样子/动作)','第4句：心情或想法'],
             'answer': '时间+人物+事件+心情', 'tip': '写话四要素：时地人事+心情！',
             'wrong': [('没有心情描写','加上心情更丰富')]},
        ],
    },
    '二下': {
        'topics': ['找春天', '识字加油站', '口语交际', '写话', '日积月累'],
        'E1': [
            {'title': '同音字填空', 'question': '选填：带/代/待  等（ ） 皮（ ） （ ）表',
             'steps': ['等待(等候)','皮带(穿戴)','代表(代替)'],
             'answer': '待，带，代', 'tip': '等待=停留，皮带=穿戴，代表=替代！',
             'wrong': [('全填"带"','三个字含义不同')]},
            {'title': '加偏旁组新字', 'question': '"青"加偏旁组3个字',
             'steps': ['请(言)清(水)晴(日)情(心)精(米)睛(目)','选3个说清意思'],
             'answer': '请/清/晴等', 'tip': '一个字加不同偏旁=不同字不同意思！',
             'wrong': [('只写字不组词','要加上组词才完整')]},
        ],
        'E2': [
            {'title': '关联词选择', 'question': '（  ）下雨了，我们（  ）不去公园了。A.因为...所以 B.虽然...但是',
             'steps': ['下雨是原因，不去是结果','因果关系→因为...所以'],
             'answer': 'A', 'tip': '因为...所以=因果, 虽然...但是=转折！',
             'wrong': [('选B转折','这是因果关系')]},
        ],
        'E3': [
            {'title': '缩句练习', 'question': '美丽的蝴蝶在花丛中快乐地飞舞。→缩句',
             'steps': ['去掉修饰词','谁→蝴蝶','做什么→飞舞','蝴蝶飞舞。'],
             'answer': '蝴蝶飞舞。', 'tip': '缩句去「的地得前+时间地点」只留主干！',
             'wrong': [('美丽的蝴蝶飞舞','去掉"美丽的"')]},
        ],
        'E4': [
            {'title': '短文理解基础', 'question': '为什么说春天来了？从文中找2个理由',
             'steps': ['找关键句子','用原文回答','标注在第几段'],
             'answer': '原文依据', 'tip': '答案在文中找，用原文原句！',
             'wrong': [('自己编答案','要从文中找依据')]},
        ],
        'E5': [
            {'title': '日积月累选填', 'question': '（  ），春风吹又生。——白居易',
             'steps': ['离离原上草，一岁一枯荣','野火烧不尽，春风吹又生'],
             'answer': '野火烧不尽', 'tip': '白居易《草》全诗4句必背！',
             'wrong': [('离离原上草','这是第一句不是第三句')]},
        ],
        'E6': [
            {'title': '写话提升模板', 'question': '我的好朋友',
             'steps': ['我的好朋友叫___。','他/她___（样子）。','我们经常一起___。','我觉得___真好！'],
             'answer': '介绍+描写+事件+感受', 'tip': '人物写话：长相+事件+感受=完整！',
             'wrong': [('只写名字','要写具体描写')]},
        ],
    },
    '三上': {
        'topics': ['大自然的声音', '总也倒不了的老屋', '古诗三首', '阅读策略', '习作'],
        'E1': [
            {'title': '多音字辨析填空', 'question': '假：jiǎ（  ）jià（  ）；乐: lè（  ）yuè（  ）',
             'steps': ['假jiǎ=假如/真假','假jià=放假/假期','乐lè=快乐','乐yuè=音乐'],
             'answer': '真假jiǎ，假期jià；快乐lè，音乐yuè', 'tip': '根据词义定读音！',
             'wrong': [('放假读jiǎ','假期的假读jià')]},
            {'title': '形近字辨析', 'question': '辨析组词: 峰/蜂  辨/辩/辫',
             'steps': ['峰=山峰(山)，蜂=蜜蜂(虫)','辨=辨别(刀)，辩=争辩(言)，辫=辫子(丝)'],
             'answer': '看偏旁辨字义', 'tip': '辨(刀切分辨)辩(言语争辩)辫(丝线编辫)！',
             'wrong': [('三个辨分不清','中间见偏旁：刀/言/丝')]},
        ],
        'E2': [
            {'title': '修辞手法选择', 'question': '"荷叶上的水珠像珍珠一样晶莹。"用了什么修辞？A.拟人 B.比喻 C.排比',
             'steps': ['有"像"→比喻','把水珠比作珍珠'],
             'answer': 'B', 'tip': '像/好像/如同/仿佛=比喻信号词！',
             'wrong': [('选A拟人','拟人是把物当人写')]},
        ],
        'E3': [
            {'title': '反问句改陈述句', 'question': '"难道这不是你的书吗？"改陈述句',
             'steps': ['去掉"难道...吗"','去掉"不"反转意思','这是你的书。'],
             'answer': '这是你的书。', 'tip': '反问改陈述：去掉反问词，否定变肯定！',
             'wrong': [('这不是你的书','反问含否定=肯定意思')]},
        ],
        'E4': [
            {'title': '阅读理解答题法', 'question': '联系上下文理解词语意思',
             'steps': ['找到词语在文中的位置','读前后句','用自己的话解释'],
             'answer': '联系上下文', 'tip': '词语理解=找位置+看前后+自己说！',
             'wrong': [('只背字典意思','要联系文中具体语境')]},
        ],
        'E5': [
            {'title': '古诗填写', 'question': '《山行》：远上寒山石径斜，（  ）。',
             'steps': ['白云生处有人家'],
             'answer': '白云生处有人家', 'tip': '注意："生处"不是"深处"！',
             'wrong': [('白云深处','是"生处"不是"深处"')]},
        ],
        'E6': [
            {'title': '写景作文模板', 'question': '这儿真美',
             'steps': ['开头：总写美（1句）','中间：分写天上/地上/水中（2-3段）','结尾：感受（1句）'],
             'answer': '总分总结构', 'tip': '写景=总分总+按顺序+用修辞！',
             'wrong': [('想到哪写到哪','要有顺序：上→下/远→近')]},
        ],
    },
    '三下': {
        'topics': ['燕子', '守株待兔', '纸的发明', '花钟', '习作：我的植物朋友'],
        'E1': [
            {'title': '易错字词听写', 'question': '听写：聚拢、偶尔、增添',
             'steps': ['聚拢的"拢"是提手旁','偶尔不是"偶而"','增添的"添"注意右下是"点"'],
             'answer': '聚拢/偶尔/增添', 'tip': '拢≠笼，尔≠而，添≠天！',
             'wrong': [('偶而(错字)','是"尔"不是"而"')]},
            {'title': '近反义词填空', 'question': '近义词: 聚拢→(  ) 反义词: 增添→(  )',
             'steps': ['聚拢≈聚集','增添的反义=减少'],
             'answer': '聚集，减少', 'tip': '近义词换位能说通，反义词相反！',
             'wrong': [('增添的反义=增加','增加和增添是近义词')]},
        ],
        'E2': [
            {'title': '标点符号选择', 'question': '下列用法正确的是？A."你好。"他说。B."你好，"他说。',
             'steps': ['引号内说完的话，后面还有"他说"','用逗号不用句号'],
             'answer': 'B', 'tip': '引号内后面有"XX说"→引号内逗号！',
             'wrong': [('选A','后面有说话人时用逗号')]},
        ],
        'E3': [
            {'title': '转述句改写', 'question': '小明说："我明天要去公园。"→改转述句',
             'steps': ['第一人称→第三人称','冒号引号→逗号','小明说，他明天要去公园。'],
             'answer': '小明说，他明天要去公园。', 'tip': '转述改三样：标点+人称+指示词！',
             'wrong': [('小明说，我明天要去','要把"我"改成"他"')]},
        ],
        'E4': [
            {'title': '概括段意', 'question': '读一段话，概括这段话的主要意思',
             'steps': ['找中心句(通常在开头或结尾)','没有中心句就概括：谁+做了什么+结果'],
             'answer': '主要内容', 'tip': '先找中心句，没有就自己概括！',
             'wrong': [('抄全段','概括不是抄写')]},
        ],
        'E5': [
            {'title': '《绝句》填空', 'question': '迟日江山丽，（  ）。泥融飞燕子，（  ）。',
             'steps': ['春风花草香','沙暖睡鸳鸯'],
             'answer': '春风花草香，沙暖睡鸳鸯', 'tip': '绝句4句写春天，日-风-燕-鸳！',
             'wrong': [('沙暖睡鸳(漏鸯)','鸳鸯两个字都要写')]},
        ],
        'E6': [
            {'title': '我的植物朋友模板', 'question': '写一种你喜欢的植物',
             'steps': ['开头：介绍植物名称','看：外形描写(形/色/大小)','闻/摸：感觉描写','结尾：表达喜爱之情'],
             'answer': '多感官描写', 'tip': '写植物用五感：看形/闻香/摸叶/听风/尝果！',
             'wrong': [('只写看到的','多感官描写更丰富')]},
        ],
    },
    '四上': {
        'topics': ['观潮', '蟋蟀的住宅', '古诗三首', '爬山虎的脚', '习作：推荐一个好地方'],
        'E1': [
            {'title': '易错生字词', 'question': '听写: 鼎沸、笼罩、均匀',
             'steps': ['鼎沸：鼎(三足)沸(水开)','笼罩：笼(竹)罩(四)','均匀：均(土)匀(勹内有一横)'],
             'answer': '鼎沸/笼罩/均匀', 'tip': '鼎有三只脚+两耳！',
             'wrong': [('鼎少一笔','鼎共12画')]},
            {'title': '词语搭配填空', 'question': '（  ）地响 / （  ）的声音 / （  ）地流',
             'steps': ['隆隆地响(ABB式)','巨大的声音','缓缓地流(AABB)'],
             'answer': '隆隆/巨大/缓缓', 'tip': '的+名词，地+动词，得+形容词！',
             'wrong': [('的地得混用','记住：地前面的修饰动词')]},
        ],
        'E2': [
            {'title': '说明方法辨别', 'question': '列数字、打比方、举例子分别是？',
             'steps': ['有数据=列数字','有"像"=打比方','有"例如"=举例子'],
             'answer': '数据/像/例如', 'tip': '看信号词：数字→列数字，像→打比方！',
             'wrong': [('打比方=比喻','说明文叫打比方，不叫比喻')]},
        ],
        'E3': [
            {'title': '双重否定句', 'question': '改双重否定句：你必须去上学。',
             'steps': ['加两个否定词','你不能不去上学。/你不得不去上学。'],
             'answer': '你不能不去上学。', 'tip': '双重否定=肯定语气更强！',
             'wrong': [('你不必去上学','这是否定句不是双重否定')]},
        ],
        'E4': [
            {'title': '理解关键句子', 'question': '联系全文理解句子含义',
             'steps': ['字面意思→深层意思','联系上下文→联系中心','有修辞→还原真实意思'],
             'answer': '表面+深层', 'tip': '关键句理解=字面意+深层意+联系中心！',
             'wrong': [('只说字面意思','一定有深层含义')]},
        ],
        'E5': [
            {'title': '《题西林壁》默写', 'question': '横看成岭侧成峰，（  ）。不识庐山真面目，（  ）。',
             'steps': ['远近高低各不同','只缘身在此山中'],
             'answer': '远近高低各不同，只缘身在此山中', 'tip': '注意"缘"不是"原"！',
             'wrong': [('只原身在此山中','是"缘"不是"原"')]},
        ],
        'E6': [
            {'title': '推荐一个好地方', 'question': '介绍你去过的一个好地方',
             'steps': ['开头：直接点明推荐的地方','中间：分段写特色(景色/美食/文化)','穿插感受和修辞','结尾：呼吁大家去看看'],
             'answer': '总分总+推荐理由', 'tip': '推荐文=我推荐+为什么好+快来看！',
             'wrong': [('像日记一样记流水账','要突出"好"在哪里')]},
        ],
    },
    '四下': {
        'topics': ['古诗词三首', '琥珀', '飞向蓝天的恐龙', '海上日出', '习作：我的乐园'],
        'E1': [
            {'title': '四字词语填空', 'question': '补充词语: 波澜（  ）阔  应接不（  ）',
             'steps': ['波澜壮阔', '应接不暇'],
             'answer': '壮，暇', 'tip': '壮=盛大，暇=空闲时间！',
             'wrong': [('波澜状阔','是"壮"不是"状"')]},
            {'title': '多义字选义项', 'question': '"深"在不同句子中的含义？1.河水很深 2.深红色',
             'steps': ['1.深=距离大(实指)', '2.深=浓/程度高(抽象)'],
             'answer': '实指距离/抽象程度', 'tip': '一字多义看语境！',
             'wrong': [('都选"距离大"','要看具体语境')]},
        ],
        'E2': [
            {'title': '病句选择', 'question': '找出病句: A.春天的公园真美丽。B.小明改正了缺点。C.他非常很高兴。',
             'steps': ['C."非常"和"很"重复','去掉一个即可'],
             'answer': 'C', 'tip': '修饰词不能重复堆叠！',
             'wrong': [('选B','改正缺点搭配正确')]},
        ],
        'E3': [
            {'title': '仿写排比句', 'question': '仿写: 幸福是___，幸福是___，幸福是___。',
             'steps': ['三个分句结构相同','内容层层递进','幸福是甜甜的微笑，幸福是温暖的拥抱，幸福是家人的陪伴。'],
             'answer': '三个相同结构', 'tip': '排比=3个以上结构相同+内容递进！',
             'wrong': [('只写两个','排比至少三个')]},
        ],
        'E4': [
            {'title': '概括文章主要内容', 'question': '用简洁的话概括文章主要内容',
             'steps': ['找六要素：时间/地点/人物/起因/经过/结果','串联成一句话'],
             'answer': '六要素概括法', 'tip': '谁+在哪+为什么+做了什么+结果=主要内容！',
             'wrong': [('三言两语说不清','抓重点略细节')]},
        ],
        'E5': [
            {'title': '《清平乐·村居》默写', 'question': '茅檐低小，溪上青青草。（  ），（  ）。',
             'steps': ['醉里吴音相媚好','白发谁家翁媪'],
             'answer': '醉里吴音相媚好，白发谁家翁媪', 'tip': '"媪"ǎo不是"温"！',
             'wrong': [('白发谁家翁温','是"媪"不是"温"')]},
        ],
        'E6': [
            {'title': '我的乐园模板', 'question': '写一写你的乐园',
             'steps': ['开头：我的乐园是___','中间1: 乐园的样子','中间2: 在那里做什么','中间3: 最难忘的一次','结尾：表达喜爱'],
             'answer': '介绍+活动+情感', 'tip': '乐园=什么地方+做什么+为什么快乐！',
             'wrong': [('只写地方不写活动','要写在乐园里的快乐体验')]},
        ],
    },
    '五上': {
        'topics': ['白鹭', '落花生', '桂花雨', '古诗词三首', '习作：我的心爱之物'],
        'E1': [
            {'title': '词义辨析填空', 'question': '严格/严厉/严肃/严密 选填',
             'steps': ['严格：标准要求高','严厉：态度生硬','严肃：认真不苟','严密：不留漏洞'],
             'answer': '根据语境选词', 'tip': '严"后面跟什么决定选哪个！',
             'wrong': [('全用一个"严格"','不同搭配不同字')]},
            {'title': '关联词填空', 'question': '（ ）今天下雨，（ ）运动会照常举行。',
             'steps': ['转折关系','虽然...但是/尽管...还是'],
             'answer': '虽然...但是', 'tip': '转折=虽然但是, 因果=因为所以, 条件=只要就！',
             'wrong': [('因为...所以','这是转折不是因果')]},
        ],
        'E2': [
            {'title': '表达方法选择', 'question': '以下哪个是借物喻人？A.落花生外表不美内心美 B.桂花雨稀里哗啦',
             'steps': ['借物喻人=借物的品质说人','花生外表朴实内心有用→喻朴实有用的人'],
             'answer': 'A', 'tip': '借物喻人=物品特点=人物品质！',
             'wrong': [('选B','桂花雨是场景描写')]},
        ],
        'E3': [
            {'title': '缩句与扩句', 'question': '缩句：五彩缤纷的花朵在温暖的阳光下快乐地绽放。',
             'steps': ['去掉修饰：五彩缤纷的、温暖的、快乐地','花朵绽放。'],
             'answer': '花朵绽放。', 'tip': '缩句只留：谁/什么+干什么/怎么样！',
             'wrong': [('花朵在阳光下绽放','要去掉所有修饰成分')]},
        ],
        'E4': [
            {'title': '体会思想感情', 'question': '作者通过___表达了___的感情',
             'steps': ['找关键词句','联系作者背景','概括中心思想'],
             'answer': '中心思想', 'tip': '思想感情=通过什么+表达什么！',
             'wrong': [('只说事件不说感情','一定要说表达了什么')]},
        ],
        'E5': [
            {'title': '《示儿》默写', 'question': '死去元知万事空，（  ）。王师北定中原日，（  ）。',
             'steps': ['但悲不见九州同','家祭无忘告乃翁'],
             'answer': '但悲不见九州同，家祭无忘告乃翁', 'tip': '注意"元"不是"原"，"乃"不是"奶"！',
             'wrong': [('死去原知','是"元知"不是"原知"')]},
        ],
        'E6': [
            {'title': '我的心爱之物模板', 'question': '写你最心爱的一样东西',
             'steps': ['开头：直接点明心爱之物','来历：怎么得到的','描写：外形+特点','故事：和它之间的故事','结尾：为什么心爱'],
             'answer': '来历+描写+故事+情感', 'tip': '心爱之物一定要写感情和故事！',
             'wrong': [('只写长什么样','要写为什么心爱')]},
        ],
    },
    '五下': {
        'topics': ['草船借箭', '景阳冈', '童年的发现', '手指', '习作：把一个人的特点写具体'],
        'E1': [
            {'title': '易混字词辨析', 'question': '用"截/载/裁/栽"填空',
             'steps': ['截=切断/截止','载=装载/承载','裁=裁剪/裁判','栽=栽种/栽培'],
             'answer': '根据字义填空', 'tip': '截(戈=刀)载(车)裁(衣)栽(木)看偏旁！',
             'wrong': [('截和栽分不清','截=刀断，栽=木种')]},
            {'title': '文言文词义', 'question': '解释: "忿然"、"才"(武松)的意思',
             'steps': ['忿然=愤怒的样子','才=才能/武艺'],
             'answer': '联系古文语境', 'tip': '文言文一字多义要看具体句子！',
             'wrong': [('用现代意思','古文词义和现代可能不同')]},
        ],
        'E2': [
            {'title': '人物描写方法选择', 'question': '哪句是心理描写？A."我想..." B."他大喊" C."他跑过去"',
             'steps': ['心理=内心想法→A','B是语言描写','C是动作描写'],
             'answer': 'A', 'tip': '动作/语言/心理/神态/外貌=五种描写方法！',
             'wrong': [('选B以为说出来的是心理','说出来是语言描写')]},
        ],
        'E3': [
            {'title': '改间接引语', 'question': '老师说："你们要认真学习。"→改转述',
             'steps': ['冒号引号→逗号','你们→我们/他们(看角度)','老师说，我们要认真学习。'],
             'answer': '老师说，我们/他们要认真学习。', 'tip': '人称代词一定要改！',
             'wrong': [('老师说，你们要认真学习','要改人称代词')]},
        ],
        'E4': [
            {'title': '理解文章写法', 'question': '这篇文章用了什么表达方法？',
             'steps': ['举例子/打比方/作比较/列数字=说明','首尾呼应/正面侧面/借物喻人=文学'],
             'answer': '辨别表达方法', 'tip': '先判断是说明文还是叙事文！',
             'wrong': [('所有修辞都列一遍','要找文章实际用的')]},
        ],
        'E5': [
            {'title': '《从军行》默写', 'question': '青海长云暗雪山，（  ）。黄沙百战穿金甲，（  ）。',
             'steps': ['孤城遥望玉门关','不破楼兰终不还'],
             'answer': '孤城遥望玉门关，不破楼兰终不还', 'tip': '"遥望"不是"远望"！',
             'wrong': [('孤城远望','是"遥望"不是"远望"')]},
        ],
        'E6': [
            {'title': '把人写具体模板', 'question': '描写一个人的特点',
             'steps': ['开头：点明人物和特点','事例1: 通过一个事展示特点','事例2: 换个角度展示','结尾：总结印象'],
             'answer': '特点+典型事例', 'tip': '写人=典型事例+细节描写(动作+语言+神态)！',
             'wrong': [('只说特点不举例','要用事例来证明')]},
        ],
    },
    '六上': {
        'topics': ['草原', '丁香结', '古诗词三首', '竹节人', '习作：多彩的活动'],
        'E1': [
            {'title': '高频易错字词', 'question': '听写: 渲染、勾勒、襟飘带舞',
             'steps': ['渲染(三点水+宣)','勾勒(勹+力)','襟飘=衣襟飘动'],
             'answer': '渲/勒/襟', 'tip': '渲(水)不是喧(口)，勒中间横别丢！',
             'wrong': [('喧染','是"渲"三点水')]},
            {'title': '词语褒贬义', 'question': '判断褒贬: 果断/武断  聪明/狡猾',
             'steps': ['果断=褒，武断=贬','聪明=褒，狡猾=贬'],
             'answer': '褒贬配对', 'tip': '褒义=夸人好，贬义=说人坏！',
             'wrong': [('都是褒义','武断和狡猾是贬义')]},
        ],
        'E2': [
            {'title': '修辞辨别题', 'question': '下列不是比喻句的是：A.他像一头牛 B.他是班长 C.月亮如银盘',
             'steps': ['B是判断句不是比喻','虽有"是"但不是比较两种事物'],
             'answer': 'B', 'tip': 'A像B：A和B是不同类事物才是比喻！',
             'wrong': [('选A','A有像且比较了两类事物')]},
        ],
        'E3': [
            {'title': '句式综合变换', 'question': '改写比喻句：这朵花很红。',
             'steps': ['找到要比喻的特点：红','联想红色的事物：火焰','这朵花红得像火焰一样。'],
             'answer': '这朵花红得像火焰。', 'tip': '比喻=本体+像+喻体，两物不同类！',
             'wrong': [('这朵花像玫瑰','花和玫瑰同类不算比喻')]},
        ],
        'E4': [
            {'title': '分析文章结构', 'question': '这篇文章是什么结构？(总分总/总分/时间顺序等)',
             'steps': ['看开头是否总述→是否分层→是否总结','判断结构类型'],
             'answer': '分析文章结构', 'tip': '总分总最常见：开头概括+中间展开+结尾总结！',
             'wrong': [('想当然就写','要从文章实际结构判断')]},
        ],
        'E5': [
            {'title': '《七律·长征》默写', 'question': '红军不怕远征难，（  ）。五岭逶迤腾细浪，（  ）。',
             'steps': ['万水千山只等闲','乌蒙磅礴走泥丸'],
             'answer': '万水千山只等闲，乌蒙磅礴走泥丸', 'tip': '逶迤wēiyí、磅礴pángbó字别写错！',
             'wrong': [('委迤','是逶迤不是委迤')]},
        ],
        'E6': [
            {'title': '多彩活动模板', 'question': '写一次活动',
             'steps': ['开头：活动名称+时间地点','起因：为什么举行','经过：详写精彩片段(点面结合)','结尾：感受和收获'],
             'answer': '点面结合写活动', 'tip': '面=全场描写+点=个人特写！',
             'wrong': [('只写自己','要将个人镜头和全场镜头结合')]},
        ],
    },
    '六下': {
        'topics': ['北京的春节', '鲁滨逊漂流记', '骑鹅旅行记', '古诗词诵读', '习作：毕业寄语'],
        'E1': [
            {'title': '易混词语辨析', 'question': '截然/竟然/果然/居然 选填',
             'steps': ['截然=完全不同','竟然=出乎意料','果然=正如所料','居然=没想到(惊讶)'],
             'answer': '看语境填词', 'tip': '果然=不意外，竟然/居然=很意外！',
             'wrong': [('竟然和居然分不清','两者很近义都表意外')]},
            {'title': '文言文字义', 'question': '解释："两小儿辩日"中"辩"的意思',
             'steps': ['辩=辩论、争辩','不是"辨"(辨别)也不是"变"'],
             'answer': '争辩、辩论', 'tip': '辩(言)=用语言争论！',
             'wrong': [('辨别','此处是争辩')]},
        ],
        'E2': [
            {'title': '阅读方法选择', 'question': '读长篇小说应该用什么方法？A.逐字精读 B.浏览+精读结合 C.只看插图',
             'steps': ['长篇适合浏览+精读结合','浏览了解全貌，精读品味细节'],
             'answer': 'B', 'tip': '长文=快速浏览+关键精读！',
             'wrong': [('选A全部精读','太花时间，要分轻重')]},
        ],
        'E3': [
            {'title': '仿写句式', 'question': '仿写：...不必说...也不必说...单是...',
             'steps': ['结构：不必说A也不必说B单是C','从大到小/从远到近','单是的内容要详写'],
             'answer': '仿写结构', 'tip': '不必说不必说是略写，单是才是详写重点！',
             'wrong': [('三部分平均写','单是后面要详写')]},
        ],
        'E4': [
            {'title': '分析人物形象', 'question': '结合全文分析鲁滨逊的人物特点',
             'steps': ['找关键事件','提取品质词','用事例支撑'],
             'answer': '勇敢/坚毅/乐观/聪明', 'tip': '人物分析=品质词+具体事例支撑！',
             'wrong': [('只说一个词','要列2-3个品质+对应事例')]},
        ],
        'E5': [
            {'title': '小学必背古诗综合', 'question': '总复习: 劝学/送别/爱国主题各背一首',
             'steps': ['劝学：少壮不努力，老大徒伤悲','送别：劝君更尽一杯酒，西出阳关无故人','爱国：王师北定中原日，家祭无忘告乃翁'],
             'answer': '分类默写', 'tip': '按主题分类背，考前按类复习！',
             'wrong': [('只背一种主题','要分类全面复习')]},
        ],
        'E6': [
            {'title': '毕业寄语模板', 'question': '写给同学或老师的毕业赠言',
             'steps': ['回忆：还记得___吗？','感谢：谢谢你___。','祝福：愿你___。','口号：我们___！'],
             'answer': '回忆+感谢+祝福', 'tip': '毕业寄语=回忆+感恩+祝福，情真意切！',
             'wrong': [('只写套话','要有真实回忆和真情')]},
        ],
    },
}


def build_card(subject, grade_short, unit_template, card_data, card_idx):
    """Build a single card dict."""
    card_id = f"E{unit_template['unit_id'][-1]}-{card_idx:02d}"
    full_id = f"{subject}-{grade_short}-{card_id}"

    card = {
        "card_id": card_id,
        "full_id": full_id,
        "title": card_data['title'],
        "type": unit_template['card_type'],
        "difficulty": 3,
        "importance": 5,
        "exam_frequency": "高",
        "score_weight": unit_template['score_weight'],
        "definition": card_data.get('definition', f"{card_data['title']}是考试高频失分点"),
        "core_points": card_data.get('core_points', card_data['steps']),
        "example": {
            "question": card_data['question'],
            "steps": card_data['steps'],
            "answer": card_data['answer'],
        },
        "mistakes": [
            {"wrong": w[0], "correct": w[1]} for w in card_data.get('wrong', [])
        ],
        "memory_tip": card_data['tip'],
        "emotion_hook": card_data.get('emotion_hook', f"这道题全班一半人做错！你家孩子会不会？"),
    }
    return card


def build_exam_file(subject, grade, semester, grade_short, textbook, units_template, content_dict):
    """Build a complete exam JSON structure."""
    units = []
    total_cards = 0
    for ut in units_template:
        uid = ut['unit_id']
        # Get the content for this unit type
        unit_key = uid  # E1..E6
        cards_data = content_dict.get(unit_key, [])
        cards = []
        for i, cd in enumerate(cards_data):
            c = build_card(subject, grade_short, ut, cd, i + 1)
            cards.append(c)
            total_cards += 1
        units.append({
            "unit_id": uid,
            "unit_name": ut['unit_name'],
            "cards": cards,
        })

    doc = {
        "subject": subject,
        "grade": grade,
        "semester": semester,
        "textbook": textbook,
        "grade_short": grade_short,
        "card_pack": "考卷真题",
        "description": f"基于真题分析的{len(units_template)}种题型满分攻略卡片",
        "units": units,
    }
    return doc, total_cards


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    generated = []

    for grade, gs, sem in GRADES:
        # 数学
        if gs in MATH_GRADE_CONTENT and MATH_GRADE_CONTENT[gs] is not None:
            fname = f"数学_{gs}_考卷.json"
            fpath = os.path.join(OUT_DIR, fname)
            if os.path.exists(fpath):
                print(f"[SKIP] {fname} (already exists)")
            else:
                doc, nc = build_exam_file('数学', grade, sem, gs, '人教版', MATH_UNITS_TEMPLATE, MATH_GRADE_CONTENT[gs])
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(doc, f, ensure_ascii=False, indent=2)
                generated.append((fname, nc))
                print(f"[OK] {fname} → {nc} cards")

        # 英语 (三年级起)
        grade_num = int(grade[0]) if grade[0].isdigit() else {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6}.get(grade[0], 0)
        if grade_num >= 3 and gs in ENGLISH_GRADE_CONTENT and ENGLISH_GRADE_CONTENT[gs] is not None:
            fname = f"英语_{gs}_考卷.json"
            fpath = os.path.join(OUT_DIR, fname)
            if os.path.exists(fpath):
                print(f"[SKIP] {fname} (already exists)")
            else:
                doc, nc = build_exam_file('英语', grade, sem, gs, '人教版(PEP)', ENGLISH_UNITS_TEMPLATE, ENGLISH_GRADE_CONTENT[gs])
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(doc, f, ensure_ascii=False, indent=2)
                generated.append((fname, nc))
                print(f"[OK] {fname} → {nc} cards")

        # 语文
        if gs in CHINESE_GRADE_CONTENT and CHINESE_GRADE_CONTENT[gs] is not None:
            fname = f"语文_{gs}_考卷.json"
            fpath = os.path.join(OUT_DIR, fname)
            if os.path.exists(fpath):
                print(f"[SKIP] {fname} (already exists)")
            else:
                doc, nc = build_exam_file('语文', grade, sem, gs, '人教版(统编)', CHINESE_UNITS_TEMPLATE, CHINESE_GRADE_CONTENT[gs])
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(doc, f, ensure_ascii=False, indent=2)
                generated.append((fname, nc))
                print(f"[OK] {fname} → {nc} cards")

    print(f"\n=== Generated {len(generated)} files ===")
    total = sum(nc for _, nc in generated)
    print(f"Total new cards: {total}")

    # Copy to root knowledge_cards
    root_dir = os.path.join(os.path.dirname(__file__), 'knowledge_cards', '小学')
    os.makedirs(root_dir, exist_ok=True)
    import shutil
    for fname, _ in generated:
        src = os.path.join(OUT_DIR, fname)
        dst = os.path.join(root_dir, fname)
        shutil.copy2(src, dst)
        print(f"[COPY] {fname} → root")

    # Update manifest.json in both locations
    for mpath in [
        os.path.join(os.path.dirname(__file__), 'public', 'knowledge_cards', 'manifest.json'),
        os.path.join(os.path.dirname(__file__), 'knowledge_cards', 'manifest.json'),
    ]:
        with open(mpath, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        existing_files = {e['file'] for e in manifest['stages'].get('小学', [])}
        added = 0
        for fname, nc in generated:
            if fname not in existing_files:
                # Infer subject/grade
                parts = fname.replace('.json','').replace('_考卷','').split('_')
                subj = parts[0]
                gs2 = parts[1]
                grade_map = {'一上':('一年级','上册'),'一下':('一年级','下册'),'二上':('二年级','上册'),'二下':('二年级','下册'),
                             '三上':('三年级','上册'),'三下':('三年级','下册'),'四上':('四年级','上册'),'四下':('四年级','下册'),
                             '五上':('五年级','上册'),'五下':('五年级','下册'),'六上':('六年级','上册'),'六下':('六年级','下册')}
                g, s = grade_map[gs2]
                # Count units from the generated file
                with open(os.path.join(OUT_DIR, fname), 'r', encoding='utf-8') as ff:
                    data = json.load(ff)
                    nu = len(data['units'])
                    nc2 = sum(len(u['cards']) for u in data['units'])

                entry = {
                    "file": fname,
                    "subject": subj,
                    "grade": g,
                    "semester": s,
                    "grade_short": gs2,
                    "is_exam": True,
                    "units": nu,
                    "cards": nc2,
                }
                manifest['stages']['小学'].append(entry)
                added += 1

        manifest['total_files'] = len(manifest['stages']['小学']) + len(manifest['stages'].get('养生减脂', []))
        manifest['total_cards'] = sum(e['cards'] for e in manifest['stages']['小学']) + sum(e.get('cards',0) for e in manifest['stages'].get('养生减脂', []))

        with open(mpath, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        print(f"[MANIFEST] {mpath} updated (+{added} entries)")

    print("\nDone!")


if __name__ == '__main__':
    main()
