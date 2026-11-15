# 农产品报价归集与可比成本分析平台

面向食堂采购员：把各来源报价（供应商箱价、市场公斤价、带泥毛菜/净菜、不同起订量与费用规则）换算成**相同等级、相同加工状态、相同可用数量口径下的可比成本**，并支持采用、验收与偏差归因的全流程留痕。

- 后端：Python 3.12 + FastAPI + SQLAlchemy + PostgreSQL
- 前端：Vue 3 + Vite + Element Plus
- 不做图片识别、不访问真实商家；只接收随题 CSV / JSON / 结构化市场快照文件

## 一键启动（Docker Compose）

```bash
docker compose up --build
```

- 前端：http://localhost:8080
- 后端 API：http://localhost:8000 （接口文档 `/api/docs`）
- 首次启动自动建表并导入 `samples/` 下的演示数据（含演示采购依据与验收记录）

## 本地开发启动

前置：PostgreSQL（`127.0.0.1:5432`，库/用户/密码均为 `ccdev`）、Python 3.12、Node 22。

```bash
# 后端（首次会自动建表；种子数据需执行一次导入）
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -c "from app.database import Base, engine, SessionLocal; from app.main import app; from app.seed import seed_if_empty; Base.metadata.create_all(bind=engine); seed_if_empty(SessionLocal())"
.venv/bin/uvicorn app.main:app --reload --port 8000

# 前端（另开终端，已配置 /api 代理到 8000）
cd frontend
npm install
npm run dev        # http://localhost:5173
```

## 测试账号

| 账号 | 密码 | 角色 | 能做什么 |
| --- | --- | --- | --- |
| `admin` | `admin123` | 管理员 | 全部操作 |
| `buyer01` | `buyer123` | 采购员 | 导入、映射审核、对比、采用报价、更正 |
| `checker01` | `check123` | 验收员 | 验收登记 |

## 本题验证方式（页面操作路径）

种子数据已覆盖题目要求的四类样例，计算均为真实运行：

1. **整箱舍入 + 阶梯运费**：「成本对比」选 土豆 / 可用净重 / 100kg → 宏发箱装报价按出成率下界 0.78 反推需 7 箱（预计可用 109.2~119kg，保守余量 9.2kg），147kg 计费重量命中 100–300kg 档（0.3 元/kg 全量计，不累计）。
2. **同名异等级**：土豆同时存在一级/二级报价；页面可按等级筛选，筛选条件严格生效（不为补齐报价而取消）。
3. **最低标价 ≠ 最低使用成本**：宏发一级箱装毛重单价最低（1.75 元/kg），计入出成率与运费后可用成本 [2.49, 2.71] 元/kg，反高于绿源净菜 2.289 元/kg；区间重叠的报价标注「不排名次」。
4. **到货后可用率降低**：「采购依据」#1（种子演示）已登记验收——单价 35→36、短装 12kg、实测出成率 0.74（低于计划下界 0.78）；「偏差归因」按 单价→数量→出成率 固定顺序逐步替换，各步贡献之和 = 总差额。

其他可验证点：

- **待核队列**：缺等级、缺单位、税费未声明、零价无依据、商品名未映射的报价进「报价与待核」，不参与最低价排名；映射审核通过后（如「洋芋→土豆」）才归集。
- **坏行单列**：`samples/quotes_supplier_a.csv` 第 9 行缺单价 → 「导入管理」批次明细中列为坏行，不悄悄丢失；同文件重复导入幂等，中断可续接。
- **重解析试算**：批次上「重解析试算」改列名表/单位表生成新修订批次，只试算、不动实时报价链；已选采购仍指向旧依据，报价详情可发起「采用新修订并更正」。
- **零价**：宏发西红柿 0 元有「新品推广试吃装」依据可正常对比；绿源胡萝卜 0 元无依据 → 待核。
- **市场参考价**：「市场参考价」土豆/一级/净菜 → 张记(2.45)、李记(2.2) 两家独立卖方归并后中位数 2.325；王五、赵六为转载，不增加权重。
- **过期与起订量**：Q-A-005 已过期、宏发大白菜起订 20 筐，分别在「不可采用报价」中说明原因。

## 自动化测试

```bash
cd backend
.venv/bin/python -m pytest tests/ -q     # 35 个用例：换算引擎/差额归因/导入续接/市场参考/API 流程
```

前端构建验证：`cd frontend && npm run build`。

## 关键业务规则（与实现对应）

| 规则 | 实现位置 |
| --- | --- |
| 整箱向上取整；净重需求按出成率下界反推保守采购量 | `backend/app/calc.py::plan_quote` |
| 运费按计重区间只应用匹配一档 + 起送费 | `calc.py::calc_freight` |
| 税费未含加计一次、已含不重复、缺失转待核 | `calc.py::cost_totals`、`importer.py::validate_quote_fields` |
| 出成率区间 → 成本区间；缺测展示原价不猜净菜率 | `calc.py::plan_quote` |
| 区间重叠不强制排名 | `calc.py::assign_overlap_groups` |
| 差额按 单价→数量→出成率 固定顺序归因，贡献和=总差额，不称唯一原因 | `backend/app/deviation.py` |
| 采购依据只读、快照固化；映射修订/重解析不影响旧依据 | `backend/app/services.py` |
| 短装/退货/等级拒收分列；未验收部分不提前算损耗 | `services.py::summarize_acceptances` |
| 市场参考价按独立卖方归并取中位数、转载去重 | `backend/app/market.py` |
| 坏行单列、按原文件续接、同号换值保留修订 | `backend/app/importer.py` |

## 目录结构

```
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── calc.py         # 可比成本换算引擎
│   │   ├── deviation.py    # 差额归因（连环替代）
│   │   ├── importer.py     # CSV/JSON/快照导入、续接、重解析
│   │   ├── market.py       # 市场参考价
│   │   ├── services.py     # 对比/采购依据/验收汇总
│   │   └── routers/        # API 路由
│   └── tests/              # pytest（35 用例）
├── frontend/             # Vue3 + Element Plus
├── samples/              # 随题样例：供应商CSV、净菜JSON、市场快照
└── docker-compose.yml
```

## 验证结论（实际执行过的验证）

- `pytest`：35/35 通过（换算引擎、差额归因一致性、导入坏行/续接/同号换值/重解析试算、市场中位数去转载、API 决策-验收-偏差全流程）。
- `npm run build`：构建成功。
- 本地联调：后端 uvicorn + 前端 vite 代理下，完成 登录→对比→采用→验收→偏差→映射审核→导入→重解析→更正 全旅程验证（见上「本题验证方式」各条数据均来自真实接口返回）。
- 本环境无 docker，`docker compose` 未实际执行；Compose 中各服务的启动命令与本地已验证命令一致（uvicorn 启动后端、vite 构建 + nginx 托管并代理 /api）。
