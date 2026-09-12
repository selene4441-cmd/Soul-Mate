const flowSteps = [
  { id: "welcome", label: "欢迎与价值主张", state: "入口" },
  { id: "profile", label: "基础条件与边界", state: "最少输入" },
  { id: "questions", label: "高信息增益选择", state: "偏好诱导" },
  { id: "insights", label: "偏好洞察", state: "可修正" },
  { id: "searching", label: "匹配过程", state: "双人特征" },
  { id: "results", label: "推荐结果", state: "概率与解释" },
  { id: "candidate", label: "推荐依据", state: "可追溯" },
  { id: "matched", label: "模拟对话", state: "双向邀请" },
  { id: "feedback", label: "体验反馈", state: "结果标签" }
];

const questions = [
  {
    id: "growth",
    eyebrow: "成长方向",
    title: "未来一年，你更希望关系呈现哪种状态？",
    helper: "这里没有标准答案。我们想知道你更看重稳定的积累，还是持续的新变化。",
    gain: 15,
    options: {
      a: {
        value: "steady-growth",
        label: "一起稳定精进",
        detail: "各自有长期目标，也希望在节奏上互相支持"
      },
      b: {
        value: "explore-together",
        label: "持续探索新方向",
        detail: "愿意不断尝试，接受生活状态发生明显变化"
      }
    }
  },
  {
    id: "boundary",
    eyebrow: "时间与空间",
    title: "当对方需要一段独处时间时，你更接近哪种反应？",
    helper: "独处需求不代表冷淡。这个选择用于判断双方对联系感和自主空间的期待。",
    gain: 18,
    options: {
      a: {
        value: "respect-space",
        label: "理解并保持稳定的联系感",
        detail: "可以暂时少聊，但希望对方说明状态，不让关系失联"
      },
      b: {
        value: "stay-connected",
        label: "希望及时确认发生了什么",
        detail: "更在意当下沟通，不愿意让不确定性持续太久"
      }
    }
  },
  {
    id: "conflict",
    eyebrow: "冲突修复",
    title: "两个人出现分歧时，你通常更需要什么？",
    helper: "冲突本身不是问题，能否修复才是关系长期稳定的关键。",
    gain: 16,
    options: {
      a: {
        value: "pause-first",
        label: "先整理情绪，再认真沟通",
        detail: "短暂停顿有助于避免说出伤害彼此的话"
      },
      b: {
        value: "talk-now",
        label: "当下说清楚，不让问题过夜",
        detail: "及时沟通能让彼此更快恢复确定感"
      }
    }
  },
  {
    id: "support",
    eyebrow: "支持方式",
    title: "对方陷入低谷时，你更自然地会怎么做？",
    helper: "支持方式没有高低，重点是双方能否理解彼此需要的是陪伴还是行动。",
    gain: 14,
    options: {
      a: {
        value: "listen",
        label: "先倾听和陪伴",
        detail: "不急着给建议，希望对方感到被理解"
      },
      b: {
        value: "solve",
        label: "一起分析和找办法",
        detail: "通过推进问题本身帮助对方恢复掌控感"
      }
    }
  },
  {
    id: "pace",
    eyebrow: "关系节奏",
    title: "关系刚开始时，你更喜欢怎样的联系频率？",
    helper: "节奏匹配会直接影响现实可行性，也能减少一方觉得被追、一方觉得被冷落。",
    gain: 17,
    options: {
      a: {
        value: "steady",
        label: "稳定但不过度密集",
        detail: "保持持续在场，也给工作和独处留出空间"
      },
      b: {
        value: "flexible",
        label: "随性但保持热度",
        detail: "根据当下状态自然联系，变化本身没有问题"
      }
    }
  }
];

