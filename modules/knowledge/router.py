"""知识域语义路由 + 多轮 Query 改写（knowledge-base 能力）。

- 语义路由：用 LLM 判断问题所属知识域（工艺类 / 制度类 / 知识类，与知识管理入库类型一致），
  无法判断返回 None（回落全库检索）。
- Query 改写：多轮对话中把含指代的追问（如「它呢」）改写为完整独立查询。
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from .loaders import DOMAIN_NAMES


def _llm(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=temperature,
    )


def route_domain(question: str, llm: ChatOpenAI | None = None) -> str | None:
    """判断问题所属知识域，返回 None 表示无法判断（回落全库）。

    注意：这里的 None 仅表示「不在任何已知域内」，是否离题由 is_offtopic 单独判定。
    """
    llm = llm or _llm()
    domain_list = "、".join(DOMAIN_NAMES)
    prompt = (
        f"你是知识库路由分类器。判断下面的问题属于哪个知识域：{domain_list}。\n"
        "规则：涉及产品结构/材质/规格/加工工艺/具体操作步骤/作业规范的归「工艺类」；"
        "涉及国标/行标/标准编号/行业规范的归「知识类」；"
        "涉及考勤/请假/报销/薪酬/考核/岗位职责/离职/人事行政规章的归「制度类」。\n"
        "如果都不属于或无法判断，回答「全库」。只输出一个词，不要解释。\n\n"
        f"问题：{question}"
    )
    resp = llm.invoke(prompt)
    label = (resp.content or "").strip()
    if label in DOMAIN_NAMES:
        return label
    return None


# 知识库强相关关键词：命中即视为「相关」，跳过 LLM 离题判定。
# 目的：离题判定依赖 LLM 输出「离题」二字，判定不稳定（曾把「美重和含钛的配件有什么区别」
# 这种明确工艺类问题误判成离题），故先做确定性前置，凡含产品/工艺/制度术语的一律放行。
_KB_KEYWORDS = (
    "管钳", "钳", "钳口", "钳体", "钳把", "钳头", "齿", "齿块", "铣齿", "车丝", "铣丝",
    "焊接", "钎焊", "镀", "发蓝", "镀彩", "金刚石", "热处理", "抛丸", "磨毛刺",
    "加力", "美重", "美式", "含钛", "内管", "钻杆", "套管", "自由钳", "铸铁",
    "规格", "型号", "BOM", "配件", "毛坯", "覆膜砂", "借用", "通配", "工艺",
    "工序", "作业", "标准", "钢材", "材料", "螺母", "板簧", "压簧", "固定帽", "把手",
    "考勤", "请假", "报销", "薪酬", "考核", "岗位", "离职", "制度", "人事",
    # 知识类 / 品牌经营类（本次补：避免「品牌建设」等新知识内容被离题误杀）
    "品牌", "建设", "推广", "市场", "商标", "专利", "营销", "销售", "外贸", "出口",
    "企业", "公司", "文化", "发展", "历程", "荣誉", "资质", "认证", "行业", "术语",
    "原理", "科普", "手册", "指南", "国标", "行标",
)


def is_offtopic(question: str, llm: ChatOpenAI | None = None) -> bool:
    """判断问题是否完全离题（与本知识库范围无关，如天气/股票/闲聊）。

    离题问题不检索、不引用，直接短路拒绝，避免「找不到」时还附带无关引用。

    双层防护（防误杀）：
    1. 确定性前置：问题含产品/工艺/制度关键词 → 直接判「相关」，不调 LLM；
    2. LLM 宽松判定：拿不准时判「相关」，只有明显无关（天气/股票/娱乐/其它公司业务）才判离题。
    """
    # 第一层：确定性关键词前置，命中即放行（不依赖 LLM，杜绝判定飘移误杀）
    if any(k in question for k in _KB_KEYWORDS):
        return False

    llm = llm or _llm()
    prompt = (
        "你是一个知识库守门员。这个知识库只包含三类内容：\n"
        "1) 管钳/自由钳产品的生产工艺、作业指导书、行业标准（工艺类）；\n"
        "2) 宏润机具的公司制度（考勤/请假/报销/薪酬/考核/岗位职责/离职/人事行政）（制度类）；\n"
        "3) 通用知识（行业标准、术语、技术原理、品牌建设、市场推广、商标专利、企业概况等）（知识类）。\n"
        "判断下面的问题是否与上述内容完全无关（例如天气、新闻、股票、娱乐、通用闲聊、其它公司业务等）。\n"
        "判定原则（重要）：宁可放行、不可误杀——只要问题可能与管钳生产、机加工、五金工具、"
        "制造业、公司经营或品牌市场沾边，就判「相关」；只有明确无关的闲聊/八卦/其它行业才判「离题」。\n"
        "只输出「相关」或「离题」，不要解释。\n\n"
        f"问题：{question}"
    )
    resp = llm.invoke(prompt)
    return (resp.content or "").strip() == "离题"


def rewrite_query(question: str, history: list[dict] | None, llm: ChatOpenAI | None = None) -> str:
    """多轮 Query 改写：把含指代的追问改写为完整独立查询。无历史时原样返回。"""
    if not history:
        return question
    llm = llm or _llm()
    conv = "\n".join(f"{h.get('role', 'user')}: {h.get('content', '')}" for h in history[-6:])
    prompt = (
        "你负责把用户的多轮对话追问改写成一句完整、独立、不含指代（如「它/这个/那个」）的查询。\n"
        "若当前问题本身已完整独立，原样返回。只输出改写后的查询，不要解释。\n\n"
        f"对话历史：\n{conv}\n\n当前追问：{question}"
    )
    resp = llm.invoke(prompt)
    return (resp.content or "").strip() or question
