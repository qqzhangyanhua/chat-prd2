from __future__ import annotations


CONFIRM_CONTINUE_COMMAND = "确认，继续下一步"


CONFIRM_FOCUS_COMMANDS = {
    CONFIRM_CONTINUE_COMMAND: {
        "phase_goal": "明确首轮验证优先级",
        "stage_hint": "推进验证优先级",
        "strategy_reason": "当前共识已锁定，下一步进入首轮验证优先级收敛。",
        "recommendation": {
            "label": "先锁定首轮验证项",
            "content": "先在频率、付费意愿、转化阻力里选一个最优先验证项",
            "rationale": "先锁定验证目标，后续访谈和方案取舍才不会发散",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先锁定首轮验证项",
                "content": "先在频率、付费意愿、转化阻力里选一个最优先验证项",
                "rationale": "先锁定验证目标，后续访谈和方案取舍才不会发散",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "优先验证频率",
                "content": "先判断这个问题是否足够高频",
                "rationale": "频率不成立，后续价值和付费判断都会失真",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "再决定验证付费还是转化阻力",
                "content": "在频率成立后，再判断用户是否愿意付费或卡在哪一步",
                "rationale": "先后顺序更稳定，验证成本更低",
                "priority": 3,
            },
        ],
        "next_best_questions": [
            "为了继续推进，请直接回答你现在最想先验证的是频率、付费意愿，还是转化阻力？"
        ],
        "reply_lines": [
            "下一步我会把讨论推进到“首轮验证优先级”，先判断你现在最该优先验证哪一项。",
            "如果你还没明确顺序，我更建议先看“频率”是否成立，因为它最先决定这个问题值不值得继续深挖。",
            "请你直接告诉我当前最想先验证的是频率、付费意愿，还是转化阻力。",
        ],
    },
    "确认，先看频率": {
        "phase_goal": "明确问题发生频率是否足够高",
        "stage_hint": "推进频率验证",
        "strategy_reason": "当前共识已锁定，下一步进入频率验证。",
        "recommendation": {
            "label": "先验证问题频率",
            "content": "先判断这个问题是否高频到值得优先解决",
            "rationale": "低频问题通常不值得优先投入 MVP",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先验证问题频率",
                "content": "先判断这个问题是否高频到值得优先解决",
                "rationale": "低频问题通常不值得优先投入 MVP",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "补一条最近发生的真实案例",
                "content": "先说明最近一次发生在什么场景、谁触发、结果如何",
                "rationale": "真实案例比抽象判断更能校准频率",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "区分偶发痛点和高频痛点",
                "content": "先分清这是偶发抱怨还是反复发生的问题",
                "rationale": "频率会直接影响产品优先级",
                "priority": 3,
            },
        ],
        "next_best_questions": [
            "为了继续推进，请直接补一句这个问题平均多久发生一次，最好带上最近一次真实场景。"
        ],
        "reply_lines": [
            "下一步我会先把讨论推进到“频率验证”，先判断这个问题是不是高频到值得优先做。",
            "如果频率站不住，后面再谈付费和转化都会偏早。",
            "请你直接告诉我这个问题平均多久发生一次，最好顺手带上最近一次真实场景。",
        ],
    },
    "确认，先看付费意愿": {
        "phase_goal": "明确付费意愿是否成立",
        "stage_hint": "推进付费意愿验证",
        "strategy_reason": "当前共识已锁定，下一步进入付费意愿验证。",
        "recommendation": {
            "label": "先验证付费意愿",
            "content": "先判断用户有没有为这类结果付费的真实动机",
            "rationale": "没有付费意愿，再顺畅的方案也很难成立为业务",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先验证付费意愿",
                "content": "先判断用户有没有为这类结果付费的真实动机",
                "rationale": "没有付费意愿，再顺畅的方案也很难成立为业务",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "先找现有替代方案价格锚点",
                "content": "先看用户现在是否已经在为其他替代方案买单",
                "rationale": "已有支付行为比口头意愿更可靠",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "区分愿意花钱和愿意花时间",
                "content": "先判断用户到底更愿意付钱还是自己折腾",
                "rationale": "这会直接决定后续商业模式方向",
                "priority": 3,
            },
        ],
        "next_best_questions": [
            "为了继续推进，请直接回答这类用户现在有没有为替代方案付费，或者愿不愿意为更好结果付费。"
        ],
        "reply_lines": [
            "下一步我会先把讨论推进到“付费意愿验证”，先判断这是不是一个用户愿意掏钱解决的问题。",
            "如果用户只觉得麻烦但不愿付费，产品价值和商业化路径都要重算。",
            "请你直接告诉我这类用户现在有没有为替代方案付费，或者愿不愿意为更好结果付费。",
        ],
    },
    "确认，先看转化阻力": {
        "phase_goal": "明确转化阻力集中在哪一环",
        "stage_hint": "推进转化阻力验证",
        "strategy_reason": "当前共识已锁定，下一步进入转化阻力验证。",
        "recommendation": {
            "label": "先验证转化阻力",
            "content": "先判断用户会卡在理解、接入还是结果稳定性",
            "rationale": "不先识别转化阻力，MVP 很容易做成却没人持续使用",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先验证转化阻力",
                "content": "先判断用户会卡在理解、接入还是结果稳定性",
                "rationale": "不先识别转化阻力，MVP 很容易做成却没人持续使用",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "先找最容易流失的一步",
                "content": "先指出用户最可能在哪一步退出",
                "rationale": "最薄弱的一环通常决定整体转化",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "区分理解成本和接入成本",
                "content": "先判断是看不懂，还是用起来太麻烦",
                "rationale": "不同阻力决定完全不同的产品打法",
                "priority": 3,
            },
        ],
        "next_best_questions": [
            "为了继续推进，请直接回答用户现在最容易卡在哪一步，是理解成本、接入成本，还是结果不够稳定。"
        ],
        "reply_lines": [
            "下一步我会先把讨论推进到“转化阻力验证”，先判断用户最可能卡在哪一步。",
            "如果不先识别阻力点，后面功能越堆越多，反而更难形成转化闭环。",
            "请你直接告诉我用户现在最容易卡在哪一步，是理解成本、接入成本，还是结果不够稳定。",
        ],
    },
}


