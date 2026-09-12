export const CONSENT_SCOPES = [
  {
    scope: "matching:v1",
    title: "关系匹配",
    purpose: "使用你主动填写的问卷生成可修正的关系信号，用于筛选和解释可继续了解的人。",
  },
  {
    scope: "conversation:v1",
    title: "双向交流",
    purpose: "在你主动邀请且双方同意后，用于保存站内消息、已读状态和必要的安全反馈。",
  },
  {
    scope: "outcomes:v1",
    title: "结果反馈",
    purpose: "在 7、14、30 天后记录相处感受，用于验证推荐是否真的带来安全、满意的结果。",
  },
] as const;