const insightMap = {
  growth: {
    "steady-growth": ["G1 成长节奏", "更看重稳定积累", 76, "你可能更安心于目标清晰、节奏可持续的共同成长。", "↗"],
    "explore-together": ["G1 成长节奏", "更看重持续探索", 81, "你可能更容易被愿意尝试新方向、接受生活变化的伙伴吸引。", "↗"]
  },
  boundary: {
    "respect-space": ["T1 时间边界", "需要说明状态，也尊重独处", 84, "你更看重稳定联系感与自主空间同时被保护。", "◷"],
    "stay-connected": ["T1 时间边界", "希望及时确认状态", 73, "不确定感会明显影响你，你更在意关系中的及时回应。", "◷"]
  },
  conflict: {
    "pause-first": ["R1 冲突修复", "先整理，再认真沟通", 79, "短暂停顿有助于你表达真实需求，而不是被情绪推着走。", "⌁"],
    "talk-now": ["R1 冲突修复", "及时沟通，不让问题过夜", 76, "你需要较快恢复确定感，也希望双方愿意直接面对问题。", "⌁"]
  },
  support: {
    listen: ["E1 支持方式", "先感受，再解决问题", 72, "陪伴和被理解，可能是你判断关系安全感的重要方式。", "○"],
    solve: ["E1 支持方式", "共同行动恢复掌控感", 74, "你可能更容易通过共同解决问题感受到关系的力量。", "◎"]
  },
  pace: {
    steady: ["M1 关系节奏", "稳定、有边界地在场", 80, "你希望关系持续连接，同时不侵占彼此的专注和独处时间。", "◌"],
    flexible: ["M1 关系节奏", "自然变化，但保持热度", 71, "你更接受联系频率随生活状态变化，只要情感回应持续存在。", "◌"]
  }
};

const candidates = [
  {
    id: "linxia",
    name: "林夏",
    avatar: "林",
    avatarClass: "",
    age: 29,
    city: "杭州",
    role: "产品设计师",
    baseScore: 80,
    confidence: 79,
    quote: "我希望关系不是两个人绑在一起，而是各自有空间，也愿意一起向前。",
    preferences: {
      growth: "explore-together",
      boundary: "respect-space",
      conflict: "pause-first",
      support: "listen",
      pace: "steady"
    },
    reasons: ["成长方向相近", "尊重独处时间", "冲突后愿意修复"],
    risk: "近期项目较忙，回复可能偏慢，但不接受失联式回避。",
    details: [
      "希望长期关系，也重视各自职业发展的连续性",
      "会用明确说明替代突然消失，尊重彼此独处需求",
      "发生分歧时倾向先整理情绪，再约定时间认真沟通"
    ],
    sources: [
      ["基础条件", "用户确认 · 1 项"],
      ["选择记录", "5 次取舍 · 已记录"],
      ["文本洞察", "2 条 · 可修改"],
      ["资料完整度", "82%"]
    ],
    opening: "你好呀，看到你也选了“先整理再沟通”，有点意外地一致。",
    replies: [
      "我也有同感。比起立刻分出对错，我更在意之后能不能把真实感受讲清楚。",
      "这个节奏挺好的。我们可以先从最近各自在忙什么聊起。",
      "同意。关系里有空间，不代表不重视对方。"
    ]
  },
  {
    id: "zhouyu",
    name: "周屿",
    avatar: "周",
    avatarClass: "gold",
    age: 31,
    city: "杭州",
    role: "独立研究者",
    baseScore: 76,
    confidence: 72,
    quote: "稳定不是停在原地，而是知道彼此正在往哪里走，并愿意为变化留位置。",
    preferences: {
      growth: "steady-growth",
      boundary: "respect-space",
      conflict: "talk-now",
      support: "solve",
      pace: "steady"
    },
    reasons: ["生活节奏接近", "更看重共同规划", "尊重自主空间"],
    risk: "更偏好明确计划，临时变化过多时可能需要额外沟通。",
    details: [
      "生活节奏稳定，重视共同规划，但不会要求完全同步",
      "更自然地通过分析问题表达关心",
      "能够接受独处，也希望重要变化被及时说明"
    ],
    sources: [
      ["基础条件", "用户确认 · 1 项"],
      ["选择记录", "5 次取舍 · 已记录"],
      ["文本洞察", "3 条 · 可修改"],
      ["资料完整度", "88%"]
    ],
    opening: "你好，我注意到我们都比较看重稳定的联系感。你最近生活里最稳定的一部分是什么？",
    replies: [
      "听起来很有画面。稳定的东西不一定无聊，反而能让人有空间做更长期的事。",
      "我也这么觉得。计划不是控制，而是让彼此知道怎样更好地靠近。",
      "同意，提前说明比突然改变更让人安心。"
    ]
  },
  {
    id: "chenmo",
    name: "陈默",
    avatar: "陈",
    avatarClass: "coral",
    age: 28,
    city: "上海",
    role: "纪录片剪辑师",
    baseScore: 73,
    confidence: 68,
    quote: "我喜欢有热度也有留白的关系。我们可以靠近，但不必占领彼此全部生活。",
    preferences: {
      growth: "explore-together",
      boundary: "stay-connected",
      conflict: "pause-first",
      support: "listen",
      pace: "flexible"
    },
    reasons: ["审美与表达方式接近", "愿意讨论生活变化", "有较强的自我边界"],
    risk: "上海与杭州存在通勤成本，生活安排需要双方进一步确认。",
    details: [
      "接受关系状态变化，也会主动表达近期需要",
      "在不确定时希望得到明确回应，不喜欢猜测",
      "对个人创作时间有较强需求，会提前说明安排"
    ],
    sources: [
      ["基础条件", "用户确认 · 1 项"],
      ["选择记录", "5 次取舍 · 已记录"],
      ["文本洞察", "1 条 · 可修改"],
      ["资料完整度", "69%"]
    ],
    opening: "你好，看到你也很在意关系的节奏。你会怎么描述理想的“有空间但不失联”？",
    replies: [
      "这个描述很准确。有空间，不代表把对方排除在自己的生活之外。",
      "我也会这样。忙的时候说明状态，比让对方猜更容易建立安全感。",
      "好的，那我们可以先从彼此最近在投入的事情聊起。"
    ]
  }
];

