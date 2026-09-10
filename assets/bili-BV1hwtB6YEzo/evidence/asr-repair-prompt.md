你是中文技术课程转录审校员。请修复 ASR 识别错误，但不要改写讲者原意。

硬性规则：
1. 只修复有证据支持的错字、术语、标点、繁简混杂和英文专名；不要补写视频里没有说的解释。
2. 保留每条 evidence_id 和时间范围，不要合并、删除或重排记录。
3. 听不准、画面也无法支持的内容必须标记 uncertain=true，repaired_content 保留最保守写法。
4. 术语优先按技术语境修正，例如 ChatGPT、softmax、QK^T、转置、词向量。
5. 输出严格 JSON 数组；每项包含 evidence_id、original_content、repaired_content、confidence、reason、uncertain。
6. 读不准但无需改写的行，不要伪造 repaired_content，改为写进不确定清单：输出对象形式 {"repairs": [...], "uncertain_ids": [...]}。

视频标题：3年少卖10亿元！曾经的国民凉茶，为什么喝的人越来越少了？

待审校时间线：
[
  {
    "evidence_id": "raw-tr-000001",
    "time": "00:00:00--00:00:01",
    "content": "三年少賣10億元"
  },
  {
    "evidence_id": "raw-tr-000002",
    "time": "00:00:01--00:00:04",
    "content": "從國民飲料到被年輕人抛棄"
  },
  {
    "evidence_id": "raw-tr-000003",
    "time": "00:00:04--00:00:05",
    "content": "王老吉涼茶"
  },
  {
    "evidence_id": "raw-tr-000004",
    "time": "00:00:05--00:00:07",
    "content": "為什麼喝得人越來越少"
  },
  {
    "evidence_id": "raw-tr-000005",
    "time": "00:00:07--00:00:08",
    "content": "做起來了茶"
  },
  {
    "evidence_id": "raw-tr-000006",
    "time": "00:00:08--00:00:10",
    "content": "你上次喝王老吉是殺手"
  },
  {
    "evidence_id": "raw-tr-000007",
    "time": "00:00:10--00:00:12",
    "content": "我至少都有一兩年沒喝過了"
  },
  {
    "evidence_id": "raw-tr-000008",
    "time": "00:00:12--00:00:13",
    "content": "廣前推十幾年"
  },
  {
    "evidence_id": "raw-tr-000009",
    "time": "00:00:13--00:00:15",
    "content": "這罐涼茶有多火呢"
  },
  {
    "evidence_id": "raw-tr-000010",
    "time": "00:00:15--00:00:16",
    "content": "2012年"
  },
  {
    "evidence_id": "raw-tr-000011",
    "time": "00:00:16--00:00:19",
    "content": "王老吉年銷售偷破200個億"
  },
  {
    "evidence_id": "raw-tr-000012",
    "time": "00:00:19--00:00:20",
    "content": "我們按三塊為官來計算的話"
  },
  {
    "evidence_id": "raw-tr-000013",
    "time": "00:00:20--00:00:23",
    "content": "相當於一年賣了57億罐"
  },
  {
    "evidence_id": "raw-tr-000014",
    "time": "00:00:23--00:00:25",
    "content": "平均每個中國人喝了4罐"
  },
  {
    "evidence_id": "raw-tr-000015",
    "time": "00:00:25--00:00:27",
    "content": "但那有句廣告辭職這麼說的"
  },
  {
    "evidence_id": "raw-tr-000016",
    "time": "00:00:27--00:00:28",
    "content": "中國美賣10罐涼茶"
  },
  {
    "evidence_id": "raw-tr-000017",
    "time": "00:00:28--00:00:32",
    "content": "七罐王老奇是脱脱的国民两查"
  },
  {
    "evidence_id": "raw-tr-000018",
    "time": "00:00:32--00:00:34",
    "content": "但最近几年他明显有点卖不动了"
  },
  {
    "evidence_id": "raw-tr-000019",
    "time": "00:00:34--00:00:36",
    "content": "我们现在看两组数据"
  },
  {
    "evidence_id": "raw-tr-000020",
    "time": "00:00:36--00:00:39",
    "content": "2013年王老奇大政看公司引售100个亿"
  },
  {
    "evidence_id": "raw-tr-000021",
    "time": "00:00:39--00:00:41",
    "content": "根据券商研究过算"
  },
  {
    "evidence_id": "raw-tr-000022",
    "time": "00:00:41--00:00:43",
    "content": "两查业务就占了90%"
  },
  {
    "evidence_id": "raw-tr-000023",
    "time": "00:00:43--00:00:47",
    "content": "相当于这一年王老奇两查卖了90亿元左右"
  },
  {
    "evidence_id": "raw-tr-000024",
    "time": "00:00:47--00:00:48",
    "content": "但到了2012年"
  },
  {
    "evidence_id": "raw-tr-000025",
    "time": "00:00:48--00:00:50",
    "content": "这个数据就降到了80亿"
  },
  {
    "evidence_id": "raw-tr-000026",
    "time": "00:00:50--00:00:51",
    "content": "也就是说"
  },
  {
    "evidence_id": "raw-tr-000027",
    "time": "00:00:51--00:00:53",
    "content": "三年少卖了10亿元"
  },
  {
    "evidence_id": "raw-tr-000028",
    "time": "00:00:53--00:00:55",
    "content": "比较让下降更扎心的是啥呢"
  },
  {
    "evidence_id": "raw-tr-000029",
    "time": "00:00:55--00:00:58",
    "content": "这些年轻人正在集体炮气他"
  },
  {
    "evidence_id": "raw-tr-000030",
    "time": "00:00:58--00:00:59",
    "content": "您有三叫啥显示"
  },
  {
    "evidence_id": "raw-tr-000031",
    "time": "00:00:59--00:01:01",
    "content": "18岁到35岁"
  },
  {
    "evidence_id": "raw-tr-000032",
    "time": "00:01:01--00:01:02",
    "content": "处于消费人群中"
  },
  {
    "evidence_id": "raw-tr-000033",
    "time": "00:01:02--00:01:05",
    "content": "选择王老级作为截可首选的比例"
  },
  {
    "evidence_id": "raw-tr-000034",
    "time": "00:01:05--00:01:07",
    "content": "从2012年的3月3日"
  },
  {
    "evidence_id": "raw-tr-000035",
    "time": "00:01:07--00:01:09",
    "content": "降到2012年的27%"
  },
  {
    "evidence_id": "raw-tr-000036",
    "time": "00:01:09--00:01:11",
    "content": "还有另一线叫啥显示"
  },
  {
    "evidence_id": "raw-tr-000037",
    "time": "00:01:11--00:01:12",
    "content": "你假设待你们最近三次"
  },
  {
    "evidence_id": "raw-tr-000038",
    "time": "00:01:12--00:01:14",
    "content": "喝过的鱼鸭类紧张中"
  },
  {
    "evidence_id": "raw-tr-000039",
    "time": "00:01:14--00:01:16",
    "content": "两茶只占了10%"
  },
  {
    "evidence_id": "raw-tr-000040",
    "time": "00:01:16--00:01:17",
    "content": "那我起来了"
  },
  {
    "evidence_id": "raw-tr-000041",
    "time": "00:01:17--00:01:19",
    "content": "两茶就个品类是怎么活起来的"
  },
  {
    "evidence_id": "raw-tr-000042",
    "time": "00:01:19--00:01:21",
    "content": "为什么现在喝的人越来越少了"
  },
  {
    "evidence_id": "raw-tr-000043",
    "time": "00:01:21--00:01:24",
    "content": "中国鱼鸭市场发生着什么样的变化呢"
  },
  {
    "evidence_id": "raw-tr-000044",
    "time": "00:01:24--00:01:24",
    "content": "猜兴莫名"
  },
  {
    "evidence_id": "raw-tr-000045",
    "time": "00:01:24--00:01:25",
    "content": "不然转前"
  },
  {
    "evidence_id": "raw-tr-000046",
    "time": "00:01:25--00:01:26",
    "content": "我先来讲"
  },
  {
    "evidence_id": "raw-tr-000047",
    "time": "00:01:26--00:01:33",
    "content": "我們現在講王老奇的來時錄"
  },
  {
    "evidence_id": "raw-tr-000048",
    "time": "00:01:33--00:01:36",
    "content": "他的歷史最早可以追溯到一般二八年"
  },
  {
    "evidence_id": "raw-tr-000049",
    "time": "00:01:36--00:01:37",
    "content": "清朝到廣林縣"
  },
  {
    "evidence_id": "raw-tr-000050",
    "time": "00:01:37--00:01:40",
    "content": "當時廣州人王澤邦在街頭賣糧茶"
  },
  {
    "evidence_id": "raw-tr-000051",
    "time": "00:01:40--00:01:42",
    "content": "因為製好了不少人的污液"
  },
  {
    "evidence_id": "raw-tr-000052",
    "time": "00:01:42--00:01:43",
    "content": "名聲大噪"
  },
  {
    "evidence_id": "raw-tr-000053",
    "time": "00:01:43--00:01:44",
    "content": "王澤邦的辱名叫阿奇"
  },
  {
    "evidence_id": "raw-tr-000054",
    "time": "00:01:44--00:01:48",
    "content": "所以大家就把他的糧茶稱為王老吉糧茶"
  },
  {
    "evidence_id": "raw-tr-000055",
    "time": "00:01:48--00:01:49",
    "content": "後來幾斤展轉"
  },
  {
    "evidence_id": "raw-tr-000056",
    "time": "00:01:49--00:01:50",
    "content": "被輸歸國有"
  },
  {
    "evidence_id": "raw-tr-000057",
    "time": "00:01:50--00:01:52",
    "content": "山標歸屬於廣藥集團"
  },
  {
    "evidence_id": "raw-tr-000058",
    "time": "00:01:52--00:01:56",
    "content": "但真正把王老奇從理南街頭推向全國神壇的"
  },
  {
    "evidence_id": "raw-tr-000059",
    "time": "00:01:56--00:01:57",
    "content": "是香港紅道集團"
  },
  {
    "evidence_id": "raw-tr-000060",
    "time": "00:01:57--00:02:01",
    "content": "或者說現在加多保母公司的老闆陳鴻道"
  },
  {
    "evidence_id": "raw-tr-000061",
    "time": "00:02:01--00:02:04",
    "content": "1995年陳鴻道從廣藥集團手裡"
  },
  {
    "evidence_id": "raw-tr-000062",
    "time": "00:02:04--00:02:07",
    "content": "租下了王老集紅冠商標的使用權"
  },
  {
    "evidence_id": "raw-tr-000063",
    "time": "00:02:07--00:02:09",
    "content": "對呀這花錢租下了使用權"
  },
  {
    "evidence_id": "raw-tr-000064",
    "time": "00:02:09--00:02:11",
    "content": "所有權還是廣藥集團的"
  },
  {
    "evidence_id": "raw-tr-000065",
    "time": "00:02:11--00:02:12",
    "content": "那時候的王老集"
  },
  {
    "evidence_id": "raw-tr-000066",
    "time": "00:02:12--00:02:15",
    "content": "只是一個在廣東地區有點名氣的區域性品牌"
  },
  {
    "evidence_id": "raw-tr-000067",
    "time": "00:02:15--00:02:17",
    "content": "連銷售了不過幾千萬"
  },
  {
    "evidence_id": "raw-tr-000068",
    "time": "00:02:17--00:02:20",
    "content": "之後陳鴻道就請了一家資群公司做定位"
  },
  {
    "evidence_id": "raw-tr-000069",
    "time": "00:02:20--00:02:23",
    "content": "結果很出了那句改變中國引讓使的廣告語"
  },
  {
    "evidence_id": "raw-tr-000070",
    "time": "00:02:23--00:02:25",
    "content": "怕上火和王老集"
  },
  {
    "evidence_id": "raw-tr-000071",
    "time": "00:02:25--00:02:27",
    "content": "這句廣告語牛在哪呢"
  },
  {
    "evidence_id": "raw-tr-000072",
    "time": "00:02:27--00:02:29",
    "content": "他把良茶從中央的飲品"
  },
  {
    "evidence_id": "raw-tr-000073",
    "time": "00:02:29--00:02:31",
    "content": "變成了預防上火的功能飲料"
  },
  {
    "evidence_id": "raw-tr-000074",
    "time": "00:02:31--00:02:33",
    "content": "這一下子受眾就多起來了"
  },
  {
    "evidence_id": "raw-tr-000075",
    "time": "00:02:33--00:02:34",
    "content": "就拿廣東來說"
  },
  {
    "evidence_id": "raw-tr-000076",
    "time": "00:02:34--00:02:37",
    "content": "胡籠痛、嗓子雅、口臭、施民等各種這狀"
  },
  {
    "evidence_id": "raw-tr-000077",
    "time": "00:02:37--00:02:39",
    "content": "都可以規界維俱"
  },
  {
    "evidence_id": "raw-tr-000078",
    "time": "00:02:39--00:02:40",
    "content": "你熱氣我哦"
  },
  {
    "evidence_id": "raw-tr-000079",
    "time": "00:02:40--00:02:42",
    "content": "上火又是全中國人都能聽懂的概念"
  },
  {
    "evidence_id": "raw-tr-000080",
    "time": "00:02:42--00:02:45",
    "content": "吃火鍋、熬夜、吃燒烤都可能會上火"
  },
  {
    "evidence_id": "raw-tr-000081",
    "time": "00:02:45--00:02:46",
    "content": "那怕上火嗎?"
  },
  {
    "evidence_id": "raw-tr-000082",
    "time": "00:02:46--00:02:48",
    "content": "那就來一罐《華老集》吧"
  },
  {
    "evidence_id": "raw-tr-000083",
    "time": "00:02:48--00:02:51",
    "content": "這時候眾一下次就變成了《十幾中國人》"
  },
  {
    "evidence_id": "raw-tr-000084",
    "time": "00:02:51--00:02:51",
    "content": "更關鍵的是"
  },
  {
    "evidence_id": "raw-tr-000085",
    "time": "00:02:51--00:02:54",
    "content": "在21世紀出中國廣告市場中"
  },
  {
    "evidence_id": "raw-tr-000086",
    "time": "00:02:54--00:02:55",
    "content": "電視廣告還是王者"
  },
  {
    "evidence_id": "raw-tr-000087",
    "time": "00:02:55--00:02:58",
    "content": "王老奇就抓住了机会2007年"
  },
  {
    "evidence_id": "raw-tr-000088",
    "time": "00:02:58--00:03:00",
    "content": "砸下了4.2亿天界广告费"
  },
  {
    "evidence_id": "raw-tr-000089",
    "time": "00:03:00--00:03:02",
    "content": "一局成为央视广告标亡"
  },
  {
    "evidence_id": "raw-tr-000090",
    "time": "00:03:02--00:03:03",
    "content": "这下我也是历干尽"
  },
  {
    "evidence_id": "raw-tr-000091",
    "time": "00:03:03--00:03:06",
    "content": "2007年王老奇销售额是50亿左右"
  },
  {
    "evidence_id": "raw-tr-000092",
    "time": "00:03:06--00:03:09",
    "content": "到2008年就直接犯了一番"
  },
  {
    "evidence_id": "raw-tr-000093",
    "time": "00:03:09--00:03:10",
    "content": "突破100亿"
  },
  {
    "evidence_id": "raw-tr-000094",
    "time": "00:03:10--00:03:13",
    "content": "2001年王老奇商标被估值1080个亿"
  },
  {
    "evidence_id": "raw-tr-000095",
    "time": "00:03:13--00:03:16",
    "content": "但是就在王老奇最疯关的时候"
  },
  {
    "evidence_id": "raw-tr-000096",
    "time": "00:03:16--00:03:18",
    "content": "一场矿正19的伤战爆发了"
  },
  {
    "evidence_id": "raw-tr-000097",
    "time": "00:03:18--00:03:20",
    "content": "我们先把关系与清爽"
  },
  {
    "evidence_id": "raw-tr-000098",
    "time": "00:03:20--00:03:23",
    "content": "王老奇商标的所有者是管要集团"
  },
  {
    "evidence_id": "raw-tr-000099",
    "time": "00:03:23--00:03:25",
    "content": "但是场上有两种主要的产品"
  },
  {
    "evidence_id": "raw-tr-000100",
    "time": "00:03:25--00:03:27",
    "content": "对于和玩老机有广要体系经营"
  },
  {
    "evidence_id": "raw-tr-000101",
    "time": "00:03:27--00:03:30",
    "content": "红贯玩老机则授权给红道集团"
  },
  {
    "evidence_id": "raw-tr-000102",
    "time": "00:03:30--00:03:32",
    "content": "尤其下加多保负责生产"
  },
  {
    "evidence_id": "raw-tr-000103",
    "time": "00:03:32--00:03:33",
    "content": "销售扑取到和打广告"
  },
  {
    "evidence_id": "raw-tr-000104",
    "time": "00:03:33--00:03:34",
    "content": "问题就出载这"
  },
  {
    "evidence_id": "raw-tr-000105",
    "time": "00:03:34--00:03:38",
    "content": "2008年红贯玩老机销售额突破了100个亿"
  },
  {
    "evidence_id": "raw-tr-000106",
    "time": "00:03:38--00:03:40",
    "content": "广要当年收到的商标使用费事多少呢"
  },
  {
    "evidence_id": "raw-tr-000107",
    "time": "00:03:40--00:03:42",
    "content": "大概是500万"
  },
  {
    "evidence_id": "raw-tr-000108",
    "time": "00:03:42--00:03:44",
    "content": "只相当于销售额的5万分之5"
  },
  {
    "evidence_id": "raw-tr-000109",
    "time": "00:03:44--00:03:49",
    "content": "而按照国际管理品牌租领费用是2%到8%"
  },
  {
    "evidence_id": "raw-tr-000110",
    "time": "00:03:49--00:03:49",
    "content": "广要一看"
  },
  {
    "evidence_id": "raw-tr-000111",
    "time": "00:03:49--00:03:52",
    "content": "你赚这么多才分我这定点"
  },
  {
    "evidence_id": "raw-tr-000112",
    "time": "00:03:52--00:03:52",
    "content": "肯定不敢"
  },
  {
    "evidence_id": "raw-tr-000113",
    "time": "00:03:52--00:03:55",
    "content": "更大的累卖在了合同期限"
  },
  {
    "evidence_id": "raw-tr-000114",
    "time": "00:03:55--00:03:58",
    "content": "原先的商票许可和同在2010年就到期了"
  },
  {
    "evidence_id": "raw-tr-000115",
    "time": "00:03:58--00:04:00",
    "content": "后来双方又签了一份补充协议"
  },
  {
    "evidence_id": "raw-tr-000116",
    "time": "00:04:00--00:04:02",
    "content": "把期限延长到了2020年"
  },
  {
    "evidence_id": "raw-tr-000117",
    "time": "00:04:02--00:04:05",
    "content": "但维许在于签署过程设计受惠"
  },
  {
    "evidence_id": "raw-tr-000118",
    "time": "00:04:05--00:04:06",
    "content": "所以黄耀就认为"
  },
  {
    "evidence_id": "raw-tr-000119",
    "time": "00:04:06--00:04:09",
    "content": "你这不合归补充协议不向"
  },
  {
    "evidence_id": "raw-tr-000120",
    "time": "00:04:09--00:04:10",
    "content": "我要收回商标"
  },
  {
    "evidence_id": "raw-tr-000121",
    "time": "00:04:10--00:04:11",
    "content": "加多保也急了"
  },
  {
    "evidence_id": "raw-tr-000122",
    "time": "00:04:11--00:04:13",
    "content": "说我协议都签了"
  },
  {
    "evidence_id": "raw-tr-000123",
    "time": "00:04:13--00:04:15",
    "content": "我语言全气去使用到2020年"
  },
  {
    "evidence_id": "raw-tr-000124",
    "time": "00:04:15--00:04:16",
    "content": "双方是将持不下"
  },
  {
    "evidence_id": "raw-tr-000125",
    "time": "00:04:16--00:04:17",
    "content": "2011年"
  },
  {
    "evidence_id": "raw-tr-000126",
    "time": "00:04:17--00:04:18",
    "content": "黄耀就提起重裁"
  },
  {
    "evidence_id": "raw-tr-000127",
    "time": "00:04:18--00:04:20",
    "content": "双方正式开战"
  },
  {
    "evidence_id": "raw-tr-000128",
    "time": "00:04:20--00:04:21",
    "content": "光思议打就是好几年"
  },
  {
    "evidence_id": "raw-tr-000129",
    "time": "00:04:21--00:04:23",
    "content": "主要的质力有三个"
  },
  {
    "evidence_id": "raw-tr-000130",
    "time": "00:04:23--00:04:24",
    "content": "首先是最核心的"
  },
  {
    "evidence_id": "raw-tr-000131",
    "time": "00:04:24--00:04:26",
    "content": "这补充协议到底有没有效"
  },
  {
    "evidence_id": "raw-tr-000132",
    "time": "00:04:26--00:04:29",
    "content": "这次决定了加多保能不能继续用广老级商标"
  },
  {
    "evidence_id": "raw-tr-000133",
    "time": "00:04:29--00:04:31",
    "content": "2011年7月法院裁定"
  },
  {
    "evidence_id": "raw-tr-000134",
    "time": "00:04:31--00:04:32",
    "content": "无效 加多保"
  },
  {
    "evidence_id": "raw-tr-000135",
    "time": "00:04:32--00:04:34",
    "content": "进一用广老级商标"
  },
  {
    "evidence_id": "raw-tr-000136",
    "time": "00:04:34--00:04:35",
    "content": "预杀 贵文奈"
  },
  {
    "evidence_id": "raw-tr-000137",
    "time": "00:04:35--00:04:37",
    "content": "加多保就改名为加多保量查"
  },
  {
    "evidence_id": "raw-tr-000138",
    "time": "00:04:37--00:04:39",
    "content": "双方旗下来争夺的重点"
  },
  {
    "evidence_id": "raw-tr-000139",
    "time": "00:04:39--00:04:42",
    "content": "也从商标变成了红广玩老级过去激烈的山爷价值"
  },
  {
    "evidence_id": "raw-tr-000140",
    "time": "00:04:42--00:04:43",
    "content": "到底归谁"
  },
  {
    "evidence_id": "raw-tr-000141",
    "time": "00:04:43--00:04:45",
    "content": "所以请接着就是第二个正义"
  },
  {
    "evidence_id": "raw-tr-000142",
    "time": "00:04:45--00:04:46",
    "content": "广告语"
  },
  {
    "evidence_id": "raw-tr-000143",
    "time": "00:04:46--00:04:47",
    "content": "加多保改名之后"
  },
  {
    "evidence_id": "raw-tr-000144",
    "time": "00:04:47--00:04:51",
    "content": "广告企业改成了全国下辆领先的红广量查"
  },
  {
    "evidence_id": "raw-tr-000145",
    "time": "00:04:51--00:04:52",
    "content": "改名加多保"
  },
  {
    "evidence_id": "raw-tr-000146",
    "time": "00:04:52--00:04:54",
    "content": "但广要不干了"
  },
  {
    "evidence_id": "raw-tr-000147",
    "time": "00:04:54--00:04:56",
    "content": "小两里现在的产品叫王老级啊"
  },
  {
    "evidence_id": "raw-tr-000148",
    "time": "00:04:56--00:04:58",
    "content": "关点加多保啥设"
  },
  {
    "evidence_id": "raw-tr-000149",
    "time": "00:04:58--00:04:59",
    "content": "这是虚假宣传"
  },
  {
    "evidence_id": "raw-tr-000150",
    "time": "00:04:59--00:05:00",
    "content": "然后又打起了官司"
  },
  {
    "evidence_id": "raw-tr-000151",
    "time": "00:05:00--00:05:01",
    "content": "从2012年开始"
  },
  {
    "evidence_id": "raw-tr-000152",
    "time": "00:05:01--00:05:02",
    "content": "防复打了毫无机场"
  },
  {
    "evidence_id": "raw-tr-000153",
    "time": "00:05:02--00:05:05",
    "content": "最终2019年最高法院财定"
  },
  {
    "evidence_id": "raw-tr-000154",
    "time": "00:05:05--00:05:07",
    "content": "这表述符合客官事实"
  },
  {
    "evidence_id": "raw-tr-000155",
    "time": "00:05:07--00:05:08",
    "content": "不够成虚假宣传"
  },
  {
    "evidence_id": "raw-tr-000156",
    "time": "00:05:08--00:05:10",
    "content": "最后就是外包装生意"
  },
  {
    "evidence_id": "raw-tr-000157",
    "time": "00:05:10--00:05:13",
    "content": "谁可以用经典的红贯包装呢"
  },
  {
    "evidence_id": "raw-tr-000158",
    "time": "00:05:13--00:05:14",
    "content": "这官司打到2017年"
  },
  {
    "evidence_id": "raw-tr-000159",
    "time": "00:05:14--00:05:15",
    "content": "法院财决"
  },
  {
    "evidence_id": "raw-tr-000160",
    "time": "00:05:15--00:05:18",
    "content": "再不损害他人合法权益的亲戚下"
  },
  {
    "evidence_id": "raw-tr-000161",
    "time": "00:05:18--00:05:19",
    "content": "你两都可以用"
  },
  {
    "evidence_id": "raw-tr-000162",
    "time": "00:05:19--00:05:20",
    "content": "别打了"
  },
  {
    "evidence_id": "raw-tr-000163",
    "time": "00:05:20--00:05:21",
    "content": "有人统计过"
  },
  {
    "evidence_id": "raw-tr-000164",
    "time": "00:05:21--00:05:22",
    "content": "王老级的加多保"
  },
  {
    "evidence_id": "raw-tr-000165",
    "time": "00:05:22--00:05:24",
    "content": "前后打了几时场官司"
  },
  {
    "evidence_id": "raw-tr-000166",
    "time": "00:05:24--00:05:26",
    "content": "索配金額從幾個億到十幾個億不等"
  },
  {
    "evidence_id": "raw-tr-000167",
    "time": "00:05:26--00:05:27",
    "content": "從市場出現來看"
  },
  {
    "evidence_id": "raw-tr-000168",
    "time": "00:05:27--00:05:29",
    "content": "王老吉是更省一籌"
  },
  {
    "evidence_id": "raw-tr-000169",
    "time": "00:05:29--00:05:30",
    "content": "出於顯示"
  },
  {
    "evidence_id": "raw-tr-000170",
    "time": "00:05:30--00:05:30",
    "content": "2023年"
  },
  {
    "evidence_id": "raw-tr-000171",
    "time": "00:05:30--00:05:33",
    "content": "兩茶市場下手額約為450億元"
  },
  {
    "evidence_id": "raw-tr-000172",
    "time": "00:05:33--00:05:34",
    "content": "其中"
  },
  {
    "evidence_id": "raw-tr-000173",
    "time": "00:05:34--00:05:36",
    "content": "王老吉占比約44%"
  },
  {
    "evidence_id": "raw-tr-000174",
    "time": "00:05:36--00:05:38",
    "content": "加多保是25%"
  },
  {
    "evidence_id": "raw-tr-000175",
    "time": "00:05:38--00:05:40",
    "content": "但你以為加多保是最大數價嗎"
  },
  {
    "evidence_id": "raw-tr-000176",
    "time": "00:05:40--00:05:41",
    "content": "不"
  },
  {
    "evidence_id": "raw-tr-000177",
    "time": "00:05:41--00:05:43",
    "content": "最慘的其實是老三和提振"
  },
  {
    "evidence_id": "raw-tr-000178",
    "time": "00:05:43--00:05:44",
    "content": "在2010年那會"
  },
  {
    "evidence_id": "raw-tr-000179",
    "time": "00:05:44--00:05:47",
    "content": "和其證年下手額突破20億元"
  },
  {
    "evidence_id": "raw-tr-000180",
    "time": "00:05:47--00:05:48",
    "content": "穩居行業第二"
  },
  {
    "evidence_id": "raw-tr-000181",
    "time": "00:05:48--00:05:50",
    "content": "僅次於王老吉"
  },
  {
    "evidence_id": "raw-tr-000182",
    "time": "00:05:50--00:05:51",
    "content": "但在王老吉的加多保"
  },
  {
    "evidence_id": "raw-tr-000183",
    "time": "00:05:51--00:05:54",
    "content": "分家之后一超变成了双雄"
  },
  {
    "evidence_id": "raw-tr-000184",
    "time": "00:05:54--00:05:55",
    "content": "上方疯狂振作广告"
  },
  {
    "evidence_id": "raw-tr-000185",
    "time": "00:05:55--00:05:56",
    "content": "渠道和货价"
  },
  {
    "evidence_id": "raw-tr-000186",
    "time": "00:05:56--00:05:57",
    "content": "合习振"
  },
  {
    "evidence_id": "raw-tr-000187",
    "time": "00:05:57--00:05:58",
    "content": "反而主席的轮回小透明了"
  },
  {
    "evidence_id": "raw-tr-000188",
    "time": "00:05:58--00:06:00",
    "content": "这场持续十多年的伤战"
  },
  {
    "evidence_id": "raw-tr-000189",
    "time": "00:06:00--00:06:02",
    "content": "最终没有赢家"
  },
  {
    "evidence_id": "raw-tr-000190",
    "time": "00:06:02--00:06:04",
    "content": "加多宝丢掉了亲自招牌"
  },
  {
    "evidence_id": "raw-tr-000191",
    "time": "00:06:04--00:06:05",
    "content": "云其大昌"
  },
  {
    "evidence_id": "raw-tr-000192",
    "time": "00:06:05--00:06:06",
    "content": "王老奇虽然拿回了商标"
  },
  {
    "evidence_id": "raw-tr-000193",
    "time": "00:06:06--00:06:09",
    "content": "但已经很难复刻当年的高光时刻了"
  },
  {
    "evidence_id": "raw-tr-000194",
    "time": "00:06:09--00:06:10",
    "content": "从2013年到2025年"
  },
  {
    "evidence_id": "raw-tr-000195",
    "time": "00:06:10--00:06:12",
    "content": "三年间少卖了十个亿"
  },
  {
    "evidence_id": "raw-tr-000196",
    "time": "00:06:12--00:06:15",
    "content": "对比2011年的200亿更是直接要战"
  },
  {
    "evidence_id": "raw-tr-000197",
    "time": "00:06:15--00:06:16",
    "content": "难怪我体现了"
  },
  {
    "evidence_id": "raw-tr-000198",
    "time": "00:06:16--00:06:18",
    "content": "为什么年轻人不爱喝两茶了呢"
  },
  {
    "evidence_id": "raw-tr-000199",
    "time": "00:06:18--00:06:20",
    "content": "專於有3個"
  },
  {
    "evidence_id": "raw-tr-000200",
    "time": "00:06:20--00:06:24",
    "content": "首先是糖份抬高和健康趨勢背道而馳"
  },
  {
    "evidence_id": "raw-tr-000201",
    "time": "00:06:24--00:06:26",
    "content": "一萬480毫升的娃娃姆吉良茶"
  },
  {
    "evidence_id": "raw-tr-000202",
    "time": "00:06:26--00:06:28",
    "content": "韓唐亮有多少呢"
  },
  {
    "evidence_id": "raw-tr-000203",
    "time": "00:06:28--00:06:29",
    "content": "40克左右"
  },
  {
    "evidence_id": "raw-tr-000204",
    "time": "00:06:29--00:06:31",
    "content": "而一塊方糖大概是4克"
  },
  {
    "evidence_id": "raw-tr-000205",
    "time": "00:06:31--00:06:34",
    "content": "相當於一瓶娃娃吉裡面有10塊方糖"
  },
  {
    "evidence_id": "raw-tr-000206",
    "time": "00:06:34--00:06:34",
    "content": "你想"
  },
  {
    "evidence_id": "raw-tr-000207",
    "time": "00:06:34--00:06:35",
    "content": "現在被列店冰櫃裡面"
  },
  {
    "evidence_id": "raw-tr-000208",
    "time": "00:06:35--00:06:37",
    "content": "實行啥飲料呢"
  },
  {
    "evidence_id": "raw-tr-000209",
    "time": "00:06:37--00:06:38",
    "content": "東方說業"
  },
  {
    "evidence_id": "raw-tr-000210",
    "time": "00:06:38--00:06:39",
    "content": "3.0烏龍茶"
  },
  {
    "evidence_id": "raw-tr-000211",
    "time": "00:06:39--00:06:39",
    "content": "氣泡水"
  },
  {
    "evidence_id": "raw-tr-000212",
    "time": "00:06:39--00:06:41",
    "content": "一血的零糖零指零卡"
  },
  {
    "evidence_id": "raw-tr-000213",
    "time": "00:06:41--00:06:44",
    "content": "王老吉這個含糖量就有點各各不入了"
  },
  {
    "evidence_id": "raw-tr-000214",
    "time": "00:06:44--00:06:45",
    "content": "那為了迎合趨勢"
  },
  {
    "evidence_id": "raw-tr-000215",
    "time": "00:06:45--00:06:48",
    "content": "王老吉也退出過無糖版的原味良茶"
  },
  {
    "evidence_id": "raw-tr-000216",
    "time": "00:06:48--00:06:50",
    "content": "但是反饋是兩極分化"
  },
  {
    "evidence_id": "raw-tr-000217",
    "time": "00:06:50--00:06:51",
    "content": "有些非主材說"
  },
  {
    "evidence_id": "raw-tr-000218",
    "time": "00:06:51--00:06:53",
    "content": "沒有糖的口感喝起來苦澀"
  },
  {
    "evidence_id": "raw-tr-000219",
    "time": "00:06:53--00:06:55",
    "content": "茶要為過於濃烈了"
  },
  {
    "evidence_id": "raw-tr-000220",
    "time": "00:06:55--00:06:57",
    "content": "而且價格還更貴"
  },
  {
    "evidence_id": "raw-tr-000221",
    "time": "00:06:57--00:06:58",
    "content": "這就很嚴格了"
  },
  {
    "evidence_id": "raw-tr-000222",
    "time": "00:06:58--00:06:59",
    "content": "加糖不健康"
  },
  {
    "evidence_id": "raw-tr-000223",
    "time": "00:06:59--00:07:01",
    "content": "不加糖又太難喝了"
  },
  {
    "evidence_id": "raw-tr-000224",
    "time": "00:07:01--00:07:01",
    "content": "再來說"
  },
  {
    "evidence_id": "raw-tr-000225",
    "time": "00:07:01--00:07:02",
    "content": "這樣火這個點"
  },
  {
    "evidence_id": "raw-tr-000226",
    "time": "00:07:02--00:07:04",
    "content": "王老吉量茶的配料表裡面有橘花"
  },
  {
    "evidence_id": "raw-tr-000227",
    "time": "00:07:04--00:07:05",
    "content": "金銀花"
  },
  {
    "evidence_id": "raw-tr-000228",
    "time": "00:07:05--00:07:06",
    "content": "甘草等重要材"
  },
  {
    "evidence_id": "raw-tr-000229",
    "time": "00:07:06--00:07:09",
    "content": "這其實在中意裡確實有清熱解讀的功效"
  },
  {
    "evidence_id": "raw-tr-000230",
    "time": "00:07:09--00:07:13",
    "content": "但别忘了,它本质上是一罐加了大量白沙糖的饮料"
  },
  {
    "evidence_id": "raw-tr-000231",
    "time": "00:07:13--00:07:15",
    "content": "只望一罐高糖饮料来降火"
  },
  {
    "evidence_id": "raw-tr-000232",
    "time": "00:07:15--00:07:16",
    "content": "这如果这是不是有点魔幻"
  },
  {
    "evidence_id": "raw-tr-000233",
    "time": "00:07:16--00:07:18",
    "content": "它叫两罐的普速认知"
  },
  {
    "evidence_id": "raw-tr-000234",
    "time": "00:07:18--00:07:21",
    "content": "应该是越苦的东西,越能去热气"
  },
  {
    "evidence_id": "raw-tr-000235",
    "time": "00:07:21--00:07:23",
    "content": "比如说苦瓜和半沙两茶"
  },
  {
    "evidence_id": "raw-tr-000236",
    "time": "00:07:23--00:07:25",
    "content": "上火了你就在街边随便找一家"
  },
  {
    "evidence_id": "raw-tr-000237",
    "time": "00:07:25--00:07:26",
    "content": "黄红烧排的两茶店"
  },
  {
    "evidence_id": "raw-tr-000238",
    "time": "00:07:26--00:07:28",
    "content": "没有什么火是一瓶半沙密不了的"
  },
  {
    "evidence_id": "raw-tr-000239",
    "time": "00:07:28--00:07:30",
    "content": "如果有,那就两瓶"
  },
  {
    "evidence_id": "raw-tr-000240",
    "time": "00:07:30--00:07:33",
    "content": "两茶直接被年轻人抛弃的第二大原因是"
  },
  {
    "evidence_id": "raw-tr-000241",
    "time": "00:07:33--00:07:35",
    "content": "场景太展被火锅半律给困住了"
  },
  {
    "evidence_id": "raw-tr-000242",
    "time": "00:07:35--00:07:37",
    "content": "大家啥时候会买王老媳呢"
  },
  {
    "evidence_id": "raw-tr-000243",
    "time": "00:07:37--00:07:40",
    "content": "一般是吃火锅 烧烤等容易上火的时候"
  },
  {
    "evidence_id": "raw-tr-000244",
    "time": "00:07:40--00:07:43",
    "content": "或者是风年过节送礼 红罐包装洗几气"
  },
  {
    "evidence_id": "raw-tr-000245",
    "time": "00:07:43--00:07:45",
    "content": "名字王老祭又带个极字"
  },
  {
    "evidence_id": "raw-tr-000246",
    "time": "00:07:45--00:07:47",
    "content": "另两箱左亲气 气体面又不贵"
  },
  {
    "evidence_id": "raw-tr-000247",
    "time": "00:07:47--00:07:51",
    "content": "所以我们看到王老祭的销量其实有明显的继节性波动"
  },
  {
    "evidence_id": "raw-tr-000248",
    "time": "00:07:51--00:07:53",
    "content": "在2023年才爆里面提到了这一点"
  },
  {
    "evidence_id": "raw-tr-000249",
    "time": "00:07:53--00:07:56",
    "content": "天气颜色时销量会有所增长"
  },
  {
    "evidence_id": "raw-tr-000250",
    "time": "00:07:56--00:07:58",
    "content": "同时重大节日销量较大"
  },
  {
    "evidence_id": "raw-tr-000251",
    "time": "00:07:58--00:08:01",
    "content": "翻译过来就是夏天靠气温 冬天靠送礼"
  },
  {
    "evidence_id": "raw-tr-000252",
    "time": "00:08:01--00:08:05",
    "content": "但问题是 这两个场景都在被其他品牌分流"
  },
  {
    "evidence_id": "raw-tr-000253",
    "time": "00:08:05--00:08:08",
    "content": "去吃火锅吧 酸梅汤 叶汁 洞奶 多能喝"
  },
  {
    "evidence_id": "raw-tr-000254",
    "time": "00:08:08--00:08:10",
    "content": "王老师并不是必选项"
  },
  {
    "evidence_id": "raw-tr-000255",
    "time": "00:08:10--00:08:11",
    "content": "再来看李品市场"
  },
  {
    "evidence_id": "raw-tr-000256",
    "time": "00:08:11--00:08:14",
    "content": "现在年货李品的选择也越来越多了"
  },
  {
    "evidence_id": "raw-tr-000257",
    "time": "00:08:14--00:08:18",
    "content": "什么牛奶里和 鸡锅里和 高端水果都在分是这款蛋糕"
  },
  {
    "evidence_id": "raw-tr-000258",
    "time": "00:08:18--00:08:19",
    "content": "王老师现在越来越少人喝"
  },
  {
    "evidence_id": "raw-tr-000259",
    "time": "00:08:19--00:08:22",
    "content": "还有第三代原因是品牌老化"
  },
  {
    "evidence_id": "raw-tr-000260",
    "time": "00:08:22--00:08:23",
    "content": "产品创新不足"
  },
  {
    "evidence_id": "raw-tr-000261",
    "time": "00:08:23--00:08:24",
    "content": "再过去十几年时间里"
  },
  {
    "evidence_id": "raw-tr-000262",
    "time": "00:08:24--00:08:27",
    "content": "品牙市场是发生了翻天腹地的变化"
  },
  {
    "evidence_id": "raw-tr-000263",
    "time": "00:08:27--00:08:28",
    "content": "什么淋汤淋卡 股电解细"
  },
  {
    "evidence_id": "raw-tr-000264",
    "time": "00:08:28--00:08:30",
    "content": "不淡白 提升新脑各种"
  },
  {
    "evidence_id": "raw-tr-000265",
    "time": "00:08:30--00:08:31",
    "content": "概念是层数不穷"
  },
  {
    "evidence_id": "raw-tr-000266",
    "time": "00:08:31--00:08:32",
    "content": "反光王老师呢"
  },
  {
    "evidence_id": "raw-tr-000267",
    "time": "00:08:32--00:08:36",
    "content": "大家熟知的包装和口味基本是没怎么变国的"
  },
  {
    "evidence_id": "raw-tr-000268",
    "time": "00:08:36--00:08:38",
    "content": "王老奇自己也不是没努力过"
  },
  {
    "evidence_id": "raw-tr-000269",
    "time": "00:08:38--00:08:39",
    "content": "但好像越努力越新酸"
  },
  {
    "evidence_id": "raw-tr-000270",
    "time": "00:08:39--00:08:42",
    "content": "2015年他关名了奔跑814"
  },
  {
    "evidence_id": "raw-tr-000271",
    "time": "00:08:42--00:08:44",
    "content": "剧署网过名费高达1.3亿元"
  },
  {
    "evidence_id": "raw-tr-000272",
    "time": "00:08:44--00:08:47",
    "content": "还成了歌手2016的超级合作伙伴"
  },
  {
    "evidence_id": "raw-tr-000273",
    "time": "00:08:47--00:08:49",
    "content": "前脚签下佔领后后脚又光轩哈岚的"
  },
  {
    "evidence_id": "raw-tr-000274",
    "time": "00:08:49--00:08:51",
    "content": "影响酸酱确实很大"
  },
  {
    "evidence_id": "raw-tr-000275",
    "time": "00:08:51--00:08:54",
    "content": "但产品销量几乎是原地踏步"
  },
  {
    "evidence_id": "raw-tr-000276",
    "time": "00:08:54--00:08:55",
    "content": "2015年王老奇大健康公司"
  },
  {
    "evidence_id": "raw-tr-000277",
    "time": "00:08:55--00:08:57",
    "content": "应收87.86亿元"
  },
  {
    "evidence_id": "raw-tr-000278",
    "time": "00:08:57--00:09:00",
    "content": "同比只威增了0.23%"
  },
  {
    "evidence_id": "raw-tr-000279",
    "time": "00:09:00--00:09:02",
    "content": "王老奇还尝试过口味创新"
  },
  {
    "evidence_id": "raw-tr-000280",
    "time": "00:09:02--00:09:04",
    "content": "这几年退出了一大堆列机口味"
  },
  {
    "evidence_id": "raw-tr-000281",
    "time": "00:09:04--00:09:05",
    "content": "哲俄更味"
  },
  {
    "evidence_id": "raw-tr-000282",
    "time": "00:09:05--00:09:07",
    "content": "腾胶清体味"
  },
  {
    "evidence_id": "raw-tr-000283",
    "time": "00:09:07--00:09:08",
    "content": "霸气流灵味"
  },
  {
    "evidence_id": "raw-tr-000284",
    "time": "00:09:08--00:09:09",
    "content": "拼命紫就很业绩"
  },
  {
    "evidence_id": "raw-tr-000285",
    "time": "00:09:09--00:09:10",
    "content": "但在试试的评价上一搜"
  },
  {
    "evidence_id": "raw-tr-000286",
    "time": "00:09:10--00:09:11",
    "content": "黑洋料理"
  },
  {
    "evidence_id": "raw-tr-000287",
    "time": "00:09:11--00:09:13",
    "content": "南赫的吐槽是不在少数"
  },
  {
    "evidence_id": "raw-tr-000288",
    "time": "00:09:13--00:09:13",
    "content": "比如说"
  },
  {
    "evidence_id": "raw-tr-000289",
    "time": "00:09:13--00:09:15",
    "content": "有人评价哲俄更味"
  },
  {
    "evidence_id": "raw-tr-000290",
    "time": "00:09:15--00:09:18",
    "content": "居然向南策所小便吃清潔球"
  },
  {
    "evidence_id": "raw-tr-000291",
    "time": "00:09:18--00:09:19",
    "content": "反正推出那么多新品之后"
  },
  {
    "evidence_id": "raw-tr-000292",
    "time": "00:09:19--00:09:20",
    "content": "最能打的"
  },
  {
    "evidence_id": "raw-tr-000293",
    "time": "00:09:20--00:09:21",
    "content": "还是那罐"
  },
  {
    "evidence_id": "raw-tr-000294",
    "time": "00:09:21--00:09:22",
    "content": "经典红罐"
  },
  {
    "evidence_id": "raw-tr-000295",
    "time": "00:09:22--00:09:23",
    "content": "其实王老奇的困境"
  },
  {
    "evidence_id": "raw-tr-000296",
    "time": "00:09:23--00:09:26",
    "content": "也是整个传统饮料行业的所以"
  },
  {
    "evidence_id": "raw-tr-000297",
    "time": "00:09:26--00:09:26",
    "content": "过去十年"
  },
  {
    "evidence_id": "raw-tr-000298",
    "time": "00:09:26--00:09:28",
    "content": "中国饮料市场发生了非常大的变化"
  },
  {
    "evidence_id": "raw-tr-000299",
    "time": "00:09:28--00:09:30",
    "content": "无摊查市场规模"
  },
  {
    "evidence_id": "raw-tr-000300",
    "time": "00:09:30--00:09:31",
    "content": "五年翻了7倍多"
  },
  {
    "evidence_id": "raw-tr-000301",
    "time": "00:09:31--00:09:33",
    "content": "東方水源們是殺風了"
  },
  {
    "evidence_id": "raw-tr-000302",
    "time": "00:09:33--00:09:34",
    "content": "另一方面"
  },
  {
    "evidence_id": "raw-tr-000303",
    "time": "00:09:34--00:09:35",
    "content": "過能飲料也在崛起"
  },
  {
    "evidence_id": "raw-tr-000304",
    "time": "00:09:35--00:09:37",
    "content": "市場規模突破2,000億"
  },
  {
    "evidence_id": "raw-tr-000305",
    "time": "00:09:37--00:09:39",
    "content": "電解置水成為民心產品"
  },
  {
    "evidence_id": "raw-tr-000306",
    "time": "00:09:39--00:09:40",
    "content": "而兩岔這邊"
  },
  {
    "evidence_id": "raw-tr-000307",
    "time": "00:09:40--00:09:41",
    "content": "不只是王老基"
  },
  {
    "evidence_id": "raw-tr-000308",
    "time": "00:09:41--00:09:43",
    "content": "整個品類都在踩沙車"
  },
  {
    "evidence_id": "raw-tr-000309",
    "time": "00:09:43--00:09:45",
    "content": "前瞻產業就願允許於顯示"
  },
  {
    "evidence_id": "raw-tr-000310",
    "time": "00:09:45--00:09:46",
    "content": "2002年到2017年"
  },
  {
    "evidence_id": "raw-tr-000311",
    "time": "00:09:46--00:09:49",
    "content": "兩岔市場增速是逐年下滑"
  },
  {
    "evidence_id": "raw-tr-000312",
    "time": "00:09:49--00:09:50",
    "content": "回過頭來看"
  },
  {
    "evidence_id": "raw-tr-000313",
    "time": "00:09:50--00:09:52",
    "content": "王老基和加多保真的十幾年"
  },
  {
    "evidence_id": "raw-tr-000314",
    "time": "00:09:52--00:09:53",
    "content": "真的是一個名字"
  },
  {
    "evidence_id": "raw-tr-000315",
    "time": "00:09:53--00:09:56",
    "content": "一隻紅貫和過去積累的消費者認知"
  },
  {
    "evidence_id": "raw-tr-000316",
    "time": "00:09:56--00:09:58",
    "content": "但就在他們為了舊賬死科的時候"
  },
  {
    "evidence_id": "raw-tr-000317",
    "time": "00:09:58--00:10:00",
    "content": "消费者已经翻篇了"
  },
  {
    "evidence_id": "raw-tr-000318",
    "time": "00:10:00--00:10:01",
    "content": "开始问"
  },
  {
    "evidence_id": "raw-tr-000319",
    "time": "00:10:01--00:10:03",
    "content": "为什么还要喝一罐高糖凉茶呢?"
  },
  {
    "evidence_id": "raw-tr-000320",
    "time": "00:10:03--00:10:06",
    "content": "这才是山爷世界最让人吸叙的地方"
  },
  {
    "evidence_id": "raw-tr-000321",
    "time": "00:10:06--00:10:07",
    "content": "拧平进权力"
  },
  {
    "evidence_id": "raw-tr-000322",
    "time": "00:10:07--00:10:08",
    "content": "用进手段去跟对手绝"
  },
  {
    "evidence_id": "raw-tr-000323",
    "time": "00:10:08--00:10:09",
    "content": "一台都却发现"
  },
  {
    "evidence_id": "raw-tr-000324",
    "time": "00:10:09--00:10:11",
    "content": "系统已经敲销晃的地图了"
  },
  {
    "evidence_id": "raw-tr-000325",
    "time": "00:10:11--00:10:12",
    "content": "以前的逼杀剂"
  },
  {
    "evidence_id": "raw-tr-000326",
    "time": "00:10:12--00:10:13",
    "content": "在新版本里面"
  },
  {
    "evidence_id": "raw-tr-000327",
    "time": "00:10:13--00:10:15",
    "content": "成了一堆棉花"
  },
  {
    "evidence_id": "raw-tr-000328",
    "time": "00:10:15--00:10:15",
    "content": "再见我们"
  },
  {
    "evidence_id": "raw-tr-000329",
    "time": "00:10:15--00:10:16",
    "content": "不想转案前"
  },
  {
    "evidence_id": "raw-tr-000330",
    "time": "00:10:16--00:10:17",
    "content": "我是阿娜讲"
  },
  {
    "evidence_id": "raw-tr-000331",
    "time": "00:10:17--00:10:18",
    "content": "上门试明圈面容"
  },
  {
    "evidence_id": "raw-tr-000332",
    "time": "00:10:18--00:10:19",
    "content": "接点赞 关注"
  },
  {
    "evidence_id": "raw-tr-000333",
    "time": "00:10:19--00:10:19",
    "content": "我们现在先"
  }
]