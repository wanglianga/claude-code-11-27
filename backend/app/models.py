"""数据模型：报价归集与可比成本分析平台。

设计要点：
- Quote 保留来源、原行(raw)、全部规格与费用规则，按 revision 保留同号换值历史；
- PurchaseDecision 生成后只读，snapshot 固化当时换算依据，映射修订/重解析不影响它；
- Acceptance 按车次登记，短装/退货/等级拒收分列，未验收部分不计损耗。
"""
from datetime import datetime

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, Float,
                        ForeignKey, Integer, String, Text)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password = Column(String(128), nullable=False)
    display_name = Column(String(64), nullable=False)
    role = Column(String(16), nullable=False)  # admin / buyer / checker
    created_at = Column(DateTime, default=datetime.utcnow)


class StandardProduct(Base):
    __tablename__ = "standard_products"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    category = Column(String(64), default="蔬菜")
    base_unit = Column(String(16), default="kg")
    note = Column(String(256))

    yield_rates = relationship("YieldRate", back_populates="product")


class YieldRate(Base):
    """出成率（有依据的区间）；缺测则不建记录，前端展示原价而不猜净菜率。"""

    __tablename__ = "yield_rates"

    id = Column(Integer, primary_key=True)
    product_id = Column(ForeignKey("standard_products.id"), nullable=False)
    from_state = Column(String(32), nullable=False)  # 报价加工状态，如 带泥毛菜
    to_state = Column(String(32), nullable=False, default="净菜")
    lower = Column(Float, nullable=False)
    upper = Column(Float, nullable=False)
    evidence = Column(String(256))  # 依据，如实测批次
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("StandardProduct", back_populates="yield_rates")


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True)
    filename = Column(String(256))
    file_hash = Column(String(64), index=True)
    kind = Column(String(16))  # csv / json / snapshot
    status = Column(String(16), default="processing")  # processing/partial/completed/failed
    total_rows = Column(Integer, default=0)
    ok_rows = Column(Integer, default=0)
    bad_rows = Column(Integer, default=0)
    column_mapping = Column(JSON)  # 文件列名 -> 标准字段
    unit_table = Column(JSON)  # 单位字面值 -> box/kg
    revision = Column(Integer, default=1)  # 重解析试算递增
    parent_batch_id = Column(Integer, ForeignKey("import_batches.id"), nullable=True)
    file_content = Column(Text)  # 原始文件内容，供续接与重解析
    created_at = Column(DateTime, default=datetime.utcnow)

    rows = relationship("ImportRow", back_populates="batch")