VALIDATION_SWITCH_COMMANDS = {
    "先别看频率，改看转化阻力": {
        "from_focus": "frequency",
        "target_command": "确认，先看转化阻力",
        "reply": "我先停止继续看频率，切到“转化阻力验证”。这样可以先判断用户究竟卡在哪一步，再决定要不要回来看频率。请你直接告诉我用户现在最容易卡在哪一步，是理解成本、接入成本，还是结果不够稳定。",
    },
    "先别看转化阻力，改看频率": {
        "from_focus": "conversion_resistance",
        "target_command": "确认，先看频率",
        "reply": "我先停止继续看转化阻力，切到“频率验证”。这样可以先判断这到底是不是高频问题，再决定是否值得继续深挖阻力。请你直接告诉我这个问题平均多久发生一次，最好顺手带上最近一次真实场景。",
    },
}


VALIDATION_FOLLOWUP_FLOWS = {
    ("frequency", 1): {
        "phase_goal": "确认高频问题是否造成真实损失",
        "stage_hint": "频率影响确认",
        "strategy_reason": "频率信号已记录，下一步确认它是否真的造成损失。",
        "summary_prefix": "用户补充了问题发生频率的描述。",
        "evidence_prefix": "频率线索",
        "recommendation": {
            "label": "先确认高频是否真的带来损失",
            "content": "把频率和真实损失连起来，再决定是否值得优先做",
            "rationale": "高频但无损失的问题，优先级仍可能不成立",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先确认高频是否真的带来损失",
                "content": "把频率和真实损失连起来，再决定是否值得优先做",
                "rationale": "高频但无损失的问题，优先级仍可能不成立",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "补真实损失",
                "content": "说明会多花多少时间、错过什么机会、造成什么错误",
                "rationale": "损失越具体，优先级越容易判断",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "区分高频噪音和高频痛点",
                "content": "判断这是单纯烦，还是会持续拖慢关键动作",
                "rationale": "不是所有高频问题都值得优先解决",
                "priority": 3,
            },
        ],
        "next_best_questions": [
            "为了继续推进，请直接回答如果这件事持续发生，实际会多花什么时间、错过什么机会，或者带来什么损失。"
        ],
        "reply_lines": [
            "我先按你的描述把当前判断收成“这是一个高频信号候选”，先不急着直接认定它值得优先做。",
            "下一步我会继续追问这个频率到底有没有真实后果，因为没有损失的高频问题不一定值得做成产品。",
            "请你直接告诉我，如果这件事持续发生，实际会多花什么时间、错过什么机会，或者带来什么损失。",
        ],
    },
    ("frequency", 2): {
        "phase_goal": "确认是否把该问题作为当前优先验证对象",
        "stage_hint": "频率结论确认",
        "strategy_reason": "频率与损失都已出现，当前先确认是否把它定义为优先问题。",
        "summary_prefix": "用户补充了高频问题带来的真实损失。",
        "evidence_prefix": "损失线索",
        "conversation_strategy": "confirm",
        "next_move": "summarize_and_confirm",
        "pending_confirmations": ["是否把这个问题定义为当前最值得优先验证的问题"],
        "recommendation": {
            "label": "先把这个问题锁成当前优先验证对象",
            "content": "如果你认可，我下一步就围绕它压缩最小验证方案",
            "rationale": "频率和损失都成立时，继续发散会拖慢验证节奏",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先把这个问题锁成当前优先验证对象",
                "content": "如果你认可，我下一步就围绕它压缩最小验证方案",
                "rationale": "频率和损失都成立时，继续发散会拖慢验证节奏",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "先停止继续扩散更多问题",
                "content": "先锁定这个问题，再看要不要补其他风险验证",
                "rationale": "优先问题不锁定，后续动作会继续飘",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "确认优先问题后再压缩方案",
                "content": "先别急着扩方案，先把优先级判断钉死",
                "rationale": "先定优先级，再定方案，返工更少",
                "priority": 3,
            },
        ],
        "next_best_questions": ["是否把这个问题定义为当前最值得优先验证的问题"],
        "reply_lines": [
            "基于你刚才补的频率和损失，我现在倾向判断这是一个值得优先推进的问题。",
            "如果你确认，我下一步就直接开始压缩最小验证方案，不再继续横向发散别的问题。",
            "你只需要确认：是否把这个问题定义为当前最值得优先验证的问题。",
        ],
    },
    ("conversion_resistance", 1): {
        "phase_goal": "确认首要阻力是否直接打断转化",
        "stage_hint": "转化阻力影响确认",
        "strategy_reason": "首要阻力已浮现，下一步确认它是否真的打断转化。",
        "summary_prefix": "用户补充了转化阻力的描述。",
        "evidence_prefix": "转化阻力线索",
        "recommendation": {
            "label": "先确认阻力会不会直接打断转化",
            "content": "先把阻力点和用户实际流失结果连起来",
            "rationale": "只有会直接打断转化的阻力，才值得优先压缩进 MVP",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先确认阻力会不会直接打断转化",
                "content": "先把阻力点和用户实际流失结果连起来",
                "rationale": "只有会直接打断转化的阻力，才值得优先压缩进 MVP",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "补流失结果",
                "content": "说明用户卡住后是放弃、延后，还是转去其他替代方案",
                "rationale": "结果越明确，越能判断阻力优先级",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "区分麻烦和致命阻力",
                "content": "先判断这只是麻烦，还是足以让用户退出流程",
                "rationale": "不是所有阻力都需要优先处理",
                "priority": 3,
            },
        ],
        "next_best_questions": [
            "为了继续推进，请直接回答一旦卡在这里，用户最常见的结果是放弃、延后，还是转去其他替代方案。"
        ],
        "reply_lines": [
            "我先按你的描述把当前阻力判断收成“首要阻力候选已经出现”，先不急着把它直接认定成最大问题。",
            "下一步我会继续追问这个阻力到底会不会直接打断转化，因为只有会导致流失的阻力才值得优先处理。",
            "请你直接告诉我，一旦卡在这里，用户最常见的结果是放弃、延后，还是转去其他替代方案。",
        ],
    },
}