const state = {
  screen: "welcome",
  questionIndex: 0,
  answers: {},
  intention: "long-term",
  selectedCandidateId: "linxia",
  feedback: null,
  messages: [],
  replyIndex: 0,
  matchCandidateId: null
};

const screenEls = Array.from(document.querySelectorAll("[data-screen]"));
const flowNav = document.getElementById("flowNav");
const modelTitle = document.getElementById("modelTitle");
const modelSummary = document.getElementById("modelSummary");
const modelChips = document.getElementById("modelChips");
const toast = document.getElementById("toast");
const demoConsole = document.getElementById("demoConsole");
const appViewport = document.getElementById("app");

function getCandidate(id) {
  return candidates.find((candidate) => candidate.id === id) || candidates[0];
}

function candidateScore(candidate) {
  const matches = Object.entries(candidate.preferences)
    .filter(([questionId, preferredValue]) => state.answers[questionId] === preferredValue)
    .length;
  return Math.min(96, candidate.baseScore + matches * 3);
}

function renderFlowNav() {
  flowNav.innerHTML = flowSteps.map((step, index) => `
    <li>
      <button type="button" data-flow="${step.id}" class="${state.screen === step.id ? "is-current" : ""}">
        <span class="flow-index">${String(index + 1).padStart(2, "0")}</span>
        <span class="flow-label">${step.label}</span>
        <span class="flow-state">${step.state}</span>
      </button>
    </li>
  `).join("");
}

function updateModelPanel() {
  const answerCount = Object.keys(state.answers).length;
  const content = {
    welcome: ["当前起点", "演示不会连接后端，也不会产生真实匹配。", ["Mock data", "No network"]],
    profile: ["硬约束", "年龄、地域和关系目标只用于筛选推荐是否可用。", ["C1", "C2", "硬过滤"]],
    questions: ["选择记录", "每个选择都在降低偏好不确定性。", [`${answerCount}/5 已选`, "信息增益"]],
    insights: ["可修正洞察", "偏好由选择生成，不是固定标签。", ["G1", "T1/T2", "R1", "可修改"]],
    searching: ["双人计算", "先过滤不可协商项，再计算成长同向与边界兼容。", ["P1", "P11", "P12", "P13"]],
    results: ["结果概率", "分数代表关系结果良好的预测概率，并附带置信度。", [`${answerCount}/5 行为特征`, "校准概率"]],
    candidate: ["推荐解释", "每个正向和风险因素都能追溯到来源。", ["证据", "置信度", "风险提示"]],
    matched: ["互动结果", "只有双方同意后才开启沟通，互动过程继续产生标签。", ["双向邀请", "互动事件"]],
    feedback: ["结果标签", "体验反馈会作为下一轮推荐的校准数据。", ["y_accept", "y_satisfaction"]]
  };
  const [title, summary, chips] = content[state.screen] || content.welcome;
  modelTitle.textContent = title;
  modelSummary.textContent = summary;
  modelChips.innerHTML = chips.map((chip) => `<span class="model-chip">${chip}</span>`).join("");
}