class ImportRow(Base):
    """逐行处理结果：坏行单列，续接时跳过已 ok 的行。"""

    __tablename__ = "import_rows"

    id = Column(Integer, primary_key=True)
    batch_id = Column(ForeignKey("import_batches.id"), nullable=False)
    row_no = Column(Integer, nullable=False)
    status = Column(String(8), nullable=False)  # ok / bad
    raw = Column(JSON)
    error = Column(String(512))
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=True)

    batch = relationship("ImportBatch", back_populates="rows")


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True)
    batch_id = Column(ForeignKey("import_batches.id"), nullable=False)
    row_no = Column(Integer)
    external_id = Column(String(64))  # 报价编号（同号换值时递增 revision）
    revision = Column(Integer, default=1)
    supersedes_id = Column(Integer, nullable=True)
    is_latest = Column(Boolean, default=True, index=True)
    source_name = Column(String(128))
    source_type = Column(String(16), default="supplier")  # supplier / market
    raw = Column(JSON)  # 原始行，溯源用
    raw_product_name = Column(String(128))
    product_id = Column(ForeignKey("standard_products.id"), nullable=True)
    mapping_status = Column(String(16), default="pending")  # mapped / pending
    mapping_candidates = Column(JSON)  # 名称相似只给候选，不自动归并
    grade = Column(String(32))  # 等级，缺 -> 待核
    origin = Column(String(64))  # 产地
    package_desc = Column(String(64))
    unit = Column(String(16))  # box / kg / None(缺单位 -> 待核)
    unit_raw = Column(String(16))
    net_weight_per_unit_kg = Column(Float)  # 包装净重
    gross_weight_per_unit_kg = Column(Float)
    processing_status = Column(String(32))  # 加工状态：带泥毛菜/净菜...
    price_per_unit = Column(Float)
    tax_included = Column(Boolean)  # 税费是否已含；NULL -> 待补
    tax_rate = Column(Float)
    valid_from = Column(Date)
    valid_to = Column(Date)
    moq_quantity = Column(Float)  # 起订量
    moq_unit = Column(String(16))
    delivery_mode = Column(String(16))  # 配送 / 自提
    lead_days = Column(Integer, default=0)  # 0=当天，1=隔日
    fee_rules = Column(JSON)  # {"freight": {...}, "alloc_fees": [...]}
    zero_price_basis = Column(String(256))  # 零价免费依据
    review_status = Column(String(16), default="ok")  # ok / pending(待核)
    pending_reasons = Column(JSON, default=list)
    terms_hash = Column(String(64))  # 关键条款哈希，确认时校验
    parse_revision = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class NameMapping(Base):
    __tablename__ = "name_mappings"

    id = Column(Integer, primary_key=True)
    raw_name = Column(String(128), unique=True, nullable=False)
    product_id = Column(ForeignKey("standard_products.id"), nullable=True)
    status = Column(String(16), default="pending")  # pending / approved / rejected
    candidates = Column(JSON)
    revision = Column(Integer, default=1)
    note = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)
    reviewed_by = Column(String(64))


class PurchaseDecision(Base):
    """采购依据：生成后只读；更正通过 correct 生成新 revision。"""

    __tablename__ = "purchase_decisions"

    id = Column(Integer, primary_key=True)
    quote_id = Column(ForeignKey("quotes.id"), nullable=False)
    product_id = Column(ForeignKey("standard_products.id"), nullable=False)
    need_type = Column(String(8), nullable=False)  # gross / net
    need_quantity = Column(Float, nullable=False)
    units = Column(Float, nullable=False)  # 实际采购件数（箱）
    snapshot = Column(JSON)  # 固化换算依据与条款
    terms_hash = Column(String(64))
    status = Column(String(16), default="active")  # active / superseded
    revision = Column(Integer, default=1)
    corrects_id = Column(Integer, ForeignKey("purchase_decisions.id"), nullable=True)
    created_by = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)

    acceptances = relationship("Acceptance", back_populates="decision")


class Acceptance(Base):
    """验收：关联实际车次与原订单；短装/退货/等级拒收分开登记。"""

    __tablename__ = "acceptances"

    id = Column(Integer, primary_key=True)
    decision_id = Column(ForeignKey("purchase_decisions.id"), nullable=False)
    trip_no = Column(String(64), nullable=False)  # 车次
    received_weight_kg = Column(Float, nullable=False)  # 实际到货毛重
    actual_unit_price = Column(Float)  # 实际结算单价
    actual_grade = Column(String(32))
    returned_weight_kg = Column(Float, default=0)  # 退货
    grade_rejected_weight_kg = Column(Float, default=0)  # 等级拒收
    actual_yield = Column(Float)  # 实际出成率（可空，未实测不猜）
    note = Column(String(512))
    created_by = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)

    decision = relationship("PurchaseDecision", back_populates="acceptances")


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True)
    batch_id = Column(ForeignKey("import_batches.id"), nullable=False)
    seller = Column(String(128), nullable=False)  # 独立卖方
    raw_product_name = Column(String(128))
    product_id = Column(ForeignKey("standard_products.id"), nullable=True)
    grade = Column(String(32))
    processing_status = Column(String(32))
    price_per_kg = Column(Float, nullable=False)
    captured_at = Column(Date, nullable=False)
    source_name = Column(String(128))  # 采集来源
    repost_of = Column(Integer, nullable=True)  # 转载来源快照 id，转载不增权重
    created_at = Column(DateTime, default=datetime.utcnow)