VALIDATION_VAGUE_REPLY_HINTS = {
    ("frequency", 1): {
        "phase_goal": "明确问题发生频率是否足够高",
        "stage_hint": "推进频率验证",
        "strategy_reason": "这轮回答仍然太模糊，暂时不能推进到下一步。",
        "next_best_questions": [
            "为了继续推进，请直接回答这个问题是每天、每周，还是偶发出现，并补一个最近一次真实场景。"
        ],
        "recommendation": {
            "label": "先把频率说到可判断",
            "content": "直接回答每天、每周或偶发，并补一个最近一次场景",
            "rationale": "没有频率尺度，后续所有优先级判断都会漂",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先把频率说到可判断",
                "content": "直接回答每天、每周或偶发，并补一个最近一次场景",
                "rationale": "没有频率尺度，后续所有优先级判断都会漂",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "别再用概括词",
                "content": "避免“差不多”“还行”这类无法判断的说法",
                "rationale": "概括词无法支撑状态机推进",
                "priority": 2,
            },
        ],
        "reply_lines": [
            "这轮回答还不足以支持我判断频率。",
            "请你不要再用“差不多”这种概括说法，直接给我频率尺度和最近一次真实场景。",
        ],
    },
    ("conversion_resistance", 1): {
        "phase_goal": "明确转化阻力集中在哪一环",
        "stage_hint": "推进转化阻力验证",
        "strategy_reason": "这轮回答仍然太模糊，暂时不能推进阻力判断。",
        "next_best_questions": [
            "为了继续推进，请直接回答用户最容易卡在哪一步，并补一句卡住后通常是放弃、延后，还是转去其他替代方案。"
        ],
        "recommendation": {
            "label": "先把阻力说到可判断",
            "content": "直接指出最容易卡住的一步，并说明卡住后的常见结果",
            "rationale": "不说清楚卡点和流失结果，就无法判断阻力优先级",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先把阻力说到可判断",
                "content": "直接指出最容易卡住的一步，并说明卡住后的常见结果",
                "rationale": "不说清楚卡点和流失结果，就无法判断阻力优先级",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "别再用概括词",
                "content": "避免“还行”“差不多”这类无法判断的说法",
                "rationale": "概括词无法支持阻力判断",
                "priority": 2,
            },
        ],
        "reply_lines": [
            "这轮回答还不足以支持我判断转化阻力。",
            "请你不要再用“还行”这种概括说法，直接告诉我用户卡在哪一步，以及卡住后最常见的结果。",
        ],
    },
}


VAGUE_VALIDATION_PHRASES = ("差不多", "还行", "可能吧", "大概吧", "说不好", "不太确定")