function showScreen(screenId) {
  state.screen = screenId;
  screenEls.forEach((screen) => {
    const active = screen.dataset.screen === screenId;
    screen.hidden = !active;
    screen.classList.toggle("is-active", active);
  });

  if (screenId === "questions") renderQuestion();
  if (screenId === "insights") renderInsights();
  if (screenId === "results") renderCandidates();
  if (screenId === "candidate") renderCandidateDetail();
  if (screenId === "matched") renderConversation();
  if (screenId === "feedback") resetFeedback();

  renderFlowNav();
  updateModelPanel();
  appViewport.scrollTo({ top: 0, behavior: "smooth" });
  demoConsole.classList.remove("is-open");
}

function renderQuestion() {
  const question = questions[state.questionIndex];
  const selectedValue = state.answers[question.id];
  const answerCount = state.questionIndex + (selectedValue ? 1 : 0);
  const uncertainty = Math.max(20, 100 - answerCount * 17);

  document.getElementById("questionCounter").textContent = `选择 ${state.questionIndex + 1} / ${questions.length}`;
  document.getElementById("uncertaintyValue").textContent = `${uncertainty}%`;
  document.getElementById("progressBar").style.width = `${((state.questionIndex + 1) / questions.length) * 100}%`;
  document.getElementById("questionEyebrow").textContent = question.eyebrow;
  document.getElementById("questionTitle").textContent = question.title;
  document.getElementById("questionHelper").textContent = question.helper;

  const options = document.getElementById("answerOptions");
  options.innerHTML = ["a", "b"].map((key) => {
    const option = question.options[key];
    const selected = selectedValue === option.value;
    return `
      <button class="answer-card ${selected ? "is-selected" : ""}" type="button" data-answer="${option.value}">
        <span class="answer-letter">${key.toUpperCase()}</span>
        <span><strong>${option.label}</strong><small>${option.detail}</small></span>
      </button>
    `;
  }).join("");

  const feedback = document.getElementById("choiceFeedback");
  feedback.textContent = selectedValue ? "这次选择已记录，下一位候选人展示时会更关注这项兼容性。" : "";
  const nextButton = document.getElementById("questionNext");
  nextButton.hidden = !selectedValue;
  nextButton.textContent = state.questionIndex === questions.length - 1 ? "查看我的偏好" : "下一个选择";
}

function selectAnswer(value) {
  const question = questions[state.questionIndex];
  state.answers[question.id] = value;

  document.querySelectorAll("[data-answer]").forEach((button) => {
    const selected = button.dataset.answer === value;
    button.classList.toggle("is-selected", selected);
    button.classList.toggle("is-dimmed", !selected);
  });

  const option = Object.values(question.options).find((item) => item.value === value);
  document.getElementById("choiceFeedback").textContent = `已记录：${option.label}。预计降低的不确定性约 ${question.gain}%。`;
  document.getElementById("uncertaintyValue").textContent = `${Math.max(20, 100 - (state.questionIndex + 1) * 17)}%`;
  const nextButton = document.getElementById("questionNext");
  nextButton.hidden = false;
  nextButton.textContent = state.questionIndex === questions.length - 1 ? "查看我的偏好" : "下一个选择";
  updateModelPanel();
}

function renderInsights() {
  const list = document.getElementById("insightList");
  const insights = questions.map((question) => {
    const answer = state.answers[question.id] || "a";
    const option = Object.values(question.options).find((item) => item.value === answer);
    return insightMap[question.id]?.[option?.value] || insightMap[question.id]?.a;
  });

  list.innerHTML = insights.map(([tag, title, confidence, description, icon]) => `
    <article class="insight-card">
      <div class="insight-card-header">
        <span class="insight-icon">${icon}</span>
        <div><span class="candidate-meta">${tag}</span><h3>${title}</h3></div>
        <span class="insight-score">${confidence}%</span>
      </div>
      <p>${description}</p>
      <div class="confidence-track" aria-label="置信度 ${confidence}%"><span style="width:${confidence}%"></span></div>
    </article>
  `).join("");

  list.querySelectorAll(".insight-card").forEach((card) => {
    card.addEventListener("click", () => showToast("演示版：真实产品应允许用户修改或否定这项判断。"));
  });
}

function renderCandidates() {
  const list = document.getElementById("candidateList");
  list.innerHTML = candidates.map((candidate, index) => {
    const score = candidateScore(candidate);
    return `
      <article class="candidate-card">
        <span class="avatar ${candidate.avatarClass}">${candidate.avatar}</span>
        <div class="candidate-main">
          <h3>${candidate.name}，${candidate.age}</h3>
          <span class="candidate-meta">${candidate.city} · ${candidate.role}</span>
          <div class="candidate-score-row">
            <span class="candidate-score">${score}%</span>
            <span class="score-label">关系结果预测 · 置信度 ${candidate.confidence}%</span>
          </div>
          <div class="candidate-reasons">
            ${candidate.reasons.map((reason) => `<span class="reason-chip">${reason}</span>`).join("")}
          </div>
        </div>
        <button class="candidate-action" type="button" data-candidate="${candidate.id}">
          ${index === 0 ? "查看最匹配的人" : `了解 ${candidate.name}`}
        </button>
      </article>
    `;
  }).join("");
}

function renderCandidateDetail() {
  const candidate = getCandidate(state.selectedCandidateId);
  const score = candidateScore(candidate);
  const matchCount = Object.entries(candidate.preferences)
    .filter(([questionId, preferredValue]) => state.answers[questionId] === preferredValue)
    .length;

  document.getElementById("candidateDetail").innerHTML = `
    <div class="candidate-profile">
      <span class="avatar ${candidate.avatarClass}">${candidate.avatar}</span>
      <h2>${candidate.name}，${candidate.age}</h2>
      <span class="candidate-meta">${candidate.city} · ${candidate.role}</span>
      <p>“${candidate.quote}”</p>
    </div>

    <section class="detail-section">
      <h3>为什么推荐给你</h3>
      <ul>
        ${candidate.details.map((detail) => `<li>${detail}</li>`).join("")}
      </ul>
    </section>

    <section class="detail-section warning">
      <h3>需要提前知道</h3>
      <ul><li>${candidate.risk}</li></ul>
    </section>

    <section class="detail-section">
      <h3>本次判断依据</h3>
      <div class="candidate-score-row">
        <span class="candidate-score">${score}%</span>
        <span class="score-label">预测概率 · 置信度 ${candidate.confidence}% · 行为选择命中 ${matchCount}/5</span>
      </div>
      <div class="provenance-grid" style="margin-top:12px">
        ${candidate.sources.map(([label, value]) => `<div class="provenance-item"><strong>${label}</strong>${value}</div>`).join("")}
      </div>
    </section>

    <button id="inviteButton" class="primary-button" type="button">发出了解邀请</button>
  `;

  document.getElementById("inviteButton").addEventListener("click", () => {
    state.selectedCandidateId = candidate.id;
    showScreen("matched");
  });
}

function renderConversation() {
  const candidate = getCandidate(state.selectedCandidateId);
  if (state.matchCandidateId !== candidate.id) {
    state.matchCandidateId = candidate.id;
    state.replyIndex = 0;
    state.messages = [{ from: "them", text: candidate.opening }];
  }

  document.getElementById("conversationAvatar").textContent = candidate.avatar;
  document.getElementById("conversationAvatar").className = `avatar avatar-small ${candidate.avatarClass}`;
  document.getElementById("conversationName").textContent = candidate.name;
  renderMessages();
}

function renderMessages() {
  const list = document.getElementById("messageList");
  list.innerHTML = "";
  state.messages.forEach((message) => {
    const node = document.createElement("div");
    node.className = `message ${message.from === "me" ? "message-me" : "message-them"}`;
    node.textContent = message.text;
    list.appendChild(node);
  });
  list.scrollTop = list.scrollHeight;
}

function sendMessage() {
  const input = document.getElementById("messageInput");
  const text = input.value.trim();
  if (!text) {
    showToast("先输入一句模拟回复");
    return;
  }

  state.messages.push({ from: "me", text });
  input.value = "";
  renderMessages();

  const candidate = getCandidate(state.selectedCandidateId);
  const reply = candidate.replies[state.replyIndex % candidate.replies.length];
  state.replyIndex += 1;
  window.setTimeout(() => {
    state.messages.push({ from: "them", text: reply });
    renderMessages();
  }, 650);
}

function resetFeedback() {
  state.feedback = null;
  document.querySelectorAll('[data-choice-group="feedback"] button').forEach((button) => {
    button.classList.remove("is-selected");
  });
  document.getElementById("feedbackThanks").hidden = true;
}

function selectFeedback(value) {
  state.feedback = value;
  document.querySelectorAll('[data-choice-group="feedback"] button').forEach((button) => {
    button.classList.toggle("is-selected", button.dataset.value === value);
  });
  document.getElementById("feedbackThanks").hidden = false;
  updateModelPanel();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("is-visible"), 2200);
}

function resetDemo() {
  state.questionIndex = 0;
  state.answers = {};
  state.intention = "long-term";
  state.selectedCandidateId = "linxia";
  state.feedback = null;
  state.messages = [];
  state.replyIndex = 0;
  state.matchCandidateId = null;

  document.querySelectorAll('[data-choice-group="intention"] button').forEach((button) => {
    button.classList.toggle("is-selected", button.dataset.value === "long-term");
  });
  document.getElementById("ageInput").value = "28";
  document.getElementById("citySelect").selectedIndex = 0;
  document.getElementById("messageInput").value = "";
  resetFeedback();
  showScreen("welcome");
  showToast("演示数据已重置");
}

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof Element)) return;

  const nextButton = target.closest("[data-next]");
  if (nextButton) {
    showScreen(nextButton.dataset.next);
    return;
  }

  const answerButton = target.closest("[data-answer]");
  if (answerButton) {
    selectAnswer(answerButton.dataset.answer);
    return;
  }

  const candidateButton = target.closest("[data-candidate]");
  if (candidateButton) {
    state.selectedCandidateId = candidateButton.dataset.candidate;
    showScreen("candidate");
    return;
  }

  const flowButton = target.closest("[data-flow]");
  if (flowButton) {
    showScreen(flowButton.dataset.flow);
    return;
  }

  const choiceButton = target.closest("[data-choice-group] button");
  if (choiceButton) {
    const group = choiceButton.closest("[data-choice-group]").dataset.choiceGroup;
    if (group === "intention") {
      state.intention = choiceButton.dataset.value;
      choiceButton.parentElement.querySelectorAll("button").forEach((button) => button.classList.remove("is-selected"));
      choiceButton.classList.add("is-selected");
    }
    if (group === "feedback") selectFeedback(choiceButton.dataset.value);
  }
});

document.getElementById("questionNext").addEventListener("click", () => {
  const question = questions[state.questionIndex];
  if (!state.answers[question.id]) {
    showToast("请先选择更接近你的答案");
    return;
  }
  if (state.questionIndex < questions.length - 1) {
    state.questionIndex += 1;
    renderQuestion();
    appViewport.scrollTo({ top: 0, behavior: "smooth" });
    updateModelPanel();
  } else {
    showScreen("insights");
  }
});

document.getElementById("sendMessage").addEventListener("click", sendMessage);
document.getElementById("messageInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter") sendMessage();
});
document.getElementById("restartDemo").addEventListener("click", resetDemo);
document.getElementById("resetFromConsole").addEventListener("click", resetDemo);
document.getElementById("consoleToggle").addEventListener("click", () => demoConsole.classList.add("is-open"));
document.getElementById("closeConsole").addEventListener("click", () => demoConsole.classList.remove("is-open"));

window.__soulmateDemo = {
  flowSteps,
  questions,
  candidates,
  state,
  showScreen,
  resetDemo
};

renderFlowNav();
updateModelPanel();